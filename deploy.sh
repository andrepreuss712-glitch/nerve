#!/bin/bash
# ── NERVE Deploy Script ─────────────────────────────────────────────────────
# Usage: ./deploy.sh staging|production
# Deploys the latest main branch to the target VPS via tar-over-ssh.
# Works on Windows Git-Bash (no rsync required) and on Linux/macOS.
# Prod-SQLite NICHT ueberschreiben — Schema-Code (database/models.py, db.py)
# wird uebertragen, .db-Dateien nicht (via tar --exclude).
# Prerequisites: SSH key auth configured for VPS_HOST, tar available locally.
# Staging-Key: ~/.ssh/nerve_staging | Production-Key: ~/.ssh/nerve_vps

set -e

# ── Target-Parameter (Pflicht, kein Default) ───────────────────────────────
TARGET="${1:?Usage: ./deploy.sh staging|production}"

APP_DIR="/opt/nerve/app"
VENV_DIR="/opt/nerve/venv"

if [[ "$TARGET" == "production" ]]; then
  # ── Production Pre-Deploy-Gate ─────────────────────────────────────────
  echo "[deploy] TARGET=production — Pre-Deploy-Gate wird ausgefuehrt..."

  # jq-Pflicht-Check (fuer JSON-Parsing der Health-Response)
  which jq || { echo "[deploy] ERROR: jq nicht installiert — brew install jq oder https://stedolan.github.io/jq/"; exit 1; }

  STAGING_HEALTH=$(curl -fsS --max-time 10 https://staging.getnerve.app/api/health 2>/dev/null || true)

  if [[ -z "$STAGING_HEALTH" ]]; then
    echo "[deploy] BLOCKER: Staging nicht erreichbar — https://staging.getnerve.app/api/health antwortet nicht"
    exit 1
  fi

  STAGING_STATUS=$(echo "$STAGING_HEALTH" | jq -r '.status // "error"')
  if [[ "$STAGING_STATUS" != "ok" ]]; then
    echo "[deploy] BLOCKER: Staging not healthy (status=$STAGING_STATUS) — zuerst ./deploy.sh staging ausfuehren"
    exit 1
  fi

  STAGING_DEPLOYED_AT=$(echo "$STAGING_HEALTH" | jq -r '.deployed_at // ""')
  if [[ -z "$STAGING_DEPLOYED_AT" || "$STAGING_DEPLOYED_AT" == "null" ]]; then
    echo "[deploy] BLOCKER: Staging hat kein deployed_at — zuerst ./deploy.sh staging ausfuehren"
    exit 1
  fi
  # Alter pruefen: deployed_at ist ISO-8601 UTC, z.B. 2026-05-19T14:30:00Z
  DEPLOYED_TS=$(date -u -d "$STAGING_DEPLOYED_AT" +%s 2>/dev/null || date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$STAGING_DEPLOYED_AT" +%s 2>/dev/null || echo "0")
  NOW_TS=$(date -u +%s)
  AGE_HOURS=$(( (NOW_TS - DEPLOYED_TS) / 3600 ))
  if [[ "$AGE_HOURS" -ge 24 ]]; then
    echo "[deploy] BLOCKER: Staging deploy older than 24h (${AGE_HOURS}h) — zuerst ./deploy.sh staging ausfuehren"
    exit 1
  fi

  LOCAL_HEAD=$(git rev-parse HEAD)
  STAGING_HEAD=$(echo "$STAGING_HEALTH" | jq -r '.git_head // ""')
  if [[ "$STAGING_HEAD" != "$LOCAL_HEAD" ]]; then
    echo "[deploy] BLOCKER: Local HEAD ($LOCAL_HEAD) != Staging HEAD ($STAGING_HEAD) — zuerst ./deploy.sh staging mit aktuellem Commit ausfuehren"
    exit 1
  fi

  echo "[deploy] Pre-Deploy-Gate bestanden — Staging ist ok, aktuell (${AGE_HOURS}h alt), HEAD stimmt ueberein"

  VPS_HOST="root@178.104.82.166"
  SSH_KEY="$HOME/.ssh/nerve_vps"
  SERVICE_NAME="nerve"

elif [[ "$TARGET" == "staging" ]]; then
  VPS_HOST="root@<STAGING_IP>"
  SSH_KEY="$HOME/.ssh/nerve_staging"
  SERVICE_NAME="nerve-staging"

else
  echo "[deploy] ERROR: Unbekannter TARGET '$TARGET'. Erlaubt: staging, production"
  exit 1
fi

# .env-Check: Beide Targets brauchen /etc/nerve/.env auf dem Ziel-Server
echo "[deploy] Pruefe /etc/nerve/.env auf $TARGET..."
ssh -i "$SSH_KEY" "$VPS_HOST" 'test -f /etc/nerve/.env' || {
  echo "[deploy] BLOCKER: /etc/nerve/.env fehlt auf $TARGET — erstelle die Datei mit .env.staging.example als Template"
  exit 1
}

# Exclude list — shared between all targets.
# Prod-DB und Secrets bleiben IMMER lokal.
TAR_EXCLUDES=(
  --exclude='./.git'
  --exclude='./.gitignore'
  --exclude='./.env'
  --exclude='./.planning'
  --exclude='./.claude'
  --exclude='./node_modules'
  --exclude='./logs'
  --exclude='./deploy'
  --exclude='./deploy.sh'
  --exclude='*.pyc'
  --exclude='__pycache__'
  --exclude='salesnerve_log_*.txt'
  --exclude='*.db-journal'
  --exclude='*.db-wal'
  --exclude='*.db-shm'
  --exclude='./database/*.db'
  --exclude='./database/salesnerve.db'
)

GIT_HEAD_LOCAL=$(git rev-parse HEAD)
echo "[deploy] Connecting to $VPS_HOST (TARGET=$TARGET)..."

echo "[deploy] Uploading via tar-over-ssh (excludes: .git, .env, .planning, *.db, ...)"
# Pack locally, stream to remote, unpack into $APP_DIR. --no-same-owner
# verhindert Permission-Konflikte (remote user ist root).
tar "${TAR_EXCLUDES[@]}" -cf - ./ | \
  ssh -i "$SSH_KEY" "$VPS_HOST" "mkdir -p '$APP_DIR' && tar -xf - -C '$APP_DIR' --no-same-owner"

# Finding 2: gthread verhindert OOM durch mehrfaches spaCy-Model-Load.
# Deploy-Ordner ist vom tar ausgeschlossen — Service-Datei separat installieren.
echo "[deploy] Installing systemd service unit ($SERVICE_NAME)..."
if [[ "$TARGET" == "staging" ]]; then
  scp -i "$SSH_KEY" deploy/nerve-staging.service "$VPS_HOST":/tmp/nerve-staging.service
  ssh -i "$SSH_KEY" "$VPS_HOST" "sudo cp /tmp/nerve-staging.service /etc/systemd/system/nerve-staging.service && sudo systemctl daemon-reload"
elif [[ "$TARGET" == "production" ]]; then
  scp -i "$SSH_KEY" deploy/nerve.service "$VPS_HOST":/tmp/nerve.service
  ssh -i "$SSH_KEY" "$VPS_HOST" "sudo cp /tmp/nerve.service /etc/systemd/system/nerve.service && sudo systemctl daemon-reload"
fi

echo "[deploy] Uploading nginx config for $TARGET..."
if [[ "$TARGET" == "staging" ]]; then
  scp -i "$SSH_KEY" deploy/nginx-staging.conf "$VPS_HOST":/tmp/nginx-staging.conf
elif [[ "$TARGET" == "production" ]]; then
  scp -i "$SSH_KEY" deploy/nginx-production.conf "$VPS_HOST":/tmp/nginx-production.conf
fi

ssh -i "$SSH_KEY" "$VPS_HOST" bash -s << ENDHEREDOC
  set -e
  echo "[deploy] Fixing file ownership (nerve_app fuer writable dirs)..."
  # tar-over-ssh kann Windows-UIDs wie 197609 uebernehmen — gunicorn laeuft als nerve_app
  # (seit Phase 08.23.2.A Server-Setup: Postgres-Peer-Auth ueber Unix-Socket).
  mkdir -p /opt/nerve/app/logs
  chown -R nerve_app:nerve_app /opt/nerve/app/logs /opt/nerve/app/database /opt/nerve/venv 2>/dev/null || true
  chmod 755 /opt/nerve/app/logs /opt/nerve/app/database 2>/dev/null || true

  echo "[deploy] Installing dependencies..."
  /opt/nerve/venv/bin/pip install -r /opt/nerve/app/requirements.txt --quiet
  echo "[deploy] Downloading spaCy model de_core_news_lg (~570MB)..."
  /opt/nerve/venv/bin/python -m spacy download de_core_news_lg --quiet

  # GLiNER Modell vorab cachen (Phase 08.23.2.C — Req-1)
  echo "[deploy] Pre-caching GLiNER model urchade/gliner_multi-v2.1 (~450MB)..."
  /opt/nerve/venv/bin/python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_multi-v2.1')" || \
      echo "[deploy] GLiNER-Pre-Download fehlgeschlagen — App startet trotzdem, laedt beim ersten Request"

  # nginx-Config installieren (Datei wurde per scp hochgeladen — kein inline-Heredoc)
  if [[ "$TARGET" == "staging" ]]; then
    sudo cp /tmp/nginx-staging.conf /etc/nginx/sites-available/nerve-staging
    sudo ln -sf /etc/nginx/sites-available/nerve-staging /etc/nginx/sites-enabled/nerve-staging
    sudo nginx -t && sudo systemctl reload nginx
  else
    sudo cp /tmp/nginx-production.conf /etc/nginx/sites-available/nerve
    sudo ln -sf /etc/nginx/sites-available/nerve /etc/nginx/sites-enabled/nerve
    sudo nginx -t && sudo systemctl reload nginx
  fi
  echo "[deploy] nginx config updated and reloaded"

  echo "[deploy] Running server-side tests (SQLite-in-memory)..."
  # NOTE: conftest.py uses sqlite:///:memory: for all fixtures regardless of TEST_DATABASE_URL.
  # Echte Postgres-Test-Suite ist eigene Folge-Phase (conftest-Refactor erforderlich).
  # Cutover-Verifikation gegen Postgres erfolgt via Pre-Cutover-Alembic-Test (manuell) +
  # post-Cutover-Smoke-Test (Live-App auf Postgres).
  /opt/nerve/venv/bin/pytest /opt/nerve/app/tests/ \
    --tb=short -q > /tmp/pytest_out.txt 2>&1
  PYTEST_EXIT=\$?
  tail -30 /tmp/pytest_out.txt
  if [ \$PYTEST_EXIT -ne 0 ]; then
    echo "[deploy] FEHLER: Tests fehlgeschlagen (exit \$PYTEST_EXIT) — kein Restart, kein Deploy"
    exit 1
  fi
  echo "[deploy] Tests bestanden"

  # REVIEW-HIGH-2 FIX: .deploy_meta VOR systemctl restart schreiben
  # Datei muss existieren bevor Service neu startet — sonst liest /api/health
  # beim ersten Request nach Restart noch stale/keine Daten.
  if [[ "$TARGET" == "staging" ]]; then
    echo "GIT_HEAD=$GIT_HEAD_LOCAL" > /opt/nerve/.deploy_meta
    echo "DEPLOYED_AT=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /opt/nerve/.deploy_meta
    echo "[deploy] .deploy_meta geschrieben (vor Restart)"
  fi

  sudo systemctl restart $SERVICE_NAME
  echo "[deploy] Service status:"
  sudo systemctl status $SERVICE_NAME --no-pager -l
ENDHEREDOC

echo "[deploy] Done."
