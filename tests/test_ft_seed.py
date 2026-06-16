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
    # scope-fix (Gemini-3.1-Pro-Fold #3): app-import committet >=6 prompt_versions
    # (_seed_prompt_versions=4 + _seed_ewb_v2=2) in die persistente nerve_test (D-03) -> globale
    # count==4 waere deterministisch False-Red. Auf die test-eigenen EXPECTED_MODULES gescoped.
    count_after_first = (db_session.query(PromptVersion)
                         .filter(PromptVersion.module.in_(EXPECTED_MODULES)).count())
    _seed_prompt_versions(db_session)
    count_after_second = (db_session.query(PromptVersion)
                          .filter(PromptVersion.module.in_(EXPECTED_MODULES)).count())
    assert count_after_first == 4
    assert count_after_second == 4
