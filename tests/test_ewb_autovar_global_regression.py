"""
tests/test_ewb_autovar_global_regression.py
──────────────────────────────────────────────────────────────────────────
Regression net (Netz-Ratsche) for the streame_auto_variante UnboundLocalError.

Bug (pre-existing since Welle 2, made reachable by Welle 3's per-SID cutover):
  services/claude_service.py streame_auto_variante reads the module-global
  _ewb_fallback_until in the circuit-breaker check and ASSIGNS it later in the
  TTFT-fallback branch. Without `global _ewb_fallback_until` Python binds the
  name function-local for the whole body, so the earlier READ throws
  `UnboundLocalError: cannot access local variable '_ewb_fallback_until'`.

This path had ZERO test coverage, so pytest never caught it — only the live
test-call did. This test drives the function so the circuit-breaker READ runs
(before the assignment) and asserts NO UnboundLocalError. The LLM stream is
mocked to raise immediately (no network); the function's own try/except then
returns a degraded {} — proving the read executed cleanly.
"""

import unittest
from unittest.mock import MagicMock, patch


class TestStreameAutoVarianteGlobalRegression(unittest.TestCase):

    def test_circuit_breaker_read_no_unbound_local(self):
        import services.claude_service as cs

        # Fake anthropic client whose .messages.stream(...) raises immediately,
        # so execution never touches the network. The buggy read at the
        # circuit-breaker check runs BEFORE this call — that is the regression point.
        fake_client = MagicMock()
        fake_client.messages.stream.side_effect = RuntimeError('regression-sentinel-no-network')
        fake_client.with_options.return_value = fake_client

        with patch.object(cs, 'claude_client', fake_client), \
             patch('extensions.socketio', MagicMock()):
            try:
                result = cs.streame_auto_variante(
                    'Das ist viel zu teuer',  # neuer_text
                    [],                       # einwaende
                    '',                       # kontext
                    'sid-ewb-regr',           # sid
                    slot=1,
                    trigger='analyse_loop',
                )
            except UnboundLocalError as e:  # pragma: no cover - this is the failure we guard against
                self.fail(
                    "Regression: streame_auto_variante raised UnboundLocalError on the "
                    f"_ewb_fallback_until circuit-breaker read (missing `global`): {e}"
                )

        # Reaching here proves the circuit-breaker read executed without UnboundLocalError.
        # With the mocked stream raising, the function's own try/except returns {} (degraded).
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()
