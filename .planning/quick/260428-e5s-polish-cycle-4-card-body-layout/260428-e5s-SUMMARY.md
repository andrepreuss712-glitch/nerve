---
phase: quick-260428-e5s
plan: 01
subsystem: profile-editor
tags: [polish, css, ui, crud-cards]
dependency_graph:
  requires: []
  provides: [crud-card-visual-consistency, trash-in-header, phasen-sublabel]
  affects: [templates/profile_editor.html]
tech_stack:
  added: []
  patterns: [inline-style-block, vanilla-js-dom-builder]
key_files:
  created: []
  modified:
    - templates/profile_editor.html
decisions:
  - ".crud-body background: transparent — erbt #F8FAFC vom .crud-card, kein eigener Dark-Token"
  - "delBtn direkt in hd (nach chevron) statt body>actions — actions-div entfernt"
  - "label.fl fuer 'Gesprächsphasen' — konsistent zum Erlaubnisfrage/Pitch-Label-Pattern"
metrics:
  duration: "~5min"
  completed: "2026-04-28"
  tasks_completed: 2
  files_modified: 1
---

# Quick Task 260428-e5s: Polish-Cycle 4 Card-Body-Layout Summary

**One-liner:** Revertiert crud-body Dunkel-Hintergrund auf transparent, verschiebt Trash-Icon in Card-Header-Zeile, fuegt Gesprächsphasen-Sub-Label ein.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | CSS — .crud-body Background revertieren + Textarea anpassen | 451d11e | templates/profile_editor.html |
| 2 | CRUD-Card Layout — Trash in Header + Phasen Sub-Überschrift | 451d11e | templates/profile_editor.html |

## Changes Made

### Task 1 — CSS-Korrekturen

- `.crud-body { background: #161B22 }` → `background: transparent` (Cycle-3-Overreach behoben)
- `.crud-body padding: 0 14px 10px` → `padding: 12px 14px 14px` (konsistent mit .block-Cards)
- Doppeltes `display: none` / `display: flex` in der Regel entfernt — nur `display: flex` im Basis-Zustand
- `textarea min-height: 48px` → `min-height: 100px`
- `textarea font-size: 12px` → `13px`
- `textarea color: var(--page-text-secondary)` → `var(--page-text-color)`
- `textarea padding: 4px 6px` → `6px 8px`

### Task 2 — DOM-Struktur + HTML

- `renderItem()`: `delBtn` direkt in `hd` nach `chevron` angehängt — `actions`-div entfernt
- Header-Reihenfolge: `[nameInput] [chevron] [delBtn]` — Trash sichtbar ohne Aufklappen
- `delete`-Listener unverändert erhalten
- `<label class="fl">Gesprächsphasen ...` vor `.col-header` in ehemals sec-phasen eingefügt

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] templates/profile_editor.html modified (8 ins, 10 del)
- [x] Commit 451d11e exists
- [x] No #161B22 remaining in .crud-body
- [x] No duplicate display property in .crud-body
- [x] hd.appendChild order: nameInput → chevron → delBtn
- [x] actions-div removed from body
- [x] Gesprächsphasen label present before col-header

## Self-Check: PASSED
