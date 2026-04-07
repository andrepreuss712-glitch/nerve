#!/bin/bash
# ── NERVE Deploy Script ─────────────────────────────────────────────────────
# Usage: ./deploy.sh [--dry-run]
# Deploys the latest main branch to the production VPS via rsync.
# Prerequisites: SSH key auth configured for VPS_HOST.

set -e

VPS_HOST="root@178.104.82.166"
APP_DIR="/opt/nerve/app"
VENV_DIR="/opt/nerve/venv"

RSYNC_FLAGS="-avz --delete"
DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  RSYNC_FLAGS="$RSYNC_FLAGS --dry-run"
  DRY_RUN=1
  echo "[deploy] DRY RUN — keine Dateien werden geändert"
fi

echo "[deploy] Connecting to $VPS_HOST..."

echo "[deploy] Uploading via rsync (excludes: .git, .env, .planning, *.db, ...)"
# Prod-SQLite NICHT überschreiben — Schema-Code (database/models.py, db.py)
# wird übertragen, .db-Dateien nicht.
rsync $RSYNC_FLAGS \
  -e "ssh -i ~/.ssh/nerve_vps" \
  --exclude='.git' \
  --exclude='.gitignore' \
  --exclude='.env' \
  --exclude='.planning' \
  --exclude='.claude' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='node_modules' \
  --exclude='logs' \
  --exclude='salesnerve_log_*.txt' \
  --exclude='deploy' \
  --exclude='deploy.sh' \
  --exclude='*.db-journal' \
  --exclude='*.db-wal' \
  --exclude='*.db-shm' \
  --exclude='database/*.db' \
  --exclude='database/salesnerve.db' \
  ./ "$VPS_HOST:$APP_DIR/"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[deploy] DRY RUN abgeschlossen — kein Remote-Setup ausgeführt."
  exit 0
fi

ssh -i ~/.ssh/nerve_vps "$VPS_HOST" bash -s << 'EOF'
  set -e
  echo "[deploy] Installing dependencies..."
  /opt/nerve/venv/bin/pip install -r /opt/nerve/app/requirements.txt --quiet

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

  echo "[deploy] Restarting nerve service..."
  sudo systemctl restart nerve

  echo "[deploy] Service status:"
  sudo systemctl status nerve --no-pager -l
EOF

echo "[deploy] Done."
