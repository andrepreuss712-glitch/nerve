# NERVE Postgres Cutover Runbook (Phase 08.23.2.A)

**Cutover Window:** Sunday 23:00 (target: < 15 minutes)
**Server:** root@178.104.82.166 (Hetzner Nürnberg)
**Rollback:** < 5 minutes via DATABASE_URL revert + systemctl restart

---

## Pre-Cutover Checklist (Complete BEFORE Sunday 23:00)

- [ ] Postgres 16 installed and nerve DB created (Plan 07)
- [ ] nerve_app user connected via unix socket: `sudo -u nerve_app psql -d nerve -c "\l"`
- [ ] Dry-run migration completed (Plan 07, Section 9) — all 32 tables validated
- [ ] Postgres tables truncated after dry-run (so production migration starts fresh)
- [ ] Alembic baseline migration ready (Plan 06): `ls alembic/versions/0001_initial_postgres_schema.py`
- [ ] Verify schema-create against nerve_test before cutover: `sudo -u postgres bash -c 'cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/nerve_test /opt/nerve/venv/bin/python -c "from database.db import Base; import database.models; from sqlalchemy import create_engine; import os; engine = create_engine(os.environ[chr(34)+\"DATABASE_URL\"+chr(34)]); Base.metadata.create_all(engine); print(\"35 tables created\")"'` (Base.metadata.create_all handles circular FKs between users/profiles/organisations.coach_id automatically — manual alembic migration could not order them correctly)
- [ ] Latest code deployed via deploy.sh (includes new models.py with Call/CallEvent)
- [ ] backup_postgres.sh copied to server: `ls /opt/nerve/app/scripts/backup_postgres.sh`
- [ ] systemd backup unit files prepared (from docs/systemd-backup-setup.md)

---

## Cutover Steps (Sunday 23:00)

### Step 1 — SQLite Backup (FIRST ACTION)

```bash
# Local laptop — run BEFORE touching the server
mkdir -p ~/nerve-backups
scp -i ~/.ssh/nerve_vps root@178.104.82.166:/opt/nerve/app/database/nerve.db \
  ~/nerve-backups/nerve-sqlite-CUTOVER-$(date +%Y%m%d-%H%M%S).db
ls -la ~/nerve-backups/nerve-sqlite-CUTOVER-*.db
# Verify: file > 0 bytes with CUTOVER in filename
```

### Step 2 — Verify Postgres is Ready

```bash
ssh -i ~/.ssh/nerve_vps root@178.104.82.166
sudo -u nerve_app psql -d nerve -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';"
# Expected: 0 rows (Postgres is empty — tables will be created by Alembic + migration)
```

### Step 3 — Stop App (Start Maintenance Window)

```bash
sudo systemctl stop nerve
echo "App stopped at $(date)"
# Maintenance window is now open. Target: restart by 23:15.
```

### Step 4 — Run Migration

CORRECT ORDER: schema first (Alembic creates tables), then data (migration script inserts rows).

```bash
# Step 4a: Create Postgres schema via SQLAlchemy Base.metadata.create_all
# (the manual alembic baseline 0001 is a no-op marker — see file header for why)
# Base.metadata.create_all handles circular FKs (users<->profiles, users<->organisations.coach_id)
# automatically via SQLAlchemy's two-pass DDL strategy.
# MUST run as postgres-user: needs CREATE TABLE. ALTER DEFAULT PRIVILEGES auto-grants
# SELECT/INSERT/UPDATE/DELETE to nerve_app on every new table.
cd /opt/nerve/app
sudo -u postgres bash -c 'cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/nerve /opt/nerve/venv/bin/python scripts/create_postgres_schema.py'

# After schema is created, mark alembic at baseline:
sudo -u postgres bash -c 'cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/nerve /opt/nerve/venv/bin/alembic stamp 0001'

# Step 4b: Insert data from SQLite
# Runs as nerve_app — only INSERT/SELECT needed, no CREATE
SQLITE_URL=sqlite:///database/nerve.db \
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/python scripts/migrate_to_postgres.py
```

Expected output (32 lines like):
```
[MIGRATE] organisations: X Zeilen → Postgres OK
[VALIDATE] OK: organisations: X Zeilen
...
[MIGRATE] 32/32 Tabellen migriert und validiert
[MIGRATE] ft_call_sessions und ft_assistant_events: NICHT migriert (Test-Daten, Rebuild)
[MIGRATE] calls und call_events: NICHT migriert (neue Architektur, starten leer)
```

**If migration fails:** See Rollback section. DO NOT switch DATABASE_URL yet.

### Step 5 — Verify Migration

```bash
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/python scripts/validate_postgres_migration.py
# Expected: "32/32 Tabellen validiert, 0 Abweichungen"

# Verify ft_* tables do NOT exist:
sudo -u nerve_app psql -d nerve -c "\dt ft_call_sessions"
# Expected: "Did not find any relation named 'ft_call_sessions'"

sudo -u nerve_app psql -d nerve -c "\dt ft_assistant_events"
# Expected: "Did not find any relation named 'ft_assistant_events'"

# Verify new architecture tables EXIST (will be empty — write paths come in Phase 08.23.2.C/D):
sudo -u nerve_app psql -d nerve -c "SELECT COUNT(*) FROM calls;"
# Expected: 0 (table exists, is empty — correct for this phase)

sudo -u nerve_app psql -d nerve -c "SELECT COUNT(*) FROM call_events;"
# Expected: 0 (table exists, is empty — correct for this phase)
```

### Step 6 — Stamp Alembic (if not auto-stamped by upgrade head)

```bash
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/alembic current
# If not showing 0001, stamp manually:
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/alembic stamp 0001
```

### Step 7 — Switch DATABASE_URL to Postgres

```bash
# Edit /opt/nerve/app/.env
sed -i 's|DATABASE_URL=sqlite.*|DATABASE_URL=postgresql://nerve_app@/nerve|' /opt/nerve/app/.env
grep DATABASE_URL /opt/nerve/app/.env
# Expected: DATABASE_URL=postgresql://nerve_app@/nerve
```

### Step 8 — Restart App

```bash
sudo systemctl start nerve
sudo systemctl status nerve --no-pager -l
# Wait 10 seconds, check no crash:
sleep 10 && sudo systemctl is-active nerve
# Expected: active
```

### Step 9 — Smoke Test (on getnerve.app)

**Scope:** App boots on Postgres, login works, dashboard loads, no 500 errors.
Note: calls und call_events werden leer sein — write paths werden in Phase 08.23.2.C/D ergaenzt.
Do NOT expect rows in calls after this smoke test.

1. **Login:** https://getnerve.app → login with your account
   - Expected: HTTP 200, dashboard loads
   - Fail: HTTP 500 → ROLLBACK IMMEDIATELY

2. **Dashboard:** https://getnerve.app/dashboard
   - Expected: HTTP 200, data visible
   - Fail: HTTP 500 or blank → check journalctl

3. **Health check:**
   ```bash
   curl -s https://getnerve.app/api/health | python3 -m json.tool
   ```
   - Expected: `{"status": "ok", ...}` — no 500 error
   - backup_status will be 'missing' until first backup timer run — this is normal

4. **Check journal for errors:**
   ```bash
   journalctl -u nerve -n 30 --no-pager | grep -i error
   ```
   - Expected: 0 ERROR lines for database operations

### Step 10 — Activate Backup Timer

```bash
# Copy systemd unit files (content from docs/systemd-backup-setup.md):
sudo tee /etc/systemd/system/nerve-backup.service > /dev/null << 'EOF'
[Unit]
Description=NERVE Postgres Backup
OnFailure=nerve-backup-alert.service

[Service]
Type=oneshot
User=postgres
ExecStart=/opt/nerve/app/scripts/backup_postgres.sh
EOF

sudo tee /etc/systemd/system/nerve-backup.timer > /dev/null << 'EOF'
[Unit]
Description=Daily NERVE Postgres Backup Timer

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=15min

[Install]
WantedBy=timers.target
EOF

sudo tee /etc/systemd/system/nerve-backup-alert.service > /dev/null << 'EOF'
[Unit]
Description=NERVE Backup Failure Alert

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo "[BACKUP-ALERT] nerve-backup.service fehlgeschlagen — $(date)" | systemd-cat -t nerve-backup -p err'
EOF

sudo systemctl daemon-reload
sudo systemctl enable nerve-backup.timer
sudo systemctl start nerve-backup.timer

# Run one backup immediately to verify:
sudo systemctl start nerve-backup.service
journalctl -u nerve-backup.service -n 10
ls /opt/nerve/backups/postgres/nerve-*.sql.gz
# Expected: backup file > 0 bytes created
```

### Step 11 — Verify: Timer Active

```bash
systemctl list-timers | grep nerve-backup
# Expected: nerve-backup.timer listed with next trigger time
```

---

## Rollback Procedure (< 5 minutes)

**Trigger:** Any smoke test step fails, or app crashes after DATABASE_URL switch.

```bash
# Step 1: Revert DATABASE_URL to SQLite
sed -i 's|DATABASE_URL=postgresql.*|DATABASE_URL=sqlite:///database/nerve.db|' /opt/nerve/app/.env
grep DATABASE_URL /opt/nerve/app/.env
# Expected: DATABASE_URL=sqlite:///database/nerve.db

# Step 2: Restart app on SQLite
sudo systemctl restart nerve
sudo systemctl status nerve --no-pager

# Step 3: Verify SQLite app is healthy
curl -s https://getnerve.app/api/health
# Expected: {"status": "ok", ...}
```

SQLite file is still on server (not deleted) — app recovers to pre-migration state.

**Total rollback time: < 5 minutes** (ENV edit + systemctl restart)

---

## Post-Cutover (14 days after)

- [ ] Confirm app stable for 14 days on Postgres
- [ ] `journalctl -u nerve | grep -i "error\|exception" | grep -v "polling"` — 0 critical errors
- [ ] Backup running daily: `ls /opt/nerve/backups/postgres/nerve-*.sql.gz | wc -l` > 1
- [ ] Restore test done: `pg_restore` on nerve_test, `SELECT COUNT(*)` on 5 tables matches production
- [ ] Archive SQLite file: `mv /opt/nerve/app/database/nerve.db /opt/nerve/backups/nerve-sqlite-archived-$(date +%Y%m%d).db`
