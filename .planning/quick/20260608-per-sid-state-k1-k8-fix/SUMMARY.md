---
slug: per-sid-state-k1-k8-fix
status: complete
date: 2026-06-08
commit: 8806516
---

# Summary: K1 Speech-Stats + K8 org_id → per-SID (Single-Source-of-State)

Zwei Bugs desselben Musters (Konstrukt §0.1): per-SID geschrieben, global gelesen →
Reader las die tote, leere Quelle (immer 0 / None). Reader auf per-SID umgestellt,
tote Globale gelöscht.

## Control-Flow-Audit (Punkt 14) — Schlüsselbefunde
- get_speech_stats-Caller: claude_service.py:1475 (sid in scope) + app_routes.py:258
  (/api/beenden — globale HTTP-Route OHNE sid).
- Kein globaler "current sid" (flask_session['sid'] nie geschrieben, ls.state['active_sid']
  nie gesetzt) → /api/beenden muss sid per user_id-Scan auflösen.
- Globale Zähler auch in app_routes.py:150-152/205 gelesen (Postcall-Payload, 2. Surface).
- init_session_state läuft deepgram:630 NACH dem alten Writer → per-SID start_time muss
  NACH init gesetzt werden.

## Änderungen (commit 8806516)
**FIX A (K1):**
- `services/live_session.py`: `get_speech_stats(sid)` liest per-SID aus `_session_state[sid]`
  unter `_session_state_lock`; Null-Stats-Fallback bei fehlender/unbekannter sid. Tote
  Globale (berater_words/kunde_words/session_start_time/laengster_monolog_sek/
  _current_monolog_start) + `speech_lock` gelöscht. `reset_session`: global-Deklaration +
  speech_lock-Reset-Block entfernt (per-SID-Reset via pop+init).
- `services/deepgram_service.py`: globalen Writer (session_start_time/berater/kunde)
  entfernt; per-SID `session_start_time` NACH `init_session_state` gesetzt (Tempo-Zeitbasis).
- `routes/app_routes.py` /api/beenden: sid per user_id-Scan (Pick = zuletzt gestartete
  Session, max session_start_time); Postcall-Payload (bw/kw → dauer_sek) + get_speech_stats
  auf den aufgelösten sid. Fallback Null/kein Crash wenn keine Session.
- `services/claude_service.py:1475`: get_speech_stats(sid).

**FIX B (K8):**
- `services/cost_tracker.py`: `_resolve_user_id_from_live_session` + `_resolve_org_id_from_live_session`
  scannen `_session_state` (erste aktive Session) statt globalem `ls.state` (nie befüllt → None).
  Fallback None. **Inline-Kommentar:** Multi-SID-ambig → vor EA-Launch via sid-Threading an
  log_api_cost(session_id=...) ersetzen (Option 2).

## Verifikation
- py_compile aller 5 Dateien (lokal + auf Prod): OK
- Grep nach Fix: keine `ls.<global>`-Reads mehr (NONE), beide get_speech_stats-Caller mit sid,
  speech_lock vollständig entfernt, globale Zähler auf Prod weg (NONE)
- Datei live auf Prod (get_speech_stats(sid) Z.862), Service neu gestartet 2026-06-08 14:03 UTC,
  is-active = active, /api/health = 200
- Edge-Cases: keine Session gefunden → Null-Stats / org_id None (kein Crash); mehrere Sessions
  desselben Users → definierter Pick (max session_start_time)

## Deploy-Notiz
deploy.sh production: Test-Gate erneut durch pre-existing crm-SQLite-Failures abgebrochen
(exit 2). Fix per pre-autorisiertem manuellem `systemctl restart nerve` live.

## Verifikation NACH André-Test-Call (ausstehend)
- **FIX A:** nach echtem Call mit Sprache beider Seiten:
  `sudo -u postgres psql -d nerve -c "SELECT tempo_avg, laengster_monolog, redeanteil_avg FROM conversation_logs ORDER BY id DESC LIMIT 1;"`
  → tempo_avg / laengster_monolog ≠ 0 (sofern berater gesprochen + Monolog >0).
- **FIX B:** nach Call:
  `sudo -u postgres psql -d nerve -c "SELECT org_id, COUNT(*) FROM api_cost_log WHERE created_at > now() - interval '15 min' GROUP BY org_id;"`
  → org_id gesetzt (nicht NULL) für die Live-Call-Kosten.

## Offen (bewusst, dokumentiert)
- cost_tracker Multi-SID-Ambiguität: vor EA-Launch sid-Threading (Option 2) durch alle
  ~15 log_api_cost-Call-Sites. Inline im Code vermerkt.
- Unrelated pre-existing Startfehler `[DB] Audit-Log Trigger setup failed: syntax error at
  or near "NOT"` (SQLAlchemy f405) besteht weiter — nicht Teil dieses Fixes.
