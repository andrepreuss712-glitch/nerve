"""Phase 08.23.2.D REQ-D-7 - Word-Confidence-Buffer + Hysterese-Tests."""
import pytest
from unittest.mock import patch
from services.deepgram_service import (
    _rolling_10s_score,
    _AUDIO_WARN_TRIGGER_BELOW,
    _AUDIO_WARN_RESET_ABOVE,
    _ROLLING_WINDOW_MS,
)
import services.live_session as ls


def test_rolling_score_empty_buffer():
    assert _rolling_10s_score([], 10_000) == 1.0


def test_rolling_score_all_outside_window():
    buf = [(0, 0.5), (1000, 0.5)]
    # now=20_000ms -> beide Tuples sind > 10s alt -> recent leer -> 1.0
    assert _rolling_10s_score(buf, 20_000) == 1.0


def test_rolling_score_mean_within_window():
    buf = [(8_000, 0.8), (9_000, 0.6)]
    assert abs(_rolling_10s_score(buf, 10_000) - 0.7) < 1e-9


def test_rolling_score_partial_window():
    # 5_000 ist gerade innerhalb 10s (cutoff = 5_000), 4_999 nicht
    buf = [(4_999, 0.2), (5_000, 0.9), (9_000, 0.9)]
    score = _rolling_10s_score(buf, 15_000)
    # cutoff = 15_000 - 10_000 = 5_000; (5_000, 0.9) ist >=, (4_999) nicht
    # recent = [0.9, 0.9] -> 0.9
    assert abs(score - 0.9) < 1e-9


def test_hysterese_thresholds_constants():
    assert _AUDIO_WARN_TRIGGER_BELOW == 0.70
    assert _AUDIO_WARN_RESET_ABOVE == 0.80
    assert _ROLLING_WINDOW_MS == 10_000


def test_session_state_buffer_isolation():
    """REQ-D-7 Acceptance: Buffer-Reset bei pop_session_state."""
    ls.init_session_state('s1', user_id=1, org_id=1)
    ls._session_state['s1']['word_confidences'].append((100, 0.5))
    assert len(ls._session_state['s1']['word_confidences']) == 1
    ls.pop_session_state('s1')
    assert 's1' not in ls._session_state
    # Neu-Init -> leer (kein Carry-Over)
    ls.init_session_state('s1', user_id=1, org_id=1)
    assert ls._session_state['s1']['word_confidences'] == []
    ls.pop_session_state('s1')


def test_hysterese_emits_once_then_resets():
    """Simuliert Hysterese-Flow via direkter State-Manipulation:
       low -> emit-flag, low again -> no emit, high -> reset, low -> emit-flag again.
    """
    ls.init_session_state('s_hys', user_id=1, org_id=1)
    state = ls._session_state['s_hys']['state']
    # Phase 1: kein Warn aktiv, score < 0.70 -> Trigger
    assert state['audio_warn_active'] is False
    # Simuliere Logik aus deepgram_service.py Block (D):
    score = 0.5
    warn_active = state['audio_warn_active']
    if not warn_active and score < _AUDIO_WARN_TRIGGER_BELOW:
        state['audio_warn_active'] = True
        first_emit = True
    else:
        first_emit = False
    assert first_emit is True
    assert state['audio_warn_active'] is True
    # Phase 2: warn aktiv, score wieder 0.5 -> KEIN zweiter Emit
    score = 0.5
    warn_active = state['audio_warn_active']
    second_emit = (not warn_active and score < _AUDIO_WARN_TRIGGER_BELOW)
    assert second_emit is False
    assert state['audio_warn_active'] is True
    # Phase 3: warn aktiv, score 0.9 -> Hysterese reset
    score = 0.9
    warn_active = state['audio_warn_active']
    if warn_active and score > _AUDIO_WARN_RESET_ABOVE:
        state['audio_warn_active'] = False
    assert state['audio_warn_active'] is False
    # Phase 4: warn inactive, score 0.5 -> erneut Trigger erlaubt
    score = 0.5
    warn_active = state['audio_warn_active']
    if not warn_active and score < _AUDIO_WARN_TRIGGER_BELOW:
        state['audio_warn_active'] = True
        fourth_emit = True
    else:
        fourth_emit = False
    assert fourth_emit is True
    ls.pop_session_state('s_hys')
