"""Phase 08.23.2.TAXO2-04 Gap-Fix — calls.audio_health_resolved (Fan-In-Join-Flag, Audio-Race).

BUG (live verifiziert, 3-Sichten Claudian+Gemini): der Call-Ende-Merge (services/slow_lane.py)
las calls.audio_health_score, BEVOR der async _audio_health_bg-Thread (routes/app_routes.py:745,
gestartet in api_beenden) ihn geschrieben hatte -> Merge sah NULL -> setzte faelschlich
rubric_score.payload.reason='poor_audio_health' / status='not_gradable'. Verifiziert: Call
94d9e895... hat audio_health_score=0.93, aber rubric_score.payload.reason='poor_audio_health'.
Permanent, weil der idempotente UPSERT nie neu feuert.

WURZEL: audio_health_score wird async OHNE Ordering-Garantie ggue. dem Merge geschrieben; der
Merge kann 'NULL = noch nicht geschrieben' nicht von 'NULL = kein Buffer' unterscheiden.

FIX: ein explizites Fan-In-Join-Flag calls.audio_health_resolved. Der Audio-Thread (bzw.
api_beenden, wenn kein Buffer existiert) setzt es auf TRUE, NACHDEM er den Audio-Zustand
festgeschrieben hat, und re-triggert den Merge. Der Merge-Gate verlangt jetzt zusaetzlich
audio_health_resolved==TRUE — erst dann ist ein NULL-Audio-Score korrekt als 'wirklich kein
Audio' interpretierbar.

audio_health_resolved ist ein nicht-trivialer Zustands-Flag (passt NICHT in die is_*/aktiv-
Trivial-Konvention L-04) -> SCHILD-Pflicht (Punkt 23): COMMENT >=10 Zeichen, auch in models.py.

create_all-Falle: Migration als postgres VOR Restart (deploy.sh macht keine Prod-Migration),
Muster wie 0020-0026. Idempotent: ADD COLUMN IF NOT EXISTS. Prod-HEAD beim Execute = 0026
(inspect.sh migrations 2026-06-26) -> down_revision='0026'.

Revision ID: 0027
Revises: 0026
"""
from alembic import op

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent (re-run-sicher, hauseigenes op.execute/IF-NOT-EXISTS-Muster): das Flag setzt
    # die Default FALSE auf alle Bestands-Zeilen (NOT NULL DEFAULT FALSE deckt das Backfill ab).
    op.execute(
        "ALTER TABLE public.calls "
        "ADD COLUMN IF NOT EXISTS audio_health_resolved BOOLEAN NOT NULL DEFAULT FALSE"
    )
    # SCHILD (Punkt 23, nicht-trivialer State-Flag, Single-Source == models.py comment=).
    op.execute(
        "COMMENT ON COLUMN public.calls.audio_health_resolved IS "
        "'Fan-In-Join-Flag (TAXO2-04 Audio-Race-Fix): TRUE sobald der async Audio-Zustand "
        "endgueltig festgeschrieben ist (Score gesetzt ODER bewiesen kein Buffer). Der Call-Ende-"
        "Merge wartet darauf, BEVOR er ein NULL-audio_health_score als poor_audio_health wertet — "
        "verhindert die Race, in der der Merge VOR dem Audio-Thread liest. Schreibt "
        "routes/app_routes.py (api_beenden / _audio_health_bg); liest services/slow_lane.py (Merge-Gate).'"
    )
    # TABELLEN-Schild aktualisieren (Punkt 23 Aktualitaet): neuer Schreiber (api_beenden/
    # _audio_health_bg setzen resolved) + neuer Leser (slow_lane-Merge-Gate). Single-Source == models.py.
    op.execute(
        "COMMENT ON TABLE public.calls IS "
        "'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-"
        "Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ "
        "der neuen Call-Pipeline; audio_health_resolved geschrieben routes/app_routes.py (api_beenden/"
        "_audio_health_bg), gelesen services/slow_lane.py (Call-Ende-Merge-Gate, TAXO2-04 Audio-Race-Fix).'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.calls DROP COLUMN IF EXISTS audio_health_resolved")
    # TABELLEN-Schild auf den Vor-0027-Stand zuruecksetzen (ohne den resolved-Verweis).
    op.execute(
        "COMMENT ON TABLE public.calls IS "
        "'Zentraler Call-Datensatz der neuen Architektur (UUID-PK, Outcome/Coaching/Transkript-"
        "Storage). Status: lebt (neue Architektur Phase 08.23.2.A+). Schreibt/liest services/+routes/ "
        "der neuen Call-Pipeline.'"
    )
