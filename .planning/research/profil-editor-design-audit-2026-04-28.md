# Profil-Editor Design-Konsistenz-Audit

**Stand:** 2026-04-28
**Phase:** 08.19.2 — Profil-Editor UX + Design-Aufräumung
**Datei-Befund:** `templates/profile_editor.html` (in salesnerve-Repo)
**Andre-Aussage:** *"verschiedene Überschriften-Größen, mal eine Überschrift in teal — wirkt unaufgeräumt und amateurhaft"*

---

## TL;DR

15 Sektionen mit zwei klaren Doppelungen, einem Tippfehler, flacher Heading-Hierarchie, und 7 verschiedenen Text-Farben verteilt im Template. Visual-Drift sammelt sich seit Phase 04.x ohne dass jemand harmonisiert hat. Pre-existing-Schuld, kein 08.19-Regression.

---

## Aktuelle Sektions-Reihenfolge (Stand 2026-04-28)

| # | Sektion-Titel | Befund |
|---|---|---|
| 1 | Basis & Produkt | OK |
| 2 | **Gespraechsleitfaden** | ⚠️ **Tippfehler** (sollte: "Gesprächsleitfaden" mit ä) |
| 3 | Zielgruppe | OK |
| 4 | Schmerzpunkte & Trigger | OK |
| 5 | Gesprächsphasen | ⚠️ **Doppelt zu #2** (überlappende Funktionalität laut Andre) |
| 6 | Einwände | OK aber Sub-Felder unstrukturiert (siehe Andre-Befund) |
| 7 | **Häufige Fragen** | ⚠️ **Doppelt zu #14** (FAQ-Datenbank) |
| 8 | Kaufsignale | OK |
| 9 | No-Go Situationen | OK |
| 10 | Wettbewerber | OK |
| 11 | Verkaufstechniken | OK aber inhaltliche Frage: "wie kommt das in den Prompt?" (gehört zu 08.20) |
| 12 | Übergang-Ziele | OK aber inhaltliche Frage (gehört zu 08.20) |
| 13 | KI-Anweisungen | OK |
| 14 | **FAQ-Datenbank** | ⚠️ **Doppelt zu #7** |
| 15 | Tabu-Begriffe & Alternativen | OK |

**3 strukturelle Probleme:**
1. **Doppelung 1:** Häufige Fragen (#7) + FAQ-Datenbank (#14) = redundant. Konsolidieren auf eine Sektion.
2. **Doppelung 2:** Gesprächsleitfaden (#2) + Gesprächsphasen (#5) — laut Andre überlappend (Opener / Pitch / Erlaubnis vs. komplette Phasen mit Skript). Konsolidieren.
3. **Tippfehler:** "Gespraechsleitfaden" → "Gesprächsleitfaden"

---

## Heading-Hierarchie-Drift

Aktuelle Schrift-Größen-Verteilung:

| Element | Größe | Befund |
|---|---|---|
| Topbar-Name (Profil-Name oben) | 15px | Top-Level — OK |
| `.unsaved-title` (Modal) | 15px | OK |
| `.u-arrow` (Sortier-Pfeile) | 15px | OK |
| `.fi/.fs/.fta` (Inputs) | 13px | OK |
| `.topbar-branche` (Branche-Dropdown) | 13px | OK |
| `.save-btn` (Speichern-Button) | 13px | OK |
| `.crud-card input` | 13px | OK |
| `.slider-val` | 13px | OK |
| `.einwand-preview` | 12px | OK |
| `.sec-title` ⚠️ | **12px** | **Zu klein für Sektions-Heading!** Niedriger als Inputs (13px). Hierarchie-Verstoß |
| `.sec-link` (Sidebar-Eintrag) | 12px | OK |
| `.btn-add` | 12px | OK |
| `.t-label` (Slider-Label) | 12px | OK |
| `.crud-card textarea` | 12px | OK |
| `.faq-used-count` | 12px | OK |
| `.btn-rm` | 11px | OK |
| Skript-Bullets-Hint (inline) | 11px | OK |
| `.sec-num` (Sidebar-Number) | 10px | OK |
| `.block-lbl` (Block-Label) | 10px | OK |
| `.sec-title-num` (Number-Badge) | 10px | OK |
| `.col-header span` | 10px | OK |
| `.tip-icon` | 9px | OK |

**Kern-Befund: `.sec-title` ist 12px = kleiner als die Eingabefelder (13px).**

Das ergibt eine Hierarchie wo die **Sektions-Überschrift visuell schwächer** als die Eingaben darunter wirkt. Ist die Hauptursache für Andre's "unaufgeräumt"-Eindruck. Best-Practice: Section-Heading sollte 16-20px sein, deutlich über dem Input-Niveau.

**Soll-Hierarchie-Vorschlag:**
- Top-Level (Profil-Name): 18-20px
- Section-Heading (`.sec-title`): 16-18px **(aktuell 12px — zu erhöhen)**
- Block-Label / Card-Title: 13-14px
- Inputs: 13-14px
- Hint-Text / Sub-Label: 11-12px

---

## Farb-Drift im Template

Direkt im Template hardcodierte Farben (mind. 11 verschiedene):

| Farbe | Bedeutung | Verwendung |
|---|---|---|
| `#00D4AA` | NERVE-Teal-Akzent | Save-Button, Active-State, Section-Number-Badge, Slider, Tag-Chip, btn-add hover, Sidebar-Active |
| `#1a8a78` | Dark-Teal | Sidebar-Active-Number (sehr seltene Verwendung) |
| `#1a1a1a` | Dunkel-Schwarz | Topbar-Name, Unsaved-Title, fi-Text, Block-Label, Einwand-Preview, Crud-Card-Input, Col-Header |
| `#374151` | Mid-Grau | Unsaved-Btn-Leave |
| `#6B7280` | Mid-Grau-2 | Unsaved-Sub |
| `#22c55e` | Grün | Save-Toast |
| `#EF4444` | Rot | Crud-Card-Delete |
| `#e05c5c` | Rot-Akzent | Tag-Chip-Danger, Btn-Rm |
| `#4899c8` | Blau | Btn-Add (vor Hover) |
| `#CBD5E1` | Hellgrau-Border | Back-Link-Hover, Btn-Add-Border |
| `#E2E8F0` | Hellgrau-Border-2 | Diverse Borders |
| `#F0F2F5` | BG-Hover | Sec-Link-Hover, Unsaved-Btn-Leave |
| `#F8FAFC` | BG-Card | Editor-Sidebar, Btn-Ord, Crud-Card |
| `#FFFFFF` | Weiß | Topbar-Inputs, Unsaved-Box |

**Plus CSS-Variablen** (definiert wahrscheinlich in `base.html` oder `nerve.css`):
- `var(--page-bg)`, `var(--page-text-muted)`, `var(--page-text-secondary)`, `var(--page-text-color)`, `var(--input-border-focus)`, `var(--label-color)`

**Drift-Befund:** Dasselbe semantische Konzept (z.B. "Mid-Grau-Text") wird in 2-3 verschiedenen Hex-Werten durch das Template gestreut. Best-Practice: alle Text-Farben über CSS-Variablen, max 3-4 semantische Text-Hierarchien (primary/secondary/muted/disabled).

**Andre's "Überschrift in teal"-Befund:**
Wahrscheinlich die `.sec-title-num` (Number-Badge in Sektions-Heading) — die ist teal (`#00D4AA`) auf Light-Teal-Hintergrund. Wenn das Auge die Number-Badge als Teil der Heading wahrnimmt, wirkt die Heading "in teal" obwohl der Heading-Text selbst dunkel ist.

---

## Inline-Style-Drift im Template

Mindestens 8 Stellen wo Styles inline statt über Klassen gesetzt werden:

- Z. 260, 263: Save-Toast mit `font-size:13px;color:#22c55e` inline
- Z. 509, 537, 549, 561, 596: Col-Header mit `display:grid;grid-template-columns:...` inline (verschiedene Spalten-Konfigurationen, jede pro Sektion neu inline)
- Z. 515: Skript-Bullets-Hint mit `font-size:11px;color:var(--page-text-muted);margin:2px 0 6px 44px` inline
- Z. 637: FL-Desc inline-Style mit hardcoded Color-Fallback `#888`
- Z. 676: FAQ-Beschreibung inline
- Z. 711: faq-used-count inline mit `font-size:12px`
- Z. 925, 954, 996: Block-Label-Inline-Styles in JS-generierten Markup (`font-size:12px;color:#00D4AA;text-align:center` für Number-Badges in Schmerzpunkten/Einwänden)

**Drift-Risiko:** Inline-Styles override CSS-Klassen. Wenn man später die Klasse anpasst, wirkt es nicht überall. Best-Practice: Styles in CSS-Klassen, max 1-2 inline-Styles pro Datei für edge-cases.

---

## Inhaltliche Probleme die Andre genannt hat (gehört teilweise zu 08.19.2, teilweise zu 08.20)

### Frontend-Polish (08.19.2):

1. **`+Skript hinzufügen`-Button funktioniert nicht** — echter Bug, JS-Handler fehlt oder kaputt
2. **Opener mehrfach möglich, aber Erlaubnisfrage + Pitch nur 1×** — Inkonsistenz, sollten alle 3 mehrfach sein
3. **Übergänge: Rand zu dünn** — CSS-Polish (border-width erhöhen)
4. **Einwände-Sub-Felder unlogisch sortiert** — aktuell: Kategorie, Intensität, Kurzlabel, Einwandtext, Gegenargument, Technik. Logischer: Einwandtext (zentral) → Gegenargument → Technik → Metadaten (Kategorie, Kurzlabel, Intensität)
5. **"Intensität"-Feld unklar** — User versteht nicht was das bedeutet. Entweder Tooltip mit Erklärung oder entfernen
6. **Einwände-Eintrag ausklappbar** — Kollabierter Default mit nur Einwandtext sichtbar, expandiert für Bearbeitung

### Backend-Pipeline-Themen (08.20):

1. **Phasen werden nicht im PiP angezeigt + Scoring sagt "keine Gesprächsphasen erkannt"** — Phasen-Pipeline tot im Live-Modus
2. **Kaufsignale** — kommen aktuell nicht in den EWB-Prompt (08.17-Audit)
3. **Aktive Techniken (Verkaufstechniken)** — nicht im EWB-Prompt
4. **Übergangsziele** — nicht im EWB-Prompt

### Education-Hint (08.19.2 als Stub, ausgebaut in 08.22):

Pro Sektion ein 1-2-Satz-Hint der erklärt wie/wo das Feld wirkt. Andre's intuitive Frage "wie kommt das in den Prompt? wo ist der Mehrwert?" muss UI-mäßig beantwortet werden.

---

## Konkrete Implementations-Empfehlungen für 08.19.2

### Sektions-Reihenfolge-Vorschlag (UX-getrieben)

1. **Branche** (NEU oben — Foundation für Phase 08.22 Wisdom-Vorbefüllung)
2. **Basis & Produkt** (User-/Firmen-/Produkt-Stamm-Daten)
3. **Zielgruppe**
4. **Gesprächsleitfaden** (konsolidiert mit Gesprächsphasen — komplett-Verkaufsablauf)
5. **Einwände** (umstrukturiert + ausklappbar)
6. **Häufige Fragen / FAQ-Datenbank** (zusammengelegt)
7. **NoGos**
8. **Wettbewerber**
9. **Übergänge**
10. **Kaufsignale** (gehört zu Live-Coaching-Signalen)
11. **Verkaufstechniken**
12. **Schmerzpunkte & Trigger**
13. **Tabu-Begriffe & Alternativen**
14. **KI-Anweisungen** (am Ende — Meta-Settings)

(Reihenfolge muss durch UX-Recherche-Output validiert werden, das ist erste Approximation)

### Visual-Harmonisierung

- **`.sec-title` font-size: 16-18px** (von 12px)
- **`.sec-title` mit deutlicherem Bottom-Border** (von 1px auf 2px)
- **Sektions-Trennungen**: 32-40px Margin-Top zwischen Sektionen (statt aktuell weniger?)
- **Übergänge-Border**: von 1px auf 2px für bessere Sichtbarkeit
- **Inline-Styles eliminieren**: alle 8 Stellen in CSS-Klassen extrahieren
- **Hardcoded Farben durch CSS-Variablen ersetzen**: `--text-primary`, `--text-secondary`, `--text-muted`, `--accent-teal`, `--success-green`, `--danger-red`, `--info-blue`, `--border-light` etc.

### Bug-Fixes

- `+Skript hinzufügen`-Button-Handler reparieren (JS-Code suchen + fixen)
- Erlaubnisfrage + Pitch auf Multi-Entry erweitern (analog zu Opener-Sammlung)

### Tippfehler

- "Gespraechsleitfaden" → "Gesprächsleitfaden"

### Doppelungen auflösen

- "Häufige Fragen" + "FAQ-Datenbank" → eine Sektion
- "Gesprächsleitfaden" + "Gesprächsphasen" → konsolidiert mit klarer Sub-Struktur

### Education-Hints (Stub-Implementation in 08.19.2)

Pro Sektion ein <small>-Element direkt unter dem Heading mit 1-2 Sätzen zur Wirkung. Beispiel:
- Einwände: *"Diese Einwände werden vom Live-Coach erkannt — bei ähnlichen Formulierungen im Gespräch schlägt die KI das passende Gegenargument vor."*
- Tabu-Begriffe: *"Wörter die die KI im Live-Coaching aktiv vermeidet."*
- Kaufsignale (TODO 08.20): *"Aktuell noch nicht in Live-Pipeline integriert — kommt in Phase 08.20."* (bewusst Transparenz statt Vortäuschen)

### Branche-Sektion (NEU)

Erstes Element ganz oben. Aktuell ist `.topbar-branche` ein Dropdown im Header — sollte in die Sektion 1 wandern als großes Auswahl-Element. Mit Vorbefüllungs-Hint-Popup-Stub (Backend-Logik kommt in 08.22):

```
[Branchen-Auswahl]
ℹ️ Wir können dein Profil mit Best-Practice-Wisdom für deine Branche vorausfüllen.
   Das spart 1-2 Stunden Setup-Zeit. Du kannst alle Vorschläge anpassen.
   [Vorausfüllen verwenden] [Leer starten]
```

(In 08.19.2 nur das UI-Skelett. Funktional gefüllt in 08.22.)

---

## Cross-Verweis: UX-Best-Practice-Recherche (parallel)

Die parallele UX-Recherche (`profil-editor-ux-best-practices-2026-04-28.md`) liefert validierte Patterns aus B2B-SaaS-Tools (HubSpot, Salesforce, Notion, Outreach etc.) — die hier formulierten Reihenfolge-/Heading-/Inline-Hilfe-Empfehlungen müssen gegen die UX-Recherche-Findings abgeglichen werden bevor Plan-Phase startet.

Konflikte werden in Discuss-Phase 08.19.2 mit Andre geklärt.
