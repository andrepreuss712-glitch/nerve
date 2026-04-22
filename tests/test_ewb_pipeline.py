"""Phase 08 tests for services/ewb_pipeline.py + _seed_ewb_v2."""
import sys

import pytest

from database.models import PromptVersion

# Import under test — RED-gate: fails before Task 2 implementation.
import services.ewb_pipeline as ep


def _seed_ewb_variants(db_session):
    """Seed 2 prompt_versions rows for module='ewb' with distinct content."""
    for v, text, default in [
        ('v1-legacy', 'v1-legacy-text CONTENT', True),
        ('v2-modular',
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
    """
    class _LSMock:
        state = {}

        @staticmethod
        def get_active_profile():
            return (None, None)

    monkeypatch.setitem(sys.modules, 'services.live_session', _LSMock)


# ─── 1. v1-legacy assembly ──────────────────────────────────────────────────

def test_build_ewb_prompt_v1_legacy(db_session, monkeypatch, _empty_active_profile):
    _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(profile_data={}, anrede='Sie',
                              version='v1-legacy', user_id=0)
    assert 'v1-legacy-text CONTENT' in out
    assert 'Anrede: Sie' in out


# ─── 2. v2-modular Baustein-Struktur ────────────────────────────────────────

def test_build_ewb_prompt_v2_modular_bausteine(db_session, monkeypatch,
                                                _empty_active_profile):
    _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(profile_data={}, anrede='Du',
                              version='v2-modular', user_id=1)
    for keyword in ['Anker', 'Reframe', 'Beweis', 'Ueberleitung',
                    'Active Listening', '45 Woerter']:
        assert keyword in out, f'missing keyword: {keyword}'


# ─── 3. Anrede='Du' → D-15 Constraint ───────────────────────────────────────

def test_build_ewb_prompt_anrede_du(db_session, monkeypatch, _empty_active_profile):
    _seed_ewb_variants(db_session)
    _bind(monkeypatch, db_session)
    out = ep.build_ewb_prompt(anrede='Du', version='v1-legacy')
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
