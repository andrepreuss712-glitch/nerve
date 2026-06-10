"""Phase 08.23.2.SCHILD Wave 4 — Deploy-blocking "Schild" guard.

Verifies that EVERY table and every non-trivial column in the public / crm / training schemas
carries a Postgres COMMENT (the "Schild") of >=10 characters in pg_description.

Design (locked decisions):
- Checks pg_description DIRECTLY on the DB (all 3 schemas), NOT models.py — so it also catches the
  ORM-less `training.transcript_archive` (L-07).
- Runs ONLY against real Postgres via the `schild_guard_pg_conn` fixture (GUARD_ROLE=nerve_app, no
  GRANT needed — proven in DISCOVERY-DECISIONS.md). On SQLite/local (no DSN) it SKIPS — never a
  SQLite fallback (RESEARCH §1.3 False-Green trap).
- Existence + min length ONLY. NO FK-in-text matching (L-05). A 3-char stub like "tbd" counts as missing.
- Real integration test: queries the live catalog and asserts on real COMMENT values (NOT a
  source-presence false-green, CLAUDE.md Test-Qualitaets-Regel).
- NO pytest.mark.xfail (Cross-AI-Finding 3 considered, rejected — the explicit server-observed
  RED→GREEN transition is the checker-mandated evidence; the deploy flow is solved by running this
  guard separately for the RED observation, then wiring it into deploy.sh only after Plan 04 GREEN).

Wave order: this guard is built in Wave 4 BEFORE the comment migration (Plan 04, Wave 5). It is
EXPECTED to FAIL (RED) here — the tables are still schild-less. Plan 04 flips it GREEN.
"""

SCHEMAS = ('public', 'crm', 'training')
MIN_LEN = 10

# Tables that are infrastructure, not domain data — excluded from the Schild requirement.
EXCLUDED_TABLES = frozenset({'alembic_version'})

# ── L-04 trivial-column convention (MUST match the same rule used in database/models.py) ──
# Trivial columns are NOT required to carry a Schild. This name-based filter is the CONTRACT the
# Plan-04 migration must satisfy: every column that is NOT trivial here must get a COMMENT.
_TRIVIAL_EXACT = frozenset({
    'id', 'created_at', 'updated_at', 'erstellt_am', 'aktualisiert_am', 'aktiv',
})


def _is_trivial_column(name: str) -> bool:
    """L-04: id, created_at, updated_at, erstellt_am, aktualisiert_am, *_id (FK/refs),
    is_* / aktiv flags, UUID/serial PK named id. Name-based — no FK lookup (L-05)."""
    if name in _TRIVIAL_EXACT:
        return True
    if name.endswith('_id'):        # foreign keys + polymorphic id refs (incl. UUID *_id PKs)
        return True
    if name.startswith('is_'):      # boolean flags
        return True
    return False


def _schema_in_clause():
    return ", ".join("%s" for _ in SCHEMAS)


def test_alle_tabellen_haben_schild(schild_guard_pg_conn):
    """Every regular table in public/crm/training must have a table COMMENT >=10 chars."""
    cur = schild_guard_pg_conn.cursor()
    cur.execute(
        f"""
        SELECT n.nspname, c.relname, obj_description(c.oid, 'pg_class') AS schild
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ({_schema_in_clause()})
          AND c.relkind = 'r'
        ORDER BY n.nspname, c.relname
        """,
        SCHEMAS,
    )
    fehlend = []
    for schema, table, schild in cur.fetchall():
        if table in EXCLUDED_TABLES:
            continue
        if schild is None or len(schild.strip()) < MIN_LEN:
            fehlend.append(f"{schema}.{table}  (Schild={schild!r})")
    cur.close()

    assert not fehlend, (
        f"{len(fehlend)} Tabelle(n) ohne Schild (>={MIN_LEN} Zeichen in pg_description):\n  "
        + "\n  ".join(fehlend)
        + "\n\nJede Tabelle braucht ein COMMENT ON TABLE ... IS '<Zweck>. Status: ...'. "
        "Setze es in database/models.py (comment=) + Migration, oder fuer ORM-lose Tabellen "
        "(transcript_archive) direkt in der Migration."
    )


def test_nicht_triviale_spalten_haben_schild(schild_guard_pg_conn):
    """Every non-trivial column (L-04) in public/crm/training must have a column COMMENT >=10 chars."""
    cur = schild_guard_pg_conn.cursor()
    cur.execute(
        f"""
        SELECT n.nspname, c.relname, a.attname, col_description(c.oid, a.attnum) AS schild
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname IN ({_schema_in_clause()})
          AND c.relkind = 'r'
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY n.nspname, c.relname, a.attnum
        """,
        SCHEMAS,
    )
    fehlend = []
    for schema, table, column, schild in cur.fetchall():
        if table in EXCLUDED_TABLES:
            continue
        if _is_trivial_column(column):
            continue
        if schild is None or len(schild.strip()) < MIN_LEN:
            fehlend.append(f"{schema}.{table}.{column}  (Schild={schild!r})")
    cur.close()

    assert not fehlend, (
        f"{len(fehlend)} nicht-triviale Spalte(n) ohne Schild (>={MIN_LEN} Zeichen):\n  "
        + "\n  ".join(fehlend)
        + "\n\nSetze comment= auf die Spalte in database/models.py + Migration "
        "(Trivial-Spalten id/created_at/*_id/is_*/aktiv sind ausgenommen, L-04)."
    )
