#!/bin/bash
# scripts/restore_test_s3.sh — Monatlicher S3-Restore-Integritaets-Test (Schicht 3, C-08)
# Phase 08.23.2.D.UX.0. systemd nerve-restore-test.timer (monatlich). User: root.
# Schreibt /opt/nerve/.s3_restore_status im key=value-Format (analog .deploy_meta).
# /api/health liest diese Datei und gibt backup_s3_restore_ok zurueck.
set -uo pipefail

SECRETS_FILE="/etc/nerve/ionos-s3.env"
[ -f "$SECRETS_FILE" ] && source "$SECRETS_FILE"

# C-WARN-2: AWS_DEFAULT_REGION MUSS gesetzt sein — aws-cli braucht Region fuer SigV4-Signing
# auch gegen custom IONOS-Endpoints. Wird aus IONOS_S3_REGION (ionos-s3.env) exportiert.
if [ -z "${IONOS_S3_REGION:-}" ]; then
    echo "[RESTORE-TEST] FEHLER: IONOS_S3_REGION nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
if [ -z "${IONOS_S3_ENDPOINT:-}" ]; then
    echo "[RESTORE-TEST] FEHLER: IONOS_S3_ENDPOINT nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
if [ -z "${IONOS_S3_BUCKET:-}" ]; then
    echo "[RESTORE-TEST] FEHLER: IONOS_S3_BUCKET nicht gesetzt in $SECRETS_FILE" >&2
    exit 1
fi
export AWS_DEFAULT_REGION="${IONOS_S3_REGION}"

STATUS_FILE="/opt/nerve/.s3_restore_status"
CHECKED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# G-3: (grep '^training-' || true) — leeres grep darf unter pipefail nicht abbrechen.
LATEST=$(aws s3 ls "s3://${IONOS_S3_BUCKET}/" --endpoint-url "$IONOS_S3_ENDPOINT" 2>/dev/null \
    | awk '{print $4}' | (grep '^training-' || true) | sort | tail -1)
if [ -z "$LATEST" ]; then
    echo "[RESTORE-TEST] Kein Objekt im Bucket — noch kein Backup gelaufen"
    echo "S3_RESTORE_OK=false" > "$STATUS_FILE"
    echo "S3_RESTORE_CHECKED_AT=$CHECKED_AT" >> "$STATUS_FILE"
    exit 0
fi
TMP="/tmp/restore-test-${LATEST}"
aws s3api get-object --bucket "$IONOS_S3_BUCKET" --key "$LATEST" "$TMP" --endpoint-url "$IONOS_S3_ENDPOINT" >/dev/null 2>&1
if gunzip -t "$TMP" 2>/dev/null; then
    echo "[RESTORE-TEST] OK: $LATEST integer"
    echo "S3_RESTORE_OK=true" > "$STATUS_FILE"
    echo "S3_RESTORE_CHECKED_AT=$CHECKED_AT" >> "$STATUS_FILE"
else
    echo "[RESTORE-TEST] FEHLER: $LATEST korrupt"
    echo "S3_RESTORE_OK=false" > "$STATUS_FILE"
    echo "S3_RESTORE_CHECKED_AT=$CHECKED_AT" >> "$STATUS_FILE"
fi
rm -f "$TMP"
