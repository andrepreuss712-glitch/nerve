---
type: quick
slug: rls-tenant-guc-regression
status: complete
created: 2026-06-24
---

# Quick: RLS-Mandanten-Regressions-Test (suggestion_reactions)

Nagelt den RLS-Mandanten-Bug aus TAXO2 Plan 08 dauerhaft fest (Live-Test-Fund 24.06.,
Fix-Commit 13e1712). Test-Netz-Regel: diesen einen Fehler nie wieder durchrutschen lassen.

## Der Bug (schon live gefixt, 13e1712)

- Call-Ende-Aufrufer (`routes/app_routes.py` ~Z.414-431) holte `tenant_id` aus `calls.tenant_id`
  (bei 36/51 Calls NULL) statt aus der Session.
- Der RLS-GUC `app.tenant_id` kommt aber aus `g.tenant_id` (before_request → contextvar →
  after_begin `set_config`).
- Folge: `row.tenant_id` (NULL/falsch) ≠ GUC → `tenant_isolation` WITH CHECK wies den INSERT
  LAUTLOS ab → `suggestion_reactions` blieb leer.
- Fix: `_sr_tenant_id = getattr(g, 'tenant_id', None)` → Quelle == GUC-Quelle.

## Warum die bestehenden Tests es nicht fingen

Alle Tests in `tests/test_suggestion_reactions.py` geben `flush_suggestion_offers` schon den
KORREKTEN `tenant_id` (`conftest.TEST_TENANT_UUID` == GUC) mit — sie stellen die
Aufrufer-Fehlerquelle (tenant ≠ GUC) nie nach.

## Was der neue Test beweist (REAL-PG nerve_test, db_session, KEIN SQLite-Branch)

- **Negativ-Bein:** flush mit `tenant_id` ≠ GUC → `tenant_isolation` WITH CHECK weist den INSERT
  ab (DB-Error). Beweist: Schutz echt + der alte Bug WÄRE gefangen worden.
- **Positiv-Bein:** flush mit `tenant_id` == GUC → genau 1 Zeile, `row.tenant_id` == GUC.

## Constraints

- In die BESTEHENDE Datei `tests/test_suggestion_reactions.py` (erweitern, nicht splitten).
- Muster gespiegelt: `db_session`-Fixture, `conftest.TEST_TENANT_UUID`, `_make_call()`,
  `cleanup_rows()` im `finally`.
- Nur Runtime-Behavior-Assertions (echte Exception / echte Zeilen), KEINE Source-Presence.
- Skip-sauber ohne `TEST_DATABASE_URL` (via `db_session`); im Deploy-Gate läuft er scharf.
