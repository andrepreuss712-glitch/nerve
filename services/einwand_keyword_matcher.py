"""
services/einwand_keyword_matcher.py
────────────────────────────────────────────────────────────────────
Lokaler Keyword-Klassifikator fuer Einwand-Erkennung in Echtzeit.

Erkennt Einwand-Keywords in Interim-Transkripten (DE) und mappt sie
auf passende Einwand-Profile — ohne API-Call, <1ms Latenz.

Verwendung:
    from services.einwand_keyword_matcher import EinwandKeywordMatcher, match_keyword

Side-effect-free beim Import: keine I/O, keine DB-Zugriffe, keine Threads.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

# ── Keyword-Regex-Datenbank ──────────────────────────────────────────────────
# Jeder Schluessel ist ein semantischer Einwand-Typ.
# Regex matcht Wort-Boundaries, case-insensitive (re.IGNORECASE).
# Korrekte Alternation-Gruppen — KEINE character-classes fuer mehrzeichige Alternativen.
#
# Umlaut-Toleranz: (ü|ue), (ä|ae), (ö|oe) damit sowohl native Umlaute
# als auch ae/ue/oe-Fallbacks erkannt werden.

DEFAULT_KEYWORDS: dict[str, str] = {
    'keine_zeit': (
        r'\b(keine?\s+zeit'
        r'|gerade\s+kei[nm]e?\s+zeit'
        r'|kei[nm]e?\s+zeit\s+hab'
        r'|gerade\s+stress)\b'
    ),
    'zu_teuer': (
        r'\b(zu\s+teuer'
        r'|viel\s+zu\s+teuer'
        r'|passt\s+nicht\s+ins\s+budget'
        r'|kein\s+budget)\b'
    ),
    'kein_interesse': (
        r'\b(kein(e)?\s+interesse'
        r'|nicht\s+interessiert'
        r'|interessiert\s+mich\s+nicht)\b'
    ),
    'ueberlegen': (
        r'\b(muss\s+(noch\s+)?(dar)?(\u00fc|ue)berlegen'
        r'|mich\s+(dar)?(\u00fc|ue)berlegen'
        r'|dar(\u00fc|ue)ber\s+nachdenken'
        r'|ich\s+schlaf\s+(mal\s+)?dr(\u00fc|ue)ber)\b'
    ),
    'skeptisch': (
        r'\b(skeptisch'
        r'|zweifel'
        r'|vertraue\s+(das\s+)?\s*nicht'
        r'|klingt\s+(zu\s+)?gut)\b'
    ),
    'haben_schon': (
        r'\b(haben\s+schon'
        r'|nutzen\s+(wir\s+)?schon'
        r'|sind\s+(schon\s+)?versorgt'
        r'|haben\s+bereits)\b'
    ),
    'falscher_ansprechpartner': (
        r'\b(nicht\s+(der|die)\s+richtige'
        r'|falscher?\s+ansprechpartner'
        r'|nicht\s+zust(\u00e4|ae)ndig)\b'
    ),
    'kompliziert': (
        r'\b(zu\s+kompliziert'
        r'|zu\s+komplex'
        r'|zu\s+aufw(\u00e4|ae)ndig'
        r'|zu\s+viel\s+arbeit)\b'
    ),
}

# Vorkompilierte Patterns (case-insensitive)
_COMPILED_KEYWORDS: dict[str, re.Pattern] = {
    key: re.compile(pattern, re.IGNORECASE)
    for key, pattern in DEFAULT_KEYWORDS.items()
}

# ── Profil-Match-Aliase ──────────────────────────────────────────────────────
# Mappt Keyword-Key -> Liste von Aliase fuer (kurzlabel | kategorie | typ).
# Verifiziert an echten DB-Profilen aus database/salesnerve.db:
#   kategorie real: Preis, Zeit, Bedarf, Vertrauen, Wettbewerb, Entscheider, Datenschutz, Skepsis
#   typ real (Demo-Profile): Kosten/Preis, Vergleich, Kein Bedarf, Zeit/Aufschub,
#                            Entscheidungstraeger, Vertrauen
# Alle Aliase lowercase fuer case-insensitiven Vergleich.

KEYWORD_TO_PROFILE_ALIASES: dict[str, list[str]] = {
    'keine_zeit':     ['zeit', 'zeit/aufschub', 'keine zeit', 'zeitdruck'],
    'zu_teuer':       ['preis', 'kosten/preis', 'zu teuer', 'kosten', 'budget'],
    'kein_interesse': ['bedarf', 'kein bedarf', 'kein interesse'],
    'ueberlegen':     ['zeit/aufschub', 'entscheider', 'entscheidungstraeger',
                       'ueberlegen', 'bedenkzeit'],
    'skeptisch':      ['vertrauen', 'skepsis', 'skeptisch'],
    'haben_schon':    ['wettbewerb', 'vergleich', 'haben schon', 'konkurrenz'],
    'falscher_ansprechpartner': ['entscheider', 'entscheidungstraeger',
                                 'falscher ansprechpartner'],
    'kompliziert':    ['datenschutz', 'kompliziert'],
}


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _profile_gegenargument(pe: dict) -> str:
    """
    Gibt das Gegenargument aus einem Profil-Einwand-Dict zurueck.
    Prueft 'gegenargument' (echtes DB-Feld), dann Fallbacks.
    """
    return (
        pe.get('gegenargument')
        or pe.get('gegenargument_1')
        or pe.get('text')
        or ''
    ).strip()


def _match_profile_einwand(keyword: str, profile_einwaende: list) -> Optional[dict]:
    """
    Sucht in profile_einwaende[] nach einem Eintrag, dessen
    (kurzlabel | kategorie | typ) einem Alias fuer `keyword` entspricht
    UND der ein nicht-leeres gegenargument hat.

    Feldprioritaet: kurzlabel > kategorie > typ (case-insensitive).
    Gibt {'profile_einwand': dict, 'matched_label': str} oder None zurueck.
    """
    aliases = {a.lower() for a in KEYWORD_TO_PROFILE_ALIASES.get(keyword, [])}
    if not aliases:
        return None

    for pe in profile_einwaende:
        if not isinstance(pe, dict):
            continue
        # Kein Gegenargument → kein Nutzen als Slot-0-Treffer
        if not _profile_gegenargument(pe):
            continue

        # Feldprioritaet: kurzlabel > kategorie > typ
        for field in ('kurzlabel', 'kategorie', 'typ'):
            val = pe.get(field)
            if val and str(val).strip().lower() in aliases:
                return {'profile_einwand': pe, 'matched_label': field}

    return None


# ── Haupt-Match-Funktion ─────────────────────────────────────────────────────

def match_keyword(transcript: str, profile_einwaende: list) -> Optional[dict]:
    """
    Prueft `transcript` gegen alle DEFAULT_KEYWORDS.
    Beim ersten Treffer: sucht passendes Profil-Einwand mit nicht-leerem Gegenargument.

    Returns:
        {'keyword': str, 'profile_einwand': dict, 'matched_label': str} oder None.

    Side-effect-free, kein State.
    """
    if not transcript or not profile_einwaende:
        return None

    for keyword, pattern in _COMPILED_KEYWORDS.items():
        if pattern.search(transcript):
            profile_match = _match_profile_einwand(keyword, profile_einwaende)
            if profile_match:
                return {
                    'keyword': keyword,
                    'profile_einwand': profile_match['profile_einwand'],
                    'matched_label': profile_match['matched_label'],
                }

    return None


# ── EinwandKeywordMatcher-Klasse ─────────────────────────────────────────────

class EinwandKeywordMatcher:
    """
    Stateful Wrapper um match_keyword() mit Dedup-Guard.

    Per-Session Dedup: derselbe Keyword-Typ feuert max. 1x innerhalb
    `dedup_window_sec` Sekunden. Thread-safe via threading.Lock.

    Lebenszyklus:
        - reset_keyword(kw) nach utterance_end → erlaubt Re-Trigger
        - reset_all()       nach Call-Ende / Session-Restart
    """

    def __init__(self, dedup_window_sec: float = 10.0) -> None:
        self._last_seen: dict[str, float] = {}   # keyword -> time.monotonic()
        self._dedup_window = dedup_window_sec
        self._lock = threading.Lock()

    def match_with_dedup(
        self,
        transcript: str,
        profile_einwaende: list,
    ) -> Optional[dict]:
        """
        Wie match_keyword(), aber mit Dedup-Guard:
        Gibt None zurueck wenn derselbe Keyword-Typ innerhalb
        des Dedup-Fensters bereits gefeuert hat.
        """
        match = match_keyword(transcript, profile_einwaende)
        if not match:
            return None

        keyword = match['keyword']
        now = time.monotonic()

        with self._lock:
            last = self._last_seen.get(keyword, 0.0)
            if now - last < self._dedup_window:
                return None
            self._last_seen[keyword] = now

        return match

    def reset_keyword(self, keyword: str) -> None:
        """
        Loescht Dedup-Eintrag fuer `keyword`.
        Aufzurufen bei utterance_end damit naechster Satz re-triggern kann.
        """
        with self._lock:
            self._last_seen.pop(keyword, None)

    def reset_all(self) -> None:
        """Loescht gesamten Dedup-State. Aufzurufen bei Call-Ende / Session-Restart."""
        with self._lock:
            self._last_seen.clear()
