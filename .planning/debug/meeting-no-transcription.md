---
slug: meeting-no-transcription
status: resolved
trigger: "POLISH-48 LAUNCH-KRITISCH — Meeting-Modus transkribiert kein Audio. Deepgram empfängt nur ersten Audio-Chunk, dann stoppt Transcription."
created: 2026-04-21
updated: 2026-04-21
priority: launch-critical
cluster: "Live-Assistent Pipeline-Fix (POLISH-48, -46, -41, -38/39/40/42) — siehe Backlog"
related: [POLISH-46, POLISH-41, POLISH-38, POLISH-39, POLISH-40, POLISH-42]
---

## Symptoms

**Expected behavior:** Meeting-Modus transkribiert Live-Audio kontinuierlich (wie Cold Call) und liefert Transcript-Events an Claude-Analyse-Pipeline.

**Actual behavior:** Deepgram empfängt (scheinbar) nur den ersten Audio-Chunk. Keine weiteren Transcript-Zeilen. Meeting-Session bleibt stumm, Frontend zeigt keine Live-Updates.

**Error messages:**
- VPS-Log: `audio_chunk received (3200 bytes)` erscheint **einmalig** — dann keine weiteren Audio-Chunk-Logs
- Keine Deepgram-Transcript-Responses danach
- Keine Python-Exceptions / Tracebacks (silent failure)

**Key config difference Cold Call vs Meeting (LiveOptions) [VORHER]:**
- Cold Call: `smart_format=True` → funktioniert
- Meeting: `diarize=True, smart_format=False, utterance_end_ms="1000"` → funktioniert NICHT

**Timeline:** Phase 07.2 UAT-R2 (2026-04-21). Immer dasselbe Verhalten bei jedem Meeting-Modus-Test.

**Reproduction:**
1. Login auf getnerve.app
2. `/live` → Mode "Meeting" wählen
3. Mikrofon-Consent
4. Sprechen (beliebiger Text)
5. VPS-Log: einmaliger `audio_chunk received`, dann Stille in der Transcription

## Current Focus

hypothesis: ROOT CAUSE FOUND — zwei-stufige Erklärung. Siehe Section "Root Cause".

test: DONE — Code-Inspektion deepgram_service.py + SDK-Internals + git log + Phase 04.2-03 Verification-Doku.

expecting: Fix setzt `smart_format=True` auch in Meeting-Mode. `diarize=True` + `utterance_end_ms="1000"` bleiben. Close-Event-Handler eingefügt. audio_chunk-Log auf every-100th umgestellt.

next_action: Fix angewandt — siehe Resolution. Runtime-Verify nötig (User-Deploy + Live-Test in Meeting-Mode).

reasoning_checkpoint: Antwort geklärt — der "nur ein Chunk"-Log war ein Red Herring (by-design one-shot). Echtes Problem: Meeting-Mode-Config war nicht validiert und lieferte keine Transcripts zurück.

## Evidence

- timestamp: 2026-04-21 inv-1
  location: services/deepgram_service.py:324-332
  observation: "`_first_chunk_logged = set()` im Closure. Log 'audio_chunk received' wird **nur beim ersten Chunk pro sid** ausgegeben — danach silent. Das bedeutet: die User-Beobachtung 'nur ein Chunk' bestätigt NICHT, dass Deepgram nur einen Chunk bekommt — sondern nur, dass das Log by design one-shot ist. Audio-Chunks werden weiterhin in Zeile 338-340 via `connection.send(data)` an Deepgram gesendet, solange eine Connection existiert."
  significance: "Kritisch — User-Observation 'nur ein Chunk' ist Red Herring. Die echte Frage ist: warum kommen von Deepgram keine Transcripts zurück? Der fehlende `[DG] [Sprecher] text`-Log auf Zeile 66 ist das wahre Symptom."

- timestamp: 2026-04-21 inv-2
  location: services/deepgram_service.py:180-208, git-commit 010d1fe (2026-04-03)
  observation: "Meeting-Mode LiveOptions: `smart_format=False, diarize=True, utterance_end_ms='1000', punctuate=True, interim_results=True, endpointing=900, encoding=linear16, sample_rate=16000`. Cold-Call-Mode: `smart_format=True, diarize=False`, sonst identisch. Die Begründung im Kommentar ('smart_format strips word-level speaker attributes') ist laut SDK-response.py **nicht korrekt**: `ListenWSWord.speaker` ist ein unabhängiges Feld von `punctuated_word` (siehe deepgram/.../response.py:31-49). `smart_format=True` liefert `speaker` trotzdem, wenn `diarize=True` gesetzt ist."
  significance: "Die ursprüngliche Annahme in Phase 04.2-03 (smart_format=False NÖTIG für diarize) war eine Fehleinschätzung. Gleichzeitig wurde der Meeting-Pfad laut Phase-04.2-03 Verification-Doku **nie runtime-verifiziert** (Zitat: 'Runtime verification still required')."

- timestamp: 2026-04-21 inv-3
  location: services/deepgram_service.py:31-150 (on_message handler)
  observation: "on_message-Handler Zeile 35-36: `text = result.channel.alternatives[0].transcript; if not text: return`. Silent return bei leerem transcript. In Kombination mit `smart_format=False, punctuate=True, interim_results=True, utterance_end_ms='1000'`: Deepgram-Nova-2 liefert häufiger leere Interim-Transcripts (weil smart_format sonst die Formatierung triggert und nicht-leere interim-Strings erzeugt). Diese werden silent verworfen — nur ein finales sichtbares Transcript würde einen Log erzeugen, und das könnte je nach `endpointing` und `utterance_end_ms`-Interaktion nie kommen."
  significance: "Eine plausible sekundäre Ursache: selbst wenn Audio fliesst, sind Interim/Final-Transcripts leer, sodass nichts geloggt wird."

- timestamp: 2026-04-21 inv-4
  location: static/pip-launcher.js:877-965, static/app.js:55-57
  observation: "Client-Side: in _startAudio() wird der AudioWorklet angelegt (L923), der `audio_chunk` emittet. DANACH erst, am Ende von _startAudio() (L965), wird `start_live_session` emittet. Race-Window: Worklet-Frames, die in den Millisekunden zwischen Worklet-Setup (L920-929) und dem `start_live_session`-Emit (L965) anfallen, werden vom Server in `handle_audio_chunk` silent dropped, weil `_deepgram_sessions.get(_sid)` noch `None` zurückgibt. Das betrifft aber nur wenige Frames am Start und gilt GLEICH FÜR COLD CALL — kein mode-spezifisches Problem."
  significance: "Race-Condition existiert, erklärt aber nicht den Mode-Unterschied. Eliminiert als Primärursache für POLISH-48."

- timestamp: 2026-04-21 inv-5
  location: services/deepgram_service.py:181, config.py, .env.example
  observation: "`DeepgramClient(DEEPGRAM_API_KEY)` wird ohne host-Override instanziiert. `.env.example` deklariert `DEEPGRAM_HOST=api.eu.deepgram.com` (DSGVO-EU-Region), aber **nichts im Code liest diese Variable**. Default-Host ist US (api.deepgram.com). Unrelated zu POLISH-48, aber ein separates DSGVO-Problem."
  significance: "Not the root cause of POLISH-48, aber gehört in einen separaten Bug-Report (DSGVO-EU-Region nicht aktiv)."

- timestamp: 2026-04-21 inv-6
  location: deepgram-sdk 3.10.0 client.py (ListenWebSocketClient) + enums.py
  observation: "Default-Verhalten: keepalive DISABLED. Event-Handler-Signaturen (on_message(self, result), on_error(self, error), on_open(self, open), on_utterance_end(self, utterance_end)) matchen SDK-Emitter. **Close-Event ist NICHT abonniert** (Zeile 183-186) — falls Deepgram die Verbindung serverseitig schliesst mit einer `Close`-Message (z.B. wegen invalid params, idle-timeout, quota), wird das silent ignoriert und der User sieht keinen Fehler. LiveTranscriptionEvents.Close existiert (enums.py:16)."
  significance: "Fehlender Close-Event-Handler ist ein bestätigter Kanal für silent failures. Wird im Fix geschlossen."

## Root Cause

**Hauptursache (high confidence):** Die Kombination `smart_format=False, punctuate=True, diarize=True, utterance_end_ms="1000"` für Nova-2 ist eine **nicht-validierte, ungewöhnliche Config**, die im Zusammenspiel mit German-Language und einem einzelnen Audio-Kanal dazu führt, dass Deepgram entweder (a) keine oder leere Interim-Transcripts liefert, oder (b) die WebSocket nach wenigen Sekunden serverseitig schliesst ohne hörbaren Error-Event (weil `Close`-Event-Handler nicht registriert ist).

**Belegte Fehleinschätzung**: Der Kommentar in L191 ("disable smart_format in meeting mode — preserves word-level speaker attributes") ist technisch falsch. Die SDK-Response-Struktur zeigt: `speaker` ist ein eigenes Word-Feld (response.py:43), unabhängig von `punctuated_word` (response.py:40). `smart_format=True` liefert beides.

**Phase 04.2-03 Verification bestätigt**: "Runtime verification still required" — dieser Pfad wurde **nie in Produktion live validiert** und war seit 2026-04-03 de-facto broken.

**Sekundärprobleme (jetzt mitgefixt)**:
- `Close`-Event-Handler fehlt — verhindert sichtbaren Error bei serverseitiger WS-Close.
- `audio_chunk received`-Log war one-shot per sid → Red Herring "nur ein Chunk empfangen". Jetzt: every-100th logging.

**Sekundärprobleme (NICHT in diesem Fix — separate Tickets)**:
- Race-Condition beim Start: Audio-Worklet emittet `audio_chunk` BEVOR `start_live_session` emittet wird. Ein paar Frames werden gedropt. Nicht mode-spezifisch. Niedrige Prio.
- `DEEPGRAM_HOST` in `.env.example` aber nirgends im Code gelesen — DSGVO-Region nicht aktiv. Separater Bug, aber launch-relevant für DACH-Compliance.

## Eliminated

- **Frontend-Mode-Differenz** — pip-launcher.js sendet `audio_chunk` in beiden Modes identisch (inv-4).
- **First-Chunk-Log als Beweis für WS-Close** — Log ist by-design one-shot, kein Beweis für WS-Close (inv-1).
- **Event-Handler-Signatur-Mismatch** — alle on_message/on_error/on_open/on_utterance_end haben korrekte SDK-konforme Signaturen (inv-6).
- **Start-Race als Primärursache** — Race existiert, aber mode-identisch (inv-4).
- **Audio-Encoding-Mismatch** — beide Modes verwenden identisch `encoding="linear16", sample_rate=16000`. Kein mode-spezifischer Encoding-Bug.

## Resolution

**Fix angewandt in services/deepgram_service.py:**

1. **Meeting-Mode auf `smart_format=True`** (primärer Fix):
   - Alt: `smart_format=not is_meeting` → Meeting=False, Cold Call=True
   - Neu: `smart_format=True` unabhängig vom Mode
   - Begründung: SDK-Response-Struktur zeigt `ListenWSWord.speaker` unabhängig von `punctuated_word` — diarize=True liefert speaker auch mit smart_format=True. `utterance_end_ms="1000"` bleibt Meeting-only.

2. **`Close`-Event-Handler registriert** (Observability):
   - Neu: `_make_on_close(sid)` — emittet `dg_close` Socket-Event + print.
   - Registriert via `connection.on(LiveTranscriptionEvents.Close, _make_on_close(sid))`.
   - Sichtbarkeit für alle zukünftigen silent Deepgram-Schliessungen.

3. **`audio_chunk received`-Log umgestellt** (Observability):
   - Alt: `_first_chunk_logged = set()` → Log nur beim ERSTEN Chunk pro sid → Red-Herring-Generator.
   - Neu: `_chunk_counts = {}` → Log bei Chunk #1 UND every 100th chunk. Bei ~100ms/Chunk = Log ca. alle 10s. Zeigt realen Audio-Flow ohne Flooding.

4. **Kommentar korrigiert** — alter Kommentar "preserves word-level speaker attributes" entfernt, neuer Kommentar erklärt die Fehleinschätzung und verweist auf die SDK-Response-Struktur.

**Runtime-Verify (User-TODO nach Deploy):**
1. Deploy auf VPS
2. `/live` → Mode "Meeting" → Consent → Sprechen
3. Erwartet in VPS-Log:
   - `[DG] LiveOptions: model=nova-2, diarize=True, smart_format=True`
   - `[DG] Verbunden (sid=...)`
   - `[DG] audio_chunk #1 (sid=..., bytes=...)`
   - `[DG] audio_chunk #100 (sid=..., bytes=...)` nach ~10s
   - `[DG] [Berater] Hallo ...` bzw. `[DG] [Kunde] ...` Zeilen (echte Transcripts)
   - Frontend zeigt Live-Updates im PiP
4. Falls weiter stumm: neuer `[DG] Close (sid=..., ...)`-Log wird den Server-Close sichtbar machen.

## Cluster Plan

Session 1 (this file): **POLISH-48** Meeting-Transcription — ✅ FIXED (runtime-verify pending)
Session 2 (next): **POLISH-41** Post-Call "Kein Gespräch erkannt" — high UX impact, likely simple
Session 3 (next): **POLISH-38/39/40/42** Backend-Daten-Persistenz Bundle — fix together (related)
Session 4 (last): **POLISH-46** Auto-Einwand-Erkennung unzuverlässig — deepest debug

## Related Files (modified / investigated)

- **services/deepgram_service.py** — MODIFIED (Fix angewandt: smart_format=True, Close-Handler, chunk-log)
- static/pip-launcher.js — inspected (Start-Race identifiziert, nicht Primärursache)
- static/app.js — inspected (legacy path, gleiches Pattern wie pip-launcher)
- config.py — inspected (DEEPGRAM_HOST unused — separater Bug)
- .env.example — inspected (DEEPGRAM_HOST deklariert)
- deepgram-sdk 3.10.0 (SDK-Internals: client.py, response.py, enums.py, options.py, helpers.py, abstract_sync_websocket.py) — zur Verifizierung der Event-Flow-Semantik

## Separate follow-up tickets (nicht Teil POLISH-48)

1. **DSGVO-EU-Region aktivieren** (LAUNCH-RELEVANT für DACH):
   - `DEEPGRAM_HOST=api.eu.deepgram.com` wird nicht gelesen.
   - Fix: `config.py` lädt `DEEPGRAM_HOST`, und `deepgram_service.py` initialisiert `DeepgramClient(DEEPGRAM_API_KEY, DeepgramClientOptions(url=DEEPGRAM_HOST))`.

2. **Start-Race audio_chunk vor start_live_session** (niedrig-prio):
   - In `_startAudio()` erst `start_live_session` emittet, dann `micStarted=true` setzen, dann Worklet-onmessage frei geben.
