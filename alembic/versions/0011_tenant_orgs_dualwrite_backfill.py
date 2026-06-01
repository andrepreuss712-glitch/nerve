"""Add public.tenant_orgs (UUID tenancy root) + dual-write trigger + calls.tenant_id backfill.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-01

Phase 08.23.2.G-MEET — Wave 1 (Multi-Tenancy-Unterbau, UUID-Achse).

Lays tenant_orgs as a parallel register beside the live Integer org_id model, bridged by
legacy_org_id. Seeds one row per existing organisation, auto-creates future rows via an
AFTER INSERT trigger on organisations (Dual-Write, D-09 — covers all 3 org-creation sites
atomically), and backfills calls.tenant_id. CLEAN independently deployable state (D-02):
nothing in the request path reads tenant_orgs yet, so the app behaves exactly as before.

# PG 16.14 verified (pre-execute audit 2026-06-01, re-confirmed at execute) -- gen_random_uuid()
# is core/built-in (since PG 13). No pgcrypto/uuid-ossp extension and no version branch needed.

Runs as postgres on Production (nerve_app has no CREATE on schema public). New public table is
re-owned to nerve_app (0010:40 pattern) so the SECURITY INVOKER trigger fires as nerve_app and,
as the table owner, already has INSERT -- no SECURITY DEFINER / no privilege escalation.
"""
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. CREATE tenant_orgs. UNIQUE(legacy_org_id) is REQUIRED for the trigger's ON CONFLICT.
    #    gen_random_uuid() is core on PG 16.14 (verified, see module docstring) -- unconditional.
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.tenant_orgs (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            legacy_org_id INTEGER     NOT NULL UNIQUE REFERENCES public.organisations(id),
            name          TEXT        NOT NULL,
            created_at    TIMESTAMPTZ DEFAULT now()
        )
    """)
    # Owner-consistency (0010:40). LOAD-BEARING: nerve_app OWNS tenant_orgs, so the
    # SECURITY INVOKER trigger (running as nerve_app on an org INSERT) already has INSERT.
    op.execute("ALTER TABLE public.tenant_orgs OWNER TO nerve_app")

    # 2. SEED one row per existing organisation (idempotent via ON CONFLICT DO NOTHING).
    op.execute("""
        INSERT INTO public.tenant_orgs (id, legacy_org_id, name, created_at)
        SELECT gen_random_uuid(), o.id, o.name, now()
        FROM public.organisations o
        ON CONFLICT (legacy_org_id) DO NOTHING
    """)

    # 3. DUAL-WRITE trigger function + trigger (D-09). SECURITY INVOKER (the default) -- NOT
    #    SECURITY DEFINER (Gemini SQL-layer review Q1, HIGH): nerve_app owns tenant_orgs so the
    #    INSERT succeeds with no escalation; DEFINER would run the body as the postgres superuser
    #    on every org INSERT (gratuitous escalation). No SET search_path: a single STATIC INSERT
    #    with no dynamic SQL has no search_path-hijack surface for an INVOKER function.
    op.execute("""
        CREATE OR REPLACE FUNCTION public.mk_tenant_org() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER AS $$
        BEGIN
          INSERT INTO public.tenant_orgs (id, legacy_org_id, name, created_at)
          VALUES (gen_random_uuid(), NEW.id, NEW.name, now())
          ON CONFLICT (legacy_org_id) DO NOTHING;
          RETURN NEW;
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER trg_mk_tenant_org AFTER INSERT ON public.organisations
        FOR EACH ROW EXECUTE FUNCTION public.mk_tenant_org()
    """)

    # 4. BACKFILL calls.tenant_id (one-time UPDATE join). Column stays NULLABLE; no FK (D-05/D-08).
    op.execute("""
        UPDATE public.calls c
        SET tenant_id = t.id
        FROM public.users u
        JOIN public.tenant_orgs t ON t.legacy_org_id = u.org_id
        WHERE c.user_id = u.id
          AND c.tenant_id IS NULL
    """)

    # 5. POST-BACKFILL NULL-TENANT GUARD -- HARD RAISE (Gemini Q3, MEDIUM; Andre decision).
    #    The join is mathematically TOTAL (users.org_id NOT NULL + seed over ALL orgs immediately
    #    above in the SAME transaction), so any remaining NULL = a corrupted/orphan row. Fail the
    #    deploy loudly rather than ship silent orphans -- the whole upgrade() rolls back on RAISE.
    op.execute("""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.calls WHERE tenant_id IS NULL) THEN
            RAISE EXCEPTION 'Backfill failed: orphaned calls with NULL tenant_id';
          END IF;
        END $$;
    """)


def downgrade() -> None:
    # Reverse order, symmetric to 0008:54-63. The DO-block guard is a one-shot assertion inside
    # upgrade() -- nothing to reverse. Backfilled calls.tenant_id values are left as data.
    op.execute("DROP TRIGGER IF EXISTS trg_mk_tenant_org ON public.organisations")
    op.execute("DROP FUNCTION IF EXISTS public.mk_tenant_org()")
    op.execute("DROP TABLE IF EXISTS public.tenant_orgs")
