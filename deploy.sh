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

  # ── Phase 08.23.2.PGTEST: Echtes Postgres-Test-Gate gegen Wegwerf-nerve_test ──
  # Ersetzt die alte SQLite-in-memory-Stufe. Baut nerve_test per pg_dump-Restore vom
  # Prod-nerve (Schema+RLS+FORCE+GRANTs+Comments) + alembic_version-Stamp-Dump + upgrade head
  # (nur neue Revs ueber prod-head, z.B. 0015->0016 — keine 0002-Kollision), prueft inline die
  # Dump-Treue (crm-RLS/FORCE/GRANTs — fail-closed False-Green-Guard), faehrt pytest mit
  # DATABASE_URL (A-1) + 4 nerve_test-DSNs dagegen, prueft POST-SUITE die crm.*/training.*-Baseline
  # (sudo postgres, RLS-bypassed) und raeumt garantiert via trap ab. Fail-closed pro Schritt.
  echo "[deploy] Postgres-Test-Gate: provisioniere Wegwerf-nerve_test (pg_dump-Restore vom Prod-nerve)..."

  # (1) Whitelist-Guard (D-02, T-PGTEST-05): TEST_DB ist EINZIGE Namensquelle; != nerve_test -> Abbruch statt Raten.
  TEST_DB="nerve_test"
  if [ "\$TEST_DB" != "nerve_test" ]; then
    echo "[deploy] FATAL: Test-DB-Name != nerve_test — Abbruch (Prod-Schutz D-02)"; exit 1
  fi

  # (2) trap cleanup EXIT (D-06, T-PGTEST-10): DROP nerve_test garantiert auch bei Test-Fehler/SIGTERM.
  cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" 2>/dev/null || true; }
  trap cleanup EXIT

  # (3) Pre-Run-DROP (D-06): verwaiste nerve_test (existiert evtl. von hartem Vorlauf-Abbruch) wegraeumen.
  sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" || { echo "[deploy] FEHLER: Pre-Run-DROP nerve_test fehlgeschlagen"; exit 1; }

  # (4) CREATE OWNER postgres (T-PGTEST-09): NICHT nerve_app — sonst crm-Tabellen owner-bypassen RLS (False-Green).
  sudo -u postgres psql -c "CREATE DATABASE \"\$TEST_DB\" OWNER postgres;" || { echo "[deploy] FEHLER: CREATE DATABASE nerve_test fehlgeschlagen"; exit 1; }

  # (5) Schema-Dump vom Prod-nerve (read-only auf nerve), MIT owners+privileges (NICHT --no-privileges/--no-owner —
  #     die GRANTs/Owner tragen die RLS-Treue). set -o pipefail (T-PGTEST-08): sonst maskiert psql-Exit-0 einen
  #     pg_dump-Crash -> leere DB -> silent False-Green.
  sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: pg_dump --schema-only nerve → nerve_test fehlgeschlagen"; exit 1; }

  # (6) Stamp-Row-Dump (alembic_version = prod-head) MIT pipefail, damit upgrade nur neue Revs anwendet (T-PGTEST-15).
  sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: alembic_version-Stamp-Dump → nerve_test fehlgeschlagen"; exit 1; }

  # (7) upgrade head (NICHT hardcoden, D-09): wendet nur Revs ueber prod-head an (z.B. 0015->0016) — keine 0002-Kollision.
  sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/\$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" || { echo "[deploy] FEHLER: alembic upgrade head gegen nerve_test fehlgeschlagen"; exit 1; }

  # (8) INLINE DUMP-TREUE-KATALOG-GATE (Gemini-HIGH, T-PGTEST-09 — automatisierter False-Green-Guard, NACH upgrade, VOR pytest):
  #     harte fail-closed Counts — wenn der Dump RLS/FORCE/GRANTs NICHT treu trug, bricht der Deploy hier.
  POLICIES=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "\$TEST_DB")
  [ "\$POLICIES" -ge 7 ] || { echo "[deploy] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz greift)"; exit 1; }
  FORCED=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "\$TEST_DB")
  [ "\$FORCED" -ge 5 ] || { echo "[deploy] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
  GRANTS=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "\$TEST_DB")
  [ "\$GRANTS" -ge 5 ] || { echo "[deploy] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
  echo "[deploy] Dump-Treue-Katalog-Gate OK: crm-Policies=\$POLICIES, FORCE=\$FORCED, anon-SELECT-GRANTs=\$GRANTS"

  # (9) pytest gegen nerve_test — ANON_PW via Env an sudo, \`env\` als KOMMANDO (#1 BLOCKER, T-PGTEST-32),
  #     single-quoted inner bash -c (T-PGTEST-06: PW nie als String-Literal interpoliert), DATABASE_URL gesetzt (A-1, T-PGTEST-18).
  ANON_PW=\$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)
  echo "[deploy] pytest gegen DATABASE_URL=postgresql://nerve_app@/\$TEST_DB (+ 4 Test-DSNs)"
  sudo -u nerve_app env ANON_PW="\$ANON_PW" TEST_DB="\$TEST_DB" bash -c '
    cd /opt/nerve/app && \
    DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
    TEST_DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
    NERVE_APP_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
    NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
    ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:\${ANON_PW}@127.0.0.1:5432/\${TEST_DB}" \
    /opt/nerve/venv/bin/pytest tests/ --tb=short -q
  ' || { echo "[deploy] FEHLER: pytest gegen nerve_test ROT — kein Restart, kein Deploy"; exit 1; }
  echo "[deploy] pytest gegen nerve_test bestanden"

  # (10) POST-SUITE-Baseline-Check (HYBRID, André locked; T-PGTEST-29 + T-PGTEST-30; NACH pytest, VOR trap-Teardown):
  #      sudo -u postgres psql (peer-auth, passwordless, SCHILD-Muster — KEINE Env-Var, KEIN PW). Als postgres RLS-bypassed
  #      ueber ALLE Tenants. (a) jede crm.* Tabelle == 0 Rows (Cross-Tenant-Leak-Guard) UND (b) training.transcript_archive
  #      == 0 (ORM-lose, non-public; Anonymizer-Leak-Guard). Plan 01's in-pytest-Waechter prueft NUR public.*.
  CRM_LEFTOVER=\$(sudo -u postgres psql -tAc "SELECT coalesce(sum(c),0) FROM (SELECT count(*) c FROM crm.account_memory UNION ALL SELECT count(*) FROM crm.accounts UNION ALL SELECT count(*) FROM crm.contacts UNION ALL SELECT count(*) FROM crm.meetings UNION ALL SELECT count(*) FROM crm.user_preferences) s" -d "\$TEST_DB")
  [ "\$CRM_LEFTOVER" = "0" ] || { echo "[deploy] FEHLER: crm.* nicht leer nach Test-Lauf (\$CRM_LEFTOVER Leak-Rows) -- Security-Test-Teardown liess Daten liegen (Cross-Tenant-Leak ODER fehlendes cleanup_rows)"; exit 1; }
  TRAINING_LEFTOVER=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM training.transcript_archive" -d "\$TEST_DB")
  [ "\$TRAINING_LEFTOVER" = "0" ] || { echo "[deploy] FEHLER: training.transcript_archive nicht leer nach Test-Lauf (\$TRAINING_LEFTOVER Leak-Rows) -- test_anonymizer_worker-Teardown liess Daten liegen (#4 HIGH non-public-Schema-Leak)"; exit 1; }
  echo "[deploy] POST-SUITE Baseline-Check OK: alle crm.* Tabellen leer + training.transcript_archive leer (0 Leak-Rows)"
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
