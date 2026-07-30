"""Session-State Phase-C Keys (Req-11, Pitfall 3+6).

Verifiziert dass alle neuen Phase-C-Keys per-SID (NICHT in ls.state) initialisiert werden.
"""
import pytest

from services.live_session import init_session_state, pop_session_state, _session_state, _session_state_lock


@pytest.fixture
def fresh_sid():
    sid = 'test-c-sid'
    # Cleanup vor dem Test (falls Relic aus vorherigem Lauf)
    with _session_state_lock:
        _session_state.pop(sid, None)
    yield sid
    # Cleanup nach dem Test
    with _session_state_lock:
        _session_state.pop(sid, None)


def test_init_session_state_has_context_notes(fresh_sid):
    init_session_state(fresh_sid, user_id=1, org_id=1)
    st = _session_state[fresh_sid]['state']
    assert st.get('context_notes') == []


def test_init_session_state_has_counterpart(fresh_sid):
    # Phase 08.23.2.COUNTERPART: EIN Gespraechspartner-Schluessel, Default 'gatekeeper'
    init_session_state(fresh_sid, user_id=1, org_id=1)
    assert _session_state[fresh_sid]['state']['counterpart'] == 'gatekeeper'


def test_init_session_state_has_hysteresis_keys(fresh_sid):
    init_session_state(fresh_sid, user_id=1, org_id=1)
    st = _session_state[fresh_sid]['state']
    assert st['phase_hint_count'] == 0
    assert st['pending_phase'] is None
    assert st['phase_entered_at'] is None


def test_init_session_state_has_call_id_placeholder(fresh_sid):
    init_session_state(fresh_sid, user_id=1, org_id=1)
    assert _session_state[fresh_sid]['state'].get('call_id') is None



def test_pop_session_state_removes_context_notes(fresh_sid):
    init_session_state(fresh_sid, user_id=1, org_id=1)
    assert fresh_sid in _session_state
    pop_session_state(fresh_sid)
    assert fresh_sid not in _session_state


def test_no_global_ls_state_writes_for_phase_c_keys(fresh_sid):
    """Pitfall 3+6: neue Phase-C-Keys duerfen NICHT in ls.state geschrieben werden."""
    import services.live_session as ls
    before_keys = set(getattr(ls, 'state', {}).keys())
    init_session_state(fresh_sid, user_id=1, org_id=1)
    after_keys = set(getattr(ls, 'state', {}).keys())
    forbidden = {'counterpart', 'context_notes', 'phase_hint_count', 'pending_phase'}
    new_keys = after_keys - before_keys
    assert not (new_keys & forbidden), f'Phase-C-Keys in ls.state geschrieben: {new_keys & forbidden}'
