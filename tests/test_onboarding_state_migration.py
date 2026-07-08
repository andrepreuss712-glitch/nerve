"""Phase 08.23.2.AUTH-2 Plan 01 — Migrations-Waechter fuer 0032 (ERST-ROT).

Prueft, dass nach Migration 0032 die Spalten users.onboarding_state und
users.skip_onboarding korrekt existieren, der Backfill greift (alle Bestands-User
onboarding_state='done'), der CHECK-Constraint ungueltige Werte ablehnt und
skip_onboarding mit Default FALSE angelegt wird.

ERST-ROT-Semantik: Diesen Test ZUERST committen (Task 1) OHNE Migration 0032 (Task 2).
Gegen HEAD (nerve_test noch ohne 0032) MUSS test_columns_exist ROT sein —
deploy.sh-Gate blockt den Restart. Nach Task 2 (0032 eingespielt) wird der Test gruen.

KEIN local-pytest — Verify ausschliesslich via deploy.sh-Gate auf nerve_test (CLAUDE.md HART).

Cleanup: committende Rows raeumen sich im Teardown via cleanup_rows weg.
Reihenfolge: Session-key vor User-key vor Organisation-key (FK-Ordnung).
ASCII: Test-/Fixture-Namen und dict-keys ASCII.
"""
import os
import uuid

import pytest
from sqlalchemy import text

from tests.conftest import cleanup_rows

# ── Real-PG-Guard: kein False-Green auf SQLite / lokal ────────────────────────────────────
_DB_URL = os.environ.get('DATABASE_URL', '') or os.environ.get('TEST_DATABASE_URL', '')
if not _DB_URL.startswith('postgresql'):
    pytest.skip(
        'real-PG only (nerve_test); kein False-Green auf SQLite',
        allow_module_level=True,
    )


# ── Cleanup-Fixture ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def migration_cleanup(db_session):
    """Verfolgt Rows, die vom Test committet werden, und raeumt sie im Teardown weg.
    Reihenfolge: users vor organisations (kein sessions-FK in diesen Tests noetig,
    users.org_id FK zeigt auf organisations -> User zuerst loeschen)."""
    tracker = {
        'public.users': [],
        'public.organisations': [],
        'public.tenant_orgs': [],
    }
    yield db_session, tracker
    cleanup_rows(db_session, tracker)


# ── Hilfsfunktion: minimaler User-Insert ──────────────────────────────────────────────────

def _insert_test_org_and_user(session, tag=''):
    """Legt eine minimale Organisation + User-Row via raw SQL an und committet.
    Gibt (org_id, user_id) zurueck. Der Insert setzt onboarding_state NICHT (DB-Default greift).
    tag wird im Namen verwendet fuer Eindeutigkeit bei mehreren Aufrufen."""
    suffix = uuid.uuid4().hex[:8]
    org_name = f'[AUTH2-TEST] {tag} {suffix}'
    email = f'auth2-test-{tag}-{suffix}@nerve.local'

    # Organisation anlegen (Trigger trg_mk_tenant_org legt tenant_orgs-Row an)
    org_id = session.execute(
        text("INSERT INTO public.organisations (name) VALUES (:n) RETURNING id"),
        {'n': org_name},
    ).scalar()

    # tenant_orgs-UUID fuer spaeteres Cleanup
    tenant_id = session.execute(
        text("SELECT id FROM public.tenant_orgs WHERE legacy_org_id = :oid"),
        {'oid': org_id},
    ).scalar()

    # User anlegen ohne onboarding_state (DB-Default 'pending' soll greifen)
    user_id = session.execute(
        text(
            "INSERT INTO public.users (org_id, email, market, language, is_superadmin, is_test_user) "
            "VALUES (:o, :e, 'dach', 'de', FALSE, TRUE) RETURNING id"
        ),
        {'o': org_id, 'e': email},
    ).scalar()

    session.commit()
    return org_id, user_id, tenant_id


# ── Test A: Spalten-Existenz ───────────────────────────────────────────────────────────────

def test_columns_exist(db_session):
    """ERST-ROT: vor Migration 0032 fehlen die Spalten -> dieser Test ist ROT.
    Nach 0032 sind beide Spalten (onboarding_state TEXT NOT NULL, skip_onboarding boolean) da."""
    rows = db_session.execute(
        text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'users' "
            "  AND column_name IN ('onboarding_state', 'skip_onboarding')"
        )
    ).fetchall()

    found = {r[0]: {'data_type': r[1], 'is_nullable': r[2]} for r in rows}

    assert 'onboarding_state' in found, (
        "users.onboarding_state fehlt — Migration 0032 noch nicht eingespielt?"
    )
    assert 'skip_onboarding' in found, (
        "users.skip_onboarding fehlt — Migration 0032 noch nicht eingespielt?"
    )

    assert found['onboarding_state']['data_type'] == 'text', (
        f"onboarding_state data_type muss 'text' sein, war: {found['onboarding_state']['data_type']!r}"
    )
    assert found['onboarding_state']['is_nullable'] == 'NO', (
        "onboarding_state muss NOT NULL sein (nach Backfill + ALTER COLUMN)"
    )
    assert found['skip_onboarding']['data_type'] == 'boolean', (
        f"skip_onboarding data_type muss 'boolean' sein, war: {found['skip_onboarding']['data_type']!r}"
    )


# ── Test B: Kein NULL + Default pending ───────────────────────────────────────────────────

def test_no_null_and_default_pending(migration_cleanup):
    """Beweist:
    (a) 0 User haben onboarding_state IS NULL (NOT-NULL/Backfill korrekt).
    (b) Neuer User ohne explizites onboarding_state bekommt DB-Default 'pending'.
    """
    session, tracker = migration_cleanup

    # (a) NULL-Zaehlung
    null_count = session.execute(
        text("SELECT count(*) FROM public.users WHERE onboarding_state IS NULL")
    ).scalar()
    assert null_count == 0, (
        f"Es gibt {null_count} User mit onboarding_state IS NULL — "
        "NOT-NULL-Constraint oder Backfill defekt?"
    )

    # (b) Neuer User -> Default 'pending'
    org_id, user_id, tenant_id = _insert_test_org_and_user(session, tag='nulltest')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant_id:
        tracker['public.tenant_orgs'].append(tenant_id)

    state_val = session.execute(
        text("SELECT onboarding_state FROM public.users WHERE id = :uid"),
        {'uid': user_id},
    ).scalar()
    assert state_val == 'pending', (
        f"Neuer User ohne explizites onboarding_state sollte 'pending' (DB-Default) haben, war: {state_val!r}"
    )


# ── Test C: CHECK-Constraint ───────────────────────────────────────────────────────────────

def test_check_constraint_rejects_bogus(migration_cleanup):
    """CHECK ck_users_onboarding_state lehnt ungueltige Werte ab,
    laesst erlaubte Werte (skipped) durch."""
    session, tracker = migration_cleanup

    org_id, user_id, tenant_id = _insert_test_org_and_user(session, tag='checktest')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant_id:
        tracker['public.tenant_orgs'].append(tenant_id)

    # Ungueltigter Wert muss IntegrityError / CheckViolation werfen
    sp = session.begin_nested()
    with pytest.raises(Exception) as exc_info:
        session.execute(
            text("UPDATE public.users SET onboarding_state = 'bogus_value' WHERE id = :uid"),
            {'uid': user_id},
        )
        session.flush()
    sp.rollback()
    assert exc_info.value is not None, (
        "UPDATE mit 'bogus_value' haette CHECK-Constraint-Verletzung werfen sollen"
    )

    # Erlaubter Wert 'skipped' muss durchgehen
    session.execute(
        text("UPDATE public.users SET onboarding_state = 'skipped' WHERE id = :uid"),
        {'uid': user_id},
    )
    session.commit()

    state_after = session.execute(
        text("SELECT onboarding_state FROM public.users WHERE id = :uid"),
        {'uid': user_id},
    ).scalar()
    assert state_after == 'skipped', (
        f"'skipped' ist ein erlaubter CHECK-Wert — sollte 'skipped' sein, war: {state_after!r}"
    )

    # Zuruecksetzen auf 'done' (sauberer Zustand fuer Cleanup)
    session.execute(
        text("UPDATE public.users SET onboarding_state = 'done' WHERE id = :uid"),
        {'uid': user_id},
    )
    session.commit()


# ── Test D: skip_onboarding Default FALSE ─────────────────────────────────────────────────

def test_skip_onboarding_default_false(migration_cleanup):
    """Neuer User ohne explizites skip_onboarding bekommt DB-Default FALSE."""
    session, tracker = migration_cleanup

    org_id, user_id, tenant_id = _insert_test_org_and_user(session, tag='skiptest')
    tracker['public.users'].append(user_id)
    tracker['public.organisations'].append(org_id)
    if tenant_id:
        tracker['public.tenant_orgs'].append(tenant_id)

    skip_val = session.execute(
        text("SELECT skip_onboarding FROM public.users WHERE id = :uid"),
        {'uid': user_id},
    ).scalar()
    assert skip_val is False, (
        f"skip_onboarding sollte FALSE (DB-Default) sein, war: {skip_val!r}"
    )
