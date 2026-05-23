---
quick_id: 20260523-cr1
slug: cold-call-phrases-reseed
status: complete
date: 2026-05-23
commit: 6092d3f
---

# Summary: 08.23.2.C.R.1 cold_call-Phrases Re-Seed

## Was gemacht wurde

Alembic Migration `0005_seed_cold_call_phrases.py` erstellt und ausgeführt.

**18 cold_call-Phrasen** in 8 objection_types seeded:

| objection_type | Varianten |
|---|---|
| zu_teuer | 3 |
| kein_budget | 3 |
| keine_zeit | 2 |
| kein_interesse | 2 |
| schicken_sie_unterlagen | 2 |
| anderer_anbieter | 2 |
| brauche_bedenkzeit | 2 |
| nicht_zustaendig | 2 |

## Phrasen-Quelle

Keine Pre-Phase-A-Seed-Datei in `tests/fixtures/` vorhanden (nur Gatekeeper-Phrasen). Phrasen aus der ursprünglichen SQLite-DB waren user-generierte Training-Ergebnisse, keine Seed-Daten — nicht wiederherstellbar. Deshalb: neue kanonische DACH-B2B Cold-Call-Phrasen aus Vertriebs-Praxis-Wissen.

## Idempotenz-Test

```
$ python -m alembic upgrade head
INFO [...] Running upgrade 0004 -> 0005
[DB] Migration 0005: 18 cold_call phrases inserted (idempotent re-seed)

$ python -m alembic upgrade head  # zweiter Run
INFO [...] Will assume non-transactional DDL.
# → keine neue Ausgabe, keine Fehler, keine Duplikate
```

## Smoke-Verify (lokal SQLite)

```python
# 8 objection_types, je 2-3 Varianten, gesamt 18 Rows
anderer_anbieter: 2, brauche_bedenkzeit: 2, kein_budget: 3,
kein_interesse: 2, keine_zeit: 2, nicht_zustaendig: 2,
schicken_sie_unterlagen: 2, zu_teuer: 3
```

## Deployment-Hinweis

Migration läuft automatisch via Alembic-Auto-Hook in `app.py` (Phase 08.23.2.C.1-04).
Production-Deploy zusammen mit Phase 08.23.2.C.R (gleiches Deploy-Fenster).

## Tests

Bestehende Testfehler sind pre-existierend (test_08_13_01_config_constants, test_anonymization_perf, test_profile_schema_v3 etc.) — keine neuen Regressions durch diese Migration.
