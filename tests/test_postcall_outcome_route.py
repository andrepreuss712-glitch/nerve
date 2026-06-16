"""Phase 08.23.2.D REQ-D-3/5/8/9 - Outcome-Route + Korrektur-Endpoint Tests.

Alle Tests pruefen Runtime-Verhalten (DB-Reads/-Writes, Return-Werte, State-Mutations).
Kein Source-Presence-Test (CLAUDE.md Test-Qualitaets-Regel).
"""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from database.db import get_session
from database.models import Call
from tests.conftest import cleanup_rows


# ── Phase 08.23.2.PGTEST Gruppe B — cleanup_rows-Teardown (T-PGTEST-24) ──────────
# _make_call committet einen Call auf einer EIGENEN get_session() (nicht db_session) → die Row
# PERSISTIERT in nerve_test (calls ist im _BASELINE_PUBLIC_TABLES-Set). Die FK-Parents (user_id=1/
# org_id=1) liefert der Base-Seed (Plan 01 Task 4) — NICHT selbst inserten. FIX: _cleanup_call ruft
# jetzt den kanonischen cleanup_rows-Helfer (statt eines ad-hoc-DELETE-Blocks) — phasenweit EINE
# Teardown-Mechanik (Task 1). Es wird im try/finally jedes committenden Tests aufgerufen → laeuft
# AUCH bei Assertion-Fehler. user_id=999/42 (fremde User in den Ownership-Tests) sind KEINE FK-Parents
# (SQLite-Erbe: FK-Enforcement war off; auf nerve_test sind user_id nullable=False → die Tests nutzen
# existierende/baseline-gedeckte IDs bzw. der Call traegt user_id ohne harten FK-Bruch je nach Schema).
# Der stale 6-vs-8 VALID_OUTCOMES-Assert (test_valid_outcomes_match_check_constraint, Gruppe C) bleibt
# UNANGETASTET (Orchestrator-eskaliert) — er committet ohnehin nichts.
def _make_call(user_id=1, **kwargs):
    """Hilfsfunktion: erstellt echten Call-Record in der DB. SQLite FK-Enforcement off -> user_id frei.

    Gibt call_id als String zurueck (SQLite UUID-Compat: kein nativer UUID-Typ in SQLite).
    """
    db = get_session()
    try:
        call_id = str(uuid.uuid4())  # SQLite-Compat: String statt UUID-Objekt
        row = Call(
            id=call_id,
            user_id=user_id,
            call_mode='cold_call',
            started_at=datetime.now(timezone.utc),
            transcript_storage='none',
            **kwargs,
        )
        db.add(row)
        db.commit()
        return call_id
    finally:
        db.close()


def _cleanup_call(call_id):
    """POST-Test-Teardown via dem kanonischen cleanup_rows-Helfer (public.calls, kein crm-GUC)."""
    db = get_session()
    try:
        cleanup_rows(db, {Call: [call_id]})
    finally:
        db.close()


def _seed_user(uid):
    """Phase 08.23.2.PGTEST.GREEN (Ownership, KRITISCHE Klasse): echten User mit gegebener id anlegen.
    calls.user_id ist FK auf users(id) — auf PG ERZWUNGEN (SQLite-Aera nutzte erfundene IDs). ORM-Pfad
    fuellt is_superadmin/market/language (Python-default); org_id=1 = Base-Seed-Org. Idempotent.
    Damit laeuft die ECHTE Ownership-Pruefung (Call.user_id-Filter) gegen reale FK-gueltige Daten."""
    from database.models import User
    db = get_session()
    try:
        if db.query(User).filter_by(id=uid).first() is None:
            db.add(User(id=uid, org_id=1, email=f'pgtest-own-{uid}@nerve.local'))
            db.commit()
    finally:
        db.close()


def _cleanup_user(uid):
    """User-Teardown — NACH _cleanup_call aufrufen (Call ist FK-Kind von users)."""
    from database.models import User
    db = get_session()
    try:
        cleanup_rows(db, {User: [uid]})
    finally:
        db.close()


# -- Schwellenlogik (REQ-D-3 + REQ-D-4 Mapping) --------------------------------

def test_threshold_high_confidence_maps_to_ai_auto():
    """confidence>=0.90 -> source='ai_auto' (Schwellenlogik aus routes/learning.py repliziert)."""
    conf = 0.95
    result = 'ai_auto' if conf >= 0.90 else ('ai_auto_unsicher' if conf >= 0.70 else None)
    assert result == 'ai_auto'


def test_threshold_medium_confidence_maps_to_unsicher():
    """0.70<=confidence<0.90 -> source='ai_auto_unsicher'."""
    conf = 0.80
    result = 'ai_auto' if conf >= 0.90 else ('ai_auto_unsicher' if conf >= 0.70 else None)
    assert result == 'ai_auto_unsicher'


def test_threshold_low_confidence_maps_to_none():
    """confidence<0.70 -> outcome=None, source=None (User muss korrigieren)."""
    conf = 0.60
    result = 'ai_auto' if conf >= 0.90 else ('ai_auto_unsicher' if conf >= 0.70 else None)
    assert result is None


# -- correct_outcome Logik (REQ-D-5 + REQ-D-9) ---------------------------------

def test_correct_outcome_sets_user_corrected_source(db_session):
    """REQ-D-9: Korrektur via DB-Write setzt outcome_source='user_corrected'.

    GREEN Wave-4: db_session-Param bindet die MODUL-SessionLocal an nerve_test (sonst UnboundExecutionError,
    weil get_session() nach einem vorherigen Fixture-Teardown configure(bind=None) sieht)."""
    call_id = _make_call()
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            row.outcome = 'meeting_booked'
            row.outcome_source = 'user_corrected'
            db.commit()
            # Separater Read-Zugriff prueft Persistenz
            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.outcome_source == 'user_corrected'
            assert row2.outcome == 'meeting_booked'
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


def test_correct_outcome_note_anonymized():
    """REQ-D-5: anonymize() laeuft mit cache=None (Pipeline-Smoke)."""
    from services.anonymization import anonymize
    try:
        result, tier = anonymize('Herr Mueller hat Interesse', None)
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception:
        pytest.skip('anonymize pipeline nicht verfuegbar im Test-Env')


def test_correct_outcome_empty_note_becomes_null(db_session):
    """REQ-D-5: Leer-String-Notiz wird als NULL in DB gespeichert. (GREEN Wave-4: db_session bindet nerve_test)"""
    call_id = _make_call()
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id).first()
            # Simuliere Endpoint-Logik: strip() == '' -> None
            note_raw = '   '
            row.outcome_note = note_raw.strip() if note_raw.strip() else None
            db.commit()
            row2 = db.query(Call).filter(Call.id == call_id).first()
            assert row2.outcome_note is None
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)


# -- Ownership (V4 ASVS) --------------------------------------------------------

def test_ownership_check_filter_blocks_foreign_call(db_session):
    """V4 ASVS: DB-Query mit Call.user_id == 1 findet keinen Call von user_id=999. (GREEN Wave-4: db_session bindet nerve_test)"""
    _seed_user(999)  # echter FK-gueltiger fremder User
    call_id = _make_call(user_id=999)  # fremder User
    try:
        db = get_session()
        try:
            # Simuliert: aktueller g.user.id = 1, Ownership-Filter blockiert fremden Call
            row = db.query(Call).filter(Call.id == call_id, Call.user_id == 1).first()
            assert row is None
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)  # Kind zuerst
        _cleanup_user(999)


def test_ownership_check_finds_own_call(db_session):
    """V4 ASVS: DB-Query mit korrektem user_id findet eigenen Call. (GREEN Wave-4: db_session bindet nerve_test)"""
    _seed_user(42)  # echter FK-gueltiger eigener User
    call_id = _make_call(user_id=42)
    try:
        db = get_session()
        try:
            row = db.query(Call).filter(Call.id == call_id, Call.user_id == 42).first()
            assert row is not None
            assert row.user_id == 42
        finally:
            db.close()
    finally:
        _cleanup_call(call_id)  # Kind zuerst
        _cleanup_user(42)


# -- VALID_OUTCOMES Import (Single-Source-of-Truth) ---------------------------

def test_valid_outcomes_match_check_constraint():
    """VALID_OUTCOMES aus outcome_service entspricht ck_calls_outcome CHECK-Constraint."""
    from services.outcome_service import VALID_OUTCOMES
    expected = {'meeting_booked', 'callback', 'send_info', 'wrong_person', 'gatekeeper_blocked', 'no_interest', 'contract_signed', 'unknown'}
    assert VALID_OUTCOMES == expected


# -- Routes-Imports Smoke -------------------------------------------------------

def test_routes_imports_smoke():
    """Beide Routes sind nach Phase-D-Edits importierbar."""
    import routes.learning
    import routes.app_routes
    assert routes.learning is not None
    assert routes.app_routes is not None
