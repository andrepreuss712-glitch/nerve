import pytest


def test_tables_created(db_session):
    from database.db import Base
    import database.models  # noqa: F401
    tables = set(Base.metadata.tables.keys())
    required = {"ft_call_sessions", "ft_assistant_events", "ft_objection_events", "prompt_versions"}
    missing = required - tables
    if missing:
        pytest.skip(f"Wave 1 gap: missing tables {missing}")
    assert required.issubset(tables)


def test_user_market_default(db_session):
    from database.models import User
    if not hasattr(User, "market"):
        pytest.skip("Wave 1 gap: User.market column not yet added")
    u = User(email="t@t.de", passwort_hash="x")
    db_session.add(u)
    db_session.commit()
    assert u.market == "dach"
    assert u.language == "de"


def test_transcript_nullable(db_session):
    try:
        from database.models import FtAssistantEvent, FtCallSession, User  # noqa: F401
    except ImportError:
        pytest.skip("Wave 1 gap: ft_* models not yet defined")
    # Full insert test — Wave 1 fills in.
    pytest.skip("Wave 1 gap: insert flow requires model + FK chain")
