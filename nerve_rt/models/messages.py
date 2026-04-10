"""
NERVE Real-Time Engine — WebSocket Message Models

Pydantic models for all message types between browser and engine.
Field names match the existing /api/ergebnis polling payload
(routes/app_routes.py) and live_session.py state dict.
"""

from pydantic import BaseModel
from typing import Optional


class AnalysisUpdate(BaseModel):
    """Engine -> Browser: analysis result push (replaces /api/ergebnis polling)."""
    type: str = "analysis_update"
    version: int
    aktiv: bool
    ergebnis: Optional[dict] = None
    line_id: Optional[str] = None
    kaufbereitschaft: int = 30
    current_phase: int = 1
    current_phase_name: str = "Opener"
    phase_confidence: float = 0.0
    readiness_score: int = 30
    readiness_bucket: str = "cold"
    active_hint: Optional[dict] = None
    ewb_buttons: Optional[list] = None
    cold_call_inference: Optional[dict] = None
    speech_stats: Optional[dict] = None


class TranscriptUpdate(BaseModel):
    """Engine -> Browser: real-time transcript line."""
    type: str = "transcript"
    text: str
    speaker: Optional[int] = None
    speaker_label: str = ""
    line_id: str
    is_final: bool
    timestamp: str


class AudioChunk(BaseModel):
    """Browser -> Engine: raw audio data envelope.

    Note: Actual audio bytes are sent as binary WebSocket frames,
    not inside this JSON model. This model is only used for
    metadata/signaling if needed.
    """
    type: str = "audio_chunk"


class SessionControl(BaseModel):
    """Browser -> Engine: session lifecycle commands."""
    type: str  # "start_session" | "stop_session" | "pause" | "resume"
    session_token: Optional[str] = None


class ErrorMessage(BaseModel):
    """Engine -> Browser: error notification."""
    type: str = "error"
    code: int
    message: str


class StatusUpdate(BaseModel):
    """Engine -> Browser: connection/mic state change."""
    type: str = "status"
    mic_active: bool = False
    stt_connected: bool = False
    engine_ready: bool = False
