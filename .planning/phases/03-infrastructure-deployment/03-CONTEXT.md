# Phase 3: Infrastructure & Deployment - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the app to a Hetzner CX22 VPS, secure the production domain, configure nginx + gunicorn with WebSocket proxying, and harden the codebase for server-side operation (no PyAudio, fail-fast SECRET_KEY, SQLite WAL, locked CORS). Phase 3 gates Phase 4 (Stripe webhooks require a live HTTPS endpoint).

**Hard gate:** Phase 4 (Payments) depends on this phase — Stripe webhook delivery requires a public HTTPS URL.

</domain>

<decisions>
## Implementation Decisions

### Domain

- **D-01:** Register and use **nerve.app** as the production domain. This is the canonical domain for all SSL config, nginx server_name, cors_allowed_origins, and Stripe webhook URL. All other domain candidates (nerve.sale, getnerve.io) are deferred.

### PyAudio / Requirements Split

- **D-02:** Split requirements into two files:
  - `requirements.txt` — server requirements only. Remove `pyaudio` entirely.
  - `requirements-dev.txt` — local dev extras. Add `pyaudio>=0.2.14` here.
  VPS installs from `requirements.txt` only. Local dev installs both. No conditional import logic needed — PyAudio is only used during local live sessions, never on the server.

### Process Management

- **D-03:** Use **systemd** to manage gunicorn on the VPS. Create a unit file (`/etc/systemd/system/nerve.service`) that:
  - Runs gunicorn with `--worker-class gthread --workers 1 --threads 4`
  - Restarts on crash (`Restart=always`)
  - Starts on boot (`WantedBy=multi-user.target`)
  - Loads environment from `/etc/nerve/.env` (not committed to git)

### Deploy Workflow

- **D-04:** Create a `deploy.sh` script in the repo root. It should:
  1. SSH to the VPS
  2. `git pull origin main`
  3. `pip install -r requirements.txt` (in virtualenv)
  4. `sudo systemctl restart nerve`
  5. Print status confirmation
  Run locally as `./deploy.sh` — no CI, no Docker, no complexity.

### Code Hardening

- **D-05:** Add fail-fast assertion for SECRET_KEY in `app.py` (or `config.py`): if `SECRET_KEY == 'dev-secret-change-me'` and `not app.debug`, raise `RuntimeError` and exit. This blocks production startup with an insecure key.

- **D-06:** Enable SQLite WAL mode in `database/db.py`. Execute `PRAGMA journal_mode=WAL` on engine connect event (SQLAlchemy `@event.listens_for(engine, 'connect')` pattern). WAL improves read concurrency for the multi-threaded Flask-SocketIO setup.

- **D-07:** Lock `cors_allowed_origins` in `app.py` to `"https://nerve.app"` (read from env var `CORS_ORIGIN` with fallback to `"*"` only in debug mode). This satisfies LEGAL-04.

### nginx Configuration

- **D-08:** nginx config must include WebSocket upgrade headers for Socket.IO:
  ```
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  ```
  Without these, Socket.IO falls back to polling instead of `101 Switching Protocols`.

### Claude's Discretion

- Exact gunicorn `--threads` count (4 is a reasonable default for gthread with 1 worker — adjust if needed based on VPS RAM).
- nginx buffer sizes and timeout values — standard defaults are fine for this traffic level.
- Virtualenv location on VPS (`/opt/nerve/venv` or similar).
- Whether `deploy.sh` uses a direct SSH command or reads a config file for the host.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Infrastructure & Deployment — INFRA-01 through INFRA-05 and LEGAL-04 define acceptance criteria

### Existing Code (read before modifying)
- `app.py` line 25 — `cors_allowed_origins="*"` to be locked (D-07)
- `config.py` line 9 — `SECRET_KEY` default to be hardened (D-05)
- `database/db.py` — WAL pragma to be added (D-06)
- `requirements.txt` — pyaudio to be removed (D-02)

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py` — environment loading pattern already established; SECRET_KEY hardening fits here naturally
- `database/db.py` — SQLAlchemy engine already initialized; WAL pragma hooks in here

### Established Patterns
- `.env` file via `python-dotenv` for all config — VPS env follows same pattern
- `cors_allowed_origins` is a single SocketIO init param in `app.py` line 25 — one-line fix

### Integration Points
- `app.py` line 25: SocketIO init — CORS origin change
- `config.py`: SECRET_KEY hardening
- `database/db.py`: WAL pragma on engine connect
- `requirements.txt`: PyAudio removal → `requirements-dev.txt`
- New files: `deploy.sh`, `nginx.conf`, `nerve.service` (systemd unit)

</code_context>

<specifics>
## Specific Ideas

- Domain: **nerve.app** (locked)
- Server: Hetzner CX22 (~4€/month, DE datacenter — DSGVO compliant)
- gunicorn worker class: **gthread**, 1 worker (Flask-SocketIO threading requirement)
- Process manager: **systemd** (not supervisor, not screen)
- Deploy: **deploy.sh** in repo root (not CI, not Docker)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-infrastructure-deployment*
*Context gathered: 2026-03-31*
