# Phase 2: Product Fixes - Research

**Researched:** 2026-03-30
**Domain:** Flask/Jinja2/Vanilla JS — pricing model, UI bug fixes, onboarding UX, profile wizard, rename
**Confidence:** HIGH (all findings verified against actual codebase source files)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Replace PLANS dict in config.py and app.py with 3 flat-rate individual plans: starter=49€, pro=59€, business=69€. No max_users concept.

**D-02:** Add 3 new columns to Organisation model: `live_minutes_used` (Integer, default 0), `training_sessions_used` (Integer, default 0), `fair_use_reset_month` (String(7)). Limits: 1000 live minutes / 50 training sessions per month. Soft warning at 80%. Counter reset: check `fair_use_reset_month` on each session start.

**D-03:** ROI tracker in `_calculate_roi()` (dashboard.py): update `plan_kosten` lookup to use flat-rate `plan_preis` field directly.

**D-04:** `plan_preis` field on Organisation is source of truth. New defaults: starter=49, pro=59, business=69.

**D-05:** Training modes (Frei/Geführt) are already implemented. Phase 2 = verify correctness. Frei mode: `t-help-btn` must be hidden when `trainingModus === 'free'`. Geführt: help button visible, penalty per use.

**D-06:** Post-training preview is already fully implemented. Phase 2 = verify it renders correctly.

**D-07:** 11 standard DACH scenarios are already seeded. Phase 2 = verify visible in selector, `schwierigkeit` filter works, `spezial_einwaende` used by engine.

**D-08:** Fix 4 live-mode bugs: (1) script button state, (2) DSGVO banner before getUserMedia, (3) compact mode circles CSS rendering, (4) toggle button position.

**D-09:** Replace hard-coded demo placeholders in onboarding.html: `placeholder="Max"` → `placeholder="Vorname"`.

**D-10:** Add Dashboard-Style selection as new card choice in onboarding. 2 cards: "Fokus" / "Vollständig" (default). Store as new `dashboard_style` column on User (String(20), default='vollständig').

**D-11:** Add 3 static Beispiel-Boxen in onboarding step 1 (Gegenargument, Kaufbereitschaft, Coaching-Tipp).

**D-12:** Create `/profile/wizard` route + `profile_wizard.html` template. 3-step flow: Branche & Rolle / Produkt & Firma / Häufige Einwände.

**D-13:** Trigger on first login when onboarding done but no profile exists — redirect to `/profile/wizard`.

**D-14:** In `profile_editor.html`, replace demo placeholders with generic text.

**D-15:** Full rename: config.py DATABASE_URL default, dashboard.py log regex, logs_routes.py log regex, app.py SALESNERVE_PROFILE_JSON → NERVE_DEMO_PROFILE_JSON and related functions/seed email. Add `os.rename()` for salesnerve.db → nerve.db in `_migrate()`. NOT changed: seed password `SalesNerve2024!`.

### Claude's Discretion

- Exact penalty value per hint use in Geführt mode
- Exact industry card list in profile wizard step 1
- Template list of häufige Einwände in wizard step 3
- Visual design of Beispiel-Boxen (match existing card style)

### Deferred Ideas (OUT OF SCOPE)

None declared.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-01 | User kann das neue Pricing-System (69/59/49€ Flat-Rate) in der App sehen und einen Tarif auswählen | PLANS dict rewrite in app.py (lines 121–155) + config.py (lines 19–24) confirmed |
| PROD-02 | User sieht im Dashboard einen ROI-Tracker mit persönlichen Nutzungsmetriken | `_calculate_roi()` in dashboard.py (line 265) exists, reads `plan_preis` already correctly via `getattr(org, 'plan_preis', None) or 39` |
| PROD-03 | User kann Trainings-Modus "Frei" wählen (max Punkte, keine Hilfe-Hints) | `selectModus('free')` exists in training.html JS (line 436); `t-helpRow` hidden when modus=free in `initChat()` (line 539) |
| PROD-04 | User kann Trainings-Modus "Geführt" wählen (Hilfe verfügbar mit Punktabzug) | Guided mode default confirmed; penalty = `min(hilfe_count * 5, 30)` in training_end (routes/training.py line 316) |
| PROD-05 | User sieht nach Training Preview "Was NERVE im echten Call gezeigt hätte" | `_generate_live_preview()` called in training_end; rendered in `.t-live-preview` section (training.html ~line 908) |
| PROD-06 | User kann aus 11 Standard-Trainingsszenarien wählen | All 11 seeded in `_seed_training_scenarios()` (app.py lines 449–571); API at `/training/scenarios` exists |
| PROD-07 | Live-Modus zeigt korrekten Skript-Button, DSGVO-Banner vor Mikrofon-Zugriff, Kompakt-Modus Kreise, Toggle | 4 concrete bugs verified in codebase — see Pitfall section |
| PROD-08 | Onboarding nutzt generische Placeholder, bietet Dashboard-Stil Auswahl, zeigt Beispiel-Boxen | Placeholder "Max" confirmed (onboarding.html line 226); dashboard_stil field exists as free-text textarea (not card selector) |
| PROD-09 | Neuer User durchläuft 3-Schritte Profil-Wizard statt leerem Formular beim ersten Login | No `/profile/wizard` GET route or template exists yet; only a POST `/profiles/wizard` exists (routes/profiles.py line 61) |
| PROD-10 | Profil-Editor zeigt generische Placeholder ("Ihr Produkt", "Ihr Unternehmen") | Most placeholders already generic in profile_editor.html; verify for any NERVE-specific demo content |
| PROD-11 | Alle SalesNerve-Referenzen im Code und UI sind durch NERVE ersetzt | 6 concrete locations confirmed; salesnerve.db file exists on disk |
</phase_requirements>

---

## Summary

Phase 2 is a polish-and-fix phase on an existing Flask + Vanilla JS application at v0.9.4. The codebase is mature — most features exist but several contain bugs, mismatches, or are only half-wired. Research confirms the exact state of every requirement by reading the actual source files.

The most critical finding is the **DSGVO bug**: the consent banner fires AFTER the first transcript arrives (app.js line 134), meaning `getUserMedia` is called before consent is shown. This is a DSGVO-legal requirement and must be prioritized. The fix requires moving banner display logic to precede the mic access request.

The second important finding is that the **profile wizard GET route does not exist yet** — only a POST handler at `/profiles/wizard` exists. D-12 requires creating a new GET route, blueprint, and template from scratch.

The pricing model has a split-brain problem: `config.py` still has the old per-user PLANS dict (starter/team/business/enterprise with `price_per_user`), while `app.py` has an already-evolved PLANS dict with different keys (solo/team/business/enterprise/trial/coach/bundle/starter) that partially aligns with the new model but uses the wrong prices. D-01 requires a coordinated rewrite of both.

**Primary recommendation:** Execute changes in this order: (1) PROD-11 rename first (establishes clean naming baseline), (2) PROD-07 DSGVO bug (legal priority), (3) PROD-01/PROD-02 pricing (foundational for Phase 4), (4) remaining verification tasks, (5) new UI features (onboarding, wizard).

---

## Standard Stack

### Core (existing — do not change)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.0.0+ | Web framework | Locked by CLAUDE.md |
| SQLAlchemy | 2.0.0+ | ORM | Existing pattern throughout codebase |
| Jinja2 | (bundled with Flask) | HTML templating | All existing templates use it |
| Vanilla JS | ES6+ | Frontend logic | Locked — no React/framework |

### No New Dependencies Required

All Phase 2 work is:
- Python backend changes (config.py, routes, models)
- Jinja2 template additions/edits
- Vanilla JS fixes and additions
- CSS additions (CSS Custom Properties only)

No new pip packages needed. No new npm packages needed.

---

## Architecture Patterns

### Existing Patterns to Follow

**Blueprint pattern:**
```python
# New route (profile wizard) goes in routes/profiles.py (existing blueprint)
# or a new routes/profile_wizard.py with profile_wizard_bp = Blueprint('profile_wizard', __name__)
# Register in app.py at the blueprints section
```

**DB migration pattern (for new columns):**
```python
# In _migrate() in app.py — the try/except pattern for ALTER TABLE:
for col, typedef in [
    ('new_column_name', 'INTEGER DEFAULT 0'),
]:
    try:
        conn.execute(text(f'ALTER TABLE tablename ADD COLUMN {col} {typedef}'))
        conn.commit()
        print(f"[DB] Migration: added tablename.{col}")
    except Exception:
        pass
```

**Try-finally DB session pattern (mandatory):**
```python
db = get_session()
try:
    # all DB work here
    db.commit()
finally:
    db.close()
```

**Flash messages:**
```python
flash('Profil erstellt. Willkommen bei NERVE.', 'success')
flash('Profil konnte nicht gespeichert werden. Bitte erneut versuchen.', 'error')
```

**CSS Custom Properties (MANDATORY — from UI-SPEC):**
```css
/* NEVER hardcode hex values in templates */
/* ALWAYS use CSS custom properties */
background: var(--color-card);
border: 1px solid var(--color-border);
color: var(--color-text-primary);
/* Selected state for cards */
border-color: var(--color-amber);
background: rgba(232, 146, 42, 0.08);
```

**Card selection UI pattern (from training.html — reuse for wizard and dashboard selector):**
```html
<div class="t-modus-card t-modus-active" id="t-modus-guided" onclick="selectModus('guided')">
```
```javascript
function selectModus(modus) {
  trainingModus = modus;
  document.querySelectorAll('.t-modus-card').forEach(c => c.classList.remove('t-modus-active'));
  const card = document.getElementById('t-modus-' + modus);
  if (card) card.classList.add('t-modus-active');
}
```

**Onboarding wizard pattern (reuse for profile wizard):**
- Progress dots: `.progress-dot` / `.progress-line` pattern
- Wizard container: `max-width: 580px`, centered
- Navigation: `.btn-back` / `.btn-next` buttons
- Step visibility: show/hide step divs with JS `currentStep` variable

### Recommended New File Structure

No new directories needed. New files:
```
routes/profile_wizard.py      (new blueprint OR add routes to profiles.py)
templates/profile_wizard.html (new template)
```

All other changes are edits to existing files.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DB schema migration | Custom migration runner | `_migrate()` pattern in app.py — just add columns to the existing try/except loop | Already works, handles duplicate-column silently |
| File rename check | Complex OS detection | `os.path.exists()` + `os.rename()` in `_migrate()` | One-liner, idiomatic Python |
| Multi-step wizard state | Custom session/localStorage state machine | Simple JS `currentStep` variable + show/hide divs (onboarding.html pattern) | Already proven in this codebase |
| Card multi-select for objections | Custom event system | Toggle `.selected` class on click, read at submit time with `querySelectorAll('.selected')` | Onboarding already uses `.t-modus-active` pattern |

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `database/salesnerve.db` — file confirmed on disk at `C:\Users\andre\OneDrive\Desktop\salesnerve\database\salesnerve.db` | `os.rename()` migration in `_migrate()`: if `salesnerve.db` exists, rename to `nerve.db`. Also: `_data_migrate()` already renames `'SalesNerve Alpha'` organisation to `'NERVE Alpha'` in DB — review if any remaining string values in DB rows contain "salesnerve" |
| Live service config | No external services (n8n, Datadog, etc.) found — app is self-contained Flask | None |
| OS-registered state | No Windows Task Scheduler / pm2 / systemd services found in codebase | None |
| Secrets/env vars | `DATABASE_URL` in `.env` currently points to `sqlite:///database/salesnerve.db` — will break after file rename | Update `.env` default and instruct developer to update `.env` file. The `config.py` default is also `sqlite:///database/salesnerve.db` → change to `sqlite:///database/nerve.db` |
| Build artifacts | No compiled artifacts; Python `__pycache__` will auto-regenerate. `salesnerve.db` is the only runtime artifact | Rename via `_migrate()` as above |

**DSGVO/legal note:** `seed account email` `andre@salesnerve.de` and `billing_email` `andre@salesnerve.de` are stored in the `organisations` table as `billing_email`. The `_data_migrate()` function already renames the org name but does NOT update `billing_email`. D-15 changes the seed account email for new installs to `admin@nerve.local` — but for existing DB this is a data migration. Decision context says seed password is intentionally NOT renamed.

---

## Common Pitfalls

### Pitfall 1: DSGVO Banner Fires After getUserMedia (CONFIRMED BUG)
**What goes wrong:** app.js line 134 shows the DSGVO banner only when the FIRST transcript segment arrives — meaning the microphone is already active and getUserMedia already called.
**Why it happens:** Banner display was wired to the Socket.IO `transcript` event handler, not to session start.
**How to avoid:** Move banner display to the session start flow, BEFORE any `navigator.mediaDevices.getUserMedia()` call. Search for `getUserMedia` in app.js to find the exact call site, then show the banner there with a user acknowledgement step.
**Warning signs:** In browser DevTools — Network tab will show WebSocket connection established before the banner appears.

### Pitfall 2: PLANS Dict Split-Brain Between config.py and app.py
**What goes wrong:** `config.py` has the OLD PLANS dict (starter/team/business/enterprise with `price_per_user`). `app.py` has a NEWER PLANS dict (solo/team/business/enterprise/trial/coach/bundle/starter). They are inconsistent. `dashboard.py` imports from `app.py` (`from app import PLANS`). D-01 requires rewriting both.
**How to avoid:** Rewrite `app.py` PLANS as the canonical source with new keys (starter=49, pro=59, business=69). Then rewrite `config.py` PLANS to match. Verify all import sites use `from app import PLANS`, not `from config import PLANS`.
**Warning signs:** Plan name lookups returning wrong prices; ROI widget showing wrong `plan_preis`.

### Pitfall 3: Profile Wizard GET Route Missing
**What goes wrong:** D-12 requires a GET `/profile/wizard` route. Only a POST `/profiles/wizard` exists (routes/profiles.py line 61). If the planner treats D-12 as only a template addition, the route will 404.
**How to avoid:** Create a GET handler returning `render_template('profile_wizard.html')` AND a POST handler that creates the profile and redirects to dashboard. The POST can reuse/extend the existing `wizard_create` logic.
**Warning signs:** 404 on GET /profile/wizard or /profiles/wizard.

### Pitfall 4: onboarding_done Flag Gating for Wizard Trigger
**What goes wrong:** D-13 says "redirect to /profile/wizard when onboarding done but no profile exists." The `login_required` decorator in auth.py (line 32) already redirects to onboarding if `onboarding_done=False`. The wizard trigger must happen AFTER onboarding, not instead of it — specifically in the dashboard route, not in `login_required`.
**How to avoid:** Add profile-check logic to `dashboard_bp.index()` in dashboard.py: after loading user, if `active_profile_id is None` and no profiles exist for the org, redirect to `/profile/wizard` (or `/profiles/wizard`). Do NOT add this check in `login_required` — it would loop with onboarding redirect.
**Warning signs:** Infinite redirect loop between onboarding and wizard.

### Pitfall 5: D-10 dashboard_style vs Existing dashboard_stil Field
**What goes wrong:** D-10 says add new `dashboard_style` column (String(20)). But `database/models.py` line 83 already has `dashboard_stil = Column(Text)` — a free-text textarea for "persönlicher Stil" (WoW, BVB, etc.). These are DIFFERENT fields serving different purposes: `dashboard_stil` = gamification text style; `dashboard_style` = Fokus/Vollständig widget layout. They must coexist.
**How to avoid:** Add `dashboard_style` as a NEW column (not `dashboard_stil`). Migration adds `dashboard_style VARCHAR(20) DEFAULT 'vollstandig'` to users table. Onboarding sends both: existing `dashboard_stil` (free text) + new `dashboard_style` (card selection).
**Warning signs:** Overwriting existing `dashboard_stil` column; breaking weekly summary generation in `_generate_weekly_summary()` which reads `user.dashboard_stil`.

### Pitfall 6: Script Button (sp-toggle-btn) State on Page Load
**What goes wrong:** The script button `#skriptToggleBtn` initializes with class `disabled` in app.html (line 444). `initSkript()` in app.js (line 854) is called with `active_phasen` injected server-side (line 957). If `active_phasen` is empty/null, button stays disabled and user cannot open the script panel even after profile has phasen.
**How to avoid:** Inspect the server-side `active_phasen` value injected in app.html. Verify it correctly reads from the active profile. Fix `initSkript()` call to only enable the button when `skriptData.some(p => p.items.length > 0)` is truly evaluated after server data arrives.
**Warning signs:** Button stuck in `.disabled` state even with a profile that has phasen defined.

### Pitfall 7: Compact Mode Circles in kompakt-panel Context
**What goes wrong:** `.metric-circle` elements are defined in `.metric-circles` inside `.panel-sprachanalyse` (the normal mode panel). In compact mode, `body.kompakt .main` is `display:none`. The compact panel (`.kompakt-panel`) has its own layout but it is unclear if `.metric-circle` styles carry over correctly in the compact panel context.
**How to avoid:** Search for `.metric-circle` usage inside `#kompaktPanel` specifically. The CSS rule for `.metric-circle` (app.html line 196) is global — but the compact panel may have different flex/grid constraints clipping the circles. Fix is likely a CSS override scoped to `.kompakt-panel .metric-circle`.

---

## Code Examples

### PLANS Dict Rewrite (D-01) — canonical pattern for app.py
```python
# Source: app.py lines 121–155 (current state to REPLACE)
PLANS = {
    'starter':  {'name': 'Starter',  'preis': 49, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'pro':      {'name': 'Pro',      'preis': 59, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
    'business': {'name': 'Business', 'preis': 69, 'max_users': 1,
                 'minuten_limit': 1000, 'training_voice_limit': 50},
}
```

### Fair-Use Reset Logic Pattern (D-02) — based on existing training.py pattern
```python
# Source: routes/training.py lines 50–54 (existing per-user reset — adapt for org-level)
from datetime import datetime as _dt
today_month = _dt.now().strftime('%Y-%m')
if org.fair_use_reset_month != today_month:
    org.live_minutes_used = 0
    org.training_sessions_used = 0
    org.fair_use_reset_month = today_month
    db.commit()
```

### DSGVO Banner Fix Pattern (D-08 Bug 2)
```javascript
// Source: app.js lines 134–140 (CURRENT WRONG location — fires on first transcript)
// CORRECT: Move banner show to BEFORE getUserMedia call
// Find getUserMedia call site in app.js, then:
const dsgvoBanner = document.getElementById('dsgvoBanner');
if (dsgvoBanner && !dsgvoBanner._shown) {
    dsgvoBanner._shown = true;
    dsgvoBanner.classList.add('visible');
    setTimeout(() => dsgvoBanner.classList.remove('visible'), 6000);
}
// navigator.mediaDevices.getUserMedia(...) — AFTER banner
```

### Profile Wizard Trigger in Dashboard Route (D-13)
```python
# Source: routes/dashboard.py index() route — add after user load
# If onboarding is done but no profile exists, redirect to wizard
if user.onboarding_done:
    profile_count = db.query(Profile).filter_by(org_id=g.org.id).count()
    if profile_count == 0:
        return redirect(url_for('profiles.wizard_page'))  # GET route
```

### DB Migration for New Columns (D-02 + D-10)
```python
# Source: app.py lines 84–116 (_migrate() organisations block — extend)
# organisations table — add fair-use tracking columns:
('live_minutes_used',     'INTEGER DEFAULT 0'),
('training_sessions_used','INTEGER DEFAULT 0'),
('fair_use_reset_month',  'VARCHAR(7)'),

# users table — add dashboard_style column:
('dashboard_style', "VARCHAR(20) DEFAULT 'vollstandig'"),
```

### Rename Migration for salesnerve.db (D-15)
```python
# Source: app.py — add to _migrate() after column migrations
import os as _os
old_db = _os.path.join(_os.path.dirname(__file__), 'database', 'salesnerve.db')
new_db = _os.path.join(_os.path.dirname(__file__), 'database', 'nerve.db')
if _os.path.exists(old_db) and not _os.path.exists(new_db):
    _os.rename(old_db, new_db)
    print('[DB] Renamed salesnerve.db → nerve.db')
```

### Training Help Row Visibility (D-05 — verify, may already be correct)
```javascript
// Source: training.html JS initChat() line 539 — ALREADY CORRECT
const hilfeRow = document.getElementById('t-helpRow');
if (hilfeRow) hilfeRow.style.display = trainingModus === 'free' ? 'none' : '';
// This hides the entire help row (including button) in free mode. VERIFIED CORRECT.
```

### Penalty Value for Geführt Mode (Claude's Discretion)
```javascript
// Source: routes/training.py lines 314–317 (EXISTING implementation)
// penalty = min(hilfe_count * 5, 30)
// points = max(base_points - penalty, base_points // 2)
// Verdict: -5 points per hint, max -30 total, minimum half of base.
// This is REASONABLE — keep as-is (Claude's Discretion = no change needed)
```

---

## State of the Art

| Old Approach | Current Approach | Status |
|--------------|------------------|--------|
| Per-user pricing (starter/team/business at price_per_user) | Flat-rate individual plans (49/59/69€) | D-01 to implement |
| DSGVO banner on first transcript | DSGVO banner before getUserMedia | D-08 bug fix |
| Seed email andre@salesnerve.de | admin@nerve.local | D-15 (new installs only) |
| salesnerve.db database filename | nerve.db | D-15 + file rename migration |
| `dashboard_stil` free-text field | `dashboard_style` card selection (Fokus/Vollständig) | D-10 new column |

---

## Open Questions

1. **Script button root cause**
   - What we know: `initSkript()` is called with server-injected `active_phasen`. The button starts disabled. `toggleSkriptPanel()` exists and works.
   - What's unclear: Whether `active_phasen` is correctly populated at page load when a profile with phasen is active. Needs inspection of `app_routes.py` `live()` route to see what `active_phasen` is set to.
   - Recommendation: Planner should include a read of `routes/app_routes.py` live route as the first step of the script-button fix task.

2. **billing_email rename in existing DB**
   - What we know: `Organisation.billing_email` field contains `andre@salesnerve.de` for the seed org. D-15 changes the seed for NEW installs but doesn't specify a data migration for existing records.
   - What's unclear: Whether billing_email should be updated in `_data_migrate()` for existing installs.
   - Recommendation: Add `UPDATE organisations SET billing_email='admin@nerve.local' WHERE billing_email='andre@salesnerve.de'` to `_data_migrate()`, consistent with the org name migration already there.

3. **Toggle button "wrong position" specifics**
   - What we know: `.btn-view-toggle` is defined as `position:fixed;top:8px;right:16px` (app.html line 96). The element is rendered inside the profile-bar div (line 467).
   - What's unclear: What the "correct position" is — the decision says it's in the wrong location but doesn't specify where it should go.
   - Recommendation: Planner should ask developer to specify the intended position before making this change, or treat it as a CSS/DOM relocation judgment call.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python/Flask | All backend changes | Assumed available (existing app running) | 3.x | — |
| SQLite | DB migrations | Confirmed (salesnerve.db exists on disk) | — | — |
| Browser (for DSGVO/JS testing) | Live mode bug fixes | Assumed available | — | — |

All Phase 2 work is pure code changes to an existing running application. No new external services or tools needed.

---

## Sources

### Primary (HIGH confidence)
- `config.py` — PLANS dict current state verified (lines 19–24)
- `app.py` — PLANS dict in app (lines 121–155), seed functions (lines 285–447), migration (lines 38–118), `_data_migrate()` (lines 158–167)
- `routes/training.py` — full training flow, modus handling, scoring, penalty (lines 1–461)
- `routes/dashboard.py` — `_calculate_roi()` (line 265), PLANS import (line 429)
- `routes/profiles.py` — existing wizard POST (line 61), no GET route confirmed
- `routes/auth.py` — `login_required` decorator, onboarding redirect logic (lines 25–35)
- `database/models.py` — Organisation and User model columns verified
- `templates/app.html` — DSGVO banner HTML (line 502), kompakt-panel, metric-circles, sp-toggle-btn, btn-view-toggle
- `static/app.js` — DSGVO banner display at transcript event (line 134), toggleSkriptPanel, initSkript, selectModus, training mode JS
- `templates/training.html` — training mode selector, help button, live preview section
- `templates/onboarding.html` — placeholder "Max" (line 226), dashboard_stil textarea (line 279)
- `.planning/phases/02-product-fixes/02-UI-SPEC.md` — design tokens, component specs
- `database/salesnerve.db` — file confirmed present on disk (via directory listing)

### Secondary (MEDIUM confidence)
- CLAUDE.md — stack constraints, naming conventions, error handling patterns

---

## Metadata

**Confidence breakdown:**
- Pricing rewrite: HIGH — both PLANS dicts read directly; exact line numbers documented
- DSGVO bug: HIGH — bug location confirmed in app.js line 134; getUserMedia call site to verify in live route
- Training modes: HIGH — verified as already correct in initChat(); only verify step needed
- Profile wizard: HIGH — missing GET route confirmed; POST exists; template to create from scratch
- SalesNerve rename: HIGH — all 6 locations from D-15 verified; salesnerve.db file confirmed on disk
- Onboarding fixes: HIGH — placeholder "Max" at line 226 confirmed; dashboard_stil vs dashboard_style conflict documented
- Fair-use counters: HIGH — existing per-user pattern in training.py is the model to adapt

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable codebase, no external API dependencies in scope)
