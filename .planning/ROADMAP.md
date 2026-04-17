---
created: 2026-03-30
milestone: v0.9.4
total_phases: 5
estimated_duration_days: 16
---

# Roadmap: NERVE

**Source:** Project interview on 2026-03-30
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
> Ohne Cost-Dashboard kann der Founder nicht erkennen, ob ein Customer profitabel ist oder subventioniert wird. Besonders bei Power-Usern in Plan 1 (49€) können die API-Kosten 60-80% der Einnahmen fressen. Dashboard liefert Early Warning Signals bevor sich Cost-Ratios in die Kassen fressen. Erste Version reicht Tagesgenauigkeit (kein Realtime), Aggregation nightly über bestehende ft_logs. Alert-System ersetzt manuelle SQL-Queries.

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
> Vertriebler haben oft keine Zeit für Recherche. PreCall-Button liefert in &lt; 10s ein Briefing (Firma, Person, letzte News, mögliche Einwände). Spart 15-30min pro Call.

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

---

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
**Requirements:** BUG-10-529
**Depends on:** Phase 06.2
**Plans:** 0 plans
