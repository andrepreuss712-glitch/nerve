import threading
import time
from datetime import datetime
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY, SAMPLE_RATE, MERGE_WINDOW_S
import services.live_session as ls

# ── Per-session Deepgram connections ──────────────────────────────────────────
_deepgram_sessions = {}   # {sid: connection}
_session_modes = {}       # {sid: 'cold_call'|'meeting'}
_cost_opened_at = {}      # {sid: float} — Phase 04.7.2 STT-minute tracking
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
        try:
            text = result.channel.alternatives[0].transcript
            if not text:
                return
            with ls.pause_lock:
                if ls.is_paused:
                    return

            if result.is_final:
                # Latenz-Optimierung: wake analyse_loop immediately on is_final
                # instead of waiting for the MERGE_WINDOW flush (~1s) or the
                # ANALYSE_INTERVALL fallback (2s). Idempotent — multiple sets
                # coalesce; analyse_loop clears the event at loop start.
                ls.analyse_trigger.set()
                ls.coaching_trigger.set()
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
                with ls.log_lock:
                    ls.conversation_log.append({
                        'ts': ts, 'type': 'transcript',
                        'speaker': log_sp if roles_confirmed else None,
                        'text': text, 'data': None,
                    })

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
                        }
                    t = threading.Timer(MERGE_WINDOW_S, ls._flush_segment, args=[key])
                    t.daemon = True
                    t.start()
                    ls._merge_pending[key]['timer'] = t
            else:
                sio.emit('transcript', {'type': 'interim', 'text': text},
                         room=sid)
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


def _open_deepgram_connection(sid, mode='meeting'):
    client = DeepgramClient(DEEPGRAM_API_KEY)
    connection = client.listen.websocket.v("1")
    connection.on(LiveTranscriptionEvents.Transcript, _make_on_message(sid))
    connection.on(LiveTranscriptionEvents.Open, _make_on_open(sid))
    connection.on(LiveTranscriptionEvents.Error, _make_on_error(sid))
    is_meeting = (mode == 'meeting')
    options_kwargs = dict(
        model="nova-2",
        language="de",
        smart_format=not is_meeting,   # disable smart_format in meeting mode — preserves word-level speaker attributes
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
    print(f"[DG] LiveOptions: model=nova-2, diarize={is_meeting}, smart_format={not is_meeting}")
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
        opened = _cost_opened_at.pop(sid, None)
    # ── Phase 04.7.2 Cost-Hook: STT-Minuten ────────────────────────────
    try:
        from services.cost_tracker import log_api_cost
        if opened:
            seconds = max(0.0, time.time() - opened)
            minutes = seconds / 60.0
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


def register_audio_handlers(sio):
    @sio.on('start_live_session')
    def handle_start_live_session(data=None, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        mode = 'meeting'  # default for backward compatibility
        if isinstance(data, dict):
            mode = data.get('mode', 'meeting')
        print(f"[DG] start_live_session received (sid={_sid}, mode={mode})")
        _open_deepgram_connection(_sid, mode=mode)

        # FT logging: create ft_call_sessions row (Phase 04.7.1)
        try:
            from flask import session as flask_session
            from database.db import SessionLocal
            from database.models import FtCallSession, User
            import services.live_session as ls

            user_id = flask_session.get('user_id')
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
                print(f"[FT] ft_call_sessions row created id={ft_session_id} market={market}")
        except Exception as _e:
            print(f"[FT] ft_call_sessions insert failed: {_e}")

    @sio.on('stop_live_session')
    def handle_stop_live_session(sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        _close_deepgram_connection(_sid)

    _first_chunk_logged = set()  # Track which sids have logged their first chunk

    @sio.on('audio_chunk')
    def handle_audio_chunk(data, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        if _sid not in _first_chunk_logged:
            _first_chunk_logged.add(_sid)
            print(f"[DG] audio_chunk received (sid={_sid}, bytes={len(data)}, type={type(data).__name__})")
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
        _first_chunk_logged.discard(_sid)
        _close_deepgram_connection(_sid)
