---
status: resolved
trigger: "deploy.sh production Gate ROT: 6 failed / 639 passed in tests/test_08_5_03_integration.py nach Welle 3 (per-SID Cutover). Fail-closed, kein Restart, Prod sicher auf Welle 2."
created: 2026-06-17
updated: 2026-06-17
phase: 08.23.2.TAXO1-03
verdict: STALE TEST (kein Produktions-Regress)
---

## Symptome (verbatim, server-seitig reproduziert via triage.sh)
6 failed, 4 passed in tests/test_08_5_03_integration.py:
- TestKwFiredForLineFlag::test_match_hit_sets_kw_fired_for_line — kw_fired_for_line == None, erwartet 'line-42'
- TestAnalyseLoopDispatcher::test_kw_fired_different_calls_classify — classify 0x (erwartet 1x)
- ::test_einwand_unknown_high_conf_emits_slot1 / ::test_frage_faq_match_emits_slot1 /
  ::test_low_confidence_emits_soft_hint / ::test_tabu_filter_triggers_soft_hint — emits == []
Fehlertext: `AssertionError: 'qa_soft_hint' not found in []`.

## Empirische Diagnose (Logging-first, kein Blind-Fix)
1. `_qa_pipeline_dispatch` (claude_service.py:1273) hat seit Welle 3 `if not sid: return` —
   der alte globale else-Fallback wurde als toter Cross-Session-Leak-Pfad GELÖSCHT (§0.1).
   Liest Zustand jetzt aus `_session_state[sid]['state']` (kw_fired_for_line,
   slot1_variant_busy_until, session_anrede), nicht aus dem globalen ls.state.
2. Einziger Live-Aufrufer (claude_service.py:911) gibt IMMER `sid=sid` mit → Live korrekt.
3. `match_with_dedup` (einwand_keyword_matcher.py:221) schreibt kw_fired_for_line per-SID,
   nur mit `sid`. Einziger Live-Aufrufer (deepgram_service.py:219) gibt sid mit → Live korrekt.
4. Die 6 Tests riefen OHNE sid auf + seedeten nur das alte globale `ls.state`.
   → dispatch returnte früh (classify/emit nie) → emits==[]; matcher schrieb nie → kw None.
   Beweis: der EINE Dispatch-Test der schon sid übergibt
   (test_einwand_unknown_passes_profile_data_not_empty) war GRÜN.

**Verdikt: VERALTETE TESTS (alter globaler Vertrag), KEIN Live-Regress.**

## Fix (test-only, Bug-Fix-Disziplin — nur dieser Cluster)
tests/test_08_5_03_integration.py:
- `_make_ls_mock`: per-SID 'state'-Sub-Dict in `_session_state[sid]` geseedet
  (line_id/kw_fired_for_line/slot1_variant_busy_until/session_anrede) wie der Live-Pfad.
- `_build_qa_dispatch_context`: active_sid an _make_ls_mock durchgereicht (Key-Konsistenz).
- Alle dispatch()/match_with_dedup()-Aufrufe reichen `sid` durch.
- test_match_hit asserted jetzt die per-SID-Quelle (nicht das alte globale ls.state).
- Asserts UNVERÄNDERT scharf (classify aufgerufen, qa_slot1/qa_soft_hint emittiert,
  kw gesetzt) — KEIN Bend auf []/None.
- Zusätzlich 2 Tests entschärft, die Welle 3 still zu False-Green machte
  (returnten ohne sid früh): jetzt mit sid → echter per-SID-Pfad geprüft.
KEINE Produktions-Code-Änderung.

## Beweis (voller Lauf, nicht nur die Datei)
`scripts/triage.sh tests/ -m "not live and not perf"` server-seitig gegen nerve_test:
**645 passed, 6 skipped, 5 deselected** (vorher 6 failed/639 passed). Kein Restart, kein Deploy.

## Lerneffekt
Lokaler AST-Parse + grep-Acceptance führt die bestehende Test-Suite NICHT aus → ein
Wave-Cutover, der eine Funktions-Signatur/einen Vertrag ändert (sid-Param, per-SID-Store),
bricht bestehende Tests still. Pre-Deploy nur über `triage.sh tests/`-Vollauf fangbar.
Pflicht für TAXO-Wellen 04-07: vor Handoff `triage.sh tests/ -m "not live and not perf"`,
nicht nur die neuen Dateien.

Commit: 2b12ad4 (test-only). Gepusht origin/main.
