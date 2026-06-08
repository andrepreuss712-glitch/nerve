---
slug: per-sid-state-k1-k8-fix
created: 2026-06-08
type: quick
---

# Quick Fix: Single-Source-of-State — K1 Speech-Stats + K8 org_id

Muster (Konstrukt §0.1): per-SID geschrieben, aber global gelesen → Reader liest die
tote, leere Quelle. Reader auf die lebende per-SID-Quelle, tote Globale gelöscht.

## Control-Flow-Audit (Punkt 14) — Vorbefund
- `get_speech_stats()` Caller: claude_service.py:1475 (coaching_loop — **sid in scope** ✓),
  app_routes.py:258 (/api/beenden — **globale HTTP-Route, KEIN sid**).
- Kein globaler "current sid": flask_session['sid'] nie geschrieben, ls.state['active_sid']
  (global) nie gesetzt → /api/beenden muss sid per **user_id-Scan** auflösen.
- Globale Zähler (185-189) zusätzlich gelesen in app_routes.py:150-152/205 (Postcall-Payload,
  **gleicher K1-Bug, 2. Surface**); geschrieben deepgram:562-564 + reset_session:819-823.
  `session_start_time` global WIRD gesetzt (dauer_sek ok), die Word-/Monolog-Zähler nicht.
- init_session_state läuft deepgram:630 (NACH dem alten Writer 562) → per-SID start_time
  muss NACH init gesetzt werden (sonst von init auf None geklobbert).
- cost_tracker resolvers lesen global ls.state; ~15 log_api_cost-Call-Sites passen weder
  session_id noch org_id → Resolver-Fallback greift immer.

## Entscheidungen (André)
- FIX A: voll per-SID + Globale + speech_lock + deepgram-Writer + reset-Block LÖSCHEN.
- FIX B: Resolver scannt _session_state (erste/aktive Session), Multi-SID-ambig →
  Inline-Kommentar + vor EA-Launch via sid-Threading (Option 2) ersetzen.

## Änderungen
FIX A:
- live_session.py: get_speech_stats(sid) liest per-SID (_session_state[sid]) unter
  _session_state_lock, Null-Stats-Fallback bei fehlender/unbekannter sid. Globale 185-189
  + speech_lock gelöscht. reset_session: global-decl + speech_lock-Reset-Block entfernt
  (per-SID-Reset via pop+init).
- deepgram_service.py: globalen session_start_time/berater/kunde-Writer entfernt; per-SID
  session_start_time NACH init_session_state gesetzt (Tempo-Zeitbasis).
- app_routes.py /api/beenden: sid per user_id-Scan (Pick: max session_start_time),
  Postcall-Payload (bw/kw/_st→dauer_sek) + get_speech_stats(sid) auf per-SID.
- claude_service.py:1475: get_speech_stats(sid).

FIX B:
- cost_tracker.py: _resolve_user_id/_resolve_org_id scannen _session_state statt global
  ls.state. Fallback None. Multi-SID-Ambiguitäts-Kommentar + EA-Launch-TODO.

## Scope
NUR K1 + K8. Kein Score-/Gewichtungs-Redesign.

## Verify (HART: kein Local-Dev)
- py_compile aller 5 Dateien: OK (parse-only). Grep: keine ls.<global>-Reads mehr, beide
  get_speech_stats-Caller passen sid, speech_lock weg.
- deploy.sh production (Gate kaputt → manueller restart) → Test-Call →
  conversation_logs.tempo_avg / laengster_monolog ≠ 0 (FIX A); org_id in api_cost_log gesetzt (FIX B).
