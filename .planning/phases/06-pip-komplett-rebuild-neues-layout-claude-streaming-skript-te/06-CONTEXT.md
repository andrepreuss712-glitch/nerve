# Phase 06: PiP Komplett-Rebuild — Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Kompletter Neuaufbau des PiP-Fensters: Neues Split-Layout (KI+EWB oben, Skript-Teleprompter unten), Claude-Wort-für-Wort-Streaming statt Polling, semantische Skript-Position-Erkennung mit manuellem Override, Transparenz-Regler (nur Background-Layer). Ersetzt den bestehenden PiP-Live-Code aus Phase 04.17 — Setup-Flow bleibt.

</domain>

<decisions>
## Implementation Decisions

### Layout-Aufteilung
- **D-01:** Fester Split ~55/45 im Live-Zustand: Obere Hälfte = KI-Hinweise + EWB-Buttons, untere Hälfte = Skript-Teleprompter. Kein Resizing, keine Tabs.
- **D-02:** KI-Bereich zeigt proaktive Tipps — nie leer. Zwischen Einwänden: kontextbezogene Frage-Vorschläge, Phase-Wechsel-Hinweise, Kaufbereitschafts-Trend (Phase, Score, Hinweis).
- **D-03:** Dual-Slot-System für KI-Antworten: 2 Antwort-Slots im oberen Bereich. Bei Frage/Einwand zeigen beide Slots Alternativen. Bei zweitem Einwand während Streaming: Slot 1 wird fertig gestreamt, Slot 2 beantwortet neue Frage. Bei komplettem Themenwechsel (z.B. Preis → Kein Bedarf): beide Slots werden ersetzt. KI entscheidet: gleicher Kontext = Alternativen, neuer Kontext = separate Antworten, Themenwechsel = alles ersetzen.

### Setup-Flow
- **D-04:** Setup-Flow bleibt wie Phase 04.17: Modus → Kundendaten → Profil/Skript → Start. Keine Änderungen an den 3 Setup-Steps selbst.
- **D-05:** Consent-Schritt verschoben aus dem Setup IN den Live-Zustand (nur Meeting-Modus). Nach Call-Start zeigt PiP als erstes den Consent-Vollbild-Screen mit Vorlesetext und zwei Buttons: [✅ Stattgegeben] → voller Meeting-Modus (KI hört beide), [❌ Abgelehnt] → Fallback auf Cold-Call-Modus (EWB-Buttons, KI hört nur Berater). Erst nach Consent erscheint Opener + reguläres Layout.
- **D-06:** Consent-Text ist natürlich formuliert, kein Technik-Jargon. Default: "Herr/Frau [Name], kurzer Hinweis — ich mache mir während unseres Gesprächs digitale Notizen. Ist das für Sie in Ordnung?" Text muss im Profil editierbar sein, damit jeder Berater seinen eigenen Wortlaut hinterlegen kann.
- **D-07:** Im Cold-Call-Modus gibt es keinen Consent-Schritt — direkt zum Opener.

### Claude Streaming
- **D-08:** Wort-für-Wort Streaming wie ChatGPT. Text erscheint Token für Token mit blinkemdem Cursor. Braucht WebSocket-Push vom Backend (Socket.IO Event statt 500ms Polling).
- **D-09:** Streaming gilt NUR für den PiP. Haupt-Tab `/live` bleibt auf bestehendem Polling. PiP wird das Premium-Erlebnis.
- **D-10:** Dual-Slot Ersetzungslogik (siehe D-03) steuert wie neue Streaming-Antworten mit laufenden interagieren.

### Skript-Teleprompter
- **D-11:** Teleprompter zeigt den vollen Skript-Text — nicht nur Phasen-Übersicht. User liest exakt den Wortlaut ab, wie ein echter Teleprompter.
- **D-12:** Datenquelle ist die ProfileSkript-Tabelle (neu gebaut). User wählt im Setup-Flow sein Skript aus dem Dropdown. Die bestehenden Profil-Phasen bleiben für die KI-Phasenerkennung, das ausgewählte Skript ist der Teleprompter-Text.
- **D-13:** Semantische Position-Erkennung per KI (skript_position im Claude-Response). KI erkennt aus dem Gesprächsverlauf, in welchem Skript-Abschnitt der User ist. Zusätzlich: manuelles Scrollen überschreibt die KI-Position. Beim nächsten Audio-Chunk passt sich die KI an die neue Position an. KI führt, User korrigiert wenn nötig.
- **D-14:** Visuelles Highlighting: Aktiver Skript-Block in voller Helligkeit + Teal-Akzent links. Vorherige und kommende Blöcke bei ~40% Opacity. Sanftes Auto-Scroll zur aktiven Position.

### Transparenz-Regler
- **D-15:** Opacity-Slider im PiP-Header, nur im Live-Zustand sichtbar (nicht im Setup).
- **D-16:** WICHTIG: Slider steuert NUR den Background-Layer (rgba auf Hintergrund). Schrift, Buttons, EWB-Buttons und KI-Hinweise bleiben IMMER bei voller Opacity (100%). Vertriebler muss alles ablesen können, egal wie transparent der Hintergrund ist.
- **D-17:** Transparenz-Wert wird in localStorage gespeichert und beim nächsten PiP-Start wiederhergestellt.

### Claude's Discretion
- Exact CSS-Implementierung der Background-Transparenz (welche Layer, rgba vs. backdrop)
- Slider-Design und Interaktion (Range-Input, Custom-Slider, Min/Max-Werte)
- Streaming-Token-Batching (wie viele Tokens pro WebSocket-Event)
- Auto-Scroll-Verhalten und Timing (Easing, Debounce)
- Dual-Slot Layout-Details (Spacing, Trenner, Animation bei Slot-Wechsel)
- Consent-Text Profil-Feld Name und Platzierung im Profil-Editor

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bestehende PiP-Implementierung (wird teilweise ersetzt)
- `static/app.js` (ab Zeile 1416) — PiP State Machine, Setup-Flow, openPipWindow(), Tab-System (Tabs werden durch Split ersetzt)
- `templates/app.html` (ab Zeile 909) — PiP HTML-Content (#pip-window), CSS-Styles (werden neu gebaut)
- `static/nerve.css` — Design-System CSS-Variablen (--page-bg, --glass-border, etc.)

### PiP Launcher Briefing (Phase 04.17)
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE PiP Launcher.md` — Ursprüngliches Briefing: User Flow, Technische Architektur, Design-Spezifikation

### Abhängige Module
- `services/live_session.py` — Session State Management, set_active_profile()
- `services/claude_service.py` — Analyse-Loop, Coaching-Loop (braucht Streaming-Erweiterung für PiP)
- `services/precall_service.py` — PreCall-Recherche Button im Setup
- `routes/app_routes.py` — /live Route, Session-Start API Endpoints

### Neue Datenquellen
- ProfileSkript-Tabelle (heute gebaut) — Datenquelle für Teleprompter-Text
- Profil-Consent-Text-Feld — Editierbarer Consent-Vorlesetext pro Profil

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `openPipWindow()` in app.js:1843 — Document PiP API Wrapper, CSS-Loading, pagehide cleanup. Wird beibehalten.
- Setup-Flow Funktionen (pipStartSetup, showPipSetupStep, pipPopulateProfiles, pipPopulateKundendatenHistory) — bleiben 1:1
- `getPipElement(id)` Helper — PiP-Window-First Lookup, bleibt
- Shared Reference Pattern (`pipWindow.nerveApp = { socket, ... }`) — bewährt, bleibt

### Wird ersetzt
- Tab-State-Machine (handlePipTabClick, setPipTabFromKI, activatePipTab) → Split-Layout
- `updatePipFromErgebnis()` / `updatePipFromCoaching()` → Dual-Slot Streaming-Renderer
- 500ms Polling für Ergebnisse → WebSocket-Push mit Token-Streaming
- Bestehende PiP-CSS in app.html → Neues Split-Layout CSS

### Established Patterns
- PiP content lebt in `#pip-window` div in app.html, moved via appendChild
- `window._pipWindow` / `window._pipState` für State Management
- Socket.IO Events für Echtzeit-Kommunikation (transcript, coaching)

### Integration Points
- Claude-Service braucht Streaming-Modus: `stream=True` bei Anthropic API, Token-Events via Socket.IO ans Frontend
- ProfileSkript-Dropdown im Setup-Step 3 (Skript-Auswahl)
- Consent-Text aus Profil-Daten laden beim Meeting-Modus Start
- skript_position als neues Feld im Claude-Response für Teleprompter-Sync

</code_context>

<specifics>
## Specific Ideas

- Consent-Text Default: "Herr/Frau [Name], kurzer Hinweis — ich mache mir während unseres Gesprächs digitale Notizen. Ist das für Sie in Ordnung?" — natürlich, keine Rückfragen provozierend, rechtlich abdeckend
- "NERVE ist nicht mehr eine weitere App die ich offen haben muss, sondern ein unsichtbarer Begleiter" — PiP schwebt transparent über CRM/Outlook
- Teleprompter-Effekt: Wie ein echter TV-Teleprompter — voller Text, aktuelle Stelle leuchtet, Rest gedimmt
- Streaming-Effekt: Wie ChatGPT, Wort-für-Wort mit Cursor — maximaler Wow-Effekt im Sales-Tool-Markt
- Dual-Slot KI: Nie nur eine Antwort — immer Alternativen oder kontextuelle Ergänzungen

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te*
*Context gathered: 2026-04-14*
