---
slug: phase-classify-int-str-fix
created: 2026-06-08
type: quick
---

# Quick Fix: phase_classify '>' int vs str (Live-Bug)

## Problem
Live auf Production (journalctl -u nerve, 8x: 28.5./3.6./5.6.):
`[phase_classify] loop error: '>' not supported between instances of 'int' and 'str'`
→ legt die Phasen-Klassifikation lahm (gefangen im inneren except claude_service.py:1075).

## Root Cause (Quelle, nicht Vergleichsstelle)
`detect_phase` (ki_logik.py:178) macht `raw_phase > current_phase`. `current_phase` ist
kanonisch **INT 1-6** (classify_phase, detect_phase, PHASE_BUTTONS-Keys, alle Reader bei
claude_service.py:992/1061/1085). EINZIGER abweichender Writer:
`deepgram_service.py:902` (handle_manual_mode_toggle) schrieb beim Modus-Wechsel ein
**String-Label** `'opener'`/`'greeting'` statt eines Ints. Danach: `int > 'opener'` → Crash.

`'opener'` (cold_call) und `'greeting'` (gatekeeper) sind die Display-Labels für **Phase 1**
(_PHASE_NAMES_COLD_CALL[1]='opener', _PHASE_NAMES_GATEKEEPER[1]='greeting').

## Fix
deepgram_service.py:902 → `st['current_phase'] = 1` (Reset Hysterese auf Start-Phase,
modus-agnostisch). current_phase ist damit im ganzen Lebenszyklus INT (Single-Source-of-State).
Kein Cast an der Vergleichsstelle (kein Pflaster). Reader unverändert (erwarten alle int).
_session_state ist In-Memory → nach Restart kein Stale-String möglich.

## Scope
NUR dieser Bug. Keine Refactors. 1 Zeile geändert + Kommentar.

## Verify (HART: kein Local-Dev)
1. bash deploy.sh production
2. André: kurzer Test-Call (inkl. manual_mode_toggle, da das der Trigger ist)
3. journalctl -u nerve | grep phase_classify → loop-error weg, stattdessen `[phase_classify] X→Y`
