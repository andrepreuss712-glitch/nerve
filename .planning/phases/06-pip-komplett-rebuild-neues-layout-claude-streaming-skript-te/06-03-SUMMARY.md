---
phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te
plan: "03"
subsystem: pip-frontend-js + backend-dispatch
tags: [pip, streaming, teleprompter, consent, opacity, dual-slot]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [pip-streaming-e2e, pip-consent-flow, pip-teleprompter, pip-opacity, pip-proactive-fill]
  affects: [static/app.js, services/claude_service.py, services/deepgram_service.py]
tech_stack:
  added: []
  patterns:
    - Dual-slot streaming state machine with _pipSlots object
    - D-03 slot alternation via function-level attributes on analyse_loop
    - Consent gate before meeting-mode live session
    - localStorage-backed opacity slider with debounced save
    - 8-second manual override for teleprompter scroll/click
key_files:
  created: []
  modified:
    - static/app.js
    - services/claude_service.py
    - services/deepgram_service.py
decisions:
  - Wired pipPopulateSkripte into pipPopulateProfiles change handler (not a separate step-3 hook) for simpler profile-switch flow
  - coaching_loop PiP forwarding uses pip_token_done directly (no streaming) since coaching tips are already complete
  - updatePipFromErgebnis/Coaching kept but guarded with PiP-active check per D-09 (main tab still uses polling)
metrics:
  duration: "~20min"
  completed_date: "2026-04-14"
  tasks_completed: 3
  files_modified: 3
---

# Phase 06 Plan 03: PiP JS Logic + Backend Dispatch Summary

**One-liner:** End-to-end PiP streaming wired: Socket.IO token handlers with dual-slot D-03 state machine, consent gate for meeting mode, localStorage opacity slider, teleprompter with 8s manual override, and analyse_loop dispatch to streaming when active_sid is set.

## What Was Built

### Task 1: Streaming handlers, dual-slot state machine, consent flow, opacity slider

Added to `static/app.js`:

- `socket.on('pip_stream_start')` — clears slot state, adds `.pip-streaming` cursor class, supports `replace_all` flag for topic switches (D-03)
- `socket.on('pip_token')` — appends token to `_pipSlots[slot].text`, discards if slot not streaming
- `socket.on('pip_token_done')` — renders formatted result, triggers teleprompter position update and proactive fill
- `socket.on('pip_stream_error')` — shows error text, clears streaming state
- `var _pipSlots` dual-slot state object
- `renderPipSlotResult()` — formats einwand badge + gegenargument, or notiz fallback
- `pipConsentGranted()` / `pipConsentDenied()` — consent flow with server mode update emit
- `setPipState()` updated with `'consent'` section and opacity slider visibility toggle (D-15)
- `initPipLiveContent()` — replaces `initPipContent()` for live state; initializes badge, EWB, timer, opacity, teleprompter, slot reset
- `initPipOpacitySlider()` + `setPipBgOpacity()` — range slider with `rgba(6,6,10,value)` background-only opacity (D-16), debounced localStorage save
- Removed: `handlePipTabClick`, `setPipTabFromKI`, `activatePipTab` function definitions
- Guarded `updatePipFromCoaching`/`updatePipFromErgebnis` callers to skip when PiP is active (D-09)

### Task 2: Teleprompter, script dropdown, proactive fill, script block wiring

Added to `static/app.js`:

- `renderTeleprompterBlocks(inhalt, activeBlockIdx)` — splits on `\n\n`, renders `.tp-block` divs with click handlers, 8s manual override timeout (D-13, D-14)
- `highlightTeleprompterBlock()` — toggles `.tp-block-active` class, smooth scrollIntoView
- `updateTeleprompterPosition()` — respects `_teleprompterManualOverride` flag (D-13)
- `pipPopulateSkripte(profileId)` — fetches `/api/skripte?profile_id=`, populates select, wired into `pipPopulateProfiles` change handler (D-12)
- `window._pipActiveSkript` — active script text state
- `fillProactiveSlots(result)` — fills slot 0 with phase/frage/notiz, slot 1 with KB% trend (D-02)
- `setPipSlotProactive()` — sets label + content on any slot
- `start_live_session` emit now includes `skript_inhalt: window._pipActiveSkript`

Added to `services/deepgram_service.py`:

- `skript_inhalt` parsed from `data` dict in `handle_start_live_session`
- Truncated to 50000 chars (T-06-07 DoS mitigation)
- Stored as `ls.state['aktives_skript_inhalt']` and `ls.state['skript_bloecke']` (list of paragraph blocks)

### Task 3: Wire analyse_loop to streaming dispatch

Modified `services/claude_service.py`:

- `analyse_loop()`: reads `active_sid` from `ls.state` under lock; if set, uses D-03 dual-slot logic (slot 0 default, slot 1 if slot 0 used within 5s) and calls `analysiere_mit_claude_streaming(neuer_text, kontext, active_sid, slot_id)`; else falls back to `analysiere_mit_claude()` for main-tab polling path (D-09)
- `coaching_loop()`: before `sio.emit('coaching', ...)`, reads `active_sid` and if set emits `pip_token_done` with slot 1 and coaching result fields to `room=_pip_sid`

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 | aa94f27 | static/app.js |
| 2 | 40c3fbb | static/app.js, services/deepgram_service.py |
| 3 | 080638b | services/claude_service.py |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written, with one minor structural choice:

**[Design Choice] pipPopulateSkripte wired via pipPopulateProfiles change handler**
- The plan said "wire into the profile selection handler". The cleanest insertion point was inside `pipPopulateProfiles()` itself, which adds a `change` event listener on the profile select and calls `pipPopulateSkripte` on initial load + on change.
- This is equivalent to the plan intent and avoids duplicating event listener logic.

## Known Stubs

- `/api/skripte?profile_id=` endpoint: The frontend calls this but the route may not exist yet. If the endpoint returns a non-JSON or 404, `pipPopulateSkripte` will log a console error and leave the select with only "Kein Skript". This is graceful degradation — no crash, teleprompter just stays empty. A future plan needs to implement the `/api/skripte` route.

## Threat Flags

None beyond what was already in the plan's threat model (T-06-07 mitigated, T-06-08 and T-06-09 accepted).

## Self-Check: PASSED

Files modified exist:
- static/app.js: confirmed
- services/claude_service.py: confirmed
- services/deepgram_service.py: confirmed

Commits exist:
- aa94f27: confirmed
- 40c3fbb: confirmed
- 080638b: confirmed
