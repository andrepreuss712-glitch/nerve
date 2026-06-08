---
slug: engine-json-extract-block2-3
status: complete
date: 2026-06-08
commit: 8ee87dd
---

# Summary: Block 2+3 json_extract → Postgres (Folge-Pass)

Folge-Pass zu `20260608-ewb-json-extract-postgres-fix` (Block 1). Schließt den dort
dokumentierten Blast-Radius. Danach: **kein json_extract()-Aufruf mehr im Code**.

## Was geändert (services/integration_engine.py)
**Block 2 — Call-Schwaeche-Check (D-06, run_postcall_engine, läuft bei jedem Call):**
- `json_extract(metadata, '$.einwand_typ') = :typ` → `(metadata::jsonb ->> 'einwand_typ') = :typ`

**Block 3 — Training-Schwaeche-Check (D-05, run_posttraining_engine, läuft nach Training):**
- `json_extract(metadata, '$.einwand_typ') = :typ` → `(metadata::jsonb ->> 'einwand_typ') = :typ`
- `json_extract(metadata, '$.success') = 0` → `(metadata::jsonb ->> 'success') = 'false'`
  **WR-05-Sonderfall:** 'success' ist ein JSON-Boolean (log_learning_event schreibt
  Python-bool via json.dumps → `true`/`false`). SQLite json_extract gab dafür 0/1
  (altes `= 0`); Postgres `->>` liefert den Text `'true'`/`'false'` → `= 'false'`.

Keine GROUP BY/HAVING in Block 2/3 → keine Alias-Anpassung nötig (anders als Block 1).

## Verifikation
- Beide Queries read-only gegen Prod-Postgres (psql -d nerve, uid=0): Syntax OK, 0 rows ✓
- WR-05-Check gegen Real-Daten: `training_completed` hat aktuell **0 Rows** in der DB →
  Boolean-Annahme nicht empirisch, aber durch json.dumps-Serialisierung deterministisch garantiert.
- Prod py_compile: COMPILE-OK ✓
- Kein json_extract()-Aufruf mehr live (nur noch 1 Komment-Erwähnung) ✓
- Service-Restart 2026-06-08 13:16 UTC, is-active = active, /api/health = 200 ✓

## Deploy-Notiz
`bash deploy.sh production` — Test-Gate erneut durch pre-existing crm-SQLite-Failures
abgebrochen (exit 2). Fix per pre-autorisiertem manuellem `systemctl restart nerve` live.

## Verifikations-Hinweis für André
- **Block 1 + Block 2** werden bei einem **Call** ausgelöst (run_postcall_engine):
  `journalctl -u nerve --since "10 min ago" | grep -E "EWB-Muster-Check|Call-Schwaeche"`
  → beide Fehler müssen weg sein.
- **Block 3** läuft nur nach einer **Training-Session** (run_posttraining_engine):
  `grep "Training-Schwaeche-Check Fehler"` → erst nach einem Training relevant; aktuell
  0 training_completed-Events, daher feuert die Empfehlungs-Logik ohnehin (noch) nicht.

## Status json_extract im Projekt
Vollständig entfernt aus services/integration_engine.py (alle 3 Blöcke). Keine weiteren
Vorkommen im Code (grep --include=*.py, ohne __pycache__).
