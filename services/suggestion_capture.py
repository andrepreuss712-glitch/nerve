"""
services/suggestion_capture.py
────────────────────────────────────────────────────────────────────
TAXO2-Plan 08 (FOLD A / A-2): Call-Ende-Flush der erfassten NERVE-Vorschlaege
aus dem RAM-Puffer (live_session.state['suggestion_offers']) nach public.suggestion_reactions.

EIGENSCHAFTEN (HART):
  - INSERT-ONLY: NUR das ANGEBOT wird geschrieben. Die Reaktions-Haelfte
    (adoption_value/following_utterance_ref/reaction_class) ist DEFERRED (post-Launch,
    neu-berechenbar) und bleibt JETZT NULL — KEIN Uebernahme-Scoring in TAXO2.
  - KEIN Live-Pfad-DB-Write (Punkt 25): der EINZIGE DB-Write ist DIESER Call-Ende-Flush,
    der in der bestehenden Finalisierungs-Transaktion (db_conv) laeuft. Caller committet.
  - ANON-VERTRAG (FOLD A-2 / Plan 09): `suggestion_text` kommt BEREITS anonymisiert
    (am Erfassen mit dem lebenden Per-SID-Cache, Plan 09) im RAM-Puffer an. Der Flush
    schreibt ihn 1:1 — KEINE Anon im Flush, KEIN cache=None (das waere ein No-Op,
    anonymization.py:612, und wuerde rohe Namen speichern -> DSGVO-Loch). Der DSGVO-Beweis
    der Anonymisierung liegt in Plan 09 (anon-live-vs-stored). Referenz:
    Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.
  - IDEMPOTENZ (FOLD A-2/B3): bei NICHT-leerem Puffer ZUERST die eigenen Zeilen DIESES
    Calls loeschen (DELETE strikt `org_id == ... AND call_id == ...`, NIE nur
    conversation_log_id, NIE Zeilen anderer Calls anfassen), DANN frisch insert-only
    re-schreiben. Doppel-/api/beenden konvergiert auf denselben Zeilen-Satz.
  - Leerer Puffer -> No-Op (return 0, KEIN DELETE): ein zweiter Aufruf nach Session-Reset
    (suggestion_offers bereits geleert) darf die im ersten Aufruf geschriebenen Zeilen
    NICHT loeschen.

KNOWN-ISSUE (FOLD A-2/B2, bewusst, NICHT still): Prozess-Crash vor Call-Ende verliert
den RAM-Puffer -> die Vorschlaege DIESES Calls werden nicht erfasst. insert-only /
nicht-nachholbar IST die bewusste Eigenschaft (Tuermoeffner-Regel); kein Backfill-Anspruch.
"""

from datetime import datetime

from database.models import SuggestionReaction


def _parse_ts(ts):
    """RAM-Puffer-ts ist ein ISO-8601-String (utcnow().isoformat()). ts_offered ist eine
    DateTime-Spalte -> in ein datetime parsen (None/unparsbar -> None, nie Crash)."""
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def flush_suggestion_offers(*, conversation_log_id, call_id, user_id, org_id,
                            tenant_id, suggestion_offers, db) -> int:
    """Flusht die im RAM erfassten Vorschlaege dieses Calls idempotent + insert-only
    nach suggestion_reactions. Committet NICHT selbst (Caller-Transaktion db_conv).

    suggestion_offers: Liste von dicts aus live_session.record_suggestion_offer
      {slot, source, model, suggestion_text (BEREITS anonymisiert/Plan 09),
       interaction_id (immer gesetzt/B1), einwand_typ, ts}.

    Return: Anzahl geschriebener Zeilen (0 bei leerem Puffer = No-Op).
    """
    offers = list(suggestion_offers or [])
    if not offers:
        # Nichts zu flushen -> bestehende Zeilen unberuehrt lassen (KEIN DELETE).
        return 0

    # ── IDEMPOTENZ-GUARD (FOLD A-2/B3): eigene Zeilen DIESES Calls loeschen ──────
    # STRIKT org_id AND call_id gescoped (NICHT nur conversation_log_id) — nie Zeilen
    # anderer Calls anfassen (Gemini-Fund). Doppel-/api/beenden konvergiert.
    db.query(SuggestionReaction).filter(
        SuggestionReaction.org_id == org_id,
        SuggestionReaction.call_id == call_id,
    ).delete(synchronize_session=False)

    # ── Frisch insert-only re-schreiben (suggestion_text 1:1, KEINE Anon im Flush) ──
    for offer in offers:
        db.add(SuggestionReaction(
            call_id=call_id,
            conversation_log_id=conversation_log_id,
            interaction_id=offer.get('interaction_id'),   # immer gesetzt (B1)
            org_id=org_id,
            user_id=user_id,
            tenant_id=tenant_id,
            slot=offer.get('slot'),
            source=offer.get('source'),
            model=offer.get('model'),
            suggestion_text=offer.get('suggestion_text'),  # BEREITS anonymisiert (Plan 09) — KEINE Anon hier
            einwand_typ=offer.get('einwand_typ'),
            ts_offered=_parse_ts(offer.get('ts')),
            payload_jsonb={},
            # DEFERRED (post-Launch, NICHT befuellt in TAXO2):
            adoption_value=None,
            following_utterance_ref=None,
            reaction_class=None,
        ))

    return len(offers)
