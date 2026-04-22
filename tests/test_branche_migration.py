"""Phase 08 tests for scripts/migrate_branche_to_enum.py heuristic + fallback.

Pure-function-Tests auf den 3 Hilfsfunktionen (_normalize_branche,
_map_branche_to_enum, _migrate_profile_branche). Keine DB-Fixtures noetig.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.migrate_branche_to_enum import (  # noqa: E402
    _map_branche_to_enum,
    _migrate_profile_branche,
    _normalize_branche,
    HEURISTIC_MAP,
    VALID_ENUMS,
)


# ── Normalisierung ──────────────────────────────────────────────────────────

def test_normalize_umlaute():
    # Direkter ASCII-Eingang (schon normalisiert) bleibt identisch:
    assert _normalize_branche('Grundstueck') == 'grundstueck'
    # Unicode ae/oe/ue/ss werden ersetzt:
    assert _normalize_branche('Gr\u00fcndst\u00fcck') == 'gruendstueck'
    assert _normalize_branche('F\u00fcr Unternehmen') == 'fuer unternehmen'
    assert _normalize_branche('Weiberma\u00dfnahme') == 'weibermassnahme'
    assert _normalize_branche('  TRIM  ') == 'trim'


def test_normalize_empty():
    assert _normalize_branche('') == ''
    assert _normalize_branche(None) == ''


# ── Heuristik-Mapping ────────────────────────────────────────────────────────

def test_heuristic_saas_b2b():
    assert _map_branche_to_enum('SaaS-Plattform B2B') == 'saas_b2b'
    assert _map_branche_to_enum('cloud software') == 'saas_b2b'


def test_heuristic_maschinenbau():
    assert _map_branche_to_enum('Werkzeugmaschinen') == 'maschinenbau'
    assert _map_branche_to_enum('Maschinenbau Mittelstand') == 'maschinenbau'
    assert _map_branche_to_enum('Anlagenbau') == 'maschinenbau'


def test_heuristic_versicherung_vor_finanz():
    """'Industrieversicherung' darf nicht als finanzprodukte klassifiziert werden."""
    assert _map_branche_to_enum('Industrieversicherung') == 'versicherung'
    assert _map_branche_to_enum('Versicherungsmakler') == 'versicherung'


def test_heuristic_finanzberatung_prio():
    """'Finanzberatung' ist finanzprodukte (nicht beratung)."""
    assert _map_branche_to_enum('Finanzberatung') == 'finanzprodukte'


def test_heuristic_immobilien():
    assert _map_branche_to_enum('Immobilienmakler') == 'immobilien'
    assert _map_branche_to_enum('Grundstueckshandel') == 'immobilien'


def test_heuristic_coaching():
    assert _map_branche_to_enum('Performance-Coach') == 'coaching'
    assert _map_branche_to_enum('Coaching') == 'coaching'


def test_heuristic_beratung_ohne_finanz():
    """Reine 'Beratung' ohne finanz-Keyword → beratung."""
    assert _map_branche_to_enum('Unternehmensberatung') == 'beratung'


def test_heuristic_fallback_sonstiges():
    assert _map_branche_to_enum('Exotisches Feld') == 'sonstiges'
    assert _map_branche_to_enum('') == 'sonstiges'
    assert _map_branche_to_enum(None) == 'sonstiges'


def test_idempotent_already_enum():
    """Wenn branche bereits Enum-Wert: kein Remap."""
    assert _map_branche_to_enum('saas_b2b') == 'saas_b2b'
    assert _map_branche_to_enum('maschinenbau') == 'maschinenbau'
    assert _map_branche_to_enum('sonstiges') == 'sonstiges'


# ── _migrate_profile_branche ────────────────────────────────────────────────

def test_migrate_preserves_originaltext_in_branche_kontext():
    daten = {'basis': {}}
    enum_val, out = _migrate_profile_branche(1, 'Exotisches Feld', daten)
    assert enum_val == 'sonstiges'
    assert out['basis']['branche_kontext'] == 'Exotisches Feld'


def test_migrate_appends_to_existing_branche_kontext():
    """Wenn branche_kontext schon belegt: append mit ' | ' separator, kein Overwrite."""
    daten = {'basis': {'branche_kontext': 'Bestehender Text'}}
    enum_val, out = _migrate_profile_branche(1, 'Neuer Freitext', daten)
    assert 'Bestehender Text' in out['basis']['branche_kontext']
    assert 'Neuer Freitext' in out['basis']['branche_kontext']
    assert '|' in out['basis']['branche_kontext']


def test_migrate_skips_if_already_enum():
    daten = {'basis': {'branche_kontext': 'Some context'}}
    enum_val, out = _migrate_profile_branche(1, 'saas_b2b', daten)
    assert enum_val == 'saas_b2b'
    # daten unveraendert
    assert out['basis']['branche_kontext'] == 'Some context'


# ── Struktur-Tests ────────────────────────────────────────────────────────────

def test_valid_enums_contains_all_expected():
    """Alle 8 Enums aus RESEARCH Focus Area 7 sind definiert."""
    expected = {
        'saas_b2b', 'maschinenbau', 'versicherung', 'finanzprodukte',
        'immobilien', 'coaching', 'beratung', 'sonstiges',
    }
    assert expected == VALID_ENUMS


def test_heuristic_map_preserves_versicherung_before_finanz():
    """Priority-Reihenfolge: versicherung muss VOR finanzprodukte stehen."""
    enums_in_order = [e for e, _ in HEURISTIC_MAP]
    idx_versicherung = enums_in_order.index('versicherung')
    idx_finanz = enums_in_order.index('finanzprodukte')
    assert idx_versicherung < idx_finanz, \
        'versicherung muss vor finanzprodukte im Heuristik-Map stehen'
