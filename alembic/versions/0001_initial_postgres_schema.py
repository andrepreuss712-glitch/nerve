"""initial_postgres_schema (no-op marker; schema created via Base.metadata.create_all)

Revision ID: 0001
Revises:
Create Date: 2026-05-12

CHANGED 2026-05-12 (Phase 08.23.2.A pre-cutover prep):
The original manually-written CREATE TABLE migration had wrong FK order — it
tried to create `users` (with FK -> profiles.id) before `profiles` exists.
SQLAlchemy's Base.metadata.create_all() handles cyclic FKs via two-pass DDL,
but a hand-written alembic migration would need explicit `use_alter=True` on
both circular FKs in models.py.

Decision: leave 0001 as a no-op MARKER. Initial schema is created by
Base.metadata.create_all() during cutover (per docs/cutover-runbook.md
Step 4a). After schema creation, `alembic stamp 0001` records that we are
at this baseline revision. Future migrations (08.23.2.F/G/H) generate as
proper alembic deltas from this baseline.

Original broken file kept as .bak-broken-fk-order for reference.
"""

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: initial schema is created via Base.metadata.create_all() during
    # cutover. This marker records the alembic baseline state. See file header.
    pass


def downgrade() -> None:
    # Initial schema cannot be downgraded via alembic (no DROP order info).
    # For full rollback, recreate the DB and restore from backup.
    pass
