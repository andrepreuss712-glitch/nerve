import os
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure repo root is on sys.path so `from services.ki_logik import ...`
# works regardless of pytest invocation directory.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from database.db import Base
# Import all models so Base.metadata knows about them
import database.models  # noqa: F401


# ── Phase 08.23.2.PGTEST — generic fixtures bind to REAL Postgres nerve_test ──────────────
# KONVENTION (Baseline-Sauberkeit, Phase 08.23.2.PGTEST Option-A): Jeder Test, der Daten in nerve_test
# COMMITTET, registriert seine erzeugten Row-IDs und ruft cleanup_rows(...) in seiner POST-yield-Sektion,
# um sie reverse-FK-clean (crm.* unter Tenant-GUC) wieder zu loeschen. Erzwungen vom autouse
# _baseline_cleanup_guard (Extension 2). Nicht aufgeraeumte public-Rows => Waechter rot => Gate blockt Deploy.
# crm.*/training.* werden NICHT in-pytest geprueft (nerve_app saehe crm.* nur tenant-gefiltert) — ihre
# Sauberkeit (jede crm.* Tabelle == 0 Rows, training.transcript_archive == 0) erzwingt der POST-SUITE-Check
# in deploy.sh (Plan 02, sudo -u postgres psql, peer-auth). Bei Cleanup-Fehler emittiert cleanup_rows eine
# laute [PGTEST-CLEANUP]-Warnung (Attribution, #5).

# Seed-erzeugt (NICHT feste Konstante): crm.* FKs zeigen auf public.tenant_orgs(id); eine erfundene UUID
# wuerde FK-Verletzung werfen (RESEARCH Q4b). Wird vom _seed_test_tenant-Helper beim ersten db_session/client
# gefuellt; der A-1-Tripwire (tests/test_rls_generic_smoke.py) liest sie ueber das exportierte Modul-Attribut.
TEST_TENANT_UUID = None


def _seed_test_tenant(engine):
    """Seede einen Test-Mandanten via Trigger-Muster (test_rls_isolation.py:_new_tenant) und gib seine
    UUID zurueck. INSERT organisations -> AFTER-INSERT-Trigger trg_mk_tenant_org legt die tenant_orgs-Row
    automatisch an -> SELECT tenant_orgs.id zurueck (NICHT manuell inserten, sonst UNIQUE(legacy_org_id)).
    Setzt das Modul-Attribut TEST_TENANT_UUID, damit Tests (A-1-Tripwire) es importieren koennen.
    Org-Name uuid-suffixed: [PGTEST-GENERIC]-Prefix fuer Analytics-Exklusion-Lineage, der uuid-Suffix
    verhindert Unique-Kollisionen bei xdist / verpasstem Teardown (Gemini-LOW)."""
    global TEST_TENANT_UUID
    org_name = f"[PGTEST-GENERIC] tenant {uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        org_id = conn.execute(
            text("INSERT INTO public.organisations (name) VALUES (:n) RETURNING id"),
            {"n": org_name},
        ).scalar()
        tenant_id = conn.execute(
            text("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = :oid"),
            {"oid": org_id},
        ).scalar()
    TEST_TENANT_UUID = tenant_id
    return tenant_id


@pytest.fixture(scope="session", autouse=True)
def _pgtest_base_seed():
    """Session-Scope Base-Seed: 1 Organisation(id=1) + 1 User(id=1) gegen nerve_test fuer FK-tragende
    generische Tests (user_id=1/org_id=1 auf PUBLIC-Tabellen) — sonst FK/NOT-NULL-Bruch auf der zero-data PG.

    A-1-Abhaengigkeit: die MODUL-Engine (database.db.engine/SessionLocal) ist beim Import bereits nerve_test-PG,
    weil das Gate (Plan 02 FIX1, T-PGTEST-18) DATABASE_URL=postgresql://nerve_app@/nerve_test exportiert
    (commit d7d8358). Daher seedet diese Fixture gegen live nerve_test mit aktiver RLS-Machinerie.

    ORM-Pfad PFLICHT (NICHT RAW-SQL): is_superadmin/is_test_user/market/language sind nullable=False mit nur
    PYTHON-default= (kein server_default) -> ein RAW-INSERT wuerde sie NICHT fuellen -> NOT-NULL-Bruch
    (models.py:19-135 verifiziert). Der Org-INSERT feuert trg_mk_tenant_org -> tenant_orgs-Row automatisch
    (KEIN manueller Insert, sonst UNIQUE(legacy_org_id), F1-Lektion). Sequenz-Advance nach dem Insert
    (PG-Gotcha: explizite id advanced die serial-Sequenz NICHT -> spaeterer serieller Insert retry'te id=1).
    Commit auf eigener Session -> ueberlebt den function-scoped db_session-Rollback. Laeuft VOR dem
    Baseline-Snapshot (Task 6) -> die Base-Rows gehoeren zur erlaubten Baseline (kein Leak).
    """
    if not os.environ.get('TEST_DATABASE_URL'):
        # Kein Seed lokal (kein sqlite-Fallback) — nur im Gate scharf.
        yield
        return

    import database.db as dbmod
    from database.models import Organisation, User
    session = dbmod.SessionLocal()
    try:
        # Idempotenz: falls die Base-Rows schon existieren (Re-Run gegen nicht frisch gedroppte DB) -> skip.
        if session.get(Organisation, 1) is None:
            org = Organisation(id=1, name="[PGTEST-BASE] org")
            session.add(org)
            session.flush()                 # feuert trg_mk_tenant_org -> tenant_orgs-Row auto
            user = User(id=1, org_id=1, email="pgtest-base@nerve.local")
            # is_superadmin/is_test_user/market/language kommen aus Python-default= (ORM-Pfad).
            session.add(user)
            session.commit()
            # Sequenz-Advance (PG explicit-id-no-sequence-advance-Gotcha).
            session.execute(text(
                "SELECT setval('organisations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organisations))"
            ))
            session.execute(text(
                "SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id),1) FROM users))"
            ))
            session.commit()
    finally:
        session.close()
    yield


# ── Phase 08.23.2.PGTEST Extension 1 — gemeinsamer cleanup_rows-Teardown-Helfer ──────────────
# Reverse-FK-Reihenfolge der bekannten Tabellen-Familien (Kind zuerst, Eltern zuletzt). crm.* MUSS
# unter gesetztem Tenant-GUC geloescht werden (sonst RLS fail-closed -> DELETE trifft 0 Rows -> Leak).
# public.* braucht keinen GUC. Tabellen, die NICHT in dieser Liste stehen, werden in der uebergebenen
# Reihenfolge am Ende angehaengt — best-effort.
_CLEANUP_FK_ORDER = [
    "crm.account_memory",
    "crm.meetings",
    "crm.contacts",
    "crm.accounts",
    "crm.user_preferences",
    "public.objection_event",
    "public.conversation_logs",
    "public.calls",
    "public.api_cost_log",
    "public.revenue_log",
    "public.ewb_ratings",
    "public.profiles",
    "public.users",
    "public.tenant_orgs",
    "public.organisations",
]


def _normalize_table_name(key):
    """Akzeptiere ein ORM-Model ODER einen Tabellen-String. Liefert den qualifizierten DB-Namen
    'schema.table' (crm.*/training.* tragen ihr Schema, public ohne Praefix wird zu public.<t>)."""
    if isinstance(key, str):
        return key if "." in key else f"public.{key}"
    tname = getattr(key, "__tablename__", None)
    if tname is None:
        return str(key)
    schema = None
    targs = getattr(key, "__table_args__", None)
    if isinstance(targs, (tuple, list)):
        for item in targs:
            if isinstance(item, dict) and "schema" in item:
                schema = item["schema"]
    elif isinstance(targs, dict):
        schema = targs.get("schema")
    return f"{schema}.{tname}" if schema else f"public.{tname}"


def cleanup_rows(conn_or_session, spec, tenant=None):
    """Gemeinsamer best-effort Teardown-Helfer (Extension 1) — modelliert auf test_rls_isolation.py:101-116.

    Jeder committende Test ruft cleanup_rows(...) in seiner POST-yield-Sektion, um seine EIGENEN committeten
    Rows reverse-FK-clean wieder zu loeschen. Akzeptiert eine SQLAlchemy-Session ODER eine psycopg2-Connection.
    spec = {Model_oder_'schema.tabelle': [id, ...]}. tenant (UUID-str) ist PFLICHT wenn crm.*-Tabellen im spec
    stehen (sonst RLS fail-closed -> 0 geloescht -> Leak).

    DREI-SCHRITT-CONTRACT (#6, Delta-Review-5, BLOCKER):
      SCHRITT 1: UNBEDINGTER rollback ALS ALLERERSTE Aktion — verwirft den uncommitteten In-Flight-State eines
                 mid-body gecrashten Tests (AssertionError NACH einem crm-INSERT, VOR seinem commit). OHNE diesen
                 fuehrenden rollback wuerde der commit in Schritt 3 die Garbage PERMANENT in nerve_test zementieren
                 (crm.*-Leak, den der public-only Waechter Task 6 NICHT sieht).
      SCHRITT 2: reverse-FK-DELETE NUR der vom Caller uebergebenen (= zuvor committeten, test-eigenen) IDs unter
                 dem richtigen Tenant-GUC (crm.* via set_config); loescht NIE Baseline-Rows (id=1/[PGTEST-BASE]/
                 app-import-Seeds) — nur die explizit uebergebenen IDs.
      SCHRITT 3: commit.
    CONTRACT: Caller uebergeben NUR ihre EIGENEN committeten IDs.

    #5 (Gemini-3.1-Pro-Fold): bei einem Cleanup-Fehler emittiert der Helfer NACH dem rollback eine LAUTE
    [PGTEST-CLEANUP]-Warnung (logger.warning/stderr, Tabelle/ids/Exception-repr) — kaputter Teardown laut +
    attribuierbar statt still verschluckt. Bleibt best-effort (KEIN hartes re-raise — der Baseline-Waechter
    (Task 6) / POST-SUITE-Check (Plan 02) ist der fail-closed Backstop).
    """
    norm = {}
    for key, ids in spec.items():
        norm[_normalize_table_name(key)] = list(ids or [])

    has_crm = any(t.startswith("crm.") for t in norm)
    if has_crm and not tenant:
        raise ValueError(
            "cleanup_rows: crm.*-Tabellen im spec, aber kein tenant uebergeben -> RLS fail-closed "
            "(DELETE wuerde 0 Rows treffen). tenant=<UUID-str> ist Pflicht."
        )

    # psycopg2-Connection (hat .cursor(), keine .execute()) vs SQLAlchemy-Session.
    is_psycopg2 = hasattr(conn_or_session, "cursor") and not hasattr(conn_or_session, "execute")

    # SCHRITT 1 (#6): unbedingter rollback — uncommitteten In-Flight-State verwerfen.
    try:
        conn_or_session.rollback()
    except Exception:
        pass

    ordered = [t for t in _CLEANUP_FK_ORDER if t in norm]
    ordered += [t for t in norm if t not in _CLEANUP_FK_ORDER]

    try:
        if is_psycopg2:
            cur = conn_or_session.cursor()
            if tenant is not None:
                cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
            for tbl in ordered:                 # SCHRITT 2: reverse-FK-DELETE der uebergebenen IDs
                ids = norm[tbl]
                if not ids:
                    continue
                cur.execute(f"DELETE FROM {tbl} WHERE id = ANY(%s)", (list(ids),))
        else:
            if tenant is not None:
                conn_or_session.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
                )
            for tbl in ordered:
                ids = norm[tbl]
                if not ids:
                    continue
                conn_or_session.execute(
                    text(f"DELETE FROM {tbl} WHERE id = ANY(:ids)"), {"ids": list(ids)}
                )
        conn_or_session.commit()                # SCHRITT 3
    except Exception as e:
        try:
            conn_or_session.rollback()
        except Exception:
            pass
        # #5: kaputter Teardown LAUT machen (Attribution), nicht still verschlucken.
        msg = f"[PGTEST-CLEANUP] cleanup_rows FEHLGESCHLAGEN fuer spec={norm} tenant={tenant}: {e!r}"
        try:
            import logging
            logging.getLogger(__name__).warning(msg)
        except Exception:
            print(msg, file=sys.stderr)


@pytest.fixture
def sample_state():
    """Factory returning a fresh state dict with all Phase 04.8 keys at defaults."""
    def _make(**overrides):
        base = {
            "current_phase": 1,
            "current_phase_name": "Opener",
            "phase_confidence": 0.0,
            "phase_changed_at": None,
            "phase_change_count": 0,
            "readiness_score": 30,
            "readiness_bucket": "cold",
            "score_factors_seen": {},
            "active_hint": None,
            "ewb_buttons": None,
            "cold_call_inference": None,
        }
        base.update(overrides)
        return base
    return _make


@pytest.fixture
def db_session(monkeypatch):
    """Generische Session gegen REAL-PG nerve_test (Phase 08.23.2.PGTEST, kein sqlite-Fallback).

    Bindet das MODUL-`database.db.SessionLocal` via `configure(bind=engine)` an die nerve_test-Engine um
    (NICHT eine frische sessionmaker — die truege den after_begin-RLS-Hook nicht, db.py:87), seedet einen
    Test-Mandanten (Trigger-Muster) und ruft set_current_tenant(TEST_TENANT_UUID) (D-05), damit crm.*-Reads
    nicht RLS-fail-closed 0 Zeilen liefern. configure(bind=engine) BEWAHRT einen import-registrierten Hook,
    ERZEUGT aber keinen — ist DATABASE_URL beim Import sqlite, schlaegt der A-1-Tripwire (test_rls_generic_smoke)
    loud-red an. #2: dieser per-Test-`configure(bind=None)`+`engine.dispose()`-Zyklus ist der Grund, warum der
    Baseline-Waechter (Task 6) eine EIGENE session-scoped Read-Engine nutzt — er liest NICHT ueber diese
    pro Test disposed MODUL-SessionLocal.
    """
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set -- generic fixtures require real-PG nerve_test "
                    "(no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.")
    import database.db as dbmod
    from database.db import set_current_tenant, clear_current_tenant
    engine = create_engine(dsn)
    monkeypatch.setattr(dbmod, "engine", engine)
    dbmod.SessionLocal.configure(bind=engine)   # behaelt den auf SessionLocal registrierten after_begin-Hook
    tenant_uuid = _seed_test_tenant(engine)     # Trigger-Muster, gibt tenant_orgs.id zurueck
    set_current_tenant(tenant_uuid)             # D-05: GUC fuer crm.* reads
    session = dbmod.SessionLocal()              # MODUL-SessionLocal -> Hook feuert auf BEGIN
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        clear_current_tenant()
        dbmod.SessionLocal.configure(bind=None)  # Binding-Reset (Gemini-MEDIUM): keine tote Engine-Bindung
        engine.dispose()


@pytest.fixture
def client(monkeypatch):
    """Flask test client gegen REAL-PG nerve_test (Phase 08.23.2.PGTEST, kein sqlite-Fallback).

    Bindet das MODUL-`database.db.SessionLocal` via `configure(bind=engine)` um (EXAKT wie db_session,
    KEINE frische sessionmaker, KEIN monkeypatch von SessionLocal auf ein neues Objekt — sonst geht der
    after_begin-RLS-Hook verloren, Gemini-HIGH), monkeypatcht NUR `dbmod.engine`, ruft set_current_tenant.
    Re-exponiert den `_test_session`/`_test_engine`-Vertrag (MODUL-SessionLocal-PG-Session, hook-tragend),
    von dem db_from_client + ~20 Konsumenten-Tests abhaengen (T-PGTEST-22).
    """
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set -- client fixture requires real-PG nerve_test "
                    "(no SQLite fallback by design, Req-2/D-07).")
    import database.db as dbmod
    from database.db import set_current_tenant, clear_current_tenant
    engine = create_engine(dsn)
    monkeypatch.setattr(dbmod, "engine", engine)   # NUR engine monkeypatchen
    dbmod.SessionLocal.configure(bind=engine)      # MODUL-SessionLocal umbinden (Hook bleibt)
    tenant_uuid = _seed_test_tenant(engine)
    set_current_tenant(tenant_uuid)                # D-05, VOR dem app-Import-Pfad
    from app import app as flask_app               # erst NACH der Umbindung importieren
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    c = None
    try:
        with flask_app.test_client() as c:
            # VERTRAG re-exponieren (pre-execute blocker fix): db_from_client + ~20 Tests lesen diese Attribute.
            # MUSS die MODUL-SessionLocal-Session sein (hook-tragend, PG-gebunden), NICHT eine frische sessionmaker.
            c._test_session = dbmod.SessionLocal()   # MODUL-SessionLocal -> PG-gebunden + hook-tragend
            c._test_engine = engine                  # die nerve_test-PG-Engine
            yield c
    finally:
        try:
            if c is not None:
                c._test_session.close()              # best-effort, analog IST-client
        except Exception:
            pass
        clear_current_tenant()
        dbmod.SessionLocal.configure(bind=None)    # Binding-Reset (Gemini-MEDIUM)
        engine.dispose()


@pytest.fixture
def db_from_client(client):
    """Alias: returns the test session bound to the same engine as client."""
    return client._test_session


# ── Phase 08.23.2.G-MEET Wave 2 — real-PG nerve_app connection (RLS isolation test, D-12.2) ──
# The RLS isolation test (tests/test_rls_isolation.py) MUST run against REAL Postgres as the
# RLS-constrained `nerve_app` role -- SQLite has no Row-Level-Security (a SQLite branch would be a
# FALSE-GREEN). This fixture provides a raw psycopg2 connection as nerve_app to the disposable
# `nerve_test` DB (Req-5: never touches Production `nerve`), reading its DSN from env. It is ONLY
# available server-side in the deploy.sh-Gate (where the DSN env var is set on the dedicated
# nerve_test DB). When the DSN is absent (e.g. local, no real PG) the dependent tests SKIP --
# they NEVER fall back to SQLite.
#
# Expected env var (server-side, set by the deploy.sh-Gate / Plan 02):
#   NERVE_APP_TEST_DSN  -- e.g. postgresql://nerve_app@/nerve_test
# (nerve_app uses peer/socket auth; the DSN is read/write to the disposable nerve_test DB, NEVER Prod nerve.)
@pytest.fixture
def nerve_app_pg_conn():
    dsn = os.environ.get('NERVE_APP_TEST_DSN')
    if not dsn:
        pytest.skip(
            "NERVE_APP_TEST_DSN not set -- RLS isolation test requires a real-PG nerve_app "
            "connection to nerve_test (no SQLite fallback by design, D-12.2). Run server-side "
            "via the deploy.sh-Gate (DSN points to nerve_test, never Prod nerve)."
        )
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed -- RLS isolation test requires real Postgres.")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False  # explicit transactions: SET LOCAL must share the query's txn
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


# ── Phase 08.23.2.G-MEET Wave 3 — real-PG nerve_anon_worker engine (anonymizer RLS test, D-16) ──
# The anonymizer worker's RLS group (tests/test_anonymizer_worker.py) MUST run against REAL Postgres
# as the `nerve_anon_worker` role -- the only role the 0013 anon_worker_read / anon_worker_stamp
# policies target. SQLite has no RLS (a SQLite branch would be a FALSE-GREEN), so there is NO
# fallback: when the DSN is absent the dependent tests SKIP. This yields a SQLAlchemy Engine (not a
# raw connection) because the worker's process_unstamped() runs on a SQLAlchemy Connection -- the
# test exercises the SAME code path the production cron uses. The DSN points to the disposable
# `nerve_test` DB (Req-5: never touches Production `nerve`).
#
# Expected env var (server-side, set by the deploy.sh-Gate / Plan 02):
#   ANON_WORKER_TEST_DSN  -- e.g. postgresql://nerve_anon_worker:<pw>@127.0.0.1:5432/nerve_test  (scram
#                            path, PW from ionos-s3.env via the Gate; the worker role sets NO app.tenant_id,
#                            relies on the 0013 worker policies for cross-tenant access). NEVER Prod nerve.
@pytest.fixture
def anon_worker_pg_engine():
    dsn = os.environ.get('ANON_WORKER_TEST_DSN')
    if not dsn:
        pytest.skip(
            "ANON_WORKER_TEST_DSN not set -- anonymizer RLS test requires a real-PG nerve_anon_worker "
            "connection to nerve_test (no SQLite fallback by design, D-16). Run server-side via the "
            "deploy.sh-Gate (scram DSN @127.0.0.1:5432/nerve_test, never Prod nerve)."
        )
    engine = create_engine(dsn)
    try:
        yield engine
    finally:
        engine.dispose()


# ── Phase 08.23.2.SCHILD Wave 4 — read-only pg_description guard connection ──
# The Schild-Guard (tests/test_schild_guard.py) verifies that every table + non-trivial column in
# public/crm/training carries a Postgres COMMENT (>=10 chars) in pg_description. It MUST run against
# REAL Postgres -- SQLite has no schemas/COMMENTs (a SQLite branch would be a FALSE-GREEN,
# RESEARCH §1.3). pg_description is a world-readable catalog, so plain nerve_app suffices WITHOUT any
# GRANT (proven in Plan 01 / DISCOVERY-DECISIONS.md via a SET ROLE + obj_description ROLLBACK test:
# GUARD_ROLE=nerve_app). The DSN points to the disposable `nerve_test` DB (Req-5: never touches
# Production `nerve`). When the DSN is absent (local/SQLite) the guard SKIPS -- never falls back.
#
# Expected env var (server-side, set by the deploy.sh-Gate / Plan 02; name LOCKED in
# DISCOVERY-DECISIONS.md key `DSN_ENV_VAR:`):
#   NERVE_SCHILD_TEST_DSN  -- e.g. postgresql://nerve_app@/nerve_test (Unix socket / peer-auth).
#                            Read-only catalog use against nerve_test, NEVER Prod nerve.
@pytest.fixture
def schild_guard_pg_conn():
    dsn = os.environ.get('NERVE_SCHILD_TEST_DSN')
    if not dsn:
        pytest.skip(
            "NERVE_SCHILD_TEST_DSN not set -- Schild-Guard requires a real-PG connection to nerve_test "
            "that can read pg_description of public/crm/training (no SQLite fallback by design, "
            "RESEARCH §1.3). Run server-side via the deploy.sh-Gate (DSN points to nerve_test, never Prod nerve)."
        )
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed -- Schild-Guard requires real Postgres.")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True  # read-only catalog queries; no transaction needed
    try:
        yield conn
    finally:
        conn.close()
