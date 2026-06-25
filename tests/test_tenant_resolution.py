"""Phase 08.23.2.TENANT-FOUND Plan 01 — Tenant-Aufloesung + Backfill-Idempotenz.

CLAUDE.md-konform: ausschliesslich Runtime-Behavior-Tests gegen REAL-PG nerve_test
(db_session-Fixture seedet einen Test-Mandanten + setzt den app.tenant_id-GUC). KEINE
Source-Presence-Assertions (echte Funktions-Rueckgabe + echte DB-Row-Effekte).

SKIP nur ohne TEST_DATABASE_URL (kein sqlite-Fallback by design — der user->org->tenant_orgs-
Join + das Trigger-Seed gibt es nur auf Postgres, kein False-Green). Im Deploy-Gate laeuft
scharf. Jeder committende Test raeumt seine Rows via cleanup_rows wieder weg (Baseline-Sauberkeit).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _legacy_org_id_for_tenant(db, tenant_uuid):
    """legacy_org_id des geseedeten Test-Tenants (tenant_orgs.id == TEST_TENANT_UUID) lesen —
    damit ein Test-User in genau dieser Org angelegt werden kann (org->tenant 1:1)."""
    from database.models import TenantOrg
    row = db.query(TenantOrg.legacy_org_id).filter(TenantOrg.id == tenant_uuid).first()
    assert row is not None, "Seed-Tenant muss eine tenant_orgs-Row haben"
    return row[0]


def _make_user_in_tenant(db, tenant_uuid):
    """Test-User in der Org des Test-Tenants anlegen -> resolve(user_id) muss TEST_TENANT_UUID
    liefern. Gibt user_id (int) zurueck. Minimal-Pflichtfelder (org_id + unique email; restliche
    NOT-NULL-Spalten haben ORM-Defaults: is_superadmin/market/language)."""
    from database.models import User
    org_id = _legacy_org_id_for_tenant(db, tenant_uuid)
    u = User(org_id=org_id, email=f"tf-resolve-{uuid.uuid4().hex[:10]}@nerve.local")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u.id


# ── Task 1: resolve_tenant_uuid_for_user (Positiv + Negativ) ─────────────────

def test_resolve_tenant_uuid_for_user_positive_and_negative(db_session):
    """Positiv: ein User in der Test-Tenant-Org loest auf TEST_TENANT_UUID auf.
    Negativ: ein nicht-existenter user_id loest auf None auf (kein Crash, kein Default)."""
    from database.db import resolve_tenant_uuid_for_user
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"
    uid = None
    try:
        uid = _make_user_in_tenant(db_session, tenant)

        # Positiv: user->org->tenant_orgs.id == TEST_TENANT_UUID
        got = resolve_tenant_uuid_for_user(uid, db_session)
        assert got == str(tenant), (
            f"resolve muss die Tenant-UUID des Users liefern, war {got!r} (erwartet {tenant!r})")

        # Negativ: unbekannter user_id -> None (KEIN Default-Tenant, KEIN raise)
        assert resolve_tenant_uuid_for_user(99999999, db_session) is None, (
            "Nicht-aufloesbarer user_id MUSS None liefern (fail-closed, kein Default).")
    finally:
        cleanup_rows(db_session, {"public.users": [uid] if uid else []})
