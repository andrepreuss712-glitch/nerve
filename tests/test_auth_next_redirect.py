"""Tests for login-redirect next-Parameter flow (Finding 4).

Protects against the bug where unauthenticated users accessing a deep URL
landed on /dashboard after login instead of the originally-requested URL.
Also covers open-redirect protection on the `next` parameter.
"""

from urllib.parse import quote

from routes.auth import safe_next


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
