"""Phase 08.23.2.AUTH-EMAIL-VERIFY Plan 02 — email_confirmed DB-Default False (D-03b).

Flippt den DB-Column-Default von users.email_confirmed auf FALSE (belt-and-suspenders).
Fail-Open-Wurzel: die Prod-Spalte ist nullable OHNE DB-Default -> ein Insert ohne
expliziten Wert landet als NULL, und das (vor Plan 01) fail-open Gate liess NULL durch.
Diese Migration setzt den DB-Default, damit ein vergessener kuenftiger Creator FALSE
(gegatet) statt NULL (fail-open) schreibt.

Prod-Ist-Stand (verifiziert ssh 2026-07-09): alembic_version=0032; users.email_confirmed
data_type=boolean, is_nullable=YES, column_default=(leer/kein DB-Default); 3 Bestandskonten
id=1/2/3 alle email_confirmed=true; 0 NULL-Rows.

★ KEIN Backfill: 0 NULL-Rows aktuell, und die 3 Bestandskonten sind explizit true — ein
`UPDATE users SET email_confirmed=False` wuerde sie faelschlich gaten. Nur DDL (SET DEFAULT),
keine Row-Aenderung.

★ Laeuft ZULETZT (Wave 3, Reorder Finding 1): Plan 01 (fail-closed Gate) + Plan 03 (jeder
Anlage-Pfad setzt email_confirmed explizit: api_register=False, OAuth Google=True/MS=False,
Invite=True, seed=True) sind bereits live -> dieser Flip ist ein garantierter No-Op fuer alle
existierenden Pfade. Reine Zukunfts-Absicherung.

down_revision = '0032'

Revision ID: 0033
Revises: 0032
"""
from alembic import op
import sqlalchemy as sa

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade():
    # ── DB-Default auf FALSE (belt-and-suspenders, D-03b) ────────────────────────────────
    # Nur DDL — betrifft ausschliesslich KUENFTIGE Inserts ohne expliziten Wert.
    # KEIN Backfill-UPDATE: die 3 Bestandskonten (email_confirmed=true) bleiben unangetastet,
    # 0 NULL-Rows vorhanden. Ein UPDATE wuerde die true-Konten faelschlich flippen.
    op.alter_column('users', 'email_confirmed', server_default=sa.false())

    # ── Schild (Punkt 23, COMMENT ON COLUMN) — Aktualitaets-Pflicht: alle Leser/Schreiber ─
    op.execute(
        "COMMENT ON COLUMN users.email_confirmed IS "
        "'Email bestaetigt — das fail-closed login_required-Gate laesst nur True passieren "
        "(NULL/False gaten). Status: lebt. "
        "Schreibt routes/oauth.py (Microsoft=False, Google=True), "
        "routes/auth.py (api_register=False, confirm_email=True, invite=True), "
        "app.py + scripts/seed_test_user.py (seed=True), DB-Default False (Migration 0033); "
        "liest routes/auth.py login_required-Gate.'"
    )


def downgrade():
    # ── DB-Default zurueck auf TRUE ──────────────────────────────────────────────────────
    op.alter_column('users', 'email_confirmed', server_default=sa.true())

    # ── Schild zurueck auf den H-18-Text ─────────────────────────────────────────────────
    op.execute(
        "COMMENT ON COLUMN users.email_confirmed IS "
        "'Email bestaetigt (Microsoft-OAuth Hijacking-Mitigation, H-18)'"
    )
