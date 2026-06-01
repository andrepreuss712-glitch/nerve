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
