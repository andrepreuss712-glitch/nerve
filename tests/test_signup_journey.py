"""Phase 08.23.2.AUTH-1 Plan 01 Task 1 — E2E-Signup-Waechter (register-only).

Zweck: beweist, dass die regulaere Registrierung ueber die Landing-Page MIT aktivem
CSRF-Schutz funktioniert (der globale window.fetch-Wrapper aus Plan 01 injiziert das
X-CSRFToken-Header aus dem <meta name="csrf-token">-Tag). Gegen HEAD (vor Plan 01 Task 2/3)
traegt landing.html KEIN Meta-Tag -> der Token ist nicht extrahierbar -> POST /api/register
prallt mit HTTP 400 ab -> test_register_flow_with_csrf ist ROT (Deploy-Gate blockt Restart).
Nach dem Fix (Meta-Tag + Wrapper in landing.html): Token extrahierbar -> 200 -> GRUEN.

CSRF ist im Test EXPLIZIT AN via `client.application.config['WTF_CSRF_ENABLED'] = True`
(Fable BLOCKER 3d — es gibt KEIN `app`-Fixture in conftest; der Toggle laeuft ueber das
bestehende `client`-Fixture). Ohne diesen expliziten AN-Schalter waere der Test blind-gruen
(conftest setzt WTF_CSRF_ENABLED=False als Default) — genau die Klasse Bug, die live durchrutschte.

Journey ist REGISTER-ONLY. NICHT durch Login verlaengern: Login schreibt audit_log;
Migration 0026 blockt UPDATE+DELETE auf audit_log -> uncleanbar -> ein committender
Login-Test faerbt das Gate dauerhaft rot (Fable-Review 2026-07-04, D-05).
`_login_user` selbst (vom Register-Pfad aufgerufen) schreibt KEIN audit_log — der
audit_log-Write sitzt nur im vollen Login-Pfad (_do_login), nicht in _login_user.

Verify NUR ueber den Production-Deploy-Pfad (CLAUDE.md „HART: Kein Local-Dev"):
`bash deploy.sh production` fuehrt pytest auf nerve_test aus (dieser Test wird auto-collected,
kein live/perf-Marker). KEIN lokales pytest als Acceptance.
"""
import re

import pytest
from sqlalchemy import text

from tests.conftest import cleanup_rows
# Session ist in database.models unter dem Namen `Session` exportiert (grep-bestaetigt
# database/models.py:195); auth.py importiert es als Alias `DbSession` (auth.py:8).
from database.models import User, Organisation, Session as DbSession


# Harte @nerve.local-Email (Fable BLOCKER 3b): /api/register triggert send_welcome ->
# echte Resend-Mail AUSSER der Empfaenger endet auf @nerve.local.
_SIGNUP_EMAIL = 'signup_journey_test@nerve.local'


@pytest.fixture
def csrf_client(client):
    """Aktiviert CSRF fuer den Test ueber das bestehende `client`-Fixture (KEIN `app`-Fixture,
    Fable BLOCKER 3d). Teardown setzt den conftest-Default (False) zurueck."""
    client.application.config['WTF_CSRF_ENABLED'] = True
    try:
        yield client
    finally:
        client.application.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture
def cleanup_tracker(db_from_client):
    """Reverse-FK-Cleanup der committeten Register-Rows via cleanup_rows (public.*).

    Reihenfolge Session -> User -> tenant_orgs -> Organisation:
    - Session VOR User: sessions.user_id FK ohne ondelete (auth.py:134) — User-Delete-vor-Session
      scheitert, Session-Row leakt (Fable BLOCKER 3a).
    - tenant_orgs VOR Organisation (DEVIATION vom Plan-Spec {Session,User,Organisation}):
      der AFTER-INSERT-Trigger trg_mk_tenant_org (Migration 0011) legt bei jedem organisations-INSERT
      eine tenant_orgs-Row an (legacy_org_id FK -> organisations.id, KEIN ondelete). Ohne diese Row
      im Cleanup FK-stallt der Organisation-Delete -> Row leakt -> baseline-guard [BASELINE-AUTO-FIX]-
      Warnung. Als 'public.tenant_orgs'-String-Key gefuehrt (id nach Register aus der DB geholt).
    cleanup_rows nutzt intern _DERIVED_FK_ORDER (katalog-abgeleitet) + savepoint-Retry, respektiert
    also die FK-Ordnung robust; die dict-Reihenfolge dokumentiert die Absicht.
    """
    ids = {DbSession: [], User: [], 'public.tenant_orgs': [], Organisation: []}
    yield ids
    cleanup_rows(db_from_client, ids)


def _extract_csrf_token(resp):
    """Zieht den Token aus dem <meta name="csrf-token" content="...">-Tag der Antwort.
    Gegen HEAD (kein Meta-Tag in landing.html) -> None."""
    m = re.search(r'name="csrf-token"\s+content="([^"]+)"', resp.get_data(as_text=True))
    return m.group(1) if m else None


def test_register_flow_with_csrf(csrf_client, db_from_client, cleanup_tracker):
    # 1) Landing-GET (verifizierte Route dashboard.py:410-414, Anonym-Zweig rendert marketing/landing.html)
    landing = csrf_client.get('/')
    assert landing.status_code == 200, f"Landing-GET erwartet 200, war {landing.status_code}"
    token = _extract_csrf_token(landing)

    # 2) Register MIT extrahiertem Token. Gegen HEAD: token None -> '' -> CSRF-400 -> Test ROT.
    payload = {
        'vorname': 'Signup',
        'nachname': 'Journey',
        'email': _SIGNUP_EMAIL,
        'passwort': 'signup-journey-pw-1234',   # >= 8 Zeichen (auth.py:237)
        'firmenname': 'Signup Journey TestCo',
        'branche': 'IT',
        'teamgroesse': '1-5',
    }
    resp = csrf_client.post('/api/register', json=payload,
                            headers={'X-CSRFToken': token or ''})
    # == 200 (NICHT != 400 — sonst maskiert ein Validierungs-400 als Erfolg; Fable BLOCKER 3c).
    assert resp.status_code == 200, (
        f"Register mit CSRF-Token erwartet 200, war {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:200]}"
    )

    # 3) Committete Rows fuer den Cleanup tracken (frische TX -> committete Register-Rows sichtbar).
    db_from_client.rollback()
    user = db_from_client.query(User).filter_by(email=_SIGNUP_EMAIL).first()
    assert user is not None, "Register meldete 200, aber kein User-Row in nerve_test gefunden"
    cleanup_tracker[User].append(user.id)
    cleanup_tracker[Organisation].append(user.org_id)
    for s in db_from_client.query(DbSession).filter_by(user_id=user.id).all():
        cleanup_tracker[DbSession].append(s.id)
    to_row = db_from_client.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :oid"),
        {"oid": user.org_id},
    ).first()
    if to_row is not None:
        cleanup_tracker['public.tenant_orgs'].append(to_row[0])


def test_register_without_token_is_400(csrf_client):
    # OHNE X-CSRFToken -> 400. Beweist, dass CSRF aktiv IST und der Waechter beisst
    # (kein Row-Leak: CSRF blockt VOR dem View, es wird nichts angelegt).
    resp = csrf_client.post('/api/register', json={
        'vorname': 'Signup',
        'email': _SIGNUP_EMAIL,
        'passwort': 'signup-journey-pw-1234',
        'firmenname': 'Signup Journey TestCo',
    })
    assert resp.status_code == 400, (
        f"Register OHNE CSRF-Token erwartet 400 (CSRF aktiv), war {resp.status_code}"
    )
