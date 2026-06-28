"""Phase 08.23.2.TAXO2.HANDLING-TIMING Plan 02 — rubric_score Schema-Umwidmung.

Erweitert rubric_score um zwei JSONB-Spalten fuer den LLM-Verhaltens-Bewerter
(Beobachtung statt Note, Soll-Verhalten §6):
  - observations_jsonb: Beobachtungen + woertliche Beleg-Zitate je fester Dimension
    (Form {dim_key:[{beobachtung,beleg_zitat}]}). Sichtbar fuer den Nutzer.
  - ratings_jsonb: INTERNE grobe Auspraegung schwach/ok/stark je Dimension
    (Form {dim_key:schwach|ok|stark}). NIE an den Nutzer ausgegeben.

Die alten Noten-Spalten (coaching_score, measured_weight_pct, unmeasured_dimensions,
dimensions, is_provisional) BLEIBEN als Spalten (kein blindes Drop, Punkt 20) aber
werden als write-stopped markiert — der LLM-Bewerter (Plan 03) befuellt sie NICHT mehr.

Compliance-Flag compliance_violation (Cross-AI-Finding 2) reitet in observations_jsonb
als JSONB-Schluessel — KEINE neue Spalte (least-migration).

down_revision = '0028' (Prod-HEAD nach Plan-01-Deploy, verifiziert per glob).
Idempotent: ADD COLUMN IF NOT EXISTS.

Revision ID: 0029
Revises: 0028
"""
from alembic import op

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

# ── Schild-Texte (Single-Source == database/models.py comment=, wortgleich) ───────────────────

_COMMENT_OBSERVATIONS_JSONB = (
    "Beobachtungen + WOERTLICHE Beleg-Zitate je fester Dimension (LLM-Verhaltens-Bewerter, "
    "Beobachtung statt Note). Form {dim_key:[{beobachtung,beleg_zitat}]}. SICHTBAR fuer den "
    "Nutzer (als KI-Einschaetzung gelabelt). Status: lebt (TAXO2 LLM-Bewerter). "
    "Schreibt services/judge_runner.py; liest routes/dashboard.py (Preview)."
)

_COMMENT_RATINGS_JSONB = (
    "INTERNE grobe Auspraegung schwach/ok/stark je Dimension (Lern-Signal, Soll-Verhalten §6). "
    "NIE an den Nutzer ausgegeben. Form {dim_key:schwach|ok|stark}. "
    "Status: lebt (TAXO2 LLM-Bewerter, intern). "
    "Schreibt services/judge_runner.py; liest spaeter Korrelation/Lernen (post-Launch)."
)

_WRITE_STOP_SUFFIX = (
    " [ALT-Marker-Engine, write-stop ab LLM-Bewerter TAXO2 — nicht mehr befuellt; "
    "Cutover services/slow_lane.py Plan 03; nicht geloescht (Foundation-Register/Punkt 20)]."
)

_COMMENT_COACHING_SCORE_ALT = (
    "Gesamt-Kopf-Zahl (0-100). NULL wenn <50% Gewicht messbar (Proration, D-02) oder "
    "not_gradable (D-09). Spiegel von calls.coaching_score (Plan 04)."
    + _WRITE_STOP_SUFFIX
)

_COMMENT_IS_PROVISIONAL_ALT = (
    "Vorlaeufig-Marker (D-08): Score ueber der 50%-Schwelle aber mit weggeprorateten "
    "Dimensionen. Anzeige 999.2."
    + _WRITE_STOP_SUFFIX
)

_COMMENT_MEASURED_WEIGHT_ALT = (
    "Anteil messbaren Gewichts am modus-konfigurierten Maximum (D-02/D-08). "
    "<0.5 -> coaching_score NULL."
    + _WRITE_STOP_SUFFIX
)

_COMMENT_UNMEASURED_ALT = (
    "Liste der nicht gewerteten Dimensionen + Grund (n/a vs vergeigt, D-08). "
    "Goldstaub fuer 999.2-Erklaerung + ML."
    + _WRITE_STOP_SUFFIX
)

_COMMENT_DIMENSIONS_ALT = (
    "Volle Aufschluesselung pro Dimension (D-05/Req 5): je Dim {score, weight, available, "
    "sample_size, beleg_ref, marker[]}. Beleg-Referenz = Transkript-/intent_event-Verweis, "
    "KEIN freier LLM-Text."
    + _WRITE_STOP_SUFFIX
)

_COMMENT_TABLE = (
    "Beobachtungen + Beleg-Zitate + interne Auspraegung (LLM-Bewerter, Soll-Verhalten §6), "
    "nicht mehr maschinelle Note. Eine Zeile pro bewerteter Call/Session. "
    "Hybrid: indizierte Kern-Spalten + observations_jsonb/ratings_jsonb + payload_jsonb. "
    "call_id harter FK CASCADE (F-08/DD-01). Partieller Unique-Index (call_id, origin=live) "
    "fuer idempotenten Upsert (F-03). FORCE ROW LEVEL SECURITY (D-11). "
    "Status: lebt (TAXO2 LLM-Bewerter). "
    "Schreibt services/judge_runner.py (Plan 03); liest routes/dashboard.py (Preview Plan 05)."
)


def upgrade() -> None:
    # ── Neue Spalten (idempotent) ──────────────────────────────────────────────────────────────

    op.execute(
        "ALTER TABLE public.rubric_score "
        "ADD COLUMN IF NOT EXISTS observations_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE public.rubric_score "
        "ADD COLUMN IF NOT EXISTS ratings_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb"
    )

    # ── Schilder neue Spalten (Punkt 23, Single-Source == models.py comment=) ─────────────────

    op.execute(
        "COMMENT ON COLUMN public.rubric_score.observations_jsonb IS "
        "'" + _COMMENT_OBSERVATIONS_JSONB + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.ratings_jsonb IS "
        "'" + _COMMENT_RATINGS_JSONB + "'"
    )

    # ── Schilder ALT-Engine-Spalten (write-stop-Markierung, Punkt 20/23) ──────────────────────

    op.execute(
        "COMMENT ON COLUMN public.rubric_score.coaching_score IS "
        "'" + _COMMENT_COACHING_SCORE_ALT + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.is_provisional IS "
        "'" + _COMMENT_IS_PROVISIONAL_ALT + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.measured_weight_pct IS "
        "'" + _COMMENT_MEASURED_WEIGHT_ALT + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.unmeasured_dimensions IS "
        "'" + _COMMENT_UNMEASURED_ALT + "'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.dimensions IS "
        "'" + _COMMENT_DIMENSIONS_ALT + "'"
    )

    # ── Tabellen-Schild aktualisieren (Punkt 23 Aktualitaet) ──────────────────────────────────

    op.execute(
        "COMMENT ON TABLE public.rubric_score IS "
        "'" + _COMMENT_TABLE + "'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.rubric_score DROP COLUMN IF EXISTS observations_jsonb")
    op.execute("ALTER TABLE public.rubric_score DROP COLUMN IF EXISTS ratings_jsonb")

    # ALT-Spalten-Schilder auf Vor-0029-Stand zuruecksetzen (ohne write-stop-Suffix)
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.coaching_score IS "
        "'Gesamt-Kopf-Zahl (0-100). NULL wenn <50% Gewicht messbar (Proration, D-02) oder "
        "not_gradable (D-09). Spiegel von calls.coaching_score (Plan 04).'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.is_provisional IS "
        "'Vorlaeufig-Marker (D-08): Score ueber der 50%-Schwelle aber mit weggeprorateten "
        "Dimensionen. Anzeige 999.2.'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.measured_weight_pct IS "
        "'Anteil messbaren Gewichts am modus-konfigurierten Maximum (D-02/D-08). "
        "<0.5 -> coaching_score NULL.'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.unmeasured_dimensions IS "
        "'Liste der nicht gewerteten Dimensionen + Grund (n/a vs vergeigt, D-08). "
        "Goldstaub fuer 999.2-Erklaerung + ML.'"
    )
    op.execute(
        "COMMENT ON COLUMN public.rubric_score.dimensions IS "
        "'Volle Aufschluesselung pro Dimension (D-05/Req 5): je Dim {score, weight, available, "
        "sample_size, beleg_ref, marker[]}. Beleg-Referenz = Transkript-/intent_event-Verweis, "
        "KEIN freier LLM-Text.'"
    )

    # Tabellen-Schild auf Vor-0029-Stand zuruecksetzen
    op.execute(
        "COMMENT ON TABLE public.rubric_score IS "
        "'Single Source der Benotung (BARS + Proration), Live + Training. Eine Zeile pro "
        "bewerteter Call/Session. Hybrid: indizierte Kern-Spalten + payload_jsonb. "
        "call_id harter FK CASCADE (F-08/DD-01). Partieller Unique-Index (call_id, origin=live) "
        "fuer idempotenten Upsert (F-03). Status: lebt (neu, TAXO2). "
        "Schreibt services/slow_lane.py (Engine, Plan 02/04); "
        "liest routes/dashboard.py + performance.py (999.2).'"
    )
