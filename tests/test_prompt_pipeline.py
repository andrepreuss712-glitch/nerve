"""Phase 08 unit tests for services/prompt_pipeline.py."""
import os
import sys

import pytest

from database.models import PromptVersion


# Import the module under test lazily — tests will fail at import-time if
# services/prompt_pipeline.py is not yet created. That is the RED-gate.
import services.prompt_pipeline as pp


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    monkeypatch.setattr(pp, '_RESOLVER_CACHE', {})
    monkeypatch.setattr(pp, '_VARIANTS_CACHE', {})
    # Clean any prior PROMPT_*_VERSION_OVERRIDE env vars so tests are hermetic.
    for k in list(os.environ.keys()):
        if k.startswith('PROMPT_') and k.endswith('_VERSION_OVERRIDE'):
            monkeypatch.delenv(k, raising=False)


def _seed_variants(db_session, module='ewb', versions=('v1-legacy', 'v2-modular')):
    for v in versions:
        db_session.add(PromptVersion(
            module=module, version=v, prompt_text=f'text-{v}',
            is_active=True, is_default=(v == versions[0]),
            changelog=f'test-{v}',
        ))
    db_session.commit()


class _Fake:
    """Adapter so SessionLocal() returns the pytest db_session without closing it."""
    def __init__(self, real):
        self._r = real

    def query(self, *a, **k):
        return self._r.query(*a, **k)

    def add(self, *a, **k):
        return self._r.add(*a, **k)

    def commit(self):
        return self._r.commit()

    def close(self):
        # Do NOT close the shared pytest session; the fixture owns its lifecycle.
        pass


def _bind(monkeypatch, db_session):
    """Route SessionLocal() to the in-memory pytest session."""
    monkeypatch.setattr('database.db.SessionLocal', lambda: _Fake(db_session))


# ─── 1. resolve_prompt_version: ENV-Override (First-Check) ──────────────────

def test_env_override_first_check(monkeypatch):
    monkeypatch.setenv('PROMPT_EWB_VERSION_OVERRIDE', 'v-override')
    # ENV wins — must never touch DB:
    assert pp.resolve_prompt_version('ewb', user_id=42) == 'v-override'


# ─── 2. Deterministic routing (user_id % N) ─────────────────────────────────

def test_deterministic_routing_even_user(db_session, monkeypatch):
    _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    # Sorted alphabetically: ['v1-legacy', 'v2-modular']; user_id=0 -> index 0
    assert pp.resolve_prompt_version('ewb', user_id=0) == 'v1-legacy'


def test_deterministic_routing_odd_user(db_session, monkeypatch):
    _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    # user_id=1 -> index 1
    assert pp.resolve_prompt_version('ewb', user_id=1) == 'v2-modular'


# ─── 3. Cache-per-user key (W-7 regression-guard) ───────────────────────────

def test_cache_per_user_key(db_session, monkeypatch):
    _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    r0 = pp.resolve_prompt_version('ewb', user_id=0)
    r1 = pp.resolve_prompt_version('ewb', user_id=1)
    assert r0 != r1, "different user_ids must land on different variants"
    assert ('ewb', 0) in pp._RESOLVER_CACHE
    assert ('ewb', 1) in pp._RESOLVER_CACHE


# ─── 4. No-variants fallback ────────────────────────────────────────────────

def test_no_variants_returns_unknown(db_session, monkeypatch):
    # empty prompt_versions table for a new module:
    _bind(monkeypatch, db_session)
    assert pp.resolve_prompt_version('nonexistent_module', user_id=0) == 'unknown'


# ─── 5. Cache invalidation ───────────────────────────────────────────────────

def test_invalidate_resolver_cache_clears_both():
    pp._RESOLVER_CACHE[('ewb', 0)] = 'cached'
    pp._VARIANTS_CACHE['ewb'] = ['x', 'y']
    pp.invalidate_resolver_cache()
    assert pp._RESOLVER_CACHE == {}
    assert pp._VARIANTS_CACHE == {}


# ─── Helper: install live_session mock (robust gegen Full-Suite-Mode) ───────
# Python's `import services.live_session as X` resolves the submodule via the
# attribute `live_session` on the `services` package — NOT via sys.modules
# lookup. If another test (e.g. via `import app`) has previously triggered
# `import services.live_session`, the `services` package caches the real module
# as its attribute. A bare `setitem(sys.modules, ...)` would NOT override that
# attribute, so the mock would be bypassed. We therefore patch BOTH:
#   - sys.modules entry (for importlib.import_module and some import paths)
#   - services package attribute (for `import services.live_session as X`)
def _install_ls_mock(monkeypatch, mock):
    import services as _services_pkg
    monkeypatch.setitem(sys.modules, 'services.live_session', mock)
    monkeypatch.setattr(_services_pkg, 'live_session', mock, raising=False)


# ─── 6. build_profile_context: empty-profile fallback ───────────────────────

def test_build_profile_context_no_active_profile(monkeypatch):
    """When no active profile is loaded, return empty string (caller adds Anrede-fallback)."""
    class _LSMock:
        state = {}

        @staticmethod
        def get_active_profile():
            return (None, None)

    _install_ls_mock(monkeypatch, _LSMock)
    assert pp.build_profile_context(user_id=1) == ''


# ─── 7. build_profile_context: new Phase-08 fields (D-07/D-08/D-11) ─────────

def test_build_profile_context_includes_phase_08_fields(monkeypatch):
    class _LSMock:
        state = {}

        @staticmethod
        def get_active_profile():
            return (1, {
                'basis': {
                    'unternehmen': 'Firma XY',
                    'produktbeschreibung': 'Testprodukt',
                    'usps': ['U1', 'U2'],
                    'branche_kontext': 'Maschinenbau-Mittelstand',
                    'eigene_formulierungen': [
                        'Darf ich fragen, was Sie einsetzen?'
                    ],
                    'beweise': [
                        'Firma Z: 15% mehr Abschluesse in 3 Monaten'
                    ],
                },
                'ki': {'ton': 'Direkt/Klartext'},
            })

    _install_ls_mock(monkeypatch, _LSMock)
    out = pp.build_profile_context(user_id=1)
    assert 'Firma XY' in out
    assert 'Testprodukt' in out
    assert 'Maschinenbau-Mittelstand' in out
    assert 'Darf ich fragen, was Sie einsetzen?' in out
    assert '15% mehr Abschluesse' in out


# ─── 8. Anrede-Resolution: Session > Profile > 'Sie' ────────────────────────

def test_build_profile_context_anrede_session_override_wins(monkeypatch):
    class _LSMock:
        state = {'session_anrede': 'Du'}

        @staticmethod
        def get_active_profile():
            return (1, {'basis': {}, 'ki': {'ansprache': 'Sie'}})

    _install_ls_mock(monkeypatch, _LSMock)
    out = pp.build_profile_context(user_id=1)
    assert 'Anrede: Du.' in out
    assert 'Wechsle NIEMALS' in out


# ─── 9. log_pipeline_event: MUST swallow errors ─────────────────────────────

def test_log_pipeline_event_swallows_errors(monkeypatch):
    """Live-loop guarantee — log_pipeline_event must never propagate exceptions."""
    # Install a fake 'services.finetune_logging' module whose log_ft_event raises.
    import types

    fake_mod = types.ModuleType('services.finetune_logging')

    def _raise(*a, **k):
        raise RuntimeError('DB down')

    fake_mod.log_ft_event = _raise
    monkeypatch.setitem(sys.modules, 'services.finetune_logging', fake_mod)

    # Must not raise:
    pp.log_pipeline_event('assistant', 'ewb', {'model': 'haiku'})


# ─── 10. log_pipeline_event: missing sibling module also swallowed ──────────

def test_log_pipeline_event_handles_missing_module(monkeypatch):
    """If services.finetune_logging does not exist at all, must still swallow."""
    # Make sure the module is NOT present in sys.modules:
    monkeypatch.delitem(sys.modules, 'services.finetune_logging', raising=False)
    # Must not raise:
    pp.log_pipeline_event('assistant', 'ewb', {'model': 'haiku'})
