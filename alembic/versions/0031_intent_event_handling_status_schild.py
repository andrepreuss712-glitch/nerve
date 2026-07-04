"""Phase 08.23.2.PERSID Plan 02 — S7: intent_event.handling_status Schild-Aktualisierung.

Punkt 23 (Aktualitaets-Pflicht): F2-Stilllegung (PERSID Req 8) fuehrt 'not_gradable'
als neuen terminal handling_status ein (services/slow_lane.py _persist_event_ref).
Das DB-Schild (pg_description) fuer intent_event.handling_status nennt bisher nur
'(pending|scored|abstained|failed)' — mit diesem Deploy tritt 'not_gradable' in den
Live-Pfad ein. Ein Schild, das einen aktiven Status verschweigt, taeuscht eine falsche
Wahrheit vor (Punkt 23 Aktualitaets-Pflicht: schlimmer als kein Schild).

Diese Migration gleicht AUSSCHLIESSLICH das DB-Schild an (COMMENT ON COLUMN) — KEIN
Schema-Aenderung. COMMENT ist deklarativ ueberschreibend (idempotent). Single-Source
(Punkt 23): WORTGLEICH zum models.py comment=-Wert nach dem PERSID-02-Commit.

down_revision = '0030' (Prod-HEAD nach HANDLING-TIMING-Plan-04-Deploy).

Revision ID: 0031
Revises: 0030
"""
from alembic import op

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade():
    # S7 Punkt 23: not_gradable in Wertebereich aufnehmen + Schreiber/Leser-Liste aktualisieren.
    op.execute(
        "COMMENT ON COLUMN intent_event.handling_status IS "
        "'INTERLOCK I-1: Verarbeitungs-Status der Slow-Lane-Benotung "
        "(pending|scored|abstained|failed|not_gradable). TAXO2-Wurzel-Fix gegen dreifach-ueberladene NULL. "
        "Arbeitsliste = WHERE handling_status=''pending''; abstained/failed/not_gradable = abgeschlossen. "
        "not_gradable = F2-Stilllegung (PERSID Req 8): per-Ereignis-Benoter tot, drainet auf 0 deadlock-frei. "
        "Schreibt services/slow_lane.py (_persist_event_ref); liest services/slow_lane.py (_pending_events, Merge-Gate).'"
    )


def downgrade():
    # Alten Schild-Text aus vor PERSID-02 wiederherstellen.
    op.execute(
        "COMMENT ON COLUMN intent_event.handling_status IS "
        "'INTERLOCK I-1: Verarbeitungs-Status der Slow-Lane-Benotung "
        "(pending|scored|abstained|failed). TAXO2-Wurzel-Fix gegen dreifach-ueberladene NULL. "
        "Arbeitsliste = WHERE handling_status=''pending''; abstained/failed = abgeschlossen. "
        "In TAXO1 leer/''pending'' (Default), KEIN Status-Schreib-Code hier — TAXO2 setzt die Werte.'"
    )
