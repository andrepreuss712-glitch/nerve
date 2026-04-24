"""
tests/test_tabu_migration.py
────────────────────────────────────────────────────────────────────
TDD RED phase: Tests for services/profile_migration.py

Tests per plan Task 1 behavior spec:
  - test_migrate_strings_to_objects
  - test_migrate_preserves_objects
  - test_migrate_empty_seeds_defaults
  - test_migrate_missing_key_seeds_defaults
  - test_migrate_idempotent
  - test_migrate_mixed
"""
import pytest


def test_migrate_strings_to_objects():
    """List of strings → list of objects with empty alternative."""
    from services.profile_migration import migrate_tabu_begriffe
    daten = {'basis': {'tabu_begriffe': ['Kosten', 'Problem']}}
    result = migrate_tabu_begriffe(daten)
    tabu = result['basis']['tabu_begriffe']
    assert tabu == [
        {'begriff': 'Kosten', 'alternative': ''},
        {'begriff': 'Problem', 'alternative': ''},
    ]


def test_migrate_preserves_objects():
    """Already-object shape passes through unchanged."""
    from services.profile_migration import migrate_tabu_begriffe
    original = [{'begriff': 'Kosten', 'alternative': 'Investition'}]
    daten = {'basis': {'tabu_begriffe': original}}
    result = migrate_tabu_begriffe(daten)
    tabu = result['basis']['tabu_begriffe']
    assert tabu == [{'begriff': 'Kosten', 'alternative': 'Investition'}]


def test_migrate_empty_seeds_defaults():
    """Empty list → 13 default pairs seeded."""
    from services.profile_migration import migrate_tabu_begriffe, TABU_DEFAULT_PAIRS
    daten = {'basis': {'tabu_begriffe': []}}
    result = migrate_tabu_begriffe(daten)
    tabu = result['basis']['tabu_begriffe']
    assert len(tabu) == 13
    assert len(tabu) == len(TABU_DEFAULT_PAIRS)
    # Check first pair
    assert tabu[0]['begriff'] == TABU_DEFAULT_PAIRS[0][0]
    assert tabu[0]['alternative'] == TABU_DEFAULT_PAIRS[0][1]


def test_migrate_missing_key_seeds_defaults():
    """daten without basis.tabu_begriffe → 13 defaults."""
    from services.profile_migration import migrate_tabu_begriffe, TABU_DEFAULT_PAIRS
    # Case 1: no basis key at all
    daten_no_basis = {}
    result = migrate_tabu_begriffe(daten_no_basis)
    tabu = result['basis']['tabu_begriffe']
    assert len(tabu) == 13

    # Case 2: basis exists but no tabu_begriffe key
    daten_no_tabu = {'basis': {'unternehmen': 'Test GmbH'}}
    result2 = migrate_tabu_begriffe(daten_no_tabu)
    tabu2 = result2['basis']['tabu_begriffe']
    assert len(tabu2) == 13


def test_migrate_idempotent():
    """Running twice yields same result as once."""
    from services.profile_migration import migrate_tabu_begriffe
    daten = {'basis': {'tabu_begriffe': ['Kosten', 'Problem']}}
    result_once = migrate_tabu_begriffe(daten)
    # Run again on the mutated dict
    result_twice = migrate_tabu_begriffe(result_once)
    assert result_once['basis']['tabu_begriffe'] == result_twice['basis']['tabu_begriffe']


def test_migrate_mixed():
    """Mixed list (string + object) → both normalized to object form."""
    from services.profile_migration import migrate_tabu_begriffe
    daten = {'basis': {'tabu_begriffe': ['Kosten', {'begriff': 'X', 'alternative': 'Y'}]}}
    result = migrate_tabu_begriffe(daten)
    tabu = result['basis']['tabu_begriffe']
    assert len(tabu) == 2
    assert tabu[0] == {'begriff': 'Kosten', 'alternative': ''}
    assert tabu[1] == {'begriff': 'X', 'alternative': 'Y'}
