# Architecture

**Analysis Date:** 2026-03-30

## Pattern Overview

**Overall:** Layered Flask application with real-time WebSocket-driven event processing architecture

**Key Characteristics:**
- Three parallel background threads processing audio transcription, AI analysis, and coaching in real-time
- Shared state management via thread-safe locks for coordination between async tasks
- Database-backed multi-tenant organization model with user roles and profile systems
- Real-time client-server updates via Socket.IO for live sales coaching delivery
- Modular blueprint-based routing separating concerns (auth, profiles, live sessions, training, dashboard)

## Layers

**Presentation Layer:**
- Purpose: Serve HTML templates and handle client-side interactivity
- Location: `templates/` for HTML, `static/app.js` for frontend logic
- Contains: Jinja2 templates for dashboard, landing page, app interface, settings
- Depends on: Flask render_template, routes providing context data
- Used by: Web browsers via HTTP and WebSocket

**API Layer:**
- Purpose: Expose HTTP and Socket.IO endpoints for frontend communication and data updates
- Location: `routes/` directory containing multiple blueprint modules
- Contains: Login, profile management, live session control, dashboard, training, coaching, organization, settings
- Depends on: Database models, service layer, auth decorators
- Used by: Frontend JavaScript and browser API calls

**Service Layer:**
- Purpose: Core business logic for transcription, AI analysis, coaching recommendations, and session management
- Location: `services/` directory
- Contains:
  - `live_session.py`: Centralized state management with thread-safe buffers for transcripts, coaching tips, analysis results
  - `claude_service.py`: Anthropic Claude API integration for objection detection and coaching
  - `deepgram_service.py`: Real-time speech-to-text transcription via Deepgram WebSocket
  - `training_service.py`: Training scenario execution and feedback handling
  - `crm_service.py`: CRM integrations (if configured)
- Depends on: Config, database, external APIs (Deepgram, Anthropic, ElevenLabs)
- Used by: Routes and background threads

**Database Layer:**
- Purpose: Persist organizational data, user profiles, conversation logs, and session metadata
- Location: `database/db.py` for connection management, `database/models.py` for ORM models
- Contains: SQLAlchemy models for Organisation, User, Profile, Session, ConversationLog, TrainingScenario, etc.
- Depends on: SQLAlchemy, SQLite or configured DATABASE_URL
- Used by: All route handlers and service layer

**Configuration Layer:**
- Purpose: Environment-based settings and application constants
- Location: `config.py`
- Contains: API keys, database URL, audio parameters (sample rate, chunk size), pricing plans, analysis intervals, category labels
- Depends on: .env file via python-dotenv
- Used by: All layers

## Data Flow

**Live Sales Coaching Session:**

1. **Audio Capture** → Deepgram microphone listener starts via `deepgram_starten()` background thread
2. **Transcription** → Deepgram WebSocket emits final transcript segments with speaker detection to `on_message()`
3. **Message Processing** → `on_message()` stores transcript in `live_session.transcript_buffer` and emits Socket.IO `transcript` event to browser
4. **Trigger Analysis** → Sets `analyse_trigger` event when buffer reaches analysis interval threshold
5. **AI Analysis** → `analyse_loop()` thread processes buffered transcripts:
   - Calls `analysiere_mit_claude()` with system prompt and profile context
   - Receives JSON with objection type, intensity, counter-arguments
   - Updates `live_session.state['ergebnis']` with analysis result
   - Increments version for client update detection
6. **Coaching Loop** → `coaching_loop()` thread processes coaching recommendations:
   - Analyzes same segments for dealer tips, pain points, buying readiness delta
   - Stores in `coaching_buffer`
   - Emits Socket.IO `coaching` event
7. **Browser Updates** → Frontend polls `/api/ergebnis` every ~500ms for new analysis results and updates UI with cards

**Conversation Logging:**

1. All transcript segments stored in `live_session.conversation_log` (in-memory)
2. User feedback and session metrics captured at end via `/api/end_session`
3. Data persisted to `ConversationLog` database table with aggregated metrics
4. Analysis history and corrections stored for feedback loop

**State Management:**

- Centralized in `live_session.py` with thread-safe locks around all shared state:
  - `state_lock`: Protects analysis results and version counter
  - `buffer_lock`: Protects transcript and analysis buffers
  - `coaching_lock`: Protects coaching recommendations
  - Prevents race conditions between Deepgram, analysis, and coaching threads

## Key Abstractions

**Session State (live_session):**
- Purpose: Single source of truth for current live session state, shared across threads
- Examples: `state`, `transcript_buffer`, `conversation_log`, `coaching_buffer`, `session_meta`
- Pattern: Thread-safe dictionary + lock pattern, event-driven triggers via threading.Event

**Profile System:**
- Purpose: Encapsulate sales methodology, objections, counter-arguments, phases as JSON
- Examples: `Profile` model stores JSON in `daten` column
- Pattern: Profile loaded at session start into `live_session.set_active_profile()`, provides context to Claude prompts
- Structure: Contains `einwaende` (objections), `phasen` (call phases), `gegenargumente` (counter-arguments), `ki` (AI tone/style), `kaufsignale` (buying signals)

**Conversation Log:**
- Purpose: Persistent record of a sales conversation with analysis results
- Examples: `ConversationLog` model, structured logs include speaker, transcript, timing, objection counts
- Pattern: Created per session, updated incrementally, finalized at `/api/end_session`

**Blueprint Organization:**
- Purpose: Modular routing by domain concern
- Examples: `auth_bp`, `profiles_bp`, `app_routes_bp`, `dashboard_bp`
- Pattern: Each blueprint in separate route file, imported and registered in `app.py`

## Entry Points

**Web Application:**
- Location: `app.py` line 21-25 (Flask initialization)
- Triggers: `python app.py` or WSGI server startup
- Responsibilities:
  - Initialize Flask app with SocketIO support
  - Set up database and migrations
  - Seed initial data (NERVE Alpha org, demo profiles, training scenarios)
  - Register blueprints
  - Start background threads (Deepgram, analysis, coaching)
  - Run WSGI server on port 5000

**Frontend Routes:**
- `/` → Landing page (public, or redirect to login/dashboard)
- `/live` → Main live coaching interface (`@app_routes_bp.route('/live', @login_required)`)
- `/dashboard` → Overview and history
- `/training` → Training scenarios
- `/profiles` → Profile management
- `/onboarding` → User onboarding flow

**API Endpoints:**
- `/api/ergebnis` → GET latest analysis result (polling endpoint, ~500ms intervals)
- `/api/analyse_line` → POST analyze a specific transcript line
- `/api/end_session` → POST finalize session and persist logs
- `/api/status` → GET session status
- Various Blueprint routes for auth, profiles, organizations, training

**WebSocket Events (Socket.IO):**
- `transcript` → Server emits final transcriptions with speaker label
- `coaching` → Server emits coaching tips and recommendations
- Client can emit control events (pause, resume, etc.)

## Error Handling

**Strategy:** Layered error handling with graceful degradation

**Patterns:**

- **Database Errors:** Try-finally blocks close sessions, constraints handled at ORM level
- **API Errors:**
  - Deepgram/Claude failures logged to stdout, analysis continues with "Fehler" state
  - Anthropic API rate limits trigger automatic retry with exponential backoff
- **Audio Errors:**
  - PyAudio failures caught in `deepgram_starten()`, logged, thread exits gracefully
  - Frontend detects disconnect, prompts user to reconnect
- **Authentication:** `login_required` decorator checks session before route execution, redirects to login
- **Business Logic:**
  - Fair-use limit checks in `/live` route trigger soft warning (not hard block)
  - Onboarding redirect for incomplete profiles
  - Invalid profile data caught in JSON parsing (returns empty dict fallback)

## Cross-Cutting Concerns

**Logging:**
- Approach: Print statements to stdout (development logging)
- Usage: `[DG]`, `[AI]`, `[DB]` prefixes denote component source
- SQL logging can be enabled via SQLAlchemy config

**Validation:**
- Approach: ORM-level constraints (nullable, unique, ForeignKey)
- Deepgram results validated to contain `transcript` and `speaker` fields
- Claude responses validated as JSON before parsing
- User input validated in route handlers (email format for signup, etc.)

**Authentication:**
- Approach: Session-based with Flask session middleware
- User ID stored in `session['user_id']`, checked by `login_required` decorator
- User object attached to `g` for request-local access
- Token-based sessions in `DbSession` model for API authentication (future use)
- Password hashing via Werkzeug `generate_password_hash()` and `check_password_hash()`

**Authorization:**
- Approach: Role-based (owner, admin, member) on users, organization-based data isolation
- Routes check `g.user.rolle` for admin/owner-only features
- All queries filtered by `org_id` to prevent cross-organization data leakage
- Profile access limited to profiles matching user's `org_id`

---

*Architecture analysis: 2026-03-30*
