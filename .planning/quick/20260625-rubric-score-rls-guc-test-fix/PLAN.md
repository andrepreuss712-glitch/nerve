---
type: quick
slug: rubric-score-rls-guc-test-fix
status: complete
created: 2026-06-25
---

# Quick: Fix test_rubric_score_rls_requires_tenant_guc (M-4-Negativ-Bein)

Gate-Fund nach Plan-01-Deploy: **1 failed, 685 passed** → kein grünes Gate.
Nur dieser eine Test (M-4-Negativ-Bein) ist rot. **Test-Harness-Bug, KEIN Schema-/Security-Bug.**

## Root Cause (Claudian, database/db.py:73-89)

Der GUC `app.tenant_id` wird im `after_begin`-Hook **bei TX-Beginn** aus dem contextvar
`_current_tenant_id` gesetzt (`SET LOCAL`, auto-clear bei commit/rollback). Das Negativ-Bein rief
`clear_current_tenant()` (contextvar=None), **aber** die laufende `db_session`-TX hatte den GUC
schon auf `TEST_TENANT_UUID`. Der Clear wirkt nur auf KÜNFTIGE TX → der INSERT committete in
derselben TX mit GUC noch = TEST_TENANT_UUID → WITH CHECK passt → INSERT geht durch → `raised=False`
→ Assertion failt.

Prod-Sperre selbst ist korrekt (Claudian verifiziert: `relforcerowsecurity=t` + `tenant_isolation`
nullif-fail-closed + Owner nerve_app + FK CASCADE + partieller Unique-Index).

## Fix (nur tests/test_rubric_score_schema.py)

Nach `clear_current_tenant()` die laufende TX mit `db_session.rollback()` beenden → der INSERT läuft
in einer **frischen TX mit leerem GUC** (after_begin liest den geleerten contextvar → kein SET).
Zwei Anti-False-Green-Gürtel (PGTEST-Lehre):
1. Beleg-`SELECT current_setting('app.tenant_id', true)` MUSS leer sein, bevor der Reject-Assert gilt.
2. Abwesenheit der Negativ-Zeile wird unter dem **korrekten** Tenant-GUC gelesen (nicht unter leerem
   GUC, wo die USING-Klausel ohnehin alles versteckt → echter Beleg statt RLS-Read-Filter).
Positiv-Bein (`set_current_tenant` → INSERT geht durch, eigene frische TX) bleibt Pflicht-Gegenkontrolle.

## Constraints

- Kein anderer Code (Punkt 17, kein Refactor im Bugfix).
- Prod NICHT nochmal migrieren (rubric_score ist live, alembic 0020). deploy.sh-Restart ist harmlos.
- Verify = Production: `deploy.sh production` erneut → Gate grün → Restart. Plan 01 erst durch, wenn grün.
- Kein lokales pytest (CLAUDE.md HART) — der scharfe Lauf ist das Deploy-Gate.
