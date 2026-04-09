"""
Runtime state for the live NERVE session.
All globals and shared state lives here to avoid circular imports.
"""
import os
import threading
import time
from datetime import datetime
from config import ANALYSE_INTERVALL, MERGE_WINDOW_S, SPEAKER_DEBOUNCE_S, KATEGORIE_LABEL

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

# ── Coach-Tipps (Live-Tipps vom Coach an Berater) ─────────────────────────────
coach_tipps_lock = threading.Lock()
coach_tipps      = []

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

def next_line_id() -> str:
    global _line_id_counter
    with _line_id_lock:
        _line_id_counter += 1
        return str(_line_id_counter)

# ── Analyse-State ─────────────────────────────────────────────────────────────
state_lock = threading.Lock()
state = {
    'version':          0,
    'aktiv':            False,
    'ergebnis':         None,
    'line_id':          None,
    'kaufbereitschaft': 30,
    'ewb_top2':         None,  # List of 2 EWB type strings, AI-ranked
    'ewb_clicks':       [],    # Liste von dicts: {'einwand_typ': str, 'success': bool, 'ts': iso}
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
speech_lock            = threading.Lock()
berater_words          = 0
kunde_words            = 0
session_start_time     = None
laengster_monolog_sek  = 0.0
_current_monolog_start = None

# ── Abgedeckte Phasen ─────────────────────────────────────────────────────────
covered_phases_lock = threading.Lock()
covered_phases      = set()

# ── Aktives Profil ────────────────────────────────────────────────────────────
active_profile_lock = threading.Lock()
active_profile_data = {}
active_profile_name = ''


def set_active_profile(name: str, daten: dict):
    global active_profile_data, active_profile_name
    with active_profile_lock:
        active_profile_name = name or ''
        active_profile_data = daten if isinstance(daten, dict) else {}


def get_active_profile():
    with active_profile_lock:
        return active_profile_name, dict(active_profile_data)


# ── Letztes Post-Call Snapshot ────────────────────────────────────────────────
last_postcall_lock = threading.Lock()
last_postcall      = None


def stabilize_speaker(raw):
    global _confirmed_speaker, _pending_speaker, _pending_since
    with _speaker_lock:
        if raw is None:
            return _confirmed_speaker
        if raw == _confirmed_speaker:
            _pending_speaker = None
            _pending_since   = None
            return _confirmed_speaker
        if raw != _pending_speaker:
            _pending_speaker = raw
            _pending_since   = time.monotonic()
        elapsed = time.monotonic() - _pending_since
        if elapsed >= SPEAKER_DEBOUNCE_S:
            _confirmed_speaker = _pending_speaker
            _pending_speaker   = None
            _pending_since     = None
        return _confirmed_speaker


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
    global berater_words, kunde_words, laengster_monolog_sek, _current_monolog_start
    with speech_lock:
        if sp_name == 'Berater':
            berater_words += word_count
            if _current_monolog_start is None:
                _current_monolog_start = t_start
            dur = now_m - _current_monolog_start
            if dur > laengster_monolog_sek:
                laengster_monolog_sek = dur
        elif sp_name == 'Kunde':
            kunde_words += word_count
            _current_monolog_start = None

    if not roles_confirmed or speaker != 0:
        with buffer_lock:
            transcript_buffer.append({'text': merged_text, 'line_id': line_id, 't_start': t_start})
        analyse_trigger.set()

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
    """Setzt den kompletten Live-State zurück (nach 'Gespräch beenden')."""
    global conversation_log, transcript_buffer, analysiert_bisher, painpoints
    global coaching_buffer, _line_id_counter, _log_last_sp
    global _confirmed_speaker, _pending_speaker, _pending_since, _second_sp_seen
    global _bof_count, roles_swapped
    global kaufbereitschaft, kaufbereitschaft_verlauf, aktive_phase_idx
    global berater_words, kunde_words, session_start_time, laengster_monolog_sek, _current_monolog_start
    global gegenargument_log, hilfe_log, quick_action_log, phasen_log

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
        state['line_id']          = None
        state['kaufbereitschaft'] = 30
        state['ewb_top2']         = None
        # ── Phase 04.8 field resets (R3: missing resets cause stale hints) ──
        state['current_phase']       = 1
        state['current_phase_name']  = 'Opener'
        state['phase_confidence']    = 0.0
        state['phase_changed_at']    = None
        state['phase_change_count']  = 0
        state['readiness_score']     = 30
        state['readiness_bucket']    = 'cold'
        state['score_factors_seen']  = {}
        state['active_hint']         = None
        state['ewb_buttons']         = None
        state['cold_call_inference'] = None
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
    with speech_lock:
        berater_words          = 0
        kunde_words            = 0
        laengster_monolog_sek  = 0.0
        _current_monolog_start = None
        session_start_time     = time.monotonic()
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


def record_ewb_click(einwand_typ: str, success: bool = False):
    """Erfasst einen EWB-Button-Klick im Session-State (thread-safe)."""
    import datetime as _dt
    with state_lock:
        state.setdefault('ewb_clicks', []).append({
            'einwand_typ': einwand_typ,
            'success':     bool(success),
            'ts':          _dt.datetime.utcnow().isoformat(),
        })


def get_speech_stats() -> dict:
    """Gibt aktuelle Sprachstatistiken zurück."""
    with speech_lock:
        total = berater_words + kunde_words
        redeanteil = round(berater_words / total * 100) if total > 0 else 0
        st = session_start_time
        bw = berater_words
        monolog = round(laengster_monolog_sek, 1)
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
