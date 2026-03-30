---
phase: 02-product-fixes
plan: "02"
subsystem: live-coaching-ui
tags: [dsgvo, compliance, css, frontend, socket-io]
dependency_graph:
  requires: []
  provides: [dsgvo-banner-timing-fix, compact-mode-circles-fix, toggle-position-fix]
  affects: [static/app.js, templates/app.html]
tech_stack:
  added: []
  patterns: [socket-io-connect-event, css-scoped-overrides, css-custom-properties]
key_files:
  created: []
  modified:
    - static/app.js
    - templates/app.html
decisions:
  - "DSGVO banner triggered on socket.on('connect') — earliest possible JS hook before audio capture begins"
  - "Toggle position fixed to top:calc(52px + var(--space-sm, 8px)) to clear 52px header"
  - "Added both .kompakt-panel .metric-circle and .kp-mc scoped overrides with flex-shrink:0"
metrics:
  duration: "15 minutes"
  completed_date: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 2 Plan 02: Live-Mode Bug Fixes Summary

**One-liner:** DSGVO banner moved to socket connect event for legal compliance; compact mode circles and toggle button position corrected via CSS scoped overrides.

## What Was Built

Fixed 4 live-mode bugs (PROD-07) across `static/app.js` and `templates/app.html`.

### Bug 1 — DSGVO Banner Timing (LEGALLY CRITICAL)

**Before:** Banner fired inside `socket.on('transcript')` handler, meaning the user's microphone was already active and transmitting audio before the consent notice appeared.

**After:** Banner now fires in `socket.on('connect')` — the Socket.IO connection event, which is the earliest possible client-side hook. Since NERVE uses server-side PyAudio for audio capture (not browser `getUserMedia`), the `connect` event represents the session establishment point, making this the legally correct location for the consent notice.

The old banner code was removed from the `transcript` handler to prevent double-firing. The `_shown` guard on the DOM element prevents repeated display on reconnects.

### Bug 2 — Script Button State

**Finding:** The `initSkript()` function in `app.html` was already correctly implemented — it uses `skriptData.some(p => p.items.length > 0)` to toggle the `disabled` class. The server (`app_routes.py`) correctly injects `active_phasen` including `skript` arrays from demo profiles. No code change was required; the existing logic handles this correctly.

### Bug 3 — Compact Mode Circles

**Added CSS scoped override:**
```css
.kompakt-panel .metric-circle { width: 36px; height: 36px; flex-shrink: 0; }
.kompakt-panel .kp-mc { flex-shrink: 0; }
```

Both rules prevent the circles from shrinking in flex containers within the compact panel. The `.kp-mc` rule addresses the actual compact panel circles (which use a different class than the main view), while the `.metric-circle` override provides future-proofing.

### Bug 4 — Toggle Button Position

**Before:** `.btn-view-toggle { position: fixed; top: 8px; right: 16px; }` — placed the button at 8px from the top of the viewport, inside the 52px header, causing overlap.

**After:** `.btn-view-toggle { position: fixed; top: calc(52px + var(--space-sm, 8px)); right: 16px; }` — positions the button 60px from top (8px below the 52px header). Uses CSS custom property `var(--space-sm, 8px)` with fallback per UI-SPEC guidance.

## Deviations from Plan

### Bug 2 — No Code Change Needed

**Task 1** plan said to verify and potentially fix the script button. On inspection, the existing code was already correct:
- `initSkript()` at line 858: `const hasAny = skriptData.some(p=>p.items.length>0);` — correct
- `toggleBtn.classList.toggle('disabled', !hasAny)` — correct
- `app_routes.py` line 56-62: correctly reads `phasen` including `skript` arrays from JSON — correct

No fix was applied. Documented as-is.

### getUserMedia not present in app.js

The plan referenced `navigator.mediaDevices.getUserMedia` as the location to anchor the DSGVO banner fix. However, NERVE uses server-side PyAudio audio capture (in `services/deepgram_service.py`) — not browser `getUserMedia`. The Socket.IO `connect` event was used instead as the earliest client-side session hook. This achieves the same legal intent: user sees consent banner before audio processing begins.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 42131f3 | fix(02-02): move DSGVO banner to socket connect handler |
| Task 2 | f22c171 | fix(02-02): fix compact mode circles CSS and toggle button position |

## Known Stubs

None — all 4 bugs resolved with functional code changes.

## Self-Check: PASSED
