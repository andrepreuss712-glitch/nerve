# Testing Patterns

**Analysis Date:** 2026-05-01

## Test Framework

**Runner:**
- pytest
- Config: `pytest.ini` at project root (single setting: `norecursedirs = tests/archive`)

**Assertion Library:**
- pytest built-in `assert` statements
- `unittest.TestCase` assertions (`self.assertEqual`, `self.assertIn`, `self.assertTrue`) in older test files that use class-based `unittest.TestCase`

**Run Commands:**
```bash
pytest                          # Run all tests (excludes tests/archive/)
pytest tests/test_ki_logik.py   # Single file
pytest -s                       # Show print output (useful for latency scaffolds)
pytest -k "test_name"           # Run matching tests
```

**No coverage enforcement.** No `.coveragerc`, no `--cov` in pytest.ini. Coverage is not measured automatically.

## Test File Organization

**Location:** All tests in `tests/` at project root (flat, not co-located with source).

**Subdirectories:**
- `tests/services/` — service-layer unit tests (currently only `test_ki_logik.py`)
- `tests/fixtures/` — fixture data files (e.g., `stripe_invoice.json`)
- `tests/archive/` — excluded from pytest run; dead/superseded tests kept for reference
- `tests/tts_samples/` — audio sample files for TTS tests

**Naming convention:** `test_<phase_or_domain>_<description>.py`
- Phase-tagged: `test_08_5_03_integration.py`, `test_08_13_01_config_constants.py`, `test_08_19_01_profile_schema.py`
- Domain-tagged: `test_ewb_pipeline.py`, `test_auth_next_redirect.py`, `test_session_scoping.py`
- Both styles coexist; phase-tagged names are newer

**Scale:** 466 test functions across ~45 active test files (~6,500 lines total).

## Shared Fixtures (`tests/conftest.py`)

Three fixtures are available to all test files without import:

**`sample_state`** — factory fixture for `ki_logik` state dicts:
```python
def test_foo(sample_state):
    state = sample_state(readiness_score=50)   # override specific keys
    state = sample_state()                      # all defaults
```

**`db_session`** — in-memory SQLite session, schema pre-created:
```python
def test_foo(db_session):
    obj = MyModel(...)
    db_session.add(obj)
    db_session.commit()
    result = db_session.query(MyModel).first()
    assert result.field == expected
```
The fixture yields the session and closes it in `finally` — matches the project's own try/finally DB pattern.

**`client`** — Flask test client with in-memory SQLite:
```python
def test_foo(client):
    resp = client.get('/some/route', follow_redirects=False)
    assert resp.status_code == 302
```
- Rebinds `database.db.engine`, `database.db.SessionLocal`, `database.db.db_session` to in-memory SQLite via `monkeypatch`
- Sets `TESTING=True`, `WTF_CSRF_ENABLED=False`
- Exposes `client._test_session` for direct DB writes in test setup

**`db_from_client`** — alias for `client._test_session`:
```python
def test_foo(client, db_from_client):
    user = _make_user(db_from_client, 'test@example.com')
    with client.session_transaction() as s:
        s['user_id'] = user.id
    resp = client.get('/protected/route')
    assert resp.status_code == 200
```

## Test Structure

**File-level docstring** (required in newer files):
```python
"""
tests/test_session_scoping.py
Phase 08.19.4: DSGVO-Pflicht-Tests — SID-Isolation
Prueft dass kein Cross-User-State-Contamination moeglich ist.
Alle Tests sind Runtime-Behavior-Tests (keine Source-Presence-Checks).
"""
```

**Section separators** inside test files use the same project-wide convention:
```python
# ── detect_phase (Phase 04.8 P02 hysteresis) ─────────────────────────────────
# ── Per-SID Coaching Buffer Isolation (WR-03 — DSGVO) ────────────────────────
```

**Class-based grouping** for related tests (newer style):
```python
class TestPerSidProfileIsolation:
    def test_two_sids_independent_profiles(self): ...
    def test_disconnect_cleanup(self): ...

class TestPerSidCoachingBufferIsolation:
    def test_two_sids_independent_coaching_buffers(self): ...
```

**Function-based tests** for simple cases (older style, still common):
```python
def test_detect_phase_forward_high_conf_advances():
    new, conf = detect_phase(3, 0.75, current_phase=2)
    assert new == 3
    assert conf == 0.75
```

**Teardown via try/finally for state cleanup:**
```python
def test_two_sids_independent_profiles(self):
    sid_a = 'test-sid-user-a'
    sid_b = 'test-sid-user-b'
    try:
        ls.set_profile_for_sid(sid_a, 'Profil A', {'unternehmen': 'Firma A'})
        # ... assertions ...
    finally:
        _clean_sids(sid_a, sid_b)   # always clean up module-level state
```

## Test Quality Rule — Integration Assertion vs. Source-Presence False Green

This rule is enforced project-wide (defined in `CLAUDE.md`). It is the single most important testing principle.

**VALID test** — tests runtime behavior that can break without source changes:
- DB write/read: query on real or in-memory DB, assert on result row or field value
- Function call return: call function (with monkeypatched I/O), assert on return value
- State mutation: check dict/object state after function call
- API response: HTTP request or Socket emit, assert on response body or status code
- `inspect.signature()`: checks runtime API interface (parameter names) — OK

**SOURCE-PRESENCE FALSE GREEN — delete on sight:**
- `inspect.getsource(fn)` + `assert 'string' in src`
- `hasattr(module, 'symbol')` as "protection from deletion"
- `open('file.py').read()` + `assert 'string' in src`
- `subprocess.run(['grep', ...])` on source files
- `src.count('function_call(')` pattern

**Edge case:** `inspect.getsource` for regex patterns enforcing runtime constraints (e.g., "no Opus model in live-loop") is acceptable ONLY if no function-call mock can test the constraint directly. Must be documented with a comment explaining why.

## Mocking

**Framework:** `unittest.mock` (`MagicMock`, `patch`, `call`)

**Standard pattern — patching service dependencies:**
```python
from unittest.mock import MagicMock, patch

def test_einwand_unknown_high_conf_emits_slot1():
    with patch('services.qa_pipeline.classify_utterance',
               return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
         patch('services.qa_pipeline.generate_qa_response',
               return_value='Gute Antwort'), \
         patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
         patch('services.claude_service._qa_load_tabu', return_value=[]):
        dispatch('text', 'line-10', '', ls_mock, sio_mock)
        calls = [str(c) for c in sio_mock.emit.call_args_list]
        assert any('qa_slot1' in c for c in calls)
```

**DB injection via monkeypatch (preferred over patch):**
```python
monkeypatch.setattr('database.db.SessionLocal', lambda: _Fake(db_session))
```

**`_Fake` adapter pattern** — wraps pytest session, no-ops `close()`:
```python
class _Fake:
    def __init__(self, real):
        self._r = real
    def query(self, *a, **k): return self._r.query(*a, **k)
    def add(self, *a, **k): return self._r.add(*a, **k)
    def commit(self): return self._r.commit()
    def close(self): pass   # do NOT close the shared pytest session
```
This pattern appears in `test_ewb_pipeline.py`, `test_prompt_pipeline.py`, and others that test DB-backed services.

**Claude API mock:**
```python
def _make_claude_mock(response_text):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock()]
    mock_msg.content[0].text = response_text
    mock_msg.usage = None
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client
```

**What to mock:**
- External API calls (Anthropic, Deepgram, ElevenLabs, Stripe)
- `database.db.SessionLocal` when testing services that open their own sessions
- `services.live_session` module when testing pipelines (avoid import side-effects)
- Socket.IO emit: `sio = MagicMock()` then assert `sio.emit.call_args_list`

**What NOT to mock:**
- In-memory SQLite for DB-layer tests (use `db_session` fixture directly)
- Pure Python business logic functions (`ki_logik.py`, `profile_schema.py`)
- The Flask test client's internal routing

## Test Helper Patterns

**Seeding DB records (inline helpers):**
```python
def _make_user(db_session, email='test@test.de'):
    org = Organisation(name='T', plan='starter')
    db_session.add(org)
    db_session.flush()
    u = User(org_id=org.id, email=email, passwort_hash='x', market='dach')
    db_session.add(u)
    db_session.commit()
    return org, u
```
Pattern: always `flush()` before referencing the new object's `id` in a foreign key. Commit after all objects are added.

**Simulating authentication in Flask client tests:**
```python
with client.session_transaction() as s:
    s['user_id'] = user.id
resp = client.get('/protected/route')
assert resp.status_code == 200
```

**Seeding prompt versions for pipeline tests:**
```python
def _seed_variants(db_session, module='ewb', versions=('v1-legacy', 'v2-modular')):
    for v in versions:
        db_session.add(PromptVersion(
            module=module, version=v, prompt_text=f'text-{v}',
            is_active=True, is_default=(v == versions[0]),
            changelog=f'test-{v}',
        ))
    db_session.commit()
```

**Cleaning module-level state (live_session tests):**
```python
def _clean_sids(*sids):
    for sid in sids:
        ls.pop_session_state(sid)
# Always called in finally block
```

**Latency scaffold (manually run):**
```python
@pytest.mark.skip(reason="Manual latency scaffold — run explicitly to measure")
def test_latency_scaffold_n_sessions():
    ...
```
Use `pytest.mark.skip` for manual-only tests; they stay in the suite but are skipped in CI.

## Coverage Areas

**Well-covered:**

| Area | Test File(s) |
|---|---|
| KI-Logik pure functions (phase detection, readiness score, hints, EWB buttons) | `tests/services/test_ki_logik.py` |
| Auth redirect, open-redirect protection, `safe_next()` | `test_auth_next_redirect.py` |
| Per-SID isolation, DSGVO scoping, thread-safety | `test_session_scoping.py` |
| Profile schema Pydantic validation + migration v1→v3 | `test_profile_schema_v3.py`, `test_08_19_01_profile_schema.py` |
| EWB pipeline prompt assembly + seed idempotency | `test_ewb_pipeline.py` |
| Prompt pipeline (version resolution, caching, env overrides) | `test_prompt_pipeline.py` |
| QA pipeline (classify, generate, tabu filter) | `test_qa_pipeline.py`, `test_qa_pipeline_rueckfrage.py` |
| Cost tracker (FX freeze, missing rate, EUR-currency) | `test_cost_tracker.py` |
| Admin dashboard auth gate (unauthenticated, non-admin 403, superadmin 200) | `test_admin_dashboard_auth.py` |
| EWB rate API (3-state whitelist, ownership, Anrede override) | `test_ewb_rate_api.py` |
| Config constants (MODEL_* defaults, CACHE_* booleans) | `test_08_13_01_config_constants.py` |
| Fine-tuning lifecycle, models, seeds, write hooks | `test_ft_lifecycle.py`, `test_ft_models.py`, `test_ft_seed.py`, `test_ft_write_hooks.py` |
| Exchange rates, EUR calculator | `test_exchange_rates.py`, `test_eur_calculator.py` |
| Keyword matcher (match/dedup, kw_fired_for_line state) | `test_einwand_keyword_matcher.py` |
| analyse_loop dispatcher (kw guard, classify routing, tabu filter, emit paths) | `test_08_5_03_integration.py` |
| Ghost-SID guard + deadlock stress (live_session) | `test_live_session_ghost_sid.py` |
| Precall schema | `test_precall_schema.py` |
| Branche migration | `test_branche_migration.py` |
| Tabu migration | `test_tabu_migration.py` |
| A/B stats | `test_ab_stats.py` |
| Training pipeline (T1, T2) | `test_08_5_05_training_pipeline_t1.py`, `test_08_5_05_training_pipeline_t2.py` |
| Briefing lifecycle + KI-script personalization routes | `test_08_20_3.py` |

**Coverage Gaps (not covered by automated tests):**

| Area | Gap | Risk |
|---|---|---|
| `services/deepgram_service.py` | Live session STT start/stop, audio chunk handling | High — no test for Deepgram integration path |
| `services/live_session.py` — analyse_loop threading | The background analyse_loop itself (threaded) is not tested end-to-end | High — thread coordination bugs invisible |
| `routes/app_routes.py` `/live` route | Main live interface template rendering, session start flow | Medium |
| `routes/dashboard.py` | Dashboard data aggregation, log parsing | Medium |
| `routes/training.py` | Training scenario selection, TTS invocation | Medium |
| `routes/payments.py` + Stripe webhook | Payment flow, webhook signature validation | High — billing logic untested |
| `routes/oauth.py` | Google/Microsoft OAuth flow | Medium |
| `services/coaching_service.py` | Coaching tip generation pipeline | Low (called inside analyse_loop) |
| `services/crm_service.py` | CRM data extraction from Claude | Low |
| WebSocket/Socket.IO events | Real-time transcript/coaching emit | High — only mocked in unit tests, no integration |
| Template rendering correctness | HTML output of Jinja2 templates | Low (manual UAT) |
| Multi-org data isolation at route level | Cross-org query filtering | Medium — scoping enforced at ORM level, not route-level tested |

## Test Types in Use

**Unit tests (pure function):** `tests/services/test_ki_logik.py` — no mocks, no DB, pure assertions on return values. The target pattern for all new business logic.

**Service integration tests (in-memory DB):** Most test files. Use `db_session` fixture to test DB-backed services without Flask context. SessionLocal is monkeypatched to route calls to the test DB.

**Flask integration tests (full request cycle):** Use `client` fixture. Tests hit real Flask routes through the test client, with in-memory SQLite. Auth state simulated via `session_transaction()`. Examples: `test_admin_dashboard_auth.py`, `test_auth_next_redirect.py`.

**Thread-safety / concurrency tests:** `test_session_scoping.py`, `test_live_session_ghost_sid.py`. Use `threading.Thread` directly, barrier synchronization, check for cross-contamination after joins.

**Schema validation tests:** Pydantic-only, no DB required. `test_profile_schema_v3.py` tests `model_validate()` raises/passes. Class-based grouping (`TestExtraForbid`, `TestMigrateV3`).

**Config/constant tests:** `test_08_13_01_config_constants.py`. Reload `config` module fresh per test via `importlib.reload()`, assert constant values.

**E2E tests:** Not present. Manual UAT documented in phase handoff docs.

---

*Testing analysis: 2026-05-01*
