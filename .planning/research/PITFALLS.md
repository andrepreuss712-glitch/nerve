# Pitfalls Research

**Domain:** AI real-time sales coaching SaaS (Flask + Stripe + VPS deployment + DSGVO)
**Researched:** 2026-03-30
**Confidence:** MEDIUM — WebSearch unavailable; based on training knowledge (Aug 2025) + codebase analysis (CONCERNS.md). Stripe API specifics and vendor DPA URLs should be verified against current official docs before implementation.

## Critical Pitfalls

### Pitfall 1: Stripe Webhook Duplicate Processing

**What goes wrong:**
Stripe retries webhooks on timeout or non-2xx response. Without an idempotency guard, a single `checkout.session.completed` event fires 3 times → subscription activated 3 times → org.aktiv and plan set repeatedly (benign) BUT billing logic can double-apply credits or re-send "welcome" emails.

**Why it happens:**
Developers handle the event, forget to store the event ID, and assume webhooks arrive exactly once.

**How to avoid:**
Store `stripe_event_id` in a `stripe_events` table with a UNIQUE constraint. At handler start: check for duplicate, return 200 immediately if found.

**Warning signs:**
Multiple welcome emails sent to one user; duplicate Stripe Customer records.

**Phase to address:**
Deployment & Launch — Stripe Integration

---

### Pitfall 2: Stripe Webhook Signature Verification Bypassed

**What goes wrong:**
`stripe.Webhook.construct_event()` requires the raw request body (bytes). Flask's `request.get_json()` or `request.json` parses and re-serializes, changing byte ordering → signature verification always fails → dev disables it → fake events can be injected.

**Why it happens:**
Most Flask tutorials show `request.get_json()`; webhook handlers need `request.data` (raw bytes).

**How to avoid:**
```python
payload = request.data  # NOT request.get_json()
sig_header = request.headers.get("Stripe-Signature")
event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
```
Also: nginx must have `proxy_request_buffering off` for the webhook endpoint.

**Warning signs:**
`stripe.error.SignatureVerificationError` in logs; developers commenting out verification "temporarily".

**Phase to address:**
Deployment & Launch — Stripe Integration

---

### Pitfall 3: nginx WebSocket Proxying Broken (Silent Degradation)

**What goes wrong:**
Without `proxy_http_version 1.1` + `Upgrade` + `Connection` headers, Socket.IO degrades to HTTP long-polling. The app appears to work but coaching hints arrive 2-3s late — destroying the product's core value proposition.

**Why it happens:**
nginx's default HTTP/1.0 proxy mode doesn't support WebSocket upgrades. The fallback to long-polling is transparent and doesn't throw errors.

**How to avoid:**
```nginx
location /socket.io/ {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_read_timeout 86400;  # live calls can run for hours
    proxy_pass http://127.0.0.1:5000;
}
```

**Warning signs:**
Network tab shows XHR polling requests instead of WebSocket frames; latency >1s for coaching tips.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 4: gunicorn Worker Mode Breaks SocketIO or Session State

**What goes wrong:**
Two failure modes:
1. `--workers > 1` → multiple processes each have their own `live_session.py` module singleton → user's audio goes to Worker A but poll hits Worker B → coaching tips never appear
2. Wrong worker class → WebSocket upgrade rejected

**Why it happens:**
Default gunicorn config uses multiple workers for scalability; developers don't realize Flask-SocketIO requires single-process or a Redis adapter.

**How to avoid:**
For Early Access (≤50 users), single worker is sufficient and safe:
```bash
gunicorn --workers 1 --worker-class eventlet --timeout 120 "app:app"
```
Check `async_mode` in `SocketIO()` init: must match worker class (`'threading'` → `gthread`, `'eventlet'` → `eventlet`).

**Warning signs:**
Live session works in dev but not in production; intermittent "no coaching" reports from different users.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 5: eventlet Monkey-Patch Import Order

**What goes wrong:**
If `async_mode='eventlet'`, `eventlet.monkey_patch()` must be the very first two lines of `app.py`. The 16 threading locks in `live_session.py` will deadlock with >2 concurrent users if standard `threading` is imported before monkey-patching.

**Why it happens:**
app.py has 22k lines with many imports at the top; the monkey-patch requirement is easy to miss.

**How to avoid:**
```python
# app.py — lines 1-2, before ALL other imports
import eventlet
eventlet.monkey_patch()
```
Alternatively: stay on `async_mode='threading'` with `--worker-class gthread` (avoids this entirely).

**Warning signs:**
Hangs or timeouts under concurrent load that work fine with one user.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 6: Fair-Use Minute Counter Race Condition

**What goes wrong:**
Three background threads + concurrent sessions all read-modify-write `user.minuten_used`. Python `+=` on an ORM object is not atomic → undercounting of 10-30% likely under load.

**Why it happens:**
ORM objects cache the value; two threads read the same stale value, both increment, both write → one increment is lost.

**How to avoid:**
Use SQL-level atomic increment:
```python
db.session.execute(
    update(User).where(User.id == user_id)
    .values(minuten_used=User.minuten_used + delta)
)
```

**Warning signs:**
Users accumulate more minutes than physically possible; fair-use limits never trigger even after extended use.

**Phase to address:**
Deployment & Launch — Stripe & Metering

---

### Pitfall 7: DSGVO Art. 28 — Fehlendes AVV mit Auftragsverarbeitern

**What goes wrong:**
Every API call to Deepgram (voice data), Anthropic (transcript content), and ElevenLabs (voice synthesis) without a signed Auftragsverarbeitungsvertrag (AVV/DPA) is an Art. 28 DSGVO violation. A single complaint to the LfDI NRW (for Iserlohn) can result in a €10k-50k fine for a small operator.

**Why it happens:**
All three vendors provide DPAs but require active acceptance in their dashboards — it's not automatic.

**How to avoid:**
- **Deepgram:** console.deepgram.com → Settings → Data Privacy → sign DPA. Also switch to EU endpoint: `wss://api.eu.deepgram.com`
- **Anthropic:** api.anthropic.com → Privacy/Legal → DPA request process
- **ElevenLabs:** elevenlabs.io account → sign DPA in enterprise/privacy settings

Do this before first paying customer — not after.

**Warning signs:**
No signed DPA on file; using US-only API endpoints for EU users.

**Phase to address:**
Deployment & Launch — Legal & Compliance

---

### Pitfall 8: DSGVO — Gesprächspartner-Einwilligung fehlt in AGB

**What goes wrong:**
The customer on the other end of the call has not consented to voice processing. "Legitimate Interest" (Art. 6(1)(f)) is the viable legal basis, but requires: (1) a documented Legitimate Interest Assessment (LIA), (2) an AGB clause requiring subscribers to inform their call partners (or use DSGVO-Modus), (3) a clear opt-out mechanism.

**Why it happens:**
Most legal templates for SaaS don't cover real-time voice processing of third parties — this requires a specialist DSGVO attorney.

**How to avoid:**
AGB must include: "Der Nutzer ist verpflichtet, Gesprächspartner über die Nutzung von NERVE zu informieren oder den DSGVO-Modus (keine Sprachspeicherung) zu aktivieren."

**Warning signs:**
AGB template doesn't mention third-party voice data; no LIA document exists.

**Phase to address:**
Deployment & Launch — Legal & Compliance

---

### Pitfall 9: PyAudio on Linux VPS Deployment Failure

**What goes wrong:**
PyAudio requires `portaudio19-dev` system package and audio hardware. A headless Hetzner VPS has neither. If PyAudio is imported at startup (not lazily), the server crashes on boot.

**Why it happens:**
PyAudio works on developer MacOS/Windows but fails silently or crashes on Linux VPS without audio devices.

**How to avoid:**
Check if `pyaudio` is imported at module level in `app.py` or any services. If server-side audio capture is not needed (browser mic → Deepgram cloud), PyAudio should not be in server requirements. Create `requirements-server.txt` without PyAudio.

**Warning signs:**
`ImportError: No module named '_portaudio'` or `OSError: No Default Input Device Available` on server startup.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 10: SECRET_KEY Default in Production

**What goes wrong:**
CONCERNS.md confirms SECRET_KEY has no fail-fast guard. If `.env` is not configured on VPS, Flask uses a default or empty key → all sessions are insecure → session fixation attacks possible.

**Why it happens:**
Development convenience: app starts without `.env`. No startup assertion catches this.

**How to avoid:**
Add to `app.py` startup:
```python
assert app.config['SECRET_KEY'] != 'dev' and len(app.config['SECRET_KEY']) >= 32, \
    "SECRET_KEY must be set to a secure random value in production"
```

**Warning signs:**
App starts without error when `SECRET_KEY` is not set; `.env.example` shows a placeholder value.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 11: SQLite Lock Contention Under Concurrent Writes

**What goes wrong:**
3 background threads × N concurrent users all writing to SQLite produce `OperationalError: database is locked` under load. Default SQLite journal mode (DELETE) allows only one writer at a time.

**Why it happens:**
SQLite is fine for development with one user; lock contention appears only under concurrent load.

**How to avoid:**
Enable WAL mode — 1-line fix:
```python
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_con, connection_record):
    dbapi_con.execute("pragma journal_mode=WAL")
```
Provides full runway to Milestone 2 PostgreSQL migration.

**Warning signs:**
`OperationalError: database is locked` in logs; intermittent 500 errors during active sessions.

**Phase to address:**
Deployment & Launch — VPS Setup

---

### Pitfall 12: Business Setup as Critical Path Blocker

**What goes wrong:**
Gewerbeanmeldung → Geschäftskonto → Stripe account verification → USt-IdNr → AGB/Impressum is a 3-5 week sequential chain. Starting it after technical deployment means a 5-week delay between "app is ready" and "first payment can be taken."

**Why it happens:**
Technical founders focus on code first; legal/business setup feels like "later" work.

**How to avoid:**
Start business setup in parallel with technical deployment — not after. Specific lead times:
- Gewerbeanmeldung: 1-3 days (online in most cities)
- Geschäftskonto (Kontist/Finom): 3-7 days
- Stripe verification: 1-3 days after Geschäftskonto
- USt-IdNr: 2-4 weeks (Bundeszentralamt für Steuern)

**Warning signs:**
Business setup items are "not started" while app is in final testing.

**Phase to address:**
Business Setup — start immediately, parallel to technical work

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| SQLite instead of PostgreSQL | Zero setup | Lock contention >20 concurrent users | OK through Milestone 1 (50 users) |
| Single gunicorn worker | Avoids state bugs | CPU-bound ceiling | OK through Milestone 1 |
| ElevenLabs instead of own TTS | No infra | ~8€/user/month cost floor | OK until 500 customers |
| Jinja2 instead of SPA | No build tooling | Limited interactivity | OK — Flask + Vanilla JS is the constraint |
| cors_allowed_origins="*" | Dev convenience | Security vulnerability | Never in production |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Stripe webhooks | Read `request.json` instead of `request.data` | Use `request.data` (raw bytes) for signature verification |
| Stripe webhooks | Trust success URL redirect for fulfillment | Fulfill only on `checkout.session.completed` webhook |
| Deepgram | Use US endpoint from German server | Use `wss://api.eu.deepgram.com` for DSGVO compliance |
| Flask-SocketIO | Multiple gunicorn workers | `--workers 1` mandatory for in-process state |
| nginx + SocketIO | Missing WebSocket upgrade headers | Add `proxy_http_version 1.1` + `Upgrade` + `Connection` |
| ElevenLabs | Import at startup without lazy loading | Lazy-import or handle `ELEVENLABS_API_KEY` not set gracefully |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| SQLite WAL mode not set | `database is locked` errors | `pragma journal_mode=WAL` at startup | >5 concurrent active sessions |
| ORM read-modify-write for counters | Undercounted usage minutes | SQL atomic update expressions | >2 concurrent sessions |
| Single gunicorn worker | CPU bottleneck on analysis | Redis adapter + multiple workers (Milestone 2) | >100 concurrent users |
| In-process session state | Worker restart loses all active calls | Acceptable for Early Access | >50 concurrent users |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `SECRET_KEY` not set | Session hijacking | Startup assertion; generate 32+ char random key |
| `cors_allowed_origins="*"` | Cross-origin WebSocket from any domain | Set to actual domain before first deploy |
| Stripe webhook without signature check | Fake event injection (free subscriptions) | Always verify `Stripe-Signature` header |
| No Stripe event idempotency | Double-processing, duplicate emails | Store `stripe_event_id` with UNIQUE constraint |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Hard fair-use block mid-call | Trust-destroying; user loses deal | Soft warning at 80% + no hard stop (already in design) |
| Empty profile editor on first login | NERVE gives generic useless tips | Profile wizard before dashboard access |
| Missing DSGVO consent banner | Legal violation + user distrust | Show before microphone access, not after |
| Demo data in profile placeholder text | Confusion (whose product am I selling?) | Generic placeholders ("Ihr Produkt", "Ihr Unternehmen") |

## "Looks Done But Isn't" Checklist

- [ ] **Stripe payment:** AVV with Stripe Payments Europe signed, not just account created
- [ ] **DSGVO compliance:** AVVs signed with Deepgram, Anthropic, AND ElevenLabs — not just Stripe
- [ ] **Deepgram EU endpoint:** `wss://api.eu.deepgram.com` actually in config, not just `wss://api.deepgram.com`
- [ ] **Secret key:** production `.env` has 32+ char random SECRET_KEY, not placeholder
- [ ] **WebSocket test:** network tab confirms WS frames (not XHR polling) on production domain
- [ ] **Stripe webhook:** test event sent and processed; idempotency guard verified
- [ ] **Fair-use counter:** counter increments on session end, resets on billing cycle (test with Stripe test clock)
- [ ] **Impressum:** contains postal address, phone number, and responsible person per TMG §5
- [ ] **AGB:** clause covering third-party voice data processing is present

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Stripe webhook not idempotent (post-launch) | MEDIUM | Add idempotency table; replay recent events; manually check affected subscriptions |
| WebSocket degraded to polling (post-launch) | LOW | Fix nginx config, reload nginx — no redeploy needed |
| DSGVO AVV missing (discovered by user complaint) | HIGH | Sign all DPAs immediately; document remediation; notify LfDI proactively if data already processed |
| SQLite lock contention (discovered in prod) | MEDIUM | Enable WAL mode in migration; restart app; no data loss |
| SECRET_KEY default in production | HIGH | Rotate key immediately; all sessions invalidated (users re-login); investigate for session tokens |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Stripe idempotency + signature | Stripe Integration | Test with Stripe CLI event replay; check for duplicate processing |
| nginx WebSocket config | VPS Setup | Network tab shows `101 Switching Protocols` on production |
| gunicorn worker mode | VPS Setup | Load test with 2 concurrent users; coaching tips appear correctly |
| eventlet monkey-patch order | VPS Setup | No deadlocks under concurrent load test |
| Fair-use race condition | Stripe & Metering | Counter equals actual session duration ±5% |
| DSGVO AVVs | Legal & Compliance | Screenshot of signed DPA in each vendor dashboard |
| DSGVO AGB clause | Legal & Compliance | AGB reviewed by DSGVO-erfahrener Anwalt; LIA documented |
| PyAudio on VPS | VPS Setup | App starts without error on clean VPS (no audio hardware) |
| SECRET_KEY in production | VPS Setup | Startup assertion throws error if key is placeholder |
| SQLite WAL mode | VPS Setup | No `database is locked` errors under 5-concurrent-user test |
| Business setup critical path | Business Setup | Gewerbeanmeldung submitted before technical deployment starts |

## Sources

- Flask-SocketIO documentation (gevent/eventlet deployment requirements)
- Stripe documentation (webhook idempotency, webhook signature verification)
- DSGVO Art. 28 (Auftragsverarbeitung)
- BDSG §26 (Mitarbeiterdaten) — not applicable but referenced for voice data context
- Codebase analysis: `.planning/codebase/CONCERNS.md`

---
*Pitfalls research for: Flask SaaS + Stripe + VPS deployment + DSGVO (voice processing)*
*Researched: 2026-03-30*
