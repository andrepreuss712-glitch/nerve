# -*- coding: utf-8 -*-
"""TAXO2-Plan 02 — D-02 Pflicht-Tests + Proration-/N/A-vs-vergeigt-/N-4-Tests.

Reine deterministische Funktions-Tests (Eingangs-Dicts -> Return-Wert-Assertion) auf
services/rubric_engine.compute_rubric. KEIN DB-Write, KEIN LLM, KEIN Live-Loop -> kein
conftest-cleanup noetig (committet nichts). Runtime-Verhalten (compute_rubric-Return),
KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel).
"""
import pytest

from services.rubric_engine import compute_rubric, MEASURED_WEIGHT_THRESHOLD


# ── Hilfen: Gewichtssaetze + Events bauen ───────────────────────────────────────────────────
def _full_meeting_config():
    """MEETING — alle 7 Dimensionen config-an (weight>0)."""
    return {
        'vorwand_behandlung':  {'weight': 0.25, 'enabled': True, 'confidence_gate': 0.70},
        'aufschub_behandlung': {'weight': 0.15, 'enabled': True, 'confidence_gate': 0.70},
        'kaufsignal_nutzung':  {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70},
        'phasen_technik':      {'weight': 0.15, 'enabled': True, 'confidence_gate': 0.70},
        'fragen_qualitaet':    {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70},
        'gespraechsfuehrung':  {'weight': 0.25, 'enabled': True, 'confidence_gate': 0.70},
        'outcome_progression': {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70},
    }


def _lean_mode_config():
    """Schlanker Modus: nur 2 Dimensionen config-an, kleines Gesamtgewicht (D-02).

    Gesamtgewicht (0.30) ist bewusst < dem Gesamtgewicht des vollen Meeting-Satzes (1.40).
    Beide config-an Dims sind Ereignis-Dims (vorwand/kaufsignal), damit volle Datenlage moeglich.
    """
    return {
        'vorwand_behandlung': {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70},
        'kaufsignal_nutzung': {'weight': 0.10, 'enabled': True, 'confidence_gate': 0.70},
        # die restlichen 5 sind config_off (nicht im Satz) -> reason='config_off'
    }


def _event(intent_type, confidence=0.9, handling_score=3, speaker='berater', text='', phase=None,
           event_id=1):
    return {
        'event_id': event_id,
        'intent_type': intent_type,
        'confidence': confidence,
        'handling_score_numeric': handling_score,
        'phase': phase,
        'text': text,
        'payload_jsonb': {'speaker_role': speaker},
    }


# ── D-02 PFLICHT-TEST 1 ─────────────────────────────────────────────────────────────────────
def test_mode_can_never_score():
    """Ein schlanker Modus (Gesamtgewicht < 50% des globalen Maximums) erzeugt bei VOLLER
    Datenlage fuer SEINE Dimensionen trotzdem einen coaching_score != None.

    Beweist: die <50%-Schwelle rechnet MODUS-relativ (gegen das Modus-Maximum), NICHT gegen die
    vollen 7 — sonst koennte ein schlanker Modus strukturell nie scoren (D-02).
    """
    mode_config = _lean_mode_config()
    # Volle Datenlage fuer die 2 config-an Dims: je >=1 konfidentes Event mit handling_score.
    events = [
        _event('vorwand', confidence=0.95, handling_score=3, event_id=1),
        _event('kaufsignal', confidence=0.95, handling_score=3, event_id=2),
    ]
    call = {'call_mode': 'cold_call', 'outcome': 'meeting_booked', 'dauer_sekunden': 300}

    result = compute_rubric(events, {}, call, mode_config)

    # Modus-relativ messbar = 0.30/0.30 = 100% -> ueber der Schwelle -> ECHTER Score.
    assert result['coaching_score'] is not None, \
        "schlanker Modus mit voller Datenlage muss scoren (D-02 modus-relativ)"
    assert result['measured_weight_pct'] >= MEASURED_WEIGHT_THRESHOLD
    assert result['status'] == 'scored'


# ── D-02 PFLICHT-TEST 2 ─────────────────────────────────────────────────────────────────────
def test_proration_drops_below_mode_threshold():
    """Ein Modus, der durch Proration unter 50% SEINES EIGENEN Maximalgewichts faellt,
    erzeugt korrekt KEINEN Gesamtscore (coaching_score == None).
    """
    mode_config = _full_meeting_config()
    # Nur EIN kleines Ereignis messbar (aufschub, weight 0.15), Rest faellt mangels Daten weg:
    # keine speech_stats (gespraechsfuehrung weg), outcome=None (outcome_progression weg),
    # keine W-Fragen (fragen_qualitaet weg), keine Phase/Dauer (phasen_technik weg),
    # kein vorwand/kaufsignal-Event. messbar = 0.15 / 1.40 = ~0.107 < 0.5.
    events = [
        _event('aufschub', confidence=0.95, handling_score=2, event_id=1),
    ]
    call = {'call_mode': 'meeting_consented', 'outcome': None, 'dauer_sekunden': 5}

    result = compute_rubric(events, {}, call, mode_config)

    assert result['coaching_score'] is None, \
        "unter 50% des Modus-Maximums darf KEIN Gesamtscore erzeugt werden (D-02)"
    assert result['measured_weight_pct'] < MEASURED_WEIGHT_THRESHOLD
    assert result['status'] == 'insufficient_data'


# ── Cold-Call-Renormalisierung: Gespraechsfuehrung nicht messbar -> available=false, renorm ──
def test_cold_call_gespraechsfuehrung_unavailable_renormalizes():
    """Cold-Call mit Einzelsprecher ohne Speech-Stats -> gespraechsfuehrung available=false
    (Proration-Drop, KEIN Fixwert-20, KEIN Dauer-0). Restgewichte renormalisieren.
    """
    mode_config = {
        'vorwand_behandlung':  {'weight': 0.30, 'enabled': True, 'confidence_gate': 0.70,
                                'indirekt_erkannt': True},
        'outcome_progression': {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70},
        'gespraechsfuehrung':  {'weight': 0.20, 'enabled': True, 'confidence_gate': 0.70,
                                'partial_marker': 'sprechdisziplin'},
    }
    events = [_event('vorwand', confidence=0.95, handling_score=3, event_id=1)]
    # speech_stats leer (monolog=0, tempo=0) -> gespraechsfuehrung NICHT messbar im cold_call.
    speech_stats = {'redeanteil': 0, 'tempo': 0, 'monolog': 0}
    call = {'call_mode': 'cold_call', 'outcome': 'meeting_booked', 'dauer_sekunden': 200}

    result = compute_rubric(events, speech_stats, call, mode_config)

    drops = {u['dim']: u['reason'] for u in result['unmeasured_dimensions']}
    assert 'gespraechsfuehrung' in drops, "gespraechsfuehrung muss weggeprorated sein"
    assert drops['gespraechsfuehrung'] in ('na', 'no_data'), \
        "nicht-messbar bei nicht-Abbruch = N/A, KEIN Fixwert"
    # messbar = vorwand(0.30)+outcome(0.20) = 0.50 von 0.70 = ~0.714 >= 0.5 -> scored.
    assert result['coaching_score'] is not None
    # KEINE messbare Dimension wird als 0 gewertet:
    for d in result['dimensions']:
        assert d['score'] in (1, 2, 3)


# ── D-08 N/A-vs-vergeigt: vorzeitiger Abbruch -> KEIN selbstbewusster hoher Score ────────────
def test_aborted_call_no_confident_high_score():
    """Vorzeitig abgebrochener Call (outcome=no_interest + kurze Dauer) -> die nicht erreichten
    Dimensionen zaehlen als 'not_reached' (NEGATIV), NICHT als benigner Proration-Drop. Eine
    isoliert gute Begruessung skaliert NICHT auf einen hohen Gesamtscore (D-08).
    """
    mode_config = _full_meeting_config()
    # Nur eine gute Vorwand-Behandlung frueh, dann legt der Kunde auf:
    events = [_event('vorwand', confidence=0.95, handling_score=3, event_id=1)]
    call = {'call_mode': 'meeting_consented', 'outcome': 'no_interest', 'dauer_sekunden': 12}

    result = compute_rubric(events, {}, call, mode_config)

    reasons = {u['dim']: u['reason'] for u in result['unmeasured_dimensions']}
    # Mindestens eine nicht erreichte Dimension traegt 'not_reached' (vergeigt), nicht 'na'.
    assert 'not_reached' in reasons.values(), \
        "Abbruch-Call muss vergeigte Dimensionen als not_reached markieren (D-08)"
    # Und: kein selbstbewusster hoher Gesamtscore — entweder None (zu wenig Gewicht) ...
    if result['coaching_score'] is not None:
        # ... oder, falls doch ueber Schwelle, dann als vorlaeufig markiert.
        assert result['is_provisional'] is True


def test_no_measurable_dimension_is_ever_zero():
    """Keine messbare Dimension wird je als 0 gewertet — nur available=false ODER score in 1-3."""
    mode_config = _full_meeting_config()
    events = [
        _event('vorwand', confidence=0.95, handling_score=1, event_id=1),
        _event('kaufsignal', confidence=0.95, handling_score=2, event_id=2),
        _event('aufschub', confidence=0.95, handling_score=3, event_id=3),
    ]
    speech_stats = {'redeanteil': 45, 'tempo': 130, 'monolog': 10.0}
    call = {'call_mode': 'meeting_consented', 'outcome': 'callback', 'dauer_sekunden': 240}

    result = compute_rubric(events, speech_stats, call, mode_config)

    for d in result['dimensions']:
        assert d['available'] is True
        assert d['score'] in (1, 2, 3), "messbare Dimension nie 0"


# ── N-4: Modus-Schluessel kommt aus call_mode, NICHT aus einem erfundenen session_mode ──────
def test_mode_key_from_call_mode():
    """Ein Call mit call_mode='meeting_consented' laedt den meeting-Gewichtssatz (Lookup
    NICHT-leer, NICHT alles config_off). Beweist dass der Lookup nicht still leer laeuft (N-4).
    """
    mode_config = _full_meeting_config()
    events = [
        _event('vorwand', confidence=0.95, handling_score=3, event_id=1),
        _event('kaufsignal', confidence=0.95, handling_score=3, event_id=2),
    ]
    speech_stats = {'redeanteil': 45, 'tempo': 130, 'monolog': 8.0}
    call = {'call_mode': 'meeting_consented', 'outcome': 'meeting_booked', 'dauer_sekunden': 300}

    result = compute_rubric(events, speech_stats, call, mode_config)

    # mode_key aus call.call_mode abgeleitet (kein erfundenes session_mode).
    assert result['mode_key'] == 'meeting_consented'
    # Lookup nicht-leer: NICHT alle Dimensionen config_off, Status nicht no_weight_set.
    assert result['status'] != 'no_weight_set'
    config_off = [u for u in result['unmeasured_dimensions'] if u['reason'] == 'config_off']
    assert len(config_off) < 7, "ein gueltiger Modus-Lookup darf nicht alles config_off liefern"
    assert len(result['dimensions']) >= 1, "mindestens eine messbare Dimension"


def test_empty_mode_config_leaves_trace_not_silent_null():
    """Leerer mode_config-Lookup (unbekannter Modus) -> status='no_weight_set' mit Spur,
    NICHT still 0/NULL ohne Trace (N-4 Schutz)."""
    call = {'call_mode': 'unbekannter_modus', 'outcome': 'meeting_booked', 'dauer_sekunden': 100}
    result = compute_rubric([], {}, call, mode_config={})

    assert result['coaching_score'] is None
    assert result['status'] == 'no_weight_set'
    assert result['mode_key'] == 'unbekannter_modus'
    # Spur vorhanden: alle Dimensionen als config_off gelistet (nicht still verschluckt).
    assert len(result['unmeasured_dimensions']) == 7
