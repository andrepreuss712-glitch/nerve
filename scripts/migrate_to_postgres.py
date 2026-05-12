#!/usr/bin/env python3
"""
SQLite -> Postgres Migration Script (Phase 08.23.2.A)

Migrates all 33 tables from SQLite to Postgres in FK-dependency order.
After each table: runs inline validation (row count + sample).
On any mismatch: aborts immediately with error message.

Usage:
    SQLITE_URL=sqlite:///database/nerve.db \
    DATABASE_URL=postgresql://nerve_app@/nerve \
    python scripts/migrate_to_postgres.py

Dry-run (no Postgres writes, just SQLite read check):
    DRY_RUN=1 python scripts/migrate_to_postgres.py
"""
import os
import sys

# Ensure project root is on path when running as standalone script
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── FK-Dependency-ordered migration: parents before children ──────────────────
# Circular FKs handled by two-pass strategy:
#   Pass 1: Insert organisations with coach_id=None, users with active_profile_id=None
#   Pass 2: Update coach_id + active_profile_id after both tables migrated
MIGRATION_ORDER = [
    # No-FK tables first
    'waitlist',
    'changelog',
    'prompt_versions',
    'api_rates',
    'fixed_costs',
    'exchange_rates',
    # organisations (coach_id->users circular: insert with coach_id=None)
    'organisations',
    # users (active_profile_id->profiles circular: insert with active_profile_id=None)
    'users',
    # profiles (depends on organisations + users)
    'profiles',
    # profile children
    'profile_skripte',
    'profile_faqs',
    'profile_opener',
    # user + org children
    'sessions',
    'invitations',
    'billing_events',
    'feedback_events',
    'coach_assignments',
    'training_scenarios',
    'personality_types',
    'audit_log',
    'feedback',
    'crm_notes',
    'coaching_reports',  # Wave 5 -- FK to users.id only, no conversation_logs dependency
    'learning_events',
    'api_cost_log',
    'revenue_log',
    # conversation_logs (depends on users, orgs, profiles, personality_types)
    'conversation_logs',
    # conversation_log children
    'phrases',
    'objection_events',
    'ewb_ratings',
    'learning_cards',
    'planning_feedback_link',
    'price_change_log',
]
assert len(MIGRATION_ORDER) == 33, f"Expected 33 tables, got {len(MIGRATION_ORDER)}"

BATCH_SIZE = 500  # rows per bulk insert call

# Tables with circular FK -- handled via two-pass nullable insert + UPDATE
CIRCULAR_FK_NULLS = {
    'organisations': {'coach_id': None},
    'users': {'active_profile_id': None},
}


def migrate_table(table_name, sqlite_sess, pg_sess, dry_run=False):
    """Read all rows from SQLite table, insert into Postgres via raw SQL copy."""
    from sqlalchemy import text, inspect as sa_inspect

    # Get columns
    inspector = sa_inspect(sqlite_sess.bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]

    # Read all rows
    rows = sqlite_sess.execute(text(f'SELECT * FROM {table_name}')).fetchall()
    print(f'[MIGRATE] {table_name}: {len(rows)} Zeilen gelesen')

    if dry_run:
        print(f'[MIGRATE] DRY_RUN: {table_name} uebersprungen')
        return

    if not rows:
        print(f'[MIGRATE] {table_name}: leer — keine Daten zu migrieren')
        return

    col_list = ', '.join(columns)
    param_list = ', '.join(f':{c}' for c in columns)
    insert_sql = text(f'INSERT INTO {table_name} ({col_list}) VALUES ({param_list})')

    # Circular FK: override with NULL for first pass
    null_overrides = CIRCULAR_FK_NULLS.get(table_name, {})

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        batch_dicts = []
        for row in batch:
            row_dict = dict(zip(columns, row))
            for col, val in null_overrides.items():
                if col in row_dict:
                    row_dict[col] = val
            batch_dicts.append(row_dict)
        pg_sess.execute(insert_sql, batch_dicts)
    pg_sess.commit()
    print(f'[MIGRATE] {table_name}: {len(rows)} Zeilen -> Postgres OK')


def restore_circular_fks(sqlite_sess, pg_sess, dry_run=False):
    """Second pass: restore coach_id on organisations and active_profile_id on users."""
    from sqlalchemy import text

    if dry_run:
        print('[MIGRATE] DRY_RUN: circular FK restore uebersprungen')
        return

    # organisations.coach_id
    orgs = sqlite_sess.execute(text('SELECT id, coach_id FROM organisations WHERE coach_id IS NOT NULL')).fetchall()
    for org_id, coach_id in orgs:
        pg_sess.execute(text('UPDATE organisations SET coach_id = :cid WHERE id = :id'), {'cid': coach_id, 'id': org_id})
    pg_sess.commit()
    print(f'[MIGRATE] organisations.coach_id: {len(orgs)} Zeilen aktualisiert')

    # users.active_profile_id
    users = sqlite_sess.execute(text('SELECT id, active_profile_id FROM users WHERE active_profile_id IS NOT NULL')).fetchall()
    for user_id, profile_id in users:
        pg_sess.execute(text('UPDATE users SET active_profile_id = :pid WHERE id = :id'), {'pid': profile_id, 'id': user_id})
    pg_sess.commit()
    print(f'[MIGRATE] users.active_profile_id: {len(users)} Zeilen aktualisiert')


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from scripts.validate_postgres_migration import validate_row_count, validate_sample_rows

    dry_run = os.environ.get('DRY_RUN', '').lower() in ('1', 'true', 'yes')
    sqlite_url = os.environ.get('SQLITE_URL', 'sqlite:///database/nerve.db')
    pg_url = os.environ.get('DATABASE_URL')

    if not dry_run and (not pg_url or 'postgres' not in pg_url):
        print('[MIGRATE] Fehler: DATABASE_URL muss eine Postgres-URL sein')
        sys.exit(1)

    if dry_run:
        print('[MIGRATE] --- DRY RUN MODUS --- Kein Schreiben in Postgres')

    sqlite_engine = create_engine(sqlite_url, connect_args={'check_same_thread': False})
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_sess = SqliteSession()

    if not dry_run:
        pg_engine = create_engine(pg_url)
        PgSession = sessionmaker(bind=pg_engine)
        pg_sess = PgSession()
    else:
        pg_sess = None

    try:
        for table in MIGRATION_ORDER:
            migrate_table(table, sqlite_sess, pg_sess, dry_run=dry_run)
            if not dry_run:
                validate_row_count(table, sqlite_sess, pg_sess)
                validate_sample_rows(table, sqlite_sess, pg_sess, n=5)

        if not dry_run:
            restore_circular_fks(sqlite_sess, pg_sess)

        print('[MIGRATE] --- Migration abgeschlossen ---')
        print(f'[MIGRATE] 33/33 Tabellen migriert und validiert')
        print('[MIGRATE] calls und call_events: NICHT migriert (neue Architektur, starten leer)')
        print('[MIGRATE] ft_call_sessions und ft_assistant_events: bereits in Phase 08.23.2.A-03/04 geloescht')

    finally:
        sqlite_sess.close()
        if pg_sess:
            pg_sess.close()


if __name__ == '__main__':
    main()
