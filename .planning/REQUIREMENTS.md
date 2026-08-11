# Requirements: NERVE

**Defined:** 2026-03-30
**Core Value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

> ## ⚠ ALTERS-WARNUNG — diese Datei ist auf Stand 2026-04-04 (Hinweis eingefügt 2026-08-11)
> Sie beschreibt die Anforderungen aus der **DACH-first**-Zeit und hat seither **keine** systematische Korrektur bekommen. Bei einer Drift-Suche am 11.08. fielen mehrere Zeilen auf, die dem geltenden Stand widersprachen (US-Markt als „out of scope", sichtbare Punktzahlen, EU-Endpunkt als Pflicht) — die auffälligsten sind jetzt einzeln markiert, **eine vollständige Durchsicht steht aus.**
> **Bei jedem Widerspruch gewinnen — in dieser Reihenfolge:** ① `Nerve-Vault/04 Entscheidungen/NERVE Konstrukt - Soll-Verhalten.md` (kanonisches Soll-Verhalten) ② `.planning/ROADMAP.md` + die Vault-Roadmap (geltende Reihenfolge) ③ diese Datei.
> **Drei Dinge, die hier flächig veraltet sind:** **(a) Markt** — US-first seit 04.07., nicht DACH. **(b) Bewertung** — keine sichtbare Note/Punktzahl mehr seit 28.06.; wo hier „Score" steht, ist es überholt. **(c) Server-Region** — folgt dem Markt (US); EU-Endpunkte sind keine Pflicht mehr.

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
- [x] **INFRA-04**: SQLite WAL-Modus ist aktiv; SECRET_KEY-Fail-Fast-Assertion blockiert Start ohne sicheren Key
- [x] **INFRA-05**: PyAudio ist nicht in Server-Requirements; App startet auf VPS ohne Audio-Hardware

### Payments & Metering

- [x] **PAY-01**: User kann einen der 3 Tarife über Stripe Checkout bezahlen (Hosted Checkout Session)
- [x] **PAY-02**: Subscription-Aktivierung erfolgt ausschließlich per Webhook (`checkout.session.completed`), nicht per Redirect-URL
- [x] **PAY-03**: Stripe Webhook Handler ist idempotent (dedupliziert per `stripe_event_id`) und verifiziert Signatur mit rohem Request-Body
- [x] **PAY-04**: User kann Abo über Stripe Customer Portal selbst verwalten (Upgrade, Downgrade, Kündigung)
- [ ] **PAY-05**: Live-Minuten und Trainings-Sessions werden atomar in DB gezählt; bei ~80% Fair-Use-Limit erscheint Soft-Warning; kein harter Block
- [ ] **PAY-06**: Pricing-Seite zeigt alle 3 Tarife mit Feature-Vergleich, Fair-Use-Limits und Gründerrabatt-Badge

### Legal & DSGVO

- [ ] **LEGAL-01**: DSGVO-Einwilligungs-Banner erscheint vor erstem Mikrofon-Zugriff (nicht danach)
- [ ] **LEGAL-02**: Impressum (TMG §5-konform), AGB (mit Klausel zur Drittdaten-Verarbeitung) und Datenschutzerklärung (Deepgram, Anthropic, ElevenLabs als Auftragsverarbeiter genannt) sind live
- [ ] **LEGAL-03**: Signierte AVVs mit Deepgram, Anthropic, ElevenLabs und Stripe liegen vor; Deepgram EU-Endpunkt (`api.eu.deepgram.com`) wird verwendet
- [x] **LEGAL-04**: `cors_allowed_origins` in SocketIO-Init ist auf die produktive Domain gesetzt (kein `"*"`)

### Live-Mikrofon Fix (INSERTED — Phase 04.1)

- [x] **MIC-01**: Server startet ohne PyAudio — kein `import pyaudio` im Produktionscode; deepgram_service.py verwaltet per-Socket.IO-Session Deepgram-Verbindungen
- [x] **MIC-02**: Jede Socket.IO-Session bekommt eine eigene Deepgram-WebSocket-Verbindung; Lifecycle: open bei `start_live_session`, close bei `stop_live_session` oder disconnect
- [x] **MIC-03**: Browser erfasst Mikrofon-Audio via `getUserMedia` + AudioWorklet (16kHz, Int16 PCM) und streamt via Socket.IO `audio_chunk` Events an den Server
- [x] **MIC-04**: Live-Transkription funktioniert end-to-end auf getnerve.app: Browser-Mikrofon → Server → Deepgram → Transkript im UI

### Cold Call und Meeting Modi (INSERTED — Phase 04.2)

- [x] **MODE-01**: User wählt vor Session-Start auf `/live` zwischen Cold Call und Meeting Modus (Pre-Session Overlay, kein Wechsel mid-call)
- [x] **MODE-02**: Cold Call nutzt Deepgram Single-Speaker-Modus (`diarize=false`); nur Berater-Audio wird verarbeitet, kein Kunden-Audio an Deepgram gesendet
- [x] **MODE-03**: Meeting zeigt Consent-Pop-up mit Vorleseskript; Stattgegeben startet volle Diarization, Abgelehnt fällt nahtlos auf Cold Call zurück
- [x] **MODE-04**: EWB-Buttons (aus aktivem Profil `einwaende` oder DACH-Standard-Fallback) triggern sofortige Claude-Haiku-Anfrage mit Einwand-Kontext und Profil-Gegenargumenten
- [x] **MODE-05**: `session_mode` ('cold_call'/'meeting') wird in `ConversationLog` gespeichert; aktiver Modus als Badge im `/live` Header sichtbar
- [x] **MODE-06**: EWB-Button-Presses werden in `quick_action_log` mit `typ='ewb'` geloggt und über bestehenden `qa_count`-Mechanismus in `api_beenden` persistiert

### Design Unification (INSERTED — Phase 04.3)

- [x] **DU-01**: Beenden-Button im Live-Assistenten funktioniert — User kann jederzeit zurück zum Dashboard navigieren
- [x] **DU-02**: Light Mode komplett entfernt — alle CSS Media Queries, Variablen und Toggle-Logic für `prefers-color-scheme: light` sind gelöscht (nicht versteckt)
- [x] **DU-03**: Dashboard, Training, Live-Assistent, Analytics, Profil, Profil-Editor, Einstellungen (alle 4 Tabs), Hilfe-Center zeigen einheitliches dunkles Farbschema
- [x] **DU-04**: Einstellungen-Seite hat dunklen Page-Background; Cards sind nahtlos integriert (kein "schweben auf hellem Hintergrund")
- [x] **DU-05**: Analytics/Logs-Tabelle hat dunklen Page-Background und Dark-Theme-Styling
- [x] **DU-06**: Training-Seite hat dunklen Hintergrund; Anrufen-Button ist kontrastreich (Teal auf Dark)
- [x] **DU-07**: Profil-Editor hat dunklen Hintergrund, Input-Felder mit dunklem BG + heller Border, Labels in Weiß/Teal
- [x] **DU-08**: Hilfe-Center konsistent mit Dark Theme; Section-Headers in Teal statt Orange
- [x] **DU-09**: Footer-Links (Impressum, AGB, Datenschutz) aus allen Seiten entfernt; stattdessen in Einstellungen unter "Rechtliches" Tab
- [x] **DU-10**: Header-Bereich ohne `admin@nerve.local` und Logout-Button; E-Mail-Anzeige und Logout in Einstellungen (Profil-Tab)
- [x] **DU-11**: Sprach-Buttons aus Training-Seite entfernt; Spracheinstellung in Einstellungen (Profil-Tab, "Bevorzugte Sprache")
- [x] **DU-12**: Settings-Button in Sidebar hat identische Pixel-Position auf allen Seiten (kein Springen)

### Training Analytics & Tools (INSERTED — Phase 04.5)

- [ ] **TA-01**: `GET /api/training/stats` liefert Sessions (Woche/Monat/Gesamt), Durchschnittsdauer, Streak, Wochenziel und Heatmap-Daten fuer den eingeloggten User
- [ ] **TA-02**: `GET /api/training/recommendation` liefert eine regelbasierte KI-Empfehlung (schlechtester Einwand, Streak-Break, Trend) ohne zusaetzlichen LLM-Call
- [ ] **TA-03**: Einwand-Heatmap zeigt alle 7 Einwand-Typen als farbige CSS-Kacheln (gruen > 70%, gelb 40-70%, rot < 40%, neutral bei fehlenden Daten)
- [ ] **TA-04**: Klick auf eine Heatmap-Kachel startet Quick-Training mit vorkonfiguriertem Einwand-Typ via URL-Parameter `?quick=1&einwand_typ=...`
- [ ] **TA-05**: Phrasen-Bank zeigt Wendepunkt-Saetze aus Post-Call Analysen (extrahiert via `generate_scoring()`), filterbar nach Einwand-Typ, paginiert mit 20 Eintraegen pro Seite
- [ ] **TA-06**: Wochenziel-Card: User kann Ziel setzen (1-30), Fortschrittsbalken zeigt Sessions dieser Woche vs. Ziel, Reset per Kalenderwoche
- [ ] **TA-07**: Letzte Session Card zeigt kompakte Zusammenfassung (Szenario, Dauer, Score, Haupt-Einwand, Top-Verbesserungstipp) mit Link zur Dashboard-Analyse
- [ ] **TA-08**: Alle neuen Cards verwenden exakt die Design-Spezifikation: #FFFFFF Card BG, 12px Border-Radius, `0 1px 3px rgba(0,0,0,0.08)` Shadow, teal #00D4AA Akzente
- [ ] **TA-09**: Keine neuen Farben ausserhalb der definierten Palette, keine Gradient-Backgrounds, Sidebar (#0D1117) unveraendert

### Backend & Feedback System (INSERTED - Phase 04.7)

- [ ] **BE-01**: users.is_superadmin Flag + ENV-Seed via SUPERADMIN_EMAIL + @superadmin_required Decorator
- [ ] **BE-02**: Flask-Admin unter /admin mit SecureIndexView Auth-Gate (Bootstrap4 Theme)
- [x] **BE-03**: audit_log Tabelle + SQLite Immutable Trigger + log_action() Helper + Wire-up in Login/Session/Profil Routes
- [x] **BE-04**: objection_events Tabelle + EWB-Klick-Persistenz pro ConversationLog (Naming-Konflikt avg_deal_wert dokumentiert)
- [x] **BE-05**: feedback Tabelle (NEU, getrennt von FeedbackEvent) + Sidebar-Button + Modal + Screenshot-Upload /opt/nerve/uploads/feedback + POST /api/feedback + /api/feedback/quick
- [x] **BE-06**: Resend EU-Region Integration + 3 Templates (Welcome, Feedback-in-Planung, Password-Reset)
- [x] **BE-07**: Session-History Seite (Umbau bestehender Analytics-Seite zu chronologischer ConversationLog-Liste + Detail-View)
- [x] **BE-08**: Admin-Dashboard mit ModelViews (User, Org, Feedback, AuditLog, ConversationLog) + KPI CustomView + Planungs-Liste + Ticket-Workflow (new -> in_planning mit Resend-Trigger)

### PiP Komplett-Rebuild (INSERTED - Phase 06)

- [x] **PIP-01**: PiP Live-Bereich zeigt Split-Layout (55% KI-Zone oben, 45% Teleprompter unten) statt Tabs
- [x] **PIP-02**: Claude-Antworten erscheinen Wort-fuer-Wort via Socket.IO Streaming im PiP (kein Polling), mit blinkendem Cursor
- [x] **PIP-03**: Dual-Slot-System zeigt zwei KI-Antworten gleichzeitig; bei Themenwechsel werden beide ersetzt, bei neuem Einwand waehrend Streaming laeuft Slot 1 weiter und Slot 2 beantwortet neu
- [x] **PIP-04**: Skript-Teleprompter zeigt vollen Skript-Text mit semantischer KI-Positionserkennung (skript_position), aktiver Block hervorgehoben, manuelles Scrollen ueberschreibt KI-Position fuer 8 Sekunden
- [x] **PIP-05**: Transparenz-Regler steuert NUR den Hintergrund-Layer (rgba); Schrift, Buttons und KI-Hinweise bleiben bei 100% Opacity; Wert in localStorage gespeichert

### Business Setup

- [ ] **BIZ-01**: Gewerbeanmeldung beim Gewerbeamt Iserlohn ist eingereicht
- [ ] **BIZ-02**: Geschäftskonto (Kontist oder Finom) ist eröffnet und verknüpft
- [ ] **BIZ-03**: USt-IdNr beim Bundeszentralamt für Steuern beantragt
- [ ] **BIZ-04**: Steuerberater count.tax kontaktiert und Erstgespräch vereinbart

### Launch

- [ ] **LAUNCH-01**: Early Access mit 50 Plätzen und 50% Gründerrabatt ist live; Waitlist-Mitglieder werden benachrichtigt

## v2 Requirements

~~Deferred nach Milestone 1 (nach DACH-Validierung und erstem MRR).~~ ⛔ **ÜBERHOLT (markiert 11.08.): „nach DACH-Validierung" ist seit dem US-first-Beschluss vom 04.07. kein gültiger Zeitpunkt mehr** — diese Validierung findet nicht statt. Was hier verschoben wurde, braucht einen **neuen** Termin gegen die geltende Reihenfolge.

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
| ~~Englische UI / US-Markt~~ | ⛔ **UMGEKEHRT seit 04.07.2026 — US-FIRST.** Englische Oberfläche und US-Markt sind **nicht** out-of-scope, sondern **Start-Voraussetzung**. Es gibt keine „DACH-Validierung" mehr, gegen die etwas verschoben werden könnte. Diese Zeile stand bis 11.08. unmarkiert hier, während `PROJECT.md` denselben Satz ausdrücklich als überholt führte — **zwei geladene Dateien sagten das Gegenteil.** |
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
| INFRA-04 | Phase 3 | Complete |
| INFRA-05 | Phase 3 | Complete |
| LEGAL-04 | Phase 3 | Complete |
| PAY-01 | Phase 4 | Complete |
| PAY-02 | Phase 4 | Complete |
| PAY-03 | Phase 4 | Complete |
| PAY-04 | Phase 4 | Complete |
| PAY-05 | Phase 4 | Pending |
| PAY-06 | Phase 4 | Pending |
| LEGAL-01 | Phase 4 | Pending |
| LEGAL-02 | Phase 4 | Pending |
| LEGAL-03 | Phase 4 | Pending |
| MIC-01 | Phase 4.1 | Complete |
| MIC-02 | Phase 4.1 | Complete |
| MIC-03 | Phase 4.1 | Complete |
| MIC-04 | Phase 4.1 | Complete |
| MODE-01 | Phase 4.2 | Complete |
| MODE-02 | Phase 4.2 | Complete |
| MODE-03 | Phase 4.2 | Complete |
| MODE-04 | Phase 4.2 | Complete |
| MODE-05 | Phase 4.2 | Complete |
| MODE-06 | Phase 4.2 | Complete |
| DU-01 | Phase 4.3 | Complete |
| DU-02 | Phase 4.3 | Complete |
| DU-03 | Phase 4.3 | Complete |
| DU-04 | Phase 4.3 | Complete |
| DU-05 | Phase 4.3 | Complete |
| DU-06 | Phase 4.3 | Complete |
| DU-07 | Phase 4.3 | Complete |
| DU-08 | Phase 4.3 | Complete |
| DU-09 | Phase 4.3 | Complete |
| DU-10 | Phase 4.3 | Complete |
| DU-11 | Phase 4.3 | Complete |
| DU-12 | Phase 4.3 | Complete |
| TA-01 | Phase 4.5 | Pending |
| TA-02 | Phase 4.5 | Pending |
| TA-03 | Phase 4.5 | Pending |
| TA-04 | Phase 4.5 | Pending |
| TA-05 | Phase 4.5 | Pending |
| TA-06 | Phase 4.5 | Pending |
| TA-07 | Phase 4.5 | Pending |
| TA-08 | Phase 4.5 | Pending |
| TA-09 | Phase 4.5 | Pending |
| LAUNCH-01 | Phase 5 | Pending |

| BE-01 | Phase 4.7 | Pending |
| BE-02 | Phase 4.7 | Pending |
| BE-03 | Phase 4.7 | Complete |
| BE-04 | Phase 4.7 | Complete |
| BE-05 | Phase 4.7 | Complete |
| BE-06 | Phase 4.7 | Complete |
| BE-07 | Phase 4.7 | Complete |
| BE-08 | Phase 4.7 | Complete |

| PIP-01 | Phase 6 | Complete |
| PIP-02 | Phase 6 | Complete |
| PIP-03 | Phase 6 | Complete |
| PIP-04 | Phase 6 | Complete |
| PIP-05 | Phase 6 | Complete |

**Coverage:**
- v1 requirements: 67 total
- Mapped to phases: 67/67
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-04-04 — TA-01 through TA-09 added for Phase 4.5 Training Analytics & Tools*
