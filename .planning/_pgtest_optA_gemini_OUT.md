Warning: True color (24-bit) support not detected. Using a terminal with true color enabled will result in a better visual experience.
Ripgrep is not available. Falling back to GrepTool.
I am starting the Cross-AI review of the `08.23.2.PGTEST` phase. My strategic intent is to assess the four provided plans (Plan 01, Plan 02, Plan 03, Plan 04) against the "ZENTRALE FRAGEN" focusing on the persistence hardening strategy, RLS implications, test isolation, and overall architectural consistency. This involves a thorough analysis of the proposed changes, their impact on existing tests and the `deploy.sh` gate, and identifying any potential False-Green, False-Red, or architectural inconsistencies.

I will now begin analyzing the plans and the detailed questions.

## ZENTRALE FRAGEN Review

### 1. Baseline-Wächter Ext-2 — Ordering & Vollständigkeit

**Plan 01 Task 6** details the `_baseline_cleanup_guard` (autouse, function-scoped) and `_baseline_snapshot` (session-scoped) fixtures.

*   **Snapshot Ordering:** The `_baseline_snapshot` is session-scoped and depends on the Base-Seed (Plan 01 Task 4). It correctly freezes the PK set *after* app-import seeds and the Base-Seed. This ensures the baseline includes the expected persistent data. OK.
*   **Per-Test-Prüfung Ordering:** The `_baseline_cleanup_guard` is `autouse=True` and function-scoped. The plan explicitly states: "die Pruefung MUSS NACH dem Test-eigenen Teardown laufen... der Waechter ist eine der AEUSSERSTEN autouse-Fixtures (frueh im Setup angefordert, damit sein Teardown zuletzt laeuft)". This ordering mechanism (autouse + early definition for late teardown execution) is standard pytest practice for ensuring post-cleanup checks. OK.
*   **Public.* Completeness:** The list of public tables to snapshot (`organisations, users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios, changelog, calls, conversation_logs, api_cost_log, revenue_log, ewb_ratings, profiles, profile_opener, exchange_rates`) appears comprehensive based on `models.py` and `PERSISTENCE-ENUMERATION.md`. This covers common write paths. OK.
*   **crm.* Completeness (Hybrid):** The `crm.*` tables are explicitly *not* checked by the in-pytest public watcher. Instead, `deploy.sh` (Plan 02 Task 1) runs a POST-SUITE check using `sudo -u postgres psql` to assert that all `crm.*` tables are empty (`== 0 rows`). This hybrid approach is justified because `nerve_app` (the role used by the in-pytest watcher) is RLS-filtered and would miss cross-tenant leaks. The `postgres` superuser role bypasses RLS and can see all `crm.*` data. This seems to cover the leakage paths effectively, with the trade-off that `crm.*` leaks are only caught post-suite and thus not attributed to a specific test's nodeid. This trade-off is acknowledged and accepted. OK.
*   **Leak Path (crm.*):** The plan dictates that all `crm`-writing tests *must* clean up their `crm` rows to 0 via `cleanup_rows` (Plan 01 Task 5) so the POST-SUITE check remains green. If a `crm` writer leaks, the POST-SUITE check will catch it. This is a sound mechanism. OK.

### 2. Ext-2 False-Green-Risiko

**Plan 01 Task 6** explicitly addresses this:
*   "crm.* wird NICHT in-pytest geprueft (nerve_app saehe nur einen Tenant) — die crm.*-Baseline (0 Rows pro crm.* Tabelle) wird POST-SUITE in deploy.sh (Plan 02) geprüft." This design prevents the in-pytest public watcher (running as `nerve_app`) from being blind to cross-tenant `crm.*` leaks.
*   The POST-SUITE `sudo -u postgres psql` check (Plan 02 Task 1) is crucial here. As `postgres` (superuser), `psql` bypasses RLS, ensuring it sees *all* `crm.*` data across *all* tenants. Asserting `== 0 rows` for `crm.*` effectively catches any cross-tenant leakage.
*   The plan deliberately avoids introducing a superuser/BYPASSRLS read path into the in-pytest test environment to maintain security and prevent false-greens in development.

This two-pronged approach (public in-pytest, crm post-suite) seems robust against false-greens by ensuring appropriate privileges for each check and addressing the RLS filtering concern. OK.

### 3. cleanup_rows Ext-1

**Plan 01 Task 5** defines the `cleanup_rows` helper.
*   **Correctness:** It's modeled *exactly* on `test_rls_isolation.py:101-116`, which is a proven deterministic teardown. It accepts a connection/session, a spec (`{Model_or_table: [ids]}`), and an optional `tenant` UUID.
*   **Reverse-FK Order:** The helper is designed to delete in a fixed reverse-FK order for known table families. This is essential for avoiding foreign key violations during cleanup. OK.
*   **crm.* under Tenant-GUC:** For `crm.*` tables, it explicitly requires and uses the `tenant` argument to set `set_config('app.tenant_id', tenant, true)` (or `set_current_tenant`) before deletion. This ensures RLS allows the deletion of tenant-owned rows. If the `tenant` argument is missing for `crm.*` operations, it should raise an exception, preventing silent failures. OK.
*   **Deletes ONLY test-eigene IDs:** The helper is designed to delete *only* the explicitly passed `ids`, preventing accidental deletion of baseline rows. This is critical. OK.
*   **No Accidental Baseline Deletion:** The helper's contract is to only delete passed IDs. The baseline rows (Org id=1, User id=1, app-import seeds) are either too generic (id=1) or not explicitly passed to `cleanup_rows` by the tests expected to use it. The baseline snapshot happens *after* the base seed, so the base seed rows are part of the *expected* baseline. This design seems to prevent accidental baseline deletion. OK.
*   **0 Rows under Wrong GUC (Leak):** If a `crm.*` table is to be cleaned up and the wrong `tenant` GUC is provided, RLS would prevent deletion, leading to a leak. However, the plan states: "Tenant ist Pflicht-Arg wenn crm.*-Tabellen im Spec sind; fehlt er → klare Exception". This explicit check should mitigate this risk. The POST-SUITE `crm` check (Plan 02) would ultimately catch such a leak. OK.
*   **POST-yield location:** The plan consistently emphasizes that `cleanup_rows` must be called in the fixture's POST-yield section (try/except `NACH dem yield`). This ensures the cleanup runs even if the test body fails, preventing state leakage. OK.

### 4. Gruppe A (Baseline-Konflikt, Plan 03 Task 4, 8, 9, 10 + Plan 04 Task 2, 3)

**This section needs to verify the proposed fixes for each listed test against the details in Plan 03 and Plan 04.**

*   **`test_ft_seed.py` (Plan 03 Task 8):** The plan states to run it "HONEST" against the schema-only `nerve_test` *as is*, without presumptive changes. If it fails, escalate. This is a sound approach for pre-existing failures where the root cause is unclear. The `count == 4` assertion is safe because `prompt_versions` is schema-only (no data in `nerve_test` baseline) and the test seeds itself. OK.
*   **`test_tenant_orgs.py` (Plan 03 Task 4):** This is a critical fix for F1 (Python-doppel-seed vs. PG-trigger) and Delta-Review-2 (global count vs. persistent Base-Seed).
    *   **Trigger Semantics:** `_mk_org` now reads back the trigger-generated `tenant_orgs` row instead of manually inserting. `_seed_tenant_orgs` becomes a no-op/read-back. This correctly aligns with PG trigger behavior. OK.
    *   **ID-Scoping:** ALL `count()/all()` assertions and helpers (`_seed_tenant_orgs`, `_backfill_calls_tenant_id`) are scoped to *test-generated* IDs using `filter(Organisation.id.in_(own_org_ids))`. This is crucial for avoiding false-reds due to the persistent Base-Seed (Org id=1, etc.). OK.
    *   **Idempotence Assertion:** `test_dualwrite_idempotent` (expecting `IntegrityError`) remains unchanged and valid, testing the `UNIQUE(legacy_org_id)` constraint. OK.
*   **`test_eur_calculator.py` (Plan 04 Task 2):** Addresses "unfiltered FixedCost-Summe draws in Baseline-FixedCosts." The action proposes scoping the aggregation to test-owned FixedCost rows (e.g., `filter(FixedCost.id.in_(own_ids))`) or using a baseline-delta approach. This resolves the false-red for global counts. OK.
*   **`test_cost_tracker.py` (Plan 03 Task 10):** Addresses `db_session.query(ApiCostLog).count() == 0` when `log_api_cost` (from `test_freeze_fx_on_write`) commits to its own session, leading to persistent rows. The proposed fix is to use a baseline-delta approach (`before = count; assert after == before`) or a provider filter (`filter_by(provider='unknown').count() == 0`). Both correctly address the persistence issue without altering the test's intent. OK.
*   **`test_ewb_pipeline.py` & `test_prompt_pipeline.py` (Plan 04 Task 3):** Address `UNIQUE(version,module)` collisions with app-import baseline PromptVersions. The proposed fix is either an idempotent check-then-insert guard or using a unique test-module name (e.g., `f'ewb-test-{uuid8}'`). Both are valid strategies for avoiding integrity errors on persistent data. OK.

All Gruppe A fixes appear correctly designed to handle the persistent `nerve_test` and baseline conflicts.

### 5. Option-A vs Option-2

The decision to choose Option A (real-commit model + targeted hardening) over Option 2 (per-test transaction rollback) is based on the critical finding that the RLS `after_begin` hook (`db.py:92`) sets `app.tenant_id` transaction-locally but *never clears it*. Under a long, single transaction (as Option 2 would imply with savepoints), the tenant GUC would leak between test steps, leading to RLS False-Greens.

*   **Justification against Option-2:** The argument about the RLS GUC leak (`if not tid: return`, `db.py:92`) is sound. A `SET LOCAL` GUC cleared on commit/rollback is safe, but if the transaction persists, the GUC persists. This is a fundamental flaw for RLS testing under Option 2. OK.
*   **Rest-Vorteil von Option-2:** Option-2 would have simplified cleanup for many tests, making them implicitly baseline-clean. However, the RLS False-Green risk outweighs this benefit for a security-critical application.
*   **Risiko in Option-A übersehen:** Option A's primary risk is the "whack-a-mole" problem of individually hardening tests and potential for missed leaks. This is mitigated by:
    *   The comprehensive `PERSISTENCE-ENUMERATION.md` listing all committing tests.
    *   The `cleanup_rows` helper (Ext 1) for standardized teardown.
    *   The `_baseline_cleanup_guard` (Ext 2) which *structurally enforces* public baseline cleanliness after *every* test.
    *   The POST-SUITE `crm.*` check (Plan 02) to catch any remaining `crm.*` leaks.

This layered mitigation strategy seems effective in addressing the risks of Option A. The overall choice appears well-justified given the RLS concern. OK.

### 6. False-Red / Vollständigkeit

This question asks about potential missing `cleanup_rows` adoptions or unresolved baseline conflicts.

*   **`cleanup_rows` Adoption:** Plan 04 Task 1 states: "Phasenweit nutzt jeder committende Test den gemeinsamen `cleanup_rows`-Helfer in seiner POST-yield-Sektion... Adoptions-Matrix (Test → Plan/Task, inkl. „Plan 03 (Orchestrator hand-edit)" fuer die Plan-03-eigenen Tests) ist im SUMMARY." The detailed tasks in Plan 03 and Plan 04 specifically include adopting `cleanup_rows` for all identified committing tests (Gruppe B). This seems comprehensive.
    *   Plan 03 Tasks 2, 4, 5, 6, 7, 9, 10 all include `cleanup_rows` adoption.
    *   Plan 04 Tasks 2, 3, 4, 5, 6, 7 all include `cleanup_rows` adoption.
*   **Unresolved Baseline Conflict Tests (Gruppe A):** All tests in Gruppe A have proposed fixes (scoping, idempotency, unique names) as detailed in Question 4. These should resolve the baseline conflicts.
*   **`test_postcall_outcome_route:156` (Gruppe C):** This is explicitly left unfixed and escalated. Plan 04 Task 6 addresses this directly: "die stale 6-vs-8 VALID_OUTCOMES-Assertion (:156) ist UNANGETASTET... Im SUMMARY als „Gruppe C, out-of-scope, eskaliert — bewusst nicht gefixt" vermerken." The important part is that the *committing* rows from this test still get cleaned up via `cleanup_rows`. This correctly handles the "false-red" from leakage while acknowledging the actual test failure. OK.
*   **"committender Test, der eine public-Tabelle trifft, die der Wächter nicht snapshotted":** The `_baseline_snapshot` (Plan 01 Task 6) explicitly lists a comprehensive set of public tables: `organisations, users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios, changelog, calls, conversation_logs, api_cost_log, revenue_log, ewb_ratings, profiles, profile_opener, exchange_rates`. This list seems to cover all public tables where data can be committed based on `models.py` and common application usage. It is likely exhaustive. OK.
*   **"crm-Writer, dessen Leak erst post-suite auffällt aber dann nicht eingrenzbar ist":** This is a known trade-off of the hybrid approach. A `crm.*` leak would be caught by the POST-SUITE check (Plan 02 Task 1), but since it's after the pytest run, the specific test that caused the leak won't be identified by nodeid. However, the `PERSISTENCE-ENUMERATION.md` identifies only ~4 `crm` writers (`test_rls_isolation`, `test_anonymizer_worker` RLS group, `A-1-Tripwire`, potentially some ported `crm` tests). This small number makes narrowing down the culprit trivial, as stated in Plan 01 Task 6. This is an accepted and mitigated risk. OK.

The strategy seems to account for potential false-reds and ensure cleanup across the board.

### 7. Architektur-Konsistenz über die 4 Plans

Let's check for any internal contradictions or overlooked dependencies across the plans.

*   **Base-Seed Rows vs. Wächter-Baseline-Snapshot:**
    *   Plan 01 Task 4: Base-Seed (Org id=1, User id=1, etc.) is session-scoped, committed *before* tests, and persists in `nerve_test`.
    *   Plan 01 Task 6: `_baseline_snapshot` runs *after* app-import seeds + Base-Seed. This means the Base-Seed rows are correctly part of the *expected* baseline snapshot. This is consistent. OK.
*   **A-1-Tripwire and POST-SUITE crm-Check:**
    *   Plan 01 Task 2: A-1-Tripwire seeds one `crm.accounts` row with `tenant_id=TEST_TENANT_UUID` to prove RLS functionality. It *must* clean up this row to 0 via `cleanup_rows` in its teardown.
    *   Plan 02 Task 1: POST-SUITE `crm` check asserts `crm.* == 0 rows`.
    *   This is consistent. The A-1 Tripwire is a `crm`-writer and is explicitly tasked with cleaning up its row to 0. If it fails to do so, the POST-SUITE check will catch the leak. OK.
*   **`client` fixture (`_test_session`/`_test_engine` contract):** Plan 01 Task 1 explicitly ensures that the `client` fixture re-exposes `c._test_session` and `c._test_engine` (pointing to the module's `SessionLocal()` and the `nerve_test` engine). This preserves the contract for ~20 consuming tests, preventing `AttributeError` and ensuring broad test compatibility. This is a critical consistency point, well-addressed. OK.
*   **WAL-Hook (db.py):** Plan 03 Task 1 explicitly states the WAL-Hook is *kept* because it protects genuine local Dev-SQLite usage outside the test environment and is guarded by `if 'sqlite' in _DATABASE_URL`, making it inert in the PG gate. This is a reasoned decision and consistent. OK.
*   **`_sqlite_attach_crm_training_schemas` and `app.py` SQLite Alembic Hook Removal:** Plan 03 Task 1 removes these, and subsequent tasks (2, 3, 4) port the tests that depended on them. This ensures consistency by eliminating SQLite emulation. OK.
*   **Plan 03 and Plan 04 `files_modified` Disjointness (flag3):** This ensures parallel execution safety during a single commit. The plan explicitly states: "Plan 03 + Plan 04 are same-wave PARALLEL-SICHER (disjunkte files_modified, keine Sequenz-Kopplung noetig)." This is important for smooth integration. OK.
*   **`DATABASE_URL` in pytest subshell (A-1):** Plan 02 Task 1 explicitly sets `DATABASE_URL=postgresql://nerve_app @/$TEST_DB` in the pytest subshell. This is crucial for `db.py` to register the `after_begin` RLS hook correctly upon import, preventing a silent false-green where the hook is never registered. This dependency is correctly identified and implemented. OK.

The plans appear consistent in their architectural approach and address inter-plan dependencies effectively.

## Schluss

**Gesamt-Risiko:** LOW (was HIGH war, ist gut mitigiert).

The plans demonstrate a thorough understanding of the Postgres testing environment, RLS mechanisms, and the complexities of migrating from an SQLite-emulated setup to a persistent Postgres test database. The identified risks (False-Greens, False-Reds, integrity violations due to persistence) are systematically addressed through a combination of:

1.  **Strict `deploy.sh` gate logic:** ensuring `nerve_test` is provisioned, schema-built (using the proven `pg_dump` method), and torn down correctly, with robust fail-closed mechanisms and explicit DSN handling.
2.  **`conftest.py` refactoring:** establishing the PG connection for generic fixtures, setting tenant context for RLS, and preserving crucial existing contracts (`_test_session`).
3.  **Comprehensive cleanup and baseline enforcement:** the `cleanup_rows` helper and the hybrid `_baseline_cleanup_guard` (public in-pytest, crm post-suite) provide a strong structural guarantee against test leakage and state pollution.
4.  **Targeted test fixes (Gruppe A & B):** meticulously addressing each test's interaction with the persistent database, whether through ID-scoping, idempotent seeding, unique naming, or `cleanup_rows` adoption.
5.  **Explicit handling of known issues:** the unfixed `test_postcall_outcome_route:156` (Gruppe C) is a deliberate choice to escalate a real bug rather than mask it, while still ensuring its test-generated data is cleaned.

The initial HIGH complexity and security-near nature of the task have been mitigated by detailed research, a well-structured plan, and robust verification points.

**Top Concerns (all appear to be mitigated or accepted trade-offs):**

1.  **CRM Leakage Attribution (Mitigated):** The `crm.*` leak detection is post-suite (Plan 02 Task 1), so specific test nodeid attribution is lost. However, the small number of `crm`-writing tests makes manual correlation trivial, and all `crm`-writing tests are tasked with `cleanup_rows` using the tenant GUC. This is an accepted and well-managed trade-off.
2.  **`test_postcall_outcome_route:156` Stale Assertion (Accepted/Escalated):** The plan explicitly leaves this assertion unfixed (6-vs-8 VALID_OUTCOMES) as an escalated pre-existing bug. This is a correct approach for a Cross-AI reviewer, distinguishing between test-infra issues and application bugs. Its committing data is still cleaned up.
3.  **`DATABASE_URL` for RLS Hook (Mitigated):** The hard precondition that `deploy.sh` *must* set `DATABASE_URL` (not just `TEST_DATABASE_URL`) in the pytest subshell is critical and correctly implemented in Plan 02 Task 1. The A-1 Tripwire (Plan 01 Task 2) provides a runtime check for this.

Overall, the plan is well-conceived and addresses the objectives effectively with robust mitigations for identified risks.

The next step would be to create the summary documents for each plan (`08.23.2.PGTEST-01-SUMMARY.md`, `08.23.2.PGTEST-02-SUMMARY.md`, `08.23.2.PGTEST-03-SUMMARY.md`, `08.23.2.PGTEST-04-SUMMARY.md`).update_topic(strategic_intent='Ich werde die vier bereitgestellten Pläne (Plan 01, Plan 02, Plan 03, Plan 04) sowie die zugehörigen Code-Dateien gründlich analysieren, um die sieben zentralen Fragen des Cross-AI Reviews zu beantworten. Mein Fokus liegt auf der Bewertung der Persistenzhärtung und der Implementierung des Postgres-Test-Gates.')
