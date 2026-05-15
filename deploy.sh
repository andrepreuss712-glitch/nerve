#!/bin/bash
# ── NERVE Deploy Script ─────────────────────────────────────────────────────
# Usage: ./deploy.sh [--dry-run]
# Deploys the latest main branch to the production VPS via tar-over-ssh.
# Works on Windows Git-Bash (no rsync required) and on Linux/macOS.
# Prod-SQLite NICHT überschreiben — Schema-Code (database/models.py, db.py)
# wird übertragen, .db-Dateien nicht (via tar --exclude).
# Prerequisites: SSH key auth configured for VPS_HOST, tar available locally.

set -e

VPS_HOST="root@178.104.82.166"
APP_DIR="/opt/nerve/app"
VENV_DIR="/opt/nerve/venv"
SSH_KEY="$HOME/.ssh/nerve_vps"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  echo "[deploy] DRY RUN — keine Dateien werden geändert"
fi

# Exclude list — shared between dry-run listing and real tar upload.
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

echo "[deploy] Connecting to $VPS_HOST..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[deploy] Dry-run: listing files that WOULD be transferred"
  echo "[deploy] (prod SQLite excluded — database/salesnerve.db is never touched)"
  echo "────────────────────────────────────────────────────────────"
  tar "${TAR_EXCLUDES[@]}" -cf - ./ | tar -tvf - | awk '{print $NF}' | sort
  echo "────────────────────────────────────────────────────────────"
  echo "[deploy] DRY RUN abgeschlossen — kein Remote-Setup ausgeführt."
  exit 0
fi

echo "[deploy] Uploading via tar-over-ssh (excludes: .git, .env, .planning, *.db, ...)"
# Pack locally, stream to remote, unpack into $APP_DIR. --no-same-owner
# verhindert Permission-Konflikte (remote user ist root).
tar "${TAR_EXCLUDES[@]}" -cf - ./ | \
  ssh -i "$SSH_KEY" "$VPS_HOST" "mkdir -p '$APP_DIR' && tar -xf - -C '$APP_DIR' --no-same-owner"

# Finding 2: gthread verhindert OOM durch mehrfaches spaCy-Model-Load.
# nerve.service enthaelt --worker-class gthread --workers 1 --threads 4.
# Deploy-Ordner ist vom tar ausgeschlossen — Service-Datei separat installieren.
echo "[deploy] Installing systemd service unit (gthread worker-class)..."
scp -i "$SSH_KEY" deploy/nerve.service "$VPS_HOST":/tmp/nerve.service
ssh -i "$SSH_KEY" "$VPS_HOST" "sudo cp /tmp/nerve.service /etc/systemd/system/nerve.service && sudo systemctl daemon-reload"

ssh -i ~/.ssh/nerve_vps "$VPS_HOST" bash -s << 'EOF'
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

  echo "[deploy] Writing nginx config..."
  sudo tee /etc/nginx/sites-available/nerve > /dev/null << 'NGINX'
server {
    listen 80;
    server_name getnerve.app www.getnerve.app;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name getnerve.app www.getnerve.app;

    ssl_certificate     /etc/letsencrypt/live/getnerve.app/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/getnerve.app/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 10m;

    # Stripe webhook — raw body required for signature verification
    location /payments/webhook {
        proxy_request_buffering off;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 1m;
    }

    # WebSocket support for Socket.IO
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # All other requests
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

  sudo nginx -t && sudo systemctl reload nginx
  echo "[deploy] nginx config updated and reloaded"

  echo "[deploy] Running server-side tests (SQLite-in-memory)..."
  # NOTE: conftest.py uses sqlite:///:memory: for all fixtures regardless of TEST_DATABASE_URL.
  # Echte Postgres-Test-Suite ist eigene Folge-Phase (conftest-Refactor erforderlich).
  # Cutover-Verifikation gegen Postgres erfolgt via Pre-Cutover-Alembic-Test (manuell) +
  # post-Cutover-Smoke-Test (Live-App auf Postgres).
  /opt/nerve/venv/bin/pytest /opt/nerve/app/tests/ \
    --tb=short -q > /tmp/pytest_out.txt 2>&1
  PYTEST_EXIT=$?
  tail -30 /tmp/pytest_out.txt
  if [ $PYTEST_EXIT -ne 0 ]; then
    echo "[deploy] FEHLER: Tests fehlgeschlagen (exit $PYTEST_EXIT) — kein Restart, kein Deploy"
    exit 1
  fi
  echo "[deploy] Tests bestanden"

  echo "[deploy] Restarting nerve service..."
  sudo systemctl restart nerve

  echo "[deploy] Service status:"
  sudo systemctl status nerve --no-pager -l
EOF

echo "[deploy] Done."
