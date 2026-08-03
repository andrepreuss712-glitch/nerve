# NERVE

## What This Is

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler — **Markt: US-FIRST** (beschlossen 2026-07-04, siehe `Nerve-Vault/00 Vision.md`). Er hört Verkaufsgesprächen live zu, erkennt Einwände in Echtzeit und liefert Gegenargumente sowie Coaching-Tipps direkt auf den Bildschirm — unsichtbar für den Kunden. Ergänzend bietet NERVE einen KI-Trainingsmodus, eine Coach-Plattform für Teams und automatisierte Post-Call-Analysen.

**Status:** Pre-Launch, Early Access vorbereitet. ⚠ **KORRIGIERT 2026-08-03 — hier stand "Phase 04.3 complete (Design Unification, dark-only theme)". UEBERHOLT:** Das aktuelle Design ist **LIGHT-MODE** (siehe HART-Regel in `CLAUDE.md`). Diese Zeile haette bei der naechsten Generierung "dark-only" in eine Datei injiziert, deren eigene Regel Light-Mode vorschreibt.
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
- ✓ Light/Dark Mode Toggle mit System-Detection und DB-Persistenz — validated Phase 03.2 (removed in Phase 04.3: dark-only)
- ⚠ **UEBERHOLT (2026-08-03):** "Einheitliches dunkles Theme validated Phase 04.3" gilt NICHT mehr — das Design ist seither auf **LIGHT-MODE** umgestellt. Markenfarbe Teal `#00D4AA` bleibt, aber nie als Hex-Literal, immer ueber ein Token.
- ✓ Dashboard back-link im Live-Assistent Header — validated Phase 04.3
- ✓ Rechtliches Tab in Einstellungen — validated Phase 04.3
- ✓ Footer und Header-Email/Logout entfernt — validated Phase 04.3
- ✓ Sidebar User Menu (Avatar + Dropdown) — validated Phase 03.2
- ✓ Globale Sprachpräferenz (DB-persistent, Training pre-selected) — validated Phase 03.2
- ✓ Trainingsmodus: KI-Kunde mit ElevenLabs-Stimme, 4 Schwierigkeitsstufen, 9 Sprachen, Scoring — existing
- ✓ Profil-System (12 Sektionen, 3 Demo-Profile) — existing
- ✓ Dashboard mit Gamification (Level, Achievements, Heatmap) — existing
- ✓ Coach-Plattform (Multi-Org, Methodik-Transfer) — existing
- ✓ Onboarding (5 Schritte) — existing
- ✓ Early Access Warteliste mit Referral-System — existing
- ✓ Rebranding SalesNerve → NERVE abgeschlossen (v0.9.1) — existing
- ✓ Einheitliche Auswertungs-Seite: Training/Cold-Call/Meeting landen auf /session/<id> mit 13 Sektionen (11 Standard + Wendepunkt-Analyse + Einzel-Bewertungen + Verbesserungspotenzial), Training-Overlay entfernt, Nochmal-trainieren-Button, POLISH-32 Persönlichkeit-Badge + POLISH-34 Score-Dopplung — validated Phase 07.2 (3 UATs approved)
- ✓ EWB-Qualität & Profil-Tiefe (Phase 08, UAT approved 2026-04-23): v2-modular EWB-Pipeline live, A/B-Routing prompt_versions, 6 neue Profil-Felder (branche/branche_kontext/eigene_formulierungen/beweise/ton/zusatz) + 3-Block-Tooltip-System, PreCall-Anrede Du/Sie, 3-State-Rating-UI, EwbRating-Tabelle, Admin-EWB-Quality-Dashboard + Rating-Template-Page mit antwort_text-Spalte, Login-Redirect-next-Param global, CR-01/CR-02 Thread-Safety + Anrede-Whitelist — validated Phase 08 (waves 1-6 + gap-fix + hotfixes)

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

- ⚠ **UEBERHOLT (korrigiert 2026-08-03):** Hier stand "Englische UI / US-Markt — erst Milestone 2, nach DACH-Validierung". **Das Gegenteil gilt seit 2026-07-04: US-FIRST.** Englische Oberflaeche + US-Recht + US-Coaching-Inhalte sind **Launch-Blocker**, nicht Milestone 2. DACH ist offen und faellt nach dem US-Start.
- Eigenes TTS (Piper/Coqui) — erst Milestone 3 ab ~500 Kunden (größter Margenhebel)
- Eigene Sales-KI (fine-tuned Llama/Mistral) — erst Milestone 4
- Enterprise-Features (SSO, erweiterte Admin-Rechte) — zu früh
- Mobile App — kein Bedarf für Desktop-Tool
- Outbound-Calling / autonomes AI-Calling — andere Produktkategorie
- Trainings-Modus mit Live-NERVE-Antworten — würde Live-Assistenten entwerten

## Context

**Codebase:** Python Flask + Flask-SocketIO, Jinja2 + Vanilla JS, **PostgreSQL** (Umstellung von SQLite seit 12.05. durch, inkl. RLS). Parallele Hintergrund-Faeden fuer Transkription, KI-Analyse und Coaching. ⚠ **Zahlen 2026-08-03 am Code korrigiert:** 23 Blueprints (nicht 12), `app.py` ~2.571 Zeilen (nicht 22k — der alte Wert stammt aus der Zeit vor der Aufteilung in `routes/`). Eine `static/app.js` existiert NICHT (real: `admin_dashboard.js`, `audio-processor.js` u. a.).

**APIs:** Deepgram **nova-3** (Live-Spracherkennung; `nova-3-diarize` im Meeting-Modus — nicht mehr Nova-2), Anthropic Claude (**Sonnet 4.5 live seit 22.07.**, Haiku 4.5 fuer die schnelle Analyse), ElevenLabs (Sprachausgabe im Training).

**Markt (Wettbewerbs-Analyse Stand April 2026, aus der DACH-Zeit — ⚠ fuer US-first nicht neu erhoben):** CloseAI (~380 User, DACH), SalesEcho (US), Gong (Enterprise, Post-Call). Differenzierung: Live + Training + Coach-Plattform + transparente Preise + **"zeichnet nichts auf"** — Letzteres ist im US-Markt das staerkste Argument, weil aufzeichnende Werkzeuge in den Staaten mit Zustimmungspflicht aller Beteiligten den Kunden fragen muessen; NERVE im Kaltakquise-Modus nicht.

**Finanzierung:** Bootstrap. Vestas-Gehalt (~65k/Jahr) finanziert Lebenshaltung. 14 Tage/Monat Offshore (Vestas), 14 Tage/Monat für NERVE.

**Ziel Milestone 1:** 50 zahlende Early-Access Kunden. GTM via LinkedIn (3x/Woche, André als Gesicht) + Direktansprache Sales-Teams.

## Constraints

- **Stack:** Kein Framework-Wechsel — Flask + Vanilla JS bleibt. Keine React-Migration.
- **Kosten/Tempo Live:** ⚠ **KORRIGIERT 2026-08-03 — hier stand "Sonnet MUSS raus, nur Haiku fuer alles Live". UEBERHOLT und das Gegenteil der geltenden Vorgabe.** Es gilt: **Gleichgewicht aus Qualitaet UND Tempo** — schnell-aber-Muell ist genauso ein Dealbreaker wie gut-aber-langsam. Ambition: **das STARKE Modell schnell genug machen** (Zwischenspeicher, kleinere Prompts, Vorladen, lokales Sofortnetz), NICHT aufs schwache ausweichen. Sonnet 4.5 laeuft seit 22.07. live.
- **DSGVO:** Pflicht von Tag 1 — kein woertliches Mitschneiden default, **NIE Audio persistieren**, Call-Logs nie loeschen. ⚠ **KORRIGIERT 2026-08-03 — hier stand "Server in Deutschland (Hetzner)". Das war nie eine DSGVO-Anforderung** und steuerte nach dem US-first-Beschluss falsch: Server-Region folgt dem Markt (beim US-Umzug US-Region). DSGVO-Pflichten bleiben unabhaengig davon, weil Andre deutscher Einzelunternehmer ist.
- **Pricing:** Flat-Rate (nicht Credits) — Kunden wollen Planbarkeit. Kein harter Stopp bei Fair-Use.
- **Budget:** Bootstrap — kein externes Kapital. Reinvestition aller NERVE-Einnahmen.
- **Zeit:** Solo-Founder, ~14 Tage/Monat verfügbar.

## Key Decisions

| Entscheidung | Begründung | Outcome |
|---|---|---|
| ⚠ **UEBERHOLT:** "Haiku fuer Live, Sonnet nur Post-Call" | Galt bis Mitte 2026. **Seit 22.07. laeuft Sonnet 4.5 live** mit scharfem Zwischenspeicher. Es gilt das Gleichgewicht Qualitaet+Tempo: das STARKE Modell schnell genug machen, nicht aufs schwache ausweichen | — Ersetzt 2026-08-03 |
| Flat-Rate 69/59/49€ statt Credits | Kunden wollen Planbarkeit, Produkt ist Premium | — Pending |
| Fair-Use statt hartem Block | Kein User soll im Arbeitstag gesperrt werden | — Pending |
| DSGVO-Modus default AN | Vertrauen als Differenzierungsmerkmal | — Pending |
| ElevenLabs bis 500 Kunden | Dann eigenes TTS als größter Margenhebel | — Pending |
| Deployment Hetzner CX22 (~4€/Monat) | Bootstrap-Budget. ⚠ Begruendung "Server in DE fuer DSGVO" ist ueberholt (2026-08-03) — Region folgt dem Markt, Hetzner hat US-Standorte, kein Anbieterwechsel noetig | — Live |
| **US-FIRST statt "mitdenken"** | Beschlossen 2026-07-04: 16x groesserer Markt, hoehere Preise ($99 statt 69€), und "NERVE zeichnet nichts auf" ist in den US-Staaten mit Zustimmungspflicht aller Beteiligten ein SCHAERFERES Argument als in DACH | — Entschieden |
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
*Zuletzt inhaltlich korrigiert: 2026-08-03 — Markt (DACH → US-FIRST), Server-Region, Live-Modell-Vorgabe und Out-of-Scope-Eintrag berichtigt. Diese Datei stand drei Monate auf einem ueberholten Stand und speist den Projekt-Kopfblock in `CLAUDE.md`, der in JEDER Session geladen wird. ⚠ Bei Aenderungen an Markt, Region, Modell-Strategie oder Scope: **hier UND in `CLAUDE.md` nachziehen** — sonst ueberschreibt die naechste Generierung die Korrektur.*

*Vorheriger Stand — Last updated: 2026-04-27 after Phase 08.18 (Block N Phase B — Sales-Literatur-Research + Branchen-Spezifika) completion — 2 Research-Dokumente verfasst: sales-coaching-literatur-synthese.md (13 Autoren, 6 Sektionen, 20 Schema-Bullets für 08.19) + branchen-precall-spezifika.md (Top-10 DACH+USA, 3 Premium-Cluster Tiefe, 4 Mittel-Tiefen, Schema-Empfehlungen für precall_service.py in 08.20). Bereit für 08.19 Pydantic-Schema-Redesign.*

## Phase Completion Notes

**Phase 03.1 complete (2026-04-01):** NERVE Design System CSS foundation created (`static/nerve.css`, 684 lines). All 8 app templates migrated to NERVE dark-glass design language — `#06060a` background, Inter font, teal `#2dd4a8` primary, `.n-*` component classes. Gold `#E8B040` fully eliminated. 4 visual items require human verification (rendering, interactive flows).
