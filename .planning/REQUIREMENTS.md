# Requirements: NERVE

**Defined:** 2026-03-30
**Core Value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

## v1 Requirements

Milestone 1: Launch — von v0.9.4 zu erstem zahlenden Kunden.

### Product Fixes

- [x] **PROD-01**: User kann das neue Pricing-System (69/59/49€ Flat-Rate) in der App sehen und einen Tarif auswählen
- [x] **PROD-02**: User sieht im Dashboard einen ROI-Tracker mit persönlichen Nutzungsmetriken
- [x] **PROD-03**: User kann Trainings-Modus "Frei" wählen (maximale Punkte, keine Hilfe-Hints)
- [x] **PROD-04**: User kann Trainings-Modus "Geführt" wählen (Hilfe verfügbar mit Punktabzug)
- [x] **PROD-05**: User sieht nach einem Training eine Preview "Was NERVE im echten Call gezeigt hätte" (Cross-Sell Live-Modus)
- [x] **PROD-06**: User kann aus 11 vordefinierten Standard-Trainingsszenarien (DACH Mittelstand) für alle Schwierigkeitsstufen wählen
- [x] **PROD-07**: Live-Modus zeigt korrekten Skript-Button, DSGVO-Banner vor Mikrofon-Zugriff, Kompakt-Modus Kreise und Toggle in richtiger Position
- [x] **PROD-08**: Onboarding nutzt generische Placeholder-Texte, bietet Dashboard-Stil Auswahl und zeigt Beispiel-Boxen
- [x] **PROD-09**: Neuer User durchläuft 3-Schritte Profil-Wizard statt leerem Formular beim ersten Login
- [x] **PROD-10**: Profil-Editor zeigt generische Placeholder ("Ihr Produkt", "Ihr Unternehmen") statt Demo-Inhalt
- [x] **PROD-11**: Alle SalesNerve-Referenzen im Code und UI sind durch NERVE ersetzt

### Infrastructure & Deployment

- [x] **INFRA-01**: App läuft stabil auf Hetzner CX22 VPS mit nginx + gunicorn (gthread, 1 Worker)
- [x] **INFRA-02**: Domain ist gesichert und SSL-Zertifikat via Let's Encrypt ist aktiv
- [x] **INFRA-03**: nginx WebSocket-Proxying ist korrekt konfiguriert (Socket.IO zeigt `101 Switching Protocols`, kein Fallback auf Polling)
- [ ] **INFRA-04**: SQLite WAL-Modus ist aktiv; SECRET_KEY-Fail-Fast-Assertion blockiert Start ohne sicheren Key
- [ ] **INFRA-05**: PyAudio ist nicht in Server-Requirements; App startet auf VPS ohne Audio-Hardware

### Payments & Metering

- [ ] **PAY-01**: User kann einen der 3 Tarife über Stripe Checkout bezahlen (Hosted Checkout Session)
- [ ] **PAY-02**: Subscription-Aktivierung erfolgt ausschließlich per Webhook (`checkout.session.completed`), nicht per Redirect-URL
- [ ] **PAY-03**: Stripe Webhook Handler ist idempotent (dedupliziert per `stripe_event_id`) und verifiziert Signatur mit rohem Request-Body
- [ ] **PAY-04**: User kann Abo über Stripe Customer Portal selbst verwalten (Upgrade, Downgrade, Kündigung)
- [ ] **PAY-05**: Live-Minuten und Trainings-Sessions werden atomar in DB gezählt; bei ~80% Fair-Use-Limit erscheint Soft-Warning; kein harter Block
- [ ] **PAY-06**: Pricing-Seite zeigt alle 3 Tarife mit Feature-Vergleich, Fair-Use-Limits und Gründerrabatt-Badge

### Legal & DSGVO

- [ ] **LEGAL-01**: DSGVO-Einwilligungs-Banner erscheint vor erstem Mikrofon-Zugriff (nicht danach)
- [ ] **LEGAL-02**: Impressum (TMG §5-konform), AGB (mit Klausel zur Drittdaten-Verarbeitung) und Datenschutzerklärung (Deepgram, Anthropic, ElevenLabs als Auftragsverarbeiter genannt) sind live
- [ ] **LEGAL-03**: Signierte AVVs mit Deepgram, Anthropic, ElevenLabs und Stripe liegen vor; Deepgram EU-Endpunkt (`api.eu.deepgram.com`) wird verwendet
- [ ] **LEGAL-04**: `cors_allowed_origins` in SocketIO-Init ist auf die produktive Domain gesetzt (kein `"*"`)

### Business Setup

- [ ] **BIZ-01**: Gewerbeanmeldung beim Gewerbeamt Iserlohn ist eingereicht
- [ ] **BIZ-02**: Geschäftskonto (Kontist oder Finom) ist eröffnet und verknüpft
- [ ] **BIZ-03**: USt-IdNr beim Bundeszentralamt für Steuern beantragt
- [ ] **BIZ-04**: Steuerberater count.tax kontaktiert und Erstgespräch vereinbart

### Launch

- [ ] **LAUNCH-01**: Early Access mit 50 Plätzen und 50% Gründerrabatt ist live; Waitlist-Mitglieder werden benachrichtigt

## v2 Requirements

Deferred nach Milestone 1 (nach DACH-Validierung und erstem MRR).

### Internationalization

- **I18N-01**: Englischsprachige UI und Onboarding für US-Markt
- **I18N-02**: Pricing in USD ($99 statt 69€)
- **I18N-03**: US-amerikanische Trainingsszenarien

### Infrastructure Scale

- **SCALE-01**: Migration von SQLite auf PostgreSQL
- **SCALE-02**: Redis Adapter für Flask-SocketIO (Multi-Worker-Support)
- **SCALE-03**: Monitoring/Alerting (Uptime, API-Fehler, Session-Fehler)

### Voice & AI

- **VOICE-01**: Eigenes TTS (Piper/Coqui) als ElevenLabs-Ersatz (ab ~500 Kunden)
- **VOICE-02**: Fine-tuned Sales-KI (Llama/Mistral) als Claude-Ergänzung (Milestone 4)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Englische UI / US-Markt | Erst Milestone 2 nach DACH-Validierung |
| Eigenes TTS (Piper/Coqui) | Erst Milestone 3 ab ~500 Kunden — größter Margenhebel |
| Eigene Sales-KI (fine-tuned) | Erst Milestone 4 |
| Enterprise-Features (SSO, Admin-Rechte) | Zu früh, falsche Zielgruppe für Milestone 1 |
| Mobile App | Desktop-Tool — kein Bedarf für mobile Nutzung |
| Outbound-Calling / autonomes AI-Calling | Andere Produktkategorie |
| Training Modus 3 (Live NERVE-Antworten im Training) | Würde Live-Assistenten entwerten |
| Metered Billing (pay-per-use via Stripe UsageRecord) | Flat-Rate ist Produktentscheidung; metered billing ist falsche Architektur |
| React-Migration | Stack-Constraint: Flask + Vanilla JS bleibt |
| PostgreSQL Milestone 1 | SQLite + WAL ist ausreichend für 50 Early Access User |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BIZ-01 | Phase 1 | Pending |
| BIZ-02 | Phase 1 | Pending |
| BIZ-03 | Phase 1 | Pending |
| BIZ-04 | Phase 1 | Pending |
| PROD-01 | Phase 2 | Complete |
| PROD-02 | Phase 2 | Complete |
| PROD-03 | Phase 2 | Complete |
| PROD-04 | Phase 2 | Complete |
| PROD-05 | Phase 2 | Complete |
| PROD-06 | Phase 2 | Complete |
| PROD-07 | Phase 2 | Complete |
| PROD-08 | Phase 2 | Complete |
| PROD-09 | Phase 2 | Complete |
| PROD-10 | Phase 2 | Complete |
| PROD-11 | Phase 2 | Complete |
| INFRA-01 | Phase 3 | Complete |
| INFRA-02 | Phase 3 | Complete |
| INFRA-03 | Phase 3 | Complete |
| INFRA-04 | Phase 3 | Pending |
| INFRA-05 | Phase 3 | Pending |
| LEGAL-04 | Phase 3 | Pending |
| PAY-01 | Phase 4 | Pending |
| PAY-02 | Phase 4 | Pending |
| PAY-03 | Phase 4 | Pending |
| PAY-04 | Phase 4 | Pending |
| PAY-05 | Phase 4 | Pending |
| PAY-06 | Phase 4 | Pending |
| LEGAL-01 | Phase 4 | Pending |
| LEGAL-02 | Phase 4 | Pending |
| LEGAL-03 | Phase 4 | Pending |
| LAUNCH-01 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 31/31 ✓
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 — traceability filled by roadmapper*
