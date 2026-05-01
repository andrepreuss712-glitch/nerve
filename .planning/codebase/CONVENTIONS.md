# Coding Conventions

**Analysis Date:** 2026-05-01

## Naming Patterns

**Files:**
- Snake_case throughout: `claude_service.py`, `live_session.py`, `app_routes.py`
- Blueprint modules named by domain noun: `auth.py`, `dashboard.py`, `training.py`, `coach.py`
- Database modules: `models.py` (ORM schema), `db.py` (connection/session)
- Service modules: descriptive noun phrases: `ewb_pipeline.py`, `prompt_pipeline.py`, `ki_logik.py`

**Functions:**
- Lowercase snake_case: `compute_readiness_score`, `build_ewb_prompt`, `log_api_cost`
- Private/internal functions prefixed with single underscore: `_do_login()`, `_parse_log_meta()`, `_normalize_branche()`, `_make_test_user()`
- Verb-first for action functions: `analysiere_mit_claude()`, `resolve_prompt_version()`, `migrate_tabu_begriffe()`
- Route handlers named by HTTP action or resource: `login()`, `liste()`, `bearbeiten()`

**Variables:**
- Lowercase snake_case: `user_id`, `passwort_hash`, `active_profile_id`, `erstellt_am`
- German domain terms for business concepts: `passwort`, `rolle`, `einwaende`, `gegenargument`, `gespraech`
- Short abbreviations for loop vars and DB references: `db`, `u`, `p`, `org`
- Global state prefixed with underscore: `_letzte_gemeldete_version`, `_ewb_fallback_until`

**Types / Classes:**
- PascalCase for SQLAlchemy models: `User`, `Organisation`, `Profile`, `ConversationLog`, `Session`
- Suffix `Model` when shadowing a Python keyword or import: `UserModel`, `OrgModel`
- Pydantic schemas: PascalCase + `Schema` suffix: `ProfileSchema`, `BasisSchema`, `KiSchema`, `ZielgruppeSchema`
- Read vs. Write schema pair: `ProfileSchema` (write, `extra='forbid'`), `ProfileReadSchema` (read, `extra='ignore'`)

**Constants:**
- UPPERCASE for module-level constants: `PLANS`, `SCORE_FACTORS`, `VOICE_POOL_MALE`, `LATEST_SCHEMA_VERSION`
- Dict keys in German for business domain: `'frage'`, `'signal'`, `'redeanteil'`, `'uebergang'`
- Environment-derived constants: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `MAX_SESSION_HOURS`

**Blueprint Instances:**
- Always suffixed with `_bp`: `auth_bp`, `dashboard_bp`, `profiles_bp`, `app_routes_bp`
- Blueprint name string (first arg to `Blueprint(...)`) is the `url_for` prefix — MUST match table in `routes/CLAUDE.md`
- Full verified mapping: `organisations.py` uses `orgs_bp = Blueprint('orgs', ...)`, NOT `'organisations'`

## Deutsche Umlaute — Zwei-Regel-System (KRITISCH)

This is the most important and most easily violated convention. The project is fully UTF-8; there is no encoding bug. Two rules apply depending on audience:

**Rule 1 — Real Umlauts (ä, ö, ü, ß) in user-facing text:**
- HTML content between tags: `<div>Gespräch wird ausgewertet…</div>`
- Labels, buttons, headings: `<button>Zurück</button>`
- Placeholders, tooltips: `placeholder="Für Sie"`
- Flash messages, error messages visible in the browser
- Default string constants for user output: `CONSENT_DEFAULT_TEXT`
- JS strings the user sees in alerts or rendered HTML

**Rule 2 — ASCII substitution (ae/oe/ue/ss) in code identifiers:**
- Python attributes and DB columns: `ConversationLog.einwaende_gesamt`
- Dict keys that round-trip as JSON: `{'einwaende': [...], 'gespraech_id': 42}`
- Jinja2 expressions resolving Python attributes: `{{ conv.einwaende_ok }}`
- JS variable names: `let einwaende = 0` (not `let einwände`)
- JS object keys sent to backend: `{spezial_einwaende: [...]}`
- HTML id/class attributes: `id="sc-einwaende"`, class `.einwand-card`
- CSS selectors: `.einwand-card` (never `.einwände-card`)
- URL slugs and route names: `/api/einwaende/list`

**Wrong — cargo-cult ASCII in user-facing text:** `<div>Einwaende erkannt</div>`
**Wrong — Umlaut in code identifier:** `let einwände = data.einwände`
**Correct:** `<div>Einwände erkannt</div>` + `let einwaende = data.einwaende`

## Code Style

**Formatting:**
- No enforced formatter (no ruff, black, or isort config detected)
- 4-space indentation (Python standard, consistent throughout)
- Line length varies 80–150 characters; no hard limit enforced
- Imports grouped informally: stdlib → third-party → project-local (not always strictly ordered)

**Linting:**
- No `.eslintrc`, `pyproject.toml` linting section, or `setup.cfg` detected
- Code follows PEP 8 informally

## Section Separators

All significant code blocks are separated with a consistent horizontal rule comment:

```python
# ── Section Name ──────────────────────────────────────────────────────────────
```

Width target ~80 characters total. Examples:
```python
# ── Score factors (from NERVE KI-Logik Kernarchitektur.md briefing) ──────────
# ── Per-SID Coaching Buffer Isolation (WR-03 — DSGVO) ────────────────────────
# ── detect_phase (Phase 04.8 P02 hysteresis) ─────────────────────────────────
```

Always add a separator when starting a new logical block, sub-section of tests, or named group of constants.

## Import Organization

**Order (informal, not enforced by tooling):**
1. stdlib (`os`, `sys`, `json`, `threading`, `datetime`)
2. Third-party (`flask`, `sqlalchemy`, `anthropic`, `pydantic`)
3. Project-local (`from database.db import get_session`, `from services.claude_service import ...`)

**Style:**
- Full dotted path: `from database.db import get_session`
- No `@` alias, no barrel re-exports — import directly from the module file
- When avoiding circular imports, use local/deferred imports inside functions

## Error Handling

**Primary pattern — try/finally for DB sessions (MANDATORY):**
```python
db = get_session()
try:
    result = db.query(Profile).filter_by(org_id=g.org.id).all()
    return render_template('profiles_list.html', profiles=result)
finally:
    db.close()
```
Never use `with get_session() as db:` — the project does NOT use context manager pattern for sessions. `get_session()` returns a raw `SessionLocal()` instance; only `get_db()` is a generator (unused in routes).

**Silent failure for non-critical operations:**
```python
try:
    daten = json.loads(raw)
except Exception:
    daten = {}
```

**Route error responses:**
- JSON APIs: `return jsonify({'ok': False, 'error': 'message'}), 400`
- HTML routes: `flash('Fehlermeldung', 'error')` + `redirect(...)`
- Auth failures: `return redirect(url_for('auth.login'))`

**Service function errors — tuple return:**
```python
def some_service(param) -> tuple:
    try:
        result = do_thing(param)
        return result, None
    except Exception as e:
        return None, str(e)

# Caller:
result, error = some_service(x)
if error:
    return jsonify({'ok': False, 'error': error}), 400
```

## Logging

**Format — context-tagged print statements (legacy pattern):**
```python
print("[DB] Migration: added users.{col}")
print(f"[API] Neues Ergebnis v{payload['version']}")
print(f"[Init] Aktives Profil geladen: {profile.name}")
```

**Tag prefixes used:**
- `[DB]` — database operations, migrations
- `[Init]` — application startup
- `[API]` — external API calls
- `[DG]` — Deepgram-specific
- `[AI]` — AI analysis steps
- `[FairUse]` — fair-use tracking
- `[AUTH]` — authentication events (security-critical; use `current_app.logger.warning(...)`)

`services/live_session.py` uses `_logger = logging.getLogger(__name__)` (newer code pattern). All other modules use `print()` (older, still dominant).

## Comments

**Section separators** are mandatory (see above).

**Intent over code restatement:**
```python
# Read ALL needed attributes now, before session closes
# Redirect GET to landing page (login is now a modal)
# Fair-Use soft-limit check (never hard-block)
```

**Phase/ticket-tagged explanations for non-obvious decisions:**
```python
# LB-11: Onboarding-Redirect reaktiviert (deaktiviert in 6b57a77 als deploy hardening...)
# M-AU-1: Org-Scoping-Assertion — verhindert Cross-Org-Datenzugriff bei inkonsistenter DB-State
# user override: Einwand gelöst = +20 (briefing says +15)
```

**No JSDoc/docstrings as a rule.** Module-level docstrings used only for complex service modules (`services/profile_schema.py`, `services/ki_logik.py`, `services/ewb_pipeline.py`). Route files rarely have docstrings.

## Function Design

**Size targets:**
- Route handlers: 15–40 lines
- Service functions: 20–60 lines
- Helper/utility functions: 5–20 lines

**Parameters:**
- Routes access request data via Flask `request`, `g`, and `session` — not function params
- Service functions accept explicit params (no Flask globals inside services)
- 1–4 parameters typical; complex data passed as dicts

**Return values:**
- Routes: `render_template()`, `redirect()`, `jsonify()`, or `Response`
- Service functions: tuple `(result_or_None, error_string_or_None)`
- Pure logic functions (`ki_logik.py`): direct return of computed value or tuple

**Private helpers:** prefix with `_` and co-locate in same module: `_normalize_branche()`, `_qa_load_tabu()`, `_build_ewb_variants()`

## Module Design

**Blueprints:**
```python
auth_bp = Blueprint('auth', __name__)
profiles_bp = Blueprint('profiles', __name__, url_prefix='/profiles')
```
Always registered explicitly in `app.py`. Full verified name table in `routes/CLAUDE.md`.

**Service modules:**
- Pure business logic, no Flask globals (`g`, `session`, `request`)
- Export main functions at module level
- Module-level singletons for expensive resources: `claude_client = anthropic.Anthropic(...)`

**No barrel files:** `routes/__init__.py` and `services/__init__.py` are empty. Import directly from the module file.

## Database Patterns

**Model definition style (`database/models.py`):**
```python
class Profile(Base):
    __tablename__ = 'profiles'
    id      = Column(Integer, primary_key=True)
    org_id  = Column(Integer, ForeignKey('organisations.id'), nullable=False)
    name    = Column(String(200), nullable=False)
    daten   = Column(Text)          # JSON blob, parsed in application layer
    erstellt_am = Column(DateTime, default=utcnow)
```
- All timestamps use `default=utcnow` (project-defined helper in `database/models.py`)
- Foreign keys are explicit `Column(Integer, ForeignKey('table.id'))`
- JSON data stored as `Text` column, never as `JSON` column type

**Session lifecycle (MANDATORY pattern):**
```python
db = get_session()
try:
    obj = db.query(Model).filter_by(org_id=g.org.id).first()
    db.add(new_obj)
    db.commit()
    return obj
finally:
    db.close()
```

**JSON column parsing (always with fallback):**
```python
try:
    daten = json.loads(profile.daten) if profile.daten else {}
except Exception:
    daten = {}
```

**Test DB injection pattern:**
```python
monkeypatch.setattr(database.db, 'SessionLocal', TestSession)
```
The `_Fake` adapter class (defined in test files) wraps the pytest session and no-ops `close()` to prevent premature session closure.

## Schema / Validation Pattern (Pydantic v2)

**Write path — strict:**
```python
# extra='forbid' — unknown keys raise ValidationError
ProfileSchema.model_validate(daten)
```

**Read path — permissive:**
```python
# extra='ignore' — unknown keys silently dropped, safe for legacy data
ProfileReadSchema.model_validate(daten)
```

**Migration before validation (always):**
```python
migrated = _migrate_profile_data(daten.copy())   # idempotent v1->v2->v3->v4
ProfileSchema.model_validate(migrated)            # strict write-schema
```

`LATEST_SCHEMA_VERSION` in `services/profile_schema.py` is the canonical version target. Always check this constant before writing schema-bump logic.

---

*Convention analysis: 2026-05-01*
