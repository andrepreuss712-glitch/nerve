import threading
import time
from datetime import datetime
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY, DEEPGRAM_HOST, SAMPLE_RATE, MERGE_WINDOW_S
import services.live_session as ls
import time as _time_mod

# ── Per-session Deepgram connections ──────────────────────────────────────────
_deepgram_sessions = {}        # {sid: connection}
_session_modes = {}            # {sid: 'cold_call'|'meeting'}
_cost_opened_at = {}           # {sid: float} — Phase 04.7.2 STT-minute tracking (kept for clean dict)
_stt_seconds_accumulated = {}  # {sid: float} — H-9: echte STT-Sekunden, nicht Socket-Lifetime
_sessions_lock = threading.Lock()


def _get_speaker(result):
    try:
        words = result.channel.alternatives[0].words
        if not words:
            return None
        counts = {}
        for w in words:
            sp = getattr(w, 'speaker', None)
            if sp is not None:
                counts[sp] = counts.get(sp, 0) + 1
        return max(counts, key=counts.get) if counts else None
    except Exception:
        return None


def _make_on_message(sid):
    def on_message(self, result, **kwargs):
        from extensions import socketio as sio
        # Guard: SID may not be in _per_sid_profile yet if Deepgram fires
        # before handle_start_live_session completes DB load (race window).
        # setdefault is a safe no-op if key already exists.
        with ls._per_sid_lock:
            ls._per_sid_profile.setdefault(sid, ('', {}))
        try:
            text = result.channel.alternatives[0].transcript
            if not text:
                return
            with ls.pause_lock:
                if ls.is_paused:
                    return

            if result.is_final:
                speaker = ls.stabilize_speaker(_get_speaker(result))
                line_id = ls.next_line_id()
                ts      = datetime.now().strftime('%H:%M:%S')

                # Zweiter Sprecher gesehen?
                with ls._sp2_lock:
                    if speaker == 1:
                        ls._second_sp_seen = True
                    roles_confirmed = ls._second_sp_seen

                # Sprecher-Fallback für Log
                with ls._log_sp_lock:
                    if speaker is not None:
                        ls._log_last_sp = speaker
                    log_sp = speaker if speaker is not None else ls._log_last_sp

                if roles_confirmed:
                    sp_label     = 'Berater' if log_sp == 0 else ('Kunde' if log_sp == 1 else 'Unbekannt')
                    emit_speaker = speaker
                else:
                    sp_label     = 'Unbekannt'
                    emit_speaker = None

                print(f"[DG] [{sp_label}] {text}")
                sio.emit('transcript', {'type': 'final', 'text': text,
                                        'speaker': emit_speaker, 'line_id': line_id},
                         room=sid)
                # D-06: Du/Sie detection heuristic (2-trigger threshold per utterance)
                _check_anrede_switch(sio, sid, text, ls)
                with ls.log_lock:
                    ls.conversation_log.append({
                        'ts': ts, 'type': 'transcript',
                        'speaker': log_sp if roles_confirmed else None,
                        'text': text, 'data': None,
                    })

                # ── H-9: akkumuliere echte STT-Sekunden ──────────────────────
                _dur = getattr(getattr(result, 'metadata', None), 'duration', 0.0) or 0.0
                if _dur > 0:
                    with _sessions_lock:
                        _stt_seconds_accumulated[sid] = _stt_seconds_accumulated.get(sid, 0.0) + _dur

                if roles_confirmed:
                    sp_name = 'Berater' if speaker == 0 else ('Kunde' if speaker == 1 else 'Sprecher')
                else:
                    sp_name = 'Sprecher'

                key = str(speaker) if speaker is not None else 'unknown'
                with ls._merge_lock:
                    if key in ls._merge_pending:
                        ls._merge_pending[key]['timer'].cancel()
                        ls._merge_pending[key]['texts'].append(text)
                        ls._merge_pending[key]['line_id'] = line_id
                    else:
                        ls._merge_pending[key] = {
                            'texts':           [text],
                            'line_id':         line_id,
                            'speaker':         speaker,
                            'roles_confirmed': roles_confirmed,
                            'sp_name':         sp_name,
                            't_start':         time.monotonic(),
                            'sid':             sid,   # Phase 08.19.4 D-02: route flush to per-SID buffer
                        }
                    t = threading.Timer(MERGE_WINDOW_S, ls._flush_segment, args=[key])
                    t.daemon = True
                    t.start()
                    ls._merge_pending[key]['timer'] = t
            else:
                sio.emit('transcript', {'type': 'interim', 'text': text},
                         room=sid)

                # ── BUG-10-LAT Wave 2: Keyword-Match auf Interim-Transcript ──────
                try:
                    with ls.state_lock:
                        _muted = ls.state.get('mic_muted', False)
                    if _muted:
                        return
                    _profile_name, _profile_daten = ls.get_profile_for_sid(sid)
                    einwaende = (_profile_daten.get('einwaende_detail') or _profile_daten.get('einwaende') or []) if isinstance(_profile_daten, dict) else []
                    if not einwaende:
                        return
                    matcher = ls.get_matcher(sid)
                    match = matcher.match_with_dedup(text, einwaende)
                    if not match:
                        return

                    # Slot 0: Sofort-Render via Socket-Event
                    _label = match.get('matched_label', '')
                    _pe = match.get('profile_einwand') or {}
                    sio.emit('keyword_einwand_match', {
                        'keyword':           match['keyword'],
                        'typ':               _label,
                        'profile_einwand':   _pe,
                        'transcript_snippet': text[:200],
                    }, room=sid)
                    print(f"[KeywordMatch] sid={sid} keyword={match['keyword']} label={_label} text={text[:60]!r}")

                    # Slot 1: parallele Haiku-Variante, shared busy_until via ls.state
                    with ls.state_lock:
                        _busy = ls.state.get('slot1_variant_busy_until', 0)
                    _now = _time_mod.monotonic()
                    if _now >= _busy:
                        with ls.state_lock:
                            ls.state['slot1_variant_busy_until'] = _now + 6
                        with ls.buffer_lock:
                            _kontext = " ".join(ls.analysiert_bisher[-20:])
                        from services.claude_service import streame_auto_variante
                        sio.start_background_task(
                            streame_auto_variante,
                            text, einwaende, _kontext, sid, 1, "keyword"
                        )
                    else:
                        print(f"[KeywordMatch] Slot-1 busy — skip (busy_until={_busy:.1f}, now={_now:.1f})")
                except Exception as _kw_err:
                    print(f"[KeywordMatch] error sid={sid}: {_kw_err}")
        except Exception as e:
            print(f"[DG] Fehler: {e}")
    return on_message


def _make_on_open(sid):
    def on_open(self, open, **kwargs):
        print(f"[DG] Verbunden (sid={sid})")
    return on_open


def _make_on_error(sid):
    def on_error(self, error, **kwargs):
        from extensions import socketio as sio
        print(f"[DG] Error (sid={sid}): {error}")
        sio.emit('dg_error', {'error': str(error)}, room=sid)
    return on_error


def _make_on_close(sid):
    # POLISH-48: Close-Handler — macht serverseitige Deepgram-Schliessungen sichtbar.
    # Vorher: wenn Deepgram die WS wegen invalid params / idle-timeout / quota silent
    # schloss, wurde der Close-Event zwar emitted aber von keinem Handler verarbeitet.
    # Symptom: Session bleibt stumm, kein Log. Jetzt: print + socket-event.
    def on_close(self, close, **kwargs):
        from extensions import socketio as sio
        print(f"[DG] Close (sid={sid}): {close}")
        try:
            sio.emit('dg_close', {'info': str(close)}, room=sid)
        except Exception:
            pass
    return on_close


def _make_on_utterance_end(sid):
    def on_utterance_end(self, utterance_end, **kwargs):
        # 06.2-r1: Kein matcher.reset_all() hier — Feedback-Loop-Schutz:
        # User liest Gegenargument vor ('...Sie haben dafuer keine Zeit...'),
        # Deepgram committet UtteranceEnd, ohne Reset wuerde der Satz erneut
        # matchen und einen doppelten Render triggern. 10s-Dedup PER KEYWORD
        # reicht: verschiedene Einwaende (zu_teuer vs. keine_zeit) haben
        # unabhaengige Dedup-Eintraege und blockieren sich nicht gegenseitig.
        pass
    return on_utterance_end


def _open_deepgram_connection(sid, mode='meeting'):
    # POLISH-49: EU-Host-Override für DSGVO-konforme Audio-Verarbeitung.
    # Standardmäßig `api.eu.deepgram.com` (siehe config.py Default).
    client = DeepgramClient(
        DEEPGRAM_API_KEY,
        config=DeepgramClientOptions(url=f"https://{DEEPGRAM_HOST}"),
    )
    connection = client.listen.websocket.v("1")
    connection.on(LiveTranscriptionEvents.Transcript, _make_on_message(sid))
    connection.on(LiveTranscriptionEvents.Open, _make_on_open(sid))
    connection.on(LiveTranscriptionEvents.Error, _make_on_error(sid))
    connection.on(LiveTranscriptionEvents.Close, _make_on_close(sid))
    connection.on(LiveTranscriptionEvents.UtteranceEnd, _make_on_utterance_end(sid))
    is_meeting = (mode == 'meeting')
    # POLISH-48: smart_format=True auch in Meeting-Mode. Der alte Kommentar
    # ("disable smart_format — preserves word-level speaker attributes") war eine
    # Fehleinschaetzung: laut Deepgram-SDK response.py ist `ListenWSWord.speaker`
    # ein eigenes Feld, unabhaengig von `punctuated_word`. diarize=True liefert
    # speaker trotz smart_format=True. Die Kombination smart_format=False +
    # punctuate=True + diarize=True + utterance_end_ms="1000" war nicht
    # runtime-verifiziert (Phase 04.2-03 Verification-Doku: "Runtime verification
    # still required") und erzeugte in der Praxis keine Transcripts.
    options_kwargs = dict(
        model="nova-2",
        language="de",
        smart_format=True,
        interim_results=True,
        endpointing=900,
        punctuate=True,
        diarize=is_meeting,
        encoding="linear16",
        sample_rate=SAMPLE_RATE,
    )
    if is_meeting:
        options_kwargs['utterance_end_ms'] = "1000"
    options = LiveOptions(**options_kwargs)
    print(f"[DG] LiveOptions: model=nova-2, diarize={is_meeting}, smart_format=True")
    connection.start(options)
    with _sessions_lock:
        _deepgram_sessions[sid] = connection
        _session_modes[sid] = mode
        _cost_opened_at[sid] = time.time()
    print(f"[DG] Session gestartet (sid={sid}, mode={mode}, diarize={is_meeting})")


def _close_deepgram_connection(sid):
    with _sessions_lock:
        connection = _deepgram_sessions.pop(sid, None)
        _session_modes.pop(sid, None)
        _cost_opened_at.pop(sid, None)           # Dict sauber halten (H-9: nicht mehr als Basis)
        stt_sek = _stt_seconds_accumulated.pop(sid, 0.0)  # H-9: echte STT-Sekunden
    # ── H-9 Cost-Hook: echte STT-Sekunden statt Socket-Lifetime ────────
    try:
        from services.cost_tracker import log_api_cost
        minutes = stt_sek / 60.0
        if minutes > 0.01:  # keine Artefakt-Rows fuer Sub-Sekunden
            log_api_cost('deepgram', 'nova-2', user_id=None,
                         units=minutes, unit_type='per_minute',
                         session_id=str(sid), context_tag='stt')
    except Exception as _e:
        print(f"[CostHook] deepgram stt skipped: {_e}")
    # ────────────────────────────────────────────────────────────────────
    if connection:
        try:
            connection.finish()
        except Exception as e:
            print(f"[DG] Fehler beim Schliessen (sid={sid}): {e}")
        print(f"[DG] Session beendet (sid={sid})")


# ── Phase 08.20 D-06: Du/Sie Anrede-Detection ────────────────────────────────
# CLAUDE.md ASCII rule: variable names use ASCII; string content may use real Umlauts.
# Note: 'weißt du' spelled as 'weisst du' in the list (ASCII-safe for pattern matching).
_DU_FORMS = [
    'kannst du', 'hast du', 'bist du', 'machst du', 'willst du',
    'weisst du', 'denkst du', 'sagst du', 'hoerst du',
    'siehst du', 'brauchst du', 'kennst du', 'findest du', 'glaubst du',
]


def _check_anrede_switch(sio_ref, sid_ref, transcript_text, ls_module):
    """Check if transcript contains Du-forms indicating anrede switch. Non-blocking."""
    try:
        text_lower = transcript_text.lower()
        _du_count = sum(1 for form in _DU_FORMS if form in text_lower)
        if _du_count >= 2:
            _current_anrede = 'sie'
            try:
                with ls_module._session_state_lock:
                    _current_anrede = ls_module._session_state.get(sid_ref, {}).get('session_anrede', 'sie')
            except Exception:
                pass
            if _current_anrede == 'sie':
                sio_ref.emit('anrede_switch_detected', {
                    'detected_form': 'du',
                    'confidence': round(min(1.0, _du_count / 3.0), 2),
                    'sid': sid_ref,
                }, room=sid_ref)
                print(f"[Anrede-Detection] Du-switch detected: {_du_count} forms in utterance sid={sid_ref}")
    except Exception as _ae:
        print(f"[Anrede-Detection] check failed (non-fatal): {_ae}")


def register_audio_handlers(sio):
    @sio.on('start_live_session')
    def handle_start_live_session(data=None, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        # setdefault race guard: prevent KeyError if vorwissen_level or other events arrive
        # before init_session_state() completes (MEDIUM fix — 08.20 REVIEWS.md)
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})
        mode = 'meeting'  # default for backward compatibility
        precall_briefing = None
        if isinstance(data, dict):
            mode = data.get('mode', 'meeting')
            precall_briefing = data.get('precall_briefing', None)
        print(f"[DG] start_live_session received (sid={_sid}, mode={mode})")
        _open_deepgram_connection(_sid, mode=mode)

        # Store precall briefing in live session state
        # (ls imported at module level — do not re-import here, causes UnboundLocalError
        # before the setdefault guard above which also uses ls)
        # POLISH-22 Bugfix: session_start_time beim Call-Start setzen (nicht erst beim
        # reset_session am Call-Ende). Vorher blieb der Timer auf dem time.monotonic()
        # des letzten Call-Endes oder None, und dauer_sek wurde zu 0 oder falsch gross.
        import time as _time
        with ls.speech_lock:
            ls.session_start_time = _time.monotonic()
            ls.berater_words = 0
            ls.kunde_words = 0
        # ── Phase 08 D-14: PreCall-Anrede-Override in ls.state persistieren ───
        # Whitelist {'Du', 'Sie'} schuetzt vor Prompt-Injection (T-08-05-01).
        # CR-02: Raw-Input wird zuerst via strip().title() normalisiert, damit
        # 'du', ' Du', 'DU' als 'Du' erkannt werden. Ungueltige Werte bleiben
        # rejected — build_profile_context faellt auf Profile-Default oder 'Sie'.
        anrede_raw = (data or {}).get('anrede') if isinstance(data, dict) else None
        anrede_norm = anrede_raw.strip().title() if isinstance(anrede_raw, str) else None
        if anrede_norm in ('Du', 'Sie'):
            with ls.state_lock:
                ls.state['session_anrede'] = anrede_norm
            print(f"[Phase08] session_anrede={anrede_norm} set from PreCall (raw={anrede_raw!r})")

        # ── Phase 08.20 D-05: vorwissen_level aus session-start Payload ───────────
        _vorwissen = (data or {}).get('vorwissen_level') if isinstance(data, dict) else None
        if _vorwissen in ('niedrig', 'mittel', 'hoch'):
            with ls._session_state_lock:
                ls._session_state.setdefault(_sid, {})
                ls._session_state[_sid]['vorwissen_level'] = _vorwissen
            print(f"[Vorwissen] initial level={_vorwissen} from session-start payload sid={_sid}")

        if precall_briefing and isinstance(precall_briefing, str):
            if len(precall_briefing) > 2000:
                precall_briefing = precall_briefing[:2000]
            with ls.state_lock:
                ls.state['precall_briefing'] = precall_briefing
            print(f"[DG] PreCall-Briefing gespeichert ({len(precall_briefing)} Zeichen)")

        skript_inhalt = data.get('skript_inhalt') if isinstance(data, dict) else None
        if skript_inhalt and isinstance(skript_inhalt, str):
            # T-06-07: Truncate to 50000 chars max to prevent DoS
            skript_inhalt = skript_inhalt[:50000]
            bloecke = [b.strip() for b in skript_inhalt.split('\n\n') if b.strip()]
            with ls.state_lock:
                ls.state['aktives_skript_inhalt'] = skript_inhalt
                ls.state['skript_bloecke'] = bloecke
            print(f"[PiP] Skript geladen ({len(bloecke)} Bloecke)")

        # WR-04: user_id extracted before try-blocks so it's always defined even
        # if the FT logging block raises before the assignment.
        from flask import session as flask_session
        user_id = flask_session.get('user_id')

        # FT logging: create ft_call_sessions row (Phase 04.7.1)
        try:
            from database.db import SessionLocal
            from database.models import FtCallSession, User
            if user_id:
                db = SessionLocal()
                try:
                    u = db.query(User).filter_by(id=user_id).first()
                    market = (getattr(u, 'market', None) if u else None) or 'dach'
                    language = (getattr(u, 'language', None) if u else None) or 'de'
                    ft_row = FtCallSession(
                        user_id=user_id,
                        mode=mode,
                        market=market,
                        language=language,
                        hints_shown=0,
                        hints_used=0,
                        buttons_pressed=0,
                    )
                    db.add(ft_row)
                    db.commit()
                    ft_session_id = ft_row.id
                finally:
                    db.close()
                with ls.state_lock:
                    ls.state['ft_session_id'] = ft_session_id
                    ls.state['user_id'] = user_id
                    ls.state['market'] = market
                    ls.state['language'] = language
                    ls.state['org_id'] = u.org_id if u else None
                    ls.state['mode'] = mode
                print(f"[FT] ft_call_sessions row created id={ft_session_id} market={market}")
        except Exception as _e:
            print(f"[FT] ft_call_sessions insert failed: {_e}")

        # ── Phase 08.19.4: Per-SID Profile + Session State Init ──────────────
        # Loads active profile from DB (User.active_profile_id — D-05 Single Source of Truth).
        # Idempotent: if SID reconnects before disconnect fires, pop old state first.
        try:
            from database.db import SessionLocal as _SL2
            from database.models import User as _User2, Profile as _Profile2
            _db2 = _SL2()
            try:
                _u2 = _db2.query(_User2).filter_by(id=user_id).first()
                _profile_id2 = getattr(_u2, 'active_profile_id', None) if _u2 else None
                _org_id2 = getattr(_u2, 'org_id', None) if _u2 else None
                _profile_name2 = ''
                _profile_daten2 = {}
                if _profile_id2:
                    _p2 = _db2.query(_Profile2).filter_by(id=_profile_id2).first()
                    if _p2 and _p2.daten:
                        import json as _json2
                        _profile_name2 = _p2.name or ''
                        _profile_daten2 = _json2.loads(_p2.daten) if isinstance(_p2.daten, str) else {}
            finally:
                _db2.close()
            # Idempotent: pop stale state if SID already exists (reconnect without disconnect)
            if _sid in ls._session_state:
                ls.pop_session_state(_sid)
            ls.init_session_state(
                _sid,
                user_id=user_id,
                org_id=_org_id2 or 0,
                profile_id=_profile_id2,
                market=market,
                language=language,
                mode=mode,
            )
            ls.set_profile_for_sid(_sid, _profile_name2, _profile_daten2)
            print(f"[08.19.4] SID {_sid}: profile={_profile_name2!r} pid={_profile_id2} org={_org_id2}")
            # HIGH-3 fix: pre-load profile extras (Opener, FAQ) into session cache
            # build_profile_context() reads from cache — no DB queries in streaming hot path
            if _profile_id2:
                try:
                    ls._load_profile_cache(sid=_sid, user_id=user_id, profile_id=_profile_id2)
                except Exception as _cache_e:
                    print(f"[DG] _load_profile_cache failed (non-fatal): {_cache_e}")
        except Exception as _pe:
            print(f"[08.19.4] per-SID init failed for {_sid}: {_pe}")

    @sio.on('stop_live_session')
    def handle_stop_live_session(sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        print(f"[DG] stop_live_session event received (sid={_sid})")
        _close_deepgram_connection(_sid)
        ls.pop_session_state(_sid)

    # POLISH-48: Chunk-Counter statt one-shot-Logs. Vorher `_first_chunk_logged`
    # loggte nur den ersten Chunk pro sid — was User-Observation "nur ein Chunk"
    # zu einem Red Herring machte. Jetzt: Log ersten Chunk + dann every 100th
    # (ca. alle 10s bei 100ms-Frames), damit realer Audio-Flow sichtbar ist.
    _chunk_counts = {}  # {sid: int}

    @sio.on('audio_chunk')
    def handle_audio_chunk(data, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        cnt = _chunk_counts.get(_sid, 0) + 1
        _chunk_counts[_sid] = cnt
        if cnt == 1 or cnt % 100 == 0:
            print(f"[DG] audio_chunk #{cnt} (sid={_sid}, bytes={len(data)}, type={type(data).__name__})")
        with ls.pause_lock:
            if ls.is_paused:
                return
        with _sessions_lock:
            connection = _deepgram_sessions.get(_sid)
        if connection:
            try:
                connection.send(data)
            except Exception as e:
                print(f"[DG] Send error (sid={_sid}): {e}")

    @sio.on('disconnect')
    def handle_disconnect(sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        # setdefault race guard: disconnect may fire before start_live_session fully initializes
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})
        print(f"[DG] socket.io disconnect event (sid={_sid})")
        _chunk_counts.pop(_sid, None)
        _close_deepgram_connection(_sid)
        ls.pop_session_state(_sid)

    @sio.on('set_anrede')
    def handle_set_anrede(data):
        """Update session_anrede for SID on manual Du/Sie toggle (D-06)."""
        from flask import request
        sid = request.sid
        anrede = (data.get('anrede') or 'sie').lower() if isinstance(data, dict) else 'sie'
        if anrede not in ('du', 'sie'):
            anrede = 'sie'
        with ls._session_state_lock:
            ls._session_state.setdefault(sid, {})
            ls._session_state[sid]['session_anrede'] = anrede
        print(f"[Anrede] set_anrede={anrede} sid={sid}")

    @sio.on('set_vorwissen')
    def handle_set_vorwissen(data):
        """Update vorwissen_level for SID on Picker interaction (D-05)."""
        from flask import request
        sid = request.sid
        level = data.get('level') if isinstance(data, dict) else None
        if level not in ('niedrig', 'mittel', 'hoch', None):
            level = None
        with ls._session_state_lock:
            ls._session_state.setdefault(sid, {})
            ls._session_state[sid]['vorwissen_level'] = level
        print(f"[Vorwissen] set_vorwissen={level} sid={sid}")

    @sio.on('anrede_switch_rejected')
    def handle_anrede_switch_rejected(data):
        """Log rejection for algorithm tuning. No state change. (D-06)."""
        from flask import request
        sid = request.sid
        print(f"[Anrede-Detection] anrede_switch_rejected sid={sid} (tuning log)")

    @sio.on('mute_mic')
    def handle_mute_mic(data=None, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        muted = bool(data.get('muted', True)) if isinstance(data, dict) else True
        with ls.state_lock:
            ls.state['mic_muted'] = muted
        print(f"[DG] mute_mic sid={_sid} muted={muted}")

    # 06.1-r2 r4: Dual-Slot Manual EWB
    # - Slot 0 wird client-side aus profile.einwaende instant gerendert (null Latenz)
    # - Slot 1 streamt Haiku eine kontextbezogene Variante (Gespraechsverlauf + Profil)
    # Klick wird zusaetzlich in ls.state.ewb_clicks fuer postcall-Analytics geloggt.
    @sio.on('manual_ewb')
    def handle_manual_ewb(data=None, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        if not isinstance(data, dict):
            return
        typ = (data.get('text') or '').strip()
        if not typ:
            return
        print(f"[PiP] manual_ewb (sid={_sid}): {typ[:80]}")
        import services.live_session as ls

        # Profil + Kontext fuer Haiku-Variante aufbereiten.
        # get_active_profile() returns tuple (name, daten) — unpack it.
        profile_daten = {}
        try:
            _pname, profile_daten = ls.get_profile_for_sid(_sid)
        except Exception:
            profile_daten = {}
        einwaende = (profile_daten.get('einwaende_detail') or profile_daten.get('einwaende') or []) if isinstance(profile_daten, dict) else []
        profile_einwand = None
        typL = typ.lower().strip()
        # 06.1-r2 BUG-14c: Match gegen kurzlabel || kategorie (gleiche Chain wie Frontend).
        for e in einwaende:
            if isinstance(e, dict):
                label = (e.get('kurzlabel') or e.get('short_label') or e.get('kategorie') or '').lower().strip()
                if label == typL:
                    profile_einwand = e
                    break
        with ls.buffer_lock:
            kontext = " ".join(ls.analysiert_bisher[-20:])

        from services.claude_service import streame_manual_ewb_variante

        def _run():
            try:
                result = streame_manual_ewb_variante(typ, profile_einwand or {}, kontext, _sid, slot=1)
                _antwort = (result.get('gegenargument_1') or '').strip() or None
                try:
                    ls.record_ewb_click(typ, success=True,
                                        antwort_text=_antwort, einwand_text=typ)
                except Exception as e:
                    print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
            except Exception as ex:
                print(f"[PiP] manual_ewb variante error (sid={_sid}): {ex}")
                try:
                    ls.record_ewb_click(typ, success=False, einwand_text=typ)
                except Exception as e:
                    print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
                try:
                    sio.emit('pip_stream_error', {'slot': 1, 'error': str(ex)}, room=_sid)
                except Exception:
                    pass

        # POLISH-38.1: record_ewb_click happens inside _run after streaming completes
        # so antwort_text is available. Spawn-error is handled separately below.
        try:
            sio.start_background_task(_run)
        except Exception as _spawn_err:
            print(f"[PiP] manual_ewb spawn error (sid={_sid}): {_spawn_err}")
            try:
                ls.record_ewb_click(typ, success=False, einwand_text=typ)
            except Exception as e:
                print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
