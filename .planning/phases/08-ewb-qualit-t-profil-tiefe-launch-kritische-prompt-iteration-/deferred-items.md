# Phase 08 — Deferred Items

## From Plan 08-05 execution (2026-04-22)

### 1. Test-Order-Dependence in `test_ewb_pipeline.py::test_build_ewb_prompt_v1_legacy`

**Symptom:** Running any test that uses the `client` pytest fixture (from
`tests/conftest.py`) followed by `test_ewb_pipeline.py::test_build_ewb_prompt_v1_legacy`
causes the latter to fail: the `_empty_active_profile` fixture's
`monkeypatch.setitem(sys.modules, 'services.live_session', _LSMock)` does not take
effect. `build_profile_context` then reads the real NERVE default profile, producing
`Anrede: Du` instead of the expected `Anrede: Sie`.

**Reproducer (on main BEFORE this plan's commits):**
```
pytest tests/test_admin_dashboard_auth.py::test_unauthenticated_redirects_to_login \
       tests/test_ewb_pipeline.py::test_build_ewb_prompt_v1_legacy
```
Both tests pre-date Plan 08-05. The failure is pre-existing — see 08-03-SUMMARY
"Open Item" and plan 08-03 Known Regression.

**Isolation:** `pytest tests/test_ewb_pipeline.py::test_build_ewb_prompt_v1_legacy`
on its own passes. `pytest tests/test_ewb_rate_api.py` (all 12 tests) passes.

**Root cause (hypothesis):** The `_empty_active_profile` fixture replaces
`sys.modules['services.live_session']` with a bare class mock. Once any other test
has imported `app` (via the `client` fixture), the real `services.live_session` module
is bound into internal caches / attribute resolutions that bypass the
`sys.modules`-based lookup in `prompt_pipeline.py`. The mock is simply not picked up
by the `import services.live_session as ls` statement inside
`build_profile_context` under this condition.

**Scope:** Rule-4 architectural change to the pytest fixture design in
`tests/test_ewb_pipeline.py`. Out of scope for Plan 08-05 (Plan 08-05 adds the
rating-API + anrede override UI; it does not own the ewb_pipeline test harness).

**Fix candidates (for a future plan):**
- Rework `_empty_active_profile` to patch
  `services.prompt_pipeline.build_profile_context` directly instead of
  `sys.modules`.
- Or autouse-scope a module-level fixture in `test_ewb_pipeline.py` that forcibly
  clears `ls.state` before each test AND patches `get_active_profile` on the REAL
  module.
- Or make `build_profile_context` accept a `get_active_profile` injection arg.

### 2. Browser smoke (Deploy-side verification)

Plan 08-05 delivers UI (3-Button Rating + Du/Sie Launcher-Row) that requires
deployed app verification: Rating-Button click → network 200 + visual state change,
PiP-Launcher Step 3 shows Du/Sie with active state, Anrede persists across step-back
navigation. Unit tests verify the wiring; deploy-time manual smoke verifies the
rendered result. This is standard final-QA, not a deferred bug.
