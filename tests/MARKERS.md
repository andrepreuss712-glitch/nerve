# Test-Marker — live / perf (Phase 08.23.2.PGTEST.GREEN Plan 05)

Lebende Betriebs-Doku: welche Tests aus dem Deploy-Gate exkludiert sind, warum, und wie man sie
separat laeuft. Das Gate (`deploy.sh production` / `scripts/triage.sh`) ruft pytest mit
`-m "not live and not perf"` — diese Marker-Tests laufen dort NICHT.

**Grundsatz (Regel 3):** Marker NUR fuer Tests, die eine ECHTE externe Abhaengigkeit (real-API,
echtes NER-Modell) ODER eine Timing-/Latenz-Messung brauchen. KEIN Security-/RLS-/Anonymisierungs-
/Isolations-LOGIK-Test wird markert — die laufen deterministisch IM Gate (z.B. `test_anonymizer_worker`
mit injiziertem `_fake_anonymize`-NER-Stub: die should_persist/Filter/Hash/RLS-Logik laeuft real).

## `perf` — Latenz/Timing-Messungen

| Test | Grund | Voraussetzung |
|------|-------|---------------|
| `tests/test_anonymization_perf.py::test_p95_latency` | misst p95-Latenz der Anonymisierung — Wanduhr-Messung, im Gate nicht stabil | echtes NER-Modell geladen, ruhige Maschine |
| `tests/test_anonymization_perf.py::test_short_snippet_latency` | Latenz kurzer Snippets — Timing | dito |
| `tests/test_anonymization_perf.py::test_art9_short_circuit_faster` | vergleicht Laufzeit ART9-Short-Circuit vs. Vollpfad — Timing | dito |

**Separat laufen:** `pytest tests/test_anonymization_perf.py -m perf` (auf einer Maschine mit geladenem
NER-Modell; HOME mit beschreibbarem HF-Cache, NICHT der Gate-Sandbox `/nonexistent`).

## `live` — echtes externes Modell / API

| Test | Grund | Voraussetzung |
|------|-------|---------------|
| `tests/test_anonymization_security.py::test_reid_rate_below_5_percent` | misst die ECHTE Re-Identifikations-RATE des realen NER-Modells gegen einen Korpus (statistische Qualitaets-Messung, kein deterministischer Logik-Test) | `ANTHROPIC_API_KEY`, echtes NER-Modell, Korpus |
| `tests/test_phase_classifier.py::test_phase_classifier_integration_real_haiku` | echter Haiku-API-Call gegen Korpus-Sequenzen (Req-12 Acceptance) | `ANTHROPIC_API_KEY` |

**Separat laufen:** `ANTHROPIC_API_KEY=<key> pytest -m live` (bzw. `-m "live and security"` nur fuer reid).

## Abgrenzung — was IM Gate bleibt (NICHT markert)

- `tests/test_anonymizer_worker.py` (7 Tests): Anonymisierungs-/should_persist-/training-Filter-/Hash-/
  RLS-LOGIK — laeuft deterministisch im Gate (NER via `_fake_anonymize`-Stub injiziert).
- `tests/test_rls_isolation.py`, `test_rls_generic_smoke.py` u.a.: RLS/Isolation — deterministisch im Gate.
- `test_postcall_outcome_route.py` Ownership-Tests: Zugriffskontroll-LOGIK — im Gate.

**Verifikation (Plan 05 must_have):** kein `@pytest.mark.security`/RLS/Isolation-LOGIK-Test traegt
`live`/`perf` AUSSER `test_reid_rate_below_5_percent` (bewusste Ausnahme: statistische Real-Modell-Messung,
nicht die Logik). Beleg: `grep -rn "pytest.mark.live\|pytest.mark.perf" tests/`.
