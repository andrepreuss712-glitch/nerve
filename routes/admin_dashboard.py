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
