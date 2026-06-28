"""Phase 08.23.2.TAXO2.HANDLING-TIMING Plan 01 — calls.transcript_resolved (Bewerter-Anstoss-Fan-In).

Fan-In-Anstoss-Signal fuer den LLM-Verhaltens-Bewerter: TRUE sobald das Transkript am Call-Ende
festgeschrieben ist (Segmente geschrieben ODER bewiesen leer = resolved-als-absent). Der
Judge-Anstoss (slow_lane Call-Ende-Schritt) wartet darauf, BEVOR er das Transkript an Sonnet gibt
— verhindert die Race, in der gegen ein noch nicht geschriebenes Transkript bewertet wird (Punkt 26,
dieselbe Klasse wie der Audio-Race in 0027).

Transkript-Segmente werden gebuendelt am Call-Ende geschrieben (batch, alle created_at identisch
~25-58s nach Einwand-Emit). Laeuft der Judge-Anstoss bevor dieser Batch abgeschlossen ist, liest er
ein leeres oder unvollstaendiges Transkript und bewertet still-falsch (kein Fehler im Log). Dieses
Flag loest das Problem analog zu audio_health_resolved (0027).

create_all-Falle: Migration als postgres VOR Restart (deploy.sh macht keine Prod-Migration),
Muster wie 0020-0027. Idempotent: ADD COLUMN IF NOT EXISTS. Prod-HEAD beim Execute = 0027
(inspect.sh migrations 2026-06-28, CONTEXT-Beleg) -> down_revision='0027'.

Revision ID: 0028
Revises: 0027
"""
from alembic import op

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent (re-run-sicher, hauseigenes op.execute/IF-NOT-EXISTS-Muster): das Flag setzt
    # Default FALSE auf alle Bestands-Zeilen (NOT NULL DEFAULT FALSE deckt das Backfill ab).
    op.execute(
        "ALTER TABLE public.calls "
        "ADD COLUMN IF NOT EXISTS transcript_resolved BOOLEAN NOT NULL DEFAULT FALSE"
    )
    # SCHILD (Punkt 23, nicht-trivialer State-Flag, Single-Source == models.py comment=).
    op.execute(
        "COMMENT ON COLUMN public.calls.transcript_resolved IS "
        "'Fan-In-Anstoss-Signal fuer den LLM-Verhaltens-Bewerter (Beobachtung statt Note): TRUE sobald "
        "das Transkript am Call-Ende festgeschrieben ist (Segmente geschrieben ODER bewiesen leer = "
        "resolved-als-absent). Der Judge-Anstoss (slow_lane Call-Ende-Schritt) wartet darauf, BEVOR er "
        "das Transkript an Sonnet gibt — verhindert die Race, in der gegen ein noch nicht geschriebenes "
        "Transkript bewertet wird (Punkt 26, analog audio_health_resolved). Status: lebt (TAXO2 LLM-Bewerter). "
        "Schreibt routes/app_routes.py (api_beenden); liest services/slow_lane.py (Judge-Anstoss-Gate + Merge-Gate).'"
    )
    # TABELLEN-Schild aktualisieren (Punkt 23 Aktualitaet): neuen Schreiber (api_beenden transcript_resolved)
    # + neuen Leser (slow_lane Judge-Anstoss-Gate) erganzen. Single-Source == models.py __table_args__ comment=.
    op.execute(
        "COMMENT ON TABLE public.calls IS "
        "'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-"
        "Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ "
        "der neuen Call-Pipeline; audio_health_resolved geschrieben routes/app_routes.py (api_beenden/"
        "_audio_health_bg), gelesen services/slow_lane.py (Call-Ende-Merge-Gate, TAXO2-04 Audio-Race-Fix); "
        "transcript_resolved geschrieben routes/app_routes.py (api_beenden), gelesen services/slow_lane.py "
        "(LLM-Judge-Anstoss-Gate + Merge-Gate).'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.calls DROP COLUMN IF EXISTS transcript_resolved")
    # TABELLEN-Schild auf den Vor-0028-Stand zuruecksetzen (mit audio_health_resolved, OHNE transcript_resolved).
    op.execute(
        "COMMENT ON TABLE public.calls IS "
        "'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-"
        "Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ "
        "der neuen Call-Pipeline; audio_health_resolved geschrieben routes/app_routes.py (api_beenden/"
        "_audio_health_bg), gelesen services/slow_lane.py (Call-Ende-Merge-Gate, TAXO2-04 Audio-Race-Fix).'"
    )
