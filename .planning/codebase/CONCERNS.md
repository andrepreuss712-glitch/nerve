# Codebase Concerns

**Analysis Date:** 2026-03-30

## Security Issues

**CORS Configuration - Wide Open:**
- Issue: SocketIO configured with `cors_allowed_origins="*"` in `app.py:25`
- Risk: Any domain can connect to WebSocket endpoints without restriction
- Files: `app.py` (line 25)
- Current mitigation: Flask session-based auth via `@login_required` decorator
- Recommendations:
  - Restrict CORS to specific origins: `cors_allowed_origins=["https://yourdomain.com"]`
  - Implement origin validation in SocketIO handlers
  - Add rate limiting to socket endpoints

**Secret Key Configuration:**
- Issue: Default SECRET_KEY fallback in `config.py:9` is `'dev-secret-change-me'`
- Risk: If SECRET_KEY env var not set in production, sessions become insecure
- Files: `config.py` (line 9)
- Current mitigation: Documented in code comment
- Recommendations:
  - Fail fast if SECRET_KEY is missing in production
  - Add startup validation that refuses to start with default key
  - Enforce minimum key length and complexity

**Environment Variables Validation:**
- Issue: Multiple API keys (DEEPGRAM_API_KEY, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY) have empty string defaults
- Risk: Silent failures or fallback to non-functional mode without alerting operators
- Files: `config.py` (lines 6-8)
- Recommendations:
  - Validate all critical API keys on startup
  - Raise exceptions for missing required credentials instead of empty defaults

## Tech Debt

**Silent Exception Handling - Widespread:**
- Issue: Multiple files catch exceptions and silently pass, swallowing errors
- Locations:
  - `app.py:83, 116, 165` - Database migration silently continues on failure
  - `services/claude_service.py:378` - Exception during behavioral tips ignored
  - `services/deepgram_service.py:137` - KeyboardInterrupt handling silently continues
  - `routes/dashboard.py:24, 58, 79, 204, 259, 338, 595` - Broad exception handling with pass statements
- Impact: Bugs become hidden, making debugging production issues nearly impossible
- Fix approach:
  - Add logging for all `except Exception` blocks
  - Use specific exception types instead of broad catches
  - Log at minimum ERROR or WARNING level with context

**Database Migration Pattern - Fragile:**
- Issue: Raw SQL migration logic in `app.py:38-118` with silent failures
- Risk: Column additions fail silently; incomplete schema evolution across environments
- Files: `app.py` (lines 38-118)
- Current state: Uses `except Exception: pass` pattern
- Safe modification:
  - Migrate to Alembic or SQLAlchemy migrations framework
  - Log each migration attempt and result
  - Validate schema consistency on startup

**Exception Handling in Auth Path:**
- Issue: `routes/auth.py:30` catches broad Exception in login_required decorator
- Risk: Real errors (network, database) treated same as intentional redirects
- Files: `routes/auth.py` (lines 29-34)
- Better approach: Catch specific exceptions (DBException, SessionException) separately

**Live Session State Management - Complex Threading:**
- Issue: Multiple threading locks in `services/live_session.py` with shared mutable state
- Risk: Race conditions, deadlocks, or stale state if lock ordering inconsistent
- Files: `services/live_session.py` (16 separate lock objects, lines 16-159)
- Fragile areas:
  - `gegenargument_log` updated from multiple threads without clear ownership
  - `conversation_log` appended from both claude_service and deepgram_service
  - `state` dict modified in multiple places with version tracking
- Test coverage: No unit tests visible for thread safety
- Safe modification: Document lock acquisition order, add assertion checks

**Model Attributes - Runtime Addition:**
- Issue: Database migration adds columns at runtime to existing models
- Risk: Model class definition in `database/models.py` doesn't match actual schema
- Files: `app.py:38-118` (migration), `database/models.py` (model definition)
- Impact: ORM queries may fail if code expects attributes that weren't migrated
- Fix approach:
  - Keep models.py and migrations in sync
  - Use proper Alembic migrations with version tracking
  - Validate schema on startup before any queries

**Unvalidated JSON Parsing:**
- Issue: JSON parsing in multiple routes with silent failures
- Locations:
  - `routes/app_routes.py:60` - `_json.loads()` with bare `except Exception: pass`
  - `services/live_session.py` - JSON profile data parsed without validation
- Risk: Corrupted profile data silently becomes empty dicts
- Files: `routes/app_routes.py:58-68`, `services/live_session.py:97-99`
- Fix: Add schema validation using pydantic or jsonschema

## Performance Bottlenecks

**Polling API Routes for Real-Time Data:**
- Issue: `/api/ergebnis` and `/api/status` polled frequently (filtered in logs at `app.py:12-18`)
- Problem: Client polls every ~1-2 seconds for analysis results; inefficient
- Files: `app.py:12-18` (logging filter suppressing poll logs), `routes/app_routes.py:77-93` (api_ergebnis)
- Current state: Poll filtering added to suppress log spam, symptom of polling problem
- Scaling issue: Each poll is a full database + state access, scales poorly with users
- Improvement path:
  - Use WebSocket for real-time updates instead of polling
  - Broadcast results to specific clients via SocketIO
  - Reduces server load and improves responsiveness

**Synchronous Claude API Calls - Blocking:**
- Issue: `services/claude_service.py:201-213` makes blocking calls to Claude API
- Problem: Each analysis call blocks the thread while waiting for response (>2-3 seconds typical)
- Files: `services/claude_service.py:201-213` (analysiere_mit_claude), line 224 (analysiere_coaching)
- Current state: Both Haiku (fast) and Sonnet (slower) calls run in separate threads but still block
- Scaling limit: Can process max 1-2 concurrent live sessions per server
- Improvement:
  - Pre-fetch or cache common responses
  - Implement response timeout/fallback for slow API
  - Use async HTTP client instead of synchronous requests

**File System Logging - Unbounded Growth:**
- Issue: Log files written to disk with no rotation or cleanup policy
- Problem: `LOG_DIR` in `services/live_session.py:12` writes conversationlogs with no size limits
- Files: `services/live_session.py:12`, `routes/dashboard.py:62-80` (log listing)
- Current capacity: No visible rotation strategy; logs accumulate indefinitely
- Scaling path:
  - Implement log rotation (hourly, daily, or by size)
  - Add automatic cleanup of logs older than N days
  - Move to database storage instead of file system

**JSON String Parsing in DB Columns:**
- Issue: Complex objects stored as JSON text in `profiles.daten`, `nudge_dismissed` columns
- Problem: Parsed with `json.loads()` multiple times per request
- Files: `database/models.py:98` (Profile.daten), `routes/app_routes.py:60, 66`
- Impact: Same JSON reparsed in every route that touches profile
- Improvement: Cache parsed JSON in session, or normalize schema to proper columns

## Known Bugs & Issues

**Active Profile Not Loaded on Session Resume:**
- Issue: User's active profile lost if browser tab closed/reopened
- Symptoms: Returns to default profile instead of last selected
- Files: `routes/app_routes.py:46-52` (checks session and fallback to user.active_profile_id)
- Workaround: User must manually select profile again
- Reproduction: 1) Select profile, 2) Close browser tab, 3) Reopen → profile reset

**Migration Silent Failures - Schema Divergence:**
- Issue: `app.py:38-118` migrations fail silently on constraint violations or schema issues
- Symptoms: Some instances have incomplete schema, queries fail unpredictably
- Files: `app.py:78-116`
- Trigger: Multiple database instances or manual schema modifications
- Workaround: None; requires manual database repair

**Fair-Use Limit Soft, Not Enforced:**
- Issue: `routes/app_routes.py:34-37` warns but doesn't block when limit reached
- Symptoms: User can exceed minuten_limit despite fair-use warning
- Design decision: "Fair-Use soft-limit check (never hard-block)" per comment
- Risk: Billing/usage tracking becomes inaccurate

**Zero Duration Sessions:**
- Issue: `routes/app_routes.py:353` comment indicates dauer_sek may be 0
- Problem: Duration calculation may not account for incomplete recordings
- Impact: Dashboard statistics and time-based metrics become unreliable
- Files: `routes/app_routes.py:350-355`

## Fragile Areas

**Claude Service - System Prompt Building:**
- Files: `services/claude_service.py:135-160` (system prompt), `163-192` (coaching prompt)
- Why fragile:
  - Prompts built dynamically by concatenating strings
  - Profile data from `live_session.get_active_profile()` may be incomplete
  - No validation that profile contains required fields
  - Changes to prompt structure could break JSON parsing
  - Embedding business rules in string concatenation (not DRY)
- Safe modification:
  - Extract prompt templates to separate files
  - Validate profile schema before building prompts
  - Use string templates instead of concatenation
  - Add unit tests for prompt formatting

**Speaker Identification & Diarization:**
- Files: `services/deepgram_service.py:10-22` (speaker detection), `162-179` (stabilization)
- Why fragile:
  - Speaker identification relies on Deepgram's diarize feature with debounce timing
  - `SPEAKER_DEBOUNCE_S = 3.0` in config hardcoded; brittle for different call types
  - Only two speakers supported (0=Berater, 1=Kunde); no support for conference calls
  - Speaker fallback logic `_log_last_sp` can persist incorrect speaker for entire call
- Test coverage: No visible unit tests for speaker stability
- Safe modification:
  - Add speaker validation/sanity checks
  - Log speaker changes with timestamps for debugging
  - Add config for debounce timing per org/profile

**Gegenargument Tracking & Effectiveness:**
- Files: `services/claude_service.py:274-296` (logging), `services/live_session.py:36-38` (state)
- Why fragile:
  - `kb_delta` calculation done post-hoc comparing before/after Kaufbereitschaft
  - Success marked as `kb_delta > 0` but may be noise or other factors
  - Option selection (gewaehlte_option) manually tracked by frontend, not validated
  - Learning loop in `_get_erfolgsquoten()` has `limit(50)` hardcoded; small sample size
- Test coverage: No visible tests for tracking accuracy
- Safe modification:
  - Validate kb_delta source (Claude or behavior)
  - Add explicit success/failure markers from conversation
  - Increase learning sample size or add recency weighting

**Profile Data as JSON String:**
- Files: `database/models.py:98` (Profile.daten as Text), `routes/app_routes.py:58-68`
- Why fragile:
  - Large JSON objects stored as string; no schema validation
  - Multiple places parse same JSON with different error handling
  - No versioning of profile schema; breaking changes possible
  - Merging changes from UI unclear (no update mechanism visible)
- Safe modification:
  - Define strict JSONSchema for profiles
  - Create dedicated Profile class/dataclass for type safety
  - Add migration path for schema versions

**Live Session Global State:**
- Files: `services/live_session.py:1-160` (all module-level globals)
- Why fragile:
  - 16+ module-level locks managing shared state
  - No clear ownership or initialization order
  - `reset_session()` called from routes but implementation not visible
  - Multiple threads writing to same lists/dicts without clear synchronization
  - Testing nearly impossible; requires thread coordination
- Safe modification:
  - Encapsulate session state in a class
  - Use a single lock per logical resource
  - Add docstrings for lock acquisition order
  - Create test fixtures that safely mock session state

## Test Coverage Gaps

**No Unit Tests for Core Logic:**
- What's not tested: Claude analysis (prompt generation, JSON parsing), speaker identification, Kaufbereitschaft calculations, gegenargument tracking
- Files: `services/claude_service.py`, `services/deepgram_service.py`, `services/live_session.py`
- Risk: Regressions in AI analysis or speech processing undetected
- Priority: High

**No Integration Tests for Session Flow:**
- What's not tested: Full end-to-end live session (connect → transcribe → analyze → coach), profile loading and switching, Fair-Use limits
- Files: All of `services/`, `routes/app_routes.py`
- Risk: Complex interactions between components break silently
- Priority: High

**No Tests for Concurrent Access:**
- What's not tested: Thread safety of live_session globals, concurrent gegenargument logging, speaker identification under load
- Files: `services/live_session.py`, `services/deepgram_service.py`
- Risk: Race conditions and data corruption in production
- Priority: High

**No Database Tests:**
- What's not tested: Migration correctness, schema consistency, Fair-Use limit enforcement
- Files: `app.py:38-118` (migrations), `routes/app_routes.py:20-41` (Fair-Use check)
- Risk: Silent schema divergence, billing logic failures
- Priority: Medium

**No Tests for Error Cases:**
- What's not tested: API failures (Deepgram down, Claude timeout), corrupted profile JSON, missing columns from incomplete migrations
- Files: All service files
- Risk: Unhandled exceptions crash live sessions
- Priority: Medium

## Scaling Limits

**Single Live Session Per User:**
- Current architecture: One session per browser tab via WebSocket + shared module state
- Limit: Cannot support multiple simultaneous sessions (e.g., trainer with student in same org)
- Scaling path: Refactor session management into database-backed registry instead of module globals

**File-Based Conversation Logs:**
- Current: Logs written to local disk in `logs/` directory
- Limit: Cannot scale to multiple servers; logs not shared; filesystem fragmentation
- Scaling path: Move to database table or S3-compatible storage

**No Database Connection Pooling Visible:**
- Current: Each route gets `get_session()` which creates new SessionLocal connection
- Limit: Database connection exhaustion under load
- Scaling path: Configure SQLAlchemy pool_size, pool_recycle, and connection pooling

**Claude API Rate Limits:**
- Current: Haiku calls (fast) and Sonnet calls (slow) both run in separate loops without backoff
- Limit: Could hit Anthropic rate limits during peak usage
- Scaling path: Add request queue, exponential backoff, fallback to cached responses

## Missing Critical Features

**Session Persistence & Recovery:**
- Problem: No visible mechanism to resume a crashed live session
- Blocks: Users cannot recover from network disconnection or server restart
- Implementation needed: Save session state to database, restore on reconnect

**Audit Logging:**
- Problem: No audit trail of who changed what (profiles, settings, billing)
- Blocks: Compliance requirements, debugging user issues
- Implementation needed: Log all changes to profiles, settings, user permissions

**API Rate Limiting:**
- Problem: No rate limiting on API endpoints; could be abused
- Blocks: Production deployment without DDoS protection
- Implementation needed: Flask-Limiter or equivalent

**Input Validation Layer:**
- Problem: No centralized input validation; each route validates independently
- Blocks: Inconsistent error handling, potential injection attacks
- Implementation needed: Pydantic request models or Flask-Inputs

---

*Concerns audit: 2026-03-30*
