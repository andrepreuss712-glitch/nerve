### TEIL 1: Verifikation der 5 zuletzt eingearbeiteten Fixes

Die vorige Pro-Runde wurde exzellent umgesetzt. Ich habe alle 5 Bereiche tiefengeprüft:

*   **#1 (sudo env): OK.** Die Syntax `sudo -u nerve_app env ANON_PW="..." TEST_DB="..." bash -c '...'` ist absolut korrekt umgesetzt und an allen relevanten Stellen (Skelett, Task 1, T-PGTEST-06, T-PGTEST-32) konsistent. Die Single-Quotes im inneren `bash -c` schützen das Passwort kugelsicher vor vorzeitiger Interpolation.
*   **#2 (Guard-Engine-Lifecycle): OK.** Die Entkopplung durch eine dedizierte, Session-scoped `_baseline_guard_engine` (statt der pro Test re-gebundenen Modul-`SessionLocal`) löst den `UnboundExecutionError` an der Wurzel. Die Lebensdauer (erstellt bei Session-Start, disposed am Session-Ende) umspannt den gesamten Lauf sicher.
*   **#3 (ft_seed Scope): OK.** Der Scope-Fix auf `PromptVersion.module.in_(EXPECTED_MODULES)` isoliert den Test robust von den deterministischen `>=6` Rows des App-Import-Seeders. Kein False-Red mehr möglich.
*   **#4 (training.transcript_archive Post-Suite): OK.** Der zusätzliche `SELECT count(*)` als `postgres`-Superuser im deploy.sh flickt den Leak-Blindspot des Anonymizers wasserdicht. Das fail-closed Muster ist korrekt angewandt.
*   **#5 (cleanup_rows laute Warnung): OK.** Ein `logger.warning/sys.stderr` ist an dieser Stelle **ausreichend und exakt richtig**. Ein hartes `re-raise` würde den Teardown abbrechen. Wenn Rows leaken, feuern ohnehin unweigerlich die fail-closed Wächter (`_baseline_cleanup_guard` oder POST-SUITE). Die Warnung garantiert lediglich die *Attribution* (welcher Test war schuld), was das Ziel erfüllt.

---

### TEIL 2: Frischer adversarialer Sweep (NEUE Probleme)

Trotz der massiven Härtung gibt es in der Wechselwirkung zwischen persistenter Datenbank und generischen Teardowns noch kritische State-Leak-Szenarien. 

**[HOCH: BLOCKER] Plan 01 + Plan 04 — Task 5 (cleanup_rows) — State-Leak durch `session.commit()` von Test-Müll**
*   **Konkretes Problem:** Der `cleanup_rows`-Helfer läuft in der POST-yield-Sektion (also *auch*, wenn ein Test mit einem `AssertionError` fehlschlägt). Schlägt ein Test fehl, *bevor* er seine Transaktion committet hat, liegen unfertige (uncommittete) Rows z.B. in `crm.accounts` in der offenen Session. `cleanup_rows` feuert dann seine `DELETE`-Befehle ab und ruft am Ende blind `session.commit()` auf. **Dadurch committet `cleanup_rows` ungewollt den Test-Müll des fehlgeschlagenen Tests dauerhaft in die persistente `nerve_test`-DB!**
*   **Warum es kritisch ist (False-Green/Red):** Da der in-pytest-Wächter nur `public.*` prüft, bleiben versehentlich committete `crm.*`-Rows den Rest der Suite in der DB liegen. Folge-Tests, die RLS prüfen, sehen diese Fremd-Daten und könnten fälschlicherweise grün (oder rot) werden. Der POST-SUITE-Guard fängt es zwar ganz am Ende, aber die Test-Isolation *während* des Laufs ist kompromittiert.
*   **Präziser Fix:** Der `cleanup_rows`-Helfer **MUSS als allererste Aktion bedingungslos `conn_or_session.rollback()` aufrufen**. Damit wird jeglicher uncommittete State eines fehlgeschlagenen Tests sicher abgeräumt. Erst *danach* darf er seine Reverse-FK `DELETE`s für bereits vorher committete IDs ausführen und diese Löschanweisungen dann committen.

**[HOCH] Plan 01 — Task 6 (_baseline_cleanup_guard) — Mutationen an Baseline-Rows bleiben unentdeckt (False-Green)**
*   **Konkretes Problem:** Der Wächter snapshottet und vergleicht ausschließlich das PK-Set (`frozenset(pks)`). Da alle Tests sich jetzt dieselbe persistente Datenbank teilen (im Gegensatz zum früheren pro-Test-SQLite-Rebuild), kann ein Test eine Baseline-Row mutieren (z.B. `User(id=1).is_superadmin = True` setzen und committen). Der Primary Key ändert sich dabei nicht. Der Wächter meldet "Grün", aber der veränderte State leakt in alle nachfolgenden Tests, die den Base-Seed konsumieren.
*   **Warum es kritisch ist:** Tests, die sich auf den unmutierten Zustand des Base-Seeds verlassen, können unerwartet fehlschlagen oder fälschlich passen.
*   **Präziser Fix:** Der Wächter muss Mutationen fangen. In Postgres ändert sich bei jedem `UPDATE` automatisch die Systemspalte `xmin`. Lasse den Wächter `SELECT id, xmin::text FROM ...` snapshotten (oder bilde einen Hash über die gesamte Row via `hashtext(t.*::text)`). Wenn ein Test eine Baseline-Row mutiert, ändert sich `xmin`, und der Wächter schlägt sicher fehl.

**[MITTEL] Plan 04 (Tasks 4-7) & Plan 03 — Silent-Failure-Risiko durch "POST-yield"-Anweisung für normale Tests**
*   **Konkretes Problem:** Die Pläne weisen an: *"registriere die erzeugten Row-IDs + cleanup_rows im POST-yield-Teardown"*. Viele Tests in Gruppe B (z.B. `test_exchange_rates.py`) sind einfache `def test_xyz():`-Funktionen ohne eigene Fixture. Wenn der umsetzende AI-Agent einfach ein `yield` mitten in den regulären Test-Body schreibt, um eine "POST-yield-Sektion" zu erzeugen, behandelt pytest den Test plötzlich als Generator und **überspringt ihn lautlos** (Silent Failure).
*   **Präziser Fix:** Füge in Plan 04 (Task 1 / Cross-cutting) und Plan 03 eine glasklare Handlungsanweisung für den Executor ein: *"Für reguläre Tests ohne eigene Fixture darf NIEMALS ein `yield` im Test-Body platziert werden. Der Executor MUSS stattdessen eine dedizierte per-Test Fixture erstellen (z.B. `@pytest.fixture def cleanup_tracker(db_session): ids={}; yield ids; cleanup_rows(db_session, ids)`), die vom Test angefordert wird."*

---

### GESAMT-VERDIKT: BLOCK

Das Architekturbild der Postgres-Integration ist herausragend, besonders die `sudo env`-Trennung und die strikte Katalog-Validierung. Bevor der Executor-Agent jedoch losgelassen werden darf, **müssen die beiden [HOCH]-Findings behoben werden**:

1. `cleanup_rows` braucht einen initialen `rollback()`, sonst zementiert es den Transaktions-Müll abstürzender Tests.
2. Der Baseline-Wächter muss `xmin` oder einen Row-Hash (nicht nur PKs) einbeziehen, um persistente `UPDATE`-Leaks zu blockieren.

**Gesamt-Risiko bei unkorrigiertem Bau:** HOCH (State-Bleed zwischen Testfällen bricht die Integrität der Suite trotz der neuen Guards). Bitte Pläne anpassen und dann freigeben.
