"""Tests fuer den Score-Split (Phase 08.23.2.D.UX.4, S-02).

Coaching-Score = Prozess-Score (outcome-UNABHAENGIG) x Outcome-Modifier.
Split: _calc_process_score(conv) + _apply_outcome_modifier(process, base_bd, outcome).
_calc_coaching_score(conv, outcome) bleibt Thin-Wrapper (3-Tupel-Return).

Alle Tests pruefen Runtime-Verhalten (Function-Call-Return / DB-State) — kein
Source-Presence (CLAUDE.md Test-Qualitaets-Regel).
"""
import pytest


class _MockConv:
    def __init__(self, kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50):
        self.kb_end = kb
        self.einwaende_gesamt = einw_total
        self.einwaende_behandelt = einw_ok
        self.redeanteil_avg = redeanteil
        self.skript_abdeckung = skript


# ── Task 1: Split + Modifier ──────────────────────────────────────────────

def test_process_score_outcome_independent():
    """_calc_process_score(conv) liefert IMMER denselben Prozess-Score —
    die Funktion nimmt gar kein outcome-Argument (outcome-unabhaengig)."""
    from routes.app_routes import _calc_process_score
    conv = _MockConv(kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50)
    ps1, bd1 = _calc_process_score(conv)
    ps2, bd2 = _calc_process_score(conv)
    # kb=70*0.30 + 1.0*100*0.30 + 100*0.20 + 50*0.10 + 0 = 21+30+20+5 = 76
    assert ps1 == ps2 == 76.0
    assert bd1['process_score'] == 76.0
    assert 'outcome_modifier' not in bd1  # base-only, kein Modifier
    assert 'final_score' not in bd1


def test_modifier_application():
    """_apply_outcome_modifier wendet NUR den Modifier auf den Prozess-Score an."""
    from routes.app_routes import _apply_outcome_modifier
    base_bd = {'schema_version': 1, 'process_score': 100.0}
    cs, final, full = _apply_outcome_modifier(100.0, base_bd, 'contract_signed')
    assert final == 100  # 100*1.15=115 -> clamp 100
    cs2, final2, full2 = _apply_outcome_modifier(80.0, base_bd, 'no_interest')
    assert final2 == 68  # 80*0.85 = 68
    assert full2['outcome_modifier'] == 0.85
    assert 'computed_at_iso' in full2


def test_modifier_unknown_outcome():
    """Unbekanntes Outcome -> modifier 1.00, process_score unveraendert."""
    from routes.app_routes import _apply_outcome_modifier
    base_bd = {'schema_version': 1, 'process_score': 50.0}
    cs, final, full = _apply_outcome_modifier(50.0, base_bd, 'foobar_unknown')
    assert full['outcome_modifier'] == 1.00
    assert final == 50


def test_thin_wrapper_compat():
    """_calc_coaching_score bleibt 3-Tupel mit identischen breakdown-Keys."""
    from routes.app_routes import _calc_coaching_score
    conv = _MockConv(kb=70, einw_total=2, einw_ok=2, redeanteil=40, skript=50)
    res = _calc_coaching_score(conv, 'meeting_booked')
    assert isinstance(res, tuple) and len(res) == 3
    cs, final, bd = res
    assert final == 84  # round(76*1.10)=round(83.6)=84
    expected_keys = {
        'schema_version', 'kb_end_norm', 'behandelt_rate', 'redeanteil_score',
        'skript_norm', 'frage_qualitaet', 'outcome_modifier', 'process_score',
        'final_score', 'computed_at_iso',
    }
    assert expected_keys.issubset(set(bd.keys()))


def test_none_conv_defaults():
    """_calc_process_score(None) nutzt Defaults ohne Exception."""
    from routes.app_routes import _calc_process_score
    ps, bd = _calc_process_score(None)
    # kb 30*0.30 + 0.5*100*0.30 + redeanteil_score(50->100-20=80)*0.20 + 0*0.10
    # = 9 + 15 + 16 + 0 = 40
    assert isinstance(ps, float)
    assert ps == 40.0
    assert bd['schema_version'] == 1
