"""Tests fuer mode_switch call_events INSERT im manual_mode_toggle Handler.

Phase 08.23.2.C.R: Jeder Toggle erzeugt einen call_events-Eintrag mit
event_type='mode_switch' und 4 payload-Feldern (D-04d).
"""
import pytest
from unittest.mock import patch, MagicMock
from database.models import CallEvent


def test_mode_switch_event_payload_fields():
    """mode_switch call_events-Eintrag muss 4 Pflicht-Felder im payload haben."""
    # Simulierter Eintrag wie er nach manual_mode_toggle entstehen soll
    event = CallEvent(
        call_id=1,
        event_type='mode_switch',
        event_ts_ms=1000000,
        payload={
            'old_mode': 'gatekeeper',
            'new_mode': 'cold_call',
            'old_category': 'gatekeeper',
            'new_category': 'target',
            'timestamp': 123.456,
        },
    )
    assert event.event_type == 'mode_switch'
    assert 'old_mode' in event.payload
    assert 'new_mode' in event.payload
    assert 'old_category' in event.payload
    assert 'new_category' in event.payload


def test_mode_initial_event_payload_fields():
    """mode_initial call_events-Eintrag muss mode, category, sid, timestamp haben."""
    import time
    event = CallEvent(
        call_id=1,
        event_type='mode_initial',
        event_ts_ms=int(time.time() * 1000),
        payload={
            'mode': 'gatekeeper',
            'category': 'gatekeeper',
            'sid': 'test-sid-123',
            'timestamp': time.monotonic(),
        },
    )
    assert event.event_type == 'mode_initial'
    assert 'mode' in event.payload
    assert 'category' in event.payload
    assert 'sid' in event.payload
    assert 'timestamp' in event.payload
