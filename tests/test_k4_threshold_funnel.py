"""
tests/test_k4_threshold_funnel.py
────────────────────────────────────────────────────────────────────
TAXO1-Welle 4 (K4, Cross-AI Finding #4) — pure-logic Regression der
K4-Funnel-Entscheidung config.should_abstain().

KEIN Live-Call, KEINE DB, KEIN LLM: echter Function-Call von should_abstain
(CLAUDE.md Test-Qualitaets-Regel — Function-Call-Return, KEIN Source-Presence).
Server-seitig via pytest lauffaehig.
"""

import pytest

from config import should_abstain


def test_low_conf_abstains_not_dropped():
    # low-conf -> abstained=True (der Aufrufer schreibt das Event mit abstained
    # statt es zu droppen — K4-Kern).
    assert should_abstain(confidence=0.40, threshold=0.55) is True


def test_high_conf_normal_emit():
    assert should_abstain(confidence=0.80, threshold=0.55) is False


def test_boundary_at_threshold():
    # >= threshold ist normal, knapp drunter ist abstain (Funnel-Grenze sauber).
    assert should_abstain(0.55, 0.55) is False
    assert should_abstain(0.5499, 0.55) is True


def test_none_confidence_abstains():
    # fehlende Confidence ist konservativ abstain, kein Crash.
    assert should_abstain(None, 0.55) is True


def test_env_default_threshold():
    # ohne explizites threshold nutzt should_abstain den ENV-Default; deckt die
    # ENV-Verdrahtung ab, ohne den exakten Default zu hardcoden.
    assert should_abstain(0.30) is True   # klar drunter -> abstain
    assert should_abstain(0.95) is False  # klar drueber -> normal
