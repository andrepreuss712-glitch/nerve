# Architecture

**Analysis Date:** 2026-05-01

## Pattern Overview

**Overall:** Multi-tenant Flask SaaS with three parallel background threads, Socket.IO real-time delivery, and Blueprint-based routing

**Key Characteristics:**
- Three concurrent background threads handle live session processing: Deepgram STT, Claude analysis loop, coaching delivery
- All shared live-session state is centralized in `services/live_session.py` using named `threading.Lock()` guards
- Database-backed multi-tenant isolation: every query is scoped to `org_id`
- Prompt versioning (A/B routing) via `prompt_versions` DB table; per-user deterministic routing in `services/prompt_pipeline.py`
- Model split enforced by config constants: Haiku for latency-critical live loop (`MODEL_ANALYSE`, `MODEL_COACHING`), Sonnet for user-visible output (`MODEL_EWB`, `MODEL_POSTCALL_ANALYSIS`, `MODEL_PRECALL`)

## Layers

**Config:**
- Purpose: All environment-based settings and application constants
- Location: `config.py`
- Contains: API keys, model constants (MODEL_EWB, MODEL_ANALYSE, etc.), DB URL, audio parameters, PLANS dict, KATEGORIE_LABEL, PERSONALIZED_SCRIPTS_CAP
- Depends on: `.env` via `python-dotenv`
- Used by: All other layers

**Presentation (Templates + Static):**
- Purpose: Jinja2 HTML rendering and client-side interactivity
- Location: `templates/` (Jinja2 HTML), `static/` (CSS, JS, fonts)
- Contains: `base.html`, `dashboard.html`, `training.html`, `profile_editor.html`, `session_detail.html`, `landing.html`; PiP launcher at `static/pip-launcher.js`; audio capture at `static/audio-processor.js`; `static/nerve.css` (global styles)
- Depends on: Flask `render_template`, route context dicts, Socket.IO browser client
- Used by: Web browsers via HTTP and WebSocket

**Routing (Blueprints):**
- Purpose: HTTP endpoints organized by domain concern
- Location: `routes/` directory — 20 blueprint modules
- Contains: auth, dashboard, profiles, training, coach, orgs, payments, oauth, admin_dashboard, admin_ewb, feedback, onboarding, settings, legal, changelog, logs_routes, performance, learning, waitlist, app_routes
- Depends on: Service layer, `@login_required` from `routes/auth.py`, `@superadmin_required` from `services/auth_decorators.py`, `g.user` / `g.org` populated by `@app.before_request`
- Used by: Frontend JS and browsers

**Services (Business Logic):**
- Purpose: Core domain logic for transcription, AI analysis, coaching, training, precall, profile schema
- Location: `services/` — 24 modules
- Key modules:
  - `services/live_session.py` — all thread-safe shared state, per-SID profile registry
  - `services/deepgram_service.py` — per-SID Deepgram WebSocket management (`_deepgram_sessions` dict)
  - `services/claude_service.py` — Anthropic API calls: analyse_loop (Haiku), EWB streaming (Sonnet/Haiku circuit-breaker), coaching
  - `services/coaching_service.py` — post-call Sonnet analysis, learning card generation
  - `services/training_service.py` — training dialog via Claude Haiku persona + ElevenLabs TTS
  - `services/precall_service.py` — Brave Search + Claude 3-layer briefing (fields + text + recommendations), 5-min in-memory cache
  - `services/prompt_pipeline.py` — A/B prompt version routing, `build_profile_context()` (9-section profile block)
  - `services/ewb_pipeline.py` — EWB system prompt assembly with profile context
  - `services/profile_schema.py` — Pydantic v2 schema for Profile JSON, versioned `_migrate_profile_data()`
  - `services/ki_logik.py` — readiness score computation, 6-phase classification, hint priority
  - `services/qa_pipeline.py` — classifier + FAQ-match response pipeline (Phase 08.5)
  - `services/einwand_keyword_matcher.py` — low-latency keyword-based objection detection (bypasses analyse_loop)
  - `services/integration_engine.py` — post-session training recommendation routing
  - `services/cost_tracker.py` — per-call API cost logging to `api_cost_log`
  - `services/rate_limiter.py` — Flask-Limiter (per-IP, in-memory; Redis-upgradeable)
  - `services/audit.py` — structured writes to `audit_log` for sensitive actions
- Depends on: `config.py`, `database/`, external APIs (Deepgram, Anthropic, ElevenLabs, Brave, Stripe)
- Used by: Routes and background threads

**Database:**
- Purpose: Persistence for all org, user, profile, session, and log data
- Location: `database/db.py` (engine + session factory), `database/models.py` (ORM models)
- Contains: SQLAlchemy 2.0 declarative models; WAL mode enabled for SQLite concurrency; `scoped_session` for Flask-Admin; `get_session()` returns plain `SessionLocal()` instances
- Depends on: SQLAlchemy 2.0, SQLite (default at `database/nerve.db`) or PostgreSQL via `DATABASE_URL`
- Used by: All route handlers and service layer

**Application Bootstrap (`app.py`):**
- Purpose: Flask app factory, extension init, all Blueprint registration, startup migrations, DB seeds
- Location: `app.py` (~2230 lines)
- Startup sequence: `ProxyFix` → `SocketIO` → `CSRFProtect` → `init_limiter` → `init_db` → `_migrate()` → `_data_migrate()` → `_migrate_profile_json()` → `_migrate_fragen_to_faqs()` → schema batch migration (v4) → `_seed_founder_dashboard_defaults()` → exchange rate scheduler → `_seed_prompt_versions()` → `_seed_ewb_v2()` → `_seed_ewb_scenarios()` → `_seed()` → blueprint imports → blueprint registration → Flask-Admin setup

## Data Flow

**Live Call — Real-Time Path:**
1. Browser captures microphone via `AudioWorkletProcessor` (`static/audio-processor.js`), streams PCM chunks over WebSocket (Socket.IO) to server
2. Socket.IO `start_live_session` event → `app.py` handler loads active profile via `ls.set_profile_for_sid(sid, ...)`, opens Deepgram WebSocket via `deepgram_service.start_deepgram(sid, mode)`
3. Deepgram fires `on_message` callback → final transcripts appended to `ls.transcript_buffer` (under `ls.buffer_lock`) and emitted to browser via `socketio.emit('transcript', ..., room=sid)`
4. Keyword-matcher (`services/einwand_keyword_matcher.py`) fires immediately on each transcript: keyword hit → Haiku EWB call → result emitted via Socket.IO (slot 1 path, `ls.state['kw_fired_for_line']` set to prevent duplicate QA)
5. `analyse_loop` thread reads `transcript_buffer` every `ANALYSE_INTERVALL` seconds (4s), calls Claude Haiku (`MODEL_ANALYSE`) → JSON with `einwand` / `gegenargument` / score flags → updates `ls.state` (under `ls.state_lock`); browser polls `/api/ergebnis` at ~500ms
6. Session end: browser POSTs `/api/beenden` → `ConversationLog` persisted → `coaching_service.generate_postcall_analysis()` (Sonnet) + `integration_engine` for training recommendations

**State Management:**
- All live-session globals in module-level variables of `services/live_session.py`
- Per-SID isolation (Phase 08.19.4): `ls._per_sid_profile[sid]` → `(name, daten)` tuple; `ls._session_state[sid]` → per-SID key-value store; both guarded by `ls._per_sid_lock` / `ls._session_state_lock`
- Global `ls.state` dict (under `ls.state_lock`): `version`, `aktiv`, `ergebnis`, `kaufbereitschaft`, `current_phase`, `readiness_score`, `active_hint`, `ewb_buttons`, `precall_briefing`, `mic_muted`, `kw_fired_for_line`, `slot1_variant_busy_until`
- Circuit-breaker in `claude_service.py`: `_ewb_ttft_history` deque (last 5); if 3/5 exceed threshold → Haiku fallback for `MODEL_PIP_AUTOVAR` for 30 seconds

**PreCall Briefing Path (Phase 08.20):**
1. User fills precall form (Firmenname, Branche, Ansprechpartner + opt. info) in PiP launcher
2. Browser POSTs to `/api/precall/personalize`
3. `precall_service.py`: Brave Search API → raw snippets → Claude structured analysis (3 layers: fields JSON + freetext briefing + recommendations)
4. Results cached in `_briefing_cache` dict for 5 min (key: `(org_id, profile_id, firma_normalized)`)
5. Briefing text injected into `ls.state['precall_briefing']` at session start; personalized opener script generated as `ProfileOpener` row with `parent_id=<original_opener_id>`, `is_personalized=True`, `briefing_source_firma=<firma>`

**Training Path:**
1. User selects scenario + difficulty + voice gender → browser POSTs to training API
2. `training_service.py`: builds persona prompt (Claude Haiku, `MODEL_TRAINING_DIALOG`) with scenario data + personality type
3. ElevenLabs TTS converts AI response to audio; returned as base64 for browser playback
4. Scoring at session end via `training_service.generate_scoring()` (Sonnet, `MODEL_TRAINING_SCORING`)

## Key Abstractions

**Live Session State (`services/live_session.py`):**
- Purpose: Single mutable shared namespace for one live call, accessed by 3+ concurrent threads
- Pattern: Module-level variables + named `threading.Lock()` per logical group (`buffer_lock`, `state_lock`, `log_lock`, `coaching_lock`, `kb_lock`, `pause_lock`, etc.)
- Per-SID profile since Phase 08.19.4: replaces single global active profile; `ls.set_profile_for_sid()` / `ls.get_profile_for_sid()` are the correct accessors
- Reset via `ls.reset_session()` at session start

**Profile (Sales Methodology Container):**
- Purpose: Encapsulates product info, objections, counter-arguments, call phases, buying signals, opener scripts, FAQ entries per customer/product segment
- Storage: `Profile.daten` column (TEXT/JSON), schema versioned (`LATEST_SCHEMA_VERSION` in `services/profile_schema.py`)
- Child tables: `profile_skripte` (call scripts), `profile_opener` (openers; `parent_id` for personalized variants, `is_personalized` flag), `profile_faqs` (FAQ with `mode='ki_generated'|'literal'`)
- Migration: `_migrate_profile_data()` runs batch at startup for all profiles below `LATEST_SCHEMA_VERSION`

**Prompt Version A/B System:**
- Purpose: DB-driven prompt management with per-user deterministic routing; no deploy needed to switch variants
- Location: `services/prompt_pipeline.py::resolve_prompt_version()`, `database/models.py::PromptVersion`
- Priority order: `ENV PROMPT_{MODULE}_VERSION_OVERRIDE` → cached `(module, user_id)` DB lookup (user_id % len(variants)) → fallback `'unknown'`
- Modules managed: `ewb`, `assistant_live`, `coaching_live`, `objection_trigger`, `training_persona`, `classifier`, `qa_response`, `training_kunde`, `training_scoring`

**Blueprint Registry:**
- Pattern: `{name}_bp = Blueprint('{name}', __name__)` registered flat (no URL prefix) in `app.py`
- Verified name mapping: see `routes/CLAUDE.md` — e.g. `organisations.py` uses `orgs_bp` with name `'orgs'`, not `'organisations'`
- All 20 blueprints: `auth`, `dashboard`, `app_routes`, `profiles`, `training`, `coach`, `settings`, `orgs`, `payments`, `onboarding`, `oauth`, `feedback`, `learning`, `logs`, `performance`, `legal`, `changelog`, `waitlist`, `admin_dashboard`, `admin_ewb`

**Multi-Tenant Isolation:**
- Every DB query scoped by `org_id` from `g.org.id`
- Roles on `User.rolle`: `owner` / `admin` / `member`; `User.is_superadmin` for Flask-Admin
- `User.is_coach` grants access to coach dashboard (`routes/coach.py`)

**ConversationLog:**
- Model: `database/models.py::ConversationLog`
- Key columns: `session_mode` (`cold_call`|`meeting`), `precall_briefing` (TEXT), `precall_fields` (JSON TEXT, Phase 08.20.2), `anrede` (`Du`|`Sie`), `result` (`win`|`loss`|`open`), `market`, `language`
- Written atomically at session end via `POST /api/beenden`

## Entry Points

**Application Start:**
- Location: `app.py`
- Triggers: `gunicorn -k eventlet app:app` (production, Hetzner VPS behind Nginx); `python app.py` (dev)
- WSGI: `ProxyFix(app.wsgi_app, x_for=1, x_proto=1)` — required for correct IP detection behind Nginx

**Key HTTP Routes:**
- `GET /` → landing / login redirect — `routes/auth.py`
- `GET /dashboard` → session history and analytics — `routes/dashboard.py` (`dashboard_bp`)
- `GET /training` → training UI — `routes/training.py` (`training_bp`)
- `GET /profiles` → profile list — `routes/profiles.py` (`profiles_bp`)
- `GET /onboarding` → onboarding wizard — `routes/onboarding.py` (`onboarding_bp`)
- `POST /api/beenden` → end live session, persist `ConversationLog` — `routes/app_routes.py` (`app_routes_bp`)
- `GET /api/ergebnis` → poll latest analysis result (browser polls ~500ms) — `routes/app_routes.py`
- `POST /api/einwand` → manual EWB trigger — `routes/app_routes.py`
- `POST /stripe/webhook` → Stripe events, CSRF-exempt — `routes/payments.py` (`payments_bp`)
- `GET /auth/google/callback`, `GET /auth/microsoft/callback` → OAuth callbacks, CSRF-exempt — `routes/oauth.py` (`oauth_bp`)
- `GET /admin` → Flask-Admin (superadmin only) — `SecureIndexView` in `app.py`

**Socket.IO Events (defined in `app.py`):**
- `connect` → join room by SID
- `start_live_session` → load per-SID profile, open Deepgram WS
- `audio_chunk` → forward PCM bytes to Deepgram for this SID
- `stop_live_session` → close Deepgram, clean up per-SID state, call `ls.drop_matcher(sid)`
- `mute_mic` / `unmute_mic` → toggle `ls.state['mic_muted']`
- `swap_roles` → toggle `ls.roles_swapped`
- `disconnect` → cleanup per-SID resources
- Server emits: `transcript` (final STT result with `speaker`, `line_id`), `coaching`, `analyse_result`

## Error Handling

**Strategy:** Fail-open for non-critical paths; hard stop only for data integrity violations at startup

**Patterns:**
- DB sessions always closed in `try/finally` blocks; `db.close()` is the cleanup mechanism (no context managers used)
- Migration `ALTER TABLE` blocks use `except Exception: pass` — expected to fail silently on re-run (idempotent)
- Claude API calls wrapped in try/except; JSON parse failures return `{}` or fallback default text
- Startup data integrity: duplicate `oauth_id` in `users` → `sys.exit(1)` with diagnostic output
- Flask error handlers: `@app.errorhandler(500)` and `@app.errorhandler(Exception)` return `{'ok': False, 'error': '...'}` JSON for AJAX/API requests; Werkzeug `HTTPException` passed through unchanged (404, 403, etc.)
- Rate limit: `@app.errorhandler(429)` returns `{'ok': False, 'error': 'rate limit exceeded'}`
- Live-loop service functions must not raise (documented in `prompt_pipeline.py` docstring) — any exception falls back to safe defaults silently

## Cross-Cutting Concerns

**Logging:**
- `print()` with bracketed context tags: `[DB]`, `[DG]` (Deepgram), `[AI]`, `[Schema]`, `[FX]`, `[Init]`, `[FairUse]`
- `app.logger.error()` for unexpected errors in migration functions
- `logging.getLogger(__name__)` in service modules
- Poll endpoint (`/api/ergebnis`) suppressed from Werkzeug access log via custom `_SuppressPolling` log filter in `app.py`

**Authentication:**
- `@login_required` in `routes/auth.py`: checks `session['user_id']`, attaches `g.user` + `g.org`, redirects to login if absent
- `@app.before_request _load_user()`: populates `g.user` / `g.org` for routes not decorated with `@login_required` (Flask-Admin, static files)
- Passwords: Werkzeug `generate_password_hash()` / `check_password_hash()`
- OAuth (Google + Microsoft): state in Flask session for CSRF; Microsoft new users get `email_confirmed=False` flag pending confirmation
- Session: `SESSION_COOKIE_SECURE` true in prod (env-gated by `FLASK_DEBUG`), `HTTPONLY=True`, `SAMESITE=Lax`, 14-day lifetime

**Authorization:**
- Role checks inline in route handlers: `g.user.rolle in ('owner', 'admin')`
- `@superadmin_required` decorator in `services/auth_decorators.py`
- Flask-Admin `SecureIndexView.is_accessible()` checks `g.user.is_superadmin`
- Org isolation: all profile/log queries include `filter_by(org_id=g.org.id)`

**CSRF:**
- `flask_wtf.csrf.CSRFProtect(app)` — initialized after `SocketIO` (order matters: SocketIO registers WSGI handler first)
- Stripe webhook + OAuth callbacks explicitly exempted: `csrf.exempt(stripe_webhook)` etc.

**Prompt Caching (Anthropic):**
- EWB and QA system prompts use Anthropic prompt caching (`cache_control: {"type": "ephemeral"}`) when prompt length > 4096 chars (`_CACHE_MIN_CHARS`)
- Toggled per module via `CACHE_EWB` / `CACHE_QA` env vars; `CACHE_ANALYSE=false` by default (analyse_loop prompt too short)

**DSGVO:**
- Deepgram EU endpoint as default: `DEEPGRAM_HOST=api.eu.deepgram.com` in `config.py`
- `Organisation.dsgvo_modus` controls transcript storage behavior
- PreCall raw search results not persisted — only structured briefing output stored
- PreCall in-memory cache: 5-min TTL, no disk write

**Markdown / XSS Sanitization:**
- PreCall briefing rendered via `{{ text | markdown | safe }}` Jinja filter (defined in `app.py`)
- `bleach.clean()` sanitizes rendered HTML to allowlist tags: `p br strong em code pre ul ol li h1–h4 blockquote a`
- Registered as Jinja filter `markdown` in `app.py` lines 101–107

---

*Architecture analysis: 2026-05-01*
