# Roadmap: NERVE — Milestone 1 (Launch)

## Overview

NERVE is at v0.9.4 with the core product fully built. Milestone 1 closes the gap from working prototype to first 50 paying customers. The path runs through five sequential phases: start the German business registration immediately (it takes 3-5 weeks regardless of technical progress), fix the product gaps that affect first-impression quality, deploy to production, wire up payments with legal compliance, and flip the Early Access switch. Business setup runs in parallel to technical work — both tracks must converge before the first customer can pay.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- ~~**Phase 1: Business Setup**~~ - *Skipped from GSD — user handles manually (Gewerbeanmeldung, Geschäftskonto, USt-IdNr, Steuerberater)*
- [x] **Phase 2: Product Fixes** - Complete all product gaps and polish before wiring payments
- [x] **Phase 3: Infrastructure & Deployment** - Deploy to Hetzner VPS with HTTPS — VPS live on getnerve.app ✓
- [x] **Phase 03.1: Frontend Redesign** - App-page redesign using NERVE Design System (INSERTED) (completed 2026-04-01)
- [x] **Phase 03.2: UAT Bug Fixes** - Fix 17 issues from Visual UAT: 6 critical bugs, 5 UX improvements, 4 design corrections, 2 architecture changes (Sidebar + Light/Dark) (INSERTED) (completed 2026-04-01)
- [ ] **Phase 4: Payments & Legal** - Stripe integration, pricing page, DSGVO legal pages and vendor DPAs
- [x] **Phase 04.1: Live-Mikrofon Fix** - Replace server-side PyAudio with browser getUserMedia + Socket.IO streaming (INSERTED)  (completed 2026-04-03)
- [x] **Phase 04.2: Cold Call und Meeting Modi** - Two distinct live session modes with DSGVO-compliant consent flow and EWB buttons (INSERTED) (completed 2026-04-03)
- [ ] **Phase 5: Launch** - Open Early Access to 50 paying customers

## Phase Details

### Phase 1: Business Setup
**Goal**: Legal entity is registered and capable of accepting payments
**Depends on**: Nothing (start immediately, runs in parallel with Phase 2)
**Requirements**: BIZ-01, BIZ-02, BIZ-03, BIZ-04
**Success Criteria** (what must be TRUE):
  1. Gewerbeanmeldung is submitted at Gewerbeamt Iserlohn
  2. Business bank account (Kontist or Finom) is open and accessible
  3. USt-IdNr application is filed with Bundeszentralamt
  4. First meeting with count.tax is scheduled (tax advice is in place for invoicing)
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Legal registration: Gewerbeanmeldung (BIZ-01) + USt-IdNr application (BIZ-03)
- [ ] 01-02-PLAN.md — Financial setup: Kontist Geschaeftskonto (BIZ-02) + Stripe account creation
- [ ] 01-03-PLAN.md — Tax advisor: count.tax first call scheduled and completed (BIZ-04)

### Phase 2: Product Fixes
**Goal**: The product is polished and complete — ready for a paying customer's first impression
**Depends on**: Nothing (runs in parallel with Phase 1)
**Requirements**: PROD-01, PROD-02, PROD-03, PROD-04, PROD-05, PROD-06, PROD-07, PROD-08, PROD-09, PROD-10, PROD-11
**Success Criteria** (what must be TRUE):
  1. A new user completes the 3-step profile wizard on first login and gets a profile with generic, non-demo content
  2. The Live-Modus shows the DSGVO banner before microphone access, the correct script button, working compact-mode circles, and the toggle in the right position
  3. A user can choose between "Frei" (max points, no hints) and "Geführt" (hints with point deduction) training modes and select from 11 standard DACH scenarios
  4. After completing a training session, the user sees a preview of what NERVE would have shown in a real call
  5. All "SalesNerve" references in code and UI are replaced with "NERVE"
**Plans**: 6 plans
**UI hint**: yes

Plans:
- [x] 02-01-PLAN.md — SalesNerve to NERVE rename across codebase and DB migration (PROD-11)
- [x] 02-02-PLAN.md — Live-mode bug fixes: DSGVO banner, script button, compact circles, toggle (PROD-07)
- [x] 02-03-PLAN.md — Training modes and scenarios verification (PROD-03, PROD-04, PROD-05, PROD-06)
- [x] 02-04-PLAN.md — Pricing model rewrite to flat-rate + fair-use tracking + ROI fix (PROD-01, PROD-02)
- [x] 02-05-PLAN.md — Onboarding improvements + profile editor placeholders (PROD-08, PROD-10)
- [x] 02-06-PLAN.md — Profile wizard: 3-step guided profile creation for new users (PROD-09)

### Phase 3: Infrastructure & Deployment
**Goal**: The app is running on the production domain over HTTPS with WebSockets confirmed working
**Depends on**: Phase 2
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, LEGAL-04
**Success Criteria** (what must be TRUE):
  1. The app is accessible at the production domain over HTTPS with a valid Let's Encrypt certificate
  2. A live Socket.IO connection shows `101 Switching Protocols` in the browser network tab — no polling fallback
  3. The app starts cleanly on the VPS without PyAudio or missing SECRET_KEY (fail-fast assertion triggers on bad config)
  4. SQLite WAL mode is confirmed active; CORS is locked to the production domain only (no wildcard)
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Code hardening: requirements split, SECRET_KEY fail-fast, SQLite WAL, CORS lock (INFRA-04, INFRA-05, LEGAL-04)
- [x] 03-02-PLAN.md — Deployment artifacts: deploy.sh, nginx.conf, nerve.service (INFRA-01, INFRA-02, INFRA-03)
- [x] 03-03-PLAN.md — VPS deployment runbook: provision, SSL, systemd, end-to-end verification — DONE (getnerve.app live)

### Phase 03.1: Frontend Redesign (INSERTED)

**Goal**: All app pages use the NERVE Design System — consistent glass panels, typography, color tokens, and component language across Dashboard, Live-Session, Training, Profil, Wizard, Analysis, and Sessions. Landing page excluded.
**Requirements**: UI-01 through UI-07 (one per page)
**Depends on**: Phase 3
**Stack constraint**: No framework change — pure CSS with Custom Properties. Design system reference: `NERVE-Design-System.html`
**Plans**: 6 plans

Plans:
- [x] 03.1-01-PLAN.md — CSS foundation: create static/nerve.css + update base.html (UI-01)
- [x] 03.1-02-PLAN.md — Dashboard redesign: glass panels, KPI cards, feed items (UI-02)
- [x] 03.1-03-PLAN.md — Live-Session redesign: NERVE tokens, AI panel, live badge (UI-03)
- [x] 03.1-04-PLAN.md — Training redesign: glass cards, pill tabs, teal accents (UI-04)
- [x] 03.1-05-PLAN.md — Profile pages: editor + list with glass panels, NERVE inputs (UI-05, UI-06)
- [x] 03.1-06-PLAN.md — Wizard + Onboarding: teal tokens, NERVE inputs (UI-07)

### Phase 03.2: UAT Bug Fixes (INSERTED)

**Goal**: All 17 UAT issues from Visual UAT after Phase 3.1 are resolved — 6 critical bugs fixed, 5 UX improvements implemented, 4 design corrections applied, 2 architecture changes shipped (Sidebar user menu + Light/Dark Mode). App is fully functional and polished on getnerve.app.
**Depends on**: Phase 03.1
**Requirements**: UAT-01 through UAT-16
**Success Criteria** (what must be TRUE):
  1. Training sessions can be started and run end-to-end (Anruf-Button works, AI responds, TTS plays)
  2. Microphone works in both /training and /live — browser requests permission, Deepgram receives audio
  3. Language selection in /training applies consistently to all UI text
  4. Live session timer counts up from session start; mic button is functional
  5. Auswertung shows placeholder message (not fake coaching) when no real conversation occurred
  6. Language preference is saved globally in /settings and applied across all pages
  7. Auswertung loading state shows animated progress bar
  8. Kompaktmodus in /live opens as floating popup overlay
  9. "Zurück zum Dashboard" button visible at end of live Auswertung
  10. Profile fields show neutral placeholder examples
  11. All yellow/purple accent colors replaced with Teal (#2dd4a8) except Gold (#d4a853) for AI elements
  12. Scenario dropdown in /training uses dark theme styling
  13. DSGVO banner does not overlap emotion analysis circles in /live
  14. Training end dialog is a styled NERVE modal, not browser window.confirm
  15. User avatar + name visible bottom-left in sidebar; click opens dropdown with Profile, Settings, Billing, Team, Logout
  16. Light/Dark Mode toggle works in Settings and sidebar dropdown; system preference applied on first visit
**Plans**: 7 plans

Plans:
- [x] 03.2-01-PLAN.md — Critical bugs: training flow — Anruf-Button, PTT mic, TTS audio (UAT-01, UAT-02)
- [x] 03.2-02-PLAN.md — Critical bugs: language switch, live timer, no-conversation guard (UAT-03, UAT-04, UAT-05)
- [x] 03.2-03-PLAN.md — Architecture: sidebar user menu with avatar + dropdown (UAT-15)
- [x] 03.2-04-PLAN.md — Architecture: Light/Dark Mode toggle with system preference (UAT-16)
- [x] 03.2-05-PLAN.md — UX: global language preference + profile wizard placeholders (UAT-06, UAT-10)
- [x] 03.2-06-PLAN.md — UX: loading state, compact overlay, Dashboard back button (UAT-07, UAT-08, UAT-09)
- [ ] 03.2-07-PLAN.md — Design: landing colors, custom dropdown, DSGVO overlap, NERVE modals (UAT-11, UAT-12, UAT-13, UAT-14)

### Phase 4: Payments & Legal
**Goal**: Users can pay for a subscription and the product is legally compliant for DACH B2B launch
**Depends on**: Phase 3 (needs HTTPS for Stripe webhooks), Phase 1 (needs verified Stripe account)
**Requirements**: PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-06, LEGAL-01, LEGAL-02, LEGAL-03
**Success Criteria** (what must be TRUE):
  1. A user can select a plan on the pricing page and complete payment via Stripe Checkout; subscription activates via webhook only (not redirect)
  2. A user can manage or cancel their subscription via the Stripe Customer Portal linked from account settings
  3. The dashboard ROI tracker and fair-use counter update correctly; at ~80% limit a soft warning appears; no hard block occurs
  4. Impressum, AGB, and Datenschutzerklärung are live at the production domain, listing Deepgram, Anthropic, ElevenLabs, and Stripe as Auftragsverarbeiter
  5. Signed AVVs with Deepgram, Anthropic, ElevenLabs, and Stripe are on file; Deepgram EU endpoint is in use
**Plans**: 3 plans
**UI hint**: yes

Plans:
- [x] 04-01-PLAN.md — Stripe foundation: DB migration, config, payments blueprint (Checkout, Webhook, Portal) (PAY-01, PAY-02, PAY-03, PAY-04)
- [ ] 04-02-PLAN.md — Pricing page + fair-use metering with soft warnings (PAY-05, PAY-06)
- [ ] 04-03-PLAN.md — Legal pages (Impressum, AGB, Datenschutz) + Deepgram EU + AVV checklist (LEGAL-01, LEGAL-02, LEGAL-03)

### Phase 04.1: Live-Mikrofon Fix: PyAudio -> Browser getUserMedia (INSERTED)

**Goal:** Replace server-side PyAudio mic capture with browser-side getUserMedia + Socket.IO streaming so live transcription works on the VPS (no audio hardware)
**Requirements**: MIC-01, MIC-02, MIC-03, MIC-04
**Depends on:** Phase 4
**Success Criteria** (what must be TRUE):
  1. Server starts without PyAudio — no `import pyaudio` in production code
  2. Each Socket.IO session gets its own Deepgram WebSocket connection (per-session, not global)
  3. Browser captures mic audio via getUserMedia + AudioWorklet at 16kHz, streams Int16 PCM via Socket.IO
  4. Live transcription works end-to-end on getnerve.app: speak into browser mic, see transcripts in UI
**Plans:** 3/3 plans complete

Plans:
- [x] 04.1-01-PLAN.md — Server: per-session Deepgram connections + remove global PyAudio startup (MIC-01, MIC-02)
- [x] 04.1-02-PLAN.md — Client: AudioWorklet processor + getUserMedia + Socket.IO streaming lifecycle (MIC-03, MIC-04)
- [x] 04.1-03-PLAN.md — Gap closure: fix AudioContext suspension + diagnostic logging (MIC-04)

### Phase 04.2: Cold Call und Meeting Modi (INSERTED)

**Goal:** Two distinct live session modes on /live — Cold Call (consultant audio only, single-speaker Deepgram, EWB buttons) and Meeting (full diarization with consent pop-up, auto-fallback to Cold Call on rejection). Mode selected before session start, persisted in ConversationLog for post-call analytics.
**Requirements**: MODE-01, MODE-02, MODE-03, MODE-04, MODE-05, MODE-06
**Depends on:** Phase 04.1
**Success Criteria** (what must be TRUE):
  1. User selects Cold Call or Meeting mode via pre-session overlay on /live before any Deepgram connection opens
  2. Cold Call uses Deepgram single-speaker (diarize=false) — no customer audio processed or stored
  3. Meeting shows consent pop-up with Vorleseskript; accepted starts full diarization, rejected silently falls back to Cold Call
  4. EWB buttons (from profile or DACH fallback list) trigger instant Claude Haiku responses with objection-specific context
  5. Active mode displayed as badge in /live header; session_mode persisted in ConversationLog
**Plans:** 4/4 plans complete

Plans:
- [x] 04.2-01-PLAN.md — Backend: DB migration (session_mode), mode-aware Deepgram, EWB trigger endpoint (MODE-02, MODE-04, MODE-05, MODE-06)
- [x] 04.2-02-PLAN.md — Frontend: mode overlay, consent modal, EWB buttons, mode badge, JS wiring (MODE-01, MODE-03, MODE-04, MODE-05)

### Phase 5: Launch
**Goal**: 50 Early Access slots are live and waitlist members can become paying customers
**Depends on**: Phase 4
**Requirements**: LAUNCH-01
**Success Criteria** (what must be TRUE):
  1. Early Access page is live with 50 slots at 50% Gruender-Rabatt and a clear CTA
  2. Waitlist members receive a notification (email or in-app) that Early Access is open
  3. At least one user completes the full flow: pricing page -> Stripe Checkout -> subscription active -> dashboard visible
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Business Setup | — | Skipped (manual) | — |
| 2. Product Fixes | 6/6 ✓ | Complete | 2026-04-01 |
| 3. Infrastructure & Deployment | 2/3 | In Progress|  |
| 3.1 Frontend Redesign | 6/6 ✓ | Complete | 2026-04-01 |
| 3.2 UAT Bug Fixes | 5/7 | In Progress|  |
| 4. Payments & Legal | 1/3 | In Progress|  |
| 4.1 Live-Mikrofon Fix | 3/3 ✓ | Complete | 2026-04-03 |
| 4.2 Cold Call und Meeting Modi | 4/4 | Complete   | 2026-04-03 |
| 5. Launch | 0/? | Not started | - |

---
*Roadmap created: 2026-03-30*
*Milestone: NERVE Launch — v0.9.4 to first 50 paying customers*
