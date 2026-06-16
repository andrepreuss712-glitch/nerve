---
slug: fix-fk-edges-unpack
created: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
type: quick
---

# Quick: Fix 3-Tupel/2-Tupel-Unpacking-Crash in tests/_schema_introspect.py

## Problem (eindeutiger Root-Cause aus Traceback)

`_fetch_fk_edges()` liefert **3-Tupel** `(child, parent, confdeltype)`, aber
`_kahn_topo_sort()` entpackte die `valid_edges`-Comprehension als **2-Tupel**
(`for child, parent in edges`) → `ValueError: too many values to unpack (expected 2)`
→ `derive_baseline_tables()` crasht.

**Kaskade:** derive crasht → Fixture `_baseline_schema` füllt den Modul-Cache nie →
`_DERIVED_PK_COLS`/`_DERIVED_FK_ORDER` bleiben leer.

Rote Tests (von den eigenen Tests gefangen):
- `test_schema_introspect`: test_04 / test_05 / test_08
- `test_baseline_autoreset`: test_01 / test_06

## Fix

1. `valid_edges`-Comprehension auf 3-Tupel: `for child, parent, _ in edges`
   (confdeltype ignoriert — ALLE Kanten gehen in den Sort, Gemini-Fund #1).
2. Cleanup (gleicher Commit): toter Code in `_kahn_topo_sort` raus
   (`in_degree`/`children_of` berechnet, nie gelesen — echter Algo nutzt
   `reverse_adj`/`reverse_in_degree`) + verwirrter ~20-Zeilen-Kommentarblock.
3. Docstring `edges:`-Zeile auf 3-Tupel korrigiert (Ehrlichkeit, Req-7).

## Entscheidung zur optionalen Bereinigung

`primary_key_column` NICHT entfernt: es ist KEIN toter Duplikat — direkt getestet
von `test_schema_introspect.py::test_06_primary_key_column_non_id` (Z.243/248) und
importiert in `conftest.py:10`. Entfernen würde test_06 + den conftest-Import brechen.

## Validierung

KEIN lokaler pytest (CLAUDE.md HART). Statisch: `python -m py_compile` grün,
grep bestätigt 0 verbleibende `for child, parent in edges`. Empirische Grün-Bestätigung
über den nächsten `deploy.sh production`-Diagnose-Lauf (Claudian): test_schema_introspect
04/05/08 + test_baseline_autoreset 01/06 müssen GRÜN sein.
