---
type: quick
slug: ewb-deadcode-cleanup
status: code-complete-gated
created: 2026-06-18
deployed: false
migration_applied: false
commits: [951ad68, 4d889c7, 3289484]
migration: 0018_drop_ewb_prompt_versions
---

# Quick: Toter EWB-Prompt-Pipeline-Code entfernen (statt Welle 6)

Welle 6 (ewb-v2-modular) ist OBSOLET. Stattdessen: Aufräumen des toten Codes, den der
MEDFIX (SYSTEM_PROMPT_BASE statt build_ewb_prompt) hinterließ. **CODE-COMPLETE + gepusht,
NICHT deployed, Migration 0018 NICHT applied** (STOP-Punkt: André fährt DB + Deploy).

## Punkt-20-grep-Beleg: 0 lebende Aufrufer
```
build_ewb_prompt: nur Definition (ewb_pipeline.py) + toter Import (claude_service:29)
                  + Kommentare + tests — 0 Aufruf im Live-Pfad.
resolve_prompt_version('ewb'): nur 1 Test — 0 Live-Aufruf des ewb-Routings.
resolve_prompt_version (Funktion): LEBT — qa_pipeline:302 ('classifier'),
                  training_service:854/855/1130 ('training_*'). NICHT angefasst.
```
Live-EWB-Antwort läuft (unverändert) über streame_auto_variante + streame_manual_ewb_variante
(build_profile_context) — beide unberührt.

## Entfernt (3 atomare Commits)
**951ad68 — toter Pfad (Code):**
- `services/ewb_pipeline.py` **komplett gelöscht** (build_ewb_prompt + _load_prompt_template +
  _FALLBACK_V1_PROMPT; 0 externe Importeure außer dem toten claude_service-Import).
- `claude_service.py`: tote Importe build_ewb_prompt + resolve_prompt_version (Z.28/29) entfernt;
  in `analysiere_mit_claude` die nach MEDFIX verwaisten per-SID `_user_id`/`_anrede`-Reads + `import ls`
  entfernt. **Punkt-14-Audit:** Funktion 510-604; `_user_id`/`_anrede` 0 Reads nach Z.535 (alle späteren
  Vorkommen 788+/1491+ sind ANDERE Funktionen) — belegt, dann gelöscht. WAR-Kommentar eingedampft.

**4d889c7 — DB-Rows + Seeder (Cross-Layer):**
- `app.py`: `_seed_ewb_v2()` (Definition + Startup-Call) entfernt. **Kritischer Befund:** dieser Seeder
  re-erzeugt die ewb-Rows bei JEDEM Boot idempotent → ohne Entfernen wäre Migration 0018 beim nächsten
  Boot rückgängig. `_seed_prompt_versions` (andere Module) + `_seed_ewb_scenarios` (Training) bleiben.
- **Migration 0018** (down_revision=0017): upgrade `DELETE FROM prompt_versions WHERE module='ewb' AND
  version IN ('v1-legacy','v2-modular')` (idempotent); downgrade re-insert mit EXAKTEN Seed-Werten,
  `ON CONFLICT (version,module) DO NOTHING` (reversibel + idempotent).
- **FK-Check (Punkt 21):** `grep ForeignKey('prompt_versions'|prompt_version_id|prompt_versions.id` → **0 Treffer**.
  Keine FK-Spalte referenziert prompt_versions.id → Rows reversibel löschbar (KEIN is_active=false-Fallback nötig).

**3289484 — Tests:**
- `tests/test_ewb_pipeline.py` **komplett gelöscht** (4 build_ewb_prompt- + 2 _seed_ewb_v2-Tests).
- `test_prompt_pipeline.py`: die 2 'ewb'-Sample-Tests (env-override, cache-invalidation) auf lebendes
  Modul `classifier` umgestellt — generischer Mechanismus bleibt getestet; generische
  resolve_prompt_version- + alle build_profile_context-Tests **unverändert**.
- Stale-Doku-Refs (`_seed_ewb_v2`/`ewb_pipeline`) in conftest.py + test_ft_seed.py nachgezogen.
  `test_ft_seed`-Assertion war bereits auf EXPECTED_MODULES (ohne 'ewb') gescoped → **kein Count-Bruch**.

## Verifikation (lokal, Build-Zeit)
- **AST-Parse exit 0** für alle geänderten/neuen Dateien.
- Verhaltens-neutral (reine Toter-Code-Entfernung) — keine neue Funktion zu testen.
- Voller triage.sh = server-only → Teil des deploy.sh-Gates beim beaufsichtigten Deploy.

## OFFEN — André (GATED, STOP-Punkt)
1. **inspect.sh prompt_versions VOR:** `ssh ... 'bash scripts/inspect.sh sample prompt_versions 20'` —
   bestätigen id 6 (ewb,v1-legacy) + id 7 (ewb,v2-modular) existieren. Verbatim hier nachtragen.
2. **Migration 0018 als postgres VOR deploy.sh-Restart** (Welle-5-Deploy-Crash-Lehre 18.06.):
   `sudo -u postgres ... alembic upgrade head`.
3. `bash deploy.sh production`.
4. **inspect.sh prompt_versions NACH:** die 2 ewb-Rows weg; classifier/training_*-Rows unverändert da.
5. **Health:** `inspect.sh health` status ok.
6. **Live-EWB-Check:** Test-Anruf — Auto-Variante (streame_auto_variante) + Button-Variante
   (streame_manual_ewb_variante) erscheinen weiter; Klassifikation/intent_event unverändert (verhaltens-neutral).
