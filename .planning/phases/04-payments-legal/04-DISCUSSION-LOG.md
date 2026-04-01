# Phase 4: Payments & Legal — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 04-payments-legal
**Areas discussed:** Stripe Setup State, Pricing Page, Fair-Use Warning UX, Legal Pages

---

## Stripe Setup State

| Option | Description | Selected |
|--------|-------------|----------|
| Existing account | Stripe already configured, just add Price IDs | |
| New account from scratch | Create account, products, prices from zero | ✓ |

**User's choice:** New account from scratch. Create 3 products + prices (49/59/69€). Payment methods: Kreditkarte, SEPA Lastschrift, PayPal (required), Klarna (optional) — configured in Stripe Dashboard, not hardcoded. Use Stripe Checkout (Hosted Session).

---

## Pricing Page

| Option | Description | Selected |
|--------|-------------|----------|
| Public only | Visible to anonymous visitors only | |
| In-app only | Logged-in upgrade page only | |
| Both | Public marketing + in-app upgrade, one template | ✓ |

**User's choice:** Both — one `/pricing` route, public + in-app. Reuse existing landing.html pricing cards as base. No separate template to build.

**Follow-up — logged-in view:**

| Option | Description | Selected |
|--------|-------------|----------|
| A | Same page as anonymous, with "Jetzt upgraden" CTA → Stripe Checkout | ✓ |
| B | Modified version with current plan highlighted, upgrade/downgrade buttons | |

---

## Fair-Use Warning UX

| Option | Description | Selected |
|--------|-------------|----------|
| Dashboard only | Warning appears on Dashboard at 80% | |
| Dashboard + /live | Warning on both Dashboard and active session page | ✓ |

**User's choice:** Dashboard + /live. 80% = soft warning. 100% = "Limit erreicht — jetzt upgraden" with upgrade button, no hard block.

**Follow-up — warning presentation:**

| Option | Description | Selected |
|--------|-------------|----------|
| A | Toast/snackbar (non-blocking, dismissible, once per session) | ✓ |
| B | Inline banner below AI panel (stays visible) | |

---

## Legal Pages

| Option | Description | Selected |
|--------|-------------|----------|
| Content ready | User provides Impressum, AGB, Datenschutz text | |
| Generated templates | Claude generates rechtskonforme German templates | ✓ |

**User's choice:** Generate rechtskonforme German templates for all three pages. AVVs (LEGAL-03) tracked as manual checklist in plan.

**Follow-up — URL structure:**

| Option | Description | Selected |
|--------|-------------|----------|
| A | `/impressum`, `/agb`, `/datenschutz` (standard German) | ✓ |
| B | Custom URLs | |

---

## Claude's Discretion

- Gründerrabatt-Badge exact styling
- StripeEvent table vs. extending BillingEvent
- Flash message styling for post-checkout

## Deferred Ideas

None.
