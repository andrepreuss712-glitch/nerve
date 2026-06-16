**ADVERSARIAL RE-REVIEW (RUNDE 2) — ERGEBNIS**

### Teil 1: Verifikation der eingearbeiteten Fixes (#6, #7, #8)

*   **Fix #6 (Leading Rollback in `cleanup_rows`): OK.** Der unbedingte `rollback()` als erste Aktion ist eine sehr starke Schutzmaßnahme gegen das Zementieren von `AssertionError`-abort-Garbage. Da in Postgres ein `ROLLBACK` auch transaktions-lokale GUCs (`SET LOCAL`, hier `app.tenant_id`) abräumt, ist es korrekt und essenziell, dass der Plan den Executor anweist, den Tenant-GUC für `crm.*`-Deletes *nach* dem Rollback explizit neu zu setzen. Das ist im Plan berücksichtigt (Schritt 2).
*   **Fix #7 (Baseline-Guard `{pk: xmin}` Snapshot): OK.** Ein reiner PK-Set-Vergleich ist blind für In-Place-Updates. Die Nutzung von `xmin` (der Transaction ID des einfügenden/updatenden Statements) oder alternativ `hashtext(t.*::text)` erfasst Mutationen zuverlässig. MVCC garantiert, dass ein Update eine neue Tuple-Version mit neuem `xmin` erzeugt. Das ist robust.
*   **Fix #8 (`cleanup_tracker` Fixture statt `yield` im Test-Body): OK.** Das ist die Lehrbuch-Lösung für das Pytest-Generator-Pitfall. Eine explizite Fixture verhindert garantiert, dass Pytest den Test stillschweigend überspringt (Silent-Skip).

---

### Teil 2: Frischer adversarialer Sweep (NEUE Probleme)

Ich habe die Architektur, die Sequenz der Fixtures und die Isolations-Mechanik in der Tiefe analysiert. Es gibt **EINEN kritischen Blocker** bezüglich der Initialisierungs-Reihenfolge des Baseline-Guards, der ansonsten bei jedem Lauf beim allerersten Test deterministisch crashen würde.

**[SCHWEREGRAD: BLOCKER]**
*   **Plan-Datei:** `08.23.2.PGTEST-01-conftest-fixtures-PLAN.md`
*   **Task-ID:** Task 6 (`_baseline_snapshot` Fixture)
*   **Problem (Guard Initialization Drift / False-Red):** Die `_baseline_snapshot`-Fixture friert den DB-Zustand bei Session-Start ein, **importiert aber `app` nicht explizit**. In dieser Codebase werden wichtige Baseline-Rows (z.B. `>=6` `prompt_versions`, `api_rates`, `fixed_costs`) durch Top-Level-Seeder (`_seed_prompt_versions`, `_seed_founder_dashboard_defaults`) exakt beim Modul-Import (`from app import app`) committet. Wenn der Snapshot genommen wird *bevor* `app` importiert wurde, ist der Snapshot bezüglich dieser Tabellen leer. Wenn dann der erste Test (z.B. über die `client`-Fixture) `app` importiert, feuern die Seeder und füllen die persistente `nerve_test`-DB. Der `_baseline_cleanup_guard` läuft nach dem Test, vergleicht die nun gefüllte DB mit dem "leeren" Snapshot, findet Drift (extra-PKs) und schießt das Gate **deterministisch mit einem False-Red beim allerersten Test ab**.
*   **Fix:** Weise den Executor in Plan 01 Task 6 explizit an, **als allererste Aktion in der `_baseline_snapshot`-Fixture `from app import app` auszuführen**, *bevor* die Queries für das `{pk: xmin}`-Mapping laufen. Da `DATABASE_URL` vom Gate korrekt exportiert ist, laufen diese Imports-Seeds sauber gegen die Postgres-DB. Danach friert der Snapshot den korrekten, vollständig initialisierten Baseline-Zustand ein. (Python's Modul-Caching `sys.modules` garantiert, dass spätere `app`-Imports in den Tests die Seeder nicht nochmal triggern).

---

### GESAMT-VERDIKT: BLOCK (bis der Initialization-Drift gefixt ist)
**Gesamt-Risiko nach Fix: LOW.**

Du hast mit dem Option-A-Pfad (Real-Commit, Cleanup-Helper, Strict Baseline-Guard, Post-Suite-CRM-Check via sudo) eine extrem harte und bewiesenermaßen dichte Test-Isolations-Architektur entworfen. Insbesondere der Post-Suite-Bypass via `sudo -u postgres` für das Testen der `crm.*` Cross-Tenant-Leaks ist ein brillantes PostgreSQL-Muster, das die Limitierungen eines In-Pytest-Guards mit `nerve_app`-Rechten perfekt umgeht.

Sobald du `from app import app` in die Snapshot-Fixture injizierst, um den Initialization-Drift zu verhindern, ist dieser Plan bereit für die Execution.
