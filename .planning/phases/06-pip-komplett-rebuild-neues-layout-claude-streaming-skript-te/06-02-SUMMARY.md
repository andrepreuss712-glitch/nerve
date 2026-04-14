---
phase: 06
plan: 02
subsystem: pip-live-window
tags: [pip, html, css, split-layout, teleprompter, consent, opacity-slider]
dependency_graph:
  requires: [06-01]
  provides: [pip-live-window-html-skeleton]
  affects: [static/pip-launcher.js]
tech_stack:
  added: []
  patterns: [css-custom-property-alpha, streaming-cursor-keyframe, flexbox-split-layout]
key_files:
  created: []
  modified:
    - templates/base.html
decisions:
  - "Kept tab CSS removal complete — .pip-tabs, .pip-tab, .pip-content, .pip-panel, .pip-tip-text all removed"
  - "pip-slot-body streaming cursor uses \\258C (block element) per UI-SPEC — CSS unicode escape"
  - "Beenden button set to display:none — pip-launcher.js Plan 03 will show it when live section activates"
metrics:
  duration: 8
  completed_date: 2026-04-14
  tasks_completed: 2
  files_modified: 1
---

# Phase 06 Plan 02: PiP Live Window HTML/CSS Rebuild Summary

Replaced the tab-based PiP live window with split layout HTML skeleton (55% KI zone / 45% teleprompter) and all associated CSS in base.html.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace #pip-live-window HTML structure | 966930c | templates/base.html |
| 2 | Add CSS for split layout, consent, teleprompter, opacity slider, streaming cursor | 966930c | templates/base.html |

## What Was Built

**HTML structure** (`#pip-live-window` inner content fully replaced):
- `#pip-header` — mini header with mode badge, timer, opacity slider (hidden until live)
- `#pip-section-consent` — full-height consent screen with `#pip-consent-text`, accept/reject buttons
- `#pip-section-live` — split layout wrapper (`pip-live-split`)
  - `#pip-ki-zone` — upper 55% KI area with `#pip-slot-0` / `#pip-slot-1` dual slots + `#nlp-ewb-row`
  - `.pip-zone-divider` — 1px separator
  - `#pip-teleprompter` — lower 45% scrollable teleprompter with empty state `.tp-empty`
- `#nlp-btn-beenden` — kept, set to `display:none` (JS activates during live)
- `#nlp-section-postcall` — kept unchanged

**CSS added** (new split layout system):
- `.pip-live-split` with `rgba(6,6,10,var(--pip-bg-alpha,1))` for opacity slider support
- `.pip-ki-zone`, `.pip-ki-slots`, `.pip-ki-slot` — dual slot flexbox layout
- `.pip-slot-body.pip-streaming::after` — block cursor `▌` with `pip-cursor-blink` keyframe
- `.pip-teleprompter` with WebKit scrollbar styling (4px thumb)
- `.tp-block`, `.tp-block-active` — teleprompter block inactive/active states
- `.tp-empty` — empty state text
- `.pip-consent-screen`, `.pip-consent-inner`, consent buttons — consent flow
- `.pip-opacity-label`, `#pip-opacity-slider` — opacity range input styling
- `.pip-zone-divider` — 1px rgba separator

**CSS removed** (old tab system):
- `.pip-tabs`, `.pip-tab`, `.pip-tab:hover`, `.pip-tab-active`, `.pip-tab-locked::after`
- `.pip-content`, `.pip-panel`, `.pip-tip-text`

**IDs preserved** (used by pip-launcher.js):
- `nlp-mode-badge`, `nlp-timer`, `nlp-ewb-row`, `nlp-btn-beenden`, `nlp-section-postcall`, `nlp-postcall-score`, `nlp-postcall-tags`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `#pip-slot-body-0` and `#pip-slot-body-1` contain placeholder text "Warte auf Gesprächsinhalt..." — intentional, Plan 03 (pip-launcher.js) wires streaming events to populate these
- `#pip-teleprompter` contains `.tp-empty` placeholder — intentional, Plan 03 renders teleprompter blocks dynamically from profile script data
- `#pip-consent-text` contains fallback consent text — intentional, Plan 03 replaces with `consent_text` from profile API response (`/api/skripte`)
- `#pip-section-consent`, `#pip-section-live` both `display:none` — intentional, Plan 03 JS manages visibility state machine

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary changes introduced. HTML/CSS only.

## Self-Check: PASSED

- `templates/base.html` exists and modified: FOUND
- Commit 966930c: FOUND
- `pip-section-live` in file: 1 occurrence (HTML) + CSS references
- `pip-tabs` in file: 0 occurrences (removed)
- `nlp-section-postcall` preserved: 1 occurrence
