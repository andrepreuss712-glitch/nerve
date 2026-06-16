# ADVERSARIAL PLAN-RE-REVIEW (RUNDE 3) — Phase 08.23.2.PGTEST.GREEN

Senior-DB/Test-Infra/DevOps-Engineer, unabhängige 3. Sicht. Lies die 5 Pläne + PATTERNS.md + echten Code (conftest.py, deploy.sh). Entscheide: PASS oder BLOCK. Sei kritisch, NICHT der Autor.

## Kontext
NERVE-Deploy-Tor baut Wegwerf-`nerve_test`, läuft pytest, deployt nur bei grün. Phase GREEN macht das KNOWN-RED-Tor grün. Isolations-Mechanismus (Auto-Reset gespalten) bereits abgesegnet. Konvergenz der Reviews: Runde 1 = 4 Funde, Runde 2 = 3 Funde — alle gefoldet.

## Teil 1 — verifiziere die 3 zuletzt gefoldeten Funde (Runde 2)
- **#5 BLOCKER (Plan 03 triage.sh):** war `pytest "$@"` im single-quoted bash -c → Args expandieren nicht → ganze Suite statt targeted. FIX: Argument-Forwarding `bash -c '… pytest "$@"' _ "$@"` (`_`=$0, dann Args). Prüfe: ist das Forwarding-Muster KORREKT (kommt der Arg wirklich bei pytest an)? Keine Quoting-Lücke bei Pfaden mit Sonderzeichen?
- **#6 HOCH (Plan 01 Task 1, Composite-PK):** war ungeschützt → Over-Deletion. FIX: `len(pk_cols) != 1` → Tabelle ins foundation_register/Denylist ("composite PK not supported"), aus Auto-Delete raus, geloggt. Prüfe: greift das für ALLE Pfade (Snapshot UND Delete)? Wird eine Composite-PK-Tabelle dann gar nicht bewacht (akzeptabel?) oder anders abgesichert?
- **#7 MITTEL (Plan 01 Task 2, Cache-Init):** war keine Reihenfolge-Garantie → stiller Hardcode-Fallback. FIX: `_baseline_snapshot` fordert `_baseline_schema` als Fixture-Parameter. Prüfe: ist die Reihenfolge damit WIRKLICH hart (pytest-Fixture-Resolution)? Cache-Lebenszyklus sauber?
- Plus: #1-#4 aus Runde 1 noch intakt? PATTERNS.md konsistent?

## Teil 2 — frischer adversarialer Sweep
NEUE Probleme? False-Green / False-Red / Silent-Failure / Prod-Sicherheit (`nerve` nie berührt, trap-teardown) / Wave-Abhängigkeiten / Mock-Strategie / FK-Topologie-Edge-Cases / der Modul-Cache vs. per-Test-Engine-Churn / Bash-Quoting / die empirische Triage-Mechanik (Plan 04) / die Security-Determinismus-Mocks (Plan 05).

## OUTPUT
Pro Fund: **[SCHWEREGRAD]** — Datei + Task — Problem — warum — Fix. Für #5/#6/#7 explizit OK/nicht-OK; #1-#4 intakt? Am Ende: **GESAMT-VERDIKT: PASS oder BLOCK** + Risiko (LOW/MED/HIGH). Ehrlich — nichts Neues finden ist legitim, erfinde nichts.

---
# UNTEN: 5 Plan-Dateien + PATTERNS.md + SPEC + CONTEXT + echter Code (conftest.py, deploy.sh)
---
