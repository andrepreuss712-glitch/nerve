<!-- GSD:project-start source:PROJECT.md -->
## Project

**NERVE**

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler im DACH-Markt. Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit und liefert Gegenargumente sowie Coaching-Tipps direkt auf den Bildschirm — unsichtbar für den Kunden. Ergänzend bietet NERVE einen KI-Trainingsmodus, eine Coach-Plattform für Teams und automatisierte Post-Call-Analysen.

**Status:** v0.9.4, Pre-Launch — Early Access vorbereitet
**Founder:** André Preuß, Iserlohn (Solo-Founder, Einzelunternehmer)

**Core Value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

### Constraints

- **Stack:** Kein Framework-Wechsel — Flask + Vanilla JS bleibt. Keine React-Migration.
- **Kosten Live:** Sonnet MUSS raus aus dem Live-Loop — nur Haiku für alles Live. Sonnet nur Post-Call.
- **DSGVO:** Pflicht von Tag 1 — Server in Deutschland (Hetzner), kein wörtliches Mitschneiden default.
- **Pricing:** Flat-Rate (nicht Credits) — Kunden wollen Planbarkeit. Kein harter Stopp bei Fair-Use.
- **Budget:** Bootstrap — kein externes Kapital. Reinvestition aller NERVE-Einnahmen.
- **Zeit:** Solo-Founder, ~14 Tage/Monat verfügbar.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.x - Core application backend
## Runtime
- Python (Flask-based runtime)
- pip - Dependency management
- Lockfile: `requirements.txt` present
## Frameworks
- Flask 3.0.0+ - Web framework
- Flask-SocketIO 5.3.6+ - Real-time WebSocket support for live session communication
- Not detected
- Werkzeug 3.0.0+ - WSGI utilities for Flask
## Key Dependencies
- `anthropic` 0.40.0+ - Claude API integration for conversation analysis and coaching
- `deepgram-sdk` 3.7.0+ - Real-time speech-to-text transcription service
- `elevenlabs-api` (configured via `ELEVENLABS_API_KEY`) - Text-to-speech voice synthesis for training
- `sqlalchemy` 2.0.0+ - ORM for database models and queries
- `pyaudio` 0.2.14+ - Audio input/capture for live recording during calls
- `requests` 2.31.0+ - HTTP client for external API calls (ElevenLabs text-to-speech)
- `python-dotenv` 1.0.0+ - Environment variable configuration loading
## Configuration
- Loaded via `python-dotenv` from `.env` file
- See `.env.example` for required variables
- `DEEPGRAM_API_KEY` - Deepgram speech recognition API credentials
- `ANTHROPIC_API_KEY` - Claude API credentials for analysis and coaching
- `ELEVENLABS_API_KEY` - ElevenLabs text-to-speech API credentials
- `SECRET_KEY` - Flask session encryption key (must be generated for production)
- `DATABASE_URL` - SQLite database path (default: `sqlite:///database/salesnerve.db`)
- `MAX_SESSION_HOURS` - Session timeout duration (default: 8 hours)
- `SAMPLE_RATE` - 16000 Hz (configured in `config.py`)
- `CHUNK_SIZE` - 1024 bytes per audio chunk
- `ANALYSE_INTERVALL` - 2 seconds between analysis runs
- `MERGE_WINDOW_S` - 1.0 second window for transcript merging
- `SPEAKER_DEBOUNCE_S` - 3.0 second debounce for speaker detection
## Platform Requirements
- Python 3.8+
- PyAudio library (requires system audio libraries)
- Git for version control
- Python 3.8+ runtime
- SQLite database (default) or PostgreSQL (via DATABASE_URL)
- System audio support for microphone input
- CORS enabled on Flask-SocketIO for real-time communication
- Port 5000 accessible (default; configurable via environment)
## Build & Run
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Lowercase with underscores: `claude_service.py`, `live_session.py`, `app_routes.py`
- Blueprint modules named descriptively: `auth.py`, `dashboard.py`, `training.py`, `coach.py`
- Database modules: `models.py`, `db.py`
- Lowercase with underscores: `_do_login()`, `_parse_log_meta()`, `_get_erfolgsquoten()`
- Private/internal functions prefixed with single underscore: `_migrate()`, `_parse_log_meta()`, `_fromjson()`
- Public route handlers: `login()`, `api_login()`, `register()`
- Verb-first action functions: `analysiere_mit_claude()`, `reset_session()`
- Lowercase with underscores: `user_id`, `passwort_hash`, `active_profile_id`, `erstellt_am`
- German variable names used extensively for domain concepts: `passwort`, `rolle`, `orgs`, `einwaende`, `gegenargument`
- Abbreviated in some contexts: `db`, `g`, `u`, `p`, `org`, `inv`
- Global state prefixed with underscore: `_letzte_gemeldete_version`, `_SuppressPolling`
- PascalCase for models: `User`, `Organisation`, `Profile`, `ConversationLog`, `Session`
- Suffix with `Model` when shadowing imports: `UserModel`, `OrgModel`, `Profile`
- Blueprint instances suffixed with `_bp`: `auth_bp`, `dashboard_bp`, `app_routes_bp`
- UPPERCASE for module-level constants: `PLANS`, `SCHWIERIGKEITEN`, `VOICE_POOL_MALE`, `VOICE_POOL_FEMALE`
- Dict keys in German for business concepts: `'frage'`, `'signal'`, `'redeanteil'`, `'uebergang'`
- Environment prefixed constants: `ANTHROPIC_API_KEY`, `DATABASE_URL`, `MAX_SESSION_HOURS`
## Code Style
- No enforced formatter detected. Code uses mixed spacing patterns
- 4-space indentation (Python standard)
- Line length varies (80-150 characters observed)
- Comments use horizontal separator lines: `# ── Section Name ────────────────────`
- No `.eslintrc` or linting configuration found
- No enforced style checker detected
- Code follows basic PEP 8 conventions informally
- Relative imports used: `from database.db import get_session`
- No alias shortcuts like `@` or custom mappings detected
## Error Handling
- Try-except with explicit error swallowing: `except Exception: pass`
- Try-finally blocks ensure resource cleanup (DB sessions):
- JSON parsing wrapped in try-except: `json.loads(daten)` → fallback to `{}`
- Silent failures common in non-critical operations (parsing, migrations)
- `routes/auth.py` lines 50-80: Safe session cleanup during login
- `routes/dashboard.py` lines 37-58: Log file parsing with graceful fallback
- `routes/profiles.py` lines 40-44: JSON validation with default fallback
- `app.py` lines 78-83: Database migration with silent failure on duplicate columns
## Logging
- Prefixed with context tags: `[DB]`, `[Init]`, `[FairUse]`, `[API]`
- Used during initialization: `print("[DB] Migration: added users.{col}")`
- Used during runtime state changes: `print(f"[API] Neues Ergebnis v{payload['version']}")`
- Line 81: `print(f"[DB] Migration: added users.{col}")`
- Line 273: `print(f"[Init] Aktives Profil geladen: {profile.name}")`
- Line 369: `print(f"[DB] Demo-Profil '{name}' erstellt")`
- Lines 12-18 in `app.py`: Custom filter to suppress polling endpoint logs
## Comments
- Section separators used extensively: `# ── Section Name ──────────────────────────`
- Brief inline comments explain non-obvious logic: `# Redirect GET to landing page (login is now a modal)`
- Comments describe intent, not code: `# Read ALL needed attributes now, before session closes`
- `routes/auth.py` line 18: `# Attach user to g — read all needed attributes BEFORE db.close()`
- `routes/auth.py` line 27: `# Read onboarding flag inside session so it's available after close`
- `routes/app_routes.py` line 17: `# Fair-Use soft-limit check (never hard-block)`
- Not used. Python docstrings minimal or absent
- Function docstrings used only for non-obvious public functions:
## Function Design
- Most route handlers: 15-40 lines
- Service functions: 20-60 lines
- Utility functions: 5-20 lines
- Minimal parameters (usually 1-3 for routes)
- Request context accessed via Flask `g` object: `g.user`, `g.org`
- Session accessed via Flask `session` or `flask_session`
- Routes return: `render_template()`, `redirect()`, `jsonify()`, or `Response`
- Service functions return tuples: `(success_dict, error_msg)` or `(result, error_string)`
- Direct returns of database objects when needed
- `routes/auth.py` lines 46-80: `_do_login()` returns tuple of `(user_info_dict, error_msg)`
- `routes/app_routes.py` lines 14-74: `live()` route builds context dict for template
## Module Design
- Flask blueprints explicitly defined: `auth_bp = Blueprint('auth', __name__)`
- Service modules export main functions and module-level objects
- Database `db.py` exports `engine`, `SessionLocal`, `Base`, `get_session()`
- No barrel files (index.py) found
- Direct imports from modules: `from services.claude_service import analysiere_mit_claude`
- Blueprints registered explicitly in `app.py`
- Service modules contain business logic: `services/claude_service.py`, `services/training_service.py`
- Routes modules contain Flask route handlers organized by domain
- Database module separate into `models.py` (schema) and `db.py` (connection)
## Database Patterns
- SQLAlchemy declarative base: `from database.db import Base`
- Columns defined with types: `Column(Integer, primary_key=True)`, `Column(String(200), nullable=False)`
- Foreign keys used: `Column(Integer, ForeignKey('organisations.id'))`
- Default functions: `Column(DateTime, default=utcnow)` where `utcnow` defined in models
- `get_session()` returns new SessionLocal instance
- Always wrapped in try-finally: `db.close()` guaranteed
- No context managers used; manual close required
- Multiple sequential DB operations chain queries: `db.query().filter().first()`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Three parallel background threads processing audio transcription, AI analysis, and coaching in real-time
- Shared state management via thread-safe locks for coordination between async tasks
- Database-backed multi-tenant organization model with user roles and profile systems
- Real-time client-server updates via Socket.IO for live sales coaching delivery
- Modular blueprint-based routing separating concerns (auth, profiles, live sessions, training, dashboard)
## Layers
- Purpose: Serve HTML templates and handle client-side interactivity
- Location: `templates/` for HTML, `static/app.js` for frontend logic
- Contains: Jinja2 templates for dashboard, landing page, app interface, settings
- Depends on: Flask render_template, routes providing context data
- Used by: Web browsers via HTTP and WebSocket
- Purpose: Expose HTTP and Socket.IO endpoints for frontend communication and data updates
- Location: `routes/` directory containing multiple blueprint modules
- Contains: Login, profile management, live session control, dashboard, training, coaching, organization, settings
- Depends on: Database models, service layer, auth decorators
- Used by: Frontend JavaScript and browser API calls
- Purpose: Core business logic for transcription, AI analysis, coaching recommendations, and session management
- Location: `services/` directory
- Contains:
- Depends on: Config, database, external APIs (Deepgram, Anthropic, ElevenLabs)
- Used by: Routes and background threads
- Purpose: Persist organizational data, user profiles, conversation logs, and session metadata
- Location: `database/db.py` for connection management, `database/models.py` for ORM models
- Contains: SQLAlchemy models for Organisation, User, Profile, Session, ConversationLog, TrainingScenario, etc.
- Depends on: SQLAlchemy, SQLite or configured DATABASE_URL
- Used by: All route handlers and service layer
- Purpose: Environment-based settings and application constants
- Location: `config.py`
- Contains: API keys, database URL, audio parameters (sample rate, chunk size), pricing plans, analysis intervals, category labels
- Depends on: .env file via python-dotenv
- Used by: All layers
## Data Flow
- Centralized in `live_session.py` with thread-safe locks around all shared state:
## Key Abstractions
- Purpose: Single source of truth for current live session state, shared across threads
- Examples: `state`, `transcript_buffer`, `conversation_log`, `coaching_buffer`, `session_meta`
- Pattern: Thread-safe dictionary + lock pattern, event-driven triggers via threading.Event
- Purpose: Encapsulate sales methodology, objections, counter-arguments, phases as JSON
- Examples: `Profile` model stores JSON in `daten` column
- Pattern: Profile loaded at session start into `live_session.set_active_profile()`, provides context to Claude prompts
- Structure: Contains `einwaende` (objections), `phasen` (call phases), `gegenargumente` (counter-arguments), `ki` (AI tone/style), `kaufsignale` (buying signals)
- Purpose: Persistent record of a sales conversation with analysis results
- Examples: `ConversationLog` model, structured logs include speaker, transcript, timing, objection counts
- Pattern: Created per session, updated incrementally, finalized at `/api/end_session`
- Purpose: Modular routing by domain concern
- Examples: `auth_bp`, `profiles_bp`, `app_routes_bp`, `dashboard_bp`
- Pattern: Each blueprint in separate route file, imported and registered in `app.py`
## Entry Points
- Location: `app.py` line 21-25 (Flask initialization)
- Triggers: `python app.py` or WSGI server startup
- Responsibilities:
- `/` → Landing page (public, or redirect to login/dashboard)
- `/live` → Main live coaching interface (`@app_routes_bp.route('/live', @login_required)`)
- `/dashboard` → Overview and history
- `/training` → Training scenarios
- `/profiles` → Profile management
- `/onboarding` → User onboarding flow
- `/api/ergebnis` → GET latest analysis result (polling endpoint, ~500ms intervals)
- `/api/analyse_line` → POST analyze a specific transcript line
- `/api/end_session` → POST finalize session and persist logs
- `/api/status` → GET session status
- Various Blueprint routes for auth, profiles, organizations, training
- `transcript` → Server emits final transcriptions with speaker label
- `coaching` → Server emits coaching tips and recommendations
- Client can emit control events (pause, resume, etc.)
## Error Handling
- **Database Errors:** Try-finally blocks close sessions, constraints handled at ORM level
- **API Errors:**
- **Audio Errors:**
- **Authentication:** `login_required` decorator checks session before route execution, redirects to login
- **Business Logic:**
## Cross-Cutting Concerns
- Approach: Print statements to stdout (development logging)
- Usage: `[DG]`, `[AI]`, `[DB]` prefixes denote component source
- SQL logging can be enabled via SQLAlchemy config
- Approach: ORM-level constraints (nullable, unique, ForeignKey)
- Deepgram results validated to contain `transcript` and `speaker` fields
- Claude responses validated as JSON before parsing
- User input validated in route handlers (email format for signup, etc.)
- Approach: Session-based with Flask session middleware
- User ID stored in `session['user_id']`, checked by `login_required` decorator
- User object attached to `g` for request-local access
- Token-based sessions in `DbSession` model for API authentication (future use)
- Password hashing via Werkzeug `generate_password_hash()` and `check_password_hash()`
- Approach: Role-based (owner, admin, member) on users, organization-based data isolation
- Routes check `g.user.rolle` for admin/owner-only features
- All queries filtered by `org_id` to prevent cross-organization data leakage
- Profile access limited to profiles matching user's `org_id`
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

## Git-Regel: Immer pushen

Nach jeder abgeschlossenen GSD-Phase und am Ende jeder Arbeitssession: `git push origin main` ausführen. GitHub muss immer den aktuellen Stand haben.

- **Wann:** Phase fertig, Session-Ende, vor riskanten Änderungen
- **Kein Auto-Push per Hook:** GSD macht 20+ Commits pro Phase. Ein Push am Ende reicht — gleich sicher, null Overhead.
- **Secrets:** Keine API-Keys, OAuth-Credentials oder Passwörter in committed Files. Alles in `.env`, Referenz in Code als `→ siehe .env`.


<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
