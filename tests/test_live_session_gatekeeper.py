"""Tests fuer den counterpart-Default in init_session_state().

Phase 08.23.2.COUNTERPART: der Gespraechspartner (Achse B) liegt in GENAU EINEM
Schluessel — state['counterpart'] mit 'gatekeeper' | 'decision_maker'. Die beiden
Alt-Schluessel contact_category + current_mode sind ersatzlos weg.

Der Init-Default haengt an der ANRUF-ART (Achse A, top-level _session_state[sid]['mode']):
cold_call startet im Vorzimmer (gatekeeper), meeting beim Entscheider (decision_maker).
"""
import pytest
from services import live_session as ls


def _get_state(mode=None):
    """Hilfsfunktion: init_session_state aufrufen und resultierenden State lesen."""
    test_sid = 'test-gatekeeper-default'
    if mode is None:
        ls.init_session_state(test_sid, 1, 1)
    else:
        ls.init_session_state(test_sid, 1, 1, mode=mode)
    return ls._session_state.get(test_sid, {}).get('state', {})


def test_init_session_state_default_counterpart():
    """counterpart muss 'gatekeeper' sein — Default ist Sekretaer-Modus."""
    state = _get_state()
    assert state['counterpart'] == 'gatekeeper', (
        f"Expected 'gatekeeper', got {state['counterpart']!r}. "
        "Default ist Sekretaer-Modus (DSGVO Single-Speaker)."
    )


def test_init_session_state_has_no_legacy_keys():
    """Die beiden Alt-Schluessel sind ersatzlos verschwunden — EIN Zustands-Ort."""
    state = _get_state()
    assert 'contact_category' not in state and 'current_mode' not in state, (
        "contact_category/current_mode duerfen nach 08.23.2.COUNTERPART nicht mehr "
        f"im per-SID-State stehen. Vorhanden: "
        f"{[k for k in ('contact_category', 'current_mode') if k in state]}"
    )


def test_init_cold_call_seeds_gatekeeper():
    """Kaltakquise startet im Vorzimmer."""
    state = _get_state()
    assert state['counterpart'] == 'gatekeeper', (
        f"cold_call muss auf gatekeeper starten, war: {state['counterpart']!r}")


def test_init_meeting_seeds_decision_maker():
    """Termin startet beim Entscheider — sonst still das falsche Phasenmodell."""
    state = _get_state(mode='meeting')
    assert state['counterpart'] == 'decision_maker', (
        "Meeting muss beim Entscheider starten — sonst laeuft jeder Termin still "
        f"im 4-Phasen-Sekretaersmodell. War: {state['counterpart']!r}")


def test_init_session_state_no_uwg_blocked_key():
    """uwg_blocked darf nicht mehr in init_session_state() vorkommen — UWG-System entfernt."""
    state = _get_state()
    assert 'uwg_blocked' not in state, (
        "uwg_blocked Key muss aus init_session_state() entfernt werden (UWG-System geloescht in C.R)."
    )
