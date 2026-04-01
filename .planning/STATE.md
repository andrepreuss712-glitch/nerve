---
gsd_state_version: 1.0
milestone: v0.9.4
milestone_name: milestone
status: waiting
stopped_at: Phase 03 Wave 1 complete — Wave 2 (VPS ops) pending user action
last_updated: "2026-04-01"
last_activity: 2026-04-01
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 12
  completed_plans: 10
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.
**Current focus:** Phase 03 — infrastructure-deployment (Wave 2 pending)

## Current Position

Phase: 03 (infrastructure-deployment) — WAITING ON MANUAL OPS
Plan: 3 of 3 (03-03 = VPS runbook, not yet done)
Status: Wave 1 code changes done. Wave 2 VPS provisioning pending user action.
Last activity: 2026-04-01

**Resume trigger:** User says "VPS ist live" → run Phase 3 verification → start Phase 4 planning.

Progress: [██████░░░░] ~40% (Phase 2 complete, Phase 3 Wave 1 complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 02-product-fixes P02 | 15 | 2 tasks | 2 files |
| Phase 02-product-fixes P01 | 15 | 2 tasks | 6 files |
| Phase 02-product-fixes P03 | 6 | 2 tasks | 0 files |
| Phase 02-product-fixes P04 | 18 | 2 tasks | 9 files |
| Phase 02-product-fixes P06 | 18 | 2 tasks | 3 files |
| Phase 02-product-fixes P05 | 12 | 2 tasks | 7 files |
| Phase 03 P02 | 3 | 2 tasks | 3 files |
| Phase 03-infrastructure-deployment P01 | 2 | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: LEGAL-04 placed in Phase 3 (infrastructure config, not legal document)
- Roadmap: Phase 1 (BIZ) and Phase 2 (PROD) run in parallel — both are independent tracks
- Roadmap: LEGAL-01 through LEGAL-03 grouped with PAY in Phase 4 (both are hard launch blockers, activated together)
- [Phase 02-product-fixes]: DSGVO banner triggered on socket connect event (not transcript) — earliest JS hook before server-side PyAudio capture
- [Phase 02-product-fixes]: SalesNerve Alpha retained in migration SQL WHERE clause — it is the search predicate for legacy record rename, not a branding artifact
- [Phase 02-product-fixes]: database/db.py had its own hardcoded salesnerve.db default — fixed alongside config.py as Rule 1 bug (inconsistent defaults)
- [Phase 02-product-fixes]: No code changes needed — training modes, scoring, preview, and scenario selector verified correct as-is (PROD-03 through PROD-06)
- [Phase 02-product-fixes]: PLANS dict has exactly 3 flat-rate plans: starter/pro/business at 49/59/69 EUR — all legacy keys removed
- [Phase 02-product-fixes]: Org-level fair-use counters (live_minutes_used, training_sessions_used) added alongside user-level counters; soft-warn at 80%, never hard-block
- [Phase 02-product-fixes]: POST wizard_create replaced JSON-API handler with form-data handler — matches HTML form submission pattern in rest of codebase
- [Phase 02-product-fixes]: Wizard redirect placed before expensive stats queries in dashboard route to minimize overhead for new users
- [Phase 03]: gthread 1+4 worker config: matches D-03 for CX22 with Flask-SocketIO threading mode
- [Phase 03]: WebSocket proxy timeouts set to 3600s in nginx — Socket.IO connections are long-lived during full sales calls
- [Phase 03-infrastructure-deployment]: SECRET_KEY check uses os.environ.get('FLASK_DEBUG') not app.debug — app.debug is always False at module-load under gunicorn
- [Phase 03-infrastructure-deployment]: WAL mode listener guarded by sqlite detection — safe for future PostgreSQL upgrade path
- [Phase 03-infrastructure-deployment]: CORS_ORIGIN defaults to nerve.app in production, wildcard only when FLASK_DEBUG env var is set

### Pending Todos

- [ ] **Phase 3 Wave 2**: Provision Hetzner CX22 VPS, configure nginx + SSL, deploy systemd service (03-03-PLAN.md — manual)
- [ ] **Phase 1**: Gewerbeanmeldung, Geschäftskonto, USt-IdNr, Steuerberater — all manual, user handles independently
- [ ] After VPS live: run Phase 3 verification, then start Phase 4 (Payments & Legal) planning

### Blockers/Concerns

- **Critical path**: Phase 4 (Stripe) cannot start until Phase 3 VPS is live (needs HTTPS for webhooks)
- **Critical path**: Phase 4 Stripe account verification needs Gewerbeanmeldung + Geschäftskonto (Phase 1 — takes 3-5 weeks)
- Research flags: AVV signing portal locations for Deepgram/Anthropic/ElevenLabs should be verified directly. Stripe Tax / VAT invoice configuration for Germany needs explicit research during Phase 4 planning.

## What's Done

| Phase | Plans | Status |
|-------|-------|--------|
| Phase 2: Product Fixes | 6/6 ✓ | Complete — all PROD requirements done |
| Phase 3: Wave 1 (code hardening) | 03-01 ✓ | pyaudio split, SECRET_KEY, WAL, CORS locked |
| Phase 3: Wave 1 (deploy artifacts) | 03-02 ✓ | deploy.sh, nginx.conf, nerve.service in repo |
| Phase 3: Wave 2 (VPS ops) | 03-03 ⏳ | Waiting on user — manual provisioning |
| Phase 1: Business Setup | 0/3 | User handles manually, not tracked here |

## Session Continuity

Last session: 2026-04-01
Stopped at: Phase 3 Wave 1 complete. Waiting for VPS provisioning.
Resume: User will say "VPS ist live" → verify Phase 3 → plan + execute Phase 4
