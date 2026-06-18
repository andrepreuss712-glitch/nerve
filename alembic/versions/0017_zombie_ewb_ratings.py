"""TAXO1-Welle 5: ewb_ratings -> zombie_ewb_ratings (§0.1 Zombie-Rename).

Reine Tabellen-Umbenennung (0 Zeilen) + [ZOMBIE]-Schild. KEIN DROP — die Tabelle
gehoert thematisch zur Noten-Engine TAXO2 und schlaeft bis dahin; Rename statt Drop
ist die Rueckhol-Sicherung (downgrade benennt zurueck). Index/UNIQUE wandern automatisch
mit ALTER TABLE ... RENAME (relation-OID bleibt). Spalten-COMMENTs (Migration 0015)
ueberleben den Rename unveraendert; nur das Tabellen-Schild wird auf [ZOMBIE] gesetzt.

Hand-geschrieben (op.execute — hauseigenes Muster aller Migrationen, SCHILD-Praezedenz 0015/0016).
Migration laeuft als postgres (Rename auf public; Owner bleibt nerve_app). COMMENT-Text =
Single-Source = models.py comment= (EwbRating).

Revision ID: 0017
Revises: 0016
"""
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


# Single-Source mit models.py EwbRating.__table_args__ comment (Punkt 21 ORM/DDL-Konsistenz)
ZOMBIE_COMMENT = (
    "Manuelle EWB-Qualitaets-Bewertungen (3 binaere Kriterien) pro EWB einer Session, "
    "fuer Quality-Score. Status: [ZOMBIE] — gehoert zur Noten-Engine TAXO2, schlaeft. "
    "Schreibt+liest routes/admin_ewb.py (umgestellt, TAXO1-Welle 5)."
)
# Original-Schild (Migration 0015) fuer den downgrade-Pfad.
LIVE_COMMENT = (
    "Manuelle EWB-Quality-Ratings (3 binaere Kriterien) pro EWB einer Session, "
    "fuer Quality-Score. Status: lebt. Schreibt routes/admin_ewb.py:192; "
    "liest routes/admin_ewb.py:65/181."
)


def upgrade() -> None:
    # Rename (Index/UNIQUE/Spalten-COMMENTs wandern mit; Owner bleibt nerve_app).
    op.execute("ALTER TABLE public.ewb_ratings RENAME TO zombie_ewb_ratings")
    # Tabellen-Schild auf [ZOMBIE] umstellen (einfache Quotes verdoppelt — keine im Text).
    op.execute(
        "COMMENT ON TABLE public.zombie_ewb_ratings IS '%s'"
        % ZOMBIE_COMMENT.replace("'", "''")
    )


def downgrade() -> None:
    # Reversibel: zurueckbenennen + Original-Schild wiederherstellen (kein Datenverlust).
    op.execute("ALTER TABLE public.zombie_ewb_ratings RENAME TO ewb_ratings")
    op.execute(
        "COMMENT ON TABLE public.ewb_ratings IS '%s'"
        % LIVE_COMMENT.replace("'", "''")
    )
