---
phase: 260428-c2x
plan: 01
subsystem: profile-editor
tags: [polish, css, ui, buttons, modal]
dependency_graph:
  requires: [08.19.2-04]
  provides: [POLISH-C2X-A, POLISH-C2X-B, POLISH-C2X-C]
  affects: [templates/profile_editor.html, static/nerve.css, static/profile_editor.js]
tech_stack:
  added: [btn-primary, btn-destructive, btn-secondary, btn-trash CSS classes, confirmDelete modal]
  patterns: [IIFE-onclick-pattern for this-context safety, inline SVG trash icon]
key_files:
  modified:
    - templates/profile_editor.html
    - static/nerve.css
    - static/profile_editor.js
decisions:
  - "IIFE-Pattern (function(btn){...})(this) fuer alle inline-onclick btn-trash Buttons — sichert this-Kontext vor Arrow-Function-Verlust"
  - "confirmDelete() als globale Funktion (ausserhalb des bestehenden IIFE) — notwendig fuer onclick-Attribut-Zugriff im Template"
  - "innerHTML fuer Modal via Array.join statt Template-Literal — sicherer in Umgebungen ohne ES6-Erzwingung"
  - "faq-delete btn-trash ohne onclick — deleteFaq() wird per JS Event-Listener verdrahtet (bereits so im Code)"
metrics:
  duration: "~20min"
  completed: 2026-04-28
  tasks: 3
  files: 3
---

# Phase 260428-c2x Plan 01: Polish Cycle 2 Button-Konsolidierung Summary

**One-liner:** Header-Link entfernt, alle Add-Buttons auf Teal-Pille (btn-primary), alle Lösch-Buttons auf SVG-trash-Icon mit confirmDelete() Modal-Dialog statt browser-native confirm().

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| A | Header-Link entfernen | b40bdc3 | templates/profile_editor.html |
| B | Button-Konsolidierung CSS + Template | 9834b10 | static/nerve.css, templates/profile_editor.html |
| C | trash-icon + confirmDelete Modal | b57c0cf | static/profile_editor.js, static/nerve.css, templates/profile_editor.html |

## Changes Summary

### Task A: Header-Link entfernt
- `<a class="beispiel-link">Sieh dir ein ausgefülltes Beispiel an</a>` aus editor-topbar entfernt
- `openBeispiel()` JS-Funktion bleibt erhalten (noch durch Modal referenziert)

### Task B: Button-Konsolidierung
- `nerve.css`: `.btn-primary`, `.btn-destructive`, `.btn-secondary` als Convenience-Aliases ergänzt (referenzieren bestehende CSS-Token)
- `nerve.css`: `.wisdom-stub-btn` als deprecated kommentiert
- `profile_editor.html`: 14× `class="btn-add"` → `class="btn-primary"`
- `profile_editor.html`: `id="tabu-add-btn" class="n-btn-ghost"` → `class="btn-primary"`
- `profile_editor.html`: `class="wisdom-stub-btn" disabled` → `class="btn-primary" disabled`
- `profile_editor.html`: Inline CSS `.btn-add` / `.btn-rm` als deprecated kommentiert

### Task C: Lösch-Button-Konsolidierung
- `nerve.css`: `.btn-trash` CSS + `#confirm-delete-modal` CSS ergänzt
- `profile_editor.js`: `ensureConfirmModal()` IIFE injiziert Modal-DOM beim Laden
- `profile_editor.js`: `confirmDelete(callback, label)` als globale Funktion (ausserhalb IIFE)
- `profile_editor.js`: `deleteFaq()` von `confirm()` auf `confirmDelete()` umgestellt
- `profile_editor.html`: `confirm('Wirklich löschen?')` in renderItem() → `confirmDelete()`
- `profile_editor.html`: 9× `class="btn-rm"` → `class="btn-trash"` mit inline SVG (trash-2 Pfade)
  - Painpoint, Gesprächsphase, Einwand, Frage, Kaufsignal, No-Go, Wettbewerber, Übergang, FAQ-Löschen

## Deviations from Plan

None — plan executed exactly as written. IIFE-Pattern durchgängig angewendet wie in Task C spezifiziert.

## Known Stubs

None — alle Änderungen sind vollständig verdrahtet. `confirmDelete()` ist global verfügbar, alle Lösch-Stellen nutzen sie.

## Threat Flags

None — keine neuen Netzwerk-Endpunkte oder Auth-Pfade eingeführt. Modal-Label-Strings sind Template-hardcoded (kein User-Input in innerHTML), konsistent mit T-C2X-01 accept-Disposition.

## Self-Check

- [x] `templates/profile_editor.html` existiert und enthält keine `class="btn-rm"` mehr
- [x] `static/nerve.css` enthält `.btn-primary`, `.btn-destructive`, `.btn-secondary`, `.btn-trash`, `#confirm-delete-modal`
- [x] `static/profile_editor.js` enthält `function confirmDelete`
- [x] Commits b40bdc3, 9834b10, b57c0cf existieren

## Self-Check: PASSED
