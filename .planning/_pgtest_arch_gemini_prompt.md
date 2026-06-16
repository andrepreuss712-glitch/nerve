Du bist die unabhängige dritte Sicht (Cross-AI) auf eine ARCHITEKTUR-Entscheidung im NERVE-Repo (C:\Users\andre\dev\salesnerve). Read-only — ändere/führe NICHTS aus. Antworte auf Deutsch. Gegenleser, kein Bauarbeiter.

## Kontext
Wir stellen die pytest-Suite von SQLite-:memory: (fresh-per-test) auf ein echtes, EINZIGES persistentes Postgres `nerve_test` um (deploy.sh-Gate, fail-closed). Problem: viele Tests wurden für „jeder Test kriegt eine frische leere DB" geschrieben; auf der EINEN persistenten PG stolpern sie übereinander (FK-dangling, globale count()-Asserts, Seeder-Kollisionen). Drei Runden Einzel-Fixes konvergierten NICHT (jede Runde fand neue Mitglieder derselben Wurzel). Deshalb jetzt die Architektur-Weiche.

## Die Enumeration (lies sie zuerst, ganz)
`.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md`
— 64 Files klassifiziert: ~40 SAFE, Gruppe A ~6 (braucht Test-Fix EGAL welche Strategie, Baseline-Konflikt), Gruppe B ~8-10 (löst sich systemisch durch Option-2-Rollback, KEIN Test-Edit), Gruppe C ~1-2 (echte Bugs, eskalieren).

## Die vorgeschlagene Wurzel-Lösung (Option 2)
Per-Test-Transaktions-Isolation im „join external transaction"-Pattern: pro Test eine äußere Transaktion auf EINER Connection öffnen, das MODUL-`SessionLocal` (db.py) daran binden, der Test-Body läuft in nested SAVEPOINTs, am Test-Ende Rollback → DB zurück auf Baseline. Weil der ganze App-Code `get_session()` = `return SessionLocal()` (db.py:122) nutzt, landen AUCH code-seitige Commits in der Test-Transaktion und werden zurückgerollt → Gruppe B löst sich ohne Test-Edit.
Alternativen: Option 3 = Truncate-Reset nach jedem Test (reverse-FK, RLS-aware). Targeted = ~16-18 Tests einzeln härten + Base-Seed behalten.

## Lies SELBST (read-only)
- `database/db.py` ganz — v.a. `SessionLocal` (sessionmaker-Konfig), `get_session()` (:122), der `after_begin`-RLS-Hook (`_set_tenant_txn_local`, ~:86-103, der `SET LOCAL app.tenant_id` / `set_config(...,true)` pro Transaktion ausgibt), `set_current_tenant`/contextvar.
- `tests/conftest.py` ganz — die db_session/client-Fixtures + die psycopg2-Security-Fixtures (nerve_app_pg_conn etc.).
- `tests/test_rls_isolation.py` (das Real-Commit-/GUC-Muster der Security-Tests).
- 2-3 Gruppe-B-Tests (z.B. test_profitability, test_admin_dashboard_auth) + 2 Gruppe-A (test_ft_seed, test_tenant_orgs).

## PRÜFE GEZIELT — die heikelsten Punkte zuerst
1. **RLS-GUC × lange Transaktion (der kritischste):** Der `after_begin`-Hook setzt `app.tenant_id` transaktions-lokal beim BEGIN. Im join-external-transaction-Pattern lebt EINE äußere Transaktion über den ganzen Test, der Test-Body in SAVEPOINTs. (a) Feuert `after_begin` überhaupt für die genested/gebundene Session, und wann? (b) Wenn ein Test mitten drin `set_current_tenant(X)` ruft (contextvar ändert), wird das `SET LOCAL` neu ausgegeben — oder bleibt der GUC auf dem Wert vom äußeren BEGIN? (c) Folge: könnte Option-2 die RLS-abhängigen generischen Tests (A-1-Tripwire: crm-Read ≥1 Zeile unter gesetztem Tenant) BRECHEN (GUC NULL → 0 Zeilen) ODER still grün machen? Das ist der zentrale False-Green/False-Red-Knackpunkt — beurteile ihn scharf und konkret gegen den echten db.py-Hook-Code.
2. **Catch der code-seitigen Commits:** Greift das Pattern wirklich für JEDEN `SessionLocal()`/`get_session()`-Aufruf im App-Code? Gibt es Pfade, die eine EIGENE Engine/Connection bauen (dann NICHT gefangen → fallen in Gruppe A)? Prüfe per grep, ob irgendwo außer db.py eine zweite `create_engine`/`sessionmaker` im App-Pfad (nicht Tests) existiert.
3. **Security-Tests-Koexistenz:** Die psycopg2-Security-Fixtures committen ECHT (Cross-Tenant-Beweis) und laufen im selben Gate gegen dieselbe nerve_test. Vertragen sich real-committende Security-Tests + rollback-isolierte generische Tests in EINER persistenten DB? Hinterlässt ein real-committender Security-Test Daten, die einen späteren generischen Test stören (oder umgekehrt)?
4. **Klassifikations-Stichprobe:** Stimmt Gruppe A vs B vs C? Sind die Gruppe-B-Tests (z.B. test_profitability, test_admin_dashboard_auth) wirklich rein durch Rollback gelöst, oder hat einer einen versteckten Baseline-Konflikt (→ eigentlich A)? Ist die eine echte Gruppe-C (test_postcall_outcome_route, 6-vs-8 Outcome-Werte) korrekt als pre-existing Bug?
4b. **Option 2 vs 3:** Teilst du, dass Transaktions-Rollback (2) dem Truncate (3) überlegen ist (schneller, Standard, weniger fragil), oder gibt es hier einen Grund für 3?
5. **Neue Risiken durch den Refactor:** Was könnte Option-2 NEU kaputt machen, das es heute nicht ist? (z.B. Tests, die absichtlich über Commit-Grenzen hinweg prüfen; Multi-Connection-Sichtbarkeit; der A-1-Tripwire selbst.)

## Ausgabe
- VERDIKT: ist Option-2 die richtige Wurzel-Lösung für GENAU diese Codebase? PASS / PASS-MIT-AUFLAGEN / GEGEN.
- Pro Risiko: Einschätzung + Schweregrad + konkrete Auflage/Fix, v.a. zu Punkt 1 (RLS-GUC).
- Klare Empfehlung Option 2 vs 3 vs targeted.
- Was du NICHT gegen echten Code/Live verifizieren konntest: ehrlich sagen (du siehst Code im Ruhezustand, nicht den laufenden Server).
