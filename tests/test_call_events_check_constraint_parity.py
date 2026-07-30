"""Waechter R3 (CHECK-Constraint-Paritaet) — Phase 08.23.2.COUNTERPART.

database/models.py deklarierte 7 event_type-Werte, die echte Datenbank kannte 9
(Migration 0004 vom 2026-05-21 ergaenzte mode_switch + mode_initial, die ORM-Deklaration
hinkte seitdem hinterher). Die Drift lag ueber ein Jahr unbemerkt herum und ist erst in
dieser Phase per Zufallsfund aufgefallen.

Ein einmaliger inspect.sh-Blick ist KEIN Waechter: bei der naechsten Constraint-Aenderung
entsteht dieselbe Drift wieder. Dieser Test diffft die Werteliste der ORM-CheckConstraint
gegen den echten Constraint in Postgres und laeuft im deploy.sh-production-Gate mit
(pytest tests/ dort mit gesetztem NERVE_SCHILD_TEST_DSN). Lokal ohne DSN: SKIP, nie ein
SQLite-Fallback (der wuerde die Frage gar nicht beantworten koennen).

Warum pg_catalog statt information_schema.check_constraints: information_schema ist
privilegien-maskiert und liefert der Rolle nerve_app ggf. LEER -> False-Negative.
pg_catalog.pg_constraint + pg_get_constraintdef ist fuer jede Rolle lesbar und traegt
dieselbe Information. "Constraint nicht gefunden" ist deshalb ein FEHLER, kein Skip.

KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel): Test 1 vergleicht zwei
LAUFZEIT-Quellen (SQLAlchemy-Metadata vs. Postgres-Katalog). Test 2 ist ein reiner
Parser-/Diff-Test mit synthetischen Eingaben und belegt die Falsifizierbarkeit ohne DB.
"""
import re

_CONSTRAINT_NAME = 'ck_call_events_event_type'
_TABLE = 'call_events'


def _parse_values(sql: str) -> frozenset:
    """Zieht die einfach-gequoteten Literale aus einer CHECK-Definition.

    Vergleicht MENGEN, nicht Text: pg_get_constraintdef normalisiert den Ausdruck
    (::text-Casts, ANY (ARRAY[...])) — ein String-Vergleich waere dauerhaft rot
    ohne echte Drift.
    """
    return frozenset(re.findall(r"'([^']+)'", sql or ''))


def _orm_values() -> frozenset:
    """Werteliste aus der ORM-Deklaration (Laufzeit, ueber die SQLAlchemy-Metadata)."""
    from sqlalchemy import CheckConstraint
    from database.models import CallEvent
    for c in CallEvent.__table__.constraints:
        if isinstance(c, CheckConstraint) and c.name == _CONSTRAINT_NAME:
            return _parse_values(str(c.sqltext))
    raise AssertionError(
        f'CheckConstraint {_CONSTRAINT_NAME!r} fehlt in der ORM-Deklaration von CallEvent '
        '— entweder umbenannt oder geloescht. Beides ist ein Befund, kein Testfehler.')


def test_orm_declaration_is_parsable():
    """Laeuft immer: die ORM-Deklaration existiert und traegt eine nicht-leere Werteliste."""
    vals = _orm_values()
    assert len(vals) >= 9, (
        f'ORM-CHECK-Werteliste hat nur {len(vals)} Werte: {sorted(vals)} — '
        'erwartet werden mindestens die 9 seit Migration 0004 gueltigen event_type-Werte.')


def test_parser_detects_drift():
    """Falsifizierbarkeit ohne DB: der Diff-Kern erkennt eine Abweichung wirklich."""
    db = _parse_values("CHECK (event_type::text = ANY (ARRAY['a'::text, 'b'::text]))")
    orm = _parse_values("event_type IN ('a')")
    assert db == frozenset({'a', 'b'})
    assert db != orm, 'Der Parser wuerde eine echte Drift nicht sehen — Waechter wertlos.'
    assert (db - orm) == frozenset({'b'})


def test_check_constraint_matches_db(schild_guard_pg_conn):
    """Der eigentliche Waechter: ORM-Deklaration == echter Constraint in Postgres."""
    cur = schild_guard_pg_conn.cursor()
    cur.execute(
        """
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.conname = %s AND t.relname = %s AND n.nspname = 'public'
        """,
        (_CONSTRAINT_NAME, _TABLE),
    )
    rows = cur.fetchall()
    assert len(rows) == 1, (
        f'Erwartet genau EINEN Constraint {_CONSTRAINT_NAME!r} auf public.{_TABLE}, '
        f'gefunden: {len(rows)}. "Nicht gefunden" ist ein Befund, kein Skip '
        '(pg_catalog ist nicht privilegien-maskiert).')
    db_vals = _parse_values(rows[0][0])
    orm_vals = _orm_values()
    assert db_vals == orm_vals, (
        'DRIFT zwischen ORM-Deklaration und echter Datenbank:\n'
        f'  nur in models.py : {sorted(orm_vals - db_vals)}\n'
        f'  nur in der DB    : {sorted(db_vals - orm_vals)}\n'
        f'  DB-Definition    : {rows[0][0]}\n\n'
        'Regel (AUTH-2-Expand/Contract): die Deklaration zieht der DB NACH, nie voraus. '
        'Wer eine CHECK-Werteliste aendert, aendert BEIDES im selben Schritt — '
        'Migration und models.py.')
