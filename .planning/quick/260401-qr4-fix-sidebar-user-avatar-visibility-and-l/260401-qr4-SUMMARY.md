---
phase: quick
plan: 260401-qr4
subsystem: frontend/sidebar
tags: [sidebar, css, flex, overflow, user-avatar, theme]
dependency_graph:
  requires: []
  provides: [sidebar-user-block-always-visible, nav-items-scrollable-independently]
  affects: [templates/base.html, static/nerve.css]
tech_stack:
  added: []
  patterns: [flex-1-inner-div-pin-pattern]
key_files:
  created: []
  modified:
    - templates/base.html
    - static/nerve.css
decisions:
  - ".g-sidebar-inner introduced as flex:1 scrollable container — sidebar-user-block stays as direct flex sibling of g-sidebar, pinned by its existing margin-top:auto"
  - "Scrollbar rules moved from .g-sidebar to .g-sidebar-inner — scrollbar only appears on nav items, not the full sidebar shell"
metrics:
  duration: "< 2 minutes"
  completed: "2026-04-01"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260401-qr4: Fix Sidebar User Avatar Visibility and Layout

**One-liner:** Introduced `.g-sidebar-inner` flex wrapper so nav items scroll independently while `sidebar-user-block` stays pinned at sidebar bottom via flex sibling layout.

## What Was Done

The sidebar user avatar/dropdown block was being pushed out of view when nav items overflowed, because `overflow-y:auto` was on `.g-sidebar` itself — meaning the entire sidebar (including the user block) scrolled as one unit.

**Fix applied in two files:**

**templates/base.html** — All nav item links and their separators (Dashboard through Changelog) are now wrapped in `<div class="g-sidebar-inner">`. The `sidebar-user-block` div remains a direct child of `<nav class="g-sidebar">`, outside the inner wrapper.

**static/nerve.css** — `.g-sidebar` rule had `overflow-y:auto` and `gap:2px` removed. New `.g-sidebar-inner` rule added with `flex:1; overflow-y:auto; min-height:0; display:flex; flex-direction:column; gap:2px`. Scrollbar rules (webkit) moved to `.g-sidebar-inner` as well. The `.sidebar-user-block` already had `margin-top:auto` and `flex-shrink:0` — no changes needed there.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wrap nav items in .g-sidebar-inner in base.html | a27f54f | templates/base.html |
| 2 | Move overflow-y:auto from .g-sidebar to .g-sidebar-inner | bc76e07 | static/nerve.css |
| 3 | Checkpoint: human-verify | auto-approved (AUTO_CFG=true) | — |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both files fully wired. The settings.html Design/Theme card was already present and wired to `toggleTheme()` defined in base.html; no changes required.

## Self-Check: PASSED
