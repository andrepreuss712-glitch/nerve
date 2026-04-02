---
gsd_state_version: 1.0
milestone: v0.9.4
milestone_name: milestone
status: executing
stopped_at: Completed 04.1-01-PLAN.md
last_updated: "2026-04-02T18:18:51.707Z"
last_activity: 2026-04-02
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 30
  completed_plans: 23
  percent: 65
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.
**Current focus:** Phase 04.1 — live-mikrofon-fix-pyaudio-browser-getusermedia

## Current Position

Phase: 04.1 (live-mikrofon-fix-pyaudio-browser-getusermedia) — EXECUTING
Plan: 2 of 2
Status: Ready to execute
Last activity: 2026-04-02

**Next:** `/gsd:plan-phase 03.1 --gaps` — close 15 UAT issues, then plan Phase 4

Progress: [████████░░] ~65% (Phase 2 ✓, Phase 3 ✓, Phase 3.1 ✓ deployed)

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
| Phase 03.1 P01 | 251 | 2 tasks | 2 files |
| Phase 03.1-frontend-redesign P02 | 12 | 1 tasks | 1 files |
| Phase 03.1 P03 | 12 | 1 tasks | 1 files |
| Phase 03.2-uat-bug-fixes P01 | 25 | 1 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P02 | 20 | 2 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P03 | 8 | 1 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P05 | 15 | 2 tasks | 6 files |
| Phase 03.2-uat-bug-fixes P04 | 2 | 2 tasks | 6 files |
| Phase 03.2-uat-bug-fixes P06 | 3min | 2 tasks | 3 files |
| Phase 03.2-uat-bug-fixes P07 | 25min | 2 tasks | 4 files |
| Phase 04-payments-legal P01 | 10 | 2 tasks | 6 files |
| Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia P01 | 2 | 2 tasks | 2 files |

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
- [Phase 03.1]: Nav logo updated to NERVE teal (#2dd4a8) — aligns with new design system primary color, replacing old gold #E8B040
- [Phase 03.1]: Legacy CSS classes preserved in nerve.css alongside new .n-* classes — prevents visual regression on unmigrated child pages during phased rollout
- [Phase 03.1-frontend-redesign]: Gold #E8B040 fully replaced by teal #2dd4a8 in dashboard — no KI/AI-specific gold elements present in this page
- [Phase 03.1-frontend-redesign]: Quick action buttons use n-btn-ghost with border-radius:8px inline override — preserves rectangular list appearance while using NERVE component
- [Phase 03.1]: app.html kept as standalone page (not extending base.html) — live-session fullscreen UX requires own document structure
- [Phase 03.1]: n-ai-panel added to scroll#ai scroll container with border overrides — preserves JS scroll behavior while applying gold AI panel styling
- [Phase 03.2-uat-bug-fixes]: startFreizeichen made async to allow await freizCtx.resume() — browser autoplay policy requires explicit resume after AudioContext creation
- [Phase 03.2-uat-bug-fixes]: TTS autoplay errors surfaced to console.warn (not silenced) — silent catch hid critical failure mode in training TTS playback
- [Phase 03.2-uat-bug-fixes]: t-endBtn id added to Beenden button — explicit id more reliable than class-based querySelector
- [Phase 03.2-uat-bug-fixes]: Timer starts on socket.on('connect'), not first transcript — transcript handler retains guarded fallback
- [Phase 03.2-uat-bug-fixes]: No-conversation guard checks trainingSecs<10||userMsgCount===0 for training, sessionSeconds<10||words<20 for live
- [Phase 03.2-uat-bug-fixes]: Standalone Einstellungen sidebar link removed — now lives exclusively in the sidebar user dropdown (ARCH-16)
- [Phase 03.2-uat-bug-fixes]: Sidebar user dropdown opens upward (bottom: calc(100% + 4px)) to avoid viewport clipping at sidebar bottom edge
- [Phase 03.2-uat-bug-fixes]: preferred_language column defaults to 'de' — backward-compatible, existing users automatically get German as preference
- [Phase 03.2-uat-bug-fixes]: DOMContentLoaded calls selectLanguage() for non-default saved language to sync tUI and button states in training.html
- [Phase 03.2-uat-bug-fixes]: profile_wizard.html already uses neutral placeholders — no personal names found, no changes required (UAT-10)
- [Phase 03.2-uat-bug-fixes]: No-FOUC script placed before CSS link — runs synchronously, prevents flash of wrong theme
- [Phase 03.2-uat-bug-fixes]: Server-hint via data-server-theme on <html> tag from g.user.preferred_theme — DB value takes precedence over localStorage on authenticated pages
- [Phase 03.2-uat-bug-fixes]: preferred_theme defaults to 'dark' — backward-compatible, existing users stay on dark theme
- [Phase 03.2-uat-bug-fixes]: Loading overlay uses display:flex for centering; pcLoading declared before try block for cleanup in catch
- [Phase 03.2-uat-bug-fixes]: Kompakt mode changed to floating overlay — all body.kompakt hide rules removed, panel floats at bottom:16px right:16px without hiding main content
- [Phase 03.2-uat-bug-fixes]: All #E8B040 (gold) replaced with #2dd4a8 (teal) in landing.html including rgba() values
- [Phase 03.2-uat-bug-fixes]: DSGVO banner overlap fix via JS paddingBottom on .panel-sprachanalyse — CSS sibling selectors cannot reach across the DOM tree
- [Phase 03.2-uat-bug-fixes]: Custom scenario dropdown uses hidden <input id='t-scenarioSelect'> — all existing callers reading .value continue working unchanged
- [Phase 03.2-uat-bug-fixes]: window._pendingDeleteId bridges deleteScenario() modal show and confirmDeleteScenario() async execution
- [Phase 04-payments-legal]: Kein Audio wird jemals gespeichert — ephemeral processing only (Kernargument für Datenschutzerklärung)
- [Phase 04-payments-legal]: Live-Assistent Cold-Call-Modus = nur Berater-Audio, kein Kundentranksript, berechtigtes Interesse Art. 6 lit. f
- [Phase 04-payments-legal]: Live-Assistent Meeting-Modus = Consent-Pop-up vor Call, Ablehnung → Auto-Wechsel in Cold-Call
- [Phase 04-payments-legal]: KI-Trainingsdaten-Checkbox muss ENTKOPPELT von Training-Nutzung sein (Art. 7 Abs. 4 DSGVO Koppelungsverbot)
- [Phase 04-payments-legal]: Alle Dienste EU-Server: Deepgram api.eu.deepgram.com, Claude Bedrock Frankfurt, ElevenLabs EU Residency, Stripe Frankfurt
- [Phase 04-payments-legal]: Webhook uses raw request.data for Stripe signature verification — idempotent by stripe_event_id UNIQUE index
- [Phase 04-payments-legal]: checkout_success only flashes and redirects — subscription activation handled exclusively in webhook (D-12)
- [Phase 04-payments-legal]: stripe_customer_id stored on Organisation at checkout for reuse on subsequent Checkout Sessions (D-06)
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: PyAudio removed — VPS has no audio hardware, browser streams audio via Socket.IO audio_chunk events
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: Per-sid _deepgram_sessions dict used for isolated Deepgram connections per browser session
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: register_audio_handlers(sio) replaces background thread — events are client-driven via start_live_session/stop_live_session/audio_chunk/disconnect

### Roadmap Evolution

- Phase 03.1 inserted after Phase 03: Frontend Redesign (INSERTED) — app-page redesign before payments
- Phase 04.1 inserted after Phase 04: Live-Mikrofon Fix: PyAudio → Browser getUserMedia (URGENT) — Phase 4 paused (Gewerbeschein blocker), mic fix inserted as 4.1
- Phase 1 (Business Setup) removed from GSD tracking — user handles manually (Gewerbeanmeldung, Geschäftskonto, etc.)

### Pending Todos

- [ ] **Phase 3.1 gap closure**: 15 visual UAT issues from browser testing — run `/gsd:plan-phase 03.1 --gaps` to plan fixes
- [ ] **landing.html + login.html**: Not yet migrated to nerve.css — agreed to do after UAT
- [ ] **Phase 1 (manual)**: Gewerbeanmeldung, Geschäftskonto, USt-IdNr, Steuerberater — user handles independently, not tracked here
- [ ] After gap closure: plan Phase 4 (Payments & Legal)

### Blockers/Concerns

- **Phase 4 dependency**: Phase 4 (Stripe) needs verified Stripe account → requires Gewerbeanmeldung + Geschäftskonto (Phase 1 manual, ~3-5 weeks) — user is handling this in parallel
- Research flags: AVV signing portal locations for Deepgram/Anthropic/ElevenLabs should be verified directly. Stripe Tax / VAT invoice configuration for Germany needs explicit research during Phase 4 planning.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260401-qr4 | Fix sidebar user avatar visibility and light/dark mode toggle | 2026-04-01 | 972cd94 | [260401-qr4-fix-sidebar-user-avatar-visibility-and-l](./quick/260401-qr4-fix-sidebar-user-avatar-visibility-and-l/) |

## What's Done

| Phase | Plans | Status |
|-------|-------|--------|
| Phase 2: Product Fixes | 6/6 ✓ | Complete — all PROD requirements done |
| Phase 3: Infrastructure & Deployment | 3/3 ✓ | Complete — VPS live on getnerve.app (178.104.82.166), HTTPS, WAL, CORS locked |
| Phase 3.1: Frontend Redesign | 6/6 ✓ | Complete — nerve.css deployed, all app pages migrated. Visual UAT: 15 issues found. |
| Phase 1: Business Setup | — | Skipped from GSD — user handles manually |

**Phase 3 verification (manual):**

- App accessible at getnerve.app over HTTPS ✓
- VPS: Hetzner CX22, IP 178.104.82.166 ✓
- Remaining checks (Socket.IO 101, WAL mode, CORS lock): user to confirm on VPS

## Session Continuity

Last session: 2026-04-02T18:18:51.704Z
Stopped at: Completed 04.1-01-PLAN.md
Resume: `/gsd:execute-phase 4` — Stripe blocker overridden (account can be created before Gewerbeanmeldung)
