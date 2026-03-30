# Architecture Research

**Domain:** AI real-time SaaS — payment integration + production deployment
**Researched:** 2026-03-30
**Confidence:** HIGH (existing codebase analyzed directly; Stripe + nginx/gunicorn patterns well-established)

---

## Standard Architecture

### System Overview: Milestone 1 Target State

```
Internet
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│  nginx (reverse proxy, port 80/443)                               │
│  - SSL termination via Let's Encrypt (Certbot)                    │
│  - HTTP → HTTPS redirect                                          │
│  - Static file serving (/static/)                                 │
│  - WebSocket upgrade passthrough                                  │
└──────────────────────┬──────────────────────────────┬────────────┘
                       │ HTTP                          │ WebSocket
                       ▼                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  gunicorn + gevent worker (port 5000, internal)                   │
│  - gevent async_mode required for Flask-SocketIO                  │
│  - Single worker (threading limitation of audio threads)          │
│  - Manages Flask app lifecycle                                     │
└──────────────────────┬────────────────────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────────────────┐
│  Flask Application (existing layered architecture)                │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Auth / Org  │  │ Live Session │  │ Stripe Billing           │ │
│  │ Blueprints  │  │ Blueprints   │  │ Blueprint (NEW)          │ │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬──────────────┘ │
│         │                │                       │               │
│  ┌──────▼────────────────▼───────────────────────▼──────────────┐ │
│  │  Service Layer                                                │ │
│  │  live_session.py | claude_service.py | metering_service.py   │ │
│  │  (NEW: stripe_service.py)                                     │ │
│  └──────────────────────────────┬────────────────────────────────┘ │
│                                 │                                 │
│  ┌──────────────────────────────▼────────────────────────────────┐ │
│  │  Database Layer (SQLite → PostgreSQL-compatible)              │ │
│  │  Organisation (stripe_customer_id, stripe_subscription_id)   │ │
│  │  User (minuten_used, trainings_voice_used, usage_reset_date) │ │
│  │  BillingEvent (webhook audit log)                            │ │
│  └───────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────┐                 ┌──────────────────────┐
│  Stripe API     │                 │  External APIs       │
│  - Subscriptions│                 │  - Deepgram (STT)    │
│  - Webhooks     │                 │  - Anthropic (AI)    │
│  - Checkout     │                 │  - ElevenLabs (TTS)  │
└─────────────────┘                 └──────────────────────┘
```

---

## Component Boundaries

### New Components (Milestone 1)

| Component | Responsibility | Lives In | Communicates With |
|-----------|---------------|----------|-------------------|
| `routes/billing.py` | Checkout session creation, customer portal, plan display | Routes layer | Stripe API, Organisation model |
| `routes/webhooks.py` | Stripe webhook receiver, signature verification, event dispatch | Routes layer | Stripe API, Organisation model, BillingEvent model |
| `services/stripe_service.py` | Stripe API calls (create customer, create checkout, cancel sub) | Service layer | Stripe SDK, Organisation model |
| `services/metering_service.py` | Usage increment, monthly reset, limit check logic | Service layer | User model, Organisation model |
| nginx config | TLS termination, static files, WebSocket proxy | Infra | gunicorn upstream |
| gunicorn config | WSGI process management with gevent workers | Infra | Flask app |
| systemd service | Process supervision, auto-restart on reboot | Infra | gunicorn |

### Existing Components Modified

| Component | What Changes | Why |
|-----------|-------------|-----|
| `database/models.py` | Add `stripe_customer_id`, `stripe_subscription_id`, `stripe_status` to Organisation | Subscription state tracking |
| `config.py` | Add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_IDS` dict | Stripe credentials |
| `routes/app_routes.py` | Fair-use check already exists — wire to `metering_service` | Centralize and harden |
| `app.py` | Register billing and webhook blueprints | Route registration |

---

## Data Flow: Stripe Subscription Lifecycle

### Checkout Flow (New Subscription)

```
User clicks "Subscribe" (billing page)
    │
    ▼
POST /billing/create-checkout-session
    │  (route: routes/billing.py)
    │
    ▼
stripe_service.create_checkout_session(org, plan)
    │  - stripe.Customer.create() if no stripe_customer_id
    │  - stripe.checkout.Session.create(
    │      customer=customer_id,
    │      line_items=[{price: STRIPE_PRICE_IDS[plan]}],
    │      mode='subscription',
    │      success_url, cancel_url,
    │      metadata={'org_id': org.id}
    │    )
    │
    ▼
Redirect → Stripe-hosted Checkout page
    │
    ▼ (user completes payment)
Stripe sends webhook: checkout.session.completed
    │
    ▼
POST /webhooks/stripe  (routes/webhooks.py)
    │  - Verify signature: stripe.Webhook.construct_event()
    │  - Extract org_id from metadata
    │  - Update Organisation.stripe_subscription_id
    │  - Update Organisation.plan to purchased plan
    │  - Update Organisation.aktiv = True
    │  - Write BillingEvent audit record
    │
    ▼
Redirect user to /dashboard (success_url)
```

### Subscription Lifecycle Webhooks

```
Stripe Event                         Action in webhooks.py
────────────────────────────────     ────────────────────────────────────────
customer.subscription.updated    →   Update org.plan, org.aktiv based on status
customer.subscription.deleted   →   Set org.aktiv = False, org.plan = None
invoice.payment_succeeded        →   Write BillingEvent, reset usage counters
invoice.payment_failed           →   Write BillingEvent, send warning (flash/email)
customer.subscription.trial_end →   Notify user, prompt payment
```

**Critical design rule:** Never trust HTTP redirect for subscription activation. Always activate via webhook only. The success_url redirect is UX-only.

### Webhook Endpoint Security

```
POST /webhooks/stripe
    │
    ├── Read raw request body (BEFORE any JSON parsing)
    ├── stripe.Webhook.construct_event(
    │       payload=request.data,          ← raw bytes, not request.json
    │       sig_header=request.headers['Stripe-Signature'],
    │       secret=STRIPE_WEBHOOK_SECRET
    │   )
    ├── If SignatureVerificationError → return 400
    └── Process event → return 200 immediately
```

**The raw body requirement is non-negotiable:** Flask's `request.data` must be used, not `request.get_json()`. Middleware that parses JSON first will break signature verification.

---

## Data Flow: Fair-Use Metering

### Current State (already in codebase)

The database schema is already correct:
- `users.minuten_used` — minutes consumed this billing period
- `users.trainings_voice_used` — TTS training sessions this period
- `users.usage_reset_date` — date of last reset (used for monthly boundary detection)
- `organisations.minuten_limit` — per-org limit (default 1000)
- `organisations.training_voice_limit` — per-org limit (default 50)

The soft-limit check pattern already exists in `routes/app_routes.py` (`/live` route). It handles monthly reset correctly.

### What to Add: Increment on Session End

```
User ends live session (POST /api/end_session)
    │
    ▼
Calculate session duration: dauer_sekunden / 60 = minutes
    │
    ▼
metering_service.increment_live_minutes(user_id, minutes)
    │  - Load user from DB
    │  - Check if usage_reset_date needs monthly reset first
    │  - user.minuten_used += minutes
    │  - Commit
    │
    ▼
Continue existing session finalization (save ConversationLog, etc.)
```

```
User completes training with TTS (POST /training/complete or equivalent)
    │
    ▼
metering_service.increment_training_voice(user_id, count=1)
    │  - Same pattern as above
    │
    ▼
Return training result to frontend
```

### Soft-Limit Enforcement (no hard blocks — project constraint)

```
At /live page load:
    check_fair_use(user, org) → status: ok | warning_90 | over_limit
        │
        ├── ok           → render normally
        ├── warning_90   → render with flash("Fast aufgebraucht", "info")
        └── over_limit   → render with flash("Limit erreicht. Upgrade?", "warning")
                           ← never redirect away, never disable features
```

The "no hard block" constraint is explicit in PROJECT.md. Users must always be able to start a session even over limit. The flash warning is the only action.

### Monthly Reset Boundary

Two trigger points reset usage:
1. At `/live` page load (already implemented in `app_routes.py`)
2. Via `invoice.payment_succeeded` webhook — reset usage when Stripe confirms new billing period

The webhook-triggered reset is more reliable than page-load detection for users who don't visit `/live` at period start.

---

## Deployment Architecture: nginx + gunicorn + Flask-SocketIO

### Critical Constraint: async_mode

The current app uses `async_mode='threading'` (line 25 of `app.py`):
```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

For gunicorn production deployment, this must change to `async_mode='gevent'`. The threading mode does not work correctly behind gunicorn. The gevent worker handles WebSocket connections as coroutines, which is the Flask-SocketIO-supported production pattern.

**Required packages to add:** `gevent` and `gevent-websocket`

### gunicorn Configuration

```ini
# gunicorn.conf.py
bind = "127.0.0.1:5000"
workers = 1                          # MUST be 1 — audio background threads are process-local
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
worker_connections = 100
timeout = 120                        # Long enough for live audio sessions
keepalive = 5
accesslog = "/var/log/nerve/access.log"
errorlog = "/var/log/nerve/error.log"
```

**Why workers = 1:** The three background threads (Deepgram, analysis loop, coaching loop) maintain in-process state via `live_session.py`. Multiple workers would spawn separate processes with separate state — users would hit different workers and lose session state. Single worker with gevent handles concurrency via coroutines within one process.

### nginx Configuration

```nginx
# /etc/nginx/sites-available/nerve
server {
    listen 80;
    server_name nerve.sale;  # replace with actual domain
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name nerve.sale;

    ssl_certificate     /etc/letsencrypt/live/nerve.sale/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nerve.sale/privkey.pem;

    # Static files served directly by nginx (bypass gunicorn)
    location /static/ {
        alias /opt/nerve/static/;
        expires 30d;
    }

    # Stripe webhook — no buffering, forward raw body
    location /webhooks/stripe {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_request_buffering off;    # Required for Stripe signature verification
    }

    # WebSocket upgrade for Socket.IO
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;       # Long timeout for persistent WS connections
        proxy_send_timeout 3600s;
    }

    # Everything else
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### systemd Service

```ini
# /etc/systemd/system/nerve.service
[Unit]
Description=NERVE Flask App
After=network.target

[Service]
User=nerve
WorkingDirectory=/opt/nerve
EnvironmentFile=/opt/nerve/.env
ExecStart=/opt/nerve/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Recommended Project Structure: New Files for Milestone 1

```
salesnerve/
├── routes/
│   ├── billing.py          # NEW: Stripe checkout, customer portal, plan pages
│   └── webhooks.py         # NEW: /webhooks/stripe handler
├── services/
│   ├── stripe_service.py   # NEW: Stripe API abstraction (customer, checkout, portal)
│   └── metering_service.py # NEW: Usage increment + reset logic (extracted from app_routes)
├── database/
│   └── models.py           # MODIFIED: add stripe_* columns to Organisation
├── config.py               # MODIFIED: add STRIPE_* keys, STRIPE_PRICE_IDS dict
├── app.py                  # MODIFIED: register billing/webhook blueprints
├── gunicorn.conf.py        # NEW: gunicorn production config
├── deploy/
│   ├── nginx.conf          # NEW: nginx site config
│   ├── nerve.service       # NEW: systemd service definition
│   └── setup.sh            # NEW: VPS provisioning script
└── requirements.txt        # MODIFIED: add stripe, gevent, gevent-websocket
```

---

## Architectural Patterns

### Pattern 1: Stripe Customer Per Organisation (not per User)

**What:** One Stripe Customer maps to one Organisation record. All users in an org share one subscription.

**When to use:** NERVE's billing model is organisation-scoped — the owner pays for the org, not individual users.

**Implementation:**
```python
# On first checkout initiation:
if not org.stripe_customer_id:
    customer = stripe.Customer.create(
        email=owner.email,
        name=org.name,
        metadata={'org_id': org.id}
    )
    org.stripe_customer_id = customer.id
    db.commit()
```

**Trade-off:** Simple and correct for current model. Requires migration work if moving to per-seat billing later.

### Pattern 2: Webhook-First Subscription State

**What:** All subscription state changes (activation, cancellation, renewal) are driven exclusively by Stripe webhooks. The checkout success redirect is UX only — it never mutates subscription state.

**When to use:** Always. HTTP redirects can be manipulated, duplicated, or missed.

**Why it matters for NERVE:** If the success redirect fires but the webhook is delayed (normal), the user's org would appear inactive until webhook arrives. The correct pattern: success page shows "Processing..." until webhook confirms, OR optimistically show dashboard and rely on webhook to set state in background.

### Pattern 3: Metering Service as Thin Wrapper

**What:** `metering_service.py` wraps all usage counter mutations. No route or service directly writes `user.minuten_used`.

**When to use:** Centralizes reset logic, prevents drift between the two reset triggers (page load and webhook).

**Trade-off:** Minor indirection cost, significant maintainability gain.

### Pattern 4: Single gunicorn Worker for Stateful Threads

**What:** Run exactly one gunicorn worker process. Use gevent for I/O concurrency within that process.

**When to use:** Any Flask app that maintains in-process state across requests (background threads, shared dicts, threading.Event objects).

**Why NERVE specifically:** `live_session.py` is a module-level singleton. Background threads (Deepgram, analyse_loop, coaching_loop) are started once at app init. Multiple worker processes would duplicate these threads with no shared state.

**Scale implication:** One process + gevent handles ~50-100 concurrent WebSocket connections on a CX22 VPS. Sufficient for Early Access (50 users). Revisit at ~200 concurrent sessions.

---

## Data Flow Summary: All New Flows

```
[Checkout Flow]
User → POST /billing/create-checkout →  stripe_service  → Stripe API
                                                              │
                          Organisation.stripe_customer_id ←──┘
                          (redirect to Stripe Checkout)
                                    │
                    Stripe webhook: checkout.session.completed
                                    │
POST /webhooks/stripe → webhooks.py → Organisation update → BillingEvent

[Usage Metering Flow]
POST /api/end_session → app_routes.py → metering_service.increment_live_minutes()
                                              → User.minuten_used += delta

GET /live → app_routes.py → metering_service.check_limits() → flash warning if needed

invoice.payment_succeeded webhook → webhooks.py → metering_service.reset_period()

[Deployment Flow]
nginx:443 → SSL termination → proxy_pass 127.0.0.1:5000
nginx:/socket.io/ → WebSocket upgrade → proxy_pass 127.0.0.1:5000
nginx:/static/ → served directly from disk (no gunicorn)
gunicorn → gevent worker → Flask app → existing blueprints + new billing/webhook blueprints
```

---

## Build Order (What Must Be Done First)

This is the mandatory dependency chain for launch:

```
1. Infrastructure first (blocks everything else)
   └── Hetzner VPS provisioned + SSH access
       └── nginx + certbot + SSL working
           └── gunicorn + gevent + systemd service running
               └── app accessible at domain over HTTPS

2. Stripe foundation (blocks payment flow)
   └── Stripe account created, keys in .env
       └── Products + prices created in Stripe dashboard (3 tiers: 69/59/49€)
           └── Price IDs stored in config.py STRIPE_PRICE_IDS
               └── stripe_customer_id + stripe_subscription_id columns added to Organisation
                   └── stripe_service.py + billing blueprint (checkout + portal)
                       └── webhooks.py with signature verification

3. Metering hardening (can parallel-track with Stripe)
   └── Extract metering logic to metering_service.py
       └── Wire /api/end_session to increment live minutes
           └── Wire training completion to increment voice sessions
               └── Wire invoice.payment_succeeded webhook to reset counters

4. Legal + launch (blocks going live)
   └── Impressum, AGB, Datenschutzerklärung pages
       └── Early Access pricing page (69/59/49€ with discount messaging)
           └── Activate 50 Early Access slots
```

**Do not** attempt to wire Stripe payments before SSL is working — Stripe webhooks require HTTPS and Stripe's checkout redirects require a valid domain.

---

## Scaling Considerations

| Scale | Architecture | Notes |
|-------|-------------|-------|
| 0–50 users (Early Access) | Single gunicorn worker, SQLite, CX22 | Current target. Sufficient. |
| 50–500 users | Single gunicorn worker, migrate to PostgreSQL, CX32 upgrade | SQLite write locks become bottleneck at ~100 concurrent sessions |
| 500–2000 users | Consider Redis for session state, multiple gunicorn workers with sticky sessions | Background threads must be moved to dedicated worker process (Celery/RQ) at this scale |
| 2000+ users | Microservices split: audio processing as separate service | Out of scope for current milestones |

**First bottleneck for NERVE:** SQLite write contention. The three background threads perform frequent writes to live session state. Migration to PostgreSQL is the single most important scaling step after Early Access validation.

**Second bottleneck:** Single gunicorn worker means vertical scaling only (bigger VPS). This is acceptable through Milestone 2.

---

## Anti-Patterns

### Anti-Pattern 1: Parsing JSON Before Stripe Signature Verification

**What people do:** Use `@app.before_request` to parse all JSON, or call `request.get_json()` before `stripe.Webhook.construct_event()`

**Why it's wrong:** Stripe signature is computed over the raw request bytes. Any transformation (including JSON parsing) invalidates the signature. Results in `stripe.error.SignatureVerificationError` on every webhook.

**Do this instead:** Read `request.data` (raw bytes) and pass directly to `construct_event()`. Parse the event object returned by construct_event.

### Anti-Pattern 2: async_mode='threading' with gunicorn

**What people do:** Leave default `async_mode='threading'` when moving from `python app.py` to gunicorn.

**Why it's wrong:** gunicorn's standard workers use a pre-fork model incompatible with Flask-SocketIO's threading mode. WebSocket connections will randomly fail or silently drop.

**Do this instead:** Switch to `async_mode='gevent'` and use `GeventWebSocketWorker` in gunicorn config. Test WebSocket functionality explicitly after deployment, not just HTTP routes.

### Anti-Pattern 3: Activating Subscriptions on Checkout Redirect

**What people do:** On the `success_url` redirect, mark the org as active and set the plan.

**Why it's wrong:** Redirects can be double-fired, skipped, or intercepted. Stripe's documentation explicitly states the success URL is unreliable for fulfillment.

**Do this instead:** Fulfillment exclusively via `checkout.session.completed` webhook. The success_url page shows a confirmation message but makes no state changes.

### Anti-Pattern 4: Multiple gunicorn Workers with In-Process State

**What people do:** Scale gunicorn to `workers = 4` to handle more load.

**Why it's wrong for NERVE:** `live_session.py` is module-level state. Each worker process gets its own copy. A user who starts a session on worker 1 sends audio to worker 2, which has no active session state. The three background threads would also be duplicated across workers with no coordination.

**Do this instead:** Single worker + gevent concurrency. When true horizontal scaling is needed (Milestone 3+), move session state to Redis and use proper message queues for the audio pipeline.

### Anti-Pattern 5: Hard-Blocking Users at Fair-Use Limit

**What people do:** Return 403 or redirect away from `/live` when `minuten_used >= minuten_limit`.

**Why it's wrong:** Explicitly against project constraints (PROJECT.md: "Kein harter Stopp bei Fair-Use"). Users in the middle of their workday must never be locked out — it's a trust-destroying UX failure for a B2B tool.

**Do this instead:** Flash warning only. Log the overage for internal monitoring. Consider proactive email when user hits 80% of limit.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Stripe | REST API via `stripe` Python SDK + webhook endpoint | Store customer/subscription IDs on Organisation. Idempotency keys on checkout creation. |
| Let's Encrypt | Certbot auto-renewal via cron/systemd timer | Certbot installs HTTP-01 challenge handler automatically. Renews every 60 days. |
| Deepgram | Existing WebSocket client in `deepgram_service.py` | No changes needed. WebSocket upgrade handled by nginx config. |
| Anthropic | Existing HTTP client in `claude_service.py` | No changes needed. |
| ElevenLabs | Existing HTTP client in `training_service.py` | No changes needed. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `billing.py` ↔ `stripe_service.py` | Direct function call | stripe_service owns all Stripe SDK calls; billing route owns session/response |
| `webhooks.py` ↔ `models.py` | SQLAlchemy session (direct DB write) | Webhooks are fire-and-forget from Stripe — process synchronously, return 200 fast |
| `metering_service.py` ↔ `app_routes.py` | Direct function call | Replace inline fair-use check with service call |
| `metering_service.py` ↔ `webhooks.py` | Direct function call | Webhook triggers usage reset on `invoice.payment_succeeded` |

---

## Sources

- Flask-SocketIO deployment documentation (gevent+gunicorn pattern): HIGH confidence — well-established pattern, version 5.x stable
- Stripe Checkout + webhook lifecycle: HIGH confidence — Stripe's documentation has been stable for years; webhook-first fulfillment is explicitly documented
- nginx WebSocket proxying (`proxy_http_version 1.1` + `Upgrade` headers): HIGH confidence — standard nginx pattern
- gunicorn single-worker constraint for in-process state: HIGH confidence — derived from codebase analysis (live_session.py singleton pattern)
- Fair-use metering pattern: HIGH confidence — derived from existing codebase (columns and soft-limit logic already present in app_routes.py)

---

*Architecture research for: NERVE SaaS — Milestone 1 (Stripe + metering + deployment)*
*Researched: 2026-03-30*
