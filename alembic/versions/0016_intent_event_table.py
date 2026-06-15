"""TAXO1-Welle 1: public.intent_event — DIE zentrale Ereignis-Tabelle (Single Source of Truth).

Reine Schema-Addition (leere Tabelle, KEINE Live-Anbindung). Hand-geschrieben
(op.create_table + op.create_index + op.execute COMMENT — hauseigenes Muster aller
Migrationen, kein autogenerate-Round-Trip, SCHILD-Praezedenz 0015).

13 Spalten: 9 indizierte Kern-Spalten + handling_status (INTERLOCK I-1, indiziert) +
reaction_latency_ms + interaction_id (Moment-Klammer, indiziert) + payload_jsonb.

INTERLOCK I-1: handling_status varchar(16) NOT NULL DEFAULT 'pending', indiziert
  (TAXO2-Arbeitsliste WHERE handling_status='pending'). In TAXO1 leer/'pending'.
INTERLOCK I-2: call_id = HARTER FK calls(id) ON DELETE CASCADE (DD-01, DSGVO-Lösch-Kette
  calls→intent_event→abstain_log). A2-"lose FK" revidiert.

Migration laeuft als postgres (nerve_app hat kein CREATE auf public); danach
ALTER TABLE ... OWNER TO nerve_app. COMMENT-Texte = Single-Source = models.py comment=.

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('intent_event',
        sa.Column('event_id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(length=128), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('calls.id', ondelete='CASCADE'), nullable=True),
        sa.Column('mode', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('intent_type', sa.String(length=64), nullable=False),
        sa.Column('phase', sa.SmallInteger(), nullable=True),
        sa.Column('handling_score_numeric', sa.SmallInteger(), nullable=True),
        sa.Column('handling_status', sa.String(length=16), nullable=False,
                  server_default='pending'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('reaction_latency_ms', sa.Integer(), nullable=True),
        sa.Column('interaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('payload_jsonb', postgresql.JSONB(), nullable=False, server_default='{}'),
    )

    # Indizes (9): Kern-Spalten + handling_status (I-1 Arbeitsliste) + interaction_id (Moment-Klammer)
    op.create_index('ix_intent_event_session_id', 'intent_event', ['session_id'])
    op.create_index('ix_intent_event_call_id', 'intent_event', ['call_id'])
    op.create_index('ix_intent_event_mode', 'intent_event', ['mode'])
    op.create_index('ix_intent_event_timestamp', 'intent_event', ['timestamp'])
    op.create_index('ix_intent_event_intent_type', 'intent_event', ['intent_type'])
    op.create_index('ix_intent_event_phase', 'intent_event', ['phase'])
    op.create_index('ix_intent_event_handling_score_numeric', 'intent_event', ['handling_score_numeric'])
    op.create_index('ix_intent_event_handling_status', 'intent_event', ['handling_status'])
    op.create_index('ix_intent_event_interaction_id', 'intent_event', ['interaction_id'])

    # Owner umlegen (Migration laeuft als postgres, RESEARCH §1)
    op.execute("ALTER TABLE public.intent_event OWNER TO nerve_app")

    # Schilder (Punkt 23) — Single-Source = models.py comment=. Einfache Quotes verdoppelt.
    op.execute("COMMENT ON TABLE public.intent_event IS 'Zentrale Ereignis-Tabelle (Single Source of Truth) fuer erkannte Kunden-Intents pro Call. Fast+Medium Lane emittieren; Slow Lane reichert via separatem Score-Objekt an (TAXO2). Hybrid: indizierte Kern-Spalten + payload_jsonb. Status: lebt (neu, TAXO1). Schreibt services/einwand_keyword_matcher.py, services/claude_service.py; liest TAXO2-Scoring.'")
    op.execute("COMMENT ON COLUMN public.intent_event.session_id IS 'SocketIO-sid des Live-Calls. Korreliert mit live_session._session_state[sid]. Per-Call-Filter.'")
    op.execute("COMMENT ON COLUMN public.intent_event.call_id IS 'Bezug zum Call-Record. HARTER FK ON DELETE CASCADE (INTERLOCK I-2 / DD-01-Konvention wie CallEvent models.py:738) — geloeschter Call raeumt Einwand + abstain_log (TAXO2-Wortlaut) DSGVO-sauber mit. A2-''lose FK'' revidiert (F-08). nullable: Events ohne call_id moeglich, FK greift nur fuer gesetzte Werte.'")
    op.execute("COMMENT ON COLUMN public.intent_event.mode IS 'Modus-Dimension (cold_call/meeting/...). First-Class, nicht aus Intent ableitbar. Quelle: ModeStrategy-Registry (Welle 7).'")
    op.execute("COMMENT ON COLUMN public.intent_event.timestamp IS 'Erzeugungs-Zeitpunkt des Events (Zeit-Achse/Latenz-Auswertung).'")
    op.execute("COMMENT ON COLUMN public.intent_event.intent_type IS 'Taxonomie-Wert (Geruest §1): Kern+Gemini-Werte ∪ custom_objection_*. Quelle services/intent_taxonomy.py. Geschrieben Fast+Medium Lane (Welle 4).'")
    op.execute("COMMENT ON COLUMN public.intent_event.phase IS 'Gespraechs-Phase 1-6 als INT (getrennt vom Intent). NICHT String (K3-Falle). Quelle detect_phase (Welle 4).'")
    op.execute("COMMENT ON COLUMN public.intent_event.handling_score_numeric IS 'REQ 2: Behandlungs-Note 1-3. Existiert ab Tag 1, bleibt NULL in TAXO1. Befuellung = TAXO2 (Slow Lane). KEIN Scoring-Code in TAXO1.'")
    op.execute("COMMENT ON COLUMN public.intent_event.handling_status IS 'INTERLOCK I-1: Verarbeitungs-Status der Slow-Lane-Benotung (pending|scored|abstained|failed). TAXO2-Wurzel-Fix gegen dreifach-ueberladene NULL. Arbeitsliste = WHERE handling_status=''pending''; abstained/failed = abgeschlossen. In TAXO1 leer/''pending'' (Default), KEIN Status-Schreib-Code hier — TAXO2 setzt die Werte.'")
    op.execute("COMMENT ON COLUMN public.intent_event.confidence IS 'Konfidenz der Klassifikation (ui_asserted=1.0). Steuert spaeter Cue-Aufdringlichkeit + Score-Beitrag.'")
    op.execute("COMMENT ON COLUMN public.intent_event.reaction_latency_ms IS 'Stress-Metrik: Reaktionszeit des Beraters in ms. Existiert ab Tag 1, befuellt spaeter (TAXO2).'")
    op.execute("COMMENT ON COLUMN public.intent_event.interaction_id IS 'Korrelations-ID pro Kundenmoment — klammert alle Emits (Fast/Medium/Button) + Cue + Reaktion + Abstain eines Moments zusammen; FK-Ziel für spätere suggestion_reactions (Phase H). call_id zu grob, event_id zu fein.'")
    op.execute("COMMENT ON COLUMN public.intent_event.payload_jsonb IS 'Hybrid-Rest: source, inference_basis, taxonomy_version(Pflicht non-null), abstained, speaker_role, speaker_id, is_simulation, origin_type, source_context, outcome, resolved_at_event_id, superseded_by, inference_config_id, was_correct, cue_fired, dimension_available, cue_visible, ui_state_hash. Provenance+Kontext-Felder; Pflichtfelder ab Tag 1, viele NULL in TAXO1.'")


def downgrade() -> None:
    # Reversibel: Tabelle startet leer -> kein Datenverlust. Indizes + FK fallen mit der Tabelle.
    op.drop_table('intent_event')
