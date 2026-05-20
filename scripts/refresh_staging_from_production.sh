#!/bin/bash
# ── NERVE DB-Refresh: Production → Staging ────────────────────────────────────
# Synchronisiert die Production-Postgres-Datenbank auf den Staging-Server.
# Kein lokaler pg_dump — alle Daten laufen via SSH-Pipe (DSGVO-Hygiene).
#
# Voraussetzungen:
#   - SSH-Key ~/.ssh/nerve_vps fuer Production (root@178.104.82.166)
#   - SSH-Key ~/.ssh/nerve_staging fuer Staging (root@178.104.245.8)
#   - pg_dump/psql auf beiden Servern verfuegbar (Postgres installiert)
#   - STAGING_IP: als Env-Var setzen oder Platzhalter unten ersetzen
#
# Aufruf:
#   bash scripts/refresh_staging_from_production.sh
#   # oder mit expliziter IP:
#   STAGING_IP=1.2.3.4 bash scripts/refresh_staging_from_production.sh
#
# DSGVO-Hinweis (Req-6 Constraint):
#   Solange kein externer Early-Access-User registriert ist, ist 1:1-Kopie
#   DSGVO-konform. Sobald erster externer User registriert:
#   -> refresh_staging_from_production.sh MUSS anonymisieren.
#   -> Trigger dokumentiert in Nerve-Vault/04 Entscheidungen/NERVE DSGVO Analyse.md Sektion 8

# REVIEW-HIGH-3 FIX: pipefail verhindert stille DB-Korruption bei halbem pg_dump-Stream.
# Ohne pipefail: bash gibt Exit-Code von psql zurueck (letztem Befehl), nicht pg_dump.
# psql kann erfolgreich beenden obwohl der pg_dump-Input leer oder korrupt war.
set -eo pipefail

# ── Konfiguration ─────────────────────────────────────────────────────────────
PROD_HOST="root@178.104.82.166"
PROD_SSH_KEY="$HOME/.ssh/nerve_vps"
STAGING_IP="${STAGING_IP:-178.104.245.8}"  # Env-Var oder Platzhalter ersetzen
STAGING_HOST="root@${STAGING_IP}"
STAGING_SSH_KEY="$HOME/.ssh/nerve_staging"
DB_NAME="nerve"
BACKUP_DIR="/opt/nerve/backups/pre-refresh"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)

echo "[DB] ============================================================"
echo "[DB] NERVE DB-Refresh: Production → Staging"
echo "[DB] Production: $PROD_HOST"
echo "[DB] Staging:    $STAGING_HOST"
echo "[DB] ============================================================"
echo ""
echo "[DB] WARNUNG: Die nerve-Datenbank auf Staging wird VOLLSTAENDIG UEBERSCHRIEBEN."
echo "[DB] Alle Staging-spezifischen Daten gehen verloren."
echo ""
printf "Fortfahren? [y/N] "
read -r CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "[DB] Abgebrochen."
  exit 0
fi

# ── Schritt 1: Pre-Refresh-Backup auf Staging ─────────────────────────────────
echo "[DB] Schritt 1/3: Erstelle Pre-Refresh-Backup auf Staging..."
ssh -i "$STAGING_SSH_KEY" "$STAGING_HOST" \
  "mkdir -p '$BACKUP_DIR' && pg_dump -U nerve_app $DB_NAME | gzip > '$BACKUP_DIR/pre-refresh-$TIMESTAMP.sql.gz'"
echo "[DB] Backup erstellt: $BACKUP_DIR/pre-refresh-$TIMESTAMP.sql.gz"

# ── Schritt 2: DB-Stream Production → Staging via SSH-Pipe ────────────────────
echo "[DB] Schritt 2/3: Streame pg_dump von Production nach Staging..."
echo "[DB] REVIEW-HIGH-3: Dump wird zuerst in Variable gefangen — Groessen-Check vor Import."
echo "[DB] Kein lokaler Dump wird erstellt (DSGVO-Hygiene)."

# Dump in Variable fangen (kein lokaler File-Dump — Daten nur im RAM)
# -o StrictHostKeyChecking=accept-new: verhindert Prompt bei neuem Host-Key
DUMP=$(ssh -i "$PROD_SSH_KEY" -o StrictHostKeyChecking=accept-new "$PROD_HOST" \
  "pg_dump -U nerve_app --no-owner --no-acl $DB_NAME 2>/dev/null")

# Groessen-Check: Ein valider nerve-Dump ist immer > 1 KB.
# < 1024 Bytes deutet auf SSH-Verbindungsfehler oder leere DB hin.
DUMP_SIZE=${#DUMP}
if [[ "$DUMP_SIZE" -lt 1024 ]]; then
  echo "[DB] ABORT: pg_dump Output zu klein (${DUMP_SIZE} Bytes) — moeglicher Verbindungsfehler auf Production"
  echo "[DB] Staging-DB wurde NICHT veraendert."
  exit 1
fi
echo "[DB] Dump-Groesse: ${DUMP_SIZE} Bytes — OK"

# Dump auf Staging importieren
echo "$DUMP" | ssh -i "$STAGING_SSH_KEY" -o StrictHostKeyChecking=accept-new "$STAGING_HOST" \
  "psql -U nerve_app $DB_NAME"

echo "[DB] DB-Stream abgeschlossen."

# ── Schritt 3: Sequence-Reset auf Staging ─────────────────────────────────────
echo "[DB] Schritt 3/3: Sequence-Reset auf Staging ausfuehren..."
ssh -i "$STAGING_SSH_KEY" "$STAGING_HOST" \
  "DATABASE_URL=postgresql://nerve_app@/$DB_NAME /opt/nerve/venv/bin/python /opt/nerve/app/scripts/reset_sequences.py"

echo "[DB] ============================================================"
echo "[DB] DB-Refresh abgeschlossen."
echo "[DB] Staging-DB entspricht jetzt Production-Stand von: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[DB] Verifikation: psql -h $STAGING_IP -U nerve_app -c 'SELECT COUNT(*) FROM users' nerve"
echo "[DB] ============================================================"
