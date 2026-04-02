---
phase: 04-payments-legal
plan: "01"
subsystem: payments
tags: [stripe, payments, webhook, checkout, portal, billing]
dependency_graph:
  requires: []
  provides: [payments_bp, stripe-checkout, stripe-webhook, stripe-portal]
  affects: [routes/payments.py, database/models.py, config.py, templates/settings.html]
tech_stack:
  added: [stripe>=11.0.0]
  patterns: [idempotent-webhook, stripe-checkout-session, stripe-customer-portal, blueprint-registration]
key_files:
  created:
    - routes/payments.py
  modified:
    - requirements.txt
    - config.py
    - .env.example
    - database/models.py
    - app.py
    - templates/settings.html
decisions:
  - "Webhook uses raw request.data (not get_json) — required for Stripe signature verification"
  - "Idempotency via stripe_event_id UNIQUE index on billing_events — silent skip on duplicate"
  - "checkout_success only flashes message and redirects — activation happens in webhook only (D-12)"
  - "stripe_customer_id stored on Organisation at checkout — reused on subsequent checkouts (D-06)"
  - "pricing route is a placeholder — full template comes in Plan 02"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-02"
  tasks_completed: 2
  files_changed: 6
---

# Phase 04 Plan 01: Stripe Payment Foundation Summary

Complete Stripe payment integration wired up: Checkout Sessions for plan selection, idempotent Webhook handler activating subscriptions, Customer Portal for self-service billing, and DB schema extended with all Stripe columns.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Stripe dependency + DB schema + config | 7727fe0 | requirements.txt, config.py, .env.example, database/models.py, app.py |
| 2 | Payments blueprint — Checkout, Webhook, Portal, Success | 0c5e1e9 | routes/payments.py, app.py, templates/settings.html |

## What Was Built

### Task 1: Stripe dependency + DB schema + config

- `requirements.txt`: Added `stripe>=11.0.0`
- `config.py`: Added `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_IDS` dict with starter/pro/business keys
- `.env.example`: Added 5 Stripe env vars with placeholder values
- `database/models.py`:
  - `Organisation` model extended with: `stripe_customer_id`, `stripe_subscription_id`, `stripe_price_id`, `subscription_status` (default 'inactive')
  - `BillingEvent` model extended with: `stripe_event_id` (VARCHAR 200, unique, nullable)
- `app.py` `_migrate()`: Extended organisations migration block with Block 7 Stripe columns; added new billing_events migration block with `stripe_event_id` column and `CREATE UNIQUE INDEX IF NOT EXISTS ix_billing_events_stripe_event_id`

### Task 2: Payments blueprint

`routes/payments.py` — new file, `payments_bp` Blueprint with `url_prefix='/payments'`:

- **`POST /payments/checkout/<plan>`** (`@login_required`): Creates Stripe Customer if needed, stores `stripe_customer_id` on Organisation, creates Checkout Session with subscription mode, redirects to Stripe-hosted checkout
- **`GET /payments/checkout/success`** (`@login_required`): Flashes success message, redirects to dashboard — does NOT activate subscription (D-12)
- **`POST /payments/webhook`** (no auth): Verifies Stripe signature with raw `request.data`, checks idempotency against `billing_events.stripe_event_id`, dispatches to handler functions, records BillingEvent
- **`POST /payments/portal`** (`@login_required`): Creates Stripe Customer Portal session, redirects to portal URL
- **`GET /payments/pricing`**: Renders pricing.html placeholder (full template in Plan 02)

Webhook event handlers:
- `checkout.session.completed` → activates subscription (sets plan, subscription_status='active', stores IDs)
- `customer.subscription.updated` → syncs subscription_status
- `customer.subscription.deleted` → sets subscription_status='canceled'
- `invoice.paid` → resets fair-use counters (live_minutes_used, training_sessions_used)
- `invoice.payment_failed` → sets subscription_status='past_due'

`app.py`: `payments_bp` imported and registered.

`templates/settings.html`: Added "Abo verwalten" block in billing tab — shows only if `g.org.stripe_customer_id` is set, POST form to `/payments/portal`.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- **`payments.pricing` route** renders `pricing.html` which does not yet exist — this is intentional. The route is a placeholder per plan spec ("full template in Plan 02"). Plan 04-02 (pricing page) will create `templates/pricing.html`. This stub will not cause issues until a user navigates to `/payments/pricing`.

## User Setup Required

Before Stripe payment flows can be tested, the following Stripe Dashboard setup is required (per plan `user_setup`):

1. Create Stripe account at stripe.com
2. Create 3 Products: Starter (49 EUR/mo), Pro (59 EUR/mo), Business (69 EUR/mo)
3. Enable payment methods: Kreditkarte, SEPA Lastschrift, PayPal (required); Klarna (optional)
4. Create webhook endpoint for `https://getnerve.app/payments/webhook` with events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
5. Configure Customer Portal (allow cancel, plan switching)
6. Set env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_STARTER`, `STRIPE_PRICE_ID_PRO`, `STRIPE_PRICE_ID_BUSINESS`

## Self-Check: PASSED
