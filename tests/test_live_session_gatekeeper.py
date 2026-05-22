"""Tests fuer init_session_state() Gatekeeper-Default.

Phase 08.23.2.C.R: init_session_state() muss contact_category='gatekeeper'
und current_mode='gatekeeper' im Session-State setzen (DSGVO Single-Speaker — Default ist Sekretaer).
"""
import pytest
from services import live_session as ls


def _get_state():
    """Hilfsfunktion: init_session_state aufrufen und resultierenden State lesen."""
    test_sid = 'test-gatekeeper-default'
    ls.init_session_state(test_sid, 1, 1)
    return ls._session_state.get(test_sid, {}).get('state', {})


def test_init_session_state_default_contact_category():
    """contact_category muss 'gatekeeper' sein — nicht 'unknown'."""
    state = _get_state()
    assert state['contact_category'] == 'gatekeeper', (
        f"Expected 'gatekeeper', got {state['contact_category']!r}. "
        "Phase C.R: Default ist Sekretaer-Modus."
    )


def test_init_session_state_default_current_mode():
    """current_mode muss 'gatekeeper' sein — nicht 'cold_call'."""
    state = _get_state()
    assert state['current_mode'] == 'gatekeeper', (
        f"Expected 'gatekeeper', got {state['current_mode']!r}. "
        "Phase C.R: Default ist Sekretaer-Modus."
    )


def test_init_session_state_no_uwg_blocked_key():
    """uwg_blocked darf nicht mehr in init_session_state() vorkommen — UWG-System entfernt."""
    state = _get_state()
    assert 'uwg_blocked' not in state, (
        "uwg_blocked Key muss aus init_session_state() entfernt werden (UWG-System geloescht in C.R)."
    )
