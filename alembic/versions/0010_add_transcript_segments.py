"""Add public.transcript_segments + deferred nerve_anon_worker GRANT.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-30

Phase 08.23.2.D.UX.1 — Bug A foundation. Creates the transcript_segments table whose
absence was the Bug-A root cause (code read a nonexistent log_entries column). Also adds
the GRANT SELECT on public.transcript_segments to nerve_anon_worker that 0008/0009 deferred.
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.transcript_segments (
            id                  BIGSERIAL   PRIMARY KEY,
            conversation_log_id INTEGER     NOT NULL
                                REFERENCES conversation_logs(id) ON DELETE CASCADE,
            ts_ms               INTEGER     NOT NULL,
            speaker             TEXT        NOT NULL
                                CHECK (speaker IN ('berater', 'kunde', 'system')),
            text                TEXT        NOT NULL,
            created_at          TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_transcript_segments_conv_ts "
        "ON public.transcript_segments (conversation_log_id, ts_ms)"
    )
    # Production: alembic laeuft als postgres (nerve_app hat KEIN CREATE auf schema public,
    # has_schema_privilege=f). Damit der App-User die Tabelle lesen/schreiben kann wie alle
    # anderen public-Tabellen (calls, conversation_logs sind nerve_app-owned), wird die
    # Tabelle + ihre BIGSERIAL-Sequence dem App-User zugewiesen (Eigentuemer-Konsistenz).
    op.execute("ALTER TABLE public.transcript_segments OWNER TO nerve_app")
    # GRANT deferred from 0008/0009 (0009 docstring). DA-06: worker reads public, writes training.* -> SELECT only.
    # F3 (Cross-AI): no sequence grant — nerve_anon_worker is SELECT-only on public.transcript_segments; it never calls nextval.
    op.execute("GRANT SELECT ON public.transcript_segments TO nerve_anon_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON public.transcript_segments FROM nerve_anon_worker")
    op.execute("DROP INDEX IF EXISTS idx_transcript_segments_conv_ts")
    op.execute("DROP TABLE IF EXISTS public.transcript_segments")
