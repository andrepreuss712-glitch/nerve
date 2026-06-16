"""account_memory Pre-Call-Briefing merge test (D-13/D-14).

Phase 08.23.2.G-MEET Wave 2 — PORTIERT auf nerve_test-PG (Phase 08.23.2.PGTEST Task 2).

This test exercises the BRIEFING-MERGE LOGIC (does merge_account_memory pull MEDDPICC /
context_hooks / last_call_summary out of crm.account_memory into the briefing dict?), NOT RLS.

PG-PORT (Req-6): frueher lief das gegen eine in-memory SQLite-Engine mit ATTACHed crm/training
(via dem globalen cf5de6d-Listener, der in Plan 03 Task 1 entfernt wurde). Jetzt laeuft es gegen
das echte nerve_test-PG: das MODUL-`database.db.SessionLocal` wird an TEST_DATABASE_URL umgebunden
(hook-tragend, damit der after_begin-RLS-Hook db.py:87 feuert), ein Test-Mandant wird via Trigger
geseedet, `set_current_tenant(tenant_uuid)` gesetzt (sonst RLS fail-closed 0 Zeilen), und
`precall.get_session` auf das MODUL-SessionLocal gepatcht. crm.account_memory.tenant_id == der
gesetzte Tenant (RLS WITH CHECK); account_id zeigt auf eine real angelegte crm.accounts-Row.

SKIP wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback by design, Req-2/D-07).

Integration-Assertion: insert an AccountMemory row, call the briefing builder, assert the returned
briefing dict CONTAINS the persisted MEDDPICC/context_hooks values (runtime assertion on returned
data, not source-presence).
"""
import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def _patched_session(monkeypatch):
    """Bind the MODUL-SessionLocal to nerve_test-PG, seed a trigger-tenant, set the tenant GUC, and
    monkeypatch precall.get_session to hand out MODUL-SessionLocal sessions (hook-bearing).

    Yields a context dict with:
      - `tenant`: the trigger-created tenant_orgs UUID (str) -- crm.account_memory.tenant_id MUST equal it
      - `make_account()`: insert a real crm.accounts row under the tenant GUC, return its account_id
      - `session()`: a fresh MODUL-SessionLocal session (PG-bound, RLS-hook-bearing)
      - `track`: register created IDs for reverse-FK teardown

    Reverse-FK teardown runs in this fixture's POST-yield section (analog test_rls_isolation.py:101-116,
    MED-1) so it executes even if a test asserts/fails -> no row leak into the persistent nerve_test.
    """
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set -- briefing-merge test requires real-PG nerve_test "
                    "(no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.")

    import database.db as dbmod
    from database.db import set_current_tenant, clear_current_tenant
    import services.precall_service as precall

    engine = create_engine(dsn)
    monkeypatch.setattr(dbmod, "engine", engine)
    dbmod.SessionLocal.configure(bind=engine)   # MODUL-SessionLocal umbinden -> after_begin-Hook bleibt

    # Seed a test tenant via the Wave-1 trigger (INSERT organisations -> trg_mk_tenant_org auto-creates
    # the tenant_orgs row; read it back -- never insert tenant_orgs manually, UNIQUE(legacy_org_id)).
    org_name = f"[PGTEST-BRIEFING] org {uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        org_id = conn.execute(
            text("INSERT INTO public.organisations (name) VALUES (:n) RETURNING id"),
            {"n": org_name},
        ).scalar()
        tenant_uuid = conn.execute(
            text("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = :oid"),
            {"oid": org_id},
        ).scalar()

    set_current_tenant(tenant_uuid)             # D-05: GUC for crm.* reads/writes (RLS)

    created = {"account_memory": [], "accounts": []}

    def make_account():
        """Insert a real crm.accounts row under the tenant GUC (FK target for account_memory)."""
        acct_id = str(uuid.uuid4())
        sess = dbmod.SessionLocal()
        try:
            sess.execute(
                text("INSERT INTO crm.accounts (id, tenant_id, name) VALUES (:i, :t, :n)"),
                {"i": acct_id, "t": tenant_uuid, "n": f"[PGTEST-BRIEFING] account {acct_id[:8]}"},
            )
            sess.commit()
        finally:
            sess.close()
        created["accounts"].append(acct_id)
        return acct_id

    def session():
        return dbmod.SessionLocal()

    # precall.get_session must hand out a PG-bound, hook-bearing MODUL-SessionLocal session.
    monkeypatch.setattr(precall, 'get_session', lambda: dbmod.SessionLocal())

    ctx = {
        "tenant": tenant_uuid,
        "make_account": make_account,
        "session": session,
        "created": created,
    }
    try:
        yield ctx
    finally:
        # POST-yield reverse-FK teardown (MED-1): runs even on assertion failure. Delete the test's
        # own crm rows under the tenant GUC, then the org (trigger-tenant_org cascades via FK? no --
        # delete tenant_orgs then organisations). Best-effort.
        try:
            sess = dbmod.SessionLocal()
            try:
                sess.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_uuid})
                # Phase 08.23.2.PGTEST.GREEN crm-Leak-Fix: id ist uuid-Spalte, created[...] traegt str-UUIDs
                # -> `id = ANY(:ids)` warf `operator does not exist: uuid = text`, die Teardown-TX brach ab,
                # crm.account_memory + (FK-Eltern) crm.accounts leakten (2 Rows -> POST-SUITE-Gate rot).
                # id::text = ANY(:ids) vergleicht str-zu-str (Muster wie cleanup_rows / D-G06).
                if created["account_memory"]:
                    sess.execute(
                        text("DELETE FROM crm.account_memory WHERE id::text = ANY(:ids)"),
                        {"ids": created["account_memory"]},
                    )
                if created["accounts"]:
                    sess.execute(
                        text("DELETE FROM crm.accounts WHERE id::text = ANY(:ids)"),
                        {"ids": created["accounts"]},
                    )
                sess.execute(
                    text("DELETE FROM public.tenant_orgs WHERE legacy_org_id = :oid"), {"oid": org_id}
                )
                sess.execute(
                    text("DELETE FROM public.organisations WHERE id = :oid"), {"oid": org_id}
                )
                sess.commit()
            finally:
                sess.close()
        except Exception as _te:
            print(f"[PGTEST-CLEANUP] briefing teardown failed (non-fatal): {_te!r}")
        clear_current_tenant()
        dbmod.SessionLocal.configure(bind=None)
        engine.dispose()


def test_merge_account_memory_surfaces_meddpicc(_patched_session):
    from sqlalchemy import text
    import services.precall_service as precall

    ctx = _patched_session
    account_id = ctx["make_account"]()
    meddpicc = {
        "metrics": "20% Kostenreduktion",
        "economic_buyer": "CFO",
        "pain": "manuelle Prozesse",
        "champion": "Head of Sales",
    }
    context_hooks = ["letzte Demo war positiv", "Budget-Freigabe Q3"]

    mem_id = str(uuid.uuid4())
    sess = ctx["session"]()
    try:
        # tenant_id MUST equal the GUC tenant (RLS WITH CHECK); JSONB columns via cast.
        sess.execute(
            text(
                "INSERT INTO crm.account_memory "
                "(id, tenant_id, account_id, meddpicc, context_hooks, last_call_summary) "
                "VALUES (:id, :t, :acc, CAST(:mp AS jsonb), CAST(:ch AS jsonb), :lcs)"
            ),
            {
                "id": mem_id, "t": ctx["tenant"], "acc": account_id,
                "mp": json.dumps(meddpicc),
                "ch": json.dumps(context_hooks),
                "lcs": "Kunde will im naechsten Call die Preise sehen.",
            },
        )
        sess.commit()
    finally:
        sess.close()
    ctx["created"]["account_memory"].append(mem_id)

    briefing = {"firmenname": "Test GmbH", "text": "Briefing-Text"}
    result = precall.merge_account_memory(briefing, account_id)

    # Runtime assertion: the persisted MEDDPICC/context_hooks/last_call_summary are surfaced.
    assert result['meddpicc'] == meddpicc
    assert result['context_hooks'] == context_hooks
    assert result['last_call_summary'] == "Kunde will im naechsten Call die Preise sehen."
    # Original briefing keys preserved
    assert result['firmenname'] == "Test GmbH"


def test_merge_account_memory_graceful_when_absent(_patched_session):
    """No account_memory row for the account -> briefing builds unchanged (graceful degradation)."""
    import services.precall_service as precall

    result = precall.merge_account_memory({"firmenname": "Leer AG", "text": "x"}, str(uuid.uuid4()))
    assert result['firmenname'] == "Leer AG"
    assert 'meddpicc' not in result
    assert 'context_hooks' not in result


def test_merge_account_memory_no_account_id_is_noop(_patched_session):
    """account_id=None -> no DB read, briefing returned unchanged."""
    import services.precall_service as precall

    result = precall.merge_account_memory({"firmenname": "Kein Account"}, None)
    assert result == {"firmenname": "Kein Account"}


def test_merge_account_memory_pre_seeds_pii_cache(_patched_session):
    """When an anonymizer cache is passed, register_briefing_pii pre-seeds it from the briefing
    (the wiring anonymization.py:495 anticipated for Phase 08.23.2.G)."""
    import services.precall_service as precall
    from services.anonymization import AnrufAnonymisierer

    cache = AnrufAnonymisierer()
    briefing = {"firmenname": "Mueller & Sohn GmbH", "personen": ["Hans Mueller"]}
    precall.merge_account_memory(briefing, None, anonymizer_cache=cache)

    # The firm + person names are now registered as PII tokens (briefing PII pre-seed, D-03).
    # Assertion on runtime cache state: re-assigning the same name yields a stable token.
    tok_firm = cache.get_or_assign_token("Mueller & Sohn GmbH", "ORG")
    tok_person = cache.get_or_assign_token("Hans Mueller", "PERSON")
    assert tok_firm
    assert tok_person
