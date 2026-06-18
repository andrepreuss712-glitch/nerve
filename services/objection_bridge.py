"""
services/objection_bridge.py
────────────────────────────────────────────────────────────────────
TAXO1-Welle 5 (D-04): EIN gekapselter Expand-Contract-Dual-Write-Shim.

# SUNSET: TAXO2 — diese Bruecke fliegt in TAXO2 raus (objection_events-Zombifizierung
# + Umzug der Leser auf intent_event). KEIN Rueck-Sync, KEIN Backfill, keine
# Zusatz-Features (D-04). EINE Datei, EINE Funktion, EINE Aufruf-Stelle.

QUELLE = ewb_clicks (RAM, live_session.state['ewb_clicks']) bei Call-Finalisierung —
die EINZIGE Schicht, die alle objection_events-Leser-Felder traegt:
einwand_typ / success / antwort_text / einwand_text (live_session.py:121).

intent_event (Welle 4, ui_asserted-Button-Emit) bleibt Trigger/Korrelation, ist aber
bewusst NICHT die Daten-Quelle: der ui_asserted-Emit ist schlank (intent_type
hartkodiert 'echter_einwand', kein success/antwort_text/einwand_text — deepgram_service.py:848,
intent_event_writer.py:86-120). Ein Spiegel aus intent_event wuerde success=NULL liefern
und damit den Dashboard-Einwand-Zaehler (app_routes.py:447 SUM(success)) brechen
(Punkt-21-Befund Welle 5, André-Entscheid 2026-06-18: Quelle = ewb_clicks).
"""

from database.models import ObjectionEvent


def mirror_ewb_clicks_to_objection_events(*, conversation_log_id, user_id, org_id,
                                          ewb_clicks, db) -> int:
    """Spiegelt die EWB-Button-Klicks dieser Session (RAM) idempotent nach objection_events.

    Ersetzt den fruehen Direkt-Write app_routes.py:384 (ewb_clicks → ObjectionEvent) durch
    EINEN gekapselten, befristeten Shim. Felder 1:1 wie der ersetzte Write → die Leser
    (dashboard.py:736, app_routes.py:447/471/1389) sehen exakt dieselben Zeilen wie heute.

    IDEMPOTENZ-GUARD (Cross-AI Finding #3, keyed per conversation_log_id):
    bei NICHT-leeren ewb_clicks ZUERST die eigenen Spiegel-Zeilen dieser conversation_log_id
    loeschen, DANN frisch re-spiegeln (DELETE-then-INSERT, last-write-wins). Ein doppeltes
    /api/beenden fuer dieselbe Session (Doppel-Klick/Reload am Call-Ende) konvergiert so auf
    denselben Zeilen-Satz — KEINE Duplikate, der Dashboard-Einwand-Zaehler zaehlt nicht doppelt
    (Punkt-21-Datenkorrektheit). Sicher, weil die Bruecke der EINZIGE objection_events-Schreiber
    fuer Live-Calls ist (ersetzt :384); historische Zeilen haben andere conversation_log_id.

    Leere ewb_clicks → No-Op (return 0, KEIN DELETE): ein zweiter Aufruf nach Session-Reset
    (ewb_clicks bereits geleert, live_session.py:932) darf die im ersten Aufruf geschriebenen
    Zeilen NICHT loeschen.

    KEIN Rueck-Sync zu intent_event, KEIN Backfill (D-04). Committet NICHT selbst — laeuft in
    der Caller-Finalisierungs-Transaktion (db_conv); der Caller committet (wie der ersetzte
    Write app_routes.py:393-394 `if ewb_clicks: db_conv.commit()`).

    Return: Anzahl gespiegelter Zeilen.
    """
    clicks = list(ewb_clicks or [])
    if not clicks:
        # Nichts zu spiegeln → bestehende Zeilen unberuehrt lassen (kein DELETE).
        return 0

    # ── IDEMPOTENZ-GUARD (Finding #3): eigene Spiegel-Zeilen dieser conv loeschen ──
    # Cross-AI Welle-5 (Gemini, 2026-06-18): DELETE auf Call-Log-Daten (objection_events = "heilig",
    # mandantenfaehig) MUSS org-scoped sein — Defense-in-Depth gegen mandantenuebergreifende Loeschung,
    # selbst wenn je eine falsche conversation_log_id durchkaeme (conversation_log_id ist zwar eindeutig).
    db.query(ObjectionEvent).filter(
        ObjectionEvent.conversation_log_id == conversation_log_id,
        ObjectionEvent.org_id == org_id,
    ).delete(synchronize_session=False)

    # ── Frisch spiegeln (insert-only, gleiche Felder wie der ersetzte Direkt-Write) ──
    for click in clicks:
        db.add(ObjectionEvent(
            user_id=user_id,
            org_id=org_id,
            conversation_log_id=conversation_log_id,
            einwand_typ=click['einwand_typ'],
            success=click['success'],
            antwort_text=click.get('antwort_text'),
            einwand_text=click.get('einwand_text'),
        ))

    return len(clicks)
