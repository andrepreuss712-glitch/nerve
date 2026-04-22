"""Phase 08 Plan 03 — Task 1: claude_service.py EWB-Pipeline-Integration.

Statt echter Live-Call-Tests (wuerden Anthropic-API-Key brauchen) verwenden wir
source-level Introspection (`inspect.getsource`) um zu verifizieren dass die 2
Call-Sites `analysiere_mit_claude` und `analysiere_mit_claude_streaming` die
Phase-08-Pipeline nutzen:

  - Import von resolve_prompt_version + build_ewb_prompt
  - Beide Funktionen rufen build_ewb_prompt als `system=` Argument auf
  - resolve_prompt_version('ewb', ...) wird pro Call aufgeloest
  - Legacy-Symbole (_build_system_prompt, get_active_prompt_version,
    _ACTIVE_PROMPT_CACHE) bleiben erhalten fuer die 4 anderen Module
  - Haiku-Model bleibt in beiden Call-Sites (CLAUDE.md Sonnet-Regel)
"""
import inspect
import re


def test_phase08_imports_present():
    """Modul importiert resolve_prompt_version + build_ewb_prompt am Datei-Kopf."""
    import services.claude_service as cs
    src = inspect.getsource(cs)
    assert 'from services.prompt_pipeline import resolve_prompt_version' in src, \
        'resolve_prompt_version import fehlt'
    assert 'from services.ewb_pipeline import build_ewb_prompt' in src, \
        'build_ewb_prompt import fehlt'


def test_phase08_marker_present():
    """Kommentar-Marker 'Phase 08 EWB-Pipeline Integration' ist auffindbar."""
    import services.claude_service as cs
    src = inspect.getsource(cs)
    assert 'Phase 08 EWB-Pipeline Integration' in src, \
        'Phase 08 Marker-Kommentar fehlt'


def test_analysiere_mit_claude_uses_pipeline():
    """analysiere_mit_claude nutzt resolve_prompt_version + build_ewb_prompt."""
    import services.claude_service as cs
    src = inspect.getsource(cs.analysiere_mit_claude)
    assert "resolve_prompt_version('ewb'" in src, \
        "analysiere_mit_claude muss resolve_prompt_version('ewb', ...) nutzen"
    assert 'build_ewb_prompt(' in src, \
        'analysiere_mit_claude muss build_ewb_prompt(...) aufrufen'
    # Legacy _build_system_prompt() darf in diesem Funktionskoerper NICHT mehr fuer system= genutzt werden
    assert 'system=_build_system_prompt()' not in src, \
        'analysiere_mit_claude darf system=_build_system_prompt() NICHT mehr nutzen'


def test_analysiere_mit_claude_streaming_uses_pipeline():
    """analysiere_mit_claude_streaming nutzt ebenfalls die neue Pipeline."""
    import services.claude_service as cs
    src = inspect.getsource(cs.analysiere_mit_claude_streaming)
    assert "resolve_prompt_version('ewb'" in src, \
        "analysiere_mit_claude_streaming muss resolve_prompt_version('ewb', ...) nutzen"
    assert 'build_ewb_prompt(' in src, \
        'analysiere_mit_claude_streaming muss build_ewb_prompt(...) aufrufen'
    assert 'system=_build_system_prompt()' not in src, \
        'analysiere_mit_claude_streaming darf system=_build_system_prompt() NICHT mehr nutzen'


def test_haiku_model_preserved_in_both():
    """CLAUDE.md Sonnet-Regel: Live-Loop MUSS Haiku bleiben."""
    import services.claude_service as cs
    for fn in (cs.analysiere_mit_claude, cs.analysiere_mit_claude_streaming):
        src = inspect.getsource(fn)
        assert 'claude-haiku-4-5-20251001' in src, \
            f'{fn.__name__} muss Haiku-4-5-Model verwenden (Live-Loop-Constraint)'
        # Kein Sonnet/Opus im Live-Call-Body (erlaubt sind nur String-Literals, keine Model-IDs)
        assert not re.search(r'model\s*=\s*["\']claude-sonnet', src), \
            f'{fn.__name__} darf kein Sonnet-Model im Live-Call verwenden'
        assert not re.search(r'model\s*=\s*["\']claude-opus', src), \
            f'{fn.__name__} darf kein Opus-Model im Live-Call verwenden'


def test_legacy_symbols_preserved():
    """_build_system_prompt, get_active_prompt_version, _ACTIVE_PROMPT_CACHE
    bleiben fuer die 4 anderen Module erhalten (assistant_live, coaching_live,
    objection_trigger, api_frage, training_persona).
    """
    import services.claude_service as cs
    assert hasattr(cs, '_build_system_prompt'), \
        '_build_system_prompt darf NICHT entfernt werden (Legacy-Module brauchen es)'
    assert hasattr(cs, 'get_active_prompt_version'), \
        'get_active_prompt_version darf NICHT entfernt werden'
    assert hasattr(cs, '_ACTIVE_PROMPT_CACHE'), \
        '_ACTIVE_PROMPT_CACHE darf NICHT entfernt werden'
    # Der Cache muss ein Dict sein
    assert isinstance(cs._ACTIVE_PROMPT_CACHE, dict), \
        '_ACTIVE_PROMPT_CACHE muss ein Dict bleiben'


def test_import_smoke_no_side_effects():
    """`from services.claude_service import analysiere_mit_claude` triggert
    keinen Crash und keine DB-I/O beim Import.
    """
    # Re-Import via sys.modules-Reset wird hier nicht benoetigt — Import ist bereits
    # in obigen Tests passiert. Dieser Test verifiziert nur dass alle Exports
    # als Callables verfuegbar sind.
    from services.claude_service import (
        analysiere_mit_claude,
        analysiere_mit_claude_streaming,
    )
    assert callable(analysiere_mit_claude)
    assert callable(analysiere_mit_claude_streaming)
