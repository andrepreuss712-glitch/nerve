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

# ── Live-Session State Reference ─────────────────────────────────────────────
# Lazy-import to avoid circular deps. Used only in match_with_dedup success path
# to set kw_fired_for_line flag (D-02 Phase 08.5 — prevents qa_pipeline double-fire).
ls_module = None  # overwritten at runtime by _get_ls()

def _get_ls():
    """Lazy-init live_session module reference. MUST NOT raise."""
    global ls_module
    if ls_module is None:
        try:
            import services.live_session as _ls
            ls_module = _ls
        except Exception:
            pass
    return ls_module

# ── Keyword-Regex-Datenbank ──────────────────────────────────────────────────
# Jeder Schluessel ist ein semantischer Einwand-Typ.
# Regex matcht Wort-Boundaries, case-insensitive (re.IGNORECASE).
# Korrekte Alternation-Gruppen — KEINE character-classes fuer mehrzeichige Alternativen.
#
# Umlaut-Toleranz: (ü|ue), (ä|ae), (ö|oe) damit sowohl native Umlaute
# als auch ae/ue/oe-Fallbacks erkannt werden.
#
# POLISH-46 Flexions-Fix:
#   kein(?:e[mnrs]?)? deckt alle 6 deutschen Flexions-Formen ab:
#   kein, keine, keinem, keinen, keiner, keines.
#   Verwendet fuer 'keine_zeit' (Nicht-'gerade'-Fall) und 'kein_interesse'.
#   Zusaetzlich 'bedarf' als Synonym fuer 'interesse' eingefuegt
#   und 'brauch(en|e)?' als verbaler Kein-Bedarf-Ausdruck.

DEFAULT_KEYWORDS: dict[str, str] = {
    'keine_zeit': (
        r'\b(kein(?:e[mnrs]?)?\s+zeit'
        r'|kein(?:e[mnrs]?)?\s+zeit\s+hab'
        r'|gerade\s+stress)\b'
    ),
    'zu_teuer': (
        r'\b(zu\s+teuer'
        r'|viel\s+zu\s+teuer'
        r'|passt\s+nicht\s+ins\s+budget'
        r'|kein\s+budget)\b'
    ),
    'kein_interesse': (
        r'\b(kein(?:e[mnrs]?)?\s+(?:interesse|bedarf)'
        r'|nicht\s+interessiert'
        r'|interessiert\s+mich\s+nicht'
        r'|brauch(?:en|e)?\s+(?:wir\s+|ich\s+|das\s+)?nicht)\b'
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
# Verifiziert an echten DB-Profilen aus database/nerve.db:
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
                return {'profile_einwand': pe, 'matched_label': str(val).strip()}

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
        sid: str = None,
    ) -> Optional[dict]:
        """
        Wie match_keyword(), aber mit Dedup-Guard:
        Gibt None zurueck wenn derselbe Keyword-Typ innerhalb
        des Dedup-Fensters bereits gefeuert hat.

        sid (Phase 08.23.2.TAXO1-03, §0.1 P4 REVERSE): per-SID kw_fired_for_line-Write.
            Der Matcher schrieb frueher global _ls.state['kw_fired_for_line'], waehrend
            analyse_loop per-SID las (claude:1265) → der D-02-Doppel-Feuer-Schutz griff NIE.
            Mit sid liest+schreibt der Matcher dieselbe per-SID-Quelle.
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

        # ── Phase 08.5 D-02: Set kw_fired_for_line flag ──────────────────────
        # Tells analyse_loop that this utterance was already handled by the
        # Keyword-Matcher — prevents qa_pipeline double-fire (529-loop guard).
        # Phase 08.23.2.TAXO1-03 (§0.1 P4 REVERSE): per-SID statt global.
        # line_id + kw_fired_for_line leben jetzt kanonisch in
        # _session_state[sid]['state'] (analyse_loop schreibt line_id dort, claude:979).
        try:
            _ls = _get_ls()
            if _ls and sid:
                with _ls._session_state_lock:
                    _sid_kw_state = (_ls._session_state.get(sid) or {}).get('state')
                    if _sid_kw_state is not None:
                        current_line = _sid_kw_state.get('line_id')
                        if current_line is not None:
                            _sid_kw_state['kw_fired_for_line'] = current_line
                            print(f"[KW] kw_fired_for_line set to {current_line} (sid={sid})")
        except Exception as _kw_e:
            print(f"[KW] kw_fired_for_line set skip: {_kw_e}")

        # ── TAXO1-Welle 4 (Task 3a): Fast-Lane-Emit (Keyword -> intent_event) ───
        # Lokaler Treffer (<800ms, KEIN LLM) -> source=llm_inferred (lokal abgeleitet).
        # Moment-Fenster (I-4-FOLD, KEIN line_id): get_or_open_moment oeffnet/setzt
        # das offene Fenster fort -> dieselbe id wie Medium/Button desselben Fensters.
        # Lock-Disziplin (Gemini-Punkt a): EIGENER `with _session_state_lock`-Block,
        # NICHT genested mit state_lock (der Matcher haelt hier ohnehin kein state_lock;
        # kw_fired oben nutzt bereits _session_state_lock) -> kein Lock-Ordering-Deadlock.
        try:
            _ls = _get_ls()
            if _ls and sid:
                # mode-Quelle per-SID (TAXO1-07: globales _session_modes geloescht).
                _kw_mode = (_ls._session_state.get(sid) or {}).get('mode', 'cold_call')
                _kw_iid = None
                _kw_uid = None
                _kw_oid = None
                _kw_phase = None
                with _ls._session_state_lock:
                    _kw_sd = _ls._session_state.get(sid) or {}
                    _kw_uid = _kw_sd.get('user_id')
                    _kw_oid = _kw_sd.get('org_id')
                    _kw_st = _kw_sd.get('state')
                    if _kw_st is not None:
                        _kw_phase = _kw_st.get('current_phase')
                        _kw_iid = _ls.get_or_open_moment(
                            sid, mode=_kw_mode, now=now)
                # Keyword-Treffer = erkannter konkreter Kunden-Einwand -> echter_einwand
                # (§1). Die feinere vorwand/reflex-Nuance liefert die Medium Lane (LLM).
                # TAXO1-07 (Task 3, Decision 2): Sprecher-Bug-Fix ueber die Registry.
                # cold_call -> Keyword-Treffer = Berater nennt den Einwand-Typ -> berater.
                from services.mode_strategy import MODE_REGISTRY
                _kw_strategy = MODE_REGISTRY.get(_kw_mode) or MODE_REGISTRY['cold_call']
                try:
                    _kw_attr = _kw_strategy.extract_intent(speaker=None, confidence=0.9)
                except Exception:
                    _kw_attr = MODE_REGISTRY['cold_call'].extract_intent(speaker=None, confidence=0.9)
                # FUND 3 (TAXO1-07): anonymisierter Ausloeser-Wortlaut = die matched
                # utterance (transcript; match['keyword'] ist nur das getroffene Keyword).
                from services.anonymization import anonymize_output as _anon_out_kw
                _kw_trig = None
                try:
                    _kw_trig = _anon_out_kw(transcript, _ls.get_anonymisierer(sid))
                    if not _kw_trig or _kw_trig in ('[ART9_REDACTED]', '[ANON_FEHLER]'):
                        _kw_trig = None
                except Exception:
                    _kw_trig = None
                from services.intent_event_writer import emit_intent_event
                emit_intent_event(
                    session_id=sid, mode=_kw_mode, intent_type='echter_einwand',
                    phase=_kw_phase, source='llm_inferred', inference_basis=_kw_attr['inference_basis'],
                    confidence=0.9, speaker_role=_kw_attr['speaker_role'],
                    speaker_id=_kw_attr['speaker_id'],
                    user_id=_kw_uid, org_id=_kw_oid, interaction_id=_kw_iid,
                    triggering_text=_kw_trig,
                )
                # ── TAXO2-08 (FOLD A): Vorschlag erfassen (Slot A Keyword/Fast-Lane) ──
                # Latenz-neutral (Punkt 25): NUR ein RAM-Append. B1: _kw_iid ist via
                # get_or_open_moment (:292) schon gesetzt. Anon-Vertrag (Plan 09): der
                # gematchte Profil-Vorschlag ist profil-statisch/niedrig-PII -> via
                # anonymize_for_storage mit lebendem Per-SID-Cache gesaeubert (nie roh,
                # nie cache=None). try/except: Live-Loop crasht nie.
                try:
                    _kw_sugg = _profile_gegenargument(match.get('profile_einwand') or {})
                    if _kw_sugg:
                        from services.anonymization import anonymize_for_storage as _anon_store_kw
                        _kw_sugg_storage = _anon_store_kw(_kw_sugg, sid)
                        _ls.record_suggestion_offer(
                            slot='A', source='keyword', model=None,
                            suggestion_text=_kw_sugg_storage, interaction_id=_kw_iid,
                            einwand_typ=match.get('matched_label'),
                        )
                except Exception as _kw_cap_e:
                    print(f"[KW] record_suggestion_offer skip (sid={sid}): {type(_kw_cap_e).__name__}")
        except Exception as _kw_emit_e:
            print(f"[KW] intent_event emit skip (sid={sid}): {type(_kw_emit_e).__name__}")

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
