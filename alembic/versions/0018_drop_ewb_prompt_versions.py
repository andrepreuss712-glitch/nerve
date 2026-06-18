"""Welle 6 (Aufraeumen): prompt_versions module='ewb' (v1-legacy/v2-modular) entfernen.

Toter EWB-Prompt-Pfad: build_ewb_prompt hat nach dem MEDFIX (SYSTEM_PROMPT_BASE)
0 lebende Aufrufer (grep-belegt). services/ewb_pipeline.py + app.py _seed_ewb_v2
(der idempotente Seeder dieser Rows) sind im selben Aufräum-Commit entfernt — ohne
das waeren die Rows beim naechsten Boot wieder da.

KEIN FK referenziert prompt_versions.id (grep-belegt: kein prompt_version_id,
kein ForeignKey('prompt_versions...')) → die Rows sind reversibel loeschbar.

Idempotent: upgrade DELETE trifft bei Re-Run 0 Rows; downgrade INSERT ... ON CONFLICT
(version, module) DO NOTHING. Reversibel: downgrade fuegt die Rows mit den EXAKTEN
Seed-Werten (Source of Truth: das entfernte app.py _seed_ewb_v2) wieder ein.

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


# Exakte Seed-Werte (verbatim aus dem entfernten app.py _seed_ewb_v2) fuer den downgrade.
_V1_LEGACY_TEXT = (
    "Du bist NERVE, ein Vertriebs-KI-Assistent im Live-Call.\n\n"
    "Wenn ein Einwand kommt, liefere EINE konkrete, sofort vorlesbare "
    "Gegenargumentation in 2-3 Saetzen. Kein Fachjargon, keine Floskeln "
    "wie 'Ich verstehe vollkommen'. Ende mit Gegenfrage.\n"
)

_V2_MODULAR_TEXT = (
    "Du bist NERVE, ein Vertriebs-KI-Assistent im Live-Call.\n\n"
    "## Bausteine (Reihenfolge einhalten)\n"
    "1. ANKER: Kurz bestaetigen was der Kunde gesagt hat "
    "(kein 'Ich verstehe'-Floskel).\n"
    "2. REFRAME: Perspektivwechsel - stelle den Einwand in einen neuen Kontext.\n"
    "3. KERN-GEGENARGUMENT + BEWEIS: Ein konkretes Argument plus ein "
    "Beweis-Element (Zahlen, Fallstudie, Kundenzitat aus dem Profil).\n"
    "4. UEBERLEITUNG: Gegenfrage oder Alternativ-Close, "
    "der den Dialog zurueckholt.\n\n"
    "## Active Listening Block (D-47)\n"
    "- Reagiere auf konkrete Phrasen des Kunden, nicht auf Kategorien.\n"
    "- Wenn der Kunde korrigiert: korrigiere dich explizit "
    "('Danke fuer die Klarstellung, ...').\n"
    "- Wenn der Kunde ein Detail nennt: spiegele es zurueck "
    "bevor du argumentierst.\n"
    "- Bilde NIEMALS Hypothesen ueber Bedarf ohne Signal - frage nach.\n"
    "- Beachte Geschlechts-Hinweise im Vornamen und halte sie konsistent.\n\n"
    "## Harte Regeln\n"
    "- Max 45 Woerter pro Antwort.\n"
    "- NIEMALS apologetisch ('Ich verstehe, dass ...', 'Tut mir leid').\n"
    "- Anrede-Constraint aus Kontext-Block strikt einhalten.\n"
    "- Niemals Floskeln wie 'Das ist eine gute Frage'.\n"
)


def upgrade() -> None:
    # Idempotent: bei Re-Run sind die Rows schon weg → 0 betroffen.
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions "
            "WHERE module = 'ewb' AND version IN ('v1-legacy', 'v2-modular')"
        )
    )


def downgrade() -> None:
    # Reversibel + idempotent: exakte Seed-Werte, ON CONFLICT DO NOTHING.
    for version, ptext, is_default in [
        ('v1-legacy', _V1_LEGACY_TEXT, True),
        ('v2-modular', _V2_MODULAR_TEXT, False),
    ]:
        op.execute(
            sa.text(
                "INSERT INTO prompt_versions "
                "(version, module, prompt_text, changelog, is_active, is_default, created_at) "
                "VALUES (:v, 'ewb', :t, :c, true, :d, now()) "
                "ON CONFLICT (version, module) DO NOTHING"
            ).bindparams(v=version, t=ptext, c='Phase 08 Seed (%s)' % version, d=is_default)
        )
