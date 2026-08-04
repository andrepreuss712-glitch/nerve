"""ttft_ms fuer api_cost_log + Schild-Nachzug (Punkt 23)

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-03

Phase 08.23.2.MESSGERAETE-1. Streaming-Pfade brauchen ZWEI Zahlen (D-03): latency_ms misst
bis zum LETZTEN Token, ttft_ms bis zum ERSTEN. Beide Bedeutungen in eine Spalte zu kippen
waere derselbe "Name luegt"-Fehler, der latency_e/latency_c unbrauchbar macht (D-02).

WARUM ALEMBIC UND NICHT _migrate(): app._migrate() RETURNT AUF POSTGRES FRUEH (app.py:140).
Die dortigen ALTER TABLE api_cost_log ADD COLUMN latency_ms/call_site (app.py:943-955) sind
der Legacy-SQLite-Pfad und auf Prod TOT — dokumentiert im Code selbst (app.py:955-962: der
Phase-08.14-ApiRate-Seed war aus genau diesem Grund auf Prod wirkungslos). Ein zusaetzlicher
_migrate()-Eintrag wird BEWUSST NICHT angelegt: es gibt keinen lokalen Dev-Pfad mehr
(CLAUDE.md "Kein Local-Dev"), und _migrate() ist das Alt-Muster (Punkt 29 — nie das
Alt-Muster fuer neuen Code kopieren).

Prod-Stand bei Planung (inspect.sh migrations, 2026-08-03): version_num = 0035.

Die Schild-Texte unten sind Modul-Konstanten und spiegeln database/models.py
(ApiCostLog.__table_args__ bzw. die comment=-Texte) ZEICHENGLEICH (Punkt 23, T-MESS-01).
Kein Backfill und kein nachtraegliches Umschreiben von Bestandszeilen (D-02, Finanzamt-Linie,
T-MESS-03) — upgrade() legt ausschliesslich die Spalte an und zieht die Schilder nach.
"""
from alembic import op
import sqlalchemy as sa

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None

_TABELLE_NEU = 'Jeder API-Call mit eingefrorenem Wechselkurs und Rate (Founder Cost Dashboard, steuerlich korrekt). Status: lebt. Schreibt ausschliesslich services/cost_tracker.py log_api_cost (gerufen aus services/claude_service.py sieben Live-Pfaden, coaching_service.py, precall_service.py, qa_pipeline.py, deepgram_service.py, training_service.py, crm_service.py, judge_runner.py, adoption_runner.py, outcome_service.py, routes/dashboard.py, routes/payments.py, routes/training.py, nerve_rt/services/session_manager.py, nerve_rt/services/llm/claude_adapter.py); liest routes/admin_dashboard.py (Founder-Dashboard: Tab Ausgaben inkl. Live-KI-Auswertung je context_tag, CSV-Export) + services/eur_calculator.py (EUER). latency_ms/ttft_ms tragen die Dauer NUR an der input-Token-Buchung (D-07).'

_TABELLE_ALT = (
    'Jeder API-Call mit eingefrorenem Wechselkurs und Rate (Founder Cost Dashboard, '
    'steuerlich korrekt). Status: lebt. Schreibt API-Call-Wrapper in services/; '
    'liest Founder-Cost-Dashboard.'
)

_TTFT_SCHILD = 'Zeit bis zum ERSTEN Token in ms. Nur Streaming-Pfade (pip_autovar, pip_variante), nur an der input-Token-Buchung; bei blockierenden Aufrufen immer NULL. Getrennte Spalte, weil latency_ms bis zum letzten Token misst — beide Bedeutungen in EINE Spalte zu kippen waere der Name-luegt-Fehler (D-03).'

_LATENCY_SCHILD_NEU = 'Reine API-Dauer in ms bis zum LETZTEN Token. Nur an der input-Token-Buchung gesetzt (D-07: eine API-Antwort zaehlt genau einmal), Cache-/Output-Buchungen bleiben NULL. NICHT identisch mit latency_e/latency_c aus live_session (die enthalten Puffer-Wartezeit + QA-Dispatch).'

_LATENCY_SCHILD_ALT = 'API-Latenz in ms'


def _comment(objekt: str, text: str) -> None:
    op.execute("COMMENT ON {} IS '{}'".format(objekt, text.replace("'", "''")))


def upgrade():
    op.add_column('api_cost_log', sa.Column('ttft_ms', sa.Integer(), nullable=True))
    _comment('COLUMN api_cost_log.ttft_ms', _TTFT_SCHILD)
    _comment('COLUMN api_cost_log.latency_ms', _LATENCY_SCHILD_NEU)
    _comment('TABLE api_cost_log', _TABELLE_NEU)


def downgrade():
    _comment('TABLE api_cost_log', _TABELLE_ALT)
    _comment('COLUMN api_cost_log.latency_ms', _LATENCY_SCHILD_ALT)
    op.drop_column('api_cost_log', 'ttft_ms')
