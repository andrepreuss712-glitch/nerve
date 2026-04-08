import stripe
from datetime import datetime
from flask import Blueprint, redirect, request, url_for, flash, g, render_template
from flask import session as flask_session
from sqlalchemy import update as sa_update
from routes.auth import login_required
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_IDS
from database.db import get_session
from database.models import Organisation, BillingEvent

stripe.api_key = STRIPE_SECRET_KEY
payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

# ── Checkout Session (PAY-01, D-02) ──────────────────────────────────────────
@payments_bp.route('/checkout/<plan>', methods=['POST'])
@login_required
def create_checkout(plan):
    price_id = STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        flash('Ungültiger Tarif.', 'error')
        return redirect(url_for('payments.pricing'))

    # Create or reuse Stripe Customer (D-06)
    customer_id = g.org.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=g.user.email,
            name=g.org.billing_name or g.org.name,
            metadata={'org_id': str(g.org.id)},
        )
        customer_id = customer.id
        db = get_session()
        try:
            db.execute(
                sa_update(Organisation)
                .where(Organisation.id == g.org.id)
                .values(stripe_customer_id=customer_id)
            )
            db.commit()
        finally:
            db.close()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=url_for('payments.checkout_success', _external=True),
        cancel_url=url_for('payments.pricing', _external=True),
        metadata={'org_id': str(g.org.id), 'plan': plan},
        automatic_tax={'enabled': True},  # Phase 04.7.2 D-03 — requires active Tax Registration (HT-01)
    )
    return redirect(session.url, code=303)


# ── Checkout Success Redirect (D-11, D-12 — NOT activation) ──────────────────
@payments_bp.route('/checkout/success')
@login_required
def checkout_success():
    flash('Abo aktiviert! Willkommen bei NERVE.', 'success')
    return redirect(url_for('dashboard.index'))


# ── Stripe Webhook (PAY-02, PAY-03, D-04) ────────────────────────────────────
@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data          # raw bytes — NOT request.get_json()
    sig = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        print('[Stripe] Webhook signature verification failed')
        return '', 400

    event_id = event['id']
    db = get_session()
    try:
        # Idempotency check (PAY-03, D-04)
        existing = db.query(BillingEvent).filter_by(stripe_event_id=event_id).first()
        if existing:
            print(f'[Stripe] Duplicate event {event_id} — skipping')
            return '', 200

        etype = event['type']
        obj   = event['data']['object']

        if etype == 'checkout.session.completed':
            _activate_subscription(db, obj)
        elif etype == 'customer.subscription.updated':
            _sync_subscription(db, obj)
        elif etype == 'customer.subscription.deleted':
            _cancel_subscription(db, obj)
        elif etype == 'invoice.paid':
            _reset_fair_use_on_invoice(db, obj)
        elif etype == 'invoice.payment_succeeded':
            try:
                _record_revenue(db, obj)
            except Exception as _rev_e:
                print(f"[Revenue] _record_revenue failed: {_rev_e}")
        elif etype == 'invoice.payment_failed':
            _handle_payment_failed(db, obj)

        # Record event for dedup
        db.add(BillingEvent(
            org_id=_resolve_org_id(db, event) or 1,
            typ=etype,
            stripe_event_id=event_id,
        ))
        db.commit()
        print(f'[Stripe] Processed {etype} (event {event_id})')
    except Exception as e:
        print(f'[Stripe] Webhook error: {e}')
        db.rollback()
        return '', 500
    finally:
        db.close()
    return '', 200


# ── Customer Portal (PAY-04, D-05) ───────────────────────────────────────────
@payments_bp.route('/portal', methods=['POST'])
@login_required
def customer_portal():
    if not g.org.stripe_customer_id:
        flash('Kein aktives Abo gefunden.', 'warning')
        return redirect(url_for('payments.pricing'))
    portal = stripe.billing_portal.Session.create(
        customer=g.org.stripe_customer_id,
        return_url=url_for('settings.index', _external=True) + '?tab=billing',
    )
    return redirect(portal.url, code=303)


# ── Pricing page route (placeholder — full template in Plan 02) ───────────────
@payments_bp.route('/pricing')
def pricing():
    from config import PLANS
    user_logged_in = bool(flask_session.get('user_id'))
    return render_template(
        'pricing.html',
        plans=PLANS,
        logged_in=user_logged_in,
        price_ids=STRIPE_PRICE_IDS,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _activate_subscription(db, session_obj):
    """checkout.session.completed — activate org subscription (D-02, PAY-02)."""
    org_id = int(session_obj.get('metadata', {}).get('org_id', 0))
    if not org_id:
        print('[Stripe] checkout.session.completed missing org_id in metadata')
        return
    plan_key = session_obj.get('metadata', {}).get('plan', 'starter')
    db.execute(
        sa_update(Organisation)
        .where(Organisation.id == org_id)
        .values(
            stripe_customer_id=session_obj.get('customer'),
            stripe_subscription_id=session_obj.get('subscription'),
            stripe_price_id=STRIPE_PRICE_IDS.get(plan_key, ''),
            subscription_status='active',
            plan=plan_key,
        )
    )
    print(f'[Stripe] Subscription activated for org {org_id}, plan={plan_key}')


def _sync_subscription(db, sub_obj):
    """customer.subscription.updated — sync status."""
    sub_id = sub_obj.get('id')
    status = sub_obj.get('status', 'active')
    db.execute(
        sa_update(Organisation)
        .where(Organisation.stripe_subscription_id == sub_id)
        .values(subscription_status=status)
    )
    print(f'[Stripe] Subscription {sub_id} updated to {status}')


def _cancel_subscription(db, sub_obj):
    """customer.subscription.deleted — mark canceled."""
    sub_id = sub_obj.get('id')
    db.execute(
        sa_update(Organisation)
        .where(Organisation.stripe_subscription_id == sub_id)
        .values(subscription_status='canceled')
    )
    print(f'[Stripe] Subscription {sub_id} canceled')


def _reset_fair_use_on_invoice(db, invoice_obj):
    """invoice.paid — reset monthly fair-use counters."""
    cust_id = invoice_obj.get('customer')
    if cust_id:
        db.execute(
            sa_update(Organisation)
            .where(Organisation.stripe_customer_id == cust_id)
            .values(
                live_minutes_used=0,
                training_sessions_used=0,
                fair_use_reset_month=datetime.now().strftime('%Y-%m'),
            )
        )
        print(f'[Stripe] Fair-use reset for customer {cust_id}')


def _handle_payment_failed(db, invoice_obj):
    """invoice.payment_failed — mark subscription as past_due."""
    cust_id = invoice_obj.get('customer')
    if cust_id:
        db.execute(
            sa_update(Organisation)
            .where(Organisation.stripe_customer_id == cust_id)
            .values(subscription_status='past_due')
        )
        print(f'[Stripe] Payment failed for customer {cust_id}')


# ── Phase 04.7.2 — Revenue Tracking ──────────────────────────────────────────

EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
    'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK',
    'SI', 'ES', 'SE',
}


def _classify_tax_treatment(country, tax_amount_cents):
    """Klassifiziert Stripe-Invoice nach DE_19 / EU_RC / DRITTLAND.
    - DE + USt > 0 → DE_19 (Inland 19%)
    - EU (nicht DE) → EU_RC (Reverse Charge, tax_amount typisch 0)
    - sonst → DRITTLAND (Nicht-EU, nicht steuerbar)
    Fallback bei country=None: conservative — DE_19 nur wenn USt>0, sonst DRITTLAND.
    """
    if not country:
        return 'DE_19' if tax_amount_cents > 0 else 'DRITTLAND'
    country = country.upper()
    if country == 'DE':
        return 'DE_19'
    if country in EU_COUNTRIES:
        return 'EU_RC'
    return 'DRITTLAND'


def _record_revenue(db, invoice_obj):
    """Schreibt RevenueLog aus invoice.payment_succeeded Event.
    Idempotent via UNIQUE(stripe_invoice_id).
    """
    import json as _json
    from datetime import datetime
    from database.models import RevenueLog

    invoice_id = invoice_obj.get('id')
    if not invoice_id:
        return

    # Idempotency check
    existing = db.query(RevenueLog).filter_by(stripe_invoice_id=invoice_id).first()
    if existing:
        return

    customer_id = invoice_obj.get('customer')
    country = None
    if customer_id:
        try:
            cust = stripe.Customer.retrieve(customer_id)
            addr = (cust.get('address') or {}) if hasattr(cust, 'get') else {}
            country = (addr or {}).get('country')
        except Exception as e:
            print(f"[Revenue] customer retrieve failed: {e}")

    # Sum tax from all line items; capture plan_key from first line
    total_tax = 0
    plan_key = None
    for line in (invoice_obj.get('lines') or {}).get('data', []) or []:
        for ta in (line.get('tax_amounts') or []):
            total_tax += int(ta.get('amount') or 0)
        if not plan_key:
            price = line.get('price') or {}
            plan_key = price.get('lookup_key') or price.get('nickname')

    netto_cents = int(invoice_obj.get('subtotal') or 0)
    brutto_cents = int(invoice_obj.get('total') or 0)
    currency = (invoice_obj.get('currency') or 'eur').upper()
    tax_treatment = _classify_tax_treatment(country, total_tax)

    paid_at_ts = ((invoice_obj.get('status_transitions') or {}).get('paid_at') or 0)
    paid_at = datetime.fromtimestamp(paid_at_ts) if paid_at_ts else datetime.utcnow()

    # org resolution via stripe_customer_id on Organisation (Phase 04 Pattern)
    org_id = None
    if customer_id:
        try:
            org = db.query(Organisation).filter_by(stripe_customer_id=customer_id).first()
            if org:
                org_id = org.id
        except Exception as e:
            print(f"[Revenue] org resolution failed: {e}")

    db.add(RevenueLog(
        stripe_invoice_id=invoice_id,
        stripe_customer_id=customer_id,
        org_id=org_id,
        paid_at=paid_at,
        netto_cents=netto_cents,
        ust_cents=total_tax,
        brutto_cents=brutto_cents,
        currency=currency,
        country=country,
        tax_treatment=tax_treatment,
        plan_key=plan_key,
        raw_json=_json.dumps(invoice_obj, default=str)[:50000],
    ))
    db.commit()
    print(f"[Revenue] logged {invoice_id}: {netto_cents/100}EUR netto, {tax_treatment}, {country}")


def _resolve_org_id(db, event):
    """Extract org_id from event metadata or customer lookup."""
    obj = event['data']['object']
    # Try metadata first
    org_id = obj.get('metadata', {}).get('org_id')
    if org_id:
        return int(org_id)
    # Try customer lookup
    cust_id = obj.get('customer')
    if cust_id:
        org = db.query(Organisation).filter_by(stripe_customer_id=cust_id).first()
        if org:
            return org.id
    return None
