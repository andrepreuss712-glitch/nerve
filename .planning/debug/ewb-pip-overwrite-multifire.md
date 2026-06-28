---
status: investigating
trigger: "Bug B — Cold-Call: NERVEs EWB-Vorschlag im PiP wird WAEHREND des Vorlesens ueberschrieben/geloescht + Einwand-Knoepfe feuern mehrfach"
created: 2026-06-28
updated: 2026-06-28
mode: logging-first (KEIN Fix im ersten Pass — CLAUDE.md Punkt 15; HART Kein-Local-Dev: Andre reproduziert live auf Prod)
---

# Debug: EWB-PiP ueberschrieben + Knoepfe feuern mehrfach

## Symptoms

- **Expected:** Berater klickt EINEN Einwand-Knopf → NERVE streamt EINE Antwort in PiP-Slot-1 → der Text bleibt stabil stehen, waehrend der Berater ihn vorliest.
- **Actual:** (1) Der Vorschlag verschwindet/aendert sich WAEHREND des Vorlesens. (2) Die Knoepfe feuern doppelt/mehrfach pro Klick.
- **Errors:** `[coldcall_infer] error: Extra data line 6` (kaputtes JSON aus Live-Erkennung); `[analyse_loop] SID … gone during Claude call — silent drop`.
- **Timeline:** Live-Test 2026-06-28 (Cold-Call).
- **Repro:** Cold-Call als Test-User, Einwand-Knopf im PiP klicken, Antwort vorlesen.

## Evidence (prod-verifiziert von Claudian, als postgres)

- timestamp: 2026-06-28 16:57 | Call 1971e681 | transcript_segments: 16× IDENTISCH `gatekeeper_insider_antwort *ewb button*` (EIN Knopf, 16 Events) + 6× IDENTISCH `Keine Zeit *ewb button*` → massives Mehrfach-Feuern. ALLE Knopf-Events haben `ts_ms=0`. Ein gesprochenes Segment bei `ts_ms=61019000` (≈17h, unmoeglich) → Judge sortiert nach ts_ms ASC → Daten-Qualitaet bricht auch Transkript-Reihenfolge.
- timestamp: 2026-06-28 ~15:36–15:39 | sid EzUqxD59WIBgxD2oAAAB | Logs: `[coldcall_infer] error: Extra data line 6`; `[analyse_loop] SID … gone during Claude call — silent drop`; manual_ewb feuerte DOPPELT.

## Hypotheses (zu bestaetigen/widerlegen per Logging — NICHT blind fixen)

- (A) Frontend feuert `manual_ewb` mehrfach pro Klick (Beleg: 16×/6×) → mehrere parallele Streams in denselben PiP-Slot. Verdacht: Doppel-Binding/Bubbling der EWB-Klick-Delegation (`.closest`), pip-launcher.js:1802–1810 / Emit :2281.
- (B) Race um die PiP-Slot-1-Anzeige zwischen manuellem EWB-Stream (`manual_ewb`) und Auto-Erkennung (`analyse_loop`/`coldcall_infer`): der Lock `slot1_variant_busy_until` (live_session.py:143, "shared lock between keyword-pipe and analyse_loop") deckt den `manual_ewb`-Pfad evtl. NICHT ab → Auto-Erkennung ueberschreibt den manuellen Vorschlag mitten im Vorlesen.
- (C) `ts_ms=0` auf Knopf-Events: separater Daten-Bug ODER Teil desselben Event-Chaos. Wo wird ts_ms fuer Knopf-Events (intent_event-Schreibpfad) gesetzt?

## Code-Anker (verifiziert)

- Frontend: static/pip-launcher.js:2281 (`socket.emit('manual_ewb',...)`), :1802–1810 (Klick-Delegation .closest), :2058+ (EWB-Render), :2321–2352 (raw_text-Stream-Variante, Slot-1-Schreiber FE).
- Backend: services/claude_service.py:935 (`analyse_loop`), :472–505 (`coldcall_infer` + "Extra data line" JSON-Parse @505), :572 (`streame_auto_variante`), :1329/1337/1345 (Socket-Emits source='analyse_loop'); services/live_session.py:143 (`slot1_variant_busy_until`). intent_event-Schreibpfad: ts_ms-Setzpunkt fuer Knopf-Events.

## Measurement Plan (5–6 Mess-Punkte — Pass 1, KEIN Fix)

1. FE: jedes `manual_ewb`-Emit loggen (Klick-ID/UUID pro Klick, button-key, timestamp) → bestaetigt/widerlegt Mehrfach-Feuern + zeigt OB ein Klick = mehrere Emits ODER mehrere Klicks/Re-Binds.
2. BE: `manual_ewb`-Empfang loggen (SID, button-key, empfangs-ts) → FE-Emits vs BE-Empfaenge abgleichen (Bubbling vs Reconnect-Replay vs Doppel-Handler).
3. BE: jedes Setzen/Lesen von `slot1_variant_busy_until` loggen (Wer/Quelle, SID, wann, Wert) — inkl. ob der manual_ewb-Pfad den Lock setzt/prueft.
4. BE: jeder Slot-1-Schreibvorgang loggen mit QUELLE (`manual_ewb` vs `analyse_loop` vs `coldcall_infer`) + war der Lock aktiv? → beweist/widerlegt das Ueberschreiben (B).
5. BE: `coldcall_infer` JSON-Parse VOR dem Fehler loggen (Roh-Input an "line 6") → was bricht das JSON.
6. BE: ts_ms-Setzpunkt fuer Knopf-Events loggen (welcher Wert wird geschrieben, warum 0).

Einbau-Regeln: Punkt 14 (30 Zeilen Kontext, Control-Flow, grep Symbol vor Edit), Punkt 17 (minimal, kein Refactor). Logs deutlich taggen (z.B. `[BUGB-EWB]`) fuer leichtes `inspect.sh logs`-Grep.

## Current Focus

hypothesis: A (FE-Mehrfach-Emit) + B (Slot-1-Race manual vs auto, Lock deckt manual_ewb NICHT) — statische Lesung stuetzt B sehr stark; C (ts_ms=0) statisch als ts-Format-Mismatch identifiziert. PASS 1 instrumentiert nur, KEIN Fix.
test: Instrumentierung (6 Mess-Punkte, Tag [BUGB-EWB]) deployt, Andre reproduziert Cold-Call live, Logs via inspect.sh ziehen.
expecting: Logs zeigen ob 1 Klick = N Emits mit GLEICHER click_id (A: FE-Bubbling) ODER N click_ids (echte Trigger); ob qa_slot1/streame_auto_variante in Slot-1 schreibt waehrend manual-Stream laeuft (B); welches Roh-JSON "Extra data line 6" bricht (MP5); dass Knopf-Entries ts=float-epoch tragen -> ts_ms=0 (C).
next_action: human-action-Checkpoint — Andre deployt (deploy.sh production) + Cold-Call + EINEN Einwand-Knopf klicken + Antwort vorlesen + beobachten ob ueberschrieben + Logs ziehen (inspect.sh logs ... | grep BUGB-EWB).

### Instrumentierung Pass 1 — 6 Mess-Punkte (file:line + Tag/Format + getestete Hypothese)

- **MP1 (FE manual_ewb-EMIT):** static/pip-launcher.js ~2280 in `_triggerEwb`. Generiert `click_id` (`clk_<ts>_<rand>`) SYNCHRON vor dem emit, sendet sie im Payload mit. Log: `[BUGB-EWB] MP1 manual_ewb emit click_id=... typ=... ts=...`. Testet **A** (1 Klick = 1 oder N Emits; gleiche click_id N-mal = FE-Doppel-Bind/Bubbling).
- **MP2 (BE manual_ewb-RECV):** services/deepgram_service.py ~852 in `handle_manual_ewb`. Log: `[BUGB-EWB] MP2 manual_ewb RECV sid=... click_id=... typ=... recv_ts=...`. Testet **A** (FE-emits vs BE-receives reconcilen: gleiche click_id mehrfach am BE = FE feuert mehrfach; verschiedene = Reconnect-Replay/Doppelklick).
- **MP3 (slot1_variant_busy_until SET/READ):** drei Stellen — (a) deepgram_service.py ~248/~253 Keyword-Pfad liest/setzt GLOBAL `ls.state[...]`; (b) claude_service.py ~1517 analyse_loop liest PER-SID `_session_state[sid]['state'][...]`; (c) claude_service.py ~819 manual-Pfad loggt busy_until + `sets_lock=False`. Logs: `[BUGB-EWB] MP3 lock READ src=keyword|analyse_loop ...` / `MP3 lock SET src=keyword ...`. Testet **B** (zwei verschiedene Speicher fuer denselben Lock + manual setzt ihn nie).
- **MP4 (Slot-1-WRITE + QUELLE):** drei Writer — (a) deepgram_service.py ~258 `streame_auto_variante(keyword)`; (b) claude_service.py ~1624 `qa_slot1(analyse_loop)` (+ busy_until_at_write); (c) claude_service.py ~819 `streame_manual_ewb_variante(manual_button)`. Log: `[BUGB-EWB] MP4 slot1 WRITE source=... sid=... lock/busy ...`. Testet **B** (zeitliche Verschachtelung manual-Stream vs auto-Write in denselben Slot).
- **MP5 (coldcall_infer Roh-Input vor json.loads):** claude_service.py ~492, direkt vor dem `json.loads`, das "Extra data line 6" wirft. Log: `[BUGB-EWB] MP5 coldcall_infer pre-parse sid=... len=... lines=... raw=<repr, 600 chars>`. Testet die JSON-Bruch-Ursache (mehrere Objekte / Trailing-Prosa von Haiku).
- **MP6 (ts_ms-Setzpunkt):** routes/app_routes.py ~63 in `_transcript_entries_to_segments`. Log pro Entry: `[BUGB-EWB] MP6 ts_ms btn=... raw_ts_type=... raw_ts=... abs_ms=... base=... rel_ts_ms=...`. Testet **C** (Knopf-Entry raw_ts=float vs gesprochen=str 'HH:MM:SS').

### Static-Reading LEADS (NICHT gefixt — nur fuer Pass 2)

- **Lead A (FE-Multi-Fire) — eher NICHT FE-Doppel-Bind:** `_wirePipButtons` (pip-launcher.js:1749) wird in `_setupPipWindow` aufgerufen, das pro PiP-Fenster GENAU EINMAL laeuft. Die EWB-Delegation (`pipWindow.document.addEventListener('click', .closest('.pip-ewb-btn'))`, :1787/1802) ist robust gegen DOM-Re-Renders. => 16×/6× ist wahrscheinlich KEIN reines FE-Bubbling. Verdacht verschiebt sich auf Reconnect-Replay (Socket re-emit nach drop) ODER mehrfache physische Klicks bei haengender UI. MP1/MP2-click_id-Reconciliation entscheidet das.
- **Lead B (Slot-1-Race) — STARK gestuetzt:** (1) `streame_manual_ewb_variante` prueft/setzt `slot1_variant_busy_until` per Design NICHT (claude_service.py:760 Docstring + verifiziert kein Lock-Zugriff). (2) Der Lock existiert in ZWEI getrennten Speichern: Keyword-Pfad nutzt GLOBAL `ls.state[...]` (deepgram:247/251), analyse_loop/QA nutzt PER-SID `_session_state[sid]['state'][...]` (claude:1516/1630) — diese teilen den Wert evtl. gar nicht. (3) FE: `qa_slot1` schreibt `pip-slot-body-1.textContent = txt` (pip-launcher.js:2495) — DERSELBE DOM-Node den der Knopf-Stream via `pip_token` beschreibt (:2355). => analyse_loop/keyword kann den Knopf-Vorschlag mitten im Vorlesen ueberschreiben. **Plausibelster Root-Cause des Ueberschreibens. Fix-Richtung (Pass 2): manual_ewb-Pfad muss denselben Lock setzen, und beide Pfade muessen denselben Speicher nutzen.**
- **Lead C (ts_ms=0) — STATISCH BESTAETIGT:** Knopf-Transcript-Zeile schreibt `'ts': time.time()` (float-epoch, deepgram_service.py:934), gesprochene Zeile schreibt `ts=datetime.now().strftime('%H:%M:%S')` (str, deepgram_service.py:66). Der Transform `_ts_to_ms_of_day` (app_routes.py:36) macht `str(ts).split(':')` und erwartet 'HH:MM:SS' -> float-epoch hat keine ':' -> ValueError -> return 0. Daher ALLE Knopf-Events ts_ms=0. Der unmoegliche `ts_ms=61019000` (~17h) entsteht wenn der ERSTE Transcript-Entry ein Knopf ist (abs=0 -> base=0), dann ergibt eine spaetere gesprochene Zeile `rel = ms-of-day - 0` = absolute Tageszeit. **Ein Format-Mismatch, zwei Symptome. Fix-Richtung (Pass 2): Knopf-Pfad ts im selben 'HH:MM:SS'-Format schreiben (oder Transform float-epoch-tolerant machen). NICHT in Pass 1.**

reasoning_checkpoint: (Pass 1 ist Instrumentierung-only — kein Fix, daher kein Fix-Reasoning-Checkpoint. Leads oben dokumentiert; Confirmation via Live-Logs in Pass 2.)
tdd_checkpoint:

## Evidence Log (Pass 2 — nach Live-Logs)

(leer — wird nach inspect.sh logs gefuellt)

## Eliminated

(noch keine)

## Resolution

root_cause:
fix:
verification:
files_changed:
