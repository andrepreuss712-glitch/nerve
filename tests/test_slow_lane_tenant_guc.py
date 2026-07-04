"""Phase 08.23.2.TENANT-FOUND Plan 03 — Slow-Lane-Integration: Abstain-Pfad schreibt abstain_log
MIT gesetztem Tenant-GUC (V-TF-5).
AKTUALISIERT: Phase 08.23.2.PERSID Plan 02 (F2-Stilllegung, PERSID Req 8).

F2-Stilllegung (PERSID Req 8): _persist_event_ref setzt 'not_gradable' fuer ALLE 'pending'-Events
VOR dem Abstain-Pfad. Konsequenz: der Abstain-Pfad ist nicht mehr erreichbar -> abstain_log-Rows
entstehen nicht mehr via _persist_event_ref. Test aktualisiert: prueft dass 'not_gradable' gesetzt
wird und abstain_log LEER bleibt (auch MIT gesetztem GUC).

Die A1-GUC-Klammer in slow_lane_consumer bleibt (defensiver Schutz), wird aber nicht mehr aktiv
durch den Abstain-Pfad ausgeloest.
"""
import uuid
from datetime import datetime, timezone

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _seed_call_and_event(db, tenant):
    """calls-Row (tenant_id=tenant, keine RLS) + pending intent_event (call_id -> calls,
    confidence=None damit Tor 1 NICHT 'failed' setzt). Gibt (call_id, event_id) zurueck."""
    from database.models import Call, IntentEvent
    cid = str(uuid.uuid4())
    db.add(Call(id=cid, user_id=1, tenant_id=tenant, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), transcript_storage='none'))
    db.commit()
    ev = IntentEvent(
        session_id=f"tf-sl-{uuid.uuid4().hex[:10]}",
        call_id=cid,
        mode='cold_call',
        intent_type='preis',
        timestamp=datetime.now(timezone.utc),
        handling_status='pending',
        confidence=None,   # Tor 1 (D-03) skippt -> kein 'failed', Abstain-Pfad erreichbar
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return cid, ev.event_id


def test_slow_lane_abstain_writes_abstain_log_with_guc(db_session, monkeypatch):
    """PERSID Req 8 Update (F2-Stilllegung): _persist_event_ref setzt 'not_gradable' fuer ALLE
    'pending'-Events VOR dem Abstain-Pfad. Keine abstain_log-Row entsteht — auch MIT gesetztem GUC.

    Vorher (TENANT-FOUND Plan 03, V-TF-5): abstain_log-Row bei gesetztem GUC.
    Jetzt (PERSID Plan 02): handling_status='not_gradable', abstain_log=leer (auch mit GUC).
    """
    import services.slow_lane as sl
    from database.db import set_current_tenant
    from database.models import IntentEvent, AbstainLog
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid, eid = _seed_call_and_event(db_session, tenant)
    try:
        # GUC setzen (A1-Klammer-Kontext) + _persist_event_ref aufrufen
        set_current_tenant(str(tenant))
        db_session.rollback()
        sl._persist_event_ref({'event_id': eid}, db_session)
        db_session.commit()

        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert row.handling_status == 'not_gradable', (
            f"Erwartet 'not_gradable' (F2-Stilllegung), bekam '{row.handling_status}'"
        )
        # Kein abstain_log — F2 greift VOR dem Abstain-Pfad
        n_abstain = db_session.query(AbstainLog).filter(AbstainLog.event_id == eid).count()
        assert n_abstain == 0, (
            "F2-Stilllegung: kein abstain_log (auch mit GUC — Abstain-Pfad nicht erreichbar)"
        )
    finally:
        set_current_tenant(str(tenant))
        db_session.rollback()
        cleanup_rows(db_session,
                     {"public.abstain_log": [],
                      "public.intent_event": [eid],
                      "public.calls": [cid]},
                     tenant=tenant)
