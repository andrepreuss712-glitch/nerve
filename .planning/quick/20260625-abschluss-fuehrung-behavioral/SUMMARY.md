---
type: quick
slug: abschluss-fuehrung-behavioral
status: complete
created: 2026-06-25
completed: 2026-06-25
---

# SUMMARY: outcome_progression → abschluss_fuehrung (verhaltens-basiert, §6)

## Geändert
- **services/rubric_dimensions.py**: Dimension `outcome_progression` → `abschluss_fuehrung`
  ("Abschluss-Führung"). Neue `_measurable_abschluss_fuehrung` (max Phase ≥ 3, sonst 'na') +
  `_score_abschluss_fuehrung` (3=Phase-6 nach Kaufsignal/gut behandeltem Vorwand; 2=Phase-6 ohne
  Momentum; 1=keine CTA). Liest NIE `calls.outcome`. BARS-Texte + Label neu. Konstanten CLOSING_PHASE
  /MIN_CLOSING_CHANCE_PHASE/MOMENTUM_VORWAND_MIN.
- **alembic/versions/0021_mode_weight_config.py**: 3 Seed-Zeilen (cold_call/meeting/training)
  umbenannt; COMMENT ON COLUMN dimension Schild-Key aktualisiert. 0021 noch nicht deployt → direkt
  editiert, KEINE neue Migration.
- **database/models.py:870**: Schild (ORM comment=) der mode_weight_config.dimension-Spalte auf den
  neuen Key gezogen (Punkt 23 — Schild muss akkurat sein; einzige Zeile außerhalb der genannten Files,
  bewusst, weil es derselbe Schild ist wie 0021 COMMENT).
- **tests/test_proration.py + test_rubric_engine.py**: Configs/Keys umbenannt; Phasen-Signal in die
  betroffenen Events ergänzt; test_outcome_does_not_change_score jetzt abschluss_fuehrung config-ON;
  3 neue Abschluss-Tests; 2 D-02-Pflicht-Tests unverändert grün.

## Verifiziertes Signal (Punkt 20/21)
intent_event.phase = SmallInt 1-6 (models.py:769, detect_phase Welle 4); Phase 6 = Abschluss,
quasi-terminal (ki_logik.py:169). Dimension setzt auf realem Signal auf.

## Statische Checks (kein Ausführen — CLAUDE.md HART)
- residual `outcome_progression` in Code = nur 4 erklärende Kommentare (kein funktionaler Ref).
- `_score/_measurable_abschluss_fuehrung` lesen kein `call.outcome` (grep leer).
- DIMENSIONS weiter 7; Seed 3× abschluss_fuehrung; kein LLM-Import (Bau-Regel 1; der eine
  Token-Treffer ist "CLAUDE.md" im Docstring, kein Import).

## ⚠ Flag (out of scope, Historie/Zukunft)
Planungs-Docs referenzieren noch den alten Namen: Plan 04 (cutover-PLAN), REVIEWS.md, Plan-02-PLAN.
Code/Seed/Schild sind umgestellt; Plan 04 sollte beim Bauen `abschluss_fuehrung` verwenden.

## Verifikation
NICHT lokal ausgeführt (CLAUDE.md HART). Scharfer Lauf = Deploy-Gate beim beaufsichtigten Plan-02-Deploy
(zusammen mit Migration 0021 + dem outcome-blind-Fix). PENDING-SUPERVISED-DEPLOY.
