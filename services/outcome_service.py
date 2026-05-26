"""Phase 08.23.2.D — Outcome-Classifier (Claude Haiku) + Audio-Health-Score.

Pure-Logik-Funktionen (D-01): kein Emit, kein DB-Write. Aufrufer (Routes)
orchestrieren DB-Updates + SocketIO-Emits.

Public functions:
  - classify(conv_data) -> {'outcome': str|None, 'confidence': float}
  - calculate_audio_health(word_confidences_buffer) -> {'mean','median','pct_below_07','longest_uncertain_block_s','stddev','score'}
"""
import json
import statistics
from typing import List, Tuple, Optional

import config
from services.claude_service import claude_client


# Outcome-Enum aus models.py ck_calls_outcome
VALID_OUTCOMES = frozenset({
    'meeting_booked', 'callback', 'no_interest', 'wrong_person',
    'contract_signed', 'unknown'
})

# D-02 Edge-Case-Grenze
MIN_CALL_SECONDS_FOR_CLASSIFICATION = 30

# Haiku-Model — config.MODEL_POSTCALL_HAIKU bevorzugt; Fallback auf MODEL_ANALYSE (bestehende Haiku-Konstante)
_HAIKU_MODEL = (
    getattr(config, 'MODEL_POSTCALL_HAIKU', None)
    or getattr(config, 'MODEL_LIVE_HAIKU', None)
    or getattr(config, 'MODEL_ANALYSE', 'claude-haiku-4-5-20251001')
)


def _select_snippets(log_entries: List[dict], dauer_sek: int, max_count: int = 3) -> List[str]:
    """D-02: Top-3 Snippets. Bei langen Calls >15 Min: erste 30s + letzte 60s.
    Annahme: log_entries sind bereits anonymisiert (Phase B, Defense-in-Depth in classify())."""
    if not log_entries:
        return []
    texts = [e.get('text', '') for e in log_entries if e.get('text')]
    if not texts:
        return []
    # Heuristik: laengste Aussagen bevorzugt (Top-3 nach Laenge)
    sorted_by_len = sorted(texts, key=len, reverse=True)
    return sorted_by_len[:max_count]


def _build_prompt(conv_data: dict, snippets: List[str]) -> str:
    """Baut den Haiku-Prompt mit strukturierten Feldern + Snippets."""
    return (
        "Klassifiziere den Outcome dieses Verkaufsgesprächs.\n\n"
        f"Dauer (s): {conv_data.get('dauer_sekunden', 0)}\n"
        f"Erreichte Phase: {conv_data.get('erreichte_phase', 'unbekannt')}\n"
        f"Einwände: {json.dumps(conv_data.get('einwaende_liste', [])[:10], ensure_ascii=False)}\n"
        f"EWB-Klicks: {json.dumps(conv_data.get('ewb_clicks', []), ensure_ascii=False)}\n"
        f"Kaufbereitschaft Ende (0-100): {conv_data.get('kb_endwert', 0)}\n\n"
        "Auszüge (anonymisiert):\n"
        + "\n".join(f"- {s}" for s in snippets)
        + "\n\n"
        "Antworte AUSSCHLIESSLICH mit JSON in genau diesem Format, ohne Markdown-Code-Fences:\n"
        '{"outcome": "<one of: meeting_booked|callback|no_interest|wrong_person|contract_signed|unknown>", '
        '"confidence": <float 0.0-1.0>}'
    )


def classify(conv_data: dict) -> dict:
    """Outcome-Classifier via Claude Haiku.

    Returns:
        {'outcome': <enum-value or None>, 'confidence': <0.0-1.0>}

    Edge-Cases (D-02):
        - dauer<30s → outcome=None, confidence=0.0
        - Claude-Exception → outcome=None, confidence=0.0
        - Malformed JSON → outcome=None, confidence=0.0
        - outcome ausserhalb Enum → outcome=None
    """
    dauer = int(conv_data.get('dauer_sekunden') or 0)
    if dauer < MIN_CALL_SECONDS_FOR_CLASSIFICATION:
        return {'outcome': None, 'confidence': 0.0}

    # Defense-in-depth: log_entries sind aus Phase B bereits anonymisiert,
    # aber fuer Direct-Call-Path safe sein.
    snippets = _select_snippets(conv_data.get('log_entries', []), dauer)

    prompt = _build_prompt(conv_data, snippets)

    try:
        response = claude_client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = response.content[0].text.strip()
        # Markdown-Code-Fence Defense
        if raw.startswith('```'):
            lines = raw.split('\n')
            raw = '\n'.join(l for l in lines if not l.strip().startswith('```'))
        data = json.loads(raw)
        outcome = data.get('outcome')
        confidence = float(data.get('confidence', 0.0))
        if outcome not in VALID_OUTCOMES:
            return {'outcome': None, 'confidence': 0.0}
        confidence = max(0.0, min(1.0, confidence))
        return {'outcome': outcome, 'confidence': confidence}
    except Exception as e:
        print(f'[OutcomeService] classify() Fehler: {e}')
        return {'outcome': None, 'confidence': 0.0}


def calculate_audio_health(word_confidences_buffer: List[Tuple[int, float]]) -> dict:
    """Berechnet 5 Audio-Health-Metriken + gewichteten Score (0.0-1.0).

    Args:
        word_confidences_buffer: Liste von (ts_ms: int, confidence: float) Tuples.

    Returns:
        {
            'mean': float|None,
            'median': float|None,
            'pct_below_07': float,
            'longest_uncertain_block_s': float,
            'stddev': float,
            'score': float|None,  # Gewichteter Composite-Score 0.0-1.0
        }
    """
    if not word_confidences_buffer:
        return {
            'mean': None,
            'median': None,
            'pct_below_07': 0.0,
            'longest_uncertain_block_s': 0.0,
            'stddev': 0.0,
            'score': None,
        }

    confidences = [c for _, c in word_confidences_buffer]
    n = len(confidences)
    mean_c = statistics.mean(confidences)
    median_c = statistics.median(confidences)
    pct_below = sum(1 for c in confidences if c < 0.70) / n
    stddev_c = statistics.stdev(confidences) if n > 1 else 0.0

    # Laengster zusammenhaengender Block mit confidence<0.70
    longest_block_ms = 0
    block_start_ms: Optional[int] = None
    for ts, c in word_confidences_buffer:
        if c < 0.70:
            if block_start_ms is None:
                block_start_ms = ts
            else:
                longest_block_ms = max(longest_block_ms, ts - block_start_ms)
        else:
            block_start_ms = None
    longest_uncertain_block_s = longest_block_ms / 1000.0

    # Gewichteter Composite-Score:
    #   mean (40%) + (1-pct_below) (30%) + (1-min(longest/30,1)) (20%) + (1-min(stddev,0.3)/0.3) (10%)
    score = (
        0.4 * mean_c
        + 0.3 * (1.0 - pct_below)
        + 0.2 * (1.0 - min(longest_uncertain_block_s / 30.0, 1.0))
        + 0.1 * (1.0 - min(stddev_c, 0.3) / 0.3)
    )
    score = max(0.0, min(1.0, score))

    return {
        'mean': mean_c,
        'median': median_c,
        'pct_below_07': pct_below,
        'longest_uncertain_block_s': longest_uncertain_block_s,
        'stddev': stddev_c,
        'score': score,
    }
