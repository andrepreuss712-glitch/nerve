"""Hysterese-Tests (Phase 08.23.2.C Req-3).

Runtime-Behavior-Tests — pruefen apply_hysteresis() State-Mutation und Return-Wert.
Kein inspect.getsource() / Source-Presence (CLAUDE.md Verbot).
"""
import time

import pytest

from services.gatekeeper import apply_hysteresis
from config.phase_transitions import HYSTERESIS_REQUIRED_HINTS


def _fresh_state(mode='cold_call', current_phase='opener', age_seconds=0):
    return {
        'current_phase': current_phase,
        'phase_hint_count': 0,
        'pending_phase': None,
        'phase_entered_at': time.monotonic() - age_seconds,
    }


def test_single_hint_does_not_switch():
    state = _fresh_state(current_phase='opener', age_seconds=10)
    result = apply_hysteresis(state, 'permission', 'cold_call')
    assert result is None
    assert state['phase_hint_count'] == 1
    assert state['pending_phase'] == 'permission'
    assert state['current_phase'] == 'opener'


def test_two_hints_switches_when_dwell_met():
    # opener->permission: opener-min-dwell=5s. Alter: 10s -> dwell ok.
    state = _fresh_state(current_phase='opener', age_seconds=10)
    apply_hysteresis(state, 'permission', 'cold_call')   # hint 1
    result = apply_hysteresis(state, 'permission', 'cold_call')  # hint 2
    assert result == 'permission'
    assert state['current_phase'] == 'permission'
    assert state['phase_hint_count'] == 0  # reset nach Wechsel
    assert state['pending_phase'] is None


def test_two_hints_blocked_by_dwell():
    # opener-min-dwell=5s. Age: 1s -> dwell zu kurz.
    state = _fresh_state(current_phase='opener', age_seconds=1)
    apply_hysteresis(state, 'permission', 'cold_call')
    result = apply_hysteresis(state, 'permission', 'cold_call')
    assert result is None
    assert state['current_phase'] == 'opener'


def test_forbidden_transition_rejected():
    # gatekeeper-Modus: handoff -> greeting ist FORBIDDEN
    state = _fresh_state(mode='gatekeeper', current_phase='handoff', age_seconds=100)
    apply_hysteresis(state, 'greeting', 'gatekeeper')
    result = apply_hysteresis(state, 'greeting', 'gatekeeper')
    assert result is None
    assert state['current_phase'] == 'handoff'


def test_allowed_backward_transition():
    # cold_call: closing -> discovery ist ALLOWED (Einwand-Recovery)
    state = _fresh_state(current_phase='closing', age_seconds=100)
    apply_hysteresis(state, 'discovery', 'cold_call')
    result = apply_hysteresis(state, 'discovery', 'cold_call')
    assert result == 'discovery'


def test_same_phase_resets_hint_count():
    state = _fresh_state(current_phase='opener', age_seconds=10)
    state['phase_hint_count'] = 5
    state['pending_phase'] = 'permission'
    apply_hysteresis(state, 'opener', 'cold_call')
    assert state['phase_hint_count'] == 0
    assert state['pending_phase'] is None


def test_changing_proposed_phase_resets_hint_count():
    state = _fresh_state(current_phase='opener', age_seconds=10)
    apply_hysteresis(state, 'permission', 'cold_call')  # hint 1 for permission
    result = apply_hysteresis(state, 'reason', 'cold_call')  # neuer Vorschlag
    assert result is None
    assert state['phase_hint_count'] == 1
    assert state['pending_phase'] == 'reason'


def test_hysteresis_required_hints_constant_is_two():
    assert HYSTERESIS_REQUIRED_HINTS == 2
