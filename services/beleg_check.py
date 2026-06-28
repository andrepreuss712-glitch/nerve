# -*- coding: utf-8 -*-
"""Fuzzy-Beleg-Check (Cross-AI-Finding 3): prueft, ob ein Judge-Beleg-Zitat (ungefaehr) im
Transkript steht — normalisiert + Token-Overlap/Levenshtein (stdlib difflib).
NICHT striktes substring-contains.
Near-Miss -> flaggen (menschliche Sicht), nicht auto-verwerfen.
Nur stdlib: re + difflib. Keine externen ML-Bibliotheken (Leitsatz 2 / Punkt 27).

Phase: 08.23.2.TAXO2.HANDLING-TIMING Plan 05
"""

import re
import difflib


def _normalisiere(text: str) -> str:
    """Lowercase, Whitespace kollabieren, Satzzeichen entfernen, trim."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)   # Satzzeichen -> Leerzeichen
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def beleg_im_transkript(
    zitat: str,
    transkript_text: str,
    *,
    schwelle: float = 0.80,
    near_schwelle: float = 0.60,
) -> tuple:
    """Pruefen ob ein Judge-Beleg-Zitat (ungefaehr) im Transkript steht.

    Normalisiert beide Texte, sucht dann den besten Teilstring-Match mit einem
    gleitenden Fenster der Zitat-Laenge via difflib.SequenceMatcher (stdlib).
    Zusaetzlich Token-Overlap-Score als zweite Heuristik; endgueltig: max(beide).

    Args:
        zitat: Das Beleg-Zitat aus observations_jsonb (vom Judge geliefert).
        transkript_text: Der vollstaendige Transkript-Text des Calls.
        schwelle: Score >= schwelle -> ok=True (klarer Treffer). Default 0.80.
        near_schwelle: near_schwelle <= score < schwelle -> ok=False, befund='near_miss'
            (flaggen fuer menschliche Sicht, NICHT auto-verwerfen). Default 0.60.

    Returns:
        Tuple (ok: bool, score: float, befund: str).
        befund: 'treffer' | 'near_miss' | 'no_match'

    Notes:
        - near_miss = FLAG fuer den Menschen, kein Auto-Verwerfen (Cross-AI-Finding 3).
        - no_match = echtes Halluzinat (gefaehrlichster Fall).
        - Nur stdlib: re + difflib. Keine externen ML-Bibliotheken (Finding 3 / Leitsatz 2).
    """
    if not zitat or not transkript_text:
        return (False, 0.0, 'no_match')

    zitat_norm = _normalisiere(zitat)
    transkript_norm = _normalisiere(transkript_text)

    if not zitat_norm:
        return (False, 0.0, 'no_match')

    # ── Score A: gleitendes Fenster via SequenceMatcher (Levenshtein-nah) ─────
    zitat_len = len(zitat_norm)
    transkript_len = len(transkript_norm)

    score_a = 0.0
    if transkript_len >= zitat_len:
        # Fenster-Schritt: jede Zitat-Laenge-grosse Position im Transkript abtasten.
        # Fensterschritt = max(1, zitat_len // 4) fuer Performance bei langen Transkripten.
        schritt = max(1, zitat_len // 4)
        for start in range(0, transkript_len - zitat_len + 1, schritt):
            fenster = transkript_norm[start: start + zitat_len + zitat_len // 4]
            ratio = difflib.SequenceMatcher(None, zitat_norm, fenster, autojunk=False).ratio()
            if ratio > score_a:
                score_a = ratio
    elif transkript_len > 0:
        # Transkript kuerzer als Zitat (ungewoehnlich) — direkt vergleichen
        score_a = difflib.SequenceMatcher(None, zitat_norm, transkript_norm, autojunk=False).ratio()

    # ── Score B: Token-Overlap (Anteil der Zitat-Tokens im Transkript) ────────
    zitat_tokens = set(zitat_norm.split())
    transkript_tokens = set(transkript_norm.split())
    if zitat_tokens:
        gemeinsame = zitat_tokens & transkript_tokens
        score_b = len(gemeinsame) / len(zitat_tokens)
    else:
        score_b = 0.0

    # Endgueltiger Score: Maximum beider Heuristiken
    score = max(score_a, score_b)

    # ── Befund ermitteln ──────────────────────────────────────────────────────
    if score >= schwelle:
        return (True, score, 'treffer')
    elif score >= near_schwelle:
        # Near-Miss: flaggen fuer menschliche Sicht — NICHT auto-verwerfen (Finding 3).
        return (False, score, 'near_miss')
    else:
        # no_match: echtes Halluzinat (gefaehrlichster Fall).
        return (False, score, 'no_match')
