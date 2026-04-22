# Phase 08: EWB-Qualität & Profil-Tiefe — Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 21 (9 new, 12 modified)
**Analogs found:** 20 / 21 (1 partial — Beispiel-Profil-Modal has no dialog precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `services/prompt_pipeline.py` (NEW) | service (shared utils) | request-response + DB-cached | `services/claude_service.py` lines 97-115 `_ACTIVE_PROMPT_CACHE` + `get_active_prompt_version` | role-match (extends existing caching pattern) |
| `services/ewb_pipeline.py` (NEW) | service (EWB-specific assembly) | request-response (prompt-assembly) | `services/claude_service.py` lines 258-394 `_build_system_prompt()` | exact (same role: assembles system prompt from Profile JSON) |
| `templates/_tooltip.html` (NEW partial) | template (Jinja macro) | request-response | No exact analog — closest is inline `ti()` JS-helper at `templates/profile_editor.html` line 625-627 | partial (no existing Jinja-macro partial pattern; use new macro file) |
| `templates/_beispiel_profil_modal.html` (NEW partial) | template (Jinja include) | request-response | No native-dialog precedent — closest is `consent-overlay` at `templates/app.html` line 698-712 (consent modal) | partial (adapt consent-overlay CSS+structure for read-only profile preview) |
| `tests/test_prompt_pipeline.py` (NEW) | test (unit) | pure-function testing | `tests/test_ft_seed.py` (minimal test with `db_session` fixture, seed-assert-pattern) | exact |
| `tests/test_ewb_pipeline.py` (NEW) | test (integration) | request-response | `tests/test_ft_write_hooks.py` (monkeypatch + fake-session + ls.state patches) | exact |
| `tests/test_branche_migration.py` (NEW) | test (unit) | data-transform | `tests/test_einwand_keyword_matcher.py` lines 1-60 (pure-function with fixture-dict list) | exact |
| `routes/admin_ewb.py` or extension to `routes/admin_dashboard.py` (NEW/MODIFY) | route (admin blueprint) | request-response | `routes/admin_dashboard.py` lines 1-75 (Blueprint+`@login_required`+`@superadmin_required`) | exact |
| `tools/ewb_rating_template.md` (optional) | doc/tool | file-I/O | — | no analog (optional; if built use `.md` convention as in `.planning/`) |
| `database/models.py` (MODIFY: ObjectionEvent + ConversationLog + PromptVersion) | ORM model | CRUD | lines 342-350 (`ObjectionEvent`), lines 231-283 (`ConversationLog`), lines 463-474 (`PromptVersion`) | exact (in-place edits) |
| `app.py _migrate()` (MODIFY) | config (inline migration) | DDL | lines 90-530 (`_migrate()` block pattern with try/except ADD COLUMN) | exact |
| `services/claude_service.py` (MODIFY) | service | request-response | lines 258-394 `_build_system_prompt()` + lines 633-661 `analysiere_mit_claude()` + lines 97-115 cache | exact (extend existing functions) |
| `services/training_service.py` (MODIFY read-only for D-46) | service | read-only (gap-analyse) | lines 499-619 `KUNDEN_PROMPT_TEMPLATE` + `build_customer_prompt` | exact (docs-only reading, no code change expected) |
| `templates/profile_editor.html` (MODIFY: 6 fields + tooltip 3-block) | template | request-response | lines 791-842 `addEinwand()`, lines 948-1007 `buildAndSubmit()`, lines 1082-1148 `init()/populate`, lines 119-141 tooltip-CSS+JS lines 625-627/629-657 | exact |
| `templates/session_detail.html` (MODIFY: 3-button rating in timeline) | template | request-response | lines 130-172 (Section 4 Einwand-Timeline with ObjectionEvent rows) | exact |
| `templates/app.html` (MODIFY: PreCall-Anrede-Overlay) | template | request-response | lines 671-685 `precall-panel` + lines 698-712 consent-overlay | exact |
| `static/pip-launcher.js` (MODIFY: Anrede-Wahl in step 3) | JS (state-machine) | request-response | lines 220-272 `renderStep3()` + `saveFormData()` | exact |
| `routes/profiles.py` (MODIFY: POST-handler) | route | request-response | lines 121-155 `bearbeiten()` POST-Handler (wholesale-replace pattern) | exact |
| `routes/app_routes.py` (MODIFY: session-start hook writes `anrede`) | route | request-response | lines 399-500 (session_start/end) + lines 450-462 (ObjectionEvent insert-loop) | exact |
| `static/nerve.css` (MODIFY: tooltip i-button ≥16px, modal styles) | CSS | — | `templates/profile_editor.html` lines 120-141 (current tooltip CSS to migrate into nerve.css) | role-match |
| `.env.example` (MODIFY) + `deploy/nerve.service` (MODIFY) | config | — | `.env.example` lines 1-25 (ENV-VAR-doc pattern) | exact |

## Pattern Assignments

### `services/prompt_pipeline.py` (service — shared utils, NEW)

**Analog:** `services/claude_service.py` lines 97-115 (caching pattern) + lines 118-196 (`_write_ft_assistant_event` — write-hook with DB-session lifecycle)

**Imports pattern** (follows `services/training_service.py` lines 1-7 and `services/einwand_keyword_matcher.py` lines 1-20):
```python
"""
services/prompt_pipeline.py
────────────────────────────────────────────────────────────────────
Shared Prompt-Pipeline-Utilities (Phase 08 + 08.5 reuse).

- build_profile_context(user_id, mode) → standardisierter Profil-Kontext-String
- resolve_prompt_version(module, user_id) → A/B-Routing (ENV-Override First, dann user_id % N)
- log_pipeline_event(event_type, module, data) → modul-agnostisches FT-Logging

Side-effect-free beim Import: keine I/O, keine DB-Zugriffe.
"""
from __future__ import annotations
import os
import time
from database.db import SessionLocal
from database.models import PromptVersion
```

**Module-level cache pattern** (from `claude_service.py` line 97 — EXTEND key from `module` → `(module, user_id)`):
```python
# services/claude_service.py line 97
_ACTIVE_PROMPT_CACHE: dict = {}

# NEW in prompt_pipeline.py — SECOND cache with (module, user_id) key:
_RESOLVER_CACHE: dict = {}    # {(module, user_id): version_string}
_VARIANTS_CACHE: dict = {}    # {module: [version_string, ...]}
```

**Core Router-Function pattern** (adapts `get_active_prompt_version` at lines 100-115):
```python
# services/claude_service.py line 100-115 — EXISTING pattern to adapt:
def get_active_prompt_version(module: str) -> str:
    if module in _ACTIVE_PROMPT_CACHE:
        return _ACTIVE_PROMPT_CACHE[module]
    try:
        from database.db import SessionLocal
        from database.models import PromptVersion
        db = SessionLocal()
        try:
            pv = db.query(PromptVersion).filter_by(module=module, is_active=True).first()
            version = pv.version if pv else 'unknown'
        finally:
            db.close()
    except Exception:
        version = 'unknown'
    _ACTIVE_PROMPT_CACHE[module] = version
    return version
```

**Adapt this pattern for `resolve_prompt_version(module, user_id)`:**
- Keep the `SessionLocal()` + try/finally `db.close()` lifecycle (ZENTRAL im Repo).
- Replace single-key cache with `(module, user_id)` tuple key.
- Add ENV-First-Check: `os.environ.get(f'PROMPT_{module.upper()}_VERSION_OVERRIDE')`.
- Order active variants deterministically: `.order_by(PromptVersion.version).all()`.
- Use `user_id % len(variants)` for deterministic routing.

**Logging-Prefix convention** (from CLAUDE.md line 155 + `claude_service.py` line 196):
```python
# claude_service.py line 196:
print(f"[FT] assistant_event write failed (module={module}): {e}")

# New in prompt_pipeline.py:
print(f"[Pipeline] variants loaded module={module} count={len(variants)}")
print(f"[Pipeline] env-override module={module} version={env_override}")
```

**Error handling pattern** (from `claude_service.py` line 118-196 `_write_ft_assistant_event`):
- `MUST NOT raise` — live-loop writes swallow all errors with `except Exception as e:` + print log.
- For `resolve_prompt_version`: fail-open to `'unknown'` string on DB error, never block.

**Test invalidation helper** (required for pytest monkeypatch — see `tests/test_ft_write_hooks.py` line 74: `monkeypatch.setattr(cs, '_ACTIVE_PROMPT_CACHE', {})`):
```python
def invalidate_resolver_cache():
    """Call after prompt_versions table changes. NOT called in live-loop."""
    _RESOLVER_CACHE.clear()
    _VARIANTS_CACHE.clear()
```

---

### `services/ewb_pipeline.py` (service — EWB-specific assembly, NEW)

**Analog:** `services/claude_service.py` lines 258-394 `_build_system_prompt()` (complete precedent for Profile-JSON → Prompt-String assembly)

**Imports pattern** (copy from `claude_service.py` lines 1-7):
```python
"""
services/ewb_pipeline.py
────────────────────────────────────────────────────────────────────
EWB-Module-spezifische Prompt-Assembly (Phase 08).

- build_ewb_prompt(profile_data, anrede, version) → kompletter System-Prompt-String
- parse_ewb_output(text) → {gegenargument_1, gegenargument_2, baustein_struktur?}

Nutzt services.prompt_pipeline fuer Shared-Utils.
"""
from __future__ import annotations
import json
from services.prompt_pipeline import build_profile_context, resolve_prompt_version, log_pipeline_event
```

**Core Assembly Pattern** (from `_build_system_prompt()` at `claude_service.py` lines 258-394):
```python
# services/claude_service.py lines 258-394 — assembly pattern to follow:
def _build_system_prompt() -> str:
    import services.live_session as ls
    _, pdata = ls.get_active_profile()
    if not pdata:
        return SYSTEM_PROMPT_BASE
    basis      = pdata.get('basis', {})
    zielgruppe = pdata.get('zielgruppe', {})
    # ... (read all sub-dicts)
    lines = [SYSTEM_PROMPT_BASE, '\n--- AKTIVES VERKAUFSPROFIL ---']
    if basis.get('unternehmen'):
        lines.append(f'Unternehmen: {basis["unternehmen"]}')
    # ... (append conditionally per field)
    if ki.get('ansprache'):
        lines.append(f'\nKundenansprache: {ki["ansprache"]} (immer einhalten)')
    # ...
    return '\n'.join(lines)
```

**Key gaps to close per D-46 / D-11 / D-15:**
- **Add lines for `branche` Enum** (NEW — currently NOT read by `_build_system_prompt()`, see RESEARCH Focus Area 1):
  ```python
  if pdata.get('branche'):  # Legacy column from Profile.branche
      lines.append(f'Branche: {pdata["branche"]}')
  if basis.get('branche_kontext'):
      lines.append(f'Branchen-Kontext: {basis["branche_kontext"]}')
  ```
- **Add `eigene_formulierungen` + `beweise`:**
  ```python
  if basis.get('eigene_formulierungen'):
      lines.append('\nEigene Formulierungen (User-Stil imitieren, nicht generisches Vertriebs-Sprech):')
      for f in basis['eigene_formulierungen']:
          lines.append(f'- "{f}"')
  if basis.get('beweise'):
      lines.append('\nBeweise (in Baustein "Beweis" einsetzen):')
      for b in basis['beweise']:
          lines.append(f'- {b}')
  ```
- **D-15 harter Anrede-Constraint** (replace line 366-367):
  ```python
  # ALT (line 366-367):
  if ki.get('ansprache'):
      lines.append(f'\nKundenansprache: {ki["ansprache"]} (immer einhalten)')
  # NEU (D-15 wortwörtlich):
  import services.live_session as ls
  anrede_override = ls.state.get('session_anrede')
  anrede = anrede_override or ki.get('ansprache') or 'Sie'
  lines.append(f'\nAnrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. '
               f'Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.')
  ```

**Baustein-Struktur (v2-Prompt):** Wird als NEUER `SYSTEM_PROMPT_BASE`-Header in `prompt_versions`-Tabelle gespeichert (D-26), NICHT hardcoded. `build_ewb_prompt()` lädt Text aus DB via `resolve_prompt_version('ewb', user_id)`.

**Logging-Prefix:** `[EWB]` (analog zu `[FT]`, `[Pipeline]`, `[POLISH-xx]`):
```python
print(f"[EWB] v{version} assembled user_id={user_id} len={len(prompt_text)}")
```

---

### `templates/_tooltip.html` (Jinja macro partial — NEW)

**Analog:** `templates/profile_editor.html` lines 625-627 (inline JS `ti()` helper + data-tip attribute pattern). No Jinja-macro-partial precedent in templates/.

**Current inline pattern** (lines 625-627):
```javascript
function ti(text){
  return `<i class="tip-icon" data-tip="${esc(text)}">?</i>`;
}
// Usage line 731:
<label class="fl">Situation ${ti('In welcher konkreten Situation befindet sich der Kunde?')}</label>
```

**Current tooltip display-JS** (lines 629-657):
```javascript
document.addEventListener('mouseover', e=>{
    const icon=e.target.closest('.tip-icon');
    if(!icon){ tip.style.display='none'; return; }
    inner.textContent=icon.dataset.tip||'';  // ← textContent, not innerHTML
    // ... positioning logic ...
});
```

**3-Block-Upgrade pattern** (D-16): Extend `ti()` JS-helper OR create Jinja macro:
```jinja
{# templates/_tooltip.html — neue Jinja-Macro-Partial #}
{% macro tip3(was_rein, beispiel, nicht_verwechseln) -%}
<i class="tip-icon"
   data-tip-was="{{ was_rein|e }}"
   data-tip-bsp="{{ beispiel|e }}"
   data-tip-nvm="{{ nicht_verwechseln|e }}"
   tabindex="0"
   role="button"
   aria-describedby="tip-content">?</i>
{%- endmacro %}
```

**Import-Usage-Pattern** (Jinja `import` analog zu anderen Templates):
```jinja
{# In profile_editor.html (oben): #}
{% import '_tooltip.html' as tooltip %}

{# Dann: #}
<label>Eigene Formulierungen {{ tooltip.tip3(
  'Sätze, die du im Call wortwörtlich sagst …',
  'Darf ich fragen, was Sie aktuell einsetzen? …',
  'Stil (ton) / Gegenargumente / Spezielle Anweisungen (zusatz)'
) }}</label>
```

**CSS-Upgrade in `nerve.css`** (move from `profile_editor.html` lines 120-128, fix ≥16px):
```css
/* ALT (profile_editor.html line 120-128): */
.tip-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; min-width: 14px;  /* ← unter D-18 Spec */
  ...
  font-size: 9px; font-weight: 700; cursor: help;
}
/* NEU (nerve.css, D-18 ≥16×16px): */
.tip-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; min-width: 16px;
  font-size: 11px; font-weight: 700; cursor: help;
  /* Rest identisch */
}
```

**Display-JS-Upgrade** for 3-block format (extend lines 629-657):
```javascript
inner.innerHTML = '';  // reset
const sections = [
  { label: 'Was rein soll', value: icon.dataset.tipWas },
  { label: 'Beispiel',      value: icon.dataset.tipBsp },
  { label: 'Nicht verwechseln mit', value: icon.dataset.tipNvm },
];
sections.forEach(s => {
  if (!s.value) return;
  const block = document.createElement('div');
  block.className = 'tip-block';
  block.innerHTML = `<strong>${s.label}:</strong> ${esc(s.value)}`;
  inner.appendChild(block);
});
```

**CRITICAL Umlaut-Regel** (CLAUDE.md lines 103-128): Tooltip-Content ist User-facing → **echte Umlaute** ä/ö/ü/ß. Aber `data-tip-*`-Attribut-Namen (HTML-IDs) sind **ASCII** (`data-tip-nvm` nicht `data-tip-nicht-verwechseln`).

---

### `templates/_beispiel_profil_modal.html` (Modal partial — NEW)

**Analog:** `templates/app.html` lines 698-712 (`consent-overlay` / `consent-box` modal pattern)

**Consent-Modal-Pattern** (lines 698-712):
```html
<!-- templates/app.html line 698-712 — modal pattern to adapt: -->
<div class="consent-overlay" id="consentOverlay" onclick="if(event.target===this)rejectConsent()">
  <div class="consent-box">
    <div class="consent-title">Einwilligung des Gesprächspartners</div>
    <div class="consent-pflicht-label">Pflicht — laut vorlesen</div>
    <div class="consent-script">„Ist es okay ..."</div>
    <div class="consent-actions">
      <button class="consent-btn consent-btn-reject" onclick="rejectConsent()">Abgelehnt</button>
      <button class="consent-btn consent-btn-accept" onclick="acceptConsent()">Stattgegeben</button>
    </div>
  </div>
</div>
```

**Adapt for Read-Only Profil-Beispiel-Modal:**
```html
<!-- templates/_beispiel_profil_modal.html (NEU, in profile_editor.html included): -->
<div class="beispiel-overlay" id="beispielOverlay" style="display:none" onclick="if(event.target===this)closeBeispiel()">
  <div class="beispiel-box">
    <div class="beispiel-header">
      <div class="beispiel-title">Beispiel-Profil — "Anna S. (Firma XY)"</div>
      <button class="beispiel-close" onclick="closeBeispiel()" aria-label="Schliessen">&times;</button>
    </div>
    <div class="beispiel-content">
      {# CONTENT NEU ERFINDEN (Open Question 3): nicht NERVE-Demo, nicht André-Ton.
         Fiktive Platzhalter: "Anna S.", "Firma XY", "Branche Maschinenbau".
         Alle 12 Sektionen analog profile_editor.html (Basis, Zielgruppe, Schmerzen, ...). #}
      <section><h3>Basis</h3>
        <p><strong>Unternehmen:</strong> Firma XY</p>
        <p><strong>Produkt:</strong> ...</p>
        ...
      </section>
      ...
    </div>
  </div>
</div>
```

**Link-Trigger in `profile_editor.html`** (D-19 wortwörtlich):
```html
<a href="#" onclick="document.getElementById('beispielOverlay').style.display='flex';return false"
   class="beispiel-link">Sieh dir ein ausgefülltes Beispiel an</a>
```

**CSS pattern** (copy from `consent-overlay` styles — search in nerve.css for `.consent-overlay` first):
- Position: `fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 9998; display: flex; align-items: center; justify-content: center`.
- Box: `background: #FFFFFF; max-width: 720px; max-height: 85vh; overflow-y: auto; border-radius: 12px; padding: 24px`.

**Jinja include pattern** (kein macro, einfacher include):
```jinja
{# profile_editor.html — oberhalb des content-blocks: #}
{% include '_beispiel_profil_modal.html' %}
```

---

### `tests/test_prompt_pipeline.py` (unit tests — NEW)

**Analog:** `tests/test_ft_seed.py` (minimal structure) + `tests/test_ft_write_hooks.py` (monkeypatch pattern)

**Imports pattern** (from `test_ft_seed.py` lines 1-3):
```python
from database.models import PromptVersion
from app import _seed_prompt_versions
```

**Test-Fixture pattern** (uses `db_session` fixture from `tests/conftest.py` lines 41-51):
```python
# tests/conftest.py line 41-51 — existing fixture:
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

**Monkeypatch-cache pattern** (from `test_ft_write_hooks.py` line 74):
```python
# BEFORE any test that exercises the resolver:
monkeypatch.setattr(cs, '_ACTIVE_PROMPT_CACHE', {})
# NEW analog in prompt_pipeline tests:
import services.prompt_pipeline as pp
monkeypatch.setattr(pp, '_RESOLVER_CACHE', {})
monkeypatch.setattr(pp, '_VARIANTS_CACHE', {})
```

**Seed-PromptVersion helper** (from `test_ft_write_hooks.py` lines 47-60):
```python
def _seed_fixtures(db_session, mode='cold_call'):
    from database.models import Organisation, User, FtCallSession, PromptVersion
    org = Organisation(name='T', plan='starter')
    db_session.add(org); db_session.flush()
    u = User(org_id=org.id, email='t@t.de', passwort_hash='x', market='dach', language='de')
    db_session.add(u); db_session.flush()
    db_session.add(PromptVersion(
        module='assistant_live', version='v1.0.0',
        prompt_text='x' * 40, is_active=True,
    ))
    db_session.commit()
    return org, u
```

**Assertions style** (from `test_ft_seed.py` lines 15-32):
```python
def test_prompt_seed(db_session):
    _seed_prompt_versions(db_session)
    for module in EXPECTED_MODULES:
        row = db_session.query(PromptVersion).filter_by(module=module, is_active=True).first()
        assert row is not None, f"missing seeded module: {module}"
        assert row.version == "v1.0.0"
```

**New tests to write per D-43:**
- `test_env_override_first_check` (set `os.environ['PROMPT_EWB_VERSION_OVERRIDE']='x'`, assert resolver returns 'x' ignoring DB)
- `test_deterministic_routing` (seed 2 variants, assert `user_id=1 % 2 = v-b`, `user_id=2 % 2 = v-a`)
- `test_cache_per_user` (seed 2 variants, assert both user_ids get cached at correct keys `(module, user_id)`)
- `test_no_variants_returns_unknown` (empty `prompt_versions`, assert returns `'unknown'`)
- `test_build_profile_context_assembles_all_fields` (seed Profile mit vollen Feldern, assert substrings)

---

### `tests/test_ewb_pipeline.py` (integration tests — NEW)

**Analog:** `tests/test_ft_write_hooks.py` (complete integration-test pattern with fake-session wrapper + ls.state patches)

**Fake-Session wrapper** (from `test_ft_write_hooks.py` lines 33-44):
```python
class _FakeSession:
    """Adapter so SessionLocal() returns the pytest db_session without closing it."""
    def __init__(self, real):
        self._real = real
    def add(self, *a, **k):
        return self._real.add(*a, **k)
    def commit(self):
        return self._real.commit()
    def close(self):
        pass
    def query(self, *a, **k):
        return self._real.query(*a, **k)
```

**ls.state patch** (from lines 10-24):
```python
def _setup_ls_state(**overrides):
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.update({
            'ft_session_id': overrides.get('ft_session_id'),
            'user_id':       overrides.get('user_id'),
            'mode':          overrides.get('mode', 'cold_call'),
            'session_anrede': overrides.get('session_anrede'),   # NEU Phase 08
            ...
        })
    return ls
```

**Integration assertions:** End-to-end flow `build_ewb_prompt(profile, anrede='Du')` → contains substring `'Anrede: Du'` + `'Wechsle NIEMALS'`; test Profile-Override-Chain (session_anrede > ki.ansprache > 'Sie').

---

### `tests/test_branche_migration.py` (unit — NEW)

**Analog:** `tests/test_einwand_keyword_matcher.py` lines 1-60 (pure-function test with dict-fixtures)

**Test-data-style** (from `test_einwand_keyword_matcher.py` lines 49-60):
```python
PROFIL_EINWAENDE = [
    _einwand('Preis',       'Unser ROI liegt bei 3x ...'),
    _einwand('Zeit',        'Das Setup dauert nur 15 Minuten.'),
    ...
]
```

**Heuristik-Mapping-Tests** (one test per Enum + edge-cases from RESEARCH Focus Area 7):
```python
def test_heuristic_saas_b2b():
    assert _map_branche_to_enum("SaaS-Plattform B2B") == 'saas_b2b'
    assert _map_branche_to_enum("cloud software")     == 'saas_b2b'

def test_heuristic_maschinenbau_umlauts():
    assert _map_branche_to_enum("Werkzeugmaschinen")  == 'maschinenbau'
    assert _map_branche_to_enum("Anlagenbau")         == 'maschinenbau'

def test_fallback_sonstiges_preserves_originaltext():
    daten_in = {'basis': {}}
    enum_val, daten_out = _migrate_branche("Exotisches Feld", daten_in)
    assert enum_val == 'sonstiges'
    assert daten_out['basis']['branche_kontext'] == "Exotisches Feld"

def test_success_reset_cutoff(db_session):
    """D-02: Alt-Daten vor cutoff auf NULL, neue Daten bleiben."""
    # Seed ObjectionEvent mit created_at VOR + NACH cutoff
    # Assert: Nur Vor-Cutoff-Rows haben success=NULL nach Migration
    ...
```

---

### `routes/admin_ewb.py` or `routes/admin_dashboard.py` extension (NEW/MODIFY)

**Analog:** `routes/admin_dashboard.py` lines 1-75 (Blueprint + decorators + period-parsing)

**Blueprint-Header** (copy from `admin_dashboard.py` lines 1-19):
```python
"""Phase 08 — EWB-Quality Admin Card."""
from __future__ import annotations
from flask import Blueprint, render_template, request, jsonify, abort, g
from routes.auth import login_required
from services.auth_decorators import superadmin_required
from database.db import get_session

admin_ewb_bp = Blueprint(
    'admin_ewb', __name__,
    url_prefix='/admin/ewb-quality',
    template_folder='../templates/admin',
)
```

**Route-Handler pattern** (from `admin_dashboard.py` lines 61-74):
```python
@admin_ewb_bp.route('/')
@login_required
@superadmin_required
def index():
    db = get_session()
    try:
        # A/B-Auswertungs-SQL aus RESEARCH Focus Area 3:
        rows = db.execute(text("""
            SELECT ftoe.prompt_version,
                   COUNT(*) AS n,
                   AVG(CASE WHEN oe.success = 1 THEN 1.0 ELSE 0.0 END) AS success_rate
            FROM ft_objection_events ftoe
            JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
            JOIN objection_events oe
                ON oe.conversation_log_id = fcs.conversation_log_id
               AND oe.einwand_typ = ftoe.objection_type
            WHERE oe.success IS NOT NULL
            GROUP BY ftoe.prompt_version
        """)).fetchall()
        return render_template('admin/ewb_quality.html', rows=rows)
    finally:
        db.close()
```

**Blueprint registration** (in `app.py` nach existing blueprints):
```python
# Muster aus app.py (search for register_blueprint):
from routes.admin_dashboard import admin_dashboard_bp
app.register_blueprint(admin_dashboard_bp)
# NEU:
from routes.admin_ewb import admin_ewb_bp
app.register_blueprint(admin_ewb_bp)
```

---

### `database/models.py` (MODIFY — 3 models affected)

**Analog:** Same file, existing patterns.

**ObjectionEvent (D-01, line 349):**
```python
# ALT (line 349):
success             = Column(Boolean, default=False, nullable=False)
# NEU:
success             = Column(Boolean, default=None, nullable=True)  # Phase 08 D-01: 3-state
```

**ConversationLog (D-14, after line 283):**
```python
# NEW Column (anhängen nach line 283):
# Phase 08 D-14: PreCall-Anrede-Override (Du/Sie pro Session)
anrede                   = Column(String(10), nullable=True)  # Fallback: Profile.daten.ki.ansprache
```

**PromptVersion (D-26, after line 473 `is_active`):**
```python
# NEW Column:
is_default  = Column(Boolean, default=False, nullable=False)  # Phase 08 D-26: A/B-Default für single-lookup
```

**German domain conventions** (CLAUDE.md lines 85, 122): DB-Spalten **ASCII** (`anrede` nicht `Anrede`, `is_default` nicht `ist_default`). Werte bleiben User-facing (`"Du"`, `"Sie"` mit echten Umlauten falls nötig in Display).

---

### `app.py _migrate()` (MODIFY — 4 migration blocks)

**Analog:** Same file, lines 90-530 (inline migration pattern).

**Existing ADD COLUMN pattern** (lines 94-152, users-block):
```python
for col, typedef in [
    ('market',   "VARCHAR(10) NOT NULL DEFAULT 'dach'"),
    ('language', "VARCHAR(10) NOT NULL DEFAULT 'de'"),
]:
    try:
        conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {typedef}'))
        conn.commit()
        print(f"[DB] Migration: added users.{col}")
    except Exception:
        pass
```

**New migrations for Phase 08:**

**Block 1 — `conversation_logs.anrede`** (D-14, identisch zur existing Pattern-Line 212-226):
```python
# ── conversation_logs Phase 08 D-14 ─────────────────────────────
for col, typedef in [
    ('anrede', 'VARCHAR(10)'),  # Phase 08: PreCall-Override Du/Sie
]:
    try:
        conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
        conn.commit()
        print(f"[DB] Migration: added conversation_logs.{col}")
    except Exception:
        pass
```

**Block 2 — `prompt_versions.is_default`** (D-26, same pattern):
```python
try:
    conn.execute(text("ALTER TABLE prompt_versions ADD COLUMN is_default BOOLEAN DEFAULT 0"))
    conn.execute(text("UPDATE prompt_versions SET is_default = 1 WHERE is_active = 1"))  # backfill
    conn.commit()
    print("[DB] Migration v08: prompt_versions.is_default added + backfilled")
except Exception:
    pass
```

**Block 3 — `objection_events.success` Nullable (Table-Rebuild)** (D-01, SQLite-Limitation):

See RESEARCH Focus Area 2 for complete SQL. **No analog for Table-Rebuild** in repo — this is the FIRST time. Copy exact snippet from 08-RESEARCH.md lines 870-907.

**CRITICAL Safeguard** (Risk 1 in RESEARCH): **Pre-migration DB-Backup** via file-copy BEFORE the UPDATE:
```python
# Before UPDATE:
import shutil
db_path = 'database/nerve.db'
backup_path = f'{db_path}.bak_pre_v08_01'
if not os.path.exists(backup_path):
    shutil.copy(db_path, backup_path)
    print(f"[DB] Phase 08 backup: {backup_path}")
```

**Block 4 — Alt-Daten-Reset für POLISH-38.1** (D-02, Destruktiv):
```python
# Cutoff = POLISH-38.1 Deploy-Timestamp (Open Question 1: genauer Git-Commit-Timestamp)
# Konservativ: 2026-04-22 00:00:00 UTC
conn.execute(text("""
    UPDATE objection_events SET success = NULL
    WHERE created_at < '2026-04-22 00:00:00'
"""))
conn.commit()
print("[DB] Migration v08_01: Reset POLISH-38.1 success-Werte auf NULL")
# Marker in audit_log:
from database.models import AuditLog
# ...
```

**Block 5 — Seed v2-Prompt `prompt_versions`** (analog `_seed_prompt_versions` at app.py lines 601-644):
```python
def _seed_ewb_v2(db=None):
    from database.db import SessionLocal
    from database.models import PromptVersion
    # v2-modular prompt-text MUSS IN PLAN definiert werden (aus Vault-Template)
    V2_PROMPT_TEXT = """[Baustein-Struktur v2 ... aus Vault]"""
    V1_PROMPT_TEXT = """[v1-Legacy ... copy of SYSTEM_PROMPT_BASE mit EWB-only subset]"""
    owns = db is None
    if owns: db = SessionLocal()
    try:
        for version, ptext, is_default in [
            ('v1-legacy', V1_PROMPT_TEXT, True),
            ('v2-modular', V2_PROMPT_TEXT, False),
        ]:
            exists = db.query(PromptVersion).filter_by(module='ewb', version=version).first()
            if exists: continue
            db.add(PromptVersion(
                module='ewb', version=version, prompt_text=ptext,
                is_active=True, is_default=is_default,
                changelog=f'Phase 08 Seed ({version})',
            ))
        db.commit()
    finally:
        if owns: db.close()
```

---

### `services/claude_service.py` (MODIFY — 3 integration points)

**Analog:** Same file.

**Point 1 — EWB-Prompt-Router-Integration** (in `analysiere_mit_claude` at lines 633-661):
```python
# ALT (lines 639-644):
msg = claude_client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=400,
    system=_build_system_prompt(),  # ← ersetzen
    messages=[{"role": "user", "content": user_msg}]
)
# NEU:
from services.prompt_pipeline import resolve_prompt_version
from services.ewb_pipeline import build_ewb_prompt
import services.live_session as ls
user_id = ls.state.get('user_id') or 0
ewb_version = resolve_prompt_version('ewb', user_id)
system_prompt = build_ewb_prompt(profile_data=_get_profile_data(), version=ewb_version)
msg = claude_client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=400,
    system=system_prompt,
    messages=[{"role": "user", "content": user_msg}]
)
```

**Point 2 — Cache-Key-Fix** (RESEARCH Pitfall 3): The legacy `_ACTIVE_PROMPT_CACHE` at line 97 stays for the 4 other modules (`assistant_live`, etc.), but the NEW resolver in `prompt_pipeline.py` has per-user cache. Don't delete line 97 — just don't use it for 'ewb'.

**Point 3 — Streaming-Variant (line 664-744):** Same pattern as Point 1. Inside `analysiere_mit_claude_streaming`, replace `system=_build_system_prompt()` at line 691 with `system=build_ewb_prompt(...)`.

---

### `templates/profile_editor.html` (MODIFY — 6 fields + tooltip upgrade)

**Analog:** Same file, multiple sections.

**Pattern for NEW Textarea-Field** (copy from line 731-736 `addSchmerz` situation-field):
```html
<!-- profile_editor.html line 731 (EXISTING pattern to copy): -->
<div class="fg">
  <label class="fl">Situation ${ti('In welcher konkreten Situation befindet sich der Kunde?')}</label>
  <textarea class="fta" data-sp="situation" style="min-height:52px"
            placeholder="Konkrete Situation des Kunden …">${esc(d.situation)}</textarea>
</div>

<!-- NEU: eigene_formulierungen, beweise (D-07, D-08) — analog in basis-Sektion: -->
<div class="fg">
  <label class="fl">Eigene Formulierungen {{ tooltip.tip3(
    'Sätze die du im Call wortwörtlich sagst — Claude imitiert deinen Stil statt generisches Vertriebs-Sprech.',
    'Darf ich fragen, was Sie aktuell einsetzen? / Was stört Sie da am meisten?',
    'Stil (ton) / Gegenargumente (einwaende) / Spezielle Anweisungen (zusatz)'
  ) }}</label>
  <textarea class="fta" id="vi_eigene_formulierungen" style="min-height:80px"
            placeholder="Eine Formulierung pro Zeile …"></textarea>
</div>
```

**Pattern for NEW Select-Field** (copy from lines 806-811 `ew-int`-Select):
```html
<!-- profile_editor.html line 806 (EXISTING pattern): -->
<div class="fg" style="margin:0">
  <label class="fl">Intensität</label>
  <select class="fs" data-ew="int">
    <option value="mittel" ${(d.intensitaet||'mittel')==='mittel'?'selected':''}>Mittel</option>
    <option value="hoch" ${d.intensitaet==='hoch'?'selected':''}>Hoch</option>
  </select>
</div>

<!-- NEU: branche Enum-Select (D-09): -->
<div class="fg">
  <label class="fl">Branche {{ tooltip.tip3(
    'Die Haupt-Branche in der du verkaufst.',
    'SaaS-B2B, Maschinenbau, Versicherung, Finanzprodukte, Immobilien, Coaching, Beratung, Sonstiges',
    'Branchen-Kontext (tiefer Pain-Points) / Unternehmen (eigenes)'
  ) }}</label>
  <select class="fs" id="vi_branche_select">
    <option value="">-- Bitte wählen --</option>
    <option value="saas_b2b">SaaS B2B</option>
    <option value="maschinenbau">Maschinenbau</option>
    <option value="versicherung">Versicherung</option>
    <option value="finanzprodukte">Finanzprodukte</option>
    <option value="immobilien">Immobilien</option>
    <option value="coaching">Coaching</option>
    <option value="beratung">Beratung</option>
    <option value="sonstiges">Sonstiges</option>
  </select>
</div>
```

**JS `buildAndSubmit()` Pattern** (copy + extend lines 948-1007):
```javascript
// profile_editor.html line 954-961 (EXISTING pattern):
const daten={
    basis:{
      unternehmen:document.getElementById('vi_unternehmen').value.trim(),
      produktbeschreibung:document.getElementById('vi_produkt').value.trim(),
      preismodell:document.getElementById('vi_preis').value.trim(),
      usps:getTags('usps-tags'),
      konsequenz:document.getElementById('vi_konsequenz').value.trim(),
    },
    // ... weitere Sektionen ...
};

// NEU: 3 Felder in basis + branche_kontext einreihen (D-07/D-08/D-11):
basis: {
  ...existing...,
  eigene_formulierungen:document.getElementById('vi_eigene_formulierungen').value
      .split('\n').map(s=>s.trim()).filter(Boolean),
  beweise:document.getElementById('vi_beweise').value
      .split('\n').map(s=>s.trim()).filter(Boolean),
  branche_kontext:document.getElementById('vi_branche_kontext').value.trim(),
},
```

**JS `ton`-Select mit Flex-Escape** (D-10 — neue Logic):
```javascript
// Im buildAndSubmit() ki-Block (line 997-1003):
ki:{
  ton: (function(){
    const sel = document.getElementById('vi_ton_select').value;
    if (sel === 'eigener_stil') {
      return document.getElementById('vi_ton_flex').value.trim();  // Flex-Escape
    }
    return sel || 'Direkt/Klartext';  // Default
  })(),
  ...
}
```

**JS Populate-Handler Pattern** (copy + extend lines 1084-1148):
```javascript
// ALT (line 1087):
setVal('vi_produkt',b.produktbeschreibung);
// NEU (in init() nach setVal-Block):
setVal('vi_eigene_formulierungen', (b.eigene_formulierungen||[]).join('\n'));
setVal('vi_beweise', (b.beweise||[]).join('\n'));
setVal('vi_branche_kontext', b.branche_kontext || '');

// branche Select:
const brancheSelect = document.getElementById('vi_branche_select');
if (brancheSelect && DATEN.branche) {
  brancheSelect.value = DATEN.branche;  // Profile.branche is top-level, NOT in daten.basis
}

// ton Select + Flex:
const tonSelect = document.getElementById('vi_ton_select');
const tonFlex = document.getElementById('vi_ton_flex');
const KNOWN_TONS = ['Direkt/Klartext', 'Beratend/Sanft', 'Enthusiastisch/Begeistert', 'Analytisch/Zahlenorientiert'];
const currentTon = (DATEN.ki||{}).ton || '';
if (KNOWN_TONS.includes(currentTon)) {
  tonSelect.value = currentTon;
  tonFlex.style.display = 'none';
} else if (currentTon) {
  tonSelect.value = 'eigener_stil';
  tonFlex.value = currentTon;
  tonFlex.style.display = 'block';
}
```

**CRITICAL — Pitfall 1 from RESEARCH:** ALLE NEUEN FELDER an **3 Stellen** einbauen: HTML-Form + `buildAndSubmit()` + Populate-Handler. Sonst gehen sie beim zweiten Save verloren (wholesale-JSON-replace-Bug).

**zusatz-Label (D-12, nur Template-Label):** In der `ki`-Sektion (search `vi_zusatz` in profile_editor.html):
```html
<!-- ALT: -->
<label class="fl">Zusatz-Anweisungen an NERVE</label>
<!-- NEU (D-12, DB-Key bleibt zusatz): -->
<label class="fl">Spezielle Anweisungen an NERVE</label>
```

---

### `templates/session_detail.html` (MODIFY — Rating-UI im Timeline)

**Analog:** Same file, lines 130-172 (Einwand-Timeline section).

**Current static badge** (lines 140-149):
```html
<!-- session_detail.html line 140-149 — EXISTING pattern: -->
<li class="n-session-detail-timeline-row {% if not ev.success %}n-session-detail-timeline-row--danger{% endif %}">
  <span class="n-label">#{{ loop.index }}</span>
  <div>
    <div class="n-session-detail-timeline-typ">{{ ev.einwand_typ }}</div>
    {% if ev.option_gewaehlt %}<div class="n-session-detail-timeline-option">{{ ev.option_gewaehlt }}</div>{% endif %}
  </div>
  <div class="n-badge {% if ev.success %}n-badge-success{% else %}n-badge-danger{% endif %}">
    {% if ev.success %}Erfolgreich{% else %}Nicht behandelt{% endif %}
  </div>
</li>
```

**REPLACE with 3-Button-Rating** (D-03, D-04 — see RESEARCH Focus Area 11 for complete HTML):
```html
<li class="n-session-detail-timeline-row" data-event-id="{{ ev.id }}">
    <span class="n-label">#{{ loop.index }}</span>
    <div>
        <div class="n-session-detail-timeline-typ">{{ ev.einwand_typ }}</div>
        {% if ev.option_gewaehlt %}<div class="n-session-detail-timeline-option">{{ ev.option_gewaehlt }}</div>{% endif %}
    </div>
    {# D-04: 3-Button Rating — Klick speichert sofort (kein Submit) #}
    <div class="n-ewb-rating-group" data-event-id="{{ ev.id }}">
        <button class="n-ewb-btn {% if ev.success == True %}n-ewb-btn--active{% endif %}"
                data-value="true" onclick="rateEwb({{ ev.id }}, true, this)">Erfolg</button>
        <button class="n-ewb-btn {% if ev.success == False %}n-ewb-btn--active{% endif %}"
                data-value="false" onclick="rateEwb({{ ev.id }}, false, this)">Kein Erfolg</button>
        <button class="n-ewb-btn {% if ev.success is none %}n-ewb-btn--active{% endif %}"
                data-value="null" onclick="rateEwb({{ ev.id }}, null, this)">Überspringen</button>
    </div>
</li>
```

**ADD Benefit-Framing above Section 4** (D-03 WORTWÖRTLICH — kein Paraphrasieren!):
```html
<!-- Insert BEFORE line 135 (before n-session-detail-card h2): -->
<div class="n-session-detail-info">
  <strong>Hilf uns, dir zu helfen.</strong>
  Wie empfandest du die Einwandbehandlung — welcher der folgenden EWBs hatte Erfolg?
  Basierend auf deinen Antworten kann NERVE dir in Zukunft besser bei der EWB helfen.
</div>
```

**JS-Handler pattern** (add inline or in new `<script>` block at bottom):
```javascript
// Standard fetch-POST pattern (analog zu crudList in profile_editor.html line 1030-1046):
async function rateEwb(eventId, value, btn) {
  try {
    const res = await fetch(`/api/ewb/${eventId}/rate`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({success: value})
    });
    if (!res.ok) throw new Error(await res.text());
    // Visuell: alle siblings entkativieren, btn aktivieren
    btn.parentElement.querySelectorAll('.n-ewb-btn').forEach(b =>
      b.classList.remove('n-ewb-btn--active'));
    btn.classList.add('n-ewb-btn--active');
  } catch (e) {
    alert('Speichern fehlgeschlagen: ' + e.message);
  }
}
```

**Umlaut-Regel** (CLAUDE.md lines 103-128): Button-Labels "Erfolg", "Kein Erfolg", "Überspringen" sind User-facing → **echte Umlaute**. Classes `n-ewb-btn--active` sind ASCII.

---

### `templates/app.html` (MODIFY — PreCall-Anrede-Overlay)

**Analog:** Same file lines 671-685 (`precallPanel`) + `static/pip-launcher.js` lines 220-272 (`renderStep3`).

**Wiring-Pfad** (see RESEARCH Focus Area 8):
- **Frontend:** 2 buttons "Du" / "Sie" in `pip-launcher.js` step 3 (PreCall-Form).
- **Backend:** Session-Start-Handler schreibt `conversation_logs.anrede` UND `ls.state['session_anrede']`.
- **Prompt:** `build_ewb_prompt()` liest `ls.state['session_anrede']` > `profile.ki.ansprache` > `'Sie'` Fallback.

**2-Button-Wahl in pip-launcher.js renderStep3** (lines 225-244):
```javascript
// AFTER existing inputs, BEFORE actions-row (line 238):
c.innerHTML = [
  '<div class="launcher-step">',
  '<div class="nav-live-title">Firmenrecherche</div>',
  // ... existing firma/ort/branche/person/optinfo inputs ...
  // NEU: Anrede-Toggle (D-14):
  '<div class="launcher-form-label" style="margin-top:10px">Wie soll der Assistent dich ansprechen?</div>',
  '<div class="launcher-anrede-row">',
  '  <button type="button" class="launcher-anrede-btn' + (saved.anrede === 'Du' ? ' active' : '') + '" data-val="Du" onclick="window.NerveLauncher._setAnrede(\'Du\')">Du</button>',
  '  <button type="button" class="launcher-anrede-btn' + (saved.anrede === 'Sie' ? ' active' : '') + '" data-val="Sie" onclick="window.NerveLauncher._setAnrede(\'Sie\')">Sie</button>',
  '</div>',
  // ... rest of existing actions-row ...
].join('');
```

**Save to state.precallFormData** (extend `saveFormData()` at lines 264-272):
```javascript
function saveFormData() {
  state.precallFormData = {
    firma: (document.getElementById('lnr-firma') || {}).value || '',
    ort: (document.getElementById('lnr-ort') || {}).value || '',
    person: (document.getElementById('lnr-person') || {}).value || '',
    branche: (document.getElementById('lnr-branche') || {}).value || '',
    optinfo: (document.getElementById('lnr-optinfo') || {}).value || '',
    anrede: state.precallFormData && state.precallFormData.anrede || 'Sie',  // NEU, Default Sie
  };
}
```

**Send to backend** (find `/api/start_live_session` or similar Socket.IO call in pip-launcher.js):
```javascript
// Search for existing fetch/emit in pip-launcher.js that starts the live session.
// Add anrede to payload:
fetch('/api/start_live_session', {
  method: 'POST',
  headers: {'Content-Type':'application/json'},
  body: JSON.stringify({
    ...existing_payload,
    anrede: state.precallFormData.anrede,
  }),
});
```

---

### `routes/profiles.py` (MODIFY — POST-Handler JSON-Merge)

**Analog:** Same file lines 121-155 (`bearbeiten`-Function).

**Current wholesale-replace** (line 134, 141):
```python
# ALT (line 134, 141):
daten_json = request.form.get('daten_json', p.daten or '{}')
try:
    json.loads(daten_json)
except Exception:
    daten_json = p.daten or '{}'
p.name    = request.form.get('name', p.name).strip()
p.branche = request.form.get('branche', p.branche or '').strip()
p.daten   = daten_json  # ← wholesale replace
```

**Strategy per RESEARCH Focus Area 6:** Keep wholesale-replace (konsistent zum Repo). Die NEUEN Felder werden **alle im JS-Builder** (profile_editor.html `buildAndSubmit()`) gesetzt, sodass der Server-POST bereits den kompletten JSON bekommt. **Kein Merge-Code im Server nötig**, solange Frontend alle 3 Stellen (HTML + build + populate) pflegt.

**`branche`-Enum-Validation** (D-09 Whitelist):
```python
# NEU in bearbeiten() POST-Handler nach request.form.get('branche'):
VALID_BRANCHE = {'saas_b2b','maschinenbau','versicherung','finanzprodukte',
                 'immobilien','coaching','beratung','sonstiges',''}
branche_raw = request.form.get('branche', p.branche or '').strip()
if branche_raw and branche_raw not in VALID_BRANCHE:
    branche_raw = 'sonstiges'  # Fallback statt 400
p.branche = branche_raw
```

---

### `routes/app_routes.py` (MODIFY — Session-Start writes anrede)

**Analog:** Same file lines 399-500 (session-end ObjectionEvent-insert-loop at lines 450-462).

**Find existing start_live_session or /api/beenden-analog** for session_start logic. Add:
```python
# In session_start handler (search for 'ls.state.set' or ft_session_id creation):
anrede = request.get_json(silent=True, force=True).get('anrede') if request.is_json else None
if anrede in ('Du', 'Sie'):
    with ls.state_lock:
        ls.state['session_anrede'] = anrede
    # Persistieren: conversation_logs wird erst am Ende geschrieben, daher
    # entweder zwischen-persistieren oder beim Ende-Write anhängen.
```

**In `/api/beenden`-Handler** (search conversation_logs-Write near line 420):
```python
# Extend ConversationLog creation at line 419-444 (search for ConversationLog(...)):
conv = ConversationLog(
    # ... existing fields ...
    anrede=ls.state.get('session_anrede'),  # NEU Phase 08 D-14
)
```

**New Rating-API Endpoint** (D-04, mirror pattern from RESEARCH Focus Area 11):
```python
# In routes/app_routes.py oder new routes/ewb.py, analog zu existing @login_required pattern:
@app.post('/api/ewb/<int:event_id>/rate')
@login_required
def api_ewb_rate(event_id):
    data = request.get_json(silent=True) or {}
    value = data.get('success')  # True / False / None
    if value not in (True, False, None):
        abort(400)
    db = get_session()
    try:
        ev = db.query(ObjectionEvent).filter_by(id=event_id).first()
        if not ev:
            abort(404)
        # Ownership check via conversation_logs (V4 Access Control aus RESEARCH Security §)
        conv = db.query(ConversationLog).filter_by(
            id=ev.conversation_log_id, user_id=g.user.id
        ).first()
        if not conv:
            abort(403)
        ev.success = value
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
```

---

### `.env.example` + `deploy/nerve.service` (MODIFY — D-25)

**Analog:** `.env.example` lines 1-25 (existing ENV-var documentation pattern).

**Pattern for inline-comment-documented ENV-Var:**
```bash
# .env.example existing pattern (line 21-26):
# --- Phase 04.7 Backend & Feedback ---
SUPERADMIN_EMAIL=
RESEND_API_KEY=
# Optional Resend Override (default ist Account-Region; EU im Resend Dashboard setzen)
RESEND_BASE_URL=
```

**Add for Phase 08:**
```bash
# --- Phase 08: EWB A/B Prompt-Routing ---
# Leer = A/B-Routing aktiv (deterministisch user_id % N).
# Gesetzt = forciert ALLE User auf die angegebene Variante (Safety-Net für Emergency-Rollback).
# Beispiele: 'v1-legacy' (vor Launch), 'v2-modular' (nach Launch wenn v2 sich bewährt hat).
PROMPT_EWB_VERSION_OVERRIDE=
```

**`deploy/nerve.service`** (der Service liest `/etc/nerve/.env` — siehe line 18):
Der Kommentar kommt ins `.env` selbst (nicht in die Service-Unit). Nur optional als Hinweis-Kommentar in `nerve.service` ergänzen nach line 18:
```ini
# Environment — secrets live in /etc/nerve/.env (not in repo)
# Phase 08: Optional PROMPT_EWB_VERSION_OVERRIDE für A/B-Override (siehe .env.example)
EnvironmentFile=/etc/nerve/.env
```

---

## Shared Patterns

### Pattern S1: DB-Session Lifecycle

**Source:** `database/db.py` + consumers everywhere (e.g., `routes/profiles.py` line 24-29, `services/claude_service.py` line 106-111)

**Apply to:** ALL new routes (`admin_ewb.py`), ALL new service-funcs (`prompt_pipeline.py`, `ewb_pipeline.py`), ALL new endpoints (rating-API).

```python
# Canonical pattern (from routes/profiles.py line 24-29):
from database.db import get_session
# ...
db = get_session()
try:
    # work
    result = db.query(...).first()
    db.commit()
finally:
    db.close()

# Alternative for services (from claude_service.py line 104-111):
from database.db import SessionLocal
db = SessionLocal()
try:
    # work
finally:
    db.close()
```

**Critical:** Never use context-manager `with`. Always explicit `try/finally + db.close()`.

---

### Pattern S2: Error-Swallow-Pattern (CLAUDE.md line 142-151)

**Source:** `app.py _migrate()` lines 147-152, `services/claude_service.py` line 112-113, `services/audit.py` line 11-26.

**Apply to:** Phase 08 migrations + FT-logging-writes + any DB-hook that MUST NOT crash the calling path.

```python
# Canonical pattern:
try:
    conn.execute(text(f'ALTER TABLE ...'))
    conn.commit()
    print(f"[DB] Migration: ...")
except Exception:
    pass  # swallow on duplicate/already-exists

# For logging-prefixed swallow (audit.py line 24-26):
except Exception as e:
    print(f"[FT] assistant_event write failed (module={module}): {e}")
    # no raise
```

**Apply to Phase 08:** `ObjectionEvent`-Nullable-migration (IF success_is_notnull), ENV-Override-read (fallback auf mod-routing bei KeyError), Rating-API failure (return 500 with JSON, not crash server).

---

### Pattern S3: Logging-Prefix-Konvention

**Source:** `app.py` lines 81, 150, 273, 369; CLAUDE.md line 155.

**Apply to:** Alle neuen Service-Module und Migrations.

| Prefix | Kontext | Beispiel |
|--------|---------|----------|
| `[DB]` | Migration, Seed, DB-Op | `print("[DB] Migration v08_01: ...")` |
| `[FT]` | FineTuning-Logging | `print(f"[FT] assistant_event write failed: {e}")` |
| `[Pipeline]` | NEU Phase 08 prompt_pipeline | `print(f"[Pipeline] variants loaded module=ewb count=2")` |
| `[EWB]` | NEU Phase 08 ewb_pipeline | `print(f"[EWB] v2-modular assembled len=3412")` |
| `[POLISH-55]` | 3-State-Rating-Updates | `print(f"[POLISH-55] event_id={eid} success={val}")` |
| `[Init]` | App-Startup | `print(f"[Init] Aktives Profil geladen: {name}")` |

---

### Pattern S4: Umlaut-Regel (CLAUDE.md lines 103-141)

**Apply to ALL Phase 08 artifacts:**

**ECHTE Umlaute (User-facing):**
- Tooltip-Content (`_tooltip.html`, all 20 tooltip-Content-Strings).
- Button-Labels in session_detail.html: "Erfolg", "Kein Erfolg", "Überspringen".
- Flash-Messages, Error-Messages, placeholder-Attributes.
- Benefit-Framing: "Hilf uns, dir zu helfen. Wie empfandest du …"
- D-15 Prompt-Text: "Anrede: {anrede}. WICHTIG: Nutze konsequent …"
- Modal-Content in `_beispiel_profil_modal.html`.

**ASCII (Code-Identifier):**
- Enum-Werte: `saas_b2b`, `maschinenbau`, `versicherung`, `finanzprodukte`, `immobilien`, `coaching`, `beratung`, `sonstiges` (alle lowercase-ASCII).
- JSON-Keys: `eigene_formulierungen`, `beweise`, `branche_kontext`, `anrede` (nicht `Anrede`).
- DB-Columns: `anrede`, `is_default` (nicht `ist_default`).
- HTML-IDs: `vi_eigene_formulierungen`, `vi_branche_select`, `n-ewb-rating-group`.
- CSS-Classes: `n-ewb-btn--active`, `tip-icon`, `beispiel-overlay`.
- ENV-Var: `PROMPT_EWB_VERSION_OVERRIDE` (uppercase ASCII).
- Python-Function-Names: `build_ewb_prompt`, `resolve_prompt_version` (nicht `aufloese_prompt_version`).

---

### Pattern S5: Ownership-Check (V4 Access Control, Security Domain)

**Source:** `routes/profiles.py` line 129 (`filter_by(id=pid, org_id=g.org.id)`), `routes/dashboard.py` line 722-725 (session_detail `CL.user_id == g.user.id`).

**Apply to:** NEW `/api/ewb/<id>/rate` endpoint (RESEARCH §12 Known Threat Patterns: IDOR).

```python
# Canonical ownership-check pattern (MUST be on every new API):
ev = db.query(ObjectionEvent).filter_by(id=event_id).first()
if not ev:
    abort(404)
conv = db.query(ConversationLog).filter_by(
    id=ev.conversation_log_id, user_id=g.user.id
).first()
if not conv:
    abort(403)  # belongs to another user → forbidden
```

---

### Pattern S6: Migration-Idempotenz (`INSERT OR IGNORE` vs `IF NOT EXISTS`)

**Source:** `app.py _seed_prompt_versions()` lines 627-633, `_seed_founder_dashboard_defaults` lines 550-582.

**Apply to:** Phase 08 v2-Prompt-Seeding + Training-Szenarien A/B/C (D-34).

```python
# Pattern 1: db-object-based idempotency (prompt_versions at app.py line 627-631):
for module, ptext in modules:
    exists = db.query(PromptVersion).filter_by(module=module, version='v1.0.0').first()
    if exists:
        continue
    db.add(PromptVersion(...))

# Pattern 2: SQL-level INSERT OR IGNORE (from RESEARCH §4):
db.execute(text("""
    INSERT OR IGNORE INTO prompt_versions (module, version, prompt_text, is_active, is_default)
    VALUES ('ewb', 'v2-modular', :text, 1, 0)
"""), {'text': V2_PROMPT_TEXT})
```

**Phase 08 uses Pattern 1** (consistent with existing `_seed_prompt_versions`).

---

### Pattern S7: Test-Fixture-Reuse

**Source:** `tests/conftest.py` lines 19-97.

**Apply to:** Alle neuen Tests.

| Fixture | Purpose | Usage |
|---------|---------|-------|
| `db_session` | In-memory SQLite mit Base.metadata | `test_prompt_pipeline.py`, `test_branche_migration.py` |
| `client` | Flask test client mit in-memory DB | `test_ewb_pipeline.py` (falls API-Tests) |
| `db_from_client` | Alias zu client._test_session | alternative zu `client` |
| `sample_state` | Factory für live-session state dict | unit-tests für prompt-assembly |

**NEU in test-files:** Use `monkeypatch.setattr(pp, '_RESOLVER_CACHE', {})` before each test that reads from the cache (analog zu `test_ft_write_hooks.py` line 74).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `templates/_beispiel_profil_modal.html` | template (modal) | request-response | No native-dialog modal pattern in repo — closest is `consent-overlay` in app.html (copied as PARTIAL analog). Planner uses div-overlay not native `<dialog>`. |
| `tools/ewb_rating_template.md` (optional) | doc/tool | file-I/O | No precedent — if built, use `.md` format analog zu `.planning/phases/` docs. Or skip and use Admin-Page (D-30 fallback). |
| SQLite Table-Rebuild Migration (in `_migrate()`) | config | DDL | **NO precedent in repo** — all existing migrations use `ADD COLUMN IF NOT EXISTS`. Phase 08 introduces Table-Rebuild-Pattern for the first time (see RESEARCH Focus Area 2). |

## Metadata

**Analog search scope:**
- `services/` (all 18 files listed)
- `routes/` (all 21 files listed, focus on admin_dashboard, profiles, app_routes, dashboard)
- `templates/` (focus on profile_editor, session_detail, app, admin subdirectory)
- `static/` (pip-launcher.js, nerve.css)
- `tests/` (all 16 test files, especially test_ft_*, test_einwand_*)
- `database/models.py`, `app.py _migrate()`, `.env.example`, `deploy/nerve.service`

**Files scanned:** ~30 files read in-depth (most at 50-250 line granularity)
**Pattern extraction date:** 2026-04-22
**Pattern-MatchQuality-Summary:** 17 exact, 3 role-match, 1 partial (no analog)

---

*Phase 08 Pattern Map complete. Planner can now reference analog patterns + concrete line-numbers in each Plan's `<read_first>` and `<action>` fields.*
