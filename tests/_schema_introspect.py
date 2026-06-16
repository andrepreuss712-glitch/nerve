"""tests/_schema_introspect.py — geteiltes Katalog-Ableitungsmodul (D-G18, Phase 08.23.2.PGTEST.GREEN).

Liefert aus EINER Wahrheit (pg_constraint topo-Sort, CROSS-SCHEMA) drei Dinge:
  baseline_table_list   -- alle auto-delete-faehigen base-Tabellen (Schema-qualifiziert, schema.table)
  reverse_fk_delete_order -- globale Cross-Schema-topo-Order Kind-vor-Eltern (crm-Kinder vor public-Eltern)
  foundation_register   -- dict {table: reason} jeder bewusst exkludierten Tabelle (D-G17, Req-7 — nie still)

ASCII-Identifier (CLAUDE.md), Deutsche Prosa in Kommentaren OK.
Verify = deploy.sh production (HART: kein Local-Dev, kein lokales pytest).
"""
import logging

log = logging.getLogger(__name__)

# Explizite Denylist-Eintraege, die IMMER exkludiert sind (unabhaengig vom Schema).
# alembic_version: Migrations-Stand-Tabelle, kein Test-Datum, kein watchbarer PK-Sinn.
_ALWAYS_DENY = {
    "public.alembic_version": "migration-state, not test-data",
}

# training.transcript_archive bleibt expliziter POST-SUITE-Check in deploy.sh (Plan 02),
# nicht im in-pytest-Waechter (ORM-los, deploy.sh prueft via sudo -u postgres direkt).
# Sie ist NICHT in _ALWAYS_DENY, weil sie ggf. in training-Schema existiert und der
# deploy.sh-Check sie separat abdeckt. Im foundation_register dokumentiert (D-G04).
_TRAINING_TRANSCRIPT_ARCHIVE_NOTE = (
    "training.transcript_archive: deliberately excluded from in-pytest auto-reset watcher "
    "(ORM-less; covered by POST-SUITE deploy.sh check as postgres peer, D-G04). "
    "Not in _ALWAYS_DENY to allow catalog enumeration."
)


def _schema_qualified(schema, table):
    """Gibt 'schema.table' zurueck. Konsistente Qualifizierung fuer alle Katalog-Outputs."""
    return f"{schema}.{table}"


def _kahn_topo_sort(nodes, edges):
    """Kahn-Algorithmus fuer einen gerichteten azyklischen Graphen.
    nodes: set von Knoten (Strings 'schema.table')
    edges: list von (child, parent) 2-Tupeln — Kind-Kanten (Kind zeigt auf Eltern).
           Der Caller (derive_baseline_tables) strippt confdeltype VOR dem Aufruf; die
           Unit-Tests rufen direkt mit 2-Tupeln auf. ALLE Kanten gehen in den Sort.
    Rueckgabe: Liste der Knoten in der UMGEKEHRTEN topologischen Reihenfolge
    (Leaves zuerst, also Kinder vor Eltern = reverse-FK-Loeschorder).

    Zyklus-Brechung (D-G16 Bau-Wachpunkt 1): self-ref-Kanten (child == parent) werden
    IGNORIERT. Mutual-FK-Zyklen (A->B und B->A) wuerden den Kahn-Algorithmus blockieren.
    Erkannte Restknoten (in-degree nach sort > 0) werden alphabetisch ans ENDE angehaengt.
    Der sort ist also best-effort zyklus-resistent.

    NERVE-konkrete self-ref/mutual-FK-Tabellen (aus Prod-Katalog 2026-06-16, psql gegen
    178.104.82.166): keine explizit bekannten mutual-FK-Zyklen. self-ref-Kanten werden
    standardmaessig ignoriert (child == parent check).

    CASCADE-Kanten (confdeltype='c') werden NICHT weggelassen (Gemini-Fund #1): in einer
    Kette A->(CASCADE)->B->(RESTRICT)->C wuerde das Weglassen der A->B-Kante den Sortierer
    A vor C lassen -> Loeschen von A cascadet auf B -> scheitert weil C noch auf B zeigt
    (FK-Violation) -> Waechter crasht -> Tor dauerhaft blockiert (DoS). ALLE Kanten gehen
    in den Sort; der ON-DELETE-CASCADE wird dadurch redundant aber nie fehlerhaft.
    """
    # Nur Kanten zwischen bekannten Knoten beruecksichtigen (Cross-Schema: Knoten aus
    # allen beteiligten Schemas). self-ref ignorieren.
    valid_edges = [
        (child, parent)
        # edges sind 2-Tupel (child, parent). Der Caller (derive_baseline_tables) strippt
        # confdeltype VOR dem Aufruf -> ALLE Kanten gehen in den Sort (Gemini-Fund #1, auch CASCADE).
        for child, parent in edges
        if child in nodes and parent in nodes and child != parent
    ]

    # Reverse-FK-Loeschorder (Kinder VOR Eltern): Kahn-Topo-Sort auf dem UMGEKEHRTEN
    # Graphen (parent->child) liefert Roots-zuerst; das Ergebnis wird am Ende umgedreht,
    # sodass Leaves (Kinder) zuerst stehen = sichere reverse-FK-DELETE-Reihenfolge.

    # Umgekehrter Graph: parent->child-Kanten
    reverse_adj = {n: [] for n in nodes}  # parent -> [children]
    reverse_in_degree = {n: 0 for n in nodes}  # in-degree im umgekehrten Graphen
    for child, parent in valid_edges:
        reverse_adj[parent].append(child)
        reverse_in_degree[child] += 1

    # Kahn auf umgekehrtem Graphen: Knoten mit reverse_in_degree==0 sind echte Roots (Tabellen ohne FK-Eltern).
    # MUTUAL-FK-ZYKLEN (Phase 08.23.2.PGTEST.GREEN Bug 3, empirisch via triage.sh): das reale Schema hat
    # echte 2-Zyklen (public.users<->public.organisations, public.users<->public.profiles). Ein reiner
    # Kahn-Sort kann einen Mutual-FK-Graphen NICHT linear ordnen -> frueher blieben users/organisations/
    # profiles + ALLES transitiv davon Abhaengige (inkl. crm.* via accounts->tenant_orgs->organisations)
    # als "Rest" und wurden alphabetisch ans Ende gehaengt = FALSCHE Loeschorder (test_06 rot). JETZT:
    # wenn die Queue leer ist aber Knoten fehlen, wird EINE Zyklus-Kante bewusst gebrochen (der Rest-Knoten
    # mit dem kleinsten residualen reverse_in_degree = am wenigsten gekoppelt wird freigegeben), dann Kahn
    # fortgesetzt. So bleiben ALLE Nicht-Zyklus-Kanten (inkl. cross-schema crm->public) erhalten -> die
    # crm-vor-public-Order stimmt; nur INNERHALB eines echten Mutual-FK-Zyklus gibt es keine perfekte Order
    # (eine Kante MUSS brechen). Die daraus theoretisch moegliche FK-Violation faengt der Cleanup-Retry-Loop
    # robust ab (conftest._fk_safe_delete_rows, Savepoint-pro-Tabelle).
    from collections import deque
    queue = deque(sorted(n for n in nodes if reverse_in_degree[n] == 0))
    topo_order = []  # Roots zuerst
    diagnosed = False

    while len(topo_order) < len(nodes):
        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for child in sorted(reverse_adj[node]):
                reverse_in_degree[child] -= 1
                if reverse_in_degree[child] == 0:
                    queue.append(child)

        if len(topo_order) >= len(nodes):
            break

        # --- Queue leer, aber Knoten fehlen -> Mutual-FK-Zyklus. Eine Kante bewusst brechen. ---
        done = set(topo_order)
        stuck = sorted(n for n in nodes if n not in done)
        stuck_set = set(stuck)

        if not diagnosed:
            # EINMALIGE Diagnose des vollen Zyklus-Kerns (Logging-First, fuer triage.sh-Beleg).
            diagnosed = True
            cycle_core_edges = sorted(
                f"{child}->{parent}"
                for child, parent in valid_edges
                if child in stuck_set and parent in stuck_set
            )
            residual_in_degree = {n: reverse_in_degree[n] for n in stuck if reverse_in_degree[n] > 0}
            blocking_parents = {}
            for child, parent in valid_edges:
                if child in stuck_set:
                    blocking_parents.setdefault(child, []).append(parent)
            log.warning(
                "[PGTEST-INTROSPECT] Mutual-FK-Zyklus erkannt: %d Knoten blockiert. "
                "Kern-Kanten (child->parent, beide im Rest) = %s",
                len(stuck), cycle_core_edges,
            )
            log.warning(
                "[PGTEST-INTROSPECT] Zyklus-Diagnose: Rest-Restgrad reverse_in_degree>0 = %s",
                residual_in_degree,
            )
            log.warning(
                "[PGTEST-INTROSPECT] Zyklus-Diagnose: FK-Eltern pro Rest-Knoten = %s",
                {k: sorted(v) for k, v in sorted(blocking_parents.items())},
            )

        # Opfer-Knoten = der echte Zyklus-HUB: der Rest-Knoten mit den MEISTEN noch blockierten Kindern
        # im Rest-Graph (Gemini-3.1-Pro 3.-Sicht, _green_bug3_gemini_OUT.md, Punkt-24-Beleg).
        # NICHT min(reverse_in_degree): das waehlte ein BLATT (z.B. crm.accounts, 0 Kinder) und machte es
        # per in_degree=0 zur Root -> frueh in topo_order -> nach reversed() SPAET in der Loeschorder ->
        # crm.accounts landete HINTER public.tenant_orgs -> test_06 rot + FK-Violation (eine legitime
        # Nicht-Zyklus-Kante accounts->tenant_orgs wurde invertiert). Den HUB (z.B. public.organisations,
        # viele Kinder) zur Root zu machen = spaet geloescht (korrekt fuer einen vielreferenzierten Parent);
        # gebrochen wird nur eine INTRA-SCC-Kante (organisations->users). Blaetter bleiben frueh ->
        # crm-vor-public erhalten (test_06 gruen). Der Retry-Loop-Airbag zuendet nur fuer die echte Bruecke.
        victim = max(stuck, key=lambda n: (sum(1 for child in reverse_adj[n] if child in stuck_set), n))
        blocked_kids = sum(1 for child in reverse_adj[victim] if child in stuck_set)
        log.warning(
            "[PGTEST-INTROSPECT] Zyklus-Kante gebrochen: HUB %s als Root freigegeben "
            "(blockiert %d Rest-Kinder, %d Rest-Knoten) -> eine FK-Kante bewusst ignoriert.",
            victim, blocked_kids, len(stuck),
        )
        reverse_in_degree[victim] = 0
        queue.append(victim)

    # Umkehren: Roots waren zuerst, jetzt Leaves (Kinder) zuerst = reverse-FK-Loeschorder
    return list(reversed(topo_order))


def primary_key_column(conn_or_cur, table, schema='public'):
    """PK-Spaltenname AUS DEM KATALOG (pg_index indisprimary), NICHT 'id' hardcoden (D-G17 REFINEMENT).
    Wird von conftest.py fuer das Auto-Delete pro Tabelle konsumiert (Gemini-Fund #2).

    Composite PK (>1 indisprimary-Zeile): die Tabelle ist NICHT auto-delete-faehig (Gemini-Fund #6) —
    sie wird in der Derivation ins foundation_register gelegt (Grund 'composite PK: not auto-delete-
    eligible AND not snapshot-monitored (known gate gap)') und NICHT fuer den Auto-Delete-Pfad
    freigegeben (gibt None zurueck).

    Gibt zurueck: (pk_col_name_str, pk_count_int)
      pk_col_name_str: Spaltenname wenn len==1, sonst None
      pk_count_int: Anzahl PK-Spalten (0=kein PK, 1=single PK, >1=composite)
    """
    qualified = _schema_qualified(schema, table)
    try:
        import psycopg2.extras  # noqa: F401 — nur zur Verfuegbarkeits-Pruefung
        is_psycopg2_cur = hasattr(conn_or_cur, 'execute') and hasattr(conn_or_cur, 'fetchall')
    except ImportError:
        is_psycopg2_cur = False

    pk_query = (
        "SELECT a.attname FROM pg_index i "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = %s::regclass AND i.indisprimary "
        "ORDER BY a.attname"
    )

    try:
        if hasattr(conn_or_cur, 'cursor'):
            # psycopg2 Connection
            cur = conn_or_cur.cursor()
            cur.execute(pk_query, (qualified,))
            rows = cur.fetchall()
            cur.close()
        elif hasattr(conn_or_cur, 'execute') and hasattr(conn_or_cur, 'fetchall'):
            # psycopg2 Cursor
            conn_or_cur.execute(pk_query, (qualified,))
            rows = conn_or_cur.fetchall()
        else:
            # SQLAlchemy Connection. WICHTIG: KEIN named-param mit ::cast mischen —
            # `:tbl::regclass` laesst SQLAlchemy/psycopg2 mit "syntax error at or near ':'"
            # crashen (empirisch via triage.sh gefunden, Phase 08.23.2.PGTEST.GREEN Bug 2:
            # JEDE Tabelle warf -> pk_count=0 -> alles in foundation_register -> Cache leer).
            # Stattdessen den katalog-abgeleiteten Namen inline interpolieren (injection-sicher,
            # gleiche Technik wie _fetch_fk_edges) und das regclass-Cast als reines Literal lassen.
            from sqlalchemy import text as sa_text
            result = conn_or_cur.execute(
                sa_text(
                    "SELECT a.attname FROM pg_index i "
                    "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
                    f"WHERE i.indrelid = '{qualified}'::regclass AND i.indisprimary "
                    "ORDER BY a.attname"
                )
            )
            rows = result.fetchall()
    except Exception as e:
        log.warning("[PGTEST-INTROSPECT] primary_key_column: Fehler fuer %s: %r", qualified, e)
        return None, 0

    pk_cols = [r[0] for r in rows]
    count = len(pk_cols)
    if count == 1:
        return pk_cols[0], 1
    elif count == 0:
        return None, 0
    else:
        return None, count  # Composite PK


def derive_baseline_tables(conn_or_dsn, schemas=('public',)):
    """Liefert (baseline_table_list, reverse_fk_delete_order, foundation_register).

    schemas: ein Tuple von Schema-Namen (z.B. ('public',), ('crm',) oder ('public','crm','training')).
        Die Katalog-Queries parametrisieren auf `n.nspname IN %s` mit dem Tuple — exakt wie der
        SCHILD-Guard (test_schild_guard.py) public+crm+training in EINER Query liest (Gemini-Fund #8).
        Alle zurueckgegebenen Tabellen sind SCHEMA-QUALIFIZIERT ('schema.table').
    baseline_table_list: alle base-Tabellen (relkind='r') der Schemas minus begruendete Denylist
        (inkl. composite-PK-Tabellen, die NICHT auto-delete-faehig sind — Fund #6).
    reverse_fk_delete_order: GLOBALER CROSS-SCHEMA-topo-Sort Kind-vor-Eltern; ALLE FK-Kanten gehen
        in den Sort (auch CASCADE/confdeltype='c') — garantiert Leaves-vor-Roots auch ueber
        CASCADE->RESTRICT-Ketten (D-G16 WP2, Gemini-Fund #1) UND ueber CROSS-SCHEMA-Kanten
        (crm.accounts -> public.tenant_orgs -> crm.accounts steht VOR public.tenant_orgs, Fund #8).
        Nur self-ref/mutual-Kanten werden zur Zyklus-Brechung ignoriert.
    foundation_register: dict {table: reason} jeder bewusst exkludierten Tabelle (D-G17, Req-7 — nie still).
        Enthaelt u.a. composite-PK-Tabellen mit reason
        'composite PK: not auto-delete-eligible AND not snapshot-monitored (known gate gap)' (Fund #6/#9).

    PROD-KATALOG-FAKT (2026-06-16, sudo -u postgres psql gegen live nerve auf 178.104.82.166):
    0 composite-PK-Tabellen in public (38 base-Tabellen), crm (5), training (2).
    Die composite-PK-Denylist ist damit heute LATENT/leer (nichts faellt aktuell hinein).
    Genau DESHALB ist die ehrliche Dokumentation (nicht Tuple-Key bauen, Fund #9) korrekt.
    FOLLOW-UP (deferred, YAGNI, Backlog-999.x): falls TAXO oder eine kuenftige Migration je
    eine composite-PK-Tabelle einfuehrt, MUSS `_snapshot_public_tables` in conftest.py auf einen
    Tuple-Key (alle PK-Spalten als dict-Key) umgebaut werden, um die Luecke zu schliessen.
    """
    foundation_register = {}

    # Denylist-Eintraege fuer IMMER exkludierte Tabellen
    for denied_tbl, reason in _ALWAYS_DENY.items():
        schema_part = denied_tbl.split('.')[0]
        if schema_part in schemas:
            foundation_register[denied_tbl] = reason

    # Verbindung aufbauen
    _conn, _close_conn = _get_connection(conn_or_dsn)
    try:
        # 1. Alle base-Tabellen aller Schemas einlesen (relkind='r' filtert Views/Matviews, D-G17)
        all_tables = _fetch_base_tables(_conn, schemas)

        # 2. FK-Kanten lesen (CROSS-SCHEMA, alle Kanten inkl. CASCADE, D-G16, Fund #8, Fund #1)
        fk_edges = _fetch_fk_edges(_conn, schemas)

        # 3. PK-Spalte pro Tabelle aus Katalog ableiten (D-G17 REFINEMENT, Fund #2, Fund #6, Fund #9)
        pk_cols_map = {}  # {qualified_table: pk_col_name} — NUR single-PK-Tabellen
        baseline_table_list = []

        for qualified_tbl in sorted(all_tables):
            # Denylist-Check
            if qualified_tbl in foundation_register:
                continue

            schema_name, table_name = qualified_tbl.split('.', 1)
            pk_col, pk_count = _fetch_pk_for_table(_conn, schema_name, table_name)

            if pk_count == 0:
                reason = "no watchable PK"
                foundation_register[qualified_tbl] = reason
                log.warning(
                    "[PGTEST-INTROSPECT] Tabelle %s hat keinen PK — Denylist-Eintrag: %s",
                    qualified_tbl, reason,
                )
                continue

            if pk_count > 1:
                # Composite PK (>1 indisprimary-Zeile) — NICHT auto-delete-faehig (Fund #6),
                # NICHT snapshot-ueberwacht (Fund #9).
                # EHRLICHKEIT: dieser Grund sagt EXPLIZIT, dass die Tabelle weder auto-deleted
                # noch snapshot-ueberwacht wird — sie ist ein unueberwachter blinder Fleck,
                # OFFEN protokolliert. KEINE falsche "Snapshot-sichtbar"-Behauptung (Fund #9).
                # FOLLOW-UP (Backlog-999.x, deferred/YAGNI): Tuple-Key fuer _snapshot_public_tables.
                reason = "composite PK: not auto-delete-eligible AND not snapshot-monitored (known gate gap)"
                foundation_register[qualified_tbl] = reason
                log.warning(
                    "[PGTEST-INTROSPECT] Tabelle %s hat Composite-PK (%d Spalten) — Denylist-Eintrag: %s",
                    qualified_tbl, pk_count, reason,
                )
                continue

            # Single-PK-Tabelle: auto-delete-faehig
            pk_cols_map[qualified_tbl] = pk_col
            baseline_table_list.append(qualified_tbl)

        # 4. topo-Sort (Kahn, Kind-vor-Eltern = reverse-FK-Loeschorder)
        #    Alle Knoten = alle bekannten Tabellen (baseline + foundation_register)
        #    FK-Kanten: ALLE (auch CASCADE) gehen in den Sort (Fund #1)
        #    Cross-Schema-Kanten (crm.accounts -> public.tenant_orgs) ebenfalls (Fund #8)
        #    NERVE-konkrete CROSS-SCHEMA-FK-Kante: crm.accounts -> public.tenant_orgs
        #    (bewiesen via sudo -u postgres psql gegen 178.104.82.166, 2026-06-16).
        all_known = set(all_tables) | set(foundation_register.keys())
        # fk_edges sind 3-Tupel (child, parent, confdeltype); _kahn_topo_sort nimmt 2-Tupel
        # (wie die Unit-Tests) -> confdeltype hier strippen. ALLE Kanten gehen in den Sort.
        reverse_fk_delete_order = _kahn_topo_sort(all_known, [(c, p) for c, p, _ in fk_edges])

        return baseline_table_list, reverse_fk_delete_order, foundation_register

    finally:
        if _close_conn:
            try:
                _conn.close()
            except Exception:
                pass


def _get_connection(conn_or_dsn):
    """Gibt (connection, should_close) zurueck. Akzeptiert:
    - einen String (DSN -> neue psycopg2-Connection oeffnen, should_close=True)
    - eine psycopg2-Connection (should_close=False)
    - ein SQLAlchemy-Engine (gibt eine Connection aus dem Pool, should_close=True)
    - eine SQLAlchemy-Connection (should_close=False)
    """
    if isinstance(conn_or_dsn, str):
        import psycopg2
        conn = psycopg2.connect(conn_or_dsn)
        return conn, True
    # SQLAlchemy Engine
    try:
        from sqlalchemy.engine import Engine
        if isinstance(conn_or_dsn, Engine):
            return conn_or_dsn.connect(), True
    except ImportError:
        pass
    # Sonst: direkt als Connection annehmen
    return conn_or_dsn, False


def _execute_query(conn, query, params=None):
    """Fuehrt eine Query aus und gibt alle Zeilen zurueck.
    Unterstuetzt psycopg2-Connection/Cursor UND SQLAlchemy-Connection.
    """
    # psycopg2 Connection (hat .cursor(), nicht .execute())
    if hasattr(conn, 'cursor') and not hasattr(conn, 'execute'):
        cur = conn.cursor()
        if params is not None:
            cur.execute(query, params)
        else:
            cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        return rows

    # SQLAlchemy Connection (hat .execute())
    try:
        from sqlalchemy import text as sa_text
        # SQLAlchemy-Style: %s -> :param Placeholder ersetzen
        # Fuer diese Katalog-Queries verwenden wir direkte SA-text mit psycopg2-Stil-Params
        # Fuer Tuple-Parameter (IN %s) muessen wir anders vorgehen
        if params is not None:
            result = conn.execute(sa_text(query), params)
        else:
            result = conn.execute(sa_text(query))
        return result.fetchall()
    except Exception:
        # Fallback: psycopg2 Cursor falls conn ein psycopg2-Cursor-aehnliches Objekt ist
        if hasattr(conn, 'execute') and hasattr(conn, 'fetchall'):
            if params is not None:
                conn.execute(query, params)
            else:
                conn.execute(query)
            return conn.fetchall()
        raise


def _fetch_base_tables(conn, schemas):
    """Liefert set von schema-qualifizierten base-Tabellen aller angegebenen Schemas.
    relkind='r' filtert Views/Matviews automatisch (D-G17 denylist edge handled by catalog).
    Analog zu test_schild_guard.py:53-66 mit n.nspname IN %s.
    """
    # psycopg2: %s-Placeholder, schemas als Tuple
    # SQLAlchemy: braucht andere Syntax
    if _is_psycopg2_conn(conn):
        cur = conn.cursor()
        cur.execute(
            "SELECT n.nspname, c.relname "
            "FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind = 'r' AND n.nspname IN %s "
            "ORDER BY n.nspname, c.relname",
            (tuple(schemas),),
        )
        rows = cur.fetchall()
        cur.close()
    else:
        # SQLAlchemy Connection: IN-Clause via ANY(:arr) oder explizites Tuple
        from sqlalchemy import text as sa_text
        placeholders = ', '.join(f"'{s}'" for s in schemas)
        result = conn.execute(sa_text(
            f"SELECT n.nspname, c.relname "
            f"FROM pg_class c "
            f"JOIN pg_namespace n ON n.oid = c.relnamespace "
            f"WHERE c.relkind = 'r' AND n.nspname IN ({placeholders}) "
            f"ORDER BY n.nspname, c.relname"
        ))
        rows = result.fetchall()

    return {_schema_qualified(r[0], r[1]) for r in rows}


def _fetch_fk_edges(conn, schemas):
    """Liefert list von (child_qualified, parent_qualified, confdeltype) Tupeln.
    ALLE FK-Kanten werden zurueckgegeben (auch CASCADE, confdeltype='c') — Fund #1.
    CROSS-SCHEMA (Fund #8): Kanten zwischen verschiedenen Schemas (z.B. crm.accounts -> public.tenant_orgs)
    werden erfasst. confdeltype='c' = ON DELETE CASCADE — wird gelesen, aber NICHT zum Ausschluss benutzt.

    NAMING-KONSISTENZ (Fund #8 Bau-Wachpunkt): ::regclass::text liefert fuer search_path-Schemas
    UNQUALIFIZIERTE Namen. Wir verwenden explizit n.nspname || '.' || c.relname um konsistente
    schema.table-Namen zu erhalten, damit der startswith('public.')-Filter und _CLEANUP_FK_ORDER
    aufeinander passen.

    NERVE-bekannte Cross-Schema-Kante (Prod-Katalog 2026-06-16): crm.accounts -> public.tenant_orgs
    (confdeltype='a' = NO ACTION/RESTRICT). Diese Kante geht in den Sort -> crm.accounts VOR
    public.tenant_orgs in der reverse_fk_delete_order.
    """
    if _is_psycopg2_conn(conn):
        cur = conn.cursor()
        # Subquery fuer parent-Schema: da cross-schema Kanten existieren (crm -> public),
        # lesen wir den Schema-Namen des parent explizit aus pg_namespace.
        # connamespace ist das Schema des CHILD (wo die FK-Constraint definiert ist).
        # confrelid ist die OID der parent-Tabelle (aus EINEM anderen Schema moeglich).
        cur.execute(
            "SELECT "
            "  n_child.nspname || '.' || c_child.relname AS child, "
            "  n_parent.nspname || '.' || c_parent.relname AS parent, "
            "  con.confdeltype "
            "FROM pg_constraint con "
            "JOIN pg_class c_child ON c_child.oid = con.conrelid "
            "JOIN pg_namespace n_child ON n_child.oid = c_child.relnamespace "
            "JOIN pg_class c_parent ON c_parent.oid = con.confrelid "
            "JOIN pg_namespace n_parent ON n_parent.oid = c_parent.relnamespace "
            "WHERE con.contype = 'f' AND n_child.nspname IN %s "
            "ORDER BY child, parent",
            (tuple(schemas),),
        )
        rows = cur.fetchall()
        cur.close()
    else:
        from sqlalchemy import text as sa_text
        placeholders = ', '.join(f"'{s}'" for s in schemas)
        result = conn.execute(sa_text(
            f"SELECT "
            f"  n_child.nspname || '.' || c_child.relname AS child, "
            f"  n_parent.nspname || '.' || c_parent.relname AS parent, "
            f"  con.confdeltype "
            f"FROM pg_constraint con "
            f"JOIN pg_class c_child ON c_child.oid = con.conrelid "
            f"JOIN pg_namespace n_child ON n_child.oid = c_child.relnamespace "
            f"JOIN pg_class c_parent ON c_parent.oid = con.confrelid "
            f"JOIN pg_namespace n_parent ON n_parent.oid = c_parent.relnamespace "
            f"WHERE con.contype = 'f' AND n_child.nspname IN ({placeholders}) "
            f"ORDER BY child, parent"
        ))
        rows = result.fetchall()

    return [(r[0], r[1], r[2]) for r in rows]


def _fetch_pk_for_table(conn, schema, table):
    """Liefert (pk_col_name, pk_count) fuer eine einzelne Tabelle.
    pk_col_name: Spaltenname wenn pk_count==1, sonst None.
    pk_count: 0=kein PK, 1=single PK, >1=composite PK.

    KONSOLIDIERT (Phase 08.23.2.PGTEST.GREEN Bug 2): delegiert an primary_key_column —
    EINE Quelle der Wahrheit fuer die PK-Katalog-Abfrage. Vorher war die Abfrage hier dupliziert
    und trug denselben `:tbl::regclass`-named-param-Bug (-> Fehler-Flood -> leerer Cache).
    Arg-Reihenfolge bewusst verschieden: hier (conn, schema, table), primary_key_column nimmt
    (conn_or_cur, table, schema) — die Delegation mappt sie korrekt.
    """
    return primary_key_column(conn, table, schema)


def _is_psycopg2_conn(conn):
    """True wenn conn eine psycopg2-Connection ist (hat .cursor() aber kein .execute() direkt)."""
    return hasattr(conn, 'cursor') and not hasattr(conn, 'execute')
