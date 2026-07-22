# Technology Stack

**Analysis Date:** 2026-05-01
**Version:** v0.9.4 (Pre-Launch, Early Access)

---

## Languages

**Primary:**
- Python 3.x — Core application backend (Flask app, services, routes, DB)

**Secondary:**
- JavaScript (Vanilla) — Frontend interactivity (`static/app.js`, inline scripts in templates)
- HTML/Jinja2 — Server-rendered templates (`templates/`)
- CSS — Custom styling (`static/nerve.css`)

**Constraint (CLAUDE.md):** No framework migration. Flask + Vanilla JS stays. No React.

---

## Runtime

**Environment:**
- Python 3.8+ (production: Hetzner VPS CX22 — 2 vCPU, 4 GB RAM, Germany/EU)

**Package Manager:**
- `pip` — dependency management
- Lockfiles: `requirements.txt` (main), `requirements-dev.txt` (PyAudio, local only), `requirements-rt.txt` (FastAPI RT Engine)

---

## Frameworks

**Core (Flask App — port 8000):**
- Flask 3.0.0+ — web framework (`app.py`)
- Flask-SocketIO 5.3.6+ — WebSocket/SocketIO for live session real-time updates (`extensions.py`, `app.py`)
- Flask-WTF 1.2.0+ — CSRF protection via `CSRFProtect`
- Flask-Limiter 3.5.0+ — rate limiting / brute-force protection (`services/rate_limiter.py`)
- Flask-Admin 2.0.2 — admin UI (`routes/admin_dashboard.py`, `routes/admin_views.py`, `routes/admin_ewb.py`)
- Werkzeug 3.0.0+ — WSGI utilities, `ProxyFix` (behind Nginx), password hashing
- Authlib 1.3.0+ — OAuth 2.0 / OIDC client (Google + Microsoft SSO, `routes/oauth.py`)

**RT Engine (FastAPI — port 8001, `nerve_rt/`):**
- FastAPI 0.135.3+ — async WebSocket engine (`nerve_rt/main.py`)
- Uvicorn + uvloop — async WSGI server for RT Engine
- Pydantic 2.0+ — data validation in RT Engine models (`nerve_rt/models/`)
- redis-py (async) 7.4.0+ — pub/sub bridge between Flask and RT Engine (`nerve_rt/redis_bridge.py`)

**Testing:**
- pytest 8.0.0+ — test runner, config in `pytest.ini` (excludes `tests/archive/`)

**Build/Serve (Production):**
- Gunicorn (gthread worker) — Flask production WSGI server, 1 worker + 4 threads, port 8000
- Uvicorn + uvloop — RT Engine production server, port 8001
- Nginx — reverse proxy, SSL termination, routes `/ws/` to port 8001 (`deploy/nginx.conf`)
- Let's Encrypt / certbot — TLS certificates for `getnerve.app`
- systemd — service management (`deploy/nerve.service`, `deploy/nerve-rt.service`)

---

## Key Dependencies

**AI / ML:**
- `anthropic` 0.40.0+ — Claude API client (`services/claude_service.py`). Two model tiers:
  - **Haiku** (`claude-haiku-4-5-20251001`) — all live/latency-critical paths:
    - `MODEL_ANALYSE` (live analyse_loop — LOCKED, never Sonnet per CLAUDE.md)
    - `MODEL_TRAINING_DIALOG`, `MODEL_PHASE_CLASSIFY`, `MODEL_COLDCALL_INFER`
    - `MODEL_COACHING`, `MODEL_VALIDATE_USER_TEXT`, `MODEL_TRAINING_PREVIEW`
    - `MODEL_PERSONALITY_GEN`
  - **Sonnet 4.5** (`claude-sonnet-4-5`) — all quality-critical/post-call paths:
    - `MODEL_EWB`, `MODEL_QA`, `MODEL_PIP_AUTOVAR`, `MODEL_PIP_VARIANTE`
    - `MODEL_POSTCALL_INSIGHTS`, `MODEL_POSTCALL_ANALYSIS`, `MODEL_WEEKLY_SUMMARY`
    - `MODEL_PRECALL`, `MODEL_CRM`, `MODEL_TRAINING_HELP`, `MODEL_TRAINING_SCORING`
  - All model constants are ENV-overridable (defined `config.py` lines 49–72)
  - Circuit-breaker for EWB TTFT: falls back Sonnet→Haiku if 3/5 calls exceed threshold (`services/claude_service.py`)
  - Prompt caching: `CACHE_ANTWORT=true` (single switch, stable answer prefix; analyse loop uncached)
- `sentence-transformers` 2.7.0+ — semantic embedding for objection matching

**Speech (STT):**
- `deepgram-sdk` 3.7.0+ — real-time speech-to-text (`services/deepgram_service.py`)
  - EU endpoint default: `api.eu.deepgram.com` (DSGVO requirement, `config.py` line 9)
  - Speaker diarization enabled
  - Per-session WebSocket connections managed in `_deepgram_sessions` dict

**Speech (TTS):**
- ElevenLabs — accessed via raw `requests` HTTP (no official SDK)
  - `ELEVENLABS_API_KEY` in `config.py`
  - Voice pool: 4 male + 4 female voices with hardcoded IDs (`services/training_service.py` lines 13–24)
  - Used only in Training mode (not live calls)

**Payments:**
- `stripe` 11.0.0+ — subscriptions, Checkout Sessions, webhook processing (`routes/payments.py`)

**Database ORM:**
- `sqlalchemy` 2.0.0+ — declarative ORM, `SessionLocal` pattern (`database/db.py`, `database/models.py`)

**Email:**
- `resend` 2.27.0 — transactional email via Resend API (`services/email_service.py`)

**Search:**
- Brave Search API — company research for PreCall briefing, via `requests` (`services/precall_service.py`)

**Auth / Security:**
- `itsdangerous` 2.0+ — URL-safe token signing for email verification / password reset
- `markdown` 3.5+ — renders AI-generated PreCall briefing text
- `bleach` 6.1.0+ — XSS sanitization for markdown output (LB-01)

**Infra:**
- `python-dotenv` 1.0.0+ — `.env` file loading

**Dev-only (never installed on VPS):**
- `pyaudio` 0.2.14+ — local microphone capture (`requirements-dev.txt`)

---

## Configuration

**Loading:** `python-dotenv` reads `.env` at startup in `config.py` and `nerve_rt/config.py`.

**Secrets location (production):** `/etc/nerve/.env` (never in repo)

**Key env vars:**

| Var | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask session encryption — **app refuses to start in prod if default** | `dev-secret-change-me` |
| `DEEPGRAM_API_KEY` | STT transcription | — |
| `DEEPGRAM_HOST` | Deepgram endpoint | `api.eu.deepgram.com` |
| `ANTHROPIC_API_KEY` | Claude API | — |
| `ELEVENLABS_API_KEY` | TTS synthesis | — |
| `STRIPE_SECRET_KEY` | Payments | — |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation | — |
| `STRIPE_PRICE_ID_STARTER/PRO/BUSINESS` | Stripe price IDs | — |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth SSO | — |
| `MICROSOFT_CLIENT_ID/SECRET` | Microsoft OAuth SSO | — |
| `BRAVE_SEARCH_API_KEY` | PreCall company research | — |
| `RESEND_API_KEY` | Transactional email | — |
| `DATABASE_URL` | DB connection string | `sqlite:///database/nerve.db` |
| `REDIS_URL` | RT Engine Redis bridge | `redis://127.0.0.1:6379` |
| `CORS_ORIGIN` | CORS allowed origins | `https://getnerve.app` in prod, `*` in debug |
| `FLASK_DEBUG` | Debug mode flag | unset (prod) |
| `CLASSIFIER_CONFIDENCE_THRESHOLD` | Objection classifier minimum confidence | `0.80` |
| `PERSONALIZED_SCRIPTS_CAP` | Max personalized scripts per profile | `20` |
| `MODEL_*` | All Claude model overrides | see `config.py` lines 49–72 |
| `CACHE_ANTWORT` | Answer-prompt caching toggle (stable prefix) | `true` |

**Audio constants (hardcoded in `config.py`):**
- `SAMPLE_RATE = 16000` Hz
- `CHUNK_SIZE = 1024`
- `ANALYSE_INTERVALL = 4` seconds
- `MERGE_WINDOW_S = 0.3`, `SPEAKER_DEBOUNCE_S = 3.0`

**CSS cache bust:** `app.config['CSS_VERSION'] = '20260421-1'` (update manually per deploy)

**Build/config files:**
- `config.py` — Flask app configuration
- `nerve_rt/config.py` — RT Engine configuration
- `pytest.ini` — test runner (excludes `tests/archive/`)
- `deploy/nginx.conf` — Nginx config (`getnerve.app`)
- `deploy/nerve.service` — Flask/gunicorn systemd unit
- `deploy/nerve-rt.service` — FastAPI/uvicorn systemd unit

---

## Platform Requirements

**Development:**
- Python 3.8+
- Install: `pip install -r requirements.txt -r requirements-dev.txt`
- PyAudio requires system PortAudio libraries
- Redis server running locally (for RT Engine)
- `.env` file with all API keys

**Production:**
- Hetzner VPS CX22 (2 vCPU, 4 GB RAM, Germany — EU data residency for DSGVO)
- Nginx + certbot/Let's Encrypt
- Redis server (`sudo apt install redis-server`)
- Python venv at `/opt/nerve/venv`
- App deployed to `/opt/nerve/app`
- Secrets at `/etc/nerve/.env`
- Two systemd services running: `nerve` (Flask) + `nerve-rt` (FastAPI)

---

## Run Commands

**Development (Flask):**
```bash
python app.py
# Dev server on http://localhost:5000
```

**Development (RT Engine):**
```bash
uvicorn nerve_rt.main:app --host 127.0.0.1 --port 8001 --reload
```

**Production (managed by systemd — do not run manually):**
```bash
# Flask/gunicorn
gunicorn --worker-class gthread --workers 1 --threads 4 \
  --bind 127.0.0.1:8000 --timeout 120 app:app

# RT Engine/uvicorn
uvicorn nerve_rt.main:app --host 127.0.0.1 --port 8001 --workers 1 --loop uvloop
```

**Deploy to VPS:**
```bash
./deploy.sh            # Full deploy via tar-over-SSH
./deploy.sh --dry-run  # Preview what would be transferred (never transfers prod .db)
```

**Tests:**
```bash
pytest                 # All tests (excludes tests/archive/)
```

---

*Stack analysis: 2026-05-01*
