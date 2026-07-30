"""rename mode_initial/mode_switch to counterpart_initial/counterpart_switch

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-28

Phase 08.23.2.COUNTERPART: der Gespraechspartner heisst ueberall 'counterpart'
('gatekeeper' | 'decision_maker'); die Anruf-Art heisst 'call_type'
('cold_call' | 'meeting'). Die zwei Call-Event-Namen trugen als letzte noch das Wort
'mode' und hielten damit die Wort-Ueberlappung in der Datenbank am Leben.

Der Punkt-20-Pflicht-grep (2026-07-28) hat 0 Leser belegt — nur Schreiber und Tests.
Die Umbenennung ist deshalb erlaubt und wird GANZ gemacht: alte Namen raus, die
Bestandszeilen (Stand 2026-07-28: 72 mode_initial + 41 mode_switch = 113) werden
mitgezogen. Kein Halb-Zustand.

Deploy-Reihenfolge: MIGRATION -> CODE. Im Zwischenfenster schreibt alter Code die alten
Namen gegen den neuen Constraint; beide Writer sind non-fatal (live_session.py:747,
deepgram_service.py:1194) -> hoechstens ein verlorener Protokoll-Eintrag, kein
Anruf-Abbruch. Ein Code-Rollback ist aus demselben Grund gutartig.

Reihenfolge im upgrade() ist zwingend: DROP Constraint -> UPDATE Zeilen -> CREATE
Constraint. Andersherum scheitert das UPDATE am jeweils geltenden CHECK.
"""
from alembic import op

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None

_CONSTRAINT_NAME = 'ck_call_events_event_type'

_BASE_VALUES = (
    "'transcript_chunk', 'suggestion_shown', 'reaction', 'phase_change', "
    "'audio_health', 'objection_detected', 'consent_optin'"
)

_NEW_CONSTRAINT = (
    "event_type IN (" + _BASE_VALUES + ", 'counterpart_switch', 'counterpart_initial')"
)

_OLD_CONSTRAINT = (
    "event_type IN (" + _BASE_VALUES + ", 'mode_switch', 'mode_initial')"
)

# (alt, neu) — Reihenfolge egal, die Werte ueberschneiden sich nicht.
_RENAMES = (
    ('mode_initial', 'counterpart_initial'),
    ('mode_switch', 'counterpart_switch'),
)


def upgrade() -> None:
    # 1) Constraint weg — sonst verbietet er die neuen Werte im UPDATE.
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_='check')
    # 2) Bestandszeilen mitziehen (kein Halb-Zustand, Andre-Entscheidung 2026-07-28).
    for _alt, _neu in _RENAMES:
        op.execute(
            f"UPDATE call_events SET event_type = '{_neu}' "
            f"WHERE event_type = '{_alt}'"
        )
    # 3) Constraint mit den neuen Werten — die alten sind ab jetzt verboten.
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.create_check_constraint(_CONSTRAINT_NAME, _NEW_CONSTRAINT)


def downgrade() -> None:
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_='check')
    for _alt, _neu in _RENAMES:
        op.execute(
            f"UPDATE call_events SET event_type = '{_alt}' "
            f"WHERE event_type = '{_neu}'"
        )
    with op.batch_alter_table('call_events') as batch_op:
        batch_op.create_check_constraint(_CONSTRAINT_NAME, _OLD_CONSTRAINT)
