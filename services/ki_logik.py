"""
Phase 04.8 — Deterministic KI-Logik primitives.

All functions in this module are pure Python (stdlib + typing only).
Haiku-backed helpers (phase classification, cold-call inference) live in
`services/claude_service.py` and are called by the analyse_loop alongside
these primitives.

Per decisions D-02, D-03, D-04, D-06 in
`.planning/phases/04.8-ki-logik-upgrade-inserted/04.8-CONTEXT.md`.

NOTE: `einwand_geloest` scores +20 per user override. The original briefing
(NERVE KI-Logik Kernarchitektur.md) specifies +15, but the user chose +20 to
reflect that a resolved objection is a stronger buy signal than a detail
question — the customer has actively removed a barrier.
"""
from typing import Optional


# ── Score factors (from NERVE KI-Logik Kernarchitektur.md briefing) ──────────
SCORE_FACTORS = {
    'detailfrage':       +15,
    'budget_erwaehnt':   +20,
    'naechster_schritt': +25,
    'zustimmung':        +10,
    'kaufsignal':        +15,
    'einwand_geloest':   +20,   # user override (+20 instead of briefing +15)
    'einwand_offen':     -10,
    'konkurrenz':        -15,
    'zeitdruck_kunde':   -20,
    'monosyllabisch':    -10,
}

SCORE_BASE = 30
SCORE_MIN, SCORE_MAX = 0, 100

# Bucket boundaries (inclusive on both ends). Ordered lo→hi.
BUCKETS = [
    (0,  30,  'cold'),
    (31, 60,  'warm'),
    (61, 80,  'hot'),
    (81, 100, 'closing'),
]

# Phase 1-6 EWB button sets from briefing tables (D-06).
PHASE_BUTTONS = {
    1: ["Keine Zeit", "Wer sind Sie?", "Kein Interesse",
        "Schicken Sie Unterlagen", "Nicht zuständig", "Rufen Sie später"],
    2: ["Kein Budget", "Nicht entscheidungsbefugt", "Haben schon Lösung",
        "Zeigen Sie mir etwas", "Brauchen wir nicht"],
    3: ["Wir haben keine Probleme", "Das läuft gut", "Kein Bedarf",
        "Zu abstrakt", "Wie meinen Sie das?"],
    4: ["Zu teuer", "Zu kompliziert", "Funktioniert das wirklich?",
        "Haben Sie Referenzen?", "Brauche Bedenkzeit"],
    5: ["Ja aber...", "Das verstehe ich nicht", "Überzeugt mich nicht",
        "Was wenn...", "Risiko zu hoch"],
    6: ["Ich überlege noch", "Schicken Sie Vertrag", "Rücksprache nötig",
        "Kein Termin heute", "Zu schnell"],
}

# Hint priority order from briefing (D-03). Lower number = higher importance.
HINT_PRIORITY = {
    'critical':   1,
    'kaufsignal': 2,
    'einwand':    3,
    'phase':      4,
    'tipp':       5,
}


def compute_readiness_score(state: dict, transcript_window: list) -> tuple:
    """Deterministic 0-100 readiness score + bucket from factor tally.

    Args:
        state: live_session.state dict (reads `score_factors_seen`).
        transcript_window: recent transcript lines (reserved for future use,
            e.g., tempo/redeanteil adjustments — currently unused).

    Returns:
        (score: int, bucket: str) where bucket in {'cold','warm','hot','closing'}.
    """
    score = SCORE_BASE
    factors = state.get('score_factors_seen', {}) or {}
    for key, delta in SCORE_FACTORS.items():
        count = factors.get(key, 0)
        score += delta * count
    score = max(SCORE_MIN, min(SCORE_MAX, score))

    bucket = 'cold'
    for lo, hi, name in BUCKETS:
        if lo <= score <= hi:
            bucket = name
            break
    return score, bucket


def select_active_hint(candidates: list) -> Optional[dict]:
    """Return hint with lowest priority number (=highest importance).

    First candidate wins on priority ties. Returns None if no valid candidates.

    Args:
        candidates: list of dicts, each with at least a 'priority' int field.
            None/falsy entries are ignored.
    """
    if not candidates:
        return None
    valid = [c for c in candidates if c and c.get('priority')]
    if not valid:
        return None
    # min() is stable → first occurrence of tied priority wins
    return min(valid, key=lambda c: c['priority'])


def dynamic_ewb_buttons(phase: int, base_buttons: Optional[list] = None) -> list:
    """Return the briefing-table button set for phase 1-6.

    Falls back to `base_buttons` (typically profile-defined) for unknown
    phases. Always returns a fresh list (never shares references with the
    module-level PHASE_BUTTONS dict).
    """
    if phase in PHASE_BUTTONS:
        return list(PHASE_BUTTONS[phase])
    return list(base_buttons or [])


# ── Stubs for Phase 04.8 P02/P03 implementation ──────────────────────────────

def detect_phase(raw_phase: int, raw_confidence: float,
                 current_phase: int, phase_change_count: int = 0,
                 cycles_since_change: int = 0) -> tuple:
    """Hysteresis rule for phase transitions (Phase 04.8 P02, RESEARCH §Q4).

    Returns (accepted_phase, accepted_confidence).

    Rules:
    - Same phase → pass through
    - Forward advance requires confidence >= 0.7
    - Regression is only allowed to Phase 5 (Einwandbehandlung) AND only with
      confidence >= 0.8 AND cycles_since_change >= 3 (3-cycle debounce) AND
      current_phase >= 2 (Phase 1 cannot regress).
    - All other regressions are blocked (flicker suppression).
    """
    if raw_phase == current_phase:
        return current_phase, raw_confidence
    if raw_phase > current_phase:
        if raw_confidence < 0.7:
            return current_phase, raw_confidence
        return raw_phase, raw_confidence
    # regression: only to phase 5, with strong evidence + debounce
    if (raw_phase == 5
            and raw_confidence >= 0.8
            and cycles_since_change >= 3
            and current_phase >= 2):
        return 5, raw_confidence
    return current_phase, raw_confidence


def infer_cold_call_context(seller_transcript, current_phase):
    """Infer customer state from seller-only audio (cold-call mode).

    Implemented in Phase 04.8 P03.
    """
    raise NotImplementedError("infer_cold_call_context lands in Phase 04.8 P03")
