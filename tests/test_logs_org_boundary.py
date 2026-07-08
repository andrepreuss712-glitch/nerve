"""Phase 08.23.2.AUTH-LOGS-TENANT Task 1 — Firmen-Grenze der Call-Logs (ERST-ROT gegen HEAD).

Nagelt fest: owner/admin sehen auf der normalen Logs-Seite (/logs), im Download (/logs/download/) und
im Dashboard-Widget (get_recent_logs) NUR Call-Logs der eigenen Firma (gefiltert ueber die User-IDs von
g.org). Gegen HEAD sind admins UNGEFILTERT -> sie sehen alle Firmen -> diese Faelle sind ROT. Nach dem
Fix (Task 4: org-User-ID-Filter, KEIN is_superadmin-Bypass) -> gruen.

Plus FAIL-CLOSED-Beweis (T-LOGS-06): faellt der org-Lookup aus (Exception), zeigt der Normal-Pfad
NICHTS (leer/403) statt fail-open auf 'alle' zurueckzufallen.

Cleanup (CLAUDE.md Test-Cleanup-Regel): committende Rows (Org/User/tenant_orgs) reverse-FK weggeraeumt;
die im LOG_DIR angelegten Test-Dateien werden im Teardown entfernt. Verify NUR via deploy.sh-Gate.
"""
import os
import pytest
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import User, Organisation
from services.live_session import LOG_DIR
import routes.logs_routes as logs_routes
from routes.dashboard import get_recent_logs


@pytest.fixture
def cleanup_tracker(db_from_client):
    ids = {User: [], 'public.tenant_orgs': [], Organisation: []}
    yield ids
    cleanup_rows(db_from_client, ids)


@pytest.fixture
def log_files():
    """Legt Test-Log-Dateien im LOG_DIR an und raeumt sie im Teardown wieder weg (nur eigene)."""
    created = []

    def _make(uid, seq):
        fname = f"nerve_log_U{uid}_2026-07-08T10-00-{seq:02d}.txt"
        fpath = os.path.join(LOG_DIR, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write("Profil: TestProbe\nGespraechssegmente gesamt: 1\n")
        created.append(fpath)
        return fname

    yield _make
    for fpath in created:
        try:
            os.remove(fpath)
        except Exception:
            pass


def _track_tenant_org(session, tracker, org_id):
    from sqlalchemy import text
    row = session.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :o"), {"o": org_id}
    ).first()
    if row:
        tracker['public.tenant_orgs'].append(row[0])


def _make_org_and_user(session, name, email, tracker, is_superadmin=False):
    org = Organisation(name=name, plan='starter')
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


def _login(client, u):
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'


def _setup_two_orgs(client, db, tracker, log_files, super_a=False):
    ua = _make_org_and_user(db, 'FirmaA', 'logs_a@nerve.local', tracker, is_superadmin=super_a)
    ub = _make_org_and_user(db, 'FirmaB', 'logs_b@nerve.local', tracker)
    fa = log_files(ua.id, 1)
    fb = log_files(ub.id, 2)
    return ua, ub, fa, fb


# ── Normal-Pfad: Firmen-Grenze ────────────────────────────────────────────────

def test_list_hides_other_org(client, db_from_client, cleanup_tracker, log_files):
    ua, ub, fa, fb = _setup_two_orgs(client, db_from_client, cleanup_tracker, log_files)
    _login(client, ua)
    r = client.get('/logs')
    assert r.status_code == 200
    assert fb.encode() not in r.data, "Firma-B-Log darf fuer Owner A NICHT sichtbar sein (Cross-Tenant-Leak)"
    assert fa.encode() in r.data, "eigenes Firma-A-Log muss sichtbar sein"


def test_download_other_org_403(client, db_from_client, cleanup_tracker, log_files):
    ua, ub, fa, fb = _setup_two_orgs(client, db_from_client, cleanup_tracker, log_files)
    _login(client, ua)
    r = client.get(f'/logs/download/{fb}')
    assert r.status_code == 403, "Owner A darf ein Firma-B-Log NICHT herunterladen"


def test_widget_excludes_other_org(client, db_from_client, cleanup_tracker, log_files):
    ua, ub, fa, fb = _setup_two_orgs(client, db_from_client, cleanup_tracker, log_files)
    files = [m['filename'] for m in get_recent_logs(ua.id, ua.org_id, 'owner')]
    assert fb not in files, "Dashboard-Widget darf Firma-B-Log fuer Owner A NICHT enthalten"


def test_superadmin_normal_hides_other_org(client, db_from_client, cleanup_tracker, log_files):
    # is_superadmin-Konto auf dem NORMALEN Pfad -> nur eigene Firma (KEIN Bypass)
    ua, ub, fa, fb = _setup_two_orgs(client, db_from_client, cleanup_tracker, log_files, super_a=True)
    _login(client, ua)
    r = client.get('/logs')
    assert r.status_code == 200
    assert fb.encode() not in r.data, "auch is_superadmin sieht auf /logs (Normal-Pfad) NUR die eigene Firma"


def test_fail_closed_when_org_lookup_raises(client, db_from_client, cleanup_tracker, log_files, monkeypatch):
    # T-LOGS-06: faellt der org-Lookup aus -> NICHTS zeigen (leer/403), NIE 'alle' (fail-open waere ROT).
    ua, ub, fa, fb = _setup_two_orgs(client, db_from_client, cleanup_tracker, log_files)

    def _boom(*a, **k):
        raise RuntimeError("org lookup down")
    monkeypatch.setattr(logs_routes, '_org_user_ids', _boom)

    _login(client, ua)
    r_list = client.get('/logs')
    assert r_list.status_code == 200
    assert fb.encode() not in r_list.data, "fail-closed: bei Lookup-Fehler KEIN fremdes Log zeigen"
    assert fa.encode() not in r_list.data, "fail-closed: bei Lookup-Fehler leere Liste (auch eigene weg)"
    r_dl = client.get(f'/logs/download/{fb}')
    assert r_dl.status_code == 403, "fail-closed: bei Lookup-Fehler Download 403 (kein 200/Leak)"
