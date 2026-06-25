"""TAXO2-Plan 02: public.mode_weight_config — Modus-Gewichtssatz der Noten-Engine (D-01/D-04).

Reine Schema-Addition + idempotenter Default-Seed. Hand-geschrieben (op.create_table +
op.create_unique_constraint + op.execute COMMENT + idempotenter INSERT ... ON CONFLICT DO NOTHING —
hauseigenes Muster aller Migrationen, kein autogenerate-Round-Trip, SCHILD-Praezedenz 0015/0019/0020).

Pro (session_mode, dimension) genau eine Zeile: config-Gewicht + config-an/aus + Tor-1-Schwelle
(D-03) + Kaltakquise-Marker (partial_marker/indirekt_erkannt, D-04). Globale Config-Tabelle
(KEINE per-Call-Daten, KEIN tenant_id, KEINE RLS) -> Owner nerve_app, KEINE Policy.

N-4 (TAXO-INTERLOCK, KRITISCH): session_mode traegt EXAKT die calls.call_mode-Wertstrings
{cold_call, meeting_consented} + 'training' (origin='training'). KEIN 'meeting'-Kurzform irgendwo.
Die Engine leitet ihren Lookup-Schluessel aus calls.call_mode (live) bzw. 'training' (origin) ab —
ein leerer Lookup -> alle Dimensionen config_off -> coaching_score IMMER NULL (stiller Totalausfall).

CREATE-ALL/SEED-TRAP (FOLD B / DEPLOY-CREATE-ALL-Lehre, wie 0020): diese Migration MUSS VOR dem
Gunicorn-Restart laufen (deploy.sh fuehrt Migration server-seitig vor dem Restart aus). Sonst baut
Base.metadata.create_all() beim App-Start eine NACKTE, UNGESEEDETE Tabelle (Owner postgres, KEIN
Schild). Der Seed lebt daher IN dieser Migration und ist idempotent (ON CONFLICT (session_mode,
dimension) DO NOTHING) — KEIN Seed via ORM/App-Startup. Migration laeuft als postgres (nerve_app
hat kein CREATE auf public); danach ALTER TABLE ... OWNER TO nerve_app. COMMENT-Texte =
Single-Source = models.py comment=.

D-04 Default-Gewichtssaetze (laufzeit-tunbar, Punkt 12):
- KALTAKQUISE (cold_call): 7 Zeilen. Vorwand/Aufschub/Kaufsignal/Phasen-Technik/Fragen-Qualitaet/
  Outcome-Progression enabled weight>0; Gespraechsfuehrung enabled weight>0 partial_marker=
  'sprechdisziplin' (nur Monolog/Tempo, Talk-Share aus). Vorwand/Aufschub/Kaufsignal indirekt_erkannt
  =true. Gesamtgewicht bewusst < Meeting (schlanker Modus, D-02 muss trotzdem scoren koennen).
- MEETING (meeting_consented): 7 Zeilen, alle enabled weight>0, indirekt_erkannt=false, kein partial.
- TRAINING (training): 7 Zeilen, alle enabled weight>0. Ground-Truth-Erkennung (8. Dim/payload) ist
  DEFERRED-Verkabelung (TRAINING-REVISIT) — hier nur die 7 Gewichtszeilen angelegt.

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


# ── D-04 Default-Gewichtssaetze (session_mode, dimension, weight, enabled, partial_marker,
#    indirekt_erkannt, confidence_gate). Gewichte sind tunbar (Punkt 12). ───────────────────
_SEED = [
    # KALTAKQUISE — schlanker Modus. Gespraechsfuehrung TEIL-AN (sprechdisziplin); Ereignis-Dims
    # indirekt erkannt. Gesamtgewicht (1.7) bewusst kleiner als Meeting (2.4) -> ein schlanker
    # Modus muss bei voller Datenlage fuer SEINE Dims trotzdem scoren (D-02 test_mode_can_never_score).
    ('cold_call', 'vorwand_behandlung',   0.30, True,  None,            True,  0.70),
    ('cold_call', 'aufschub_behandlung',  0.20, True,  None,            True,  0.70),
    ('cold_call', 'kaufsignal_nutzung',   0.20, True,  None,            True,  0.70),
    ('cold_call', 'phasen_technik',       0.15, True,  None,            False, 0.70),
    ('cold_call', 'fragen_qualitaet',     0.15, True,  None,            False, 0.70),
    ('cold_call', 'abschluss_fuehrung',   0.20, True,  None,            False, 0.70),
    ('cold_call', 'gespraechsfuehrung',   0.20, True,  'sprechdisziplin', False, 0.70),
    # MEETING — alle 7 voll AN, kein indirekt, kein partial.
    ('meeting_consented', 'vorwand_behandlung',  0.25, True, None, False, 0.70),
    ('meeting_consented', 'aufschub_behandlung', 0.15, True, None, False, 0.70),
    ('meeting_consented', 'kaufsignal_nutzung',  0.20, True, None, False, 0.70),
    ('meeting_consented', 'phasen_technik',      0.15, True, None, False, 0.70),
    ('meeting_consented', 'fragen_qualitaet',    0.20, True, None, False, 0.70),
    ('meeting_consented', 'abschluss_fuehrung', 0.20, True, None, False, 0.70),
    ('meeting_consented', 'gespraechsfuehrung',  0.25, True, None, False, 0.70),
    # TRAINING — alle 7 AN (Ground-Truth-Score DEFERRED, hier nur die Gewichtszeilen).
    ('training', 'vorwand_behandlung',   0.20, True, None, False, 0.70),
    ('training', 'aufschub_behandlung',  0.15, True, None, False, 0.70),
    ('training', 'kaufsignal_nutzung',   0.15, True, None, False, 0.70),
    ('training', 'phasen_technik',       0.15, True, None, False, 0.70),
    ('training', 'fragen_qualitaet',     0.20, True, None, False, 0.70),
    ('training', 'abschluss_fuehrung',   0.15, True, None, False, 0.70),
    ('training', 'gespraechsfuehrung',   0.20, True, None, False, 0.70),
]


def upgrade() -> None:
    op.create_table('mode_weight_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_mode', sa.String(length=32), nullable=False),
        sa.Column('dimension', sa.String(length=48), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('partial_marker', sa.String(length=48), nullable=True),
        sa.Column('indirekt_erkannt', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('confidence_gate', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_unique_constraint(
        'uq_mode_weight_config_mode_dim', 'mode_weight_config', ['session_mode', 'dimension']
    )

    # Owner umlegen (Migration laeuft als postgres). Globale Config -> KEINE RLS/Policy.
    op.execute("ALTER TABLE public.mode_weight_config OWNER TO nerve_app")

    # ── Idempotenter Default-Seed (SEED-TRAP-Schutz): ON CONFLICT DO NOTHING auf dem
    #    UNIQUE(session_mode, dimension). Re-Run der Migration / vorhandene Zeilen -> No-Op. ──
    insert_sql = sa.text(
        "INSERT INTO public.mode_weight_config "
        "(session_mode, dimension, weight, enabled, partial_marker, indirekt_erkannt, "
        " confidence_gate, updated_at) "
        "VALUES (:session_mode, :dimension, :weight, :enabled, :partial_marker, "
        "        :indirekt_erkannt, :confidence_gate, now()) "
        "ON CONFLICT (session_mode, dimension) DO NOTHING"
    )
    bind = op.get_bind()
    for (session_mode, dimension, weight, enabled, partial_marker,
         indirekt_erkannt, confidence_gate) in _SEED:
        bind.execute(insert_sql, {
            'session_mode': session_mode,
            'dimension': dimension,
            'weight': weight,
            'enabled': enabled,
            'partial_marker': partial_marker,
            'indirekt_erkannt': indirekt_erkannt,
            'confidence_gate': confidence_gate,
        })

    # Schilder (Punkt 23) — Single-Source = models.py comment=. Einfache Quotes verdoppelt.
    op.execute("COMMENT ON TABLE public.mode_weight_config IS 'Modus-Gewichtssatz fuer die Noten-Engine (D-01/D-04, laufzeit-tunbar Punkt 12). Pro Modus+Dimension: Gewicht, config-an/aus, Tor-1-Konfidenzschwelle. Globale Config (kein tenant_id, keine RLS). Status: lebt (neu, TAXO2). Liest services/rubric_engine.py; schreibt Admin/Seed (Migration).'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.session_mode IS 'Modus: cold_call|meeting_consented|training (N-4, EXAKT calls.call_mode-Werte + training, KEIN meeting-Kurzform). Lookup-Schluessel der Engine (aus calls.call_mode/origin=training).'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.dimension IS 'Dimensions-Key (ASCII): vorwand_behandlung/kaufsignal_nutzung/aufschub_behandlung/phasen_technik/fragen_qualitaet/gespraechsfuehrung/abschluss_fuehrung. Korreliert mit services/rubric_dimensions.py DIMENSIONS.'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.weight IS 'Config-Gewicht der Dimension im Modus (D-01/D-04). 0 = config-AUS = Dimension gilt im Modus nicht (Ausschluss-Grund config_off, getrennt von Proration-Drop).'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.enabled IS 'config-an-Flag (D-01). enabled=false ODER weight<=0 -> Dimension config_off (faellt VOR der Messbarkeit raus, eigener Ausschluss-Grund).'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.partial_marker IS 'Teil-Messbarkeits-Marker (D-04), z.B. sprechdisziplin fuer Kaltakquise-Gespraechsfuehrung (nur Monolog/Tempo messbar, Talk-Share aus). NULL = voll messbar.'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.indirekt_erkannt IS '(indirekt erkannt)-Marker (D-04): Kaltakquise-Vorwand/Aufschub/Kaufsignal werden indirekt erkannt -> 999.2 zeigt geringere statistische Belastbarkeit. NICHT killen, Unsicherheit transparent machen.'")
    op.execute("COMMENT ON COLUMN public.mode_weight_config.confidence_gate IS 'Tor-1-Konfidenzschwelle (D-03) fuer Ereignis-Messbarkeit. NULL -> Engine-Default 0.70. Niedrig-Konfidenz-Ereignisse zaehlen nicht fuer >=1/messbar (garbage-in-Schutz).'")


def downgrade() -> None:
    # Reversibel: Tabelle startet leer (nur Seed) -> kein Nutzer-Datenverlust. UNIQUE faellt mit
    # der Tabelle.
    op.drop_table('mode_weight_config')
