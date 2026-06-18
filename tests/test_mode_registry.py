"""
tests/test_mode_registry.py
────────────────────────────────────────────────────────────────────
TAXO1-07 (REQ 6): Struktur-/Runtime-Test der ModeStrategy-Registry.

Alle Assertionen pruefen RUNTIME-Verhalten (Registry-Inhalt + extract_intent-
Rueckgaben) — KEIN Source-Presence (kein Quell-Code-Lesen/Grep auf die Datei).
Die eine hasattr-Assertion (test_abc_has_no_classification_prompt) prueft die
KLASSEN-SCHNITTSTELLE zur Laufzeit (Decision 1), nicht Code-Existenz — sie ist
laut CLAUDE.md-Test-Qualitaets-Regel eine valide Runtime-API-Assertion.

Cleanup-Regel (Phase 08.23.2.PGTEST): N/A — diese Tests sind rein in-memory,
KEIN nerve_test-Commit, also keine Rows zu raeumen.
"""

import pytest

from services.mode_strategy import (
    MODE_REGISTRY,
    ModeStrategy,
    ColdCallStrategy,
    register,
    COLD_CALL_CONF_CAP,
)


def test_cold_call_and_meeting_registered():
    # Runtime-Registry-Inhalt: beide echten Modi sind registrierte Instanzen.
    assert 'cold_call' in MODE_REGISTRY
    assert 'meeting' in MODE_REGISTRY
    assert isinstance(MODE_REGISTRY['cold_call'], ModeStrategy)
    assert isinstance(MODE_REGISTRY['meeting'], ModeStrategy)


def test_new_mode_registers_without_core_change():
    # Neuer Modus = neue Klasse via register() — Kern-Eintraege unveraendert.
    _cold_before = MODE_REGISTRY['cold_call']
    _meeting_before = MODE_REGISTRY['meeting']

    @register('x_test')
    class _XTestStrategy(ModeStrategy):
        def setup_audio_routes(self):
            return {'diarize': False, 'audible': ['berater']}

        def extract_intent(self, *, speaker=None, ergebnis=None, **ctx):
            return {'speaker_role': 'berater', 'speaker_id': 'local',
                    'inference_basis': 'advisor_paraphrase', 'confidence': 0.5}

    try:
        assert 'x_test' in MODE_REGISTRY
        assert isinstance(MODE_REGISTRY['x_test'], ModeStrategy)
        # Kern-Eintraege wurden NICHT angefasst (kein Kern-Code-Aenderung noetig).
        assert MODE_REGISTRY['cold_call'] is _cold_before
        assert MODE_REGISTRY['meeting'] is _meeting_before
    finally:
        MODE_REGISTRY.pop('x_test', None)


def test_cold_call_speaker_is_berater():
    # DER Bug-Fix-Beweis (Decision 2): cold_call attribuiert als Berater, NICHT Kunde.
    attr = MODE_REGISTRY['cold_call'].extract_intent(speaker=None, confidence=0.7)
    assert attr['speaker_role'] == 'berater'
    assert attr['speaker_id'] == 'local'
    assert attr['inference_basis'] == 'advisor_paraphrase'


def test_cold_call_confidence_capped():
    # cold_call ist haerter gecapped (Berater-Paraphrase ist Inferenz, nicht direkte Aussage).
    attr = MODE_REGISTRY['cold_call'].extract_intent(speaker=None, confidence=0.99)
    assert attr['confidence'] <= COLD_CALL_CONF_CAP


def test_meeting_speaker_separation():
    # meeting folgt der Diarization: 0 -> berater, 1 -> kunde.
    attr0 = MODE_REGISTRY['meeting'].extract_intent(speaker=0)
    attr1 = MODE_REGISTRY['meeting'].extract_intent(speaker=1)
    assert attr0['speaker_role'] == 'berater'
    assert attr1['speaker_role'] == 'kunde'
    assert attr1['inference_basis'] == 'direct_customer_utterance'


def test_future_slots_raise_not_implemented():
    # Die 3 Steckplaetze sind aufnahmefaehig, aber noch nicht ausgebaut.
    for k in ('meeting_ext', 'training_cold', 'training_meeting'):
        assert k in MODE_REGISTRY
        with pytest.raises(NotImplementedError):
            MODE_REGISTRY[k].extract_intent(speaker=None)


def test_abc_has_no_classification_prompt():
    # Decision 1 (Runtime-API-Assertion, KEIN Source-Presence-Schutz): die ABC darf
    # KEINE Klassifikations-Prompt-Methode exponieren — SYSTEM_PROMPT_BASE
    # (claude_service.py:32, MEDFIX) ist der EINE Prompt. Wuerde diese Methode
    # eingefuehrt, re-braeche der MEDFIX (intent_event wieder leer). hasattr prueft
    # hier die Klassen-SCHNITTSTELLE zur Laufzeit, nicht ob Code existiert.
    assert not hasattr(ModeStrategy, 'get_classification_prompt')
    assert not hasattr(ColdCallStrategy, 'get_classification_prompt')
