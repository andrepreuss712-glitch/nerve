"""
tests/test_08_5_05_training_pipeline_t1.py
──────────────────────────────────────────────────────────────────────────────
Phase 08.5 Plan 05 — Task 1 TDD: _load_training_prompt_template helper +
_TRAINING_FALLBACKS dict.

RED phase: these tests fail until the helper is added to training_service.py.
"""
import sys
import types
import pytest


# ─── Stub out heavy imports before any training_service import ──────────────

# Stub anthropic so training_service.py can be imported without the real SDK
_fake_anthropic = types.ModuleType('anthropic')
_fake_client = object()


class _FakeAnthropic:
    def __init__(self, **kwargs):
        pass

    # STABIL-1 (2026-07-23): der Modul-Global claude_service.claude_client wird
    # (reihenfolge-abhaengig) diese _FakeAnthropic-Instanz, weil der sys.modules-
    # Stub unten den echten anthropic-Import abklemmt. Nach dem Call-Site-Rename
    # ruft der Code http_llm_client() -> claude_client.with_options(...); der nackte
    # Stub crashte daran ('has no attribute with_options') und riss fremde Tests mit.
    # with_options gibt sich selbst zurueck (Kopie-Semantik); messages.create wirft
    # bewusst (Vor-Rename-Aequivalent: ungemockte Kollateralpfade landeten am echten
    # API-Call in ihren except-Bloecken). Tests, die eine ANTWORT brauchen, patchen
    # claude_service.claude_client bzw. <modul>.http_llm_client selbst.
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

# Stub requests ONLY if not already loaded. import first to ensure the real
# package wins (authlib in oauth.py needs requests.Session — if this setdefault
# fired before authlib's import, the real package would be replaced by an empty
# stub and break all subsequent test collection). Phase 08.23.2.A bugfix.
import requests as _real_requests  # noqa: F401
sys.modules.setdefault('requests', types.ModuleType('requests'))

# Stub elevenlabs/config imports via a thin config stub
import os
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('ELEVENLABS_API_KEY', 'test-key')


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_import_helper():
    """Test 1: _load_training_prompt_template is importable from training_service."""
    from services.training_service import _load_training_prompt_template
    assert callable(_load_training_prompt_template)


def test_fallback_for_all_4_modules():
    """Test 2: fallback works for all 4 modules when DB row missing."""
    from services.training_service import _load_training_prompt_template
    for module in ['training_kunde', 'training_sek', 'training_stimmung', 'training_scoring']:
        result = _load_training_prompt_template(module, 'nonexistent_version_xyz')
        assert isinstance(result, str), f"module {module} did not return str"
        assert len(result) > 0, f"module {module} returned empty string: {result!r}"


def test_unknown_module_returns_empty_string():
    """Test 3: unknown module returns empty string without raising."""
    from services.training_service import _load_training_prompt_template
    result = _load_training_prompt_template('unknown_xyz', 'v1')
    assert result == '', f"expected empty string, got: {result!r}"


def test_fallbacks_dict_has_expected_keys():
    """Test 4: _TRAINING_FALLBACKS has exactly the 4 expected module keys."""
    from services.training_service import _TRAINING_FALLBACKS
    expected = {'training_kunde', 'training_sek', 'training_stimmung', 'training_scoring'}
    assert set(_TRAINING_FALLBACKS.keys()) == expected, (
        f"_TRAINING_FALLBACKS keys mismatch: {set(_TRAINING_FALLBACKS.keys())} != {expected}"
    )


def test_fallback_kunde_matches_constant():
    """Test 5: _TRAINING_FALLBACKS['training_kunde'] equals KUNDEN_PROMPT_TEMPLATE constant."""
    from services.training_service import _TRAINING_FALLBACKS, KUNDEN_PROMPT_TEMPLATE
    assert _TRAINING_FALLBACKS['training_kunde'] == KUNDEN_PROMPT_TEMPLATE


def test_db_row_returned_when_present(monkeypatch):
    """Test 6: Returns DB row's prompt_text when a matching active row exists."""
    expected_prompt = 'This is the DB-loaded prompt text for testing.'

    # Create a fake PromptVersion row
    class _FakeRow:
        prompt_text = expected_prompt

    # Fake DB session that returns the row
    class _FakeSession:
        def query(self, model):
            return self

        def filter_by(self, **kwargs):
            return self

        def first(self):
            return _FakeRow()

        def close(self):
            pass

    import database.db as db_mod
    monkeypatch.setattr(db_mod, 'SessionLocal', _FakeSession)

    from services.training_service import _load_training_prompt_template
    result = _load_training_prompt_template('training_kunde', 'v1')
    assert result == expected_prompt


def test_placeholder_seed_falls_back_to_constant(monkeypatch):
    """Test 7: If DB row starts with 'Placeholder v1', fall back to constant."""
    class _FakePlaceholderRow:
        prompt_text = 'Placeholder v1 — fallback to constant (Phase 08.5 seed)'

    class _FakePlaceholderSession:
        def query(self, model):
            return self

        def filter_by(self, **kwargs):
            return self

        def first(self):
            return _FakePlaceholderRow()

        def close(self):
            pass

    import database.db as db_mod
    monkeypatch.setattr(db_mod, 'SessionLocal', _FakePlaceholderSession)

    from services.training_service import _load_training_prompt_template, KUNDEN_PROMPT_TEMPLATE
    result = _load_training_prompt_template('training_kunde', 'v1')
    assert result == KUNDEN_PROMPT_TEMPLATE, (
        f"Placeholder seed should fall back to KUNDEN_PROMPT_TEMPLATE, got: {result!r}"
    )


# Allow direct run
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
