# Stack Research

**Domain:** AI real-time sales coaching SaaS — Launch phase additions (Stripe, deployment, DSGVO)
**Researched:** 2026-03-30
**Confidence:** MEDIUM (training knowledge to August 2025; WebSearch/WebFetch unavailable — verify versions before pinning)

---

## Context: What Is Already Locked

The core stack is not a research question. This file only covers the three additions needed for launch:

1. **Stripe** — subscription billing + fair-use metering in Flask
2. **Production deployment** — gunicorn + nginx + systemd on Hetzner CX22
3. **DSGVO** — data processing agreements (AVV/DPA) with Deepgram, Anthropic, ElevenLabs

---

## Part 1: Stripe Subscription + Fair-Use Metering

### Recommended Stack

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `stripe` (Python SDK) | `>=10.0.0` | All Stripe API calls — Customers, Subscriptions, Prices, webhooks | Official SDK; v10 uses sync-by-default with proper error types. Do NOT use v2-era API |
| `stripe` CLI | latest | Local webhook forwarding during dev (`stripe listen`) | Essential for testing webhook handlers without ngrok |
| Stripe Customer Portal | hosted (no extra lib) | Self-serve subscription management (cancel, upgrade, billing info) | Stripe hosts it; zero code for the cancellation/upgrade flow |
| Stripe Checkout | hosted Sessions API | Payment page for initial subscription | Stripe-hosted = no PCI scope for NERVE; redirect user, Stripe handles card input |

### Stripe Architecture for NERVE's Pricing Model

NERVE's model is: **Flat-rate subscription** (69/59/49 €/month) with **soft fair-use limits** (1,000 min live, 50 trainings/month). No hard blocks, no metered overage charges. This is simpler than true metered billing.

**The right Stripe objects:**

```
Stripe Customer  →  one per NERVE user (stores billing info)
Stripe Product   →  "NERVE Subscription" (one product)
Stripe Price     →  3x recurring prices (69€, 59€, 49€ annual)
Stripe Subscription  →  ties Customer to Price; has status field
Stripe Checkout Session  →  hosted payment page; redirects back on success
Stripe Customer Portal  →  self-serve cancel/upgrade
Stripe Webhook   →  notifies NERVE backend of payment events
```

**What NOT to use:** `stripe.UsageRecord` / metered pricing. That is for true pay-per-unit billing where the charge varies. NERVE's fair-use is a soft limit tracked in NERVE's own DB — Stripe only handles the flat fee. Using metered billing here adds complexity for no benefit.

### New DB Columns Required

Add to the `users` or `organisations` table:

```sql
stripe_customer_id      TEXT  -- stripe cus_xxx
stripe_subscription_id  TEXT  -- stripe sub_xxx
plan_tier               TEXT  -- 'early_access' | 'basic' | 'pro'
subscription_status     TEXT  -- 'active' | 'past_due' | 'canceled' | 'trialing'
current_period_end      DATETIME
live_minutes_used       INTEGER DEFAULT 0  -- reset monthly by webhook/cron
trainings_used          INTEGER DEFAULT 0  -- reset monthly
fair_use_warned_at      DATETIME           -- last time user received soft warning
```

### Flask Integration Pattern

**Blueprint approach** — add a `routes/billing.py` blueprint:

```python
# routes/billing.py
import stripe
from flask import Blueprint, redirect, request, current_app, session, jsonify

billing_bp = Blueprint('billing', __name__)
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
STRIPE_WEBHOOK_SECRET = os.environ['STRIPE_WEBHOOK_SECRET']

# 1. Create Checkout Session → redirect to Stripe hosted page
@billing_bp.route('/billing/checkout', methods=['POST'])
@login_required
def create_checkout():
    price_id = request.json.get('price_id')  # from PRICE_IDS dict
    checkout = stripe.checkout.Session.create(
        customer=g.user.stripe_customer_id,  # or None → Stripe creates one
        mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=url_for('dashboard.index', _external=True) + '?subscribed=1',
        cancel_url=url_for('billing.pricing', _external=True),
        metadata={'user_id': g.user.id},
    )
    return redirect(checkout.url)

# 2. Webhook handler — single endpoint, all events
@billing_bp.route('/billing/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        return '', 400

    # Handle relevant events only
    if event['type'] == 'checkout.session.completed':
        _handle_checkout_completed(event['data']['object'])
    elif event['type'] in ('customer.subscription.updated',
                           'customer.subscription.deleted'):
        _handle_subscription_change(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        _handle_payment_failed(event['data']['object'])

    return '', 200

# 3. Customer Portal → Stripe-hosted cancel/upgrade
@billing_bp.route('/billing/portal', methods=['POST'])
@login_required
def customer_portal():
    session = stripe.billing_portal.Session.create(
        customer=g.user.stripe_customer_id,
        return_url=url_for('dashboard.index', _external=True),
    )
    return redirect(session.url)
```

**Critical webhook events to handle:**

| Event | When It Fires | Action |
|-------|--------------|--------|
| `checkout.session.completed` | User completes payment | Activate subscription, store `stripe_subscription_id`, set `subscription_status = active` |
| `customer.subscription.updated` | Plan change, renewal, trial end | Sync `plan_tier`, `subscription_status`, `current_period_end` |
| `customer.subscription.deleted` | Cancellation takes effect | Set `subscription_status = canceled`, disable access |
| `invoice.payment_failed` | Renewal charge fails | Set `subscription_status = past_due`, send warning email |
| `invoice.paid` | Renewal succeeds | Reset `live_minutes_used = 0`, `trainings_used = 0` (monthly reset) |

### Fair-Use Tracking (No Stripe Involvement)

Track usage in NERVE's own DB. Check at session start:

```python
# In /live route, before starting session
def check_fair_use(user):
    if user.live_minutes_used >= FAIR_USE_LIVE_MINUTES:
        # Soft warning, do NOT block — per PROJECT.md constraint
        return {'warning': True, 'message': 'Fair-Use-Limit erreicht...'}
    return {'warning': False}
```

Increment on session end (`/api/end_session`):

```python
user.live_minutes_used += session_duration_minutes
db.session.commit()
```

Monthly reset via `invoice.paid` webhook (subscription renewal) or a cron job.

### Installation

```bash
pip install stripe>=10.0.0
```

Add to `requirements.txt`:
```
stripe>=10.0.0
```

**Confidence: MEDIUM** — stripe-python v10.x was released in 2024 and is current as of August 2025. Verify exact latest version at https://pypi.org/project/stripe/ before pinning.

---

## Part 2: Production Deployment on Hetzner CX22

### Hardware Reality Check

Hetzner CX22 specs: 2 vCPU (AMD EPYC), 4 GB RAM, 40 GB NVMe, Ubuntu 24.04, Falkenstein DC (Germany). At ~4€/month this is sufficient for 50 early-access users. Bottleneck will be concurrent SocketIO connections and background threads (Deepgram + Claude + coaching per live session), not HTTP traffic.

### Recommended Production Stack

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **gunicorn** | `>=22.0.0` | WSGI server, wraps Flask app | Industry standard for Flask production; handles worker process management |
| **nginx** | system (1.24+) | Reverse proxy, SSL termination, static files, WebSocket upgrade | Required for WebSocket proxying; gunicorn alone cannot handle SSL |
| **certbot** | system | Let's Encrypt SSL certificate management | Free TLS; auto-renewal via systemd timer |
| **systemd** | system | Process supervision, auto-restart | Standard on Ubuntu; simpler than supervisor for single-app VPS |
| **python3-venv** | system | Isolated Python environment | Prevents dependency conflicts with system Python |

### Critical: async_mode='threading' Means gthread Workers

The app is initialized as:
```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

This is the most important deployment constraint. Flask-SocketIO's `async_mode='threading'` requires **standard Python threading** — it is compatible with gunicorn's `gthread` worker class. It is **NOT compatible with eventlet or gevent workers**.

**Wrong (will break WebSockets):**
```bash
gunicorn --worker-class eventlet app:app        # WRONG
gunicorn --worker-class geventwebsocket...app   # WRONG
```

**Correct:**
```bash
gunicorn --worker-class gthread --threads 4 --workers 1 wsgi:app
```

Use exactly **1 worker** with multiple threads. Multiple workers break SocketIO's in-process state sharing (live_session.py shared state, transcript buffers, locks). The threading model assumes single-process.

### Deployment File Structure

```
/home/nerve/
├── app/                    # git clone here
│   ├── app.py
│   ├── wsgi.py             # NEW — gunicorn entry point
│   ├── requirements.txt
│   └── .env                # secrets (chmod 600)
├── venv/                   # python3 -m venv
└── logs/                   # application logs
```

**wsgi.py** (new file needed):
```python
# wsgi.py — gunicorn entry point
from app import app, socketio

if __name__ == '__main__':
    socketio.run(app)
```

Wait — actually Flask-SocketIO requires using the socketio object as the WSGI app for gunicorn. The correct approach:

```python
# wsgi.py
from app import app, socketio

# Flask-SocketIO exposes the WSGI-compatible app via socketio.wsgi_app
# For gunicorn, pass the socketio-wrapped app
application = socketio.manage(app)
```

Actually, the simplest correct approach for Flask-SocketIO with threading mode and gunicorn is to import and reference the socketio instance correctly. See the gunicorn config section below.

### gunicorn Configuration

Create `/home/nerve/app/gunicorn.conf.py`:

```python
# gunicorn.conf.py
bind = "127.0.0.1:5000"          # only localhost; nginx proxies externally
workers = 1                        # MUST be 1 — threading mode uses shared state
worker_class = "gthread"           # correct worker for async_mode='threading'
threads = 4                        # handles concurrent requests within single worker
timeout = 120                      # long timeout for audio analysis requests
keepalive = 5
accesslog = "/home/nerve/logs/gunicorn_access.log"
errorlog = "/home/nerve/logs/gunicorn_error.log"
loglevel = "info"
```

Start command:
```bash
gunicorn --config gunicorn.conf.py "app:app"
```

**Note on the entry point:** With Flask-SocketIO + threading mode, `app:app` (the Flask app object) works correctly with gunicorn gthread. The SocketIO middleware is already attached to the app object via `socketio = SocketIO(app, ...)`.

### systemd Service Unit

Create `/etc/systemd/system/nerve.service`:

```ini
[Unit]
Description=NERVE SaaS Application
After=network.target

[Service]
Type=notify
User=nerve
Group=nerve
WorkingDirectory=/home/nerve/app
Environment="PATH=/home/nerve/venv/bin"
EnvironmentFile=/home/nerve/app/.env
ExecStart=/home/nerve/venv/bin/gunicorn --config gunicorn.conf.py "app:app"
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
systemctl daemon-reload
systemctl enable nerve
systemctl start nerve
systemctl status nerve
```

### nginx Configuration

Critical: WebSocket proxying requires `Upgrade` and `Connection` headers. Without these, SocketIO long-poll fallback kicks in (works but slower).

Create `/etc/nginx/sites-available/nerve`:

```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name nerve.sale;  # replace with actual domain
    return 301 https://$host$request_uri;
}

# HTTPS + WebSocket proxy
server {
    listen 443 ssl;
    server_name nerve.sale;

    ssl_certificate     /etc/letsencrypt/live/nerve.sale/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nerve.sale/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers (DSGVO-relevant: prevents clickjacking)
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy strict-origin-when-cross-origin;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Static files served directly by nginx (bypasses Python)
    location /static/ {
        alias /home/nerve/app/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Stripe webhook — higher body size limit
    location /billing/webhook {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 1m;
    }

    # Socket.IO WebSocket endpoint
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;   # 24h — live calls can be long
        proxy_send_timeout 86400;
    }

    # All other routes
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

Enable:
```bash
ln -s /etc/nginx/sites-available/nerve /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### SSL via Certbot

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d nerve.sale
# Follow prompts; certbot auto-edits nginx config
# Auto-renewal via systemd timer (installed by certbot package)
systemctl status certbot.timer
```

### CORS Hardening for Production

Current code: `cors_allowed_origins="*"` — acceptable for early access but tighten before launch:

```python
# In app.py, change to:
socketio = SocketIO(
    app,
    cors_allowed_origins=["https://nerve.sale"],
    async_mode='threading'
)
```

### Environment Variables on Server

```bash
# /home/nerve/app/.env (chmod 600, owned by nerve user)
SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=sqlite:////home/nerve/app/database/salesnerve.db
DEEPGRAM_API_KEY=...
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_69=price_...
STRIPE_PRICE_ID_59=price_...
STRIPE_PRICE_ID_49=price_...
MAX_SESSION_HOURS=8
```

### Installation

```bash
# On Hetzner CX22 (Ubuntu 24.04)
apt update && apt upgrade -y
apt install nginx python3-venv python3-dev build-essential portaudio19-dev -y

# Create app user
useradd -m -s /bin/bash nerve

# Clone and set up
su - nerve
git clone <repo> app
cd app
python3 -m venv ~/venv
~/venv/bin/pip install -r requirements.txt
~/venv/bin/pip install gunicorn>=22.0.0
```

**Confidence: MEDIUM-HIGH** — gunicorn gthread + threading mode is well-documented. The `proxy_read_timeout 86400` for SocketIO long connections is a known requirement. The systemd unit pattern is standard Ubuntu practice.

---

## Part 3: DSGVO Data Processing Agreements (AVV)

### Legal Context

Under GDPR Art. 28, when NERVE sends personal data (voice, transcript content, conversation data) to external processors, a signed Data Processing Agreement (DPA / Auftragsverarbeitungsvertrag AVV) is mandatory. The three processors are Deepgram, Anthropic, and ElevenLabs.

All three offer self-serve DPA/AVV processes — no lawyer required, no negotiation needed for standard SaaS.

### Deepgram

**DPA availability:** YES — Deepgram provides a standard DPA for GDPR compliance.

**How to get it:**
- Log into Deepgram Console → Account Settings → Legal / Privacy → "Request DPA"
- Or email: privacy@deepgram.com with subject "DPA Request — GDPR Art. 28"
- Deepgram's DPA covers their EU data processing addendum

**Data transfer basis:** Deepgram is a US company. Their DPA includes Standard Contractual Clauses (SCCs) as the transfer mechanism under GDPR Chapter V.

**Server location note:** Deepgram has EU processing available. In the Deepgram API, add the `endpoint` parameter to route to EU servers:
```python
# Use EU endpoint in deepgram_service.py
DEEPGRAM_EU_URL = "wss://api.eu.deepgram.com/v1/listen"
```
Using EU servers strengthens DSGVO position significantly.

**What goes to Deepgram:** Raw audio stream, transcribed text. Under NERVE's DSGVO mode (default ON), no customer names or identifying info should appear, but audio itself is personal data. The DPA covers this.

**Confidence: MEDIUM** — Deepgram DPA exists per their public docs; exact current process may differ.

### Anthropic

**DPA availability:** YES — Anthropic offers a DPA for business customers.

**How to get it:**
- Anthropic Console (console.anthropic.com) → Account → Legal / Privacy
- Or: privacy@anthropic.com with "DPA Request — GDPR"
- Anthropic's "Data Processing Addendum" covers Claude API usage

**Data transfer basis:** SCCs (Anthropic is US-based, no EU data center confirmed as of August 2025). Anthropic's DPA includes EU SCCs.

**What goes to Anthropic:** Conversation transcripts (text, not audio), sales coaching context from user profiles. Under DSGVO mode, no direct customer PII should be included in prompts — NERVE already handles this.

**Important:** Anthropic's API Terms state they do not train on API data by default (as of 2024). Confirm this is still true in the current Terms of Service — it's a key selling point for NERVE's DSGVO compliance.

**Confidence: MEDIUM** — Anthropic DPA process exists; confirm exact URL/steps at console.anthropic.com.

### ElevenLabs

**DPA availability:** YES — ElevenLabs provides GDPR DPA.

**How to get it:**
- ElevenLabs dashboard → Account → Privacy / Legal
- Or: legal@elevenlabs.io
- Their DPA covers voice synthesis API usage

**Data transfer basis:** SCCs. ElevenLabs is US/UK-based.

**What goes to ElevenLabs:** Text to be synthesized (training scenario scripts). This is lower-risk than audio/transcripts — it's sales training script text, generally no personal data. Still requires DPA because training scenarios could contain customer names if user customizes them.

**Confidence: MEDIUM** — ElevenLabs GDPR compliance page exists; verify current DPA process.

### Datenschutzerklärung Requirements

The privacy policy (Datenschutzerklärung) must name each processor and their role. Template entries:

```
Spracherkennung: Deepgram, Inc., 535 Mission St, San Francisco, CA 94105, USA
  Zweck: Echtzeit-Transkription von Verkaufsgesprächen
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO (Vertragserfüllung) + AVV gem. Art. 28 DSGVO
  Datentransfer: USA, abgesichert durch EU-Standardvertragsklauseln

KI-Analyse: Anthropic, PBC, 548 Market St, San Francisco, CA 94104, USA
  Zweck: KI-gestützte Gesprächsanalyse und Coaching
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO + AVV gem. Art. 28 DSGVO
  Datentransfer: USA, abgesichert durch EU-Standardvertragsklauseln

Sprachsynthese (Training): ElevenLabs, Inc.
  Zweck: Text-zu-Sprache für KI-Trainingsszenarien
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO + AVV gem. Art. 28 DSGVO
  Datentransfer: USA, abgesichert durch EU-Standardvertragsklauseln
```

Also required for Stripe:
```
Zahlungsabwicklung: Stripe Payments Europe, Ltd., 1 Grand Canal Street Lower, Dublin 2, Irland
  Zweck: Abwicklung von Zahlungen und Abonnementverwaltung
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO + AVV gem. Art. 28 DSGVO
  Datentransfer: EU (Stripe Europe); teilweise USA über Stripe Inc.
```

**Note on Stripe:** Stripe Payments Europe (Irish entity) handles EU customers. The GDPR DPA with Stripe is available in the Stripe Dashboard → Settings → Compliance. Stripe's EU entity means no SCC needed for the primary processing.

### AVV Checklist

Before launch, verify these are in place:

- [ ] Deepgram DPA signed (or e-signed via their portal)
- [ ] Anthropic DPA signed
- [ ] ElevenLabs DPA signed
- [ ] Stripe DPA signed (in Stripe Dashboard)
- [ ] All four processors listed in Datenschutzerklärung
- [ ] Deepgram EU endpoint configured in deepgram_service.py
- [ ] Verarbeitungsverzeichnis (Art. 30 DSGVO) created — required for businesses processing personal data

**Confidence: MEDIUM** — GDPR Art. 28 requirements are stable law. Specific DPA portal locations may change; verify directly with each vendor.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| gunicorn gthread (1 worker, 4 threads) | gunicorn gevent/eventlet | App uses `async_mode='threading'` — gevent/eventlet workers will not work with SocketIO |
| gunicorn gthread | uwsgi | uwsgi WebSocket support is more complex to configure; gunicorn is the Flask community default |
| systemd | supervisor / pm2 | systemd is already present on Ubuntu 24.04; no extra install; simpler |
| Stripe Checkout (hosted) | Custom payment form | Custom form requires PCI SAQ-D compliance; hosted Checkout limits scope to SAQ-A |
| Stripe Customer Portal | Custom subscription management | Stripe Portal handles cancel/upgrade/billing details at zero development cost |
| stripe-python SDK | raw HTTP calls to Stripe API | SDK handles retry logic, idempotency keys, signature verification; raw HTTP is error-prone |
| Flat-rate + DB usage tracking | Stripe metered billing | Metered billing adds complexity for no gain; NERVE uses soft limits, not hard billing stops |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `gunicorn --worker-class gevent` | Incompatible with `async_mode='threading'`; SocketIO handshakes will fail | `--worker-class gthread` |
| `gunicorn --workers 4` (multiple workers) | Shared in-process state (live_session.py locks, buffers) breaks across workers | `--workers 1 --threads 4` |
| `socketio.run(app, host=...)` in production | Development server, not production-grade | gunicorn with wsgi entry point |
| `cors_allowed_origins="*"` in production | Allows any origin to connect SocketIO | Set to `["https://nerve.sale"]` |
| Stripe `UsageRecord` / metered prices | Wrong billing model for flat-rate + soft limits | Record usage in NERVE DB, use fixed recurring Price |
| Self-signing SSL | Browsers reject; DSGVO requires encryption in transit | Let's Encrypt via certbot |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `flask>=3.0.0` | `gunicorn>=20.1.0` | Flask 3.x WSGI compatible; use `app:app` entry point |
| `flask-socketio>=5.3.6` | `async_mode='threading'` + gunicorn gthread | DO NOT mix with eventlet/gevent |
| `stripe>=10.0.0` | Python 3.8+ | v10 dropped Python 3.6/3.7 support; v10 uses typed responses |
| `gunicorn>=22.0.0` | Python 3.8+ | v22 current as of 2024; gthread worker stable |
| nginx 1.24+ | Let's Encrypt + WebSocket | `proxy_http_version 1.1` required for WS upgrade |

**Note:** Check latest versions before pinning:
- stripe: https://pypi.org/project/stripe/
- gunicorn: https://pypi.org/project/gunicorn/

## Sources

- Training knowledge (Python, Flask, Stripe, nginx, GDPR) — HIGH confidence for patterns, MEDIUM for specific versions
- Flask-SocketIO deployment docs (training knowledge) — async_mode='threading' + gthread compatibility is documented in Flask-SocketIO v5 docs
- Stripe Python SDK docs (training knowledge) — Checkout Sessions, webhook handling, Customer Portal are stable APIs since 2022
- GDPR Art. 28 (law) — HIGH confidence; DPA requirement is unambiguous
- Vendor DPA availability — MEDIUM confidence; confirm current process directly with each vendor

**Verification priority before implementation:**
1. Confirm `stripe` latest version: `pip index versions stripe`
2. Confirm gunicorn gthread + Flask-SocketIO threading mode works: test in staging
3. Confirm Deepgram EU endpoint URL: check Deepgram docs
4. Confirm DPA portal locations for all four vendors before launch

---

*Stack research for: NERVE SaaS — Launch phase (Stripe + deployment + DSGVO)*
*Researched: 2026-03-30*
*Web tools unavailable — based on training knowledge to August 2025. Verify versions before pinning.*
