"""Anlage-Pfad-Inventur + Confirm-Flow-Guard (Plan 03, D-02/D-03/D-09/D-11/D-12/D-13).

VALID Runtime-Verhalten (API-Response + DB-Read gegen echte PG nerve_test, KEIN Source-Presence):
- Register landet auf der Warteseite und setzt email_confirmed=False (nicht NULL, nicht True).
- Register versendet NUR die Confirmation-Mail, KEIN Welcome an die unbestaetigte Adresse.
- confirm_email setzt True + versendet Welcome — IDEMPOTENT (Welcome nur beim ERSTEN Confirm).
- Kein Nicht-OAuth-Creator (api_register/Invite) laesst email_confirmed NULL.

★ ERST-ROT: gegen den heutigen Code sind Test A/B/C/C2/D rot (Register returnt heute
post_login_destination + sendet Welcome; confirm_email sendet kein Welcome / nicht idempotent).
Gruen erst nach den Naht-Edits in Task 1.

Alle committenden Tests raeumen ihre Rows via cleanup_rows im POST-yield-Teardown (public.*),
uuid-suffixed Emails gegen die UNIQUE-Constraint auf users.email. send_welcome /
send_confirmation_email werden gespäht (monkeypatch am Modul services.email_service — der
Import in den Routen laeuft zur Call-Zeit gegen genau dieses Modul).
"""

import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer

from tests.conftest import cleanup_rows
from database.models import User, Organisation, Invitation
from config import SECRET_KEY


@pytest.fixture
def cleanup_tracker(client):
    """yield ein {Model: [ids]}-Dict; POST-yield reverse-FK-clean via cleanup_rows (public.*)."""
    ids = {User: [], Organisation: [], Invitation: []}
    yield ids
    cleanup_rows(client._test_session, ids)


def _unique_email():
    return f'evcreate-{uuid.uuid4().hex[:8]}@nerve.local'


def _confirm_token(email):
    return URLSafeTimedSerializer(SECRET_KEY, salt='nerve-email-confirm').dumps(email)


def _read_user(session, email):
    session.expire_all()
    return session.query(User).filter_by(email=email).first()


def _register_payload(email):
    return {
        'vorname': 'Test', 'nachname': 'User', 'email': email,
        'passwort': 'secret12345', 'firmenname': 'TestCo', 'teamgroesse': '1-5',
    }


def _make_unconfirmed_user(client, tracker, email):
    """Org + User (email_confirmed=False) auf client._test_session, committet + getrackt."""
    db = client._test_session
    org = Organisation(name='TestOrg', plan='starter')
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=email,
        passwort_hash=generate_password_hash('secret12345'),
        rolle='owner',
        aktiv=True,
        email_confirmed=False,
    )
    db.add(user)
    db.commit()
    tracker[Organisation].append(org.id)
    tracker[User].append(user.id)
    return org.id, user.id


# ── Test A: Register → False + Warteseite (D-02/D-09) ──────────────────────────────
def test_register_lands_on_waiting_page_and_sets_false(client, cleanup_tracker, monkeypatch):
    import services.email_service as es
    monkeypatch.setattr(es, 'send_confirmation_email', lambda *a, **k: True)
    monkeypatch.setattr(es, 'send_welcome', lambda *a, **k: True)
    email = _unique_email()
    resp = client.post('/api/register', json=_register_payload(email))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['next'] == '/auth/confirm-email-pending'   # D-09 (heute: post_login_destination → rot)
    u = _read_user(client._test_session, email)
    assert u is not None
    cleanup_tracker[User].append(u.id)
    cleanup_tracker[Organisation].append(u.org_id)
    assert u.email_confirmed is False                      # D-02 (nicht NULL, nicht True)


# ── Test B: Register sendet Confirmation, KEIN Welcome (D-12) ───────────────────────
def test_register_sends_confirmation_not_welcome(client, cleanup_tracker, monkeypatch):
    import services.email_service as es
    calls = {'welcome': 0, 'confirm': 0}
    monkeypatch.setattr(es, 'send_welcome', lambda *a, **k: calls.__setitem__('welcome', calls['welcome'] + 1))
    monkeypatch.setattr(es, 'send_confirmation_email', lambda *a, **k: calls.__setitem__('confirm', calls['confirm'] + 1))
    email = _unique_email()
    resp = client.post('/api/register', json=_register_payload(email))
    assert resp.status_code == 200
    u = _read_user(client._test_session, email)
    assert u is not None
    cleanup_tracker[User].append(u.id)
    cleanup_tracker[Organisation].append(u.org_id)
    assert calls['welcome'] == 0    # kein Welcome an unbestaetigte Adresse (heute 1 → rot)
    assert calls['confirm'] == 1    # Confirmation versendet (heute 0 → rot)


# ── Test C: confirm_email → True + Welcome (D-13) ──────────────────────────────────
def test_confirm_email_sets_true_and_sends_welcome(client, cleanup_tracker, monkeypatch):
    import services.email_service as es
    welcome_calls = []
    monkeypatch.setattr(es, 'send_welcome', lambda *a, **k: welcome_calls.append(1))
    email = _unique_email()
    _make_unconfirmed_user(client, cleanup_tracker, email)
    resp = client.get('/auth/confirm_email?token=' + _confirm_token(email), follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308)
    u = _read_user(client._test_session, email)
    assert u.email_confirmed is True
    assert len(welcome_calls) == 1   # Welcome beim Confirm (heute 0 → rot)


# ── Test C2: confirm_email idempotent (Finding 3b) ─────────────────────────────────
def test_confirm_email_welcome_is_idempotent(client, cleanup_tracker, monkeypatch):
    import services.email_service as es
    welcome_calls = []
    monkeypatch.setattr(es, 'send_welcome', lambda *a, **k: welcome_calls.append(1))
    email = _unique_email()
    _make_unconfirmed_user(client, cleanup_tracker, email)
    token = _confirm_token(email)
    client.get('/auth/confirm_email?token=' + token, follow_redirects=False)   # 1. Confirm → Welcome
    client.get('/auth/confirm_email?token=' + token, follow_redirects=False)   # 2. Confirm → KEIN Welcome
    assert len(welcome_calls) == 1   # nur beim ERSTEN Confirm (heute 0 → rot; ohne Guard 2 → rot)


# ── Test D: Anlage-Pfad-Inventur — kein Creator laesst NULL (D-03) ─────────────────
def test_creation_paths_never_leave_null(client, cleanup_tracker, monkeypatch):
    import services.email_service as es
    monkeypatch.setattr(es, 'send_confirmation_email', lambda *a, **k: True)
    monkeypatch.setattr(es, 'send_welcome', lambda *a, **k: True)
    db = client._test_session

    # (1) api_register → explizit False, NICHT NULL
    email_r = _unique_email()
    resp = client.post('/api/register', json=_register_payload(email_r))
    assert resp.status_code == 200
    ur = _read_user(db, email_r)
    assert ur is not None
    cleanup_tracker[User].append(ur.id)
    cleanup_tracker[Organisation].append(ur.org_id)
    assert ur.email_confirmed is not None
    assert ur.email_confirmed is False

    # (2) Invite-register → explizit True (Invite beweist Mail-Besitz), NICHT NULL
    org = Organisation(name='InviteOrg', plan='starter')
    db.add(org)
    db.flush()
    email_i = _unique_email()
    token = uuid.uuid4().hex
    inv = Invitation(org_id=org.id, email=email_i, token=token, verwendet=False)
    db.add(inv)
    db.commit()
    cleanup_tracker[Organisation].append(org.id)
    cleanup_tracker[Invitation].append(inv.id)
    resp = client.post('/register?token=' + token,
                       data={'email': email_i, 'passwort': 'secret12345'},
                       follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307, 308)
    ui = _read_user(db, email_i)
    assert ui is not None
    cleanup_tracker[User].append(ui.id)
    assert ui.email_confirmed is not None
    assert ui.email_confirmed is True
