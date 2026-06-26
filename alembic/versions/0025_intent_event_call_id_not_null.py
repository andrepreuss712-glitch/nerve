"""Phase 08.23.2.CALLID Plan 04 (Deploy 2) — intent_event.call_id NOT NULL + 54 NULL-Zeilen loeschen.

CI-3: haertet die call_id-Integritaet als DB-Waechter, NACHDEM Deploy 1 (Plan 01-03, live 2026-06-25)
+ Soak (3 echte Test-Anrufe, 2026-06-26: alle Pfade — Knopf/Medium-Lane/Stichwort-Erkenner — erzeugen
Events MIT call_id, 0 neue NULL, 0 [CALLID-ALARM]) bewiesen haben, dass keine neuen NULLs mehr entstehen.

Reihenfolge (GELOCKT): (1) Pre-Check (BLOCKIEREND) -> (2) DELETE der NULL-Zeilen -> (3) SET NOT NULL.
Der defensive Backstop (Plan 03) bleibt das PRIMAERE Netz; NOT NULL ist Belt-and-Suspenders.

ZUSATZ (gefaltet, Schild-Aktualitaets-Pflicht CLAUDE.md Punkt 23): das intent_event-TABELLEN-Schild
korrigiert — Slow Lane reichert IN-PLACE an (handling_score_numeric/handling_status) statt via dem
verworfenen 'separaten Score-Objekt'; Schreiber-Liste ergaenzt um services/deepgram_service.py
(EWB-Knopf-Emit) + services/slow_lane.py (In-Place-Benotung). Plus call_id-Spalten-Schild auf
NOT-NULL-Stand. NUR COMMENTs, kein Verhaltens-Change. Single-Source: COMMENT-Texte == models.py comment=.

create_all-Falle: Migration als postgres VOR Restart. Prod-HEAD beim Execute = 0024 (Claudian
verifiziert 2026-06-26) -> down_revision='0024'; SCHRITT 0 (head==0024) unmittelbar vor dem Lauf re-checken.

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # (1) PRE-CHECK (BLOCKIEREND, CI-3): alle verbleibenden call_id-NULL-Zeilen MUESSEN
    #     handling_status='failed' sein (= die alten ~54 Pre-Launch-Testzeilen). Eine FRISCHE NULL
    #     (pending/scored/abstained) NACH Deploy 1 = Race NICHT geschlossen -> STOP, NICHTS aendern
    #     (kein DELETE, kein SET NOT NULL), zurueck zu Plan 02 + Soak.
    bad = conn.execute(sa.text(
        "SELECT count(*) FROM intent_event "
        "WHERE call_id IS NULL AND handling_status <> 'failed'"
    )).scalar()
    if bad and bad > 0:
        raise RuntimeError(
            f"CALLID Deploy 2 ABGEBROCHEN: {bad} call_id-NULL-Zeile(n) sind NICHT 'failed' "
            "(frische NULLs => Race nicht geschlossen). KEIN DELETE, KEIN SET NOT NULL. "
            "Zurueck zu Plan 02 + Soak."
        )

    # (2) DELETE der 'failed'+NULL-Zeilen (Pre-Launch-Testdaten, nicht rekonstruierbar, Andre-Freigabe).
    #     Idempotent, scoped: WHERE call_id IS NULL (Pre-Check garantiert: alle verbleibenden sind 'failed').
    conn.execute(sa.text("DELETE FROM intent_event WHERE call_id IS NULL"))

    # (3) SET NOT NULL (DB-Waechter). Backstop Plan 03 bleibt primaer; dies ist Belt-and-Suspenders.
    op.alter_column('intent_event', 'call_id', nullable=False,
                    existing_type=postgresql.UUID(as_uuid=True))

    # (4) Schilder aktualisieren (Punkt 23, Single-Source == models.py comment=).
    #     call_id-Spalten-Schild: NOT-NULL-Stand (das alte 'Events ohne call_id moeglich' stimmt nicht mehr).
    op.execute(
        "COMMENT ON COLUMN public.intent_event.call_id IS "
        "'Bezug zum Call-Record. HARTER FK ON DELETE CASCADE (INTERLOCK I-2 / DD-01-Konvention wie "
        "CallEvent models.py:738) — geloeschter Call raeumt Einwand + abstain_log (TAXO2-Wortlaut) "
        "DSGVO-sauber mit. A2-''lose FK'' revidiert (F-08). NOT NULL ab CALLID Deploy 2 (CI-3): jeder "
        "Event traegt seinen Call (call_id-Naht Plan 01 + Race-Close Plan 02); alte NULL-Testzeilen geloescht.'"
    )
    #     TABELLEN-Schild: 'in-place'-Korrektur (verworfenes 'separates Score-Objekt' war irrefuehrend)
    #     + vollstaendige Schreiber-Liste (deepgram-Knopf-Emit + slow_lane-In-Place fehlten).
    op.execute(
        "COMMENT ON TABLE public.intent_event IS "
        "'Zentrale Ereignis-Tabelle (Single Source of Truth) fuer erkannte Kunden-Intents pro Call. "
        "Fast+Medium Lane emittieren; Slow Lane reichert IN-PLACE an (handling_score_numeric/"
        "handling_status, TAXO2). Hybrid: indizierte Kern-Spalten + payload_jsonb. Status: lebt (TAXO1). "
        "Schreibt services/einwand_keyword_matcher.py (Keyword-Fast-Lane), services/claude_service.py "
        "(Medium+QA-Lane), services/deepgram_service.py (EWB-Knopf-Emit), services/slow_lane.py "
        "(In-Place-Benotung); liest TAXO2/TAXO3-Auswertung.'"
    )


def downgrade() -> None:
    # call_id zurueck auf nullable. Die Schild-Texte bleiben auf dem neuen (korrekten) Stand —
    # die alten Texte waren ohnehin veraltet/falsch, ein Zurueckschreiben waere sinnlos.
    op.alter_column('intent_event', 'call_id', nullable=True,
                    existing_type=postgresql.UUID(as_uuid=True))
    # Das DELETE ist NICHT reversibel (Pre-Launch-Testdaten unwiederbringlich weg) — bewusst, AUDIT-NOTE.
