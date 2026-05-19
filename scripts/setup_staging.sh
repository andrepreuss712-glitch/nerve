#!/bin/bash
# ── NERVE Staging Server Setup ────────────────────────────────────────────────
# Idempotent: zweiter Lauf bricht nicht ab (Pruefung vor jedem Schritt).
# Ausfuehren auf frischem Hetzner CX32 Debian/Ubuntu als root:
#   bash setup_staging.sh
set -e

echo "[setup] === NERVE Staging Server Setup ==="

echo "[setup] Updating apt..."
apt-get update -qq

echo "[setup] Installing packages..."
apt-get install -y \
  nginx \
  postgresql \
  postgresql-client \
  certbot \
  python3-certbot-nginx \
  python3-venv \
  python3-dev \
  libpq-dev \
  jq \
  apache2-utils

echo "[setup] Creating nerve_app system user (idempotent)..."
id nerve_app &>/dev/null || useradd --system --no-create-home --shell /bin/false nerve_app

echo "[setup] Creating directory structure..."
mkdir -p /opt/nerve/app
mkdir -p /opt/nerve/venv
mkdir -p /opt/nerve/backups/postgres
mkdir -p /opt/nerve/backups/pre-refresh
mkdir -p /etc/nerve

echo "[setup] Setting permissions..."
chown -R nerve_app:nerve_app /opt/nerve/app /opt/nerve/venv /opt/nerve/backups
chmod 755 /opt/nerve/app /opt/nerve/venv /opt/nerve/backups
chmod 700 /opt/nerve/backups/postgres /opt/nerve/backups/pre-refresh
# /etc/nerve/.env wird von Andre manuell erstellt (Secrets)
chmod 750 /etc/nerve

echo "[setup] Configuring Postgres user and databases (idempotent)..."
# nerve_app als Postgres-Peer-Auth-User (kein Passwort, Unix-Socket)
# -tAc: tuple-only + unaligned + command — verhindert False-Positive durch Row-Count-Footer "(1 row)"
su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='nerve_app'\" | grep -q 1 || psql -c \"CREATE ROLE nerve_app WITH LOGIN;\""
# nerve-Datenbank
su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='nerve'\" | grep -q 1 || psql -c \"CREATE DATABASE nerve OWNER nerve_app;\""
# nerve_test-Datenbank fuer Tests
su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='nerve_test'\" | grep -q 1 || psql -c \"CREATE DATABASE nerve_test OWNER nerve_app;\""

echo "[setup] Enabling nginx..."
systemctl enable nginx
systemctl start nginx || true

echo "[setup] === Setup abgeschlossen ==="
echo "[setup] Naechste Schritte laut RUNBOOK-staging.md:"
echo "[setup]   1. /etc/nerve/.env anlegen (Vorlage: .env.staging.example)"
echo "[setup]   2. htpasswd-Datei erstellen: htpasswd -c /etc/htpasswd.nerve-staging staging"
echo "[setup]   3. Certbot ausfuehren: certbot --nginx -d staging.getnerve.app"
echo "[setup]   4. deploy.sh staging ausfuehren"
