"""
tests/test_08_5_05_training_pipeline_t2.py
──────────────────────────────────────────────────────────────────────────────
Phase 08.5 Plan 05 — Integration-Tests fuer Training-Pipeline Mocked-Calls.

Source-Presence-Tests (Tests 1-11 der urspruenglichen Datei) entfernt in
Phase 08.7 (Block H Test-False-Greens). Die 3 Mocked-Integration-Tests
und der Signature-Test bleiben als genuine Integration-Gates.
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

    # STABIL-1 (2026-07-23): siehe _t1.py — with_options()->self + messages.create
    # wirft, damit der geleakte Stub http_llm_client() ueberlebt statt fremde Tests
    # mitzureissen. Tests mit echter Antwort patchen claude_service.claude_client selbst.
    def with_options(self, *a, **k):
        return self

    class _Messages:
        def create(self, *a, **k):
            raise RuntimeError(
                'fake anthropic client (test stub) — patch '
                'services.claude_service.claude_client oder <modul>.http_llm_client')

    messages = _Messages()


_fake_anthropic.Anthropic = _FakeAnthropic
sys.modules.setdefault('anthropic', _fake_anthropic)
# Stub requests ONLY if not already loaded — see _t1.py for full reasoning.
import requests as _real_requests  # noqa: F401
sys.modules.setdefault('requests', types.ModuleType('requests'))


# ─── Integration Tests ────────────────────────────────────────────────────────

def test_generate_response_mocked_call(monkeypatch):
    """generate_response works end-to-end with mocked Anthropic client."""
    import services.training_service as ts

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

        def with_options(self, *args, **kwargs):
            return self

    _fake = _FakeClient()
    monkeypatch.setattr(ts, 'claude_client', _fake)
    # STABIL-1 (2026-07-23): generate_response ruft http_llm_client() -> liest
    # claude_service.claude_client, NICHT ts.claude_client. Umleiten auf den Fake.
    monkeypatch.setattr(ts, 'http_llm_client', lambda *a, **k: _fake)

    monkeypatch.setattr(ts, 'resolve_prompt_version', lambda module, uid: 'v1')

    conversation = [{'speaker': 'berater', 'text': 'Guten Tag'}]
    persona = {'chef_nachname': 'Test', 'firma': 'TestFirma', 'sek_name': 'Test Sek'}
    system_prompt = ts.build_sekretaerin_type_prompt(persona, 'blockerin', 'mittel')
    result = ts.generate_response(conversation, system_prompt)

    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_response_with_mood_mocked_call(monkeypatch):
    """generate_response_with_mood works with mocked Anthropic client."""
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

        def with_options(self, *args, **kwargs):
            return self

    _fake = _FakeClient()
    monkeypatch.setattr(ts, 'claude_client', _fake)
    # STABIL-1 (2026-07-23): generate_response ruft http_llm_client() -> liest
    # claude_service.claude_client, NICHT ts.claude_client. Umleiten auf den Fake.
    monkeypatch.setattr(ts, 'http_llm_client', lambda *a, **k: _fake)
    monkeypatch.setattr(ts, 'resolve_prompt_version', lambda module, uid: 'v1')

    conversation = [{'speaker': 'berater', 'text': 'Hallo'}]
    system_prompt = "Test system prompt"
    result = ts.generate_response_with_mood(conversation, system_prompt, current_mood=0)

    assert isinstance(result, dict)
    assert 'text' in result
    assert 'neue_stimmung' in result


def test_public_signatures_unchanged():
    """Public function signatures of generate_response and generate_response_with_mood unchanged."""
    import inspect
    import services.training_service as ts

    sig_gr = inspect.signature(ts.generate_response)
    params_gr = list(sig_gr.parameters.keys())
    assert 'conversation_history' in params_gr
    assert 'system_prompt' in params_gr

    sig_grm = inspect.signature(ts.generate_response_with_mood)
    params_grm = list(sig_grm.parameters.keys())
    assert 'conversation_history' in params_grm
    assert 'system_prompt' in params_grm
    assert 'current_mood' in params_grm


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
