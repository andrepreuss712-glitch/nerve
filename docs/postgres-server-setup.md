# Postgres Server Setup — Hetzner VPS (178.104.82.166)

**Phase:** 08.23.2.A — SQLite → Postgres Migration
**Purpose:** Install and configure Postgres 16 on the Hetzner server 3-5 days before
cutover (D-16). Allows dry-run testing before the production maintenance window.

> **IMPORTANT:** DATABASE_URL must NOT be changed in .env during this setup.
> The app continues running on SQLite. DATABASE_URL is switched ONLY in Plan 09
> Step 7 (the cutover maintenance window), after migration succeeds and the app
> is stopped. Setting it early would cause app restarts to fail before migration
> is complete.

---

## Section 1: Pre-Setup — SQLite Backup (FIRST — before anything)

Run this from your **local laptop terminal** before touching the server:

```bash
mkdir -p ~/nerve-backups

scp -i ~/.ssh/nerve_vps root@178.104.82.166:/opt/nerve/app/database/nerve.db \
  ~/nerve-backups/nerve-sqlite-$(date +%Y%m%d-%H%M%S).db

echo "Backup timestamp: $(date)" >> ~/nerve-backups/backup-log.txt
```

Verify the backup:

```bash
ls -la ~/nerve-backups/nerve-sqlite-*.db
# Must show a file > 0 bytes
```

---

## Section 2: Postgres 16 Installation

SSH into the server:

```bash
ssh -i ~/.ssh/nerve_vps root@178.104.82.166
```

Install Postgres 16:

```bash
apt update
apt install -y postgresql-16 postgresql-client-16

# Verify installation
systemctl status postgresql
psql --version
# Expected: psql (PostgreSQL) 16.x
```

---

## Section 3: Create Databases

Run as the `postgres` system user (exact SQL from D-13):

```bash
sudo -u postgres psql
```

```sql
-- UTF-8 + German locale, template0 required for custom collation
CREATE DATABASE nerve
  WITH ENCODING 'UTF8'
       LC_COLLATE='de_DE.UTF-8'
       LC_CTYPE='de_DE.UTF-8'
       TEMPLATE template0;

CREATE DATABASE nerve_test
  WITH ENCODING 'UTF8'
       LC_COLLATE='de_DE.UTF-8'
       LC_CTYPE='de_DE.UTF-8'
       TEMPLATE template0;
```

Verify:

```sql
\l
-- Should show nerve and nerve_test with de_DE.UTF-8 collation
\q
```

If `de_DE.UTF-8` locale is not available, generate it first:

```bash
locale-gen de_DE.UTF-8
update-locale
# Then retry Section 3
```

---

## Section 4: Create Users with Restricted Permissions

Run as the `postgres` user (exact SQL from D-14):

```bash
sudo -u postgres psql
```

```sql
-- Create nerve_app user (production) — no password: unix socket peer auth
CREATE USER nerve_app;

-- Create nerve_test_user (test DB only) — no password: peer auth
CREATE USER nerve_test_user;

-- ── nerve DB permissions ──────────────────────────────────────────────────
-- Explicitly NO DROP/CREATE/ALTER/TRUNCATE — limits blast radius of app compromise
GRANT CONNECT ON DATABASE nerve TO nerve_app;
GRANT USAGE ON SCHEMA public TO nerve_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nerve_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nerve_app;

-- ALTER DEFAULT PRIVILEGES: future tables from 08.23.2.F/G/H are automatically accessible
-- without a manual GRANT per follow-on phase
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nerve_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO nerve_app;

-- ── nerve_test DB permissions ─────────────────────────────────────────────
GRANT CONNECT ON DATABASE nerve_test TO nerve_test_user;
\c nerve_test
GRANT USAGE ON SCHEMA public TO nerve_test_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nerve_test_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nerve_test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nerve_test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO nerve_test_user;

\q
```

---

## Section 5: Configure Unix Socket Auth

Edit `pg_hba.conf` (exact config from D-15):

```bash
nano /etc/postgresql/16/main/pg_hba.conf
```

Add these lines **BEFORE** the default `local all all peer` line:

```
# nerve production app
local   nerve       nerve_app                           peer
# nerve test runner
local   nerve_test  nerve_test_user                     peer
```

Disable TCP entirely in `postgresql.conf`:

```bash
nano /etc/postgresql/16/main/postgresql.conf
```

Find and set:

```
listen_addresses = ''
```

Reload Postgres to apply changes:

```bash
systemctl reload postgresql
```

---

## Section 6: Configure Linux Users for Peer Auth

Postgres peer auth requires a matching Linux user. The production app runs via
`gunicorn`. Create a dedicated `nerve_app` Linux user so `pg_hba.conf` peer auth
matches:

```bash
# Create dedicated nerve_app system user (no home, no shell)
adduser --system --no-create-home --shell /bin/false nerve_app

# Update /etc/systemd/system/nerve.service to run gunicorn as nerve_app:
# User=nerve_app
# (Edit the service file and reload)
systemctl daemon-reload

# Verify which user gunicorn currently runs as:
ps aux | grep gunicorn
```

If the app already runs as `www-data` and changing the service user is not yet
feasible, create a matching Postgres role:

```bash
sudo -u postgres createuser --no-superuser --no-createdb --no-createrole www-data 2>/dev/null || true
# Then update pg_hba.conf: replace nerve_app with www-data
```

---

## Section 7: Verify Connection

Test that peer auth works end-to-end:

```bash
sudo -u nerve_app psql -d nerve -c "SELECT current_database(), current_user, version();"
# Expected output: nerve | nerve_app | PostgreSQL 16.x (...)
```

Test nerve_test as nerve_test_user:

```bash
sudo -u nerve_test_user psql -d nerve_test -c "SELECT current_database(), current_user;"
# Expected: nerve_test | nerve_test_user
```

Confirm TCP is disabled:

```bash
sudo -u postgres psql -c "SHOW listen_addresses;"
# Expected: empty string (no TCP)
```

Confirm DATABASE_URL in app .env is still SQLite (must NOT be changed yet):

```bash
grep DATABASE_URL /opt/nerve/app/.env
# Must still show: sqlite:///database/nerve.db
```

---

## Section 8: DATABASE_URL — DO NOT SET YET

DATABASE_URL must NOT be written to `.env` during this setup phase. The app is
still running on SQLite. If DATABASE_URL is set now, any app restart before
cutover will attempt to connect to Postgres before migration is complete and fail.

DATABASE_URL is switched exclusively in Plan 09 Step 7 (the cutover maintenance
window), AFTER the migration succeeds and the app is stopped.

**This step is intentionally left empty.** Move on to dry-run testing (Section 9)
once Section 7 verification passes.

---

## Section 9: Dry-Run Test (3-5 days before cutover)

Run this on the server at least 3-5 days before the cutover Sunday. The app
continues serving SQLite traffic during this test — do NOT set DATABASE_URL in
.env during dry-run.

```bash
cd /opt/nerve/app

# Step 1: Dry-run (reads SQLite, writes to Postgres, verifies counts, rolls back)
SQLITE_URL=sqlite:///database/nerve.db \
DATABASE_URL=postgresql://nerve_app@/nerve \
DRY_RUN=1 \
/opt/nerve/venv/bin/python scripts/migrate_to_postgres.py
```

If the dry-run passes (row counts match, no validation errors):

```bash
# Step 2: Actual migration into Postgres
SQLITE_URL=sqlite:///database/nerve.db \
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/python scripts/migrate_to_postgres.py
```

```bash
# Step 3: Validate migrated data
DATABASE_URL=postgresql://nerve_app@/nerve \
/opt/nerve/venv/bin/python scripts/validate_postgres_migration.py
```

After dry-run succeeds, truncate all Postgres tables so the production cutover
starts from a clean state. TRUNCATE requires superuser — `nerve_app` has no
TRUNCATE privilege (C-3 design constraint), so run as `postgres`:

```bash
sudo -u postgres psql -d nerve -c "
  DO \$\$ DECLARE r RECORD;
  BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
      EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
  END \$\$;
"
```

The cutover window (Plan 09 Step 7) will then re-run the migration against live
production SQLite data, followed by the DATABASE_URL switch.

---

## Quick Reference — Verification Checklist

After completing all setup steps, verify:

| Check | Command | Expected |
|-------|---------|----------|
| Postgres running | `systemctl status postgresql` | active (running) |
| nerve DB exists | `sudo -u postgres psql -c "\l"` | nerve listed |
| nerve_test DB exists | `sudo -u postgres psql -c "\l"` | nerve_test listed |
| Collation correct | `sudo -u postgres psql -c "\l"` | de_DE.UTF-8 |
| nerve_app connects | `sudo -u nerve_app psql -d nerve -c "SELECT 1;"` | 1 row |
| nerve_test_user connects | `sudo -u nerve_test_user psql -d nerve_test -c "SELECT 1;"` | 1 row |
| TCP disabled | `sudo -u postgres psql -c "SHOW listen_addresses;"` | (empty) |
| DATABASE_URL unchanged | `grep DATABASE_URL /opt/nerve/app/.env` | sqlite:/// |
| SQLite backup on laptop | `ls ~/nerve-backups/nerve-sqlite-*.db` | file > 0 bytes |
