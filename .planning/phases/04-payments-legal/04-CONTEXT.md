# Phase 4: Payments & Legal — Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up Stripe Checkout + Webhooks + Customer Portal, build a public/in-app `/pricing` page, implement fair-use metering with soft warnings, and ship German legal pages (Impressum, AGB, Datenschutzerklärung). Phase 4 gates Phase 5 (no paying customers without this).

No Stripe account exists yet — full setup from scratch including products and prices.

</domain>

<decisions>
## Implementation Decisions

### Stripe Setup

- **D-01:** No existing Stripe account — create from scratch. Planner tasks must include: create Stripe account, create 3 Products (Starter, Pro, Business), create recurring Prices at 49€, 59€, 69€/month (EUR), obtain Price IDs for `.env`.
- **D-02:** Use **Stripe Checkout (Hosted Session)** — `checkout.session.completed` webhook activates the subscription. Redirect URL is NOT used for activation (PAY-02).
- **D-03:** Payment methods: **Kreditkarte, SEPA Lastschrift, PayPal** (required), **Klarna** (optional). All configured via Stripe Dashboard payment method settings — no hardcoding in the app. The Checkout Session inherits whatever is enabled in the Dashboard.
- **D-04:** Webhook handler must be idempotent: deduplicate by `stripe_event_id` (add column to a webhook events table or `billing_events`). Verify signature with raw request body (`stripe.Webhook.construct_event`). PAY-03.
- **D-05:** Users manage subscriptions via **Stripe Customer Portal** — link from `/settings` billing tab (existing tab). One-click "Abo verwalten" button generates a portal session URL.
- **D-06:** `Organisation` model needs new columns: `stripe_customer_id`, `stripe_subscription_id`, `stripe_price_id`, `subscription_status` (e.g. `active`/`trialing`/`canceled`/`past_due`). `BillingEvent` (or new `StripeEvent`) table needs `stripe_event_id` for dedup.

### Pricing Page

- **D-07:** `/pricing` is a **public route** (no `@login_required`) AND serves as the in-app upgrade page. One template, two contexts: anonymous visitors see "Jetzt starten" CTAs → Stripe Checkout; logged-in users see same page with "Jetzt upgraden" CTAs → Stripe Checkout for their org.
- **D-08:** Base the pricing page on the **existing landing.html pricing cards** — extract and adapt, do not build from scratch. Use NERVE Design System tokens (glass panels, teal accent, nerve.css).
- **D-09:** All 3 plans (Starter 49€, Pro 59€, Business 69€) have the same Fair-Use limits (1000 Live-Minuten, 50 Trainings/Monat) — differentiation is by price tier and positioning copy only. PAY-06: pricing page shows feature comparison and Fair-Use limits.
- **D-10:** Gründerrabatt-Badge on pricing page: visual label ("50% Early Access Rabatt") on all cards — Claude's discretion on exact styling. No Stripe coupon code needed for this badge.

### Post-Checkout Flow

- **D-11:** After Stripe Checkout completes, user lands on **`/dashboard`** with a success flash message ("Abo aktiviert! Willkommen bei NERVE."). No separate thank-you page.
- **D-12:** Subscription activation is **webhook-only** (`checkout.session.completed`). The redirect from Stripe (`/checkout/success?session_id=...`) just redirects to `/dashboard` and shows the flash — it does NOT activate the subscription.

### Fair-Use Metering

- **D-13:** Fair-use counters (`live_minutes_used`, `training_sessions_used`) are incremented **atomically** in DB — use `Organisation.live_minutes_used += 1` inside a db session, not read-modify-write in Python. Reset monthly (compare `fair_use_reset_month` to current `YYYY-MM`).
- **D-14:** Soft warning at **~80%** of limit appears as a **toast/snackbar** — non-blocking, dismissible, shown once per session. Triggered on: Dashboard load AND at session start in `/live`.
- **D-15:** At **100%** (limit reached): show persistent "Limit erreicht — jetzt upgraden" message with an Upgrade button linking to `/pricing`. No hard block — session can continue but warning stays visible. PAY-05.
- **D-16:** 80% warning appears on: **Dashboard** (on page load) AND **`/live`** (at session start, before recording begins). 100% message appears in both locations as well.

### Legal Pages

- **D-17:** Routes: `/impressum`, `/agb`, `/datenschutz` — standard German SEO-friendly URLs, no `@login_required`.
- **D-18:** Content: generate **rechtskonforme German templates** for all three pages. Datenschutzerklärung must explicitly name **Deepgram, Anthropic, ElevenLabs, and Stripe** as Auftragsverarbeiter (per LEGAL-02). Templates should be functional/compliant placeholders André can review — not lorem ipsum.
- **D-19:** Footer links on `landing.html` and `base.html` must link to all three legal pages.
- **D-20:** LEGAL-03 (signed AVVs with Deepgram, Anthropic, ElevenLabs, Stripe) is a **manual task** — tracked as checklist items in the plan, not codeable. Deepgram EU endpoint (`api.eu.deepgram.com`) switch IS codeable (update `DEEPGRAM_URL` in config/env).

### DSGVO-Architektur (ergänzt 2026-04-02 — mit Rechtsberater erarbeitet)

- **D-21:** **Kein Audio wird gespeichert.** NERVE verarbeitet Audio ephemeral: rein → Analyse → sofort gelöscht. Niemals persistent. Dies ist das zentrale Datenschutzargument und muss in der Datenschutzerklärung explizit stehen.
- **D-22:** Live-Assistent hat **zwei Modi** mit unterschiedlicher Rechtsgrundlage:
  - **Cold-Call-Modus:** KI hört NUR den Berater, NICHT den Kunden. EWB-Buttons statt Kundenstimme. Kein Transkript, nur Metadaten. Rechtsgrundlage: berechtigtes Interesse (Art. 6 Abs. 1 lit. f DSGVO) — Dritte werden nicht verarbeitet.
  - **Meeting-Modus:** Consent-Pop-up vor dem Call. Zustimmung = volle Analyse beider Seiten. Ablehnung = automatischer Wechsel in Cold-Call-Modus. Rechtsgrundlage: Einwilligung (Art. 6 Abs. 1 lit. a DSGVO).
  - Die AGB und Datenschutzerklärung müssen beide Modi und ihre Rechtsgrundlagen klar beschreiben.
- **D-23:** **Training-Modus:** Verarbeitung ist durch AGB/Vertragserfüllung abgedeckt (Art. 6 Abs. 1 lit. b DSGVO). Kein separates Consent-Pop-up notwendig.
- **D-24:** **KI-Training mit Nutzerdaten:** Separate freiwillige Checkbox in den Einstellungen. DARF Training-Modus NICHT blockieren (Koppelungsverbot Art. 7 Abs. 4 DSGVO). Rechtsgrundlage: Einwilligung. Datenschutzerklärung muss diesen Verarbeitungszweck separat ausweisen.
- **D-25:** **EU-Server für alle Dienste** — kein Drittlandtransfer ohne Dokumentation:
  - Deepgram: EU-Endpoint (`api.eu.deepgram.com`) — update in config/env als Teil von Plan 04-01.
  - Anthropic Claude: AWS Bedrock Frankfurt (`eu-central-1`) — falls aktuell US-Endpoint, im Code prüfen und updaten.
  - ElevenLabs: EU Data Residency aktivieren (manuelle Aufgabe im Account).
  - Stripe: EU-Datenverarbeitung (Frankfurt) — standardmäßig DSGVO-konform.
  - Datenschutzerklärung muss Serverstandorte und Drittlandtransfer-Mechanismen (SCCs) dokumentieren.
- **D-26:** **Datenschutzerklärung Pflichtinhalt** — folgende Punkte MÜSSEN abgebildet sein:
  - Deepgram als Auftragsverarbeiter (STT), EU-Endpoint, AVV-Status
  - Anthropic als Auftragsverarbeiter (KI-Analyse), Bedrock Frankfurt, AVV-Status
  - ElevenLabs als Auftragsverarbeiter (TTS Training), EU Data Residency, AVV-Status
  - Stripe als Auftragsverarbeiter (Zahlungen), EU-Verarbeitung, AVV-Status
  - Cold-Call vs. Meeting-Modus: Rechtsgrundlagen und Verarbeitungsumfang
  - Ephemeral Audio Processing: explizit keine Speicherung
  - Freiwillige KI-Trainingsdaten-Einwilligung (Art. 7 Abs. 4 DSGVO)
  - Betroffenenrechte (Auskunft, Löschung, Widerspruch, Portabilität)

### Claude's Discretion

- Exact styling of the Gründerrabatt-Badge (size, placement, color — teal or gold)
- Whether to create a new `StripeEvent` table or add `stripe_event_id` to existing `BillingEvent`
- Flash message styling for post-checkout success
- Exact copy for plan differentiation on pricing page

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Payments & Metering — PAY-01 through PAY-06 (exact acceptance criteria)
- `.planning/REQUIREMENTS.md` §Legal & DSGVO — LEGAL-01 through LEGAL-04

### Existing Models & Config
- `database/models.py` — `Organisation` (has `plan`, `live_minutes_used`, `fair_use_reset_month`, billing fields), `BillingEvent` (needs Stripe fields)
- `config.py` — `PLANS` dict with Starter/Pro/Business limits
- `routes/settings.py` — existing `/billing` tab (Customer Portal button goes here)

### Existing Templates to Adapt
- `templates/landing.html` — existing pricing cards to extract/reuse for `/pricing`
- `templates/base.html` — footer where legal links must be added
- `templates/settings.html` — billing tab where "Abo verwalten" button goes

### Design System
- `static/nerve.css` — all NERVE design tokens; pricing page must use these

### No external specs
No ADRs or external docs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Organisation.live_minutes_used` + `fair_use_reset_month` — fair-use tracking already in DB schema
- `BillingEvent` model — extend with `stripe_event_id` for webhook dedup (or create new `StripeEvent` table)
- `routes/settings.py` `/billing` POST — existing billing info form; add Customer Portal button here
- `templates/landing.html` pricing cards — visual base for `/pricing` route

### Established Patterns
- Blueprint-based routes: new `payments_bp` in `routes/payments.py`
- DB session pattern: `try/finally db.close()` — use for all Stripe webhook DB writes
- Flash messages: Flask `flash()` + template display pattern already exists in auth

### Integration Points
- `app.py` — register `payments_bp`
- `config.py` — add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_IDS` dict
- `database/models.py` — extend `Organisation` with Stripe columns (migration via `app.py` `_migrate()` pattern)
- `base.html` — add footer legal links
- `routes/app_routes.py` — add fair-use check at session start (`/api/start_session` or wherever recording begins)

</code_context>

<specifics>
## Specific Ideas

- Payment methods (Kreditkarte, SEPA, PayPal, optional Klarna) configured via Stripe Dashboard — not hardcoded in app
- Stripe Checkout = hosted, not embedded Elements (simpler, handles SCA/3DS automatically)
- "Limit erreicht" at 100% shows upgrade button → `/pricing`, no hard session kill

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-payments-legal*
*Context gathered: 2026-04-01*
