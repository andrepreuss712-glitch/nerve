---
phase: quick
plan: 260414-kf8
subsystem: precall, profile-editor, live-ai
tags: [profile, precall, live-session, prompt-engineering]
dependency_graph:
  requires: []
  provides: [profile-leitfaden-fields, precall-profile-context, live-precall-briefing]
  affects: [profile-editor, precall-service, live-ai-prompt]
tech_stack:
  added: []
  patterns: [profile-context-injection, socket-event-payload-extension]
key_files:
  created: []
  modified:
    - templates/profile_editor.html
    - services/precall_service.py
    - routes/app_routes.py
    - services/live_session.py
    - static/pip-launcher.js
    - services/deepgram_service.py
    - services/claude_service.py
decisions:
  - opener/erlaubnis/pitch stored as top-level keys in profile daten JSON (not nested under leitfaden)
  - precall_briefing truncated to 2000 chars max before storing in live state
  - precall briefing injected read-only via GIL-safe ls.state.get() in claude_service
metrics:
  duration: ~20 minutes
  completed: 2026-04-14T12:49:26Z
  tasks_completed: 3
  files_modified: 7
---

# Phase quick Plan 260414-kf8: PreCall & Profil Upgrade Summary

**One-liner:** Profile editor gains Gespraechsleitfaden section (opener/erlaubnis/pitch), PreCall analysis injects active profile context into Claude briefing, and live AI system prompt receives PreCall briefing as Firmenkontext.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Profil-Editor — Neue Sektion Gespraechsleitfaden | 5005b41 | templates/profile_editor.html |
| 2 | PreCall-Analyse — Profil injizieren | 7901e7a | services/precall_service.py, routes/app_routes.py |
| 3 | Live-KI — PreCall-Briefing in den Call-Prompt | 081143e | services/live_session.py, static/pip-launcher.js, services/deepgram_service.py, services/claude_service.py |

## What Was Built

### Task 1: Profile Editor — Gespraechsleitfaden Section
- New sidebar link at position 2 ("Gespraechsleitfaden") between Basis & Produkt and Zielgruppe
- All subsequent sidebar links renumbered (Zielgruppe→3 through KI-Anweisungen→13)
- New `sec-leitfaden` div with three textarea fields: opener, erlaubnis, pitch
- All sec-title-num spans updated to match new numbering (13 sections total)
- `buildAndSubmit()` collects opener/erlaubnis/pitch as top-level keys in the daten JSON
- `init()` loads existing values into the new fields on profile edit

### Task 2: PreCall Analysis — Profile Injection
- `recherche_firma()` accepts optional `profil_daten` dict parameter
- `_generiere_briefing()` appends "Vertriebsprofil des Beraters" block to user_msg when profile provided
- Profile context includes: produktbeschreibung, USPs, Zielgruppe/berufsstatus, opener, pitch
- PRECALL_SYSTEM_PROMPT extended with rule to connect company insights with sales profile
- `api_precall_research` route loads active profile from session (active_profile_id) and passes it
- Backward compatible: PreCall without active profile continues to work unchanged

### Task 3: Live AI — PreCall Briefing Injection
- `live_session.state` gains `precall_briefing: None` key
- `reset_session()` clears `precall_briefing` on session end
- `pip-launcher.js` passes `precallBriefing.text` as `precall_briefing` in `start_live_session` emit
- `deepgram_service.handle_start_live_session()` extracts, validates (max 2000 chars), and stores briefing
- `claude_service._build_system_prompt()` appends briefing under `## Firmenkontext (aus PreCall-Recherche)` when present
- Live sessions without PreCall research continue to work (precall_briefing stays None)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all three features are fully wired end-to-end.

## Self-Check: PASSED

Files verified:
- templates/profile_editor.html: FOUND (sec-leitfaden, vi_opener, vi_erlaubnis, vi_pitch, DATEN.opener)
- services/precall_service.py: FOUND (recherche_firma profil_daten param, Vertriebsprofil des Beraters)
- routes/app_routes.py: FOUND (profil_daten= in api_precall_research, active_profile_id)
- services/live_session.py: FOUND (precall_briefing in state dict and reset_session)
- static/pip-launcher.js: FOUND (precall_briefing in start_live_session emit)
- services/deepgram_service.py: FOUND (precall_briefing extraction in handle_start_live_session)
- services/claude_service.py: FOUND (Firmenkontext, precall_briefing in _build_system_prompt)

Commits verified:
- 5005b41: feat(quick-260414-kf8): add Gespraechsleitfaden section to profile editor
- 7901e7a: feat(quick-260414-kf8): inject active profile into PreCall analysis
- 081143e: feat(quick-260414-kf8): inject PreCall briefing into live AI system prompt
