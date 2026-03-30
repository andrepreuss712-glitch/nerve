---
phase: 02-product-fixes
plan: 05
subsystem: onboarding, profile-editor, dashboard
tags: [ux, onboarding, placeholders, dashboard-style, user-model]
dependency_graph:
  requires: [02-01, 02-04]
  provides: [generic-onboarding, dashboard-style-preference, profile-editor-generics]
  affects: [templates/onboarding.html, templates/profile_editor.html, templates/dashboard.html, database/models.py, routes/dashboard.py, routes/onboarding.py, app.py]
tech_stack:
  added: []
  patterns: [CSS custom properties, Jinja2 conditionals, SQLAlchemy migration pattern]
key_files:
  created: []
  modified:
    - templates/onboarding.html
    - templates/profile_editor.html
    - templates/dashboard.html
    - database/models.py
    - routes/onboarding.py
    - routes/dashboard.py
    - app.py
decisions:
  - dashboard_style hidden input in onboarding read via JS payload (not HTML form POST) — consistent with existing fetch-based onboarding submission pattern
metrics:
  duration: 12 minutes
  completed: 2026-03-30
  tasks_completed: 2
  files_modified: 7
---

# Phase 02 Plan 05: Onboarding & Profile Polish Summary

**One-liner:** Generic DACH placeholders, 3 product-value Beispiel-Boxen, and a Vollständig/Fokus Dashboard-Style selector with persistent User model preference.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Fix onboarding placeholders, add Beispiel-Boxen and Dashboard-Style selector | bb44b9a | templates/onboarding.html, database/models.py, app.py, routes/onboarding.py |
| 2 | Fix profile editor placeholders and wire dashboard_style rendering | c080230 | templates/profile_editor.html, routes/dashboard.py, templates/dashboard.html |

## What Was Built

### Task 1
- Changed `placeholder="Max"` to `placeholder="Vorname"` in onboarding step 2
- Added 3 Beispiel-Boxen to step 1 (Gegenargument, Kaufbereitschaft, Coaching-Tipp) with amber-themed CSS using only custom properties
- Added Dashboard-Style selector (Vollständig / Fokus) to step 2 with JS `selectDashboardStyle()` handler and hidden input
- Added `User.dashboard_style = Column(String(20), default='vollstaendig')` to models.py (coexists with `dashboard_stil`)
- Added `('dashboard_style', "VARCHAR(20) DEFAULT 'vollstaendig'")` migration in app.py `_migrate()`
- Route `routes/onboarding.py` saves `dashboard_style` from JSON payload to user record

### Task 2
- Added `placeholder="Ihr Unternehmen"` and `placeholder="Ihr Produkt oder Service"` fields to profile_editor.html Basis section
- `routes/dashboard.py` reads `dashboard_style = getattr(user, 'dashboard_style', 'vollstaendig')` and passes to template
- `templates/dashboard.html` wraps gamification/heatmap (`dash-grid`) and recent-logs (`bottom-grid`) in `{% if dashboard_style != 'fokus' %}` — ROI tracker always visible

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Note on implementation:** The dashboard_style value is transmitted via the existing `fetch('/onboarding/complete')` JSON payload pattern (not HTML form POST), consistent with how all other onboarding fields are submitted. The hidden `<input name="dashboard_style">` serves as the JS capture mechanism.

## Known Stubs

None — all data is wired end-to-end (model column, migration, save in route, read in dashboard route, conditional rendering in template).

## Self-Check: PASSED

- bb44b9a FOUND
- c080230 FOUND
- templates/onboarding.html: exists, contains Beispiel-Boxen and dashboard_style
- database/models.py: dashboard_style column present
- templates/dashboard.html: fokus conditional present
