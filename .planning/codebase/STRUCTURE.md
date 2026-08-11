# Codebase Structure

**Analysis Date:** 2026-05-01

## Directory Layout

```
salesnerve/
├── app.py                  # Flask app factory, all blueprints, Socket.IO handlers, startup migrations/seeds (~2230 lines)
├── config.py               # All env-based config: API keys, model constants, plan definitions
├── extensions.py           # Shared SocketIO stub (avoids circular imports)
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Dev/test dependencies
├── requirements-rt.txt     # nerve_rt (FastAPI prototype, unused in prod)
├── pytest.ini              # Test runner config
├── deploy.sh               # Hetzner deploy script
├── database/
│   ├── db.py               # SQLAlchemy engine, SessionLocal, get_session(), WAL mode
│   ├── models.py           # All ORM models (Organisation, User, Profile, ConversationLog, etc.)
│   └── nerve.db            # SQLite database (production file, WAL mode)
├── routes/
│   ├── CLAUDE.md           # Blueprint name map + url_for() verification rules
│   ├── auth.py             # Login, register, logout, login_required decorator
│   ├── dashboard.py        # Session history, weekly summary, analytics
│   ├── app_routes.py       # Live session API: /api/beenden, /api/ergebnis, /api/einwand, EWB trigger
│   ├── profiles.py         # Profile CRUD, profile editor, precall personalize endpoint
│   ├── training.py         # Training UI, scenario API, TTS dialog
│   ├── coach.py            # Coach dashboard (is_coach users)
│   ├── organisations.py    # Org management, team invitations
│   ├── payments.py         # Stripe checkout, webhook handler
│   ├── oauth.py            # Google + Microsoft OAuth callbacks
│   ├── onboarding.py       # Onboarding wizard steps
│   ├── settings.py         # User settings (theme, language, notifications, billing)
│   ├── feedback.py         # In-app feedback collection
│   ├── learning.py         # Learning cards UI
│   ├── logs_routes.py      # Conversation log viewer
│   ├── performance.py      # Sales performance calculator
│   ├── changelog.py        # Changelog page
│   ├── waitlist.py         # Waitlist management
│   ├── legal.py            # AGB, Datenschutz, Impressum
│   ├── admin_dashboard.py  # Founder cost/revenue dashboard
│   ├── admin_ewb.py        # EWB prompt version management (A/B admin)
│   └── admin_views.py      # Flask-Admin ModelViews (User, Org, Feedback, AuditLog, ConvLog)
├── services/
│   ├── live_session.py     # All thread-safe shared state for live calls (module-level globals + locks)
│   ├── deepgram_service.py # Per-SID Deepgram WebSocket connections (_deepgram_sessions dict)
│   ├── claude_service.py   # Anthropic API: analyse_loop (Haiku), EWB streaming, coaching; circuit-breaker
│   ├── coaching_service.py # Post-call Sonnet analysis, learning card generation
│   ├── training_service.py # Training dialog (Claude Haiku + ElevenLabs TTS), scoring
│   ├── precall_service.py  # Brave Search + Claude briefing (3-layer), 5-min cache
│   ├── prompt_pipeline.py  # A/B prompt routing (resolve_prompt_version), build_profile_context()
│   ├── ewb_pipeline.py     # EWB system prompt assembly with profile context
│   ├── profile_schema.py   # Pydantic v2 ProfileSchema, LATEST_SCHEMA_VERSION, _migrate_profile_data()
│   ├── ki_logik.py         # Readiness score, 6-phase classification, hint priority
│   ├── qa_pipeline.py      # Classifier + FAQ-match response pipeline (Phase 08.5)
│   ├── einwand_keyword_matcher.py  # Low-latency keyword-based objection detection
│   ├── integration_engine.py       # Post-session training recommendation routing
│   ├── cost_tracker.py     # API cost logging to api_cost_log table
│   ├── rate_limiter.py     # Flask-Limiter (per-IP, in-memory; Redis-upgradeable)
│   ├── audit.py            # Writes to audit_log for sensitive actions
│   ├── auth_decorators.py  # @superadmin_required decorator
│   ├── branchen_data.py    # DACH industry/sector reference data
│   ├── crm_service.py      # CRM integration helpers
│   ├── customer_success_service.py # Customer success nudge logic
│   ├── email_service.py    # Email sending (invitations, notifications)
│   ├── eur_calculator.py   # EUR revenue/profitability calculations
│   ├── exchange_rates.py   # Daily EUR/USD rate fetch (Frankfurter API), scheduler
│   ├── feedback_service.py # Feedback event persistence
│   └── profile_migration.py # Legacy profile migration helpers
├── templates/
│   ├── base.html           # Base layout: nav, sidebar, CSS/JS includes, theme/lang vars
│   ├── landing.html        # Public landing page
│   ├── dashboard.html      # Main dashboard (session history, stats, coaching cards)
│   ├── training.html       # Training UI (scenario selector, audio player, scoring)
│   ├── profile_editor.html # Profile editor (full JSON schema UI)
│   ├── profile_wizard.html # New profile creation wizard
│   ├── profiles_list.html  # Profile list view
│   ├── session_detail.html # Post-call session detail + analysis
│   ├── onboarding.html     # Onboarding wizard
│   ├── settings.html       # User settings page
│   ├── coach_dashboard.html # Coach view (team sessions)
│   ├── coach_firma.html    # Coach company profile view
│   ├── coach_methodik.html # Coach methodology page
│   ├── analytics.html      # Analytics overview
│   ├── logs_page.html      # Conversation log list
│   ├── changelog.html      # Changelog
│   ├── help.html           # Help page
│   ├── team.html           # Team management
│   ├── register.html       # Registration
│   ├── confirm_email_pending.html  # Microsoft OAuth email confirmation pending
│   ├── waitlist_admin.html # Waitlist admin view
│   ├── agb.html            # AGB (terms)
│   ├── datenschutz.html    # Datenschutz (privacy)
│   ├── impressum.html      # Impressum (legal notice)
│   ├── _beispiel_profil_modal.html # Partial: example profile modal
│   ├── _tooltip.html       # Partial: tooltip component
│   └── admin/              # Flask-Admin templates override
├── static/
│   ├── nerve.css           # Global styles (dark/light mode, all components)
│   ├── pip-launcher.js     # Picture-in-Picture launcher: precall form, session control, EWB overlay
│   ├── audio-processor.js  # AudioWorklet: PCM capture, Socket.IO streaming
│   ├── audio-processor.js  # AudioWorklet PCM processor
│   ├── profile_editor.js   # Profile editor dynamic UI
│   ├── feedback.js         # In-app feedback widget
│   ├── feedback.css        # Feedback widget styles
│   ├── admin_dashboard.js  # Founder dashboard JS
│   ├── admin_dashboard.css # Founder dashboard styles
│   ├── fonts/              # Self-hosted web fonts
│   ├── audio/              # Audio samples / test files
│   └── vendor/             # Third-party JS (Socket.IO client, etc.)
├── database/               # (see above)
├── tests/
│   ├── conftest.py         # Pytest fixtures (Flask test client, in-memory SQLite, mock services)
│   ├── fixtures/           # Test fixture data files
│   ├── services/           # Service-level unit tests
│   ├── archive/            # Archived/disabled tests
│   └── test_*.py           # Integration and unit tests (named by phase + feature)
├── scripts/
│   ├── export_ft_jsonl.py  # Export fine-tuning JSONL from ft_qa_events
│   ├── migrate_branche_to_enum.py  # One-off branche enum migration
│   ├── migrate_polish_38_counters.py # One-off POLISH-38 counter migration
│   ├── tts_comparison.py   # TTS voice comparison tool
│   └── update_nerve_profile.py     # Profile update helper script
├── nerve_rt/               # FastAPI + Redis async engine prototype (not in production)
│   ├── main.py
│   ├── config.py
│   ├── redis_bridge.py
│   ├── routers/
│   └── services/
├── docs/                   # Internal architecture notes
├── logs/                   # Runtime log files (created at startup, gitignored)
├── deploy/                 # Deployment config files
├── .planning/
│   ├── codebase/           # Codebase map documents (this file)
│   ├── phases/             # Phase plan documents (PLAN.md, SPEC.md per phase)
│   ├── audits/             # Schema/data audits
│   ├── quick/              # Quick-fix plans
│   └── debug/              # Debug session artifacts
└── .claude/
    └── worktrees/          # Agent worktree checkouts (auto-managed)
```

## Directory Purposes

**`routes/`:**
- Purpose: One file per domain concern, each exporting a single Flask Blueprint instance
- Naming: `{domain}.py` → `{domain}_bp = Blueprint('{domain}', __name__)`
- Exception: `organisations.py` exports `orgs_bp` with name `'orgs'` (not `'organisations'`) — critical for `url_for()`
- Key constraint: before adding `url_for('blueprint.endpoint')`, verify in `routes/CLAUDE.md`

**`services/`:**
- Purpose: All business logic, external API clients, background thread workers
- No Flask request context assumed — services must work from background threads
- Pattern: module-level client objects (e.g. `claude_client = anthropic.Anthropic(...)`) + functions
- Thread-safety: all shared state accessed under explicit locks

**`database/`:**
- Purpose: SQLAlchemy engine, session factory, all ORM models
- `db.py` exports: `engine`, `SessionLocal`, `get_session()`, `db_session` (scoped), `Base`
- `models.py` exports: all model classes + `init_db(engine)` to create tables
- WAL mode enabled at engine `connect` event for SQLite — required for concurrent thread reads/writes

**`templates/`:**
- Purpose: Jinja2 HTML templates, all extending `base.html`
- Partials prefixed with `_` (e.g. `_tooltip.html`, `_beispiel_profil_modal.html`)
- Custom Jinja filters available everywhere: `fromjson`, `de_currency`, `markdown`, `static_mtime(filename)`

**`static/`:**
- Purpose: CSS, JavaScript, fonts served directly by Nginx in production
- Cache-busting: `static_mtime('filename')` Jinja global returns file mtime as integer for query-string versioning
- Main CSS: `nerve.css` — contains all component styles, dark/light mode vars

**`tests/`:**
- Purpose: pytest-based tests; naming pattern `test_{phase}_{feature}.py`
- `conftest.py` provides shared fixtures: Flask test client, in-memory SQLite DB, mocked external services
- Rule: tests must assert runtime behavior (DB writes, function return values, API responses) — not source presence (no `inspect.getsource` assertions)

**`scripts/`:**
- Purpose: One-off data migration and tooling scripts run manually
- Not imported by the app; executed directly: `python scripts/export_ft_jsonl.py`

**`nerve_rt/`:**
- Purpose: FastAPI + Redis async engine prototype (Phase 04.8.1 research)
- Not deployed; not imported by `app.py`
- Has its own `config.py` and separate `requirements-rt.txt`

**`.planning/`:**
- Purpose: All GSD workflow artifacts — phase plans, codebase maps, audits, quick fixes
- `phases/{phase-slug}/` — contains `PLAN.md`, `SPEC.md`, `HANDOFF.json`, `.continue-here.md`
- `codebase/` — this document and sibling analysis files (STACK.md, CONVENTIONS.md, etc.)

## Key File Locations

**Entry Points:**
- `app.py`: Flask application object, all initialization, Socket.IO handlers
- `config.py`: all constants and env config

**Database:**
- `database/db.py`: `get_session()`, `engine`, `SessionLocal`
- `database/models.py`: `Organisation`, `User`, `Profile`, `ConversationLog`, `ProfileSkript`, `ProfileOpener`, `ProfileFaq`, `TrainingScenario`, `PromptVersion`, `ConversationLog`, `BillingEvent`, `FeedbackEvent`, `CoachAssignment`, `ApiCostLog`, `AuditLog`

**Live Session Core:**
- `services/live_session.py`: `state`, `state_lock`, `transcript_buffer`, `buffer_lock`, `conversation_log`, `session_meta`, `_per_sid_profile`, `reset_session()`, `set_profile_for_sid()`, `get_profile_for_sid()`

**Routing:**
- `routes/auth.py`: `login_required` decorator (imported by all other routes that need auth)
- `routes/app_routes.py`: `/api/beenden`, `/api/ergebnis`, `/api/einwand`
- `routes/profiles.py`: profile CRUD + `/api/precall/personalize`

**AI Pipeline:**
- `services/claude_service.py`: `SYSTEM_PROMPT_BASE`, `COACHING_PROMPT_BASE`, `analysiere_mit_claude()`, EWB streaming functions
- `services/prompt_pipeline.py`: `resolve_prompt_version()`, `build_profile_context()`, `invalidate_resolver_cache()`
- `services/ewb_pipeline.py`: `build_ewb_prompt()`
- `services/profile_schema.py`: `LATEST_SCHEMA_VERSION`, `ProfileSchema` (Pydantic v2), `_migrate_profile_data()`

**Styles + Frontend:**
- `static/nerve.css`: all app styles
- `static/pip-launcher.js`: PiP overlay, precall form, EWB buttons, session controls
- `static/audio-processor.js`: AudioWorklet PCM capture
- `templates/base.html`: nav, sidebar, global JS includes

## Naming Conventions

**Files:**
- Python: `lowercase_underscores.py` — `claude_service.py`, `live_session.py`, `app_routes.py`
- Templates: `lowercase.html` or `domain_detail.html` — `profile_editor.html`, `session_detail.html`
- Partials: prefixed with `_` — `_tooltip.html`
- Static: `kebab-case.js` / `snake_case.css` — `pip-launcher.js`, `nerve.css`
- Tests: `test_{phase}_{feature}.py` — `test_08_20_3.py`, `test_precall_schema.py`

**Identifiers:**
- Blueprint instances: `{name}_bp` → `auth_bp`, `dashboard_bp`
- Blueprint names: match variable prefix → `Blueprint('auth', ...)`, `Blueprint('dashboard', ...)`
- Model classes: PascalCase → `User`, `Organisation`, `ConversationLog`
- DB columns: `lowercase_underscores` in ASCII (no Umlauts in identifiers) → `einwaende_gesamt`, `org_id`, `erstellt_am`
- Constants: UPPER_SNAKE_CASE → `SYSTEM_PROMPT_BASE`, `VOICE_POOL_MALE`, `LATEST_SCHEMA_VERSION`
- Private/internal functions: single underscore prefix → `_migrate()`, `_do_login()`, `_load_prompt_template()`

## Where to Add New Code

**New HTTP endpoint:**
- Add to the matching `routes/{domain}.py` blueprint
- If domain is new: create `routes/{domain}.py`, define `{domain}_bp = Blueprint('{domain}', __name__)`, import and register in `app.py`
- Verify blueprint name with `routes/CLAUDE.md` before any `url_for()` calls

**New service / business logic:**
- Create `services/{feature}.py` — no Flask imports, no request context assumed
- If it needs DB access: call `get_session()` from `database/db.py`, always wrap in `try/finally: db.close()`

**New template:**
- Add to `templates/`, extend `{% extends 'base.html' %}`
- Use `{{ text | markdown | safe }}` for AI-generated Markdown content
- Use `static_mtime('file.js')` for cache-busted static includes

> ⛔ **KORRIGIERT 2026-08-11 — die vorherige Fassung dieses Abschnitts war auf dem Live-Server WIRKUNGSLOS.**
> Sie schrieb vor, neue Spalten und Tabellen als idempotente Blöcke in `_migrate()` (`app.py`) anzulegen. **`app.py` verlässt `_migrate()` bei PostgreSQL sofort wieder** — der Datenbank-Nutzer auf dem Live-Server hat bewusst keine Änderungsrechte, und der Live-Server läuft auf PostgreSQL. **Wer nach der alten Fassung baute, schrieb eine Migration, die NIE läuft — und merkte es nicht, weil nichts fehlschlägt.**
> Die `_migrate()`-Einträge im Code sind **Alt-Bestand** aus der lokalen Zeit; lokal wird seit dem 27.05. ohnehin nicht mehr entwickelt. **Nicht als Vorlage kopieren.**

**New database column:**
- Add `Column(...)` to appropriate model in `database/models.py`
- **Write an Alembic revision** that cleanly builds on the current head. This is the ONLY path that takes effect in production. Do **not** add an `ALTER TABLE` block to `_migrate()`.
- ⚠ Special characters in `COMMENT ON` statements: a colon without a preceding word character is parsed as a bind parameter and kills the migration. Use `exec_driver_sql` (real incident, migration `0039`).

**New ORM model (new table):**
- Add class to `database/models.py` extending `Base`
- `init_db(engine)` in `database/models.py` calls `Base.metadata.create_all(engine)` — new tables auto-created on startup
- **Write an Alembic revision for the table as well.** Do **not** add a `CREATE TABLE IF NOT EXISTS` fallback to `_migrate()` "for deploy safety" — it provides none in production.

**New background thread:**
- Import `services/live_session.py` as `ls` for shared state access
- Always acquire the appropriate named lock before reading/writing `ls` state
- Use `threading.Event` for inter-thread signaling (existing pattern: `ls.analyse_trigger`, `ls.coaching_trigger`)

**New test:**
- Add to `tests/test_{phase}_{feature}.py`
- Use fixtures from `tests/conftest.py`
- Assert runtime behavior (return values, DB rows, HTTP responses) — never source presence

## Special Directories

**`logs/`:**
- Purpose: Runtime log files and session transcript files
- Generated: Yes (created at startup by `live_session.py` `os.makedirs`)
- Committed: No (gitignored)

**`database/nerve.db`:**
- Purpose: Production SQLite database (WAL mode, concurrent reads)
- Generated: Yes (created by `init_db(engine)` on first run)
- Committed: No (gitignored in production; local dev may have it checked in)

**`nerve_rt/`:**
- Purpose: Async FastAPI prototype, separate dependency set
- Generated: No
- Committed: Yes (research artifact, not linked to main app)

**`.planning/`:**
- Purpose: GSD workflow artifacts — all planning and execution docs
- Generated: By GSD commands
- Committed: Yes — source of truth for project roadmap and phase history

---

*Structure analysis: 2026-05-01*
