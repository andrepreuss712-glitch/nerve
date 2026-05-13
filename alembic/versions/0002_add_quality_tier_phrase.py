"""add quality_tier to phrases table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13

Phase 08.23.2.B: DSGVO-Anonymisierungs-Pipeline.
quality_tier='A': sauber anonymisiert
quality_tier='B': Edge-Cases (NER-Heuristik)
quality_tier='C': Art-9-Treffer oder Pipeline-Exception
DPO-Training-Filter in Phase 08.23.2.E: WHERE quality_tier IN ('A', 'B')
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'phrases',
        sa.Column(
            'quality_tier',
            sa.String(1),
            nullable=False,
            server_default='A',
        )
    )


def downgrade() -> None:
    op.drop_column('phrases', 'quality_tier')
