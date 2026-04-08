"""Phase 04.7.2 Wave 3 — admin_dashboard auth gate integration tests."""
import pytest
from werkzeug.security import generate_password_hash


def _make_org_and_user(session, email, is_superadmin=False, sub_status='active'):
    from database.models import User, Organisation
    org = Organisation(name='TestCo', plan='starter',
                       subscription_status=sub_status)
    session.add(org)
    session.flush()
    u = User(email=email, passwort_hash=generate_password_hash('pw'),
             rolle='owner', org_id=org.id, is_superadmin=is_superadmin,
             aktiv=True, onboarding_done=True)
    session.add(u)
    session.commit()
    return u


def test_unauthenticated_redirects_to_login(client):
    r = client.get('/admin/dashboard/', follow_redirects=False)
    assert r.status_code in (302, 401)


def test_normal_user_gets_403(client, db_from_client):
    u = _make_org_and_user(db_from_client, 'normal@example.com',
                           is_superadmin=False)
    with client.session_transaction() as s:
        s['user_id'] = u.id
    r = client.get('/admin/dashboard/')
    assert r.status_code == 403


def test_superadmin_gets_200_with_6_tabs(client, db_from_client):
    u = _make_org_and_user(db_from_client, 'andre@nerve.app',
                           is_superadmin=True)
    with client.session_transaction() as s:
        s['user_id'] = u.id
    r = client.get('/admin/dashboard/')
    assert r.status_code == 200
    html = r.data.decode('utf-8')
    for tab in ['uebersicht', 'einnahmen', 'ausgaben', 'kunden', 'eur', 'export']:
        assert f'data-tab="{tab}"' in html, f"tab {tab} missing from shell"


def test_invalid_period_format_400(client, db_from_client):
    u = _make_org_and_user(db_from_client, 'andre2@nerve.app',
                           is_superadmin=True)
    with client.session_transaction() as s:
        s['user_id'] = u.id
    r = client.get('/admin/dashboard/?period=BADFORMAT')
    assert r.status_code == 400


def test_valid_period_200(client, db_from_client):
    u = _make_org_and_user(db_from_client, 'andre3@nerve.app',
                           is_superadmin=True)
    with client.session_transaction() as s:
        s['user_id'] = u.id
    r = client.get('/admin/dashboard/?period=2026-03')
    assert r.status_code == 200
