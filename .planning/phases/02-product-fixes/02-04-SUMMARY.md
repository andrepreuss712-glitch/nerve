---
phase: 02-product-fixes
plan: 04
subsystem: database
tags: [pricing, fair-use, flat-rate, organisation, migration, roi]

# Dependency graph
requires:
  - phase: 02-01
    provides: database migration patterns, Organisation model, app.py structure

provides:
  - PLANS dict with exactly 3 flat-rate plans: starter (49 EUR), pro (59 EUR), business (69 EUR)
  - Organisation model extended with fair-use tracking columns (live_minutes_used, training_sessions_used, fair_use_reset_month)
  - Org-level monthly fair-use reset at live session start and training start
  - Live minutes increment at session end (api_beenden)
  - Training sessions increment at training start
  - ROI tracker using correct flat-rate plan_preis (fallback 49, not 39)
  - Backend pricing model ready for Phase 4 (Stripe/plan-selection)

affects: [04-payments, routes/dashboard.py, routes/settings.py, routes/app_routes.py, routes/training.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Org-level fair-use counters reset monthly via fair_use_reset_month string comparison ('%Y-%m')"
    - "Soft-warn at 80% of limit, never hard-block (80% live minutes, 80% training sessions)"
    - "Canonical PLANS dict in app.py; config.py mirrors it identically for dual-import sites"

key-files:
  created: []
  modified:
    - app.py
    - config.py
    - database/models.py
    - routes/auth.py
    - routes/settings.py
    - routes/dashboard.py
    - routes/waitlist.py
    - routes/app_routes.py
    - routes/training.py

key-decisions:
  - "PLANS dict has exactly 3 flat-rate plans: starter/pro/business at 49/59/69 EUR — all legacy keys removed"
  - "All plans have max_users=1 (individual flat-rate); team/multi-user pricing deferred to Phase 4"
  - "Org-level fair-use counters are separate from user-level counters (user.minuten_used vs org.live_minutes_used)"
  - "Fair-use is soft-warn only, never hard-block — prints warning at 80% of limit"

patterns-established:
  - "Fair-use reset pattern: compare fair_use_reset_month string to today_month = dt.now().strftime('%Y-%m')"
  - "Plan fallback: always use 'starter' not 'solo'/'bundle' — legacy plan keys are gone"

requirements-completed: [PROD-01, PROD-02]

# Metrics
duration: 18min
completed: 2026-03-30
---

# Phase 02 Plan 04: Flat-Rate Pricing and Fair-Use Tracking Summary

**PLANS dict rewritten to 3 flat-rate tiers (49/59/69 EUR), Organisation model extended with org-level fair-use counters that reset monthly, ROI tracker updated to use correct flat-rate pricing**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-30T17:00:00Z
- **Completed:** 2026-03-30T17:18:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Replaced old multi-key PLANS dict (trial/solo/team/business/enterprise/coach/starter/bundle) with canonical 3-key flat-rate dict in both app.py and config.py
- Added 3 org-level fair-use tracking columns to Organisation model (live_minutes_used, training_sessions_used, fair_use_reset_month) with matching migrations
- Wired org-level monthly reset + live_minutes increment in app_routes.py, org-level training_sessions increment in training.py
- Fixed ROI _calculate_roi() fallback from 39 to 49 (starter price) and cleaned up all 'solo' fallback references to use 'starter'

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite PLANS dict and unify imports** - `101fd3c` (feat)
2. **Task 2: Fair-use columns, migration, reset logic, ROI fix** - `53dac78` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app.py` - PLANS dict rewritten to 3 flat-rate plans; migration extended with 3 fair-use columns; seed org uses plan_preis=49
- `config.py` - PLANS dict rewritten to match app.py exactly (same 3 plans)
- `database/models.py` - Organisation: plan_preis default 39→49; added live_minutes_used, training_sessions_used, fair_use_reset_month columns
- `routes/auth.py` - size_to_plan mapping updated to use only valid plan keys (removed 'team'/'enterprise' refs)
- `routes/settings.py` - 'solo' fallback replaced with 'starter'; plan_preis fallback 39→49
- `routes/dashboard.py` - 'solo' fallback replaced with 'starter'; plan_preis fallback 39→49; ROI fallback 39→49
- `routes/waitlist.py` - invite_from_waitlist uses plan='starter' with plan_preis=49 (removed 'bundle' plan ref)
- `routes/app_routes.py` - org-level fair-use monthly reset at /live route; org live_minutes_used increment in api_beenden
- `routes/training.py` - org-level monthly reset + training_sessions_used increment at training_start

## Decisions Made
- All 3 flat-rate plans have max_users=1 — the old multi-user per-seat pricing (team/enterprise) is removed; Phase 4 will wire team billing if needed
- Org-level counters (live_minutes_used, training_sessions_used) are tracked separately from existing user-level counters (user.minuten_used, user.trainings_voice_used) — both are retained for different purposes
- soft-warn at 80% (800 min / 40 sessions), never hard-block, consistent with PROJECT.md constraint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed auth.py size_to_plan mapping referencing removed plan keys**
- **Found during:** Task 1 (PLANS dict rewrite)
- **Issue:** api_register() used size_to_plan = {'1-5':'starter','6-15':'team','16-30':'business','30+':'enterprise'} — 'team' and 'enterprise' are removed from PLANS, causing KeyError on PLANS['team']['max_users']
- **Fix:** Updated mapping to {'1-5':'starter','6-15':'starter','16-30':'business','30+':'business'}
- **Files modified:** routes/auth.py
- **Verification:** All plan keys in mapping exist in new PLANS dict
- **Committed in:** 101fd3c (Task 1 commit)

**2. [Rule 1 - Bug] Fixed waitlist.py invite_from_waitlist using removed 'bundle' plan**
- **Found during:** Task 1 (PLANS dict rewrite)
- **Issue:** invite_from_waitlist hardcoded plan='bundle', max_users=5 — 'bundle' no longer exists in PLANS dict; also imported PLANS from config but never used it
- **Fix:** Changed to plan='starter', max_users=1, plan_preis=49; removed unused PLANS import
- **Files modified:** routes/waitlist.py
- **Verification:** plan key 'starter' exists in new PLANS; no unused import
- **Committed in:** 101fd3c (Task 1 commit)

**3. [Rule 1 - Bug] Fixed settings.py and dashboard.py fallback to removed 'solo' plan key**
- **Found during:** Task 1 (PLANS dict rewrite)
- **Issue:** Both files used PLANS.get('solo', {}) as fallback — 'solo' no longer exists, resulting in empty dict and missing plan_name/preis
- **Fix:** Changed fallback to PLANS.get('starter', {}); updated plan_preis fallback from 39 to 49
- **Files modified:** routes/settings.py, routes/dashboard.py
- **Verification:** 'starter' key exists in new PLANS with correct preis=49
- **Committed in:** 101fd3c (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 - bugs caused by removing legacy plan keys)
**Impact on plan:** All fixes required for correctness. Without them, several routes would raise KeyError or return wrong plan data. No scope creep.

## Issues Encountered
None — plan executed cleanly. All fixes were cascade corrections from the PLANS dict cleanup.

## Known Stubs
None — all new columns are wired to actual increment/reset logic. Fair-use counters will accumulate real data on first session use. The ROI widget reads real org.plan_preis from DB.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Backend pricing model complete: PLANS dict, Organisation fair-use columns, monthly reset, soft-warn logic all in place
- Phase 4 (Payments/Stripe) can read org.plan and org.plan_preis to determine billing amounts
- Phase 4 can read org.live_minutes_used and org.training_sessions_used for usage display in billing UI
- Plan-selection UI (where users switch between starter/pro/business) is scoped to Phase 4 (PAY-01, PAY-06)

---
*Phase: 02-product-fixes*
*Completed: 2026-03-30*
