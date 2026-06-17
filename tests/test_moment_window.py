"""
tests/test_moment_window.py
────────────────────────────────────────────────────────────────────
TAXO1-Welle 4 (I-4-FOLD + Gemini-R2) — pure-logic Tests fuer das
ereignis-getriebene Moment-FENSTER (get_or_open_moment / close_moment).

KEIN Live-Call, KEINE DB, KEIN LLM: baut ein Mini-_session_state[sid]['state']
und ruft die Helfer direkt (Function-Call-Return + State-Mutation, CLAUDE.md
Test-Qualitaets-Regel). Die Helfer sind lock-free — der Test simuliert den
"Aufrufer haelt _session_state_lock"-Kontext durch direkten Aufruf.
"""

import uuid

import pytest

import services.live_session as ls


@pytest.fixture
def sid():
    _sid = f"test-moment-{uuid.uuid4().hex[:12]}"
    # Mini-State seeden (wie init_session_state['state'] die 3 Fenster-Keys legt)
    with ls._session_state_lock:
        ls._session_state[_sid] = {
            'state': {
                'interaction_id': None,
                'moment_opened_mode': None,
                'moment_opened_monotonic': 0.0,
            }
        }
    yield _sid
    with ls._session_state_lock:
        ls._session_state.pop(_sid, None)


def test_open_mints_id(sid):
    iid = ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    assert iid is not None
    assert ls._session_state[sid]['state']['interaction_id'] == iid


def test_consecutive_same_window_joins(sid):
    a = ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    b = ls.get_or_open_moment(sid, mode='cold_call', now=2.0)
    assert a == b  # Stapeln/JOIN: mehrere Einwand-Echos = EIN Moment (§5)


def test_continue_does_not_refresh_cap(sid):
    """Gemini-R2: der Max-Dauer-Deckel refresht NICHT. Fenster bei now=0 oeffnen,
    bei 10/20/30/40 fortsetzen, dann bei 95 (>90 ab OEFFNUNG, obwohl letzter Call
    bei 40) -> NEUE id. Haette der alte Idle-Timer refresht, waere 95-40=55<90 noch
    dieselbe id (Ueber-Verklumpung)."""
    a = ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    for t in (10.0, 20.0, 30.0, 40.0):
        same = ls.get_or_open_moment(sid, mode='cold_call', now=t)
        assert same == a
    new = ls.get_or_open_moment(sid, mode='cold_call', now=95.0)
    assert new != a  # Deckel ab OEFFNUNG -> neue id (kein Refresh)


def test_close_then_open_new_id(sid):
    a = ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    ls.close_moment(sid, reason='advisor_answered')
    b = ls.get_or_open_moment(sid, mode='cold_call', now=1.0)
    assert a != b  # neues Fenster nach "Berater hat geantwortet"


def test_max_duration_cap_closes(sid):
    a = ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    b = ls.get_or_open_moment(sid, mode='cold_call', now=91.0)  # > MOMENT_WINDOW_MAX_S (90)
    assert a != b  # harte Notbremse


def test_mode_downgrade_resets(sid):
    a = ls.get_or_open_moment(sid, mode='meeting', now=0.0)
    b = ls.get_or_open_moment(sid, mode='cold_call', now=1.0)
    assert a != b
    assert ls._session_state[sid]['state']['moment_opened_mode'] == 'cold_call'


def test_close_idempotent(sid):
    ls.get_or_open_moment(sid, mode='cold_call', now=0.0)
    ls.close_moment(sid, reason='x')
    ls.close_moment(sid, reason='x')  # zweimal -> kein Crash
    assert ls._session_state[sid]['state']['interaction_id'] is None
