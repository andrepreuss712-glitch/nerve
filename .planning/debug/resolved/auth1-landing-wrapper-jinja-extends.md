---
status: resolved
trigger: "AUTH-1 Plan 01: window.fetch-Wrapper in templates/marketing/landing.html KAPUTT ausgeliefert (Prod-Regression, live via curl verifiziert) — <script> vor <html>, head verschluckt, nichts klickbar; nur landing.html betroffen, base.html-Seiten sauber."
created: 2026-07-05
updated: 2026-07-05
resolved: 2026-07-05
phase: 08.23.2.AUTH-1
plan: "01"
---

# Debug: landing.html Wrapper KAPUTT — Jinja verarbeitet {% extends %} im JS-Kommentar

## Symptome
- `curl https://getnerve.app/`: geöffnetes `<script>` VOR `<html>`, nie sauber geschlossen; danach direkt `<html lang="de">`. Browser frisst den kompletten `<head>` (inkl. eines ZWEITEN Wrapper-Blocks) als ungültigen Script-Text → kein Wrapper läuft, Struktur zerschossen, nichts klickbar.
- base.html-Seiten (/datenschutz, /agb, /impressum) SAUBER — nur landing.html betroffen.
- Der Server-E2E-Test `test_register_flow_with_csrf` war GRÜN (Meta-Tag erschien trotzdem → register 200).

## Root Cause (bewiesen)
`templates/marketing/landing.html` (standalone, kein base.html-Erbe) trug im **JS-Kommentar** des Wrapper-Blocks den Literal-Text `{% extends 'base.html' %}` (Zeile 12, eingefügt in Commit 7fa8ea2, Plan 01 Task 2).

**Jinja2 verarbeitet Template-Tags zur Render-Zeit UNABHÄNGIG vom HTML-/JS-Kommentar-Kontext** (Jinja läuft VOR der HTML-Analyse). Das verirrte `{% extends 'base.html' %}` liess Jinja landing.html fälschlich von base.html erben → gemischte/zerschossene Ausgabe: Wrapper-`<script>` vor `<html>`, head verschluckt, base.html-Wrapper zusätzlich gezogen (= das „Doppel").

**Warum nur landing.html:** base.html's Wrapper-Kommentar enthält KEIN `{% extends %}` (anderer Kommentar-Text) → base.html unbetroffen. Grep-belegt.

**Warum der E2E-Test grün war:** durch die fälschliche Vererbung rendert base.html sein `<meta name="csrf-token" content="{{ csrf_token() }}">` → der server-seitige Regex-Scan fand das Token → register 200 → grün. Der Test deckt nur Server-Verhalten, nicht die ausgelieferte HTML-Struktur.

## Fix (angewandt, deploy-gate-Verifikation ausstehend — André fährt)
1. `templates/marketing/landing.html` Zeile 12: `{% extends 'base.html' %}` aus dem Kommentar entfernt → „erbt NICHT von base.html"; Warn-Kommentar ergänzt (kein Jinja-Tag-Syntax in Kommentaren).
2. Struktur-Wächter `tests/test_signup_journey.py::test_landing_renders_valid_structure` ergänzt — prüft die **ausgelieferte** Struktur (nicht String-Präsenz): (a) `<html>` steht VOR jedem `<script>`, (b) genau EIN `window.fetch =`-Wrapper ausgeliefert. Fängt genau diese Regressions-Klasse (Jinja-Tag im Quelltext → script-vor-html / Doppel-Wrapper).

## Verifikation (Deploy-Gate B-fix, André) — RESOLVED 2026-07-05
- `bash deploy.sh production`: **886 passed** inkl. `test_landing_renders_valid_structure` + `test_register_flow_with_csrf`; Dienst neu gestartet, live deployed.
- `curl https://getnerve.app/`: Ausgabe beginnt `<!DOCTYPE html>`/`<html>`/`<head>`, KEIN `<script>` davor, `window.fetch`-Wrapper genau 1× sauber im head geschlossen, `<meta name="csrf-token">` echtes DOM-Element. Startseite 200 / /login 302.
- Browser (André, Inkognito): Startseite klickbar (nicht mehr tot), Login-Modal öffnet, Register-Wizard 1→2→3 → Absenden erreicht Server ("E-Mail bereits registriert" = Durchkommen, vor Fix war es 400). Wrapper hängt Token korrekt an.

## Files Changed
- templates/marketing/landing.html
- tests/test_signup_journey.py
