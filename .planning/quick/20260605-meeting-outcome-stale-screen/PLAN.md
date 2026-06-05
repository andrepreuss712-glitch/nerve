---
type: quick
slug: meeting-outcome-stale-screen
created: 2026-06-05
files_modified:
  - static/pip-launcher.js
cross_ai: skipped   # Bugfix mit klarer, verifizierter Root-Cause (CLAUDE.md Punkt 7)
---

# Quick: Meeting-Post-Call Stale-Outcome-Screen + Debug-Cleanup

## Objective

Zwei kleine Frontend-Fixes in `static/pip-launcher.js`, Folge der `/gsd-debug`-Session
[[meeting-postcall-kein-outcome]] (Root-Cause via [MEETDBG]-Logs + Andre-Screenshot bestätigt).

## FIX 1 — Stale-Outcome-Screen beim Meeting-Termin-Schritt ausblenden

**Root-Cause (verifiziert):** Im `meeting_booked`-Branch des Confirm-Handlers wird
`renderMeetingForm(json)` aufgerufen. `renderMeetingForm` clearet (MM-03) nur seinen
eigenen Mount (`#meeting-form-mount`), NICHT die Host-Section `pip-outcome-section`
(`sec`, im `_renderOutcomeUx`-Closure). Folge: Outcome-Auswahl-Screen bleibt sichtbar,
`confirmBtn` eingefroren auf "Bewertung wird berechnet…" (gesetzt, nie zurückgesetzt) →
beide Screens stapeln sich.

- **FIX 1a:** Im `meeting_booked`-Branch `sec.style.display = 'none'` VOR `renderMeetingForm(json)`.
- **FIX 1b (Control-Flow-Edge, CLAUDE.md Punkt 14):** Der "Falsches Ergebnis? Zurück"-Button
  (`meeting-back-btn`) setzt `outcomeRendered='0'` und re-rendert via
  `_renderOutcomeUx(state.pendingOutcomeData)`. Damit die ausgeblendete Section nach "Zurück"
  wieder sichtbar wird, in `_renderOutcomeUx` (nach `sec.innerHTML=''`) `sec.style.display=''`
  erzwingen. `_renderOutcomeUx` resettete display vorher NICHT → ohne FIX 1b wäre der
  Auswahl-Screen nach "Zurück" unsichtbar (neuer Bug).

## FIX 2 — Diagnose-Logs entfernen

Alle 8 `console.log`-Statements mit Marker `[MEETDBG]` (7 Probe-Punkte) aus
`static/pip-launcher.js` entfernen (liefen live im Browser jedes Users).

## Verify (Production-only, CLAUDE.md HART)

- `grep -c MEETDBG static/pip-launcher.js` == 0
- `node --check static/pip-launcher.js` OK
- Deploy `bash deploy.sh production` (JS-only, statisch via nginx — kein Service-Restart nötig)
- Andre: 1 Meeting-Test-Call → Auswahl-Screen erscheint, Confirm → NUR Termin-Formular
  (kein gestapelter Screen, kein eingefrorener "Bewertung wird berechnet…"), dann
  einmal "Falsches Ergebnis? Zurück" → Auswahl-Screen wieder sichtbar.
