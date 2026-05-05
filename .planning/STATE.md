---
gsd_state_version: 1.0
milestone: v0.9.4
milestone_name: milestone
status: In Progress
stopped_at: "08.19.5.6 Plan 01 COMPLETE — Frontend 4-Tab-UI renderStep5() + modus-abhaengige Personalisierung abgeschlossen"
last_updated: "2026-05-05T17:16:00.000Z"
last_activity: 2026-05-05
progress:
  total_phases: 64
  completed_phases: 50
  total_plans: 221
  completed_plans: 212
  percent: 96
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-13)

**Core value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.
**Current focus:** 08.19.5.1 VERIFIED — WR-01 + WR-02 per-SID migration complete. Multi-User-Daten-Trennung 100% abgeschlossen.

## Current Position

Phase: 08.19.5.6 (4-reiter-ui-skript-opener-auswahl-briefing-skript-merge) — Plan 01 + 02 COMPLETE
Plan: 1 — Plan 01 COMPLETE (2026-05-05)
Last activity: 2026-05-05

**Phase 08.19.5.6 Plan 01 abgeschlossen:** Frontend 4-Tab-UI renderStep5() — state.activeTab + selectedErlaubnisId + selectedPitchId + window.switchTab5(). renderStep5() von flachem Auswahl-UI zu 4-Tab-Layout umgebaut (Opener/Erlaubnisfrage/Pitch/Skript). openerItems-Filterung nach o.type. Leerstand-States pro Tab mit /profiles-Link. Titel "Gesprächsvorbereitung". Vorwissen + Anrede immer sichtbar. Personalisieren-Button modus-abhängig (Cold-Call→Opener-Tab, Meeting→Skript-Tab). renderStep4b/4c/_savePersonalizedAndStartCall/cap-modal alle modus-abhängig umgestellt. _collectEditedTexts() Guard-Fix. OD-01 Pitch/Skript-Priorität via _resolvedTeleprompterSkript. Deviation: fcd-tab CSS in base.html eingefügt. 4 Commits: 6446f4d, 90557dc, 91491d8, 487b806.

**Phase 08.19.5.6 Plan 02 abgeschlossen:** Backend call_mode-Routing fuer KI-Personalisierung — ProfileSkript + 3 neue Columns (is_personalized, parent_id ohne FK, briefing_source_firma). DB-Migration idempotent in app.py. api_personalize_skript() auf call_mode-Routing umgestellt (meeting->ProfileSkript, cold_call->ProfileOpener, Fallback ohne call_mode). api_personalize_skript_save() Cap-Check + Delete + Insert IMMER gegen ProfileSkript (kein ProfileOpener-Insert mehr). 4 Commits: 0c1221a, dbeec58, 7d8ca8f, 950337b. Decisions: D-04 parent_id ohne FK-Constraint, Cap gegen ProfileSkript in beiden Modi.

**Phase 08.19.5.4 Plan 02 abgeschlossen:** Wave 2 Modal-Neubau — .n-modal-overlay/.n-modal-card/.n-modal-actions CSS-Klassen in nerve.css (Design-Tokens, keine hardcoded Farben). nerveNavModal HTML in base.html vor </body>. window._nerveNavConfirm() als window-Property (global aus onclick erreichbar). Click-Interceptor via Event-Delegation auf document (.closest('.n-nav-item, a.popup-item-logout')). ESC + Overlay-Klick schliessen Modal ohne Navigation. beforeunload unveraendert. 2 Commits: 4cbb385, acea0d3. Decisions: n-btn-ghost/n-btn-danger pre-existing (kein Fallback), Event-Delegation statt querySelectorAll (DOM-Timing-sicher).

**Phase 08.19.5.4 Plan 01 abgeschlossen:** Wave 1 Token-Migration — 10 App-Templates (coach_dashboard, coach_firma, coach_methodik, team, register, changelog, waitlist_admin, kpi_dashboard, dashboard, logs_page) auf nerve.css Design-Tokens migriert. .badge-gray bereinigt. landing.html nach templates/marketing/ verschoben. render_template-Pfade in dashboard.py aktualisiert. 3 Commits: b0b7a77, 4c40ff9, 668f1f8. Decisions: Semantisches Token-Mapping (#0c0c18 body->--page-bg, card->--glass-bg), Chart.js direkte Hex-Farbe (#00D4AA), register.html nerve.css-Link ergaenzt.

**Phase 08.19.5.2 Plan 05 abgeschlossen:** PiP Re-Launch-Flow + Nav-Label-Fix — Nav-Label "Profil"→"Profile" (base.html:56), localStorage nerve_pip_was_active Flag im pagehide-Handler, Re-Launch-Banner vor </body>, removeItem in _stopMic(). MEDIUM-3 Cross-AI: PiP State-Loss v1 akzeptiert (SPEC Fallback-Acceptance, D-12). 2 Commits: fca5360, 7028259.

**Phase 08.19.5.2 Plan 04 abgeschlossen:** Session-Row onclick-Handler — `db2-session-row`-div in renderSessions() erhaelt onclick="location.href='/session/'+s.id" + style="cursor:pointer". Ein-Zeilen-Fix, Pattern konsistent mit renderRecommendations(). 1 Commit: 2f37d45.

**Phase 08.19.5.1 Plan 01 abgeschlossen:** WR-01 + WR-02 nachmigiert — `_write_ft_assistant_event` liest per-SID aus `_session_state[sid]` (kein `ls.state` Global mehr); `analyse_loop` Learning-Cards-Read per-SID isoliert. 2 neue Isolation-Tests in test_per_sid_migration.py. 4 Tests in test_ft_write_hooks.py auf neues sid-API aktualisiert. 10/10 Tests gruen. 3 Commits: 5854598, 5ee13cf, d4c45b3. Decisions: D-01 Return-Early bei sid=None, D-03 einmaliger _session_state_lock Block.

**Phase 08.19.5 Plan 04 abgeschlossen:** Wave 3 test suite — created tests/test_per_sid_migration.py with 4 Function-Call-Return-Tests (REQ-01 is_paused isolation, REQ-06 _load_profile_cache, REQ-07 vorwissen_level chain, REQ-08 ewb_variante error propagation). Fixed 2 pre-existing failures in test_session_scoping.py by adding init_session_state() before set_profile_for_sid() (Ghost-SID-Guard FINDING-05). 2 commits: 45a152c, 8916a77.

**Phase 08.19.5 Plan 03 abgeschlossen:** Global pause guards (ls.pause_lock/ls.is_paused) removed from analyse_loop and coaching_loop; per-SID `sid_state.get('state',{}).get('is_paused',False)` checks added. 3 Phase-Classifier ls.analysiert_bisher global reads (lines ~1023/1059/1093) replaced with sid_state.get('analysiert_bisher',[]). HIGH-1 pre-check confirmed no hidden global writes. REQ-01 + REQ-02 complete across all services/. 1 commit: b87bbdc.

**Phase 08.19.5 Plan 02 abgeschlossen:** init_session_state() extended with 14 per-SID sub-keys (state{} with is_paused, session_meta{}, phasen_log, analysiert_bisher, etc.). get_sid_paused(sid) added. next_line_id(sid), stabilize_speaker(sid, raw), load_learning_cards(sid, user_id) migrated. _flush_segment() writes speech stats per-SID. deepgram_service.py: is_paused reads replaced with get_sid_paused(), handle_connect() WS auth added (return False for unauth), ls.analysiert_bisher reads (lines ~154, ~587) migrated to per-SID. reset_session() updated with pop+init loop (1 external caller). 3 commits: 0a59780, ea91fa3, 2986c3c.

**Phase 08.19.5 Plan 01 abgeschlossen:** ft_objection_events + ft_qa_events dropped (REQ-05), /api/feedback renamed to /api/session-rating (D-02/REQ-04, CASE A — no FE caller), streame_manual_ewb_variante() propagates build_profile_context errors (REQ-08). test_ab_stats.py cleaned of dead FtObjectionEvent tests. 4 commits: b630cd7, 7f78f41, 31be646, 73d053f.

**Phase 08.20.3 Plan 03 abgeschlossen:** DB-Foundation (parent_id, is_personalized, briefing_source_firma), PERSONALIZED_SCRIPTS_CAP config, tests/test_08_20_3.py mit 6 Klassen (23 passed/5 skipped), Profile-Editor Opener Filter-Toggle mit Cap-Status.
**Phase 08.20.3 Plan 04 abgeschlossen:** PiP #pip-briefing-tab DOM in base.html, 7 Edits in pip-launcher.js (4 state keys, renderStep() pre-check, Briefing Tab show/hide/toggle/auto-collapse, education hint, window.mdToHtml expose). Tests: 4 passed.
**Phase 08.20.3 Plan 01 abgeschlossen:** renderStep4() 3-Button Modus-Selector (A/B/C), renderStep4b() KI-Ladescreen mit AbortController, renderStep4c() Vorher/Nachher, _savePersonalizedAndStartCall() + _showCapSubModal(), renderStep5() optgroup-Dropdown + Personalisieren-Button. API: is_personalized + briefing_source_firma in opener responses. Tests: 23 passed/5 skipped.
**Phase 08.20.3 Plan 02 abgeschlossen:** generate_personalized_skript() in precall_service.py (Sonnet via MODEL_PRECALL, cost tracking context_tag='personalize_skript', tuple return), POST /api/precall/personalize (KI-only, no DB write), POST /api/precall/personalize/save (atomic with _db.begin(), cap-check, DSGVO-Audit-Log, briefing_source_firma). Tests: 28 passed.
**Next:** Plan 05 (Call-Flow Integration — briefingModus state konsumieren)

**Decisions made (08.19.5.1):**

  - D-01: sid=None -> Return-Early in _write_ft_assistant_event (kein DB-Write, kein Global-Read) — DSGVO-sicher
  - D-03: Einmaliger _session_state_lock Block fuer alle per-SID Reads in _write_ft_assistant_event (kein Split-Read, kein state_lock mehr in dieser Funktion)

**Decisions made (08.20):**

  - D-09: Briefing als _session_state[sid]['_briefing'] Sub-Key (nicht separater Dict) — eliminiert Deadlock-Risiko
  - D-02/D-10: branchen_data.py als pure static module, keine I/O, 10 Cluster + Default-Block
  - D-04: einwaende -> einwaende_detail Migration v3->v4, idempotent, alle 11 Callsites mit Transition-Fallback
  - D-01: build_profile_context() 9-Sektionen Markdown, deterministic, leere Sektionen nie skippen
  - HIGH-3: _profile_cache warm-path 0 DB-Queries; ProfileOpener field=inhalt (nicht content)
  - LB-3-Fix: build_profile_context errors in generate_qa_response non-fatal; QA sieht jetzt Voll-Profil
  - D-02/D-03: branchen hint injection + Anti-Header-Constraint in PreCall system prompt
  - D-07 LOCKED: MODEL_PIP_AUTOVAR + MODEL_PIP_VARIANTE = claude-sonnet-4-5-20251022; rollback ENV documented in config.py
  - 08.20.3-03: SQLite FK L5 — ALTER TABLE uses INTEGER only (no REFERENCES); FK only in SQLAlchemy model
  - 08.20.3-03: PERSONALIZED_SCRIPTS_CAP = 20 default; ENV-overridable via int(os.environ.get(...))
  - 08.20.3-03: opener_liste() backward-compat — plain array for all/standard, {items, cap_status} for personalized
  - 08.20.3-04: pipEl() exclusiv fuer pip-briefing-tab — kein document.getElementById direkt (L2 compliance)
  - 08.20.3-04: window.mdToHtml am IIFE-Ende exposed — alle Consumer laden nach pip-launcher.js (Script-Order)
  - 08.20.3-04: briefingTabExpandedAtStreamStart guard verhindert Re-Expand waehrend Streaming
  - 08.20.3-01: briefingText save-back in allen 3 Modus A/B/C Handlern beibehalten (User kann Analyse in Step 4 noch bearbeiten)
  - 08.20.3-01: opGroupOther nach id desc sortiert (neuere personalisierte Items oben in Sektion 3)
  - 08.20.3-01: Auto-Select wenn genau 1 opGroupCurrent Item existiert (state.selectedOpenerId auto-gesetzt)

Progress: [█████████░] ~94% (Phase 2 ✓, Phase 3 ✓, Phase 3.1 ✓, Phase 04.8.1 ✓, Phase 04.10.1 ✓, Phase 06.2 ✓, Phase 07.2 ✓, Phase 08.5 ✓, Phase 08.6 ✓, Phase 08.7 ✓, Phase 08.8 ✓)

## Performance Metrics

**Velocity:**

- Total plans completed: 28
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 04.6.1 | 3 | - | - |
| 04.9 | 5 | - | - |
| 04.10.1 | 1 | - | - |
| 04.11 | 4 | - | - |
| 04.12 | 4 | - | - |
| 04.13 | 2 | - | - |
| 06.3 | 1 | - | - |
| 06.5 | 1 | - | - |
| 07.2 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 02-product-fixes P02 | 15 | 2 tasks | 2 files |
| Phase 02-product-fixes P01 | 15 | 2 tasks | 6 files |
| Phase 02-product-fixes P03 | 6 | 2 tasks | 0 files |
| Phase 02-product-fixes P04 | 18 | 2 tasks | 9 files |
| Phase 02-product-fixes P06 | 18 | 2 tasks | 3 files |
| Phase 02-product-fixes P05 | 12 | 2 tasks | 7 files |
| Phase 03 P02 | 3 | 2 tasks | 3 files |
| Phase 03-infrastructure-deployment P01 | 2 | 3 tasks | 5 files |
| Phase 03.1 P01 | 251 | 2 tasks | 2 files |
| Phase 03.1-frontend-redesign P02 | 12 | 1 tasks | 1 files |
| Phase 03.1 P03 | 12 | 1 tasks | 1 files |
| Phase 03.2-uat-bug-fixes P01 | 25 | 1 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P02 | 20 | 2 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P03 | 8 | 1 tasks | 2 files |
| Phase 03.2-uat-bug-fixes P05 | 15 | 2 tasks | 6 files |
| Phase 03.2-uat-bug-fixes P04 | 2 | 2 tasks | 6 files |
| Phase 03.2-uat-bug-fixes P06 | 3min | 2 tasks | 3 files |
| Phase 03.2-uat-bug-fixes P07 | 25min | 2 tasks | 4 files |
| Phase 04-payments-legal P01 | 10 | 2 tasks | 6 files |
| Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia P01 | 2 | 2 tasks | 2 files |
| Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia P02 | 5 | 2 tasks | 2 files |
| Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia P03 | 5 | 1 tasks | 2 files |
| Phase 04.2-cold-call-und-meeting-modi P01 | 10min | 2 tasks | 4 files |
| Phase 04.2-cold-call-und-meeting-modi P02 | 15min | 2 tasks | 2 files |
| Phase 04.2-cold-call-und-meeting-modi P03 | 1min | 1 tasks | 1 files |
| Phase 04.2-cold-call-und-meeting-modi P04 | 5min | 2 tasks | 2 files |
| Phase 04.2.1 P01 | 10 | 3 tasks | 2 files |
| Phase 04.2.1 P03 | 15 | 3 tasks | 2 files |
| Phase 04.2.1 P02 | 15 | 2 tasks | 2 files |
| Phase 04.2.1 P04 | 8 | 5 tasks | 2 files |
| Phase 04.2.1 P05 | 12 | 3 tasks | 5 files |
| Phase 04.3-design-unification P01 | 5 | 1 tasks | 1 files |
| Phase 04.3-design-unification P02 | 15 | 2 tasks | 3 files |
| Phase 04.3-design-unification P03 | 3 | 2 tasks | 2 files |
| Phase 04.3-design-unification P04 | 3min | 2 tasks | 3 files |
| Phase 04.3-design-unification P05 | 5 | 2 tasks | 2 files |
| Phase 04.3-design-unification P06 | 5min | 2 tasks | 4 files |
| Phase 04.6-sales-performance-calculator P01 | 10 | 2 tasks | 3 files |
| Phase 04.6-sales-performance-calculator P02 | 3 | 2 tasks | 1 files |
| Phase 04.6-sales-performance-calculator P03 | 8 | 2 tasks | 2 files |
| Phase 04.7 P03 | 10 | 2 tasks | 3 files |
| Phase 04.7 P06 | 10 | 2 tasks | 3 files |
| Phase 04.7 P04 | 20 | 2 tasks | 7 files |
| Phase 04.7 P05 | 25 | 2 tasks | 10 files |
| Phase 04.8.1 P01 | 3min | 2 tasks | 7 files |
| Phase 04.8.1 P02 | 2min | 2 tasks | 3 files |
| Phase 04.8.1 P03 | 2 | 2 tasks | 3 files |
| Phase 04.8.1 P04 | 3min | 2 tasks | 4 files |
| Phase 04.8.1 P05 | 3min | 2 tasks | 5 files |
| Phase 04.9-training-modul-upgrade-inserted P01 | 3min | 2 tasks | 3 files |
| Phase 04.9-training-modul-upgrade-inserted P02 | 1min | 2 tasks | 1 files |
| Phase 04.9-training-modul-upgrade-inserted P03 | 3min | 2 tasks | 1 files |
| Phase 04.9-training-modul-upgrade-inserted P04 | 5min | 2 tasks | 1 files |
| Phase 04.9-training-modul-upgrade-inserted P05 | 5min | 2 tasks | 3 files |
| Phase 04.10 P01 | 3min | 2 tasks | 2 files |
| Phase 04.10 P02 | 3min | 2 tasks | 15 files |
| Phase 04.10 P03 | 4min | 2 tasks | 1 files |
| Phase 04.10.1 P01 | 3min | 2 tasks | 3 files |
| Phase 04.11 P01 | 3min | 3 tasks | 5 files |
| Phase 04.11 P02 | 5min | 2 tasks | 3 files |
| Phase 04.11 P03 | 2min | 2 tasks | 3 files |
| Phase 04.11 P04 | 3min | 2 tasks | 3 files |
| Phase 04.12 P01 | 4min | 2 tasks | 3 files |
| Phase 04.12 P02 | 4min | 2 tasks | 3 files |
| Phase 04.12 P03 | 3min | 2 tasks | 2 files |
| Phase 04.12 P04 | 4min | 2 tasks | 5 files |
| Phase 04.13 P01 | 2 | 2 tasks | 4 files |
| Phase 04.13 P02 | 3 | 3 tasks | 3 files |
| Phase 04.14-crm-customer-success-inserted P01 | 80 | 2 tasks | 2 files |
| Phase 04.14 P02 | 5 | 2 tasks | 3 files |
| Phase 04.17-pip-launcher-inserted P01 | 18 | 2 tasks | 3 files |
| Phase 04.17-pip-launcher-inserted P02 | 12 | 2 tasks | 1 files |
| Phase 06-pip-komplett-rebuild-neues-layout-claude-streaming-skript-te P01 | 10 | 2 tasks | 7 files |
| Phase 06 P02 | 5 | 1 tasks | 1 files |
| Phase 06 P03 | 20 | 3 tasks | 3 files |
| Phase 06 P02 | 8 | 2 tasks | 1 files |
| Phase 06 P03 | 13 | 1 tasks | 1 files |
| Phase 06.1 P01 | 15 | 3 tasks | 2 files |
| Phase 06.1 P02 | 10 | 2 tasks | 2 files |
| Phase 06.1 P03 | 12 | 2 tasks | 2 files |
| Phase 06.1 P04 | 8 | 2 tasks | 2 files |
| Phase 06.2 P01 | 183 | 3 tasks | 2 files |
| Phase 06.2 P02 | 139 | 5 tasks | 3 files |
| Phase 06.2 P03 | 240 | 4 tasks | 1 files |
| Phase 06.3-analyse-loop-entkoppeln-von-live-slots P01 | 8 | 2 tasks | 2 files |
| Phase 06.4 P01 | 2min | 2 tasks | 3 files |
| Phase 06.5 P01 | 5min | 4 tasks | 2 files |
| Phase 07.2 P01 | 3 | 2 tasks | 2 files |
| Phase 07.2 P02 | 4min | 2 tasks | 2 files |
| Phase 07.2 P03 | 20min | 2 tasks | 3 files |
| Phase 07.2 P04 | 60min | 5 tasks | 5 files |
| Phase 08.5 P01 | 2 | 2 tasks | 5 files |
| Phase 08.5 P02 | 4 | 2 tasks | 3 files |
| Phase 08.5 P03 | 15 | 2 tasks | 8 files |
| Phase 08.5 P04 | 5 | 2 tasks | 2 files |
| Phase 08.5 P05 | 4 | 2 tasks | 1 files |
| Phase 08.5 P06 | 3 | 2 tasks | 3 files |
| Phase 08.8 P01 | 264 | 3 tasks | 2 files |
| Phase 08.8 P02 | 115 | 2 tasks | 3 files |
| Phase 08.8 P05 | 15 | 3 tasks | 7 files |
| Phase 08.9 P01 | 4 | 3 tasks | 3 files |
| Phase 08.9 P02 | 3 | 1 tasks | 1 files |
| Phase 08.9 P03 | 4 | 2 tasks | 2 files |
| Phase 08.9 P04 | 5 | 1 tasks | 1 files |
| Phase 08.11 P01 | 15 | 3 tasks | 2 files |
| Phase 08.11 P02 | 6 | 3 tasks | 6 files |
| Phase 08.13 P01 | 25 | 3 tasks | 6 files |
| Phase 08.13 P02 | 20 | 2 tasks | 5 files |
| Phase 08.13 P04 | 4min | 2 tasks | 2 files |
| Phase 08.13 P05 | 15min | 2 tasks | 2 files |
| Phase 08.19.2 P01 | 8min | 2 tasks | 1 files |
| Phase 08.19.2 P02 | 35 | 4 tasks | 5 files |
| Phase 08.19.2 P03 | 20min | 2 tasks | 1 files |
| Phase 08.19.2 P04 | 15min | 1 tasks | 1 files |
| Phase 08.19.3 P01 | 12min | 2 tasks | 2 files |
| Phase 08.19.3 P02 | 2min | 2 tasks | 2 files |
| Phase 08.19.3 P03 | 5min | 1 tasks | 1 files |
| Phase 08.19.3 P04 | 5min | 2 tasks | 2 files |
| Phase 08.20.2 P01 | 3min | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 08.19-01]: UnternehmensgroesseEnum Literal-Werte kanonisch in services/profile_schema.py: '<10', '10-50', '50-250', '250-1000', '1000+' — Plan 04 HTML-Chips muessen exakt matchen (Reviews v2 Enum-Sync-Pflicht)
- [Phase 08.19-01]: zielgruppe.vorwissen + zielgruppe.entscheidungsverhalten bleiben in zielgruppe.* (claude_service._build_coaching_prompt liest explizit pdata.get('zielgruppe', {}))
- [Phase 08.19-01]: ProfileSchema Dual-Schema-Pattern: Write extra='forbid' (ValidationError bei unbekannten Feldern), Read extra='ignore' (Drift-Felder ignoriert)
- [Phase 08.19-02]: _migrate_profile_json() Aufruf NACH _seed_demo_profiles() — Profile-First-Reihenfolge (Profile muessen existieren bevor migriert werden kann)
- [Phase 08.20.2-01]: PRECALL_FIELDS_SYSTEM_PROMPT ersetzt PRECALL_SYSTEM_PROMPT — strukturierter JSON-Output mit per-Feld confidence + source_url (high/medium/not_found)
- [Phase 08.20.2-01]: Cache-Key erweitert auf firmenname_lower + '_' + str(profile_id) (D-06) — Schicht-3-Empfehlungen refreshen bei Profil-Aenderung
- [Phase 08.20.2-01]: _generiere_empfehlungen() muss NACH set_briefing_for_sid() aufgerufen werden — build_profile_context() braucht Section 8 fuer Schicht-3-Kontext
- [Phase 08.20.2-01]: set_briefing_for_sid() bekommt schicht1_summary + newline + newline + text (NICHT empfehlungen)
- [Phase 08.19-03]: wizard_create() macht KEINEN ProfileOpener-INSERT — Wizard hat kein opener/pitch Eingabefeld (Code-Check-Befund, by design); neue Profile starten ohne Opener-Eintrag
- [Phase 08.19-03]: bearbeiten() POST: _migrate_profile_data() VOR ProfileSchema.model_validate() (Finding 2) — Altlasten-Stripping verhindert false-positive 400 durch extra='forbid'
- [Phase 08.19-03]: ValidationError -> flash + db.rollback() + redirect HTTP 400 (Finding 3) — kein 500, Blueprint-Name 'profiles', Parameter 'pid'
- [Phase 08.19-03]: consent_text dual-write NULL -> '' in daten.meta (Finding 4) — DB-Column-Drop in spaeterer Phase nach Stabilitaets-Verifikation
- [Phase 08.19.1-02]: einwaende + phasen als List[dict] top-level in ProfileSchema (D-01 Kalibrierung); BasisSchema Dead Fields entfernt; _BasisReadSchema behaelt einwaende/phasen fuer Lese-Kompatibilitaet alter Profile
- [Phase 08.19.1-02]: produkt: Any = None in ProfileSchema + ProfileReadSchema (2/6 Production-Profile — Entscheidungsregel >= 2 getroffen per KEY-FINDINGS.md)
- [Phase 08.19.1-02]: 1/6-Profil-Keys als Noise (beschreibung, emotionale_trigger, no_go etc.) — kein Schema-Eintrag; Plan-03 pop()-Schritt bereinigt sie in v2->v3 Migration
- [Phase 08.19.3-04]: faq-mode-toggle visual state driven via JS (modeTrack.style.background, modeThumb.style.transform) — no CSS :checked pseudo-selector; avoids CSS specificity conflicts
- [Phase 08.19.3-04]: prevChecked = !modeChk.checked captured BEFORE _setModeVisual() — change event already has new value, inverse is the pre-change state
- [Phase 08.19.3-04]: Ghost-toggle reads data-faq-id at change-event time via row.getAttribute() (not closure faqId) — allows toggle to fire after POST-success sets the ID
- [Phase 08.19.3-04]: No showToast in profile_editor.js — alert() fallback is correct per plan spec
- [Phase 08.19.3-03]: mode Whitelist ('literal', 'ki_generated') in GET/POST/PUT identisch — SQL-Injection-Mitigation per ORM-Zuweisung (T-08.19.3-09/10/13)
- [Phase 08.19.3-03]: POST mode default 'ki_generated' via (data.get('mode') or 'ki_generated').strip() — verhindert NOT NULL Constraint-Edge-Cases
- [Phase 08.19.3-03]: Partial-PUT Pattern: if 'field' in data → validate → assign; mode folgt gleichem Muster wie kategorie
- [Phase 08.19.3-02]: _qa_pipeline_dispatch() filtert _faqs_all auf literal-only vor match_faq() — ki_generated FAQs aus Embedding-Match ausgeschlossen (D-06/D-07/D-08)
- [Phase 08.19.3-02]: build_profile_context() liest active_profile_id via ls.state['active_profile_id'] (state_lock) — ls.get_active_profile()[0] gibt name zurueck, nicht id (Deviation fix)
- [Phase 08.19.3-02]: FAQ Q+A-Block in build_profile_context() gecapped auf 20 rows (order_by used_count DESC) — LLM-degradation + Token-Budget-Schutz (D-10)
- [Phase 08.19.3-01]: Block A+B (ALTER TABLE + Backfill) in single try/except — Backfill runs only on first start when ALTER TABLE succeeds (D-16 Toggle-Persistenz-Schutz)
- [Phase 08.19.3-01]: Advisory-lock id 81930 fuer _migrate_fragen_to_faqs() — keine Kollision mit 819 aus _migrate_profile_json()
- [Phase 08.19.3-01]: _migrate_fragen_to_faqs() als Top-Level-Funktion vor _migrate()-Aufruf definiert — engine/app.logger zugreifbar ohne circular import
- [Phase 08.19-04]: Wizard unternehmensgroesse Chip-Select onclick-Werte exakt gleich UnternehmensgroesseEnum Literals — HTML-Entity &lt; nur im sichtbaren Text-Content, NICHT im onclick-String (Reviews v2 Enum-Sync)
- [Phase 08.19-04]: initGroesseChip() direkt nach Funktionsdefinition aufgerufen (kein DOMContentLoaded-Wrapper noetig da Script am Body-Ende steht)
- [Phase 08.19-04]: selectGroesse() loescht boxShadow-Highlight bei Auswahl (Deviation Rule 2 — UX-Korrektur)
- [Phase 08.19-03]: precall_service profile_id=None -> leerer Opener-Block (graceful degradation) — backward-compatible, kein Crash
- [Phase 08.19-02]: ProfileReadSchema verwendet eigenstaendige Read-Sub-Schemas mit extra=ignore + Any-Typen — echte Produktionsdaten haben Typ-Drift (nogos: List[dict], ki.antwortlaenge, beruflicher_hintergrund: List)
- [Phase 08.19-02]: schema_version None-safe Guard: (daten.get('schema_version') or 1) >= 2 — get() mit Default ignoriert None-Werte (Key=None), 'or 1' wandelt None in 1 um
- [Phase 08.19-02]: BEGIN EXCLUSIVE via conn.execute(text(...)) statt execution_options(isolation_level='EXCLUSIVE') — SQLAlchemy 2.x unterstuetzt EXCLUSIVE nicht als gueltigen Isolation-Level fuer SQLite
- [Phase 08.18-03]: precall_service.recherche_firma() benoetigt branche als Pflicht-Parameter — 3-Tier-Routing: Premium (5 Dim.) / Mittel-Tiefe (3 Dim.) / Generisch (Standard)
- [Phase 08.18-03]: 3 neue Profil-Felder empfohlen fuer 08.19: profil.branche (Pflicht), profil.zielkunden_branche (optional), profil.branchen_fachbegriffe (List[str], optional)
- [Phase 08.18-03]: Datenquellen-Routing je Branche: Maschinenbau → Northdata/VDMA, IT/SaaS → Crunchbase/LinkedIn/Builtwith, Versicherung → GDV/Northdata/Asscompact
- [Phase 08.18-02]: Premium-Cluster DACH (fuer Plan 03 Tiefen-Recherche): Maschinenbau (~16-18%), IT/SaaS (~12-14%), Versicherung/Finanz (~11-13%) — auf Basis BA KldB 2010 + VDMA/GDV/bitkom
- [Phase 08.18-02]: Premium-Cluster USA: Technology/SaaS (~15-18%), Financial Services (~12-15%), Healthcare/Pharma (~10-12%) — auf Basis BLS OES May 2023 SOC 41-XXXX
- [Phase 08.18-02]: USA gleichberechtigt zu DACH in Research (André-Entscheidung) — USA ist echtes Hauptgeschaeft, DACH ist Soft-Launch/Test-Sandbox
- [Phase 08.18-01]: Reihenfolge build_profile_context: Block 1 Kern (Cache-Anchor), Block 2 Einwand-Repertoire, Block 3 No-Gos, Block 4 Kommunikation — per Anthropic Lost-in-Middle + Sales-Trainer-Konsens
- [Phase 08.18-01]: EWB-Integration-Ziel nach 08.19/08.20: 21% (10/48) → 62% (30/48) — Literatur-Konsens erfordert einwaende[] + wettbewerber[] + nogos[] + ki.zusatz + statusquo im EWB-Prompt
- [Phase 08.18-01]: 6 neue Schema-Felder empfohlen: zielkunde.unternehmensgroesse, zielkunde.buying_committee, zielkunde.statusquo, zielkunde.zeithorizont, value.roi_argumente, einwaende[].einwand_typ
- [Phase 08.18-01]: 7 Felder fuer Elimination: alter/einkommensniveau/lebenssituation (B2C), schmerzen.trigger (Slider ohne Wirkung), ki.stil (Duplikat), erlaubnis (tot), consent_text (UI-only)
- [Phase 08.17-01]: LB-3 Fix (08.9): technische Parameteruebergabe profile_data korrekt, aber _SYSTEM_PROMPT_QA hat kein {profile_context} Placeholder — Pfad 4 bleibt generisch, Kandidat fuer Phase 08.19
- [Phase 08.17-01]: 08.13 Block E claude_client-Konsolidierung: system= Kwarg einheitlich in allen API-Calls, Prompt-Assembly-Struktur unveraendert — kein Matrix-Impact
- [Phase 08.17-01]: Alle 🧟 Zombie-Code-Eintraege → ❌ (sauber): _build_system_prompt seit 08.8 tatsaechlich geloescht (nicht mehr nur unreachable)
- [Phase 08.17-01]: EWB-Integration-Quote: 10/48 = 21% — unveraendert nach Phasen 08.8-08.14, kein neuer EWB-Profil-Kontext eingefuehrt
- [Phase 08.17-01]: Andrés Verdacht-Liste: kaufsignale/wettbewerber/uebergaenge/vorwissen/entscheidungsverhalten leben im Coach-Pfad (nicht in EWB) — waren nicht "tot" sondern "EWB-tot"
- [Phase 08.14-02]: ApiRate-Seed in _migrate() — 8 Rows sonnet-4-5-20251022 + haiku-4-5-20251001 (input/output/cache_read/cache_write), idempotent per SELECT-vor-INSERT
- [Phase 08.14-02]: Alle 9 Sonnet-MODEL_*-Konstanten auf claude-sonnet-4-5-20251022 — Date-Suffix verhindert Anthropic-Alias-Drift auf aeltere Modelle; konsistent mit Haiku-Pattern
- [Phase 08.14-01]: ruff-Hook in settings.local.json (projektlokal) — Hook soll nur fuer salesnerve gelten, nicht global
- [Phase 08.14-01]: Context7-MCP via claude mcp add statt settings.json — mcpServers ist kein gueltiges settings.json-Schema-Feld; registriert in ~/.claude.json
- [Phase 08.14-01]: Regel 13: Hook fuer deterministische Aktionen (ruff format), CLAUDE.md-Regel fuer Urteilsvermoegen-Anforderungen
- [Phase 08.14-01]: Blueprint-Tabelle in routes/CLAUDE.md verifiziert — organisations.py nutzt orgs_bp='orgs' (nicht 'organisations'); Fehler-Quelle dokumentiert
- [Phase 08.13-05]: H-9 Fix: _stt_seconds_accumulated akkumuliert result.metadata.duration per is_final=True — Cost-Hook nutzt echte Audio-Dauer statt Socket-Lifetime (Overcharge-Illusion behoben)
- [Phase 08.13-05]: T-08.13-11 accept: Race-Condition _stt_seconds_accumulated Deepgram-Thread vs. close-Thread — Worst-Case < 1 Chunk verloren, Billing-Fehler minimal, Lock fuer spaeter
- [Phase 08.13-05]: routes/training.py Kundentyp-Generator auf config.MODEL_TRAINING_PREVIEW (Haiku) migriert — Smoke-Check-Fund, semantisch korrekt
- [Phase 08.13-04]: EWB-System-Prompts kuerzer als 16000 Zeichen — Cache bleibt 'off' bis Prompts wachsen; Threshold-Guard korrekt (verhindert sinnlose Cache-Write-Kosten)
- [Phase 08.13-04]: Cache-Token-Logging EWB model='sonnet-4-5' per Plan-Spec — tatsaechlicher Call nutzt Haiku; Log-String stimmt wenn EWB auf Sonnet umgestellt wird
- [Phase 08.13-03]: generate_response/generate_response_with_mood KEIN user_id-Parameter (BG-Thread) — Cost-Hook user_id=None akzeptiert
- [Phase 08.13-03]: GRUPPE A (generate_help_suggestion/generate_scoring/_generate_live_preview) user_id=None Parameter — routes/training.py uebergibt g.user.id
- [Phase 08.13-03]: H-22 T-08.13-06 mitigiert — api_postcall_analysis except gibt {'ok': False, 'error': 'internal error'} ohne str(e)
- [Phase 08.13-02]: H-12 Block E abgeschlossen — 5 inline anthropic.Anthropic()-Clients eliminiert, alle Modules nutzen shared claude_client aus claude_service (Connection-Pooling)
- [Phase 08.13-02]: H-29 Cost-Hook in dashboard._generate_weekly_summary — context_tag=weekly_dashboard, call_site=weekly, getattr(user, 'id', None) fuer sichere user_id-Extraktion
- [Phase 08.13-02]: training_service.generate_help_suggestion Haiku -> config.MODEL_TRAINING_HELP (Sonnet) per CONTEXT.md
- [Phase 08.13-01]: MODEL_POSTCALL_INSIGHTS ENV-Key korrigiert (POSTCALL nicht POSTCOLL — Plan-Tippfehler behoben)
- [Phase 08.13-01]: ApiRate-Seeding idempotent — 6 neue Rows (sonnet-4-5 input/output/cache_read/cache_write, haiku-4-5 cache_read/cache_write); haiku-4-5 input/output waren bereits vorhanden
- [Phase 08.13-01]: 21 MODEL_*-Konstanten + 3 CACHE_*-Booleans in config.py als os.getenv() mit ENV-Defaults — alle Waves koennen config.MODEL_XYZ nutzen
- [Phase 08.13-01]: ApiCostLog.latency_ms (Integer nullable) + ApiCostLog.call_site (String(50) nullable) — idempotente ALTER TABLE Migration in app.py _migrate()
- [Phase 08.10-06]: email_confirmed=False VOR Email-Send committed — ECHTER BLOCK bleibt sauber; Resend-Endpoint /auth/resend-confirm (VARIANTE B) schliesst Lockout-Luecke bei Email-Send-Failure
- [Phase 08.10-06]: except SystemExit: raise in Migration-Try-Block — sys.exit(1) STOPS-Behavior wird nicht von except Exception abgefangen
- [Phase 08.10-06]: confirm_email_pending + confirm_email + resend_confirm BEWUSST ohne @login_required — verhindert Redirect-Loop
- [Phase 08.10-06]: Partial UNIQUE INDEX WHERE oauth_id IS NOT NULL — NULL-Werte erzeugen keine Constraint-Verletzung
- [Phase 08.10-05]: In-Memory-Storage fuer flask-limiter Single-Worker (Gunicorn gthread 1+4) — Counter-Reset bei App-Restart akzeptiert; Redis-Hinweis fuer Block-M-Skalierung in services/rate_limiter.py dokumentiert
- [Phase 08.10-05]: init_limiter(app) nach CSRFProtect — Reihenfolge ProxyFix→CSRFProtect→init_limiter kritisch fuer korrektes per-IP-Bucketing hinter Nginx
- [Phase 08.10-05]: Kein globales Limit (default_limits=[]) — nur spezifische Decorators auf Login/Register, keine Kollateral-Limits auf anderen Routen
- [Phase 08.10-04]: session.clear() in _login_user() VOR session.permanent=True — neue Session-ID bei jedem Login (H-17 Session-Fixation-Praevention)
- [Phase 08.10-04]: current_app.logger.warning() statt from app import app — circular import guard (routes/auth.py importiert von app.py)
- [Phase 08.10-04]: if-Variante fuer Org-Mismatch statt assert — sauberer Redirect ohne 500er Stack-Trace; logger.warning() VOR session.clear() fuer Incident-Response
- [Phase 08.10-03]: csrf = CSRFProtect(app) NACH socketio = SocketIO(app, ...) — WSGI-Level-Interception garantiert SocketIO-Exemption automatisch (VARIANTE B, kein expliziter /socket.io-Workaround noetig)
- [Phase 08.10-03]: 3 csrf.exempt(): stripe_webhook (HMAC-Auth via STRIPE_WEBHOOK_SECRET), google_callback + microsoft_callback (OAuth GET-Callbacks, kein Browser-POST)
- [Phase 08.10-03]: getCsrfToken() in jedem JS-File separat definiert — Self-contained IIFE-Pattern bleibt erhalten, kein shared module
- [Phase 08.10-02]: x_host=1 aus ProxyFix entfernt — Host-Header-Injection-Vektor bei Fixed-Domain getnerve.app unnoetig und riskant; nur x_for+x_proto
- [Phase 08.10-02]: _debug via os.environ.get('FLASK_DEBUG') — app.debug ist unter gunicorn immer False (established pattern Phase 03)
- [Phase 08.10-02]: SESSION_COOKIE_SECURE=not _debug — False lokal (kein HTTPS), True Prod; HTTPONLY=True, SAMESITE=Lax, LIFETIME=14 Tage (LB-10)
- [Phase 08.11-04]: SMOKE-TESTS.md mit 5 EA-Flow-Checkboxen erstellt — sequenzielle Verifikation nach Block-F-Deletion; git push origin main abgeschlossen
- [Phase 08.11-03]: legacyOpener / profileDaten.opener vollstaendig entfernt — alle EA-Profile nutzen openerItems direkt seit Phase 04.17. Kein Fallback mehr noetig.
- [Phase 08.11-03]: test_ft_seed.py auf 4 Module reduziert — api_frage Route in Wave 1 geloescht, Seed-Funktion entfernt
- [Phase 08.11-02]: onboarding.html finish('live') — NerveLauncher ? open() : /dashboard Fallback (Cross-AI Review Override; pip-launcher.js koennte beim Onboarding-Click noch nicht geladen sein)
- [Phase 08.11-02]: logs_page.html <a>-Tag href=/live — beide Attribute href=javascript:void(0) + onclick=NerveLauncher zusammen gesetzt (Cross-AI Review Override)
- [Phase 08.11-01]: OBJECTION_TRIGGER_PROMPT_BASE bleibt in app_routes.py — Konstante wird noch fuer objection_trigger Seed-Eintrag in _seed_prompt_versions() benoetigt; HTTP-Route api_ewb_trigger() geloescht, Konstante bleibt
- [Phase 08.11-01]: /live gibt 302 redirect auf dashboard_bp.dashboard — kein Setup-Code mehr (fair-use, profile load), alles laeuft ueber /api/launcher/init beim PiP-Start
- [Phase 08.11-01]: _SuppressPolling vollstaendig entfernt — /api/ergebnis (dieser Plan) und /api/status (Block I) beide weg, Filter-Klasse war toter Code
- [Phase 08.9-04]: H-25 _rolle()-Checks eingebaut — wizard_create (flash+redirect), aktivieren/api_faqs_create/api_tabu_update (jsonify 403). api_faqs_update/delete unveraendert (Org-Isolation genuegt auf FAQ-Ebene)
- [Phase 08.9-03]: LB-3 _qa_pipeline_dispatch beide generate_qa_response-Aufrufe korrigiert — profile_data={} → _profile_daten, confidence='' → confidence=float(_conf), positional user_id → user_id=_user_id keyword
- [Phase 08.9-02]: HSR-2 wizard_create() auf basis.*-Schema umgestellt — Flat-Keys firma/produkt/zielkunden/rolle/einwaende ersetzt durch basis.produktbeschreibung/zielkunden/einwaende/phasen + ki.anrede + meta.firma/rolle
- [Phase 08.9-01]: LB-11 Onboarding-Redirect in login_required reaktiviert — deaktiviert in 6b57a77 als deploy hardening, kein Safety-Concern, onboarding_done default=True schuetzt bestehende User
- [Phase 08.9-01]: H-31/HSR-2 BRANCHE_TEMPLATES auf basis.*-Schema (produktbeschreibung/einwaende/phasen unter 'basis'-Key) — konsistent mit qa_pipeline.py basis-Read-Pattern Zeile 374
- [Phase 08.9-01]: Demo-Profile-Migration idempotent per 'basis' in _daten Check — nur Profile IDs 2/3/4, nur Flat-Schema-Profile werden migriert
- [Phase 08.8-05]: H-1 log_pipeline_event war dauerhafter No-Op (finetune_logging.py nie erstellt) — gesamter Wrapper + 5 try/except Bloecke + 6 Tests entfernt; FtPipelineEvent-Tabelle existiert nicht, keine DB-Migration noetig
- [Phase 08.8-05]: Phase 08.8 Block I vollstaendig — ~581 Zeilen Dead-Code entfernt (H-1/H-3/H-4/H-11/H-27/H-28/Orphan-Routes/Orphan-Templates/ewb_top2)
- [Phase 08.8-04]: ewb_top2 Option A — sofort entfernt aus app.js + app_routes.py + live_session.py; Writer seit Phase 04.8 D-08 entfernt, Wert war immer None
- [Phase 08.8-04]: classic-opener-block-f — Classic-opener-Branch in app.js nicht angefast, verschoben auf Block F (Classic-Deprecation)
- [Phase 08.8-03]: swap_roles + api_status + api_skripte aus app_routes.py geloescht — 0 Frontend-Caller verifiziert; api_skripte war Duplikat zu /api/launcher/*
- [Phase 08.8-03]: api_feedback_quick + training_ping + api_training_postcall_analysis geloescht — 0 Frontend-Caller; /api/postcall_analysis (live) bleibt erhalten
- [Phase 08.8-02]: H-27 live_tipp + api_tipps geloescht nach 0-Frontend-Caller-Verifikation — datetime-Import mitentfernt
- [Phase 08.8-02]: H-27 coach_tipps unbounded List (Memory-Leak) aus live_session.py entfernt — kein Reset noetig da keine anderen Caller
- [Phase 08.8-02]: H-28 api_training_personality_save geloescht — Frontend-Caller saveGeneratedPersonality() in 07.2 Wave 3 bereits entfernt
- [Phase 08.6-01]: settings_theme silent coercion replaced with HTTP 400 — invalid enum values rejected, not coerced
- [Phase 08.6-01]: settings_language allowed list shrunk to ['de', 'en'] — fr/es/it/pt/nl/pl/cs/tr have no app content
- [Phase 08.6-01]: ROI KPI card hidden via inline style (not deleted) — preserves JS reference to id=perf-roi for future implementation
- [Phase 08.6-01]: LB-12 column names fixed without DB migration — real columns were always einwaende_gesamt/einwaende_behandelt, only the admin view references were wrong
- Roadmap: LEGAL-04 placed in Phase 3 (infrastructure config, not legal document)
- Roadmap: Phase 1 (BIZ) and Phase 2 (PROD) run in parallel — both are independent tracks
- Roadmap: LEGAL-01 through LEGAL-03 grouped with PAY in Phase 4 (both are hard launch blockers, activated together)
- [Phase 02-product-fixes]: DSGVO banner triggered on socket connect event (not transcript) — earliest JS hook before server-side PyAudio capture
- [Phase 02-product-fixes]: SalesNerve Alpha retained in migration SQL WHERE clause — it is the search predicate for legacy record rename, not a branding artifact
- [Phase 02-product-fixes]: database/db.py had its own hardcoded salesnerve.db default — fixed alongside config.py as Rule 1 bug (inconsistent defaults)
- [Phase 02-product-fixes]: No code changes needed — training modes, scoring, preview, and scenario selector verified correct as-is (PROD-03 through PROD-06)
- [Phase 02-product-fixes]: PLANS dict has exactly 3 flat-rate plans: starter/pro/business at 49/59/69 EUR — all legacy keys removed
- [Phase 02-product-fixes]: Org-level fair-use counters (live_minutes_used, training_sessions_used) added alongside user-level counters; soft-warn at 80%, never hard-block
- [Phase 02-product-fixes]: POST wizard_create replaced JSON-API handler with form-data handler — matches HTML form submission pattern in rest of codebase
- [Phase 02-product-fixes]: Wizard redirect placed before expensive stats queries in dashboard route to minimize overhead for new users
- [Phase 03]: gthread 1+4 worker config: matches D-03 for CX22 with Flask-SocketIO threading mode
- [Phase 03]: WebSocket proxy timeouts set to 3600s in nginx — Socket.IO connections are long-lived during full sales calls
- [Phase 03-infrastructure-deployment]: SECRET_KEY check uses os.environ.get('FLASK_DEBUG') not app.debug — app.debug is always False at module-load under gunicorn
- [Phase 03-infrastructure-deployment]: WAL mode listener guarded by sqlite detection — safe for future PostgreSQL upgrade path
- [Phase 03-infrastructure-deployment]: CORS_ORIGIN defaults to nerve.app in production, wildcard only when FLASK_DEBUG env var is set
- [Phase 03.1]: Nav logo updated to NERVE teal (#2dd4a8) — aligns with new design system primary color, replacing old gold #E8B040
- [Phase 03.1]: Legacy CSS classes preserved in nerve.css alongside new .n-* classes — prevents visual regression on unmigrated child pages during phased rollout
- [Phase 03.1-frontend-redesign]: Gold #E8B040 fully replaced by teal #2dd4a8 in dashboard — no KI/AI-specific gold elements present in this page
- [Phase 03.1-frontend-redesign]: Quick action buttons use n-btn-ghost with border-radius:8px inline override — preserves rectangular list appearance while using NERVE component
- [Phase 03.1]: app.html kept as standalone page (not extending base.html) — live-session fullscreen UX requires own document structure
- [Phase 03.1]: n-ai-panel added to scroll#ai scroll container with border overrides — preserves JS scroll behavior while applying gold AI panel styling
- [Phase 03.2-uat-bug-fixes]: startFreizeichen made async to allow await freizCtx.resume() — browser autoplay policy requires explicit resume after AudioContext creation
- [Phase 03.2-uat-bug-fixes]: TTS autoplay errors surfaced to console.warn (not silenced) — silent catch hid critical failure mode in training TTS playback
- [Phase 03.2-uat-bug-fixes]: t-endBtn id added to Beenden button — explicit id more reliable than class-based querySelector
- [Phase 03.2-uat-bug-fixes]: Timer starts on socket.on('connect'), not first transcript — transcript handler retains guarded fallback
- [Phase 03.2-uat-bug-fixes]: No-conversation guard checks trainingSecs<10||userMsgCount===0 for training, sessionSeconds<10||words<20 for live
- [Phase 03.2-uat-bug-fixes]: Standalone Einstellungen sidebar link removed — now lives exclusively in the sidebar user dropdown (ARCH-16)
- [Phase 03.2-uat-bug-fixes]: Sidebar user dropdown opens upward (bottom: calc(100% + 4px)) to avoid viewport clipping at sidebar bottom edge
- [Phase 03.2-uat-bug-fixes]: preferred_language column defaults to 'de' — backward-compatible, existing users automatically get German as preference
- [Phase 03.2-uat-bug-fixes]: DOMContentLoaded calls selectLanguage() for non-default saved language to sync tUI and button states in training.html
- [Phase 03.2-uat-bug-fixes]: profile_wizard.html already uses neutral placeholders — no personal names found, no changes required (UAT-10)
- [Phase 03.2-uat-bug-fixes]: No-FOUC script placed before CSS link — runs synchronously, prevents flash of wrong theme
- [Phase 03.2-uat-bug-fixes]: Server-hint via data-server-theme on <html> tag from g.user.preferred_theme — DB value takes precedence over localStorage on authenticated pages
- [Phase 03.2-uat-bug-fixes]: preferred_theme defaults to 'dark' — backward-compatible, existing users stay on dark theme
- [Phase 03.2-uat-bug-fixes]: Loading overlay uses display:flex for centering; pcLoading declared before try block for cleanup in catch
- [Phase 03.2-uat-bug-fixes]: Kompakt mode changed to floating overlay — all body.kompakt hide rules removed, panel floats at bottom:16px right:16px without hiding main content
- [Phase 03.2-uat-bug-fixes]: All #E8B040 (gold) replaced with #2dd4a8 (teal) in landing.html including rgba() values
- [Phase 03.2-uat-bug-fixes]: DSGVO banner overlap fix via JS paddingBottom on .panel-sprachanalyse — CSS sibling selectors cannot reach across the DOM tree
- [Phase 03.2-uat-bug-fixes]: Custom scenario dropdown uses hidden <input id='t-scenarioSelect'> — all existing callers reading .value continue working unchanged
- [Phase 03.2-uat-bug-fixes]: window._pendingDeleteId bridges deleteScenario() modal show and confirmDeleteScenario() async execution
- [Phase 04-payments-legal]: Kein Audio wird jemals gespeichert — ephemeral processing only (Kernargument für Datenschutzerklärung)
- [Phase 04-payments-legal]: Live-Assistent Cold-Call-Modus = nur Berater-Audio, kein Kundentranksript, berechtigtes Interesse Art. 6 lit. f
- [Phase 04-payments-legal]: Live-Assistent Meeting-Modus = Consent-Pop-up vor Call, Ablehnung → Auto-Wechsel in Cold-Call
- [Phase 04-payments-legal]: KI-Trainingsdaten-Checkbox muss ENTKOPPELT von Training-Nutzung sein (Art. 7 Abs. 4 DSGVO Koppelungsverbot)
- [Phase 04-payments-legal]: Alle Dienste EU-Server: Deepgram api.eu.deepgram.com, Claude Bedrock Frankfurt, ElevenLabs EU Residency, Stripe Frankfurt
- [Phase 04-payments-legal]: Webhook uses raw request.data for Stripe signature verification — idempotent by stripe_event_id UNIQUE index
- [Phase 04-payments-legal]: checkout_success only flashes and redirects — subscription activation handled exclusively in webhook (D-12)
- [Phase 04-payments-legal]: stripe_customer_id stored on Organisation at checkout for reuse on subsequent Checkout Sessions (D-06)
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: PyAudio removed — VPS has no audio hardware, browser streams audio via Socket.IO audio_chunk events
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: Per-sid _deepgram_sessions dict used for isolated Deepgram connections per browser session
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: register_audio_handlers(sio) replaces background thread — events are client-driven via start_live_session/stop_live_session/audio_chunk/disconnect
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: workletNode.connect(audioCtx.destination) required to prevent garbage collection of AudioWorklet node mid-session
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: stopMicStream() called before fetch('/api/beenden') — ensures stop_live_session emitted before server resets session state
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: audioCtx.resume() called conditionally (state==='suspended') in startMicStream() — bypasses Chrome autoplay suspension without errors on other browsers
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: window.location.pathname guard added to socket.on('connect') as defensive measure — app.js only loads on /live but guard prevents future regression
- [Phase 04.1-live-mikrofon-fix-pyaudio-browser-getusermedia]: _first_chunk_logged scoped as closure in register_audio_handlers() — first-chunk diagnostics without module-level global pollution
- [Phase 04.2-cold-call-und-meeting-modi]: session_mode defaults to 'meeting' for backward compatibility — existing frontend calls without the field treated as meeting mode
- [Phase 04.2-cold-call-und-meeting-modi]: EWB trigger endpoint mirrors api_frage pattern (same Haiku model, same logging) with objection-specific prompt ending in open question
- [Phase 04.2-cold-call-und-meeting-modi]: DSGVO banner deferred from socket.on('connect') to activateSession() — mode overlay must appear first, banner only relevant after session mode confirmed
- [Phase 04.2-cold-call-und-meeting-modi]: activateSession() centralizes all post-mode-selection setup: overlay hide, badge update, DSGVO banner, timer start, EWB render, mic start
- [Phase 04.2-cold-call-und-meeting-modi]: Socket connect handler guards mic auto-start behind sessionMode check — prevents mic start before mode overlay dismissed, handles reconnect correctly
- [Phase 04.2-cold-call-und-meeting-modi]: smart_format=False in meeting mode — smart_format strips word-level speaker attributes required for diarization; disabled to preserve raw word objects
- [Phase 04.2-cold-call-und-meeting-modi]: utterance_end_ms=1000 added for meeting mode via conditional dict — avoids passing None to SDK, improves speaker segmentation on single-channel audio
- [Phase 04.2-cold-call-und-meeting-modi]: renderEwbButtons uses shared html string assigned to both bar and kpBar — avoids duplication and keeps both bars in sync
- [Phase 04.2-cold-call-und-meeting-modi]: triggerEwb() left unchanged — queries .ewb-btn by text content which works for both full-mode and compact-mode bars
- [Phase 04.2.1]: g-content auto-expands on sidebar collapse via flexbox flex:1 — no margin-left CSS needed
- [Phase 04.2.1]: Legacy nav items (Team, Coach, Methodik, Changelog) kept in DOM in display:none wrapper per D-31
- [Phase 04.2.1]: sidebar-plan-badge uses existing --badge-primary-bg / --badge-primary-text tokens per D-03 (no new colors)
- [Phase 04.2.1]: Document PiP replaces kompakt-panel toggle — fallback overlay kept for non-Chrome browsers (display:none by default)
- [Phase 04.2.1]: window.sessionMode synced from activateSession() local var for PiP badge access across JS module boundary
- [Phase 04.2.1]: get_recent_calls_db replaces file-based log parsing for dashboard -- DB query gives session_mode and kb_end score unavailable from log files
- [Phase 04.2.1]: NBA card dismiss uses week-keyed localStorage (sn_nba_dismissed_YYYY-WNN) -- resets weekly without server state
- [Phase 04.2.1]: Old dashboard Python helpers kept (qotd, achievements, ROI, weekly_summary) -- only HTML rendering removed per D-26/D-27/D-28/D-29
- [Phase 04.2.1]: confirmBeenden() in plan HTML does not exist — used beenden() (existing function) for Beenden button in new single header
- [Phase 04.2.1]: id=st status text span kept display:none in header — app.js writes mic error text to it; removing would silence mic error feedback
- [Phase 04.2.1]: Profile-bar and phasen-bar hidden (display:none, not deleted) — ~72px vertical space reclaimed, 3-bar chrome reduced to single 52px header
- [Phase 04.2.1]: rank_ewb() uses Option B (separate Haiku call) to avoid modifying existing Einwand-detection prompt — validates returned EWB types against profile list
- [Phase 04.2.1]: EWB ranking throttled to every 3rd analyse_loop cycle — ewb_top2 stored in live_session.state and exposed via /api/ergebnis polling endpoint
- [Phase 04.3-design-unification]: back-link placed after .nav-mark inside the left header flex section — integrates naturally with existing header layout
- [Phase 04.3-design-unification]: href=C:/Program Files/Git/dashboard used (not history.back()) in app.html back-link — avoids Socket.IO/AudioContext state issues from browser history navigation
- [Phase 04.3-design-unification]: Light mode fully removed — theme hardcoded to dark in base.html, no toggle UI anywhere in app
- [Phase 04.3-design-unification]: Teal updated from #2dd4a8 to #00D4AA / #20b090 to #00B894 across all 30+ occurrences in nerve.css
- [Phase 04.3-design-unification]: Page bg updated from #06060a to #0D1117, sidebar from rgba(6,6,10,0.95) to #0A0E14 (solid)
- [Phase 04.3-design-unification]: Settings toggle knob uses #1C2333 when checked — matches card background for seamless look
- [Phase 04.3-design-unification]: Logs page dark alternating rows use #1C2333/#161B22, thead #0D1117 — consistent with page bg token hierarchy
- [Phase 04.3-design-unification]: profile_editor inputs use explicit #1C2333/#2D3748 hex over CSS vars — vars too dark to distinguish from page bg
- [Phase 04.3-design-unification]: All help.html #E8B040 orange replaced with #00D4AA teal — section headers, focus borders, hover states, contact link
- [Phase 04.3-design-unification]: app.html stats footer left intact - not a legal links footer; Rechtliches tab outside role-check for all-user visibility
- [Phase 04.3-design-unification]: Training language sourced from Jinja preferred_language const — TRAINING_LANGUAGES kept for ring tones, selectLanguage() removed, no client-side UI switching
- [Phase 04.3-design-unification]: Sidebar Settings pinned to bottom via flex:1 spacer div inside .g-sidebar-inner — preserves collapsed sidebar CSS, no position:fixed used
- [Phase 04.6-sales-performance-calculator]: performance.py as standalone blueprint (not appended to dashboard.py) — clean separation of concerns per blueprint pattern
- [Phase 04.6-sales-performance-calculator]: Forecast uses 5% monthly growth S-curve factor — marketing assumption, documented inline in code
- [Phase 04.6-sales-performance-calculator]: HTML entities used for special chars in dashboard.html (em dash, euro, emoji) — encoding safety, cosmetically identical
- [Phase 04.6-sales-performance-calculator]: Chart.js CDN added to dashboard.html directly — only needed on dashboard, avoids loading on all pages
- [Phase 04.6-sales-performance-calculator]: perfRenderReal auto-switches to sim mode when hat_daten=false — empty state UX per CONTEXT
- [Phase 04.7]: session_start + session_end beide in api_beenden — kein HTTP-Start-Endpoint, Socket.IO hat kein g.user
- [Phase 04.7]: Bootstrap4Theme() statt template_mode — flask-admin 2.x API
- [Phase 04.7]: ewb_clicks in state-Dict (nicht separates Modul-Global) — bleibt im bestehenden state_lock-Scope, kein neuer Lock noetig
- [Phase 04.7]: ObjectionEvent bulk-insert vor log_action(session_end) — Reihenfolge per Plan-Spec enforced
- [Phase 04.7]: analytics_page() statt analytics() als Funktionsname in dashboard.py — vermeidet Namenskollision mit bestehender /api/analytics JSON-Route
- [Phase 04.7]: Feedback-Tabelle getrennt von FeedbackEvent — FeedbackEvent bleibt Post-Session-Sterne, Feedback ist Ticket-System
- [Phase 04.7]: MAX_CONTENT_LENGTH=5MB global gesetzt fuer alle Uploads in der App
- [Phase 04.7]: FeedbackAdmin endpoint='feedback_admin' wegen Blueprint-Namenskonflikt mit feedback_bp aus Plan 04 (Rule 1 Auto-fix)
- [Phase 04.8.1]: os.environ.get + load_dotenv statt pydantic-settings -- konsistent mit Flask config.py Pattern
- [Phase 04.8.1]: Session tokens single-use (delete after read) -- Replay-Attack-Mitigation T-04.8.1-01
- [Phase 04.8.1]: Redis Pool max_connections=10 -- DoS-Mitigation T-04.8.1-04, ausreichend fuer Single-Worker Uvicorn
- [Phase 04.8.1]: TranscriptCallback is async Callable -- streaming pattern requires async callbacks for non-blocking asyncio operation
- [Phase 04.8.1]: Connection handle is opaque Any type -- adapter controls concrete type, interface doesnt leak implementation
- [Phase 04.8.1]: start()/finish() wrapped with iscoroutine check -- Deepgram SDK version may return bool or coroutine (Pitfall 5)
- [Phase 04.8.1]: AsyncAnthropic statt sync Anthropic -- blockiert nicht den asyncio Event Loop (Pitfall 2)
- [Phase 04.8.1]: D-05 Ground Truth: user_ewb_click/readiness_delta/hint_acted_on auf ShadowComparison -- Claude Outputs nur Vergleich, nie Training Targets
- [Phase 04.8.1]: SessionManager injected via set_session_manager() statt Depends() -- WebSocket langlebige Objekte
- [Phase 04.8.1]: Drei concurrent Tasks via asyncio.gather -- audio_receiver + stt_forwarder + analysis_loop, kein threading
- [Phase 04.8.1]: Audio Queue bounded 100 mit Drop-Oldest -- QueueFull -> get_nowait + put_nowait, kein Memory-Wachstum
- [Phase 04.8.1]: Sync redis-py in Flask (not async) — Flask is threaded, not asyncio
- [Phase 04.8.1]: pollErgebnis starts inactive — only activated by startPolling() or 3s WS timeout
- [Phase 04.8.1]: EWB clicks forwarded to Engine before Flask API call for D-05 ground truth
- [Phase 04.9]: System personality types seeded via INSERT OR IGNORE in _migrate() — idempotent, runs on every app start
- [Phase 04.9]: System training scenarios use org_id=first_org.id with erstellt_von=NULL as system marker — avoids NOT NULL constraint without schema change
- [Phase 04.9]: SCHWIERIGKEITEN internal keys unchanged (leicht/mittel/schwer) — only display labels updated to Einsteiger/Fortgeschritten/Experte
- [Phase 04.9]: generate_response_with_mood uses find/rfind JSON extraction pattern — consistent with generate_scoring() in same file
- [Phase 04.9]: generate_response() left untouched for sekretaerin mode backward compatibility — mood tracking only in new function
- [Phase 04.9-training-modul-upgrade-inserted]: scenario_id lookup in training_start extended to include system scenarios (erstellt_von IS NULL)
- [Phase 04.9-training-modul-upgrade-inserted]: personality_hidden=True only for schwierigkeit=schwer + is_custom — standard system types always visible
- [Phase 04.9-training-modul-upgrade-inserted]: D-07 stimmung only returned to frontend when schwierigkeit=leicht — Fortgeschritten/Experte stay blind
- [Phase 04.9-training-modul-upgrade-inserted]: selectModus() triggers loadPersonalityTypes() + shows t-typ-section — personality type selection appears after modus step
- [Phase 04.9-training-modul-upgrade-inserted]: confirmEndTraining() reused for hangup auto-transition — avoids duplication
- [Phase 04.9-training-modul-upgrade-inserted]: generate_scoring() punkte field (10+bonus) coexists with punkte_verdient (modus/hilfe penalty) — both serve different display purposes
- [Phase 04.9-training-modul-upgrade-inserted]: Chart containers injected as placeholders in buildScoring() innerHTML, rendered post-DOM by renderMoodChart()/renderWendepunkteDetail()
- [Phase 04.10]: Patience (geduld) modifiers mapped to existing leicht/mittel/schwer keys, not separate scale
- [Phase 04.10]: Transfer audio (wartemusik/klingeln/verbindungston) plays regardless of voice_available flag -- UI feedback, not TTS
- [Phase 04.10]: selectDiff scoped to #t-diff-section to avoid deselecting anruf-typ cards sharing t-diff-card class
- [Phase 04.10.1]: 4-zone step model (positiv/neutral/gereizt/wuetend) with fixed boundaries, no interpolation (D-01, D-02)
- [Phase 04.11]: T-04.11-02 mitigated: conv_id ownership check in api_postcall_analysis
- [Phase 04.11]: T-04.11-05 mitigated: duplicate Sonnet analysis guard per conversation
- [Phase 04.11]: Learning cards stored as vorschlag status until user explicit confirmation
- [Phase 04.11]: Gold #E8B040 re-introduced as scoped exception via --learning-gold CSS variable for learning card hints per D-10
- [Phase 04.11]: Learning card context capped at ~200 tokens (80 chars/card, max 5 cards) to avoid live prompt bloat
- [Phase 04.11]: Weekly report uses on-demand Sonnet generation with DB caching per ISO week (D-12)
- [Phase 04.12]: event_metadata Python attribute maps to metadata DB column — SQLAlchemy reserves metadata on declarative models
- [Phase 04.12]: json_extract for metadata queries in SQLite — works with current DB, PostgreSQL migration would need jsonb equivalent
- [Phase 04.12]: D-12 clearing only on success (gesamt_score >= 50) — failed training should not clear recommendation
- [Phase 04.12]: learning_card_rejected logged on archiviert status change (no dedicated reject route)
- [Phase 04.12]: Weekly report generates with training-only weeks (no live calls required)
- [Phase 04.12]: JS functions in app.js for PostCall training recommendation display
- [Phase 04.12]: Dashboard training-rec card placed before greeting row for maximum visibility
- [Phase 04.13]: Input validation 3-200 chars with control char stripping per threat model T-04.13-01
- [Phase 04.13]: PreCall panel inserted into mode overlay flow with _showPrecallOrActivate gateway
- [Phase 04.14]: CrmNote uses unique user_id (one note per user, upsert pattern)
- [Phase 04.14]: Status badge thresholds: 7d Ruhig, 14d Churn, avg_calls+kb>60 Top
- [Phase 04.14]: endpoint='crm_view' (not 'crm') to avoid Flask-Admin namespace collision
- [Phase 04.14]: inaccessible_callback returns 403 for logged-in non-superadmin, redirect to login for anonymous
- [Phase 04.17-pip-launcher-inserted]: PiP window restructured into 3 sections (setup/live/postcall); existing live-coaching tabs wrapped in pip-section-live unchanged per D-12/D-13
- [Phase 04.17-pip-launcher-inserted]: Profile list embedded as window._allProfiles via Flask template variable at page load — no new AJAX endpoint needed
- [Phase 04.17-pip-launcher-inserted]: calcPipScore uses ga_details.filter(x.erfolgreich) for behandelt rate — no backend change needed
- [Phase 04.17-pip-launcher-inserted]: pipStartCall calls startMicStream() synchronously to preserve getUserMedia user gesture
- [Phase 06-01]: Haiku used for pip streaming function per CLAUDE.md Live-cost constraint
- [Phase 06-01]: room=sid targeting on all pip_token emits prevents cross-user broadcast (T-06-02)
- [Phase 06-01]: JOIN to profiles in /api/skripte enforces org_id isolation (T-06-01)
- [Phase 06]: Removed duplicate .pip-consent-text CSS (old inline consent rule overrode new Phase 06 design)
- [Phase 06-03]: coaching_loop PiP forwarding uses pip_token_done directly (no streaming) since coaching tips are complete before emit
- [Phase 06]: Tab system fully removed from pip-live-window; replaced with split 55/45 KI/teleprompter layout in base.html
- [Phase 06]: Polling fully removed in pip-launcher.js — Socket.IO streaming (pip_stream_start/pip_token/pip_token_done) handles all AI results in Phase 06 split layout
- [Phase 06]: EWB _triggerEwb keeps POST to /api/analyse_line but drops .then() handler — streaming events deliver results instead
- [Phase 06.1]: EWB-Fallback startet mit e.kategorie (Profile-Editor-Format) vor e.typ/e.name/e.einwand
- [Phase 06.1]: Opener wandert vollstaendig in Teleprompter als Block 0 — keine Slot-A-Zuweisung mehr
- [Phase 06.1]: Scrollbar-Farbe rgba(0,0,0,0.15) bereits auf hellen Body (Plan 02) vorbereitet
- [Phase 06.1]: PiP-Default-Groesse 480x760: mehr Teleprompter-Bloecke sichtbar auf 1080p neben CRM
- [Phase 06.1]: Header explizit #0D1117 statt var(--page-bg) damit er unabhaengig vom Body-Scheme dunkel bleibt
- [Phase 06.1]: MediaStreamTrack.enabled=false statt track.stop() fuer Mute-Toggle — Deepgram bleibt verbunden, kein Reconnect-Overhead
- [Phase 06.1]: AnalyserNode nur an source connected (nicht an destination) — kein Audio-Echo, reine Pegel-Visualisierung
- [Phase 06.1]: Integer-basierter localStorage-Read (10-100) statt Float — konsistenter mit Slider min/max, einfacher zu validieren
- [Phase 06.1]: _updateSliderFill als separate Funktion fuer iOS-style Slider-Fill via --pip-slider-pct CSS-Variable
- [Phase 06.2]: KEYWORD_TO_PROFILE_ALIASES an echter salesnerve.db verifiziert: plan-draft Aliase durch real-DB-Werte ersetzt (kategorie/typ)
- [Phase 06.2]: EinwandKeywordMatcher mit threading.Lock: match_with_dedup() wird aus Deepgram-Thread und Analyse-Thread gleichzeitig aufgerufen
- [Phase 06.2]: slot1_variant_busy_until in ls.state statt Funktions-Attribut: einzige Quelle der Wahrheit, vereint Keyword-Pipe und analyse_loop ohne Race
- [Phase 06.2]: Lock-Unifikation aus Wave 4 in Plan 02 vorgezogen: analyse_loop._variant_busy_until vollstaendig durch ls.state ersetzt
- [Phase 06.2]: slot0LastKeywordTyp 3s-Fenster: gleicher typ -> pip_token_done ueberschreibt nicht
- [Phase 06.2]: mute_mic emit NACH state-Toggle, damit Wert korrekt an Backend
- [Phase 06.3]: D-08: Fallback-Variante (a) — non-streaming analysiere_mit_claude for PiP sessions, minimal regression surface
- [Phase 06.3]: D-10: ANALYSE_INTERVALL raised to 4s — intelligence-only loop, not latency-sensitive, halves API call volume
- [Phase 06.3]: D-11: _last_slot/_last_slot_time removed — confirmed write-only dead code
- [Phase 06.4]: sessionStorage for headset flag (resets on tab close for DSGVO)
- [Phase 06.5]: Consent-Modal-Callback dreistufig (accepted/rejected/cancelled) — rejected setzt mode='cold_call' + consentDone=true, rekursiver startCall greift Headset-Gate
- [Phase 06.5]: state.consentDone statt sessionStorage — Flag lebt in Launcher-Instanz, wird via _cleanup() resettet (nicht wie Headset der sessionStorage ueberlebt)
- [Phase 06.5]: Consent-Gate steht in startCall() NACH Headset-Gate, VOR close() — bei 'Abbrechen' bleibt Launcher auf Step 5 sichtbar
- [Phase 06.5]: Default-Text em-dash als \u2014 Unicode-Escape (POLISH-12 Encoding-Regel, keine nativen Umlaute)
- [Phase 07.2]: [Phase 07.2-01]: _parse_kunden_meta uses module-level import re (dashboard.py line 2) — no new import needed
- [Phase 07.2]: [Phase 07.2-01]: schwierigkeit_raw whitelist-gated to leicht|mittel|schwer only (T-07.2-04b Tampering-Mitigation for Plan-03-URL)
- [Phase 07.2]: [Phase 07.2-01]: _log_id=None default before try-block — robust against DB-persist failure; frontend detects None and falls back to overlay-flow
- [Phase 07.2]: [Phase 07.2-01]: result['log_id']=_log_id as dict-assignment not jsonify-unpack — avoids scoring-dict collision risk if generate_scoring() later adds log_id
- [Phase 07.2]: [Phase 07.2-02]: Training-Hero-Breakdown removed via positive typ=='live' branch (Schritt F Zweite Form) — semantically clearer than Training-Negation, no dead code
- [Phase 07.2]: [Phase 07.2-02]: Scoring-Fail-Sentinel detection in Sektion 14 case-insensitive (|lower) — tolerates future wording changes in routes/training.py fallback
- [Phase 07.2]: [Phase 07.2-02]: All 14 new CSS rules use var(--*) tokens exclusively — no new hex colors, no yellow/gold regression, insertion between .n-session-detail-future-text and @media block
- [Phase 07.2]: [Phase 07.2-03]: Redirect-Fallback /analytics (not /logs) — /logs route does not exist; analytics_page is the history page (Rule-1 auto-fix)
- [Phase 07.2]: [Phase 07.2-03]: endTraining() no-conversation-guard refactored to alert+resetTraining instead of showPhase('scoring')+#t-scoring.innerHTML (Rule-3: original guard depended on now-removed DOM)
- [Phase 07.2]: [Phase 07.2-03]: saveGeneratedPersonality() orphan removed — only caller was save-personality-div inside removed scoring overlay. Re-introduction under POLISH-37 (Rule-1 dead-code)
- [Phase 07.2]: [Phase 07.2-03]: Button URL uses Jinja qparams-list-join idiom (not direct string concat) — avoids trailing-& edge cases for 0/1/2 param combinations
- [Phase 07.2]: [Phase 07.2-04]: CSS_VERSION bumped twice in one plan — '20260420-4' (initial Task 4.1) + '20260420-5' (precautionary after UAT-R1 fixes, even though fixes were HTML-only) — accepts cheap cache-invalidation to avoid mixed-state browser renders
- [Phase 07.2]: [Phase 07.2-04]: Custom-Persona-Kunden-Subtext via phasen_details JSON-Keys 'custom_persona_*' — no DB migration; kollisionsfrei zu Scoring-Keys; Fallback-Pfad in session_detail() setzt kunden_display_name/_icon zusaetzlich zu Wave-1-Keys
- [Phase 07.2]: [Phase 07.2-04]: Umlaut-Plural 'Einwände' via explicit Jinja if/else (not inline {% if %}e{% endif %}) — CLAUDE.md user-text rule; Inline-Pluralisierung kann Umlaut-Wechsel strukturell nicht abbilden
- [Phase 07.2]: [Phase 07.2-04]: _derive_practice_recommendations() order-preserving dedupe by explanation-key before recs[:3]-Trim — defense-in-depth im Training- UND Live-Branch, fixt Cold-Call-B1-Case (3 identische Bullets bei 3 unbehandelten Einwaenden)
- [Phase 07.2]: [Phase 07.2-04]: UAT-R2 B2-B5 out-of-scope -> Backlog POLISH-38/-39/-40/-41 — 07.2-Scope ist Scoring-UI-Konsolidierung, nicht Live-Persistenz-Plumbing; pre-existing Bugs vor 07.2
- [Phase 07.2]: [Phase 07.2-04]: 3 Deploy-Runs statt 1 (R1/R2/R3) — analog 07.1 DEVIATIONS-Workflow mit Fix-Commits auf main + CSS-Bump + Re-Deploy + Re-UAT; de facto 2 UAT-Runden (besser als 07.1 mit 5)
- [Phase 07.2]: [Phase 07.2-04]: POLISH-29 refined als Produkt-Entscheidung: 'EWB-Button gedrueckt = Einwand behandelt' — verbindliche Standard-Definition fuer alle Metriken/Labels; Referenz fuer POLISH-38-Fix
- [Phase 08.5]: is_default column exists in prompt_versions — Wave 2 seeds can use it safely without column list adjustment
- [Phase 08.5]: tabu_begriffe stored in profiles.daten JSON (not DB column) per D-15 — consistent with eigene_formulierungen/beweise pattern from Phase 08
- [Phase 08.5]: sentence-transformers>=2.7.0 minimum version for paraphrase-multilingual-MiniLM-L12-v2 DACH multilingual FAQ matching
- [Phase 08.5]: _parse_json EXISTS in services/claude_service.py at line 463 — imported directly in classify_utterance, no inline substitute needed
- [Phase 08.5]: sentence_transformers not installed in dev env — test stub injected via sys.modules.setdefault before import; CI works without model download
- [Phase 08.5]: active_profile_id added to ls.state + set_active_profile extended with profile_id param — all 4 call sites updated
- [Phase 08.5]: _qa_pipeline_dispatch extracted as module-level helper in claude_service.py — analyse_loop calls it in single line; enables TDD without threading setup
- [Phase 08.5]: savedAnrede5 preset into precallFormData.anrede at renderStep5 entry — anredeForSession payload wiring unchanged
- [Phase 08.5]: lastSessionAnrede persisted in _cleanup() before state reset — stored in both state and localStorage
- [Phase 08.5]: Single-script auto-select: skripte.length===1 pre-selects but renderStep5() NOT skipped (D-10 edge case)
- [Phase 08.5]: generate_response/generate_response_with_mood: version resolved for FT logging only, not prompt override — callers pre-build system_prompt via build_customer_prompt/build_personality_prompt, signatures unchanged
- [Phase 08.5]: user_id=0 default in all 3 training prompt call sites — per-user A/B routing for training deferred until user_id threaded through from routes/training.py
- [Phase 08.5]: tabu_begriffe stored in profile.daten['basis']['tabu_begriffe'] — canonical location for Plan 03 read path
- [Phase 08.5]: PROFILE_ID already exposed by inline script in profile_editor.html — no change needed for profile_editor.js
- [Phase 08.5]: Raw fetch used in profile_editor.js — no shared apiClient helper exists in this codebase
- [Phase 08.19.2]: sec-header Pattern mit div.sec-header/h2.sec-title anstatt direkter div.sec-title
- [Phase 08.19.2]: Erlaubnis/Pitch bleiben als textarea in sec-gespraechsleitfaden (kein crudList in Phase 08.19.2)
- [Phase 08.19.2]: Unified ProfileOpener architecture: type-Diskriminator opener/pitch/erlaubnis
- [Phase 08.19.2]: Dual-write pattern: CRUD-Write -> concatenate all items -> UPDATE Profile.daten (transitional bis 08.20)
- [Phase 08.19.2-03]: save-toast als span in Topbar eingefuegt (display:none initial) — crudList-success-handler steuert Sichtbarkeit via querySelector
- [Phase 08.19.2-03]: wizard-banner inline-styles (#22c55e) bleiben erhalten — anderes Element als save-toast, out-of-scope fuer Plan 03
- [Phase 08.19.2-03]: varianten-Feld aus addEinwand() und getEinwaende() entfernt — konsistent mit D-03 Sub-Feld-Spec (nicht in neuer Reihenfolge aufgefuehrt)
- [Phase 08.19.2-03]: goSec() war bereits korrekt mit getBoundingClientRect 16px offset (Plan 02) — keine Aenderung noetig
- [Phase ?]: 08.19.2-04: EWB-Placeholder als span.sec-hint — gleiche CSS-Klasse wie sec-hint, passend als Inline-Hinweis nach Sub-Sektion-Header

### Roadmap Evolution

- Phase 08.12 inserted after Phase 08.11: Stabilisierung Cleanup-Hotfix DB-Naming + User-Migration (URGENT) — Post-Deploy-Bugs aus Block-F-Live: salesnerve.db Cleanup, .env-Korrektur, Rename-Code in app.py:710-719 entfernen, Kommentar-Drift fixen, idempotente User-Migration für onboarding_done=False.
- Phase 08.11 inserted after Phase 08.10: Stabilisierung Block F Classic-View-Deprecation (URGENT) — Reihenfolge-Korrektur durch Cross-AI-Review (Gemini): F muss VOR Block B (08.10) laufen, weil F /api/frage, /api/ewb_trigger und Classic-Socket-Handler entfernt (~600 Z. app.js). 08.10-Pläne werden nach 08.11-Done neu geplant. Pflicht-Lektüre: MASTER-AUDIT-v2.md Sektion "BLOCK F".
- Phase 08.10 inserted after Phase 08.9: Stabilisierung Block B Auth-Härtung (URGENT) — tbd via /gsd-plan-phase 08.10. Pflicht-Lektüre: MASTER-AUDIT-v2.md Sektion "BLOCK B". Cross-AI-Plan-Review geplant.
- Phase 08.9 inserted after Phase 08.8: Stabilisierung Block C Schema-Drift-Cleanup (URGENT) — 5 Tasks: LB-11 Onboarding-Redirect reaktivieren, H-31/HSR-2 BRANCHE_TEMPLATES auf basis.*-Schema, Wizard-Create auf basis.*-Schema, LB-3 QA-Pipeline Komplett-Fix (profile_data aus Live-Session, confidence als float/None, inkl. WR-01/WR-03), H-25 Rollen-Check _rolle() einbauen. Quelle: MASTER-AUDIT v2 Block C.
- Phase 08.8 inserted after Phase 08.7: Stabilisierung Block I — Dead-Code-Prune (URGENT) — 11 Tasks ~4-6h: H-3/H-4 analysiere_mit_claude_streaming/_build_system_prompt/_get_erfolgsquoten löschen, H-27 Coach-Routes, H-28 Personality-Save, 9 Orphan-Routes, 3 Orphan-Templates, ewb_top2 Cleanup, Legacy-opener Entscheidung, H-1 finetune_logging.py + FtPipelineEvent-Drop (DB-Migration). Quelle: MASTER-AUDIT v2 Block I.
- Phase 08.7 inserted after Phase 08.6: Stabilisierung Block H — Test-False-Greens raus (URGENT) — 6 Tasks ~4h: inspect.getsource-Tests löschen/umbauen, Migration-Tests auf Fresh-DB, RED-Gate-Tests löschen, tts_comparison.py → scripts/, CLAUDE.md Regel. Pflicht-Vorarbeit für Block I (Dead-Code-Prune). Quelle: MASTER-AUDIT v2 Block H.
- Phase 08.6 inserted after Phase 08.5: Stabilisierung Block A Quick-Wins (URGENT) — 8 triviale Launch-Blocker-Fixes in < 30 min: LB-5/LB-6 State-Writer, LB-12 Ghost-Columns, LB-13 ROI-Card, CORS-Domain, unused Imports, Theme-400, Language-Restrict. Quelle: MASTER-AUDIT v2 Block A.
- Phase 08.5 inserted after Phase 08: Universal Response Loop — Launch-kritische Erweiterung des Live-Loops. Claude klassifiziert jede Kundenäußerung in 4 Kategorien (einwand_known/einwand_unknown/frage/smalltalk-none). Unbekannte Einwände + Fragen aus Profil-Daten beantwortet, nie halluziniert. FAQ-Feld + Exclusion-Liste, Anrede-UX-Umzug, Training-Pipeline v2-modular. Löst POLISH-56. Aufwand 30-36h. (INSERTED)
- Phase 08 added: EWB-Qualität & Profil-Tiefe (Launch-kritisch) — 6 neue Profil-Felder, POLISH-55 Behandelt-Semantik, A/B-Prompt-Framework, Quality-Gates. Vorbereitet Phase 08.5 (Q&A) + 07.5 (EWB-Feed-Redesign).
- Phase 03.1 inserted after Phase 03: Frontend Redesign (INSERTED) — app-page redesign before payments
- Phase 04.1 inserted after Phase 04: Live-Mikrofon Fix: PyAudio → Browser getUserMedia (URGENT) — Phase 4 paused (Gewerbeschein blocker), mic fix inserted as 4.1
- Phase 04.2 inserted after Phase 04: Cold Call und Meeting Modi (URGENT) — dedicated modes for cold call (only consultant audio) and meeting (consent popup) before Phase 5
- Phase 04.2.1 inserted after Phase 04.2: UI/UX Overhaul — Dashboard, Live-Assistent, Kompaktmodus (URGENT) — complete layout overhaul, Getclose.ai design reference, PiP overlay
- Phase 1 (Business Setup) removed from GSD tracking — user handles manually (Gewerbeanmeldung, Geschäftskonto, etc.)
- Phase 04.6.1 inserted after Phase 04.6: Auth-Upgrade Google + Microsoft OAuth Login (URGENT) — Authlib-basierter OAuth-Flow für Google + Microsoft, User-Model nullable passwort_hash, Login-UI Buttons
- Phase 04.6.2 inserted after Phase 04.6.1: deploy hardening and oauth polish (URGENT) — gehört zum Auth-Block (completed 2026-04-07: tar-over-ssh deploy, header→app.getnerve.app link, MS Consumer-tenant block + conditional prompt=consent, onboarding diagnostic logging)
- Phase 04.8.1 inserted after Phase 04.8: Echtzeit-Engine Rebuild — Split-Architektur (URGENT) — Async FastAPI+uvicorn WebSocket Engine als eigener Service, Redis Bridge zu Flask, STT/LLM Abstraktionsschicht, HTTP-Polling durch WebSocket-Push ersetzen. Fundament für eigene KI, eigene STT, Skalierung.
- Phase 6 added: PiP Komplett-Rebuild — Neues Layout (EWB+KI oben, Skript-Teleprompter unten), Claude Streaming, semantische Skript-Position-Erkennung, Transparenz-Regler. Ersetzt bestehenden PiP-Code.
- Phase 06.1 inserted after Phase 06: PiP UAT-Fixes — Bugs (EWB `[object Object]`, Scrollbar, Opener belegt Slot), Design (Farben umkehren, Mic-Indikator, Opacity-Slider), Proportionen (Teleprompter größer, EWB kompakter) (URGENT)
- Phase 7 added after Phase 06.5: MAIN DESIGN — App-weite Design-Konsolidierung (RETRO-DOC, completed 2026-04-18) — Bulk-Migration Gelb/Gold -> Grau/Teal, data-theme Dead-Code entfernt, PiP light-Modus, nerve.css Farb-Tokens als Single Source of Truth, Umlaut-Regel kodifiziert in CLAUDE.md
- Phase 07.1 inserted after Phase 7: POLISH-24 Session-Detail-Redesign — /session/<id> komplett auf MAIN DESIGN umbauen (8 Sektionen: Header, Score-Hero mit Breakdown, Kaufbereitschafts-Verlauf-Chart, Einwand-Timeline, Phasen-Visualisierung, Skript-Abdeckung, Painpoints, PreCall-Briefing), inkl. DB-Migration kb_verlauf TEXT (URGENT)

### Pending Todos

- [ ] **Phase 3.1 gap closure**: 15 visual UAT issues from browser testing — run `/gsd:plan-phase 03.1 --gaps` to plan fixes
- [ ] **landing.html + login.html**: Not yet migrated to nerve.css — agreed to do after UAT
- [ ] **Phase 1 (manual)**: Gewerbeanmeldung, Geschäftskonto, USt-IdNr, Steuerberater — user handles independently, not tracked here
- [ ] After gap closure: plan Phase 4 (Payments & Legal)

### Blockers/Concerns

- **Phase 4 dependency**: Phase 4 (Stripe) needs verified Stripe account → requires Gewerbeanmeldung + Geschäftskonto (Phase 1 manual, ~3-5 weeks) — user is handling this in parallel
- Research flags: AVV signing portal locations for Deepgram/Anthropic/ElevenLabs should be verified directly. Stripe Tax / VAT invoice configuration for Germany needs explicit research during Phase 4 planning.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260401-qr4 | Fix sidebar user avatar visibility and light/dark mode toggle | 2026-04-01 | 972cd94 | [260401-qr4-fix-sidebar-user-avatar-visibility-and-l](./quick/260401-qr4-fix-sidebar-user-avatar-visibility-and-l/) |
| 260421-kwm | POLISH-45 headset-confirm-state clear on logout + POLISH-38.1 manual_ewb success flag | 2026-04-21 | e9acc10 + 585f567 | [260421-kwm-polish-45-polish-38-1-nachzug-headset-mo](./quick/260421-kwm-polish-45-polish-38-1-nachzug-headset-mo/) |
| 260421-lpx | POLISH-38 Haupt-Fix: re-aggregate einwaende_gesamt/behandelt from ObjectionEvent + migration | 2026-04-21 | 451c909 + 29c8b71 | [260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou](./quick/260421-lpx-polish-38-haupt-bug-einwaende-gesamt-cou/) |
| 260421-mwy | POLISH-54: aggregate einwaende_liste from ObjectionEvent for cold-call postcall | 2026-04-21 | 497350d | [260421-mwy-polish-54-einwaende-liste-aus-objectione](./quick/260421-mwy-polish-54-einwaende-liste-aus-objectione/) |
| 260424-ekk | Phase 08.5 Post-Execute-Refinement: Tabu Alternativen + Profil-Editor Sektion 15 + Low-Confidence Rueckfrage | 2026-04-24 | 5e2b438 | [260424-ekk-phase-08-5-post-execute-refinement-tabu-](./quick/260424-ekk-phase-08-5-post-execute-refinement-tabu-/) |
| 260424-fo0 | Phase 08.5 Nachbesserung: Standard-Paare einfuegen Button + Auto-Vorschlag Placeholder in Sektion 15 | 2026-04-24 | 5d6478c | [260424-fo0-phase-08-5-nachbesserung-standard-paare-](./quick/260424-fo0-phase-08-5-nachbesserung-standard-paare-/) |
| 260424-h7u | Phase 08.5 Nachschaerfung: Tabu-Filter kontext-bewusst mit protected-words Safety-Net | 2026-04-24 | c059e5d | [260424-h7u-phase-08-5-nachschaerfung-tabu-filter-ko](./quick/260424-h7u-phase-08-5-nachschaerfung-tabu-filter-ko/) |
| 260428-c2x | Polish-Cycle 2: Header-Link entfernen + Button-Konsolidierung Primary/Destructive/Secondary + Lucide-trash-2 confirmDelete | 2026-04-28 | b57c0cf | [260428-c2x-polish-cycle-2-button-konsolidierung](./quick/260428-c2x-polish-cycle-2-button-konsolidierung/) |
| 260428-d4r | Polish-Cycle 3: Save-btn schwarz, Vorschläge-disabled, Spacing, Card-Toggle-Isolation, Chevron teal, crud-del→trash, tip-icon, Tabu-x→trash, Visual-Separator | 2026-04-28 | 9d6759d | [260428-d4r-polish-cycle-3-card-toggle-loeschen](./quick/260428-d4r-polish-cycle-3-card-toggle-loeschen/) |
| 260428-e5s | Polish-Cycle 4: crud-body bg transparent (Cycle-3-Revert), Textarea min-height 100px, Trash in Card-Header, Gesprächsphasen Sub-Label | 2026-04-28 | 451d11e | [260428-e5s-polish-cycle-4-card-body-layout](./quick/260428-e5s-polish-cycle-4-card-body-layout/) |
| 260428-f7p | Polish-Cycle 5 KRITISCH: FAQ deleteFaq/updateFaq CSRF-Fix + r.ok-Guards + saveTabuToServer Guard + FAQ-Trash in Card-Header | 2026-04-28 | fcdf456 | [260428-f7p-polish-cycle-5-faq-csrf-fix](./quick/260428-f7p-polish-cycle-5-faq-csrf-fix/) |
| 260429-dmd | Polish 08.19.3: FAQ-Card-Header truncation — JS slice(0,40) entfernt + CSS ellipsis + title-Tooltip | 2026-04-29 | bba802d | [260429-dmd-faq-header-truncation](./quick/260429-dmd-faq-header-truncation/) |
| 20260430-css | 08.20.2 CSS-Hotfix U1-U3: nav-live-box 90vh scroll, launcher-step overflow guard, launcher-inline-edit-btn | 2026-04-30 | ecf8d41+df20777+67beec0 | [20260430-css-modal-button-hotfix-u1u2u3](./quick/20260430-css-modal-button-hotfix-u1u2u3/) |
| 20260430-r6r7 | Block-J R6+R7: Vorwissen-Duplikat (step45/renderStep4b) entfernt + Step-5-Zurück zu Step-4 korrigiert | 2026-04-30 | 2613fd3+18487b7 | [20260430-block-j-r6-r7-vorwissen-zurueck](./quick/20260430-block-j-r6-r7-vorwissen-zurueck/) |

## What's Done

| Phase | Plans | Status |
|-------|-------|--------|
| Phase 08.8: Block I Dead-Code-Prune | 5/5 ✓ | Complete 2026-04-25 — ~643 Zeilen entfernt (H-1/H-3/H-4/H-11/H-27/H-28/6 Orphan-Routes/2 Templates/ewb_top2). pytest 265 passing. |
| Phase 2: Product Fixes | 6/6 ✓ | Complete — all PROD requirements done |
| Phase 3: Infrastructure & Deployment | 3/3 ✓ | Complete — VPS live on getnerve.app (178.104.82.166), HTTPS, WAL, CORS locked |
| Phase 3.1: Frontend Redesign | 6/6 ✓ | Complete — nerve.css deployed, all app pages migrated. Visual UAT: 15 issues found. |
| Phase 1: Business Setup | — | Skipped from GSD — user handles manually |
| Phase 04.8.1: Echtzeit-Engine Rebuild | 5/5 ✓ | Complete — FastAPI+uvicorn RT Engine, Redis Bridge, STT/LLM Abstraktion, Shadow Mode, WS Push, Deployment |
| Phase 04.10: Training-Realismus | 3/3 ✓ | Complete — 3 Sekretärin-Typen, Audio-Simulation (13 MP3), Transfer-Sequenz, Hangup-Popup, Anruf-Typ Auswahl, linearer Setup-Flow, Kundentyp-Generator mit Profilbezug, Gender-Voice-Matching, Siezen, globaler Error Handler |
| Phase 04.10.1: Emotionale TTS-Stimmen | 1/1 ✓ | Complete — MOOD_VOICE_ZONES (4 Zonen), mood_to_voice_settings(), 3 Sekretärin-Presets, text_to_speech() erweitert, 3 TTS Call Sites verdrahtet |

**Phase 3 verification (manual):**

- App accessible at getnerve.app over HTTPS ✓
- VPS: Hetzner CX22, IP 178.104.82.166 ✓
- Remaining checks (Socket.IO 101, WAL mode, CORS lock): user to confirm on VPS

## Session Continuity

Last session: 2026-05-03T11:36:01.726Z
Stopped at: Completed 08.20.2-01-PLAN.md
Resume file: None
