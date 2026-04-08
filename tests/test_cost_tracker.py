"""Phase 04.7.2 Wave 2 — cost_tracker unit tests."""
from datetime import date
from decimal import Decimal
import pytest

from database.models import ApiCostLog, ApiRate, ExchangeRate
from services.cost_tracker import log_api_cost
import database.db as _db_mod


@pytest.fixture
def patched_sessionlocal(db_session, monkeypatch):
    """Point database.db.SessionLocal at the in-memory test engine so that
    log_api_cost() writes into the same DB as the test fixture."""
    bind = db_session.get_bind()
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=bind, autocommit=False, autoflush=False)
    monkeypatch.setattr(_db_mod, 'SessionLocal', TestSession)
    return TestSession


@pytest.fixture
def seeded_rate(db_session, patched_sessionlocal):
    rate = ApiRate(provider='anthropic', model='haiku-test',
                   unit_type='per_1k_input_tokens',
                   price_per_unit=Decimal('0.00025'),
                   currency='USD', active=True)
    db_session.add(rate)
    fx = ExchangeRate(date=date(2026, 4, 1), currency_pair='USD_EUR',
                      rate=Decimal('0.92'), source='test')
    db_session.add(fx)
    db_session.commit()
    return rate


def test_freeze_fx_on_write(db_session, seeded_rate):
    log_api_cost('anthropic', 'haiku-test', user_id=1, units=10.0,
                 unit_type='per_1k_input_tokens')
    row = db_session.query(ApiCostLog).filter_by(provider='anthropic').first()
    assert row is not None
    assert float(row.fx_rate_applied) == 0.92
    assert float(row.rate_applied) == 0.00025
    # 10 * 0.00025 * 0.92 = 0.0023
    assert abs(float(row.cost_eur) - 0.0023) < 1e-6
    assert row.rate_currency == 'USD'


def test_missing_rate_no_raise(db_session, patched_sessionlocal):
    # KEIN seeded_rate — log should silently skip
    log_api_cost('unknown', 'noop', user_id=1, units=5, unit_type='per_minute')
    assert db_session.query(ApiCostLog).count() == 0


def test_missing_rate_no_raise_no_db():
    """Ensure function does not raise even without any DB setup."""
    log_api_cost('unknown', 'noop', user_id=1, units=5, unit_type='per_minute')


def test_eur_rate_currency_no_fx(db_session, patched_sessionlocal):
    rate = ApiRate(provider='stripe', model='card', unit_type='fixed_per_tx',
                   price_per_unit=Decimal('0.25'), currency='EUR', active=True)
    db_session.add(rate)
    db_session.commit()
    log_api_cost('stripe', 'card', user_id=1, units=1.0,
                 unit_type='fixed_per_tx')
    row = db_session.query(ApiCostLog).filter_by(provider='stripe').first()
    assert row is not None
    assert float(row.fx_rate_applied) == 1.0
    assert float(row.cost_eur) == 0.25


def test_silent_on_db_error(monkeypatch, capsys):
    def broken_session(*args, **kwargs):
        raise RuntimeError("db down")
    import database.db as _db_mod2
    monkeypatch.setattr(_db_mod2, 'SessionLocal', broken_session)
    # Should NOT raise
    log_api_cost('anthropic', 'haiku-test', user_id=1, units=1.0,
                 unit_type='per_1k_input_tokens')
    captured = capsys.readouterr()
    assert 'CostTracker' in captured.out or 'failed' in captured.out.lower()
