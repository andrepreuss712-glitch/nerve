"""Gatekeeper-Klassifikation und Trigger-Phrasen-Erkennung (Phase 08.23.2.C, D-02).

NER-Schnittstelle: ruft services.anonymization.extract_entities() auf —
KEINE eigenen GLiNER/spaCy-Aufrufe (DRY-Pflicht per D-02).

Voting-Strategie (Review Finding 4):
- Target-Erkennung: UNION (ein Modell reicht) — Recall maximieren
- Gatekeeper-Erkennung: CONSENSUS (beide Modelle) — False-Positives minimieren
"""
import re
import time
from typing import Optional

from services.anonymization import extract_entities
from services.ki_logik import (
    TRIGGER_PHRASES,
    UWG_HARD_BLOCK_PATTERNS,
    _phrase_matches,
)
from config.phase_transitions import (
    MIN_PHASE_DURATIONS,
    ALLOWED_TRANSITIONS,
    FORBIDDEN_TRANSITIONS,
    MODE_TRANSITION_AUTO,
    HYSTERESIS_REQUIRED_HINTS,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _names_match(extracted: str, briefing: str) -> bool:
    """Fuzzy-Match zwischen extrahierter Name und Briefing-CEO/GF.

    Strategie (Review Finding 3):
    1. Exact match (case-insensitive)
    2. Substring/Wort-Overlap (Vorname oder Nachname reicht)
    3. RapidFuzz fuzzy (threshold=0.85) — fuer STT-Phonetik-Varianten
       (Meier/Meyer/Maier, Schroeder/Schroeder etc.)

    RapidFuzz-Import ist optional — bei ImportError degradiert auf Substring-only.
    """
    if not extracted or not briefing:
        return False
    e = extracted.strip().lower()
    b = briefing.strip().lower()

    # Exact match
    if e == b:
        return True

    # Substring: ein Vorname / Nachname reicht
    e_parts = set(e.split())
    b_parts = set(b.split())
    if e_parts & b_parts:
        return True

    # RapidFuzz fuzzy: handles STT phonetic variants (Meier/Meyer/Maier) — Review Finding 3
    try:
        from rapidfuzz import fuzz
        for e_part in e_parts:
            for b_part in b_parts:
                # Kurze Woerter (< 3 Zeichen) ueberspringen — zu viele Falsch-Treffer
                if len(e_part) >= 3 and len(b_part) >= 3:
                    # Threshold 80: Meier/Meyer=80, Mueller/Muller=92 — deckt DE-Phonetik-Varianten ab.
                    # 85 wuerde Meier/Meyer (=80) verfehlen (Plan-Acceptance-Criterion).
                    if fuzz.ratio(e_part, b_part) >= 80:
                        return True
    except ImportError:
        pass  # rapidfuzz nicht installiert -> Substring-only (degraded mode)

    return False


# ── classify_contact (Req-5) ───────────────────────────────────────────────────

def classify_contact(
    transcript_window: list,
    briefing_ceo_name: Optional[str],
    current_mode: str,
) -> str:
    """UNION/CONSENSUS-Voting fuer Kontakt-Klassifikation (Review Finding 4).

    Voting-Asymmetrie (warum unterschiedlich):
    - Target (CEO erkannt): UNION — ein Modell reicht wenn Name CEO matcht.
      Recall maximieren: spaCy hat ~77% Recall auf deutschen Namen;
      wenn spaCy den CEO verpasst aber GLiNER ihn erkennt, verlieren wir den
      Target-Treffer bei reinem Consensus.
    - Gatekeeper (Unbekannte Person erkannt): CONSENSUS — beide Modelle muessen
      einig sein. FP-Rate minimieren: falscher Gatekeeper-Modus blockiert den
      Sales-Flow unnoetig.

    Returns:
        'target'     wenn UNION-Set einen Namen enthaelt der CEO fuzzy-matched (D-01)
        'gatekeeper' wenn CONSENSUS-Set nicht leer und kein CEO-Match
        'unknown'    wenn kein Konsens fuer gatekeeper und kein Union-Hit fuer target
    """
    if not transcript_window:
        return 'unknown'

    combined_text = ' '.join(transcript_window)
    entities = extract_entities(combined_text, cache=None)

    spacy_persons = {e['text'].lower() for e in entities if e['source'] == 'spacy' and e['type'] == 'PERSON'}
    gliner_persons = {e['text'].lower() for e in entities if e['source'] == 'gliner' and e['type'] == 'PERSON'}

    all_persons = spacy_persons | gliner_persons  # UNION fuer Target-Check
    consensus = spacy_persons & gliner_persons     # CONSENSUS fuer Gatekeeper-Check

    # UNION: wenn EIN Modell einen Namen erkennt der CEO matcht -> target
    if briefing_ceo_name and all_persons:
        for name in all_persons:
            if _names_match(name, briefing_ceo_name):
                return 'target'

    # CONSENSUS: nur wenn BEIDE Modelle einig sind -> gatekeeper
    if consensus:
        return 'gatekeeper'

    return 'unknown'


# ── detect_trigger_phrases (Req-7) ────────────────────────────────────────────

def detect_trigger_phrases(transcript_line: str) -> dict:
    """Scant einzelne Zeile auf bekannte Gatekeeper-Trigger.

    Returns:
        dict {'matches': [list of category strings], 'hard_block': bool}
    """
    if not transcript_line:
        return {'matches': [], 'hard_block': False}
    matches = []
    hard_block = False
    for p in TRIGGER_PHRASES:
        if _phrase_matches(transcript_line, p['pattern']):
            matches.append(p['category'])
            if p.get('hard_block'):
                hard_block = True
    return {'matches': matches, 'hard_block': hard_block}


# ── detect_uwg_hard_block (Req-8) ─────────────────────────────────────────────

def detect_uwg_hard_block(transcript_line: str) -> bool:
    """Schneller Single-Purpose-Check fuer UWG §7 Opt-Out.
    Identisch mit detect_trigger_phrases()['hard_block'] aber ohne andere Kategorien zu scannen.
    """
    if not transcript_line:
        return False
    return any(
        _phrase_matches(transcript_line, p)
        for p in UWG_HARD_BLOCK_PATTERNS
    )


# ── get_gatekeeper_phase_for_window (Helper fuer Wave 5 Tests) ─────────────────

def get_gatekeeper_phase_for_window(transcript_window: list) -> str:
    """Heuristische Phasen-Abschaetzung fuer Gatekeeper-Modus (4 Phasen).

    Sehr einfacher String-basierter Mapper — fuer Tests und Quick-Estimation.
    Echte Klassifikation passiert weiterhin via claude_service.classify_phase().
    """
    if not transcript_window:
        return 'greeting'
    joined = ' '.join(transcript_window).lower()
    if any(w in joined for w in ('mit wem', 'wer sind sie', 'von welcher firma')):
        return 'identify'
    if any(w in joined for w in ('verbinden', 'durchstellen', 'weiterleiten')):
        return 'handoff'
    if any(w in joined for w in ('worum geht es', 'um was geht es', 'wegen welcher angelegenheit')):
        return 'bypass'
    return 'greeting'


# ── Hysterese (Req-3) ──────────────────────────────────────────────────────────

def apply_hysteresis(state: dict, proposed_phase: str, mode: str) -> Optional[str]:
    """Prueft drei Bedingungen vor Phasen-Wechsel-Akzeptanz (Req-3).

    Args:
        state: per-SID Session-State dict (mutiert IN-PLACE!).
               Erwartet Keys: 'current_phase', 'phase_hint_count', 'pending_phase',
                              'phase_entered_at' (monotonic seconds).
        proposed_phase: Vom Klassifikator vorgeschlagene neue Phase (Token wie 'pitch').
        mode: 'cold_call' | 'gatekeeper' | 'meeting'.

    Returns:
        new_phase wenn Wechsel akzeptiert (Caller persistiert phase_change), sonst None.
    """
    current = state.get('current_phase')

    # Same phase -> reset hint count (stability signal)
    if proposed_phase == current:
        state['phase_hint_count'] = 0
        state['pending_phase'] = None
        return None

    # Build hint count
    if state.get('pending_phase') == proposed_phase:
        state['phase_hint_count'] = state.get('phase_hint_count', 0) + 1
    else:
        state['pending_phase'] = proposed_phase
        state['phase_hint_count'] = 1

    # Bedingung 1: >=HYSTERESIS_REQUIRED_HINTS aufeinanderfolgende Hinweise
    if state['phase_hint_count'] < HYSTERESIS_REQUIRED_HINTS:
        return None

    # Bedingung 2: Mindest-Verweildauer in aktueller Phase
    durations = MIN_PHASE_DURATIONS.get(mode, {})
    min_dwell = durations.get(current, 0)
    entered_at = state.get('phase_entered_at') or time.monotonic()
    elapsed = time.monotonic() - entered_at
    if elapsed < min_dwell:
        return None  # noch zu frueh

    # Bedingung 3: Uebergang erlaubt?
    allowed = ALLOWED_TRANSITIONS.get(mode, {}).get(current, [])
    forbidden = FORBIDDEN_TRANSITIONS.get(mode, {}).get(current, [])
    if proposed_phase in forbidden:
        return None
    if current is not None and proposed_phase not in allowed:
        # Keine erlaubte Kante -> ablehnen (Req-3 Acceptance)
        return None

    # ALLE Bedingungen ok -> Wechsel
    state['current_phase'] = proposed_phase
    state['phase_entered_at'] = time.monotonic()
    state['phase_hint_count'] = 0
    state['pending_phase'] = None
    return proposed_phase


# ── Foundation-Stub (Req-11, D-02) ────────────────────────────────────────────

def populate_context_notes(state: dict, entity: dict) -> None:
    """Foundation-Stub fuer Phase 08.23.2.I (Sekretaer-Uebergabe-Feature).

    Aktiviert von: Phase 08.23.2.I
    Aktueller Stand: Body bleibt leer. Phase 08.23.2.I schreibt die Implementierung
                     und ruft die Funktion aus dem Gatekeeper-Loop heraus auf.

    Siehe .planning/04 Entscheidungen/Foundation-Code-Register.md Eintrag 1.
    """
    pass


__all__ = [
    'classify_contact',
    'detect_trigger_phrases',
    'detect_uwg_hard_block',
    'get_gatekeeper_phase_for_window',
    'apply_hysteresis',
    'populate_context_notes',
]
