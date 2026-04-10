"""Shadow Mode orchestrator and comparison logger (D-04, D-05).

Shadow Mode runs both primary and shadow providers on identical input.
Only primary result is shown to user. Both results are logged for comparison.
Shadow failures are ALWAYS silent (never affect user experience).

IMPORTANT (D-05): The fine-tuned model will be trained on REAL USER DATA:
- Which EWB button the user clicked (ground truth for objection detection)
- Whether readiness score changed after intervention
- Which hints the user acted on
- Session outcomes

Claude outputs are logged for COMPARISON ONLY, never as training targets.
This prevents the fine-tuned model from imitating Claude -- it learns from
actual user behavior.
"""
import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Optional, List

from nerve_rt.services.llm import LLMProvider, AnalysisInput, AnalysisResult

logger = logging.getLogger("nerve_rt.llm.shadow")


@dataclass
class ShadowComparison:
    """Single A/B comparison record."""
    session_id: str
    input_hash: str                     # SHA256[:16] of input text (no raw text stored)
    primary_model: str
    shadow_model: Optional[str]
    primary_output: dict
    shadow_output: Optional[dict]
    latency_primary_ms: float
    latency_shadow_ms: Optional[float]
    timestamp: float                    # time.time()
    # D-05: User action fields (filled later by session manager)
    user_ewb_click: Optional[str] = None
    readiness_delta: Optional[int] = None
    hint_acted_on: Optional[bool] = None


class ShadowLogger:
    """Orchestrates primary + shadow LLM calls and logs comparisons.

    Usage:
        shadow = ShadowLogger(primary=claude_adapter, shadow=None)  # no shadow yet
        result = await shadow.analyse(session_id, input)
        # result is ALWAYS from primary provider

    When shadow is set:
        shadow = ShadowLogger(primary=claude_adapter, shadow=finetuned_adapter)
        result = await shadow.analyse(session_id, input)
        # Both run in parallel, only primary result returned
        # Comparison logged to self.comparisons
    """

    def __init__(
        self,
        primary: LLMProvider,
        shadow: Optional[LLMProvider] = None,
        enabled: bool = True,
    ):
        self.primary = primary
        self.shadow = shadow
        self.enabled = enabled and shadow is not None
        self.comparisons: List[ShadowComparison] = []
        self._max_comparisons = 1000  # Ring buffer to prevent memory growth

    async def analyse(self, session_id: str, input: AnalysisInput) -> AnalysisResult:
        """Run analysis with optional shadow comparison.

        ALWAYS returns primary result. Shadow is fire-and-forget.
        Shadow exceptions are caught and logged -- never propagated.
        """
        if not self.enabled or self.shadow is None:
            # No shadow -- just run primary
            return await self.primary.analyse(input)

        # Run both in parallel
        primary_task = asyncio.create_task(self.primary.analyse(input))
        shadow_task = asyncio.create_task(self._safe_shadow(input))

        # Wait for primary (blocking) -- shadow can finish later
        primary_result = await primary_task

        # Fire-and-forget shadow logging
        asyncio.create_task(self._log_comparison(
            session_id, input, primary_result, shadow_task
        ))

        return primary_result

    async def _safe_shadow(self, input: AnalysisInput) -> Optional[AnalysisResult]:
        """Run shadow provider. NEVER raises -- returns None on any error."""
        try:
            return await self.shadow.analyse(input)
        except Exception as e:
            logger.warning("[Shadow] Provider error (silent): %s", e)
            return None

    async def _log_comparison(
        self,
        session_id: str,
        input: AnalysisInput,
        primary_result: AnalysisResult,
        shadow_task: asyncio.Task,
    ):
        """Log A/B comparison after both providers complete."""
        try:
            shadow_result = await shadow_task
            input_hash = hashlib.sha256(input.text.encode()).hexdigest()[:16]

            comparison = ShadowComparison(
                session_id=session_id,
                input_hash=input_hash,
                primary_model=primary_result.model_id,
                shadow_model=shadow_result.model_id if shadow_result else None,
                primary_output=primary_result.raw,
                shadow_output=shadow_result.raw if shadow_result else None,
                latency_primary_ms=primary_result.latency_ms,
                latency_shadow_ms=shadow_result.latency_ms if shadow_result else None,
                timestamp=time.time(),
            )

            self.comparisons.append(comparison)
            # Ring buffer -- drop oldest when full
            if len(self.comparisons) > self._max_comparisons:
                self.comparisons = self.comparisons[-self._max_comparisons:]

            if shadow_result:
                logger.info(
                    "[Shadow] Comparison logged: primary=%s (%.0fms) vs shadow=%s (%.0fms)",
                    primary_result.model_id,
                    primary_result.latency_ms,
                    shadow_result.model_id,
                    shadow_result.latency_ms,
                )
            else:
                logger.info(
                    "[Shadow] Comparison logged: primary=%s (%.0fms) vs shadow=FAILED",
                    primary_result.model_id,
                    primary_result.latency_ms,
                )
        except Exception as e:
            logger.warning("[Shadow] Comparison log error (non-fatal): %s", e)

    def update_user_action(
        self,
        session_id: str,
        ewb_click: Optional[str] = None,
        readiness_delta: Optional[int] = None,
        hint_acted_on: Optional[bool] = None,
    ):
        """Attach user action data to the most recent comparison for this session (D-05).

        Called by session manager when user clicks EWB button, score changes, etc.
        This is the GROUND TRUTH data that the fine-tuned model will train on.
        """
        for comp in reversed(self.comparisons):
            if comp.session_id == session_id:
                if ewb_click is not None:
                    comp.user_ewb_click = ewb_click
                if readiness_delta is not None:
                    comp.readiness_delta = readiness_delta
                if hint_acted_on is not None:
                    comp.hint_acted_on = hint_acted_on
                break

    def get_comparisons(self, session_id: str) -> List[ShadowComparison]:
        """Get all comparisons for a session (for post-session analysis)."""
        return [c for c in self.comparisons if c.session_id == session_id]

    def flush_session(self, session_id: str) -> List[ShadowComparison]:
        """Remove and return all comparisons for a session (for DB persistence at session end)."""
        session_comps = [c for c in self.comparisons if c.session_id == session_id]
        self.comparisons = [c for c in self.comparisons if c.session_id != session_id]
        return session_comps
