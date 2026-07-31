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
# DELETED: pause_lock (modul-global, 0 aktive Leser — S5); is_paused per-SID (Seed :354, Read :110)
# is_paused Modul-Global GELOESCHT (D-09/S5, 2026-07-03 Phase PERSID Plan 01)
# pause_lock hatte 0 Leser ausserhalb live_session.py selbst → ebenfalls entfernt

# ── Transkript-Buffer ─────────────────────────────────────────────────────────
# transcript_buffer/analysiert_bisher Modul-Globale GELOESCHT (Plan 04, Familie B):
# alle Schreiber sind per-SID (_per_sid_transcript / _session_state[sid]['analysiert_bisher']).
# Fallback-Zweig in _flush_segment ebenfalls entfernt (toter Post-Migration-Zweig, Plan 04).
buffer_lock       = threading.Lock()
analyse_trigger   = threading.Event()

# ── Coaching-Buffer ───────────────────────────────────────────────────────────
coaching_lock    = threading.Lock()
coaching_buffer  = []
coaching_trigger = threading.Event()
# painpoints_lock + painpoints GELOESCHT (PERSID Plan 05, Familie C per-SID):
# liegt unter _session_state[sid]['painpoints'] (seeded init_session_state:424).

# ── Gegenargument-Tracking ────────────────────────────────────────────────────
# gegenargument_log_lock + gegenargument_log GELOESCHT (PERSID Plan 05, Familie C):
# liegt unter _session_state[sid]['gegenargument_log'] (seeded init_session_state:421).

# ── Hilfe-Button Tracking (per-SID, Modul-Global entfernt) ───────────────────
# DELETED: hilfe_log + hilfe_log_lock (0 .append in Services — D-09, 2026-07-03 Phase PERSID)
# Readers app_routes.py:296 + _build_log_content:1190 → ersetzt durch 0/[] (D-09)
hilfe_log_lock = threading.Lock()  # Lock bleibt fuer reset_session Abwaertskompatibilitaet
hilfe_log      = []  # DEPRECATED-GLOBAL: hilfe_log — 0 .append()-Schreiber (RESEARCH §1), Loeschung Plan 03

# ── Quick-Action Tracking (per-SID, Modul-Global entfernt) ───────────────────
# DELETED: quick_action_log + quick_action_log_lock (0 .append — D-09, 2026-07-03 Phase PERSID)
# Readers app_routes.py:298 + _build_log_content:1192 → ersetzt durch 0/[] (D-09)
quick_action_log_lock = threading.Lock()  # Lock bleibt fuer reset_session Abwaertskompatibilitaet
quick_action_log      = []  # DEPRECATED-GLOBAL: quick_action_log — 0 .append()-Schreiber (RESEARCH §1), Loeschung Plan 03

# ── Phasenwechsel-Tracking ────────────────────────────────────────────────────
# phasen_log_lock + phasen_log GELOESCHT (PERSID Plan 05, Familie C):
# liegt unter _session_state[sid]['phasen_log'] (seeded init_session_state:420).

# ── Session-Metadaten ─────────────────────────────────────────────────────────
# DELETED: session_meta Modul-Global + session_meta_lock (0 externe Leser — D-09, 2026-07-03 Phase PERSID)
# Per-SID-Seed in init_session_state (sub-key 'session_meta') ebenfalls entfernt (RESEARCH §6.10).
# session_meta_lock bleibt als Stub fuer reset_session Abwaertskompatibilitaet bis Plan 03.
session_meta_lock = threading.Lock()
# session_meta GELOESCHT (D-09/RESEARCH §1) — reset_session-Block unten bleibt bis Plan 03 bereinigt

# ── Satz-Zusammenführung ──────────────────────────────────────────────────────
# _merge_lock GELOESCHT (S4: EIN Lock = _session_state_lock, Plan 04).
# _merge_pending Modul-Global GELOESCHT (Plan 04, Familie B):
# Puffer liegt jetzt unter _session_state[sid]['_merge_pending'] (seeded in init_session_state).

# ── Zeilen-ID Counter (per-SID; Modul-Globale entfernt) ──────────────────────
# DELETED: _line_id_counter (Modul-Global, schon per-SID :426 — S5, 2026-07-03 Phase PERSID)
# DELETED: _line_id_lock (0 Leser nach S5-Cleanup; next_line_id nutzt _session_state_lock)

def next_line_id(sid: str) -> str:
    """Returns next sequential line ID for the given SID. Ghost-SID-safe."""
    with _session_state_lock:
        if sid not in _session_state:
            return '0'  # Ghost-SID guard
        cnt = _session_state[sid].get('_line_id_counter', 0) + 1
        _session_state[sid]['_line_id_counter'] = cnt
        return str(cnt)


def get_sid_paused(sid: str) -> bool:
    """Liest is_paused fuer EINE sid. BEWUSST RIEGEL-FREI. False fuer unbekannte sids.

    WARUM OHNE DEN GLOBALEN SITZUNGS-RIEGEL (Phase 08.23.2.LOCK-1 Teil 1, Wurzel 1):
    Diese Funktion lief bei JEDEM Ton-Brocken, also 10x/Sekunde pro Anruf
    (services/deepgram_service.py:864, 100ms-Frames) — und nahm dabei denselben GLOBALEN
    `_session_state_lock` wie Analyse, Coaching, Umschalter, Knopfdruck und Auflegen.
    Beleg am laufenden Prozess, nicht erschlossen: py-spy-Abzug 30.07. (PID 2335884,
    sid 5Y-0MFlm_ITb1cupAAAB) — 1415 von 1416 blockierten Rahmen standen genau hier,
    davon 1414 aus handle_audio_chunk. Klemmte der Riegel einmal, starb die ganze
    Sitzung: keine Coaching-Zeile, kein Transkript, keine Kostenzeile — und stumm.

    WARUM DAS SICHER IST: der Zugriff ist durchgaengig mit .get()-Defaults geschrieben und
    liefert EINEN bool. Die drei nebenlaeufigen Schreiber (init_session_state setzt
    _session_state[sid] als Ganzes, pop_session_state entfernt es als Ganzes, der
    Pause-Pfad setzt einen bool) sind einzelne dict-Operationen und unter dem GIL atomar —
    ein halb geschriebenes dict ist in CPython nicht sichtbar. Jede Zwischenstufe faellt
    auf einen Default zurueck: sid weg -> {} -> {} -> False. Riegel-freies Lesen kann
    also hoechstens einen um Millisekunden veralteten Ja/Nein-Wert liefern (harmlos — der
    naechste Ton-Brocken kommt in 100ms), NIEMALS einen Fehler und NIEMALS kaputte Daten.

    Das ist kein Praezedenzbruch: riegel-freie _session_state-Reads sind Bestand, z.B.
    services/deepgram_service.py:961 (mode) und :1061 (analysiert_bisher).

    ABGRENZUNG: das macht den on_message-Weg NICHT riegel-frei. Dort liegen 13 weitere
    Riegel-Nahmen, u.a. services/deepgram_service.py:94 bei JEDER finalisierten Zeile —
    deshalb gibt es zusaetzlich das finish()-Zeitlimit (Teil 2). Zwei getrennte Defekte.

    NICHT WIEDER EINEN RIEGEL EINBAUEN. Wer hier einen braucht, hat die Funktion
    erweitert — dann gehoert die Erweiterung woanders hin, nicht der Riegel hierher.
    Bewacht von tests/test_audio_path_lock_free_guard.py (Verhaltens-Test: der haelt den
    Riegel und diese Funktion muss trotzdem den KORREKTEN Wert liefern).
    """
    return _session_state.get(sid, {}).get('state', {}).get('is_paused', False)


# ── Phase 08.23.2.LOCK-1 Teil 2b: begrenzte Riegel-Probe fuer genau zwei Eingaenge ──────
# Unveraenderliche Konstante (Punkt 28: kein veraenderlicher Modul-Zustand).
# Der Text der LOCKWATCH-Log-Zeilen ist auf ">2s" festgelegt (CONTEXT) — wer diesen Wert
# aendert, aendert auch die zwei Log-Zeilen in deepgram_service.py und app_routes.py.
_LOCK_PROBE_TIMEOUT_S = 2.0


def wait_session_state_lock_free(timeout: float = _LOCK_PROBE_TIMEOUT_S) -> bool:
    """Probiert, den Sitzungs-Riegel innerhalb `timeout` Sekunden zu bekommen, und gibt ihn
    SOFORT wieder frei. True = der Riegel war (oder wurde) frei. False = er klemmt.

    ZWECK: der Knopfdruck (handle_manual_ewb) und das Auflegen (api_beenden) duerfen NICHT
    ewig warten, sondern muessen MIT FEHLER zurueckkehren. Am 30.07. hingen vier Klicks
    (09:28:07 / 09:29:11 / 09:29:55 / 09:30:07) und ein [Beenden] (09:30:18) stumm — kein
    Fehler, keine Anzeige, kein 504 (die Anfrage endete nicht, sie brach nur im Browser ab;
    gunicorn --timeout 120 greift bei blockierten Arbeits-Faeden nicht, weil der Herzschlag
    vom Haupt-Faden kommt).

    BEWUSST EINE PROBE AM EINGANG, KEIN begrenzter Erwerb an sieben Stellen (Punkt 27 +
    Punkt 17): der Fehlerfall ist ein MINUTENLANG klemmender Riegel, keine Mikrosekunden-
    Konkurrenz. Dafuer genuegt eine Probe — und KEINER der bestehenden Riegel-Bloecke muss
    dafuer angefasst werden. Die theoretische Luecke (der Riegel wird ZWISCHEN Probe und Nutzung
    genommen) ist bewusst offen: dann wartet der Aufrufer wie bisher, aber der Wachhund
    (Teil 3) sagt es, und das Auflegen ist durch das finish()-Zeitlimit (Teil 2)
    unabhaengig gedeckelt. Die Abwaegung steht in .planning/DIALOG-GSD-CLAUDIAN.md.

    KEIN Zustand, KEIN Log hier — der Aufrufer loggt mit seinem eigenen Kontext (sid bzw.
    user_id). LATENZ (Punkt 25): ein unkonkurriertes acquire+release kostet ~0.1 us und
    laeuft pro Knopfdruck bzw. pro Anruf-Ende, nicht im 10-Hz-Takt.
    """
    got = _session_state_lock.acquire(timeout=timeout)
    if got:
        _session_state_lock.release()
    return got


# ── Analyse-State ─────────────────────────────────────────────────────────────
# D-09 Phase PERSID Plan 01 — Zombie-State-Keys entfernt (0 Prod-Reader, RESEARCH §1):
#   DELETED: 'version', 'aktiv', 'ergebnis' (Auslieferung via sio.emit(room=sid), nie gelesen)
#   DELETED: 'line_id' (schon per-SID, claude_service.py:1141 Kommentar)
#   DELETED: 'active_hint', 'ewb_buttons' (Writers cs:1360-1361 ebenfalls entfernt)
#   DELETED: 'slot1_variant_busy_until' (PIP-01 entfernt, 0 Reader)
# Verbliebene Keys haben aktive Schreiber/Leser in laufenden Migrationswellen.
# precall_briefing: DEPRECATED-GLOBAL — Reader-Umbau in Plan 03 (Welle A); bis dahin PENDING.
state_lock = threading.Lock()
state = {
    'kaufbereitschaft': 30,
    # PERSID Plan 06 Familie D: ewb_clicks + suggestion_offers per-SID migriert — Modul-Global-Keys ENTFERNT.
    # Schreiber: record_ewb_click(sid,...) / record_suggestion_offer(sid,...) schreiben NUR noch per-SID.
    # Reader: app_routes api_beenden liest via _bs.get('state',{}).get('ewb_clicks',[]). (D-10)
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
    # ── Phase 04.8: Cold-Call Inference ──
    'cold_call_inference':  None,
    # ── Phase 04.11: Active Learning Cards (D-09) ──
    'active_learning_cards': [],
    # PERSID Plan 03 W-A: precall_briefing Modul-Key ENTFERNT.
    # Reader app_routes:112 liest jetzt per-SID via _bs.get('_briefing') (N-3).
    # PERSID Plan 03 W-A: mic_muted Modul-Key ENTFERNT.
    # Liegt jetzt top-level per-SID: _session_state[sid]['mic_muted'].
    # ── Phase 08.5: QA-Pipeline state ──
    'active_profile_id': None,        # set in set_active_profile_with_id() at session start
    'kw_fired_for_line': None,        # D-02: line_id of last keyword-matcher hit; qa_pipeline skips when equal to line_id
}

# ── Conversation Log ──────────────────────────────────────────────────────────
# log_lock + conversation_log GELOESCHT (PERSID Plan 05, Familie C):
# liegt unter _session_state[sid]['conversation_log'] (seeded init_session_state:331).
# ALLE 6 Writer (deepgram:2, claude:4) schreiben per-SID unter _session_state_lock.

# ── Rollen-Tausch ─────────────────────────────────────────────────────────────
# DELETED: roles_swapped (Modul-Global, 0 `= True` Schreiber — D-09, 2026-07-03 Phase PERSID)
# _build_log_content liest per-SID state; per-SID-Seed :318 bleibt fuer spaetere Nutzung.
# roles_lock bleibt fuer reset_session Abwaertskompatibilitaet.
roles_lock    = threading.Lock()
roles_swapped = False  # DEPRECATED-GLOBAL: roles_swapped — 0 `= True` Schreiber (RESEARCH §1), Loeschung Plan 03

# ── Sprecher-Fallback für Log (PERSID Plan 06 Familie E: per-SID) ───────────
# _log_last_sp GELOESCHT (Modul-Global DELETE, 2026-07-04): Lag unter _session_state[sid]['_log_last_sp'].
# _log_sp_lock GELOESCHT: kein Modul-Global mehr; Lock unnoetig.
# Seed in init_session_state :339 ('_log_last_sp': None) bleibt.

# ── Zweiter Sprecher gesehen? (PERSID Plan 06 Familie E: per-SID) ────────────
# _second_sp_seen GELOESCHT (Modul-Global DELETE, 2026-07-04): liegt unter _session_state[sid]['_second_sp_seen'].
# _sp2_lock GELOESCHT: kein Modul-Global mehr; Lock unnoetig.
# Seed in init_session_state :426 ('_second_sp_seen': False) bleibt.

# ── Sprecher-Stabilisierung ───────────────────────────────────────────────────
_speaker_lock      = threading.Lock()
_confirmed_speaker = None
_pending_speaker   = None
_pending_since     = None

# ── Berater-ohne-Frage-Zähler ─────────────────────────────────────────────────
# DELETED: _bof_count Modul-Global (D-09, Task-1-Verdikt DELETE, 2026-07-03 Phase PERSID)
# per-SID-Pfad claude_service.py:1711-1714 + per-SID-Seed live_session.py:321 BLEIBEN.
_bof_lock  = threading.Lock()  # Lock bleibt fuer potenzielle Abwaertskompatibilitaet

# ── Kaufbereitschaft ──────────────────────────────────────────────────────────
# kb_lock + kaufbereitschaft + kaufbereitschaft_verlauf GELOESCHT (PERSID Plan 05, Familie C):
# liegt unter _session_state[sid]['kaufbereitschaft'] + ['kaufbereitschaft_verlauf'].
# update_kaufbereitschaft(sid, delta) schreibt atomar unter _session_state_lock (S4).

# ── Aktive Gesprächsphase ─────────────────────────────────────────────────────
# phase_lock + aktive_phase_idx GELOESCHT (PERSID Plan 05, B5):
# BEIDE Reader (app_routes:244 + claude:206) jetzt per-SID unter _session_state_lock.
# liegt unter _session_state[sid]['aktive_phase_idx'] (seeded init_session_state:428).

# ── Sprachstatistik ───────────────────────────────────────────────────────────
# Single-Source-of-State (Konstrukt §0.1): Sprach-Zähler sind AUSSCHLIESSLICH per-SID
# (_session_state[sid]: berater_words / kunde_words / session_start_time /
# laengster_monolog_sek / _current_monolog_start). _flush_segment schreibt nur dorthin,
# get_speech_stats(sid) liest nur dorthin (unter _session_state_lock). Die früheren
# Modul-Globalen + speech_lock wurden NIE befüllt (toter Ghost-Read → immer 0) und sind
# komplett entfernt.

# ── Abgedeckte Phasen ─────────────────────────────────────────────────────────
# covered_phases_lock + covered_phases GELOESCHT (PERSID Plan 05, Familie C):
# liegt unter _session_state[sid]['covered_phases'] (seeded init_session_state:335).

# set_active_profile / get_active_profile deleted Phase 08.19.4 D-04/D-05 — use set_profile_for_sid / get_profile_for_sid


# ── Per-SID State Infrastructure (Phase 08.19.4 — DSGVO) ─────────────────────
# Replaces single-global pattern. One entry per WebSocket SID.
# Pattern copied from deepgram_service._deepgram_sessions (same lifecycle).
# Lock granularity: acquire lock for snapshot only, release before long ops.

# ── Per-SID Profil-Cache (D-01) — analog _deepgram_sessions Pattern ──────────
_per_sid_profile: dict = {}     # {sid: (name, daten)}

# ── B1: _ended_session_snapshots — Beenden-Naht-Stash (PERSID Plan 03) ───────
# Wenn stop_live_session (:779) ODER handle_disconnect (:815) den per-SID-State
# aufraeumt, wird ZUERST eine flache Kopie gestasht (TTL=300s).
# api_beenden liest via consume_ended_session (NICHT-destruktiver PEEK, N-3).
# :674 (reconnect re-init) ist B1-EXEMPT: init_session_state folgt sofort.
# Whitelist-Eintrag (Punkt 28): sid-gekeyt -> per-sid-safe.
_ended_session_snapshots: dict = {}   # {sid: {'state': <kopie>, 'ts': monotonic()}}
_ended_snapshots_lock = threading.Lock()
_SNAPSHOT_TTL_S: float = 300.0       # 5 Minuten TTL
_per_sid_lock = threading.Lock()

# ── Phase 08.23.2.LOCK-1 Teil 3: Aufsatz-Riegel mit Halter-Aufzeichnung ──────────────
class _TracedLock:
    """Duenner Aufsatz auf threading.Lock, der den HALTER aufzeichnet.

    WARUM: CPython gibt aus einem threading.Lock KEINE Halter-Information heraus. Der
    py-spy-Abzug vom 30.07. (PID 2335884) zeigte 1416 wartende Faeden und KEINEN Halter mit
    sichtbarem Python-Rahmen — 'wer haelt den Riegel' ist ohne Aufzeichnung BEIM ERWERB
    schlicht nicht beantwortbar. faulthandler zeigt exakt dieselbe Sicht und kann es
    deshalb AUCH NICHT; er ersetzt nur das Werkzeug py-spy, nicht die Antwort.

    PUNKT 17 (kein Refactor nebenbei): diese Klasse ersetzt GENAU EINE Zeile — die
    Erzeugung von _session_state_lock. Keine der 97 'with ... _session_state_lock:'-
    Stellen in acht Dateien wird angefasst; sie brauchen nur das Kontext-Manager-Protokoll.
    Alle ANDEREN Riegel des Moduls (_per_sid_lock, _ended_snapshots_lock,
    _per_sid_transcript_lock, _per_sid_coaching_lock, state_lock) bleiben bewusst
    gewoehnliche threading.Lock — nur der eine, der am 30.07. geklemmt hat, bekommt den Aufsatz.

    KEIN RLock. Wieder-Eintritt desselben Fadens muss weiterhin verklemmen: close_moment /
    get_or_open_moment sind ausdruecklich darauf gebaut ('LOCK-FREE, der AUFRUFER haelt',
    weiter unten in dieser Datei). Ein RLock wuerde diesen Design-Zwang lautlos aufloesen.

    PUNKT 28 (kein modul-globaler veraenderlicher Zustand fuer pro-Nutzer-Daten): die
    Halter-Felder sind veraenderlich und prozessweit — aber sie beschreiben DEN RIEGEL,
    nicht einen Nutzer, eine Sitzung oder einen Anruf. Sie enthalten KEINE sid, KEINE
    user_id, KEINE org_id; ein Cross-Tenant-Vermischungs-Risiko existiert nicht. Sie liegen
    ausserdem INNERHALB dieses Moduls, waehrend der Global-Waechter
    (tests/test_no_live_global_state.py) Zuweisungen der Form `ls.<attr> = ...` aus
    FREMDmodulen prueft. Kein Whitelist-Eintrag noetig — diese Begruendung IST der Eintrag.

    LATENZ (Punkt 25): ein Python-__enter__/__exit__-Paar kostet grob 1-2 us pro Erwerb
    statt ~0.1 us beim C-Riegel. Nach Teil 1 nimmt der 10-Hz-Ton-Weg diesen Riegel GAR
    NICHT mehr; die verbleibenden Erwerbe (mehrere pro finalisierter Zeile, ~1/s pro Anruf,
    plus Analyse-/Coaching-Schleife alle 2-4s) liegen bei grob 1.8 ms PRO MINUTE und Anruf.
    Budget: < 5 ms/min/Anruf.
    """

    __slots__ = ('_lock', '_name', 'holder_thread', 'holder_ident',
                 'holder_since')

    def __init__(self, name: str):
        self._lock = threading.Lock()
        self._name = name
        self.holder_thread = None        # str  — Faden-Name des aktuellen Halters
        self.holder_ident = None         # int  — Faden-Kennung (fuer den faulthandler-Abzug)
        self.holder_since = None         # float monotonic — Halte-DAUER; die Uebernahme-
                                         # UHRZEIT wird daraus erst beim Loggen abgeleitet

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        got = self._lock.acquire(blocking, timeout)
        if got:
            _t = threading.current_thread()
            self.holder_thread = _t.name
            self.holder_ident = _t.ident
            self.holder_since = time.monotonic()   # EIN C-Aufruf, kein zweiter fuer die Uhrzeit
        return got

    def release(self) -> None:
        # REIHENFOLGE IST LOAD-BEARING: erst die Felder loeschen, DANN freigeben.
        # Umgekehrt koennte ein wartender Faden den Riegel sofort uebernehmen und seine
        # Felder setzen — und unser nachgelagertes Loeschen wuerde den NEUEN Halter
        # wegwischen. Der Wachhund meldete dann 'Halter unbekannt', obwohl er bekannt ist.
        self.holder_thread = None
        self.holder_ident = None
        self.holder_since = None
        self._lock.release()

    def locked(self) -> bool:
        return self._lock.locked()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

    def __repr__(self):
        return f"<_TracedLock {self._name} holder={self.holder_thread!r}>"


# ── Per-SID Session-State (D-02) ─────────────────────────────────────────────
_session_state: dict = {}       # {sid: {key: value, ...}}
_session_state_lock = _TracedLock('_session_state_lock')

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


def get_counterpart(sid: str) -> str:
    """Gespraechspartner (Achse B) fuer sid: 'gatekeeper' | 'decision_maker'.

    Reiner Lese-Zugriff, nimmt _session_state_lock selbst — NICHT aus einem bereits
    gehaltenen Lock heraus aufrufen (threading.Lock ist nicht reentrant).
    Fail-open Default 'gatekeeper' bei Ghost-SID (nie raise, Live-Pfad).
    """
    with _session_state_lock:
        return ((_session_state.get(sid) or {}).get('state') or {}).get('counterpart') or 'gatekeeper'


def init_session_state(sid: str, user_id: int, org_id: int, profile_id=None,
                       market: str = 'dach', language: str = 'de',
                       mode: str = 'cold_call') -> None:
    """Initialize _session_state[sid] for a new WebSocket connection (D-02)."""
    # Phase 08.23.2.COUNTERPART — der Init-Default haengt an der ANRUF-ART:
    # zu einem Termin sitzt man per Definition beim Entscheider, bei Kaltakquise
    # zuerst im Vorzimmer. Ohne diese Kopplung liefe JEDER Meeting-Anruf bis zum
    # ersten manuellen Toggle still im 4-Phasen-Sekretaersmodell statt im
    # 6-Phasen-Meeting-Modell (Cross-AI-Fund 2026-07-28, Meeting-Regression).
    # Umschalten bleibt jederzeit moeglich — das hier ist nur der Startwert.
    _counterpart_default = 'decision_maker' if mode == 'meeting' else 'gatekeeper'
    with _session_state_lock:
        _session_state[sid] = {
            'user_id': user_id,
            'org_id': org_id,
            'active_profile_id': profile_id,
            'kaufbereitschaft': 30,
            'active_sid': sid,
            'market': market,
            'language': language,
            # ── ACHSE A (call_type) ────────────────────────────────────────────
            # 'cold_call' | 'meeting' = die ANRUF-ART. Aendert sich waehrend eines
            # Anrufs NIE. Der Speicher-Schluessel heisst historisch 'mode', weil
            # MODE_REGISTRY/mode_strategy darauf sitzen — das ist Absicht, kein
            # Restposten. Es gibt bewusst KEINEN Lese-Helfer dafuer (9 Direktleser
            # im Bestand; ein Helfer mit 1 Aufrufer wuerde nur den Namen luegen).
            # NIE mit dem Gespraechspartner verwechseln: der liegt getrennt in
            # state['counterpart'] ('gatekeeper' | 'decision_maker').
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
                # D-09 PERSID Plan 01: 'version'/'aktiv'/'ergebnis' Zombie-Keys aus
                # per-SID state entfernt (Auslieferung via sio.emit(room=sid)).
                # 'active_hint'/'ewb_buttons' ebenfalls (0 Prod-Reader).
                # 'slot1_variant_busy_until' PIP-01 entfernt (0 Reader).
                'line_id':               None,  # per-SID line tracking (claude_service:1146)
                'kaufbereitschaft':      30,
                'ewb_clicks':            [],  # PERSID Plan 06 Familie D per-SID (B4)
                'suggestion_offers':     [],  # PERSID Plan 06 Familie D per-SID (B4, TAXO2-08)
                'current_phase':         1,
                'current_phase_name':    'Opener',
                'phase_confidence':      0.0,
                'phase_changed_at':      None,
                'phase_change_count':    0,
                'readiness_score':       30,
                'readiness_bucket':      'cold',
                'score_factors_seen':    {},
                'cold_call_inference':   None,
                'active_learning_cards': [],
                'precall_briefing':      None,
                # W-1 PERSID Plan 03: 'mic_muted' aus 'state'-Subdict ENTFERNT.
                # Liegt jetzt top-level: _session_state[sid]['mic_muted'] = False (unten).
                'active_profile_id':     profile_id,
                'kw_fired_for_line':     None,
                'is_paused':             False,   # REQ-01
                'ft_session_id':         None,
                # W-1 PERSID Plan 03: 'session_anrede' aus 'state'-Subdict ENTFERNT.
                # Liegt top-level lazy: _session_state[sid]['session_anrede'] (kein Seed,
                # LAZY erzeugt durch per-SID Start-Write NACH init N-4 oder Toggle :827).
                # Phase 08.23.2.COUNTERPART — Gespraechspartner (Achse B), EIN Ort.
                # Werte: 'gatekeeper' | 'decision_maker'. NIE 'cold_call'/'meeting' —
                # das ist die Anruf-Art (call_type, top-level _session_state[sid]['mode']).
                # Geschrieben NUR hier (Init) und in handle_toggle_counterpart
                # (deepgram_service.py) — Ein-Schreiber-Sperre, Waechter 3.
                'counterpart':           _counterpart_default,
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
            # D-09 PERSID Plan 01: per-SID 'session_meta' Sub-Key geloescht (RESEARCH §6.10).
            # Modul-Global session_meta ebenfalls geloescht (0 externe Leser). Plan 03 bringt
            # echte per-SID Session-Metriken.
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
            # PERSID Plan 03 W-1: mic_muted top-level (kanonische Ebene fuer Writer+Reader).
            # Vorher im 'state'-Subdict (:364, jetzt entfernt). Seed False (Default stumm=False).
            'mic_muted':             False,
            # PERSID Plan 04 Familie B: _merge_pending pro-SID (S4: EIN Lock = _session_state_lock).
            # Keyed nach Sprecher-String innerhalb des sid-Buckets (z.B. '0', '1', 'unknown').
            '_merge_pending':        {},
        }
    # WR-03: init per-SID coaching buffer (separate lock — same lifecycle as transcript)
    with _per_sid_coaching_lock:
        _per_sid_coaching_buffer[sid] = []


def pop_session_state(sid: str) -> None:
    """Remove all per-SID state on disconnect. Briefing is stored as _session_state[sid]['_briefing']
    and is auto-cleaned when the dict entry is popped — no separate briefing cleanup needed (HIGH-2 fix).

    PERSID Plan 04 (Punkt 14 / S4): offene _merge_pending-Timer der sid werden VOR dem Pop
    gecancelt (kein Feuern in weggeraeumte sid). Cancel AUSSERHALB des Locks (kein langer Op unter Lock):
    Snapshot der Timer-Dicts unter Lock nehmen, Lock freigeben, dann .cancel() ausfuehren.
    """
    # Timer-Cancel: Snapshot unter Lock, cancel ausserhalb (D-03 Lock-Disziplin)
    _timers_to_cancel = []
    # Teil 2c (B1-Folge): begrenzter Erwerb — pop_session_state ist der direkte Schwanz von
    # stash_ended_session (Aufruf am Ende dort). Bliebe es hier unbegrenzt, waere der
    # Haenger nur eine Zeile weiter gewandert.
    if _session_state_lock.acquire(timeout=_LOCK_PROBE_TIMEOUT_S):
        try:
            _mp = _session_state.get(sid, {}).get('_merge_pending', {})
            for _entry in _mp.values():
                _t = _entry.get('timer')
                if _t is not None:
                    _timers_to_cancel.append(_t)
        finally:
            _session_state_lock.release()
    else:
        print(f"[LOCKWATCH] pop_session_state: Riegel >2s belegt (sid={sid}) — offene "
              f"_merge_pending-Timer bleiben ungecancelt. Der Ghost-SID-Guard verwirft "
              f"sie beim Feuern; wir laufen weiter, statt zu warten.")
    for _t in _timers_to_cancel:
        try:
            _t.cancel()
        except Exception:
            pass

    if _session_state_lock.acquire(timeout=_LOCK_PROBE_TIMEOUT_S):
        try:
            _session_state.pop(sid, None)   # clears ['_briefing'] + ['_merge_pending'] sub-keys automatically
        finally:
            _session_state_lock.release()
    else:
        print(f"[LOCKWATCH] pop_session_state: Riegel >2s belegt (sid={sid}) — der "
              f"per-sid-Zustand bleibt im Speicher liegen und wird beim naechsten "
              f"Aufraeumen mitgenommen. Wir laufen weiter, statt zu warten.")
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


# ── B1: Beenden-Naht-Stash-Helfer (PERSID Plan 03) ────────────────────────────

def stash_ended_session(sid: str) -> None:
    """Stasht eine flache Kopie des per-SID-State in _ended_session_snapshots, dann pop.

    Wird an BEIDEN Beenden-Naehten aufgerufen:
      - stop_live_session (~:779, normaler Hangup)  — Haupt-Pfad
      - handle_disconnect (~:815, Netz-Blip/Tab-Zu) — Edge-Case

    N-1 Schutzmassnahmen (gegen setdefault :810-811 in handle_disconnect):
      1. Leer-/Fehlend-Skip: leeres oder fehlendes _session_state[sid] wird NICHT gestasht.
      2. first-stash-wins: ist bereits ein TTL-frischer Snapshot vorhanden, NICHT
         ueberschreiben. Der volle :779-Snapshot gewinnt gegen einen spaeteren leeren
         :815-Stash-Versuch.
    """
    # ── Phase 08.23.2.LOCK-1 Teil 2c: begrenzter Erwerb statt unbegrenztem Warten ──────
    # Cross-AI-Fund B1: das finish()-Zeitlimit (Teil 2) deckelt NUR das Schliessen der
    # Deepgram-Verbindung. Direkt danach ruft BEIDE Auflege-Naehte diese Funktion
    # (handle_stop_live_session und handle_disconnect) — ein unbegrenztes Warten hier
    # haette den Haenger nur um eine Zeile verschoben.
    # Klemmt der Riegel, ist der Schnappschuss ohnehin nicht zu bekommen. Dann ist
    # Ueberspringen die richtige Antwort, nicht Warten. NICHT still: die Log-Zeile sagt
    # ausdruecklich, dass der Schnappschuss VERWORFEN wurde — ein stummer Skip waere
    # genau das stumme Sterben, gegen das diese Phase gebaut ist.
    # Die drei Zusagen bleiben unveraendert: Leer-/Fehlend-Skip, first-stash-wins, und
    # die Kopie wird weiterhin UNTER dem Riegel genommen (D-03).
    if not _session_state_lock.acquire(timeout=_LOCK_PROBE_TIMEOUT_S):
        print(f"[LOCKWATCH] stash_ended_session: Riegel >2s belegt (sid={sid}) — der "
              f"Schnappschuss dieses Anrufs wird VERWORFEN, damit das Auflegen "
              f"zurueckkehrt. Stapel-Abzug: sudo systemctl kill -s SIGUSR1 nerve")
        return
    try:
        # N-1 Pruefung 1: leeres oder fehlendes Dict NICHT stashen
        state_copy = _session_state.get(sid)
        if not state_copy:
            # Leer-/Fehlend-Skip — kein Stash (verhindert Ueberschreiben mit leerem Dict)
            return
        # Flache Kopie unter Riegel nehmen (D-03: Snapshot unter Lock, dann Lock freigeben)
        state_copy = dict(state_copy)
    finally:
        _session_state_lock.release()

    # Lazy TTL-Sweep: alte Snapshots entfernen
    _now = time.monotonic()
    with _ended_snapshots_lock:
        # N-1 Pruefung 2: first-stash-wins (kein Ueberschreiben eines TTL-frischen Snapshots)
        existing = _ended_session_snapshots.get(sid)
        if existing is not None and (_now - existing['ts']) <= _SNAPSHOT_TTL_S:
            # Frischer Snapshot bereits vorhanden — NICHT ueberschreiben
            # pop_session_state trotzdem aufrufen (State aufraumen)
            pass
        else:
            # Lazy TTL-Sweep fuer alle alten Eintraege
            _expired = [s for s, v in _ended_session_snapshots.items()
                        if _now - v['ts'] > _SNAPSHOT_TTL_S]
            for _s in _expired:
                _ended_session_snapshots.pop(_s, None)
            # Snapshot stashen
            _ended_session_snapshots[sid] = {'state': state_copy, 'ts': _now}

    # State aufraumen (NACH Snapshot-Stash)
    pop_session_state(sid)


def consume_ended_session(sid: str) -> 'dict | None':
    """N-3 NICHT-destruktiver PEEK: gibt den gestashten State zurueck OHNE zu loeschen.

    Mehrfaches Lesen liefert denselben Inhalt (Doppel-Beenden bleibt gutartig).
    TTL-Check: abgelaufene Snapshots gelten als nicht vorhanden.
    Aufraeumen: via pop_ended_session (Plan 06 Task 2c in reset_session).
    """
    _now = time.monotonic()
    with _ended_snapshots_lock:
        entry = _ended_session_snapshots.get(sid)
        if entry is None:
            return None
        if _now - entry['ts'] > _SNAPSHOT_TTL_S:
            # Abgelaufen
            _ended_session_snapshots.pop(sid, None)
            return None
        return entry['state']


def pop_ended_session(sid: str) -> None:
    """Expliziter Snapshot-Pop (Plan 06 Task 2c: reset_session ruft ihn auf).

    Entfernt den Snapshot final. Wird NACH dem Persistieren des Call-Records
    aufgerufen (in reset_session(_beenden_sid)), nicht vorher.
    """
    with _ended_snapshots_lock:
        _ended_session_snapshots.pop(sid, None)


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


def _durable_call_id(raw):
    """Reiner Sentinel-/None-Guard (KEIN Lock): durable UUID-str bleibt, None/'__call_pending__' -> None.

    NIEMALS den Sentinel-String '__call_pending__' zurueckgeben (CI-1) — er wuerde sonst in eine
    UUID-Spalte (intent_event.call_id) geschrieben. Single-Source der 'nie Sentinel'-Regel:
    genutzt von BEIDEN — dem gesperrten Getter resolve_call_id_for_sid UND den 4 Live-emit-Aufrufern,
    die call_id direkt aus dem schon-gehaltenen state lesen (kein 4x dupliziertes Guard).
    """
    return raw if (raw and raw != '__call_pending__') else None


def resolve_call_id_for_sid(sid):
    """Locking-Getter NUR fuer Kontexte OHNE gehaltene _session_state_lock-Sperre (Backfill/unlocked).

    Die 4 Live-emit-Aufrufer (claude_service:1065/:1599, deepgram_service:877, einwand_keyword_matcher:315)
    rufen DIESEN Getter NICHT — sie halten _session_state_lock bereits, ein Re-Lock auf den plain Lock
    waere ein Deadlock. Sie lesen state['call_id'] direkt und wenden _durable_call_id an.
    Race-Schliessung (call_id durable VOR Detection) ist Plan 02.
    """
    with _session_state_lock:
        cid = _session_state.get(sid, {}).get('state', {}).get('call_id')
    return _durable_call_id(cid)


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
    # und beide einen Call-Record in DB schreiben (Doppel-Records + Doppel-counterpart_initial).
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
        # TENANT-FOUND Plan 01 Task 2: Tenant aus user_id aufloesen (Deepgram-Callback-Thread,
        # KEIN Request-Kontext, kein g.tenant_id). calls hat KEINE RLS (RESEARCH §3) -> dieser
        # INSERT braucht KEINEN set_current_tenant/GUC, nur den aufgeloesten Wert. Latenz (Punkt 25):
        # 1x indizierter Join bei Call-Anlage, NICHT im Live-Antwort-Pfad. None bei Edge -> tenant_id
        # NULL geschrieben, Call-Anlage bricht NICHT (Live-Schutz, fail-soft).
        from database.db import resolve_tenant_uuid_for_user
        _tid = resolve_tenant_uuid_for_user(user_id, _db)
        call = Call(
            user_id=user_id,
            tenant_id=_tid,
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
        # D-04b: counterpart_initial-Event — liest call_type + counterpart aus State (nach call_id-Write)
        with _session_state_lock:
            _mi_sd = _session_state.get(sid) or {}
            _mode_init_state = _mi_sd.get('state') or {}
            _counterpart_init = _mode_init_state.get('counterpart', 'gatekeeper')
            _call_type_init = _mi_sd.get('mode', 'cold_call')
        _db_mi = None
        try:
            from database.db import SessionLocal as _SL_mi
            from database.models import CallEvent as _CE_mi
            import time as _t_mi
            _db_mi = _SL_mi()
            try:
                _db_mi.add(_CE_mi(
                    call_id=cid,
                    event_type='counterpart_initial',
                    event_ts_ms=int(_t_mi.time() * 1000),
                    payload={
                        # Phase 08.23.2.COUNTERPART: Event-Name UND Payload tragen jetzt
                        # dieselben zwei Achsen-Woerter. 'counterpart_initial' ersetzt
                        # 'mode_initial' (Migration 0035, inkl. der Bestandszeilen).
                        'call_type': _call_type_init,
                        'counterpart': _counterpart_init,
                        'sid': sid,
                        'timestamp': _t_mi.monotonic(),
                    },
                ))
                _db_mi.commit()
                print(f'[live_session] counterpart_initial event written: call_id={cid!r} '
                      f'call_type={_call_type_init!r} counterpart={_counterpart_init!r}')
            finally:
                _db_mi.close()
        except Exception as _mi_err:
            print(f'[live_session] counterpart_initial persist Fehler (non-fatal): {type(_mi_err).__name__}: {_mi_err}')
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
                # TEMPO-1/W0: '' = "geladen, aber kein (nutzbarer) Opener" — NICHT None.
                # None bleibt reserviert fuer "Cache noch nicht geladen" (prompt_pipeline.py:193
                # faellt dann bewusst in den DB-Pfad, Punkt 26). BEIDE Wege muessen '' ergeben:
                # auch _opener vorhanden mit inhalt NULL (Spalte ist nullable).
                'opener_content': (getattr(_opener, 'inhalt', '') or '') if _opener else '',
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
# DELETED: last_postcall + last_postcall_lock (0 Prod-Reader nach app_routes:641 Writer-Entfernung)
# D-09 Phase PERSID Plan 01, 2026-07-03. Writer war app_routes.py:641 — ebenfalls entfernt.


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


def _flush_segment(sid: str, key: str):
    """Timer-Callback: popt Segment aus per-SID _merge_pending und uebergibt an Analyse-Queues.

    PERSID Plan 04 Familie B (S4):
    - Signatur nimmt sid + key (EIN Lock = _session_state_lock).
    - Ghost-SID-Guard: sid nicht mehr in _session_state -> Timer-Leiche, return.
    - Pop aus _session_state[sid]['_merge_pending'][key] unter _session_state_lock.
    - Toter transcript_buffer-Fallback entfernt (pending['sid'] IMMER gesetzt nach Plan 04).
    """
    # Pop unter _session_state_lock (EIN Lock, S4 — kein langer Op unter Lock)
    with _session_state_lock:
        _ss = _session_state.get(sid)
        if _ss is None:
            # Ghost-SID-Guard: Timer feuerte nach pop_session_state -> verwerfen
            return
        pending = _ss.get('_merge_pending', {}).pop(key, None)
    if not pending:
        return
    merged_text     = " ".join(pending['texts'])
    line_id         = pending['line_id']
    speaker         = pending['speaker']
    roles_confirmed = pending['roles_confirmed']
    sp_name         = pending['sp_name']
    t_start         = pending.get('t_start', time.monotonic())

    # Sprachstatistik aktualisieren (per-SID)
    word_count = len(merged_text.split())
    now_m = time.monotonic()
    with _session_state_lock:
        if sid in _session_state:
            _ss = _session_state[sid]
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
        with _per_sid_transcript_lock:
            _per_sid_transcript.setdefault(sid, []).append(
                {'text': merged_text, 'line_id': line_id, 't_start': t_start}
            )
        analyse_trigger.set()

    # WR-03: append to per-SID coaching buffer (not module-global)
    with _per_sid_coaching_lock:
        _per_sid_coaching_buffer.setdefault(sid, []).append(
            {'text': merged_text, 'speaker': sp_name, 't_start': t_start}
        )
    coaching_trigger.set()


def update_kaufbereitschaft(sid: str, delta: int):
    """Aktualisiert Kaufbereitschaft per-SID mit Delta, clamped to [5, 100].

    S4 RMW (PERSID Plan 05): clamp + verlauf.append als EIN atomarer Block unter
    _session_state_lock (kein Zwischen-Release, kein Lost-Update bei parallelen Ticks).
    D-02: ohne sid oder unbekannte sid → No-Op (kein Crash, kein Fehlzuordnung).
    """
    if not sid:
        return
    ts = datetime.now().strftime('%H:%M:%S')
    with _session_state_lock:
        if sid not in _session_state:
            return  # Ghost-SID Guard (D-02)
        _st = _session_state[sid]
        _st['kaufbereitschaft'] = max(5, min(100, _st.get('kaufbereitschaft', 30) + delta))
        _st['kaufbereitschaft_verlauf'].append({'ts': ts, 'wert': _st['kaufbereitschaft']})


def reset_session(sid: str) -> None:
    """Raeume NUR die eigene sid auf + poppe deren Snapshot (N-3 finales Cleanup).

    PERSID Plan 06 Familie E (Task 2c):
    - Signatur nimmt jetzt sid als Pflicht-Arg (NICHT no-arg all-reset).
    - D-02: sid=None → skip (kein All-Reset, kein Crash).
    - Raeumt pop_session_state(sid) — cancelt offene _merge_pending-Timer der sid.
    - N-3: poppt AUCH den gestashten Snapshot via pop_ended_session(sid).
      Doppel-Beenden bleibt gutartig (Snapshot schon weg nach erstem reset → kein Fehler).
    - Andere aktive Sessions (sidB, sidC …) bleiben VOLLSTAENDIG unangetastet.
    - Reset-Ueberlebens-Check (SPEC Req 4): get_anonymisierer(sidB) is anon_b_before.

    Caller: routes/app_routes.py:884 (FRESH-GREP 2026-07-04).
    Alle Modul-Global-Reset-Bloecke (Speaker-Familie, state-Keys, roles_swapped etc.) sind
    nach Plan 06 Familie E geloescht — per-SID-Daten liegen in _session_state[sid].
    """
    if not sid:
        return  # D-02: None-sid → No-Op (kein All-Reset)
    # per-SID-Cleanup: cancelt offene _merge_pending-Timer + popt den SID-Bucket
    pop_session_state(sid)
    # N-3: finales Snapshot-Cleanup (PEEK-Gegenstueck aus Plan 03 stash_ended_session)
    pop_ended_session(sid)


def record_ewb_click(sid: str, einwand_typ: str, success: bool = False,
                     antwort_text: str = None, einwand_text: str = None):
    """Erfasst einen EWB-Button-Klick im per-SID-State (thread-safe).

    PERSID Plan 06 Familie D: schreibt in _session_state[sid]['state']['ewb_clicks'].
    D-02 Ghost-SID-Guard: sid=None oder tote sid -> No-Op (kein globaler Fallback).
    LATENZ (Punkt 25, HART): NUR ein list.append unter _session_state_lock.
    """
    if not sid:
        return  # D-02: None-sid -> No-Op
    import datetime as _dt
    entry = {
        'einwand_typ':  einwand_typ,
        'success':      bool(success),
        'ts':           _dt.datetime.utcnow().isoformat(),
        'antwort_text': antwort_text or None,
        'einwand_text': einwand_text or None,
    }
    with _session_state_lock:
        if sid not in _session_state:
            return  # Ghost-SID-Guard: tote/nicht-existente sid -> No-Op
        _session_state[sid]['state'].setdefault('ewb_clicks', []).append(entry)


def record_suggestion_offer(sid: str, slot, source, model, suggestion_text, interaction_id,
                            einwand_typ=None):
    """TAXO2-08 (FOLD A): Erfasst EINEN ausgegebenen NERVE-Vorschlag im per-SID-RAM-Puffer
    _session_state[sid]['state']['suggestion_offers'] (thread-safe Append).

    PERSID Plan 06 Familie D: sid als erstes Arg — alle 3 Caller (deepgram:1017,
    matcher:338, claude:722) reichen sid durch (B4).

    LATENZ (Punkt 25, HART): NUR ein list.append unter _session_state_lock — KEIN get_session/commit,
    KEIN Netz, KEIN LLM. Der EINZIGE DB-Write ist der Call-Ende-Flush (suggestion_capture.py).

    ANON-VERTRAG (FOLD A-2 / Plan 09 depends_on): `suggestion_text` ist die BEREITS am Erfassen
    mit dem lebenden Per-SID-Cache anonymisierte Storage-Version (NICHT roh, NIE cache=None).
    Diese Funktion reicht sie nur durch — KEIN eigener Anon-Aufruf hier.

    B1 (FOLD A-2): `interaction_id` wird vom Capture-Hook via get_or_open_moment IMMER gesetzt
    (nie None erwartet). Wird hier nur durchgereicht.

    D-02 Ghost-SID-Guard: sid=None oder tote sid -> No-Op (kein globaler Fallback).
    """
    if not sid:
        return  # D-02: None-sid -> No-Op
    import datetime as _dt
    entry = {
        'slot':            slot,
        'source':          source,
        'model':           model,
        'suggestion_text': suggestion_text,   # bereits anonymisierte Storage-Version (Plan 09)
        'interaction_id':  interaction_id,     # immer gesetzt (B1)
        'einwand_typ':     einwand_typ,
        'ts':              _dt.datetime.utcnow().isoformat(),
    }
    with _session_state_lock:
        if sid not in _session_state:
            return  # Ghost-SID-Guard: tote/nicht-existente sid -> No-Op
        _session_state[sid]['state'].setdefault('suggestion_offers', []).append(entry)


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


def _build_log_content(bs, user_email='', profile_name='') -> str:
    """Baut TXT-Log-Content aus dem uebergebenen per-SID-State (bs/dict).

    N-3 (PERSID Plan 05): KEIN eigener _load_beenden_state-Aufruf — Caller
    (app_routes.api_beenden) reicht das EINE `_bs` als Parameter durch.
    Liest conversation_log, painpoints, gegenargument_log, phasen_log aus `bs`.
    bs darf None sein (leere Ausgabe, kein Crash — D-02 defensiv).
    """
    if bs is None:
        bs = {}
    entries = list(bs.get('conversation_log', []))
    # roles_swapped: per-SID aus bs lesen (PERSID Plan 05).
    # Hatte immer 0 `=True`-Schreiber (RESEARCH §1) → sp_map fest unswapped korrekt.
    sp_map = {0: 'Berater', 1: 'Kunde'}

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

    # painpoints aus bs (per-SID, N-3 — PERSID Plan 05)
    pp_snapshot = list(bs.get('painpoints', []))

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
    # gegenargument_log aus bs (per-SID, N-3 — PERSID Plan 05)
    ga_log = list(bs.get('gegenargument_log', []))
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
    # D-09 PERSID Plan 01: hilfe_log/quick_action_log hatten 0 .append()-Schreiber (RESEARCH §1).
    # Per Plan 03 (Welle A) vollstaendig migriert. Bis dahin: immer leere Listen (korrekt fuer 0 Events).

    # ── Phasen-Verlauf ────────────────────────────────────────────────────────
    # phasen_log aus bs (per-SID, N-3 — PERSID Plan 05)
    ph_log = list(bs.get('phasen_log', []))
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


# ── Phase 08.23.2.LOCK-1 Teil 3: Wachhund auf dem Sitzungs-Riegel ────────────────────
# Am 30.07. starb eine Sitzung um 09:27:56 und NIEMAND hat es gemerkt: kein Fehler, kein
# 504, keine Log-Zeile. Vier Klicks und ein [Beenden] liefen ins Leere. Dieser Tick ist
# die Antwort auf 'und wenn er doch klemmt?'.
#
# MUSTER: exakt wie [SLOW] requeue_pending (services/slow_lane.py:326-341) — Registrierung
# ueber register_periodic_tick_hook, Drosselung ueber einen Zaehler modulo N, KEIN zweiter
# Timer. Der Consumer taktet mit SLOW_LANE_TICK = 5.0s, also 6 Ticks = ~30s.
#
# FEHLERBEHANDLUNG: keine eigene noetig — _periodic_tick (slow_lane.py:349-353) klammert
# jeden Hook einzeln. ABER der Wachhund darf niemals werfen, WAEHREND er den Riegel haelt,
# sonst wird der Waechter zur Ursache. Deshalb: im Erfolgsfall NICHTS unter dem Riegel tun
# und im finally freigeben; die Log-Zeile steht im FEHL-Zweig, also OHNE Riegel.
#
# NEBENLAEUFIGKEIT: _lockwatch_tick laeuft ausschliesslich im EINEN Slow-Lane-Consumer-
# Faden (app.py). Die drei Zaehler unten haben genau einen Schreiber — kein Riegel noetig.
#
# PUNKT 28: die drei Zaehler sind veraenderlicher Modul-Zustand, beschreiben aber den
# RIEGEL/den PROZESS, nicht einen Nutzer oder Anruf (keine sid, keine user_id, keine
# org_id). Sie leben innerhalb dieses Moduls; der Global-Waechter prueft `ls.<attr> = ...`
# aus Fremdmodulen. Diese Begruendung IST der Whitelist-Eintrag.
#
# BEKANNTE GRENZE (P-6): _periodic_tick feuert NUR bei leerer Slow-Lane-Queue
# (slow_lane.py:792-793). Ist der Consumer beschaeftigt, gibt es keinen Tick. Im
# Verklemmungsfall ist das gutartig (bei geklemmtem Riegel produziert niemand neue Items,
# die Queue laeuft leer) — trotzdem gibt es die Herzschlag-Zeile, damit ein STUMMER
# Wachhund von einem ZUFRIEDENEN unterscheidbar ist.

# Der Log-Text ist auf ">2s" FESTGELEGT (CONTEXT). Wer diesen Wert aendert, aendert auch
# den Text — und die zwei Zeilen in deepgram_service.py / app_routes.py aus Teil 2b.
_LOCKWATCH_ACQUIRE_TIMEOUT_S = 2.0
_LOCKWATCH_EVERY_N_TICKS = 6        # 6 x SLOW_LANE_TICK(5.0s) = ~30s
_LOCKWATCH_HEARTBEAT_EVERY = 20     # jede 20. Pruefung = ~10 Minuten
_lockwatch_tick_count = 0
_lockwatch_runs = 0
_lockwatch_fails = 0


def _lockwatch_tick() -> None:
    """Periodische Riegel-Pruefung. Registriert via register_lockwatch_hook()."""
    global _lockwatch_tick_count, _lockwatch_runs, _lockwatch_fails
    _lockwatch_tick_count += 1
    if _lockwatch_tick_count % _LOCKWATCH_EVERY_N_TICKS != 0:
        return
    _lockwatch_runs += 1

    if _session_state_lock.acquire(timeout=_LOCKWATCH_ACQUIRE_TIMEOUT_S):
        try:
            pass    # P-3: im Erfolgsfall unter dem Riegel NICHTS tun
        finally:
            _session_state_lock.release()
        if _lockwatch_runs % _LOCKWATCH_HEARTBEAT_EVERY == 0:
            print(f"[LOCKWATCH] Herzschlag: {_lockwatch_runs} Pruefungen, "
                  f"{_lockwatch_fails} davon fehlgeschlagen")
        return

    # ── Fehl-Fall: OHNE gehaltenen Riegel loggen ──────────────────────────────────
    _lockwatch_fails += 1
    # Halter-Felder EINMAL in lokale Variablen lesen (sie koennen sich waehrend der
    # Formatierung aendern, wenn der Halter freigibt) und ALLE defensiv behandeln.
    _h_name = _session_state_lock.holder_thread
    _h_ident = _session_state_lock.holder_ident
    _h_mono = _session_state_lock.holder_since
    # Wanduhr wird NICHT beim Erwerb erfasst (B5), sondern hier aus dem monotonic-Abstand
    # abgeleitet — gleiche Aussage, ein C-Aufruf weniger im heissen Pfad.
    _jetzt_mono = time.monotonic()
    _dauer = (f"{_jetzt_mono - _h_mono:.1f}s" if _h_mono else 'unbekannt')
    _seit = (time.strftime('%H:%M:%S', time.localtime(time.time() - (_jetzt_mono - _h_mono)))
             if _h_mono else 'unbekannt')
    print(f"[LOCKWATCH] _session_state_lock >2s belegt | Faden={_h_name or 'unbekannt'!r} "
          f"ident={_h_ident} | Uebernahme={_seit} | gehalten={_dauer} | "
          f"Stapel-Abzug: sudo systemctl kill -s SIGUSR1 nerve")


def register_lockwatch_hook() -> None:
    """Haengt den Wachhund in die Slow-Lane-Tick-Registry. Wird EINMAL aus app.py gerufen,
    VOR dem Start des slow_lane_consumer-Fadens — damit das Start-Beleg-Log
    (slow_lane.py:781) ihn mitzaehlt und man in `inspect.sh logs` sieht, dass er scharf ist.

    Der Import ist LAZY: slow_lane zieht database.db nach, und live_session wird sehr frueh
    und sehr breit importiert. Heute gibt es keinen Zyklus (slow_lane importiert
    live_session nicht) — das lazy Import haelt es dabei.

    Idempotent: ein zweiter Aufruf registriert NICHT erneut (sonst doppelte Log-Zeilen).
    """
    from services.slow_lane import register_periodic_tick_hook, _PERIODIC_TICK_HOOKS
    if _lockwatch_tick in _PERIODIC_TICK_HOOKS:
        print("[LOCKWATCH] Wachhund war bereits registriert — kein zweiter Eintrag")
        return
    register_periodic_tick_hook(_lockwatch_tick)
    print(f"[LOCKWATCH] Wachhund registriert: alle ~{_LOCKWATCH_EVERY_N_TICKS * 5}s eine "
          f"Probe mit {_LOCKWATCH_ACQUIRE_TIMEOUT_S}s Zeitlimit")
