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


# Outcome-Enum aus models.py ck_calls_outcome (D-W2-01: send_info + gatekeeper_blocked hinzugefuegt)
VALID_OUTCOMES = frozenset({
    'meeting_booked', 'callback', 'send_info', 'wrong_person',
    'gatekeeper_blocked', 'no_interest', 'contract_signed', 'unknown'
})

# D-02 Edge-Case-Grenze
MIN_CALL_SECONDS_FOR_CLASSIFICATION = 30

# Haiku-Model — config.MODEL_POSTCALL_HAIKU bevorzugt; Fallback auf MODEL_ANALYSE (bestehende Haiku-Konstante)
_HAIKU_MODEL = (
    getattr(config, 'MODEL_POSTCALL_HAIKU', None)
    or getattr(config, 'MODEL_LIVE_HAIKU', None)
    or getattr(config, 'MODEL_ANALYSE', 'claude-haiku-4-5-20251001')
)


def _estimate_tokens(text: str) -> int:
    """Conservative token estimate for German transcript text.
    Factor 1.4 is a conservative best-guess (WARNING Claudian-Review 2026-05-28).
    German compound nouns tokenize heavier than English (~1.4-1.6 tokens/word).
    Calibrate factor with real NERVE call corpus after EA launch.
    Current 1.4 may undercount tokens for long compound-heavy transcripts --
    true boundary may be 1400 words rather than 2000/1.4 approx 1429 words."""
    return int(len(text.split()) * 1.4)


def _select_snippets(log_entries: List[dict], dauer_sek: int) -> List[str]:
    """D.UX-W2-03: Full transcript if < 2000 estimated tokens, else first-30s + last-60s.
    Replaces the old 'top-3 longest statements' heuristic which dropped short
    closing sentences (e.g. 'Montag um 10' = meeting_booked classified as unknown).

    Token estimate: len(words) * 1.4 (conservative, German compound nouns tokenize heavier).
    Fallback boundary: if ts_ms available -> time-based (first 30s + last 60s).
                       if ts_ms absent   -> index-based (first 15 + last 15 entries).
    """
    if not log_entries:
        return []
    texts = [e.get('text', '') for e in log_entries if e.get('text')]
    if not texts:
        return []

    full_text = ' '.join(texts)

    # Full transcript if below token threshold
    if _estimate_tokens(full_text) < 2000:
        return texts

    # Fallback: first 30s + last 60s
    # Check if ts_ms is available in entries
    has_ts = any('ts_ms' in e for e in log_entries)
    if has_ts:
        early = [e.get('text', '') for e in log_entries
                 if e.get('ts_ms', 0) <= 30_000 and e.get('text')]
        late  = [e.get('text', '') for e in log_entries
                 if e.get('ts_ms', 0) >= (dauer_sek - 60) * 1000 and e.get('text')]
    else:
        # Index-based fallback: first 15 + last 15 entries
        early = texts[:15]
        late  = texts[-15:]
    return early + late


SYSTEM_PROMPT = """\
Du bist ein Klassifikations-Assistent für B2B-Verkaufsgespräche im DACH-Markt.

Klassifiziere den Gesprächsausgang in genau eine der 7 Kategorien:
- meeting_booked: Ein konkreter Termin mit Datum/Zeit wurde vereinbart
- callback: Rückruf vereinbart, aber kein fester Termin (z.B. "melde mich nächste Woche")
- send_info: Interessent möchte Unterlagen/Infos zugeschickt bekommen
- wrong_person: Gesprächspartner ist nicht der richtige Ansprechpartner
- gatekeeper_blocked: Sekretariat/Empfang hat Weiterleitung verweigert, kein Durchkommen
- no_interest: Klare Ablehnung, kein Interesse
- contract_signed: Vertrag oder Abschluss wurde im Gespräch bestätigt

Rangfolge bei Überlappung: Termin (meeting_booked) > Rückruf (callback) > Kein Interesse (no_interest).

<examples>
<example>
<input>Ja, das klingt interessant. Montag um 10 hätte ich Zeit. Tragen Sie mich ein.</input>
<output>{"outcome": "meeting_booked", "confidence": 0.95}</output>
</example>
<example>
<input>Nein danke, das ist nichts für uns. Bitte rufen Sie nicht wieder an.</input>
<output>{"outcome": "no_interest", "confidence": 0.97}</output>
</example>
<example>
<input>Schicken Sie mir die Unterlagen, ich melde mich nächste Woche. Einen festen Termin kann ich jetzt nicht zusagen.</input>
<output>{"outcome": "callback", "confidence": 0.88}</output>
</example>
<example>
<input>Das macht bei uns die Frau Müller in der Geschäftsführung. Ich gebe Ihnen mal die Durchwahl.</input>
<output>{"outcome": "wrong_person", "confidence": 0.92}</output>
</example>
<example>
<input>Frau Schmidt ist heute nicht zu sprechen. Versuchen Sie es nächste Woche. Durchstellen kann ich Sie nicht.</input>
<output>{"outcome": "gatekeeper_blocked", "confidence": 0.91}</output>
</example>
</examples>

Antworte AUSSCHLIESSLICH mit JSON in genau diesem Format, ohne Markdown-Code-Fences:
{"outcome": "<enum-wert>", "confidence": <float 0.0-1.0>}\
"""


def _build_prompt(conv_data: dict, snippets: List[str]) -> str:
    """Baut den User-Message-Teil für Haiku (System-Prompt ist in SYSTEM_PROMPT)."""
    return (
        f"Gesprächsdauer (s): {conv_data.get('dauer_sekunden', 0)}\n"
        f"Erreichte Phase: {conv_data.get('erreichte_phase', 'unbekannt')}\n"
        f"Einwände: {json.dumps(conv_data.get('einwaende_liste', [])[:10], ensure_ascii=False)}\n"
        f"Kaufbereitschaft Ende (0-100): {conv_data.get('kb_endwert', 0)}\n\n"
        "<transkript>\n"
        + "\n".join(f"- {s}" for s in snippets)
        + "\n</transkript>\n\n"
        "Klassifiziere den Gesprächsausgang."
    )


def classify(conv_data: dict) -> dict:
    """Outcome-Classifier via Claude Haiku.

    Returns:
        {'outcome': <enum-value or 'unknown'>, 'confidence': <0.0-1.0>}

    Edge-Cases (D-02 + REQ-D.UX-6):
        - conv_data leer oder dauer<30s -> outcome='unknown', confidence=0.0 (kein HTTP-Call)
        - Claude-Exception -> outcome='unknown', confidence=0.0
        - Malformed JSON -> outcome='unknown', confidence=0.0
        - outcome ausserhalb Enum -> outcome='unknown'
        - snippets < 20 Woerter -> confidence ceiling 0.65 (post-processing, nicht Prompt)
    """
    # Early exit for empty or very short calls (REQ-D.UX-6)
    if not conv_data or conv_data.get('dauer_sekunden', 0) < MIN_CALL_SECONDS_FOR_CLASSIFICATION:
        return {'outcome': 'unknown', 'confidence': 0.0}

    dauer = int(conv_data.get('dauer_sekunden') or 0)

    # Defense-in-depth: log_entries sind aus Phase B bereits anonymisiert,
    # aber fuer Direct-Call-Path safe sein.
    snippets = _select_snippets(conv_data.get('log_entries', []), dauer)

    prompt = _build_prompt(conv_data, snippets)

    try:
        response = claude_client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=80,
            system=SYSTEM_PROMPT,
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
            return {'outcome': 'unknown', 'confidence': 0.0}
        confidence = max(0.0, min(1.0, confidence))
        # Post-process: enforce confidence ceiling for short inputs (< 20 words)
        word_count = sum(len(s.split()) for s in snippets)
        if word_count < 20:
            confidence = min(confidence, 0.65)
        return {'outcome': outcome, 'confidence': confidence}
    except Exception as e:
        print(f'[OutcomeService] classify() Fehler: {e}')
        return {'outcome': 'unknown', 'confidence': 0.0}


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
