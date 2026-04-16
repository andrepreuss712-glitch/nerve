---
slug: pip-neuer-call-alt-abort
status: resolved
trigger: "BUG-11 Live-Assistent bricht bei jedem 2. 'Neuer Call' nach 1-2s ab"
created: 2026-04-16
updated: 2026-04-16
---

# Debug Session: PiP "Neuer Call" — alternierender Abort nach 1-2s

## Symptoms

- **Expected:** "Neuer Call" (im Postcall) → neue Session laeuft wie Call #1
- **Actual:** **Jedes zweite Mal** bricht die Session 1-2s nach Start ab, Popup "Call beendet"
  - Call 1: normal
  - Call 2 via "Neuer Call": abort nach 1-2s
  - Call 3 via "Neuer Call": normal bis User beendet
  - Call 4 via "Neuer Call": abort nach 1-2s
  - Alternierend — klassisches "doppelt registrierter Handler"-Pattern
- **Gegenprobe:** Postcall → Details (`/logs/{id}`) → von dort "Neuer Call" → NIE Bug, beliebig oft wiederholbar
  - Full page reload raeumt State, In-Place-Restart nicht
- **Erstmals beobachtet:** 2026-04-16 nach Deploy `7526129` (BUG-A/B Fixes von heute)

## Context

- Nachfolger von BUG-07/08 Klasse (siehe `.planning/debug/pip-nextcall-ewb-regression.md`)
- Selbes Szenario: `pip-live-window` DOM-Element ueberlebt Calls (wandert zwischen Haupt-Doc und PiP-Doc), inline-Styles/Handler leaken
- Deploy: `bash ./deploy.sh`
- Live: https://getnerve.app

## Current Focus

RESOLVED — Root cause gefunden und gefixt.

## Evidence

- timestamp: 2026-04-16T10:00:00
  finding: >
    `_setupPipWindow()` registriert einen `pagehide`-Handler auf `pipWindow`.
    Dieser Handler hat einen Race-Condition-Bug: er prueft `state.micStarted`
    OHNE zu pruefen ob das schliessende Fenster noch das aktive PiP-Fenster ist.
    
    Race-Ablauf beim "Neuer Call"-Klick (gerade-nummerierte Calls):
    1. Call 1 laeuft, Beenden → endCall() → _stopMic() setzt micStarted=false
    2. Postcall angezeigt. User klickt "Neuer Call"
    3. nextCall() → pipWin1.close() → _cleanup() setzt state.pipWindow=null
    4. open() → User klickt durch Modal → startCall() → _openPipAndMic()
    5. requestWindow() loest auf → _setupPipWindow(pipWin2) → Mic startet → micStarted=true
    6. **pagehide von pipWin1 feuert** (async, ~1-2s nach close()) → handler sieht
       state.pipWindow===null und state.micStarted===true → ruft _stopMic() auf
    7. _stopMic() emittet stop_live_session auf Call-2-Socket → Deepgram-Session beendet
       → "Call beendet"-Popup erscheint nach 1-2s ✗
    
    Warum alternierend (1=ok, 2=abort, 3=ok, 4=abort):
    - Call 1 → Beenden: kein vorheriger pipWin → kein stalempagehide
    - Call 2: pagehide von pipWin1 race-triggert _stopMic() → abort
    - Call 2 (aborted): _stopMic() setzt micStarted=false → naechster pagehide (von pipWin2) 
      sieht micStarted=false → kein abort
    - Call 3: sauber
    - Call 4: pagehide von pipWin3 race-triggert wieder → abort

## Eliminated

- _wirePipButtons() double-listener: nein — jeder Call bekommt ein neues pipWindow-Document, 
  Listener leben im alten Document, koennen nicht auf neues Document feuern
- Socket-Event-Leak (stop_live_session via altes Socket): nein — _cleanup() disconnected 
  das alte Socket vor dem neuen Call
- Backend-seitige Spurious-Events: nein — Race ist rein frontend/DOM

## Resolution

- **root_cause:** `pagehide`-Handler in `_setupPipWindow()` prueft `state.micStarted` 
  ohne zu verifizieren ob das schliessende PiP-Fenster noch das aktive ist. 
  Wenn `nextCall()` `pipWin1.close()` aufruft und danach Call 2 startet, feuert 
  `pagehide` async mit `micStarted=true` (von Call 2) und stoppt Call 2.
- **fix:** Guard hinzugefuegt: `if (state.pipWindow === pipWindow)` vor mic-Teardown 
  und `state.pipWindow = null`. Nur wenn das schliessende Fenster noch das aktive ist 
  (User-initiierter OS-Close) wird der Mic gestoppt. Beim programmatischen Close via 
  `nextCall()` ist `state.pipWindow` bereits null → kein Teardown → neue Session bleibt intakt.
- **file:** `static/pip-launcher.js`, Funktion `_setupPipWindow()`, pagehide-Handler, Zeile ~928
