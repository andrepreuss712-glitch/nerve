**TEIL 1: Verifikation des zuletzt eingearbeiteten Fixes (#9)**

**Fix #9 (`import app` als erste Aktion im Snapshot): OK.**
- **Kein neuer Fehler:** Der frühe Import erzwingt die Top-Level-Evaluation von `app.py` (inkl. `_seed_prompt_versions` etc.) genau zum richtigen Zeitpunkt: NACHDEM die Modul-Engine bereits durch den `deploy.sh` A-1 Fix (`DATABASE_URL=postgres...`) auf `nerve_test` zeigt, aber BEVOR das `{pk:xmin}`-Mapping im Snapshot eingefroren wird. Die Seed-Rows landen korrekt in `nerve_test` und sind Teil der Baseline.
- **sys.modules-Caching:** Ist absolut stichhaltig. Wenn die `client`-Fixture später für einen Test `from app import app` ausführt, sieht Python den Hit in `sys.modules` und überspringt die Ausführung der Modul-Ebene. Es gibt keinen Doppel-Seed.
- **Keine Kollision mit der Spät-Import-Strategie der client-Fixture:** Die `client`-Fixture verzögert den `app`-Import, um sicherzustellen, dass die Engine vorher gemockt/umgebunden wurde. Da der Modul-Engine beim Start durch `DATABASE_URL` bereits identisch zur per-Test-Engine auf `nerve_test` zielt, hat der frühe Auslöser der Seeder keine negativen Nebenwirkungen. Die spätere `SessionLocal`-Umbindung der `client`-Fixture modifiziert nur die Session-Factory für die Tests, was von dem einmaligen Import-Verhalten entkoppelt ist.

**Status der Fixes #1–#8: INTAKT.**
Ich habe alle Plan-Dateien auf den Erhalt der vorherigen Härtungen geprüft.
- **#1 (sudo env):** Ist als Blocker-Fix in Plan 02 Task 1 fehlerfrei als `sudo -u nerve_app env ANON_PW...` implementiert.
- **#2 (Guard-Engine):** In Plan 01 Task 6 perfekt als `_baseline_guard_engine` (eigene Read-Engine) entkoppelt vom per-Test-Lifecycle.
- **#3, #8, #10 (Scope-Fixes):** Sämtliche deterministischen False-Reds aus globalen Counts sind in Plan 03 / Plan 04 via ID-Scoping und `baseline-delta` aufgelöst.
- **#4 (transcript_archive):** In Plan 02 als POST-SUITE-Check verankert.
- **#5 (Laute Cleanup-Warnung):** In Plan 01 Task 5 korrekt implementiert.
- **#6 (Leading Rollback):** In Plan 01 Task 5 als zwingender Schritt 1 vor dem Teardown eingebaut (verhindert das Zementieren von AssertionError-Garbage).
- **#7 (xmin-Snapshot):** In Plan 01 Task 6 als Schutz vor mutierten Baseline-Rows erhalten.

---

**TEIL 2: Frischer adversarialer Sweep (NEUE Probleme)**

Die Pläne sind architektonisch extrem dicht und haben durch die Iterationen ein herausragendes Niveau an "Defensive Engineering" erreicht. Ein systemischer "False-Green" oder "False-Red" ist auf Design-Ebene nicht mehr auszumachen.

Ein kleines syntaktisches Detail ist mir beim tiefen Sweep des Wächters aufgefallen, das im Executor-Stadium abgefangen werden muss:

**[SCHWEREGRAD: NIEDRIG] — Plan 01 Task 6 (`_baseline_snapshot` / `_baseline_cleanup_guard`)**
- **Das Problem:** Der Plan instruiert den Executor, die Baseline mit der Query `SELECT id, xmin::text FROM <tabelle>` zu erfassen. Er listet Tabellen wie `api_rates`, `changelog` oder `exchange_rates` als Ziel-Tabellen auf.
- **Das Risiko (False-Red / Gate Crash):** Falls auch nur eine dieser Tabellen in `database/models.py` einen Primary Key nutzt, der *nicht* explizit `id` heißt (z.B. ein Compound-Key, oder Spalten wie `version` im Changelog, `currency` in exchange_rates), wird die Query `SELECT id ...` mit einem `UndefinedColumn`-Fehler hart abstürzen. Da der Snapshot-Wächter auf `session`-Scope (`autouse`) läuft, würde dies einen Gate-Crash direkt bei der Initialisierung der Test-Suite auslösen.
- **Der Fix:** Dies erfordert keine Plan-Änderung, aber der ausführende Executor muss die Direktive "SELECT id" logisch als "SELECT <primary_key_column(s)>" interpretieren und (z.B. über SQLAlchemy Reflection via `insp.get_pk_constraint(t)`) dynamisch den korrekten PK-Namen für die jeweilige Tabelle einsetzen.

**[SCHWEREGRAD: INFO] — Plan 04 Task 6 (Stale Gruppe-C-Assert `test_postcall_outcome_route`)**
- **Beobachtung:** Der Plan belässt den echten App-Bug (6 vs. 8 VALID_OUTCOMES) bewusst unangetastet. Da das Gate (`deploy.sh`) strikt `fail-closed` (`|| exit 1`) ist, wird der `production`-Deploy so lange scheitern (True-Red), bis der Bug durch den Orchestrator separat in der Applikation repariert wurde.
- **Bewertung:** Dies ist kein Fehler im Plan, sondern die exakte Einhaltung der Direktive `Req-7` (Honesty: Fehler nicht maskieren). Es bedeutet operativ lediglich, dass die Pipeline erst dann wirklich "grün" durchlaufen kann, wenn der Orchestrator parallel den Code gefixt hat.

---

**GESAMT-VERDIKT: PASS**

**Gesamt-Risiko: LOW**
Die Architektur des echten Postgres-Gates, kombiniert mit der isolierten Read-Engine (#2), dem leading Rollback (#6), der xmin-Mutation-Detection (#7) und dem hybriden POST-SUITE-Check für crm-Daten, ist wasserdicht. Das Risiko für unerkannte False-Greens oder persistente Leak-False-Reds ist vollständig mitigiert. Die Pläne sind freigegeben zur autonomen Ausführung.
