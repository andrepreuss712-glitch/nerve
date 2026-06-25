---
type: quick
slug: abschluss-fuehrung-behavioral
status: complete
created: 2026-06-25
---

# Quick: outcome_progression → verhaltens-basierte abschluss_fuehrung (§6)

Löst die im outcome-blind-Fix geflaggte §6-Spannung (André + Gemini-Cross-AI): die einzige
outcome-lesende Dimension wird verhaltens-basiert umgebaut. NUR `services/rubric_dimensions.py` +
die Seed-Zeilen in `alembic/versions/0021_mode_weight_config.py` (noch nicht deployt → direkt
editiert, keine neue Migration) + die betroffenen Tests + die beiden Schild-Strings (models.py:870
+ 0021 COMMENT, Punkt 23 — Key muss akkurat sein). Kein Refactor sonst (Punkt 17). NICHT deployen.

## Verifiziertes Signal (Punkt 20/21)
`intent_event.phase` = SmallInt 1-6 nullable (Quelle detect_phase Welle 4, models.py:769);
Phase 6 = Abschluss/Terminvereinbarung, quasi-terminal (ki_logik.py:169). Reales Signal, kein Wunsch.

## Umbau
- Key `outcome_progression` → `abschluss_fuehrung`, Label "Abschluss-Führung".
- `is_measurable`: max. Phase ≥ 3 (echte Abschluss-Chance); Phase 1-2 / kein Phasen-Signal → 'na'
  (keine schlechte Note → kein Outcome-Bias beim Früh-Aufleger).
- `score` (kein outcome-Read): 3 = Phase-6-Abschluss nach Kaufsignal/gut behandeltem Vorwand
  (Momentum + Timing); 2 = Phase 6 ohne Momentum (drückt durch); 1 = tiefe Phase, keine CTA.
  Anti-Goodhart: Stufe 3 an Signal+Timing gekoppelt, nicht ans bloße Fragen.
- Seed bleibt pro Modus gewichtet aktiv (nur Key-Name ändert sich).

## Tests
- test_outcome_does_not_change_score: jetzt abschluss_fuehrung CONFIG-ON (stärkerer Beweis).
- neu: test_early_hangup_closing_not_measurable / test_closing_after_signal_scores_high /
  test_no_cta_fizzle_scores_low. 2 D-02-Pflicht-Tests bleiben grün.
