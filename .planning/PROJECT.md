# NERVE

## What This Is

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler im DACH-Markt. Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit und liefert Gegenargumente sowie Coaching-Tipps direkt auf den Bildschirm — unsichtbar für den Kunden. Ergänzend bietet NERVE einen KI-Trainingsmodus, eine Coach-Plattform für Teams und automatisierte Post-Call-Analysen.

**Status:** v0.9.5, Pre-Launch — Phase 4.2 complete (Cold Call/Meeting Modi live)
**Founder:** André Preuß, Iserlohn (Solo-Founder, Einzelunternehmer)

## Core Value

Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.

## Requirements

### Validated

<!-- Bereits gebaut und funktionsfähig (v0.9.4) -->

- ✓ Live-Einwandbehandlung mit 2 Gegenargumenten pro Einwand — existing
- ✓ Vorwand vs. echter Einwand Erkennung — existing
- ✓ Kaufbereitschafts-Tracking in Echtzeit (0-100%) — existing
- ✓ Sprachanalyse: Redeanteil, WPM, Monolog-Warnung — existing
- ✓ Quick-Action Buttons (Frage, Einwand, Übergang, Abschluss) — existing
- ✓ Phasen-Tracking (Einstieg → Bedarfsanalyse → Demo → Einwand → Closing) — existing
- ✓ Post-Call Analyse mit PDF-Download — existing
- ✓ CRM-Export: Automatische Gesprächsnotiz + Follow-up Email — existing
- ✓ DSGVO-Modus (Default AN) — existing
- ✓ Skript-Teleprompter mit Abdeckungs-Tracking — existing
- ✓ Kompakt-Modus (320px floating overlay, bottom-right) — validated Phase 03.2
- ✓ Light/Dark Mode Toggle mit System-Detection und DB-Persistenz — validated Phase 03.2
- ✓ Sidebar User Menu (Avatar + Dropdown) — validated Phase 03.2
- ✓ Globale Sprachpräferenz (DB-persistent, Training pre-selected) — validated Phase 03.2
- ✓ Trainingsmodus: KI-Kunde mit ElevenLabs-Stimme, 4 Schwierigkeitsstufen, 9 Sprachen, Scoring — existing
- ✓ Profil-System (12 Sektionen, 3 Demo-Profile) — existing
- ✓ Dashboard mit Gamification (Level, Achievements, Heatmap) — existing
- ✓ Coach-Plattform (Multi-Org, Methodik-Transfer) — existing
- ✓ Onboarding (5 Schritte) — existing
- ✓ Early Access Warteliste mit Referral-System — existing
- ✓ Rebranding SalesNerve → NERVE abgeschlossen (v0.9.1) — existing

### Active

<!-- Milestone 1: Launch — was noch gebaut werden muss -->

**Produktfixes (Prio 1)**
- [ ] Neues Pricing-System: 69/59/49 Flat-Rate + Fair-Use-Limits (1.000 Min Live, 50 Trainings/Monat) + ROI-Tracker im Dashboard
- [ ] Trainings-Modi: Frei (max Punkte, keine Hilfe) + Geführt (Hilfe mit Punktabzug)
- [ ] Post-Training Preview: "Was NERVE im echten Call gezeigt hätte" (Cross-Sell Live-Modus)
- [ ] 11 Standard-Trainingsszenarien (für alle Schwierigkeitsstufen)
- [ ] Live-Modus Fixes: Skript-Button, DSGVO-Banner, Kompakt-Modus Kreise, Toggle-Position
- [ ] Onboarding Verbesserungen: generische Placeholder, Dashboard-Stil Auswahl, Beispiel-Boxen
- [ ] Geführte Profil-Erstellung: 3-Schritte Wizard statt leeres Formular
- [ ] Profil-Editor Placeholder auf generisch (weg von Demo-Inhalten)
- [ ] SalesNerve → NERVE: Restliche Code-Stellen bereinigen

**Deployment & Launch (Prio 2)**
- [ ] Hetzner CX22 VPS einrichten und App deployen
- [ ] Domain sichern (nerve.sale, getnerve.io oder nerve.app)
- [ ] Stripe Payment Integration
- [ ] Impressum, AGB, Datenschutzerklärung (Deepgram, Anthropic, ElevenLabs als Auftragsverarbeiter)
- [ ] Early Access live schalten (50 Plätze, 50% Gründerrabatt)

**Business Setup (Prio 3)**
- [ ] Steuerberater count.tax kontaktieren
- [ ] Gewerbeanmeldung Gewerbeamt Iserlohn
- [ ] Geschäftskonto Kontist oder Finom
- [ ] USt-IdNr beim Bundeszentralamt beantragen

### Out of Scope

- Englische UI / US-Markt — erst Milestone 2, nach DACH-Validierung
- Eigenes TTS (Piper/Coqui) — erst Milestone 3 ab ~500 Kunden (größter Margenhebel)
- Eigene Sales-KI (fine-tuned Llama/Mistral) — erst Milestone 4
- Enterprise-Features (SSO, erweiterte Admin-Rechte) — zu früh
- Mobile App — kein Bedarf für Desktop-Tool
- Outbound-Calling / autonomes AI-Calling — andere Produktkategorie
- Trainings-Modus mit Live-NERVE-Antworten — würde Live-Assistenten entwerten

## Context

**Codebase:** Python Flask + Flask-SocketIO, Jinja2 + Vanilla JS, SQLite (PostgreSQL-kompatibel). Drei parallele Background-Threads für Audio-Transkription, KI-Analyse und Coaching-Delivery in Echtzeit. 12 Blueprints, 12 DB-Tabellen, 19 HTML-Templates. ~22k Zeilen app.py.

**APIs:** Deepgram Nova-2 (Live-STT), Anthropic Claude (Haiku für Live, Sonnet für Post-Call), ElevenLabs Multilingual v2 (TTS Training).

**Markt:** CloseAI (~380 User, DACH, schlechte Bewertungen), SalesEcho (US, DSGVO-Problem), Gong (Enterprise, Post-Call). Differenzierung: Live + DSGVO + Training + Coach-Plattform + transparente Preise.

**Finanzierung:** Bootstrap. Vestas-Gehalt (~65k/Jahr) finanziert Lebenshaltung. 14 Tage/Monat Offshore (Vestas), 14 Tage/Monat für NERVE.

**Ziel Milestone 1:** 50 zahlende Early-Access Kunden. GTM via LinkedIn (3x/Woche, André als Gesicht) + Direktansprache Sales-Teams.

## Constraints

- **Stack:** Kein Framework-Wechsel — Flask + Vanilla JS bleibt. Keine React-Migration.
- **Kosten Live:** Sonnet MUSS raus aus dem Live-Loop — nur Haiku für alles Live. Sonnet nur Post-Call.
- **DSGVO:** Pflicht von Tag 1 — Server in Deutschland (Hetzner), kein wörtliches Mitschneiden default.
- **Pricing:** Flat-Rate (nicht Credits) — Kunden wollen Planbarkeit. Kein harter Stopp bei Fair-Use.
- **Budget:** Bootstrap — kein externes Kapital. Reinvestition aller NERVE-Einnahmen.
- **Zeit:** Solo-Founder, ~14 Tage/Monat verfügbar.

## Key Decisions

| Entscheidung | Begründung | Outcome |
|---|---|---|
| Haiku für Live, Sonnet nur Post-Call | Halbiert Kosten, ausreichend für Echtzeit | — Pending |
| Flat-Rate 69/59/49€ statt Credits | Kunden wollen Planbarkeit, Produkt ist Premium | — Pending |
| Fair-Use statt hartem Block | Kein User soll im Arbeitstag gesperrt werden | — Pending |
| DSGVO-Modus default AN | Vertrauen als Differenzierungsmerkmal | — Pending |
| ElevenLabs bis 500 Kunden | Dann eigenes TTS als größter Margenhebel | — Pending |
| Deployment Hetzner CX22 (~4€/Monat) | Bootstrap-Budget, Server in DE für DSGVO | — Pending |
| US-Markt von Anfang an mitdenken | 16x größerer Markt, höhere Preise ($99 statt 69€) | — Pending |
| Alles reinvestieren, kein Gründergehalt | Bootstrap-Weg, Vestas deckt Lebenshaltung | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after Phase 03.2 (uat-bug-fixes) completion — 17 UAT issues resolved*

## Phase Completion Notes

**Phase 03.1 complete (2026-04-01):** NERVE Design System CSS foundation created (`static/nerve.css`, 684 lines). All 8 app templates migrated to NERVE dark-glass design language — `#06060a` background, Inter font, teal `#2dd4a8` primary, `.n-*` component classes. Gold `#E8B040` fully eliminated. 4 visual items require human verification (rendering, interactive flows).
