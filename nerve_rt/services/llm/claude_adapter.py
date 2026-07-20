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

    def _log_cost_async(self, input: AnalysisInput, posten, latency_ms: int) -> None:
        """KOSTEN-1 R3.2 — Kosten-Zeilen schreiben, OHNE den Event-Loop zu blockieren.

        Feuern und vergessen: der Aufrufer wartet nicht. Ein Kosten-Log darf eine
        Live-Antwort niemals verzoegern (Punkt 25) und niemals brechen (`log_api_cost`
        raist ohnehin nie, cost_tracker.py:91/142).

        Modell-String ist `self.MODEL` = die Voll-ID; deren Raten hat Plan 01 auf die
        echten 4.5-Preise korrigiert (sie standen 4x zu niedrig).
        """
        def _sync() -> None:
            try:
                from database.db import SessionLocal
                from services.cost_tracker import log_api_cost, resolve_org_id_from_user

                org_id = None
                if input.user_id:
                    db = SessionLocal()
                    try:
                        org_id = resolve_org_id_from_user(db, input.user_id)
                    finally:
                        try:
                            db.close()
                        except Exception:
                            pass

                for units, unit_type in posten:
                    if units > 0:
                        log_api_cost("anthropic", self.MODEL,
                                     user_id=input.user_id, org_id=org_id,
                                     units=units, unit_type=unit_type,
                                     session_id=str(input.session_id or "") or None,
                                     context_tag="live_rt", latency_ms=latency_ms,
                                     call_site="nerve_rt.claude_adapter")
            except Exception as e:
                logger.error("[Cost] nerve_rt LLM-Log fehlgeschlagen: %s", e)

        try:
            import asyncio
            asyncio.get_running_loop().run_in_executor(None, _sync)
        except Exception as e:  # pragma: no cover - defensiv
            logger.error("[Cost] nerve_rt LLM-Log nicht startbar: %s", e)

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

            # ── KOSTEN-1 R3.2 Cost-Hook ──────────────────────────────────────────────
            # `msg.usage` wurde hier bisher NIRGENDS gelesen — die Live-LLM-Kosten von
            # nerve_rt existierten schlicht nicht.
            #
            # ★ LATENZ (Punkt 25, HART): `analyse()` ist die schnelle Live-Bahn. Der
            #   Kosten-Log macht einen DB-Roundtrip und ist synchron — direkt aufgerufen
            #   wuerde er den Event-Loop blockieren und damit ALLE parallelen Sessions
            #   dieses Prozesses bremsen. Deshalb: Werte hier auslesen (Mikrosekunden,
            #   reines Attribut-Lesen) und das Schreiben per `run_in_executor` in einen
            #   Thread geben. Der Antwort-Pfad darunter wartet NICHT darauf.
            # POSITION: nach der Latenz-Messung, VOR dem Parsen — `msg.content[0]` und
            #   `_parse_json` koennen werfen; bezahlt ist der Call dann trotzdem.
            try:
                _u = getattr(msg, "usage", None)
                if _u is not None:
                    _posten = [
                        ((getattr(_u, "input_tokens", 0) or 0) / 1000.0, "per_1k_input_tokens"),
                        ((getattr(_u, "output_tokens", 0) or 0) / 1000.0, "per_1k_output_tokens"),
                        ((getattr(_u, "cache_read_input_tokens", 0) or 0) / 1000.0, "per_1k_cache_read_tokens"),
                        ((getattr(_u, "cache_creation_input_tokens", 0) or 0) / 1000.0, "per_1k_cache_write_tokens"),
                    ]
                    self._log_cost_async(input, _posten, int(latency_ms))
            except Exception as _e:
                logger.warning("[Cost] nerve_rt LLM-Hook uebersprungen: %s", _e)
            # ─────────────────────────────────────────────────────────────────────────

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
