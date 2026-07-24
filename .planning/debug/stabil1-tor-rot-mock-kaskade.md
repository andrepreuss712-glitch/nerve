---
status: fix-applied-awaiting-gate
trigger: "STABIL-1-Tor rot: 21 failed + 58 errors nach claude_client->http_llm_client Rename; Produktionscode gesund (Claudian verifiziert). Universeller Fix: Test-Mock-Helfer retargeten."
created: 2026-07-24
updated: 2026-07-24
---

## Resolution (Fix angewandt 2026-07-24, Verifikation am Tor durch Claudian ausstehend)

Universeller Fix auf 13 Test-Dateien angewandt (nur `tests/`, 46 Insertions, 0 Deletions, KEIN
Produktionscode). Commits `dbf87d5` (Pattern A) + `f851cb6` (Pattern B).

- **Pattern A (MagicMock):** 28 Stellen `<mock>.with_options.return_value = <mock>` in
  test_outcome_service (7), test_08_20_3 (3), test_precall_schema (1), test_adoption_runner (4),
  test_qa_pipeline (4), test_phase_classifier (4), test_heiler_resolved (1),
  test_ewb_autovar_global_regression (1), test_judge_runner (3, via ALSO-CHECK gefunden).
- **Pattern B (_FakeClient-Klassen):** `def with_options(self,*a,**k): return self` in
  test_medium_lane_intent_event_live, test_qa_pipeline_rueckfrage (2 Klassen),
  test_anon_live_vs_stored, test_08_5_05_training_pipeline_t2 (2 Klassen).
- `test_stabil1_http_llm_timeout.py` unberührt (war bereits korrekt = Vorbild).

AST-Parse aller 13 Dateien grün (Vorabsignal). **HART: kein lokales pytest gelaufen.**
Verbindliches Tor = `deploy.sh production` (Claudian). Bei Rest-Rot → hier reopnen.

## Current Focus
- hypothesis: Universeller Mock-Retarget behebt FAILED + ERRORs ohne Produktionscode-Änderung
- next_action: ANHALTEN — Claudian fährt das Tor. Bei Rest-Rot Session reopnen + neu bewerten.

# Debug: STABIL-1 Tor ROT — Test-Kaskade nach claude_client → http_llm_client Rename

## Root Cause (Claudian-diagnostiziert, DIALOG-GSD-CLAUDIAN.md Commit 8f8a2cb)

Plan 01 hat 15 HTTP-Call-Sites von `claude_client.messages.create(...)` auf
`http_llm_client().messages.create(...)` umgestellt. `http_llm_client()` gibt
`claude_client.with_options(timeout, max_retries)` zurück. Jeder Test, der `claude_client`
durch ein MagicMock ersetzt, bekommt aus `mock.with_options(...)` ein **frisches,
unkonfiguriertes** MagicMock → `.messages.create()` liefert ein nacktes MagicMock statt der
konfigurierten Antwort → (a) 21 FAILED Assertions; (b) nacktes MagicMock fließt in DB-/Cost-Log-
Write → `_baseline_cleanup_guard` (conftest.py:642 json.dumps) verschluckt sich → Wächter
vergiftet → 58 ERRORs kaskadieren über fremde Tests. **Produktionscode gesund — reine Test-
Contract-Breakage. Kein Code-Rückbau.**

## Universeller Fix (mechanisch, sicher, idempotent)

- **MagicMock-Mock-Helfer:** `<mock>.with_options.return_value = <mock>` an der Mock-Config-Stelle.
- **`_FakeClient`-Custom-Klassen:** Methode `def with_options(self, *a, **k): return self`.

Angewandt auf ALLE `claude_client`-Mock-Helfer (14 Test-Dateien; `test_stabil1_http_llm_timeout.py`
ist bereits korrekt = Vorbild). HART: kein lokales pytest — GSD editiert, Claudian fährt das Tor.

## Current Focus
- hypothesis: Universeller Mock-Retarget behebt FAILED + ERRORs ohne Produktionscode-Änderung
- next_action: Fix auf alle claude_client-Mock-Helfer anwenden, committen, ANHALTEN (Claudian testet)
