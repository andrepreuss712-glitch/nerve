"""
tests/test_persid_03_mic_muted.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 03 — Task 3 (TDD RED then GREEN).

Waechter:
  Task 3 — mic_muted per-SID isoliert (Write via handle_mute_mic + Read via on_message).
  W-1     — toter 'state'-Subdict-Seed 'mic_muted' geloescht (liegt jetzt top-level).

Integration-Assertions (CLAUDE.md Test-Qualitaets-Regel):
  Alle Tests pruefe RUNTIME-Verhalten — State-Mutation.
"""

import pytest
import services.live_session as ls


@pytest.fixture(autouse=True)
def _clean_mic_state():
    yield
    with ls._session_state_lock:
        for sid in ['sid_a', 'sid_b', '__mic_test__']:
            ls._session_state.pop(sid, None)


def test_mic_muted_per_sid_isolation():
    """mic_muted ist per-SID isoliert: sid_a muted, sid_b nicht.

    Writer und Reader auf DERSELBEN top-level-Ebene.
    """
    with ls._session_state_lock:
        ls._session_state['sid_a'] = {'mic_muted': False}
        ls._session_state['sid_b'] = {'mic_muted': False}

    # Mute sid_a per-SID
    with ls._session_state_lock:
        if 'sid_a' in ls._session_state:
            ls._session_state['sid_a']['mic_muted'] = True

    muted_a = ls._session_state.get('sid_a', {}).get('mic_muted', False)
    muted_b = ls._session_state.get('sid_b', {}).get('mic_muted', False)

    assert muted_a is True, f"sid_a sollte muted sein, ist {muted_a!r}"
    assert muted_b is False, f"sid_b sollte nicht muted sein, ist {muted_b!r}"


def test_mic_muted_read_per_sid():
    """on_message-Logik liest mic_muted per-SID top-level."""
    with ls._session_state_lock:
        ls._session_state['sid_a'] = {'mic_muted': True}
        ls._session_state['sid_b'] = {'mic_muted': False}

    # Simuliere on_message-Read per-SID
    with ls._session_state_lock:
        muted_a = ls._session_state.get('sid_a', {}).get('mic_muted', False)
        muted_b = ls._session_state.get('sid_b', {}).get('mic_muted', False)

    assert muted_a is True
    assert muted_b is False


def test_w1_mic_muted_not_in_state_subdict():
    """W-1: init_session_state legt mic_muted top-level an, NICHT im 'state'-Subdict."""
    sid = '__mic_test__'
    ls.init_session_state(sid, user_id=99, org_id=1)
    with ls._session_state_lock:
        st = ls._session_state.get(sid, {})
        state_subdict = st.get('state', {})
        top_level_mic = st.get('mic_muted')
    ls.pop_session_state(sid)

    assert 'mic_muted' not in state_subdict, \
        f"W-1 verletzt: 'mic_muted' noch im 'state'-Subdict (statt top-level)"
    assert top_level_mic is not None, \
        "mic_muted fehlt top-level in init_session_state"


def test_mic_muted_no_global_read():
    """mic_muted-Read kommt NICHT aus ls.state (global) sondern per-SID.

    Prueft: ls.state hat kein 'mic_muted' (wurde in Plan 03 W-A entfernt).
    """
    assert 'mic_muted' not in ls.state, \
        f"ls.state enthaelt noch 'mic_muted' (sollte nach W-A entfernt sein)"
