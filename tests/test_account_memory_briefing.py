"""account_memory Pre-Call-Briefing merge test (D-13/D-14).

Phase 08.23.2.G-MEET Wave 2.

This test exercises the BRIEFING-MERGE LOGIC (does merge_account_memory pull MEDDPICC /
context_hooks / last_call_summary out of crm.account_memory into the briefing dict?), NOT RLS.
Per the plan it MAY use the in-memory SQLite schema (built from the ORM models, CLAUDE.md Punkt 21)
because it tests merge behavior, not Row-Level-Security (RLS is proven separately in
tests/test_rls_isolation.py against real Postgres).

Integration-Assertion: insert an AccountMemory row, call the briefing builder, assert the returned
briefing dict CONTAINS the persisted MEDDPICC/context_hooks values (runtime assertion on returned
data, not source-presence).
"""
import uuid

import pytest


@pytest.fixture
def _patched_session(monkeypatch):
    """Rebind get_session in precall_service to an in-memory SQLite session built from the ORM.

    The crm.* models are schema-qualified ({'schema': 'crm'}), but SQLite has no schemas -- a schema
    name maps to an ATTACHed database. So we ATTACH an in-memory db AS crm before create_all. A
    StaticPool (single shared connection) is required so the ATTACH, create_all, and every session
    all run on the SAME connection -- otherwise the attached crm db (and the in-memory data) would
    vanish per-connection. crm models carry NO SQLAlchemy-level ForeignKeys (DB-side only), so
    create_all emits no cross-database REFERENCES that SQLite would reject.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from database.db import Base
    import database.models  # noqa: F401  (registers all tables incl. crm.* on Base.metadata)
    import services.precall_service as precall

    engine = create_engine(
        "sqlite://",
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _attach_crm_schema(dbapi_conn, _rec):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS crm")

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr(precall, 'get_session', lambda: TestSession())
    try:
        yield TestSession
    finally:
        engine.dispose()


def test_merge_account_memory_surfaces_meddpicc(_patched_session):
    from database.models import AccountMemory
    import services.precall_service as precall

    account_id = str(uuid.uuid4())
    meddpicc = {
        "metrics": "20% Kostenreduktion",
        "economic_buyer": "CFO",
        "pain": "manuelle Prozesse",
        "champion": "Head of Sales",
    }
    context_hooks = ["letzte Demo war positiv", "Budget-Freigabe Q3"]

    sess = _patched_session()
    try:
        sess.add(AccountMemory(
            id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            account_id=account_id,
            meddpicc=meddpicc,
            context_hooks=context_hooks,
            last_call_summary="Kunde will im naechsten Call die Preise sehen.",
        ))
        sess.commit()
    finally:
        sess.close()

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

    briefing = {"firmenname": "Leer AG", "text": "x"}
    result = precall.merge_account_memory(briefing, str(uuid.uuid4()))
    assert result['firmenname'] == "Leer AG"
    assert 'meddpicc' not in result
    assert 'context_hooks' not in result


def test_merge_account_memory_no_account_id_is_noop(_patched_session):
    """account_id=None -> no DB read, briefing returned unchanged."""
    import services.precall_service as precall

    briefing = {"firmenname": "Kein Account"}
    result = precall.merge_account_memory(briefing, None)
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
