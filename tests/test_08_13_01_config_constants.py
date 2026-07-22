"""Phase 08.13 Plan 01 — Test: MODEL_*-Konstanten + CACHE_*-Booleans in config.py.

RED: Alle Assertions schlagen fehl, solange config.py die Konstanten nicht hat.
GREEN: Alle Assertions bestehen nach Einfuegen des Konstantenblocks.
"""
import os
import importlib
import pytest


def fresh_config():
    """Importiert config frisch (ohne gecachte ENV-Overrides)."""
    import config
    importlib.reload(config)
    return config


class TestModelConstants:
    """Sonnet-Konstanten defaulten auf 'claude-sonnet-4-5'."""

    def test_model_ewb_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_EWB == 'claude-sonnet-4-5'

    def test_model_qa_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_QA == 'claude-sonnet-4-5'

    def test_model_postcall_insights_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_POSTCALL_INSIGHTS == 'claude-sonnet-4-5'

    def test_model_postcall_analysis_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_POSTCALL_ANALYSIS == 'claude-sonnet-4-5'

    def test_model_weekly_summary_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_WEEKLY_SUMMARY == 'claude-sonnet-4-5'

    def test_model_precall_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_PRECALL == 'claude-sonnet-4-5'

    def test_model_crm_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_CRM == 'claude-sonnet-4-5'

    def test_model_training_help_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_TRAINING_HELP == 'claude-sonnet-4-5'

    def test_model_training_scoring_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_TRAINING_SCORING == 'claude-sonnet-4-5'


class TestHaikuConstants:
    """Haiku-Konstanten defaulten auf 'claude-haiku-4-5-20251001'."""

    def test_model_analyse_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_ANALYSE == 'claude-haiku-4-5-20251001'

    def test_model_training_dialog_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_TRAINING_DIALOG == 'claude-haiku-4-5-20251001'

    def test_model_personality_gen_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_PERSONALITY_GEN == 'claude-haiku-4-5-20251001'

    def test_model_phase_classify_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_PHASE_CLASSIFY == 'claude-haiku-4-5-20251001'

    def test_model_coldcall_infer_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_COLDCALL_INFER == 'claude-haiku-4-5-20251001'

    def test_model_pip_autovar_default(self):
        # Phase 08.23.2.PGTEST.GREEN Muster D: PiP-Modelle default jetzt Sonnet (D-07 DSGVO/Qualitaet,
        # config.py:68 verifiziert) — Haiku-Rollback nur via ENV. Test an Sonnet-Default nachgezogen.
        cfg = fresh_config()
        assert cfg.MODEL_PIP_AUTOVAR == 'claude-sonnet-4-5'

    def test_model_pip_variante_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_PIP_VARIANTE == 'claude-sonnet-4-5'

    def test_model_coaching_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_COACHING == 'claude-haiku-4-5-20251001'

    def test_model_validate_user_text_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_VALIDATE_USER_TEXT == 'claude-haiku-4-5-20251001'

    def test_model_training_preview_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_TRAINING_PREVIEW == 'claude-haiku-4-5-20251001'


class TestCacheBooleans:
    """TEMPO-1: EIN Cache-Schalter (CACHE_ANTWORT) statt der drei abgeloesten
    CACHE_EWB/CACHE_QA/CACHE_ANALYSE. Der Vertrag hat sich geaendert, der Test wird
    nachgezogen (CLAUDE.md Punkt 18) — nicht ersatzlos entfernt."""

    def test_cache_antwort_default_true(self):
        cfg = fresh_config()
        assert cfg.CACHE_ANTWORT is True

    def test_cache_antwort_is_bool_type(self):
        cfg = fresh_config()
        assert isinstance(cfg.CACHE_ANTWORT, bool)

    def test_cache_antwort_env_override_false(self, monkeypatch):
        """Rollback-Pfad ohne Deploy (CLAUDE.md Punkt 12): ENV CACHE_ANTWORT=false."""
        monkeypatch.setenv('CACHE_ANTWORT', 'false')
        import importlib
        import config
        importlib.reload(config)
        assert config.CACHE_ANTWORT is False
        monkeypatch.delenv('CACHE_ANTWORT', raising=False)
        importlib.reload(config)
        assert config.CACHE_ANTWORT is True

    def test_abgeloeste_schalter_sind_weg(self):
        """Die drei alten Schalter duerfen NICHT wieder auftauchen — sonst kehrt die
        'zwei Schalter fuer einen Cache-Eintrag'-Luege zurueck (B2)."""
        cfg = fresh_config()
        for _tot in ('CACHE_EWB', 'CACHE_QA', 'CACHE_ANALYSE'):
            assert not hasattr(cfg, _tot), f'{_tot} lebt wieder — TEMPO-1 rueckgaengig gemacht?'


class TestEnvOverride:
    """ENV-Override funktioniert fuer MODEL_EWB."""

    def test_model_ewb_env_override(self, monkeypatch):
        monkeypatch.setenv('MODEL_EWB', 'claude-opus-4-5')
        import config
        importlib.reload(config)
        assert config.MODEL_EWB == 'claude-opus-4-5'
        # Cleanup: reload ohne Override
        monkeypatch.delenv('MODEL_EWB', raising=False)
        importlib.reload(config)
