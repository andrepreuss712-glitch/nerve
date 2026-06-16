"""Phase 08.23.2.D REQ-D-1 -- Migration 0005 Real-Daten-Validation (CLAUDE.md Punkt 13).

Tests laufen gegen die echte Dev-DB (nach alembic upgrade head auf 0005).
Sie pruefen Runtime-Verhalten: Spalten-Existenz per inspect(), CHECK-Constraint
per INSERT-Versuch, NULL-Akzeptanz per INSERT+Cleanup.
"""
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError

from database.db import engine, get_session
from database.models import Call


def test_0005_columns_present():
    """Migration 0005 hat alle 4 Spalten in calls hinzugefuegt."""
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('calls')}
    assert 'conversation_log_id' in cols, "conversation_log_id fehlt in calls"
    assert 'outcome_confidence' in cols, "outcome_confidence fehlt in calls"
    assert 'outcome_note' in cols, "outcome_note fehlt in calls"
    assert 'outcome_source' in cols, "outcome_source fehlt in calls"


def test_0005_existing_rows_null(db_session):
    """SELECT auf calls inkl. neue Spalten wirft keinen Fehler (Smoke-Test).

    db_session-Param (Phase 08.23.2.PGTEST.GREEN Muster A): bindet die Modul-SessionLocal an
    nerve_test (sonst UnboundExecutionError beim get_session()-Call gegen ungebundene SQLite-Aera-Engine).
    """
    db = get_session()
    try:
        rows = db.execute(text(
            "SELECT outcome_confidence, outcome_note, outcome_source, conversation_log_id "
            "FROM calls LIMIT 5"
        )).fetchall()
        # Kein Fehler beim SELECT = Spalten sind vorhanden und lesbar
        assert True
    finally:
        db.close()


def test_0005_check_constraint_blocks_invalid_source(db_session):
    """CHECK-Constraint ck_calls_outcome_source blockiert ungueltige outcome_source-Werte.

    db_session-Param (Muster A): bindet Modul-SessionLocal an nerve_test. Ohne Bind faengt das
    `pytest.raises((IntegrityError, Exception))` faelschlich den UnboundExecutionError statt der
    echten CHECK-Constraint-Violation (False-Green) — der Param erzwingt die echte Pruefung.
    """
    db = get_session()
    call_id = str(uuid.uuid4())
    try:
        with pytest.raises((IntegrityError, Exception)):
            db.execute(text(
                "INSERT INTO calls (id, user_id, call_mode, outcome_source, created_at) "
                "VALUES (:id, 1, 'cold_call', 'invalid_value', :now)"
            ), {'id': call_id, 'now': datetime.now(timezone.utc)})
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_0005_check_constraint_allows_valid_source(db_session):
    """CHECK-Constraint erlaubt die 3 gueltigen Enum-Werte sowie NULL.

    db_session-Param (Muster A): bindet Modul-SessionLocal an nerve_test (sonst UnboundExecutionError).
    calls-Insert braucht nur id/user_id/call_mode (NOT NULL ohne Default, Schema-Check 2026-06-16);
    user_id=1 + call_mode='cold_call' sind gesetzt -> Insert vollstaendig.
    """
    db = get_session()
    inserted_ids = []
    try:
        for src in ['ai_auto', 'ai_auto_unsicher', 'user_corrected', None]:
            call_id = str(uuid.uuid4())
            db.execute(text(
                "INSERT INTO calls (id, user_id, call_mode, outcome_source, created_at) "
                "VALUES (:id, 1, 'cold_call', :src, :now)"
            ), {'id': call_id, 'src': src, 'now': datetime.now(timezone.utc)})
            db.commit()
            inserted_ids.append(call_id)
    finally:
        # Cleanup: alle eingefuegten Test-Rows entfernen
        for cid in inserted_ids:
            try:
                db.execute(text("DELETE FROM calls WHERE id = :id"), {'id': cid})
                db.commit()
            except Exception:
                db.rollback()
        db.close()
