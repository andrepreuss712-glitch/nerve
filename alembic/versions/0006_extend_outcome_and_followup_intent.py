"""Extend outcome CHECK + add followup_intent to calls.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-28

Phase 08.23.2.D.UX — UX-Quality-Polish Wave 0.
Adds send_info + gatekeeper_blocked to ck_calls_outcome (6->8 values).
Adds followup_intent TEXT NOT NULL DEFAULT 'none' with ck_calls_followup_intent.

Wave 3+4 require send_info + gatekeeper_blocked as valid outcome values.
Without this migration, any INSERT/UPDATE with these new outcomes violates the CHECK.
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

# ── Outcome CHECK constraint ─────────────────────────────────────────────────

_CK_OUTCOME = 'ck_calls_outcome'

_NEW_OUTCOME_CONSTRAINT = (
    "outcome IN ('meeting_booked', 'callback', 'send_info', 'wrong_person', "
    "'gatekeeper_blocked', 'no_interest', 'contract_signed', 'unknown') OR outcome IS NULL"
)
_OLD_OUTCOME_CONSTRAINT = (
    "outcome IN ('meeting_booked', 'callback', 'no_interest', 'wrong_person', "
    "'contract_signed', 'unknown') OR outcome IS NULL"
)

# ── followup_intent column + CHECK ──────────────────────────────────────────

_CK_FOLLOWUP = 'ck_calls_followup_intent'
_FOLLOWUP_CONSTRAINT = (
    "followup_intent IN ('none', 'callback', 'meeting', 'send_info', 'retry_internal')"
)


def upgrade() -> None:
    with op.batch_alter_table('calls') as batch_op:
        # 1. Extend outcome CHECK constraint (drop old 6-value, add new 8-value)
        batch_op.drop_constraint(_CK_OUTCOME, type_='check')
        batch_op.create_check_constraint(_CK_OUTCOME, _NEW_OUTCOME_CONSTRAINT)
        # 2. Add followup_intent column (NOT NULL with server_default='none')
        batch_op.add_column(
            sa.Column('followup_intent', sa.Text(), nullable=False,
                      server_default='none')
        )
        # 3. Add followup_intent CHECK constraint
        batch_op.create_check_constraint(_CK_FOLLOWUP, _FOLLOWUP_CONSTRAINT)


def downgrade() -> None:
    with op.batch_alter_table('calls') as batch_op:
        # Revert followup_intent (CHECK first, then column)
        batch_op.drop_constraint(_CK_FOLLOWUP, type_='check')
        batch_op.drop_column('followup_intent')
        # Revert outcome CHECK to 6 values
        batch_op.drop_constraint(_CK_OUTCOME, type_='check')
        batch_op.create_check_constraint(_CK_OUTCOME, _OLD_OUTCOME_CONSTRAINT)
