"""add mode column to phrases table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-14

Phase 08.23.2.C: Phasen-Klassifikator + Gatekeeper-Erkennung.
mode='cold_call': Standard-Outbound-Gespraeche
mode='gatekeeper': Gatekeeper-Modus (Sekretaer/Assistent)
mode='meeting': Meeting-/Demo-Gespraeche
Wave 2 (gatekeeper.py + classify_contact) und Wave 4 (PiP-Buttons)
brauchen den Mode-Diskriminator um Gatekeeper-Phrases zu trennen.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mode-Spalte mit server_default='cold_call' — bestehende Zeilen bekommen automatisch 'cold_call'
    op.add_column(
        'phrases',
        sa.Column('mode', sa.String(20), nullable=False, server_default='cold_call'),
    )
    # CHECK-Constraint: mode IN ('cold_call', 'gatekeeper', 'meeting')
    op.execute(
        "ALTER TABLE phrases ADD CONSTRAINT ck_phrases_mode "
        "CHECK (mode IN ('cold_call', 'gatekeeper', 'meeting'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE phrases DROP CONSTRAINT IF EXISTS ck_phrases_mode")
    op.drop_column('phrases', 'mode')
