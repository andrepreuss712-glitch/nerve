"""Claude (Haiku) adapter for LLM analysis (D-04).

Uses anthropic.AsyncAnthropic -- the async client that does NOT block
the asyncio event loop (unlike sync anthropic.Anthropic).

MUST use claude-haiku-4-5-20251001 for live analysis (CLAUDE.md rule:
"Nur Haiku fuer Live-Loop, Sonnet nur Post-Call").
"""
import json
import time
import logging
from typing import Optional

import anthropic

from nerve_rt.services.llm import LLMProvider, AnalysisInput, AnalysisResult

logger = logging.getLogger("nerve_rt.llm.claude")


class ClaudeAdapter(LLMProvider):
    """Claude Haiku adapter for real-time analysis."""

    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 2000
    TEMPERATURE = 0.2

    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def model_id(self) -> str:
        return self.MODEL

    async def analyse(self, input: AnalysisInput) -> AnalysisResult:
        """Call Claude Haiku for objection detection and coaching.

        Replicates the exact prompt and parsing from claude_service.py
        analysiere_mit_claude(), but uses the async client.
        """
        t0 = time.monotonic()

        user_prompt = (
            f"Neues Segment:\n{input.text}\n\n"
            f"Bisheriger Gespraechskontext:\n{input.context}"
        )

        try:
            msg = await self._client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=[{
                    "type": "text",
                    "text": input.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": user_prompt}],
                temperature=self.TEMPERATURE,
            )

            latency_ms = (time.monotonic() - t0) * 1000
            raw_text = msg.content[0].text.strip()

            # Parse JSON -- same logic as claude_service.py _parse_json()
            parsed = self._parse_json(raw_text)

            return AnalysisResult(
                raw=parsed,
                einwand=parsed.get("einwand", False),
                typ=parsed.get("typ"),
                intensitaet=parsed.get("intensitaet"),
                gegenargument_1=parsed.get("gegenargument_1"),
                gegenargument_2=parsed.get("gegenargument_2"),
                notiz=parsed.get("notiz"),
                einwand_geloest=parsed.get("einwand_geloest", False),
                detailfrage=parsed.get("detailfrage", False),
                budget_erwaehnt=parsed.get("budget_erwaehnt", False),
                naechster_schritt=parsed.get("naechster_schritt", False),
                zustimmung=parsed.get("zustimmung", False),
                konkurrenz=parsed.get("konkurrenz", False),
                model_id=self.MODEL,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error("[Claude] Analysis error (%.0fms): %s", latency_ms, e)
            return AnalysisResult(
                raw={"einwand": False, "notiz": f"Fehler: {e}"},
                einwand=False,
                notiz=f"Fehler: {e}",
                model_id=self.MODEL,
                latency_ms=latency_ms,
            )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from Claude response. Handles markdown code blocks."""
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("[Claude] JSON parse failed: %s", text[:100])
            return {"einwand": False, "notiz": "JSON parse error"}
