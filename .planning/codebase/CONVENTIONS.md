# Coding Conventions

**Analysis Date:** 2026-03-30

## Naming Patterns

**Files:**
- Lowercase with underscores: `claude_service.py`, `live_session.py`, `app_routes.py`
- Blueprint modules named descriptively: `auth.py`, `dashboard.py`, `training.py`, `coach.py`
- Database modules: `models.py`, `db.py`

**Functions:**
- Lowercase with underscores: `_do_login()`, `_parse_log_meta()`, `_get_erfolgsquoten()`
- Private/internal functions prefixed with single underscore: `_migrate()`, `_parse_log_meta()`, `_fromjson()`
- Public route handlers: `login()`, `api_login()`, `register()`
- Verb-first action functions: `analysiere_mit_claude()`, `reset_session()`

**Variables:**
- Lowercase with underscores: `user_id`, `passwort_hash`, `active_profile_id`, `erstellt_am`
- German variable names used extensively for domain concepts: `passwort`, `rolle`, `orgs`, `einwaende`, `gegenargument`
- Abbreviated in some contexts: `db`, `g`, `u`, `p`, `org`, `inv`
- Global state prefixed with underscore: `_letzte_gemeldete_version`, `_SuppressPolling`

**Types/Classes:**
- PascalCase for models: `User`, `Organisation`, `Profile`, `ConversationLog`, `Session`
- Suffix with `Model` when shadowing imports: `UserModel`, `OrgModel`, `Profile`
- Blueprint instances suffixed with `_bp`: `auth_bp`, `dashboard_bp`, `app_routes_bp`

**Constants:**
- UPPERCASE for module-level constants: `PLANS`, `SCHWIERIGKEITEN`, `VOICE_POOL_MALE`, `VOICE_POOL_FEMALE`
- Dict keys in German for business concepts: `'frage'`, `'signal'`, `'redeanteil'`, `'uebergang'`
- Environment prefixed constants: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `MAX_SESSION_HOURS`

## Code Style

**Formatting:**
- No enforced formatter detected. Code uses mixed spacing patterns
- 4-space indentation (Python standard)
- Line length varies (80-150 characters observed)
- Comments use horizontal separator lines: `# ── Section Name ────────────────────`

**Linting:**
- No `.eslintrc` or linting configuration found
- No enforced style checker detected
- Code follows basic PEP 8 conventions informally

**Imports Organization:**

Order observed:
1. Standard library imports: `json`, `logging`, `threading`, `datetime`
2. Third-party framework imports: `flask`, `flask_socketio`, `anthropic`, `sqlalchemy`
3. Local imports: `from config import ...`, `from database import ...`, `from routes import ...`

**Path Aliases:**
- Relative imports used: `from database.db import get_session`
- No alias shortcuts like `@` or custom mappings detected

Example import structure (`routes/auth.py`):
```python
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_session
from database.models import User, Organisation, Session as DbSession, Invitation
from config import MAX_SESSION_HOURS, PLANS
```

## Error Handling

**Patterns:**
- Try-except with explicit error swallowing: `except Exception: pass`
- Try-finally blocks ensure resource cleanup (DB sessions):
  ```python
  db = get_session()
  try:
      # DB operations
  finally:
      db.close()
  ```
- JSON parsing wrapped in try-except: `json.loads(daten)` → fallback to `{}`
- Silent failures common in non-critical operations (parsing, migrations)

**Examples:**
- `routes/auth.py` lines 50-80: Safe session cleanup during login
- `routes/dashboard.py` lines 37-58: Log file parsing with graceful fallback
- `routes/profiles.py` lines 40-44: JSON validation with default fallback
- `app.py` lines 78-83: Database migration with silent failure on duplicate columns

## Logging

**Framework:** `print()` statements

**Patterns:**
- Prefixed with context tags: `[DB]`, `[Init]`, `[FairUse]`, `[API]`
- Used during initialization: `print("[DB] Migration: added users.{col}")`
- Used during runtime state changes: `print(f"[API] Neues Ergebnis v{payload['version']}")`

**Examples from `app.py`:**
- Line 81: `print(f"[DB] Migration: added users.{col}")`
- Line 273: `print(f"[Init] Aktives Profil geladen: {profile.name}")`
- Line 369: `print(f"[DB] Demo-Profil '{name}' erstellt")`

**Werkzeug Logging:**
- Lines 12-18 in `app.py`: Custom filter to suppress polling endpoint logs

## Comments

**When to Comment:**
- Section separators used extensively: `# ── Section Name ──────────────────────────`
- Brief inline comments explain non-obvious logic: `# Redirect GET to landing page (login is now a modal)`
- Comments describe intent, not code: `# Read ALL needed attributes now, before session closes`

**Examples:**
- `routes/auth.py` line 18: `# Attach user to g — read all needed attributes BEFORE db.close()`
- `routes/auth.py` line 27: `# Read onboarding flag inside session so it's available after close`
- `routes/app_routes.py` line 17: `# Fair-Use soft-limit check (never hard-block)`

**JSDoc/TSDoc:**
- Not used. Python docstrings minimal or absent
- Function docstrings used only for non-obvious public functions:
  ```python
  def _do_login(email, passwort):
      """Shared login logic. Returns (user_info_dict, error_msg).
      All User attribute access happens inside the session before db.close().
      """
  ```

## Function Design

**Size:**
- Most route handlers: 15-40 lines
- Service functions: 20-60 lines
- Utility functions: 5-20 lines

**Parameters:**
- Minimal parameters (usually 1-3 for routes)
- Request context accessed via Flask `g` object: `g.user`, `g.org`
- Session accessed via Flask `session` or `flask_session`

**Return Values:**
- Routes return: `render_template()`, `redirect()`, `jsonify()`, or `Response`
- Service functions return tuples: `(success_dict, error_msg)` or `(result, error_string)`
- Direct returns of database objects when needed

**Examples:**
- `routes/auth.py` lines 46-80: `_do_login()` returns tuple of `(user_info_dict, error_msg)`
- `routes/app_routes.py` lines 14-74: `live()` route builds context dict for template

## Module Design

**Exports:**
- Flask blueprints explicitly defined: `auth_bp = Blueprint('auth', __name__)`
- Service modules export main functions and module-level objects
- Database `db.py` exports `engine`, `SessionLocal`, `Base`, `get_session()`

**Barrel Files:**
- No barrel files (index.py) found
- Direct imports from modules: `from services.claude_service import analysiere_mit_claude`
- Blueprints registered explicitly in `app.py`

**Module Patterns:**
- Service modules contain business logic: `services/claude_service.py`, `services/training_service.py`
- Routes modules contain Flask route handlers organized by domain
- Database module separate into `models.py` (schema) and `db.py` (connection)

## Database Patterns

**Model Definition:**
- SQLAlchemy declarative base: `from database.db import Base`
- Columns defined with types: `Column(Integer, primary_key=True)`, `Column(String(200), nullable=False)`
- Foreign keys used: `Column(Integer, ForeignKey('organisations.id'))`
- Default functions: `Column(DateTime, default=utcnow)` where `utcnow` defined in models

**Session Management:**
- `get_session()` returns new SessionLocal instance
- Always wrapped in try-finally: `db.close()` guaranteed
- No context managers used; manual close required
- Multiple sequential DB operations chain queries: `db.query().filter().first()`

**Example Pattern (`routes/profiles.py` lines 21-28):**
```python
db = get_session()
try:
    profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
    active_id = _active_profile_id()
    return render_template('profiles_list.html', profiles=profiles, active_id=active_id)
finally:
    db.close()
```

---

*Convention analysis: 2026-03-30*
