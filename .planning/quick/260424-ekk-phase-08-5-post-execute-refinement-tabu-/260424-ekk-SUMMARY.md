---
phase: quick-260424-ekk
plan: 01
subsystem: qa-pipeline, profile-editor, pip-launcher
tags: [tabu, rueckfrage, profile-editor, migration, qa-pipeline]
key-decisions:
  - tabu_begriffe shape is List-of-Objects {begriff, alternative} — canonical in profile.daten.basis.tabu_begriffe
  - migrate_tabu_begriffe() is idempotent — safe to call on every editor load
  - CONFIDENCE_THRESHOLD = 0.80 stays unchanged; < 0.80 branches to Rückfrage (never silent)
  - apply_tabu_filter() kept for backward compat but deprecated — new code uses build_tabu_instruction + apply_tabu_safety_net
  - qa_soft_hint socket event kept for backward compat but no longer shows "noch kein Vorschlag"
  - pip-rueckfrage CSS class added for visual differentiation (no CSS rules added — styling deferred)
key-files:
  created:
    - services/profile_migration.py
    - tests/test_tabu_migration.py
    - tests/test_profile_editor_validation.py
    - tests/test_qa_pipeline_rueckfrage.py
  modified:
    - routes/profiles.py
    - templates/profile_editor.html
    - static/profile_editor.js
    - services/qa_pipeline.py
    - services/prompt_pipeline.py
    - static/pip-launcher.js
metrics:
  tasks_completed: 5
  tasks_total: 6
  files_created: 4
  files_modified: 6
  tests_added: 17
  completed_date: "2026-04-24"
---

# Phase quick-260424-ekk Plan 01: Post-Execute-Refinement Tabu Summary

**One-liner:** Three locked UAT corrections — Tabu migrated to List-of-Objects with 13 default pairs, profile editor section 15 rebuilt as 2-column rows with disabled-save validation, and low-confidence QA always returns "Frag nach:" (never silent).

## What Was Built

### Korrektur 1 — Tabu: List-of-Strings → List-of-Objects + Default Seed

**Canonical data location:** `profile.daten['basis']['tabu_begriffe']`

**Shape:**
```python
[{"begriff": "Kosten", "alternative": "Investition"}, ...]
```

**Migration behavior (`services/profile_migration.py`):**
- `TABU_DEFAULT_PAIRS` — 13 tuples (German user-facing text with echte Umlaute)
- `migrate_tabu_begriffe(profile_daten)` — idempotent, handles:
  - Empty / missing list → seeds 13 default pairs
  - List of strings → converts each to `{begriff, alternative: ""}`
  - List of objects → passes through (ensures both keys)
  - Mixed list → each entry normalized per type
- Called on every GET profile editor load (in `bearbeiten()` route)

**POST /api/profile/<id>/tabu (routes/profiles.py):**
- Now accepts `{"tabu_begriffe": [{"begriff": "...", "alternative": "..."}, ...]}`
- Validates both fields non-empty; silently ignores incomplete entries
- Returns `{"ok": true, "saved": N, "ignored": [...]}`

**Prompt integration (services/prompt_pipeline.py):**
- `build_profile_context()` now appends `build_tabu_instruction(profile)` output
- Empty string when no complete pairs → no prompt bloat

### Korrektur 2 — Profile Editor Section 15 Rebuild

**HTML changes (templates/profile_editor.html):**
- Replaced tag-chip-input with `<div id="tabu-rows">` container + `<button id="tabu-add-btn">`
- Added `id="main-save-btn"` to Speichern button (needed for JS disable)

**JS logic (static/profile_editor.js):**
- `renderTabuRow(pair)` — creates one row: Begriff input + Alternative input + Delete button + hint span
- `validateTabuRows()` — runs on every input event:
  - Begriff filled, Alternative empty → "Alternative fehlt" (red hint), save disabled
  - Alternative filled, Begriff empty → "Begriff fehlt" (red hint), save disabled
  - Both empty → neutral (ignored silently on save)
  - Both filled → valid, save enabled
- `syncTabuHidden()` — keeps `vi_tabu_begriffe` hidden input in list-of-objects format
- `wrapBuildAndSubmit()` — gates the main save through validation
- `loadTabu()` — reads `window.PROFILE_DATEN.basis.tabu_begriffe` (already migrated by server)
- `tabu-add-btn` click → appends empty row, runs validation

### Korrektur 3 — Low-Confidence → Rückfrage (never silent)

**New functions in services/qa_pipeline.py:**

`build_tabu_instruction(profile: dict) -> str`:
- Reads `profile.daten.basis.tabu_begriffe` (list-of-objects)
- Filters to complete pairs only
- Returns block: `"WICHTIG: Bei folgenden Wörtern ... Begriff → Alternative, ..."`
- Returns `""` if no complete pairs

`apply_tabu_safety_net(text, tabu_pairs) -> str`:
- Post-generation word-boundary regex substitution (`re.IGNORECASE`)
- Called in generate_qa_response high-confidence branch

**Rebuilt `generate_qa_response()`:**
- New signature: added `confidence: float = 1.0` parameter
- `CONFIDENCE_THRESHOLD = 0.80` module constant
- `>= 0.80`: direct answer + Tabu-safety-net applied
- `< 0.80`: biases Claude to "Frag nach:" prefix, validates output starts with it, prepends if not
- Never returns empty/None — fallback: `"Frag nach: Wie meinen Sie das genau?"`

**Soft-Hint removed (static/pip-launcher.js):**
- `qa_soft_hint` handler no longer shows "Neuer Einwand — noch kein Vorschlag"
- Now renders received text as normal answer (Rückfrage from backend)
- Adds `pip-rueckfrage` CSS class when text starts with "Frag nach:"
- `qa_slot1` handler: label shows "RÜCKFRAGE" vs "ANTWORT" based on prefix

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (RED+GREEN) | 01699ae | Migration helper + 13-pair default seed (6 tests) |
| Task 2 | 23ff316 | POST /api/profile/<id>/tabu accepts list-of-objects |
| Task 3 | 57cc574 | Section 15 2-column UI + validation + disabled save (4 tests) |
| Task 4 (RED+GREEN) | 2d54f23 | build_tabu_instruction + Rückfrage branch + safety net (7 tests) |
| Task 5 | 5e2b438 | Remove Soft-Hint from pip-launcher.js |
| Task 6 | — | UAT checkpoint — Pending André UAT |

## UAT Checklist (Manual)

**Task 6 status: Pending André UAT**

Steps to verify manually in the running app:

1. **Migration + seed:** Open profile editor for a profile with empty `tabu_begriffe`.
   - Expected: 13 default rows auto-populated (Kosten → Investition, Problem → Herausforderung, etc.)

2. **Validation — missing alternative:** Clear the alternative field of one row.
   - Expected: Red "Alternative fehlt" hint under that row AND save button disabled (grayed out, cursor=not-allowed).

3. **Validation — save re-enables:** Fill in the missing alternative.
   - Expected: Hint clears, save button re-enables, save succeeds.

4. **Old-string migration:** If a profile with legacy string-only tabu list exists (or create one by editing `profile.daten` in DB directly), open the editor.
   - Expected: Rows render with filled Begriff, empty Alternative. Save is disabled, red hints visible.

5. **Live prompt integration:** Start a PiP session. Trigger an einwand containing "Kosten" (e.g., "Das ist zu teuer, hohe Kosten.").
   - Expected: Claude answer uses "Investition" instead of "Kosten".

6. **Low-confidence Rückfrage:** Trigger an unclear utterance ("hm, naja, weiß nicht so recht").
   - Expected: Slot 1 shows "Frag nach: ..." text, label shows "RÜCKFRAGE". NOT silent, NOT halluziniert.

7. **Soft-Hint gone:** Trigger same unclear utterance.
   - Expected: No "Neuer Einwand — noch kein Vorschlag" text anywhere in PiP.

## Deviations from Plan

### Auto-additions (Rule 2)

**1. [Rule 2 - Enhancement] pip-rueckfrage class on qa_slot1 handler**
- Found during: Task 5
- Issue: Plan specified adding `pip-rueckfrage` class to `qa_soft_hint` handler but `qa_slot1` also renders QA responses and needed the same treatment for visual consistency
- Fix: Added `pip-rueckfrage` class toggle and "RÜCKFRAGE" label to `qa_slot1` handler as well
- Files modified: static/pip-launcher.js

**2. [Rule 2 - Enhancement] wrapBuildAndSubmit() gate in profile_editor.js**
- Found during: Task 3
- Issue: The plan specified disabling the save button visually, but without wrapping `buildAndSubmit` the form could still be submitted if the button state was bypassed
- Fix: Added `wrapBuildAndSubmit()` to intercept `window.buildAndSubmit` and validate tabu rows before allowing submission
- Files modified: static/profile_editor.js

### No architectural deviations. Plan executed as designed.

## Known Stubs

None — all tabu data flows from DB through migration to UI. No hardcoded empty values in rendering paths.

## Threat Flags

None — changes are within existing trust boundary (authenticated profile editor, org-isolated API routes).

## Self-Check

- [x] services/profile_migration.py — exists
- [x] tests/test_tabu_migration.py — exists, 6 tests pass
- [x] tests/test_profile_editor_validation.py — exists, 4 tests pass
- [x] tests/test_qa_pipeline_rueckfrage.py — exists, 7 tests pass
- [x] Commit 01699ae — exists
- [x] Commit 23ff316 — exists
- [x] Commit 57cc574 — exists
- [x] Commit 2d54f23 — exists
- [x] Commit 5e2b438 — exists
- [x] "noch kein Vorschlag" absent from pip-launcher.js — verified

## Self-Check: PASSED
