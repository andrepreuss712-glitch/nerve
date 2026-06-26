"""
tests/test_slowlane_callid_defensive.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.CALLID Plan 03 — defensiver Backstop + flush_to_db A1-GUC-Klammer (CI-4/CI-5).

(a) Backstop: ein abstain-faehiges intent_event OHNE call_id (Tenant nicht ermittelbar) ->
    _persist_event_ref setzt handling_status='failed' (TERMINAL, kein 'pending', kein H-3-Re-Queue),
    schreibt KEIN abstain_log (kein fail-closed-Crash), loggt [CALLID-ALARM]. (V-CI-4)
(b) flush-mit-GUC: ein abstain-faehiges Item MIT gueltiger call_id (seeded calls.tenant_id) ->
    flush_to_db setzt PRO ITEM den Tenant-GUC und schreibt die abstain_log-Row (NICHT fail-closed). (V-CI-5)

Echte DB-Row-Assertionen gegen REAL-PG (db_session, skip ohne TEST_DATABASE_URL — KEIN Mock,
sonst kein RLS-Beleg). grade_handling/_find_next_advisor_utterance gemonkeypatcht (Abstention
erzwingen, keine Live-Transkript-Infra). Committende Tests raeumen ihre Rows via cleanup_rows.
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


def test_backstop_unresolvable_tenant_sets_failed_no_abstain_log(db_session, monkeypatch, capsys):
    """V-CI-4: abstain-faehiges Event, dessen Tenant NICHT aufloesbar ist -> _persist_event_ref setzt
    'failed' (terminal), KEIN abstain_log, lauter [CALLID-ALARM], KEIN 'pending' (H-3 re-queued nicht).

    AB CALLID Deploy 2 (Migration 0025) ist intent_event.call_id NOT NULL -> der Backstop wird NICHT
    mehr ueber call_id=NULL erreicht, sondern ueber eine GUELTIGE call_id, deren calls.tenant_id NULL ist
    -> _tenant_id_for liefert None. Der fail-closed-Schutz (kein abstain_log gegen FORCE RLS) bleibt
    identisch: nicht-aufloesbarer Tenant => terminal 'failed' + Alarm, kein Endlos-Loop."""
    import services.slow_lane as sl
    from database.models import IntentEvent, AbstainLog

    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)            # Abstention erzwingen
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid = _seed_call(db_session, tenant=None)     # calls.tenant_id IS NULL -> Tenant nicht aufloesbar
    eid = _seed_event(db_session, call_id=cid)    # gueltige call_id (NOT NULL erfuellt)
    try:
        sl._persist_event_ref({'event_id': eid}, db_session)
        db_session.commit()

        row = db_session.query(IntentEvent).filter_by(event_id=eid).one()
        assert row.handling_status == 'failed', (
            "Backstop: nicht-aufloesbarer Abstain muss TERMINAL 'failed' werden (nicht 'pending')")
        assert row.handling_status != 'pending'   # kein H-3-Endlos-Re-Queue

        # KEIN abstain_log fuer dieses Event (kein fail-closed INSERT-Versuch)
        n_abstain = db_session.query(AbstainLog).filter(AbstainLog.event_id == eid).count()
        assert n_abstain == 0, "Backstop darf KEIN abstain_log schreiben (fail-closed vermieden)"

        out = capsys.readouterr().out
        assert '[CALLID-ALARM]' in out, "Backstop muss LAUT alarmieren (sichtbar, nicht still)"
    finally:
        cleanup_rows(db_session, {"public.intent_event": [eid], "public.calls": [cid]})


def test_flush_to_db_writes_abstain_log_with_guc(db_session, monkeypatch):
    """V-CI-5: flush_to_db setzt PRO ITEM den Tenant-GUC (A1-Klammer, symmetrisch zum Consumer-Loop)
    und schreibt die abstain_log-Row bei gueltiger call_id — NICHT fail-closed (Shutdown-Flush-Pfad)."""
    import services.slow_lane as sl
    from services.slow_lane import slow_lane
    from database.db import set_current_tenant
    from database.models import AbstainLog
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    monkeypatch.setattr(sl, "grade_handling", lambda *a, **k: None)            # Abstention erzwingen
    monkeypatch.setattr(sl, "_find_next_advisor_utterance", lambda *a, **k: None)

    cid = _seed_call(db_session, tenant)
    eid = _seed_event(db_session, call_id=cid)

    written = []
    try:
        # Item in die ECHTE Slow-Lane-Queue legen; flush_to_db drained + benotet es (eigene Sessions,
        # nerve_test-gebunden via db_session-Fixture). Die A1-Klammer setzt den GUC pro Item.
        slow_lane.put({'event_id': eid})
        drained = sl.flush_to_db()
        assert drained >= 1

        # abstain_log-Row unter korrektem GUC lesen (FORCE RLS -> GUC noetig).
        set_current_tenant(str(tenant))
        db_session.rollback()
        row = (db_session.query(AbstainLog)
               .filter(AbstainLog.event_id == eid).first())
        assert row is not None, (
            "V-CI-5: flush_to_db muss die abstain_log-Row mit gesetztem GUC schreiben "
            "(A1-Klammer greift, kein fail-closed beim Shutdown-Flush).")
        assert str(row.tenant_id) == str(tenant), "tenant_id == calls.tenant_id (via _tenant_id_for)"
        written.append(str(row.id))
    finally:
        set_current_tenant(str(tenant))
        db_session.rollback()
        cleanup_rows(db_session,
                     {"public.abstain_log": written,
                      "public.intent_event": [eid],
                      "public.calls": [cid]},
                     tenant=tenant)
