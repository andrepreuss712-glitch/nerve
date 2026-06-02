"""Add crm.user_preferences (per-user meeting-save opt-in) with Row-Level-Security
(ENABLE + FORCE, USING + WITH CHECK, nullif-fail-closed) + tenant index + tenant/user UNIQUE.
PLUS MM-05: UNIQUE(tenant_id, name) on crm.accounts (atomic double-submit guard).

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-02

Phase 08.23.2.G-MEET — Meeting-Modal-Increment (Plan 04, Backend).

Runs as postgres on Production (nerve_app has no CREATE on the crm schema). owner=postgres ->
RLS engages for the restricted nerve_app role (rolbypassrls=f, non-owner). nerve_app gets DML
on this NEW table AUTOMATICALLY via the ALTER DEFAULT PRIVILEGES from 0012:57-58
(`FOR ROLE postgres IN SCHEMA crm GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO nerve_app`)
=> nerve_app=arwd without any explicit GRANT here.

NO `GRANT` and NO `ALTER TABLE crm.user_preferences OWNER TO nerve_app` (Research §0.3): making
nerve_app the owner would let it BYPASS RLS. The default-ACL grants DML, not ownership.

RLS policy uses the proven nullif-fail-closed form (0012:138-146 amendment): a transaction-local
GUC set via set_config('app.tenant_id', uuid, true) on the SQLAlchemy after_begin hook reverts to
EMPTY STRING '' on later transactions of a pooled connection; nullif(...,'') maps both never-set
(NULL) and reverted-empty ('') to NULL -> NULL::uuid -> predicate false -> 0 rows (fail-closed).

All identifiers ASCII (CLAUDE.md German-Umlaut rule — DB columns ohne Umlaute).
"""
from alembic import op

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── crm.user_preferences (born tenant_id NOT NULL, FK -> public.tenant_orgs is allowed; NOT the wall) ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm.user_preferences (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),   -- gen_random_uuid: core on PG 16.14
            tenant_id         UUID NOT NULL REFERENCES public.tenant_orgs(id),
            user_id           INTEGER NOT NULL,                             -- soft link public.users.id, NO FK (D-08)
            auto_save_meeting BOOLEAN NOT NULL DEFAULT false,               -- DSGVO opt-in OFF by default (Art. 25 Abs. 2)
            schema_version    SMALLINT NOT NULL DEFAULT 1,
            created_at        TIMESTAMPTZ DEFAULT now(),
            updated_at        TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_user_preferences_tenant_user UNIQUE (tenant_id, user_id)
        )
    """)
    op.execute("ALTER TABLE crm.user_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crm.user_preferences FORCE ROW LEVEL SECURITY")   # belt-and-suspenders (D-12.4)
    op.execute("""
        CREATE POLICY tenant_isolation ON crm.user_preferences
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_tenant ON crm.user_preferences(tenant_id)")

    # ── MM-05 (Cross-AI): atomare Doppel-Submit-Sicherung auf crm.accounts. Tabelle ist neu/near-empty
    # (Research §0.5) -> UNIQUE sicher nachruestbar ohne Backfill-Konflikt. DO-Block-guarded (idempotent re-run). ──
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_accounts_tenant_name'
          ) THEN
            ALTER TABLE crm.accounts ADD CONSTRAINT uq_accounts_tenant_name UNIQUE (tenant_id, name);
          END IF;
        END $$;
    """)


def downgrade() -> None:
    # Reverse, symmetric. No GRANT / OWNER to restore -- none were set.
    op.execute("ALTER TABLE crm.accounts DROP CONSTRAINT IF EXISTS uq_accounts_tenant_name")
    op.execute("DROP INDEX IF EXISTS crm.idx_user_preferences_tenant")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON crm.user_preferences")
    op.execute("DROP TABLE IF EXISTS crm.user_preferences")
