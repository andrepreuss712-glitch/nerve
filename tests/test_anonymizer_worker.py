"""Anonymizer worker Integration-Assertion test (Phase 08.23.2.G-MEET Wave 3, D-15/D-16/D-17).

TWO GROUPS, by what they prove:

1. LOGIC GROUP (in-memory SQLite, built from the ORM models + a hand-created transcript_archive).
   Proves the MERGE/FILTER/HASH/GATING logic — behavior that breaks without a source change:
   transcript_archive rows written, anonymized_at stamped, is_test_user calls excluded,
   source_call_hash is a one-way hash (no raw id), should_persist() drops ART9/error snippets.
   SQLite has NO Row-Level-Security, so RLS is explicitly NOT tested here (a SQLite RLS branch
   would be a Source-Presence FALSE-GREEN — CLAUDE.md). The heavy NLP pipeline is never loaded:
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
import itertools
import uuid
from datetime import datetime, timezone

import pytest

# TranscriptSegment.id is BigInteger (BIGSERIAL on PG) — SQLite only auto-increments INTEGER PRIMARY
# KEY, not BIGINT, so we assign explicit ids in the in-memory logic group. Process-global counter
# guarantees uniqueness within each (per-test, fresh) in-memory DB.
_seg_id = itertools.count(1)

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
# LOGIC GROUP
# ──────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mem_engine():
    """In-memory SQLite with `crm` and `training` ATTACHed as schemas (the crm/training models are
    schema-qualified). StaticPool keeps the ATTACH, create_all and every connection on ONE DBAPI
    connection. training.transcript_archive is raw DDL (migration 0008), not an ORM model, so we
    create it by hand to mirror its 0008 shape."""
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.pool import StaticPool
    from database.db import Base
    import database.models  # noqa: F401 (registers crm.* + training.* on Base.metadata)

    engine = create_engine(
        "sqlite://",
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach(dbapi_conn, _rec):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS crm")
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS training")

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS training.transcript_archive (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                source_call_hash TEXT    NOT NULL,
                segment_index    INTEGER NOT NULL,
                speaker          TEXT    NOT NULL,
                text             TEXT    NOT NULL,
                ts_offset_ms     INTEGER NOT NULL,
                schema_version   SMALLINT NOT NULL DEFAULT 1,
                archived_at      TIMESTAMP
            )
            """
        ))
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_account(engine, *, is_test_user=False, stamped=False, segments=None, tenant_id=None):
    """Seed one org/user/conversation_log/call/account/account_memory chain (+ optional transcript
    segments) and return (account_memory_id, account_id, call_id). `segments` is a list of
    (ts_ms, speaker, text); when None the account has no transcript material."""
    from sqlalchemy.orm import sessionmaker
    from database.models import (
        Organisation, User, ConversationLog, Call, TranscriptSegment, Account, AccountMemory,
    )
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        tid = tenant_id or str(uuid.uuid4())
        org = Organisation(name="[ANON-TEST] org")
        s.add(org)
        s.flush()
        user = User(org_id=org.id, email=f"anon-test-{uuid.uuid4().hex[:8]}@nerve.local",
                    is_test_user=is_test_user)
        s.add(user)
        s.flush()
        clog = ConversationLog(user_id=user.id, org_id=org.id, started_at=datetime.now())
        s.add(clog)
        s.flush()
        acct_id = str(uuid.uuid4())
        call_id = str(uuid.uuid4())
        s.add(Account(id=acct_id, tenant_id=tid, name="[ANON-TEST] account"))
        # call_mode CHECK is ('cold_call','meeting_consented') — see ck_calls_call_mode.
        s.add(Call(id=call_id, user_id=user.id, account_id=acct_id, call_mode='cold_call',
                   conversation_log_id=clog.id))
        if segments:
            for ts_ms, speaker, seg_text in segments:
                s.add(TranscriptSegment(id=next(_seg_id), conversation_log_id=clog.id, ts_ms=ts_ms,
                                        speaker=speaker, text=seg_text))
        mem_id = str(uuid.uuid4())
        s.add(AccountMemory(
            id=mem_id, tenant_id=tid, account_id=acct_id,
            meddpicc={}, context_hooks=[],
            anonymized_at=(datetime.now(timezone.utc) if stamped else None),
        ))
        s.commit()
        return mem_id, acct_id, call_id
    finally:
        s.close()


def _run(engine, dry_run=False):
    with engine.connect() as conn:
        stats = process_unstamped(conn, dry_run=dry_run, anonymize_fn=_fake_anonymize)
        if not dry_run:
            conn.commit()
    return stats


def _archive_rows(engine):
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT source_call_hash, segment_index, speaker, text FROM training.transcript_archive "
            "ORDER BY source_call_hash, segment_index"
        )).fetchall()


def _anonymized_at(engine, mem_id):
    from sqlalchemy import text
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT anonymized_at FROM crm.account_memory WHERE id = :id"), {'id': mem_id}
        ).scalar()


def test_worker_processes_unstamped(mem_engine):
    """A normal unstamped row with transcript material -> anonymized segments written to
    transcript_archive (Mueller rewritten), and anonymized_at stamped. The 'GEHEIM' segment is
    dropped by should_persist() -> 2 of 3 segments persisted."""
    mem_id, _acct, call_id = _seed_account(
        mem_engine,
        segments=[(0, 'berater', "Herr Mueller will kaufen"),
                  (10, 'kunde', "Diagnose GEHEIM Information"),
                  (20, 'berater', "Zweiter Punkt ohne PII")],
    )
    stats = _run(mem_engine)

    assert stats['candidates'] == 1
    assert stats['stamped'] == 1
    rows = [r for r in _archive_rows(mem_engine) if r[0] == _hash_call_id(call_id)]
    assert len(rows) == 2                                  # GEHEIM snippet dropped by should_persist
    texts = [r[3] for r in rows]
    assert "Herr [PERSON_A] will kaufen" in texts          # anonymization actually rewrote the text
    assert all('GEHEIM' not in t for t in texts)           # ART9 snippet never persisted
    assert _anonymized_at(mem_engine, mem_id) is not None   # Variante A stamp applied


def test_worker_skips_stamped(mem_engine):
    """An already-stamped row is NOT reselected (idempotent) -> its segments are never written."""
    _mem_id, _acct, call_id = _seed_account(
        mem_engine, stamped=True,
        segments=[(0, 'berater', "Bereits anonymisiert Mueller")],
    )
    stats = _run(mem_engine)

    assert stats['candidates'] == 0                         # stamped row not selected
    assert all(r[0] != _hash_call_id(call_id) for r in _archive_rows(mem_engine))


def test_worker_filters_test_user(mem_engine):
    """A row whose source call belongs to an is_test_user user is NOT written to training (no test
    data into the foundation), though the row is still stamped (evaluated)."""
    mem_id, _acct, call_id = _seed_account(
        mem_engine, is_test_user=True,
        segments=[(0, 'berater', "Test User Mueller Gespraech")],
    )
    stats = _run(mem_engine)

    assert stats['skipped_test_user'] == 1
    assert all(r[0] != _hash_call_id(call_id) for r in _archive_rows(mem_engine))  # nothing written
    assert _anonymized_at(mem_engine, mem_id) is not None                          # still stamped


def test_no_crm_id_in_training(mem_engine):
    """Written transcript_archive rows store source_call_hash (a SHA-256 hash), NEVER a raw crm/call
    id -> no re-identification surface (D-17)."""
    mem_id, acct_id, call_id = _seed_account(
        mem_engine, segments=[(0, 'berater', "Ein Satz ohne GEHEIM")],
    )
    _run(mem_engine)

    rows = _archive_rows(mem_engine)
    assert rows, "expected at least one archived segment"
    hashes = {r[0] for r in rows}
    expected = hashlib.sha256(str(call_id).encode('utf-8')).hexdigest()
    assert hashes == {expected}
    for h in hashes:
        assert len(h) == 64 and all(c in '0123456789abcdef' for c in h)  # sha256 hex
        assert h not in (str(call_id), str(acct_id), str(mem_id))         # never a raw id


def test_dry_run_writes_nothing(mem_engine):
    """--dry-run reports candidates but writes no transcript_archive rows and stamps nothing."""
    mem_id, _acct, _call = _seed_account(
        mem_engine, segments=[(0, 'berater', "Mueller Satz")],
    )
    stats = _run(mem_engine, dry_run=True)

    assert stats['candidates'] == 1
    assert stats['archived_segments'] == 0
    assert _archive_rows(mem_engine) == []
    assert _anonymized_at(mem_engine, mem_id) is None       # not stamped in dry-run


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
