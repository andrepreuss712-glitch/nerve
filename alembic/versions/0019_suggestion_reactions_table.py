"""TAXO2-Plan 08 (FOLD A): public.suggestion_reactions — Roh-Erfassung jedes NERVE-Vorschlags pro Call.

Reine Schema-Addition (leere Tabelle). Hand-geschrieben (op.create_table + op.create_index +
op.execute COMMENT — hauseigenes Muster aller Migrationen, kein autogenerate-Round-Trip,
SCHILD-Praezedenz 0015/0016).

Roh-Angebot-Spalten (JETZT befuellt vom Call-Ende-Flush) + nullable DEFERRED-Reaktions-Spalten
(adoption_value/following_utterance_ref/reaction_class — post-Launch, NICHT in TAXO2 befuellt).

F-08/DD-01: call_id = HARTER FK calls(id) ON DELETE CASCADE (DSGVO-Loesch-Kette
calls->suggestion_reactions; suggestion_text = potenzieller Wortlaut). tenant_id = FK
public.tenant_orgs(id) (erlaubt, NICHT die RLS-Wall).

DEPLOY-REIHENFOLGE (FOLD B P3 / DEPLOY-CREATE-ALL-Lehre 18.06): diese Migration MUSS VOR dem
Gunicorn-Restart laufen (deploy.sh fuehrt Migration server-seitig vor dem Restart aus). Sonst
baut Base.metadata.create_all() beim App-Start eine NACKTE Tabelle (Owner postgres, KEINE RLS,
KEIN Schild) -> SCHILD-Guard rot, RLS fehlt.

Migration laeuft als postgres (nerve_app hat kein CREATE auf public); danach
ALTER TABLE ... OWNER TO nerve_app. RLS: ENABLE + FORCE ROW LEVEL SECURITY (FORCE greift auch
fuer Owner nerve_app -> kein Bypass) + tenant_isolation (nullif-fail-closed, 0014-Muster).
COMMENT-Texte = Single-Source = models.py comment=.

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('suggestion_reactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        # ── Roh-Angebot-Spalten ───────────────────────────────────────────────
        sa.Column('call_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('calls.id', ondelete='CASCADE'), nullable=True),
        sa.Column('conversation_log_id', sa.Integer(), nullable=True),
        sa.Column('interaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('slot', sa.String(length=8), nullable=True),
        sa.Column('source', sa.String(length=24), nullable=True),
        sa.Column('model', sa.String(length=48), nullable=True),
        sa.Column('suggestion_text', sa.Text(), nullable=True),
        sa.Column('einwand_typ', sa.String(length=64), nullable=True),
        sa.Column('ts_offered', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenant_orgs.id'), nullable=True),
        sa.Column('payload_jsonb', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        # ── DEFERRED-Reaktions-Spalten (nullable, NICHT befuellt in TAXO2) ─────
        sa.Column('adoption_value', sa.Float(), nullable=True),
        sa.Column('following_utterance_ref', sa.String(length=128), nullable=True),
        sa.Column('reaction_class', sa.String(length=24), nullable=True),
    )

    # Indizes (7): call_id + interaction_id (Moment-Korrelation) + source + conversation_log_id
    # + org_id + user_id + tenant_id
    op.create_index('ix_suggestion_reactions_call_id', 'suggestion_reactions', ['call_id'])
    op.create_index('ix_suggestion_reactions_interaction_id', 'suggestion_reactions', ['interaction_id'])
    op.create_index('ix_suggestion_reactions_source', 'suggestion_reactions', ['source'])
    op.create_index('ix_suggestion_reactions_conversation_log_id', 'suggestion_reactions', ['conversation_log_id'])
    op.create_index('ix_suggestion_reactions_org_id', 'suggestion_reactions', ['org_id'])
    op.create_index('ix_suggestion_reactions_user_id', 'suggestion_reactions', ['user_id'])
    op.create_index('ix_suggestion_reactions_tenant_id', 'suggestion_reactions', ['tenant_id'])

    # Owner umlegen (Migration laeuft als postgres). FORCE RLS (unten) greift auch fuer den Owner.
    op.execute("ALTER TABLE public.suggestion_reactions OWNER TO nerve_app")

    # RLS: ENABLE + FORCE + tenant_isolation (nullif-fail-closed, 0014:51-55).
    op.execute("ALTER TABLE public.suggestion_reactions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.suggestion_reactions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON public.suggestion_reactions
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    """)

    # Schilder (Punkt 23) — Single-Source = models.py comment=. Einfache Quotes verdoppelt.
    op.execute("COMMENT ON TABLE public.suggestion_reactions IS 'Roh-Erfassung jedes NERVE-Vorschlags pro Call (Auto-Variante Slot B + Manueller Knopf + Keyword), insert-only + anonymisiert, Call-Ende-Flush (KEIN Live-Write). NUR das ANGEBOT befuellt; Reaktions-Haelfte (adoption_value/...) DEFERRED post-Launch. call_id harter FK CASCADE (F-08). Status: lebt (neu, TAXO2 FOLD A). Schreibt services/suggestion_capture.py (Flush) + services/live_session.py (RAM); liest Uebernahme-Scoring (Post-Launch).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.call_id IS 'Bezug zum Call. HARTER FK ON DELETE CASCADE (F-08/DD-01) — geloeschter Call raeumt das Angebot (suggestion_text=potenzieller Wortlaut) DSGVO-sauber mit. nullable: Edge ohne ermittelbare call_id.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.conversation_log_id IS 'Bezug zur Session. Korrelations-/Gruppier-Schluessel des Flushs.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.interaction_id IS 'Moment-Klammer (Korrelation zu intent_event.interaction_id, TAXO1). Vom Capture-Pfad IMMER gesetzt (get_or_open_moment, FOLD A-2/B1); nullable nur als Defense. KEIN FK (kein PK). Naht fuer spaeteres Uebernahme-Scoring.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.org_id IS 'Mandant (per-Berater-/Org-Filter, RLS-Ergaenzung).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.user_id IS 'Berater (per-Berater-Auswertung, DEFERRED).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.slot IS 'Liefer-Kanal: A=Profil-Stichwort-instant (Keyword/Fast-Lane) | B=KI-gestreamt (Auto-Variante/Knopf-Antwort).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.source IS 'Ausloeser des Angebots: auto_variante | manual_button | keyword. Fuer A/B-Test der Antwort-Engine + systematisch-ignoriert-Analyse (TAXO3).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.model IS 'Antwort-Modell (z.B. haiku/sonnet) — A/B-Test + Selbst-Verbesserung.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.suggestion_text IS 'Was NERVE ausgab — ANONYMISIERTE Storage-Version (Plan 09, am Erfassen mit lebendem Per-SID-Cache; NIE cache=None). DSGVO: Cascade-clean via call_id-FK.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.einwand_typ IS 'Einwand-Typ-Kontext des Angebots (Korrelation).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.ts_offered IS 'Zeitpunkt des Angebots (Live-Latenz-Diagnose: ignoriert-weil-zu-spaet vs weil-schlecht).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.tenant_id IS 'Mandanten-Abschottung (RLS FORCE, abgeleitet aus calls.tenant_id).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.payload_jsonb IS 'Reserve fuer kuenftige Felder (confidence, einwand_typ-Detail) ohne Migration. FOLD A.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.adoption_value IS '[DEFERRED, post-Launch] Uebernahme-Grad 0-1 (1:1 / ~90% / ignoriert). In TAXO2 NICHT befuellt (Soll-Verhalten §6).'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.following_utterance_ref IS '[DEFERRED, post-Launch] Verweis auf die folgende Berater-Aeusserung (Uebernahme-Skala). NICHT in TAXO2.'")
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.reaction_class IS '[DEFERRED, post-Launch] Klassifikation der Reaktion. NICHT in TAXO2.'")


def downgrade() -> None:
    # Reversibel: Tabelle startet leer -> kein Datenverlust. Indizes + FK + Policy fallen mit der Tabelle,
    # Policy explizit zuerst (symmetrisch zum 0014-Muster).
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON public.suggestion_reactions")
    op.drop_table('suggestion_reactions')
