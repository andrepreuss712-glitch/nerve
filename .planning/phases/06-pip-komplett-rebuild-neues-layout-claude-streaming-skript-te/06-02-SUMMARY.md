---
phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te
plan: 02
subsystem: frontend/pip
tags: [pip, html, css, split-layout, teleprompter, consent]
dependency_graph:
  requires: [06-01]
  provides: [pip-split-layout-dom, pip-consent-dom, pip-css-classes]
  affects: [static/app.js]
tech_stack:
  added: []
  patterns: [vanilla-css-in-template, pip-split-layout, dual-ki-slots]
key_files:
  created: []
  modified:
    - templates/app.html
decisions:
  - Removed duplicate .pip-consent-text CSS rule (old inline consent) to avoid cascade conflict with new Phase 06 consent screen rule
metrics:
  duration: "~5 min"
  completed: "2026-04-14T17:01:32Z"
  tasks: 1
  files: 1
---

# Phase 06 Plan 02: PiP Split-Layout HTML/CSS Rebuild — Summary

**One-liner:** Replaced PiP tab-based layout with 55/45 split (dual KI slots + teleprompter) and added consent screen section, all CSS per 06-UI-SPEC.md.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace PiP live section HTML with split layout + consent section | a6f254f | templates/app.html |

## What Was Built

- **CSS removed:** `.pip-tabs`, `.pip-tab`, `.pip-tab-active`, `.pip-tab-locked::after`, `.pip-content`, `.pip-panel` — all old tab system CSS gone
- **HTML removed:** All 4 tab buttons (`handlePipTabClick`), all 4 `pip-panel-*` divs, the inline `pip-active-hint` div
- **CSS added:** `.pip-ki-zone`, `.pip-ki-slots`, `.pip-ki-slot`, `.pip-slot-label`, `.pip-slot-body`, `.pip-slot-result`, `.pip-slot-typ-badge`, `.pip-zone-divider`, `.pip-teleprompter` (scrollbar included), `.tp-block`, `.tp-block-active`, `.tp-empty`, `.pip-opacity-label`, `#pip-opacity-slider` (with webkit thumb), `.pip-consent-heading`, `.pip-consent-subtext`, `.pip-consent-text`, `.pip-consent-buttons`, `.pip-consent-btn-granted`, `.pip-consent-btn-denied`
- **Streaming cursor:** `@keyframes pip-cursor-blink` + `.pip-slot-body.pip-streaming::after` with `#00D4AA` teal color
- **New HTML structure:** `#pip-section-live` now has header (with opacity slider), `#pip-ki-zone` with two `#pip-slot-0`/`#pip-slot-1`, `pip-ewb-row` inside KI zone, `.pip-zone-divider`, `#pip-teleprompter` with empty state, Beenden button, fallback warning
- **New section:** `#pip-section-consent` with `#pip-consent-text`, `#pip-consent-granted`, `#pip-consent-denied` buttons inserted before `#pip-section-postcall`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed duplicate .pip-consent-text CSS rule**
- **Found during:** Task 1 verification
- **Issue:** Old `.pip-consent-text { font-size: 12px; color: #e8ecf4; margin: 0 0 8px 0; }` remained from the old inline consent block (line ~654). The new Phase 06 rule at line 580 has correct 14px / line-height 1.6 / rgba color. The old rule would win due to CSS cascade order (later rule wins), overriding the new design.
- **Fix:** Removed the old `.pip-consent` + `.pip-consent-text` stale block. Left `.pip-consent-actions`, `.pip-btn-consent-yes`, `.pip-btn-consent-no` intact as they are used by the setup flow, not the new consent section.
- **Files modified:** templates/app.html
- **Commit:** a6f254f (same commit — caught before commit)

## Verification Results

```
pip-ki-zone count: 2 (CSS + HTML)
pip-section-consent count: 1 (HTML div)
pip-teleprompter count: 5 (CSS rules + HTML)
pip-opacity-slider count: 3 (CSS rules + HTML input)
pip-tab count: 0 (all tabs removed)
handlePipTabClick count: 0 (no old onclick handlers)
tp-block-active count: 1 (CSS rule)
pip-zone-divider count: 2 (CSS + HTML)
pip-streaming::after: 1 (CSS rule with cursor blink)
```

All acceptance criteria passed.

## Known Stubs

None — this plan is HTML/CSS structure only. JS wiring is Plan 03's responsibility. The slot bodies show "Warte auf Gespraechsinhalt..." as intentional placeholder text that Plan 03 JS will replace at runtime.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. HTML-only changes with onclick handlers calling existing trusted JS functions (T-06-06 accepted per plan threat model).

## Self-Check: PASSED

- `templates/app.html` modified: FOUND
- Commit a6f254f: FOUND (git rev-parse --short HEAD)
- `pip-ki-zone` in file: FOUND (count=2)
- `pip-section-consent` in file: FOUND (count=1)
- `pip-tab` in file: NOT FOUND (count=0) — correct, all removed
