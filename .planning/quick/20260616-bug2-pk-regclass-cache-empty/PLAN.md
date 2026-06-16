---
slug: bug2-pk-regclass-cache-empty
created: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
type: quick
---

# Quick: Bug 2 (Cache-Empty) — `:tbl::regclass` SQLAlchemy-Named-Param-Crash

## Root-Cause (empirisch via scripts/triage.sh gefunden)

`tests/_schema_introspect.py`: die PK-Katalog-Abfrage im **SQLAlchemy-Zweig** von
`_fetch_pk_for_table` UND dem Duplikat `primary_key_column` mischte einen named-param mit
einem `::`-Cast: `WHERE i.indrelid = :tbl::regclass`. Über eine SQLAlchemy-Connection
(`_baseline_guard_engine.connect()`) führt das zu `psycopg2: syntax error at or near ":"`.

Kaskade: JEDE der ~45 Tabellen wirft → `pk_count=0` → alles landet als „no watchable PK"
im `foundation_register` → `baseline_table_list` LEER + `_DERIVED_PK_COLS` LEER → Modul-Cache
leer → `test_baseline_autoreset` test_01/test_06 rot (`cleanup_rows` fiel still auf
`_CLEANUP_FK_ORDER` zurück = Fund-#7-Meta-False-Green).

Warum nur dieser Pfad: `test_schema_introspect`-Tests nutzen eine psycopg2-DSN-Connection →
trafen den funktionierenden `%s::regclass`-Zweig → grün. Nur die conftest-Fixture
(`_baseline_guard_engine`, SQLAlchemy-Engine) traf den kaputten named-param-Zweig.

## Fix (Muster aus demselben File: `_fetch_fk_edges`)

`_fetch_fk_edges` interpoliert im SQLAlchemy-Zweig katalog-sichere Namen per f-string.
Gleiche Technik hier: den `:tbl::regclass`-named-param durch inline `'{qualified}'::regclass`
ersetzen (f-string; `qualified` ist katalog-/test-abgeleitet = injection-sicher), Cast als
reines Literal lassen. **Duplikat konsolidiert:** `_fetch_pk_for_table` delegiert jetzt an
`primary_key_column` — EINE Quelle der Wahrheit für die PK-Abfrage. Der psycopg2-`%s::regclass`-
Zweig (funktioniert) bleibt unverändert.

## Validierung

KEIN lokaler pytest (HART). Statisch: `python -m py_compile` grün; grep bestätigt 0 verbleibende
`:tbl::regclass`-SQL. Empirisch: Claudian fährt `scripts/triage.sh` für test_01/test_06 (Server) —
der `_fetch_pk_for_table`-Fehler-Flood muss WEG sein, `_DERIVED_PK_COLS` NON-EMPTY, test_01/06 grün.

Bug 3 (31 Zyklen) danach separat — die Zyklus-Diagnose-Logs lagen unter dem PK-Fehler-Flood begraben.
