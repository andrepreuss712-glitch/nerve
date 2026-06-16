"""Anonymizer worker Integration-Assertion test (Phase 08.23.2.G-MEET Wave 3, D-15/D-16/D-17).

TWO GROUPS, by what they prove:

1. LOGIC GROUP (REAL Postgres nerve_test — PORTIERT in Phase 08.23.2.PGTEST Task 2; frueher
   in-memory SQLite). Proves the MERGE/FILTER/HASH/GATING logic — behavior that breaks without a
   source change: transcript_archive rows written, anonymized_at stamped, is_test_user calls
   excluded, source_call_hash is a one-way hash (no raw id), should_persist() drops ART9/error
   snippets. RLS is NOT the subject here (the _fake_anonymize stub keeps the NLP out). Because
   training.* is the DPO vault that nerve_app may NOT touch (CONTEXT.md:111), the WRITE path runs as
   nerve_anon_worker (anon_worker_pg_engine) while the crm.* chain is seeded as nerve_app under the
   tenant GUC (nerve_app_pg_conn) — same two-role harness as the RLS group, scoped via limit_ids.
   SKIP when either DSN is absent (no SQLite fallback). The heavy NLP pipeline is never loaded:
   anonymize() is injected as a deterministic stub.

2. RLS GROUP (REAL Postgres, NO SQLite fallback — same harness style as test_rls_isolation.py).
   Two roles against the real `nerve` DB: `nerve_app` (psycopg2, seeds + the no-leak assertion) and
   `nerve_anon_worker` (SQLAlchemy engine, runs the worker's OWN process_unstamped code path, sets
   NO app.tenant_id). Proves the 0013 worker policies: (a) the worker SELECTs account_memory rows
   from TWO different tenants cross-tenant (anon_worker_read), (b) its anonymized_at stamp PERSISTS
   on both (anon_worker_stamp passes FORCE RLS), (c) a SECOND run selects neither (idempotency — the
   stamp took), (d) nerve_app stays tenant-scoped (the worker policies, being TO nerve_anon_worker,
   do NOT leak cross-tenant rows to the app role — no Wave-2 isolation regression).
   The seeded rows have NO source calls, so the worker writes NOTHING to training.transcript_archive
   (neither role can DELETE from training, so this keeps the prod training foundation un-polluted);
   the WRITE path is covered by the logic group. process_unstamped is called with limit_ids scoped
   to the seeded rows so the test has ZERO blast radius on real Production data.

Run server-side on Production (CLAUDE.md HART: pytest via SSH, real PG; no local pytest).
"""
import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from scripts.anonymizer_worker import process_unstamped, _hash_call_id


# ════════════════════════════════════════════════════════════════════════════════════════════
# Deterministic anonymize() stub for the logic group (no NLP load).
#   - any segment containing 'GEHEIM' -> ('[ART9_REDACTED]', 'C')  => should_persist() drops it
#   - otherwise 'Mueller' -> '[PERSON_A]' (proves anonymization actually rewrites the text)
# ════════════════════════════════════════════════════════════════════════════════════════════
def _fake_anonymize(text_in, _cache):
    if 'GEHEIM' in text_in:
        return ('[ART9_REDACTED]', 'C')
    return (text_in.replace('Mueller', '[PERSON_A]'), 'A')


# ──────────────────────────────────────────────────────────────────────────────────────────────
# LOGIC GROUP — PORTIERT auf nerve_test-PG (Phase 08.23.2.PGTEST Task 2)
# ──────────────────────────────────────────────────────────────────────────────────────────────
# Frueher lief die Logic-Group gegen eine in-memory SQLite-Engine mit ATTACHed crm/training (via dem
# globalen cf5de6d-Listener, der in Plan 03 Task 1 entfernt wurde). Sie pruft die MERGE/FILTER/HASH/
# GATING-Logik (NICHT RLS — der _fake_anonymize-Stub haelt das NLP raus).
#
# PG-PORT + ROLLEN-NOTWENDIGKEIT (Deviation Rule 3, im SUMMARY dokumentiert): training.* ist der
# DPO-Tresor — nerve_app hat KEINEN Zugriff (CONTEXT.md:111, TAXO3-OQ-1: "permission denied for
# schema training"). Die Worker-Schreib-Logik (INSERT training.transcript_archive) kann daher NICHT
# als nerve_app laufen. Korrekter PG-Port = exakt die Rollen-Aufteilung der RLS-Gruppe unten:
#   - SEEDEN der crm.*-Kette als `nerve_app` unter dem Tenant-GUC (RLS WITH CHECK) — nerve_app_pg_conn
#   - LAUFEN von process_unstamped als `nerve_anon_worker` (die EINZIGE Rolle mit training-Write +
#     cross-tenant-crm-Read) — anon_worker_pg_engine, mit limit_ids auf die test-eigenen mem_ids
#     gescoped (zero blast radius + deterministische candidates-Counts auf der persistenten nerve_test).
# Wenn eine der DSNs fehlt -> SKIP (kein sqlite-Fallback). Reverse-FK-Teardown in der Fixture-POST-yield-
# Sektion (MED-1) raeumt crm.* + training.transcript_archive auf 0 (POST-SUITE-Check Plan 02 #4 faengt Leak).


def _seed_pg_account(cur, tenant_id, *, is_test_user=False, stamped=False, segments=None):
    """As nerve_app (psycopg2 cur), seed one org/user/conversation_log/call/account/account_memory
    chain (+ optional transcript segments) UNDER the given tenant GUC. Returns
    (account_memory_id, account_id, call_id). `segments` = list of (ts_ms, speaker, text)."""
    # public.* (no GUC needed): org/user/conversation_log/call/transcript_segments.
    cur.execute("INSERT INTO public.organisations (name) VALUES (%s) RETURNING id",
                ("[ANON-TEST] org",))
    org_id = cur.fetchone()[0]
    # GREEN Wave-4: is_superadmin/market/language sind NOT NULL OHNE server_default (ORM-default greift
    # bei rohem psycopg2-INSERT nicht) -> explizit setzen, sonst NotNullViolation im Seed (inspect.sh schema users).
    cur.execute(
        "INSERT INTO public.users (org_id, email, is_test_user, is_superadmin, market, language) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (org_id, f"anon-test-{uuid.uuid4().hex[:8]}@nerve.local", is_test_user, False, 'dach', 'de'),
    )
    user_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO public.conversation_logs (user_id, org_id, started_at) VALUES (%s, %s, %s) "
        "RETURNING id",
        (user_id, org_id, datetime.now()),
    )
    clog_id = cur.fetchone()[0]
    acct_id = str(uuid.uuid4())
    call_id = str(uuid.uuid4())
    # call_mode CHECK is ('cold_call','meeting_consented') — see ck_calls_call_mode.
    cur.execute(
        "INSERT INTO public.calls (id, user_id, account_id, call_mode, conversation_log_id) "
        "VALUES (%s, %s, %s, %s, %s)",
        (call_id, user_id, acct_id, 'cold_call', clog_id),
    )
    if segments:
        for ts_ms, speaker, seg_text in segments:
            # id is BIGSERIAL on PG -> let the sequence assign it (NO explicit id, Klasse-D-Hinweis).
            cur.execute(
                "INSERT INTO public.transcript_segments (conversation_log_id, ts_ms, speaker, text) "
                "VALUES (%s, %s, %s, %s)",
                (clog_id, ts_ms, speaker, seg_text),
            )
    # crm.* under the tenant GUC (RLS WITH CHECK: tenant_id = current_setting('app.tenant_id')).
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
    cur.execute("INSERT INTO crm.accounts (id, tenant_id, name) VALUES (%s, %s, %s)",
                (acct_id, tenant_id, "[ANON-TEST] account"))
    mem_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks, "
        "anonymized_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (mem_id, tenant_id, acct_id, '{}', '[]',
         (datetime.now(timezone.utc) if stamped else None)),
    )
    return mem_id, acct_id, call_id, org_id


@pytest.fixture
def logic_ctx(nerve_app_pg_conn, anon_worker_pg_engine):
    """nerve_test-PG harness for the logic group. Seeds crm.* as nerve_app under a trigger-tenant GUC,
    runs the worker as nerve_anon_worker (training-write + cross-tenant), tracks created IDs, and
    tears everything down reverse-FK in the POST-yield section (MED-1, runs even on assertion failure).

    Yields a context with:
      - seed(...): seed one account chain, return (mem_id, acct_id, call_id)
      - run(...): run process_unstamped as nerve_anon_worker, scoped to the seeded mem_ids
      - archive_rows(): SELECT the test's own training.transcript_archive rows (by source_call_hash)
      - anonymized_at(mem_id): read the crm.account_memory stamp (as nerve_app under the tenant GUC)
    """
    from sqlalchemy import text
    conn = nerve_app_pg_conn       # psycopg2 as nerve_app (seeds + reads crm under GUC)
    engine = anon_worker_pg_engine  # SQLAlchemy as nerve_anon_worker (runs the worker code path)
    cur = conn.cursor()

    # Trigger-tenant: INSERT organisations -> trg_mk_tenant_org auto-creates tenant_orgs; read it back.
    cur.execute("INSERT INTO public.organisations (name) VALUES (%s) RETURNING id",
                (f"[ANON-TEST] tenant {uuid.uuid4().hex[:8]}",))
    tenant_org_id = cur.fetchone()[0]
    cur.execute("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s", (tenant_org_id,))
    tenant_id = cur.fetchone()[0]
    conn.commit()

    created = {"mem_ids": [], "acct_ids": [], "call_ids": [], "org_ids": [tenant_org_id]}

    def seed(*, is_test_user=False, stamped=False, segments=None):
        mem_id, acct_id, call_id, org_id = _seed_pg_account(
            cur, tenant_id, is_test_user=is_test_user, stamped=stamped, segments=segments)
        conn.commit()
        created["mem_ids"].append(mem_id)
        created["acct_ids"].append(acct_id)
        created["call_ids"].append(call_id)
        created["org_ids"].append(org_id)
        return mem_id, acct_id, call_id

    def run(dry_run=False):
        # Scope to the test's own seeded rows: deterministic candidates count on persistent nerve_test
        # + zero blast radius. The worker (nerve_anon_worker) reads cross-tenant via anon_worker_read.
        ids = list(created["mem_ids"])
        with engine.connect() as wconn:
            stats = process_unstamped(wconn, dry_run=dry_run, anonymize_fn=_fake_anonymize,
                                      limit_ids=ids)
            if not dry_run:
                wconn.commit()
        return stats

    def archive_rows():
        # As nerve_anon_worker (the role that can read training), restricted to the test's own hashes.
        own_hashes = [_hash_call_id(c) for c in created["call_ids"]]
        with engine.connect() as wconn:
            return wconn.execute(
                text(
                    "SELECT source_call_hash, segment_index, speaker, text "
                    "FROM training.transcript_archive WHERE source_call_hash = ANY(:h) "
                    "ORDER BY source_call_hash, segment_index"
                ),
                {"h": own_hashes},
            ).fetchall()

    def anonymized_at(mem_id):
        # As nerve_app under the tenant GUC (RLS-scoped read of the stamp).
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
        cur.execute("SELECT anonymized_at FROM crm.account_memory WHERE id = %s::uuid", (mem_id,))
        val = cur.fetchone()[0]
        conn.rollback()  # end the read transaction; SET LOCAL discarded
        return val

    ctx = {
        "tenant": tenant_id, "created": created,
        "seed": seed, "run": run, "archive_rows": archive_rows, "anonymized_at": anonymized_at,
    }
    try:
        yield ctx
    finally:
        # POST-yield reverse-FK teardown (MED-1): runs even on assertion failure -> no leak.
        # training.transcript_archive: DELETE as nerve_anon_worker? It has only column-UPDATE on crm
        # and SELECT on training (no DELETE) -> the worker role canNOT clean training. So we delete
        # training rows as nerve_app IF it has the grant; otherwise the POST-SUITE-Check (Plan 02 #4)
        # is the fail-closed backstop. We attempt via the worker engine first, best-effort.
        own_hashes = [_hash_call_id(c) for c in created["call_ids"]]
        try:
            with engine.begin() as wconn:
                if own_hashes:
                    wconn.execute(
                        text("DELETE FROM training.transcript_archive WHERE source_call_hash = ANY(:h)"),
                        {"h": own_hashes},
                    )
        except Exception as _we:
            print(f"[PGTEST-CLEANUP] training teardown (anon_worker) failed (non-fatal): {_we!r}")
        try:
            c2 = conn.cursor()
            c2.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
            if created["mem_ids"]:
                c2.execute("DELETE FROM crm.account_memory WHERE id = ANY(%s::uuid[])",
                           ([str(m) for m in created["mem_ids"]],))
            if created["acct_ids"]:
                c2.execute("DELETE FROM crm.accounts WHERE id = ANY(%s::uuid[])",
                           ([str(a) for a in created["acct_ids"]],))
            conn.commit()
            c3 = conn.cursor()
            # public reverse-FK: calls -> transcript_segments(by clog) -> conversation_logs -> users
            # -> tenant_orgs -> organisations. Delete by org lineage (test-own org_ids only).
            org_ids = [o for o in created["org_ids"]]
            if created["call_ids"]:
                c3.execute("DELETE FROM public.calls WHERE id = ANY(%s::uuid[])",
                           ([str(c) for c in created["call_ids"]],))
            c3.execute(
                "DELETE FROM public.transcript_segments WHERE conversation_log_id IN "
                "(SELECT id FROM public.conversation_logs WHERE org_id = ANY(%s))", (org_ids,))
            c3.execute("DELETE FROM public.conversation_logs WHERE org_id = ANY(%s)", (org_ids,))
            c3.execute("DELETE FROM public.users WHERE org_id = ANY(%s)", (org_ids,))
            c3.execute("DELETE FROM public.tenant_orgs WHERE legacy_org_id = ANY(%s)", (org_ids,))
            c3.execute("DELETE FROM public.organisations WHERE id = ANY(%s)", (org_ids,))
            conn.commit()
        except Exception as _te:
            print(f"[PGTEST-CLEANUP] anonymizer logic teardown failed (non-fatal): {_te!r}")
            try:
                conn.rollback()
            except Exception:
                pass


def test_worker_processes_unstamped(logic_ctx):
    """A normal unstamped row with transcript material -> anonymized segments written to
    transcript_archive (Mueller rewritten), and anonymized_at stamped. The 'GEHEIM' segment is
    dropped by should_persist() -> 2 of 3 segments persisted."""
    mem_id, _acct, call_id = logic_ctx["seed"](
        segments=[(0, 'berater', "Herr Mueller will kaufen"),
                  (10, 'kunde', "Diagnose GEHEIM Information"),
                  (20, 'berater', "Zweiter Punkt ohne PII")],
    )
    stats = logic_ctx["run"]()

    assert stats['candidates'] == 1
    assert stats['stamped'] == 1
    rows = [r for r in logic_ctx["archive_rows"]() if r[0] == _hash_call_id(call_id)]
    assert len(rows) == 2                                  # GEHEIM snippet dropped by should_persist
    texts = [r[3] for r in rows]
    assert "Herr [PERSON_A] will kaufen" in texts          # anonymization actually rewrote the text
    assert all('GEHEIM' not in t for t in texts)           # ART9 snippet never persisted
    assert logic_ctx["anonymized_at"](mem_id) is not None   # Variante A stamp applied


def test_worker_skips_stamped(logic_ctx):
    """An already-stamped row is NOT reselected (idempotent) -> its segments are never written."""
    _mem_id, _acct, call_id = logic_ctx["seed"](
        stamped=True, segments=[(0, 'berater', "Bereits anonymisiert Mueller")],
    )
    stats = logic_ctx["run"]()

    assert stats['candidates'] == 0                         # stamped row not selected
    assert all(r[0] != _hash_call_id(call_id) for r in logic_ctx["archive_rows"]())


def test_worker_filters_test_user(logic_ctx):
    """A row whose source call belongs to an is_test_user user is NOT written to training (no test
    data into the foundation), though the row is still stamped (evaluated)."""
    mem_id, _acct, call_id = logic_ctx["seed"](
        is_test_user=True, segments=[(0, 'berater', "Test User Mueller Gespraech")],
    )
    stats = logic_ctx["run"]()

    assert stats['skipped_test_user'] == 1
    assert all(r[0] != _hash_call_id(call_id) for r in logic_ctx["archive_rows"]())  # nothing written
    assert logic_ctx["anonymized_at"](mem_id) is not None                            # still stamped


def test_no_crm_id_in_training(logic_ctx):
    """Written transcript_archive rows store source_call_hash (a SHA-256 hash), NEVER a raw crm/call
    id -> no re-identification surface (D-17)."""
    mem_id, acct_id, call_id = logic_ctx["seed"](
        segments=[(0, 'berater', "Ein Satz ohne PII")],
    )
    logic_ctx["run"]()

    rows = logic_ctx["archive_rows"]()
    assert rows, "expected at least one archived segment"
    hashes = {r[0] for r in rows}
    expected = hashlib.sha256(str(call_id).encode('utf-8')).hexdigest()
    assert hashes == {expected}
    for h in hashes:
        assert len(h) == 64 and all(c in '0123456789abcdef' for c in h)  # sha256 hex
        assert h not in (str(call_id), str(acct_id), str(mem_id))         # never a raw id


def test_dry_run_writes_nothing(logic_ctx):
    """--dry-run reports candidates but writes no transcript_archive rows and stamps nothing."""
    mem_id, _acct, _call = logic_ctx["seed"](
        segments=[(0, 'berater', "Mueller Satz")],
    )
    stats = logic_ctx["run"](dry_run=True)

    assert stats['candidates'] == 1
    assert stats['archived_segments'] == 0
    assert logic_ctx["archive_rows"]() == []
    assert logic_ctx["anonymized_at"](mem_id) is None       # not stamped in dry-run


# ──────────────────────────────────────────────────────────────────────────────────────────────
# RLS GROUP (REAL Postgres, two roles, NO SQLite fallback)
# ──────────────────────────────────────────────────────────────────────────────────────────────
def _seed_pg_tenant(cur, suffix):
    """As nerve_app: create a [ANON-RLS-TEST] org (the Wave-1 trigger auto-creates its tenant_orgs
    row); read back tenant_orgs.id. Returns (tenant_id_str, org_id)."""
    cur.execute(
        "INSERT INTO public.organisations (name) VALUES (%s) RETURNING id",
        (f"[ANON-RLS-TEST] tenant {suffix}",),
    )
    org_id = cur.fetchone()[0]
    cur.execute("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s", (org_id,))
    return cur.fetchone()[0], org_id


@pytest.fixture
def two_tenant_memories(nerve_app_pg_conn):
    """As nerve_app: seed an unstamped crm.account_memory row under each of TWO tenants (each with a
    real crm.accounts parent, inserted under that tenant's GUC so the Wave-2 WITH CHECK passes). The
    rows have NO source calls, so the worker writes nothing to training (un-pollutable). Clean up in
    teardown (reverse FK order, under each tenant GUC)."""
    conn = nerve_app_pg_conn
    cur = conn.cursor()
    tenant_a, org_a = _seed_pg_tenant(cur, "A")
    tenant_b, org_b = _seed_pg_tenant(cur, "B")

    mem_a, mem_b = str(uuid.uuid4()), str(uuid.uuid4())
    acct_a, acct_b = str(uuid.uuid4()), str(uuid.uuid4())
    for tid, acct_id, mem_id in ((tenant_a, acct_a, mem_a), (tenant_b, acct_b, mem_b)):
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
        cur.execute("INSERT INTO crm.accounts (id, tenant_id, name) VALUES (%s, %s, %s)",
                    (acct_id, tid, f"[ANON-RLS-TEST] account {tid[:8]}"))
        cur.execute(
            "INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks) "
            "VALUES (%s, %s, %s, %s, %s)",
            (mem_id, tid, acct_id, '{}', '[]'),
        )
    conn.commit()

    yield {"conn": conn, "tenant_a": tenant_a, "tenant_b": tenant_b,
           "mem_a": mem_a, "mem_b": mem_b, "org_a": org_a, "org_b": org_b}

    cur = conn.cursor()
    try:
        for tid in (tenant_a, tenant_b):
            cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
            cur.execute("DELETE FROM crm.account_memory WHERE tenant_id = %s::uuid", (tid,))
            cur.execute("DELETE FROM crm.accounts WHERE tenant_id = %s::uuid", (tid,))
        conn.commit()
        cur = conn.cursor()
        cur.execute("DELETE FROM public.tenant_orgs WHERE id IN (%s::uuid, %s::uuid)", (tenant_a, tenant_b))
        cur.execute("DELETE FROM public.organisations WHERE id IN (%s, %s)", (org_a, org_b))
        conn.commit()
    except Exception:
        conn.rollback()


def _worker_anonymized_at(engine, mem_id):
    """As nerve_anon_worker: read anonymized_at for a row (the worker can SELECT cross-tenant)."""
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT anonymized_at FROM crm.account_memory WHERE id = :id"), {'id': mem_id}
        ).scalar()


def test_worker_cross_tenant_read_and_stamp_persists(anon_worker_pg_engine, two_tenant_memories):
    """As nerve_anon_worker (NO app.tenant_id), the worker SELECTs unstamped account_memory rows
    from BOTH tenants (cross-tenant, anon_worker_read) and its anonymized_at stamp PERSISTS on both
    (anon_worker_stamp passes FORCE RLS). A SECOND run selects neither (idempotency — the stamp
    took; a SELECT-only non-persisting fix would re-select them)."""
    t = two_tenant_memories
    engine = anon_worker_pg_engine

    # First run, scoped to the two seeded rows (zero blast radius on real prod data).
    with engine.connect() as conn:
        stats1 = process_unstamped(conn, anonymize_fn=_fake_anonymize, limit_ids=[t["mem_a"], t["mem_b"]])
        conn.commit()
    assert stats1['candidates'] == 2            # saw BOTH tenants' rows cross-tenant (anon_worker_read)
    assert stats1['stamped'] == 2

    # Stamp persisted on both (anon_worker_stamp let the UPDATE through FORCE RLS).
    assert _worker_anonymized_at(engine, t["mem_a"]) is not None
    assert _worker_anonymized_at(engine, t["mem_b"]) is not None

    # Second run: both now stamped -> selected by neither (idempotent).
    with engine.connect() as conn:
        stats2 = process_unstamped(conn, anonymize_fn=_fake_anonymize, limit_ids=[t["mem_a"], t["mem_b"]])
        conn.commit()
    assert stats2['candidates'] == 0
    assert stats2['stamped'] == 0


def test_nerve_app_still_tenant_scoped(two_tenant_memories):
    """After the 0013 worker policies exist, nerve_app inside tenant_A's GUC sees ONLY tenant_A's
    account_memory row -- the worker policies (TO nerve_anon_worker) do NOT leak cross-tenant rows
    to the app role (no Wave-2 isolation regression)."""
    t = two_tenant_memories
    conn = t["conn"]
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.tenant_id', %s, true)", (t["tenant_a"],))
    cur.execute("SELECT id::text FROM crm.account_memory WHERE id IN (%s::uuid, %s::uuid)",
                (t["mem_a"], t["mem_b"]))
    seen = {r[0] for r in cur.fetchall()}
    conn.rollback()

    assert t["mem_a"] in seen          # own-tenant row visible
    assert t["mem_b"] not in seen      # cross-tenant row NOT visible to nerve_app (no leak)
