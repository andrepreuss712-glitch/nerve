"""Phase 08.23.2.AUTH-2 Plan 01 — Fundament der Onboarding-Weiche.

Legt users.onboarding_state (TEXT, pending/done/skipped) + users.skip_onboarding
(boolean, Default FALSE) an. Backfillt ALLE Bestands-User sofort auf 'done'
(Anti-Block-C, D-07 — kein Zwangs-Onboarding fuer Bestand). Setzt einen
CHECK-Constraint als D-09-Tueroeffner. Traegt Postgres-Schilder (COMMENT ON COLUMN)
und markiert users.onboarding_done als [DEPRECATED] (EINGEFROREN, nicht gedroppt).

★ EXPAND/CONTRACT Schritt 1a (Finding 1): database/models.py wird in DIESEM Plan
UNANGETASTET gelassen. Grund: routes/auth.py:51 macht bei jedem login_required-Request
db.get(User, ...) = SELECT * auf users. Wuerde models.py die neue Spalte kennen
UND deploy.sh (deploy.sh:247 restartet Prod) die App neustarten, BEVOR diese Migration
auf Prod lief -> Login-Crash "column onboarding_state does not exist". Deshalb:
erst die DATEI + der Guard live (alter ORM kennt onboarding_state nicht -> sicher).
ORM-Spalten + app.py kommen in Plan 03 (Schritt 1c), NACH der manuellen Prod-Migration
(Plan 02, Schritt 1b).

Prod-Ist-Stand (verifiziert ssh 2026-07-08): alembic_version=0030; 3 users
(onboarding_done f=1/t=2); onboarding_state + skip_onboarding NICHT vorhanden.
0031 = reine COMMENT-Migration (idempotent); 0030->0031->0032 gefahrlos zusammen.

down_revision = '0031'

Revision ID: 0032
Revises: 0031
"""
from alembic import op
import sqlalchemy as sa

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade():
    # ── Schritt 1: onboarding_state erst nullable anlegen (Backfill greift) ───────────────
    op.add_column(
        'users',
        sa.Column('onboarding_state', sa.Text(), nullable=True, server_default='pending'),
    )

    # ── Schritt 2: ALLE Bestands-User auf 'done' setzen (Anti-Block-C, D-07) ─────────────
    # Kein Zwangs-Onboarding fuer existierende User — sie gelten als bereits fertig.
    op.execute("UPDATE users SET onboarding_state = 'done'")

    # ── Schritt 3: jetzt gefahrlos NOT NULL setzen (kein NULL mehr vorhanden) ─────────────
    op.alter_column('users', 'onboarding_state', nullable=False)

    # ── Schritt 4: CHECK-Constraint (D-09 Tueroeffner) ────────────────────────────────────
    # D-09 Tueroeffner: die Weiche liest 'pending' = alles ausser done/skipped. Der spaetere
    # Voll-Wizard darf step_*-Zwischenzustaende per CHECK-ERWEITERUNG (neue Werte in die
    # IN-Liste) ergaenzen, OHNE die Weiche anzufassen -- pending bleibt der Default/Sammelzustand.
    op.create_check_constraint(
        'ck_users_onboarding_state',
        'users',
        "onboarding_state IN ('pending','done','skipped')",
    )

    # ── Schritt 5: skip_onboarding (D-08 Interlock-Blocker S4) ───────────────────────────
    op.add_column(
        'users',
        sa.Column(
            'skip_onboarding',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # ── Schritt 6: Schilder (Punkt 23, COMMENT ON COLUMN) ────────────────────────────────
    op.execute(
        "COMMENT ON COLUMN users.onboarding_state IS "
        "'Onboarding-Fortschritt der Weiche post_login_destination "
        "(pending|done|skipped; CHECK ck_users_onboarding_state, erweiterbar um step_* "
        "ohne Weichen-Aenderung, D-09). Neue Wahrheitsquelle statt onboarding_done. "
        "Status: lebt (ab AUTH-2). "
        "Schreibt routes/onboarding.py (Erstprofil-Submit/Skip) + DB-Default pending bei Anlage; "
        "liest routes/auth.py + routes/oauth.py (post_login_destination).'"
    )

    op.execute(
        "COMMENT ON COLUMN users.skip_onboarding IS "
        "'Founder/Support-Schalter: ueberspringt NUR das Onboarding (Stufe 1 der Weiche), "
        "NICHT das Billing (das laeuft ueber organisations.skip_billing, AUTH-3/4). "
        "Status: Foundation -- Setz-UI kommt AUTH-4, hier nur Spalte + Leser. "
        "Schreibt (spaeter) AUTH-4 Flask-Admin; "
        "liest routes/auth.py + routes/oauth.py (post_login_destination Stufe 1).'"
    )

    # ── Schritt 7: onboarding_done DEPRECATED-Marker (D-06, EINGEFROREN, nicht gedroppt) ─
    # onboarding_done hat noch aktive Leser (auth.py:109/:147, oauth.py:100/:108).
    # Drop erst nach grep-Beleg 0 Leser (Zombie-Regel Punkt 23/29).
    op.execute(
        "COMMENT ON COLUMN users.onboarding_done IS "
        "'[DEPRECATED ab AUTH-2 -- EINGEFROREN, nicht droppen] "
        "Abgeloest durch users.onboarding_state. "
        "Noch aktive LESER (kein neuer Schreiber): "
        "routes/auth.py (_login_user liest, _create_org_and_user setzt False), "
        "routes/oauth.py. "
        "Drop erst nach grep-Beleg 0 Leser (Zombie-Regel Punkt 23/29).'"
    )


def downgrade():
    # ── onboarding_done DEPRECATED-Schild zuruecksetzen ──────────────────────────────────
    op.execute(
        "COMMENT ON COLUMN users.onboarding_done IS "
        "'Flag: Onboarding abgeschlossen'"
    )

    # ── skip_onboarding droppen ───────────────────────────────────────────────────────────
    op.drop_column('users', 'skip_onboarding')

    # ── CHECK-Constraint droppen ──────────────────────────────────────────────────────────
    op.drop_constraint('ck_users_onboarding_state', 'users', type_='check')

    # ── onboarding_state droppen ──────────────────────────────────────────────────────────
    op.drop_column('users', 'onboarding_state')
