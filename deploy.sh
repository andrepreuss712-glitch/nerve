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
  # ── Production-Target (Staging-Gate ENTFERNT 2026-06-01) ───────────────
  # Andre-Decision: Staging ist bis zur letzten Phase vor Launch KOMPLETT aus
  # dem Workflow. Production ist der einzige Deploy-/Test-Pfad (manual-direct-prod).
  # Das alte Staging-Pre-Deploy-Gate (Health/Frische/HEAD-Match gegen staging.getnerve.app)
  # wird als Staging-Promotion-Pipeline in der LETZTEN Phase vor Launch reaktiviert
  # (Phase 08.23.2.STAGING). Siehe ROADMAP.md + CLAUDE.md "Deploy-Realitaet".
  echo "[deploy] TARGET=production — direkter Deploy (kein Staging-Gate, Pre-Launch-Modus)"

  VPS_HOST="root@178.104.82.166"
  SSH_KEY="$HOME/.ssh/nerve_vps"
  SERVICE_NAME="nerve"

elif [[ "$TARGET" == "staging" ]]; then
  VPS_HOST="root@178.104.245.8"
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
  --exclude='./_design_export'
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

  # Phase 08.23.2.SCHILD (CLAUDE.md Punkt 23): Schild-Guard als SEPARATE Stufe — laeuft als nerve_app
  # (peer-auth) gegen Postgres-pg_description aller 3 Schemas. NICHT im root-SQLite-Lauf oben (der
  # skippt mangels DSN; root kann nerve_app peer-auth nicht). Blockt den Deploy, wenn eine
  # Tabelle/Spalte kein Schild (>=10 Zeichen) hat. Eingehaengt NACH dem ersten GRUEN-Deploy
  # (Migration 0015), damit der eigene Setup-Deploy nicht blockiert wurde (Deadlock-Schutz).
  echo "[deploy] Schild-Guard (pg_description, public/crm/training)..."
  if sudo -u nerve_app bash -c 'cd /opt/nerve/app && NERVE_SCHILD_TEST_DSN=postgresql://nerve_app@/nerve /opt/nerve/venv/bin/pytest tests/test_schild_guard.py -q -p no:cacheprovider'; then
    echo "[deploy] Schild-Guard GRUEN"
  else
    echo "[deploy] FEHLER: Schild-Guard ROT — Tabelle/Spalte ohne Schild. Kein Restart, kein Deploy."
    exit 1
  fi

  # REVIEW-HIGH-2 FIX: .deploy_meta VOR systemctl restart schreiben
  # Datei muss existieren bevor Service neu startet — sonst liest /api/health
  # beim ersten Request nach Restart noch stale/keine Daten.
  # .deploy_meta fuer BEIDE Targets schreiben (Fix 2026-06-01: vorher nur staging
  # -> /api/health zeigte auf Production stale git_head). Vor systemctl restart.
  echo "GIT_HEAD=$GIT_HEAD_LOCAL" > /opt/nerve/.deploy_meta
  echo "DEPLOYED_AT=\$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> /opt/nerve/.deploy_meta
  echo "[deploy] .deploy_meta geschrieben (vor Restart)"

  sudo systemctl restart $SERVICE_NAME
  echo "[deploy] Service status:"
  sudo systemctl status $SERVICE_NAME --no-pager -l
ENDHEREDOC

echo "[deploy] Done."
