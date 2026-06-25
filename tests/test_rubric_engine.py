# -*- coding: utf-8 -*-
"""TAXO2-Plan 02 — Engine-Aufschluesselungs-Form-Tests (Req 5) + Dimensions-Daten-Invarianten.

Reine deterministische Funktions-Tests auf services/rubric_engine.compute_rubric +
services/rubric_dimensions.DIMENSIONS. Runtime-Verhalten (Return-Form/Werte), kein
Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel). committet nichts -> kein cleanup.
"""
import pytest

from services.rubric_engine import compute_rubric
from services.rubric_dimensions import DIMENSIONS


def _event(intent_type, confidence=0.9, handling_score=3, event_id=1):
    return {
        'event_id': event_id,
        'intent_type': intent_type,
        'confidence': confidence,
        'handling_score_numeric': handling_score,
        'payload_jsonb': {'speaker_role': 'berater'},
    }


def _full_config():
    return {k: {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70} for k in DIMENSIONS}


# ── DIMENSIONS-Daten-Invarianten (D-05 / Geruest §4) ────────────────────────────────────────
def test_dimensions_has_seven():
    assert len(DIMENSIONS) == 7


def test_each_dimension_has_three_bars():
    for key, d in DIMENSIONS.items():
        assert set(d['bars'].keys()) == {1, 2, 3}, f"{key} muss genau 3 BARS-Stufen haben"
        for stufe, text in d['bars'].items():
            assert isinstance(text, str) and len(text) > 0


def test_each_dimension_is_callable():
    for key, d in DIMENSIONS.items():
        assert callable(d['is_measurable']), f"{key} braucht is_measurable"
        assert callable(d['score']), f"{key} braucht score"


def test_dimension_keys_are_ascii():
    for key in DIMENSIONS:
        assert key.isascii(), f"Dimensions-Key {key} muss ASCII sein (Code-Identifier)"


# ── Aufschluesselungs-Form (Req 5) ──────────────────────────────────────────────────────────
def test_breakdown_shape_full_data():
    mode_config = _full_config()
    events = [
        _event('vorwand', event_id=1),
        _event('kaufsignal', event_id=2),
        _event('aufschub', event_id=3),
    ]
    speech_stats = {'redeanteil': 45, 'tempo': 130, 'monolog': 8.0}
    call = {'call_mode': 'meeting_consented', 'outcome': 'meeting_booked', 'dauer_sekunden': 300}

    result = compute_rubric(events, speech_stats, call, mode_config)

    # Top-Level-Schluessel (Req 5 / D-08-Schema).
    for k in ('coaching_score', 'dimensions', 'is_provisional', 'measured_weight_pct',
              'unmeasured_dimensions', 'status', 'mode_key'):
        assert k in result, f"Aufschluesselung muss '{k}' tragen"

    # Pro messbare Dimension die volle Aufschluesselung.
    for d in result['dimensions']:
        for k in ('dim', 'label', 'score', 'weight', 'available', 'sample_size',
                  'beleg_ref', 'marker'):
            assert k in d, f"Dimensions-Eintrag muss '{k}' tragen"
        assert d['available'] is True
        assert d['score'] in (1, 2, 3)
        assert isinstance(d['marker'], list)


def test_unmeasured_reasons_are_separated():
    """unmeasured_dimensions traegt getrennte reasons: config_off vs no_data/na/not_reached
    (D-01 config-aus vs D-08 Daten-Gruende SAUBER getrennt)."""
    mode_config = {
        'vorwand_behandlung': {'weight': 0.40, 'enabled': True, 'confidence_gate': 0.70},
        'kaufsignal_nutzung': {'weight': 0.40, 'enabled': True, 'confidence_gate': 0.70},
        # die restlichen 5 sind config_off.
    }
    # vorwand messbar, kaufsignal NICHT (kein Event) -> getrennte Gruende.
    events = [_event('vorwand', event_id=1)]
    call = {'call_mode': 'cold_call', 'outcome': 'meeting_booked', 'dauer_sekunden': 200}

    result = compute_rubric(events, {}, call, mode_config)

    reasons = {u['dim']: u['reason'] for u in result['unmeasured_dimensions']}
    # 5 nicht im Satz -> config_off.
    assert reasons.get('phasen_technik') == 'config_off'
    assert reasons.get('fragen_qualitaet') == 'config_off'
    # kaufsignal im Satz, aber keine Daten -> na (kein Abbruch).
    assert reasons.get('kaufsignal_nutzung') in ('na', 'no_data')


def test_indirekt_marker_present_for_cold_call():
    """KALTAKQUISE-indirekt-erkannte Dims tragen '(indirekt erkannt)'-Marker (D-04)."""
    mode_config = {
        'vorwand_behandlung': {'weight': 0.60, 'enabled': True, 'confidence_gate': 0.70,
                               'indirekt_erkannt': True},
        'abschluss_fuehrung': {'weight': 0.40, 'enabled': True, 'confidence_gate': 0.70},
    }
    events = [_event('vorwand', event_id=1)]
    call = {'call_mode': 'cold_call', 'outcome': 'meeting_booked', 'dauer_sekunden': 200}

    result = compute_rubric(events, {}, call, mode_config)

    vorwand = next(d for d in result['dimensions'] if d['dim'] == 'vorwand_behandlung')
    assert '(indirekt erkannt)' in vorwand['marker']


def test_beleg_ref_is_event_reference_not_text():
    """beleg_ref = Verweis auf intent_event (event_id), KEIN freier Text (Req 5)."""
    mode_config = {
        'vorwand_behandlung': {'weight': 0.60, 'enabled': True, 'confidence_gate': 0.70},
        'abschluss_fuehrung': {'weight': 0.40, 'enabled': True, 'confidence_gate': 0.70},
    }
    events = [_event('vorwand', event_id=42)]
    call = {'call_mode': 'cold_call', 'outcome': 'meeting_booked', 'dauer_sekunden': 200}

    result = compute_rubric(events, {}, call, mode_config)

    vorwand = next(d for d in result['dimensions'] if d['dim'] == 'vorwand_behandlung')
    assert vorwand['beleg_ref'] == {'intent_event_id': 42}
    assert vorwand['sample_size'] == 1
