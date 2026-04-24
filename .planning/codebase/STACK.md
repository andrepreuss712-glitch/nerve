# Technology Stack

**Analysis Date:** 2026-04-24

## Languages

**Primary:**
- Python 3.x - Core application backend and all business logic

## Runtime

**Environment:**
- Python 3.8+ (Flask-based runtime)

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- Flask 3.0.0+ - Web framework for HTTP routing and template rendering
- Flask-SocketIO 5.3.6+ - Real-time WebSocket support for live session communication
- Werkzeug 3.0.0+ - WSGI utilities for Flask, including ProxyFix for nginx reverse proxy

**Admin Interface:**
- Flask-Admin 2.0.2 - Admin panel for user/organization/conversation management

**Testing:**
- pytest 8.0.0+ - Unit and integration test framework

**Build/Dev:**
- python-dotenv 1.0.0+ - Environment variable loading from `.env`

## Key Dependencies

**Critical:**
- `anthropic` 0.40.0+ - Claude API integration for real-time objection detection, coaching, and post-call analysis
  - Used in: `services/claude_service.py`, `services/training_service.py`, `nerve_rt/services/llm/claude_adapter.py`
  - Purpose: Core AI backbone for live conversation analysis and counter-argument generation

- `deepgram-sdk` 3.7.0+ - Real-time speech-to-text transcription service
  - Used in: `services/deepgram_service.py`, `nerve_rt/services/stt/deepgram_adapter.py`
  - Purpose: Live audio-to-text conversion during sales calls with speaker diarization

- `sqlalchemy` 2.0.0+ - ORM for database models and queries
  - Used in: `database/db.py`, `database/models.py`, all route handlers
  - Purpose: Data persistence layer for users, organizations, profiles, conversation logs

- `stripe` 11.0.0+ - Payment processing SDK
  - Used in: `routes/payments.py`
  - Purpose: Subscription management, checkout sessions, webhook handling for billing

- `authlib` 1.3.0+ - OAuth 2.0 / OIDC authentication
  - Used in: `routes/oauth.py`
  - Purpose: Google and Microsoft OAuth integration for single sign-on (Phase 04.6.1)

- `resend` 2.27.0+ - Transactional email service
  - Used in: `services/email_service.py`
  - Purpose: Welcome emails, password reset, feedback acknowledgments

**Infrastructure:**
- `requests` 2.31.0+ - HTTP client library
  - Used in: `services/training_service.py`, `services/precall_service.py`, test files
  - Purpose: API calls to external services (ElevenLabs, Brave Search) and general HTTP requests

- `markdown` 3.5+ - Markdown parsing
  - Used in: `app.py` (Jinja2 filter for template rendering)
  - Purpose: Render AI-generated PreCall briefing markdown as HTML (Phase 08.1)

- `bleach` 6.1.0+ - HTML sanitization
  - Used in: `app.py` (markdown filter)
  - Purpose: XSS protection on user-generated content in PreCall briefing (LB-01)

- `sentence-transformers` 2.7.0+ - Semantic similarity matching
  - Used in: `services/qa_pipeline.py`
  - Purpose: Vector-based matching of training scenarios to detected objections (Phase 08.5)
  - Note: Only imported within conditional blocks; not loaded on every startup

## Configuration

**Environment Variables (via `.env`):**
All configuration is loaded by `python-dotenv` from `.env` file at startup. See `config.py` for complete list.

**Required for production:**
- `DEEPGRAM_API_KEY` - Deepgram STT credentials
- `ANTHROPIC_API_KEY` - Claude API key
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `STRIPE_PRICE_ID_STARTER`, `_PRO`, `_BUSINESS` - Stripe price IDs for tiers
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Google OAuth credentials
- `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` - Microsoft OAuth credentials
- `RESEND_API_KEY` - Resend email service API key
- `BRAVE_SEARCH_API_KEY` - Brave Search API for PreCall Intelligence (Phase 04.13)
- `ELEVENLABS_API_KEY` - ElevenLabs TTS voice synthesis (training mode)
- `DATABASE_URL` - SQLAlchemy database connection string (default: `sqlite:///database/nerve.db`)
- `SECRET_KEY` - Flask session encryption key (must be cryptographically secure in production)
- `CORS_ORIGIN` - Allowed CORS origins for WebSocket (default: `*` in debug, `https://nerve.app` in production)

**Audio Processing:**
- `SAMPLE_RATE` - 16000 Hz (configured in `config.py`)
- `CHUNK_SIZE` - 1024 bytes per audio chunk
- `ANALYSE_INTERVALL` - 4 seconds between analysis loop runs (Phase 06.3)
- `MERGE_WINDOW_S` - 0.3 seconds window for transcript merging
- `SPEAKER_DEBOUNCE_S` - 3.0 seconds debounce for speaker detection

**Business Logic:**
- `MAX_SESSION_HOURS` - Maximum session duration before timeout (default: 8 hours)
- `CLASSIFIER_CONFIDENCE_THRESHOLD` - Minimum confidence for objection classification (default: 0.80, Phase 08.5)

**Build Time:**
- `.env.example` - Template file documenting all required environment variables

## Platform Requirements

**Development:**
- Python 3.8+
- System audio support (microphone input via pyaudio)
- SQLite database (default) or PostgreSQL connection string

**Production:**
- Python 3.8+ runtime
- Database: SQLite or PostgreSQL (via `DATABASE_URL`)
- Port 5000+ accessible (configurable via Flask)
- HTTPS reverse proxy (nginx) recommended for production deployment
- Email service: Resend API account with credentials
- Payment processing: Stripe account with API keys
- AI services: Anthropic, Deepgram, ElevenLabs, Brave Search API accounts

**Deployment:**
- Hetzner VPS (current hosting, Germany for DSGVO compliance)
- WSGI server: Gunicorn or similar
- Reverse proxy: nginx for SSL/TLS, ProxyFix headers

## Database

**Default:**
- SQLite with WAL (write-ahead logging) mode enabled for concurrent reads/writes under threading

**Alternative:**
- PostgreSQL (any version compatible with SQLAlchemy 2.0)
- Connection pooling configured via SQLAlchemy engine

---

*Stack analysis: 2026-04-24*
