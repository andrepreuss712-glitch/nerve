"""
tests/test_slowlane_callid_defensive.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.CALLID Plan 03 — urspruenglich: defensiver Backstop + flush_to_db A1-GUC-Klammer.
AKTUALISIERT: Phase 08.23.2.PERSID Plan 02 (F2-Stilllegung, PERSID Req 8).

F2-Stilllegung (PERSID Req 8): _persist_event_ref setzt 'not_gradable' fuer ALLE 'pending'-Events
direkt nach dem Idempotenz-Skip, VOR Confidence-Gate/grade_handling/Backstop.

Konsequenz:
  (a) Backstop-Test (V-CI-4): Event mit nicht-aufloesbarem Tenant bekommt jetzt 'not_gradable'
      (nicht mehr 'failed' — F2-Stilllegung greift vorher). Kein [CALLID-ALARM] mehr.
      Backward-Beleg: Event ist terminal und blockiert _pending_events nicht (Ziel bleibt gleich).
  (b) flush-mit-GUC (V-CI-5): flush_to_db schreibt KEINE abstain_log-Row mehr (F2-Pfad).
      Test aktualisiert: prueft dass das Event 'not_gradable' und abstain_log LEER bleibt.

Echte DB-Row-Assertionen gegen REAL-PG (db_session, skip ohne TEST_DATABASE_URL).
Committende Tests raeumen ihre Rows via cleanup_rows.
"""
import uuid
from datetime import datetime, timezone

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _seed_call(db, tenant):
    from database.models import Call
    cid = str(uuid.uuid4())
    db.add(Call(id=cid, user_id=1, tenant_id=tenant, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), transcript_storage='none'))
    db.commit()
    return cid


def _seed_event(db, call_id):
    """pending intent_event (confidence=None -> Tor 1 skippt -> Abstain-Pfad erreichbar).
    call_id MUSS auf eine echte calls.id zeigen (intent_event.call_id ist NOT NULL ab Deploy 2 / 0025).
    Der Backstop wird ueber einen Call mit tenant_id=NULL erreicht (nicht mehr via call_id=NULL)."""
    from database.models import IntentEvent
    ev = IntentEvent(
        session_id=f"callid-sl-{uuid.uuid4().hex[:10]}",
        call_id=call_id,
        mode='cold_call',
        intent_type='echter_einwand',
        timestamp=datetime.now(timezone.utc),
        handling_status='pending',
        confidence=None,   # Tor 1 (D-03) skippt -> kein 'failed' dort; Abstain via grade_handling=None
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev.event_id


def test_backstop_unresolvable_tenant_sets_not_gradable(db_session, monkeypatch, capsys):
    """PERSID Req 8 Update (F2-Stilllegung): Event mit nicht-aufloesbarem Tenant bekommt
    'not_gradable' (F2 greift VOR dem Backstop/grade_handling).

    Vorher (CALLID Plan 03): handling_status='failed' + [CALLID-ALARM].
    Jetzt (PERSID Plan 02): handling_status='not_gradable' + kein [CALLID-ALARM]
    (F2-Terminal ist VOR dem CALLID-Backstop).

    Das Kern-Ziel bleibt: Event ist TERMINAL und blockiert _pending_events NICHT.
    """
    import services.slow_lane as sl
    from database.models import IntentEvent, AbstainLog

    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid = _seed_call(db_session, tenant=None)
    eid = _seed_event(db_session, call_id=cid)
    try:
        sl._persist_event_ref({'event_id': eid}, db_session)
        db_session.commit()

        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert row.handling_status == 'not_gradable', (
            f"Erwartet 'not_gradable' (F2-Stilllegung), bekam '{row.handling_status}'"
        )
        assert row.handling_status != 'pending'  # kein H-3-Endlos-Re-Queue

        # KEIN abstain_log (F2 tritt VOR dem Abstain-Pfad auf)
        n_abstain = db_session.query(AbstainLog).filter(AbstainLog.event_id == eid).count()
        assert n_abstain == 0, "F2-Stilllegung: kein abstain_log (nicht-erreichbarer Abstain-Pfad)"
    finally:
        cleanup_rows(db_session, {"public.intent_event": [eid], "public.calls": [cid]})


def test_flush_to_db_sets_not_gradable_no_abstain_log(db_session, monkeypatch):
    """PERSID Req 8 Update (F2-Stilllegung): flush_to_db schreibt KEINE abstain_log-Row mehr.
    F2-Terminal greift in _persist_event_ref VOR dem Abstain-Pfad -> Event bekommt 'not_gradable'.

    Vorher (CALLID Plan 03, V-CI-5): flush_to_db schreibt abstain_log-Row mit GUC.
    Jetzt (PERSID Plan 02): Event = 'not_gradable', abstain_log = leer.
    Die A1-GUC-Klammer in flush_to_db bleibt (defensiver Schutz falls abstain-Pfad reaktiviert wird).
    """
    import services.slow_lane as sl
    from services.slow_lane import slow_lane
    from database.db import set_current_tenant
    from database.models import IntentEvent, AbstainLog
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid = _seed_call(db_session, tenant)
    eid = _seed_event(db_session, call_id=cid)

    try:
        slow_lane.put({'event_id': eid})
        drained = sl.flush_to_db()
        assert drained >= 1

        # Event muss 'not_gradable' sein (F2-Terminal)
        set_current_tenant(str(tenant))
        db_session.rollback()
        row = db_session.query(IntentEvent).filter_by(event_id=eid).first()
        assert row is not None
        assert row.handling_status == 'not_gradable', (
            f"Erwartet 'not_gradable' (F2-Stilllegung), bekam '{row.handling_status}'"
        )

        # KEIN abstain_log (F2-Pfad: grade_handling wird nicht erreicht)
        n_abstain = db_session.query(AbstainLog).filter(AbstainLog.event_id == eid).count()
        assert n_abstain == 0, "F2-Stilllegung: kein abstain_log (Abstain-Pfad nicht erreichbar)"
    finally:
        set_current_tenant(str(tenant))
        db_session.rollback()
        cleanup_rows(db_session,
                     {"public.abstain_log": [],
                      "public.intent_event": [eid],
                      "public.calls": [cid]},
                     tenant=tenant)
