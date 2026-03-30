# Project Research Summary

**Project:** NERVE — AI Real-Time Sales Coaching SaaS
**Domain:** B2B SaaS, DACH market, Flask + SocketIO + Stripe deployment
**Researched:** 2026-03-30
**Confidence:** MEDIUM (training knowledge to August 2025; no live web search available)

## Executive Summary

NERVE is a mature v0.9.4 Flask application with the core product fully built — live objection coaching, training mode, post-call analysis, coach platform, gamification, and onboarding all exist and function. The Milestone 1 research question is not "how to build the product" but "what must be added and hardened to accept the first 50 paying customers in the DACH B2B market." The answer is a focused set of four work streams: (1) product fixes and feature gaps (pricing UI, training scenarios, onboarding wizard), (2) Stripe payment integration with billing UI, (3) production deployment on Hetzner CX22 with nginx/gunicorn, and (4) DSGVO/legal compliance including signed DPAs with all three AI vendors.

The recommended technical approach is deliberately conservative: keep the existing Flask + Vanilla JS stack, deploy as a single gunicorn worker with gthread workers (matching the existing `async_mode='threading'` SocketIO configuration), use SQLite with WAL mode for the Early Access phase, and use Stripe's hosted Checkout and Customer Portal to minimize PCI scope and development time. The architecture adds four new modules — `routes/billing.py`, `routes/webhooks.py`, `services/stripe_service.py`, and `services/metering_service.py` — without restructuring anything that already works.

The most critical risks are in the deployment and legal domains rather than the feature domain. Three pitfalls have the highest consequence if missed: (1) using the wrong gunicorn worker class will silently break WebSocket coaching delivery in production; (2) missing signed AVV/DPA agreements with Deepgram, Anthropic, and ElevenLabs before onboarding the first paying customer is an Art. 28 DSGVO violation; (3) the German business registration chain (Gewerbeanmeldung → Geschäftskonto → Stripe verification → USt-IdNr) takes 3-5 weeks and must start immediately in parallel with technical work, not after it.

## Key Findings

### Recommended Stack

The existing stack (Flask 3.x, Flask-SocketIO 5.x, SQLite, Deepgram Nova-2, Claude Haiku/Sonnet, ElevenLabs Multilingual v2) requires no changes for Milestone 1. The only additions are `stripe>=10.0.0` for billing and `gunicorn>=22.0.0` for production serving.

The single most important deployment decision is the gunicorn worker class: `--worker-class gthread --workers 1 --threads 4`. The app's `async_mode='threading'` is incompatible with gevent/eventlet workers. ARCHITECTURE.md contains a conflict on this point — it recommends gevent while STACK.md correctly identifies gthread as the match for `async_mode='threading'`. **STACK.md is correct.** The ARCHITECTURE.md gevent recommendation should be disregarded; it was produced without direct analysis of the `async_mode` setting.

**Core technologies added for Milestone 1:**
- `stripe>=10.0.0`: Subscription billing (Checkout Sessions + Customer Portal + webhooks) — official SDK with idempotency and signature verification built in
- `gunicorn>=22.0.0` with `gthread` worker: Production WSGI serving — single worker mandatory due to in-process SocketIO state
- nginx 1.24+: SSL termination and WebSocket upgrade proxying — required for production SocketIO; `proxy_http_version 1.1` + `Upgrade`/`Connection` headers are non-negotiable
- certbot: Let's Encrypt TLS — free, auto-renews, required before Stripe webhooks can be tested
- systemd service unit: Process supervision and auto-restart on VPS reboot

**Do not add:** gevent, gevent-websocket, eventlet, Stripe metered billing (UsageRecord), multiple gunicorn workers.

### Expected Features

The research confirms a clear split between already-built features and the gaps that block a credible Early Access launch.

**Must have at launch (not yet built):**
- Pricing page with 3-tier comparison table (69/59/49€), fair-use limits explicitly stated, DSGVO compliance positioned as a trust signal — DACH buyers read fine print and compare carefully
- Stripe payment integration with Checkout Session, webhook handler, and Customer Portal linked from account settings — German consumer law (Fernabsatzgesetz) requires self-serve cancellation
- 11 standard training scenarios covering DACH Mittelstand verticals (IT/software skeptic, procurement/price focus, competitor comparison, stakeholder delay, closing, renewal)
- Free vs. Guided training mode selection — power users need max-difficulty with no help; beginners need scaffolded coaching
- Post-training preview ("Was NERVE im echten Call gezeigt hätte") — concrete cross-sell trigger for live mode adoption
- ROI tracker in dashboard (calls handled + estimated deal value retained) — connects usage to business outcome, reduces churn
- 3-step profile wizard with generic placeholders and example boxes — empty profile produces generic AI coaching which kills first-impression quality
- Contextual empty states on dashboard — blank heatmap and achievements on new accounts feel broken
- Impressum, AGB, Datenschutzerklärung — hard legal requirement; AGB must include third-party voice data processing clause
- Fair-use usage tracking with 80% soft warning — no hard block per project constraint

**Should have (competitive, post-validation):**
- Annual billing toggle UI (show even if only monthly is active at launch)
- Loom walkthrough linked from help icon
- Slack/Teams integration for post-call summary export

**Defer to v2+:**
- English UI / US market
- Custom TTS (Piper/Coqui) — relevant at ~500 customers
- AI-generated custom training scenarios
- Fine-tuned sales AI (Llama/Mistral)
- Enterprise SSO / admin roles
- Call recording/playback (GDPR scope explosion, not worth it)

### Architecture Approach

Milestone 1 adds four new modules to the existing layered architecture without restructuring. Stripe billing state lives on the `Organisation` model (one Stripe Customer per org), not per user. All subscription state changes are driven exclusively by webhooks — the checkout success redirect is UX-only and must never mutate state. The metering service wraps all usage counter mutations to centralize the monthly reset logic and prevent race conditions via SQL-level atomic increments.

**Major components added:**
1. `routes/billing.py` — Checkout session creation, Customer Portal redirect, pricing page rendering
2. `routes/webhooks.py` — Stripe webhook receiver with raw-body signature verification and idempotency guard
3. `services/stripe_service.py` — All Stripe SDK calls (customer creation, checkout, portal); billing route owns session/response
4. `services/metering_service.py` — Usage increment (atomic SQL), monthly reset, soft-limit check; extracted from `app_routes.py`

**Deployment architecture:** nginx (443) → SSL termination → gunicorn (127.0.0.1:5000, 1 gthread worker, 4 threads) → Flask app. nginx serves `/static/` directly from disk. `/socket.io/` location block requires `proxy_http_version 1.1` + WebSocket upgrade headers + `proxy_read_timeout 86400`. Webhook endpoint (`/billing/webhook`) requires `proxy_request_buffering off` for Stripe signature verification.

**Build order is mandatory:** Infrastructure (VPS + SSL + nginx) must be running before Stripe webhooks can be tested. Stripe products/prices must be created in the dashboard before checkout sessions can be generated. SQLite WAL mode must be enabled before any concurrent load.

### Critical Pitfalls

1. **Wrong gunicorn worker class** — Using `--worker-class gevent` or `--worker-class eventlet` with `async_mode='threading'` will break WebSocket connections in production. The failure is silent (SocketIO falls back to long-polling, adding 2-3s latency that destroys the product's core value). Use `--worker-class gthread --workers 1`.

2. **Stripe webhook signature using parsed JSON** — `request.get_json()` re-serializes the body, invalidating the Stripe signature. Always use `request.data` (raw bytes). Developers who encounter `SignatureVerificationError` often disable verification "temporarily," creating a fake-event injection vulnerability. Never disable; fix the body reading instead.

3. **Missing AVV/DPA with AI vendors before first paying customer** — Deepgram (voice audio), Anthropic (transcripts), and ElevenLabs (TTS text) all require signed Art. 28 DSGVO data processing agreements. A complaint to LfDI NRW can result in €10k-50k fines. All three vendors provide self-serve DPA processes; this is a process task, not a technical one, but it must be completed before launch.

4. **Business setup is on the critical path** — Gewerbeanmeldung → Geschäftskonto → Stripe account verification → USt-IdNr takes 3-5 weeks sequentially. If not started immediately, the technical deployment will be complete and waiting on legal/business setup. Start the Gewerbeanmeldung this week, in parallel with technical work.

5. **Fair-use counter race condition** — Python ORM `user.minuten_used += delta` is not atomic under concurrent writes from three background threads. Use SQL-level atomic update: `UPDATE users SET minuten_used = minuten_used + ? WHERE id = ?`. Without this, counters undercount by 10-30% and fair-use warnings never trigger.

6. **PyAudio on Linux VPS** — PyAudio requires `portaudio19-dev` and audio hardware. A headless Hetzner VPS has neither. If imported at module level, the server crashes on boot. Verify whether PyAudio is in server-side imports; if browser mic audio goes directly to Deepgram cloud (likely), remove PyAudio from `requirements-server.txt`.

7. **SQLite lock contention** — Default journal mode produces `OperationalError: database is locked` under concurrent writes from audio background threads. Enable WAL mode at startup with `pragma journal_mode=WAL`. One-line fix with no data loss risk.

## Implications for Roadmap

Based on combined research, the mandatory dependency chain and DACH market requirements suggest five phases:

### Phase 1: Business Setup (Start Immediately, Parallel)
**Rationale:** The Gewerbeanmeldung → Geschäftskonto → Stripe verification → USt-IdNr chain takes 3-5 weeks. This is the critical path blocker for accepting payments. It must start in parallel with all technical work, not after it.
**Delivers:** Legal entity capable of accepting payments; Stripe account verified; VAT invoicing configured
**Addresses:** PITFALLS.md Pitfall 12 (Business setup as critical path blocker)
**Avoids:** "App is ready but can't take money for 5 more weeks" scenario
**Research flag:** No deeper research needed — the steps are known, the timeline is fixed, just start.

### Phase 2: Product Fixes and Feature Completion
**Rationale:** The existing product has known bugs (DSGVO banner, compact mode circles, toggle position) and missing features (pricing UI, training scenarios, onboarding wizard, ROI tracker) that directly affect first-impression quality for Early Access users. These must be solid before payments are wired.
**Delivers:** A complete, polished v1 product ready for 50 paying DACH B2B salespeople
**Addresses:**
- 3-step profile wizard with generic placeholders and example boxes (profile quality drives AI coaching quality)
- 11 standard DACH B2B training scenarios at all 4 difficulty levels
- Free vs. Guided training mode
- Post-training preview ("Was NERVE gezeigt hätte")
- ROI tracker in dashboard
- Contextual empty states on dashboard
- Live mode bug fixes (DSGVO banner, compact mode, script button)
- SalesNerve → NERVE remaining code cleanup
**Avoids:** Poor first impression from generic AI coaching (empty profile), blank dashboards, broken UI elements
**Research flag:** Standard product development — no additional research needed. Scenario content for the 11 training scenarios may benefit from reviewing DACH Mittelstand sales contexts.

### Phase 3: Infrastructure and Deployment
**Rationale:** SSL must be running before Stripe webhooks can be tested. Infrastructure must be stable before payment integration can be validated end-to-end. nginx WebSocket configuration is a known pitfall that must be verified in staging before customers hit it.
**Delivers:** App running on nerve.sale (or chosen domain) over HTTPS with WebSocket confirmed working
**Uses:** gunicorn (gthread worker, 1 worker, 4 threads), nginx with WebSocket upgrade config, certbot/Let's Encrypt, systemd service unit
**Implements:** Full deployment architecture from ARCHITECTURE.md
**Avoids:**
- Wrong gunicorn worker class (Pitfall 4)
- nginx WebSocket silent degradation (Pitfall 3)
- PyAudio crash on VPS (Pitfall 9)
- SECRET_KEY default in production (Pitfall 10)
- SQLite lock contention (Pitfall 11, enable WAL mode)
**Research flag:** Well-documented patterns. No additional research needed. Verify gunicorn/Flask-SocketIO threading mode compatibility with a manual WebSocket test post-deploy (network tab should show `101 Switching Protocols`, not XHR polling).

### Phase 4: Stripe Payment Integration
**Rationale:** Requires running SSL (Phase 3 complete) for webhook delivery. Requires Stripe account verified (Phase 1 in progress). Webhook-first fulfillment pattern must be followed strictly — success redirect must never activate subscriptions.
**Delivers:** Full payment flow: Checkout → webhook activation → Customer Portal self-service; fair-use metering wired to billing cycle resets; pricing page with 3-tier comparison live
**Uses:** `stripe>=10.0.0` Python SDK, Stripe Checkout (hosted), Stripe Customer Portal (hosted)
**Implements:** `routes/billing.py`, `routes/webhooks.py`, `services/stripe_service.py`, `services/metering_service.py`
**Avoids:**
- Webhook signature bypass via JSON parsing (Pitfall 2 / Anti-Pattern 1)
- Subscription activation on success redirect instead of webhook (Anti-Pattern 3)
- Stripe metered billing for flat-rate model (use DB usage tracking, fixed recurring Price)
- Webhook duplicate processing (store stripe_event_id with UNIQUE constraint)
- Fair-use counter race condition (atomic SQL update, Pitfall 6)
- Hard usage block mid-call (soft warning only, project constraint)
**Research flag:** Stripe Checkout + webhook patterns are well-documented and stable. No additional research needed. Verify Stripe VAT invoice configuration separately — DACH B2B buyers require proper Rechnungen and Stripe Tax must be configured before first payment.

### Phase 5: Legal, DSGVO, and Launch
**Rationale:** Legal pages (Impressum, AGB, Datenschutzerklärung) and signed vendor DPAs are hard launch blockers — not optional polish. AVV agreements must be in place before first paying customer, not after. Early Access slots activate after legal is confirmed.
**Delivers:** Legally compliant launch: Impressum (TMG §5), AGB (including third-party voice data clause), Datenschutzerklärung listing all sub-processors, signed DPAs with Deepgram/Anthropic/ElevenLabs/Stripe, Deepgram EU endpoint configured
**Addresses:**
- PITFALLS.md Pitfall 7 (missing AVV — DSGVO Art. 28 violation)
- PITFALLS.md Pitfall 8 (missing AGB clause for call partner voice data)
- FEATURES.md DACH consideration: DPA/AVV findable from pricing page for procurement review
**Avoids:** €10k-50k LfDI fine from first user complaint; Stripe account suspension for non-compliant data practices
**Research flag:** AVV signing processes for Deepgram, Anthropic, ElevenLabs, and Stripe should be verified directly in each vendor's dashboard before implementation — portal locations may have changed since August 2025 training data. The legal text for AGB (third-party voice data clause, Legitimate Interest Assessment for Art. 6(1)(f)) benefits from review by a DSGVO-experienced attorney; this is the only area where external professional input is recommended.

### Phase Ordering Rationale

- **Business setup starts first and runs in parallel** because it is time-gated by German bureaucracy (not by development effort) and blocks the ability to accept any payment.
- **Product fixes before payment** because early access users will form their first impression during payment-free evaluation; broken UI or empty dashboard on first login causes immediate churn.
- **Infrastructure before Stripe** because Stripe requires HTTPS for webhooks, and the webhook handler must be tested against a live Stripe test environment, not just locally.
- **Stripe before legal launch** because the payment flow must be end-to-end verified before Early Access slots open.
- **Legal last in the technical sequence** (but DPA signing should begin during Phase 3) because the legal pages reference the live domain and completed feature set; however, AVV signing with vendors is independent and should not wait.

### Research Flags

Phases needing caution during planning:
- **Phase 5 (Legal):** AGB clause covering third-party voice data (Art. 6(1)(f) Legitimate Interest) and the Legitimate Interest Assessment document are specialist DSGVO territory. Recommend a one-time review by a DSGVO-experienced German attorney (approximate cost: €300-600 for template review).
- **Phase 4 (Stripe):** Verify Stripe VAT invoice (Stripe Tax) configuration is enabled for Germany before first payment — missing VAT invoices cause DACH B2B churn immediately.

Phases with standard, well-documented patterns (no additional research needed):
- **Phase 2 (Product Fixes):** Standard Flask/Jinja2 development within existing architecture.
- **Phase 3 (Infrastructure):** gunicorn + nginx + certbot + systemd is the standard Flask production stack; patterns are stable and well-documented.
- **Phase 4 (Stripe):** Checkout Sessions + Customer Portal + webhook handling are documented Stripe patterns unchanged since 2022.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core stack is locked and well-understood. Stripe/gunicorn patterns are stable. Version pinning needs verification at implementation time (stripe, gunicorn latest). |
| Features | MEDIUM | DACH B2B feature expectations based on training knowledge of Gong/Chorus/CloseAI ecosystem; competitor-specific claims (CloseAI UX quality, pricing) should be spot-checked before using in marketing copy. |
| Architecture | HIGH | Derived directly from codebase analysis (live_session.py singleton, async_mode='threading', existing metering columns). Patterns are solid. Note: ARCHITECTURE.md gevent recommendation conflicts with STACK.md gthread recommendation — gthread is correct, gevent is wrong. |
| Pitfalls | MEDIUM-HIGH | Security and race condition pitfalls are derived from code analysis and are reliable. DSGVO DPA portal locations (Deepgram/Anthropic/ElevenLabs dashboard URLs) may have changed and must be verified directly. |

**Overall confidence:** MEDIUM-HIGH

The core technical decisions are solid and based on direct codebase analysis. The main uncertainty is in version-specific details (verify package versions before pinning) and vendor-specific process details (DPA portal locations, Stripe Tax configuration steps).

### Gaps to Address

- **Worker class conflict:** ARCHITECTURE.md recommends `gevent` while STACK.md recommends `gthread`. During Phase 3 planning, confirm the correct worker class by testing Flask-SocketIO WebSocket functionality with gthread workers. The recommendation here (gthread) is correct based on `async_mode='threading'` in `app.py`, but must be verified empirically post-deploy.
- **Stripe VAT invoice configuration:** Research did not cover the specific steps to configure Stripe Tax for German VAT invoicing (§14 UStG compliance). This must be resolved in Phase 4 planning — missing VAT invoices are an immediate churn trigger for DACH B2B buyers.
- **Deepgram EU endpoint URL:** `wss://api.eu.deepgram.com` is cited in research but should be confirmed against current Deepgram documentation before changing `deepgram_service.py`.
- **wsgi.py entry point:** STACK.md notes some ambiguity in the correct gunicorn entry point for Flask-SocketIO with threading mode. Test `gunicorn "app:app"` (Flask app object) vs. an explicit `wsgi.py` wrapper during Phase 3.
- **AVV signing process changes:** All three vendor DPA portal locations (Deepgram, Anthropic, ElevenLabs) cited from August 2025 training data. Verify current process directly with each vendor during Phase 5.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis (`app.py`, `live_session.py`, `database/models.py`, `routes/app_routes.py`) — async_mode, metering columns, existing blueprint structure
- GDPR/DSGVO Art. 28 (law) — AVV requirement is unambiguous; requirement is stable
- Flask-SocketIO v5.x documentation pattern (threading mode + gthread) — well-established, multiple sources agree

### Secondary (MEDIUM confidence)
- Stripe Python SDK v10.x documentation (training knowledge, Aug 2025) — Checkout Sessions, webhooks, Customer Portal APIs stable since 2022
- gunicorn + nginx + systemd Flask deployment patterns — community standard, well-documented
- DACH B2B SaaS market knowledge — competitor landscape (Gong, CloseAI, SalesEcho), pricing expectations, DSGVO procurement concerns
- SaaS onboarding best practices (Intercom, Appcues, ProductLed patterns) — stable since 2020

### Tertiary (LOW confidence — verify before use)
- Specific vendor DPA portal locations for Deepgram, Anthropic, ElevenLabs — may have changed
- Competitor-specific feature claims (CloseAI UX quality, pricing) — based on user reviews in training data
- Stripe Tax configuration for German VAT — not researched in detail

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
