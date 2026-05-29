#!/bin/bash
# Postgres Backup Script — NERVE (Phase 08.23.2.A + Phase 08.23.2.D.UX.0)
# Runs via systemd nerve-backup.timer (daily at 03:30 UTC)
# User: postgres (peer auth, no password needed)
# REQUIRES: #!/bin/bash shebang — uses bash-specific features
set -e

# ── Schicht 2: Hetzner Storage Box (Phase 08.23.2.D.UX.0) ────────────────────
BOX_USER="uXXXXX"          # ← ID aus Task 1 eintragen (Format uXXXXX); resume-signal: "box ready uXXXXX=<id>"
BOX_HOST="${BOX_USER}.your-storagebox.de"
BOX_PATH="/backups/nerve"
BOX_KEY="/root/.ssh/id_storagebox"
BOX_RETENTION_DAYS=90      # 3x laenger als lokale 30d (B-03)
# ─────────────────────────────────────────────────────────────────────────────

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

# ── Schicht 2: rsync Push → Hetzner Storage Box ──────────────────────────────
if [ -f "$BOX_KEY" ] && [ -n "$BOX_USER" ] && [ "$BOX_USER" != "uXXXXX" ]; then
    echo "[BACKUP] Schicht 2: rsync Push → ${BOX_HOST}${BOX_PATH}/"
    # W-4: non-fatal — Box-Outage darf die nachfolgende lokale Rotation NICHT verhindern.
    rsync \
        --archive \
        --compress \
        -e "ssh -p23 -i ${BOX_KEY} -o StrictHostKeyChecking=no -o BatchMode=yes" \
        "$BACKUP_FILE" \
        "${BOX_USER}@${BOX_HOST}:${BOX_PATH}/" \
        && echo "[BACKUP] Schicht 2: Push OK" \
        || echo "[BACKUP] Schicht 2: Push FAILED (box unreachable) — continuing"

    # 90d-Rotation: Storage Box hat KEINE volle Shell (Pitfall 5) — kein remote find.
    # Dateinamen-Timestamp parsen (nerve-YYYY-MM-DD_HHMMSS.sql.gz), Alter script-seitig pruefen.
    # G-3: (grep '^nerve-' || true) — leeres grep darf die Pipeline unter set -e nicht abbrechen.
    CUTOFF_DATE=$(date -d "-${BOX_RETENTION_DAYS} days" +%Y-%m-%d)
    ssh -p23 -i "${BOX_KEY}" -o BatchMode=yes "${BOX_USER}@${BOX_HOST}" \
        "ls ${BOX_PATH}/" 2>/dev/null \
        | (grep '^nerve-' || true) \
        | while read -r fname; do
            file_date=$(echo "$fname" | grep -oP '\d{4}-\d{2}-\d{2}' | head -1)
            if [ -n "$file_date" ] && [ "$file_date" \< "$CUTOFF_DATE" ]; then
                ssh -p23 -i "${BOX_KEY}" -o BatchMode=yes "${BOX_USER}@${BOX_HOST}" \
                    "rm ${BOX_PATH}/${fname}" 2>/dev/null \
                    && echo "[BACKUP] Schicht 2: Rotation geloescht: ${fname} (>${BOX_RETENTION_DAYS}d)"
            fi
          done
else
    echo "[BACKUP] Schicht 2: BOX_KEY fehlt oder BOX_USER nicht konfiguriert — skip"
fi
# ─────────────────────────────────────────────────────────────────────────────

# Rolling retention: delete backups older than 30 days
find "$BACKUP_DIR" -name "nerve-*.sql.gz" -mtime +30 -delete
echo "[BACKUP] Retention cleanup: Dateien aelter als 30 Tage geloescht"

echo "[BACKUP] Abgeschlossen: $(date)"
