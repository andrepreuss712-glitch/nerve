"""Add outcome fields + conversation_log_id FK to calls (Phase 08.23.2.D REQ-D-1, prerequisite for REQ-D-2).

Adds 4 nullable columns to calls:
  - conversation_log_id (Integer FK to conversation_logs.id, nullable)
    NOTE: This FK column is required by REQ-D-2 (calls-UPDATE in Plan 04 writes
    saved_conv_id into it). The column itself is created here in Plan 01.
  - outcome_confidence (Float, nullable)
  - outcome_note (Text, nullable)
  - outcome_source (Text, nullable + CHECK: ai_auto/ai_auto_unsicher/user_corrected/NULL)

No backfill required -- existing rows keep NULL (forward-feature semantics).
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

_CK_OUTCOME_SOURCE = 'ck_calls_outcome_source'
_FK_CONVERSATION_LOG = 'fk_calls_conversation_log_id'

# Column list that existed BEFORE this migration (0004 state).
# Used in downgrade() raw-SQL path to reconstruct the pre-0005 table.
_PRE_0005_COLS = (
    'id, tenant_id, account_id, contact_id, user_id, call_mode, call_type, '
    'started_at, ended_at, transcript_storage, transcript_expires_at, '
    'call_summary, outcome, audio_health_score, coaching_score, '
    'meddpicc_extracted, created_at'
)


def upgrade() -> None:
    with op.batch_alter_table('calls') as batch_op:
        batch_op.add_column(sa.Column('conversation_log_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('outcome_confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('outcome_note', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('outcome_source', sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            _CK_OUTCOME_SOURCE,
            "outcome_source IN ('ai_auto', 'ai_auto_unsicher', 'user_corrected') OR outcome_source IS NULL",
        )
        batch_op.create_foreign_key(
            _FK_CONVERSATION_LOG,
            'conversation_logs',
            ['conversation_log_id'],
            ['id'],
        )


def downgrade() -> None:
    # SQLite + Alembic batch_alter_table limitation:
    # batch_alter_table builds the temp table from the ORM model. Once models.py
    # contains ck_calls_outcome_source, the batch-copy fails because it tries to
    # create a temp table with that CHECK but without the outcome_source column.
    #
    # Workaround: raw-SQL CREATE+COPY+DROP pattern (what batch_alter_table does
    # internally, but without pulling constraints from the ORM model).
    # This is safe because SQLite CHECK enforcement is dialect-level and the
    # constraint disappears with the column in the new table DDL.
    bind = op.get_bind()
    bind.execute(sa.text(
        "CREATE TABLE _calls_pre0005 ("
        "  id VARCHAR(36) NOT NULL,"
        "  tenant_id VARCHAR(36),"
        "  account_id VARCHAR(36),"
        "  contact_id VARCHAR(36),"
        "  user_id INTEGER NOT NULL,"
        "  call_mode TEXT NOT NULL,"
        "  call_type TEXT,"
        "  started_at DATETIME,"
        "  ended_at DATETIME,"
        "  transcript_storage TEXT,"
        "  transcript_expires_at DATETIME,"
        "  call_summary TEXT,"
        "  outcome TEXT,"
        "  audio_health_score FLOAT,"
        "  coaching_score FLOAT,"
        "  meddpicc_extracted JSON,"
        "  created_at DATETIME,"
        "  PRIMARY KEY (id),"
        "  CONSTRAINT ck_calls_call_mode CHECK (call_mode IN ('cold_call', 'meeting_consented')),"
        "  CONSTRAINT ck_calls_transcript_storage CHECK (transcript_storage IN ('none', 'ephemeral', 'consented_full')),"
        "  CONSTRAINT ck_calls_outcome CHECK (outcome IN ('meeting_booked', 'callback', 'no_interest', 'wrong_person', 'contract_signed', 'unknown') OR outcome IS NULL),"
        "  FOREIGN KEY(user_id) REFERENCES users (id)"
        ")"
    ))
    bind.execute(sa.text(
        f"INSERT INTO _calls_pre0005 ({_PRE_0005_COLS}) "
        f"SELECT {_PRE_0005_COLS} FROM calls"
    ))
    bind.execute(sa.text("DROP TABLE calls"))
    bind.execute(sa.text("ALTER TABLE _calls_pre0005 RENAME TO calls"))
