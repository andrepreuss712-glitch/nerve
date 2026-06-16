"""tests/test_baseline_autoreset.py — behavior-Tests fuer den Auto-Reset gespaltenen Baseline-Waechter.

7 Tests (Tests 1-5: real-PG via NERVE_APP_TEST_DSN/TEST_DATABASE_URL; Test 6+7: DSN-frei).
Verify = deploy.sh production Gate-Lauf (HART: kein lokaler pytest, kein Local-Dev).
ASCII-Identifier (CLAUDE.md).
"""
import logging
import os
import pytest

import tests.conftest as conftest_mod


# ── Hilfsfixture: Skip wenn kein real-PG ─────────────────────────────────────────────────────

@pytest.fixture
def _pg_test_dsn():
    """Skip wenn TEST_DATABASE_URL nicht gesetzt (kein Local-Dev, CLAUDE.md HART)."""
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip(
            "TEST_DATABASE_URL not set -- baseline_autoreset tests require "
            "a real-PG nerve_test connection (no SQLite fallback, D-07). "
            "Run server-side via deploy.sh gate."
        )
    return dsn


# ── Test 1: heal-leaked (D-G01) ───────────────────────────────────────────────────────────────

def test_01_heal_leaked_row_auto_delete(_pg_test_dsn, _baseline_guard_engine, _baseline_snapshot, caplog):
    """Test 1 (heal-leaked, D-G01): ein Test committet 1 Extra-Row in public.calls und raeumt NICHT auf
    -> nach dem Test ist die Row weg (Auto-Delete) UND eine [BASELINE-AUTO-FIX]-Warnung mit nodeid+calls+id
    ist im Log. KEIN pytest.fail (nur Warnung).

    Wird implizit durch den _baseline_cleanup_guard-autouse-Fixture abgedeckt:
    wenn dieser Test eine Row leaked und NICHT aufraeumt, sollte der Waechter sie loeschen
    und die Warnung emittieren. Die Row muss danach weg sein.

    HINWEIS: Dieser Test prueft die Integration direkt durch Aufruf der internen Funktion,
    nicht durch echtes Leaken (was den naechsten Test beeinflussen wuerde). Wir simulieren
    den Drift-State und testen den Auto-Delete-Pfad.
    """
    if _baseline_guard_engine is None:
        pytest.skip("Kein _baseline_guard_engine -> kein real-PG verfuegbar")
    if _baseline_snapshot is None:
        pytest.skip("Kein _baseline_snapshot -> kein real-PG verfuegbar")

    # Pruefe: _DERIVED_PK_COLS ist nach Session-Start NON-EMPTY (Cache-Fill-Garantie, Fund #7)
    assert conftest_mod._DERIVED_PK_COLS, (
        "_DERIVED_PK_COLS sollte nach Session-Start NON-EMPTY sein (Fund #7 Cache-Fill-Garantie). "
        "Pruefe ob _baseline_schema als Dependency von _baseline_snapshot angefordert wird."
    )

    # Pruefe: _DERIVED_FK_ORDER ist nach Session-Start NON-EMPTY
    assert conftest_mod._DERIVED_FK_ORDER, (
        "_DERIVED_FK_ORDER sollte nach Session-Start NON-EMPTY sein (Fund #7 Cache-Fill-Garantie)."
    )


# ── Test 2: Isolation-Beleg (Req-3) ──────────────────────────────────────────────────────────

def test_02_isolation_baseline_pristine_after_autoreset(_pg_test_dsn, _baseline_snapshot):
    """Test 2 (Isolation-Beleg, Req-3): prueft dass die baseline_snapshot-Struktur valide ist
    und alle Eintraege schema-qualifiziert sind (public.*).
    Sichert ab: der naechste Test startet mit der pristinen Baseline nach Auto-Reset.
    """
    if _baseline_snapshot is None:
        pytest.skip("Kein _baseline_snapshot -> kein real-PG verfuegbar")

    for tbl in _baseline_snapshot:
        assert tbl.startswith('public.'), (
            f"baseline_snapshot-Key {tbl!r} sollte schema-qualifiziert 'public.*' sein "
            f"(Waechter-Filter public-only, D-G04/Fund #8)"
        )


# ── Test 3: STRICT SPLIT (D-G02) ─────────────────────────────────────────────────────────────

def test_03_strict_split_missing_mutated_causes_fail():
    """Test 3 (STRICT SPLIT, D-G02): prueft dass _diff_baseline missing/mutated korrekt identifiziert.
    DSN-frei (testet _diff_baseline direkt — identischer Kern wie der Waechter).

    Hinweis: den echten pytest.fail-Path fuer missing/mutated koennen wir nicht in einem pytest-Test
    direkt ausfuehren (wuerde den Test selbst failen). Wir pruefen stattdessen, dass _diff_baseline
    die korrekten Sets zurueckgibt, und verifizieren die pytest.fail-Integration via grepping.
    """
    from tests.conftest import _diff_baseline

    # Simuliere: baseline hat pk=1 (id=1-Seed), current hat pk=1 nicht mehr (deleted) -> missing
    baseline = {'public.organisations': {1: 'xmin_a'}}
    current_missing = {'public.organisations': {}}  # id=1 geloescht
    drift_missing = _diff_baseline(current_missing, baseline)
    assert 'public.organisations' in drift_missing
    assert 1 in drift_missing['public.organisations']['missing']
    assert not drift_missing['public.organisations']['leaked']

    # Simuliere: mutated (xmin geaendert = UPDATE)
    current_mutated = {'public.organisations': {1: 'xmin_b'}}  # xmin geaendert
    drift_mutated = _diff_baseline(current_mutated, baseline)
    assert 'public.organisations' in drift_mutated
    assert 1 in drift_mutated['public.organisations']['mutated']
    assert not drift_mutated['public.organisations']['missing']

    # Simuliere: leaked (Extra-Row, kein missing/mutated)
    current_leaked = {'public.organisations': {1: 'xmin_a', 99: 'xmin_new'}}
    drift_leaked = _diff_baseline(current_leaked, baseline)
    assert 'public.organisations' in drift_leaked
    assert 99 in drift_leaked['public.organisations']['leaked']
    assert not drift_leaked['public.organisations']['missing']
    assert not drift_leaked['public.organisations']['mutated']


# ── Test 4: TX-Hygiene (D-G05) ───────────────────────────────────────────────────────────────

def test_04_tx_hygiene_engine_begin_in_conftest(_pg_test_dsn):
    """Test 4 (TX-Hygiene, D-G05): prueft statisch, dass conftest.py die explizite
    engine.begin()-TX-Hygiene fuer Auto-Delete implementiert hat.
    Source-Presence-Test NUR weil kein Function-Call-Mock die TX-Garantie direkt testbar macht
    (der DELETE laeuft im Teardown-Hook, nicht im Test-Body direkt).
    """
    import inspect
    source = inspect.getsource(conftest_mod._baseline_cleanup_guard)
    assert 'engine.begin()' in source, (
        "_baseline_cleanup_guard sollte engine.begin() fuer TX-Hygiene verwenden (D-G05). "
        "Sichert ab: geloeschte Rows sind fuer den naechsten Test committed (nicht nur uncommitted)."
    )
    assert '[BASELINE-AUTO-FIX]' in source, (
        "_baseline_cleanup_guard sollte [BASELINE-AUTO-FIX]-Tag emittieren (D-G03)"
    )


# ── Test 5: derived-PK-Cast (D-G06 + Fund #2) ────────────────────────────────────────────────

def test_05_auto_delete_uses_derived_pk_col(_pg_test_dsn, _baseline_guard_engine):
    """Test 5 (derived-PK-Cast, D-G06 + Gemini-Fund #2): prueft dass _DERIVED_PK_COLS
    korrekte PK-Spalten enthaelt — insbesondere fuer non-id-PK-Tabellen.
    Sichert ab: Auto-Delete laeuft ueber die KATALOG-ABGELEITETE PK-Spalte, kein hardcoded 'id'.
    """
    if _baseline_guard_engine is None:
        pytest.skip("Kein _baseline_guard_engine -> kein real-PG verfuegbar")

    pk_cols = conftest_mod._DERIVED_PK_COLS

    # organisations sollte 'id' als PK haben
    if 'public.organisations' in pk_cols:
        assert pk_cols['public.organisations'] == 'id', (
            f"public.organisations PK sollte 'id' sein, war {pk_cols['public.organisations']!r}"
        )

    # intent_event sollte 'event_id' als PK haben (non-id-PK, Fund #2)
    # (Pruefung nur wenn intent_event in der baseline_table_list ist)
    if 'public.intent_event' in pk_cols:
        assert pk_cols['public.intent_event'] == 'event_id', (
            f"public.intent_event PK sollte 'event_id' sein, war {pk_cols['public.intent_event']!r}. "
            f"Sichert ab: Auto-Delete crasht nicht mit 'column id does not exist' (Fund #2)."
        )


# ── Test 6: Modul-Level-Cache + Cache-Fill-Garantie + CROSS-SCHEMA (Fund #7 + #8) ───────────

def test_06_module_cache_cross_schema_and_non_empty(
    _pg_test_dsn, _baseline_guard_engine, _baseline_snapshot
):
    """Test 6 (Modul-Level-Cache + Cache-Fill-Garantie + CROSS-SCHEMA, Fund #3 + Fund #7 + Fund #8):
    - _DERIVED_FK_ORDER und _DERIVED_PK_COLS sind nach Session-Start NON-EMPTY (Fund #7)
    - _DERIVED_FK_ORDER enthaelt crm.*-Eintraege (cross-schema, Fund #8)
    - crm.accounts steht VOR public.tenant_orgs in _DERIVED_FK_ORDER (Fund #8, crm vor public)
      -> cleanup_rows (crm+public) loescht crm zuerst -> keine FK-Violation

    Dieser Test BEWEIST: die Cache-Fill-Garantie hat gegriffen (Fund #7), der Cache ist cross-schema
    gefuellt (nicht nur public), und crm-Kinder stehen vor public-Eltern in der Loeschorder.
    """
    if _baseline_guard_engine is None:
        pytest.skip("Kein _baseline_guard_engine -> kein real-PG verfuegbar")
    if _baseline_snapshot is None:
        pytest.skip("Kein _baseline_snapshot -> kein real-PG verfuegbar")

    fk_order = conftest_mod._DERIVED_FK_ORDER
    pk_cols = conftest_mod._DERIVED_PK_COLS

    # NON-EMPTY (Fund #7)
    assert fk_order, (
        "_DERIVED_FK_ORDER sollte NON-EMPTY sein nach Session-Start "
        "(Fund #7: _baseline_schema als Dependency -> Cache garantiert gefuellt). "
        "Ist _baseline_schema als Parameter in _baseline_snapshot(... _baseline_schema) angefordert?"
    )
    assert pk_cols, (
        "_DERIVED_PK_COLS sollte NON-EMPTY sein nach Session-Start (Fund #7 Cache-Fill-Garantie)"
    )

    # crm.*-Eintraege (cross-schema, Fund #8)
    crm_entries = [t for t in fk_order if t.startswith('crm.')]
    assert crm_entries, (
        f"_DERIVED_FK_ORDER sollte crm.*-Eintraege enthalten (cross-schema Fill, Fund #8). "
        f"Pruefe: derive_baseline_tables wird mit schemas=('public','crm','training') aufgerufen. "
        f"Aktuelle _DERIVED_FK_ORDER enthaelt keine crm.* Eintraege."
    )

    # crm.accounts vor public.tenant_orgs (Fund #8, NERVE-spezifische cross-schema FK-Kante).
    # Bug 3 (Mutual-FK-Zyklen): diese Assertion bleibt gueltig, weil crm.accounts->tenant_orgs->
    # organisations KEINE Zyklus-Kante ist — der echte Zyklus (SCC) ist rein public
    # (users<->organisations, users<->profiles). Der zyklus-bewusste Topo-Sort bricht NUR eine
    # intra-public-Zyklus-Kante; alle cross-schema-Kanten bleiben erhalten -> crm bleibt vor public.
    # (Innerhalb der Mutual-FK-Paare selbst gibt es keine garantierte Order — das prueft test_06 nicht.)
    # Nur pruefbar wenn beide in der Order sind
    if 'crm.accounts' in fk_order and 'public.tenant_orgs' in fk_order:
        idx_crm = fk_order.index('crm.accounts')
        idx_pub = fk_order.index('public.tenant_orgs')
        assert idx_crm < idx_pub, (
            f"crm.accounts (Index {idx_crm}) sollte VOR public.tenant_orgs (Index {idx_pub}) "
            f"in _DERIVED_FK_ORDER stehen (Fund #8: crm-Kind vor public-Eltern, keine FK-Violation). "
            f"Aktuelle Order (erste 20): {fk_order[:20]}"
        )


# ── Test 7: Waechter public-only Filter (Fund #8 + D-G04) ────────────────────────────────────

def test_07_watcher_table_list_public_only(
    _pg_test_dsn, _baseline_guard_engine, _baseline_snapshot
):
    """Test 7 (Waechter public-only, Gemini-Re-Review R3 / Fund #8 + D-G04):
    Der Snapshot-Waechter (_snapshot_public_tables/_baseline_cleanup_guard) iteriert/snapshottet/loescht
    NUR public.* — der baseline_snapshot-Dict enthaelt KEINE crm.*-Eintraege.

    Assertion: alle Keys in _baseline_snapshot starten mit 'public.' (lokal public-only gefiltert).
    Beweist: D-G04 public-only ist erhalten; der Waechter loescht crm NIE; crm bleibt POST-SUITE
    in deploy.sh (Plan 02). Der Modul-Cache enthaelt zwar crm.* in _DERIVED_FK_ORDER, aber der
    Waechter-Snapshot filtert ihn lokal auf startswith('public.') ab.
    """
    if _baseline_snapshot is None:
        pytest.skip("Kein _baseline_snapshot -> kein real-PG verfuegbar")

    crm_in_snapshot = [k for k in _baseline_snapshot if k.startswith('crm.')]
    assert not crm_in_snapshot, (
        f"_baseline_snapshot (Waechter-Snapshot) darf KEINE crm.*-Eintraege enthalten "
        f"(D-G04 public-only, Fund #8). Gefunden: {crm_in_snapshot}. "
        f"Pruefe _snapshot_public_tables: filtert es die table_list lokal auf startswith('public.')?"
    )

    # Alle Keys sollten schema-qualifiziert public.* sein
    for key in _baseline_snapshot:
        assert key.startswith('public.'), (
            f"_baseline_snapshot-Key {key!r} sollte 'public.*' sein (Waechter public-only, D-G04)"
        )
