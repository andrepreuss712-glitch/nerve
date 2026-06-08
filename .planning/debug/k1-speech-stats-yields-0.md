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

## Diagnose-Ergebnis (echte Marker, Test-Call 15:10-15:11)
- **H1 WIDERLEGT:** `/api/beenden uid=2 resolved_sid='GMr6...' -> bw=150 kw=0 start_set=True
  dauer=64` — sid-Scan funktioniert, früher Read sieht bw=150.
- **H2 WIDERLEGT:** flush-Marker zeigen `sp_name='Berater' roles_confirmed=True`, berater_words
  zählt 15→150 hoch, monolog→43.1, start_set=True. Counter akkumulieren sauber. Sprecher-
  Routing greift (anders als qa_slot1) — die zwei Bugs hängen NICHT zusammen.
- **ECHTE WURZEL (Case 3):** `get_speech_stats(sid='GMr6...') -> {0,0,0}` TROTZ bw=150.
  Mathematisch unmöglich außer im `if not _ss`-Pfad → Session zum Zeitpunkt des SPÄTEN
  get_speech_stats-Aufrufs (app_routes.py:288) schon aus _session_state entfernt. Der
  WebSocket-`disconnect`-Handler (deepgram_service.py:755 `pop_session_state`) räumt
  _session_state[sid] im Fenster zwischen frühem Read (Z.170, bw=150) und spätem
  get_speech_stats (Z.288) ab. reset_session (Z.726) ist erst danach.

## Fix (umgesetzt, commit folgt)
app_routes.py /api/beenden: Speech-Stats FRÜH (Z.165-180, vor disconnect-Teardown) aus dem
early _session_state-Read berechnen (+ laengster_monolog_sek mitlesen), `_stats` bis zur
Persistenz durchreichen. Später get_speech_stats(Z.288)-Aufruf entfernt. get_speech_stats
bleibt für coaching_loop (live, Session existiert). [K1-DIAG]-Marker entfernt.

## PLUS — gleiche Bug-Klasse (späte _session_state-Reads, REPORT-ONLY, NICHT gefixt)
- **word_confidences (app_routes.py:594-606):** später _session_state-Read NACH dem early-
  Punkt. `call_id` HAT einen DB-Fallback (Z.613-624, latest Call ended_at IS NULL) → robust.
  ABER `_phase_d_word_confidences` hat KEINEN Fallback → bei disconnect-Pop-Race leer (Daten
  nur im RAM, nicht in DB). Gleiche Wurzel wie Speech-Stats. → Folge-Pass-Kandidat (früh lesen
  oder word_confidences anders persistieren). Außerhalb dieses Scopes (nur Speech-Stats).
- Andere späte Reads in /api/beenden lesen `ls.state` (globales Dict, NICHT _session_state) —
  z.B. ewb_clicks (Z.202), session_anrede (Z.215). Global wird vom disconnect NICHT gepoppt →
  nicht dieselbe Race-Klasse.

status: fixed (verify pending nach Test-Call)
