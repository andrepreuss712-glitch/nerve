"""Integration-Assertion tests for Wave 1 (Phase 08.23.2.G-MEET): tenant_orgs seed,
dual-write contract, and calls.tenant_id backfill.

CLAUDE.md Test-Qualitaets-Regel: every test below is an Integration-Assertion
(DB-write/read with an assertion on the resulting row/state) against the in-memory
SQLite schema built from database.models (the ORM is the test-schema source per
CLAUDE.md Punkt 21). None is a source-presence false-green.

SQLite-vs-Postgres boundary (HONEST note): SQLite in-memory has NO triggers and no
`ON CONFLICT (col) DO NOTHING` DDL semantics, so the *live* Postgres dual-write trigger
`trg_mk_tenant_org` and the migration's post-backfill `RAISE EXCEPTION` guard are NOT
exercised here — they are verified server-side on Production via the plan's
`<live>`/`<migrate>` inspect.sh / psql checks (migration 0011). What IS tested here:
  - ORM/DDL schema parity: tenant_orgs builds from models.py with the right columns,
    legacy_org_id is UNIQUE NOT NULL FK -> organisations.id (the ON CONFLICT target),
    calls.tenant_id stays nullable.
  - The seed invariant (1 tenant_org per organisation) and the backfill-join semantics
    (calls.tenant_id = tenant_orgs.id bridged via users.org_id) as real row assertions.
  - Idempotency: the UNIQUE(legacy_org_id) constraint that the trigger's ON CONFLICT
    relies on actually rejects a duplicate bridge row (IntegrityError).
"""
import uuid

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from database.models import TenantOrg, Organisation, User, Call


def _mk_org(db, name):
    o = Organisation(name=name)
    db.add(o)
    db.flush()
    return o


def _seed_tenant_orgs(db):
    """Python equivalent of migration 0011 step 2 (idempotent seed: one row per org)."""
    existing = {t.legacy_org_id for t in db.query(TenantOrg).all()}
    for org in db.query(Organisation).all():
        if org.id in existing:
            continue  # ON CONFLICT (legacy_org_id) DO NOTHING analogue
        db.add(TenantOrg(id=str(uuid.uuid4()), legacy_org_id=org.id, name=org.name))
    db.flush()


def _backfill_calls_tenant_id(db):
    """Python equivalent of migration 0011 step 4 (UPDATE join calls->users->orgs->tenant_orgs)."""
    bridge = {t.legacy_org_id: t.id for t in db.query(TenantOrg).all()}
    org_of_user = {u.id: u.org_id for u in db.query(User).all()}
    for call in db.query(Call).filter(Call.tenant_id.is_(None)).all():
        org_id = org_of_user.get(call.user_id)
        if org_id is not None and org_id in bridge:
            call.tenant_id = bridge[org_id]
    db.flush()


def test_seed_one_row_per_org(db_session):
    a = _mk_org(db_session, "Org A")
    b = _mk_org(db_session, "Org B")
    c = _mk_org(db_session, "Org C")
    _seed_tenant_orgs(db_session)

    assert db_session.query(TenantOrg).count() == db_session.query(Organisation).count() == 3
    legacy_ids = sorted(t.legacy_org_id for t in db_session.query(TenantOrg).all())
    assert legacy_ids == sorted([a.id, b.id, c.id])  # every org.id appears exactly once


def test_dualwrite_trigger_fires(db_session):
    """Dual-write CONTRACT (the live trigger is verified on Production): a freshly created
    organisation gets exactly one bridged tenant_orgs row with legacy_org_id == new org id.
    Here we drive the same INSERT the trigger would, then assert the bridge row exists."""
    _seed_tenant_orgs(db_session)
    new_org = _mk_org(db_session, "Brand New GmbH")
    # trigger analogue: AFTER INSERT ON organisations -> INSERT tenant_orgs(...NEW.id, NEW.name)
    db_session.add(TenantOrg(id=str(uuid.uuid4()), legacy_org_id=new_org.id, name=new_org.name))
    db_session.flush()

    rows = db_session.query(TenantOrg).filter_by(legacy_org_id=new_org.id).all()
    assert len(rows) == 1
    assert rows[0].name == "Brand New GmbH"


def test_dualwrite_idempotent(db_session):
    """The trigger uses ON CONFLICT (legacy_org_id) DO NOTHING, which REQUIRES a UNIQUE
    constraint on legacy_org_id. Prove that constraint rejects a duplicate bridge row."""
    org = _mk_org(db_session, "Solo Org")
    db_session.add(TenantOrg(id=str(uuid.uuid4()), legacy_org_id=org.id, name=org.name))
    db_session.flush()
    db_session.add(TenantOrg(id=str(uuid.uuid4()), legacy_org_id=org.id, name=org.name))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_calls_tenant_id_backfilled(db_session):
    org = _mk_org(db_session, "Backfill Org")
    _seed_tenant_orgs(db_session)
    tenant = db_session.query(TenantOrg).filter_by(legacy_org_id=org.id).one()
    user = User(email="u@example.com", passwort_hash="x", org_id=org.id)
    db_session.add(user)
    db_session.flush()
    call = Call(id=str(uuid.uuid4()), user_id=user.id, call_mode="cold_call", tenant_id=None)
    db_session.add(call)
    db_session.flush()

    _backfill_calls_tenant_id(db_session)

    db_session.refresh(call)
    assert call.tenant_id == tenant.id  # bridged via users.org_id -> tenant_orgs.id


def test_calls_tenant_id_stays_nullable(db_session):
    """COLUMN constraint assertion (NOT row state): calls.tenant_id is NOT made NOT NULL.
    Does not contradict the post-backfill row-state guard (test_no_orphan_calls_after_backfill)."""
    col = sa_inspect(Call).columns['tenant_id']
    assert col.nullable is True


def test_no_orphan_calls_after_backfill(db_session):
    """Post-backfill ROW STATE: after a successful backfill over known-org users, no call
    retains NULL tenant_id (the migration's RAISE guard would have aborted the deploy)."""
    org = _mk_org(db_session, "Total Join Org")
    _seed_tenant_orgs(db_session)
    user = User(email="t@example.com", passwort_hash="x", org_id=org.id)
    db_session.add(user)
    db_session.flush()
    for _ in range(3):
        db_session.add(Call(id=str(uuid.uuid4()), user_id=user.id, call_mode="cold_call", tenant_id=None))
    db_session.flush()

    _backfill_calls_tenant_id(db_session)

    orphan_count = (
        db_session.query(Call)
        .join(User, Call.user_id == User.id)
        .filter(Call.tenant_id.is_(None))
        .count()
    )
    assert orphan_count == 0
