---
type: quick
slug: rubric-score-rls-guc-test-fix
status: complete
created: 2026-06-25
completed: 2026-06-25
---

# SUMMARY: Fix test_rubric_score_rls_requires_tenant_guc

## Geändert (nur tests/test_rubric_score_schema.py — eine Testfunktion)

`test_rubric_score_rls_requires_tenant_guc` korrigiert:
- Nach `clear_current_tenant()` ein `db_session.rollback()` → beendet die laufende TX (deren GUC
  noch = TEST_TENANT_UUID) → der folgende Block läuft in frischer TX, in der `after_begin` den
  geleerten contextvar liest → **kein** `SET` → `app.tenant_id` ungesetzt → `nullif(...,'')::uuid`
  = NULL → WITH CHECK fail-closed (exakt die Plan-04-Daemon-ohne-Request-Context-Lage).
- **Gürtel 1 (Anti-False-Green):** `SELECT current_setting('app.tenant_id', true)` muss leer
  (`None`/`''`) sein, sonst Assert-Fehler — der Test beweist, dass die kein-Tenant-Lage echt
  nachgestellt ist, bevor der Reject-Assert greift.
- **Gürtel 2:** die Abwesenheit der Negativ-Zeile wird unter dem **korrekten** Tenant-GUC gelesen
  (Positiv-Bein) — sonst würde die USING-Klausel die Zeile ohnehin verstecken (kein echter Beleg).
- Positiv-Bein: `set_current_tenant(tenant)` + `db_session.rollback()` (leere-GUC-TX beenden) →
  INSERT in frischer TX mit GUC=tenant geht durch + ist lesbar.
- `finally`: GUC + frische TX vor `cleanup_rows` wiederhergestellt.

## Warum kein Schema-/Security-Fix

Claudian hat auf Prod verifiziert: `rubric_score` hat `relforcerowsecurity=t` + `tenant_isolation`
(nullif-fail-closed) + Owner nerve_app + FK CASCADE + partieller Unique-Index. Die echte Sperre ist
korrekt — nur die Test-Transaktions-Choreografie stellte die kein-Tenant-Lage falsch nach.

## Verifikation

- **NICHT lokal ausgeführt** (CLAUDE.md HART, kein Local-Dev). Mechanik gegen `database/db.py:73-89`
  (after_begin-Hook) + die `db_session`-Fixture (plain Session, commit/rollback startet neue TX)
  bestätigt. Vorbild-Muster: explizite TX-Grenzen je Bein wie `test_meeting_save_rls.py`.
- **Scharf im Deploy-Gate** (server-side gegen nerve_test) beim erneuten `deploy.sh production`.
  rubric_score ist bereits auf nerve_test/Prod (alembic 0020) → der Test kann jetzt grün/rot laufen
  (vorher PENDING-SUPERVISED-DEPLOY). Erwartung: 686 passed / 0 failed.

## Offen
- `deploy.sh production` erneut (Gate grün → Restart + Code live) — beaufsichtigt durch Claudian/André.
- Plan 01 ist erst DURCH, wenn das Gate grün ist.
