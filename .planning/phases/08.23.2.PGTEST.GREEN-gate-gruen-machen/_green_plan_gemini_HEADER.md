# ADVERSARIAL PLAN-RE-REVIEW (RUNDE 4) — Phase 08.23.2.PGTEST.GREEN

Senior-DB/Test-Infra/DevOps, unabhängige 3. Sicht. Lies die 5 Pläne + PATTERNS.md + echten Code (conftest.py, deploy.sh). PASS oder BLOCK. Kritisch, NICHT der Autor.

## Kontext + Konvergenz
NERVE-Deploy-Tor baut Wegwerf-`nerve_test`, läuft pytest, deployt nur bei grün. Phase GREEN macht das KNOWN-RED-Tor grün. Review-Konvergenz: R1=4 Funde, R2=3, R3=2 — alle gefoldet. Isolations-Mechanismus (Auto-Reset gespalten, public-only) bereits abgesegnet.

## Teil 1 — verifiziere die 2 zuletzt gefoldeten Funde (Runde 3)
- **#8 BLOCKER (Plan 01, cleanup_rows Cross-Schema-FK):** war public-only Cache → crm-Tabellen ans Ende → crm.accounts→public.tenant_orgs FK-Violation. FIX: `derive_baseline_tables` nimmt jetzt mehrere Schemas (`n.nspname IN %s`); Cache für public+crm+training gefüllt → globale Cross-Schema-FK-Order (crm vor public); der Snapshot-Wächter filtert table_list lokal auf public (D-G04 bleibt public-only). Prüfe: ist die globale Order WIRKLICH korrekt schema-übergreifend? Bleibt D-G04 (Wächter public-only) sauber? Kein neues Loch durch die Multi-Schema-Ableitung (z.B. crm im Snapshot, training-FKs)?
- **#9 HOCH (Plan 01, Composite-PK False-Green):** Prod-Katalog-Check ergab 0 Composite-PK-Tabellen heute (public/crm/training). FIX: falsche „snapshot-sichtbar"-Behauptung raus; ehrlich als „known gate gap: composite-PK nicht überwacht" ins foundation_register (Req-7, geloggt); Tuple-Key als YAGNI-Folge. Prüfe: ist die Doku jetzt ehrlich (keine Falsch-Behauptung mehr)? Ist der Gap akzeptabel begründet?
- Plus: #1-#7 noch intakt? PATTERNS.md konsistent mit allen Folds?

## Teil 2 — frischer adversarialer Sweep
NEUE Probleme? False-Green / False-Red / Silent-Failure / Prod-Sicherheit (`nerve` nie berührt, trap-teardown) / Wave-Abhängigkeiten / Mock-Strategie (Plan 05, umgeht Security-Logik nicht) / die empirische Triage (Plan 04) / Cross-Schema-Edge-Cases / der Modul-Cache vs. per-Test-Engine-Churn / Bash-Quoting. Achte besonders darauf, ob die letzten Folds (#8 Multi-Schema, #9 Gap-Doku) selbst neue Nähte aufreißen.

## OUTPUT
Pro Fund: **[SCHWEREGRAD]** — Datei + Task — Problem — warum — Fix. Für #8/#9 explizit OK/nicht-OK; #1-#7 intakt? Am Ende: **GESAMT-VERDIKT: PASS oder BLOCK** + Risiko. Ehrlich — wenn die Pläne jetzt bau-frei sind, sag PASS; erfinde keine Funde, um etwas zu liefern.

---
# UNTEN: 5 Plan-Dateien + PATTERNS.md + SPEC + CONTEXT + echter Code (conftest.py, deploy.sh)
---
