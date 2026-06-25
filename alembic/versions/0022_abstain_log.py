"""TAXO2-Plan 03, Task 2: public.abstain_log — Goodhart-/Bias-Schutz-Log (D-07 Rider 3).

Reine Schema-Addition (leere Tabelle). Hand-geschrieben (op.create_table + op.create_index +
op.execute COMMENT — hauseigenes Muster aller Migrationen, kein autogenerate-Round-Trip,
SCHILD-Praezedenz 0015/0016/0019/0020).

Jede handling_score-Abstention der Slow Lane wird hier mit der nachfolgenden Berater-Aussage
+ interaction_id geloggt. Goldstaub fuer Post-Call-LLM-Nachbewertung (Flywheel).

SCHEMA-ABWEICHUNG vom PLAN (dokumentiert in SUMMARY): der Plan spezifizierte event_id als
UUID -> intent_event(id) ON DELETE CASCADE. Der REALE TAXO1-Vertrag (Migration 0016,
models.py:763) hat KEIN id-UUID — der PK von intent_event ist event_id BIGSERIAL. Darum hier:
event_id = BigInteger -> REFERENCES public.intent_event(event_id) ON DELETE CASCADE.

F-08 DSGVO: harter FK event_id ON DELETE CASCADE schliesst die Loesch-Kette
calls -> intent_event (call_id CASCADE, I-2) -> abstain_log. Ein geloeschter Call hinterlaesst
0 Waisen-Zeilen (next_advisor_sentence = potenzieller Wortlaut). Berater-EIGENE Stimme; bei
moeglichem Kunden-PII anonymisiert der Aufrufer (services/anonymization.py).

KEINE RLS auf dieser Tabelle (Plan-Scope: nur Listen-/Status-Felder + Wortlaut; tenant_id ist
Filter-Spalte, keine RLS-Wall — bewusst minimal, kein Over-Engineering). tenant_id ohne FK
(tenant_orgs-Aktivierung erst Phase F).

DEPLOY-REIHENFOLGE (DEPLOY-CREATE-ALL-Lehre 18.06 / 0020): diese Migration MUSS VOR dem
Gunicorn-Restart laufen (deploy.sh fuehrt Migration server-seitig vor dem Restart aus). Sonst
baut Base.metadata.create_all() beim App-Start eine NACKTE Tabelle (Owner postgres, KEIN Schild)
-> SCHILD-Guard rot. Migration laeuft als postgres (nerve_app hat kein CREATE auf public);
danach ALTER TABLE ... OWNER TO nerve_app. COMMENT-Texte = Single-Source = models.py comment=.

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('abstain_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        # ── harter FK CASCADE auf den intent_event-PK (event_id BIGSERIAL, NICHT id-UUID) ──
        sa.Column('event_id', sa.BigInteger(),
                  sa.ForeignKey('intent_event.event_id', ondelete='CASCADE'), nullable=False),
        sa.Column('interaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('next_advisor_sentence', sa.Text(), nullable=True),
        sa.Column('intent_type', sa.String(length=64), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # Indizes (2): event_id (FK-Lookup + Cascade) + tenant_id (Mandanten-Filter)
    op.create_index('ix_abstain_log_event_id', 'abstain_log', ['event_id'])
    op.create_index('ix_abstain_log_tenant_id', 'abstain_log', ['tenant_id'])

    # Owner umlegen (Migration laeuft als postgres, nerve_app hat kein CREATE auf public).
    op.execute("ALTER TABLE public.abstain_log OWNER TO nerve_app")

    # Schilder (Punkt 23) — Single-Source = models.py comment=. Einfache Quotes verdoppelt.
    op.execute("COMMENT ON TABLE public.abstain_log IS 'Goodhart-/Bias-Schutz-Log (D-07 Rider 3): jede handling_score-Abstention mit nachfolgendem Berater-Satz + interaction_id. Harter FK event_id ON DELETE CASCADE (F-08, DSGVO-clean). Goldstaub fuer Post-Call-LLM-Nachbewertung (Flywheel). Status: lebt (neu, TAXO2). Schreibt services/slow_lane.py; liest Active-Learning (Post-Launch).'")
    op.execute("COMMENT ON COLUMN public.abstain_log.event_id IS 'HARTER FK -> intent_event.event_id ON DELETE CASCADE (F-08/DD-01). Schliesst die DSGVO-Loesch-Kette calls->intent_event->abstain_log: geloeschter Call raeumt die Wortlaut-Zeile mit. event_id = BigInteger (intent_event-PK ist BIGSERIAL, KEIN UUID — Plan-Abweichung dokumentiert).'")
    op.execute("COMMENT ON COLUMN public.abstain_log.interaction_id IS 'Moment-Klammer (Korrelation zu intent_event.interaction_id, TAXO1). Bindet die Abstention an den Kundenmoment fuer die Post-Call-Nachbewertung. KEIN FK (interaction_id ist kein PK).'")
    op.execute("COMMENT ON COLUMN public.abstain_log.next_advisor_sentence IS 'Die nachfolgende Berater-Aussage zum abgewinkten Einwand (D-07 Rider 3, Goodhart-Beleg). Berater-EIGENE Stimme; bei moeglichem Kunden-PII anonymisiert (services/anonymization.py). DSGVO: Cascade-clean via event_id-FK.'")
    op.execute("COMMENT ON COLUMN public.abstain_log.intent_type IS 'Einwand-Typ-Kontext der Abstention (Korrelation/Auswertung welche Intents oft abgewinkt werden).'")
    op.execute("COMMENT ON COLUMN public.abstain_log.tenant_id IS 'Mandanten-Abschottung (abgeleitet aus calls.tenant_id). Per-Tenant-Filter der Nachbewertung.'")


def downgrade() -> None:
    # Reversibel: Tabelle startet leer -> kein Datenverlust. Indizes + FK fallen mit der Tabelle.
    op.drop_table('abstain_log')
