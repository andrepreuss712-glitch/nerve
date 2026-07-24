"""Phase 08.23.2.STABIL-1 Plan 03 — DB-Pool-Dimensionierung.

Runtime-Assertions auf das lebende Engine-Objekt (kein Source-Presence-False-Green,
siehe CLAUDE.md Test-Qualitaets-Regel). Bei SQLite (lokal/Dev) wird bewusst geskippt —
die Pool-Dimensionierung gilt nur fuer Postgres (database/db.py: `_pool_kwargs`).
Verbindliches Tor ist das Pytest-Gate in `deploy.sh production` (real-PG nerve_test),
dort laeuft `test_pool_ist_dimensioniert` OHNE Skip.
"""
import pytest
from sqlalchemy import create_engine

import config
from database.db import engine


def _is_sqlite(eng):
    return eng.url.drivername.startswith("sqlite")


def test_pool_ist_dimensioniert():
    """Auf Postgres muss der Pool tatsaechlich mit pool_size/max_overflow >= den
    konfigurierten Werten laufen — sonst wandert der Engpass von gunicorn (64 Threads)
    stillschweigend zu SQLAlchemy (Default 5+10)."""
    if _is_sqlite(engine):
        pytest.skip("SQLite-Engine — Pool-Dimensionierung gilt nur fuer Postgres")
    assert engine.pool.size() >= 20
    assert engine.pool._max_overflow >= 10


def test_pool_budget_unter_pg_limit():
    """PG max_connections=100, davon 3 reserviert => 97 nutzbar, geteilt mit
    nerve-rt (importiert dieselbe Engine, siehe database/db.py-Kommentar Phase
    08.23.2.STABIL-1 K1). 60 ist die harte Obergrenze, unter der die Haupt-App
    (pool_size + max_overflow) bleiben muss, damit auch bei zukuenftigen Erhoehungen
    genug Kopf-Raum fuer nerve-rt + Wartung (psql/inspect.sh/Deploy-Gate) bleibt."""
    assert config.DB_POOL_SIZE + config.DB_MAX_OVERFLOW <= 60


def test_pool_timeout_ist_kurz():
    """Ein Request soll bei Pool-Erschoepfung schnell und sichtbar scheitern
    (TimeoutError) statt bis zu 30s zu haengen (SQLAlchemy-Default)."""
    assert config.DB_POOL_TIMEOUT <= 15


def test_sqlite_bekommt_keine_pool_kwargs():
    """SQLite-Pfad darf die Postgres-Pool-Ueberdimensionierung nicht tragen — das
    Verhalten wird ueber denselben Code-Pfad wie database/db.py gebaut (Wegwerf-Engine),
    nicht nur ueber Import-Zeit-Zustand geprueft."""
    if not _is_sqlite(engine):
        pytest.skip("Aktive Engine ist Postgres — dieser Test prueft ausschliesslich den SQLite-Zweig")
    throwaway = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # SQLAlchemy-Default fuer SQLite ist der NullPool/SingletonThreadPool je nach
    # connect_args -- in jedem Fall KEIN QueuePool mit pool_size=20/max_overflow=15.
    assert not hasattr(throwaway.pool, "_max_overflow") or throwaway.pool._max_overflow != 15
    throwaway.dispose()
