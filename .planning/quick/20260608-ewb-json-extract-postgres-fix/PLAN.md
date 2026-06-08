---
slug: ewb-json-extract-postgres-fix
created: 2026-06-08
type: quick
---

# Quick Fix: EWB-Muster-Check json_extract → Postgres

## Problem
Prod-Log (08.06., journalctl -u nerve), bei jedem Call:
`[Engine] EWB-Muster-Check Fehler: (psycopg2.errors.UndefinedFunction)
function json_extract(text, unknown) does not exist`

## Root Cause
`json_extract()` ist SQLite-spezifisch, existiert in Postgres (Prod) nicht.
`services/integration_engine.py` Block "Muster-Erkennung EWB >3x" (D-11) nutzt es.
`learning_events.metadata` ist TEXT mit JSON-Inhalt (database/models.py:623,
`event_metadata = Column('metadata', Text)`; geschrieben via json.dumps).

## Fix (NUR EWB-Muster-Check, Block 1)
`json_extract(metadata, '$.einwand_typ')` → `(metadata::jsonb ->> 'einwand_typ')`.
Zusätzlich Postgres-Korrektheit der gleichen Query: GROUP BY auf den Ausdruck
statt SELECT-Alias, HAVING COUNT(*) statt Alias `cnt` (Postgres erlaubt keine
Output-Aliase in HAVING) — sonst kippt die Query nach dem json_extract-Fix in
den nächsten Postgres-Fehler. Gleiche Logik, läuft auf Postgres.

## Blast-Radius (REPORT-ONLY, NICHT in diesem Pass gefixt)
Weitere json_extract-Vorkommen, alle in services/integration_engine.py:
- Block 2 "Call-Schwaeche-Check" (D-06), Z.186-193, run_postcall_engine —
  `json_extract(metadata, '$.einwand_typ') = :typ`. Läuft AUCH bei jedem Call,
  Fehler `[Engine] Call-Schwaeche-Check Fehler`.
- Block 3 "Training-Schwaeche-Check" (D-05), Z.253-260, run_posttraining_engine —
  `json_extract(metadata, '$.einwand_typ') = :typ` + `json_extract(metadata, '$.success') = 0`.
  Läuft nach Training-Sessions. WR-05-Hinweis: SQLite json_extract gibt 0/1 für
  JSON-Booleans; Postgres `->> 'success'` gibt 'true'/'false' (Text) → beim Fix
  muss `= 0` zu `= 'false'` o.ä. angepasst werden (eigener Pass beachten!).
→ Separater Pass empfohlen.

## Scope
NUR EWB-Muster-Check (Block 1). Keine Refactors.

## Verify (HART: kein Local-Dev)
1. Pre-Deploy: korrigierte Query read-only gegen Prod-Postgres (uid=0) → Syntax OK
2. bash deploy.sh production (Gate bekannt kaputt → ggf. manueller systemctl restart)
3. André: Test-Call → journalctl -u nerve | grep "EWB-Muster-Check" → kein Fehler mehr
