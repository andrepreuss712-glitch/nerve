# Codebase Concerns

**Analysis Date:** 2026-04-24

## Executive Summary

The NERVE codebase exhibits **significant architectural drift** between the data model (rich profile fields) and execution (narrow EWB prompt integration). Approximately 50-60% of profile fields never reach the live Claude prompt. Additionally, multiple dead/orphaned code patterns have been identified, though most are intentionally kept for legacy support. Two high-priority performance bottlenecks exist in real-time analysis loops, and test coverage has gaps in critical integration paths.

---

## Dead Code & Orphaned Flows

### Python: `_build_system_prompt()` — Intentional Legacy Stub

**Location:** `services/claude_service.py:265`

**Status:** Defined but not called in live paths

**Investigation:**
- `_build_system_prompt()` exists (265 lines of comprehensive system prompt building)
- No invocation in active code paths: `analysiere_mit_claude()` and `analysiere_mit_claude_streaming()` use `build_ewb_prompt()` instead (Phase 08 refactor)
- Tests explicitly verify it is NOT called: `services/test_claude_service_phase08.py:46-59`
- **Intention documented:** Comments in `claude_service.py:10` note this is intentionally retained for "Legacy-Module" compatibility

**Severity:** **LOW**

**Action:** **KEEP** — Intentional stub for backward compatibility. Mark more clearly as deprecated in code comments.

---

### Python: Profile Data → EWB Prompt Gap (Architectural)

**Location:** 
- Profile definitions: `database/models.py:122-130` (Profile model)
- Active EWB prompt builder: `services/claude_service.py:647` (analysiere_mit_claude)
- System prompt construction: `services/prompt_pipeline.py` (build_ewb_prompt, build_profile_context)

**Issue:** Profile contains ~20+ data fields; EWB prompt reads only ~10

**Fields in Profile but NEVER read in live EWB prompt:**
- All `zielgruppe` fields (alter, berufsstatus, einkommen, hintergrund, vorwissen, entscheidungsverhalten)
- All `schmerzen.trigger` fields
- `faqs[]` array
- `wettbewerber` (competitors) — only read in coaching analysis, not EWB
- `uebergaenge` (transition phrases) — only in coaching
- `techniken_aktiv`, `techniken_verboten`
- `offene_fragen`
- Most `ki` substyle settings (stil, antwortlaenge, sensitivitaet, zusatz)
- `basis.name` (username)

**Audit Reference:** `.planning/audits/profil-prompt-integration-matrix.md` documents this at ~50-60% field disconnect. Particularly:
- Line 16-17: Old `_build_system_prompt` (called nowhere) had full context; Phase 08 replacement `build_ewb_prompt` strips 50% of data
- Line 52-62: Detailed breakdown of which fields reach which prompts

**Impact:** 
- Users build comprehensive profiles with rich context, but live EWB receives minimal context
- Profile field investment (UX effort, data modeling) yields diminishing returns
- AI recommendations (Haiku) lack rich customer context they could use

**Severity:** **HIGH** — Architectural misalignment, not a bug but a design gap

**Root Cause:** Phase 08 performance optimization (reduce Haiku token cost) cut corners on prompt building without refactoring profile schema

**Fix Approach:**
1. **Short term:** Document which profile fields are "live-relevant" vs. "analytics-only" in profile UI
2. **Long term:** Either (a) expand `build_ewb_prompt()` to re-include high-value fields, or (b) deprecate profile fields not used in live path (zielgruppe, wettbewerber, uebergaenge → move to coaching-only)
3. Establish field-to-prompt traceability matrix as part of architecture review

---

### PreCall Briefing Flow — Dead Data Path

**Location:**
- PreCall briefing storage: `services/deepgram_service.py:309` (stored in `ls.state['precall_briefing']`)
- Historical prompt usage: `services/claude_service.py:387` (old code, reads briefing into coaching prompt)
- EWB usage: `services/prompt_pipeline.py:149` (reference only, not in live EWB call)

**Issue:** PreCall briefing data flows into session state but **not into live EWB prompt**

**Investigation:**
- PreCall data generated via `/api/precall/research` route
- Stored in `ls.state['precall_briefing']` during session init (deepgram_service.py:309)
- **NOT injected into EWB system prompt** — `build_ewb_prompt()` does NOT read `ls.state['precall_briefing']`
- Audit confirms (line 17): "PreCall-Briefing fließt NICHT mehr in den EWB-Prompt"
- Only visible in UI context, never sent to Claude

**Severity:** **MEDIUM** — Wasted data preprocessing (research cost, token overhead in session)

**Action:** 
- **Option A (Recommended):** Remove PreCall briefing from session state OR add explicit flag that it's UI-only
- **Option B:** Re-integrate briefing into `build_ewb_prompt()` with token budget check (Phase 08.x feature)

---

### Manual EWB Button Path — Hardcoded Coach Prompt

**Location:** `services/claude_service.py:897` (streame_manual_ewb_variante)

**Issue:** Button clicks bypass profile context entirely

**Details:**
- When user clicks EWB button (Slot 1), `streame_manual_ewb_variante()` is called
- System prompt is **hardcoded** (line 899): `"Du bist ein erfahrener Sales-Coach..."`
- Only profile context sent: the single `gegenargument_1` text
- **No access to:** ton, usps, beweise, tabu_begriffe, eigene_formulierungen, etc.

**Audit Reference:** Line 70-79 of `profil-prompt-integration-matrix.md`

**Severity:** **MEDIUM** — Button-clicked responses lack profile personality/tone

**Fix Approach:**
1. Enhance `streame_manual_ewb_variante()` to inject `build_profile_context()` into system prompt
2. Add profile personality (ton, ansprache) to hardcoded coach prompt
3. Consider moving to template-based system prompt like EWB path uses

---

### ls.state Fields — Orphaned Writers/Readers

**Checked Fields:**

| Field | Writer | Reader | Status |
|-------|--------|--------|--------|
| `ewb_top2` | None found | Read in `app_routes.py:140` (legacy marker) | **ORPHANED WRITER** |
| `_phase_cycle_at_last_change` | `claude_service.py:1184` | `claude_service.py:1170` (same function) | Used (phase dedupe) |
| `last_einwand_typ` | `claude_service.py:1313` | `claude_service.py:1313` + `ki_logik.py` | Used (followup logic) |
| `active_learning_cards` | `live_session.py:214` | Read in templates/live.html | Used |
| `precall_briefing` | `deepgram_service.py:309` | **Never read** (see above) | **ORPHANED READER** |

**Severity:** **LOW** — `ewb_top2` is read as "legacy (may be None)" indicating intentional obsolescence

**Action:** 
- Remove `ewb_top2` write/read (Phase 04.8 leftover)
- Add comment to `precall_briefing` initialization: "UI-only; not sent to Claude (as of Phase 08)"

---

### JavaScript: Polling Suppress Pattern — Working As Designed

**Location:** `app.py:14-19` (_SuppressPolling filter)

**Status:** `/api/ergebnis` and `/api/status` polling endpoints exist; logs are intentionally suppressed

**Verification:** Grep for `_SuppressPolling` shows it's only defined and applied once (app.py), not read elsewhere. This is correct (logging filter is one-directional).

**Severity:** **NONE** — No issue found

---

## Architectural Gaps & Data Flow Issues

### Profile Data Segmentation Problem

**Files Affected:**
- `database/models.py:122-130` (Profile schema)
- `services/prompt_pipeline.py:180-250` (build_profile_context)
- All route files importing profiles

**Problem:** No clear demarcation between:
1. **Live EWB fields** (ton, produktbeschreibung, usps, beweise, tabu_begriffe)
2. **Coaching-only fields** (wettbewerber, uebergaenge, schmerzpunkte, zielgruppe)
3. **Analytics-only fields** (consent_text, branche enum for categorization)

**Result:** UI presents all fields as equally important; developers must hunt through prompt_pipeline.py to know which are actually used

**Severity:** **MEDIUM** — Confuses feature developers, increases technical debt

**Recommendation:** 
- Add `field_type` metadata to profile JSON schema (e.g., `"tier": "live"` vs `"tier": "coaching"`)
- Document in STRUCTURE.md where each field is consumed

---

## Performance Bottlenecks

### 1. Analyse Loop Blocking on Claude API

**Location:** `services/claude_service.py:1039-1340` (analyse_loop thread)

**Issue:** 
- Loop runs every `ANALYSE_INTERVALL` (4 seconds per config.py — Phase 06.3: raised from 2s to reduce 529-Risk)
- Calls `analysiere_mit_claude()` (non-streaming) which blocks on Claude API response
- If Claude latency exceeds 4s, loop skips ticks and EWB updates backlog

**Current Mitigation:** Non-streaming call; 4s interval halves API call volume vs. original 2s

**Severity:** **LOW** — Affects responsiveness under high API latency (>4s)

**Fix Path:**
1. Implement async/await for Claude calls (currently blocking threads)
2. Or: increase ANALYSE_INTERVALL to 3-4 seconds with explicit user communication
3. Or: queue transcripts and process in batch (trade-off: 2s+ latency for EWB)

**Files:** `config.py` (ANALYSE_INTERVALL), `services/claude_service.py` (analyse_loop implementation)

---

### 2. State Lock Contention on High-Volume Writes

**Location:** `services/live_session.py:103` (state_lock)

**Issue:**
- Single `state_lock` protects 25+ fields
- Every EWB result write (1-2x per second), keyword match write (10+x per second), phase change, readiness score write locks entire state dict
- Deepgram interim transcript processing competes with analyse_loop for same lock

**Severity:** **MEDIUM** — Affects live latency under concurrent transcript/analysis load

**Mitigation:** Phase 06.2 introduced separate locks for different concerns (phase_lock, kb_lock, etc.) but state_lock remains monolithic

**Fix Path:**
1. Split `state_lock` into: `analysis_lock` (ergebnis, line_id, version), `phase_lock` (already separated), `meta_lock` (other)
2. Or accept 2-4ms contention at current 50-user concurrency limit

---

### 3. Deepgram Interim Transcript Processing Regex Overhead

**Location:** `services/deepgram_service.py:105-137` (BUG-10-LAT Wave 2 keyword matching)

**Issue:**
- Keyword matcher runs Regex against **every interim transcript** from Deepgram (~100ms intervals)
- Regex patterns stored in `EinwandKeywordMatcher` (services/einwand_keyword_matcher.py)
- No caching of compiled patterns per session

**Severity:** **LOW-MEDIUM** — Depends on profile size (number of einwaende); typical 10-20 patterns

**Current Status:** Comment indicates this is a known performance area (Wave 2 improvement)

**Action:** Already scoped for optimization; no immediate change needed

---

## Security Considerations

### PreCall Research Input XSS Risk

**Location:** `app.py:58-74` (markdown_filter with bleach sanitizer)

**Status:** **MITIGATED** — Phase POLISH-52 (2026-04-21) added:
- Bleach sanitizer for PreCall briefing HTML rendering
- Allowlist tags: p, br, strong, em, code, pre, ul, ol, li, h1-h4, blockquote, a
- Input path: user provides firm name, industry, contact → Haiku generates markdown → rendered via filter

**Severity:** **LOW** — Mitigation in place; no XSS vectors found in testing

**Review Due:** Verify bleach version is up-to-date; re-audit if user input format changes

---

### Session State Exposure in /api/ergebnis

**Location:** `routes/app_routes.py:140-175` (live() polling endpoint)

**Issue:** Endpoint returns nearly full `ls.state` dict to frontend:
```python
'version':          ls.state['version'],
'aktiv':            ls.state['aktiv'],
'ergebnis':         ls.state['ergebnis'],
'line_id':          ls.state['line_id'],
```

**Current State:** Only non-sensitive fields exposed (version, aktiv, ergebnis). Profile data not exposed.

**Severity:** **LOW** — API is login-required; state dict contains no PII, API keys, or passwords

**Note:** If `ergebnis` dict ever contains user identifiers or profile references, audit this endpoint

---

### Database Session Management

**Location:** Multiple routes (e.g., `routes/app_routes.py:81-80`)

**Pattern:** Manual try-finally for DB session cleanup:
```python
db = get_session()
try:
    # work
finally:
    db.close()
```

**Issue:** No use of context managers; error-prone if exception raised

**Severity:** **LOW** — Pattern is consistently applied; no known resource leaks

**Improvement:** Consider wrapping in @contextmanager decorator (refactor, not urgent)

---

## Test Coverage Gaps

### Integration: Analyse Loop ↔ PreCall Briefing

**Gap:** No test verifies that PreCall briefing data, when present, influences EWB prompt

**Files:** No test in `tests/test_claude_service_phase08.py` for this path

**Risk:** If precall briefing is re-integrated in Phase 08.x, regression risk is high

**Action:** Add test case `test_precall_briefing_in_ewb_prompt()` to verify briefing reaches Claude call

---

### Integration: Manual EWB Button ↔ Profile Context

**Gap:** `streame_manual_ewb_variante()` (claude_service.py:897) has no dedicated test

**Current Tests:** Only tested indirectly via `/api/ewb/<event_id>/rate` endpoint in `tests/test_ewb_rate_api.py`

**Risk:** Hardcoded prompt may drift from intended behavior; profile-less responses unchecked

**Action:** Add unit test for `streame_manual_ewb_variante()` with mock profile data

---

### Dead Code: EWB Clicks Tracking

**Location:** `services/live_session.py:407` (append to ewb_clicks), `routes/app_routes.py:480-490` (read for postcall)

**Test Coverage:** Minimal — tracked but not validated for correctness

**Risk:** If EWB click format changes (dict keys), postcall analysis breaks silently

**Action:** Add schema validation test for ewb_clicks entries

---

## Scaling Limits

### Concurrent User Sessions & State Lock

**Current:** Single global `ls.state` dict managed by one `state_lock`

**Limit:** Works for ~50 concurrent users (Phase 06 UAT limit). Beyond that, lock contention becomes noticeable.

**Improvement Path:**
1. Phase 09+: Migrate to per-session state objects (one dict per user_id)
2. Implement Redis or in-memory session store for multi-worker deployments
3. Current single-threaded design assumes one worker; WSGI multi-worker breaks state sharing

**Severity:** **MEDIUM** — Not a blocker for current phase; document in Phase 09 planning

---

### Claude API Concurrent Requests

**Current:** analyse_loop spawns one non-streaming request per tick (every 4s — Phase 06.3)

**Limit:** At ~50 concurrent users, that's ~25 Claude requests per second (peak). Haiku tier supports this, but quota exhaustion is possible under large deployment.

**Mitigation:** Fair-use limits in place (1000 min/month per user), no hard blocking

**Action:** Monitor token spend; consider batching analysis or increasing ANALYSE_INTERVALL

---

## Missing Critical Features

### Profile Field Live/Coaching Metadata

**Problem:** No way to know at development time whether a profile field is used in live EWB or only coaching

**Workaround:** Must grep through prompt_pipeline.py

**Action:** Add `field_usage` metadata to profile schema (in Phase 08 or 09 refactor doc)

---

### Precall Briefing Usage Flag

**Problem:** PreCall briefing is generated but not used. No clear signal that it's WIP or intentionally disabled.

**Solution:** Add boolean `precall_briefing_enabled` to session config, or deprecate field entirely

---

## Dependencies at Risk

### Deepgram SDK Version

**File:** `requirements.txt` (not visible, inferred from imports)

**Risk:** Deepgram API changes (diarization output format, transcript confidence) could break interim transcript parsing

**Mitigation:** Vendored parsing in `services/deepgram_service.py:350+` handles most changes

**Action:** Pin Deepgram SDK version to known-good release; add integration test for interim transcript format

---

### Anthropic Claude API

**Current:** Using Haiku for live, Sonnet for post-call

**Risk:** API rate limits, cost escalation if token consumption grows

**Current Mitigation:** Fair-use limits enforced per user/org

**Action:** Monitor token spend metrics; consider local/cached fallback for objection responses

---

## Fragile Areas

### Keyword Matcher State (einwand_keyword_matcher.py)

**Location:** `services/einwand_keyword_matcher.py` + `services/live_session.py:13-29` (registry)

**Why Fragile:**
1. Regex patterns loaded from profile JSON (basis.einwaende array)
2. If profile JSON is malformed (invalid regex), matcher fails silently
3. No validation of regex syntax at profile save time

**Safe Modification:**
- Always validate regex patterns when profile is saved (routes/profiles.py)
- Add try-catch in matcher.match_with_dedup() to log failures
- Add unit test for malformed regex handling

**Files:**
- Profile validation: `routes/profiles.py` (add regex validation)
- Matcher: `services/einwand_keyword_matcher.py:match_with_dedup()`
- Test: `tests/test_keyword_matcher.py` (add malformed regex case)

---

### Conversation Log Parsing (routes/app_routes.py:452+)

**Location:** `routes/app_routes.py:452-500` (end_session endpoint)

**Why Fragile:**
- Assumes `conversation_log` global has specific format (dicts with 'text', 'speaker' keys)
- If live_session.py logging format changes, postcall analysis breaks
- No schema validation before inserting into ConversationLog model

**Safe Modification:**
1. Define and validate ConversationLog entry schema at append time (in live_session.py or deepgram_service.py)
2. Use TypedDict for conversation_log entries
3. Add pre-commit hook to validate schema on session end

**Files:**
- Log appending: `services/deepgram_service.py:240+` (append to conversation_log)
- Log reading: `routes/app_routes.py:452+` (read for postcall analysis)
- Validation: Add in `services/live_session.py` (new validator function)

---

## Test Coverage Gaps (Summary)

| Area | Coverage | Gap | Priority |
|------|----------|-----|----------|
| EWB analysis (happy path) | ~80% | None | - |
| Keyword matching (happy path) | ~70% | Malformed regex, edge cases | MEDIUM |
| Phase detection | ~60% | Early/late phase transitions, artifacts | MEDIUM |
| PreCall integration | ~40% | **Briefing not tested in EWB prompt** | **HIGH** |
| Manual EWB button | ~50% | **No dedicated test** | **MEDIUM** |
| Conversation log schema | ~60% | **No format validation** | **MEDIUM** |
| Error recovery | ~30% | API failures, network timeout | LOW |

---

## Recommended Near-Term Actions (Priority Order)

1. **Profile Field Metadata (Phase 08.x)** — Add `field_usage` flag to clarify live vs. coaching fields
   - Impact: Reduces developer confusion, prevents future profile bloat
   - Effort: 2 hours (schema update + docs)
   - Severity: MEDIUM

2. **PreCall Briefing Clarity (Phase 08.x)** — Either re-wire into EWB prompt OR deprecate
   - Impact: Resolves architectural gap, improves data flow clarity
   - Effort: 3-4 hours (re-wire + tests) OR 1 hour (deprecate + cleanup)
   - Severity: HIGH

3. **Manual EWB Button Profile Context (Phase 08.x)** — Inject profile context into hardcoded prompt
   - Impact: Improves button-clicked response quality, aligns with EWB path
   - Effort: 2 hours (refactor + test)
   - Severity: MEDIUM

4. **Add Integration Test for Conversation Log Format (Phase 08.x)** — Validate schema at append time
   - Impact: Prevents silent postcall analysis failures
   - Effort: 1.5 hours
   - Severity: MEDIUM

5. **State Lock Monitoring (Phase 09)** — Instrument lock contention; prepare for per-session state refactor
   - Impact: Foundation for multi-worker scaling
   - Effort: 3-4 hours (instrumentation + analysis)
   - Severity: MEDIUM (not urgent for current phase)

---

*Concerns audit: 2026-04-24*
