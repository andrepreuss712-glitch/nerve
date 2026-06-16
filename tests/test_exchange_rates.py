"""Phase 04.7.2 — Frankfurter client + DB persistence tests."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from services.exchange_rates import (
    fetch_usd_eur,
    update_daily_rate,
    get_current_rate,
)
from database.models import ExchangeRate
from tests.conftest import cleanup_rows


# ── Phase 08.23.2.PGTEST Gruppe B — cleanup_rows-Teardown + Baseline-Restore (T-PGTEST-24) ──
# update_daily_rate() committet auf einer EIGENEN get_session() (services/exchange_rates.py:49),
# NICHT auf der function-scoped db_session → der D-03-Rollback raeumt das NICHT weg. ZWEI Faelle:
#   (a) Es existiert KEINE heutige USD_EUR-Row → update_daily_rate INSERTet eine neue frankfurter-Row
#       → leaked PK → cleanup_rows loescht sie.
#   (b) Die Baseline traegt bereits eine heutige USD_EUR-Row (_seed_founder_dashboard_defaults seedet
#       ExchangeRate(date=today, 'USD_EUR', rate=0.92, source='seed')) → update_daily_rate UPGRADEt sie
#       IN-PLACE auf source='frankfurter'+neue rate (exchange_rates.py:56-64) → KEINE neue Row, aber die
#       Baseline-Row MUTIERT (xmin-Drift, #7) → Guard rot. Loeschen waere falsch (→ missing-PK). FIX:
#       Pre-State der heutigen USD_EUR-Row SICHERN, POST-yield RESTOREN (Baseline-Treue).
# get_current_rate-/db_session-only-Tests sind rollback-covered (D-03) und brauchen das nicht.
# Kanonische Mechanik: cleanup_tracker-FIXTURE (NIEMALS yield im plain Test-Body, T-PGTEST-34).
@pytest.fixture
def fx_cleanup(db_session):
    from database.db import get_session
    # Pre-State der heutigen USD_EUR-Rows sichern (id -> (rate, source)).
    db = get_session()
    try:
        pre = {r.id: (r.rate, r.source) for r in (
            db.query(ExchangeRate).filter_by(date=date.today(),
                                              currency_pair='USD_EUR').all())}
    finally:
        db.close()
    yield
    teardown_db = get_session()
    try:
        rows = (teardown_db.query(ExchangeRate)
                .filter_by(date=date.today(), currency_pair='USD_EUR').all())
        new_ids = []
        for r in rows:
            if r.id in pre:
                # Baseline-Row: Pre-State wiederherstellen (rate + source), kein DELETE.
                orig_rate, orig_source = pre[r.id]
                r.rate, r.source = orig_rate, orig_source
            else:
                new_ids.append(r.id)   # neu inserted → wegloeschen
        teardown_db.commit()
    finally:
        teardown_db.close()
    if new_ids:
        cl_db = get_session()
        try:
            cleanup_rows(cl_db, {ExchangeRate: new_ids})
        finally:
            cl_db.close()


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

def test_update_daily_rate_skips_on_api_failure(db_session, fx_cleanup):
    # Phase 08.23.2.PGTEST.GREEN Muster C: echtes nerve_test traegt gesaete/geupgradete heutige
    # USD_EUR-Rows -> absolutes `len == 0` ist drift-anfaellig. Delta-Pruefung: API-down darf KEINE
    # NEUE frankfurter-Row schreiben (update_daily_rate returnt early bei rate=None).
    before = (
        db_session.query(ExchangeRate)
                  .filter_by(date=date.today(), source='frankfurter')
                  .count()
    )
    with patch('services.exchange_rates.fetch_usd_eur', return_value=None):
        update_daily_rate()
    after = (
        db_session.query(ExchangeRate)
                  .filter_by(date=date.today(), source='frankfurter')
                  .count()
    )
    assert after == before


def test_update_daily_rate_idempotent(db_session, fx_cleanup):
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
    # Phase 08.23.2.PGTEST.GREEN Muster C: echtes nerve_test traegt eine gesaete heutige USD_EUR-Row
    # (source='seed', 0.92). get_current_rate ordnet date.desc() OHNE Obergrenze -> die Test-Row braucht
    # ein Datum NEUER als jede gesaete Row, damit sie date.desc() gewinnt (statt fixem 2026-04-01, das
    # eine gesaete heutige Row ueberstimmt). Anschliessend cleanup_rows (Baseline-Sauberkeit).
    row = ExchangeRate(
        date=date.today() + timedelta(days=1),
        currency_pair='USD_EUR',
        rate=Decimal('0.91'),
        source='test',
    )
    db_session.add(row)
    db_session.commit()
    try:
        assert get_current_rate('USD_EUR') == 0.91
    finally:
        cleanup_rows(db_session, {ExchangeRate: [row.id]})


def test_get_current_rate_fallback_when_empty(db_session):
    db_session.query(ExchangeRate).filter_by(currency_pair='XXX_YYY').delete()
    db_session.commit()
    assert get_current_rate('XXX_YYY') == 0.92
