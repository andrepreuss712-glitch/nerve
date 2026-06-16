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
import uuid

import pytest


@pytest.fixture(autouse=True)
def _profile_editor_cleanup():
    """Phase 08.23.2.PGTEST Task 7: diese Tests COMMITTEN Org/User/Profile (public, kein crm). Auf der
    persistenten nerve_test wuerden sie leaken -> Baseline-Cleanup-Waechter rot. id-Wasserzeichen-
    Teardown ueber eine eigene kurzlebige Engine (entkoppelt von client/db_from_client)."""
    import os as _os
    from sqlalchemy import create_engine as _ce, text as _sql
    dsn = _os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        yield
        return
    eng = _ce(dsn)
    tables = ("profiles", "users", "tenant_orgs", "organisations")
    def _maxid(conn, tbl):
        try:
            return conn.execute(_sql(f"SELECT COALESCE(MAX(id),0) FROM public.{tbl}")).scalar()
        except Exception:
            return 0
    with eng.connect() as conn:
        base = {t: _maxid(conn, t) for t in tables}
    try:
        yield
    finally:
        try:
            with eng.begin() as conn:
                conn.execute(_sql("DELETE FROM public.profiles WHERE id > :b"), {"b": base["profiles"]})
                conn.execute(
                    _sql("DELETE FROM public.tenant_orgs WHERE legacy_org_id IN "
                         "(SELECT id FROM public.organisations WHERE id > :b)"),
                    {"b": base["organisations"]},
                )
                conn.execute(_sql("DELETE FROM public.users WHERE id > :b"), {"b": base["users"]})
                conn.execute(_sql("DELETE FROM public.organisations WHERE id > :b"),
                             {"b": base["organisations"]})
        except Exception as _te:
            print(f"[PGTEST-CLEANUP] profile_editor teardown failed (non-fatal): {_te!r}")
        finally:
            eng.dispose()


def _make_test_user_and_profile(db_session, engine):
    """Seed a minimal Organisation + User + Profile in the test DB.

    Phase 08.23.2.PGTEST Task 7: email UNIQUE pro Run (uuid-suffixed) — sonst users.email UNIQUE-Bruch
    auf der persistenten nerve_test (4 Tests seedeten denselben 'test@example.com'). Org-Insert feuert
    trg_mk_tenant_org -> tenant_orgs automatisch (kein manueller Insert). profiles ist public, keine
    crm-RLS-Luecke (Claudian); der client-Fixture-set_current_tenant deckt etwaige crm-Reads der Route."""
    from database.models import Organisation, User, Profile
    from werkzeug.security import generate_password_hash

    org = Organisation(name='TestOrg')
    db_session.add(org)
    db_session.flush()

    user = User(
        org_id=org.id,
        email=f'profile-edit-{uuid.uuid4().hex[:8]}@nerve.local',
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
