# NERVE Postgres Backup — systemd Unit Setup (Phase 08.23.2.A)

These three unit files must be installed on the Hetzner VPS **manually after cutover (Plan 09)**.
They are NOT deployed by deploy.sh — copy them to `/etc/systemd/system/` once.

---

## Unit Files

### /etc/systemd/system/nerve-backup.service

```ini
[Unit]
Description=NERVE Postgres Backup
OnFailure=nerve-backup-alert.service

[Service]
Type=oneshot
User=postgres
ExecStart=/opt/nerve/scripts/backup_postgres.sh
```

### /etc/systemd/system/nerve-backup.timer

```ini
[Unit]
Description=Daily NERVE Postgres Backup Timer

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=15min

[Install]
WantedBy=timers.target
```

### /etc/systemd/system/nerve-backup-alert.service

```ini
[Unit]
Description=NERVE Backup Failure Alert

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo "[BACKUP-ALERT] nerve-backup.service fehlgeschlagen — $(date)" | systemd-cat -t nerve-backup -p err'
```

---

## Activation Commands (run on server after cutover)

```bash
# Script is deployed via deploy.sh into /opt/nerve/app/scripts/
# Symlink it to the expected location:
ln -sf /opt/nerve/app/scripts/backup_postgres.sh /opt/nerve/scripts/backup_postgres.sh
chmod +x /opt/nerve/scripts/backup_postgres.sh

# Install and start the timer
sudo systemctl daemon-reload
sudo systemctl enable nerve-backup.timer
sudo systemctl start nerve-backup.timer

# Test run (force one backup immediately):
sudo systemctl start nerve-backup.service
journalctl -u nerve-backup.service -n 20

# Verify backup file created (should be > 1KB):
ls -lh /opt/nerve/backups/postgres/nerve-*.sql.gz
```

---

## Monitoring

- Timer status: `systemctl status nerve-backup.timer`
- Last run logs: `journalctl -u nerve-backup.service -n 50`
- Alert logs: `journalctl -t nerve-backup -p err`
- `/api/health` returns `backup_status: ok|stale|missing` + `backup_age_hours`
- Dashboard shows yellow warning strip when `backup_status != 'ok'`
