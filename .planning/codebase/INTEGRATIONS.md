# External Integrations

**Analysis Date:** 2026-04-24

## APIs & External Services

**AI & Speech Processing:**
- Anthropic Claude API - Real-time objection detection and coaching
  - SDK/Client: `anthropic` 0.40.0+
  - Used in: `services/claude_service.py`, `services/training_service.py`, `nerve_rt/services/llm/claude_adapter.py`
  - Auth: `ANTHROPIC_API_KEY` (env var)
  - Purpose: Live call analysis, counter-argument generation, post-call summaries, training scenarios

- Deepgram API - Speech-to-text transcription with speaker diarization
  - SDK/Client: `deepgram-sdk` 3.7.0+
  - Used in: `services/deepgram_service.py`, `nerve_rt/services/stt/deepgram_adapter.py`
  - Auth: `DEEPGRAM_API_KEY` (env var)
  - Host: `api.eu.deepgram.com` (DSGVO-compliant EU endpoint, POLISH-49)
  - Purpose: Real-time live call transcription, speaker identification

- ElevenLabs Text-to-Speech - Voice synthesis for training scenarios
  - SDK/Client: HTTP API via `requests` library
  - Used in: `services/training_service.py`, `tests/tts_comparison.py`
  - Auth: `ELEVENLABS_API_KEY` (env var)
  - Endpoint: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
  - Purpose: Training mode voice generation, emotional tone variety

**Search & Intelligence:**
- Brave Search API - PreCall research and company intelligence
  - SDK/Client: HTTP API via `requests` library
  - Used in: `services/precall_service.py`
  - Auth: `BRAVE_SEARCH_API_KEY` (env var, header `X-Subscription-Token`)
  - Endpoint: `https://api.search.brave.com/res/v1/web/search`
  - Purpose: Company research for PreCall briefing (Phase 04.13), objection context gathering

**Semantic Matching:**
- Sentence Transformers - Semantic similarity for training scenarios
  - SDK/Client: `sentence-transformers` 2.7.0+
  - Used in: `services/qa_pipeline.py` (conditional, lazy-loaded)
  - Auth: None (local embeddings)
  - Purpose: Vector-based matching of objections to training scenarios (Phase 08.5)

## Data Storage

**Databases:**
- SQLite (default)
  - Connection: `sqlite:///database/nerve.db`
  - Client: SQLAlchemy ORM 2.0+
  - Features: WAL mode enabled for concurrent read/write access
  - Usage: User accounts, organizations, profiles, conversation logs, audit trails

- PostgreSQL (alternative)
  - Connection: Via `DATABASE_URL` environment variable
  - Client: SQLAlchemy ORM 2.0+
  - Usage: Production deployments requiring scalability

**File Storage:**
- Local filesystem only
  - Log files: `logs/` directory
  - Conversation logs: `logs/` directory (timestamped JSON files)
  - Screenshots/feedback: `logs/feedback/` directory
  - No cloud storage integration

**Caching:**
- Redis (via nerve_rt integration, future-ready)
  - Used in: `nerve_rt/redis_bridge.py` (message broker for async processing)
  - Purpose: Real-time message queueing between FastAPI async services
  - Not required for core Flask app operation

## Authentication & Identity

**Auth Provider:**
- Session-based authentication (Flask session middleware)
  - Implementation: Email + password with bcrypt hashing (Werkzeug)
  - Session storage: Server-side via Flask session
  - Token: DbSession model for API authentication (future use)

- OAuth 2.0 / OIDC (Phase 04.6.1)
  - Implementation: Authlib library
  - Providers: Google and Microsoft
  - Google config:
    - Client ID: `GOOGLE_CLIENT_ID` (env var)
    - Client Secret: `GOOGLE_CLIENT_SECRET` (env var)
    - Endpoint: `https://accounts.google.com/.well-known/openid-configuration`
    - Scope: `openid email profile`
  - Microsoft config:
    - Client ID: `MICROSOFT_CLIENT_ID` (env var)
    - Client Secret: `MICROSOFT_CLIENT_SECRET` (env var)
    - Endpoint: `https://login.microsoftonline.com/organizations/v2.0/.well-known/openid-configuration`
    - Scope: `openid email profile`
    - Note: Uses `/organizations/` endpoint (Work/School accounts only, no personal)

**Password Management:**
- Reset tokens: ITSdangerous URLSafeTimedSerializer
  - Used in: `services/email_service.py`
  - Salt: `nerve-pwreset`
  - Token TTL: 3600 seconds (1 hour)

## Monitoring & Observability

**Error Tracking:**
- Not detected (no Sentry/Rollbar integration)

**Logs:**
- Approach: Print statements to stdout with context tags
  - Tags used: `[DG]` (Deepgram), `[AI]` (Claude), `[DB]` (Database), `[EMAIL]`, `[API]`, `[FairUse]`, `[OAuth]`, `[Stripe]`
  - Stored: Local log files in `logs/` directory
  - Conversation logs: Per-session JSON files with transcripts, timestamps, speaker labels
  - Suppressed routes: `/api/ergebnis` and `/api/status` (polling endpoints) filtered via `_SuppressPolling` logging filter

## CI/CD & Deployment

**Hosting:**
- Hetzner VPS (current), Germany-based for DSGVO compliance

**CI Pipeline:**
- Not detected (no GitHub Actions, GitLab CI, or similar)
- Manual deployment via `deploy.sh` script
- Pre-deployment checks: SSL certs, environment variables

## Environment Configuration

**Required Environment Variables (Security-Critical):**
- `DEEPGRAM_API_KEY` - STT service credentials
- `ANTHROPIC_API_KEY` - Claude API key (highest privilege)
- `STRIPE_SECRET_KEY` - Stripe live key (PCI-DSS)
- `STRIPE_WEBHOOK_SECRET` - Webhook HMAC secret
- `GOOGLE_CLIENT_SECRET` - OAuth provider secret
- `MICROSOFT_CLIENT_SECRET` - OAuth provider secret
- `RESEND_API_KEY` - Email service key
- `BRAVE_SEARCH_API_KEY` - Search API key
- `ELEVENLABS_API_KEY` - TTS service key
- `SECRET_KEY` - Flask session encryption (must be cryptographically random for production)

**Secrets Location:**
- `.env` file (local development, NOT committed)
- Environment variables set directly in production environment (Hetzner vServer)
- `.env.example` provides template documentation of all required variables
- No secrets stored in git, code, or config files

## Webhooks & Callbacks

**Incoming:**
- Stripe webhook endpoint: `POST /payments/webhook`
  - Listens for: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.created`, `invoice.finalized`, `invoice.payment_succeeded`
  - Signature verification: HMAC with `STRIPE_WEBHOOK_SECRET`
  - Idempotency: Tracked via `BillingEvent` model to prevent duplicate processing

**Outgoing:**
- Email callbacks: None (Resend is fire-and-forget)
- No outbound webhooks to external services detected

## Real-Time Communication

**WebSocket (Socket.IO):**
- Client ↔ Server communication for live session updates
  - Namespace: Default (no explicit namespace routing)
  - Events emitted by server:
    - `transcript` - Final transcription with speaker label
    - `coaching` - Live coaching tips and recommendations
    - `status` - Session state updates
  - Events received from client: Control events (pause, resume, end session)
  - CORS configured via `CORS_ORIGIN` environment variable
  - Async mode: `threading` (synchronous, not truly async)

## Fair-Use & Cost Tracking

**Usage Tracking:**
- Live minutes: Tracked at user and organization level (monthly reset)
  - Stored in: `User.minuten_used`, `Organisation.live_minutes_used`
  - Limit enforcement: Fair-use soft-limit (POLISH-17)

- Training sessions: Tracked separately
  - Stored in: `User.trainings_voice_used`, `Organisation.training_sessions_used`
  - Limit enforcement: Monthly quota per plan

**Cost Tracking:**
- Service: `services/cost_tracker.py`
- Provider costs tracked: Anthropic (Claude), Deepgram, ElevenLabs
  - Model: Per-token/per-minute pricing
  - Stored in: Database via cost tracking models
- Exchange rates: `services/eur_calculator.py` tracks USD → EUR conversion
- Used for: Profitability calculation, fair-use enforcement

## Model Specifics

**Claude Models Used:**
- Haiku (live analysis) - `services/claude_service.py`, real-time low-cost
- Sonnet (post-call) - Post-call detailed analysis
- Selected per-phase via prompt pipeline (`services/prompt_pipeline.py`)

**Deepgram Models:**
- Model: Not explicitly specified in code (uses default)
- Language: German (de)
- Features: Multi-speaker diarization (speaker 0 = sales rep, speaker 1 = customer)

---

*Integration audit: 2026-04-24*
