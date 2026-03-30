---
phase: 02-product-fixes
plan: 06
subsystem: ui
tags: [wizard, profile, onboarding, flask, jinja2, vanilla-js]

# Dependency graph
requires:
  - phase: 02-01
    provides: NERVE design system CSS custom properties (base.html), profiles blueprint, dashboard route, User model with onboarding_done flag
provides:
  - 3-step guided profile creation wizard at /profiles/wizard (GET + POST)
  - Dashboard redirect for profileless users who finished onboarding
  - Profile created with firma, produkt, zielkunden, rolle, einwaende from wizard form
affects: [03-deployment, 04-payments]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wizard form with JS step navigation — show/hide divs, hidden inputs for selected values"
    - "CSS color-mix() for amber opacity variants without hardcoded rgba"
    - "Profile wizard creates profile and sets user.active_profile_id in one DB transaction"

key-files:
  created:
    - templates/profile_wizard.html
  modified:
    - routes/profiles.py
    - routes/dashboard.py

key-decisions:
  - "POST wizard_create replaced JSON-API handler with form-data handler — matches HTML form submission pattern in rest of codebase"
  - "Wizard redirect placed before expensive stats queries in dashboard route to minimize overhead for new users"
  - "10 DACH B2B industries used (Software/IT, Maschinenbau, Beratung, Finanzen/Versicherung, Medizintechnik, Logistik, Energie, Telekommunikation, Handel, Immobilien)"

patterns-established:
  - "profile_wizard.html: CSS custom properties only — no hardcoded hex/rgba; color-mix() for opacity variants"
  - "Wizard nav: show/hide steps with JS, hidden inputs for card-selection state, form submit on step 3"

requirements-completed: [PROD-09]

# Metrics
duration: 18min
completed: 2026-03-30
---

# Phase 02 Plan 06: Profile Wizard Summary

**3-step guided profile wizard at /profiles/wizard — industry cards, product info, 10 DACH B2B objection chips — creates Profile and redirects profileless users from dashboard**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-30T17:00:00Z
- **Completed:** 2026-03-30T17:18:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- GET /profiles/wizard renders 3-step wizard with progress dots, 10 industry cards, product info inputs, and 10 DACH B2B objection chips
- POST /profiles/wizard creates Profile with daten JSON (firma, produkt, zielkunden, rolle, einwaende), sets user.active_profile_id, flashes success, redirects to dashboard
- Dashboard route redirects users with onboarding_done=True and 0 profiles to /profiles/wizard, placed before all expensive queries

## Task Commits

Each task was committed atomically:

1. **Task 1: Create profile wizard route (GET + POST) and template** - `4616b00` (feat)
2. **Task 2: Add wizard trigger redirect in dashboard route** - `0069abd` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `routes/profiles.py` - Added GET wizard_page handler; replaced JSON wizard_create with form-data handler that creates Profile and sets active_profile_id
- `templates/profile_wizard.html` - 3-step wizard template extending base.html; CSS custom properties only; 10 industry cards; 10 objection chips; JS navigation
- `routes/dashboard.py` - Added profile_count check early in index(); redirects to wizard when count==0 and onboarding_done is True

## Decisions Made
- POST handler converted from JSON-API to form-data approach to match the rest of the codebase's HTML form pattern and avoid requiring JS fetch for form submission
- Profile name defaults to firma field value (or "Mein Profil" if blank) — gives meaningful name without additional required field
- Wizard redirect check placed as first action inside index() after user load, before streak update and all stats queries — minimizes overhead for new users who will be immediately redirected

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Profile wizard complete — new users now get guided onboarding experience
- Dashboard redirect ensures no user lands on empty dashboard without a profile
- Ready for Phase 3 (deployment / infrastructure setup)

---
*Phase: 02-product-fixes*
*Completed: 2026-03-30*
