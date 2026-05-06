---
status: resolved
trigger: "Doppel-Save-Bug bei Personalisieren — User klickt einmal auf 'Personalisiert nutzen + Call', Backend bekommt zwei POST /api/precall/personalize/save Calls"
created: 2026-05-06T00:00:00.000Z
updated: 2026-05-06T01:00:00.000Z
---

## Symptoms

expected: 1 Klick auf "Personalisiert nutzen + Call" → genau 1 POST /api/precall/personalize/save (200)
actual: 1 Klick → 2 POST /api/precall/personalize/save — erster 200, zweiter 400 nach ~4 Sekunden
errors: |
  POST /api/precall/personalize/save 400 (Bad Request)
  [Personalize] Reload fand keinen personalisierten Opener — stiller Backend-Fehler?
  _savePersonalizedAndStartCall @ pip-launcher.js:624
  document.getElementById.onclick @ pip-launcher.js:614
timeline: "Nach Phase 08.19.5.6.2 Deploy heute, Hard-Refresh ohne Effekt. Loading-State Fix (saveBtn.disabled) aus Phase 08.19.5.6.1 bereits eingebaut, hilft nicht."
reproduction: "Step 4c öffnen (Personalisierung), Text anpassen, einmal auf 'Personalisiert nutzen + Call' klicken"

vps_logs: |
  18:44:05  POST /api/precall/personalize       → 200 (KI antwortet)
  18:44:07  POST /api/precall/personalize/save  → 200 (erster Save)
  18:44:11  POST /api/precall/personalize/save  → 400 (zweiter Save, 4 Sek später)

hypotheses:
  - "Doppel-Klick-Schutz greift nicht: saveBtn.disabled wird zu früh resettet (im Reload-Path)"
  - "Event-Listener-Doppelung: save-Button bekommt onclick zweimal zugewiesen"
  - "Race-Condition im R-04-Reload-Flow: renderStep5() re-rendert save-Button mit neuem onclick der direkt feuert"
  - "Browser-Network-Retry: HTTP/1.1 Retry (unwahrscheinlich)"

## Current Focus

hypothesis: "Null-guard early-return auf Zeile 691-695 re-enablet saveBtn nach erfolgreichem Save — User sieht aktivierten Button und klickt nochmals"
test: "_savePersonalizedAndStartCall() vollständig gelesen — null-guard path analysiert"
expecting: "null-guard soll nicht re-enablen wenn Save bereits erfolgreich war — stattdessen immer zu Step 5 navigieren"
next_action: "fix applied"

## Evidence

- timestamp: 2026-05-06T01:00:00.000Z
  finding: |
    In _savePersonalizedAndStartCall() (pip-launcher.js):
    1. Erster POST /api/precall/personalize/save → 200 OK (Zeile 624)
    2. Zweites fetch: /api/launcher/profile/{id} (Zeile 663) — lädt frisches Profil
    3. Cold-Call-Pfad: persOpener = filter(is_personalized) (Zeile 686-688)
    4. NULL-GUARD: persOpener.length === 0 → Zeilen 691-695:
       console.error('[Personalize] Reload fand keinen personalisierten Opener...')
       _showToast(...)
       saveBtn.disabled = false      ← BUG: re-enablet Button nach erfolgreichem Save
       saveBtn.textContent = saveBtnOrigText
       return                        ← bleibt auf Step 4c statt zu Step 5 zu navigieren
    5. User sieht nun aktiven "Personalisiert nutzen + Call" Button auf Step 4c
    6. User klickt nochmals (oder Browser-Autofill-Event) → zweiter POST → 400

  root_cause_confirmed: true

## Eliminated

- "Event-Listener-Doppelung": nein — onclick wird nur einmal in renderStep4c() zugewiesen
- "renderStep5() feuert onclick": nein — renderStep5() hat keinen lnr-step4c-save Button
- "Browser-Network-Retry": nein — 4 Sek Abstand und anderer Callstack (line:614) bestätigen zweiten User-Klick

## Resolution

root_cause: |
  Null-guard in _savePersonalizedAndStartCall() (pip-launcher.js Zeilen 691-695) re-enablet
  den Save-Button (saveBtn.disabled = false) und navigiert NICHT zu Step 5 weiter, wenn der
  Profile-Reload nach erfolgreichem Save keinen personalisierten Opener findet. Der Save war
  bereits erfolgreich (200 OK). Durch das re-enablen bleibt User auf Step 4c mit aktivem
  Button und klickt nochmals → zweiter POST → 400 (Backend: Duplikat oder Constraint).
  Identischer Bug im Meeting-Pfad (persSkripte.length === 0, Zeilen 677-682).

fix: |
  Null-guard-Pfade (beide Zweige: cold_call und meeting) ändern:
  - saveBtn.disabled = false und saveBtn.textContent reset ENTFERNEN (Save war erfolgreich — kein re-enable)
  - Stattdessen: state.step = 5; renderStep5(); aufrufen — auch wenn Reload keinen neuen
    personalisierten Eintrag findet, navigiert der User sauber zu Step 5

verification: |
  1. Step 4c öffnen, einmal auf "Personalisiert nutzen + Call" klicken
  2. Nach ~4 Sek: nur 1 POST /api/precall/personalize/save im Netzwerk-Tab
  3. User landet auf Step 5, kein aktiver Save-Button sichtbar

files_changed:
  - static/pip-launcher.js (Zeilen 677-695: beide null-guard early-return Pfade)
