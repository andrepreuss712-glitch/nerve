"""
tests/test_callid_threading.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.CALLID Plan 01 — call_id-Threading durch den Live-Emit-Pfad (CI-1).

Drei Ebenen:
  (a) _durable_call_id — reiner Sentinel-/None-Guard (KEIN Setup, reine Funktion).
  (b) resolve_call_id_for_sid — Locking-Getter gegen echten _session_state (State-Mutation,
      kein Source-Presence).
  (c) Integration: die EXAKTE Caller-Naht (_durable_call_id(state['call_id']) -> emit_intent_event(
      call_id=...)) gegen REAL-PG -> die geschriebene intent_event-Row traegt die durable call_id.

Integration-Assertion (CLAUDE.md Test-Qualitaets-Regel): echte DB-Row gegen nerve_test, KEIN
Source-Presence. Committende Tests raeumen ihre Rows via cleanup_rows weg (Baseline-Sauberkeit).
Server-seitig via pytest (kein Local-Dev). Sauberer Skip wenn DB-Fixture fehlt.
"""

import uuid
from datetime import datetime, timezone

import tests.conftest as conftest
from tests.conftest import cleanup_rows

import services.live_session as ls


# ── (a) _durable_call_id — reine Funktion, kein Setup ────────────────────────────
def test_durable_call_id_durable_uuid_passes_through():
    cid = str(uuid.uuid4())
    assert ls._durable_call_id(cid) == cid


def test_durable_call_id_sentinel_returns_none():
    # NIEMALS den Sentinel-String durchreichen (CI-1) — er wuerde sonst in die UUID-Spalte landen.
    assert ls._durable_call_id('__call_pending__') is None


def test_durable_call_id_none_and_empty_return_none():
    assert ls._durable_call_id(None) is None
    assert ls._durable_call_id('') is None


# ── (b) resolve_call_id_for_sid — Locking-Getter gegen echten _session_state ─────
def _set_state_call_id(sid, raw):
    """Echte State-Mutation (kein Mock): setzt _session_state[sid]['state']['call_id']."""
    with ls._session_state_lock:
        ls._session_state.setdefault(sid, {}).setdefault('state', {})['call_id'] = raw


def test_resolve_returns_durable_uuid_from_state():
    sid = f"test-callid-{uuid.uuid4().hex[:10]}"
    cid = str(uuid.uuid4())
    _set_state_call_id(sid, cid)
    try:
        assert ls.resolve_call_id_for_sid(sid) == cid
    finally:
        ls.pop_session_state(sid)


def test_resolve_sentinel_returns_none():
    sid = f"test-callid-{uuid.uuid4().hex[:10]}"
    _set_state_call_id(sid, '__call_pending__')
    try:
        assert ls.resolve_call_id_for_sid(sid) is None
    finally:
        ls.pop_session_state(sid)


def test_resolve_empty_or_unknown_sid_returns_none():
    # unbekannte sid -> None (kein KeyError)
    assert ls.resolve_call_id_for_sid(f"unknown-{uuid.uuid4().hex[:8]}") is None
    # sid mit call_id=None im State -> None
    sid = f"test-callid-{uuid.uuid4().hex[:10]}"
    _set_state_call_id(sid, None)
    try:
        assert ls.resolve_call_id_for_sid(sid) is None
    finally:
        ls.pop_session_state(sid)


# ── (c) Integration: Caller-Naht (durable state-call_id -> emit) gegen REAL-PG ────
def _seed_call(db, tenant):
    """calls-Row (tenant_id=tenant, keine RLS) -> gibt call_id (UUID-str) zurueck."""
    from database.models import Call
    cid = str(uuid.uuid4())
    db.add(Call(id=cid, user_id=1, tenant_id=tenant, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), transcript_storage='none'))
    db.commit()
    return cid


def test_emit_with_durable_call_id_from_state_writes_call_id(db_session):
    """Die exakte 4-Caller-Naht: durable call_id im gehaltenen state lesen (_durable_call_id),
    an emit_intent_event uebergeben -> die geschriebene intent_event-Row traegt die call_id (V-CI-1).
    Kein reiner Mock: echte calls-FK + echte intent_event-Row gegen nerve_test."""
    from database.models import IntentEvent
    from services.intent_event_writer import emit_intent_event
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    cid = _seed_call(db_session, tenant)
    sid = f"test-callid-{uuid.uuid4().hex[:10]}"
    # State so setzen, wie der Live-Pfad ihn nach create_call_for_sid haelt (durable UUID).
    _set_state_call_id(sid, cid)
    eid = None
    try:
        # NAHT wie in den 4 Aufrufern: call_id DIREKT aus dem gehaltenen state via reinem Guard.
        with ls._session_state_lock:
            _st = ls._session_state.get(sid, {}).get('state', {})
            _cid = ls._durable_call_id(_st.get('call_id'))
        assert _cid == cid  # Sentinel-frei, durable
        eid = emit_intent_event(
            session_id=sid, mode='cold_call', intent_type='echter_einwand',
            source='llm_inferred', speaker_role='kunde', speaker_id='local',
            confidence=0.9, call_id=_cid,
        )
        assert isinstance(eid, int) and eid > 0
        # frische TX -> die vom Writer (eigene Session) committete Row sehen
        db_session.rollback()
        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert str(row.call_id) == cid  # durable call_id durchgereicht, NICHT NULL, NICHT Sentinel
    finally:
        ls.pop_session_state(sid)
        if eid is not None:
            cleanup_rows(db_session,
                         {"public.intent_event": [eid], "public.calls": [cid]},
                         tenant=tenant)
        else:
            cleanup_rows(db_session, {"public.calls": [cid]}, tenant=tenant)


def test_emit_alarm_on_none_call_id_fails_closed(db_session, capsys):
    """call_id=None (Rest-Race/Regression) -> LAUTER [CALLID-ALARM]-Log + KEIN raise (Punkt 25,
    Live-Pfad bricht nicht). AB CALLID Deploy 2 (Migration 0025, call_id NOT NULL): der INSERT
    wird von der DB fail-closed abgewiesen -> emit faengt den IntegrityError (Edge 3) -> Rueckgabe -1,
    KEINE Row. Der Alarm bleibt sichtbar (vor dem INSERT geloggt). V-CI-1.

    (Vor Deploy 2 schrieb dieser Pfad eine NULL-Row; NOT NULL macht den Regress jetzt zusaetzlich
    am DB-Waechter sichtbar, ohne den Live-Loop zu brechen — der Backstop Plan 03 bleibt primaer.)"""
    from database.models import IntentEvent
    from services.intent_event_writer import emit_intent_event

    sid = f"test-callid-{uuid.uuid4().hex[:10]}"
    eid = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='echter_einwand',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
        confidence=0.9, call_id=None,
    )
    out = capsys.readouterr().out
    assert '[CALLID-ALARM]' in out          # lauter Alarm, sichtbar (vor dem INSERT)
    assert eid == -1                          # NOT NULL -> INSERT fail-closed -> -1 (kein raise, Edge 3)
    # KEINE Row mit dieser session_id geschrieben (fail-closed, nicht still NULL).
    db_session.rollback()
    assert db_session.query(IntentEvent).filter_by(session_id=sid).count() == 0
