"""Quick-Fix — audit_log Immutability-Trigger in Postgres-Syntax (DSGVO-/Tamper-Schutz).

BUG (klare Ursache): der App-Start-Block (app.py ~1330-1350) schrieb den Trigger in SQLite-Dialekt
(`CREATE TRIGGER IF NOT EXISTS ... BEGIN SELECT RAISE(ABORT,...) END`) -> Postgres wirft bei JEDEM
Boot `syntax error at or near "NOT"` (non-fatal gefangen) -> 0 Trigger auf prod.audit_log
(`pg_trigger` == 0 rows, Tabelle aber 948 echte Zeilen). audit_log war damit NICHT UPDATE/DELETE-
gesperrt -> Defense-in-Depth/DSGVO-Tamper-Schutz fehlte still.

BAU-ENTSCHEIDUNG: der Trigger gehoert in eine Migration (als postgres ausgefuehrt), NICHT in den
App-Start — der App-Start laeuft als `nerve_app` und ist nicht zwingend Owner von audit_log
(CREATE TRIGGER braucht Owner-Recht). Muster wie 0011 (mk_tenant_org) / die RLS-Migrationen.
Hinweis: Trigger feuern AUCH fuer den Tabellen-Owner (anders als RLS ohne FORCE) -> die Sperre
greift unabhaengig von der Rolle.

Idempotent: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS + CREATE TRIGGER.
create_all-Falle: Migration von Hand als postgres VOR Restart (deploy.sh macht keine Prod-Migration),
Muster wie 0020-0025.

Revision ID: 0026
Revises: 0025
"""
from alembic import op

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard-Funktion: jeder UPDATE/DELETE auf audit_log wird hart abgelehnt (Unveraenderlichkeit).
    # Reines RAISE EXCEPTION -> keine Privilegien-Eskalation noetig -> SECURITY INVOKER (Default).
    # Die Message ('audit_log is immutable') ist der vom Regressions-Test gematchte Beleg.
    op.execute("""
        CREATE OR REPLACE FUNCTION public.audit_log_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_log is immutable';
        END; $$
    """)
    # Idempotenz: alten Trigger droppen, dann EINEN Trigger fuer UPDATE+DELETE neu anlegen.
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON public.audit_log")
    op.execute("""
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON public.audit_log
        FOR EACH ROW EXECUTE FUNCTION public.audit_log_immutable()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON public.audit_log")
    op.execute("DROP FUNCTION IF EXISTS public.audit_log_immutable()")
