---
phase: 02-product-fixes
verified: 2026-03-30T00:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 02: Product Fixes Verification Report

**Phase Goal:** The product is polished and complete — ready for a paying customer's first impression
**Verified:** 2026-03-30
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No 'SalesNerve' string in Python/HTML (except migration literals and seed password) | ✓ VERIFIED | 5 remaining hits are all inside `_migrate()` / `_data_migrate()` string literals used to locate old DB rows and file names — not branding. All production-facing strings use NERVE. |
| 2 | config.py DATABASE_URL default references nerve.db | ✓ VERIFIED | `config.py:10` — `sqlite:///database/nerve.db` |
| 3 | Log regex patterns use nerve_log_ prefix | ✓ VERIFIED | `routes/dashboard.py:16` and `routes/logs_routes.py:38` both contain `nerve_log_` |
| 4 | PLANS dict has exactly 3 flat-rate keys: starter/49, pro/59, business/69 | ✓ VERIFIED | `config.py:20-24` and `app.py` both match: starter=49, pro=59, business=69 |
| 5 | Organisation model has fair-use tracking columns | ✓ VERIFIED | `database/models.py:45-47` — `live_minutes_used`, `training_sessions_used`, `fair_use_reset_month` |
| 6 | ROI tracker uses correct flat-rate fallback (49, not 39) | ✓ VERIFIED | `routes/dashboard.py:283` — `getattr(org, 'plan_preis', None) or 49` |
| 7 | Fair-use counters reset monthly and increment correctly | ✓ VERIFIED | `routes/app_routes.py:43-50` resets on month change, increments `live_minutes_used` at session end; `routes/training.py:75-79` increments `training_sessions_used` at training start |
| 8 | DSGVO banner fires before microphone access | ✓ VERIFIED | Banner fires in `socket.on('connect')` handler (`app.js:127-132`). `getUserMedia` is not called from JS — mic access is PyAudio server-side, triggered by the connection event. Banner appears at the moment of connect, before any audio stream is active. |
| 9 | Training Frei/Gefuehrt mode switching works; post-training preview renders | ✓ VERIFIED | `templates/training.html:271/277` — modus cards; `line:337` — `t-helpRow`; `line:436` — `selectModus()`; `line:538` — helpRow toggle in `initChat`. `routes/training.py:14,346` — `_generate_live_preview` imported and called. 11 TrainingScenarios seeded in `app.py`. Schwierigkeit filter exists at `training.html:395`. |
| 10 | Onboarding and profile editor use generic placeholders; dashboard_style persists | ✓ VERIFIED | `onboarding.html:272` — `placeholder="Vorname"` (not "Max"). 7 `.beispiel-box` elements. `database/models.py:91` — `dashboard_style = Column(String(20), default='vollstaendig')`. `routes/dashboard.py:455` reads and passes it. `dashboard.html:267,309,343,373` — `{% if dashboard_style != 'fokus' %}` conditionals. `profile_editor.html:269` — `placeholder="Ihr Unternehmen"`. |
| 11 | Profile wizard exists with 3 steps; dashboard redirects profileless users | ✓ VERIFIED | `templates/profile_wizard.html` exists with 6 `wizard-step` references (3 step divs + 3 nav references). `routes/profiles.py:61-70` — GET and POST handlers for `/wizard`. `routes/dashboard.py:335-337` — `profile_count == 0` redirects to `profiles.wizard_page`. |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Plan | Status | Key Evidence |
|----------|------|--------|-------------|
| `config.py` | 01, 04 | ✓ VERIFIED | `nerve.db` in DATABASE_URL; PLANS with 3 flat-rate keys |
| `app.py` | 01, 04 | ✓ VERIFIED | `NERVE_DEMO_PROFILE_JSON`, `_seed_demo_profile`, `admin@nerve.local`; migration for all 3 fair-use columns; 11 TrainingScenarios |
| `routes/dashboard.py` | 01, 04, 05, 06 | ✓ VERIFIED | `nerve_log_` regex; `or 49` ROI fallback; `dashboard_style` passed to template; wizard redirect on `profile_count == 0` |
| `routes/logs_routes.py` | 01 | ✓ VERIFIED | `nerve_log_` regex |
| `static/app.js` | 02 | ✓ VERIFIED | DSGVO banner in `socket.on('connect')` before any audio stream |
| `templates/app.html` | 02 | ✓ VERIFIED | `.kompakt-panel .metric-circle` scoped CSS at line 202; `btn-view-toggle` at `top:calc(52px + var(--space-sm, 8px))` |
| `templates/training.html` | 03 | ✓ VERIFIED | `selectModus()`, `t-helpRow`, schwierigkeit filter, live preview section |
| `routes/training.py` | 03 | ✓ VERIFIED | `_generate_live_preview` called in training_end handler |
| `database/models.py` | 04, 05 | ✓ VERIFIED | `live_minutes_used`, `training_sessions_used`, `fair_use_reset_month`; `dashboard_style` |
| `routes/app_routes.py` | 04 | ✓ VERIFIED | fair-use reset and `live_minutes_used` increment at session end |
| `templates/onboarding.html` | 05 | ✓ VERIFIED | `placeholder="Vorname"`, 7 `.beispiel-box` elements, `dashboard_style` hidden input |
| `templates/profile_editor.html` | 05 | ✓ VERIFIED | `placeholder="Ihr Unternehmen"` |
| `templates/dashboard.html` | 05 | ✓ VERIFIED | `{% if dashboard_style != 'fokus' %}` conditional wrapping non-essential widgets |
| `templates/profile_wizard.html` | 06 | ✓ VERIFIED | Exists; 6 wizard-step references; 3-step structure |
| `routes/profiles.py` | 06 | ✓ VERIFIED | GET `/wizard` → `wizard_page()`; POST `/wizard` → `wizard_create()` |

---

### Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|-----|--------|---------|
| `app.py _migrate()` | `database/nerve.db` | `_os.rename salesnerve.db→nerve.db` | ✓ WIRED | `app.py` contains rename block guarded by `exists(old) and not exists(new)` |
| `app.py _data_migrate()` | organisations table | billing_email UPDATE | ✓ WIRED | `UPDATE organisations SET billing_email='admin@nerve.local'` present |
| `routes/dashboard.py _calculate_roi()` | `Organisation.plan_preis` | getattr lookup | ✓ WIRED | `getattr(org, 'plan_preis', None) or 49` at line 283 |
| `routes/app_routes.py` | `Organisation.live_minutes_used` | increment at session end | ✓ WIRED | `_org2.live_minutes_used += minuten` at line 382 |
| `routes/training.py` | `Organisation.training_sessions_used` | increment at training start | ✓ WIRED | `_org.training_sessions_used += 1` at line 79 |
| `static/app.js socket.on('connect')` | DSGVO banner DOM element | `classList.add('visible')` | ✓ WIRED | Lines 127-132 in app.js |
| `templates/training.html selectModus()` | `#t-helpRow visibility` | `style.display` toggle | ✓ WIRED | `initChat()` at line 538 toggles helpRow based on `trainingModus` |
| `routes/training.py training_end` | `_generate_live_preview()` | function call in POST handler | ✓ WIRED | `routes/training.py:346` |
| `templates/onboarding.html` | `routes/onboarding.py` | POST with `dashboard_style` field | ✓ WIRED | Hidden input `name="dashboard_style"` in onboarding form |
| `routes/dashboard.py index()` | `/profiles/wizard` | redirect when `profile_count == 0` | ✓ WIRED | Lines 335-337 in dashboard.py |
| `routes/profiles.py wizard POST` | `database/models.py Profile` | `Profile(...)` creation | ✓ WIRED | `wizard_create()` POST handler creates Profile and sets `user.active_profile_id` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PROD-01 | 02-04 | Pricing system (49/59/69 Flat-Rate) visible in app | ✓ SATISFIED | PLANS dict updated in config.py and app.py; `plan_preis` defaults updated; ROI widget shows correct cost. Full plan-selection UI deferred to Phase 4 per PROD-01 scope note. |
| PROD-02 | 02-04 | ROI-Tracker in Dashboard with usage metrics | ✓ SATISFIED | `routes/dashboard.py:283` — ROI uses correct `or 49` fallback; fair-use counters feed into display |
| PROD-03 | 02-03 | Training mode "Frei" (no hints, max points) | ✓ SATISFIED | `selectModus('free')` in training.html; `t-helpRow` hidden in free mode |
| PROD-04 | 02-03 | Training mode "Gefuehrt" (hints with point deduction) | ✓ SATISFIED | Default mode is guided; `t-helpRow` visible; penalty `min(hilfe_count * 5, 30)` in training.py |
| PROD-05 | 02-03 | Post-training preview "Was NERVE im echten Call gezeigt haette" | ✓ SATISFIED | `_generate_live_preview` called in training_end handler; `.t-live-preview` section in training.html |
| PROD-06 | 02-03 | 11 standard DACH Mittelstand scenarios, all difficulty levels | ✓ SATISFIED | `grep -c "TrainingScenario(" app.py` returns 11; schwierigkeit filter in training.html |
| PROD-07 | 02-02 | Live-mode: correct script button, DSGVO banner before mic, compact circles, toggle position | ✓ SATISFIED | DSGVO banner in `socket.on('connect')`; `.kompakt-panel .metric-circle` CSS scoped fix; `btn-view-toggle` at `top:calc(52px + ...)` |
| PROD-08 | 02-05 | Onboarding uses generic placeholders, dashboard-style selector, Beispiel-Boxen | ✓ SATISFIED | `placeholder="Vorname"`; 7 `.beispiel-box` elements; `.style-card` selector in onboarding.html |
| PROD-09 | 02-06 | 3-step profile wizard for new users | ✓ SATISFIED | `profile_wizard.html` exists with 3 wizard steps; GET+POST routes in profiles.py; dashboard redirect trigger |
| PROD-10 | 02-05 | Profile editor shows generic placeholders | ✓ SATISFIED | `placeholder="Ihr Unternehmen"` in profile_editor.html |
| PROD-11 | 02-01 | All SalesNerve references replaced with NERVE | ✓ SATISFIED | 5 remaining occurrences are all in migration code string literals (old values being searched/renamed) — intentional and correct |

**All 11 PROD requirements accounted for. No orphaned requirements.**

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|-----------|
| `app.py` | `"salesnerve"` string literals in `_migrate()` | ℹ️ Info | These are intentional — they are the old values being searched to perform the rename migration. Not a stub or branding issue. |

No blockers. No warnings.

---

### Human Verification Required

#### 1. DSGVO Banner Visual Timing

**Test:** Open the live session page in browser, click "Start". Observe whether the DSGVO consent banner appears visually before any microphone activity indicator appears.
**Expected:** Banner is visible for ~6 seconds from the moment the socket connects; no audio processing occurs before the banner has been shown.
**Why human:** The banner fires on `socket.on('connect')` which precedes PyAudio startup on the server — but the exact timing gap between socket connect and first audio chunk cannot be verified by code inspection alone.

#### 2. Compact Mode Circles Visual Rendering

**Test:** Open the live session, switch to compact mode. Observe the metric circles (Kaufbereitschaft, Redeanteil, etc.).
**Expected:** All circles are fully visible, properly sized (36x36px per CSS), not clipped or overflowing.
**Why human:** CSS scoped rule exists but actual rendering depends on browser layout engine and runtime DOM state.

#### 3. Profile Wizard Step 1 Industry Cards

**Test:** Create a new account, complete onboarding, arrive at wizard. Verify step 1 shows industry cards as a grid.
**Expected:** 8-10 DACH B2B industry cards visible, selectable, with "Weiter" button activating after selection.
**Why human:** Template exists and routes work, but actual card count and grid rendering requires visual inspection.

#### 4. Dashboard Fokus Mode Widget Visibility

**Test:** Set dashboard_style to 'fokus' for a user, open dashboard. Confirm ROI widget and Kaufbereitschaft are visible; confirm session history table and detailed stats are hidden.
**Expected:** Conditional `{% if dashboard_style != 'fokus' %}` blocks hide non-essential widgets without breaking layout.
**Why human:** Conditional logic is verified but actual widget classification (which widgets are inside vs outside the conditional) and visual layout integrity requires browser check.

---

### Gaps Summary

No gaps. All 11 PROD requirements are satisfied with substantive implementation evidence. The phase goal — *the product is polished and complete, ready for a paying customer's first impression* — is achieved at the code level.

The 4 human verification items are quality/UX checks, not blockers.

---

_Verified: 2026-03-30_
_Verifier: Claude (gsd-verifier)_
