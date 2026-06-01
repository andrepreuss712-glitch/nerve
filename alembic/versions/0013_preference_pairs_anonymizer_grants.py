"""Add training.preference_pairs (DPO foundation) + extend nerve_anon_worker grants
(write training, column-stamp crm) + worker-targeted PERMISSIVE RLS policies on
crm.account_memory (cross-tenant read + anonymized_at stamp).

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-01

Phase 08.23.2.G-MEET — Wave 3 (Training-Schema completion + Anonymizer-Worker).

W-6 SCOPE BOUNDARY (explicit, NOT a silent reduction): training.preference_pairs is
CREATED here as the DPO-triple sink (prompt/chosen/rejected) but is POPULATED by Phase
08.23.2.E (the DPO consumer that owns the crm-row -> DPO-triple mapping, which is not yet
specified). The Wave-3 worker (scripts/anonymizer_worker.py) writes training.transcript_archive
and stamps crm.account_memory.anonymized_at (Variante A); it does NOT write preference_pairs.
The INSERT grant on preference_pairs is provisioned NOW so Phase E needs no further migration.

EXTEND, NEVER RECREATE (PROVEN, pre-execute audit + execute STEP-0 HARD GATE 2026-06-01,
psql as postgres on Production): the `training` schema, the `nerve_anon_worker` role, and
`training.transcript_archive` ALREADY EXIST (migrations 0008/0009); `training.preference_pairs`
is ABSENT. This migration therefore does NOT `CREATE SCHEMA training`, does NOT `CREATE ROLE`,
and does NOT recreate transcript_archive. The only `CREATE SCHEMA IF NOT EXISTS` in this whole
phase is for `crm` (Plan 02 / migration 0012). On any STEP-0 mismatch the execute task HARD-STOPS
before this migration is written.

PG 16.14 (proven Plan 01 Task 0 / A3, re-confirmed STEP-0): gen_random_uuid() is core/built-in
(since PG 13). No pgcrypto/uuid-ossp extension and no version branch needed. preference_pairs
uses a UUID PK -> no sequence (0009's ALTER DEFAULT PRIVILEGES already covers any future training
sequence regardless).

MIGRATION ORDERING (explicit): 0013 chains AFTER 0012 (down_revision='0012'). By the time 0013
runs, crm.account_memory AND its base `tenant_isolation` policy (created in 0012, amended to the
nullif fail-closed form) already exist. The two worker policies added here STACK on top of that
existing table+policy. They live in 0013 (not 0012) because they are a WORKER concern and pair
with the worker grant in this same migration -- keeping `GRANT UPDATE (anonymized_at)` next to the
two anon_worker_* policies makes the worker's full crm-access surface auditable in one place.

WORKER RLS RESOLUTION (D-15/D-16, PINNED in DDL -- not deferred to the executor):
The 0012 `tenant_isolation` policy is PERMISSIVE with NO `TO`/`FOR` clause, so it applies to
nerve_anon_worker too. The worker (rolbypassrls=f proven, non-owner) sets NO app.tenant_id, so
its predicate is NULL -> FALSE -> it would SELECT 0 unstamped rows AND its anonymized_at-stamp
UPDATE would be blocked by USING/WITH CHECK (stamping 0 rows -> re-processing forever). D-16 makes
nerve_anon_worker the ONE role that reads crm CROSS-TENANT to anonymize and stamps anonymized_at.
We add two role-targeted PERMISSIVE policies on crm.account_memory so the worker's effective row
set becomes `tenant_isolation(FALSE) OR anon_worker_*(TRUE)` = all rows cross-tenant (PERMISSIVE
policies combine with OR). They are `TO nerve_anon_worker` ONLY -- nerve_app is NOT in the TO list,
so nerve_app stays tenant-scoped via the unchanged tenant_isolation policy (no leak). FORCE RLS
stays on for everyone. The base tenant_isolation policy is NOT modified/dropped/recreated.

Two independent controls bound the worker write: the column-level GRANT UPDATE (anonymized_at)
bounds WHICH columns (only the stamp -- never meddpicc/context_hooks/cleartext); the anon_worker_stamp
policy's WITH CHECK(true) only lifts the RLS ROW-predicate, it does NOT broaden the column surface.

NO FK crm<->training (D-17). NO raw crm ids stored in training (source_call_hash is a one-way hash).

Runs as postgres on Production. All identifiers ASCII (CLAUDE.md German-Umlaut rule).
"""
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── training.preference_pairs (DPO foundation; CREATED here, POPULATED by Phase 08.23.2.E) ──
    # UUID PK -> no sequence. NO FK to crm (D-17): source_call_hash is a one-way hash, not call_id.
    # gen_random_uuid() is core on PG 16.14 (proven) -- no extension, no version branch.
    op.execute("""
        CREATE TABLE IF NOT EXISTS training.preference_pairs (
            pair_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            prompt             JSONB NOT NULL,
            chosen             JSONB NOT NULL,
            rejected           JSONB NOT NULL,
            batch_id           UUID NOT NULL,
            anonymizer_version TEXT NOT NULL,
            source_call_hash   TEXT,                 -- HASH not call_id (no FK across the wall, D-17)
            labeller           TEXT,
            rating_chosen      SMALLINT,
            rating_rejected    SMALLINT,
            rationale          TEXT,
            split              TEXT CHECK (split IN ('train', 'val', 'test')),
            schema_version     SMALLINT NOT NULL DEFAULT 1,
            created_at         TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_preference_pairs_batch "
               "ON training.preference_pairs(batch_id)")

    # ── Grant extension (EXTEND existing nerve_anon_worker — write training, column-stamp crm) ──
    # preference_pairs INSERT provisioned NOW so Phase E needs no further grant migration; the
    # Wave-3 worker itself does not INSERT preference_pairs (it writes transcript_archive, Task 3).
    op.execute("GRANT INSERT, SELECT ON training.preference_pairs TO nerve_anon_worker")
    # crm read already granted in 0012 (ALTER DEFAULT PRIVILEGES SELECT ON TABLES). Add ONLY the
    # column-level UPDATE for the Variante A stamp -- the worker physically cannot mutate any other
    # crm column (meddpicc/context_hooks/cleartext stay untouchable). T-G3-02.
    op.execute("GRANT UPDATE (anonymized_at) ON crm.account_memory TO nerve_anon_worker")

    # ── Worker-targeted PERMISSIVE RLS policies on crm.account_memory (D-15/D-16, T-G3-07) ──
    # They stack OR on top of the unchanged 0012 tenant_isolation policy. TO nerve_anon_worker ONLY,
    # so nerve_app keeps its tenant-scoped access (no leak). The base tenant_isolation policy
    # (PERMISSIVE, no TO/FOR, USING + WITH CHECK on the nullif fail-closed predicate) is untouched.
    op.execute("""
        CREATE POLICY anon_worker_read ON crm.account_memory
          FOR SELECT TO nerve_anon_worker USING (true)
    """)
    op.execute("""
        CREATE POLICY anon_worker_stamp ON crm.account_memory
          FOR UPDATE TO nerve_anon_worker USING (true) WITH CHECK (true)
    """)


def downgrade() -> None:
    # Reverse, symmetric. Do NOT touch the 0012 tenant_isolation policy, the training schema,
    # the nerve_anon_worker role, or transcript_archive -- they predate this migration.
    op.execute("DROP POLICY IF EXISTS anon_worker_stamp ON crm.account_memory")
    op.execute("DROP POLICY IF EXISTS anon_worker_read ON crm.account_memory")
    op.execute("REVOKE UPDATE (anonymized_at) ON crm.account_memory FROM nerve_anon_worker")
    op.execute("REVOKE INSERT, SELECT ON training.preference_pairs FROM nerve_anon_worker")
    op.execute("DROP INDEX IF EXISTS training.idx_preference_pairs_batch")
    op.execute("DROP TABLE IF EXISTS training.preference_pairs")
