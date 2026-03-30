# Phase 2: Product Fixes - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning
**Mode:** Auto (--auto flag — all decisions chosen at recommended defaults)

<domain>
## Phase Boundary

Polish the product to be ready for a paying customer's first impression. This phase covers pricing model restructure, training mode verification, onboarding UX improvements, a guided 3-step profile wizard, and eliminating all SalesNerve remnants. No new capabilities — only completing and fixing what was scoped. Phase 3 (Deployment) depends on this phase being complete.

**Hard gate:** Phase 3 requires a clean, polished product. Phase 4 (Payments) will wire payments to the new pricing model defined here.

</domain>

<decisions>
## Implementation Decisions

### Pricing Model Restructure (PROD-01, PROD-02)

- **D-01:** Replace the old per-user pricing model (starter/team/business/enterprise with `price_per_user`) with 3 flat-rate individual plans:
  - `starter` → 49€/month
  - `pro` → 59€/month
  - `business` → 69€/month
  All plans are individual (no `max_users` concept). PLANS dict in `config.py` gets a full rewrite.

- **D-02:** Fair-use limits tracked per Organisation (owner-level), not per individual user. Add 3 new columns to the `Organisation` model:
  - `live_minutes_used` (Integer, default 0) — reset monthly
  - `training_sessions_used` (Integer, default 0) — reset monthly
  - `fair_use_reset_month` (String(7), e.g. "2026-04") — track which month the counters belong to
  Limits: 1000 live minutes / month, 50 training sessions / month. At 80% of limit: soft warning (no hard block). Counter reset logic: check `fair_use_reset_month` on each session start; if month changed, reset both counters.

- **D-03:** ROI tracker in `_calculate_roi()` (dashboard.py): update `plan_kosten` lookup to use the new flat-rate `plan_preis` field directly. Plan key lookup stays the same pattern (`PLANS.get(plan_key, {})`). ROI widget in dashboard.html already exists and renders this — no new UI needed, just correct data.

- **D-04:** The `plan_preis` field on Organisation stays as the source of truth (already exists in model). New plan defaults: starter=49, pro=59, business=69. Update the default assignment where plan_preis is set from PLANS.

### Training Modes — Verification (PROD-03, PROD-04)

- **D-05:** Training modes (Frei/Geführt) are **already implemented** in `training.html` and `routes/training.py`. Phase 2 task = verify correctness and polish:
  - Frei mode: help button (`t-help-btn`) must be hidden/disabled when `trainingModus === 'free'` — verify this is enforced in JS
  - Geführt mode: help button visible, each use adds a penalty. Verify scoring: Frei = +50% bonus on base score, Geführt = -X points per hint used (current code has this logic in route — confirm the penalty value is reasonable)
  - Default mode on page load: Geführt (already set with `t-modus-active` class on guided card) — correct, keep as-is

### Post-Training Preview — Verification (PROD-05)

- **D-06:** Post-training preview ("Was NERVE im echten Call gezeigt hätte") is **already fully implemented**: `_generate_live_preview()` in `services/training_service.py` + `.t-live-preview` section in `training.html`. Phase 2 task = verify it renders correctly after a session ends and that the "Zusammenfassung" text is visible. No new implementation needed.

### Standard Training Scenarios (PROD-06)

- **D-07:** All 11 standard DACH Mittelstand scenarios are **already seeded** in `_seed_training_scenarios()` in `app.py`:
  - 3 × Leicht (Warmer Lead, Empfehlung, Follow-up nach Demo)
  - 3 × Mittel (Kaltakquise, Wettbewerber-Wechsel, Preisverhandlung)
  - 3 × Schwer (Abwimmler, Technischer Entscheider, Einkäufer)
  - 2 × Sekretärin (Blockt + Entscheiderin)
  Phase 2 task = verify scenarios are visible in training scenario selector, that `schwierigkeit` filter UI works per difficulty, and that `spezial_einwaende` are used by the training engine.

### Live-Mode Bug Fixes (PROD-07)

- **D-08:** Fix all 4 live-mode bugs. Each fix is a targeted surgical change — read `templates/app.html` and `static/app.js` to confirm current state before touching anything:
  1. **Script button** — investigate why `sp-toggle-btn` is broken or in wrong state; fix so script panel opens correctly
  2. **DSGVO banner** — must appear BEFORE `navigator.mediaDevices.getUserMedia()` is called. If currently firing after, move the banner display logic to precede the mic access request. This is a DSGVO-critical fix.
  3. **Compact mode circles** — `.metric-circle` elements in `.kompakt-panel` have a visual rendering bug; fix CSS/JS so circles display correctly in compact mode
  4. **Toggle position** — `.btn-view-toggle` (compact mode toggle button) is in the wrong position; move to the correct location per the intended design

### Onboarding Improvements (PROD-08)

- **D-09:** Replace hard-coded demo placeholders with generic text in `templates/onboarding.html`:
  - `placeholder="Max"` → `placeholder="Vorname"`
  - Any specific industry/product examples → generic equivalents
  - Remove or generalize any NERVE-specific demo content

- **D-10:** Add **Dashboard-Style selection** as a new card choice in onboarding (recommended placement: between existing step 2 and step 3, or as an addition to step 2). Show 2 cards:
  - "Fokus" — Minimalist view: ROI widget + Kaufbereitschaft + next-session CTA only
  - "Vollständig" (default, pre-selected) — All current dashboard widgets
  Store choice as a new `dashboard_style` column on the `User` model (String(20), default='vollständig'). Dashboard route reads this preference and conditionally renders widget sections.

- **D-11:** Add **Beispiel-Boxen** in onboarding step 1 — 3 static visual preview cards showing what NERVE displays during a real call:
  - Card 1: "Gegenargument" — shows sample objection counter text
  - Card 2: "Kaufbereitschaft" — shows the 0–100% readiness gauge
  - Card 3: "Coaching-Tipp" — shows sample coaching nudge
  These are visual-only (no interaction). Purpose: explain the product during onboarding before the user has used it.

### Profile Wizard (PROD-09)

- **D-12:** Create a new `/profile/wizard` route in `routes/profiles.py` (or a new `routes/profile_wizard.py` blueprint). 3-step wizard flow in a new template `templates/profile_wizard.html`:
  - **Step 1: Branche & Rolle** — Industry card selection (reuse or adapt the industry cards from onboarding step 3) + role text input ("Was verkaufst du?")
  - **Step 2: Produkt & Firma** — Company name, product/service description, target customer — all with generic placeholders ("Ihr Unternehmen", "Ihr Produkt oder Service", "Ihre Zielkunden")
  - **Step 3: Häufige Einwände** — Pick 3 common objections from a template list (DACH B2B typical) or enter free text. These seed the profile's objection handling.

- **D-13:** Trigger: New user on first login when no profile exists — redirect to `/profile/wizard` instead of showing empty `profile_editor`. After wizard completion, profile is created and user lands on dashboard. The existing onboarding flow is NOT replaced — wizard fires if onboarding is done but no profile exists, OR is integrated as step 3 replacement.

### Profile Editor Placeholders (PROD-10)

- **D-14:** In `templates/profile_editor.html`, replace all demo-content placeholders with generic text:
  - Company names → "Ihr Unternehmen"
  - Product names → "Ihr Produkt oder Service"
  - Person names → "Ihr Name" / "Ansprechpartner"
  - Any NERVE-specific demo content → generic
  This is a pure template edit — no route changes needed.

### SalesNerve Cleanup (PROD-11)

- **D-15:** Full rename across code and UI. Scope:
  - `config.py`: `DATABASE_URL` default `salesnerve.db` → `nerve.db`. Add migration check in `_migrate()` to rename existing database file if found.
  - `routes/dashboard.py` line 16: log filename regex `salesnerve_log_` → `nerve_log_`
  - `routes/logs_routes.py` line 38: log filename validation regex `salesnerve_log_` → `nerve_log_`
  - `app.py`: `SALESNERVE_PROFILE_JSON` → `NERVE_DEMO_PROFILE_JSON`, `_seed_salesnerve_profile` → `_seed_demo_profile`, seed account `andre@salesnerve.de` → `admin@nerve.local`
  - Any remaining "SalesNerve" strings in templates → "NERVE"
  - **Intentionally NOT changed:** seed password `SalesNerve2024!` (internal dev seed only, never shown to users; rename on next credential rotation)

### Claude's Discretion

- Exact penalty value per hint use in Geführt mode (e.g., -10% or -5 points per hint) — choose what feels fair given the scoring range observed in the codebase
- Exact list of industry cards in profile wizard step 1 — reuse existing industries from onboarding, add any missing DACH B2B verticals
- Template list of häufige Einwände in wizard step 3 — generate 8-10 typical DACH B2B objections to choose from
- Visual design of Beispiel-Boxen — match existing card style (dark bg, gold accent, border) from the app's established design language

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — Stack constraints (Flask + Vanilla JS, no React), Haiku-only for live loop, bootstrap budget
- `.planning/REQUIREMENTS.md` — PROD-01 through PROD-11 acceptance criteria, full traceability table

### Core Files to Read Before Planning
- `config.py` — Current PLANS dict (per-user model being replaced), all constants
- `routes/training.py` — Training mode handling (modus param, scoring, live_preview call)
- `services/training_service.py` — `_generate_live_preview()` implementation
- `templates/training.html` — Training UI (mode cards, help button, results section, live preview rendering)
- `templates/app.html` — Live mode template (DSGVO banner, script panel, compact mode, toggle button)
- `routes/dashboard.py` — `_calculate_roi()` function, plan_key lookup logic
- `app.py` lines 449-619 — `_seed_training_scenarios()` (11 existing scenarios), `_seed_salesnerve_profile()`, migration logic in `_migrate()`
- `database/models.py` — Organisation model (plan_typ, plan_preis fields), User model

No external ADRs — requirements are fully captured in REQUIREMENTS.md and decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `templates/training.html` `.t-modus-grid` + `selectModus()` JS — training mode selector (Frei/Geführt) already complete
- `templates/training.html` `.t-live-preview` section — post-training preview rendering already complete
- `templates/onboarding.html` industry card grid (step 3) — reuse or adapt for profile wizard step 1
- `routes/dashboard.py` `_calculate_roi()` — ROI calculation exists, just needs plan price update
- `app.py` `_seed_training_scenarios()` — 11 scenarios already seeded and categorized

### Established Patterns
- Dark theme: `#0c0c18` bg, `#E8B040` gold accent, `#6b6b80` muted text — all new UI must match
- Card selection UI: `.t-modus-card` / `.t-modus-active` pattern — use for wizard step choices and dashboard-style selector
- German variable names for domain concepts: `einwaende`, `schwierigkeit`, `gegenargument`, `modus`
- Try/finally for all DB sessions (see `routes/auth.py`)
- Blueprint pattern: new routes go in `routes/` with `_bp` suffix

### Integration Points
- **Pricing changes** feed into Phase 4 (Payments): `PLANS` dict and `Organisation.plan_preis` are the source of truth Stripe integration will read
- **Fair-use counters** (new columns) need to be incremented in `routes/app_routes.py` (live session start) and `routes/training.py` (training session start)
- **dashboard_style preference** (new User column): `routes/dashboard.py` route reads it and conditionally renders sections in `templates/dashboard.html`
- **DB rename migration**: `_migrate()` in `app.py` already handles schema migrations — add file rename logic there

</code_context>

<specifics>
## Specific Ideas

- Training mode help button: look for `id="t-helpBtn"` in `training.html` — verify it's hidden when `trainingModus === 'free'` in the `selectModus()` JS function
- DSGVO banner fix: search for `getUserMedia` in `static/app.js` — banner must fire before this call
- Profile wizard industry list: reuse `templates/onboarding.html` step 3 industry cards as starting point
- SalesNerve DB rename: check if `database/salesnerve.db` exists on disk; if so, add `os.rename()` in `_migrate()` as a one-time migration check

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-product-fixes*
*Context gathered: 2026-03-30*
