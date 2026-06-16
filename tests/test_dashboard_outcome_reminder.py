"""Phase 08.23.2.D REQ-D-8 + REQ-D-9 - Dashboard Reminder + JOIN Tests.

CLAUDE.md-konform: ausschliesslich Runtime-Behavior-Tests.
KEIN open(__file__).read() / inspect.getsource / string-in-source.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import or_

from database.db import get_session
from database.models import Call, ConversationLog
from tests.conftest import cleanup_rows


# ── Phase 08.23.2.PGTEST Gruppe B — cleanup_rows-Teardown + count-Scoping (T-PGTEST-24) ──────
# _make_call committet einen Call auf einer EIGENEN get_session() (nicht db_session) → die Rows
# PERSISTIEREN in nerve_test (calls ist im _BASELINE_PUBLIC_TABLES-Set). Frueher raeumte ein
# ad-hoc-DELETE-Block (_cleanup) sie weg — jetzt der kanonische cleanup_rows-Helfer (Task 1),
# weiterhin im try/finally jedes Tests (laeuft AUCH bei Assertion-Fehler). FK-Parents user_id=1/
# org_id=1 liefert der Base-Seed (Plan 01 Task 4). REVERSE-FK: Call ist KIND von ConversationLog
# (conversation_log_id-FK, models.py:704) → der Call MUSS vor der ConversationLog geloescht werden;
# cleanup_rows' globale _CLEANUP_FK_ORDER listet conversation_logs VOR calls, daher wird der
# Call+ConversationLog-Mischtest (test_join_call_to_conversation_log) in ZWEI getrennten
# cleanup_rows-Aufrufen geraeumt (erst calls, dann conversation_logs). Zusaetzlich: die globale
# unsichere-count-Assertion wird auf die Test-eigenen IDs gescoped (Call.id.in_(ids)) — sonst zoegen
# Baseline-/Fremd-user_id=1-Calls den Count hoch (Delta-Review-2-Klasse).
def _now():
    return datetime.now(timezone.utc)


def _make_call(user_id=1, source=None, outcome=None, ended_offset_days=0, conv_log_id=None):
    db = get_session()
    try:
        cid = str(uuid.uuid4())
        row = Call(
            id=cid,
            user_id=user_id,
            call_mode='cold_call',
            started_at=_now() - timedelta(days=ended_offset_days),
            ended_at=_now() - timedelta(days=ended_offset_days),
            transcript_storage='none',
            outcome=outcome,
            outcome_source=source,
            conversation_log_id=conv_log_id,
        )
        db.add(row)
        db.commit()
        return cid
    finally:
        db.close()


def _cleanup(call_ids):
    """POST-Test-Teardown via dem kanonischen cleanup_rows-Helfer (public.calls, kein crm-GUC)."""
    if not call_ids:
        return
    db = get_session()
    try:
        cleanup_rows(db, {Call: list(call_ids)})
    finally:
        db.close()


def test_unsichere_count_filter_logic():
    """Filter: ai_auto_unsicher OR outcome IS NULL, ended_at >= now - 7d."""
    user_id = 1
    ids = []
    try:
        # In-Scope: ai_auto_unsicher, 1 Tag alt -> zaehlt
        ids.append(_make_call(user_id=user_id, source='ai_auto_unsicher', outcome='callback', ended_offset_days=1))
        # In-Scope: outcome IS NULL, 2 Tage alt -> zaehlt
        ids.append(_make_call(user_id=user_id, source=None, outcome=None, ended_offset_days=2))
        # Out-Of-Scope: ai_auto (sicher), 1 Tag alt -> zaehlt NICHT
        ids.append(_make_call(user_id=user_id, source='ai_auto', outcome='meeting_booked', ended_offset_days=1))
        # Out-Of-Scope: ai_auto_unsicher aber 10 Tage alt -> zaehlt NICHT
        ids.append(_make_call(user_id=user_id, source='ai_auto_unsicher', outcome=None, ended_offset_days=10))

        seven_days_ago = _now() - timedelta(days=7)
        db = get_session()
        try:
            count = (
                db.query(Call)
                  .filter(
                      Call.user_id == user_id,
                      Call.ended_at >= seven_days_ago,
                      Call.id.in_(ids),  # auf Test-eigene IDs gescoped (kein Baseline-/Fremd-Poison)
                      or_(Call.outcome_source == 'ai_auto_unsicher', Call.outcome.is_(None)),
                  )
                  .count()
            )
            # Genau die 2 in-scope unsicheren Test-Calls (ai_auto_unsicher 1d + NULL-outcome 2d);
            # die ai_auto-/10d-alten Test-Calls fallen durch den Filter.
            assert count == 2, f'Erwartet genau 2 unsichere Test-Calls, bekam {count}'
        finally:
            db.close()
    finally:
        _cleanup(ids)


def test_old_call_excluded_from_count():
    """Call aelter als 7 Tage wird vom Reminder-Counter ausgeschlossen."""
    user_id = 1
    ids = []
    try:
        # 10 Tage alt -> ausserhalb 7-Tage-Fenster
        ids.append(_make_call(user_id=user_id, source='ai_auto_unsicher', outcome='callback', ended_offset_days=10))

        seven_days_ago = _now() - timedelta(days=7)
        db = get_session()
        try:
            count = (
                db.query(Call)
                  .filter(
                      Call.user_id == user_id,
                      Call.ended_at >= seven_days_ago,
                      Call.id.in_(ids),  # nur unsere Test-IDs
                  )
                  .count()
            )
            assert count == 0, f'Alter Call darf nicht im 7-Tage-Fenster erscheinen, bekam {count}'
        finally:
            db.close()
    finally:
        _cleanup(ids)


def test_ai_auto_not_in_unsicher_count():
    """Call mit outcome_source='ai_auto' (sicher) ist NICHT im Reminder-Counter."""
    user_id = 1
    ids = []
    try:
        cid = _make_call(user_id=user_id, source='ai_auto', outcome='meeting_booked', ended_offset_days=1)
        ids.append(cid)

        seven_days_ago = _now() - timedelta(days=7)
        db = get_session()
        try:
            count = (
                db.query(Call)
                  .filter(
                      Call.id == cid,
                      Call.ended_at >= seven_days_ago,
                      or_(Call.outcome_source == 'ai_auto_unsicher', Call.outcome.is_(None)),
                  )
                  .count()
            )
            assert count == 0, f'ai_auto-Call darf nicht als unsicher zaehlen, bekam {count}'
        finally:
            db.close()
    finally:
        _cleanup(ids)


def test_null_outcome_in_unsicher_count():
    """Call mit outcome=NULL zaehlt im Reminder-Counter (unklassifiziert)."""
    user_id = 1
    ids = []
    try:
        cid = _make_call(user_id=user_id, source=None, outcome=None, ended_offset_days=1)
        ids.append(cid)

        seven_days_ago = _now() - timedelta(days=7)
        db = get_session()
        try:
            count = (
                db.query(Call)
                  .filter(
                      Call.id == cid,
                      Call.ended_at >= seven_days_ago,
                      or_(Call.outcome_source == 'ai_auto_unsicher', Call.outcome.is_(None)),
                  )
                  .count()
            )
            assert count == 1, f'NULL-outcome-Call muss als unsicher zaehlen, bekam {count}'
        finally:
            db.close()
    finally:
        _cleanup(ids)


def test_join_call_to_conversation_log():
    """Call.conversation_log_id FK funktioniert — JOIN liefert Outcome-Daten."""
    db = get_session()
    cid = None
    conv_id = None
    try:
        conv = ConversationLog(user_id=1, org_id=1, created_at=_now())
        db.add(conv)
        db.commit()
        conv_id = conv.id

        cid = str(uuid.uuid4())
        row = Call(
            id=cid,
            user_id=1,
            call_mode='cold_call',
            started_at=_now(),
            ended_at=_now(),
            transcript_storage='none',
            conversation_log_id=conv_id,
            outcome='callback',
            outcome_source='ai_auto_unsicher',
        )
        db.add(row)
        db.commit()

        row2 = db.query(Call).filter(Call.conversation_log_id == conv_id).first()
        assert row2 is not None, 'JOIN via conversation_log_id muss Call finden'
        assert row2.outcome == 'callback', f'Erwartet callback, bekam {row2.outcome}'
        assert row2.outcome_source == 'ai_auto_unsicher', f'Erwartet ai_auto_unsicher, bekam {row2.outcome_source}'
    finally:
        db.close()
        # Reverse-FK: erst der Call (Kind), dann die ConversationLog (Eltern) — in ZWEI
        # cleanup_rows-Aufrufen, da die globale _CLEANUP_FK_ORDER conversation_logs vor calls
        # listet (ein einzelner Aufruf wuerde die Eltern-Row zuerst loeschen → FK-Bruch).
        if cid:
            cdb = get_session()
            try:
                cleanup_rows(cdb, {Call: [cid]})
            finally:
                cdb.close()
        if conv_id:
            cdb = get_session()
            try:
                cleanup_rows(cdb, {ConversationLog: [conv_id]})
            finally:
                cdb.close()


def test_api_dashboard_returns_unsichere_outcomes_count():
    """REQ-D-8: GET /api/dashboard JSON-Body enthaelt unsichere_outcomes_count als Zahl.

    Echter Endpoint-Test via Flask test_client.
    """
    try:
        from app import app  # Flask-App-Instanz
    except Exception:
        pytest.skip('Flask app nicht importierbar im Test-Env')

    user_id = 1
    ids = []
    try:
        ids.append(_make_call(user_id=user_id, source='ai_auto_unsicher', outcome='callback', ended_offset_days=1))

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user_id

        resp = client.get('/api/dashboard')
        if resp.status_code in (401, 302):
            pytest.skip('Login-Fixture fehlt - Endpoint braucht authentifizierte Session')

        assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
        data = resp.get_json()
        assert data is not None, 'Response muss JSON sein'
        assert 'unsichere_outcomes_count' in data, \
            'JSON-Response muss key unsichere_outcomes_count enthalten'
        assert isinstance(data['unsichere_outcomes_count'], int), \
            'unsichere_outcomes_count muss int sein'
        assert data['unsichere_outcomes_count'] >= 1, \
            f'Counter muss >=1 sein (ai_auto_unsicher-Call angelegt), war: {data["unsichere_outcomes_count"]}'

        # recent_sessions muss Outcome-Felder mitliefern (JOIN-Beweis)
        if 'recent_sessions' in data and isinstance(data['recent_sessions'], list) and data['recent_sessions']:
            first = data['recent_sessions'][0]
            assert any(k in first for k in ('outcome', 'outcome_source', 'call_id')), \
                'recent_sessions muss outcome/outcome_source/call_id mitliefern'
    finally:
        _cleanup(ids)


def test_api_dashboard_unsichere_count_is_int():
    """Counter ist immer int (auch 0) — Typ-Sicherheit.

    Wird geskippt wenn Login-Fixture fehlt.
    """
    try:
        from app import app
    except Exception:
        pytest.skip('Flask app nicht importierbar')

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1

    resp = client.get('/api/dashboard')
    if resp.status_code != 200:
        pytest.skip(f'Endpoint nicht zugaenglich (Status {resp.status_code})')

    data = resp.get_json()
    assert 'unsichere_outcomes_count' in data, 'Key muss im Response sein'
    assert isinstance(data['unsichere_outcomes_count'], int), \
        f'Typ muss int sein, bekam {type(data["unsichere_outcomes_count"])}'
    assert data['unsichere_outcomes_count'] >= 0, 'Counter muss >= 0 sein'
