"""
tests/test_intent_event_writer.py
────────────────────────────────────────────────────────────────────
TAXO1-Welle 4 — Unit-Tests fuer die EINE gekapselte Schreibstelle
services.intent_event_writer.emit_intent_event.

Integration-Assertion (CLAUDE.md Test-Qualitaets-Regel): echte INSERTs gegen
nerve_test + Assertion auf die geschriebene Row / payload_jsonb-Felder; KEIN
Source-Presence. Committende Tests raeumen ihre Rows via cleanup_rows weg
(Baseline-Sauberkeit, Phase 08.23.2.PGTEST).

Server-seitig via pytest (kein Local-Dev). Sauberer Skip wenn DB-Fixture fehlt.
"""

import uuid

import pytest

from database.models import IntentEvent
from services.intent_event_writer import emit_intent_event
from services.intent_taxonomy import TAXONOMY_VERSION


def _sid():
    return f"test-iew-{uuid.uuid4().hex[:12]}"


def test_emit_inserts_row_with_payload(db_session):
    """Test 1: emit schreibt EINE Zeile; payload traegt taxonomy_version, source,
    speaker_role, speaker_id, abstained=False; handling_score_numeric bleibt NULL."""
    from tests.conftest import cleanup_rows

    sid = _sid()
    eid = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='echter_einwand',
        phase=2, source='llm_inferred', confidence=0.7,
        speaker_role='kunde', speaker_id='local', user_id=1, org_id=1,
    )
    assert isinstance(eid, int) and eid > 0
    try:
        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert row.intent_type == 'echter_einwand'
        assert row.mode == 'cold_call'
        assert row.phase == 2
        assert abs((row.confidence or 0) - 0.7) < 1e-6
        assert row.handling_score_numeric is None  # REQ 2 — kein Scoring
        pj = row.payload_jsonb or {}
        assert pj.get('taxonomy_version') == TAXONOMY_VERSION
        assert pj.get('source') == 'llm_inferred'
        assert pj.get('speaker_role') == 'kunde'
        assert pj.get('speaker_id') == 'local'
        assert pj.get('abstained') is False
    finally:
        cleanup_rows(db_session, {IntentEvent: [eid]})


def test_emit_accepts_custom_objection(db_session):
    """Test 2: custom_objection_* wird akzeptiert (Praefix), Insert erfolgt."""
    from tests.conftest import cleanup_rows

    sid = _sid()
    eid = emit_intent_event(
        session_id=sid, mode='meeting', intent_type='custom_objection_preis',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
    )
    assert eid > 0
    try:
        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert row.intent_type == 'custom_objection_preis'
    finally:
        cleanup_rows(db_session, {IntentEvent: [eid]})


def test_emit_rejects_invalid_intent_type(db_session):
    """Test 3: ungueltiger intent_type (kein Kern, kein Praefix) → ValueError,
    KEIN Insert (dokumentierte Entscheidung: harter Fehler statt stiller Fallback)."""
    before = db_session.query(IntentEvent).count()
    with pytest.raises(ValueError):
        emit_intent_event(
            session_id=_sid(), mode='cold_call', intent_type='quatsch_unbekannt',
            source='llm_inferred', speaker_role='kunde', speaker_id='local',
        )
    db_session.rollback()
    after = db_session.query(IntentEvent).count()
    assert after == before  # kein ungueltiger intent_type in DB


def test_emit_abstain_low_conf_written(db_session):
    """Test 4: abstain/low-conf → Zeile MIT abstained=True + confidence (K4: nicht droppen)."""
    from tests.conftest import cleanup_rows

    eid = emit_intent_event(
        session_id=_sid(), mode='meeting', intent_type='info_frage',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
        confidence=0.40, abstained=True,
    )
    assert eid > 0
    try:
        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert (row.payload_jsonb or {}).get('abstained') is True
        assert abs((row.confidence or 0) - 0.40) < 1e-6
    finally:
        cleanup_rows(db_session, {IntentEvent: [eid]})


def test_two_emits_two_inserts_no_update(db_session):
    """Test 5: zwei Aufrufe → zwei INSERTs, KEIN UPDATE einer bestehenden Zeile (Bau-Regel 1)."""
    from tests.conftest import cleanup_rows

    sid = _sid()
    eid1 = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='vorwand',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
    )
    eid2 = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='aufschub',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
    )
    assert eid1 != eid2  # zwei distinkte Zeilen, kein Overwrite
    try:
        r1 = db_session.query(IntentEvent).filter_by(event_id=eid1).one()
        r2 = db_session.query(IntentEvent).filter_by(event_id=eid2).one()
        assert r1.intent_type == 'vorwand'      # erste Zeile UNVERAENDERT
        assert r2.intent_type == 'aufschub'
    finally:
        cleanup_rows(db_session, {IntentEvent: [eid1, eid2]})


def test_shared_interaction_id_two_rows(db_session):
    """Test 6: zwei Aufrufe mit DERSELBEN interaction_id (gleicher Moment) → zwei
    Zeilen mit identischer interaction_id-Spalte; ohne interaction_id bleibt NULL."""
    from tests.conftest import cleanup_rows

    sid = _sid()
    iid = str(uuid.uuid4())
    eid_a = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='echter_einwand',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
        interaction_id=iid,
    )
    eid_b = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='vorwand',
        source='ui_asserted', speaker_role='kunde', speaker_id='local',
        interaction_id=iid,
    )
    eid_none = emit_intent_event(
        session_id=sid, mode='cold_call', intent_type='info_frage',
        source='llm_inferred', speaker_role='kunde', speaker_id='local',
    )
    try:
        ra = db_session.query(IntentEvent).filter_by(event_id=eid_a).one()
        rb = db_session.query(IntentEvent).filter_by(event_id=eid_b).one()
        rn = db_session.query(IntentEvent).filter_by(event_id=eid_none).one()
        assert str(ra.interaction_id) == iid
        assert str(rb.interaction_id) == iid       # geteilt ueber Lanes desselben Moments
        assert rn.interaction_id is None           # optional/nullable, kein Crash
    finally:
        cleanup_rows(db_session, {IntentEvent: [eid_a, eid_b, eid_none]})
