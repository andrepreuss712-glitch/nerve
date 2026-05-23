---
quick_id: 20260523-cr1
slug: cold-call-phrases-reseed
description: "08.23.2.C.R.1: cold_call-Phrases Re-Seed via idempotente Alembic-Migration 0005"
date: 2026-05-23
---

# Quick Task 20260523-cr1: cold_call-Phrases Re-Seed

## Goal

Alembic Migration 0005 die 8 Standard-Cold-Call-EWB-Phrasen re-seeded die in
Phase 08.23.2.A bulk-deleted wurden. Migration ist idempotent (skip wenn
objection_type+text-Kombination bereits existiert).

## Tasks

### Task 1: Alembic Migration 0005 erstellen

**File:** `alembic/versions/0005_seed_cold_call_phrases.py`

**Schema:**
- `revision = '0005'`, `down_revision = '0004'`
- Verwendet `op.get_bind()` + SELECT-Guard per Phrase (idempotent)
- `user_id=1` (Admin-MVP-Pattern, identisch mit 0003 Gatekeeper-Seed)
- `mode='cold_call'`, `quality_tier='A'`
- 8 objection_types × 2-3 Varianten = 19-24 Rows

**Objection types + Phrasen:**

| objection_type | Varianten |
|---|---|
| zu_teuer | 3 |
| keine_zeit | 2 |
| kein_interesse | 2 |
| kein_budget | 3 |
| schicken_sie_unterlagen | 2 |
| anderer_anbieter | 2 |
| brauche_bedenkzeit | 2 |
| nicht_zustaendig | 2 |

**Idempotenz-Logik:** Pro Phrase: `SELECT id FROM phrases WHERE objection_type=? AND text=?` — INSERT nur wenn kein Ergebnis.

**downgrade():** DELETE WHERE mode='cold_call' AND objection_type IN (die 8 Typen) — nur die Seed-Rows, nicht User-Phrasen mit anderem Text.

### Task 2: Migration lokal testen + Smoke-Verify

- `python -m alembic upgrade head` (oder `python -c "from app import *"` um Auto-Hook zu triggern)
- Verify: `SELECT objection_type, count(*) FROM phrases WHERE mode='cold_call' GROUP BY objection_type` → 8 Typen mit je 2-3 Rows
- Idempotenz-Test: zweiter Upgrade-Run darf keine Fehler werfen und keine Duplikate erzeugen
- Pre-Deploy-Smoke-Check: PiP im Cold-Call-Modus zeigt EWB-Buttons (mentaler Check auf Route-Logik)

## must_haves

truths:
- 0005_seed_cold_call_phrases.py existiert in alembic/versions/
- Migration ist idempotent (doppelter Run = kein Fehler, keine Duplikate)
- Alle 8 objection_types vorhanden mit je mind. 2 Varianten
- down_revision='0004'

artifacts:
- alembic/versions/0005_seed_cold_call_phrases.py
