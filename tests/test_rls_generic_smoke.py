"""A-1-Tripwire — der GENERISCHE db_session-Pfad beweist Runtime-RLS-Sichtbarkeit (Phase 08.23.2.PGTEST).

WARUM DIESER TEST EXISTIERT (A-1):
  db.py registriert den after_begin-RLS-Hook (_set_tenant_txn_local, db.py:87) zur IMPORT-ZEIT NUR wenn
  DATABASE_URL (NICHT TEST_DATABASE_URL) non-sqlite ist (db.py:86 `if 'sqlite' not in _DATABASE_URL`). Wenn
  das Gate (Plan 02) DATABASE_URL=postgres NICHT exportiert, picked db.py den sqlite-Default beim Import ->
  der Hook wird NIE registriert -> set_current_tenant(...) ist inert -> generische crm-Reads liefern 0 Zeilen
  -> Tests passen STILL (False-Green). Dieser Test ist die EINZIGE Assertion, die diesen Defekt von
  silent-green auf loud-red dreht. test_tenant_orgs.py kann das NICHT (public-only, beruehrt KEIN crm).

ASSERTIONS sind echte Runtime-GUC- + Row-Count-Pruefungen (keine Source-Presence, CLAUDE.md-Test-Regel).
SKIP nur wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback) — im Gate laeuft er scharf.
"""
import uuid

from sqlalchemy import text

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def test_a1_generic_path_guc_set_and_crm_visible(db_session):
    """A-1-Tripwire auf dem generischen db_session-Pfad: GUC NON-null + crm-Read >=1 Zeile.

    Arm (a): current_setting('app.tenant_id', true) == TEST_TENANT_UUID (NON-null) — beweist DIREKT, dass
             der after_begin-Hook auf der generischen MODUL-Session feuerte (waere DATABASE_URL beim Import
             sqlite, waere dieser Wert NULL -> RED, nicht silent-green).
    Arm (b): ein crm.accounts-Read unter dem Tenant liefert >=1 Zeile (vorher 1 Row geseedet) — beweist
             tenant-scoped Sichtbarkeit end-to-end, NICHT 0-Zeilen-fail-closed.
    """
    # Die db_session-Fixture hat TEST_TENANT_UUID geseedet + set_current_tenant aufgerufen.
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"

    acct_id = str(uuid.uuid4())
    try:
        # Arm (a): GUC NON-null — beweist der after_begin-Hook feuerte auf DIESER MODUL-Session.
        guc = db_session.execute(
            text("SELECT current_setting('app.tenant_id', true)")
        ).scalar()
        assert guc == tenant, (
            f"A-1: app.tenant_id GUC == {guc!r}, erwartet {tenant!r} (NON-null). "
            "Der after_begin-RLS-Hook hat NICHT gefeuert -> DATABASE_URL war beim Import vermutlich "
            "sqlite-Default (A-1 / Plan 02 FIX 1 exportiert DATABASE_URL=postgres)."
        )

        # Arm (b): crm.accounts-Row unter dem Tenant seeden (tenant_id MUSS == GUC, sonst RLS WITH CHECK).
        db_session.execute(
            text("INSERT INTO crm.accounts (id, tenant_id, name) "
                 "VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name)"),
            {"id": acct_id, "tid": tenant, "name": "[PGTEST-SMOKE] account " + tenant[:8]},
        )
        db_session.commit()

        count = db_session.execute(
            text("SELECT count(*) FROM crm.accounts WHERE tenant_id = CAST(:tid AS uuid)"),
            {"tid": tenant},
        ).scalar()
        assert count >= 1, (
            f"A-1: crm.accounts-Read unter Tenant {tenant!r} lieferte {count} Zeilen (erwartet >=1). "
            "RLS fail-closed (0 Zeilen) deutet auf nicht-gesetzten Tenant-GUC -> Hook feuerte nicht."
        )
    finally:
        # crm-Baseline=0-Konformitaet (HYBRID, André locked): die geseedete crm.accounts-Row via dem
        # gemeinsamen cleanup_rows-Helfer (Extension 1) wieder loeschen -> crm.accounts == 0 nach dem Test
        # (POST-SUITE-crm-Check in Plan 02 gruen; der in-pytest public-Waechter prueft crm.* nicht).
        cleanup_rows(db_session, {"crm.accounts": [acct_id]}, tenant=tenant)
