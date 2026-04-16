---
slug: pip-neuer-call-alt-abort
status: resolved
trigger: "BUG-11 Live-Assistent bricht bei jedem 2. 'Neuer Call' nach 1-2s ab"
created: 2026-04-16
updated: 2026-04-16
reopened: 2026-04-16 — f2fe4f6 pagehide-Guard hat das Problem NICHT behoben
resolved: 2026-04-16 — BUG-11b fix (commit 2d44119)
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

## NEUE EVIDENCE (2026-04-16 nachmittags, nach f2fe4f6-Deploy)

### Console-Logs vergleichen:

**Gesunder Call (User beendet manuell):**
```
PiP click-delegation wired
Mic started, mode: cold_call
Beenden click (delegation)    <- User-Input
Mic stopped
Socket disconnected
```

**Kaputter Call (Mic stoppt automatisch ohne User-Input):**
```
PiP click-delegation wired
Mic started, mode: cold_call
Mic stopped                    <- KEIN "Beenden click" davor!
(manchmal kein Socket disconnected)
```

### Zusatz-Symptom:
**Uhr im Header tickt ungleichmaessig** -> starker Hinweis auf doppelt registrierten Timer.

## Evidence

- timestamp: 2026-04-16T10:00:00
  finding: >
    `_setupPipWindow()` registriert einen `pagehide`-Handler auf `pipWindow`.
    Dieser Handler hat einen Race-Condition-Bug: er prueft `state.micStarted`
    OHNE zu pruefen ob das schliessende Fenster noch das aktive PiP-Fenster ist.

- timestamp: 2026-04-16T11:00:00 (f2fe4f6 Deploy)
  finding: >
    Erster Fix: Guard `if (state.pipWindow === pipWindow)` vor mic-Teardown.
    Deckt NUR den async-Fall ab. Bug persistiert.

- timestamp: 2026-04-16T afternoon
  finding: >
    BUG-11b Root Cause: Chrome kann `pagehide` SYNCHRON waehrend `pipWin.close()` feuern.
    In nextCall() war die Reihenfolge: (1) pipWin.close(), (2) _cleanup() [setzt state.pipWindow=null].
    Wenn pagehide SYNCHRON in (1) feuert, sieht der Guard state.pipWindow===pipWin (NOCH nicht null) →
    Guard evaluiert TRUE → _stopMic() wird gerufen → Call 2 wird abgebrochen.
    
    Zusaetzlich: _startTimer() hatte kein _stopTimer()-Guard → bei Race konnte altes Interval
    weiterlaufen (erklaert den ungleichmaessigen Timer-Tick).

## Eliminated

- _wirePipButtons() double-listener: nein — jeder Call bekommt ein neues pipWindow-Document
- Socket-Event-Leak (stop_live_session via altes Socket): nein — _cleanup() disconnected das alte Socket
- Backend-seitige Spurious-Events: nein — Race ist rein frontend/DOM
- app.js socket disconnect handler: nein — ruft nur app.js stopMicStream() auf, die micStarted=false hat
- Server-initiated events: nein — Server emittiert kein session_end/call_end an Client

## Resolution

- **root_cause (BUG-11b):** Chrome feuert `pagehide` SYNCHRON waehrend `pipWin.close()` — BEVOR
  `_cleanup()` `state.pipWindow = null` setzen kann. Der f2fe4f6-Guard `state.pipWindow === pipWindow`
  evaluiert dann noch `true` (alter Wert), und `_stopMic()` beendet die neue Session.
  
  Zweiter Faktor: `_startTimer()` fehlte ein `_stopTimer()`-Guard → bei einem Timing-Race konnten
  zwei setInterval-Instanzen parallel laufen (erklaert den ungleichmaessigen Uhren-Tick).

- **fix (commit 2d44119):**
  1. `nextCall()` und `showDetails()`: `state.pipWindow = null` ZUERST setzen, DANN `oldWin.close()`.
     → Guard kann nie mehr `state.pipWindow === oldWin` treffen (null === win → false).
  2. `_startTimer()`: `_stopTimer()` am Anfang aufrufen → kein Interval-Leak moeglich.
  3. `_stopMic()`: `console.trace()` hinzugefuegt → kuenftige Regressionen sofort debuggbar.

- **file:** `static/pip-launcher.js`, Funktionen `nextCall()`, `showDetails()`, `_startTimer()`, `_stopMic()`
- **commit:** 2d44119
- **deployed:** 2026-04-16 via `bash ./deploy.sh`
