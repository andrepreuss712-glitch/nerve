"""TAXO2-Plan 01 — rubric_score: Schema-/Insert-Roundtrip + payload_jsonb-Training-Reserve
+ F-08-Cascade (0 Waisen) + F-03 partieller Unique-Konflikt + M-4 RLS-GUC-Falle (Negativ/Positiv).

CLAUDE.md-konform: ausschliesslich Runtime-Behavior-Tests gegen REAL-PG nerve_test
(db_session-Fixture seedet einen Test-Mandanten + setzt den app.tenant_id-GUC -> FORCE-RLS
laesst die Inserts unter `tenant_id == TEST_TENANT_UUID` durch). KEINE Source-Presence-Assertions.

SKIP nur ohne TEST_DATABASE_URL (kein sqlite-Fallback by design — RLS/partieller Index/Cascade
gibt es nur auf Postgres, kein False-Green). Im Deploy-Gate laeuft scharf. Jeder committende Test
raeumt seine Rows via cleanup_rows wieder weg (Baseline-Sauberkeit).

PENDING-SUPERVISED-DEPLOY: diese Tests laufen erst GRUEN, wenn public.rubric_score auf nerve_test
existiert (Migration 0020). Der Prod-/Test-DB-Migrations-Lauf + die scharfe pytest-Ausfuehrung
laufen SUPERVISED (Claudian/Andre) — NICHT in dieser Welle (kein Local-Dev, kein lokales pytest).
"""
import uuid
from datetime import datetime, timezone

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _make_call(db, tenant):
    """Erzeugt eine calls-Row unter dem Test-Tenant (tenant_id == GUC, sonst RLS WITH CHECK
    auf abhaengigen Tabellen). Gibt call_id (str) zurueck."""
    from database.models import Call
    call_id = str(uuid.uuid4())
    db.add(Call(
        id=call_id,
        user_id=1,
        tenant_id=tenant,
        call_mode='cold_call',
        started_at=datetime.now(timezone.utc),
        transcript_storage='none',
    ))
    db.commit()
    return call_id


# ── Schema-/Insert-Roundtrip + Defaults ──────────────────────────────────────

def test_rubric_score_insert_roundtrip(db_session):
    """Minimaler Insert (session_mode/origin/payload_jsonb + tenant) -> commit -> query ->
    assert Feldwerte; is_provisional default False, score_schema_version default 1."""
    from database.models import RubricScore
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"
    row_id = str(uuid.uuid4())
    try:
        db_session.add(RubricScore(
            id=row_id,
            tenant_id=tenant,
            session_mode='cold_call',
            origin='live',
            payload_jsonb={},
        ))
        db_session.commit()

        got = db_session.query(RubricScore).filter(RubricScore.id == row_id).first()
        assert got is not None
        assert got.session_mode == 'cold_call'
        assert got.origin == 'live'
        # Defaults (server_default false / 1).
        assert got.is_provisional is False
        assert got.score_schema_version == 1
        # Noch nicht gerechnet -> NULL.
        assert got.coaching_score is None
        assert got.measured_weight_pct is None
    finally:
        cleanup_rows(db_session, {"public.rubric_score": [row_id]}, tenant=tenant)


# ── Training-Fit-Reserve: payload_jsonb nimmt Training-only-Keys ──────────────

def test_rubric_score_payload_jsonb_accepts_training_keys(db_session):
    """Training-Fit-Pass (Task 0) real belegt: payload_jsonb traegt was_correct/scenario_id/
    ground_truth_score (training-only) -> Read zurueck, Keys vorhanden. Beweist die spaetere
    Training-Verkabelung braucht KEINE Migration (SPEC Req 1)."""
    from database.models import RubricScore
    tenant = conftest.TEST_TENANT_UUID
    row_id = str(uuid.uuid4())
    try:
        db_session.add(RubricScore(
            id=row_id,
            tenant_id=tenant,
            session_mode='training',
            origin='training',
            payload_jsonb={
                'was_correct': True,
                'scenario_id': 'sz-42',
                'ground_truth_score': 0.83,
            },
        ))
        db_session.commit()

        got = db_session.query(RubricScore).filter(RubricScore.id == row_id).first()
        assert got is not None
        assert got.payload_jsonb.get('was_correct') is True
        assert got.payload_jsonb.get('scenario_id') == 'sz-42'
        assert got.payload_jsonb.get('ground_truth_score') == 0.83
    finally:
        cleanup_rows(db_session, {"public.rubric_score": [row_id]}, tenant=tenant)


# ── F-08: Cascade on Call-Delete (0 Waisen, DSGVO Art.17) ─────────────────────

def test_rubric_score_cascade_on_call_delete(db_session):
    """F-08/DD-01: rubric_score.call_id ist HARTER FK ON DELETE CASCADE.
    Test-Call + rubric_score-Zeile (origin='live', call_id=<call>) -> DELETE Call ->
    assert 0 Waisen (DSGVO: geloeschter Call raeumt die Note mit)."""
    from database.models import Call, RubricScore
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    row_id = str(uuid.uuid4())
    try:
        db_session.add(RubricScore(
            id=row_id, call_id=call_id, tenant_id=tenant,
            session_mode='cold_call', origin='live', payload_jsonb={},
        ))
        db_session.commit()
        assert db_session.query(RubricScore).filter(
            RubricScore.id == row_id).first() is not None

        # Call loeschen -> CASCADE raeumt rubric_score mit.
        db_session.query(Call).filter(Call.id == call_id).delete(synchronize_session=False)
        db_session.commit()

        orphans = db_session.query(RubricScore).filter(
            RubricScore.call_id == call_id).count()
        assert orphans == 0, f"F-08: {orphans} Waisen nach Call-Delete (erwartet 0 — CASCADE)"
    finally:
        cleanup_rows(db_session,
                     {"public.rubric_score": [row_id], "public.calls": [call_id]},
                     tenant=tenant)


# ── F-03: partieller Unique-Index (call_id WHERE origin='live') ───────────────

def test_rubric_score_live_unique_conflict(db_session):
    """F-03: zwei rubric_score-Zeilen mit demselben call_id + origin='live' -> die zweite muss
    eine Unique-Verletzung werfen (partieller Index greift). Gegencheck: zwei origin='training'-
    Zeilen mit gleichem conversation_log_id (call_id NULL) sind ERLAUBT (Index ausgenommen ->
    Training-Fit unverletzt)."""
    from database.models import Call, RubricScore
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
    id_t1, id_t2 = str(uuid.uuid4()), str(uuid.uuid4())
    written = []
    try:
        # ── erste origin='live'-Zeile fuer call_id -> ok ──
        db_session.add(RubricScore(
            id=id_a, call_id=call_id, tenant_id=tenant,
            session_mode='cold_call', origin='live', payload_jsonb={}))
        db_session.commit()
        written.append(id_a)

        # ── zweite origin='live'-Zeile fuer DENSELBEN call_id -> Unique-Verletzung ──
        raised = False
        try:
            db_session.add(RubricScore(
                id=id_b, call_id=call_id, tenant_id=tenant,
                session_mode='cold_call', origin='live', payload_jsonb={}))
            db_session.commit()
        except Exception:
            raised = True
            db_session.rollback()
        assert raised, ("F-03: zweite origin='live'-Zeile mit gleichem call_id haette den "
                        "partiellen Unique-Index ux_rubric_score_live_call_id verletzen muessen")
        # die zweite Zeile darf NICHT existieren.
        assert db_session.query(RubricScore).filter(RubricScore.id == id_b).first() is None

        # ── Gegencheck: zwei origin='training'-Zeilen (call_id NULL) sind ERLAUBT ──
        clog = 99001
        db_session.add(RubricScore(
            id=id_t1, call_id=None, conversation_log_id=clog, tenant_id=tenant,
            session_mode='training', origin='training', payload_jsonb={}))
        db_session.add(RubricScore(
            id=id_t2, call_id=None, conversation_log_id=clog, tenant_id=tenant,
            session_mode='training', origin='training', payload_jsonb={}))
        db_session.commit()
        written.extend([id_t1, id_t2])
        cnt = db_session.query(RubricScore).filter(
            RubricScore.conversation_log_id == clog).count()
        assert cnt == 2, ("F-03 Gegencheck: zwei origin='training'-Zeilen muessen erlaubt sein "
                          "(partieller Index ist auf origin='live' beschraenkt)")
    finally:
        cleanup_rows(db_session,
                     {"public.rubric_score": written, "public.calls": [call_id]},
                     tenant=tenant)


# ── M-4: FORCE-RLS-Falle gegen den eigenen Daemon (Awareness, Fix = Plan 04) ──

def test_rubric_score_rls_requires_tenant_guc(db_session):
    """M-4 (TAXO-INTERLOCK-FINDINGS, teuerste stille Regression): FORCE ROW LEVEL SECURITY +
    WITH CHECK greift AUCH gegen den eigenen Scoring-Daemon (Plan 04, Slow-Lane ohne
    Request-Context -> GUC NULL -> INSERT lautlos abgelehnt -> coaching_score ewig NULL).

    (a) NEGATIV: ohne gesetzten Tenant-GUC (clear_current_tenant, wie im Daemon-Thread ohne
        Request) -> ein INSERT mit gesetztem tenant_id wird von WITH CHECK fail-closed ABGELEHNT.
    (b) POSITIV: nach set_current_tenant(<tenant>) -> derselbe INSERT geht durch + ist lesbar.

    Beweist: der Schreiber MUSS den GUC setzen (Plan-04-Vertrag: set_current_tenant vor dem
    rubric_score-Write). Server-seitig gegen Postgres (skip ohne TEST_DATABASE_URL -> kein
    False-Green; SQLite hat kein RLS). Schuetzt die teuerste stille Regression.
    """
    from sqlalchemy import text
    from database.db import set_current_tenant, clear_current_tenant
    from database.models import RubricScore
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"
    id_neg, id_pos = str(uuid.uuid4()), str(uuid.uuid4())
    written = []
    try:
        # ── (a) NEGATIV: GUC leer (Daemon ohne Request-Context) -> WITH CHECK weist ab ──
        # WICHTIG (TX-Mechanik, database/db.py:73-89): der app.tenant_id-GUC wird vom after_begin-Hook
        # bei TRANSAKTIONS-BEGINN aus dem contextvar gesetzt (SET LOCAL, auto-clear bei commit/rollback).
        # clear_current_tenant() leert nur den contextvar fuer KUENFTIGE TX, NICHT die schon laufende
        # db_session-TX (deren GUC steht bereits auf TEST_TENANT_UUID). Daher: nach dem Clear die laufende
        # TX per rollback() beenden -> der naechste Statement-Block oeffnet eine FRISCHE TX, in der
        # after_begin den geleerten contextvar liest -> KEIN SET -> GUC ungesetzt -> exakt die
        # Daemon-ohne-Request-Context-Lage (Plan 04).
        clear_current_tenant()
        db_session.rollback()
        # BELEG (Anti-False-Green, PGTEST-Lehre): in der frischen TX ist der GUC WIRKLICH leer.
        # Dieser SELECT oeffnet die neue TX (after_begin feuert mit leerem contextvar -> kein SET).
        guc = db_session.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar()
        assert guc in (None, ''), (
            f"Negativ-Bein-Vorbedingung: app.tenant_id-GUC MUSS leer sein, war {guc!r}. "
            "Sonst stellt der Test die kein-Tenant-Lage NICHT nach (False-Green-Gefahr).")
        raised = False
        try:
            # Laeuft in DERSELBEN frischen TX (leerer GUC) -> WITH CHECK greift beim commit.
            db_session.add(RubricScore(
                id=id_neg, tenant_id=tenant,
                session_mode='cold_call', origin='live', payload_jsonb={}))
            db_session.commit()
        except Exception:
            # tenant_isolation WITH CHECK (GUC NULL -> nullif -> NULL::uuid -> predicate false)
            # rejiziert -> TX abgebrochen -> rollback Pflicht.
            raised = True
            db_session.rollback()
        assert raised, (
            "M-4: ohne Tenant-GUC haette FORCE-RLS WITH CHECK den INSERT fail-closed abweisen "
            "muessen. Genau das trifft den Plan-04-Daemon (Slow-Lane ohne Request-Context) -> "
            "rubric_score-INSERT lautlos verworfen -> coaching_score ewig NULL. Fix = Plan 04: "
            "set_current_tenant(str(call.tenant_id)) vor dem Write (db.py:43-Muster).")

        # ── (b) POSITIV: GUC gesetzt -> derselbe INSERT geht durch + ist lesbar ──
        set_current_tenant(str(tenant))
        db_session.rollback()   # leere-GUC-TX beenden -> naechste TX laeuft mit GUC=tenant
        db_session.add(RubricScore(
            id=id_pos, tenant_id=tenant,
            session_mode='cold_call', origin='live', payload_jsonb={}))
        db_session.commit()
        written.append(id_pos)
        got = db_session.query(RubricScore).filter(RubricScore.id == id_pos).first()
        assert got is not None, ("M-4: nach set_current_tenant muss der INSERT durchgehen "
                                 "(Positiv-Kontrolle -> Plan-04-Daemon-Vertrag).")
        assert str(got.tenant_id) == str(tenant)
        # BEWEIS dass der GUC-lose Negativ-INSERT WIRKLICH nichts schrieb — gelesen unter dem
        # KORREKTEN Tenant-GUC (sonst versteckt die USING-Klausel ohnehin alles -> kein echter Beleg).
        assert db_session.query(RubricScore).filter(RubricScore.id == id_neg).first() is None, (
            "M-4: der GUC-lose INSERT darf KEINE Zeile geschrieben haben (Lese unter korrektem "
            "Tenant-GUC -> echte Absenz, nicht RLS-Read-Filter).")
    finally:
        # GUC fuer den Fixture-Teardown wiederherstellen (db_session erwartet gesetzten Tenant).
        set_current_tenant(str(tenant))
        db_session.rollback()   # frische TX mit GUC=tenant fuer cleanup_rows
        cleanup_rows(db_session, {"public.rubric_score": written}, tenant=tenant)
