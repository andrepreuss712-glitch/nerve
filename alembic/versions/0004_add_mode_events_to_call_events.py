"""add mode_switch and mode_initial to call_events event_type check constraint

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21

Phase 08.23.2.C.R: Gatekeeper-Modus-Toggle ersetzt Auto-Erkennung.
mode_switch: Manueller Toggle durch Berater (manual_mode_toggle Socket-Handler).
mode_initial: Startmodus bei Call-Anlage (create_call_for_sid).
DSGVO Single-Speaker-Constraint: Auto-Erkennung konzeptuell unmoeglich.
"""
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

_NEW_CONSTRAINT = (
    "event_type IN ("
    "'transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', "
    "'audio_health', 'objection_detected', 'consent_optin', "
    "'mode_switch', 'mode_initial'"
    ")"
)

_OLD_CONSTRAINT = (
    "event_type IN ("
    "'transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', "
    "'audio_health', 'objection_detected', 'consent_optin'"
    ")"
)

_CONSTRAINT_NAME = 'ck_call_events_event_type'


def upgrade() -> None:
    # PostgreSQL: DROP + RECREATE (einzige Methode fuer CHECK-Constraint-Aenderung)
    # SQLite: render_as_batch=True in env.py uebernimmt CREATE+COPY+DROP automatisch
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_='check')
        batch_op.create_check_constraint(_CONSTRAINT_NAME, _NEW_CONSTRAINT)


def downgrade() -> None:
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_='check')
        batch_op.create_check_constraint(_CONSTRAINT_NAME, _OLD_CONSTRAINT)
