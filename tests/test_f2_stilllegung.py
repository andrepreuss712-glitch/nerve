"""
tests/test_f2_stilllegung.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 02 — Welle 1, Task 1.
Waechter: F2-Stilllegung ('not_gradable'-Terminal in _persist_event_ref).

Integration-Assertions (CLAUDE.md Test-Qualitaets-Regel):
  Test 1: 'pending'-Event durch _persist_event_ref → handling_status='not_gradable'
          KEIN grade_handling/AbstainLog-INSERT laeuft.
  Test 2: Nach not_gradable zaehlt _pending_events dieses Event NICHT (drainet auf 0).
  Test 3: Event mit handling_status != 'pending' bleibt unveraendert (Idempotenz-Skip
          NACH der neuen Terminal-Setzung — bleibt immer noch vor not_gradable).

Server-seitig via pytest gegen REAL-PG nerve_test (db_session-Fixture skippt wenn DSN
fehlt). KEIN live/perf-Marker. Committende Tests raeumen ihre Rows via cleanup_rows weg
(Baseline-Sauberkeit, Phase 08.23.2.PGTEST).

D-10-Konformitaet: dieser Test wurde VOR der not_gradable-Implementierung committiert —
MUSS initial ROT sein (Test 1 faengt ohne die neue Terminal-Setzung nicht ab).
"""

import uuid
from datetime import datetime, timezone

import pytest

from database.models import IntentEvent, Call
from tests.conftest import cleanup_rows


def _seed_call(db):
    """calls-Row als FK-Ziel fuer intent_event.call_id (NOT NULL, Migration 0025)."""
    cid = str(uuid.uuid4())
    db.add(Call(id=cid, user_id=1, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), transcript_storage='none'))
    db.commit()
    return cid


def _seed_event(db, call_id, handling_status='pending', confidence=None):
    """Erzeugt eine IntentEvent-Row mit gegebenem handling_status."""
    sid = f"test-f2-{uuid.uuid4().hex[:12]}"
    ev = IntentEvent(
        session_id=sid,
        mode='cold_call',
        timestamp=datetime.now(timezone.utc),
        intent_type='preiseinwand',
        call_id=call_id,
        confidence=confidence,
        payload_jsonb={
            'source': 'test',
            'inference_basis': 'keyword',
            'taxonomy_version': '1.0',
            'abstained': False,
            'speaker_role': 'Kunde',
            'speaker_id': '1',
            'is_simulation': False,
            'origin_type': 'fast_lane',
            'triggering_text': 'zu teuer',
        },
        handling_status=handling_status,
    )
    db.add(ev)
    db.commit()
    return ev


@pytest.mark.usefixtures('_pgtest_base_seed')
def test_f2_persist_event_sets_not_gradable(db_session):
    """Test 1: _persist_event_ref setzt handling_status='not_gradable' fuer 'pending'-Events.
    KEIN grade_handling (kein Score), KEIN AbstainLog-INSERT.

    RED-Phase: ohne die neue Terminal-Setzung in _persist_event_ref landet der Event
    entweder bei 'scored'/'abstained'/'failed' — NICHT bei 'not_gradable'.
    """
    from services.slow_lane import _persist_event_ref
    from database.models import AbstainLog

    call_id = _seed_call(db_session)
    ev = _seed_event(db_session, call_id, handling_status='pending', confidence=0.95)
    event_id = ev.event_id

    # _persist_event_ref erwartet event_ref: dict mit 'event_id' + eine DB-Session.
    # ACHTUNG: _persist_event_ref macht IN-PLACE-UPDATE aber KEINEN Commit (Consumer committet).
    # Wir committen selbst nach dem Aufruf um das Ergebnis lesen zu koennen.
    _persist_event_ref({'event_id': event_id}, db_session)
    db_session.commit()

    # Nachher pruefen: handling_status muss 'not_gradable' sein
    db_session.expire(ev)
    reloaded = db_session.query(IntentEvent).filter(
        IntentEvent.event_id == event_id
    ).first()

    # Test-Assertion (wird ROT ohne die F2-Implementierung):
    assert reloaded is not None
    assert reloaded.handling_status == 'not_gradable', (
        f"Erwartet 'not_gradable', bekam '{reloaded.handling_status}'. "
        "F2-Stilllegung noch nicht implementiert in _persist_event_ref."
    )
    # Kein Score gesetzt:
    assert reloaded.handling_score_numeric is None, (
        "handling_score_numeric muss NULL bleiben (kein grade_handling-Pfad)"
    )
    # Kein AbstainLog-INSERT:
    abstain_count = db_session.query(AbstainLog).filter(
        AbstainLog.event_id == event_id
    ).count()
    assert abstain_count == 0, (
        f"Kein AbstainLog erwartet, aber {abstain_count} gefunden"
    )

    # Cleanup
    cleanup_rows(db_session, {
        'public.abstain_log': [],
        'public.intent_event': [event_id],
        'public.calls': [call_id],
    })


@pytest.mark.usefixtures('_pgtest_base_seed')
def test_f2_not_gradable_drains_pending_events(db_session):
    """Test 2: nach not_gradable zaehlt _pending_events dieses Event NICHT (drainet auf 0).

    _pending_events zaehlt NUR handling_status='pending'. not_gradable ist terminal
    (wie scored/abstained/failed) -> wird NICHT gezaehlt.
    """
    from services.slow_lane import _persist_event_ref, _pending_events

    call_id = _seed_call(db_session)
    ev = _seed_event(db_session, call_id, handling_status='pending', confidence=0.9)
    event_id = ev.event_id

    # Vor der Verarbeitung: 1 pending Event
    count_before = _pending_events(call_id, db_session)
    assert count_before == 1, f"Erwartet 1 pending, bekam {count_before}"

    # _persist_event_ref aufrufen
    _persist_event_ref({'event_id': event_id}, db_session)
    db_session.commit()

    # Nach not_gradable: 0 pending Events (drainet auf 0)
    count_after = _pending_events(call_id, db_session)
    assert count_after == 0, (
        f"Erwartet 0 pending nach not_gradable, bekam {count_after}. "
        "not_gradable ist terminal — _pending_events darf es NICHT mitzaehlen."
    )

    # Cleanup
    cleanup_rows(db_session, {
        'public.intent_event': [event_id],
        'public.calls': [call_id],
    })


@pytest.mark.usefixtures('_pgtest_base_seed')
def test_f2_idempotenz_non_pending_bleibt_unveraendert(db_session):
    """Test 3: Event mit handling_status != 'pending' bleibt unveraendert.

    Der Idempotenz-Skip (:230) greift VOR der neuen Terminal-Setzung —
    ein bereits 'scored'/'abstained'/'failed'/'not_gradable'-Event wird NICHT
    erneut verarbeitet.
    """
    from services.slow_lane import _persist_event_ref

    call_id = _seed_call(db_session)

    for status in ('scored', 'abstained', 'failed', 'not_gradable'):
        ev = _seed_event(db_session, call_id, handling_status=status)
        event_id = ev.event_id

        _persist_event_ref({'event_id': event_id}, db_session)
        db_session.commit()

        db_session.expire(ev)
        reloaded = db_session.query(IntentEvent).filter(
            IntentEvent.event_id == event_id
        ).first()
        assert reloaded.handling_status == status, (
            f"handling_status wurde fuer '{status}' auf '{reloaded.handling_status}' "
            f"veraendert — Idempotenz-Skip muss greifen"
        )

        # Cleanup pro Iteration
        cleanup_rows(db_session, {
            'public.intent_event': [event_id],
        })

    cleanup_rows(db_session, {
        'public.calls': [call_id],
    })
