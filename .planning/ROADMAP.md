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

### Phase 08.23.2.C.1: Staging-Server aufsetzen + Deploy-Workflow Staging→Production (REWRITTEN — 2026-05-19) 🔴

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
**Plans:** 5 Plaene | Plan 01 DONE (Staging-Artefakte) | Plan 02 DONE (deploy.sh Refactor + /api/health + .env.staging.example) | Plan 03 DONE (reset_sequences.py + refresh_staging_from_production.sh, REVIEW-HIGH-3 Fix) | Plan 04 DONE (render_as_batch=True alembic/env.py REVIEW-MEDIUM-5 + Alembic-Auto-Hook app.py Python-API REVIEW-MEDIUM-4) | Plan 05 offen

Plans:
- [ ] TBD nach Spec-Phase
