---
phase: 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te
plan: 01
subsystem: backend
tags: [streaming, socketio, claude, pip, consent, teleprompter, profiles]
dependency_graph:
  requires: []
  provides:
    - analysiere_mit_claude_streaming() in services/claude_service.py
    - active_sid storage in ls.state via deepgram_service.py
    - Profile.consent_text column in database/models.py
    - /api/skripte endpoint with org_id security in routes/app_routes.py
    - consent_text textarea in templates/profile_editor.html
    - skript_position instruction in _build_system_prompt()
  affects:
    - services/claude_service.py
    - services/deepgram_service.py
    - database/models.py
    - routes/app_routes.py
    - routes/profiles.py
    - templates/profile_editor.html
    - app.py
tech_stack:
  added: []
  patterns:
    - Claude streaming via client.messages.stream() with text_stream iterator
    - Socket.IO room targeting via room=sid for per-user token relay
    - org_id JOIN security pattern on /api/skripte (T-06-01)
key_files:
  created: []
  modified:
    - services/claude_service.py
    - services/deepgram_service.py
    - database/models.py
    - routes/app_routes.py
    - routes/profiles.py
    - templates/profile_editor.html
    - app.py
decisions:
  - Haiku used for streaming function per CLAUDE.md constraint (Sonnet only Post-Call)
  - room=sid targeting on all 4 pip emit types ensures no cross-user broadcast (T-06-02)
  - JOIN to profiles table in /api/skripte prevents cross-org script access (T-06-01)
  - consent_text stored as nullable Text; empty form submission saves NULL not empty string
metrics:
  duration: ~10min
  completed: "2026-04-14"
  tasks_completed: 2
  files_modified: 7
---

# Phase 06 Plan 01: Backend Infrastructure — Streaming, Consent, Teleprompter Summary

**One-liner:** PiP streaming relay via Socket.IO room targeting, active_sid routing, consent_text column + editor UI, org-scoped /api/skripte endpoint, and skript_position in Claude system prompt.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Streaming relay + sid routing + consent_text migration | b1106d5 | claude_service.py, deepgram_service.py, models.py, app.py |
| 2 | /api/skripte + skript_position prompt + consent_text editor | 19d8252 | app_routes.py, profiles.py, profile_editor.html |

## What Was Built

### Task 1
- `analysiere_mit_claude_streaming(neuer_text, kontext, sid, slot_id)` added to `services/claude_service.py` after `analysiere_mit_claude()`. Uses `claude_client.messages.stream()` with `claude-haiku-4-5-20251001`. Emits 4 Socket.IO events all targeting `room=sid`: `pip_stream_start`, `pip_token`, `pip_token_done`, `pip_stream_error`. Includes cost-hook pattern (`context_tag='pip_stream'`) and `_write_ft_assistant_event()` call matching existing patterns.
- `ls.state['active_sid'] = _sid` stored in `handle_start_live_session` in `deepgram_service.py`, after `_open_deepgram_connection()` call.
- `Profile.consent_text = Column(Text, nullable=True)` added to `database/models.py`.
- `ALTER TABLE profiles ADD COLUMN consent_text TEXT` migration block added to `app.py` migration function.

### Task 2
- `/api/skripte` endpoint added to `routes/app_routes.py`. Takes `profile_id` query param, JOINs `ProfileSkript` to `Profile` and filters `Profile.org_id == g.org.id` (T-06-01 mitigation). Returns JSON array `[{id, name, inhalt}]`.
- `skript_position` block added to `_build_system_prompt()` in `claude_service.py`: reads `aktives_skript_inhalt` and `skript_bloecke` from `ls.state`, conditionally appends teleprompter block description and JSON field instruction.
- `p.consent_text = request.form.get('consent_text', ...).strip() or None` added to `bearbeiten()` POST handler in `routes/profiles.py`.
- Consent text `<textarea>` with `name="consent_text"` and `{{ profile.consent_text or '' }}` pre-fill added to `templates/profile_editor.html`.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

All new surfaces were in the plan's threat model and mitigated:

| Flag | File | Description |
|------|------|-------------|
| T-06-01 mitigated | routes/app_routes.py | /api/skripte JOINs profiles + filters org_id |
| T-06-02 mitigated | services/claude_service.py | All pip emit calls use room=sid (verified: 4 matches) |

## Known Stubs

- `skript_bloecke` in `ls.state` is read by the system prompt builder but not yet populated server-side. Plan 03 will wire frontend JS to send script blocks at `start_live_session`. The teleprompter block in the prompt is silently skipped when `skript_bloecke` is empty — no broken behavior.
- `aktives_skript_inhalt` similarly populated by Plan 03.

## Self-Check: PASSED

- `services/claude_service.py` contains `def analysiere_mit_claude_streaming` — FOUND
- `services/deepgram_service.py` contains `ls.state['active_sid'] = _sid` — FOUND
- `database/models.py` contains `consent_text` — FOUND
- `app.py` contains `ALTER TABLE profiles ADD COLUMN consent_text` — FOUND
- `routes/app_routes.py` contains `/api/skripte` and `Profile.org_id == g.org.id` — FOUND
- `services/claude_service.py` contains `skript_position` — FOUND
- `routes/profiles.py` contains `consent_text` — FOUND
- `templates/profile_editor.html` contains `name="consent_text"` and `profile.consent_text` — FOUND
- Commit b1106d5 — FOUND
- Commit 19d8252 — FOUND
