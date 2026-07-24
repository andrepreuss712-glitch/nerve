# tests/test_precall_schema.py
# Phase 08.20.2: Mock-Tests fuer _generiere_briefing() Schicht-1-Schema-Output
# Prueft Runtime-Rueckgabewerte (D-08) — keine inspect.getsource()-Tests (CLAUDE.md-Regel).

import json
import pytest
from unittest.mock import MagicMock


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_claude_mock(response_text):
    """Create a mock claude_client that returns response_text as message content."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock()]
    mock_msg.content[0].text = response_text
    mock_msg.usage = None  # no cost tracking in tests
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    mock_client.with_options.return_value = mock_client
    return mock_client


def _call_briefing(monkeypatch, response_text, firmenname='TestFirma GmbH', branche='IT'):
    """Call _generiere_briefing() with monkeypatched claude_client."""
    import services.precall_service as ps
    _mock = _make_claude_mock(response_text)
    monkeypatch.setattr(ps, 'claude_client', _mock)
    # STABIL-1 (2026-07-23): der Code ruft http_llm_client() -> liest
    # claude_service.claude_client, NICHT ps.claude_client. Den by-name-Import
    # ps.http_llm_client (precall_service.py:15) direkt auf den Mock umleiten.
    monkeypatch.setattr(ps, 'http_llm_client', lambda *a, **k: _mock)
    return ps._generiere_briefing(
        firmenname=firmenname,
        ansprechpartner='Max Mustermann',
        branche=branche,
        suchergebnisse=[{"title": "TestFirma", "description": "Ein Test", "url": "https://example.com"}],
    )


# ── Valid JSON response — all 4 Pflichtfelder present ─────────────────────────

_VALID_RESPONSE = json.dumps({
    "fields": {
        "geschaeftsfuehrer": {"value": "Hans Meier", "source_url": "https://example.com/impressum", "confidence": "high"},
        "branche": {"value": "IT-SaaS", "source_url": "https://linkedin.com/company/test", "confidence": "medium"},
        "mitarbeiterzahl": {"value": "ca. 50", "source_url": None, "confidence": "medium"},
        "hauptprodukt": {"value": "not_found", "source_url": None, "confidence": "not_found"},
    },
    "text": "TestFirma GmbH ist ein IT-SaaS Unternehmen mit ca. 50 Mitarbeitern."
})


def test_schicht1_returns_fields_dict(monkeypatch):
    """_generiere_briefing() must return a dict with 'fields' key that is a dict."""
    result = _call_briefing(monkeypatch, _VALID_RESPONSE)
    assert isinstance(result, dict), "return value must be a dict"
    assert 'fields' in result, "return dict must have 'fields' key"
    assert isinstance(result['fields'], dict), "fields must be a dict"


def test_schicht1_all_pflichtfelder_present(monkeypatch):
    """All 4 Pflichtfelder must be in result['fields'] regardless of confidence."""
    result = _call_briefing(monkeypatch, _VALID_RESPONSE)
    fields = result['fields']
    for key in ['geschaeftsfuehrer', 'branche', 'mitarbeiterzahl', 'hauptprodukt']:
        assert key in fields, f"Pflichtfeld '{key}' missing from fields"


def test_schicht1_field_struct_exact_keys(monkeypatch):
    """Each field dict must have exactly value, source_url, confidence — no extra keys."""
    result = _call_briefing(monkeypatch, _VALID_RESPONSE)
    for key, val in result['fields'].items():
        assert isinstance(val, dict), f"field '{key}' must be a dict"
        assert set(val.keys()) == {'value', 'source_url', 'confidence'}, \
            f"field '{key}' must have exactly value/source_url/confidence, got {set(val.keys())}"
        assert val['confidence'] in ('high', 'medium', 'not_found'), \
            f"field '{key}' confidence must be high/medium/not_found, got {val['confidence']!r}"


def test_schicht1_not_found_enforcement(monkeypatch):
    """not_found fields must have value='not_found' and source_url=None.

    Even if Claude returns an invented value with confidence=not_found,
    the service must normalize it to value='not_found', source_url=None.
    """
    bad_response = json.dumps({
        "fields": {
            "geschaeftsfuehrer": {"value": "Erfundener Name", "source_url": "https://fake.de", "confidence": "not_found"},
            "branche": {"value": "IT", "source_url": None, "confidence": "high"},
            "mitarbeiterzahl": {"value": "not_found", "source_url": None, "confidence": "not_found"},
            "hauptprodukt": {"value": "SaaS", "source_url": "https://linkedin.com", "confidence": "medium"},
        },
        "text": "Some text."
    })
    result = _call_briefing(monkeypatch, bad_response)
    gf = result['fields']['geschaeftsfuehrer']
    assert gf['value'] == 'not_found', \
        f"not_found field must have value='not_found', got {gf['value']!r}"
    assert gf['source_url'] is None, \
        f"not_found field must have source_url=None, got {gf['source_url']!r}"
    # mitarbeiterzahl: already correct, stays correct
    assert result['fields']['mitarbeiterzahl']['value'] == 'not_found'
    assert result['fields']['mitarbeiterzahl']['source_url'] is None


def test_schicht1_optional_field_not_found_excluded(monkeypatch):
    """Optional fields with confidence=not_found must NOT appear in result['fields']."""
    response_with_optional_not_found = json.dumps({
        "fields": {
            "geschaeftsfuehrer": {"value": "Hans Meier", "source_url": "https://impressum.de", "confidence": "high"},
            "branche": {"value": "IT", "source_url": None, "confidence": "medium"},
            "mitarbeiterzahl": {"value": "not_found", "source_url": None, "confidence": "not_found"},
            "hauptprodukt": {"value": "SaaS", "source_url": "https://linkedin.com", "confidence": "medium"},
            "standorte": {"value": "not_found", "source_url": None, "confidence": "not_found"},
            "gruendungsjahr": {"value": "2015", "source_url": "https://northdata.de/test", "confidence": "high"},
        },
        "text": "Kurzprofil."
    })
    result = _call_briefing(monkeypatch, response_with_optional_not_found)
    fields = result['fields']
    # standorte (not_found optional) must be absent
    assert 'standorte' not in fields, \
        "Optional field 'standorte' with not_found must be excluded from result"
    # gruendungsjahr (high, real value) must be present
    assert 'gruendungsjahr' in fields, \
        "Optional field 'gruendungsjahr' with high confidence must be present"
    assert fields['gruendungsjahr']['value'] == '2015'


def test_schicht1_graceful_degradation_on_parse_error(monkeypatch):
    """When Claude returns non-JSON, _generiere_briefing must not raise.

    All 4 Pflichtfelder must be present with confidence=not_found.
    """
    result = _call_briefing(monkeypatch, "Sorry, ich kann das nicht beantworten.")
    assert isinstance(result, dict), "Must return dict even on parse error"
    assert 'fields' in result, "Must have 'fields' key even on parse error"
    for key in ['geschaeftsfuehrer', 'branche', 'mitarbeiterzahl', 'hauptprodukt']:
        assert key in result['fields'], f"Pflichtfeld '{key}' missing after parse error"
        assert result['fields'][key]['confidence'] == 'not_found', \
            f"After parse error, '{key}' must have confidence=not_found"
    # text must be a string (may be empty), not None
    assert isinstance(result.get('text', ''), str), "text must be str, not None"


def test_schicht1_return_dict_has_required_top_level_keys(monkeypatch):
    """Top-level return dict must have exactly: fields, text, firmenname, ansprechpartner, quellen_count.

    Guards against Plan 02 breaking when it accesses briefing['fields'],
    and against regressions in the passthrough values firmenname and quellen_count.
    """
    result = _call_briefing(monkeypatch, _VALID_RESPONSE, firmenname='MeineFirma GmbH')
    for key in ['fields', 'text', 'firmenname', 'ansprechpartner', 'quellen_count']:
        assert key in result, f"Top-level key '{key}' missing from return dict"
    # Spot-check passthrough values
    assert result['firmenname'] == 'MeineFirma GmbH', \
        f"firmenname passthrough wrong: {result['firmenname']!r}"
    assert isinstance(result['quellen_count'], int), \
        f"quellen_count must be int, got {type(result['quellen_count'])}"
