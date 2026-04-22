---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
verified: 2026-04-22T17:28:47Z
status: human_needed
score: 6/6 must-haves programmatisch verifiziert (8 manuelle Browser-Smokes ausstehend)
overrides_applied: 0
re_verification: false
human_verification:
  - test: "Admin-Dashboard /admin/ewb/quality rendert im Browser (A/B-Stats-Card, Quality-Score-Gate-Metriken, Varianz-Range)"
    expected: "Seite laedt ohne 500. Cards fuer A/B-Stats + Score-Gate + Varianz-Range sichtbar. Bei leerer DB: Placeholder-Text 'Noch keine Ratings mit success IS NOT NULL'."
    why_human: "Visuelles Rendering, CSS-Klassen-Conditional (metric-pass/metric-fail), JSON-to-Template-Binding koennen nur im Browser verifiziert werden."
  - test: "Admin-Rating-Tool /admin/ewb/rating-template rendert + 3-Kriterien-Radio-Roundtrip"
    expected: "Tabelle mit ObjectionEvents. User klickt Ja/Nein-Paare fuer klingt/halluzi/trifft bei einer Row. Nach 3. Klick: Gruener Flash-Hintergrund. Row persistiert in ewb_ratings-Tabelle mit rater_id = g.user.id."
    why_human: "Auto-save-JS-Handler + Visual-Feedback + idempotentes Upsert benoetigt Live-DOM + Network-Tab + DB-SELECT."
  - test: "PreCall-Anrede-Wahl (Du/Sie) in PiP-Launcher Step 3"
    expected: "Zwei Buttons sichtbar, Default 'Sie' aktiv. Klick auf 'Du' toggelt Active-Class. State persistiert in state.precallFormData.anrede. Session-Start emitted { anrede: 'Du' }. Server schreibt ls.state['session_anrede']='Du'. Nach Call-End landet 'Du' in conversation_logs.anrede."
    why_human: "Socket.IO-Emit + Multi-Tab-Test + DB-Inspektion. Wartet auf aktive Deepgram-Session."
  - test: "Session-Detail 3-Button-Rating (Erfolg/Kein Erfolg/Ueberspringen) pro ObjectionEvent"
    expected: "Benefit-Framing-Block 'Hilf uns, dir zu helfen...' sichtbar oberhalb Timeline. 3 Buttons pro Event. Klick updated Button-Class ohne Reload, POST /api/ewb/<id>/rate gibt 200 mit success=true/false/null. Bereits-gerated-Events zeigen aktiven Button bei Page-Load."
    why_human: "Visual-State-Toggle + Network-Tab-Verifikation + Aria-State-Pruefung."
  - test: "Profile-Editor Tooltip-3-Block-Display"
    expected: "Hover/Focus auf i-Button (>=16x16px) fuer jedes der 6 neuen/geaenderten Felder (branche, branche_kontext, eigene_formulierungen, beweise, ton, zusatz) zeigt 3 Text-Bloecke 'Was rein soll / Beispiel / Nicht verwechseln mit'. Keine D-20-Verletzungen (keine NERVE-Claims, keine echten Firmen, kein '2,3x ROI')."
    why_human: "Tooltip-Rendering + UX-Groesse + Anti-Pattern-Content-Audit. Claudian-Review in Plan 04 war Erstcheck — post-deploy-Sichtpruefung folgt."
  - test: "Profile-Editor Beispiel-Profil-Modal Open/Close"
    expected: "Klick auf 'Sieh dir ein ausgefuelltes Beispiel an' oeffnet Modal mit 7 Sektionen (Anna S., Firma XY GmbH, Firma Z GmbH). Schliessen per X, Outside-Click und ESC. Nur fiktive Platzhalter."
    why_human: "Modal-Overlay, ESC-Taste-Handler, Outside-Click-Close benoetigen Live-Browser."
  - test: "Profile-Editor Save-Roundtrip mit 4 neuen Feldern (Pitfall 1 Regression)"
    expected: "User fuellt eigene_formulierungen (2 Zeilen), beweise (2 Zeilen), branche_kontext (1 Satz), waehlt branche=Maschinenbau, ton=Direkt/Klartext. Save → Success-Flash. Reload der Seite: ALLE 4 Felder + branche + ton noch befuellt. Kein Data-Loss durch Wholesale-JSON-Replace."
    why_human: "Benoetigt echten POST-Roundtrip auf Flask + DB-Write + Template-Re-Render. JS-Builder-Logik komplex genug um manuellen Smoke-Test zu rechtfertigen."
  - test: "ton-Flex-Escape: 'Eigener Stil' → Freitext-Input erscheint, Value persistiert"
    expected: "User waehlt ton='Eigener Stil...' → Text-Input wird sichtbar. User tippt 'Freundlich aber bestimmt' → Save. Reload zeigt ton-Select auf 'Eigener Stil' + Freitext-Feld mit 'Freundlich aber bestimmt'. Bei leerem Flex → daten.ki.ton='' (nicht der Sentinel-String 'eigener_stil')."
    why_human: "Dynamisches Show/Hide-Element + Save/Load-Interaktion in JS."
---

# Phase 08: EWB-Qualitaet & Profil-Tiefe — Verification Report

**Phase Goal:** EWB-Pipeline liefert konsistent hohe Qualitaet (80% sofort-vorlesbar, Varianz-Range <30 ueber Szenarien A/B/C), A/B-Routing zwischen v1-legacy und v2-modular-Prompt ist live, 6 neue Profil-Felder + 3-Block-Tooltip-System + POLISH-55 3-State-Rating-Infrastruktur bringen die fuer Early-Access-Launch noetige Mess- und Qualitaetsbasis.

**Verified:** 2026-04-22T17:28:47Z
**Status:** human_needed — Infrastruktur komplett verdrahtet; 8 Browser-Smokes und Wave-7 Messung ausstehend
**Re-verification:** Nein (Initial-Verifikation)

## Goal Achievement

Phase 08 hat die fuer Early-Access-Launch noetige **Mess- und Qualitaetsbasis** geliefert. Die Phase definiert explizit keine Quality-Numbers (die misst Wave 7 offline), sondern baut die Infrastruktur um Gates zu messen:

- A/B-Routing live (v1-legacy vs. v2-modular)
- 3-State-Rating-UI (POLISH-55) + Admin-Bulk-Rating-Tool
- 6 neue Profil-Felder in Editor + 3-Block-Tooltip-System
- Quality-Score-Formel (D-27) + Varianz-Range-Query (D-28) im Admin-Dashboard sichtbar

Die tatsaechlichen Quality-Number-Gates (80% >=80, Range <30) sind **Wave-7-Messung**, nicht Teil von Phase 08 Code. Entsprechend fokussiert die Verifikation auf die Infrastruktur.

### Observable Truths

| # | Truth                                                                 | Status      | Evidence |
| - | --------------------------------------------------------------------- | ----------- | -------- |
| 1 | A/B-Routing live (resolve_prompt_version + ENV-Override)              | VERIFIED   | Spot-check: `user_id=0 -> v1-legacy`, `user_id=1 -> v2-modular`. ENV-Override `PROMPT_EWB_VERSION_OVERRIDE=v2-modular` forciert alle User. Live-DB: 2 Rows in prompt_versions (v1-legacy is_default=1, v2-modular is_default=0). |
| 2 | v2-modular Prompt-Seed vorhanden und routbar (_seed_ewb_v2 im Startup) | VERIFIED   | `app.py:765 def _seed_ewb_v2`, call at `app.py:842`. Seed-Text enthaelt ANKER/REFRAME/KERN-GEGENARGUMENT/UEBERLEITUNG + Active Listening + NIEMALS apologetisch + 45 Woerter. Live-DB bestaetigt. |
| 3 | 6 neue Profil-Felder in Editor (branche Enum, branche_kontext, eigene_formulierungen, beweise, ton Flex, zusatz Relabel) | VERIFIED (programmatisch) / HUMAN_NEEDED (UI) | `templates/profile_editor.html` enthaelt alle 6 `id="vi_*"` inputs + 6 `tooltip.tip3(...)` Aufrufe + Populate + buildAndSubmit. Browser-Smoke ausstehend. |
| 4 | POLISH-55 3-State-Rating-Infrastruktur (UI + API + DB) funktional       | VERIFIED (programmatisch) / HUMAN_NEEDED (UI) | `routes/app_routes.py:1414 def api_ewb_rate` mit `isinstance(value, bool) or value is None` + Ownership via ConversationLog.user_id. 12 Tests gruen. Session-Detail-Template hat `rateEwb()` + 3 Buttons. Browser-Smoke fuer UI-Toggle ausstehend. |
| 5 | Admin-Tooling fuer Quality-Gates erreichbar (`/admin/ewb/quality` + `/admin/ewb/rating-template`)       | VERIFIED (programmatisch) / HUMAN_NEEDED (UI) | Blueprint `admin_ewb_bp` registriert in `app.py:1563`. 3 Routes registriert: `/admin/ewb/quality`, `/admin/ewb/rating-template`, `/admin/ewb/rating-template/<int:conv_id>/<path:einwand_key>/rate`. Unauth-GET = 302 redirect. A/B-Query baut 3-stufigen JOIN (ft_objection_events + ft_call_sessions + objection_events). Browser-Smoke ausstehend. |
| 6 | DB-Migrations idempotent angewendet (success nullable, anrede, is_default, ewb_ratings) | VERIFIED   | Live-DB verifiziert: `objection_events.success` notnull=0, `conversation_logs.anrede` existiert, `prompt_versions.is_default` existiert, `ewb_ratings` Table existiert mit 7 Spalten. audit_log marker `migration_v08_01_reset_success_polish38_1` 1x vorhanden (Idempotenz-Check). Backup `database/nerve.db.bak_pre_v08_01` existiert (328 KB). |

**Score:** 6/6 Truths programmatisch VERIFIED. 8 manuelle Browser-Smokes sind in `human_verification` gelistet — diese sind nicht-blockierend fuer den Code-Zustand aber erforderlich fuer Deploy-Tag.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `services/prompt_pipeline.py` | 4 Exports (resolve_prompt_version, build_profile_context, log_pipeline_event, invalidate_resolver_cache), >=120 LOC, side-effect-frei | VERIFIED | 237 LOC. Alle 4 Exports definiert. LAZY DB-Imports innerhalb Funktionen. `(module, user_id)` Cache-Key. ENV-First-Check vor Cache-Hit. `Wechsle NIEMALS` wortwoertlich. |
| `services/ewb_pipeline.py` | build_ewb_prompt Export + _FALLBACK_V1_PROMPT, >=60 LOC | VERIFIED | 89 LOC. `build_ewb_prompt(profile_data, anrede, version, user_id)`. Fallback-Prompt definiert. Importiert `build_profile_context` aus prompt_pipeline. Logging-Prefix `[EWB]`. |
| `services/claude_service.py` (Edits) | 2 Call-Sites swappen `_build_system_prompt()` gegen `build_ewb_prompt`; Legacy-Symbole preservieren | VERIFIED | `analysiere_mit_claude` (line 646-672) und `analysiere_mit_claude_streaming` (line 714-740) nutzen `resolve_prompt_version('ewb', user_id)` + `build_ewb_prompt(...)`. `_build_system_prompt` nicht geloescht (bleibt fuer 4 Legacy-Module). Haiku-Model unveraendert. |
| `database/models.py` (Edits) | 3 Column-Changes + neue EwbRating-Klasse | VERIFIED | `ObjectionEvent.success = Column(Boolean, default=None, nullable=True)` line 352. `ConversationLog.anrede = Column(String(10), nullable=True)` line 285. `PromptVersion.is_default = Column(Boolean, default=False, nullable=False)` line 508. `EwbRating` class line 356 mit UniqueConstraint + quality_score-Property (D-27-Formel). |
| `app.py` (Edits) | 5 Migration-Bloecke (A-E) + _seed_ewb_v2 + _seed_ewb_scenarios + admin_ewb_bp register | VERIFIED | Bloecke markiert mit `# -- Phase 08 D-01/D-02/D-14/D-26`. `_seed_ewb_v2` line 765, call line 842. `_seed_ewb_scenarios` line 847, call line 941. `from routes.admin_ewb import admin_ewb_bp` line 1559, register line 1563. Backup-Block (A) + Table-Rebuild (B) + audit_log-Marker (C) + ADD COLUMN anrede (D) + ADD COLUMN is_default + backfill (E). |
| `routes/admin_ewb.py` | Blueprint mit 3 Routes, >=120 LOC | VERIFIED | 197 LOC. Blueprint-Import + 3 decorated routes (`/quality`, `/rating-template`, `/rating-template/<int:conv_id>/<path:einwand_key>/rate`). Alle `@login_required + @superadmin_required`. A/B-Query aus RESEARCH Focus Area 3. Strict Boolean-Check in ewb_rating_save. |
| `routes/profiles.py` (Edits) | VALID_BRANCHE Whitelist + Fallback 'sonstiges' | VERIFIED | `VALID_BRANCHE = {...}` line 14 mit 8 Enum-Werten + empty-string. `_normalize_branche` helper line 27. Check in 3 Routes (bearbeiten/neu/wizard_create). |
| `routes/app_routes.py` (Edits) | api_ewb_rate endpoint + session_anrede-read + ConversationLog.anrede persist | VERIFIED | `api_ewb_rate` line 1414 mit strict `isinstance(value, bool) or value is None` + Ownership via ConversationLog. session_anrede-Read line 416 unter `state_lock`. `anrede=_session_anrede` line 452 bei ConversationLog-Create. |
| `services/deepgram_service.py` (Edits) | Anrede-Whitelist-Hook in handle_start_live_session | VERIFIED | line 298-301: `if anrede_raw in ('Du', 'Sie'): with ls.state_lock: ls.state['session_anrede'] = anrede_raw`. Fail-closed bei invalid input. |
| `templates/_tooltip.html` | Jinja-Macro tip3, >=15 LOC | VERIFIED | 26 LOC. Macro `tip3(was_rein, beispiel, nicht_verwechseln)` mit 3 data-attribs + tabindex + role + aria-label. |
| `templates/_beispiel_profil_modal.html` | Read-Only Modal mit 7 Sektionen, >=60 LOC | VERIFIED | 80 LOC. Overlay + Box + Close-Button. 7 Sektionen (Basis, Branche+Kontext, Eigene Formulierungen, Beweise, Stil, Spezielle Anweisungen, Einwaende) mit fiktiven Platzhaltern. Nach Claudian-Fix (commit 4cef4b1) D-20-compliant. |
| `templates/profile_editor.html` (Edits) | 6 tip3-Aufrufe + Modal-Include + 4 neue Felder + ton-Flex + zusatz-Relabel + Dual-Mode-Handler | VERIFIED | Grep bestaetigt alle id="vi_*" + `tooltip.tip3(` + `openBeispiel` + Setzen/Lesen-Roundtrip. buildAndSubmit (Zeile 1096-1106) und Populate (Zeile 1252-1254) komplett verdrahtet. |
| `templates/session_detail.html` (Edits) | Benefit-Framing-Text wortwoertlich + 3-Button-Rating + rateEwb() | VERIFIED | `Hilf uns, dir zu helfen` + `Wie empfandest du` + `Basierend auf deinen Antworten` vorhanden. `rateEwb(ev.id, true/false/null, this)` 3 onclick-Handlers. Aria-role="radiogroup". |
| `static/pip-launcher.js` (Edits) | savedAnrede + launcher-anrede-row + _setAnrede + emit anrede | VERIFIED | Grep zeigt 14+ Matches fuer anrede-related patterns: `launcher-anrede-btn` (HTML), `_setAnrede` (helper + public API), `state.precallFormData.anrede` (save/load/emit). |
| `static/nerve.css` (Edits) | .tip-icon >=16px + #g-tip 3-Block + .beispiel-overlay + .n-ewb-btn-* + .launcher-anrede-* | VERIFIED | Von Plan 04 und Plan 05 bestaetigt: 16px `.tip-icon` + `.tip-block` + `.beispiel-overlay` + `.n-ewb-btn--active/--success/--danger/--neutral` + `.launcher-anrede-row/-btn`. |
| `templates/admin/ewb_quality.html` | A/B-Tabelle + 3 Metric-Cards, >=50 LOC | VERIFIED | 128 LOC. A/B-Auswertung + Quality-Score (3 Metric-Boxes) + Varianz-Range mit conditional `ewb-metric--pass`/`ewb-metric--fail` styling. |
| `templates/admin/ewb_rating_template.html` | Bulk-Rating-UI mit 3 Radio-Paaren pro Row, >=60 LOC | VERIFIED | 152 LOC. 6-Spalten-Tabelle (Session, Einwand, klingt, halluzi, trifft). Auto-Save bei 3. Radio-Click. POST fetch + Success/Error Flash. |
| `scripts/migrate_branche_to_enum.py` | CLI mit dry-run/run, Heuristik-Map, Append-Kontext, >=100 LOC | VERIFIED | 211 LOC. 5 Funktionen (_normalize_branche, _map_branche_to_enum, _migrate_profile_branche, _run, _main). 8 Enums + Priority-Chain. `--run` noch nicht ausgefuehrt (Deploy-Tag-Entscheidung). |
| `docs/phase-08-training-vs-live-prompt-gap.md` | Gap-Matrix, >=40 LOC mit >=14 Tabellen-Zeilen | VERIFIED | 112 LOC. Gap-Matrix + Code-Stellen fuer Wave 2 + Anti-Regression-Checks. |
| `database/nerve.db.bak_pre_v08_01` | Backup-File (Safety-Net fuer D-02 destructive migration) | VERIFIED | 328 KB Backup existiert. |
| Test-Dateien | 8 neue Test-Files mit 70+ Tests | VERIFIED | `test_phase_08_models.py` (4), `test_phase_08_migration.py` (6), `test_prompt_pipeline.py` (11), `test_ewb_pipeline.py` (6), `test_claude_service_phase08.py` (7), `test_branche_migration.py` (16), `test_ewb_rate_api.py` (12), `test_ab_stats.py` (9). **Gesamt: 71/71 gruen in 3.10s** (voll isoliert). |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `services/claude_service.py analysiere_mit_claude/streaming` | `services.ewb_pipeline.build_ewb_prompt` | `system=build_ewb_prompt(...)` in 2 Call-Sites | WIRED | 2 Marker `# -- Phase 08 EWB-Pipeline Integration` an Zeilen 646 und 714. `resolve_prompt_version('ewb', _user_id)` + `build_ewb_prompt(...)` in beiden Call-Sites. |
| `services/ewb_pipeline.py` | `services/prompt_pipeline.py build_profile_context` | Import + Call in `build_ewb_prompt` | WIRED | `from services.prompt_pipeline import build_profile_context` line 19. Call in line 54. |
| `services/prompt_pipeline.py` | `prompt_versions` table | SessionLocal().query(PromptVersion).filter_by(module=X, is_active=True) | WIRED | `_load_active_variants` line 73. Lazy-Import. try/finally. Fallback `['unknown']` bei DB-Error. |
| `services/deepgram_service.py handle_start_live_session` | `ls.state['session_anrede']` | whitelist-check + `with ls.state_lock` | WIRED | line 298-301. |
| `routes/app_routes.py /api/beenden` | `conversation_logs.anrede` | `anrede=_session_anrede` in ConversationLog(...) | WIRED | line 452. Read aus `ls.state.get('session_anrede')` unter state_lock line 411-418. |
| `routes/app_routes.py api_ewb_rate` | `objection_events.success` | UPDATE via `ev.success = value` + ownership via ConversationLog | WIRED | line 1446. 403 bei cross-user (ownership-check line 1441-1445). |
| `static/pip-launcher.js` | Socket.IO-Emit payload | `emit('start_live_session', { ..., anrede: anredeForSession })` | WIRED | Plan 05 SUMMARY dokumentiert emit at line 985. `_setAnrede` Helper + `state.precallFormData.anrede` Persist. |
| `templates/session_detail.html rateEwb()` | `POST /api/ewb/<id>/rate` | fetch + JSON | WIRED | Plan 05 dokumentiert Zeile 465-498. Spot-check: Grep bestaetigt `rateEwb` (6 Matches) + `fetch.*api/ewb` (2 Matches). |
| `routes/admin_ewb.py` | `ewb_ratings` + `ft_objection_events` + `ft_call_sessions` + `objection_events` + `conversation_logs` | JOIN-Queries | WIRED | A/B-Query line 39-51 (3-stufig). LEFT-JOIN in rating-template line 108-124. UPDATE-or-INSERT in save line 170-189. |
| `app.py _seed_ewb_v2()` | `prompt_versions` (module='ewb') | existing-row-check + is_default-reconciliation | WIRED | line 765 def + line 842 call. Idempotent. Live-DB bestaetigt 2 Rows. |
| `app.py _seed_ewb_scenarios()` | `training_scenarios` (name LIKE '[P08-%') | name-based idempotent-check, erstellt_von=None | WIRED | line 847 def + line 941 call. 3 Rows in Live-DB, alle erstellt_von=NULL. |
| `templates/profile_editor.html` | `daten.basis.*` via JSON-Merge | buildAndSubmit (3 neue Keys) + Populate (3 setVal) | WIRED | eigene_formulierungen Array at line 1097-1099, beweise Array at 1101-1103, branche_kontext String at 1105-1106. Populate line 1252-1254. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `/admin/ewb/quality` A/B-Tabelle | `ab_rows` | `db.execute(text(3-stage-JOIN-query))` mit echten FK-Joins | Ja (wenn success IS NOT NULL vorhanden) / Leer-State-Handler wenn keine Ratings | FLOWING |
| `/admin/ewb/quality` Score-Gate | `scores = [r.quality_score for r in rating_rows]` | `db.query(EwbRating).all()` | Ja | FLOWING |
| `/admin/ewb/quality` Varianz-Range | `session_scores` | `SELECT COALESCE(kb_end, 0) FROM conversation_logs WHERE id IN (...)` | Ja (kb_end-Spalte existiert in DB) | FLOWING |
| `/admin/ewb/rating-template` Events-Liste | `events` | LEFT-JOIN `objection_events + conversation_logs + ewb_ratings` | Ja | FLOWING |
| `session_detail.html` Einwand-Timeline | `events` (Route dashboard.session_detail) | `db.query(ObjectionEvent).filter(conversation_log_id=sid)` | Ja (wird von dashboard.py geladen, unveraendert durch Plan 05) | FLOWING |
| `build_ewb_prompt` -> system_prompt in Live-EWB-Call | `_system_prompt` | `build_ewb_prompt(version=resolved, user_id=_user_id)` | Ja (liest prompt_versions real + build_profile_context real) | FLOWING (behavioral spot-check: v1-legacy=383 chars, v2-modular=1226 chars) |
| `profile_editor.html` new fields Render | `basis.eigene_formulierungen / beweise / branche_kontext` | Jinja `{{ profile.daten \| safe }}` → DATEN JS-Var → populate | Ja (Save/Load-Roundtrip) | HUMAN_NEEDED (Browser-Smoke #7 wegen Pitfall-1-Regression-Pruefung) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| A/B-Routing deterministisch | `resolve_prompt_version('ewb', 0)` + `resolve_prompt_version('ewb', 1)` | `v1-legacy` und `v2-modular` (verschiedene Varianten) | PASS |
| ENV-Override aktiv | `PROMPT_EWB_VERSION_OVERRIDE=v2-modular`; `resolve_prompt_version('ewb', 42)` | `v2-modular` (Override gewinnt) | PASS |
| v2-modular enthaelt alle Bausteine | `build_ewb_prompt(version='v2-modular', anrede='Du', user_id=1)` | ANKER + Active Listening + NIEMALS apologetisch + Anrede Du + Wechsle NIEMALS | PASS |
| Admin-Routes registriert + Auth-Gate | `app.url_map` inspection + `client.get('/admin/ewb/quality')` | 3 Routes, 302 redirect bei unauth | PASS |
| Migrationen angewendet + idempotent | Full-DB-PRAGMA-Sweep + audit-log-marker-Count | Alle 4 Schema-Aenderungen vorhanden + marker Count=1 auch nach 3+ Re-Runs | PASS |
| Phase-08 Test-Suite | `pytest tests/test_ab_stats.py test_ewb_rate_api.py test_prompt_pipeline.py test_ewb_pipeline.py test_phase_08_models.py test_phase_08_migration.py test_branche_migration.py test_claude_service_phase08.py -x` | **71/71 gruen in 3.10s** | PASS |
| Full Test Suite | `pytest tests/ --tb=no -q` | 229 passed, 2 failed (pre-existing `test_exchange_rates.py` Phase 4.7.2), 1 skipped. Phase-08 komplett gruen. | PASS (Phase 08 scope) |

### Requirements Coverage

**Quell-Nutzung:** Phase 08 deriviert EWB-01 bis EWB-20 in `08-RESEARCH.md §Phase Requirements`. Diese IDs sind noch NICHT in REQUIREMENTS.md back-portiert (Grep auf REQUIREMENTS.md findet 0 Matches). Das ist dokumentiert in ROADMAP.md Zeile 624 als "to be back-ported" und fuer Phase 08 akzeptabel (Prozess-Sache, kein Code-Gap).

Alle 20 Requirements sind via PLAN-Frontmatter `requirements:` an konkrete Plans gebunden:

| Requirement | Source Plan | Beschreibung (aus RESEARCH / LOCKED Decisions) | Status | Evidence |
| ----------- | ----------- | ---------------------------------------------- | ------ | -------- |
| EWB-01 | 08-01 | objection_events.success nullable (D-01 3-state) | SATISFIED | `database/models.py:352` + Live-DB-PRAGMA |
| EWB-02 | 08-01 | POLISH-38.1 Alt-Daten reset auf NULL + audit_log marker (D-02) | SATISFIED | Block C in app.py:561 + marker-Row in audit_log |
| EWB-03 | 08-05 | POLISH-55 3-Button-Rating-UI (D-03 Benefit-Framing wortwoertlich + D-04 Kein-Submit) | SATISFIED (Code) / NEEDS HUMAN (UI) | Benefit-Framing + 3 Buttons im session_detail.html. Browser-Smoke ausstehend. |
| EWB-04 | 08-04 | 6 Profil-Felder live (D-07/08/09/10/11/12/13) | SATISFIED (Code) / NEEDS HUMAN (UI) | Alle 6 in profile_editor.html. Save-Roundtrip-Smoke ausstehend. |
| EWB-05 | 08-03 | branche Freitext→Enum-Heuristik-Migration (D-09) | SATISFIED | `scripts/migrate_branche_to_enum.py` + 16 Tests gruen. `--run` noch nicht ausgefuehrt auf Prod (Deploy-Tag). |
| EWB-06 | 08-01, 08-05 | conversation_logs.anrede + PreCall-Anrede-Override (D-14) | SATISFIED (Code) / NEEDS HUMAN (UI) | Column + ls.state-Hook + Persist-Path + pip-launcher-UI. Live-Socket.IO-Test ausstehend. |
| EWB-07 | 08-04 | 3-Block-Tooltip-System + i-Button >=16px (D-16/17/18) | SATISFIED (Code) / NEEDS HUMAN (UI) | Jinja-Macro + Dual-Mode-Display-Handler + 16px CSS. Tooltip-Hover-Smoke ausstehend. |
| EWB-08 | 08-04 | Read-Only Beispiel-Profil-Modal (D-19) | SATISFIED (Code) / NEEDS HUMAN (UI) | `_beispiel_profil_modal.html` + Open/Close-JS. Modal-Display-Smoke ausstehend. |
| EWB-09 | 08-02, 08-03 | A/B-Routing resolve_prompt_version + ENV-Override (D-23/D-24/D-25) | SATISFIED | Spot-check bestaetigt deterministic routing + ENV-override + claude_service hot-swap. |
| EWB-10 | 08-01, 08-02 | prompt_versions.is_default + Seed v2-modular (D-26 + D-41) | SATISFIED | is_default-Column + _seed_ewb_v2 + 2 Rows in Live-DB. |
| EWB-11 | 08-02 | services/prompt_pipeline.py Shared-Utils (D-40) | SATISFIED | 4 Exports in 237 LOC + 11 Unit-Tests gruen. |
| EWB-12 | 08-02 | services/ewb_pipeline.py modul-spezifische Assembly (D-41) | SATISFIED | 89 LOC + 6 Tests gruen. |
| EWB-13 | 08-02, 08-03 | D-15 Anrede-Constraint wortwoertlich "Wechsle NIEMALS..." | SATISFIED | prompt_pipeline.py:188 + ewb_pipeline.py:60 (Fallback). Spot-check bestaetigt. |
| EWB-14 | 08-02 | Active-Listening-Block im v2-modular-Seed (D-47) | SATISFIED | Grep auf app.py bestaetigt "Active Listening"-Block mit 5 Regeln. |
| EWB-15 | 08-06 | EwbRating-Model + Quality-Score-Property (D-27 Formel) | SATISFIED | `class EwbRating` + `@property quality_score` + UniqueConstraint. 9 Tests gruen. |
| EWB-16 | 08-06 | Admin-Dashboard /admin/ewb/quality + Rating-Tool (D-30/31/35) | SATISFIED (Code) / NEEDS HUMAN (UI) | 3 Routes + 2 Templates. Browser-Smoke ausstehend. |
| EWB-17 | 08-03, 08-06 | 3-stufiger JOIN-Query fuer A/B-Auswertung (D-22 RESEARCH Focus Area 3) | SATISFIED | routes/admin_ewb.py:39-51 + Integration-Test `test_ab_stats_join_success_rate` gruen. |
| EWB-18 | 08-02 | Caching per (module, user_id) (W-7 Fix gegen Single-Variant-Sticky) | SATISFIED | prompt_pipeline.py:25 `_RESOLVER_CACHE` + `cache_key = (module, user_id)` + Test `test_cache_per_user_key` gruen. |
| EWB-19 | 08-02 | Build_profile_context liest alle Phase-08-Felder + Anrede-Resolution | SATISFIED | Zeile 162-189. Test `test_build_profile_context_includes_phase_08_fields` gruen. |
| EWB-20 | 08-06 | 3 Test-Szenarien A/B/C als System-Training-Scenarios (D-34) | SATISFIED | `_seed_ewb_scenarios` + 3 Rows in training_scenarios mit erstellt_von=NULL. |

**Keine ORPHANED Requirements.** Alle 20 Requirements IDs sind von genau einem (oder mehreren) der 6 Plans claimed und programmatisch belegt.

### Known Advisory Issues (aus 08-REVIEW.md)

Nicht-blockierend fuer Phase-08-Goal. Scheduled fuer Follow-up (siehe 08-REVIEW.md §Empfehlungen):

- **CR-01 (Critical)**: Race Condition beim Lesen von `ls.state['session_anrede']` ohne state_lock in `services/prompt_pipeline.py:196-204` + `services/claude_service.py:659,722`. Pre-Launch MUST-FIX. Kein Daten-Verlust, aber inkonsistente A/B-Zuordnung moeglich.
- **CR-02 (Critical)**: Weak Whitelist `anrede_raw in ('Du', 'Sie')` in `services/deepgram_service.py:297-301` akzeptiert keine Mixed-Case (`'du'`, `' Du'`). Frontend filtert bereits — defense-in-depth-Luecke. Pre-Launch MUST-FIX.
- **WR-01 bis WR-09** (Warning): siehe 08-REVIEW.md. Insbesondere WR-04 (`path:einwand_key` vs. `encodeURIComponent` konflikt bei Einwand-Typen mit Slashes wie 'Zeit/Aufschub'), WR-03 (inkonsistente Profil-Einwand-Match-Logic in 3 Code-Pfaden), WR-05 (`_seed_ewb_v2` reconciled is_default bei jedem Start → Admin-Override verhindert).
- **IN-01 bis IN-07** (Info): Test-Fixture-Duplikation, Dead-Code in Legacy-Modulen, CSS-Regel ohne HTML-Match.

**Alle 18 Findings explizit nicht-blockierend** — Phase 08 Goal hat Infrastruktur geliefert, Code-Review-Fixes sind Pre-Launch-Hardening (Phase 08.1 oder direkt via /gsd-code-review-fix).

### Anti-Patterns Found

Aus Plan 04 Claudian-Review und Code-Stand bei Verifikation:

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `templates/profile_editor.html`, `templates/_beispiel_profil_modal.html` | 378, 43 | "2,3x ROI" in Beweise-Example/Modal (D-20 Violation) | Info (bereits gefixt) | Fix-Commit `4cef4b1`: Ersetzt durch "Durchschnitt: 15.000 EUR Ersparnis pro Quartal". Claudian-Review D-21 Launch-Gate passed nach diesem Fix. |
| (keine weiteren) | - | - | - | Keine TODO/FIXME/Placeholder in neuen Phase-08-Dateien gefunden. |

### Human Verification Required

Siehe YAML-Frontmatter `human_verification`. 8 Browser-Smoke-Steps von den urspruenglich 16 (aus Plan 04 Task 3 + Plan 06 Task 3) die unter `workflow.auto_advance=true` auto-approved wurden. Sie sind nicht-blockierend fuer Code, aber Deploy-Tag-Items:

1. **Admin-Dashboard /admin/ewb/quality visuell rendern** — CSS-Conditional-Styling (pass/fail), Template-Render
2. **Admin-Rating-Tool 3-Kriterien-Roundtrip** — Radio-JS + AJAX-Save + DB-Persist
3. **PreCall-Anrede-Wahl in PiP-Launcher** — Socket.IO-Emit + ls.state + DB-Persist
4. **Session-Detail 3-Button-Rating** — Visual-Toggle + Network-Tab + Aria
5. **Profile-Editor Tooltip-3-Block-Display** — Hover/Focus, 16px-Size, D-20-Content-Sichtpruefung
6. **Profile-Editor Beispiel-Profil-Modal** — Open/Close + ESC + Outside-Click
7. **Profile-Editor Save-Roundtrip Pitfall-1-Regression** — 4 neue Felder, Reload, keine Data-Loss
8. **ton-Flex-Escape Dynamic-Show/Hide** — Select-Change + Freitext-Save

### Gaps Summary

**Keine Goal-blockierenden Gaps.** Phase 08 hat die Mess- und Qualitaetsbasis fuer Early-Access-Launch komplett geliefert:

- A/B-Routing live (deterministic + ENV-Override) - **funktional verifiziert**
- 6 neue Profil-Felder + 3-Block-Tooltips - **Code verdrahtet, UI-Smoke ausstehend**
- POLISH-55 3-State-Rating (UI + API + DB) - **Backend verifiziert, UI-Smoke ausstehend**
- Admin-Tooling fuer Quality-Gates (/admin/ewb/quality + rating-template) - **Routes + Templates + Queries verifiziert, Browser-Rendering ausstehend**
- DB-Migrations idempotent angewendet - **vollstaendig verifiziert**

**Was Phase 08 bewusst NICHT liefert** (per Plan):
- **Quality-Gate-Messung selbst** (80/80 Score, Range<30) — das ist Wave 7 offline-Messung, kein Code-Deliverable
- **18 Code-Review-Findings aus 08-REVIEW.md** — Pre-Launch-Hardening, Post-Phase-08-Scope (Phase 08.1 oder /gsd-code-review-fix)
- **Production-Deploy-Tag-Items** (scripts/migrate_branche_to_enum.py --run, 8 Browser-Smokes, A/B-Dashboard-Refresh nach ersten Ratings)

**Status-Begruendung:** `human_needed` weil die Phase-Success explizit UI-Smokes erfordert. Auto-Mode hat die UI-Checkpoints auto-approved, was Code-komplett ist, aber die 8 manuellen Sichtpruefungen am Deploy-Tag muessen stattfinden bevor Launch. Keine `gaps_found` - alle Pfade funktional vorhanden.

---

_Verified: 2026-04-22T17:28:47Z_
_Verifier: Claude (gsd-verifier) — Model Opus 4.7 (1M context)_
