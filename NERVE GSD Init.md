---
tags: [projekt, gsd]
status: aktiv
erstellt: 2026-03-30
hinweis: Diese Datei in C:\Users\andre\OneDrive\Desktop\salesnerve\ kopieren, dann in Claude Code: /gsd:new-project --auto @NERVE GSD Init.md
---

# NERVE — GSD Project Seed

## Was ist NERVE

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS). Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit, liefert Gegenargumente und Coaching-Tipps direkt auf den Bildschirm des Vertrieblers — unsichtbar für den Kunden. Zielgruppe sind B2B-Vertriebler, Sales-Teams und Sales-Coaches im DACH-Markt.

**Solo-Founder:** André Preuß, Iserlohn
**Status:** v0.9.4, Pre-Launch, Early Access vorbereitet
**Rechtsform:** Einzelunternehmer (→ UG/GmbH ab 3-5k€ MRR)

---

## Core Value

Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

---

## Tech Stack

- **Backend:** Python Flask + Flask-SocketIO
- **Frontend:** Jinja2 Templates + Vanilla JS
- **Datenbank:** SQLite (PostgreSQL-kompatible Struktur)
- **STT:** Deepgram Nova-2 (Live-WebSocket + REST)
- **KI:** Anthropic Claude API (Haiku für Live, Sonnet für Post-Call + Scoring)
- **TTS:** ElevenLabs Multilingual v2
- **Deployment:** Hetzner CX22 (~4€/Monat) — geplant
- **Fonts:** Playfair Display + DM Sans
- **Farben:** Gold #E8B040, Navy #0c0c18, Cream #f0ebe0

## Dateistruktur

```
salesnerve/
├── app.py (22k — Hauptanwendung, Blueprints, Seed-Daten, Migration)
├── config.py (API-Keys, Intervalle)
├── database/
│   ├── models.py (12 Tabellen)
│   └── db.py (SQLAlchemy Engine)
├── routes/ (12 Blueprints)
│   ├── app_routes.py, auth.py, changelog.py, coach.py
│   ├── dashboard.py, logs_routes.py, onboarding.py
│   ├── organisations.py, profiles.py, settings.py
│   ├── training.py, waitlist.py
├── services/
│   ├── claude_service.py, crm_service.py
│   ├── deepgram_service.py, live_session.py, training_service.py
├── static/app.js
└── templates/ (19 HTML-Templates)
```

---

## Was bereits gebaut ist (Validated)

- ✓ Live-Einwandbehandlung mit 2 Gegenargumenten pro Einwand
- ✓ Vorwand vs. echter Einwand Erkennung
- ✓ Kaufbereitschafts-Tracking in Echtzeit (0-100%)
- ✓ Sprachanalyse: Redeanteil, WPM, Monolog-Warnung
- ✓ Quick-Action Buttons (Frage, Einwand, Übergang, Abschluss)
- ✓ Phasen-Tracking (Einstieg → Bedarfsanalyse → Demo → Einwand → Closing)
- ✓ Post-Call Analyse mit PDF-Download
- ✓ CRM-Export: Automatische Gesprächsnotiz + Follow-up Email
- ✓ DSGVO-Modus (Default AN)
- ✓ Skript-Teleprompter mit Abdeckungs-Tracking
- ✓ Kompakt-Modus (380px floating Panel)
- ✓ Trainingsmodus: KI-Kunde mit ElevenLabs-Stimme
- ✓ 4 Schwierigkeitsstufen, 9 Sprachen, Scoring
- ✓ Profil-System (12 Sektionen, 3 Demo-Profile)
- ✓ Dashboard mit Gamification (Level, Achievements, Heatmap)
- ✓ Coach-Plattform (Multi-Org, Methodik-Transfer)
- ✓ Onboarding (5 Schritte)
- ✓ Early Access Warteliste mit Referral-System
- ✓ Rebranding SalesNerve → NERVE abgeschlossen (v0.9.1)

---

## Was als nächstes gebaut werden muss (Active — Milestone 1: Launch)

### Produktfixes (Prio 1)
- [ ] Neues Pricing-System: 69/59/49 Flat-Rate + Fair-Use-Limits (1.000 Min Live, 50 Trainings/Monat) + ROI-Tracker im Dashboard
- [ ] Trainings-Modi: Frei (max Punkte, keine Hilfe) + Geführt (Hilfe mit Punktabzug)
- [ ] Post-Training Preview: "Was NERVE im echten Call gezeigt hätte" (Cross-Sell Live-Modus)
- [ ] 11 Standard-Trainingsszenarien (für alle Schwierigkeitsstufen)
- [ ] Live-Modus Fixes: Skript-Button, DSGVO-Banner, Kompakt-Modus Kreise, Toggle-Position
- [ ] Onboarding Verbesserungen: generische Placeholder, Dashboard-Stil Auswahl, Beispiel-Boxen
- [ ] Geführte Profil-Erstellung: 3-Schritte Wizard statt leeres Formular
- [ ] Profil-Editor Placeholder auf generisch (weg von Demo-Inhalten)
- [ ] SalesNerve → NERVE: Restliche Stellen im Code bereinigen

### Deployment & Launch (Prio 2)
- [ ] Hetzner CX22 VPS einrichten und App deployen
- [ ] Domain sichern (nerve.sale, getnerve.io oder nerve.app prüfen)
- [ ] Stripe Payment Integration
- [ ] Impressum, AGB, Datenschutzerklärung (Deepgram, Anthropic, ElevenLabs als Auftragsverarbeiter)
- [ ] Early Access live schalten (50 Plätze, 50% Gründerrabatt)

### Business Setup (Prio 3)
- [ ] Steuerberater count.tax kontaktieren
- [ ] Gewerbeanmeldung Gewerbeamt Iserlohn (~20-40€)
- [ ] Geschäftskonto Kontist oder Finom
- [ ] USt-IdNr beim Bundeszentralamt beantragen

---

## Out of Scope (Milestone 1)

- Englische UI / US-Markt — erst Milestone 2, nach DACH-Validierung
- Eigenes TTS (Piper/Coqui) — erst Milestone 3 ab ~500 Kunden
- Eigene Sales-KI (fine-tuned Llama/Mistral) — erst Milestone 4
- Enterprise-Features (SSO, erweiterte Admin-Rechte) — zu früh
- Mobile App — kein Bedarf für Desktop-Tool
- Outbound-Calling / autonomes AI-Calling (andere Produktkategorie)

---

## Constraints

- **Budget:** Bootstrap — kein externes Kapital. Vestas-Gehalt (~65k/Jahr) finanziert Lebenshaltung, NERVE-Einnahmen werden reinvestiert.
- **Zeit:** Solo-Founder. 14 Tage/Monat Offshore (Vestas), 14 Tage/Monat für NERVE. Kein Team.
- **Kosten Live:** Sonnet MUSS raus aus dem Live-Loop. Nur Haiku für alles Live. Sonnet nur Post-Call.
- **DSGVO:** Pflicht von Tag 1. Server in Deutschland (Hetzner). Kein wörtliches Mitschneiden default.
- **Pricing:** Flat-Rate (nicht Credits) — Kunden wollen Planbarkeit. Kein harter Stopp bei Fair-Use.
- **Stack:** Kein Framework-Wechsel. Flask + Vanilla JS bleibt. Keine React-Migration.

---

## Key Decisions (bereits getroffen)

| Entscheidung | Begründung |
|--------------|------------|
| Haiku für Live, Sonnet nur Post-Call | Halbiert Kosten, ausreichend für Echtzeit |
| Flat-Rate statt Credits | Kunden wollen wissen was es kostet |
| Pricing 69/59/49 statt 39/34/29 | Produkt ist Premium, Preis muss passen |
| Fair-Use statt hartem Block | Kein User soll im Arbeitstag gesperrt werden |
| DSGVO-Modus default AN | Vertrauen als Differenzierungsmerkmal |
| Eigenes TTS erst ab 500 Kunden | ElevenLabs bis dahin, dann größter Margenhebel |
| Kein Modus 3 im Training (Live-Antworten) | Würde Live-Assistenten entwerten |
| Alles reinvestieren, kein Gehalt | Bootstrap-Weg, Vestas deckt Lebenshaltung |
| US-Markt von Anfang an mitdenken | 16x größerer Markt, höhere Preise ($99 statt 69€) |

---

## Wettbewerber

- **CloseAI** — Direkter Konkurrent, DACH, ~380 User, schlechte Bewertungen, kein Training, kein Coach-System
- **SalesEcho** — US-basiert, DSGVO-Problem, $1 Trial
- **Gong** — Enterprise, $100-150/User, Post-Call (nicht live), Big-Brother-Feeling
- **Differenzierung:** Live (nicht Post-Mortem) + DSGVO + Training + Coach-Plattform + transparente Preise

---

## Go-To-Market (Milestone 1)

- LinkedIn-Content 3x/Woche (André als Gesicht, kein AI-generiertes Material)
- Persönliches Netzwerk aktivieren
- Direktansprache Sales-Teams über LinkedIn
- Ziel: 50 zahlende Early-Access Kunden

---

## Finanzielle Projektion

- Durchschnitts-User: Kosten ~8€/Monat → **Marge 88%** bei 69€
- Konservativ (500 Kunden, Jahr 3): ~15.000€/Monat Gewinn netto
- Optimistisch (2.000 Kunden DACH+US, Jahr 3): ~112.000€/Monat Gewinn

---

*Dieses Dokument dient als GSD-Seed. Befehl: `/gsd:new-project --auto @"NERVE GSD Init.md"`*
*Erstellt: 2026-03-30 — Obsidian Vault Nerve-Vault*
