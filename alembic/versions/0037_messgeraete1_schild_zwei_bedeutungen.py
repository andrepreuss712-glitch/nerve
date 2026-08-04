"""latency_ms/ttft_ms: Schild-Wortlaut auf ZWEI Bedeutungen korrigiert (Punkt 23)

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-04

Phase 08.23.2.MESSGERAETE-1, Nachzug nach dem Code-Review dieser Phase (Befund WR-01).

WAS FALSCH WAR: 0036 setzte "Reine API-Dauer in ms bis zum LETZTEN Token". Fuer die sechs
blockierenden Pfade stimmt das. Fuer die beiden Stream-Pfade (pip_variante, pip_autovar)
stimmt es NICHT: dort liegt der per-Token-Versand (sio.emit) im Messfenster, und weil die App
mit async_mode=threading laeuft (app.py:47), ist jedes emit ein echter send-Syscall — keine
RAM-Anhaengung. Bei Gegendruck vom Browser steigt die Zahl, obwohl das Modell gleich schnell war.

WARUM NUR DER WORTLAUT UND NICHT DER CODE: das emit aus dem Messfenster zu ziehen hiesse, einen
funktionierenden Live-Pfad umzubauen (CLAUDE.md Punkt 25). Und fuer die Frage, die das Dashboard
beantworten soll ("ist das starke Modell schnell genug?"), ist die Zahl inklusive Auslieferung
sogar die ehrlichere — sie liegt naeher an dem, was der Berater spuert. Falsch war allein die
Behauptung "reine API-Dauer", nicht die Messung.

Das ist exakt die Fehlerklasse, gegen die D-02/D-03 in dieser Phase gebaut wurden: latency_e und
latency_c sind unbrauchbar geworden, weil ihr Name etwas anderes behauptet als ihr Inhalt. Ein
Schild, das nicht stimmt, ist nach Punkt 23 NUTZLOS — schlimmer als kein Schild.

ZWEITE HAELFTE DER KORREKTUR (nicht in dieser Migration, sondern im Code): pg_description liest
niemand beim Draufschauen. Die Ansicht markiert die Stream-Zeilen deshalb sichtbar mit einem
Zeichen plus Klartext-Fussnote (templates/admin/_tab_ausgaben.html), Quelle ist
services/cost_tracker.py::STREAM_CONTEXT_TAGS.

Die Texte unten spiegeln database/models.py (comment=) ZEICHENGLEICH (Punkt 23).
Reine COMMENT-Migration: kein DDL an Daten, kein Backfill, keine Spaltenaenderung.
"""
from alembic import op

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None

_LATENCY_NEU = 'Dauer des KI-Aufrufs in ms bis zum LETZTEN Token. ACHTUNG, zwei Bedeutungen: bei den beiden Stream-Pfaden (pip_variante, pip_autovar) INKLUSIVE der Auslieferung an den Browser, weil der per-Token-Versand (sio.emit, async_mode=threading) im Messfenster liegt; bei den sechs blockierenden Pfaden reine API-Dauer. Bewusst so gelassen (Punkt 25: kein Umbau eines funktionierenden Live-Pfads); die Ansicht markiert die Stream-Zeilen sichtbar. Nur an der input-Token-Buchung gesetzt (D-07: eine API-Antwort zaehlt genau einmal), Cache-/Output-Buchungen bleiben NULL. NICHT identisch mit latency_e/latency_c aus live_session (die enthalten Puffer-Wartezeit + QA-Dispatch).'

_TTFT_NEU = 'Zeit bis zum ERSTEN Token in ms, im selben Messrahmen wie latency_ms — also inklusive der Auslieferung dieses ersten Tokens an den Browser. Nur Streaming-Pfade (pip_autovar, pip_variante), nur an der input-Token-Buchung; bei blockierenden Aufrufen immer NULL. Getrennte Spalte, weil latency_ms bis zum letzten Token misst — beide Bedeutungen in EINE Spalte zu kippen waere der Name-luegt-Fehler (D-03).'

# Die Fassung aus 0036 — fuer downgrade().
_LATENCY_ALT = 'Reine API-Dauer in ms bis zum LETZTEN Token. Nur an der input-Token-Buchung gesetzt (D-07: eine API-Antwort zaehlt genau einmal), Cache-/Output-Buchungen bleiben NULL. NICHT identisch mit latency_e/latency_c aus live_session (die enthalten Puffer-Wartezeit + QA-Dispatch).'

_TTFT_ALT = 'Zeit bis zum ERSTEN Token in ms. Nur Streaming-Pfade (pip_autovar, pip_variante), nur an der input-Token-Buchung; bei blockierenden Aufrufen immer NULL. Getrennte Spalte, weil latency_ms bis zum letzten Token misst — beide Bedeutungen in EINE Spalte zu kippen waere der Name-luegt-Fehler (D-03).'


def _comment(objekt: str, text: str) -> None:
    op.execute("COMMENT ON {} IS '{}'".format(objekt, text.replace("'", "''")))


def upgrade():
    _comment('COLUMN api_cost_log.latency_ms', _LATENCY_NEU)
    _comment('COLUMN api_cost_log.ttft_ms', _TTFT_NEU)


def downgrade():
    _comment('COLUMN api_cost_log.latency_ms', _LATENCY_ALT)
    _comment('COLUMN api_cost_log.ttft_ms', _TTFT_ALT)
