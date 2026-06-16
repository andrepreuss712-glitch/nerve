**[BLOCKER]** — 08.23.2.PGTEST.GREEN-01-introspect-autoreset-PLAN.md (Task 1) — Topo-Sort ignoriert CASCADE-Kanten
**Problem:** Der Plan fordert explizit: `CASCADE-Kinder (confdeltype='c') als Kanten WEGLASSEN`. Das bricht die Integrität der topologischen Sortierung.
**Warum Wächter-Tod / Denial-of-Service:** Wenn Tabelle A (Eltern) ein CASCADE-Kind B hat, und B ein RESTRICT-Kind C hat, fehlt dem Sortierer die Kante A->B. Er ordnet A möglicherweise fälschlicherweise vor C an. Löscht der Wächter nun A, versucht die Datenbank via CASCADE auch B zu löschen. Das schlägt fehl, weil C noch auf B zeigt (FK Violation). Der Wächter crasht und blockiert das gesamte Deploy-Tor dauerhaft.
**Präziser Fix:** In Plan 01 Task 1 die Anweisung ändern: ALLE Foreign-Key-Kanten (unabhängig von `confdeltype`) MÜSSEN in den topologischen Sort einfließen. Nur so ist garantiert, dass immer "Leaves vor Roots" gelöscht werden, selbst wenn CASCADE im Spiel ist.

**[HOCH]** — 08.23.2.PGTEST.GREEN-01-introspect-autoreset-PLAN.md (Task 2) — Hardcoded `id::text` beim Auto-Delete ignoriert abgeleitete PK-Spalte
**Problem:** Task 1 leitet die PK-Spalte dynamisch aus dem Katalog ab (`primary_key_column`), aber Task 2 fordert für den Auto-Delete explizit: `DELETE FROM {tbl} WHERE id::text = ANY(:ids)`.
**Warum Wächter-Tod:** Wenn eine künftige Tabelle (z.B. eine Junction-Table für TAXO) einen Primary Key hat, der nicht `id` heißt (z.B. `event_id`), wird der Leak-Snapshot zwar korrekt gelesen, aber der anschließende DELETE-Befehl wirft einen Postgres-Fehler `column "id" does not exist` und crasht den Wächter.
**Präziser Fix:** In Plan 01 Task 2 anweisen, dass der generierte DELETE-String zwingend die in Task 1 abgeleitete PK-Spalte nutzen muss: `DELETE FROM {tbl} WHERE {pk_col}::text = ANY(:ids)`.

**[HOCH]** — 08.23.2.PGTEST.GREEN-01-introspect-autoreset-PLAN.md (Task 2) — Architektur-Falle bei `cleanup_rows`
**Problem:** Der Plan fordert, dass der bestehende Helfer `cleanup_rows` (der von Tests in `conftest.py` aufgerufen wird) ebenfalls auf die dynamische `reverse_fk_order` umgestellt wird. `cleanup_rows` ist aber eine normale Funktion ohne direkten Zugriff auf die session-scoped Fixture `_baseline_schema`.
**Warum Breakage / Performance-Kill:** Der ausführende Executor wird entweder die Signatur von `cleanup_rows` ändern (was alle bestehenden 20+ Test-Aufrufe bricht) ODER `derive_baseline_tables` bei jedem einzelnen `cleanup_rows`-Aufruf neu gegen die DB laufen lassen (was die Test-Suite extrem verlangsamt).
**Präziser Fix:** In Plan 01 Task 2 explizit anweisen: Die dynamisch abgeleitete `reverse_fk_order` muss auf Modul-Ebene gecached werden (z.B. globales Dict in `conftest.py`), ODER `cleanup_rows` behält als Fallback die harte `_CLEANUP_FK_ORDER` Liste (da es ohnehin nur ein best-effort Teardown ist).

**[NIEDRIG]** — 08.23.2.PGTEST.GREEN-02-deploy-crm-derivation-marker-wiring-PLAN.md (Task 1) — Dynamischer `crm_leak_count` 
**Problem:** Das Wrapper-Skript `scripts/_crm_leak_count.py` nutzt `derive_baseline_tables(schema='crm')`. Diese Funktion liefert ein Tupel zurück. Der Plan lässt offen, wie das Skript die eigentlichen Counts ausführt.
**Präziser Fix:** In Task 1 kurz ergänzen, dass das Python-Skript das Tabellen-Array aus dem Tupel extrahieren und dann pro Tabelle ein iteratives `SELECT count(*)` abfeuern muss.

---

**GESAMT-VERDIKT: BLOCK**
**Gesamt-Risiko: HIGH** (Der Fehler in der Topologischen Sortierung und der hardcodierte `id`-Delete kollidieren direkt mit den Postgres-Constraints und führen mit hoher Wahrscheinlichkeit zu einem crashenden Wächter, der das Gate lahmlegt).
