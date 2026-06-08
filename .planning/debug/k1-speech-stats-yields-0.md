---
slug: k1-speech-stats-yields-0
status: instrumented
created: 2026-06-08
updated: 2026-06-08
---

# Debug: K1 deployed aber conversation_logs Speech-Stats weiter 0

## Symptom
K1-Fix (get_speech_stats per-SID, commit 8806516) IST live auf Prod (Files verifiziert:
get_speech_stats(sid):862, globals weg, mtime 14:00). Trotzdem: conversation_logs row 223
(ended 14:45, NACH Deploy+Restart 14:03) zeigt redeanteil_avg=0, tempo_avg=0,
laengster_monolog=0. Code deployed, aber zur Laufzeit unwirksam.

## Methode
Logging-First (Punkt 15), DIAGNOSE-ONLY, KEIN Fix im ersten Pass. 3 Mess-Punkte,
deployen, André macht echten Test-Call, dann Diagnose aus echten Markern.

## Hypothesen
- **H1 — sid-Resolution in /api/beenden schlägt fehl:** user_id→sid-Scan liefert None
  (Session schon gepoppt / user_id-Mismatch) → get_speech_stats(None) → {0,0,0}.
- **H2 — per-SID Counter akkumulieren nie:** berater_words/kunde_words bleiben 0 während
  des Calls. Mögliche Wurzel = Sprecher-Zuordnung (gleiche wie qa_slot1→smalltalk_none):
  sp_name ist nicht 'Berater'/'Kunde' (roles_confirmed-Gating / Single-Speaker-Cold-Call)
  → weder if- noch elif-Zweig in _flush_segment feuert.

## Mess-Punkte (commit folgt, Tag [K1-DIAG])
- **MP1** `_flush_segment` (live_session.py): pro flush sp_name, speaker, roles_confirmed,
  word_count + resultierende berater_words/kunde_words/monolog + start_set. Plus Log wenn
  sid NICHT in _session_state (Session weg bei flush). → testet H2 + Sprecher-Routing.
- **MP2** `/api/beenden` (app_routes.py): aufgelöste _beenden_sid, gelesene bw/kw/start,
  + Snapshot ALLER aktiven Sessions (sid,user_id,start,bw,kw). → testet H1 (Scan-Miss vs
  leere Counter vs Session weg).
- **MP3** `/api/beenden`: Rückgabe von get_speech_stats(_beenden_sid). → was wird persistiert.

## Diskriminierung
- MP1 zeigt berater_words>0 akkumulierend, MP2 resolved_sid=None ODER bw=0 trotz Session
  im Snapshot mit bw>0 → **H1** (Scan-Bug / falsche/keine sid / Session weg bei beenden).
- MP1 zeigt sp_name ≠ 'Berater'/'Kunde' und Counter nie >0 → **H2 + Sprecher-Routing-Wurzel**
  (dieselbe wie qa_slot1).
- MP1 akkumuliert + MP2 resolved korrekt mit bw>0 ABER MP3 stats=0 → Bug in get_speech_stats.

## Current Focus
hypothesis: deployed-but-ineffective — entweder sid-Resolution (H1) oder Counter-Akkumulation/
  Sprecher-Routing (H2). Mess-Punkte unterscheiden.
next_action: [K1-DIAG] deployen + manueller Restart → André echter Test-Call →
  journalctl grep "[K1-DIAG]" → Diagnose, dann erst Fix.
