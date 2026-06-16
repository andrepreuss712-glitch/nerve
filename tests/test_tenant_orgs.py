"""Integration-Assertion tests for Wave 1 (Phase 08.23.2.G-MEET): tenant_orgs seed,
dual-write contract, and calls.tenant_id backfill.

PORTIERT auf nerve_test-PG (Phase 08.23.2.PGTEST Task 4, F1 + Delta-Review-2).

CLAUDE.md Test-Qualitaets-Regel: every test below is an Integration-Assertion (DB-write/read with an
assertion on the resulting row/state) against the REAL nerve_test-PG (db_session aus conftest, Plan 01).
None is a source-presence false-green.

PG-Trigger-Semantik (F1): auf nerve_test feuert der AFTER-INSERT-Trigger `trg_mk_tenant_org`
(Migration 0011) bei JEDEM `INSERT organisations` automatisch die passende tenant_orgs-Row
(ON CONFLICT (legacy_org_id) DO NOTHING). Daher ERWARTET dieser Test die Trigger-Row und liest sie
zurueck (test_rls_isolation.py:33-54-Muster) statt sie Python-seitig zu doppeln — ein manueller
TenantOrg-Insert wuerde sonst auf UNIQUE(legacy_org_id) kollidieren WO der Test es nicht erwartet.
Der ECHTE Idempotenz-Test (erwarteter IntegrityError) bleibt: EIN forcierter Duplikat-Insert nach der
schon vorhandenen Trigger-Row provoziert die UNIQUE-Verletzung.

ID-Scoping (Delta-Review-2 BLOCKER): nerve_test ist PERSISTENT (D-03) + traegt den session-scoped
Base-Seed (Org id=1 + dessen Trigger-tenant_org + User id=1) und generische [PGTEST-GENERIC]-Tenants.
JEDE count/all-Assertion + die Helper sind daher auf die TEST-EIGENEN Org/User/TenantOrg-IDs gescoped
(filter(...id.in_(own_ids))) — NIEMALS global, sonst sehen sie die Base-Seed-Rows -> False-Red.

Reverse-FK-Teardown laeuft in der cleanup_tracker-Fixture-POST-yield-Sektion (MED-1, runs even on
assertion failure) -> kein State-Leak in nerve_test; der Base-Seed (id=1) bleibt unangetastet.
"""
import uuid

import pytest
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.exc import IntegrityError

from database.models import TenantOrg, Organisation, User, Call


@pytest.fixture
def cleanup_tracker(db_session):
    """Tracks test-created org/user/call/tenant_org IDs and reverse-FK-deletes them in its POST-yield
    section (MED-1: runs even if a test asserts/fails). NEVER touches the Base-Seed (id=1). The fixture
    yields a dict the test registers its created IDs into.

    NOTE (#8, T-PGTEST-34): the teardown lives in THIS fixture (fixtures may yield), NEVER as a `yield`
    in a plain test body (that would silently turn the test into a skipped generator = false-green)."""
    ids = {"calls": [], "users": [], "org_ids": []}
    yield ids
    try:
        # reverse-FK: calls -> users -> tenant_orgs (by legacy_org_id) -> organisations.
        if ids["calls"]:
            db_session.execute(
                text("DELETE FROM public.calls WHERE id = ANY(:c)"),
                {"c": [str(x) for x in ids["calls"]]},
            )
        if ids["users"]:
            db_session.execute(
                text("DELETE FROM public.users WHERE id = ANY(:u)"), {"u": list(ids["users"])}
            )
        if ids["org_ids"]:
            db_session.execute(
                text("DELETE FROM public.tenant_orgs WHERE legacy_org_id = ANY(:o)"),
                {"o": list(ids["org_ids"])},
            )
            db_session.execute(
                text("DELETE FROM public.organisations WHERE id = ANY(:o)"), {"o": list(ids["org_ids"])}
            )
        db_session.commit()
    except Exception as _te:
        print(f"[PGTEST-CLEANUP] tenant_orgs teardown failed (non-fatal): {_te!r}")
        try:
            db_session.rollback()
        except Exception:
            pass


def _mk_org(db, name, track=None):
    """INSERT organisations -> trg_mk_tenant_org auto-creates the tenant_orgs row. Returns the org
    (with .id). NO manual TenantOrg insert (would collide on UNIQUE(legacy_org_id))."""
    o = Organisation(name=name)
    db.add(o)
    db.flush()  # fires trg_mk_tenant_org -> tenant_orgs row auto-created
    if track is not None:
        track["org_ids"].append(o.id)
    return o


def _read_back_tenant_org(db, org_id):
    """Read the trigger-created tenant_orgs row for a given org (test_rls_isolation.py:33-54 pattern)."""
    return db.query(TenantOrg).filter_by(legacy_org_id=org_id).one()


def _backfill_calls_tenant_id(db, own_org_ids, own_user_ids):
    """Python equivalent of migration 0011 step 4 (UPDATE join calls->users->orgs->tenant_orgs),
    SCOPED to the test's own orgs/users (Delta-Review-2: never iterate global query(...).all())."""
    bridge = {
        t.legacy_org_id: t.id
        for t in db.query(TenantOrg).filter(TenantOrg.legacy_org_id.in_(own_org_ids)).all()
    }
    org_of_user = {
        u.id: u.org_id
        for u in db.query(User).filter(User.id.in_(own_user_ids)).all()
    }
    for call in (db.query(Call)
                   .filter(Call.user_id.in_(own_user_ids))
                   .filter(Call.tenant_id.is_(None)).all()):
        org_id = org_of_user.get(call.user_id)
        if org_id is not None and org_id in bridge:
            call.tenant_id = bridge[org_id]
    db.flush()


def test_seed_one_row_per_org(db_session, cleanup_tracker):
    """The Wave-1 trigger creates exactly one tenant_orgs row per organisation. Assertions are scoped
    to the test's own 3 orgs (the persistent Base-Seed Org id=1 + generic tenants must NOT count)."""
    a = _mk_org(db_session, "Org A", cleanup_tracker)
    b = _mk_org(db_session, "Org B", cleanup_tracker)
    c = _mk_org(db_session, "Org C", cleanup_tracker)
    own_org_ids = [a.id, b.id, c.id]

    # Scoped (Delta-Review-2): NOT a global count -> Base-Seed/generic tenants don't poison it.
    assert (db_session.query(Organisation)
            .filter(Organisation.id.in_(own_org_ids)).count() == 3)
    assert (db_session.query(TenantOrg)
            .filter(TenantOrg.legacy_org_id.in_(own_org_ids)).count() == 3)

    legacy_ids = sorted(
        t.legacy_org_id for t in
        db_session.query(TenantOrg).filter(TenantOrg.legacy_org_id.in_(own_org_ids)).all()
    )
    assert legacy_ids == sorted(own_org_ids)  # every own org.id appears exactly once


def test_dualwrite_trigger_fires(db_session, cleanup_tracker):
    """Dual-write CONTRACT exercised on REAL PG: a freshly created organisation gets exactly one
    bridged tenant_orgs row with legacy_org_id == new org id (the trigger fires; we read it back)."""
    new_org = _mk_org(db_session, "Brand New GmbH", cleanup_tracker)

    rows = db_session.query(TenantOrg).filter_by(legacy_org_id=new_org.id).all()
    assert len(rows) == 1                       # trigger created exactly one row
    assert rows[0].name == "Brand New GmbH"


def test_dualwrite_idempotent(db_session, cleanup_tracker):
    """The trigger uses ON CONFLICT (legacy_org_id) DO NOTHING, which REQUIRES a UNIQUE constraint on
    legacy_org_id. On PG the trigger ALREADY created the row for the new org -> ONE forced duplicate
    insert provokes the IntegrityError the ON CONFLICT relies on."""
    org = _mk_org(db_session, "Solo Org", cleanup_tracker)
    # Trigger already created tenant_orgs(legacy_org_id=org.id). One forced duplicate -> UNIQUE error.
    db_session.add(TenantOrg(id=str(uuid.uuid4()), legacy_org_id=org.id, name=org.name))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_calls_tenant_id_backfilled(db_session, cleanup_tracker):
    org = _mk_org(db_session, "Backfill Org", cleanup_tracker)
    tenant = _read_back_tenant_org(db_session, org.id)
    user = User(email=f"u-{uuid.uuid4().hex[:8]}@example.com", passwort_hash="x", org_id=org.id)
    db_session.add(user)
    db_session.flush()
    cleanup_tracker["users"].append(user.id)
    call = Call(id=str(uuid.uuid4()), user_id=user.id, call_mode="cold_call", tenant_id=None)
    db_session.add(call)
    db_session.flush()
    cleanup_tracker["calls"].append(call.id)

    _backfill_calls_tenant_id(db_session, [org.id], [user.id])

    db_session.refresh(call)
    assert call.tenant_id == tenant.id  # bridged via users.org_id -> tenant_orgs.id


def test_calls_tenant_id_stays_nullable(db_session):
    """COLUMN constraint assertion (NOT row state): calls.tenant_id is NOT made NOT NULL.
    Does not contradict the post-backfill row-state guard (test_no_orphan_calls_after_backfill)."""
    col = sa_inspect(Call).columns['tenant_id']
    assert col.nullable is True


def test_no_orphan_calls_after_backfill(db_session, cleanup_tracker):
    """Post-backfill ROW STATE (scoped to the test's own calls): after a successful backfill over
    known-org users, none of THIS TEST's calls retains NULL tenant_id."""
    org = _mk_org(db_session, "Total Join Org", cleanup_tracker)
    user = User(email=f"t-{uuid.uuid4().hex[:8]}@example.com", passwort_hash="x", org_id=org.id)
    db_session.add(user)
    db_session.flush()
    cleanup_tracker["users"].append(user.id)
    own_call_ids = []
    for _ in range(3):
        call = Call(id=str(uuid.uuid4()), user_id=user.id, call_mode="cold_call", tenant_id=None)
        db_session.add(call)
        db_session.flush()
        cleanup_tracker["calls"].append(call.id)
        own_call_ids.append(call.id)

    _backfill_calls_tenant_id(db_session, [org.id], [user.id])

    orphan_count = (
        db_session.query(Call)
        .filter(Call.id.in_(own_call_ids))
        .filter(Call.tenant_id.is_(None))
        .count()
    )
    assert orphan_count == 0
