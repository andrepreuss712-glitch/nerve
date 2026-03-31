import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

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

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
