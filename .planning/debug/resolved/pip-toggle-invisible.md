---
status: resolved
trigger: '"Transkript ▶"-Knopf erscheint NICHT im PiP während eines Live-Calls (deployed, getnerve.app). Phase 08.23.2.D.UX.2 Plan 04.'
created: 2026-06-03
updated: 2026-06-03
---

# Debug: PiP "Transkript ▶"-Toggle erscheint nicht

## Symptoms
- **Expected:** Im Live-Call-PiP erscheint oben rechts im Header ein "Transkript ▶"-Knopf.
- **Actual:** Kein Knopf sichtbar.
- **When:** Seit Phase 08.23.2.D.UX.2 Plan 04 (Feature neu, nie sichtbar gewesen).
- **Repro:** Live-Call starten → PiP öffnet → Header zeigt Mode-Badge + Timer + Mic + Beenden, aber keinen Transkript-Knopf.

## Hypothesen (André)
1. Wird `_wireTranscriptToggle` überhaupt aufgerufen? → **WIDERLEGT**
2. Enthält `state.pipWindow.document` wirklich `.pip-header-right`? → **WIDERLEGT**

## Investigation (statisch, Code-Lesen — Diagnose ohne Browser möglich)

Hinweis-Korrektur: `inspect.sh logs` liest **Server**-Logs (gunicorn). Der Toggle ist
**client-side JS** → Browser-`console.log` landet NIE in inspect.sh. Logging-first hier =
Browser-DevTools ODER statische DOM-Lifecycle-Analyse (read-only, kein Local-Dev-Verstoß).

### Evidence
- `pip-launcher.js:4019-4038` `_wireTranscriptToggle`: erzeugt Button, `headerRight = doc.querySelector('.pip-header-right')`, early-return nur wenn nicht gefunden.
- `pip-launcher.js` `_setupPipWindow`: ruft `_wireTranscriptToggle(pipWindow)` NACH `_initPipLive()` auf → **Funktion wird aufgerufen** (H1 widerlegt).
- `pip-launcher.js:~1734` `_setupPipWindow`: `pipWindow.document.body.appendChild(liveWin)` **VERSCHIEBT** den echten `#pip-live-window`-Knoten (der `.pip-header-right` enthält, base.html:474-491) in das PiP-Dokument — kein Clone. → `querySelector('.pip-header-right')` im PiP-Doc **findet ihn** (H2 widerlegt).
- `_initPipLive` (endet :2199) togglet nur `style.display`, baut den Header NICHT neu → Button wird nicht clobbered.
- `base.html:204` `.pip-header { background:#0D1117 }` (fast-schwarz).
- `nerve.css:593` `.n-btn-ghost { color:var(--btn-ghost-text); background:var(--btn-ghost-bg); border:1.5px solid var(--btn-ghost-border); }`.
- `nerve.css:76-79` Light-Mode-Tokens: `--btn-ghost-text:#1a1a1a`, `--btn-ghost-bg:rgba(0,0,0,0.04)`, `--btn-ghost-border:rgba(0,0,0,0.12)`.
- `base.html:287` Geschwister-Knopf `.pip-btn-beenden`: explizites Dark-Header-Styling (transparent bg, farbiger Border/Text, kompaktes Pill). `.pip-mic-indicator` (base.html:254) ebenso teal/explizit.

## Root Cause
Der Knopf WIRD injiziert und IST im DOM — aber er nutzt die Light-Mode-Klasse `.n-btn n-btn-ghost`
(Text `#1a1a1a`, bg `rgba(0,0,0,.04)`, border `rgba(0,0,0,.12)` — alle fast-schwarz) auf dem
fast-schwarzen `#0D1117` PiP-Header → **dark-on-dark, komplett unsichtbar**. Die App ist seit
Phase 4.4 Light-Mode; die generische Ghost-Klasse ist nur für helle Flächen gedacht. Alle anderen
Header-Controls nutzen deshalb bespoke Dark-Header-Styles mit expliziten Farben.

## Fix
`_wireTranscriptToggle`: `.n-btn n-btn-ghost`-Klasse entfernt, durch explizites kompaktes
Dark-Header-Styling ersetzt (transparent bg, **teal** Border + Text `#00D4AA` wie Mode-Badge/Mic,
Pill-Radius, 12px, padding 2px 10px). Lucide-Icon entfernt (Text-only "Transkript ▶"/"◀" —
vermeidet 24px-SVG-im-36px-Header + Icon-Lade-Timing). Open/Close-Label-Updates ebenfalls text-only.
Inline-Styles → robust unabhängig von den injizierten Stylesheet-Tokens.

## Verification
- node --check pip-launcher.js OK.
- greps 'Transkript ▶'/'Transkript ◀' weiterhin present (Acceptance unverändert).
- **Production-Confirm (André):** deploy + Live-Call → teal "Transkript ▶" sichtbar oben rechts;
  Klick → side-by-side. DevTools-Gegenprobe: `#pip-transcript-toggle` war schon vorher im
  `.pip-header-right` (computed color #1a1a1a) — bestätigt dark-on-dark.

## files_changed
- static/pip-launcher.js (_wireTranscriptToggle Styling + Label-Updates)
