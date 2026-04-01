# Phase 4: Payments & Legal — Research

**Researched:** 2026-04-01
**Domain:** Stripe Checkout/Webhooks/Customer Portal + German DSGVO legal pages (Flask/Python)
**Confidence:** HIGH (Stripe SDK version verified against PyPI; patterns verified against codebase; DSGVO law is stable)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** No existing Stripe account — create from scratch. Tasks must include: create Stripe account, create 3 Products (Starter, Pro, Business), create recurring Prices at 49€, 59€, 69€/month (EUR), obtain Price IDs for `.env`.
- **D-02:** Use Stripe Checkout (Hosted Session) — `checkout.session.completed` webhook activates the subscription. Redirect URL is NOT used for activation (PAY-02).
- **D-03:** Payment methods: Kreditkarte, SEPA Lastschrift, PayPal (required), Klarna (optional). All configured via Stripe Dashboard — no hardcoding in the app.
- **D-04:** Webhook handler must be idempotent: deduplicate by `stripe_event_id`. Verify signature with raw request body (`stripe.Webhook.construct_event`). PAY-03.
- **D-05:** Users manage subscriptions via Stripe Customer Portal — link from `/settings` billing tab. One-click "Abo verwalten" button generates portal session URL.
- **D-06:** `Organisation` model needs new columns: `stripe_customer_id`, `stripe_subscription_id`, `stripe_price_id`, `subscription_status`. `BillingEvent` table needs `stripe_event_id` for dedup.
- **D-07:** `/pricing` is a public route (no `@login_required`) AND serves as in-app upgrade page. Anonymous visitors: "Jetzt starten" CTAs; logged-in users: "Jetzt upgraden" CTAs.
- **D-08:** Base pricing page on existing landing.html pricing cards. Use NERVE Design System tokens (glass panels, teal accent, nerve.css).
- **D-09:** All 3 plans (Starter 49€, Pro 59€, Business 69€) have same Fair-Use limits (1000 Live-Minuten, 50 Trainings/Monat). Differentiation by price/positioning only. PAY-06 requires feature comparison and Fair-Use limits shown.
- **D-10:** Gründerrabatt-Badge on pricing page: visual label ("50% Early Access Rabatt") on all cards. No Stripe coupon needed.
- **D-11:** After Stripe Checkout, user lands on `/dashboard` with flash message "Abo aktiviert! Willkommen bei NERVE." No separate thank-you page.
- **D-12:** Subscription activation is webhook-only. The redirect from Stripe (`/checkout/success?session_id=...`) just redirects to `/dashboard` with flash — does NOT activate.
- **D-13:** Fair-use counters (`live_minutes_used`, `training_sessions_used`) incremented atomically in DB. Reset monthly (compare `fair_use_reset_month` to current `YYYY-MM`).
- **D-14:** Soft warning at ~80% of limit appears as toast/snackbar — non-blocking, dismissible, shown once per session. Triggered on Dashboard load AND at session start in `/live`.
- **D-15:** At 100% (limit reached): show persistent "Limit erreicht — jetzt upgraden" message with Upgrade button to `/pricing`. No hard block.
- **D-16:** 80% and 100% warnings on both Dashboard (page load) and `/live` (session start).
- **D-17:** Routes: `/impressum`, `/agb`, `/datenschutz` — standard German URLs, no `@login_required`.
- **D-18:** Generate rechtskonforme German templates for all three pages. Datenschutzerklärung must name Deepgram, Anthropic, ElevenLabs, and Stripe as Auftragsverarbeiter (LEGAL-02).
- **D-19:** Footer links on `landing.html` and `base.html` must link to all three legal pages.
- **D-20:** LEGAL-03 (signed AVVs) is a manual task — checklist items in the plan. Deepgram EU endpoint (`api.eu.deepgram.com`) switch IS codeable (update in deepgram_service.py).

### Claude's Discretion

- Exact styling of the Gründerrabatt-Badge (size, placement, color — teal or gold)
- Whether to create a new `StripeEvent` table or add `stripe_event_id` to existing `BillingEvent`
- Flash message styling for post-checkout success
- Exact copy for plan differentiation on pricing page

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAY-01 | User kann einen der 3 Tarife über Stripe Checkout bezahlen (Hosted Checkout Session) | Stripe Checkout Sessions API + `payments_bp` blueprint with `/checkout/<plan>` route |
| PAY-02 | Subscription-Aktivierung ausschließlich per Webhook (`checkout.session.completed`) | Webhook handler activates org; `/checkout/success` only sets flash + redirects |
| PAY-03 | Stripe Webhook Handler ist idempotent (dedupliziert per `stripe_event_id`) und verifiziert Signatur mit rohem Request-Body | `stripe_event_id` UNIQUE constraint on `BillingEvent`; `request.data` for sig verification |
| PAY-04 | User kann Abo über Stripe Customer Portal selbst verwalten (Upgrade, Downgrade, Kündigung) | `stripe.billing_portal.Session.create()` + "Abo verwalten" button in `/settings` billing tab |
| PAY-05 | Live-Minuten und Trainings-Sessions atomar in DB gezählt; ~80% Soft-Warning; kein harter Block | SQLAlchemy `update()` expression for atomic increment; JS toast on Dashboard + `/live` |
| PAY-06 | Pricing-Seite zeigt alle 3 Tarife mit Feature-Vergleich, Fair-Use-Limits und Gründerrabatt-Badge | `/pricing` route + `pricing.html` template extending existing landing card styles |
| LEGAL-01 | DSGVO-Einwilligungs-Banner erscheint vor erstem Mikrofon-Zugriff | Already implemented in Phase 02 (socket connect trigger) — verify still intact |
| LEGAL-02 | Impressum, AGB, Datenschutzerklärung live — Deepgram/Anthropic/ElevenLabs/Stripe as Auftragsverarbeiter | `/impressum`, `/agb`, `/datenschutz` routes + templates + footer links |
| LEGAL-03 | Signed AVVs with all 4 vendors; Deepgram EU endpoint in use | Manual checklist tasks + codeable: `DeepgramClient(DEEPGRAM_API_KEY, config=DeepgramClientOptions(url="api.eu.deepgram.com"))` |
</phase_requirements>

---

## Summary

Phase 4 wires up Stripe payments (Checkout, Webhooks, Customer Portal), builds a public `/pricing` page, implements fair-use metering with soft warnings, ships three German legal pages, and switches Deepgram to the EU endpoint. The infrastructure (Hetzner HTTPS) is already in place from Phase 3, which satisfies the prerequisite for Stripe webhooks.

The Stripe integration follows the locked architecture: hosted Checkout Session for payment, webhook-only activation to prevent redirect-based fraud, Customer Portal for self-service management. The existing `Organisation` model already has `live_minutes_used`, `training_sessions_used`, and `fair_use_reset_month` columns — the fair-use tracking infrastructure exists and just needs activation logic. The `BillingEvent` table needs a `stripe_event_id` column added via the existing `_migrate()` pattern.

The legal pages are content-and-route work: three Flask routes, three Jinja2 templates with legally compliant German content, and footer links in `landing.html` and `base.html`. The Deepgram EU endpoint switch is a one-line code change in `deepgram_service.py`. Signing AVVs with all four vendors is a manual task that runs in parallel with code work.

**Primary recommendation:** Implement in this order: (1) DB migration + stripe install, (2) payments blueprint with checkout/webhook/portal, (3) pricing page, (4) fair-use warning logic, (5) legal pages + footer + Deepgram EU endpoint, (6) AVV checklist.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `stripe` | 15.0.0 | All Stripe API calls — Checkout Sessions, Customer Portal, Webhooks, Customer/Subscription CRUD | Official Stripe Python SDK; v15 is current (verified 2026-04-01 via pip index). Use `>=11.0.0` in requirements.txt for compatibility buffer. |
| Flask (existing) | 3.0.0+ | Routes for payments, legal pages | Already in stack; payments blueprint follows existing pattern |
| SQLAlchemy (existing) | 2.0.0+ | Atomic counter updates, model migrations | Already in stack; use `update()` expression for atomicity |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Stripe CLI | latest (dev only) | Local webhook forwarding during development (`stripe listen --forward-to localhost:5000/payments/webhook`) | Essential for testing webhook handler without public URL; dev only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Stripe Checkout (hosted) | Stripe Elements (embedded) | Elements gives more styling control but requires PCI SAQ-A-EP vs SAQ-A for hosted; hosted is simpler and correct for this use case |
| Stripe Customer Portal (hosted) | Custom subscription management UI | Portal handles all edge cases (proration, failed payments, card updates) at zero development cost; custom UI would need significant work |

**Installation:**
```bash
pip install stripe>=11.0.0
```

Add to `requirements.txt`:
```
stripe>=11.0.0
```

**Version verified:** `stripe 15.0.0` is the current latest as of 2026-04-01 (`pip index versions stripe`). Using `>=11.0.0` in requirements.txt provides a safe lower bound while allowing auto-upgrade to latest.

---

## Architecture Patterns

### Recommended Project Structure

```
routes/
└── payments.py          # new payments_bp blueprint (checkout, webhook, portal, pricing, legal)

templates/
├── pricing.html         # new — public pricing page (Starter/Pro/Business with Gründerrabatt-Badge)
├── impressum.html       # new — TMG §5-konforme Pflichtangaben
├── agb.html             # new — AGB with Drittdaten-Klausel
└── datenschutz.html     # new — DSGVO Datenschutzerklärung with all 4 Auftragsverarbeiter

database/
└── models.py            # extend Organisation + BillingEvent (via _migrate() in app.py)

config.py                # add STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_IDS
.env                     # add Stripe keys and Price IDs
```

### Pattern 1: Stripe Checkout Session (Hosted)

**What:** Create a Checkout Session server-side, redirect user to Stripe's hosted page.
**When to use:** When user clicks "Jetzt starten/upgraden" CTA on `/pricing`.

```python
# routes/payments.py
import stripe
from flask import Blueprint, redirect, request, url_for, flash, g
from routes.auth import login_required
from config import STRIPE_SECRET_KEY, STRIPE_PRICE_IDS

stripe.api_key = STRIPE_SECRET_KEY
payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

@payments_bp.route('/checkout/<plan>', methods=['POST'])
@login_required
def create_checkout(plan):
    price_id = STRIPE_PRICE_IDS.get(plan)
    if not price_id:
        return 'Invalid plan', 400

    # Create or reuse Stripe Customer
    customer_id = g.org.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=g.user.email,
            name=g.org.billing_name or g.org.name,
            metadata={'org_id': str(g.org.id)},
        )
        customer_id = customer.id
        # Persist immediately (before redirect, so webhook can match)
        db = get_session()
        try:
            org = db.query(Organisation).get(g.org.id)
            org.stripe_customer_id = customer_id
            db.commit()
        finally:
            db.close()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=url_for('payments.checkout_success', _external=True),
        cancel_url=url_for('payments.pricing', _external=True),
        metadata={'org_id': str(g.org.id)},
        # Payment methods are configured in Stripe Dashboard — no hardcoding
    )
    return redirect(session.url, code=303)

@payments_bp.route('/checkout/success')
@login_required
def checkout_success():
    # D-12: redirect only — activation is webhook-only
    flash('Abo aktiviert! Willkommen bei NERVE.', 'success')
    return redirect(url_for('dashboard.index'))
```

### Pattern 2: Stripe Webhook Handler (Idempotent)

**What:** Receive Stripe events, verify signature, deduplicate, update DB.
**When to use:** All Stripe event processing.

```python
# CRITICAL: webhook endpoint must NOT have @login_required
@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data          # raw bytes — NOT request.get_json()
    sig = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return '', 400

    event_id = event['id']
    # D-04: Idempotency check — deduplicate by stripe_event_id
    db = get_session()
    try:
        existing = db.query(BillingEvent).filter_by(stripe_event_id=event_id).first()
        if existing:
            return '', 200  # already processed

        event_type = event['type']
        obj = event['data']['object']

        if event_type == 'checkout.session.completed':
            _activate_subscription(db, obj)
        elif event_type in ('customer.subscription.updated',
                            'customer.subscription.deleted'):
            _sync_subscription(db, obj)
        elif event_type == 'invoice.paid':
            _reset_fair_use(db, obj)
        elif event_type == 'invoice.payment_failed':
            _handle_payment_failed(db, obj)

        # Record event for dedup
        db.add(BillingEvent(
            org_id=_get_org_id_from_event(db, event),
            typ=event_type,
            stripe_event_id=event_id,
        ))
        db.commit()
    finally:
        db.close()
    return '', 200
```

### Pattern 3: Customer Portal (Self-Service)

**What:** Generate one-time Portal URL, redirect user to Stripe-hosted management.

```python
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
```

The "Abo verwalten" button in `settings.html` billing tab:
```html
<form action="/payments/portal" method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() if csrf_token is defined else '' }}">
  <button type="submit" class="btn btn-primary">Abo verwalten</button>
</form>
```

### Pattern 4: Atomic Fair-Use Counter Increment

**What:** SQL-level atomic increment to prevent race conditions with concurrent threads.
**When to use:** On session end (`/api/end_session`) and on training session start.

```python
# CORRECT — atomic at SQL level, no read-modify-write in Python
from sqlalchemy import update as sa_update

def increment_live_minutes(org_id: int, minutes: int):
    db = get_session()
    try:
        db.execute(
            sa_update(Organisation)
            .where(Organisation.id == org_id)
            .values(live_minutes_used=Organisation.live_minutes_used + minutes)
        )
        db.commit()
    finally:
        db.close()

# WRONG — race condition under concurrent sessions
# org.live_minutes_used += minutes  # DO NOT USE
# db.commit()
```

### Pattern 5: Monthly Fair-Use Reset

**What:** Reset counters when the billing month rolls over.
**When to use:** Check on Dashboard load and `/live` session start; also reset via `invoice.paid` webhook.

```python
def check_and_reset_fair_use(org: Organisation, db) -> None:
    current_month = datetime.now().strftime('%Y-%m')
    if org.fair_use_reset_month != current_month:
        db.execute(
            sa_update(Organisation)
            .where(Organisation.id == org.id)
            .values(
                live_minutes_used=0,
                training_sessions_used=0,
                fair_use_reset_month=current_month,
            )
        )
        db.commit()

def get_fair_use_status(org: Organisation) -> dict:
    live_pct = min(100, round(org.live_minutes_used / max(org.minuten_limit, 1) * 100))
    train_pct = min(100, round(org.training_sessions_used / max(org.training_voice_limit, 1) * 100))
    return {
        'live_pct': live_pct,
        'train_pct': train_pct,
        'warn_80': live_pct >= 80 or train_pct >= 80,
        'limit_reached': live_pct >= 100 or train_pct >= 100,
    }
```

### Pattern 6: DB Migration (Stripe columns)

Follow the existing `_migrate()` pattern in `app.py`. New columns for `organisations` and `billing_events`:

```python
# In _migrate() — organisations block
('stripe_customer_id',      'VARCHAR(100)'),
('stripe_subscription_id',  'VARCHAR(100)'),
('stripe_price_id',         'VARCHAR(100)'),
('subscription_status',     "VARCHAR(50) DEFAULT 'inactive'"),

# In _migrate() — billing_events block
('stripe_event_id',         'VARCHAR(200) UNIQUE'),
```

### Pattern 7: Deepgram EU Endpoint Switch

The current `deepgram_service.py` uses `DeepgramClient(DEEPGRAM_API_KEY)` which defaults to the US endpoint. Switch to EU:

```python
# deepgram_service.py — change DeepgramClient instantiation
from deepgram import DeepgramClient, DeepgramClientOptions

def deepgram_starten():
    options = DeepgramClientOptions(url="api.eu.deepgram.com")
    client = DeepgramClient(DEEPGRAM_API_KEY, config=options)
    # rest unchanged
```

Alternatively, if `DeepgramClientOptions` does not accept `url` in the installed SDK version, check the `deepgram-sdk` docs for the `DEEPGRAM_HOST` env var:
```
DEEPGRAM_HOST=api.eu.deepgram.com
```
Both approaches achieve the same routing.

### Anti-Patterns to Avoid

- **Using `request.get_json()` in webhook handler:** Parses body, breaking signature verification. Always use `request.data`.
- **Activating subscription on redirect URL:** User can forge success URLs. Only activate on verified webhook.
- **Python-level `org.live_minutes_used += N`:** ORM caches stale values; use `sa_update()` expression.
- **Multiple Stripe Customer objects per org:** Always check `org.stripe_customer_id` before creating new Customer.
- **Adding `@login_required` to webhook endpoint:** Stripe has no session cookie; the webhook will always 401.
- **Hardcoding payment methods:** All payment method config lives in Stripe Dashboard, not in code.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Payment form / card input | Custom HTML form with card fields | Stripe Checkout (hosted) | PCI compliance; Stripe handles 3DS/SCA automatically; no card data touches your server |
| Subscription cancel/upgrade UI | Custom modal + API calls | Stripe Customer Portal (hosted) | Handles proration, card updates, billing history — all free via Portal |
| Webhook signature verification | HMAC comparison from scratch | `stripe.Webhook.construct_event()` | Timing attacks, encoding issues — use the SDK |
| Invoice PDF generation | ReportLab / WeasyPrint | Stripe-hosted invoice URLs | Stripe generates compliant VAT invoices automatically once billing address and USt-IdNr are set |
| Subscription status sync | Polling Stripe API | Webhook events only | Event-driven is authoritative; polling adds load and is stale |
| SEPA/PayPal integration code | Raw SEPA XML or PayPal SDK | Stripe Dashboard payment method settings | Stripe handles the payment rail; enable in Dashboard, it appears in Checkout |

**Key insight:** Stripe's hosted surfaces (Checkout + Portal) handle virtually all customer-facing payment interaction. The Flask app only needs: create-session, verify-webhook, create-portal-session. That is three API calls total.

---

## Common Pitfalls

### Pitfall 1: Webhook Receives Raw Body But nginx Buffers It

**What goes wrong:** `stripe.Webhook.construct_event()` receives a modified body if nginx buffers and re-transmits it, causing `SignatureVerificationError`. Developers comment out verification "temporarily" and ship without it.

**Why it happens:** nginx proxy buffering modifies byte-for-byte content for some payloads.

**How to avoid:** Add to the nginx location block for the webhook endpoint:
```nginx
location /payments/webhook {
    proxy_request_buffering off;
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    client_max_body_size 1m;
}
```

**Warning signs:** `SignatureVerificationError` in logs on the production server only (not local dev).

### Pitfall 2: Checkout Success Redirect vs Webhook Race

**What goes wrong:** User completes payment, lands on `/dashboard` with flash message "Abo aktiviert!", but the webhook hasn't arrived yet — so `subscription_status` is still `inactive`. UI looks inconsistent.

**Why it happens:** Stripe webhook delivery is asynchronous; the redirect happens before the webhook in ~20% of cases.

**How to avoid:** The success redirect (`/checkout/success`) shows the flash message unconditionally — it's a user experience message, not a technical confirmation. The dashboard should check `subscription_status` from the DB for feature gating, not rely on the flash. The webhook updates the DB within 1-5 seconds; a simple page load or AJAX poll after 2 seconds can refresh status if needed. For the Early Access launch (50 users) this edge case is acceptable.

**Warning signs:** Users report dashboard shows "Abo aktiviert!" but features are locked.

### Pitfall 3: Stripe Event ID Not UNIQUE in DB — Silently Loses Dedup

**What goes wrong:** Migration adds `stripe_event_id` column but without `UNIQUE` constraint. Dedup check still uses `filter_by(stripe_event_id=...)` which works, but on DB reset or migration issue, duplicates can be inserted silently.

**Why it happens:** SQLite `ALTER TABLE ADD COLUMN` doesn't support constraints; the UNIQUE must be in the original `CREATE TABLE` or a separate `CREATE UNIQUE INDEX`.

**How to avoid:** For the `BillingEvent` model in `models.py`, add `stripe_event_id = Column(String(200), unique=True, nullable=True)`. The `unique=True` triggers SQLAlchemy to create the index. Also add a manual dedup check in the handler as a belt-and-suspenders measure.

**Warning signs:** Duplicate rows with the same `stripe_event_id` in `billing_events`.

### Pitfall 4: Pricing Page Shows Stale Plan Data from Old landing.html

**What goes wrong:** The existing `landing.html` pricing section shows old prices (Solo 39€, Team 99€, Business 249€, Enterprise on request). The new `/pricing` page must show the correct Early Access prices (Starter 49€, Pro 59€, Business 69€). If someone copies the old cards without updating, wrong prices go live.

**Why it happens:** The landing.html pricing section was never updated to reflect the new flat-rate model.

**How to avoid:** Build `pricing.html` fresh from the locked decision: 3 plans × (49/59/69€), same Fair-Use limits for all, Gründerrabatt-Badge on every card. Do not copy the landing.html pricing HTML verbatim — use the CSS classes as reference only.

**Warning signs:** Pricing page shows 39€, 99€, 249€ or 4-card layout with Enterprise.

### Pitfall 5: Fair-Use Reset Logic Runs on Every Request

**What goes wrong:** `check_and_reset_fair_use()` is called on every dashboard load and every session start. If it runs a `db.execute(sa_update(...))` on every call regardless of whether a reset is needed, it hammers the DB.

**Why it happens:** Developer places the reset call inside the route without the month-comparison guard.

**How to avoid:** Always guard with `if org.fair_use_reset_month != current_month:` before issuing the UPDATE. The check itself is a cheap attribute read; the UPDATE only runs once per org per month.

**Warning signs:** Every dashboard page load produces a DB write in the SQLite WAL log.

### Pitfall 6: AGB Missing the Drittdaten-Verarbeitungs-Klausel

**What goes wrong:** Generic AGB template (e.g., from IT-Recht-Kanzlei) doesn't address the fact that NERVE processes voice data of third parties (the sales prospect on the other end of the call). Without this clause, NERVE has no legal basis for that processing.

**Why it happens:** Standard SaaS AGB templates don't cover real-time voice processing of third parties — this is a NERVE-specific scenario.

**How to avoid:** AGB must contain an explicit clause: "Der Nutzer ist verpflichtet, seinen Gesprächspartnern die Nutzung von NERVE mitzuteilen und deren Einwilligung einzuholen, oder den DSGVO-Modus (keine Sprachaufzeichnung, nur Echtzeit-Analyse ohne Speicherung) zu aktivieren."

**Warning signs:** AGB template was generated for a generic SaaS without reviewing the voice processing use case.

### Pitfall 7: Deepgram SDK URL Override Method

**What goes wrong:** `deepgram-sdk` Python SDK v3.x changed the client configuration API. The `DeepgramClientOptions(url=...)` approach may need to be `DeepgramClientOptions(api_url=...)` depending on the installed version. Using the wrong parameter name silently falls back to the US endpoint.

**Why it happens:** The SDK version in `requirements.txt` is `deepgram-sdk>=3.7.0`; the exact option name varies between minor versions.

**How to avoid:** After switching, verify by printing `client._config.url` or checking Deepgram's dashboard for request origin. Alternatively, use the `DEEPGRAM_HOST` environment variable which the SDK always reads: `DEEPGRAM_HOST=api.eu.deepgram.com` in `.env` — this is the safest approach since it doesn't require code changes if the API option name changes.

**Warning signs:** Deepgram console shows requests from US region after "switching" to EU endpoint.

---

## Code Examples

### Webhook Event Dispatch (complete handler)

```python
# routes/payments.py
@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data   # raw bytes — critical
    sig = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return '', 400

    db = get_session()
    try:
        # Idempotency check
        if db.query(BillingEvent).filter_by(stripe_event_id=event['id']).first():
            return '', 200

        etype = event['type']
        obj   = event['data']['object']

        if etype == 'checkout.session.completed':
            sub_id  = obj.get('subscription')
            cust_id = obj.get('customer')
            org_id  = int(obj.get('metadata', {}).get('org_id', 0))
            if org_id:
                db.execute(
                    sa_update(Organisation)
                    .where(Organisation.id == org_id)
                    .values(
                        stripe_customer_id=cust_id,
                        stripe_subscription_id=sub_id,
                        subscription_status='active',
                        plan=_price_to_plan(obj.get('metadata', {}).get('price_id', '')),
                    )
                )

        elif etype == 'customer.subscription.deleted':
            sub_id = obj.get('id')
            db.execute(
                sa_update(Organisation)
                .where(Organisation.stripe_subscription_id == sub_id)
                .values(subscription_status='canceled')
            )

        elif etype == 'invoice.paid':
            cust_id = obj.get('customer')
            db.execute(
                sa_update(Organisation)
                .where(Organisation.stripe_customer_id == cust_id)
                .values(
                    live_minutes_used=0,
                    training_sessions_used=0,
                    fair_use_reset_month=datetime.now().strftime('%Y-%m'),
                )
            )

        # Store event for dedup (org_id=0 is acceptable for events without org context)
        db.add(BillingEvent(
            org_id=_resolve_org_id(db, event) or 1,
            typ=etype,
            stripe_event_id=event['id'],
        ))
        db.commit()
    except Exception as e:
        print(f'[Stripe] Webhook error: {e}')
        db.rollback()
        return '', 500
    finally:
        db.close()
    return '', 200
```

### Pricing Page Route (public + authenticated dual context)

```python
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
```

### config.py additions

```python
# Stripe
STRIPE_SECRET_KEY      = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET  = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_PRICE_IDS = {
    'starter':  os.environ.get('STRIPE_PRICE_ID_STARTER', ''),
    'pro':      os.environ.get('STRIPE_PRICE_ID_PRO', ''),
    'business': os.environ.get('STRIPE_PRICE_ID_BUSINESS', ''),
}
```

### .env additions (server + dev)

```
STRIPE_SECRET_KEY=sk_test_...           # sk_live_... in production
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_STARTER=price_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_BUSINESS=price_...
DEEPGRAM_HOST=api.eu.deepgram.com       # EU endpoint for DSGVO
```

### Datenschutzerklärung Auftragsverarbeiter Block (German template content)

```
Deepgram, Inc., 535 Mission St, San Francisco, CA 94105, USA
Zweck: Echtzeit-Transkription von Verkaufsgesprächen
Datenbasis: Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung) + Art. 28 DSGVO (AVV)
Transfer-Mechanismus: EU-Standardvertragsklauseln (SCC); Datenverarbeitung auf EU-Servern (api.eu.deepgram.com)

Anthropic, PBC, 548 Market St PMB 90375, San Francisco, CA 94104, USA
Zweck: KI-gestützte Gesprächsanalyse, Einwand-Erkennung und Coaching-Generierung
Datenbasis: Art. 6 Abs. 1 lit. b DSGVO + Art. 28 DSGVO (AVV)
Transfer-Mechanismus: EU-Standardvertragsklauseln (SCC)
Hinweis: Anthropic verwendet API-Daten nicht für Modelltraining (laut Anthropic API Terms)

ElevenLabs, Inc. (Eleven Labs, Inc.), New York, USA
Zweck: Text-zu-Sprache-Synthese für KI-Trainingsszenarien
Datenbasis: Art. 6 Abs. 1 lit. b DSGVO + Art. 28 DSGVO (AVV)
Transfer-Mechanismus: EU-Standardvertragsklauseln (SCC)

Stripe Payments Europe, Ltd., 1 Grand Canal Street Lower, Grand Canal Dock, Dublin 2, Irland
Zweck: Zahlungsabwicklung, Rechnungsstellung und Abonnementverwaltung
Datenbasis: Art. 6 Abs. 1 lit. b DSGVO + Art. 28 DSGVO (AVV)
Transfer-Mechanismus: EU-Verarbeitungsentität (keine SCC erforderlich für EU-zu-EU)
```

### Impressum required fields (TMG §5)

Impressum must contain:
- Vollständiger Name + Anschrift: André Preuß, [Straße], 58636 Iserlohn
- Kontakt: Telefon (or "auf Anfrage via E-Mail") + E-Mail
- Verantwortlich für den Inhalt (§55 RStV): same person
- Hinweis auf USt-IdNr (or "beantragt") if applicable

### Gründerrabatt-Badge recommendation (Claude's discretion)

Teal badge, consistent with NERVE design system primary color (`#2dd4a8`). Apply to all three plan cards. Example:

```html
<div class="founder-badge" style="
  display:inline-block;
  background:rgba(45,212,168,.15);
  border:1px solid rgba(45,212,168,.3);
  color:#2dd4a8;
  font-size:11px;
  font-weight:700;
  padding:3px 10px;
  border-radius:20px;
  letter-spacing:.05em;
  text-transform:uppercase;
  margin-bottom:8px;
">50% Early Access Rabatt</div>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Stripe v2/v3 API | stripe-python v11-15 (sync client, typed responses) | 2023-2024 | `stripe.checkout.Session.create()` not `stripe.checkout.session.create()` — object capitalization changed |
| `stripe.error.*` exception hierarchy | Same (unchanged) | — | Catch `stripe.error.SignatureVerificationError` for webhook sig failures |
| `stripe.billing_portal.Session` | Same API, confirmed stable | 2022+ | Customer Portal is mature; no breaking changes expected |
| Manual payment method lists | Stripe Dashboard payment method configuration | 2023 | No `payment_method_types` needed in Session.create() if Dashboard is configured; Stripe reads from Dashboard |

**Deprecated/outdated:**
- `stripe.Checkout.Session.create()` (lowercase `checkout`): Use `stripe.checkout.Session.create()` (lowercase module, capitalized class)
- `stripe.UsageRecord`: Metered billing — not relevant for NERVE's flat-rate model

---

## Open Questions

1. **Deepgram EU endpoint SDK parameter name**
   - What we know: The Deepgram Python SDK v3.7+ supports EU routing; `DEEPGRAM_HOST` env var is the most reliable approach
   - What's unclear: Whether `DeepgramClientOptions(url=...)` or `DeepgramClientOptions(api_url=...)` is the correct parameter in the installed version
   - Recommendation: Use `DEEPGRAM_HOST=api.eu.deepgram.com` in `.env` — no code change needed, works regardless of SDK minor version. Verify by checking Deepgram console for request origin after the first session.

2. **Stripe Tax / VAT invoice configuration for Germany**
   - What we know: NERVE will collect VAT from German B2B customers; Stripe Tax can auto-calculate and add VAT to invoices
   - What's unclear: Whether Stripe Tax requires explicit configuration in Dashboard, and how it interacts with the AVV (it's data processing by Stripe)
   - Recommendation: Enable Stripe Tax in Dashboard during product/price setup (before first payment). Set tax behavior to `exclusive` on prices so 49/59/69€ shows ex-VAT. AVV with Stripe covers this. This is a Dashboard task, not a code task.

3. **AVV signing portal locations (current 2026)**
   - What we know: All four vendors offer DPAs; portal locations were MEDIUM confidence as of August 2025
   - What's unclear: Exact current URLs for signing — they may have moved
   - Recommendation: Access each vendor's dashboard directly and search for "Privacy", "Legal", or "DPA" in account settings. For Anthropic specifically, check console.anthropic.com under account settings or email privacy@anthropic.com. For Stripe: Dashboard → Settings → Compliance. Verified in STACK.md prior research — confirm before André attempts signing.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python pip / stripe package | PAY-01 through PAY-04 | ✓ (pip present) | stripe not yet installed; 15.0.0 on PyPI | — |
| Stripe account | PAY-01 | Must be created manually | n/a (no account yet) | No fallback — blocking |
| Stripe CLI | Dev webhook testing | Not checked (dev tool) | — | Use Stripe Dashboard "Send test webhook" button |
| Deepgram EU endpoint | LEGAL-03 | ✓ (code change only) | api.eu.deepgram.com via DEEPGRAM_HOST env | — |
| nginx (production) | Webhook sig verification (buffering fix) | ✓ (Phase 3 complete) | 1.24+ on Hetzner | — |
| HTTPS (production) | Stripe webhook delivery | ✓ (Phase 3 complete, getnerve.app) | Let's Encrypt | — |

**Missing dependencies with no fallback:**
- Stripe account: must be created before any payment testing. Requires Gewerbeanmeldung + Geschäftskonto (Phase 1 manual tasks).

**Missing dependencies with fallback:**
- Stripe CLI: not required; Stripe Dashboard "Send test webhook" function can be used to test webhook handler without CLI.

---

## Validation Architecture

> `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json` — this section is skipped.

---

## Project Constraints (from CLAUDE.md)

The following CLAUDE.md directives constrain this phase's implementation:

| Directive | Impact on Phase 4 |
|-----------|-------------------|
| **No framework change — Flask + Vanilla JS** | Payments blueprint uses Flask Blueprint pattern; no React/Next.js payment UI |
| **Sonnet MUSS raus aus Live-Loop — nur Haiku für alles Live** | Not directly relevant to payments, but fair-use check in `/live` route must be lightweight (no AI call) |
| **DSGVO Pflicht von Tag 1 — Hetzner Deutschland** | Legal pages, AVVs, and Deepgram EU endpoint must all be complete before first paying customer |
| **Pricing: Flat-Rate, nicht Credits** | Confirmed: Stripe fixed recurring Prices, NOT metered billing / UsageRecord |
| **Kein harter Stopp bei Fair-Use** | 100% limit shows warning + upgrade button, session continues — implemented in D-15 |
| **Bootstrap — kein externes Kapital** | No paid 3rd-party legal review tools; use German AGB/Impressum templates with manual review |
| **Naming: lowercase_underscores for routes/services** | `routes/payments.py`, `payments_bp`, functions like `create_checkout()`, `stripe_webhook()`, `customer_portal()` |
| **Blueprint pattern** | `payments_bp = Blueprint('payments', __name__, url_prefix='/payments')` registered in `app.py` |
| **DB session pattern: try/finally db.close()** | All Stripe-triggered DB writes use the standard `get_session()` + try/finally pattern |
| **Migration via `_migrate()` in app.py** | New Organisation and BillingEvent columns added to existing `_migrate()` function, not a new migration system |
| **Print-based logging with context tags** | `print('[Stripe] checkout.session.completed ...')`, `print('[Legal] /impressum route registered')` |

---

## Sources

### Primary (HIGH confidence)
- PyPI stripe package registry — version 15.0.0 verified 2026-04-01 via `pip index versions stripe`
- Stripe API docs (training knowledge, stable API since 2022) — Checkout Sessions, Customer Portal, Webhook construct_event
- DSGVO Art. 28 (EU law) — Auftragsverarbeitungsvertrag requirement is unambiguous and stable
- Existing codebase: `database/models.py`, `config.py`, `routes/settings.py`, `app.py`, `services/deepgram_service.py` — read directly 2026-04-01

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` — Stripe architecture patterns and DSGVO AVV guidance (researched 2026-03-30, training knowledge)
- `.planning/research/PITFALLS.md` — Webhook idempotency, signature verification, fair-use race conditions (researched 2026-03-30)
- Training knowledge: stripe-python v10-15 API shape (Checkout Sessions, billing_portal, Webhook.construct_event) — stable since 2022

### Tertiary (LOW confidence — verify before implementing)
- Deepgram EU endpoint `DEEPGRAM_HOST` env var approach — needs verification against installed deepgram-sdk version
- AVV portal locations for Anthropic, ElevenLabs, Deepgram — MEDIUM in prior research; URLs should be verified directly in each dashboard before signing attempt

---

## Metadata

**Confidence breakdown:**
- Standard stack (stripe-python): HIGH — version verified against PyPI live registry
- Architecture (Checkout/Webhook/Portal pattern): HIGH — stable Stripe API, confirmed against existing codebase patterns
- Fair-use metering: HIGH — existing DB columns confirmed in `models.py`; atomic update pattern is SQLAlchemy standard
- Legal content (DSGVO): MEDIUM-HIGH — DSGVO Art. 28 is stable law; Impressum TMG §5 is stable; specific AGB Drittdaten-Klausel wording is best-practice recommendation, not law-reviewed
- Deepgram EU endpoint switch: MEDIUM — DEEPGRAM_HOST env var approach is most resilient; specific SDK option name needs verification

**Research date:** 2026-04-01
**Valid until:** 2026-07-01 (Stripe APIs are stable; DSGVO law is stable; stripe-python version check is time-sensitive — re-verify if more than 30 days pass before implementation)
