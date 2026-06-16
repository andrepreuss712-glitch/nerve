Du bist die unabhängige dritte Sicht (Cross-AI Review) im NERVE-Projekt. Antworte AUSSCHLIESSLICH auf Deutsch, knapp und konkret. Du bist Gegenleser, KEIN Bauarbeiter.

WICHTIG: Die KOMPLETTEN, UNVERÄNDERTEN realen Dateien stehen unten im Input (nach diesem Prompt), jeweils markiert mit `===== FILE: <pfad> =====`. Es sind ganze Dateien (keine selektiven Auszüge) — bewerte direkt daran, du musst nichts nachladen.

## Kontext
Phase 08.23.2.PGTEST baut das deploy.sh-Test-Gate um: pytest läuft im Gate gegen eine wegwerfbare, schema-only aus Prod gedumpte Postgres-DB `nerve_test` (statt SQLite-in-memory), fail-closed, ZERO Daten-Zeilen. Du prüfst das DELTA mehrerer Audit-Fixes — ob sie das Gate EHRLICH und VOLLSTÄNDIG machen (kein False-Green, kein False-Red), gelesen am realen Code + den 3 Plan-Files im Input.

## Bewerte diese DELTA-Punkte (je: OK / CONCERN / BLOCKER + 1-3 Sätze mit datei:zeile-Beleg)

1. **A-1 (RLS-Hook-Ehrlichkeit — am wichtigsten):** `database/db.py` registriert den `after_begin`-RLS-Hook NUR `if 'sqlite' not in _DATABASE_URL` zur IMPORT-Zeit auf das Modul-`SessionLocal`. Plan 02 setzt im pytest-Subshell jetzt `DATABASE_URL=postgresql://nerve_app@/nerve_test`; Plan 01 bindet das Modul-`SessionLocal` via `.configure(bind=engine)` um. Greift damit der Hook WIRKLICH (set_current_tenant setzt den GUC, generische crm-Reads sehen echte Zeilen) — oder bleibt ein Pfad, auf dem der Hook tot ist und crm-Reads still 0 liefern (False-Green)? Ist der Tripwire-Test (`tests/test_rls_generic_smoke.py`, in Plan 01 beschrieben) scharf genug, um das ROT zu machen?

2. **Base-Seed (Plan 01 Task 4):** Session-Scope-autouse Org+User id=1, trigger-aware (`trg_mk_tenant_org` erzeugt tenant_orgs auto → KEIN manueller Insert), `setval` der Sequenzen nach explizitem id=1, ORM-Insert wegen `nullable=False`-Spalten mit nur python-`default=`. Löst das die 6 FK-Consumer-Tests? Kollisions-/Robustheits-Risiken (generischer Tenant aus Task 1, andere selbst-seedende Tests, id=1-Annahme)?

3. **db_from_client-Vertrag (Plan 01 Task 1):** Der `client`-Rewrite muss `c._test_session = dbmod.SessionLocal()` (Modul-SessionLocal, hook-tragend) + `c._test_engine` RE-exponieren (siehe conftest.py IST Z.84-85, db_from_client Z.95-97), sonst AttributeError in ~20 Gate-Tests. Ist `_test_session` aus dem umgebundenen Modul-SessionLocal hook-tragend UND dieselbe Engine wie `_test_engine`? Vollständig?

4. **test_08_14 (Plan 03 Task 3):** `Base.metadata.create_all` → `ApiRate.__table__.create(engine)` (ApiRate public?). Korrekt?

5. **F1 test_tenant_orgs (Plan 03 Task 4):** Auf PG-Trigger-Semantik portiert (erwartet auto-erzeugte Row, kein Python-Doppel-Seed). Korrekt?

6. **5 Deltas (Plan 03 Tasks 5-9):** postcall_split · ewb_rate_api · profile_editor · ft_seed (honest-run/eskalieren statt presumed-fix) · ab_stats. Je korrekt am realen Test?

## ZENTRALE FRAGEN
- **False-Green:** Maskiert irgendein Fix einen echten App-Bug, statt den Test ehrlich zu reparieren? (Besonders: macht Base-Seed/Tenant-Setzen einen real-roten Test künstlich grün?)
- **False-Red / Vollständigkeit:** Gibt es NOCH einen Test im Input, der gegen die schema-only/zero-data nerve_test bricht (FK/NOT-NULL/UNIQUE/RLS-0-Zeilen/Trigger/fallengelassenes Fixture-Attribut/Import-Seiteneffekt) und von KEINEM Fix abgedeckt ist?
- **Architektur-Konsistenz:** Widersprechen sich die Fixes über die 3 Pläne (Base-Seed vs. db_session-Rollback vs. session-scope-Commit; A-1 DATABASE_URL vs. die 3 Spezial-Fixture-DSNs)?

## Schluss
Gesamt-Risiko (LOW/MED/HIGH) + Top-Concerns priorisiert (BLOCKER zuerst). Wenn du etwas nicht am gelieferten Code verifizieren kannst, sag es explizit statt zu raten. Du siehst Code im Ruhezustand, nicht den Live-Server — Befunde ggf. „gegen Live gegenprüfen" markieren.

--- INPUT (komplette Dateien) folgt ---
