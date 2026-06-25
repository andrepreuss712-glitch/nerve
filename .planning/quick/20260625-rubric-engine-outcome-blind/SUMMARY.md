---
type: quick
slug: rubric-engine-outcome-blind
status: complete
created: 2026-06-25
completed: 2026-06-25
---

# SUMMARY: Noten-Engine ergebnis-blind (Soll-Verhalten §6)

## Geändert (3 Dateien — Punkt 17, kein Refactor)

**services/rubric_engine.py**
- ENTFERNT: `_is_aborted_failure()`, `ABORT_OUTCOMES`, `SHORT_CALL_SECONDS` + die
  `aborted_failure`-Verzweigung. `compute_rubric` liest `calls.outcome` NICHT mehr für die Benotung.
- Nicht-messbare config-an-Dimension → neutraler `reason='na'` (NIE outcome-getriebenes `not_reached`).
- `is_provisional` weiterhin bei weggeprorateten config-an Dims (`na`/`no_data`), kein `not_reached`.
- Daten-Substanz-Schutz BLEIBT (`measured_weight_pct < 0.5` → `coaching_score=None`,
  `status='insufficient_data'`) — der einzige Über-Bewertungs-Schutz, ergebnis-blind.
- `_sample_size_for`: `conf is None or conf >= gate` → `conf is not None and conf >= gate`
  (Events ohne Vertrauens-Wert NICHT als sicher zählen — Gemini-Flag).

**services/rubric_dimensions.py**
- `_confident_events_of_type` (genutzt von is_measurable UND score der Ereignis-Dims): dieselbe
  Skepsis — `confidence=None` zählt NICHT mehr als konfident.

**Tests**
- ENTFERNT: `test_aborted_call_no_confident_high_score` (prüfte die jetzt falsche Outcome-Bestrafung).
- NEU: `test_outcome_does_not_change_score` (identisches Verhalten, anderes outcome → exakt gleicher
  Score), `test_thin_call_insufficient_not_high` (dünner Call → insufficient_data/None egal welches
  outcome), `test_good_behavior_short_call_not_penalized` (gutes Verhalten, kurzer Call, no_interest
  → hohe Note, nicht runtergezogen).
- Die 2 D-02-Pflicht-Tests bleiben. `_behavior_only_config`-Helfer ergänzt (ohne outcome_progression).

## Statische Selbst-Checks (kein Ausführen — CLAUDE.md HART)
- engine: kein anthropic/claude/haiku/sonnet, kein `db.commit`/`setattr`, `def compute_rubric`==1 ✓
- engine+dimensions: skeptische `conf is not None and conf >= gate` je 1×; alte Leniency 0× ✓
- alter Abbruch-Test 0×, 3 neue Tests vorhanden, 2 D-02-Pflicht-Tests vorhanden ✓

## ⚠ Flag (separate Entscheidung, nicht in diesem Fix)
`outcome_progression` benotet weiterhin direkt `calls.outcome` (no_interest=1 … meeting_booked=3).
1 der 7 kanonischen Dimensionen, NICHT Teil der Direktive; in den §6-Tests bewusst `config_off`.
Ob mit §6 vereinbar (behalten / verhaltens-basiert umdeuten / entfernen) = Claudian/André-Entscheid.

## Verifikation
- NICHT lokal ausgeführt (CLAUDE.md HART). Tests laufen scharf im **Deploy-Gate** beim
  beaufsichtigten Plan-02-Deploy (PENDING-SUPERVISED-DEPLOY).
