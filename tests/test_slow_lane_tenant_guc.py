"""Phase 08.23.2.TENANT-FOUND Plan 03 — Slow-Lane-Integration: Abstain-Pfad schreibt abstain_log
MIT gesetztem Tenant-GUC (V-TF-5).

Beweist integrativ (nicht nur unit), dass der Daemon-Abstain-Pfad (_persist_event_ref) mit
gesetztem app.tenant_id-GUC — wie ihn die Plan-03-A1-Consumer-Klammer setzt — eine abstain_log-Row
schreibt, die OHNE GUC fail-closed verworfen wuerde. Echte DB-Row-Assertion gegen REAL-PG
(db_session, skip ohne TEST_DATABASE_URL — KEIN MagicMock, sonst kein RLS-Beleg).

grade_handling/_find_next_advisor_utterance werden gezielt gemonkeypatcht (Abstention erzwingen
+ keine Live-Transkript-Infra noetig); der DB-Write laeuft scharf gegen Postgres (RLS-Beleg).
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
    """Mit gesetztem Tenant-GUC (A1-Klammer) schreibt der Abstain-Pfad eine abstain_log-Row
    (tenant_id == calls.tenant_id). Gegen-Beweis: ohne GUC wird derselbe Write fail-closed
    verworfen (Daemon-ohne-Fix-Zustand). V-TF-5."""
    import services.slow_lane as sl
    from database.db import set_current_tenant, clear_current_tenant
    from database.models import AbstainLog
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    # Abstention erzwingen: grade_handling -> None (score None = Tor 2 Abstain); keine Transkript-Infra.
    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid, eid = _seed_call_and_event(db_session, tenant)
    cid2, eid2 = _seed_call_and_event(db_session, tenant)
    written = []
    try:
        # ── POSITIV: GUC gesetzt (wie nach der A1-set_current_tenant-Klammer) -> Write greift ──
        set_current_tenant(str(tenant))
        db_session.rollback()   # frische TX -> after_begin setzt app.tenant_id=tenant
        sl._persist_event_ref({'event_id': eid}, db_session)
        db_session.commit()
        row = (db_session.query(AbstainLog)
               .filter(AbstainLog.event_id == eid).first())
        assert row is not None, ("V-TF-5: mit gesetztem GUC muss der Daemon-Abstain-Pfad eine "
                                 "abstain_log-Row schreiben (A1-Klammer greift).")
        assert str(row.tenant_id) == str(tenant), "tenant_id == calls.tenant_id (via _tenant_id_for)"
        written.append(str(row.id))

        # ── GEGEN-BEWEIS: ohne GUC (Daemon ohne A1-Fix) -> Write fail-closed verworfen ──
        clear_current_tenant()
        db_session.rollback()   # frische TX mit LEEREM GUC
        raised = False
        try:
            sl._persist_event_ref({'event_id': eid2}, db_session)
            db_session.commit()
        except Exception:
            raised = True
            db_session.rollback()
        assert raised, ("V-TF-5 Gegen-Beweis: ohne GUC haette FORCE-RLS WITH CHECK den "
                        "abstain_log-INSERT fail-closed abgewiesen (genau die M-4-Falle).")
        # unter korrektem GUC: die GUC-lose Row ist nachweislich ABWESEND
        set_current_tenant(str(tenant))
        db_session.rollback()
        assert (db_session.query(AbstainLog).filter(AbstainLog.event_id == eid2).first() is None), (
            "V-TF-5: der GUC-lose Abstain-Write darf KEINE abstain_log-Row hinterlassen haben.")
    finally:
        set_current_tenant(str(tenant))
        db_session.rollback()
        cleanup_rows(db_session,
                     {"public.abstain_log": written,
                      "public.intent_event": [eid, eid2],
                      "public.calls": [cid, cid2]},
                     tenant=tenant)
