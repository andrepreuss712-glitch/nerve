"""LLM Provider abstraction layer (D-04).

The interface is provider-agnostic. Claude-specific features like
cache_control, system prompt format, and model names are adapter internals.

Shadow Mode: When enabled, ShadowLogger orchestrates parallel calls to
primary + shadow providers. Shadow failures never affect user experience.
"""
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class AnalysisInput:
    """Standardized input for LLM analysis."""
    text: str                    # Current transcript segment
    context: str                 # Previous conversation context
    profile_data: dict           # Active profile (einwaende, phasen, gegenargumente, etc.)
    session_mode: str            # 'cold_call' | 'meeting'
    system_prompt: str = ""      # Full system prompt (built by caller)


@dataclass
class AnalysisResult:
    """Standardized output from LLM analysis."""
    raw: dict                    # Full parsed JSON from provider
    einwand: bool = False
    typ: Optional[str] = None
    intensitaet: Optional[str] = None
    gegenargument_1: Optional[str] = None
    gegenargument_2: Optional[str] = None
    notiz: Optional[str] = None
    # Phase 04.8 score signals
    einwand_geloest: bool = False
    detailfrage: bool = False
    budget_erwaehnt: bool = False
    naechster_schritt: bool = False
    zustimmung: bool = False
    konkurrenz: bool = False
    # Metadata
    model_id: str = ""
    latency_ms: float = 0.0


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Lifecycle:
    1. Instantiate with API key/config
    2. analyse(input) -> AnalysisResult (repeated per segment)

    Adapter internals: model name, temperature, max_tokens, prompt format,
    caching strategy -- all belong inside the adapter.
    """

    @abstractmethod
    async def analyse(self, input: AnalysisInput) -> AnalysisResult:
        """Analyse transcript segment. Returns structured result.

        Must be async (no blocking in asyncio event loop).
        """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Provider identifier for logging (e.g. 'claude-haiku-4-5-20251001')."""
