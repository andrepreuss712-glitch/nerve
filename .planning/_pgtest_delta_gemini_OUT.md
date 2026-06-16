Warning: True color (24-bit) support not detected. Using a terminal with true color enabled will result in a better visual experience.
Ripgrep is not available. Falling back to GrepTool.
Hier ist das Cross-AI Review der Phase 08.23.2.PGTEST, basierend auf den bereitgestellten Dateien und Plänen.

### Bewertung der DELTA-Punkte

1. **A-1 (RLS-Hook-Ehrlichkeit): OK**
   Plan 02 exportiert korrekt `DATABASE_URL=postgresql...` in der pytest-Subshell, sodass `database/db.py` beim Import den `after_begin`-Hook registriert. Plan 01 (Task 1) überschreibt nicht das `SessionLocal`-Objekt mit einer neuen Factory, sondern nutzt `dbmod.SessionLocal.configure(bind=engine)`. Dadurch bleibt der import-registrierte Hook erhalten. Der Tripwire-Test (`test_rls_generic_smoke.py`) liefert den harten Laufzeit-Beweis. Das schließt die False-Green-Lücke wasserdicht.

2. **Base-Seed (Plan 01 Task 4): OK**
   Der Session-Scope-Seed (Org+User id=1) über den ORM-Pfad sichert die Python-Defaults (`is_superadmin`, etc.) ab. Der Trigger `trg_mk_tenant_org` wird korrekt durch das Org-Insert ausgelöst, und der `setval`-Aufruf schützt vor Kollisionen. Löst die FK-Abhängigkeiten der 6 Consumer-Tests solide.

3. **db_from_client-Vertrag (Plan 01 Task 1): OK**
   Die Zuweisung `c._test_session = dbmod.SessionLocal()` (aus der rekonfigurierten Modul-Factory) stellt sicher, dass die Session hook-tragend ist und den Vertrag für die ~20 Consumer-Tests (kein `AttributeError`) aufrechterhält. Die parallele Zuweisung von `c._test_engine` ist komplett.

4. **test_08_14 (Plan 03 Task 3): OK**
   Die Änderung von `Base.metadata.create_all` zu `ApiRate.__table__.create(engine)` isoliert die SQLite-in-memory Erstellung auf diese eine Public-Tabelle. Das umgeht das "unknown database crm"-Problem nach dem Löschen des ATTACH-Listeners elegant und bewahrt den Laufzeit-Write-Test.

5. **F1 test_tenant_orgs (Plan 03 Task 4): BLOCKER (False-Red)**
   Der Plan portiert den Test zwar inhaltlich korrekt auf die Trigger-Semantik (Zurücklesen der auto-erzeugten Row), macht aber einen fatalen Logikfehler in der Validierung: Plan 03 Task 4 fordert, dass die **`count == 3`- und `legacy_ids == ...`-Assertions beibehalten werden** ("die count==3-Assertion... hält").
   *Der Fehler:* Da `nerve_test` über den Lauf persistent ist, liegen in der `organisations` / `tenant_orgs` Tabelle bereits der **Base-Seed** aus Plan 01 Task 4 UND die **Generic Tenants**, die pro `db_session`-Test von `_seed_test_tenant(engine)` angelegt wurden. Ein globales `.count()` oder `.all()` wird also `>3` Rows zurückliefern und das Gate garantiert rot färben.
   *Lösung:* Der Test muss seine Assertions auf die im Test selbst erzeugten IDs filtern (z.B. `.filter(Organisation.id.in_([a.id, b.id, c.id])).count()`).

6. **5 Deltas (Plan 03 Tasks 5-9): OK**
   Alle test-spezifischen Fixes sind konsistent. Besonders hervorzuheben ist Task 8 (`test_ft_seed`): Da die `nerve_test` via `pg_dump --schema-only` gebaut wird, ist die `prompt_versions` Tabelle initial absolut leer. Den Test unverfälscht ("honest run", `count == 4`) laufen zu lassen, ist die einzig richtige Architekturentscheidung, statt auf Verdacht Assertions aufzuweichen.

### ZENTRALE FRAGEN

- **False-Green:** Es gibt keine maskierten Tests. Die Architektur zwingt RLS-Tests zum Real-Commit und generische Tests zum expliziten Tenant-GUC. Das Katalog-Gate im `deploy.sh` sichert die RLS/GRANT-Struktur ab.
- **False-Red / Vollständigkeit:** Wie in Punkt 5 beschrieben, bricht `test_tenant_orgs.py` mit einem False-Red, wenn die Assertions nicht von globalen `.count()` / `.all()` auf ID-gefilterte Queries umgestellt werden. Alle anderen Abhängigkeiten (wie Unique-Constraints auf `users.email`) wurden bedacht.
- **Architektur-Konsistenz:** Exzellent. Die Verteilung von Verantwortung (`DATABASE_URL` via Shell, Hooks via `db.py`, Rückstandsfreier Teardown im POST-yield von `pytest`) ist durchdacht und greift nahtlos ineinander.

### Schluss

**Gesamt-Risiko: HIGH (aufgrund des garantierten Blockers in Plan 03 Task 4)**

**Top-Concern:** 
Korrigiere Plan 03 Task 4 zwingend vor der Implementierung. Das Ersetzen von globalen `db_session.query(Organisation).count()` durch ID-gefilterte Prüfungen ist kritisch, andernfalls wird das neue Gate bereits beim ersten Validierungslauf an den globalen Tabellen-Resten des Base-Seeds und der Generischen Tenants scheitern. Alle anderen Punkte sind bereit zur Ausführung.
