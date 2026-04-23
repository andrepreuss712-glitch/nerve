"""
tests/test_08_5_05_training_pipeline_t2.py
──────────────────────────────────────────────────────────────────────────────
Phase 08.5 Plan 05 — Task 2 TDD: 4 call-site swaps + log_pipeline_event.

RED phase: fails until generate_response, generate_response_with_mood,
generate_scoring all route through _load_training_prompt_template and emit
log_pipeline_event.
"""
import sys
import types
import pytest

# ─── Stub heavy imports ──────────────────────────────────────────────────────

import os
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('ELEVENLABS_API_KEY', 'test-key')

_fake_anthropic = types.ModuleType('anthropic')


class _FakeAnthropic:
    def __init__(self, **kwargs):
        pass


_fake_anthropic.Anthropic = _FakeAnthropic
sys.modules.setdefault('anthropic', _fake_anthropic)
sys.modules.setdefault('requests', types.ModuleType('requests'))


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_source_has_4_module_references():
    """Test 1: All 4 training module names are referenced in training_service.py."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts)
    for module in ['training_kunde', 'training_sek', 'training_stimmung', 'training_scoring']:
        assert module in src, f"module '{module}' not referenced in training_service.py"


def test_source_has_4_loader_calls():
    """Test 2: _load_training_prompt_template called at least 4 times in source."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts)
    count = src.count('_load_training_prompt_template(')
    assert count >= 4, f"_load_training_prompt_template call count < 4: {count}"


def test_source_has_3_log_pipeline_event_calls():
    """Test 3: log_pipeline_event called at least 3 times in source."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts)
    count = src.count('log_pipeline_event(')
    assert count >= 3, f"log_pipeline_event call count < 3: {count}"


def test_constants_still_present():
    """Test 4: existing constants preserved — no regression."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts)
    assert 'KUNDEN_PROMPT_TEMPLATE' in src, 'KUNDEN_PROMPT_TEMPLATE deleted (regression risk)'
    assert 'SEKRETAERIN_PROMPT' in src, 'SEKRETAERIN_PROMPT deleted'
    assert 'PERSONALITY_MOOD_PROMPT_SUFFIX' in src, 'PERSONALITY_MOOD_PROMPT_SUFFIX deleted'


def test_haiku_model_still_present():
    """Test 5: Haiku model ID unchanged for live training calls."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts)
    assert 'claude-haiku-4-5-20251001' in src, 'Haiku model id missing'


def test_generate_response_uses_loader():
    """Test 6: generate_response source references _load_training_prompt_template."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_response)
    assert '_load_training_prompt_template(' in src, (
        "generate_response does not call _load_training_prompt_template"
    )


def test_generate_response_logs_pipeline_event():
    """Test 7: generate_response source references log_pipeline_event."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_response)
    assert 'log_pipeline_event(' in src, (
        "generate_response does not call log_pipeline_event"
    )


def test_generate_scoring_uses_loader():
    """Test 8: generate_scoring source references _load_training_prompt_template."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_scoring)
    assert '_load_training_prompt_template(' in src, (
        "generate_scoring does not call _load_training_prompt_template"
    )


def test_generate_scoring_logs_pipeline_event():
    """Test 9: generate_scoring logs with module='training_scoring'."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_scoring)
    assert 'log_pipeline_event(' in src, "generate_scoring does not call log_pipeline_event"
    assert 'training_scoring' in src, "generate_scoring does not reference 'training_scoring' module"


def test_generate_response_with_mood_uses_loader():
    """Test 10: generate_response_with_mood source references _load_training_prompt_template."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_response_with_mood)
    assert '_load_training_prompt_template(' in src, (
        "generate_response_with_mood does not call _load_training_prompt_template"
    )


def test_generate_response_with_mood_logs_stimmung():
    """Test 11: generate_response_with_mood logs with module='training_stimmung'."""
    import inspect
    import services.training_service as ts
    src = inspect.getsource(ts.generate_response_with_mood)
    assert 'log_pipeline_event(' in src, "generate_response_with_mood does not call log_pipeline_event"
    assert 'training_stimmung' in src, "generate_response_with_mood does not reference 'training_stimmung'"


def test_generate_response_mocked_call(monkeypatch):
    """Test 12: generate_response works end-to-end with mocked Anthropic client."""
    import services.training_service as ts

    # Mock claude_client.messages.create
    class _FakeContent:
        text = "Das ist ein Test-Antwort des simulierten Kunden."

    class _FakeResponse:
        content = [_FakeContent()]

    def _fake_create(**kwargs):
        return _FakeResponse()

    class _FakeMessages:
        create = staticmethod(_fake_create)

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(ts, 'claude_client', _FakeClient())

    # Mock log_pipeline_event to capture calls
    log_calls = []
    monkeypatch.setattr(ts, 'log_pipeline_event', lambda *a, **kw: log_calls.append((a, kw)))

    # Mock resolve_prompt_version
    monkeypatch.setattr(ts, 'resolve_prompt_version', lambda module, uid: 'v1')

    conversation = [{'speaker': 'berater', 'text': 'Guten Tag'}]
    system_prompt = ts.build_sekretaerin_prompt({'chef_nachname': 'Test', 'firma': 'TestFirma', 'sek_name': 'Test Sek'})
    result = ts.generate_response(conversation, system_prompt)

    assert isinstance(result, str)
    assert len(result) > 0
    # log_pipeline_event should have been called
    assert len(log_calls) >= 1, "log_pipeline_event was not called from generate_response"


def test_generate_response_with_mood_mocked_call(monkeypatch):
    """Test 13: generate_response_with_mood works with mocked Anthropic client."""
    import services.training_service as ts

    class _FakeContent:
        text = '{"text": "Antwort.", "neue_stimmung": 1, "aufgelegt": false, "letzte_chance": false}'

    class _FakeResponse:
        content = [_FakeContent()]

    def _fake_create(**kwargs):
        return _FakeResponse()

    class _FakeMessages:
        create = staticmethod(_fake_create)

    class _FakeClient:
        messages = _FakeMessages()

    monkeypatch.setattr(ts, 'claude_client', _FakeClient())
    log_calls = []
    monkeypatch.setattr(ts, 'log_pipeline_event', lambda *a, **kw: log_calls.append((a, kw)))
    monkeypatch.setattr(ts, 'resolve_prompt_version', lambda module, uid: 'v1')

    conversation = [{'speaker': 'berater', 'text': 'Hallo'}]
    system_prompt = "Test system prompt"
    result = ts.generate_response_with_mood(conversation, system_prompt, current_mood=0)

    assert isinstance(result, dict)
    assert 'text' in result
    assert 'neue_stimmung' in result
    assert len(log_calls) >= 1, "log_pipeline_event was not called from generate_response_with_mood"


def test_public_signatures_unchanged():
    """Test 14: public function signatures of generate_response etc. unchanged."""
    import inspect
    import services.training_service as ts

    # generate_response(conversation_history, system_prompt)
    sig_gr = inspect.signature(ts.generate_response)
    params_gr = list(sig_gr.parameters.keys())
    assert 'conversation_history' in params_gr
    assert 'system_prompt' in params_gr

    # generate_response_with_mood(conversation_history, system_prompt, current_mood, schwierigkeit)
    sig_grm = inspect.signature(ts.generate_response_with_mood)
    params_grm = list(sig_grm.parameters.keys())
    assert 'conversation_history' in params_grm
    assert 'system_prompt' in params_grm
    assert 'current_mood' in params_grm


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
