# External Integrations

**Analysis Date:** 2026-05-01
**Version:** v0.9.4

---

## AI — Anthropic Claude

**Purpose:** All AI analysis, coaching, and generation throughout the app.

**SDK:** `anthropic` 0.40.0+ (`services/claude_service.py`)
**Auth:** `ANTHROPIC_API_KEY` env var
**Client:** `claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)` (module-level singleton)

**Model routing (two tiers — all overridable via ENV):**

| Constant | Model | Use Case |
|----------|-------|----------|
| `MODEL_ANALYSE` | `claude-haiku-4-5-20251001` | Live analyse_loop — **LOCKED, never Sonnet** |
| `MODEL_TRAINING_DIALOG` | Haiku | Training conversation dialog |
| `MODEL_PHASE_CLASSIFY` | Haiku | Call phase classification |
| `MODEL_COLDCALL_INFER` | Haiku | Cold-call inference |
| `MODEL_COACHING` | Haiku | Live coaching tips |
| `MODEL_VALIDATE_USER_TEXT` | Haiku | User input validation |
| `MODEL_TRAINING_PREVIEW` | Haiku | Training scenario preview |
| `MODEL_PERSONALITY_GEN` | Haiku | Personality generation |
| `MODEL_EWB` | `claude-sonnet-4-5` | Einwand-Gegenargument (EWB) streaming |
| `MODEL_QA` | Sonnet | QA pipeline responses |
| `MODEL_PIP_AUTOVAR` | Sonnet | EWB auto-variant (with circuit-breaker fallback to Haiku) |
| `MODEL_POSTCALL_INSIGHTS` | Sonnet | Post-call insight generation |
| `MODEL_POSTCALL_ANALYSIS` | Sonnet | Post-call full analysis |
| `MODEL_WEEKLY_SUMMARY` | Sonnet | Weekly performance summary |
| `MODEL_PRECALL` | Sonnet | PreCall intelligence briefing |
| `MODEL_CRM` | Sonnet | CRM note + follow-up email generation (`services/crm_service.py`) |
| `MODEL_TRAINING_HELP` | Sonnet | Training coaching hints |
| `MODEL_TRAINING_SCORING` | Sonnet | Training session scoring |

**Prompt caching (Anthropic cache_control):**
- `CACHE_ANTWORT = true` — the shared answer system prompt (Auto/EWB, button, QA) is cached on its stable block; ENV-overridable, rollback without deploy
- Marker sits in `services/prompt_pipeline.py` (`answer_system_content`), on the `_layer='stable'` block only — never on the volatile block
- Analyse loop deliberately uncached (prompt below the model's minimum cacheable prefix of 4.096 TOKENS)

**EWB circuit-breaker (Phase 08.20, `services/claude_service.py`):**
- Tracks TTFT for last 5 EWB streaming calls
- If 3/5 exceed threshold: falls back `MODEL_PIP_AUTOVAR` Sonnet→Haiku for 30 seconds
- Rollback without deploy: set `MODEL_PIP_AUTOVAR=claude-haiku-4-5-20251001` in env

**Key service files:**
- `services/claude_service.py` — main Claude client, analyse_loop, EWB circuit-breaker
- `services/ewb_pipeline.py` — EWB prompt building
- `services/qa_pipeline.py` — QA pipeline
- `services/prompt_pipeline.py` — prompt version resolution (A/B routing)
- `services/precall_service.py` — PreCall briefing generation
- `services/crm_service.py` — CRM note + follow-up email
- `services/training_service.py` — training dialog AI
- `services/coaching_service.py` — live coaching recommendations

---

## Speech-to-Text — Deepgram

**Purpose:** Real-time speech transcription during live sales calls.

**SDK:** `deepgram-sdk` 3.7.0+ (`services/deepgram_service.py`)
**Auth:** `DEEPGRAM_API_KEY` env var
**Endpoint:** `DEEPGRAM_HOST` — default `api.eu.deepgram.com` (DSGVO: EU data residency mandatory)

**Features used:**
- Live WebSocket transcription (`LiveTranscriptionEvents`)
- Speaker diarization (speaker 0 = salesperson, speaker 1 = customer)
- `is_final` flag for stable transcripts
- `LiveOptions` with `SAMPLE_RATE = 16000` Hz

**Session management:**
- Per-session WebSocket connections: `_deepgram_sessions = {}` keyed by Socket.IO `sid`
- STT seconds tracked per session: `_stt_seconds_accumulated` (for fair-use billing)
- Thread-safe via `_sessions_lock`

**Key service file:** `services/deepgram_service.py`

---

## Text-to-Speech — ElevenLabs

**Purpose:** Voice synthesis for AI training partner (training mode only — not used in live calls).

**SDK:** None — raw HTTP via `requests` library
**Auth:** `ELEVENLABS_API_KEY` env var
**API:** Standard ElevenLabs REST API (text-to-speech endpoint)

**Voice pools (hardcoded IDs in `services/training_service.py` lines 13–24):**
- Male: Brian (`nPczCjzI2devNBz1zQrb`), Daniel, Callum, Antoni
- Female: Bella (`EXAVITQu4vr4xnSDxMaL`), Rachel, Domi, Emily

**Voice settings per scenario type:**
- Per-character `voice_settings` (stability, similarity_boost, style) defined in `SEKRETAERIN_TYPES` dict

**Usage limit:** `training_voice_limit` per org/month (default 50), tracked in `Organisation.trainings_voice_used`

**Key service file:** `services/training_service.py`

---

## Payments — Stripe

**Purpose:** Subscription billing for Starter/Pro/Business plans (flat-rate, EUR).

**SDK:** `stripe` 11.0.0+ (`routes/payments.py`)
**Auth:** `STRIPE_SECRET_KEY` env var
**Webhook secret:** `STRIPE_WEBHOOK_SECRET` env var

**Plans and price IDs:**
- Starter (49€/mo): `STRIPE_PRICE_ID_STARTER`
- Pro (59€/mo): `STRIPE_PRICE_ID_PRO`
- Business (69€/mo): `STRIPE_PRICE_ID_BUSINESS`

**Stripe features used:**
- `stripe.checkout.Session` — hosted payment page
- `stripe.Customer` — customer creation/reuse (stored as `Organisation.stripe_customer_id`)
- `stripe.billing_portal.Session` — self-service subscription management
- `stripe.Webhook.construct_event` — signature-verified webhook processing
- `automatic_tax={'enabled': True}` — Stripe Tax (requires active Tax Registration)

**Webhook endpoint:** `POST /payments/webhook`

**Webhook events handled:**
- `checkout.session.completed` → activate subscription (`_activate_subscription`)
- `customer.subscription.updated` → sync status (`_sync_subscription`)
- `customer.subscription.deleted` → cancel subscription (`_cancel_subscription`)
- `invoice.paid` → reset monthly fair-use counters (`_reset_fair_use_on_invoice`)
- `invoice.payment_succeeded` → record revenue (`_record_revenue`)
- `invoice.payment_failed` → handle failed payment (`_handle_payment_failed`)

**Idempotency:** Stripe event IDs stored in `BillingEvent.stripe_event_id` with unique index — duplicate webhook events are detected and skipped.

**Key route file:** `routes/payments.py`

---

## Email — Resend

**Purpose:** Transactional email (welcome, email verification, password reset, notifications).

**SDK:** `resend` 2.27.0 (`services/email_service.py`)
**Auth:** `RESEND_API_KEY` env var
**From addresses:**
- `NERVE <noreply@getnerve.app>` — system emails
- `NERVE Feedback <feedback@getnerve.app>` — feedback notifications

**Optional:** `RESEND_BASE_URL` env var for EU endpoint override

**Emails sent:**
- Welcome email on registration (`send_welcome`)
- Additional email flows in `services/email_service.py`

**Failure handling:** Errors swallowed — email failure never blocks the triggering request.

**Key service file:** `services/email_service.py`

---

## OAuth / SSO — Google + Microsoft

**Purpose:** Social login for B2B users (Work/School accounts).

**SDK:** `authlib` 1.3.0+ (`routes/oauth.py`)
**Auth config:**
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Microsoft: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`

**Google configuration:**
- OIDC discovery: `https://accounts.google.com/.well-known/openid-configuration`
- Scope: `openid email profile`

**Microsoft configuration:**
- OIDC discovery: `https://login.microsoftonline.com/organizations/v2.0/.well-known/openid-configuration`
- Scope: `openid email profile`
- **Organizations endpoint only** — Work/School accounts (Microsoft 365), no personal accounts

**Login flow:**
- Email match: existing user gets OAuth fields attached (idempotent)
- New user: creates Organisation + User, redirects to `/onboarding`
- Tenant heuristic: checks existing OAuth users from same email domain for silent SSO

**User fields:** `User.oauth_provider`, `User.oauth_id`, `User.avatar_url`

**Key route file:** `routes/oauth.py`

---

## Web Search — Brave Search

**Purpose:** Company research for PreCall Intelligence briefing (Phase 04.13).

**SDK:** None — raw HTTP via `requests`
**Auth:** `BRAVE_SEARCH_API_KEY` env var
**Endpoint:** `https://api.search.brave.com/res/v1/web/search`

**Usage:**
- User provides company name/domain before a call
- Brave returns web results → fed to Claude Sonnet for structured briefing
- 3-layer output: structured fields (CEO, industry, headcount, product), free text, recommendations
- DSGVO: no raw data stored, only generated briefing (D-03)
- In-memory cache: 5 minute TTL (`_briefing_cache`, `_CACHE_TTL_S = 300`)

**Required fields extracted:** `geschaeftsfuehrer`, `branche`, `mitarbeiterzahl`, `hauptprodukt`

**Key service file:** `services/precall_service.py`

---

## Real-Time Bridge — Redis

**Purpose:** Inter-process communication between Flask app (port 8000) and FastAPI RT Engine (port 8001).

**SDK:** `redis-py` async client (`nerve_rt/redis_bridge.py`)
**Auth:** `REDIS_URL` env var — default `redis://127.0.0.1:6379`
**Server:** Redis installed as system package on VPS (`redis-server`), local only (not external)

**Key prefixes / channels:**
- `nerve:session:` — HSET, Flask writes session tokens, RT Engine validates
- `nerve:results:` — PUB/SUB, RT Engine publishes analysis results, Flask subscribes
- `nerve:control:` — PUB/SUB, Flask publishes control events (pause/resume), RT Engine subscribes

**Constraint:** No audio data ever touches Redis (ephemeral processing only, D-09)

**Key file:** `nerve_rt/redis_bridge.py`

---

## WebSockets — Flask-SocketIO + FastAPI RT Engine

**Purpose:** Real-time bidirectional communication with browser during live sessions.

**Flask-SocketIO (legacy path, port 8000):**
- `socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGIN, async_mode='threading')`
- `extensions.py` holds shared `socketio` instance to avoid circular imports
- Server emits: `transcript` (final transcription lines), `coaching` (coaching tips)
- CORS: `CORS_ORIGIN` env var (default `https://getnerve.app` in prod)

**FastAPI RT Engine (new async path, port 8001, `nerve_rt/`):**
- WebSocket router: `nerve_rt/routers/ws_router.py`
- Nginx routes `/ws/` path to port 8001 (`deploy/nginx.conf` line 49+)
- Adapters: `nerve_rt/services/stt/deepgram_adapter.py`, `nerve_rt/services/llm/claude_adapter.py`
- Shadow logger: `nerve_rt/services/llm/shadow_logger.py`
- Session manager: `nerve_rt/services/session_manager.py`

---

## Data Storage

**Primary database:**
- SQLite (development + production default): `sqlite:///database/nerve.db`
- PostgreSQL: supported via `DATABASE_URL` env var (SQLAlchemy URL format)
- ORM: SQLAlchemy 2.0+ declarative models (`database/models.py`)
- Connection: `database/db.py` exports `engine`, `SessionLocal`, `Base`, `get_session()`
- Schema migrations: inline `ALTER TABLE` in `app.py` `_migrate()` function (runs at startup)

**Key models:** `Organisation`, `User`, `Profile`, `ConversationLog`, `Session`, `TrainingScenario`, `BillingEvent`, `AuditLog`, `ExchangeRate`, `Feedback`, `ProfileOpener`

**File storage:** Local filesystem only — feedback screenshots (`MAX_CONTENT_LENGTH = 5MB`)

**Caching:** In-memory only (Python dicts with locks):
- PreCall briefing cache: `_briefing_cache` in `services/precall_service.py` (5 min TTL)
- Profile context cache: `_per_sid_profile` in `services/live_session.py`
- EWB TTFT history: `_ewb_ttft_history` deque in `services/claude_service.py`

---

## Monitoring & Observability

**Error tracking:** None (not detected)

**Logging:** `print()` to stdout with context prefixes:
- `[DB]` — database operations
- `[DG]` — Deepgram STT events
- `[AI]` — Claude API events
- `[API]` — general API events
- `[Stripe]` — payment events
- `[EMAIL]` — email sends
- `[OAuth]` — SSO events
- `[AUDIT]` — audit log failures
- Captured by systemd journald in production (`journalctl -u nerve -f`)

**Audit log:** `AuditLog` model + `services/audit.py` — immutable user action log (DSGVO: no transcript content, only aggregates and metadata)

**Cost tracking:** `services/cost_tracker.py` — API cost log with frozen FX rates at write time

---

## CI/CD & Deployment

**Hosting:** Hetzner VPS CX22 (Germany, EU) — `root@178.104.82.166`

**Deploy:** `./deploy.sh` — tar-over-SSH, no rsync required (works from Windows Git-Bash)
- Never transfers: `.env`, `.git`, `.planning`, `*.db`, `logs/`
- Never overwrites production SQLite

**CI pipeline:** None detected

**SSL:** Let's Encrypt / certbot, auto-renewal

**Process management:** systemd
- `nerve.service` — Flask/gunicorn (port 8000)
- `nerve-rt.service` — FastAPI/uvicorn (port 8001), requires `redis.service`

---

## Environment Configuration

**Required env vars summary:**

```
# AI
ANTHROPIC_API_KEY=
DEEPGRAM_API_KEY=
DEEPGRAM_HOST=api.eu.deepgram.com      # DSGVO default
ELEVENLABS_API_KEY=

# Payments
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_STARTER=
STRIPE_PRICE_ID_PRO=
STRIPE_PRICE_ID_BUSINESS=

# Auth
SECRET_KEY=                            # Required — app refuses to start without it in prod
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# Email
RESEND_API_KEY=

# Search
BRAVE_SEARCH_API_KEY=

# Database / Cache
DATABASE_URL=sqlite:///database/nerve.db
REDIS_URL=redis://127.0.0.1:6379

# App
CORS_ORIGIN=https://getnerve.app
FLASK_DEBUG=                           # Leave unset in production
```

**Secrets location (production):** `/etc/nerve/.env` — never committed to repo

---

## Webhooks & Callbacks

**Incoming webhooks:**
- `POST /payments/webhook` — Stripe billing events (signature-verified via `STRIPE_WEBHOOK_SECRET`)

**Outgoing webhooks/callbacks:**
- None detected

**OAuth callbacks:**
- `GET /auth/google/callback` — Google OIDC callback (`routes/oauth.py`)
- `GET /auth/microsoft/callback` — Microsoft OIDC callback (`routes/oauth.py`)

---

*Integration audit: 2026-05-01*
