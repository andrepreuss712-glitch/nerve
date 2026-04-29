---
phase: 260429-dmd-faq-header-truncation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - static/profile_editor.js
  - static/nerve.css
autonomous: false
requirements:
  - POLISH-FAQ-HEADER-TRUNCATION
must_haves:
  truths:
    - "Im eingeklappten Zustand zeigt der FAQ-Card-Header die Frage NIEMALS abrupt mittendrin abgeschnitten — stattdessen sauber mit CSS-Ellipsis (…) am rechten Rand des Text-Bereichs."
    - "Buttons rechts (count × / trash / chevron) behalten ihren Platz und werden NICHT durch lange Fragen verdrängt oder umgebrochen."
    - "Hover über den Frage-Text zeigt einen nativen Browser-Tooltip mit dem vollständigen Wortlaut der Frage — ohne dass der User die Card aufklappen muss."
    - "Einwand-Cards (#einwaende-list) und Painpoint-Cards (#schmerz-list) zeigen dasselbe Truncation-Verhalten (Ellipsis + title-Tooltip), wenn der Text-Inhalt im Header zu lang wird."
  artifacts:
    - path: "static/profile_editor.js"
      provides: "FAQ-Render: full frage_muster in lbl.textContent (kein slice(0,40)) + title-Attribut auf .faq-lbl gesetzt; persistFaq aktualisiert beide Werte; Einwand/Painpoint analog falls Header-Preview-Text betroffen."
      contains: "lbl.title ="
    - path: "static/nerve.css"
      provides: "Geteilte Truncation-Regel auf .block-lbl bzw. einer neu eingeführten .block-lbl-truncate Modifier-Klasse: white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; flex:1. Plus .block-hd flex-Layout-Pflege: align-items:center; gap (bestehend); rechte Buttons flex-shrink:0."
      contains: "text-overflow: ellipsis"
  key_links:
    - from: "templates/profile_editor.html (#tpl-faq-row .faq-lbl)"
      to: "static/nerve.css (.block-lbl truncate styles)"
      via: "CSS-Klasse .block-lbl auf <span> im Header — ellipsis greift sobald Text breiter als verfügbarer Flex-Platz"
      pattern: "block-lbl"
    - from: "static/profile_editor.js (renderFaqRow)"
      to: "DOM .faq-lbl"
      via: "lbl.textContent = faq.frage_muster (vollständig, ohne slice) + lbl.title = faq.frage_muster"
      pattern: "lbl\\.title"
---

<objective>
Im FAQ-Card-Header (eingeklappter Zustand) wird der Fragetext aktuell hart bei Zeichen 40 via JS-`slice(0, 40)` abgeschnitten — Resultat: "Können wir das erstmal mit einem Vertrie" statt sauberer Ellipsis "Können wir das erstmal mit einem Vertrieb…". Buttons rechts (count, trash, chevron) sind dadurch zwar geschützt, aber die UX wirkt kaputt.

**Fix:** JS-Slice raus → vollen Text in `textContent` setzen → CSS-Ellipsis + flex-min-width:0 übernimmt das saubere Abschneiden visuell. Zusätzlich `title`-Attribut für nativen Hover-Tooltip mit voller Frage. Konsistenz-Check: dieselbe Truncation-Regel auf shared `.block-lbl` (oder via Modifier-Klasse) damit Einwand- und Painpoint-Cards bei langem Header-Inhalt das gleiche Verhalten haben.

Purpose: Polish — Profil-Editor Card-Header sollen bei jeder Inhalts-Länge sauber lesbar sein und volle Information per Hover liefern, ohne Klick-Aufwand zum Aufklappen.

Output: 2 geänderte Dateien (profile_editor.js + nerve.css), keine HTML-Template-Änderung nötig — bestehende `.block-lbl`/`.faq-lbl`/`.acc-chevron` Klassen reichen.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@CLAUDE.md
@.planning/STATE.md
@templates/profile_editor.html
@static/profile_editor.js
@static/nerve.css

<interfaces>
<!-- Bestehende Strukturen, die bereits da sind und unverändert bleiben (HTML-Template & generierte JS-DOM-Struktur). Nicht erfinden — nur darauf bauen. -->

FAQ-Header (templates/profile_editor.html Z. 495–502):
```html
<div class="block-hd faq-hd" style="cursor:pointer">
  <span class="block-lbl faq-lbl">Frage</span>
  <span class="faq-used-count faq-count" style="margin-left:auto;…">0×</span>
  <button class="btn-trash faq-delete" style="flex-shrink:0">…</button>
  <span class="acc-chevron" style="flex-shrink:0">▸</span>
</div>
```

Aktuelle Truncation-Bug-Quelle (static/profile_editor.js Z. 176):
```js
if (lbl && faq.frage_muster) lbl.textContent = faq.frage_muster.slice(0, 40) || 'Frage';
```

Einwand-Header (static/profile_editor.js Z. 963–968, JS-injected):
```html
<div class="block-hd" onclick="toggleEW(...)">
  <span class="block-lbl">Einwand N</span>
  <span class="einwand-preview">${kategorie}</span>
  <span class="acc-chevron" style="flex-shrink:0">▸</span>
  <button class="btn-trash" …>…</button>
</div>
```
Hinweis: `.einwand-preview` zeigt nur die Kategorie (kurz, max ~20 Zeichen) — Truncation hier unwahrscheinlich relevant. ABER: `.block-lbl` ("Einwand 1", "Einwand 2") braucht `flex-shrink:0` damit die Nummerierung nicht weggekürzt wird, falls preview lang ist.

Painpoint-Header (static/profile_editor.js Z. 889–893):
```html
<div class="block-hd" onclick="toggleBlock(...)">
  <span class="block-lbl">Painpoint N</span>
  <span class="acc-chevron" style="margin-left:auto;flex-shrink:0">▸</span>
  <button class="btn-trash" …>…</button>
</div>
```
Hinweis: Painpoint hat KEIN preview-Element im Header — nur den Index-Label. Truncation hier nicht nötig (Label ist immer kurz). KEINE Änderung nötig für Painpoints.

Bestehender CSS-Stand (static/nerve.css):
- Z. 178–184: `.block-hd` (display:flex, gap, align-items:center — bereits gesetzt im Schema; muss verifiziert werden via Read), `.block-hd-right`, `.einwand-preview { flex:1 }`
- Z. 849–854: `.acc-chevron { flex-shrink:0 }` — schon korrekt
- Z. 2751–2755: `.block-lbl { font-size:13px; font-weight:600 }` — KEIN truncation

Schlüssel-Regel: Konsistenz-Check ergab, Skripte/Opener/Erlaubnis/Pitch nutzen aktuell KEINE eigenen `.block`-Accordion-Header in `templates/profile_editor.html` — die Templates liegen woanders (Live-Loop / andere Sections) und sind NICHT Teil dieses Polish-Fixes. Nur FAQ ist akut betroffen, Einwand/Painpoint präventiv mit gleichem Pattern abgesichert.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: CSS — Shared Truncation auf .block-lbl + Header-Layout-Pflege</name>
  <files>static/nerve.css</files>
  <action>
Erweitere `static/nerve.css` an zwei Stellen:

1. **Bestehender `.block-lbl`-Block (~Z. 2751)** — Truncation-fähig machen, OHNE den Index-Label-Use-Case (Painpoint/Einwand-Numerierung) zu brechen. Lösung: NICHT `.block-lbl` selbst kürzen, sondern eine zusätzliche Modifier-Klasse einführen, die nur dort greift wo der Label volltextigen User-Inhalt enthält (FAQ-Frage). Füge direkt NACH dem bestehenden `.block-lbl`-Block ein:

```css
/* Truncation-Variante: für Header-Labels mit User-Inhalt (FAQ-Frage etc.).
   Nicht auf .block-lbl global, weil "Painpoint 1"/"Einwand 1"-Nummern-Labels
   nicht kürzen sollen. Aktiviert durch Doppelklasse .block-lbl.block-lbl--truncate
   oder durch konkrete Card-Klasse wie .faq-lbl. */
.block-lbl--truncate,
.faq-lbl {
  flex: 1 1 auto;
  min-width: 0;          /* damit flex-child überhaupt unter ihre intrinsische Breite schrumpfen darf — Kern-Trick für ellipsis im flexbox */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

2. **`.block-hd`-Block prüfen und absichern (~Z. 178)** — Stelle sicher dass Buttons rechts geschützt sind. Aktuelle Regel ist bereits `display:flex; align-items:center; gap` (verifiziert via Read). Füge — falls nicht vorhanden — eine schützende Regel hinzu, dass alle direkten Button/Chevron/Count-Children im Header per Default `flex-shrink:0` bekommen. Sicherheits-Pattern (idempotent, additiv):

```css
/* Header-Buttons & -Icons (chevron, trash, count) dürfen unter keinen Umständen
   geschrumpft oder umgebrochen werden — Truncation muss ausschließlich am Text-Label passieren. */
.block-hd > .acc-chevron,
.block-hd > .btn-trash,
.block-hd > .faq-used-count {
  flex-shrink: 0;
}
```

Position: direkt unter dem bestehenden `.block-hd`-Block. NICHT einfach pauschal `.block-hd > *` setzen, weil das `.einwand-preview` (das `flex:1` braucht) brechen würde.

Verifiziere VOR dem Edit per Read-Tool den exakten aktuellen Inhalt der relevanten Bereiche (`.block-hd`-Definition um Z. 178 und `.block-lbl` um Z. 2751), damit kein Bestehendes überschrieben wird.

Per CLAUDE.md UTF-8-Regel: User-facing Kommentar-Text in CSS darf Umlaute haben, aber CSS-Klassennamen MÜSSEN ASCII bleiben — `block-lbl--truncate` ist konform.
  </action>
  <verify>
    <automated>grep -n "block-lbl--truncate\|faq-lbl" static/nerve.css && grep -n "flex-shrink: 0" static/nerve.css | head -5</automated>
  </verify>
  <done>nerve.css enthält neue `.block-lbl--truncate, .faq-lbl`-Regel mit `min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1 1 auto`. Bestehende `.block-lbl`-Numerierungs-Regel ist unverändert. Header-Buttons/-Icons sind via additiver Regel `flex-shrink:0`-geschützt.</done>
</task>

<task type="auto">
  <name>Task 2: JS — slice(0,40) entfernen, vollen Text + title-Attribut setzen</name>
  <files>static/profile_editor.js</files>
  <action>
In `static/profile_editor.js`:

1. **renderFaqRow (Z. 173–176):** Ersetze die `.slice(0, 40)`-Truncation durch vollen Text + title-Attribut. Aktuell:

```js
var hd = row.querySelector('.faq-hd');
var lbl = row.querySelector('.faq-lbl');
if (hd) hd.title = faq.frage_muster || '';
if (lbl && faq.frage_muster) lbl.textContent = faq.frage_muster.slice(0, 40) || 'Frage';
```

Ändere zu:

```js
var hd = row.querySelector('.faq-hd');
var lbl = row.querySelector('.faq-lbl');
var fullFrage = (faq.frage_muster || '').trim();
if (lbl) {
  lbl.textContent = fullFrage || 'Frage';
  lbl.title = fullFrage;        // nativer Browser-Tooltip mit vollem Wortlaut bei Hover
}
if (hd) hd.title = '';            // bisheriger Tooltip auf Header-Container redundant — auf lbl ist präziser
```

Begründung Tooltip-Verschiebung: `.faq-hd` deckt den ganzen Header inkl. Buttons ab — Hover über trash/chevron würde sonst auch den Tooltip zeigen. Auf `.faq-lbl` ist die Hover-Zone präzise dort, wo der Text steht und gekürzt sein kann. Falls UX später entscheidet "Tooltip soll auch auf Header-Hover greifen", kann hd.title wieder rein — aktuell aber sauberer auf lbl.

2. **persistFaq (Z. 215–292) Live-Update:** Nach Inline-Edit der Frage soll der Header-Label sofort den neuen Text spiegeln. Aktuell macht persistFaq KEIN Update auf `.faq-lbl`. Suche das Ende des `frage`-Read-Blocks (kurz nach Z. 217–225, wo `frageEl`/`antwortEl` ausgelesen werden) und ergänze nach dem Validierungs-Check (kurz bevor der fetch losgeht):

```js
// Header-Preview live aktualisieren (sonst zeigt der eingeklappte Header alten Text bis Reload)
var lblLive = row.querySelector('.faq-lbl');
if (lblLive) {
  var liveTxt = (frageEl.value || '').trim();
  lblLive.textContent = liveTxt || 'Frage';
  lblLive.title = liveTxt;
}
```

Position: direkt nach den ersten Variablen-Reads (frageEl, antwortEl, kategorieEl) und VOR den Persistenz-Branches (`if (id) { ... fetch PUT ... } else { ... fetch POST ... }`).

3. **Skripte/Opener/Erlaubnis/Pitch:** Nicht in dieser Datei vorhanden — kein Touch nötig.

4. **Einwand-Cards (`addEinwand` Z. 956+):** Header-Label "Einwand N" ist Index, kein User-Inhalt → keine JS-Änderung. CSS in Task 1 hat hier keinen Effekt (greift nur auf `.block-lbl--truncate`/`.faq-lbl`).

5. **Painpoint-Cards (`addSchmerz` Z. 883+):** Header zeigt nur "Painpoint N" → keine JS-Änderung.

Per CLAUDE.md: User-facing Strings ("Frage") behalten Umlaute (hier keine), Code-Identifier ASCII (alle js-Variablen sind bereits ASCII).

Verifiziere VOR dem Edit per Read-Tool die exakten Zeilen-Bereiche (Z. 173–176 und Z. 215–230) — Einrückung und Var-Namen müssen exakt matchen für Edit.
  </action>
  <verify>
    <automated>grep -n "slice(0, 40)\|slice(0,40)" static/profile_editor.js; grep -n "lbl.title\s*=\s*fullFrage\|lblLive.textContent" static/profile_editor.js</automated>
  </verify>
  <done>`slice(0, 40)` ist komplett entfernt aus profile_editor.js. `lbl.textContent` bekommt vollen `frage_muster`-String. `lbl.title` ist mit demselben vollen String gesetzt. persistFaq aktualisiert `.faq-lbl` (textContent + title) live nach jedem blur/change. grep auf `slice(0, 40)` liefert keine Treffer mehr.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human-Verify — FAQ-Header in Browser prüfen</name>
  <what-built>FAQ-Card-Header zeigt jetzt sauberen Ellipsis-Text statt abrupten Cut bei Zeichen 40. Hover zeigt nativen Tooltip mit voller Frage. Buttons rechts (count, trash, chevron) bleiben fix.</what-built>
  <how-to-verify>
1. Flask-App lokal starten (`python app.py`) oder bestehenden Dev-Server nutzen.
2. Login → `/profiles` → FAQ-Section öffnen.
3. Eine FAQ mit langer Frage anlegen oder vorhandene editieren, z.B.: "Können wir das erstmal mit einem Vertriebler bei uns testen, bevor wir das Team-weit ausrollen?"
4. **Visuelle Prüfung (eingeklappt):**
   - Header zeigt am rechten Text-Rand SAUBERE drei Punkte `…` — KEIN abrupter Mitten-im-Wort-Cut
   - Buttons rechts (`0×`, Mülleimer, Chevron `▸`) sind alle vollständig sichtbar und an ihrer Position
5. **Hover-Tooltip:**
   - Maus über den Frage-Text-Bereich (NICHT über die Buttons) → nach ~1s erscheint nativer Browser-Tooltip mit der VOLLSTÄNDIGEN Frage
6. **Aufklappen:**
   - Klick auf Header → Card öffnet sich, Frage-Textarea zeigt vollen Text wie bisher (regression-check)
7. **Live-Edit:**
   - Frage in der Textarea ändern → Tab/Klick raus (blur)
   - Card einklappen → Header zeigt JETZT den neuen Text mit Ellipsis (vorher: alter Text bis Reload)
8. **Konsistenz-Check (sollte unverändert sein):**
   - Einwand-Cards: Header zeigt "Einwand 1 [Kategorie]" — keine Truncation/keine Regression
   - Painpoint-Cards: Header zeigt "Painpoint 1" — keine Regression
9. **Browser-DevTools Inspector** auf `.faq-lbl`: Computed-Style muss `text-overflow: ellipsis`, `overflow: hidden`, `white-space: nowrap`, `min-width: 0` enthalten.

Wenn alle Punkte ok → "approved" antworten. Bei Issues: Screenshot + Beschreibung.
  </how-to-verify>
  <resume-signal>Type "approved" oder beschreibe Issues</resume-signal>
</task>

</tasks>

<verification>
- `static/profile_editor.js` enthält KEIN `slice(0, 40)` mehr
- `static/nerve.css` enthält Truncation-Regel auf `.block-lbl--truncate, .faq-lbl` mit `min-width:0` (Flex-Ellipsis-Trick)
- Browser zeigt CSS-Ellipsis statt JS-Slice
- title-Attribut auf `.faq-lbl` zeigt vollen Wortlaut bei Hover
- Header-Layout: [Frage…ellipsis] [count×] [trash] [chevron] — Buttons fix, Text flexibel
- Einwand- und Painpoint-Cards unverändert (kein Regression)
</verification>

<success_criteria>
- Lange FAQ-Fragen werden im eingeklappten Header mit `…` (CSS-Ellipsis) terminiert, nie abrupt mittendrin
- Hover über Frage-Text zeigt vollen Wortlaut als nativen Browser-Tooltip
- Buttons rechts behalten in jedem Fall ihren Platz
- Live-Edit der Frage spiegelt sich sofort im eingeklappten Header (textContent + title)
- Keine Regression in Einwand-/Painpoint-Cards
- Human-verify checkpoint approved
</success_criteria>

<output>
Nach Approval: git commit auf main mit Message
`fix(profile-editor): faq header ellipsis + native tooltip statt slice(0,40)`
und git push origin main (per CLAUDE.md Git-Regel).
</output>
