"""
delete_pretest_data.py — Pre-Migration Test-Daten Bereinigung (Phase 08.23.2.B D-07)

Loescht alle Pre-Migration Test-Daten aus den Mitschrift-Tabellen.
Backup-Pflicht vor DELETE: pg_dump nach /opt/nerve/backups/postgres/

Ausfuehren: python scripts/delete_pretest_data.py [--dry-run] [--backup-only]

FK-Reihenfolge (D-07):
1. objection_events WHERE conversation_log_id IN (alle conversation_logs.id)
2. learning_events WHERE conversation_log_id IN (alle conversation_logs.id)
3. ewb_ratings WHERE conversation_log_id IN (alle conversation_logs.id)
4. phrases WHERE session_id IN (alle conversation_logs.id)
5. coaching_reports (vollstaendig)
6. conversation_logs (vollstaendig)

AUSGENOMMEN: audit_log (Compliance-Trail, bleibt bis Phase 08.23.2.E)
"""
import os
import sys
import subprocess
import datetime
from pathlib import Path

# Lade DATABASE_URL aus .env
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL', '')
DRY_RUN = '--dry-run' in sys.argv
BACKUP_ONLY = '--backup-only' in sys.argv

BACKUP_DIR = '/opt/nerve/backups/postgres'
BACKUP_FILENAME_PATTERN = 'pre-test-data-delete-{date}.sql.gz'


def create_backup() -> str:
    """pg_dump Backup vor DELETE. Gibt Backup-Pfad zurueck."""
    date_str = datetime.date.today().isoformat()
    filename = BACKUP_FILENAME_PATTERN.format(date=date_str)
    backup_path = os.path.join(BACKUP_DIR, filename)

    # Backup-Verzeichnis erstellen wenn noetig
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

    # Extrahiere DB-Name aus DATABASE_URL
    # Format: postgresql://user:pass@host/dbname oder postgresql:///dbname (unix socket)
    if '/' in DATABASE_URL:
        db_name = DATABASE_URL.rstrip('/').split('/')[-1]
    else:
        db_name = 'nerve'

    print(f'[DELETE] Erstelle pg_dump Backup: {backup_path}')
    cmd = ['pg_dump', db_name, '--format=custom', '--compress=9', f'--file={backup_path}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'[DELETE] FEHLER beim pg_dump: {result.stderr}')
        sys.exit(1)
    print(f'[DELETE] Backup erstellt: {backup_path}')
    return backup_path


def count_rows(conn) -> dict:
    """Zaehlt Rows in allen betroffenen Tabellen vor DELETE."""
    from sqlalchemy import text
    tables = [
        'conversation_logs', 'objection_events', 'learning_events',
        'ewb_ratings', 'phrases', 'coaching_reports',
    ]
    counts = {}
    for table in tables:
        result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
        counts[table] = result.scalar()
    return counts


def reset_sequences(conn) -> None:
    """Setzt Auto-Increment-Sequences nach DELETE zurueck (analog Phase 08.23.2.A)."""
    from sqlalchemy import text
    sequences = [
        ('conversation_logs', 'id'),
        ('objection_events', 'id'),
        ('learning_events', 'id'),
        ('ewb_ratings', 'id'),
        ('phrases', 'id'),
        ('coaching_reports', 'id'),
    ]
    for table, col in sequences:
        try:
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), "
                    f"COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1, false)"
                )
            )
            print(f'[DELETE] Sequence reset: {table}.{col}')
        except Exception as e:
            print(f'[DELETE] Sequence reset FEHLER ({table}.{col}): {e}')


def run_delete() -> None:
    """Hauptfunktion: Backup -> Count-Check -> DELETE -> Sequence-Reset."""
    if not DATABASE_URL.startswith('postgresql'):
        print('[DELETE] FEHLER: DATABASE_URL muss postgresql:// sein (kein SQLite)')
        sys.exit(1)

    # Backup erstellen (PFLICHT vor DELETE, D-07)
    backup_path = create_backup()

    if BACKUP_ONLY:
        print(f'[DELETE] --backup-only: Backup erstellt, kein DELETE ausgefuehrt.')
        return

    # SQLAlchemy Connection
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Tabellen-Count vor DELETE (D-07 Anforderung)
        counts_before = count_rows(conn)
        print('[DELETE] Row-Counts VOR DELETE:')
        for table, count in counts_before.items():
            print(f'  {table}: {count}')

        if DRY_RUN:
            print('[DELETE] --dry-run: Kein DELETE ausgefuehrt. Backup liegt unter:', backup_path)
            return

        # Bestaetigung einholen
        print('\n[DELETE] ACHTUNG: Alle Mitschrift-Daten werden unwiderruflich geloescht.')
        print(f'[DELETE] Backup liegt unter: {backup_path}')
        confirm = input('[DELETE] Zum Bestaetigen "DELETE" eingeben: ')
        if confirm.strip() != 'DELETE':
            print('[DELETE] Abgebrochen.')
            sys.exit(0)

        # FK-Reihenfolge DELETE (D-07)
        with conn.begin():
            print('[DELETE] Starte DELETE in FK-Reihenfolge...')

            # 1. objection_events
            r = conn.execute(text('DELETE FROM objection_events WHERE conversation_log_id IN (SELECT id FROM conversation_logs)'))
            print(f'[DELETE] objection_events: {r.rowcount} Zeilen geloescht')

            # 2. learning_events
            r = conn.execute(text('DELETE FROM learning_events WHERE conversation_log_id IN (SELECT id FROM conversation_logs)'))
            print(f'[DELETE] learning_events: {r.rowcount} Zeilen geloescht')

            # 3. ewb_ratings
            r = conn.execute(text('DELETE FROM ewb_ratings WHERE conversation_log_id IN (SELECT id FROM conversation_logs)'))
            print(f'[DELETE] ewb_ratings: {r.rowcount} Zeilen geloescht')

            # 4. phrases (via session_id FK auf conversation_logs)
            r = conn.execute(text('DELETE FROM phrases WHERE session_id IN (SELECT id FROM conversation_logs)'))
            print(f'[DELETE] phrases: {r.rowcount} Zeilen geloescht')

            # 5. coaching_reports (vollstaendig)
            r = conn.execute(text('DELETE FROM coaching_reports'))
            print(f'[DELETE] coaching_reports: {r.rowcount} Zeilen geloescht')

            # 6. conversation_logs (vollstaendig)
            r = conn.execute(text('DELETE FROM conversation_logs'))
            print(f'[DELETE] conversation_logs: {r.rowcount} Zeilen geloescht')

        # Sequence-Reset nach DELETE
        reset_sequences(conn)

        # Count-Verifikation nach DELETE
        counts_after = count_rows(conn)
        print('\n[DELETE] Row-Counts NACH DELETE:')
        for table, count in counts_after.items():
            print(f'  {table}: {count}')

        # audit_log AUSGENOMMEN — Compliance-Trail bleibt (D-07)
        print('\n[DELETE] audit_log AUSGENOMMEN (Compliance-Trail bis Phase 08.23.2.E)')
        print('[DELETE] Fertig.')


if __name__ == '__main__':
    run_delete()
