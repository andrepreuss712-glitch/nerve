import pytest


def test_prompt_seed(db_session):
    try:
        from database.models import PromptVersion
        from app import _seed_prompt_versions
    except ImportError:
        pytest.skip("Wave 2 gap: PromptVersion / _seed_prompt_versions not yet implemented")
    _seed_prompt_versions(db_session)
    row = db_session.query(PromptVersion).filter_by(module="assistant_live", is_active=True).first()
    assert row is not None
    assert row.version == "v1.0.0"


def test_seed_idempotent(db_session):
    try:
        from database.models import PromptVersion
        from app import _seed_prompt_versions
    except ImportError:
        pytest.skip("Wave 2 gap")
    _seed_prompt_versions(db_session)
    count_after_first = db_session.query(PromptVersion).count()
    _seed_prompt_versions(db_session)
    count_after_second = db_session.query(PromptVersion).count()
    assert count_after_first == count_after_second
