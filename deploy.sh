#!/bin/bash
# ── NERVE Deploy Script ─────────────────────────────────────────────────────
# Usage: ./deploy.sh
# Deploys the latest main branch to the production VPS.
# Prerequisites: SSH key auth configured for VPS_HOST.

set -e

VPS_HOST="root@YOUR_VPS_IP"   # ← Replace with your Hetzner VPS IP before first use
APP_DIR="/opt/nerve/app"
VENV_DIR="/opt/nerve/venv"

echo "[deploy] Connecting to $VPS_HOST..."

ssh "$VPS_HOST" bash -s << EOF
  set -e
  echo "[deploy] Pulling latest code..."
  cd $APP_DIR
  git pull origin main

  echo "[deploy] Installing dependencies..."
  $VENV_DIR/bin/pip install -r requirements.txt --quiet

  echo "[deploy] Restarting nerve service..."
  sudo systemctl restart nerve

  echo "[deploy] Service status:"
  sudo systemctl status nerve --no-pager -l
EOF

echo "[deploy] Done."
