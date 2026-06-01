"""Cross-tenant RLS isolation test against REAL Postgres (D-12.2 MANDATORY).

Phase 08.23.2.G-MEET Wave 2.

WHY REAL POSTGRES, NO SQLITE FALLBACK (B-2 / CLAUDE.md Integration-Assertion rule):
  SQLite has NO Row-Level-Security. A SQLite/in-memory branch would PASS while testing NOTHING
  about RLS -- a Source-Presence-class FALSE-GREEN. This test MUST exercise REAL Postgres RLS as
  the restricted `nerve_app` role (proven rolbypassrls=f, non-owner of crm.* -> RLS engages)
  against the real Production `nerve` database. There is deliberately NO dialect branch and NO
  :memory: connection anywhere in this module.

HARNESS:
  - `nerve_app_pg_conn` fixture (conftest.py) yields a raw psycopg2 connection as nerve_app to the
    real nerve DB, DSN from NERVE_APP_TEST_DSN. When the DSN is absent the test SKIPS (never
    falls back to SQLite). This is intended to run SERVER-SIDE on Production (CLAUDE.md HART:
    pytest runs via SSH on the prod host, not locally).
  - TRANSACTION-LOCAL mechanism (matches Task 3 db.py after_begin hook): each assertion runs
    INSIDE an explicit transaction. We issue `SELECT set_config('app.tenant_id', %s, true)`
    (third arg true = SET LOCAL, bound param) so the SET and the query share ONE transaction;
    the GUC is GONE after the transaction ends (test_guc_is_transaction_local proves this).
  - TEST-TENANT rows: we create dedicated organisations (is_test_user lineage / tag) + tenant_orgs
    rows so the Wave-3 anonymizer and founder analytics already exclude them. All test rows are
    cleaned up in teardown (reverse FK order).

ASSERTIONS are on ACTUAL returned rows / raised exceptions (runtime behavior that breaks if RLS
regresses), never on source text.
"""
import uuid

import pytest


def _new_tenant(cur, suffix):
    """Create a test organisation + tenant_orgs row, return the tenant UUID (str).

    tenant_orgs.legacy_org_id is NOT NULL UNIQUE FK -> organisations(id), so a real org row is
    required. Org name is tagged '[RLS-TEST]' for identifiability + analytics exclusion lineage.
    """
    cur.execute(
        "INSERT INTO public.organisations (name) VALUES (%s) RETURNING id",
        (f"[RLS-TEST] tenant {suffix}",),
    )
    org_id = cur.fetchone()[0]
    tenant_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO public.tenant_orgs (id, legacy_org_id, name) VALUES (%s, %s, %s)",
        (tenant_id, org_id, f"[RLS-TEST] tenant {suffix}"),
    )
    return tenant_id, org_id


@pytest.fixture
def two_tenants(nerve_app_pg_conn):
    """Set up tenant A + tenant B with one account_memory row each, yield their UUIDs, clean up.

    The setup INSERTs run under each tenant's own GUC so the RLS WITH CHECK is satisfied (a tenant
    can only insert rows tagged with its own tenant_id). Cleanup deletes in reverse FK order under
    each tenant's GUC, then drops the tenant_orgs + organisations rows.
    """
    conn = nerve_app_pg_conn
    cur = conn.cursor()
    # Create the two test tenants (no tenant GUC needed for public.* inserts -- those tables are
    # not RLS-protected; only crm.* is).
    tenant_a, org_a = _new_tenant(cur, "A")
    tenant_b, org_b = _new_tenant(cur, "B")

    mem_a = str(uuid.uuid4())
    mem_b = str(uuid.uuid4())

    # Insert one account_memory row per tenant, each under its OWN tenant GUC (WITH CHECK pass).
    for tid, mem_id in ((tenant_a, mem_a), (tenant_b, mem_b)):
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
        cur.execute(
            "INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks) "
            "VALUES (%s, %s, %s, %s, %s)",
            (mem_id, tid, str(uuid.uuid4()), '{"pain": "test"}', '[]'),
        )
    conn.commit()

    yield {
        "conn": conn,
        "tenant_a": tenant_a, "tenant_b": tenant_b,
        "mem_a": mem_a, "mem_b": mem_b,
        "org_a": org_a, "org_b": org_b,
    }

    # Teardown: delete crm rows under each tenant GUC, then public rows. Best-effort.
    cur = conn.cursor()
    try:
        for tid in (tenant_a, tenant_b):
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
            cur.execute("DELETE FROM crm.account_memory WHERE tenant_id = %s::uuid", (tid,))
        conn.commit()
        cur = conn.cursor()
        cur.execute("DELETE FROM public.tenant_orgs WHERE id IN (%s::uuid, %s::uuid)", (tenant_a, tenant_b))
        cur.execute("DELETE FROM public.organisations WHERE id IN (%s, %s)", (org_a, org_b))
        conn.commit()
    except Exception:
        conn.rollback()


def test_tenant_a_cannot_read_tenant_b_account_memory(two_tenants):
    """Inside tenant A's transaction-local GUC, SELECT returns ONLY A's rows; B's are invisible."""
    conn = two_tenants["conn"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (two_tenants["tenant_a"],))
    cur.execute("SELECT id::text, tenant_id::text FROM crm.account_memory")
    rows = cur.fetchall()
    conn.rollback()

    seen_ids = {r[0] for r in rows}
    seen_tenants = {r[1] for r in rows}
    # A's own row IS visible
    assert two_tenants["mem_a"] in seen_ids
    # B's row is NOT visible (cross-tenant isolation)
    assert two_tenants["mem_b"] not in seen_ids
    # Every visible row belongs to tenant A
    assert seen_tenants == {two_tenants["tenant_a"]}


def test_tenant_a_cannot_insert_as_tenant_b(two_tenants):
    """Under tenant A's GUC, INSERT of a row tagged tenant B raises (WITH CHECK violation)."""
    import psycopg2
    conn = two_tenants["conn"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (two_tenants["tenant_a"],))
    with pytest.raises(psycopg2.Error):
        cur.execute(
            "INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks) "
            "VALUES (%s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), two_tenants["tenant_b"], str(uuid.uuid4()), '{}', '[]'),
        )
    conn.rollback()


def test_unset_guc_returns_zero_rows(two_tenants):
    """With app.tenant_id UNSET, SELECT returns 0 rows (fail-closed), NOT an error."""
    conn = two_tenants["conn"]
    cur = conn.cursor()
    # Fresh transaction, NO set_config -> current_setting('app.tenant_id', true) is NULL ->
    # NULL::uuid never equals any tenant_id -> 0 rows.
    cur.execute("SELECT count(*) FROM crm.account_memory")
    count = cur.fetchone()[0]
    conn.rollback()
    assert count == 0


def test_guc_is_transaction_local(two_tenants):
    """After a transaction with a SET LOCAL commits/rolls back, a FRESH transaction sees the GUC
    empty (the SET LOCAL did not survive -- no cross-request leak)."""
    conn = two_tenants["conn"]
    # Transaction 1: set the GUC, then end the transaction.
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (two_tenants["tenant_a"],))
    cur.execute("SELECT current_setting('app.tenant_id', true)")
    in_txn_val = cur.fetchone()[0]
    conn.rollback()  # ends transaction 1 -> SET LOCAL discarded

    # Transaction 2 (fresh): no SET -> GUC must be empty/NULL.
    cur = conn.cursor()
    cur.execute("SELECT current_setting('app.tenant_id', true)")
    fresh_val = cur.fetchone()[0]
    conn.rollback()

    assert in_txn_val == two_tenants["tenant_a"]   # was set within the transaction
    assert not fresh_val                           # '' or None -> did not leak across transactions
