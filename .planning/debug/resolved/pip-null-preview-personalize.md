---
status: resolved
slug: pip-null-preview-personalize
trigger: "UAT-Round-2 nach Phase 08.19.5.6.1: 3 Folge-Bugs durch null-Default und R-04-Refactoring"
created: 2026-05-06T12:00:00Z
updated: 2026-05-06T13:00:00Z
phase_context: 08.19.5.6.1
files_suspected:
  - static/pip-launcher.js
---

# Debug Session: pip-null-preview-personalize

## Trigger

UAT-Round-2 nach Phase 08.19.5.6.1 + Regex-Hotfix (Commit 5542aba). Reihenfolge, "kein"-Option und Textanzeige sind jetzt grün, aber 3 Folge-Bugs entstanden durch null-Default + R-04-Refactoring.

## Symptoms

### Bug 1 — Preview-Text bei null-Selection sichtbar
Erwartet: leeres/Hint-Textfeld bei selectedXId === null.
Tatsächlich: Text vom ersten Item wird gräulich angezeigt.

### Bug 2 — Personalisierungs-API 400 bei null-Selection
POST /api/precall/personalize → 400 "opener_id muss eine positive Ganzzahl sein"
weil personalizeBtn5.onclick keinen Null-Guard hat.

### Bug 3 — Hardcoded "Skript wird personalisiert…" im Cold-Call-Modus
renderStep4b() Header ist statisch, Sub-Text spricht von "Opener". Mismatch.

## Current Focus

hypothesis: "Bestätigt — drei voneinander unabhängige Bugs in static/pip-launcher.js mit klar lokalisierten Fix-Stellen."
next_action: "Fixes anwenden in pip-launcher.js: (a) IIFE Zeile 1043-1050, (b) personalizeBtn5.onclick Zeile 1163-1176, (c) renderStep4b Zeile 522-527."

## Evidence

- timestamp: 2026-05-06T12:25:00Z — Read pip-launcher.js:1026-1051 (Tab-Switch Preview IIFE)
  Beobachtung: `var displayItem = item || items[0];` (Zeile 1045) verwendet bei `item === null`
  IMMER `items[0]` als Fallback und schreibt dessen `inhalt` in das Preview-Element (Zeile 1047).
  Der State `selectedXId` bleibt null, aber der DOM zeigt items[0].inhalt italic+muted.
  → Root-Cause Bug 1 BESTÄTIGT.

- timestamp: 2026-05-06T12:25:30Z — Read pip-launcher.js:1162-1177 (personalizeBtn5.onclick)
  Beobachtung: Handler liest selSelect.value in selectedSkriptId/selectedOpenerId (Zeile 1166-1172),
  setzt `state.briefingModus = 'C'; state.step = '4b'; renderStep();` OHNE null-Check.
  renderStep4b (Zeile 546-557) sendet dann fetch mit `state.selectedOpenerId` (kann null sein).
  Backend `/api/precall/personalize` rejected null mit 400.
  → Root-Cause Bug 2 BESTÄTIGT.

- timestamp: 2026-05-06T12:26:00Z — Read pip-launcher.js:514-534 (renderStep4b Header)
  Beobachtung: Zeile 524 hardcoded `'<div class="nav-live-title">Skript wird personalisiert…</div>'`.
  Zeile 526 hardcoded `'KI passt deinen Opener auf den Lead an (~5–10 Sekunden)'` —
  Header sagt "Skript", Sub-Text sagt "Opener" — beides müsste state.mode-abhängig sein.
  → Root-Cause Bug 3 BESTÄTIGT.

- timestamp: 2026-05-06T12:27:00Z — Geprüft: kein generisches Toast-Helper im Modul.
  Bestehendes Pattern für nicht-blockierende Inline-Fehler: `lnr-precall-error` (Zeile 274/318),
  `lnr-cap-error` (Zeile 771). Step 5 hat aber kein eigenes Error-Element. Einfachster
  konsistenter Fix: `alert(...)` wie bereits in Zeile 1563 (`'Mikrofon-Zugriff verweigert.'`).
  Alternative: neues `lnr-step5-error`-Div einfügen — Overhead nicht gerechtfertigt für
  einen Pflicht-Validierungs-Pfad.

## Eliminated

- Backend-Bug ausgeschlossen: 400-Response ist korrektes Verhalten (`opener_id muss eine positive Ganzzahl sein` ist eine valide Validierungs-Antwort). Frontend muss vor-validieren.
- Profil-Reset-Bug ausgeschlossen: `profileSel5.onchange` (Zeile 1071-1075) setzt korrekt alle 4 Selection-Variablen auf null. Die Bugs sind isoliert in den 3 genannten Stellen.

## Resolution

### Root-Cause-Zusammenfassung
Drei unabhängige Frontend-Bugs in `static/pip-launcher.js`, alle Folge des Phase-08.19.5.6.1-Refactorings (null-Default + R-04 Tab-Switch IIFE):

1. **Bug 1 — Preview-Fallback ignoriert null-State** (Zeile 1045):
   `var displayItem = item || items[0];` → fällt immer auf items[0] zurück, statt das Preview leer/Hint-Text zu lassen, wenn `selId === null`.

2. **Bug 2 — Fehlender Null-Guard vor Personalize-Fetch** (Zeile 1164-1176):
   `personalizeBtn5.onclick` ruft `renderStep()` mit `step='4b'` auf, ohne zu prüfen ob die modus-relevante Selection (selectedOpenerId bei Cold-Call, selectedSkriptId bei Meeting) gesetzt ist.

3. **Bug 3 — Hardcoded Header in renderStep4b** (Zeile 522-527):
   Header `'Skript wird personalisiert…'` und Sub-Text `'KI passt deinen Opener auf den Lead an'` sind fest verdrahtet — beide müssen state.mode-abhängig sein.

### Fix-Plan
**Fix 1 — Preview bei null leer/Hint statt items[0] (pip-launcher.js:1042-1050):**
```js
// Selektiertes Item anzeigen; wenn null → Preview-Element auf Hint-Text + muted-Style zurücksetzen.
var item = selId ? items.find(function (i) { return i.id === selId; }) : null;
if (item && item.inhalt) {
  previewEl.textContent = item.inhalt;
  previewEl.style.fontStyle = 'normal';
  previewEl.style.color = '';
} else {
  // Hint-Text passend zum Tab; State bleibt null per D-03
  var hint = tab === 'skript'    ? 'Skript auswählen für Vorschau'
           : tab === 'erlaubnis' ? 'Erlaubnisfrage auswählen für Vorschau'
           : tab === 'pitch'     ? 'Pitch auswählen für Vorschau'
           :                       'Opener auswählen für Vorschau';
  previewEl.textContent = hint;
  previewEl.style.fontStyle = 'italic';
  previewEl.style.color = 'var(--page-text-muted)';
}
```

**Fix 2 — Null-Guard in personalizeBtn5.onclick (pip-launcher.js:1163-1176):**
```js
if (personalizeBtn5) {
  personalizeBtn5.onclick = function () {
    // Modus-abhängig: Meeting → selectedSkriptId; Cold-Call → selectedOpenerId
    if (state.mode === 'meeting') {
      var skSel = document.getElementById('lnr-skript-select');
      if (skSel && skSel.value) state.selectedSkriptId = parseInt(skSel.value, 10) || null;
      if (!state.selectedSkriptId) {
        alert('Bitte erst ein Skript auswählen, bevor du personalisierst.');
        return;
      }
    } else {
      var opSel = document.getElementById('lnr-opener-select');
      if (opSel && opSel.value) state.selectedOpenerId = parseInt(opSel.value, 10) || null;
      if (!state.selectedOpenerId) {
        alert('Bitte erst einen Opener auswählen, bevor du personalisierst.');
        return;
      }
    }
    state.briefingModus = 'C';
    state.step = '4b';
    renderStep();
  };
}
```

**Fix 3 — Modus-abhängiger Header in renderStep4b (pip-launcher.js:522-527):**
```js
var isMeeting4b = state.mode === 'meeting';
var titleTxt   = isMeeting4b ? 'Skript wird personalisiert…' : 'Opener wird personalisiert…';
var subTxt     = isMeeting4b
  ? 'KI passt dein Skript auf den Lead an (~5–10 Sekunden)'
  : 'KI passt deinen Opener auf den Lead an (~5–10 Sekunden)';
c.innerHTML = [
  '<div class="launcher-step">',
  '<div class="nav-live-title">' + titleTxt + '</div>',
  '<div style="font-size:13px;color:var(--page-text-muted);margin-bottom:12px">',
  subTxt,
  '</div>',
  ...
].join('');
```

### specialist_hint
javascript / vanilla-js — keine spezialisierte Skill nötig (Stack: Flask + Vanilla JS, kein Framework).
Hint: `general` (Default-Engineering-Review optional, da Fixes mechanisch sind).

### Empfehlung
Goal `find_and_fix` aktiv → Fixes direkt anwenden.
