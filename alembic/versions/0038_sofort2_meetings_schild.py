"""crm.meetings + crm.meetings.call_id: Schild nennt den echten Schreiber (Punkt 23)

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-05

Phase 08.23.2.SOFORT-2, Plan 09 Task 3 — Nachzug zum R-7-Fix im selben Commit.

WAS FALSCH WAR: das Tabellen-Schild nannte "Schreibt/liest services/crm_service.py +
routes/app_routes.py". Der Schreiber dieser Zeilen ist aber routes/crm_export.py::save_meeting
(POST /crm/meetings) — er fehlte. Ein Schild, das nicht alle Schreiber nennt, ist nach
CLAUDE.md Punkt 23 NUTZLOS, schlimmer als kein Schild, weil es eine falsche Wahrheit
vortaeuscht. Und die Leser-Behauptung fehlte ganz: die Spalte call_id wird zu 100 % befuellt
(Production 2026-08-05: 13 von 13 Zeilen), hat aber KEINEN Leser im Code — das gehoert ins
Schild, damit ein spaeterer Konsument weiss, worauf er sich einlaesst.

WAS SICH AM SCHREIB-PFAD GEAENDERT HAT (der Ausloeser der Aktualitaets-Pflicht): save_meeting
prueft die geposteten call_id seit dieser Phase VOR dem Insert gegen den Besitzer
(services/live_session.py::call_belongs_to, eigener Anruf ODER gleicher Mandant). Vorher
wanderte eine beliebige fremde call_id ungeprueft als Fremdreferenz in die eigene Zeile — die
RLS auf crm.* schuetzt die ZEILE mandantenweise, NICHT die Fremdreferenz darin.

Die Leser-Aussage ist grep-belegt, nicht abgeschrieben (2026-08-05):
  grep -rn "Meeting\\.call_id|meetings\\.call_id|m\\.call_id" routes/ services/ scripts/ database/
  -> 2 Treffer, BEIDE in Kommentaren/Docstrings (routes/crm_export.py:148,
     services/live_session.py:512). Kein Code-Leser.

Die Texte unten spiegeln database/models.py (comment=) ZEICHENGLEICH (Punkt 23).
Reine COMMENT-Migration: kein DDL an Daten, kein Backfill, keine Spaltenaenderung.
"""
from alembic import op

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

_TABELLE_NEU = 'Termin-/Meeting-Datensaetze je Tenant (PiP-Termin-Form, G-MEET). Status: lebt (crm, RLS-isoliert, tenant_isolation FORCE). Schreibt routes/crm_export.py::save_meeting (POST /crm/meetings, seit 08.23.2.SOFORT-2 mit Besitzpruefung der call_id) + services/crm_service.py + routes/app_routes.py; liest bislang KEIN Produktionspfad.'

_SPALTE_NEU = 'Soft-Link zu public.calls.id, KEIN FK (D-08). Wird beim Speichern gegen den Besitzer geprueft (services/live_session.py::call_belongs_to, eigener Anruf ODER gleicher Mandant) — vorher wurde der geposteten Wert ungeprueft uebernommen. Status: wird befuellt, hat KEINEN Leser.'

# Die Fassung aus 0015 — fuer downgrade() (verbatim aus inspect.sh schilder meetings, 2026-08-05).
_TABELLE_ALT = 'Termin-/Meeting-Datensaetze je Tenant (PiP-Termin-Form, G-MEET). Status: lebt (crm, RLS-isoliert). Schreibt/liest services/crm_service.py + routes/app_routes.py.'

_SPALTE_ALT = 'Soft-Link zu public.calls.id, KEIN FK (D-08)'


def _q(text: str) -> str:
    """Einfache Anfuehrungszeichen fuer das SQL-Literal verdoppeln."""
    return text.replace("'", "''")


def upgrade():
    op.execute("COMMENT ON TABLE crm.meetings IS '{}'".format(_q(_TABELLE_NEU)))
    op.execute("COMMENT ON COLUMN crm.meetings.call_id IS '{}'".format(_q(_SPALTE_NEU)))


def downgrade():
    op.execute("COMMENT ON TABLE crm.meetings IS '{}'".format(_q(_TABELLE_ALT)))
    op.execute("COMMENT ON COLUMN crm.meetings.call_id IS '{}'".format(_q(_SPALTE_ALT)))
