import re
import threading
import time
import statistics as _stats_wc  # Phase 08.23.2.D - Rolling-10s-Score
from datetime import datetime
from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions
from config import DEEPGRAM_API_KEY, DEEPGRAM_HOST, SAMPLE_RATE, MERGE_WINDOW_S
import services.live_session as ls
import time as _time_mod

# Phase 08.23.2.D REQ-D-7 - Hysterese-Schwellen
_AUDIO_WARN_TRIGGER_BELOW = 0.70  # Score faellt unter -> emit warning
_AUDIO_WARN_RESET_ABOVE   = 0.80  # Score steigt ueber -> Hysterese reset
_ROLLING_WINDOW_MS        = 10_000

# ── Per-session Deepgram connections ──────────────────────────────────────────
_deepgram_sessions = {}        # {sid: connection}
# _session_modes geloescht TAXO1-07: cold_call/meeting-Modus-Quelle ist per-SID
# _session_state[sid]['mode'] (Call-Start-only, kein Live-Toggle). Alle Reads per-SID.
_cost_opened_at = {}           # {sid: float} — Phase 04.7.2 STT-minute tracking (kept for clean dict)
_stt_seconds_accumulated = {}  # {sid: float} — H-9: echte STT-Sekunden, nicht Socket-Lifetime
_sessions_lock = threading.Lock()
_send_fail_counts = {}         # {sid: int} — Fehl-Sendungen pro Session (per-sid gekeyt, Punkt 28)


def _send_audio_chunk(sid, connection, data, chunk_no=None):
    """Sendet einen Ton-Brocken und macht ein STILLES Scheitern sichtbar.

    Das SDK wirft bei toter Verbindung nicht, es gibt False zurueck
    (abstract_sync_websocket.py:387-447) — ohne Auswertung verschwinden Brocken lautlos.
    NUR Logging, KEIN Wiederaufbau (bewusst spaetere Phase).
    Rueckgabe: True wenn gesendet, sonst False.
    """
    try:
        ok = connection.send(data)
    except Exception as e:
        print(f"[DG] Send error (sid={sid}): {e}")
        return False
    if ok is False:
        n = _send_fail_counts.get(sid, 0) + 1
        _send_fail_counts[sid] = n
        # Log-Flut vermeiden: erste Fehl-Sendung pro sid, danach jede 100.
        if n == 1 or n % 100 == 0:
            print(f"[DG] Send fehlgeschlagen — Verbindung tot? "
                  f"(sid={sid}, chunk=#{chunk_no}, fehl_sendungen={n})")
        return False
    return True


def _rolling_10s_score(buffer, now_ms):
    """Phase 08.23.2.D D-06c - Rolling-10s-Score aus Word-Confidence-Buffer.
    Returns 1.0 wenn Buffer leer (defensive - keine Warnung bei Stille)."""
    cutoff = now_ms - _ROLLING_WINDOW_MS
    recent = [c for ts, c in buffer if ts >= cutoff]
    return _stats_wc.mean(recent) if recent else 1.0


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


def _make_on_message(sid, mode='meeting'):
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
            if ls.get_sid_paused(sid):
                return

            if result.is_final:
                speaker = ls.stabilize_speaker(sid, _get_speaker(result))
                line_id = ls.next_line_id(sid)
                ts      = datetime.now().strftime('%H:%M:%S')

                # Zweiter Sprecher gesehen? (PERSID Plan 06 Familie E: per-SID)
                with ls._session_state_lock:
                    _sp_ss = ls._session_state.get(sid)
                    if _sp_ss is not None:
                        if speaker == 1:
                            _sp_ss['_second_sp_seen'] = True
                        roles_confirmed = _sp_ss.get('_second_sp_seen', False)
                    else:
                        roles_confirmed = False

                # Sprecher-Fallback fuer Log (PERSID Plan 06 Familie E: per-SID)
                with ls._session_state_lock:
                    _sp_ss2 = ls._session_state.get(sid)
                    if _sp_ss2 is not None:
                        if speaker is not None:
                            _sp_ss2['_log_last_sp'] = speaker
                        log_sp = speaker if speaker is not None else _sp_ss2.get('_log_last_sp')
                    else:
                        log_sp = speaker  # Ghost-SID: kein Fallback-Wert

                if mode == 'cold_call':
                    # Cold-Call ist Single-Speaker: immer der Berater (diarize=False -> keine .speaker-Attribute).
                    sp_label        = 'Berater'
                    emit_speaker    = 0
                    log_sp          = 0
                    roles_confirmed = True       # damit Persist (unten) speaker=0 schreibt statt None
                elif roles_confirmed:
                    sp_label     = 'Berater' if log_sp == 0 else ('Kunde' if log_sp == 1 else 'Unbekannt')
                    emit_speaker = speaker
                else:
                    sp_label     = 'Unbekannt'
                    emit_speaker = None

                print(f"[DG] [{sp_label}] {text}")
                sio.emit('transcript', {'type': 'final', 'text': text,
                                        'speaker': emit_speaker, 'line_id': line_id},
                         room=sid)
                # ── TAXO1-Welle 4 (Task 3c): MOMENT-FENSTER Schliesser (I-4-FOLD §5) ──
                # Meeting=Berater spricht wieder (Sprecher-Wechsel zum Berater) -> das
                # Einwand-Fenster schliesst; der naechste Kunden-Einwand oeffnet ein neues.
                # NUR meeting + FINALISIERT (kein Flackern). Cold-Call ist Single-Speaker
                # (immer Berater) -> HIER NICHT schliessen (sonst schloesse jede Zeile);
                # Cold-Call nutzt das "Berater-antwortet"-Signal (claude Task 2 c2).
                # Sprecher-Detection NUR GELESEN (sp_label), NICHT veraendert (T-TAXO1-12).
                if mode == 'meeting' and sp_label == 'Berater':
                    with ls._session_state_lock:
                        ls.close_moment(sid, reason='advisor_spoke')
                # D-06: Du/Sie detection heuristic (2-trigger threshold per utterance)
                _check_anrede_switch(sio, sid, text, ls)
                # Phase 08.23.2.B: INPUT-PFAD Anonymisierung (D-01, Req-7)
                # Pre-Insert-Audit: laeuft unter ls.log_lock; Race-Condition (Ghost-SID) via
                # get_anonymisierer()-None-Return abgefangen; anonymize() handelt None-Cache defensiv.
                # Finding 4: Expliziter Skip bei '[ART9_REDACTED]' und '[ANON_FEHLER]' — verhindert DB-Spam.
                # WR-05 fix: _text_for_analysis tracks anonymized text for merge-queue;
                # None means Art-9/pipeline-error — snippet is excluded from analysis buffers.
                _text_for_analysis = text  # default: raw text (fallback if anonymization unavailable)
                try:
                    from services.anonymization import anonymize, AnonymizationPipelineUnavailable
                    _anon_cache = ls.get_anonymisierer(sid)
                    _anon_result = anonymize(text, _anon_cache)
                    _anon_text, _anon_tier = _anon_result
                    if _anon_text == '[ART9_REDACTED]':
                        # Art-9-Treffer: Snippet nicht persistieren und aus Analyse-Puffer ausschliessen
                        print(f'[ANON] Art-9 erkannt, Transcript-Snippet verworfen (sid={sid!r}, len={len(text)})')
                        _text_for_analysis = None
                    elif _anon_text == '[ANON_FEHLER]':
                        # Pipeline-Fehler: Snippet nicht persistieren (Finding 4 — kein DB-Spam)
                        print(f'[ANON] Pipeline-Fehler, Transcript-Snippet verworfen (sid={sid!r}, len={len(text)})')
                        _text_for_analysis = None
                    else:
                        _text_for_analysis = _anon_text
                        # conversation_log per-SID (PERSID Plan 05, deepgram on_message Writer)
                        with ls._session_state_lock:
                            if sid in ls._session_state:
                                ls._session_state[sid]['conversation_log'].append({
                                    'ts': ts, 'type': 'transcript',
                                    'speaker': log_sp if roles_confirmed else None,
                                    'text': _anon_text, 'data': None,
                                })
                except AnonymizationPipelineUnavailable:
                    # D-08 Kat. A: Pipeline unavailable — kein Insert, Live-Call laeuft weiter
                    print(f'[ANON] Pipeline unavailable, Transcript-Snippet verworfen (sid={sid!r})')
                    _text_for_analysis = None
                except Exception as _anon_err:
                    # Unerwarteter Fehler — Safety: lieber nicht persistieren
                    print(f'[ANON] Unerwarteter Fehler im INPUT-PFAD (sid={sid!r}): {type(_anon_err).__name__}')
                    _text_for_analysis = None

                # ── H-9: akkumuliere echte STT-Sekunden ──────────────────────
                _dur = getattr(getattr(result, 'metadata', None), 'duration', 0.0) or 0.0
                if _dur > 0:
                    with _sessions_lock:
                        _stt_seconds_accumulated[sid] = _stt_seconds_accumulated.get(sid, 0.0) + _dur

                # -- Phase 08.23.2.D - Word-Confidence-Buffer + Hysterese-Warning (REQ-D-7) --
                try:
                    _wc_words = result.channel.alternatives[0].words or []
                except (AttributeError, IndexError):
                    _wc_words = []
                if _wc_words:
                    _now_ms = int(time.time() * 1000)
                    _new_tuples = [(_now_ms, float(w.confidence)) for w in _wc_words if hasattr(w, 'confidence') and w.confidence is not None]
                    _should_emit = False
                    _score_now = 1.0
                    with ls._session_state_lock:
                        _sd = ls._session_state.get(sid)
                        if _sd is not None:
                            _buf = _sd.setdefault('word_confidences', [])
                            _buf.extend(_new_tuples)
                            # Hysterese-Check innerhalb Lock - atomar mit Buffer-Update
                            _score_now = _rolling_10s_score(_buf, _now_ms)
                            _state = _sd.get('state', {})
                            _warn_active = _state.get('audio_warn_active', False)
                            if not _warn_active and _score_now < _AUDIO_WARN_TRIGGER_BELOW:
                                _state['audio_warn_active'] = True
                                _should_emit = True
                            elif _warn_active and _score_now > _AUDIO_WARN_RESET_ABOVE:
                                _state['audio_warn_active'] = False  # Hysterese reset
                    # Emit AUSSERHALB Lock (SocketIO kann blockierend sein)
                    if _should_emit:
                        try:
                            sio.emit('audio_health_warning', {
                                'score': round(_score_now, 3),
                                'window_s': 10,
                            }, room=sid)
                        except Exception as _e_emit:
                            print(f'[AudioHealth] emit Fehler: {_e_emit}')

                if mode == 'cold_call':
                    sp_name = 'Berater'
                elif roles_confirmed:
                    sp_name = 'Berater' if speaker == 0 else ('Kunde' if speaker == 1 else 'Sprecher')
                else:
                    sp_name = 'Sprecher'

                # WR-05 fix: use anonymized text in merge-queue; skip if Art-9/pipeline-error
                # PERSID Plan 04 (S4): _merge_pending pro-SID unter _session_state_lock (EIN Lock).
                # Ghost-SID-Guard: kein Write wenn SID nicht mehr in _session_state (Disconnect-Race).
                if _text_for_analysis is not None:
                    key = str(speaker) if speaker is not None else 'unknown'
                    with ls._session_state_lock:
                        if sid not in ls._session_state:
                            # Ghost-SID: Session bereits beendet, Segment verwerfen
                            pass
                        else:
                            _bucket = ls._session_state[sid].setdefault('_merge_pending', {})
                            if key in _bucket:
                                _bucket[key]['timer'].cancel()
                                _bucket[key]['texts'].append(_text_for_analysis)
                                _bucket[key]['line_id'] = line_id
                            else:
                                _bucket[key] = {
                                    'texts':           [_text_for_analysis],
                                    'line_id':         line_id,
                                    'speaker':         speaker,
                                    'roles_confirmed': roles_confirmed,
                                    'sp_name':         sp_name,
                                    't_start':         time.monotonic(),
                                    'sid':             sid,
                                }
                            # Timer-Args tragen jetzt sid + key (neue _flush_segment-Signatur)
                            t = threading.Timer(MERGE_WINDOW_S, ls._flush_segment, args=[sid, key])
                            t.daemon = True
                            t.start()
                            _bucket[key]['timer'] = t
            else:
                sio.emit('transcript', {'type': 'interim', 'text': text},
                         room=sid)

                # ── BUG-10-LAT Wave 2: Keyword-Match auf Interim-Transcript ──────
                try:
                    # Phase 08.23.2.PIP (Entscheidungs-Update 2026-06-30, André): Im Cold-Call
                    # gibt es KEINE Auto-Erkennung von Einwaenden mehr. NERVE hoert dort nur den
                    # Berater (Single-Speaker) -> eine Keyword-Auto-Reaktion (Slot-0-Profil-
                    # Antwort-Render via keyword_einwand_match + EWB-Knopf-Highlight + ewb_signal)
                    # kann nur auf die EIGENEN Worte des Beraters reagieren = Selbst-Trigger-
                    # Rauschen, nichts Neues. Modell Cold-Call: Berater hoert Einwand -> klickt
                    # Knopf -> liest Antwort. Die Auto-Erkennung lebt NUR im Meeting-Modus (da
                    # hoert NERVE den Kunden). Werkzeug bleibt erhalten, im Cold-Call abgeschaltet.
                    # (analyse_loop/QA emittiert seit PIP.1 ohnehin kein ewb_signal.)
                    if mode == 'cold_call':
                        return
                    # PERSID Plan 03 W-A: mic_muted per-SID top-level lesen (Ghost-SID: False).
                    with ls._session_state_lock:
                        _muted = ls._session_state.get(sid, {}).get('mic_muted', False)
                    if _muted:
                        return
                    _profile_name, _profile_daten = ls.get_profile_for_sid(sid)
                    einwaende = (_profile_daten.get('einwaende_detail') or _profile_daten.get('einwaende') or []) if isinstance(_profile_daten, dict) else []
                    if not einwaende:
                        return
                    matcher = ls.get_matcher(sid)
                    match = matcher.match_with_dedup(text, einwaende, sid=sid)
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

                    # Phase 08.23.2.PIP-01 (Item a, Anzeige-Trennung): Der Auto-Erkenner
                    # schreibt NICHT mehr in die Lese-Zone (slot 1). Frueher feuerte hier
                    # start_background_task(streame_auto_variante, ...) einen parallelen
                    # Haiku-Stream in slot 1 -> ueberschrieb den manuell geklickten Vorschlag
                    # mitten im Vorlesen (Bug B, Wurzel). Jetzt: nur ein Button-Signal an die
                    # EWB-Zone (bekannter Profil-Einwand -> bestehenden Button aufleuchten).
                    # - KEIN Haiku im Live-Highlight-Pfad (Punkt 25 Latenz — ein Highlight
                    #   braucht keine LLM-Antwort).
                    # - KEIN slot1_variant_busy_until-Lock mehr (GLOBAL ls.state-Zugriff
                    #   entfaellt — der Lese-Zonen-Lock ist obsolet, da Auto slot 1 nicht mehr
                    #   beschreibt). live_session.py-Default bleibt als Foundation unberuehrt.
                    # - streame_auto_variante wird damit nicht mehr aufgerufen (PIP.4-Foundation,
                    #   write-only/dormant, inkl. dem self-contained TTFT-Circuit-Breaker —
                    #   grep-belegt 0 externe Produktiv-Reader, MEDIUM #1).
                    # typ = _label (matched_label = das data-typ der gerenderten Profil-Buttons,
                    # gleicher Wert wie im keyword_einwand_match oben), Fallback keyword.
                    # known=True (Profil-Keyword-Treffer -> Button existiert). NIE der Roh-
                    # Transkript-Text, NIE ein Roh-Enum-Wert (Cross-AI HIGH/LOW).
                    _ewb_typ = _label or match.get('keyword', '')
                    if _ewb_typ:
                        sio.emit('ewb_signal', {
                            'typ':    _ewb_typ,
                            'known':  True,
                            'source': 'keyword',
                        }, room=sid)
                        print(f"[PIP-EWB] ewb_signal emit source=keyword sid={sid} typ={_ewb_typ!r} known=True")
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


# Phase 08.23.2.STT — keyterm Layer 2: feste Sales-Grundliste.
# DATEN-Strings (keyterm-Werte) -> echte Umlaute erlaubt (CLAUDE.md User-Data-Regel), KEINE Identifier.
_SALES_KEYTERMS_BASE = [
    "Einwand",
    "Einwandbehandlung",
    "Vorwand",
    "Cold Call",
    "Kaltakquise",
    "Kaufsignal",
    "Kalendereinladung",
    "Vertriebler",
    "Opener",
    "Entscheider",
    "Gatekeeper",
    "Abschluss",
    "Termin",
    "Bedarfsanalyse",
    "Angebot",
    "Nachfassen",
]

MAX_KEYTERMS = 60          # << 500-Token-Cap (Deepgram) mit grossem Sicherheitsabstand
_KEYTERM_MIN_LEN = 4
_STOPWORDS = {"oder", "und", "der", "die", "das", "fuer", "mit", "von", "den", "ein", "eine"}


def build_keyterms(profile_daten: dict, profile_branche: str, mode: str) -> list:
    """Baut die per-Call keyterm-Liste (Layer 2 fix + Layer 3 Profil-Extraktion).
    Reihenfolge = Prioritaet: Grundliste zuerst (gewinnt bei Cap), dann Profil.
    Return: deduplizierte Liste von Strings (jeder String = 1 keyterm, ggf. mehrwortig).
    Niemals persistiert — nur Transkriptions-Hint (DSGVO).

    mode wird in Stufe 1 NICHT im Body genutzt (bewusst durchgereicht fuer kuenftige
    cold_call-vs-meeting-Differenzierung).
    """
    terms = []
    seen = set()   # lowercase-dedup

    def _add(t):
        t = (t or "").strip()
        if len(t) < _KEYTERM_MIN_LEN:
            return
        low = t.lower()
        if low in seen or low in _STOPWORDS:
            return
        if len(terms) >= MAX_KEYTERMS:
            return
        seen.add(low)
        terms.append(t)

    # Layer 2: feste Grundliste zuerst (Prioritaet, gewinnt bei Cap)
    for t in _SALES_KEYTERMS_BASE:
        _add(t)

    if not isinstance(profile_daten, dict):
        profile_daten = {}
    basis = profile_daten.get("basis") if isinstance(profile_daten.get("basis"), dict) else {}

    # Layer 3.1: Branche (DB-Column-Prioritaet, sonst basis.branche)
    _add(profile_branche or basis.get("branche") or "")

    # Layer 3.2: Markenname / Unternehmen
    _add(basis.get("unternehmen") or "")

    # Layer 3.3: Substantive aus Produktbeschreibung (Capitalized-Token-Heuristik fuer Deutsch).
    # Stufe-1-Limitation: zerlegt mehrwortige Komposita ("Sales Flow"->"Sales"+"Flow"); Multi-Word deferred (REVIEW LOW).
    produkt = basis.get("produktbeschreibung") or ""
    for tok in re.findall(r"\b[A-ZÄÖÜ][\wäöüß\-]{3,}\b", produkt)[:10]:
        _add(tok)

    # Layer 3.4: Einwand-Kategorien + Kurzlabels (kurze Domain-Begriffe, KEINE Saetze)
    for e in (profile_daten.get("einwaende_detail") or [])[:20]:
        if isinstance(e, dict):
            _add(e.get("kategorie") or "")
            _add(e.get("kurzlabel") or "")

    return terms


def _open_deepgram_connection(sid, mode='cold_call', keyterms=None):
    # POLISH-49: EU-Host-Override für DSGVO-konforme Audio-Verarbeitung.
    # Standardmäßig `api.eu.deepgram.com` (siehe config.py Default).
    client = DeepgramClient(
        DEEPGRAM_API_KEY,
        config=DeepgramClientOptions(
            url=f"https://{DEEPGRAM_HOST}",
            # Keepalive (SDK 3.10.0 = Prod-Stand): das SDK startet daraufhin in
            # connection.start() selbst einen Hintergrund-Thread, der periodisch KeepAlive
            # schickt. Ohne das schliesst Deepgram nach ~10s ohne eintreffende Audio-Daten
            # mit 1011 "did not receive audio data" — ein kurzer Ton-Stau genuegt
            # (Test-Anruf 27.07., 17:03:42).
            options={"keepalive": "true"},
        ),
    )
    connection = client.listen.websocket.v("1")
    connection.on(LiveTranscriptionEvents.Transcript, _make_on_message(sid, mode))
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
        model="nova-3",
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
    if keyterms:
        # keyterm ist nova-3-only (siehe RESEARCH context7). Liste von Strings;
        # jeder String = 1 (ggf. mehrwortiger) keyterm. SDK serialisiert zu wiederholten Query-Params.
        options_kwargs['keyterm'] = keyterms
    try:
        options = LiveOptions(**options_kwargs)
    except Exception as e:
        # REVIEW HIGH: SDK kennt keyterm-Kwarg evtl. nicht (strikte LiveOptions-Signatur).
        # Fallback: keyterm verwerfen, Call trotzdem mit nova-3 starten (kein harter Crash).
        print(f"[DG] LiveOptions init mit keyterm fehlgeschlagen (SDK-Mismatch?): {e}. Fallback ohne keyterm.")
        options_kwargs.pop('keyterm', None)
        options = LiveOptions(**options_kwargs)
    print(f"[DG] LiveOptions: model=nova-3, diarize={is_meeting}, smart_format=True, keyterm_count={len(options_kwargs.get('keyterm') or [])}")
    connection.start(options)
    with _sessions_lock:
        _deepgram_sessions[sid] = connection
        # _session_modes[sid] = mode  ENTFERNT (TAXO1-07): cold_call/meeting-mode lebt
        # per-SID in _session_state[sid]['mode'] (im Call-Start VOR _open_deepgram_connection
        # gesetzt, FUND 2). Der `mode`-Parameter bleibt lokale Variable fuer diarize/keyterms.
        _cost_opened_at[sid] = time.time()
    print(f"[DG] Session gestartet (sid={sid}, mode={mode}, diarize={is_meeting})")


def _close_deepgram_connection(sid):
    with _sessions_lock:
        connection = _deepgram_sessions.pop(sid, None)
        # _session_modes.pop(sid, None)  ENTFERNT (TAXO1-07): per-SID mode raeumt pop_session_state.
        _cost_opened_at.pop(sid, None)           # Dict sauber halten (H-9: nicht mehr als Basis)
        _send_fail_counts.pop(sid, None)
        stt_sek = _stt_seconds_accumulated.pop(sid, 0.0)  # H-9: echte STT-Sekunden
    # ── H-9 Cost-Hook: echte STT-Sekunden statt Socket-Lifetime ────────
    try:
        from services.cost_tracker import log_api_cost
        minutes = stt_sek / 60.0
        if minutes > 0.01:  # keine Artefakt-Rows fuer Sub-Sekunden
            # KOSTEN-1 R1: Diarization ist bei Deepgram ein ADD-ON (+$0.0020/min), NICHT im
            # Minutenpreis enthalten. Wir schalten sie konditional (`diarize=is_meeting`,
            # :457) -> eigener Modell-String pro Modus, damit der Cold-Call (Mehrheitsfall)
            # nicht pauschal 26% zu teuer gerechnet wird. mode-Quelle EINHEITLICH per-SID
            # (_session_state[sid]['mode'], gesetzt :580); der Bucket lebt hier noch, weil
            # beide Aufrufer erst _close_deepgram_connection und DANN stash_ended_session
            # rufen (:803 / :842). Kein State -> 'cold_call' (dann sind auch keine Minuten da).
            _mode = (ls._session_state.get(sid) or {}).get('mode', 'cold_call')
            _dg_model = 'nova-3-diarize' if _mode == 'meeting' else 'nova-3'
            log_api_cost('deepgram', _dg_model, user_id=None,
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
    @sio.on('connect')
    def handle_connect(sid=None, environ=None, auth=None):
        from flask import request, session as flask_session
        _sid = request.sid if sid is None else sid
        user_id = flask_session.get('user_id')
        if not user_id:
            print(f"[WS-Auth] Unauthorized connect rejected: sid={_sid}")
            return False  # Flask-SocketIO 5.6.1: return False = reject connection
        # Thin stub — only _user_id registered here.
        # init_session_state() called on start_live_session event fills all sub-keys.
        # .setdefault() safely handles SIDs not yet in state — no KeyError risk (MEDIUM-1).
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})['_user_id'] = user_id
        print(f"[WS-Auth] Authenticated connect: sid={_sid} user_id={user_id}")

    @sio.on('start_live_session')
    def handle_start_live_session(data=None, sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        # setdefault race guard: prevent KeyError if vorwissen_level or other events arrive
        # before init_session_state() completes (MEDIUM fix — 08.20 REVIEWS.md)
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})
        mode = 'cold_call'  # default for backward compatibility (D4: sicherere Annahme)
        precall_briefing = None
        if isinstance(data, dict):
            mode = data.get('mode', 'cold_call')
            precall_briefing = data.get('precall_briefing', None)
        print(f"[DG] start_live_session received (sid={_sid}, mode={mode})")

        # FUND 2 (TAXO1-07): mode per-SID VOR _open_deepgram_connection (unten) gesetzt —
        # schliesst das Race-Fenster, in dem on_message-Reads sonst auf den Default fielen
        # (das leere setdefault-dict oben hat KEINEN 'mode'-Key). init_session_state (unten)
        # re-setzt denselben Wert beim wholesale-replace -> konsistent, kein Overwrite.
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})['mode'] = mode

        # Phase 08.23.2.STT: keyterm-Liste VOR Connection-Open ableiten (keyterm ist nova-3-only,
        # muss beim LiveOptions-Build vorliegen). Mini-Profil-Load (nur daten+branche) — der volle
        # per-SID-Init unten (init_session_state/set_profile_for_sid/call-record) bleibt unveraendert.
        # REVIEW MEDIUM (akzeptiert): Diese synchrone SQLAlchemy-Session laeuft im SocketIO-Handler
        # und kann unter Gevent/Eventlet ohne Yield kurz blocken. Bewusst akzeptiert: nur EINMAL pro
        # Call-Start (kein Hot-Path), und der bestehende volle Profil-Load (Z.478-509) macht exakt
        # dasselbe Pattern — also kein NEUES Architektur-Risiko, kein Re-Architecting noetig.
        _kt_daten = {}
        _kt_branche = ''
        try:
            from flask import session as _kt_flask_session
            _kt_user_id = _kt_flask_session.get('user_id')
            from database.db import SessionLocal as _SL_kt
            from database.models import User as _User_kt, Profile as _Profile_kt
            _db_kt = _SL_kt()
            try:
                _u_kt = _db_kt.query(_User_kt).filter_by(id=_kt_user_id).first()
                _pid_kt = getattr(_u_kt, 'active_profile_id', None) if _u_kt else None
                if _pid_kt:
                    _p_kt = _db_kt.query(_Profile_kt).filter_by(id=_pid_kt).first()
                    if _p_kt:
                        _kt_branche = getattr(_p_kt, 'branche', None) or ''   # DB-Column-Prioritaet (kanonisch seit 08.19.1)
                        if _p_kt.daten:
                            import json as _json_kt
                            _kt_daten = _json_kt.loads(_p_kt.daten) if isinstance(_p_kt.daten, str) else (_p_kt.daten or {})
            finally:
                _db_kt.close()
        except Exception as _kt_e:
            print(f"[DG] keyterm-Profil-Load fehlgeschlagen (non-fatal, fallback Grundliste): {_kt_e}")
        _keyterms = build_keyterms(_kt_daten, _kt_branche, mode)

        # CI-2 Race-Close (Plan 02, Mechanik=REORDER): _open_deepgram_connection wird NICHT mehr
        # hier (vor dem per-SID-Init) geoeffnet, sondern ERST NACH create_call_for_sid (unten, nach
        # dem Init-try-Block). Damit ist die durable call_id im per-SID-state, BEVOR die Verbindung
        # steht und on_message-Detection (Fast/Medium/Button-emit) fuer diese sid feuern kann ->
        # kein NULL-call_id-Emit im Start-Fenster, kein verlorener erster Einwand (RESEARCH §3/§4).
        # mode (:530) + _keyterms (oben) sind die EINZIGEN Connection-Open-Inputs und bleiben als
        # Locals im Scope. Single-Owner gewahrt: create_call_for_sid bleibt in start_live_session,
        # NIE im Detection-Thread.

        # Store precall briefing in live session state
        # (ls imported at module level — do not re-import here, causes UnboundLocalError
        # before the setdefault guard above which also uses ls)
        # POLISH-22 / K1: session_start_time wird per-SID gesetzt — und zwar NACH
        # init_session_state() weiter unten (init überschreibt _session_state[sid]
        # und würde einen hier gesetzten Wert wieder auf None zurücksetzen).
        # berater_words/kunde_words werden von init_session_state() auf 0 initialisiert.
        # ── Phase 08 D-14 / PERSID Plan 03 N-4: PreCall-Anrede capturen ────────
        # Whitelist {'du', 'sie'} (lowercase-kanonisch) schuetzt vor Prompt-Injection.
        # CR-02: Raw-Input wird zuerst via strip().lower() normalisiert.
        # N-4: der globale ls.state-Write WIRD ENTFERNT. Das Local `_anrede_local`
        # wird unten NACH init_session_state per-SID geschrieben (Muster :687-690).
        anrede_raw = (data or {}).get('anrede') if isinstance(data, dict) else None
        # Capturen: strip().lower() (lowercase-kanonisch, wie Toggle :827)
        _anrede_local = anrede_raw.strip().lower() if isinstance(anrede_raw, str) else None
        if _anrede_local not in ('du', 'sie'):
            _anrede_local = None
        # N-4-ENTFERNT: globaler ls.state['session_anrede']-Write ist weg.
        # Per-SID-Write erfolgt NACH init_session_state weiter unten.

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
            # truncated above — bridged to _session_state[sid] via set_briefing_for_sid after init_session_state

        # D-09 PERSID Plan 01: aktives_skript_inhalt/skript_bloecke Writer GELOESCHT.
        # Task-1-Verdikt DELETE (0 Prod-Reader belegt, RESEARCH §1, 2026-07-03).
        # Skript-Inhalt war write-only (nie gelesen nach dem Set).

        from flask import session as flask_session
        user_id = flask_session.get('user_id')
        # CR-01 fix: extract market/language from payload with safe defaults
        market   = (data or {}).get('market', 'dach') if isinstance(data, dict) else 'dach'
        language = (data or {}).get('language', 'de')  if isinstance(data, dict) else 'de'

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
            # B1-EXEMPT: re-init folgt sofort (init_session_state :675), kein api_beenden-Read
            # gegen diese sid -> kein Snapshot noetig. RAW-pop bleibt.
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
            # POLISH-22 / K1: per-SID session_start_time auf Call-Start setzen (Zeit-Basis
            # für tempo in get_speech_stats). NACH init_session_state, da init es auf None setzt.
            import time as _time_ss
            with ls._session_state_lock:
                _ss_start = ls._session_state.get(_sid)
                if _ss_start is not None:
                    _ss_start['session_start_time'] = _time_ss.monotonic()
            ls.init_anonymisierer(_sid)   # WR-03 fix: D-06 create AnrufAnonymisierer for this SID
            ls.set_profile_for_sid(_sid, _profile_name2, _profile_daten2)
            # Phase 08.23.2.D.UX.3 Task R5: Firmenname aus Profil vorab in Token-Cache
            # registrieren (loest NERVE->[ORG_A]-Ueberlappung). basis.unternehmen ist
            # ein bestehendes Feld (profile_schema.py:52), kein neues Profilfeld.
            # RAM-only: get_or_assign_token schreibt in cache.mapping, nie DB.
            # Defensiver Dict-Zugriff (Gemini LOW): '.get('unternehmen') or ''' faengt
            # zusaetzlich den Fall ab dass der Key existiert aber Wert explizit None ist
            # (sonst .strip()-AttributeError); '.get('basis') or {}' faengt fehlende Section.
            # Known-Limitation (Gemini MEDIUM, BEWUSST nicht behoben): Exact-String-Match.
            # STT transkribiert Firmennamen oft abgewandelt ('Nerve GmbH' vs Profil 'NERVE')
            # -> GLiNER taggt die Variante dann als neues [ORG_X] statt des Profil-Tokens.
            # KEIN Fuzzy-/phonetisches Matching in dieser Phase (Scope-Creep, kein PII-Leck
            # da die Variante immer noch als irgendein ORG-Token geschwaerzt wird).
            _anon_cache = ls.get_anonymisierer(_sid)
            if _anon_cache and _profile_daten2:
                _firma = ((_profile_daten2.get('basis') or {}).get('unternehmen') or '')
                if isinstance(_firma, str) and _firma.strip():
                    _anon_cache.get_or_assign_token(_firma.strip(), 'ORG')
                    print(f"[ANON] Firmenname aus Profil registriert ({len(_firma.strip())} Zeichen)")
            # BUG1 FIX: bridge precall_briefing from socket payload to _session_state[sid]["_briefing"]
            # Must run AFTER init_session_state (which overwrites _session_state[sid])
            if precall_briefing and isinstance(precall_briefing, str):
                ls.set_briefing_for_sid(_sid, precall_briefing)
                print(f"[DG] PreCall-Briefing bridged to _session_state[sid] ({len(precall_briefing)} Zeichen)")
            # PERSID Plan 03 N-4: Start-Anrede per-SID NACH init_session_state schreiben.
            # Muster analog session_start_time :687-690 / Briefing-Bridge :713-714 — beide
            # MUESSEN nach init sitzen weil init _session_state[sid] neu anlegt.
            # _anrede_local wurde oben gecaptured (strip().lower(), Whitelist 'du'/'sie').
            if _anrede_local in ('du', 'sie'):
                with ls._session_state_lock:
                    if _sid in ls._session_state:
                        ls._session_state[_sid]['session_anrede'] = _anrede_local
                print(f"[Phase08] session_anrede={_anrede_local} set per-sid={_sid} (start, nach init N-4)")
            print(f"[08.19.4] SID {_sid}: profile={_profile_name2!r} pid={_profile_id2} org={_org_id2}")
            # HIGH-3 fix: pre-load profile extras (Opener, FAQ) into session cache
            # build_profile_context() reads from cache — no DB queries in streaming hot path
            if _profile_id2:
                try:
                    ls._load_profile_cache(sid=_sid, user_id=user_id, profile_id=_profile_id2)
                except Exception as _cache_e:
                    print(f"[DG] _load_profile_cache failed (non-fatal): {_cache_e}")
            # Phase 08.23.2.C.R.F: Call-Record anlegen fuer counterpart_switch/counterpart_initial Events (REQ-6)
            # Punkt 14 Control-Flow-Audit: user_id ist gesetzt (handle_connect() rejectet unauthenticated)
            # sio ist per Closure aus register_audio_handlers(sio) verfuegbar
            # call_mode mapping: 'meeting' -> 'meeting_consented', else 'cold_call'
            # DSGVO Single-Speaker: Modus-Toggle ist manuell durch Nutzer — kein auto-detection
            _call_mode_f = 'meeting_consented' if mode == 'meeting' else 'cold_call'
            # Idempotenz-Pruefung im deepgram_service ist nur noch Fast-Path-Optimierung.
            # Die echte atomare Idempotenz-Sicherung sitzt in create_call_for_sid() selbst
            # (Sentinel '__call_pending__' unter _session_state_lock — Cross-AI Review Fix).
            # Dieser Check vermeidet ueberfluessige create_call_for_sid()-Aufrufe bei Reconnect,
            # ist aber NICHT fuer Korrektheit bei Concurrent-Reconnects verantwortlich.
            with ls._session_state_lock:
                _existing_cid_f = ls._session_state.get(_sid, {}).get('state', {}).get('call_id')
            if _existing_cid_f is None:
                # Finding 1.3 (Claudian Pre-Execute): Return-Wert protokollieren.
                # Bei DB-Fehler bleibt call_id None und Skip-Guard greift weiterhin.
                # Sichtbar im Log statt stiller Folge-Fehler.
                _cid_f = ls.create_call_for_sid(_sid, user_id=user_id, call_mode=_call_mode_f)
                if _cid_f is None:
                    print(f'[DG] create_call_for_sid returned None for sid={_sid!r} — '
                          f'counterpart_switch/counterpart_initial events will be skipped on this session')
            else:
                print(f'[DG] Reconnect detected for sid={_sid!r}, existing call_id={_existing_cid_f!r} '
                      f'— skipping create_call_for_sid (fast-path idempotency)')
            # Initial-Sync: die Anzeige im Browser auf die Server-Wahrheit setzen
            # (verhindert "erster Klick wirkt nicht"). Der Browser haelt selbst KEINEN
            # entscheidungsrelevanten Zustand mehr — er zeigt nur, was hier steht.
            # Reiner LESE-Zugriff: der Init-Default kommt aus init_session_state
            # (Ein-Schreiber-Sperre, Waechter 3).
            _init_cp_f = ls.get_counterpart(_sid)
            sio.emit('counterpart_changed',
                     {'counterpart': _init_cp_f, 'call_type': mode,
                      'source': 'session_init'},
                     room=_sid)
        except Exception as _pe:
            print(f"[08.19.4] per-SID init failed for {_sid}: {_pe}")

        # CI-2 Race-Close (Plan 02, REORDER): JETZT — NACH create_call_for_sid (durable call_id im
        # per-SID-state) — die Deepgram-Verbindung oeffnen. Erst ab hier ist Detection (on_message)
        # freigeschaltet; jeder moegliche emit traegt die durable call_id (kein NULL-Start-Fenster).
        # AUDIO-DROP-NOTIZ (Gemini-Review-Fund 2, bewusst akzeptiert): audio_chunk-Events, die feuern
        # bevor die Connection offen ist (_deepgram_sessions[sid] noch None), werden von
        # handle_audio_chunk verworfen -> die ersten ~50–200 ms Audio koennen gedroppt werden.
        # OK: VoIP-Gespraechsanlauf ist i.d.R. Stille/Rauschen, und Detection laeuft ohnehin erst nach
        # offener Connection -> kein Einwand-Verlust. Keine echte Vorwaerts-Abhaengigkeit (mode :530 +
        # _keyterms bleiben als Locals im Scope; der Init-Block haengt NICHT an der STT-Connection).
        _open_deepgram_connection(_sid, mode=mode, keyterms=_keyterms)

    @sio.on('stop_live_session')
    def handle_stop_live_session(sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        print(f"[DG] stop_live_session event received (sid={_sid})")
        _close_deepgram_connection(_sid)
        # B1: stash_ended_session statt raw pop — api_beenden liest via consume_ended_session (N-3)
        # :674 (reconnect re-init) bleibt RAW-pop (B1-EXEMPT).
        ls.stash_ended_session(_sid)

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
        if ls.get_sid_paused(_sid):
            return
        with _sessions_lock:
            connection = _deepgram_sessions.get(_sid)
        if connection:
            _send_audio_chunk(_sid, connection, data, chunk_no=cnt)

    @sio.on('disconnect')
    def handle_disconnect(sid=None):
        from flask import request
        _sid = request.sid if sid is None else sid
        # setdefault race guard: disconnect may fire before start_live_session fully initializes
        # N-1: stash_ended_session hat Leer-Skip — ein leeres {} vom setdefault wird NICHT gestasht.
        with ls._session_state_lock:
            ls._session_state.setdefault(_sid, {})
        print(f"[DG] socket.io disconnect event (sid={_sid})")
        _chunk_counts.pop(_sid, None)
        _close_deepgram_connection(_sid)
        # B1: stash_ended_session statt raw pop — Leer-Skip (N-1) faengt das setdefault-{} ab.
        # first-stash-wins: falls stop_live_session (:779) schon stashte, bleibt sein voller Snapshot.
        ls.stash_ended_session(_sid)

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
        # PERSID Plan 03 W-A: mic_muted per-SID top-level (Ghost-SID-Guard, D-02).
        with ls._session_state_lock:
            if _sid in ls._session_state:
                ls._session_state[_sid]['mic_muted'] = muted
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

        # ── TAXO1-Welle 4 (Task 3b): EWB-Button -> intent_event (ui_asserted) ───
        # SOFORT beim Klick (nicht erst bei Call-Ende). Der Button haengt am AKTUELL
        # OFFENEN Moment (Punkt c: kein line_id-Race) — ist kein Fenster offen, oeffnet
        # get_or_open_moment eines (Button-getriebener Moment erlaubt). Der bestehende
        # ewb_clicks/record_ewb_click-Pfad bleibt (Welle-5 Dual-Write). Lock-Disziplin:
        # eigener _session_state_lock-Block, NICHT mit state_lock genested.
        # mode-Quelle EINHEITLICH mit Medium/Fast: per-SID _session_state[sid]['mode']
        # (TAXO1-07: globales _session_modes geloescht).
        # HINWEIS (COUNTERPART): es gibt ZWEI orthogonale Achsen —
        # _session_state[sid]['mode'] (Anruf-Art/Hoerbarkeit: cold_call vs meeting, Registry,
        # HIER) und state['counterpart'] (Gespraechspartner: gatekeeper vs decision_maker).
        # Seit Phase 08.23.2.COUNTERPART teilen sie KEIN Wort mehr. Nicht vermischen:
        # die Gespraechspartner-Achse wird NICHT ins Register migriert.
        try:
            _btn_mode = (ls._session_state.get(_sid) or {}).get('mode', 'cold_call')
            _btn_iid = None
            _btn_uid = None
            _btn_oid = None
            _btn_phase = None
            _btn_cid = None
            with ls._session_state_lock:
                _btn_sd = ls._session_state.get(_sid) or {}
                _btn_uid = _btn_sd.get('user_id')
                _btn_oid = _btn_sd.get('org_id')
                _btn_st = _btn_sd.get('state')
                if _btn_st is not None:
                    _btn_phase = _btn_st.get('current_phase')
                    # CI-1: durable call_id direkt aus dem gehaltenen _sid-state (reiner Guard).
                    _btn_cid = ls._durable_call_id(_btn_st.get('call_id'))
                    _btn_iid = ls.get_or_open_moment(
                        _sid, mode=_btn_mode, now=time.monotonic())
            # FUND 3 (TAXO1-07): triggering_text = der Knopf-Typ-Label (typ, z.B. 'zu_teuer';
            # KEIN PII). Defensiv durch anonymize_output (belt-and-suspenders, Sentinel->None).
            from services.anonymization import anonymize_output as _anon_out_btn
            _btn_trig = None
            try:
                _btn_trig = _anon_out_btn(typ, ls.get_anonymisierer(_sid))
                if not _btn_trig or _btn_trig in ('[ART9_REDACTED]', '[ANON_FEHLER]'):
                    _btn_trig = None
            except Exception:
                _btn_trig = None
            # Decision 2: speaker_role='kunde' BLEIBT — der Button ist die EINZIGE erlaubte
            # Kunde-Ausnahme im cold_call (Knopf-Druck = der Knopf-Text zaehlt als Kunde-Einwand,
            # source='ui_asserted'). Daher NICHT ueber die Registry (die wuerde cold_call->berater
            # erzwingen und die Ausnahme brechen).
            from services.intent_event_writer import emit_intent_event
            emit_intent_event(
                session_id=_sid, mode=_btn_mode, intent_type='echter_einwand',
                phase=_btn_phase, source='ui_asserted', inference_basis='ui_button',
                confidence=1.0, speaker_role='kunde', speaker_id='local',
                user_id=_btn_uid, org_id=_btn_oid, interaction_id=_btn_iid,
                call_id=_btn_cid,
                triggering_text=_btn_trig,
            )
        except Exception as _btn_emit_e:
            print(f"[PiP] intent_event emit skip (sid={_sid}): {type(_btn_emit_e).__name__}")

        # ── NEU (TAXO1-07 Refinement 1 + FUND 1): markierte EWB-Transcript-Zeile ──────
        # ZUSAETZLICH zum intent_event-Emit oben: EINE conversation_log-Transcript-Zeile,
        # damit der Knopf-Einwand beim Export/Lesen sichtbar UND als Button-Einwand markiert
        # ist. Spiegelt den kanonischen gesprochenen Append (oben im on_message-Pfad).
        # Dies ist die EINZIGE Kunde-Zeile im Cold-Call-Transcript; gesprochene cold_call-
        # Zeilen bleiben Berater. try-except: der Live-Loop crasht nie.
        try:
            from services.anonymization import anonymize as _anonymize_btn
            _anon_cache_btn = ls.get_anonymisierer(_sid)
            _anon_typ, _ = _anonymize_btn(typ, _anon_cache_btn)
            if _anon_typ in ('[ART9_REDACTED]', '[ANON_FEHLER]'):
                # Sentinel -> Zeile NICHT schreiben (kein DB-Spam, wie der gesprochene Pfad).
                # Der intent_event-Emit (oben) BLEIBT trotzdem.
                print(f"[PiP] EWB-Transcript-Zeile verworfen (Anon-Sentinel, sid={_sid})")
            else:
                # speaker=1 (INT) = Kunde-Label — wie der gesprochene Pfad (log_sp). Der
                # Reader (pip-launcher.js:2295 + routes/app_routes.py:47 /api/transcript)
                # mappt INT 0/1/None -> berater/kunde/system. VERIFIZIERT: INT 1 = Kunde.
                # FUND 1: KANONISCHER Marker = `*ewb button*`-Text-Suffix im `text`-Feld
                # (ueberlebt _build_log_content, das transcript-Eintraege NUR aus text+speaker
                # rendert). Das data={'ewb_button':True}-Flag ist NON-load-bearing RAM-only
                # (wird beim Persist verworfen — live_session:988-1020 liest data nur fuer
                # analyse-Eintraege), NICHT der Export-Marker.
                # conversation_log per-SID (EWB button, PERSID Plan 05, deepgram Writer 2)
                with ls._session_state_lock:
                    if _sid in ls._session_state:
                        ls._session_state[_sid]['conversation_log'].append({
                            # Phase 08.23.2.PIP-03 (Bug C, Item e): ts im selben 'HH:MM:SS'-Format
                            # wie die gesprochene Zeile (Z.66) — NICHT float-epoch (time.time()).
                            # Frueher: time.time() -> _ts_to_ms_of_day (app_routes.py:36) macht
                            # str(ts).split(':') ohne ':' -> ValueError -> ts_ms=0; war der erste
                            # Entry ein Knopf (abs=0 -> base=0), ergab eine spaetere gesprochene
                            # Zeile einen unmoeglichen Folge-Timestamp (~17h). Ein Format, kein ts_ms=0.
                            'ts': datetime.now().strftime('%H:%M:%S'), 'type': 'transcript',
                            'speaker': 1,
                            'text': f"{_anon_typ} *ewb button*",
                            'data': {'ewb_button': True},
                        })
        except Exception as _btn_log_e:
            print(f"[PiP] EWB-Transcript-Zeile skip (sid={_sid}): {type(_btn_log_e).__name__}")

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
        kontext = " ".join(ls._session_state.get(_sid, {}).get('analysiert_bisher', [])[-20:])

        from services.claude_service import streame_manual_ewb_variante

        def _run():
            try:
                result = streame_manual_ewb_variante(typ, profile_einwand or {}, kontext, _sid, slot=1)
                if isinstance(result, dict) and result.get('error'):
                    print(f"[PiP] Variante-Fehler (sid={_sid}, typ={typ!r}): {result['error']}")
                _antwort = (result.get('gegenargument_1') or '').strip() or None
                # Phase 08.23.2.B: OUTPUT-PFAD Anonymisierung (D-01, Req-9)
                # anonymize_output() nutzt Cache-Reverse-Lookup (bekannte Namen aus Briefing echoen)
                # einwand_text=typ ist ein Typ-Label ('zu_teuer') — kein Anonymisierungs-Bedarf (D-01)
                # Finding 4: anonymize_output() gibt nie '[ART9_REDACTED]' zurueck — kein Skip-Check noetig.
                if _antwort:
                    # FOLD A-2 / Req 11: gemeinsamer Storage-Anon-Helper (nie roh, nie verloren, geloggt).
                    # Ersetzt den frueheren fail-OPENen Pfad (bei Anon-Fehler blieb _antwort ROH durch) —
                    # Andre-Entscheidung 22.06.: Auto- UND Knopf-Pfad gleich behandeln, nie roh speichern.
                    from services.anonymization import anonymize_for_storage
                    _antwort = anonymize_for_storage(_antwort, _sid)
                try:
                    ls.record_ewb_click(_sid, typ, success=True,
                                        antwort_text=_antwort, einwand_text=typ)
                except Exception as e:
                    print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
                # ── TAXO2-08 (FOLD A): Vorschlag erfassen (Slot B Manueller Knopf) ──
                # Latenz-neutral (Punkt 25): NUR ein RAM-Append. Anon-Vertrag (Plan 09):
                # suggestion_text = _antwort (bereits via anonymize_for_storage gesaeubert,
                # :954). B1: _btn_iid ist via get_or_open_moment (:860) schon gesetzt — KEIN
                # zusaetzlicher Aufruf noetig. try/except: Live-Loop crasht nie.
                try:
                    import config as _cfg_btn
                    ls.record_suggestion_offer(
                        _sid, slot='B', source='manual_button', model=_cfg_btn.MODEL_PIP_VARIANTE,
                        suggestion_text=_antwort, interaction_id=_btn_iid, einwand_typ=typ,
                    )
                except Exception as _btn_cap_e:
                    print(f"[PiP] record_suggestion_offer skip (sid={_sid}): {type(_btn_cap_e).__name__}")
            except Exception as ex:
                print(f"[PiP] manual_ewb variante error (sid={_sid}): {ex}")
                try:
                    ls.record_ewb_click(_sid, typ, success=False, einwand_text=typ)
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
                ls.record_ewb_click(_sid, typ, success=False, einwand_text=typ)
            except Exception as e:
                print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")

    @sio.on('toggle_counterpart')
    def handle_toggle_counterpart(data=None):
        """Phase 08.23.2.COUNTERPART — Gespraechspartner umschalten, SERVER-autoritativ.

        Der Browser sendet einen reinen BEFEHL ohne Wert; der Server berechnet das
        Gegenteil aus SEINEM Zustand und schickt das Ergebnis zurueck. Damit kann der
        Knopf nicht mehr verklemmen: ein verlorenes Echo kostet eine Sekunde falsche
        Anzeige, nie einen toten Knopf. `data` wird bewusst ignoriert.

        Race (RESEARCH F): zwischen 'connect' und 'start_live_session' existiert
        _session_state[sid] OHNE 'state'-Sub-Dict. Ein Write dorthin wuerde von der
        init_session_state-Wholesale-Replace kommentarlos verworfen -> wir lehnen ab
        (ok:False) statt zu schreiben. KEIN setdefault('state', {}) — das war der Bug.
        """
        from flask import request
        sid = request.sid
        _ok = False
        _old_cp = None
        _new_cp = None
        _call_id = None
        _call_type = 'cold_call'
        with ls._session_state_lock:
            _sd = ls._session_state.get(sid)
            st = _sd.get('state') if isinstance(_sd, dict) else None
            if isinstance(st, dict) and 'counterpart' in st:
                _ok = True
                _old_cp = st['counterpart']
                _new_cp = 'decision_maker' if _old_cp == 'gatekeeper' else 'gatekeeper'
                st['counterpart'] = _new_cp
                _call_id = st.get('call_id')
                _call_type = _sd.get('mode', 'cold_call')
                # Reset Hysterese auf neuen Gespraechspartner → Phase 1. current_phase ist
                # kanonisch INT 1-6 (detect_phase/classify_phase/PHASE_BUTTONS); der Label
                # kommt aus dem Phasenmodell. Frueher stand hier ein String-Label →
                # '>' int vs str-Crash in detect_phase (live_bug phase_classify).
                st['current_phase'] = 1
                st['phase_hint_count'] = 0
                st['pending_phase'] = None
                import time as _t
                st['phase_entered_at'] = _t.monotonic()
                # ── TAXO1-Welle 4 (Task 3c b): Downgrade-Schliesser (Gemini-Punkt d) ──
                # Gespraechspartner aendert sich live -> offenen Moment des alten
                # Zustands SOFORT verwerfen. close_moment ist lock-frei, der umgebende
                # _session_state_lock wird gehalten.
                if _new_cp != _old_cp:
                    ls.close_moment(sid, reason='mode_downgrade')
        if not _ok:
            print(f'[COUNTERPART] toggle abgelehnt (kein aktiver Session-State) sid={sid}')
            sio.emit('counterpart_toggle_ack',
                     {'ok': False, 'error': 'no_active_session'}, room=sid)
            return
        print(f'[COUNTERPART] toggle sid={sid} {_old_cp!r} -> {_new_cp!r} call_type={_call_type!r}')
        # D-04a: Skip-Guard — kein INSERT wenn call_id nicht gesetzt (kein aktiver Anruf)
        if _call_id is None:
            print('[COUNTERPART] counterpart_switch: call_id not set, skip event')
        else:
            _db_ms = None
            try:
                from database.db import SessionLocal as _SL_ms
                from database.models import CallEvent as _CE_ms
                import time as _t_ms
                _db_ms = _SL_ms()
                try:
                    _db_ms.add(_CE_ms(
                        call_id=_call_id,
                        event_type='counterpart_switch',
                        event_ts_ms=int(_t_ms.time() * 1000),
                        payload={
                            # Phase 08.23.2.COUNTERPART: Event-Name UND Payload tragen jetzt
                            # dieselben zwei Achsen-Woerter. 'counterpart_switch' ersetzt
                            # 'mode_switch' (Migration 0035, inkl. der Bestandszeilen).
                            'call_type': _call_type,
                            'old_counterpart': _old_cp,
                            'new_counterpart': _new_cp,
                            'timestamp': _t_ms.monotonic(),
                        },
                    ))
                    _db_ms.commit()
                    print(f'[COUNTERPART] counterpart_switch event written: {_old_cp!r} → {_new_cp!r}')
                finally:
                    _db_ms.close()
            except Exception as _ms_err:
                if _db_ms is not None:
                    _db_ms.rollback()
                print(f'[COUNTERPART] counterpart_switch persist Fehler (non-fatal): '
                      f'{type(_ms_err).__name__}: {_ms_err}')
        sio.emit('counterpart_changed',
                 {'counterpart': _new_cp, 'call_type': _call_type, 'source': 'manual'}, room=sid)
        sio.emit('counterpart_toggle_ack', {'ok': True}, room=sid)
