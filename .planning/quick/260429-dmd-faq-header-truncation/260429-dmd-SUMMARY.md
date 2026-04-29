---
phase: 260429-dmd-faq-header-truncation
plan: 01
subsystem: profile-editor
tags: [polish, css, js, faq, truncation, tooltip]
key-files:
  modified:
    - static/nerve.css
    - static/profile_editor.js
decisions:
  - "Tooltip auf .faq-lbl statt .faq-hd — praezisere Hover-Zone, kein Tooltip beim Hovern ueber Buttons"
  - ".block-lbl global ungekuerzt — Painpoint/Einwand-Index-Labels sollen nicht truncaten; nur .faq-lbl und .block-lbl--truncate modifier kuerzen"
  - ".block-hd > .btn-trash/.acc-chevron/.faq-used-count explizit flex-shrink:0 statt pauschal .block-hd > * — .einwand-preview braucht flex:1"
metrics:
  completed: "2026-04-29"
  tasks: 3/3 (Task 3 = human-verify, APPROVED)
  files: 2
---

# Phase 260429-dmd Plan 01: FAQ Header Truncation Summary

**One-liner:** CSS-Ellipsis + nativer title-Tooltip auf .faq-lbl ersetzt JS-slice(0,40) im FAQ-Card-Header; Header-Buttons flex-shrink:0 geschuetzt.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CSS — Shared Truncation auf .block-lbl + Header-Layout-Pflege | 71782b0 | static/nerve.css |
| 2 | JS — slice(0,40) entfernen, vollen Text + title-Attribut setzen | bba802d | static/profile_editor.js |
| 3 | Human-Verify — FAQ-Header in Browser pruefen | — | APPROVED |

## Changes Made

### static/nerve.css
- Added `.block-lbl--truncate, .faq-lbl` rule: `flex:1 1 auto; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis`
- Added `.block-hd > .acc-chevron, .block-hd > .btn-trash, .block-hd > .faq-used-count { flex-shrink:0 }` to protect right-side buttons
- Global `.block-lbl` rule left unchanged (index labels "Painpoint 1", "Einwand 1" must not truncate)

### static/profile_editor.js
- `renderFaqRow`: Removed `faq.frage_muster.slice(0, 40)` — full text now set via `lbl.textContent = fullFrage`
- `renderFaqRow`: Added `lbl.title = fullFrage` for native browser hover tooltip on the text span
- `renderFaqRow`: Set `hd.title = ''` (tooltip moved from full header to text label only)
- `persistFaq`: Added live-update block — after validation, `.faq-lbl` textContent + title updated immediately on blur/change (no reload needed to see new text in collapsed header)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — CSS/JS-only polish fix, no new network endpoints or auth paths.

## Self-Check: PASSED

- static/nerve.css modified: FOUND
- static/profile_editor.js modified: FOUND
- Commit 71782b0 exists: FOUND
- Commit bba802d exists: FOUND
- `slice(0, 40)` no longer present in profile_editor.js: VERIFIED
- `text-overflow: ellipsis` present in nerve.css for .faq-lbl: VERIFIED
