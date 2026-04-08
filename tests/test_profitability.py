"""Phase 04.7.2-05 — Profitability calc tests."""
from datetime import date, datetime
from decimal import Decimal
from routes.admin_dashboard import classify_margin, compute_org_profitability
from database.models import Organisation, RevenueLog, ApiCostLog


def _mk_org(db, name='TC'):
    o = Organisation(name=name, plan='solo', subscription_status='active')
    db.add(o); db.flush()
    return o


def test_classify_margin_thresholds():
    assert classify_margin(95) == 'healthy'
    assert classify_margin(70.1) == 'healthy'
    assert classify_margin(70) == 'warn'
    assert classify_margin(50) == 'warn'
    assert classify_margin(49.9) == 'critical'
    assert classify_margin(0) == 'critical'


def test_margin_calc_healthy(db_session):
    o = _mk_org(db_session, 'Healthy')
    db_session.add(RevenueLog(
        stripe_invoice_id='in_h1', org_id=o.id,
        paid_at=datetime(2026, 3, 15), netto_cents=10000, ust_cents=1900,
        brutto_cents=11900, country='DE', tax_treatment='DE_19',
    ))
    db_session.add(ApiCostLog(
        provider='anthropic', model='haiku-4-5',
        org_id=o.id, units=Decimal('1'), unit_type='per_1k_input_tokens',
        rate_applied=Decimal('0.00025'), rate_currency='USD',
        fx_rate_applied=Decimal('0.92'), cost_eur=Decimal('20.00'),
        created_at=datetime(2026, 3, 15),
    ))
    db_session.commit()
    p = compute_org_profitability(db_session, o.id, date(2026, 3, 1), date(2026, 4, 1))
    assert p['revenue_eur'] == 100.0
    assert p['api_cost_eur'] == 20.0
    assert p['margin_pct'] == 80.0
    assert p['status'] == 'healthy'


def test_margin_calc_warn(db_session):
    o = _mk_org(db_session, 'Warn')
    db_session.add(RevenueLog(
        stripe_invoice_id='in_w1', org_id=o.id,
        paid_at=datetime(2026, 3, 15), netto_cents=10000, ust_cents=0,
        brutto_cents=10000, country='DE', tax_treatment='DE_19',
    ))
    db_session.add(ApiCostLog(
        provider='anthropic', model='haiku-4-5', org_id=o.id,
        units=Decimal('1'), unit_type='per_1k_input_tokens',
        rate_applied=Decimal('1'), rate_currency='EUR',
        fx_rate_applied=Decimal('1'), cost_eur=Decimal('40.00'),
        created_at=datetime(2026, 3, 15),
    ))
    db_session.commit()
    p = compute_org_profitability(db_session, o.id, date(2026, 3, 1), date(2026, 4, 1))
    assert p['margin_pct'] == 60.0
    assert p['status'] == 'warn'


def test_margin_calc_critical(db_session):
    o = _mk_org(db_session, 'Crit')
    db_session.add(RevenueLog(
        stripe_invoice_id='in_c1', org_id=o.id,
        paid_at=datetime(2026, 3, 15), netto_cents=10000, ust_cents=0,
        brutto_cents=10000, country='DE', tax_treatment='DE_19',
    ))
    db_session.add(ApiCostLog(
        provider='anthropic', model='haiku-4-5', org_id=o.id,
        units=Decimal('1'), unit_type='per_1k_input_tokens',
        rate_applied=Decimal('1'), rate_currency='EUR',
        fx_rate_applied=Decimal('1'), cost_eur=Decimal('60.00'),
        created_at=datetime(2026, 3, 15),
    ))
    db_session.commit()
    p = compute_org_profitability(db_session, o.id, date(2026, 3, 1), date(2026, 4, 1))
    assert p['margin_pct'] == 40.0
    assert p['status'] == 'critical'


def test_margin_calc_no_revenue(db_session):
    o = _mk_org(db_session, 'Empty')
    p = compute_org_profitability(db_session, o.id, date(2026, 3, 1), date(2026, 4, 1))
    assert p['revenue_eur'] == 0
    assert p['margin_pct'] == 0
    assert p['status'] == 'critical'
