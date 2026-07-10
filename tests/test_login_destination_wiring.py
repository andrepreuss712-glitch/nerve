"""Phase 08.23.2.AUTH-2 Plan 05 Task 1 — E2E Wiring-Waechter (ERST-ROT).

Prueft, dass die 4 Login-Docks (S1-S4) korrekt an post_login_destination angedockt sind.

Sequenz:
  - test_register_owner_lands_on_confirm_pending: Register-Response fuer Unbestaetigte traegt
    'next'=='/auth/confirm-email-pending' (AUTH-EMAIL-VERIFY D-09, Confirm-First — ueberschreibt
    die AUTH-2-Onboarding-Weiche; Onboarding erst NACH dem Bestaetigen).
  - test_login_done_user_no_onboarding_redirect: GRUEN auch gegen HEAD (kein falscher Redirect).
  - test_member_submit_rejected: setzt Plan-04-Submit-Handler voraus (Finding 3 gate) —
    gruen sobald Plan 04 executet ist (routes/onboarding.py Rollen-Gate live).

Verify NUR ueber den Production-Deploy-Pfad (CLAUDE.md 'HART: Kein Local-Dev'):
  bash deploy.sh production  — pytest auf nerve_test, auto-collected (kein live/perf-Marker).

Test-Qualitaets-Regel (CLAUDE.md): API-Response-Assertions (HTTP-Status + JSON-Body),
KEINE Source-Presence-Tests (inspect.getsource/hasattr/grep-auf-Quellcode).
"""
import re

import pytest
from sqlalchemy import text

from tests.conftest import cleanup_rows
from database.models import User, Organisation, Session as DbSession, Profile


# ── @nerve.local-Email-Convention (Fable BLOCKER 3b) ─────────────────────────
# /api/register triggert send_confirmation_email (nach AUTH-EMAIL-VERIFY, statt send_welcome)
# -> echte Resend-Mail AUSSER @nerve.local (im _send-Guard uebersprungen).
_OWNER_EMAIL   = 'wiring_test_owner@nerve.local'
_DONE_EMAIL    = 'wiring_test_done@nerve.local'
_MEMBER_EMAIL  = 'wiring_test_member@nerve.local'


# ── CSRF-Client-Fixture (AUTH-1-Muster, Fable BLOCKER 3d) ────────────────────
@pytest.fixture
def csrf_client(client):
    """Aktiviert CSRF explizit AN. Teardown setzt conftest-Default (False) zurueck."""
    client.application.config['WTF_CSRF_ENABLED'] = True
    try:
        yield client
    finally:
        client.application.config['WTF_CSRF_ENABLED'] = False


def _extract_csrf_token(resp):
    """Zieht den Token aus <meta name='csrf-token' content='...'> (AUTH-1-Muster)."""
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', resp.get_data(as_text=True))
    return m.group(1) if m else None


# ── Test 1: D-09 — Formular-Register → Warteseite (Confirm-First) ────────────

def test_register_owner_lands_on_confirm_pending(csrf_client, db_from_client):
    """AUTH-EMAIL-VERIFY D-09: Register-Response fuer Unbestaetigte hat 'next'=='/auth/confirm-email-pending'.

    Vertrags-Update (Plan 03): api_register ueberschreibt die AUTH-2-Onboarding-Weiche fuer
    unbestaetigte Neu-Registrierte — sie landen auf der Warteseite (email_confirmed=False, das
    fail-closed Gate haelt bis Confirm). Das Onboarding-Routing (S3) greift erst NACH dem
    Bestaetigen (via /login → Weiche → /onboarding/), belegt durch den Confirm-Flow-Guard
    (tests/test_email_verify_creation_paths.py) + Live-UAT.

    API-Response-Assertion (nicht source-presence): prueft resp.get_json()['next'] == '/auth/confirm-email-pending'.
    """
    ids = {DbSession: [], User: [], 'public.tenant_orgs': [], Organisation: []}
    try:
        # Landing-GET -> CSRF-Token
        landing = csrf_client.get('/')
        token = _extract_csrf_token(landing)

        payload = {
            'vorname':     'WiringTest',
            'nachname':    'Owner',
            'email':       _OWNER_EMAIL,
            'passwort':    'wiring-test-pw-9876',
            'firmenname':  'Wiring Test GmbH',
            'branche':     'SaaS',
            'teamgroesse': '1-5',
        }
        resp = csrf_client.post(
            '/api/register',
            json=payload,
            headers={'X-CSRFToken': token or ''},
        )
        assert resp.status_code == 200, (
            f"Register erwartet 200, war {resp.status_code}: "
            f"{resp.get_data(as_text=True)[:300]}"
        )

        data = resp.get_json()
        assert data.get('ok') is True, f"Register-Response nicht ok: {data}"

        # ★ KERN-ASSERTION (D-09): Unbestaetigte Neu-Registrierte landen auf der Warteseite,
        # NICHT auf /onboarding/ (das kommt erst nach dem Confirm). api_register ueberschreibt
        # die AUTH-2-Weiche fuer email_confirmed=False (auth.py:294).
        assert data.get('next') == '/auth/confirm-email-pending', (
            f"Register-Response traegt falsches Ziel: next={data.get('next')!r} "
            f"(erwartet '/auth/confirm-email-pending' — Confirm-First-Flow D-09)"
        )

        # Cleanup-Rows fuer Teardown registrieren
        db_from_client.rollback()
        user = db_from_client.query(User).filter_by(email=_OWNER_EMAIL).first()
        if user:
            ids[User].append(user.id)
            ids[Organisation].append(user.org_id)
            for s in db_from_client.query(DbSession).filter_by(user_id=user.id).all():
                ids[DbSession].append(s.id)
            to_row = db_from_client.execute(
                text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :oid"),
                {"oid": user.org_id},
            ).first()
            if to_row is not None:
                ids['public.tenant_orgs'].append(to_row[0])
    finally:
        cleanup_rows(db_from_client, ids)


# ── Test 2: D-02 — done-User bekommt keinen /onboarding/-Redirect ─────────────

def test_login_done_user_no_onboarding_redirect(client, db_from_client):
    """D-02 (Routing-Matrix): done-User wird NICHT auf /onboarding/ umgeleitet.

    API-Response-Assertion: resp.get_json() hat ok=True; data.get('next') != '/onboarding/'.
    Legt einen done-User per direktem DB-Insert an (kein Register-Pfad, kein audit_log-Leak).
    """
    from werkzeug.security import generate_password_hash
    from database.models import Organisation as OrgModel

    ids = {DbSession: [], User: [], 'public.tenant_orgs': [], Organisation: []}
    try:
        # Done-User + Org direkt per ORM anlegen (kein Register-Pfad -> kein audit_log-Write)
        org = OrgModel(name='DoneUser TestOrg')
        db_from_client.add(org)
        db_from_client.flush()

        done_user = User(
            org_id=org.id,
            email=_DONE_EMAIL,
            passwort_hash=generate_password_hash('done-user-pw-9876'),
            rolle='owner',
        )
        # Setzt onboarding_state explizit auf 'done' (Bestandsuser-Simulation)
        done_user.onboarding_state = 'done'
        db_from_client.add(done_user)
        db_from_client.commit()

        # Cleanup tracken
        ids[User].append(done_user.id)
        ids[Organisation].append(org.id)
        to_row = db_from_client.execute(
            text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :oid"),
            {"oid": org.id},
        ).first()
        if to_row is not None:
            ids['public.tenant_orgs'].append(to_row[0])

        # POST /api/login (kein CSRF-Token im Test: conftest setzt WTF_CSRF_ENABLED=False)
        resp = client.post('/api/login', json={
            'email':    _DONE_EMAIL,
            'passwort': 'done-user-pw-9876',
        })
        assert resp.status_code == 200, (
            f"Login erwartet 200, war {resp.status_code}: {resp.get_data(as_text=True)[:200]}"
        )
        data = resp.get_json()
        assert data.get('ok') is True, f"Login-Response nicht ok: {data}"

        # D-02-Assertion: done-User bekommt KEINEN /onboarding/-Redirect
        assert data.get('next') != '/onboarding/', (
            f"done-User wurde faelschlich auf /onboarding/ weitergeleitet: next={data.get('next')!r} "
            f"(D-02: done/skipped-User werden NICHT umgeleitet)"
        )

        # Cleanup fuer Login-Session (audit_log NICHT committet von _login_user -- kein Leak-Risiko)
        db_from_client.rollback()
        for s in db_from_client.query(DbSession).filter_by(user_id=done_user.id).all():
            ids[DbSession].append(s.id)
    finally:
        cleanup_rows(db_from_client, ids)


# ── Test 3: Finding 3 — Member-Submit auf /onboarding/ wird abgewiesen ────────

def test_member_submit_rejected(client, db_from_client):
    """Finding 3 (Plan 04 Rollen-Gate routes/onboarding.py:195): Member-User kann kein
    Erstprofil via POST /onboarding/ anlegen (302 oder 403). Gegenprobe: Profil-Count unveraendert.

    Setzt Plan-04-Submit-Handler voraus (routes/onboarding.py Rollen-Gate). Dieser Test laeuft
    GRUEN sobald Plan 04 executet ist. Gegen HEAD (vor Plan 04): /onboarding/ stub -> 302 ->
    ebenfalls kein Profil angelegt -> Test-Assertion (count unveraendert) trotzdem GRUEN.

    API-Response-Assertion: HTTP-Status 302 oder 403; SELECT COUNT(*) Profile unveraendert.
    """
    from werkzeug.security import generate_password_hash
    from database.models import Organisation as OrgModel

    ids = {DbSession: [], Profile: [], User: [], 'public.tenant_orgs': [], Organisation: []}
    try:
        # Org + Member-User direkt per ORM anlegen (kein Register-Pfad)
        org = OrgModel(name='Member Reject TestOrg')
        db_from_client.add(org)
        db_from_client.flush()

        member_user = User(
            org_id=org.id,
            email=_MEMBER_EMAIL,
            passwort_hash=generate_password_hash('member-reject-pw-9876'),
            rolle='member',
        )
        db_from_client.add(member_user)
        db_from_client.commit()

        ids[User].append(member_user.id)
        ids[Organisation].append(org.id)
        to_row = db_from_client.execute(
            text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :oid"),
            {"oid": org.id},
        ).first()
        if to_row is not None:
            ids['public.tenant_orgs'].append(to_row[0])

        # Profil-Count VOR Submit
        profile_count_before = db_from_client.query(Profile).filter_by(org_id=org.id).count()

        # Member-Session etablieren (Login ohne CSRF, conftest hat WTF_CSRF_ENABLED=False)
        login_resp = client.post('/api/login', json={
            'email':    _MEMBER_EMAIL,
            'passwort': 'member-reject-pw-9876',
        })
        assert login_resp.status_code == 200, (
            f"Member-Login erwartet 200, war {login_resp.status_code}"
        )

        # Cleanup Login-Session tracken
        db_from_client.rollback()
        for s in db_from_client.query(DbSession).filter_by(user_id=member_user.id).all():
            ids[DbSession].append(s.id)

        # POST /onboarding/ als Member (Finding 3 — Rollen-Gate)
        # Erwartet 302 (Redirect zu Dashboard) ODER 403 (Forbidden).
        submit_resp = client.post('/onboarding/', data={
            'branche_key': 'SaaS',
            'produkt':     'Testsoftware fuer Vertrieb',
        }, follow_redirects=False)

        assert submit_resp.status_code in (302, 403), (
            f"Member-Submit auf /onboarding/ erwartet 302 oder 403, war {submit_resp.status_code} "
            f"(Finding 3: Member duerfen kein Erstprofil anlegen)"
        )

        # Gegenprobe: Profil-Count unveraendert (kein Profil angelegt)
        db_from_client.rollback()
        profile_count_after = db_from_client.query(Profile).filter_by(org_id=org.id).count()
        assert profile_count_after == profile_count_before, (
            f"Member-Submit legte trotz Gate ein Profil an: "
            f"count vorher={profile_count_before}, nachher={profile_count_after} "
            f"(Finding 3: Rollen-Gate in routes/onboarding.py fehlt oder defekt)"
        )

    finally:
        cleanup_rows(db_from_client, ids)
