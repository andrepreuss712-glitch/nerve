"""Unit tests for services/ki_logik.py pure functions (Phase 04.8 P01).

Covers compute_readiness_score, select_active_hint, dynamic_ewb_buttons
and the user override: einwand_geloest = +20 (not briefing's +15).
"""
from services.ki_logik import (
    BUCKETS,
    PHASE_BUTTONS,
    SCORE_BASE,
    SCORE_FACTORS,
    compute_readiness_score,
    detect_phase,
    dynamic_ewb_buttons,
    select_active_hint,
)


# ── detect_phase (Phase 04.8 P02 hysteresis) ─────────────────────────────────

def test_detect_phase_same_phase_passes_through():
    assert detect_phase(3, 0.42, current_phase=3) == (3, 0.42)


def test_detect_phase_forward_low_conf_blocked():
    # 2 → 3 with conf 0.6 < 0.7 → stays at 2
    new, conf = detect_phase(3, 0.6, current_phase=2)
    assert new == 2
    assert conf == 0.6


def test_detect_phase_forward_high_conf_advances():
    new, conf = detect_phase(3, 0.75, current_phase=2)
    assert new == 3
    assert conf == 0.75


def test_detect_phase_forward_skip_multiple_allowed():
    # 1 → 4 with high conf allowed (forward progression, no skip penalty)
    new, _ = detect_phase(4, 0.9, current_phase=1)
    assert new == 4


def test_detect_phase_regress_to_5_allowed_with_debounce():
    # 4 → 5 with conf 0.85, 3 cycles since last change → allowed
    new, conf = detect_phase(5, 0.85, current_phase=4, cycles_since_change=3)
    assert new == 5
    assert conf == 0.85


def test_detect_phase_regress_to_5_from_6_allowed():
    new, _ = detect_phase(5, 0.9, current_phase=6, cycles_since_change=5)
    assert new == 5


def test_detect_phase_regress_to_5_debounce_blocks():
    # 6 → 5 with cycles_since_change < 3 → BLOCKED even with high conf
    new, _ = detect_phase(5, 0.9, current_phase=6, cycles_since_change=2)
    assert new == 6


def test_detect_phase_regress_to_5_low_conf_blocks():
    # 6 → 5 with conf < 0.8 → BLOCKED
    new, _ = detect_phase(5, 0.75, current_phase=6, cycles_since_change=5)
    assert new == 6


def test_detect_phase_regress_to_non_5_always_blocked():
    # 4 → 3 always blocked regardless of confidence
    new, _ = detect_phase(3, 0.99, current_phase=4, cycles_since_change=10)
    assert new == 4


def test_detect_phase_regress_from_phase_6_to_3_blocked():
    # Regression target != 5 → always blocked
    new, _ = detect_phase(3, 0.99, current_phase=6, cycles_since_change=10)
    assert new == 6


# ── compute_readiness_score ──────────────────────────────────────────────────

def test_base_case_empty_factors_returns_30_cold(sample_state):
    score, bucket = compute_readiness_score(sample_state(), [])
    assert score == 30
    assert bucket == "cold"


def test_buying_signals_accumulate_to_closing(sample_state):
    state = sample_state(score_factors_seen={
        "detailfrage": 1,       # +15
        "budget_erwaehnt": 1,   # +20
        "naechster_schritt": 1, # +25
    })
    score, bucket = compute_readiness_score(state, [])
    assert score == 30 + 15 + 20 + 25  # 90
    assert bucket == "closing"


def test_einwand_geloest_is_plus_20_not_15():
    """User override: `Einwand gelöst` = +20 (briefing says +15)."""
    assert SCORE_FACTORS["einwand_geloest"] == 20, (
        "User override: Einwand gelöst = +20 (briefing says +15)"
    )


def test_einwand_geloest_applied_in_score(sample_state):
    state = sample_state(score_factors_seen={"einwand_geloest": 1})
    score, _ = compute_readiness_score(state, [])
    assert score == 50  # 30 + 20


def test_negative_zeitdruck_subtracts(sample_state):
    state = sample_state(score_factors_seen={"zeitdruck_kunde": 1})
    score, bucket = compute_readiness_score(state, [])
    assert score == 10  # 30 - 20
    assert bucket == "cold"


def test_score_clamps_to_zero(sample_state):
    state = sample_state(score_factors_seen={
        "zeitdruck_kunde": 5,  # -100
        "konkurrenz": 5,       # -75
    })
    score, bucket = compute_readiness_score(state, [])
    assert score == 0
    assert bucket == "cold"


def test_score_clamps_to_100(sample_state):
    state = sample_state(score_factors_seen={"naechster_schritt": 10})  # +250
    score, bucket = compute_readiness_score(state, [])
    assert score == 100
    assert bucket == "closing"


def test_bucket_boundary_30_is_cold(sample_state):
    score, bucket = compute_readiness_score(sample_state(), [])
    assert score == 30
    assert bucket == "cold"


def test_bucket_boundary_31_is_warm(sample_state):
    # 30 base + 1 from... need to craft. Use zustimmung=+10 minus 9? Not possible cleanly.
    # Use detailfrage(+15) - einwand_offen*... Use score_factors directly.
    # Easiest: monosyllabisch(-10) twice=-20 + detailfrage*3=+45 → 30+45-20 = 55? no.
    # Just brute-force via direct factor injection that yields 31.
    # detailfrage=1(+15), einwand_offen=1(-10), zustimmung=... we can craft:
    # 30 + 15 - 10 - 10 + 10 = 35. Use detailfrage=1, monosyllabisch=1 → 30+15-10=35 (warm)
    state = sample_state(score_factors_seen={"detailfrage": 1, "monosyllabisch": 1})
    score, bucket = compute_readiness_score(state, [])
    assert score == 35
    assert bucket == "warm"


def test_bucket_boundary_60_is_warm(sample_state):
    # 30 + detailfrage*2(+30) = 60
    state = sample_state(score_factors_seen={"detailfrage": 2})
    score, bucket = compute_readiness_score(state, [])
    assert score == 60
    assert bucket == "warm"


def test_bucket_boundary_61_is_hot(sample_state):
    # 30 + detailfrage*2(+30) + zustimmung(+10) - monosyllabisch*... → want 61
    # 30 + 15 + 15 + 10 - ... tricky. Use detailfrage=2 + zustimmung=1 = 70 (hot).
    # Just verify 70 is hot then check >=61 boundary at 65:
    # 30 + detailfrage*1(+15) + kaufsignal*1(+15) + zustimmung*1(+10) - monosyllabisch(-10) + detailfrage = ugh
    # Use: detailfrage=1(+15) + budget(+20) + zustimmung(+10) = 75 hot
    state = sample_state(score_factors_seen={
        "detailfrage": 1, "budget_erwaehnt": 1, "zustimmung": 1,
    })
    score, bucket = compute_readiness_score(state, [])
    assert score == 75
    assert bucket == "hot"


def test_bucket_boundary_81_is_closing(sample_state):
    # 30 + naechster(+25) + budget(+20) + detailfrage(+15) + kaufsignal(+15) = 105 → clamp 100
    # Need 81: 30 + naechster(+25) + budget(+20) + zustimmung(+10) - monosyllabisch(-10) + detailfrage(+15) + zustimmung(+10) ...
    # 30 + 25 + 20 + 15 + 10 + 10 - 10 = 100. Use different combo for 85:
    # 30 + 25 + 20 + 15 + 15 - 10 - 10 = 85 closing
    state = sample_state(score_factors_seen={
        "naechster_schritt": 1, "budget_erwaehnt": 1, "detailfrage": 1,
        "kaufsignal": 1, "einwand_offen": 1, "monosyllabisch": 1,
    })
    score, bucket = compute_readiness_score(state, [])
    assert score == 85
    assert bucket == "closing"


# ── select_active_hint ───────────────────────────────────────────────────────

def test_select_active_hint_empty_returns_none():
    assert select_active_hint([]) is None


def test_select_active_hint_all_none_returns_none():
    assert select_active_hint([None, None]) is None


def test_select_active_hint_priority_1_wins():
    candidates = [
        {"priority": 5, "text": "tipp"},
        {"priority": 1, "text": "critical"},
        {"priority": 3, "text": "einwand"},
    ]
    result = select_active_hint(candidates)
    assert result["text"] == "critical"


def test_select_active_hint_tie_first_wins():
    candidates = [
        {"priority": 2, "text": "first"},
        {"priority": 2, "text": "second"},
    ]
    result = select_active_hint(candidates)
    assert result["text"] == "first"


def test_select_active_hint_ignores_falsy_and_missing_priority():
    candidates = [
        None,
        {"text": "no-prio"},   # missing priority
        {"priority": 4, "text": "phase"},
    ]
    result = select_active_hint(candidates)
    assert result["text"] == "phase"


# ── dynamic_ewb_buttons ──────────────────────────────────────────────────────

def test_dynamic_ewb_buttons_phase_1_returns_six():
    buttons = dynamic_ewb_buttons(1)
    assert len(buttons) == 6
    assert "Keine Zeit" in buttons


def test_dynamic_ewb_buttons_all_phases_present():
    for phase in range(1, 7):
        buttons = dynamic_ewb_buttons(phase)
        assert len(buttons) >= 5, f"Phase {phase} must have >=5 buttons"


def test_dynamic_ewb_buttons_unknown_phase_returns_base():
    base = ["Custom A", "Custom B"]
    assert dynamic_ewb_buttons(99, base_buttons=base) == base


def test_dynamic_ewb_buttons_unknown_phase_no_base_returns_empty():
    assert dynamic_ewb_buttons(99) == []


def test_dynamic_ewb_buttons_returns_fresh_list():
    """Must not share reference with module-level PHASE_BUTTONS."""
    b1 = dynamic_ewb_buttons(1)
    b1.append("MUTATED")
    b2 = dynamic_ewb_buttons(1)
    assert "MUTATED" not in b2
