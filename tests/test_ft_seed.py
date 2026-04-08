from database.models import PromptVersion
from app import _seed_prompt_versions


EXPECTED_MODULES = [
    'assistant_live',
    'coaching_live',
    'objection_trigger',
    'ewb_ranking',
    'api_frage',
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
    assert count_after_first == 6
    assert count_after_second == 6
