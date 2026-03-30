# Phase 2: Product Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 02-product-fixes
**Mode:** Auto (--auto flag)
**Areas discussed:** Pricing Model Shape, Training Mode Verification, Onboarding Dashboard-Style, Profile Wizard Steps, SalesNerve Cleanup Scope, Live-Mode Bug Fix Approach

---

## Pricing Model Shape (PROD-01, PROD-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Keep per-user model, adjust prices | Minimal change, update max_users tiers | |
| 3 flat-rate solo plans (49/59/69€) | Replace model entirely — matches requirements | ✓ |
| Hybrid (solo + team tiers) | More complex, premature for 50 Early Access users | |

**Auto choice:** 3 flat-rate solo plans (Starter 49€, Pro 59€, Business 69€)
**Notes:** Requirements PROD-01 explicitly states "69/59/49 Flat-Rate". Fair-use counters go on Organisation model. Phase 4 will wire Stripe to these plan keys.

---

## Training Mode Verification (PROD-03, PROD-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify existing implementation only | Code already complete (training.html + routes/training.py) | ✓ |
| Rewrite training mode logic | Unnecessary — feature is substantially built | |

**Auto choice:** Verify and polish existing implementation
**Notes:** Codebase scout confirmed Frei/Geführt modes are fully implemented. Task is verification, not new development.

---

## Post-Training Preview (PROD-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify existing implementation only | _generate_live_preview() and .t-live-preview both exist | ✓ |
| Redesign preview UI | Unnecessary — existing UI matches requirement | |

**Auto choice:** Verify existing implementation
**Notes:** `_generate_live_preview()` in training_service.py is complete with Haiku call. Template renders it in `.t-live-preview` section.

---

## Standard Scenarios (PROD-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Verify existing 11 scenarios | All 11 already seeded in _seed_training_scenarios() | ✓ |
| Add/replace scenarios | Unnecessary — existing set covers Leicht/Mittel/Schwer/Sekretärin | |

**Auto choice:** Verify existing scenarios are accessible and correctly filtered by difficulty
**Notes:** Exactly 11 scenarios seeded: 3 Leicht + 3 Mittel + 3 Schwer + 2 Sekretärin.

---

## Live-Mode Bug Fixes (PROD-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all 4 bugs in one pass | Script button, DSGVO banner, compact circles, toggle position | ✓ |
| Triage and fix most critical only | DSGVO banner is legally required — can't defer | |

**Auto choice:** Fix all 4 bugs
**Notes:** DSGVO banner placement is legally critical (must fire before mic access). All 4 are targeted surgical fixes after reading app.html and app.js.

---

## Onboarding Dashboard-Style Selection (PROD-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Binary card choice (Fokus / Vollständig) | Simple, reuses existing .t-modus-card pattern | ✓ |
| More than 2 styles | Premature — 2 choices sufficient for v1 | |
| Skip dashboard style selection | Requirement PROD-08 explicitly includes it | |

**Auto choice:** Binary card choice — "Fokus" vs "Vollständig" (default)
**Notes:** Stored as `user.dashboard_style` column. Dashboard route conditionally renders widget sections based on this value.

---

## Profile Wizard 3 Steps (PROD-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Step 1: Industry + Role / Step 2: Product + Company / Step 3: Objections | Builds complete profile progressively | ✓ |
| Embed in existing onboarding flow | Onboarding already has 5 steps — adds complexity | |
| Single long form with sections | Same as current empty form — doesn't solve the problem | |

**Auto choice:** Separate /profile/wizard route, 3-step flow
**Notes:** Triggered on first login when no profile exists. After completion, profile is created and user lands on dashboard. Existing onboarding flow unchanged.

---

## SalesNerve Cleanup Scope (PROD-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Full code + UI rename including DB file | Comprehensive, no lingering references | ✓ |
| UI only, leave code variable names | Leaves dead references in codebase | |
| Rename all including seed password | Seed password is internal-only, not worth changing now | |

**Auto choice:** Full rename — code + UI + DB filename migration; exclude seed password
**Notes:** Key renames: DATABASE_URL default, log filename regex (2 files), seed account email, SALESNERVE_PROFILE_JSON variable, _seed_salesnerve_profile function. DB file rename handled as one-time migration in _migrate().

---

## Claude's Discretion

- Exact hint penalty value in Geführt mode
- Exact industry card list for profile wizard step 1
- Template objection list for wizard step 3
- Visual design of onboarding Beispiel-Boxen (match existing dark/gold card style)

## Deferred Ideas

None captured during this session.
