---
slug: pip-neuer-call-alt-abort
status: investigating
trigger: "BUG-11 Live-Assistent bricht bei jedem 2. 'Neuer Call' nach 1-2s ab"
created: 2026-04-16
updated: 2026-04-16
reopened: 2026-04-16 (Runde 3) — 2d44119 NICHT ausreichend; User fordert architektonischen Fix statt Symptom-Flickerei
prior_fixes: [f2fe4f6 pagehide-guard, 2d44119 pipWindow-null-first + _stopTimer-guard + console.trace]
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

## NEUE SYMPTOME (Runde 3 — nach 2d44119-Deploy, 2026-04-16)

User berichtet **3 verwandte Symptome**, Arbeitshypothese: **alle Nachwirkungen eines unvollstaendigen Post-Call-Cleanups**:

1. **Timer-DOM leak:** Header-Uhr zeigt ~1s nach Call-Ende noch Endzeit des vorherigen Calls, springt dann auf 00:00
2. **Slot-1-DOM leak:** Unteres EWB-Antwortfeld zeigt manchmal noch die Claude-Variante aus dem vorherigen Call
3. **BUG-11 persistiert:** Jeder 2. Call bricht nach 1-2s ab (auch nach 2d44119)

## ARCHITEKTUR-FIX-VORGABE (User-Entscheidung)

NICHT Symptome einzeln flicken. Stattdessen:

**Neue Funktion `_resetLiveState()`** — einmal sauber definieren was zum Live-UI-State gehoert, in einer Funktion sammeln, nach Call-Ende aufrufen UND beim Call-Start nochmal (belt-and-suspenders).

**Scope von `_resetLiveState()`:**
- Timer stoppen UND DOM auf 00:00 setzen (nicht nur state.timerInterval clearen)
- Slot 0 + Slot 1 body-Text zuruecksetzen (auf "Warte auf Gespraechsinhalt..." Default)
- Slot-Labels auf ANTWORT A / B zuruecksetzen falls geaendert
- state.pipSlots[0].text, state.pipSlots[1].text, streaming-Flags, result — alles clearen
- EWB-Buttons: pip-ewb-ai-selected Klasse entfernen, Flashing-Klasse entfernen
- Teleprompter active-Index reset
- state.micStarted, micMuted, analyser-Refs clearen falls nicht schon durch _stopMic

**NICHT anfassen (wichtig!):**
- `state.lastConvId` — fuer Details-Link im Postcall noetig
- Server-side Call-Log (Transkript, EWB-Events, conversation DB-Row)
- Postcall-Analyse / Coach-Auswertung / Fine-Tuning-Material
- Alles ausserhalb der PiP-Live-UI

**Belt-and-suspenders-Pattern:**
- `endCall()` ruft `_resetLiveState()` NACH _stopTimer+_stopMic (also bevor die Postcall-Section eingeblendet wird)
- `_showPipLive()` ruft `_resetLiveState()` AM ANFANG — garantiert dass Call N+1 aus Clean State startet egal was vorher passiert ist

**Hypothese:** Wenn _resetLiveState() sauber implementiert ist, verschwindet BUG-11 automatisch, weil die Race-Condition-Grundlage (stale Timer/Handler/DOM) wegfaellt.

## Current Focus (Runde 3)

- **hypothesis:** Root-Cause fuer alle 3 Symptome: Post-Call-Flow blendet Postcall-Section ein ohne Live-UI-Zustand zu resetten. Stale DOM/Timer/Slot-Content bleibt liegen. Beim naechsten `open()` kollidiert das mit dem Fresh-Start-Code — Race-Conditions mit verschobenen Timings produzieren den alternierenden BUG-11.
- **test:** gsd-debugger baut `_resetLiveState()` als zentrale Cleanup-Funktion, integriert an 2 Call-Sites (endCall + _showPipLive), entfernt ggf. redundante Teil-Resets die jetzt in _resetLiveState gebuendelt sind. Regression-Check gegen BUG-13 (Postcall-Section bleibt nicht stehen).
- **expecting:** Timer auf 00:00 sofort nach Beenden, beide Slots leer im Postcall, Call-2/3/4 laeuft zuverlaessig.
- **next_action:** gsd-debugger spawnen mit expliziter Architektur-Vorgabe (siehe oben).

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
