"""Tests for login-redirect next-Parameter flow (Finding 4).

Protects against the bug where unauthenticated users accessing a deep URL
landed on /dashboard after login instead of the originally-requested URL.
Also covers open-redirect protection on the `next` parameter.
"""

import uuid
from urllib.parse import quote

import pytest

from routes.auth import safe_next
from tests.conftest import cleanup_rows
from database.models import User, Organisation


# ── Phase 08.23.2.PGTEST Gruppe B — unique-email + cleanup_rows-Teardown (T-PGTEST-24) ──────
# _make_test_user committet eine Organisation + einen User auf der MODULE-SessionLocal
# (client._test_session) → die Rows PERSISTIEREN in nerve_test (kein D-03-Rollback fuer committete
# Rows). ZWEI Folgen auf der persistenten DB: (1) users.email ist UNIQUE (models.py:70) → der feste
# 'test@nerve.local' braeche beim 2. Test auf UNIQUE → uuid-suffixed Email pro Run. (2) org/user
# leaken → public-Baseline-Drift → der autouse _baseline_cleanup_guard (Plan 01 Task 6) faerbt rot.
# FIX: kanonische cleanup_tracker-FIXTURE (NIEMALS yield im plain Test-Body, T-PGTEST-34) loescht die
# committeten IDs POST-yield via cleanup_rows in reverse-FK-Reihenfolge (users vor organisations,
# public.* ohne Tenant-GUC). Die reinen safe_next-Unit-Tests + die unauth-Redirect-Tests committen
# nichts → kein Tracker noetig.
@pytest.fixture
def cleanup_tracker(client):
    """yield ein {Model: [ids]}-Dict; POST-yield reverse-FK-clean via cleanup_rows (public.*)."""
    ids = {User: [], Organisation: []}
    yield ids
    cleanup_rows(client._test_session, ids)


# ── Unit tests for safe_next helper ─────────────────────────────────────────

def test_safe_next_accepts_plain_path():
    assert safe_next('/admin/ewb/quality') == '/admin/ewb/quality'


def test_safe_next_accepts_path_with_query():
    assert safe_next('/profiles?edit=1') == '/profiles?edit=1'


def test_safe_next_rejects_protocol_relative():
    # Browsers resolve //evil.com as http(s)://evil.com — must be blocked.
    assert safe_next('//evil.com/phish') is None


def test_safe_next_rejects_backslash_escape():
    # Some browsers normalize /\evil.com similar to protocol-relative.
    assert safe_next('/\\evil.com') is None


def test_safe_next_rejects_absolute_url():
    assert safe_next('https://evil.com/') is None
    assert safe_next('http://evil.com/phish') is None


def test_safe_next_rejects_missing_leading_slash():
    assert safe_next('dashboard') is None
    assert safe_next('') is None


def test_safe_next_rejects_crlf():
    # Prevent header-injection via CRLF in Location header.
    assert safe_next('/foo\r\nX-Evil: 1') is None
    assert safe_next('/foo\nbar') is None


def test_safe_next_rejects_non_string():
    assert safe_next(None) is None
    assert safe_next(['/foo']) is None


# ── Integration tests for redirect chain ────────────────────────────────────

def test_unauth_protected_url_redirects_to_login_with_next(client):
    """Unauth GET /admin/ewb/quality → 302 to /login?next=/admin/ewb/quality."""
    resp = client.get('/admin/ewb/quality', follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers['Location']
    assert '/login' in loc
    assert 'next=' in loc
    assert quote('/admin/ewb/quality', safe='/') in loc


def test_login_preserves_next_into_modal_url(client):
    """GET /login?next=/admin/ewb/quality → 302 to /?modal=login&next=…"""
    resp = client.get('/login?next=/admin/ewb/quality', follow_redirects=False)
    assert resp.status_code == 302
    loc = resp.headers['Location']
    assert '/?modal=login' in loc
    assert 'next=' in loc
    assert quote('/admin/ewb/quality', safe='/') in loc


def test_login_without_next_goes_to_plain_modal(client):
    """Behavior preserved: /login with no next → /?modal=login (no &next=)."""
    resp = client.get('/login', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'] == '/?modal=login'


def test_login_rejects_open_redirect_next(client):
    """GET /login?next=//evil.com → redirects to plain modal, not forwarded."""
    resp = client.get('/login?next=//evil.com/phish', follow_redirects=False)
    assert resp.status_code == 302
    # Evil URL must NOT appear in Location header.
    assert 'evil.com' not in resp.headers['Location']
    assert resp.headers['Location'] == '/?modal=login'


def test_unauth_protected_url_rejects_crlf_injection_in_path(client):
    """Paths with CR/LF should never reach Location header unescaped."""
    # werkzeug rejects CR/LF in URLs before reaching the view, but our
    # safe_next is the last line of defense if that ever regresses.
    # Covered by test_safe_next_rejects_crlf.
    pass


# ── api/login next round-trip (Bug B fix, 2026-04-23) ────────────────────────

def _make_test_user(client, email=None, password='secret12345', tracker=None):
    """Helper: create a minimal user + org in the test DB.

    email defaults to a uuid-suffixed unique value (users.email is UNIQUE on the persistent
    nerve_test). Returns the User; callers read user.email for the login POST. Registers the
    committed org/user IDs in tracker (if given) for cleanup_rows teardown.
    """
    from werkzeug.security import generate_password_hash
    if email is None:
        email = f'test-{uuid.uuid4().hex[:8]}@nerve.local'
    db = client._test_session
    org = Organisation(name='TestOrg', plan='starter')
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=email,
        passwort_hash=generate_password_hash(password),
        rolle='owner',
        aktiv=True,
    )
    db.add(user)
    db.commit()
    if tracker is not None:
        tracker[Organisation].append(org.id)
        tracker[User].append(user.id)
    return user


def test_api_login_echoes_valid_next_in_response(client, cleanup_tracker):
    """POST /api/login with next=/admin/ewb/quality → response includes next."""
    u = _make_test_user(client, tracker=cleanup_tracker)
    resp = client.post(
        '/api/login',
        json={'email': u.email, 'passwort': 'secret12345',
              'next': '/admin/ewb/quality'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data.get('next') == '/admin/ewb/quality'


def test_api_login_drops_open_redirect_next(client, cleanup_tracker):
    """POST /api/login with next=//evil.com → response omits next (rejected by safe_next)."""
    u = _make_test_user(client, tracker=cleanup_tracker)
    resp = client.post(
        '/api/login',
        json={'email': u.email, 'passwort': 'secret12345',
              'next': '//evil.com/phish'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    # S2-Wiring (AUTH-2): safe_next verwirft den boesen next → nxt=None → die Weiche
    # setzt ein sicheres INTERNES Ziel (pending Owner → '/onboarding/'). Der Angreifer-Wert
    # darf NICHT reflektiert werden; ein internes Pfad-Ziel ist erlaubt (Open-Redirect-Schutz intakt, Punkt 18).
    nxt = data.get('next', '')
    assert 'evil.com' not in nxt
    assert not nxt.startswith(('http://', 'https://', '//'))


def test_api_login_without_next_preserves_legacy_shape(client, cleanup_tracker):
    """POST /api/login without next, done-User → response has ok+coach, no next key."""
    u = _make_test_user(client, tracker=cleanup_tracker)
    # done-User: die Weiche (S2) gibt None → kein next-Key → Legacy-Shape bleibt geprueft.
    db = client._test_session
    u.onboarding_state = 'done'
    db.commit()
    resp = client.post(
        '/api/login',
        json={'email': u.email, 'passwort': 'secret12345'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert 'coach' in data
    assert 'next' not in data


def test_api_login_bad_creds_ignores_next(client, cleanup_tracker):
    """POST /api/login with wrong password and next → 401, no next leak."""
    u = _make_test_user(client, tracker=cleanup_tracker)
    resp = client.post(
        '/api/login',
        json={'email': u.email, 'passwort': 'wrong-password',
              'next': '/admin/ewb/quality'},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert data['ok'] is False
    assert 'next' not in data


def test_api_login_rejects_crlf_in_next(client, cleanup_tracker):
    """Defense-in-depth: CRLF in next must not reach response."""
    u = _make_test_user(client, tracker=cleanup_tracker)
    resp = client.post(
        '/api/login',
        json={'email': u.email, 'passwort': 'secret12345',
              'next': '/foo\r\nX-Evil: 1'},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    # S2-Wiring (AUTH-2): safe_next verwirft den CRLF-next → Weiche setzt sicheres internes Ziel.
    # Der injizierte Wert darf NICHT in der Antwort landen (kein \r\n, kein X-Evil, kein externer Host).
    nxt = data.get('next', '')
    assert '\r' not in nxt and '\n' not in nxt
    assert 'X-Evil' not in nxt
    assert not nxt.startswith(('http://', 'https://', '//'))
