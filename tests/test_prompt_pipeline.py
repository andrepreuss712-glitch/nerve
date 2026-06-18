"""Phase 08 unit tests for services/prompt_pipeline.py."""
import os
import sys
import threading
import time
import uuid

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


# ── Phase 08.23.2.PGTEST Gruppe A — unique test-module gegen UNIQUE(version,module) ──────
# resolve_prompt_version(module, user_id) nimmt das Modul als PARAMETER. Welle 6: der ewb-Seeder
# _seed_ewb_v2 ist entfernt — die app-import-Baseline traegt 'ewb' nicht mehr. Trotzdem bleibt ein
# UNIQUE test-eigener module-Name pro Run die robuste Wahl (baseline-unabhaengig, kollisionsfrei).
# Ein Re-Seed unter einem bereits geseedeten Modul braeche auf UNIQUE(version,module)=uq_prompt_version_module
# (models.py:483) UND machte das deterministische Routing von einer ggf. wachsenden Baseline-Varianten-
# Menge abhaengig (Index-Shift bei kuenftiger 3. ewb-Variante). FIX: ein UNIQUE test-eigener
# module-Name pro Run → keine Kollision, deterministisch genau 2 Varianten, baseline-unabhaengig.
# db_session ist rollback-covered (D-03) → kein cleanup_rows noetig.
def _seed_variants(db_session, module=None, versions=('v1-legacy', 'v2-modular')):
    """Seed active variants under a UNIQUE test-module. Returns the module name to route against."""
    if module is None:
        module = f'ewb-test-{uuid.uuid4().hex[:8]}'
    for v in versions:
        db_session.add(PromptVersion(
            module=module, version=v, prompt_text=f'text-{v}',
            is_active=True, is_default=(v == versions[0]),
            changelog=f'test-{v}',
        ))
    db_session.commit()
    return module


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
    # Welle 6: generischer ENV-Override-Test (Mechanismus PROMPT_{MODULE}_VERSION_OVERRIDE),
    # auf ein lebendes Modul (classifier) umgestellt — 'ewb' ist ausgemustert.
    monkeypatch.setenv('PROMPT_CLASSIFIER_VERSION_OVERRIDE', 'v-override')
    # ENV wins — must never touch DB:
    assert pp.resolve_prompt_version('classifier', user_id=42) == 'v-override'


# ─── 2. Deterministic routing (user_id % N) ─────────────────────────────────

def test_deterministic_routing_even_user(db_session, monkeypatch):
    module = _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    # Sorted alphabetically: ['v1-legacy', 'v2-modular']; user_id=0 -> index 0
    assert pp.resolve_prompt_version(module, user_id=0) == 'v1-legacy'


def test_deterministic_routing_odd_user(db_session, monkeypatch):
    module = _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    # user_id=1 -> index 1
    assert pp.resolve_prompt_version(module, user_id=1) == 'v2-modular'


# ─── 3. Cache-per-user key (W-7 regression-guard) ───────────────────────────

def test_cache_per_user_key(db_session, monkeypatch):
    module = _seed_variants(db_session)
    _bind(monkeypatch, db_session)
    r0 = pp.resolve_prompt_version(module, user_id=0)
    r1 = pp.resolve_prompt_version(module, user_id=1)
    assert r0 != r1, "different user_ids must land on different variants"
    assert (module, 0) in pp._RESOLVER_CACHE
    assert (module, 1) in pp._RESOLVER_CACHE


# ─── 4. No-variants fallback ────────────────────────────────────────────────

def test_no_variants_returns_unknown(db_session, monkeypatch):
    # empty prompt_versions table for a new module:
    _bind(monkeypatch, db_session)
    assert pp.resolve_prompt_version('nonexistent_module', user_id=0) == 'unknown'


# ─── 5. Cache invalidation ───────────────────────────────────────────────────

def test_invalidate_resolver_cache_clears_both():
    # Welle 6: 'ewb' (ausgemustert) → 'classifier' als generischer Sample-Cache-Key.
    pp._RESOLVER_CACHE[('classifier', 0)] = 'cached'
    pp._VARIANTS_CACHE['classifier'] = ['x', 'y']
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


# ─── 6. build_profile_context: empty-profile → 9 sections with markers (D-01) ──

def test_build_profile_context_no_active_profile(monkeypatch):
    """D-01: Even with no active profile (empty pdata), all 9 section headers must appear
    with (noch nicht ausgefüllt) markers. Never return empty string — sections are non-negotiable."""

    class _LSMock:
        state = {}
        state_lock = __import__('threading').Lock()
        _session_state = {}
        _session_state_lock = __import__('threading').Lock()
        _per_sid_profile = {}
        _per_sid_lock = __import__('threading').Lock()

        @staticmethod
        def get_profile_for_sid(sid):
            return ('', {})

        @staticmethod
        def get_briefing_for_sid(sid):
            return None

    _install_ls_mock(monkeypatch, _LSMock)
    # sid=None, user_id=0 → no DB fallback triggered (user_id=0 is falsy)
    out = pp.build_profile_context(user_id=0)
    # D-01: all 9 section headers must be present even for empty profile
    for section in ['## Branche', '## Basis', '## Zielkunde', '## Schmerzen',
                    '## Einwände', '## Phasen', '## KI-Verhalten',
                    '## PreCall-Briefing', '## Lead-Kontext']:
        assert section in out, f"Missing section {section!r} even for empty profile"
    assert '(noch nicht ausgefüllt)' in out


# ─── 7. build_profile_context: new Phase-08 fields (D-07/D-08/D-11) ─────────

def test_build_profile_context_includes_phase_08_fields(monkeypatch):
    _SID = 'test-build-profile-phase08-sid'
    import threading as _t

    class _LSMock:
        state = {}
        state_lock = _t.Lock()
        _session_state = {_SID: {'user_id': 1, 'org_id': 1, '_briefing': None, '_profile_cache': {}}}
        _session_state_lock = _t.Lock()
        _per_sid_profile = {}
        _per_sid_lock = _t.Lock()

        @staticmethod
        def get_profile_for_sid(sid):
            if sid == _SID:
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
            return ('', {})

        @staticmethod
        def get_briefing_for_sid(sid):
            return None

    _install_ls_mock(monkeypatch, _LSMock)
    out = pp.build_profile_context(user_id=1, sid=_SID)
    assert 'Firma XY' in out
    assert 'Testprodukt' in out
    assert 'Maschinenbau-Mittelstand' in out
    assert 'Darf ich fragen, was Sie einsetzen?' in out
    assert '15% mehr Abschluesse' in out


# ─── 8. Anrede-Resolution: Session > Profile > 'Sie' ────────────────────────

def test_build_profile_context_anrede_session_override_wins(monkeypatch):
    _SID = 'test-anrede-override-sid'
    import threading as _t

    class _LSMock:
        state = {'session_anrede': 'Du'}
        state_lock = _t.Lock()
        _session_state = {_SID: {'user_id': 1, 'org_id': 1, '_briefing': None,
                                  '_profile_cache': {}, 'session_anrede': 'Du'}}
        _session_state_lock = _t.Lock()
        _per_sid_profile = {}
        _per_sid_lock = _t.Lock()

        @staticmethod
        def get_profile_for_sid(sid):
            if sid == _SID:
                return (1, {'basis': {}, 'ki': {'ansprache': 'Sie'}})
            return ('', {})

        @staticmethod
        def get_briefing_for_sid(sid):
            return None

    _install_ls_mock(monkeypatch, _LSMock)
    out = pp.build_profile_context(user_id=1, sid=_SID)
    assert 'Anrede: Du.' in out
    assert 'Wechsle NIEMALS' in out


# ─── 9. 9-Sektionen-Output (D-01) ───────────────────────────────────────────

_MOCK_PROFILE_FULL = {
    'schema_version': 4,
    'basis': {
        'unternehmen': 'TestCo GmbH',
        'produktbeschreibung': 'SaaS-Tool fuer Vertrieb',
        'branche': 'IT/SaaS',
        'preismodell': '99 EUR/Monat',
        'konsequenz': 'Kein Wachstum',
        'usps': ['Schnell', 'Guenstig'],
        'eigene_formulierungen': ['Darf ich fragen...'],
        'beweise': ['Firma Z: +15%'],
    },
    'einwaende_detail': [
        {
            'einwand': 'Preis zu hoch',
            'einwand_typ': 'echt',
            'gegenargument': 'ROI in 6 Monaten',
            'varianten': [],
            'technik': '',
            'intensitaet': 3,
            'kurzlabel': '',
            'kategorie': '',
        }
    ],
    'phasen': [{'name': 'Erstgespraech'}, {'name': 'Demo'}],
    'ki': {'ansprache': 'Sie', 'ton': 'professionell'},
    'zielkunde': {'unternehmensgroesse': 'KMU'},
    'schmerzen': {'s1': 'Zu viel manuelle Arbeit'},
}

_MOCK_CACHE = {
    'opener_content': 'Guten Tag, ich bin...',
    'user_firstname': 'Max',
    'faqs': [{'q': 'Was kostet es?', 'a': '99 EUR/Monat'}],
}


def _make_ls_mock_9sections(sid, profile=None, cache=None, briefing=None):
    """Create an ls-mock that returns the given profile + _profile_cache for sid."""
    import types
    mock = types.SimpleNamespace()
    mock.state = {}
    mock.state_lock = threading.Lock()
    _ss = {sid: {'user_id': 1, 'org_id': 1, '_briefing': briefing,
                 '_profile_cache': cache or {}}}
    mock._session_state = _ss
    mock._session_state_lock = threading.Lock()
    mock._per_sid_profile = {sid: ('TestCo', profile or {})}
    mock._per_sid_lock = threading.Lock()

    def _get_profile_for_sid(s):
        return mock._per_sid_profile.get(s, ('', {}))
    mock.get_profile_for_sid = _get_profile_for_sid

    def _get_briefing_for_sid(s):
        with mock._session_state_lock:
            return mock._session_state.get(s, {}).get('_briefing')
    mock.get_briefing_for_sid = _get_briefing_for_sid

    def _pop_session_state(s):
        with mock._session_state_lock:
            mock._session_state.pop(s, None)
        with mock._per_sid_lock:
            mock._per_sid_profile.pop(s, None)
    mock.pop_session_state = _pop_session_state

    return mock


def test_build_profile_context_9sections_present(monkeypatch):
    """D-01: all 9 ## section headers must be present in fixed order."""
    _SID = 'test-9sec-sid'
    ls_mock = _make_ls_mock_9sections(_SID, _MOCK_PROFILE_FULL, _MOCK_CACHE)
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)

    expected_sections = [
        '## Branche', '## Basis', '## Zielkunde', '## Schmerzen',
        '## Einwände', '## Phasen', '## KI-Verhalten',
        '## PreCall-Briefing', '## Lead-Kontext',
    ]
    for section in expected_sections:
        assert section in out, f"Missing section: {section!r}"

    # Verify order is correct
    positions = [out.index(s) for s in expected_sections]
    assert positions == sorted(positions), "Sections out of order"


def test_build_profile_context_deterministic(monkeypatch):
    """D-01: byte-equal output for identical input (determinism required for cache-stability)."""
    _SID = 'test-determ-sid'
    ls_mock = _make_ls_mock_9sections(_SID, _MOCK_PROFILE_FULL, _MOCK_CACHE)
    _install_ls_mock(monkeypatch, ls_mock)

    r1 = pp.build_profile_context(user_id=1, sid=_SID)
    r2 = pp.build_profile_context(user_id=1, sid=_SID)
    assert r1 == r2, "build_profile_context must be deterministic (byte-equal for identical input)"


def test_build_profile_context_empty_section_not_skipped(monkeypatch):
    """Empty schmerzen section must render marker, not be silently skipped."""
    _SID = 'test-empty-schmerzen-sid'
    profile_no_schmerzen = {
        'schema_version': 4,
        'basis': {'unternehmen': 'TestCo'},
        'ki': {'ansprache': 'Sie'},
        # schmerzen deliberately absent
    }
    ls_mock = _make_ls_mock_9sections(_SID, profile_no_schmerzen, {})
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    assert '## Schmerzen' in out, "## Schmerzen header must always appear"
    assert '(noch nicht ausgefüllt)' in out, "Empty section must show marker"


def test_build_profile_context_einwaende_format(monkeypatch):
    """Einwände items must be formatted as '- {einwand} ({einwand_typ}) | {gegenargument}'."""
    _SID = 'test-einwaende-fmt-sid'
    ls_mock = _make_ls_mock_9sections(_SID, _MOCK_PROFILE_FULL, _MOCK_CACHE)
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    assert '- Preis zu hoch (echt) | ROI in 6 Monaten' in out, \
        "Einwände format must be '- {einwand} ({einwand_typ}) | {gegenargument}'"


def test_build_profile_context_precall_briefing_empty_marker(monkeypatch):
    """## PreCall-Briefing must show '(noch nicht erstellt)' when no briefing set."""
    _SID = 'test-precall-empty-sid'
    ls_mock = _make_ls_mock_9sections(_SID, _MOCK_PROFILE_FULL, _MOCK_CACHE, briefing=None)
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    assert '## PreCall-Briefing' in out
    assert '(noch nicht erstellt)' in out


def test_build_profile_context_warm_cache_latency(monkeypatch):
    """HIGH-3: build_profile_context() with warm _profile_cache must complete in < 5ms."""
    import services.live_session as _real_ls

    sid = 'latency-test-sid-08.20'
    mock_cache = {
        'opener_content': 'Guten Tag, ich bin...',
        'user_firstname': 'Max',
        'faqs': [{'q': 'Was kostet es?', 'a': '99 EUR/Monat'}],
    }

    with _real_ls._session_state_lock:
        _real_ls._session_state[sid] = {
            'user_id': 1, 'org_id': 1,
            '_briefing': None,
            '_profile_cache': mock_cache,
        }
    with _real_ls._per_sid_lock:
        _real_ls._per_sid_profile[sid] = ('TestCo', _MOCK_PROFILE_FULL)

    try:
        # Warm-up (module load, caches)
        pp.build_profile_context(user_id=1, sid=sid)

        # Timed call — must be < 5ms (hot path: no DB)
        start = time.perf_counter()
        result = pp.build_profile_context(user_id=1, sid=sid)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 5, \
            f"Expected < 5ms warm-cache latency, got {elapsed_ms:.1f}ms — DB query in hot path?"
        assert '## Branche' in result
        assert '## PreCall-Briefing' in result
        print(f'test_build_profile_context_warm_cache_latency: PASS ({elapsed_ms:.2f}ms)')
    finally:
        _real_ls.pop_session_state(sid)


# ── Issue 1: Profile.branche DB-Column via _profile_cache (Phase 08.20 Hotfix) ──

def test_build_profile_context_branche_from_db_column(monkeypatch):
    """Issue 1: branche from _profile_cache['profile_branche'] wins over daten JSON.
    After Phase 08.19.1 the branche field lives in Profile.branche (DB column),
    not in daten['basis']['branche']. build_profile_context must read it from cache."""
    _SID = 'test-branche-db-col-sid'
    profile_no_branche_in_json = {
        'schema_version': 4,
        'basis': {'unternehmen': 'TestCo'},   # no 'branche' key
        'ki': {'ansprache': 'Sie'},
    }
    cache_with_branche = {
        'opener_content': None,
        'user_firstname': '',
        'faqs': [],
        'profile_branche': 'IT-Dienstleistung',
    }
    ls_mock = _make_ls_mock_9sections(_SID, profile_no_branche_in_json, cache_with_branche)
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    branche_section = out.split('## Branche')[1].split('##')[0] if '## Branche' in out else ''
    assert 'IT-Dienstleistung' in branche_section, \
        "Branche must be read from _profile_cache['profile_branche'] (DB column)"
    assert '(noch nicht ausgefüllt)' not in branche_section, \
        "Branche section must not show empty-marker when profile_branche is set"


# ── Issue 2: Schmerzen list-of-dict — no Python dict repr in output ────────────

def test_build_profile_context_schmerzen_dict_with_list_value(monkeypatch):
    """Block J: schmerzen={'schmerzpunkte': [...list-of-dict...]} must render Markdown,
    not Python list repr — the dict-branch must delegate list values to dict-item logic."""
    _SID = 'test-schmerzen-dict-list-sid'
    profile_dict_list_schmerzen = {
        'schema_version': 4,
        'basis': {'unternehmen': 'TestCo'},
        'ki': {'ansprache': 'Sie'},
        'schmerzen': {'schmerzpunkte': [
            {'situation': 'X', 'kern': 'Y', 'verstaerken': 'Z'},
        ]},
    }
    ls_mock = _make_ls_mock_9sections(_SID, profile_dict_list_schmerzen, {})
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    schmerzen_section = out.split('## Schmerzen')[1].split('##')[0] if '## Schmerzen' in out else ''
    assert '[{' not in schmerzen_section, "Must not contain Python list repr"
    assert "{'situation'" not in schmerzen_section, "Must not contain Python dict repr"
    assert '**Situation:** X' in schmerzen_section, "Situation must render as Markdown"
    assert '**Kern:** Y' in schmerzen_section, "Kern must render as Markdown"
    assert '**Verstärken:** Z' in schmerzen_section, "Verstaerken must render as Markdown"


def test_build_profile_context_schmerzen_no_dict_repr(monkeypatch):
    """Issue 2: Schmerzen list-of-dict items must render as Markdown, not str(dict)."""
    _SID = 'test-schmerzen-dict-sid'
    profile_dict_schmerzen = {
        'schema_version': 4,
        'basis': {'unternehmen': 'TestCo'},
        'ki': {'ansprache': 'Sie'},
        'schmerzen': [
            {'situation': 'Keine Zeit', 'kern': 'Burnout-Risiko', 'verstaerken': 'Kosten steigen'},
            {'situation': 'Hohe Fluktuation', 'kern': 'Know-how verloren'},
        ],
    }
    ls_mock = _make_ls_mock_9sections(_SID, profile_dict_schmerzen, {})
    _install_ls_mock(monkeypatch, ls_mock)

    out = pp.build_profile_context(user_id=1, sid=_SID)
    schmerzen_section = out.split('## Schmerzen')[1].split('##')[0] if '## Schmerzen' in out else ''
    assert "[{'" not in schmerzen_section and "{'situation'" not in schmerzen_section, \
        "Schmerzen must not contain Python dict repr strings"
    assert 'Keine Zeit' in schmerzen_section, \
        "Schmerzen situation text must appear in output"
    assert 'Burnout-Risiko' in schmerzen_section, \
        "Schmerzen kern text must appear in output"

