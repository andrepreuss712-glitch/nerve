"""Regressions-Test: audit_log ist UPDATE/DELETE-unveraenderlich (Postgres-Trigger, Migration 0026).

Beweist Runtime-Verhalten gegen REAL-PG (db_session, skip ohne TEST_DATABASE_URL — SQLite hat den
Trigger nicht -> waere False-Green). Der Trigger `trg_audit_log_immutable` (BEFORE UPDATE OR DELETE)
lehnt jeden UPDATE und DELETE mit `RAISE EXCEPTION 'audit_log is immutable'` ab.

WARUM ins Deploy-Gate (Andre-Direktive): der frueher im App-Start stehende SQLite-Dialekt-Trigger warf
auf Postgres still einen Syntaxfehler -> 0 Trigger -> das Unveraenderlichkeits-Siegel fehlte unbemerkt.
Dieser Test verankert es, damit es nie wieder still wegfaellt.

KEIN commit/cleanup: die Test-Zeile wird nur geflusht (NIE committet) -> der db_session-Teardown-rollback
verwirft sie. Cleanup waere ohnehin unmoeglich (der Trigger blockt DELETE). Pro verbotener Anweisung ein
SAVEPOINT (begin_nested) -> die Trigger-Exception rollt nur den Savepoint zurueck, die aeussere TX (mit
der pending INSERT-Zeile) bleibt nutzbar.
"""
import uuid

import pytest
from sqlalchemy import text


def _insert_audit_row(db):
    """Eine audit_log-Zeile in die laufende TX flushen (NICHT committen). Gibt die id zurueck.
    Kein INSERT-Trigger -> der INSERT geht durch; nur UPDATE/DELETE sind gesperrt."""
    from database.models import AuditLog
    ev = AuditLog(action=f"test-immutable-{uuid.uuid4().hex[:10]}")
    db.add(ev)
    db.flush()
    return ev.id


def test_audit_log_update_rejected(db_session):
    aid = _insert_audit_row(db_session)
    sp = db_session.begin_nested()
    with pytest.raises(Exception) as exc:
        db_session.execute(
            text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"), {"id": aid})
    sp.rollback()
    assert 'immutable' in str(exc.value).lower(), (
        f"UPDATE muss vom Immutability-Trigger abgelehnt werden (RAISE EXCEPTION), war: {exc.value!r}")
    db_session.rollback()  # geflushte INSERT-Zeile verwerfen (kein commit, kein Leak)


def test_audit_log_delete_rejected(db_session):
    aid = _insert_audit_row(db_session)
    sp = db_session.begin_nested()
    with pytest.raises(Exception) as exc:
        db_session.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": aid})
    sp.rollback()
    assert 'immutable' in str(exc.value).lower(), (
        f"DELETE muss vom Immutability-Trigger abgelehnt werden (RAISE EXCEPTION), war: {exc.value!r}")
    db_session.rollback()
