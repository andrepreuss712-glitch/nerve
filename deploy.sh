#!/bin/bash
# ── NERVE Deploy Script ─────────────────────────────────────────────────────
# Usage: ./deploy.sh
# Deploys the latest main branch to the production VPS.
# Prerequisites: SSH key auth configured for VPS_HOST.

set -e

VPS_HOST="root@178.104.82.166"
APP_DIR="/opt/nerve/app"
VENV_DIR="/opt/nerve/venv"

echo "[deploy] Connecting to $VPS_HOST..."

ssh -i ~/.ssh/nerve_vps "$VPS_HOST" bash -s << 'EOF'
  set -e
  echo "[deploy] Pulling latest code..."
  cd /opt/nerve/app
  git pull origin main

  echo "[deploy] Installing dependencies..."
  /opt/nerve/venv/bin/pip install -r requirements.txt --quiet

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
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 1m;
    }

    # WebSocket support for Socket.IO
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
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
        proxy_pass http://127.0.0.1:5000;
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
