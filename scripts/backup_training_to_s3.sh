#!/bin/bash
# scripts/backup_training_to_s3.sh — NERVE Training Schema Backup (Schicht 3)
# Phase 08.23.2.D.UX.0. systemd nerve-backup-training.timer (woechentlich). User: root.
#
# C-03 WRITE-TIME-FILTER-CONTRACT (Dokumentation, NICHT hier implementiert):
#   Dieser Dump ist VOLL (--schema=training, kein WHERE). Test-Calls duerfen NIE in training.*
#   landen — der D.UX.1-Background-Job prueft users.is_test_user BEVOR er in training.* schreibt.
#   KEIN dump-time-Filter (haette FK training.*->calls gebraucht = ADR-Verletzung Re-ID).
set -euo pipefail

SECRETS_FILE="/etc/nerve/ionos-s3.env"
if [ ! -f "$SECRETS_FILE" ]; then
    echo "[BACKUP-S3] FEHLER: $SECRETS_FILE nicht gefunden" >&2
    exit 1
fi
source "$SECRETS_FILE"

# C-WARN-2: AWS_DEFAULT_REGION MUSS gesetzt sein — aws-cli braucht Region fuer SigV4-Signing
# auch gegen custom IONOS-Endpoints. Wird aus IONOS_S3_REGION (ionos-s3.env) exportiert.
if [ -z "${IONOS_S3_REGION:-}" ]; then
    echo "[BACKUP-S3] FEHLER: IONOS_S3_REGION nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
if [ -z "${IONOS_S3_ENDPOINT:-}" ]; then
    echo "[BACKUP-S3] FEHLER: IONOS_S3_ENDPOINT nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
if [ -z "${IONOS_S3_BUCKET:-}" ]; then
    echo "[BACKUP-S3] FEHLER: IONOS_S3_BUCKET nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
export AWS_DEFAULT_REGION="${IONOS_S3_REGION}"

TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
BACKUP_KEY="training-${TIMESTAMP}.sql.gz"
TMP_FILE="/tmp/${BACKUP_KEY}"
MIN_SIZE_BYTES=512
IONOS_ENDPOINT="${IONOS_S3_ENDPOINT}"
BUCKET="${IONOS_S3_BUCKET}"

echo "[BACKUP-S3] Start: $TIMESTAMP"

# G-2: -h 127.0.0.1 erzwingt TCP -> pg_hba host-Regel (scram/md5) -> PGPASSWORD greift.
# Ohne -h: Unix-Socket -> peer auth (root vs nerve_anon_worker) -> Connection abgelehnt.
PGPASSWORD="$NERVE_ANON_WORKER_DB_PASSWORD" \
    pg_dump -h 127.0.0.1 -U nerve_anon_worker -d nerve \
    --schema=training --no-owner --no-acl \
    | gzip > "$TMP_FILE"

ACTUAL_SIZE=$(stat -c%s "$TMP_FILE" 2>/dev/null || echo 0)
if [ "$ACTUAL_SIZE" -lt "$MIN_SIZE_BYTES" ]; then
    echo "[BACKUP-S3] FEHLER: Dump zu klein ($ACTUAL_SIZE bytes < $MIN_SIZE_BYTES)" >&2
    rm -f "$TMP_FILE"
    exit 1
fi
echo "[BACKUP-S3] pg_dump OK: $ACTUAL_SIZE bytes"

# WORM-Upload (COMPLIANCE +30d). WICHTIG: aws s3 cp unterstuetzt kein --object-lock-* -> put-object.
RETAIN_UNTIL=$(date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ)
aws s3api put-object \
    --bucket "$BUCKET" \
    --key "$BACKUP_KEY" \
    --body "$TMP_FILE" \
    --object-lock-mode COMPLIANCE \
    --object-lock-retain-until-date "$RETAIN_UNTIL" \
    --endpoint-url "$IONOS_ENDPOINT"
echo "[BACKUP-S3] OK: s3://$BUCKET/$BACKUP_KEY (WORM until $RETAIN_UNTIL)"
rm -f "$TMP_FILE"

# 365d-Rotation: Objekte mit abgelaufener Retention loeschen.
# G-3: (grep '^training-' || true) — leeres grep darf die Pipeline unter set -euo pipefail nicht abbrechen.
CUTOFF_DATE=$(date -u -d '-365 days' +%Y-%m-%d)
aws s3 ls "s3://${BUCKET}/" --endpoint-url "$IONOS_ENDPOINT" \
    | awk '{print $4}' \
    | (grep '^training-' || true) \
    | while read -r obj; do
        obj_date=$(echo "$obj" | grep -oP '\d{4}-\d{2}-\d{2}' | head -1)
        if [ -n "$obj_date" ] && [ "$obj_date" \< "$CUTOFF_DATE" ]; then
            aws s3api delete-object --bucket "$BUCKET" --key "$obj" --endpoint-url "$IONOS_ENDPOINT" 2>/dev/null \
                && echo "[BACKUP-S3] Rotation: $obj geloescht (>365d)"
        fi
      done

echo "[BACKUP-S3] Abgeschlossen: $(date)"
