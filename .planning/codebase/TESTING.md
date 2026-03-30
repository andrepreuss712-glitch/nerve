# Testing Patterns

**Analysis Date:** 2026-03-30

## Test Framework

**Current State:**
- **No test framework configured** — No `pytest.ini`, `setup.cfg`, or `pyproject.toml` detected
- **No test files found** — No `test_*.py`, `*_test.py`, or `tests/` directory exists
- **Testing infrastructure:** Absent
- **Test runner:** Not configured
- **Assertion library:** Not selected

**Requirements.txt:**
- `flask>=3.0.0`
- `flask-socketio>=5.3.6`
- `anthropic>=0.40.0`
- `deepgram-sdk>=3.7.0`
- `pyaudio>=0.2.14`
- `python-dotenv>=1.0.0`
- `sqlalchemy>=2.0.0`
- `werkzeug>=3.0.0`
- `requests>=2.31.0`

No test-related dependencies present.

## Test Structure

**Current Testing Approach:**
- Manual testing only (no automated test suite)
- Code size: 5,570 lines total across `app.py`, `routes/`, `services/`, `database/`
- High risk: No automated validation of core features

## Testing Opportunities

### Unit Testing

**Priority 1 - Authentication (`routes/auth.py`):**
```python
# Current code at lines 46-80
def _do_login(email, passwort):
    """Shared login logic. Returns (user_info_dict, error_msg)."""
    db = get_session()
    try:
        user = db.query(User).filter_by(email=email, aktiv=True).first()
        if user and check_password_hash(user.passwort_hash, passwort):
            # ... session setup ...
            return { 'id': user_id, 'org_id': user_org_id, ... }, None
        return None, 'E-Mail oder Passwort falsch.'
    finally:
        db.close()
```

**What should be tested:**
- Valid credentials return user info dict with no error
- Invalid password returns None, error message
- Inactive user returns None, error message
- Non-existent email returns None, error message
- Session token creation and expiry calculation

### Unit Testing

**Priority 2 - Profile Management (`routes/profiles.py`):**
```python
# Lines 61-112 (wizard_create function)
# Lines 115-145 (bearbeiten function)
```

**What should be tested:**
- Profile creation with valid data returns success
- Invalid JSON in daten field falls back to empty object
- Permission checks (non-admin cannot create profile)
- Profile activation updates active_profile_id
- Profile deletion removes profile and clears session if active

### Integration Testing

**Priority 1 - Live Session Flow (`routes/app_routes.py`):**
```python
# Lines 77-93 (api_ergebnis)
# Lines 96-115 (api_analyse_line)
```

**What needs testing:**
- Live session creation and state management
- Analysis pipeline: raw input → Claude analysis → structured output
- Fair-use quota enforcement (`/live` endpoint lines 17-41)
- Monthly quota reset logic

**Priority 2 - API Endpoints:**
- `/api/login` - Authentication endpoint
- `/api/register` - Direct registration
- `/api/ergebnis` - Results polling
- `/api/analyse_line` - Claude analysis submission
- `/profiles/wizard` - Profile creation wizard

## Error Handling Test Cases

**Current Error Patterns to Test:**

1. **JSON Parsing Failures** (`routes/profiles.py` lines 40-44):
   ```python
   try:
       json.loads(daten_json)
   except Exception:
       daten_json = '{}'
   ```
   Test: Invalid JSON should silently fallback to `{}`

2. **Database Session Cleanup** (all routes):
   ```python
   db = get_session()
   try:
       # ... operations ...
   finally:
       db.close()
   ```
   Test: Session must close even if exception occurs

3. **File Parsing** (`routes/dashboard.py` lines 37-58):
   ```python
   try:
       content = open(fpath, encoding='utf-8').read()
       # ... regex extractions ...
   except Exception:
       pass
   ```
   Test: Missing files, encoding errors, missing patterns should not crash

4. **Migration Errors** (`app.py` lines 78-83):
   ```python
   try:
       conn.execute(text(f'ALTER TABLE users ADD COLUMN {col} {typedef}'))
   except Exception:
       pass
   ```
   Test: Duplicate columns should not break initialization

## Fixtures and Test Data

**Needed for Testing:**

1. **User Fixtures:**
   ```python
   # Would need:
   test_user = {
       'email': 'test@example.com',
       'passwort': 'TestPass123!',
       'org_id': 1,
       'rolle': 'member'
   }
   test_admin = {
       'email': 'admin@example.com',
       'passwort': 'AdminPass123!',
       'org_id': 1,
       'rolle': 'owner'
   }
   ```

2. **Profile Fixtures:**
   ```python
   test_profile = {
       'name': 'Test Profile',
       'branche': 'Vertrieb',
       'org_id': 1,
       'daten': json.dumps({
           'basis': {'produktbeschreibung': 'Test Product'},
           'einwaende': [],
           'phasen': []
       })
   }
   ```

3. **Session Fixtures:**
   - Authenticated Flask test client
   - Login helper to set session cookies

## Coverage Analysis

**Critical Untested Areas:**

1. **Authentication & Authorization:**
   - `routes/auth.py` (207 lines)
   - `routes/coach.py` `coach_required` decorator

2. **Core Business Logic:**
   - `services/claude_service.py` - AI prompt handling and response parsing
   - `services/training_service.py` - Voice interaction and difficulty levels
   - `services/live_session.py` - Session state management

3. **Data Operations:**
   - User registration and invitation flow
   - Organisation management
   - Profile CRUD operations

4. **API Endpoints:**
   - All 15+ endpoints in `routes/app_routes.py`
   - All organisation endpoints in `routes/organisations.py`
   - All training endpoints in `routes/training.py`

## Recommendations for Test Implementation

### Phase 1: Foundation

1. **Install test dependencies:**
   ```bash
   pip install pytest pytest-flask pytest-cov python-dotenv
   ```

2. **Create test structure:**
   ```
   tests/
   ├── __init__.py
   ├── conftest.py           # Fixtures, DB setup
   ├── test_auth.py          # Authentication tests
   ├── test_profiles.py      # Profile CRUD tests
   └── test_api.py           # API endpoint tests
   ```

3. **Database isolation for tests:**
   - Use in-memory SQLite: `sqlite:///:memory:`
   - Or separate test database with automatic cleanup

### Phase 2: Core Coverage

1. **Authentication:**
   - Valid login, invalid password, non-existent user
   - Registration with valid/invalid data
   - Permission checks (login_required, coach_required)

2. **Profiles:**
   - Create, read, update, delete operations
   - Permission enforcement
   - JSON validation

3. **Fair-Use Quotas:**
   - Monthly reset logic
   - Usage tracking
   - Limit enforcement

### Phase 3: Integration

1. **End-to-end API flows:**
   - Registration → Login → Profile activation → Live session
   - Training session start → analysis → results

2. **Service integration:**
   - Claude API mocking for analysis
   - Deepgram API mocking for transcription
   - ElevenLabs API mocking for voice

### Mock Strategy

**Services to Mock:**
- `anthropic.Anthropic` - AI analysis
- `deepgram_sdk` - Speech-to-text
- `requests` - HTTP calls (training voice generation)
- File I/O - Log reading/writing

**Example Mock Pattern:**
```python
from unittest.mock import patch, MagicMock

@patch('services.claude_service.claude_client')
def test_analyse_line(mock_claude):
    mock_claude.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"einwand": true, "typ": "Preis"}')]
    )
    # Test analysis endpoint
```

## Current Manual Testing Patterns

**Observable Test Scenarios in Code:**
- Account creation during initialization (`app.py` lines 239-260)
- Demo profile creation for new orgs
- Training scenario seeding
- Live session simulation ready (code structure supports it)

## Testing Gaps & Risks

**High Risk - No Validation:**
- Claude JSON parsing (could return invalid format)
- Session state management under concurrent requests
- Fair-use quota enforcement
- Database migrations with schema changes

**Medium Risk - Partial Manual Testing:**
- API endpoint behavior
- Frontend-backend contract
- Permission enforcement

---

*Testing analysis: 2026-03-30*
