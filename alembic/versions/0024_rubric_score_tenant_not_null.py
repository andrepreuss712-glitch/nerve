"""Phase 08.23.2.TENANT-FOUND Plan 02 — Bewertungs-Kinder tenant_id NOT NULL (Sammel-Revision).

Konsistente NOT-NULL-Haerte auf rubric_score + suggestion_reactions (TF-2, D-11). Beide sind
prod schon FORCE RLS (0019/0020); diese Revision zieht nur die NOT-NULL-Constraint nach.
rubric_score ist leer -> SET NOT NULL trivial; suggestion_reactions hat 3/3 Zeilen mit Tenant
(RESEARCH §1.3) -> kein Backfill noetig. abstain_log bekommt NOT NULL + RLS in 0022 (gefaltet).

Reihenfolge: 0022(editiert)->0023(Backfill)->0024. EIN Deploy, Migrationen VOR Restart.
COMMENT-Texte = Single-Source = models.py comment=.

Revision ID: 0024
Revises: 0023
"""
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rubric_score ist leer (RESEARCH §1.3) -> SET NOT NULL trivial, kein Backfill.
    op.alter_column('rubric_score', 'tenant_id', nullable=False,
                    existing_type=postgresql.UUID(as_uuid=True))
    op.execute("COMMENT ON COLUMN public.rubric_score.tenant_id IS 'Mandanten-Abschottung (D-11 FORCE RLS, NOT NULL). Abgeleitet aus calls.tenant_id via Daemon-GUC (Plan 04 erbt Plan-03-A1-Klammer).'")

    # suggestion_reactions: 3/3 prod-Zeilen mit Tenant (RESEARCH §1.3) -> SET NOT NULL ohne Backfill.
    # Request-Flush (app_routes.py) skippt fail-closed bei fehlendem g.tenant_id (kein IntegrityError).
    op.alter_column('suggestion_reactions', 'tenant_id', nullable=False,
                    existing_type=postgresql.UUID(as_uuid=True))
    op.execute("COMMENT ON COLUMN public.suggestion_reactions.tenant_id IS 'Mandanten-Abschottung (FORCE RLS tenant_isolation, NOT NULL; abgeleitet aus calls.tenant_id). Request-Flush fail-closed bei fehlendem Tenant.'")


def downgrade() -> None:
    op.alter_column('suggestion_reactions', 'tenant_id', nullable=True,
                    existing_type=postgresql.UUID(as_uuid=True))
    op.alter_column('rubric_score', 'tenant_id', nullable=True,
                    existing_type=postgresql.UUID(as_uuid=True))
