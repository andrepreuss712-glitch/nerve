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


def test_migrate_profile_json_rollback_isolation_real_error(client, db_from_client, monkeypatch):
    """Test B (GESCHAERFT, CONS-B4): ECHTE Fehler-Isolation. Zwei gesunde v1-Profile + EIN Profil,
    dessen finales UPDATE deterministisch scheitert (nicht-serialisierbarer _mpd-Rueckgabewert ->
    json.dumps TypeError am UPDATE-Seam app.py:1520, gefangen vom UPDATE-except :1528 -> conn.rollback()).

    Belegt: der Fehler ist isoliert (conn.rollback im except), die Schleife laeuft weiter -> das NACH
    dem defekten Profil einsortierte gesunde Profil (pid_b) wird trotzdem auf v4 migriert (keine
    Kaskade), und der Aufruf wirft nicht. Real-Error-Seam statt kuenstlichem Skip (Plan CONS-B4).
    """
    session = db_from_client
    pid_a = _insert_versionless_profile(session, opener_text='Opener A')       # zuerst (committet vor dem Defekt)
    pid_bad = _insert_versionless_profile(session, opener_text='Opener BAD')   # mitte: UPDATE scheitert
    pid_b = _insert_versionless_profile(session, opener_text='Opener B')       # NACH dem Defekt

    # Real-Error-Seam: _mpd gibt fuer das Bad-Profil einen nicht-serialisierbaren Wert (set) zurueck ->
    # json.dumps am UPDATE (app.py:1520) wirft TypeError -> UPDATE-except (:1528) -> conn.rollback().
    import services.profile_schema as _ps
    _real_mpd = _ps._migrate_profile_data

    def _poison_mpd(daten):
        _res = _real_mpd(daten)
        if isinstance(daten, dict) and daten.get('opener') == 'Opener BAD':
            _res['__nonserializable__'] = {1, 2}   # set -> json.dumps TypeError am UPDATE-Seam
        return _res

    monkeypatch.setattr(_ps, '_migrate_profile_data', _poison_mpd)

    import app as appmod
    monkeypatch.setattr(appmod, 'engine', client._test_engine)
    from app import _migrate_profile_json

    try:
        _migrate_profile_json()   # darf NICHT werfen (TypeError im UPDATE-except gefangen)
        session.rollback()
        va = _read_schema_version(session, pid_a)
        vb = _read_schema_version(session, pid_b)
        assert va == LATEST_SCHEMA_VERSION, f'gesundes Profil A {pid_a} blieb v{va} (Kaskade vom Defekt?)'
        assert vb == LATEST_SCHEMA_VERSION, (
            f'gesundes Profil B {pid_b} (NACH dem Defekt) blieb v{vb} — Schleife nach dem Fehler '
            f'abgebrochen statt via conn.rollback isoliert weitergelaufen'
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(
            session,
            {
                'profile_opener': (
                    _opener_ids(session, pid_a) + _opener_ids(session, pid_bad) + _opener_ids(session, pid_b)
                ),
                'profiles': [pid_a, pid_bad, pid_b],
            },
        )


def _opener_ids(session, pid):
    return [
        r[0]
        for r in session.execute(
            text("SELECT id FROM profile_opener WHERE profile_id=:id"), {'id': pid}
        ).fetchall()
    ]


# ── Phase 08.23.2.PROFILE-MIGRATE-CONSOLIDATE Task 1 — Erst-Rot fuer A2/A2b/A2c + B2-Coverage ──
# Alle real-PG (nerve_test), KEIN Source-Presence. Import-/Engine-Bindung wie Test A/B.


def _insert_profile_with_version(session, version, extra=None):
    """Insert ein Profil mit daten.schema_version=<version> (+ optionale extra-Felder). id zurueck."""
    d = {'schema_version': version}
    if extra:
        d.update(extra)
    pid = session.execute(
        text("INSERT INTO profiles (org_id, name, daten) VALUES (1, :n, :d) RETURNING id"),
        {'n': f'migcons-{uuid.uuid4().hex[:8]}', 'd': json.dumps(d)},
    ).scalar()
    session.commit()
    return pid


def _insert_versionless_profile_full(session):
    """v1/versions-los mit opener + pitch + erlaubnis im daten-JSON (fuer Sync-Coverage-Test D)."""
    daten = json.dumps({'opener': 'Op-Text', 'pitch': 'Pi-Text', 'erlaubnis': 'Er-Text'})
    pid = session.execute(
        text("INSERT INTO profiles (org_id, name, daten) VALUES (1, :n, :d) RETURNING id"),
        {'n': f'migcons-{uuid.uuid4().hex[:8]}', 'd': daten},
    ).scalar()
    session.commit()
    return pid


def _insert_existing_opener_row(session, pid, type_):
    """Bestands-profile_opener-Row EINES Typs anlegen (Test-F-Precondition: COUNT>0, type-los)."""
    session.execute(
        text("INSERT INTO profile_opener (profile_id, name, inhalt, sortierung, type, is_personalized) "
             "VALUES (:pid, 'Pre', 'bestand', 5, :t, false)"),
        {'pid': pid, 't': type_},
    )
    session.commit()


def _opener_types(session, pid):
    return sorted(
        r[0] for r in session.execute(
            text("SELECT type FROM profile_opener WHERE profile_id=:id"), {'id': pid}
        ).fetchall()
    )


def _created_at_null_count(session, pid, type_=None):
    q = "SELECT COUNT(*) FROM profile_opener WHERE profile_id=:id AND created_at IS NULL"
    params = {'id': pid}
    if type_:
        q += " AND type=:t"
        params['t'] = type_
    return session.execute(text(q), params).scalar()


def _run_migration(client, monkeypatch):
    """Engine an nerve_test binden + _migrate_profile_json ausfuehren (Muster Test A/B)."""
    import app as appmod
    monkeypatch.setattr(appmod, 'engine', client._test_engine)
    from app import _migrate_profile_json
    _migrate_profile_json()


def test_migrate_v3_profile_lifted_to_latest(client, db_from_client, monkeypatch):
    """Test C (Erst-Rot CONS-A2): ein v3-Profil wird auf LATEST_SCHEMA_VERSION (v4) gehoben.
    Gegen HEAD ROT: der Idempotenz-Skip `>= 2` (app.py:1461) ueberspringt v3 -> bleibt v3."""
    session = db_from_client
    pid = _insert_profile_with_version(session, 3)
    try:
        _run_migration(client, monkeypatch)
        session.rollback()
        v = _read_schema_version(session, pid)
        assert v == LATEST_SCHEMA_VERSION, (
            f'v3-Profil {pid} nicht auf v{LATEST_SCHEMA_VERSION} gehoben (ist v{v}) — '
            f'Skip >=2 statt >=LATEST_SCHEMA_VERSION? (CONS-A2)'
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(session, {'profile_opener': _opener_ids(session, pid), 'profiles': [pid]})


def test_migrate_v1_syncs_opener_pitch_erlaubnis_with_created_at(client, db_from_client, monkeypatch):
    """Test D (CONS-B2 + Sync-Coverage): v1 mit opener+pitch+erlaubnis (KEINE Bestands-Rows) ->
    drei typisierte profile_opener-Rows, alle mit created_at NICHT NULL.
    Gegen HEAD ROT (via created_at): rohe INSERTs setzen kein created_at (Python-default greift bei raw SQL nicht)."""
    session = db_from_client
    pid = _insert_versionless_profile_full(session)
    try:
        _run_migration(client, monkeypatch)
        session.rollback()
        types = _opener_types(session, pid)
        assert types == ['erlaubnis', 'opener', 'pitch'], (
            f'Profil {pid}: profile_opener-Typen {types} != [erlaubnis, opener, pitch]'
        )
        assert _created_at_null_count(session, pid) == 0, (
            f'Profil {pid}: profile_opener created_at NULL — roher INSERT ohne created_at (CONS-B2)'
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(session, {'profile_opener': _opener_ids(session, pid), 'profiles': [pid]})


def test_migrate_v2_logs_real_profile_id_not_questionmark(client, db_from_client, monkeypatch, capsys):
    """Test E (Erst-Rot CONS-A2b): ein durchfliessendes v2-Profil loggt die ECHTE Profil-ID, nicht 'Profile ?'.

    Gegen HEAD ROT: v2 wird geskippt (>=2) -> gar kein v2->v3-Log. Nach A2-only: '[Schema] Profile ?'
    (kein _migration_profile_id injiziert). Nach A2b: '[Schema] Profile {pid}: v2->v3'. Dieselbe
    _migration_profile_id steuert auch audit_log.target_id (profile_schema.py:399-403) — der print ist
    der robuste, session-bindungs-unabhaengige Beleg fuer den Fix."""
    session = db_from_client
    pid = _insert_profile_with_version(session, 2)
    try:
        _run_migration(client, monkeypatch)
        out = capsys.readouterr().out
        assert '[Schema] Profile ?' not in out, (
            f"'[Schema] Profile ?' im Log — _migration_profile_id nicht injiziert (CONS-A2b).\n{out}"
        )
        assert f'Profile {pid}: v2->v3' in out, (
            f"kein '[Schema] Profile {pid}: v2->v3'-Log — v2 geskippt (>=2, CONS-A2 fehlt) "
            f"oder falsche/keine ID.\n{out}"
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(session, {'profile_opener': _opener_ids(session, pid), 'profiles': [pid]})


def test_migrate_opener_synced_despite_existing_row_of_other_type(client, db_from_client, monkeypatch):
    """Test F (Erst-Rot CONS-A2c): ein v1-Profil mit opener-Text UND einer Bestands-profile_opener-Row
    eines ANDEREN Typs (pitch) -> nach dem Lauf existiert trotzdem eine type='opener'-Row (kein stiller
    Verlust). created_at der opener-Row NICHT NULL (CONS-B2).

    Gegen HEAD ROT: der type-lose COUNT-Gate (app.py:1469 `WHERE profile_id=:pid`) sieht COUNT>0 ->
    opener-INSERT ausgelassen -> _mpd poppt opener (profile_schema.py:304) -> Opener fuer immer weg."""
    session = db_from_client
    pid = _insert_versionless_profile(session, opener_text='Erhalte diesen Opener')
    _insert_existing_opener_row(session, pid, 'pitch')  # COUNT>0, ANDERER Typ als opener
    try:
        _run_migration(client, monkeypatch)
        session.rollback()
        types = _opener_types(session, pid)
        assert 'opener' in types, (
            f'Profil {pid}: keine opener-Row nach dem Lauf (types={types}) — type-loser COUNT-Gate hat '
            f'den opener-INSERT ausgelassen, _mpd hat opener gepoppt = stiller Verlust (CONS-A2c)'
        )
        assert _created_at_null_count(session, pid, 'opener') == 0, (
            f'Profil {pid}: opener-Row created_at NULL (CONS-B2)'
        )
    finally:
        from tests.conftest import cleanup_rows
        session.rollback()
        cleanup_rows(session, {'profile_opener': _opener_ids(session, pid), 'profiles': [pid]})
