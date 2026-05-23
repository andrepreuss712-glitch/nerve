"""seed cold_call phrases (re-seed after Phase 08.23.2.A bulk-delete)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-23

Phase 08.23.2.C.R.1: Production-DB hatte seit Bulk-DELETE in Phase 08.23.2.A
0 cold_call-Phrases. PiP im Cold-Call-Modus zeigte keine EWB-Buttons.

8 Standard-Einwand-Themen mit je 2-3 Antwort-Varianten.
user_id=1 (Admin-MVP, identisch mit 0003 Gatekeeper-Seed).
Idempotent: INSERT wird pro Phrase nur ausgefuehrt wenn text+objection_type
nicht bereits existiert.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLD_CALL_PHRASES = [
    # ── zu_teuer ──────────────────────────────────────────────────────────────
    {
        'objection_type': 'zu_teuer',
        'text': 'Was genau meinen Sie mit zu teuer — im Vergleich zu was?',
    },
    {
        'objection_type': 'zu_teuer',
        'text': 'Viele unserer Kunden dachten das anfangs auch — bis sie gerechnet haben, was der Status quo sie kostet. Darf ich Ihnen eine Zahl zeigen?',
    },
    {
        'objection_type': 'zu_teuer',
        'text': 'Das verstehe ich. Wenn wir die Investition auf die gewonnenen Aufträge herunterbrechen — rechnen Sie mit mir kurz: Was ist ein Auftrag bei Ihnen im Schnitt wert?',
    },
    # ── keine_zeit ────────────────────────────────────────────────────────────
    {
        'objection_type': 'keine_zeit',
        'text': 'Das respektiere ich. Wann wäre in den nächsten zwei Wochen ein Drei-Minuten-Fenster für Sie realistisch?',
    },
    {
        'objection_type': 'keine_zeit',
        'text': 'Gerade deshalb rufe ich an — wir sparen Vertriebsleitern wie Ihnen durchschnittlich vier Stunden pro Woche. Wann darf ich Ihnen zeigen wie?',
    },
    # ── kein_interesse ────────────────────────────────────────────────────────
    {
        'objection_type': 'kein_interesse',
        'text': 'Das höre ich häufig als Erstes. Darf ich fragen, was Sie in diesem Bereich schon ausprobiert haben?',
    },
    {
        'objection_type': 'kein_interesse',
        'text': 'Kein Interesse — an was genau? An dem Thema oder an der Lösung wie wir sie machen?',
    },
    # ── kein_budget ───────────────────────────────────────────────────────────
    {
        'objection_type': 'kein_budget',
        'text': 'Ist das eine Frage des Budgets generell, oder ist es aktuell nicht eingeplant?',
    },
    {
        'objection_type': 'kein_budget',
        'text': 'Wann planen Sie das Budget für das nächste Quartal? Dann würde ich mich genau zu dem Zeitpunkt melden.',
    },
    {
        'objection_type': 'kein_budget',
        'text': 'Viele unserer Kunden haben das Budget nicht eingeplant — und trotzdem umgesetzt, weil der ROI innerhalb von 90 Tagen sichtbar war. Darf ich Ihnen das kurz skizzieren?',
    },
    # ── schicken_sie_unterlagen ───────────────────────────────────────────────
    {
        'objection_type': 'schicken_sie_unterlagen',
        'text': 'Das mache ich gerne — damit ich Ihnen das Richtige schicke: Welches Thema brennt Ihnen aktuell am meisten unter den Nägeln?',
    },
    {
        'objection_type': 'schicken_sie_unterlagen',
        'text': 'Unterlagen schicke ich Ihnen zu. Nur damit die nicht im Spam landen: Wann schauen Sie kurz rein, und wen darf ich kopieren?',
    },
    # ── anderer_anbieter ──────────────────────────────────────────────────────
    {
        'objection_type': 'anderer_anbieter',
        'text': 'Gut zu wissen. Was schätzen Sie an Ihrem jetzigen Anbieter am meisten?',
    },
    {
        'objection_type': 'anderer_anbieter',
        'text': 'Den kenne ich. Was würde sich für Sie verändern, wenn die Zusammenarbeit besser laufen würde als heute?',
    },
    # ── brauche_bedenkzeit ────────────────────────────────────────────────────
    {
        'objection_type': 'brauche_bedenkzeit',
        'text': 'Selbstverständlich. Was genau möchten Sie noch durchdenken? Dann kann ich Ihnen gezielt helfen.',
    },
    {
        'objection_type': 'brauche_bedenkzeit',
        'text': 'Wann sprechen wir dann — Donnerstag oder Freitag diese Woche?',
    },
    # ── nicht_zustaendig ──────────────────────────────────────────────────────
    {
        'objection_type': 'nicht_zustaendig',
        'text': 'Wer wäre denn bei Ihnen die richtige Ansprechperson dafür?',
    },
    {
        'objection_type': 'nicht_zustaendig',
        'text': 'Verstehe. Darf ich fragen, wer das Thema verantwortet — damit ich direkt mit der richtigen Person spreche?',
    },
]

_SEED_OBJECTION_TYPES = {p['objection_type'] for p in _COLD_CALL_PHRASES}


def upgrade() -> None:
    conn = op.get_bind()
    inserted = 0
    for phrase in _COLD_CALL_PHRASES:
        existing = conn.execute(
            sa.text(
                "SELECT id FROM phrases WHERE objection_type = :ot AND text = :tx LIMIT 1"
            ),
            {'ot': phrase['objection_type'], 'tx': phrase['text']},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO phrases (user_id, text, objection_type, mode, quality_tier)"
                " VALUES (:uid, :tx, :ot, :mode, :qt)"
            ),
            {
                'uid': 1,
                'tx': phrase['text'],
                'ot': phrase['objection_type'],
                'mode': 'cold_call',
                'qt': 'A',
            },
        )
        inserted += 1
    print(f"[DB] Migration 0005: {inserted} cold_call phrases inserted (idempotent re-seed)")


def downgrade() -> None:
    # Loescht nur die Seed-Rows — User-generierte Phrasen mit gleichem
    # objection_type bleiben erhalten da sie anderen text haben.
    conn = op.get_bind()
    for phrase in _COLD_CALL_PHRASES:
        conn.execute(
            sa.text(
                "DELETE FROM phrases WHERE objection_type = :ot AND text = :tx AND mode = 'cold_call'"
            ),
            {'ot': phrase['objection_type'], 'tx': phrase['text']},
        )
