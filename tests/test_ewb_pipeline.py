"""Phase 08 tests for services/ewb_pipeline.py + _seed_ewb_v2."""
import sys
import uuid

import pytest

from database.models import PromptVersion

# Import under test — RED-gate: fails before Task 2 implementation.
import services.ewb_pipeline as ep


# ── Phase 08.23.2.PGTEST Gruppe A — unique test-version gegen UNIQUE(version,module) ──────
# _load_prompt_template() ist HART auf module='ewb' verdrahtet (ewb_pipeline.py:85) → ein
# test-eigener module-Name ginge am Loader vorbei. Daher bleibt module='ewb', aber die VERSION
# wird pro Test-Run unique (uuid-suffixed). Grund: auf der persistenten nerve_test traegt
# prompt_versions bereits die app-import-Baseline (_seed_ewb_v2: (ewb,v1-legacy)+(ewb,v2-modular),
# via `from app import app` im _baseline_snapshot gefeuert). Ein blindes Re-Insert derselben
# (version,module) bricht auf UNIQUE(version,module)=uq_prompt_version_module (models.py:483).
# Unique Versions kollidieren nicht UND tragen die test-eigene Distinkt-Content (die der Test
# assertet — die Baseline-Rows tragen ANDEREN Content). db_session ist rollback-covered (D-03) →
# kein cleanup_rows noetig; die test-eigenen Rows verschwinden beim Rollback, Baseline unberuehrt.
def _seed_ewb_variants(db_session):
    """Seed 2 prompt_versions rows for module='ewb' with distinct content + unique test-versions.

    Returns (v1_version, v2_version) so callers pass the exact unique version into build_ewb_prompt.
    """
    suffix = uuid.uuid4().hex[:8]
    v1 = f'v1-legacy-test-{suffix}'
    v2 = f'v2-modular-test-{suffix}'
    for v, text, default in [
        (v1, 'v1-legacy-text CONTENT', False),
        (v2,
         ('v2 with Anker Reframe Beweis Ueberleitung '
          'Active Listening max 45 Woerter NIEMALS apologetisch'),
         False),
    ]:
        db_session.add(PromptVersion(
            module='ewb', version=v, prompt_text=text,
            is_active=True, is_default=default,
            changelog=f'test-{v}',
        ))
    db_session.commit()
    return v1, v2


class _Fake:
    """SessionLocal-adapter so ewb_pipeline sees pytest db_session."""
    def __init__(self, real):
        self._r = real

    def query(self, *a, **k):
        return self._r.query(*a, **k)

    def add(self, *a, **k):
        return self._r.add(*a, **k)

    def commit(self):
        return self._r.commit()

    def close(self):
        pass


def _bind(monkeypatch, db_session):
    monkeypatch.setattr('database.db.SessionLocal', lambda: _Fake(db_session))


@pytest.fixture
def _empty_active_profile(monkeypatch):
    """Opt-in: no active profile → build_profile_context returns '' and
    build_ewb_prompt falls back to manual Anrede-Constraint.

    Used only by build_ewb_prompt tests. NOT autouse — would break app-import
    for _seed_ewb_v2 tests because routes/app_routes does
    `from services.live_session import LOG_DIR` at import time.

    NOTE: Python's `import services.live_session as X` resolves the submodule
    via the attribute `live_session` on the `services` package — NOT via
    sys.modules. If another test previously triggered `import app` (which
    transitively imports services.live_session), the `services` package
    caches the real module as its attribute. A bare `setitem(sys.modules, ...)`
    does NOT override that attribute. We therefore patch BOTH:
      - sys.modules entry
      - services package attribute
    so the mock is honoured regardless of suite order.
    """
    class _LSMock:
        state = {}

        @staticmethod
        def get_active_profile():
            return (None, None)

    import services as _services_pkg
    monkeypatch.setitem(sys.modules, 'services.live_session', _LSMock)
    monkeypatch.setattr(_services_pkg, 'live_session', _LSMock, raising=False)


# ─── 1. v1-legacy assembly ──────────────────────────────────────────────────

def test_build_ewb_prompt_v1_legacy(db_session, monkeypatch, _empty_active_profile):
    v1, _v2 = _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(profile_data={}, anrede='Sie',
                              version=v1, user_id=0)
    assert 'v1-legacy-text CONTENT' in out
    assert 'Anrede: Sie' in out


# ─── 2. v2-modular Baustein-Struktur ────────────────────────────────────────

def test_build_ewb_prompt_v2_modular_bausteine(db_session, monkeypatch,
                                                _empty_active_profile):
    _v1, v2 = _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(profile_data={}, anrede='Du',
                              version=v2, user_id=1)
    for keyword in ['Anker', 'Reframe', 'Beweis', 'Ueberleitung',
                    'Active Listening', '45 Woerter']:
        assert keyword in out, f'missing keyword: {keyword}'


# ─── 3. Anrede='Du' → D-15 Constraint ───────────────────────────────────────

def test_build_ewb_prompt_anrede_du(db_session, monkeypatch, _empty_active_profile):
    v1, _v2 = _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(anrede='Du', version=v1)
    assert 'Anrede: Du' in out
    assert 'Wechsle NIEMALS' in out


# ─── 4. Unknown version → Fallback zu _FALLBACK_V1_PROMPT ──────────────────

def test_build_ewb_prompt_fallback_unknown_version(db_session, monkeypatch,
                                                    _empty_active_profile):
    _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(anrede='Sie', version='nonexistent')
    assert len(out) > 50, 'fallback must provide substantial text'
    assert ('NERVE' in out) or ('Vertrieb' in out), \
        'fallback must mention NERVE/Vertrieb to be recognizable'


# ─── 5. _seed_ewb_v2 idempotent ─────────────────────────────────────────────

def test_seed_ewb_v2_idempotent(db_session):
    from app import _seed_ewb_v2
    _seed_ewb_v2(db=db_session)
    c1 = db_session.query(PromptVersion).filter_by(module='ewb').count()
    _seed_ewb_v2(db=db_session)
    c2 = db_session.query(PromptVersion).filter_by(module='ewb').count()
    assert c1 == c2 == 2, f"seed must be idempotent (got {c1}/{c2})"


# ─── 6. _seed_ewb_v2 flags (is_default + is_active) ────────────────────────

def test_seed_ewb_v2_default_flags(db_session):
    from app import _seed_ewb_v2
    _seed_ewb_v2(db=db_session)
    v1 = db_session.query(PromptVersion).filter_by(
        module='ewb', version='v1-legacy').first()
    v2 = db_session.query(PromptVersion).filter_by(
        module='ewb', version='v2-modular').first()
    assert v1 is not None, "v1-legacy row missing"
    assert v2 is not None, "v2-modular row missing"
    assert v1.is_default is True, "v1-legacy must be default"
    assert v2.is_default is False, "v2-modular must NOT be default"
    assert v1.is_active is True
    assert v2.is_active is True
