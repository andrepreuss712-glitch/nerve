"""Phase 08.23.2.D REQ-D-3 + REQ-D-6 + REQ-D.UX-6/7/8 -- outcome_service Unit-Tests."""
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
            {'sprecher': 'berater', 'text': 'Verstehe -- darf ich Ihnen kurz erläutern ...'},
        ],
    }


@pytest.fixture
def mock_haiku_response_meeting():
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps({'outcome': 'meeting_booked', 'confidence': 0.92}))]
    return msg


def test_classify_returns_valid_outcome(valid_conv_data, mock_haiku_response_meeting):
    from services import outcome_service
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        mock_client.messages.create.return_value = mock_haiku_response_meeting
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] in outcome_service.VALID_OUTCOMES
    assert 0.0 <= result['confidence'] <= 1.0


def test_classify_short_call_returns_unknown():
    """Edge-Case REQ-D.UX-6: Call <30s -> outcome='unknown' (not None), confidence=0."""
    from services import outcome_service
    short_call = {'dauer_sekunden': 15, 'erreichte_phase': None, 'einwaende_liste': [], 'kb_endwert': 30, 'log_entries': []}
    result = outcome_service.classify(short_call)
    assert result['outcome'] == 'unknown'
    assert result['confidence'] == 0.0


def test_classify_empty_conv_data_no_http():
    """Empty conv_data returns unknown/0.0 without HTTP call."""
    from services import outcome_service
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        result = outcome_service.classify({})
        mock_client.messages.create.assert_not_called()
    assert result == {'outcome': 'unknown', 'confidence': 0.0}


def test_classify_dauer_zero_no_http():
    """Call with dauer_sekunden=0 returns unknown/0.0 without HTTP call."""
    from services import outcome_service
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        result = outcome_service.classify({'dauer_sekunden': 0})
        mock_client.messages.create.assert_not_called()
    assert result == {'outcome': 'unknown', 'confidence': 0.0}


def test_classify_handles_claude_exception(valid_conv_data):
    """Bei Claude-Fehler: outcome='unknown', kein Crash."""
    from services import outcome_service
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError('Claude API down')
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] == 'unknown'
    assert result['confidence'] == 0.0


def test_classify_handles_malformed_json(valid_conv_data):
    """Claude liefert kaputtes JSON -> outcome='unknown', kein Crash."""
    from services import outcome_service
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text='nicht-json-text {{{')]
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        mock_client.messages.create.return_value = bad_msg
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] == 'unknown'
    assert result['confidence'] == 0.0


def test_classify_invalid_outcome_value_rejected(valid_conv_data):
    """Claude liefert outcome ausserhalb Enum -> outcome='unknown'."""
    from services import outcome_service
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text=json.dumps({'outcome': 'random_value', 'confidence': 0.9}))]
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        mock_client.messages.create.return_value = bad_msg
        result = outcome_service.classify(valid_conv_data)
    assert result['outcome'] == 'unknown'


def test_confidence_ceiling_short_text():
    """Text < 20 words gets confidence ceiling of 0.65 (post-processing, REQ-D.UX-7)."""
    from services import outcome_service
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"outcome": "meeting_booked", "confidence": 0.92}')]
    with patch('services.claude_service.claude_client') as mock_client:  # STABIL-1: http_llm_client() liest claude_service.claude_client
        mock_client.with_options.return_value = mock_client
        mock_client.messages.create.return_value = mock_response
        result = outcome_service.classify({
            'dauer_sekunden': 60,
            'log_entries': [{'text': 'ja tschüss'}]
        })
    assert result['confidence'] <= 0.65


# ── _estimate_tokens() Tests ──────────────────────────────────────────────────

def test_estimate_tokens_empty():
    from services.outcome_service import _estimate_tokens
    assert _estimate_tokens('') == 0


def test_estimate_tokens_three_words():
    from services.outcome_service import _estimate_tokens
    assert _estimate_tokens('ein zwei drei') == int(3 * 1.4)


# ── _select_snippets() Tests ──────────────────────────────────────────────────

def test_select_snippets_empty():
    from services.outcome_service import _select_snippets
    assert _select_snippets([], 60) == []


def test_select_snippets_short_returns_full():
    from services.outcome_service import _select_snippets
    entries = [{'text': 'Hallo wie geht es'}]
    result = _select_snippets(entries, 30)
    assert result == ['Hallo wie geht es']


def test_select_snippets_no_text_field():
    from services.outcome_service import _select_snippets
    entries = [{'sprecher': 'berater'}, {'sprecher': 'kunde'}]
    assert _select_snippets(entries, 60) == []


# ── VALID_OUTCOMES Tests ──────────────────────────────────────────────────────

def test_valid_outcomes_contains_new_values():
    from services.outcome_service import VALID_OUTCOMES
    assert 'send_info' in VALID_OUTCOMES
    assert 'gatekeeper_blocked' in VALID_OUTCOMES


def test_valid_outcomes_has_8_values():
    from services.outcome_service import VALID_OUTCOMES
    assert len(VALID_OUTCOMES) == 8


def test_valid_outcomes_contains_all_expected():
    from services.outcome_service import VALID_OUTCOMES
    expected = {'meeting_booked', 'callback', 'send_info', 'wrong_person',
                'gatekeeper_blocked', 'no_interest', 'contract_signed', 'unknown'}
    assert VALID_OUTCOMES == expected


# ── SYSTEM_PROMPT Tests ───────────────────────────────────────────────────────

def test_system_prompt_contains_examples():
    from services.outcome_service import SYSTEM_PROMPT
    # Runtime behavior check: SYSTEM_PROMPT is a non-empty string with XML examples block
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 100
    assert '<examples>' in SYSTEM_PROMPT
    assert 'meeting_booked' in SYSTEM_PROMPT
    assert 'gatekeeper_blocked' in SYSTEM_PROMPT


# ── calculate_audio_health() Tests ───────────────────────────────────────────

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
