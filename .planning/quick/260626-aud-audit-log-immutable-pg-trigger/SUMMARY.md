---
task: 260626-aud-audit-log-immutable-pg-trigger
status: complete
result: built-pending-deploy-gate
date: 2026-06-26
migration: "0026"
down_revision: "0025"
---

# Quick-Task: audit_log Immutability-Trigger (Postgres) — DSGVO-/Tamper-Schutz

> Acceptance = `deploy.sh production`-Gate (kein Local-Dev). Code committet + gepusht; Claudian fährt
> den beaufsichtigten Deploy (Migration 0026 als postgres VOR Restart). Stand-alone — berührt KEINEN
> Scoring-/TAXO-Code.

## Bug (klare Ursache, verifiziert)

Der App-Start-Block (`app.py` ~1330-1350) schrieb den audit_log-Immutability-Trigger in **SQLite-Dialekt**
(`CREATE TRIGGER IF NOT EXISTS … BEGIN SELECT RAISE(ABORT,…) END`). Auf Production-Postgres wirft das
bei JEDEM Boot `syntax error at or near "NOT"` (non-fatal gefangen) → **0 Trigger** auf `audit_log`
(`pg_trigger` == 0 rows, Tabelle aber 948 echte Zeilen). `audit_log` war damit NICHT vor UPDATE/DELETE
geschützt — Defense-in-Depth / DSGVO-Tamper-Schutz fehlte still.

## Bau-Entscheidung (bewusst, nicht geraten)

**Trigger gehört in eine alembic-Migration (als postgres ausgeführt), NICHT in den App-Start.** Der
App-Start läuft als `nerve_app` — `CREATE TRIGGER` braucht Owner-Recht, das `nerve_app` für `audit_log`
nicht zwingend hat. Muster wie `0011` (`mk_tenant_org`) / die RLS-Migrationen. **Wichtig:** Trigger
feuern AUCH für den Tabellen-Owner (anders als RLS ohne FORCE) → die Sperre greift rollen-unabhängig.

## Was gebaut wurde

- **`alembic/versions/0026_audit_log_immutable_trigger.py`** (revision `0026`, down_revision `0025`):
  `CREATE OR REPLACE FUNCTION public.audit_log_immutable()` (plpgsql, `RAISE EXCEPTION 'audit_log is immutable'`)
  + `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER trg_audit_log_immutable BEFORE UPDATE OR DELETE ON
  public.audit_log FOR EACH ROW`. Idempotent. `downgrade()` droppt Trigger + Funktion.
- **`app.py`**: kaputten SQLite-Trigger-Block entfernt, durch Kommentar ersetzt (Verweis auf Migration 0026).
- **`tests/test_audit_log_immutable.py`** (Regressions-Netz, Andre-Direktive): 2 Tests gegen REAL-PG
  (db_session, skip ohne DSN — SQLite hätte den Trigger nicht = False-Green) — UPDATE bzw. DELETE auf
  audit_log → `RAISE EXCEPTION`, Assertion auf `'immutable'` in der Message. Insert-and-rollback
  (nie committet, Savepoint pro verbotener Anweisung) → kein Cleanup nötig (der Trigger blockt DELETE
  ohnehin), kein Baseline-Leak.

## Punkt-20-Beleg

`grep` über routes/ services/ app.py database/ nach `UPDATE audit_log` / `DELETE FROM audit_log` /
`.query(AuditLog).update/delete` → **0 Treffer**: audit_log ist append-only (INSERT-only, der Boot-
Marker bei app.py:669 ist INSERT) → der Trigger bricht keinen Live-Pfad. Kein toter Code (948 Zeilen aktiv).

## Verifikation

`py_compile` aller 3 geänderten Dateien lokal OK (reiner Parse, kein Acceptance). Echtes Gate:
`deploy.sh production` (Migration 0026 als postgres VOR Restart → nerve_test mit Trigger → die 2
Regressions-Tests müssen grün sein). create_all-Falle: Migration von Hand, Muster wie 0020-0025.

## Status

🔨 built — pending Deploy-Gate. Nach grünem Deploy: `pg_trigger` zeigt `trg_audit_log_immutable` auf audit_log.
