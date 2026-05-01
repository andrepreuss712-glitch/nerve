# Codebase Concerns

**Analysis Date:** 2026-05-01

---

## Tech Debt

**app.py is a 2240-line god file:**
- Issue: App initialization, migration runner, SocketIO handlers, background thread startup, Flask-Admin setup, changelog seeding, and training scenario seeding all live in `app.py`. Startup side effects run at module import time.
- Files: `app.py` lines 123–860 (`_migrate()`), 1860–2013 (`_seed_demo_training_scenarios()`), 2017–2065 (`_seed_changelog()`), 2226–2232 (thread starts)
- Impact: Slow test startup (full migration runs on import), hard to isolate individual concerns, high cognitive load for any change near startup.
- Fix approach: Extract `_migrate()` into `database/migrations.py`, extract seeding into `database/seeds.py`, keep `app.py` under ~300 lines.

**Manual ALTER TABLE migration system instead of Alembic:**
- Issue: 50+ `ALTER TABLE ... ADD COLUMN` statements in `_migrate()` use catch-all `except: pass`. No rollback possible. No migration history.
- Files: `app.py` lines 123–860
- Impact: Silent failures if a column fails to add for non-duplicate reasons (e.g. disk full, schema corruption). No way to detect which migrations have run without querying the DB.
- Fix approach: Adopt Alembic post-launch. Acceptable to keep current approach until >5 paying customers.

**`services/claude_service.py` is 1571 lines with mixed responsibilities:**
- Issue: Contains `analyse_loop`, `coaching_loop`, EWB streaming, training scoring, post-call analysis, and phase classification in one file.
- Files: `services/claude_service.py`
- Impact: High blast radius for any change; two background threads cannot be unit-tested without starting the full threading machinery.
- Fix approach: Split into `services/live_analysis.py`, `services/coaching.py`, `services/postcall.py` in a quiet phase.

**Module-level mutable globals in `live_session.py` (partial fix in 08.19.4):**
- Issue: Per-SID state was added in Phase 08.19.4 (`_per_sid_profile`, `_per_sid_transcript`, `_per_sid_coaching_buffer`) but the old module-level globals (`conversation_log`, `transcript_buffer`, `coaching_buffer`) still exist and are still used by both background threads. Both code paths are active simultaneously.
- Files: `services/live_session.py` lines 39–556
- Impact: Concurrent sessions could cross-contaminate via the old globals if per-SID routing has a gap. The `is_paused` flag is still a single global boolean — pausing one user pauses all analysis for all sessions on the process.
- Fix approach: Complete the per-SID migration. Remove all module-level mutable state. Route every consumer through `_per_sid_*` lookups.

**`is_paused` is a single process-global, not per-session:**
- Issue: `services/live_session.py:40` — `is_paused = False`. The `deepgram_service.py` `on_message` handler checks `with ls.pause_lock: if ls.is_paused: return`.
- Files: `services/live_session.py:39–46`, `services/deepgram_service.py:44–46`
- Impact: If User A pauses their session, User B's transcription is also silently dropped.
- Fix approach: Move `is_paused` into `_session_state[sid]`, read it via `sid`-keyed lookup in `on_message`.

---

## Security Considerations

**Rate limiter uses in-memory storage — resets on restart:**
- Risk: `storage_uri="memory://"` in `services/rate_limiter.py:11`. A server restart resets all rate-limit counters.
- Files: `services/rate_limiter.py:8–13`
- Current mitigation: Comment notes future Redis upgrade. 1-worker gunicorn means restarts are rare.
- Recommendations: Switch to `storage_uri="redis://localhost:6379"`. Redis is already in the stack for nerve_rt.

**Waitlist admin protected only by session role check, not `@superadmin_required`:**
- Risk: `/waitlist/invite/<wid>` and `/waitlist/admin` check `flask_session.get('rolle') != 'owner'`. Any org owner who discovers the URL can access waitlist management and invite arbitrary users.
- Files: `routes/waitlist.py:96–100`, `routes/waitlist.py:138–141`
- Current mitigation: URL is not linked in UI. Security by obscurity.
- Recommendations: Add `@superadmin_required` (already defined in `services/auth_decorators.py`, used in `routes/admin_dashboard.py`).

**`delete_account` soft-deletes only — no data purge:**
- Risk: `/settings/delete_account` sets `aktiv=False` on users and org. Personal data (name, email, `schmerzpunkt`, conversation logs) remains in the database permanently. Conflicts with DSGVO Art. 17 (right to erasure).
- Files: `routes/settings.py:188–205`
- Current mitigation: None.
- Recommendations: Implement a post-deletion anonymization job that scrubs PII fields (name, email, `schmerzpunkt`, `persoenlich`) after a 30-day retention window, or hard-deletes immediately.

**500 error handler prints full Python traceback to stdout (contains variable values):**
- Risk: `app.py:2162–2181` — `print(tb_str)` on every unhandled exception. Tracebacks may contain user input values, profile data snippets, or API response fragments. stdout goes to systemd journal.
- Files: `app.py:2160–2181`
- Current mitigation: JSON response body to the client is sanitized. Traceback only in server logs.
- Recommendations: Replace `print(tb_str)` with `app.logger.error(tb_str)`. Add log rotation. Avoid logging request body content in tracebacks.

**Bleach allow-list for AI-generated markdown includes `<a href>` without domain restriction:**
- Risk: `app.py:98–106` — `<a href>` tags in PreCall briefing HTML are permitted with `protocols=['http', 'https', 'mailto']`. Prompt injection via Brave search results could produce redirect links.
- Files: `app.py:97–107`
- Current mitigation: bleach blocks `javascript:` protocol. HTML tags not on the allowlist are stripped.
- Recommendations: Remove `a` from `_ALLOWED_TAGS` for AI-generated briefing content, or add `rel="noopener noreferrer"` enforcement.

**Superadmin role seeded at login time via env var comparison:**
- Risk: `auth.py:124–128` — on every login, `SUPERADMIN_EMAIL` is compared to the logging-in user's email. If the env var is leaked (e.g. via a future `/api/debug` endpoint), the admin email is exposed.
- Files: `routes/auth.py:124–129`
- Current mitigation: The env var value is not logged. Low risk currently.
- Recommendations: Seed superadmin via a one-time CLI script (`flask shell`) rather than at login time.

---

## DSGVO / GDPR Gaps

**No data export endpoint (Art. 20 — data portability):**
- Issue: No user-facing "Export my data" function exists. Users have no way to download their conversation logs, profile data, or usage history.
- Files: Missing — no route in `routes/settings.py` or elsewhere.
- Impact: Non-compliant with DSGVO Art. 20. Required before public launch with paying customers.
- Fix approach: Add `/settings/export_data` POST that generates a JSON download of `ConversationLog`, `Profile`, and `User` records for the requesting user.

**Account deletion is soft-delete only (Art. 17 — right to erasure):**
- Issue: `aktiv=False` flag is not erasure. Personal fields remain in DB indefinitely.
- Files: `routes/settings.py:188–205`
- Impact: DSGVO Art. 17 violation for users who request deletion.
- Fix approach: Implement anonymization of PII fields (`vorname`, `nachname`, `email` → unique tombstone token, `schmerzpunkt`, `persoenlich` → NULL) on deletion request.

**`dsgvo_modus` org flag is not enforced in the AI analysis pipeline:**
- Issue: `Organisation.dsgvo_modus` can be toggled via `/settings/privacy` but there is no check of this flag in `analyse_loop` or `coaching_loop`. Transcripts are always sent to Claude regardless.
- Files: `database/models.py:22`, `routes/settings.py:119–133`, `services/claude_service.py` (missing check)
- Impact: The flag controls only UI behavior. Backend behavior is unchanged.
- Fix approach: In `analyse_loop`, read `dsgvo_modus` from org state before sending transcript to Claude. When false, skip coaching analysis (or anonymize speaker labels).

**PreCall briefing cache is process-global — shared across all users:**
- Issue: `_briefing_cache` in `services/precall_service.py:22` is a module-level dict keyed by `(firmenname, profile_id)`. If two users from different orgs research the same company with the same profile_id (unlikely but possible), they share cached briefing data.
- Files: `services/precall_service.py:22–24`, `services/precall_service.py:172–196`
- Current mitigation: Cache key includes `profile_id`. Different orgs with different profiles are isolated.
- Recommendations: Add `org_id` to the cache key: `f"{firmenname.lower()}_{org_id}_{profile_id}"`.

**No consent timestamp stored for live session recording:**
- Issue: The headset/consent modal is shown before live sessions but the timestamp of user consent acceptance is not persisted to the DB.
- Files: `services/live_session.py`, `database/models.py`
- Impact: No audit trail for consent. In a dispute, there is no record that the user accepted the consent terms before the session started.
- Fix approach: Add `consent_accepted_at` field to `ConversationLog` and set it when the session starts.

---

## Performance Bottlenecks

**Two daemon threads (`analyse_loop`, `coaching_loop`) permanently consume 2 of 4 gthreads:**
- Issue: Both loops are started at app startup (`app.py:2231–2232`) and block on `threading.Event.wait()`. With `--threads 4`, only 2 threads remain for HTTP request handling.
- Files: `app.py:2231–2232`, `services/claude_service.py`
- Impact: During a live session, HTTP requests (PreCall research, PostCall save, dashboard loads) compete with only 2 available threads.
- Fix approach: Migrate live sessions to `nerve_rt/` (FastAPI + asyncio). Flask handles only HTTP/admin. This was the stated goal of Phase 04.8.1 but nerve_rt is not yet the active code path.

**PreCall Brave Search + Claude is synchronous and blocks the request thread:**
- Issue: `services/precall_service.py:203` — `_brave_search()` makes a synchronous `requests.get()` with 5s timeout, then `_generiere_briefing()` makes a synchronous Claude call. Both happen in the Flask request thread.
- Files: `services/precall_service.py:203–228`, `routes/app_routes.py:945–993`
- Impact: 4 simultaneous PreCall requests can freeze all HTTP handling for 10+ seconds.
- Fix approach: Move to background task pattern (SocketIO `start_background_task`), return a job ID, poll for completion. This is how EWB streaming already works.

**N+1 query risk in `routes/coach.py`:**
- Issue: Coach dashboard loads users, profiles, and logs in separate queries per org without joins.
- Files: `routes/coach.py:27–76`
- Impact: Degrades linearly with number of coached orgs. At 10 orgs: 30+ queries per page load.
- Fix approach: Use `joinedload()` or `subqueryload()` in SQLAlchemy.

---

## Fragile Areas

**`_migrate()` runs synchronously at every app startup with all errors silenced:**
- Files: `app.py:120` (`init_db` + `_migrate()` called at module level)
- Why fragile: If migration fails midway (disk full at column 30 of 60), the app starts with partial schema. The next request that touches the missing column gets a cryptic SQLite error with no link to the failed migration step.
- Safe modification: Always add new columns at the END of the migration list. Never remove existing migration blocks (idempotency depends on them).
- Test coverage: No test verifies schema completeness after `_migrate()`.

**`nerve_rt/` (FastAPI) and Flask coexist as separate processes with unclear active-path ownership:**
- Files: `nerve_rt/main.py`, `deploy/nerve-rt.service`, `nerve_rt/redis_bridge.py`
- Why fragile: It is unclear from code inspection whether `nerve_rt` is live in production or exists as a future replacement. Both `deploy/nerve.service` (Flask+threads) and `deploy/nerve-rt.service` (FastAPI+asyncio) exist. The Redis bridge has no circuit-breaker.
- Safe modification: Before touching any WebSocket session handling, confirm which service is active on the production VPS (`systemctl status nerve nerve-rt`).
- Test coverage: No integration test covers the Flask ↔ Redis ↔ nerve_rt round trip.

**JSON stored in `Profile.daten` column — not validated at read time in service layer:**
- Files: `database/models.py` (`Profile.daten` TEXT column), `services/prompt_pipeline.py`, `services/ewb_pipeline.py`, `services/coaching_service.py`
- Why fragile: `ProfileSchema` validation is enforced at write time in `routes/profiles.py` but not when services read `daten` and call `.get()` directly. A corrupted or legacy-schema profile dict causes silent key misses in prompt assembly.
- Safe modification: Always pass `daten` through `ProfileReadSchema(**json.loads(daten))` before consuming in service layer.

**`_load_training_prompt_template()` silently falls back to hardcoded strings on DB miss:**
- Files: `services/training_service.py:697–720`, `services/ewb_pipeline.py:74–95`
- Why fragile: DB miss prints a warning and returns an inline constant. No alerting. If a prompt version is accidentally deleted from `prompt_versions`, the system silently degrades.
- Test coverage: Tests verify the fallback path exists but not end-to-end degraded behavior.

---

## Scaling Limits

**SQLite as the production database:**
- Current capacity: Single file on Hetzner CX22. WAL mode enabled. Handles concurrent reads + 1 writer.
- Limit: Write throughput degrades under concurrent live sessions. Each `analyse_loop` cycle writes to `api_cost_log`; each session end writes multiple rows. With 10+ simultaneous live users, SQLite write lock contention causes latency spikes.
- Scaling path: Migrate to PostgreSQL. `DATABASE_URL` env var is parameterized. SQLAlchemy ORM is used consistently — migration is mostly schema-level.

**Single gunicorn worker + 4 threads:**
- Current capacity: 2 threads permanently used by background loops. 2 threads for HTTP.
- Limit: Any scenario with 2+ concurrent HTTP requests longer than 1s will queue. Rate limiting breaks if scaled to multiple workers.
- Scaling path: Move live sessions to `nerve_rt/` (asyncio). Flask then scales to multiple workers without threading state issues.

---

## Dependencies at Risk

**`bleach` is deprecated upstream (last release 2023):**
- Risk: Used for XSS sanitization of AI-generated markdown in `app.py:105`. No longer maintained.
- Impact: No security patches for new bypass techniques. Python version incompatibilities over time.
- Migration plan: Replace with `nh3` (`pip install nh3`). API is similar: `nh3.clean(html, tags=..., attributes=...)`.

**`flask-limiter` `storage_uri="memory://"` is non-HA:**
- Risk: Rate limit state is lost on every deploy, crash, or restart.
- Impact: Login and register endpoints unprotected during the restart window.
- Migration plan: `pip install flask-limiter[redis]`, set `storage_uri="redis://localhost:6379"`.

---

## Missing Critical Features

**No automated monthly fair-use reset:**
- Problem: `Organisation.fair_use_reset_month` and `User.usage_reset_date` exist but no scheduled job resets `live_minutes_used`, `minuten_used`, `trainings_voice_used`, `training_sessions_used` at month start.
- Blocks: Fair-use enforcement is meaningless without a reset. Users who exhaust their limit in month 1 are permanently soft-blocked.
- Files: `database/models.py:44–47`, `database/models.py:99–101` — no corresponding APScheduler job.

**No DSGVO data export (Art. 20):**
- Problem: No `/settings/export_data` endpoint. Users cannot download their own data.
- Blocks: Required for DSGVO compliance before billing goes live.

**No automated Stripe subscription status reconciliation:**
- Problem: `Organisation.subscription_status` is set by Stripe webhooks only. No periodic sync job to reconcile if a webhook is missed.
- Blocks: Missed `customer.subscription.deleted` = customer keeps access after cancellation.
- Files: `routes/payments.py:64–120`

**`favicon.ico` returns 204 (no content):**
- Problem: TODO comment in `app.py:2149` acknowledges this. Browsers show a blank tab icon.
- Fix: Add `static/favicon.ico` and serve via `send_from_directory`.

---

## Test Coverage Gaps

**`analyse_loop` and `coaching_loop` have no tests:**
- What's not tested: The two background threads that drive the entire live-session intelligence pipeline.
- Files: `services/claude_service.py`
- Risk: Any regression in loop logic (wrong state key, missed lock, wrong sid lookup) goes undetected until production.
- Priority: High

**Cross-session data isolation under concurrent load:**
- What's not tested: Two active sessions simultaneously using the per-SID state infrastructure. `tests/test_live_session_ghost_sid.py` covers ghost-SID cleanup but not concurrent active isolation.
- Files: `services/live_session.py:193–210`
- Risk: A bug in `_per_sid_profile` lookup could leak one user's profile data into another user's EWB call.
- Priority: High

**Stripe webhook idempotency is untested:**
- What's not tested: Duplicate Stripe event delivery. The `BillingEvent` dedup check is never exercised by a test.
- Files: `routes/payments.py:76–85`
- Risk: Double-activation or double-cancellation if a webhook fires twice.
- Priority: Medium

**`_migrate()` has no schema-completeness test:**
- What's not tested: Running `_migrate()` on a fresh DB and asserting all expected columns exist.
- Files: `app.py:123–860`
- Risk: A typo in a new migration block silently fails. Column is missing in production with no error at startup.
- Priority: Medium

---

*Concerns audit: 2026-05-01*
