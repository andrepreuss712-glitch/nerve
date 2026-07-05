"""Phase 08.23.2.AUTH-1 Plan 03 Task 1 — Waitlist/Changelog-Admin-Auth-Waechter (ERST-ROT gegen HEAD).

Nagelt fest: GET /waitlist/admin, POST /waitlist/invite/<wid>, POST /changelog/admin sind NUR fuer
Superadmin erreichbar (jeder Firmen-Owner -> 403, anon -> Redirect zur Login-Seite). Gegen HEAD haben
alle drei nur einen schwachen `flask_session.get('rolle') != 'owner'`-Check ohne @login_required ->
JEDER Owner kommt durch -> die drei Owner->403-Faelle sind gegen HEAD ROT. Nach dem Fix
(@login_required + @superadmin_required, Plan 03 Task 2/3) -> 403 -> gruen.

Cleanup (CLAUDE.md Test-Cleanup-Regel): committende Rows werden reverse-FK weggeraeumt — inkl. der
vom Superadmin-invite-Pfad als Side-Effect erzeugten Organisation + Invitation + tenant_orgs-Row
(trg_mk_tenant_org, Migration 0011) + der Waitlist-/Changelog-Rows. Die Owner->403-Faelle tracken
defensiv, was gegen HEAD (Owner kommt durch) faelschlich angelegt wird (Side-Effect-Leak-Schutz).

Verify NUR ueber `bash deploy.sh production` (CLAUDE.md „Kein Local-Dev"); auto-collected.
"""
import pytest
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from tests.conftest import cleanup_rows
from database.models import User, Organisation, Waitlist, Invitation, Changelog


@pytest.fixture
def cleanup_tracker(db_from_client):
    """reverse-FK-Cleanup via cleanup_rows. tenant_orgs (trg_mk_tenant_org bei jedem org-INSERT,
    FK ohne ondelete) + Invitation (org_id FK) mit im Tracker — cleanup_rows loescht reverse-FK."""
    ids = {
        Invitation: [],
        User: [],
        Changelog: [],
        Waitlist: [],
        'public.tenant_orgs': [],
        Organisation: [],
    }
    yield ids
    cleanup_rows(db_from_client, ids)


def _track_tenant_org(session, tracker, org_id):
    row = session.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :o"), {"o": org_id}
    ).first()
    if row:
        tracker['public.tenant_orgs'].append(row[0])


def _make_org_and_user(session, email, is_superadmin, tracker):
    org = Organisation(name='TestCo', plan='starter')
    session.add(org)
    session.flush()
    u = User(email=email, passwort_hash=generate_password_hash('pw'),
             rolle='owner', org_id=org.id, is_superadmin=is_superadmin,
             aktiv=True, onboarding_done=True)
    session.add(u)
    session.commit()
    tracker[Organisation].append(org.id)
    tracker[User].append(u.id)
    _track_tenant_org(session, tracker, org.id)
    return u


def _make_waitlist_entry(session, email, tracker):
    w = Waitlist(email=email, name='Probe', firma='ProbeCo', status='waiting')
    session.add(w)
    session.commit()
    tracker[Waitlist].append(w.id)
    return w


def _track_invite_side_effects(session, tracker, waitlist_email):
    """Der invite-Pfad erzeugt Organisation(billing_email=waitlist_email) + Invitation + tenant_orgs.
    Defensiv tracken (auch im Owner->403-Fall, falls HEAD den Owner durchliess -> Side-Effect-Leak)."""
    session.rollback()  # frische TX -> committete Rows sichtbar
    for org in session.query(Organisation).filter_by(billing_email=waitlist_email).all():
        tracker[Organisation].append(org.id)
        _track_tenant_org(session, tracker, org.id)
    for inv in session.query(Invitation).filter_by(email=waitlist_email).all():
        tracker[Invitation].append(inv.id)


# ── GET /waitlist/admin ───────────────────────────────────────────────────────

def test_admin_anon_redirects(client):
    # kein Login -> Redirect (HEAD: 302 zum Dashboard ueber schwachen Check; nach Fix: 302 zur Login-Seite)
    r = client.get('/waitlist/admin', follow_redirects=False)
    assert r.status_code in (302, 401)


def test_admin_normal_owner_gets_403(client, db_from_client, cleanup_tracker):
    u = _make_org_and_user(db_from_client, 'wl_owner_admin@nerve.local',
                           is_superadmin=False, tracker=cleanup_tracker)
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'   # HEAD-Rot-Reproduktion: schwacher Check laesst Owner durch
    r = client.get('/waitlist/admin')
    assert r.status_code == 403   # HEAD: Owner kommt durch (200) -> ROT; nach Fix: 403


def test_admin_superadmin_gets_200(client, db_from_client, cleanup_tracker):
    u = _make_org_and_user(db_from_client, 'wl_superadmin_admin@nerve.local',
                           is_superadmin=True, tracker=cleanup_tracker)
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
    r = client.get('/waitlist/admin')
    assert r.status_code == 200


# ── POST /waitlist/invite/<wid> ───────────────────────────────────────────────

def test_invite_owner_gets_403(client, db_from_client, cleanup_tracker):
    u = _make_org_and_user(db_from_client, 'wl_owner_invite@nerve.local',
                           is_superadmin=False, tracker=cleanup_tracker)
    w = _make_waitlist_entry(db_from_client, 'wl_invite_probe_owner@nerve.local', cleanup_tracker)
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
    r = client.post(f'/waitlist/invite/{w.id}')
    # defensiv: falls HEAD den Owner durchliess, den invite-Side-Effect (Org/Invitation/tenant_orgs) tracken
    _track_invite_side_effects(db_from_client, cleanup_tracker, 'wl_invite_probe_owner@nerve.local')
    assert r.status_code == 403   # HEAD: Owner kommt durch (200) -> ROT; nach Fix: 403


def test_invite_superadmin_allowed(client, db_from_client, cleanup_tracker):
    u = _make_org_and_user(db_from_client, 'wl_superadmin_invite@nerve.local',
                           is_superadmin=True, tracker=cleanup_tracker)
    w = _make_waitlist_entry(db_from_client, 'wl_invite_probe_super@nerve.local', cleanup_tracker)
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
    r = client.post(f'/waitlist/invite/{w.id}')
    _track_invite_side_effects(db_from_client, cleanup_tracker, 'wl_invite_probe_super@nerve.local')
    assert r.status_code != 403   # Superadmin darf einladen (HEAD + nach Fix)


# ── POST /changelog/admin (Fable should-include) ──────────────────────────────

def test_changelog_admin_owner_gets_403(client, db_from_client, cleanup_tracker):
    u = _make_org_and_user(db_from_client, 'cl_owner_admin@nerve.local',
                           is_superadmin=False, tracker=cleanup_tracker)
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
    r = client.post('/changelog/admin', json={'version': 'x-test', 'titel': 't', 'inhalt': 'i'})
    # defensiv: HEAD laesst Owner durch -> add_entry committet eine Changelog-Row (id in der Antwort) -> tracken
    if r.status_code == 200:
        body = r.get_json(silent=True) or {}
        if body.get('id'):
            cleanup_tracker[Changelog].append(body['id'])
    assert r.status_code == 403   # HEAD: Owner kommt durch (200) -> ROT; nach Fix: 403
