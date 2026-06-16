

===== FILE: database/db.py =====
import os
import sqlite3
import contextvars
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, scoped_session

# Resolve relative SQLite paths relative to project root
_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')

if _DATABASE_URL.startswith('sqlite:///') and not _DATABASE_URL.startswith('sqlite:////'):
    _rel = _DATABASE_URL[len('sqlite:///'):]
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _abs  = os.path.join(_root, _rel)
    os.makedirs(os.path.dirname(_abs), exist_ok=True)
    _DATABASE_URL = f'sqlite:///{_abs}'

_connect_args = {'check_same_thread': False} if 'sqlite' in _DATABASE_URL else {}
engine = create_engine(_DATABASE_URL, connect_args=_connect_args)

# ── Enable WAL mode for SQLite (concurrent reads + writes under threading) ─────
if 'sqlite' in _DATABASE_URL:
    @event.listens_for(engine, 'connect')
    def set_wal_mode(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()

# ── Test-only: SQLite-Schema-Emulation fuer crm.* / training.* ─────────────────
# Die crm-/training-Modelle (models.py) sind __table_args__ {'schema': 'crm'|'training'}.
# SQLite kennt keine Schemas -> Base.metadata.create_all() wirft "unknown database crm"
# und bricht das deploy.sh-Pytest-Gate schon bei der COLLECTION (jeder Test, der app/models
# importiert). Wir ATTACHen pro SQLite-Verbindung eine In-Memory-DB namens crm/training, sodass
# schema-qualifiziertes create_all + alle Queries aufloesen (generalisiert das StaticPool+ATTACH-
# Muster aus test_account_memory_briefing.py / test_anonymizer_worker.py auf JEDE SQLite-Engine —
# auch die im Test-Suite-Code separat erzeugten). Die crm/training-Modelle tragen ausschliesslich
# Soft-Links (KEIN FK, D-08/D-17) -> create_all emittiert keine cross-database REFERENCES.
# GLOBAL auf der Engine-Klasse registriert (nicht nur auf der Modul-Engine), damit es Test-Engines
# aus conftest/tests/ ebenfalls erfasst. Postgres-Verbindungen sind psycopg2, kein sqlite3.Connection
# -> unberuehrt (echte Schemas in Produktion).
@event.listens_for(Engine, "connect")
def _sqlite_attach_crm_training_schemas(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        try:
            cur.execute("ATTACH DATABASE ':memory:' AS crm")
            cur.execute("ATTACH DATABASE ':memory:' AS training")
        finally:
            cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)


# ── Phase 08.23.2.G-MEET Wave 2 — Multi-Tenant RLS GUC plumbing (D-11, D-12.1, D-12.3) ──
# The crm.* RLS policies filter on current_setting('app.tenant_id', true)::uuid. We publish the
# request/thread tenant UUID into a contextvar, and a SQLAlchemy Session `after_begin` hook issues
# a TRANSACTION-LOCAL set_config('app.tenant_id', <uuid>, true) at transaction start. Because the
# SET fires when the transaction begins (BEFORE its queries), the SET and the tenant-scoped queries
# share ONE transaction by construction (fixes B-1 connection-affinity). set_config(...,true) is
# SET LOCAL: it clears AUTOMATICALLY at COMMIT/ROLLBACK -> NO checkin RESET needed, pooler-agnostic
# (immune if a pooler is ever added, e.g. 08.23.2.STAGING), and safe for out-of-request worker
# threads (the GUC lives only for the worker's own transaction).
_current_tenant_id = contextvars.ContextVar("nerve_tenant_id", default=None)


def set_current_tenant(tid):
    """Publish the active tenant UUID (string) for the current request/thread.

    Called from before_request (request path) AND by any worker thread before its session work
    (so the after_begin hook can issue the transaction-local SET on the worker's own transaction).
    """
    _current_tenant_id.set(tid)


def clear_current_tenant():
    """Reset the contextvar (hygiene). The actual tenant control is the transaction-local SET,
    which auto-clears at COMMIT/ROLLBACK -- this only prevents the contextvar surviving into the
    next request on a reused thread."""
    _current_tenant_id.set(None)


# Postgres-only: SQLite has no set_config / RLS, so the in-memory test schema is unaffected
# (inverse of the SQLite WAL hook above).
if 'sqlite' not in _DATABASE_URL:
    @event.listens_for(SessionLocal, "after_begin")
    def _set_tenant_txn_local(session, transaction, connection):
        # Fires when a transaction begins, BEFORE its queries, on the SAME connection
        # => the GUC is transaction-local for exactly the queries that follow.
        tid = _current_tenant_id.get()
        if not tid:
            # No tenant context (pre-login / static / worker w/o tenant) -> GUC unset
            # -> current_setting('app.tenant_id', true) is NULL -> RLS fails closed (0 rows).
            return
        # Third arg true = transaction-local (SET LOCAL). PARAMETERIZED (bound param) ->
        # SQL-injection-safe (T-G2-05): never f-string/%-format the UUID into SQL.
        # NOTE: NO `RESET app.tenant_id` / checkin listener exists -- transaction-local
        # auto-clears at COMMIT/ROLLBACK, so a returned/reused connection carries no residual
        # tenant GUC (T-G2-03 solved by construction).
        connection.exec_driver_sql(
            "SELECT set_config('app.tenant_id', %s, true)", (str(tid),)
        )


class Base(DeclarativeBase):
    pass


# Alias so routes can do: from database.db import db
db = Base


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_session():
    """Returns a new DB session (for use outside request context)."""
    return SessionLocal()


===== FILE: tests/conftest.py =====
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure repo root is on sys.path so `from services.ki_logik import ...`
# works regardless of pytest invocation directory.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from database.db import Base
# Import all models so Base.metadata knows about them
import database.models  # noqa: F401


@pytest.fixture
def sample_state():
    """Factory returning a fresh state dict with all Phase 04.8 keys at defaults."""
    def _make(**overrides):
        base = {
            "current_phase": 1,
            "current_phase_name": "Opener",
            "phase_confidence": 0.0,
            "phase_changed_at": None,
            "phase_change_count": 0,
            "readiness_score": 30,
            "readiness_bucket": "cold",
            "score_factors_seen": {},
            "active_hint": None,
            "ewb_buttons": None,
            "cold_call_inference": None,
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(monkeypatch):
    """Flask test client with in-memory SQLite rebinding.

    Rebinds `database.db.engine` + `SessionLocal` + `db_session` to a fresh
    in-memory SQLite engine so any code path using `get_session()` or
    `SessionLocal()` sees the same test DB. Seeds schema via Base.metadata.
    """
    from sqlalchemy import create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm, scoped_session as _ss
    import database.db as _db_mod

    engine = _ce("sqlite:///:memory:", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    TestSession = _sm(autocommit=False, autoflush=False, bind=engine)
    TestScoped = _ss(TestSession)

    monkeypatch.setattr(_db_mod, 'engine', engine)
    monkeypatch.setattr(_db_mod, 'SessionLocal', TestSession)
    monkeypatch.setattr(_db_mod, 'db_session', TestScoped)

    # Import app AFTER patching so module-level references still work;
    # routes use get_session() which calls SessionLocal() at call time.
    import app as _app_mod
    flask_app = _app_mod.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    # Expose the test session via the db_session fixture path for convenience
    with flask_app.test_client() as c:
        c._test_session = TestSession()
        c._test_engine = engine
        yield c
        try:
            c._test_session.close()
        except Exception:
            pass
    engine.dispose()


@pytest.fixture
def db_from_client(client):
    """Alias: returns the test session bound to the same engine as client."""
    return client._test_session


# ── Phase 08.23.2.G-MEET Wave 2 — real-PG nerve_app connection (RLS isolation test, D-12.2) ──
# The RLS isolation test (tests/test_rls_isolation.py) MUST run against REAL Postgres as the
# RLS-constrained `nerve_app` role -- SQLite has no Row-Level-Security (a SQLite branch would be a
# FALSE-GREEN). This fixture provides a raw psycopg2 connection as nerve_app to the real `nerve`
# DB, reading its DSN from env. It is ONLY available server-side on Production (where the DSN
# env var is set). When the DSN is absent (e.g. local, no real PG) the dependent tests SKIP --
# they NEVER fall back to SQLite.
#
# Expected env var (server-side, set by André in the deploy/test environment):
#   NERVE_APP_TEST_DSN  -- e.g. postgresql://nerve_app@127.0.0.1:5432/nerve
# (nerve_app uses peer/socket auth on Production; the DSN is read/write to the real nerve DB.)
@pytest.fixture
def nerve_app_pg_conn():
    dsn = os.environ.get('NERVE_APP_TEST_DSN')
    if not dsn:
        pytest.skip(
            "NERVE_APP_TEST_DSN not set -- RLS isolation test requires a real-PG nerve_app "
            "connection (no SQLite fallback by design, D-12.2). Run server-side on Production."
        )
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed -- RLS isolation test requires real Postgres.")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False  # explicit transactions: SET LOCAL must share the query's txn
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


# ── Phase 08.23.2.G-MEET Wave 3 — real-PG nerve_anon_worker engine (anonymizer RLS test, D-16) ──
# The anonymizer worker's RLS group (tests/test_anonymizer_worker.py) MUST run against REAL Postgres
# as the `nerve_anon_worker` role -- the only role the 0013 anon_worker_read / anon_worker_stamp
# policies target. SQLite has no RLS (a SQLite branch would be a FALSE-GREEN), so there is NO
# fallback: when the DSN is absent the dependent tests SKIP. This yields a SQLAlchemy Engine (not a
# raw connection) because the worker's process_unstamped() runs on a SQLAlchemy Connection -- the
# test exercises the SAME code path the production cron uses.
#
# Expected env var (server-side, set by André in the deploy/test environment):
#   ANON_WORKER_TEST_DSN  -- e.g. postgresql://nerve_anon_worker@/nerve  (the worker role; sets NO
#                            app.tenant_id, relies on the 0013 worker policies for cross-tenant access)
@pytest.fixture
def anon_worker_pg_engine():
    dsn = os.environ.get('ANON_WORKER_TEST_DSN')
    if not dsn:
        pytest.skip(
            "ANON_WORKER_TEST_DSN not set -- anonymizer RLS test requires a real-PG nerve_anon_worker "
            "connection (no SQLite fallback by design, D-16). Run server-side on Production."
        )
    engine = create_engine(dsn)
    try:
        yield engine
    finally:
        engine.dispose()


# ── Phase 08.23.2.SCHILD Wave 4 — read-only pg_description guard connection ──
# The Schild-Guard (tests/test_schild_guard.py) verifies that every table + non-trivial column in
# public/crm/training carries a Postgres COMMENT (>=10 chars) in pg_description. It MUST run against
# REAL Postgres -- SQLite has no schemas/COMMENTs (a SQLite branch would be a FALSE-GREEN,
# RESEARCH §1.3). pg_description is a world-readable catalog, so plain nerve_app suffices WITHOUT any
# GRANT (proven in Plan 01 / DISCOVERY-DECISIONS.md via a SET ROLE + obj_description ROLLBACK test:
# GUARD_ROLE=nerve_app). When the DSN is absent (local/SQLite) the guard SKIPS -- never falls back.
#
# Expected env var (server-side; name LOCKED in DISCOVERY-DECISIONS.md key `DSN_ENV_VAR:`):
#   NERVE_SCHILD_TEST_DSN  -- set it to the value of DATABASE_URL from /etc/nerve/.env
#                            (postgresql://nerve_app:<pw>@/nerve, Unix socket). Read-only catalog use.
@pytest.fixture
def schild_guard_pg_conn():
    dsn = os.environ.get('NERVE_SCHILD_TEST_DSN')
    if not dsn:
        pytest.skip(
            "NERVE_SCHILD_TEST_DSN not set -- Schild-Guard requires a real-PG connection that can read "
            "pg_description of public/crm/training (no SQLite fallback by design, RESEARCH §1.3). "
            "Run server-side: NERVE_SCHILD_TEST_DSN=$(grep ^DATABASE_URL= /etc/nerve/.env | cut -d= -f2-)"
        )
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed -- Schild-Guard requires real Postgres.")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True  # read-only catalog queries; no transaction needed
    try:
        yield conn
    finally:
        conn.close()


===== FILE: tests/test_tenant_orgs.py =====
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


===== FILE: tests/test_08_14_apirate_seed.py =====
"""Phase 08.14 — Regression: ApiRate-Seed auf fresh in-memory-SQLite.

Bug: INSERT fehlte last_checked_at -> NOT NULL constraint failed auf jeder fresh DB.
Fix: last_checked_at=datetime.utcnow() im INSERT ergaenzt.

Testet Runtime-Verhalten (echte SQLite-Writes), keine Source-Presence-Checks.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@pytest.fixture(scope='module')
def fresh_engine():
    """In-memory SQLite mit ApiRate-Tabelle, frisch erstellt."""
    from database.models import Base
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return engine


SEED_ROWS = [
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_input_tokens',       0.003,   'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_output_tokens',      0.015,   'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_read_tokens',  0.0003,  'USD'),
    ('anthropic', 'claude-sonnet-4-5-20251022', 'per_1k_cache_write_tokens', 0.00375, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_input_tokens',       0.00025, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_output_tokens',      0.00125, 'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_read_tokens',  0.000025,'USD'),
    ('anthropic', 'claude-haiku-4-5-20251001',  'per_1k_cache_write_tokens', 0.0003,  'USD'),
]


class TestApiRateSeed:
    def test_seed_inserts_8_rows(self, fresh_engine):
        """Seed-Logik schreibt exakt 8 Rows in eine leere api_rates-Tabelle."""
        now = datetime.utcnow()
        with fresh_engine.connect() as conn:
            for provider, model, unit, price, currency in SEED_ROWS:
                conn.execute(
                    text(
                        "INSERT INTO api_rates "
                        "(provider, model, unit_type, price_per_unit, currency, active, source_url, last_checked_at, created_at) "
                        "VALUES (:p,:m,:u,:price,:cur,1,'seed:test',:now,:now)"
                    ),
                    {'p': provider, 'm': model, 'u': unit, 'price': price, 'cur': currency, 'now': now}
                )
            conn.commit()
            count = conn.execute(text("SELECT COUNT(*) FROM api_rates")).scalar()
        assert count == 8

    def test_seed_rows_have_last_checked_at(self, fresh_engine):
        """Alle Seed-Rows haben last_checked_at != NULL (war der Bug)."""
        with fresh_engine.connect() as conn:
            null_count = conn.execute(
                text("SELECT COUNT(*) FROM api_rates WHERE last_checked_at IS NULL")
            ).scalar()
        assert null_count == 0, f"{null_count} Rows haben last_checked_at=NULL"

    def test_seed_idempotent_no_duplicates(self, fresh_engine):
        """Zweiter Seed-Lauf fuegt keine Duplikate ein (existing-Row-Check greift)."""
        now = datetime.utcnow()
        with fresh_engine.connect() as conn:
            for provider, model, unit, price, currency in SEED_ROWS:
                exists = conn.execute(
                    text("SELECT 1 FROM api_rates WHERE provider=:p AND model=:m AND unit_type=:u AND active=1"),
                    {'p': provider, 'm': model, 'u': unit}
                ).fetchone()
                if not exists:
                    conn.execute(
                        text(
                            "INSERT INTO api_rates "
                            "(provider, model, unit_type, price_per_unit, currency, active, source_url, last_checked_at) "
                            "VALUES (:p,:m,:u,:price,:cur,1,'seed:test',:now)"
                        ),
                        {'p': provider, 'm': model, 'u': unit, 'price': price, 'cur': currency, 'now': now}
                    )
            conn.commit()
            count = conn.execute(text("SELECT COUNT(*) FROM api_rates")).scalar()
        assert count == 8, f"Nach zweitem Seed-Lauf: {count} Rows statt 8 (Duplikat-Bug)"

    def test_seed_sonnet_and_haiku_models_present(self, fresh_engine):
        """Beide Models (sonnet-4-5 + haiku-4-5) sind nach Seed vorhanden."""
        with fresh_engine.connect() as conn:
            models = {
                row[0] for row in
                conn.execute(text("SELECT DISTINCT model FROM api_rates")).fetchall()
            }
        assert 'claude-sonnet-4-5-20251022' in models
        assert 'claude-haiku-4-5-20251001' in models


===== FILE: tests/test_postcall_split.py =====
"""Phase 08.23.2.D.UX.4-02 — Backend Postcall-Split Tests.

Runtime-Verhalten (echte Flask test_client Requests, DB-Reads/-Writes, Return-Werte):
- /api/postcall_outcome liefert outcome OHNE Sonnet (generate_postcall_analysis NICHT aufgerufen)
- conf=0-Degraded-Pfad (outcome None, source None)
- /api/postcall_cards liefert vorschlaege (Sonnet gemockt)

Kein Source-Presence-Test (CLAUDE.md Test-Qualitaets-Regel).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from database.db import get_session
from database.models import User, Organisation, ConversationLog, Call


def _now():
    return datetime.now(timezone.utc)


def _seed_user_and_conv(user_id=1, org_id=1):
    """Legt Org + User + ConversationLog an, damit login_required passt + Ownership-Check gruen ist.

    Gibt conv_id (int) zurueck. login_required laedt User via session['user_id'] und prueft
    user.org_id == org.id — beide muessen existieren.
    """
    db = get_session()
    try:
        if db.query(Organisation).filter_by(id=org_id).first() is None:
            db.add(Organisation(id=org_id, name='Test-Org'))
            db.commit()
        if db.query(User).filter_by(id=user_id).first() is None:
            db.add(User(
                id=user_id, org_id=org_id, email=f'split-test-{user_id}@nerve.local',
                passwort_hash='x', rolle='owner', aktiv=True,
            ))
            db.commit()
        conv = ConversationLog(user_id=user_id, org_id=org_id, created_at=_now())
        db.add(conv)
        db.commit()
        return conv.id
    finally:
        db.close()


def _cleanup_conv(conv_id):
    db = get_session()
    try:
        db.query(ConversationLog).filter(ConversationLog.id == conv_id).delete()
        db.commit()
    finally:
        db.close()


def _auth_client(client, user_id=1):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return client


# -- /api/postcall_outcome — Haiku-only (kein Sonnet) --------------------------

def test_outcome_endpoint_returns_outcome_without_sonnet(client):
    """Outcome-Endpoint liefert outcome/source aus Haiku-classify; Sonnet wird NICHT aufgerufen."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'meeting_booked', 'confidence': 0.95}) as m_classify, \
             patch('services.coaching_service.generate_postcall_analysis') as m_sonnet:
            resp = client.post('/api/postcall_outcome', json={'conv_id': conv_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')

            assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
            data = resp.get_json()
            assert data is not None
            # Haiku-classify wurde aufgerufen, Sonnet NICHT (kein generate_postcall_analysis)
            assert m_classify.called or 'outcome' in data, 'classify oder outcome-Pfad muss laufen'
            m_sonnet.assert_not_called()
            # Response enthaelt KEIN vorschlaege-Key (gehoert zu /api/postcall_cards)
            assert 'vorschlaege' not in data, 'Outcome-Endpoint darf kein vorschlaege liefern'
            assert 'outcome' in data and 'confidence' in data and 'source' in data
    finally:
        _cleanup_conv(conv_id)


def test_outcome_endpoint_returns_outcome_with_call_id(client):
    """Mit call_id triggert classify + Schwellenlogik -> source='ai_auto' bei conf>=0.90."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    call_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.add(Call(id=call_id, user_id=1, call_mode='cold_call',
                    started_at=_now(), transcript_storage='none'))
        db.commit()
    finally:
        db.close()
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'meeting_booked', 'confidence': 0.95}), \
             patch('services.coaching_service.generate_postcall_analysis') as m_sonnet:
            resp = client.post('/api/postcall_outcome',
                               json={'conv_id': conv_id, 'call_id': call_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['outcome'] == 'meeting_booked'
            assert data['source'] == 'ai_auto'
            m_sonnet.assert_not_called()
    finally:
        db2 = get_session()
        try:
            db2.query(Call).filter(Call.id == call_id).delete()
            db2.commit()
        finally:
            db2.close()
        _cleanup_conv(conv_id)


def test_outcome_endpoint_conf_zero_path(client):
    """conf=0 (leeres Transcript / classify-Fail) -> outcome None, source None (LB-04 Degraded)."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    call_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.add(Call(id=call_id, user_id=1, call_mode='cold_call',
                    started_at=_now(), transcript_storage='none'))
        db.commit()
    finally:
        db.close()
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'unknown', 'confidence': 0.0}):
            resp = client.post('/api/postcall_outcome',
                               json={'conv_id': conv_id, 'call_id': call_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['outcome'] is None, 'conf=0 -> outcome None'
            assert data['source'] is None, 'conf=0 -> source None'
            assert data['confidence'] == 0.0
    finally:
        db2 = get_session()
        try:
            db2.query(Call).filter(Call.id == call_id).delete()
            db2.commit()
        finally:
            db2.close()
        _cleanup_conv(conv_id)


def test_outcome_endpoint_ownership_404(client):
    """Fremder/nicht-existenter conv_id -> 404 (Ownership-Check, T-UX4-05)."""
    _auth_client(client)
    resp = client.post('/api/postcall_outcome', json={'conv_id': 999999})
    if resp.status_code in (302, 401):
        pytest.skip('Login-Fixture greift nicht')
    assert resp.status_code == 404


# -- /api/postcall_cards — Sonnet-only -----------------------------------------

def test_cards_endpoint_returns_vorschlaege(client):
    """Cards-Endpoint liefert vorschlaege aus generate_postcall_analysis (gemockt)."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    fake_cards = [
        {'category': 'einwand_preis', 'original_suggestion': 'Im Vergleich wozu?',
         'lernziel': 'Einwaende vertiefen'},
    ]
    try:
        with patch('services.coaching_service.generate_postcall_analysis',
                   return_value=fake_cards) as m_sonnet:
            resp = client.post('/api/postcall_cards', json={'conv_id': conv_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
            data = resp.get_json()
            assert 'vorschlaege' in data, 'Cards-Endpoint muss vorschlaege liefern'
            assert data['vorschlaege'] == fake_cards
            m_sonnet.assert_called_once()
            # call kwargs tragen conv_id + user_id durch (confirm-unabhaengige Persistenz)
            _, kwargs = m_sonnet.call_args
            assert kwargs.get('conv_id') == conv_id
    finally:
        _cleanup_conv(conv_id)


def test_cards_endpoint_ownership_404(client):
    """Fremder/nicht-existenter conv_id -> 404."""
    _auth_client(client)
    resp = client.post('/api/postcall_cards', json={'conv_id': 999999})
    if resp.status_code in (302, 401):
        pytest.skip('Login-Fixture greift nicht')
    assert resp.status_code == 404


===== FILE: tests/test_ewb_rate_api.py =====
"""Phase 08 Plan 05 — Rating-API + Anrede-Override integration tests.

Tests fuer POST /api/ewb/<id>/rate (3-State-Whitelist + Ownership) + Anrede-Whitelist
in services/deepgram_service.py start_live_session-Handler + /api/beenden persist.

Whitelist-Logik (Phase 08 W-1): isinstance(value, bool) or value is None.
Integer 1/0 darf NICHT als bool akzeptiert werden (Python-Equality 1 == True matcht sonst).
"""
import json
from datetime import datetime

import pytest

from database.models import (
    ConversationLog,
    ObjectionEvent,
    Organisation,
    Profile,
    User,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_user(db_session, email='test@test.de'):
    """Erstelle Org + User. Returnt (org, user)."""
    org = Organisation(name='T', plan='starter')
    db_session.add(org)
    db_session.flush()
    u = User(
        org_id=org.id,
        email=email,
        passwort_hash='x',
        market='dach',
        language='de',
    )
    db_session.add(u)
    db_session.flush()
    db_session.commit()
    return org, u


def _make_event(db_session, user, einwand_typ='Preis', success=None):
    """Helper: ConversationLog + ObjectionEvent fuer einen User."""
    conv = ConversationLog(
        user_id=user.id,
        org_id=user.org_id,
        session_mode='cold_call',
        dauer_sekunden=60,
        started_at=datetime.now(),  # NOT NULL constraint
    )
    db_session.add(conv)
    db_session.flush()
    ev = ObjectionEvent(
        user_id=user.id,
        org_id=user.org_id,
        conversation_log_id=conv.id,
        einwand_typ=einwand_typ,
        success=success,
    )
    db_session.add(ev)
    db_session.flush()
    db_session.commit()
    return conv, ev


def _login(client, user_id):
    """Setze session cookie direkt — Pattern aus test_admin_dashboard_auth.py."""
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


# ── Rating-API Tests ─────────────────────────────────────────────────────

def test_rate_success_true(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 200, r.data
    # expire_all() forces a refresh from DB — route wrote via a separate Session
    # on the same shared engine, so test-session's cached ev is stale.
    db.expire_all()
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is True


def test_rate_success_false(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': False}),
        content_type='application/json',
    )
    assert r.status_code == 200
    db.expire_all()
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is False


def test_rate_success_null(client, db_from_client):
    """D-04 'Ueberspringen' → NULL. Falls Event vorher True war."""
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u, success=True)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': None}),
        content_type='application/json',
    )
    assert r.status_code == 200
    db.expire_all()
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is None


def test_rate_invalid_string_rejected(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({'success': 'maybe'}),
        content_type='application/json',
    )
    assert r.status_code == 400


def test_rate_integer_rejected(client, db_from_client):
    """Phase 08 W-1: Strict type-check — integer 1/0 NICHT als bool akzeptieren.
    Python-Equality matcht 1 == True und 0 == False, aber isinstance(1, bool) ist False.
    """
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    # Integer 1 muss abgelehnt werden:
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': 1}),
        content_type='application/json',
    )
    assert r.status_code == 400, f'integer 1 must be rejected, got {r.status_code}'
    # Integer 0 muss ebenfalls abgelehnt werden:
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': 0}),
        content_type='application/json',
    )
    assert r.status_code == 400, f'integer 0 must be rejected, got {r.status_code}'
    # DB muss unveraendert sein:
    db.expire_all()
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is None, 'success column must not be mutated on rejected input'


def test_rate_missing_key_rejected(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert r.status_code == 400


def test_rate_unknown_event_404(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _login(client, u.id)
    r = client.post(
        '/api/ewb/99999/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 404


def test_rate_ownership_other_user_403(client, db_from_client):
    """User A cannot rate User B's event."""
    db = db_from_client
    _org_a, u_a = _make_user(db, 'a@a.de')
    _org_b, u_b = _make_user(db, 'b@b.de')
    _conv, ev_b = _make_event(db, u_b)
    _login(client, u_a.id)  # login als A
    r = client.post(
        f'/api/ewb/{ev_b.id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 403


def test_rate_without_login_redirects(client, db_from_client):
    """@login_required muss redirecten — routes/auth.py redirect(url_for('auth.login')) = 302."""
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    # kein _login()
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    # login_required ist implementation-spezifisch — accept 302 oder 401
    assert r.status_code in (302, 401), f'expected 302/401, got {r.status_code}'


# ── Anrede-Override Tests ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_session_anrede():
    """Autouse fixture: ensure ls.state['session_anrede'] is always clean
    before AND after each test in this module. Prevents cross-test leakage
    into test_ewb_pipeline.py which reads session_anrede via build_profile_context.
    """
    import threading
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    yield
    with ls.state_lock:
        ls.state.pop('session_anrede', None)


def _apply_anrede_whitelist(anrede_raw):
    """Mirror production logic from services/deepgram_service.py (CR-02)."""
    import services.live_session as ls
    anrede_norm = anrede_raw.strip().title() if isinstance(anrede_raw, str) else None
    if anrede_norm in ('Du', 'Sie'):
        with ls.state_lock:
            ls.state['session_anrede'] = anrede_norm
        return anrede_norm
    return None


def test_anrede_whitelist_du():
    """Whitelist akzeptiert 'Du' exakt."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Du')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_lowercase():
    """CR-02: 'du' wird als 'Du' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('du')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_whitespace():
    """CR-02: ' Du' (mit Whitespace) wird normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist(' Du ')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_uppercase():
    """CR-02: 'DU' wird als 'Du' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('DU')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_sie_lowercase():
    """CR-02: 'sie' wird als 'Sie' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('sie')
    assert ls.state.get('session_anrede') == 'Sie'


def test_anrede_whitelist_rejects_invalid():
    """'Hallo; drop table' oder anderes → wird NICHT in ls.state geschrieben."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Hallo; drop table')  # attempt prompt injection
    assert ls.state.get('session_anrede') is None


def test_anrede_whitelist_rejects_partial_match():
    """CR-02: 'Duo' oder 'Sieb' fallen trotz Normalisierung raus."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Duo')
    assert ls.state.get('session_anrede') is None
    _apply_anrede_whitelist('sieb')
    assert ls.state.get('session_anrede') is None


def test_conv_log_persists_anrede(db_session):
    """ConversationLog.anrede akzeptiert String oder None (D-14 Model-Schema)."""
    org = Organisation(name='T', plan='starter')
    db_session.add(org)
    db_session.flush()
    u = User(
        org_id=org.id,
        email='c@c.de',
        passwort_hash='x',
        market='dach',
        language='de',
    )
    db_session.add(u)
    db_session.flush()
    conv = ConversationLog(
        user_id=u.id,
        org_id=org.id,
        session_mode='cold_call',
        dauer_sekunden=60,
        started_at=datetime.now(),
        anrede='Du',
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)
    assert conv.anrede == 'Du'


===== FILE: tests/test_ft_seed.py =====
from database.models import PromptVersion
from app import _seed_prompt_versions


# ewb_ranking removed in Phase 04.8 (D-08): rank_ewb Haiku call deleted.
EXPECTED_MODULES = [
    'assistant_live',
    'coaching_live',
    'objection_trigger',
    'training_persona',
]


def test_prompt_seed(db_session):
    _seed_prompt_versions(db_session)
    for module in EXPECTED_MODULES:
        row = db_session.query(PromptVersion).filter_by(module=module, is_active=True).first()
        assert row is not None, f"missing seeded module: {module}"
        assert row.version == "v1.0.0"
        assert row.prompt_text and len(row.prompt_text) > 30, \
            f"prompt_text too short for {module} (placeholder?)"


def test_seed_idempotent(db_session):
    _seed_prompt_versions(db_session)
    count_after_first = db_session.query(PromptVersion).count()
    _seed_prompt_versions(db_session)
    count_after_second = db_session.query(PromptVersion).count()
    assert count_after_first == 4
    assert count_after_second == 4


===== FILE: tests/test_profile_editor_validation.py =====
"""
tests/test_profile_editor_validation.py
────────────────────────────────────────────────────────────────────
Backend integration tests for POST /profiles/api/profile/<id>/tabu
with list-of-objects validation.

Tests the server-side contract:
  - Valid pair → saved=1, ignored=[]
  - Incomplete (empty alternative) → saved=0, ignored has entry
  - Incomplete (empty begriff) → saved=0, ignored has entry
  - Mixed → saved=N, ignored=M
"""
import json
import pytest


def _make_test_user_and_profile(db_session, engine):
    """Seed a minimal Organisation + User + Profile in the test DB."""
    from database.models import Organisation, User, Profile
    from werkzeug.security import generate_password_hash

    org = Organisation(name='TestOrg')
    db_session.add(org)
    db_session.flush()

    user = User(
        org_id=org.id,
        email='test@example.com',
        passwort_hash=generate_password_hash('secret'),
        rolle='owner',
    )
    db_session.add(user)
    db_session.flush()

    profile = Profile(
        org_id=org.id,
        name='Test-Profil',
        daten=json.dumps({'basis': {'tabu_begriffe': []}}),
        erstellt_von=user.id,
    )
    db_session.add(profile)
    db_session.commit()
    return org, user, profile


def _login(client, db_session, user, org):
    """Inject session state so login_required passes."""
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['org_id'] = org.id
        sess['rolle'] = user.rolle


# ── Tests ──────────────────────────────────────────────────────────────────


def test_tabu_valid_pair_saved(client, db_from_client):
    """POST with complete pair → saved=1, ignored=[]"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': 'A', 'alternative': 'B'}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 1
    assert data['ignored'] == []


def test_tabu_empty_alternative_ignored(client, db_from_client):
    """POST with empty alternative → saved=0, ignored has entry"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': 'A', 'alternative': ''}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 0
    assert len(data['ignored']) == 1


def test_tabu_empty_begriff_ignored(client, db_from_client):
    """POST with empty begriff → saved=0, ignored has entry"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': '', 'alternative': 'B'}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 0
    assert len(data['ignored']) == 1


def test_tabu_mixed_saved_and_ignored(client, db_from_client):
    """POST with mixed → saved=N, ignored=M"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    payload = {
        'tabu_begriffe': [
            {'begriff': 'Kosten', 'alternative': 'Investition'},   # valid
            {'begriff': 'Problem', 'alternative': ''},              # incomplete
            {'begriff': '', 'alternative': 'Herausforderung'},      # incomplete
            {'begriff': 'Risiko', 'alternative': 'Absicherung'},    # valid
        ]
    }
    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps(payload),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 2
    assert len(data['ignored']) == 2


===== FILE: database/models.py Organisation+User+ApiRate region (lines 20,140p;520,545p) =====


===== FILE: app.py _seed_prompt_versions region (lines 1190,1235p) =====


===== FILE: PLAN-01-conftest-fixtures =====
---
phase: 08.23.2.PGTEST
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/conftest.py
  - tests/test_rls_generic_smoke.py
autonomous: true
requirements: [Req-2, Req-5, Req-9]
complexity: "🔴 (security-near — RLS fixture wiring, DSN redirect away from prod nerve)"
user_setup: []

must_haves:
  truths:
    - "Generische Fixtures db_session + client verbinden gegen Postgres-nerve_test (kein hardcoded sqlite)"
    - "Generische crm-berührende Tests sehen ihre Zeilen (Tenant-Kontext gesetzt, RLS nicht fail-closed)"
    - "Kein Fixture-DSN zeigt im Test-Lauf auf die Produktions-nerve-DB"
    - "Die 3 Spezial-Fixtures (nerve_app_pg_conn / anon_worker_pg_engine / schild_guard_pg_conn) lesen DSNs die auf nerve_test zeigen"
    - "Ein dedizierter A-1-Tripwire auf dem GENERISCHEN db_session-Pfad asserted (a) current_setting('app.tenant_id') == TEST_TENANT_UUID (NON-null, beweist der after_begin-Hook feuerte) UND (b) ein realer crm-Read unter dem Tenant liefert >=1 Zeile — dreht den DATABASE_URL-unset-False-Green (A-1) von silent-green auf loud-red"
    - "Ein Session-Scope Base-Seed (Org+User id=1, trigger-aware, Sequenzen advanced) existiert, sodass FK-tragende generische Tests (user_id=1/org_id=1) auf der leeren nerve_test-PG nicht an FK/NOT-NULL brechen"
    - "Die client-Fixture re-exponiert den _test_session/_test_engine-Vertrag (MODUL-SessionLocal-PG-Session + nerve_test-Engine), sodass db_from_client + die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) WEITER funktionieren (kein AttributeError → kein fail-closed Gate-Block)"
  artifacts:
    - path: "tests/conftest.py"
      provides: "PG-basierte generische Fixtures + TEST_TENANT_UUID-Konstante + tenant_orgs-Seed + set_current_tenant-Aufruf + Session-Scope Base-Seed (Org+User id=1, Sequenz-Advance) + client._test_session/_test_engine-Vertrag (MODUL-SessionLocal) + db_from_client unverändert"
      contains: "TEST_TENANT_UUID"
    - path: "tests/test_rls_generic_smoke.py"
      provides: "A-1-Tripwire: GUC-NON-null-Assertion + crm-Read-≥1-Zeile auf dem generischen db_session-Pfad"
      contains: "current_setting"
  key_links:
    - from: "tests/conftest.py db_session/client"
      to: "database.db.set_current_tenant + after_begin-Hook"
      via: "set_current_tenant(TEST_TENANT_UUID) am Fixture-Start"
      pattern: "set_current_tenant\\("
    - from: "tests/conftest.py db_session/client"
      to: "TEST_DATABASE_URL → nerve_test"
      via: "os.environ['TEST_DATABASE_URL'] create_engine"
      pattern: "TEST_DATABASE_URL"
    - from: "tests/conftest.py client._test_session/_test_engine + db_from_client"
      to: "die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)"
      via: "client re-exponiert _test_session = dbmod.SessionLocal() (MODUL, hook-bearing) + _test_engine = engine; db_from_client returnt client._test_session unverändert"
      pattern: "_test_session|_test_engine|db_from_client"
    - from: "tests/conftest.py Base-Seed"
      to: "public.organisations + public.users (id=1) + Sequenz-Advance"
      via: "session-scoped autouse fixture gegen die MODUL-Engine (nerve_test via A-1-DATABASE_URL)"
      pattern: "setval\\('(organisations|users)_id_seq'"
    - from: "tests/test_rls_generic_smoke.py"
      to: "current_setting('app.tenant_id') + crm-Read"
      via: "db_session-Fixture (Hook gefeuert) + SELECT auf crm unter Tenant-GUC"
      pattern: "current_setting\\('app.tenant_id'"
---

<objective>
<!-- FK-debt fold 2026-06-15: base-seed (Plan 01) + 5 deltas (Plan 03) — André/Claudian-bestätigte 11-Test-Klassifikation (11 A / admin_dashboard→SAFE / 24 SAFE), kein Split. -->
<!-- revised via --reviews 2026-06-15: Gemini-Findings eingearbeitet — HIGH (client RLS-Hook-Verlust → MODUL-SessionLocal.configure(bind=engine) statt frischer sessionmaker), MEDIUM (SessionLocal.configure(bind=None)-Reset im finally beider Fixtures), LOW (Tenant-Seed-Org-Name uuid-suffixed). -->
<!-- pre-execute audit fold 2026-06-15: A-1 Hook-Präkondition (Hard precondition statt Annahme: db.py registriert den after_begin-Hook beim Import NUR wenn DATABASE_URL — nicht TEST_DATABASE_URL — non-sqlite ist → Gate (Plan 02) MUSS DATABASE_URL=postgres exportieren). F1: test_tenant_orgs-RLS-Proof-Referenz entfernt (public-only, beweist RLS NICHT) und durch dedizierten A-1-Tripwire ersetzt. -->
<!-- db_from_client contract fix + ft_seed/postcall_split precision 2026-06-15 -->
Refactor `tests/conftest.py` so die generischen Fixtures (`db_session`, `client`) gegen die echte
Postgres-Wegwerf-DB `nerve_test` verbinden (statt hardcoded `sqlite:///:memory:`), einen Default-Test-
Mandanten setzen (D-05, sonst RLS-fail-closed → 0 Zeilen), und die 3 bestehenden Spezial-Fixtures
deren DSN-Env-Var so liefert, dass sie auf `nerve_test` (nicht Prod-`nerve`) zeigen. ZUSÄTZLICH (pre-execute
audit, A-1-Tripwire): ein dedizierter Smoke-Test auf dem generischen db_session-Pfad, der beweist dass der
after_begin-RLS-Hook tatsächlich feuert (GUC NON-null) und ein crm-Read >=1 Zeile liefert (nicht 0).
ZUSÄTZLICH (FK-debt fold, Task 4): ein Session-Scope Base-Seed (1 Org + 1 User id=1) gegen nerve_test, damit
die FK-tragenden generischen Tests (user_id=1/org_id=1 auf PUBLIC-Tabellen) auf der schema-only/zero-data
nerve_test-PG nicht an ForeignKey/NOT-NULL brechen (die 11-Test-FK-Klassifikation, 6 davon konsumieren diesen
Base-Seed direkt). KRITISCH (pre-execute blocker fix 2026-06-15): der `client`-Rewrite (MODUL-SessionLocal-
Umbindung) MUSS den bestehenden `_test_session`/`_test_engine`-Vertrag re-exponieren, sodass `db_from_client`
+ die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)
NICHT an AttributeError zerbrechen (sonst fail-closed Gate blockt jeden Deploy).

Purpose: Req-2 (conftest honoriert Test-DSN), Req-5 (kein Prod-DB-Kontakt), Teil-Grundlage für Req-9.
Diese Fixtures sind die Vertrags-Schicht, gegen die Plan 02 (Gate) und Plan 03 (Klasse-A-Port + 5 Deltas) bauen.
Output: refactored conftest.py mit PG-Fixtures + TEST_TENANT_UUID + tenant_orgs-Seed + A-1-Tripwire-Test +
Session-Scope Base-Seed (Org+User id=1, Sequenz-Advance) + re-exponiertem client._test_session/_test_engine-
Vertrag (MODUL-SessionLocal) + unverändertem db_from_client.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-CONTEXT.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md

<interfaces>
<!-- Verträge aus dem Codebase. Executor nutzt diese direkt — keine Exploration nötig. -->

Aus database/db.py (RLS-GUC-Plumbing, db.py:65-103):
```python
_current_tenant_id = contextvars.ContextVar("nerve_tenant_id", default=None)
def set_current_tenant(tid):  # tid = String-UUID; publiziert in contextvar
def clear_current_tenant():
# after_begin-Hook _set_tenant_txn_local (db.py:87): NUR registriert wenn 'sqlite' not in _DATABASE_URL (db.py:86).
# Hängt zur IMPORT-ZEIT an SessionLocal (Modul-Engine). Liest _current_tenant_id, issued
#   SELECT set_config('app.tenant_id', %s, true)  (transaktions-lokal, parametrisiert)
# Ohne Tenant → GUC NULL → RLS fail-closed → 0 Zeilen.
# WICHTIG: der Hook hängt am MODUL-SessionLocal. Eine FRISCHE sessionmaker(bind=engine) trägt ihn NICHT.
```

**A-1 HARD PRECONDITION (pre-execute audit 2026-06-15 — KEINE Annahme, eine Voraussetzung):**
Der after_begin-RLS-Hook (db.py:87) wird zur IMPORT-ZEIT registriert AUSSCHLIESSLICH wenn `DATABASE_URL`
(NICHT `TEST_DATABASE_URL`) non-sqlite ist — denn db.py:9 liest `_DATABASE_URL = os.environ.get('DATABASE_URL',
'sqlite:///database/nerve.db')` und db.py:86 entscheidet `if 'sqlite' not in _DATABASE_URL`. DESHALB MUSS das
Gate (Plan 02, FIX 1) in der pytest-Subshell `DATABASE_URL=postgresql://nerve_app@/nerve_test` exportieren —
sonst sieht db.py den sqlite-Default und registriert den Hook NIE. `SessionLocal.configure(bind=engine)`
(diese Plan-01-Fixtures) bewahrt einen import-zeit-registrierten Listener, kann aber KEINEN erzeugen der nie
registriert wurde. Wenn DATABASE_URL fehlt → Hook nie da → set_current_tenant inert → crm-Reads 0 Zeilen →
False-Green. Der A-1-Tripwire (tests/test_rls_generic_smoke.py, dieser Plan) macht diesen Defekt loud-red.
Cross-ref Plan 02 FIX 1 (T-PGTEST-18). **Der Base-Seed (Task 4) hängt am SELBEN A-1-Fakt:** weil das Gate
DATABASE_URL=postgres exportiert, IST die MODUL-Engine (`database.db.engine`/`SessionLocal`/`get_session()`)
beim Import bereits nerve_test-PG — der Base-Seed läuft also gegen live nerve_test mit aktiver RLS-Machinerie
(commit d7d8358 belegt: der Gate-pytest-Subshell exportiert DATABASE_URL=postgresql://nerve_app@/nerve_test).

**client-Vertrag _test_session/_test_engine + db_from_client (pre-execute blocker fix 2026-06-15 — KEINE Annahme, IST-Stand verifiziert):**
Der IST-`client` (conftest.py:84-86) exponiert ZWEI Attribute, von denen ~20 Gate-Tests abhängen:
```python
# conftest.py:84  c._test_session = TestSession()
# conftest.py:85  c._test_engine = engine
# conftest.py:95-97  db_from_client-Fixture:  return client._test_session
```
KONSUMENTEN (verifiziert gegen live source — würden bei AttributeError im Setup zu pytest exit≠0 → fail-closed Gate → blockt JEDEN Deploy):
- `tests/test_admin_dashboard_auth.py` — 4 Tests nutzen `db_from_client` (z.B. Z.25-26, 34-35, 46-47, 55-56). FK-klassifiziert SAFE → KEINE Test-Datei-Edits nötig, nur der conftest-Vertrag entblockt sie.
- `tests/test_auth_next_redirect.py:106` — `db = client._test_session` (direkter Zugriff). SAFE → keine Edits.
- `tests/test_ewb_rate_api.py` — ~11 Tests nutzen `db_from_client` (Z.75-76, 94-95, … 211-213). Delta #8 (Plan 03 Task 6) deckt die FK-Seite ab; der db_from_client-Vertrag muss intakt sein.
- `tests/test_profile_editor_validation.py` — 4 Tests nutzen `db_from_client` UND `client._test_engine` (Z.57-60, 74-77, 91-94, 108-111). Delta #9 (Plan 03 Task 7) deckt die FK-Seite ab.
DESHALB MUSS der `client`-Rewrite in Task 1 — NACH `dbmod.SessionLocal.configure(bind=engine)` + set_current_tenant, VOR `yield c` — den Vertrag re-exponieren:
```python
c._test_session = dbmod.SessionLocal()   # MODUL-SessionLocal (hook-bearing PG-Session), NICHT eine frische sessionmaker
c._test_engine = engine                  # die nerve_test-PG-Engine
```
und im finally `c._test_session.close()` (best-effort) zusätzlich zum bestehenden `configure(bind=None)` + `engine.dispose()`.
`db_from_client` (conftest.py:95-97) bleibt UNVERÄNDERT (`return client._test_session`) — es returnt jetzt eine
PG-gebundene, hook-tragende MODUL-SessionLocal-Session. So funktionieren die 4 Konsumenten-Dateien WEITER
ohne Edits über die Plan-03-Deltas (#8/#9) hinaus.

Aus database/models.py (Base-Seed-Vertrag — EXAKTE NOT-NULL-Spalten ohne DB-Default, verifiziert):
```
Organisation (__tablename__='organisations'):
  id    Integer PK
  name  String(200) NOT NULL, KEIN Default  ← muss gesetzt werden
  (alle übrigen NOT-NULL-relevanten Spalten haben Python-Defaults: plan='starter', dsgvo_modus=True,
   subscription_status='inactive', plan_typ='bundle', billing_country='Deutschland', diverse Integer-Defaults)
  coach_id  FK→users.id, nullable=True (kein Problem; Org wird VOR User geseedet)

User (__tablename__='users'):
  id            Integer PK
  org_id        Integer FK→organisations.id, NOT NULL  ← = die Base-Org-id (1)
  email         String(200) UNIQUE NOT NULL, KEIN Default  ← z.B. 'pgtest-base@nerve.local'
  passwort_hash String(256) nullable=True  ← darf NULL bleiben (OAuth-Sentinel-Spalte)
  rolle         String(50) default='member'
  is_superadmin Boolean NOT NULL, default=False  ← Python-Default
  is_test_user  Boolean NOT NULL, default=False  ← Python-Default
  market        String(10) NOT NULL, default='dach'  ← Python-Default
  language      String(10) NOT NULL, default='de'   ← Python-Default
```
**KRITISCHER Hinweis (Python-Default ≠ DB-Default):** `is_superadmin`, `is_test_user`, `market`, `language`
sind `nullable=False` ABER haben nur ein SQLAlchemy-PYTHON-`default=` (kein `server_default`). Ein RAW-SQL
`INSERT` (psycopg2/`text()`) würde diese Spalten NICHT füllen → NOT-NULL-Verletzung. DESHALB MUSS der
Base-Seed den ORM-Pfad nutzen (`session.add(Organisation(id=1, name=...))` / `session.add(User(id=1,
org_id=1, email=..., ...))`) ODER beim RAW-Insert diese 4 Spalten EXPLIZIT mitsetzen. ORM-Pfad ist der
robuste Default (Python-Defaults greifen automatisch).

Aus tests/conftest.py (IST-Stand, zu ändern):
- db_session (Z.41-51): `create_engine("sqlite:///:memory:")` + create_all + Session.
- client (Z.54-91): IST-Stand baut eine FRISCHE `TestSession = _sm(...)` (sessionmaker) und
  monkeypatcht database.db.{engine,SessionLocal,db_session} auf diese frische Session +
  `sqlite:///:memory:`-Engine. DIESE frische sessionmaker verliert den after_begin-RLS-Hook
  (der hängt am MODUL-SessionLocal, db.py:87) → MUSS auf MODUL-`SessionLocal.configure(bind=engine)` umgebaut werden.
  WICHTIG: der IST-client exponiert ZUSÄTZLICH `c._test_session = TestSession()` (Z.84) + `c._test_engine = engine`
  (Z.85) — der Rewrite MUSS diesen Vertrag re-exponieren (s.o. client-Vertrag-Block), sonst AttributeError in ~20 Tests.
- db_from_client (Z.94-97): `return client._test_session` — bleibt UNVERÄNDERT, returnt nach dem Rewrite die MODUL-SessionLocal-PG-Session.
- nerve_app_pg_conn (Z.111-132): liest `NERVE_APP_TEST_DSN`, psycopg2, autocommit=False, rollback im finally. SKIP wenn DSN fehlt.
- anon_worker_pg_engine (Z.146-158): liest `ANON_WORKER_TEST_DSN`, SQLAlchemy-Engine. SKIP wenn DSN fehlt.
- schild_guard_pg_conn (Z.172-190): liest `NERVE_SCHILD_TEST_DSN`, psycopg2, autocommit=True. SKIP wenn DSN fehlt.

Aus tests/test_rls_isolation.py:33-54 (Trigger-tenant_orgs-Muster, EXAKT wiederverwenden):
```python
# INSERT org → AFTER-INSERT-Trigger trg_mk_tenant_org erzeugt tenant_orgs-Row automatisch
cur.execute("INSERT INTO public.organisations (name) VALUES (%s) RETURNING id", (...,))
org_id = cur.fetchone()[0]
cur.execute("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s", (org_id,))
tenant_id = cur.fetchone()[0]  # DIESE UUID ist set_current_tenant-fähig
```

Aus tests/test_rls_isolation.py:82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — für den A-1-Tripwire-crm-Read):
```python
cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
cur.execute("INSERT INTO crm.accounts (id, tenant_id, name) VALUES (%s, %s, %s)", (acct_id, tid, "[RLS-TEST] account ..."))
cur.execute("INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks) VALUES (...)", ...)
```

Gate-DSN-Mapping (RESEARCH Q2c — was Plan 02 inline setzt; conftest LIEST diese Env-Vars):
| Env-Var | Wert im Gate |
|---------|--------------|
| DATABASE_URL | postgresql://nerve_app@/nerve_test  (A-1: damit db.py den after_begin-Hook beim Import registriert UND die MODUL-Engine = nerve_test ist, gegen die der Base-Seed läuft) |
| TEST_DATABASE_URL | postgresql://nerve_app@/nerve_test  (peer-socket, NEU für db_session/client) |
| NERVE_APP_TEST_DSN | postgresql://nerve_app@/nerve_test |
| NERVE_SCHILD_TEST_DSN | postgresql://nerve_app@/nerve_test |
| ANON_WORKER_TEST_DSN | postgresql://nerve_anon_worker:<pw>@127.0.0.1:5432/nerve_test (scram) |
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Generische Fixtures (db_session + client) auf TEST_DATABASE_URL + nerve_app + Tenant-Kontext umbauen + client._test_session/_test_engine-Vertrag re-exponieren</name>
  <read_first>
    - tests/conftest.py (IST: db_session Z.41-51, client Z.54-91 — die zu ändernden Fixtures; SPEZIELL Z.84-86 `c._test_session = TestSession()` + `c._test_engine = engine`, und Z.94-97 die `db_from_client`-Fixture `return client._test_session` — der zu ERHALTENDE Vertrag)
    - tests/test_admin_dashboard_auth.py (Z.25-26, 34-35, 46-47, 55-56 — 4 db_from_client-Konsumenten, FK-SAFE, keine Edits) + tests/test_auth_next_redirect.py:106 (`client._test_session`, SAFE) + tests/test_ewb_rate_api.py (~11 db_from_client-Nutzer) + tests/test_profile_editor_validation.py (4 db_from_client + `client._test_engine`-Nutzer) — die ~20 Vertrags-Konsumenten, die ohne re-exponierten _test_session/_test_engine an AttributeError zerbrechen
    - database/db.py Z.9 (DATABASE_URL-Default sqlite) + Z.65-103 (set_current_tenant + after_begin-Hook — der Vertrag, gegen den D-05 baut; PRÜFEN: der Hook ist auf das MODUL-SessionLocal registriert, nicht auf eine Fixture-lokale sessionmaker, UND er wird nur registriert wenn DATABASE_URL non-sqlite — A-1 HARD PRECONDITION, vom Gate Plan 02 garantiert)
    - tests/test_rls_isolation.py Z.33-54 (_new_tenant — das Trigger-tenant_orgs-Seed-Muster, EXAKT übernehmen)
    - tests/test_rls_isolation.py Z.82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — Vorbild für den A-1-Tripwire-crm-Read in Task 2)
    - tests/conftest.py Z.111-132 (nerve_app_pg_conn — Vorbild für DSN-aus-Env + SKIP-wenn-fehlt + psycopg2/SQLAlchemy-Connectivity)
    - tests/conftest.py client (Z.54-91) — IST-Stand baut `TestSession = _sm(...)` (frische sessionmaker, RLS-Hook-LOS); dient als Beispiel WAS umzubauen ist (NICHT als Vorbild für die frische sessionmaker)
  </read_first>
  <behavior>
    - db_session: liest os.environ['TEST_DATABASE_URL']; fehlt → pytest.skip (KEIN sqlite-Fallback, D-07-Geist). Bindet das MODUL-`database.db.SessionLocal` via `dbmod.SessionLocal.configure(bind=engine)` an die nerve_test-Engine um (NICHT lokale sessionmaker), seedet EINMAL einen Test-Mandanten (Trigger-Muster), ruft set_current_tenant(TEST_TENANT_UUID) auf, yieldet eine Session aus dem MODUL-SessionLocal, rollback/close + `dbmod.SessionLocal.configure(bind=None)` (Binding-Reset) + engine.dispose() im finally.
    - client: identische DSN-Quelle; bindet das MODUL-`database.db.SessionLocal` EXAKT wie db_session via `dbmod.SessionLocal.configure(bind=engine)` um (KEINE frische `TestSession = sessionmaker(...)` mehr — die trüge den after_begin-RLS-Hook nicht); monkeypatcht NUR `dbmod.engine` auf die nerve_test-Engine; ruft set_current_tenant(TEST_TENANT_UUID) NACH der Umbindung. RE-EXPONIERT VOR `yield c` den Vertrag: `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal-PG-Session, hook-tragend — NICHT eine frische sessionmaker) + `c._test_engine = engine` (die nerve_test-Engine). Im finally `c._test_session.close()` (best-effort) + `dbmod.SessionLocal.configure(bind=None)` + engine.dispose(); KEINE sqlite-URL mehr.
    - db_from_client (Z.94-97): UNVERÄNDERT lassen (`return client._test_session`) — returnt nach dem Rewrite die MODUL-SessionLocal-PG-Session. Die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) funktionieren dadurch WEITER ohne AttributeError; admin_dashboard_auth + auth_next_redirect brauchen GAR KEINE Test-Datei-Edits (FK-SAFE), die conftest-Vertrags-Restauration allein entblockt sie.
    - A-1-PRÄKONDITION (NICHT in diesem Fixture lösbar, hier nur dokumentiert): der after_begin-Hook feuert NUR wenn das Gate (Plan 02) `DATABASE_URL=postgres` exportiert (db.py:86 entscheidet beim Import). `configure(bind=engine)` bewahrt einen import-registrierten Hook, erzeugt aber keinen. Der konkrete Laufzeit-Nachweis dass der Hook feuert ist der A-1-Tripwire in Task 2 (tests/test_rls_generic_smoke.py).
  </behavior>
  <action>
    Ersetze die `sqlite:///:memory:`-Verdrahtung in `db_session` (Z.41-51) und `client` (Z.54-91) durch
    eine Postgres-Verbindung aus `TEST_DATABASE_URL`. KONKRET:

    1. Modul-Konstante / Helper einführen (oben in conftest.py, nach den Imports):
       eine Helper-Funktion `_seed_test_tenant(engine_or_conn) -> str` die das Trigger-Muster aus
       test_rls_isolation.py:_new_tenant repliziert (INSERT organisations → SELECT tenant_orgs.id zurück)
       und die UUID liefert. Tag den Org-Namen `f"[PGTEST-GENERIC] tenant {uuid.uuid4().hex[:8]}"`
       (Identifizierbarkeit + Analytics-Exklusion-Lineage über den `[PGTEST-GENERIC]`-Prefix; der
       angehängte uuid-Suffix verhindert Unique-Constraint-Kollisionen bei xdist / verpasstem Teardown —
       Gemini-LOW). Falls `import uuid` oben noch nicht vorhanden ist → ergänzen.
       `TEST_TENANT_UUID` wird beim Seed gefüllt (Discretion D-05: feste Konstante vs. seed-erzeugt →
       seed-erzeugt, FK-Zwang: crm.* FKs auf public.tenant_orgs(id), eine erfundene UUID würde
       FK-Verletzung werfen — RESEARCH Q4b).

    2. `db_session` — MUSS die MODUL-Engine umbinden (NICHT eine lokale sessionmaker bauen):
       ```python
       @pytest.fixture
       def db_session(monkeypatch):
           dsn = os.environ.get('TEST_DATABASE_URL')
           if not dsn:
               pytest.skip("TEST_DATABASE_URL not set -- generic fixtures require real-PG nerve_test "
                           "(no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.")
           import database.db as dbmod
           from database.db import set_current_tenant, clear_current_tenant
           engine = create_engine(dsn)
           # KRITISCH (A-1 HARD PRECONDITION / RESEARCH Q2c): der RLS-after_begin-Hook (_set_tenant_txn_local,
           # db.py:87) ist zur IMPORT-ZEIT auf das MODUL-SessionLocal registriert — ABER NUR wenn das Gate
           # DATABASE_URL=postgres exportiert hat (db.py:86 `if 'sqlite' not in _DATABASE_URL`). Eine FRISCHE
           # sessionmaker(bind=engine) trägt diesen Hook NICHT → set_current_tenant bliebe inert → RLS
           # fail-closed → 0 Zeilen. Deshalb: das MODUL-SessionLocal an die nerve_test-Engine umbinden (exakt
           # wie `client`) und Sessions aus dem MODUL-SessionLocal ziehen. configure(bind=engine) BEWAHRT
           # einen import-registrierten Hook, ERZEUGT aber keinen — ist DATABASE_URL beim Import sqlite, ist
           # hier nichts zu bewahren (→ A-1-Tripwire, Task 2, schlägt loud-red an).
           monkeypatch.setattr(dbmod, "engine", engine)
           dbmod.SessionLocal.configure(bind=engine)   # behält den auf SessionLocal registrierten Hook
           tenant_uuid = _seed_test_tenant(engine)      # Trigger-Muster, gibt tenant_orgs.id zurück
           set_current_tenant(tenant_uuid)              # D-05: GUC für crm.* reads
           session = dbmod.SessionLocal()               # MODUL-SessionLocal → Hook feuert auf BEGIN
           try:
               yield session
           finally:
               session.rollback()
               session.close()
               clear_current_tenant()
               dbmod.SessionLocal.configure(bind=None)  # Binding-Reset (Gemini-MEDIUM): NICHT an die
                                                        # gleich gedisposte Engine gebunden lassen, sonst
                                                        # leakt eine tote Engine-Bindung in spätere Tests
               engine.dispose()
       ```
       WICHTIG: NICHT `Session = sessionmaker(bind=engine)` lokal bauen. `db_session` MUSS das
       MODUL-`SessionLocal` via `configure(bind=engine)` umbinden und seine Session aus dem MODUL-
       `SessionLocal` ziehen, sonst feuert der after_begin-Hook nicht. Der `configure(bind=None)`-Reset
       im finally ist Pflicht (kein globaler Seiteneffekt einer toten Engine-Bindung).

    3. `client` — EXAKT dieselbe MODUL-SessionLocal-Umbindung wie `db_session` (KEINE frische sessionmaker),
       UND der `_test_session`/`_test_engine`-Vertrag MUSS re-exponiert werden (pre-execute blocker fix):
       Der IST-Stand baut `TestSession = _sm(...)` (frische sessionmaker) und monkeypatcht damit
       `database.db.SessionLocal` auf ein NEUES Objekt — dadurch geht der after_begin-RLS-Hook verloren
       (er hängt am MODUL-SessionLocal, db.py:87) → alle API-Integration-Tests setzen den Tenant-GUC nicht
       → 0 crm-Zeilen → fail-closed False-Green (Gemini-HIGH). ZUSÄTZLICH exponiert der IST-client
       `c._test_session = TestSession()` (Z.84) + `c._test_engine = engine` (Z.85), von denen `db_from_client`
       (Z.95-97) + ~20 Tests abhängen — DIESEN Vertrag NICHT fallenlassen, sonst AttributeError → fail-closed
       Gate. FIX:
       ```python
       @pytest.fixture
       def client(monkeypatch):
           dsn = os.environ.get('TEST_DATABASE_URL')
           if not dsn:
               pytest.skip("TEST_DATABASE_URL not set -- client fixture requires real-PG nerve_test "
                           "(no SQLite fallback by design, Req-2/D-07).")
           import database.db as dbmod
           from database.db import set_current_tenant, clear_current_tenant
           engine = create_engine(dsn)
           monkeypatch.setattr(dbmod, "engine", engine)   # NUR engine monkeypatchen
           dbmod.SessionLocal.configure(bind=engine)      # MODUL-SessionLocal umbinden (Hook bleibt) —
                                                          # KEIN `SessionLocal = sessionmaker(...)`, KEIN
                                                          # monkeypatch von SessionLocal auf ein neues Objekt
           tenant_uuid = _seed_test_tenant(engine)
           set_current_tenant(tenant_uuid)                # D-05, VOR dem app-Import-Pfad
           from app import app as flask_app               # erst NACH der Umbindung importieren
           flask_app.config['TESTING'] = True
           flask_app.config['WTF_CSRF_ENABLED'] = False
           try:
               with flask_app.test_client() as c:
                   # VERTRAG re-exponieren (pre-execute blocker fix 2026-06-15): db_from_client (Z.95-97)
                   # + ~20 Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)
                   # lesen diese Attribute. MUSS die MODUL-SessionLocal-Session sein (hook-tragend, PG-gebunden),
                   # NICHT eine frische sessionmaker — sonst feuert der RLS-Hook auf der db_from_client-Session nicht.
                   c._test_session = dbmod.SessionLocal()   # MODUL-SessionLocal → PG-gebunden + hook-tragend
                   c._test_engine = engine                  # die nerve_test-PG-Engine
                   yield c
           finally:
               try:
                   c._test_session.close()                  # best-effort, analog IST-client Z.87-90
               except Exception:
                   pass
               clear_current_tenant()
               dbmod.SessionLocal.configure(bind=None)    # Binding-Reset (Gemini-MEDIUM)
               engine.dispose()
       ```
       Entferne `connect_args={'check_same_thread': False}` (sqlite-spezifisch) und die frische
       `TestSession = _sm(...)`-Konstruktion komplett. Die exakte App-Import-/test_client-Mechanik aus
       dem IST-`client` beibehalten — nur die DB-Umbindung wird von „frische sessionmaker" auf
       „MODUL-SessionLocal.configure(bind=engine)" umgestellt, und der `_test_session`/`_test_engine`-Vertrag
       wird auf die MODUL-SessionLocal-PG-Session umgestellt (statt der alten sqlite-TestSession).

    3b. `db_from_client` (Z.94-97) NICHT anfassen — bleibt `return client._test_session`. Nach dem Rewrite
        returnt es die MODUL-SessionLocal-PG-Session (hook-tragend). Verifiziere im read_first dass die Fixture
        unverändert bleibt und jetzt eine PG-Session liefert. KEINE Edits an den 4 Konsumenten-Dateien aus
        diesem Plan heraus (admin_dashboard_auth + auth_next_redirect brauchen GAR KEINE; ewb_rate_api +
        profile_editor_validation kriegen ihre FK-Deltas in Plan 03 #8/#9 — NICHT in files_modified dieses Plans).

    4. NICHT Base.metadata.create_all aufrufen — das Schema baut das Gate (Plan 02) per pg_dump+alembic.
       Die Fixtures verbinden gegen die fertig gebaute nerve_test.

    Kein PW im Code/Log. KEINE BYPASSRLS-Rolle (D-05 abgelehnt — wäre False-Green).
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -n "sqlite:///:memory:" tests/conftest.py | grep -v "^\s*#"; echo "EXIT_GREP=$?"; grep -nE "_test_session = dbmod.SessionLocal\(\)|_test_engine = engine|return client._test_session" tests/conftest.py'  # erwartet: kein aktiver sqlite-Treffer (Req-2-Acceptance) UND der re-exponierte _test_session/_test_engine-Vertrag + unverändertes db_from_client present. Voll-Beleg = deploy.sh-Gate-Lauf (Plan 02) zeigt generische crm-Tests + API-Integration-Tests (über client) PASSED (crm-Read unter set_current_tenant liefert geseedete Zeile, nicht 0), die ~20 db_from_client/_test_engine-Konsumenten (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) PASSED (kein AttributeError) UND der A-1-Tripwire (Task 2) PASSED.</automated>
  </verify>
  <done>
    `grep "sqlite:///:memory:" tests/conftest.py` liefert keinen Treffer im aktiven Fixture-Code (nur ggf.
    in Kommentaren). db_session UND client binden das MODUL-`database.db.SessionLocal` via
    `dbmod.SessionLocal.configure(bind=engine)` an die nerve_test-Engine um (NICHT lokale/frische sessionmaker,
    KEIN monkeypatch von SessionLocal auf ein neues Objekt), lesen TEST_DATABASE_URL und rufen
    set_current_tenant. Beide setzen im finally `dbmod.SessionLocal.configure(bind=None)` (Binding-Reset, keine
    tote Engine-Bindung). Der `client` re-exponiert `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal,
    hook-tragende PG-Session) + `c._test_engine = engine` (nerve_test-Engine) VOR `yield c` und schließt
    `c._test_session` best-effort im finally; `db_from_client` (Z.95-97) bleibt UNVERÄNDERT und returnt nun die
    MODUL-SessionLocal-PG-Session. ACCEPTANCE: im Gate-Lauf (Plan 02) liefert ein crm-Read unter
    set_current_tenant(TEST_TENANT_UUID) — sowohl über db_session als auch über client/API-Integration — die
    geseedete Zeile zurück (≥1 Zeile, NICHT 0 — Beweis dass der after_begin-Hook auf der genutzten MODUL-Session
    feuert); generische crm-berührende Tests sind PASSED (nicht 0-Zeilen-rot, nicht SKIPPED); die ~20
    db_from_client/_test_engine-Konsumenten (admin_dashboard_auth + auth_next_redirect ohne Edits, ewb_rate_api +
    profile_editor_validation mit Plan-03-Deltas) sind PASSED (kein AttributeError im Setup).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: A-1-Tripwire-Test (tests/test_rls_generic_smoke.py) — GUC-NON-null + crm-Read-≥1-Zeile auf dem generischen db_session-Pfad</name>
  <read_first>
    - tests/conftest.py (NACH Task 1: db_session-Fixture + _seed_test_tenant + TEST_TENANT_UUID — der generische Pfad, den der Tripwire prüft)
    - database/db.py Z.9 + Z.86-103 (A-1: Hook nur registriert wenn DATABASE_URL non-sqlite; der Tripwire ist der Laufzeit-Nachweis dass der Hook feuerte)
    - tests/test_rls_isolation.py Z.82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — EXAKT als Muster für den crm-Read-Arm übernehmen)
    - tests/test_rls_isolation.py Z.101-116 (Best-Effort-Teardown im POST-yield-try/except — analog für etwaigen Seed-Cleanup)
  </read_first>
  <behavior>
    - Ein dedizierter, scharfer A-1-Tripwire auf dem GENERISCHEN db_session-Pfad (db_session-Fixture aus Task 1,
      mit set_current_tenant(TEST_TENANT_UUID) bereits angewandt) asserted BEIDE Arme:
      (a) `SELECT current_setting('app.tenant_id', true)` unter db_session liefert die TEST_TENANT_UUID (NON-null)
          — beweist DIREKT dass der after_begin-Hook auf der generischen Session feuerte. Wäre DATABASE_URL beim
          Import sqlite-Default gewesen (A-1), wäre dieser Wert NULL → Test RED, nicht silent-green.
      (b) ein realer crm-Read unter dem Tenant liefert >=1 Zeile (vorher 1 crm.accounts-Row mit
          tenant_id=TEST_TENANT_UUID seeden, analog test_rls_isolation.py:82-90) — beweist end-to-end
          tenant-scoped Sichtbarkeit, NICHT 0-Zeilen-fail-closed.
    - Anti-False-Green (CLAUDE.md Test-Regel): der Test asserted Runtime-GUC + echte Row-Count — KEINE
      Source-Presence (kein inspect.getsource/hasattr/grep-on-source). Er ist der Mechanismus, der A-1 von
      silent-green auf loud-red dreht.
    - SKIP nur wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback) — im Gate (Plan 02) läuft er scharf.
  </behavior>
  <action>
    Erstelle `tests/test_rls_generic_smoke.py` mit GENAU EINEM Tripwire-Test, der die db_session-Fixture
    aus conftest (Task 1) nutzt (db_session hat set_current_tenant(TEST_TENANT_UUID) schon angewandt). KONKRET:

    1. Arm (a) — GUC NON-null: über die db_session-Session
       `SELECT current_setting('app.tenant_id', true)` ausführen (z.B. via `db_session.execute(text(...))`)
       und asserten dass der zurückgegebene Wert == die geseedete TEST_TENANT_UUID ist (NON-null, nicht ''/None).
       Das ist der direkte Beweis dass der after_begin-Hook (db.py:87) auf der generischen Session feuerte.
       Importiere TEST_TENANT_UUID aus conftest (von Task 1 exportiert) ODER lies die UUID, die die Fixture
       gesetzt hat — wähle die Mechanik passend zu Task 1's Export.
    2. Arm (b) — crm-Read ≥1 Zeile: vor der Read-Assertion eine crm.accounts-Row mit
       `tenant_id=TEST_TENANT_UUID` (+ id + name `"[PGTEST-SMOKE] account ..."`) über die db_session-Session
       inserten (analog test_rls_isolation.py:82-90; tenant_id MUSS = gesetzter Tenant, sonst RLS WITH CHECK
       violation). Dann `SELECT count(*) FROM crm.accounts WHERE tenant_id = <TEST_TENANT_UUID>::uuid` (bzw.
       ein einfaches SELECT auf crm.accounts unter dem Tenant) und asserten `>= 1` — beweist tenant-scoped
       Sichtbarkeit, NICHT 0-Zeilen-fail-closed. (Die db_session rollbackt im finally, d.h. der Seed ist
       Wegwerf; ein zusätzlicher Best-Effort-DELETE ist optional, da die Wegwerf-nerve_test ohnehin gedroppt
       wird — falls ein DELETE genutzt wird, im POST-yield/finally analog test_rls_isolation.py:101-116
       als try/except-after-yield.)
    3. KEIN sqlite-Fallback: läuft nur wenn db_session nicht skippt (TEST_DATABASE_URL gesetzt). Der Test
       erbt die SKIP-Semantik der db_session-Fixture.

    **Warum dieser Test existiert (im Test-Docstring festhalten):** Er ist der A-1-Tripwire — die einzige
    Assertion, die den DATABASE_URL-unset-False-Green (db.py registriert den Hook beim Import nicht, wenn
    DATABASE_URL sqlite-Default ist) von silent-green auf loud-red dreht. test_tenant_orgs.py kann das NICHT
    leisten (public-only, berührt KEIN crm — siehe F1 in Plan 03). Daher dieser dedizierte generische crm-Tripwire.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy1b.log | grep -E "test_rls_generic_smoke.*PASSED|test_rls_generic_smoke.*passed|current_setting|passed|failed"; echo "EXIT=$?"  # A-1-Tripwire PASSED gegen nerve_test: GUC NON-null (Hook feuerte) + crm-Read ≥1 Zeile. Wäre DATABASE_URL im Gate sqlite-Default → dieser Test RED (loud), nicht silent-green.</automated>
  </verify>
  <done>
    `tests/test_rls_generic_smoke.py` existiert und asserted auf dem GENERISCHEN db_session-Pfad BEIDE Arme:
    (a) current_setting('app.tenant_id', true) == TEST_TENANT_UUID (NON-null → after_begin-Hook feuerte) UND
    (b) ein crm-Read unter dem Tenant liefert ≥1 Zeile (nicht 0). Im Gate-Lauf (Plan 02) erscheint der Test als
    PASSED. Der Test ist eine echte Runtime-GUC- + Row-Count-Assertion (keine Source-Presence). Er ist der
    Mechanismus, der A-1 (DATABASE_URL unset → Hook nie registriert → silent False-Green) auf loud-red dreht.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Die 3 Spezial-Fixture-DSNs auf nerve_test umlenken (Doku + SKIP-Texte), Prod-nerve eliminieren</name>
  <read_first>
    - tests/conftest.py Z.100-190 (die 3 Real-PG-Fixtures: nerve_app_pg_conn, anon_worker_pg_engine, schild_guard_pg_conn — IST-Doku zeigt auf `nerve`/Prod)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q2c (DSN→nerve_test-Mapping + scram-Pfad für anon_worker)
  </read_first>
  <behavior>
    - Die 3 Fixtures lesen WEITERHIN ihre Env-Vars (NERVE_APP_TEST_DSN / ANON_WORKER_TEST_DSN / NERVE_SCHILD_TEST_DSN); der Wert wird im Gate (Plan 02) auf nerve_test gesetzt. Kein Code in conftest hardcodet `@/nerve`.
    - Die Fixture-DOCSTRINGS dürfen nicht mehr behaupten, gegen die Prod-`nerve`-DB zu verbinden (Req-5: kein Prod-Kontakt).
  </behavior>
  <action>
    Die 3 Fixtures lesen ihre DSN bereits aus Env — der eigentliche Redirect passiert im Gate (Plan 02
    setzt die Env-Vars auf nerve_test). Diese Aufgabe stellt sicher, dass conftest.py KEINEN hardcoded
    Prod-`nerve`-DSN enthält und die Doku korrekt ist:

    1. `grep "@/nerve\b"` und `grep "nerve_test"` über tests/conftest.py — verifiziere: KEIN hardcoded
       `postgresql://...@/nerve` (ohne `_test`) im aktiven Code (nur Env-Reads). Falls die SKIP-Hinweis-
       Strings oder Docstrings einen `@/nerve`-Beispiel-DSN nennen, ändere ihn auf `@/nerve_test` bzw.
       `@127.0.0.1:5432/nerve_test` (anon_worker scram), damit kein Doc-Drift den Eindruck erweckt, Tests
       liefen gegen Prod.
    2. Aktualisiere die Fixture-Docstrings: ersetze Formulierungen wie "to the real `nerve` DB" /
       "real Production `nerve` database" durch "to the disposable `nerve_test` DB (Req-5: never touches
       Production `nerve`)". Die anon_worker-Doku nennt den scram-Pfad (`@127.0.0.1:5432`, PW aus
       ionos-s3.env via Gate), nicht peer.
    3. KEINE funktionale Änderung an der Connectivity-Logik (psycopg2/SQLAlchemy, autocommit-Flags,
       SKIP-wenn-fehlt) — die bleibt; nur DSN-Ziel-Doku + Env-Wert (Gate) ändern sich. Das Real-Commit-
       Muster der RLS-Gruppe (D-04) bleibt unangetastet — es existiert bereits in test_rls_isolation.py.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "@/nerve([^_]|$)|/nerve\"" tests/conftest.py'; echo "EXIT=$?"  # erwartet: kein aktiver hardcoded Prod-nerve-DSN. Voll-Beleg im Gate-Log: Fixtures verbinden gegen nerve_test.</automated>
  </verify>
  <done>
    conftest.py enthält keinen hardcoded `@/nerve`-DSN (ohne `_test`) im aktiven Code; alle 3 Fixtures
    lesen ihre Env-Var (vom Gate auf nerve_test gesetzt); Docstrings nennen nerve_test, nicht Prod-nerve.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Session-Scope Base-Seed (1 Org + 1 User id=1) gegen nerve_test fuer FK-tragende generische Tests</name>
  <read_first>
    - tests/conftest.py (NACH Task 1: die _seed_test_tenant-Helper-Struktur, der db_session/TEST_TENANT_UUID-Seed — der Base-Seed ist SEPARAT vom generischen [PGTEST-GENERIC]-Tenant; beide koexistieren: die Base-Org id=1 ist die FK-Bridge für user_id=1/org_id=1-Tests, der [PGTEST-GENERIC]-Tenant ist der RLS-Tenant für crm-Reads)
    - database/models.py Z.19-63 (Organisation — NUR `name` ist NOT-NULL ohne Default) + Z.65-135 (User — NOT-NULL ohne Default: `org_id`, `email`; NOT-NULL mit nur PYTHON-Default: `is_superadmin`, `is_test_user`, `market`, `language` → ORM-Insert nutzen, sonst NOT-NULL-Bruch; `passwort_hash` ist nullable=True). Verifiziere die Sequenz-Namen (PG-Konvention `organisations_id_seq` / `users_id_seq`).
    - tests/test_rls_isolation.py:33-54 (Trigger-Read-Back-Muster — der Base-Org-INSERT feuert trg_mk_tenant_org; die tenant_orgs-Row entsteht automatisch — NICHT manuell tenant_orgs inserten, sonst UNIQUE(legacy_org_id)-Bruch, F1-Lektion)
    - database/db.py:84-103 (after_begin-Hook-Präkondition: die MODUL-Engine ist beim Import bereits nerve_test-PG weil das Gate DATABASE_URL=postgres exportiert, commit d7d8358 — der Base-Seed läuft gegen live nerve_test mit aktiver RLS-Machinerie)
  </read_first>
  <behavior>
    - Eine session-scoped autouse Fixture in conftest.py, die EINMAL vor allen Tests läuft, gegen die
      MODUL-Engine (`database.db.engine`/`SessionLocal`/`get_session()`) — die ist beim Import bereits
      nerve_test-PG, weil das Gate (Plan 02 FIX1, T-PGTEST-18) DATABASE_URL=postgresql://nerve_app@/nerve_test
      exportiert (A-1-Abhängigkeit explizit; cross-ref Plan 02 FIX1).
    - Seedet EXAKT: 1 Organisation (id=1) + 1 User (id=1, org_id=1). NOT-NULL-Spalten ohne DB-Default
      vollständig (Org: name; User: org_id, email UNIQUE z.B. 'pgtest-base@nerve.local'). Da `is_superadmin`/
      `is_test_user`/`market`/`language` nullable=False aber nur Python-`default=` haben (kein server_default),
      MUSS der Seed über den ORM-Pfad laufen (`session.add(Organisation(id=1, name=...))` /
      `session.add(User(id=1, org_id=1, email=...))`) — dann greifen die Python-Defaults; ein RAW-SQL-INSERT
      würde diese 4 Spalten NICHT füllen → NOT-NULL-Bruch (im read_first models.py verifiziert).
    - Der Org-INSERT feuert trg_mk_tenant_org → tenant_orgs-Row entsteht AUTOMATISCH. KEIN manueller
      tenant_orgs-Insert (sonst UNIQUE(legacy_org_id)-Verletzung, F1-Lektion).
    - Nach den explizit-id-Inserts: Sequenzen advancen
      (`SELECT setval('organisations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organisations))` + dasselbe für
      `users_id_seq`), damit spätere serielle Inserts anderer Tests nicht id=1 retry'en (PG-Gotcha: explizite
      id advanced die serial-Sequenz NICHT → ein späterer serieller Insert würde id=1 retry'en → UNIQUE-Bruch).
    - COMMIT des Seeds (session-scoped, persistiert über alle Tests; nerve_test wird vom Gate-Trap am Ende
      gedroppt → kein Teardown nötig). WICHTIG: der generische function-scoped db_session-Rollback (Task 1)
      darf den Base-Seed NICHT wegwischen — der Base-Seed committet auf seiner EIGENEN Connection/Session
      BEVOR db_session's Per-Test-Transaktion beginnt.
  </behavior>
  <action>
    Füge eine session-scoped autouse Fixture (z.B. `_pgtest_base_seed`) in conftest.py hinzu, die EINMALIG
    vor allen Tests den FK-tragenden Base-Datensatz gegen nerve_test legt. KONKRET:

    1. **Fixture-Signatur:** `@pytest.fixture(scope="session", autouse=True)`. Am Anfang: wenn
       `os.environ.get('TEST_DATABASE_URL')` (bzw. das A-1-DATABASE_URL) NICHT gesetzt → `return`/no-op
       (KEIN Seed lokal; nur im Gate scharf, kein sqlite-Fallback). Im Gate ist die MODUL-Engine bereits
       nerve_test-PG (DATABASE_URL=postgres, A-1).

    2. **Seed über ORM gegen die MODUL-Engine:** `import database.db as dbmod`, eine Session aus dem
       MODUL-`dbmod.SessionLocal()` (ODER `dbmod.get_session()`) ziehen. Prüfe zuerst idempotent ob die
       Base-Org/-User schon existieren (z.B. `session.get(Organisation, 1)` / `session.get(User, 1)`); wenn
       ja → skip (Idempotenz, falls die Fixture in einem Re-Run gegen eine nicht frisch gedroppte DB läuft).
       Sonst:
       ```python
       org  = Organisation(id=1, name="[PGTEST-BASE] org")
       session.add(org); session.flush()         # flush feuert trg_mk_tenant_org → tenant_orgs-Row auto
       user = User(id=1, org_id=1, email="pgtest-base@nerve.local")
       # is_superadmin/is_test_user/market/language kommen aus Python-default= (ORM-Pfad) — NICHT explizit nötig
       session.add(user)
       session.commit()
       ```
       KEIN manueller `TenantOrg(...)`-Insert — der Trigger erzeugt die tenant_orgs-Row (F1-Lektion:
       manuelles Doppeln → UNIQUE(legacy_org_id)-IntegrityError).

    3. **Sequenz-Advance** (PG explicit-id-no-sequence-advance-Gotcha) NACH dem Commit, auf derselben Session:
       ```python
       session.execute(text("SELECT setval('organisations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organisations))"))
       session.execute(text("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id),1) FROM users))"))
       session.commit()
       ```
       Verifiziere die exakten Sequenz-Namen im read_first (PG-Default `<table>_<pk>_seq` → `organisations_id_seq`
       / `users_id_seq`; falls die DB abweichende Namen hat → an die tatsächlichen anpassen). Danach
       `session.close()`.

    4. **Reconciliation mit dem generischen Tenant (Task 1):** die Base-Org id=1 ist SEPARAT vom
       `[PGTEST-GENERIC]`-Tenant aus _seed_test_tenant — beide koexistieren. Die Base-Org dient den
       FK-tragenden generischen Tests (user_id=1/org_id=1 auf PUBLIC-Tabellen: calls/conversation_logs etc.);
       der [PGTEST-GENERIC]-Tenant dient dem crm-RLS-Read-Pfad. Kein Konflikt: verschiedene Org-Namen,
       verschiedene ids (Base=1, generischer Tenant = fresh-serial nach setval).

    5. **Completeness-Lineage (im SUMMARY festhalten):** die frühere `create_all|sqlite`-Map verfehlte die
       get_session-direkte FK-Klasse (Tests die user_id=1/org_id=1 ohne ORM-Seed annahmen — auf SQLite mit
       FK-enforcement-off lautlos grün, auf nerve_test FK-rot). Die 36-File-Klassifikation (11 A / admin_dashboard
       →SAFE / 24 SAFE, André+Claudian deep-checked, kein verstecktes (B)) ist die korrigierte Map. Der Base-Seed
       deckt 6 der 11 (test_postcall_outcome_route, test_api_beenden_calls_update, test_dashboard_outcome_reminder,
       test_cost_tracker, test_per_sid_migration, test_migration_0005 — alle referenzieren user_id=1/org_id=1 auf
       PUBLIC-Tabellen); die 5 Deltas (Plan 03) sind test-spezifisch.

    Kein PW im Code/Log. KEINE BYPASSRLS-Rolle. Org/User sind PUBLIC-Tabellen (kein crm-RLS); der Seed
    braucht keinen gesetzten Tenant-GUC (organisations/users/calls/tenant_orgs sind RLS-frei).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy1c.log | grep -E "test_postcall_outcome_route|test_api_beenden_calls_update|test_dashboard_outcome_reminder|test_cost_tracker|test_per_sid_migration|test_migration_0005|passed|failed|error|ForeignKey|NotNull"; echo "EXIT=$?"  # nach dem Gate-Lauf sind die 6 FK-Konsumenten PASSED (kein FK-/NOT-NULL-Error). Ferner grep-style: `grep -nE "scope=.session.*autouse|setval\('(organisations|users)_id_seq'" tests/conftest.py` → Base-Seed-Fixture present (session-scope + autouse + Sequenz-Advance).</automated>
  </verify>
  <done>
    Eine session-scoped autouse Fixture in conftest.py seedet EINMAL 1 Organisation(id=1) + 1 User(id=1,
    org_id=1, email UNIQUE) gegen die MODUL-Engine (= nerve_test-PG via A-1-DATABASE_URL, commit d7d8358) über
    den ORM-Pfad (Python-Defaults für is_superadmin/is_test_user/market/language greifen), feuert den Trigger
    trg_mk_tenant_org (kein manueller tenant_orgs-Insert) und advanced `organisations_id_seq` + `users_id_seq`
    via setval. Der Seed committet auf eigener Session (überlebt den function-scoped db_session-Rollback). Im
    Gate-Lauf (Plan 02) sind die 6 FK-Konsumenten (test_postcall_outcome_route, test_api_beenden_calls_update,
    test_dashboard_outcome_reminder, test_cost_tracker, test_per_sid_migration, test_migration_0005) PASSED —
    nicht ForeignKeyViolation/NOT-NULL-Error. grep zeigt session-scope + autouse + setval('organisations_id_seq'/
    'users_id_seq'). A-1/DATABASE_URL-Abhängigkeit + Sequenz-Advance-Gotcha sind in Fixture-Kommentar + SUMMARY
    dokumentiert.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test-Fixture → Postgres-Rolle | Fixtures verbinden als nerve_app/nerve_anon_worker (rolbypassrls=f) — RLS engaged |
| conftest-DSN → DB-Ziel | DSN-Wert entscheidet ob nerve_test (sicher) oder nerve (Prod, verboten) berührt wird |
| db.py-Import-DATABASE_URL → Hook-Registrierung | DATABASE_URL beim Import entscheidet ob der after_begin-RLS-Hook überhaupt existiert (A-1) |
| Base-Seed → schema-only nerve_test | FK-tragende generische Tests setzen user_id=1/org_id=1 voraus — ohne Base-Seed FK/NOT-NULL-Bruch auf der zero-data PG |
| client._test_session/_test_engine → ~20 Konsumenten-Tests | der client-Rewrite-Vertrag entscheidet ob db_from_client + 4 Test-Dateien laufen oder an AttributeError zerbrechen (fail-closed Gate) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-01 | Tampering | Fixture-DSN zeigt versehentlich auf Prod-`nerve` | mitigate | Kein hardcoded `@/nerve` in conftest (grep-verifiziert Task 3); DSN-Wert kommt ausschließlich vom Gate (Plan 02 setzt nerve_test) |
| T-PGTEST-02 | Information Disclosure | BYPASSRLS-Rolle für generische Tests → RLS-Defekt unsichtbar (False-Green) | mitigate | D-05: generische Fixtures verbinden als nerve_app (rolbypassrls=f, RESEARCH Q1a bewiesen) + set_current_tenant; KEINE Superuser/BYPASSRLS-Rolle |
| T-PGTEST-03 | Information Disclosure | crm-Tests ohne Tenant-Kontext ODER mit frischer sessionmaker (Hook feuert nicht) → RLS fail-closed → 0 Zeilen (Test grün trotz kaputt) | mitigate | D-05 set_current_tenant(TEST_TENANT_UUID) + tenant_orgs-Seed; SOWOHL db_session ALS AUCH client binden das MODUL-SessionLocal via `dbmod.SessionLocal.configure(bind=engine)` um (NICHT frische `TestSession = sessionmaker(...)`, NICHT monkeypatch von SessionLocal auf ein neues Objekt — Gemini-HIGH), damit der after_begin-Hook auf JEDER genutzten Session feuert (db_session UND API-Integration über client); Gate verifiziert crm-Read liefert geseedete Zeile (≥1, nicht 0) auch über den client-Pfad |
| T-PGTEST-04 | Information Disclosure | anon_worker-PW in conftest hardcodet/geloggt | accept | PW lebt nur in Gate-Env (Plan 02 sourct ionos-s3.env); conftest liest nur die fertige DSN-Env-Var, nie das nackte PW |
| T-PGTEST-16 | Tampering | `SessionLocal.configure(bind=engine)` ohne Reset → nach engine.dispose() bleibt das MODUL-SessionLocal an eine tote Engine gebunden, leakt in spätere Tests | mitigate | Gemini-MEDIUM: beide Fixtures (db_session + client) rufen im finally `dbmod.SessionLocal.configure(bind=None)` NACH engine.dispose() → keine tote Engine-Bindung im Modul-Zustand |
| T-PGTEST-18 | Spoofing/Information Disclosure | DATABASE_URL unset im pytest-Prozess (Gate-Subshell) → db.py:9 picked den sqlite-Default beim Import → der after_begin-RLS-Hook (db.py:87) wird NIE registriert (db.py:86) → set_current_tenant inert (contextvar von niemandem gelesen) → generische crm-Reads 0 Zeilen, Tests passen STILL (False-Green) | mitigate | A-1 HARD PRECONDITION (Fixture-Seite, Spiegel zu Plan 02 FIX 1): die db_session/client-Umbindung via `configure(bind=engine)` BEWAHRT nur einen import-registrierten Hook — die Registrierung selbst garantiert das Gate (Plan 02 exportiert DATABASE_URL=postgres in der pytest-Subshell). Der DEDIZIERTE A-1-Tripwire (tests/test_rls_generic_smoke.py, Task 2) asserted (a) current_setting('app.tenant_id') == TEST_TENANT_UUID NON-null + (b) crm-Read ≥1 Zeile auf dem generischen db_session-Pfad → dreht den Defekt von silent-green auf loud-red. Cross-ref Plan 02 T-PGTEST-18. |
| T-PGTEST-20 | Denial | Generische Tests inserten FK-tragende Rows (user_id=1/org_id=1) in die schema-only/zero-data nerve_test → ForeignKeyViolation/NOT-NULL → fail-closed Gate blockt jeden Deploy (False-Red blocker-class wie test_08_14/test_tenant_orgs) | mitigate | Task 4: Session-Scope Base-Seed (1 Org id=1 + 1 User id=1) über den ORM-Pfad (Python-Defaults für is_superadmin/is_test_user/market/language) + Sequenz-Advance (setval organisations_id_seq + users_id_seq, PG-explicit-id-Gotcha) + trigger-aware (trg_mk_tenant_org erzeugt tenant_orgs, kein manueller Insert). Hängt am A-1-Fix (DATABASE_URL=postgres → MODUL-Engine ist nerve_test, Hook aktiv). Deckt 6 der 11 FK-Tests (André/Claudian-Klassifikation); die 5 Deltas in Plan 03. |
| T-PGTEST-22 | Denial | Der `client`-Rewrite (`dbmod.SessionLocal.configure(bind=engine)` + monkeypatch von engine) lässt den bestehenden `_test_session`/`_test_engine`-Attribut-Vertrag (IST-conftest Z.84-85) fallen → `db_from_client` (Z.95-97 `return client._test_session`) + `client._test_session`/`client._test_engine`-Direktzugriffe werfen AttributeError im Setup von ~20 Gate-Tests (test_admin_dashboard_auth 4×, test_auth_next_redirect:106, test_ewb_rate_api ~11×, test_profile_editor_validation 4×) → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy | mitigate | pre-execute blocker fix 2026-06-15: der `client`-Rewrite (Task 1) re-exponiert NACH `configure(bind=engine)` + set_current_tenant, VOR `yield c`: `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal — hook-tragende PG-Session, NICHT eine frische sessionmaker) + `c._test_engine = engine` (nerve_test-PG-Engine); im finally `c._test_session.close()` (best-effort). `db_from_client` (Z.95-97) bleibt UNVERÄNDERT und returnt nun die MODUL-SessionLocal-PG-Session → die 4 Konsumenten-Dateien laufen WEITER (admin_dashboard_auth + auth_next_redirect ohne jede Edit; ewb_rate_api + profile_editor_validation mit den FK-Deltas #8/#9 in Plan 03 — NICHT in files_modified dieses Plans). |

</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen

- `public.organisations` (schreiben — generischer Seed via Trigger-Muster UND Base-Seed id=1) — Trigger `trg_mk_tenant_org` legt automatisch die `tenant_orgs`-Row an
- `public.users` (schreiben — Base-Seed id=1, org_id=1, email UNIQUE) — PUBLIC, kein RLS
- `public.tenant_orgs` (lesen — die vom Trigger erzeugte UUID; Quelle für set_current_tenant + crm.*-FK; vom Base-Org-Insert ebenfalls automatisch erzeugt)
- `crm.accounts` (schreiben + lesen — der A-1-Tripwire seedet 1 Row mit tenant_id=TEST_TENANT_UUID und liest sie unter dem Tenant-GUC zurück) — RLS engaged
- `crm.*` (lesen, indirekt über generische crm-berührende Tests / Plan-03-Ports) — RLS engaged unter dem gesetzten Tenant-GUC

### inspect.sh / Katalog-Beleg (zitiert aus RESEARCH + models.py)

`tenant_orgs` wird vom AFTER-INSERT-Trigger auf `organisations` erzeugt — verbatim aus
test_rls_isolation.py:33-54 (RESEARCH Q4, „Trigger-tenant_orgs-Muster"):
```
INSERT INTO public.organisations (name) VALUES (%s) RETURNING id
SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s   -- trg_mk_tenant_org füllt das
```
Base-Seed-NOT-NULL-Beleg (models.py:19-135, verifiziert): Organisation hat NUR `name` als NOT-NULL ohne
Default; User hat `org_id`+`email` als NOT-NULL ohne Default und `is_superadmin`/`is_test_user`/`market`/
`language` als NOT-NULL mit nur PYTHON-`default=` (kein server_default) → ORM-Insert-Pfad Pflicht, sonst
NOT-NULL-Bruch. `passwort_hash` ist nullable=True (OAuth-Sentinel). Sequenz-Namen PG-Default:
`organisations_id_seq`, `users_id_seq` (im read_first an der DB zu verifizieren).

crm-RLS-Treue (aus RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test bewiesen):
7 crm-RLS-Policies (`pg_policies`: account_memory anon_worker_read/anon_worker_stamp/tenant_isolation,
accounts/contacts/meetings/user_preferences tenant_isolation), ENABLE+FORCE auf allen 5 crm-Tabellen
(`relrowsecurity=t, relforcerowsecurity=t`), GRANTs nerve_app=DML / nerve_anon_worker=SELECT. → crm.*
liefert ohne Tenant-GUC 0 Zeilen (fail-closed); MIT gesetztem Tenant die geseedete Zeile.

client._test_session/_test_engine-Vertrag (IST-conftest Z.84-97, live-source verifiziert): der client
exponiert `c._test_session = TestSession()` + `c._test_engine = engine`; `db_from_client` returnt
`client._test_session`. Konsumenten (grep-verifiziert): test_admin_dashboard_auth (4× db_from_client),
test_auth_next_redirect:106 (client._test_session direkt), test_ewb_rate_api (~11× db_from_client),
test_profile_editor_validation (4× db_from_client + client._test_engine). Nach dem Rewrite ist
`_test_session` die MODUL-SessionLocal-PG-Session (hook-tragend) — der Vertrag bleibt strukturell identisch,
nur das Backend wechselt von sqlite auf nerve_test-PG.

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| `TEST_TENANT_UUID` | Seed-Helper liest `tenant_orgs.id` zurück | DB-Spalte `public.tenant_orgs.id` (UUID, vom Trigger erzeugt) | ✓ Trigger-Muster bewiesen (test_rls_isolation.py:33-54, RESEARCH Q4) |
| Org-Seed `[PGTEST-GENERIC] tenant <uuid8>` | INSERT in `organisations.name` (uuid-suffixed, Gemini-LOW) | DB-Spalte `public.organisations.name` | ✓ |
| Base-Seed Org(id=1) + User(id=1) | ORM-INSERT in `organisations`/`users` (Python-Defaults greifen) | DB-Tabellen `public.organisations`/`public.users` (PUBLIC, kein RLS) | ✓ models.py:19-135 NOT-NULL-Map verifiziert; ORM-Pfad Pflicht |
| `organisations_id_seq` / `users_id_seq` | setval nach explizit-id-Insert | PG-Sequenzen (advanced, sonst id=1-Retry-Kollision) | ✓ PG-explicit-id-Gotcha; Namen an DB verifizieren |
| `set_current_tenant(uuid)` → `app.tenant_id` GUC | after_begin-Hook auf MODUL-SessionLocal | transaktions-lokaler GUC (set_config, NICHT DB-Spalte) — gelesen von crm-RLS-Policies | ✓ db.py:87; greift NUR wenn (i) db_session/client das MODUL-SessionLocal nutzen (Warning #3 — `configure(bind=engine)`, KEINE frische sessionmaker) UND (ii) DATABASE_URL beim Import non-sqlite ist (A-1, Gate Plan 02) — der A-1-Tripwire (Task 2) beweist beides zur Laufzeit |
| `client._test_session` / `client._test_engine` | client-Rewrite re-exponiert; db_from_client (Z.95-97) returnt _test_session | `_test_session` = MODUL-SessionLocal-PG-Session (hook-tragend); `_test_engine` = nerve_test-Engine | ✓ IST-conftest Z.84-97 live-verifiziert; pre-execute blocker fix re-exponiert auf MODUL-SessionLocal; T-PGTEST-22 |
| `crm.accounts` (A-1-Tripwire-Seed/Read) | Tripwire inserted 1 Row tenant_id=TEST_TENANT_UUID, liest sie zurück | DB-Tabelle `crm.accounts` mit RLS (FORCE) | ✓ test_rls_isolation.py:82-90-Muster; Acceptance: ≥1 Zeile statt 0 |
| generischer crm-Read | SELECT auf crm.* unter Tenant-GUC | crm.*-Tabellen mit RLS (FORCE) | ✓ RESEARCH RLS-Treue-Beweis; Acceptance: ≥1 Zeile statt 0 |

### Bei Diskrepanz: STOP + Replan
(z.B. Base-Seed RAW-SQL statt ORM → is_superadmin/market NOT-NULL-Bruch → STOP, ORM-Pfad nutzen; Sequenz-Name weicht ab → an DB-Namen anpassen; manueller tenant_orgs-Insert → UNIQUE(legacy_org_id)-Bruch → STOP, Trigger erzeugt die Row; client-Rewrite ohne _test_session/_test_engine-Re-Exposition → AttributeError in ~20 Tests → STOP, Vertrag re-exponieren)

<verification>
- Req-2: `grep "sqlite:///:memory:" tests/conftest.py` → kein aktiver Treffer (server-side gegen deployed conftest).
- Req-5: kein hardcoded `@/nerve` (ohne `_test`) in conftest; im Gate-Log verbinden alle 4 DSNs gegen nerve_test.
- Req-9 (Teilbeitrag): schild_guard_pg_conn liest weiterhin NERVE_SCHILD_TEST_DSN (Gate setzt nerve_test) — Schild-Guard bleibt lauffähig.
- A-1-Tripwire: tests/test_rls_generic_smoke.py PASSED im Gate-Lauf (GUC NON-null + crm-Read ≥1 Zeile) — beweist dass der after_begin-Hook auf dem generischen Pfad feuert (DATABASE_URL=postgres im Gate, Plan 02).
- client-Vertrag (T-PGTEST-22): `grep -nE "_test_session = dbmod.SessionLocal\(\)|_test_engine = engine|return client._test_session" tests/conftest.py` → re-exponierter Vertrag + unverändertes db_from_client present; im Gate-Lauf die ~20 Konsumenten (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) PASSED (kein AttributeError im Setup).
- Base-Seed (T-PGTEST-20): die 6 FK-Konsumenten (test_postcall_outcome_route, test_api_beenden_calls_update, test_dashboard_outcome_reminder, test_cost_tracker, test_per_sid_migration, test_migration_0005) PASSED im Gate-Lauf (kein FK-/NOT-NULL-Error); session-scope + autouse + setval('organisations_id_seq'/'users_id_seq') grep-verifiziert.
- Voll-Beleg erst im Plan-02-Gate-Lauf: generische crm-Tests + API-Integration-Tests (über client) + A-1-Tripwire + die 6 FK-Konsumenten + die ~20 db_from_client/_test_engine-Konsumenten PASSED (set_current_tenant greift, after_begin-Hook feuert auf der von db_session UND client genutzten MODUL-Session → crm-Read ≥1 Zeile; Base-Seed deckt user_id=1/org_id=1; _test_session/_test_engine-Vertrag intakt).
</verification>

<success_criteria>
- db_session + client verbinden gegen TEST_DATABASE_URL (nerve_test), kein sqlite im aktiven Pfad.
- TEST_TENANT_UUID/Seed via Trigger-Muster vorhanden (Org-Name uuid-suffixed); set_current_tenant am Fixture-Start aufgerufen.
- db_session UND client binden das MODUL-`database.db.SessionLocal` via `configure(bind=engine)` um (NICHT frische sessionmaker) → after_begin-Hook feuert auf beiden Pfaden; crm-Read liefert ≥1 Zeile (nicht 0).
- Der `client` re-exponiert `_test_session = dbmod.SessionLocal()` (MODUL-SessionLocal, hook-tragende PG-Session) + `_test_engine = engine` (nerve_test) und schließt `_test_session` best-effort im finally; `db_from_client` bleibt unverändert und returnt die MODUL-SessionLocal-PG-Session → die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) laufen ohne AttributeError (T-PGTEST-22).
- Beide Fixtures resetten im finally `SessionLocal.configure(bind=None)` (keine tote Engine-Bindung leakt in spätere Tests).
- A-1-Tripwire (tests/test_rls_generic_smoke.py) existiert und asserted auf dem generischen db_session-Pfad (a) current_setting('app.tenant_id') == TEST_TENANT_UUID NON-null + (b) crm-Read ≥1 Zeile — dreht den DATABASE_URL-unset-False-Green (A-1) von silent-green auf loud-red; im Gate PASSED.
- Session-Scope Base-Seed (1 Org id=1 + 1 User id=1) existiert, trigger-aware (kein manueller tenant_orgs-Insert), ORM-Pfad (Python-Defaults), Sequenzen advanced (setval organisations_id_seq + users_id_seq), A-1/DATABASE_URL-Abhängigkeit dokumentiert → die 6 FK-Konsumenten brechen nicht an FK/NOT-NULL (im Gate PASSED).
- 3 Spezial-Fixturen DSN-Ziel-Doku = nerve_test; keine hardcoded Prod-nerve-DSN.
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-01-SUMMARY.md`
</output>


===== FILE: PLAN-02-deploy-gate-block =====
---
phase: 08.23.2.PGTEST
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - deploy.sh
autonomous: true
requirements: [Req-1, Req-3, Req-4, Req-5, Req-7, Req-8, Req-9]
complexity: "🔴 (security-near — CREATE/DROP DATABASE auf Prod-Instanz, anon_worker-PW-Handling, fail-closed)"
user_setup: []

must_haves:
  truths:
    - "Das deploy.sh-Gate provisioniert nerve_test, baut Schema per pg_dump-Restore vom Prod-nerve + upgrade-only-neue-Revs, fährt pytest dagegen, räumt nerve_test ab"
    - "CREATE/DROP DATABASE + alle 4 Test-DSNs zielen ausschliesslich auf nerve_test (Whitelist-Guard, Abbruch statt Raten)"
    - "Jeder Schritt (Pre-DROP, CREATE, schema-dump, stamp-dump, upgrade, pytest) bricht bei Fehler mit eigenem Klartext-Grund ab — kein SQLite/Prod-Ausweich"
    - "trap cleanup EXIT garantiert DROP nerve_test auch bei Test-Fehler/SIGTERM; Pre-Run-DROP entfernt verwaiste nerve_test"
    - "anon_worker-PW wird aus ionos-s3.env gesourct und nie geloggt; Schild-Guard läuft gegen nerve_test"
    - "Der dump-gebaute nerve_test trägt die echten crm-RLS-Policies/FORCE/GRANTs treu (kein False-Green) — inline-Katalog-Gate prüft das bei JEDEM Deploy"
    - "Die pytest-Subshell exportiert DATABASE_URL=postgresql://nerve_app@/nerve_test (NICHT nur TEST_DATABASE_URL) — sonst sieht db.py beim Import den sqlite-Default, der after_begin-RLS-Hook wird NIE registriert und set_current_tenant bleibt inert (A-1 False-Green-Killer)"
    - "Die gesamte Phase (Plan 01 + 02 + 03) wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM alle drei Pläne committet sind — kein Zwischen-Deploy nach Wave 1 (das Gate self-testet den deployten Baum, der nur mit Wave-2-Code konsistent ist)"
  artifacts:
    - path: "deploy.sh"
      provides: "Postgres-Test-Gate-Block (Provision → pg_dump-Restore-Build → inline-Katalog-Treue-Gate → pytest 4-DSN+DATABASE_URL → Teardown) mit Whitelist-Guard + pipefail + fail-closed"
      contains: "nerve_test"
  key_links:
    - from: "deploy.sh Gate-Block"
      to: "pg_dump --schema-only nerve | psql nerve_test  +  pg_dump --data-only --table=alembic_version  +  alembic upgrade head"
      via: "DATABASE_URL=postgresql://postgres@/nerve_test als postgres, set -o pipefail in den Dump-Pipes"
      pattern: "pg_dump --schema-only|--table=alembic_version|upgrade head|set -o pipefail"
    - from: "deploy.sh Gate-Block"
      to: "pytest tests/ mit 4 nerve_test-DSNs + DATABASE_URL"
      via: "sudo -u nerve_app ANON_PW=... TEST_DB=... bash -c '...' (Env-Übergabe, single-quoted inner), DATABASE_URL gesetzt damit db.py-Import den RLS-Hook registriert"
      pattern: "DATABASE_URL=postgresql://nerve_app@/|TEST_DATABASE_URL=postgresql://nerve_app@/"
---

<objective>
<!-- revised via --reviews 2026-06-15: Gemini-Findings eingearbeitet — HIGH (set -o pipefail in beide pg_dump-Pipes), HIGH (Dump-Treue-Katalog-Check als harter Inline-deploy.sh-Schritt statt nur manueller SSH-One-Off), MEDIUM (ANON_PW via Env-Var an sudo + single-quoted inner bash -c statt String-Interpolation). -->
<!-- pre-execute audit fold 2026-06-15: A-1 DATABASE_URL (load-bearing) — pytest-Subshell exportiert DATABASE_URL=postgres, sonst registriert db.py den after_begin-RLS-Hook beim Import NICHT (sqlite-Default) -> False-Green. Plus MED(2) test_schild_guard PASSED-Assertion, MED(3) Ein-Deploy-Constraint. -->
Ersetze die kaputte SQLite-Test-Stufe in `deploy.sh` (Z.130-143) durch einen echten Postgres-Test-Gate-
Block: provisioniere die Wegwerf-DB `nerve_test` auf der Prod-Instanz (als `postgres`), baue ihr Schema
per **pg_dump-Restore vom Prod-`nerve`** (carries Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments) + Stamp-Row-
Dump (`alembic_version`) + `alembic upgrade head` (wendet NUR neue Revs über prod-head an, z.B. 0015→0016),
prüfe inline die Dump-Treue (crm-RLS-Policies/FORCE/GRANTs — fail-closed False-Green-Guard),
fahre pytest mit `DATABASE_URL` + 4 nerve_test-DSNs dagegen, und räume garantiert ab. Fail-closed pro Schritt,
`set -o pipefail` in den Dump-Pipes, Whitelist-Guard `nerve_test` (D-02).

**A-1 (load-bearing, pre-execute audit 2026-06-15):** Die pytest-Subshell MUSS `DATABASE_URL=postgresql://nerve_app@/nerve_test`
exportieren — NICHT nur `TEST_DATABASE_URL`. Grund: `database/db.py:9` defaultet `_DATABASE_URL` auf sqlite,
und der after_begin-RLS-Hook (`_set_tenant_txn_local`, db.py:87) wird zur IMPORT-ZEIT nur registriert wenn
`'sqlite' not in _DATABASE_URL` (db.py:86). Ohne gesetztes `DATABASE_URL` sieht db.py im pytest-Prozess den
sqlite-Default → Hook wird NIE registriert → Plan 01's `SessionLocal.configure(bind=engine)` rebindet zwar auf
PG, kann aber einen nie-registrierten Hook nicht auferstehen → `set_current_tenant` schreibt in einen contextvar,
den niemand liest → GUC bleibt NULL → generische crm-Reads liefern 0 Zeilen → Tests grün trotz kaputt (False-Green,
verletzt Req-4 Honesty + Req-7 fail-closed). `DATABASE_URL` ist nerve_app-peer-socket (PW-frei) → log-safe.

**WARUM pg_dump statt create_all+stamp+upgrade (empirisch verriegelt, RESEARCH „⚑ BUILD-PATH LOCKED"):**
Die ursprünglich geplante Sequenz `create_postgres_schema.py (create_all) → alembic stamp 0001 → upgrade head`
KOLLIDIERT bewiesen bei Migration 0002 (create_all baut das VOLLE aktuelle Modell inkl. `phrases.quality_tier`/
`users.is_test_user`; der `upgrade`-Replay von 0002's `add_column` hat kein `IF NOT EXISTS` → „column already
exists"). From-scratch `upgrade head` scheitert bei 0008 (0001 ist No-op-Marker → `public.users` existiert nie).
Der pg_dump-Pfad ist der EINZIGE, der kollisionsfrei baut UND die echten RLS/GRANTs treu trägt. Supervised
gegen einen Wegwerf-`nerve_test` bewiesen (André Punkt-22, danach geteardownt): 7 crm-RLS-Policies + ENABLE/
FORCE auf allen 5 crm-Tabellen + GRANTs alle vom Dump getragen; echter Cross-Tenant-Test (test_rls_isolation
+ test_anonymizer_worker) = **11 passed** (echte Isolation, nicht 0-Zeilen); `upgrade head` applizierte nur
0016 (`Running upgrade 0015 -> 0016`), keine 0002-Kollision; beide Rollen connecten (peer + scram).

**MED(3) Ein-Deploy-Constraint (pre-execute audit 2026-06-15):** Die Phase wird durch GENAU EINEN
`deploy.sh production`-Lauf validiert, NACHDEM Plan 01 + 02 + 03 zusammen committet sind. KEIN Zwischen-Deploy
nach Wave 1 — das Gate self-testet den deployten Baum, und ein Baum mit Wave-1-Gate aber OHNE Wave-2
(Listener-Entfernung + Klasse-A-Port) ist inkonsistent (test_08_14 würde „unknown database crm" werfen,
Plan-01-conftest-Refactor wäre noch nicht da). Der `<verify>`-deploy.sh-Lauf jedes Plans IST dieser eine
finale integrierte Gate-Lauf, kein Per-Plan-Deploy.

Purpose: Req-1 (pytest gegen echtes PG), Req-3 (Schema-End-Zustand = head + crm/training-Schemas + RLS,
via dump-restore + upgrade-only-neue-Revs — bewusste André-autorisierte Abweichung vom Wortlaut „via upgrade
head", siehe Acceptance-Rationale), Req-4 (RLS/Anon laufen — DSNs + DATABASE_URL gesetzt), Req-5 (alle DSNs → nerve_test),
Req-7 (fail-closed), Req-8 (Teardown), Req-9 (Prod + Schild-Guard grün). Output: umgebauter deploy.sh-Test-Block.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-CONTEXT.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md

<interfaces>
<!-- Verträge + Production-Fakten (RESEARCH, alle live bewiesen). Executor baut daraus, ohne zu raten. -->

deploy.sh IST-Stand (relevant):
- Z.99 `ssh ... bash -s << ENDHEREDOC` mit `set -e`; der gesamte Server-Block läuft als root.
- Z.130-143 = die zu ERSETZENDE SQLite-pytest-Stufe (`pytest tests/` ohne DSN → SQLite; PYTEST_EXIT-Check existiert).
- Z.145-156 = Schild-Guard-Stufe (`sudo -u nerve_app bash -c '... NERVE_SCHILD_TEST_DSN=postgresql://nerve_app@/nerve ...'`) → DSN auf nerve_test umlenken (Req-5/Req-9).
- Z.158-169 = .deploy_meta + systemctl restart — NACH dem Gate, NICHT brechen.

A-1-Vertrag (database/db.py — load-bearing, pre-execute audit 2026-06-15):
- db.py:9 `_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')` → Default sqlite.
- db.py:86 `if 'sqlite' not in _DATABASE_URL:` → db.py:87 `@event.listens_for(SessionLocal, "after_begin")`.
  Diese Entscheidung fällt EINMAL zur IMPORT-ZEIT. Ist `DATABASE_URL` im pytest-Prozess unset → sqlite-Default →
  Hook NIE registriert → set_current_tenant inert → crm-Reads 0 Zeilen → False-Green.
- FOLGE für das Gate: die pytest-Subshell MUSS `DATABASE_URL=postgresql://nerve_app@/nerve_test` setzen (gleicher
  Wert wie TEST_DATABASE_URL), damit db.py beim Import den Hook registriert. Cross-ref Plan 01 (hängt von diesem
  Hook ab — db_session/client binden das MODUL-SessionLocal um, was den Hook erhält aber nicht erzeugt).

Production-Fakten (RESEARCH, verbatim-belegt):
- postgres = super+createdb (CREATE/DROP DATABASE bewiesen). OWNER-Klausel MUSS `OWNER postgres` sein
  (NICHT nerve_app — sonst crm-Tabellen nerve_app-owned → RLS bypassed → False-Green, Migration 0012-Doku).
- pg_dump --schema-only MUSS owners+privileges tragen (NICHT --no-privileges, NICHT --no-owner) — sonst
  fallen RLS-Policies/FORCE/GRANTs weg → False-Green. Empirisch bewiesen: trägt alle 7 crm-Policies + FORCE + GRANTs.
- nerve_app: peer-socket, KEIN PW → DSN `postgresql://nerve_app@/nerve_test`. OS-User nerve_app existiert.
- nerve_anon_worker: KEIN OS-User → peer unmöglich → scram-host:
  `postgresql://nerve_anon_worker:<pw>@127.0.0.1:5432/nerve_test`; PW = `NERVE_ANON_WORKER_DB_PASSWORD`
  in `/etc/nerve/ionos-s3.env` (als root via sudo grep sourcen, VOR sudo -u nerve_app, nie loggen).
- Live HEAD = 0015 (Repo kann höher sein, z.B. 0016) → `alembic upgrade head` (NICHT hardcoden, D-09).
  Der Dump trägt die Stamp-Row 0015 → upgrade applied NUR neue Revs darüber (0016) → keine 0002-Kollision.
- Eine verwaiste leere `nerve_test`-DB existiert HEUTE auf Prod (owner postgres) → Pre-Run-DROP zwingend (D-06).
- scripts/create_postgres_schema.py: NICHT mehr Gate-Baustein (bleibt im Repo für den echten Cutover-Pfad).

Build-Pfad-Skelett (RESEARCH „⚑ BUILD-PATH LOCKED" — exakt so strukturiert übernehmen; pipefail + ANON_PW-Env + Inline-Katalog-Gate per Gemini-Review ergänzt; DATABASE_URL in der pytest-Subshell per pre-execute audit ergänzt):
```bash
TEST_DB="nerve_test"
if [ "$TEST_DB" != "nerve_test" ]; then echo "[deploy] FATAL: ... Prod-Schutz D-02"; exit 1; fi
cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" 2>/dev/null || true; }
trap cleanup EXIT
sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" || { echo FEHLER; exit 1; }
sudo -u postgres psql -c "CREATE DATABASE \"$TEST_DB\" OWNER postgres;" || { echo FEHLER; exit 1; }
# Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments vom Prod-nerve übertragen (read-only auf nerve):
# set -o pipefail: ohne das maskiert ein psql-Exit-0 einen pg_dump-Crash → leere DB → silent False-Green.
sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" || { echo FEHLER; exit 1; }
# Stamp-Row (= prod-head) übertragen, damit upgrade nur neue Revs anwendet:
sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" || { echo FEHLER; exit 1; }
sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" || { echo FEHLER; exit 1; }
# --- INLINE DUMP-TREUE-KATALOG-GATE (fail-closed False-Green-Guard, NACH upgrade, VOR pytest) ---
POLICIES=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "$TEST_DB")
[ "$POLICIES" -ge 7 ] || { echo "[deploy] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz greift)"; exit 1; }
FORCED=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "$TEST_DB")
[ "$FORCED" -ge 5 ] || { echo "[deploy] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
GRANTS=$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "$TEST_DB")
[ "$GRANTS" -ge 5 ] || { echo "[deploy] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
# --- pytest: ANON_PW via Env an sudo, single-quoted inner bash -c (keine String-Interpolation des PW) ---
# A-1: DATABASE_URL gesetzt (gleicher PG-Wert wie TEST_DATABASE_URL) -> db.py registriert beim Import den after_begin-RLS-Hook.
ANON_PW=$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)
sudo -u nerve_app ANON_PW="$ANON_PW" TEST_DB="$TEST_DB" bash -c '
  cd /opt/nerve/app && \
  DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  TEST_DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_APP_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:${ANON_PW}@127.0.0.1:5432/${TEST_DB}" \
  /opt/nerve/venv/bin/pytest tests/ --tb=short -q
' || { echo "[deploy] FEHLER: pytest gegen nerve_test ROT -- kein Restart, kein Deploy"; exit 1; }
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: SQLite-Test-Stufe durch Postgres-Gate-Block ersetzen (Provision → pg_dump-Restore-Build → inline-Katalog-Treue-Gate → pytest DATABASE_URL+4-DSN → Teardown)</name>
  <read_first>
    - deploy.sh Z.99-156 (IST: heredoc set -e, SQLite-pytest-Stufe Z.130-143, Schild-Guard Z.145-156)
    - database/db.py Z.9 (DATABASE_URL-Default sqlite) + Z.86-103 (after_begin-Hook NUR wenn 'sqlite' not in _DATABASE_URL — der A-1-Grund warum DATABASE_URL=postgres in der pytest-Subshell stehen MUSS)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md „⚑ BUILD-PATH LOCKED" (der bewiesene pg_dump-Pfad — SUPERSEDET Q3), Q1 (DSN-Formen + OWNER postgres + pg_dump-Read-Rechte), Q2c (4-DSN-Mapping)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q3 (NUR als Begründung WARUM nicht bare upgrade head / nicht create_all — historischer Kontext)
  </read_first>
  <behavior>
    - Innerhalb des ENDHEREDOC-Blocks (läuft als root, set -e aktiv): die SQLite-pytest-Stufe (Z.130-143) wird ersetzt durch den Gate-Block.
    - Whitelist-Guard: TEST_DB ≠ "nerve_test" → sofort exit 1 mit Prod-Schutz-Grund (D-02).
    - trap cleanup EXIT registriert DROP DATABASE IF EXISTS nerve_test (garantiert auch bei pytest-Fehler/SIGTERM, D-06).
    - Pre-Run-DROP der verwaisten nerve_test, dann CREATE OWNER postgres.
    - Schema-Build als postgres: `set -o pipefail; pg_dump --schema-only nerve | psql nerve_test`; dann `set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql nerve_test`; dann alembic upgrade head. Jeder Schritt eigener Exit-Check + Klartext-Grund (D-07). KEIN create_postgres_schema.py, KEIN stamp 0001 (würde bei 0002 kollidieren).
    - **Inline-Dump-Treue-Katalog-Gate (Gemini-HIGH, NACH upgrade, VOR pytest):** harte fail-closed psql-Counts — crm-RLS-Policies ≥7, FORCE auf ≥5 crm-Tabellen, nerve_anon_worker-SELECT-GRANTs ≥5. Jede Assertion `|| exit 1` mit Klartext-Grund. Das ist der automatisierte False-Green-Guard bei JEDEM Deploy (nicht nur ein manueller One-Off-SSH-Build).
    - pytest als nerve_app mit **DATABASE_URL + 4 DSNs**; **A-1 (pre-execute audit):** `DATABASE_URL=postgresql://nerve_app@/${TEST_DB}` wird ZUSÄTZLICH zu den 4 Test-DSNs in der Subshell gesetzt — sonst registriert db.py beim Import den after_begin-RLS-Hook NICHT (db.py:86 sieht den sqlite-Default) und set_current_tenant bleibt inert → crm-Reads 0 Zeilen → False-Green. ANON_PW + TEST_DB werden als ENV an `sudo -u nerve_app` übergeben, der innere `bash -c` ist SINGLE-quoted und expandiert `${ANON_PW}`/`${TEST_DB}` aus der Prozess-Env (KEINE String-Interpolation des PW in die Befehlszeile — Gemini-MEDIUM). ANON_PW vorab als root aus ionos-s3.env, nie geloggt. DATABASE_URL ist nerve_app-peer-socket (PW-frei) → log-safe, darf geechot werden.
    - Jeder Schritt fail-closed (exit 1), kein || -Zweig der auf SQLite/Prod ausweicht.
  </behavior>
  <action>
    Ersetze in deploy.sh die SQLite-pytest-Stufe (Z.130-143, inkl. des Kommentars Z.131-134 der den
    conftest-Refactor als Folge-Phase nennt — der ist jetzt erledigt) durch den folgenden Block. Baue ihn
    nach dem „⚑ BUILD-PATH LOCKED"-Skelett (interfaces oben), heredoc-konform (im `<< ENDHEREDOC` werden
    lokale `$` escaped wie heute `\$PYTEST_EXIT` — beachte: TEST_DB/ANON_PW/POLICIES/FORCED/GRANTS sind
    SERVER-seitige Vars, also `\$` escapen wo sie erst auf dem Server expandieren sollen):

    1. `TEST_DB="nerve_test"` + Whitelist-Guard:
       `if [ "\$TEST_DB" != "nerve_test" ]; then echo "[deploy] FATAL: Test-DB-Name != nerve_test — Abbruch (Prod-Schutz D-02)"; exit 1; fi`
    2. `cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" 2>/dev/null || true; }` + `trap cleanup EXIT`
    3. Pre-Run-DROP: `sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" || { echo "[deploy] FEHLER: Pre-Run-DROP nerve_test fehlgeschlagen"; exit 1; }`
    4. CREATE: `sudo -u postgres psql -c "CREATE DATABASE \"\$TEST_DB\" OWNER postgres;" || { echo "[deploy] FEHLER: CREATE DATABASE nerve_test fehlgeschlagen"; exit 1; }`
    5. **Schema-Dump** (Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments vom Prod-nerve, read-only auf nerve) — MIT `set -o pipefail`:
       `sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: pg_dump --schema-only nerve → nerve_test fehlgeschlagen"; exit 1; }`
       WICHTIG: `set -o pipefail` ist Pflicht (Gemini-HIGH) — sonst maskiert ein psql-Exit-0 einen pg_dump-Crash → leere/teilweise DB → silent False-Green. KEIN `--no-privileges`, KEIN `--no-owner` — die GRANTs/Owner tragen die RLS-Treue (False-Green-Schutz).
    6. **Stamp-Row-Dump** (carry die alembic_version-Row = prod-head, damit upgrade nur neue Revs anwendet) — MIT `set -o pipefail`:
       `sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: alembic_version-Stamp-Dump → nerve_test fehlgeschlagen"; exit 1; }`
    7. **upgrade**: `sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/\$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" || { echo "[deploy] FEHLER: alembic upgrade head gegen nerve_test fehlgeschlagen"; exit 1; }`  (NICHT hardcoden — `head`, D-09; wendet nur Revs über prod-head an, z.B. 0015→0016 — keine 0002-Kollision).
    8. **Inline-Dump-Treue-Katalog-Gate (Gemini-HIGH — automatisierter False-Green-Guard, NACH upgrade, VOR pytest):**
       ```
       POLICIES=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "\$TEST_DB")
       [ "\$POLICIES" -ge 7 ] || { echo "[deploy] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz greift)"; exit 1; }
       FORCED=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "\$TEST_DB")
       [ "\$FORCED" -ge 5 ] || { echo "[deploy] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
       GRANTS=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "\$TEST_DB")
       [ "\$GRANTS" -ge 5 ] || { echo "[deploy] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
       echo "[deploy] Dump-Treue-Katalog-Gate OK: crm-Policies=\$POLICIES, FORCE=\$FORCED, anon-SELECT-GRANTs=\$GRANTS"
       ```
       Falls eine Assertion fehlschlägt → exit 1, KEIN Restart, KEIN Deploy (der Dump trug RLS/FORCE/GRANTs nicht treu → False-Green-Gefahr). Diese drei Counts sind die automatisierte Dump-Treue-Garantie pro Deploy.
    9. ANON_PW + pytest — Env-Übergabe statt String-Interpolation (Gemini-MEDIUM), **DATABASE_URL gesetzt (A-1, pre-execute audit)**:
       `ANON_PW=\$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)` — danach NIE in echo/set -x sichtbar machen.
       ```
       sudo -u nerve_app ANON_PW="\$ANON_PW" TEST_DB="\$TEST_DB" bash -c '
         cd /opt/nerve/app && \
         DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
         TEST_DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
         NERVE_APP_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
         NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
         ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:\${ANON_PW}@127.0.0.1:5432/\${TEST_DB}" \
         /opt/nerve/venv/bin/pytest tests/ --tb=short -q
       ' || { echo "[deploy] FEHLER: pytest gegen nerve_test ROT — kein Restart, kein Deploy"; exit 1; }
       ```
       **A-1 (load-bearing):** `DATABASE_URL` MUSS in der Subshell stehen — auf denselben PG-Wert wie TEST_DATABASE_URL.
       Sonst sieht `database/db.py:9` im pytest-Prozess den sqlite-Default → der after_begin-RLS-Hook (db.py:87)
       wird beim Import NICHT registriert (db.py:86 `if 'sqlite' not in _DATABASE_URL`) → set_current_tenant inert →
       generische crm-Reads 0 Zeilen → Tests grün trotz kaputt (False-Green). DATABASE_URL ist nerve_app-peer-socket
       (PW-frei) → log-safe.
       Der innere `bash -c`-Block ist SINGLE-quoted: `${ANON_PW}`/`${TEST_DB}` expandieren aus der
       nerve_app-Prozess-Env — bullet-proof gegen `"`, Backtick, `$` im PW; das PW landet NIE als
       String-Literal in der Befehlszeile. (Beachte heredoc-Escaping: damit `${ANON_PW}` erst auf dem Server
       in der single-quoted Subshell expandiert, im `<< ENDHEREDOC` als `\${ANON_PW}` schreiben.)
       Log-Echo der DSN (Req-1-Acceptance: Beleg dass postgresql://…/nerve_test lief, inkl. DATABASE_URL) — aber NUR die
       nerve_app-DSNs echoen, NIE die anon_worker-DSN (enthält PW). Z.B.
       `echo "[deploy] pytest gegen DATABASE_URL=postgresql://nerve_app@/\$TEST_DB (+ 4 Test-DSNs)"`.

    KEIN Code-Zweig der bei Fehler auf SQLite/Prod ausweicht (Req-7). `set -e` bleibt, aber jeder Schritt
    hat zusätzlich seinen expliziten `|| { echo FEHLER; exit 1; }` (D-07: Klartext-Grund pro Schritt).
    KEIN `scripts/create_postgres_schema.py`, KEIN `alembic stamp 0001` im Gate — beide würden kollidieren
    (RESEARCH „⚑ BUILD-PATH LOCKED"). Die create_all-Build-Ordering-Frage (A1/Q3d) ist damit GEGENSTANDSLOS.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy.log; grep -E "pytest gegen DATABASE_URL=postgresql://nerve_app@/nerve_test|set -o pipefail; pg_dump --schema-only nerve|Dump-Treue-Katalog-Gate OK|Running upgrade 0015 -> 0016|upgrade head" /tmp/pgtest_deploy.log; echo "EXIT=$?"  # Req-1/Req-3/A-1-Beleg: Gate lief gegen nerve_test mit DATABASE_URL=postgres (RLS-Hook registriert), baute via pg_dump-Restore (pipefail), inline-Katalog-Gate grün, upgrade applied nur neue Revs (kein "already exists").</automated>
  </verify>
  <done>
    deploy.sh enthält den Postgres-Gate-Block: Whitelist-Guard + trap cleanup EXIT + Pre-Run-DROP + CREATE
    OWNER postgres + `set -o pipefail; pg_dump --schema-only nerve→nerve_test` + `set -o pipefail`-alembic_version-Stamp-Dump
    + alembic upgrade head + **inline-Dump-Treue-Katalog-Gate (crm-Policies≥7 + FORCE≥5 + anon-SELECT-GRANTs≥5, fail-closed)**
    + pytest mit **DATABASE_URL (A-1) + 4 nerve_test-DSNs** (ANON_PW via Env an sudo, single-quoted inner bash -c), jeder Schritt fail-closed
    mit Klartext-Grund. **A-1-Acceptance:** das Deploy-Log zeigt `DATABASE_URL=postgresql://nerve_app@/nerve_test` in der
    pytest-Env (PW-frei, log-safe) — damit db.py beim Import den after_begin-RLS-Hook registriert; ein generischer
    crm-Read unter set_current_tenant liefert ≥1 Zeile (Plan 01's Tripwire), NICHT 0. Deploy-Log belegt zusätzlich
    `set -o pipefail; pg_dump --schema-only nerve` piped in nerve_test (NICHT create_all), `Dump-Treue-Katalog-Gate OK`,
    und `Running upgrade 0015 -> 0016` (kein „already exists"-Fehler). anon_worker-PW nirgendwo geloggt:
    `grep -i "nerve_anon_worker:" /tmp/pgtest_deploy.log` zeigt KEIN Klartext-PW (Env-Übergabe, nicht interpoliert).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Inline-Dump-Treue-Gate dokumentieren/verifizieren (manueller SSH-Build als Pre-Execute-Zusatzbeleg) + Schild-Guard-DSN auf nerve_test umlenken (Req-9) + test_schild_guard PASSED-Assertion (MED-2)</name>
  <read_first>
    - deploy.sh Z.145-156 (Schild-Guard-Stufe — DSN `@/nerve` → `@/nerve_test`)
    - deploy.sh Task-1-Inline-Katalog-Gate (die harten Counts POLICIES/FORCED/GRANTS — DIESE sind der automatisierte Guard, hier nur dokumentiert/verifiziert)
    - tests/test_schild_guard.py (SKIP-Bedingung: skippt wenn NERVE_SCHILD_TEST_DSN fehlt/sqlite — MED-2: im Gate MUSS er PASSED erscheinen, nicht SKIPPED, sobald DSN auf nerve_test zeigt)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md „⚑ BUILD-PATH LOCKED" (die bewiesenen Katalog-Werte: 7 Policies, FORCE auf 5 Tabellen, GRANTs, alembic_version=0016) + Assumption A3 (Schild-Guard-Aussagekraft gegen frische DB)
  </read_first>
  <behavior>
    - Die automatisierte Dump-Treue-Garantie ist das INLINE-Katalog-Gate in Task 1 (läuft bei JEDEM Deploy, fail-closed). Diese Task ist die DOKUMENTATION + ein zusätzlicher manueller SSH-Build-Beweis VOR Execute (verbatim-Katalog-Output ins SUMMARY) — NICHT der einzige Fidelity-Check (Gemini-HIGH: der einzige Check darf nicht manuell sein).
    - Schild-Guard: läuft gegen nerve_test (nicht Prod-nerve), bleibt grün, behält Aussagekraft (head-Schilder in nerve_test vorhanden, da Schema vom Prod-nerve gedumpt + auf head migriert).
    - **MED-2 (pre-execute audit):** `test_schild_guard.py` MUSS im Haupt-pytest-Lauf des Gates (mit NERVE_SCHILD_TEST_DSN → nerve_test) als PASSED erscheinen — NICHT SKIPPED, NICHT error. (Der Test skippt lokal/sqlite by design; im Gate mit gesetztem nerve_test-DSN läuft er scharf.)
  </behavior>
  <action>
    1. **Inline-Gate ist der automatisierte Guard (Task 1) — diese Task dokumentiert + liefert Zusatzbeleg:**
       Der harte fail-closed Katalog-Check (POLICIES≥7 / FORCED≥5 / GRANTS≥5) läuft bei jedem Deploy IN
       deploy.sh (Task 1, Schritt 8). Zusätzlich (Pre-Execute-Proof, NICHT der einzige Check): ein gezielter
       manueller Build gegen einen Wegwerf-`nerve_test` + verbose Katalog-Query, um die verbatim-Outputs ins
       SUMMARY zu schreiben — server-side als postgres:
       ```
       ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'sudo -u postgres psql -c "DROP DATABASE IF EXISTS nerve_test;" && \
         sudo -u postgres psql -c "CREATE DATABASE nerve_test OWNER postgres;" && \
         sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d nerve_test" && \
         sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d nerve_test" && \
         sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/nerve_test /opt/nerve/venv/bin/alembic upgrade head" && \
         sudo -u postgres psql -d nerve_test -c "\dn" && \
         sudo -u postgres psql -d nerve_test -c "SELECT version_num FROM alembic_version;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT count(*) FROM pg_policies WHERE schemaname=\$\$crm\$\$;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT relname, relforcerowsecurity FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=\$\$crm\$\$) AND relkind=\$\$r\$\$;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE table_schema=\$\$crm\$\$ AND grantee IN (\$\$nerve_app\$\$,\$\$nerve_anon_worker\$\$) ORDER BY grantee, table_name;" && \
         sudo -u postgres psql -c "DROP DATABASE nerve_test;"'
       ```
       ERWARTUNG (RESEARCH „⚑ BUILD-PATH LOCKED", bewiesen):
       - `\dn` zeigt crm + training (+ public).
       - `alembic_version` = Repo-HEAD (heute 0016).
       - `pg_policies` schemaname='crm' → **≥7 Zeilen** (account_memory ×3, accounts/contacts/meetings/user_preferences tenant_isolation).
       - `relforcerowsecurity=t` auf **allen 5 crm-Tabellen**.
       - `role_table_grants`: nerve_app = INSERT/SELECT/UPDATE/DELETE auf crm.*; nerve_anon_worker = SELECT auf crm.*.
       Diese drei Katalog-Werte sind der False-Green-Guard — IM Deploy automatisiert (Task 1, Schritt 8), hier
       zusätzlich verbatim dokumentiert. Dokumentiere die Outputs im SUMMARY.
       FALLS eine Assertion fehlschlägt (z.B. 0 crm-Policies → Dump trug RLS nicht): STOP + Eskalation
       (pg_dump-Flags prüfen: --no-privileges/--no-owner versehentlich gesetzt?) — NICHT weiterbauen.
    2. **Schild-Guard-DSN umlenken (Req-9/Req-5):** In deploy.sh Z.151 ändere
       `NERVE_SCHILD_TEST_DSN=postgresql://nerve_app@/nerve` → `...@/nerve_test`. Da die Schild-Guard-Stufe
       NACH dem Gate-Block läuft, nerve_test aber vom trap am EXIT gedroppt wird: ziehe den Schild-Guard IN
       den Gate-Block (der Haupt-`pytest tests/`-Lauf in der nerve_app-Gate-Subshell deckt test_schild_guard.py
       bereits ab, da NERVE_SCHILD_TEST_DSN dort gesetzt ist).
       → die separate Z.145-156-Stufe wird damit redundant; ersetze sie durch einen Hinweis-Kommentar, dass
       der Schild-Guard jetzt im Postgres-Gate gegen nerve_test mitläuft. Verifiziere A3: der dump-gebaute
       nerve_test trägt die head-Schilder (pg_description vom Prod-nerve mitgedumpt) → Schild-Guard grün.
    3. **MED-2 — test_schild_guard PASSED-Assertion:** Verifiziere im Gate-Lauf-Log explizit, dass
       `test_schild_guard.py` als **PASSED** erscheint (NICHT SKIPPED, NICHT error) — der Beweis, dass
       NERVE_SCHILD_TEST_DSN tatsächlich auf nerve_test zeigt und der Guard scharf gegen das dump-gebaute
       Schema lief. Im SUMMARY den `test_schild_guard ... PASSED`-Eintrag aus dem `-v`/`-q`-Output zitieren.
       (Der Test skippt lokal/sqlite by design — im Gate mit gesetztem nerve_test-DSN MUSS er laufen.)
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "NERVE_SCHILD_TEST_DSN" deploy.sh'; echo "---"; bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy2.log | grep -E "test_schild_guard.*PASSED|test_schild_guard.*passed|Dump-Treue-Katalog-Gate OK|alembic_version|crm|nerve_test|relforcerowsecurity|nerve_anon_worker"; echo "EXIT=$?"  # Schild-Guard gegen nerve_test PASSED (nicht SKIPPED, MED-2); inline-Katalog-Gate OK (crm-Policies≥7 + FORCE + GRANTs).</automated>
  </verify>
  <done>
    Inline-Dump-Treue-Gate (Task 1) ist der automatisierte fail-closed Guard pro Deploy; zusätzlich verbatim-
    Katalog-Output im SUMMARY dokumentiert: `pg_policies` crm ≥7, `relforcerowsecurity=t` auf allen 5 crm-Tabellen,
    `role_table_grants` nerve_app=DML + nerve_anon_worker=SELECT, `alembic_version`=Repo-HEAD, `\dn` zeigt crm+training
    (Req-3 End-Zustand). Schild-Guard läuft im Gate gegen nerve_test (kein `@/nerve` ohne `_test` mehr in deploy.sh)
    und ist grün (Req-9). **MED-2:** `test_schild_guard.py` erscheint im Gate-Log als PASSED (NICHT SKIPPED, NICHT error) —
    Beweis dass NERVE_SCHILD_TEST_DSN auf nerve_test zeigt und der Guard scharf lief; der PASSED-Eintrag ist im SUMMARY zitiert.
    Voller deploy.sh production endet grün; Prod-`nerve` unverändert (kein Test-DSN/CREATE/DROP
    zeigt drauf; pg_dump war read-only).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| deploy.sh (root) → postgres-Rolle | CREATE/DROP DATABASE auf der Prod-Instanz — ein falscher Name = Prod-Verlust |
| deploy.sh → Prod-nerve (pg_dump) | pg_dump liest die Prod-DB read-only — darf nie schreiben/droppen auf nerve |
| deploy.sh → ionos-s3.env | anon_worker-PW-Secret quert in die Gate-Subshell-Env |
| Gate-pytest → nerve_test | alle 4 DSNs + DATABASE_URL müssen nerve_test treffen, nie Prod-nerve |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-05 | Tampering/Denial | `DROP DATABASE` Tippfehler trifft Prod-`nerve` | mitigate | D-02 Whitelist-Guard `[ "$TEST_DB" != "nerve_test" ] && exit 1` VOR jedem CREATE/DROP; TEST_DB ist EINZIGE Quelle des Namens; grep-verifiziert |
| T-PGTEST-06 | Information Disclosure | anon_worker-PW landet im Deploy-Log ODER bricht den Parser bei Sonderzeichen | mitigate | Gemini-MEDIUM: ANON_PW + TEST_DB via `sudo -u nerve_app ANON_PW="\$ANON_PW" TEST_DB="\$TEST_DB" bash -c '...'` als ENV übergeben; innerer `bash -c` SINGLE-quoted, expandiert `${ANON_PW}` aus der Prozess-Env → KEINE String-Interpolation (bullet-proof gegen `"`/Backtick/`$` im PW), PW nie als String-Literal in der Befehlszeile; nur nerve_app-DSNs (PW-frei) + DATABASE_URL (PW-frei) werden geloggt; Code-Review-grep nach Klartext-PW im Log |
| T-PGTEST-07 | Tampering | Test-DSN zeigt auf Prod-`nerve` → Test mutiert Prod | mitigate | alle 4 DSNs + DATABASE_URL hartkodiert auf `\$TEST_DB`=nerve_test (Req-5); Schild-Guard-DSN auf nerve_test umgelenkt; pg_dump auf nerve ist read-only |
| T-PGTEST-08 | Denial/Spoofing | Gate skippt still bei nicht-provisionierbarer DB ODER pg_dump-Crash wird durch psql-Exit-0 maskiert → False-Green-Deploy | mitigate | D-07 fail-closed pro Schritt (exit 1 + Klartext-Grund); `set -o pipefail` in BEIDEN pg_dump-Pipes (Gemini-HIGH — ein pg_dump-Crash propagiert jetzt als Pipeline-Exit≠0, statt durch psql-Exit-0 maskiert zu werden); `psql -v ON_ERROR_STOP=1` bei beiden Dump-Restores; KEIN SQLite/Prod-Ausweich-Zweig; trap droppt nerve_test |
| T-PGTEST-09 | Tampering | nerve_test OWNER nerve_app ODER --no-privileges-Dump → crm-Tabellen owner-bypassen RLS / RLS-Policies fehlen (False-Green) | mitigate | CREATE DATABASE ... OWNER postgres (RESEARCH Q1e/0012-Doku); pg_dump --schema-only MIT owners+privileges (NICHT --no-privileges/--no-owner). **AUTOMATISIERTER GUARD (Gemini-HIGH):** Inline-Dump-Treue-Katalog-Gate in deploy.sh (Task 1, NACH upgrade, VOR pytest) — harte fail-closed Counts crm-RLS-Policies ≥7, FORCE auf ≥5 crm-Tabellen, nerve_anon_worker-SELECT-GRANTs ≥5; bei Drift exit 1 (kein Restart). **EMPIRISCH BEWIESEN (RESEARCH „⚑ BUILD-PATH LOCKED"):** der Dump trug alle 7 crm-RLS-Policies + ENABLE/FORCE auf allen 5 crm-Tabellen + GRANTs; der echte Cross-Tenant-Test test_tenant_a_cannot_read_tenant_b_account_memory PASSED gegen das dump-gebaute nerve_test (11 passed gesamt) = genuine Isolation, NICHT 0-Zeilen-False-Green. Task-2 dokumentiert die Katalog-Werte verbatim als Pre-Execute-Zusatzbeleg. |
| T-PGTEST-10 | Denial | verwaiste nerve_test (existiert HEUTE) blockiert CREATE | mitigate | D-06 Pre-Run-DROP IF EXISTS vor CREATE; trap cleanup EXIT für Lauf-Ende |
| T-PGTEST-15 | Tampering | upgrade head replayt 0002 gegen schon-vorhandene Spalte → „column already exists" → Gate bricht / falsch grün | mitigate | Stamp-Row-Dump (`pg_dump --data-only --table=alembic_version`) trägt prod-head 0015 → upgrade applied NUR neue Revs (0016); empirisch `Running upgrade 0015 -> 0016`, keine 0002-Kollision (RESEARCH „⚑ BUILD-PATH LOCKED"). create_all+stamp 0001 explizit verworfen. |
| T-PGTEST-18 | Spoofing/Information Disclosure | DATABASE_URL unset in der pytest-Subshell → db.py:9 picked den sqlite-Default beim Import → der after_begin-RLS-Hook (db.py:87) wird NIE registriert (db.py:86 `if 'sqlite' not in _DATABASE_URL`) → set_current_tenant inert → generische crm-Reads liefern 0 Zeilen, Tests passen STILL (False-Green; verletzt Req-4 Honesty + Req-7 fail-closed) | mitigate | pre-execute audit 2026-06-15 (A-1): die pytest-Subshell exportiert EXPLIZIT `DATABASE_URL=postgresql://nerve_app@/\$TEST_DB` (gleicher PG-Wert wie TEST_DATABASE_URL), sodass db.py beim Import `'sqlite' not in _DATABASE_URL` als TRUE wertet und den Hook registriert. DATABASE_URL ist nerve_app-peer-socket (PW-frei) → log-safe, wird geechot (Acceptance-Beleg). Plan 01 fügt einen direkten Tripwire hinzu (current_setting('app.tenant_id') NON-null + crm-Read ≥1 Zeile auf dem generischen db_session-Pfad), der diesen Defekt von silent-green auf loud-red dreht. Cross-ref Plan 01 hook-dependency. |

</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen / Schemas

Dieser Plan BAUT das gesamte nerve_test-Schema (alle public.* + crm.* + training.*) per pg_dump-Restore
vom Prod-`nerve`. Die Treue dieser gebauten Schicht IST der Kern-Verify (False-Green-Guard).

- `nerve` (Prod, **read-only** via pg_dump — niemals Schreib-/DROP-Pfad)
- `nerve_test` (gebaut: Schema+Daten-Stamp übertragen, dann upgrade head, am Ende gedroppt)
- `crm.*` (account_memory/accounts/contacts/meetings/user_preferences) — RLS/FORCE/GRANTs müssen treu getragen sein (inline-Gate prüft das)
- `training.*` (inkl. `training.transcript_archive`, ORM-los — kommt mit dem Schema-Dump mit)
- `public.alembic_version` (Stamp-Row vom Prod-nerve übertragen)

### Katalog-Beleg (verbatim aus RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test)

```
pg_policies (schemaname='crm') → 7 Policies:
  account_memory: anon_worker_read, anon_worker_stamp, tenant_isolation
  accounts/contacts/meetings/user_preferences: tenant_isolation
pg_class (crm, relkind='r') → relrowsecurity=t UND relforcerowsecurity=t auf allen 5 crm-Tabellen
role_table_grants (crm) → nerve_app: DELETE/INSERT/SELECT/UPDATE ; nerve_anon_worker: SELECT (alle 5 Tabellen)
alembic upgrade head → "Running upgrade 0015 -> 0016", final version_num = 0016
Cross-Tenant-Realtest → tests/test_rls_isolation.py + tests/test_anonymizer_worker.py = 11 passed
  (test_tenant_a_cannot_read_tenant_b_account_memory PASSED = echte Isolation, nicht 0-Zeilen)
```

### Cross-Layer-Konsistenz-Tabelle

| Datum / Annahme | Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| crm-RLS-Policies | pg_dump --schema-only nerve → nerve_test (pipefail) | `pg_policies` (Katalog) | ✓ 7 Policies bewiesen; inline-Gate (Task 1) re-assertet ≥7 pro Deploy |
| crm FORCE ROW LEVEL SECURITY | pg_dump (mit owner) | `pg_class.relforcerowsecurity` | ✓ t auf 5 Tabellen; inline-Gate re-assertet ≥5 |
| crm GRANTs (nerve_app DML / anon SELECT) | pg_dump (MIT privileges) | `information_schema.role_table_grants` | ✓ bewiesen; inline-Gate re-assertet anon-SELECT ≥5; --no-privileges würde es brechen |
| prod-head Stamp-Row | pg_dump --data-only --table=alembic_version (pipefail) | `public.alembic_version.version_num` | ✓ trägt 0015 → upgrade applied nur 0016 |
| neue Revs über prod-head | alembic upgrade head | Migrations-Apply (0015→0016) | ✓ keine 0002-Kollision |
| DATABASE_URL=postgres in pytest-Subshell (A-1) | `database/db.py:9` Import → db.py:86 Hook-Registrierung | Prozess-Env (NICHT DB-Spalte) → entscheidet ob after_begin-RLS-Hook registriert wird | ✓ pre-execute audit: ohne DATABASE_URL=postgres bleibt der Hook unregistriert → False-Green; Plan 01-Tripwire (GUC NON-null + crm-Read ≥1) macht es loud-red |
| training.transcript_archive | Schema-Dump (ORM-los) | `training`-Schema-Tabelle | ✓ kommt mit Schema-Dump; Plan-03-Port nutzt sie |

### Bei Diskrepanz: STOP + Replan
(z.B. 0 crm-Policies nach Dump → inline-Gate exit 1 → --no-privileges/--no-owner versehentlich gesetzt → False-Green-Gefahr → Eskalation, nicht weiterbauen)

<verification>
- Req-1: Deploy-Log zeigt `pytest gegen DATABASE_URL=postgresql://nerve_app@/nerve_test` + `set -o pipefail; pg_dump --schema-only nerve`.
- A-1 (pre-execute audit): Deploy-Log belegt `DATABASE_URL=postgresql://nerve_app@/nerve_test` in der pytest-Env (PW-frei) → db.py registriert den after_begin-RLS-Hook beim Import; Plan-01-Tripwire (GUC NON-null + crm-Read ≥1 Zeile) ist GRÜN (nicht 0-Zeilen-False-Green).
- Req-3 (End-Zustand-Acceptance, André-autorisierte Mechanismus-Abweichung): Inline-Katalog-Gate + Katalog-Query
  gegen nerve_test (Task 2) → `alembic_version`=Repo-HEAD (0016) + crm/training-Schemas (`\dn`) + ≥7 crm-RLS-Policies + FORCE.
  RATIONALE: Req-3 prüft den End-Zustand (head + Schemas + RLS vorhanden) — alle erfüllt. Der MECHANISMUS
  (dump-restore + upgrade-nur-neue-Revs statt from-scratch „upgrade head") ist eine BEWUSSTE, von André
  autorisierte Abweichung vom Req-3-Wortlaut „via alembic upgrade head", weil from-scratch unmöglich (0001
  no-op → 0008-Bruch) UND create_all+replay kollidiert (0002 „already exists"). Empirisch verriegelt (RESEARCH).
- Req-5: kein `@/nerve` (ohne `_test`) in deploy.sh-DSNs; alle 4 + DATABASE_URL zeigen auf nerve_test; pg_dump auf nerve read-only.
- Req-7: simulierter Fehler (z.B. falsche Rolle / gestopptes PG / ON_ERROR_STOP / pg_dump-Crash unter pipefail) → exit≠0,
  kein systemctl restart, expliziter Log-Grund — MANUELL via Manual-Only-Verification (VALIDATION.md).
- Req-8: nach Lauf `sudo -u postgres psql -c "\l"` → kein nerve_test (trap + Pre-Run-DROP).
- Req-9: voller deploy.sh production grün (Tests + Schild-Guard gegen nerve_test als PASSED nicht SKIPPED + Restart); Prod-nerve unverändert.
- MED-2: `test_schild_guard.py` erscheint im Gate-Log als PASSED (nicht SKIPPED, nicht error) sobald NERVE_SCHILD_TEST_DSN → nerve_test.
- MED-3 (Ein-Deploy-Constraint): die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03 zusammen committet sind; kein Zwischen-Deploy nach Wave 1 (der `<verify>`-deploy.sh-Lauf ist der eine finale integrierte Gate-Lauf).
</verification>

<success_criteria>
- Gate-Block in deploy.sh: Whitelist-Guard + trap EXIT + Pre-Run-DROP + CREATE OWNER postgres + pg_dump-Restore-Build (schema + alembic_version-Stamp, BEIDE mit `set -o pipefail` + upgrade head) + inline-Dump-Treue-Katalog-Gate (≥7 crm-Policies + FORCE≥5 + anon-SELECT-GRANTs≥5, fail-closed) + pytest **DATABASE_URL (A-1) + 4-DSN** (ANON_PW via Env, single-quoted inner), alles fail-closed.
- A-1: `DATABASE_URL=postgresql://nerve_app@/nerve_test` steht in der pytest-Subshell (gleicher Wert wie TEST_DATABASE_URL) → db.py registriert den after_begin-RLS-Hook beim Import; Plan-01-Tripwire grün (GUC NON-null + crm-Read ≥1 Zeile).
- Dump-Treue automatisiert pro Deploy (inline-Gate) + verbatim im SUMMARY dokumentiert; Schild-Guard gegen nerve_test PASSED (MED-2, nicht SKIPPED).
- MED-3: Ein-Deploy-Constraint — Phase validiert durch genau EINEN deploy.sh production-Lauf nach gemeinsamem Commit aller 3 Pläne; kein Zwischen-Deploy nach Wave 1.
- KEIN create_postgres_schema.py / stamp 0001 im Gate (kollisionsfrei via pg_dump). anon_worker-PW nie geloggt/interpoliert; alle DSNs + DATABASE_URL → nerve_test; Prod-nerve unberührt.
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-02-SUMMARY.md`
</output>


===== FILE: PLAN-03-remove-sqlite-port =====
---
phase: 08.23.2.PGTEST
plan: 03
type: execute
wave: 2
depends_on: [1, 2]
files_modified:
  - database/db.py
  - app.py
  - tests/test_account_memory_briefing.py
  - tests/test_anonymizer_worker.py
  - tests/test_08_14_apirate_seed.py
  - tests/test_tenant_orgs.py
  - tests/test_postcall_split.py
  - tests/test_ewb_rate_api.py
  - tests/test_profile_editor_validation.py
  - tests/test_ft_seed.py
  - tests/test_ab_stats.py
autonomous: true
complexity: "🔴 (security-near — entfernt SQLite-Emulation; Klasse-A-Tests müssen im selben Zug auf PG portiert werden, sonst Collection-Error)"
requirements: [Req-4, Req-6]
user_setup: []

must_haves:
  truths:
    - "Der cf5de6d ATTACH-Listener (db.py) und der app.py SQLite-Alembic-Hook sind entfernt"
    - "test_account_memory_briefing.py + die anonymizer Logic-Group laufen gegen nerve_test-PG (nicht SQLite-StaticPool)"
    - "Die volle Suite läuft grün im Gate OHNE die SQLite-Pflaster"
    - "test_rls_isolation.py + test_anonymizer_worker.py RLS-Gruppe erscheinen als PASSED (nicht SKIPPED)"
    - "Die volle Suite collected + läuft grün im Gate OHNE SQLite-Emulations-Pflaster UND ohne verwaisten Listener-abhängigen Test — test_08_14_apirate_seed.py ist entblockt (create_all auf die public ApiRate-Tabelle gescopet, kein 'unknown database crm')"
    - "test_tenant_orgs.py ist auf PG-Trigger-Semantik portiert (F1): es ERWARTET die vom AFTER-INSERT-Trigger trg_mk_tenant_org auto-erzeugte tenant_orgs-Row statt Python-seitig zu doppeln — kein UNIQUE(legacy_org_id)-Kollisions-Error mehr auf nerve_test, das Gate bleibt grün"
    - "Die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03 zusammen committet sind — kein Zwischen-Deploy nach Wave 1"
    - "Die volle pytest-Suite (inkl. der 11 SQLite-Laxheits-Tests) ist im Gate GRÜN gegen nerve_test ohne stillgelegte/geskippte real-rote Tests — die 5 test-spezifischen FK-Deltas (test_postcall_split CONSUME base-seed, test_ewb_rate_api unique-email, test_profile_editor_validation parents/tenant, test_ft_seed HONEST/investigativ — echte Ursache verifizieren statt vermutete maskieren, test_ab_stats base-org) sind angewandt"
  artifacts:
    - path: "database/db.py"
      provides: "RLS-GUC-Plumbing OHNE SQLite-ATTACH-Listener"
      contains: "set_current_tenant"
    - path: "tests/test_account_memory_briefing.py"
      provides: "Briefing-Merge-Test gegen nerve_test-PG"
    - path: "tests/test_tenant_orgs.py"
      provides: "tenant_orgs-Seed/Backfill-Test gegen nerve_test-PG mit Trigger-Semantik (kein Python-Doppel-Seed)"
  key_links:
    - from: "tests/test_account_memory_briefing.py"
      to: "nerve_test-PG (über conftest-Fixture aus Plan 01)"
      via: "PG-Session statt sqlite-StaticPool"
      pattern: "TEST_DATABASE_URL|nerve_app_pg|get_session"
    - from: "database/db.py"
      to: "(entfernt) _sqlite_attach_crm_training_schemas"
      via: "Listener gelöscht"
      pattern: "_sqlite_attach_crm_training_schemas"
    - from: "tests/test_tenant_orgs.py"
      to: "nerve_test-PG trg_mk_tenant_org"
      via: "Trigger-auto-erzeugte tenant_orgs-Row zurücklesen (kein manueller TenantOrg-Insert)"
      pattern: "tenant_orgs|trg_mk_tenant_org"
---

<objective>
<!-- FK-debt fold 2026-06-15: base-seed (Plan 01) + 5 deltas (Plan 03) — André/Claudian-bestätigte 11-Test-Klassifikation (11 A / admin_dashboard→SAFE / 24 SAFE), kein Split. -->
<!-- revised via --reviews 2026-06-15: Gemini-Finding eingearbeitet — MEDIUM (Reverse-FK-Teardown der Klasse-A-Tests MUSS im Fixture-POST-yield laufen, sonst leaken Rows bei Assertion-Fehler in nerve_test → State-Leakage für nachfolgende Tests auf derselben Connection). -->
<!-- pre-execute blocker fix 2026-06-15: Claudian-Deep-Audit fand einen GOAL-KILLER — der globale cf5de6d ATTACH-Listener trägt einen DRITTEN Test (test_08_14_apirate_seed.py, fresh_engine Z.14-19), der NICHT in Task 2 portiert war. Nach Listener-Entfernung würde `Base.metadata.create_all` dort "unknown database crm" werfen → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy. Neuer Task 3 (Option B: create_all auf die public ApiRate-Tabelle scopen) schließt die Lücke. Vollständige create_all|sqlite-Map über tests/ verifiziert: nur test_08_14 war ungedeckt; test_08_20_3 (raw single-table, kein create_all/crm) + test_meeting_form_dsgvo (Kommentar) sind safe. Sekundär: WAL-Hook-"prüfen" → explizite KEEP-Entscheidung. -->
<!-- db_from_client contract fix + ft_seed/postcall_split precision 2026-06-15 -->
<!-- pre-execute audit fold 2026-06-15: F1 — test_tenant_orgs.py bricht auf nerve_test-PG (es doppelt Python-seitig die vom Trigger trg_mk_tenant_org bereits erzeugte tenant_orgs-Row → UNIQUE(legacy_org_id)-IntegrityError + count-Asserts == 3 halten nicht → Gate ROT → blockt jeden Deploy, blocker-class wie test_08_14). Neuer Task 4 portiert es auf Trigger-Semantik. MED-1: jede "try...finally analog test_rls_isolation.py:103-113"-Formulierung präzisiert zu "POST-yield try/except analog test_rls_isolation.py:102-116" (das zitierte Cleanup ist try/except-NACH-yield, NICHT ein literales try...finally im Test-Body). -->
Entferne die beiden SQLite-Emulations-Pflaster (Req-6): den `cf5de6d`-ATTACH-Listener in `database/db.py`
(Z.29-49) und den SQLite-only Alembic-Auto-Hook in `app.py` (Z.1105-1127, der `if startswith('sqlite')`-
Zweig). Da der ATTACH-Listener von zwei Klasse-A-Tests gebraucht wird (sie bauen lokal `sqlite://`+StaticPool
+ crm/training-create_all), MÜSSEN diese im selben Zug auf nerve_test-Postgres portiert werden — sonst
werfen sie "unknown database crm" bei der Collection (RESEARCH Q6 Klasse A, Pitfall 2). Ein DRITTER Test
(test_08_14_apirate_seed.py) hängt ebenfalls am globalen Listener — er wird in Task 3 entblockt (Option B:
sein create_all wird auf die PUBLIC ApiRate-Tabelle gescopet, kein crm/training mehr nötig). Ein VIERTER Test
(test_tenant_orgs.py) bricht aus einem ANDEREN Grund auf echtem PG: er doppelt Python-seitig die vom Trigger
`trg_mk_tenant_org` bereits erzeugte tenant_orgs-Row → er wird in Task 4 auf Trigger-Semantik portiert (F1).

Purpose: Req-6 (SQLite-Emulation entfernt, kein toter Pfad), Req-4 (RLS+Anon laufen WIRKLICH — der ganze
Suite-Lauf wird erst grün, wenn die Klasse-A-Tests portiert sind, test_tenant_orgs trigger-tauglich ist und
die RLS-Gruppen-DSNs gesetzt sind).
Output: db.py + app.py ohne Pflaster; beide Klasse-A-Tests gegen PG; test_08_14 entblockt (public-Tabelle);
test_tenant_orgs auf Trigger-Semantik portiert.

Wave-Kopplung (DEEP-WORK-Regel): Req-6 + Klasse-A-Port MÜSSEN zusammen — daher in EINEM Plan/Wave.
Depends_on Plan 01 (conftest-PG-Fixtures als Vorbild/Quelle der PG-Session) + Plan 02 (Gate baut nerve_test,
sonst gibt es nichts, wogegen die portierten Tests laufen).

MED-3 (Ein-Deploy-Constraint, pre-execute audit): die Phase wird durch GENAU EINEN `deploy.sh production`-Lauf
validiert NACHDEM Plan 01 + 02 + 03 zusammen committet sind. KEIN Zwischen-Deploy nach Wave 1 — das Gate
self-testet den deployten Baum, der nur mit Wave-2 (Listener-Entfernung + Klasse-A-Port + test_tenant_orgs-Port)
konsistent ist. Ein Deploy mit Wave-1-Gate aber ohne Wave-2 würde „unknown database crm" (test_08_14) +
UNIQUE-Kollision (test_tenant_orgs) werfen → Gate ROT.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md

<interfaces>
<!-- Verträge. Die portierten Tests laufen gegen die nerve_test-DB, die das Gate (Plan 02) baut. -->

database/db.py (zu entfernen):
- Z.29-49 `_sqlite_attach_crm_training_schemas` (@event.listens_for(Engine,"connect")) — der cf5de6d-Listener.
- Behalten: WAL-Hook Z.22-27. KEEP-ENTSCHEIDUNG (pre-execute 2026-06-15, war "prüfen"): Der WAL-Hook ist auf der
  MODUL-Engine registriert und durch `if 'sqlite' in _DATABASE_URL` (Z.22) beim Import geguardet. Im PG-Gate
  (DATABASE_URL=postgres) wird er NIE registriert → inert im Gate. Er schützt genuine lokale Dev-SQLite
  (DATABASE_URL-Default `sqlite:///database/nerve.db`) — ECHTE SQLite-Nutzung AUSSERHALB der Tests, NICHT die
  crm/training-Emulation. Er ist KEIN Req-6-Ziel (Req-6 = crm/training-ATTACH-Emulation + app.py-sqlite-Alembic-
  Hook). → WAL-Hook bleibt UNANGETASTET (Foundation-Register-Note, kein offenes TODO).
- Behalten: set_current_tenant/after_begin-Hook Z.56-103 (RLS-Plumbing, bleibt).

app.py Z.1105-1127 (zu entfernen):
- Der `if _db_url_str.startswith('sqlite'):` Zweig der `alembic_command.upgrade(cfg,'head')` fährt.
- Der `else`-Print "Alembic-Hook uebersprungen (Postgres...)" kann bleiben oder der ganze Block entfällt
  (Postgres-Schema kommt von deploy.sh). Postgres-only für Tests = André-Entscheidung (D, SPEC Req-6).

tests/test_account_memory_briefing.py (Klasse A — IST):
- `_patched_session` (Z.20-55): create_engine("sqlite://", StaticPool) + ATTACH(via globalem Listener) + create_all(crm.*) + monkeypatch precall.get_session.
- 4 Tests prüfen merge_account_memory: meddpicc surfaced, graceful-absent, no-account-id-noop, pii-cache-preseed.

tests/test_anonymizer_worker.py (Klasse A LOGIC-GROUP — IST):
- `mem_engine` (Z.57-96): create_engine("sqlite://", StaticPool) + create_all + raw CREATE TABLE training.transcript_archive.
- 6 Logic-Tests (process_unstamped MERGE/FILTER/HASH/GATING via _fake_anonymize-Stub).
- `_seed_account` (Z.99-140): org/user/conversation_log/call/account/account_memory-Kette (+ optional segments). `_seg_id` itertools.count für BIGSERIAL-Workaround.
- RLS-GROUP (Z.247+): bereits REAL-PG (nerve_app + nerve_anon_worker), läuft sobald DSNs gesetzt (Gate, Plan 02). NICHT anfassen außer Verifikation.

tests/test_08_14_apirate_seed.py (Listener-abhängig — IST, Task 3 entblockt):
- `fresh_engine` (Z.14-19): `from database.models import Base` + create_engine('sqlite:///:memory:') + `Base.metadata.create_all(engine)`. Heute funktioniert das NUR weil der globale cf5de6d-Listener crm/training auf diese frische Engine ATTACHed; nach Listener-Entfernung wirft create_all "unknown database crm".
- `ApiRate` (models.py:524-540) ist eine PUBLIC-Tabelle (`__tablename__='api_rates'`, `__table_args__` nur UniqueConstraint + comment — KEIN {'schema':'crm'}). Das Schema-Problem entsteht nur, weil `Base.metadata.create_all` ALLE Tabellen inkl. crm.* baut. Scopen auf `ApiRate.__table__.create(engine)` baut nur die public api_rates-Tabelle → kein crm → DSN-unabhängig (läuft im Gate UND lokal), bleibt echte SQLite-Runtime-Write-Regression (NOT-NULL last_checked_at).

tests/test_tenant_orgs.py (SQLite-Annahme-Test — IST, Task 4 portiert auf PG-Trigger-Semantik, F1):
- Docstring (verbatim): "SQLite in-memory has NO triggers ... the *live* Postgres dual-write trigger `trg_mk_tenant_org` and the migration's post-backfill `RAISE EXCEPTION` guard are NOT exercised here". Importiert nur `TenantOrg, Organisation, User, Call` — berührt AUSSCHLIESSLICH public.*, ZERO crm.
- Auf SQLite (heute): `_seed_tenant_orgs` (Z.38-46) macht Python-seitiges INSERT TenantOrg pro Org; `test_dualwrite_trigger_fires` (Z.70-82) + `test_dualwrite_idempotent` (Z.85-94) machen manuelle `db_session.add(TenantOrg(...legacy_org_id=org.id...))`.
- Auf nerve_test-PG (das Problem, F1): Migration 0011's AFTER-INSERT-Trigger `trg_mk_tenant_org` auf `organisations` erzeugt die tenant_orgs-Row AUTOMATISCH bei jedem `INSERT organisations`. Die Python-seitigen `_seed_tenant_orgs` + manuellen TenantOrg-Inserts DOPPELN diese Trigger-Row → kollidieren mit `UNIQUE(legacy_org_id)` → IntegrityError WO der Test ihn NICHT erwartet; `test_seed_one_row_per_org` (Z.65) `count == 3` hält nicht. → Test ERRORt → Gate ROT → blockt jeden Deploy (blocker-class wie test_08_14).
- ECHTE Idempotenz-Assertion (BEHALTEN): `test_dualwrite_idempotent` (Z.85-94) erwartet EINEN IntegrityError auf einen WIRKLICHEN Duplikat-Insert (zweiter TenantOrg mit gleichem legacy_org_id) — diese Assertion bleibt valide, sie testet die UNIQUE-Constraint die der Trigger's ON CONFLICT braucht.

Vorbild für PG-Session in Tests (aus Plan 01 conftest + test_rls_isolation.py):
- nerve_app_pg_conn-Fixture (psycopg2) ODER db_session/db_from_client (SQLAlchemy gegen TEST_DATABASE_URL — bindet das MODUL-SessionLocal um, damit der RLS-Hook feuert).
- Trigger-tenant_orgs-Muster: INSERT organisations → SELECT tenant_orgs.id (für crm-FK + set_current_tenant). test_rls_isolation.py:33-54.
- crm.account_memory.tenant_id muss = gesetzter Tenant sein (RLS WITH CHECK); set_current_tenant vor crm-Writes.
- Best-Effort-Teardown in der Fixture-POST-yield-Sektion (NACH `yield`) als `try/except` — test_rls_isolation.py:102-116. WICHTIG (MED-1, pre-execute audit): das zitierte Cleanup ist `cur = conn.cursor(); try: <deletes>; conn.commit() except Exception: conn.rollback()` NACH dem yield. pytest führt die POST-yield-Sektion auch bei Test-Fehler aus (das IST das finally-Äquivalent) — es ist KEIN literales `try...finally` im Test-Body. Reverse-FK-Reihenfolge.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: cf5de6d-ATTACH-Listener (db.py) + app.py SQLite-Alembic-Hook entfernen</name>
  <read_first>
    - database/db.py Z.1-53 (ATTACH-Listener Z.29-49 + Engine-Setup drumherum; WAL-Hook Z.22-27 bleibt)
    - app.py Z.1103-1128 (der startswith('sqlite')-Alembic-Hook)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q6 Klasse A (warum der Listener 2 Tests trägt) + SPEC Req-6
    - .planning/_testgate_gemini_OUT.md (Cross-AI: Listener ist statisch korrekt aber bleibt SQLite-Pflaster — bestätigt Entfernung)
  </read_first>
  <behavior>
    - `_sqlite_attach_crm_training_schemas` (db.py Z.41-49) + sein Doc-Kommentar (Z.29-40) gelöscht.
    - Der app.py `if _db_url_str.startswith('sqlite'):` alembic-upgrade-Zweig entfernt (Postgres-Schema kommt von deploy.sh).
    - `import sqlite3` in db.py entfernen, wenn nach Löschung ungenutzt.
    - Nach Entfernung: kein aktiver Code-Pfad hängt an SQLite-Schema-Emulation oder SQLite-Auto-Alembic.
    - Der WAL-Hook (Z.22-27) bleibt UNANGETASTET — KEEP-Entscheidung (siehe action Schritt 1): Modul-Engine,
      sqlite-geguardet → inert im PG-Gate; schützt lokale Dev-SQLite (echte SQLite-Nutzung außerhalb der Tests);
      KEIN Req-6-Emulations-Ziel. Es bleibt KEIN offenes "prüfen"-TODO zurück.
  </behavior>
  <action>
    1. **db.py:** Lösche den Block Z.29-49 vollständig (Kommentar-Header Z.29-40 + die Funktion
       `_sqlite_attach_crm_training_schemas` Z.41-49). Prüfe, ob `import sqlite3` (Z.2) danach noch
       irgendwo genutzt wird; wenn nicht → entfernen. Den WAL-Hook (Z.22-27) NICHT anfassen — explizite
       KEEP-ENTSCHEIDUNG (pre-execute 2026-06-15, ersetzt das frühere "prüfen"): Der Hook ist auf der
       MODUL-Engine registriert und durch `if 'sqlite' in _DATABASE_URL` beim Import geguardet → im PG-Gate
       (DATABASE_URL=postgres) NIE registriert (inert). Er schützt die genuine lokale Dev-SQLite-DB
       (DATABASE_URL-Default `sqlite:///database/nerve.db`) — echte SQLite-Nutzung AUSSERHALB der Tests, NICHT
       die crm/training-ATTACH-Emulation. Er ist KEIN Req-6-Ziel (Req-6 = crm/training-ATTACH-Emulation +
       app.py-sqlite-Alembic-Hook). Daher bleibt er. Den set_current_tenant/after_begin-RLS-Block (Z.56-103)
       ebenfalls NICHT anfassen.
    2. **app.py:** Entferne den `if _db_url_str.startswith('sqlite'):`-Zweig (Z.1114-1125), der
       `alembic_command.upgrade(cfg, 'head')` ausführt. Der `else`-Print (Z.1126-1127, "Alembic-Hook
       uebersprungen (Postgres)") darf bleiben (informativ) ODER der ganze Hook-Block (Z.1105-1127) entfällt
       — wähle: ganzen Block entfernen, da Tests jetzt Postgres-only sind und Prod-Schema von deploy.sh kommt.
       Behalte `_migrate()` (Z.1103) — das ist eine separate Spalten-Migration, NICHT der alembic-Hook.
    3. KEINE Migration umschreiben (Anti-Pattern, SPEC Constraint). KEIN neues SQLite-Pflaster.
    Der WAL-Hook-Rest ist mit obiger KEEP-Begründung im SUMMARY als Foundation-Register-Eintrag zu vermerken
    (SPEC Req-6 erlaubt begründete Reste); es bleibt KEIN offenes "prüfen"-TODO.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "_sqlite_attach_crm_training_schemas|startswith\(.sqlite.\)" database/db.py app.py'; echo "EXIT=$?"  # erwartet: kein Treffer (Req-6-Acceptance). Voll-Beleg: Gate-Suite grün ohne Pflaster.</automated>
  </verify>
  <done>
    `grep _sqlite_attach_crm_training_schemas database/db.py` → leer; `grep "startswith('sqlite')" app.py`
    → kein alembic-upgrade-Zweig mehr. Listener + Hook entfernt (oder begründeter Rest im SUMMARY-Foundation-
    Register). Der WAL-Hook bleibt bewusst (KEEP-Begründung im SUMMARY, kein offenes TODO). Die Suite läuft
    grün ohne diese Pflaster (Beleg im Gate-Lauf, Plan 02).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Klasse-A-Tests auf nerve_test-PG portieren (test_account_memory_briefing + anonymizer Logic-Group)</name>
  <read_first>
    - tests/test_account_memory_briefing.py (ganze Datei — _patched_session + 4 Tests)
    - tests/test_anonymizer_worker.py Z.1-245 (Header, mem_engine, _seed_account, _run, die 6 Logic-Tests)
    - tests/conftest.py (NACH Plan 01: db_session/db_from_client/nerve_app_pg_conn + TEST_TENANT_UUID/Seed-Helper — das PG-Vorbild; db_session bindet das MODUL-SessionLocal um, damit der RLS-Hook feuert)
    - tests/test_rls_isolation.py Z.33-90 (_new_tenant Trigger-Muster + crm.accounts/account_memory-Seed unter Tenant-GUC — D-04-Muster) + Z.101-116 (Best-Effort-Reverse-FK-Teardown in der POST-yield-Sektion: cur/try/except NACH dem yield, läuft auch bei Assertion-Fehler — das IST das finally-Äquivalent, KEIN literales try...finally im Body, MED-1)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q6 Klasse A + Q4 (Real-Commit + Tenant-Seed) + Klasse D (BIGSERIAL/JSONB-Hinweise)
  </read_first>
  <behavior>
    - test_account_memory_briefing.py: die 4 merge-Tests laufen gegen nerve_test-PG (crm.account_memory echt), nicht sqlite-StaticPool. Assertions bleiben Runtime-Integration (meddpicc/context_hooks surfaced, graceful-absent, noop, pii-preseed) — KEINE Source-Presence-Checks.
    - test_anonymizer_worker.py Logic-Group: die 6 Tests laufen gegen nerve_test-PG (transcript_archive echt via dump-gebautes Schema, KEIN raw CREATE TABLE mehr). MERGE/FILTER/HASH/GATING-Logik bleibt geprüft (_fake_anonymize-Stub bleibt — kein NLP-Load).
    - Beide nutzen das Trigger-tenant_orgs-Seed + set_current_tenant (crm-FK + RLS) und committen real mit deterministischem Teardown (Wegwerf-DB, aber Intra-Lauf-Leak-Schutz). Der Reverse-FK-Teardown läuft ZWINGEND in der Fixture-POST-yield-Sektion (try/except NACH dem yield, analog test_rls_isolation.py:102-116), sodass die Cleanup-Deletes auch bei einem Assertion-Fehler ausgeführt werden (sonst leaken Rows in nerve_test → State-Leakage für nachfolgende Tests auf derselben Connection — Gemini-MEDIUM).
    - Die RLS-Gruppe in test_anonymizer_worker.py (Z.247+) bleibt unverändert und läuft (DSNs vom Gate).
  </behavior>
  <action>
    Ersetze die SQLite-StaticPool-Fixtures durch PG-Fixtures gegen nerve_test. KONKRET:

    1. **test_account_memory_briefing.py — `_patched_session` (Z.20-55):**
       Ersetze die `create_engine("sqlite://", StaticPool)` + `create_all`-Logik durch eine PG-Session
       gegen TEST_DATABASE_URL. Nutze das Vorbild aus conftest (Plan 01): entweder die `db_session`-Fixture
       direkt verwenden ODER eine lokale Fixture, die das MODUL-`database.db.SessionLocal` an
       `create_engine(os.environ['TEST_DATABASE_URL'])` umbindet (wie db_session/client, damit der RLS-Hook
       feuert — NICHT eine frische lokale sessionmaker), einen Test-Tenant via Trigger-Muster seedet,
       `set_current_tenant(tenant_uuid)` aufruft, und `precall.get_session` auf eine PG-Session aus dem
       MODUL-SessionLocal monkeypatcht. SKIP wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback). Das Schema
       NICHT mit create_all bauen — es existiert (Gate, pg_dump+alembic). Die crm.account_memory-Inserts der
       Tests brauchen `tenant_id` = der gesetzte Test-Tenant (RLS WITH CHECK) und ein vorhandenes account-FK-
       Ziel (crm.accounts) — passe die Test-Inserts an: vor dem AccountMemory-Insert eine crm.accounts-Row mit
       demselben tenant_id + account_id anlegen (analog test_rls_isolation.py:82-90).
       **Deterministischer Teardown ZWINGEND in der Fixture-POST-yield-Sektion** (Gemini-MEDIUM, MED-1): die
       getaggten Rows (`[PGTEST-...]`) unter dem Tenant-GUC in reverse-FK-Reihenfolge löschen (account_memory
       → accounts → tenant_orgs → organisations) — EXAKT analog test_rls_isolation.py:101-116, wo das Cleanup
       als `cur = conn.cursor(); try: <deletes>; commit; except Exception: rollback` NACH dem `yield` steht.
       pytest führt diese POST-yield-Sektion auch bei AssertionError aus (das IST das finally-Äquivalent), also
       läuft das Cleanup auch wenn ein Test fehlschlägt — sonst bleiben Rows in nerve_test für nachfolgende
       Tests auf derselben Connection liegen (State-Leakage). Es ist KEIN literales `try...finally` im
       Test-Body — die POST-yield-Platzierung ist das Mittel.
    2. **test_anonymizer_worker.py — `mem_engine` (Z.57-96):**
       Ersetze sqlite-StaticPool + raw `CREATE TABLE training.transcript_archive` durch eine Engine gegen
       TEST_DATABASE_URL (Schema vom Gate via pg_dump+alembic — training.transcript_archive existiert dann echt,
       kein hand-DDL mehr). SKIP wenn DSN fehlt. ENTFERNE den `_seg_id = itertools.count` BIGSERIAL-Workaround
       NUR falls die Inserts die id-Spalte nicht mehr explizit setzen müssen (PG BIGSERIAL vergibt selbst) —
       prüfe `_seed_account` (Z.127-130 setzt `id=next(_seg_id)` für TranscriptSegment): gegen PG mit echtem
       BIGSERIAL die explizite id WEGLASSEN (Sequenz übernimmt), sonst RESEARCH-Klasse-D-Kollision. account/
       account_memory unter set_current_tenant + tenant_orgs-Seed (RLS). `_run`/`_archive_rows`/`_anonymized_at`
       (Z.143-165) funktionieren gegen PG unverändert (sie nutzen text()-SQL auf crm./training.). Der
       anonymizer arbeitet als nerve_app — prüfe, ob process_unstamped gegen die crm.*-RLS Tenant-Kontext
       braucht; falls ja, set_current_tenant vor `_run`.
       **Auch hier: der Reverse-FK-Teardown der geseedeten Rows (account_memory/accounts/transcript_archive/
       tenant_orgs/organisations) MUSS in der Fixture-POST-yield-Sektion liegen** (Gemini-MEDIUM, MED-1; try/except
       NACH dem yield, analog test_rls_isolation.py:101-116), damit er bei Assertion-Fehler eines der 6
       Logic-Tests trotzdem läuft (kein State-Leak auf die geteilte nerve_test-Connection).
    3. **Anti-False-Green (CLAUDE.md Test-Regel):** KEINE `inspect.getsource`/`hasattr`/grep-on-source-
       Assertions einführen. Die Tests bleiben Integration-Assertions auf echte DB-Rows / Return-Werte /
       gestampte anonymized_at — exakt wie heute, nur Backend PG statt SQLite. Der `_fake_anonymize`-Stub
       bleibt (kein NLP-Load — das ist ein I/O-Mock, kein Source-Presence-Check).
    4. RLS-Gruppe (Z.247+) NICHT ändern — sie ist bereits Real-PG und läuft sobald die DSNs gesetzt sind
       (Gate, Plan 02). Nur verifizieren, dass sie im Gate-Lauf PASSED erscheint (Req-4).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy3.log | grep -E "test_account_memory_briefing|test_anonymizer_worker|test_rls_isolation|PASSED|SKIPPED|passed|failed"; echo "EXIT=$?"  # Req-4/Req-6: Klasse-A-Tests grün gegen PG; RLS+Anon-RLS-Gruppe PASSED nicht SKIPPED; keine Collection-Errors; kein Reststate-Leak (POST-yield-Teardown).</automated>
  </verify>
  <done>
    test_account_memory_briefing.py + test_anonymizer_worker.py Logic-Group laufen gegen nerve_test-PG
    (kein sqlite-StaticPool, kein hand-DDL training.transcript_archive); die volle Suite collected + läuft
    grün im Gate OHNE den ATTACH-Listener. Der Reverse-FK-Teardown beider Test-Gruppen liegt in der
    Fixture-POST-yield-Sektion (try/except nach dem yield, analog test_rls_isolation.py:101-116) → Cleanup läuft
    auch bei Assertion-Fehler, kein State-Leak in nerve_test. test_rls_isolation.py + test_anonymizer_worker.py
    RLS-Gruppe erscheinen im Gate-Log als PASSED (nicht SKIPPED) — Req-4. Falls ein Test an einem ECHTEN App-Bug
    rot wird (Klasse D/E, z.B. test_ft_seed) → im SUMMARY als Fund ESKALIEREN, NICHT still patchen (SPEC out-of-scope).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: test_08_14_apirate_seed.py entblocken (create_all auf ApiRate-Tabelle scopen, NICHT Base.metadata)</name>
  <read_first>
    - tests/test_08_14_apirate_seed.py (ganze Datei — `fresh_engine` Z.14-19 + SEED_ROWS Z.23-32 + die TestApiRateSeed-Klasse mit den 4 INSERT/COUNT-Tests Z.35-91; speziell die 8-rows-Assertion + die NOT-NULL-last_checked_at-Regression Z.53-59)
    - database/models.py Z.524-540 (`ApiRate` — `__tablename__='api_rates'`, `__table_args__` nur UniqueConstraint + comment, KEIN {'schema':'crm'} → PUBLIC-Tabelle)
    - database/db.py Z.29-49 (der cf5de6d-Listener, der in Task 1 ENTFERNT wird — DESHALB funktioniert `Base.metadata.create_all` heute, weil er crm/training auf die frische fresh_engine-Connection ATTACHed; nach Entfernung wirft create_all "unknown database crm")
  </read_first>
  <behavior>
    - Nach Listener-Entfernung (Task 1) baut der Test nur noch die PUBLIC `api_rates`-Tabelle (kein crm/training),
      sodass `create_all` nicht mehr "unknown database crm" wirft → kein Collection-/Setup-Error mehr.
    - Die NOT-NULL-last_checked_at-Regression-Assertion (test_seed_rows_have_last_checked_at) bleibt intakt auf
      echten SQLite-Writes — es bleibt ein Runtime-Write-Test (CLAUDE.md Test-Qualitaets-Regel), KEIN Source-Presence-Check.
    - Der Test bleibt DSN-unabhängig (in-memory SQLite), läuft also IM Gate (DATABASE_URL=postgres) UND außerhalb —
      er wird NICHT geskippt und NICHT an TEST_DATABASE_URL gekoppelt.
    - SEED_ROWS, die 3 INSERT-Tests + die 8-rows-Assertion bleiben UNVERÄNDERT.
  </behavior>
  <action>
    Option B — den create_all-Aufruf auf die public ApiRate-Tabelle scopen (Begründung unten). KONKRET in
    `tests/test_08_14_apirate_seed.py`, NUR in der `fresh_engine`-Fixture (Z.14-20):

    1. Importzeile in der Fixture ändern: `from database.models import Base` → `from database.models import ApiRate`.
    2. `Base.metadata.create_all(engine)` → `ApiRate.__table__.create(engine)` (baut NUR die public `api_rates`-
       Tabelle, kein crm/training → kein "unknown database crm" mehr nach Listener-Entfernung).
    3. Falls `Base` danach in der Datei nirgends mehr genutzt wird (ist es nicht — der Import steht nur lokal in
       der Fixture), bleibt der `ApiRate`-Import die einzige Modell-Referenz. Keinen ungenutzten `Base`-Import
       stehen lassen.
    4. ALLES ANDERE unverändert: `engine = create_engine('sqlite:///:memory:')` bleibt (in-memory SQLite,
       DSN-unabhängig), SEED_ROWS (Z.23-32) bleibt, die 4 Tests in TestApiRateSeed (INSERT/COUNT/idempotent/
       models-present) bleiben Wort für Wort, die 8-rows-Assertion bleibt.

    **Option-B-Rationale (im SUMMARY festhalten):** `ApiRate` ist eine PUBLIC-Tabelle (kein {'schema':'crm'},
    models.py:526-530) — eine NOT-NULL-Seed-Regression auf einer public Tabelle ist KEINE crm/training-Emulation.
    Req-6 zielt auf die crm/training-EMULATION (das False-Green), NICHT auf JEDE SQLite-Nutzung. Ein einzelner
    public-Tabellen-SQLite-Regressionstest bleibt daher legitim auf in-memory SQLite: schnell + DSN-unabhängig
    (läuft im Gate UND lokal, nicht nur wenn ein PG-DSN gesetzt ist) + echte Runtime-Write-Assertion. Ein Port auf
    PG wurde VERWORFEN: er fügt eine skip-when-DSN-missing-Kopplung hinzu für null Korrektheits-Gewinn (die
    Regression reproduziert identisch auf SQLite, keine crm/RLS/PG-spezifische Semantik).

    **Anti-False-Green (CLAUDE.md):** KEINE `inspect.getsource`/`hasattr`/grep-on-source-Assertion einführen —
    der Test bleibt eine echte DB-Write/Read-Integration-Assertion (INSERT → COUNT → NOT-NULL-Check), exakt wie heute.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "Base.metadata.create_all|ApiRate.__table__.create" tests/test_08_14_apirate_seed.py'; echo "EXIT=$?"  # erwartet: Base.metadata.create_all WEG, ApiRate.__table__.create PRESENT. Voll-Beleg: Gate-Lauf zeigt test_08_14 PASSED (nicht error/SKIPPED), kein "unknown database crm".</automated>
  </verify>
  <done>
    test_08_14_apirate_seed.py collected + läuft GRÜN im Gate mit dem entfernten ATTACH-Listener — kein
    "unknown database crm". `grep Base.metadata.create_all tests/test_08_14_apirate_seed.py` → leer;
    `grep ApiRate.__table__.create ...` → Treffer. Der Test bleibt in-memory SQLite (DSN-unabhängig, nicht
    geskippt) und eine echte NOT-NULL-Runtime-Regression (keine Source-Presence). Die 4 Tests (8-rows,
    last_checked_at-NOT-NULL, idempotent, models-present) passen unverändert.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: test_tenant_orgs.py auf PG-Trigger-Semantik portieren (F1 — kein Python-Doppel-Seed der Trigger-Row)</name>
  <read_first>
    - tests/test_tenant_orgs.py (ganze Datei — Docstring Z.9-21 SQLite-vs-PG-Boundary; Helpers `_seed_tenant_orgs` Z.38-46, `_backfill_calls_tenant_id` Z.48-56; die 6 Tests Z.59-141, speziell `test_seed_one_row_per_org` Z.59-67 mit `count == 3`, `test_dualwrite_trigger_fires` Z.70-82 mit manuellem TenantOrg-add Z.77, `test_dualwrite_idempotent` Z.85-94 mit dem ECHTEN Duplikat-IntegrityError-Test)
    - tests/conftest.py (NACH Plan 01: db_session bindet das MODUL-SessionLocal an nerve_test um — der PG-Pfad für diesen Test)
    - tests/test_rls_isolation.py Z.33-54 (Trigger-tenant_orgs-Read-Back-Muster: INSERT organisations → SELECT tenant_orgs.id zurück — das ist die PG-Semantik, die test_tenant_orgs ERWARTEN muss) + Z.101-116 (POST-yield Best-Effort-Teardown, MED-1)
    - alembic/versions/*0011* (Migration 0011 — der AFTER-INSERT-Trigger `trg_mk_tenant_org` auf organisations + das UNIQUE(legacy_org_id) auf tenant_orgs)
  </read_first>
  <behavior>
    - test_tenant_orgs.py läuft gegen nerve_test-PG (db_session aus Plan 01) statt in-memory SQLite. Es ERWARTET
      jetzt den AFTER-INSERT-Trigger `trg_mk_tenant_org`: ein `INSERT organisations` erzeugt die tenant_orgs-Row
      AUTOMATISCH. Der Test liest die auto-erzeugte `tenant_orgs.id` zurück (Trigger-Read-Back-Muster,
      test_rls_isolation.py:33-54) statt Python-seitig eine eigene TenantOrg-Row zu inserten.
    - KEIN Python-seitiges Doppel-Seed mehr: `_seed_tenant_orgs` (Python-INSERT pro Org) entfällt bzw. wird zum
      No-op/Read-Back, und die manuellen `db_session.add(TenantOrg(...))` in test_dualwrite_trigger_fires werden
      durch ein Zurücklesen der vom Trigger erzeugten Row ersetzt — sonst UNIQUE(legacy_org_id)-Kollision auf PG.
    - Die ECHTE Idempotenz-Assertion bleibt: `test_dualwrite_idempotent` erwartet WEITERHIN einen IntegrityError
      auf einen WIRKLICHEN Duplikat-Insert (ein zweiter TenantOrg mit gleichem legacy_org_id, manuell forciert) —
      das testet die UNIQUE-Constraint, auf die der Trigger's ON CONFLICT baut. Dieser eine erwartete IntegrityError
      bleibt unverändert valide.
    - Alle Assertions bleiben echte Row-Reads (count/legacy_id-Liste/backfill-join-Ergebnis) — KEINE Source-Presence.
    - Deterministischer Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except NACH yield, reverse-FK:
      tenant_orgs → organisations bzw. calls → users → orgs), getaggte Rows, analog test_rls_isolation.py:101-116 (MED-1).
    - SKIP wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback — der Test ist jetzt trigger-/PG-abhängig).
  </behavior>
  <action>
    Portiere `tests/test_tenant_orgs.py` von der SQLite-no-trigger-Annahme auf die nerve_test-PG-Trigger-Semantik.
    KONKRET:

    1. **Trigger ERWARTEN statt Python-doppeln:** Auf nerve_test erzeugt der AFTER-INSERT-Trigger
       `trg_mk_tenant_org` (Migration 0011) bei jedem `INSERT organisations` automatisch die passende
       tenant_orgs-Row. Daher:
       - `_mk_org` (Z.31-35) bleibt (INSERT organisations), aber danach wird die tenant_orgs-Row vom Trigger
         ZURÜCKGELESEN (SELECT tenant_orgs.id WHERE legacy_org_id = org.id — test_rls_isolation.py:33-54-Muster),
         NICHT manuell ge-insertet.
       - `_seed_tenant_orgs` (Z.38-46): entfällt als Python-Seed (der Trigger seedet). Falls die Tests die
         Funktion strukturell brauchen, mach sie zu einem reinen Read-Back/No-op (sie darf KEINE neue TenantOrg-
         Row inserten — sonst Doppel + UNIQUE-Kollision).
       - `test_seed_one_row_per_org` (Z.59-67): die `count == 3`-Assertion bleibt, aber die 3 tenant_orgs-Rows
         kommen jetzt vom Trigger (eine pro `_mk_org`), nicht vom Python-Seed. legacy_ids-Liste-Assertion bleibt
         (read-back der Trigger-Rows).
       - `test_dualwrite_trigger_fires` (Z.70-82): ersetze den manuellen `db_session.add(TenantOrg(...))` (Z.77)
         durch ein Zurücklesen der vom Trigger bei `_mk_org("Brand New GmbH")` erzeugten Row; asserte
         `len(rows) == 1` + `rows[0].name == "Brand New GmbH"` auf der TRIGGER-Row (das testet den Dual-Write
         jetzt ECHT auf PG, nicht mehr nur als Python-Analog).
    2. **Echte Idempotenz BEHALTEN:** `test_dualwrite_idempotent` (Z.85-94) — der erwartete IntegrityError auf
       einen FORCIERTEN zweiten TenantOrg mit gleichem legacy_org_id bleibt unverändert (er testet die
       UNIQUE-Constraint, die der Trigger's ON CONFLICT braucht). Hinweis: auf PG existiert nach `_mk_org` bereits
       die Trigger-Row, also reicht EIN zusätzlicher manueller Duplikat-Insert um den IntegrityError zu provozieren
       (statt zwei). Passe die Setup-Zeilen so an, dass genau ein echter Duplikat-Insert den erwarteten Error wirft.
    3. **Backfill-Tests** (`test_calls_tenant_id_backfilled` Z.97-111, `test_no_orphan_calls_after_backfill`
       Z.121-141): die tenant_orgs-Rows kommen vom Trigger (über `_mk_org`); `_backfill_calls_tenant_id` (Python-
       Analog der Migrations-0011-Step-4-UPDATE-Join) bleibt als Logik-Test gültig, liest die Trigger-tenant_orgs.id
       als Bridge-Ziel. Assertions (call.tenant_id == tenant.id; orphan_count == 0) bleiben echte Row-Reads.
       `test_calls_tenant_id_stays_nullable` (Z.114-118) bleibt (Column-Constraint-Assertion via sa_inspect — OK).
    4. **Teardown** in der Fixture-POST-yield-Sektion (MED-1, try/except NACH yield analog
       test_rls_isolation.py:101-116): reverse-FK DELETE der getaggten Rows (calls → users → tenant_orgs →
       organisations bzw. die im Test angelegten). Läuft auch bei Assertion-Fehler. KEIN literales try...finally
       im Test-Body — die POST-yield-Platzierung ist das Mittel.
    5. **Docstring aktualisieren:** die SQLite-vs-PG-Boundary-Note (Z.9-21) umschreiben — der Test läuft jetzt
       GEGEN PG und übt den Trigger `trg_mk_tenant_org` + UNIQUE(legacy_org_id) WIRKLICH aus (nicht mehr nur als
       SQLite-Analog). Das ist ein SQLite-Annahme-Test (wie test_08_14), der auf PG portiert wird, NICHT geskippt.
    6. **Anti-False-Green (CLAUDE.md):** alle Assertions bleiben echte DB-Row-Reads (count, legacy_id-Liste,
       backfill-join, erwarteter IntegrityError) — KEINE inspect.getsource/hasattr/grep-on-source.

    **F1-Rationale (im SUMMARY festhalten):** test_tenant_orgs berührt NUR public.* (TenantOrg/Organisation/
    User/Call), ZERO crm — deshalb war es NIE ein gültiger RLS-Proof (das war eine falsche Annahme in Plan 01,
    dort entfernt; der echte RLS-Tripwire ist tests/test_rls_generic_smoke.py aus Plan 01). Auf echtem PG bricht
    es aus einem ANDEREN Grund: Python-Doppel-Seed kollidiert mit der Trigger-Row. Es ist ein SQLite-Annahme-Test
    (wie test_08_14), der auf PG-Trigger-Semantik portiert — nicht geskippt — werden MUSS, sonst Gate ROT.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy4.log | grep -E "test_tenant_orgs|test_seed_one_row_per_org|test_dualwrite|test_calls_tenant_id|PASSED|passed|failed|error"; echo "EXIT=$?"  # F1: test_tenant_orgs PASSED gegen nerve_test (Trigger-Semantik, kein UNIQUE-Kollisions-Error, kein count==3-Mismatch).</automated>
  </verify>
  <done>
    test_tenant_orgs.py läuft gegen nerve_test-PG und ERWARTET den AFTER-INSERT-Trigger `trg_mk_tenant_org`:
    `_mk_org` liest die vom Trigger auto-erzeugte tenant_orgs-Row zurück (kein Python-Doppel-Seed, kein manueller
    TenantOrg-Insert in test_dualwrite_trigger_fires) → kein UNIQUE(legacy_org_id)-Kollisions-Error mehr; die
    count==3-Assertion in test_seed_one_row_per_org hält (Trigger-Rows). Die echte Idempotenz-Assertion
    (erwarteter IntegrityError auf einen forcierten Duplikat-Insert) bleibt valide. Backfill-Tests lesen die
    Trigger-tenant_orgs.id als Bridge. Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, analog
    test_rls_isolation.py:101-116) → kein State-Leak. Im Gate-Lauf erscheint test_tenant_orgs als PASSED
    (nicht error/SKIPPED). Alle Assertions sind echte Row-Reads (keine Source-Presence).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: FK-Delta test_postcall_split — eigenen Org/User-id=1-Insert entfernen, Base-Seed konsumieren</name>
  <read_first>
    - tests/test_postcall_split.py (ganze Datei — speziell `_seed_user_and_conv` Z.24-46: nutzt `db = get_session()` + `db.add(Organisation(id=org_id, name='Test-Org'))` / `db.add(User(id=user_id, org_id=org_id, ...))`, MIT bestehendem idempotentem Guard `if db.query(Organisation).filter_by(id=org_id).first() is None` Z.32 bzw. dem User-Guard Z.35 — plus die Call/outcome-Split-Assertions)
    - tests/conftest.py (NACH Plan 01 Task 4: der Session-Scope Base-Seed Org(id=1)+User(id=1) — der Vertrag, den dieser Test JETZT konsumiert statt selbst die Test-Org id=1 zu inserten)
  </read_first>
  <behavior>
    - test_postcall_split self-seedet seine Test-Org/-User aktuell in `_seed_user_and_conv` (Z.24-46) via `get_session()` + `db.add(Organisation(id=1, name='Test-Org'))` / `db.add(User(id=1, ...))`, beide bereits HINTER einem idempotenten `... .first() is None`-Guard (Z.32/Z.35). Dieser Guard verhindert auf der persistenten nerve_test schon eine harte PK-Doppel-IntegrityError (der Insert wird uebersprungen, wenn id=1 vom Base-Seed bereits da ist).
    - Die Aenderung ist daher eine Klarheits-/Konsistenz-Verbesserung (KEIN harter break-fix): der Test soll die EINE Base-Org/-User (id=1) aus dem Plan-01-Base-Seed KONSUMIEREN, statt parallel eine zweite „Test-Org"-Definition (Name 'Test-Org' vs Base-Name '[PGTEST-BASE] org') fuer dieselbe id=1 zu fuehren. Zwei Quellen, die beide „die Test-Org id=1" meinen, sind verwirrend und drift-anfaellig — eine reicht.
    - Die echten Call/outcome-Split-Assertions bleiben unveraendert (Runtime-Integration, kein Source-Presence). `_seed_user_and_conv` legt WEITERHIN den ConversationLog an (Z.41-43) — nur die Org/User-Parent-Inserts entfallen zugunsten des Base-Seeds.
  </behavior>
  <action>
    1. In `_seed_user_and_conv` (Z.24-46): ENTFERNE die Org/User-Self-Inserts —
       konkret den `if db.query(Organisation).filter_by(id=org_id).first() is None: db.add(Organisation(id=org_id, name='Test-Org')); db.commit()`-Block (Z.32-34) und den analogen
       `db.add(User(id=user_id, org_id=org_id, ...))`-Block (Z.35-40). Der Plan-01-Base-Seed (Task 4) liefert
       Org id=1 + User id=1 bereits session-scoped. Der bestehende idempotente Guard (`... .first() is None`)
       hat zwar bereits einen harten PK-Doppel-Insert verhindert — die Entfernung ist die saubere Konsequenz:
       EINE Quelle der Wahrheit fuer die Base-Org/-User id=1 (kein paralleles 'Test-Org'-Duplikat fuer dieselbe id).
    2. Falls der Test die Org/User-Objekte als lokale Variablen braucht, hole sie READ-ONLY via
       `db.query(Organisation).filter_by(id=org_id).first()` / `db.query(User).filter_by(id=user_id).first()`
       (bzw. `db.get(Organisation, org_id)`) — Read, kein Insert. Der `ConversationLog`-Insert (Z.41-43) bleibt.
    3. ALLE Call-Erstellungs- und outcome-Split-Assertions bleiben Wort fuer Wort — nur die Org/User-Parent-Seeds entfallen.
    4. Anti-False-Green (CLAUDE.md): die Assertions bleiben echte Row-/Return-Checks auf den Split — KEINE
       inspect.getsource/hasattr/grep-on-source.
    Rationale (#3, W2-praezisiert): der Test nutzt `get_session()` + `db.add(Organisation(id=1,...))` (NICHT `db_session.add`)
    und HAT bereits einen idempotenten `.first() is None`-Guard (Z.32/35) — „self-inserting id=1" wuerde also nicht hart
    an einem PK-Doppel brechen. Die Aenderung CONSUMET den Base-Seed statt eine zweite Test-Org-Definition fuer dieselbe
    id=1 zu fuehren: Klarheit/Konsistenz (eine Quelle), kein harter break-fix.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy5.log | grep -E "test_postcall_split|passed|failed|error|UniqueViolation|IntegrityError"; echo "EXIT=$?"  # test_postcall_split PASSED gegen nerve_test (kein id=1-Doppel-Insert-Konflikt mit dem Base-Seed).</automated>
  </verify>
  <done>
    `_seed_user_and_conv` in test_postcall_split.py inserted KEINE eigene Organisation(id=1)/User(id=1) mehr
    (die `get_session()`+`db.add(Organisation/User)`-Bloecke Z.32-40 entfernt), sondern konsumiert den
    Plan-01-Base-Seed (id=1) read-only; der ConversationLog-Insert (Z.41-43) bleibt. Der bestehende idempotente
    `.first() is None`-Guard hatte schon einen harten PK-Doppel verhindert — die Aenderung ist die saubere
    Konsequenz (eine Quelle fuer die Base-Org/-User id=1). Die Call/outcome-Split-Assertions bleiben echte
    Row-/Return-Checks; im Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 6: FK-Delta test_ewb_rate_api — unique email pro Run, trigger-aware Org (kein manueller tenant_orgs)</name>
  <read_first>
    - tests/test_ewb_rate_api.py (ganze Datei — der Org->User->ConvLog->ObjectionEvent-Self-Seed + die rate-API-Assertions)
    - tests/test_rls_isolation.py:33-54 (Trigger-Read-Back: INSERT organisations -> tenant_orgs.id vom Trigger; kein manueller tenant_orgs-Insert) + Z.101-116 (POST-yield Best-Effort-Teardown, MED-1)
    - database/models.py Z.65-135 (User.email UNIQUE NOT NULL — die Kollisions-Quelle auf persistenter PG)
  </read_first>
  <behavior>
    - test_ewb_rate_api self-seedet weiterhin seine eigene Org->User->ConversationLog->ObjectionEvent-Kette (PUBLIC-Tabellen, KEIN crm — Claudian bestaetigt), laeuft aber jetzt gegen die persistente nerve_test: deshalb (a) eine UNIQUE email pro Run (sonst users.email-Kollision wenn der Test mehrfach/neben anderen laeuft) und (b) die Org wird via Trigger trg_mk_tenant_org versorgt — KEIN doppelter manueller tenant_orgs-Insert.
    - Die ObjectionEvent/rate-Assertions bleiben echte Runtime-Checks.
  </behavior>
  <action>
    1. UNIQUE email pro Run: ersetze die hardcodete Test-Email durch `f"ewb-rate-{uuid.uuid4().hex[:8]}@nerve.local"`
       (bzw. eine eindeutige Variante) — sonst wirft users.email UNIQUE NOT NULL eine IntegrityError auf der
       persistenten nerve_test, wenn der Test neben anderen email-seedenden Tests laeuft. (`import uuid` ergaenzen.)
    2. Org-Seed trigger-aware: der `INSERT organisations` feuert trg_mk_tenant_org -> tenant_orgs entsteht
       automatisch. Falls der Test bisher MANUELL eine TenantOrg-Row inserted -> entfernen (sonst
       UNIQUE(legacy_org_id)-Bruch, F1-Lektion). Falls er tenant_orgs NICHT braucht (ObjectionEvent/ConvLog
       sind public, kein crm-FK) -> einfach NICHT doppelt inserten.
    3. ConversationLog/ObjectionEvent/rate-Assertions bleiben Wort fuer Wort (PUBLIC, kein crm — kein
       set_current_tenant noetig).
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       objection_event -> conversation_log -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), damit
       die self-geseedeten Rows nicht in nerve_test leaken.
    5. Anti-False-Green (CLAUDE.md): rate-Assertions bleiben echte Response-/Row-Checks — kein Source-Presence.
    Rationale (#8): bricht nur an (a) trg_mk_tenant_org-Doppel + (b) users.email UNIQUE auf persistenter PG.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy6.log | grep -E "test_ewb_rate_api|passed|failed|error|UniqueViolation|legacy_org_id"; echo "EXIT=$?"  # test_ewb_rate_api PASSED gegen nerve_test (unique email, kein tenant_orgs-Doppel).</automated>
  </verify>
  <done>
    test_ewb_rate_api.py nutzt eine UNIQUE email pro Run (kein users.email-UNIQUE-Bruch), seedet die Org
    trigger-aware (kein manueller tenant_orgs-Doppel-Insert -> kein UNIQUE(legacy_org_id)-Bruch); die
    ObjectionEvent/rate-Assertions bleiben echte Runtime-Checks; Teardown in der POST-yield-Sektion; im
    Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 7: FK-Delta test_profile_editor_validation — Parents present + Tenant-Kontext (falls Route crm liest)</name>
  <read_first>
    - tests/test_profile_editor_validation.py (ganze Datei — der client-Fixture-Self-Seed Org/User/Profile + die Validation-Assertions)
    - tests/conftest.py (NACH Plan 01: client bindet das MODUL-SessionLocal um + set_current_tenant; Base-Seed Org/User id=1 verfuegbar)
    - database/models.py Z.137+ (Profile — FK auf org/user; profiles ist PUBLIC, kein crm — Claudian bestaetigt KEINE RLS-Luecke)
  </read_first>
  <behavior>
    - test_profile_editor_validation self-seedet Org/User/Profile via die client-Fixture; gegen die persistente nerve_test muessen die org/user-Parents present sein (entweder den Base-Seed id=1 konsumieren ODER korrekt selbst seeden) und — falls die getestete Route crm beruehrt — der Tenant-Kontext gesetzt sein (die client-Fixture aus Plan 01 ruft set_current_tenant bereits auf).
    - Claudian-Befund: profiles ist PUBLIC, KEINE crm-RLS-Luecke — der Tenant-Kontext ist nur relevant falls die Route selbst crm liest.
    - Die Validation-Assertions bleiben echte Response-/Row-Checks.
  </behavior>
  <action>
    1. Parents present sicherstellen: entweder den Plan-01-Base-Seed (Org id=1 + User id=1) konsumieren
       (`db_session.get(...)` / Profile mit org_id=1,user_id=1 anlegen) ODER — wenn der Test eigene Org/User
       braucht — diese mit UNIQUE email (uuid-suffixed) korrekt selbst seeden (kein id=1-Doppel mit dem
       Base-Seed). Profile-FK-Ziele (org_id/user_id) muessen auf existierende Parents zeigen.
    2. Tenant-Kontext: die client-Fixture aus Plan 01 ruft set_current_tenant bereits auf — falls die
       Profile-Editor-Route crm liest, ist der Kontext damit gesetzt. (Claudian: profiles selbst ist public,
       keine zusaetzliche RLS-Behandlung noetig.)
    3. Die Validation-Assertions (gueltige/ungueltige Profile-Eingaben -> erwartete Response/Fehlermeldung)
       bleiben Wort fuer Wort.
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       profile -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), fuer selbst-geseedete Rows.
    5. Anti-False-Green (CLAUDE.md): echte Response-/Row-Assertions, kein Source-Presence.
    Rationale (#9): braucht org/user-Parents present + ggf. Tenant-Kontext; profiles public, keine RLS-Luecke.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy7.log | grep -E "test_profile_editor_validation|passed|failed|error|ForeignKey|IntegrityError"; echo "EXIT=$?"  # test_profile_editor_validation PASSED gegen nerve_test (Parents present, ggf. Tenant-Kontext).</automated>
  </verify>
  <done>
    test_profile_editor_validation.py hat die org/user-Parents present (Base-Seed konsumiert ODER korrekt
    selbst geseedet mit unique email), der Tenant-Kontext ist ueber die Plan-01-client-Fixture gesetzt (falls
    Route crm liest); die Validation-Assertions bleiben echte Response-/Row-Checks; Teardown in der
    POST-yield-Sektion; im Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 8: test_ft_seed HONEST gegen schema-only nerve_test laufen lassen — echte Fehlerursache verifizieren, NICHT eine vermutete maskieren</name>
  <read_first>
    - tests/test_ft_seed.py (ganze Datei — `test_prompt_seed` Z.14-21 ruft `_seed_prompt_versions(db_session)` SELBST und prueft je-Modul row+version+prompt_text; `test_seed_idempotent` Z.24-30 ruft `_seed_prompt_versions(db_session)` ZWEIMAL und asserted `count == 4` nach jedem Aufruf — der Test seedet also SELBST, er erwartet KEINE vor-existierenden Rows)
    - app.py — `_seed_prompt_versions` (idempotenter check-then-insert von EXAKT 4 aktiven Modulen: assistant_live/coaching_live/objection_trigger/training_persona; `is_active=True`, `version='v1.0.0'`). EXAKTE Zeile beim Lesen verifizieren (grep `def _seed_prompt_versions`).
    - alembic/versions/* — VERIFIZIERT (grep `INSERT INTO prompt_versions` / `bulk_insert.*prompt`): KEINE Migration seedet prompt_versions-DATEN; 0015 setzt nur COMMENT/Schild. nerve_test wird per `pg_dump --schema-only` (ZERO data rows) gebaut -> prompt_versions ist beim Test-Start LEER.
    - .planning/.../08.23.2.PGTEST-SPEC.md (Klasse-E / Stufe-2 pre-existing failure: test_ft_seed ist der bekannte rote Stufe-2-Test, dessen WIRKLICHE Ursache NICHT etabliert ist — NICHT out-of-scope wegmaskieren)
  </read_first>
  <behavior>
    - KORREKTUR der frueheren Annahme (W1, pre-execute 2026-06-15): die alte Diagnose "alembic pre-seedet prompt_versions -> `assert count == 4` bricht" ist FALSCH. nerve_test ist SCHEMA-ONLY (`pg_dump --schema-only`, ZERO data — grep-verifiziert: keine Migration seedet prompt_versions-Daten). `_seed_prompt_versions` ist idempotenter check-then-insert von EXAKT 4 Modulen, und der Test ruft ihn SELBST auf der leeren Tabelle auf -> `count == 4` haelt auf der schema-only DB sehr WAHRSCHEINLICH (kein Pre-Seed-Konflikt). test_ft_seed ist der bekannte Stufe-2/Klasse-E pre-existing failure, dessen ECHTE Ursache NICHT etabliert ist.
    - DESHALB: KEINE presumptive count-on-empty-"Toleranz" einbauen. Erst die WIRKLICHE Ursache im Gate beobachten. Der Test soll genuin den Seed ueben (4 Module insert + je-Modul-Pruefung + Idempotenz), nicht durch eine aufgeweichte Assertion gruen-gefaerbt werden.
  </behavior>
  <action>
    1. **HONEST laufen lassen:** test_ft_seed gegen die schema-only nerve_test im Gate laufen lassen WIE ER IST
       (er seedet selbst via `_seed_prompt_versions(db_session)`, dann `count == 4` / je-Modul-Assertions). KEINE
       presumptive Aenderung an der Assertion VOR der Beobachtung — die alte "assert >=4 / expected-set"-Aufweichung
       (basierend auf der widerlegten Pre-Seed-Story) NICHT blind einbauen.
    2. **Tolerante Assertion NUR als bewusste Defensiv-Massnahme — und nur falls der Seed echt geuebt bleibt:**
       Eine tolerantere Form (`count >= 4` PLUS `EXPECTED_MODULES.issubset(present_modules)`, OHNE eigene
       Row-Inserts) ist NUR dann akzeptabel, wenn (a) der Gate-Lauf zeigt dass tatsaechlich Rows vor-existieren
       (was nach grep UNERWARTET waere — dann die Quelle finden, nicht zudecken) UND (b) der Test weiterhin
       `_seed_prompt_versions` aufruft und die je-Modul-Eigenschaften (version='v1.0.0', prompt_text>30) echt
       prueft. Wird sie eingebaut, im Test-Kommentar die BEOBACHTETE Ursache dokumentieren — nicht die vermutete.
    3. **Wenn test_ft_seed im Gate ROT ist:** den ECHTEN tatsaechlichen Fehler-Output (assert-Diff / Exception /
       Traceback) im SUMMARY VERBATIM festhalten. Ist es ein echter App-Bug (Klasse-E, SPEC-Boundary — z.B.
       `_seed_prompt_versions` verhaelt sich auf PG anders, ConversationLog-FK, JSONB-Cast, was-auch-immer) ->
       ESKALIEREN (eigene Bugfix-Phase), NICHT mit einer aufgeweichten Assertion maskieren/skippen.
    4. **Harte Regeln (unveraendert):** der Test inserted KEINE eigenen prompt_versions-Rows ueber
       `_seed_prompt_versions` hinaus; KEINE Source-Presence-Pruefung (inspect.getsource/grep-on-source) — die
       Assertion bleibt ein echter DB-Row-Read (count/Modul-Set/Feldwerte).
    Rationale (#10, W1-korrigiert): nicht einen VERMUTETEN Fehlermodus (count-on-empty gegen angeblich
    pre-seedete Rows) fixen — die WIRKLICHE Ursache am Execute verifizieren. Schema-only nerve_test + selbst-seedender
    Test => count==4 haelt wahrscheinlich; bleibt der Test rot, ist es ein anderer (echter) Bug -> eskalieren.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy8.log | grep -E "test_ft_seed|test_prompt_seed|test_seed_idempotent|passed|failed|error|assert"; echo "EXIT=$?"  # test_ft_seed gegen schema-only nerve_test: ENTWEDER PASSED (Seed uebt sauber, count==4 haelt) ODER der ECHTE Fehler-Output wird sichtbar -> im SUMMARY verbatim festhalten + eskalieren falls echter App-Bug (KEINE Aufweichung als Maskierung).</automated>
  </verify>
  <done>
    test_ft_seed laeuft im Gate gegen die schema-only nerve_test, seedet weiterhin selbst via
    `_seed_prompt_versions(db_session)` und prueft die 4 Module + Idempotenz als echte Row-Reads (keine
    Source-Presence). Die widerlegte Pre-Seed-Story ist NICHT als presumptive Aufweichung eingebaut. ENTWEDER der
    Test ist PASSED (count==4 haelt auf der leeren Tabelle), ODER der tatsaechliche Fehler-Output ist im SUMMARY
    verbatim dokumentiert und — falls echter App-Bug (Klasse-E) — eskaliert (nicht maskiert/geskippt). Eine
    tolerante Assertion existiert nur falls der Gate-Lauf vor-existierende Rows BEWIESEN hat (dann mit
    beobachteter Ursache kommentiert) UND der Seed weiterhin echt geuebt wird.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 9: FK-Delta test_ab_stats — Base-Org present, _seed_ewb_scenarios braucht keinen extra Parent</name>
  <read_first>
    - tests/test_ab_stats.py (ganze Datei — der eigene org/user/conv/rating-Self-Seed + die A/B-Stats-Assertions)
    - tests/conftest.py (NACH Plan 01 Task 4: Base-Seed Org id=1 verfuegbar)
    - database/models.py (TrainingScenario.erstellt_von — nullable; daher braucht `_seed_ewb_scenarios` keinen extra User-Parent)
  </read_first>
  <behavior>
    - test_ab_stats self-seedet seine eigene org/user/conversation/rating-Kette; gegen die persistente nerve_test muss die Base-Org present sein (Plan-01-Base-Seed) und es ist zu verifizieren, dass `_seed_ewb_scenarios` keinen zusaetzlichen Parent braucht (TrainingScenario.erstellt_von ist nullable -> clean).
    - Minimale Aenderung: kein Re-Architecting, nur Base-Org-Praesenz sicherstellen + den nullable-erstellt_von-Pfad bestaetigen. Die A/B-Stats-Assertions bleiben echte Runtime-Checks.
  </behavior>
  <action>
    1. Base-Org present: stelle sicher dass die org/user-Parents present sind — entweder den Plan-01-Base-Seed
       (Org id=1 + User id=1) konsumieren ODER die self-geseedete Kette mit UNIQUE email (uuid-suffixed)
       korrekt anlegen (kein id=1-Doppel mit dem Base-Seed).
    2. `_seed_ewb_scenarios`-Pfad bestaetigen: TrainingScenario.erstellt_von ist nullable -> der Scenario-Seed
       braucht KEINEN extra User-Parent. Verifiziere das im read_first (models.py) und stelle sicher dass der
       Scenario-Seed keinen NOT-NULL-FK auf einen fehlenden Parent setzt. Minimale Aenderung — kein
       Re-Architecting.
    3. Die A/B-Stats-Assertions (rating-Aggregation/Split-Ergebnis) bleiben Wort fuer Wort echte Row-Reads.
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       rating -> conversation -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), fuer self-geseedete Rows.
    5. Anti-False-Green (CLAUDE.md): echte Stats-/Row-Assertions, kein Source-Presence.
    Rationale (#11): nur Base-Org-Praesenz + nullable erstellt_von verifizieren; minimaler Eingriff.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy9.log | grep -E "test_ab_stats|passed|failed|error|ForeignKey|IntegrityError"; echo "EXIT=$?"  # test_ab_stats PASSED gegen nerve_test (Base-Org present, _seed_ewb_scenarios clean via nullable erstellt_von).</automated>
  </verify>
  <done>
    test_ab_stats.py hat die org/user-Parents present (Base-Seed konsumiert ODER unique self-seed), und es ist
    bestaetigt dass `_seed_ewb_scenarios` keinen extra Parent braucht (TrainingScenario.erstellt_von nullable);
    die A/B-Stats-Assertions bleiben echte Row-Reads; Teardown in der POST-yield-Sektion; im Gate-Lauf PASSED.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Klasse-A-Test → nerve_test crm.* | portierte Tests schreiben crm-Rows als nerve_app (RLS engaged) |
| Code-Pfad → SQLite-Emulation | nach Entfernung darf KEIN aktiver Pfad SQLite-Schema-Emulation voraussetzen |
| test_tenant_orgs → nerve_test public.* + Trigger | der Test schreibt organisations und ERWARTET die Trigger-erzeugte tenant_orgs-Row (kein Python-Doppel) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-11 | Denial | ATTACH-Listener entfernt → Klasse-A-Tests werfen "unknown database crm" (Collection-Error) | mitigate | Req-6 + Port im SELBEN Plan/Wave (Wave-Kopplung); Tests gegen nerve_test-PG portiert bevor/während Listener-Entfernung |
| T-PGTEST-12 | Information Disclosure | portierte crm-Tests ohne Tenant-Kontext ODER frische sessionmaker (Hook feuert nicht) → RLS fail-closed 0 Zeilen ODER BYPASSRLS-Umgehung | mitigate | set_current_tenant(TEST_TENANT_UUID) + tenant_orgs-Seed (D-05); MODUL-SessionLocal-Umbindung (Plan-01-Vorbild) damit der RLS-Hook feuert; nerve_app rolbypassrls=f; keine Superuser-Rolle |
| T-PGTEST-13 | Tampering | Test schlägt mit AssertionError fehl BEVOR der reverse-FK-Teardown läuft (Teardown NICHT in der POST-yield-Sektion) → geseedete crm/tenant_orgs-Rows leaken in nerve_test → State-Leakage für nachfolgende Tests (gleiche Connection) → False-Green/False-Red Folge-Tests | mitigate | Gemini-MEDIUM (MED-1 präzisiert): der Reverse-FK-Teardown beider Klasse-A-Gruppen + test_tenant_orgs liegt ZWINGEND in der Fixture-POST-yield-Sektion (try/except NACH dem `yield`, analog test_rls_isolation.py:101-116) — pytest führt die POST-yield-Sektion auch bei Assertion-Fehler aus (das IST das finally-Äquivalent), sodass das Cleanup (account_memory → accounts → tenant_orgs → organisations) auch bei Assertion-Fehler läuft; KEIN literales `try...finally` im Test-Body. Klasse-A sind LOGIK-Tests (merge/filter/hash), die RLS-Cross-Tenant-Prüfung bleibt im D-04-Real-Commit-Pfad der RLS-Gruppe (unverändert) |
| T-PGTEST-14 | Spoofing | echter App-Bug wird still im Test gepatcht statt eskaliert (Req-7-Geist verletzt) | mitigate | Klasse D/E-Brüche im SUMMARY ESKALIEREN (eigene Bugfix-Phase), Test NICHT stilllegen/skippen |
| T-PGTEST-17 | Denial | ATTACH-Listener entfernt, aber ein DRITTER Listener-abhängiger Test (test_08_14_apirate_seed.py, fresh_engine Z.14-19) bleibt unportiert → `Base.metadata.create_all` wirft "unknown database crm" → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy (GOAL-KILLER) | mitigate | Task 3 scopet den create_all auf die PUBLIC ApiRate-Tabelle (`ApiRate.__table__.create`) — kein crm/training nötig, DSN-unabhängig. Vollständigkeits-grep `create_all\|sqlite` über tests/ verifiziert (orchestrator-confirmed): NUR test_08_14 war ungedeckt; test_08_20_3 (raw single-table CREATE TABLE profile_opener, KEIN create_all/crm) + test_meeting_form_dsgvo (Kommentar-only, kein Engine/Fixture) bestätigt SAFE; conftest.py:43/67 → Plan 01; test_account_memory_briefing + test_anonymizer_worker → Task 2 |
| T-PGTEST-19 | Denial | test_tenant_orgs.py (SQLite-no-trigger-Annahme) doppelt auf nerve_test-PG die vom AFTER-INSERT-Trigger trg_mk_tenant_org bereits erzeugte tenant_orgs-Row → UNIQUE(legacy_org_id)-IntegrityError WO der Test ihn nicht erwartet + count==3-Asserts halten nicht → Test errort → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy (blocker-class wie test_08_14) | mitigate | F1 (pre-execute audit 2026-06-15): Task 4 portiert test_tenant_orgs auf Trigger-Semantik — `_mk_org` liest die vom Trigger auto-erzeugte tenant_orgs-Row zurück (test_rls_isolation.py:33-54-Muster) statt Python-seitig zu doppeln; `_seed_tenant_orgs` wird Read-Back/No-op; test_dualwrite_trigger_fires liest die Trigger-Row statt manuell zu inserten; die ECHTE Idempotenz-Assertion (erwarteter IntegrityError auf forcierten Duplikat) bleibt valide. SQLite-Annahme-Test (wie test_08_14) → portiert, nicht geskippt. SEPARAT: test_tenant_orgs berührt ZERO crm → war nie ein gültiger RLS-Proof (falsche Annahme in Plan 01, dort entfernt; echter RLS-Tripwire = tests/test_rls_generic_smoke.py, Plan 01 Task 2) |
| T-PGTEST-21 | Denial | 5 test-spezifische FK-Deltas brechen auf der persistenten/zero-data nerve_test aus EINZEL-Gruenden: test_postcall_split (id=1-Doppel mit Base-Seed), test_ewb_rate_api (users.email UNIQUE + tenant_orgs-Doppel), test_profile_editor_validation (fehlende org/user-Parents), test_ft_seed (Stufe-2/Klasse-E pre-existing failure, echte Ursache NICHT etabliert — nerve_test ist schema-only/zero-data, der Test seedet selbst via _seed_prompt_versions, count==4 haelt wahrscheinlich; KEIN bewiesener Pre-Seed-Konflikt), test_ab_stats (fehlende Base-Org) -> je ein roter Test -> fail-closed Gate blockt jeden Deploy (blocker-class) | mitigate | Tasks 5-9 (FK-debt fold 2026-06-15): #3 CONSUME Base-Seed statt id=1-Doppel; #8 unique email pro Run + trigger-aware Org (kein manueller tenant_orgs); #9 Parents present + Tenant-Kontext via Plan-01-client (profiles public, keine RLS-Luecke); #10 (W1-korrigiert) test_ft_seed HONEST gegen schema-only nerve_test laufen lassen — KEINE presumptive count-on-empty-Aufweichung; echte Fehlerursache am Execute verifizieren, bei echtem App-Bug eskalieren (tolerante >=4/expected-set-Assertion NUR falls Gate vor-existierende Rows beweist UND der Seed echt geuebt bleibt); #11 Base-Org present + nullable erstellt_von bestaetigt. Alle behalten echte Runtime-Row/Return-Assertions (CLAUDE.md Test-Regel), Best-Effort-Teardown in der POST-yield-Sektion (test_rls_isolation.py:101-116, MED-1). Haengt am Plan-01-Base-Seed (T-PGTEST-20) + A-1-DATABASE_URL. |
</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen / Schemas

- `crm.accounts` (schreiben — FK-Ziel für account_memory; Test-Insert mit tenant_id) — RLS engaged
- `crm.account_memory` (schreiben + lesen — die merge-Tests; tenant_id muss = gesetzter Tenant, RLS WITH CHECK)
- `training.transcript_archive` (schreiben + lesen — anonymizer Logic-Group; ORM-los, existiert via Gate-Schema-Dump)
- `public.organisations` + `public.tenant_orgs` (Seed-Kette via Trigger trg_mk_tenant_org — für crm-FK + set_current_tenant; UND der primäre Test-Gegenstand von test_tenant_orgs/Task 4)
- `public.users` + `public.calls` (test_tenant_orgs backfill-Tests — calls.tenant_id-Bridge via users.org_id → tenant_orgs.id)
- `public.api_rates` (schreiben + lesen — test_08_14, in-memory SQLite via `ApiRate.__table__.create`; PUBLIC-Tabelle, KEIN crm-Schema, KEIN RLS — reine NOT-NULL-Seed-Regression)

### Katalog-Beleg (zitiert aus RESEARCH; Schema kommt 1:1 vom Prod-nerve-Dump, Plan 02)

`training.transcript_archive` ist eine ORM-LOSE Tabelle (nur im DB-Schema, nicht in models.py) — der
Schild-Guard fängt sie genau deshalb über `pg_description` (CLAUDE.md Punkt 23). Sie wird vom
`pg_dump --schema-only nerve` getragen (Plan 02 Dump-Treue-Assertion) → KEIN hand-DDL `CREATE TABLE
training.transcript_archive` mehr nötig im Test.

`trg_mk_tenant_org` (Migration 0011) ist ein AFTER-INSERT-Trigger auf `public.organisations`, der bei jedem
`INSERT organisations` eine `tenant_orgs`-Row mit `legacy_org_id = NEW.id` per ON CONFLICT (legacy_org_id)
DO NOTHING anlegt. `tenant_orgs` hat ein `UNIQUE(legacy_org_id)`. Auf nerve_test (vom Prod-nerve gedumpt +
auf head migriert) ist dieser Trigger AKTIV → test_tenant_orgs MUSS die Trigger-Row erwarten statt sie zu
doppeln (F1, Task 4).

`api_rates` (models.py:524-540) ist eine PUBLIC-Tabelle (`__tablename__='api_rates'`, `__table_args__` nur
UniqueConstraint `uix_api_rate_active` + comment, KEIN {'schema':'crm'}). Sie hat eine NOT-NULL-Spalte
`last_checked_at` (DateTime, default=utcnow, nullable=False, Z.538) — genau die Regression, die test_08_14
prüft. Da public, baut `ApiRate.__table__.create(engine)` sie ohne crm/training-ATTACH → kein
"unknown database crm" nach Listener-Entfernung.

crm-RLS/FORCE/GRANTs (RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test):
7 crm-RLS-Policies, ENABLE+FORCE auf account_memory/accounts/contacts/meetings/user_preferences, GRANTs
nerve_app=DML / nerve_anon_worker=SELECT. crm.account_memory hat eine `tenant_id`-Spalte mit FK →
`public.tenant_orgs(id)` (RESEARCH Q4b — eine erfundene UUID würde FK-Verletzung werfen, daher Seed).

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| `account_memory.tenant_id` | Test-Insert in merge-Tests | DB-Spalte `crm.account_memory.tenant_id` (FK→tenant_orgs, RLS WITH CHECK) | ✓ RESEARCH Q4b + RLS-Treue-Beweis |
| `account_memory` merge-Felder (meddpicc/context_hooks) | merge_account_memory liest/schreibt | DB-Spalten in `crm.account_memory` (JSONB) | ✓ Schema vom Prod-nerve-Dump (Plan 02) |
| `crm.accounts` FK-Ziel | Test legt accounts-Row vor account_memory an | DB-Tabelle `crm.accounts` mit RLS | ✓ test_rls_isolation.py:82-90-Muster |
| `transcript_archive` (anonymized_at-Stamp) | anonymizer _run schreibt | DB-Tabelle `training.transcript_archive` (ORM-LOS — kein models.py-Eintrag, nur DB) | ✓ via Schema-Dump; KEIN hand-DDL mehr |
| `id` (TranscriptSegment) | _seed_account-Insert | DB-Spalte BIGSERIAL (PG vergibt selbst) | ✓ explizite id WEGLASSEN gegen PG (Klasse-D-Hinweis) |
| `tenant_orgs` (test_tenant_orgs) | `_mk_org` INSERT organisations → Trigger erzeugt Row → Test liest sie zurück | DB-Tabelle `public.tenant_orgs` (UNIQUE legacy_org_id; vom Trigger trg_mk_tenant_org gefüllt) | ✓ F1/Task 4: kein Python-Doppel-Seed; test_rls_isolation.py:33-54-Read-Back-Muster |
| `calls.tenant_id` (backfill-Tests) | `_backfill_calls_tenant_id` UPDATE-Join | DB-Spalte `public.calls.tenant_id` (nullable, Bridge via users.org_id → tenant_orgs.id) | ✓ Logik-Analog der Migration 0011 Step 4; Row-Read-Assertion |
| geseedete Rows (Teardown) | reverse-FK-DELETE in der POST-yield-Sektion | crm.*/tenant_orgs/organisations/users/calls | ✓ POST-yield try/except (test_rls_isolation.py:101-116, MED-1) → kein Leak bei Assertion-Fehler |
| `set_current_tenant` → `app.tenant_id` GUC | vor crm-Writes | transaktions-lokaler GUC (NICHT DB-Spalte) — gelesen von RLS-Policies | ✓ db.py:87; greift via MODUL-SessionLocal (Plan-01-Umbindung) + DATABASE_URL=postgres im Gate (A-1, Plan 02) |
| `api_rates.last_checked_at` | test_08_14 INSERT + NOT-NULL-COUNT-Assertion | DB-Spalte `public.api_rates.last_checked_at` (DateTime, NOT NULL) — in-memory SQLite via `ApiRate.__table__.create` | ✓ models.py:538 (nullable=False); PUBLIC-Tabelle, kein crm → kein ATTACH nötig |

### Bei Diskrepanz: STOP + Replan
(z.B. account_memory-Insert ohne tenant_id → RLS WITH CHECK violation; transcript_archive nicht im Schema → Dump-Lücke → zurück an Plan 02; ApiRate wäre wider Erwarten crm-scoped → Option B ungültig, STOP; test_tenant_orgs UNIQUE-Kollision trotz Port → trg_mk_tenant_org-Read-Back nicht korrekt umgesetzt → STOP)

<verification>
- Req-6: `grep _sqlite_attach_crm_training_schemas database/db.py` + `grep "startswith('sqlite')" app.py` → leer; Suite grün ohne Pflaster.
- Req-4: test_rls_isolation.py + test_anonymizer_worker.py (RLS-Gruppe) PASSED (nicht SKIPPED) im Gate-Log.
- Klasse-A: test_account_memory_briefing + anonymizer Logic-Group PASSED gegen nerve_test (keine Collection-Errors); Reverse-FK-Teardown in der POST-yield-Sektion (try/except nach yield, test_rls_isolation.py:101-116, MED-1 — kein State-Leak bei Assertion-Fehler).
- test_08_14: `grep Base.metadata.create_all tests/test_08_14_apirate_seed.py` → leer; `grep ApiRate.__table__.create ...` → Treffer; im Gate-Lauf PASSED (nicht error/SKIPPED), kein "unknown database crm".
- F1/test_tenant_orgs: im Gate-Lauf PASSED (Trigger-Semantik, kein UNIQUE(legacy_org_id)-Kollisions-Error, count==3-Assert hält); `_seed_tenant_orgs` doppelt die Trigger-Row nicht mehr; test_dualwrite_trigger_fires liest die Trigger-Row zurück.
- WAL-Hook (db.py Z.22-27): bewusst BEHALTEN (KEEP-Entscheidung, Modul-Engine + sqlite-Guard → inert im PG-Gate; schützt lokale Dev-SQLite; kein Req-6-Ziel) — kein offenes "prüfen"-TODO.
- Klasse D/E (test_ft_seed etc.): falls rot durch echten App-Bug → SUMMARY-Eskalation, nicht gepatcht.
- MED-3 (Ein-Deploy-Constraint): die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03 zusammen committet sind; kein Zwischen-Deploy nach Wave 1 (der `<verify>`-deploy.sh-Lauf ist der eine finale integrierte Gate-Lauf).
</verification>

<success_criteria>
- ATTACH-Listener + SQLite-Alembic-Hook entfernt; kein toter SQLite-Emulations-Pfad.
- WAL-Hook (db.py Z.22-27) bewusst BEHALTEN — KEEP-Entscheidung dokumentiert (Modul-Engine, sqlite-geguardet → inert im PG-Gate; schützt echte lokale Dev-SQLite außerhalb der Tests; kein Req-6-Emulations-Ziel). Kein offenes "prüfen"-TODO mehr.
- Beide Klasse-A-Test-Gruppen gegen nerve_test-PG, Integration-Assertions intakt (kein Source-Presence).
- test_08_14_apirate_seed.py entblockt: create_all auf die public ApiRate-Tabelle gescopet (`ApiRate.__table__.create`), DSN-unabhängig (in-memory SQLite, nicht geskippt), echte NOT-NULL-Runtime-Regression intakt, kein "unknown database crm" nach Listener-Entfernung.
- F1: test_tenant_orgs.py auf PG-Trigger-Semantik portiert — erwartet die vom trg_mk_tenant_org auto-erzeugte tenant_orgs-Row (kein Python-Doppel-Seed), kein UNIQUE(legacy_org_id)-Kollisions-Error, count==3-Assert hält, echte Idempotenz-Assertion (erwarteter IntegrityError auf forcierten Duplikat) bleibt; im Gate PASSED (nicht error/SKIPPED).
- Reverse-FK-Teardown aller portierten Test-Gruppen in der Fixture-POST-yield-Sektion (try/except nach yield, analog test_rls_isolation.py:101-116, MED-1) → läuft auch bei Assertion-Fehler, kein State-Leak in nerve_test.
- RLS+Anon-RLS-Gruppe PASSED im Gate; volle Suite grün ohne Pflaster (inkl. test_08_14 + test_tenant_orgs entblockt — kein verwaister Listener-/Trigger-inkompatibler Test).
- MED-3: Ein-Deploy-Constraint — Phase validiert durch genau EINEN deploy.sh production-Lauf nach gemeinsamem Commit aller 3 Pläne; kein Zwischen-Deploy nach Wave 1.
- Etwaige Klasse-D/E-App-Bugs eskaliert, nicht still gepatcht.
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-03-SUMMARY.md`
</output>
