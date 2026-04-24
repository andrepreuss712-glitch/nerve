---
phase: quick-260424-ekk
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - database/models.py
  - services/profile_migration.py
  - routes/profiles.py
  - static/profile_editor.js
  - templates/profile_editor.html
  - services/prompt_pipeline.py
  - services/qa_pipeline.py
  - static/pip-launcher.js
  - tests/test_tabu_migration.py
  - tests/test_profile_editor_validation.py
  - tests/test_qa_pipeline_rueckfrage.py
autonomous: true
requirements:
  - UAT-08.5-R1-TABU
  - UAT-08.5-R1-PROFIL-15
  - UAT-08.5-R1-LOWCONF
must_haves:
  truths:
    - "tabu_begriffe is persisted as List-of-Objects {begriff, alternative}"
    - "Existing string-entries are auto-migrated to {begriff, alternative: ''} on first load"
    - "Profile with empty tabu_begriffe gets 13 default pairs seeded on editor load"
    - "Profile editor section 15 renders 2-column rows (Begriff + Alternative + Delete)"
    - "Main save button is disabled while any tabu row is incomplete"
    - "POST /api/profile/<id>/tabu silently ignores incomplete entries and returns warning"
    - "Live prompt includes Tabu-Alternative instruction block (Begriff → Alternative)"
    - "Low-confidence (< 0.80) triggers Rückfrage branch — never silent"
    - "Old Soft-Hint 'Neuer Einwand — noch kein Vorschlag' is removed from pip-launcher.js"
    - "Safety-Net post-generation substitution of tabu words still works"
  artifacts:
    - path: "services/profile_migration.py"
      provides: "Migration helper: strings → objects + default seed"
      contains: "TABU_DEFAULT_PAIRS"
    - path: "routes/profiles.py"
      provides: "POST /api/profile/<id>/tabu with list-of-objects validation"
    - path: "static/profile_editor.js"
      provides: "Section 15 2-column UI + validation + disabled save button"
    - path: "services/qa_pipeline.py"
      provides: "build_tabu_instruction() + Rückfrage branch in generate_qa_response()"
      contains: "build_tabu_instruction"
    - path: "services/prompt_pipeline.py"
      provides: "build_profile_context() embeds Tabu-Instruction-Block"
  key_links:
    - from: "services/profile_migration.py"
      to: "routes/profiles.py GET profile_editor"
      via: "migrate_tabu_begriffe(profile) called on editor load"
    - from: "static/profile_editor.js"
      to: "POST /api/profile/<id>/tabu"
      via: "fetch with list-of-objects payload"
    - from: "services/prompt_pipeline.py build_profile_context"
      to: "services/qa_pipeline.py build_tabu_instruction"
      via: "direct function call, embedded in system prompt"
    - from: "services/qa_pipeline.py generate_qa_response"
      to: "EWB-prompt-template"
      via: "confidence < 0.80 → Rückfrage-branch, never silent"
---

<objective>
Phase 08.5 Post-Execute-Refinement: Three locked design corrections after UAT on 23./24.04.2026 falsified earlier decisions.

1. **KORREKTUR 1 — Tabu:** List-of-Strings → List-of-Objects `{begriff, alternative}` with 13-pair default seed. Old `apply_tabu_filter()` becomes a prompt-instruction block (`build_tabu_instruction`) integrated into `build_profile_context()`. Safety-Net post-generation substitution remains.

2. **KORREKTUR 2 — Profil-Editor Sektion 15 Rebuild:** Tag-chip-input replaced by 2-column rows (Begriff + Alternative + Delete). Save button disabled while any row is incomplete; visual red hint per incomplete row. Default seed loaded on empty profile.

3. **KORREKTUR 3 — Low-Confidence → Rückfrage:** Remove Soft-Hint. `generate_qa_response()` threshold 0.80 unchanged, but `< 0.80` now branches to Rückfrage-Prompt ("Frag nach: …") instead of staying silent. Never silent, never halluziniert.

Purpose: Fix UAT-falsified design — Tabu was a useless blacklist, Low-Confidence was a silent dead-end, Profile editor did not collect the new data shape.
Output: DB-safe migration, 2-column UI, prompt-integrated Tabu-Alternatives, Rückfrage-branch in QA pipeline, tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md

<!-- Phase 08.5 background (canonical location & pattern) -->
<!-- STATE.md decisions confirm: -->
<!-- - tabu_begriffe stored in profile.daten['basis']['tabu_begriffe'] (canonical, D-15) -->
<!-- - No DB column change; JSON column `daten` holds the list -->
<!-- - PROFILE_ID already exposed in profile_editor.html -->
<!-- - profile_editor.js uses raw fetch (no shared apiClient) -->
<!-- - _qa_pipeline_dispatch extracted in claude_service.py -->
<!-- - build_profile_context() in services/prompt_pipeline.py is the integration point -->

<interfaces>
<!-- Canonical data location -->
profile.daten = {
  "basis": {
    "tabu_begriffe": [ {"begriff": "Kosten", "alternative": "Investition"}, ... ]
  },
  ...
}

<!-- Old shape (to migrate on read) -->
profile.daten["basis"]["tabu_begriffe"] = ["Kosten", "Problem", ...]  # list of str

<!-- Default seed (13 pairs) -->
TABU_DEFAULT_PAIRS = [
  ("Kosten", "Investition"),
  ("Problem", "Herausforderung"),
  ("günstig", "effizient"),
  ("billig", "preis-attraktiv"),
  ("Risiko", "Absicherung"),
  ("Schwäche", "Entwicklungspotenzial"),
  ("Nachteil", "Unterschied"),
  ("verkaufen", "helfen"),
  ("müssen", "können"),
  ("alt", "etabliert"),
  ("kompliziert", "strukturiert"),
  ("verlieren", "absichern"),
  ("Konkurrenz", "Mitbewerber"),
]

<!-- New QA pipeline function -->
def build_tabu_instruction(profile: dict) -> str:
    """Returns system-prompt block for prompt_pipeline, empty string if no tabu."""

<!-- Confidence branching contract -->
# generate_qa_response():
#   confidence >= 0.80  → direct answer (with Tabu-Alternatives applied)
#   confidence <  0.80  → Rückfrage-branch, prefix "Frag nach:"
#   NEVER silent, NEVER halluzinated
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Migration helper + default seed + on-read conversion</name>
  <files>services/profile_migration.py, tests/test_tabu_migration.py</files>
  <behavior>
    - test_migrate_strings_to_objects: ["Kosten", "Problem"] → [{"begriff":"Kosten","alternative":""},{"begriff":"Problem","alternative":""}]
    - test_migrate_preserves_objects: already-object shape passes through unchanged
    - test_migrate_empty_seeds_defaults: [] → 13 default pairs
    - test_migrate_missing_key_seeds_defaults: daten without basis.tabu_begriffe → 13 defaults
    - test_migrate_idempotent: running twice yields same result as once
    - test_migrate_mixed: ["Kosten", {"begriff":"X","alternative":"Y"}] → both normalized to object form
  </behavior>
  <action>
    Create `services/profile_migration.py` with:
    - `TABU_DEFAULT_PAIRS` — 13 tuples per task briefing (use echte Umlaute per CLAUDE.md: Schwäche, müssen, günstig — these are user-facing strings)
    - `migrate_tabu_begriffe(profile_daten: dict) -> dict`:
      - Reads `profile_daten.get('basis', {}).get('tabu_begriffe', [])`
      - If list is empty/missing → inject `TABU_DEFAULT_PAIRS` as list-of-objects
      - If list contains strings → convert each to `{"begriff": s, "alternative": ""}`
      - If list contains objects → pass through (ensure keys exist, default missing keys to "")
      - Return the mutated profile_daten (same dict, in-place-update safe)
      - Idempotent — running N times === running 1 time
    Write test file `tests/test_tabu_migration.py` per behavior spec above.
  </action>
  <verify>
    <automated>cd C:/Users/andre/dev/salesnerve && python -m pytest tests/test_tabu_migration.py -x -q</automated>
  </verify>
  <done>All 6 tests pass. Migration function is idempotent, handles empty/string/mixed/object shapes, seeds 13 defaults when empty.</done>
</task>

<task type="auto">
  <name>Task 2: API route rebuild — POST /api/profile/<id>/tabu accepts list-of-objects</name>
  <files>routes/profiles.py</files>
  <action>
    In `routes/profiles.py`:

    1. Find existing `POST /api/profile/<id>/tabu` handler (or the handler that saves `tabu_begriffe` as part of profile save).
    2. Replace request body parsing:
       - Accept `request.get_json()` with shape `{"tabu_begriffe": [{"begriff": "...", "alternative": "..."}, ...]}`
       - Validate each entry:
         - Must be dict with keys `begriff` and `alternative`
         - Both must be non-empty stripped strings
         - **Silently ignore** (do NOT raise) entries where either field is empty/missing
       - Collect ignored entries into `ignored: List[dict]`
    3. Persist only VALID entries to `profile.daten['basis']['tabu_begriffe']`.
    4. Response JSON: `{"ok": True, "saved": N, "ignored": [...]}` — client can show warning for ignored entries.
    5. Also add a GET helper path inside the profile editor load route (or the existing profile editor GET) that calls `migrate_tabu_begriffe(profile.daten)` from Task 1 BEFORE rendering the template. This ensures:
       - Old string-entries surface as objects with empty alternative (user must fill in)
       - Empty tabu gets 13 default pairs seeded on display
       - Save happens through same validation path — incomplete defaults get silently ignored on save (user must confirm each)

    Keep ownership check (profile.org_id == g.user.org_id) unchanged. Use `from services.profile_migration import migrate_tabu_begriffe`.

    Umlaute-Regel: German flash messages use echte Umlaute; dict keys stay ASCII (`tabu_begriffe`, `begriff`, `alternative`).
  </action>
  <verify>
    <automated>cd C:/Users/andre/dev/salesnerve && python -c "from routes.profiles import profiles_bp; print('ok')"</automated>
  </verify>
  <done>Handler accepts list-of-objects, validates both fields non-empty, silently drops incomplete entries, returns ignored list. GET profile editor route calls migrate_tabu_begriffe before render.</done>
</task>

<task type="auto">
  <name>Task 3: Profile editor section 15 rebuild — 2-column UI + validation + disabled save</name>
  <files>templates/profile_editor.html, static/profile_editor.js, tests/test_profile_editor_validation.py</files>
  <action>
    **templates/profile_editor.html — Section 15:**
    Replace the existing tag-chip-input for tabu_begriffe with a container:
    ```html
    <section id="section-15-tabu" class="profile-section">
      <h2>15. Tabu-Begriffe &amp; Alternativen</h2>
      <p class="hint">Wörter die du vermeiden willst — und was du stattdessen sagst.</p>
      <div id="tabu-rows"></div>
      <button type="button" id="tabu-add-btn" class="n-btn-ghost">+ Hinzufügen</button>
    </section>
    ```

    **static/profile_editor.js — new logic:**
    1. On init: read seeded `window._tabuBegriffe` (rendered by Jinja from migrated profile.daten). If missing/empty, request `GET /api/profile/<id>/tabu` or rely on the server-side migration already having seeded defaults.
    2. `renderTabuRows()` — renders one row per entry:
       ```
       <div class="tabu-row">
         <input type="text" class="tabu-begriff" placeholder="Tabu-Begriff" value="...">
         <input type="text" class="tabu-alternative" placeholder="Alternative (stattdessen nutzen)" value="...">
         <button type="button" class="tabu-del-btn">×</button>
         <span class="tabu-hint" hidden></span>
       </div>
       ```
    3. `validateTabuRows()` — runs on every input/change:
       - For each row: if `begriff` empty and `alternative` non-empty → show hint "Begriff fehlt" (red)
       - If `alternative` empty and `begriff` non-empty → show hint "Alternative fehlt" (red)
       - If both empty → neutral (row is "about to be deleted on save")
       - If any row has incomplete state (exactly one filled) → disable main save button, set `title="Tabu-Zeile unvollständig"`
       - Else → enable main save button
    4. `tabu-add-btn` click → append new empty row, run validation (stays disabled-save because new row is incomplete).
    5. `tabu-del-btn` click → remove row, run validation.
    6. Main save button handler: collect all rows where BOTH fields are non-empty, POST to `/api/profile/<id>/tabu` as list-of-objects. Ignore completely-empty rows client-side (not an error). Incomplete rows are prevented by disabled-button, so never submitted.

    **tests/test_profile_editor_validation.py:**
    Since this is DOM/JS logic, write Python-level integration test for the backend contract:
    - POST with `[{"begriff":"A","alternative":"B"}]` → saved=1, ignored=[]
    - POST with `[{"begriff":"A","alternative":""}]` → saved=0, ignored=[{...}]
    - POST with `[{"begriff":"","alternative":"B"}]` → saved=0, ignored=[{...}]
    - POST with mixed → saved=N, ignored=[M]
    Use Flask test client + an in-memory test profile fixture.

    User-facing strings with echte Umlaute: "Alternative fehlt", "Begriff fehlt", "Tabu-Zeile unvollständig". Code identifiers ASCII: `tabu-begriff`, `tabu-alternative`, `tabuBegriffe`.
  </action>
  <verify>
    <automated>cd C:/Users/andre/dev/salesnerve && python -m pytest tests/test_profile_editor_validation.py -x -q</automated>
  </verify>
  <done>2-column rows render, add/delete works, save button disabled while any row incomplete, red hint per incomplete row, POST accepts/filters correctly per server-side validation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: QA pipeline — build_tabu_instruction + Rückfrage branch + safety net</name>
  <files>services/qa_pipeline.py, services/prompt_pipeline.py, tests/test_qa_pipeline_rueckfrage.py</files>
  <behavior>
    - test_build_tabu_instruction_empty: profile without tabu_begriffe → returns "" (empty string, no prompt bloat)
    - test_build_tabu_instruction_populated: 3 pairs → returns block containing "WICHTIG:" and all 3 "Begriff → Alternative" mappings
    - test_build_tabu_instruction_skips_incomplete: pair with empty alternative → skipped
    - test_generate_qa_response_high_confidence_direct: confidence=0.90 → returns direct answer text (no "Frag nach:" prefix)
    - test_generate_qa_response_low_confidence_rueckfrage: confidence=0.50 → returns text starting with "Frag nach:"
    - test_generate_qa_response_never_silent: confidence=0.30, thin profile → still returns non-empty Rückfrage, never "" or None
    - test_safety_net_substitutes_tabu: generated answer contains "Kosten", profile has {begriff:"Kosten",alternative:"Investition"} → output substituted to "Investition"
  </behavior>
  <action>
    **services/qa_pipeline.py:**

    1. Remove/deprecate old `apply_tabu_filter()` (pre-generation filter). Keep a minimal post-generation safety-net substitution function:
       ```python
       def apply_tabu_safety_net(text: str, tabu_pairs: list[dict]) -> str:
           """Post-generation defensive substitution. Regex word-boundary replace."""
           for p in tabu_pairs:
               b, a = p.get('begriff','').strip(), p.get('alternative','').strip()
               if b and a:
                   text = re.sub(rf'\b{re.escape(b)}\b', a, text, flags=re.IGNORECASE)
           return text
       ```
    2. New function `build_tabu_instruction(profile: dict) -> str`:
       - Read `profile.get('daten', {}).get('basis', {}).get('tabu_begriffe', [])` (or already-unwrapped shape)
       - Filter to complete pairs only (both non-empty)
       - If empty → return ""
       - Else return:
         ```
         WICHTIG: Bei folgenden Wörtern nutze bevorzugt die Alternative anstelle des Tabu-Begriffs:
         Kosten → Investition, Problem → Herausforderung, ...
         ```
    3. Rebuild `generate_qa_response(utterance, profile, classifier_result, ...)` Rückfrage-branch:
       - Compute `confidence = classifier_result.get('confidence', 0.0)`
       - Build system prompt with instruction (LOCKED wording per task briefing):
         ```
         Analysiere den Einwand. Entscheide:
         1. Wenn Einwand klar ist UND Profil-Daten passen → direkte Antwort aus Profil (mit Tabu-Alternativen).
         2. Wenn Einwand unklar ODER Profil-Daten dünn ODER Klassifikator unsicher → KEINE Antwort erfinden. Stattdessen eine offene Rückfrage vorschlagen die den Kunden zur Konkretisierung zwingt.
            Format: 'Frag nach: <konkrete Rückfrage>'
            Beispiele:
            - 'Frag nach: Wie meinen Sie das genau?'
            - 'Frag nach: Was müsste passieren damit das für Sie in Frage kommt?'
            - 'Frag nach: Ist das ein Budget-Thema oder fehlt noch die Überzeugung?'
         3. NIEMALS stumm bleiben. NIEMALS halluzinierte konkrete Behauptungen über Produkt/Firma/Zahlen.
         ```
       - If `confidence >= 0.80`: direct-answer branch. Include `build_tabu_instruction(profile)` in system prompt. Apply `apply_tabu_safety_net` to output.
       - If `confidence < 0.80`: Rückfrage branch — same Claude call but system prompt biases to "Frag nach:" prefix. Validate output starts with "Frag nach:"; if not, prepend it.
       - Never return empty/None. On LLM failure fallback to: `"Frag nach: Wie meinen Sie das genau?"`

    4. Threshold 0.80 stays in a module-level constant `CONFIDENCE_THRESHOLD = 0.80`.

    **services/prompt_pipeline.py:**
    - In `build_profile_context(profile)`: append `build_tabu_instruction(profile)` to the returned system prompt block. If empty string, no-op.

    **tests/test_qa_pipeline_rueckfrage.py:**
    Write per behavior spec. Mock `claude_service.generate_completion` / whatever LLM call exists so tests run without network. For `test_safety_net_substitutes_tabu` — test the pure function directly.

    User-facing strings keep echte Umlaute: "Frag nach:", "müsste", "für", "Überzeugung", "dünn". Code identifiers ASCII: `build_tabu_instruction`, `apply_tabu_safety_net`, `confidence`, `tabu_pairs`, `tabu_begriffe`.
  </action>
  <verify>
    <automated>cd C:/Users/andre/dev/salesnerve && python -m pytest tests/test_qa_pipeline_rueckfrage.py -x -q</automated>
  </verify>
  <done>build_tabu_instruction returns prompt-ready block. Low-confidence never silent — always returns "Frag nach: ..." text. Safety-net substitutes tabu words post-generation. Tabu-instruction-block wired into build_profile_context.</done>
</task>

<task type="auto">
  <name>Task 5: Remove Soft-Hint from pip-launcher.js + end-to-end smoke test</name>
  <files>static/pip-launcher.js</files>
  <action>
    In `static/pip-launcher.js`:
    1. Grep/search for the Soft-Hint string "Neuer Einwand — noch kein Vorschlag" (or the ASCII variant "noch kein Vorschlag") introduced in Plan 08.5-03 D-04.
    2. Remove the entire conditional branch that sets that hint text. The slot should now either:
       - Receive a real answer (from `pip_token_done` with Tabu-filtered content), OR
       - Receive a Rückfrage (starts with "Frag nach:") which renders as normal answer
    3. If there is a UI differentiation hook (class toggle for Rückfrage vs Antwort), add a minimal one: if token text starts with `"Frag nach:"`, add class `pip-rueckfrage` to the slot element. CSS styling is optional but add one-liner in nerve.css scope ONLY if there is an obvious single-file CSS location — otherwise skip (out of scope).
    4. Verify no remaining references to the old Soft-Hint by grep.

    After edits, run a manual JS-syntax check by loading the file through Python (it is served as a static asset — a syntax error would break the page). No new dependency.

    Umlaute-Regel: "Frag nach:" is user-facing text — keep as-is. JS variable names ASCII.
  </action>
  <verify>
    <automated>cd C:/Users/andre/dev/salesnerve && python -c "import pathlib; s=pathlib.Path('static/pip-launcher.js').read_text(encoding='utf-8'); assert 'noch kein Vorschlag' not in s and 'kein Vorschlag' not in s, 'Soft-Hint still present'; print('ok')"</automated>
  </verify>
  <done>Soft-Hint removed. Slots only show real answers or Rückfragen. Optional: `pip-rueckfrage` class toggle for visual differentiation.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 6: UAT Verification — 3 correction flows</name>
  <what-built>
    - Tabu DB shape: list-of-objects with migration + default seed
    - Profile editor section 15: 2-column rows + disabled save when incomplete
    - Low-Confidence → Rückfrage (never silent)
    - Soft-Hint removed from PiP
  </what-built>
  <how-to-verify>
    1. **Migration + seed:** Open profile editor for a profile with empty tabu_begriffe. Expect 13 default rows auto-populated (Kosten → Investition etc.)
    2. **Validation:** Clear the alternative field of one row. Expect: red "Alternative fehlt" hint under that row AND save button disabled.
    3. **Save flow:** Fill in the missing alternative. Expect: hint clears, save button enabled, save succeeds.
    4. **Old-string migration:** Find a profile with legacy string-only tabu list (if exists) or create one by manually editing profile.daten in DB. Open editor. Expect: rows render with filled Begriff, empty Alternative, save disabled, red hints.
    5. **Live prompt integration:** Start a live PiP session. Ask an einwand like "Das ist zu teuer, hohe Kosten." Expect: Claude answer uses "Investition" instead of "Kosten".
    6. **Low-Confidence Rückfrage:** Trigger an unclear utterance ("hm, naja, weiß nicht so recht"). Expect: slot shows "Frag nach: ..." Rückfrage, NOT silent, NOT halluzinated.
    7. **Soft-Hint gone:** Trigger same unclear utterance. Expect: no "Neuer Einwand — noch kein Vorschlag" text anywhere.
  </how-to-verify>
  <resume-signal>Type "approved" or describe specific failures per step number</resume-signal>
</task>

</tasks>

<verification>
- `pytest tests/test_tabu_migration.py tests/test_profile_editor_validation.py tests/test_qa_pipeline_rueckfrage.py -x` all pass
- Grep confirms "noch kein Vorschlag" absent from static/pip-launcher.js
- Manual UAT per Task 6 checkpoint passes all 7 steps
</verification>

<success_criteria>
- [ ] tabu_begriffe stored as List-of-Objects `{begriff, alternative}` in profile.daten.basis
- [ ] Migration idempotent: strings → objects, empty → 13 defaults, objects pass through
- [ ] POST /api/profile/<id>/tabu silently ignores incomplete entries, returns ignored list
- [ ] Profile editor section 15: 2-column rows + Add + Delete + Disabled-save-while-incomplete + red hints
- [ ] build_tabu_instruction returns prompt block; integrated into build_profile_context
- [ ] Safety-Net `apply_tabu_safety_net` substitutes tabu words post-generation
- [ ] Low-Confidence (< 0.80) branches to "Frag nach: ..." — never silent, never halluziniert
- [ ] Soft-Hint removed from pip-launcher.js
- [ ] All 3 new test files pass
- [ ] Manual UAT (Task 6) approved
</success_criteria>

<output>
After completion, create `.planning/quick/260424-ekk-phase-08-5-post-execute-refinement-tabu-/260424-ekk-SUMMARY.md` documenting:
- Final list-of-objects shape + canonical location
- Migration behavior and the 13-pair default seed
- New QA pipeline confidence-branching contract
- Any deviations from this plan (Rule-1 auto-fix, Rule-3 stale pattern)
- Commit hashes for the 8 atomic commits
</output>
