# Codebase Structure

**Analysis Date:** 2026-04-24

## Directory Layout

```
salesnerve/
├── app.py                          # Flask app initialization, socketio setup, Jinja filters, DB init
├── config.py                       # Environment-based config: API keys, audio params, constants
├── requirements.txt                # Python dependencies
│
├── database/
│   ├── db.py                       # SQLAlchemy connection, SessionLocal, Base
│   └── models.py                   # SQLAlchemy ORM models (User, Organisation, Profile, ConversationLog, etc.)
│
├── services/
│   ├── claude_service.py           # Claude API calls: analysiere_mit_claude(), gebrauche_coaching_prompt(), etc.
│   ├── prompt_pipeline.py          # A/B routing: resolve_prompt_version(), build_profile_context()
│   ├── ewb_pipeline.py             # EWB prompt assembly: build_ewb_prompt(), _load_prompt_template()
│   ├── live_session.py             # Global session state (live_session.state), thread-safe locks, helpers
│   ├── deepgram_service.py         # Deepgram streaming STT, transcript buffering, session start/end
│   ├── training_service.py         # Training scenario logic, persona simulation, LLM generation
│   ├── coaching_service.py         # Coach tips, learning cards, recommendation logic
│   ├── precall_service.py          # PreCall research briefing generation
│   ├── qa_pipeline.py              # Quality assurance question dispatch (Phase 08.5)
│   ├── einwand_keyword_matcher.py  # Pattern matching for objection detection (Phase 06.2)
│   ├── ki_logik.py                 # Phase classifier, readiness score computation
│   ├── audit.py                    # Audit logging for compliance
│   ├── cost_tracker.py             # API cost tracking for Anthropic, Deepgram, ElevenLabs
│   ├── crm_service.py              # CRM integration (Hubspot, Salesforce stubs)
│   ├── customer_success_service.py # Customer support coordination
│   ├── feedback_service.py         # Post-call feedback collection and analysis
│   ├── email_service.py            # Email sending (welcome, password reset, etc.)
│   ├── auth_decorators.py          # login_required, admin_required decorators
│   ├── profile_migration.py        # Profile data schema migration helpers
│   ├── eur_calculator.py           # EUR calculation utilities
│   ├── einwand_keyword_matcher.py  # Objection keyword pattern matching
│   ├── exchange_rates.py           # Currency conversion
│   └── __init__.py
│
├── routes/                         # Flask Blueprint modules
│   ├── app_routes.py               # Main routes: /live, /api/start_session, /api/end_session, /api/ergebnis, /api/analyse_line
│   ├── auth.py                     # /login, /register, /logout, /check_session
│   ├── profiles.py                 # /profiles (CRUD), /api/profile/{id}/update
│   ├── training.py                 # /training, /api/training/scenarios, /api/training/run_scenario
│   ├── coach.py                    # Coach module routes
│   ├── dashboard.py                # /dashboard, session history, analytics
│   ├── learning.py                 # Learning cards and coaching material
│   ├── admin_dashboard.py          # Admin views
│   ├── admin_ewb.py                # EWB prompt admin (version management)
│   ├── admin_views.py              # General admin routes
│   ├── organisations.py            # Org management
│   ├── payments.py                 # Payment/subscription routes
│   ├── performance.py              # Performance analytics
│   ├── feedback.py                 # Feedback collection
│   ├── onboarding.py               # User onboarding flow
│   ├── changelog.py                # Changelog display
│   ├── legal.py                    # Legal docs (privacy, ToS)
│   ├── logs_routes.py              # Session logs export
│   ├── waitlist.py                 # Waitlist management
│   ├── oauth.py                    # OAuth 2.0 (Google, Microsoft)
│   └── __init__.py
│
├── templates/
│   ├── base.html                   # Base template with nav, header, footer
│   ├── landing.html                # Landing page
│   ├── login.html                  # Login/register modal
│   ├── live.html                   # Main live coaching interface
│   ├── dashboard.html              # Session history and analytics
│   ├── profiles.html               # Profile management
│   ├── training.html               # Training scenarios
│   ├── coach.html                  # Coach module
│   ├── admin_ewb.html              # EWB prompt admin UI
│   ├── session_detail.html         # Session replay and analysis
│   └── ... (other admin, settings templates)
│
├── static/
│   ├── app.js                      # Core frontend logic: WebSocket, polling, event handlers
│   ├── live.js                     # Live coaching interface JS (hints, buttons, UI updates)
│   ├── training.js                 # Training scenario JS (persona simulation)
│   ├── pip-launcher.js             # Picture-in-Picture launcher (Phase 06)
│   ├── styles/
│   │   ├── nerve.css               # Main stylesheet (light mode Phase 04.4)
│   │   ├── dashboard.css           # Dashboard-specific styles
│   │   ├── live.css                # Live interface styles
│   │   └── ... (component-specific CSS)
│   └── ... (JS, CSS files)
│
├── logs/
│   └── *.log                       # Session transcripts and analysis logs (generated at runtime)
│
├── tests/
│   ├── test_ewb_pipeline.py        # EWB prompt building tests
│   ├── test_prompt_pipeline.py     # A/B routing and prompt version tests
│   ├── test_phase_08_models.py     # PromptVersion model tests
│   ├── test_ki_logik.py            # Phase classifier tests
│   ├── test_08_5_05_training_pipeline_t1.py  # Training pipeline tests
│   └── services/
│       └── test_ki_logik.py
│
├── .env.example                    # Example environment variables
├── .gitignore                      # Git ignore rules
├── CLAUDE.md                       # Project documentation
└── .planning/
    ├── codebase/                   # This directory (architecture maps)
    │   ├── ARCHITECTURE.md
    │   ├── STRUCTURE.md
    │   ├── STACK.md
    │   ├── INTEGRATIONS.md
    │   ├── CONVENTIONS.md
    │   └── TESTING.md
    └── phases/                     # Phase planning documents
        ├── 08-ewb-quality-profil-tiefe-launch-kritische-prompt-iteration/
        ├── 08.5-universal-response-loop-launch-kritische-erweiterung-des-liv/
        └── ... (other phase directories)
```

## Directory Purposes

**app.py:**
- Purpose: Flask application factory, SocketIO initialization, request context setup
- Contains: Flask() instantiation, Jinja filters (de_currency, markdown), database init, route blueprint registration
- Key functions: _migrate() for DB schema upgrades, _seed_prompt_versions() for Phase 08 setup
- Called at: Application startup (WSGI server entry point)

**config.py:**
- Purpose: Centralized configuration loading from .env
- Contains: API keys (ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY), database URL, audio params, pricing plans, category labels
- Accessed by: All services via `from config import ...`

**database/:**
- **db.py:** Connection and session management
  - Exports: `engine`, `SessionLocal`, `Base`, `get_session()` context manager
  - Creates SQLite engine or uses DATABASE_URL env var
  - Called by: All data access layers
  
- **models.py:** SQLAlchemy ORM models
  - User, Organisation, Profile, ConversationLog, Session, DbSession, TrainingScenario, FtAssistantEvent, PromptVersion, etc.
  - Relationships: Organisation → Users, Users → Profiles, Sessions → ConversationLogs
  - Key columns: Profile.daten (JSON), ConversationLog.details (JSON), PromptVersion.prompt_text, FtAssistantEvent.*

**services/:**

- **claude_service.py:** Core Claude API integration
  - Main functions: `analysiere_mit_claude()`, `analysiere_mit_claude_streaming()`, `gebrauche_coaching_prompt()`, `analyse_loop()`, `coaching_loop()`
  - Helpers: `_build_system_prompt()` (legacy, DEAD), `_build_coaching_prompt()`, `_parse_json()`, `_write_ft_assistant_event()`
  - Threaded entry points: `analyse_loop()` and `coaching_loop()` (continuous loops waiting on events)

- **prompt_pipeline.py:** Phase 08 A/B routing
  - Main functions: `resolve_prompt_version(module, user_id)`, `build_profile_context(user_id)`, `log_pipeline_event()`
  - Caches: `_RESOLVER_CACHE`, `_VARIANTS_CACHE`
  - Deterministic routing via `user_id % len(variants)` with ENV override safety net
  - Called by: EWB-module (analyse_loop) and training modules

- **ewb_pipeline.py:** EWB prompt assembly
  - Main function: `build_ewb_prompt(profile_data, anrede, version, user_id)`
  - Helper: `_load_prompt_template(version)` (loads from PromptVersion DB, fallback to _FALLBACK_V1_PROMPT)
  - Called by: analyse_loop (via analysiere_mit_claude) and streaming variant

- **live_session.py:** Global session state and thread-safe access
  - Global state dicts: `state`, `transcript_buffer`, `conversation_log`, `coaching_buffer`, `session_meta`, etc.
  - Locks: `state_lock`, `buffer_lock`, `coaching_lock`, `log_lock`, `kb_lock`, `phase_lock`, `speech_lock`, etc.
  - Main functions: `reset_session()`, `set_active_profile()`, `update_kaufbereitschaft()`, `record_ewb_click()`
  - Called by: All services, routes, and background threads

- **deepgram_service.py:** Real-time STT transcription
  - Main function: `handle_start_live_session(user_id, profile_id, etc.)`
  - Handles Deepgram streaming, transcript buffering, speaker detection, session metadata
  - Writes to: `transcript_buffer`, `state` (user_id, session_anrede, precall_briefing, ft_session_id, etc.)
  - Entry point: Called from `/api/start_live_session` route

- **training_service.py:** Training scenario execution
  - Functions: `build_customer_prompt()`, `build_sekretaerin_prompt()`, `build_personality_prompt()`, `generate_response()`
  - Handles persona simulation, LLM-based training conversations
  - Called from: `/api/training/run_scenario` route

- **coaching_service.py:** Coach tips and learning cards
  - Functions: `get_active_cards(user_id)` (D-09 learning cards)
  - Called by: analyse_loop when injecting active_learning_cards into context

- **precall_service.py:** PreCall briefing generation
  - Main function: `generate_precall_briefing(user_email, profile_name, org_context)`
  - Called by: `deepgram_service.handle_start_live_session()` at session start

- **qa_pipeline.py:** Quality assurance dispatch (Phase 08.5)
  - Main function: `_qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio)`
  - Dispatches to QA modules when kw_fired_for_line != line_id (D-02 guard)
  - Called by: analyse_loop after analysis complete

- **einwand_keyword_matcher.py:** Pattern-based objection detection (Phase 06.2)
  - Class: `EinwandKeywordMatcher`
  - Used by: deepgram_service to detect objections in real-time, set `state['kw_fired_for_line']`

- **ki_logik.py:** Phase classification and readiness scoring
  - Functions: `classify_phase()`, `detect_phase()`, `compute_readiness_score()`
  - Called by: analyse_loop periodically (every 5th cycle) and for score computation

**routes/:**

- **app_routes.py:** Main application routes
  - `GET /` - Landing/redirect
  - `GET /live` - Live coaching interface
  - `POST /api/start_live_session` - Initialize session (calls deepgram_service)
  - `POST /api/end_session` - Finalize session
  - `GET /api/ergebnis` - Polling endpoint for current state
  - `POST /api/analyse_line` - Manual EWB button click handling
  - `POST /api/status` - Session status

- **auth.py:** Authentication routes
  - `POST /login` - User login
  - `POST /register` - User registration
  - `GET /logout` - Logout
  - `GET /check_session` - Session validity check

- **profiles.py:** Profile CRUD
  - `GET /profiles` - List user's profiles
  - `POST /api/profile/create` - Create profile
  - `POST /api/profile/{id}/update` - Update profile
  - `POST /api/profile/{id}/duplicate` - Clone profile
  - `POST /api/profile/{id}/delete` - Delete profile
  - `GET /api/profile/{id}` - Get profile details

- **training.py:** Training scenarios
  - `GET /training` - Training overview
  - `POST /api/training/scenarios` - List scenarios
  - `POST /api/training/run_scenario` - Start training (calls training_service)

- **dashboard.py:** Analytics and history
  - `GET /dashboard` - Session history, stats
  - `GET /api/session/{id}` - Session detail view
  - `POST /api/sessions/search` - Search sessions

- **Other routes:** coach, learning, admin_*, organizations, payments, feedback, onboarding, etc.

**templates/:**

- **live.html:** Main live coaching interface
  - Components: Status display, hints/buttons, transcript view, coaching tips
  - JavaScript: Fetches via polling, WebSocket listeners, event handlers
  - Depends on: `static/live.js`, `static/app.js`

- **dashboard.html:** Session history and analytics
  - Components: Session list, filters, detail view, download logs
  - JavaScript: Tabular display, search, export

- **base.html:** Layout wrapper
  - Components: Navigation bar, header, footer
  - Jinja blocks: `{% block content %}` for page-specific content

- **Other templates:** login, profiles, training, admin, etc.

**static/:**

- **app.js:** Core frontend logic
  - SocketIO initialization and event handlers
  - Polling interval setup (GET /api/ergebnis every 500ms)
  - Event handlers: start_session, end_session, mute_mic, etc.
  - UI updates: Render hints, buttons, transcript, coaching tips

- **live.js:** Live interface-specific JavaScript
  - Dynamic button rendering (ewb_buttons from state)
  - Hint display logic, category styling
  - Button click handlers for EWB selection

- **training.js:** Training interface
  - Persona simulation handling
  - Response generation and display
  - Conversation flow management

- **pip-launcher.js:** Picture-in-Picture (Phase 06)
  - Slot management, token streaming display
  - Early einwand detection and callback

- **styles/:** CSS files
  - **nerve.css:** Main stylesheet with light mode (Phase 04.4)
  - Component-specific: live.css, dashboard.css, etc.

**logs/:**
- Location: `os.path.join(os.path.dirname(...), 'logs')`
- Contents: Generated at session end by `_build_log_content()` in live_session.py
- Format: Plain text transcripts with metadata, analysis results, latencies

**tests/:**
- Test location pattern: Co-located or in tests/ directory
- Test files: test_*.py, *_test.py patterns
- Runners: pytest, coverage support

## Key File Locations

**Entry Points:**
- `app.py` - Application startup (WSGI entry)
- `routes/app_routes.py` lines 1-120 - HTTP route registration and /live handler
- `services/deepgram_service.py` lines 280-360 - Session initialization (start_live_session)

**Configuration:**
- `config.py` - Environment variable loading
- `.env` - Runtime secrets (API keys, DATABASE_URL)
- `database/models.py` - Schema definition

**Core Logic:**
- `services/claude_service.py` lines 630-850 - Prompt building and API calls (analysiere_mit_claude)
- `services/live_session.py` lines 104-137 - State dict definition and thread-safe access
- `services/prompt_pipeline.py` lines 31-107 - A/B routing and profile context assembly

**Prompt Pipelines:**
- **EWB (ACTIVE):** `services/ewb_pipeline.py` → `build_ewb_prompt()`
- **Coaching (LEGACY):** `services/claude_service.py` line 404 → `_build_coaching_prompt()`
- **Dead code:** `services/claude_service.py` line 265 → `_build_system_prompt()` (not called in live loop)

**Testing:**
- `tests/test_ewb_pipeline.py` - EWB prompt tests
- `tests/test_prompt_pipeline.py` - A/B routing tests
- `tests/test_phase_08_models.py` - PromptVersion model tests

## Naming Conventions

**Files:**
- Services: `{domain}_service.py` (claude_service.py, training_service.py, deepgram_service.py)
- Routes: `{domain}.py` (auth.py, profiles.py, training.py)
- Utilities: `{name}_utility.py` or just `{name}.py` (config.py, audit.py)
- Patterns: Lowercase with underscores, no CamelCase for files

**Directories:**
- Domain-based: `services/`, `routes/`, `templates/`, `static/`, `database/`, `tests/`
- Logical grouping: No nested domain subdirectories (all routes in routes/, all services in services/)
- Special: `.planning/` for documentation, `logs/` for generated logs

**Functions:**
- Private/internal: `_function_name()` or `_helper_name()`
- Public/service: `action_noun()` e.g., `analysiere_mit_claude()`, `start_training_session()`
- Async/threaded: `_loop()` suffix e.g., `analyse_loop()`, `coaching_loop()`
- Builders: `build_*()` e.g., `build_ewb_prompt()`, `build_profile_context()`
- Loaders: `_load_*()` e.g., `_load_prompt_template()`

**Variables:**
- Session state: `ls` (imported live_session), `ls.state`, `ls.conversation_log`
- Locks: `{domain}_lock` e.g., `state_lock`, `buffer_lock`, `log_lock`
- Events: `{trigger}_trigger` e.g., `analyse_trigger`, `coaching_trigger`
- German domain concepts: `einwaende`, `gegenargument`, `kaufbereitschaft`, `schnierzen`, `phasen`
- English/German mix: `user_id`, `user_email`, `profile_name`, `kontext` (German for context in Claude context)

**Types (Python):**
- Models: PascalCase e.g., `User`, `Organisation`, `Profile`, `ConversationLog`
- Dicts (JSON-like): lowercase keys with underscores e.g., `{'einwand_typ': '...', 'intensitaet': '...'}`

## Where to Add New Code

**New Feature (EWB-related):**
- Primary code: `services/claude_service.py` (new function in analyse_loop flow) or `services/ewb_pipeline.py` (new prompt logic)
- Tests: `tests/test_ewb_pipeline.py`
- Route if needed: `routes/app_routes.py`

**New Service Module:**
- Implementation: `services/{domain}_service.py`
- Export main functions and module-level objects
- Import and use in routes or other services
- Example: `from services.{domain}_service import {function_name}`

**New Route/Endpoint:**
- HTTP: `routes/{domain}.py` (create new blueprint or add to existing)
- WebSocket: Emit/on handlers in `app.py` or route file
- Register blueprint in `app.py` line ~150: `app.register_blueprint(...)`
- Test: `tests/test_{domain}_routes.py`

**New Database Model:**
- Add to `database/models.py`
- Inherit from `Base`
- Define columns, relationships, constraints
- Run migration via `_migrate()` in `app.py` if adding to existing table

**New Template:**
- Location: `templates/{name}.html`
- Inherit from `base.html` with `{% extends "base.html" %}`
- Jinja filters available: `{{ value | de_currency }}`, `{{ text | markdown | safe }}`
- Include JavaScript: `<script src="{{ url_for('static', filename='...js') }}"></script>`

**New Static Asset (JS/CSS):**
- Location: `static/{name}.js` or `static/styles/{name}.css`
- Import in template: `<script src="{{ url_for('static', filename='...js') }}"></script>`
- Cache-busting: Use `{{ static_mtime('...js') }}` for mtime-based versioning

**Utilities:**
- Shared helpers: `services/{util_name}.py` or add to existing service
- Config constants: Add to `config.py`
- DB helpers: Add methods to models or in `database/db.py`

## Special Directories

**`.planning/codebase/`:**
- Purpose: Architecture and code structure documentation
- Generated: By `/gsd-map-codebase` command
- Committed: Yes, part of repository
- Contents: ARCHITECTURE.md, STRUCTURE.md, STACK.md, INTEGRATIONS.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

**`.planning/phases/`:**
- Purpose: Phase planning documents (requirements, implementation notes, progress)
- Generated: By `/gsd-plan-phase` and `/gsd-execute-phase` commands
- Committed: Yes, part of repository
- Contents: Phase-specific markdown files with requirements, tasks, status

**`logs/`:**
- Purpose: Generated session transcripts and analysis logs
- Generated: At session end by `/api/end_session` handler
- Committed: No (added to .gitignore)
- Format: Plain text, one file per session with metadata and full conversation log

**`tests/`:**
- Purpose: Unit and integration tests
- Generated: By developer via pytest
- Committed: Yes, part of repository
- Coverage: Key modules (claude_service, prompt_pipeline, ewb_pipeline, models)

---

*Structure analysis: 2026-04-24*
