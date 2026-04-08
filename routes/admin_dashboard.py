"""Phase 04.7.2 — Founder Cost Dashboard Blueprint.

Alle Routes gated mit @login_required + @superadmin_required.
6 Tabs: uebersicht, einnahmen, ausgaben, kunden, eur, export.
"""
from __future__ import annotations
import re
import calendar
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, abort
from routes.auth import login_required
from services.auth_decorators import superadmin_required
from database.db import get_session

admin_dashboard_bp = Blueprint(
    'admin_dashboard', __name__,
    url_prefix='/admin/dashboard',
    template_folder='../templates/admin',
)

VALID_TABS = {'uebersicht', 'einnahmen', 'ausgaben', 'kunden', 'eur', 'export'}
PERIOD_RE = re.compile(r'^\d{4}-\d{2}$')


def _parse_period(period_str):
    """Parst 'YYYY-MM' in (start_date, end_date_exclusive).
    Fallback: aktueller Monat. Bei ungueltigem Format: abort(400)."""
    if period_str and not PERIOD_RE.match(period_str):
        abort(400, description="Invalid period format, expected YYYY-MM")
    if not period_str:
        today = date.today()
        period_str = f"{today.year}-{today.month:02d}"
    year, month = map(int, period_str.split('-'))
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _mrr_from_active_orgs(db):
    """MRR-Sum: Summe plan_preis aller active Organisationen.
    Fallback auf PLANS[plan]['preis'] wenn plan_preis nicht gesetzt."""
    from database.models import Organisation
    from config import PLANS
    orgs = db.query(Organisation).filter(
        Organisation.subscription_status == 'active'
    ).all()
    total = 0.0
    for o in orgs:
        price = getattr(o, 'plan_preis', None)
        if price:
            total += float(price)
        else:
            pk = getattr(o, 'plan', None) or 'starter'
            total += float(PLANS.get(pk, {}).get('preis', 0))
    return total


@admin_dashboard_bp.route('/')
@login_required
@superadmin_required
def index():
    tab = request.args.get('tab', 'uebersicht')
    if tab not in VALID_TABS:
        tab = 'uebersicht'
    period = request.args.get('period')
    _parse_period(period)  # validates, aborts 400 on bad format
    return render_template(
        'admin/dashboard.html',
        active_tab=tab,
        period=period or date.today().strftime('%Y-%m'),
    )


# ── Tab Uebersicht: KPI Endpoint ─────────────────────────────────────

@admin_dashboard_bp.route('/api/overview')
@login_required
@superadmin_required
def api_overview():
    from database.models import (
        RevenueLog, ApiCostLog, FixedCost, Organisation, User
    )
    from sqlalchemy import func

    period = request.args.get('period')
    start, end = _parse_period(period)

    db = get_session()
    try:
        # MRR aus aktiven Subscriptions (forward-looking)
        mrr_eur = _mrr_from_active_orgs(db)

        # Einnahmen in Periode (backward-looking, netto)
        revenue_q = (db.query(func.sum(RevenueLog.netto_cents))
                     .filter(RevenueLog.paid_at >= start,
                             RevenueLog.paid_at < end))
        revenue_eur = float((revenue_q.scalar() or 0) / 100.0)

        # API-Kosten in Periode
        api_costs_q = (db.query(func.sum(ApiCostLog.cost_eur))
                       .filter(ApiCostLog.created_at >= start,
                               ApiCostLog.created_at < end))
        api_costs_eur = float(api_costs_q.scalar() or 0)

        # Fixkosten (cycle='monthly', active)
        fc_monthly = (db.query(func.sum(FixedCost.amount_eur))
                      .filter(FixedCost.cycle == 'monthly',
                              FixedCost.active == True)  # noqa: E712
                      .scalar() or 0)
        total_costs = api_costs_eur + float(fc_monthly)

        # Aktive User (Org mit active-Subscription)
        active_users = (db.query(func.count(User.id))
                        .join(Organisation, Organisation.id == User.org_id)
                        .filter(Organisation.subscription_status == 'active')
                        .scalar() or 0)

        gewinn = revenue_eur - total_costs
        marge_pct = (gewinn / revenue_eur * 100.0) if revenue_eur > 0 else 0

        # 12-Monats-Serie rueckwaerts (ab 11 Monate vor start bis start inkl.)
        labels_12m = []
        mrr_12m = []
        costs_12m = []
        margin_12m = []

        cursor_year, cursor_month = start.year, start.month
        # 11 Monate zurueck
        for _ in range(11):
            cursor_month -= 1
            if cursor_month == 0:
                cursor_month = 12
                cursor_year -= 1

        for _ in range(12):
            m_start = date(cursor_year, cursor_month, 1)
            _last = calendar.monthrange(cursor_year, cursor_month)[1]
            m_end = date(cursor_year, cursor_month, _last) + timedelta(days=1)

            rev = float((db.query(func.sum(RevenueLog.netto_cents))
                         .filter(RevenueLog.paid_at >= m_start,
                                 RevenueLog.paid_at < m_end).scalar() or 0) / 100.0)
            api_c = float(db.query(func.sum(ApiCostLog.cost_eur))
                          .filter(ApiCostLog.created_at >= m_start,
                                  ApiCostLog.created_at < m_end).scalar() or 0)
            total_c = api_c + float(fc_monthly)
            labels_12m.append(f"{cursor_year}-{cursor_month:02d}")
            mrr_12m.append(round(rev, 2))
            costs_12m.append(round(total_c, 2))
            margin_12m.append(round((rev - total_c) / rev * 100, 1) if rev > 0 else 0)

            cursor_month += 1
            if cursor_month > 12:
                cursor_month = 1
                cursor_year += 1

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'kpis': {
                'mrr': f"{mrr_eur:,.2f} EUR".replace(',', '.'),
                'costs_mo': f"{total_costs:,.2f} EUR".replace(',', '.'),
                'marge': f"{marge_pct:,.1f} %".replace(',', '.'),
                'active_users': str(int(active_users)),
                'gewinn_mo': f"{gewinn:,.2f} EUR".replace(',', '.'),
            },
            'mrr_costs_12m': {
                'labels': labels_12m,
                'mrr': mrr_12m,
                'costs': costs_12m,
            },
            'margin_12m': {
                'labels': labels_12m,
                'values': margin_12m,
            },
        })
    finally:
        db.close()


# ── Tab Einnahmen ────────────────────────────────────────────────────

@admin_dashboard_bp.route('/einnahmen')
@login_required
@superadmin_required
def einnahmen_page():
    from database.models import RevenueLog
    from sqlalchemy import func

    period = request.args.get('period')
    start, end = _parse_period(period)

    db = get_session()
    try:
        # Summary by tax_treatment
        rows = (db.query(RevenueLog.tax_treatment,
                         func.sum(RevenueLog.netto_cents),
                         func.sum(RevenueLog.ust_cents),
                         func.sum(RevenueLog.brutto_cents),
                         func.count(RevenueLog.id))
                .filter(RevenueLog.paid_at >= start,
                        RevenueLog.paid_at < end)
                .group_by(RevenueLog.tax_treatment).all())
        summary = [{
            'treatment': r[0],
            'netto': round((r[1] or 0) / 100.0, 2),
            'ust': round((r[2] or 0) / 100.0, 2),
            'brutto': round((r[3] or 0) / 100.0, 2),
            'count': r[4],
        } for r in rows]

        # By plan
        plan_rows = (db.query(RevenueLog.plan_key,
                              func.count(RevenueLog.id),
                              func.sum(RevenueLog.netto_cents))
                     .filter(RevenueLog.paid_at >= start,
                             RevenueLog.paid_at < end)
                     .group_by(RevenueLog.plan_key).all())
        by_plan = [{
            'plan': (r[0] or '—'),
            'count': r[1],
            'netto': round((r[2] or 0) / 100.0, 2),
        } for r in plan_rows]

        # By country + tax_treatment
        country_rows = (db.query(RevenueLog.country, RevenueLog.tax_treatment,
                                 func.count(RevenueLog.id),
                                 func.sum(RevenueLog.netto_cents))
                        .filter(RevenueLog.paid_at >= start,
                                RevenueLog.paid_at < end)
                        .group_by(RevenueLog.country,
                                  RevenueLog.tax_treatment).all())
        by_country = [{
            'country': r[0] or '?',
            'treatment': r[1],
            'count': r[2],
            'netto': round((r[3] or 0) / 100.0, 2),
        } for r in country_rows]

        # Transactions (paginated)
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        per_page = 50
        txs = (db.query(RevenueLog)
               .filter(RevenueLog.paid_at >= start,
                       RevenueLog.paid_at < end)
               .order_by(RevenueLog.paid_at.desc())
               .offset((page - 1) * per_page).limit(per_page).all())
        transactions = [{
            'date': t.paid_at.strftime('%Y-%m-%d') if t.paid_at else '',
            'invoice_id': t.stripe_invoice_id,
            'country': t.country or '',
            'plan': t.plan_key or '',
            'netto': round((t.netto_cents or 0) / 100.0, 2),
            'ust': round((t.ust_cents or 0) / 100.0, 2),
            'brutto': round((t.brutto_cents or 0) / 100.0, 2),
            'treatment': t.tax_treatment,
        } for t in txs]

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'summary': summary,
            'by_plan': by_plan,
            'by_country': by_country,
            'transactions': transactions,
            'page': page,
        })
    finally:
        db.close()


# ── Tab Ausgaben ─────────────────────────────────────────────────────

# EÜR-Kategorie-Mapping (Stammdaten, hart-codiert)
EUR_CATEGORY_BY_PROVIDER = {
    'anthropic':  {'label': 'Anthropic Claude API',  'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'deepgram':   {'label': 'Deepgram Nova-2 STT',   'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'elevenlabs': {'label': 'ElevenLabs TTS',        'cat': 'Bezogene Fremdleistungen', 'eur_line': 26, 'skr03': '3100', 'vat_rc': True},
    'stripe':     {'label': 'Stripe Gebühren',       'cat': 'Nebenkosten Geldverkehr',  'eur_line': 57, 'skr03': '4970', 'vat_rc': False},
}


@admin_dashboard_bp.route('/ausgaben')
@login_required
@superadmin_required
def ausgaben_page():
    from database.models import ApiCostLog, ApiRate, FixedCost
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        by_provider_rows = (db.query(ApiCostLog.provider,
                                     func.sum(ApiCostLog.cost_eur))
                              .filter(ApiCostLog.created_at >= start,
                                      ApiCostLog.created_at < end)
                              .group_by(ApiCostLog.provider).all())
        by_provider = []
        api_total = 0.0
        for row in by_provider_rows:
            cat_info = EUR_CATEGORY_BY_PROVIDER.get(
                row[0],
                {'label': row[0], 'cat': 'Übrige', 'eur_line': 57, 'skr03': '', 'vat_rc': False},
            )
            val = float(row[1] or 0)
            api_total += val
            by_provider.append({**cat_info, 'provider': row[0], 'netto': round(val, 2)})

        fc_all = db.query(FixedCost).filter(FixedCost.active == True).all()  # noqa: E712
        fixed_costs_rows = []
        for fc in fc_all:
            amount = float(fc.amount_eur)
            if fc.cycle == 'monthly':
                period_cost = amount
            elif fc.cycle == 'yearly':
                period_cost = amount / 12.0
            elif fc.cycle == 'per_day':
                try:
                    home_days = int(request.args.get(f'days_{fc.id}', 0))
                except (TypeError, ValueError):
                    home_days = 0
                period_cost = amount * home_days
            else:
                period_cost = 0.0
            fixed_costs_rows.append({
                'id': fc.id, 'name': fc.name, 'amount_eur': amount,
                'cycle': fc.cycle, 'skr03': fc.skr03, 'eur_line': fc.eur_line,
                'period_cost': round(period_cost, 2),
            })
        fc_total = sum(r['period_cost'] for r in fixed_costs_rows)

        # 30-Tage-Serie (rückwärts ab end)
        daily = []
        cursor = end - timedelta(days=30)
        while cursor < end:
            next_day = cursor + timedelta(days=1)
            v = float(db.query(func.sum(ApiCostLog.cost_eur))
                        .filter(ApiCostLog.created_at >= cursor,
                                ApiCostLog.created_at < next_day).scalar() or 0)
            daily.append({'date': cursor.strftime('%Y-%m-%d'), 'cost': round(v, 2)})
            cursor = next_day

        rates = db.query(ApiRate).filter(ApiRate.active == True).all()  # noqa: E712
        now = datetime.utcnow()
        rates_out = []
        for r in rates:
            stale_days = (now - r.last_checked_at).days if r.last_checked_at else 999
            rates_out.append({
                'id': r.id, 'provider': r.provider, 'model': r.model,
                'unit_type': r.unit_type,
                'price': float(r.price_per_unit),
                'currency': r.currency,
                'last_checked': r.last_checked_at.strftime('%Y-%m-%d') if r.last_checked_at else '—',
                'stale_days': stale_days,
                'stale': stale_days > 30,
            })

        return jsonify({
            'period': start.strftime('%Y-%m'),
            'by_provider': by_provider,
            'api_total': round(api_total, 2),
            'fixed_costs': fixed_costs_rows,
            'fixed_total': round(fc_total, 2),
            'grand_total': round(api_total + fc_total, 2),
            'daily_30': daily,
            'api_rates': rates_out,
        })
    finally:
        db.close()


@admin_dashboard_bp.route('/api_rates/<int:rate_id>/mark_checked', methods=['POST'])
@login_required
@superadmin_required
def api_rate_mark_checked(rate_id):
    from database.models import ApiRate
    db = get_session()
    try:
        rate = db.query(ApiRate).get(rate_id)
        if not rate:
            abort(404)
        rate.last_checked_at = datetime.utcnow()
        db.commit()
        return jsonify({'ok': True, 'last_checked': rate.last_checked_at.isoformat()})
    finally:
        db.close()


@admin_dashboard_bp.route('/api_rates/<int:rate_id>/new_price', methods=['POST'])
@login_required
@superadmin_required
def api_rate_new_price(rate_id):
    """Deaktiviert alten Preis, legt neuen aktiven Preis an, schreibt PriceChangeLog."""
    from database.models import ApiRate, ApiCostLog, PriceChangeLog
    from sqlalchemy import func
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        old = db.query(ApiRate).get(rate_id)
        if not old:
            abort(404)
        try:
            new_price = Decimal(request.form.get('new_price', '').replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="new_price invalid")
        note = (request.form.get('note', '') or '')[:500]
        old.active = False
        db.flush()
        new = ApiRate(
            provider=old.provider, model=old.model, unit_type=old.unit_type,
            price_per_unit=new_price, currency=old.currency, active=True,
            last_checked_at=datetime.utcnow(),
            source_url=old.source_url,
        )
        db.add(new)
        db.flush()
        since = datetime.utcnow() - timedelta(days=30)
        avg_units = float(db.query(func.sum(ApiCostLog.units))
                            .filter(ApiCostLog.provider == old.provider,
                                    ApiCostLog.model == old.model,
                                    ApiCostLog.unit_type == old.unit_type,
                                    ApiCostLog.created_at >= since).scalar() or 0)
        delta = float(new_price) - float(old.price_per_unit)
        try:
            from services.exchange_rates import get_current_rate
            fx = float(get_current_rate('USD_EUR')) if old.currency == 'USD' else 1.0
        except Exception:
            fx = 0.92 if old.currency == 'USD' else 1.0
        impact = round(avg_units * delta * fx, 2)
        db.add(PriceChangeLog(
            api_rate_id=new.id, old_rate=old.price_per_unit,
            new_rate=new_price, currency=old.currency,
            impact_eur_per_month=Decimal(str(impact)), note=note,
        ))
        db.commit()
        return jsonify({'ok': True, 'impact_eur_per_month': impact})
    finally:
        db.close()


@admin_dashboard_bp.route('/fixed_costs', methods=['POST'])
@login_required
@superadmin_required
def fixed_cost_create():
    from database.models import FixedCost
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        name = (request.form.get('name', '') or '').strip()[:128]
        cycle = request.form.get('cycle', 'monthly')
        if cycle not in ('monthly', 'yearly', 'per_day'):
            abort(400, description="invalid cycle")
        try:
            amount = Decimal(request.form.get('amount_eur', '0').replace(',', '.'))
            vat = Decimal(request.form.get('vat_rate', '19').replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="amount/vat invalid")
        if not name or float(amount) < 0:
            abort(400, description="name and non-negative amount required")
        try:
            eur_line = int(request.form.get('eur_line') or 57)
        except (TypeError, ValueError):
            eur_line = 57
        fc = FixedCost(
            name=name, amount_eur=amount, vat_rate=vat,
            cycle=cycle,
            skr03=(request.form.get('skr03', '') or '')[:8] or None,
            eur_line=eur_line,
            active=True,
        )
        db.add(fc)
        db.commit()
        return jsonify({'ok': True, 'id': fc.id})
    finally:
        db.close()


@admin_dashboard_bp.route('/fixed_costs/<int:fc_id>', methods=['POST'])
@login_required
@superadmin_required
def fixed_cost_update(fc_id):
    from database.models import FixedCost
    from decimal import Decimal, InvalidOperation
    db = get_session()
    try:
        fc = db.query(FixedCost).get(fc_id)
        if not fc:
            abort(404)
        action = request.form.get('_action', 'update')
        if action == 'delete':
            db.delete(fc)
            db.commit()
            return jsonify({'ok': True, 'deleted': True})
        if action == 'toggle':
            fc.active = not bool(fc.active)
            db.commit()
            return jsonify({'ok': True, 'active': fc.active})
        # update
        name = request.form.get('name')
        if name is not None:
            fc.name = name[:128]
        skr = request.form.get('skr03')
        if skr is not None:
            fc.skr03 = skr[:8] or None
        try:
            if 'amount_eur' in request.form:
                fc.amount_eur = Decimal(request.form['amount_eur'].replace(',', '.'))
            if 'vat_rate' in request.form:
                fc.vat_rate = Decimal(request.form['vat_rate'].replace(',', '.'))
        except (InvalidOperation, AttributeError):
            abort(400, description="amount/vat invalid")
        if 'cycle' in request.form:
            c = request.form['cycle']
            if c in ('monthly', 'yearly', 'per_day'):
                fc.cycle = c
        if 'eur_line' in request.form:
            try:
                fc.eur_line = int(request.form['eur_line'])
            except (TypeError, ValueError):
                pass
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


# ── Tab Kunden: Profitabilität (Org + User-Drilldown) ────────────────

def classify_margin(margin_pct: float) -> str:
    if margin_pct > 70:
        return 'healthy'
    if margin_pct >= 50:
        return 'warn'
    return 'critical'


def compute_org_profitability(db, org_id: int, start, end) -> dict:
    from database.models import RevenueLog, ApiCostLog
    from sqlalchemy import func
    revenue_cents = db.query(func.sum(RevenueLog.netto_cents)).filter(
        RevenueLog.org_id == org_id,
        RevenueLog.paid_at >= start, RevenueLog.paid_at < end).scalar() or 0
    revenue = float(revenue_cents) / 100.0
    api_cost = float(db.query(func.sum(ApiCostLog.cost_eur)).filter(
        ApiCostLog.org_id == org_id,
        ApiCostLog.created_at >= start, ApiCostLog.created_at < end).scalar() or 0)
    margin_pct = ((revenue - api_cost) / revenue * 100.0) if revenue > 0 else 0.0
    return {
        'revenue_eur': round(revenue, 2),
        'api_cost_eur': round(api_cost, 2),
        'margin_pct': round(margin_pct, 1),
        'status': classify_margin(margin_pct),
    }


@admin_dashboard_bp.route('/kunden')
@login_required
@superadmin_required
def kunden_page():
    from database.models import Organisation, User
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        orgs = db.query(Organisation).filter(
            Organisation.subscription_status == 'active').all()
        out = []
        for org in orgs:
            prof = compute_org_profitability(db, org.id, start, end)
            user_count = db.query(func.count(User.id)).filter(User.org_id == org.id).scalar() or 0
            out.append({
                'org_id': org.id,
                'name': org.name,
                'plan': getattr(org, 'plan', '') or '',
                'user_count': int(user_count),
                **prof,
            })
        out.sort(key=lambda r: r['margin_pct'])
        summary = {
            'healthy':  sum(1 for r in out if r['status'] == 'healthy'),
            'warn':     sum(1 for r in out if r['status'] == 'warn'),
            'critical': sum(1 for r in out if r['status'] == 'critical'),
        }
        return jsonify({'period': start.strftime('%Y-%m'), 'orgs': out, 'summary': summary})
    finally:
        db.close()


@admin_dashboard_bp.route('/kunden/<int:org_id>/users')
@login_required
@superadmin_required
def kunden_drilldown(org_id):
    from database.models import User, ApiCostLog
    from sqlalchemy import func
    period = request.args.get('period')
    start, end = _parse_period(period)
    db = get_session()
    try:
        users = db.query(User).filter(User.org_id == org_id).all()
        result = []
        for u in users:
            by_provider_rows = db.query(
                ApiCostLog.provider, func.sum(ApiCostLog.cost_eur)
            ).filter(
                ApiCostLog.user_id == u.id,
                ApiCostLog.created_at >= start, ApiCostLog.created_at < end,
            ).group_by(ApiCostLog.provider).all()
            breakdown = {p: round(float(c or 0), 2) for p, c in by_provider_rows}
            total = sum(breakdown.values())
            weekly = []
            cur = end - timedelta(days=28)
            while cur < end:
                nxt = cur + timedelta(days=7)
                v = float(db.query(func.sum(ApiCostLog.cost_eur)).filter(
                    ApiCostLog.user_id == u.id,
                    ApiCostLog.created_at >= cur,
                    ApiCostLog.created_at < nxt).scalar() or 0)
                weekly.append({'week_start': cur.strftime('%Y-%m-%d'), 'cost': round(v, 2)})
                cur = nxt
            result.append({
                'user_id': u.id, 'email': u.email,
                'total_cost_eur': round(total, 2),
                'by_provider': breakdown,
                'weekly_trend': weekly,
            })
        result.sort(key=lambda r: r['total_cost_eur'], reverse=True)
        return jsonify({'org_id': org_id, 'users': result})
    finally:
        db.close()


# ── Tab EÜR ───────────────────────────────────────────────────────

@admin_dashboard_bp.route('/eur')
@login_required
@superadmin_required
def eur_data():
    period = request.args.get('period')
    start, end = _parse_period(period)
    try:
        home_days = int(request.args.get('home_days', 0))
    except (TypeError, ValueError):
        home_days = 0
    from services.eur_calculator import compute_eur
    db = get_session()
    try:
        data = compute_eur(start, end, db, home_days=home_days)
        return jsonify(data)
    finally:
        db.close()
