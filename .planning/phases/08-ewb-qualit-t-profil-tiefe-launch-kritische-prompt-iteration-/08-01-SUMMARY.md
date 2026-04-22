---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
plan: 01
subsystem: database-migration
tags: [migration, schema, ewb-qualitaet, profile-tiefe, wave-1, foundation]
requires: []
provides:
  - objection_events.success_nullable
  - conversation_logs.anrede
  - prompt_versions.is_default
  - database/nerve.db.bak_pre_v08_01
  - docs/phase-08-training-vs-live-prompt-gap.md
affects:
  - app.py (_migrate function)
  - database/models.py (3 Column-Edits)
  - .gitignore (*.bak* pattern)
tech-stack:
  added: []
  patterns:
    - SQLite-Table-Rebuild (CREATE new -> INSERT SELECT -> DROP -> RENAME) fuer ALTER COLUMN DROP NOT NULL
    - audit_log Marker-Row mit SELECT-Check fuer Idempotenz
    - shutil.copy fuer Pre-Migration DB-Backup
key-files:
  created:
    - tests/test_phase_08_models.py
    - tests/test_phase_08_migration.py
    - docs/phase-08-training-vs-live-prompt-gap.md
    - database/nerve.db.bak_pre_v08_01 (runtime artifact)
  modified:
    - database/models.py (3 in-place Column-Edits)
    - app.py (5 neue Migrations-Bloecke A-E, 1 Rule-3-Fix am Phase-06 consent_text-Block)
    - .gitignore (*.bak* Pattern fuer T-08-01-04)
decisions:
  - 3-state (TRUE/FALSE/NULL) fuer ObjectionEvent.success wegen D-01 POLISH-55
  - Table-Rebuild statt Alembic fuer nullable-Toggle (SQLite-Limitation, Repo-Pattern ohne Alembic)
  - audit_log Marker idempotent via SELECT-COUNT-Check (Rule 2 Auto-fix — Plan-Spec hatte pure INSERT)
  - Rule 3 Auto-fix: Phase-06 consent_text inner `with engine.connect() as conn` Shadowing aufgeloest
  - .gitignore-Ergaenzung database/*.bak* fuer T-08-01-04 Info-Disclosure-Mitigation
metrics:
  duration: 42 minutes
  completed: 2026-04-22
  tests_green: 10/10
  commits: 5
---

# Phase 08 Plan 01: EWB-Qualitaet Wave 1 Foundation Summary

Wave-1-Foundation fuer Phase 08 EWB-Qualitaet abgeschlossen: 3 DB-Schema-Aenderungen (success nullable, anrede, is_default) mit Pre-Backup und idempotentem audit_log-Marker, plus Gap-Matrix-Doku als Planner-Input fuer Wave 2 v2-modular-Prompt.

## Was wurde implementiert

### Task 1: Model-Aenderungen in database/models.py

Drei in-place Column-Edits:
- `ObjectionEvent.success`: `nullable=False` → `nullable=True`, default=None (D-01 3-state: TRUE=Erfolg, FALSE=Kein Erfolg, NULL=Uebersprungen/Unbekannt)
- `ConversationLog.anrede`: neu als `Column(String(10), nullable=True)` — PreCall Du/Sie Override (D-14)
- `PromptVersion.is_default`: neu als `Column(Boolean, default=False, nullable=False)` — A/B-Default-Fallback (D-26)

UniqueConstraint `uq_prompt_version_module` bleibt erhalten.

### Task 2: 5 Migrations-Bloecke in app.py _migrate()

Alle Bloecke in strikt geforderter Reihenfolge (A vor B, B vor C):

| Block | Purpose | SQL-Pattern |
|-------|---------|-------------|
| A | Pre-Migration DB-Backup | `shutil.copy(nerve.db, nerve.db.bak_pre_v08_01)` |
| B | objection_events.success NULLABLE | CREATE TABLE _new → INSERT SELECT → DROP → RENAME (Table-Rebuild, PRAGMA-Check fuer Idempotenz) |
| C | Reset POLISH-38.1 Alt-Daten + audit_log Marker | `UPDATE WHERE created_at < '2026-04-22 00:00:00'` + idempotenter audit_log INSERT |
| D | conversation_logs.anrede | `ALTER TABLE ADD COLUMN anrede VARCHAR(10)` |
| E | prompt_versions.is_default + Backfill | `ALTER TABLE ADD COLUMN is_default BOOLEAN DEFAULT 0` + `UPDATE SET is_default=1 WHERE is_active=1` |

### Task 3: Gap-Matrix-Doku

`docs/phase-08-training-vs-live-prompt-gap.md` (112 Zeilen, 15 Matrix-Zeilen) dokumentiert:
- 14 Profil-Feld-Elemente mit IST (`services/claude_service.py:258-394 _build_system_prompt`) vs. SOLL (v2-modular)
- 3 konkrete Code-Aenderungen fuer Wave 2 Plan 02 (neue Datei `services/ewb_pipeline.py` gemaess D-41)
- v2-Prompt-Baustein-Struktur (Anker/Reframe/Beweis/Ueberleitung + Active-Listening D-47)
- Anti-Regression-Checks fuer Wave 2

## Verification Results

### Actual migration numbers

| Metrik | Wert |
|--------|------|
| reset_count (Block C) | 0 von 0 Rows — aktuelle DB hat keine Alt-Daten mit success=TRUE vor 2026-04-22 00:00:00 UTC (Test-DB ohne Live-Traffic) |
| backfill_count (Block E) | 5 Rows (alle 5 aktiven prompt_versions-Seed-Rows: assistant_live, coaching_live, objection_trigger, api_frage, training_persona) → is_default=1 |
| Backup-File-Groesse | 335872 bytes = 328 KB |
| audit_log Marker Count | 1 (stabil nach 3+ Re-Runs dank Idempotenz-Fix) |

### Tests

- `tests/test_phase_08_models.py`: 4/4 Tests green (3 Column-Assertions + 1 UniqueConstraint-Preservation)
- `tests/test_phase_08_migration.py`: 6/6 Tests green (Blocks A-E Source-Level Markers + Ordering)
- Gesamt: 10/10 Phase-08-Tests green

### Idempotenz

`_migrate()` wurde 3+ mal in Folge aufgerufen — keine Exceptions, keine duplizierten audit_log-Rows, keine DB-Korruption. PRAGMA-Check verhindert doppelten Rebuild.

### Plan Acceptance Criteria (alle aus 08-01-PLAN.md)

- [x] Task 1: 3 Column-Aenderungen (success nullable, anrede, is_default) committed
- [x] Task 2: 5 Migration-Bloecke (A-E) committed, alle mit `# ── Phase 08 ...` Markern
- [x] database/nerve.db.bak_pre_v08_01 existiert (335872 bytes)
- [x] audit_log hat 1 Row mit action='migration_v08_01_reset_success_polish38_1'
- [x] docs/phase-08-training-vs-live-prompt-gap.md (112 Zeilen, 15 Matrix-Zeilen)
- [x] Re-Run von _migrate() wirft keine Exception
- [x] Umlaut-Regel: Kommentare mit Umlauten, SQL/Python-Identifier ASCII (anrede/is_default)
- [x] Keine bestehenden Migrations-Bloecke entfernt oder modifiziert

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Phase-06 `consent_text`-Block Connection-Shadowing**

- **Found during:** Task 2 Live-Test
- **Issue:** Der Phase-06-Block (line 513-520) hatte ein geschachteltes `with engine.connect() as conn:` das die aeussere `conn` Variable ueberschattete. Nach Ende des inneren `with`-Kontexts zeigte `conn` auf eine **geschlossene** Connection, wodurch die nachfolgenden Phase-08-Bloecke B-E mit `conn is closed` fehlschlugen.
- **Fix:** Innere Variable zu `_p06_conn` umbenannt, sodass die aeussere `conn` intakt bleibt.
- **Files modified:** app.py (line 513-522)
- **Commit:** 17723ae (als Teil von Task 2 GREEN)

**2. [Rule 2 - Missing Critical] audit_log Marker ohne Idempotenz**

- **Found during:** Task 2 Live-Test (3+ Re-Runs)
- **Issue:** Plan-Spec fuer Block C hatte rein `INSERT INTO audit_log ... VALUES (...)` ohne WHERE-NOT-EXISTS-Check. Das wuerde bedeuten: bei jedem App-Neustart waechst `audit_log` um eine Marker-Row → unbegrenztes Wachstum fuer forensisch-relevante Infrastruktur-Tabelle.
- **Fix:** `SELECT COUNT(*) FROM audit_log WHERE action = 'migration_v08_01_reset_success_polish38_1'` vor dem INSERT. INSERT nur wenn existing_marker == 0.
- **Files modified:** app.py (line 571-587)
- **Commit:** 17723ae (als Teil von Task 2 GREEN)
- **Validation:** audit_log marker count bleibt konstant bei 1 auch nach 3+ `_migrate()`-Re-Runs.

**3. [Rule 2 - Threat Mitigation] .gitignore `database/*.bak*` fehlte**

- **Found during:** Task 2 GREEN, threat-model-review
- **Issue:** Threat T-08-01-04 (Info Disclosure) im Plan forderte Pre-Backup database/nerve.db.bak_pre_v08_01 lokal auf VPS zu halten. Aber `.gitignore` hatte nur `database/*.db` ohne `*.bak*`-Coverage → Backup waere versehentlich commitbar geworden.
- **Fix:** `.gitignore` erweitert um `database/*.bak*` + `database/*.bak_pre_v*`.
- **Files modified:** .gitignore (line 10-12)
- **Commit:** 17723ae (als Teil von Task 2 GREEN)

## Open Question fuer Wave 2

Soll Wave 2 (Plan 02 v2-modular Prompt) die 4 bestehenden Legacy-Module (`assistant_live`, `coaching_live`, `objection_trigger`, `api_frage`, `training_persona`) mitmigrieren (is_default=1 bleibt stabil) oder als Risiko dokumentiert?

**Empfehlung (aus RESEARCH Open Question 2):** Minimalen Scope halten. Nur `ewb`-Modul neu. Die bestehenden 5 Module behalten ihr `is_default=1` via Backfill aus Block E. Kein Refactoring am Legacy-Pfad in Phase 08.

## Known Stubs

Keine Stubs eingebaut. Alle 3 Schema-Aenderungen sind vollstaendig verdrahtet in Models + DB-Migration; die Gap-Matrix-Doku ist explizit als "Spec-Input fuer Wave 2" ausgeschildert, nicht als Implementierung.

## Self-Check: PASSED

**Files verified existing:**
- database/models.py — FOUND (modified)
- app.py — FOUND (modified)
- docs/phase-08-training-vs-live-prompt-gap.md — FOUND (112 Zeilen)
- database/nerve.db.bak_pre_v08_01 — FOUND (335872 bytes)
- tests/test_phase_08_models.py — FOUND
- tests/test_phase_08_migration.py — FOUND
- .gitignore — FOUND (modified)

**Commits verified in git log:**
- c9b4ad4 — FOUND (test RED Task 1)
- 1d9dd25 — FOUND (feat GREEN Task 1)
- d41d704 — FOUND (test RED Task 2)
- 17723ae — FOUND (feat GREEN Task 2)
- 3f17a5d — FOUND (docs Task 3)

**Tests runtime verification:**
- tests/test_phase_08_models.py: 4/4 passed
- tests/test_phase_08_migration.py: 6/6 passed
- Total: 10/10 passed
