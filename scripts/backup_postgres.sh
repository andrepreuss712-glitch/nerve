#!/bin/bash
# Postgres Backup Script — NERVE (Phase 08.23.2.A)
# Runs via systemd nerve-backup.timer (daily at 03:30 UTC)
# User: postgres (peer auth, no password needed)
# REQUIRES: #!/bin/bash shebang — uses bash-specific features
set -e

BACKUP_DIR="/opt/nerve/backups/postgres"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/nerve-$TIMESTAMP.sql.gz"
MIN_SIZE_BYTES=1024  # < 1KB = silent pg_dump failure

mkdir -p "$BACKUP_DIR"

echo "[BACKUP] Starting pg_dump at $TIMESTAMP"
pg_dump nerve | gzip > "$BACKUP_FILE"

# Size check — catch silent pg_dump failures
ACTUAL_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
if [ "$ACTUAL_SIZE" -lt "$MIN_SIZE_BYTES" ]; then
    echo "[BACKUP] FEHLER: Backup-Datei zu klein ($ACTUAL_SIZE bytes < $MIN_SIZE_BYTES). Loeschen und Abbruch."
    rm -f "$BACKUP_FILE"
    exit 1
fi

echo "[BACKUP] OK: $BACKUP_FILE ($ACTUAL_SIZE bytes)"

# Rolling retention: delete backups older than 30 days
find "$BACKUP_DIR" -name "nerve-*.sql.gz" -mtime +30 -delete
echo "[BACKUP] Retention cleanup: Dateien aelter als 30 Tage geloescht"

echo "[BACKUP] Abgeschlossen: $(date)"
