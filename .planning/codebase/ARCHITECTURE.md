# Architecture

**Analysis Date:** 2026-04-24

## Pattern Overview

**Overall:** Multi-threaded event-driven architecture with thread-safe shared state, serving real-time sales coaching via WebSocket.

**Key Characteristics:**
- Three parallel background threads process audio → transcription → AI analysis → coaching recommendations
- Centralized shared state (`live_session.state`) with thread-safety via locks; all cross-thread communication flows through this dict
- Flask Blueprint-based modular routing with SocketIO for bidirectional client-server updates
- Prompt pipeline with A/B routing (via `resolve_prompt_version`) and template-based system prompts
- Database-backed multi-tenant organization model with role-based access control
- Session-level context inheritance: transcripts → active profile → Claude prompts → hints

## Layers

**Presentation Layer (Frontend):**
- Purpose: Serve HTML templates, handle client-side interactivity, display real-time coaching hints via WebSocket
- Location: `templates/` for Jinja2 templates, `static/` for JavaScript and CSS
- Contains: Dashboard, live coaching interface, training scenarios, profile management UIs
- Depends on: Flask route handlers, WebSocket events from socketio
- Used by: Web browsers via HTTP and WebSocket connections

**Application/Routes Layer:**
- Purpose: Expose HTTP endpoints and Socket.IO events for client-server communication; orchestrate business logic
- Location: `routes/` directory with blueprint modules (auth.py, app_routes.py, profiles.py, training.py, coach.py, etc.)
- Contains: Login, session control, profile CRUD, live session start/end, dashboard queries, training execution
- Depends on: Database models, service layer, auth decorators
- Used by: Frontend JavaScript via HTTP and WebSocket

**Business Logic Layer (Services):**
- Purpose: Core business logic for transcription, AI analysis, coaching, training, and session management
- Location: `services/` directory
- Contains:
  - `claude_service.py` - Prompt building and Claude API calls (analysis, coaching, auto-variante streaming)
  - `prompt_pipeline.py` - Prompt version routing (A/B via ENV override or user_id % variants)
  - `ewb_pipeline.py` - EWB-module-specific prompt assembly from templates
  - `live_session.py` - Global session state, thread-safe locks, helper functions for state updates
  - `deepgram_service.py` - Real-time speech-to-text transcription pipeline
  - `training_service.py` - Training scenario logic, persona simulation, LLM-based training conversations
  - `coaching_service.py` - Coach tips, learning cards, recommendation logic
  - `precall_service.py` - Pre-call research and briefing text generation
  - `qa_pipeline.py` - Quality assurance and follow-up question dispatch
  - `einwand_keyword_matcher.py` - Pattern matching for objection detection via keywords
  - Other utilities: audit, cost_tracker, crm_service, feedback_service, etc.
- Depends on: Config, database models, external APIs (Deepgram, Anthropic)
- Used by: Routes and background threads

**Database Layer:**
- Purpose: Persist organizational data, user profiles, conversation logs, session metadata
- Location: `database/db.py` for connection and session management; `database/models.py` for SQLAlchemy ORM models
- Contains: SQLAlchemy models (Organisation, User, Profile, Session, ConversationLog, TrainingScenario, PromptVersion, FtAssistantEvent, etc.)
- Depends on: SQLAlchemy ORM, SQLite or configured DATABASE_URL
- Used by: All route handlers and service layer functions

**Configuration Layer:**
- Purpose: Environment-based settings and application constants
- Location: `config.py` and `.env` file
- Contains: API keys, database URL, audio parameters (SAMPLE_RATE, CHUNK_SIZE, ANALYSE_INTERVALL, MERGE_WINDOW_S, SPEAKER_DEBOUNCE_S), pricing plans, category labels, phase names
- Depends on: python-dotenv for environment variable loading
- Used by: All layers

**Background Processing Threads:**
- Purpose: Asynchronous processing of audio, transcription, analysis, and coaching
- Entry points: `analyse_loop()`, `coaching_loop()`, and microphone input handling
- Pattern: Event-driven with threading.Event triggers, thread-safe access to shared state via locks
- Details: See Data Flow section below

## Data Flow

**Live Session Architecture (Thread-Safe State Machine):**

Centralized in `live_session.py` with thread-safe locks around all shared state:

```
┌─────────────────────────────────────────────────────────┐
│         live_session.state (dict, thread-safe)          │
│  Protected by live_session.state_lock                   │
│                                                          │
│  Core fields:                                            │
│    • version (int) - Incremented on each analysis       │
│    • aktiv (bool) - Analysis in progress                │
│    • ergebnis (dict) - Latest Claude analysis result    │
│    • line_id (str) - ID of current transcript line      │
│    • kaufbereitschaft (int) - 5-100, readiness score    │
│    • current_phase (int 1-6) - Conversation phase       │
│    • readiness_score/bucket - Phase 04.8 deterministic  │
│    • active_hint (dict) - Ranked single hint to show    │
│    • ewb_buttons (list) - Dynamic objection buttons     │
│    • active_learning_cards (list) - Coach learning      │
│    • precall_briefing (str) - Research context inject   │
│    • user_id (int) - Session user, set by deepgram_srv  │
│    • session_anrede (str) - 'Du'/'Sie', inferred/set    │
│    • ft_session_id - Finetune logging session ID        │
│    • kw_fired_for_line (str) - D-02 QA guard           │
│    • slot1_variant_busy_until (float) - Anti-overlap    │
│    • mic_muted (bool) - Mute state                      │
│    • mode (str) - 'cold_call' or 'meeting'             │
│    • market, language - Locale for finetune logs        │
└─────────────────────────────────────────────────────────┘
```

**Three-Thread Processing Pipeline:**

1. **STT Thread (Deepgram input handler):**
   - Captures microphone audio chunks via WebRTC
   - Sends to Deepgram streaming API
   - On transcript segment: writes to `transcript_buffer` under `buffer_lock`
   - Sets `analyse_trigger` event to wake analyse_loop
   - Keyword matcher runs in this thread (Phase 06.2): checks for objection patterns, writes `kw_fired_for_line` to state

2. **analyse_loop() Thread (EWB - Einwand Analysis):**
   - Waits on `analyse_trigger` event (timeout: ANALYSE_INTERVALL = 2s)
   - Reads `transcript_buffer` under `buffer_lock`, clears it
   - Builds context from `analysiert_bisher` (last 20 analyzed segments)
   - **Prompt call:** `analysiere_mit_claude()` or `analysiere_mit_claude_streaming()`
     - Uses `resolve_prompt_version('ewb', user_id)` to route to A/B variant
     - Calls `build_ewb_prompt()` with resolved version
     - Sends to Claude Haiku with profile context + active learning cards
   - Parses JSON response: einwand (true/false), typ, intensitaet, gegenargument_1/_2, optional score signals
   - Updates `state['ergebnis']`, `state['version']`, `state['kaufbereitschaft']`
   - Logs to `conversation_log` and `gegenargument_log`
   - Phase-classifier runs every 5th cycle via `classify_phase()` (optional)
   - Readiness-score computation via `compute_readiness_score()` (optional, Phase 04.8)
   - **QA Dispatch:** Calls `_qa_pipeline_dispatch()` when `kw_fired_for_line != line_id` (D-02 guard)
   - **FT Logging:** Writes assistant_event via `_write_ft_assistant_event()`

3. **coaching_loop() Thread (Live Coaching Tips):**
   - Waits on `coaching_trigger` event
   - Reads `coaching_buffer` under `coaching_lock`, clears it
   - **Prompt call:** `gebrauche_coaching_prompt()` (uses legacy `_build_coaching_prompt()`)
     - System prompt reads from `active_profile_data` directly, not EWB-pipeline
     - Sends to Claude Haiku with purchase signals, conversation phases
   - Parses: tipp (string), kategorie (frage/signal/redeanteil/uebergang/lob), painpoint, kb_delta
   - Updates `state['kaufbereitschaft']` with kb_delta
   - Appends to `coaching_buffer` (displayed as coach tips on UI)
   - Stores painpoints in `painpoints` (dedup via `ist_painpoint_duplikat()`)

**Prompt Building Call Chains:**

**EWB (Einwand-Analyse) Path (ACTIVE in analyse_loop):**
```
analyse_loop()
  ↓
analysiere_mit_claude() or analysiere_mit_claude_streaming()
  ├─ resolve_prompt_version('ewb', user_id)  # A/B router (ENV override or user_id % variants)
  │   └─ returns version string ('v1-legacy', 'v2-modular', or 'unknown')
  ├─ build_ewb_prompt(profile_data=None, anrede=..., version=..., user_id=...)
  │   ├─ _load_prompt_template(version)  # Loads from PromptVersion DB, fallback to _FALLBACK_V1_PROMPT
  │   ├─ build_profile_context(user_id)  # Shared D-40 utilities: basis fields, eigene_formulierungen, beweise, anrede
  │   └─ combines template + profile context into system prompt
  └─ claude_client.messages.create(system=_system_prompt, messages=[...])
```

**Coaching Path (LEGACY, runs separately in coaching_loop):**
```
coaching_loop()
  ↓
gebrauche_coaching_prompt()
  ├─ _build_coaching_prompt()  # Reads active_profile_data directly (NOT via pipeline)
  │   ├─ Gets basis, zielgruppe, schmerzen, kaufsignale, uebergaenge, wettbewerber, phasen
  │   └─ Constructs COACHING_PROMPT_BASE + profile fields
  └─ claude_client.messages.create(system=_system_prompt, messages=[...])
```

**Training Path (OFF-MAIN-THREAD, started from routes/training.py):**
```
POST /api/training/run_scenario
  ↓
start_training_session()
  ├─ build_customer_prompt(profile_data, schwierigkeit, persona, sprache)
  ├─ build_sekretaerin_prompt(persona, sprache)
  ├─ build_personality_prompt(profile_data, personality_data, ...)
  └─ Each sends to claude_client.messages.create() sequentially (NOT streaming)
```

**PreCall Briefing Path (Called at session start):**
```
POST /api/start_live_session (deepgram_service.py)
  ↓
generate_precall_briefing(user_email, profile_name, org_context)
  ├─ Claude API call with system prompt
  └─ Result stored in ls.state['precall_briefing']
  └─ Injected into EWB prompts via build_profile_context() (D-40)
```

**Dead Code Analysis:**
- `_build_system_prompt()` in claude_service.py (line 265): **DEAD** — Not called anywhere in live request path
  - Was used by legacy pipeline before Phase 08 EWB integration
  - Still used in some unit tests and fallback logic, but NEVER by analyse_loop
  - analyse_loop exclusively uses `build_ewb_prompt()` via `resolve_prompt_version()` routing

**Key Abstractions:**

**Session State (live_session.state):**
- Purpose: Single source of truth for current live session, shared across all threads
- Pattern: Thread-safe dict + lock pattern, event-driven triggers via threading.Event
- Read: All threads check fields; e.g., analyse_loop reads `user_id`, `session_anrede`, `kw_fired_for_line`
- Write: Each thread writes to specific fields (see Field Writers/Readers below)

**Active Profile (live_session.active_profile_data):**
- Purpose: Encapsulate sales methodology, objections, counter-arguments, phases as JSON
- Examples: `Profile.daten` column stores complete profile JSON
- Pattern: Profile loaded at session start via `set_active_profile()`, provides context to Claude prompts
- Structure: Contains `basis` (unternehmen, produktbeschreibung, usps, konsequenz, etc.), `einwaende`, `phasen`, `gegenargumente`, `ki` (ton, ansprache, sensitivitaet), `kaufsignale`, `schmerzen`, `wettbewerber`

**Conversation Log (live_session.conversation_log):**
- Purpose: Persistent record of a sales conversation with analysis results
- Pattern: Created per session, updated incrementally by analyse_loop and coaching_loop, finalized at `/api/end_session`
- Structure: List of dicts with keys: ts, type ('transcript', 'analyse', 'coaching', 'latenz_coaching', 'korrektur', 'painpoint', 'tipp'), speaker, text, data

**Keyword Matcher (live_session.get_matcher(sid)):**
- Purpose: Session-scoped pattern matching for objection detection (Phase 06.2)
- Pattern: Lazy-init, dropped at session end via `drop_matcher(sid)`
- Called from deepgram_service to detect objections in real-time, set `state['kw_fired_for_line']` to trigger QA-pipeline

**Blueprint Organization (Modular Routing):**
- Examples: `auth_bp`, `app_routes_bp`, `dashboard_bp`, `training_bp`, `coach_bp`, `profiles_bp`
- Pattern: Each blueprint in separate route file, imported and registered in `app.py`
- Responsibility separation: auth handles login/logout, profiles handles CRUD, app_routes handles live session control

## Entry Points

**HTTP Entry Points:**

**`GET /` (app_routes.py):**
- Location: `routes/app_routes.py`
- Triggers: Page load or redirect from login
- Responsibilities: Check auth, route to landing page or `/live`, render template

**`GET /live` (app_routes.py, @login_required):**
- Location: `routes/app_routes.py`
- Triggers: User navigates to live coaching interface
- Responsibilities: Render live.html template with session context, SocketIO client initialization

**`POST /api/start_live_session` (deepgram_service.py):**
- Location: `routes/app_routes.py` → calls `handle_start_live_session()` from `services/deepgram_service.py`
- Triggers: User clicks "Start Call" on live interface
- Responsibilities:
  - Generate PreCall briefing via Claude (optional)
  - Initialize live_session state: set user_id, session_anrede, active profile, ft_session_id
  - Start WebRTC microphone capture and Deepgram streaming
  - Launch analyse_loop and coaching_loop background threads
  - Emit `session_started` WebSocket event

**`GET /api/ergebnis` (app_routes.py, polling endpoint):**
- Location: `routes/app_routes.py`
- Triggers: Frontend polls every ~500ms
- Responsibilities: Return current `ls.state` (version, ergebnis, kaufbereitschaft, current_phase, active_hint, etc.)

**`POST /api/end_session` (app_routes.py):**
- Location: `routes/app_routes.py`
- Triggers: User clicks "End Call"
- Responsibilities: Finalize session, persist conversation_log to DB, reset live_session state

**`POST /api/analyse_line` (app_routes.py):**
- Location: `routes/app_routes.py`
- Triggers: Manual EWB button click (user selects a response variant)
- Responsibilities: Record gegenargument selection, update kb tracking, emit UI feedback

**WebSocket Entry Points (Socket.IO):**

- `transcript`: Server emits final transcriptions with speaker label
- `coaching`: Server emits coaching tips and recommendations
- `pip_token`: Server emits Claude response tokens during streaming (Phase 06, PiP mode)
- Client can emit: `start_session`, `end_session`, `mute_mic`, `pause`, `resume`, etc.

**Background Thread Entry Points:**

**`analyse_loop()` (claude_service.py):**
- Started as daemon thread in `handle_start_live_session()`
- Runs continuously, waits on `ls.analyse_trigger` event
- Calls `analysiere_mit_claude()` or `analysiere_mit_claude_streaming()` when transcript buffer has content

**`coaching_loop()` (claude_service.py):**
- Started as daemon thread in `handle_start_live_session()`
- Runs continuously, waits on `ls.coaching_trigger` event
- Calls `gebrauche_coaching_prompt()` when coaching buffer has content

## Error Handling

**Strategy:** Defensive with silent fallbacks; never crash the live loop or HTTP thread

**Patterns:**

**Database Errors:** Try-finally blocks close sessions, constraints handled at ORM level
- `routes/auth.py` lines 46-80: `_do_login()` catches DB errors, returns (None, error_msg)
- `services/live_session.py` lines 311-413: `reset_session()` catches and silently swallows lock errors

**API Errors (Claude, Deepgram, ElevenLabs):** Try-except with fallback JSON
- `claude_service.py` lines 679-701: `analysiere_mit_claude()` catches API errors, returns parsed or empty dict
- `deepgram_service.py`: Handles streaming errors, continues if single chunk fails

**Prompt Loading Errors:** Fallback to _FALLBACK_V1_PROMPT
- `ewb_pipeline.py` lines 73-89: `_load_prompt_template()` returns fallback if DB miss or error
- `prompt_pipeline.py` lines 55-97: `_load_active_variants()` returns ['unknown'] if DB fails

**FT Logging Errors:** Never raise, swallow all exceptions
- `claude_service.py` lines 125-203: `_write_ft_assistant_event()` catches all exceptions, prints to log
- `prompt_pipeline.py` lines 228-255: `log_pipeline_event()` catches all exceptions, no raise

**Audio Errors:** Graceful degradation, continue without audio
- `deepgram_service.py`: Handles streaming connection loss, emits error to client

**Authentication:** `login_required` decorator checks session before route execution, redirects to login
- `services/auth_decorators.py`: Validates user_id in session, attaches to Flask `g` object

**Business Logic:** Explicit None checks, defensive get() with defaults
- `live_session.py` lines 227-244: `stabilize_speaker()` handles None input, returns confirmed or pending
- `einwand_keyword_matcher.py`: Pattern matching with fallback to "no match"

## Cross-Cutting Concerns

**Logging:** Print statements to stdout with `[PREFIX]` tags (development logging)
- Usage: `[Claude-1]`, `[DG]`, `[AI]`, `[DB]`, `[FT]`, `[EWB]`, `[PiP-Stream]`, `[Phase08]`
- Severity: Informational only, no exceptions logged by default
- SQL logging can be enabled via SQLAlchemy config

**Validation:**
- ORM-level constraints: nullable, unique, ForeignKey
- Deepgram results validated to contain `transcript` and `speaker` fields
- Claude responses validated as JSON before parsing via `_parse_json()`
- User input validated in route handlers: email format for signup, etc.

**Authentication & Authorization:**
- Session-based with Flask session middleware
- User ID stored in `session['user_id']`, checked by `login_required` decorator
- User object attached to `g` for request-local access
- Password hashing via Werkzeug `generate_password_hash()` and `check_password_hash()`
- Role-based: owner, admin, member on users; organization-based data isolation
- Routes check `g.user.rolle` for admin/owner-only features
- All queries filtered by `org_id` to prevent cross-organization data leakage
- Profile access limited to profiles matching user's `org_id`

**Thread Safety:**
- All shared state protected by locks (state_lock, buffer_lock, coaching_lock, etc.)
- No global variables without lock protection
- Event-driven coordination via threading.Event
- Pattern: acquire lock → read/write → release lock (via `with` statement)
- Atomicity guaranteed within lock region, but cross-lock operations must be careful (e.g., reading user_id, then accessing profile under separate lock)

---

*Architecture analysis: 2026-04-24*
