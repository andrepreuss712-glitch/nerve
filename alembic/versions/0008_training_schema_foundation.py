"""Add training schema foundation, transcript_archive table, nerve_anon_worker grants,
and users.is_test_user column.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-29

Phase 08.23.2.D.UX.0 — Wave 1 (Migration).

NOTE: CREATE ROLE nerve_anon_worker is NOT in this migration — see Task 2 Runbook.
Passwords must not appear in VCS (CLAUDE.md HART Secrets-Regel).
Roles are cluster-global and belong outside schema migrations.

NOTE: GRANT on public.transcript_segments is NOT here — that table is created
in migration 0009 (D.UX.1). Add that GRANT in 0009.
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS training")
    op.execute("""
        CREATE TABLE IF NOT EXISTS training.transcript_archive (
            id               BIGSERIAL   PRIMARY KEY,
            source_call_hash TEXT        NOT NULL,
            segment_index    INTEGER     NOT NULL,
            speaker          TEXT        NOT NULL
                CHECK (speaker IN ('berater', 'kunde', 'system')),
            text             TEXT        NOT NULL,
            ts_offset_ms     INTEGER     NOT NULL,
            schema_version   SMALLINT    NOT NULL DEFAULT 1,
            archived_at      TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("GRANT USAGE ON SCHEMA training TO nerve_anon_worker")
    op.execute("GRANT INSERT, SELECT ON training.transcript_archive TO nerve_anon_worker")
    op.execute("GRANT SELECT ON public.calls TO nerve_anon_worker")
    op.execute("GRANT SELECT ON public.users TO nerve_anon_worker")
    op.execute("GRANT SELECT ON public.conversation_logs TO nerve_anon_worker")
    # NOTE: public.transcript_segments existiert noch NICHT (kommt in 0009/D.UX.1) — kein GRANT hier
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('is_test_user', sa.Boolean(), nullable=False,
                      server_default='false')
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_test_user')
    op.execute("REVOKE SELECT ON public.conversation_logs FROM nerve_anon_worker")
    op.execute("REVOKE SELECT ON public.users FROM nerve_anon_worker")
    op.execute("REVOKE SELECT ON public.calls FROM nerve_anon_worker")
    op.execute("REVOKE INSERT, SELECT ON training.transcript_archive FROM nerve_anon_worker")
    op.execute("REVOKE USAGE ON SCHEMA training FROM nerve_anon_worker")
    op.execute("DROP TABLE IF EXISTS training.transcript_archive")
    op.execute("DROP SCHEMA IF EXISTS training")
