"""Phase 08.23.2.KOSTEN-1 R1 — Schild-Nachzug api_rates + price_change_log (Punkt 23).

Reines COMMENT-Update, keine Struktur-, keine Daten-Aenderung.

WARUM: KOSTEN-1 R1b aendert den Schreib-Pfad beider Tabellen — damit werden die alten
Schilder unvollstaendig, und ein unvollstaendiges Schild ist laut Punkt 23 schlimmer als
keines (es behauptet eine Wahrheit, die nicht mehr stimmt):

  * `api_rates`: bisher stand dort nur "Schreibt Admin-Rate-Pflege". Ab R1b ist der
    Haupt-Schreiber der Startup-Seed `app._seed_api_rates` (Liste `_API_RATE_SOLL`) —
    die beiden alten Seeds (08.14 in `_migrate()`, PG-tot; Seed A mit `count()==0`-Guard)
    sind entfernt. Zusaetzlich fehlte der wichtigste Leser-Hinweis: `cost_tracker.py:105-108`
    verwirft einen Call STILL, wenn hier keine aktive Rate steht — genau das Leck der Phase.
  * `price_change_log`: bekommt mit dem Seed einen ZWEITEN Schreiber (bisher nur die
    Admin-Route). Bleibt ansonsten write-only/[ZOMBIE] — es gibt weiterhin keinen Leser.

Der SCHILD-Guard (`tests/test_schild_guard.py`) prueft nur Vorhandensein + Laenge, NICHT
Aktualitaet — dieser Nachzug ist deshalb Handarbeit im selben Commit wie die Code-Aenderung.

Spiegelt models.py (`ApiRate.__table_args__` / `PriceChangeLog.__table_args__`) wortgleich.
"""
from alembic import op

# ACHTUNG fuer AUTH-3: dessen Bauplan reserviert "0034" fuer skip_billing. AUTH-3 ist noch
# NICHT gebaut, deshalb nimmt dieser Schild-Nachzug die 0034 und skip_billing wird 0035.
revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


_API_RATES_NEU = (
    'Aktuelle API-Preise pro Provider/Modell, editierbar, historisch via active-Flag. '
    'Preispflege ist MANUELL (gepflegte Liste + Admin-UI), keine Sync-Engine. Status: lebt. '
    'Schreibt app.py _seed_api_rates (Startup-Seed, Liste _API_RATE_SOLL) + '
    'routes/admin_dashboard.py:411-438 (Admin-Preiswechsel); liest services/cost_tracker.py:105-108 '
    '(Rate pro geloggtem Call; fehlt sie, wird der Call STILL verworfen) + '
    'routes/admin_dashboard.py (Founder-Dashboard).'
)
_API_RATES_ALT = (
    'Aktuelle API-Preise pro Provider/Modell, editierbar, historisch via active-Flag. Status: lebt. '
    'Schreibt Admin-Rate-Pflege; liest Cost-Berechnung (api_cost_log) + Dashboard.'
)

_PCL_NEU = (
    'Erkannte API-Preisaenderungen mit Impact-Berechnung (Historie-Spur zu api_rates). '
    'Status: write-only [ZOMBIE] — kein Reader. Schreibt routes/admin_dashboard.py:434 '
    '(Admin-Preiswechsel) + app.py _seed_api_rates (Startup-Seed, wenn die Soll-Liste einen '
    'Preis korrigiert).'
)
_PCL_ALT = (
    'Manuell erkannte API-Preisaenderungen mit Impact-Berechnung. Status: write-only [ZOMBIE]. '
    'Schreibt routes/admin_dashboard.py:434; kein Reader.'
)


def _comment(table: str, text: str) -> None:
    op.execute("COMMENT ON TABLE {} IS '{}'".format(table, text.replace("'", "''")))


def upgrade():
    _comment('api_rates', _API_RATES_NEU)
    _comment('price_change_log', _PCL_NEU)


def downgrade():
    _comment('api_rates', _API_RATES_ALT)
    _comment('price_change_log', _PCL_ALT)
