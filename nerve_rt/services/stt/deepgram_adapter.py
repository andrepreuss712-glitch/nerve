"""Deepgram STT adapter using asyncwebsocket (D-03).

Uses client.listen.asyncwebsocket.v("1") — the native asyncio Deepgram client.
This is the CRITICAL difference from the Flask version which uses
client.listen.websocket.v("1") (sync, threading, breaks under eventlet).

Audio is NEVER stored. Ephemeral processing only (D-09).
"""
import asyncio
import logging
from typing import Any

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)

from nerve_rt.services.stt import STTProvider, TranscriptResult, TranscriptCallback

logger = logging.getLogger("nerve_rt.stt.deepgram")


class DeepgramAdapter(STTProvider):
    """Deepgram Nova-2 adapter via asyncwebsocket.

    Adapter-internal config (NOT exposed to interface):
    - model: nova-2
    - smart_format: True for cold_call, False for meeting
    - utterance_end_ms: 1000 for meeting mode only
    - encoding: linear16, sample_rate: 16000
    - endpointing: 900ms
    """

    def __init__(self, api_key: str, sample_rate: int = 16000):
        self._client = DeepgramClient(api_key)
        self._sample_rate = sample_rate

    @property
    def provider_name(self) -> str:
        return "deepgram-nova-2"

    async def connect(
        self,
        mode: str,
        language: str,
        on_transcript: TranscriptCallback,
    ) -> Any:
        """Open async Deepgram WebSocket connection.

        Returns the connection handle (AsyncListenWebSocketClient).
        """
        conn = self._client.listen.asyncwebsocket.v("1")

        # Register transcript callback — wraps Deepgram event into TranscriptResult
        async def _on_message(self_dg, result, **kwargs):
            try:
                alt = result.channel.alternatives[0]
                text = alt.transcript
                if not text:
                    return

                # Extract speaker for meeting mode diarization
                speaker = None
                if mode == "meeting":
                    words = getattr(alt, "words", [])
                    if words:
                        counts: dict[int, int] = {}
                        for w in words:
                            sp = getattr(w, "speaker", None)
                            if sp is not None:
                                counts[sp] = counts.get(sp, 0) + 1
                        if counts:
                            speaker = max(counts, key=counts.get)

                tr = TranscriptResult(
                    text=text,
                    is_final=result.is_final,
                    speaker=speaker,
                    confidence=getattr(alt, "confidence", 0.0),
                    language=language,
                )
                await on_transcript(tr)
            except Exception as e:
                logger.error("[DG] Transcript callback error: %s", e)

        async def _on_error(self_dg, error, **kwargs):
            logger.error("[DG] WebSocket error: %s", error)

        async def _on_close(self_dg, close, **kwargs):
            logger.info("[DG] WebSocket connection closed")

        conn.on(LiveTranscriptionEvents.Transcript, _on_message)
        conn.on(LiveTranscriptionEvents.Error, _on_error)
        conn.on(LiveTranscriptionEvents.Close, _on_close)

        # Build LiveOptions — adapter internals, not interface concerns
        options_dict = {
            "model": "nova-2",
            "language": language,
            "smart_format": (mode != "meeting"),
            "interim_results": True,
            "endpointing": 900,
            "punctuate": True,
            "diarize": (mode == "meeting"),
            "encoding": "linear16",
            "sample_rate": self._sample_rate,
        }
        if mode == "meeting":
            options_dict["utterance_end_ms"] = "1000"

        options = LiveOptions(**options_dict)

        # start() — may or may not be a coroutine depending on SDK version
        # Handle both: if it's awaitable, await it; if it returns bool directly, use it
        # See RESEARCH.md Pitfall 5
        result = conn.start(options)
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            success = await result
        else:
            success = result

        if not success:
            raise RuntimeError("Deepgram async WebSocket connection failed")

        logger.info(
            "[DG] Connected: mode=%s, lang=%s, diarize=%s",
            mode, language, mode == "meeting",
        )
        return conn

    async def send_audio(self, conn: Any, data: bytes) -> None:
        """Send audio chunk to Deepgram. Audio is NEVER stored (D-09).

        conn.send() is synchronous internally (thread-safe queue) but
        we keep the async signature for interface consistency.
        """
        conn.send(data)

    async def close(self, conn: Any) -> None:
        """Close Deepgram connection cleanly.

        Safe to call multiple times — errors are caught and logged.
        """
        try:
            result = conn.finish()
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                await result
        except Exception as e:
            logger.warning("[DG] Close error (non-fatal): %s", e)
