"""Phase 04.7.2 — Frankfurter client + DB persistence tests."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from services.exchange_rates import (
    fetch_usd_eur,
    update_daily_rate,
    get_current_rate,
)
from database.models import ExchangeRate


# ── fetch_usd_eur() ─────────────────────────────────────────────────────────

def test_fetch_usd_eur_success():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'rates': {'EUR': 0.9168},
        'base': 'USD',
        'date': '2026-04-08',
    }
    with patch('services.exchange_rates.requests.get', return_value=mock_resp):
        rate = fetch_usd_eur()
    assert rate == 0.9168


def test_fetch_failure_returns_none():
    with patch(
        'services.exchange_rates.requests.get',
        side_effect=Exception("connection refused"),
    ):
        rate = fetch_usd_eur()
    assert rate is None


# ── update_daily_rate() ─────────────────────────────────────────────────────

def test_update_daily_rate_skips_on_api_failure(db_session):
    with patch('services.exchange_rates.fetch_usd_eur', return_value=None):
        update_daily_rate()
    rows = (
        db_session.query(ExchangeRate)
                  .filter_by(date=date.today(), source='frankfurter')
                  .all()
    )
    assert len(rows) == 0


def test_update_daily_rate_idempotent(db_session):
    with patch('services.exchange_rates.fetch_usd_eur', return_value=0.9168):
        update_daily_rate()
        update_daily_rate()  # 2nd run — no duplicate
    frankfurter_rows = (
        db_session.query(ExchangeRate)
                  .filter_by(date=date.today(), source='frankfurter')
                  .all()
    )
    assert len(frankfurter_rows) == 1


# ── get_current_rate() ──────────────────────────────────────────────────────

def test_get_current_rate_with_data(db_session):
    db_session.add(ExchangeRate(
        date=date(2026, 4, 1),
        currency_pair='USD_EUR',
        rate=Decimal('0.91'),
        source='test',
    ))
    db_session.commit()
    assert get_current_rate('USD_EUR') == 0.91


def test_get_current_rate_fallback_when_empty(db_session):
    db_session.query(ExchangeRate).filter_by(currency_pair='XXX_YYY').delete()
    db_session.commit()
    assert get_current_rate('XXX_YYY') == 0.92
