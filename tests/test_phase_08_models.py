"""Phase 08 Plan 01 Task 1 — Model schema changes for EWB-Qualitaet.

Tests the 3 in-place Column changes in database/models.py:
- ObjectionEvent.success → nullable=True (D-01, 3-state)
- ConversationLog.anrede → new VARCHAR(10) nullable column (D-14)
- PromptVersion.is_default → new Boolean nullable=False column (D-26)

TDD gate: these tests MUST fail before Task 1 edits and MUST pass after.
"""
import pytest


def test_objection_event_success_is_nullable(db_session):
    """D-01: ObjectionEvent.success accepts NULL for 3-state rating."""
    from database.models import ObjectionEvent
    col = ObjectionEvent.__table__.columns['success']
    assert col.nullable is True, (
        "ObjectionEvent.success must be nullable=True (Phase 08 D-01 3-state). "
        f"Got nullable={col.nullable}"
    )


def test_conversation_log_anrede_exists_and_nullable(db_session):
    """D-14: conversation_logs.anrede exists as String(10) nullable=True."""
    from database.models import ConversationLog
    assert 'anrede' in ConversationLog.__table__.columns, (
        "ConversationLog.anrede column missing (Phase 08 D-14 PreCall-Override)"
    )
    col = ConversationLog.__table__.columns['anrede']
    assert col.nullable is True, (
        f"ConversationLog.anrede must be nullable=True. Got nullable={col.nullable}"
    )
    # String(10) check
    assert hasattr(col.type, 'length'), (
        f"ConversationLog.anrede must be String type. Got {type(col.type)}"
    )
    assert col.type.length == 10, (
        f"ConversationLog.anrede must be String(10). Got length={col.type.length}"
    )


def test_prompt_version_is_default_exists(db_session):
    """D-26: prompt_versions.is_default exists as Boolean nullable=False default=False."""
    from database.models import PromptVersion
    assert 'is_default' in PromptVersion.__table__.columns, (
        "PromptVersion.is_default column missing (Phase 08 D-26 A/B-Routing)"
    )
    col = PromptVersion.__table__.columns['is_default']
    assert col.nullable is False, (
        f"PromptVersion.is_default must be nullable=False. Got nullable={col.nullable}"
    )


def test_prompt_version_unique_constraint_preserved(db_session):
    """D-26 safety: existing UniqueConstraint uq_prompt_version_module must remain."""
    from database.models import PromptVersion
    constraint_names = {c.name for c in PromptVersion.__table__.constraints if c.name}
    assert 'uq_prompt_version_module' in constraint_names, (
        "uq_prompt_version_module UniqueConstraint must be preserved during Phase 08 edits"
    )
