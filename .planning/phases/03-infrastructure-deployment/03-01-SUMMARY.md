---
phase: 03-infrastructure-deployment
plan: 01
subsystem: infra
tags: [flask, sqlalchemy, sqlite, cors, pyaudio, security, wal]

# Dependency graph
requires:
  - phase: 02-product-fixes
    provides: Hardened codebase pre-deployment baseline
provides:
  - requirements split (server vs dev) — pyaudio isolated to local only
  - CORS_ORIGIN config var — production domain locked in SocketIO
  - SECRET_KEY fail-fast — RuntimeError on insecure key in production
  - SQLite WAL mode — concurrent read/write under Flask-SocketIO threading
affects: [04-legal-payments, deployment scripts, VPS setup]

# Tech tracking
tech-stack:
  added: [requirements-dev.txt]
  patterns: [SQLAlchemy event listener for PRAGMA, env-var-based debug detection, fail-fast startup guard]

key-files:
  created: [requirements-dev.txt]
  modified: [requirements.txt, config.py, app.py, database/db.py]

key-decisions:
  - "SECRET_KEY check uses os.environ.get('FLASK_DEBUG') not app.debug — Flask app.debug is always False at module-load under gunicorn"
  - "WAL mode listener guarded with 'if sqlite in _DATABASE_URL' — safe for future PostgreSQL upgrade"
  - "CORS_ORIGIN reads env var first, then falls back to production domain (not wildcard) in non-debug mode"

patterns-established:
  - "Startup fail-fast: raise RuntimeError before serving any request if critical config is insecure"
  - "SQLAlchemy event listener pattern for per-connection SQLite PRAGMAs"
  - "Dev-only dependencies isolated to requirements-dev.txt to prevent VPS install accidents"

requirements-completed: [INFRA-04, INFRA-05, LEGAL-04]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 03 Plan 01: Production Hardening Summary

**PyAudio isolated to dev requirements, CORS locked to nerve.app in production, SECRET_KEY fail-fast guard, and SQLite WAL mode via SQLAlchemy event listener — four silent production failures prevented**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-31T08:38:12Z
- **Completed:** 2026-03-31T08:39:41Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- requirements.txt now server-safe: no pyaudio (no PortAudio system lib crash on VPS)
- requirements-dev.txt created for local dev with pyaudio
- CORS_ORIGIN added to config.py — defaults to `https://nerve.app` when FLASK_DEBUG not set
- SocketIO init in app.py uses CORS_ORIGIN variable instead of hardcoded `"*"`
- SECRET_KEY fail-fast: app raises RuntimeError at startup if default key is used in production
- SQLite WAL mode activated on every DB connection via event listener (concurrent threading safe)

## Task Commits

Each task was committed atomically:

1. **Task 1: Split requirements.txt — remove pyaudio, create requirements-dev.txt** - `f5b4eac` (chore)
2. **Task 2: Add CORS_ORIGIN to config.py and harden app.py** - `36519cb` (feat)
3. **Task 3: Enable SQLite WAL mode in database/db.py** - `1c70702` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `requirements.txt` - Removed pyaudio>=0.2.14; server-only dependencies remain
- `requirements-dev.txt` - Created; pyaudio>=0.2.14 for local dev only
- `config.py` - Added CORS_ORIGIN with env-var override and production default
- `app.py` - Added import os, CORS_ORIGIN import, SECRET_KEY fail-fast RuntimeError, CORS locked on SocketIO init
- `database/db.py` - Added `event` import, WAL mode listener guarded by SQLite detection

## Decisions Made

- SECRET_KEY check uses `os.environ.get('FLASK_DEBUG')` not `app.debug` — `app.debug` is always False at module-load time under gunicorn (the `if __name__ == '__main__'` block never runs)
- WAL listener wrapped in `if 'sqlite' in _DATABASE_URL` guard — prevents ProgrammingError if DATABASE_URL is switched to PostgreSQL in future
- CORS_ORIGIN checks env var first, allowing per-environment override, defaults to `'https://nerve.app'` in production

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed `import os` placement in app.py**
- **Found during:** Task 2 (app.py changes)
- **Issue:** When adding `import os` alongside the config import line, the new import was placed after flask/socketio imports instead of with other stdlib imports
- **Fix:** Moved `import os` to the stdlib import block at the top (alphabetical order with json, logging, threading)
- **Files modified:** app.py
- **Verification:** Import order is correct PEP 8 style, no duplicate imports
- **Committed in:** 36519cb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 import order fix)
**Impact on plan:** Minor cosmetic fix. No scope creep. All plan requirements delivered exactly as specified.

## Issues Encountered

None — all four code hardening changes applied cleanly.

## User Setup Required

None - no external service configuration required for this plan. However, before deploying to VPS:
- Set `SECRET_KEY` env var (any secure random string)
- Optionally set `CORS_ORIGIN` to override the `https://nerve.app` default
- Install deps on VPS using `pip install -r requirements.txt` (NOT requirements-dev.txt)

## Next Phase Readiness

- Codebase is now safe to deploy to Hetzner VPS: no pyaudio crash, no wildcard CORS, no guessable secret key, no SQLite lock contention
- Phase 03 Plan 02 (Gunicorn/systemd config) and Plan 03 (Nginx/SSL) can proceed immediately

---
*Phase: 03-infrastructure-deployment*
*Completed: 2026-03-31*
