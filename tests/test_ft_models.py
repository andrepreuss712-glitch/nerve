import pytest


def test_tables_created(db_session):
    from database.db import Base
    import database.models  # noqa: F401
    tables = set(Base.metadata.tables.keys())
    required = {"ft_call_sessions", "ft_assistant_events", "ft_objection_events", "prompt_versions"}
    assert required.issubset(tables)


def test_user_market_default(db_session):
    from database.models import Organisation, User
    org = Organisation(name="TestOrg")
    db_session.add(org)
    db_session.flush()
    u = User(org_id=org.id, email="t@t.de", passwort_hash="x")
    db_session.add(u)
    db_session.commit()
    assert u.market == "dach"
    assert u.language == "de"


def test_transcript_nullable(db_session):
    from database.models import (
        Organisation, User, FtCallSession, FtAssistantEvent,
    )
    org = Organisation(name="TestOrg2")
    db_session.add(org)
    db_session.flush()
    u = User(org_id=org.id, email="n@n.de", passwort_hash="x")
    db_session.add(u)
    db_session.flush()
    sess = FtCallSession(user_id=u.id, mode="cold_call")
    db_session.add(sess)
    db_session.flush()
    evt = FtAssistantEvent(
        ft_session_id=sess.id,
        user_id=u.id,
        timestamp_ms=0,
        conversation_phase="unknown",
        speaker=None,
        transcript_segment=None,
        hint_type="objection",
        hint_text="x",
        model_used="claude-haiku",
        prompt_version="v1.0.0",
    )
    db_session.add(evt)
    db_session.commit()
    got = db_session.query(FtAssistantEvent).filter_by(id=evt.id).first()
    assert got.transcript_segment is None
    assert got.speaker is None
