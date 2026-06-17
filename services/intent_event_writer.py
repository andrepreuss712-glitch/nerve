"""
services/intent_event_writer.py
────────────────────────────────────────────────────────────────────
TAXO1-Welle 4 (Cutover): DIE EINE gekapselte Schreibstelle fuer intent_event.

# SINGLE SOURCE: alle Erkennungs-Bahnen emittieren ueber DIESE Funktion (Cutover TAXO1).

Fast Lane (Keyword-Matcher + EWB-Button) UND Medium Lane (analyse_loop Haiku
Intent+Phase) schreiben ihre erkannten Kunden-Intents ausschliesslich hier hin.

Bau-Regel 1 (Geruest §5): INSERT-ONLY, keine Mutation bestehender Zeilen
(Live-Bahnen sind read-only auf erzeugte Events; Anreicherung = Slow Lane / TAXO2).
KEIN Scoring (handling_score_numeric bleibt NULL — TAXO2).

Geruest §3 Pflichtfelder je Event: taxonomy_version (non-null im payload_jsonb),
mode, speaker_role, speaker_id, source. intent_type wird gegen die geteilte
Taxonomie (services/intent_taxonomy.py) validiert.

interaction_id (Moment-Fenster, I-4-FOLD): wird vom AUFRUFER via
live_session.get_or_open_moment bestimmt und durchgereicht — der Writer mintet
selbst KEINE uuid (sonst teilt sich die id nicht ueber Fast/Medium/Button des
DESSELBEN offenen Fensters).
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.intent_taxonomy import is_valid_intent_type, TAXONOMY_VERSION


def emit_intent_event(
    *,
    session_id,
    mode,
    intent_type,
    source,
    speaker_role,
    speaker_id,
    phase=None,
    confidence=None,
    user_id=None,
    org_id=None,
    call_id=None,
    interaction_id=None,
    inference_basis=None,
    abstained=False,
    is_simulation=False,
    origin_type='human_live',
    extra_payload=None,
) -> int:
    """Schreibt EINE intent_event-Zeile (insert-only) und gibt event_id zurueck.

    Pflichtfelder (Geruest §3): session_id, mode, source, speaker_role nicht leer;
    taxonomy_version Pflicht non-null im payload. intent_type muss in der
    geteilten Taxonomie (Kern ∪ custom_objection_*) liegen.

    interaction_id (optional/nullable, UUID-str): das offene Moment-Fenster, vom
    Aufrufer via get_or_open_moment bestimmt — der Writer setzt nur die Spalte
    und mintet KEINE eigene id.

    Fehlertoleranz: bei DB-Fehler wird geloggt + geschluckt (Live-Loop darf nicht
    crashen, Edge 3); Rueckgabe -1 signalisiert "nicht persistiert".
    """
    # ── Pflichtfeld-Validierung (Geruest §3 "bei jedem Event") ──────────────
    if not session_id:
        raise ValueError("emit_intent_event: session_id ist Pflicht")
    if not mode:
        raise ValueError("emit_intent_event: mode ist Pflicht")
    if not source:
        raise ValueError("emit_intent_event: source ist Pflicht")
    if not speaker_role:
        raise ValueError("emit_intent_event: speaker_role ist Pflicht")

    # ── Taxonomie-Validierung (T-TAXO1-10): LLM-Output ist untrusted ────────
    # Entscheidung (Task 1 Test 3): ungueltiger intent_type → ValueError (hartes
    # Signal an den Aufrufer; KEIN stiller abstained-Fallback, der Muell unter
    # einem Pseudo-Intent in die Single-Source schreiben wuerde).
    if not is_valid_intent_type(intent_type):
        raise ValueError(
            f"emit_intent_event: intent_type {intent_type!r} nicht in der "
            f"Taxonomie (Kern ∪ custom_objection_*)"
        )

    # ── payload_jsonb (Hybrid §3): taxonomy_version Pflicht non-null ────────
    payload = {
        'source': source,
        'inference_basis': inference_basis,
        'taxonomy_version': TAXONOMY_VERSION,
        'abstained': bool(abstained),
        'speaker_role': speaker_role,
        'speaker_id': speaker_id,
        'is_simulation': bool(is_simulation),
        'origin_type': origin_type,
    }
    if extra_payload:
        for _k, _v in extra_payload.items():
            payload[_k] = _v

    # ── INSERT (insert-only, Bau-Regel 1; eigene get_session pro Call =
    #    thread-safe im Daemon-/Matcher-/Socket-Kontext). Keine Row-Mutation,
    #    KEIN Scoring (handling_score_numeric NICHT gesetzt → NULL). ────────────
    from database.db import get_session
    from database.models import IntentEvent

    db = get_session()
    try:
        ev = IntentEvent(
            session_id=str(session_id),
            mode=mode,
            timestamp=datetime.now(timezone.utc),
            intent_type=intent_type,
            phase=(int(phase) if phase is not None else None),
            confidence=(float(confidence) if confidence is not None else None),
            call_id=call_id,
            interaction_id=interaction_id,
            payload_jsonb=payload,
            # handling_score_numeric: NICHT setzen (NULL, REQ 2 — TAXO2).
            # handling_status: server_default 'pending' (TAXO2 setzt Werte).
        )
        db.add(ev)
        db.commit()
        eid = ev.event_id
    except Exception as _e:
        # Edge 3: DB weg → loggen + schlucken, Live-Loop laeuft weiter.
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[intent_event] emit failed (insert-only): {type(_e).__name__}: {_e}")
        return -1
    finally:
        db.close()

    # ── Optional: read-only Referenz an die Slow Lane (Welle 2). KEIN Score,
    #    KEINE Mutation — nur ein Arbeits-Signal auf eine schon-durable Zeile. ──
    try:
        from services.slow_lane import slow_lane
        slow_lane.put({'event_id': eid})
    except Exception as _sl_e:
        print(f"[intent_event] slow_lane.put skip: {type(_sl_e).__name__}")

    return eid
