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


def _get_typed_columns(table_name):
    """Return (bool_cols, json_cols) sets for the given Postgres table.

    Phase 08.23.2.A bugfix: SQLite stores Booleans as int 0/1 and JSON as
    string. Postgres rejects ints in Boolean columns and strings in JSONB
    columns. Map Postgres model column types so we can coerce on insert.
    """
    from sqlalchemy import Boolean, JSON
    from database.db import Base
    import database.models  # noqa: F401 — registers models

    pg_table = Base.metadata.tables.get(table_name)
    if pg_table is None:
        return set(), set()

    bool_cols = {c.name for c in pg_table.columns if isinstance(c.type, Boolean)}
    # JSON_TYPE = JSON().with_variant(JSONB, "postgresql") — base impl is JSON
    json_cols = {c.name for c in pg_table.columns if isinstance(c.type, JSON)}
    return bool_cols, json_cols


def _coerce_value(val, col, bool_cols, json_cols):
    """Convert SQLite-stored value to Postgres-compatible Python type."""
    if val is None:
        return None
    if col in bool_cols and isinstance(val, int):
        return bool(val)
    if col in json_cols and isinstance(val, str):
        import json as _json
        try:
            return _json.loads(val)
        except (ValueError, TypeError):
            return val  # leave as-is, let Postgres complain if truly bad
    return val


def _get_fk_info(table_name):
    """Return list of (col_name, parent_table, parent_col, is_nullable) for each FK.

    Phase 08.23.2.A bugfix: SQLite source has orphan FKs (e.g. conversation_logs
    .profile_id=5 references a profile that was deleted). Postgres enforces FKs
    strictly. We need to detect and handle these during migration.
    """
    from database.db import Base
    import database.models  # noqa: F401

    pg_table = Base.metadata.tables.get(table_name)
    if pg_table is None:
        return []

    fk_info = []
    for col in pg_table.columns:
        for fk in col.foreign_keys:
            parent_full = fk.target_fullname  # 'profiles.id'
            parent_table, parent_col = parent_full.split('.')
            fk_info.append((col.name, parent_table, parent_col, col.nullable))
    return fk_info


def _build_parent_id_cache(pg_sess, fk_info):
    """Pre-load existing parent IDs for each FK target table — used for orphan detection."""
    from sqlalchemy import text
    cache = {}
    for _col, parent_table, parent_col, _nullable in fk_info:
        cache_key = (parent_table, parent_col)
        if cache_key in cache:
            continue
        rows = pg_sess.execute(text(f'SELECT {parent_col} FROM {parent_table}')).fetchall()
        cache[cache_key] = {r[0] for r in rows}
    return cache


def migrate_table(table_name, sqlite_sess, pg_sess, dry_run=False):
    """Read all rows from SQLite table, insert into Postgres via raw SQL copy."""
    from sqlalchemy import text, inspect as sa_inspect

    # Get columns
    inspector = sa_inspect(sqlite_sess.bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]

    # Type-coercion maps for SQLite -> Postgres compatibility
    bool_cols, json_cols = _get_typed_columns(table_name)

    # FK-orphan handling: SQLite had no FK enforcement, so legacy data may
    # reference parent rows that no longer exist (e.g. conversation_logs
    # .profile_id=5 -> profile 5 deleted long ago).
    fk_info = _get_fk_info(table_name)
    parent_ids = _build_parent_id_cache(pg_sess, fk_info) if fk_info else {}

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

    inserted = 0
    skipped_orphan = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        batch_dicts = []
        for row in batch:
            row_dict = dict(zip(columns, row))
            # Coerce types: SQLite int/string -> Postgres bool/json
            for col in list(row_dict.keys()):
                row_dict[col] = _coerce_value(row_dict[col], col, bool_cols, json_cols)
            # FK orphan handling
            row_has_unresolvable_orphan = False
            for fk_col, parent_table, parent_col, nullable in fk_info:
                val = row_dict.get(fk_col)
                if val is None:
                    continue
                if val not in parent_ids.get((parent_table, parent_col), set()):
                    if nullable:
                        row_dict[fk_col] = None
                    else:
                        row_has_unresolvable_orphan = True
                        break
            if row_has_unresolvable_orphan:
                skipped_orphan += 1
                continue
            # Circular FK first-pass nulls
            for col, val in null_overrides.items():
                if col in row_dict:
                    row_dict[col] = val
            batch_dicts.append(row_dict)
        if batch_dicts:
            pg_sess.execute(insert_sql, batch_dicts)
            inserted += len(batch_dicts)
    pg_sess.commit()
    if skipped_orphan:
        print(f'[MIGRATE] {table_name}: {inserted} Zeilen -> Postgres OK ({skipped_orphan} orphan-FK-Records uebersprungen, NOT-NULL-FK-Parent fehlt)')
    else:
        print(f'[MIGRATE] {table_name}: {inserted} Zeilen -> Postgres OK')


def restore_circular_fks(sqlite_sess, pg_sess, dry_run=False):
    """Second pass: restore coach_id on organisations and active_profile_id on users."""
    from sqlalchemy import text

    if dry_run:
        print('[MIGRATE] DRY_RUN: circular FK restore uebersprungen')
        return

    # Pre-load valid parent IDs to skip orphan FKs (same logic as migrate_table)
    valid_user_ids = {r[0] for r in pg_sess.execute(text('SELECT id FROM users')).fetchall()}
    valid_profile_ids = {r[0] for r in pg_sess.execute(text('SELECT id FROM profiles')).fetchall()}

    # organisations.coach_id
    orgs = sqlite_sess.execute(text('SELECT id, coach_id FROM organisations WHERE coach_id IS NOT NULL')).fetchall()
    updated_orgs = 0
    skipped_orgs = 0
    for org_id, coach_id in orgs:
        if coach_id in valid_user_ids:
            pg_sess.execute(text('UPDATE organisations SET coach_id = :cid WHERE id = :id'), {'cid': coach_id, 'id': org_id})
            updated_orgs += 1
        else:
            skipped_orgs += 1
    pg_sess.commit()
    suffix_o = f' ({skipped_orgs} orphan-FK uebersprungen)' if skipped_orgs else ''
    print(f'[MIGRATE] organisations.coach_id: {updated_orgs} Zeilen aktualisiert{suffix_o}')

    # users.active_profile_id
    users = sqlite_sess.execute(text('SELECT id, active_profile_id FROM users WHERE active_profile_id IS NOT NULL')).fetchall()
    updated_users = 0
    skipped_users = 0
    for user_id, profile_id in users:
        if profile_id in valid_profile_ids:
            pg_sess.execute(text('UPDATE users SET active_profile_id = :pid WHERE id = :id'), {'pid': profile_id, 'id': user_id})
            updated_users += 1
        else:
            skipped_users += 1
    pg_sess.commit()
    suffix_u = f' ({skipped_users} orphan-FK uebersprungen)' if skipped_users else ''
    print(f'[MIGRATE] users.active_profile_id: {updated_users} Zeilen aktualisiert{suffix_u}')


def reset_sequences(pg_sess):
    """Reset auto-increment sequences to MAX(id)+1 for all migrated tables.

    Phase 08.23.2.A bugfix: After migrating rows with explicit IDs (1, 2, 3...),
    Postgres' auto-increment sequences still start at 1. Next INSERT would
    collide with existing row IDs. Must SETVAL each sequence to MAX(id)+1
    after data migration. SQLite doesn't have this problem (ROWID semantics).
    """
    from sqlalchemy import text
    pg_sess.execute(text("""
        DO $$
        DECLARE
            r RECORD;
            seq_name TEXT;
            max_id BIGINT;
        BEGIN
            FOR r IN
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND column_default LIKE 'nextval%'
            LOOP
                seq_name := pg_get_serial_sequence(r.table_name, r.column_name);
                IF seq_name IS NOT NULL THEN
                    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I', r.column_name, r.table_name) INTO max_id;
                    EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
                END IF;
            END LOOP;
        END $$;
    """))
    pg_sess.commit()
    print('[MIGRATE] Sequences auf MAX(id)+1 gesetzt fuer alle migrierten Tabellen')


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
            reset_sequences(pg_sess)

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
