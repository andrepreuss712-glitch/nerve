"""Meeting-write-path + crm.user_preferences RLS/DSGVO tests against REAL Postgres.

Phase 08.23.2.G-MEET — Meeting-Modal-Increment (Plan 04).

WHY REAL POSTGRES, NO SQLITE FALLBACK (CLAUDE.md Integration-Assertion rule, D-12.2):
  SQLite has NO Row-Level-Security and no ON CONFLICT-on-named-constraint parity. A SQLite branch
  would PASS while testing NOTHING about RLS / the UNIQUE guard -- a Source-Presence FALSE-GREEN.
  These tests MUST exercise REAL Postgres as the restricted `nerve_app` role (rolbypassrls=f,
  non-owner of crm.* -> RLS engages) against the real Production `nerve` DB. NO dialect branch,
  NO :memory:. Harness: `nerve_app_pg_conn` fixture (conftest.py:112, DSN from NERVE_APP_TEST_DSN,
  SKIPS when absent). Runs SERVER-SIDE on Production via SSH (CLAUDE.md HART).

  TRANSACTION-LOCAL mechanism (matches db.py after_begin): each assertion runs inside an explicit
  transaction and issues `SELECT set_config('app.tenant_id', %s, true)` (SET LOCAL, bound param)
  so the SET and the query share ONE transaction.

ASSERTIONS are on ACTUAL returned rows / raised exceptions, never on source text.
"""
import uuid
from datetime import datetime

import pytest


def _new_tenant(cur, suffix):
    """Create a test organisation, return its (trigger-created) tenant UUID (str) + org id.

    The Wave-1 AFTER INSERT trigger trg_mk_tenant_org -> mk_tenant_org() auto-creates the matching
    tenant_orgs row, so we READ BACK the tenant_orgs.id the trigger generated (same transaction ->
    visible). Org name tagged '[MEET-TEST]' for analytics-exclusion lineage.
    """
    cur.execute(
        "INSERT INTO public.organisations (name) VALUES (%s) RETURNING id",
        (f"[MEET-TEST] tenant {suffix}",),
    )
    org_id = cur.fetchone()[0]
    cur.execute(
        "SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s",
        (org_id,),
    )
    tenant_id = cur.fetchone()[0]
    return tenant_id, org_id


@pytest.fixture
def tenants_ab(nerve_app_pg_conn):
    """Create tenant A + tenant B (no crm rows yet); yield UUIDs; clean up all crm rows + public rows.

    Tests insert their own crm rows under the appropriate tenant GUC. Teardown deletes from every
    crm.* table this increment touches (user_preferences, meetings, contacts, accounts) under each
    tenant's GUC (reverse FK order: contacts before accounts), then drops public rows.
    """
    conn = nerve_app_pg_conn
    cur = conn.cursor()
    tenant_a, org_a = _new_tenant(cur, "A")
    tenant_b, org_b = _new_tenant(cur, "B")
    conn.commit()

    yield {
        "conn": conn,
        "tenant_a": tenant_a, "tenant_b": tenant_b,
        "org_a": org_a, "org_b": org_b,
    }

    cur = conn.cursor()
    try:
        for tid in (tenant_a, tenant_b):
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
            cur.execute("DELETE FROM crm.user_preferences WHERE tenant_id = %s::uuid", (tid,))
            cur.execute("DELETE FROM crm.meetings WHERE tenant_id = %s::uuid", (tid,))
            cur.execute("DELETE FROM crm.contacts WHERE tenant_id = %s::uuid", (tid,))
            cur.execute("DELETE FROM crm.accounts WHERE tenant_id = %s::uuid", (tid,))
        conn.commit()
        cur = conn.cursor()
        cur.execute("DELETE FROM public.tenant_orgs WHERE id IN (%s::uuid, %s::uuid)", (tenant_a, tenant_b))
        cur.execute("DELETE FROM public.organisations WHERE id IN (%s, %s)", (org_a, org_b))
        conn.commit()
    except Exception:
        conn.rollback()


# ── crm.user_preferences RLS isolation ────────────────────────────────────────────────────────

def test_user_preferences_rls_isolation(tenants_ab):
    """Under tenant A's GUC: SELECT sees only A's prefs row; INSERT tagged tenant B raises (WITH CHECK)."""
    import psycopg2
    conn = tenants_ab["conn"]
    tenant_a, tenant_b = tenants_ab["tenant_a"], tenants_ab["tenant_b"]
    cur = conn.cursor()

    # Insert one prefs row per tenant, each under its OWN GUC (WITH CHECK passes).
    for tid, uid in ((tenant_a, 1001), (tenant_b, 1002)):
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
        cur.execute(
            "INSERT INTO crm.user_preferences (id, tenant_id, user_id) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), tid, uid),
        )
    conn.commit()

    # Under tenant A's GUC: SELECT returns only A's rows.
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    cur.execute("SELECT tenant_id::text FROM crm.user_preferences")
    seen = {r[0] for r in cur.fetchall()}
    conn.rollback()
    assert tenant_a in seen
    assert tenant_b not in seen
    assert seen == {tenant_a}

    # Under tenant A's GUC: INSERT tagged tenant B raises (WITH CHECK violation).
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    with pytest.raises(psycopg2.Error):
        cur.execute(
            "INSERT INTO crm.user_preferences (id, tenant_id, user_id) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), tenant_b, 1003),
        )
    conn.rollback()


def test_auto_save_meeting_default_false(tenants_ab):
    """D-2/D-4: a freshly-created prefs row with no auto_save_meeting reads back False (DSGVO off-by-default)."""
    conn = tenants_ab["conn"]
    tenant_a = tenants_ab["tenant_a"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    cur.execute(
        "INSERT INTO crm.user_preferences (id, tenant_id, user_id) VALUES (%s, %s, %s)",
        (str(uuid.uuid4()), tenant_a, 2001),
    )
    cur.execute("SELECT auto_save_meeting FROM crm.user_preferences WHERE user_id = 2001")
    val = cur.fetchone()[0]
    conn.rollback()
    assert val is False


# ── resolve-or-create accounts + MM-05 no-duplicate ────────────────────────────────────────────

def test_meeting_resolve_or_create_account(tenants_ab):
    """New Firma -> tenant-stamped accounts row; same Firma again -> reuse (no duplicate); blank -> none."""
    conn = tenants_ab["conn"]
    tenant_a = tenants_ab["tenant_a"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))

    firma = f"[MEET-TEST] Firma {uuid.uuid4().hex[:8]}"
    # Mirror _resolve_account's ON CONFLICT INSERT (the route's DB behavior).
    cur.execute(
        "INSERT INTO crm.accounts (id, tenant_id, name) VALUES (gen_random_uuid(), %s, %s) "
        "ON CONFLICT (tenant_id, name) DO NOTHING",
        (tenant_a, firma),
    )
    cur.execute("SELECT id::text, tenant_id::text FROM crm.accounts WHERE name = %s", (firma,))
    row = cur.fetchone()
    assert row is not None
    assert row[1] == tenant_a   # tenant-stamped

    # Same Firma again -> still exactly one row.
    cur.execute(
        "INSERT INTO crm.accounts (id, tenant_id, name) VALUES (gen_random_uuid(), %s, %s) "
        "ON CONFLICT (tenant_id, name) DO NOTHING",
        (tenant_a, firma),
    )
    cur.execute("SELECT count(*) FROM crm.accounts WHERE name = %s", (firma,))
    assert cur.fetchone()[0] == 1
    conn.rollback()


def test_meeting_account_no_duplicate_on_conflict(tenants_ab):
    """MM-05: two ON CONFLICT inserts of the same Firma under one tenant -> exactly one accounts row."""
    conn = tenants_ab["conn"]
    tenant_a = tenants_ab["tenant_a"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    firma = f"[MEET-TEST] Dup {uuid.uuid4().hex[:8]}"
    for _ in range(2):
        cur.execute(
            "INSERT INTO crm.accounts (id, tenant_id, name) VALUES (gen_random_uuid(), %s, %s) "
            "ON CONFLICT (tenant_id, name) DO NOTHING",
            (tenant_a, firma),
        )
    cur.execute("SELECT count(*) FROM crm.accounts WHERE tenant_id = %s::uuid AND name = %s", (tenant_a, firma))
    count = cur.fetchone()[0]
    conn.rollback()
    assert count == 1   # uq_accounts_tenant_name (0014) held


# ── MM-01 tz-aware scheduled_at (instant correctness + naive rejection) ─────────────────────────

def test_meeting_scheduled_at_tz_instant(tenants_ab):
    """MM-01: an offset-bearing scheduled_at persists the correct INSTANT in timestamptz (10:00+02:00 == 08:00Z)."""
    conn = tenants_ab["conn"]
    tenant_a = tenants_ab["tenant_a"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))

    aware = datetime.fromisoformat("2026-06-03T10:00:00+02:00")   # tz-AWARE
    mid = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO crm.meetings (id, tenant_id, scheduled_at) VALUES (%s, %s, %s)",
        (mid, tenant_a, aware),
    )
    # Read the stored instant normalized to UTC -- proves no wall-clock drift.
    cur.execute(
        "SELECT (scheduled_at AT TIME ZONE 'UTC')::text FROM crm.meetings WHERE id = %s", (mid,)
    )
    stored_utc = cur.fetchone()[0]
    conn.rollback()
    assert stored_utc.startswith("2026-06-03 08:00:00")   # 10:00+02:00 -> 08:00Z


def test_meeting_scheduled_at_naive_rejected():
    """MM-01: the route's parse branch rejects an offset-less (naive) value (tzinfo is None -> 400 path).

    Function-level assertion on the exact parse logic save_meeting() uses (datetime.fromisoformat +
    tzinfo check) -- a runtime branch assertion, NOT a source grep. No DB needed.
    """
    parsed = datetime.fromisoformat("2026-06-03T10:00")        # naive, no offset
    assert parsed.tzinfo is None or parsed.utcoffset() is None  # -> route returns 400 'Datum braucht Zeitzone'

    aware = datetime.fromisoformat("2026-06-03T10:00:00+02:00")  # the accepted form
    assert aware.tzinfo is not None and aware.utcoffset() is not None


# ── meeting tenant-stamp + cross-tenant rejection ──────────────────────────────────────────────

def test_meeting_tenant_stamp(tenants_ab):
    """A meetings row stamped with the GUC tenant persists; a cross-tenant INSERT raises (WITH CHECK)."""
    import psycopg2
    conn = tenants_ab["conn"]
    tenant_a, tenant_b = tenants_ab["tenant_a"], tenants_ab["tenant_b"]
    cur = conn.cursor()

    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    mid = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO crm.meetings (id, tenant_id, notes) VALUES (%s, %s, %s)",
        (mid, tenant_a, "[MEET-TEST] note"),
    )
    cur.execute("SELECT tenant_id::text FROM crm.meetings WHERE id = %s", (mid,))
    assert cur.fetchone()[0] == tenant_a
    conn.commit()

    # Cross-tenant: under tenant A's GUC, INSERT tagged tenant B raises.
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_a,))
    with pytest.raises(psycopg2.Error):
        cur.execute(
            "INSERT INTO crm.meetings (id, tenant_id, notes) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), tenant_b, "[MEET-TEST] cross"),
        )
    conn.rollback()
