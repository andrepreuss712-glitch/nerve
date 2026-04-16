---
slug: pip-nextcall-ewb-regression
status: resolved
trigger: "BUG-A + BUG-B Regression im PiP Post-Call Flow (Phase 06.1)"
created: 2026-04-16
updated: 2026-04-16
---

# Debug Session: PiP "Nächster Call" EWB-Leiste fehlt + Details-Navigation kaputt

## Symptoms

### BUG-A (Blocker)
- **Expected:** "Nächster Call" Button → neuer Call mit allen 5 EWB-Buttons gerendert
- **Actual:** Call startet, Teleprompter + Slot 0 + Slot 1 da, **EWB-Leiste rendert nicht**
- **Repro:** Call 1 starten → beenden → Post-Call → "Nächster Call"
- **Workaround:** Post-Call → Details → von dort Neuer Call → Buttons da
- **Hypothese User:** "Nächster Call" macht JS-State-Reset ohne DOM-Re-Render der EWB-Leiste

### BUG-B
- **Expected:** Post-Call Details-Button → `/logs/{conv_id}` (Auswertungs-Dashboard)
- **Actual:** Navigiert zu `/logs` (generische Liste)
- **War gestern gefixt:** BUG-11 in Commit `3648cbb` (2026-04-15)
- **Regression erstmals heute (2026-04-16) beobachtet**

## Context
- Phase 06.1 formal verifiziert 2026-04-15 (Commit `0f42811`)
- Gestern UAT-Runde R2 mit ~20 Fixes auf main (letzter Commit `cde024d`)
- Beide Bugs im Scope von `static/pip-launcher.js` (nextCall, showDetails, _cleanup, open)
- Handoff-Doc: `.planning/phases/06.1-pip-uat-fixes-.../06.1-HANDOFF-R2.md`
- Deploy-Pfad: `bash ./deploy.sh`
- Live: https://getnerve.app

## Evidence

### BUG-A Root Cause — DOM-State-Leak zwischen Calls
- `_showPostcallRaw()` (Zeile ~1590) setzt explizit `nlp-ewb-row.style.display = 'none'`
  (in der forEach-Schleife: `['nlp-btn-beenden', 'nlp-ewb-row', 'pip-section-live', ...]`)
- `pip-live-window` DOM-Element überlebt den Call — es wird in die neue PiP-Window verschoben,
  nicht neu erzeugt. Inline-Style `display:none` bleibt erhalten.
- `_showPipLive()` (nächster Call) macht `pip-section-live.style.display = 'flex'`, setzt aber
  `nlp-ewb-row.style.display` NICHT zurück.
- `_renderEwbButtons()` setzt nur `row.innerHTML`, nie `row.style.display`. Buttons sind im DOM,
  aber durch den verbleibenden inline-Style unsichtbar.
- Warum Workaround funktioniert: Navigation zu `/logs/{id}` → full page reload →
  pip-live-window DOM neu erzeugt → kein verbleibender inline-Style.

### BUG-B Root Cause — _cleanup() nullt lastConvId vor Verwendung
- `showDetails()` ruft `_cleanup()` auf (Zeile 1620) BEVOR `state.lastConvId` gelesen wird
- `_cleanup()` setzt `state.lastConvId = null` (Zeile 1637)
- Check `if (state.lastConvId)` (Zeile 1621) ist deshalb immer false → immer `/logs`
- BUG-11 Fix (`3648cbb`) hat die Logik korrekt implementiert, aber `_cleanup()` wurde
  danach (in R2-Runde) NACH den State-Reads verschoben → Regression

## Eliminated
- `_cleanup()` löscht profileDaten NICHT (profileDaten überlebt den Cleanup)
- Async-Race zwischen fetch('/api/launcher/init') und _renderEwbButtons() — beide
  laufen in verschiedenen Phasen, kein Timing-Problem
- `nlp-ewb-row` existiert nicht im DOM — es ist da, nur display:none

## Resolution

### Fix BUG-A
**File:** `static/pip-launcher.js`, Funktion `_showPipLive()`
**Change:** `nlp-ewb-row.style.display = ''` hinzugefügt direkt nach dem detailsBtn-Reset,
bevor `_renderEwbButtons()` (aus `_initPipLive()`) aufgerufen wird. Setzt den
Postcall-Hidden-State zurück.

### Fix BUG-B
**File:** `static/pip-launcher.js`, Funktion `showDetails()`
**Change:** `var convId = state.lastConvId` VOR `_cleanup()` gespeichert; dann
`window.location.href` nutzt `convId` statt `state.lastConvId`.

### Commits
- BUG-A: fix(pip): reset nlp-ewb-row display in _showPipLive after postcall
- BUG-B: fix(pip): capture lastConvId before _cleanup() in showDetails
