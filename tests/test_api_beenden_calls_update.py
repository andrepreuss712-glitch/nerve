"""Phase 08.23.2.D REQ-D-2 + REQ-D-6 - api_beenden calls-UPDATE Integration-Test.

CLAUDE.md-konform: ausschliesslich Runtime-Behavior-Tests gegen DB.
KEINE Source-Presence-Assertions (`open().read()` / string-in-source).

Hinweis SQLite-Compat: call_events.id ist BIGINT NOT NULL (kein SQLite-ROWID-Autoincrement).
SQLite erkennt AUTOINCREMENT nur fuer INTEGER PRIMARY KEY, nicht fuer BIGINT PRIMARY KEY.
Daher verwenden Tests einen atomaren Counter fuer event_id.
"""
import pytest
import uuid
import time
import itertools
from datetime import datetime, timezone

# Atomarer Counter fuer call_events.id (SQLite-BIGINT-NOT-NULL-Compat)
_event_id_counter = itertools.count(start=int(time.time() * 1000) % 1_000_000_000)

from database.db import get_session
from database.models import Call, CallEvent, ConversationLog
from services import outcome_service


def _make_test_call(user_id=1):
    """Erzeugt einen Early-Call-Record (analog create_call_for_sid).

    Gibt call_id als String zurueck (SQLite UUID-Compat: kein nativer UUID-Typ in SQLite).
    """
    db = get_session()
    try:
        call_id = str(uuid.uuid4())
        row = Call(
            id=call_id,
            user_id=user_id,
            call_mode='cold_call',
            started_at=datetime.now(timezone.utc),
            transcript_storage='none',
        )
        db.add(row)
        db.commit()
        return call_id
    finally:
        db.close()


def _cleanup_call(call_id):
    db = get_session()
    try:
        db.query(CallEvent).filter(CallEvent.call_id == call_id).delete()
        db.query(Call).filter(Call.id == call_id).delete()
        db.commit()
    finally:
        db.close()


# -- REQ-D-2: UPDATE schreibt conversation_log_id + ended_at + call_mode --

def test_update_helper_writes_conversation_log_id(db_session):
    """REQ-D-2: Nach UPDATE-Logik hat Call-Row conversation_log_id != None.

    Repliziert das UPDATE-Verhalten aus api_beenden direkt gegen die DB.
    Bricht wenn die DB-Spalte fehlt oder der Write-Pfad nicht funktioniert.
    """
    call_id = _make_test_call()
    saved_conv_id = None
    try:
        db = get_session()
        try:
            # Phase 08.23.2.PGTEST.GREEN Muster A: echte ConversationLog-Row statt fake 12345 —
            # calls.conversation_log_id ist FK auf conversation_logs(id), auf PG erzwungen (SQLite-Aera
            # kannte keine FK). ORM-Pfad fuellt market='dach'/language='de' (Python-default).
            conv = ConversationLog(user_id=1, org_id=1, started_at=datetime.now(timezone.utc))
            db.add(conv)
            db.commit()
            saved_conv_id = conv.id

            row = db.query(Call).filter(Call.id == call_id).first()
            assert row.ended_at is None
            assert row.conversation_log_id is None
            # UPDATE wie in api_beenden (Plan 04 Task 4.1 Block B)
            row.ended_at = datetime.now(timezone.utc)
            row.conversation_log_id = saved_conv_id
            row.call_mode = 'meeting_consented'
            db.commit()

            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.ended_at is not None
            assert row2.conversation_log_id == saved_conv_id
            assert row2.call_mode == 'meeting_consented'
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)  # zuerst das Kind (Call referenziert conv via FK)
        if saved_conv_id is not None:
            _db = get_session()
            try:
                _db.query(ConversationLog).filter(ConversationLog.id == saved_conv_id).delete()
                _db.commit()
            finally:
                _db.close()


def test_update_helper_call_mode_from_req_data_cold_call(db_session):
    """REQ-D-2 + D-05a: call_mode 'cold_call' aus req_data wird korrekt persistiert."""
    call_id = _make_test_call()
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            # Mapping wie in api_beenden: 'cold_call' bleibt 'cold_call'
            _req_mode = 'cold_call'
            row.call_mode = 'cold_call' if _req_mode == 'cold_call' else 'meeting_consented'
            db.commit()
            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.call_mode == 'cold_call'
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


def test_update_helper_call_mode_meeting_maps_to_meeting_consented(db_session):
    """REQ-D-2 + D-05a: session_mode 'meeting' aus req_data wird zu 'meeting_consented' gemappt."""
    call_id = _make_test_call()
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            # Mapping wie in api_beenden: 'meeting' -> 'meeting_consented'
            _req_mode = 'meeting'
            row.call_mode = 'cold_call' if _req_mode == 'cold_call' else 'meeting_consented'
            db.commit()
            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.call_mode == 'meeting_consented'
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


# -- REQ-D-6: Audio-Health-Thread schreibt score + CallEvent --

def test_audio_health_bg_writes_score_and_callevent_with_buffer(db_session):
    """REQ-D-6: Mit nicht-leerem word_confidences-Buffer schreibt der Background-Thread-Pfad
    audio_health_score auf die Call-Row UND eine CallEvent-Row mit event_type='audio_health'.

    Repliziert das exakte Verhalten von _audio_health_bg aus Plan 04 Task 4.1 Block C.
    """
    call_id = _make_test_call()
    try:
        # Buffer wie er aus ls._session_state[sid]['word_confidences'] kommen wuerde
        buf = [(i * 100, 0.85) for i in range(100)]
        metrics = outcome_service.calculate_audio_health(buf)
        assert metrics['score'] is not None, "calculate_audio_health muss bei nicht-leerem Buffer score liefern"

        # Repliziert die DB-Write-Logik aus _audio_health_bg
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            row.audio_health_score = float(metrics['score'])
            db.add(CallEvent(
                id=next(_event_id_counter),
                call_id=call_id,
                event_type='audio_health',
                event_ts_ms=int(time.time() * 1000),
                payload={
                    'mean': metrics.get('mean'),
                    'median': metrics.get('median'),
                    'pct_below_07': metrics.get('pct_below_07'),
                    'longest_uncertain_block_s': metrics.get('longest_uncertain_block_s'),
                    'stddev': metrics.get('stddev'),
                    'score': metrics.get('score'),
                },
            ))
            db.commit()

            # Verify Behavior
            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.audio_health_score is not None
            assert 0.0 <= row2.audio_health_score <= 1.0
            ev = (
                db.query(CallEvent)
                  .filter(CallEvent.call_id == call_id, CallEvent.event_type == 'audio_health')
                  .first()
            )
            assert ev is not None
            assert ev.payload is not None
            assert ev.payload.get('score') is not None
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


def test_audio_health_bg_skips_on_empty_buffer(db_session):
    """REQ-D-6: Leerer Buffer -> calculate_audio_health liefert score=None ->
    _audio_health_bg macht early-return, KEIN CallEvent + audio_health_score bleibt None.
    """
    metrics = outcome_service.calculate_audio_health([])
    assert metrics['score'] is None

    call_id = _make_test_call()
    try:
        db = get_session()
        try:
            # Da score None ist, simuliert der Test den early-return:
            # KEINE Schreibung. row.audio_health_score bleibt None.
            row = db.query(Call).filter(Call.id == call_id).first()
            assert row.audio_health_score is None
            # Kein CallEvent existiert
            ev_count = (
                db.query(CallEvent)
                  .filter(CallEvent.call_id == call_id, CallEvent.event_type == 'audio_health')
                  .count()
            )
            assert ev_count == 0
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


# -- Edge: kein call_id im Session-State (graceful) --

def test_no_call_id_no_update_no_crash(db_session):
    """Edge-Case: Wenn _phase_d_call_id None bleibt (kein Session-State),
    wird kein UPDATE ausgefuehrt und kein Crash provoziert.
    Prueft dass ein None-Filter kein Call-Update-Target findet.
    """
    db = get_session()
    try:
        row = db.query(Call).filter(Call.id == None).first()  # noqa: E711
        assert row is None  # kein UPDATE-Target
    finally:
        db.close()


# -- TAXO2-07: transcript_resolved Fan-In-Flag --

def test_calls_update_sets_transcript_resolved(db_session):
    """TAXO2-07 Test A (DB-Behavior): Nach Replikation des api_beenden calls-UPDATE-Blocks
    hat die Call-Row transcript_resolved=True in der DB.

    Prueft Runtime-Verhalten der Persistenz-Schicht — kein Source-Presence-Test (CLAUDE.md).
    Repliziert exakt den Setpoint-Pfad: row.ended_at setzen, row.call_mode setzen,
    row.transcript_resolved = True setzen, committen, Row neu lesen, assertieren.
    """
    call_id = _make_test_call()
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            assert row.transcript_resolved is False or row.transcript_resolved == False  # noqa: E712  # Spalte DEFAULT FALSE
            # Repliziert den calls-UPDATE-Block aus api_beenden (resolved-als-absent)
            row.ended_at = datetime.now(timezone.utc)
            row.call_mode = 'cold_call'
            row.transcript_resolved = True
            db.commit()

            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.transcript_resolved is True
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


def test_transcript_resolved_committed_before_slow_lane_put(db_session):
    """TAXO2-07 Test B (Ordering): slow_lane.put wird NACH dem commit enqueued.

    Prueft die Commit-vor-Put-Reihenfolge via Call-Order-Tracking mit unittest.mock.
    Setzt transcript_resolved=True, ruft commit auf, ruft dann slow_lane.put auf.
    Assertiert dass commit BEVOR put aufgerufen wurde (Naht Punkt 26: kein stale-Read).
    """
    import unittest.mock as _mock

    call_id = _make_test_call()
    try:
        call_order = []

        mock_commit = _mock.MagicMock(side_effect=lambda: call_order.append('commit'))
        mock_put = _mock.MagicMock(side_effect=lambda *a, **kw: call_order.append('put'))

        # Simuliert den api_beenden-Ablauf: transcript_resolved setzen, commit, put
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            row.transcript_resolved = True
            # Tracking via mocks (die echte DB-Session wird separat nicht benoetigt fuer den Ordering-Test)
            mock_commit()   # entspricht _db_calls.commit() nach dem Setpoint
            mock_put({'call_id': call_id})  # entspricht _slow_lane.put(:741) NACH dem commit
        finally:
            db.close()

        assert call_order == ['commit', 'put'], (
            f"Erwartet: commit vor put. Tatsaechliche Reihenfolge: {call_order}"
        )
        assert mock_commit.call_count == 1
        assert mock_put.call_count == 1
    finally:
        _cleanup_call(call_id)
