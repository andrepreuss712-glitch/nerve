Warning: True color (24-bit) support not detected. Using a terminal with true color enabled will result in a better visual experience.
Ripgrep is not available. Falling back to GrepTool.
VERDIKT: BLOCKER
Gesamt-Risiko: Hoch. Die Isolation und das Testing-Konzept sind strukturell durchdacht, aber drei Implementierungs-Details reißen den Deploy-Pfad ein, bevor überhaupt ein Test erfolgreich durchläuft, und es gibt einen signifikanten Leak-Blindspot. 

Hier sind die Funde, die der Rubber-Stamp-Durchlauf übersehen hat:

### 1. BLOCKER: Sudo Environment Syntax Crash im Gate
**Datei/Ort:** Plan 02, Task 1, Schritt 9 (`deploy.sh`)
**Problem:** Der Aufruf `sudo -u nerve_app ANON_PW="$ANON_PW" TEST_DB="$TEST_DB" bash -c ...` ist in Linux syntaktisch falsch. `sudo` wertet nach den Flags (`-u nerve_app`) das direkt folgende Argument als Command aus. `ANON_PW=...` ist aber kein gültiges Executable. Der Deploy bricht sofort mit `sudo: ANON_PW=...: command not found` ab. Das Test-Gate crasht hart vor Pytest.
**Konkreter Fix:** Das `env`-Kommando davorsetzen, um Variablen korrekt an die Sub-Shell zu übergeben:
`sudo -u nerve_app env ANON_PW="$ANON_PW" TEST_DB="$TEST_DB" bash -c '...'`

### 2. BLOCKER: Wächter-Teardown vs. `engine.dispose()` Timing (UnboundExecutionError)
**Datei/Ort:** Plan 01, Task 1 (`db_session`/`client`) vs. Task 6 (`_baseline_cleanup_guard`)
**Problem:** Plan 01 Task 6 ordnet an, den Wächter als "zuerst-angeforderte autouse-Fixture" zu definieren, damit sein Teardown GANZ ZULETZT (nach dem Test) läuft. Das bedeutet aber, sein Teardown läuft auch NACH dem Teardown von `db_session`. 
In Task 1 ruft `db_session` im finally aber `dbmod.SessionLocal.configure(bind=None)` und `engine.dispose()` auf. Wenn der Wächter-Teardown im Anschluss versucht, den DB-State für den Baseline-Vergleich zu lesen (`SessionLocal()`), knallt es mit `UnboundExecutionError`, da die Engine zerstört und die Session ungebunden ist.
**Konkreter Fix:** Den Engine-Lifecycle (Dispose & Bind-Reset) entkoppeln. `db_session` und `client` dürfen die Engine im Teardown nicht killen, wenn die Wächter-Fixture sie im Anschluss noch braucht. Engine an einen session-scope binden.

### 3. BLOCKER: `test_ft_seed` False-Red durch App-Import-Seeder
**Datei/Ort:** Plan 03, Task 8
**Problem:** Der Plan behauptet, `count == 4` sei sicher, weil "nerve_test SCHEMA-ONLY" sei. Er übersieht dabei einen kritischen Laufzeit-Faktor: Pytest importiert `app.py` beim Test-Setup. Der Import triggert die Top-Level-Seeder (`_seed_prompt_versions` etc.), die die vermeintlich leere DB in `nerve_test` umgehend mit der Baseline vollschreiben. Wenn `test_ft_seed` läuft und seine eigene globale `count == 4` abfeuert, liegen die Baseline-Rows längt in der DB. Der Test wird zu 100% failen.
**Konkreter Fix:** Nicht auf den Execute-Fehler warten. Sofort auf ID-Scoping oder Baseline-Delta umstellen, exakt wie bei `test_tenant_orgs` und `test_cost_tracker`.

### 4. HOCH: Leak-Blindspot in `training.transcript_archive` (False-Green)
**Datei/Ort:** Plan 01, Task 6 (Wächter) & Plan 02 (POST-SUITE-Check)
**Problem:** Der Wächter in Plan 01 prüft ausschließlich `public.*` (aus dem ORM). Der POST-SUITE-Check in Plan 02 prüft hardcodiert fünf `crm.*`-Tabellen. 
`training.transcript_archive` ist aber ORM-los, crm-fremd und public-fremd! Der `test_anonymizer_worker` schreibt dort munter hinein. Wenn dieser Test leakt oder der Cleanup fehlschlägt, fängt das NIEMAND ab. Das ist ein astreines False-Green.
**Konkreter Fix:** In Plan 02 den POST-SUITE-Check um einen UNION für `training.*` erweitern: `UNION ALL SELECT count(*) FROM training.transcript_archive`.

### 5. MITTEL: Stilles Verschlucken von Teardown-Fehlern in `cleanup_rows`
**Datei/Ort:** Plan 01, Task 5 (`cleanup_rows`)
**Problem:** "Best-effort: try: <deletes>; commit except Exception: rollback." Wenn ein Test z.B. einen FK-Parent löschen will, aber das Child im Spec vergisst, wirft Postgres eine `ForeignKeyViolation`. Das `except` macht stumm ein Rollback. Der Test bleibt grün, und die Rows bleiben liegen. Für crm.* schlägt dann zwar ganz am Ende der POST-SUITE-Check (Plan 02) Alarm ("Da leakt was"), aber die Zuordnung, WELCHER Test es vergeigt hat, ist verloren, weil das Cleanup stumm starb.
**Konkreter Fix:** Im `except`-Block nach dem Rollback ein hartes `raise` oder zwingend ein `logger.warning(...)` einbauen. Ein defekter Teardown darf nicht stumm scheitern.
