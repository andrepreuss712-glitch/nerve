---
phase: quick-260424-fo0
plan: "01"
subsystem: profile-editor
tags: [tabu, ux, frontend-only, sektion-15]
dependency_graph:
  requires: [260424-ekk]
  provides: [tabu-default-pairs-merge, tabu-placeholder-suggestion]
  affects: [static/profile_editor.js, templates/profile_editor.html]
tech_stack:
  added: []
  patterns: [dedupe-merge, html-placeholder-as-suggestion]
key_files:
  created: []
  modified:
    - static/profile_editor.js
    - templates/profile_editor.html
decisions:
  - "mergeDefaultPairs() is in-memory only — saveTabuToServer() is NOT called on seed-btn click; data persists only when user clicks main Save."
  - "Placeholder set as HTML attribute (not input value) — native browser behaviour hides it on user input, no value written until user types."
  - "Dedupe key is Begriff (case-insensitive exact match) only — Alternative value is never compared."
metrics:
  duration: "~5 min"
  completed: "2026-04-24"
  tasks: 2
  files: 2
---

# Quick Task 260424-fo0: Nachbesserung Standard-Paare (Sektion 15) Summary

**One-liner:** One-click seed of 13 default Tabu pairs with dedupe-merge and inline Vorschlag placeholder on matching rows.

## Outcome

After deploy, users opening the profile editor on Sektion 15 (Tabu-Begriffe & Alternativen) now have two UX improvements:

**Fix A — "+ Standard-Paare einfügen" button:** A new button appears next to the existing "+ Hinzufügen" button. Clicking it merges all 13 default pairs (mirrored from `services/profile_migration.py`) into the current in-memory list using a 3-way dedupe: rows with a matching Begriff and empty Alternative get the default filled in; rows with a user-supplied Alternative are left untouched; missing pairs are appended as new rows. A feedback message (e.g. "5 hinzugefügt, 3 ergänzt, 5 schon vollständig") appears for 6 seconds. No backend request is fired — data stays in-memory until the user clicks the main Save button.

**Fix B — Auto-Vorschlag placeholder:** Whenever a row is rendered (on initial load or via "+ Hinzufügen"), if the Begriff matches a default pair (case-insensitive) and the Alternative input is empty, the Alternative field shows a greyed placeholder `Vorschlag: <default>` (e.g. `Vorschlag: Investition`). The placeholder updates live as the user types in the Begriff field. It is a native HTML placeholder — no value is written until the user types.

## Files Changed

| File | Lines added | Lines removed | Notes |
|------|-------------|---------------|-------|
| `static/profile_editor.js` | +114 | -1 | TABU_DEFAULT_PAIRS constant, findDefaultAlternative(), mergeDefaultPairs(), applyPlaceholderSuggestion(), seed-btn wire-up |
| `templates/profile_editor.html` | +2 | 0 | #tabu-seed-btn button + #tabu-seed-feedback span |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Fix A | fd67cbf | fix(profile-editor): add '+ Standard-Paare einfügen' button to Sektion 15 with dedupe-merge (quick task 260424-fo0 Fix A) |
| Fix B | 5d6478c | fix(profile-editor): show 'Vorschlag: X' placeholder on Alternative when Begriff matches default pair (quick task 260424-fo0 Fix B) |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `static/profile_editor.js` — exists and contains TABU_DEFAULT_PAIRS, mergeDefaultPairs, findDefaultAlternative, applyPlaceholderSuggestion, Vorschlag
- `templates/profile_editor.html` — contains tabu-seed-btn, tabu-seed-feedback, Standard-Paare einfügen
- Commits fd67cbf and 5d6478c confirmed in git log
