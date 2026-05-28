"""Tests for _calc_coaching_score() in routes/app_routes.py.

D.UX REQ-D.UX-11: deterministic score formula with outcome modifier.
All tests use pure function calls — no DB, no Flask context needed.
"""
import pytest
from routes.app_routes import _calc_coaching_score


class _MockConv:
    def __init__(self, kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50):
        self.kb_end = kb
        self.einwaende_gesamt = einw_total
        self.einwaende_behandelt = einw_ok
        self.redeanteil_avg = redeanteil
        self.skript_abdeckung = skript


def test_score_meeting_booked():
    """kb=70, behandelt_rate=1.0, redeanteil=40, skript=50, outcome=meeting_booked
    process_score = 70*0.30 + 100*0.30 + 100*0.20 + 50*0.10 + 0 = 21+30+20+5+0 = 76
    final_score = round(76 * 1.10) = round(83.6) = 84
    """
    conv = _MockConv(kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50)
    _, final, bd = _calc_coaching_score(conv, 'meeting_booked')
    assert final == 84


def test_score_no_interest():
    """final_score = round(76 * 0.85) = round(64.6) = 65"""
    conv = _MockConv(kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50)
    _, final, bd = _calc_coaching_score(conv, 'no_interest')
    assert final == 65


def test_score_contract_signed():
    """final_score = round(76 * 1.15) = round(87.4) = 87"""
    conv = _MockConv(kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50)
    _, final, bd = _calc_coaching_score(conv, 'contract_signed')
    assert final == 87


def test_score_breakdown_has_9_keys():
    """score_breakdown must contain all 9 required keys."""
    _, _, bd = _calc_coaching_score(None, 'meeting_booked')
    expected_keys = {
        'schema_version', 'kb_end_norm', 'behandelt_rate', 'redeanteil_score',
        'skript_norm', 'frage_qualitaet', 'outcome_modifier', 'process_score',
        'final_score', 'computed_at_iso',
    }
    assert expected_keys.issubset(set(bd.keys()))


def test_score_breakdown_schema_version():
    """schema_version must be 1 in all breakdowns."""
    _, _, bd = _calc_coaching_score(None, 'callback')
    assert bd['schema_version'] == 1


def test_score_clamp_max():
    """final_score must never exceed 100."""
    conv = _MockConv(kb=100, einw_total=1, einw_ok=1, redeanteil=40, skript=100)
    _, final, _ = _calc_coaching_score(conv, 'contract_signed')
    assert final <= 100


def test_score_clamp_min():
    """final_score must never go below 0."""
    conv = _MockConv(kb=0, einw_total=1, einw_ok=0, redeanteil=0, skript=0)
    _, final, _ = _calc_coaching_score(conv, 'no_interest')
    assert final >= 0


def test_score_no_conv_uses_defaults():
    """conv=None uses fallback defaults and returns valid int in [0, 100]."""
    coaching, final, bd = _calc_coaching_score(None, 'meeting_booked')
    assert isinstance(final, int)
    assert 0 <= final <= 100
