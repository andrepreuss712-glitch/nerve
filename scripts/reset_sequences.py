#!/usr/bin/env python3
"""reset_sequences.py — Setzt alle Postgres-Sequences auf MAX(id)+1.

Idempotent: Mehrfacher Lauf ist sicher (GREATEST(max_id, 1) verhindert
setval auf 0 bei leeren Tabellen).

Aufruf:
    DATABASE_URL=postgresql://nerve_app@/nerve python scripts/reset_sequences.py

Oder direkt auf Staging-Server:
    /opt/nerve/venv/bin/python /opt/nerve/app/scripts/reset_sequences.py

Hintergrund (Phase 08.23.2.A Bugfix): Nach einem pg_dump | psql-Import starten
Postgres-Sequences bei 1, obwohl Zeilen mit IDs 1, 2, 3, ... bereits existieren.
Naechstes INSERT wuerde mit Duplicate-Key-Fehler schlagen. Sequence auf MAX(id)+1
setzen behebt das Problem.
"""
import os
import sys

from sqlalchemy import create_engine, text


def reset_sequences(engine):
    """Setzt alle Sequences auf GREATEST(MAX(id), 1) — idempotent."""
    with engine.connect() as conn:
        conn.execute(text("""
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
                        EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I',
                            r.column_name, r.table_name) INTO max_id;
                        EXECUTE format('SELECT setval(%L, %s, true)',
                            seq_name, GREATEST(max_id, 1));
                        RAISE NOTICE 'Sequence % -> %', seq_name, GREATEST(max_id, 1);
                    END IF;
                END LOOP;
            END $$;
        """))
        conn.commit()
    print('[DB] Sequence-Reset abgeschlossen — alle Sequences auf MAX(id)+1 gesetzt')


def main():
    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url.startswith('postgresql'):
        print(f'[DB] ERROR: DATABASE_URL muss mit postgresql:// beginnen, ist: {database_url!r}')
        sys.exit(1)

    print(f'[DB] Verbinde mit: {database_url}')
    engine = create_engine(database_url)
    reset_sequences(engine)


if __name__ == '__main__':
    main()
