---
status: resolved
trigger: "R1-R4: PiP EWB-Buttons fehlen, EWB-Pipeline broken, Anrede-Toggle funktionslos, Vorwissen-Picker als Text — alle 4 Regressionen durch Phase 08.20.2 Plan 02+03"
created: 2026-04-30
updated: 2026-04-30
---

## Symptoms

DATA_START
- R1: PiP zeigt KEINE EWB-Buttons mehr — nach Call-Start fehlen Einwand-Buttons (z.B. "zu teuer", "kein Bedarf") komplett. Nur Anrede + Vorwissen-Knöpfe sichtbar (aber auch broken, siehe R3/R4).
- R2: EWB triggert keine KI-Antwort — User spricht Einwand ("Achso, das ist Ihnen also zu teuer"), Painpoint wird im Scoring gematcht, aber KEINE KI-Antwort generiert/gestreamt.
- R3: Anrede-Button (Du/Sie-Toggle) im PiP funktionslos — Klick ändert nichts.
- R4: Vorwissen-Picker im PiP erscheint als Text-Element, nicht als interaktiver Button — Klick passiert nichts.
DATA_END

## Timeline

DATA_START
- Regressions introduced by Phase 08.20.2 commits:
  - a8f3471: feat(08.20.2-03): rewrite renderStep4() for 3-section PreCall UI — changed pip-launcher.js (89 lines, 63 insertions/26 deletions)
  - 00e8dd9: feat(08.20.2-02): wire precall_fields into api_precall_research and api_beenden — changed routes/app_routes.py
- Key file: static/pip-launcher.js (renderStep4 rewritten)
- Pre-regression: PiP buttons worked fine (Phase 06.1 R2 session confirmed)
DATA_END

## Reproduction

DATA_START
- Start live session on getnerve.app
- Trigger PiP modal (after Call-Start)
- Expected: EWB-Buttons, Anrede-Toggle, Vorwissen-Picker all interactive
- Actual: EWB-Buttons missing, Anrede-Toggle/Vorwissen-Picker non-functional
DATA_END

## Current Focus

hypothesis: "R1 caused by schema v4 migration dropping einwaende key; R3/R4 caused by pipSetAnrede/pipSetVorwissen using main window document instead of PiP window document"
test: ""
expecting: ""
next_action: "RESOLVED — fixes applied to static/pip-launcher.js"
reasoning_checkpoint: "Investigation showed Phase 08.20.2 commits did NOT touch PiP live code. Root causes predate the reported trigger: R1 was introduced with schema v3->v4 in Phase 08.20, R3/R4 were defects in Phase 08.20-05 initial implementation."

## Evidence

- timestamp: 2026-04-30T18:00:00Z
  finding: "a8f3471 and 00e8dd9 only changed renderStep4() (PreCall UI) and backend precall_fields wiring — neither touched PiP live code (_renderEwbButtons, pipSetAnrede, pipSetVorwissen)"
  file: static/pip-launcher.js
  
- timestamp: 2026-04-30T18:05:00Z
  finding: "R1 ROOT CAUSE: services/profile_schema.py v3->v4 migration (Phase 08.20 cd5edb3) pops 'einwaende' from profile daten (line 442: daten.pop('einwaende', None)) and puts data into 'einwaende_detail'. Both _renderEwbButtons() (line 1384) and _triggerEwb() (line 1419) only read state.profileDaten.einwaende — returns [] for any v4 profile."
  file: static/pip-launcher.js:1384,1419 + services/profile_schema.py:442

- timestamp: 2026-04-30T18:10:00Z
  finding: "R3/R4 ROOT CAUSE: pipSetAnrede (line 2455), pipVorwissenEdit (line 2467), pipSetVorwissen (line 2474) all use document.getElementById() which searches the MAIN window document. After _setupPipWindow() moves #pip-live-window into pipWindow.document.body, these elements no longer exist in the main document. pipEl() helper exists and correctly searches pipWindow.document first — these functions should use it."
  file: static/pip-launcher.js:2455-2488

- timestamp: 2026-04-30T18:12:00Z
  finding: "R2 (EWB no KI response) is secondary to R1 — no EWB buttons means no manual EWB clicks. Auto-detection path (keyword_einwand_match -> pip_token_done) was separately broken by model constant bug (20251022 suffix, fixed in hotfix 52c34e5). R2 is likely resolved post-hotfix; needs live verification."
  file: config.py (MODEL_EWB, MODEL_QA, MODEL_PIP_AUTOVAR all now use alias without date suffix)

- timestamp: 2026-04-30T18:15:00Z
  finding: "window.nerveSio and window.currentSid referenced in pipSetAnrede/pipSetVorwissen are never set anywhere in the codebase — they are ghost variables. The correct approach is to use state.socket directly since these functions are defined inside the IIFE where state is in scope."
  file: static/pip-launcher.js:2462-2463,2485-2486

## Eliminated

- renderStep4() rewrite (a8f3471) as root cause — diff confirms only PreCall UI changed, zero PiP live code touched
- 00e8dd9 (precall_fields wiring) as root cause — backend-only change, no JS touched
- CSRF issue on /api/launcher/init — GET requests are exempt from Flask-WTF CSRF validation
- profileDaten reset by _cleanup() — confirmed _cleanup() does not reset state.profileDaten

## Resolution

root_cause: "R1: _renderEwbButtons() and _triggerEwb() read state.profileDaten.einwaende which is absent in Phase 08.20 schema v4 profiles (data is in einwaende_detail). R3: pipSetAnrede uses document.getElementById() but elements are in pipWindow.document after _setupPipWindow move. R4: pipVorwissenEdit and pipSetVorwissen same document context bug."
fix: "5 targeted edits to static/pip-launcher.js: (1) _renderEwbButtons reads einwaende_detail first then falls back to einwaende; (2) _triggerEwb same fix; (3) pipSetAnrede uses pipEl() for all 3 elements + state.socket.emit; (4) pipVorwissenEdit uses pipEl(); (5) pipSetVorwissen uses pipEl() for 3 elements, uses state.pipWindow.document for querySelectorAll, uses state.socket.emit."
verification: "node --check syntax OK. R2 needs live verification after R1 fix."
files_changed: "static/pip-launcher.js (5 hunks)"
