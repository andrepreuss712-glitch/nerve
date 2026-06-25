"""Phase 08.23.2.TENANT-FOUND Plan 01 — Backfill calls.tenant_id (idempotent, set-based).

Reine DATEN-Migration (KEIN Schema-DDL: kein ALTER, kein NOT NULL, kein FK, kein RLS).
calls.tenant_id bleibt NULLABLE diese Runde (Live-Anlage-Schutz; NOT-NULL+FK = Phase F).

Setzt fuer ALLE calls mit tenant_id IS NULL den korrekten Mandanten ueber den eindeutigen
Join user->org->tenant_orgs (prod 2026-06-25: 37/37 auflösbar, §6). fail-closed by construction:
NUR was eindeutig per Join aufloest wird gesetzt — KEIN Default-Tenant (ein Default zoege fremde
Calls unter einen falschen Mandanten = DSGVO-Leck). Nicht-aufloesbare Calls bleiben NULL.

Idempotent: `WHERE tenant_id IS NULL` macht den zweiten Lauf zum No-Op (0 Rows).

DEPLOY-REIHENFOLGE (DEPLOY-CREATE-ALL-Lehre): diese Migration laeuft beaufsichtigt als postgres
VOR dem Gunicorn-Restart (deploy.sh-Gate). Reihenfolge 0022(editiert)->0023->0024 in EINEM Deploy.

Revision ID: 0023
Revises: 0022
"""
from alembic import op

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotenter set-based Backfill: nur NULL-Tenant-Calls, eindeutig per Join aufgeloest.
    # fail-closed by construction — KEIN Default-Tenant. Nicht-aufloesbare bleiben NULL. (§6)
    op.execute("""
        UPDATE calls c
        SET tenant_id = t.id
        FROM users u JOIN tenant_orgs t ON t.legacy_org_id = u.org_id
        WHERE c.user_id = u.id AND c.tenant_id IS NULL
    """)


def downgrade() -> None:
    # AUDIT-NOTE (Cross-AI Gemini Migration-Safety LOW #4): intentionaler No-Op.
    # Daten-verlust-frei + reversibel-trivial: tenant_id ist jederzeit aus user_id
    # rekonstruierbar (user->org->tenant_orgs). Ein Downgrade stellt den exakten
    # Vorzustand (welche Rows NULL waren) NICHT wieder her — bewusst akzeptiert, weil
    # kein Schema geaendert wird und die Zuordnung deterministisch reproduzierbar ist.
    pass
