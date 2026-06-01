"""Add crm schema + grants + 4 tenant-scoped tables (accounts/contacts/account_memory/meetings)
with Row-Level-Security (ENABLE + FORCE, USING + WITH CHECK, current_setting missing_ok) +
tenant indexes + FK-column indexes.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-01

Phase 08.23.2.G-MEET — Wave 2 (CRM-Schema + RLS + Meeting-data layer).

This is where multi-tenant CUSTOMER data first exists and is protected. RLS only matters once
there is a tenant-scoped table to protect — that is Wave 2 (resolving the D-03/D-10 "RLS ab
Welle 1" ordering tension). Ships as a clean independently-deployable state on top of Wave 1's
tenant_orgs (the FK target).

# PG 16.14 verified (pre-execute audit 2026-06-01, re-confirmed at execute STEP-0 gate) --
# gen_random_uuid() is core/built-in (since PG 13). No pgcrypto/uuid-ossp extension and no
# version branch needed anywhere below.

RLS ENGAGEMENT (RESOLVED -- no role mutation needed):
  nerve_app is PROVEN rolbypassrls=f (psql as postgres, audit 2026-06-01, re-confirmed STEP-0)
  and is a NON-OWNER of the crm tables (they are postgres-owned; nerve_app gets DML via
  ALTER DEFAULT PRIVILEGES only). Postgres bypasses RLS ONLY for the table OWNER or a
  BYPASSRLS/superuser role -- nerve_app is neither, so RLS engages automatically.
  Therefore this migration emits:
    - NO `ALTER ROLE nerve_app NOBYPASSRLS`           (it is already false)
    - NO `ALTER ROLE nerve_app SET search_path = ...`  (rolconfig is EMPTY by design; the ORM
                                                         schema-qualifies via {'schema':'crm'} instead, Task 2)
  We KEEP `FORCE ROW LEVEL SECURITY` per crm table belt-and-suspenders: if a future migration
  ever flips ownership to nerve_app, FORCE keeps RLS active for the owner too (D-12.4).

OWNER SPLIT (load-bearing for D-16): crm tables are postgres-owned. We do NOT
`ALTER TABLE crm.* OWNER TO nerve_app` (inverse of 0010's public-table choice). nerve_app gets
DML via ALTER DEFAULT PRIVILEGES but NOT ownership => it does not bypass RLS.

Runs as postgres on Production (nerve_app has no CREATE on most schemas).
All identifiers ASCII (CLAUDE.md German-Umlaut rule -- DB columns / JSONB keys ohne Umlaute).
"""
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


# crm tables created in this migration. Order matters for FK dependency:
# accounts -> contacts -> account_memory -> meetings.
_CRM_TABLES = ('accounts', 'contacts', 'account_memory', 'meetings')


def upgrade() -> None:
    # ── Step A: schema + grants (MIRROR proven 0008/0009 pattern, RESEARCH §5) ──
    op.execute("CREATE SCHEMA IF NOT EXISTS crm")
    op.execute("GRANT USAGE ON SCHEMA crm TO nerve_app")
    # D-18.2 critical: DML on FUTURE crm tables created by postgres flows to nerve_app.
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nerve_app")
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "GRANT USAGE, SELECT ON SEQUENCES TO nerve_app")
    # Worker read side of the wall (Wave 3 anonymizer reads crm as nerve_anon_worker).
    op.execute("GRANT USAGE ON SCHEMA crm TO nerve_anon_worker")
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "GRANT SELECT ON TABLES TO nerve_anon_worker")
    # NOTE (D-18.1 superseded): the original plan added
    #   ALTER ROLE nerve_app SET search_path = crm, public
    # The audit proved rolconfig is EMPTY and there is no role-search_path. The crm tables are
    # schema-qualified in the ORM ({'schema':'crm'}, Task 2) instead. NO role search_path here.

    # ── Step B: 4 tables (born with tenant_id NOT NULL, in crm) ──
    # FK to public.tenant_orgs is allowed (NOT the crm/training wall, D-17).
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm.accounts (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),   -- gen_random_uuid: core on PG 16.14
            tenant_id   UUID NOT NULL REFERENCES public.tenant_orgs(id),
            name        TEXT NOT NULL,
            domain      TEXT,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm.contacts (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES public.tenant_orgs(id),
            account_id  UUID REFERENCES crm.accounts(id),
            name        TEXT NOT NULL,
            email       TEXT,
            phone       TEXT,
            created_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    # account_memory: MEDDPICC (8 ASCII JSONB keys) + context_hooks + last_call_summary.
    # anonymized_at (Variante A state-tracking, consumed by Wave 3 anonymizer).
    # CHECK: at least one of account_id / contact_id present.
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm.account_memory (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         UUID NOT NULL REFERENCES public.tenant_orgs(id),
            account_id        UUID REFERENCES crm.accounts(id),
            contact_id        UUID REFERENCES crm.contacts(id),
            schema_version    SMALLINT NOT NULL DEFAULT 1,
            meddpicc          JSONB NOT NULL DEFAULT '{}',
            context_hooks     JSONB NOT NULL DEFAULT '[]',
            last_call_summary TEXT,
            anonymized_at     TIMESTAMPTZ,
            updated_at        TIMESTAMPTZ DEFAULT now(),
            CHECK (account_id IS NOT NULL OR contact_id IS NOT NULL)
        )
    """)
    # meetings.call_id is a deliberate SOFT link to public.calls.id (a bare UUID column, NO
    # foreign key) per D-08 -- the calls FK is deferred; the crm wall stays decoupled from the
    # calls lifecycle (W-4 rationale).
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm.meetings (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      UUID NOT NULL REFERENCES public.tenant_orgs(id),
            account_id     UUID REFERENCES crm.accounts(id),
            contact_id     UUID REFERENCES crm.contacts(id),
            call_id        UUID,                       -- soft link to public.calls.id, NO FK (D-08)
            scheduled_at   TIMESTAMPTZ,
            notes          TEXT,
            schema_version SMALLINT NOT NULL DEFAULT 1,
            created_at     TIMESTAMPTZ DEFAULT now()
        )
    """)

    # ── Step C: RLS per table (D-12.4/.5/.6) + tenant index ──
    # current_setting('app.tenant_id', true) uses missing_ok=true. AMENDMENT 2026-06-01 (Claudian
    # gate + Cross-AI Gemini, reproduced live on PG 16.14): a custom GUC set transaction-locally on
    # a connection reverts to EMPTY STRING '' (NOT NULL) on that pooled connection's later
    # transactions. Bare current_setting(...)::uuid then evaluates ''::uuid -> ERROR "invalid input
    # syntax for type uuid" instead of fail-closing. nullif(...,'') maps BOTH the never-set (NULL)
    # and the reverted-empty ('') cases to NULL -> NULL::uuid -> predicate false -> 0 rows
    # (fail-closed, D-12.1). The GUC is set TRANSACTION-LOCAL via set_config(...,true) on the
    # SQLAlchemy Session after_begin hook (Task 3), so the SET and the tenant queries share ONE
    # transaction. (Non-UUID garbage would still throw ::uuid, but after_begin only ever writes
    # real UUIDs or None -> garbage cannot enter; nullif suffices, no try_cast needed -- Gemini.)
    for tbl in _CRM_TABLES:
        op.execute(f"ALTER TABLE crm.{tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE crm.{tbl} FORCE ROW LEVEL SECURITY")   # belt-and-suspenders (D-12.4)
        op.execute(f"""
            CREATE POLICY tenant_isolation ON crm.{tbl}
              USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
        """)                                                            # D-12.5 USING + WITH CHECK
        op.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_tenant ON crm.{tbl}(tenant_id)")  # D-12.6

    # ── Step C.2: FK-column indexes (Gemini SQL-layer review, MEDIUM "Missing FK indexes") ──
    # FK columns account_id/contact_id are otherwise UNINDEXED -> seq-scans on
    # WHERE account_id = ? / WHERE contact_id = ? and during cascade ops. B-tree each.
    op.execute("CREATE INDEX IF NOT EXISTS idx_account_memory_account_id ON crm.account_memory(account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_account_memory_contact_id ON crm.account_memory(contact_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meetings_account_id        ON crm.meetings(account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meetings_contact_id        ON crm.meetings(contact_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contacts_account_id        ON crm.contacts(account_id)")

    # ── Step C.3: GIN index on meddpicc JSONB (DDL/ORM parity with AccountMemory, Task 2) ──
    # Mirrors CallEvent's payload GIN index (models.py) -- supports containment queries on the
    # MEDDPICC keys. The ORM declares idx_account_memory_meddpicc_gin; keep the live DB in sync.
    op.execute("CREATE INDEX IF NOT EXISTS idx_account_memory_meddpicc_gin "
               "ON crm.account_memory USING gin (meddpicc)")


def downgrade() -> None:
    # Reverse, symmetric. No BYPASSRLS / search_path to restore -- none were set.
    op.execute("DROP INDEX IF EXISTS crm.idx_account_memory_meddpicc_gin")
    op.execute("DROP INDEX IF EXISTS crm.idx_account_memory_account_id")
    op.execute("DROP INDEX IF EXISTS crm.idx_account_memory_contact_id")
    op.execute("DROP INDEX IF EXISTS crm.idx_meetings_account_id")
    op.execute("DROP INDEX IF EXISTS crm.idx_meetings_contact_id")
    op.execute("DROP INDEX IF EXISTS crm.idx_contacts_account_id")

    for tbl in _CRM_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON crm.{tbl}")
        op.execute(f"DROP INDEX IF EXISTS crm.idx_{tbl}_tenant")

    # DROP in reverse FK-dependency order: meetings, account_memory, contacts, accounts.
    op.execute("DROP TABLE IF EXISTS crm.meetings")
    op.execute("DROP TABLE IF EXISTS crm.account_memory")
    op.execute("DROP TABLE IF EXISTS crm.contacts")
    op.execute("DROP TABLE IF EXISTS crm.accounts")

    # Revoke crm grants from both roles.
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "REVOKE SELECT ON TABLES FROM nerve_anon_worker")
    op.execute("REVOKE USAGE ON SCHEMA crm FROM nerve_anon_worker")
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "REVOKE USAGE, SELECT ON SEQUENCES FROM nerve_app")
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA crm "
               "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM nerve_app")
    op.execute("REVOKE USAGE ON SCHEMA crm FROM nerve_app")
    op.execute("DROP SCHEMA IF EXISTS crm")
