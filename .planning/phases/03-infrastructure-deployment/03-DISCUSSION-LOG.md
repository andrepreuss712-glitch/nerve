# Phase 3: Infrastructure & Deployment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-31
**Phase:** 03-infrastructure-deployment
**Areas discussed:** Domain choice, PyAudio split, Process management, Deploy workflow

---

## Domain choice

| Option | Description | Selected |
|--------|-------------|----------|
| nerve.sale | Short, brandable, .sale TLD | |
| getnerve.io | Fallback option | |
| nerve.app | Premium TLD, clean brand, Google-backed registry | ✓ |

**User's choice:** nerve.app
**Notes:** User confirmed directly. No deliberation required.

---

## PyAudio split

| Option | Description | Selected |
|--------|-------------|----------|
| Remove from requirements.txt (manual local install) | Simple, no extra file | |
| Split: requirements.txt + requirements-dev.txt | Clean separation, VPS installs server-only file | ✓ |
| Conditional import stub | Added complexity, not needed | |

**User's choice:** requirements-dev.txt for PyAudio
**Notes:** Server installs from requirements.txt only. Local dev installs both.

---

## Process management

| Option | Description | Selected |
|--------|-------------|----------|
| systemd | OS-native, auto-restart, starts on boot | ✓ |
| supervisor | Extra dependency, more config | |
| screen/tmux | Manual, fragile, no auto-restart | |

**User's choice:** systemd
**Notes:** Confirmed directly.

---

## Deploy workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Manual SSH + git pull + restart | No automation, error-prone | |
| deploy.sh script in repo root | One command, repeatable, no CI overhead | ✓ |
| CI/CD pipeline | Over-engineered for solo bootstrap | |

**User's choice:** deploy.sh
**Notes:** Confirmed directly. No CI, no Docker, simple is correct here.

---

## Claude's Discretion

- gunicorn thread count (default: 4 threads with gthread + 1 worker)
- nginx buffer/timeout values
- Virtualenv path on VPS
- deploy.sh host config approach (inline vs. config file)

## Deferred Ideas

None.
