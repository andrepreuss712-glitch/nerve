#!/usr/bin/env python3
"""Create Postgres schema from SQLAlchemy models (Phase 08.23.2.A cutover Step 4a).

Replaces the broken manual alembic baseline migration. Uses SQLAlchemy's
Base.metadata.create_all() which handles circular FKs (users<->profiles,
users<->organisations.coach_id) automatically via two-pass DDL strategy.

After this script runs successfully, run `alembic stamp 0001` to mark the
alembic baseline state. Future migrations (08.23.2.F/G/H) generate as
proper alembic deltas from this baseline.

Usage:
    sudo -u postgres bash -c "
      cd /opt/nerve/app && \
      DATABASE_URL=postgresql://postgres@/nerve \
      /opt/nerve/venv/bin/python scripts/create_postgres_schema.py
    "

Expected output:
    Schema created: 35 tables in <database-name>

Designed to be IDEMPOTENT — re-running creates only missing tables.
"""
import os
import sys

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sqlalchemy import create_engine, inspect
from database.db import Base
import database.models  # noqa: F401 — registers all models with Base.metadata


def main() -> int:
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('ERROR: DATABASE_URL not set', file=sys.stderr)
        return 1

    if not database_url.startswith('postgresql'):
        print(f'ERROR: DATABASE_URL must be postgresql:// (got: {database_url[:20]}...)',
              file=sys.stderr)
        return 1

    print(f'Connecting to: {database_url.split("@")[1] if "@" in database_url else database_url}')

    engine = create_engine(database_url)

    inspector = inspect(engine)
    before = set(inspector.get_table_names())
    print(f'Tables BEFORE create_all: {len(before)}')

    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    after = set(inspector.get_table_names())
    created = after - before
    print(f'Tables AFTER create_all: {len(after)}')
    print(f'Newly created: {len(created)}')
    if created:
        for t in sorted(created):
            print(f'  + {t}')

    # Sanity: verify 'calls' and 'call_events' (new architecture tables) exist
    required_new = {'calls', 'call_events'}
    if not required_new.issubset(after):
        missing = required_new - after
        print(f'ERROR: New architecture tables missing: {missing}', file=sys.stderr)
        return 1

    print(f'OK: schema ready ({len(after)} tables total)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
