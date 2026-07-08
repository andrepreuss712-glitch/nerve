"""Phase 08.23.2.AUTH-2 Plan 04 — Routing-Matrix-Waechter (ERST-ROT gegen HEAD).

Prueft das Laufzeit-Verhalten von post_login_destination(user) gegen echte User-Objekte
(Function-Call-Return, KEIN source-presence, CLAUDE.md Test-Qualitaets-Regel).

ERST-ROT: services/onboarding_routing.py existiert noch nicht -> ImportError macht diesen
Test ROT, sobald er gegen HEAD eingespielt wird (Task 1). Nach Task 2 (services-Modul) wird
er gruen.

Matrix-Faelle (alle 8):
  1. pending + owner + 0 Profile -> Erstprofil-URL
  2. pending + admin + 0 Profile -> Erstprofil-URL
  3. pending + member + 0 Profile -> None (Member NIE umleiten, D-03)
  4. pending + owner + >=1 Profil -> None + Selbstheilung (onboarding_state='done', D-18)
  5. done + owner + 0 Profile -> None (D-02)
  6. skipped + owner + 0 Profile -> None (D-02)
  7. skip_onboarding=True + pending + owner + 0 Profile -> None (Stufe 1 gewinnt, D-04)
  8. ★ FINDING 2: onboarding_state='step_1' + owner + 0 Profile -> Erstprofil-URL
     (beweist: Weiche liest NOT IN ('done','skipped'), nicht == 'pending')

Finding 3: test_member_submit_rejected (Member-POST-Gate auf Submit-Handler).

Real-PG-Guard: skippt wenn DATABASE_URL nicht postgresql.
Cleanup: cleanup_rows (CLAUDE.md Test-Cleanup-Regel).
ASCII: alle Bezeichner/Dict-Keys/Funktionsnamen.
"""
import os
import uuid

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows

# ── Real-PG-Guard ─────────────────────────────────────────────────────────────
_DB_URL = os.environ.get('DATABASE_URL', '') or os.environ.get('TEST_DATABASE_URL', '')
if not _DB_URL.startswith('postgresql'):
    pytest.skip(
        'real-PG only (nerve_test); kein False-Green auf SQLite/lokal',
        allow_module_level=True,
    )

# ── Import unter Test (ERST-ROT: gegen HEAD ImportError) ──────────────────────
from services.onboarding_routing import post_login_destination  # noqa: E402


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _insert_org_and_user(session, rolle='owner', onboarding_state='pending',
                         skip_onboarding=False):
    """Legt eine Organisation + User via raw SQL an und committet.
    Gibt (org_id, user_id, tenant_uuid) zurueck.
    User bekommt die ORM-Felder als Python-Objekt nach dem Commit via db.get(User).
    Verwendet RAW-SQL fuer Insert um ORM-Pflicht-Felder (market/language/is_test_user)
    explizit zu setzen (kein Python-default, sonst NOT-NULL-Bruch, PGTEST-Lektion).
    """
    suffix = uuid.uuid4().hex[:8]
    org_name = f'[AUTH2-P04-TEST] {rolle} {suffix}'
    email = f'auth2-p04-{rolle}-{suffix}@nerve.local'

    org_id = session.execute(
        text("INSERT INTO public.organisations (name) VALUES (:n) RETURNING id"),
        {'n': org_name},
    ).scalar()

    tenant_uuid = session.execute(
        text("SELECT id FROM public.tenant_orgs WHERE legacy_org_id = :o"),
        {'o': org_id},
    ).scalar()

    user_id = session.execute(
        text(
            "INSERT INTO public.users "
            "(org_id, email, rolle, onboarding_state, skip_onboarding, "
            " market, language, is_superadmin, is_test_user) "
            "VALUES (:org, :em, :ro, :st, :sk, 'dach', 'de', FALSE, TRUE) "
            "RETURNING id"
        ),
        {'org': org_id, 'em': email, 'ro': rolle, 'st': onboarding_state,
         'sk': skip_onboarding},
    ).scalar()

    session.commit()
    return org_id, user_id, tenant_uuid


def _insert_profile(session, org_id, user_id):
    """Legt ein minimales Profil fuer org_id/user_id an und gibt profile_id zurueck."""
    profile_id = session.execute(
        text(
            "INSERT INTO public.profiles (org_id, name, erstellt_von) "
            "VALUES (:oid, 'Test-Profil', :uid) RETURNING id"
        ),
        {'oid': org_id, 'uid': user_id},
    ).scalar()
    session.commit()
    return profile_id


def _get_user_obj(session, user_id):
    """Laedt User-Objekt via ORM (gibt echtes SQLAlchemy-Model zurueck)."""
    from database.models import User
    return session.get(User, user_id)


def _onboarding_state_of(session, user_id):
    """Liest onboarding_state direkt via SQL (re-SELECT nach Selbstheilung)."""
    return session.execute(
        text("SELECT onboarding_state FROM public.users WHERE id = :uid"),
        {'uid': user_id},
    ).scalar()


# ── App-Kontext-Fixture (fuer url_for) ────────────────────────────────────────

@pytest.fixture
def app_ctx(client):
    """Stellt einen Flask-Test-Request-Context bereit, damit url_for() aufloesbar ist."""
    with client.application.test_request_context('/'):
        yield client.application


# ── Cleanup-Fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def routing_cleanup(db_from_client):
    """Verfolgt Rows und raeumt sie im Teardown weg.
    Reihenfolge: profiles vor users vor tenant_orgs vor organisations (FK-Ordnung)."""
    tracker = {
        'public.profiles': [],
        'public.users': [],
        'public.tenant_orgs': [],
        'public.organisations': [],
    }
    yield db_from_client, tracker
    cleanup_rows(db_from_client, tracker)


# ═══════════════════════════════════════════════════════════════════════════════
# Routing-Matrix-Faelle 1–8
# ═══════════════════════════════════════════════════════════════════════════════

def test_owner_pending_no_profiles_returns_url(app_ctx, routing_cleanup):
    """Fall 1: pending + owner + 0 Profile -> Erstprofil-URL (nicht None)."""
    from flask import url_for
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='owner', onboarding_state='pending')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    expected = url_for('onboarding.wizard')
    assert result == expected, (
        f"pending+owner+0 Profile muss Erstprofil-URL '{expected}' liefern, war: {result!r}"
    )


def test_admin_pending_no_profiles_returns_url(app_ctx, routing_cleanup):
    """Fall 2: pending + admin + 0 Profile -> Erstprofil-URL."""
    from flask import url_for
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='admin', onboarding_state='pending')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    expected = url_for('onboarding.wizard')
    assert result == expected, (
        f"pending+admin+0 Profile muss Erstprofil-URL '{expected}' liefern, war: {result!r}"
    )


def test_member_pending_no_profiles_returns_none(app_ctx, routing_cleanup):
    """Fall 3: pending + member + 0 Profile -> None (Member NIE zur Erstprofil-Seite, D-03)."""
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='member', onboarding_state='pending')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    assert result is None, (
        f"pending+member muss None liefern (Member NIE umgeleitet), war: {result!r}"
    )


def test_owner_pending_with_profile_selfheal(app_ctx, routing_cleanup):
    """Fall 4: pending + owner + >=1 Profil -> None UND Selbstheilung onboarding_state='done' (D-18).
    re-SELECT verifiziert dass state nach dem Call in der DB auf 'done' steht."""
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='owner', onboarding_state='pending')
    profile_id = _insert_profile(db, org_id, user_id)
    tracker['public.profiles'].append(profile_id)
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    assert result is None, (
        f"pending+owner+Profil vorhanden muss None (kein Redirect) liefern, war: {result!r}"
    )

    # re-SELECT: Selbstheilung muss onboarding_state auf 'done' gesetzt haben
    # (post_login_destination oeffnet eine eigene Session -> wir brauchen eine neue Abfrage)
    from database.db import get_session
    verify_db = get_session()
    try:
        state_after = _onboarding_state_of(verify_db, user_id)
    finally:
        verify_db.close()

    assert state_after == 'done', (
        f"Selbstheilung: onboarding_state muss nach Call 'done' sein, war: {state_after!r}"
    )


def test_owner_done_returns_none(app_ctx, routing_cleanup):
    """Fall 5: done + owner + 0 Profile -> None (nicht umleiten, D-02)."""
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='owner', onboarding_state='done')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    assert result is None, (
        f"done+owner muss None liefern (nicht umleiten), war: {result!r}"
    )


def test_owner_skipped_returns_none(app_ctx, routing_cleanup):
    """Fall 6: skipped + owner + 0 Profile -> None (nicht umleiten, D-02)."""
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='owner', onboarding_state='skipped')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    assert result is None, (
        f"skipped+owner muss None liefern (nicht umleiten), war: {result!r}"
    )


def test_skip_onboarding_true_returns_none(app_ctx, routing_cleanup):
    """Fall 7: skip_onboarding=True + pending + owner + 0 Profile -> None (Stufe 1, D-04).
    Stufe 1 (skip_onboarding) gewinnt VOR Stufe 3 (Onboarding-State)."""
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(
        db, rolle='owner', onboarding_state='pending', skip_onboarding=True
    )
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    result = post_login_destination(user)

    assert result is None, (
        f"skip_onboarding=True muss None (Stufe 1, kein Onboarding-Redirect) liefern, war: {result!r}"
    )


def test_step_1_state_routes_like_pending(app_ctx, routing_cleanup):
    """★ Fall 8 — FINDING 2: onboarding_state='step_1' + owner + 0 Profile -> Erstprofil-URL.

    Beweist: die Weiche liest NOT IN ('done','skipped'), NICHT == 'pending'.
    Ein hypothetischer step_*-Zwischenzustand (spaeterer Voll-Wizard) darf die Weiche NICHT
    umgehen (genau was D-09 CHECK-Kommentar ausschliessen wollte).

    Implementierungs-Hinweis: 'step_1' ist kein gueltiger CHECK-Wert in 0032 (nur
    pending/done/skipped). Daher testet dieser Fall per in-memory User-Objekt-Attribut-Override
    (kein DB-Persist des 'step_1'-Wertes), weil ein CHECK-verletzender DB-INSERT den Test
    selbst beschaedigen wuerde. post_login_destination(user) liest ausschliesslich via
    getattr(user, 'onboarding_state') -> der In-Memory-Override ist funktional aequivalent
    zu einem zukuenftigen step_*-State nach CHECK-Erweiterung (D-09 Tueroefffner-Design).
    """
    from flask import url_for
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='owner', onboarding_state='pending')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    user = _get_user_obj(db, user_id)
    # In-Memory-Override des States auf 'step_1' (kein DB-Persist, da CHECK wuerde verletzen).
    # Dieser Override simuliert den zukuenftigen Zustand NACH CHECK-Erweiterung (D-09).
    user.onboarding_state = 'step_1'

    result = post_login_destination(user)

    expected = url_for('onboarding.wizard')
    assert result == expected, (
        f"step_1 muss wie pending routen (Erstprofil-URL '{expected}'), war: {result!r}. "
        "Finding 2: Weiche liest NOT IN ('done','skipped'), nicht == 'pending'."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Finding 3 — Member-Submit-Gate (Rollen-Gate auf POST /onboarding/)
# ═══════════════════════════════════════════════════════════════════════════════

def test_member_submit_rejected(client, db_from_client, routing_cleanup):
    """★ Finding 3: Member-POST auf /onboarding/ muss abgewiesen werden (403/Redirect +
    kein Profil angelegt). Prueft, dass das g.user.rolle-Gate auf dem Submit-Handler
    greift — dasselbe Gate wie profiles.py:63.

    Prueft RUNTIME-Verhalten: HTTP-POST mit eingeloggtem Member -> Redirect + 0 neue Profile.
    """
    db, tracker = routing_cleanup
    org_id, user_id, tenant = _insert_org_and_user(db, rolle='member', onboarding_state='pending')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant:
        tracker['public.tenant_orgs'].append(tenant)

    # Profile-Count vor dem Request
    count_before = db.execute(
        text("SELECT COUNT(*) FROM public.profiles WHERE org_id = :oid"),
        {'oid': org_id},
    ).scalar()

    # Session als Member einloggen
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['org_id'] = org_id

    # POST als Member auf Submit-Handler
    resp = client.post('/onboarding/', data={
        'branche_key': 'SaaS',
        'produkt': 'Test-Produkt',
        'csrf_token': 'ignored-in-test',  # CSRF disabled in test-client
    }, follow_redirects=False)

    # Muss Redirect (3xx) oder Fehler (403) liefern, KEIN 200 mit Profil-Anlage
    assert resp.status_code in (302, 303, 403), (
        f"Member-POST auf /onboarding/ muss abgewiesen werden (3xx/403), war: {resp.status_code}"
    )

    # Keine neuen Profile angelegt
    # Neue DB-Session, da post_login_destination und Route ihre eigenen Sessions nutzen
    from database.db import get_session
    verify_db = get_session()
    try:
        count_after = verify_db.execute(
            text("SELECT COUNT(*) FROM public.profiles WHERE org_id = :oid"),
            {'oid': org_id},
        ).scalar()
    finally:
        verify_db.close()

    assert count_after == count_before, (
        f"Member-Submit darf KEINE Profile anlegen: vorher {count_before}, nachher {count_after}"
    )
