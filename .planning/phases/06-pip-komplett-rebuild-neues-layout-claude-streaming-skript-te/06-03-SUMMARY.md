---
phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te
plan: 03
subsystem: ui
tags: [pip, socket.io, streaming, teleprompter, opacity, consent, javascript]

requires:
  - phase: 06-01
    provides: Backend streaming events pip_stream_start/pip_token/pip_token_done/pip_stream_error emitted via Socket.IO
  - phase: 06-02
    provides: New HTML structure with pip-section-live, pip-section-consent, pip-slot-0/1, pip-teleprompter, pip-opacity-slider IDs

provides:
  - pip-launcher.js fully rewired for Phase 06 split layout
  - Socket.IO streaming listeners replacing polling in PiP
  - Dual-slot state machine with topic-switch (replace_all) logic
  - Meeting-mode consent flow with cold_call fallback
  - Teleprompter renderer with KI position tracking and manual override
  - Opacity slider with localStorage persistence
  - Proactive slot fill between einwaende
  - Skript content sent to backend at session start

affects: [06, live-session, pip-window]

tech-stack:
  added: []
  patterns:
    - "Socket.IO streaming: pip_stream_start/pip_token/pip_token_done replaces polling pattern"
    - "Dual-slot state machine: state.pipSlots[0|1] tracks streaming/text/result per slot"
    - "PiP consent gate: meeting mode shows consent screen, reject falls back to cold_call"
    - "Teleprompter manual override: 8s timeout after scroll/click resets to KI position tracking"
    - "Opacity CSS custom property: --pip-bg-alpha on pip-section-live controls background alpha only"

key-files:
  created: []
  modified:
    - static/pip-launcher.js

key-decisions:
  - "Polling (_pollLoop/_startPolling/_stopPolling/_handleErgebnis) fully removed — Socket.IO streaming handles all AI results"
  - "Tab management (_switchPipTab) removed — new split layout has no tabs"
  - "EWB _triggerEwb keeps POST to /api/analyse_line but drops .then() handler — results now arrive via streaming events"
  - "_showPostcallRaw updated to hide pip-section-live/pip-section-consent instead of old .pip-tabs/.pip-content selectors"
  - "PiP body background hardcoded to #06060a (always dark per UI-SPEC D-09)"

patterns-established:
  - "Streaming slot bodies use textContent (not innerHTML) for XSS safety per T-06-08"
  - "Consent text rendered via textContent (not innerHTML) for XSS safety per T-06-09"

requirements-completed: [PIP-01, PIP-02, PIP-03, PIP-04, PIP-05]

duration: 13min
completed: 2026-04-14
---

# Phase 06 Plan 03: pip-launcher.js Streaming Wiring Summary

**Socket.IO streaming listeners, dual-slot state machine, meeting consent flow, teleprompter with manual override, and localStorage opacity slider replace the polling-based tab layout in pip-launcher.js**

## Performance

- **Duration:** 13 min
- **Started:** 2026-04-14T17:58:10Z
- **Completed:** 2026-04-14T18:11:30Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced entire polling infrastructure (_pollLoop, _startPolling, _stopPolling, _handleErgebnis) with Socket.IO streaming listeners (pip_stream_start, pip_token, pip_token_done, pip_stream_error)
- Implemented dual-slot state machine: state.pipSlots[0|1] tracks streaming/text/result; replace_all flag clears both slots on topic switch (D-03)
- Added consent flow for meeting mode: _showPipConsent gates live section, reject falls back to cold_call with backend notification (D-05/D-06/D-07)
- Added teleprompter: _initTeleprompter/_renderTeleprompterBlocks/_updateTeleprompterPosition with 8s manual override timer (D-11/D-13/D-14)
- Added opacity slider: _initOpacitySlider/_setPipBgOpacity with localStorage persistence via nerve_pip_opacity key (D-15/D-16/D-17)
- Added proactive fill: _showProactiveContent/_showProactiveTipp populates idle slot with phase hints and KB trend (D-02)
- Wired skript_inhalt/skript_bloecke into start_live_session emit (D-12)
- Removed _switchPipTab (tabs gone), updated _showPostcallRaw for new section IDs

## Task Commits

1. **Task 1: Streaming handlers, dual-slot state machine, consent flow, remove polling** - `068844c` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `static/pip-launcher.js` - Full Phase 06 rewire: streaming, dual-slot, consent, teleprompter, opacity, proactive fill, skript wiring

## Decisions Made

- Polling fully removed — no backward compatibility shim needed since Plan 01 backend now emits streaming events
- EWB button POST kept but .then() handler dropped — streaming events deliver results instead
- backward-compat `coaching` socket listener retained to forward tips to slot 1 if not streaming
- PiP body background set to #06060a (dark) as required by UI-SPEC D-09

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Next Phase Readiness

- pip-launcher.js is fully wired for the Phase 06 split layout
- All streaming events are handled; dual-slot state machine is operational
- Consent flow, teleprompter, and opacity slider are in place
- Phase 06 is ready for end-to-end verification

---
*Phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te*
*Completed: 2026-04-14*
