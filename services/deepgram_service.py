import threading
import time
from datetime import datetime
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import pyaudio
from config import DEEPGRAM_API_KEY, SAMPLE_RATE, CHUNK_SIZE, MERGE_WINDOW_S
import services.live_session as ls


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
                                    'speaker': emit_speaker, 'line_id': line_id})
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
            from extensions import socketio as sio2
            sio2.emit('transcript', {'type': 'interim', 'text': text})
    except Exception as e:
        print(f"[DG] Fehler: {e}")


def on_open(self, open, **kwargs):
    print("[DG] Verbunden")


def on_error(self, error, **kwargs):
    print(f"[DG] Error: {error}")


def deepgram_starten():
    client     = DeepgramClient(DEEPGRAM_API_KEY)
    connection = client.listen.websocket.v("1")
    connection.on(LiveTranscriptionEvents.Transcript, on_message)
    connection.on(LiveTranscriptionEvents.Open,       on_open)
    connection.on(LiveTranscriptionEvents.Error,      on_error)
    options = LiveOptions(
        model="nova-2",
        language="de",
        smart_format=True,
        interim_results=True,
        endpointing=900,
        punctuate=True,
        diarize=True,
        encoding="linear16",
        sample_rate=SAMPLE_RATE,
    )
    connection.start(options)
    pa     = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, frames_per_buffer=CHUNK_SIZE
    )
    print("[Audio] Mikrofon gestartet – sprechen!")
    try:
        while True:
            daten = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            connection.send(daten)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
        connection.finish()
