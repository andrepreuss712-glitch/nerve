---
slug: bug3-cycle-breaker-hub
status: complete
created: 2026-06-16
completed: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
gemini_review: _green_bug3_gemini_OUT.md
files_modified:
  - tests/_schema_introspect.py
---

# Summary: Bug 3 Cycle-Breaker — Hub statt Blatt (Gemini-3.-Sicht)

## Was geändert wurde (1 Datei)

`tests/_schema_introspect._kahn_topo_sort`:
- **Victim-Wahl korrigiert:** `min(reverse_in_degree)` (= Blatt) → `max(blockierte Rest-Kinder)`
  (= Hub). Das Blatt-Brechen invertierte legitime cross-schema-Kanten (`accounts->tenant_orgs`)
  und schob `crm.accounts` hinter `public.tenant_orgs` → test_06 rot. Hub-Brechen (`organisations`
  als Root → spät gelöscht) bricht nur eine Intra-SCC-Kante (`organisations->users`); alle
  Nicht-Zyklus-Kanten bleiben → crm-vor-public erhalten.
- `stuck_set = set(stuck)` aus dem Diagnose-Block hochgezogen (pro Iteration für Victim-Wahl nötig).
- Kommentar + Log-Message auf Hub-Semantik (`blockiert N Rest-Kinder`) aktualisiert.

## Gemini-3.-Sicht (CLAUDE.md Punkt 24)

3. Sicht via Gemini 3.1 Pro (Claudian-stdin, da `agy -p` headless nicht lief). Gemini fand den
Ordering-Bug am realen Code; Beleg-Artefakt: `_green_bug3_gemini_OUT.md` im Phasen-Verzeichnis.
test_06 bewusst NICHT gelockert (Gemini: Maskieren).

## Verifikation

- `python -m py_compile tests/_schema_introspect.py` → OK.
- grep: `victim = max(stuck, ...)` vorhanden, `min(stuck` weg, `stuck_set` vor Victim-Zeile.
- **Empirisch (Server, ausstehend):** Claudian `scripts/triage.sh` test_06 → grün
  (crm.accounts vor public.tenant_orgs), FK-violation-frei. (HART kein local pytest.)

## Self-Check: PASSED
