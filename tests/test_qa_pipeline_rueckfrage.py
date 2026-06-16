"""
tests/test_qa_pipeline_rueckfrage.py
────────────────────────────────────────────────────────────────────
TDD tests for Phase 08.5 Korrektur 3:
  - build_tabu_instruction() in services/qa_pipeline.py
  - apply_tabu_safety_net() in services/qa_pipeline.py
  - generate_qa_response() Rückfrage branch (confidence < 0.80)

All LLM calls are mocked — tests run without network.
"""
import sys
import types
import pytest


# ── Fixtures / Helpers ────────────────────────────────────────────────────────

def _make_profile(tabu_begriffe=None):
    """Return minimal profile_data dict with tabu_begriffe."""
    return {
        'daten': {
            'basis': {
                'tabu_begriffe': tabu_begriffe if tabu_begriffe is not None else [],
            }
        }
    }


# ── build_tabu_instruction ────────────────────────────────────────────────────

def test_build_tabu_instruction_empty():
    """Profile without tabu_begriffe → returns empty string."""
    from services.qa_pipeline import build_tabu_instruction
    profile = _make_profile([])
    result = build_tabu_instruction(profile)
    assert result == ''


def test_build_tabu_instruction_populated():
    """3 complete pairs → block containing 'TABU-ALTERNATIVEN' and all 3 mappings."""
    from services.qa_pipeline import build_tabu_instruction
    tabu = [
        {'begriff': 'Kosten', 'alternative': 'Investition'},
        {'begriff': 'Problem', 'alternative': 'Herausforderung'},
        {'begriff': 'Risiko', 'alternative': 'Absicherung'},
    ]
    profile = _make_profile(tabu)
    result = build_tabu_instruction(profile)
    # Phase 08.23.2.PGTEST.GREEN Muster D: Template-Header geaendert 'WICHTIG:' -> 'TABU-ALTERNATIVEN'
    # (services/qa_pipeline.py:177 verifiziert).
    assert 'TABU-ALTERNATIVEN' in result
    assert 'Kosten' in result and 'Investition' in result
    assert 'Problem' in result and 'Herausforderung' in result
    assert 'Risiko' in result and 'Absicherung' in result


def test_build_tabu_instruction_skips_incomplete():
    """Pair with empty alternative → skipped from output."""
    from services.qa_pipeline import build_tabu_instruction
    tabu = [
        {'begriff': 'Kosten', 'alternative': ''},          # incomplete → skip
        {'begriff': 'Problem', 'alternative': 'Herausforderung'},  # complete
    ]
    profile = _make_profile(tabu)
    result = build_tabu_instruction(profile)
    # 'Kosten' should NOT appear (no alternative)
    assert 'Kosten' not in result
    assert 'Problem' in result
    assert 'Herausforderung' in result


# ── apply_tabu_safety_net ────────────────────────────────────────────────────

def test_safety_net_substitutes_tabu():
    """Generated answer contains 'Kosten', profile has Kosten→Investition → substituted."""
    from services.qa_pipeline import apply_tabu_safety_net
    text = 'Das sind die Kosten für unser Produkt.'
    tabu_pairs = [{'begriff': 'Kosten', 'alternative': 'Investition'}]
    result = apply_tabu_safety_net(text, tabu_pairs)
    assert 'Investition' in result
    assert 'Kosten' not in result


# ── generate_qa_response Rückfrage branch (mocked LLM) ─────────────────────

@pytest.fixture(autouse=True)
def mock_claude_client(monkeypatch):
    """Mock claude_client so no network calls happen."""
    import services.claude_service as cs

    class _FakeUsage:
        input_tokens = 10
        output_tokens = 20

    class _FakeContent:
        def __init__(self, text):
            self.text = text

    class _FakeMsg:
        def __init__(self, text):
            self.content = [_FakeContent(text)]
            self.usage = _FakeUsage()

    class _FakeMessages:
        def __init__(self, text):
            self._text = text

        def create(self, **kwargs):
            return _FakeMsg(self._text)

    class _FakeClient:
        def __init__(self, text):
            self.messages = _FakeMessages(text)

    # Default: high-confidence direct answer
    monkeypatch.setattr(cs, 'claude_client', _FakeClient('Das ist eine direkte Antwort.'))
    return _FakeClient


def _patch_claude_response(monkeypatch, text):
    """Re-patch claude_client with a specific response text."""
    import services.claude_service as cs

    class _FakeUsage:
        input_tokens = 10
        output_tokens = 20

    class _FakeContent:
        def __init__(self, t):
            self.text = t

    class _FakeMsg:
        def __init__(self, t):
            self.content = [_FakeContent(t)]
            self.usage = _FakeUsage()

    class _FakeMessages:
        def __init__(self, t):
            self._t = t
        def create(self, **kwargs):
            return _FakeMsg(self._t)

    class _FakeClient:
        def __init__(self, t):
            self.messages = _FakeMessages(t)

    monkeypatch.setattr(cs, 'claude_client', _FakeClient(text))


def test_generate_qa_response_high_confidence_direct(monkeypatch):
    """confidence=0.90 → returns direct answer, no 'Frag nach:' prefix."""
    _patch_claude_response(monkeypatch, 'Das ist eine direkte Antwort.')
    from services.qa_pipeline import generate_qa_response
    profile = _make_profile([{'begriff': 'Kosten', 'alternative': 'Investition'}])
    result = generate_qa_response(
        utterance='Das ist zu teuer.',
        category='einwand_unknown',
        profile_data=profile,
        anrede='Sie',
        confidence=0.90,
        version='v1',
        user_id=1,
    )
    assert result  # not empty
    assert not result.startswith('Frag nach:')


def test_generate_qa_response_low_confidence_rueckfrage(monkeypatch):
    """confidence=0.50 → returns text starting with 'Frag nach:'."""
    _patch_claude_response(monkeypatch, 'Frag nach: Wie meinen Sie das genau?')
    from services.qa_pipeline import generate_qa_response
    profile = _make_profile([])
    result = generate_qa_response(
        utterance='Hm, weiß nicht so recht.',
        category='einwand_unknown',
        profile_data=profile,
        anrede='Sie',
        confidence=0.50,
        version='v1',
        user_id=1,
    )
    assert result.startswith('Frag nach:')


def test_generate_qa_response_never_silent(monkeypatch):
    """confidence=0.30, LLM returns empty → fallback Rückfrage, never '' or None."""
    _patch_claude_response(monkeypatch, '')
    from services.qa_pipeline import generate_qa_response
    profile = _make_profile([])
    result = generate_qa_response(
        utterance='Hmm.',
        category='einwand_unknown',
        profile_data=profile,
        anrede='Sie',
        confidence=0.30,
        version='v1',
        user_id=1,
    )
    assert result  # never empty
    assert result is not None
    assert 'Frag nach:' in result
