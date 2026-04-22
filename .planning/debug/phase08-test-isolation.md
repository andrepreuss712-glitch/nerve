---
status: investigating
trigger: "Fix 4 Phase-08 test isolation failures surfacing only in full pytest suite. 4 tests pass in isolation but fail when suite runs together."
created: 2026-04-22T00:00:00Z
updated: 2026-04-22T00:00:00Z
---

## Current Focus

reasoning_checkpoint:
  hypothesis: "Python's 'import services.live_session as X' statement resolves the submodule via the 'live_session' attribute on the 'services' package object, NOT via sys.modules lookup. When app.py is imported by another test (triggering _load_initial_profile at app.py:1535 which mutates the real live_session globals via set_active_profile), the 'services' package caches the real live_session module as its 'live_session' attribute. The test's monkeypatch.setitem(sys.modules, 'services.live_session', _LSMock) only patches sys.modules — it does NOT replace the attribute on the services package. Therefore 'import services.live_session as ls' inside build_profile_context returns the REAL module with the planted NERVE data, not the mock."
  confirming_evidence:
    - "Minimal repro: after 'import app', manually setting sys.modules['services.live_session'] = _LSMock then calling 'import services.live_session as ls' inside a function returns the REAL module (id(ls) == id(real), NOT id(_LSMock))"
    - "Minimal repro: setting ALSO services.live_session = _LSMock on the package object (in addition to sys.modules) makes 'import services.live_session as ls' return the mock — confirming the package attribute is the resolution path"
    - "In isolation mode, the 'services' package does NOT have a 'live_session' attribute before the test runs — so sys.modules fallback works. In full-suite mode, 'import app' transitively loads services.live_session and sets the attribute, breaking the mock."
  falsification_test: "Add an additional 'monkeypatch.setattr' call that replaces the attribute on the services package. If the test still fails, the hypothesis is wrong. Expected: test passes because 'import services.live_session as ls' now returns the mock."
  fix_rationale: "Root cause is a test-mock incompleteness — production code is correct and uses standard 'import services.live_session as ls'. Fix is test-local: enhance _bind helper / _LSMock injection so that the services package attribute is also patched. This makes the mock truly isolate the tests regardless of whether 'services.live_session' was previously imported. No production code changes needed."
  blind_spots: "Does monkeypatch correctly restore the package attribute at teardown? Need to verify that after the test, services.live_session reverts to the real module so other tests still see real live_session. Also: are there any tests that depend on the CURRENT behavior (unlikely but worth verifying)."

test: Apply fix — add monkeypatch.setattr on services package attribute in both test files. Re-run full suite.
expecting: All 4 failing tests pass; 17/17 isolation tests still pass; only the 2 out-of-scope exchange_rates tests remain failed.
next_action: Edit tests/test_prompt_pipeline.py and tests/test_ewb_pipeline.py to enhance the mock-injection helper.

## Symptoms

expected: |
  test_build_ewb_prompt_anrede_du: 'Anrede: Du' in out
  test_build_profile_context_no_active_profile: build_profile_context returns ''
  test_build_profile_context_includes_phase_08_fields: 'Firma XY' in out
  test_build_profile_context_anrede_session_override_wins: 'Anrede: Du.' in out

actual: |
  test_build_ewb_prompt_anrede_du: out contains 'Anrede: Sie. WICHTIG: Nutze konsequent Sie-Form...'
  test_build_profile_context_no_active_profile: returns NERVE profile text (Unternehmen: NERVE..., Produkt: NERVE ist...)
  test_build_profile_context_includes_phase_08_fields: out has NERVE default data, 'Firma XY' fixture not applied
  test_build_profile_context_anrede_session_override_wins: out has 'Anrede: Sie.'

errors: |
  AssertionError: assert 'Anrede: Du' in 'Anrede: Sie. WICHTIG: Nutze konsequent Sie-Form...'
  AssertionError: assert '' == 'Unternehmen: NERVE...'
  AssertionError: assert 'Firma XY' in '...'
  AssertionError: assert 'Anrede: Du.' in '...Anrede: Sie...'

reproduction: |
  python -m pytest -q --tb=short
  All 4 tests pass when run standalone:
  python -m pytest tests/test_prompt_pipeline.py tests/test_ewb_pipeline.py -q

started: "Phase 08 implementation (Plans 08-02, 08-05, 08-06)"

## Eliminated

## Evidence

- timestamp: 2026-04-22T initial
  checked: full-suite pytest run
  found: 4 targeted tests fail + 2 exchange_rates fail (out of scope). Error output contains "Unternehmen: NERVE KI-Echtzeit-Vertriebsassistent..." — this is the real NERVE profile, planted by _seed_demo_profile and loaded into live_session via _load_initial_profile at app.py line 1535.
  implication: build_profile_context returns real NERVE data, which means either (a) the mock _LSMock is not reaching build_profile_context, or (b) the import inside build_profile_context resolves to the REAL services.live_session module, not the _LSMock

- timestamp: 2026-04-22T initial
  checked: app.py line 1535
  found: `_load_initial_profile()` is called unconditionally at app-import time. It does `ls_mod.set_active_profile(profile.name, daten)` which mutates the real live_session module's active_profile_name and active_profile_data globals.
  implication: Any test module that imports `app` (directly or transitively via `from app import ...` or `import app`) triggers this mutation. The mutation persists in the real live_session module for the rest of the pytest process.

- timestamp: 2026-04-22T initial
  checked: tests/test_prompt_pipeline.py lines 115-125
  found: Test uses `monkeypatch.setitem(sys.modules, 'services.live_session', _LSMock)`. But `prompt_pipeline.build_profile_context` does `import services.live_session as ls` internally. If `services.live_session` was already imported BEFORE the setitem (e.g., because the test session started with `import services.live_session` or `from services.live_session import ...` in a conftest or another test file), Python's `import` statement looks up in sys.modules — so setitem SHOULD work.
  implication: Need to verify the setitem is actually replacing what `import services.live_session as ls` returns.

## Resolution

root_cause:
fix:
verification:
files_changed: []
