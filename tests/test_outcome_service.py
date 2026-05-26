"""Phase 08.23.2.D REQ-D-3 + REQ-D-6 — outcome_service Unit-Tests."""
import pytest
from unittest.mock import patch, MagicMock
import json
import statistics


# ── classify() Tests ──────────────────────────────────────────────────────────

@pytest.fixture
def valid_conv_data():
    return {
        'dauer_sekunden': 240,
        'erreichte_phase': 'einwand',
        'einwaende_liste': [{'typ': 'preis', 'intensitaet': 'hoch'}],
        'ewb_clicks': [{'einwand_typ': 'preis', 'success': True}],
        'kb_endwert': 65,
        'log_entries': [
            {'sprecher': 'berater', 'text': 'Guten Tag, ich rufe wegen ...'},
            {'sprecher': 'kunde', 'text': 'Wir haben aktuell keinen Bedarf.'},
            {'sprecher': 'berater', 'text': 'Verstehe — darf ich Ihnen kurz erläutern ...'},
        ],
    }


@pytest.fixture
def mock_haiku_response_meeting():
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps({'outcome': 'meeting_booked', 'confidence': 0.92}))]
    return msg


def test_classify_returns_valid_outcome(valid_conv_data, mock_haiku_response_meeting):
    from services import outcome_service
    with patch.object(outcome_service, 'claude_client') as mock_client:
        mock_client.messages.create.return_value = mock_haiku_response_meeting
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] in ('meeting_booked', 'callback', 'no_interest', 'wrong_person', 'contract_signed', 'unknown')
    assert 0.0 <= result['confidence'] <= 1.0


def test_classify_short_call_returns_null():
    """Edge-Case D-02: Call <30s → outcome=None, confidence=0."""
    from services import outcome_service
    short_call = {'dauer_sekunden': 15, 'erreichte_phase': None, 'einwaende_liste': [], 'ewb_clicks': [], 'kb_endwert': 30, 'log_entries': []}
    result = outcome_service.classify(short_call)
    assert result['outcome'] is None
    assert result['confidence'] == 0.0


def test_classify_handles_claude_exception(valid_conv_data):
    """Bei Claude-Fehler: outcome=None, kein Crash."""
    from services import outcome_service
    with patch.object(outcome_service, 'claude_client') as mock_client:
        mock_client.messages.create.side_effect = RuntimeError('Claude API down')
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] is None
    assert result['confidence'] == 0.0


def test_classify_handles_malformed_json(valid_conv_data):
    """Claude liefert kaputtes JSON → outcome=None, kein Crash."""
    from services import outcome_service
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text='nicht-json-text {{{')]
    with patch.object(outcome_service, 'claude_client') as mock_client:
        mock_client.messages.create.return_value = bad_msg
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] is None
    assert result['confidence'] == 0.0


def test_classify_invalid_outcome_value_rejected(valid_conv_data):
    """Claude liefert outcome außerhalb Enum → outcome=None."""
    from services import outcome_service
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text=json.dumps({'outcome': 'random_value', 'confidence': 0.9}))]
    with patch.object(outcome_service, 'claude_client') as mock_client:
        mock_client.messages.create.return_value = bad_msg
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] is None


# ── calculate_audio_health() Tests ────────────────────────────────────────────

def test_audio_health_5_metrics_present():
    from services.outcome_service import calculate_audio_health
    buf = [(i * 100, 0.9) for i in range(100)]
    m = calculate_audio_health(buf)
    assert 'mean' in m
    assert 'median' in m
    assert 'pct_below_07' in m
    assert 'longest_uncertain_block_s' in m
    assert 'stddev' in m
    assert 'score' in m
    assert 0.0 <= m['score'] <= 1.0


def test_audio_health_empty_buffer_safe():
    from services.outcome_service import calculate_audio_health
    m = calculate_audio_health([])
    assert m['score'] is None or m['score'] == 1.0
    # Kein Crash erwartet


def test_audio_health_high_confidence_high_score():
    from services.outcome_service import calculate_audio_health
    buf = [(i * 100, 0.95) for i in range(200)]
    m = calculate_audio_health(buf)
    assert m['score'] > 0.85
    assert m['pct_below_07'] == 0.0


def test_audio_health_low_confidence_low_score():
    from services.outcome_service import calculate_audio_health
    buf = [(i * 100, 0.3) for i in range(200)]
    m = calculate_audio_health(buf)
    assert m['score'] < 0.5
    assert m['pct_below_07'] == 1.0


def test_audio_health_longest_uncertain_block():
    """Buffer mit 5s schlechtem Block in der Mitte."""
    from services.outcome_service import calculate_audio_health
    buf = []
    # 10s gut
    for i in range(100):
        buf.append((i * 100, 0.9))
    # 5s schlecht (ms 10000-15000)
    for i in range(50):
        buf.append((10000 + i * 100, 0.5))
    # 10s gut
    for i in range(100):
        buf.append((15000 + i * 100, 0.9))
    m = calculate_audio_health(buf)
    assert m['longest_uncertain_block_s'] >= 4.0
