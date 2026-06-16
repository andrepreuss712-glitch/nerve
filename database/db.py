import os
import contextvars
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, scoped_session

# Resolve relative SQLite paths relative to project root
_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')

if _DATABASE_URL.startswith('sqlite:///') and not _DATABASE_URL.startswith('sqlite:////'):
    _rel = _DATABASE_URL[len('sqlite:///'):]
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _abs  = os.path.join(_root, _rel)
    os.makedirs(os.path.dirname(_abs), exist_ok=True)
    _DATABASE_URL = f'sqlite:///{_abs}'

_connect_args = {'check_same_thread': False} if 'sqlite' in _DATABASE_URL else {}
engine = create_engine(_DATABASE_URL, connect_args=_connect_args)

# ── Enable WAL mode for SQLite (concurrent reads + writes under threading) ─────
if 'sqlite' in _DATABASE_URL:
    @event.listens_for(engine, 'connect')
    def set_wal_mode(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()

# ── Phase 08.23.2.PGTEST (Req-6): SQLite-crm/training-ATTACH-Emulation ENTFERNT ────────────────
# Frueher registrierte hier ein globaler @event.listens_for(Engine,"connect")-Listener
# (_sqlite_attach_crm_training_schemas, cf5de6d) pro SQLite-Verbindung In-Memory-DBs crm/training,
# damit schema-qualifiziertes create_all/Queries der crm.*/training.*-Modelle gegen SQLite aufloesten.
# Das war ein reines Test-Emulations-Pflaster (False-Green-Risiko: RLS/Schema-Semantik existiert in
# SQLite NICHT). Mit dem echten Postgres-Test-Gate (nerve_test, deploy.sh) sind die crm/training-Tests
# auf echtes PG portiert -> die Emulation ist toter Pfad und entfernt. Postgres in Produktion ist
# unberuehrt (echte Schemas). Der WAL-Hook oben (Modul-Engine, sqlite-geguardet) bleibt: er ist im
# PG-Gate inert (nie registriert) und schuetzt die genuine lokale Dev-SQLite ausserhalb der Tests —
# KEIN Req-6-Emulations-Ziel.

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)


# ── Phase 08.23.2.G-MEET Wave 2 — Multi-Tenant RLS GUC plumbing (D-11, D-12.1, D-12.3) ──
# The crm.* RLS policies filter on current_setting('app.tenant_id', true)::uuid. We publish the
# request/thread tenant UUID into a contextvar, and a SQLAlchemy Session `after_begin` hook issues
# a TRANSACTION-LOCAL set_config('app.tenant_id', <uuid>, true) at transaction start. Because the
# SET fires when the transaction begins (BEFORE its queries), the SET and the tenant-scoped queries
# share ONE transaction by construction (fixes B-1 connection-affinity). set_config(...,true) is
# SET LOCAL: it clears AUTOMATICALLY at COMMIT/ROLLBACK -> NO checkin RESET needed, pooler-agnostic
# (immune if a pooler is ever added, e.g. 08.23.2.STAGING), and safe for out-of-request worker
# threads (the GUC lives only for the worker's own transaction).
_current_tenant_id = contextvars.ContextVar("nerve_tenant_id", default=None)


def set_current_tenant(tid):
    """Publish the active tenant UUID (string) for the current request/thread.

    Called from before_request (request path) AND by any worker thread before its session work
    (so the after_begin hook can issue the transaction-local SET on the worker's own transaction).
    """
    _current_tenant_id.set(tid)


def clear_current_tenant():
    """Reset the contextvar (hygiene). The actual tenant control is the transaction-local SET,
    which auto-clears at COMMIT/ROLLBACK -- this only prevents the contextvar surviving into the
    next request on a reused thread."""
    _current_tenant_id.set(None)


# Postgres-only: SQLite has no set_config / RLS, so the in-memory test schema is unaffected
# (inverse of the SQLite WAL hook above).
if 'sqlite' not in _DATABASE_URL:
    @event.listens_for(SessionLocal, "after_begin")
    def _set_tenant_txn_local(session, transaction, connection):
        # Fires when a transaction begins, BEFORE its queries, on the SAME connection
        # => the GUC is transaction-local for exactly the queries that follow.
        tid = _current_tenant_id.get()
        if not tid:
            # No tenant context (pre-login / static / worker w/o tenant) -> GUC unset
            # -> current_setting('app.tenant_id', true) is NULL -> RLS fails closed (0 rows).
            return
        # Third arg true = transaction-local (SET LOCAL). PARAMETERIZED (bound param) ->
        # SQL-injection-safe (T-G2-05): never f-string/%-format the UUID into SQL.
        # NOTE: NO `RESET app.tenant_id` / checkin listener exists -- transaction-local
        # auto-clears at COMMIT/ROLLBACK, so a returned/reused connection carries no residual
        # tenant GUC (T-G2-03 solved by construction).
        connection.exec_driver_sql(
            "SELECT set_config('app.tenant_id', %s, true)", (str(tid),)
        )


class Base(DeclarativeBase):
    pass


# Alias so routes can do: from database.db import db
db = Base


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_session():
    """Returns a new DB session (for use outside request context)."""
    return SessionLocal()
