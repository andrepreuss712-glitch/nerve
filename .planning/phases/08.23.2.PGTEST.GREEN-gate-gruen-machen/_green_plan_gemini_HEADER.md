# ADVERSARIAL PLAN-RE-REVIEW (RUNDE 2) — Phase 08.23.2.PGTEST.GREEN

Du bist Senior-Datenbank/Test-Infrastruktur/DevOps-Engineer und unabhängige 3. Sicht. Lies die 5 Plan-Dateien + PATTERNS.md (bindende Referenz) + echten Code (conftest.py, deploy.sh) und entscheide: bau-frei (PASS) oder blockieren (BLOCK). Du bist NICHT der Autor — sei kritisch.

## Kontext
NERVE-Deploy-Tor (`deploy.sh production`) baut Wegwerf-`nerve_test`, läuft pytest, deployt nur bei grün. Phase GREEN macht das KNOWN-RED-Tor grün. Die schwerste Entscheidung (Isolations-Mechanismus = Auto-Reset gespalten) ist bereits abgesegnet (`_green_isolation_gemini_OUT.md`).

## Verlauf (wichtig)
RUNDE 1 (du) gab BLOCK mit 4 Funden, die jetzt GEFOLDET wurden — verifiziere zuerst, dass sie KORREKT + VOLLSTÄNDIG behoben sind und keinen NEUEN Fehler einführen:
- **#1 BLOCKER (Plan 01 topo-Sort):** war „CASCADE-Kanten (confdeltype='c') WEGLASSEN" → Wächter-Crash bei CASCADE→RESTRICT-Ketten. FIX: ALLE FK-Kanten (auch CASCADE) gehen jetzt in den topo-Sort; CASCADE-Kind bleibt in Liste UND als Kante. Prüfe: ist die Leaves-vor-Roots-Garantie jetzt für JEDE FK-Topologie (CASCADE-Ketten, self-ref/mutual-Zyklen) gegeben? Zyklus-Brechung noch intakt?
- **#2 HOCH (Plan 01 Auto-Delete):** war hardcoded `id::text` trotz abgeleiteter PK-Spalte → Crash bei non-id-PK (intent_event.event_id). FIX: Auto-Delete nutzt jetzt `{pk_col}::text = ANY(...)` mit der katalog-abgeleiteten PK-Spalte; `::text`-Cast (D-G06) bleibt. Prüfe: wird die PK-Spalte überall konsistent abgeleitet (Snapshot UND Delete)? Bei zusammengesetztem PK (>1 Spalte)?
- **#3 HOCH (cleanup_rows):** war Kopplung an dynamische Order → Signatur-Bruch/per-call-Query. FIX: Modul-Level-Cache `_DERIVED_FK_ORDER`/`_DERIVED_PK_COLS` (einmal Session-Start); cleanup_rows liest daraus, Fallback `_CLEANUP_FK_ORDER`. Prüfe: Cache-Lebenszyklus sauber (wann gefüllt/geleert)? Race mit der per-Test-Engine-Churn?
- **#4 NIEDRIG (Plan 02 crm_leak_count):** 3-Tupel-Unpack + iterative counts. Prüfe: korrekt.
- **PLUS PATTERNS.md** (bindende Referenz, in jedem Plan-Kontext geladen): wurde mit-gefoldet (kein stales „skip cascade"/hardcoded-id mehr). Prüfe auf Konsistenz Plan ↔ PATTERNS.

## Teil 2 — frischer adversarialer Sweep
Unabhängig von #1-#4: NEUE Probleme? Achsen: False-Green (Tor grün trotz kaputter Isolation/RLS/Anon), False-Red (Tor crasht/rot trotz Korrektheit — z.B. Wächter-Tod), Silent-Failure, Prod-Sicherheit (`nerve` nie berührt, trap-teardown), Wave-Abhängigkeiten, Mock-Strategie (umgeht Security-Logik nicht), zusammengesetzte/zyklische FK-Topologien, der Modul-Cache vs. die per-Test-Engine-Umbindung.

## OUTPUT
Pro Fund: **[SCHWEREGRAD: BLOCKER/HOCH/MITTEL/NIEDRIG]** — Plan-Datei + Task — Problem — warum (False-Green/Red/Silent/Prod) — Fix. Für #1-#4 explizit OK/nicht-OK. Am Ende: **GESAMT-VERDIKT: PASS oder BLOCK** + Risiko (LOW/MED/HIGH). Ehrlich — nichts Neues finden ist legitim; erfinde nichts.

---
# UNTEN: 5 Plan-Dateien + PATTERNS.md + SPEC + CONTEXT + echter Code (conftest.py, deploy.sh)
---
