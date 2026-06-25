---
type: quick
slug: rubric-engine-outcome-blind
status: complete
created: 2026-06-25
---

# Quick: Noten-Engine ergebnis-blind machen (Soll-Verhalten §6)

Pre-Execute-Audit + Cross-AI (Gemini) fanden ein Outcome-Bias-Loch in der TAXO2-Plan-02-Engine.
André entschied die Richtung (Soll-Verhalten §6, Log 2026-06-25). NUR `services/rubric_engine.py`
+ `services/rubric_dimensions.py` + die Engine-Tests — kein anderer Code, kein Refactor (Punkt 17).
NICHT deployen — STOP vor dem Deploy, Claudian fährt den beaufsichtigten Deploy.

## Prinzip (kanonisch, §6)
Die Note misst NUR Verhalten. Das Ergebnis (Ja/Nein, `calls.outcome`) zieht die Note NIE runter —
ein Nein ist keine schlechte Leistung. Einziger Über-Bewertungs-Schutz = Daten-Substanz
(`measured_weight_pct < 0.5` → `coaching_score=None`), ergebnis-blind.

## Änderungen
1. `rubric_engine.py`: `_is_aborted_failure`/`ABORT_OUTCOMES`/`SHORT_CALL_SECONDS` + aborted_failure-
   Zweig ENTFERNT; nicht-messbare config-an-Dims → neutraler `reason='na'` (kein `not_reached`);
   `_sample_size_for` skeptisch (`conf is not None and conf >= gate`); Daten-Substanz-Schutz + is_provisional bleiben.
2. `rubric_dimensions.py`: `_confident_events_of_type` skeptisch (`confidence=None` ≠ konfident).
3. Tests: alter D-08-Abbruch-Straf-Test ersetzt durch `test_outcome_does_not_change_score`,
   `test_thin_call_insufficient_not_high`, `test_good_behavior_short_call_not_penalized`; 2 D-02-
   Pflicht-Tests bleiben grün. Bau-Regel 1 (kein LLM) gehalten.

## Flag
`outcome_progression` (1 von 7 Dimensionen) benotet weiterhin `calls.outcome` — NICHT in dieser
Direktive enthalten; in den ergebnis-blinden Tests bewusst `config_off`. Separate §6-Entscheidung.
