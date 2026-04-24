# Coding Conventions

**Analysis Date:** 2026-04-24

## Naming Patterns

**Files:**
- Python modules: lowercase with underscores: `claude_service.py`, `live_session.py`, `app_routes.py`
- Blueprint route files: descriptive lowercase: `auth.py`, `dashboard.py`, `training.py`, `coach.py`
- Service modules: `[domain]_service.py`: `training_service.py`, `coaching_service.py`, `ki_logik.py`
- JavaScript files: kebab-case or lowercase: `app.js`, `pip-launcher.js`, `audio-processor.js`

**Python Functions:**
- Public route handlers: `login()`, `api_login()`, `register()`, `training_page()`
- Private/internal functions: prefixed with single underscore: `_do_login()`, `_parse_log_meta()`, `_migrate()`, `_ensure_dict()`
- Verb-first action functions: `analysiere_mit_claude()`, `reset_session()`, `build_customer_prompt()`
- Service layer returns tuples: `(success_dict, error_msg)` or `(result, error_string)` convention used in `routes/auth.py:80`
- Example: `routes/auth.py:80` `_login_user()` reads all needed attributes before db.close()

**JavaScript Functions:**
- camelCase for all function names: `startMicStream()`, `stopMicStream()`, `selectMode()`, `activateSession()`
- Private/internal (module-level IIFE): underscore prefix: `_showPrecallOrActivate()`, `_scenarioMeta`, `_lastEwbKey`
- Socket.IO handlers: `socket.on('eventname', function)`
- Event handlers: `onclick="functionName()"` directly in HTML attributes
- Example from `static/app.js:115`: `function _showPrecallOrActivate()` — underscore marks internal to mode selection logic

**Python Variables & Attributes:**
- German domain terms used throughout: `passwort`, `rolle`, `orgs`, `einwaende`, `gegenargument`, `gespraech_id`
- Database columns: `einwaende_gesamt`, `conversation_log`, `erstellt_am`, `org_id`, `active_profile_id`
- Global state prefixed with underscore: `_letzte_gemeldete_version`, `_SuppressPolling`, `_sessions`, `_sessions_lock` (see `routes/training.py:40-41`)
- Abbreviated sometimes: `db`, `g`, `u`, `p`, `org`, `inv` (request context helpers)
- Request context via Flask `g` object: `g.user`, `g.org` (loaded in `login_required` decorator, `routes/auth.py:54-55`)

**Classes & Models:**
- PascalCase: `User`, `Organisation`, `Profile`, `ConversationLog`, `Session`, `TrainingScenario`
- Suffix with `Model` when shadowing imports: `UserModel`, `OrgModel` (used in `routes/training.py:96`)
- Blueprint instances: suffix with `_bp`: `auth_bp`, `dashboard_bp`, `app_routes_bp` (see `routes/auth.py:12`)

**Constants:**
- UPPERCASE for module-level constants: `PLANS`, `SCHWIERIGKEITEN`, `VOICE_POOL_MALE`, `VOICE_POOL_FEMALE` (see `services/training_service.py:13-24`)
- Dict keys in German for business concepts: `'frage'`, `'signal'`, `'redeanteil'`, `'uebergang'` (see `services/claude_service.py:85-88`)
- Environment prefixed constants: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `MAX_SESSION_HOURS`

**JavaScript Variables:**
- camelCase: `micStream`, `audioCtx`, `workletNode`, `sessionMode`, `precallBriefingText`
- State objects in IIFE: `state = {...}` namespace (see `static/pip-launcher.js:12`)
- Event-based message keys: `'audio_chunk'`, `'start_live_session'`, `'stop_live_session'` (see `static/app.js:57`)

## Code Style

**Python:**
- 4-space indentation (Python standard PEP 8)
- No enforced formatter detected (no .black, .isort, or .flake8)
- Line length varies widely (80-150 characters observed)
- Comments use horizontal separator lines: `# ── Section Name ────────────────────` (see `routes/auth.py:15` onward)
- Code follows basic PEP 8 conventions informally — no strict enforcement
- Multi-line imports used: `from flask import (Blueprint, render_template, request, ...)`

**JavaScript:**
- 2-space indentation (observed in `static/app.js`, `static/pip-launcher.js`)
- No `.eslintrc` or ESLint configuration found
- No `.prettierrc` or Prettier configuration found
- Comments use horizontal separators: `// ── Section Name ──────────────────────────────` (see `static/app.js:3, 32, 88, 230`)
- Single quotes preferred for string literals: `'websocket'`, `'polling'`, `'cold_call'`
- Strict mode in IIFE: `'use strict';` (see `static/pip-launcher.js:5`)

**Imports & Module Organization:**
- Relative imports used in Python: `from database.db import get_session`, `from services.training_service import ...`
- No alias shortcuts like `@` or custom path mappings detected
- Imports grouped: stdlib → third-party → local (see `routes/auth.py:1-10`, `services/training_service.py:1-8`)
- Explicit imports preferred over star imports: `from database.models import User, Organisation, Profile`

## UTF-8 & German Umlaute

**User-Facing Text (HTML/Output):** Use real umlauts ä, ö, ü, ß
- HTML content: `<div>Gespräch wird ausgewertet…</div>`
- Labels, buttons, headers: `<button>Zurück</button>`
- Placeholders, tooltips: `placeholder="Für Sie"`
- Flash messages, error messages
- Example: `templates/training.html` contains `"Bitte Firmennamen eingeben"`

**Code Identifiers (Variables, Attributes, Keys):** Use ASCII replacements ae, oe, ue, ss
- Python attributes: `ConversationLog.einwaende_gesamt` (not `einwände`)
- Dict keys: `{'einwaende': [...], 'gespraech_id': 42}` (not `{'einwände': ...}`)
- Jinja2 expressions: `{% if log.einwaende > 0 %}` (not `{% if log.einwände %}`)
- JavaScript variable names: `let einwaende = 0` (not `let einwände`)
- HTML IDs/classes: `id="sc-einwaende"` (not `id="sc-einwände"`)
- URL slugs/routes: `/api/einwaende/list` (not `/api/einwände/list`)

**Rationale:** Python and JS identifiers resolve via ASCII lookup; HTML attributes need JavaScript selectors. Umlauts in these contexts cause encoding confusion in older codebases, though this project is UTF-8 clean.

## Error Handling

**Strategy:** Defensive try-except with silent failures for non-critical operations, explicit logging for critical paths

**Patterns:**
- Try-except with explicit error swallowing: `except Exception: pass` (common in non-critical parsing)
- Try-finally blocks ensure resource cleanup — especially database sessions: `db.close()` guaranteed in finally block
- Example: `routes/auth.py:48-59` — login_required decorator uses try-finally to close DB session
- JSON parsing wrapped in try-except with fallback: `json.loads(daten)` → fallback to `{}`
- Example: `routes/training.py:31-38` — `_ensure_dict()` handles double-encoded JSON, None, and type errors gracefully
- Silent failures in non-critical operations (migrations, parsing): print warning but don't raise
- Example: `routes/training.py:114-141` — Voice usage check catches all exceptions and logs `[Training] Voice-Check Fehler` but continues

**Database Errors:**
- Handled at ORM constraint level (NOT NULL, UNIQUE, ForeignKey)
- Queries wrapped in try-finally to guarantee session cleanup
- Example: `routes/dashboard.py` uses try-finally around DB session

**API Errors:**
- Graceful degradation when external APIs fail (Deepgram, Anthropic, ElevenLabs)
- Silent failure on rate limit or temporary outages — logged with `[API]` prefix
- Example: `services/claude_service.py` catches anthropic exceptions and returns error tuple

**Authentication:**
- `login_required` decorator checks session before route execution, redirects to login if invalid
- User object attached to `g` for request-local access
- Session stored via Flask `session['user_id']`

## Logging

**Framework:** Print statements to stdout with prefixed context tags

**Patterns:**
- Tag prefixes denote component: `[DB]`, `[Init]`, `[FairUse]`, `[API]`, `[Mic]`, `[Training]`, `[DG]` (Deepgram)
- Used during initialization: `print("[DB] Migration: added users.{col}")` (see `app.py:81`)
- Used during runtime state changes: `print(f"[FairUse] Org {_org.id} at {_org.training_sessions_used}/{training_limit} training sessions")`
- JavaScript logging: `console.log('[Mic] AudioContext state after creation:', audioCtx.state)` (see `static/app.js:45`)
- No structured logging framework (no Sentry, CloudWatch, ELK stack detected)
- SQL logging can be enabled via SQLAlchemy config if needed

**Log Locations & Audience:**
- Development: stdout (visible in terminal/container logs)
- Production: stdout → captured by deployment platform (Hetzner, Docker, systemd journal)
- No separate log files tracked (logs are ephemeral per request in stateless deploy)

## Comments

**When to Comment:**
- Section separators to mark logical blocks: `# ── Section Name ──────────────────────────`
- Brief inline comments explain non-obvious logic: `# Redirect GET to landing page (login is now a modal)` (see `routes/auth.py:73`)
- Comments describe intent, not code: avoid `# Increment x` → do use `# Read all needed attributes BEFORE db.close()`
- Phase references: `# Phase 04.13: stored briefing for session persistence` (see `static/app.js:18`)
- Implementation notes: `# Attach user to g — read all needed attributes BEFORE db.close()` (see `routes/auth.py:47`)

**JSDoc/TSDoc:**
- Not used. Python docstrings minimal or absent
- Function docstrings used only for non-obvious public functions: `safe_next()` in `routes/auth.py:15-21` includes docstring explaining open-redirect protection
- Most functions lack docstrings — rely on clear naming and code structure

**Dead Code Comments:**
- Marked with explicit "ENTFERNT" or "orphaned" comment: `// ENTFERNT in 07.2 Wave 3: saveGeneratedPersonality()` (see `templates/training.html:1633`)
- Includes reason: "war nur aus dem Post-Call-Scoring-Overlay aufrufbar. Overlay ist weg"
- Known re-introduction plan noted: "Re-Introduction zusammen mit dem Save-Prompt unter POLISH-37"

## Function Design

**Size Guidelines:**
- Route handlers: 15-40 lines (most stay under 30)
- Service functions: 20-60 lines
- Utility functions: 5-20 lines
- Example: `routes/auth.py:80-100` `_login_user()` is ~25 lines

**Parameters:**
- Minimal parameters (usually 1-3 for routes)
- Flask routes use context via `g` object instead of parameters: `g.user`, `g.org`
- Session accessed via Flask `session` or `flask_session`
- Database accessed via `get_session()` call within function

**Return Values:**
- Routes return: `render_template()`, `redirect()`, `jsonify()`, or `Response` object
- Service functions return tuples: `(success_dict, error_msg)` or `(result, error_string)` convention
- Direct returns of database objects when needed: `db.get(User, user_id)` returns ORM object or None
- JavaScript async functions: return Promises, resolve with JSON data from fetch
- Example: `routes/training.py:89-175` POST handler returns `jsonify()` with response dict

**Error Handling in Functions:**
- Wrap DB operations: `db = get_session(); try: ... finally: db.close()`
- Return error tuple on validation failure: `(None, "Validation error message")`
- No exceptions raised for expected errors (validation, missing data) — use error tuple pattern

## Module Design

**Exports:**
- Flask blueprints explicitly defined: `auth_bp = Blueprint('auth', __name__)` at module top (see `routes/auth.py:12`)
- Service modules export main functions and module-level objects: `build_customer_prompt()`, `SCHWIERIGKEITEN`, `VOICE_POOL_MALE`
- Database module separate: `models.py` (schema), `db.py` (connection) → `get_session()`, `engine`, `SessionLocal`, `Base`
- No barrel files (index.py) found — direct imports from modules preferred

**File Organization:**
- Routes: `routes/` directory — one blueprint per file, domain-organized
- Services: `services/` directory — business logic, API clients, data processing
- Database: `database/` directory — `models.py` (SQLAlchemy ORM), `db.py` (session management)
- Templates: `templates/` directory — Jinja2 HTML
- Static: `static/` directory — JavaScript, CSS
- Config: `config.py` at root — environment variables, constants

**Blueprint Registration:**
- All blueprints registered in `app.py` explicitly: `app.register_blueprint(auth_bp, url_prefix='/auth')`
- Service modules contain business logic, routes contain Flask endpoints
- No middleware or decorators defined at module level (except `@login_required` which wraps route handlers)

## Database Patterns

**ORM Approach:**
- SQLAlchemy declarative base: `from database.db import Base` (see `database/models.py`)
- Columns defined with types: `Column(Integer, primary_key=True)`, `Column(String(200), nullable=False)`
- Foreign keys used: `Column(Integer, ForeignKey('organisations.id'))`
- Default functions: `Column(DateTime, default=utcnow)` where `utcnow` defined in models

**Session Management:**
- `get_session()` returns new SessionLocal instance — called within route handlers
- Always wrapped in try-finally: `db.close()` guaranteed (see `routes/training.py:53-64`)
- No context managers used — manual close required
- Multiple sequential DB operations chain queries: `db.query(Profile).filter_by(org_id=g.org.id).all()`

**Constraints & Validation:**
- NOT NULL, UNIQUE enforced at ORM level
- Foreign key constraints enforced by SQLAlchemy
- User input validated in route handlers (email format, length checks)
- Business logic constraints enforced in service layer before DB write

## Special Patterns Observed

**Locking Pattern (Thread-Safe State):**
- Global state + threading.Lock for concurrent access: `_sessions = {}; _sessions_lock = threading.Lock()` (see `routes/training.py:40-41`)
- Example usage: acquire lock before reading/writing shared state in multi-threaded context

**Request Context Pattern (Flask g object):**
- User loaded into `g.user` in `login_required` decorator
- Org loaded into `g.org` in same decorator
- Attributes read from DB BEFORE session closes (see `routes/auth.py:47` comment)
- Rationale: Flask `g` is request-scoped; if you close DB before returning `g`, attributes aren't accessible later

**Safe URL Pattern (Open Redirect Protection):**
- `safe_next()` function validates next-URL to same-origin only (see `routes/auth.py:15-31`)
- Rejects protocol-relative paths (`//evil.com`), absolute URLs (`http://...`), newlines/carriage returns
- Used in login flow to preserve original request path across redirect

---

*Convention analysis: 2026-04-24*
