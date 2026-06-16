---
slug: fix-fk-edges-unpack
status: complete
created: 2026-06-16
completed: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
files_modified:
  - tests/_schema_introspect.py
---

# Summary: Fix 3-Tupel-Unpacking-Crash in _kahn_topo_sort

## Was geändert wurde (1 Datei, net −23 Zeilen)

`tests/_schema_introspect.py`:
- **Bugfix:** `valid_edges`-Comprehension entpackt jetzt 3-Tupel
  `for child, parent, _ in edges` (war 2-Tupel → ValueError). confdeltype wird
  ignoriert → alle FK-Kanten in den Sort (Fund #1).
- **Cleanup:** toter `in_degree`/`children_of`-Block + verwirrter ~20-Zeilen-
  Kommentarblock entfernt. Echter Algo (Kahn auf umgekehrtem Graphen
  `reverse_adj`/`reverse_in_degree`, Ergebnis reversed) unverändert/korrekt.
- **Doku:** Docstring `edges:`-Zeile auf 3-Tupel korrigiert.

## Bewusst NICHT geändert

`primary_key_column` bleibt: live getestet (`test_06_primary_key_column_non_id`)
+ in `conftest.py:10` importiert. Kein toter Duplikat — Entfernen hätte test_06
und den conftest-Import gebrochen.

## Verifikation

- `python -m py_compile tests/_schema_introspect.py` → OK (nur Syntax, kein Import/Exec/DB).
- `grep "for child, parent in edges"` → 0 Treffer (kein weiteres Fehl-Unpacking).
- `for child, parent in valid_edges` → genau 1 (reverse_adj-Loop, 2-Tupel-konsistent).
- **Voller Test-Grün:** aufgeschoben auf den nächsten `deploy.sh production`-Diagnose-Lauf
  (CLAUDE.md HART kein local pytest). Erwartung: test_schema_introspect 04/05/08 +
  test_baseline_autoreset 01/06 GRÜN.

## Self-Check: PASSED
