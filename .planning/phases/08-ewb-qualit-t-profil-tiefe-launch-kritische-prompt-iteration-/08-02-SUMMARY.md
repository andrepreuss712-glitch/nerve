---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
plan: 02
subsystem: prompt-pipeline
tags: [ewb, prompt-pipeline, a-b-routing, seed, shared-utils, wave-2]
requires:
  - 08-01 (prompt_versions.is_default column + Profile schema + conversation_logs.anrede)
provides:
  - services.prompt_pipeline.resolve_prompt_version
  - services.prompt_pipeline.build_profile_context
  - services.prompt_pipeline.log_pipeline_event
  - services.prompt_pipeline.invalidate_resolver_cache
  - services.ewb_pipeline.build_ewb_prompt
  - app._seed_ewb_v2
  - prompt_versions.module='ewb' (v1-legacy is_default=1, v2-modular is_default=0)
affects:
  - app.py (+71 lines: _seed_ewb_v2 definition + startup call + is_default reconciliation)
tech-stack:
  added: []
  patterns:
    - LAZY DB-import innerhalb Funktionen (side-effect-free beim Modul-Import)
    - Cache-Key als 2-Tuple (module, user_id) fuer per-user Variant-Routing (W-7)
    - ENV-First-Check vor Cache-Lookup (safety-net pattern fuer ops-override)
    - Reconciliation-bei-Idempotent-Seed (zustaendig fuer is_default-Flags) gegen Plan-01 Backfill-Drift
    - Opt-in-Fixture statt autouse fuer Live-Session-Mocks (verhindert routes/app_routes Import-Break)
key-files:
  created:
    - services/prompt_pipeline.py (237 lines)
    - services/ewb_pipeline.py (89 lines)
    - tests/test_prompt_pipeline.py (203 lines, 11 Tests)
    - tests/test_ewb_pipeline.py (141 lines, 6 Tests)
  modified:
    - app.py (+71 lines: _seed_ewb_v2 def at line 738, call at line 807)
decisions:
  - Cache-Key (module, user_id) ist 2-Tuple — verhindert Cross-User-Variant-Leakage (W-7)
  - ENV-Override-Check vor jedem Cache-Hit (keine gecachte ENV-Entscheidung) — Ops kann live umschalten
  - LAZY DB-Imports (from database.db import SessionLocal) innerhalb Funktionen — keine Import-Side-Effects
  - _FALLBACK_V1_PROMPT als In-Memory-Sicherheit — Service bleibt funktional bei DB-Down
  - Rule 1 Auto-fix: _seed_ewb_v2 reconciled is_default bei bestehenden Rows — nicht nur INSERT bei Miss
  - Opt-in-Fixture statt autouse — routes/app_routes ImportError wenn services.live_session gemockt waere
  - 1 Extra-Test (missing-module) fuer log_pipeline_event Robustheit — deckt Pre-Launch-Zustand ab (services.finetune_logging existiert nicht)
metrics:
  duration: ~18 minutes
  completed: 2026-04-22
  tests_green: 17/17
  tasks_complete: 2/2
  commits: 4 (2x test-RED, 2x feat-GREEN)
---

# Phase 08 Plan 02: EWB-Prompt-Pipeline Wave 2 Summary

Shared Prompt-Pipeline-Utils (`resolve_prompt_version`, `build_profile_context`, `log_pipeline_event`) plus EWB-spezifisches Assembly-Modul (`build_ewb_prompt`) plus idempotenter v2-modular Prompt-Seed — vollstaendig unit-getestet, side-effect-free beim Import, bereit fuer Plan-03-Integration in `services/claude_service.py`.

## Was wurde implementiert

### Task 1: services/prompt_pipeline.py + 11 Unit-Tests

**4 exportierte Funktionen** (side-effect-free):

- `resolve_prompt_version(module, user_id)` — 3-stufige Priority-Chain:
  1. ENV-Override: `PROMPT_{MODULE}_VERSION_OVERRIDE` (D-24 Safety-Net)
  2. Deterministic: `variants[user_id % len(variants)]` (D-23, alphabetisch sortiert via `order_by(PromptVersion.version)`)
  3. Fallback: `'unknown'` (fail-open bei DB-Fehler oder leerer Table)
- `build_profile_context(user_id, mode)` — standardisierter Profil-Kontext mit Phase-08-Neufeldern:
  - Bestehende Felder: Unternehmen, Produktbeschreibung, USPs, Konsequenz, Ton
  - D-11 NEU: `branche_kontext`
  - D-07 NEU: `eigene_formulierungen` (als quoted list)
  - D-08 NEU: `beweise` (als list)
  - D-15 Anrede-Constraint WORTWOERTLICH: `Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.`
- `log_pipeline_event(event_type, module, data)` — modul-agnostisches Logging-Interface, schluckt alle Fehler (live-loop-safe). Import von `services.finetune_logging` ist bewusst lazy+swallowed — das Modul existiert in Pre-Launch noch nicht.
- `invalidate_resolver_cache()` — Admin-/Test-Helper, leert `_RESOLVER_CACHE` + `_VARIANTS_CACHE`.

**Anti-Regression Design:**

- Cache-Key `(module, user_id)` zwei-Tuple — W-7 Fix: zwei user_ids landen garantiert auf verschiedenen Variants wenn N>1
- KEIN Referenz auf Legacy `_ACTIVE_PROMPT_CACHE` — neuer Resolver-Cache ist komplett unabhaengig
- DB-Imports LAZY innerhalb Funktionen — `python -c "import services.prompt_pipeline"` triggert keine DB-Connection

**Anrede-Resolution-Prioritaet verifiziert:**

- Session-Override (`ls.state['session_anrede']`) > Profile-Default (`ki.ansprache`) > `'Sie'`-Fallback
- D-15 Phrase `Wechsle NIEMALS` erscheint in `resolve_prompt_version`/`build_profile_context` Output sowie als Fallback in `ewb_pipeline`

### Task 2: services/ewb_pipeline.py + _seed_ewb_v2 + 6 Integration-Tests

**`build_ewb_prompt(profile_data, anrede, version, user_id)`:**

- Laedt Prompt-Template aus `prompt_versions` WHERE `module='ewb' AND version=X AND is_active=True`
- Fallback `_FALLBACK_V1_PROMPT` (in-memory) bei Miss/DB-Error
- Delegiert Kontext an `build_profile_context` aus Shared-Utils
- Manueller Anrede-Constraint-Block wenn Kontext leer ist (Tests / leere Session)
- Logging: `[EWB] v{version} assembled user_id={uid} len={N}`

**`_seed_ewb_v2(db=None)` in app.py:**

Idempotent 2 Rows fuer `module='ewb'` mit folgenden Texten:

- **v1-legacy** (is_default=True): Kompakter Standard-EWB-Prompt (2-3 Saetze, keine Floskeln)
- **v2-modular** (is_default=False): Baustein-Struktur (ANKER/REFRAME/KERN-GEGENARGUMENT+BEWEIS/UEBERLEITUNG) + Active-Listening-Block (D-47, 5 Regeln gegen POLISH-35/36/37-Inkonsistenzen) + harte Regeln (45 Woerter, NIEMALS apologetisch)

**Reconciliation-Fix (Rule 1 Auto-fix):**

Beim zweiten App-Start setzt Plan-01 Block E (`UPDATE prompt_versions SET is_default=1 WHERE is_active=1`) **alle** aktiven ewb-Rows auf `is_default=True` — widerspricht A/B-Semantik (exakt 1 Default pro Modul). Fix: `_seed_ewb_v2` prueft bei bestehenden Rows ob `is_default` vom Soll-Wert abweicht und korrigiert — `[DB] Seed v08: reconciled ewb/{version}.is_default={bool}`. Verifiziert per Live-DB-Query.

## Verification Results

### Test counts

| Datei                         | Tests | Runtime |
|-------------------------------|-------|---------|
| tests/test_prompt_pipeline.py | 11    | 0.12s   |
| tests/test_ewb_pipeline.py    | 6     | 3.00s (first) / 2.44s (combined) |
| **Total**                     | **17**| **2.44s** |

### Acceptance-Criteria Task 1 (alle erfuellt)

- `test -f services/prompt_pipeline.py` ✓
- `wc -l services/prompt_pipeline.py` = **237** (>=120 ✓)
- 4 exports (`resolve_prompt_version`, `build_profile_context`, `log_pipeline_event`, `invalidate_resolver_cache`) ✓
- `_RESOLVER_CACHE: dict` ✓
- Cache-Key-Pattern `(module, user_id)` ✓ (6 Treffer inkl. Doku)
- Keine `_ACTIVE_PROMPT_CACHE` Referenz ✓ (verifiziert per `grep → exit 1`)
- `PROMPT_*_VERSION_OVERRIDE` Pattern ✓
- `user_id % len` Routing ✓
- `Wechsle NIEMALS` wortwoertlich ✓ (1 Vorkommen in Code, 1 in Doku)
- `[Pipeline]` Logging-Prefix: 8 Vorkommen ✓
- `tests/test_prompt_pipeline.py`: 11 Tests (>=10 ✓) — alle green
- `python -c "import services.prompt_pipeline"`: OK, keine Side-Effects

### Acceptance-Criteria Task 2 (alle erfuellt)

- `test -f services/ewb_pipeline.py` ✓
- `wc -l services/ewb_pipeline.py` = **89** (>=60 ✓)
- `build_ewb_prompt` export ✓
- `_FALLBACK_V1_PROMPT` definiert ✓
- `[EWB]` Logging-Prefix ✓ (3 Vorkommen)
- `from services.prompt_pipeline import build_profile_context` ✓
- `_seed_ewb_v2` def in app.py line 738 ✓
- 4 Baustein-Marker ANKER/REFRAME/KERN-GEGENARGUMENT/UEBERLEITUNG ✓ (4/4)
- `Active Listening` (D-47) ✓
- `45 Woerter` ✓
- `NIEMALS apologetisch` ✓
- `_seed_ewb_v2()` Call-Site in app.py line 807 ✓
- `tests/test_ewb_pipeline.py`: 6 Tests (>=6 ✓) — alle green

### Live-DB Nachweis (nach App-Start)

```
ewb rows: 2
  version=v1-legacy is_default=True is_active=True text_len=241
  version=v2-modular is_default=False is_active=True text_len=1086
```

### _FALLBACK_V1_PROMPT

Jemals gegriffen? **Nein in den Tests**, nur der 4er-Test `test_build_ewb_prompt_fallback_unknown_version` triggert es bewusst mit `version='nonexistent'`. In der Live-DB mit ordnungsgemaessem Seed greift es nie. Dokumentiert als Safety-Net fuer DB-Down-Szenarien.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] is_default-Drift durch Plan-01 Backfill**

- **Found during:** Live-App-Start Verifikation (Task 2 GREEN)
- **Issue:** Plan-01 Block E (`app.py:607`) fuehrt `UPDATE prompt_versions SET is_default=1 WHERE is_active=1` bei jedem App-Start aus. Nach Erst-Seed haben beide ewb-Rows `is_default=True`, was der A/B-Test-Semantik (exakt 1 Default pro Modul) widerspricht und das Plan-02-Acceptance-Criterion `v2-modular.is_default=False` auf Prod-DB brechen wuerde.
- **Fix:** `_seed_ewb_v2` prueft bei bestehenden Rows ob `is_default` vom Soll-Wert abweicht und korrigiert (`exists.is_default = is_default` wenn unterschiedlich). Log-Line `[DB] Seed v08: reconciled ewb/{version}.is_default={bool}`.
- **Files modified:** app.py (`_seed_ewb_v2` Reconciliation-Block)
- **Commit:** 56d1030
- **Validation:** Live-DB-Query nach 2. App-Start zeigt korrekte Flags (v1-legacy=True, v2-modular=False).

**2. [Rule 3 - Blocking] Autouse-Fixture brach Seed-Test-Import**

- **Found during:** Task 2 Erste Test-Run (4/6 pass)
- **Issue:** Die ursprueng fuer alle Tests autouse markierte `_empty_active_profile` Fixture ersetzt `sys.modules['services.live_session']` mit einem Mock. Danach triggert `from app import _seed_ewb_v2` transitive Imports, darunter `routes/app_routes` mit `from services.live_session import LOG_DIR` — dieser Import schlaegt fehl (`ImportError: cannot import name 'LOG_DIR' from '_LSMock'`).
- **Fix:** Fixture von `autouse=True` auf Opt-In-Parameter umgestellt. Die 4 `build_ewb_prompt`-Tests deklarieren sie explizit als Parameter; die 2 `_seed_ewb_v2`-Tests laufen ohne Mock und koennen `from app import _seed_ewb_v2` sauber aufloesen.
- **Files modified:** tests/test_ewb_pipeline.py
- **Commit:** 56d1030

**3. [Rule 2 - Robustness] log_pipeline_event bei fehlendem services.finetune_logging**

- **Found during:** Task 1 Test-Design
- **Issue:** Der Plan-Action-Block nimmt an, dass `services/finetune_logging.py` existiert (`from services.finetune_logging import log_ft_event`). Im Repo existiert dieses Modul NICHT (verifiziert per `grep`). Der urspruenglich spezifizierte Test `monkeypatch.setattr('services.finetune_logging.log_ft_event', _raise)` wuerde an dem fehlenden Modul scheitern.
- **Fix:** `log_pipeline_event` fangt `from services.finetune_logging import log_ft_event` per `try/except Exception` ab und returned early bei ImportError. Dazu 1 zusaetzlicher Test `test_log_pipeline_event_handles_missing_module` der genau diesen Pre-Launch-Zustand absichert. Der originale Swallow-Test wurde umgestellt auf `sys.modules`-Mock-Injection (via `types.ModuleType`), damit er unabhaengig vom Repo-Zustand laeuft.
- **Files modified:** services/prompt_pipeline.py (lazy import + swallow), tests/test_prompt_pipeline.py (+1 test)
- **Commit:** a60e6fd + (tests) ebdb3d6

## Interface-Contract fuer Plan 03

Plan 03 integriert die Pipeline in `services/claude_service.py`. Erwartete Consumer-Signatur:

```python
from services.prompt_pipeline import resolve_prompt_version
from services.ewb_pipeline import build_ewb_prompt
import services.live_session as ls

user_id = ls.state.get('user_id') or 0
ewb_version = resolve_prompt_version('ewb', user_id)
system_prompt = build_ewb_prompt(
    profile_data=None,        # build_profile_context liest direkt aus live_session
    anrede='Sie',             # Fallback, ueberschreiben wenn session-override bekannt
    version=ewb_version,
    user_id=user_id,
)

msg = claude_client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=400,
    system=system_prompt,
    messages=[{"role": "user", "content": user_msg}]
)
```

**Wichtige Invarianten fuer Plan 03:**

- `_ACTIVE_PROMPT_CACHE` in `services/claude_service.py:97` bleibt unveraendert — weiterhin aktiv fuer die 4 Legacy-Module (`assistant_live`, `coaching_live`, `objection_trigger`, `api_frage`, `training_persona`).
- Nur der EWB-Pfad migriert auf `resolve_prompt_version` — dokumentiert in RESEARCH Open Question 2 als bewusster Minimal-Scope.
- `build_ewb_prompt` ist side-effect-frei bis auf den `[EWB] v{version} assembled ...` print — kein DB-Write, kein Event-Log.

## Known Stubs

Keine. Beide Module sind vollstaendig verdrahtet:

- `resolve_prompt_version` liest real aus `prompt_versions`
- `build_profile_context` liest real aus `services.live_session.get_active_profile()` (Integration-Test mit echter Profile-Struktur)
- `_seed_ewb_v2` schreibt real in `prompt_versions` (verifiziert per Live-DB-Query)
- `log_pipeline_event` lazy-importiert `services.finetune_logging` — bewusst documented-stub: das Modul wird in einer spaeteren Phase hinzugefuegt, bis dahin ist der Swallow-Path der korrekte Live-Verhalten

## Phase-08 Open Item (aus Plan 01)

Plan 01 Block E Backfill-Logik (`UPDATE prompt_versions SET is_default=1 WHERE is_active=1`) trifft ab Plan-02 auf 2 aktive ewb-Rows. Die Reconciliation im Seed (Auto-fix 1) neutralisiert das. Post-Plan-03 sollte geprueft werden, ob Block E generell restriktiver formuliert werden sollte (z.B. `WHERE is_active=1 AND NOT EXISTS (SELECT 1 FROM prompt_versions p2 WHERE p2.module=prompt_versions.module AND p2.is_default=1)`). Aktuell NICHT noetig — Seed ueberschreibt konsistent.

## Self-Check: PASSED

**Files verified existing:**

- services/prompt_pipeline.py — FOUND (237 lines)
- services/ewb_pipeline.py — FOUND (89 lines)
- tests/test_prompt_pipeline.py — FOUND (203 lines, 11 tests)
- tests/test_ewb_pipeline.py — FOUND (141 lines, 6 tests)
- app.py — modified (line 738 `_seed_ewb_v2`, line 807 call-site)

**Commits verified in git log:**

- ebdb3d6 — FOUND (test RED Task 1)
- a60e6fd — FOUND (feat GREEN Task 1)
- d123f0e — FOUND (test RED Task 2)
- 56d1030 — FOUND (feat GREEN Task 2 + is_default-reconciliation + fixture-fix)

**Test runtime verification:**

- tests/test_prompt_pipeline.py: 11/11 passed (0.12s)
- tests/test_ewb_pipeline.py: 6/6 passed (2.44s combined)
- Total: 17/17 passed (2.44s)

**Live-DB verification (per python -c "import app; query"):**

- `prompt_versions` hat 2 Rows mit `module='ewb'`
- `v1-legacy is_default=True is_active=True text_len=241`
- `v2-modular is_default=False is_active=True text_len=1086`

**Smoke-Import verification:**

- `python -c "import services.prompt_pipeline; import services.ewb_pipeline; print('OK')"` → OK, keine Side-Effects
