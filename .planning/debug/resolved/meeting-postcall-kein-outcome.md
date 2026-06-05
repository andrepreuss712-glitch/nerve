---
status: resolved
trigger: "Meeting-Modus: nach Call-Ende kein Ergebnis-Auswahl-Screen, springt direkt ins Scoreboard, 'Score wird berechnet' bleibt hängen, 'Zur Auswertung'-Knopf fehlt. Cold Call läuft sauber. NICHT von Phase STT (nur deepgram_service.py). Wahrscheinlich pre-existing, Meeting-Post-Call-Pfad nie exerziert."
created: 2026-06-05
updated: 2026-06-05
resolved_by: .planning/quick/20260605-meeting-outcome-stale-screen/
phase: pre-existing (entdeckt während 08.23.2.STT Prod-Test)
approach: logging-first (CLAUDE.md Punkt 15) — kein Fix im ersten Pass
---

# Debug: Meeting-Postcall — kein Outcome-Auswahl-Screen

## Symptoms

- **Expected:** Nach Call-Ende erscheint der Outcome-Auswahl-Screen ("Call wirklich beenden?" + Outcome-Buttons + Bestätigen). Nach Confirm → Score + "Zur Auswertung".
- **Actual (nur Meeting):** Kein Auswahl-Screen, springt direkt ins Scoreboard, "Score wird berechnet" hängt, "Zur Auswertung" fehlt komplett.
- **Cold Call:** läuft sauber durch.
- **Timeline:** vermutlich pre-existing; Meeting-Post-Call-Pfad bisher nie live exerziert.

## Evidence (Production-Server-Logs, 2 Test-Calls 2026-06-05)

- **Cold Call (ok):** `POST /api/beenden 200 → postcall_outcome 200 → calls/<id>/correct_outcome 200 → crm/meetings 200 → GET /api/postcall/trend 200 → postcall_cards 200`
- **Meeting (bug):** `POST /api/beenden 200 → postcall_outcome 200 → postcall_cards 200` — **es fehlen `correct_outcome` UND `trend`.**

**Ableitung:** `correct_outcome` (Frontend: `static/pip-launcher.js:4370`, im Confirm-Button-Handler) feuert nie → der Outcome-Confirm-Schritt wird im Meeting nie ausgelöst. `trend` (`:3393`, in `_revealScoreAndActions`) fehlt konsequenterweise auch (Reveal hängt am Confirm).

## Code-Karte (Call-Sites von _renderOutcomeUx)

| Call-Site | Zeile | Trigger |
|---|---|---|
| Socket `outcome_ready` | 2555 | Backend-Emit (REQ-D-4) — **Verdächtiger "alterner Pfad"** |
| Reconnect `latest_outcome` | 2586 | Socket-`connect`-Fallback |
| 9s-Timeout | 3102 | Haiku-Timeout (outcome:null) |
| postcall_outcome success | 3140 | nur wenn `paResult.call_id` |

`_renderOutcomeUx` (4212): Guard `outcomeRendered==='1'`→return (4225); `!callId`→return (4232); `_decideModalState` (4235) → bei `'final'` read-only Summary + return (4250, KEIN Confirm-Button); Confirm-Handler fired `correct_outcome` (4370), bei `meeting_booked`→`renderMeetingForm` sonst `_revealScoreAndActions` (4400-4404).

## Current Focus

hypothesis: Im Meeting wird der Outcome-Auswahl-Screen entweder (a) gar nicht gerendert (`!callId`-return, oder `paResult.call_id` fehlt im Meeting), oder (b) durch einen früheren `outcome_ready`-Socket-Emit bzw. `_decideModalState==='final'` als read-only/no-confirm gerendert → Idempotenz-Guard (4225) lässt den echten Render-Pfad früh aussteigen → Confirm-Button (und damit `correct_outcome`) existiert nie.
test: 7 `[MEETDBG]`-console.logs instrumentieren, auf Prod deployen, André macht 1 Meeting-Test-Call, Browser-Console-Log lesen.
expecting: Log zeigt welcher Call-Site `_renderOutcomeUx` zuerst trifft, mit welchem callId/outcome/source, ob ein Guard greift, welcher `modalState` entschieden wird.
next_action: Logs einbauen (kein Fix), deploy, reproduzieren lassen.

## Evidence Log

- 2026-06-05: Server-Log-Diff Cold-Call vs Meeting (oben). Frontend-Confirm-Pfad feuert im Meeting nie.

## Eliminated

- Phase 08.23.2.STT als Ursache — STT hat nur `services/deepgram_service.py` angefasst, nicht `pip-launcher.js`.

## Resolution

root_cause: Im `meeting_booked`-Branch des Confirm-Handlers (`_renderOutcomeUx`) ruft der Code `renderMeetingForm(json)` auf. `renderMeetingForm` clearet (MM-03) NUR seinen eigenen Mount `#meeting-form-mount`, NICHT die Host-Section `pip-outcome-section` (`sec`). Dadurch blieb der Outcome-Auswahl-Screen sichtbar und stapelte sich hinter dem Termin-Formular — mit `confirmBtn` eingefroren auf "Bewertung wird berechnet…" (nie zurückgesetzt). Andre-Screenshot bestätigte die Stapelung. (Hinweis: die [MEETDBG]-Logs grenzten den Pfad ein; die endgültige Bestätigung kam aus dem Screenshot, der die zwei gestapelten Screens zeigte.)
fix: FIX 1a — `sec.style.display='none'` im `meeting_booked`-Branch VOR `renderMeetingForm`. FIX 1b — `sec.style.display=''` in `_renderOutcomeUx` (nach `innerHTML=''`), damit der "Zurück"-Re-Render die Section wieder sichtbar macht (Control-Flow-Edge). FIX 2 — alle [MEETDBG]-Logs entfernt.
verification: `grep -c MEETDBG`==0, `node --check` OK, Production-Deploy + Andre-Meeting-Test-Call (inkl. "Zurück") ausstehend.
files_changed: static/pip-launcher.js
fixed_in: .planning/quick/20260605-meeting-outcome-stale-screen/ (commit 765a52b)
