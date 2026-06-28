"""Phase 08.23.2.TAXO2.HANDLING-TIMING Plan 04 — suggestion_reactions Schild-Aktualisierung.

Punkt 23 (Aktualitaets-Pflicht): Plan 04 befuellt erstmals die 3 DEFERRED-Spalten
adoption_value / following_utterance_ref / reaction_class via services/adoption_runner.py.
Deren DB-Schilder (pg_description) tragen durch Migration 0019 noch den veralteten Text
'[DEFERRED] NICHT in TAXO2' — durch Plan 04 FALSCH. Ein veraltetes Schild ist schlimmer
als keines (es taeuscht eine falsche Wahrheit vor).

Diese Migration gleicht AUSSCHLIESSLICH die DB-Schilder (pg_description) an — KEIN
Schema-Aenderung (ADD/ALTER COLUMN). Die Spalten existieren bereits. COMMENT ist deklarativ
ueberschreibend (idempotent).

Single-Source (Punkt 23): die COMMENT-Texte im upgrade() sind WORTGLEICH zu den
models.py comment=-Werten (3 Spalten + Tabelle). Der downgrade() stellt die 0019-ALT-Texte
wortgleich wieder her (Symmetrie, aus 0019 Z.87/101-103 exakt uebernommen).

down_revision = '0029' (Prod-HEAD nach Plan-02-Deploy; Migrations-Chain:
0027 live -> 0028 Plan01 -> 0029 Plan02 -> 0030 DIESER Plan).

Revision ID: 0030
Revises: 0029
"""
from alembic import op

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


# ── Neue Schild-Texte (WORTGLEICH zu database/models.py comment=, Single-Source Punkt 23) ──────

_COMMENT_ADOPTION_VALUE_NEW = (
    "Uebernahme-Grad 0-1 (voll/teilweise/ignoriert). Befuellt ab TAXO2 LLM-Uebernahme-Call. "
    "Schreibt services/adoption_runner.py (gebuendelter Sonnet-Call am Call-Ende); "
    "gelesen: Uebernahme-Auswertung post-Launch."
)

_COMMENT_FOLLOWING_UTTERANCE_REF_NEW = (
    "Verweis/Hash auf die folgende Berater-Aeusserung (Uebernahme-Beleg). "
    "Befuellt ab TAXO2 LLM-Uebernahme-Call (services/adoption_runner.py); "
    "gelesen: Auswertung post-Launch."
)

_COMMENT_REACTION_CLASS_NEW = (
    "Klassifikation der Reaktion (voll|teilweise|ignoriert). "
    "Befuellt ab TAXO2 LLM-Uebernahme-Call (services/adoption_runner.py); "
    "gelesen: Auswertung post-Launch."
)

_COMMENT_TABLE_NEW = (
    "Roh-Erfassung jedes NERVE-Vorschlags pro Call (Auto-Variante Slot B + Manueller Knopf + "
    "Keyword), insert-only + anonymisiert, Call-Ende-Flush (KEIN Live-Write). "
    "ANGEBOT-Haelfte befuellt (FOLD A); Reaktions-Haelfte (adoption_value/reaction_class/"
    "following_utterance_ref) ab TAXO2 vom LLM-Uebernahme-Call befuellt. "
    "call_id harter FK CASCADE (F-08). Status: lebt (neu, TAXO2 FOLD A). "
    "Schreibt services/suggestion_capture.py (Flush) + services/live_session.py (RAM) + "
    "services/adoption_runner.py (Reaktions-Haelfte adoption_value/reaction_class/"
    "following_utterance_ref, gebuendelter LLM-Uebernahme-Call am Call-Ende); "
    "liest Uebernahme-Auswertung (post-Launch)."
)

# ── ALT-Schild-Texte (aus Migration 0019 Z.87/101-103 — fuer downgrade() Symmetrie) ────────────

_COMMENT_ADOPTION_VALUE_OLD = (
    "[DEFERRED, post-Launch] Uebernahme-Grad 0-1 (1:1 / ~90% / ignoriert). "
    "In TAXO2 NICHT befuellt (Soll-Verhalten §6)."
)

_COMMENT_FOLLOWING_UTTERANCE_REF_OLD = (
    "[DEFERRED, post-Launch] Verweis auf die folgende Berater-Aeusserung (Uebernahme-Skala). "
    "NICHT in TAXO2."
)

_COMMENT_REACTION_CLASS_OLD = (
    "[DEFERRED, post-Launch] Klassifikation der Reaktion. NICHT in TAXO2."
)

_COMMENT_TABLE_OLD = (
    "Roh-Erfassung jedes NERVE-Vorschlags pro Call (Auto-Variante Slot B + Manueller Knopf + "
    "Keyword), insert-only + anonymisiert, Call-Ende-Flush (KEIN Live-Write). "
    "NUR das ANGEBOT befuellt; Reaktions-Haelfte (adoption_value/...) DEFERRED post-Launch. "
    "call_id harter FK CASCADE (F-08). Status: lebt (neu, TAXO2 FOLD A). "
    "Schreibt services/suggestion_capture.py (Flush) + services/live_session.py (RAM); "
    "liest Uebernahme-Scoring (Post-Launch)."
)


def upgrade() -> None:
    # ── Schild-Aktualisierung (COMMENT ON COLUMN/TABLE — KEIN Schema-Aenderung) ──────────────
    # 3 Spalten + Tabelle von '[DEFERRED] NICHT in TAXO2' auf 'befuellt ab TAXO2 LLM-Uebernahme-Call'.
    # Einfache Quotes im Schild-Text sind in der Python-String-Konkatenation bereits nicht vorhanden;
    # hauseigenes Muster: op.execute("COMMENT ON ... IS '" + text + "'").

    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.adoption_value IS "
        "'" + _COMMENT_ADOPTION_VALUE_NEW + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.following_utterance_ref IS "
        "'" + _COMMENT_FOLLOWING_UTTERANCE_REF_NEW + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.reaction_class IS "
        "'" + _COMMENT_REACTION_CLASS_NEW + "'"
    )
    op.execute(
        "COMMENT ON TABLE public.suggestion_reactions IS "
        "'" + _COMMENT_TABLE_NEW + "'"
    )


def downgrade() -> None:
    # Schilder zurueck auf 0019-ALT-Texte (wortgleich aus 0019 Z.87/101-103).
    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.adoption_value IS "
        "'" + _COMMENT_ADOPTION_VALUE_OLD + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.following_utterance_ref IS "
        "'" + _COMMENT_FOLLOWING_UTTERANCE_REF_OLD + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.suggestion_reactions.reaction_class IS "
        "'" + _COMMENT_REACTION_CLASS_OLD + "'"
    )
    op.execute(
        "COMMENT ON TABLE public.suggestion_reactions IS "
        "'" + _COMMENT_TABLE_OLD + "'"
    )
