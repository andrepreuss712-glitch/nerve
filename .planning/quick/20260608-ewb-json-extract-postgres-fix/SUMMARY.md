---
slug: ewb-json-extract-postgres-fix
status: complete
date: 2026-06-08
commit: f118e57
---

# Summary: EWB-Muster-Check json_extract → Postgres

## Was geändert
`services/integration_engine.py` Block "Muster-Erkennung EWB >3x" (D-11):
- `json_extract(metadata, '$.einwand_typ')` → `(metadata::jsonb ->> 'einwand_typ')`
- `GROUP BY einwand_typ` → `GROUP BY (metadata::jsonb ->> 'einwand_typ')`
- `HAVING cnt > :threshold` → `HAVING COUNT(*) > :threshold`

Grund für die GROUP BY/HAVING-Anpassung: Postgres erlaubt keine SELECT-Output-Aliase
in HAVING — sonst wäre die Query nach dem json_extract-Fix in den nächsten Postgres-
Fehler gekippt. Gleiche Logik, läuft jetzt auf Postgres.

## Root Cause
`json_extract()` ist SQLite-spezifisch. Prod ist Postgres → `function json_extract(text,
unknown) does not exist` bei jedem Call (`[Engine] EWB-Muster-Check Fehler`). metadata ist
TEXT mit JSON (LearningEvent.event_metadata, json.dumps).

## Verifikation
- Korrigierte Query read-only gegen Prod-Postgres (sudo -u postgres psql -d nerve, uid=0):
  `QUERY-SYNTAX-OK`, 0 rows ✓
- Datei live auf Prod (integration_engine.py:163/167 = jsonb-Version) ✓
- Service neu gestartet 2026-06-08 13:08 UTC, is-active = active, /api/health = 200 ✓
- EWB-Muster-Check-Fehler erscheint erst bei einem Call (post-call engine) → André-Test-Call ausstehend

## Deploy-Notiz
`bash deploy.sh production` lief, Test-Gate erneut durch dieselben ~120 pre-existing
crm-SQLite-Failures abgebrochen (exit 2, kein Auto-Restart). Fix per pre-autorisiertem
manuellem `sudo systemctl restart nerve` live gebracht (wie beim phase_classify-Fix).

## Blast-Radius (REPORT-ONLY — NICHT in diesem Pass gefixt)
Weitere json_extract-Vorkommen, alle services/integration_engine.py:
1. **Block 2 "Call-Schwaeche-Check" (D-06)**, Z.186-193 (run_postcall_engine) —
   `json_extract(metadata, '$.einwand_typ') = :typ`. Läuft AUCH bei jedem Call →
   `[Engine] Call-Schwaeche-Check Fehler` feuert vermutlich ebenfalls bei jedem Call.
2. **Block 3 "Training-Schwaeche-Check" (D-05)**, Z.253-260 (run_posttraining_engine) —
   `json_extract(metadata, '$.einwand_typ') = :typ` + `json_extract(metadata, '$.success') = 0`.
   Läuft nach Training-Sessions. **Achtung WR-05:** SQLite json_extract gibt 0/1 für JSON-
   Booleans; Postgres `->> 'success'` liefert Text 'true'/'false' → beim Fix muss `= 0` zu
   `= 'false'` (Text) angepasst werden, sonst matcht nichts.
→ Empfehlung: ein gemeinsamer Folge-Pass für Block 2+3 (gleiches Pattern, Block 3 mit
  Boolean-Sonderfall).

## Weitere Beobachtung (unrelated, pre-existing)
Beim Service-Start: `[DB] Audit-Log Trigger setup failed: (psycopg2.errors.SyntaxError)
syntax error at or near "NOT"`. Nicht von diesem Fix, nicht integration_engine — separate
Audit-Log-Trigger-DDL. Eigener Check empfohlen.
