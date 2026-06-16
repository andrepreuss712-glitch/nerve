Du bist die unabhängige dritte Sicht (Cross-AI Review) im NERVE-Projekt. Antworte AUSSCHLIESSLICH auf Deutsch. Du bist Gegenleser, KEIN Bauarbeiter — ändere/führe NICHTS aus, lies nur (read-only).

## Was du prüfst: ein DELTA-Review (nicht die ganze Phase neu)

Phase 08.23.2.PGTEST baut das deploy.sh-Test-Gate um: pytest läuft im Gate gegen eine wegwerfbare, schema-only aus Prod gedumpte Postgres-DB `nerve_test` (statt SQLite-in-memory), fail-closed. Die 3 Plan-Files wurden von DIR (Gemini) bereits einmal reviewt (7 Findings). Seitdem wurden mehrere Audit-Funde eingearbeitet. DU prüfst jetzt NUR das DELTA seit deinem letzten Review — ob diese Fixes das Gate EHRLICH und VOLLSTÄNDIG machen (kein False-Green, kein False-Red), gelesen am REALEN Code.

## Lies SELBST (read-only) — reale Code-Dateien
- `database/db.py` — speziell: Z.9 `DATABASE_URL`-Default (sqlite); Z.84-103 der `after_begin`-RLS-Hook `_set_tenant_txn_local`, der NUR `if 'sqlite' not in _DATABASE_URL` zur IMPORT-Zeit auf das Modul-`SessionLocal` registriert wird; `set_current_tenant`/`clear_current_tenant`.
- `tests/conftest.py` — Z.41-100: die generischen Fixtures `db_session` + `client` + `db_from_client` (Z.95-97 `return client._test_session`); die IST-`client` exponiert `c._test_session`/`c._test_engine` (Z.84-85).
- `tests/test_tenant_orgs.py` — Docstring „SQLite has NO triggers"; nutzt nur public (TenantOrg/Organisation/User/Call); `_seed_tenant_orgs` + manuelle TenantOrg-Inserts.
- `tests/test_08_14_apirate_seed.py` — `fresh_engine` (Z.14-19), `Base.metadata.create_all`.
- `database/models.py` — `ApiRate` (~Z.524-540: public? `__table_args__` Schema?); `Organisation`/`User` NOT-NULL-Spalten (welche `nullable=False` haben nur python `default=`, keinen `server_default`?); `calls.user_id` FK.
- `tests/test_postcall_split.py`, `tests/test_ewb_rate_api.py`, `tests/test_ft_seed.py`, `tests/test_profile_editor_validation.py` — die von den Deltas berührten Tests.
- `app.py` — `_seed_prompt_versions` (~Z.1196, Idempotenz check-then-insert?).

## Lies SELBST (read-only) — die 3 Plan-Files (die Anweisungen, die der Executor ausführt)
- `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-01-conftest-fixtures-PLAN.md`
- `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-02-deploy-gate-block-PLAN.md`
- `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-03-remove-sqlite-port-klasse-a-PLAN.md`

## Das DELTA, das du bewerten sollst (jeder Punkt: ist der Fix korrekt am realen Code UND ehrlich?)

1. **A-1 (RLS-Hook-Ehrlichkeit — am wichtigsten):** Im Gate-pytest-Subshell setzt Plan 02 jetzt `DATABASE_URL=postgresql://nerve_app@/nerve_test` (zusätzlich zu TEST_DATABASE_URL). Plan 01 bindet das MODUL-`SessionLocal` via `.configure(bind=engine)` um (statt frischer sessionmaker). FRAGE: Greift damit der `after_begin`-Hook (db.py:86, Import-Zeit-Entscheidung) WIRKLICH, sodass `set_current_tenant` den GUC `app.tenant_id` setzt und generische crm-Reads ECHTE Zeilen sehen — oder gibt es noch einen Pfad, auf dem der Hook tot bleibt und crm-Reads still 0 Zeilen liefern (False-Green)? Ist der neue Tripwire-Test `tests/test_rls_generic_smoke.py` (Plan 01) WIRKLICH scharf — geht er ROT, wenn der Hook tot wäre (assert `current_setting('app.tenant_id')`==Tenant + crm-Read ≥1)?

2. **Base-Seed (Plan 01 Task 4):** Ein Session-Scope-autouse-Fixture seedet 1 Organisation + 1 User (id=1, org_id=1) gegen nerve_test, trigger-aware (Org-Insert feuert `trg_mk_tenant_org` → tenant_orgs automatisch, KEIN manueller tenant_orgs-Insert), `setval` der Sequenzen nach explizitem id=1, ORM-Insert (wg. `nullable=False`-Spalten mit nur python-`default=`). FRAGE: Löst das die 6 FK-Consumer-Tests (user_id=1/org_id=1 auf leerer schema-only nerve_test) wirklich? Kollidiert es mit (a) dem generischen `[PGTEST-GENERIC]`-Tenant aus Task 1, (b) anderen Tests, die selbst Orgs seeden (Sequenz/UNIQUE)? Ist die `id=1`-Annahme robust (schema-only-Dump resettet Sequenzen auf 1 → erster Insert=1)?

3. **db_from_client-Vertrag (Plan 01 Task 1):** Der `client`-Rewrite (configure(bind=engine)) muss `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal, hook-tragend) + `c._test_engine` RE-exponieren, sonst AttributeError in ~20 Gate-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor). FRAGE: Ist die `_test_session` aus dem umgebundenen MODUL-SessionLocal wirklich hook-tragend UND dieselbe Engine wie `_test_engine`? Deckt der Fix alle Consumer?

4. **test_08_14 (Plan 03 Task 3):** `Base.metadata.create_all` → `ApiRate.__table__.create(engine)` gescopet (public Tabelle, kein crm). Korrekt?

5. **F1 test_tenant_orgs (Plan 03 Task 4):** Auf PG-Trigger-Semantik portiert (erwartet die vom `trg_mk_tenant_org` auto-erzeugte Row, kein Python-Doppel-Seed → kein UNIQUE(legacy_org_id)-Error). Korrekt?

6. **5 Deltas (Plan 03 Tasks 5-9):** postcall_split (Base-Seed konsumieren) · ewb_rate_api (unique email + trigger-aware) · profile_editor (Parents+Tenant) · ft_seed (HONEST-Run, eskalieren-wenn-echter-Bug statt presumed-fix) · ab_stats (Base-Org). Jeder korrekt am realen Test?

## ZENTRALE FRAGEN (am wichtigsten)
- **False-Green:** Maskiert IRGENDEIN Fix einen echten Fehler, statt den Test ehrlich zu reparieren? (Besonders: macht der Base-Seed / das Tenant-Setzen einen real-roten Test künstlich grün, der eigentlich einen echten App-Bug zeigt?)
- **False-Red / Vollständigkeit:** Gibt es NOCH einen Test, der im Gate gegen die schema-only/zero-data nerve_test-PG läuft und bricht (FK / NOT-NULL / UNIQUE / RLS-0-Zeilen / Trigger / fallengelassenes Fixture-Attribut / Import-Zeit-Seiteneffekt) und von KEINEM der obigen Fixes/Tasks abgedeckt ist? (Diese Klasse wurde mehrfach zu spät gefunden — grabe gezielt.)
- **Architektur-Konsistenz:** Widersprechen sich die Fixes über die 3 Pläne (z.B. Base-Seed vs. db_session-Rollback vs. session-scope-Commit; A-1 DATABASE_URL vs. die 3 Spezial-Fixture-DSNs)?

## Format deiner Antwort
Pro DELTA-Punkt (1-6) + die 3 zentralen Fragen: ein Verdikt (OK / CONCERN / BLOCKER) + 1-3 Sätze Begründung mit konkretem `datei:zeile`-Beleg aus dem realen Code. Am Ende: Gesamt-Risiko (LOW/MED/HIGH) + die Top-Concerns priorisiert (BLOCKER zuerst). Bleib knapp und konkret; keine Höflichkeitsfloskeln. Wenn du etwas nicht am Code verifizieren kannst, sag das explizit (statt zu raten). Denk dran: du siehst Code im Ruhezustand, nicht den Live-Server — Befunde ggf. als „gegen Live/inspect.sh gegenprüfen" markieren.
