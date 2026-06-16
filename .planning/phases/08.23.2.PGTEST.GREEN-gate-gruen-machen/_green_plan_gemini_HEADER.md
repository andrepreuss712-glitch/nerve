# ADVERSARIAL PLAN-REVIEW (Cross-AI, 3. Sicht) — Phase 08.23.2.PGTEST.GREEN

Du bist Senior-Datenbank/Test-Infrastruktur/DevOps-Engineer und unabhängige 3. Sicht. Lies die 5 Plan-Dateien + den echten Code (conftest.py, deploy.sh, pytest-Config) und entscheide: bau-frei (PASS) oder blockieren (BLOCK). Du bist NICHT der Autor — sei kritisch.

## Kontext
NERVE hat ein Deploy-Tor (`deploy.sh production`): baut eine Wegwerf-Postgres-DB `nerve_test` (Schema per pg_dump von Prod + alembic), läuft die volle pytest-Suite, deployt nur bei grün. Phase PGTEST lieferte das ehrliche Tor, blieb aber bewusst KNOWN-RED: 61 Test-Files leaken über 11 public-Tabellen (~507 Wächter-Errors) + 51 Assertion-Fails. Diese Phase **GREEN** macht das Tor grün.

Die SCHWERSTE Entscheidung (Isolations-Mechanismus = Auto-Reset gespalten) wurde bereits in einer separaten Gemini-Runde reviewt (`_green_isolation_gemini_OUT.md`, Verdikt Option 1) — die musst du NICHT neu bewerten. **Fokussiere auf die NEUEN Details, die diese Pläne dazu erfinden:**

## DEINE PRÜF-ACHSEN
1. **Topo-Sort (Plan 01, pg_constraint):** Ist die reverse-FK-Lösch-Order korrekt aus `pg_constraint` abgeleitet? Werden ZYKLEN (self-ref / mutual FK) sauber gebrochen? Wird `ON DELETE CASCADE` korrekt berücksichtigt (Eltern-Delete räumt Kinder → keine Doppel-/Fehl-Deletes)? Stirbt der Wächter NICHT am eigenen Cleanup?
2. **D-G19-Kopplung (Plan 01):** Liefert das Schema-Introspect-Modul list+order, BEVOR der Wächter sie konsumiert? Reihenfolge wirklich erzwungen (nicht nur behauptet)?
3. **Strict-Split (D-G02):** leaked → auto-delete + laute Warnung; missing/mutated → harter `pytest.fail` (KEIN Heilen). Korrekt umgesetzt? Kein stilles Schlucken?
4. **Schema-Ableitung (Plan 01/02, Req-9):** Tabellen-Liste + crm-Liste aus dem Katalog statt hardcoded. Denylist (alembic_version/Views) begründet? PK-Spalte pro Tabelle aus dem Katalog (nicht `id` angenommen)? Eine Wahrheit für conftest UND deploy.sh (kein Drift)?
5. **Triage-Harness (Plan 03):** Wiederverwendet er den Gate-Provisioning-Block 1:1, läuft NUR gezielte Tests, löst NIE Restart/Deploy aus? nerve_test-only, Prod sicher?
6. **Empirische Triage + Bug-Policy (Plan 04, Req-5/6):** xfail nur mit strict+reason+Ticket; Security/DSGVO/RLS/Anon-Bugs BLOCKEN (nie ge-xfailed). Wird Maskierung verhindert?
7. **Marker + Security-Mocks (Plan 05, Req-7/8):** live/perf-Marker NUR für echt env-abhängige Tests; KEIN Security-Test live/perf-markiert; Security-Tests die real-API brauchen werden GEMOCKT (Mock umgeht die Sicherheits-Logik NICHT) + bleiben im Tor. Kein false-green durch Über-Mocking?
8. **Wave-Integration:** W1 (Modul+Wächter) → W2 (Harness) → W3 (Triage+Marker+Mocks) → finaler Deploy. Abhängigkeiten korrekt? Kann ein späterer Wave einen früheren brechen?
9. **Prod-Sicherheit (Req-10):** `nerve` nie berührt (nur-lesender pg_dump, Whitelist-Guard), `nerve_test` trap-teardown. Irgendein neuer Pfad, der das verletzt?

## OUTPUT-FORMAT
Pro Fund: **[SCHWEREGRAD: BLOCKER/HOCH/MITTEL/NIEDRIG]** — Plan-Datei + Task — Problem — warum False-Green/False-Red/Silent-Failure/Prod-Risiko — präziser Fix.
Am Ende: **GESAMT-VERDIKT: PASS oder BLOCK** + Gesamt-Risiko (LOW/MED/HIGH). Sei ehrlich — nichts Neues finden ist ein legitimes Ergebnis. Aber wenn ein stilles Loch durchrutscht, ist das genau der Fehler, den diese Phase verhindern soll.

---
# UNTEN: 5 Plan-Dateien + SPEC + CONTEXT + echter Code (conftest.py, deploy.sh, pytest-Config)
---
