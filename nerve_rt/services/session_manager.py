"""Session Manager -- per-connection lifecycle for real-time analysis (D-06, D-07).

Replaces Flask's live_session.py globals + claude_service.py analyse_loop threading.
Each WebSocket connection gets a _Session instance with:
- Audio queue (bounded, drops oldest on overflow)
- STT connection (Deepgram asyncwebsocket)
- Transcript buffer (for context window)
- Analysis task (async loop replacing threading.Event.wait)
- WebSocket push (replaces HTTP polling)

NO module-level globals. NO threading.Lock. All state is per-session.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import WebSocket, WebSocketDisconnect

from nerve_rt.services.stt import STTProvider, TranscriptResult
from nerve_rt.services.llm import AnalysisInput
from nerve_rt.services.llm.shadow_logger import ShadowLogger
from nerve_rt.models.messages import AnalysisUpdate, TranscriptUpdate, StatusUpdate
from nerve_rt.redis_bridge import redis_bridge

logger = logging.getLogger("nerve_rt.session")

# Audio queue config
AUDIO_QUEUE_MAX = 100  # Drop oldest chunks when full (Pitfall 1: backpressure)
ANALYSE_INTERVAL_S = 2  # Match Flask ANALYSE_INTERVALL


async def _log_stt_cost(session, stt_conn) -> None:
    """KOSTEN-1 R3.1 — die akkumulierten STT-Sekunden dieser Session als Kosten buchen.

    Bis zu dieser Phase hat `nerve_rt` GAR NICHTS geloggt: weder STT noch LLM. Waere der
    Pfad produktiv gegangen, waeren die Zahlen nicht nachholbar gewesen.

    ★ ERSTE DB-Kopplung in nerve_rt (vorher 0 Treffer fuer cost_tracker/SessionLocal/psycopg).
      Sie ist bewusst DIREKT und nicht ueber die Redis-Bruecke gebaut: `log_api_cost` bringt
      seine eigene `SessionLocal` mit (services/cost_tracker.py:103), und der Dienst laeuft
      laut deploy/nerve-rt.service mit `WorkingDirectory=/opt/nerve/app` und derselben
      `EnvironmentFile=/etc/nerve/.env` wie Flask — also gleicher Import-Pfad, gleiche
      DATABASE_URL. Kein Event-System, keine Bruecke (Fable-STOP-Signal).

    ★ NICHT-BLOCKIEREND (Punkt 25): der Log-Aufruf ist synchron (DB-Roundtrip) und laeuft
      deshalb ueber `run_in_executor` — ein blockierender Aufruf im Event-Loop wuerde alle
      anderen laufenden Sessions dieses Prozesses mit anhalten. Das ist keine Optimierung,
      sondern der Grund, warum der Hook ueberhaupt so aussieht.

    Attribution: `session.user_id` liegt vor; `org_id` nicht — es wird ueber den User
    aufgeloest, sonst faende diese Position im Kunden-Deckungsbeitrag nicht statt.
    `session_id` ist eine RAM-Kennung (`f"{user_id}_{timestamp}"`), KEINE DB-Zeilen-ID —
    sie geht als Text mit, damit die Zeile zuordenbar bleibt (Punkt R4 "Name != Sache").
    """
    try:
        sekunden = float(getattr(stt_conn, "_nerve_stt_seconds", 0.0) or 0.0)
    except Exception:
        sekunden = 0.0
    if sekunden <= 0.6:
        # Keine Rausch-Zeilen fuer Sub-Sekunden (Spiegel deepgram_service.py:495).
        return

    # Diarization ist bei Deepgram ein Add-on (+$0.0020/min) und wird nur im Meeting-Modus
    # eingeschaltet (deepgram_adapter LiveOptions `diarize`) -> eigener Modell-String, damit
    # der Cold-Call nicht pauschal zu teuer gerechnet wird (KOSTEN-1 R1, Option B).
    modell = "nova-3-diarize" if session.mode == "meeting" else "nova-3"

    def _sync_log() -> None:
        try:
            from database.db import SessionLocal
            from services.cost_tracker import log_api_cost, resolve_org_id_from_user

            org_id = None
            db = SessionLocal()
            try:
                org_id = resolve_org_id_from_user(db, session.user_id)
            finally:
                try:
                    db.close()
                except Exception:
                    pass

            log_api_cost("deepgram", modell, user_id=session.user_id, org_id=org_id,
                         units=sekunden / 60.0, unit_type="per_minute",
                         session_id=str(session.session_id), context_tag="stt_rt",
                         call_site="nerve_rt.session_manager")
        except Exception as e:
            # log_api_cost raist nie — ein Fehler HIER waere also der Import oder die DB.
            # Genau der Fall, der sonst spurlos bliebe: laut melden.
            logger.error("[Cost] nerve_rt STT-Log fehlgeschlagen: %s", e)

    try:
        await asyncio.get_running_loop().run_in_executor(None, _sync_log)
    except Exception as e:  # pragma: no cover - defensiv
        logger.error("[Cost] nerve_rt STT-Log konnte nicht ausgefuehrt werden: %s", e)


class _Session:
    """Per-connection session state. Replaces live_session.py globals."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        mode: str,
        profile_id: str,
        profile_data: dict,
        system_prompt: str,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.mode = mode
        self.profile_id = profile_id
        self.profile_data = profile_data
        self.system_prompt = system_prompt

        # State (replaces live_session.state dict)
        self.version = 0
        self.aktiv = False
        self.ergebnis: Optional[dict] = None
        self.line_id: Optional[str] = None
        self.kaufbereitschaft = 30
        self.current_phase = 1
        self.current_phase_name = "Opener"
        self.phase_confidence = 0.0
        self.readiness_score = 30
        self.readiness_bucket = "cold"
        self.active_hint: Optional[dict] = None
        self.ewb_buttons: Optional[list] = None
        self.cold_call_inference: Optional[dict] = None
        self.speech_stats: Optional[dict] = None

        # Buffers (replaces live_session transcript_buffer/analysiert_bisher)
        self.transcript_buffer: list[str] = []
        self.analysiert_bisher: list[str] = []
        self.conversation_log: list[dict] = []
        self._line_counter = 0

        # Audio queue
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=AUDIO_QUEUE_MAX)

        # Control
        self.is_paused = False
        self._running = False

    def next_line_id(self) -> str:
        self._line_counter += 1
        return str(self._line_counter)

    def build_analysis_update(self) -> dict:
        """Build the payload matching /api/ergebnis format."""
        return AnalysisUpdate(
            version=self.version,
            aktiv=self.aktiv,
            ergebnis=self.ergebnis,
            line_id=self.line_id,
            kaufbereitschaft=self.kaufbereitschaft,
            current_phase=self.current_phase,
            current_phase_name=self.current_phase_name,
            phase_confidence=self.phase_confidence,
            readiness_score=self.readiness_score,
            readiness_bucket=self.readiness_bucket,
            active_hint=self.active_hint,
            ewb_buttons=self.ewb_buttons,
            cold_call_inference=self.cold_call_inference,
            speech_stats=self.speech_stats,
        ).model_dump()


class SessionManager:
    """Manages all active real-time sessions."""

    def __init__(self, stt_provider: STTProvider, shadow_logger: ShadowLogger):
        self.stt = stt_provider
        self.llm = shadow_logger
        self._sessions: Dict[str, _Session] = {}

    async def handle_session(self, websocket: WebSocket, session_data: dict):
        """Main session lifecycle -- called after WebSocket accept.

        Runs until WebSocket disconnects or session is stopped.
        Creates three concurrent tasks:
        1. Audio receiver (browser -> audio queue)
        2. STT forwarder (audio queue -> Deepgram)
        3. Analysis loop (transcript buffer -> Claude -> WebSocket push)
        """
        session_id = f"{session_data['user_id']}_{int(time.time())}"
        session = _Session(
            session_id=session_id,
            user_id=session_data["user_id"],
            mode=session_data.get("mode", "meeting"),
            profile_id=session_data.get("profile_id", ""),
            profile_data=session_data.get("profile_data", {}),
            system_prompt=session_data.get("system_prompt", ""),
        )
        session._running = True
        session.aktiv = True
        self._sessions[session_id] = session

        # Connect STT
        stt_conn = None
        try:
            async def on_transcript(result: TranscriptResult):
                await self._handle_transcript(websocket, session, result)

            stt_conn = await self.stt.connect(
                mode=session.mode,
                language=session_data.get("language", "de"),
                on_transcript=on_transcript,
            )

            # Send ready status
            await websocket.send_json(
                StatusUpdate(stt_connected=True, engine_ready=True).model_dump()
            )

            # Run concurrent tasks
            await asyncio.gather(
                self._audio_receiver(websocket, session),
                self._stt_forwarder(session, stt_conn),
                self._analysis_loop(websocket, session),
                return_exceptions=True,
            )
        except WebSocketDisconnect:
            logger.info("[Session %s] WebSocket disconnected", session_id)
        except Exception as e:
            logger.error("[Session %s] Error: %s", session_id, e)
        finally:
            session._running = False
            session.aktiv = False
            if stt_conn:
                # KOSTEN-1 R3.1: Kosten-Flush VOR dem Schliessen — die akkumulierten Sekunden
                # haengen an der Verbindung, und close() darf sie danach mitnehmen.
                await _log_stt_cost(session, stt_conn)
                await self.stt.close(stt_conn)
            # Publish final state to Redis (Flask can read for dashboard)
            await redis_bridge.set_latest_result(
                session.user_id, session.build_analysis_update()
            )
            # Flush shadow comparisons for DB persistence
            self.llm.flush_session(session_id)
            del self._sessions[session_id]
            logger.info("[Session %s] Cleaned up", session_id)

    async def _audio_receiver(self, websocket: WebSocket, session: _Session):
        """Receive audio chunks from browser WebSocket and queue them."""
        try:
            while session._running:
                data = await websocket.receive()
                if "bytes" in data:
                    # Binary frame = audio chunk
                    try:
                        session.audio_queue.put_nowait(data["bytes"])
                    except asyncio.QueueFull:
                        # Drop oldest chunk (backpressure -- Pitfall 1)
                        try:
                            session.audio_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        session.audio_queue.put_nowait(data["bytes"])
                elif "text" in data:
                    # JSON frame = control message
                    msg = json.loads(data["text"])
                    await self._handle_control(websocket, session, msg)
        except WebSocketDisconnect:
            session._running = False

    async def _stt_forwarder(self, session: _Session, stt_conn: Any):
        """Forward audio chunks from queue to STT provider."""
        while session._running:
            try:
                chunk = await asyncio.wait_for(
                    session.audio_queue.get(), timeout=1.0
                )
                if not session.is_paused:
                    await self.stt.send_audio(stt_conn, chunk)
            except asyncio.TimeoutError:
                continue  # Check _running flag

    async def _handle_transcript(
        self,
        websocket: WebSocket,
        session: _Session,
        result: TranscriptResult,
    ):
        """Process incoming transcript from STT and push to browser."""
        if session.is_paused:
            return

        if result.is_final:
            line_id = session.next_line_id()
            ts = datetime.now().strftime("%H:%M:%S")

            # Buffer for analysis context
            session.transcript_buffer.append(result.text)

            # Log for conversation history
            session.conversation_log.append({
                "ts": ts,
                "type": "transcript",
                "speaker": result.speaker,
                "text": result.text,
                "line_id": line_id,
            })

            # Push transcript to browser
            await websocket.send_json(
                TranscriptUpdate(
                    text=result.text,
                    speaker=result.speaker,
                    speaker_label=self._speaker_label(result.speaker, session.mode),
                    line_id=line_id,
                    is_final=True,
                    timestamp=ts,
                ).model_dump()
            )

    async def _analysis_loop(self, websocket: WebSocket, session: _Session):
        """Periodic analysis of buffered transcripts (replaces threading analyse_loop).

        Runs every ANALYSE_INTERVAL_S seconds. Takes unanalysed segments from buffer,
        sends to LLM, pushes result via WebSocket.
        """
        while session._running:
            await asyncio.sleep(ANALYSE_INTERVAL_S)
            if session.is_paused or not session.transcript_buffer:
                continue

            # Grab unanalysed segments
            new_segments = session.transcript_buffer[len(session.analysiert_bisher):]
            if not new_segments:
                continue

            text = " ".join(new_segments)
            kontext = " ".join(session.analysiert_bisher[-20:])
            session.analysiert_bisher.extend(new_segments)

            # LLM analysis (async, non-blocking)
            analysis_input = AnalysisInput(
                text=text,
                context=kontext,
                profile_data=session.profile_data,
                session_mode=session.mode,
                system_prompt=session.system_prompt,
                # KOSTEN-1 R3.2: Attribution fuer den Kosten-Hook im ClaudeAdapter.
                user_id=session.user_id,
                session_id=session.session_id,
            )

            try:
                result = await self.llm.analyse(session.session_id, analysis_input)
            except Exception as e:
                logger.error("[Session %s] LLM error: %s", session.session_id, e)
                continue

            # Update session state
            session.version += 1
            session.ergebnis = result.raw
            session.line_id = (
                session.conversation_log[-1]["line_id"]
                if session.conversation_log
                else None
            )
            session.aktiv = True

            # Push to browser via WebSocket (D-06: replaces HTTP polling)
            try:
                await websocket.send_json(session.build_analysis_update())
            except Exception as e:
                logger.warning("[Session %s] Push failed: %s", session.session_id, e)

            # Publish to Redis for Flask dashboard
            await redis_bridge.publish_result(
                session.user_id, session.build_analysis_update()
            )

    async def _handle_control(
        self, websocket: WebSocket, session: _Session, msg: dict
    ):
        """Handle control messages from browser."""
        msg_type = msg.get("type", "")
        if msg_type == "pause":
            session.is_paused = True
            logger.info("[Session %s] Paused", session.session_id)
        elif msg_type == "resume":
            session.is_paused = False
            logger.info("[Session %s] Resumed", session.session_id)
        elif msg_type == "ewb_click":
            # D-05: Record EWB click as ground truth for shadow comparison
            ewb_type = msg.get("einwand_typ", "")
            self.llm.update_user_action(
                session.session_id, ewb_click=ewb_type
            )
            logger.info("[Session %s] EWB click: %s", session.session_id, ewb_type)
        elif msg_type == "stop_session":
            session._running = False

    @staticmethod
    def _speaker_label(speaker: Optional[int], mode: str) -> str:
        if mode == "cold_call":
            return "Berater"
        if speaker == 0:
            return "Berater"
        elif speaker == 1:
            return "Kunde"
        return ""
