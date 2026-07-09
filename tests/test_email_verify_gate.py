"""ERST-ROT Fail-Closed-Verhaltens-Guard fuer das login_required-Gate (Plan 01, D-16b).

Beweist RUNTIME-Verhalten (Request gegen echte PG nerve_test, KEIN Source-Presence,
CLAUDE.md Test-Qualitaets-Regel): ein User mit email_confirmed IS NULL ODER False wird
vom Gate auf die Warteseite ('/auth/confirm-email-pending') umgeleitet; nur explizit
True passiert ungehindert.

★ ERST-ROT: Test A (NULL gatet) MUSS gegen das heutige `... is False`-Gate ROT sein
(None ist NICHT `is False` → NULL-User rutscht heute durch). Gruen erst nach dem
fail-closed Fix (`... is not True`) in Task 2.

Alle Tests raeumen ihre committeten Rows im POST-yield-Teardown via cleanup_rows weg
(Test-Cleanup-Regel, public.* ohne Tenant-GUC). Emails sind uuid-suffixed gegen die
UNIQUE-Constraint auf users.email.
"""

import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import User, Organisation


# ── Cleanup-Tracker: POST-yield reverse-FK-clean der committeten IDs (public.*) ──────
@pytest.fixture
def cleanup_tracker(client):
    """yield ein {Model: [ids]}-Dict; POST-yield reverse-FK-clean via cleanup_rows (public.*)."""
    ids = {User: [], Organisation: []}
    yield ids
    cleanup_rows(client._test_session, ids)


def _make_user(client, tracker, email_confirmed):
    """Legt Org + User auf der MODUL-SessionLocal (client._test_session) an und committet.

    email_confirmed:
      - True/False  -> explizit vor dem commit auf dem ORM-Objekt gesetzt.
      - None        -> nach dem ORM-Insert (ORM-Default greift sonst) via raw
                       UPDATE users SET email_confirmed = NULL zurueckgesetzt + commit,
                       weil der ORM-Default die Spalte sonst nie NULL laesst.
    Returns (org_id, user_id). Registriert beide IDs im tracker fuer cleanup_rows.
    """
    db = client._test_session
    org = Organisation(name='TestOrg', plan='starter')
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=f'evgate-{uuid.uuid4().hex[:8]}@nerve.local',
        passwort_hash=generate_password_hash('secret12345'),
        rolle='owner',
        aktiv=True,
        email_confirmed=(email_confirmed if email_confirmed is not None else True),
    )
    db.add(user)
    db.commit()
    if email_confirmed is None:
        # ORM-Default setzt sonst True/False — echtes NULL nur via raw UPDATE erreichbar.
        db.execute(
            text("UPDATE users SET email_confirmed = NULL WHERE id = :id"),
            {'id': user.id},
        )
        db.commit()
    tracker[Organisation].append(org.id)
    tracker[User].append(user.id)
    return org.id, user.id


def _login(client, org_id, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['org_id'] = org_id


# ── Test A (ERST-ROT-Kern): email_confirmed IS NULL gatet ──────────────────────────
def test_null_email_confirmed_is_gated(client, cleanup_tracker):
    """NULL-User auf @login_required-Route → 302 auf die Warteseite.

    HEUTE ROT: `None is False` == False → der NULL-User passiert das `... is False`-Gate.
    Gruen erst nach fail-closed `... is not True`.
    """
    org_id, user_id = _make_user(client, cleanup_tracker, email_confirmed=None)
    _login(client, org_id, user_id)
    resp = client.get('/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/auth/confirm-email-pending' in resp.headers['Location']


# ── Test B: email_confirmed = False gatet ──────────────────────────────────────────
def test_false_email_confirmed_is_gated(client, cleanup_tracker):
    """False-User auf @login_required-Route → 302 auf die Warteseite."""
    org_id, user_id = _make_user(client, cleanup_tracker, email_confirmed=False)
    _login(client, org_id, user_id)
    resp = client.get('/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/auth/confirm-email-pending' in resp.headers['Location']


# ── Test C: email_confirmed = True passiert ────────────────────────────────────────
def test_true_email_confirmed_passes(client, cleanup_tracker):
    """True-User auf @login_required-Route → KEIN Redirect auf die Warteseite."""
    org_id, user_id = _make_user(client, cleanup_tracker, email_confirmed=True)
    _login(client, org_id, user_id)
    resp = client.get('/dashboard', follow_redirects=False)
    # 200 (Dashboard rendert) ODER Redirect auf etwas ANDERES — nur NICHT die Warteseite.
    loc = resp.headers.get('Location', '') if resp.status_code in (301, 302, 303, 307, 308) else ''
    assert '/auth/confirm-email-pending' not in loc


# ── Test D: Ausnahme-Pfad /auth/confirm_email sperrt einen NULL-User NICHT ──────────
def test_confirm_email_route_not_gated_for_null_user(client, cleanup_tracker):
    """NULL-User auf /auth/confirm_email → KEIN Redirect auf die Warteseite (kein Loop).

    # FINDING 4: beweist nur Nicht-Sperre, NICHT den Gate-Ausnahmezweig (keine
    # @login_required-Route mit /auth/confirm_email-Praefix). /auth/confirm_email traegt
    # bewusst KEIN @login_required → das Gate laeuft dort NIE; der
    # `request.path.startswith('/auth/confirm_email')`-Zweig im Gate ist rein defensiv
    # und wird von keiner heutigen decorierten Route exerziert.
    """
    org_id, user_id = _make_user(client, cleanup_tracker, email_confirmed=None)
    _login(client, org_id, user_id)
    resp = client.get('/auth/confirm_email?token=invalid', follow_redirects=False)
    loc = resp.headers.get('Location', '') if resp.status_code in (301, 302, 303, 307, 308) else ''
    assert '/auth/confirm-email-pending' not in loc
