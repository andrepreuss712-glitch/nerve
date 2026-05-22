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
    # mode-Spalte hinzufuegen — idempotent via inspect (Spalte koennte durch app.py-Migration bereits existieren)
    from sqlalchemy import inspect as sa_inspect
    from alembic import op as _op
    conn = _op.get_bind()
    inspector = sa_inspect(conn)
    existing_cols = [c['name'] for c in inspector.get_columns('phrases')]
    if 'mode' not in existing_cols:
        op.add_column(
            'phrases',
            sa.Column('mode', sa.String(20), nullable=False, server_default='cold_call'),
        )
    # CHECK-Constraint via batch_alter_table — render_as_batch=True transformiert nur Alembic-Ops,
    # nicht raw SQL in op.execute(). batch_op.create_check_constraint ist SQLite-safe.
    # Bestehenden Constraint ignorieren falls er bereits existiert (idempotent).
    try:
        with op.batch_alter_table('phrases') as batch_op:
            batch_op.create_check_constraint(
                'ck_phrases_mode',
                "mode IN ('cold_call', 'gatekeeper', 'meeting')",
            )
    except Exception:
        pass  # Constraint bereits vorhanden (idempotent re-run)

    # ── Gatekeeper-Seed-Phrases (Phase 08.23.2.C D-05, Req-9) ──────────────────
    # Eingelesen aus tests/fixtures/gatekeeper_phrases_seed.md (Andre-Gate approved in Plan 01).
    # user_id=1 (Admin-MVP — Pitfall 7, RESEARCH.md A7).
    # objection_type entspricht der Mr.-Miyagi-Button-ID im PiP.
    # D-05: mindestens 2 Varianten pro Button (4 Buttons x >= 2 = >= 8 Rows).
    # Tatsaechlich: Button 1 = 3, Button 2 = 3, Button 3 = 2, Button 4 = 2 = 10 Rows.
    # uwg_blocked-Kontext: Diese Seed-Phrasen sind Vertriebs-Reaktions-Vorschlaege (Mr. Miyagi),
    # NICHT die UWG-Hard-Block-Erkennungs-Pattern (die liegen in services/ki_logik.py).
    # Plan 06 Task 3 setzt uwg_blocked=True wenn ein UWG-Pattern erkannt wird —
    # ab diesem Zeitpunkt sind die Mr.-Miyagi-Buttons nicht mehr relevant (Guard blockiert Loop).
    phrases_table = sa.table(
        'phrases',
        sa.column('user_id', sa.Integer),
        sa.column('text', sa.Text),
        sa.column('objection_type', sa.String),
        sa.column('mode', sa.String),
        sa.column('quality_tier', sa.String),
    )

    op.bulk_insert(phrases_table, [
        # ── Button 1: Verbündeten-Bitte (Source: Stephan Heinrich + Ulrike Knauer) — 3 Varianten
        {
            'user_id': 1,
            'text': '{vorname}, dürfte ich Sie um Ihre Einschätzung bitten — wer wäre bei Ihnen für {branche} der richtige Ansprechpartner?',
            'objection_type': 'gatekeeper_verbuendeten_bitte',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Ich brauche kurz Ihre Hilfe — können Sie mir sagen, wer bei Ihnen für {branche} zuständig ist?',
            'objection_type': 'gatekeeper_verbuendeten_bitte',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Sie sind gerade die einzige Person, die mir helfen kann — wer wäre bei Ihnen verantwortlich für {detail}?',
            'objection_type': 'gatekeeper_verbuendeten_bitte',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        # ── Button 2: Insider-Antwort (Source: Tim Taxis + Eduard Klein) — 3 Varianten
        {
            'user_id': 1,
            'text': 'Es geht um {detail} — könnten Sie mich bitte mit der zuständigen Person verbinden?',
            'objection_type': 'gatekeeper_insider_antwort',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Sie wollen ja sicherlich wissen, worum es geht, bevor Sie mich mit {nachname} verbinden — es geht um {detail}.',
            'objection_type': 'gatekeeper_insider_antwort',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Konkret: {detail}. Wer ist bei Ihnen dafür der richtige Ansprechpartner?',
            'objection_type': 'gatekeeper_insider_antwort',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        # ── Button 3: Voss-Label (Source: Chris Voss — Never Split the Difference) — 2 Varianten
        {
            'user_id': 1,
            'text': 'Es klingt so, als ob Sie das tagtäglich filtern müssen — was wäre der einfachste Weg, mich kurz durchzustellen?',
            'objection_type': 'gatekeeper_voss_label',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Es scheint, als hätten Sie viele solcher Anfragen — was bräuchten Sie, damit Sie sich sicher fühlen mich weiterzuleiten?',
            'objection_type': 'gatekeeper_voss_label',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        # ── Button 4: Vornamen-Pause (Source: Martin Limbeck — Pattern-Interrupt) — 2 Varianten
        {
            'user_id': 1,
            'text': '{vorname} ... (Pause) ... ich brauche genau zwei Minuten.',
            'objection_type': 'gatekeeper_vornamen_pause',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
        {
            'user_id': 1,
            'text': 'Ist denn der {vorname} ... der {vorname} {nachname} im Hause?',
            'objection_type': 'gatekeeper_vornamen_pause',
            'mode': 'gatekeeper',
            'quality_tier': 'A',
        },
    ])


def downgrade() -> None:
    # Seed-Daten loeschen vor Schema-Aenderung
    op.execute("DELETE FROM phrases WHERE mode = 'gatekeeper' AND objection_type LIKE 'gatekeeper_%'")
    # CHECK-Constraint via batch_alter_table entfernen (SQLite-safe)
    with op.batch_alter_table('phrases') as batch_op:
        try:
            batch_op.drop_constraint('ck_phrases_mode', type_='check')
        except Exception:
            pass  # Constraint existiert nicht (idempotent)
    op.drop_column('phrases', 'mode')
