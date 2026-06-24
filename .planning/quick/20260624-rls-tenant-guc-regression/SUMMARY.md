---
type: quick
slug: rls-tenant-guc-regression
status: complete
created: 2026-06-24
completed: 2026-06-24
---

# SUMMARY: RLS-Mandanten-Regressions-Test

## Was gebaut wurde

Ein neuer Test `test_flush_tenant_must_match_guc_rls` in `tests/test_suggestion_reactions.py`
(angehängt, Datei nicht gesplittet) nagelt den RLS-Mandanten-Bug (Live-Fund 24.06., Fix 13e1712)
fest:

- **Negativ-Bein:** `flush_suggestion_offers(..., tenant_id=<fremde UUID ≠ GUC>)` + commit →
  erwartet eine DB-Exception (`tenant_isolation` WITH CHECK rejiziert); `rollback` + Assert
  `raised`; danach 0 sichtbare Zeilen für den Fremd-Mandanten-Call. Das ist der eigentliche
  Beweis, dass der alte Bug gefangen worden wäre (nicht nur "0 Zeilen", was auch ohne Schutz
  durch das USING-Read-Filter true wäre — daher harte Exception-Assertion gegen False-Green).
- **Positiv-Bein:** `flush(..., tenant_id=GUC)` → genau 1 Zeile, `row.tenant_id == GUC`.

## Muster / Konformität

- `db_session` (REAL-PG nerve_test, kein SQLite-Branch — sonst False-Green wie PGTEST-Lehre).
- `conftest.TEST_TENANT_UUID` (== GUC via `set_current_tenant`/after_begin-Hook), `_make_call()`,
  `cleanup_rows()` im `finally` (Baseline-Sauberkeit; rollt zuerst die abgebrochene TX zurück).
- Nur Runtime-Behavior-Assertions, keine Source-Presence. Skip-sauber ohne `TEST_DATABASE_URL`.

## Verifikation

- **NICHT lokal ausgeführt** (CLAUDE.md HART: kein Local-Dev, kein lokales pytest als Acceptance).
- Läuft **scharf im Deploy-Gate** (server-side gegen nerve_test) — das geschieht beim
  ausstehenden **beaufsichtigten Plan-08-Deploy** (`deploy.sh production` Test-Gate). Bis dahin
  ist die Tabelle `suggestion_reactions` noch nicht auf Prod (supervised migration pending).

## Pre-Insert (Punkt 14)

`tests/test_suggestion_reactions.py` + `tests/conftest.py` gelesen, Control-Flow + GUC-Quelle
(after_begin → `app.tenant_id`) + cleanup-Muster bestätigt vor dem Einfügen.
