"""Phase 08.23.2.TENANT-FOUND Plan 03 — M-4 RLS-GUC-Falle fuer abstain_log (Negativ/Positiv).

abstain_log bekommt mit Plan 02 (Migration 0022 gefaltet) FORCE ROW LEVEL SECURITY +
tenant_isolation + tenant_id NOT NULL. Dieser Test beweist die M-4-Falle 1:1 wie
test_rubric_score_schema.py:195-269, aber fuer AbstainLog:

(a) NEGATIV: ohne gesetzten Tenant-GUC (clear_current_tenant — wie der Daemon-Thread ohne
    Request-Context VOR dem Plan-03-A1-Fix) -> ein INSERT mit gesetztem tenant_id wird von
    WITH CHECK fail-closed ABGELEHNT (V-TF-3).
(b) POSITIV: nach set_current_tenant(<tenant>) -> derselbe INSERT geht durch + ist lesbar;
    die GUC-lose Negativ-Row ist nachweislich ABWESEND (echte Absenz, nicht RLS-Read-Filter) (V-TF-4).

abstain_log.event_id ist NOT NULL FK -> intent_event.event_id (CASCADE): der Test seedet eine
gueltige intent_event-Row (intent_event hat KEINE RLS -> GUC-frei seedbar) und raeumt sie
reverse-FK-clean (abstain_log -> intent_event) wieder weg.

Server-seitig gegen Postgres (skip ohne TEST_DATABASE_URL -> kein False-Green; SQLite hat kein RLS).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _seed_intent_event(db):
    """Gueltige intent_event-Row seeden (NOT-NULL: session_id/mode/intent_type; timestamp/
    payload_jsonb/handling_status haben Defaults). intent_event hat KEINE RLS -> GUC-frei.
    Gibt event_id (int) zurueck."""
    from database.models import IntentEvent
    ev = IntentEvent(
        session_id=f"tf-rls-{uuid.uuid4().hex[:10]}",
        mode='cold_call',
        intent_type='preis',
        timestamp=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev.event_id


def test_abstain_log_rls_requires_tenant_guc(db_session):
    """M-4 (teuerste stille Regression): FORCE ROW LEVEL SECURITY + WITH CHECK greift AUCH gegen
    den eigenen Slow-Lane-Daemon (Plan 03, ohne Request-Context -> GUC NULL -> INSERT lautlos
    abgelehnt -> abstain_log nie geschrieben). Beweist: der Daemon MUSS den GUC setzen (Plan-03-A1)."""
    from database.db import set_current_tenant, clear_current_tenant
    from database.models import AbstainLog
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    eid = _seed_intent_event(db_session)
    id_neg, id_pos = str(uuid.uuid4()), str(uuid.uuid4())
    written = []
    try:
        # ── (a) NEGATIV: GUC leer (Daemon ohne Request-Context) -> WITH CHECK weist ab ──
        # (TX-Mechanik db.py:73-89: der GUC wird bei TX-BEGIN aus dem contextvar gesetzt.
        #  clear_current_tenant() leert nur den contextvar fuer KUENFTIGE TX -> nach dem Clear
        #  die laufende TX per rollback beenden -> die naechste TX laeuft mit leerem GUC.)
        clear_current_tenant()
        db_session.rollback()
        guc = db_session.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar()
        assert guc in (None, ''), (
            f"Negativ-Bein-Vorbedingung: app.tenant_id-GUC MUSS leer sein, war {guc!r} "
            "(sonst stellt der Test die kein-Tenant-Lage NICHT nach -> False-Green-Gefahr).")
        raised = False
        try:
            db_session.add(AbstainLog(id=id_neg, event_id=eid, tenant_id=tenant,
                                      intent_type='preis'))
            db_session.commit()
        except Exception:
            raised = True
            db_session.rollback()
        assert raised, (
            "M-4: ohne Tenant-GUC haette FORCE-RLS WITH CHECK den abstain_log-INSERT fail-closed "
            "abweisen muessen. Genau das trifft den Plan-03-Daemon ohne die A1-set_current_tenant-"
            "Klammer (Slow-Lane ohne Request-Context) -> abstain_log lautlos verworfen, Event ewig "
            "'pending'. Fix = Plan 03: set_current_tenant(str(tenant)) vor dem Write.")

        # ── (b) POSITIV: GUC gesetzt -> derselbe INSERT geht durch + ist lesbar ──
        set_current_tenant(str(tenant))
        db_session.rollback()   # leere-GUC-TX beenden -> naechste TX laeuft mit GUC=tenant
        db_session.add(AbstainLog(id=id_pos, event_id=eid, tenant_id=tenant, intent_type='preis'))
        db_session.commit()
        written.append(id_pos)
        got = db_session.query(AbstainLog).filter(AbstainLog.id == id_pos).first()
        assert got is not None, ("M-4: nach set_current_tenant muss der abstain_log-INSERT "
                                 "durchgehen (Positiv-Kontrolle -> Plan-03-A1-Daemon-Vertrag).")
        assert str(got.tenant_id) == str(tenant)
        # BEWEIS dass der GUC-lose Negativ-INSERT WIRKLICH nichts schrieb (Lese unter korrektem GUC).
        assert db_session.query(AbstainLog).filter(AbstainLog.id == id_neg).first() is None, (
            "M-4: der GUC-lose INSERT darf KEINE Zeile geschrieben haben (echte Absenz, nicht "
            "RLS-Read-Filter).")
    finally:
        set_current_tenant(str(tenant))
        db_session.rollback()   # frische TX mit GUC=tenant fuer cleanup_rows (abstain_log FORCE RLS)
        cleanup_rows(db_session,
                     {"public.abstain_log": written, "public.intent_event": [eid]},
                     tenant=tenant)
