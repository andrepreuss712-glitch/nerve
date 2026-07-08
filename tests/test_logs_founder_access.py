"""Phase 08.23.2.AUTH-LOGS-TENANT Task 2 — Founder-Log-Pfad (ERST-ROT gegen HEAD).

Nagelt fest: die getrennte superadmin-only Founder-Route (/admin/logs, /admin/logs/download/) ist
(a) fuer owner/admin (nicht-superadmin) 403; (b) jeder erfolgreiche Founder-Download schreibt GENAU EINEN
audit_log-Eintrag (action='founder_log_access', Metadaten-only: Datei+Grund, KEIN Transkript) VOR dem
send_file; (c) FAIL-CLOSED: schlaegt der Audit-Write fehl, wird KEIN File gesendet.

Gegen HEAD existiert die Route nicht -> 404 (rot) bis Task 4. Nach dem Fix -> gruen.

audit_log ist append-only (Migration 0026); die committeten Eintraege raeumt der Baseline-Cleanup-Guard
(Phase TEST-AUFRAEUM Trigger-Bypass) automatisch ab. Org/User via cleanup_rows. Verify NUR via deploy.sh-Gate.
"""
import os
import json
import pytest
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import User, Organisation, AuditLog
from services.live_session import LOG_DIR
import routes.logs_routes as logs_routes


@pytest.fixture
def cleanup_tracker(db_from_client):
    ids = {User: [], 'public.tenant_orgs': [], Organisation: []}
    yield ids
    cleanup_rows(db_from_client, ids)


@pytest.fixture
def log_files():
    created = []

    def _make(uid, seq):
        fname = f"nerve_log_U{uid}_2026-07-08T11-00-{seq:02d}.txt"
        fpath = os.path.join(LOG_DIR, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write("Profil: FounderProbe\nGeheimes Transkript-Fragment XYZ\n")
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


def _make_user(session, name, email, tracker, is_superadmin):
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


def _count_founder_audits(db):
    db.rollback()  # frische TX -> committete Rows sichtbar
    return db.query(AuditLog).filter_by(action='founder_log_access').count()


# ── (a) owner/admin (nicht-superadmin) -> 403 ─────────────────────────────────

def test_founder_list_non_superadmin_403(client, db_from_client, cleanup_tracker):
    u = _make_user(db_from_client, 'FirmaOwner', 'founder_owner@nerve.local', cleanup_tracker, is_superadmin=False)
    _login(client, u)
    r = client.get('/admin/logs')
    assert r.status_code == 403, "Nicht-Superadmin darf den Founder-Log-Pfad NICHT sehen"


def test_founder_download_non_superadmin_403(client, db_from_client, cleanup_tracker, log_files):
    u = _make_user(db_from_client, 'FirmaOwner2', 'founder_owner2@nerve.local', cleanup_tracker, is_superadmin=False)
    f = log_files(u.id, 1)
    _login(client, u)
    r = client.get(f'/admin/logs/download/{f}?grund=x')
    assert r.status_code == 403, "Nicht-Superadmin darf ueber den Founder-Pfad NICHT herunterladen"


# ── (b) Superadmin-Download -> 200 + genau 1 audit_log (Metadaten-only) ────────

def test_founder_download_superadmin_audits_once(client, db_from_client, cleanup_tracker, log_files):
    victim = _make_user(db_from_client, 'FremdFirma', 'founder_victim@nerve.local', cleanup_tracker, is_superadmin=False)
    founder = _make_user(db_from_client, 'FounderCo', 'founder_super@nerve.local', cleanup_tracker, is_superadmin=True)
    f = log_files(victim.id, 2)  # Cross-Org-Datei (gehoert Fremd-Firma)
    _login(client, founder)

    before = _count_founder_audits(db_from_client)
    r = client.get(f'/admin/logs/download/{f}?grund=support-ticket-42')
    assert r.status_code == 200, "Superadmin darf mit Grund cross-org laden"
    after = _count_founder_audits(db_from_client)
    assert after - before == 1, "GENAU ein audit_log-Eintrag pro Founder-Download"

    row = (db_from_client.query(AuditLog)
           .filter_by(action='founder_log_access')
           .order_by(AuditLog.id.desc()).first())
    d = json.loads(row.details)
    assert d.get('datei') == f and d.get('grund') == 'support-ticket-42', "Metadaten (Datei+Grund) im Audit"
    assert 'Transkript-Fragment' not in (row.details or ''), "KEIN Transkript-Inhalt im Audit (DSGVO)"


def test_founder_download_missing_grund_400(client, db_from_client, cleanup_tracker, log_files):
    founder = _make_user(db_from_client, 'FounderCo2', 'founder_super2@nerve.local', cleanup_tracker, is_superadmin=True)
    f = log_files(founder.id, 3)
    _login(client, founder)
    r = client.get(f'/admin/logs/download/{f}')  # kein grund
    assert r.status_code == 400, "Founder-Download ohne Grund -> 400 (Grund-Pflicht)"


# ── (c) FAIL-CLOSED: Audit-Fehler -> KEIN Download ────────────────────────────

def test_founder_download_fail_closed_when_audit_fails(client, db_from_client, cleanup_tracker, log_files, monkeypatch):
    founder = _make_user(db_from_client, 'FounderCo3', 'founder_super3@nerve.local', cleanup_tracker, is_superadmin=True)
    f = log_files(founder.id, 4)
    _login(client, founder)

    def _boom(*a, **k):
        raise RuntimeError("audit down")
    monkeypatch.setattr(logs_routes, 'log_action', _boom)

    r = client.get(f'/admin/logs/download/{f}?grund=support')
    assert r.status_code != 200, "fail-closed: bei Audit-Fehler KEIN File senden"
    assert b'FounderProbe' not in r.data, "fail-closed: keine Datei-Bytes im Response"
