"""
tests/test_profile_editor_validation.py
────────────────────────────────────────────────────────────────────
Backend integration tests for POST /profiles/api/profile/<id>/tabu
with list-of-objects validation.

Tests the server-side contract:
  - Valid pair → saved=1, ignored=[]
  - Incomplete (empty alternative) → saved=0, ignored has entry
  - Incomplete (empty begriff) → saved=0, ignored has entry
  - Mixed → saved=N, ignored=M
"""
import json
import pytest


def _make_test_user_and_profile(db_session, engine):
    """Seed a minimal Organisation + User + Profile in the test DB."""
    from database.models import Organisation, User, Profile
    from werkzeug.security import generate_password_hash

    org = Organisation(name='TestOrg')
    db_session.add(org)
    db_session.flush()

    user = User(
        org_id=org.id,
        email='test@example.com',
        passwort_hash=generate_password_hash('secret'),
        rolle='owner',
    )
    db_session.add(user)
    db_session.flush()

    profile = Profile(
        org_id=org.id,
        name='Test-Profil',
        daten=json.dumps({'basis': {'tabu_begriffe': []}}),
        erstellt_von=user.id,
    )
    db_session.add(profile)
    db_session.commit()
    return org, user, profile


def _login(client, db_session, user, org):
    """Inject session state so login_required passes."""
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['org_id'] = org.id
        sess['rolle'] = user.rolle


# ── Tests ──────────────────────────────────────────────────────────────────


def test_tabu_valid_pair_saved(client, db_from_client):
    """POST with complete pair → saved=1, ignored=[]"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': 'A', 'alternative': 'B'}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 1
    assert data['ignored'] == []


def test_tabu_empty_alternative_ignored(client, db_from_client):
    """POST with empty alternative → saved=0, ignored has entry"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': 'A', 'alternative': ''}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 0
    assert len(data['ignored']) == 1


def test_tabu_empty_begriff_ignored(client, db_from_client):
    """POST with empty begriff → saved=0, ignored has entry"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps({'tabu_begriffe': [{'begriff': '', 'alternative': 'B'}]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 0
    assert len(data['ignored']) == 1


def test_tabu_mixed_saved_and_ignored(client, db_from_client):
    """POST with mixed → saved=N, ignored=M"""
    org, user, profile = _make_test_user_and_profile(db_from_client, client._test_engine)
    _login(client, db_from_client, user, org)

    payload = {
        'tabu_begriffe': [
            {'begriff': 'Kosten', 'alternative': 'Investition'},   # valid
            {'begriff': 'Problem', 'alternative': ''},              # incomplete
            {'begriff': '', 'alternative': 'Herausforderung'},      # incomplete
            {'begriff': 'Risiko', 'alternative': 'Absicherung'},    # valid
        ]
    }
    resp = client.post(
        f'/profiles/api/profile/{profile.id}/tabu',
        data=json.dumps(payload),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['saved'] == 2
    assert len(data['ignored']) == 2
