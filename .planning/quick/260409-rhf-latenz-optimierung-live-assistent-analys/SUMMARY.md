---
task: 260409-rhf
title: Latenz-Optimierung Live-Assistent
type: quick
completed: 2026-04-09
---

# 260409-rhf: Latenz-Optimierung Live-Assistent

**One-liner:** Reduce live-hint end-to-end latency from 2-3s toward sub-1s by event-driving analyse_loop on Deepgram is_final and converting the client /api/ergebnis poll from setInterval to a self-scheduling setTimeout chain.

## Changes

### Part A — Server (services/deepgram_service.py:41-50)
Fire `ls.analyse_trigger.set()` and `ls.coaching_trigger.set()` immediately on `result.is_final` inside `_make_on_message.on_message`, instead of waiting for the MERGE_WINDOW flush (~1s) or the ANALYSE_INTERVALL fallback (2s). `analyse_trigger` already existed at `services/live_session.py:23`. `Event.set()` is idempotent; `analyse_loop` (services/claude_service.py:671) handles empty-buffer wakes via `if not ls.transcript_buffer: continue`.

### Part B — Client (static/app.js:680-713, :549)
Replaced `setInterval(..., 500)` with a self-scheduling `pollErgebnis()` that re-arms via `setTimeout(pollErgebnis, 500)` in a `finally{}` block, guarded by `window._pollingActive`. `beenden()` sets `window._pollingActive=false` to stop the chain cleanly. Next poll fires only after the previous response is processed — no request pileup under load.

## Latency (worst-case)

| Stage                                    | Before                   | After        |
|------------------------------------------|--------------------------|--------------|
| Deepgram is_final → analyse_trigger      | +0..1000ms (merge window)| ~0ms         |
| analyse_trigger → analyse_loop wakes     | +0..2000ms (fallback)    | ~0ms         |
| Claude Haiku call                        | ~400-600ms               | ~400-600ms   |
| /api/ergebnis poll surface               | +0..500ms + queue bloat  | +0..500ms    |
| **Worst-case total**                     | ~3.5-4s                  | **~0.9-1.1s**|

Primary win: removing the 2s analyse-wake fallback.

## Files modified
- services/deepgram_service.py (+6)
- static/app.js (+12 / -2)

## Commits
- 8e70e32 perf(260409-rhf): wake analyse_loop on Deepgram is_final
- 571012e perf(260409-rhf): convert /api/ergebnis poll to setTimeout chain

## Verification
- Imports clean
- `grep analyse_trigger.set services/deepgram_service.py` → line 46
- `grep setInterval static/app.js` → only unrelated timers (L256, L789, L1339)
- `pytest tests/services/test_ki_logik.py` → 35 passed

## Deviations
None — analyse_trigger already existed.
