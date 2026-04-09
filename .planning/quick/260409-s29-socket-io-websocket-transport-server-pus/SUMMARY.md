---
task: 260409-s29
title: Socket.IO WebSocket transport + server push ergebnis
type: quick
completed: 2026-04-09
---

# 260409-s29: Socket.IO WebSocket + Server Push

**One-liner:** Migrated Flask-SocketIO to eventlet async_mode, switched client to WebSocket-first transport, and replaced `/api/ergebnis` HTTP polling with server-side `socketio.emit('ergebnis', ...)` push from `analyse_loop` — saves 0-500ms per result.

## Changes

### Part 1 — Server: eventlet migration
- `requirements.txt` L3: added `eventlet>=0.35.0`
- `app.py` L1-6: `import eventlet; eventlet.monkey_patch()` as the very first executable lines
- `app.py` L39: `async_mode='threading'` → `async_mode='eventlet'`

### Part 2 — systemd unit (local prep only)
- `deploy/nerve.service` L20-26: `--worker-class gthread` → `--worker-class eventlet`, removed `--threads 4`

### Part 3 — Server push
- `services/claude_service.py` ~L889-918: new block after readiness/active_hint state-write. Snapshots under `state_lock`, emits via `from extensions import socketio as _sio; _sio.emit('ergebnis', push_payload)`. 15-field payload mirrors `/api/ergebnis`. Try/except wrapped so emit failures never break analysis.
- `routes/app_routes.py::api_ergebnis` unchanged — stays as reconnect/baseline fallback.

### Part 4 — Client
- `static/app.js` L4-10: `transports: ['websocket', 'polling']` + `upgrade: true`
- `static/app.js` L684-722: `pollErgebnis` setTimeout chain removed, replaced with `socket.on('ergebnis', handleErgebnis)` + one-shot baseline GET on page load
- `static/app.js` L553: `window._pollingActive` flag retained for external compat

### Nginx — no change
`deploy/nginx.conf` L51-64 already sets `proxy_http_version 1.1` + Upgrade/Connection headers + 3600s timeouts.

## Manual Deploy Checklist (VPS: nerve@getnerve.app)

```bash
# 1. Push & pull
git push origin main
ssh nerve@getnerve.app
cd /opt/nerve/app && git pull

# 2. Install eventlet
source /opt/nerve/venv/bin/activate
pip install 'eventlet>=0.35.0'

# 3. Deploy systemd unit
sudo cp /opt/nerve/app/deploy/nerve.service /etc/systemd/system/nerve.service
sudo systemctl daemon-reload

# 4. Restart & watch
sudo systemctl restart nerve
sudo journalctl -u nerve -f
# Watch for: eventlet startup clean; no [socketio-push] emit failed; Deepgram connects

# 5. Smoke test
# https://getnerve.app/live → mock session
# DevTools Network → WS tab must show wss:// (not polling)
# Einwand cards appear without 500ms poll lag

# 6. Rollback (if needed)
cd /opt/nerve/app
git revert 54d726a ec406bb 8c384a3 f196942
sudo cp deploy/nerve.service /etc/systemd/system/nerve.service
sudo systemctl daemon-reload && sudo systemctl restart nerve
```

## Risks & Notes

- **deepgram-sdk thread compatibility:** SDK uses its own worker threads; eventlet patches socket+threading globally so SDK threads become greenlets with cooperative socket I/O. **Untested with our specific SDK version under eventlet** — smoke test on first VPS run. If transcription stalls → rollback.
- **Single worker mandatory:** `--workers 1` required for eventlet + Socket.IO (sticky session state). Horizontal scale requires Redis message queue (out of scope).
- **`/api/ergebnis` retained:** one-shot baseline + reconnect-resync fallback.
- **Payload parity:** push payload mirrors REST response 1:1 (15 fields). Future `/api/ergebnis` fields must be mirrored in `claude_service.py::push_payload`.

## Latency
- **Before:** poll every 500ms → worst-case 500ms stale
- **After:** emit on state-write → worst-case ~network RTT
- **Expected savings:** avg ~250ms per Einwand→card render

## Commits
- f196942 build(260409-s29): add eventlet dep + monkey_patch, switch SocketIO async_mode=eventlet
- 8c384a3 chore(260409-s29): update nerve.service to eventlet worker class
- ec406bb feat(260409-s29): server push ergebnis via socketio.emit from analyse_loop
- 54d726a feat(260409-s29): client listens for socket 'ergebnis' event, remove poll chain

## Verification
- `python -c "import eventlet; import app"` → OK
- `pytest tests/services/test_ki_logik.py` → 35 passed
- `grep setTimeout(pollErgebnis static/app.js` → 0 matches
- `grep socket.on('ergebnis' static/app.js` → match
- `grep async_mode='eventlet' app.py` → match
- `grep --worker-class eventlet deploy/nerve.service` → match
