---
phase: 02-product-fixes
plan: 01
subsystem: database
tags: [branding, migration, sqlite, naming]

# Dependency graph
requires: []
provides:
  - All Python source files use NERVE naming (no SalesNerve except migration SQL predicates)
  - config.py DATABASE_URL default points to nerve.db
  - database/db.py DATABASE_URL default points to nerve.db
  - app.py seed uses NERVE_DEMO_PROFILE_JSON, _seed_demo_profile, admin@nerve.local
  - routes/dashboard.py log regex uses nerve_log_ prefix
  - routes/logs_routes.py log validation regex uses nerve_log_ prefix
  - DB file rename migration (salesnerve.db -> nerve.db) in _migrate(), idempotent
  - billing_email data migration (andre@salesnerve.de -> admin@nerve.local) in _data_migrate()
  - .env.example updated to nerve.db
affects: [02-02, 02-03, 02-04, 02-05, 02-06, deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Migration guard pattern: os.path.exists(old) and not os.path.exists(new) before rename"
    - "Data migration: wrapped in try/except for silent failure on already-migrated DB"

key-files:
  created: []
  modified:
    - config.py
    - app.py
    - routes/dashboard.py
    - routes/logs_routes.py
    - database/db.py
    - .env.example

key-decisions:
  - "SalesNerve Alpha in migration SQL WHERE clause intentionally retained — it is the search predicate for legacy record rename, not a branding artifact"
  - "database/db.py had its own hardcoded salesnerve.db default separate from config.py — fixed as Rule 1 bug"

patterns-established:
  - "DB file migration: check old exists AND new does not exist before rename (idempotent)"
  - "Data migration SQL: WHERE old_value pattern, wrapped in try/except"

requirements-completed: [PROD-11]

# Metrics
duration: 15min
completed: 2026-03-30
---

# Phase 2 Plan 01: SalesNerve -> NERVE Rename Summary

**Eliminated all SalesNerve branding from Python source and config; added idempotent DB file rename and billing_email data migration for existing installs**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T14:30:00Z
- **Completed:** 2026-03-30T14:45:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Renamed `SALESNERVE_PROFILE_JSON` to `NERVE_DEMO_PROFILE_JSON` and `_seed_salesnerve_profile` to `_seed_demo_profile` in app.py
- Updated all seed email addresses from `andre@salesnerve.de` to `admin@nerve.local`
- Updated log filename regex patterns in dashboard.py and logs_routes.py to use `nerve_log_` prefix
- Added safe DB file rename migration (`salesnerve.db` -> `nerve.db`) guarded by existence checks
- Added data migration to update `billing_email` from old value to `admin@nerve.local`
- Updated `config.py`, `database/db.py`, and `.env.example` to reference `nerve.db`

## Task Commits

1. **Task 1: Rename SalesNerve references in Python source files** - `7f64b6a` (feat)
2. **Task 2: Add DB file rename migration and billing_email data migration** - `50ce3c9` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `config.py` - DATABASE_URL default changed to nerve.db
- `app.py` - Variable/function renames, seed email updates, DB rename migration, billing_email migration
- `routes/dashboard.py` - Log regex updated to nerve_log_ prefix
- `routes/logs_routes.py` - Log validation regex updated to nerve_log_ prefix
- `database/db.py` - Default DATABASE_URL corrected to nerve.db (Rule 1 auto-fix)
- `.env.example` - DATABASE_URL example updated to nerve.db

## Decisions Made

- `SalesNerve Alpha` retained in data migration SQL `WHERE` clause — it is the predicate to locate legacy records, not a branding artifact. Removing it would silently break the migration on existing installs.
- Seed password `SalesNerve2024!` intentionally preserved per D-15 (plan explicitly specifies do not touch).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hardcoded salesnerve.db default in database/db.py**
- **Found during:** Task 1 (grep verification after source renames)
- **Issue:** `database/db.py` had its own `os.environ.get('DATABASE_URL', 'sqlite:///database/salesnerve.db')` separate from `config.py`. Plan only specified updating `config.py`, but `db.py` would still reference the old name if `DATABASE_URL` env var was not set.
- **Fix:** Updated `database/db.py` line 6 default to `sqlite:///database/nerve.db`
- **Files modified:** `database/db.py`
- **Verification:** `grep "salesnerve" database/db.py` returns empty
- **Committed in:** `7f64b6a` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary for correctness — without this fix, fresh installs without DATABASE_URL env var would still create salesnerve.db via db.py. No scope creep.

## Issues Encountered

- One remaining `salesnerve` reference in `app.py` migration SQL (`WHERE name='SalesNerve Alpha'` and `WHERE billing_email='andre@salesnerve.de'`) is correct and intentional — these are legacy values used as search predicates in data migrations. Removing them would prevent existing installs from auto-migrating.

## Known Stubs

None — all renames are complete. Log regex change (salesnerve_log_ -> nerve_log_) means existing log files named `salesnerve_log_*` will no longer match the parse/download patterns. This is intentional per the rebranding — existing log files can be manually renamed if needed.

## Next Phase Readiness

- Branding baseline is clean; Plans 02-06 can proceed without SalesNerve naming conflicts
- Log files on disk still named `salesnerve_log_*` will be invisible to dashboard/download — acceptable trade-off per rebranding intent

---
*Phase: 02-product-fixes*
*Completed: 2026-03-30*
