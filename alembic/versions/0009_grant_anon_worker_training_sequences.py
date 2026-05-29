"""Grant USAGE+SELECT on training sequences to nerve_anon_worker.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-29

Phase 08.23.2.D.UX.0 — Plan 03 deviation fix (sequence-grant gap from 0008).

0008 granted INSERT/SELECT on training.transcript_archive but missed the
table's identity sequence (transcript_archive_id_seq). Two failures result:
  - pg_dump --schema=training reads the sequence value
    (SELECT last_value, is_called FROM training.transcript_archive_id_seq)
    -> "permission denied for sequence transcript_archive_id_seq" (Schicht-3 backup)
  - the future anonymisation worker (D.UX.1) needs USAGE on the sequence for
    nextval() on INSERT into transcript_archive.

Grant on ALL SEQUENCES IN SCHEMA training covers the existing sequence, and
ALTER DEFAULT PRIVILEGES covers sequences created later in the schema so this
gap cannot silently reappear.

NOTE: GRANT on public.transcript_segments (reserved for D.UX.1 in 0008's note)
is NOT here — that table still does not exist. D.UX.1's migration chains from 0009.
"""
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA training TO nerve_anon_worker")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA training "
        "GRANT USAGE, SELECT ON SEQUENCES TO nerve_anon_worker"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA training "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM nerve_anon_worker"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA training FROM nerve_anon_worker")
