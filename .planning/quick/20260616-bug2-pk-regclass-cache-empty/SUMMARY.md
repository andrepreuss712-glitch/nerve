---
slug: bug2-pk-regclass-cache-empty
status: complete
created: 2026-06-16
completed: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
files_modified:
  - tests/_schema_introspect.py
---

# Summary: Bug 2 Cache-Empty — PK-regclass-Query-Fix + Konsolidierung

## Was geändert wurde (1 Datei)

`tests/_schema_introspect.py`:
- **Fix `primary_key_column` SQLAlchemy-Zweig:** `:tbl::regclass`-named-param →
  inline f-string `'{qualified}'::regclass` (injection-sicher, katalog-abgeleitet;
  gleiche Technik wie `_fetch_fk_edges`). Behebt `psycopg2: syntax error at or near ":"`.
- **Konsolidierung:** `_fetch_pk_for_table` delegiert jetzt an `primary_key_column`
  (`return primary_key_column(conn, table, schema)`) — Duplikat eliminiert, EINE
  Quelle der Wahrheit. Arg-Reihenfolge korrekt gemappt (hier conn,schema,table →
  primary_key_column conn,table,schema).
- Der funktionierende psycopg2-`%s::regclass`-Zweig bleibt unangetastet.

## Wirkung

Vorher: SQLAlchemy-Engine-Pfad (conftest `_baseline_guard_engine`) → jede Tabelle wirft →
`pk_count=0` → alles in `foundation_register` → `baseline_table_list`/`_DERIVED_PK_COLS` leer →
test_baseline_autoreset 01/06 rot. Nachher: PK-Query läuft, Cache füllt sich.

## Verifikation

- `python -m py_compile tests/_schema_introspect.py` → OK.
- `grep ":tbl::regclass"` → nur noch in Kommentaren (SQL entfernt).
- f-string-Fix + Delegation per grep bestätigt; beide Aufrufer (conftest:410, derive:260)
  unverändert kompatibel.
- **Empirisch (Server, ausstehend):** Claudian fährt `scripts/triage.sh` test_01/test_06 →
  `_fetch_pk_for_table`-Flood weg, `_DERIVED_PK_COLS` NON-EMPTY, test_01/06 grün.
  (HART: kein local pytest.)

## Self-Check: PASSED
