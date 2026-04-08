"""Phase 04.7.2 — Stripe invoice.payment_succeeded webhook handler tests."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from routes.payments import _classify_tax_treatment, _record_revenue
from database.models import RevenueLog


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'stripe_invoice.json'


def _load_fixture(country='DE', total_tax=1311):
    base = json.loads(FIXTURE_PATH.read_text())
    if total_tax == 0:
        for line in base['lines']['data']:
            line['tax_amounts'] = []
        base['total'] = base['subtotal']
    base['_test_country'] = country
    return base


def _mock_customer(country):
    m = MagicMock()
    m.get = lambda k, d=None: {'address': {'country': country}}.get(k, d)
    return m


# ── Unit: _classify_tax_treatment ──────────────────────────────────────────

def test_classify_tax_treatment_unit():
    assert _classify_tax_treatment('DE', 1311) == 'DE_19'
    assert _classify_tax_treatment('AT', 0) == 'EU_RC'
    assert _classify_tax_treatment('FR', 0) == 'EU_RC'
    assert _classify_tax_treatment('CH', 0) == 'DRITTLAND'
    assert _classify_tax_treatment('US', 0) == 'DRITTLAND'
    assert _classify_tax_treatment(None, 1311) == 'DE_19'
    assert _classify_tax_treatment(None, 0) == 'DRITTLAND'


# ── Integration: _record_revenue ───────────────────────────────────────────

def test_de_invoice_tax_19(db_session):
    inv = _load_fixture('DE', 1311)
    with patch('stripe.Customer.retrieve', return_value=_mock_customer('DE')):
        _record_revenue(db_session, inv)
    row = db_session.query(RevenueLog).filter_by(stripe_invoice_id=inv['id']).first()
    assert row is not None
    assert row.netto_cents == 6900
    assert row.ust_cents == 1311
    assert row.brutto_cents == 8211
    assert row.country == 'DE'
    assert row.tax_treatment == 'DE_19'


def test_at_reverse_charge(db_session):
    inv = _load_fixture('AT', 0)
    inv['id'] = 'in_test_at_rc'
    with patch('stripe.Customer.retrieve', return_value=_mock_customer('AT')):
        _record_revenue(db_session, inv)
    row = db_session.query(RevenueLog).filter_by(stripe_invoice_id='in_test_at_rc').first()
    assert row is not None
    assert row.tax_treatment == 'EU_RC'
    assert row.ust_cents == 0


def test_ch_drittland(db_session):
    inv = _load_fixture('CH', 0)
    inv['id'] = 'in_test_ch_dl'
    with patch('stripe.Customer.retrieve', return_value=_mock_customer('CH')):
        _record_revenue(db_session, inv)
    row = db_session.query(RevenueLog).filter_by(stripe_invoice_id='in_test_ch_dl').first()
    assert row is not None
    assert row.tax_treatment == 'DRITTLAND'
    assert row.country == 'CH'


def test_idempotent_on_duplicate_event(db_session):
    inv = _load_fixture('DE', 1311)
    inv['id'] = 'in_test_idemp'
    with patch('stripe.Customer.retrieve', return_value=_mock_customer('DE')):
        _record_revenue(db_session, inv)
        _record_revenue(db_session, inv)
    count = db_session.query(RevenueLog).filter_by(stripe_invoice_id='in_test_idemp').count()
    assert count == 1
