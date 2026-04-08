import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
# Import all models so Base.metadata knows about them
import database.models  # noqa: F401


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
