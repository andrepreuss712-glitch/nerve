"""
Runtime state for the live NERVE session.
All globals and shared state lives here to avoid circular imports.
"""
import os
import threading
import time
import uuid
import logging as _logging
from datetime import datetime
from typing import Optional
from config import ANALYSE_INTERVALL, MERGE_WINDOW_S, SPEAKER_DEBOUNCE_S, KATEGORIE_LABEL

_logger = _logging.getLogger(__name__)

# ── Einwand-Keyword-Matcher Registry (Wave 2: BUG-10-LAT) ────────────────────
# Pro Session eine EinwandKeywordMatcher-Instanz. Lazy-init via get_matcher(sid).
keyword_matchers: dict = {}          # sid -> EinwandKeywordMatcher
keyword_matchers_lock = threading.Lock()


def get_matcher(sid: str):
    """Gibt den EinwandKeywordMatcher fuer die Session zurueck (lazy-init)."""
    with keyword_matchers_lock:
        if sid not in keyword_matchers:
            from services.einwand_keyword_matcher import EinwandKeywordMatcher
            keyword_matchers[sid] = EinwandKeywordMatcher()
        return keyword_matchers[sid]


def drop_matcher(sid: str) -> None:
    """Entfernt den Matcher fuer `sid` — aufzurufen bei Session-Ende."""
    with keyword_matchers_lock:
        keyword_matchers.pop(sid, None)

# ── Log-Ordner ────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# ── Pause State ───────────────────────────────────────────────────────────────
pause_lock = threading.Lock()
is_paused  = False

# ── Transkript-Buffer ─────────────────────────────────────────────────────────
buffer_lock       = threading.Lock()
transcript_buffer = []
analysiert_bisher = []
analyse_trigger   = threading.Event()

# ── Coaching-Buffer ───────────────────────────────────────────────────────────
coaching_lock    = threading.Lock()
coaching_buffer  = []
coaching_trigger = threading.Event()
painpoints_lock  = threading.Lock()
painpoints       = []

# ── Gegenargument-Tracking ────────────────────────────────────────────────────
gegenargument_log_lock = threading.Lock()
gegenargument_log      = []

# ── Hilfe-Button Tracking ─────────────────────────────────────────────────────
hilfe_log_lock = threading.Lock()
hilfe_log      = []

# ── Quick-Action Tracking ─────────────────────────────────────────────────────
quick_action_log_lock = threading.Lock()
quick_action_log      = []

# ── Phasenwechsel-Tracking ────────────────────────────────────────────────────
phasen_log_lock = threading.Lock()
phasen_log      = []

# ── Session-Metadaten ─────────────────────────────────────────────────────────
session_meta_lock = threading.Lock()
session_meta = {
    'profil_name': '', 'profil_branche': '', 'schwierigkeit': None,
    'start_zeit': None, 'end_zeit': None,
    'gesamt_segmente': 0, 'gesamt_einwaende': 0,
    'einwaende_behandelt': 0, 'einwaende_fehlgeschlagen': 0,
    'einwaende_ignoriert': 0, 'vorwaende_erkannt': 0,
    'painpoints_gesamt': 0, 'kaufsignale_gesamt': 0,
    'coaching_tipps_gesamt': 0, 'hilfe_button_genutzt': 0,
    'quick_actions_genutzt': 0, 'skript_abdeckung_prozent': 0,
    'redeanteil_durchschnitt': 0, 'tempo_durchschnitt': 0, 'laengster_monolog': 0,
    'kb_start': 30, 'kb_end': 30, 'kb_min': 30, 'kb_max': 30,
    'sterne_bewertung': None, 'feedback_kommentar': '',
}

# ── Satz-Zusammenführung ──────────────────────────────────────────────────────
_merge_lock    = threading.Lock()
_merge_pending = {}

# ── Zeilen-ID Counter ─────────────────────────────────────────────────────────
_line_id_counter = 0
_line_id_lock    = threading.Lock()

def next_line_id(sid: str) -> str:
    """Returns next sequential line ID for the given SID. Ghost-SID-safe."""
    with _session_state_lock:
        if sid not in _session_state:
            return '0'  # Ghost-SID guard
        cnt = _session_state[sid].get('_line_id_counter', 0) + 1
        _session_state[sid]['_line_id_counter'] = cnt
        return str(cnt)


def get_sid_paused(sid: str) -> bool:
    """Thread-safe read of is_paused for a single SID. Returns False for unknown SIDs."""
    with _session_state_lock:
        return _session_state.get(sid, {}).get('state', {}).get('is_paused', False)


# ── Analyse-State ─────────────────────────────────────────────────────────────
state_lock = threading.Lock()
state = {
    'version':          0,
    'aktiv':            False,
    'ergebnis':         None,
    'line_id':          None,
    'kaufbereitschaft': 30,
    'ewb_clicks':       [],    # Liste von dicts: {'einwand_typ': str, 'success': bool, 'ts': iso, 'antwort_text': str|None, 'einwand_text': str|None}
    # ── Phase 04.8: Conversation Phase Model (6-phase auto-detected) ──
    'current_phase':        1,
    'current_phase_name':   'Opener',
    'phase_confidence':     0.0,
    'phase_changed_at':     None,
    'phase_change_count':   0,
    # ── Phase 04.8: Readiness Score (deterministic) ──
    'readiness_score':      30,
    'readiness_bucket':     'cold',
    'score_factors_seen':   {},   # dict[str,int] — tally for compute_readiness_score
    # ── Phase 04.8: Active Hint (single-slot prio winner) ──
    'active_hint':          None,
    # ── Phase 04.8: Dynamic EWB Buttons (phase-aware) ──
    'ewb_buttons':          None,
    # ── Phase 04.8: Cold-Call Inference ──
    'cold_call_inference':  None,
    # ── Phase 04.11: Active Learning Cards (D-09) ──
    'active_learning_cards': [],
    'precall_briefing': None,  # PreCall briefing text injected at session start
    # ── Phase 06.2 Wave 2: Keyword-Match busy-guard + mic-mute ──
    'slot1_variant_busy_until': 0.0,  # monotonic timestamp — shared lock between keyword-pipe and analyse_loop
    'mic_muted': False,               # set via 'mute_mic' socket event
    # ── Phase 08.5: QA-Pipeline state ──
    'active_profile_id': None,        # set in set_active_profile_with_id() at session start
    'kw_fired_for_line': None,        # D-02: line_id of last keyword-matcher hit; qa_pipeline skips when equal to line_id
}

# ── Conversation Log ──────────────────────────────────────────────────────────
log_lock         = threading.Lock()
conversation_log = []

# ── Rollen-Tausch ─────────────────────────────────────────────────────────────
roles_lock    = threading.Lock()
roles_swapped = False

# ── Sprecher-Fallback für Log ─────────────────────────────────────────────────
_log_sp_lock = threading.Lock()
_log_last_sp = None

# ── Zweiter Sprecher gesehen? ─────────────────────────────────────────────────
_sp2_lock       = threading.Lock()
_second_sp_seen = False

# ── Sprecher-Stabilisierung ───────────────────────────────────────────────────
_speaker_lock      = threading.Lock()
_confirmed_speaker = None
_pending_speaker   = None
_pending_since     = None

# ── Berater-ohne-Frage-Zähler ─────────────────────────────────────────────────
_bof_lock  = threading.Lock()
_bof_count = 0

# ── Kaufbereitschaft ──────────────────────────────────────────────────────────
kb_lock                 = threading.Lock()
kaufbereitschaft        = 30
kaufbereitschaft_verlauf = []  # [{'ts': '...', 'wert': 30}, ...]

# ── Aktive Gesprächsphase ─────────────────────────────────────────────────────
phase_lock      = threading.Lock()
aktive_phase_idx = 0

# ── Sprachstatistik ───────────────────────────────────────────────────────────
# Single-Source-of-State (Konstrukt §0.1): Sprach-Zähler sind AUSSCHLIESSLICH per-SID
# (_session_state[sid]: berater_words / kunde_words / session_start_time /
# laengster_monolog_sek / _current_monolog_start). _flush_segment schreibt nur dorthin,
# get_speech_stats(sid) liest nur dorthin (unter _session_state_lock). Die früheren
# Modul-Globalen + speech_lock wurden NIE befüllt (toter Ghost-Read → immer 0) und sind
# komplett entfernt.

# ── Abgedeckte Phasen ─────────────────────────────────────────────────────────
covered_phases_lock = threading.Lock()
covered_phases      = set()

# set_active_profile / get_active_profile deleted Phase 08.19.4 D-04/D-05 — use set_profile_for_sid / get_profile_for_sid


# ── Per-SID State Infrastructure (Phase 08.19.4 — DSGVO) ─────────────────────
# Replaces single-global pattern. One entry per WebSocket SID.
# Pattern copied from deepgram_service._deepgram_sessions (same lifecycle).
# Lock granularity: acquire lock for snapshot only, release before long ops.

# ── Per-SID Profil-Cache (D-01) — analog _deepgram_sessions Pattern ──────────
_per_sid_profile: dict = {}     # {sid: (name, daten)}
_per_sid_lock = threading.Lock()

# ── Per-SID Session-State (D-02) ─────────────────────────────────────────────
_session_state: dict = {}       # {sid: {key: value, ...}}
_session_state_lock = threading.Lock()

# ── Per-SID Transcript Buffer (D-02 Tier 2 PFLICHT) ──────────────────────────
# Replaces module-global transcript_buffer. SID written by _flush_segment.
# analyse_loop reads per-SID instead of the global buffer.
_per_sid_transcript: dict = {}          # {sid: list[dict]}
_per_sid_transcript_lock = threading.Lock()

# ── Per-SID Coaching Buffer (WR-03 — DSGVO: prevents cross-user coaching data leak) ─
# Replaces module-global coaching_buffer. Same lifecycle as _per_sid_transcript.
# Producer: _flush_segment appends per SID. Consumer: coaching_loop reads per SID.
_per_sid_coaching_buffer: dict = {}     # {sid: list[dict]}
_per_sid_coaching_lock = threading.Lock()


def set_profile_for_sid(sid: str, name: str, daten: dict) -> None:
    """Cache profile for an active WebSocket SID. Ghost-SID guard: drops silently if
    SID no longer active in _session_state (async load completing after disconnect)."""
    with _per_sid_lock:
        # Ghost-SID guard: check _session_state for SID liveness.
        # CPython dict __contains__ is GIL-safe; slight TOCTOU window is acceptable —
        # worst case: write completes then pop_session_state clears it on next line.
        if sid not in _session_state:
            _logger.debug(f"[SID] set_profile_for_sid: Ghost SID {sid!r} — dropped")
            return
        _per_sid_profile[sid] = (name or '', daten if isinstance(daten, dict) else {})


def get_profile_for_sid(sid: str) -> tuple:
    """Returns (name, daten) for SID. Returns ('', {}) + warning for unknown SID (D-01)."""
    with _per_sid_lock:
        result = _per_sid_profile.get(sid)
    if result is None:
        _logger.warning(f"[SID] get_profile_for_sid: unknown SID {sid}")
        return ('', {})
    return result


# ── Per-SID PreCall-Briefing Cache (D-09 Phase 08.20) ────────────────────────
# Briefing stored as sub-key of _session_state[sid]['_briefing'] — NOT a separate dict.
# Uses _session_state_lock (no extra lock needed — eliminates deadlock risk).
# Ghost-SID guard: if SID not in _session_state, write is silently dropped.
# Lifecycle: set on PreCall success, auto-cleared when pop_session_state() pops _session_state[sid].

def set_briefing_for_sid(sid: str, briefing_text: str) -> None:
    """Cache PreCall-Briefing text for an active SID. Ghost-SID guard prevents async
    race when recherche_firma() completes after user disconnect (HIGH-1 fix)."""
    with _session_state_lock:
        if sid not in _session_state:
            _logger.debug(f"[SID] set_briefing_for_sid: Ghost SID {sid!r} — dropped (post-disconnect race)")
            return
        _session_state[sid]['_briefing'] = briefing_text or ''


def get_briefing_for_sid(sid: str) -> str | None:
    """Returns cached briefing text for SID, or None if not set or SID unknown."""
    with _session_state_lock:
        return _session_state.get(sid, {}).get('_briefing')


# ── Per-SID AnrufAnonymisierer Cache (D-06 Phase 08.23.2.B) ──────────────────
# AnrufAnonymisierer stored as sub-key of _session_state[sid]['anonymisierer'].
# Uses _session_state_lock (no extra lock needed — eliminates deadlock risk).
# Ghost-SID guard: if SID not in _session_state, init is silently skipped.
# Lifecycle: set via init_anonymisierer() after init_session_state(), auto-cleared
# when pop_session_state() pops _session_state[sid] (D-06 Trigger 1+2).
# mapping NIEMALS in DB persistiert — nur RAM-Cache.

def init_anonymisierer(sid: str) -> None:
    """Erstellt AnrufAnonymisierer fuer SID und legt ihn in _session_state[sid]['anonymisierer'].
    Muss NACH init_session_state() aufgerufen werden.
    Ghost-SID Guard: kein Fehler wenn SID nicht mehr existiert (Race-Condition Pitfall 3).
    """
    from services.anonymization import AnrufAnonymisierer
    with _session_state_lock:
        if sid not in _session_state:
            print(f'[ANON] init_anonymisierer: Ghost SID {sid!r} — skipped')
            return
        _session_state[sid]['anonymisierer'] = AnrufAnonymisierer()
        print(f'[ANON] AnrufAnonymisierer erstellt fuer sid={sid!r}')


def get_anonymisierer(sid: str):
    """Gibt AnrufAnonymisierer fuer SID zurueck, oder None wenn nicht initialisiert/SID unbekannt.
    Thread-safe. Gibt None bei Ghost-SID (Race-Condition Pitfall 3 — Caller handelt None defensiv).
    """
    with _session_state_lock:
        return _session_state.get(sid, {}).get('anonymisierer')


def init_session_state(sid: str, user_id: int, org_id: int, profile_id=None,
                       market: str = 'dach', language: str = 'de',
                       mode: str = 'cold_call') -> None:
    """Initialize _session_state[sid] for a new WebSocket connection (D-02)."""
    with _session_state_lock:
        _session_state[sid] = {
            'user_id': user_id,
            'org_id': org_id,
            'active_profile_id': profile_id,
            'kaufbereitschaft': 30,
            'active_sid': sid,
            'market': market,
            'language': language,
            'mode': mode,
            'conversation_log': [],
            'berater_words': 0,
            'kunde_words': 0,
            'roles_swapped': False,
            'covered_phases': set(),
            'kaufbereitschaft_verlauf': [],  # Tier 3 — same code operation
            '_bof_count': 0,
            '_pending_speaker': None,
            '_confirmed_speaker': None,
            '_pending_since': None,
            '_log_last_sp': None,
            # D-01: state dict as sub-key (single write path after migration)
            # NOTE (HIGH-2 coexistence): Services still WRITE to module-level globals
            # (session_meta, phasen_log, etc.) in this phase. These sub-keys are present
            # for future cleanup phases. Routes/ callers read from module-level globals.
            'state': {
                'version':               0,
                'aktiv':                 False,
                'ergebnis':              None,
                'line_id':               None,
                'kaufbereitschaft':      30,
                'ewb_clicks':            [],
                'current_phase':         1,
                'current_phase_name':    'Opener',
                'phase_confidence':      0.0,
                'phase_changed_at':      None,
                'phase_change_count':    0,
                'readiness_score':       30,
                'readiness_bucket':      'cold',
                'score_factors_seen':    {},
                'active_hint':           None,
                'ewb_buttons':           None,
                'cold_call_inference':   None,
                'active_learning_cards': [],
                'precall_briefing':      None,
                'slot1_variant_busy_until': 0.0,
                'mic_muted':             False,
                'active_profile_id':     profile_id,
                'kw_fired_for_line':     None,
                'is_paused':             False,   # REQ-01
                'ft_session_id':         None,
                'session_anrede':        None,
                # Phase 08.23.2.C.R — Gatekeeper-State (Default: Sekretaer-Modus, DSGVO Single-Speaker)
                'contact_category':      'gatekeeper', # 'target' | 'gatekeeper' — Default gatekeeper (REQ-5)
                'current_mode':          'gatekeeper',  # Default gatekeeper; manuell via pip-mode-indicator aenderbar
                'context_notes':         [],            # Phase 08.23.2.I aktiviert Befuellung
                # Hysterese-interne Keys (Req-3) — Token-basiert (z.B. 'opener', 'pitch')
                # HINWEIS: 'current_phase' (Integer) oben ist das alte Phase-04.8-System.
                # 'phase_hint_count', 'pending_phase', 'phase_entered_at' sind neu fuer Phase-C.
                'phase_hint_count':      0,
                'pending_phase':         None,
                'phase_entered_at':      None,        # monotonic seconds
                # Call-Record-Referenz (Pitfall 4 — call_id-Provenienz)
                'call_id':               None,        # UUID nach Call-Insert in create_call_for_sid
                # Phase 08.23.2.D - Audio-Health-Hysterese (REQ-D-7)
                # False = keine aktive Warnung; True nach erstem Score<0.70-Emit,
                # zurueck auf False sobald Score>0.80 (Hysterese - verhindert Spam).
                'audio_warn_active':     False,
                # ── TAXO1-Welle 4: Moment-Fenster (I-4-FOLD + Gemini-R2) ──────
                # Ereignis-getriebenes Einwand-FENSTER pro-SID (KEIN line_id-Key,
                # KEIN module-globaler state). interaction_id = offene UUID oder None;
                # moment_opened_mode = mode bei OEFFNUNG (Downgrade-Erkennung);
                # moment_opened_monotonic = OEFFNUNGS-Zeitpunkt (NIE refresht, nur
                # fuer den Max-Dauer-Deckel). Gemini-R2: KEIN refreshender Idle-Timer
                # (der war Teil der Ueber-Verklumpung — distinkte Zyklen klebten).
                'interaction_id':           None,
                'moment_opened_mode':       None,
                'moment_opened_monotonic':  0.0,
                # ── TAXO1-Welle 4: IL-2 Live-Uebergabe-Vertrag fuer TAXO3 ─────
                # Medium-Lane schreibt primary_intent(=intent_type) + confidence
                # per-SID VOR dem Antwort-Trigger; TAXO3 build_answer_context liest
                # sie LIVE aus dem RAM (nicht aus der DB). Seed None (TAXO3 .get()
                # toleriert None vor dem ersten Intent; danach immer ein float).
                'primary_intent':           None,
                'confidence':               None,
                # ── TAXO1-Welle 4 Addition A (§0.1): phase_cycle_counter per-SID ──
                # War global function-attribute analyse_loop._phase_cycle_counter
                # (ueber ALLE SIDs geteilt -> erratische Phasen-Kadenz bei parallelen
                # Calls). Jetzt per-SID single-source wie die Welle-3-Zaehler.
                'phase_cycle_counter':      0,
            },
            # D-04: tracking logs — initialized as per-SID scaffolding for future migration.
            # NOTE (HIGH-2 coexistence): Services still WRITE to module-level globals
            # (session_meta, phasen_log, etc.) in this phase. These sub-keys are present
            # for future cleanup phases. Routes/ callers read from module-level globals.
            'session_meta': {
                'profil_name': '', 'profil_branche': '', 'schwierigkeit': None,
                'start_zeit': None, 'end_zeit': None,
                'gesamt_segmente': 0, 'gesamt_einwaende': 0,
                'einwaende_behandelt': 0, 'einwaende_fehlgeschlagen': 0,
                'einwaende_ignoriert': 0, 'vorwaende_erkannt': 0,
                'painpoints_gesamt': 0, 'kaufsignale_gesamt': 0,
                'coaching_tipps_gesamt': 0, 'hilfe_button_genutzt': 0,
                'quick_actions_genutzt': 0, 'skript_abdeckung_prozent': 0,
                'redeanteil_durchschnitt': 0, 'tempo_durchschnitt': 0,
                'laengster_monolog': 0,
                'kb_start': 30, 'kb_end': 30, 'kb_min': 30, 'kb_max': 30,
                'sterne_bewertung': None, 'feedback_kommentar': '',
            },
            'phasen_log':            [],
            'gegenargument_log':     [],
            'hilfe_log':             [],
            'quick_action_log':      [],
            'painpoints':            [],
            # analysiert_bisher is FULLY per-SID (no global write path remains after Plan 03)
            'analysiert_bisher':     [],
            '_second_sp_seen':       False,
            'aktive_phase_idx':      0,
            'session_start_time':    None,
            'laengster_monolog_sek': 0.0,
            '_current_monolog_start': None,
            '_line_id_counter':      0,
            'anonymisierer':         None,    # D-06: AnrufAnonymisierer, erstellt via init_anonymisierer()
            # Phase 08.23.2.D - Word-Confidence-Buffer (D-06)
            # Liste von (ts_ms: int, confidence: float) Tuples;
            # cleared bei reset_session/pop_session_state automatisch.
            'word_confidences':      [],
        }
    # WR-03: init per-SID coaching buffer (separate lock — same lifecycle as transcript)
    with _per_sid_coaching_lock:
        _per_sid_coaching_buffer[sid] = []


def pop_session_state(sid: str) -> None:
    """Remove all per-SID state on disconnect. Briefing is stored as _session_state[sid]['_briefing']
    and is auto-cleaned when the dict entry is popped — no separate briefing cleanup needed (HIGH-2 fix)."""
    with _session_state_lock:
        _session_state.pop(sid, None)   # clears ['_briefing'] sub-key automatically
    with _per_sid_lock:
        _per_sid_profile.pop(sid, None)
    with _per_sid_transcript_lock:
        _per_sid_transcript.pop(sid, None)
    # WR-03: cleanup per-SID coaching buffer on disconnect
    with _per_sid_coaching_lock:
        _per_sid_coaching_buffer.pop(sid, None)
    drop_matcher(sid)
    # I-4-FOLD: das Moment-Fenster (interaction_id/moment_opened_*) liegt in
    # _session_state[sid]['state'] und wird mit dem pop oben automatisch entfernt
    # (Gemini-Punkt: Memory-Cleanup der per-SID-Klammer bei Disconnect/Beenden).


# ── TAXO1-Welle 4: Moment-FENSTER (I-4-FOLD + Gemini-R2) ──────────────────────
# MOMENT-FENSTER (I-4-FOLD): ereignis-getriebenes Einwand-Fenster pro-SID; oeffnet
# bei erstem Kunden-Einwand, schliesst wenn der Berater ANTWORTET (Task 2 c2) /
# Meeting-Sprecher-Wechsel / Modus-Downgrade / Max-Dauer-Deckel. Hintergrund-
# Etikett, GATET NICHT die Live-Reaktion (Soll-Verhalten §5: Speed gewinnt).
#
# LOCK-FREE (Gemini-Punkt a): beide Helfer NEHMEN KEINEN Lock — der AUFRUFER haelt
# `_session_state_lock` (Muster matcher: caller holds lock, writes directly). KEIN
# RLock. `state_lock` (module-global) und `_session_state_lock` NIE gleichzeitig
# halten -> kein Lock-Ordering-Deadlock. KEIN line_id-Key, KEIN refreshender Timer.

def get_or_open_moment(sid, *, mode, now) -> Optional[str]:
    """Gibt die interaction_id des offenen Einwand-Fensters zurueck; oeffnet ein
    neues beim ersten Kunden-Einwand. LOCK-FREE — Aufrufer haelt `_session_state_lock`.

    - (d) Modus-Downgrade: offenes Fenster + moment_opened_mode != mode -> schliessen
      (frisches Fenster fuer den neuen Modus, z.B. Meeting->Cold-Call bei Consent-Verweigerung).
    - (b) NICHT-refreshender Max-Dauer-Deckel: offen + now-opened > MOMENT_WINDOW_MAX_S
      -> harte Notbremse, schliessen. Gemessen ab OEFFNUNG, NICHT ab letzter Aktivitaet.
    - OEFFNEN: interaction_id is None -> mint uuid4, setze 3 Keys, return id.
    - FORTSETZEN (JOIN): sonst -> return bestehende id OHNE Timer-Refresh (mehrere
      Einwand-Echos / pausen-gesplittete Fortsetzung desselben Einwands = EIN Moment).

    Gibt None zurueck, falls die SID/State nicht (mehr) existiert (kein Crash).
    """
    from config import MOMENT_WINDOW_MAX_S
    _sd = _session_state.get(sid)
    if not _sd:
        return None
    st = _sd.get('state')
    if st is None:
        return None

    # (d) Modus-Downgrade-Reset
    if st.get('interaction_id') is not None and st.get('moment_opened_mode') != mode:
        st['interaction_id'] = None
        st['moment_opened_mode'] = None
        st['moment_opened_monotonic'] = 0.0
    # (b) NICHT-refreshender Max-Dauer-Deckel ab Oeffnung
    elif (st.get('interaction_id') is not None
          and (now - (st.get('moment_opened_monotonic') or 0.0)) > MOMENT_WINDOW_MAX_S):
        st['interaction_id'] = None
        st['moment_opened_mode'] = None
        st['moment_opened_monotonic'] = 0.0

    if st.get('interaction_id') is None:
        # OEFFNEN
        iid = str(uuid.uuid4())
        st['interaction_id'] = iid
        st['moment_opened_mode'] = mode
        st['moment_opened_monotonic'] = now
        return iid
    # FORTSETZEN (JOIN) — KEIN Timer-Refresh (Gemini-R2)
    return st['interaction_id']


def close_moment(sid, *, reason) -> None:
    """Schliesst das offene Einwand-Fenster (interaction_id=None) -> der naechste
    Kunden-Einwand oeffnet ein neues. LOCK-FREE — Aufrufer haelt `_session_state_lock`.
    Idempotent (schon None -> no-op)."""
    _sd = _session_state.get(sid)
    if not _sd:
        return
    st = _sd.get('state')
    if st is None:
        return
    if st.get('interaction_id') is not None:
        st['interaction_id'] = None
        st['moment_opened_mode'] = None
        st['moment_opened_monotonic'] = 0.0
        print(f"[MOMENT] close sid={sid} reason={reason}")


def create_call_for_sid(sid: str, user_id: int, call_mode: str = 'cold_call') -> Optional[str]:
    """Legt Call-Record an und speichert call_id im per-SID-State.

    Phase 08.23.2.C Pitfall 4 — call_events.call_id ist NOT NULL.
    Erstellt bei Session-Start einen Call-Eintrag, sodass CallEvent-Inserts
    (z.B. phase_change, uwg_hard_block) eine gueltige FK-Referenz haben.

    call_mode: 'cold_call' oder 'meeting_consented' (CHECK-Constraint in DB).
    Unbekannte Modi werden auf 'cold_call' gemappt.

    Returns: call_id (UUID-string) oder None bei Fehler.
    """
    # Phase 08.23.2.C.R.F Fix — Atomare Idempotenz (Cross-AI Review: TOCTOU bei Reconnect).
    # Check + Sentinel-Write muessen unter DEMSELBEN Lock-Eintritt passieren.
    # Zwei parallele handle_start_live_session-Aufrufe koennen sonst beide None lesen
    # und beide einen Call-Record in DB schreiben (Doppel-Records + Doppel-mode_initial).
    with _session_state_lock:
        _existing_cid_atomic = _session_state.get(sid, {}).get('state', {}).get('call_id')
        if _existing_cid_atomic is not None and _existing_cid_atomic != '__call_pending__':
            print(f'[live_session] create_call_for_sid: call_id already set, returning existing '
                  f'sid={sid!r} call_id={_existing_cid_atomic!r}')
            return _existing_cid_atomic
        if _existing_cid_atomic == '__call_pending__':
            print(f'[live_session] create_call_for_sid: in-progress by parallel call, skipping '
                  f'sid={sid!r}')
            return None
        # Sentinel setzen: kein anderer Thread kann jetzt ebenfalls None lesen und fortfahren
        if sid in _session_state:
            _session_state[sid].setdefault('state', {})['call_id'] = '__call_pending__'
    from datetime import timezone as _tz
    from database.db import SessionLocal as _SL
    from database.models import Call
    # Mapping auf erlaubte call_mode-Werte (CHECK-Constraint ck_calls_call_mode)
    _allowed_modes = ('cold_call', 'meeting_consented')
    _db_mode = call_mode if call_mode in _allowed_modes else 'cold_call'
    _db = _SL()
    try:
        call = Call(
            user_id=user_id,
            call_mode=_db_mode,
            started_at=datetime.now(_tz.utc),
            transcript_storage='none',
        )
        _db.add(call)
        _db.commit()
        _db.refresh(call)
        cid = str(call.id)
        with _session_state_lock:
            if sid in _session_state:
                _session_state[sid].setdefault('state', {})['call_id'] = cid
        print(f'[live_session] create_call_for_sid: call_id={cid!r} sid={sid!r}')
        # D-04b: mode_initial-Event — liest aktuellen Modus aus State (nach call_id-Write)
        with _session_state_lock:
            _mode_init_state = _session_state.get(sid, {}).get('state', {})
            _current_mode = _mode_init_state.get('current_mode', 'gatekeeper')
            _current_cat = _mode_init_state.get('contact_category', 'gatekeeper')
        _db_mi = None
        try:
            from database.db import SessionLocal as _SL_mi
            from database.models import CallEvent as _CE_mi
            import time as _t_mi
            _db_mi = _SL_mi()
            try:
                _db_mi.add(_CE_mi(
                    call_id=cid,
                    event_type='mode_initial',
                    event_ts_ms=int(_t_mi.time() * 1000),
                    payload={
                        'mode': _current_mode,
                        'category': _current_cat,
                        'sid': sid,
                        'timestamp': _t_mi.monotonic(),
                    },
                ))
                _db_mi.commit()
                print(f'[live_session] mode_initial event written: call_id={cid!r} mode={_current_mode!r}')
            finally:
                _db_mi.close()
        except Exception as _mi_err:
            print(f'[live_session] mode_initial persist Fehler (non-fatal): {type(_mi_err).__name__}: {_mi_err}')
        return cid
    except Exception as e:
        print(f'[live_session] create_call_for_sid Fehler: {type(e).__name__}: {e}')
        try:
            _db.rollback()
        except Exception:
            pass
        # Sentinel aufraumen: DB-Fehler darf '__call_pending__' nicht im State lassen
        with _session_state_lock:
            if sid in _session_state:
                _st_err = _session_state[sid].get('state', {})
                if _st_err.get('call_id') == '__call_pending__':
                    _st_err['call_id'] = None
        return None
    finally:
        _db.close()


def _load_profile_cache(sid: str, user_id: int, profile_id: int) -> None:
    """Load ProfileOpener, User display fields, ProfileFaq into _session_state[sid]['_profile_cache'].
    Called once at session start by handle_start_live_session. Non-fatal on failure.
    After this call, build_profile_context() reads from cache only (no DB in hot path — HIGH-3 fix).
    Note: ProfileOpener uses 'inhalt' field (not 'content'); ProfileFaq uses 'frage_muster'/'antwort'."""
    try:
        from database.db import SessionLocal as _SL
        from database.models import ProfileOpener as _PO
        _db = _SL()
        try:
            # ORDER BY id LIMIT 1 — deterministic, cache-stable (MEDIUM fix)
            _opener = _db.query(_PO).filter_by(
                profile_id=profile_id
            ).order_by(_PO.id).limit(1).first()

            # User display fields
            _firstname = ''
            try:
                from database.models import User as _User
                _user = _db.query(_User).filter_by(id=user_id).first()
                _firstname = getattr(_user, 'vorname', None) or ''
            except Exception:
                pass

            # ProfileFaq — all FAQs for profile (literal mode if column exists, else all)
            _faqs = []
            try:
                from database.models import ProfileFaq as _FAQ
                try:
                    _faq_rows = _db.query(_FAQ).filter_by(
                        profile_id=profile_id, mode='literal'
                    ).limit(20).all()
                except Exception:
                    # mode column filter may fail on some DB states — load all
                    _faq_rows = _db.query(_FAQ).filter_by(
                        profile_id=profile_id
                    ).limit(20).all()
                for f in _faq_rows:
                    _q = getattr(f, 'frage_muster', '') or ''
                    _a = getattr(f, 'antwort', '') or ''
                    if _q and _a:
                        _faqs.append({'q': _q, 'a': _a})
            except Exception as _faq_e:
                print(f"[Cache] ProfileFaq load failed (non-fatal): {_faq_e}")

            # Profile.branche — DB column (moved from daten JSON in Phase 08.19.1)
            _profile_branche = ''
            try:
                from database.models import Profile as _Prof
                _p_row = _db.query(_Prof).filter_by(id=profile_id).first()
                _profile_branche = getattr(_p_row, 'branche', None) or ''
            except Exception as _br_e:
                print(f"[Cache] Profile.branche load failed (non-fatal): {_br_e}")

            _cache = {
                'opener_content': getattr(_opener, 'inhalt', None) if _opener else None,
                'user_firstname': _firstname,
                'faqs': _faqs,
                'profile_branche': _profile_branche,
            }
            with _session_state_lock:
                if sid in _session_state:
                    _session_state[sid]['_profile_cache'] = _cache
                    print(f"[Cache] _profile_cache loaded for sid={sid}: "
                          f"opener={'yes' if _cache['opener_content'] else 'no'}, faqs={len(_faqs)}")
        finally:
            _db.close()
    except Exception as _e:
        print(f"[Cache] _load_profile_cache failed for sid={sid} (non-fatal): {_e}")


def load_learning_cards(sid: str, user_id: int) -> None:
    """D-09: Load active learning cards per-SID at session start."""
    try:
        from services.coaching_service import get_active_cards
        cards = get_active_cards(user_id)
        with _session_state_lock:
            if sid not in _session_state:
                return  # Ghost-SID guard
            _session_state[sid]['state']['active_learning_cards'] = cards[:5]
        print(f"[Coach] {len(cards)} aktive Lernkarten geladen sid={sid}")
    except Exception as e:
        print(f"[Coach] Lernkarten laden fehlgeschlagen sid={sid}: {e}")
        with _session_state_lock:
            if sid in _session_state:
                _session_state[sid]['state']['active_learning_cards'] = []


# ── Letztes Post-Call Snapshot ────────────────────────────────────────────────
last_postcall_lock = threading.Lock()
last_postcall      = None


def stabilize_speaker(sid: str, raw):
    """Debounced speaker stabilization. Reads/writes per-SID speaker keys."""
    with _session_state_lock:
        if sid not in _session_state:
            return None  # Ghost-SID guard
        ss = _session_state[sid]
        confirmed = ss.get('_confirmed_speaker')
        pending   = ss.get('_pending_speaker')
        since     = ss.get('_pending_since')
        if raw is None:
            return confirmed
        if raw == confirmed:
            ss['_pending_speaker'] = None
            ss['_pending_since']   = None
            return confirmed
        if raw != pending:
            ss['_pending_speaker'] = raw
            ss['_pending_since']   = time.monotonic()
            since = ss['_pending_since']
        elapsed = time.monotonic() - since
        if elapsed >= SPEAKER_DEBOUNCE_S:
            ss['_confirmed_speaker'] = ss['_pending_speaker']
            ss['_pending_speaker']   = None
            ss['_pending_since']     = None
        return ss.get('_confirmed_speaker')


def ist_painpoint_duplikat(neu: str, bestehende: list) -> bool:
    neu_w = set(neu.lower().split())
    if not neu_w:
        return False
    for pp in bestehende:
        alt_w = set(pp['text'].lower().split())
        if not alt_w:
            continue
        overlap = len(neu_w & alt_w)
        kleiner = min(len(neu_w), len(alt_w))
        if overlap / kleiner >= 0.6:
            return True
    return False


def _flush_segment(key: str):
    """Timer-Callback: übergibt zusammengeführtes Segment an die Analyse-Queues."""
    with _merge_lock:
        pending = _merge_pending.pop(key, None)
    if not pending:
        return
    merged_text     = " ".join(pending['texts'])
    line_id         = pending['line_id']
    speaker         = pending['speaker']
    roles_confirmed = pending['roles_confirmed']
    sp_name         = pending['sp_name']
    t_start         = pending.get('t_start', time.monotonic())

    # Sprachstatistik aktualisieren
    word_count = len(merged_text.split())
    now_m = time.monotonic()
    # NEW (per-SID):
    _flush_sid = pending.get('sid')
    if _flush_sid:
        with _session_state_lock:
            if _flush_sid in _session_state:
                _ss = _session_state[_flush_sid]
                if sp_name == 'Berater':
                    _ss['berater_words'] = _ss.get('berater_words', 0) + word_count
                    if _ss.get('_current_monolog_start') is None:
                        _ss['_current_monolog_start'] = t_start
                    dur = now_m - _ss['_current_monolog_start']
                    if dur > _ss.get('laengster_monolog_sek', 0.0):
                        _ss['laengster_monolog_sek'] = dur
                elif sp_name == 'Kunde':
                    _ss['kunde_words'] = _ss.get('kunde_words', 0) + word_count
                    _ss['_current_monolog_start'] = None

    if not roles_confirmed or speaker != 0:
        _flush_sid = pending.get('sid')
        if _flush_sid:
            with _per_sid_transcript_lock:
                _per_sid_transcript.setdefault(_flush_sid, []).append(
                    {'text': merged_text, 'line_id': line_id, 't_start': t_start}
                )
        else:
            # Fallback: pre-08.19.4 entry without SID (edge case — should not occur post-migration)
            with buffer_lock:
                transcript_buffer.append({'text': merged_text, 'line_id': line_id, 't_start': t_start})
        analyse_trigger.set()

    # WR-03: append to per-SID coaching buffer (not module-global) to prevent cross-user leak
    _flush_sid = pending.get('sid')
    if _flush_sid:
        with _per_sid_coaching_lock:
            _per_sid_coaching_buffer.setdefault(_flush_sid, []).append(
                {'text': merged_text, 'speaker': sp_name, 't_start': t_start}
            )
    else:
        # Fallback for pre-08.19.4 entries without SID (edge case — should not occur post-migration)
        with coaching_lock:
            coaching_buffer.append({'text': merged_text, 'speaker': sp_name, 't_start': t_start})
    coaching_trigger.set()


def update_kaufbereitschaft(delta: int):
    """Aktualisiert Kaufbereitschaft mit Delta, clamped to [5, 100]."""
    global kaufbereitschaft
    with kb_lock:
        kaufbereitschaft = max(5, min(100, kaufbereitschaft + delta))
        ts = datetime.now().strftime('%H:%M:%S')
        kaufbereitschaft_verlauf.append({'ts': ts, 'wert': kaufbereitschaft})
        return kaufbereitschaft


def reset_session():
    """Setzt den kompletten Live-State zurück (nach 'Gespräch beenden').
    Deprecated -- after per-SID migration this is a thin wrapper.
    Prefer pop_session_state(sid) + init_session_state(sid, ...) directly.
    Kept for backward compatibility with routes/ callers (Phase 08.19.5).
    Audit 08.19.5: 1 external caller found -- routes/app_routes.py line 480.
    Per-SID cleanup: iterates all active SIDs and calls pop+init as well as
    resetting module-level globals for backward compat with remaining callers."""
    global conversation_log, transcript_buffer, analysiert_bisher, painpoints
    global coaching_buffer, _line_id_counter, _log_last_sp
    global _confirmed_speaker, _pending_speaker, _pending_since, _second_sp_seen
    global _bof_count, roles_swapped
    global kaufbereitschaft, kaufbereitschaft_verlauf, aktive_phase_idx
    global gegenargument_log, hilfe_log, quick_action_log, phasen_log
    # Per-SID cleanup: reset all active SIDs via pop+init (Phase 08.19.5 migration)
    with _session_state_lock:
        active = list(_session_state.keys())
    for _rsid in active:
        _ss = _session_state.get(_rsid, {})
        _uid = _ss.get('user_id') or _ss.get('_user_id', 0)
        _oid = _ss.get('org_id', 0)
        _pid = _ss.get('active_profile_id')
        pop_session_state(_rsid)
        init_session_state(_rsid, user_id=_uid, org_id=_oid, profile_id=_pid)

    with log_lock:
        conversation_log.clear()
    with buffer_lock:
        transcript_buffer.clear()
        analysiert_bisher.clear()
    with coaching_lock:
        coaching_buffer.clear()
    with painpoints_lock:
        painpoints.clear()
    with state_lock:
        state['version']          = 0
        state['aktiv']            = False
        state['ergebnis']         = None
        state['kaufbereitschaft'] = 30
        # ── Phase 04.8 field resets (R3: missing resets cause stale hints) ──
        # Phase 08.23.2.TAXO1-03 (B-A Interlock): die per-SID-migrierten Anker werden
        # NICHT mehr hier im Modul-globalen state genullt — das waeren tote Geister-Writes
        # (Halbmigration → Doppel-Feuer-Schutz sporadisch wirkungslos). Der per-SID-Reset
        # laeuft ueber den pop+init-Loop oben (746-755): init_session_state['state'] seedet
        # line_id/kw_fired_for_line/current_phase/current_phase_name/phase_confidence/
        # cold_call_inference frisch (live_session.py:332/351/335/336/337/345).
        # GELOESCHT (B-A): line_id, kw_fired_for_line, current_phase, current_phase_name,
        #   phase_confidence, phase_changed_at, phase_change_count, cold_call_inference.
        # BLEIBEN (noch globaler Write-Pfad / nicht-§0.1-migriert): readiness_*,
        #   score_factors_seen, kaufbereitschaft (Task 3 Rider), active_hint, ewb_buttons,
        #   active_learning_cards, precall_briefing (HTTP-Pfad-Reader app_routes:111),
        #   slot1_variant_busy_until, mic_muted, active_profile_id.
        state['readiness_score']     = 30
        state['readiness_bucket']    = 'cold'
        state['score_factors_seen']  = {}
        state['active_hint']         = None
        state['ewb_buttons']         = None
        state['active_learning_cards'] = []
        state['precall_briefing'] = None
        state['slot1_variant_busy_until'] = 0.0
        state['mic_muted'] = False
        state['active_profile_id'] = None  # re-set by set_active_profile_with_id at session start
    with _line_id_lock:
        _line_id_counter = 0
    with _log_sp_lock:
        _log_last_sp = None
    with _speaker_lock:
        _confirmed_speaker = None
        _pending_speaker   = None
        _pending_since     = None
    with _sp2_lock:
        _second_sp_seen = False
    with _merge_lock:
        for v in _merge_pending.values():
            try:
                v['timer'].cancel()
            except Exception:
                pass
        _merge_pending.clear()
    with _bof_lock:
        _bof_count = 0
    with roles_lock:
        roles_swapped = False
    with kb_lock:
        kaufbereitschaft = 30
        kaufbereitschaft_verlauf.clear()
    with phase_lock:
        aktive_phase_idx = 0
    # Sprach-Zähler werden per-SID via pop_session_state+init_session_state oben
    # zurückgesetzt (Single-Source-of-State); keine Modul-Globalen mehr.
    with covered_phases_lock:
        covered_phases.clear()
    with gegenargument_log_lock:
        gegenargument_log.clear()
    with hilfe_log_lock:
        hilfe_log.clear()
    with quick_action_log_lock:
        quick_action_log.clear()
    with phasen_log_lock:
        phasen_log.clear()
    with state_lock:
        state['ewb_clicks'] = []
    with session_meta_lock:
        session_meta.update({
            'profil_name': '', 'profil_branche': '', 'schwierigkeit': None,
            'start_zeit': None, 'end_zeit': None,
            'gesamt_segmente': 0, 'gesamt_einwaende': 0,
            'einwaende_behandelt': 0, 'einwaende_fehlgeschlagen': 0,
            'einwaende_ignoriert': 0, 'vorwaende_erkannt': 0,
            'painpoints_gesamt': 0, 'kaufsignale_gesamt': 0,
            'coaching_tipps_gesamt': 0, 'hilfe_button_genutzt': 0,
            'quick_actions_genutzt': 0, 'skript_abdeckung_prozent': 0,
            'redeanteil_durchschnitt': 0, 'tempo_durchschnitt': 0, 'laengster_monolog': 0,
            'kb_start': 30, 'kb_end': 30, 'kb_min': 30, 'kb_max': 30,
            'sterne_bewertung': None, 'feedback_kommentar': '',
        })


def record_ewb_click(einwand_typ: str, success: bool = False,
                     antwort_text: str = None, einwand_text: str = None):
    """Erfasst einen EWB-Button-Klick im Session-State (thread-safe)."""
    import datetime as _dt
    entry = {
        'einwand_typ':  einwand_typ,
        'success':      bool(success),
        'ts':           _dt.datetime.utcnow().isoformat(),
        'antwort_text': antwort_text or None,
        'einwand_text': einwand_text or None,
    }
    with state_lock:
        state.setdefault('ewb_clicks', []).append(entry)


def get_speech_stats(sid: str = None) -> dict:
    """Gibt aktuelle Sprachstatistiken für die per-SID-Session zurück.

    Liest die Zähler aus _session_state[sid] (dort befüllt _flush_segment sie).
    Ohne gültige/bekannte sid → Null-Stats statt Crash (die früheren Modul-Globalen
    wurden entfernt — Single-Source-of-State, Konstrukt §0.1).
    """
    if not sid:
        return {'redeanteil': 0, 'tempo': 0, 'monolog': 0}
    with _session_state_lock:
        _ss = _session_state.get(sid)
        if not _ss:
            return {'redeanteil': 0, 'tempo': 0, 'monolog': 0}
        bw = _ss.get('berater_words', 0)
        kw = _ss.get('kunde_words', 0)
        st = _ss.get('session_start_time')
        monolog = round(_ss.get('laengster_monolog_sek', 0.0), 1)
    total = bw + kw
    redeanteil = round(bw / total * 100) if total > 0 else 0
    elapsed_min = (time.monotonic() - st) / 60 if st else 1
    tempo = round(bw / max(elapsed_min, 0.1))
    return {'redeanteil': redeanteil, 'tempo': tempo, 'monolog': monolog}


def _build_log_content(user_email='', profile_name='') -> str:
    with log_lock:
        entries = list(conversation_log)
    with roles_lock:
        swapped = roles_swapped

    sp_map = {0: ('Kunde' if swapped else 'Berater'),
              1: ('Berater' if swapped else 'Kunde')}

    lines = []
    lines.append("=" * 65)
    lines.append("  NERVE – Gesprächsprotokoll")
    lines.append(f"  Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    if user_email:
        lines.append(f"  User: {user_email}")
    if profile_name:
        lines.append(f"  Profil: {profile_name}")
    lines.append("=" * 65)
    lines.append("")

    n_segmente = n_einwaende = n_zurueckgezogen = 0
    einwand_typen = {}
    latenzen_einwand  = []
    latenzen_coaching = []
    laengste_latenz   = 0.0
    laengste_text     = ''

    for entry in entries:
        t = entry['type']
        if t == 'transcript':
            n_segmente += 1
            sp = sp_map.get(entry['speaker'], 'Unbekannt')
            lines.append(f"[{entry['ts']}] [{sp}]  {entry['text']}")
        elif t == 'analyse':
            d = entry.get('data') or {}
            if d.get('einwand'):
                n_einwaende += 1
                typ = d.get('typ', '?')
                einwand_typen[typ] = einwand_typen.get(typ, 0) + 1
                lines.append(f"[{entry['ts']}] [EINWAND – {typ} / {d.get('intensitaet','?')}]")
                lines.append(f"           Zitat:         \"{d.get('einwand_zitat','')}\"")
                lines.append(f"           Gegenargument: {d.get('gegenargument','')}")
            else:
                lines.append(f"[{entry['ts']}] [KEIN EINWAND]  {d.get('notiz','')}")
            if entry.get('latency') is not None:
                lat = entry['latency']
                latenzen_einwand.append(lat)
                lines.append(f"           [LATENZ] Einwand: {lat}s")
                if lat > laengste_latenz:
                    laengste_latenz = lat
                    laengste_text   = entry.get('text', '')[:60]
            lines.append("")
        elif t == 'latenz_coaching':
            lat = entry.get('latency', 0)
            latenzen_coaching.append(lat)
            lines.append(f"[{entry['ts']}] [LATENZ] Berater-Tipp: {lat}s")
            if lat > laengste_latenz:
                laengste_latenz = lat
                laengste_text   = '(Berater-Tipp)'
        elif t == 'korrektur':
            lines.append(f"[{entry['ts']}] [KORREKTUR] Rolle geändert: {entry.get('von','')} → {entry.get('nach','')}")
        elif t == 'zurueckgezogen':
            n_zurueckgezogen += 1
            lines.append(f"[{entry['ts']}] [ZURÜCKGEZOGEN] Einwand {entry.get('einwand_typ','')} zurückgezogen")
        elif t == 'painpoint':
            lines.append(f"[{entry['ts']}] [PAINPOINT]  {entry.get('text','')}")
        elif t == 'tipp':
            kat_str = KATEGORIE_LABEL.get(entry.get('kategorie', ''), 'Tipp')
            lines.append(f"[{entry['ts']}] [TIPP – {kat_str}]  {entry.get('text','')}")

    with painpoints_lock:
        pp_snapshot = list(painpoints)

    lines.append("")
    lines.append("=" * 65)
    lines.append("  ZUSAMMENFASSUNG")
    lines.append("=" * 65)
    lines.append(f"  Gesprächssegmente gesamt:    {n_segmente}")
    lines.append(f"  Erkannte Einwände:           {n_einwaende}")
    lines.append(f"  Zurückgezogene Einwände:     {n_zurueckgezogen}")
    lines.append(f"  Verbleibende Einwände:       {n_einwaende - n_zurueckgezogen}")
    lines.append(f"  Gesammelte Painpoints:       {len(pp_snapshot)}")
    if einwand_typen:
        haeufigster = max(einwand_typen, key=einwand_typen.get)
        lines.append(f"  Häufigster Einwand-Typ:      {haeufigster} ({einwand_typen[haeufigster]}×)")
        if len(einwand_typen) > 1:
            lines.append("  Alle Einwand-Typen:")
            for typ, count in sorted(einwand_typen.items(), key=lambda x: -x[1]):
                lines.append(f"    · {typ}: {count}×")
    if pp_snapshot:
        lines.append("  Alle Painpoints:")
        for pp in pp_snapshot:
            lines.append(f"    · [{pp['ts']}] {pp['text']}")
    if latenzen_einwand or latenzen_coaching:
        lines.append("")
        lines.append("  LATENZ-STATISTIKEN")
        lines.append("  " + "-" * 40)
        if latenzen_einwand:
            avg_e = round(sum(latenzen_einwand) / len(latenzen_einwand), 2)
            lines.append(f"  Ø Einwand-Analyse:            {avg_e}s  (n={len(latenzen_einwand)})")
        if latenzen_coaching:
            avg_c = round(sum(latenzen_coaching) / len(latenzen_coaching), 2)
            lines.append(f"  Ø Berater-Tipp:               {avg_c}s  (n={len(latenzen_coaching)})")
        if laengste_latenz > 0:
            snippet = f'"{laengste_text}"' if laengste_text != '(Berater-Tipp)' else laengste_text
            lines.append(f"  Längste Analyse:              {laengste_latenz}s  — {snippet}")

    # ── Gegenargument-Analyse ─────────────────────────────────────────────────
    with gegenargument_log_lock:
        ga_log = list(gegenargument_log)
    if ga_log:
        lines.append("")
        lines.append("  GEGENARGUMENT-ANALYSE")
        lines.append("  " + "-" * 40)
        lines.append(f"  {'Einwand-Typ':<22} {'Option':<8} {'KB Δ':<8} {'Erfolg'}")
        for ga in ga_log:
            opt   = str(ga.get('gewaehlte_option') or '-')
            delta = ga.get('kb_delta')
            delta_s = (f"+{delta}" if delta and delta > 0 else str(delta)) if delta is not None else '–'
            erfolg = '✓' if ga.get('erfolgreich') is True else ('✗' if ga.get('erfolgreich') is False else ('ignoriert' if ga.get('gewaehlte_option') is None else '–'))
            lines.append(f"  {ga.get('einwand_typ','?'):<22} {opt:<8} {delta_s:<8} {erfolg}")
        gesamt = len(ga_log)
        erfolge = sum(1 for g in ga_log if g.get('erfolgreich') is True)
        quote = round(erfolge / gesamt * 100) if gesamt else 0
        lines.append(f"  Erfolgsquote: {erfolge}/{gesamt} ({quote}%)")
        opt1 = sum(1 for g in ga_log if g.get('gewaehlte_option') == 1)
        opt2 = sum(1 for g in ga_log if g.get('gewaehlte_option') == 2)
        if opt1 + opt2 > 0:
            pref = '1' if opt1 >= opt2 else '2'
            pref_pct = round(max(opt1, opt2) / (opt1 + opt2) * 100)
            lines.append(f"  Bevorzugte Option: {pref} ({pref_pct}% der Wahlen)")
        typ_count = {}
        for g in ga_log:
            t = g.get('einwand_typ', '?')
            typ_count[t] = typ_count.get(t, 0) + 1
        if typ_count:
            haeufigster = max(typ_count, key=typ_count.get)
            lines.append(f"  Häufigster Einwand: {haeufigster} ({typ_count[haeufigster]}×)")

    # ── Hilfe-Button / Quick-Action Nutzung ───────────────────────────────────
    with hilfe_log_lock:
        hl = list(hilfe_log)
    with quick_action_log_lock:
        ql = list(quick_action_log)
    if hl or ql:
        lines.append("")
        lines.append("  HILFE-BUTTON / QUICK-ACTION NUTZUNG")
        lines.append("  " + "-" * 40)
        lines.append(f"  Hilfe-Button genutzt: {len(hl)}×  |  Quick-Actions: {len(ql)}×")
        all_actions = hl + ql
        if all_actions:
            typ_cnt = {}
            for a in all_actions:
                t = a.get('typ', '?')
                typ_cnt[t] = typ_cnt.get(t, 0) + 1
            haeufigster = max(typ_cnt, key=typ_cnt.get)
            lines.append(f"  Häufigster Typ: \"{haeufigster}\" ({typ_cnt[haeufigster]}×)")

    # ── Phasen-Verlauf ────────────────────────────────────────────────────────
    with phasen_log_lock:
        ph_log = list(phasen_log)
    if ph_log:
        lines.append("")
        lines.append("  PHASEN-VERLAUF")
        lines.append("  " + "-" * 40)
        for ph in ph_log:
            von  = ph.get('von_phase', '–') or 'Start'
            nach = ph.get('nach_phase', '–')
            segs = ph.get('segment_count', 0)
            lines.append(f"  {von} → {nach}  ({segs} Segmente bis Wechsel)")

    lines.append("=" * 65)
    return "\n".join(lines) + "\n"
