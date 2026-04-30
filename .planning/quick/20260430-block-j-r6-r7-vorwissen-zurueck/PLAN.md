---
title: "Block-J R6+R7: Vorwissen-Duplikat entfernen + Zurück-Navigation Step 5 fixen"
complexity: trivial   # R6 is trivial; R7 is mittel — using lower bound for combined plan
quick_task: true
file: static/pip-launcher.js
---

## Context

Step-Karte (relevant für beide Fixes):

| state.step | renderStep-Funktion | Anzeige |
|---|---|---|
| 1 | renderStep1 | Modus wählen |
| 2 | renderStep2 | PreCall-Option (Ja/Überspringen) |
| 3 | renderStep3 | PreCall-Formular |
| 4 | renderStep4 | PreCall-Ergebnis (Briefing) |
| 45 | renderStep4b | Standalone Vorwissen-Picker — DUPLIKAT (R6) |
| 5 | renderStep5 | Skript & Opener wählen (enthält bereits Vorwissen-Picker, Zeilen 601-608) |

State-Felder die für die Fixes relevant sind:
- `state.precallBriefing` — null wenn PreCall übersprungen, Objekt wenn Analyse gemacht
- `state.precallVerfuegbar` — true wenn Feature aktiviert (unabhängig von ob Analyse gemacht)
- `state.vorwissenLevel` — wird durch `_setVorwissen()` gesetzt, unabhängig von welchem Step

---

## Task 1: R6 — Standalone Vorwissen-Step entfernen (trivial)

**Datei:** `static/pip-launcher.js`

**Problem:** `renderStep4b()` (case 45, Zeilen 476-517) ist ein separater Modal-Step "Wie gut kennt der Lead euer Angebot?" der nach Step 4 erscheint. Step 5 hat denselben Vorwissen-Picker bereits eingebaut (Zeilen 601-608). Der Flow geht: Step 4 → Zurück drücken auf "Ergebnis übernehmen" → Step 45 → Step 5. Das ist ein doppelter Vorwissen-Schritt.

**Fix:** Einzige Änderung ist Zeile 470.

Zeile 470, vorher:
```javascript
      state.step = 45;
```

Zeile 470, nachher:
```javascript
      state.step = 5;
```

Das ist die onclick-Funktion des "Ergebnis übernehmen"-Buttons in `renderStep4()` (Zeilen 465-472). Mit dieser Änderung springt Step 4 direkt zu Step 5. `renderStep4b()` und `case 45` werden damit toter Code — sie können im gleichen Commit belassen werden (kein Laufzeitschaden), aber zur Sauberkeit werden sie auch entfernt.

**Ebenfalls entfernen (same commit, optional aber sauber):**
- Zeilen 153: `case 45: renderStep4b(); break;` aus dem switch in `renderStep()`
- Zeilen 475-517: die gesamte Funktion `renderStep4b()` inkl. Kommentar-Header

**Wichtig:** `_setVorwissen()` und `state.vorwissenLevel` bleiben unberührt — sie werden von Step 5 weiterhin verwendet.

**Verify:**
1. PiP-Launcher öffnen, Modus wählen, PreCall durchführen
2. "Ergebnis übernehmen" klicken → landet direkt in "Skript & Opener wählen" (Step 5)
3. Kein "Wie gut kennt der Lead euer Angebot?" Modal dazwischen

**Commit message:**
```
fix(pip-launcher): remove duplicate standalone Vorwissen step (R6)

Step 4 "Ergebnis übernehmen" now goes directly to Step 5 (Skript-Auswahl)
which already contains the Vorwissen picker. Removes redundant Step 4b modal.
renderStep4b() and case 45 removed as dead code.
```

---

## Task 2: R7 — Zurück-Navigation Step 5 auf Step 4 korrigieren (mittel)

**Datei:** `static/pip-launcher.js`

**Problem:** Der "Zurück"-Button in Step 5 (`renderStep5`, Zeilen 674-677):

```javascript
    document.getElementById('lnr-step5-back').onclick = function () {
      state.step = state.precallVerfuegbar ? 2 : 1;
      renderStep();
    };
```

Logik ist falsch: Wenn der User eine PreCall-Analyse gemacht hat (und jetzt Step 4 Ergebnis gesehen hat), sollte "Zurück" zurück zu Step 4 (Briefing-Ergebnis) gehen. Stattdessen geht er zu Step 2 (PreCall-Option-Frage).

**Korrekte Logik:**
- Wenn `state.precallBriefing` gesetzt ist (User hat Analyse durchgeführt und Ergebnis akzeptiert) → Step 4
- Wenn `state.precallBriefing === null` UND `state.precallVerfuegbar === true` (User hat PreCall übersprungen) → Step 2
- Wenn `state.precallVerfuegbar === false` (PreCall-Feature nicht aktiv) → Step 1

**Fix:** Zeilen 674-677, vorher:
```javascript
    document.getElementById('lnr-step5-back').onclick = function () {
      state.step = state.precallVerfuegbar ? 2 : 1;
      renderStep();
    };
```

Nachher:
```javascript
    document.getElementById('lnr-step5-back').onclick = function () {
      if (state.precallBriefing) {
        state.step = 4;
      } else if (state.precallVerfuegbar) {
        state.step = 2;
      } else {
        state.step = 1;
      }
      renderStep();
    };
```

**Edge-cases abgedeckt:**

| Zustand | Zurück-Ziel | Warum |
|---|---|---|
| `precallBriefing` gesetzt | Step 4 (Briefing-Ergebnis) | User kam von Step 4, soll dorthin zurück |
| `precallBriefing = null`, `precallVerfuegbar = true` | Step 2 (PreCall-Option) | User hat PreCall übersprungen |
| `precallVerfuegbar = false` | Step 1 (Modus-Wahl) | PreCall nicht verfügbar, direkt von Step 1 zu Step 5 |

**Verify:**
1. PreCall durchführen → Ergebnis übernehmen → in Step 5 "Zurück" → landet in Step 4 (Briefing)
2. PreCall überspringen (Step 2 "Überspringen") → in Step 5 "Zurück" → landet in Step 2
3. `precallVerfuegbar = false` (kein PreCall-Feature) → Step 1 → Modus-Wahl → Step 5 → "Zurück" → Step 1

**Commit message:**
```
fix(pip-launcher): fix Step 5 back-navigation to go to Step 4 when briefing exists (R7)

Back from Skript-Auswahl now goes to PreCall result (step 4) when a briefing
was accepted. Falls back to step 2 (PreCall option) when user skipped PreCall,
or step 1 when PreCall feature is unavailable.
```

---

## Ausführungsreihenfolge

Task 1 zuerst (da Task 1 die step-45-Referenz entfernt, die Task 2 nicht berührt — beide Tasks sind unabhängig voneinander, können aber der Reihe nach in einem Edit-Pass erledigt werden).

Beide Änderungen nur in `static/pip-launcher.js`. Kein anderer File betroffen.
