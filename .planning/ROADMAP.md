---
created: 2009-03-30
milestone: v0.9.4
total_phases: 5
estimated_duration_days: 16
---

# Roadmap: NERVE

**Source:** Project interview on 2009-03-30
**Goal:** Launch NERVE zum ersten zahlenden Kunden in Deutschland
**Target:** Milestone 1 = v0.9.4 → v1.0 (Early Access mit 50 Plätzen + 50% Gründerrabatt)

## Core Value

Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

## Context

**User's Goal (von Ihm formuliert):**
> "Ich will NERVE launchen — genug gebaut, jetzt rausbringen. Die Grundfunktion läuft stabil. Was fehlt: Pricing, Legal-Sachen, Gewerbeanmeldung, Payments. Ich habe ~14 Tage im Monat Zeit."

**Business Context:**
- Solo-Founder André Preuß, Iserlohn (NRW)
- Noch keine Gewerbeanmeldung, USt-IdNr, Geschäftskonto
- Erwartet: ~100.000€/Jahr Gehalt → Einzelunternehmer vs. UG noch offen
- Warteliste bereits aufgebaut, bereit für Launch

**Technical Context:**
- NERVE v0.9.4 production-ready
- Flask + Vanilla JS (keine React-Migration)
- DACH-Fokus Milestone 1, i18n später
- Flat-Rate Pricing (69/59/49€) — nicht Credit-basiert

**Aktuelle Richtungs-Entscheidungen (Stand 2026-06-01, Sync von Vault-Roadmap):**
- **Staging komplett aus dem Workflow** bis zur letzten Phase vor Launch → Production ist einziger Deploy-/Test-Pfad (Details: `CLAUDE.md` → "ÜBERSCHREIBUNG 2026-06-01"). `deploy.sh`-Staging-Gate entfernt. Reaktivierung = Phase **08.23.2.STAGING** (ganz am Ende, letzte Phase vor Launch).
- **Block O = kompletter Design-Wechsel auf neues Dark-Design** (kein Polish mehr). Das alte Light-Design fliegt komplett raus (nerve.css-Tokens/Klassen/Inline-Styles) → nur das neue bleibt als single source of truth, damit GSD künftig nicht mehr im alten Design bauen kann. Mockups + Export in `_design_export/`. Usability-Bar: ein Anfänger ohne Sales/IT muss das Dashboard in ~10 Sek verstehen (Klartext-Labels statt Metapher-Jargon).
- **Hinweis:** Strategische Blocks (Block O, STAGING, Pricing 08.15/08.16) leben primär in der Vault-Roadmap (`Nerve-Vault/01 Roadmap.md`); diese GSD-Roadmap ist operativ-granularer. Bei Phasen-Scope immer beide abgleichen.

## Phases Overview

| Phase | Title | Depends On |
|-------|-------|------------|
| 1 | Business Setup | - |
| 2 | Product Fixes | - |
| 3 | Infrastructure & Deployment | 1, 2 |
| 4 | Payments & Legal | 1, 3 |
| 5 | Launch | 4 |

## Phases Detail

### Phase 1: Business Setup

**Goal:** Als Unternehmer gründen und alle rechtlichen/finanziellen Grundlagen sichern
**Depends on:** — (kein Blocker)
**Parallelizable with:** Phase 2 (unabhängig)
**Plans:** 3-4 plans (to be broken down)

**Items:**
- Gewerbeanmeldung beim Gewerbeamt Iserlohn
- Geschäftskonto eröffnen (Empfehlung: Kontist oder Finom)
- USt-IdNr beim Bundeszentralamt für Steuern beantragen
- Steuerberater engagieren (Empfehlung: count.tax für Online-Beratung)

**Reasoning:**
> Ohne Gewerbeanmeldung kein Geschäftskonto, ohne USt-IdNr keine B2B-Rechnungen ins Ausland. Steuerberater muss von Anfang an beraten — sonst Panik im ersten Jahr.

---

### Phase 2: Product Fixes

**Goal:** Alle Blocker aus dem Produkt-Tool rauskicken, damit v0.9.4 launchfähig ist
**Depends on:** — (kein Blocker)
**Parallelizable with:** Phase 1 (unabhängig)
**Plans:** 3-4 plans (to be broken down)

**Items:**
- Pricing-System aus ToDo-Liste umsetzen (69/59/49€ Flat-Rate)
- ROI-Tracker im Dashboard einbauen
- Trainings-Modus "Frei" hinzufügen (keine Hilfe-Hints, maximale Punkte)
- Trainings-Modus "Geführt" hinzufügen (Hilfe verfügbar mit Abzug)
- Cross-Sell im Training: "Was hätte NERVE Live gezeigt" Preview
- 11 DACH-Mittelstand Trainings-Szenarien als Standard (alle Schwierigkeitsstufen)
- Live-Bereich Bugs: Skript-Button fehlt, DSGVO-Einwilligung fehlt/falsche Position, Kompakt-Modus Kreise/Toggle korrigieren
- Onboarding Text-Änderungen (generischer statt Demo-Inhalt)
- Profil-Wizard statt leerem Formular für Erstuser
- Profil-Editor-Texte generalisieren
- "SalesNerve" → "NERVE" überall im Code ersetzen

**Reasoning:**
> Wenn Pricing nicht live ist, kann keiner bezahlen. Wenn Trainings-Modi unklar sind, versteht keiner den Vorteil gegenüber Live. Bugs im Live-Bereich unterminieren das Kernversprechen. Onboarding-Text muss generisch sein — nicht mit Demo-Inhalt. Wizard statt leeres Formular reduziert Friction.

---

### Phase 3: Infrastructure & Deployment

**Goal:** App von localhost auf Hetzner Cloud VPS deployen (DSGVO-konform)
**Depends on:** Phase 1 (Gewerbeanmeldung für Hetzner-Account), Phase 2 (stabiles Produkt)
**Plans:** 3-4 plans (to be broken down)

**Items:**
- Hetzner Cloud CX22 VPS provisionen (4.15€/Monat, Falkenstein)
- Domain kaufen und verknüpfen (noch keine gesichert)
- nginx + gunicorn Setup mit SSL (Let's Encrypt)
- SQLite + persistentes Volume (statt PostgreSQL für Milestone 1)
- Git-Deployment-Pipeline aufsetzen
- Monitoring basics (uptime, logs)

**Reasoning:**
> Hetzner ist deutscher Anbieter = DSGVO trivial. CX22 reicht für ~50 Early Access User. PostgreSQL-Migration wäre Overkill für Milestone 1. Domain ist prio — ohne kein Launch.

---

### Phase 03.1: Frontend Redesign (INSERTED)

**Goal:** Frontend komplett neu aufbauen — Farben/Kontrast fixen (dunkle Schrift auf dunklem BG überall)
**Depends on:** Phase 3
**Plans:** 5-8 plans (to be broken down)

**Items:**
- Aktuelle UI komplett verwerfen (außer Struktur/Layout)
- Neues Design-System: Dark Mode mit hohem Kontrast (WCAG AAA wo möglich)
- Alle Seiten durchgehen: Landing, Dashboard, Training, Profile, Live-Bereich, Kompakt-Modus
- Farbpalette neu definieren (Text-Farben auf dunklem Hintergrund: #E4E4E7 statt #9CA3AF etc.)
- Komponenten-Bibliothek: Buttons, Cards, Inputs, Modals, Dropdowns, Tables
- Animations/Transitions verfeinern (nicht übertrieben)
- Responsiveness prüfen (Desktop-first, aber mindestens Tablet tauglich)
- Onboarding-Texte inline testen im neuen Design

**Reasoning:**
> UAT zeigte: Text-Kontrast ist massiv zu schwach, Placeholder-Grau fast unlesbar, Input-Felder verschwinden im Dark-BG. Komplettes Re-Design ist schneller als Einzelfixes — Farben sind systemisch falsch gesetzt.

---

### Phase 03.2: UAT Bug Fixes (INSERTED)

**Goal:** Alle kritischen Bugs aus UAT Phase 03.1 beheben (Registrierung, Dashboard, Training, Live-Assistent)
**Depends on:** Phase 03.1
**Plans:** 7 plans (P01 Auth + Settings, P02 Dashboard, P03 Dashboard BugFix, P04 Training, P05 Live-Assistent, P06 Global CSS Theme, P07 Profil-Editor + Duplikate)

**Items:**
- P01: Registrierung auf Landing-Page zugänglich machen + Einstellungen aus Sidebar
- P02: Dashboard umbauen (keine Demo-Daten, sinnvolle Content-Gliederung, Analyse-Details, ehrliche Analytics)
- P03: Dashboard Call-Log Redirect auf /analyse/<id> (statt leerer GET /analyse Route)
- P04: Training umbauen (Nicht-User-Profile verbergen, Demo-Gesprächspartner-Namen, "KI ruft an" Flow, Post-Call-Zusammenfassung verschoben, Einstellungen verschoben)
- P05: Live-Assistent umbauen (Transkription prominent, Skript + Gegenargumente integriert statt Alt-Buttons)
- P06: Globales CSS-Theme (Dark Background auf allen Seiten, Einheitlichkeit Dashboard/Training/Analyse/Profile/Settings)
- P07: Profil-Editor neu (Schnelleingabe + Expert-Modus, zuverlässiges Speichern), Duplikate aus DB entfernen

**Reasoning:**
> UAT fand 11 kritische Bugs. Registrierung ist blockiert (Login-Overlay zeigt kein Sign-Up). Dashboard zeigt Demo-Daten. Training zeigt Fremd-Profile. Live-Bereich hat doppelte Buttons und versteckte Transkription. Alle fixen vor nächstem UAT-Durchlauf.

---

### Phase 4: Payments & Legal

**Goal:** Bezahlung funktioniert + DSGVO-rechtlich sauber + Impressum/AGB/Datenschutz fertig
**Depends on:** Phase 1 (Gewerbeanmeldung für Stripe, USt-IdNr für Rechnungen), Phase 3 (deployed App)
**Plans:** 4-5 plans (to be broken down)

**Items:**
- Stripe Account eröffnen (Business-Account, nicht Personal)
- 3 Produkte in Stripe anlegen (69/59/49€/Monat + Tax-Codes)
- Checkout-Flow integrieren (Hosted Checkout empfohlen)
- Customer-Portal für Kündigung/Upgrade
- Webhooks: checkout.session.completed, customer.subscription.updated/deleted
- DSGVO-Einwilligung vor erstem Mikrofon-Zugriff (aus Phase 2)
- Impressum erstellen (TMG §5-konform)
- AGB erstellen (mit Klausel zur Datenverarbeitung durch Drittanbieter)
- Datenschutzerklärung (DSGVO Art. 13, DeepGram + Anthropic + ElevenLabs als Auftragsverarbeiter nennen)
- Auftragsverarbeitungsverträge (AVVs) signieren: DeepGram, Anthropic, ElevenLabs, Stripe
- Fair-Use Tracking (Live-Minuten + Trainings-Sessions) in DB
- Soft-Warnung bei ~80% des Fair-Use-Limits, kein harter Block

**Reasoning:**
> Ohne Impressum ist jeder Betrieb in Deutschland illegal. AVVs sind Pflicht für DSGVO. Stripe erfordert echte Gewerbeanmeldung und USt-IdNr. Fair-Use per DB atomar zählen — keine harten Limits (Founder-Philosophie). Für MEETING-Modus: "Wir brauchen DEUTLICHE Einwilligung, Deepgram hört zu" statt Kontext-Hinweis.

---

### Phase 04.6.2: deploy hardening and oauth polish (INSERTED)

**Goal:** zusammenfassend abschließen — deploy stabilisieren und oauth/credits feinschliff
**Depends on:** Phase 4
**Plans:** 2-4 plans (to be planned)

**Items:**
- tbd via /gsd-plan-phase

**Reasoning:**
> User-defined: zusammenfassend abschließen — deploy stabilisieren und oauth/credits feinschliff

---

### Phase 04.1: Live-Mikrofon Fix: PyAudio -> Browser getUserMedia (INSERTED)

**Goal:** Live-Mikrofon funktioniert auf getnerve.app — Audio wird vom Browser erfasst (nicht Server-PyAudio)
**Depends on:** Phase 4
**Plans:** 3 plans (Backend Deepgram-Service, Frontend MediaStream + AudioWorklet, Integration + DSGVO-Banner)

**Items:**
- Backend: PyAudio komplett aus deepgram_service.py entfernen
- Backend: Deepgram-WebSocket pro Socket.IO-Session aufbauen (start_live_session, stop_live_session Events)
- Backend: audio_chunk Event empfangen und 1:1 an Deepgram weiterleiten
- Frontend: getUserMedia mit {sampleRate:16000, channelCount:1, echoCancellation:true}
- Frontend: AudioWorklet (oder ScriptProcessor Fallback) konvertiert Float32 → Int16 PCM
- Frontend: audio_chunk via Socket.IO an Server streamen (ArrayBuffer)
- DSGVO: Einwilligungs-Banner VOR getUserMedia-Aufruf, Berechtigungs-Dialog erst nach Zustimmung
- E2E-Test: getnerve.app öffnen → Live-Modus → Sprechen → Transkription erscheint
- Lokaler Fallback: bestehender PyAudio-Code als Fallback wenn MIC_USE_BROWSER=false (optional)

**Reasoning:**
> Showstopper-Bug für Launch: Server hat keine PyAudio-Umgebung (und darf keine haben — Server hört nicht mit). Browser erfasst Audio, Server routet nur durch zu Deepgram. Alle Trigger laufen schon (MODE-01..06), es fehlt nur der Audio-Pipe. Lösung ist Web-Standard (getUserMedia + AudioWorklet), DSGVO-konform (Einwilligung vor getUserMedia), ohne Third-Party-Dependency.

---

### Phase 04.2: Cold Call und Meeting Modi (INSERTED)

**Goal:** User können vor Live-Session zwischen Cold Call (nur Berater) und Meeting (Berater + Kunde) wählen
**Depends on:** Phase 4
**Plans:** 5-6 plans (to be broken down)

**Items:**
- Pre-Session Modus-Auswahl Overlay auf /live (Pflicht, kein Wechsel mid-call)
- Cold Call: Deepgram single-speaker mode, nur Berater-Audio, EWB-Buttons sichtbar (aus aktivem Profil)
- Meeting: Consent-Popup mit Vorleseskript, Stattgegeben startet Diarization, Abgelehnt fällt auf Cold Call zurück
- EWB-Buttons lösen sofortige Claude-Haiku-Anfrage aus (Einwand-Kontext, Profil-Gegenargumente)
- session_mode in ConversationLog speichern, Badge im /live Header
- EWB-Klicks in quick_action_log (typ='ewb') loggen, qa_count Persistenz in api_beenden

**Reasoning:**
> Cold Call hat rechtliche + ethische Klarheit (nur der Berater), Meeting braucht expliziten Consent. EWB-Buttons sind der Low-Friction-Pfad für bekannte Einwände, ohne Transkription-Roundtrip abzuwarten. Beide Modi nutzen das Profil als Wissensbasis.

---

### Phase 04.2.1: UI/UX Overhaul — Dashboard, Live-Assistent, Kompaktmodus. Komplettes Layout überarbeiten, Getclose.ai als Design-Referenz, Picture-in-Picture Overlay, intuitive Anordnung aller Elemente. (INSERTED)

**Goal:** UI/UX Overhaul — Dashboard, Live-Assistent, Kompaktmodus. Komplettes Layout überarbeiten, Getclose.ai als Design-Referenz, Picture-in-Picture Overlay, intuitive Anordnung aller Elemente.
**Depends on:** Phase 4.2
**Plans:** 2-4 plans (to be planned)

**Items:**
- tbd via /gsd-plan-phase

**Reasoning:**
> User-defined: UI/UX Overhaul — Dashboard, Live-Assistent, Kompaktmodus. Komplettes Layout überarbeiten, Getclose.ai als Design-Referenz, Picture-in-Picture Overlay, intuitive Anordnung aller Elemente.

---

### Phase 04.3: Design Unification (INSERTED)

**Goal:** Gesamte UI auf einheitliches dunkles Farbschema umstellen (kein Light Mode, kein User-Toggle). Alle Seiten in einem Stil.
**Depends on:** Phase 04.2
**Plans:** 5-8 plans (to be broken down)

**Items:**
- Beenden-Button im Live-Assistenten (stoppt Session und navigiert zurück)
- Einheitliches Farbschema (Option D: Dunkel überall, kein Toggle)
- Training-Seite: Einheitliches Dark-Theme (Hintergrund + Cards)
- Einstellungen-Seite: Cards auf dunklem Grund, keine hellen "schwebenden" Cards
- Analytics/Logs: Dark Background + einheitliche Tabellen
- Footer entfernen (Impressum/AGB/Datenschutz) — stattdessen im Einstellungen-Bereich als "Rechtliches" Tab
- Login-Email-Anzeige + Logout-Button aus Header entfernen → in Einstellungen verlagern
- Sprach-Buttons aus Training entfernen → nach Einstellungen verlagern
- Hilfe-Center: Orange durch Teal ersetzen, komplett ins Dark-Theme integrieren
- Profil-Editor: Dark-Theme umsetzen (aktuell zu hell, schlechter Kontrast)
- Settings-Button in Sidebar fix positionieren (kein Springen beim Seitenwechsel)

**Reasoning:**
> UAT zeigte starke visuelle Inkonsistenz: Training hat weiße Cards, Einstellungen schwebt, Analytics hat eigenes Theme, Hilfe-Center orange statt teal, Profil-Editor hell. Login-Anzeige und Logout bleiben permanent oben sichtbar. Einheitliches Dark-Theme ist schneller zu bauen als Light-Mode mit Toggle, und NERVE ist ein Sales-Tool — keine iOS/Android Consumer-App mit Dark/Light-Präferenz.

---

### Phase 04.5: Training Analytics & Tools (INSERTED)

**Goal:** Training-Seite wird zentrale Lern- und Diagnose-Plattform (Analytics + smarte Tools)
**Depends on:** Phase 04.3
**Plans:** 3-4 plans (to be broken down)

**Items:**
- Trainings-Metrik-Card (Woche/Monat/Gesamt + Durchschnittsdauer + Streak + Wochenziel)
- Einwand-Heatmap mit 7 Kategorien (farblich kodiert, Klick startet Quick-Training)
- Phrasen-Bank (Wendepunkt-Sätze aus Post-Call-Analysen, filterbar, paginiert)
- Letzte Session Card (kompakte Zusammenfassung mit Link zur Analyse)
- KI-Empfehlung der Woche (regelbasiert, ohne zusätzlichen Claude-Call)
- Wochenziel-Card (User setzt Ziel, Fortschrittsbalken, Kalenderwoche-Reset)

**Reasoning:**
> UAT fand: Post-Call-Analyse wertvoll, aber schwer auffindbar. Training-Seite aktuell nur Szenario-Liste, sollte Home-Base für Weiterentwicklung sein. Analytics + Heatmap + Phrasen-Bank geben sofortigen Mehrwert. KI-Empfehlung regelbasiert (kein LLM-Call) — kosten-bewusst.

---

### Phase 04.6: Sales Performance Calculator (INSERTED)

**Goal:** Verkaufs-Performance-Rechner in Einstellungen "Rechtliches & Compliance". User gibt Standardpreis, Provisionssatz, Gewinnsteigerung in %/Session an (z. B. 25% mehr Umsatz pro Call). System rechnet automatisch Gesamtgewinn vs. Standardwerte. Mitarbeiter-Verwaltung bleibt bestehen, Export für Team-Leader. Kein Paywall-Trigger.
**Depends on:** Phase 04.5
**Plans:** 3 plans completed (P01 DB Model + Save, P02 Calculator Page + Sidebar Link, P03 CSV Export)

**Items:**
- DB Model SalesCalculator (profile_id FK, standardpreis, provisionssatz, gewinnsteigerung_prozent, timestamps)
- Settings Tab 'Verkaufsrechner' — Eingabeformular für Rechner-Werte + Berechnung
- Calculator-Seite mit Auto-Berechnung (pro Session Zusatzgewinn, monatlicher Zusatzgewinn, ROI-Berechnung)
- Sidebar Nav-Link für Rechner (Label: "Rechner")
- CSV Export für Team-Leader (Pro User: Standardpreis, Provisionssatz, %-Gewinn, Berechnete Werte)
- Sales Performance Calculator in Profil-Settings (nicht global) + Team-Export

**Reasoning:**
> Team-Leader brauchen proof-of-value für Ihren Boss, und für jede Sales-Session. User hat Formel klar: (Standardpreis × Provisionssatz × Gewinnsteigerung_Prozent). Export im CSV für Chef-Reports. Kein eigener Menüpunkt nötig — in Einstellungen reicht, aber Sidebar-Link für Quick-Access.

---

### Phase 04.6.1: Auth-Upgrade Google + Microsoft OAuth Login (INSERTED)

**Goal:** User können sich mit Google OAuth, Microsoft OAuth, Magic-Link und Email+Password einloggen — alle Accounts landen im User-Modell, auch bei Methoden-Wechsel bleibt Identität konsistent
**Depends on:** Phase 04.6
**Plans:** 3 plans completed (P01 DB migration + pytest + /me endpoint, P02 Authlib Google+Microsoft OAuth routes, P03 Fernet token encryption + Magic-Link)

**Items:**
- DB-Migration (oauth_provider, oauth_id unique constraint, email_verified, oauth_tokens encrypted, magic_link_tokens)
- Fernet Token-Encryption für OAuth refresh_tokens (AUTH_TOKEN_ENCRYPTION_KEY)
- Google OAuth Flow (Authlib, openid+email+profile scopes, claims in Session speichern)
- Microsoft OAuth Flow (Authlib, openid+email+offline_access scopes, Multi-Tenant endpoint)
- Magic-Link Sign-In Flow (60s rate-limit, 15min token, single-use, Email via Resend EU)
- pytest Setup (pytest + SQLite in-memory fixtures, CI-fähig)
- Smoke Test für /me Endpoint (GET with session cookie returns user profile)
- CLAUDE.md + .env.example aktualisiert mit OAuth + Magic-Link vars

**Reasoning:**
> UAT zeigt: neue User blockieren bei der Registrierung. OAuth ist Enterprise-Table-Stakes (Google + Microsoft decken 95%+ der B2B-Zielgruppe ab). Magic-Link als Password-Reset-Alternative. DB-First-Approach stellt sicher, dass bestehende Email-User nicht brechen. Fernet-Encryption schützt OAuth-Tokens. Pytest erlaubt ab jetzt TDD in Auth-Code. P01 (DB + Tests) ✅ P02 (Google+Microsoft OAuth) ✅ P03 (Token-Encryption + Magic-Link + Email via Resend) ✅

---

### Phase 04.7: Backend & Feedback System (INSERTED)

**Goal:** Admin-Backend + User-Feedback-System — Superadmin-Dashboard mit Admin-Tools, Feedback-Modal, strukturiertes Logging für Produkt-Daten
**Depends on:** Phase 04.6
**Plans:** 8 plans (P01 Superadmin Flag + Decorator, P02 Flask-Admin Setup, P03 Audit Log + Triggers, P04 Einwand-Events Tabelle, P05 Feedback Modal + Upload Endpoint, P06 Email via Resend DE-Region, P07 Session-History Seite, P08 Admin-Dashboard KPIs + Planungs-Liste)

**Items:**
- P01: users.is_superadmin Flag, ENV-Seed via SUPERADMIN_EMAIL, @superadmin_required Decorator
- P02: Flask-Admin unter /admin mit SecureIndexView (Bootstrap4 Theme)
- P03: audit_log Tabelle + Immutable Trigger + log_action() Helper, Wire-up in Login/Session/Profil Routes
- P04: objection_events Tabelle, EWB-Klick-Persistenz pro ConversationLog, avg_deal_wert unverändert aber mit Naming-Konflikt-Note
- P05: feedback Tabelle (getrennt von bestehender FeedbackEvent), Sidebar-Button (unten links), Modal, Screenshot-Upload, POST /api/feedback, /api/feedback/quick
- P06: Resend EU-Region Integration, 3 Templates (Welcome, Feedback-in-Planung, Password-Reset)
- P07: Session-History-Seite (Umbau bestehender Analytics-Seite zu chronologischer ConversationLog-Liste + Detail-View)
- P08: Admin-Dashboard mit ModelViews (User, Org, Feedback, AuditLog, ConversationLog), KPI-CustomView, Planungs-Liste, Ticket-Workflow (new → in_planning mit Resend-Trigger)

**Reasoning:**
> Ohne Admin-Tools keine Kontrolle über Produktentwicklung. Ohne strukturierte Feedback-Erfassung keine Priorisierung. audit_log ermöglicht nachträgliche Analyse (Wer? Wann? Was?). Einwand-Events erlauben Tiefenanalyse über Zeit ("Welcher Einwand kommt am häufigsten in Cold Calls?"). Feedback-Modal reduziert Friction für User, Screenshots klären Kontext. Email via Resend bestätigt Feedback-Eingang und Status. Session-History ersetzt Analytics-Seite mit sinnvollerer chronologischer View. Admin-Dashboard ist Single-Source-of-Truth für Founder.

---

### Phase 04.7.1: FineTuning Logging Grundlage (INSERTED)

**Goal:** FineTuning Datengrundlage — Minimal-invasive Logging (7-day Retention, opt-out für freien Plan) mit DSGVO-Konsent und spaeteren FineTune-Datasets
**Depends on:** Phase 04.7
**Plans:** 5 plans completed (P01 ft_logs table + UserSettings.analytics_consent column, P02 log helper + finetune_enabled gate, P03 settings endpoint + UI toggle, P04 delete endpoint + opt-out/consent revocation, P05 retention cron + Flask-Admin FtLog ModelView)

**Items:**
- ft_logs Tabelle mit user_id, phase, model, prompt_full, response_full, feedback, latency_ms, tokens_prompt, tokens_response, cost_cents, created_at
- DB-Migrations-Helper wired in app.py startup
- UserSettings.analytics_consent Column + Opt-Out-Logic
- app_config.finetune_enabled Gate fuer Master-Kill-Switch
- log_ft_event() Helper in services/finetune_logging.py (opt-out + gate check + resilient insert)
- Wire-ups in services/claude_service.py (Haiku+Sonnet responses) und training_service.py (bewertung_mit_claude)
- /api/settings/analytics_consent POST + Settings UI Toggle (opt-in fuer Privacy-Default)
- /api/settings/analytics_data DELETE endpoint (harte ft_logs-Loeschung, opt-out retour)
- Daily cron (cron/cron_ftlog_cleanup.py) mit 7-Tage-Retention
- Flask-Admin FtLogView (read-only, created_at desc sorted)

**Reasoning:**
> FineTuning-Datasets brauchen hochqualitative Paare aus realen Sessions, nicht nur synthetische. 7-Tage-Retention reicht fuer Datenpunkt, reduziert DSGVO-Fussabdruck. Opt-Out default fuer Free-Plan (Datenschutz-first), Paid-Plan kann opt-in fuer bessere Individualisierung. finetune_enabled Gate erlaubt Master-Kill (z.B. bei einer Rechtschutzfrage) ohne Code-Rollback. ft_logs ist append-only und DSGVO-konform (harte Deletion via API moeglich, automatische Cleanup via Cron). 

---

### Phase 04.7.2: Founder Cost Dashboard (INSERTED)

**Goal:** Founder-Dashboard das echte API-Kosten (Anthropic + Deepgram + ElevenLabs) pro User und Plan zeigt, damit wir sehen wann ein Kunde unprofitabel ist
**Depends on:** Phase 04.7.1
**Plans:** 4 plans completed (P01 CostBatch model + migration + seeded rates, P02 cost rollup job + usage counters, P03 /admin/costs dashboard + sidebar link, P04 alerts table + in-app warning + CSV export)

**Items:**
- Kosten-Rate-Seed (CLAUDE_HAIKU, CLAUDE_SONNET, DEEPGRAM_NOVA2, ELEVENLABS_FLASH) als Tagesgenauigkeit
- Cost-Rollup-Job (nightly Cron) der ft_logs + deepgram_minutes + elevenlabs_chars → cost_cents_total pro User+Plan
- /admin/costs Dashboard mit Filter (User-Email, Date-Range, Plan) + Tabelle + Sidebar-Link im Flask-Admin
- Plan-Profitability-Row (Earned € vs. Cost € vs. Margin %) und Alert-Row (Kunden mit Margin &lt; 30%)
- Alerts-Tabelle + Cron-Trigger (täglich-Check Margin thresholds, Admin erhält In-App-Warning im Dashboard)
- CSV-Export für Buchhaltung + Archiv (Monthly)
- Infra: pytest-Tests für Cost-Rollup-Logic (nicht aufwand-schwer — einmaliger Job)

**Reasoning:**
> Ohne Cost-Dashboard kann der Founder nicht erkennen, ob ein Customer profitabel ist oder subventioniert wird. Besonders bei Power-Usern in Plan 1 (49€) können die API-Kosten 09-80% der Einnahmen fressen. Dashboard liefert Early Warning Signals bevor sich Cost-Ratios in die Kassen fressen. Erste Version reicht Tagesgenauigkeit (kein Realtime), Aggregation nightly über bestehende ft_logs. Alert-System ersetzt manuelle SQL-Queries.

---

### Phase 04.8: KI-Logik Upgrade (INSERTED)

**Goal:** Analyse- und Trainings-Pipelines so überarbeiten, dass Coaching, Training und Echtzeit-Engine präzise, schnell und markenkonform arbeiten
**Depends on:** Phase 04.7.2
**Plans:** 6 plans completed (P01 Live-Prompt Revamp, P02 Training Voice-Pool, P03 Training Post-Call Pipeline, P04 Feedback Loop Coach Experiments, P05 Dashboard ROI Rebuild, P06 Critical Bugfixes Phase 04.8)

**Items:**
- Live-Prompt revamp + Haiku model pinning + Phase 1 streaming ack
- Training voice pool rotation + gender match + last-voice cache
- Training post-call pipeline (wendepunkte + richtige entscheidungen + empfehlung)
- Training feedback loop + coach experiments + prompt experiments
- Dashboard ROI rebuild (Kunden-Mehrwert, realistische Einsparungen)
- 6 Critical Bugfixes — Live Rendering Flash, PiP height, Training voice deadlock, Analyse Matomo crash, German copy in settings

**Reasoning:**
> Phase 04.8 war der große KI-Qualitäts-Phase: Haiku für Live, Sonnet für Post-Call, Prompts markenkonform, Training/Coaching-Infrastruktur stabilisiert. Bugfixes lösen kritische UAT-Blocker für Launch.

---

### Phase 04.8.1: Echtzeit-Engine Rebuild — Async FastAPI WebSocket Engine, Redis Bridge, STT/LLM Abstraktionsschicht, Polling ersetzen (INSERTED)

**Goal:** Echtzeit-Engine Rebuild — Async FastAPI WebSocket Engine, Redis Bridge, STT/LLM Abstraktionsschicht, Polling ersetzen
**Depends on:** Phase 04.8
**Plans:** 3 plans completed (FastAPI WebSocket Engine setup, Redis Bridge + State Management, STT/LLM Abstraction + Polling-Replacement)

**Items:**
- Async FastAPI WebSocket Engine als zweiter Service (live/ ordner) der parallel zu Flask läuft
- Redis-Bridge zwischen Flask und FastAPI für Session-State
- STT/LLM Abstraktionsschicht mit Provider-Swap (Deepgram nebst Nova2 und Nova3)
- Polling-Replacement mit WebSocket Push für Analyse-Ergebnisse
- Alte Polling-Endpoints (/api/ergebnis) bleiben für Backward-Compat mit PiP und anderen Seiten

**Reasoning:**
> Das Polling-System mit 500ms Intervall hatte Latenz-Issues und war nicht skalierbar. FastAPI WebSocket-Engine mit Redis-Bridge liefert sub-100ms Push, die STT/LLM Abstraktion erlaubt Provider-Swap ohne Code-Änderungen.

---

### Phase 04.9: Training-Modul Upgrade (INSERTED)

**Goal:** Training-Modul auf Enterprise-Niveau — strukturierte Szenarien, Kategorien, Difficulty-Levels, Progression, Analytics-Integration
**Depends on:** Phase 04.8.1
**Plans:** 5 plans completed (P01 Szenario-Kategorien, P02 Difficulty-Levels, P03 Progression-Tracking, P04 Analytics-Integration, P05 Szenarien-Verwaltung)

**Items:**
- Training-Szenarien in Kategorien (Cold Call, Discovery Call, Demo, Closing) strukturiert
- Difficulty-Levels (Anfänger, Fortgeschritten, Experte) mit Auswahl im Setup
- Progression-Tracking (User durchläuft Szenarien in definierter Reihenfolge)
- Analytics-Integration (Scores pro Szenario, Kategorie-Performance)
- Szenarien-Verwaltung für Admin (CRUD für Training-Szenarien)

**Reasoning:**
> Phase 04.5 brachte Analytics, Phase 04.9 bringt die Szenario-Infrastruktur auf Enterprise-Niveau. Kategorien, Difficulty, Progression sind Basis-Features für "richtig trainieren".

---

### Phase 04.10: Training Realismus (INSERTED)

**Goal:** Training-Szenarien realistischer machen — Customer-Personas, dynamische Einwände, Verhaltens-Variationen
**Depends on:** Phase 04.9
**Plans:** 4 plans completed (P01 Customer-Personas, P02 Dynamische Einwände, P03 Verhaltens-Variationen, P04 Emotionale Reaktionen)

**Items:**
- Customer-Personas mit Profil (Alter, Position, Firmen-Typ, Persönlichkeit)
- Dynamische Einwände (Claude generiert Einwände basierend auf Persona + Kontext)
- Verhaltens-Variationen (Persona kann kooperativ, neutral oder ablehnend sein)
- Emotionale Reaktionen (Persona reagiert emotional auf Berater-Aussagen)

**Reasoning:**
> Statische Szenarien werden schnell durchschaut. Realistische Personas mit dynamischen Reaktionen erzeugen echten Lerneffekt. Claude als "Persona-Player" mit klarem System-Prompt.

---

### Phase 04.10.1: Emotionale TTS-Stimmen (INSERTED)

**Goal:** TTS-Stimmen emotional machen — ElevenLabs v2 + Emotion-Tags, Persona-spezifische Voice-Configs
**Depends on:** Phase 04.10
**Plans:** 1 plan completed (P01 ElevenLabs v2 Integration + Emotion-Tags)

**Items:**
- ElevenLabs v2 API Integration
- Emotion-Tags pro Persona (freundlich, skeptisch, genervt, interessiert)
- Voice-Config pro Persona (male_deep, female_warm, male_young, female_authoritative)
- Fallback auf ElevenLabs v1 wenn v2 nicht verfügbar

**Reasoning:**
> Emotionale Stimmen sind der Kern-Unterschied zwischen "Training-Tool" und "realistischem Gesprächs-Simulator". ElevenLabs v2 mit Emotion-Tags ist state-of-the-art.

---

### Phase 04.11: Coach-Modul (INSERTED)

**Goal:** Coach-Modul — Team-Leader können Mitarbeiter-Trainings reviewen, Feedback geben, Coaching-Sessions planen
**Depends on:** Phase 04.10.1
**Plans:** 4 plans completed (P01 Coach-Rolle + DB, P02 Coach-Dashboard, P03 Review-Interface, P04 Coaching-Sessions)

**Items:**
- Coach-Rolle (users.rolle = 'coach') + Coach-Zuordnung zu Mitarbeitern
- Coach-Dashboard mit Team-Overview (Sessions, Scores, Trends)
- Review-Interface (Coach sieht Session-Details, kann kommentieren, Feedback geben)
- Coaching-Sessions (Coach plant 1:1-Sessions mit Mitarbeiter, in-app Notes)

**Reasoning:**
> Enterprise-Kunden brauchen Coach-Funktionalität. Team-Leader können so direkten Impact auf Mitarbeiter-Training haben.

---

### Phase 04.12: Gesamt-Integration (INSERTED)

**Goal:** Gesamt-Integration — alle Module (Live, Training, Coach, Analytics, Dashboard) miteinander verbinden, Konsistenz prüfen, Cross-References
**Depends on:** Phase 04.11
**Plans:** 4 plans completed (P01 Cross-References, P02 Konsistenz-Check, P03 User-Flows, P04 UAT-Vorbereitung)

**Items:**
- Cross-References zwischen Modulen (z.B. Live → Session-History → Analyse → Training-Empfehlung)
- Konsistenz-Check für UI/UX (gleiche Farben, gleiche Buttons, gleiche Sprache)
- User-Flows durchgehen (Neuer User → Onboarding → Erste Session → Analyse → Training)
- UAT-Vorbereitung (Szenarien definieren, Tester einladen)

**Reasoning:**
> Vor Launch muss alles aus einem Guss sein. Phase 04.12 ist der "Integrations-Phase" die sicherstellt, dass nichts isoliert steht.

---

### Phase 04.13: PreCall Intelligence (INSERTED)

**Goal:** PreCall-Recherche — User kann vor Call Recherche-Button drücken, Claude recherchiert Firma/Ansprechpartner, liefert Briefing
**Depends on:** Phase 04.12
**Plans:** 2 plans completed (P01 PreCall-Service + API, P02 PreCall-UI + Integration)

**Items:**
- services/precall_service.py (Claude-Call mit Firma/Person/Website/LinkedIn als Input)
- /api/precall/recherche Endpoint (POST mit Kundendaten)
- PreCall-Button im Live-Setup + PreCall-Briefing als Collapsible Panel
- Caching (Recherche wird pro Firma gecached, 30-Tage TTL)

**Reasoning:**
> Vertriebler haben oft keine Zeit für Recherche. PreCall-Button liefert in &lt; 10s ein Briefing (Firma, Person, letzte News, mögliche Einwände). Spart 09-30min pro Call.

---

### Phase 04.14: CRM & Customer Success (INSERTED)

**Goal:** CRM & Customer Success — tbd
**Depends on:** Phase 04.13
**Plans:** tbd

**Items:**
- tbd

**Reasoning:**
> tbd

---

### Phase 04.15: Rollen, Support & Kompensation (INSERTED)

**Goal:** Rollen, Support & Kompensation — tbd
**Depends on:** Phase 04.14
**Plans:** tbd

**Items:**
- tbd

**Reasoning:**
> tbd

---

### Phase 04.16: Finaler Polish + UAT (INSERTED)

**Goal:** Finaler Polish + UAT vor Launch — Bugfixes, Performance, Copy-Check, E2E-Tests
**Depends on:** Phase 04.15
**Plans:** tbd

**Items:**
- tbd

**Reasoning:**
> tbd

---

### Phase 04.17: PiP Launcher (INSERTED)

**Goal:** PiP Launcher — Picture-in-Picture Overlay für den Live-Assistenten
**Depends on:** Phase 04.16
**Plans:** 5 plans completed (P01 PiP Setup, P02 Tab-System, P03 Kompakt-Modus, P04 CSS-Loading, P05 pagehide cleanup)

**Items:**
- Document Picture-in-Picture API Integration
- Tab-System im PiP (KI, Skript, EWB)
- Kompakt-Modus (reduzierte Ansicht)
- CSS-Loading in PiP-Fenster
- pagehide cleanup (Fenster wird beim Schließen sauber abgebaut)

**Reasoning:**
> PiP erlaubt es dem Berater, während eines Calls sein CRM/Outlook zu nutzen und trotzdem NERVE im Blick zu haben. Die Ursprungs-Implementation (04.17) war Tab-basiert, wurde in Phase 06 komplett ersetzt durch Split-Layout + Streaming.

---

### Phase 5: Launch

**Goal:** Early Access öffnen mit 50 Plätzen + 50% Gründerrabatt
**Depends on:** Phase 4
**Plans:** 2-3 plans (to be broken down)

**Items:**
- Early Access Landing Page aktualisieren (50 Plätze, 50% Rabatt, USP-Sätze)
- Waitlist-Mitglieder einladen (Mail-Template)
- Monitoring-Kanäle definieren (Slack/Mail-Notifications für erste Calls, Payments, Bugs)
- Support-Workflow (Response-Time, Eskalations-Pfad)
- Post-Launch: Feedback-Loop (wöchentlich 1-2 User-Interviews)

**Reasoning:**
> 50 Plätze ist die Zahl aus der ToDo-Liste. 50% Rabatt schafft Dringlichkeit und Loyalität. Support-Workflow verhindert Burnout — 14 Tage/Monat heißt strukturierte Response, nicht 24/7.

---

### Phase 6: PiP Komplett-Rebuild — Neues Layout, Claude Streaming, Skript-Teleprompter, Transparenz-Regler

**Goal:** PiP-Fenster komplett neu aufbauen mit Split-Layout (KI+EWB oben, Skript-Teleprompter unten), Wort-für-Wort Claude-Streaming, semantischer Skript-Position-Erkennung und Hintergrund-Transparenz-Regler
**Requirements**: PIP-01, PIP-02, PIP-03, PIP-04, PIP-05
**Depends on:** Phase 04.17 (PiP Launcher Basis)
**Plans:** 3 plans completed

Plans:
- [x] 06-01-PLAN.md — Split Layout + Setup cleanup (HTML/CSS struktur, consent in live, dual slot scaffolding)
- [x] 06-02-PLAN.md — Backend Streaming (claude_service.py WebSocket streaming, skript_position detection, proactive coaching)
- [x] 06-03-PLAN.md — Frontend JS: pip-launcher.js streaming handlers, dual-slot state machine, consent flow, teleprompter, opacity, proactive fill

### Phase 8: EWB-Qualität & Profil-Tiefe — Launch-kritische Prompt-Iteration, 6 neue Profil-Felder für Authentizität/Branche/Sie-Du, POLISH-55 Behandelt-Semantik-Messinfrastruktur, A/B-Test-Framework für Prompt-Versions, Quality-Gates (80% sofort-vorlesbar, Score-Varianz <±15). Launch-kritisch: blockiert Early-Access-Go-Live wenn EWB-Qualität nicht messbar. Vorbereitet Phase 08.5 (Q&A) + 07.5 (EWB-Feed-Redesign).

**Goal:** EWB-Pipeline liefert konsistent hohe Qualität (80% sofort-vorlesbar, Varianz-Range <30 über Szenarien A/B/C), A/B-Routing zwischen v1-legacy und v2-modular-Prompt ist live, 6 neue Profil-Felder + 3-Block-Tooltip-System + POLISH-55 3-State-Rating-Infrastruktur bringen die für Early-Access-Launch nötige Mess- und Qualitätsbasis.
**Requirements**: EWB-01 through EWB-20 (newly derived — see 08-RESEARCH.md §Phase Requirements, to be back-ported into REQUIREMENTS.md)
**Depends on:** Phase 7
**Plans:** 6/6 plans complete
**Completed:** 2009-04-23 — UAT approved. Wave 7 (100 EWB-Ratings + 15 Training-Sessions + 5 Cold-Calls) bewusst VERSCHOBEN auf nach Phase 08.5: Training-Pipeline nutzt noch alten Prompt (nicht v2-modular) — Wave-7-Daten wären zirkulär. Phase 08.5 enthält Training-Pipeline-Angleichung als Sub-Scope.

Plans:
- [x] 08-01-PLAN.md — Wave 1 Foundation: DB-Migrations (success nullable, anrede column, prompt_versions.is_default) + Backup + Gap-Analyse-Doc (D-01/02/14/26/46)
- [x] 08-02-PLAN.md — Wave 2 Pipeline: prompt_pipeline.py + ewb_pipeline.py + v2-modular Seed + Unit-Tests (D-15/23/24/25/26/09-47)
- [x] 08-03-PLAN.md — Wave 3 Integration: claude_service.py EWB-Pfad-Swap + branche-Heuristik-Migration + ENV-Doc (D-09/24/25)
- [x] 08-04-PLAN.md — Wave 4 UI: Profile-Editor 6 Felder + 3-Block-Tooltips + Beispiel-Modal + Claudian-Review-Checkpoint (D-07-13/09-21)
- [x] 08-05-PLAN.md — Wave 5 Messinfrastruktur: Post-Call-Rating-UI + PreCall-Anrede + Rating-API + ownership-check (D-03-05/09-15)
- [x] 08-06-PLAN.md — Wave 6 Quality-Gate-Tooling: EwbRating Table + Admin-Dashboard + Rating-Template-Page + 3 Test-Szenarien seed (D-22/09-39) + Human-Checkpoint
- [x] Gap-Fix-Run (2009-04-23): CR-01 state_lock, CR-02 anrede-whitelist, Admin-Sidebar-Nav, Login-Redirect-next, Tooltip-Laien-Tauglichkeit, Admin-Intro-Blöcke
- [x] Bug-Hotfixes (2009-04-23): Bug A strftime-crash (admin_ewb._to_datetime), Bug B Login-Modal-next round-trip, Bug C antwort_text/einwand_text Persistierung in ObjectionEvent

---

### Phase 08.5: Universal Response Loop — Launch-kritische Erweiterung des Live-Loops. Claude klassifiziert jede Kundenäußerung in 4 Kategorien (einwand_known / einwand_unknown / frage / smalltalk-none). Unbekannte Einwände (POLISH-56) und offene Fragen werden aus Profil-Daten beantwortet, nie halluzinieren. Integriert: Anrede-UX-Umzug aus PreCall in Skript-Auswahl, Training-Pipeline-Angleichung auf v2-modular (Voraussetzung für Wave 7), FAQ-Feld + Exclusion-Liste. Nutzt Phase 08 prompt_pipeline.py. Aufwand 30-36h. Pre-Launch, löst POLISH-56. (INSERTED)

**Goal:** NERVE reagiert live auf alle Kundenäußerungen — bekannte Einwände (Keyword, bleibt), unbekannte Einwände (Claude-klassifiziert + Antwort aus Profil-Daten), offene Fragen (FAQ-Match). Inkl. Anrede-UX-Umzug aus PreCall in Skript-Auswahl (D-08 bis D-12), Training-Pipeline komplett v2-modular auf prompt_versions (D-07), FAQ-Tabelle + Tabu-Begriffe im Profil-Editor (D-13, D-15). Löst POLISH-56.
**Requirements**: D-01, D-02, D-03, D-04, D-06, D-07, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15, D-16
**Depends on:** Phase 8
**Plans:** 6/6 plans complete

Plans:
- [x] 08.5-01-PLAN.md — Wave 1 DB+Config Foundation: ProfileFaq + FtQaEvent ORM, _migrate() CREATE TABLE, prompt_versions seeds, CLASSIFIER_CONFIDENCE_THRESHOLD, sentence-transformers dependency
- [x] 08.5-02-PLAN.md — Wave 2 qa_pipeline.py: classify_utterance + generate_qa_response + match_faq (sentence-transformers local) + apply_tabu_filter + unit tests
- [x] 08.5-03-PLAN.md — Wave 3 claude_service integration: kw_fired_for_line guard (D-02 prevents 529-loop regression), analyse_loop dispatcher, confidence gate, tabu filter, Socket.IO qa_slot1/qa_soft_hint, frontend Soft-Hint render
- [x] 08.5-04-PLAN.md — Wave 3 Anrede-UX Umzug: PreCall → Skript-Auswahl step, single-script edge case, profile editor ki_ansprache relabeled as Vorauswahl
- [x] 08.5-05-PLAN.md — Wave 3 Training-Pipeline v2-modular: 4 training modules (kunde/sek/scoring/stimmung) routed via prompt_versions + prompt_version-Tag logging
- [x] 08.5-06-PLAN.md — Wave 3 FAQ-UI + Tabu-Begriffe: profile editor FAQ CRUD + tabu tag input, 5 org-isolated API endpoints

### Phase 08.6: Stabilisierung Block A Quick-Wins (INSERTED)

**Goal:** 8 triviale Launch-Blocker und Low-Fixes in < 30 min eliminieren — LB-5/LB-6 State-Writer, LB-12 Ghost-Columns, LB-13 ROI-Card, CORS-Domain, unused Imports, Theme-400, Language-Restrict.
**Depends on:** Phase 08.5
**Plans:** 1/1 ✓ Complete
**Completed:** 2026-04-24

**Items:**
- LB-5 + LB-6: ls.state['org_id'] + ls.state['mode'] Writer in deepgram_service.py:~351
- LB-12: Column-Rename einwaende_total→einwaende_gesamt + einwaende_ok→einwaende_behandelt in admin_views.py:96-97 + analytics.html:24-25
- LB-13: ROI-Card in dashboard.html verstecken (dashboard.py:367-368 Kommentar stehen lassen)
- config.py CORS_ORIGIN: 'https://nerve.app' → 'https://getnerve.app'
- routes/settings.py unused imports raus: redirect, url_for
- routes/organisations.py unused import raus: BillingEvent
- routes/settings.py settings_theme: Silent-Overwrite → 400
- routes/settings.py settings_language: allowed auf ['de','en'] reduzieren

**Reasoning:**
> MASTER-AUDIT v2 Block A — unverzüglich umsetzbar, kein Risiko. Löst LB-5/LB-6/LB-12/LB-13 (4 Launch-Blocker) + 4 LOW/MEDIUM. Jeder Task einzelner atomarer Commit, dann git push.

---

### Phase 08.7: Stabilisierung Block H — Test-False-Greens raus (INSERTED)

**Goal:** Test-Suite von Source-Presence-basierten False-Green-Tests befreien, damit Block I (Dead-Code-Prune) danach ohne rote Tests möglich ist. 6 Tasks, ~4h, mechanisch.
**Depends on:** Phase 08.6
**Status:** Complete — 2026-04-25 ✓

**Tasks (aus MASTER-AUDIT-v2 Block H):**
1. `tests/test_claude_service_phase08.py` — 7 inspect.getsource-Tests löschen oder auf Mocked-Integration umbauen
2. `tests/test_08_5_05_training_pipeline_t2.py` — 11/14 Source-Presence-Tests löschen, 3 Core-Tests mit Mock-Client behalten
3. `tests/test_phase_08_migration.py` — 6 Tests auf Fresh-DB-Migration umbauen ODER nach tests/archive/ verschieben
4. `tests/test_qa_pipeline_t1.py` — 4 RED-Gate-Tests löschen (RED-Gate ist vorbei)
5. `tests/tts_comparison.py` → `scripts/` verschieben (ist kein pytest-Test, sondern print-basiertes Vergleichsscript)
6. `CLAUDE.md` — Regel ergänzen: "Test ist grün nur wenn Integration-Assertion (DB-Write/API-Response/State-Mutation), nicht Source-Presence via inspect.getsource oder hasattr"

**Reasoning:**
> MASTER-AUDIT v2 Block H — Pflicht-Vorarbeit für Block I (Dead-Code-Prune). Tests die via inspect.getsource/hasattr prüfen ob Code *existiert* schützen aktiv Dead-Code vor dem Prune und blockieren H-3/H-4 Löschung. Jeder Task ein atomarer Commit. pytest-Baseline vor Beginn, pytest nach jedem Task.

---

### Phase 08.8: Stabilisierung Block I — Dead-Code-Prune (INSERTED)

**Goal:** ~500-800 Zeilen toten Code entfernen. 11 atomare Tasks aus MASTER-AUDIT-v2 Block I — analysiere_mit_claude_streaming, _build_system_prompt, _get_erfolgsquoten löschen (H-3/H-4); Coach-Live-Tipp-Routes entfernen (H-27); Personality-Save-Route entfernen (H-28); 9 Orphan-Routes prunen; 3 Orphan-Templates löschen; ewb_top2-Writer/Reader-Cleanup (F-8/H-36); Legacy-opener vs. openerItems Entscheidung; finetune_logging.py + FtPipelineEvent-Tabelle droppen (H-1, DB-Migration). pytest grün nach jedem Commit.
**Depends on:** Phase 08.7
**Status:** Complete — 5/5 plans complete
**Completed:** 2026-04-25

**Plans:** 5 plans

Plans:
- [x] 08.8-01-PLAN.md — Wave 1: H-3 + H-4 + H-11 (analysiere_mit_claude_streaming, _build_system_prompt, _get_erfolgsquoten, if/else-Branch, CONCERNS.md)
- [x] 08.8-02-PLAN.md — Wave 2: H-27 Coach-Live-Tipp-Routes + H-28 Personality-Save-Route
- [x] 08.8-03-PLAN.md — Wave 3: 6 Orphan-Routes (swap_roles, status, skripte, feedback/quick, training/postcall-analysis, training/ping)
- [x] 08.8-04-PLAN.md — Wave 4: 2 Orphan-Templates + ewb_top2 Cleanup (F-8/H-36) + opener-Entscheidung
- [x] 08.8-05-PLAN.md — Wave 5: H-1 log_pipeline_event/finetune_logging Entfernung (LETZTER)

---

### Phase 08.9: Stabilisierung Block C Schema-Drift-Cleanup (INSERTED)

**Goal:** Schema-Drift zwischen Onboarding-Wizard, BRANCHE_TEMPLATES und QA-Pipeline beseitigen. 5 atomare Tasks: LB-11 Onboarding-Redirect reaktivieren; H-31/HSR-2 BRANCHE_TEMPLATES auf `basis.*`-Schema umstellen; Wizard-Create-Endpoint auf `basis.*`-Schema angleichen; LB-3 QA-Pipeline Komplett-Fix (profile_data aus Live-Session laden, confidence als float/None, inkl. WR-01/WR-03 Sub-Tasks); H-25 Rollen-Check `_rolle()` einbauen. Pytest-Baseline 265 passing nach jedem Commit.
**Depends on:** Phase 08.8
**Status:** Complete — 4/4 plans done (2026-04-25)

Plans:
- [x] 08.9-01-PLAN.md — LB-11 Onboarding-Redirect + H-31/HSR-2 BRANCHE_TEMPLATES basis.*-Schema + DB-Migration Demo-Profile (complete 2026-04-25)
- [x] 08.9-02-PLAN.md — Wizard-Create-Endpoint auf basis.*-Schema (complete 2026-04-25)
- [x] 08.9-03-PLAN.md — LB-3/WR-01/WR-03 QA-Pipeline Komplett-Fix (complete 2026-04-25)
- [x] 08.9-04-PLAN.md — H-25 Rollen-Check _rolle() einbauen (complete 2026-04-25)

---

### Phase 08.10: Stabilisierung Block B Auth-Härtung (INSERTED)

**Goal:** Flächendeckende Security-Baseline: CSRF-Schutz, Session-Cookie-Hardening, Session-Fixation-Fix, Brute-Force-Schutz, Org-Scoping-Assertion, OAuth oauth_id UNIQUE-Constraint, Microsoft-OAuth Email-Hijacking-Mitigation, zentraler Error-Handler + Frontend-Traceback-Filter, Route-Exception-Leaks beseitigen.
**Depends on:** Phase 08.9
**Plans:** 6 plans

Plans:
- [x] 08.10-01-PLAN.md — Wave 1: LB-7 Error-Handler Traceback-Leak + H-15 Route-Exception-Leaks + Frontend-Traceback-Filter
- [x] 08.10-02-PLAN.md — Wave 2: LB-10 Session-Cookie-Hardening (FLASK_DEBUG-aware)
- [x] 08.10-03-PLAN.md — Wave 3: LB-9 CSRF Backend (CSRFProtect+Exempts) + Frontend (X-CSRFToken in allen JS-Files)
- [x] 08.10-04-PLAN.md — Wave 4: H-17 Session-Fixation-Fix + M-AU-1 Org-Scoping-Assertion
- [x] 08.10-05-PLAN.md — Wave 5: H-20 flask-limiter Brute-Force-Schutz
- [x] 08.10-06-PLAN.md — Wave 6: H-21 oauth_id UNIQUE-Constraint + H-18 Microsoft-OAuth Email-Hijacking-Mitigation

**Reasoning:**
> MASTER-AUDIT v2 Block B — Flächendeckende Auth-Härtung vor Launch. Cross-AI-Plan-Review mit Gemini + Claude nach Plan-Phase.
> WICHTIG: Phase 08.11 (Block F) muss VOR Phase 08.10 (Block B) ausgeführt werden — 08.10-Pläne werden nach 08.11-Done neu geplant.

---

### Phase 08.11: Stabilisierung Block F Classic-View-Deprecation (INSERTED)

**Goal:** Classic-View-Deprecation — PiP-only Architektur, ~2500 Zeilen Classic-Code entfernen
**Depends on:** Phase 08.9
**Plans:** 4/4 complete (DONE 2026-04-25)

**Items:**
- [x] Plan 01: Backend-Cleanup Wave 1 — 10 Classic-Routen + /live redirect + app.py cleanup (c05e548)
- [x] Plan 02: Frontend-Cleanup Wave 2 — app.js + app.html geloescht + /live Template-Refs auf NerveLauncher.open() (e89e2bd)
- [x] Plan 03: Wave 3 Legacy-Opener-Cleanup + test_ft_seed Fix — legacyOpener aus pip-launcher.js entfernt, test_ft_seed.py auf 4 Module korrigiert (42a7c29 + 57605d9)
- [x] Plan 04: Wave 4 Manual Smoke-Test-Checkliste + git push origin main (62d50d9)

**Reasoning:**
> MASTER-AUDIT v2 Block F — Classic-View komplett raus (PiP-only). Reihenfolge-Korrektur durch Cross-AI-Review (Gemini): Block F wird VOR Block B (Phase 08.10) ausgeführt, weil F die Routen /api/frage, /api/ewb_trigger und Classic-Socket-Handler entfernt. Würde B (Auth-Härtung, CSRF, Error-Handler) zuerst laufen, würden diese Routen zuerst gehärtet und dann gelöscht = Doppelarbeit. Phase 08.10 (Block B) bleibt mit existierendem Plan erhalten — wird nach Abschluss von 08.11 neu geplant da sich der Code-Stand ändert (~600 Z. app.js gelöscht, Classic-Routen weg). Pflicht-Lektüre für Planner: .planning/audits/MASTER-AUDIT-v2.md Sektion "BLOCK F".

---

### Phase 08.12: Stabilisierung Cleanup-Hotfix DB-Naming + User-Migration (INSERTED)

**Goal:** Zwei Post-Deploy-Bugs aus Block-F-Live-Deploy beheben: (1) DB-Naming-Cleanup — salesnerve.db löschen, .env korrigieren, Rename-Code in app.py:710-719 entfernen, Kommentar-Drift in services/ + scripts/ fixen. (2) Block-C-User-Migration-Lücke — LB-11 Onboarding-Redirect reaktiviert ohne Migration für bestehende User (onboarding_done=False default) → idempotente Migration in app.py einbauen.
**Depends on:** Phase 08.11
**Plans:** 0 plans — not planned yet

---

### Phase 08.13: Stabilisierung Block E — Cost-Tracking + Caching + Sonnet-Upgrade (INSERTED)

**Goal:** Billing-Integrität, Prompt-Caching, Sonnet-Qualitätsupgrade und Latenz-Messung in einem einmaligen Durchgang durch alle Claude-Call-Sites. Löst LB-4 (user_id im Cost-Tracker), konsolidiert 3 verbliebene inline-Anthropic-Clients auf `claude_service.claude_client`, implementiert POLISH-58 Prompt-Caching (`cache_control: {type: "ephemeral"}`) für alle Call-Sites mit System-Prompt ≥ 4000 Token (EWB, QA, Analyse-Loop), upgradet User-sichtbare Outputs auf Sonnet 4.5 (EWB-Generation, QA-Response, PostCall-Insights, Weekly-Summary, Training-Help, CRM, PreCall), hält Haiku 4.5 für Analyse-Loop (4s-Polling latenz-kritisch) + Training-Dialog (ElevenLabs-Cost + Realismus), führt ENV-basierte Model-Switchbarkeit pro Call-Site in config.py ein (MODEL_EWB, MODEL_QA, MODEL_ANALYSE, MODEL_OBJECTION etc.), ergänzt ApiCostLog um `latency_ms` + `call_site` Spalten (Schema-Migration), findet + ersetzt alle 17 hardcoded-Model-Stellen durch ENV-Variablen, implementiert H-9 Socket-Lifetime-Messung (Deepgram STT-Sekunden statt Socket-Lifetime), und konsolidiert pro-Request-HTTP-Sessions (H-12 Connection-Pooling). Kombinations-Hebel: Sonnet gecacht ist ~2.7× billiger als Haiku ungecacht für input-schwere Calls (4000-Token System-Prompt).
**Requirements:** LB-4, POLISH-58, H-9, H-12, H-22, H-29
**Depends on:** Phase 08.12
**Launch-relevant:** true
**Plans:** 5 plans

Plans:
- [x] 08.13-01-foundation-PLAN.md — config.py MODEL_*-Konstanten + DB-Migration latency_ms/call_site + cost_tracker-Erweiterung
- [x] 08.13-02-client-consolidation-PLAN.md — 5 inline-Anthropic-Clients konsolidieren auf shared claude_client (H-12) + dashboard Cost-Hook (H-29)
- [x] 08.13-03-callsite-migration-PLAN.md — alle 21 model-Strings auf config.MODEL_*, training_service/crm Cost-Hooks, H-22 Exception-Handling (3a0fd57 + 85862fb)
- [x] 08.13-04-prompt-caching-PLAN.md — POLISH-58: cache_control=ephemeral fuer EWB + QA + Analyse-Loop (b2c473f + 4282e25)
- [x] 08.13-05-deepgram-verification-PLAN.md — H-9 STT-Sekunden-Fix + pytest Abschluss-Verifikation (09bd6a9 + 047cb3f)

---

### Phase 08.14: Claude-Code-Workflow-Polish + Block-E-Lessons-Learned (INSERTED)

**Goal:** Werkzeugschärfung vor Block N: 4 konkrete GSD-Setup-Lücken schließen (ruff-Hook, Context7-MCP, Sub-CLAUDE.md für routes/, Determinismus-Regel 13) + 2 Lessons-Learned aus Block-E-Live-Deploy integrieren (ApiRate-Seeding in _migrate() + Sonnet-Date-Suffix in config.py).
**Depends on:** Phase 08.13
**Plans:** 2/2 plans executed — **COMPLETE (2026-04-27)**

Plans:
- [x] 08.14-01-PLAN.md — Wave 1: ruff-Hook, Context7-MCP, routes/CLAUDE.md, Regel 13
- [x] 08.14-02-PLAN.md — Wave 2: config.py Sonnet-Date-Suffix + app.py ApiRate-Seed

---

### Phase 08.17: Block N Phase A — Prompt-Integrations-Audit (INSERTED)

**Goal:** Matrix erstellen die zeigt welche Profil-Felder in welchen Prompt-Pfaden tatsaechlich ankommen — feldgenau, pfadgenau. Basiert auf existierendem Audit (2026-04-24) der gegen aktuellen Code-Stand (post-08.14) verifiziert und aktualisiert wird.
**Komplexitaet:** 🟡 mittel — Cross-AI Pflicht (Andre-Decision 2026-04-27)
**Depends on:** Phase 08.14
**Plans:** 1 plan

Plans:
- [x] 08.17-01-PLAN.md — Audit-Verifikation: profil-prompt-integration-matrix.md gegen post-08.14 Code-Stand aktualisieren (COMPLETE 2026-04-27, commit 82a14f5)

**Items:**
- Existierenden Audit (`.planning/audits/profil-prompt-integration-matrix.md`, Stand 2026-04-24) gegen aktuellen Code verifizieren
- Matrix updaten fuer Aenderungen aus Phasen 08.6-08.14 (Dead-Code-Prune, Classic-View-Deprecation, Prompt-Caching, Model-Konsolidierung)
- Findings-Liste mit Zahlen (X tot, Y teilweise, Z voll integriert)
- Top-Ueberraschungen dokumentieren
- Quellen-Referenzen mit aktuellen Datei:Zeile-Verweisen
- Audit-Stand-Datum auf 2026-04-27 aktualisieren

**Reasoning:**
> Phase 08.5-Audit-Befund: ~90% des Profils kommt nicht im Live-PiP an. Audit-Datei existiert bereits (2026-04-24) aber ist vor grossem Cleanup-Block (08.6-08.14) erstellt — muss gegen aktuellen Code verifiziert werden. Foundation fuer Phase 08.18 (Sales-Literatur-Research) + Phase 08.19 (Pydantic-Schema-Redesign).

---

### Phase 08.18: Block N Phase B — Sales-Literatur-Research + Branchen-Spezifika PreCall (INSERTED)

**Goal:** Drei Recherche-Stränge als Input für Phase 08.19 (Pydantic-Schema-Redesign) und 08.20 (Pipeline-Re-Wire): (1) Sales-Literatur-Synthese (8 EN + 5 DE Autoren) — Profil-Inputs, Frame-Strukturen, Einwand-Muster, No-Gos pro Autor. (2) Branchen-Spezifika fuer PreCall — welcher Recherche-Fokus pro Branche (Maschinenbau/SaaS/Versicherung/Beratung/etc.)? (3) Reihenfolge eines Voll-Profil-Prompts — Sales-Trainer-Konsens + Anthropic Best-Practices (Lost-in-Middle, System-vs-User-Aufteilung).
**Komplexitaet:** 🟡 mittel — Cross-AI Pflicht (Andre-Decision 2026-04-27)
**Depends on:** Phase 08.17

**Items:**
- Sales-Literatur-Synthese: SPIN Selling, Challenger Sale, Sandler, Straight Line, Value Selling, Predictable Revenue, Little Red Book, Pitch Anything (EN); Tim Taxis, Dirk Kreuter, Stephan Heinrich, Martin Limbeck, Hans-Uwe Köhler (DE) — AUSGESCHLOSSEN: Uwe Beyreuther
- Pro Autor: Profil-Inputs / Frame-Struktur / Einwand-Muster / No-Gos
- Branchen-Spezifika PreCall: Maschinenbau, SaaS, Versicherung, Beratung, Werkzeug-Verkauf, Field-Sales — pro Branche: typischer PreCall-Vorbereitungs-Bedarf, Datenquellen, Recherche-Fokus
- Reihenfolge Voll-Profil-Prompt: Sales-Trainer-Konsens + Anthropic Best-Practices (Lost-in-Middle)
- Output-Dateien: `.planning/research/sales-coaching-literatur-synthese.md` + `.planning/research/branchen-precall-spezifika.md`

**Reasoning:**
> Audit (08.17) zeigt: ~50-60% der Profil-Felder landen nie in einem Live-Prompt, PreCall-Briefing fließt nicht in EWB. Bevor das Schema (08.19) und die Pipeline (08.20) umgebaut werden, Grundlage schaffen: was sagen Experten was rein muss, und wie muss es strukturiert sein damit es wirkt. Andre-Decision 2026-04-27 abend: ALLES in sinnvoller Reihenfolge im EWB-Prompt, branchenspezifische PreCall-Recherche als Steuerungs-Input fuer den LLM.

**Plans:** 3/3 plans executed — COMPLETE
**Status:** Complete — 2026-04-27 ✓
**Completed:** 2026-04-27

Plans:
- [x] 08.18-01-PLAN.md — Sales-Literatur-Synthese (5 thematische Sektionen + Reihenfolge-Sektion + Schema-Bullets)
- [x] 08.18-02-PLAN.md — Branchen-Spezifika Stufe 3a (Verteilungs-Recherche DACH + USA)
- [x] 08.18-03-PLAN.md — Branchen-Spezifika Stufe 3b (Tiefen-Cluster-Analyse, haengt von Plan 02 ab)

---

### Phase 08.19: Block N Phase C — Pydantic-Schema-Redesign + Migration (INSERTED) ✅ COMPLETE 2026-04-27

**Goal:** Profil-Datenmodell sauber neu definieren — Pydantic v2 ProfileSchema mit 6 neuen Feldern aus 08.18 (zielkunde.unternehmensgroesse / buying_committee / statusquo / zeithorizont, value.roi_argumente, einwaende[].einwand_typ), 7 Felder eliminieren (B2C-Felder alter/einkommensniveau/lebenssituation, schmerzen.trigger, ki.stil, erlaubnis), consent_text als meta.consent_text behalten (DSGVO-relevant fuer Meeting-Modus-Consent-Modal, UI-only-Markierung). Schema-Drift opener/pitch (top-level vs basis.*) bereinigen. Idempotente verlustfreie Migration fuer bestehende Profile in DB (Andre's User + Demo-Profile IDs 2/3/4). Wizard/UI auf neues Schema anpassen. Output: services/profile_schema.py (Pydantic v2) + idempotente _migrate()-Erweiterung + Wizard-UI-Anpassungen + Test alle 4 Profile laden verlustfrei.
**Komplexitaet:** 🔴 komplex — Schema-Migration ist DB-Risiko, Wizard-UI muss konsistent sein. Cross-AI Pflicht (doppelter Cycle empfehlenswert).
**Depends on:** Phase 08.18

**Input:**
- `.planning/research/sales-coaching-literatur-synthese.md` (Sektion E + Schema-Empfehlungen-Bullets)
- `.planning/research/branchen-precall-spezifika.md` (Schema-Empfehlungen fuer 08.20-Branchen-Steuerung)
- `.planning/audits/profil-prompt-integration-matrix.md` (Schema-Drift-Findings opener/pitch)

**NICHT in 08.19 (gehoert zu 08.20 Pipeline-Re-Wire):**
- build_profile_context() Reihenfolge-Refactor
- System/User-Message-Split
- Manual-EWB-Button mit Profil-Kontext fuettern
- _SYSTEM_PROMPT_QA mit {profile_context} erweitern
- PreCall-Briefing-Inject in EWB-Prompt
- Sonnet-Default fuer EWB-Streaming

**Plans:** 4 plans

Plans:
- [x] 08.19-01-PLAN.md — services/profile_schema.py (Pydantic v2 ProfileSchema + _migrate_profile_data) (317c0a2)
- [x] 08.19-02-PLAN.md — DB-Level Migration aller Profile auf schema_version=2 + opener/pitch Sync + consent_text dual-write (b0d837c)
- [x] 08.19-03-PLAN.md — Read/Write-Pfad Integration (wizard_create, bearbeiten, precall_service opener/pitch -> ProfileOpener) (ee9fa3c)
- [x] 08.19-04-PLAN.md — Wizard-UI unternehmensgroesse Chip-Select + UI-Hint + Validation (f2a23f1)

---

### Phase 08.19.1: Block N Phase C.1 — Schema-Realität-Kalibrierung + extra='forbid' (INSERTED)

**Goal:** Pydantic-Profil-Schema (services/profile_schema.py) komplett auf die reale Profil-JSON-Struktur aller 6 Production-Profile kalibrieren, dann extra='forbid' (strict-Mode) wieder aktivieren. Aktuell läuft Schema mit extra='ignore' als Hotfix aus 08.19 — das ist Schuldzettel der jetzt zurückgezahlt wird.
**Komplexität:** 🟡 mittel
**Depends on:** Phase 08.19 (initial-Schema), Phase 08.19.2 (tote Felder + Sektionen-Polish), Phase 08.19.3 (FAQ-mode-Feld)

**Pflicht-Tasks:**
1. Echtes Profil-JSON aller 6 Production-Profile als Spec-Input ziehen (SQL-Export aus profiles-Tabelle)
2. Pro Feld: Type analysieren (String / List / Dict / Union), Pflicht-vs-Optional klären, mit 08.18-Sales-Wisdom-Empfehlungen Sektion E abgleichen
3. daten.fragen-Key-Removal aus allen 6 Profilen + aus Schema (wurde durch 08.19.3-FAQ-Konsolidierung obsolet — alles liegt jetzt in profile_faqs)
4. profile_faqs.mode-Feld als Teil des kalibrierten Schemas berücksichtigen (literal vs. ki_generated)
5. Schema-Update mit allen real existierenden Feldern + den 6 neuen aus 08.18 Sektion E
6. Migration _migrate_profile_data() erweitern um Type-Konvertierungen wo nötig (z.B. nogos List[Object] standardisieren)
7. extra='forbid' wieder aktivieren
8. Test gegen alle 6 Profile dass model_validate(strict=True) durchgeht — Test-Suite-Pflicht
9. Cross-AI Pflicht (Block-N-Phase + Andre-Decision: alle Block-N-Phasen kriegen Cross-AI)

**Plans:** 5/5 plans complete ✓

Plans:
- [x] 08.19.1-01-PLAN.md — Production-Profil-Analyse (Hetzner SSH-Dump + KEY-FINDINGS.md)
- [x] 08.19.1-02-PLAN.md — Schema-Kalibrierung (ProfileSchema + BasisSchema Dead-Fields)
- [x] 08.19.1-03-PLAN.md — _migrate_profile_data() v2->v3 (einwaende/phasen merge, fragen/branche drop)
- [x] 08.19.1-04-PLAN.md — DB-Level Batch-Migration alle Profile auf v3 (app.py _migrate()) — checkpoint BESTÄTIGT: alle 4 Profile v3, Idempotency OK. D-03: audit_log nur print(), kein DB-Insert (Code-Review-Fix ausstehend)
- [x] 08.19.1-05-PLAN.md — extra='forbid' aktivieren + Test-Suite — checkpoint APPROVED 2026-04-29: 27/27 pytest, extra='forbid' enforcement confirmed, alle 4 Profile validieren. Code-Review-Fix ausstehend: audit_log Test-Pollution (TestF1/F3/F4)

---

### Phase 08.19.2: Profil-Editor UX + Design-Aufräumung (INSERTED)

**Goal:** Profil-Editor visuell aufräumen und UX-Konsistenz herstellen — Frontend-only, kein Schema-Change, kein Backend-Touch. Kern-Deliverables: Heading-Hierarchie korrigieren (`.sec-title` von 12px auf 16-18px), Inline-Styles in CSS-Klassen extrahieren (8 Stellen), Hardcoded-Farben durch CSS-Variablen ersetzen, Sektions-Doppelungen auflösen (Häufige Fragen + FAQ-Datenbank → eine Sektion; Gesprächsleitfaden + Gesprächsphasen konsolidieren), Tippfehler-Fix, Einwände-Sub-Felder logisch umsortiert + ausklappbar (default kollabiert, nur Einwandtext sichtbar), `+Skript hinzufügen`-Bug gefixt, Education-Hints Stub (1-2 Sätze pro Sektion welche Wirkung das Feld hat), Branchen-Sektion UI-Skelett stub (Content-ready in 08.22). Andre will sichtbares Resultat vor Schema-Hygiene-Kalibrierung (08.19.1).
**Komplexität:** 🟡 mittel — Cross-AI Pflicht (Andre-Decision für Block-N-Phasen)
**Depends on:** Phase 08.19

**Input:**
- `.planning/research/profil-editor-design-audit-2026-04-28.md` — Audit: Heading-Drift, Farb-Drift, 8 Inline-Style-Stellen, Sektions-Doppelungen, Bug-Liste
- `.planning/research/profil-editor-ux-best-practices-2026-04-28.md` — UX-Best-Practices: Sidebar-Layout, Reihenfolge-Logik, Inline-Education-Patterns, Visual-Hierarchy

**NICHT in 08.19.2 (gehört zu anderen Phasen):**
- build_profile_context() Reihenfolge-Refactor (08.20)
- Kaufsignale / Verkaufstechniken / Übergangsziele in EWB-Prompt (08.20)
- Branchen-Template-Wizard funktional mit Daten-Vorbefüllung (08.22)
- Profil-Wizard erster Setup-Flow (08.22)
- Schema-Realität-Kalibrierung + tote Felder säubern (08.19.1)

**Plans:** 4/4 plans complete

Plans:
- [x] 08.19.2-01-PLAN.md — nerve.css: neue CSS-Variablen + Typography-Korrekturen + alle neuen Klassen (Wave 1)
- [x] 08.19.2-02-PLAN.md — profile_editor.html: 15 Sektionen -> 6 Gruppen, Sidebar, Slider-Entfernung, Branche Sektion #1 + Wisdom-Stub (Wave 2)
- [x] 08.19.2-03-PLAN.md — profile_editor.html: CSRF-Fix crudList, Erlaubnisfrage+Pitch Multi-Entry, Accordion default-kollabiert, Inline-Style-Extraktion (Wave 3)
- [x] 08.19.2-04-PLAN.md — profile_editor.html: sec-hint Texte, field-desc Hilfstext, EWB-Platzhalter, Human-Verifikation (Wave 4)

---

### Phase 08.19.3: Block N FAQ-Konsolidierung mit Toggle (INSERTED — 2026-04-28)

**Goal:** Zwei überlappende UI-Sektionen ("Häufige Fragen" aus `daten.fragen` JSON + "FAQ-Datenbank" aus `profile_faqs` DB) zu einer einzigen Sektion konsolidieren. Kern: `mode`-Spalte zu `profile_faqs` + Backfill-Migration + `daten.fragen` → `profile_faqs` Migration mit mode='ki_generated'. Toggle pro FAQ-Card steuert: `literal` (Embedding-Match → wortwörtlicher Auswurf, kein LLM-Call) vs. `ki_generated` (KI generiert Antwort aus Kontext). `match_faq()` Caller filtert mode-aware. `build_profile_context()` inkludiert ALLE FAQs als Q+A-Block (Foundation für 08.20). "Häufige Fragen"-Sektion aus UI entfernen.
**Komplexität:** 🔴 (Schema-Migration + Backend-Logik + Frontend)
**Depends on:** Phase 08.19.2
**Andre-Decision:** 2026-04-28 abend — KI-Antworten als Default, wortwörtlich nur für Compliance-kritische Fragen. Cross-AI Pflicht (Block-N-Decision).

**Plans:** 4 plans

Plans:
- [x] 08.19.3-01-PLAN.md — Schema-Migration: profile_faqs.mode Spalte + Backfill + daten.fragen → profile_faqs
- [x] 08.19.3-02-PLAN.md — Backend: match_faq() mode-Filter + build_profile_context() FAQ Q+A-Block
- [x] 08.19.3-03-PLAN.md — Routen: GET/PUT FAQ-Endpoints mode-aware
- [x] 08.19.3-04-PLAN.md — Frontend: sec-fragen entfernen + Toggle-Widget + renderFaqRow() + Human-Verify

---

### Phase 08.19.4: Multi-User-Profile-Session-Scoping (INSERTED — 2026-04-29)

**Goal:** `services/live_session.py` hat `active_profile_data` + `active_profile_name` als Modul-globalen State — ein Python-Worker = ein einziges aktives Profil für alle gleichzeitig aktiven User. Bei Multi-User-EA-Launch (50 Plätze auf einem Flask-Worker) sieht User B im selben Worker User A's Profil → DSGVO-Cross-Session-Data-Leak + 100% falsch personalisierte EWBs. `_load_initial_profile()` in `app.py` lädt beim Boot Profil 7 (Admin-Org "NERVE Alpha") als globales Default — user-agnostisch. Fix: Profile-Lookup user/session-scoped machen (Flask `g` für HTTP-Pfade, per-Connection-State für WebSocket-Pfade). Alle Caller in `claude_service.py`, `qa_pipeline.py`, EWB-Prompt-Builder, Coach-Pipeline, Training-Module umstellen. DSGVO-Audit aller Modul-Globalen in `live_session.py`.
**Komplexität:** 🔴 (DSGVO-Pflicht + Architektur + Multi-Threading) — Cross-AI Pflicht. Plan-Phase mit Pro-Modell verifizieren (Gemini-Pro statt Flash) wegen Architektur-Tiefe.
**Depends on:** Phase 08.19.1 (Schema sauber)
**Voraussetzung für:** Phase 08.20 (Pipeline-Re-Wire darf nicht auf kaputter Profile-Lookup-Foundation bauen)

**Plans:** 4 plans in 3 waves

Plans:
- [ ] 08.19.4-01-PLAN.md — Per-SID dict infrastructure + _load_initial_profile() deletion
- [ ] 08.19.4-02-PLAN.md — SID lifecycle hooks in deepgram_service + remove module globals
- [ ] 08.19.4-03-PLAN.md — Rebuild analyse_loop/coaching_loop + migrate 7 get_active_profile() callers
- [ ] 08.19.4-04-PLAN.md — D-05 route cleanup + delete deprecated wrappers + DSGVO isolation tests

---

### Phase 08.19.5: Per-User-Daten-Trennung + WebSocket-Auth (INSERTED — 2026-05-02)

**Goal:** ~25 Modul-Globale in `services/live_session.py` (is_paused, state, transcript_buffer, conversation_log, coaching_buffer, session_meta, speaker-Tracking, BOF-Counter etc.) sind shared across all concurrent users on one Flask worker — DSGVO-Cross-Session-Data-Leak + falsch personalisierte EWBs. Zusätzlich: WebSocket-Verbindungen haben keine Auth-Prüfung im connect-Handler — theoretisch kann jede erratene SID mithören. Phase liefert: (1) Alle verbleibenden Modul-Globalen auf per-SID-Dicts migrieren (Pattern: `_per_sid_*` wie bereits `_per_sid_profile`, `_per_sid_transcript`, `_per_sid_coaching_buffer`), (2) `is_paused` per-SID statt global, (3) WebSocket connect-Handler prüft `session['user_id']` vor Accept, (4) Route-Konflikt `/api/feedback` (zwei Blueprints) auflösen, (5) Tote Tabellen `ft_objection_events` + `ft_qa_events` entfernen, (6) `_load_profile_cache()` Integration-Test + `vorwissen_level`-Chain-Test + `streame_manual_ewb_variante()` Error-Propagation-Fix.
**Komplexität:** 🔴 (DSGVO-Pflicht + Threading + WebSocket-Auth + Multi-File) — Cross-AI Pflicht vor Execute.
**Depends on:** Phase 08.19.4 (per-SID infrastructure als Foundation — kann parallel laufen wenn 08.19.4 noch offen)
**Voraussetzung für:** Phase 08.20 Pipeline-Re-Wire (saubere SID-Foundation)

**Plans:** 4 plans in 3 waves

Plans:
- [x] 08.19.5-01-PLAN.md — Wave 1: Dead code cleanup (ft_objection_events reader, models, migration), route rename /api/session-rating, EWB error propagation fix (COMPLETE 2026-05-02)
- [x] 08.19.5-02-PLAN.md — Wave 2a: live_session.py init_session_state extension + per-SID helpers + deepgram_service.py is_paused migration + WS auth handler (COMPLETE 2026-05-02)
- [x] 08.19.5-03-PLAN.md — Wave 2b: claude_service.py is_paused + analysiert_bisher loop migration (parallel to Plan 02) (COMPLETE 2026-05-02)
- [x] 08.19.5-04-PLAN.md — Wave 3: New tests (REQ-06/07/08/01 isolation) + fix 2 pre-existing test_session_scoping failures (COMPLETE 2026-05-02)

---

### Phase 08.19.5.1: Per-User-Trennung Restposten — WR-01 + WR-02 (INSERTED — 2026-05-03)

**Goal:** WR-01 und WR-02 aus dem Phase-08.19.5-Code-Review nachmigieren: `_write_ft_assistant_event` liest Session-Kontext per-SID statt aus dem Modul-Globalen `ls.state`; `analyse_loop:916` liest `active_learning_cards` per-SID statt global. Danach ist Multi-User-Daten-Trennung 100% abgeschlossen.
**Status:** COMPLETE (2026-05-03)
**Verification:** passed (5/5 must-haves)

**Plans:** 1 plan in 1 wave

Plans:
- [x] 08.19.5.1-01-PLAN.md — Wave 1: WR-01 _write_ft_assistant_event per-SID + WR-02 learning-cards per-SID + tests (COMPLETE 2026-05-03)

---

### Phase 08.19.5.2: UI-Audit + akute Hotfixes (INSERTED — 2026-05-03)

**Goal:** Systematischer UI-Inventur-Durchgang aller Seiten (Wave 1) + Fix der 4 akuten Pre-Launch-Bugs aus 08.19.5-UAT (Wave 2), bevor DSGVO-Härtung (08.19.6) obendrauf gebaut wird.
**Komplexität:** 🟡 mittel (Multi-File-Edits, Frontend + Backend). PiP-Bug evtl. 🔴.
**Depends on:** Phase 08.19.5.1 ✅ (Multi-User-Daten-Trennung komplett)
**Voraussetzung für:** Phase 08.19.6 (DSGVO-Härtung braucht sauberes UI-Fundament — "Dach-vor-Keller")

**Wave 1 — UI-Audit (Claudian + Andre gemeinsam):**
1. Inventur ALLER Seiten: Dashboard, Profile, Live-Call, Trainings, Coach-Dashboard, Admin-Bereich, Settings, Logs, Changelog, Performance, Onboarding
2. Pro Seite: was steht drauf, was ist klickbar, was passiert beim Klick, funktioniert der Klick
3. Discoverability-Check: wie würde ein neuer User Feature X finden? Wenn "gar nicht" → Bug
4. Tote-Buttons-Check: Buttons/Links die nichts tun
5. Findings-Bericht: `03 Planung/UI-Audit-Ergebnis-2026-05-XX.md` sortiert nach kritisch / mittel / kosmetisch
6. Output ist Foundation für Block O Teil 2 (Visual-Polish via Claude Design)

**Wave 2 — Akute Hotfixes (GSD):**
1. 🔴 Profil-Wizard reparieren — Frontend↔Backend-Drift fixen, CSRF-Token, Feldnamen abgleichen (PRE-LAUNCH-BLOCKER)
2. 🟡 Sessions im Dashboard klickbar machen — onclick-Handler in dashboard.html (PRE-LAUNCH-BLOCKER)
3. 🟡/🔴 PiP-Schließ-Bug bei Tab-Wechsel fixen — Picture-in-Picture-Web-API oder Service-Worker
4. 🟢 UX-Mini: "Profil" → "Profile" Umbenennung in Hauptnavi
5. Plus alles was Wave 1 als kritisch/mittel findet

**Plans:** 4 plans

Plans:
- [ ] 08.19.5.2-01-PLAN.md — Wave 1: Autonomer UI-Code-Scan + Checkpoint André+Claude Live-Durchgang → Findings-Bericht
- [ ] 08.19.5.2-02-PLAN.md — Wave 2a: Profil-Wizard Fix (get_json + CSRF + Feldnamen + zielkunden/unternehmensgroesse)
- [ ] 08.19.5.2-03-PLAN.md — Wave 2b: Dashboard Session-Row onclick + Nav-Label + PiP Re-Launch-Flow
- [ ] 08.19.5.2-04-PLAN.md — Wave 2c: Wave-1-kritische Findings (Scope nach Checkpoint)

---

### Phase 08.19.5.4: Dark-Mode-Reste raus + Modal im neuen Design (INSERTED — 2026-05-05) 🟡

**Goal:** Hardcoded Dark-Mode-Farben aus 8 App-Templates + nerve.css entfernen und durch nerve.css-CSS-Tokens ersetzen; Nav-Bestätigungs-Modal (.n-modal-*) sauber im aktuellen Design neu bauen.

**Depends on:** Phase 08.19.5.2 (UI-Cleanup-Foundation), Phase 08.19.5 (PiP-State-Basis)
**Komplexität:** 🟡
**Cross-AI:** Pflicht — Gemini-Briefing explizit mit "prüfe auf hardcoded Farben + Inline-Styles + Design-Token-Konsistenz"
**CLAUDE.md:** Anti-Hardcoded-Farben-Sektion, Regel 7

**Plans:** 2 plans in 2 waves

Plans:
- [ ] 08.19.5.4-01-PLAN.md — Wave 1: Token-Migration 10 Templates (inkl. dashboard, logs_page) + .badge-gray nerve.css-Bereinigung + Pattern-Marker + landing.html nach templates/marketing/ verschieben
- [ ] 08.19.5.4-02-PLAN.md — Wave 2: .n-modal-CSS-Klassen in nerve.css + Modal-HTML in base.html + Click-Interceptor + _nerveNavConfirm() + ESC/Overlay-Dismiss in pip-launcher.js

---

### Phase 08.19.5.6: 4-Reiter-UI für Skript+Opener-Auswahl + Briefing-Skript-Merge (INSERTED — 2026-05-05) 🟡

**Goal:** Das Skript+Opener-Auswahl-Fenster im PiP-Launcher in 4 separate Reiter (Opener / Erlaubnisfrage / Skript / Pitch) aufteilen; Vorwissen-Picker + Du/Sie-Toggle als 5. Sub-Sektion immer verfügbar (nicht nur nach PreCall); PreCall-Briefing-Merge-Target von Opener auf Skript umstellen.

**Depends on:** Phase 08.19.5.4 (UI-Cleanup-Foundation), Phase 08.19 ✅ (ProfileOpener-Schema mit type-Spalte), Phase 08.19.2 ✅ (erlaubnis + pitch Multi-Entry)
**Komplexität:** 🟡
**Cross-AI:** Pflicht — Briefing: "prüfe auf Vollständigkeit aller 4 Reiter-Inhalte (kein vergessener Profile-Type), prüfe Briefing-Merge-Target-Switch im Backend, prüfe Konsistenz mit existing nerve.css-Tokens (Anti-Hardcoded-Farben), prüfe ob neue Reiter-UI mit existing consent-overlay-Pattern konsistent ist"
**CLAUDE.md:** Anti-Hardcoded-Farben-Sektion, Regel 7
**Andre-Decision (2026-05-05):** Vorgezogen aus Block O Teil 2 — UX-Stelle die André täglich nervt; Pflicht vor 08.20 (Pipeline-Re-Wire) damit 08.20-EWB-Prompt die 4 Profile-Type-Reiter korrekt berücksichtigen kann.

**Plans:** tbd

Plans:
- [ ] 08.19.5.6-01-PLAN.md — tbd

---

### Phase 08.19.5.6.1: 4-Reiter-UI Hotfixes + UX-Polish (INSERTED — 2026-05-06) 🟡

**Goal:** 3 Bugs + 2 UX-Verbesserungen aus Phase 08.19.5.6 UAT beheben: Teleprompter-Sequenz-Bug, unmögliches Abwählen einer Auswahl, leeres Text-Feld beim ersten Tab-Switch; Personalisierungs-Flow zurück zur 4-Reiter-Ansicht; Hilfe-Hinweise pro Reiter.

**Depends on:** Phase 08.19.5.6 ✅ (4-Reiter-UI live deployed)
**Komplexität:** 🟡
**Cross-AI:** Pflicht — Briefing: "prüfe ob Teleprompter-Block-Builder alle 4 Reiter-Auswahlen in korrekter Reihenfolge zusammenstellt + ob null-Selection-Pattern konsistent durch alle 4 state-Variablen geleitet wird + ob Personalisierungs-Flow-Refactoring (zurück zur 4-Reiter-Ansicht) mit existing State-Mgmt kompatibel ist"
**CLAUDE.md:** Anti-Hardcoded-Farben-Sektion, Regel 7
**Andre-Decision (2026-05-06):** UAT 08.19.5.6 zeigt 10/14 grün — Foundation solide. 3 Bugs + 2 UX-Verbesserungen als dedizierte Hotfix-Phase vor Weitermachen mit 08.20.

**Plans:** 2 plans

Plans:
- [x] 08.19.5.6.1-01-PLAN.md — Null-Default-Optionen (R-02) + Tab-Switch Preview-Trigger (R-03) + Hint-Box (R-05) ✅ 2026-05-06
- [ ] 08.19.5.6.1-02-PLAN.md — Teleprompter Block-Builder Sequenz (R-01) + Personalisierungs-Flow Return (R-04)

---

### Phase 08.19.5.6.2: Briefing-Buttons-Konsolidierung: 3-zu-1 (INSERTED — 2026-05-06) 🟡

**Goal:** Die 3-Button-Modus-Wahl nach PreCall-Briefing-Erstellung (Modus A/B/C) wird zu einem einzigen "Briefing übernehmen"-Button konsolidiert. EWB-Integration und PiP-Tab werden automatisches Default-Verhalten. Personalisierung bleibt als optionaler Step-5-Pfad erhalten.

**Depends on:** Phase 08.19.5.6.1 ✅ (Hotfixes live)
**Komplexität:** 🟡
**Cross-AI:** Pflicht — Briefing: "prüfe ob alle 3 Funktions-Pfade (EWB-Integration / PiP-Tab / Personalisierung-Trigger) sauber als Default-Verhalten beim Briefing-Erstellen ausgelöst werden + ob state.briefingModus-Konsumenten alle migriert sind oder als toter Code entfernt werden + ob Personalisierungs-Trigger weiterhin korrekt modus-abhängig (Cold-Call/Meeting) funktioniert"
**UI-SAFETY-GATE:** --skip-ui (Visual-Polish kommt in Block O Teil 2)
**Andre-Decision (2026-05-06):** UAT Round 3: 3 Buttons sind Anti-UX. Alle 3 Funktionen sollen immer aktiv sein. Step 4 → 1 Button. Personalisierung lebt in Step 5 (modus-abhängige ✨-Knöpfe pro Reiter).

**Plans:** 1 plan

Plans:
- [x] 08.19.5.6.2-01-PLAN.md — renderStep4() 3→1 Button + briefingModus entfernen + PiP-Gate + Tests bereinigen ✅ 2026-05-07

---

### Phase 08.19.5.6.3: PiP-Briefing-Tab Cheat-Sheet-Format (INSERTED — 2026-05-07) 🟢

**Goal:** PiP-Briefing-Tab zeigt strukturiertes Cheat-Sheet (Eckdaten + Empfehlungen + kollabierter Fließtext) statt reinem Fließtext — User kann im Live-Call wichtige Daten auf einen Blick erfassen.

**Depends on:** Phase 08.19.5.6.2 ✅ (Briefing-Buttons-Konsolidierung live)
**Komplexität:** 🟢
**UI-SAFETY-GATE:** --skip-ui (Visual-Polish kommt in Block O Teil 2)

**Plans:** 1 plan

Plans:
- [ ] 08.19.5.6.3-01-PLAN.md — nerve.css pip-cheat-* Klassen + pip-launcher.js Cheat-Sheet render + Toggle Event-Delegation

---

### Phase 08.20: Pipeline-Re-Wire — Voll-Profil-EWB + Lead-Context + branchenspezifische PreCall (INSERTED — 2026-04-29)

**Goal:** Den EWB-Live-Pfad von ~10 genutzten Profil-Feldern (50-60% tot nach 08.17-Audit) auf Voll-Profil-Integration hochrüsten. `build_profile_context()` erhält definierte Sektions-Reihenfolge (Branche → Zielkunde → Schmerzen → Einwände → Phasen → KI-Verhalten → Wisdom). PreCall-Pipeline (`recherche_firma` + `_generiere_briefing`) bekommt Profil als Steuerungs-Input für branchenspezifische Recherche-Strategie. PreCall-Briefing fließt wieder ins EWB-Prompt (war in 08.8 gelöscht). Manual-EWB-Button-Pfad erhält Profil-Kontext (kein hardcoded Coach-Prompt mehr). `_SYSTEM_PROMPT_QA` um `{profile_context}`-Placeholder erweitern (LB-3-Fix). Schema-Drift `opener`/`pitch` (top-level vs. `basis.*`) bereinigen. Sonnet-Switch via ENV für EWB-Streaming bei Voll-Profil-Kontexten als Pflicht (Voll-Profil + Haiku → grammatisch hölzern; Voll-Profil + Sonnet 4.5 → Quality + akzeptable Latenz mit Caching). Caching-Auswirkung verifizieren: Voll-Profil → Cache-Threshold immer überschritten → max. Cache-ROI. Org-Scoping-Verifikation: `build_profile_context()` nutzt SID-Lookup aus 08.19.4 korrekt (User in Org 2 sieht NICHT Profil 7 aus Admin-Org 1). Mini-Adds (alle Pflicht): (8) Vorwissen-Picker im Live-Workflow nach PreCall — Lead-spezifisch (3-stufig), fließt als Lead-Context in EWB-Prompt; (9) Du/Sie-Smart-Switch — Lead-spezifisch + Live-Detection im Transcript; (10) Live-EWB-Prompt-Preview-Panel — kollabierbares Panel pro Profil-Sektion; (12) `einwaende_detail` vs. `einwaende` Koexistenz konsolidieren — Migration auf einheitliches Format.
**Komplexität:** 🔴 (Multi-File-Refactoring auf 8+ Pipelines, EWB-Prompt-Struktur ändert, Caching-Strategie betroffen) — Cross-AI Pflicht. Pro-Modell explizit verifizieren vor Cross-AI-Run.
**Depends on:** Phase 08.19 ✅ (Schema), Phase 08.19.1 ✅ (Strict-Mode), Phase 08.19.4 ✅ (Multi-User-Session-Scoping als Foundation)
**Andre-Decision (2026-04-27):** EWB wird besser je mehr Daten ankommen — ALLES aus dem Profil in sinnvoller Reihenfolge ins EWB-Prompt, nicht selektiv.

**Plans:** 5 plans

Plans:
- [x] 08.20-01-PLAN.md — Foundation: _per_sid_briefing + branchen_data.py + Schema v3->v4 + einwaende consumer migration
- [x] 08.20-02-PLAN.md — build_profile_context() 9-Section Rewrite + BUG-A/BUG-B fixes
- [x] 08.20-03-PLAN.md — PreCall branchen-hint inject + _per_sid_briefing write + QA pipeline {profile_context}
- [x] 08.20-04-PLAN.md — Manual-EWB Voll-Profil + Sonnet defaults + Circuit-Breaker TTFT
- [ ] 08.20-05-PLAN.md — Lead-Context UI: Vorwissen-Picker + Du/Sie-Detection + EWB-Preview-Panel
---

### Phase 08.20.2: PreCall-Briefing-Trust + Web-Search-Integration (INSERTED — 2026-04-30)

**Goal:** precall_service.py wird von freiem Markdown-Briefing zu dreischichtigem, verifizierbarem Firmen-Recherche-Output umgebaut: Schicht 1 (strukturierte Pflichtfeld-Karte mit per-Feld Confidence + Source-URL), Schicht 2 (gehärteter Fließtext), Schicht 3 (Gesprächs-Empfehlungen als separater Call).
**Komplexität:** 🟡 mittel
**Depends on:** Phase 08.20 ✅

**Plans:** 4 plans in 3 waves

Plans:
- [x] 08.20.2-01-PLAN.md — precall_service.py rebuild: PRECALL_FIELDS_SYSTEM_PROMPT, _generiere_briefing() Schicht-1+2, _generiere_empfehlungen() Schicht-3, cache key extension
- [x] 08.20.2-02-PLAN.md — DB migration (precall_fields column) + route integration (api_precall_research + api_beenden)
- [x] 08.20.2-03-PLAN.md — UI 3-layer PreCall modal: confidence card CSS + renderStep4() 3-section rewrite
- [x] 08.20.2-04-PLAN.md — Tests: test_precall_schema.py with 7 mock-based Schicht-1 schema tests (all GREEN, commit 3840b0a)

---

### Phase 08.20.3: Briefing-Lebenszyklus + KI-Skript-Personalisierung (INSERTED — 2026-04-30)

**Goal:** Nach „Ergebnis übernehmen” entscheidet der User aktiv was mit dem PreCall-Briefing passiert — Modus A (nur EWB, default), Modus B (Briefing als ausklappbarer PiP-Reiter während Call), Modus C (KI personalisiert gewählten Opener/Skript mit Lead-Daten, speichert dauerhaft als neues ProfileOpener-Item).
**Komplexität:** 🔴 komplex
**Depends on:** Phase 08.20.2 ✅
**Status:** ⚠️ feature_incomplete — Modus A + Modus B shipped ✅. Modus C (KI-Skript-Personalisierung) nach Block O vorgezogen → Phase 08.20.4. (Andre-Decision 2026-05-01)

**Plans:** 4 plans

Plans:
- [x] 08.20.3-03-PLAN.md — DB-Foundation (parent_id + is_personalized Migration, PERSONALIZED_SCRIPTS_CAP, Test-Scaffold) ✅ 2026-05-01 (0d6df97, 4bb7714, 15bae1f)
- [x] 08.20.3-04-PLAN.md — PiP-Briefing-Tab Modus B + window.mdToHtml + renderStep() Pre-Check ✅ 2026-05-01 (967b607, 9618caf)
- [x] 08.20.3-01-PLAN.md — Step-4-Footer 3-Button Modus-Selector + renderStep4b/4c + Step-5 zweiter Button + optgroup-Dropdown ✅ 2026-05-01 (f58d9ea, d7d6b20, 4466448)
- [~] 08.20.3-02-PLAN.md — KI-Backend: generate_personalized_skript() + /api/precall/personalize + /save Route → DEFERRED zu Phase 08.20.4 (nach Block O)

---

### Phase 08.20.4: KI-Skript-Personalisierung Modus C — Vollständig (INSERTED — 2026-05-01)

**Goal:** Modus C End-to-End vollständig ausliefern — nach Block O. KI-Personalisierung des gewählten Openers mit Lead-Daten aus PreCall-Briefing, Vorher/Nachher-Vergleich, dauerhafter Speicherung in ProfileOpener (is_personalized=True) und Call-Start mit personalisiertem Opener als aktiver Text.
**Komplexität:** 🟡 mittel
**Depends on:** Phase 08.20.3 ✅, Block O ✅

**Plans:** tbd

---

### Phase 06.1: PiP UAT-Fixes — Bugs, Farben, Proportionen, Mic-Indikator, Slider (INSERTED)

**Goal:** UAT-Fix-Cycle nach Phase 06: behebt 3 funktionale Bugs (EWB-Labels, Scrollbar, Opener-Relocation), invertiert das Farbschema (heller Body, dunkler Header), rotiert das Split-Layout (Teleprompter 60% oben, EWB 10% mittig, KI 30% unten), vergrößert PiP-Default auf 480×760, fügt 4-Balken Audio-Level-Mic-Indikator mit Click-to-Mute hinzu und redesignt den Transparenz-Slider iOS-style (140px, filled portion).
**Requirements**: PIP-01, PIP-03, PIP-04, PIP-05
**Depends on:** Phase 6
**Plans:** 4/4 plans complete

Plans:
- [x] 06.1-01-PLAN.md — Bug-Fixes (D-01 EWB-Labels, D-02 Scrollbar, D-03 Opener→Teleprompter-Block-0)
- [x] 06.1-02-PLAN.md — Layout-Rotation + helles Farbschema (D-04 bis D-12: 480×760, light body, teleprompter top 60%, EWB horizontal pills, slot colors inverted)
- [x] 06.1-03-PLAN.md — Mic-Indikator (D-13 bis D-16: 4 audio-level bars, WebAudio AnalyserNode, green/grey states, click-to-mute via track.enabled)
- [x] 06.1-04-PLAN.md — Slider-Redesign (D-17 bis D-19: 140px iOS-style mit teal filled portion, touch hit-area, localStorage-clamp)

### Phase 06.2: Auto-Einwand-Erkennung Latenz-Architektur (INSERTED — BUG-10 Teil 2)

**Goal:** Gefühlte Latenz bei Auto-Einwand-Erkennung von 2-2.5s auf <1s reduzieren. Lokaler Keyword-Klassifikator auf Deepgram-Interim-Transcripts rendert Slot 0 mit Profil-Antwort in <300ms (keine API-Latenz). Parallel startet Haiku-Variante für Slot 1 mit erstem Token in <1s. USP "KI erkennt Einwand automatisch" wird im Cold-Call benutzbar.
**Requirements:** BUG-10-LAT
**Depends on:** Phase 06, Phase 06.1
**Plans:** 4/4 plans executed — COMPLETE

Plans:
- [x] 06.2-01-PLAN.md — Keyword-Matcher-Modul (DE-tolerant Regex + Profil-Mapping + Dedup-State)
- [x] 06.2-02-PLAN.md — Backend-Pipeline (Deepgram-Interim-Hook + Match + Socket-Emit + parallel Auto-Variante spawn + UtteranceEnd-Reset + Mute-Guard)
- [x] 06.2-03-PLAN.md — Frontend-Handler (keyword_einwand_match Instant-Render + pip_token_done-Respekt + mute_mic-Emit + Timing-Logs)
- [x] 06.2-04-PLAN.md — Shared busy_until-Lock (Keyword + analyse_loop teilen Guard → kein Doppel-Spawn, Button-Pfad unabhängig)

### Phase 06.3: analyse_loop entkoppeln von Live-Slots (INSERTED)

**Goal:** Den 529 overloaded_error beim EWB-Vorlesen strukturell unterbinden. Keyword-Matcher (Phase 06.2) wird alleiniger Primary fuer Live-EWB-Slots. analyse_loop behaelt Intelligence-Funktionen (FT-Events, Kaufbereitschaft, Phase-Classifier, Coaching-Hints), verliert aber jeden UI-Render-Pfad in Slot 0 und Slot 1. Akzeptanz: 0 Anthropic-529-Fehler bei 3x EWB-Vorlesen, kein trigger=analyse_loop in PiP-AutoVar Logs.
**Requirements:** BUG-09-529
**Depends on:** Phase 06.2
**Plans:** 1/1 plans complete

Plans:
- [x] 06.3-01-PLAN.md — analyse_loop Slot-0/Slot-1 Entkopplung + ANALYSE_INTERVALL auf 4s

### Phase 06.4: Headset-Pflicht-Modal Cold Call DSGVO-Hardening (INSERTED)

**Goal:** Einmal-pro-Session-Modal beim ersten Cold-Call-Start: User bestätigt Headset-Nutzung und Einzel-Stimm-Verarbeitung. Ohne Bestätigung startet kein Call. sessionStorage-Flag (verfällt bei Tab-Close). Meeting-Modus unberührt. DSGVO-Compliance (§ 201 StGB Stimmverarbeitungsgrenze).
**Requirements:** POLISH-16
**Depends on:** Phase 06.3
**Launch-relevant:** true
**Plans:** 1/1 plans complete

Plans:
- [x] 06.4-01-PLAN.md — Headset-Modal HTML/CSS + Call-Gate-Logik + Logout-Cleanup

### Phase 06.5: Meeting-Modus Flow-Umbau — Consent als Modal beim Call-Start (INSERTED)

**Goal:** Meeting-Modus bekommt denselben Launcher-Flow wie Cold Call (Profil -> PreCall -> Skript/Opener). Inline-Consent-Screen wird entfernt. Consent erscheint stattdessen als Modal (analog Headset-Modal aus Phase 06.4) beim Klick auf "Call starten". "Stattgegeben" startet Meeting-Call (ohne Headset-Check, da Consent beide Stimmen rechtlich abdeckt). "Abgelehnt" schaltet auf Cold-Call-Modus mit regulaerem Headset-Gate. "Abbrechen" laesst User auf Step 5. Consent-Text aus state.profileDaten.consent_text ueberschreibbar mit [Name]-Platzhalter aus precallFormData.person. state.consentDone einmal pro Session. Alter PiP-Consent-Screen komplett ausgebaut.
**Requirements:** POLISH-16
**Depends on:** Phase 06.4
**Launch-relevant:** true
**Plans:** 1/1 plans complete

Plans:
- [x] 06.5-01-PLAN.md — Meeting-Card direct-flow + Consent-Modal (HTML/CSS/JS) + startCall consent-gate + alten pip-section-consent komplett ausbauen

### Phase 7: MAIN DESIGN — App-weite Design-Konsolidierung

**Goal:** App-weite Design-Konsolidierung auf MAIN DESIGN: weisse Kacheln, schwarze Schrift, teal Akzent (#00D4AA), kein Gelb/Gold, Header-Schwarz nur im PiP, 1.5px Borders via `var(--n-border)` in nerve.css. Bulk-Migration Gelb/Gold -> Grau/Teal ueber 50+ Touchpoints. `data-theme` Dead-Code entfernt (kein Theme-Switch mehr). PiP auf light-Modus umgestellt. `.n-btn-accent` entfernt (teal als Primary). nerve.css Farb-Tokens (`--n-border`, `--n-accent`, ...) als Single Source of Truth. Umlaut-Regel kodifiziert: User-Text mit echten Umlauten, Code-Identifier ASCII (siehe CLAUDE.md) — /logs-Regression deswegen eingefangen.
**Requirements:** POLISH (Main Design Konsolidierung)
**Depends on:** Phase 06.5
**Launch-relevant:** true
**Plans:** N/A (retro-documented — direkt ohne GSD-Phase umgesetzt)
**Completed:** 2009-04-18 (UAT green, 6 Commits, Daily Note 2009-04-18.md)

Plans:
- [x] (retro) Bulk-sed Gelb/Gold -> Grau/Teal ueber 50+ Touchpoints
- [x] (retro) data-theme Dead-Code entfernt
- [x] (retro) PiP light-Modus, Header-Schwarz nur im PiP
- [x] (retro) .n-btn-accent entfernt, teal als Primary konsolidiert
- [x] (retro) Umlaut-Regression-Fix + CLAUDE.md-Regel
- [x] (retro) nerve.css Farb-Tokens als Single Source of Truth

### Phase 07.1: POLISH-24 — Session-Detail-Redesign /session/<id> (INSERTED)

**Goal:** Details-Seite `/session/<id>` komplett auf MAIN DESIGN umbauen (weisse Kacheln, 1.5px Borders, teal Akzent, keine Inline-Styles, `.n-session-detail-*` Klassenfamilie in nerve.css). 8 Sektionen von oben nach unten: (1) Header mit Session-ID/Modus-Badge/Datum/Dauer/Result, (2) Score-Hero mit Breakdown (kb_end 40% / behandelt-Rate 30% / redeScore 20% / skript 10%) + Trend vs Schnitt letzte 5, (3) Kaufbereitschafts-Verlauf als Chart.js-Chart mit X/Y-Achsen, (4) Einwand-Timeline chronologisch mit gewaehlter Option + erfolgreich-Badge, (5) Phasen-Visualisierung als horizontaler Strip ueber Call-Dauer, (6) Skript-Abdeckung Progress-Bar mit Block-Breakdown, (7) Painpoints-Liste (wenn vorhanden), (8) PreCall-Briefing collapsible (wenn vorhanden). Inkl. DB-Migration: Spalte `kb_verlauf TEXT` in `conversation_logs`, `/api/beenden` persistiert kb_verlauf als JSON. NICHT drin: Transkript (Phase 4.19), Lernkarten, Audio. Empty-States bei sparse Sessions. CSS_VERSION bumpen. Mobile-responsive. Zurueck-Navigation zu `/logs`.
**Requirements:** POLISH-24
**Depends on:** Phase 7
**Launch-relevant:** true
**Plans:** 3 plans

Plans:
- [x] 07.1-01-backend-db-helper-PLAN.md — Wave 1: kb_verlauf Migration + ORM Column + /api/beenden Persistenz + _derive_practice_recommendations Helper + session_detail Route-Erweiterung
- [x] 07.1-02-frontend-template-css-PLAN.md — Wave 2: session_detail.html Komplett-Rewrite (11 Sektionen, typ-diskriminierend, Chart.js) + nerve.css .n-session-detail-* Klassenfamilie (21+ Klassen)
- [x] 07.1-03-polish-deploy-PLAN.md — Wave 3: CSS_VERSION bump + deploy.sh + Browser-Smoke-Tests fuer alle 3 Session-Typen + Cross-Context-Badge-Verifikation (UAT-R5 approved 2009-04-20, 22+ commits, POLISH-34 deferred zu 07.2)

### Phase 07.2: Scoring-Konsolidierung (INSERTED)

**Goal:** Aus zwei parallelen Scoring-UIs (Training-Post-Call-Overlay + Session-Detail-Seite) wird EINE Auswertungs-Seite. User landet IMMER auf `/session/<id>` nach Call-Ende, egal ob Training/Cold Call/Meeting. Selbe 11 Sektionen aus Phase 07.1 PLUS drei neue Sektionen unten: (12) Wendepunkt-Analyse mit max 3-5 Karten (Du hast gesagt / Problem / Besser waere), (13) 6 Einzel-Scores mit Progress-Bars (Gespraechseroeffnung, Bedarfsanalyse, Einwandbehandlung, Gespraechsfuehrung, Abschluss, Beziehungsaufbau), (14) Verbesserungspotenzial-Liste mit 3-5 Bullet-Points. Header-Unterschied: Live=Cold-Call/Meeting-Badge, Training=Persoenlichkeitstyp+Schwierigkeit+Kunden-Name+Alter als Badge-Gruppe (loest POLISH-32 mit). Training-Post-Call-Overlay entfernt, direkter Redirect auf /session/<id>, "Nochmal trainieren"-Button wandert in Action-Button oben rechts. Live-Session: Sektionen mit Empty-State + Phase-4.19-Hinweis wo Daten fehlen (Wendepunkte brauchen Transkript-Persistierung). Training-Session: alle Sektionen aktiv, Daten aus ConversationLog (Wiederverwendung der Felder die heute im Overlay gerendert werden).
**Requirements:** POLISH-32 (implicit), plus neue Anforderung Scoring-Konsolidierung
**Depends on:** Phase 07.1
**Launch-relevant:** true
**Plans:** 4/4 plans complete

---

## ⚠️ Auto-Scroll-Komplex KOMPLETT ZURÜCKGENOMMEN (2026-05-10)

**Was wurde versucht (5.-10. Mai 2026):**
- Phase 08.19.5.6.4 — PiP Teleprompter Auto-Scroll + KI-Position-Erkennung
- Phase 08.19.5.6.4.1 — TeleprompterRegistry + lokales Token-Match
- Phase 08.19.5.6.4.2 — Deepgram-Latenz-Optimierung (interim_results, endpointing 300, CSS-Pulse)
- Phase 08.19.5.6.4.3 — Predictive-Cursor-Jump bei Block-Ende (Coverage-Tracking)
- Phase 08.19.5.6.4.4 — Visuelle Voranzeige (CSS .tp-block-next-up)

**Aufwand:** 5 Phasen, ~78 Commits, mehrere Cross-AI-Reviews mit Gemini, mehrere Bug-Cycles, eine Code-Review pro Phase, knapp 5 Tage Solo-Founder-Zeit.

**Ergebnis aus User-Sicht:** Funktioniert nicht zuverlässig. Andre-UAT mehrfach: Cursor reagiert nicht klar genug auf Block-Wechsel, springt nicht vor Block-Ende, Predictive triggert nicht zuverlässig wegen Deepgram-Aussprache-Drift + Token-Match-Fragilität.

**Wurzel der Fehlentscheidung:** Token-Match-Algorithmus war das falsche Werkzeug für vorausschauende Cursor-Steuerung. Reactive-Auto-Scroll mit Deepgram-Latenz (1-3s Final-Transcript) war im echten Live-Call nicht user-tauglich. Plus: Frust-Schleife durch wiederholte UAT-Iterationen ohne sauber zu reframen (Drei-Versuche-Stop-Regel aus CLAUDE.md Punkt 16 wiederholt verletzt).

**Aktion 2026-05-10:**
- Hard-Reset auf Pre-Phase-Stand (Commit 1c3bccd vom 7.5.2026)
- qa-pipeline-Markdown-Sanitizer-Fix (86671ae vom 8.5.) als einziger Code-Fix erhalten
- Alle 5 Phase-Verzeichnisse (.planning/phases/08.19.5.6.4*) entfernt
- Teleprompter ist wieder dumm-statisch wie vor 5.5.2026 — User scrollt manuell mit Mausrad

**Nächster Anlauf — wenn überhaupt:**
Komplett andere Architektur erforderlich (Embedding-basierter Vergleich statt Token-Match). Frühestens Phase 08.21 (Sales-Wisdom-Layer) mit anderer LLM-Pipeline. Eventuell auch nie — manuelles Scrollen durch User ist akzeptable Default-UX, Auto-Scroll war Premium-Feature-Ambition die mit aktueller Tech nicht haltbar ist.

**Lessons-Learned für CLAUDE.md (separat zu dokumentieren):**
- Drei-Versuche-Stop-Regel (Punkt 16) muss ernster genommen werden — wir hatten >8 Iterationen heute (10.5.) bevor Stop kam
- Token-Match ist false-friend für UX-kritische Algorithmen mit realer Sprache (Deepgram-Drift, Improvisation, Tokenization-Verluste)
- Bei Algorithmen-Bugs früher die Architektur-Frage stellen statt am gleichen Werkzeug rumzudoktern (Punkt 11 Fix-vs-Rebuild)

---

### Phase 08.23.2.A: Postgres-Migration + Schema-Umbenennung (INSERTED — 2026-05-11) 🔴

**Goal:** SQLite → Postgres Engine-Wechsel (32 Tabellen 1:1) + 2 Rebuilds (calls/call_events ersetzen ft_call_sessions/ft_assistant_events) + Code-Refactor (alle FtCallSession/FtAssistantEvent-Referenzen entfernen) + Alembic-Baseline + Migrations-/Validierungs-Skripte + Cutover-Vorbereitung + Backup-Cronjob.

**Depends on:** Phase 08.19.5 ✅
**Komplexität:** 🔴 — Schema-Migration, Postgres-Cutover, DB-Rebuild
**Plans:** 9 plans (3 completed)

Plans:
- [x] 08.23.2.A-01-PLAN.md — Call + CallEvent SQLAlchemy-Modelle in models.py + FtCallSession/FtAssistantEvent löschen ✅ 2026-05-12
- [x] 08.23.2.A-02-PLAN.md — Alembic tooling init (alembic.ini + env.py + requirements.txt) ✅ 2026-05-12
- [x] 08.23.2.A-03-PLAN.md — FT dead-code prune: deepgram_service.py + claude_service.py + export_ft_jsonl.py ✅ 2026-05-12
- [x] 08.23.2.A-04-PLAN.md — app_routes.py FtCallSession block + test file cleanup (D-08/D-10/D-11) ✅ 2026-05-12
- [x] 08.23.2.A-05-PLAN.md — migrate_to_postgres.py + validate_postgres_migration.py (33 Tabellen, FK-Order, DRY_RUN) ✅ 2026-05-12
- [x] 08.23.2.A-06-PLAN.md — Alembic Baseline-Migration 0001 (35 Tabellen, CHECK-Constraints, GIN-Index) ✅ 2026-05-12
- [x] 08.23.2.A-07-PLAN.md — Postgres 16 Server-Setup Runbook + Hetzner-Setup durch Andre ausgefuehrt ✅ 2026-05-12
- [x] 08.23.2.A-08-PLAN.md — backup_postgres.sh + systemd docs + deploy.sh pytest + /api/health backup_status + dashboard warning strip ✅ 2026-05-12
- [ ] 08.23.2.A-09-PLAN.md — Cutover-Sonntag + Smoke-Test + Dashboard-Backup-Warnung

### Phase 08.23.2.B: Anonymisierungs-Strecke vor Mitschrift-Schreibungen (INSERTED — 2026-05-12) 🔴

**Goal:** Drei-stufige Anonymisierungs-Strecke (Regex-Vorfilter + spaCy NER + Art-9-Filter) als eigenständiges Modul `services/anonymization.py` bauen und vor allen DB-Schreibungen von Mitschrift-Daten in existierenden Tabellen verdrahten. Sicherheits-Test (50 Snippets, <5% Re-Identifikation) + Performance-Test (<200ms/Snippet) als Acceptance-Gate.

**Depends on:** Phase 08.23.2.A
**Komplexität:** 🔴 — DSGVO-kritische Foundation-Phase. Cross-AI mit Gemini Pflicht.
**Plans:** 10 plans

Plans:
- [x] 08.23.2.B-01-PLAN.md -- services/art9_keywords.py + services/anonymization.py (AnrufAnonymisierer + Fallback-Architektur)
- [x] 08.23.2.B-02-PLAN.md -- requirements.txt + deploy.sh Dependencies (spacy + phonenumbers + Modell-Download)
- [x] 08.23.2.B-03-PLAN.md -- Alembic-Migration quality_tier + DELETE-Skript historische Daten (D-07)
- [x] 08.23.2.B-04-PLAN.md -- live_session.py Cache-Lifecycle-Verdrahtung (init_anonymisierer + get_anonymisierer)
- [x] 08.23.2.B-05-PLAN.md -- deepgram_service.py INPUT-PFAD (Z.78 conversation_log) + OUTPUT-PFAD (Z.568 EWB)
- [x] 08.23.2.B-06-PLAN.md -- claude_service.py OUTPUT-PFAD (Z.892 gegenargument_log + Z.1432 painpoints)
- [x] 08.23.2.B-07-PLAN.md -- app_routes.py /api/session-rating Kommentar + /api/health pipeline_status
- [x] 08.23.2.B-08-PLAN.md -- Unit-Tests anonymization.py + art9_keywords.py (Req-1 bis Req-6) ✅ 2026-05-13
- [x] 08.23.2.B-09-PLAN.md -- Integration-Tests Verdrahtungs-Punkte + Fallback A/B/C (Req-7 bis Req-9) ✅ 2026-05-13
- [x] 08.23.2.B-10-PLAN.md -- Security-Test (50 Snippets, Re-ID <5%) + Performance-Test (<200ms P95) ✅ 2026-05-13

### Phase 08.23.2.C: Phasen-Klassifikator-Anpassung + Gatekeeper-Erkennung (INSERTED — 2026-05-14) 🔴

**Goal:** Modus-blinder Phasen-Klassifikator auf drei separate Listen umbauen (Cold-Call 6, Meeting 6, Gatekeeper 4) + Drei-Kategorien-Klassifikator (target/gatekeeper/unknown) via NER-Namens-Match gegen Briefing-CEO/GF + GLiNER-Integration + manueller Strg+G/Strg+E Toggle + Hysterese-Logik + Trigger-Phrasen + UWG §7 Hard-Block + Mr.-Miyagi-Buttons + phrases.mode-Migration.

**Depends on:** Phase 08.23.2.B ✅
**Komplexität:** 🔴 — Cross-AI mit Gemini Pflicht.
**Plans:** 9 plans

Plans:
- [ ] 08.23.2.C-01-PLAN.md -- GLiNER-Dependency + Korpus-Gate + Phrase-Entwurf-Seed (Andre-Gate)
- [ ] 08.23.2.C-02-PLAN.md -- Alembic 0003 phrases.mode + Schema-Sync (Req-10)
- [x] 08.23.2.C-03-PLAN.md -- config/phase_transitions.py + Kalibrierungs-Skript + Foundation-Code-Register (Req-3, Req-11)
- [x] 08.23.2.C-04-PLAN.md -- GLiNER in services/anonymization.py Union-Voting + extract_entities() Export (Req-1)
- [x] 08.23.2.C-05-PLAN.md -- claude_service modus-spezifische Phasen + ki_logik TRIGGER_PHRASES (Req-2, Req-7) ✅ 2026-05-15
- [x] 08.23.2.C-06-PLAN.md -- services/gatekeeper.py + live_session + Call-Lifecycle + phase_change/UWG Wiring (Req-3,4,5,7,8,11) ✅ 2026-05-15
- [x] 08.23.2.C-06b-PLAN.md -- Migration 0003 Gatekeeper Seed-Insert (10 Phrasen, 4 Buttons, Req-9) ✅ 2026-05-15
- [x] 08.23.2.C-07-PLAN.md -- PiP Ctrl+G/E Toggle + Gatekeeper-Buttons + UWG-Banner (Req-6, Req-8, Req-9) ✅ 2026-05-15 [Live-Test deferred → Production]
- [ ] 08.23.2.C-08-PLAN.md -- Tests: Hysterese, Phase-Classifier (F1>=0.75), Gatekeeper (acc>=0.80), Re-ID<5%, Session-State (Req-2,3,4,5,7,8,11,12,13,14)

### Phase 08.23.2.C.1: Staging-Server aufsetzen + Deploy-Workflow Staging→Production ✅ 2026-05-20

**Goal:** Zweiter Hetzner-Server `staging.getnerve.app` als 1:1-Spiegel von Production. Deploy-Workflow: Code → push → Auto-Deploy auf Staging → Browser-Tests dort → manuelle Freigabe → Push auf Production. Damit fängt jede künftige Phase Bugs auf Staging statt auf Production. Anti-Drift-Erkenntnis Andre 2026-05-19: lokales Windows-SQLite-Setup wird strukturell NIE 1:1-Production-Linux-Postgres-Spiegel sein — Staging ist die strukturelle Lösung, nicht Lokal-Fix. Lokal bleibt "good enough" zum Code-Schreiben.

**Andre-Quote (Pflicht-Lesen für Spec-Author):** "vllt macht es mehr sinn einen testserver jetzt schon aufzusetzen mit den aktuellen live daten. dann werkeln wir immer auf dem testserver und schubsen es dann rüber auf den live server. meist treten ja eh nochmal bugs auf wenn wir von local auf live pushen und weil aus einem mir nicht erkennbaren grund die versionen komplett anders sind oder anders handeln"

**Datenstrategie (Andre-Decision 2026-05-19): Option A — 1:1-Kopie der Production-Postgres-DB auf Staging.** Pre-Launch: DSGVO-konform weil Daten generisch (Andre-Test-Daten + post-Phase-B-anonymisierte Anrufe) + beide Server EU-Frankfurt. **Pflicht-Trigger:** sobald erster externer Early-Access-User registriert → Refresh-Logik muss DSGVO-konform werden (siehe `Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.md` Sektion 8).

**Pflicht-Inputs für Spec-Phase (LESEN BEVOR INTERVIEW STARTET):**
- `Nerve-Vault/01 Roadmap.md` Eintrag 08.23.2.C.1 (vollständige 11-Tasks-Liste + Akzeptanz-Kriterium + Symptome-Mapping welche durch Staging entblockt werden)
- `Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.md` Sektion 8 (Staging-Datenstrategie + Pflicht-Trigger)
- `Nerve-Vault/05 Log.md` Eintrag 2026-05-19 (Drift-Historie + Andre's Anti-Abrieb-Argumentation)

**Kern-Tasks (Detail in Spec-Phase ausarbeiten):**
1. Hetzner CX22 zweiter Server provisionieren (Frankfurt, Ubuntu 24.04, ~5€/Monat)
2. DNS-Eintrag `staging.getnerve.app` + SSL via Let's Encrypt
3. Postgres 16.13 installieren (gleiche Version wie Production), nerve + nerve_test DBs anlegen
4. nginx + systemd nerve.service deployen analog zu Production
5. deploy.sh erweitern: TARGET-Parameter (production vs staging), Default = staging
6. pg_dump-Refresh-Skript scripts/refresh_staging_from_production.sh (manueller Trigger + ggf. nightly Cron)
7. Sandbox-API-Keys für Staging (separate Anthropic, Deepgram, Stripe-Test-Mode)
8. Browser-Test-Workflow dokumentiert (nach jedem Staging-Deploy: Test-Checkliste)
9. Pre-Deploy-Gate vor Production (blockiert wenn Staging rot oder veraltet)
10. DSGVO-Pflicht-Eintrag verlinken (existiert bereits in Vault Sektion 8)
11. Mini-Teil: Lokales Setup minimum (Auto-Alembic für SQLite + DB-File-Drift-Schutz, max 1 Tag) — NUR damit Andre lokal Code schreiben kann, keine vollständige Lokal-Fix

**Akzeptanz-Kriterium:**
1. staging.getnerve.app erreichbar mit gültigem SSL
2. deploy.sh staging deployt in <5 Min
3. refresh_staging_from_production.sh synchronisiert DB in <10 Min
4. Deferred Live-PiP-Test aus Phase 08.23.2.C Plan 07 Task 4 läuft auf Staging durch (Ctrl+G/Ctrl+E/UWG-Banner)
5. deploy.sh production blockt automatisch wenn Staging rot
6. DSGVO-Trigger-Eintrag in Vault verlinkt
7. Lokales Setup minimum: python app.py startet, Alembic-Auto-Hook funktioniert, CSRF-Workaround bleibt

**Depends on:** Phase 08.23.2.C (Code committed) — Live-PiP-Test wird auf Staging nachgeholt
**Komplexität:** 🔴 — Server-Provisionierung + DSGVO-Datenstrategie + Deploy-Workflow-Änderung = drei unabhängige Hochrisiko-Achsen. Cross-AI Pflicht mit Gemini.
**Blocker für:** Phase 08.23.2.D + Phase 08.23.2.C Production-Deploy
**Plans:** 5 Plaene abgeschlossen. Req-9 (PiP-Live-Test) deferred → Phase 08.23.2.C.R (Gatekeeper-Rebuild). Staging-Infrastruktur 100% funktional.

Plans:
- [x] 08.23.2.C.1-01-PLAN.md -- Staging-Artefakte (setup_staging.sh, nginx-configs, systemd, RUNBOOK) ✅ 2026-05-20
- [x] 08.23.2.C.1-02-PLAN.md -- deploy.sh Refactor + Production-Gate + /api/health + .env.staging.example ✅ 2026-05-20
- [x] 08.23.2.C.1-03-PLAN.md -- DB-Sync-Skripte (refresh_staging + reset_sequences, REVIEW-HIGH-3 Fix) ✅ 2026-05-20
- [x] 08.23.2.C.1-04-PLAN.md -- alembic/env.py render_as_batch + app.py Alembic Python-API-Hook ✅ 2026-05-20
- [x] 08.23.2.C.1-05-PLAN.md -- DSGVO §8.3 + CSRF-Check ✅ | PiP-Test DEFERRED → 08.23.2.C.R ✅ 2026-05-20

### Phase 08.23.2.C.R: Gatekeeper-Modul-Rebuild (INSERTED — 2026-05-21) 🔴

**Goal:** Phase 08.23.2.C komplett umbauen weil Live-Test auf Staging am 2026-05-20 vier kritische Findings aufgedeckt hat (1 KRITISCH Architektur-Spec-Fehler + 3 HIGH). CLAUDE.md Punkt 11 (Fix-vs-Rebuild) Trigger erfüllt. Phase 08.23.2.C ist Code-committed aber Production-Deploy ist eingefroren bis C.R durch ist.

**Andre-Live-Test-Befunde 2026-05-20 (Pflicht-Lesen für Spec-/Plan-Author, siehe `Nerve-Vault/05 Log.md` Eintrag 19+20.05.):**

1. **KRITISCH — Architektur-Spec-Fehler:** Auto-Erkennung Gatekeeper im Single-Speaker-Cold-Call ist konzeptuell unmöglich. NERVE hört im Cold-Call NUR Berater-Stimme (DSGVO-Konstrukt aus `Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.md`). Klassifikator kann den Sekretär nie direkt hören → 12 Sekretär-Trigger-Phrasen aus Phase-C-Recherche-Block-B.6 greifen nie. Drei Cross-AI-Pässe + Code-Review haben die DSGVO-Single-Speaker-Konflikt übersehen (Phase-08.18-Wiederholungs-Pattern: Theorie-Spec gegen Realität nie validiert).
2. **HIGH — UX-Drift:** Tastaturkürzel Strg+G/E unzugänglich (Berater-Hände am Telefon, plus Strg+G ist Browser-Standard).
3. **HIGH — CLAUDE.md HART-Regel-Verletzung #4:** "Vorzimmer"-Indikator nutzt hardcoded gelbe Farbe statt CSS-Token aus `static/nerve.css`.
4. **HIGH — Inhalts-Drift:** 10 Gatekeeper-Phrasen aus Migration 0003 nie gegen Real-Sekretär-Interaktion validiert ("Bettel-Ton, Pseudo-Therapie").

**Spec-Phase abgeschlossen 2026-05-21 (Commit 6346391, Ambiguity 0.13 bei Gate ≤0.20). 9 Requirements gelockt:**

1. Auto-Erkennung löschen — `classify_contact()`, `apply_hysteresis()`, `detect_trigger_phrases()` aus `deepgram_service.py` + `services/gatekeeper.py` raus
2. UWG vollständig raus — `detect_uwg_hard_block()`, Banner, DOM, CSS, Handler komplett gelöscht. UWG-§7-Erfassung wandert in Block J Outcome-Tracking als Manuell-Status (siehe `Nerve-Vault/01 Roadmap.md` Block J)
3. Strg+G/E löschen — kein Tastatur-Kürzel mehr
4. Toggle-Button neben pip-mode-indicator — klickbar via existierendem Socket-Handler `manual_mode_toggle`
5. Default = Sekretär-Modus beim PiP-Öffnen — `init_session_state()` + `base.html`
6. call_events bei Mode-Switch — `event_type='mode_switch'`, payload mit 4 Feldern (old_mode/new_mode/timestamp/sid). KEIN visueller Trennstrich im Live-PiP
7. CSS-Token `--pip-gatekeeper-bg` + `--pip-gatekeeper-text` — `--pipeline-warning-bg` war semantisch falsch
8. pip-launcher.js Hex-Sweep — Z.1226 + Z.2582 + Z.1710 + Brand-Teal-Vorkommen migriert. SVG-inline-Strokes bleiben (CSS-Cascade greift nicht)
9. Terminologie "Sekretär/Entscheider" — sichtbare UI-Texte komplett umstellen. `gatekeeper` bleibt nur als Code-Variable

**Out of scope (explizit locked):**
- Phrasen-Inhalt (→ Phase 08.23.2.C.R.2 = eigene Mini-Phase, Praxis-Recherche durch Claudian + Andre-Filter)
- cold_call-phrases Re-Seed (→ Phase 08.23.2.C.R.1 = eigene Mini-Phase)
- SVG-inline-Farben
- Production-Deploy (eingefroren bis C.R komplett durch + Staging-Live-PiP-Test grün)

**Done-Kriterium (3-Schichten-Verteidigung — Andre-Decision 2026-05-21 nach Live-Test-Bug-Lerneffekt):**
1. Pytest auf `init_session_state()` — State-Init = `contact_category='gatekeeper'` UND `current_mode='gatekeeper'`
2. Pytest auf `nlp_ewb_payload()` — Default-State liefert 4 Gatekeeper-Buttons, nicht Standard-EWB
3. Manueller Browser-Test auf Staging mit Screenshot-Beleg im SUMMARY — PiP öffnen ohne Toggle → Indikator "Sekretär" + 4 Gatekeeper-Buttons sichtbar. Test-Schritte in HUMAN-UAT.md verankern.

Begründung: 20.05.-Live-Test-Bug hätte reinen Pytest bestanden (Daten korrekt, UI kaputt). Drei Schichten weil Datenpfad ≠ Render-Pfad ≠ User-Sicht.

**Anti-Pattern verankert:** vor jeder UI-Phase Pflicht-Live-Test auf Staging bevor Code-Review-Approval. Theoretisches Review reicht nicht.

**Depends on:** Phase 08.23.2.C (Code committed), Phase 08.23.2.C.1 (Staging-Workflow)
**Komplexität:** 🔴 — DSGVO-relevante Architektur-Korrektur + UI-Rebuild + Cross-AI Pflicht mit Real-Test-Material aus Phase-C-Live-Test
**Blocker für:** Phase 08.23.2.D + Production-Deploy von Phase 08.23.2.C
**Spec-Commit:** 6346391
**Plans:** 8 Pläne in 6 Waves

Plans:
- [x] 08.23.2.C.R-01-PLAN.md -- Alembic Migration 0004 (batch_alter_table) + Test-Scaffolds ✅ 2026-05-22
- [x] 08.23.2.C.R-02-PLAN.md -- gatekeeper.py Prune + deepgram_service.py UWG/Auto-Erkennung löschen ✅ 2026-05-22
- [x] 08.23.2.C.R-03-PLAN.md -- claude_service.py Auto-Erkennung löschen + live_session.py gatekeeper-Default ✅ 2026-05-22
- [x] 08.23.2.C.R-04-PLAN.md -- mode_switch-INSERT + mode_initial-INSERT ✅ 2026-05-22
- [x] 08.23.2.C.R-05-PLAN.md -- nerve.css Tokens + base.html span→button ✅ 2026-05-22
- [x] 08.23.2.C.R-06-PLAN.md -- pip-launcher.js UWG/Ctrl+G/Hex-Sweep/aria-label/Klick-Handler ✅ 2026-05-22
- [x] 08.23.2.C.R-07-PLAN.md -- Test-Cleanup + alle Acceptance-Greps ✅ 2026-05-22
- [ ] 08.23.2.C.R-08-PLAN.md -- Staging-Smoke-Test (checkpoint:human-verify)

### Phase 08.23.2.C.R.1: cold_call-phrases Re-Seed in Production-DB ❌ VERWORFEN 2026-05-24

**Status:** Verworfen + revertet 2026-05-24 nach Claudian-Diagnose-Fehler aufgedeckt.

**Was passiert ist:** Phase wurde via /gsd-quick durchgezogen (Commits 6092d3f + 595f837, Migration 0005 mit 18 Cold-Call-Phrasen, nie auf Staging applied). DANACH beim Andre-Phrasen-Review hat Andre gefragt "wo werden die Phrasen ausgespielt?" — und beim Code-Lookup festgestellt: **die phrases-Tabelle wird im echten Code-Pfad NUR für Gatekeeper-Modus gelesen** (`routes/app_routes.py` Z.1468: `Phrase.mode == 'gatekeeper'`). Es gibt KEINEN Code-Pfad der `phrases` WHERE `mode='cold_call'` liest. Die 18 Migration-0005-Phrasen wären toter Code in der DB.

**Wo die echten Cold-Call-EWB-Buttons herkommen:** `static/pip-launcher.js` Z.2099 `_renderEwbButtons()` liest aus `state.profileDaten.einwaende_detail` (oder fallback `einwaende`) — also aus dem **User-Profil**, nicht aus phrases-Tabelle. Andre's "fehlende EWB-Buttons im 20.05.-Live-Test" war NICHT durch leere phrases-Tabelle verursacht, sondern durch fehlende `einwaende_detail` im Test-Profil (separates Profil-Daten-Issue).

**Claudian-Selbst-Lerneffekt:** Pre-/gsd-quick Pflicht-grep: wird die betroffene Tabelle überhaupt im echten Code-Pfad gelesen? Wäre 2 Min Aufwand gewesen, hätte ganzen C.R.1-Detour erspart. Verankert für künftige Mini-Phasen.

**Revert-Aktionen 2026-05-24:**
- Migration 0005 Datei gelöscht (`alembic/versions/0005_seed_cold_call_phrases.py`)
- Plan-Files gelöscht (`.planning/quick/20260523-cr1-cold-call-phrases-reseed/`)
- DB-Cleanup nicht nötig: Migration war nie auf Staging applied (alembic_version blieb 0004)
- Production-Deploy-Plan: kein C.R.1-Block mehr, nur noch C.R + C.R.F

**Was bleibt:** Die echte Wurzel "fehlende EWB-Buttons im Test-Profil" bleibt offen — wird beim ersten echten EA-User mit befülltem Profil sichtbar oder nicht, abhängig vom User. Nicht Production-Blocker.

### Phase 08.23.2.C.R.2: Gatekeeper-Phrasen-Inhalt aus Praxis-Recherche ⏸ ABSORBIERT in 08.21 (Andre-Decision 2026-05-24)

**Status:** Verschoben + zusammengefasst in Phase 08.21 (Sales-Wisdom-Layer). Statt 10 statische Phrasen-Templates auszutauschen wird Gatekeeper-Modus auf KI-generierte Antworten umgebaut (Sales-Wisdom + Gatekeeper-spezifischer System-Prompt + Profil-Context). Anti-Abrieb-Reflex: statische Phrasen sind Pflaster, KI-Antworten mit Wisdom sind die saubere Lösung. Plus: YouTube-Sales-Mining-Tool unter `Nerve-Vault/07 Referenz/yt-sales-mining/` feeded beide (Cold-Call + Gatekeeper) mit gleichem Datenstrom — Andre sammelt URLs reaktiv (was Algorithmus ausspielt), Tool zieht Transkripte, Claudian extrahiert Patterns. Siehe Vault-Roadmap-Eintrag 08.21 für vollständigen absorbierten Scope.

**Original-Goal (historisch):** Andre-Live-Test 2026-05-20 hat die 10 Gatekeeper-Phrasen aus Migration 0003 als unrealistisch markiert. Phrasen waren aus Verhandlungs-Theorie-Literatur (Heinrich/Voss/Taxis) — nie gegen echte deutsche Sekretärs-Realität validiert. Andre hat selbst keine Cold-Call-Sekretärs-Erfahrung → kann Phrasen nicht aus eigener Real-Daten-Quelle schreiben → KI-Generierung aus Theorie würde gleichen Bettel-Ton produzieren.

**Strategie — Praxis-Recherche statt Theorie:**

Claudian (im Vault) führt gezielte Recherche durch echte Praxis-Quellen (nicht Verhandlungs-Bücher):
- Deutsche Cold-Call-Coach-YouTube-Videos mit echten Anruf-Mitschnitten
- Vertriebler-Foren wo Praxis-Skripte geteilt werden (LinkedIn-Posts, Reddit r/sales, Xing-Gruppen)
- Verkaufs-Coach-Blogs mit Beispiel-Dialogen
- Stichproben aus DACH-Telefonie-Anbieter-Best-Practice-Material (Placetel/NFON/Sipgate-Blogs)

Claudian liefert 30-40 Vorschläge in 4 Button-Kategorien. Andre wählt pro Button 2-3 finale Phrasen nach Bauchgefühl "Profi-Ton" vs. "Bettel-Ton". Andre-Filter ist Pflicht, kein KI-Auto-Pick.

**Scope:**
1. Recherche-Dokument `Nerve-Vault/03 Planung/NERVE Gatekeeper-Phrasen Praxis-Recherche YYYY-MM-DD.md` mit Quellen + Vorschlägen
2. Sparring-Pass mit Andre (~30-45 Min): Andre liest, kommentiert, wählt
3. Finales Vault-Dokument mit 10 finalen Phrasen (4 Buttons × 2-3 Varianten)
4. Alembic-Migration 0005 ersetzt 10 Phrasen in `phrases`-Tabelle (mode='gatekeeper') — Hinweis: ursprünglich als 0004 vorgemerkt, ist auf 0005 verschoben weil Migration 0004 in Phase 08.23.2.C.R den `call_events.event_type`-CHECK-Constraint um `mode_switch` + `mode_initial` erweitert
5. Pre-Deploy-Smoke-Test: Phrases sind in DB, Buttons zeigen neue Texte

**CLAUDE.md Punkt 13 (Real-Daten-Validation):** Wenn erste EA-Vertriebler im Live-Test sagen "Phrase X funktioniert nicht" → Update-Mechanismus aus C.R wird genutzt. C.R.2 ist Pre-EA-Best-Effort, nicht endgültig.

**Depends on:** Phase 08.23.2.C.R (Production-Deploy, Update-Mechanismus muss live sein)
**Komplexität:** 🟡 — Recherche-Quellen-Vielfalt + Andre-Filter ist eigener Cross-Check. Cross-AI optional.
**Blocker für:** keine harten Blocker (Phrasen-Update braucht nicht den Mechanismus aufzuhalten)

### Phase 08.23.2.C.R.F: Gatekeeper-Modul Fix-Pass ✅ 2026-05-23 (INSERTED — 2026-05-23) 🟡

**Status:** Abgeschlossen 2026-05-23 nachmittag mit Staging-Live-Test-Approval durch Andre. 12/12 must-haves grün, REQ-6 strukturell in DB verifiziert (1× mode_initial + 8× mode_switch sauber persistiert pro Test-Call). Plus Brand-Token-Hotfix nachgeschoben (blau → teal, Andre-Live-Befund) als Commit 78b1f11.

**Goal:** Live-Test 2026-05-23 hat zwei kritische Findings aufgedeckt die vor Production-Deploy gefixt werden müssen: (1) create_call_for_sid() wird im Production-Code nirgendwo aufgerufen → Skip-Guard greift immer → mode_switch + mode_initial nie persistiert → REQ-6 strukturell nicht erfüllt trotz Pytest-Grün. (2) Toggle-Button visuell zu blass → iOS-Style-Schalter (toggle switch).

**Scope:**
1. create_call_for_sid() in handle_start_live_session() integrieren — CLAUDE.md Punkt 14 Pflicht-Audit des gesamten Control-Flow-Pfads
2. Initial-Backend-Emit von contact_category_update beim Connect (verhindert "erster Klick wirkt nicht")
3. button → iOS-Style Toggle Switch CSS+HTML Migration (pip-mode-indicator)
4. Tests grün für mode_initial + mode_switch mit echtem call_id (nicht nur Mock)

**Depends on:** Phase 08.23.2.C.R (Code-Stand)
**Komplexität:** 🟡 — Code-Insert in bestehende Funktion (handle_start_live_session) = CLAUDE.md Punkt 14 Pflicht-Audit. Cross-AI Gemini bei Plan 01 empfohlen.
**Blocker für:** Production-Deploy von Phase 08.23.2.C + 08.23.2.C.R (gleiches Deploy-Fenster mit 08.23.2.C.R.1)
**Plans:** 3 Pläne ✅ abgeschlossen

Plans:
- [x] 08.23.2.C.R.F-01-PLAN.md -- create_call_for_sid() Hook + Initial contact_category_update Emit (atomic TOCTOU sentinel, Cross-AI-Fix) ✅ 2026-05-23
- [x] 08.23.2.C.R.F-02-PLAN.md -- pip-mode-indicator → iOS Toggle Switch (CSS+HTML+JS) ✅ 2026-05-23
- [x] 08.23.2.C.R.F-03-PLAN.md -- Behavioral handler tests via register_audio_handlers(mock_sio) ✅ 2026-05-23

**Code-Review-Notes für später (3 IN-Findings out-of-scope + Brand-Token-Lerneffekt):**
- Concurrent-Return-Log-Drift in deepgram_service.py: wenn Sentinel von parallel-Reconnect getroffen wird, loggt Caller fälschlich "DB-Fehler". WR-02 Code-Review-Fix hat das auf JS-Seite mit `contactCategory: 'gatekeeper'` Init mitigated. Backend-Log-Drift bleibt minor.
- Meeting-Modus Click-Handler Edge-Case: pip-launcher.js Click-Handler sollte `if (state.currentMode === 'meeting') return;` checken — sonst wechselt Meeting-Session zu Cold-Call wenn User auf Toggle-Bereich klickt obwohl Track via `display: none` ausgeblendet ist. Sehr selten weil visual nicht-klickbar wirkt.
- deploy.sh Drift-Pattern: tar-over-ssh überschreibt Dateien aber löscht keine → Geister-Test-Files können pytest-Collection blockieren. Empfehlung: rsync `--delete` ODER `find -newer` Cleanup ergänzen.
- Brand-Token-Pflicht-Check (NEU CLAUDE.md HART-Regel-Erweiterung): bei jeder neuen UI-Token-Definition Pflicht-grep gegen Brand-Tokens (`--btn-primary-bg-from`, `--accent`-Familie). Hardcoded-Farbe-Verbot ist eine Schicht, Brand-Konsistenz ist zweite Schicht. UI-SPEC vom 21.05. hat blau gewählt ohne Brand-Check.

**Schieber-UX-Polish deferred nach Block O Teil 2 (Visual-Polish via Claude Design):** Andre-Quote 2026-05-23: "die stelle ist zwar noch nicht gut aber wir gehen ja sowieso in einer späteren phase nochmal durch das design". Schieber-Position relativ zum Header, exakter Hover-State, Größen-Tuning werden in Block O finalisiert.

### Phase 08.23.2.D: Outcome-Erfassung + Audio-Qualitäts-Score ✅ 2026-05-27 (technisch fertig auf Production) (INSERTED — 2026-05-11, GSD-Roadmap-Sync 2026-05-26) 🟡

**Status:** ✅ Production-Deploy 2026-05-27 abgeschlossen. Migration 0005 live auf Postgres, Haiku-Classifier-Chain durchgängig, Brand-konforme UX (Teal-Outline), Dashboard-Reminder + Inline-Korrektur. 7 Hotfixes im Live-Test-Cycle gefangen + gefixt (Commit-Range f81e61c..0ab3680). Klassifikations-Qualität + UX-Polish (Inline-Korrektur, Score-Integration, Call-Bewertung-Knopf) wandern in Folge-Phase 08.23.2.D.UX. Vault-Roadmap-Eintrag bestand seit 2026-05-11. GSD-Roadmap-Sync 2026-05-26 nach Drift-Fund — CLAUDE.md "Vault-vs-GSD-Roadmap-Sync HART"-Regel ausgelöst, weil `/gsd-spec-phase 08.23.2.D` ohne Eintrag aus dem Bauch geraten hätte.

**Goal:** Pflicht-Modal nach jedem Anruf mit 5 Knöpfen (Termin / Rückruf / Kein Interesse / Falsche Person / Vertrag) + Optional-Notiz (durch Anonymisierungs-Strecke aus 08.23.2.B gejagt). Plus Audio-Qualitäts-Score pro Anruf aus Deepgram-Wort-Confidences (5 Metriken: mean, median, %-unter-0.7, längster unsicherer Block, stddev). Harte Schwelle 0,80 für Trainings-Korpus-Aufnahme (DPO-Gate in 08.23.2.E). Live-Warnung an User wenn rollender 10-Sek-Score unter 0,70.

**Scope (6 Tasks aus Vault-Roadmap):**
1. Frontend-Modal nicht-überspringbar nach Anruf-Ende
2. `calls.outcome` speichern (Optional-Notiz durch Anonymisierungs-Strecke)
3. Dashboard-Reminder wenn 7-Tage-Outcome-Quote unter 80%
4. Audio-Health-Berechnung als Hintergrund-Job nach Anruf-Ende
5. `calls.audio_health_score` persistieren
6. Empirische Kalibrierung gegen 200 Hand-Korrekturen (Pflicht in den ersten 100 Anrufen)

**Code-Pattern:** Vault-Repo `Nerve-Vault/03 Planung/NERVE DPO.md` Sektion F.2-F.8. Audio-Health-Code lebt im Backend nach Call-Ende (Hintergrund-Job, kein Live-Pfad).

**Depends on:** Phase 08.23.2.B ✅ (Anonymisierungs-Strecke), Phase 08.23.2.C + C.R + C.R.F ✅ 2026-05-24 (Production-Deploy)
**Komplexität:** 🟡 mittel — neue UX (Pflicht-Modal-Anti-Pattern-Risiko) + neuer Hintergrund-Job + Schema-Erweiterung `calls.outcome` + `calls.audio_health_score`. Cross-AI Pflicht (CLAUDE.md Punkt 7 — 🟡 immer Cross-AI).
**Blocker für:** Phase 08.23.2.E (DPO-Paar-Sammler nutzt `audio_health_score >= 0.80` als Gate für Trainings-Korpus-Aufnahme)

**Plans:** 7 Pläne in 6 Waves (erstellt 2026-05-26)

**CLAUDE.md-Pflicht-Pattern für die Spec/Plan-Phase:**
- **Punkt 7** Cross-AI Gemini Pflicht (🟡 mittel — keine Skip-Begründung möglich)
- **Punkt 13** Real-Daten-Validation: Schema-Änderungen (`calls.outcome` + `calls.audio_health_score`) gegen bestehende `calls`-Records prüfen — bestehende Records bekommen NULL und brauchen keine Backfill-Pflicht (Outcome ist Vorwärts-Feature, Audio-Health ebenfalls). Pflicht-Check trotzdem dokumentieren.
- **Punkt 14** Pre-Insert-Control-Flow-Audit: Modal-Trigger-Pfad nach Call-End in `services/live_session.py` + `routes/` komplett lesen (30 Zeilen vor/nach Insertion-Site, alle return/continue/break, Cross-File-grep wo `call.outcome` und `audio_health_score` gelesen werden würden)
- **Punkt 19** Pre-Execute-Audit: Plans vor Execute auf Placeholders + ungeprüfte Annahmen + Race-Conditions (Modal-Trigger vs. parallel-Reconnect) prüfen
- **Punkt 20** Pflicht-grep vor Migration + Code-Insert: wird `calls.outcome` + `audio_health_score` im echten Lese-Pfad genutzt nach Bau? Foundation-Code-Register-Eintrag falls Felder vor 08.23.2.E noch keinen aktiven Lese-Pfad haben

Plans:
- [x] 08.23.2.D-01-PLAN.md — Alembic-Migration 0005 (calls + outcome_* Felder + FK conversation_log_id) (REQ-D-1) — DONE 2026-05-26
- [x] 08.23.2.D-02-PLAN.md — services/outcome_service.py (Haiku-Classifier + Audio-Health-5-Metriken) (REQ-D-3, REQ-D-6) — DONE 2026-05-26
- [x] 08.23.2.D-03-PLAN.md — Word-Confidence-Buffer + Rolling-10s-Score + Hysterese-Emit in deepgram_service (REQ-D-7) — DONE 2026-05-26
- [x] 08.23.2.D-04-PLAN.md — api_beenden: calls-UPDATE + Audio-Health-Background-Thread + call_id in Response (REQ-D-2, REQ-D-6) — DONE 2026-05-26
- [x] 08.23.2.D-05-PLAN.md — api_postcall_analysis (Classifier+UPDATE+Emit) + Fallback-Pull + Korrektur-Endpoint (REQ-D-3, REQ-D-5, REQ-D-8, REQ-D-9) — DONE 2026-05-26
- [x] 08.23.2.D-06-PLAN.md — PiP Frontend: outcome_ready-Handler + 3-stufige UX + Korrektur-Modal + Audio-Warn (REQ-D-4, REQ-D-5, REQ-D-7) — DONE 2026-05-27
- [x] 08.23.2.D-07-PLAN.md — Dashboard Reminder-Card + Inline-Korrektur + Foundation-Code-Register (REQ-D-8, REQ-D-9, REQ-D-10) — DONE 2026-05-27

### Phase 08.23.2.D.UX: UX-Inline + Score-Integration + Klassifikations-Tuning (NEU 2026-05-27, GSD-Roadmap-Sync 2026-05-27) ✅ 2026-05-28

**Goal:** Folge-Phase aus Live-Test-Feedback Phase D. 4 Wellen: Wave 1 Security-Findings (CR-01 CSRF, CR-02 Ownership, WR-01/02/04 Sicherheit + IN-03 Debug-Cleanup), Wave 2 Klassifikations-Tuning (Plan-02 Snippet-Heuristik + Haiku-Prompt), Wave 3 Outcome-Pflicht-Schritt VOR Score-Reveal im PiP (Andre-Direktive 27.05.: "bevor der user seinen score sehen darf, bekommt er einmal dieses modal vorgesetzt"), Wave 4 coaching_score-Outcome-Modifier (Cross-AI-Architektur: process_score × outcome_modifier, NICHT Komponente) + Dashboard-Edit-Knopf für nachträgliche Korrektur.

**Score-Architektur final (Cross-AI 2026-05-27):**
- process_score = 30/30/20/10/10 (kb_end / behandelt_rate / redeanteil / skript / Reserve)
- final_score = clamp(process_score × outcome_modifier, 0, 100)
- Modifier: contract_signed=1.15, meeting_booked=1.10, callback=0.95, no_interest=0.85, wrong_person=1.00
- Roh-Werte-Persistierung pflicht (calls.coaching_score + calls.score_breakdown JSONB) für Phase-E-Tuning

**Pflicht-Patterns (CLAUDE.md):** Punkt 7 Cross-AI (🟡 + Security-Anteil), Punkt 13 Real-Daten-Validation, Punkt 14 Pre-Insert-Audit für Score-Migration, HART-Regel 27.05. (Default Production, kein Local-Dev), inspect.sh für Schema-Inspection.

**Depends on:** Phase 08.23.2.D ✅ 2026-05-27
**Komplexität:** 🟡 mittel mit Security-Anteil
**Blocker für:** keine direkten Blocker — kann parallel zu G/MEET laufen, aber UX-Coherence besser wenn G/MEET vor 08.21 fertig

**Plans:** 8 plans

Plans:
- [x] 08.23.2.D.UX-01-PLAN.md — Migration 0006: outcome CHECK (8 Werte) + followup_intent Spalte
- [x] 08.23.2.D.UX-02-PLAN.md — Migration 0007: score_breakdown + score_schema_version
- [x] 08.23.2.D.UX-03-PLAN.md — Security Fixes: CR-01/CR-02/WR-01/WR-02/IN-03
- [x] 08.23.2.D.UX-04-PLAN.md — Klassifikations-Tuning: Snippet-Heuristik + Few-Shot-Prompt
- [x] 08.23.2.D.UX-05-PLAN.md — Wave 3 PiP UX: 7 Buttons + Score-Gate + followup_intent
- [x] 08.23.2.D.UX-06-PLAN.md — Wave 4 Score-Persistierung: coaching_score + score_breakdown
- [x] 08.23.2.D.UX-07-PLAN.md — Dashboard Pencil-Edit Button + 7-Klassen Accordion
- [x] 08.23.2.D.UX-08-PLAN.md — DSGVO Art.6 Abs.1f Dokumentation + Cross-AI Gemini Log — DONE 2026-05-28

**⚠️ Live-Test-Bug 2026-05-28:** Andre's erster Test-Call nach Production-Deploy zeigte KEIN Outcome-Modal — System sprang direkt zur alten Auswertung. **Wurzel-Diagnose (via Logs + DB-Inspect):** Plan 04 hat in `routes/learning.py` angenommen `conv.log_entries` ist DB-Spalte auf conversation_logs. War aber nur Code-Variable im RAM während Calls — DB-Spalte existiert nicht. Transcript landet als TXT-Datei in `/opt/nerve/app/logs/`, classify() liest aus DB → leer. Folge: Haiku rät blind ohne Wortlaut → 0.65 confidence → `outcome=NULL, source=NULL` gesetzt → Frontend-Defensive-Check `if (paResult.outcome || paResult.source)` failed → kein Modal. **Cross-Layer-Bug, durch ALLE drei Schutzschichten gerutscht** (Cross-AI Gemini Pre+Post, zwei Pre-Execute-Audit-Runden Claudian, GSD Verification). Fix in **Phase 08.23.2.D.UX.1**. D.UX-UAT bleibt offen bis D.UX.1 durch. Plus: neue CLAUDE.md Hartregel Punkt 21 verankert (Cross-Layer-Audit-Pflicht) damit gleiche Bug-Klasse zukünftig gefangen wird.

### Phase 08.23.2.D.UX.0: Test-User-Pattern + Drei-Schichten-Backup-Foundation (NEU 2026-05-28, Foundation vor D.UX.1) ✅ ABGESCHLOSSEN + verifiziert 2026-05-29 (15/15 Must-Haves, live auf Production)

**Goal:** Zwei Foundation-Komponenten die VOR D.UX.1 stehen müssen damit Trainings-Daten-Sammlung sauber startet ohne Test-Daten-Verschmutzung in der Cloud.

**Andre-Quote 2026-05-28:** *"wenn wir das backup jetzt schon bauen dann werden ständig tests gespeichert in der cloud, dann müssen wir alles vor launch nochmal löschen was wir als backup gespeichert haben."* Lösung: Test-User-Pattern markiert Test-Calls, Backup-Schicht 3 filtert is_test_user-Calls aus → kein Cloud-Müll, kein Pre-Launch-Purge nötig.

**Drei Komponenten:**

**A) Test-User-Pattern (aus CLAUDE.md HART-Regel 27.05.):**
- Migration: `users.is_test_user BOOLEAN DEFAULT FALSE`
- Test-User-Account `andre-test@nerve.local` mit Flag=True anlegen
- DPO-Korpus-Sammler-Filter (Phase E nutzt das später)
- Analytics-Dashboard-Filter
- Calls vom Test-User bekommen `tag='test'` für spätere Daten-Filterung
- Email-Send-Schutz für Test-User (Test-SMTP oder Dummy — keine echten Emails an externe)

**B) Backup-Schicht 2 (Hetzner Storage Box):**
- Hetzner Storage Box bestellen (~3 EUR/Monat für 100 GB, gleicher AVV wie Hauptsystem)
- SSH-Key + Skript-Erweiterung in `scripts/backup_postgres.sh` → nach pg_dump auch zu Storage Box pushen
- 90 Tage Rotation
- Test-Restore-Verifikation
- Defense bei Server-Crash oder Disk-Failure

**C) Backup-Schicht 3 (IONOS S3 Object Storage):**
- Cross-AI-Empfehlung Gemini 2026-05-28: IONOS bevorzugt über Backblaze B2 wegen DSGVO-Eindeutigkeit (deutscher Anbieter, kein Drittland-Transfer-Issue)
- IONOS-Account + S3-Bucket anlegen, AVV abschließen
- **Object-Lock-Konfiguration (30 Tage WORM)** — Ransomware-Schutz, Gemini-Pflicht-Empfehlung
- Backup-Skript für `training.*`-Tabellen NUR (anonymisierte Daten, kein DSGVO-Issue beim Cross-Anbieter-Transfer)
- **Filter:** `WHERE source_call_hash NOT IN (SELECT call_hash FROM calls WHERE user_id IN (SELECT id FROM users WHERE is_test_user=TRUE))` — Test-Calls ausgefiltert
- 365 Tage Rotation
- Push-basiert via S3-CLI (s3cmd oder rclone)
- Test-Restore-Verifikation
- Verschlüsselung-at-rest verifizieren

**DSGVO-Pflicht:** `NERVE DSGVO Analyse.md` Sektion 3 (AVVs) um IONOS-AVV erweitern. Plus Sektion 7 um Schicht-3-Backup-Strategie + Begründung warum nur `training.*` outside Hetzner.

**Pflicht-Patterns:** CLAUDE.md Punkt 7 Cross-AI (🟡 mittel, AVV-Trigger + DSGVO-relevant), Punkt 21 NEU (Cross-Layer-Audit für users-Tabelle Erweiterung + Backup-Pfade auf Production), Punkt 19 (Pre-Execute-Audit für Backup-Skript-Erweiterung).

**Depends on:** keine (Foundation-Phase)
**Komplexität:** 🟡 mittel (zwei Komponenten, Cloud-Setup, AVV-Verhandlung)
**Blocker für:** Phase 08.23.2.D.UX.1 (Backup von Trainings-Daten muss VOR ersten echten Trainings-Daten existieren), Phase 08.23.2.E (DPO-Sammler braucht is_test_user-Filter)

**Plans:** 4 plans (2 waves) — ALLE ABGESCHLOSSEN 2026-05-29
- [x] 08.23.2.D.UX.0-01-PLAN.md — Test-User-Pattern + Migration 0008 (training-Schema + transcript_archive + nerve_anon_worker GRANTs + is_test_user + Email-Guard + Seed) [A/D, wave 1] — DONE 2026-05-29
- [x] 08.23.2.D.UX.0-02-PLAN.md — Backup-Schicht 2: Hetzner Storage Box rsync-Push + 90d-Rotation + Restore-Test [B, wave 1] — DONE 2026-05-29
- [x] 08.23.2.D.UX.0-03-PLAN.md — Backup-Schicht 3: IONOS S3 WORM-Backup + systemd-Timer + monatl. Restore-Test + /api/health [C, wave 2, depends 01] — DONE 2026-05-29
- [x] 08.23.2.D.UX.0-04-PLAN.md — DSGVO-Doku: IONOS-AVV (Sektion 3) + Schicht-3-Strategie (Sektion 7) [X, wave 2, depends 03] — DONE 2026-05-29

WARN D-02 Downstream: D.UX.1-Migration muss von 0008 auf 0009 umnummeriert werden (D.UX.0 belegt 0008). transcript_segments-GRANT gehört in 0009, nicht 0008.

### Phase 08.23.2.D.UX.1: Transcript-Persistence + Outcome-Force-Wahl-Bug-Fix (NEU 2026-05-28, aus D.UX-Live-Test-Bug-Befund) 🔴 ✅ ABGESCHLOSSEN + live verifiziert 2026-05-30 (3 Bugs gefixt, Production HEAD a2d7d3c, conv 200: 11 Segmente + meeting_booked 0.96; Modal rendert)

**Goal:** Drei Bugs eine Wurzel fixen damit D.UX-Outcome-Modal tatsächlich funktioniert.

**Bug-Liste:**
- **Bug A (Wurzel):** Transcript wird als TXT-Datei gespeichert, NICHT in DB → outcome_service.classify() bekommt leere log_entries
- **Bug B:** Backend bei confidence < 0.70 setzt outcome+source auf NULL (statt outcome=Haiku-Best-Guess + source='ai_auto_unsicher')
- **Bug C:** Frontend bei outcome+source=NULL: kein Modal rendern (statt Force-Wahl-Modal ohne Vorauswahl)

**Tasks:**
1. **Bug A:** Migration `0008` mit neuer `conversation_logs.log_entries`-Spalte als JSONB (oder eigene `transcript_segments`-Tabelle mit FK — Architektur-Entscheidung in Spec-Phase). Plus `services/live_session.py` beim Call-Ende: Transcript-Segments aus RAM in DB schreiben (anonymisiert wie schon in TXT-Datei).
2. **Bug B:** `routes/learning.py` Z.97-101 — bei confidence < 0.70: outcome=Haiku-Vorschlag + source='ai_auto_unsicher' (nicht NULL).
3. **Bug C:** `static/pip-launcher.js` Z.2956 — Defensive-Check erweitern: auch rendern wenn call_id + confidence>0, auch wenn outcome+source=null (Force-Wahl-Modal ohne Vorauswahl).
4. DSGVO-Anpassung: Transcript-Persistierung war bisher TXT-Datei. Neue DB-Spalte erweitert `04 Entscheidungen/NERVE DSGVO Analyse.md` Sektion 7. Plus Cascade-Delete für log_entries bei User-Löschanfragen.
5. Re-Test der D.UX-UAT-Items nach Fix-Deploy.

**Pflicht-Patterns:** CLAUDE.md Punkt 7 Cross-AI (🟡 mittel), Punkt 14 Pre-Insert-Audit, **Punkt 21 NEU (Cross-Layer-Audit-Pflicht):** Persistenz-Schicht-Verifikation für conversation_logs UND calls UND alle Tabellen die TXT-Logging-Code anfasst. Plan MUSS Sektion `## 5. Persistenz-Schicht-Verifikation` mit inspect.sh-Output für jede angefasste Tabelle + Cross-Layer-Konsistenz-Tabelle enthalten.

**Depends on:** Phase 08.23.2.D.UX ✅ 2026-05-28 (technisch fertig, Live-Test-Bug muss aber zuerst hier gefixt werden)
**Komplexität:** 🔴 komplex (DB-Migration 0010 + DSGVO/Cascade-Delete + Schema + FE+BE multi-layer — Cross-AI Pflicht vor Execute)
**Blocker für:** D.UX-UAT-Pass, Phase 08.23.2.D.UX.2 (Transcript-Reiter braucht DB-Persistierung), Phase 08.23.2.E (DPO-Sammler nutzt log_entries als Trainings-Korpus-Input)

**Plans:** 5 plans (3 waves) — geplant 2026-05-30 (🔴 Cross-AI-Review PFLICHT vor Execute)
- [x] 08.23.2.D.UX.1-01-PLAN.md — Bug-A-Foundation: Migration 0010 transcript_segments + TranscriptSegment-Model + [BLOCKING] migration-apply [DA-01/02/03, DD-01, DP-01; wave 1] ✅ live head=0010
- [x] 08.23.2.D.UX.1-02-PLAN.md — Bug-A Write-Pfad: api_beenden transcript_segments INSERT (speaker/ts_ms-Transform + Idempotenz) [DA-04, DP-02; wave 2] ✅ (DA-06 training-Doppelschreib -> Phase E verschoben)
- [x] 08.23.2.D.UX.1-03-PLAN.md — Bug-A Read-Pfad + Bug B: learning.py DB-Read statt getattr + Schwellen-Rewrite (Best-Guess behalten) + confidence=0 Telemetrie [DA-05, DB-01/02/03/04, DP-02; wave 2] ✅
- [x] 08.23.2.D.UX.1-04-PLAN.md — Bug C: pip-launcher.js _decideModalState 5-Zustaende + 3 Call-Sites + node:test [DC-01/02/03/04; wave 1] ✅ (Decider in UMD-Helper outcome-modal-state.js)
- [x] 08.23.2.D.UX.1-05-PLAN.md — DSGVO + Re-Test: Soft-Delete-Gap-Entscheidung (Option A) + audit log_action + DSGVO-Doku Sektion 7 + Live-Re-Test [DD-01/02/03/04, DP-01/02, DT-01/02/03; wave 3] ✅

**Folge-Items aus D.UX.1 — promotet zu echten Phasen 2026-05-30:** OUTCOME-ORDER → Phase 08.23.2.D.UX.4 (🟡, NÄCHSTE PHASE), ART17-PURGE → Phase 08.23.2.ART17 (🔴 START-BLOCKER vor EA-Launch), Login-Härtung → Phase 08.23.2.LOGIN (aus Backlog 999.1 promotet, 🟡 START-BLOCKER Login-Audit-Teil). DA-06 Training-Archiv-Doppelschreib → Phase E.

### Phase 08.23.2.D.UX.2: Transcript-Reiter UI im PiP + Auswertung + Dashboard (NEU 2026-05-28, Andre-Feature-Wunsch) 🟡

**Goal:** Transcript-Reiter an drei UI-Stellen damit Cold-Caller nicht mehr mitschreiben muss während er telefoniert.

**Andre-Quote 2026-05-28:** *"Was ich auch gern hätte in kürze ist ein Transskript reiter. Gerne auch an mehreren Stellen. Einmal während des Calls, dann in jeder auswertung (Pip und in der kompletten auswertung). das führt dann dazu das user auch nicht zwingend sofort mitschreiben müssen und sich komplett auf den call konzentrieren können."*

**Tasks:**
1. Transcript-Reiter im PiP **während Call** — Live-Scroll der Transcript-Segments. Hidden-Default, optional einblendbar via Tab/Knopf.
2. Transcript-Reiter in PiP-Post-Call-Auswertung — direkt nach Outcome-Bestätigen sichtbar als Reiter neben Score + Lernkarten.
3. Transcript-Reiter im Dashboard-Call-Detail-View — User klickt alten Call → Detail-Seite öffnet → Transcript ist Reiter neben Score-/Outcome-/Lernkarten-Reitern.
4. **Optional Bonus:** Such-/Highlight-Funktion im Transcript (z.B. nach "Termin", "Einwand").
5. **Aus-/einklappbares Panel im PiP** (nicht nur Tab) — erreichbar per Knopf aus der PiP-Score-Ansicht UND der vollen Auswertung (Andre 2026-05-30).
6. **Text-Markieren + Copy-out** — User kann Transcript-Stellen rauskopieren / extern speichern.

**Warum wichtig (Andre 2026-05-30, "finde ich definitiv wichtig"):** (a) für uns bei Tests — prüfen ob was zerschossen wurde; (b) für User — gute Out-of-Script-Momente / neue Einwände rauskopieren zum Nachdenken/Speichern.

**UI-SPEC nötig** für drei UI-Kontexte mit unterschiedlichen Constraints (PiP-eng vs. Dashboard-breit) — `/gsd-ui-phase` Pflicht.

**Depends on:** Phase 08.23.2.D.UX.1 (Transcript-DB-Persistierung)
**Komplexität:** 🟡 mittel (drei UI-Kontexte, neue Reiter-Komponente, neue API-Endpoints für Transcript-Pull)
**Blocker für:** keine direkten

**Plans:** 4 plans (2 Waves) — geplant 2026-06-03. 🟡 + Trigger (FE+BE gleichzeitig, neuer Endpoint) -> Cross-AI Pflicht VOR Execute. **CODE-COMPLETE 2026-06-03 (alle 4 Plans, inline ausgeführt — Multi-Segment-ID-Gotcha: gsd-tools/gsd-code-review/gsd-verifier umgangen, Pfade hardcoded, STATE/ROADMAP hand-editiert). Manuell goal-backward verifiziert + node --check OK. NOCH NICHT auf Prod deployed — André fährt `deploy.sh production` + Live-UAT (CLAUDE.md HART: Production-only Verify). NICHT auto-advanced.**
Plans:
- [x] 08.23.2.D.UX.2-01-PLAN.md — Foundation: n-tabs.js (reusable Vanilla-JS Tabs, deep-link+last-tab+ARIA+n-tab:activated+hashchange) + nerve.css Transcript-/Tab-Tokens [R-01, R-03; wave 1] ✓ SUMMARY
- [x] 08.23.2.D.UX.2-02-PLAN.md — Endpoint GET /api/transcript/<int:id> in learning_bp, owner-scoped, anonymisierte DB-Segmente + Persistenz-Schicht-Verifikation [DQ-02; wave 1] ✓ SUMMARY
- [x] 08.23.2.D.UX.2-03-PLAN.md — session_detail.html Reiter-Umbau (Übersicht/Transkript) + lazy fire-once Fetch/Suche-Highlight/Copy-All [R-02, R-03, TT-01/02/03; wave 2] ✓ SUMMARY
- [x] 08.23.2.D.UX.2-04-PLAN.md — PiP Live side-by-side (resize-Spike-Blueprint + ResizeObserver) + Live-Segment-Render (Neubau) + Auto-Scroll + Post-Call collapsible (RAM) [PT-01/02/03, DQ-01/03; wave 2] ✓ SUMMARY

### Phase 08.23.2.STT: Deepgram-Qualität — nova-3 + Fachwort-Liste (keyterm) + Sprecher-Label-Fix (NEU 2026-06-05) 🟡 — ✅ COMPLETE 2026-06-05 (live auf Prod, git_head bbd90ef)

**Ergebnis Live-Test (2 Calls 09:31 cold_call + 09:33 meeting):** `[DG] LiveOptions: model=nova-3 ... keyterm_count=41` (Grundliste 16 + 25 Profil-Terms, KEIN SDK-Fallback → keyterm-Kwarg von deepgram-sdk akzeptiert, Gemini-HIGH-Risiko nicht eingetreten). Transkript klar besser: NERVE/Vertriebler/Einwände/Kalendereinladung/Cold Calls korrekt, Verdopplung weg, cold_call `[Berater]`-Label statt `[Unbekannt]`. Restfehler inkonsistent (tagesform) → **Stufe 2 datenbasiert** nach mehr Call-Samples (Name in keyterm, keyterm-Gewichtung, endpointing). Deploy via Claudian (deploy.sh upload + manueller systemctl restart wegen pre-existing test_ft_seed-Gate). **Folge-Items (Block J Vault):** Cold-Call-Redeanteil-Disclaimer + nicht-in-Score (Redeanteil ist Single-Speaker konstruktiv 100%). **Offen (NICHT STT-verursacht):** Meeting → Scoreboard ja, große Auswertung nein (separater Bug, eigene Untersuchung).

**Goal:** Live-Transkript-Qualität heben. nova-2→nova-3 + keyterm-Fachwort-Liste gegen zerschossene Domain/Brand-Wörter + Sprecher-Label-Fix im Cold-Call.

**Diagnose 2026-06-05 (Claudian, gegen 5 rohe Production-Test-Calls im journalctl `[DG]`-Log):** Verdopplung ("Die die meisten", "ein eine Kalendereinladung", "fehlt die fehlt die", "ein mit Ihnen gerne einen") + Garbling stehen INNERHALB einer einzelnen `is_final`-Zeile → kommt aus **Deepgram-Rohausgabe, NICHT aus unserem Merge-Code** (`_flush_segment` joint nur Finals mit Space, kann mitten in Satz kein "die die" erzeugen). Verifiziert: (a) Sample-Rate/Encoding 16kHz linear16 stimmt Frontend↔Backend (audio-processor.js Int16 + AudioContext 16000 ↔ deepgram_service SAMPLE_RATE=16000) → KEIN Mismatch; (b) saved transcript + transcriptSegments nutzen nur `type==='final'` (pip-launcher.js:2278) → kein Interim-Leak.

**Fehler-Cluster:**
1. Fachwörter/Marken zerschossen: "Einwände"→"ein, wenn", "Cold Calls"→"Callcalls/Call Codes/Call Calls", "NERVE"→"Nerf/Neuauf/Nerfh", "Vertriebler"→"Fahrradbetreiber", "die mithört"→"die Mütter".
2. Verdoppelte Grenz-Wörter (Endpointing/Segmentierung — inkonsistent: derselbe Satz mal sauber mal doppelt über die 5 Calls).
3. Abgehackte Satz-Anfänge ("rufe an bei Vertrieb dabei unterstützen" — "wir" fehlt).

**Doku-Check (context7 /websites/developers_deepgram):** Keyterm-Prompting (`keyterm`) ist NUR mit nova-3 kompatibel — nova-2 nutzt das ältere/schwächere `keywords`. nova-3 = 54 Sprachen inkl. Deutsch. Keyterm verfügbar für nova-3 monolingual + multilingual.

**Strategie — 2 Stufen (Hebel-Isolierung, nicht alles auf einmal):**
- **Stufe 1 (diese Phase):** `model="nova-2"`→`"nova-3"` + `keyterm`-Fachwort-Liste (Brand + Sales-Vokabular) + Sprecher-Label-Fix. Dann frische Test-Calls von Andre → Claudian zieht `[DG]`-Roh-Logs via `inspect.sh logs` + vergleicht vorher/nachher.
- **Stufe 2 (nur falls Verdopplung bleibt):** `endpointing`/`utterance_end_ms`-Timing nachjustieren.

**Sprecher-Label-Fix:** Im Cold-Call ist `diarize=False` → `_get_speaker` immer None → `roles_confirmed` bleibt False → jede Zeile Label "Unbekannt"/SYSTEM. Im Cold-Call ist es immer der Berater. Fix in `_make_on_message` (deepgram_service.py:78-84): bei mode=cold_call Label hart "Berater".

**Datei:** `services/deepgram_service.py` — `_open_deepgram_connection` Z.310-324 (LiveOptions: model + keyterm), `_make_on_message` Z.61-88 (Label-Logik). **NICHT** `nerve_rt/services/stt/deepgram_adapter.py` (experimentelle Engine, nicht Live-Pfad).

**Fachwort-Liste = 3-Schichten-Architektur (Andre-Decision 2026-06-05, Anti-Abrieb):** KEINE manuelle Pro-Branche-Recherche (Fass ohne Boden). Stattdessen:
1. nova-3 trägt das allgemeine Deutsch (die schlimmsten Fehler waren normale Wörter wie "Einwände", kein Fachsprech → nova-3 räumt davon viel weg, null Pflege-Aufwand).
2. Kleine FESTE Sales-Grundliste (~15 Wörter: Einwand/Einwandbehandlung/Cold Call/Kaltakquise/Kaufsignal/Vorwand/Kalendereinladung/Vertriebler/Opener/Entscheider etc.) — gilt universell, einmal gebaut.
3. Branchen-Wörter AUTOMATISCH aus dem User-Profil extrahiert (Produktname, Branche, einwaende_detail, profile_faqs, profile_skripte) → pro Call als keyterm mitgegeben. Der Kunde liefert sein Vokabular durch Profilpflege. Skaliert ohne unsererseits Branchen-Lexika; ist Verkaufs-Argument (bessere Profilpflege = bessere KI). Margin-/Automate-Säule (CLAUDE.md Punkt 12).

**Pre-Plan-Pflicht:**
- context7 für exakte `keyterm`-Parameter-Syntax + keyterm-LIMIT in `LiveOptions` (Deepgram Python SDK) — SDK-Drift-Schutz. Limit bestimmt Längen-Cap der Profil-Extraktion.
- Profil-Extraktions-Logik designen: welche Felder, Dedup gegen Grundliste, Längen-Cap, wo im Session-Init (`handle_start_live_session` lädt Profil schon → keyterm dort ableiten vor `_open_deepgram_connection`).
- DSGVO-Hinweis: Brand/Eigenname als keyterm = nur Erkennungs-Hilfe, Anonymizer schwärzt danach normal weiter. Cross-AI absegnen lassen.
- Real-Daten via `inspect.sh logs` (HART-Regel: keine lokalen Tests, Production-Pfad).

**Test:** nur Production (HART-Regel Kein-Local-Dev). Frische Test-Calls von Andre, Claudian zieht `[DG]`-Logs + Soll-Ist-Vergleich gegen bekannten Pitch.

**Depends on:** keine harte.
**Komplexität:** 🟡 mittel (Kern-STT-Config, betrifft ALLE Calls). **Cross-AI Pflicht** (Punkt 7).
**Blocker für:** Phase 08.23.2.E (DPO-Korpus-Qualität — schlechte Transkripte = schlechte Trainingsdaten), Transkript-Wert von D.UX.2.
**Priorität:** vor Phase E, kann vor/parallel zu D.UX.3.

**Plans:** 2 plans (2 Waves, sequenziell — beide nur `services/deepgram_service.py`) — geplant 2026-06-05. RESEARCH (context7-verifiziert) + plan-checker PASSED 1. Iteration (0 Blocker/0 Warning/3 INFO). Cross-AI Review (Gemini) 2026-06-05 → Replan `--reviews` (HIGH SDK-Fallback + MEDIUM A1-Verify + MEDIUM DB-Smell-Note + LOW deferred), plan-checker PASSED 1. Iter. **EXECUTED 2026-06-05** (Commits 3705664…01ce28f, Code-Level-Must-Haves statisch verifiziert). Verzeichnis: `.planning/phases/08.23.2.STT-deepgram-qualitaet-nova3-keyterm-sprecher-label/`. ⏳ **Production-Verifikation offen** (HART: nur auf Prod testbar) → siehe `08.23.2.STT-HUMAN-UAT.md`.
Plans:
- [x] 08.23.2.STT-01-PLAN.md — nova-2→nova-3 (model+cost-tag+[DG]-log) + 3-Schichten keyterm (`build_keyterms`: feste Sales-Grundliste + Profil-Layer aus `basis.produktbeschreibung`/`basis.unternehmen`/`Profile.branche`/`einwaende_detail`, dedup, MAX_KEYTERMS=60, 500-Token-Limit) + **Reorder** (additiver Mini-Profil-Load VOR `_open_deepgram_connection`) + try/except keyterm-Fallback (Review HIGH) → `LiveOptions(keyterm=[...])` [wave 1] ✅ executed
- [x] 08.23.2.STT-02-PLAN.md — Cold-Call Sprecher-Label-Fix: `_make_on_message(sid, mode)` Closure-Wiring + bei cold_call `emit_speaker=0`/`roles_confirmed=True`/`sp_name='Berater'`, Meeting-Pfad (diarize=True) strikt unverändert [wave 2, depends_on 01] ✅ executed
**Korrektur ggü. Original-Eintrag (RESEARCH grep-belegt):** Feldnamen oben waren teils falsch (kein `Produktname`; `Branche`=DB-Spalte `Profile.branche`; `einwaende`→`einwaende_detail` top-level). `profile_skripte`+`profile_faqs` = eigene DB-Tabellen, nicht im Session-Cache vor dem keyterm-Load → für Stufe 1 DEFERRED. Stufe 2 (endpointing/utterance_end_ms) bleibt out-of-scope.
**keyterm context7-Befund:** `keyterm` (singular, repeated/Liste, **nova-3-only**), German GA, Limit 500 Token/Request. A1-Restrisiko (Listen→repeated-param vs CSV-Blob) → 1.-Prod-Log-Check in Plan 01.

### Phase 08.23.2.D.UX.3: Anonymisierungs-Tuning — Wortteil-Bug + Pronomen + Whitelist + Konfidenz (NEU 2026-05-28; neu priorisiert 2026-06-05) 🟡 ✅ COMPLETE 2026-06-05

**Goal:** Anonymizer (GLiNER + spaCy, `services/anonymization.py`) repariert + entschärft — Trainings-Daten-Qualität für Phase E + lesbare Transkripte sichern.

**⭐ REAL-DATEN-BEFUND 2026-06-05 (Claudian, echtes Cold-Call-Transkript von heute via `inspect.sh` / TXT-Log `/opt/nerve/app/logs/`):** Die Über-Schwärzung überlappt fast NICHTS mit dem Profil — NUR der Firmenname (NERVE→`[ORG_A]`). Die ursprüngliche Annahme "Profil-Whitelist löst das" ist falsch: sie löst genau 1 Wort. Echte Belege heute + neue Wirk-Reihenfolge:

**Tasks (neu sortiert nach Wirkung):**
1. **WORTTEIL-BUG FIXEN (wichtigster Hebel, ECHTER CODE-BUG):** Die Replace-Logik ersetzt Buchstaben-Folgen MITTEN im Wort statt nur ganzer erkannter Entity-Spans. Belege heute: `ausführliche`→`ausführl[PERSON_C]e`, `wirklich`→`wirkl[PERSON_C]`, `Ich`→`[PERSON_B]`, `Sie`→`[PERSON_D]`. Root-Cause vermutlich nacktes `str.replace(token, tag)` über den ganzen Text statt Offset-basiertes Ersetzen der NER-Entity-Spans. Fix: whole-word/Span-basiert ersetzen (Entity char-offsets von GLiNER/spaCy nutzen, rückwärts ersetzen). **Pflicht Real-Daten-Validation (Punkt 13):** gegen heutige TXT-Logs verifizieren.
2. **Pronomen-Whitelist** (Ich, mich, mir, mein, Sie, Ihr, ihr, du, dich, dir, dein, wir, uns, …) — werden NIE anonymisiert. Größter sichtbarer Einzel-Gewinn.
3. **GLiNER-Konfidenz-Schwelle erhöhen** — Fehlalarme wie `nach dem Anruf`→`[LOC_A]` raus.
4. **Generic-Berufs-Wort-Liste** (Vertriebler, Berater, Manager, Verkäufer, Geschäftsführer, …) — nie als ORG tokenisiert.
5. **Firmenname aus Profil `basis.unternehmen`** (NEBENDARSTELLER, löst nur NERVE — Feld heute via STT-Phase verifiziert vorhanden, kein neues Profilfeld nötig). Plus Doppel-Klammer-Token-Bug `[PERSON_B]B]`.
6. Re-Test mit kuratiertem Goldstandard-Korpus (heutige Transkripte als Basis).

**Depends on:** keine
**Komplexität:** 🟡 (hochgestuft von 🟢 — Task 1 ist echte Logik-Änderung in der Replace-Mechanik, kein reines Config-Tuning). Cross-AI optional.
**Blocker für:** Phase 08.23.2.E (DPO-Paar-Sammler — Trainings-Daten würden sonst durch Over-Anonymisierung + Wortteil-Bug verzerrt)
**Plans:** 1 plan (1 Wave, autonomous:false) — geplant + Cross-AI (Gemini) + --reviews-Replan + ✅ ausgeführt + UAT PASS 2026-06-05. RESEARCH korrigierte ROADMAP-Hypothese: Wortteil-Bug sitzt in `anonymize_output` (naked text.replace), NICHT `_apply_ner` (bereits span-korrekt); Pronomen-Whitelist = Wurzel-Fix. Gemini-Findings eingearbeitet: GLINER_THRESHOLD Default **0.55** (nicht 0.6) + ENV-Override, `_is_whitelisted`-Pflicht-Helper, 5-10-Call-Korpus-Gate, defensiver Dict-Zugriff. **Folge-Fix-Pass 1 (Prod-Log Call 15:04, commit 18a95a1):** (1) Doppel-Klammer `[PERSON_E]SON_D]` = überlappende Union-Voting-Spans → `_dedup_overlapping_spans` (längster gewinnt) in beiden NER-Funktionen; (2) generische Über-Schwärzung (wir Vertriebler/Vertriebsteams/Einkauf/Viele Firmen) → `_is_whitelisted` typ-unabhängig + Mehrwort-Check + Liste erweitert; (3) ORG-Teil-Leak `[PERSON_J] Brennecke GmbH` → durch (1) mit-behoben. UAT-Re-Test 2026-06-05: alle 3 Abweichungen weg, DSGVO-Gate hält (alle echten Namen geschwärzt @0.55). Deploy manual-direct-prod. Verzeichnis hardcoded `.planning/phases/08.23.2.D.UX.3-anonymisierungs-tuning/`. gsd-sdk/gsd-code-review/gsd-verifier umgangen (Multi-Segment-Gotcha).
Plans:
- [x] 08.23.2.D.UX.3-01-PLAN.md — Anonymizer-Tuning: Pronomen/Berufs/Org-Whitelist + `_is_whitelisted`-Helper + GLINER_THRESHOLD 0.55 (ENV) + wortgrenzen-gehaerteter `anonymize_output` (Wortteil-Bug-Root-Fix in OUTPUT-Pfad, NICHT `_apply_ner`) + `_dedup_overlapping_spans` (Folge-Fix) + basis.unternehmen-Registrierung + Goldstandard-Re-Test [R1-R6; wave 1] ✅ executed + UAT PASS

### Phase 08.23.2.D.UX.4: Call-Ende-Ablauf-Redesign — Ergebnis-vor-Score (NEU 2026-05-30, aus D.UX.1-Live-Test) 🟡 ✅ COMPLETE 2026-05-31

**Goal:** Reihenfolge beim Auflegen umdrehen — erst Outcome bestätigen, dann Score EINMAL sauber rechnen+zeigen. Plus Outcome-Abfrage sofort im PiP statt verzögert im Dashboard-Auswertungs-Ladebildschirm.

**Befund Andre's Live-Test 2026-05-30 (D.UX.1):** Score wird BERECHNET BEVOR Outcome bestätigt ist → bestätigtes Outcome fließt nicht in die erste Score-Anzeige. Ergebnis-Fenster wartet auf Auswertungs-Ladebildschirm (~10-15s spät, im Dashboard) statt sofort im PiP.

**Claudian Code-Lesung 2026-05-30:** Logik "Outcome beeinflusst Score" STEHT bereits — `_calc_coaching_score(conv, outcome)` (routes/app_routes.py:720) mit `_OUTCOME_MODIFIERS` (contract_signed ×1.15, meeting_booked ×1.10, no_interest ×0.85) + `correct_outcome` (Z.1923) rechnet Score neu bei Bestätigung/Korrektur. → Reihenfolge-Umbau (🟡), KEIN Neubau (nicht 🔴).

**Tasks:**
1. Ablauf umdrehen: erst Outcome-Abfrage, dann Score-Berechnung EINMAL (statt vorläufig-zeigen-und-still-nachrechnen).
2. Beim Auflegen kurzer Ladebalken im PiP während die KI das Outcome aus dem Transkript schätzt, DANN Auswahl-Screen mit KI-Vorauswahl (bewusst sequenziell, KEIN async-Preselect — vermeidet Race-Bugs).
3. "Call wirklich beenden?" + Outcome-Abfrage als EIN Schritt (Andre-UX).
4. Zweiter Ladebalken danach für Detail-Auswertung.

**Entscheidung 2026-05-30 (Andre):** KEIN vorläufiger Score. Der Score wird ERST berechnet wenn das Outcome gewählt ist (User bestätigt oder KI-Vorauswahl übernommen) — keine Doppelrechnung. Ablauf: Auflegen → Ladebalken (KI schätzt Outcome aus Transkript) → Auswahl-Screen mit Vorauswahl → User bestätigt/korrigiert → Score EINMAL rechnen+zeigen. Der Auswahl-Screen erscheint IMMER erst NACH der KI-Analyse → immer eine KI-Vorauswahl (kein leerer Screen, kein "später nachtragen"). Bei unsicherer KI (selten): Vorauswahl wird trotzdem getroffen, aber ROT hinterlegt + Disclaimer im PiP ("KI unsicher, bitte prüfen") — zwingt den User bei wackeligen Fällen zum Hinschauen, gut für Daten-Qualität. Echter KI-Ausfall (sehr selten) = degradierter Modus, Plan-Detail.

**Cross-AI Pflicht** (🟡, Punkt 7). **Pre-Plan-Check Punkt 21:** Persistenz-Schicht `calls` (outcome, coaching_score, score_breakdown).

**Depends on:** Phase 08.23.2.D.UX.1 ✅
**Komplexität:** 🟡 mittel — Reihenfolge-Umbau Frontend (PiP) + Backend-Score-Trigger, keine Schema-Änderung
**Blocker für:** keine direkten. **Priorität vor D.UX.2/.3** (dort keine harte Abhängigkeit).
**Koordination mit D.UX.2:** neuen Post-Call-Score-Screen so bauen, dass D.UX.2 später Transkript-Knopf/ausklappbares Panel dranhängen kann (Platz lassen, kein Umbau) — Anti-Abrieb.
**Plans:** 3 plans (2 Waves) — geplant 2026-05-31, ✅ ausgeführt + deployed + UAT PASS 2026-05-31. Cross-AI (Gemini) + Claudian-Pre-Execute-Audit + 1 Live-UAT-Bug (leeres PiP: _showLadebalken1 versteckte den Outcome-Container → gefixt, Section sichtbar). Option-3-Scope: keine Karten/Ladebalken-2 im PiP (Sonnet laeuft im Hintergrund, persistiert LearningCards). Deploy: manual-direct-prod (tar-over-ssh, kein git pull — Prod ist tar-deployed mit .git excluded).
Plans:
- [x] 08.23.2.D.UX.4-01-PLAN.md — Backend Score-Split: _calc_process_score + _apply_outcome_modifier, Beenden-Stash, correct_outcome-Rewire [S-02/S-01/L-01; wave 1] ✅
- [x] 08.23.2.D.UX.4-02-PLAN.md — Backend Postcall-Split: /api/postcall_outcome (Haiku schnell) + /api/postcall_cards (Sonnet, confirm-unabhaengig im Hintergrund) [L-04/LB-04/B-01; wave 1] ✅
- [x] 08.23.2.D.UX.4-03-PLAN.md — Frontend Reorder: Hold-to-end (B-02), Ladebalken 1 (Option-3: kein Ladebalken-2/keine Karten im PiP), Outcome-Screen 3 States (U-01 rot), Score+Analytics S-03 (pipEl), _calcScore raus (L-01) [alle FE-IDs; wave 2] ✅

### Phase 08.23.2.ART17: Art. 17 Hard-Delete — echtes PII-Löschen (NEU 2026-05-30, promotet aus D.UX.1-Folge-Item) 🔴 START-BLOCKER vor EA-Launch

**Goal:** Echtes Löschen/Anonymisieren von PII bei Account-Löschung. DSGVO Art. 17. Heute nur Soft-Delete ("inaktiv"-Flag).

**Stand nach D.UX.1 (Option A):** Soft-Delete bleibt + Lösch-Anfrage im Audit-Log (`user_deletion_request` via log_action). Diese Phase aktiviert das echte Hard-Delete + Cascade.

**Tasks:**
1. Hard-Delete-Pfad: echtes PII-Löschen oder Anonymisieren bei Account-Löschung.
2. Lösch-Kaskade über alle PII-haltenden Tabellen aufwecken — Entscheidung pro Tabelle: Hard-Delete vs. anonymisierter Tombstone (Trainings-Daten bleiben anonymisiert erhalten).
3. Cross-Layer-Inventur welche Tabellen PII halten (Punkt 21): users, profiles, conversation_logs, transcript_segments, calls, call_events, suggestions/reactions falls vorhanden. **PLUS (Holistic-Review 01.06.): die neuen crm-Tabellen (accounts/contacts/account_memory/meetings) — sie halten Klartext-PII (Namen, MEDDPICC, context_hooks).**
   - **⚠ HOLISTIC-REVIEW-CONSTRAINT (Gemini 01.06., HIGH/Drift):** die crm-FKs (Migration 0012: `account_id`/`contact_id` → crm.accounts/contacts, `tenant_id` → public.tenant_orgs) haben KEIN `ON DELETE CASCADE` (Drift vom Architektur-Doc, das es hatte) → naive Account/Contact/Tenant-Löschung bricht mit Constraint-Error solange account_memory/meetings existieren. Bei der Kaskaden-Entscheidung crm-Tabellen explizit aufnehmen (CASCADE nachrüsten ODER Reihenfolge choreografieren). Detail: `Nerve-Vault/04 Entscheidungen/NERVE Architektur-Entscheidung Internes Datenmodell.md` §Nachträge-2026-06-01.
4. Restore-Re-Delete-Skript für Backups (WORM): liest user_deletion_request, re-deletet bei Restore. Gemini-Insight aus D.UX.1.
5. DSGVO-Doc Sektion 7.x aktualisieren.

**Cross-AI Pflicht** (🔴, DSGVO-Architektur + Daten-Verlust-Risiko). **Pre-Plan-Check Punkt 21:** Persistenz-Schicht-Inventur aller PII-Tabellen Pflicht.

**Depends on:** Phase 08.23.2.D.UX.1 ✅ (Audit-Log-Foundation)
**Komplexität:** 🔴 komplex — Lösch-Kaskade + Backup-Konformität + DSGVO
**Blocker für:** EA-Launch (START-BLOCKER — darf nicht im Backlog untergehen)
**Herkunft:** verschoben aus 08.19.6 Punkt 2 + Block D Löschkaskaden → eigene fokussierte Phase.
**Team-Verbindung (NEU 2026-05-30):** Lösch-Logik muss Org-Ownership beachten — User-Konto-Löschung entfernt den User, lässt aber Org-Calls + geteilte Skripte stehen (Daten gehören der Org, nicht dem User — Andre-Entscheidung). Schon hier mitdenken, auch wenn Team-System (08.23.2.TEAM/SEATS) erst danach voll steht.
**Plans:** 0 plans

### Phase 08.23.2.LOGIN: Login-Härtung + Admin-Nutzerverwaltung (promotet aus Backlog 999.1 am 2026-05-30) 🟡 START-BLOCKER (Login-Audit-Teil) vor EA-Launch

**Goal:** (1) Login-Audit als Start-Blocker: sicherstellen dass echte User sich sauber einloggen. (2) Admin-Maske zum User-Anlegen als Side-Feature.

**Start-Pflicht — Login-Härtung (Pre-EA-Launch-Audit):**
- Verifizieren: Passwort-Login + OAuth Google/Microsoft funktionieren für echte User.
- Edge-Cases: falsches Passwort, nicht-bestätigte Email, OAuth-Erstanmeldung.
- Auslöser: Login-Bereich wirkt fehlerhaft; andre-test@nerve.local in D.UX.0 ohne Login-Weg angelegt → real nicht einloggbar.

**Side-Feature — Admin-Nutzerverwaltung (nach Kernfeatures, CLAUDE.md Kernfeatures-Priorität):**
- Backend-Maske User-Anlegen (Admin-only), "Passwort generieren"-Knopf, Willkommens-Mail mit Zugangsdaten, Auswahl regulärer vs. Test-Account (is_test_user).

**Reihenfolge:** Login-Audit = Blocker, sofort machbar. Admin-Maske = Side-Feature, darf warten bis Kernfeatures sauber.

**Cross-AI Pflicht** (🟡).
**Depends on:** keine harte
**Komplexität:** 🟡 (Admin-Maske + Mail + Login-Audit) — finalisieren in Spec/Discuss
**Blocker für:** EA-Launch (Login-Audit-Teil — START-BLOCKER)
**Plans:** 0 plans

### Phase 08.23.2.G/MEET: Foundation-Phase Conversational Memory + CRM-Lookup + Multi-Tenancy + Training-Schema (NEU 2026-05-27, Phase G + MEET fusioniert nach Cross-AI-Architektur-Entscheidung) 🔴 ✅ COMPLETE — Vor-Increment 2026-06-01 (3 Wellen live, head=0013, a5a2b60) + MEETING-MODAL-Increment 2026-06-03 (Plan 04 Backend head=0014 7a127c7 + Plan 05 Frontend fa9654d live, Firma=Pflichtfeld, Live-E2E-verifiziert)

**KRITISCHE Architektur-Phase. Cross-AI-Recherche 2026-05-27 abgeschlossen. Spec-Dokument:** `Nerve-Vault/04 Entscheidungen/NERVE Architektur-Entscheidung Internes Datenmodell.md` — **Pflicht-Pre-Read** für Plan-Phase.

**Goal:** Foundation-Schema das industriebestätigte Conversational-Memory-Pattern (Gong/Chorus/Salesloft/Apollo/Outreach) für NERVE etabliert. Phase G (Konten-Welt) wird vorgezogen weil account_memory Foundation des Pre-Call-Briefing-USP ist. Plus Meeting-Memory-Modal-Frontend integriert (Andre-Wunsch 27.05.). Plus DPO-Foundation für Phase E.

**Drei Day-1-Pflichten (sonst frisst's uns in Year 2):**
1. `workspace_id` auf JEDER Tabelle (auch existing users/profiles/calls/conversation_logs/call_events) — Multi-Tenancy-Retrofit ist Hölle wenn später
2. Strikte Schema-Trennung `crm.*` vs. `training.*` mit zwei DB-Rollen (nerve_app crm-only, nerve_anon_worker bridge)
3. `schema_version SMALLINT` auf jedem JSONB-Feld — JSONB-Migration-Hell-Prevention

**3-Wellen-Aufteilung:**
- **Wave 1 Multi-Tenancy-Retrofit:** workspace_id-Migration auf existing Tabellen, Postgres RLS aktivieren, neue DB-Rollen, GRANT-Audit.
- **Wave 2 CRM-Schema + Meeting-Modal:** 5 neue Tabellen (crm.accounts, crm.contacts, crm.calls-Erweiterung, crm.call_events append-only, crm.meetings, crm.account_memory mit MEDDPICC-JSONB + context_hooks, crm.user_preferences). Meeting-Modal-Frontend nach Outcome=Termin (4 Felder + auto-save-Checkbox). Pre-Call-Briefing-Pipeline um account_memory erweitern. CSV-Export-Endpoint.
- **Wave 3 Training-Schema + Anonymizer:** training.preference_pairs (TRL-kompatibel, prompt/chosen/rejected JSONB), Anonymizer-Worker als separater Cron mit nerve_anon_worker-Rolle.

**Anti-Patterns explizit verboten:**
- Pipeline-Stages / Deal-Values / Forecasts (Pipedrive-Territorium)
- FKs zwischen crm.* und training.*
- Token-Cache-Persistierung (Pseudonymisierungs-Falle)
- JSONB ohne schema_version
- Custom-Fields-Mechanismus für User
- Lead/Contact-Trennung
- Bidirektionaler CRM-Sync v1 (push-only reicht)
- Volle Event-Sourcing-Implementierung

**Cross-AI Pflicht** (🔴 Foundation + DSGVO + DPO-Tragweite).

**Depends on:** Phase 08.23.2.D ✅
**Komplexität:** 🔴 komplex — Schema-Migration + Multi-Tenancy-Retrofit + neues Frontend-Modal + DSGVO-relevante Architektur-Trennung
**Blocker für:** Phase 08.23.2.E (DPO-Sammler nutzt training.preference_pairs aus Wave 3), Phase 08.21 (Battlecard-Pattern nutzt account_memory aus Wave 2), EA-Launch (Wave 1+2 sollten vor EA-Launch fertig sein, Wave 3 kann während EA-Phase)

**Schema-Skizze:** vollständig in `04 Entscheidungen/NERVE Architektur-Entscheidung Internes Datenmodell.md` (Cross-AI-Output). Migrations-Pfad in 3 Phasen, 8-Wochen-Plan bis EA-Launch.

**UPDATE 2026-06-01 (Discuss-Phase abgeschlossen, CONTEXT D-01–D-20, Cross-AI Gemini 4×):** Scope-Präzisierung gegenüber obiger Skizze — Plan-Author MUSS das beachten: (1) Mandanten-Schild = `tenant_id` (UUID) → `tenant_orgs`, NICHT `workspace_id` (0 Code-Treffer). (2) Strangler statt Big-Bang: neue Tabellen in `crm` mit `tenant_id`; die ~32 Alttabellen behalten `org_id` (Integer) in `public` — KEIN Retrofit auf existing Tabellen jetzt. Wave 1 = `tenant_orgs` anlegen + Brücke zu `organisations.id` + `calls.tenant_id`-Backfill (NICHT Voll-Retrofit). `users`→UUID + `org_id`-Ablösung deferred (war Vault-Phase-F-Scope, F existiert nur in Vault-Roadmap). (3) RLS nur auf neuen Tabellen. (4) Verbindungs-Karten-Pflicht: kein Name/Tabelle ohne grep+Live-Server-Beweis. Gemini-Umsetzungs-Fallen für den Plan: Connection-Pooling-Reset (teardown_request), Owner-BYPASSRLS (FORCE RLS oder restricted role), WITH CHECK, tenant_id-Index, search_path auf der Rolle, ALTER DEFAULT PRIVILEGES, Dual-Write bei Neuanmeldung, Session-tenant-UUID-Enrichment, Anonymizer-State-Tracking ohne ID-Spiegelung über die crm/training-Mauer.

**Plans:** 5 plans (Wellen 1-3 done; +2 NEU: Meeting-Modal-Increment, Welle 1 backend / Welle 2 frontend)

Plans:
- [x] 08.23.2.G-MEET-01-PLAN.md — Wave 1: Multi-Tenancy-Unterbau (tenant_orgs + Dual-Write-Trigger + calls.tenant_id-Backfill + Residual-Verification-Runbook) ✅ 2026-06-01 — live auf Prod (migration head=0011, git_head ed8a137); tenant_orgs 1:1 seeded (2==2), trg_mk_tenant_org SECURITY INVOKER, backfill 0 Orphans, 6 Tests grün
- [x] 08.23.2.G-MEET-02-PLAN.md — Wave 2: crm-Schema + 4 Tabellen + RLS-Kit + Session-UUID-Enrichment + Pre-Call-Briefing + CSV-Export (Meeting-Modal-UX deferred zu /gsd-ui-phase) ✅ 2026-06-01 — live auf Prod (migration head=0012, nullif fail-closed RLS-Amendment); 8/8 real-PG-Tests grün (RLS-Isolation 4/4 + Briefing 4/4)
- [x] 08.23.2.G-MEET-03-PLAN.md — Wave 3: training.preference_pairs (EXTEND, created-not-populated → Phase E) + Anonymizer-Worker (Variante A) + worker-targeted crm-RLS-Policies (anon_worker_read/stamp) ✅ 2026-06-01 — live auf Prod (migration head=0013, git_head a5a2b60); 14/14 Tests grün + D-16-Worker-Runtime via Claudian SET-ROLE-Tor verifiziert (cross-tenant read + stamp-persist + column-bound + nerve_app no-leak)
- [x] 08.23.2.G-MEET-04-PLAN.md — 🔴 NEU-Increment Wave 1 (backend, eigenständig deploybar): crm.user_preferences (Migration 0014, FORCED RLS NULLIF-Policy, owner postgres) + POST /crm/meetings (tenant_id-Stamp + resolve-or-create accounts/contacts) + GET/POST /crm/preferences + real-PG RLS/DSGVO-default-off-Tests ✅ 2026-06-02 — live auf Prod (migration head=0014, git_head 7a127c7, André drove manual-direct-prod als postgres); crm.user_preferences FORCED RLS + NULLIF tenant_isolation + nerve_app=arwd (KEIN GRANT/OWNER), MM-05 crm.accounts UNIQUE(tenant_id,name), POST /crm/meetings (MM-01 tz-aware reject-naive-400, resolve-or-create MM-05 ON CONFLICT, MM-04 sanitized logging) + GET/POST /crm/preferences (auto_save_meeting DSGVO-default-off, keyed g.user.id MM-07); 7/7 real-PG Tests grün; STEP-0-Gate PASS (head 0013→0014). gsd-code-review GESKIPPT (Multi-Segment-Gotcha)
- [x] 08.23.2.G-MEET-05-PLAN.md — 🔴 NEU-Increment Wave 2 (frontend, konsumiert Plan-04-Route): PiP 'Termin festhalten'-Form (pipEl, post-call host, datetime-local) + DSGVO-Checkbox UNCHECKED-by-default (Art. 25 Abs. 2) + Art. 6 Abs. 1 f Privacy-Note verbatim (build-blocking) + Bestätigungs-View + .n-meeting-* Light-Mode-Teal-CSS ✅ 2026-06-03 — live auf Prod (code-only, KEINE Migration, head bleibt 0014, git_head fa9654d). renderMeetingForm mountet in #meeting-form-mount NACH Score-Screen (MM-03), _toIsoWithOffset offset-ISO (MM-01), saveBtn-disable (MM-05), ehrliche Hint-Copy (MM-02), :root --meeting-check-color (MM-06b). **Firma=PFLICHTFELD (André-Direktive 2026-06-02):** Frontend required+Marker+block-empty+input-erhalt, Backend save_meeting 400 'Firma ist Pflicht' (redeployed) — kein Orphan. 4 DSGVO-Render-Tests + 7 RLS-Tests grün, Live-E2E Test-User bestanden. gsd-code-review GESKIPPT (Multi-Segment-Gotcha). MM-02-Honor-Logik deferred → Backlog 999.3

### Phase 08.23.2.TEAM: Team-Grundgerüst — Firmen-Konten, Rollen, Einladungen, Org-Ownership (NEU 2026-05-30, Andre-Strategie + Cross-AI Gemini) 🔴 PRE-LAUNCH-PFLICHT (Verkaufs-Enabler)

**Goal:** Verkaufbares Team-System-Grundgerüst (ohne Abrechnung). Im B2B-Vertrieb kaum Einzelkämpfer → Käufer ist die Firma, ein Kunde = ein ganzes Team = Multiplikator. Ohne Team-Verwaltung stirbt das Verkaufsgespräch ("Sie müssten jeden einzeln anmelden").

**Tasks:**
1. Rollen: Manager / Mitarbeiter.
2. Einladungs-Flow: Manager lädt Team ein — Status pending/accepted/expired (Token), Einladungs-Link mündet in den bestehenden Auth-Flow.
3. Team-Liste für Manager (Mitglieder + X/Y Plätze belegt — einfache Liste, KEINE tiefen Aktivitäts-Analytics, die kommen nach EA-Feedback).
4. **Org-Ownership (Andre-Entscheidung 2026-05-30):** Call-Logs, Skripte + Opener gehören der ORG, nicht dem User. Datenmodell `owner = Org`, nicht `owner = User`.
5. Seat-Enforcement-Vorbereitung (Logik die blockt wenn active_users > paid_seats — scharf in SEATS).

**Verbindung ART17:** Hard-Delete muss Org-Ownership beachten — User-Konto-Löschung entfernt den User, lässt aber Org-Calls + geteilte Skripte stehen.

**Cross-AI Pflicht** (🔴). Gemini-Konsultation 2026-05-30: Reihenfolge korrigiert (Datenmodell VOR Billing), Ownership-Konflikt aufgedeckt.

**Depends on:** Phase 08.23.2.G/MEET (workspace_id/Org-Struktur + DB-Rollen-Trennung)
**Komplexität:** 🔴 komplex — Rollen + Invite-Lifecycle + Org-Ownership-Retrofit auf profile_opener/profile_skripte/calls
**Blocker für:** Phase 08.23.2.SEATS (Billing braucht Team-Tabellen), EA-Launch (Verkaufs-Enabler)
**Reihenfolge:** nach G/MEET, VOR den Preis-Phasen 08.15/08.16 (ohne Team-Tabellen kein Per-Seat-Billing baubar — sonst 08.15 zweimal).
**Plans:** 0 plans

**ERWEITERUNG 2026-06-02 (Andre — Rollen-Ausbau + Coach + Profil-Sharing):**
- Rollen jetzt 3-stufig: **Leiter (Manager) > Coach > Mitarbeiter.** Coach UNTER Leiter (nicht gleichgestellt) — Coach hat KEINE Rechte auf Zahlungsdaten/Pläne/Abrechnung (bleibt beim Leiter).
- Profil-Einsicht: Coach UND Leiter dürfen Mitarbeiter-Profile EINSEHEN (gemeinsame Verbesserung). Ändern-Rechte + volle Permission-Matrix in Discuss festlegen.
- Profil-Sharing: Share-Button für ganze Profile UND einzelne Profil-Teilbereiche (Peer-Hilfe). ⚠️ Überschneidung mit SEATS Task 4 (Opener/Skript-Sharing) → Sharing-Mechanik an EINER Stelle (Vorschlag: Grund-Mechanik in TEAM, Nutzung in SEATS/COACH). In Discuss zusammenführen.
- OFFEN (Discuss): Coach intern (Org-Mitarbeiter) vs. extern (Coaching-Dienst über mehrere Tenants)? Ändert Zugriffs-/Tenant-Modell → vor Datenmodell klären.
- **Bau-Workflow TEAM + COACH:** beide Phasen erst KOMPLETT planen → Pläne gegeneinander abgleichen (Schnittstellen, v.a. Datenmodell „Aktivität pro Person unter Org-Ownership") → DANN sequenziell bauen.
- **Coach-Plan = eigener günstiger Tarif, bewusst beschnitten (Andre 2026-06-02):** Coach-Zugang deutlich günstiger, ABER (a) KEINE Cold-Call/Meeting-Ausführung mit dem Coach-Account (separat als Add-on dazubuchbar); (b) KEIN Team-Einladen/-Verwalten. Zweck: verhindern dass jeder den billigen Coach-Plan kauft und faktisch alle Features hat. → 08.15/08.16 müssen Coach-Tarif + Call/Meeting-Add-on abbilden; SEATS regelt die Abrechnung.

### Phase 08.23.2.MEETSTEP: Termin-Formular als eigener Post-Call-Schritt (vor dem Score) (NEU 2026-06-03, aus G/MEET-Live-Test) 🟡 — ✅ COMPLETE 2026-06-03 (live auf Prod, 7/7 UAT bestätigt, head 021d21c)

**Problem:** Termin-Formular sitzt aktuell UNTER dem Score + unter den "Nächster Call / Auswertung"-Buttons → User überspringt den Termin aus Versehen (klickt "Nächster Call"). Untergräbt den Feature-Nutzen.
**Soll (Andre-Reihenfolge 03.06.):** Anruf endet → Ergebnis-Auswahl ("Termin gebucht") → **Termin-Formular (eigener PiP-Schritt)** → Score-Karte → Auswertung/Nächster Call. Formular kommt VOR den Score.
**Begründung:** Nicht jeder Vertriebler schaut auf den Score — die Termin-Erfassung ist die wichtige Geschäfts-Aktion, darf nicht hinter dem Score begraben/überspringbar sein.
**Umbau am Post-Call-Flow (D.UX.4-Nachbarschaft).** Cross-AI Pflicht (🟡, Control-Flow Punkt 14: Schritt-Reihenfolge + Edge-Case Nicht-Meeting-Outcome = kein Formular → direkt Score). Pre-Insert-Control-Flow-Audit auf pip-launcher.js _renderOutcomeUx/Postcall-Sequenz.
**Koordination mit MODES:** beide fassen den Post-Call-/Meeting-Flow an → nicht doppelt umbauen; MEETSTEP (klein, sofort, fixt Live-Skippability) zuerst.
**Depends on:** G/MEET Meeting-Modal (live). ID ohne Schrägstrich (kein Multi-Segment-Gotcha).
**Plans:** 1 plan
- [x] 08.23.2.MEETSTEP-01-formular-vor-score-reorder-PLAN.md — Termin-Formular als eigener Schritt VOR dem Score: _revealScoreAndActions-Helper extrahieren, correct_outcome.then() bei meeting_booked verzweigen, Skip/Weiter/Zurück-Pfade verdrahten (D-03/D-04 Re-Entry) ✅ 2026-06-03 (Commits c448a6a/1382c36, SUMMARY)

### Phase 08.23.2.NACHTRAG: Ergebnis-Korrektur + Termin nachtragen (Scoreboard-Zurück + Auswertungs-Reiter) (NEU 2026-06-03, aus MEETSTEP-Live-Test) 🟡

**Problem (Andre-Logik-Bruch):** Übersprungener/verpasster Termin kann nirgends nachgetragen werden (Formular nur direkt nach dem Call). Wenn das Dashboard Skippern "schau nochmal rein" sagt, MUSS es hinten eine Nachtrag-Option geben.
**Andre-Design 03.06.:**
- (1) Knopf im Scoreboard (PiP) → komplett zurück zur Ergebnis-Auswahl (nutzt MEETSTEP-Re-Render; bei "Termin gebucht" öffnet Formular zum Nachtragen).
- (2) Reiter in der großen Auswertung (session_detail.html) → Ergebnis korrigieren + Termin nachtragen.
- (3) Wenn vorher Nicht-Formular-Ergebnis gewählt (oder PiP geschlossen) → spätestens in der Auswertung Formular nachtrag-öffenbar.
**OFFEN (Discuss):** nachträgliche Korrektur in der Auswertung — Score neu werten ODER Disclaimer "Score bleibt unberührt"? (Claudian-Lean: neu werten = Single Source of Truth.)
**Konsistenz-Regel:** Dashboard-Erinnerung ("schau nochmal rein") erst bauen WENN Nachtrag existiert — Reminder + Nachtrag zusammen, sonst broken promise.
**Depends on:** MEETSTEP (Re-Render + Formular), G/MEET (crm.meetings), session_detail. **Koordination:** MODES (Meeting-Modus) + D.UX.4-Dashboard-Outcome-Korrektur (nicht doppelt). Cross-AI Pflicht (Control-Flow + Score-Logik).
**Plans:** 0 plans

### Phase 08.23.2.MODES: Live-Assistent aufteilen — eigener Cold-Call- + Meeting-Modus (NEU 2026-06-02, Andre-Insight) 🟡 Kernfeature

**Problem:** Cold Call + Meeting beide hinter EINEM Live-Assistent-Button → gleicher Ablauf, obwohl grundverschiedene Einstiege (Cold Call = bei null; Meeting = Kontext existiert schon).
**Insight:** In Sidebar splitten → eigene Buttons + eigene Modal-Wege pro Modus.
**Kern-Nutzen:** Meeting-Modus listet gebuchte Termine (liest crm.meetings) → User startet konkretes Meeting → Vorab-Briefing lädt automatisch aus gespeichertem Termin + account_memory (precall_service.merge_account_memory). Beantwortet "woher weiß NERVE welches Briefing?": man startet vom gespeicherten Termin, statt Firma neu einzutippen. Schließt die Termin→Briefing-Schleife (die der Meeting-Modal-Bestätigungstext G/MEET bereits verspricht — bewusst nicht gekürzt, weil DIESE Phase es nachreicht).
**Depends on:** G/MEET (crm.meetings + account_memory-Briefing, live).
**Cross-AI Pflicht** (UX + Daten-Flow). **Reihenfolge:** Kernfeature (Live-Assistent) → vor COACH; Einordnung vs Auto-Save-Mini (999.3) + 08.21 in Discuss.
**Plans:** 0 plans

### Phase 08.23.2.COACH: Teamleiter-/Coach-Coaching-Sicht (Team-Leistungs-Dashboard) (NEU 2026-06-02, Andre-Idee) 🟡 Nebenfeature, nach TEAM

**Goal:** Teamleiter (+ Coach) sieht schwarz auf weiß wo das Team steht (Cold Calls/Meetings/Trainings pro Person, wer struggelt bei welchen Einwänden/Vorwänden) → gezieltes Nachschulen statt ungenaues Selbst-Berichten im Team-Meeting.

**PFLICHT-Recherche ZUERST (vor Design):** Was darf ein Chef in DE über Mitarbeiter sehen? Leistungs-/Verhaltenskontrolle, Betriebsrat-Mitbestimmung (§ 87 BetrVG), Beschäftigten-Datenschutz (DSGVO Art. 88). Auslegungssache — wie weit im Erlaubten?

**Design-Leitplanken (Andre 2026-06-02):**
- evtl. nur VAGE Hinweise ("hat noch Schwierigkeiten bei Einwand X") statt nackter Zahlen — Recherche entscheidet wie weit.
- Report-Schwelle: ab Leistungs-Level X% bei allen Metriken kein Report mehr (Mitarbeiter läuft allein) = Data-Minimization, nur Hilfsbedürftige zeigen.

**Depends on:** Phase 08.23.2.TEAM (Rollen + Org-Ownership + Aktivitätsdaten pro Person).
**Cross-AI Pflicht** (Beschäftigten-Datenschutz).
**Reihenfolge:** Plan zusammen mit TEAM (abgleichen), Bau direkt nach TEAM.
**Plans:** 0 plans

### Phase 08.23.2.SEATS: Team-Abrechnung pro Platz + Opener/Skript-Sharing (NEU 2026-05-30, Andre-Strategie + Cross-AI Gemini) 🔴 PRE-LAUNCH-PFLICHT

**Goal:** Per-Seat-Billing + Team-Sharing oben auf das Team-Grundgerüst.

**Tasks:**
1. Per-Seat-Billing via Stripe (Seat-Anzahl als quantity).
2. Proration von Anfang an (Seat mitten im Monat dazu → Stripe rechnet anteilig). Gemini: B2B-Manager prüfen Rechnungen pingelig; Stripe macht das fast automatisch wenn man quantity sauber hoch/runtersetzt statt neue Subscriptions anzulegen.
3. Seat-Enforcement scharf (blockt wenn active_users > paid_seats).
4. **Opener + Skripte im Team teilen** ("ganzes Team" / "Auswahl") — sitzt auf profile_opener + profile_skripte + Org-Ownership.
5. "Team verwalten"-UI für den Manager.

**Stripe-Fallstricke (Gemini, für Plan-Phase):**
- Webhook-Race: bei schnellem Mehrfach-Add IMMER absolute quantity aus dem Stripe-Payload nehmen, nie Delta addieren/subtrahieren (sonst DB-Desync).
- Failed Invoice bei Seat-Erhöhung: Seat erst in DB freigeben wenn Stripe `invoice.paid` fürs Update meldet, nicht schon beim Erhöhen.

**Cross-AI Pflicht** (🔴, Billing-Korrektheit).
**Depends on:** Phase 08.23.2.TEAM (Grundgerüst) + 08.15/08.16 (Preis-/Stripe-Fundament)
**Komplexität:** 🔴 komplex — Billing-Korrektheit + Stripe-Quantity-Sync + Sharing
**Blocker für:** EA-Launch (Verkaufs-Enabler — ohne Per-Seat kein Team-Verkauf)
**Reihenfolge:** nach 08.15/08.16.
**Coach-Seat (NEU 2026-06-02):** eigener günstiger Seat-Typ OHNE Cold-Call/Meeting-Ausführung (separat als Add-on dazubuchbar) und OHNE Team-Einladen/-Verwalten — Plan-Segmentierung gegen Missbrauch des billigen Coach-Plans. Stripe führt Coach-Seat + Call/Meeting-Add-on als getrennte Posten.
**Plans:** 0 plans

### Phase 08.23.2.E: DPO-Paar-Sammler + DSFA-Dokument (NEU 2026-05-11, **erweitert 2026-05-27**) 🟡

**Goal:** Sammelt strukturiert "chosen/rejected"-Paare aus jedem Anruf für späteres Fine-Tuning. NOCH KEIN Training. Plus DSFA-Dokument für BayLDA.

**Erweitert 2026-05-27 nach Cross-AI-Architektur-Entscheidung:** training-Schema-Foundation (`training.preference_pairs`-Tabelle + Anonymizer-Worker) kommt jetzt aus Phase 08.23.2.G/MEET Wave 3, NICHT in dieser Phase neu gebaut. Phase E nutzt die existing Foundation und schreibt nur die Sammler-Logik (Pair-Klassifikator: Cosinus+Jaccard, Quality-Tier-Vergabe, Hintergrund-Job nach Call-Ende) plus DSFA-Dokument.

**⚠ HOLISTIC-REVIEW-CONSTRAINT (Gemini 01.06., HIGH/DSGVO) — VOR Worker-Aktivierung fixen:** `scripts/anonymizer_worker.py` `_hash_call_id()` nutzt nacktes `SHA-256(call_id)` → reversibel für jeden mit `public.calls`-Lesezugriff (alle call_ids hashen + joinen) = nur Pseudonymisierung, bricht die "echte Anonymisierung"-Behauptung. **Fix:** `HMAC-SHA256(call_id, ANON_WORKER_PEPPER)`, Pepper nur in Worker-`.env`, nie in DB. Im DSFA adressieren. Detail: `Nerve-Vault/04 Entscheidungen/NERVE Architektur-Entscheidung Internes Datenmodell.md` §Nachträge-2026-06-01 + `05 Log` Anker.

**Depends on:** Phase 08.23.2.G/MEET Wave 3 (training-Schema-Foundation)
**Komplexität:** 🟡 (kleiner als ursprünglich geplant, weil Schema-Foundation schon in G/MEET)
**Blocker für:** Fine-Tuning-Iterationen (langfristig)

---

### Phase 08.23.2.SCHILD: Tabellen-Dokumentations-Pflicht — "Schild an jeder Tabelle" (NEU 2026-06-10, aus TAXO-Gerüst §0.2) 🔴 ✅ COMPLETE 2026-06-10 (alle 6 Wellen, Migration 0015 live auf Prod, Guard RED→GREEN belegt)

**Goal:** Jede DB-Tabelle (~44, Schemas public/crm/training) + jede nicht-triviale Spalte bekommt ein selbst-erklärendes "Schild" (Postgres-`COMMENT`): Zweck (Business-Logik), Status (lebt/Reserve/Zombie), wer liest/schreibt (Code-Pfade). Schild lebt im Code (`models.py` `comment=`) → Alembic-Migration schiebt es in die DB. pytest-Guard blockt künftig den Deploy, wenn eine Tabelle/Spalte kein Schild hat. `inspect.sh schilder` zeigt Schild + Migrations-Historie. Regel §0.2 in `salesnerve/CLAUDE.md` verankert. **Doku-Grundlage VOR dem TAXO-Bau** — macht spätere Zombie-Renames + Tabellen-Konsolidierungen sicher ("kein Raten mehr ob tot oder lebendig").

**Scope (7 Punkte, Detail in CONTEXT.md):** (1) `comment=` für jede Tabelle + nicht-triviale Spalte in `database/models.py` (Trivial-Konvention: id/created_at/updated_at/erstellt_am/aktualisiert_am/*_id/is_*/aktiv/UUID-PK ausgenommen); (2) Alembic-Migration (autogenerate; `training.transcript_archive` hat KEIN ORM-Model → COMMENT direkt in Migration/DDL); (3) pytest-Guard über `pg_description` auf ALLEN Schemas (Test-Connection braucht search_path + USAGE auf crm+training; KEIN FK-im-Text-Abgleich; failt bei fehlendem/<10-Zeichen-Schild); (4) `inspect.sh schilder`-Befehl; (5) §0.2 in `salesnerve/CLAUDE.md`; (6) Roadmap-Sync beide Roadmaps (erledigt); (7) Cross-AI vor Execute.

**PFLICHT:** §G-Schild-Entwürfe (Aufräum-Inventur) sind KANDIDATEN — jeden Status vor Festschreibung selbst greppen (Punkt 20/22). Bekannte Korrekturen: `AccountMemory` LEBT (precall_service.py:175), `coaching_reports` LEBT (Cache, dashboard.py:599). NICHT löschen: write-only/Zombie-Funde (sessions, feedback_events, price_change_log, learning_events) nur als [ZOMBIE]/Status markieren. Foundation-Tabellen (crm.account_memory, training.preference_pairs, training.transcript_archive, tenant_orgs) ins Foundation-Code-Register.

**Quell-Docs:** `Nerve-Vault/04 Entscheidungen/NERVE TAXO-Gerüst (verriegelt).md` §0.2 · `Nerve-Vault/03 Planung/TAXO Aufräum-Inventur (Verständnis + Scoring).md` §G.
**Depends on:** — (eigenständige Doku-Phase; KEIN Code-Verhalten geändert)
**Blocker für:** TAXO-Bau (Zombie-Rename + Single-Source-Konsolidierung + intent_event + Scoring-Rubrik + Drei-Bahnen)
**Komplexität:** 🔴 — Schema-Migration DB-weit + neue Test-Infrastruktur. Cross-AI **Pflicht** vor Execute.
**Plans:** 6 plans (6 Wellen — models.py-Edits serialisieren da EINE Datei; Guard wird VOR der Migration gebaut/ROT beobachtet, Migration flippt ihn GRUEN; inspect.sh+CLAUDE.md zuletzt)
- [x] 08.23.2.SCHILD-01-discovery-db-rolle-autogenerate-PLAN.md — Discovery: nerve_app liest pg_description aller 3 Schemas OHNE GRANT (SET-ROLE-Proof), MIGRATION_STYLE=op.execute, down_revision=0014 (Wave 1)
- [x] 08.23.2.SCHILD-02-schilder-cluster-call-infra-PLAN.md — comment= 30 Tabellen (Call-Analyse + Identitaet/Abrechnung/Infra), 3 Zombies grep-belegt, learning_events→lebt korrigiert (Wave 2)
- [x] 08.23.2.SCHILD-03-schilder-cluster-wissen-crm-training-PLAN.md — comment= 13 Tabellen (Wissen + crm + training-ORM), crm/training ins Schema-Dict gemerged; alle 43 ORM-Tabellen beschildert (Wave 3)
- [x] 08.23.2.SCHILD-05-guard-inspect-claudemd-PLAN.md — pytest-Schild-Guard + conftest-Fixture, server-seitig ROT beobachtet (44 Tab + 317 Spalten, transcript_archive gefangen) (Wave 4)
- [x] 08.23.2.SCHILD-04-migration-foundation-register-PLAN.md — Migration 0015 op.execute COMMENTs (44 Tab + 333 Spalten inkl. transcript_archive) live auf Prod, Guard GRUEN; env.py include_schemas; Foundation-Register (Wave 5)
- [x] 08.23.2.SCHILD-06-inspect-claudemd-PLAN.md — inspect.sh schilder (FALL A nerve_app, public+crm bewiesen) + CLAUDE.md Punkt 23 + deploy.sh-Guard-Stufe (Wave 6)

> ⚠️ Multi-Segment-ID-Gotcha: Pfade hartkodieren auf `.planning/phases/08.23.2.SCHILD-tabellen-dokumentations-pflicht/`. Verify=Production (`deploy.sh production` + `inspect.sh schilder`), kein Local-Dev.

---

## Phase 08.23.2.PGTEST: Echtes Postgres-Test-Gate (NEU 2026-06-15) 🔴 — ⚠️ GATET TAXO1-DEPLOY, LÄUFT ZUERST

**Goal:** Das `deploy.sh`-Test-Gate (volle pytest-Suite) läuft gegen eine echte, wegwerfbare Postgres-DB statt SQLite-in-memory — ehrlich + stabil für ALLE künftigen Deploys. Damit ist der Production-Deploy von TAXO1-01 (intent_event-Migration) und allem danach wieder belastbar abgesichert.

**Anlass (Diagnose 2026-06-15, 3 Schichten, alle pre-existing, NICHT TAXO1):**
1. `deploy.sh:135` fährt pytest gegen SQLite-in-memory.
2. `tests/conftest.py` nutzt `sqlite:///:memory:` HARDCODED (ignoriert `TEST_DATABASE_URL` laut Code-Kommentar).
3. `app.py:1115` lässt NUR im SQLite-Pfad `alembic upgrade head` laufen; Migrationen 0008–0016 haben ~57 nur-Postgres-Befehle (CREATE SCHEMA, GRANT, RLS, OWNER) → SQLite-Syntaxfehler → harter raise.
4. Schicht-1-Fix `cf5de6d` (SQLite-ATTACH crm/training) ist nur ein Pflaster auf `create_all` (Cross-AI Gemini PASS = statisch korrekt, aber bestätigt: bleibt SQLite-Pflaster); die alembic-Kette bleibt SQLite-inkompatibel. **NICHT die 57 Befehle einzeln patchen (Hau-den-Maulwurf).**

**Scope-Richtung (Research/Plan offen, nicht vorgeschrieben):** (1) Wegwerf-Postgres-Test-DB provisionieren (eigene DB auf bestehender Server-Instanz ODER Container — Research: was auf dem Hetzner-Host am saubersten + schnellsten ist); (2) Schema via `alembic upgrade head` gegen diese echte Postgres-DB bauen (läuft jetzt); (3) `conftest.py` refactoren: `TEST_DATABASE_URL` honorieren statt hardcoded sqlite; (4) Isolation entscheiden: frische DB pro Lauf vs. Transaktions-Rollback pro Test; (5) `deploy.sh`: Test-DB provisionieren → pytest dagegen → teardown; (6) `app.py:1115` alembic-auf-SQLite-Hook + `cf5de6d`-ATTACH-Fix prüfen ob obsolet → ggf. entfernen (sonst toter Pfad); (7) Postgres-Produktion + Schild-Guard-Pfad (läuft schon gegen echtes Postgres) NICHT brechen.

**Sicherheits-Schranken (🔴-Begründung — Test-Infra + DB-Setup + RLS/Grants = security-nah):** Test-DB darf KEINE Produktionsdaten berühren + muss sauber teardownen. Pre-EA-Launch: Test gegen Production-Host, kein Local-Dev (CLAUDE.md HART).

**Depends on:** keine harte (steht eigenständig). **Blocker für:** TAXO1-Deploy-Fortsetzung + jeden künftigen `deploy.sh production`. **Execute VOR TAXO1-Bau-Fortsetzung.**
**Herkunft:** herausgelöst aus Slot 08.23.2.STAGING Task (1) („deploy.sh-Test-Gate fixen") — vorgezogen, weil es jeden Deploy blockiert. STAGING bleibt am Ende mit Rest-Tasks (2)-(5) (Auto-Alembic, deploy_meta, atomarer Promote, Drift-Audit).
**Komplexität:** 🔴 — Cross-AI **Pflicht** (André-Direktive Punkt 24: 3 Sichten). Voll Spec → Plan → Cross-AI → Execute.
**Plans:** 3 plans (2 waves) — GEPLANT 2026-06-15, plan-checker PASSED (2. Iteration: 2 Blocker + 2 Warnings in Rev-1 gefixt).
- [x] 08.23.2.PGTEST-01-conftest-fixtures-PLAN.md — conftest generische Fixtures auf nerve_test-PG + Tenant-Kontext (Modul-SessionLocal-Rebind, D-05) + 3 Spezial-Fixtures → nerve_test (Req-2/5/9) [Wave 1] ✅ EXECUTED 2026-06-16 (7 Commits e35e031→9a0f120, SUMMARY geschrieben; statisch verifiziert, Voll-Beleg im deploy.sh-Gate)
- [x] 08.23.2.PGTEST-02-deploy-gate-block-PLAN.md — deploy.sh Postgres-Gate: Whitelist-Guard D-02 + trap-Teardown + **pg_dump-Bau-Pfad** (schema-only + alembic_version-data + upgrade-head-nur-neue-Revs) + 4-DSN-pytest, fail-closed pro Schritt (Req-1/3/4/5/7/8/9) [Wave 1] ✅ EXECUTED 2026-06-16 (2 Commits 76536b1 Gate-Block + 3201265 Schild-Guard-Fold, SUMMARY geschrieben; `bash -n` PASS + alle Guards/key_links grep-verifiziert, 0 bare @/nerve-DSN; manueller SSH-Katalog-Build deferred an orchestrator-deploy.sh-Lauf per HARD_OVERRIDE — inline-Katalog-Gate ist der automatisierte fail-closed Guard; Voll-Beleg im EINEN integrierten deploy.sh-production-Lauf nach allen 4 Plans)
- [x] 08.23.2.PGTEST-03-remove-sqlite-port-klasse-a-PLAN.md — SQLite-Emulation entfernen (ATTACH-Listener + app.py-Hook) + Klasse-A-Tests + FK-/F1-/Gruppe-A-Ports (test_tenant_orgs Trigger-Semantik, test_08_14 ApiRate-scope, cost_tracker/ft_seed, Base-Seed-Konsumenten) (Req-4/6) [Wave 2] ✅ EXECUTED 2026-06-16 (10 Commits 17d1087→444b9da, SUMMARY geschrieben; statisch verifiziert — py_compile alle 12 Dateien, key_links present, kein Plan-04-File berührt; Voll-Beleg im EINEN integrierten deploy.sh-Gate). DEVIATION: anonymizer Logic-Group-Write läuft als nerve_anon_worker (nicht nerve_app — training-DPO-Wand) [Rule 3]; committende Tests bekamen id-Wasserzeichen-Teardown [Rule 2].
- [x] 08.23.2.PGTEST-04-persistenz-haertung-gruppe-a-b-PLAN.md — Persistenz-Härtung gegen app-geseedete persistente nerve_test (Option A): Gruppe-A-Rest (eur_calculator/ewb_pipeline/prompt_pipeline) + Gruppe-B-Teardown-Adoption via cleanup_rows-Helfer (Plan 01) + Baseline-Wächter-Konformität; Gruppe-C-Bugs eskaliert (Req-4/6/7) [Wave 2] ✅ EXECUTED 2026-06-16 (6 Commits 4b9296f→1833601, SUMMARY geschrieben; 13 Dateien py_compile-grün, files_modified-disjoint von Plan 03, stale 6/8-VALID_OUTCOMES-Assert untouched+eskaliert; statisch verifiziert, Voll-Beleg im EINEN deploy.sh-Gate nach allen 4 Plänen)

> **Plan-Count: 4 Plans (2 Waves).** Wave 1 = 01+02; Wave 2 = 03+04 (disjunkte files_modified, parallel-safe). Option-2-Transaktions-Isolation verworfen (Gemini+Claudian: RLS-after_begin-Hook db.py:92 löscht GUC nie → Savepoint-Leak = False-Green). Architektur = Option A (produktions-treues Real-Commit + Liste härten + Cleanup-Helfer + Baseline-Wächter à la SCHILD). Enumeration: `08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md`.

**⚑ BUILD-PATH empirisch BEWIESEN 2026-06-15 (supervised, André Punkt-22):** plan-checker fing einen echten Blocker — `create_all→stamp 0001→upgrade head` kollidiert bei 0002 (create_all baut volles Modell, add_column-Replay doppelt). Gewählter+bewiesener Pfad = `pg_dump --schema-only nerve` + `pg_dump --data-only alembic_version` + `alembic upgrade head` (nur neue Revs 0015→0016). Gegen Wegwerf-nerve_test serverseitig belegt: 7 crm-RLS-Policies + FORCE + GRANTs treu vom Dump getragen, echter Cross-Tenant-Test (11 passed), danach rückstandsfrei geteardownt. Req-3-Mechanismus-Abweichung André-autorisiert (End-Zustand erfüllt Acceptance). Details: RESEARCH.md „⚑ BUILD-PATH LOCKED".

**🔴 → Cross-AI PFLICHT vor Execute** (André Punkt 24). NÄCHSTER SCHRITT: `/gsd-review --phase 08.23.2.PGTEST --all`.

> ⚠️ Multi-Segment-ID-Gotcha (wie SCHILD/TAXO): Pfade hartkodieren auf `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/`, gsd-tools-ID-Auflösung umgehen, STATE/ROADMAP hand-editieren. Verify=Production (`deploy.sh production`), kein Local-Dev.

**🟥 PGTEST-AUSGANG 2026-06-16 (supervised execute, Claudian): Infrastruktur GELIEFERT, Gate bewusst KNOWN-RED → Rest in 08.23.2.PGTEST.GREEN eskaliert.**
Geliefert + gepusht: der PG-Gate-Block in `deploy.sh` (provision→pg_dump-Restore→Katalog-Treue-Gate crm-Policies≥7/FORCE≥5/GRANTs≥5 ✅→pytest→POST-SUITE→trap-Teardown), die conftest-PG-Fixtures, der Baseline-Wächter, SQLite-Entfernung. **Der EINE validierende `deploy.sh production`-Lauf lief 4× (alle prod-sicher rot, KEIN Restart — Prod unangetastet, `nerve` auf 0015).** Gate-Ergebnis: `51 failed, 595 passed, 555 errors` → ehrlich rot, NICHT maskiert (Req-7).
**2 ECHTE Bugs gefangen + gefixt (Claudian-verifizierbar):** (1) `6253676` — `_seed_test_tenant` committet org+tenant_org im `db_session`/`client`-Setup, Teardown raeumte nie auf → jede fixture-nutzende Testfunktion leakte; Fix = org_id zurueckgeben + `_leak_cleanup_seed_tenant` in beiden Teardowns. (2) `10e5d0a` — `cleanup_rows` `id = ANY(:ids)` warf `operator does not exist: uuid = text` bei uuid-PK-Tabellen (tenant_orgs/crm.*) → ganze Cleanup-Transaktion rollte zurueck; Fix = `id::text = ANY(:ids)`.
**Bewusst KNOWN-RED (eskaliert, NICHT gefixt):** die suite-weite Baseline-Konformitaet — nach den 2 Fixes leaken weiterhin **61 Test-Files über 11 public-Tabellen** (organisations/users/tenant_orgs/ewb_ratings/conversation_logs/revenue_log/api_cost_log/fixed_costs/prompt_versions/exchange_rates/profiles). Wurzel: Plan-01s globaler fail-closed Baseline-Wächter verlangt dass JEDER der ~600 Tests die GANZE public-Baseline pristine laesst — die ueber viele Phasen gegen Wegwerf-SQLite geschriebene Suite war nie so gebaut. Plus **51 Assertion-Fails** (~22 Plan-03/04-Port-Bugs, ~29 fremde/env-abhaengige reds wie real-Haiku/Perf). Das ist eine Architektur-/Scope-Entscheidung (Plan-01-Design), kein lokaler Fix → Option-3-Schnitt (André 2026-06-16).

### Phase 08.23.2.PGTEST.GREEN: Gate grün machen — Isolations-Strategie + Test-Triage (NEU 2026-06-16) 🔴 ✅ COMPLETE 2026-06-16 — Tor GRÜN (638/0/0, POST-SUITE crm+training=0), deployed, TAXO1-01 live. Triage: 0 echte Bugs / 0 kritische, alles veraltete Tests. Details [[05 Log]] + 08.23.2.PGTEST.GREEN-TRIAGE.md.

**Herkunft:** Eskaliert aus 08.23.2.PGTEST (Option-3-Schnitt, André 2026-06-16). PGTEST lieferte das ehrliche PG-Tor + Infrastruktur; dieses Tor ist KNOWN-RED. GREEN macht es grün. **NICHT bauen — erst voll spec'en (Discuss→Plan→Cross-AI, Gemini Pflicht, alle Teile False-Green-nah).**

**Scope — vier 🔴-Teile:**
- **(a) ISOLATIONS-STRATEGIE entscheiden (Kern, Plan-01-Design-Reversal-Kandidat):** den globalen fail-closed Baseline-Wächter ersetzen. Führender Kandidat: **Auto-Reset** — Extra-Rows (alles NICHT in der Session-Start-Baseline) nach jedem Test automatisch DELETEn statt fail-closed-block, nutzt die schon vorhandene Snapshot-Infrastruktur, greent die Leak-Dimension über alle 61 Files mit EINER Fixture-Änderung ohne ~60 Test-Files umzuschreiben; Req-7 bleibt via lauter Warnung (welcher Test leakte) + auto-clean, Gate blockt nur noch auf echten Assertion-Fails. Alternativen offen (per-Test-Delta-Snapshot etc.). **Gemini gegenlesen BEVOR umgesetzt — kehrt die Plan-01-„fail-closed"-Entscheidung um.**
- **(b) ~22 Port-Assertion-Fails triagieren** (Plan-03/04-Dateien: anonymizer_worker, postcall_split, postcall_outcome_route, eur_calculator, cost_tracker, ewb_pipeline, exchange_rates, dashboard_outcome_reminder): pro Test = echter App-Bug (eskalieren, Req-7) ODER veralteter Test (fixen, wie stale 6-vs-8). NICHT blind grün-machen.
- **(c) Tor-Umfang:** ~29 env-abhängige Tests (real-Haiku-Integration, p95/Perf-Latenz, Re-ID-Rate) per pytest-Marker (z.B. `live`/`perf`) aus dem Gate, Gate läuft `-m "not live and not perf"`, separater Lauf + dokumentieren warum (sonst False-Green-Risiko).
- **(d) Wächter-Tabellenlisten schema-abgeleitet statt hardcoded** (André-Fund 2026-06-16): `_BASELINE_PUBLIC_TABLES` + `_CLEANUP_FK_ORDER` sind heute handgepflegte Listen → neue Tabellen (intent_event, transcript_segments, künftige TAXO-Tabellen) werden NICHT auto-bewacht. Aus dem Schema ableiten. **MUSS vor TAXO-Deploy stehen.**

**Depends on:** 08.23.2.PGTEST (Infrastruktur + 2 Bug-Fixes) — DONE/KNOWN-RED.
**Blocker für:** TAXO1-Deploy (erbt die Gate-Rolle von PGTEST — ein grünes Tor ist die Voraussetzung für sicheren TAXO-Deploy).
**🔴 → voll Spec → Discuss → Plan → Cross-AI (Gemini Pflicht) → Execute.** Multi-Segment-ID-Gotcha gilt (Pfade hardcoden).

**Plans:** 5 Plans in 3 Wellen (geplant 2026-06-16; 🔴 Cross-AI/Gemini Pflicht VOR Execute)
- [x] 08.23.2.PGTEST.GREEN-01-introspect-autoreset-PLAN.md — Schema-Introspect-Modul + Auto-Reset gespaltener Baseline-Waechter (Wave 1, Req-2/3/9, D-G19-Kopplung) ✅ 2026-06-16 (statisch verifiziert, Gate-Verifikation auf deploy.sh production aufgeschoben)
- [x] 08.23.2.PGTEST.GREEN-02-deploy-crm-derivation-marker-wiring-PLAN.md — deploy.sh crm-Derivation + live/perf-Marker-Registrierung + Gate-Exklusion (Wave 1, Req-7/9/10) ✅ 2026-06-16 (statisch verifiziert, Gate-Verifikation auf deploy.sh production aufgeschoben)
- [x] 08.23.2.PGTEST.GREEN-03-triage-harness-PLAN.md — scripts/triage.sh (Gate-Provisioning 1:1, kein Restart, Ratchet) (Wave 2, Req-5) ✅ 2026-06-16 (statisch verifiziert, Server-Smoke-Test auf nächsten Server-Lauf aufgeschoben)
- [x] 08.23.2.PGTEST.GREEN-04-empirical-triage-PLAN.md — Triage (Claudian) + alle (i)-Fixes ANGEWENDET, 0 kritische/(iii), 0 echte App-Bugs (Wave 3, Req-5/6) ✅ 2026-06-16 (full-suite triage.sh -m "not live and not perf" = 638 passed/0 failed)
- [x] 08.23.2.PGTEST.GREEN-05-markers-security-mocks-final-deploy-PLAN.md — live/perf-Marker (5) + MARKERS.md + Anon-NER-Mock im Gate (Req-1/7/8/10) ✅ 2026-06-16 (Code grün bewiesen). ✅ FINALER deploy.sh production GRÜN + Restart 2026-06-16 (Claudian beaufsichtigt) — 638 passed/0/0, POST-SUITE crm+training=0. Prod alembic 0015→0016, TAXO1-01 (intent_event) live, /api/health ok. Unterwegs 2 weitere Gate-Lecks gefixt: crm uuid-Cast (`5d550c8`, test_account_memory_briefing) + training-DPO-Tresor test-only GRANT (`b6ecd81`, André-Option-1). LEHRE: triage.sh fährt den POST-SUITE-Leak-Check NICHT — echtes Grün = voller deploy.sh-Gate.

---

## TAXO-Bau — drei Teile (NEU 2026-06-10, aus `Nerve-Vault/04 Entscheidungen/NERVE TAXO-Gerüst (verriegelt).md`)

> **Workflow (Andre-Direktive 2026-06-10):** Alle drei Teile (TAXO1/2/3) ZUERST bis kurz vor Execute bringen — je Spec → Discuss → Plan → Cross-AI-Review. Dann alle drei Pläne + Reviews nebeneinanderlegen und auf sauberes Ineinandergreifen prüfen (gemeinsamer Klebstoff = das `intent_event`-Schema, Gerüst §3). ERST danach Execute, einer nach dem anderen: TAXO1 → TAXO2 → TAXO3. Anti-Abrieb: nicht Teil 1 fertigbauen und dann merken, dass Teil 2 ihn anders braucht.
> **Quell-Doc Pflicht-Pre-Read für jede Spec/Plan-Phase:** `Nerve-Vault/04 Entscheidungen/NERVE TAXO-Gerüst (verriegelt).md` (der verriegelte Bauplan, Single Source of Truth). Real-Daten/Schema-Pulls IMMER gegen Production (`inspect.sh`), kein Local-Dev. SCHILD-Guard bei Tabellen-Änderungen MANUELL laufen lassen (Auto-Blockade inert bis das Test-Gate echtes Postgres fährt — Tor-Fix = Phase **08.23.2.PGTEST**, vorgezogen vor TAXO1-Deploy; nicht mehr erst 08.23.2.STAGING).
> **Sicherheits-Verifikation pro Phase (André 2026-06-12):** Jede TAXO-Phase, die eine Tabelle anfasst, verifiziert für genau diese Tabellen den Daten-Schutz — User-Trennung (per-user/tenant-Isolation) + „sensible Daten nicht leicht erreichbar". Inline (OQ-1 = erster Fall, DPO-Wand). Die breite app-weite Userdaten-Sicherheits-Prüfung ist davon GETRENNT = eigene Pflicht-Phase vor Launch (SEC-USERDATA), nicht in TAXO reinquetschen (Scope/Abrieb).

### Phase 08.23.2.TAXO1: Verstehen — Fundament + Erkennung (NEU 2026-06-10) 🔴 — 🟢 TEILSTAND 2026-06-16: TAXO1-01 (intent_event-Tabelle, Migration 0016) LIVE auf Prod (Gate grün + entsperrt). OFFEN: Plan 02–07 (Live-Pfad-Anschluss). — **2026-06-17:** Welle 2+3 live+verifiziert; Welle 4 (Live-Cutover/K4) deployed, aber Live-Test deckte Kern-Defekt auf (`intent_event` bleibt leer — `analysiere` bekam Antwort-Prompt statt Struktur-Auftrag → Medium-Lane speichert nie; Kaufbereitschaft/Phase/Buttons brach). → **🔴 Fix-Phase `08.23.2.TAXO1.MEDFIX`** (analysiere-Struktur-Auftrag zurück + Modus-Fix + Integration-Test der Live-Schreiben beweist; Gemini PFLICHT vor Execute). Welle 4 NICHT fertig bis MEDFIX live+grün; Welle 5 erst danach. Diagnose: `.planning/debug/taxo1-04-intent-event-empty-medium-lane.md`.

**Goal:** Das Fundament UND das Herz "was sagt der Kunde gerade". Eine neue zentrale Ereignis-Tabelle `intent_event` als Single Source of Truth (startet leer, KEINE Migration der Test-Schrott-Logs), das Drei-Bahnen-Gerüst als Klempnerei, und die Einsortier-Logik (Taxonomie + Modi) darauf umgestellt.

**SPEC verriegelt 2026-06-10 (e2aa93e, 9 Requirements, Ambiguity 0.14):** Zombie-Umfang ENG — NUR `ewb_ratings` hart zombifiziert (0 Zeilen); `objection_events` bleibt per **Dual-Write-Brücke** am Leben (Dashboard-Einwand-Zähler bricht nicht), echte Zombifizierung = TAXO2; die 4 großen Tabellen (`conversation_logs`/`calls`/`call_events`/`transcript_segments`) UNANGETASTET (Konsolidierung = TAXO2/spätere Phase). Dual-Write-Compat-Shim-Mechanik = offene WIE-Frage für Discuss/Plan.

**Scope (Gerüst §0.1 / §1-3 / §5):** (1) `intent_event` hybrides Schema (indizierte Spalten: event_id/session_id/call_id/mode/timestamp/intent_type/phase/handling_score_numeric/confidence + JSONB payload; alle 4+3 Pflichtfelder ab Tag 1 — Gerüst §3); (2) Zombie-Rename ENG (Spec-Lock): NUR `ewb_ratings` hart zombifiziert (`zombie_`-Prefix + [ZOMBIE]-Schild, NICHT droppen); `objection_events` per Dual-Write-Brücke am Leben (Dashboard-Zähler), echte Zombifizierung TAXO2; `conversation_logs`/`calls`/`call_events`/`transcript_segments` UNANGETASTET (Konsolidierung TAXO2/später); (3) Drei-Bahnen-Gerüst (Fast/Medium/Slow Lane) — Slow-Lane = `queue.Queue` + Daemon-Consumer, Interface gekapselt (Adapter → Redis-Zukunft), Graceful-Shutdown-Flush in DB (Bau-Regel 2); intent_event read-only für Live-Bahnen, Slow Lane arbeitet auf Kopie + separates Score-Objekt (Bau-Regel 1); (4) Taxonomie §1 (Intent-Schubladen inkl. Gemini-Ergänzungen + custom_objection_*) + Modi §2 (Audibility-Contract als deklarative Routing-Tabelle, Modus-Registry/Strategy-Pattern, Single-Speaker-Echo-Regeln + Konfidenz-Deckel) auf intent_event umstellen; (5) Single-Source-Putzliste falten (§0.1): `user_id` (claude_service.py:452 global→per-SID, Prod 164× Warn), `current_phase` (:1012 write / :1085 read), `cold_call_inference` (:1071/:1086), `kw_fired_for_line` (REVERSE matcher:253/claude:1265) + Cross-Session-Globale (score_factors_seen/last_einwand_typ/kaufbereitschaft/readiness_*) auf EINE per-SID-Quelle, alte globale Pfade LÖSCHEN; (6) ewb-Varianten-Frage auflösen (user_id-Fix bestimmt v1-legacy vs v2-modular; ENV `PROMPT_EWB_VERSION_OVERRIDE` als Notschalter). org_id (K8) wandert als Teil dieser Konsolidierung mit (COST-ATTRIB).

**★ COST-ATTRIB Vollständigkeit + Abhängigkeits-Kette (Andre 2026-06-12, Interlock-Befund):** Die Kosten-Zuordnung (Punkt 5/6) muss **ALLE** `log_api_cost`-Aufrufe abdecken — Code-Stand ~14 mit `user_id=None` (claude_service.py:315/320/323/391/396/399/489/492/499/503/626/629/636/640), TAXO1-03-Plan nennt explizit nur 489/492/499/503 → beim Planen/Re-Grep prüfen dass **alle** erfasst sind (user_id + org_id + session_id durchgereicht), sonst bleibt ein Teil der API-Kosten ohne User. **Diese vollständige Pro-User-Verbuchung ist Foundation für die Überschuss-Abrechnung (kein neues Phasen-Stück nötig — schon geplant):** `api_cost_log` (user_id/org_id/units/unit_type/session_id/cost_eur existieren ✓) → **Phase 08.15** (Plan-Tabelle `audio_min_cap` + `overage_price_eur_per_min` + monatl. Minuten-Zähler aus api_cost_log) → **Phase 08.16** (Stripe Usage-Based-Billing 0,05 €/extra Min). Andre-Anforderung: pro-User-Sicht (X Anrufe/Y € pro Monat) für Pricing + faire Team-Überschuss-Abrechnung (Free-Minuten/Plan, dann zahlt der User; Abrechnung über Head of Sales via org_id) → kein Minus-Geschäft bei Power-Teams. Klein/später: ggf. Token-Überschuss zusätzlich zu Audio-Minuten (unit_type trägt beides).

**Depends on:** 08.23.2.SCHILD (Boden dokumentiert) — DONE.
**Blocker für:** TAXO2 + TAXO3 (beide referenzieren das `intent_event`-Schema). **Execute zuerst.**
**Komplexität:** 🔴 — Schema-weite Migration + Live-Pfad-Umbau + Single-Source-Konsolidierung. Cross-AI **Pflicht**. Real-Daten-Validation (Punkt 13) + Persistenz-Schicht-Audit (Punkt 21) + Pflicht-grep (Punkt 20) Pflicht.
**Plans:** TBD (Plan-Phase)

### Phase 08.23.2.TAXO2: Bewerten — EINE Noten-Engine (NEU 2026-06-10) 🔴

**Goal:** EINE rubrik-basierte Noten-Engine (BARS) ersetzt die ZWEI driftenden Alt-Systeme (Live-Formel `app_routes.py:735` + Training-7-Kategorien `training_service.py:1122`). Tötet den Redeanteil-0%-Bug an der Wurzel.

**Scope (Gerüst §4 / §5 Slow Lane):** (1) EINE `rubric_score`-Tabelle, Live + Training schreiben rein (Single Source, ersetzt beide Alt-Systeme); (2) Dimensionen aus der Taxonomie abgeleitet (Vorwand-Behandlung, Kaufsignal-Nutzung, Aufschub-Behandlung, Phasen-Technik-Passung, Fragen-Qualität, Gesprächsführung, Outcome-Progression) als DB-Daten mit je 3 BARS-Stufen; (3) **Proration statt Null-Strafe** — nicht-messbare Dimension (Redeanteil im Single-Speaker) → available=false → Restgewichte renormalisieren auf 100%; <50% verfügbar → kein Gesamtscore, nur Teil-Dimensionen (tötet K2 `frage_qualitaet=0.0` + Block-J-Redeanteil); (4) Speech-Stats-Fix K1 (live_session.py:867 globale Zähler tot → per-SID-Quelle live_session.py:684-693) speist Note + ambienten Tempo-Regler; (5) `handling_score` 1-3 v1 regel-/marker-basiert + großzügige Abstention, LLM-Verhaltens-Urteil NUR async auf Slow Lane (Gemini-Fix gegen Zirkelschluss + unfaire Noten); (6) Vertrauens-Regeln (Kluger&DeNisi 1996): Breakdown + Transkript-Beleg statt nackter Zahl, "nicht gewertet"-Hinweis sichtbar, Low-Confidence als "vorläufig", ein erreichbares Ziel pro Call. Training-Ground-Truth (gespielter vs. erkannter Intent) als objektiver Anker.

**Erbt aus TAXO1 (Spec-Lock 2026-06-10):** echte Zombifizierung von `objection_events` (Dual-Write-Brücke ablösen, Dashboard-Einwand-Zähler auf intent_event/rubric_score umziehen) + Konsolidierung des `conversation_logs`-Aggregats (Note/Bewertung).
**Depends on:** 08.23.2.TAXO1 (`intent_event`-Schema + Slow Lane).
**Komplexität:** 🔴 — Schema + Scoring-Logik (ersetzt 2 Systeme). Cross-AI **Pflicht**. Real-Daten-Validation Pflicht.
**★ PFLICHT-PULL aus backlog.md bei TAXO2-Planung (Live-Test 2026-06-18):** `PHASE-CLOSE-DETECT` (Phasen-Takt: classify_phase nur jede 5. Runde → bestätigter Termin am Call-Ende verpasst Phase 6 → event-getriebener Takt bei zustimmung/naechster_schritt + per-SID-Takt-Zähler) + Redeanteil-100%-Cold-Call-Artefakt (Tipp im Single-Speaker unterdrücken, gehört zu K2/Proration §3).
**Plans:** 7 Plans / 6 De-Risk-Wellen (GEPLANT 2026-06-11, Wellen-Schnitt):
- [ ] 08.23.2.TAXO2-01-rubric-score-tabelle-PLAN.md — neue rubric_score-Tabelle (hybrid, Owner nerve_app, RLS FORCE, Schild, Training-Fit-Pass) [W1, Req 1/5/8/D-08/D-11]
- [ ] 08.23.2.TAXO2-02-bars-engine-proration-PLAN.md — BARS-Engine + Proration + Modus-Gewichte + 2 D-02-Pflicht-Tests (reine Funktion) [W2, Req 2/3/5/9/D-01..05/D-08]
- [ ] 08.23.2.TAXO2-03-handling-score-slow-lane-PLAN.md — handling_score 1-3 in-place (Slow Lane), Race-Gate, Goodhart-Logging [W2, Req 4/D-03/D-07]
- [ ] 08.23.2.TAXO2-04-coaching-score-cutover-async-PLAN.md — Live-Cutover: Engine→calls.coaching_score (EIN Schreiber, async D-10), alte Formel weg, Audio-Gate D-09, NULL-Edge 3 Screens [W3, Req 2/5/6/9/D-09/D-10]
- [ ] 08.23.2.TAXO2-05-objection-zombify-admin-ewb-PLAN.md — 4 objection_events-Leser→intent_event, Brücke weg, [ZOMBIE]-Schild + admin_ewb ersatzlos raus [W4, Req 7/D-06]
- [ ] 08.23.2.TAXO2-06-convlogs-aggregat-schatten-PLAN.md — conversation_logs-Aggregat Schatten-Welle (Engine rechnet alle, loggt Diskrepanzen) [W5, Req 8]
- [ ] 08.23.2.TAXO2-07-convlogs-aggregat-cutover-PLAN.md — Cutover: Engine = EIN Schreiber je Aggregat-Feld, alte raus, FK unangetastet [W6, Req 8]

**🔴 → Cross-AI PFLICHT vor Execute** (André-Direktive: TAXO1/2/3 alle bis kurz vor Execute, dann Ineinandergreifen prüfen, dann TAXO1→TAXO2→TAXO3). NÄCHSTER SCHRITT: /gsd-review --phase 08.23.2.TAXO2 --all. Alle 9 SPEC-Requirements abgedeckt. Multi-Segment-Gotcha: Pfade hardcoded, gsd-tools umgangen, STATE/ROADMAP hand-editiert.

### Phase 08.23.2.TAXO3: Antworten — EINE Wissensversorgung (Säule 3) (NEU 2026-06-10) 🔴

**Goal:** EINE `build_answer_context()`-Funktion für ALLE KI-Antwort-Pfade (QA-Pipeline, manueller Knopf, Auto-Variante) — kein Antwort-Pfad mehr ohne Profil-Persona + Voice-Anker. Die kontext-arme hardcoded Auto-Variante stirbt.

**Scope (Gerüst §4.5 inkl. KORREKTUR 2026-06-12 / §5 Bau-Regel 3 — Scope geschärft nach 3-Wege-Abgleich + André-Freigabe; QUELL-DOC PFLICHT: Vault `04 Entscheidungen/NERVE TAXO-Gerüst (verriegelt).md` §4.5-KORREKTUR + `03 Planung/Antwort-Wissensversorgung für NERVE Entscheidungsreife Empfehlung.md` + `03 Planung/Taxo3 coach schnittstelle planungs vorgabe.md`):** (1) `build_answer_context()` bauen, kontext-arme hardcoded Auto-Variante LÖSCHEN (Single Source, Konstrukt §2 "jede Antwort = voller Kontext"); (2) lokale Slot-A-Stichwort-Antwort BLEIBT (schnelle Bahn, Sofort-Netz aus Profil in User-Stimme); (3) kuratiertes Intent→Technik→Fakten-Mapping als editierbare Config (JSON/DB, NICHT hardcoded in Python) — die Taxonomie IST die Routing-Tabelle, KEIN RAG/Vektor-DB; **(4) PARADIGMA-RESET (Kern, Haupt-Müll-Ursache): Grund-Anweisung von "bekämpfe Einwand → Reframe → Gegenargument → Close" auf "verstehen + diagnostizieren + helfen + rollen-angemessen" drehen; Technik als unsichtbares Gerüst (Gong/Voss-Haltung), NIE als Vokabular; KEINE Beispiel-Antworten — auch NICHT die eigenen hinterlegten Gegenargumente als "Vorlage zum Nachbauen" (= derselbe Cliché-Anker, homogenisiert die Stimme, belegt Moon 2025/Padmakumar ICLR2024); Stimme kommt aus Stil-Deskriptoren des Profils + Paradigma, nicht aus Beispielen; (4b) ROLLEN-REGISTER config-getrieben: Gatekeeper ≠ Interessent ≠ Meeting, Gatekeeper-Ziel = Respekt+Ehrlichkeit, NICHT "Einwand überwinden";** (5) immer EIN Intent ans LLM (der wahrscheinlichste, kein Top-2-Hedging); (6) Modus + Konfidenz als EIN Parameter in derselben Funktion (Cold Call vorsichtiger, Meeting tiefer, Training Ground-Truth — kein Code-Zweig); **(6b) COACH-TÜR mitbauen (nur Tür, nicht Raum): Intent→Technik-Mapping als austauschbares versioniertes `method_pack` (Default=NERVE-eigenes, beim Start einziges Paket) + `pack_assignments`-Tabelle mit `valid_until`/stillem Default-Fallback; Rangfolge bei Konflikt User-Stimme > Methoden-Paket > NERVE-Default; NERVE-Default standalone vollwertig; HARTE LINIE: Coach sieht NIE Calls/Transkripte/Scores seiner Kunden; Schema-Vorgabe E1-E3 + Akzeptanzkriterien siehe Vault `Taxo3 coach schnittstelle planungs vorgabe.md`;** (7) Produktwissen als strukturierte intent-getaggte FAQ mit IDs + "reguliert/riskant"-Flag + Grounding-Regel (KEINE Live-Web-Recherche in der Live-Schleife); (8) deterministische Single-Source-pro-Fenster (Slot B per line_id/Event-ID dedupliziert — behebt D3 Doppel-Emit keyword_einwand_match + qa_slot1, Bau-Regel 3; **line_id-Dedup hängt an TAXO1-03 per-SID — Interlock**); **(9) PROMPT-CACHING NUTZEN (NICHT mehr deferred — Infra existiert schon: config.CACHE_EWB, cache_control:ephemeral, TTFT-Circuit-Breaker EWB_SONNET_FALLBACK_TTFT_MS), Sonnet als HAUPT-Modell (Haiku nur Fallback); ⚠ flüchtige Daten (PreCall-Briefing/Lead-Kontext) NICHT in den gecachten System-Prompt-Prefix (Cache-Miss-Falle, Gemini-Fund — gegen Live-Code prüfen); ⚠ eigene TTFT-Messung Pflicht vor Festzurren (Cached-Zahlen interpoliert); Circuit-Breaker beim Umbau auf EINE Funktion als Wrapper mit is_auto_triggered-Flag (Auto downgradet zu Haiku bei Spike, manueller Button probiert immer Sonnet).** DEFERRED (Post-Launch): Top-2-Laden, User-eigenes Stimm-Onboarding, Coach-FEATURE selbst (Dashboard/Paket-Editor-UI/Abrechnung — nur die Tür jetzt).

**Depends on:** 08.23.2.TAXO1 (`intent_event`-Schema; nutzt primary_intent + confidence + mode).
**Komplexität:** 🔴 — berührt jeden Live-Antwort-Pfad. Cross-AI **Pflicht**. Context7 für SDK-Calls (Anthropic). Real-Daten-Validation Pflicht.
**★ PFLICHT-PULL aus backlog.md bei TAXO3-Planung (Live-Test 2026-06-17/18):** `ANON-LIVE-ANSWER` (Live-Antwort wird auf anonymisiertem Text gebaut → [ORG_B]/[PERSON_A] in der Antwort = Unsinn; DSGVO-Entscheidung „echter Text live, Anonymisierung storage-only" — berührt DSGVO-Pfeiler, mit Gemini + DSGVO-Doc) + `POSTCALL-COACH-QUALITY` (Antworten/Tipps schwach, Pitch-Floskeln, kein Profil-Bezug, verwirrende Beispiel-Termine — = Paradigma-Reset #4 in Aktion). TAXO3-Plan MUSS beide explizit adressieren.
**Plans:** 5 plans / 5 De-Risk-Wellen (GEPLANT 2026-06-12, Wave-Cut RESEARCH: erst Ton, dann Tempo; W3 gated auf TAXO1-interaction_id-Interlock)

Plans:
- [ ] 08.23.2.TAXO3-01-coach-tuer-schema-grant-PLAN.md — W0 Schema-Tür: method_packs + pack_assignments + product_facts (**public-Schema**, leer) — **OQ-1 = Option B (André 2026-06-12): public, KEIN training-Grant, DPO-Wand bleibt absolut (Blast-Radius)** + Schild [W1, SPEC Req 4/7-Schema; schema-addition, kein Test-Anruf]
- [ ] 08.23.2.TAXO3-02-nerve-default-pack-freigabe-PLAN.md — W0b: NERVE-Default method_pack-Inhalt destilliert (Paradigma+3 Rollen+3 Tabus) → André-Freigabe (D-01) → idempotenter Seed [W2, SPEC Req 2/3/4-Inhalt; daten-seed, kein Test-Anruf]
- [ ] 08.23.2.TAXO3-03-build-answer-context-ton-PLAN.md — W1 Ton (größter Hebel): EINE build_answer_context (Wrapper, Block-Split strukturell), Auto-Müll + Few-Shot gelöscht, Paradigma/Rollen/Intent aus method_pack, EIN Intent, Modus/Konfidenz Parameter, Grounding-Regel [W3, SPEC Req 1/2/3/4-Loader/5/6/7-Grounding; riskant, Test-Anruf + TTFT-Basislinie]
- [ ] 08.23.2.TAXO3-04-caching-circuit-breaker-tempo-PLAN.md — W2 Tempo: cache_control-Layering aktiv (stabil cached/volatil ungecacht), Pre-Warming nicht-blockierend, is_auto_triggered-Circuit-Breaker (Auto→Haiku/Knopf→Sonnet) [W4, SPEC Req 9; riskant, Test-Anruf + eigene TTFT-Messung + cache_read>0]
- [ ] 08.23.2.TAXO3-05-slot-b-dedup-interaction-id-PLAN.md — W3 D3-Dedup: Slot B deterministisch per interaction_id (nicht line_id/Mutex), keyword-Doppelung raus, Slot A bleibt, FE-Render-Dedup [W5, SPEC Req 8; riskant, Test-Anruf; GATED auf TAXO1-04-I-4-Fix + interaction_id-Quelle per-SID]

**🔴 → Cross-AI PFLICHT vor Execute** (André-Direktive: TAXO1/2/3 alle bis kurz vor Execute, dann 3-Wege-Interlock intent_event-Klebstoff, dann Execute TAXO1→2→3). W0 OQ-1-Schema-Entscheidung (narrow GRANT vs public vs coach-Schema) am Cross-AI-Review bestätigen. W3 erst nach TAXO1-04-Blocker-I-4-Fix + interaction_id-Quelle-Klärung. NÄCHSTER SCHRITT: /gsd-review --phase 08.23.2.TAXO3 --all. Alle 9 SPEC-Requirements abgedeckt. Multi-Segment-Gotcha: Pfade hardcoded, gsd-tools umgangen, STATE/ROADMAP hand-editiert.

> ⚠️ Multi-Segment-ID-Gotcha (wie SCHILD): Pfade auf `.planning/phases/08.23.2.TAXO1-*/` etc. hartkodieren. Verify=Production, kein Local-Dev. Plan-Pflicht-Sektionen Punkt 14 (Control-Flow) + Punkt 21 (Persistenz-Schicht) bei jedem Code-Insert.

### Phase SEC-USERDATA: App-weite Userdaten-Sicherheits-Prüfung (PFLICHT vor Launch, André 2026-06-12) 🔴

**Goal:** Proportionierte (NICHT Fort-Knox) Sicherheits-Prüfung der sensiblen Userdaten über die ganze App — getrennt von TAXO (dort wird der Daten-Fußabdruck pro Phase inline gesichert; SEC-USERDATA prüft das Gesamtbild + den Rest + den äußeren Zaun).

**Scope:** (1) **Äußerer Zaun (kurz):** WAF/Schutzschild, Rate-Limiting (Flask-Limiter teils da → verifizieren+ergänzen), Account-Lockout nach Fehl-Logins, fail2ban-Pattern. (2) **Innere Schlösser (gründlich, das Wichtigere):** hält die per-user/tenant-Isolation an JEDER Tabelle+Query (RLS vs App-Level)? Ist Sensibles im Breach-Fall nicht leicht erreichbar (Blast-Radius)? Deckt die Anonymisierung jeden Persistenz-Pfad? Encryption-at-rest? DB-Credential-Handhabung? Secrets-Management. **Zahlungsdaten via Stripe (nicht bei uns) — Anbindung bestätigen.** **Output:** Klartext-Bericht „was dicht / was nicht" + Fix-Liste. **Werkzeug:** security-review-Skill + `/gsd-secure-phase` + Prod-Check Zugriffsrechte/RLS via inspect.sh. **Komplexität:** 🔴 (Security/DSGVO, Cross-AI Pflicht). **⚠ Timing offen (André 2026-06-12):** Fable 5/Mythos (Security-Tool) nur bis ~nächste Woche → erwägen, es JETZT auf stabile Schichten (Auth/Datenschicht/DSGVO-Architektur) + TAXO-Pläne anzusetzen und Funde zu banken, statt das Fenster verfallen zu lassen. Entscheidung steht aus.

---

## Backlog

> Unsequenzierte Ideen (999.x), noch nicht in der aktiven Phasen-Reihenfolge. Promoten via `/gsd-review-backlog`.

### Phase 999.1: Admin-Nutzerverwaltung + Login-Härtung — ✅ PROMOTET 2026-05-30 → Phase 08.23.2.LOGIN (oben in der aktiven Reihenfolge)

**Goal:** Eine Backend-Maske mit der Andre selbst User anlegen kann, plus ein Audit ob echte User sich vor dem EA-Launch sauber einloggen können.

**Side-Feature — Admin-Nutzerverwaltung:**
- Backend-Maske zum User-Anlegen (Admin-only)
- "Passwort generieren"-Knopf (sicheres Zufalls-Passwort)
- Automatische Willkommens-Mail an die eingetragene Adresse (mit Zugangsdaten / Login-Weg)
- Auswahl beim Anlegen: regulärer Account vs. Test-Account (`is_test_user`-Flag setzen)

**Launch-relevant — Login-Härtung (Pre-EA-Launch-Audit):**
- Login-Bereich wirkt fehlerhaft → vor EA-Launch prüfen ob echte User (Passwort-Login + OAuth Google/Microsoft) sich sauber einloggen können. Edge-Cases: falsches Passwort, nicht-bestätigte Email, OAuth-Erstanmeldung.

**Hintergrund:** Der Test-Account `andre-test@nerve.local` wurde in Phase 08.23.2.D.UX.0 direkt in der Datenbank angelegt — OHNE Login-Weg (kein OAuth-Konto, kein gesetztes Passwort). Dadurch ist er real nicht einloggbar. Live-Tests mit dem Test-User brauchen entweder einen gesetzten Passwort-Login oder die Admin-Maske oben.

**Requirements:** TBD
**Komplexität:** 🟡 (vermutlich — Admin-Maske + Mail-Versand + Login-Audit; finalisieren in Spec/Discuss)
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.2: Session-Detail Live-Auswertung ausbauen — 3 verwaiste UI-Platzhalter (BACKLOG, NEU 2026-05-30)

**Goal:** Drei "Future"-Platzhalter-Karten im Session-Detail (Live-Call-Detailansicht, `templates/session_detail.html`) versprechen Features mit TOTEN Phasen-Nummern. Aufräumen + als echte Features einordnen.

**Die 3 Platzhalter:**
1. **Wendepunkt-Analyse** (session_detail.html:367-372) — markiert einzelne Sätze die den Gesprächsverlauf kritisch beeinflusst haben. Label "Kommt mit Phase 4.19 (Transkript-Persistierung)".
2. **Einzel-Bewertungen** (session_detail.html:401-406) — 6 Coaching-Dimensionen (Gesprächseröffnung, Bedarfsanalyse, Einwandbehandlung, Gesprächsführung, Abschluss, Beziehungsaufbau) statt nur Gesamt-Score + 4 Komponenten. Label "Kommt mit Phase 4.19".
3. **Lernkarten / Coach-Modul** (session_detail.html:453-461) — max 3 Sätze pro Call als Lernkarte speichern, vor nächstem Call geladen. Label "Kommt mit Phase 4.11". (Coach-Modul-Backend existiert teilweise aus alter Phase 04.11.)

**WICHTIG — Status-Klärung 2026-05-30:**
- "Phase 4.19 (Transkript-Persistierung)" = Voraussetzung von #1+#2 = WURDE IN D.UX.1 GELIEFERT (transcript_segments-Tabelle). → #1 und #2 sind jetzt UNBLOCKED.
- Phasen-Nummern 4.19 / 4.11 sind STALE (alte Nummerierung, existieren in aktueller Roadmap nicht).
- **Pre-Launch-Polish-Bug (separat + kleiner):** die Badges zeigen interne Phasen-Nummern AN USER ("Kommt mit Phase 4.19") — unprofessionell fürs Verkaufsprodukt. Text vor Launch bereinigen (→ "folgt bald" oder Karte ausblenden), unabhängig davon wann die Features kommen.

**Verbindungen:** #2 Einzel-Bewertungen = Coaching-Score-Tiefe (verwandt mit Frage-Qualitäts-Dimension `frage_qualitaet=0.0` in app_routes.py:738 + Zwei-Track-Scoring, D.UX-Roadmap). #3 Lernkarten = verwandt mit Battlecard (vor Call geladen) + Coach-Modul. Alle 3 teilen die Transkript-Abhängigkeit mit Phase 08.23.2.D.UX.2 (Transcript-Reiter).

**Priorität:** TBD mit Andre — #2 (Einzel-Bewertungen) ist Coaching-Kernwert (evtl. pre-launch), #1/#3 eher Tiefe (evtl. post-launch). UI-Text-Cleanup ist kleiner Pre-Launch-Polish.
**Komplexität:** 🟡 (Sonnet-Analyse pro Dimension + UI), finalisieren in Spec/Discuss.
**Plans:** 0 plans

### Phase 999.3: Auto-Save-Meeting HONOR-Logik — gebuchte Termine ohne Form anlegen (BACKLOG, NEU 2026-06-02, aus G-MEET-Cross-AI MM-02)

**Goal:** Die echte Auto-Save-Behavior die das `auto_save_meeting`-Preference-Flag tatsächlich EINLÖST. In Phase 08.23.2.G-MEET (Meeting-Modal) wird das Häkchen "Solche Termine künftig automatisch merken" gebaut + die Präferenz nach `crm.user_preferences` persistiert — ABER die Honor-Logik (Termin am Call-Ende OHNE Form-Anzeige automatisch nach `crm.meetings` schreiben wenn Flag=true) ist bewusst NICHT in 04/05 enthalten. Cross-AI MM-02 (Gemini + Claudian) fing die sonst falsche UX-Versprechung; André-Entscheidung 2026-06-02 (Option b): Häkchen + Persistenz jetzt mit ehrlichem Hint ("Merkt sich deine Auswahl für später"), Honor-Logik in DIESE dedizierte Folge-Mini-Phase — direkt NACH G-MEET einzuplanen, weil sie den Call-End-Flow neu anfasst und richtig gebaut (nicht drangeflanscht) werden soll.

**Tasks (Skizze, in Spec/Discuss schärfen):**
1. Beim Call-Ende mit outcome=meeting_booked: `crm.user_preferences.auto_save_meeting` des aktuellen Nutzers (`g.user.id`, tenant-scoped) lesen.
2. Wenn true: Termin OHNE Form direkt nach `crm.meetings` schreiben (tenant_id-Stamp + resolve-or-create accounts/contacts wie POST /crm/meetings) — entscheiden: welche Felder aus dem Call ableitbar (Firma/Ansprechpartner/Datum/Thema), welcher Default-Zeitpunkt, was bei fehlenden Daten.
3. UX-Entscheidung: stille Bestätigung (Toast "Termin gemerkt") vs. Mini-Confirm; wie bei AI-unsicherem Outcome (confidence-Schwelle) verfahren — NICHT blind bei Unsicherheit auto-anlegen.
4. DSGVO bleibt: Flag default OFF (Art. 25 Abs. 2), jederzeit abschaltbar; Auto-Anlage nur bei explizitem Opt-in.

**Abhängigkeit:** Baut auf G-MEET Plan 04 (crm.user_preferences + /crm/meetings-Write-Pfad) + Plan 05 (Häkchen + Persistenz). Re-touchiert den D.UX.4 Post-Call-Flow.
**Komplexität:** 🟡 (Call-End-Flow-Integration + UX-Entscheidungen + confidence-Handling), finalisieren in Spec/Discuss.
**Plans:** 0 plans

---

## 🧭 Strategische Themen-Pipeline (aus Strategie-Gespräch 2026-06-06 — Vault-Sync)

> Überwiegend Post-Kernfeature / Phase 2-3. Volldetail + Einordnung im Vault: `Nerve-Vault/03 Planung/Strategie-Gespräch 2026-06-06.md` + `Nerve-Vault/01 Roadmap.md` (Sektion Strategische Themen-Pipeline). Bau-Reihenfolge wird mit Gemini abgestimmt (06.06.). **NICHT sofort** — erst Speech-Stats (Block J / Notizbuch B).

- **TAXO — Taxonomie-Rückgrat + Gesprächs-Verständnis-Konsolidierung** 🔴 (DAS große Architektur-Stück) — gemeinsame **Intent-Schicht** (Einwand/**Vorwand**/Info-Frage/Kaufsignal/Aufschub) + **Phasen-Achse** unter Live-Cues, Post-Call-Analyse, Training, Profil, Branchen-Packs. EWB UND VWB gleichwertig. Konsolidiert + repariert gedriftete Teile: Phasen-Analyse (`phase_classify`-Live-Bug), Speech-Stats, EWB-Keyword-Match, Training. Prozess: tiefer Code-Dive (Ist-Stand) → Recherche (Claude-Chat) → Realität-gegen-Recherche → Plan. Cross-AI + Real-Daten-Pflicht (Schema). Hängt mit Block-J-Outcome-Tracking + Phase E.
- **PRODWISSEN — Info-Frage-Intent + tiefes Produktwissen + Live-Recherche** 🟡/🔴 — NERVE erkennt Info-/Produkt-Fragen (3. Intent ≠ EWB/VWB) + Button schnelle/ausführliche Recherche → Teleprompter. (a) Profil-Produktwissen (erweitert `profile_faqs`, ZUERST, sicher) (b) Live-Web-Recherche (PreCall hat schon Anthropic Web Search; Latenz+Haftung → später). Hängt an TAXO.
- **HINTS — Stichpunkte-Toggle mehrstufig + adaptiv** 🟡 — Schalter ganze Sätze→Schlüsselphrase→Stichwort, Default Hilfestellung, adaptiver Schubs. Hängt an PROFILADAPT/TAXO-Skill-Stufen. **+ Slot-Routing (André 2026-06-12):** User wählt per Schalter, welche Antwort-Art in welches Feld fliegt (Profil-Treffer vs. KI → oben/unten). Tür-Öffner: TAXO3 baut Single-Source-pro-Fenster-Zuordnung als einstellbaren Wert, HINTS macht ihn später sichtbar.
- **PROFILADAPT — Adaptives Profil (Vorschläge aus Calls)** 🟡 — vorschlagen nie still editieren + Versionierung; Muster+Beleg; additiv vs korrigierend; Stimme nicht homogenisieren; Dosierung. Erste-Partei. Hängt an TAXO. Datenmodell nicht zumauern.
- **TRAINING-REVISIT — Trainingsmodus Taxonomie-getrieben modernisieren** 🟡 — veraltet. "Üben X" = Zeiger auf Szenario (nicht neue Generierung). Personas eng + Rubrics. NACH TAXO. Hängt an Phase E.
- **COST-ATTRIB — Kosten-Zuordnung org_id/user_id Multi-Session-korrekt (Tech-Debt, Pre-EA-Launch)** 🟡 — `cost_tracker.py` `_resolve_org_id/_resolve_user_id` nutzen aktuell einen **Interim-Resolver-Scan** über `_session_state` (erste/aktive Session; K8-Fix 2026-06-08, commit 8806516). Bei mehreren parallelen Sessions ist die Zuordnung **ambig** → vor EA-Launch `session_id` (=sid) durch die ~15 `log_api_cost`-Call-Sites threaden (Option 2), Resolver liest dann `_session_state[session_id]`. **Bau NACH TAXO-Stabilisierung** — nicht durch Live-Loop-Code (claude_service/deepgram/coaching/training/crm) fädeln, der dort noch im Umbau ist. Inline-Kommentar im Code markiert die Stelle.
- **MEETING-Modus** → schon verankert (08.23.2.MODES + Client-Vehikel-Entscheidung Hybrid Web+Extension). Recall.ai-Bot tabu. Multi-Person = binär reicht meist, Pro-Person = Extension-Premium.
- **Nicht-Build (Querverweis):** Legal-Moat (§7 UWG/AI Act, Mensch-in-Schleife = Burggraben) → Marketing; Retention-Policy (User-Daten behalten vs anonym. Korpus) → DSGVO + 08.23.2.ART17.

**Plus Block-J-Bug (Vault):** ~~`[phase_classify] loop error: '>' not supported between int and str` LIVE in Prod (05.06. 09:32) — Phasen-Klassifikation teils kaputt.~~ ✅ **GEFIXT 2026-06-08** (Quick-Task `20260608-phase-classify-int-str-fix`, commit `8db6278`, live auf Prod): Wurzel war `current_phase`-String-Label ('opener'/'greeting') beim manual_mode_toggle statt int 1 (deepgram_service.py) → Single-Source-of-State, kein Cast-Pflaster. TAXO muss den Bug NICHT mehr mitnehmen — die Phasen-Achsen-Konsolidierung bleibt aber Teil von TAXO.
