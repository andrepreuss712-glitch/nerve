#!/usr/bin/env python3
"""
Postgres Migration Validation Module (Phase 08.23.2.A)

Reusable functions for validating SQLite->Postgres data integrity.
Import by migrate_to_postgres.py or run standalone.
"""
import os
import sys
import random

# ── Table list: 33 tables to migrate (calls + call_events excluded) ──
MIGRATE_TABLES = [
    'organisations',
    'users',
    'profiles',
    'profile_skripte',
    'profile_faqs',
    'profile_opener',
    'sessions',
    'invitations',
    'billing_events',
    'feedback_events',
    'coach_assignments',
    'training_scenarios',
    'personality_types',
    'conversation_logs',
    'phrases',
    'waitlist',
    'changelog',
    'audit_log',
    'objection_events',
    'ewb_ratings',
    'feedback',
    'planning_feedback_link',
    'prompt_versions',
    'api_cost_log',
    'api_rates',
    'price_change_log',
    'fixed_costs',
    'revenue_log',
    'exchange_rates',
    'learning_cards',
    'coaching_reports',
    'learning_events',
    'crm_notes',
]
assert len(MIGRATE_TABLES) == 33, f"Expected 33 tables, got {len(MIGRATE_TABLES)}"

# Explicitly excluded — new architecture tables, start empty
EXCLUDED_TABLES = ['calls', 'call_events']
# Also excluded (deleted in Phase 08.23.2.A-03/04): ft_call_sessions, ft_assistant_events


def validate_row_count(table_name: str, sqlite_session, pg_session) -> None:
    """Compare row count for table_name between SQLite and Postgres.

    Raises SystemExit with error message if counts differ.
    """
    from sqlalchemy import text
    sqlite_count = sqlite_session.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
    pg_count = pg_session.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
    if sqlite_count != pg_count:
        print(f'[VALIDATE] FEHLER: {table_name}: SQLite={sqlite_count}, Postgres={pg_count}')
        sys.exit(1)
    print(f'[VALIDATE] OK: {table_name}: {pg_count} Zeilen')


def validate_sample_rows(table_name: str, sqlite_session, pg_session, n: int = 5) -> None:
    """Compare n random rows between SQLite and Postgres by primary key.

    Fetches row IDs from SQLite, checks each exists in Postgres with matching id.
    Raises SystemExit if any row is missing in Postgres.
    """
    from sqlalchemy import text
    rows = sqlite_session.execute(text(f'SELECT id FROM {table_name} ORDER BY id LIMIT 100')).fetchall()
    if not rows:
        print(f'[VALIDATE] STICHPROBE: {table_name}: leer (uebersprungen)')
        return
    sample_ids = random.sample([r[0] for r in rows], min(n, len(rows)))
    for row_id in sample_ids:
        pg_row = pg_session.execute(text(f'SELECT id FROM {table_name} WHERE id = :id'), {'id': row_id}).fetchone()
        if pg_row is None:
            print(f'[VALIDATE] FEHLER: {table_name}: id={row_id} in SQLite vorhanden, in Postgres NICHT')
            sys.exit(1)
    print(f'[VALIDATE] STICHPROBE: {table_name}: {len(sample_ids)} Zeilen OK')


if __name__ == '__main__':
    """Standalone validation run after migration. Requires SQLITE_URL and DATABASE_URL env vars."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sqlite_url = os.environ.get('SQLITE_URL', 'sqlite:///database/nerve.db')
    pg_url = os.environ.get('DATABASE_URL')
    if not pg_url or 'postgres' not in pg_url:
        print('[VALIDATE] Fehler: DATABASE_URL muss eine Postgres-URL sein')
        sys.exit(1)

    sqlite_engine = create_engine(sqlite_url, connect_args={'check_same_thread': False})
    pg_engine = create_engine(pg_url)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    sqlite_sess = SqliteSession()
    pg_sess = PgSession()
    try:
        errors = 0
        for table in MIGRATE_TABLES:
            try:
                validate_row_count(table, sqlite_sess, pg_sess)
                validate_sample_rows(table, sqlite_sess, pg_sess, n=5)
            except SystemExit:
                errors += 1
        if errors == 0:
            print(f'[VALIDATE] 33/33 Tabellen validiert, 0 Abweichungen')
        else:
            print(f'[VALIDATE] {errors} Fehler gefunden — Migration NICHT erfolgreich')
            sys.exit(1)
    finally:
        sqlite_sess.close()
        pg_sess.close()
