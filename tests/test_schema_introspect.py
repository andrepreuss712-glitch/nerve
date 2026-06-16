"""tests/test_schema_introspect.py — behavior-Tests fuer tests/_schema_introspect.py.

8 Behavior-Tests:
  Tests 1-3, 7, 8: DSN-frei (injizierte Kanten/pk_cols-Listen)
  Tests 4-6: gegen real-PG (Skip-when-env-missing, NERVE_APP_TEST_DSN)

Verify = deploy.sh production Gate-Lauf (HART: kein lokaler pytest, kein Local-Dev).
ASCII-Identifier (CLAUDE.md).
"""
import logging
import os
import pytest

# Imports aus dem zu testenden Modul
from tests._schema_introspect import (
    _kahn_topo_sort,
    derive_baseline_tables,
    primary_key_column,
    _schema_qualified,
)


# ── Hilfsfunktionen fuer DSN-freie Tests ──────────────────────────────────────────────────────


class _MockConn:
    """Minimaler Mock fuer eine DB-Connection, der injizierte Daten zurueckgibt.
    Unterstuetzt _is_psycopg2_conn-Check (hat .cursor() fuer psycopg2-Erkennung).
    """
    def __init__(self, tables_by_schema=None, fk_edges=None, pk_map=None):
        """
        tables_by_schema: {schema: [table_name, ...]}
        fk_edges: [(child_qualified, parent_qualified, confdeltype), ...]
        pk_map: {qualified_table: pk_col_name_or_list}
            - str -> single PK
            - list -> composite PK (pk_count = len(list))
            - None -> kein PK
        """
        self._tables_by_schema = tables_by_schema or {}
        self._fk_edges = fk_edges or []
        self._pk_map = pk_map or {}

    def cursor(self):
        return _MockCursor(self)

    # Kein .execute() -> _is_psycopg2_conn gibt True zurueck


class _MockCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []

    def execute(self, query, params=None):
        # Tabellen-Query: relkind='r'
        if "relkind = 'r'" in query:
            rows = []
            for schema, tables in self._conn._tables_by_schema.items():
                for tbl in tables:
                    rows.append((schema, tbl))
            self._rows = rows
        # FK-Kanten-Query
        elif "contype = 'f'" in query:
            self._rows = list(self._conn._fk_edges)
        # PK-Spalten-Query fuer eine spezifische Tabelle
        elif "indisprimary" in query:
            # params[0] ist z.B. 'public.calls' -> wir suchen in pk_map
            tbl_arg = params[0] if params else None
            if tbl_arg and tbl_arg in self._conn._pk_map:
                pk_val = self._conn._pk_map[tbl_arg]
                if pk_val is None:
                    self._rows = []
                elif isinstance(pk_val, list):
                    self._rows = [(col,) for col in pk_val]
                else:
                    self._rows = [(pk_val,)]
            else:
                # Default: 'id' als PK
                self._rows = [('id',)]

    def fetchall(self):
        return self._rows

    def close(self):
        pass


# ── Test 1: DSN-frei, topo-Sort kuenstlicher FK-Kanten ────────────────────────────────────────

def test_01_topo_sort_basic():
    """Test 1 (DSN-frei): topo-Sort einer kuenstlichen FK-Kanten-Liste
    {users->organisations, profiles->users} liefert reverse-FK-Order = Kinder vor Eltern.
    profiles -> users -> organisations (Kind vor Eltern).
    """
    nodes = {'public.users', 'public.organisations', 'public.profiles'}
    edges = [
        ('public.users', 'public.organisations'),
        ('public.profiles', 'public.users'),
    ]
    result = _kahn_topo_sort(nodes, edges)

    assert 'public.profiles' in result
    assert 'public.users' in result
    assert 'public.organisations' in result

    # profiles vor users (profiles -> users FK)
    idx_profiles = result.index('public.profiles')
    idx_users = result.index('public.users')
    idx_orgs = result.index('public.organisations')

    assert idx_profiles < idx_users, (
        f"profiles ({idx_profiles}) sollte vor users ({idx_users}) kommen (Kind vor Eltern)"
    )
    assert idx_users < idx_orgs, (
        f"users ({idx_users}) sollte vor organisations ({idx_orgs}) kommen (Kind vor Eltern)"
    )


# ── Test 2: Zyklus (self-ref) haengt nicht ────────────────────────────────────────────────────

def test_02_self_ref_cycle_no_hang():
    """Test 2 (Zyklus, Bau-Wachpunkt 1): self-ref Kante {accounts->accounts} haengt NICHT —
    die Kante wird ignoriert/gebrochen, accounts erscheint genau einmal in der Order.
    """
    nodes = {'public.accounts', 'public.users'}
    edges = [
        ('public.accounts', 'public.accounts'),  # self-ref
        ('public.accounts', 'public.users'),
    ]
    result = _kahn_topo_sort(nodes, edges)

    # accounts genau einmal
    assert result.count('public.accounts') == 1, "accounts sollte genau einmal in der Order sein"
    assert result.count('public.users') == 1
    # accounts vor users (accounts -> users FK)
    assert result.index('public.accounts') < result.index('public.users')


# ── Test 3: CASCADE-Kante BLEIBT im Sort ─────────────────────────────────────────────────────

def test_03_cascade_edge_stays_in_sort():
    """Test 3 (CASCADE-Kante BLEIBT im Sort, Gemini-Fund #1):
    Eine Kette mit einer CASCADE-Kante (confdeltype='c', z.B. intent_event->calls) UND einer
    RESTRICT-Kante darunter (calls->organisations) -> die CASCADE-Kante wird NICHT uebersprungen.
    Assertion: intent_event VOR calls VOR organisations in der reverse-FK-Order.
    Beweist: Leaves-vor-Roots haelt auch ueber eine CASCADE->RESTRICT-Kette -> kein DoS.
    """
    # Alle 3 Kanten (intent_event->calls CASCADE, calls->organisations RESTRICT, plus intent_event direkt)
    # Dieser Test prueft den topo-Sort-Kernel direkt mit cascade-inklusiven Kanten.
    nodes = {
        'public.intent_event',
        'public.calls',
        'public.organisations',
    }
    # intent_event -> calls (CASCADE, confdeltype='c') MUSS in den Sort
    # calls -> organisations (RESTRICT, confdeltype='a')
    edges_with_cascade = [
        ('public.intent_event', 'public.calls', 'c'),   # CASCADE
        ('public.calls', 'public.organisations', 'a'),  # RESTRICT
    ]
    # _kahn_topo_sort nimmt nur (child, parent) — confdeltype wird ignoriert (nur fuer Diagnose)
    edges_2col = [(e[0], e[1]) for e in edges_with_cascade]
    result = _kahn_topo_sort(nodes, edges_2col)

    idx_intent = result.index('public.intent_event')
    idx_calls = result.index('public.calls')
    idx_orgs = result.index('public.organisations')

    assert idx_intent < idx_calls, (
        f"intent_event ({idx_intent}) sollte vor calls ({idx_calls}) kommen (CASCADE-Kind vor Eltern)"
    )
    assert idx_calls < idx_orgs, (
        f"calls ({idx_calls}) sollte vor organisations ({idx_orgs}) kommen (RESTRICT-Kind vor Eltern)"
    )
    # intent_event ist in der result-Liste (nicht still weggelassen)
    assert 'public.intent_event' in result, "CASCADE-Kind intent_event sollte in der Order sein"


# ── Test 4-6: gegen real-PG (NERVE_APP_TEST_DSN) ─────────────────────────────────────────────

@pytest.fixture
def _pg_dsn():
    """Skip wenn NERVE_APP_TEST_DSN nicht gesetzt (kein Local-Dev, CLAUDE.md HART)."""
    dsn = os.environ.get('NERVE_APP_TEST_DSN')
    if not dsn:
        pytest.skip(
            "NERVE_APP_TEST_DSN not set -- schema_introspect real-PG tests require "
            "a real-PG nerve_test connection (no SQLite fallback, D-07). "
            "Run server-side via deploy.sh gate (scripts/triage.sh)."
        )
    return dsn


def test_04_denylist_foundation_register(_pg_dsn):
    """Test 4 (Denylist/Foundation-Register, D-G17): alembic_version ist NICHT in der
    baseline_table_list; Views/Matviews (relkind != 'r') sind nicht drin;
    eine Tabelle ohne bewachbaren PK landet mit Grund in der Denylist (geloggt), nicht still gedroppt.
    """
    table_list, fk_order, register = derive_baseline_tables(_pg_dsn, schemas=('public',))

    # alembic_version ist in der Denylist, nicht in der table_list
    assert 'public.alembic_version' not in table_list, (
        "alembic_version darf nicht in der baseline_table_list sein"
    )
    assert 'public.alembic_version' in register, (
        "alembic_version muss im foundation_register mit Begruendung stehen"
    )
    assert 'migration-state' in register['public.alembic_version']

    # Alle Eintraege sind schema-qualifiziert
    for tbl in table_list:
        assert '.' in tbl, f"Tabelle {tbl!r} ist nicht schema-qualifiziert"

    # Foundation-Register-Eintraege haben alle eine nicht-leere Begruendung
    for tbl, reason in register.items():
        assert reason, f"foundation_register[{tbl!r}] hat leere Begruendung"


def test_05_derived_list_contains_calls_and_objection_events(_pg_dsn):
    """Test 5 (Req-9-Beleg): die abgeleitete public-Liste enthaelt calls + objection_events
    (die in der alten _BASELINE_PUBLIC_TABLES fehlten).

    Echter Tabellenname ist 'objection_events' (Plural, models.py:407 __tablename__) —
    die fruehere Assertion auf Singular 'objection_event' war ein TEST-BUG (empirisch via
    deploy.sh-Gate gefangen: derive lieferte 'public.objection_events', Assertion suchte Singular).
    """
    table_list, _, _ = derive_baseline_tables(_pg_dsn, schemas=('public',))

    assert 'public.calls' in table_list, (
        "public.calls sollte in der abgeleiteten baseline_table_list sein (Req-9)"
    )
    assert 'public.objection_events' in table_list, (
        "public.objection_events sollte in der abgeleiteten baseline_table_list sein (Req-9)"
    )


def test_06_primary_key_column_non_id(_pg_dsn):
    """Test 6 (PK-from-catalog, D-G17 REFINEMENT, Gemini-Fund #2): primary_key_column liefert
    fuer eine non-id-PK-Tabelle den korrekten Spaltennamen.
    intent_event -> 'event_id' (nicht 'id'); eine id-PK-Tabelle liefert 'id'.
    Beweist: spaeteres Auto-Delete bekommt die richtige PK-Spalte (kein 'column id does not exist').
    """
    import psycopg2
    conn = psycopg2.connect(_pg_dsn)
    try:
        # id-PK-Tabelle: organisations hat PK 'id'
        pk_col, pk_count = primary_key_column(conn, 'organisations', schema='public')
        assert pk_count == 1, "organisations sollte einen single PK haben"
        assert pk_col == 'id', f"organisations PK sollte 'id' sein, war {pk_col!r}"

        # non-id-PK-Tabelle: intent_event hat PK 'event_id'
        pk_col_ie, pk_count_ie = primary_key_column(conn, 'intent_event', schema='public')
        assert pk_count_ie == 1, "intent_event sollte einen single PK haben"
        assert pk_col_ie == 'event_id', (
            f"intent_event PK sollte 'event_id' sein, war {pk_col_ie!r}"
        )
    finally:
        conn.close()


# ── Test 7: Composite-PK-Guard (DSN-frei, injizierter Fall) ──────────────────────────────────

def test_07_composite_pk_denylist(caplog):
    """Test 7 (Composite-PK-Guard, Gemini-Re-Review R2 / Fund #6 + R3 / Fund #9):
    Eine Tabelle mit zusammengesetztem PK (Katalog-Query liefert >1 indisprimary-Zeile,
    z.B. eine kuenstliche Join-Tabelle mit (a_id, b_id) als PK) landet NICHT in der
    auto-delete-faehigen baseline_table_list, sondern im foundation_register.

    Assertions:
    (a) die Tabelle ist im foundation_register mit genau dem ehrlichen Grund;
    (b) primary_key_column gibt fuer sie KEINE einzelne Spalte zurueck (None);
    (c) logging.warning wurde emittiert (caplog).

    HINWEIS: heute existiert keine composite-PK-Tabelle in NERVE (Prod-Katalog 2026-06-16 = 0)
    -> Test laeuft gegen einen INJIZIERTEN >1-pk_cols-Fall.
    EHRLICHKEIT (Fund #9): der Grund sagt EXPLIZIT, dass die Tabelle weder auto-deleted noch
    snapshot-ueberwacht wird. KEINE falsche "Snapshot-sichtbar"-Behauptung.
    """
    # Injizierte composite-PK-Tabelle: public.tag_assignments hat (a_id, b_id) als PK
    composite_tbl = 'public.tag_assignments'
    mock_conn = _MockConn(
        tables_by_schema={'public': ['organisations', 'tag_assignments']},
        fk_edges=[],
        pk_map={
            'public.organisations': 'id',            # single PK
            'public.tag_assignments': ['a_id', 'b_id'],  # composite PK -> liste
        },
    )

    with caplog.at_level(logging.WARNING, logger='tests._schema_introspect'):
        table_list, fk_order, register = derive_baseline_tables(mock_conn, schemas=('public',))

    # (a) Tabelle im foundation_register mit ehrlichem Grund (Fund #9)
    assert composite_tbl in register, (
        f"{composite_tbl} sollte im foundation_register sein"
    )
    expected_reason = "composite PK: not auto-delete-eligible AND not snapshot-monitored (known gate gap)"
    assert register[composite_tbl] == expected_reason, (
        f"foundation_register[{composite_tbl!r}] sollte genau den ehrlichen Grund haben: "
        f"{expected_reason!r}, war {register[composite_tbl]!r}"
    )

    # (b) Tabelle NICHT in der baseline_table_list (nicht auto-delete-faehig)
    assert composite_tbl not in table_list, (
        f"{composite_tbl} darf NICHT in der auto-delete-faehigen baseline_table_list sein"
    )

    # (c) logging.warning wurde emittiert
    assert any('Composite-PK' in r.message or 'composite PK' in r.message.lower()
               for r in caplog.records), (
        "logging.warning fuer Composite-PK-Tabelle sollte emittiert worden sein (Req-7)"
    )

    # Zusaetzlich: organisations ist in der baseline_table_list (single PK)
    assert 'public.organisations' in table_list


# ── Test 8: Cross-Schema-FK-Order (DSN-frei, injizierter Fall) ───────────────────────────────

def test_08_cross_schema_fk_order():
    """Test 8 (CROSS-SCHEMA-FK-Order, Gemini-Re-Review R3 / Fund #8):
    Bei Aufruf mit schemas=('public','crm','training') und einer FK-Kante
    crm.accounts -> public.tenant_orgs (cross-schema) steht in der reverse_fk_delete_order
    crm.accounts VOR public.tenant_orgs (crm-Kind vor public-Eltern).

    Assertion: beide Tabellen schema-qualifiziert UND Index-Position von crm.accounts <
    Index-Position von public.tenant_orgs.

    Beweist: cleanup_rows (crm+public) loescht crm zuerst -> keine FK-Violation (Fund #8).

    NERVE-Prod-Fakt (2026-06-16): crm.accounts -> public.tenant_orgs ist eine echte FK-Kante
    (bewiesen via psql gegen 178.104.82.166). Diese Kante muss cross-schema im Sort erfasst werden.
    """
    # Injizierte cross-schema Kante: crm.accounts -> public.tenant_orgs
    mock_conn = _MockConn(
        tables_by_schema={
            'public': ['tenant_orgs', 'organisations'],
            'crm': ['accounts', 'contacts'],
        },
        fk_edges=[
            ('crm.accounts', 'public.tenant_orgs', 'a'),   # cross-schema: crm.accounts -> public.tenant_orgs
            ('crm.contacts', 'crm.accounts', 'a'),          # crm-intern
        ],
        pk_map={
            'public.tenant_orgs': 'id',
            'public.organisations': 'id',
            'crm.accounts': 'id',
            'crm.contacts': 'id',
        },
    )

    table_list, fk_order, register = derive_baseline_tables(
        mock_conn, schemas=('public', 'crm', 'training')
    )

    # Beide Tabellen muessen in der fk_order sein
    assert 'crm.accounts' in fk_order, "crm.accounts sollte in der cross-schema fk_order sein"
    assert 'public.tenant_orgs' in fk_order, "public.tenant_orgs sollte in der fk_order sein"

    # crm.accounts VOR public.tenant_orgs (Kind vor Eltern, crm vor public)
    idx_crm_accounts = fk_order.index('crm.accounts')
    idx_pub_tenant_orgs = fk_order.index('public.tenant_orgs')

    assert idx_crm_accounts < idx_pub_tenant_orgs, (
        f"crm.accounts (Index {idx_crm_accounts}) sollte VOR public.tenant_orgs "
        f"(Index {idx_pub_tenant_orgs}) in der reverse_fk_delete_order stehen "
        f"(Fund #8: crm-Kinder vor public-Eltern, keine FK-Violation beim Cleanup). "
        f"Vollstaendige Order: {fk_order}"
    )

    # Beide schema-qualifiziert
    assert 'crm.accounts' in fk_order  # schema-qualifiziert mit 'crm.'
    assert 'public.tenant_orgs' in fk_order  # schema-qualifiziert mit 'public.'
