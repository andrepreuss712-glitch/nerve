**[OK] — Datei: Plan 01 / conftest.py — Fund #8 (Cross-Schema-FK)**
- **Problem:** `cleanup_rows` räumt `crm` und `public` ab. Wenn die Topo-Order nur mit `public`-Tabellen gefüllt wird, fallen `crm`-Tabellen in den Fallback-Bucket ans Ende. Das führt zwingend zu FK-Violations (z.B. `crm.accounts` -> `public.tenant_orgs`), da Kinder nach den Eltern gelöscht werden würden.
- **Warum OK:** `derive_baseline_tables` verwendet nun ein Tuple `schemas=('public', 'crm', 'training')`. Die resultierende globale Topo-Order reiht `crm`-Kinder strikt vor `public`-Eltern ein. `cleanup_rows` profitiert davon und löscht in der richtigen Reihenfolge. Der Wächter (`_snapshot_public_tables`) filtert die Liste via `startswith('public.')` lokal, wodurch D-G04 (Wächter ist public-only) unangetastet bleibt. Keine neuen Lücken.

**[OK] — Datei: Plan 01 / _schema_introspect.py — Fund #9 (Composite-PK False-Green)**
- **Problem:** Der Plan behauptete fälschlicherweise, Composite-PK-Tabellen seien "snapshot-sichtbar", obwohl sie aus der Wächter-Iteration exkludiert waren (Blind Spot).
- **Warum OK:** Die falsche Sicherheit ist raus. Composite-PK-Tabellen werden jetzt ehrlich als unüberwacht im `foundation_register` (`known gate gap`) dokumentiert. Da der aktuelle Prod-Katalog (Stand 16.06.) 0 solcher Tabellen aufweist, ist dies aktuell eine leere Lücke und die YAGNI-Entscheidung (Tuple-Key-Umbau aufgeschoben) ist absolut korrekt und transparent.

**Funde #1-#7 intakt?**
Ja, alle Folds aus den Vorrunden sind weiterhin präzise in den Plänen verankert:
- CASCADE-Kanten fließen in den Topo-Sort mit ein (Plan 01).
- Auto-Delete nutzt `pk_col::text = ANY` statt hartkodiertem `id` (Plan 01).
- Modul-Cache-Fill ist via `_baseline_schema` Dependency an `_baseline_snapshot` garantiert (Plan 01).
- Iterativer Count in `_crm_leak_count.py` entpackt die Tabelle sauber (Plan 02).
- `$@` Forwarding in `triage.sh` ist mit `_ "$@"` korrekt gelöst (Plan 03).

**Frischer Adversarial Sweep (Teil 2)**
- **Harness Bash-Quoting (`triage.sh`):** Das Single-Quote Konstrukt `sudo -u nerve_app env ... bash -c '...' _ "$@"` ist wasserdicht. Das `_` belegt `$0` der inneren Subshell, sodass `pytest "$@"` exakt die Parameter expandiert. Keine Maskierungsprobleme, Full-Suite-Runs werden bei Parametrisierung zuverlässig verhindert.
- **Security-Mocks (Plan 05):** Die Präzisierung, dass Mocks *nur* externe Abhängigkeiten (z.B. den LLM-Call) deterministisch machen, während die RLS-/Filter-Logik echt durchlaufen wird, verhindert effektiv False-Greens auf Security-Ebene.
- **Cross-Layer:** Keine Diskrepanzen zwischen `pg_constraint` Multi-Schema Abfragen und der Verarbeitung in Python (`cleanup_rows`). Die Katalog-Abfragen für crm-UNION und Wächter sind schlüssig separiert (nerve_app vs. postgres-Peer).

**GESAMT-VERDIKT: PASS**
Risiko: Gering. Die Pläne sind bau-frei, die Architektur-Nähte (insbesondere Cross-Schema-Interaktionen und Bash-Forwarding) sind geschlossen und Edge-Cases transparent dokumentiert. Keine False-Greens oder gefährlichen Lücken identifizierbar. Execute kann erfolgen.
