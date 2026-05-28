"""Add score_breakdown and score_schema_version to calls.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-28

Phase 08.23.2.D.UX — Wave 1 (Plan 02).

Note: coaching_score (FLOAT) already existed before this migration
(present in initial schema, confirmed via inspect.sh 2026-05-28).
This migration ONLY adds score_breakdown + score_schema_version.

score_breakdown: JSONB NULL — written by Wave 4 correct_outcome endpoint.
  Schema (version 1, 9 keys):
    schema_version, kb_end_norm, behandelt_rate, redeanteil_score, skript_norm,
    frage_qualitaet, outcome_modifier, process_score, final_score, computed_at_iso

score_schema_version: SMALLINT NOT NULL DEFAULT 1 — enables forward-compatible
  schema migrations without data loss (T-D.UX-02-01 mitigated).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB as _JSONB

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

# JSON type with PostgreSQL JSONB variant (matches models.py JSON_TYPE pattern)
_JSON_TYPE = sa.JSON().with_variant(_JSONB(), 'postgresql')


def upgrade() -> None:
    with op.batch_alter_table('calls') as batch_op:
        # coaching_score already exists — DO NOT add it
        batch_op.add_column(
            sa.Column('score_breakdown', _JSON_TYPE, nullable=True)
        )
        batch_op.add_column(
            sa.Column('score_schema_version', sa.SmallInteger(),
                      nullable=False, server_default='1')
        )


def downgrade() -> None:
    with op.batch_alter_table('calls') as batch_op:
        batch_op.drop_column('score_schema_version')
        batch_op.drop_column('score_breakdown')
