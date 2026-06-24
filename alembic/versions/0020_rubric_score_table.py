"""TAXO2-Plan 01: public.rubric_score — Single Source der Benotung (BARS + Proration), Live + Training.

Reine Schema-Addition (leere Tabelle). Hand-geschrieben (op.create_table + op.create_index +
op.execute COMMENT — hauseigenes Muster aller Migrationen, kein autogenerate-Round-Trip,
SCHILD-Praezedenz 0015/0016/0019).

Hybrid: indizierte feste Kern-Spalten + payload_jsonb-Reserve (SPEC Req 1, aufnahmefaehig fuer
Live UND Training ab Tag 1). KEIN Schreiber in dieser Welle — die Engine (Plan 02/04) ist der
einzige Schreiber.

F-08/DD-01: call_id = HARTER FK calls(id) ON DELETE CASCADE (DSGVO-Loesch-Kette
calls->rubric_score; ein geloeschter Call hinterlaesst 0 Waisen-Zeilen). tenant_id = FK
public.tenant_orgs(id) (erlaubt, NICHT die RLS-Wall). nullable, weil Training-Zeilen call_id NULL.

F-03: partieller Unique-Index ux_rubric_score_live_call_id ON (call_id) WHERE origin='live' —
Plan 04 braucht ihn fuer ein valides ON CONFLICT (call_id) DO UPDATE (Postgres verlangt einen
passenden Unique-Index; index=True allein reicht NICHT). Partiell, damit Training-Zeilen
(origin='training', call_id evtl. NULL/mehrfach) NICHT kollidieren.

D-11: RLS ENABLE + FORCE ROW LEVEL SECURITY (FORCE greift auch fuer Owner nerve_app -> kein
Bypass) + tenant_isolation (nullif-fail-closed, 0014:51-55-Muster). Aufloesung Req1 (Owner
nerve_app) + D-11 (RLS-ready): Owner SETZEN + FORCE.

M-4 (TAXO-INTERLOCK-FINDINGS, NUR Awareness hier): FORCE WITH CHECK greift auch gegen den
eigenen Scoring-Daemon (Plan 04, Slow-Lane ohne Request-Context -> GUC NULL -> INSERT lautlos
abgelehnt -> coaching_score ewig NULL). Fix = Plan-04-Vertrag (set_current_tenant vor dem Write);
diese Welle dokumentiert + testet die Falle (test_rubric_score_rls_requires_tenant_guc).

DEPLOY-REIHENFOLGE (FOLD B P3 / DEPLOY-CREATE-ALL-Lehre 18.06): diese Migration MUSS VOR dem
Gunicorn-Restart laufen (deploy.sh fuehrt Migration server-seitig vor dem Restart aus). Sonst
baut Base.metadata.create_all() beim App-Start eine NACKTE Tabelle (Owner postgres, KEINE RLS,
KEIN Schild) -> SCHILD-Guard rot, RLS fehlt. Migration laeuft als postgres (nerve_app hat kein
CREATE auf public); danach ALTER TABLE ... OWNER TO nerve_app. COMMENT-Texte = Single-Source =
models.py comment=.

KEIN CHECK auf session_mode/origin in der DB (Validierung Python-seitig in der Engine, Plan 02).

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('rubric_score',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        # ── harter FK CASCADE (F-08); tenant_id FK tenant_orgs (erlaubt) ──────────
        sa.Column('call_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('calls.id', ondelete='CASCADE'), nullable=True),
        sa.Column('conversation_log_id', sa.Integer(), nullable=True),
        sa.Column('session_mode', sa.String(length=32), nullable=False),
        sa.Column('origin', sa.String(length=16), nullable=False),
        sa.Column('coaching_score', sa.Float(), nullable=True),
        sa.Column('is_provisional', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('measured_weight_pct', sa.Float(), nullable=True),
        sa.Column('unmeasured_dimensions', postgresql.JSONB(), nullable=True),
        sa.Column('dimensions', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenant_orgs.id'), nullable=True),
        sa.Column('payload_jsonb', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('score_schema_version', sa.SmallInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Indizes (5): call_id + conversation_log_id + session_mode + origin + tenant_id
    op.create_index('ix_rubric_score_call_id', 'rubric_score', ['call_id'])
    op.create_index('ix_rubric_score_conversation_log_id', 'rubric_score', ['conversation_log_id'])
    op.create_index('ix_rubric_score_session_mode', 'rubric_score', ['session_mode'])
    op.create_index('ix_rubric_score_origin', 'rubric_score', ['origin'])
    op.create_index('ix_rubric_score_tenant_id', 'rubric_score', ['tenant_id'])

    # F-03 partieller Unique-Index: Plan 04 ON CONFLICT (call_id) WHERE origin='live'.
    # Partiell, damit Training-Zeilen (origin='training') frei bleiben.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_rubric_score_live_call_id "
        "ON public.rubric_score (call_id) WHERE origin = 'live'"
    )

    # Owner umlegen (Migration laeuft als postgres). FORCE RLS (unten) greift auch fuer den Owner.
    op.execute("ALTER TABLE public.rubric_score OWNER TO nerve_app")

    # RLS (D-11): ENABLE + FORCE + tenant_isolation (nullif-fail-closed, 0014:51-55).
    op.execute("ALTER TABLE public.rubric_score ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.rubric_score FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON public.rubric_score
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    """)

    # Schilder (Punkt 23) — Single-Source = models.py comment=. Einfache Quotes verdoppelt.
    op.execute("COMMENT ON TABLE public.rubric_score IS 'Single Source der Benotung (BARS + Proration), Live + Training. Eine Zeile pro bewerteter Call/Session. Hybrid: indizierte Kern-Spalten + payload_jsonb. call_id harter FK CASCADE (F-08/DD-01). Partieller Unique-Index (call_id, origin=live) fuer idempotenten Upsert (F-03). Status: lebt (neu, TAXO2). Schreibt services/slow_lane.py (Engine, Plan 02/04); liest routes/dashboard.py + performance.py (999.2).'")
    op.execute("COMMENT ON COLUMN public.rubric_score.call_id IS 'Bezug zum Call. HARTER FK ON DELETE CASCADE (F-08/DD-01-Konvention wie CallEvent models.py:741) — geloeschter Call raeumt die Note DSGVO-sauber mit. nullable: Training-Zeilen ohne call_id.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.conversation_log_id IS 'Bezug zur Session/conversation_logs. Live=aus Call, Training=aus Trainings-Session.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.session_mode IS 'Modus der Bewertung: cold_call|meeting_consented|training (N-4, EXAKT calls.call_mode-Werte + training, kein meeting-Kurzform). Bestimmt den Gewichtssatz (D-01/D-04).'")
    op.execute("COMMENT ON COLUMN public.rubric_score.origin IS 'Herkunft der Note: live|training. SPEC Req 1 — eine Tabelle fuer beide Welten. Steuert den partiellen Unique-Index (F-03).'")
    op.execute("COMMENT ON COLUMN public.rubric_score.coaching_score IS 'Gesamt-Kopf-Zahl (0-100). NULL wenn <50% Gewicht messbar (Proration, D-02) oder not_gradable (D-09). Spiegel von calls.coaching_score (Plan 04).'")
    op.execute("COMMENT ON COLUMN public.rubric_score.is_provisional IS 'Vorlaeufig-Marker (D-08): Score ueber der 50%-Schwelle aber mit weggeprorateten Dimensionen. Anzeige 999.2.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.measured_weight_pct IS 'Anteil messbaren Gewichts am modus-konfigurierten Maximum (D-02/D-08). <0.5 -> coaching_score NULL.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.unmeasured_dimensions IS 'Liste der nicht gewerteten Dimensionen + Grund (n/a vs vergeigt, D-08). Goldstaub fuer 999.2-Erklaerung + ML.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.dimensions IS 'Volle Aufschluesselung pro Dimension (D-05/Req 5): je Dim {score, weight, available, sample_size, beleg_ref, marker[]}. Beleg-Referenz = Transkript-/intent_event-Verweis, KEIN freier LLM-Text.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.status IS 'Bewertungs-Status: scored|pending|not_gradable (D-09 poor_audio_health). NULL = noch nicht gelaufen.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.tenant_id IS 'Mandanten-Abschottung (D-11, RLS-ready). Abgeleitet aus calls.tenant_id. Policy erst COACH.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.payload_jsonb IS 'Reserve + Training-only-Felder (was_correct, scenario_id, ground_truth_score) ohne spaetere Migration. SPEC Req 1.'")
    op.execute("COMMENT ON COLUMN public.rubric_score.score_schema_version IS 'Format-Version der Aufschluesselung fuer spaetere Bumps.'")


def downgrade() -> None:
    # Reversibel: Tabelle startet leer -> kein Datenverlust. Indizes + FK + Policy fallen mit der
    # Tabelle; Policy + partieller Unique-Index explizit zuerst (symmetrisch zum 0014/0019-Muster).
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.rubric_score")
    op.execute("DROP INDEX IF EXISTS ux_rubric_score_live_call_id")
    op.drop_table('rubric_score')
