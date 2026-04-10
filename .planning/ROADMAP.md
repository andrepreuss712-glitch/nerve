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
- [x] **Phase 04.3: Design Unification** - Light/Dark Mode entfernen, einheitliches dunkles Theme, Beenden-Button Fix, UI-Elemente konsolidieren (INSERTED) (completed 2026-04-04)
- [ ] **Phase 04.5: Training Analytics & Tools** - Analytics-Panel mit Stats, Heatmap, Phrasen-Bank, Wochenziel, Quick-Training (INSERTED)
- [ ] **Phase 04.6: Sales Performance Calculator** - Interaktiver ROI-Rechner im Dashboard: echte Call-Daten + Simulations-Schieberegler, KPI-Karten, Charts, Umsatz-Forecast (INSERTED)
- [x] **Phase 04.6.1: Auth-Upgrade Google + Microsoft OAuth Login** - OAuth-Login via authlib, nullable passwort_hash, Login-UI Buttons (INSERTED) (completed 2026-04-06)
 (completed 2026-04-07)
- [x] **Phase 04.6.2: Deploy Hardening & OAuth Polish** - Urgent: deploy hardening and oauth polish (INSERTED) (completed 2026-04-07)
- [x] **Phase 04.7: Backend & Feedback System** - Admin-Dashboard, Feedback-System, Audit-Log, transaktionale Emails (Resend/Postmark), Session-History (INSERTED) (completed 2026-04-08)
- [ ] **Phase 04.7.1: FineTuning Logging Grundlage** - ft_call_sessions, ft_assistant_events, ft_objection_events, prompt_versions Tabellen von Tag 1 (INSERTED)
- [ ] **Phase 04.7.2: Founder Cost Dashboard** - Einnahmen, Ausgaben, Kunden-Profitabilität, EÜR, Export für count.tax, API-Preismonitor (INSERTED)
- [ ] **Phase 04.8: KI-Logik Upgrade** - Gesprächsphasen-Erkennung (6 Phasen), Kaufbereitschafts-Score (0-100%), Hinweis-Priorisierung, Cold Call Inferenz, dynamische EWB-Buttons (INSERTED)
- [x] **Phase 04.9: Training-Modul Upgrade** - 6 Persönlichkeitstypen, Stimmungs-Dynamik (-5 bis +5), Auflege-Logik, Szenarien pro Branche, 3 Schwierigkeitsgrade (INSERTED) (completed 2026-04-10)
- [ ] **Phase 04.10: Training Realismus** - Sekretärin/Chef 2-Stimmen Modus, Freizeichen/Klingeln/Besetztzeichen Audio-Simulation, Auflegen-Flow mit Pop-up und Scoring (INSERTED)
- [ ] **Phase 04.11: Coach-Modul** - Post-Call Lernkarten (max 3/Call, max 5 aktiv), KI-Gedächtnis im Call (goldener Rahmen), Wöchentlicher Coach-Report, Langzeit-Fortschritt (INSERTED)
- [ ] **Phase 04.12: Gesamt-Integration** - learning_events Tabelle, Modul-Verbindungen (Training↔Call↔Coach↔Bewertungen), Selbstverbesserungs-Kreislauf, Netzwerkeffekt (INSERTED)
- [ ] **Phase 04.13: PreCall Intelligence** - Automatische Firmen-Recherche vor dem Call, Call-Briefing im PIP, Datenquellen-Ansatz wird in Phase geklärt (INSERTED)
- [ ] **Phase 04.14: CRM & Customer Success** - Status-Badges (Aktiv/Ruhig/Churn-Risiko/Top), CRM-Notizen, Follow-Up System mit automatischen Vorschlägen, Metriken (INSERTED)
- [ ] **Phase 04.15: Rollen, Support & Kompensation** - Granulares Rollen-System (superadmin/support/billing/analyst), DSGVO-konformer Support-Zugriff, Kompensation bei Ausfällen (INSERTED)
- [ ] **Phase 04.16: Finaler Polish + UAT** - Finaler UAT-Durchlauf, Design-Pass, CSS Refactoring, Code Audit, Performance-Check (INSERTED)
- [ ] **Phase 04.17: PiP Launcher** - Always-on-Top verschiebbarer Live-Assistent via Document Picture-in-Picture API, Call-Start aus CRM heraus, Modus/Kunden/Skript-Auswahl im PiP (INSERTED)
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

### Phase 04.6.2: deploy hardening and oauth polish (INSERTED)

**Goal:** Deploy-Pipeline härten (rsync mit DB-Schutz) und verbleibende OAuth-Rough-Edges aus 04.6.1 glätten (Landing-Link, MS-Branding, Consumer-Account-Block, Silent-SSO, Onboarding-Render-Bug)
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06
**Depends on:** Phase 04.6.1
**Plans:** 2/4 plans executed

Plans:
- [x] 04.6.2-01-PLAN.md — Deploy-Hardening: deploy.sh auf tar-over-ssh (Windows-kompat) mit Excludes und Prod-DB-Schutz (D-01)
- [x] 04.6.2-02-PLAN.md — Landing & Branding: Header-Login → app.getnerve.app, Microsoft 365 Button-Labels (D-02, D-03)
- [x] 04.6.2-03-PLAN.md — OAuth Flow Polish: Consumer-Tenant-Block verifizieren + conditional prompt=consent (D-04, D-06)
- [x] 04.6.2-04-PLAN.md — Onboarding-Bug Fix: diagnostisches Logging + Cache-Control no-store (Root-Cause: pre-existing user, Hypothesis E) (D-05)

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

### Phase 04.2.1: UI/UX Overhaul — Dashboard, Live-Assistent, Kompaktmodus. Komplettes Layout überarbeiten, Getclose.ai als Design-Referenz, Picture-in-Picture Overlay, intuitive Anordnung aller Elemente. (INSERTED)

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 4.2
**Plans:** 2/5 plans executed

Plans:
- [ ] TBD (run /gsd:plan-phase 04.2.1 to break down)

### Phase 04.3: Design Unification (INSERTED)

**Goal:** Einheitliches dunkles Theme auf allen Seiten — Light/Dark Mode komplett entfernt, konsistentes Farbschema (#0D1117 Page BG / #1C2333 Cards / #00D4AA Teal Akzent), kritischer Beenden-Button Fix, UI-Elemente (Footer, Header, Sprachauswahl) umgezogen.
**Depends on**: Phase 04.2
**Requirements**: DU-01, DU-02, DU-03, DU-04, DU-05, DU-06, DU-07, DU-08, DU-09, DU-10, DU-11, DU-12
**Success Criteria** (what must be TRUE):
  1. Beenden-Button in `/live` navigiert zurück zum Dashboard
  2. Kein `prefers-color-scheme` Media Query und kein Theme-Toggle mehr im Codebase
  3. Alle 8 App-Bereiche (Dashboard, Training, Live, Analytics, Profil, Profil-Editor, Einstellungen, Hilfe-Center) zeigen identisches dunkles Farbschema
  4. Footer-Links, Header-Email/Logout und Sprach-Buttons aus den Seiten entfernt und in Einstellungen verschoben
  5. Settings-Button in Sidebar an gleicher Position auf allen Seiten
**UI hint**: yes
**Plans**: 6 plans

Plans:
- [x] 04.3-01-PLAN.md — Beenden-Button Fix: Dashboard back-link in app.html header (DU-01)
- [x] 04.3-02-PLAN.md — Light Mode entfernen + Dark Theme CSS-Variablen auf Zielwerte setzen (DU-02, DU-03)
- [x] 04.3-03-PLAN.md — Einstellungen + Analytics Dark Theme Fixes (DU-04, DU-05)
- [x] 04.3-04-PLAN.md — Training + Profil-Editor + Hilfe-Center Dark Theme (DU-06, DU-07, DU-08)
- [x] 04.3-05-PLAN.md — Footer-Links entfernen + Header aufräumen + Rechtliches Tab (DU-09, DU-10)
- [x] 04.3-06-PLAN.md — Sprachauswahl aus Training + Settings-Button Fix + Dark Theme Sweep (DU-11, DU-12, DU-03)

### Phase 04.5: Training Analytics & Tools (INSERTED)

**Goal**: Die Training-Seite zeigt rechts neben den Einstellungen sinnvolle Statistiken (Fortschritt, Einwand-Heatmap, Stärken/Schwächen, Verbesserungskurve) und intelligente Tools (KI-Empfehlung, Quick-Training, Phrasen-Bank, Wochenziel, Letzte Session) — der leere Platz ist vollständig genutzt.
**Depends on**: Phase 04.3 (Training-Seite Layout + Light Content Design)
**Requirements**: TA-01, TA-02, TA-03, TA-04, TA-05, TA-06, TA-07, TA-08, TA-09
**Success Criteria** (what must be TRUE):
  1. `GET /api/training/stats` liefert Sessions, Dauer, Streak, Heatmap-Daten für den eingeloggten User
  2. `GET /api/training/recommendation` liefert eine regelbasierte KI-Empfehlung basierend auf Schwächen
  3. Einwand-Heatmap zeigt alle 7 Einwand-Typen als farbige Kacheln (grün/gelb/rot nach Erfolgsquote)
  4. Klick auf Heatmap-Kachel startet Quick-Training mit diesem Einwand-Typ
  5. Phrasen-Bank zeigt Wendepunkt-Sätze aus Post-Call Analysen, filterbar nach Einwand-Typ
  6. Wochenziel-Card: User kann Ziel setzen, Fortschrittsbalken und Streak werden korrekt berechnet
  7. Letzte Session Card zeigt kompakte Zusammenfassung der letzten Trainings-Session
  8. Alle neuen Cards verwenden exakt die Design-Spezifikation (#FFFFFF Card BG, 12px radius, teal #00D4AA Akzente)
  9. Keine neuen Farben außerhalb der definierten Palette, keine Gradient-Backgrounds, Sidebar unverändert
**UI hint**: yes
**Plans**: 4 plans

Plans:
- [x] 04.5-01-PLAN.md — DB-Schema + ConversationLog-Persistenz fuer Training-Sessions (TA-01, TA-05)
- [x] 04.5-02-PLAN.md — 5 neue API-Endpoints: stats, recommendation, phrases, goal, last-session (TA-01, TA-02, TA-05, TA-06, TA-07)
- [x] 04.5-03-PLAN.md — Frontend Analytics Panel: 7 Cards + Chart.js + CSS + JS Fetch (TA-01, TA-03, TA-05, TA-06, TA-07, TA-08, TA-09)
- [ ] 04.5-04-PLAN.md — Quick-Training Flow + Visual Verification Checkpoint (TA-04, TA-08, TA-09)

### Phase 04.6: Sales Performance Calculator (INSERTED)

**Goal**: Der User sieht im Dashboard auf einen Blick was NERVE ihm finanziell bringt — echte Call-Daten kombiniert mit einem interaktiven Simulations-Rechner. Rechtfertigt den Preis (99€/Mo) mit harten Zahlen und macht das Dashboard zum täglichen Anlaufpunkt.
**Depends on**: Phase 04.3 (Light Content Design), Phase 04.5 (ConversationLog-Persistenz)
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06
**Success Criteria** (what must be TRUE):
  1. `GET /api/performance` liefert echte Metriken: Calls/Woche, Closing-Rate, Einwand-Erfolgsquote, Umsatz-Forecast
  2. Dashboard zeigt KPI-Karten (Deals, Umsatz, Wachstum %, ROI) mit echten User-Daten
  3. Balkendiagramm zeigt Call-Aktivität pro Woche/Monat (Chart.js)
  4. Wachstumskurve zeigt Umsatz-Forecast über 3/6/12 Monate (S-Kurve, Chart.js)
  5. Simulations-Modus: 5 Schieberegler (Calls/Tag, Show-Rate, Closing-Rate, Deal-Wert, Arbeitstage) berechnen live Umsatz-Szenarien
  6. ROI-Berechnung: "NERVE kostet 99€ und bringt dir X.XXX€ mehr" — basierend auf Einwand-Verbesserung
  7. Design exakt nach Spezifikation: #FFFFFF Cards, 12px Radius, #00D4AA Teal, DM Sans, keine eigenen Farben
**UI hint**: yes
**Plans**: 4 plans

Plans:
- [x] 04.6-01-PLAN.md — DB-Migration (result + avg_deal_wert) + performance Blueprint + 3 API-Endpoints (PERF-01, PERF-02)
- [x] 04.6-02-PLAN.md — Dashboard HTML: Sales Performance Sektion + KPI-Karten + Charts + Slider + Modal (PERF-03, PERF-04, PERF-05, PERF-06)
- [x] 04.6-03-PLAN.md — CSS Slider-Styling + vollstaendiges JavaScript (Chart.js + Simulation + Modal + Tagging) (PERF-03, PERF-04, PERF-05, PERF-06)
- [ ] 04.6-04-PLAN.md — End-to-End visuelle Verifikation + Checkpoint (PERF-01 bis PERF-06)

### Phase 04.6.1: Auth-Upgrade Google + Microsoft OAuth Login (INSERTED)

**Goal:** User können sich mit Google- oder Microsoft-Account einloggen. Bestehende Email/Passwort-Auth bleibt erhalten. Email-Match verhindert Duplikat-Accounts. Login-Modal auf Landing Page bekommt OAuth-Buttons.
**Requirements**: AUTH-OAUTH-01, AUTH-OAUTH-02, AUTH-OAUTH-03, AUTH-OAUTH-04, AUTH-OAUTH-05, AUTH-OAUTH-06
**Depends on:** Phase 4.6
**Plans:** 3/3 plans complete

Plans:
- [x] 04.6.1-01-PLAN.md — DB-Migration (oauth_provider/oauth_id/avatar_url, passwort_hash nullable) + Auth-Refactor (_login_user, _create_org_and_user)
- [x] 04.6.1-02-PLAN.md — routes/oauth.py Blueprint (Google + Microsoft via authlib) + app.py Integration + ProxyFix
- [x] 04.6.1-03-PLAN.md — Landing-Modal UI (Google + Microsoft Buttons, Trennlinie, oauth_error-Anzeige) + Visual Checkpoint

### Phase 04.7: Backend & Feedback System (INSERTED)

**Goal:** Admin-Dashboard, Feedback-System, Audit-Log, transaktionale Emails und Session-History stehen - Grundlage fuer alle folgenden Phasen.
**Depends on:** Phase 04.6.1
**Briefing:** Nerve-Vault/02 Projekte/NERVE Backend & Feedback System.md
**Requirements:** [BE-01, BE-02, BE-03, BE-04, BE-05, BE-06, BE-07, BE-08]
**Plans:** 6/6 plans complete

Plans:
- [x] 04.7-01-PLAN.md - Foundation: is_superadmin + Decorator + ENV-Seed + Flask-Admin /admin Mount
- [x] 04.7-02-PLAN.md - Audit-Log Tabelle + Immutable Trigger + log_action Wire-up
- [x] 04.7-03-PLAN.md - Daten-Tracking: ObjectionEvent Tabelle + EWB-Persistenz (avg_deal_wert reuse)
- [x] 04.7-04-PLAN.md - Feedback-Buttons + Modal + Upload + API + feedback Tabelle
- [x] 04.7-05-PLAN.md - Admin-Dashboard KPI + Tickets + Planung + Resend EU Emails + Checkpoint
- [x] 04.7-06-PLAN.md - Session-History (Analytics-Umbau zu ConversationLog-Liste + Detail)

### Phase 04.7.1: FineTuning Logging Grundlage (INSERTED)

**Goal:** Strukturierte Logging-Tabellen fuer Fine-Tuning Trainingsdaten von Tag 1 — ft_call_sessions, ft_assistant_events, ft_objection_events, prompt_versions. Markt-Trennung DACH/US, synchroner Write-Path im Live-Assistent, Prompt-Versionierung, Cold-Call DSGVO NULL-Enforcement, JSONL-Export-Stub.
**Depends on:** Phase 04.7
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE FineTuning Logging Architektur.md`
**Plans:** 5 plans

Plans:
- [ ] 04.7.1-01-PLAN.md — pytest Setup + tests/conftest.py + Test-Scaffolds (Wave 0)
- [ ] 04.7.1-02-PLAN.md — SQLAlchemy Models (FtCallSession/FtAssistantEvent/FtObjectionEvent/PromptVersion) + users/conversation_logs market+language ALTER (Wave 1)
- [ ] 04.7.1-03-PLAN.md — Prompt-Seed fuer alle 6 Module + get_active_prompt_version Cache-Helper (Wave 2)
- [ ] 04.7.1-04-PLAN.md — Write-Hooks analyse_loop + coaching_loop -> ft_assistant_events mit Cold-Call NULL-Enforcement (Wave 2)
- [ ] 04.7.1-05-PLAN.md — Lifecycle Hooks: start_live_session INSERT, api_ewb_trigger -> ft_objection_events, api_beenden UPDATE + JSONL-Export-CLI-Stub (Wave 2)

### Phase 04.7.2: Founder Cost Dashboard (INSERTED)

**Goal:** André sieht auf einen Blick wie sein Business steht — 6 Tabs (Übersicht, Einnahmen, Ausgaben, Kunden-Profitabilität, EÜR, Export). Am Monatsende: Klick auf Export → count.tax bekommt alles fertig aufbereitet.
**Depends on:** Phase 04.7
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Admin Dashboard Final.md`
**Plans:** 7 plans in 6 waves
- [ ] 04.7.2-01-PLAN.md — DB Models + Migration + Seed + Test-Skeletons (Wave 1)
- [ ] 04.7.2-02-PLAN.md — services/cost_tracker.py + Hooks in claude/deepgram/training_service (Wave 2)
- [ ] 04.7.2-03-PLAN.md — Frankfurter exchange_rates + APScheduler + Stripe invoice.payment_succeeded Webhook (Wave 2)
- [ ] 04.7.2-04-PLAN.md — admin_dashboard Blueprint + Shell + Tab Übersicht + Tab Einnahmen (Wave 3)
- [ ] 04.7.2-05-PLAN.md — Tab Ausgaben (CRUD FixedCost + ApiRate) + Tab Kunden (Org+User-Drilldown) (Wave 4)
- [ ] 04.7.2-06-PLAN.md — services/eur_calculator.py + §13b TDD + Tab EÜR (Wave 5)
- [ ] 04.7.2-07-PLAN.md — WeasyPrint EÜR-PDF + 4 CSV-Exports + Tab Export (Wave 6)

### Phase 04.8: KI-Logik Upgrade (INSERTED)

**Goal:** Kernarchitektur für intelligente Hinweise — automatische Gesprächsphasen-Erkennung (6 Phasen), Live-Kaufbereitschafts-Score (0-100%), Hinweis-Priorisierung (nie mehr als einer gleichzeitig), Cold Call Inferenz aus Vertriebler-Aussagen, dynamische EWB-Buttons pro Phase.
**Depends on:** Phase 04.7.1
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE KI-Logik Kernarchitektur.md`
**Plans:** TBD

### Phase 04.8.1: Echtzeit-Engine Rebuild — Async FastAPI WebSocket Engine, Redis Bridge, STT/LLM Abstraktionsschicht, Polling ersetzen (INSERTED)

**Goal:** Async FastAPI+uvicorn WebSocket Engine als eigener Service, Redis Bridge zu Flask, STT/LLM Abstraktionsschicht, HTTP-Polling durch WebSocket-Push ersetzen. Fundament fuer eigene KI, eigene STT, Skalierung.
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09
**Depends on:** Phase 04.8
**Plans:** 5/5 plans complete

Plans:
- [x] 04.8.1-01-PLAN.md — FastAPI skeleton, config, Redis bridge, Pydantic models (D-01, D-02)
- [x] 04.8.1-02-PLAN.md — STTProvider ABC + DeepgramAdapter asyncwebsocket (D-03, D-09)
- [x] 04.8.1-03-PLAN.md — LLMProvider ABC + ClaudeAdapter async + ShadowLogger (D-04, D-05, D-09)
- [x] 04.8.1-04-PLAN.md — SessionManager + WebSocket router, wire STT+LLM+push (D-06, D-07)
- [x] 04.8.1-05-PLAN.md — Flask token bridge, frontend WS client, systemd+nginx deploy (D-06, D-07, D-08)

### Phase 04.9: Training-Modul Upgrade (INSERTED)

**Goal:** Training gegen lebendige KI-Persönlichkeiten — 6 Typen (Beschäftigter Chef, Skeptiker, Analytiker, Freundlicher Ja-Sager, Aggressiver, Entscheider), dynamische Stimmung (-5 bis +5), echte Auflege-Logik, Szenarien pro Branche, 3 Schwierigkeitsgrade.
**Depends on:** Phase 04.8
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Training-Modul.md`
**Requirements:** D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16, D-17
**Plans:** 5/5 plans complete

Plans:
- [x] 04.9-01-PLAN.md — DB foundation: PersonalityType model, 6 system types seed, ConversationLog extension, system scenarios, difficulty labels (D-01, D-03, D-04, D-11)
- [x] 04.9-02-PLAN.md — AI logic: build_personality_prompt() + generate_response_with_mood() with mood tracking and auflege rules (D-08, D-10)
- [x] 04.9-03-PLAN.md — Backend API: personality endpoints (list/generate/save), training start/respond/end wiring, scenario list fix (D-02, D-03, D-05, D-06, D-13)
- [x] 04.9-04-PLAN.md — Frontend setup + chat: personality type cards, scenario step, mood indicator, hangup UX, save prompt (D-02, D-05, D-06, D-07, D-09, D-12, D-13)
- [x] 04.9-05-PLAN.md — Scoring upgrade: 6th category Beziehungsaufbau, mood curve Chart.js, Wendepunkt-Analyse, basis points + visual checkpoint (D-14, D-15, D-16, D-17)

### Phase 04.10: Training Realismus (INSERTED)

**Goal:** Sekretärin + Chef Modus mit 2 Stimmen, echte Audio-Simulation (Freizeichen, Klingeln, Besetztzeichen), Auflegen-Flow mit Besetztzeichen → Pop-up → Scoring.
**Depends on:** Phase 04.9
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Training Realismus Regeln.md`
**Plans:** 1/3 plans executed

Plans:
- [x] 04.10-01-PLAN.md -- Backend: 3 Sekretaerin-Typen, anruf_typ-Logik, Audio-Pfade, Hangup-Metadaten
- [ ] 04.10-02-PLAN.md -- Frontend: Audio-Manager, Transfer-Sequenz, Hangup-Popup, Auflegen-Button
- [ ] 04.10-03-PLAN.md -- Setup-Flow linear, Anruf-Typ Step, Profil-Modal, Szenario-Karten Glass-Design

### Phase 04.11: Coach-Modul (INSERTED)

**Goal:** Persönliches Lernsystem — Post-Call Analyse mit max 3 konkreten Lernkarten-Vorschlägen, max 5 aktive Lernkarten, KI-Gedächtnis im nächsten Call (goldener Rahmen bei passender Situation), Wöchentlicher Coach-Report, Langzeit-Fortschritt über 4-12 Wochen.
**Depends on:** Phase 04.8, Phase 04.9
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Coach-Modul.md`
**Plans:** TBD

### Phase 04.12: Gesamt-Integration (INSERTED)

**Goal:** Alle Module zu einem geschlossenen Lernökosystem verbinden — learning_events Tabelle, 5 Modul-Verbindungen (Training↔Call↔Coach↔Bewertungen↔EWB), Selbstverbesserungs-Kreislauf, Netzwerkeffekt durch aggregierte anonymisierte Daten.
**Depends on:** Phase 04.11
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Gesamt-Architektur.md`
**Plans:** TBD

### Phase 04.13: PreCall Intelligence (INSERTED)

**Goal:** Automatische Firmen-Recherche vor dem Call — Vertriebler gibt Firmenname + Ansprechpartner ein, NERVE erstellt kompaktes Call-Briefing in ~30 Sekunden, Briefing erscheint im PIP. Datenquellen-Ansatz wird beim Start der Phase gemeinsam festgelegt.
**Depends on:** Phase 04.8
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Phase 5.1 PreCall Intelligence.md`
**Plans:** TBD

### Phase 04.14: CRM & Customer Success (INSERTED)

**Goal:** Internes CRM mit Status-Badges (Aktiv/Ruhig/Churn-Risiko/Top), CRM-Notizen, Follow-Up System mit automatischen Vorschlägen basierend auf Performance (nicht Kalendertagen), Erfolgs-Metriken.
**Depends on:** Phase 04.7
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE GSD Status.md` (Abschnitt Phase 4.14)
**Plans:** TBD

### Phase 04.15: Rollen, Support & Kompensation (INSERTED)

**Goal:** Granulares Rollen-System (superadmin/support/billing/analyst), DSGVO-konformer Support-Zugriff auf Kundenprofile mit Audit-Trail, Kompensation (Gratis-Tage bei Ausfällen), Mitarbeiter-Verwaltung.
**Depends on:** Phase 04.14
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE GSD Status.md` (Abschnitt Phase 4.15)
**Plans:** TBD

### Phase 04.16: Finaler Polish + UAT (INSERTED)

**Goal:** Letzter Schliff vor Launch — finaler UAT-Durchlauf aller Features auf Produktion, Design-Pass (Farben, Fonts, Abstände), CSS Refactoring (Inline-Styles → nerve.css), Code Audit + Refactoring, Performance-Check.
**Depends on:** Alle vorherigen Phasen
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Finaler Polish Pass.md`
**Plans:** TBD

### Phase 04.17: PiP Launcher (INSERTED)

**Goal:** Always-on-Top verschiebbarer Live-Assistent via Document Picture-in-Picture API. User kann aus CRM/Outlook/Teams heraus direkt einen NERVE-Call starten — Modus waehlen, Kundendaten eingeben, Skript auswaehlen, Live-Coaching im PiP-Fenster.
**Depends on:** Phase 04.8 (Consent-System), Phase 04.12 (Gesamt-Integration). Optional: Phase 04.13 (PreCall Auto-Recherche Button)
**Briefing:** `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE PiP Launcher.md`
**Plans:** TBD

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
| 4.3 Design Unification | 6/6 | Complete   | 2026-04-04 |
| 4.5 Training Analytics & Tools | 3/4 | In Progress | - |
| 4.6 Sales Performance Calculator | 3/4 | In Progress | - |
| 4.6.1 Auth-Upgrade OAuth | 3/3 ✓ | Complete | 2026-04-06 |
| 4.7 Backend & Feedback System | 0/? | Not started | - |
| 4.7.1 FineTuning Logging | 0/? | Not started | - |
| 4.7.2 Founder Cost Dashboard | 0/? | Not started | - |
| 4.8 KI-Logik Upgrade | 0/? | Not started | - |
| 4.9 Training-Modul Upgrade | 0/5 | Planned | - |
| 4.10 Training Realismus | 0/? | Not started | - |
| 4.11 Coach-Modul | 0/? | Not started | - |
| 4.12 Gesamt-Integration | 0/? | Not started | - |
| 4.13 PreCall Intelligence | 0/? | Not started | - |
| 4.14 CRM & Customer Success | 0/? | Not started | - |
| 4.15 Rollen, Support & Kompensation | 0/? | Not started | - |
| 4.16 Finaler Polish + UAT | 0/? | Not started | - |
| 4.17 PiP Launcher | 0/? | Not started | - |
| 5. Launch | 0/? | Not started | - |

---
*Roadmap created: 2026-03-30*
*Milestone: NERVE Launch — v0.9.4 to first 50 paying customers*
