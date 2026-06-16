import logging
import os
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests._schema_introspect import derive_baseline_tables, primary_key_column

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
    # Phase 08.23.2.PGTEST LEAK-FIX: org_id mit zurueckgeben, damit der db_session/client-Teardown die
    # committete Seed-Org (+ ihre Trigger-tenant_orgs-Row) wieder wegraeumen kann (sonst leakt jede
    # fixture-nutzende Test-Funktion 1 org + 1 tenant_org -> _baseline_cleanup_guard rot).
    return tenant_id, org_id


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

    # Loeschorder: Modul-Level-Cache _DERIVED_FK_ORDER (cross-schema, katalog-abgeleitet, Fund #8) hat
    # Vorrang. Ist der Cache leer (non-PG/SQLite-Skip-Pfad), faellt cleanup_rows auf den hardcoded
    # _CLEANUP_FK_ORDER zurueck (best-effort). KEINE Signatur-Aenderung, KEINE per-call DB-Query.
    # Der dynamische Cache liefert dieselbe crm-vor-public-Order wie _CLEANUP_FK_ORDER (beide enthalten
    # crm.accounts -> public.tenant_orgs als cross-schema FK-Kante).
    _fk_order = _DERIVED_FK_ORDER if _DERIVED_FK_ORDER else _CLEANUP_FK_ORDER
    ordered = [t for t in _fk_order if t in norm]
    ordered += [t for t in norm if t not in _fk_order]

    try:
        if is_psycopg2:
            cur = conn_or_session.cursor()
            if tenant is not None:
                cur.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
            for tbl in ordered:                 # SCHRITT 2: reverse-FK-DELETE der uebergebenen IDs
                ids = norm[tbl]
                if not ids:
                    continue
                # id::text-Vergleich (Phase 08.23.2.PGTEST): traegt int-PK (organisations/users/calls) UND
                # uuid-PK (tenant_orgs/crm.*) — sonst `operator does not exist: uuid = text` bei uuid-PK-Tabellen.
                cur.execute(f"DELETE FROM {tbl} WHERE id::text = ANY(%s)", ([str(x) for x in ids],))
        else:
            if tenant is not None:
                conn_or_session.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
                )
            for tbl in ordered:
                ids = norm[tbl]
                if not ids:
                    continue
                # id::text-Vergleich (Phase 08.23.2.PGTEST): traegt int-PK UND uuid-PK (tenant_orgs/crm.*).
                conn_or_session.execute(
                    text(f"DELETE FROM {tbl} WHERE id::text = ANY(:ids)"),
                    {"ids": [str(x) for x in ids]},
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
            logging.getLogger(__name__).warning(msg)
        except Exception:
            print(msg, file=sys.stderr)


def _leak_cleanup_seed_tenant(engine, org_id, tenant_org_pk):
    """Phase 08.23.2.PGTEST LEAK-FIX: raeumt die von _seed_test_tenant committete Seed-Org + ihre
    Trigger-tenant_orgs-Row wieder weg — aufzurufen im db_session/client-Teardown VOR engine.dispose().
    OHNE das leakt JEDE fixture-nutzende Test-Funktion genau 1 organisations- + 1 tenant_orgs-Row, was
    den autouse _baseline_cleanup_guard ueber die ganze Suite rot macht (Cascade). public.* -> kein
    Tenant-GUC noetig; cleanup_rows loescht reverse-FK (tenant_orgs VOR organisations, _CLEANUP_FK_ORDER).
    Best-effort: bei einem Cleanup-Fehler (z.B. ein Test liess FK-Kinder der Seed-Org liegen) emittiert
    cleanup_rows seine laute [PGTEST-CLEANUP]-Warnung — der echte Test-Body-Leak bleibt damit sichtbar."""
    sess = sessionmaker(bind=engine)()
    try:
        cleanup_rows(sess, {
            "public.tenant_orgs": [tenant_org_pk],
            "public.organisations": [org_id],
        })
    finally:
        sess.close()


# ── Phase 08.23.2.PGTEST.GREEN Plan 01 — Katalog-abgeleiteter Baseline-Waechter (PUBLIC.*-only, HYBRID) ──
# Ersetzt die hardcodierte _BASELINE_PUBLIC_TABLES-Liste durch Katalog-Ableitung aus pg_constraint
# (Req-9, D-G16/D-G17/D-G18). Der Waechter snapshottet / loescht NUR public.* (D-G04 erhalten,
# Fund #8). crm.* + training.transcript_archive bleiben UNVERAENDERT POST-SUITE-Check in deploy.sh
# (Plan 02, sudo -u postgres psql, peer-auth) — nerve_app saehe crm.* nur tenant-gefiltert.
#
# CROSS-SCHEMA-CACHE (Fund #8): der Modul-Level-Cache wird EINMAL bei Session-Start ueber ALLE drei
# Schemas (public+crm+training) gefuellt, damit cleanup_rows (das crm UND public raeumt) eine globale
# crm-vor-public-Loeschorder bekommt. Wuerde man den Cache nur mit schema='public' fuellen, fehlten
# crm-Tabellen im _DERIVED_FK_ORDER -> public wird zuerst geloescht -> crm.accounts->public.tenant_orgs
# FK-Violation -> jeder crm+public-raeumende Test crasht (Regression #3-Fold).
# Der Waechter-Snapshot (_snapshot_public_tables) filtert die table_list LOKAL auf startswith('public.').
#
# CACHE-FILL-GARANTIE (Fund #7): _baseline_snapshot fordert _baseline_schema als Fixture-PARAMETER
# (Dependency) an -> pytest baut _baseline_schema (und damit den Cross-Schema-Modul-Cache) auf, BEVOR
# _baseline_snapshot laeuft und BEVOR ein cleanup_rows-Fallback triggern kann. Ohne diese Dependency
# faellt cleanup_rows still auf _CLEANUP_FK_ORDER zurueck -> Req-9 wirkungslos (Meta-False-Green).

# Modul-Level-Globals (gesetzt von _baseline_schema-Fixture, EINMAL bei Session-Start).
# _DERIVED_FK_ORDER: globale cross-schema reverse-FK-Loeschorder (Kind-vor-Eltern).
#   crm.* VOR public.* (z.B. crm.accounts vor public.tenant_orgs — echte NERVE-Kante 2026-06-16).
# _DERIVED_PK_COLS: {qualified_table: pk_col_name} NUR fuer single-PK-Tabellen (auto-delete-faehig).
#   composite-PK + no-PK Tabellen sind NICHT enthalten (sie liegen im foundation_register, Fund #6/#9).
_DERIVED_FK_ORDER = []  # Wird von _baseline_schema gefuellt (cross-schema, sessions-scoped)
_DERIVED_PK_COLS = {}   # Wird von _baseline_schema gefuellt ({qualified_tbl: pk_col_name})


def _snapshot_public_tables(read_engine, public_table_list=None):
    """Lies pro relevanter PUBLIC Tabelle ein {pk: xmin_text}-Mapping (#7 per-Row-Change-Token) ueber die
    EIGENE session-scoped Read-Engine (#2 — NICHT die per-Test umgebundene MODUL-SessionLocal, sonst
    UnboundExecutionError im zuletzt-laufenden Waechter-Teardown). Tabellen, die (noch) nicht existieren,
    werden best-effort uebersprungen. Liefert {'schema.table': {pk: xmin_text}}.

    Phase 08.23.2.PGTEST.GREEN Plan 01 (Req-9/D-G17/Fund #8):
    public_table_list: KATALOG-ABGELEITETE Liste der schema-qualifizierten public-Tabellen aus
    _baseline_schema. Falls None (Legacy/Skip-Pfad), nutzt den Modul-Cache oder leere Menge.

    WAECHTER PUBLIC-ONLY (Fund #8, D-G04 erhalten): diese Funktion iteriert NUR public.* Eintraege,
    selbst wenn public_table_list cross-schema Eintraege enthaelt — gefiltert via startswith('public.').
    crm.*/training.* werden NICHT snapshot-ueberwacht (nerve_app saehe crm.* nur tenant-gefiltert).

    PK-Spalte: aus _DERIVED_PK_COLS (katalog-abgeleitet). Fallback 'id' nur bei leerem Cache.
    Composite-PK-Tabellen sind NICHT in _DERIVED_PK_COLS und daher NICHT snapshot-ueberwacht —
    das ist eine bekannte, offen im foundation_register dokumentierte Tor-Luecke (Fund #9, heute leer).
    """
    snap = {}
    # public_table_list ist die cross-schema list (crm+public+training), lokal auf public gefiltert
    if public_table_list is not None:
        watch_list = [t for t in public_table_list if t.startswith('public.')]
    else:
        # Legacy/Skip-Pfad: kein Cache verfuegbar -> leere Baseline (kein Watch)
        watch_list = []

    for qualified_tbl in watch_list:
        # PK-Spalte aus Katalog-abgeleitetem Cache, Fallback 'id' bei leerem Cache
        pk_col = _DERIVED_PK_COLS.get(qualified_tbl, 'id')
        try:
            with read_engine.connect() as conn:
                rows = conn.execute(
                    text(f"SELECT {pk_col}, xmin::text FROM {qualified_tbl}")
                ).fetchall()
            snap[qualified_tbl] = {r[0]: r[1] for r in rows}
        except Exception:
            # Tabelle existiert nicht / kein id-PK -> nicht Teil der Baseline-Pruefung.
            continue
    return snap


def _diff_baseline(current, baseline):
    """Vergleichs-Kern (DSN-frei testbar): liefert {tabelle: {'leaked':set,'missing':set,'mutated':set}}
    fuer jede Tabelle mit Drift, sonst {}. leaked = extra-PKs (committed+nicht-aufgeraeumt), missing =
    geloeschte Baseline-PKs, mutated = gleiche PK aber geaendertes xmin (#7 — committetes UPDATE)."""
    drift = {}
    for tbl, base_map in baseline.items():
        cur_map = current.get(tbl, {})
        cur_pks = set(cur_map)
        base_pks = set(base_map)
        leaked = cur_pks - base_pks
        missing = base_pks - cur_pks
        mutated = {pk for pk in (cur_pks & base_pks) if cur_map[pk] != base_map[pk]}
        if leaked or missing or mutated:
            drift[tbl] = {"leaked": leaked, "missing": missing, "mutated": mutated}
    return drift


@pytest.fixture(scope="session")
def _baseline_guard_engine():
    """EIGENE session-scoped Read-Engine (#2, Gemini-3.1-Pro-Fold): `create_engine(TEST_DATABASE_URL)`,
    EINMAL bei Session-Start erstellt, am Session-ENDE disposed. ENTKOPPELT von der per-Test umgebundenen
    MODUL-SessionLocal (db_session/client machen pro Test configure(bind=None)+engine.dispose() im finally;
    der Waechter-Teardown laeuft ZULETZT -> ueber die MODUL-SessionLocal zu lesen waere UnboundExecutionError).
    nerve_app-peer-socket, public.*-only (kein RLS auf public), KEINE Superuser/BYPASSRLS-Rolle."""
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        yield None
        return
    engine = create_engine(dsn)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def _baseline_schema(_baseline_guard_engine):
    """Session-scoped Katalog-Ableitung: fuellt EINMAL die Modul-Level-Globals
    _DERIVED_FK_ORDER und _DERIVED_PK_COLS aus pg_constraint (CROSS-SCHEMA, Fund #8).

    CROSS-SCHEMA-CACHE (Fund #8): ruft derive_baseline_tables ueber ALLE drei Schemas
    ('public','crm','training'). Damit enthaelt _DERIVED_FK_ORDER cross-schema Kanten
    (z.B. crm.accounts -> public.tenant_orgs) und liefert crm-Kinder VOR public-Eltern —
    exakt wie der hardcodierte _CLEANUP_FK_ORDER (cleanup_rows crm vor public fuer D-G04-crm-Writer).

    CACHE-FILL-GARANTIE (Gemini-Re-Review R2 / Fund #7): diese Fixture wird als Dependency
    von _baseline_snapshot angefordert -> der Cache ist garantiert gefuellt, BEVOR der erste
    cleanup_rows-Fallback triggern kann. Ohne diese explizite Dependency wuerde cleanup_rows
    still auf _CLEANUP_FK_ORDER zurueckfallen -> Req-9 wirkungslos (Meta-False-Green).

    Liefert die public-gefilterte table_list (fuer _snapshot_public_tables).
    """
    global _DERIVED_FK_ORDER, _DERIVED_PK_COLS
    if _baseline_guard_engine is None:
        yield None
        return

    try:
        with _baseline_guard_engine.connect() as conn:
            table_list, fk_order, foundation_register = derive_baseline_tables(
                conn,
                schemas=('public', 'crm', 'training'),  # CROSS-SCHEMA (Fund #8)
            )

        # Modul-Level-Cache fuellen (einmal, CROSS-SCHEMA)
        _DERIVED_FK_ORDER = fk_order
        # PK-Cols: nur single-PK-Tabellen aus derive_baseline_tables (Ergebnis ist baseline_table_list)
        # Wir brauchen die PK-Cols pro Tabelle. derive_baseline_tables liefert nur die Liste,
        # nicht das pk_cols dict direkt. Wir rekonstruieren sie aus einer zweiten Pass:
        pk_cols_built = {}
        with _baseline_guard_engine.connect() as conn:
            for qualified_tbl in table_list:
                parts = qualified_tbl.split('.', 1)
                if len(parts) == 2:
                    schema_name, table_name = parts
                    from tests._schema_introspect import _fetch_pk_for_table
                    pk_col, pk_count = _fetch_pk_for_table(conn, schema_name, table_name)
                    if pk_count == 1 and pk_col:
                        pk_cols_built[qualified_tbl] = pk_col
        _DERIVED_PK_COLS = pk_cols_built

        # DIAGNOSE (Logging-First, Phase 08.23.2.PGTEST.GREEN Bug-2): warum sieht der TEST den
        # Modul-Cache leer, obwohl diese Fixture ihn fuellt? Drei Verdaechtige, alle hier belegbar:
        #  (a) DUAL-MODULE: pytest hat conftest sowohl als 'conftest' ALS auch 'tests.conftest'
        #      geladen -> global-Rebind landet in EINEM, der Test liest den ANDEREN (-> leer).
        #      Beleg: __name__ dieser Fixture + ob beide sys.modules-Eintraege existieren + ihre id().
        #  (b) EMPTY-DERIVE: derive_baseline_tables lieferte leere Listen (-> len==0).
        #  (c) PK-PASS-FAIL: table_list ok, aber zweiter Pass baute kein pk_cols (-> pk len==0).
        import sys as _sys
        _self_mod = _sys.modules.get(__name__)
        _alias_conftest = _sys.modules.get('conftest')
        _alias_tests_conftest = _sys.modules.get('tests.conftest')
        _diaglog = logging.getLogger(__name__)
        _diaglog.warning(
            "[PGTEST-INTROSPECT] _baseline_schema FILL: module __name__=%s id(self)=%s | "
            "sys.modules['conftest']=%s sys.modules['tests.conftest']=%s | "
            "DUAL_MODULE=%s | len(table_list)=%d len(fk_order)=%d len(pk_cols)=%d",
            __name__, id(_self_mod),
            id(_alias_conftest) if _alias_conftest is not None else None,
            id(_alias_tests_conftest) if _alias_tests_conftest is not None else None,
            (_alias_conftest is not None and _alias_tests_conftest is not None
             and _alias_conftest is not _alias_tests_conftest),
            len(table_list), len(fk_order), len(pk_cols_built),
        )

        # foundation_register loggen (Transparenz, Req-7)
        if foundation_register:
            _log = logging.getLogger(__name__)
            _log.info(
                "[PGTEST-INTROSPECT] Foundation-Register (exkludierte Tabellen): %s",
                list(foundation_register.keys()),
            )

        yield table_list  # public-gefiltert wird in _baseline_snapshot gemacht

    except Exception as e:
        _log = logging.getLogger(__name__)
        _log.warning(
            "[PGTEST-INTROSPECT] _baseline_schema: derive_baseline_tables fehlgeschlagen (%r) "
            "-> Modul-Cache bleibt leer, cleanup_rows faellt auf _CLEANUP_FK_ORDER zurueck (best-effort).",
            e,
        )
        yield None


@pytest.fixture(scope="session")
def _baseline_snapshot(_pgtest_base_seed, _baseline_guard_engine, _baseline_schema):
    """Session-Start-Snapshot der PUBLIC.*-Baseline ({pk: xmin}, #7). Haengt am Base-Seed (Task 4) -> laeuft
    danach. #9 (Delta-Review-6, BLOCKER): fuehrt als ALLERERSTE Aktion `from app import app` aus, BEVOR der
    {pk:xmin}-Snapshot laeuft -> erzwingt die Modul-Top-Level-Seeder (_seed_prompt_versions/_seed_ewb_v2/
    _seed_founder_dashboard_defaults) gegen nerve_test, sodass prompt_versions/api_rates/fixed_costs in der
    Baseline enthalten sind (kein First-Test-False-Red durch leere Baseline). A-1: die MODUL-Engine ist beim
    Import schon nerve_test-PG (DATABASE_URL=postgres) -> der fruehe Import seedet gegen die korrekte DB; der
    spaetere client-Rebind ist unberuehrt; sys.modules-cached -> idempotent. Reihenfolge: Base-Seed commit ->
    `import app` (Seeder feuern) -> {pk:xmin}-Snapshot ueber die eigene Read-Engine (#2).

    Phase 08.23.2.PGTEST.GREEN Plan 01: nimmt jetzt _baseline_schema als Dependency (Fund #7 Cache-Fill-Garantie).
    _baseline_schema hat den Modul-Cache (_DERIVED_FK_ORDER / _DERIVED_PK_COLS) bereits gefuellt, BEVOR
    dieser Snapshot laeuft. _baseline_schema liefert die katalog-abgeleitete public table_list."""
    if _baseline_guard_engine is None:
        yield None
        return
    # #9: app-Import ERZWINGT die Modul-Top-Level-Seeder VOR dem Snapshot.
    from app import app as _flask_app  # noqa: F401
    # _baseline_schema liefert die katalog-abgeleitete table_list (cross-schema, aber gefiltert in snapshot)
    baseline = _snapshot_public_tables(_baseline_guard_engine, public_table_list=_baseline_schema)
    yield baseline


@pytest.fixture(autouse=True)
def _baseline_cleanup_guard(request, _baseline_snapshot, _baseline_guard_engine):
    """Autouse Baseline-Cleanup-Waechter (Phase 08.23.2.PGTEST.GREEN Plan 01, PUBLIC.*-only, AUTO-RESET).

    SPLIT (D-G01/D-G02): Drift in 3 Kategorien:
    - leaked (Extra-Rows): AUTO-DELETE mit lauter [BASELINE-AUTO-FIX]-Warnung (D-G03). KEIN pytest.fail.
      Loeschorder aus _DERIVED_FK_ORDER (cross-schema Katalog, Kind-vor-Eltern). PK-Spalte aus
      _DERIVED_PK_COLS (katalog-abgeleitet, kein hardcoded 'id', Fund #2). uuid-Cast bleibt ({pk_col}::text).
    - missing/mutated (Baseline-Verletzung): SOFORT pytest.fail mit nodeid (D-G02 hard-block).
      KEIN Re-Insert (Re-Insert wuerde trg_mk_tenant_org feuern -> neue UUID -> Folge-Tests kaputt).

    AUTO-DELETE-TX-HYGIENE (D-G05): DELETE laeuft in with engine.begin() as conn (commit-on-exit),
    damit geloeschte Rows fuer den NAECHSTEN Test wirklich weg sind (kein uncommittetes Delete).

    SCOPE (D-G04): Waechter snapshottet/loescht NUR public.* (table_list lokal public-gefiltert, Fund #8).
    crm.* UNVERAENDERT POST-SUITE-Check in deploy.sh (Plan 02). _DERIVED_FK_ORDER enthaelt zwar cross-schema
    Kanten (crm vor public), aber der Waechter-DELETE nutzt sie nur fuer public.*-Eintraege.

    COMPOSITE-PK-TABELLEN (Fund #6/#9): kommen hier NICHT vor — sie sind nicht in der baseline_table_list
    / nicht in _DERIVED_PK_COLS. Sie werden weder auto-geloescht noch snapshot-ueberwacht. Bekannte,
    offen dokumentierte Tor-Luecke, heute leer (0 composite-PK-Tabellen, Prod-Katalog 2026-06-16).

    Frueh angefordert (autouse + Dependency auf _baseline_snapshot) -> Teardown laeuft ZULETZT,
    NACH dem Test-eigenen cleanup_rows-Teardown (sonst saehe er noch un-aufgeraeumte Rows -> False-Positive).
    crm.*/training.* werden NICHT hier geprueft — POST-SUITE in deploy.sh (Plan 02, sudo -u postgres psql).
    """
    yield
    if _baseline_snapshot is None or _baseline_guard_engine is None:
        return
    current = _snapshot_public_tables(_baseline_guard_engine, public_table_list=list(_baseline_snapshot.keys()))
    drift = _diff_baseline(current, _baseline_snapshot)
    if not drift:
        return

    _log = logging.getLogger(__name__)

    # Trenne leaked von missing/mutated (D-G01/D-G02 STRICT SPLIT)
    leaked_by_tbl = {}
    hard_fail_parts = []

    for tbl, d in drift.items():
        if d['leaked']:
            leaked_by_tbl[tbl] = d['leaked']
        if d['missing'] or d['mutated']:
            hard_fail_parts.append(
                f"{tbl}: missing={sorted(d['missing'])}, mutated={sorted(d['mutated'])}"
            )

    # 1. Zuerst: missing/mutated -> harter pytest.fail (D-G02, STRICT SPLIT)
    if hard_fail_parts:
        pytest.fail(
            f"[BASELINE-GUARD] {request.node.nodeid}: protected baseline drifted "
            f"(missing/mutated) -> " + " | ".join(hard_fail_parts)
        )

    # 2. Dann: leaked -> Auto-Delete mit lauter Warnung (D-G01/D-G03)
    if leaked_by_tbl:
        # Loeschorder aus _DERIVED_FK_ORDER (cross-schema, Kind-vor-Eltern, Fund #8).
        # Nur public.*-Eintraege aus dem Waechter-Snapshot loeschen (D-G04 public-only).
        if _DERIVED_FK_ORDER:
            delete_order = [t for t in _DERIVED_FK_ORDER if t in leaked_by_tbl]
            delete_order += [t for t in leaked_by_tbl if t not in _DERIVED_FK_ORDER]
        else:
            # Fallback: _CLEANUP_FK_ORDER (best-effort, bleibt erhalten)
            delete_order = [t for t in _CLEANUP_FK_ORDER if t in leaked_by_tbl]
            delete_order += [t for t in leaked_by_tbl if t not in _CLEANUP_FK_ORDER]

        # Laut warnen (D-G03: jedes Auto-Delete emittiert Warnung mit nodeid + Tabelle + PKs)
        for tbl in delete_order:
            ids = leaked_by_tbl[tbl]
            _log.warning(
                "[BASELINE-AUTO-FIX] %s leaked rows in %s: %s",
                request.node.nodeid, tbl, sorted(ids),
            )

        # Auto-Delete in engine.begin() (D-G05: TX-Hygiene, commit-on-exit)
        try:
            with _baseline_guard_engine.begin() as conn:
                for tbl in delete_order:
                    ids = leaked_by_tbl[tbl]
                    if not ids:
                        continue
                    # PK-Spalte aus Katalog-abgeleitetem Cache (Fund #2: kein hardcoded 'id')
                    pk_col = _DERIVED_PK_COLS.get(tbl, 'id')
                    # {pk_col}::text = ANY(:ids) — uuid-Cast bleibt (D-G06, 10e5d0a-Fix)
                    conn.execute(
                        text(f"DELETE FROM {tbl} WHERE {pk_col}::text = ANY(:ids)"),
                        {"ids": [str(x) for x in ids]},
                    )
        except Exception as e:
            _log.warning(
                "[BASELINE-AUTO-FIX] Auto-Delete fehlgeschlagen fuer %s: %r "
                "(Folge-Tests koennen beeintraechtigt sein)",
                request.node.nodeid, e,
            )


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
    tenant_uuid, seed_org_id = _seed_test_tenant(engine)  # Trigger-Muster; tenant_orgs.id + organisations.id
    set_current_tenant(tenant_uuid)             # D-05: GUC fuer crm.* reads
    session = dbmod.SessionLocal()              # MODUL-SessionLocal -> Hook feuert auf BEGIN
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        clear_current_tenant()
        # Phase 08.23.2.PGTEST LEAK-FIX: Seed-Org + Trigger-tenant_org wegraeumen (tenant_uuid == tenant_orgs.id),
        # VOR configure(bind=None)/dispose() solange die Engine noch lebt. Sonst leakt jede db_session-Nutzung.
        _leak_cleanup_seed_tenant(engine, seed_org_id, tenant_uuid)
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
    tenant_uuid, seed_org_id = _seed_test_tenant(engine)
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
        # Phase 08.23.2.PGTEST LEAK-FIX: Seed-Org + Trigger-tenant_org wegraeumen (tenant_uuid == tenant_orgs.id),
        # VOR configure(bind=None)/dispose(). Sonst leakt jede client/db_from_client-Nutzung 1 org + 1 tenant_org.
        _leak_cleanup_seed_tenant(engine, seed_org_id, tenant_uuid)
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
