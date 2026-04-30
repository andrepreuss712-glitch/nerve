---
title: "CSS-Hotfix Phase 08.20.2 — Modal-Größe + Button-Look-Regression"
complexity: trivial
quick_task: true
files_modified:
  - templates/base.html
autonomous: true
---

<objective>
3 isolierte CSS-Fixes für den PiP-Launcher-Modal:

U1 — PreCall-Ergebnis-Modal (Step 4) läuft über Viewport: kein max-height auf dem Outer-Container.
U2 — Skript/Opener-Modal (Step 5) zu groß: max-height auf .launcher-opener-preview zu groß oder fehlender Outer-Constraint.
U3 — "Bearbeiten"/"Fertig"-Buttons in Step 5 sehen aus wie Plain-Text-Links (inline style in pip-launcher.js überschreibt kein Button-Styling, es fehlt schlicht — kein echter Regression, sie haben nie Button-Styling gehabt).

Alle 3 Fixes landen in der `<style>`-Sektion von `templates/base.html` (Zeilen 177–370).
Kein Backend, kein pip-launcher.js nötig.
</objective>

<context>
## Modal-Struktur (aus Codeanalyse)

**Outer Container (base.html L456):**
```html
<div id="launcherModal" class="nav-live-overlay">
  <div class="nav-live-box" style="max-width:640px" id="launcherModalBox">
    <div id="launcherContent" style="width:100%"></div>
  </div>
</div>
```

**Relevante CSS-Regeln in base.html `<style>` (alle Launcher-Styles sind hier, NICHT in nerve.css):**

- L180: `.nav-live-box` — `padding:44px 40px 36px; display:flex; flex-direction:column; align-items:center; gap:20px` — **kein max-height, kein overflow** → Ursache U1
- L331: `.launcher-step` — `width:100%; display:flex; flex-direction:column; gap:16px` — kein height-constraint
- L347: `.launcher-briefing-html` — `max-height:400px; overflow-y:auto` — eigene Scrollbar, Scroll-in-Scroll
- L368: `.launcher-opener-preview` — `max-height:100px; overflow-y:auto` — Step-5-Sektion
- L346: `.launcher-briefing` — `max-height:400px` auf textarea

**"Bearbeiten"/"Fertig"-Buttons (pip-launcher.js L581+592):**
```js
style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px"
```
Sie sind absichtlich als Inline-Text-Link gestylt. Das IST das Design aus Plan 08.20.
Kein CSS-Class → kein Stylesheet-Fix nötig. Fix: Klasse `launcher-btn-inline` hinzufügen + in CSS definieren ODER Inline-Style in JS upgraden auf echtes Button-Aussehen.
Entscheidung: CSS-only-Fix via neue Klasse `.launcher-inline-edit-btn` in base.html `<style>` + Klasse in pip-launcher.js ergänzen (minimaler JS-Touch, laut Constraint erlaubt).
</context>

<tasks>

<task type="auto">
  <name>U1 — PreCall-Modal (Step 4): Outer-Container max-height + Scroll-in-Scroll entfernen</name>
  <files>templates/base.html</files>
  <action>
**Ziel:** `.nav-live-box` bekommt `max-height: 90vh; overflow-y: auto;` damit der Modal-Container nie größer als der Viewport wird. Die per-Sektion-Scrollbar auf `.launcher-briefing-html` entfernen, damit nur eine Scrollbar existiert.

**Edit 1 — base.html L180:** `.nav-live-box`-Regel um `max-height:90vh; overflow-y:auto;` ergänzen.

Vorher:
```
.nav-live-box{background:var(--page-bg);border:1.5px solid var(--glass-border);border-radius:16px;padding:44px 40px 36px;position:relative;max-width:520px;width:90%;display:flex;flex-direction:column;align-items:center;gap:20px}
```
Nachher:
```
.nav-live-box{background:var(--page-bg);border:1.5px solid var(--glass-border);border-radius:16px;padding:44px 40px 36px;position:relative;max-width:520px;width:90%;max-height:90vh;overflow-y:auto;display:flex;flex-direction:column;align-items:center;gap:20px}
```

**Edit 2 — base.html L347:** `.launcher-briefing-html` — `max-height:400px; overflow-y:auto` entfernen (beide Properties), damit kein Scroll-in-Scroll.

Vorher:
```
.launcher-briefing-html{width:100%;padding:16px;border:1.5px solid var(--glass-border);border-radius:8px;background:var(--glass-bg);color:var(--page-text-color);font-size:13px;line-height:1.6;max-height:400px;overflow-y:auto;box-sizing:border-box}
```
Nachher:
```
.launcher-briefing-html{width:100%;padding:16px;border:1.5px solid var(--glass-border);border-radius:8px;background:var(--glass-bg);color:var(--page-text-color);font-size:13px;line-height:1.6;box-sizing:border-box}
```
  </action>
  <verify>
Browser: Launcher öffnen → Step 3 "Firma analysieren" → Analyse mit langem Ergebnis abwarten → Step 4 darf nicht über den Viewport-Rand ragen. Nur eine Scrollbar (auf dem Outer-Modal), kein Scroll-in-Scroll.
  </verify>
  <done>Step-4-Modal scrollt als Ganzes innerhalb 90vh. Kein innerer Scroll-Bereich auf .launcher-briefing-html.</done>
</task>

<task type="auto">
  <name>U2 — Step-5-Modal zu groß: Outer-Constraint greift bereits nach U1-Fix</name>
  <files>templates/base.html</files>
  <action>
**Analyse:** Step 5 rendert `.launcher-step` in `#launcherContent` inside `.nav-live-box`. Nach dem U1-Fix hat `.nav-live-box` bereits `max-height:90vh; overflow-y:auto`, was Step 5 genauso begrenzt.

Falls Step 5 dennoch zu groß bleibt (wegen langer Opener-/Skript-Vorschau), zusätzlich `.launcher-opener-preview` von `max-height:100px` auf `max-height:80px` reduzieren — dieser Wert war schon in L368 gesetzt, also nur Änderung der Zahl.

**Edit 1 (konditional, nur wenn nach U1 noch Problem besteht):**
base.html L368 `.launcher-opener-preview`: `max-height:100px` → `max-height:80px`

Falls U1 das Step-5-Problem bereits behebt, diesen Edit weglassen.

**Sicherheits-Override:** Direkt nach dem U1-Fix `.launcher-step` eine explizite `overflow-y:auto` geben, damit lange Step-Inhalte sicher scrollen:

base.html L331: `.launcher-step` — `overflow-y:auto` hinzufügen.

Vorher:
```
.launcher-step{width:100%;display:flex;flex-direction:column;gap:16px}
```
Nachher:
```
.launcher-step{width:100%;display:flex;flex-direction:column;gap:16px;overflow-y:auto}
```
  </action>
  <verify>
Browser: Step 5 öffnen mit mehreren Skripten + Opener-Einträgen. Modal-Box darf nicht über den Bildschirm ragen. Skript/Opener-Vorschauen sind scrollbar (eigene max-height), Modal selbst scrollt wenn nötig.
  </verify>
  <done>Step-5-Modal bleibt innerhalb 90vh. Kein Viewport-Overflow.</done>
</task>

<task type="auto">
  <name>U3 — "Bearbeiten"/"Fertig"-Buttons: echtes Button-Styling</name>
  <files>templates/base.html, static/pip-launcher.js</files>
  <action>
**Ursache:** Die Buttons `lnr-skript-edit-btn` und `lnr-opener-edit-btn` werden in pip-launcher.js (L581, L592) mit Inline-Style als Plain-Link gerendert (`background:none; border:none`). Sie haben keine CSS-Klasse die Button-Styling trägt.

**Fix (CSS-only, minimaler JS-Touch):**

**Step A — base.html `<style>`:** Neue Klasse nach L368 einfügen:
```css
.launcher-inline-edit-btn{font-size:11px;color:#00D4AA;background:rgba(0,212,170,0.08);border:1px solid rgba(0,212,170,0.3);border-radius:5px;cursor:pointer;padding:3px 8px;margin-top:2px;font-family:inherit;font-weight:600;transition:background .15s,border-color .15s}
.launcher-inline-edit-btn:hover{background:rgba(0,212,170,0.16);border-color:#00D4AA}
```

**Step B — pip-launcher.js L581:** Button-Tag um Klasse ergänzen, Inline-Style entfernen.

Vorher (L581):
```js
? '<button type="button" id="lnr-skript-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
```
Nachher:
```js
? '<button type="button" class="launcher-inline-edit-btn" id="lnr-skript-edit-btn">Bearbeiten</button>'
```

**Step C — pip-launcher.js L592:** Gleich wie Step B für den Opener-Button.

Vorher (L592):
```js
? '<button type="button" id="lnr-opener-edit-btn" style="font-size:11px;color:#00D4AA;background:none;border:none;cursor:pointer;padding:2px 0;margin-top:2px">Bearbeiten</button>'
```
Nachher:
```js
? '<button type="button" class="launcher-inline-edit-btn" id="lnr-opener-edit-btn">Bearbeiten</button>'
```

Hinweis: Der `textContent`-Wechsel zu "Fertig"/"Bearbeiten" (L707/L719 in `_wireInlineEdit`) bleibt unverändert — er betrifft nur den Label-Text, nicht das Styling.
  </action>
  <verify>
Browser: Step 5 öffnen → Skript und Opener mit Inhalt wählen → "Bearbeiten"-Button erscheint mit grünem Rahmen + Hintergrund (nicht als Plain-Text-Link). Klick auf Button wechselt zu Textarea + Label "Fertig". Klick auf "Fertig" zeigt wieder Preview + Label "Bearbeiten". Styling bleibt konsistent in beiden Zuständen.
  </verify>
  <done>"Bearbeiten"/"Fertig" sehen aus wie kleine Sekundär-Buttons (grüner Rahmen, leichter Hintergrund), nicht als unstyled Links.</done>
</task>

</tasks>

<verification>
Nach allen 3 Commits:
- [ ] Step 4 PreCall-Ergebnis scrollt als ganzes Modal, nicht intern — kein Viewport-Overflow
- [ ] Step 5 Skript/Opener bleibt in 90vh
- [ ] "Bearbeiten"/"Fertig" haben sichtbares Button-Styling
- [ ] Kein anderer Modal-Step (1, 2, 3, 4b) wurde visuell beeinträchtigt (smoke test)
</verification>

<success_criteria>
3 atomare Commits (U1, U2, U3). Kein Viewport-Overflow in Step 4 oder Step 5. "Bearbeiten"/"Fertig" haben Button-Look.
</success_criteria>

## Commit-Reihenfolge

```
fix(css): U1 PreCall-Modal max-height 90vh + remove scroll-in-scroll on launcher-briefing-html
fix(css): U2 launcher-step overflow-y:auto sichert Step-5-Containment
fix(css): U3 Bearbeiten/Fertig Buttons — launcher-inline-edit-btn Klasse + Styling
```
