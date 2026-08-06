<!-- GSD:project-start source:PROJECT.md -->
## Project

**NERVE**

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler — **Markt: US-FIRST** (beschlossen 2026-07-04). Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit und liefert Gegenargumente sowie Coaching-Tipps direkt auf den Bildschirm — unsichtbar für den Kunden. Ergänzend bietet NERVE einen KI-Trainingsmodus, eine Coach-Plattform für Teams und automatisierte Post-Call-Analysen.

**Status:** v0.9.4, Pre-Launch — Early Access vorbereitet
**Founder:** Solo-Founder (Einzelunternehmer)

**Core Value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

### Skill-Routing

- **Spike findings for salesnerve** (implementation patterns, constraints, gotchas) → `Skill("spike-findings-salesnerve")`

### Constraints

- **Stack:** Kein Framework-Wechsel — Flask + Vanilla JS bleibt. Keine React-Migration.
- **Kosten/Tempo Live:** ⚠ **KORRIGIERT 2026-08-03 — hier stand "Sonnet MUSS raus, nur Haiku fuer alles Live". Das ist UEBERHOLT und war das Gegenteil der geltenden Vorgabe.** Es gilt Punkt 25 (Latenz): **Gleichgewicht aus Qualitaet UND Tempo.** Schnell-aber-Muell ist genauso ein Dealbreaker wie gut-aber-langsam. Die Ambition ist **"das STARKE Modell schnell genug machen"** (Zwischenspeicher, kleinere Prompts, Vorladen, lokales Sofortnetz) — NICHT aufs schwache Modell ausweichen. Sonnet 4.5 laeuft seit 22.07. live mit scharfem Zwischenspeicher.
- **DSGVO:** Pflicht von Tag 1 — kein woertliches Mitschneiden default, **NIE Audio persistieren**, Call-Logs nie loeschen. ⚠ **KORRIGIERT 2026-08-03 — hier stand "Server in Deutschland (Hetzner)". Das war nie eine DSGVO-Anforderung** und steuerte nach dem US-first-Beschluss in die falsche Richtung: Server-Region folgt dem Markt, beim US-Umzug also **US-Region**. DSGVO-Pflichten (Loeschpflicht, Auskunft, Datenschutzerklaerung) bleiben unabhaengig davon bestehen, weil Andre deutscher Einzelunternehmer ist.
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

## Deutsche Umlaute & UTF-8 (WICHTIG)
Die App ist durchgehend UTF-8 (`<meta charset="UTF-8">` in allen Templates,
`encoding='utf-8'` bei Datei-I/O). Zwei Regeln — Zielgruppe bestimmt Kontext:

### ✅ Echte Umlaute (ä, ö, ü, ß) — in USER-FACING-TEXT
Alles was der User im Browser sichtbar liest, schreibt, hört:
- HTML-Content zwischen Tags: `<div>Gespräch wird ausgewertet…</div>`
- Labels, Buttons, Überschriften: `<button>Zurück</button>`
- Placeholder, Tooltips, Alt-Texte: `placeholder="Für Sie"`
- JS-Strings die User sehen: `alert('Einwände: 3')`
- data-search/data-tip-Attribute (User-facing im HTML)
- Flash-Messages, Error-Messages
- Default-String-Konstanten für User-Output (z.B. `CONSENT_DEFAULT_TEXT`)

### ❌ ASCII-Pflicht (ae/oe/ue/ss) — in CODE-IDENTIFIERN
Alles was als Bezeichner im Code gelesen/aufgelöst wird — auch wenn dort
Text steht der wie Deutsch aussieht. Identifier sind:
- **Python-Attribute / DB-Spalten**: `ConversationLog.einwaende_gesamt`
- **Dict-Keys**: `{'einwaende': [...], 'gespraech_id': 42}`
- **Jinja2-Expressions**: `{% if log.einwaende > 0 %}`, `{{ conv.einwaende_ok }}`
  (Jinja löst auf Python-Attribute auf — Umlaut-Attribut existiert nicht)
- **JS-Variable-Namen**: `let einwaende = 0` (nicht `let einwände`)
- **JS-Object-Keys** die als JSON ans Backend gehen: `{spezial_einwaende: […]}`
- **JS-Object-Property-Access** auf Backend-Response: `data.einwaende`
- **HTML-ID/class-Attribute**: `id="sc-einwaende"` (JS-Selektoren erwarten ASCII)
- **CSS-Selektoren/-Klassen**: `.einwand-card` (nie `.einwände-card`)
- **URL-Slugs, Route-Namen**: `/api/einwaende/list`

### Plan-Docs & Kommentare
In `.planning/phases/*.md` und reinen Code-Kommentaren ist ASCII-Ersatz
zur Lesbarkeit erlaubt aber nicht zwingend. Beide sind OK.

### Historie
Früher wurde pauschal ASCII-Ersatz aus angeblichem "Encoding-Bug" verwendet —
das ist Cargo-Cult. Es gab nie ein echtes Encoding-Problem; das Projekt ist
sauber UTF-8. Der Fehler am 2026-04-18 war die gegenläufige Überreaktion:
blindes Ersetzen auch in Code-Identifiern. Regel ist deshalb **zweischneidig**:
User-Text mit Umlauten, Code-Identifier ohne. Siehe POLISH-12 und Phase 07
in [[02 Projekte/NERVE Finaler Polish Pass]].
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

## Test-Qualitaets-Regel: Integration-Assertion vs. Source-Presence-False-Green

Ein Test ist VALID wenn er Runtime-Verhalten prueft — Verhalten das kaputt gehen
kann ohne dass der Source-Code sich aendert:
- **DB-Write/Read:** Query auf echte oder In-Memory-DB, Assertion auf Ergebnis-Row oder Feldwert
- **Function-Call-Return:** Funktion aufrufen (ggf. mit monkeypatched I/O), Assertion auf Rueckgabewert
- **State-Mutation:** Zustandsaenderung in Dict/Objekt nach Function-Call pruefen
- **API-Response:** HTTP-Request oder Socket-Emit, Assertion auf Response-Body oder Status-Code
- **inspect.signature():** Prueft Runtime-API-Schnittstelle (Parameter-Namen) — OK

Ein Test ist ein SOURCE-PRESENCE-FALSE-GREEN wenn er nur prueft ob Code *existiert*:
- `inspect.getsource(fn)` + `assert 'string' in src` → LOESCHEN
- `hasattr(module, 'symbol')` als "Schutz vor Loeschung" → LOESCHEN
- `open('datei.py').read()` + `assert 'string' in src` → LOESCHEN
- `subprocess.run(['grep', ...])` auf Quelldateien → LOESCHEN
- `src.count('funktionsaufruf(')` → LOESCHEN

Source-Presence-Tests geben GREEN solange der Code *existiert* — auch wenn er Dead-Code
ist, nie aufgerufen wird, oder fehlerhafte Logik hat. Sie blockieren Dead-Code-Prune
und geben falsche Sicherheit.

Grenzfall: `inspect.getsource` fuer Regex-Muster die Runtime-Constraints sichern
(z.B. "kein Opus-Model im Live-Loop") sind OK NUR wenn kein Function-Call-Mock
die Constraint direkt testbar macht. Dokumentiere den Grund mit Kommentar im Test.

## Test-Cleanup-Regel: Committende Tests raeumen ihre Rows weg (Phase 08.23.2.PGTEST)

Tests, die Daten in nerve_test committen, raeumen ihre eigenen Rows im Teardown via dem gemeinsamen
Cleanup-Helfer (`cleanup_rows` in tests/conftest.py) wieder weg (Baseline-Sauberkeit, vom
Test-Cleanup-Waechter `_baseline_cleanup_guard` erzwungen; ein Cleanup-Fehler wird via
`[PGTEST-CLEANUP]`-Warnung laut gemeldet). public.* erzwingt der in-pytest-Waechter; crm.*/training.*
erzwingt der POST-SUITE-Check in deploy.sh (jede crm.* Tabelle == 0 Rows, training.transcript_archive
== 0). Code-Identifier (`cleanup_rows`/`_baseline_cleanup_guard`) bleiben ASCII.

## DB-Regel: Nie stiller except auf einer PG-Connection/Session ohne rollback (Phase 08.23.2.PROFILE-MIGRATE-TXN-FIX)

**Nie `except: pass`/stiller except auf einer Postgres-Connection/Session ohne `rollback`.**
Ein verschluckter Fehler auf einer laufenden Transaktion vergiftet sie → alle Folge-Statements
sterben still als `InFailedSqlTransaction` (Postgres-only, auf SQLite unsichtbar — daher fängt lokal/SQLite
das Problem NICHT, nur real-PG). Jeder `except` auf einer `conn`/`session`, der den Fehler nicht
re-raist, MUSS zuerst `conn.rollback()`/`session.rollback()` rufen (VOR dem print/pass/continue).

Anlass: PROFILE-MIGRATE-TXN-FIX 2026-07-13 — ein totes `ALTER TABLE profile_opener ADD COLUMN type`
in `except: pass` OHNE rollback (`DuplicateColumn`/Permission) hat bei jedem Start die Transaktion
vergiftet → `InFailedSqlTransaction`-Kette → ein versions-loses Profil blieb unmigriert.

Ein AST-basierter Wächter (grep reicht nicht — Kontroll-/Datenfluss-Analyse) ist bewusst nach Backlog
`TXN-ROLLBACK-GUARD-AST` vertagt (Cross-AI Fable+Gemini: grep-Wächter over-engineered/unzuverlässig).

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

## Routes-spezifische Regeln

Regeln fuer die Arbeit im routes/-Ordner: siehe `routes/CLAUDE.md`
(url_for-Verifikation, Blueprint-Namen, Fehlerquellen).

## Regel 13: Hook vs. CLAUDE.md — Determinismus-Entscheidung

Bevor eine neue Verhaltensregel in CLAUDE.md geschrieben wird:

- Ist das Verhalten "jedes Mal ohne Ausnahme, unabhaengig vom Kontext"?
  → **Hook** (settings.json PostToolUse/PreToolUse). Deterministisch, kein Vergessen.
- Braucht es Urteilsvermögen, Kontext oder Ausnahmen?
  → **CLAUDE.md-Regel**. Gilt als Guideline, nicht als erzwungene Aktion.
- Memory-Regel ist halb-zuverlaessig fuer deterministische Aktionen — nicht fuer
  "immer X tun"-Anforderungen verwenden.

Beispiele:
- "Nach Python-Edit immer ruff format" → Hook (kein Urteil noetig)
- "Bei Umlaut-Entscheidung User-Text vs. Code-Identifier unterscheiden" → CLAUDE.md

## GSD-Workflow-Pflichten — Plan/Execute/Review

> **Pflicht-Sequenz für jeden Plan-/Execute-/Review-Agent.** Diese Regeln sind verbindlich und gelten ZUSÄTZLICH zur "Next Up"-Empfehlung des Plan-Agents. Wenn der Plan-Agent direkt zu Execute springt bei einer 🔴-Phase, ist das ein Bug — Cross-AI-Review kommt dazwischen.
> **Source-of-Truth für Mechanik (Trigger-Logik, Hit-Rate-Pattern, Fairness-Regel):** `Nerve-Vault/CLAUDE.md` Punkt 7. (Punkt 8 wurde am 02.08. gestrichen — er ist in "Vorgehens-Prinzip Teil B" derselben Datei aufgegangen.)

### Komplexitäts-Marker

Jede Phase ist mit einem Marker klassifiziert (in PLAN.md / SPEC.md sichtbar):
- 🟢 **trivial** — mechanisch, GSD-Auto-Tempo (Renaming, CSS, String-Updates, mechanische Prunes, Bugfixes mit klarem Root-Cause)
- 🟡 **mittel** — mehrere Entscheidungen, Multi-File-Edits, kein Architektur-Risiko (Refactors, neue Endpoints, Schema-Anpassungen)
- 🔴 **komplex** — Architektur/Security/DSGVO/Schema/Multi-Pipeline. Cross-AI Pflicht.

### Pflicht-Workflows

| Trigger | Pflicht-Schritt | Kommando | Wann |
|---|---|---|---|
| 🔴 Plan fertig | Cross-AI-Plan-Review **vor** Execute | `/gsd-review --phase X --all` | **IMMER bei 🔴 UND bei 🟡** (Trigger egal — korrigiert 2026-08-03, hier stand faelschlich "Default-ON bei 🟡 nur mit Trigger"). Skip nur bei 🟢. |
| Cross-AI-Findings da | Replan mit Findings | `/gsd-plan-phase X --reviews` | Wenn Cross-AI ≥1 substantielles Finding (HIGH actionable) liefert |
| Schema-Phase Plan | Real-Daten-Validation Pflicht | Plan muss Real-Daten-Sample gegen neues Schema testen | Bei Phasen die ein Pydantic/SQLAlchemy/etc.-Schema ändern (Vault-CLAUDE.md Punkt 13) |
| `url_for(...)`-Strings | Endpoint-Verifikation | `grep "def " routes/X.py` + Live-Test-Request-Context | Bei jedem Plan/Edit mit `url_for('blueprint.function')` (Vault-CLAUDE.md Punkt 9) |
| Feature-Reaktivierung | Migration-Vollständigkeit prüfen | "Brauchen bestehende Records eine UPDATE-Migration?" | Wenn Plan einen `if` reaktiviert/auskommentiert/aktiviert (Vault-CLAUDE.md Punkt 10) |
| Execute fertig | Code-Review | `/gsd-code-review` → `/gsd-code-review-fix` | Pflicht bei 🔴, empfohlen bei 🟡 |
| 🔴 Schema-Bump | LATEST_SCHEMA_VERSION-Konstante prüfen | `services/profile_schema.py` + `app.py`-Skip-Check | Bei jedem Plan der Schema-Version-Bump auslöst (Block-J-Lesson 08.20-Plan-01) |

### Skip-Regel (für Plan-Agent)

- 🟢 trivial: Cross-AI-Review SKIP (Overkill, frisst Momentum)
- 🟡 mittel (mit oder ohne Trigger) ODER 🔴 komplex: Cross-AI-Review **PFLICHT vor Execute**
  (korrigiert 2026-08-03: hier stand "🟡 ohne Trigger = optional" — das war ein Widerspruch
   zum Vault, wo Cross-AI bei 🟡 seit dem 03.05.2026 Pflicht ist. Belegter Anlass damals:
   Phase 08.19.5.1, wo der uebersprungene Check drei Migrations-Stellen kostete.)

### Was Plan-Agent NICHT tun soll

- Direkt zu `/gsd-execute-phase` springen wenn Phase 🔴 **ODER 🟡** ist
- Cross-AI-Pflicht als optional darstellen bei 🔴 **ODER 🟡**
- "Next Up — Execute" empfehlen ohne vorherigen Review-Schritt bei 🔴 **ODER 🟡**

⚠ **KORRIGIERT 2026-08-03 (Gemini-Fund):** Hier stand ueberall nur 🔴. Weil ein Modell sich
stark an ausdruecklichen Verboten orientiert, war der 🟡-Review damit faktisch wegrationalisierbar
— obwohl er seit 2026-05-03 Pflicht ist. **Skip gilt nur bei 🟢.**

### Was Plan-Agent statt dessen empfehlen soll

Bei 🔴- **und 🟡**-Phase als "Next Up":
```
▶ Next Up — Cross-AI Peer Review (PFLICHT bei 🔴 und 🟡)

/clear
/gsd-review --phase X --all
```

Erst NACH Review-Findings + Replan kommt Execute als Next Up.

### Cross-AI-Entscheidung im Log dokumentieren

Pro Phase wird in `Nerve-Vault/05 Log.md` festgehalten:
- Cross-AI gemacht: warum (🔴 / 🟡-Trigger) + Hit-Rate (Anzahl actionable Findings)
- Cross-AI geskippt: warum (**nur 🟢 ist ein gueltiger Grund**) — kurze Begründung

Begründung: Lerneffekt aus Block-N-Phasen — Hit-Rate steigt bei klarem Briefing + Pro-Modell, Skip-Entscheidungen müssen genauso bewusst sein wie Run-Entscheidungen.
- "Immer git push nach Phase" → CLAUDE.md (Ausnahmen: lokale Branches, WIP)

## HART: Kein Local-Dev — Default ist Production-Server (bis EA-Launch)

> ### ⬛ ÜBERSCHREIBUNG 2026-06-01 — Staging ist KOMPLETT aus dem Workflow (Andre-Decision)
>
> **Bis zur letzten Phase vor Launch gibt es nur Production.** Staging wird NICHT mehr benutzt — weder zum Deployen, Testen, noch für Daten/Schema/Logs/inspect.sh. Begründung: das kaputte Staging-Gate hat 2× Phasen ausgebremst (D.UX.1, D.UX.4) und GSD jede Phase die falsche git-pull/Staging-Verify-Strategie schreiben lassen. Schluss damit.
>
> **Mapping — überall wo unten "Staging" steht, gilt JETZT Production:**
> - **Deploy:** `bash deploy.sh production` (das Staging-Pre-Gate wurde aus `deploy.sh` ENTFERNT). KEIN `deploy.sh staging`, KEIN "erst staging dann production".
> - **Verify in Plan-Files:** KEIN `git pull` — Production ist tar-deployed (`.git` excluded), git pull existiert dort nicht. Acceptance = der Pytest-Gate den `deploy.sh production` selbst eingebaut hat (läuft auf dem Production-Server vor dem Restart; bei Test-Fehler kein Restart, alter Code bleibt live). Plus Live-Test im Browser mit Test-User.
> - **Daten/Schema/Logs/Routes:** `inspect.sh` gegen **Production** read-only: `ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh <cmd>'`. NICHT gegen `staging.getnerve.app`.
> - **Vor jedem Prod-Overwrite-Deploy:** kurz prüfen ob auf Prod echter Code liegt der NICHT in origin/main ist (SCP-Hotfix) — sonst bügelt der tar-Push ihn weg.
>
> **Reaktivierung:** Das gesamte Staging-basierte Vorgehen unten in diesem Abschnitt ist PAUSIERT und als "= Production" zu lesen. Es wird in der **LETZTEN Phase vor Launch** wieder scharfgeschaltet — Phase **08.23.2.STAGING** (Staging-Promotion-Pipeline, ans Ende verschoben).
>
> **Der Kern bleibt unverändert gültig:** kein Local-Dev — Production IST die Test-Umgebung (mit Test-User), nicht der lokale Rechner.

**Verankert 2026-05-27 in zwei Andre-Direktanweisungen (Phase 08.23.2.D Live-Test):**

1. *"nene moment, wir entwickeln GAR NICHTS MEHR LOCAL."* (vormittag — Stufe 1 verankert)
2. *"lass uns auf live bauen bis launch, dann auf staging wechseln. wir ändern aktuell viel auf staging nur um dinge herauszufinden... ich bin gespannt ob unser feature dann tatsächlich auf dem live server laufen oder ob wieder bugs entstehen."* (nachmittag — Default-Umgebung auf Production)

### Pre-EA-Launch: Default-Test-Umgebung ist Production

Code-Änderungen werden committet, gepusht, **direkt auf Production deployed** (`bash deploy.sh production`), dort getestet mit Test-User-Account. Wenn grün: Feature ist live. Punkt.

Begründung: Phase 08.23.2.D Live-Test 2026-05-27 hat empirisch belegt dass Staging-Workflow nicht 1:1-Production-Spiegel ist. Heute 4× manuelle Eingriffe nötig (manueller Alembic-Upgrade, deploy_meta-Patch, Service-Restart, SCP-Hotfix für Test-Hook). Solange keine echten EA-User Schaden nehmen können, ist Direkt-Live-Test der ehrlichere Workflow.

### Drei-Stufen-Plan (verankert 2026-05-27)

| Stufe | Wann | Was |
|---|---|---|
| **1 — Live bis Launch** | jetzt bis EA-Launch | Direkt auf Production deployen + testen. Sandbox via dedicated Test-User. |
| **2 — Staging-Promotion-Pipeline** | kurz vor EA-Launch (Mini-Phase, ~1 Tag) | `deploy.sh`-Test-Gate fixen (test_ft_seed Pre-existing Failure), Auto-Alembic im Deploy-Workflow, Auto-deploy_meta-Write, atomarer `staging→production`-Promote als single command. |
| **3 — Dedicated Staging-Cloud** | Post-Launch wenn EA-User da | Eigene abgekapselte Umgebung mit Production-identischen URLs, eigene OAuth-Apps für Google/Microsoft, eigene Stripe-Test-Setup, DB-Snapshot-Sync von Production. Eigene große Phase. Vermutlich Roadmap-Eintrag als `08.23.2.X — Staging-Mirror-Cloud`. |

### Pre-Launch Sandbox-Pattern: Test-User-Account

Damit Live-Tests keinen Daten-Schaden anrichten:

- Dedicated User-Account (z.B. `andre-test@nerve.local`) mit Spalte `is_test_user=True` in users-Tabelle
- DPO-Korpus-Sammler (Phase 08.23.2.E) **filtert is_test_user-Calls aus** — keine Vergiftung der Trainings-Foundation
- Founder-Analytics-Dashboards (Block J + 08.16) filtern Test-User-Calls aus
- Stripe-Subscription des Test-Users im Stripe-Test-Mode oder ganz ohne Subscription
- Calls vom Test-User bekommen Tag `tag='test'` für spätere Daten-Filterung
- Test-User darf KEINE Email-Sends triggern (Test-SMTP oder Dummy)

**Pflicht-Migration vor Phase 08.23.2.E** (Mini-Phase): `is_test_user BOOLEAN DEFAULT FALSE` zu users-Tabelle. Plus Filter-Logik in DPO-Sammler.

### Was bleibt unverändert — Kein Local-Dev (Original HART-Regel)

### Keine Ausnahmen — auch nicht für vermeintlich kleine Sachen

- KEIN lokales `python app.py`
- KEIN lokales `pytest` als Acceptance-Check (auch nicht für "ist doch nur ein Unit-Test")
- KEINE lokalen Smoke-Tests via `python -c "import ..."`
- KEINE lokalen Migrations-Trockenläufe
- KEINE lokalen Frontend-Tests (Browser, DevTools, WebSocket)
- KEINE Live-`.env`-Anpassung für Local-Dev (CORS_ORIGIN=\*, FLASK_DEBUG=1, GLINER_DISABLED=1, etc.)

### Erlaubt ohne Diskussion

- `git`-Operationen (commit, push, log, diff, status, checkout) — manipulieren keinen Code-Pfad
- Lesen von Dateien (Source-Code, Configs, Docs) — kein Ausführen
- `pip install` lokal NUR wenn explizit für GSD-Agent-Tooling nötig (z.B. Context7, MCP-Server) — NICHT für NERVE-App-Dependencies
- IDE-Funktionen (Grep, Find, Refactor-Tools) — verändern Source aber führen nicht aus

### Folge für GSD-Workflow

Plan-Author + Executor müssen Test-Abnahmen **auf dem Server** laufen lassen, nicht lokal. Kostet pro Abnahme 30-60s (SSH), stellt aber sicher, dass „Tests gruen" ueberhaupt Aussagekraft hat.

⚠ **KORRIGIERT 2026-08-03 (Gemini-Fund): In diesem Abschnitt standen bis heute woertliche
Beispiele mit `deploy.sh staging` und `ssh deploy@staging.getnerve.app` — obwohl 60 Zeilen
darueber steht, dass Staging KOMPLETT raus ist. Ein Agent kopiert Code-Beispiele woertlich,
statt sie im Kopf gemaess Prosa-Regel umzuschreiben. Die Beispiele sind jetzt auf Production
umgestellt.**

**Workflow pro Plan-Task:**

1. Code-Edit (lokal in der IDE — nur Editieren, kein Ausfuehren)
2. `git commit`
3. `git push`
4. `bash deploy.sh production` — das Test-Tor laeuft dabei **auf dem Server** vor dem Neustart
5. Bei rotem Tor: **kein Neustart, der alte Stand bleibt live.** Das ist kein Fehlschlag, sondern der Zweck des Tors.
6. Bei gruenem Tor: Neustart = live → Live-Test im Browser auf `https://app.getnerve.app` mit dem Test-Konto

### Konsequenz für Plan-Author

`<verify>`-Sektionen so formulieren, dass die Pruefung **auf dem Production-Server** laeuft, nicht im lokalen Arbeitsverzeichnis.

Pattern für Plan-Author:

```xml
<verify>
  <automated>bash deploy.sh production</automated>
  <!-- Das Test-Tor laeuft serverseitig im Deploy. Fuer gezielte Einzelpruefungen read-only: -->
  <!-- ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh <cmd>' -->
</verify>
```

NICHT mehr:

```xml
<verify>
  <automated>cd C:\Users\andre\dev\salesnerve && pytest tests/test_X.py -x</automated>
</verify>
```

### Anti-Inkonsistenz-Reflex

Wenn beim Schreiben von Plan-Files oder Diskussionen "ja aber Ausnahmen" hochkommen (z.B. "Unit-Tests sind doch lokal okay" / "schnell mal eben pytest lokal"), ist das die Falle. Die Trennlinie wird sonst weich, der Local-Dev-Modus kommt zurück. Klartext-Direktive von Andre: keine Ausnahmen.

### Beleg warum die Regel notwendig ist

**Aus heutiger Session (Phase 08.23.2.D Live-Test 2026-05-27):**

- Plan 01-05 alle lokalen Pytests grün
- ABER lokaler Server-Start scheiterte an CORS-Origin-Block (`CORS_ORIGIN` default = `https://getnerve.app`)
- Plus GLiNER-Pre-Warm-Hang (~800MB Hugging-Face-Download ohne HF_TOKEN)
- Plus heute Vormittag hat lokaler Pytest den Flask-Context-Bug NICHT gefangen — Cross-AI Gemini hat ihn gefangen

Lokale Tests sind Schein-Sicherheit. Auf Staging zu gehen ist Pflicht.

## HART-Erweiterung 2026-05-27 — Daten/Schema/Logs werden von Staging gezogen

**Zweite Schicht der HART-Regel "Kein Local-Dev" (Andre-Direktive 2026-05-27):**

Code-LESEN lokal ist OK weil git die Synchronität garantiert. ABER alles was Live-Zustand betrifft (DB-Schema, Real-Daten, Environment, Flask-Routes, Logs, Service-Status), wird via `scripts/inspect.sh` von Staging gezogen — nicht lokal aufgerufen.

### Pflicht-Werkzeug: `scripts/inspect.sh`

Read-only Wrapper auf Staging-Server `/opt/nerve/app/scripts/inspect.sh`. SQL-Injection-sicher (Whitelist [a-z_][a-z0-9_]*), Secret-sicher (env-keys gibt nur Namen, nie Werte).

**SSH-Pattern für GSD-Plan-Author + Research-Phase + Pre-Execute-Audit:**

```bash
ssh -i ~/.ssh/nerve_vps root@178.104.82.166 \
    'cd /opt/nerve/app && bash scripts/inspect.sh <command> [args]'
```

### Plan-Author-Pflicht-Pattern (für `<read_first>`-Sektionen)

**NICHT mehr (lokal):**

```xml
<read_first>
  - database/models.py Z.644-693 (Call-Modell aktueller Stand)
  - inspect(engine).get_columns('calls') Output
</read_first>
```

**STATTDESSEN (Staging):**

```xml
<read_first>
  - ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh schema calls' (Live-Schema-Stand)
  - ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh constraints calls' (CHECK-Constraints)
  - ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh sample calls 100' (Real-Daten-Sample)
  - database/models.py Z.644-693 (ORM-Definition — Code-Lesen lokal OK via git-Sync)
</read_first>
```

### Konkrete Befehlsabbildung

| Was der Plan-Author wissen will | Lokaler Reflex (NICHT mehr) | Staging-Befehl |
|---|---|---|
| Schema-Detail einer Tabelle | `inspect(engine).get_columns(...)` lokal | `inspect.sh schema <table>` |
| Spalten + Nullable + Type | DESCRIBE lokal | `inspect.sh columns <table>` |
| CHECK/FK/Unique-Constraints | Code in models.py lesen | `inspect.sh constraints <table>` |
| Real-Daten-Sample | `SELECT * LIMIT N` lokal | `inspect.sh sample <table> <N>` |
| Row-Count | `COUNT(*)` lokal | `inspect.sh count <table>` |
| Alle Tabellen | `\dt` lokal | `inspect.sh tables` |
| Migration-Stand | `alembic current` lokal | `inspect.sh migrations` |
| Flask-Routes | `app.url_map.iter_rules()` lokal | `inspect.sh routes` |
| Live-Logs | gibt es lokal nicht | `inspect.sh logs [N]` |
| Nur Errors aus Logs | gibt es lokal nicht | `inspect.sh logs-errors [N]` |
| /api/health Output | lokal nicht aussagekräftig | `inspect.sh health` |
| Git-Stand (Commit + Working-Tree) | lokal nicht repräsentativ | `inspect.sh git-stand` |
| Service-Status | gibt es lokal nicht | `inspect.sh service-status` |
| Environment-Variablen | `cat .env` lokal | `inspect.sh env-keys` (NUR Namen, Secret-Safety) |
| Code-Grep auf deployed Stand | `grep -rn` lokal | `inspect.sh grep <pattern>` |

### Folgen für andere CLAUDE.md-Punkte

- **Punkt 13 (Real-Daten-Validation):** der Pflicht-Schritt "Real-Daten-Sample ziehen" läuft ab sofort über `inspect.sh sample`-SSH. Sonst ist Validation wertlos.
- **Punkt 15 (Logging-First-Debugging):** Logs via `inspect.sh logs` / `logs-errors`, nicht lokal. Neue Diagnose-Ausgaben werden committet → `deploy.sh production` → dann via `inspect.sh logs` gelesen.
- **Punkt 19 (Pre-Execute-Audit):** neuer Pflicht-Check — "Greifen alle Daten/Schema/Routes-Pulls in den Plan-Files auf Staging zu, nicht lokal?" Wenn lokal → BLOCK + Replan.
- **Punkt 20 (Pflicht-grep):** der Pflicht-grep läuft ab sofort entweder lokal auf git-pulled Code ODER via `inspect.sh grep` auf Staging — beide äquivalent solange Code synchron ist. Pflicht: vor dem Grep `git pull origin/main` damit lokaler Stand = Staging-Stand.

### Anti-Inkonsistenz-Reflex (Erweiterung)

Wenn beim Schreiben von Plan-Files / Discuss / Research ein lokaler DB-/Routes-/Logs-Befehl reinrutscht ("nur kurz lokal nachschauen"), STOP. Lokale Antworten zu Live-Zustand sind Schein-Sicherheit. Auf Staging-Inspect-Befehl umstellen, dann weitermachen.

## Punkt 21 — Cross-Layer-Audit-Pflicht (verankert 2026-05-28)

Vollständige Begründung in `Nerve-Vault/CLAUDE.md` Punkt 21. Hier die GSD-relevante Kurzfassung.

**Verankerungs-Anlass (D.UX-Bug 2026-05-28):**

Phase 08.23.2.D.UX hatte einen Bug der durch ALLE drei Schutzschichten gerutscht ist — Cross-AI Gemini (Pre + Post), zwei Pre-Execute-Audit-Runden (Claudian), GSD's interne Verification. Plan 04 hat in `routes/learning.py` angenommen `conv.log_entries` ist eine DB-Spalte auf conversation_logs. War aber nur eine Code-Variable im RAM während des Calls — DB-Spalte existiert nicht. outcome_service.classify() bekam leere log_entries-Liste → Haiku rät blind ohne Wortlaut → 0.65 confidence → outcome=NULL → kein Modal angezeigt → D.UX-Feature funktional broken trotz "All edits succeeded"-Bestätigung.

**Wurzel-Pattern:** Aktuelle Audit-Schichten prüfen Code-Pfade (was wird aufgerufen, was wird gelesen/geschrieben), aber NICHT die darunterliegende Daten-Persistenz-Schicht (wo werden die Daten WIRKLICH gespeichert, existiert die angenommene DB-Spalte/Tabelle/Datei?). Cross-Variable-Naming-Falle: nur weil eine Code-Variable `log_entries` heißt heißt nicht dass es eine DB-Spalte `log_entries` gibt.

### Pflicht-Aktion für Plan-Author (GSD)

Bei jedem Plan der Daten LIEST oder SCHREIBT muss eine neue Pflicht-Sektion `## 5. Persistenz-Schicht-Verifikation` enthalten sein:

1. **Liste aller DB-Tabellen** die der Plan anfasst (lesen oder schreiben)
2. **Für jede Tabelle:** `inspect.sh schema <table>`-Output als read_first-Beleg zitieren — nicht aus dem Bauch raten, nicht delegieren an Executor
3. **Cross-Layer-Konsistenz-Tabelle:** jedes gelesene/geschriebene Datum mit Persistenz-Schicht (DB-Spalte/Datei/RAM/Cache)
4. **Falls Datum in mehreren Schichten existiert:** explizite Auswahl welche Schicht der Plan nutzt + Begründung

**Pflicht-Beispiel-Template für die Sektion:**

```markdown
## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen

- `conversation_logs` (lesen) — siehe inspect.sh-Output unten
- `calls` (schreiben) — siehe inspect.sh-Output unten

### inspect.sh-Beleg

```
$ ssh ... 'bash scripts/inspect.sh schema conversation_logs'
[Output verbatim hier einfügen, NICHT zusammenfassen]
```

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| `conv.log_entries` | gelesen in classify() | KEINE DB-Spalte — nur RAM + TXT-Datei | ❌ inspect.sh zeigt: existiert nicht |
| `call.outcome` | geschrieben | DB-Spalte calls.outcome | ✓ inspect.sh bestätigt |

### Bei Diskrepanz: STOP + Replan
```

### Pflicht-Check für Plan-Checker

Wenn ein Plan Daten anfasst und die Sektion "Persistenz-Schicht-Verifikation" fehlt ODER unvollständig befüllt ist (inspect.sh-Output fehlt, Tabelle leer, keine Cross-Layer-Konsistenz-Tabelle): **BLOCK-Verdikt**, kein Cross-AI-Review bis nachgeholt.

### Pflicht-Check für Cross-AI Gemini

Cross-AI-Briefing muss bei Daten-anfassenden Plänen explizit fragen:
- "Werden alle gelesenen/geschriebenen Daten in der wirklichen Persistenz-Schicht erwartet?"
- "Ist der inspect.sh-Output im Plan substantiell (echter Output) oder nur Pseudo-Code-Block?"
- "Gibt es Code-Variablen die DB-Spalten-Namen tragen aber keine DB-Spalten sind?"

### 10-20%-Lese-Aufwand-Regel

Audit-Schichten dürfen nicht nur den Plan + den direkten Code lesen. Sie müssen 10-20% darüber hinaus:
- Welche DB-Tabellen sind betroffen? Schema via inspect.sh verifizieren.
- Wo werden die Daten persistiert? Cross-Layer-Konsistenz prüfen.
- Cross-Variable-Naming-Check: passt der Code-Variable-Name zur DB-Spalte?

### Verhältnis zu anderen Punkten

- **Punkt 13 (Real-Daten-Validation):** prüft Schema-vs-Real-Daten. Punkt 21 prüft Code-vs-Schema-Konsistenz.
- **Punkt 14 (Pre-Insert-Control-Flow-Audit):** 4 Schichten. Punkt 21 fügt **Schicht 5** hinzu (Persistenz-Schicht-Verifikation).
- **Punkt 19 (Pre-Execute-Audit):** Claudian's Audit erweitert sich um eine fünfte Pflicht-Frage zur Persistenz-Schicht.
- **Punkt 20 (Pflicht-grep):** prüft Code-Pfad-Sinnhaftigkeit. Punkt 21 prüft Cross-Layer-Annahmen. Beide parallel.

### Geltungsbereich

- Pflicht bei jedem Plan der DB-Spalten liest oder schreibt
- Pflicht bei jedem Plan der via getattr/setattr auf Model-Objekte zugreift
- Pflicht bei jedem Plan der Migrations-Annahmen über existing Spalten macht
- Skip-OK: rein UI-Tweaks ohne Daten-Pfad-Änderung, CSS-Polish, String-Updates

## Punkt 22 — Verbindungs-Karten-Pflicht vor Namen-/Schema-/Tabellen-Entscheidungen (verankert 2026-06-01)

Vollständige Begründung in `Nerve-Vault/05 Log` (G/MEET-Saga 2026-06-01). Hier die GSD-relevante Kurzfassung.

**Verankerungs-Anlass (G/MEET 2026-06-01):** GSDs Discuss-Agent empfahl "tenant_id ist tot, neue Tabellen kriegen org_id" — eine reine Annahme. `grep` + Phase-08.23.2.A-SPEC zeigten: `tenant_id` ist bewusst gelegte Deferred-FK-Foundation, NICHT tot. Hätte zu Split-Brain (calls=UUID-tenant, accounts=Integer-org) geführt. Gefangen NUR weil vor dem Festklopfen eine bewiesene Verbindungs-Karte verlangt wurde. Dieselbe Phase fing später noch 2 Production-Defekte (empty-string-GUC, SHA-256-Re-ID) — alle durch dieselbe Beweis-statt-Annahme-Disziplin.

**Pflicht-Aktion bei jeder Plan-Phase die Namen / DB-Schema / Tabellen / Spalten / DB-Rollen festlegt:**

Bevor IRGENDEIN Name/Tabelle/Spalte/Schema-Identifier im Plan festgeklopft wird, MUSS eine **Verbindungs-Karte** als eigenes Artefakt (RESEARCH.md oder Plan-Sektion) vorliegen — nichts aus Annahme, alles bewiesen:

1. **NAMEN/IDENTIFIER:** jeder Kandidat via `grep -rn` in services/ routes/ database/ alembic/ + Treffer-Zählung pro aktivem Production-Pfad (Tests/Migrationen getrennt zählen). Entscheidung wird mit der Treffer-Liste begründet — **was LEBT gewinnt, nicht was der Plan/das Doc wünscht.** Kein neuer Name / keine neue Parallel-Spalte ohne Beweis dass die alte tot ist (0 aktive Leser/Schreiber im Production-Pfad).
2. **TABELLEN/SPALTEN:** jede angefasste Tabelle gegen Production verifiziert — `inspect.sh schema <t>` ODER `sudo -u postgres psql -c "\d <t>"` wenn privilege-maskiert (z.B. training.*/Rollen-Attribute sieht nerve_app nicht). Existiert sie? Typ? Constraints? Befüllt?
3. **WER SCHREIBT / WER LIEST + Schicht-Check (Punkt 21):** pro Verknüpfung der echte Code-Pfad (welche Funktion schreibt/liest, welche Datei, welcher Thread/Worker) + liegt das Datum wirklich da wo angenommen (DB-Spalte/RAM/Datei).
4. **REICHWEITE:** pro Entscheidung der umgebende Code (~30 Zeilen) + was die Entscheidung sonst berührt (andere Worker, Migrationen, RLS-Policies, SocketIO/Thread-Pfade).

**Beweis pro Behauptung, nicht Prosa:** jeder Punkt mit `grep file:line` UND inspect.sh/psql-Output. Bei Researcher-Subagent: Karte physisch in Datei schreiben, KEINE komprimierte Prosa-Zusammenfassung an den Orchestrator zurück (Informationsverlust-Schutz).

**Kontroll-Mechanismen:** Plan-Checker BLOCKt wenn die Karte fehlt oder unbewiesen ist (Behauptung ohne grep/inspect-Beleg). Cross-AI Gemini prüft Substanz. Claudian-Pre-Execute-Audit (Punkt 19) verifiziert dass die Karte bewiesen statt behauptet ist — bei "X ist tot" ohne grep-Beleg → BLOCK + zurück.

**Geltungsbereich:** Pflicht bei jeder Plan-Phase mit Namen-/Schema-/Tabellen-/DB-Rollen-Entscheidung. Skip-OK: reine Logik-Bugfixes, CSS, String-Updates ohne neue Identifier.

**Verhältnis zu anderen Punkten:** synthetisiert Punkt 14 (Control-Flow), 20 (Pflicht-grep) und 21 (Cross-Layer) in EIN bewiesenes Artefakt — die Karte ist das Plan-Deliverable, die anderen Punkte sind die Checks darin.

## Punkt 23 — Tabellen-Dokumentations-Pflicht (Schild an jeder Tabelle) — verankert 2026-06-10

Quelle: `Nerve-Vault/04 Entscheidungen/NERVE TAXO-Gerüst (verriegelt).md` §0.2. Umgesetzt in Phase 08.23.2.SCHILD (Migration 0015, pg_description aller 3 Schemas).

**Die Regel (6 Punkte aus §0.2):**

1. **Schild = Postgres-`COMMENT`** auf JEDER Tabelle UND jeder nicht-trivialen Spalte (in `models.py` via `comment=`, in die DB via Alembic-Migration).
2. **Inhalt des Schilds:** `"<Zweck/Business-Logik>. Status: <lebt|Reserve/Foundation|write-only [ZOMBIE]>. Schreibt <datei.py:zeile>; liest <datei.py>."` — knackig, aber alle drei Teile + ≥10 Zeichen.
3. **Schild lebt im Code** (`models.py` `comment=`) und wird per Migration in `pg_description` geschoben — KEIN zweites Tagebuch.
4. **KEINE Historie/FK-Pfade im Schild-Text** (zu brüchig). Die „wann/warum"-Historie kommt aus `inspect.sh schilder` (Migrationen, die die Tabelle berühren), nicht aus dem COMMENT.
5. **Trivial-Spalten-Konvention (L-04, NICHT kommentieren):** `id`, `created_at`, `updated_at`, `erstellt_am`, `aktualisiert_am`, `*_id` (FK/Refs), `is_*`/`aktiv` (Flags), UUID-PK. Alles andere = nicht-trivial = braucht ein Schild.
6. **Zombie-Regel:** tote/write-only Tabellen werden NUR per Status `[ZOMBIE]`/`write-only` im Schild markiert — NICHT gelöscht (Löschung/Reparatur = eigener Cleanup/TAXO-Bau, nach grep-Beleg).

**Workflow-Pflicht (Anti-Abrieb):** Wer einen Code-Pfad ändert, der eine Tabelle/Spalte liest/schreibt, oder eine neue Tabelle/Spalte anlegt, **zieht das Schild in DERSELBEN Änderung nach** (`comment=` in models.py + COMMENT-Migration).

**Schild-AKTUALITÄTS-Pflicht (André 2026-06-25, kanonisch):** Ein Schild, das **nicht aktuell** ist ODER **nicht alle relevanten Leser/Schreiber abdeckt**, ist **NUTZLOS** — schlimmer als kein Schild, weil es eine falsche Wahrheit vortäuscht (jemand liest „Schreibt X" und vertraut darauf, obwohl längst auch Y schreibt). Der SCHILD-Guard (`test_schild_guard.py`) erzwingt nur **Vorhandensein + Länge ≥10**, **NICHT Aktualität** — er kann ein veraltetes/unvollständiges Schild nicht fangen. Daher:

- **Pflicht:** Wer den **Lese-/Schreib-Pfad** einer Tabelle ändert — neuer Schreiber, geänderter Mechanismus (z.B. separates Objekt → In-Place-Update), neue Konsum-Stelle — zieht das Tabellen-/Spalten-Schild (Zweck/Business-Logik + Status + Schreibt/liest-Liste, §0.2 Punkt 2) im **SELBEN Commit** nach. Das ist die Aktualitäts-Hälfte der Anti-Abrieb-Regel: nicht nur „ein Schild existiert", sondern „das Schild **stimmt noch**".
- **Vollständigkeit:** die `Schreibt <datei.py>; liest <datei.py>`-Liste muss **ALLE** aktiven Produktiv-Pfade nennen (grep-belegt, wie Punkt 22) — ein vergessener zweiter Schreiber macht das Schild irreführend.
- **Kontroll-Mechanismus:** Pre-Execute-Audit (Punkt 19) + Code-Review prüfen bei **daten-anfassenden Phasen** explizit die **Schild-Aktualität** (deckt der Schild-Text die im Plan geänderten/neuen Leser/Schreiber + den Mechanismus ab?). Diskrepanz = Schild nachziehen, BEVOR die Phase als fertig gilt.

**Guard (Deploy-Block):** `tests/test_schild_guard.py` prüft server-side gegen Postgres über `pg_description` aller 3 Schemas (public/crm/training), dass jede Tabelle + nicht-triviale Spalte ein Schild ≥10 Zeichen hat. Läuft als OS-User `nerve_app` (peer-auth, Catalog-Read braucht KEINEN GRANT) mit `NERVE_SCHILD_TEST_DSN`; skippt lokal/SQLite (kein False-Green). Fängt auch ORM-lose Tabellen (z.B. `training.transcript_archive`), weil er die DB prüft, nicht models.py.

**Werkzeug:** `inspect.sh schilder <tabelle>` zeigt Tabellen-Schild + Spalten-Schilder + best-effort Migrations-Historie (für public UND crm/training).

**Migrations-Stil:** neue Schilder via `op.execute("COMMENT ON TABLE/COLUMN ... IS '...'")` in einer Migration (hauseigenes Muster aller Migrationen, Cross-AI-Finding 1) — KEIN autogenerate-Round-Trip nötig.

**Geltungsbereich:** Pflicht bei jeder neuen Tabelle/Spalte + bei jeder Änderung an deren Leser/Schreiber. Skip-OK: reine UI/CSS/String-Edits ohne DB-Bezug.

## Punkt 24 — Rollende Voraus-Planung + 3 Sichten (verankert 2026-06-11)

Quelle: `Nerve-Vault/CLAUDE.md` → „Vorgehens-Prinzip: Rollende Voraus-Planung + 3 Sichten" (Andre-Direktive nach der TAXO-Erfahrung). Gilt für Plan-Author, Executor, Reviewer.

### Teil A — Rollende Voraus-Planung (immer EINEN Roadmap-Brocken vorausplanen)

Ein großer Roadmap-Brocken wird in Phasen aufgeteilt und **bis kurz vor Execute** geplant. **Bevor** der aktuelle Brocken executet wird, wird der **nächste** Brocken so weit geplant, dass die **gemeinsamen Verträge/Nahtstellen** geprüft werden können. So liegen ≥2 Brocken-Pläne nebeneinander und man fängt Vertrags-Drifts (Schema/Schnittstelle/Daten-Fluss), die der aktuelle Brocken sonst falsch zementiert, VOR dem Bau. Anker-Beleg: TAXO1/2/3 teilen den `intent_event`-Vertrag; der Interlock fing I-1/I-2/I-3 + den I-4-Launch-Blocker, die im Einzelplan + Standard-Cross-AI durchgerutscht waren.

**Drei harte Leitplanken (für den Plan-Author):**
1. **VERTRAGS-tief, nicht BAU-tief.** Vom nächsten Brocken NUR die gemeinsamen Verträge festzurren (DB-Tabelle/Schema, Funktions-/API-Signatur, Daten-Fluss-Naht). NICHT bis zur Bau-Reife durchdetaillieren — ein zu weit vorausgeplanter Detail-Plan verrottet (der Code ändert sich beim Bauen des aktuellen Brockens). Details des nächsten Brockens erst kurz vorm Bauen.
2. **Genau EIN Brocken voraus.** Nicht zwei+ (Kartenhaus).
3. **Kopplungs-abhängig.** Voller Interlock NUR wenn der nächste Brocken einen gemeinsamen Vertrag/eine Architektur-Naht mit dem aktuellen teilt. Unabhängige Brocken (kein gemeinsamer Schreib-/Lese-Pfad, kein geteiltes Schema) → leichter Check oder skip.

**Interlock-Schritt vor Execute (Pflicht bei gekoppelten Brocken):** alle relevanten Phasen-Pläne nebeneinander legen, die geteilten Verträge gegeneinander greppen (gleicher Tabellen-/Spalten-/Signatur-Name? gleiche Semantik? gleiche Arbeitslisten-/Trigger-Invariante?). Divergenz = STOP + auflösen, BEVOR der aktuelle Brocken gebaut wird. Plus: **„erst alle Blocker des aktuellen Brockens fixen, dann nächster Teil"** (Andre 2026-06-11) — kein Bau auf einem Fundament mit bekanntem Loch (Anker: TAXO1-04-Blocker I-4 vor TAXO3).

### Teil B — 3 Sichten: Gemini bei ALLEN substanziellen Fragen (erweitert die GSD-Workflow-Pflichten + Cross-AI-Regel)

Default ist drei unabhängige Sichten auf jede substanzielle Entscheidung: (1) Andre + Claudian (Vault-Strategie), (2) GSD/Claude Code (Code-Repo), (3) **Gemini** (anderes Gehirn, andere Blindstellen). Cross-AI mit Gemini wird damit der Default — nicht mehr NUR beim formalen `/gsd-review`, sondern auch bei: Discuss-Grau-Zonen, Plan-Entscheidungen, Interlock-Checks, Audit-Funden, Architektur-/Design-Fragen, nicht-trivialen Bug-Diagnosen.

**Einzige Ausnahme (Anti-Inflation):** echt-triviale/mechanische Dinge (Renaming, CSS, String-Fixes, Tippfehler, Bugfix mit glasklarer Root-Cause). Da ist Gemini Rauschen.

**Pflicht-Disziplin:**
- **Gemini liest bei echten Reviews den REALEN Code read-only** (aus dem Repo / auf die Dateien gezeigt, Schreib-/Ausführ-Rechte verweigert) — NICHT nur zugefütterte Auszüge. Grund: nur Auszüge geben macht den Frager zum Filter und vererbt dessen blinde Flecken (genau die soll die 3. Sicht finden). Read-Zugriff ist kein Sicherheitsthema (nur Schreiben/Ausführen bleibt verboten). Auszüge nur für geschlossene Logik-Checks („Plan A vs B — Widerspruch?"), dann als „prüft die Auswahl" markiert. **Bleibt (gilt für alle):** Gemini sieht Code im Ruhezustand, nicht den Live-Server → Befunde gegen `inspect.sh`/Live gegenprüfen. (Intuition: ein Bauteil ohne Sicht auf seinen Einbau-Ort entwerfen → landet an unerreichbarer Position, der Mechaniker zahlt — Review ohne Einbau-Ort ist dasselbe Anti-Pattern.)
- **Gegenleser, kein Bauer:** Gemini via `agy -p`/`gemini -p` (reiner Antwort-Modus) oder interaktiv mit verweigerten Schreib-/Ausführ-Rechten. NIEMALS unseren Code eigenständig anfassen lassen. Modell: `gemini-3.1-pro-preview` (bzw. agy Gemini 3.1 Pro High ab 15.06.), Flash als Notausweich.
  **⚠ BEHOBEN 2026-08-06 — diese Regel war RICHTIG und wurde trotzdem monatelang unterlaufen:** `~/.gemini/settings.json` stand auf **`gemini-2.5-pro`**. Wer `gemini -p` **ohne `-m`** aufruft (also der Normalfall, u.a. `/gsd-review --gemini`), bekam die **Voreinstellung** — eine Generation älter als das hier vorgeschriebene Modell. **Die Regel zu kennen genügte nicht; die Voreinstellung hat sie ausgehebelt.** Belegter Schaden: der Cross-AI-Lauf zu 08.23.2.MEHRNUTZER-REST-1 (06.08.) lieferte vier Befunde, aber **keinen einzigen Gegenbefund** auf die harten Fragen — bestätigend statt angreifend. **Fix: Voreinstellung auf `gemini-3.1-pro-preview` gesetzt** (Sicherung: `settings.json.bak-2026-08-06`), verifiziert mit einem Aufruf **ohne** `-m`. **Nachgemessen, welche Namen der Zugang kennt:** `gemini-3.1-pro-preview` ✅ · `gemini-3-pro-preview` ✅ · `gemini-3.1-pro` ❌ · `gemini-3-pro` ❌ · `gemini-2.5-pro` ✅ (alt) · `gemini-2.5-pro-latest` ❌. **Das Anhängsel `-preview` ist Pflicht** — ohne es antwortet der Anbieter „not found", und wer das für „Modell gibt's nicht" hält, fällt stillschweigend auf die alte Voreinstellung zurück.
  ⚠ **Zwei Betriebs-Hinweise:** Das Preview-Modell wirft gelegentlich `503`/`fetch failed` — das Werkzeug wiederholt selbst, ein **einzelner** Fehlversuch ist **kein** Beleg, dass ein Modell fehlt (genau das hat mich hier zuerst in die Irre geführt). Und: Ein Preview-Name kann jederzeit abgeschaltet werden — bricht **jeder** Review, dann Rückfall auf `gemini-2.5-pro` und hier vermerken.
  **★ Und die Lehre, die über Gemini hinausgeht:** Eine Regel, die ein Werkzeug korrekt beschreibt, ist wertlos, wenn die **Voreinstellung des Werkzeugs** etwas anderes tut. Bei jedem Werkzeug mit Voreinstellung gilt: **die Einstellung prüfen, nicht die Regel lesen.**
- Cross-AI-Entscheidung + -Funde pro Brocken in `Nerve-Vault/05 Log` dokumentieren.

**Geltungsbereich:** Pflicht-Prozess bei jedem großen Roadmap-Brocken (Plan→Interlock→Execute). Skip-OK nur für 🟢-triviale Einzelaufgaben.

## Punkt 25 — Latenz ist ein Dealbreaker (verankert 2026-06-12)

Quelle: `Nerve-Vault/CLAUDE.md` → „HART: Latenz ist ein Dealbreaker". Andre-Direktive: Antworten müssen schnell SEIN, nicht nur gut — eine bessere Antwort, die spürbar später kommt, ist im Live-Call wertlos.

**Regel für Plan-Author/Executor/Reviewer:** Jedes Feature, das einen Live-Antwort-/Erkennungs-Pfad berührt (EWB-Antwort, QA, Slot-A/B, Live-Cue, intent_event-Emit), nennt im Plan ein **Latenz-Budget** und prüft die Änderung dagegen. **Antwort-Latenz ist gleichrangig mit Qualität, nicht nachrangig.**

**BALANCE (André 2026-06-12):** GLEICHGEWICHT, nicht „schnell gewinnt". **Schnell-aber-Müll = genauso Dealbreaker wie gut-aber-langsam** (Haiku-Müll in 200ms so wertlos wie Sonnet-Gold in 2-3s). **Ambition: das STARKE Modell schnell genug machen, NICHT aufs schwache ausweichen.** Wenn Sonnet via Caching/Prompt-Größe/First-Token-Streaming/Vorladen auf wenige ms kommt → klar Sonnet. Die schnellen Hebel machen das gute Modell schnell — sie sind keine Ausrede fürs schwache.

- **Modell-Wahl IST eine Latenz-Entscheidung** (Haiku schnell/schwach vs Sonnet langsam/stark) — bewusst abwägen, nicht blind auf Qualität. Bau-Regel 1 (kein LLM in der schnellen Live-Bahn) bleibt.
- **Schnelle Hebel zuerst** (vor „langsameres stärkeres Modell"): lokales Slot-A-Sofortnetz, Prompt-Caching (stabile Prompt-Teile gecacht — CACHE_* bereits vorhanden), fokussierte/kleine Prompts, paralleles Vorladen.
- **Streaming hilft dem Gefühl, nicht der Roh-Latenz** bis zum ersten sinnvollen Wort.
- **Pre-Execute-Audit Pflicht-Frage (Punkt 19 ergänzt):** „Erhöht dieser Pfad die spürbare Antwort-Latenz? Um wie viel? Im Budget?" Deutlicher Anstieg → Dealbreaker, umdesignen, NICHT „bauen + später optimieren".

**Gilt besonders für TAXO3:** die Qualitäts-Verbesserung (gutes Antwort-Paradigma, Rollen-Bewusstsein, ggf. stärkeres Modell) darf das Tempo nicht opfern — die Latenz-Lösung (Slot-A-Sofortnetz + Caching + Modell-Abwägung) ist Teil des Scope, kein Nachgedanke.

## Punkt 26 — Async-Daten-Bereitschafts-Naht: vor jedem Lese-Schritt prüfen WANN die Daten geschrieben werden (verankert 2026-06-26)

Quelle: `Nerve-Vault/CLAUDE.md` → Punkt 22. Dort die volle Begründung; hier die GSD-relevante Kurzfassung. **Dritter Vorfall derselben Klasse → Regel.**

**Die Falle:** Ein Schritt (Live-Benoter, Slow-Lane-Consumer, Merge, Hintergrund-Job) LIEST Daten, die ein ANDERER Pfad (Hintergrund-Thread, Batch-Job, separate Pipeline) erst SPÄTER schreibt. Läuft der Leser bevor der Schreiber geschrieben hat → er liest NULL/leer/stale und schließt daraus **still falsch** (kein Fehler im Log, nur ein falsches Ergebnis). Spezialfall von Race-Condition (Punkt 14): zeitlicher Versatz zwischen Schreib- und Lese-Pipeline.

**Drei Vorfälle (Trigger):**
- **CALLID (24.-25.06.):** Hintergrund-Schleifen reichten `call_id`/Tenant nicht durch → leer beim Lesen.
- **Audio-Race (26.06.):** Call-Ende-Merge las `calls.audio_health_score` BEVOR der `_audio_health_bg`-Thread (Start bei `api_beenden`) ihn schrieb → NULL → fälschlich `poor_audio_health` bei Audio=0.93. Fix: Fan-In-Flag `calls.audio_health_resolved` (Migration 0027).
- **Handling-Timing (26.06.):** `_persist_event_ref`→`_find_next_advisor_utterance` benotet ~30ms nach Einwand-Emit (LIVE), aber `transcript_segments` werden gebündelt am Call-Ende geschrieben (~25-58s später, alle `created_at` identisch) → Benoter findet nie den Berater-Antwort-Satz → enthält sich IMMER → Einwand-Behandlung nie benotet. Plus: Lookup ankerte auf `created_at` (Batch-Schreibzeit) statt `ts_ms` (Sprech-Zeit).

**Pflicht-Check für Plan-Author + Plan-Checker + Cross-AI — bei JEDEM Schritt der Daten eines anderen Pfades liest:**
1. **„Wann wird diese Quelle TATSÄCHLICH geschrieben?"** — live/inkrementell, Batch-am-Call-Ende, oder Hintergrund-Thread/Job? Am echten Code + an Prod-Daten belegen (z.B. `inspect.sh` — identische `created_at` einer Zeilen-Gruppe = Batch-Write; Schreibstelle greppen). NICHT annehmen.
2. **„Kann mein Leser dem Schreiber vorauslaufen? Was liest er dann (NULL/leer/stale) und was schließt der Code daraus fälschlich?"**
3. **Zeit-Anker:** Sortiert/filtert der Leser nach Zeit → nutzt er die **Sprech-/Ereignis-Zeit** (fachlich korrekt) oder die **DB-Schreib-Zeit** (`created_at`, bei Batch-Write wertlos)?

**Wenn der Leser vorauslaufen kann → Fan-In-Bereitschafts-Naht bauen** (Muster `audio_health_resolved`): Leser wartet auf ein explizites „X resolved"-Signal (Flag/Marker), ODER wird vom Schreiber-Abschluss neu angestoßen. „NULL" erst NACH „resolved" als „wirklich absent" werten. Signal IMMER setzen (try/finally + Nicht-gestartet-Pfad) → kein Hang, aber OHNE neuen Zeit-Sweep.

**Plan-Sektion-Pflicht:** Bei daten-lesenden Schritten in der Persistenz-Schicht-Verifikation (Punkt 21, Sektion 5) zusätzlich eine Spalte/Zeile „**Schreib-Zeitpunkt** (live/batch/bg-thread) + kann Leser vorauslaufen?". Fehlt sie bei einem Schritt der fremd-geschriebene Daten liest → Plan-Checker BLOCK.

**Verhältnis:** Erweitert Punkt 14 (Race-Fragen, allgemein) + Punkt 21 (Cross-Layer — „existiert die Spalte?" → hier „ist sie zum Lese-Zeitpunkt BEFÜLLT?"). Pre-Execute-Audit (Claudian) prüft das mit.

## Punkt 27 — Einfachster tragfähiger Weg zuerst (verankert 2026-06-28)

Quelle: `Nerve-Vault/CLAUDE.md` → „Leitsatz 2". Hier die GSD-relevante Kurzfassung.

**Regel:** Vor jedem Plan/Bau die Pflicht-Frage: *Gibt es einen einfacheren Weg, der das Problem genauso richtig löst?* Den einfachsten **tragfähigen** Ansatz wählen — nicht den billigsten Hack, den einfachsten, der wirklich funktioniert. Erst wenn der auf eine echte Wand stößt → Plan B. **Über-Engineering ist eine Form von Abrieb** (komplexe Mechanik, die ein einfacherer Ansatz auflöst), gleichrangig mit der „lieber einmal richtig"-Regel.

**Beleg-Fall:** Zwei Tage maschinelle Einwand-zu-Antwort-Anker-Mechanik (PATH B / Wartenummer / ordinale Zuordnung) gebaut — bis die Frage „denken wir zu kompliziert?" kam. Ein LLM, das am Call-Ende das ganze Transkript liest, löst die Zuordnung von selbst → die ganze Mechanik überflüssig.

**Pflicht für Plan-Author + Plan-Checker:** Wenn ein Plan eine wachsende, mehrstufige Mechanik baut (mehrere Anker-Strategien, Spezialfall-Ketten, „Härtung der Härtung"), EINMAL explizit prüfen + im Plan beantworten: *„Gibt es einen radikal einfacheren Ansatz (z.B. ein LLM-Gesamturteil statt mechanischer Verkettung), der das Problem auflöst statt es zu verwalten?"* Plan-Checker FLAG bei un-beantworteter wachsender Komplexität. „richtig" heißt **angemessen einfach**, nicht maximal ausgebaut.

## Punkt 28 — Mehr-Nutzer-Pflicht: kein globaler Live-Zustand für pro-Nutzer-Daten (verankert 2026-07-03)

Quelle: `Nerve-Vault/CLAUDE.md` → „Fable-Audit-Lehren". Beleg: Launch-Blocker — modul-globaler Live-Zustand → Cross-Tenant-Vermischung bei parallelen Calls (Phase 08.23.2.PERSID räumt es auf).

**Regel:** Kein **modul-globaler veränderlicher Zustand** für pro-Nutzer-/pro-Call-Daten. Alles im Live-Pfad (Session-State, Puffer, Zähler, Merge-Dicts, Logs) MUSS pro-sid/pro-Tenant gekeyt sein (`_session_state[sid][...]`) — NIE ein modul-global `x = {}` / `x = []`, in das mehrere gleichzeitige Sessions schreiben. **Ausnahme nur** für unveränderliche Konstanten + tenant-neutrale Caches → **expliziter Whitelist-Eintrag** im Global-Wächter, kein stilles Durchrutschen. **Grund:** solo getestet unsichtbar; 2 gleichzeitige EA-User → Daten vermischen sich (bis ins rohe Transkript + den persistierten Call-Record, cross-tenant, RLS fängt es NICHT).

**→ Wächter (Test-Netz-Ratsche, Deploy-Gate):** `tests/test_no_live_global_state.py` — statischer Sweep über `services/` + `routes/` auf das Zuweisungs-Muster `ls.<GLOBAL> = ...` im Live-Pfad; rot bei jedem nicht-per-sid-gekeyten veränderlichen Modul-Global (Whitelist für Konstanten/neutrale Caches). Muster: `test_ewb_autovar_global_regression.py` / `test_schild_guard.py`.

**→ Verify=Production-Pflicht** bei jeder Live-Pfad-Änderung: ein deterministischer Zwei-Tenant-Concurrency-Test (zwei SocketIO-Test-Clients, zwei Orgs, gemockte Deepgram/Haiku/Anon-Seams, gepaarte Positiv+Isolations-Assertions). Der echte Doppel-Anruf ist einmalige UAT, NIE das Gate.

**Plan-Author + Plan-Checker:** bei jedem user-/call-Daten-Feature explizit prüfen „schreibt hier irgendwas in einen modul-globalen Zustand statt per-sid?" — FLAG wenn ja.

## Punkt 29 — Halb-Migration-Falle: nie das Alt-Muster für neuen Code kopieren (verankert 2026-07-03)

Quelle: `Nerve-Vault/CLAUDE.md` → „Fable-Audit-Lehren". Beleg-Fall: die per-sid-Migration war halb gemacht; NEUER TAXO2-Code kopierte das verbotene globale Muster („EXAKT das Muster von record_ewb_click") — der Bug wanderte ins neue Feature.

**Regel:** Eine Migration/Refactor wird **fertig gemacht ODER der Rest wird im Foundation-Code-Register mit Aktivierungs-/Lösch-Trigger eingetragen** — kein halb-migrierter Zustand ohne Register. **Kern:** vor dem Kopieren eines bestehenden Musters/einer Funktion/einer Global prüfen, ob es das **ZIEL-Muster oder das ALT-Muster** ist — grep, ob die Vorlage einen Deprecated-Marker trägt. Nie ein deprecated Muster kopieren, weil es „noch da ist".

**→ Wächter (Deploy-Gate, im selben Test wie Punkt 28 oder daneben):** jede als abgelöst markierte Global/Funktion bekommt einen `# DEPRECATED-GLOBAL`-Marker; der Test macht jeden NEUEN Schreib-Zugriff darauf rot (erzwingt „Migration fertig ODER registriert + geschrieben-verboten").

## Punkt 30 — Neue bezahlte API / neues Modell = Kosten-Hook + ApiRate sind Pflicht (verankert 2026-07-20)

Anlass: Phase 08.23.2.KOSTEN-1. Die Live-Spracherkennung loggte `nova-3`, die Preis-Tabelle kannte nur `nova-2` — `services/cost_tracker.py` verwirft in dem Fall **still** (`if not rate: print + return`). Ergebnis: die minuten-getriebene **Hauptkostenposition war monatelang unsichtbar**, dazu acht bezahlte Call-Sites ganz ohne Hook und Haiku-Preise 4× zu niedrig. Kein Fehler im Log, nur eine zu schöne Marge.

**Die Regel:** Wer eine bezahlte API neu anbindet **oder einen Modell-String ändert**, liefert im selben Commit (a) den Kosten-Hook nach dem Muster im Block `Phase 04.7.2 Cost-Hook` in `services/claude_service.py` (try/except, niemals raisen — **ueber den Kommentar-Marker suchen, nicht ueber Zeilennummern**: der frühere Anker "542-568" war am 03.08. bereits um ~40 Zeilen verrutscht) und (b) den passenden Eintrag in der Rate-Soll-Liste `app._API_RATE_SOLL`. Ein Modellname ohne Rate ist kein „kleiner Rest" — er ist ein stilles Loch in der Marge.

**Strukturell erzwungen durch drei Wächter — zwei zur Deploy-Zeit, einer zur Laufzeit:**

| Wächter | Datei | fängt | Grenze |
|---|---|---|---|
| **W1** Raten-Abdeckung | `tests/test_api_rate_coverage.py` | geloggtes Tripel ohne aktive `ApiRate` (real-PG) | sieht nur String-Literale + die gepflegte Nicht-Literal-Liste |
| **W2** Hook-Abdeckung | `tests/test_cost_hook_coverage.py` | bezahlter Call ohne `log_api_cost` (Stufe 1 Datei-, Stufe 2 Funktions-Granularität) | sieht keine Namens-Auflösung, sagt nichts über „feuert der Hook wirklich" |
| **W3** Laufzeit-Skip-Zähler | `services/cost_tracker.py` + `tests/test_cost_skip_counter.py` | **jeden** Skip im Moment des Auftretens, egal woher der Modellname kam | RAM, pro Prozess, seit Deploy |

W1/W2 sind statische Sweeps und können ENV-/config-basierte Modellnamen (`config.MODEL_*`, `MODEL_JUDGE`, `MODEL_ADOPTION`) grundsätzlich **nicht** sehen — genau dafür gibt es W3. Sein Zähler steht im Founder-Dashboard („Kosten-Log-Skips", Soll: **0**). Steht dort eine Zahl, ist das kein Schönheitsfehler, sondern der Hinweis auf das nächste unsichtbare Loch.

**Bewusst NICHT gebaut:** keine Rate-Sync-Engine, die Preise von Anbieter-APIs zieht. Preispflege bleibt **manuell** (gepflegte Liste + Admin-UI `routes/admin_dashboard.py:393-442`). Und: alte `api_cost_log`-Zeilen werden **nie** rückwirkend korrigiert (D-02, Finanzamt-Linie) — unvollständige Zeiträume werden über `COST_DATA_COMPLETE_SINCE` **markiert**, nicht umgeschrieben.

**Zwei Fallen, die diese Phase gekostet hat — beim nächsten Mal direkt mitprüfen:**
- **Preis-Modell ≠ Preis-Liste:** Deepgram-Diarization ist ein Add-on (+$0.0020/min) und wird nur im Meeting-Modus geschaltet. Ein Preis pro `(provider, model, unit_type)` kann das nur abbilden, wenn der Modus **im Modell-String** steckt (`nova-3` vs. `nova-3-diarize`). Wo ein Anbieter Zusatzoptionen separat berechnet: eigener String statt Pauschale in die falsche Richtung.
- **Zwei Pfade, ein Modell:** Haupt-App und `nerve_rt` fuhren unbemerkt verschiedene STT-Modelle. Dagegen wacht `tests/test_stt_model_parity.py`.

## ⛔ HART: `nerve_rt` hat KEINE Anonymisierung — nicht scharf schalten, bevor sie drin ist (verankert 2026-08-02)

**Befund (Cross-AI-Audit am echten Code):** Im gesamten `nerve_rt/` gibt es **0 Treffer** fuer `anonym`. Roher Deepgram-Text wird gepuffert (`nerve_rt/services/session_manager.py:298`) und ungefiltert an die Anthropic-API geschickt (`:337-351` → `nerve_rt/services/llm/claude_adapter.py:92`). Der Dienst laeuft seit 28.07. auf Prod, hatte aber **0 Verbindungen** — bislang ist also nichts passiert. **Das bleibt nur so, solange niemand die Engine anschliesst.**

**Pflicht vor dem Scharfschalten** (Vollfassung + Vorbild-Zeilen: `nerve_rt/README.md`):
1. `anonymize()` vor **jedem** LLM-Aufruf und **jedem** DB-Insert. Vorbild: `services/deepgram_service.py:148-179`.
2. **Fail-closed:** Faellt die Anonymisierung aus, wird das Segment **verworfen**, nicht roh weitergereicht (`deepgram_service.py:154-179` + `:231`).
3. **Kein Abschalt-Schalter** — die Haupt-App hat bewusst keinen.
4. **Ein Waechter statt eines Kommentars** (Fable: *„Eine Prosa-Regel ohne Waechter kommt wieder"*). Muster existiert: `tests/test_stt_model_parity.py` faengt genau diese Zwei-Pfade-Divergenz. Analog: rot, wenn in `nerve_rt/` ein LLM-Adapter Text bekommt, der nicht durch `anonymize()` lief. **Pruefkatalog + bekannte Luecke dokumentieren** (Punkt 31).

**Warum hart:** DSGVO gilt weiter (deutscher Einzelunternehmer, auch bei US-first) · die US-Klagewelle gegen Otter.ai/Invoca stuetzt sich genau auf „Anbieter nutzt Daten fuer eigene Zwecke" · und das Produktversprechen lautet „NERVE zeichnet nichts auf".

## Punkt 31 — Ein Waechter beweist nur, was in seinem Pruefkatalog steht (verankert 2026-07-31)

Anlass: Phase 08.23.2.LOCK-2. Waechter 2 aus LOCK-1 lief ueber **102 Riegel-Bloecke** und fand
**NULL** Verstoesse — waehrend eine Selbstverklemmung die ganze Zeit im Code stand
(`services/claude_service.py:2062` nahm den Riegel, `:2076` rief `ls.get_anonymisierer(sid)`,
das denselben Riegel nochmal nimmt). Sein Verbots-Set kannte `get_session`, `SessionLocal`,
`messages.create/stream`, `sio.emit`, `requests.*`, `sleep`, `join` — **aber nicht die erneute
Riegel-Nahme**. Der Waechter war nicht falsch, er war **unvollstaendig**. Sein gruenes Ergebnis
war **wahr und wertlos zugleich**, und es hat die Suche nach dem Halter zwei Tage in die
falsche Richtung gelenkt.

**Die Regel:** Wer einen Waechter baut oder erweitert, schreibt in **denselben** Commit, was
der Waechter **NICHT** prueft. Die Restluecken gehoeren
(a) in den **Modul-Docstring** des Waechters, unter einer Ueberschrift `RESTLUECKEN`, und
(b) ins **SUMMARY** der Phase, die ihn gebaut hat.
Ein Waechter ohne benannte Grenzen erzeugt falsche Sicherheit — er ist dann schlimmer als kein
Waechter, weil sein Gruen als Beweis gelesen wird.

**Pflicht-Bestandteile des Restluecken-Absatzes:**
1. **Was der Pruefkatalog abdeckt** — in einem Satz, positiv formuliert.
2. **Was er strukturell nicht sehen kann** (bei statischen Sweeps typisch: dynamischer Dispatch
   via `getattr`, Callbacks, Monkeypatch, Registry-Hooks; Kanten aus Modulen ausserhalb des
   Sweep-Bereichs; alles, was erst zur Laufzeit entsteht).
3. **Wo Heuristiken zweischneidig sind** — jede namens-/muster-basierte Abkuerzung mit beiden
   Richtungen: Falschtreffer **und** Durchrutscher.
4. **Was formal UNKLAR bleibt** — ehrlich als unklar markieren, nicht als „praktisch
   ausgeschlossen" wegschreiben.
5. **Welche zweite Schicht darunter liegt** — Laufzeit-Wachhund, Gate-Check, UAT. Ein
   statischer Waechter ist nie die einzige Schicht; wenn es keine zweite gibt, gehoert **das**
   in den Absatz.
6. **Was geprueft und GESCHLOSSEN wurde** — der Katalog ist keine reine Mangelliste. Klassen,
   die geprueft und **abgedeckt** sind, gehoeren mit dem Vermerk `GEPRUEFT UND GESCHLOSSEN`
   hinein, samt Rest-Kante, falls eine bleibt. Sonst weiss der naechste Leser nicht, ob eine
   nicht genannte Klasse **abgedeckt** oder bloss **nicht bedacht** war — und genau diese
   Unterscheidung ist der ganze Zweck des Katalogs. **Besonders fuer die direkteste Form der
   Fehlerklasse, gegen die der Waechter gebaut wurde:** sie darf nie unbenannt bleiben, weder
   als Luecke noch als geschlossen.

**Zwei Zusatz-Pflichten, ohne die ein Waechter nichts beweist:**
- **ROT-Beleg vor GRUEN.** Ein Waechter, der nie rot war, beweist nichts. Der Rot-Lauf ist ein
  **Acceptance-Artefakt** (Ausgabe verbatim ins SUMMARY), keine Nebenbemerkung — und er wird
  **vor** dem Fix gezogen, nicht danach.
- **Sperre gegen den stillen Ausfall.** Jeder Waechter, der eine Menge ableitet (Bloecke,
  Nehmer, Dateien, Call-Sites), braucht ein **Mindest-Soll** auf dieser Zahl. Faellt die
  Ableitung aus, wird er sonst **blind statt rot** und sieht dabei gruen aus. Sinkt die Zahl:
  Ursache klaeren und die Zahl **mit Begruendung** nachziehen — den Test **nie** entfernen und
  die Zahl **nie** stillschweigend senken.

**Was NICHT erlaubt ist, wenn ein Waechter anschlaegt:** die Whitelist fuellen, das Muster
aufweichen, oder den Design-Zwang aufloesen, den er schuetzt (im Anlass-Fall waere das ein
`RLock` gewesen — er haette die Fehlerklasse **unsichtbar** gemacht statt sie zu beseitigen).
Einzige zulaessige Whitelist-Kategorie bleibt der nachweisliche **Falsch**-Treffer, mit
`# FALSCH-TREFFER:`-Kommentar, `Datei:Zeile` und Begruendung.

**Muster-Umsetzung:** `tests/test_session_lock_blocking_calls_guard.py` (Abschnitte
`RESTLUECKEN` und `ZWEITE SCHICHT DARUNTER` im Modul-Docstring). Die zweite Schicht dort ist
der LOCKWATCH-Wachhund (`services/live_session.py:1518-1541`) — **er** hat den Fund geliefert,
den der statische Waechter nicht sehen konnte.

**Verhaeltnis zu anderen Punkten:** ergaenzt die Test-Qualitaets-Regel (dort: „dokumentiere den
Grund mit Kommentar im Test") um die **Grenzen**-Haelfte. Punkt 30 macht es in seiner
Waechter-Tabelle bereits vor (Spalte „Grenze") — Punkt 31 macht daraus die Pflicht fuer jeden
neuen Waechter.

**Geltungsbereich:** jeder neue oder erweiterte Waechter/Guard/statische Sweep. Skip-OK:
gewoehnliche Verhaltens-Tests (die behaupten nichts ueber eine Fehler**klasse**).

---

## ⛔ HART: Keine hardcoded Farben, keine Inline-Styles in UI-Komponenten

> **Gespiegelt 2026-08-01 aus dem Vault-Regelwerk.** Grund für die Spiegelung: Die Regel richtet sich WÖRTLICH an den Plan- und Execute-Agent — stand aber bis heute **nur** in `Nerve-Vault/CLAUDE.md`, die GSD nie lädt. Der Verstoß ist dadurch **fünfmal** passiert (08.20.2 Pflichtfeld-Karte, 08.20.3 Filter-Toggle, 08.19.5.2 nerve-nav-guard Modal, C.R, C.R.F). Jedes Mal wurde die Regel verschärft — an einer Stelle, wo der Adressat sie nicht sehen konnte. Gefunden beim Vault-Audit 01.08.
>
> André-Zitat, das die Verankerung ausgelöst hat: *„WO LIEGT DIESE VERFICKTE DESIGN DATEI VON DER DU MIR JETZT SCHON ZIG MAL GESAGT HAST DAS SIE GELÖSCHT IST?!?!?!"*

**Das aktuelle NERVE-Design ist LIGHT-MODE.** Alte Dark-Mode-Farben gehören zu einem Design-Stand, den es nicht mehr gibt.

### Schicht 1 — Keine hardcoded Farben

1. **VERBOTEN:** `style="..."`-Attribute mit hardcoded Farben. Enthält ein `style`-Attribut ein `#xxxxxx` → **SOFORT-FAIL** im Code-Review. Plan-Agent darf es nicht vorschlagen, Execute-Agent nicht bauen.
2. **VERBOTEN als Hex-Literal — tote Dark-Mode-Farben, ganz raus:** `#1a1a2e`, `#2a2a4e`, `#f0c040`, `#9a9ab0`.
   **Sonderfall `#00D4AA`:** Das ist die **Markenfarbe Teal** und bleibt gueltig — aber **nie als Hex-Literal schreiben**, immer ueber das passende Token (`var(--btn-primary-bg-from)`).
   ⚠ Bis 2026-08-03 stand `#00D4AA` faelschlich in derselben Liste wie die toten Farben. Ein Plan-Agent konnte daraus schliessen, Teal sei abgeschafft — der C.R.F-Blau-Fehler in Gegenrichtung.
3. **PFLICHT:** CSS-Variablen aus `static/nerve.css` nutzen. ⚠ **KORRIGIERT 2026-08-03 — hier stand `var(--accent)` als Beispiel. DIESES TOKEN EXISTIERT NICHT** (grep ueber `static/*.css`: 0 Treffer). Die Regel schickte Plan-Agenten auf ein Phantom-Token; in `templates/profile_editor.html:1411` wird es bereits benutzt und loest nicht auf. **Real existierende Tokens:** `var(--page-bg)`, `var(--page-text-color)`, `var(--border-color)`, `var(--btn-primary-bg-from)` (= Teal `#00D4AA`), Fallback-Muster `var(--n-accent, #00D4AA)`. **Vor der Verwendung eines Tokens: einmal in `static/nerve.css` greppen, ob es dort definiert ist.** Fehlt eines → erst dort ergaenzen, dann nutzen.
4. **PFLICHT:** UI-Komponenten als CSS-Klassen (`.n-*`) in `static/nerve.css`, nicht inline. Inline-Styles NUR für dynamische Werte (`style="width:${score}%"`).
5. **PFLICHT-Vorabrecherche bei jeder UI-Phase:** VOR der ersten UI-Codezeile `static/nerve.css` scannen — welche Variablen und Klassen existieren? Welche Modals/Cards/Pills nutzt die App schon? **Pattern aus bestehenden Komponenten kopieren, nicht neu erfinden.**

### Schicht 2 — Brand-Konsistenz (ein sauberer Token kann trotzdem falsch sein)

Verankert nach C.R.F: Ein Schieber war blau (`#3b82f6`) statt teal — formal sauber als CSS-Variable definiert, trotzdem ein Fremdkörper. André: *„warum ist der blau? wo kommt diese farbe schon wieder her? warum nicht einfach in teal…"* Weder Pre-Execute-Audit noch Cross-AI hatten es gefangen — beide prüften nur „ist es ein Token", nicht „passt der Wert zur Marke".

**Bei JEDER neuen Token-Definition:**
1. `grep` gegen die real existierenden Brand-Tokens in `static/nerve.css` — `--btn-primary-bg-from` (#00D4AA), `--btn-primary-bg-to`, Fallback-Muster `--n-accent`. *(`--accent` und `--brand-*` standen hier bis 03.08. — beide existieren nicht.)*
2. Farb-Familie prüfen: **Teal ist die Marke.** Blau = Fremdkörper. Lila = Fremdkörper. „Neutral-professionelles Blau" ist KEINE gültige Begründung.
3. Neue Funktion braucht neue Farbe? → **André fragen**, nicht eigenständig festlegen.
4. In der UI-SPEC-Phase: Token-Werte gegen die Brand-Liste kreuzprüfen VOR der Freigabe.

### Durchsetzung

- **Code-Review-Pflicht:** Jede UI-Datei (`templates/*.html`, `static/*.css`, `static/*.js`) explizit auf Inline-Styles + hardcoded Farben prüfen. Findings sind **CRITICAL**, nicht INFO — vor Phasen-Freigabe zu fixen.
- **Cross-AI-Briefing bei UI-Komponenten** muss explizit enthalten: „prüfe auf hardcoded Farben, Inline-Styles und Design-Token-Konsistenz" — nicht nur Logik-Review.
- **Bei Verstoß:** Phase nicht freigeben. André wird gefragt, ob neu gebaut wird. **Anti-Abrieb schlägt Termindruck.**

---

## ⚠ Bau-Regeln 13, 14, 20 — Vollfassungen in eigener Datei

Beim Vault-Aufräumen am 02.08. wurden drei Regeln aus `Nerve-Vault/CLAUDE.md` auf Anker-Saetze gekuerzt, mit der Begruendung "Vollfassung steht im Code-Repo". **Fable-Gegenpruefung: fuer diese drei stimmte das NICHT** — Punkt 13 war sogar ein Zirkelverweis zurueck ins Vault. Nachgetragen in **`CLAUDE-BAUREGELN-13-14-20.md`**:

- **13 — Real-Daten-Validation bei Schema-Phasen.** 5 Pflicht-Schritte vor Plan-Approval. Plan-Checker BLOCKt bei Fehlen. *Strict-Mode schuetzt nur, wenn das Schema die Realitaet abbildet — sonst ist es ein Selbstschuss.*
- **14 — Pre-Insert-Control-Flow-Audit.** 5 Pflicht-Sektionen im Plan (Lokaler Kontext / Funktions-Skelett / Cross-File-grep / Edge-Cases inkl. 4 Race-Fragen / Persistenz-Schicht). Anlass: neuer Code hinter zwei `return`-Statements = Dead Code.
- **20 — Pflicht-grep vor Migration/Insert:** Wird die Tabelle/Funktion im Production-Pfad ueberhaupt gelesen? 0 Treffer = STOPP. Zwei belegte Faelle, zusammen ~4 h Verlust.

**⚠ Nummerierungs-Falle:** Vault-Punkt 22 heisst hier Punkt 26; der hiesige Punkt 22 ist etwas anderes. Verweisen "siehe Punkt N" nie blind folgen — ueber den Regel-NAMEN suchen.

---

## ⛔ HART: Vier Vault-Regeln, die sich an DICH richten (gespiegelt 2026-08-03)

> **Warum das hier steht:** Diese vier Regeln adressieren woertlich den Plan- und Execute-Agenten,
> standen aber nur in `Nerve-Vault/CLAUDE.md` — einer Datei, die GSD nie laedt. Gefunden bei einer
> Fable-Gegenpruefung am 03.08. **Exakt dasselbe Muster wie bei der Farb-Regel, die fuenf Verstoesse
> lang am falschen Ort stand.** Vollfassungen bleiben im Vault; hier steht, was beim Bauen zaehlt.

### A) Context7 ist Pflicht bei fremden Bibliotheken
Vor Plan-/Code-Arbeit an einer dieser Abhaengigkeiten die aktuelle Doku ueber Context7 ziehen
(`use context7` + konkrete Frage), statt aus dem Modellwissen zu schreiben:
**Anthropic-SDK · Stripe · Pydantic · Deepgram · ElevenLabs · Flask-Erweiterungen · SQLAlchemy.**
**Skip bei:** Python-Bordmitteln, HTML/CSS/JS, Geschaeftslogik ohne fremde Bibliothek, Fehlern mit
klarer Ursache, rein mechanischen Aufgaben.
**Zweck:** verhindert Plan-Fehler durch veraltete Schnittstellen-Annahmen. Trainingsstand != Ist-Stand.

### B) Roadmap-Sync ist HART — beide Roadmaps in EINER Sequenz
Es gibt zwei Roadmaps: `.planning/ROADMAP.md` (hier) und `Nerve-Vault/01 Roadmap.md` (strategisch).
**Jede** Aenderung (neue Phase, Scope-Update, Komplexitaets-Hochstufung, Abschluss-Markierung) muss in
**beiden** stehen — nicht "erst hier, Vault spaeter".
**Was du konkret tust:** Nach einer ROADMAP.md-Aenderung einen Hinweis in
`.planning/DIALOG-GSD-CLAUDIAN.md` schreiben (`## ROADMAP-SYNC — <Phase> — <Datum>`, was geaendert
wurde und warum), damit Claudian die Vault-Roadmap im selben Zug nachzieht.
**Beleg:** 4 Drift-Vorfaelle. Wenn nur eine Seite gepflegt wird, laeuft der naechste
`/gsd-spec-phase`-Aufruf in den falschen Scope und produziert eine ge-driftete SPEC.md.

### C) Fix oder Neubau — pro angefasstem Modul bewusst entscheiden
**Neubau-Signale:** drei oder mehr Pflaster schon drin · gemischte Konventionen in einer Datei ·
ueber 500 Zeilen mit vermischten Zustaendigkeiten · unklarer Datenfluss · "der Fix waere das
naechste Pflaster".
**Der Plan MUSS dann eine Tabelle enthalten:** pro Datei *reparierbar* oder *zu verworren*, mit
Begruendung. Bei Neubau den alten Code als **Funktions-Referenz** lesen (welche Randfaelle loest
er?), aber **nicht als Vorlage** — sonst erbt man den Wildwuchs.
**Grenze:** gilt fuer **einzelne Module**, nie fuer die ganze App. Vor dem Start und ohne echte
Nutzer ist Modul-Neubau billig; spaeter nicht.

### D) Vier Saeulen — Pflicht-Check in JEDEM Feature-Plan
1. **Automatisieren:** Routine-Entscheidungen macht der Code, nicht Andre.
2. **Nachvollziehen:** Jede wichtige Aktion landet in einer Tabelle, nicht nur auf dem Bildschirm.
3. **Eingreifen koennen:** Fuer jede automatische Entscheidung ein Schalter — von "Andre entscheidet
   anders" bis "Code verhaelt sich anders" duerfen **30 Sekunden** vergehen.
4. **Marge:** Der Code loest ein Problem, fuer das man sonst jemanden einstellen muesste.

**Vier Fragen, die im Plan beantwortet sein muessen:** Was wird automatisiert? Wo wird es
gespeichert? Welcher Schalter erlaubt Eingriff? Welche Handarbeit spart es dauerhaft?
**Ist eine dieser Antworten "bauen wir spaeter", ist das genau das Fuenfmal-Anfassen, das wir
vermeiden wollen.**

---

## ⛔ HART: Acht weitere Vault-Regeln, die sich an DICH richten (gespiegelt 2026-08-03, zweite Runde)

> **Wie sie gefunden wurden:** Eine systematische Durchsicht der Vault-Regeldatei Regel fuer Regel
> mit der Frage "wer muss danach handeln — und steht sie dort, wo er sie liest?". Diese Richtung
> war nie geprueft worden. Ergebnis: acht Regeln verlangten eine Handlung von GSD, standen aber
> nur im Vault, den GSD nie laedt. Vollfassungen bleiben im Vault.

### 1. Regressions-Test bei JEDEM Bugfix — erst rot, dann fixen
Zu jedem Fix gehoert ein Test, der genau diesen Fehler festnagelt. **Den Test ERST gegen den
ungefixten Stand rot laufen lassen, DANN fixen** — der Rot-Lauf gehoert in Commit/SUMMARY.
Sonst entsteht ein Test, der gruen ist, aber nichts prueft.
Bei sicherheits-, datentrennungs- oder kernpfad-kritischem Verhalten: Deploy-Tor-Test statt
Einmal-Check. **Das Test-Netz ist eine Ratsche — was einmal drin ist, bleibt drin.**
*(Punkt 31 verlangt den Rot-Beleg bisher nur fuer Waechter. Diese Regel ist allgemeiner.)*

### 2. Tueroeffner gegen das spaetere Feature validieren — BEVOR er gegossen wird
Ergaenzt Punkt 24 Teil A als **Leitplanke 4** (am 22.06. beschlossen, hier nie nachgezogen).
Bei jedem Haken/Foundation-Bau — neue Erfassungs-Tabelle, durchgereichte ID, Vertrag mit einer
spaeteren Phase — **das Ziel-Feature grob skizzieren** (welche Felder, welche Verknuepfungen
braucht es?) und im Plan belegen, dass der Haken sie traegt.
**Besonders kritisch bei nur-einfuegenden Erfassungs-Haken: verpasste Felder sind fuer immer weg,
es gibt kein Nachtragen.** Pflicht-Frage im Plan: *"Habe ich das Feature, das hier dranhaengt,
weit genug skizziert, um sicher zu sein, dass dieser Haken passt?"*

### 3. Zwei unverhandelbare Daten-Schranken
1. **NERVE persistiert NIE Audio.** Audio rein, Analyse, sofort weg — auch nicht "kurz zum
   Debuggen". Das ist Produktversprechen ("NERVE zeichnet NICHTS auf") und Rechtsgrundlage der
   Single-Speaker-Architektur, kein Detail.
2. **Call-Logs sind heilig.** Transkripte, Ereignisse, Metadaten werden NIE geloescht.
   Zuruecksetzen im Browser darf **ausschliesslich** Anzeige-Zustand toeten, **niemals**
   server-seitige Anruf-Daten. Sie sind Grundlage der Nachbereitung UND Trainingsmaterial.

**Jeder Plan, der Audio-Pfade, Zuruecksetzen oder Loesch-Logik anfasst, schreibt einen
Bestaetigungs-Satz in den Plan** — woertlich: *"Geprueft: Diese Phase persistiert kein Audio und
loescht keine Call-Logs."* Fehlt der Satz bei einer solchen Phase, ist der Plan unvollstaendig.
Vollbegruendung: Vault + DSGVO-Analyse.

### 4. Fragen-Kanal — Pflicht in allen Phasen, unabhaengig vom Session-Start-Block
Jede Frage, Entscheidung und jeden Checkpoint ans **Ende** von
`.planning/DIALOG-GSD-CLAUDIAN.md` schreiben und **sofort committen**:
`## FRAGE — <Phase> — <Datum>` mit: *wo stehe ich* (Datei:Zeile/Task) · *Frage + alle Optionen +
deine Empfehlung* · *was ist blockiert*.
Dieselbe Frage **zusaetzlich als normalen Fliesstext im Terminal** — **NIE als interaktives Menue.**
**Warum:** Andre arbeitet zeitweise vom Handy und kann Terminal-Ausgabe nicht kopieren; Claudian
sieht das Terminal ueberhaupt nicht. Ohne diesen Kanal **raet** Claudian deine Fragen — belegter
Schadensfall Juli 2026. Die Antwort kommt als `### ANTWORT — Claudian` in dieselbe Datei.

### 5. Reparatur-Modus: NUR der Fehler wird angefasst
Keine Umbenennungen ausserhalb des Fehler-Pfads, kein Sortieren von Importen, kein Auslagern,
keine "wenn ich schon dabei bin"-Verbesserungen — die werden als Todo notiert, nicht committet.
**Pruefung vor dem Commit:** Aendert der Diff mehr Zeilen, als der Fehler mechanisch braucht?
Dann begruenden. **Erlaubt:** die Fehlerstelle, direkt abhaengige Stellen (mit Begruendung),
ergaenzende Tests.
**Grund:** In etwa vier von fuenf Faellen ist eine der nebenbei geaenderten Stellen subtil kaputt.
**Ebenso:** Faellt waehrend einer Phase toter oder kaputter Code auf — **nicht in die laufende
Phase mischen**, sondern direkt danach als eigene Mini-Phase.

### 6. Nach drei Fehlversuchen am selben Fehler: harter Stopp
Derselbe Fehler = gleicher Code-Pfad, gleiches Symptom. (Ein durch den vorigen Fix NEU erzeugter
Fehler zaehlt nicht mit.) Dann drei Fragen: *"Verstehe ich das Problem ueberhaupt, oder repariere
ich ein Symptom?"* · *"Welche Annahme habe ich nie geprueft?"* · *"Was wuerde ein Frischer fragen?"*
**Zweitmeinung ist PFLICHT vor Versuch vier** (Cross-AI oder Claudian ueber die DIALOG-Datei).
**Drei Fehlversuche sind ein starkes Signal, dass die ARCHITEKTUR das Problem erzeugt**, nicht
eine Code-Stelle → Fix-oder-Neubau-Pruefung (Abschnitt "Vier Vault-Regeln", C).

### 7. Pruning-Notiz — Pflichtteil JEDER Phasen-SUMMARY
Am Phasen-Ende auflisten, welche Code-Stellen durch diese Phase obsolet geworden sind. Pro Stelle
genau eine der beiden Angaben: **geloescht** ODER **bleibt als Foundation fuer Phase Y, weil ...**
(dann zusaetzlich Eintrag in `Nerve-Vault/04 Entscheidungen/Foundation-Code-Register.md`).
**Kein stehengelassenes Legacy ohne Begruendung** — das ist die Nudelcode-Wurzel.

### 8. Werkzeug-Falle: `grep -ciF` nie als Abnahme-Anker
`grep -ciF` stuerzt auf Andres Git-Bash ab und liefert **gar nichts statt einer `0`**. Ein Plan mit
diesem Muster im `<verify>`-Block schlaegt falsch-rot fehl — und erzeugt den Reflex, den Text an
den Anker anzupassen statt umgekehrt. Stattdessen `grep -c` ohne diese Flag-Kombination, oder
Treffer ueber `grep ... | wc -l` zaehlen. *(Gilt auch fuer die Pattern in
`CLAUDE-BAUREGELN-13-14-20.md`, Punkt 20.)*
