---
phase: 03-infrastructure-deployment
plan: 02
subsystem: deployment
tags: [nginx, systemd, gunicorn, deploy, websocket, ssl]
dependency_graph:
  requires: []
  provides: [deploy.sh, deploy/nginx.conf, deploy/nerve.service]
  affects: [VPS provisioning, production deploy workflow]
tech_stack:
  added: [nginx reverse proxy config, systemd service unit, gunicorn gthread]
  patterns: [HTTP-to-HTTPS redirect, WebSocket upgrade headers, systemd EnvironmentFile]
key_files:
  created:
    - deploy.sh
    - deploy/nginx.conf
    - deploy/nerve.service
  modified: []
decisions:
  - "VPS_HOST left as YOUR_VPS_IP placeholder — only the user knows the Hetzner IP"
  - "gthread worker class with 1 worker + 4 threads — matches D-03 for CX22 (2 vCPU, 4 GB RAM) with Socket.IO"
  - "WebSocket proxy_read_timeout and proxy_send_timeout set to 3600s for long-lived Socket.IO connections"
  - "www → apex redirect uses separate server block to avoid nginx 'if is evil' anti-pattern"
metrics:
  duration: 3 minutes
  completed: 2026-03-31T08:41:00Z
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 03 Plan 02: Deployment Artifacts Summary

**One-liner:** Three VPS deployment artifacts — deploy.sh one-command script, nginx SSL+WebSocket config, and systemd gunicorn service unit — all copy-paste ready for Hetzner CX22 provisioning.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create deploy.sh in repo root | 2396ccc | deploy.sh |
| 2 | Create deploy/nginx.conf and deploy/nerve.service | 7053dcb | deploy/nginx.conf, deploy/nerve.service |

## What Was Built

### deploy.sh (repo root)

One-command deploy script run from developer's laptop. Sets `VPS_HOST="root@YOUR_VPS_IP"` as the single placeholder to fill. Executes over SSH: `git pull origin main` → `pip install -r requirements.txt` → `sudo systemctl restart nerve` → `systemctl status nerve` for post-deploy verification.

### deploy/nginx.conf

Full nginx configuration for nerve.app:
- HTTP server block (port 80): redirects all traffic to `https://nerve.app` (301)
- www server block (HTTPS): separate redirect block for www → apex, avoids "if is evil" anti-pattern
- HTTPS server block (port 443): SSL via Let's Encrypt (`/etc/letsencrypt/live/nerve.app/`), proxy to gunicorn on `127.0.0.1:8000`, WebSocket upgrade headers (`proxy_http_version 1.1`, `Upgrade $http_upgrade`, `Connection "upgrade"`), generous timeouts (3600s) for long-lived Socket.IO connections

### deploy/nerve.service

systemd unit file for the gunicorn process:
- `WorkingDirectory=/opt/nerve/app`, `User=www-data`
- `EnvironmentFile=/etc/nerve/.env` — secrets never in repo
- `ExecStart`: gunicorn with `--worker-class gthread --workers 1 --threads 4 --bind 127.0.0.1:8000 --timeout 120`
- `Restart=always`, `RestartSec=5s` — auto-restarts on failure
- Security hardening: `NoNewPrivileges=true`, `PrivateTmp=true`

## Decisions Made

- **VPS_HOST placeholder:** Left as `YOUR_VPS_IP` — the only value that requires user input. All other paths, ports, and domain names are fixed per architecture decisions.
- **gthread 1+4:** Matches D-03. Flask-SocketIO requires threading mode; gthread with 4 threads optimized for CX22 (2 vCPU, 4 GB RAM).
- **Separate www redirect block:** Avoids nginx "if is evil" anti-pattern where conditional redirects inside a server block can cause unexpected behavior.
- **3600s WebSocket timeouts:** Socket.IO connections are long-lived (full sales calls); default 60s would disconnect active sessions.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all three files are complete and copy-paste ready. The `YOUR_VPS_IP` placeholder in deploy.sh is intentional and documented in the file itself.

## Self-Check: PASSED

- deploy.sh exists at repo root: FOUND
- deploy/nginx.conf exists: FOUND
- deploy/nerve.service exists: FOUND
- Commit 2396ccc (deploy.sh): FOUND
- Commit 7053dcb (nginx.conf + nerve.service): FOUND
