"""STT Provider abstraction layer (D-03).

The interface is provider-agnostic. Deepgram-specific features like
smart_format, utterance_end_ms are adapter internals, NOT interface methods.

Supported patterns:
- Streaming (Deepgram): connect() opens persistent WS, send_audio() streams chunks
- Batch-with-VAD (faster-whisper, future): connect() may be no-op, send_audio()
  buffers internally and calls on_transcript when VAD detects utterance end
"""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    """Standardized transcript output from any STT provider."""
    text: str
    is_final: bool
    speaker: Optional[int] = None  # None if no diarization
    confidence: float = 0.0
    language: str = "de"


# Type alias for transcript callback
TranscriptCallback = Callable[[TranscriptResult], Awaitable[None]]


class STTProvider(ABC):
    """Abstract interface for Speech-to-Text providers.

    Lifecycle:
    1. connect(mode, language, on_transcript) -> connection handle
    2. send_audio(conn, data) -> streams audio bytes (repeated)
    3. close(conn) -> clean shutdown

    IMPORTANT: Adapter internals (smart_format, utterance_end_ms, model name)
    belong inside the adapter, NOT in this interface.
    """

    @abstractmethod
    async def connect(
        self,
        mode: str,
        language: str,
        on_transcript: TranscriptCallback,
    ) -> Any:
        """Open STT connection. Returns opaque connection handle.

        Args:
            mode: 'cold_call' (single speaker) or 'meeting' (diarization)
            language: ISO language code (e.g. 'de', 'en')
            on_transcript: async callback invoked for each transcript result
        """

    @abstractmethod
    async def send_audio(self, conn: Any, data: bytes) -> None:
        """Send audio chunk to STT provider. Audio is NEVER stored (D-09)."""

    @abstractmethod
    async def close(self, conn: Any) -> None:
        """Close STT connection cleanly. Must be safe to call multiple times."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier for logging (e.g. 'deepgram-nova-2')."""
