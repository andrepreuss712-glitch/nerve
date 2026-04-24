# Testing Patterns

**Analysis Date:** 2026-04-24

## Test Framework

**Runner:**
- pytest - Python testing framework
- Config: `tests/conftest.py` (no pytest.ini — uses pytest defaults)
- Run Commands:
```bash
pytest tests/                    # Run all tests
pytest tests/ -v                 # Verbose output
pytest tests/ -k test_name       # Run specific test
pytest tests/ --tb=short         # Short traceback format
pytest tests/ -x                 # Stop on first failure
pytest tests/test_cost_tracker.py::test_freeze_fx_on_write  # Run single test
```

**Assertion Library:**
- pytest built-in assertions: `assert x == y`
- No external assertion library (unittest.mock used for mocking)

**Watch Mode:** Not configured. Manual re-run via pytest command.

**Coverage:** Not enforced. No pytest-cov configuration detected.

## Test File Organization

**Location:**
- Co-located with source: `tests/` directory mirrors project structure
- `tests/services/test_ki_logik.py` for `services/ki_logik.py`
- `tests/test_cost_tracker.py` for `services/cost_tracker.py`

**Naming:**
- Test files: `test_*.py` or `*_test.py` convention
- Test functions: `test_*()` prefix required by pytest
- Fixtures: Defined in conftest or inline with `@pytest.fixture` decorator

**Structure:**
```
tests/
├── conftest.py                    # Shared fixtures (sample_state, db_session, client)
├── test_cost_tracker.py
├── test_eur_calculator.py
├── test_ki_logik.py
├── services/
│   └── test_ki_logik.py
└── ... (35+ test files total)
```

## Test Structure

**Suite Organization:**

Example from `tests/services/test_ki_logik.py`:

```python
"""Unit tests for services/ki_logik.py pure functions (Phase 04.8 P01).

Covers compute_readiness_score, select_active_hint, dynamic_ewb_buttons
and the user override: einwand_geloest = +20 (not briefing's +15).
"""

# Import section (functions, fixtures)

# Test function group with inline comments
# ── detect_phase (Phase 04.8 P02 hysteresis) ────────────────────────────────

def test_detect_phase_same_phase_passes_through():
    assert detect_phase(3, 0.42, current_phase=3) == (3, 0.42)


def test_detect_phase_forward_low_conf_blocked():
    # Comment explains test logic if non-obvious
    new, conf = detect_phase(3, 0.6, current_phase=2)
    assert new == 2
    assert conf == 0.6
```

**Patterns:**
- No setup/teardown functions — fixtures used instead via `@pytest.fixture` and parameter injection
- Fixtures defined in `conftest.py`: `sample_state`, `db_session`, `client`, `db_from_client`
- Each test is independent (no shared state between tests)
- Comments mark logical test groups: `# ── Group Name ────────────────────`

## Mocking

**Framework:** unittest.mock (Python standard library)

**Patterns:**

Example from `tests/test_cost_tracker.py:36-45`:

```python
@pytest.fixture
def patched_sessionlocal(db_session, monkeypatch):
    """Point database.db.SessionLocal at the in-memory test engine so that
    log_api_cost() writes into the same DB as the test fixture."""
    bind = db_session.get_bind()
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=bind, autocommit=False, autoflush=False)
    monkeypatch.setattr(_db_mod, 'SessionLocal', TestSession)
    return TestSession
```

**What to Mock:**
- Database session: Use pytest's `db_session` fixture with in-memory SQLite
- External APIs: Mock via monkeypatch (Anthropic, Deepgram, ElevenLabs calls not tested)
- Module-level state: Use monkeypatch to replace SessionLocal, engine, etc.

**What NOT to Mock:**
- Database queries — use real SQLAlchemy in-memory DB fixture
- Business logic functions — test actual implementation, not mocks
- Helper functions — test end-to-end behavior

**Example:** `tests/test_cost_tracker.py:48-51` demonstrates testing with missing rate (should not raise):

```python
def test_missing_rate_no_raise(db_session, patched_sessionlocal):
    # KEIN seeded_rate — log should silently skip
    log_api_cost('unknown', 'noop', user_id=1, units=5, unit_type='per_minute')
    assert db_session.query(ApiCostLog).count() == 0
```

## Fixtures and Factories

**Test Data:**

Example from `tests/conftest.py:19-38`:

```python
@pytest.fixture
def sample_state():
    """Factory returning a fresh state dict with all Phase 04.8 keys at defaults."""
    def _make(**overrides):
        base = {
            "current_phase": 1,
            "current_phase_name": "Opener",
            "phase_confidence": 0.0,
            "phase_changed_at": None,
            "phase_change_count": 0,
            "readiness_score": 30,
            "readiness_bucket": "cold",
            "score_factors_seen": {},
            "active_hint": None,
            "ewb_buttons": None,
            "cold_call_inference": None,
        }
        base.update(overrides)
        return base
    return _make
```

Usage in tests: `state = sample_state(score_factors_seen={'detailfrage': 1})` (see `tests/services/test_ki_logik.py:87-94`)

**Database Fixture:** In-memory SQLite engine created per test

```python
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
```

**Flask Test Client:** Rebinds database to in-memory for integration tests

```python
@pytest.fixture
def client(monkeypatch):
    """Flask test client with in-memory SQLite rebinding."""
    engine = _ce("sqlite:///:memory:", connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    TestSession = _sm(autocommit=False, autoflush=False, bind=engine)
    TestScoped = _ss(TestSession)
    
    monkeypatch.setattr(_db_mod, 'engine', engine)
    monkeypatch.setattr(_db_mod, 'SessionLocal', TestSession)
    monkeypatch.setattr(_db_mod, 'db_session', TestScoped)
    
    # ... Flask app setup
    with flask_app.test_client() as c:
        c._test_session = TestSession()
        c._test_engine = engine
        yield c
```

See `tests/conftest.py:55-91` for full implementation.

**Location:**
- `tests/conftest.py` — shared fixtures for all tests
- Inline fixtures in test files if specific to that file

## Coverage

**Requirements:** Not enforced. No pytest-cov configuration or CI check detected.

**Test Count:** 35+ test files present:
- Unit tests: `test_ki_logik.py`, `test_cost_tracker.py`, `test_eur_calculator.py`, etc.
- Integration tests: `test_ft_lifecycle.py`, `test_phase_08_models.py`
- Route tests: `test_admin_dashboard_auth.py`, `test_auth_next_redirect.py`

**Known Coverage Gaps:**
- No tests for `static/app.js` (JavaScript not tested)
- No tests for `static/pip-launcher.js`
- Some route handlers in `routes/` not explicitly tested
- No E2E tests for full session flow

## Test Types

**Unit Tests:**
- Scope: Pure functions, single component in isolation
- Approach: Call function with inputs, assert output
- Example: `tests/services/test_ki_logik.py:20-34` — tests `detect_phase()` with different confidence/phase transitions
- No database access (unless mocked fixture used)
- Examples: `test_cost_tracker.py`, `test_eur_calculator.py`, `services/test_ki_logik.py`

**Integration Tests:**
- Scope: Multiple components working together, often with database
- Approach: Set up fixtures, call route/service, assert database state changed
- Example: `tests/test_ft_lifecycle.py` — tests full training flow with DB writes
- Uses `db_session` fixture for real database operations
- Uses `client` fixture for Flask route testing
- Example: `tests/test_cost_tracker.py:36-45` — `test_freeze_fx_on_write()` calls service function, checks DB result

**E2E Tests:**
- Status: Not detected. No Selenium, Playwright, or WebDriver tests
- No browser-based session flow tests

## Common Patterns

**Async Testing:**

Example from `tests/test_prompt_pipeline.py` (if async routes tested):

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

Status: Async testing framework (`pytest-asyncio`) not detected. Flask routes are synchronous.

**Error Testing:**

Example from `tests/test_cost_tracker.py:48-57`:

```python
def test_missing_rate_no_raise(db_session, patched_sessionlocal):
    # Should silently skip when rate not found
    log_api_cost('unknown', 'noop', user_id=1, units=5, unit_type='per_minute')
    assert db_session.query(ApiCostLog).count() == 0

def test_silent_on_db_error(monkeypatch, capsys):
    def broken_session(*args, **kwargs):
        raise RuntimeError("db down")
    monkeypatch.setattr(_db_mod2, 'SessionLocal', broken_session)
    # Should NOT raise
    log_api_cost('anthropic', 'haiku-test', user_id=1, units=1.0,
                 unit_type='per_1k_input_tokens')
    captured = capsys.readouterr()
```

**Parametrized Testing:**

No `@pytest.mark.parametrize` found in reviewed tests. Tests use explicit function calls instead.

## Known Test Gaps & Dead Code Analysis

**Tested Code:**
- `services/ki_logik.py` — fully tested: `detect_phase()`, `compute_readiness_score()`, `select_active_hint()`, `dynamic_ewb_buttons()`
- `services/cost_tracker.py` — fully tested: API cost logging with currency conversion
- `services/eur_calculator.py` — fully tested: EUR price calculations
- Database migrations — tested: `test_models_04_7_2.py`, `test_phase_08_models.py`, `test_branche_migration.py`

**Untested/Minimal Coverage:**
- `static/app.js` — No JavaScript tests. Functions defined: `startMicStream()`, `stopMicStream()`, `selectMode()`, `activateSession()`, `triggerEwb()`, `pollErgebnis()`, `beenden()` — all live-session critical paths, no test coverage
- `static/pip-launcher.js` — No JavaScript tests. Core state machine in IIFE, no unit tests
- Route handlers in `routes/dashboard.py`, `routes/profiles.py`, `routes/organizations.py` — not explicitly tested
- WebSocket handlers in `socket_routes.py` (if exists) — no tests found

**Dead Code Identified:**

1. **`saveGeneratedPersonality()` in `templates/training.html`**
   - Status: **REMOVED** in Phase 07.2 Wave 3
   - Evidence: Comment at `templates/training.html:1633-1635`
   - Reason: "war nur aus dem Post-Call-Scoring-Overlay aufrufbar. Overlay ist weg — Funktion damit orphaned"
   - Re-introduction: Planned under POLISH-37 (ROADMAP) when Save-Prompt feature re-introduced
   - No remaining calls to this function — safely removed

2. **Potential dead JS functions in `static/app.js`:**
   - `updateSpeechCircles()` — defined at line 386, may be unused if mic visualization removed
   - `updateSpeechUI()` — defined at line 401 with comment `/* kept for compatibility */` — deprecated but retained
   - `logGenutzt()` — defined at line 816, unclear if called from HTML
   - Recommend: Verify HTML onclick attributes for actual usage

**Test Recommendations:**

Priority High:
- Add JavaScript tests for `startMicStream()`, `stopMicStream()`, `activateSession()` (core session lifecycle)
- Add route tests for `/api/ergebnis`, `/api/end_session` (critical polling endpoints)
- Add integration test for full training scenario creation → response generation → completion

Priority Medium:
- Add tests for error paths in training service (missing voice, rate limit, API failure)
- Add parametrized tests for all `SCHWIERIGKEITEN` difficulty levels
- Add database constraint tests (unique org_id + name for profiles, etc.)

Priority Low:
- Add E2E tests for live session flow (requires browser automation)
- Add tests for performance (session timer accuracy, polling interval timing)

---

*Testing analysis: 2026-04-24*
