---
phase: 20260421-launch-readiness
fixed_at: 2026-04-20T00:00:00Z
review_path: .planning/reviews/20260421-launch-readiness-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 18
status: all_fixed
---

# Launch-Readiness Code Review Fix Report — 2026-04-21

**Fixed at:** 2026-04-20
**Source review:** `.planning/reviews/20260421-launch-readiness-REVIEW.md`
**Iteration:** 1
**Scope directive (user):** "Nur die 2 Launch-Blockers (LB-01 Markdown-XSS, LB-02 Migration Dry-Run Flag)." Alle PL-/POST-/NTH-Findings wurden vom User explizit auf Phase 08 (architektonischer Fix-Round) verschoben.

**Summary:**
- Findings in scope: 2 (LB-01, LB-02)
- Fixed: 2
- Skipped by user-directive: 18 (6x PL, 7x POST, 5x NTH)

---

## Fixed Issues

### LB-01: Markdown filter renders raw HTML tags — XSS via PreCall-Briefing

**Files modified:** `app.py`, `requirements.txt`
**Commit:** `5a494f7`
**Applied fix:** Added `bleach` post-processing step after `markdown.markdown()` render. Allowlist-only tags (`p`, `br`, `strong`, `em`, `code`, `pre`, `ul`, `ol`, `li`, `h1-h4`, `blockquote`, `a`) + allowlist attrs (`a: href, title`) + allowlist protocols (`http`, `https`, `mailto`), `strip=True`. Added `bleach>=6.1.0` to `requirements.txt`.

**Verification (user-specified):**
Ran inline Python test with four XSS payloads:

```
Test1 input:  <img src=x onerror=alert(1)>
Test1 output: <p></p>                                       -> onerror STRIPPED (tag removed)

Test2 input:  <script>alert(1)</script>
Test2 output: alert(1)                                      -> <script> STRIPPED

Test3 input:  ## Headline\n**bold** and *italic*
Test3 output: <h2>Headline</h2><p><strong>bold</strong> and <em>italic</em></p>
             -> safe markdown PRESERVED

Test4 input:  <iframe src=evil></iframe>
Test4 output: (empty string)                                -> <iframe> STRIPPED
```

All assertions pass (`'onerror' not in result`, `'<script' not in result`, `'<iframe' not in result`, safe-markdown preserved). **XSS-safe: PASS.**

**Pip install:** `pip install "bleach>=6.1.0"` → bleach 6.3.0 + webencodings 0.5.1 installed locally (confirmed on build machine).

---

### LB-02: Migration script `--dry-run` flag mismatch + no production-safeguard

**Files modified:** `scripts/migrate_polish_38_counters.py`
**Commit:** `4a5142f`
**Applied fix:** Replaced `'--dry' in sys.argv` substring-check with `argparse.ArgumentParser()` + two flags (`--dry-run`, `--confirm-production`). Added mandatory safeguard: bare invocation (no args) or any invocation without `--dry-run` AND without `--confirm-production` errors out with exit code 2 and clear message. Updated docstring to match real flag behavior.

**Verification (user-specified 3 CLI invocations):**

```
$ python scripts/migrate_polish_38_counters.py --dry-run
[migrate] Keine ObjectionEvent-Rows in der DB - nichts zu tun.
Exit code: 0                                                -> PASS: dry-run path, no writes

$ python scripts/migrate_polish_38_counters.py
[migrate] FEHLER: Produktions-Lauf braucht --confirm-production flag.
[migrate] Tipp: Erst mit --dry-run pruefen, dann mit --confirm-production scharf laufen lassen.
Exit code: 2                                                -> PASS: safeguard error, no writes

$ python scripts/migrate_polish_38_counters.py --confirm-production
[migrate] Keine ObjectionEvent-Rows in der DB - nichts zu tun.
Exit code: 0                                                -> PASS: scharf run (no-op: DB empty)
```

**Additional argparse checks:**
- `--help` shows both flags documented → PASS
- `--bogus` rejected by argparse with usage message → PASS

**LB-02 verification: PASS (all 3 CLI-invocations behave correctly).**

---

## Skipped Issues

### Skipped by explicit user-directive — deferred to Phase 08 (architectural round)

User statement: *"Nur die 2 Launch-Blockers … Die Pre-Launch items go into a later round (Phase 08)."*

#### PL-01: `/api/beenden` is not wrapped in a single transaction
**File:** `routes/app_routes.py:411-635`
**Skip reason:** Deferred to Phase 08 architectural round. Multiple separate commits (ConversationLog, ObjectionEvent bulk, reconcile, FtCallSession, points) need to be wrapped in nested transactions. Happy-path is correct today because `einwaende_gesamt=len(ewb_clicks)` defensive fallback matches reconciled value.

#### PL-02: Race window between `record_ewb_click` and `api_beenden` state read
**File:** `routes/app_routes.py:402-403`, `services/live_session.py:406-414`
**Skip reason:** Deferred to Phase 08. Low-impact (~5ms click-before-Beenden race), not data-corrupting in aggregate. Both operations already hold `state_lock` — the race is only in thread-scheduling between socketio and HTTP threads.

#### PL-03: SECRET_KEY fallback + CORS wildcard on FLASK_DEBUG
**File:** `config.py:12-13`
**Skip reason:** Deferred to Phase 08. SECRET_KEY startup-guard already raises on insecure default. CORS wildcard-on-debug is a prod-misconfig hazard, but requires explicit `FLASK_DEBUG=1` in prod. Not blocking launch.

#### PL-04: No new tests for launch-critical POLISH changes
**Files:** `tests/`
**Skip reason:** Deferred to Phase 08. Test coverage gap is a regression-safety concern, not a launch-correctness bug. Manual verification during UAT round covered the live paths.

#### PL-05: Migration `--dry-run` flag mismatch (duplicate of LB-02)
**Skip reason:** Already addressed via LB-02 fix in commit `4a5142f`. The REVIEW.md explicitly noted PL-05 was a duplicate reference of the LB-02 issue.

#### PL-06: Deepgram close handler emits raw exception content to frontend
**File:** `services/deepgram_service.py:173-180`
**Skip reason:** Deferred to Phase 08. Current `str(close)` output doesn't contain API keys (verified against deepgram-sdk 3.7+ Close event shape). Info-disclosure risk surfaces only if SDK upgrade changes Close shape.

---

### Skipped as out-of-scope (POST-LAUNCH / NICE-TO-HAVE)

The REVIEW.md classified these as non-blocking post-launch items. User directive confirms: "POST-LAUNCH + NICE-TO-HAVE SKIPPED (out of scope)."

#### POST-01: Phase-classifier lock-ordering comment missing
**File:** `services/claude_service.py:1125-1156`
**Skip reason:** Post-launch. No actual deadlock risk today; code is correct. Documentation-only improvement.

#### POST-02: Deepgram on_close no retry logic
**File:** `services/deepgram_service.py:168-180`
**Skip reason:** Post-launch UX enhancement (reconnect-on-drop). No data-safety impact.

#### POST-03: `_chunk_counts` dict grows unbounded
**File:** `services/deepgram_service.py:357, 363`
**Skip reason:** Post-launch memory-leak mitigation. Low-impact under normal disconnect flow.

#### POST-04: `_letzte_gemeldete_version` dict unbounded
**File:** `routes/app_routes.py:13`
**Skip reason:** Post-launch memory-leak mitigation. Same pattern as POST-03.

#### POST-05: Markdown filter doesn't handle bytes vs str defensively
**File:** `app.py:61-65`
**Skip reason:** Post-launch defensive-coding. POLISH-40 type-guards already prevent `bytes` reaching this filter.

#### POST-06: Close-overlay sessionStorage clear fires on public pages
**File:** `templates/base.html:141-147`
**Skip reason:** Post-launch UX polish. Review confirms this is NOT a security issue.

#### POST-07: `ANALYSE_INTERVALL` semantic drift in CLAUDE.md
**File:** `config.py:37` / `CLAUDE.md`
**Skip reason:** Post-launch docs-sync. No code behavior change.

#### NTH-01: `classify_phase` JSON extraction fragility
**Skip reason:** Nice-to-have post-launch. Haiku outputs reliably structured today.

#### NTH-02: Markdown filter `<br>` + list-item quirks
**Skip reason:** Nice-to-have post-launch. UX polish only.

#### NTH-03: POLISH-46 regex ReDoS assessment
**Skip reason:** Review confirmed all patterns are bounded and safe. No action needed.

#### NTH-04: `ls.state.get('ewb_clicks', [])` default inconsistency
**Skip reason:** Nice-to-have code-harmonization. No behavior impact.

#### NTH-05: CLAUDE.md stale on intervals (duplicate of POST-07)
**Skip reason:** Docs-sync; same as POST-07.

---

## Verification Summary

| Finding | Status | Commit | Verification |
|---------|--------|--------|--------------|
| LB-01   | FIXED  | `5a494f7` | 4 XSS tests PASS: `onerror` stripped, `<script>` stripped, `<iframe>` stripped, safe markdown preserved |
| LB-02   | FIXED  | `4a5142f` | 3 CLI-invocations PASS: `--dry-run` (exit 0, no write), no-args (exit 2, safeguard), `--confirm-production` (exit 0, scharf run) |

**All in-scope fixes verified. Working tree clean after both commits.**

**Phase 08 (architectural round) TODO:** 6 PL-findings + 7 POST-findings + 5 NTH-findings (see skip-table above).

---

_Fixed: 2026-04-20_
_Fixer: Claude (gsd-code-fixer, Opus 4.7 1M ctx)_
_Iteration: 1_
_Scope: user-restricted to LB-01 + LB-02 only_
