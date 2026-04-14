# Phase 06: PiP Komplett-Rebuild - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te
**Areas discussed:** Layout-Aufteilung, Claude Streaming, Skript-Teleprompter, Transparenz-Regler

---

## Layout-Aufteilung

### Split-Typ

| Option | Description | Selected |
|--------|-------------|----------|
| Fester Split (empfohlen) | Obere Hälfte: KI+EWB, Untere Hälfte: Teleprompter. ~55/45. | ✓ |
| Resizable Split | Gleich, aber mit Drag-Divider | |
| Tabs beibehalten | Bestehende Tab-Navigation + Teleprompter als neuer Tab | |

**User's choice:** Fester Split
**Notes:** Einfach und vorhersagbar, passt zum schnellen Call-Workflow.

### KI-Bereich zwischen Einwänden

| Option | Description | Selected |
|--------|-------------|----------|
| Proaktive Tipps (empfohlen) | KI zeigt laufend Hinweise: Fragen, Phase, Score. Nie leer. | ✓ |
| Minimal — nur bei Einwänden | Nur EWB-Buttons und Phase/Score, KI-Text nur bei Einwand | |
| Du entscheidest | Claude wählt basierend auf bestehendem Output | |

**User's choice:** Proaktive Tipps
**Notes:** Bereich ist nie leer, zeigt immer kontextbezogenen Mehrwert.

### Setup-Flow

| Option | Description | Selected |
|--------|-------------|----------|
| 1:1 übernehmen (empfohlen) | Bestehender 3-Step Setup bleibt identisch | |
| Flow anpassen | Bestimmte Schritte ändern | ✓ |
| Du entscheidest | Claude behält was funktioniert | |

**User's choice:** Flow anpassen
**Notes:** Consent-Schritt verschoben von Setup IN den Live-Zustand. Meeting-Modus startet → PiP zeigt Consent-Vorlesetext → Stattgegeben = voller Meeting-Modus, Abgelehnt = Fallback Cold Call. Cold Call hat keinen Consent-Schritt.

### Consent-Screen

| Option | Description | Selected |
|--------|-------------|----------|
| Vorlesetext + 2 Buttons | PiP zeigt Consent-Satz groß + [Stattgegeben] / [Abgelehnt] | ✓ |
| Kompakter Consent-Banner | Schmaler Banner oben, Opener ausgegraut darunter | |

**User's choice:** Vorlesetext + 2 Buttons
**Notes:** Consent-Text geändert zu natürlichem Wortlaut: "digitale Notizen" statt "KI-Tool begleiten lassen". Text muss im Profil editierbar sein pro Berater.

### Rest-Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Ja, Rest bleibt (empfohlen) | Nur Consent verschiebt sich, 3 Setup-Steps bleiben | ✓ |
| Weitere Änderungen | Noch andere Anpassungen | |

**User's choice:** Rest bleibt wie 04.17

---

## Claude Streaming

### Streaming-Stil

| Option | Description | Selected |
|--------|-------------|----------|
| Wort-für-Wort (empfohlen) | Token-weise wie ChatGPT, blinkender Cursor | ✓ |
| Satz-weise | Ganzer Satz erscheint auf einmal, Satz für Satz | |
| Block-Update (Status quo) | Fertiger Text via WebSocket-Push statt Polling | |

**User's choice:** Wort-für-Wort
**Notes:** Maximaler Wow-Effekt im Sales-Tool-Markt.

### Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Nur PiP (empfohlen) | Haupt-Tab bleibt auf Polling | ✓ |
| Beides | PiP und Haupt-Tab | |
| Du entscheidest | Claude wählt | |

**User's choice:** Nur PiP

### Overlap-Verhalten

| Option | Description | Selected |
|--------|-------------|----------|
| Sofort ersetzen (empfohlen) | Neuer Hinweis unterbricht alten | |
| Queue — nacheinander | Alter Hinweis fertig, dann neuer | |
| Dual-Slot Kombination | 2 Slots mit intelligenter Ersetzungslogik | ✓ |

**User's choice:** Kombination — Dual-Slot-System
**Notes:** PiP hat immer 2 Antwort-Slots. Gleicher Kontext = Alternativen, neuer Kontext = separate Antworten, Themenwechsel = alles ersetzen. KI entscheidet Modus.

---

## Skript-Teleprompter

### Position-Erkennung

| Option | Description | Selected |
|--------|-------------|----------|
| Semantisch per KI (empfohlen) | Claude erkennt Phase aus Gesprächsverlauf | |
| Keyword-Matching | Gesprochene Wörter vs. Skript-Text | |
| Manuell | User scrollt/klickt selbst | |
| Kombination KI + Manuell | KI führt, manuelles Scrollen überschreibt | ✓ |

**User's choice:** Kombination — primär KI, manueller Override per Scroll
**Notes:** Manuelles Scrollen überschreibt KI-Position. Beim nächsten Audio-Chunk passt sich KI an die neue Position an.

### Inhalt

| Option | Description | Selected |
|--------|-------------|----------|
| Phasen + Stichpunkte | Kompakte Phasen-Übersicht mit Kernfragen | |
| Voller Skript-Text | Kompletter Text, wie echter Teleprompter | ✓ |
| Du entscheidest | Claude wählt basierend auf Profil-Daten | |

**User's choice:** Voller Skript-Text

### Datenquelle

| Option | Description | Selected |
|--------|-------------|----------|
| Bestehende Profil-Phasen | phasen-Array mit text/inhalt Feldern | |
| Neues Skript-Feld | Eigenes Freitext-Feld im Profil | |
| ProfileSkript-Tabelle | Neue Tabelle (heute gebaut), Auswahl im Setup-Dropdown | ✓ |

**User's choice:** ProfileSkript-Tabelle
**Notes:** Bestehende Profil-Phasen bleiben für KI-Phasenerkennung, Skript-Dropdown im Setup wählt den Teleprompter-Text.

### Highlighting

| Option | Description | Selected |
|--------|-------------|----------|
| Aktiver Block hell, Rest gedimmt | Volle Helligkeit + Teal-Akzent, Rest ~40% Opacity | ✓ |
| Scroll-Fokus ohne Dimming | Teal-Border links, kein Dimming | |
| Du entscheidest | Claude wählt passend zum Dark Theme | |

**User's choice:** Aktiver Block hell, Rest gedimmt

---

## Transparenz-Regler

### Steuerung

| Option | Description | Selected |
|--------|-------------|----------|
| Slider im Header (empfohlen) | Opacity-Slider im PiP-Header | ✓ |
| 3 Presets | Toggle-Button: 100% / 60% / 30% | |
| Hover-basiert | Semi-transparent im Ruhezustand, 100% bei Hover | |

**User's choice:** Slider im Header
**Notes:** WICHTIG: Slider steuert NUR Background-Layer (rgba). Schrift, Buttons, EWB-Buttons und KI-Hinweise bleiben IMMER bei 100% Opacity. Wert in localStorage gespeichert.

### Sichtbarkeit

| Option | Description | Selected |
|--------|-------------|----------|
| Nur im Live-Zustand (empfohlen) | Slider erst wenn Call läuft | ✓ |
| Immer verfügbar | Setup und Live | |
| Du entscheidest | Claude wählt | |

**User's choice:** Nur im Live-Zustand

---

## Claude's Discretion

- CSS-Implementierung der Background-Transparenz
- Slider-Design und Min/Max-Werte
- Streaming-Token-Batching
- Auto-Scroll-Verhalten und Timing
- Dual-Slot Layout-Details
- Consent-Text Profil-Feld Platzierung

## Deferred Ideas

None — discussion stayed within phase scope
