---
status: resolved
trigger: "Backend-Frontend-Mismatch Cold-Call-Personalisierung: Backend speichert in ProfileSkript, Frontend filtert in profileData.opener — Item wird nicht gefunden. Plus Button-Text 'Personalisiert nutzen + Call' passt nicht mehr zu R-04-Verhalten."
created: 2026-05-06T00:00:00.000Z
updated: 2026-05-06T01:00:00.000Z
---

## Symptoms

expected: |
  Cold-Call-Personalisierung: nach Save findet Frontend-Reload das personalisierte Item korrekt
  in profileData.opener, selektiert es, User landet auf Step 5 mit aktiver Personalisierung.
  Button-Text spiegelt das tatsächliche Verhalten wider (kein Auto-Call mehr seit R-04).
actual: |
  SACHE 1: POST /personalize → 200, POST /save → 200, GET /launcher/profile/6 → 200 (Item drin),
  aber Frontend-Filter findet nichts → Toast "Reload fand keinen personalisierten Opener",
  User landet auf Step 5 aber Personalisierter Opener NICHT selektiert.
  SACHE 2: Button-Text "Personalisiert nutzen + Call ▶" verspricht Auto-Call der nicht passiert
  (seit R-04-Fix Phase 08.19.5.6.1 navigiert Klick zurück zur 4-Reiter-Ansicht, kein Auto-Call).
errors: |
  [Personalize] Reload fand keinen personalisierten Opener — stiller Backend-Fehler?
timeline: "Nach Phase 08.19.5.6.2-Deploy heute. Root cause durch UAT identifiziert."
reproduction: "Cold-Call-Modus, Personalisierung starten, Text anpassen, 'Personalisiert nutzen' klicken"

root_cause_known: true
root_cause_sache1: |
  api_personalize_skript_save (app_routes.py Zeile ~1306-1316) speicherte das personalisierte
  Item IMMER in ProfileSkript-Tabelle, auch bei call_mode='cold_call'. Frontend (pip-launcher.js
  Zeile ~717) filtert für Cold-Call: profileData.opener mit type='opener' + is_personalized=True.
  Da Item in profileData.skripte statt profileData.opener landete: leeres Array → Toast.
root_cause_sache2: |
  Button-Text "Personalisiert nutzen + Call ▶" (pip-launcher.js ~602, 645, 650, 720) referenzierte
  Auto-Call der seit Phase 08.19.5.6.1 R-04-Fix nicht mehr passiert. Verwirrend im UAT.

## Current Focus

hypothesis: "Beide Issues behoben — Fix implementiert und committed"
test: "28/28 tests pass (test_08_20_3.py)"
expecting: "Cold-Call-Personalisierung speichert korrekt in ProfileOpener, Button-Text ohne Auto-Call-Versprechen"
next_action: "done"

## Evidence

- timestamp: 2026-05-06T01:00:00Z
  observation: "api_personalize_skript_save zeigte Kommentar '# Insert IMMER als ProfileSkript (auch Cold-Call-Pfad)' — confirmed root cause"
  source: routes/app_routes.py line 1306
- timestamp: 2026-05-06T01:00:00Z
  observation: "pip-launcher.js line 688-700: Frontend filtert für Cold-Call profileData.opener mit type=opener und is_personalized=True — nie ProfileSkript"
  source: static/pip-launcher.js line 688
- timestamp: 2026-05-06T01:00:00Z
  observation: "Button-Text an 4 Stellen (602, 645, 650, 720) korrigiert auf 'Personalisiert nutzen'"
  source: static/pip-launcher.js

## Eliminated

- Netzwerkfehler (POST /save → 200 OK war bestätigt)
- Frontend-Filter-Bug (Filter-Logik korrekt — Problem war falsche Tabelle im Backend)

## Resolution

root_cause: |
  Sache 1: api_personalize_skript_save inserierte immer in ProfileSkript, unabhaengig von call_mode.
  Frontend filtert Cold-Call-Personalisierungen aus profileData.opener (ProfileOpener), nicht profileData.skripte.
  Sache 2: Button-Text "Personalisiert nutzen + Call ▶" versprach Auto-Call der seit R-04 nicht mehr passiert.
fix: |
  Sache 1: opener_id-Pfad inseriert jetzt in ProfileOpener (type='opener', is_personalized=True, parent_id, briefing_source_firma).
  Cap-Check und Delete-Phase decken beide Tabellen ab (ProfileSkript + ProfileOpener combined count).
  Sache 2: Button-Text an allen 4 Stellen in pip-launcher.js auf "Personalisiert nutzen" gekuerzt.
verification: "28/28 tests pass (test_08_20_3.py). Commit da20506 auf main gepusht."
files_changed:
  - routes/app_routes.py (api_personalize_skript_save: modus-abhaengiger Insert, Cap-Check beide Tabellen, Delete-Fallback)
  - static/pip-launcher.js (Button-Text 4 Stellen korrigiert)
