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
        cfg = fresh_config()
        assert cfg.MODEL_PIP_AUTOVAR == 'claude-haiku-4-5-20251001'

    def test_model_pip_variante_default(self):
        cfg = fresh_config()
        assert cfg.MODEL_PIP_VARIANTE == 'claude-haiku-4-5-20251001'

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
    """CACHE_*-Booleans haben die korrekten Defaults."""

    def test_cache_ewb_default_true(self):
        cfg = fresh_config()
        assert cfg.CACHE_EWB is True

    def test_cache_qa_default_true(self):
        cfg = fresh_config()
        assert cfg.CACHE_QA is True

    def test_cache_analyse_default_false(self):
        cfg = fresh_config()
        assert cfg.CACHE_ANALYSE is False

    def test_cache_booleans_are_bool_type(self):
        cfg = fresh_config()
        assert isinstance(cfg.CACHE_EWB, bool)
        assert isinstance(cfg.CACHE_QA, bool)
        assert isinstance(cfg.CACHE_ANALYSE, bool)


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
