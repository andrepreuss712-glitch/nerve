# Codebase Structure

**Analysis Date:** 2026-03-30

## Directory Layout

```
salesnerve/
├── app.py                      # Flask app initialization, blueprint registration, background threads
├── config.py                   # Environment config, API keys, constants, pricing plans
├── extensions.py               # Shared extension instances (SocketIO)
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (secrets - not committed)
├── .env.example                # Template for environment variables
├── .planning/
│   └── codebase/              # GSD analysis documents (this directory)
│
├── database/
│   ├── __init__.py
│   ├── db.py                  # SQLAlchemy engine, session factory, Base declarative
│   └── models.py              # ORM models: Organisation, User, Profile, Session, ConversationLog, etc.
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                # Login, registration, logout, login_required decorator
│   ├── app_routes.py          # Live coaching interface (/live), API endpoints for analysis
│   ├── organisations.py       # Organization CRUD, team management, billing
│   ├── profiles.py            # Profile CRUD, profile switching, data validation
│   ├── dashboard.py           # Dashboard views, session history, statistics
│   ├── logs_routes.py         # Conversation log viewing, corrections, feedback
│   ├── training.py            # Training scenario selection, execution, feedback
│   ├── coach.py               # Coach dashboard (if coach role), coaching assignments
│   ├── onboarding.py          # Multi-step onboarding flow for new users
│   ├── settings.py            # User settings, notification prefs, profile management
│   ├── waitlist.py            # Waitlist signup for landing page
│   └── changelog.py           # Changelog/what's new display
│
├── services/
│   ├── __init__.py
│   ├── live_session.py        # Runtime state: buffers, locks, session metadata (NOT persistent)
│   ├── claude_service.py      # Anthropic Claude API: objection detection, counter-args, coaching
│   ├── deepgram_service.py    # Deepgram WebSocket: audio capture, transcription, speaker diarization
│   ├── training_service.py    # Training scenario logic, scenario execution, role-play responses
│   └── crm_service.py         # CRM integrations (structure ready, implementation optional)
│
├── templates/
│   ├── base.html              # Master layout with CSS/JS, navigation
│   ├── landing.html           # Public landing/marketing page
│   ├── login.html             # Login form (modal or standalone)
│   ├── register.html          # Signup flow
│   ├── onboarding.html        # Onboarding wizard (multi-step)
│   ├── app.html               # Main live coaching interface
│   ├── dashboard.html         # Dashboard with session overview
│   ├── logs_page.html         # Conversation log viewer with transcript playback
│   ├── profiles_list.html     # Profile listing and selection
│   ├── profile_editor.html    # Profile CRUD interface
│   ├── training.html          # Training scenario selection and execution
│   ├── coach_dashboard.html   # Coach role dashboard
│   ├── coach_firma.html       # Coach organization/company view
│   ├── coach_methodik.html    # Coach methodology editing
│   ├── team.html              # Team member management
│   ├── settings.html          # User settings
│   ├── help.html              # Help/documentation
│   ├── changelog.html         # Changelog display
│   └── waitlist_admin.html    # Waitlist management (admin)
│
├── static/
│   └── app.js                 # Frontend JavaScript: Socket.IO handling, UI updates, polling
│
├── logs/
│   └── [session logs]         # Generated session JSON logs (not committed)
│
└── __pycache__/               # Python bytecode cache (not committed)
```

## Directory Purposes

**`database/`:**
- Purpose: ORM models and database connection management
- Contains: SQLAlchemy models, connection initialization, session factory
- Key files: `models.py` (data schema), `db.py` (engine setup)

**`routes/`:**
- Purpose: HTTP route handlers organized by feature domain
- Contains: Blueprint modules for auth, live sessions, profiles, training, coaching, organizations, dashboard
- Key files: `app_routes.py` (live coaching endpoints), `auth.py` (login/register)

**`services/`:**
- Purpose: Core business logic separated from HTTP routes
- Contains: Real-time processing threads, API client integrations, session state
- Key files: `live_session.py` (shared state), `claude_service.py` (AI analysis), `deepgram_service.py` (audio)

**`templates/`:**
- Purpose: Jinja2 HTML templates for server-rendered pages
- Contains: Base layout, page-specific templates for all major features
- Key files: `base.html` (master layout), `app.html` (main live interface)

**`static/`:**
- Purpose: Client-side JavaScript and static assets
- Contains: Frontend logic for Socket.IO communication, UI interactions
- Key files: `app.js` (main application logic, ~800+ lines)

**`logs/`:**
- Purpose: Generated session JSON logs (runtime-created, not source code)
- Contains: Conversation logs with timestamps, transcripts, analysis results
- Generated: Via `services/live_session.py` at session end

## Key File Locations

**Entry Points:**
- `app.py`: Application startup, Flask initialization, thread spawning (line 1-669)
- `config.py`: Environment configuration loaded before app init

**Database & Models:**
- `database/models.py`: All ORM models (Organisation, User, Profile, Session, ConversationLog, etc.)
- `database/db.py`: SQLAlchemy engine, session factory, Base class

**Core Live Session Logic:**
- `services/live_session.py`: Centralized state management, thread-safe buffers
- `services/claude_service.py`: Objection detection and coaching AI logic
- `services/deepgram_service.py`: Real-time speech transcription and speaker diarization

**Main Interface:**
- `routes/app_routes.py`: `/live` route (main UI), `/api/ergebnis` (polling), `/api/analyse_line` (manual analysis)
- `templates/app.html`: Live coaching interface HTML
- `static/app.js`: Frontend Socket.IO handling, transcript display, UI updates

**Authentication & Users:**
- `routes/auth.py`: Login, register, `login_required` decorator
- `database/models.py` (User, Organisation, Session models)

**Profiles & Configuration:**
- `routes/profiles.py`: Profile CRUD, activation, data validation
- `database/models.py` (Profile model)

**Dashboard & History:**
- `routes/dashboard.py`: History view, statistics
- `routes/logs_routes.py`: Conversation log viewer with transcript corrections
- `database/models.py` (ConversationLog model)

**Configuration:**
- `config.py`: All constants, API keys, plans, analysis parameters

## Naming Conventions

**Files:**
- `*_service.py`: Service layer files (e.g., `claude_service.py`, `deepgram_service.py`)
- `*_routes.py`: Route/blueprint files (e.g., `app_routes.py`, `auth.py`)
- Snake_case for file names: `live_session.py`, `conversation_log`

**Directories:**
- Lowercase, pluralized for collections: `routes/`, `services/`, `templates/`, `static/`, `database/`
- PascalCase converted to lowercase in database filenames: `__pycache__/`

**Variables & Functions:**
- Snake_case: `transcript_buffer`, `get_session()`, `analysiere_mit_claude()`
- German terms used in database and API: `daten` (data), `ergebnis` (result), `einwand` (objection)
- Prefixed logs: `[DG]` (Deepgram), `[AI]` (AI/Claude), `[DB]` (Database), `[FairUse]`, `[API]`

**Database Models:**
- PascalCase: `Organisation`, `User`, `Profile`, `ConversationLog`, `TrainingScenario`
- Column names in snake_case with German terms: `erstellt_am` (created_at), `aktiv` (active), `passwort_hash` (password_hash)
- Timestamps: `erstellt_am`, `aktualisiert_am`, `start_zeit`, `end_zeit`

**API Routes:**
- RESTful convention where applicable: `/profiles` (list), `/profiles/<id>` (detail)
- Mixed: Some routes are RPC-style: `/api/ergebnis` (poll state), `/api/analyse_line` (trigger analysis)
- Prefix `/api/` for JSON API endpoints

**HTML Templates:**
- Lowercase with underscores: `app.html`, `coach_dashboard.html`, `profile_editor.html`
- Suffix `_admin.html` for admin-only pages: `waitlist_admin.html`

## Where to Add New Code

**New Feature (e.g., new profile type, new objection type):**
- Backend Logic: Add route to appropriate file in `routes/` or extend `services/live_session.py`
- Database: Add column to existing model in `database/models.py` or create new model
- Tests: Create test file in `tests/` (if testing is added)
- Frontend: Add Vue/JavaScript logic to `static/app.js` or extend HTML in `templates/`

**New Page/Template:**
- Create HTML in `templates/[page_name].html` extending `base.html`
- Create route handler in appropriate `routes/[feature].py` file
- Add navigation link in `base.html`
- Register any new Blueprint in `app.py` if it's a new feature domain

**New Service Integration (e.g., new API client):**
- Create `services/[service_name]_service.py` with class/functions
- Import in `app.py` or route that needs it
- Add API key to `config.py` and `.env.example`
- If background thread needed, instantiate in `app.py` line 659-661

**New Route Group:**
- Create `routes/[feature_name].py` with Blueprint definition:
  ```python
  from flask import Blueprint
  feature_bp = Blueprint('feature', __name__)

  @feature_bp.route('/feature', methods=['GET', 'POST'])
  @login_required
  def handler():
      ...
  ```
- Import and register in `app.py` around line 624-648

**Database Migration:**
- Alter existing model in `database/models.py` (add Column)
- Add migration code to `app.py` `_migrate()` function (lines 38-116)
- Migration runs automatically on startup via `init_db()` and `_migrate()`

**New Utility Function:**
- Shared helpers: Add to `services/` file (e.g., add to `live_session.py`)
- Route-specific: Add to route file in `routes/`
- Cross-cutting: Create new file in `services/` or root if no appropriate place

## Special Directories

**`.planning/codebase/`:**
- Purpose: GSD (Goal-Structured Development) analysis documents
- Generated: Via `/gsd:map-codebase` orchestrator command
- Committed: Yes, guides future planning phases
- Contains: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md

**`logs/`:**
- Purpose: Runtime session logs generated during live coaching sessions
- Generated: Via `services/live_session.py` at session end
- Committed: No (added to .gitignore)
- Contains: JSON files with timestamps, transcripts, analysis results per session

**`__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Automatically by Python interpreter
- Committed: No (in .gitignore)

## Thread Architecture

The application uses three background threads spawned in `app.py` (lines 659-661):

1. **Deepgram Thread** (`deepgram_starten()`):
   - Captures audio from microphone via PyAudio
   - Streams to Deepgram WebSocket for real-time transcription
   - Emits `on_message()` callback with final transcripts
   - Maintains speaker diarization (Berater=0, Kunde=1)
   - Updates `live_session.transcript_buffer` with text and speaker
   - Emits Socket.IO `transcript` event to browser

2. **Analysis Thread** (`analyse_loop()`):
   - Runs continuously in background
   - Waits on `live_session.analyse_trigger` event
   - Processes buffered transcripts in batch via Claude API
   - Calls `analysiere_mit_claude()` with profile context and recent transcript
   - Stores JSON result (objection type, counter-args) in `live_session.state['ergebnis']`
   - Increments version counter for client update detection
   - Emits Socket.IO `analysis` event with result

3. **Coaching Thread** (`coaching_loop()`):
   - Runs continuously in background
   - Analyzes conversation for coaching tips
   - Calls coaching Claude prompt to detect dealer tips, pain points, buying readiness
   - Stores in `live_session.coaching_buffer`
   - Emits Socket.IO `coaching` event

All threads use thread-safe locks from `live_session.py` to coordinate shared state.

---

*Structure analysis: 2026-03-30*
