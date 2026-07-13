"""Phase 08.23.2.PROFILE-MIGRATE-TXN-FIX Task 1 (TXN-07) — Erst-Rot Regressions-Waechter.

Prueft RUNTIME-Verhalten von `_migrate_profile_json()` gegen real-PG (nerve_test) — KEIN Source-Presence.
Die Transaktions-Vergiftung (totes `ALTER TABLE profile_opener ADD COLUMN type` -> DuplicateColumn /
Permission-Fehler in `except: pass` OHNE rollback) ist Postgres-only; SQLite waere hier False-Green.

Gegen HEAD (vor den TXN-01/02-Fixes) ist Test A ROT: die Mine vergiftet die conn -> der ProfileOpener-Sync
und das finale UPDATE sterben still als `InFailedSqlTransaction` -> das versions-lose Profil bleibt
unmigriert (schema_version bleibt None/1). Nach dem Fix wird es auf LATEST_SCHEMA_VERSION (v4) gehoben.

Import-Reihenfolge (Fable P5): `_migrate_profile_json` erst NACH der Fixture-Engine-Umbindung importieren
(analog `from app import app` in conftest:838). Zusaetzlich wird `app.engine` explizit auf die
nerve_test-Engine der Fixture gebunden, damit die Migration gegen dieselbe DB laeuft.
"""
import json
import uuid

import pytest
from sqlalchemy import text

from services.profile_schema import LATEST_SCHEMA_VERSION


def _insert_versionless_profile(session, opener_text):
    """Insert EIN versions-loses Profil (daten OHNE schema_version) und gib seine id zurueck.
    org_id=1 == [PGTEST-BASE] org (session-scope Base-Seed, conftest _pgtest_base_seed)."""
    daten = json.dumps({'opener': opener_text})  # KEIN schema_version -> version-los
    pid = session.execute(
        text("INSERT INTO profiles (org_id, name, daten) VALUES (1, :n, :d) RETURNING id"),
        {'n': f'migtxn-{uuid.uuid4().hex[:8]}', 'd': daten},
    ).scalar()
    session.commit()
    return pid


def _read_schema_version(session, pid):
    """Liest schema_version AUS dem daten-JSON (profiles hat KEINE schema_version-Spalte)."""
    row = session.execute(
        text("SELECT daten FROM profiles WHERE id=:id"), {'id': pid}
    ).scalar()
    try:
        return (json.loads(row) if row else {}).get('schema_version')
    except Exception:
        return None


def _opener_count(session, pid):
    return session.execute(
        text("SELECT COUNT(*) FROM profile_opener WHERE profile_id=:id"), {'id': pid}
    ).scalar()


def test_migrate_profile_json_versionless_survives_to_latest(client, db_from_client, monkeypatch):
    """Test A (Kern, Erst-Rot): ein versions-loses Profil ueberlebt _migrate_profile_json() -> v4,
    OHNE InFailedSqlTransaction, und der Opener wird nach ProfileOpener gesynct.

    Gegen HEAD ROT: die Mine (ALTER profile_opener ADD COLUMN type) vergiftet die conn -> sync/UPDATE
    sterben still -> Profil bleibt version-los (schema_version None/1) -> assert schlaegt fehl.
    """
    session = db_from_client
    pid = _insert_versionless_profile(session, opener_text='Hallo, guten Tag')

    # Import + Engine-Bindung NACH der Fixture (client hat dbmod.engine bereits auf nerve_test gebunden).
    import app as appmod
    monkeypatch.setattr(appmod, 'engine', client._test_engine)
    from app import _migrate_profile_json

    try:
        _migrate_profile_json()  # darf NICHT werfen (kein InFailedSqlTransaction nach aussen)

        # Ein Folge-SELECT auf der Fixture-Session muss funktionieren (conn nicht vergiftet).
        session.rollback()
        version = _read_schema_version(session, pid)
        assert version == LATEST_SCHEMA_VERSION, (
            f'versions-loses Profil {pid} nach _migrate_profile_json nicht auf '
            f'v{LATEST_SCHEMA_VERSION} gehoben (ist v{version}) — conn vergiftet? '
            f'(InFailedSqlTransaction-Kette der toten ALTER-Mine)'
        )
        assert _opener_count(session, pid) >= 1, (
            f'Profil {pid}: opener wurde nicht nach ProfileOpener gesynct '
            f'(Sync-Statement still als InFailedSqlTransaction gestorben?)'
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(session, {'profile_opener': _opener_ids(session, pid), 'profiles': [pid]})


def test_migrate_profile_json_two_healthy_profiles_both_migrate(client, db_from_client, monkeypatch):
    """Test B (rollback-Isolation): zwei gesunde versions-lose Profile werden in EINEM
    _migrate_profile_json()-Lauf BEIDE auf v4 gehoben. Belegt, dass die Schleife nach conn.rollback()
    im except weiterlaeuft (ein Sync-Fehler blockiert nicht die Migration eines zweiten Profils).
    """
    session = db_from_client
    pid_a = _insert_versionless_profile(session, opener_text='Opener A')
    pid_b = _insert_versionless_profile(session, opener_text='Opener B')

    import app as appmod
    monkeypatch.setattr(appmod, 'engine', client._test_engine)
    from app import _migrate_profile_json

    try:
        _migrate_profile_json()
        session.rollback()
        va = _read_schema_version(session, pid_a)
        vb = _read_schema_version(session, pid_b)
        assert va == LATEST_SCHEMA_VERSION, f'Profil A {pid_a} blieb v{va} (nicht v{LATEST_SCHEMA_VERSION})'
        assert vb == LATEST_SCHEMA_VERSION, f'Profil B {pid_b} blieb v{vb} (nicht v{LATEST_SCHEMA_VERSION})'
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(
            session,
            {
                'profile_opener': _opener_ids(session, pid_a) + _opener_ids(session, pid_b),
                'profiles': [pid_a, pid_b],
            },
        )


def _opener_ids(session, pid):
    return [
        r[0]
        for r in session.execute(
            text("SELECT id FROM profile_opener WHERE profile_id=:id"), {'id': pid}
        ).fetchall()
    ]
