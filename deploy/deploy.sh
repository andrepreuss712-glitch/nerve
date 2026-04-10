#!/bin/bash
# NERVE Deploy Script — lokale Git Bash → VPS
# Usage: bash deploy/deploy.sh
set -e

VPS="root@178.104.82.166"
REMOTE_DIR="/opt/nerve/app"

echo "[1/4] Packing..."
tar czf /tmp/nerve-deploy.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='.planning' --exclude='database/*.db' .

echo "[2/4] Uploading..."
scp /tmp/nerve-deploy.tar.gz "$VPS:/tmp/"

echo "[3/4] Deploying + fixing permissions..."
ssh "$VPS" "cd $REMOTE_DIR && tar xzf /tmp/nerve-deploy.tar.gz && chown -R www-data:www-data database && chmod 664 database/*.db && systemctl restart nerve && systemctl restart nerve-rt && rm /tmp/nerve-deploy.tar.gz"

echo "[4/4] Health check..."
ssh "$VPS" "curl -s http://127.0.0.1:8001/health && echo '' && systemctl is-active nerve && systemctl is-active nerve-rt"

echo "Deploy complete."
