<!-- GSD:project-start source:PROJECT.md -->
## Project

**NERVE**

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler im DACH-Markt. Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit und liefert Gegenargumente sowie Coaching-Tipps direkt auf den Bildschirm — unsichtbar für den Kunden. Ergänzend bietet NERVE einen KI-Trainingsmodus, eine Coach-Plattform für Teams und automatisierte Post-Call-Analysen.

**Status:** v0.9.4, Pre-Launch — Early Access vorbereitet
**Founder:** Solo-Founder (Einzelunternehmer)

**Core Value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

### Skill-Routing

- **Spike findings for salesnerve** (implementation patterns, constraints, gotchas) → `Skill("spike-findings-salesnerve")`

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
> **Source-of-Truth für Mechanik (Trigger-Logik, Hit-Rate-Pattern, Fairness-Regel):** `Nerve-Vault/CLAUDE.md` Punkt 7+8.

### Komplexitäts-Marker

Jede Phase ist mit einem Marker klassifiziert (in PLAN.md / SPEC.md sichtbar):
- 🟢 **trivial** — mechanisch, GSD-Auto-Tempo (Renaming, CSS, String-Updates, mechanische Prunes, Bugfixes mit klarem Root-Cause)
- 🟡 **mittel** — mehrere Entscheidungen, Multi-File-Edits, kein Architektur-Risiko (Refactors, neue Endpoints, Schema-Anpassungen)
- 🔴 **komplex** — Architektur/Security/DSGVO/Schema/Multi-Pipeline. Cross-AI Pflicht.

### Pflicht-Workflows

| Trigger | Pflicht-Schritt | Kommando | Wann |
|---|---|---|---|
| 🔴 Plan fertig | Cross-AI-Plan-Review **vor** Execute | `/gsd-review --phase X --all` | IMMER bei 🔴, Default-ON bei 🟡 mit substantiellem Code-Removal (>500 Zeilen) ODER >5 Files ODER FE+BE gleichzeitig ODER Migrations-Logik |
| Cross-AI-Findings da | Replan mit Findings | `/gsd-plan-phase X --reviews` | Wenn Cross-AI ≥1 substantielles Finding (HIGH actionable) liefert |
| Schema-Phase Plan | Real-Daten-Validation Pflicht | Plan muss Real-Daten-Sample gegen neues Schema testen | Bei Phasen die ein Pydantic/SQLAlchemy/etc.-Schema ändern (Vault-CLAUDE.md Punkt 13) |
| `url_for(...)`-Strings | Endpoint-Verifikation | `grep "def " routes/X.py` + Live-Test-Request-Context | Bei jedem Plan/Edit mit `url_for('blueprint.function')` (Vault-CLAUDE.md Punkt 9) |
| Feature-Reaktivierung | Migration-Vollständigkeit prüfen | "Brauchen bestehende Records eine UPDATE-Migration?" | Wenn Plan einen `if` reaktiviert/auskommentiert/aktiviert (Vault-CLAUDE.md Punkt 10) |
| Execute fertig | Code-Review | `/gsd-code-review` → `/gsd-code-review-fix` | Pflicht bei 🔴, empfohlen bei 🟡 |
| 🔴 Schema-Bump | LATEST_SCHEMA_VERSION-Konstante prüfen | `services/profile_schema.py` + `app.py`-Skip-Check | Bei jedem Plan der Schema-Version-Bump auslöst (Block-J-Lesson 08.20-Plan-01) |

### Skip-Regel (für Plan-Agent)

- 🟢 trivial: Cross-AI-Review SKIP (Overkill, frisst Momentum)
- 🟡 mittel ohne Trigger oben: Cross-AI-Review optional (Andre entscheidet pro Phase)
- 🟡 mittel mit Trigger ODER 🔴 komplex: Cross-AI-Review **PFLICHT vor Execute**

### Was Plan-Agent NICHT tun soll

- Direkt zu `/gsd-execute-phase` springen wenn Phase 🔴 ist
- Cross-AI-Pflicht als optional darstellen wenn 🔴
- "Next Up — Execute" empfehlen ohne vorherigen Review-Schritt bei 🔴

### Was Plan-Agent statt dessen empfehlen soll

Bei 🔴-Phase als "Next Up":
```
▶ Next Up — Cross-AI Peer Review (PFLICHT bei 🔴)

/clear
/gsd-review --phase X --all
```

Erst NACH Review-Findings + Replan kommt Execute als Next Up.

### Cross-AI-Entscheidung im Log dokumentieren

Pro Phase wird in `Nerve-Vault/05 Log.md` festgehalten:
- Cross-AI gemacht: warum (🔴 / 🟡-Trigger) + Hit-Rate (Anzahl actionable Findings)
- Cross-AI geskippt: warum (🟢 / 🟡 ohne Trigger) — kurze Begründung

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

Plan-Author + Executor müssen Pytest-Acceptance-Checks auf Staging laufen lassen, nicht lokal. Macht jede Plan-Acceptance 30-60s langsamer (SSH-Roundtrip), aber stellt sicher dass Tests-Grün auf Staging tatsächlich Aussagekraft hat.

**Workflow pro Plan-Task:**

1. Code-Edit (lokal in IDE — nur Editieren, kein Ausführen)
2. `git commit`
3. `git push`
4. `bash deploy.sh staging` (oder GSD-Executor-Wrapper)
5. Pytest auf Staging via SSH: `ssh deploy@<staging-ip> 'cd /opt/nerve && source venv/bin/activate && pytest tests/test_X.py -x -v'`
6. Live-Test im Browser via `https://staging.getnerve.app`
7. Wenn grün: `bash deploy.sh production`

### Konsequenz für Plan-Author

Plan-Files müssen `<verify>`-Sektionen so formulieren dass Pytest **auf Staging-Server** läuft, nicht in lokalem Working-Directory. Plan-Acceptance-Criteria müssen Staging-Befehle enthalten (SSH-basiert).

Pattern für Plan-Author:

```xml
<verify>
  <automated>bash deploy.sh staging && ssh deploy@staging.getnerve.app 'cd /opt/nerve && source venv/bin/activate && pytest tests/test_X.py -x'</automated>
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
ssh -i ~/.ssh/id_ed25519_nerve root@staging.getnerve.app \
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
  - ssh deploy@staging 'cd /opt/nerve/app && bash scripts/inspect.sh schema calls' (Live-Schema-Stand)
  - ssh deploy@staging 'cd /opt/nerve/app && bash scripts/inspect.sh constraints calls' (CHECK-Constraints)
  - ssh deploy@staging 'cd /opt/nerve/app && bash scripts/inspect.sh sample calls 100' (Real-Daten-Sample)
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
- **Punkt 15 (Logging-First-Debugging):** Logs via `inspect.sh logs` / `logs-errors`, nicht lokal. Neue Diagnose-Prints werden committed → `deploy.sh staging` → dann via `inspect.sh logs` gelesen.
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
- Cross-AI-Entscheidung + -Funde pro Brocken in `Nerve-Vault/05 Log` dokumentieren.

**Geltungsbereich:** Pflicht-Prozess bei jedem großen Roadmap-Brocken (Plan→Interlock→Execute). Skip-OK nur für 🟢-triviale Einzelaufgaben.
