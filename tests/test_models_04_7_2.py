"""Phase 04.7.2 — Schema-Smoke-Tests fuer die 6 neuen Models."""
import pytest
from database.models import ApiCostLog, ApiRate, FixedCost, RevenueLog, ExchangeRate, PriceChangeLog


def test_all_six_tables_have_tablenames():
    expected = {
        ApiCostLog:     'api_cost_log',
        ApiRate:        'api_rates',
        FixedCost:      'fixed_costs',
        RevenueLog:     'revenue_log',
        ExchangeRate:   'exchange_rates',
        PriceChangeLog: 'price_change_log',
    }
    for cls, name in expected.items():
        assert cls.__tablename__ == name


def test_api_cost_log_required_columns():
    cols = {c.name for c in ApiCostLog.__table__.columns}
    for required in ('provider', 'model', 'units', 'unit_type', 'rate_applied',
                     'fx_rate_applied', 'cost_eur', 'created_at'):
        assert required in cols, f"ApiCostLog missing column: {required}"


def test_revenue_log_unique_stripe_invoice_id():
    col = RevenueLog.__table__.columns['stripe_invoice_id']
    assert col.unique is True


def test_fixed_cost_cycle_accepts_three_values():
    cols = {c.name for c in FixedCost.__table__.columns}
    assert 'cycle' in cols
    assert 'amount_eur' in cols
    assert 'eur_line' in cols


def test_api_rate_has_last_checked_at():
    cols = {c.name for c in ApiRate.__table__.columns}
    assert 'last_checked_at' in cols


def test_exchange_rate_uniqueness_constraint():
    constraints = [c.name for c in ExchangeRate.__table__.constraints if hasattr(c, 'name') and c.name]
    assert any('exchange_rate' in (n or '') for n in constraints), f"Expected unique constraint, got: {constraints}"


def test_insert_roundtrip_fixed_cost(db_session):
    """Smoke-Roundtrip: INSERT + SELECT."""
    from database.models import FixedCost
    fc = FixedCost(name='TEST', amount_eur=9.99, vat_rate=19.00, cycle='monthly',
                   skr03='4806', eur_line=57, active=True)
    db_session.add(fc)
    db_session.commit()
    fetched = db_session.query(FixedCost).filter_by(name='TEST').first()
    assert fetched is not None
    assert float(fetched.amount_eur) == 9.99
    db_session.delete(fetched)
    db_session.commit()
