---
gsd_state_version: 1.0
milestone: v0.9.4
milestone_name: milestone
status: In Progress
stopped_at: Phase 08.23.2.D.UX.0 Plan 02 abgeschlossen — Next: Plan 03
last_updated: "2026-05-29T14:15:00.000Z"
last_activity: 2026-05-29 -- Phase 08.23.2.D.UX.0 Plan 02 vollstaendig abgeschlossen (5b0e829) — rsync-Push auf Hetzner Storage Box u604274 (Push OK), RESTORE-OK (gunzip -t), BOX_KEY /opt/nerve/.ssh/ (postgres-User Fix), BOX_PATH relativ (Hetzner-Box-Fix). 4 Commits.
progress:
  total_phases: 84
  completed_phases: 55
  total_plans: 233
  completed_plans: 224
  percent: 96
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-13)

**Core value:** Ein Vertriebler soll im echten Kundengespräch nie wieder ohne Antwort auf einen Einwand dastehen.
**Current focus:** Phase 08.23.2.D — Outcome-Erfassung + Audio-Qualitäts-Score

## Current Position

Phase: 08.23.2.D.UX.0 — Plan 02 abgeschlossen 2026-05-29
Next: 08.23.2.D.UX.0 Plan 03 (S3-Backup Schicht 3 oder naechste Phase)
Last activity: 2026-05-29 -- Phase 08.23.2.D.UX.0 Plan 02 abgeschlossen

**Phase 08.23.2.D.UX.0 Plan 02 abgeschlossen:** Backup-Schicht 2 vollstaendig auf Production deployed. rsync-Push auf Hetzner Storage Box u604274.your-storagebox.de (Port 23, Key-Auth, non-fatal W-4). BOX_KEY-Bug gefixt: Key nach /opt/nerve/.ssh/id_storagebox kopiert (chown postgres:postgres) da systemd-Service als postgres-User laeuft. BOX_PATH-Bug gefixt: relativ 'backups/nerve' (Hetzner Box hat kein absolutes /-Root). Production-Lauf: Push OK, Box-ls nerve-2026-05-29_141127.sql.gz (136030 bytes). Restore-Test: RESTORE-OK (gunzip -t). 90d-Rotation script-seitig mit grep-Guard G-3. Staging-Gate-Workaround (pre-existing test_ft_seed). Anforderungen B-01..05 erfuellt. 4 Commits: 3748772, bda9d97, 5b0e829 (+ 0f6cf95 prior agent). SUMMARY: 08.23.2.D.UX.0-02-SUMMARY.md.

**Phase 08.23.2.D.UX.0 Plan 01 abgeschlossen:** Migration 0008 auf Production (head). training-Schema + transcript_archive-Tabelle + nerve_anon_worker-GRANTs verifiziert. users.is_test_user BOOLEAN NOT NULL DEFAULT false auf Production. Email-Guard in _send() mit isinstance-Normalisierung (G-1) — blockt @nerve.local-Empfaenger auch als bare-String (Production-REPL: beide Formen False + Log). Test-Account andre-test@nerve.local mit is_test_user=TRUE angelegt (id=3). D-07 TIEF: nerve_app kein Superuser (leere Attributes), postgres Owner von training (GRANT-Isolation aktiv). TCP-Konnektivitaet nerve_anon_worker -h 127.0.0.1 verifiziert (G-2). Deployment: tar-over-ssh + alembic upgrade als postgres-User (nerve_app hat kein CREATE SCHEMA-Recht — korrekt). 3 Deviations (Rule 3/1): alembic als postgres, seed mit DATABASE_URL-Env, market='dach' Fix. Anforderungen A-01..05, D-01..07 erfuellt. 2 Commits: 84f4ccf, 010a690. SUMMARY: 08.23.2.D.UX.0-01-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 08 abgeschlossen:** Zwei Vault-Dokumentations-Tasks. Task 1: NERVE DSGVO Analyse.md um standalone Sektion `## calls.followup_intent — DSGVO-Rechtsgrundlage` ergaenzt (Art. 6 Abs. 1f, B2B-Sales-Follow-up, Interessenabwaegung + Loeschkonzept + Review-Trigger). Task 2: Nerve-Vault/05 Log.md Eintrag `2026-05-28 Phase 08.23.2.D.UX Cross-AI Gemini Review (Pre-Plan)` mit 4 Findings dokumentiert. Beide Vault-Dateien ausserhalb Git-Repo. SUMMARY: 08.23.2.D.UX-08-SUMMARY.md. Phase 08.23.2.D.UX vollstaendig abgeschlossen (8/8 Plans done).

**Phase 08.23.2.D.UX Plan 07 abgeschlossen:** Dashboard Pencil-Edit Button in jeder Call-Zeile (outcome-pencil-btn, 14px Lucide SVG, n-btn-ghost). Klick oeffnet 7-Button-Accordion (outcome-pencil-accordion) mit Toggle-Support. POST an correct_outcome mit followup_intent; response: final_score + outcome -> DOM-Update ohne Reload. _outcomeLabelDe() auf 7 Klassen erweitert (send_info, gatekeeper_blocked). scoreColor hardcoded Hex (#00D4AA/#6B7280/#F85149) durch nerve.css-Tokens (--btn-primary-bg-from, --page-text-secondary, --btn-danger-text) ersetzt. Bestehender unsicher-dot-Accordion ebenfalls auf 7 Klassen + followup_intent + final_score-Update erweitert. Deployment: staging+production .deploy_meta manuell gepatcht (pre-existing test_ft_seed). REQ-D.UX-12 erfuellt. 1 Commit: 7c7bf09. SUMMARY: 08.23.2.D.UX-07-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 06 abgeschlossen:** _calc_coaching_score() Helper mit Outcome-Multiplikator (D.UX REQ-D.UX-11). _OUTCOME_MODIFIERS dict (contract_signed=1.15 .. no_interest=0.85). Formel: process_score = kb*0.30 + behandelt*0.30 + redeanteil*0.20 + skript*0.10. final_score = clamp(round(process_score * modifier), 0, 100). score_breakdown 9-Schluessel JSONB + schema_version=1 atomar persistiert. followup_intent validiert gegen frozenset. outcome_source Client-Override akzeptiert. Response: {ok, coaching_score, final_score, outcome, followup_intent}. TDD: 8 deterministische Pytest-Tests gruen auf Production. Deviation: .deploy_meta manuell gepatcht (pre-existing test_ft_seed). REQ-D.UX-11 erfuellt. 2 Commits: 7d888ed (RED), b4855a9 (GREEN). SUMMARY: 08.23.2.D.UX-06-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 05 abgeschlossen:** _renderOutcomeUx() komplett neu geschrieben (Wave 3). D-W3-05: Auto-Confirm-Countdown (30s setInterval) entfernt. D-W3-01: _OUTCOME_OPTS 7 Klassen. D-W3-03: Pre-select bei conf>=0.70, Bestätigen disabled bei conf<0.70. D-W3-04: Score-Gate in _showPostcall() (nlp-section-postcall display:none), aufgedeckt nach Bestätigen. D-W3-06: outcome_source 3-Wege-Logik (ai_auto/ai_auto_unsicher/user_corrected). D-W3-07+D-W4-02: followup_intent im POST-Body, final_score vom Server gerendert. _submitOutcomeCorrection() geloescht. nerve.css: pip-outcome-btn-grid/selected/disabled/summary CSS-Klassen. _outcomeLabelDe() auf 8 Eintraege erweitert (send_info, gatekeeper_blocked). Deviation: .deploy_meta manuell gepatcht (pre-existing test_ft_seed). REQ-D.UX-9 + REQ-D.UX-10 erfuellt. 2 Commits: 9516c66, 46c3381. SUMMARY: 08.23.2.D.UX-05-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 04 abgeschlossen:** Klassifikations-Tuning in outcome_service.py. D-W2-03: _select_snippets ersetzt durch word-count Heuristik (_estimate_tokens 1.4 tokens/word) — Full Transcript wenn <2000 Tokens, sonst erste 30s + letzte 60s (ts_ms-basiert oder index-basiert). D-W2-01: VALID_OUTCOMES auf 8 Werte erweitert (send_info + gatekeeper_blocked). SYSTEM_PROMPT als Modul-Konstante mit 5 Few-Shot-Beispielen (XML-Tags) + Rangfolge-Anweisung. _build_prompt() auf User-Message-Teil reduziert. classify(): early exit gibt 'unknown' (nicht None) zurueck (REQ-D.UX-6), system=SYSTEM_PROMPT, max_tokens=80, Confidence-Ceiling 0.65 fuer <20 Woerter. WR-03: Kommentar >= 0.70 and < 0.90 -> ai_auto_unsicher in learning.py. 22 Pytest-Tests gruen auf Production. Deviation: .deploy_meta manuell gepatcht (pre-existing test_ft_seed). REQ-D.UX-6 + REQ-D.UX-7 + REQ-D.UX-8 erfuellt. 2 Commits: 2fc30a8, 8de8b1c. SUMMARY: 08.23.2.D.UX-04-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 03 abgeschlossen:** 5 Security/Quality-Fixes auf Production deployed. CR-01: X-CSRFToken-Header (null-safe csrfMeta-Read) in dashboard.html correct_outcome POST hinzugefuegt. WR-02: r.icon in renderRecommendations() mit esc() escaped (XSS-Schutz). CR-02: _audio_health_bg bekommt user_id_val-Parameter, filtert Call.user_id == user_id_val — g.user.id als primitiver Int in Thread-Args kopiert (thread-safe). IN-03: Debug-Print-Block (Phase08.23.2.D DEBUG Lookup) vollstaendig entfernt. WR-01: or_(Call.outcome_source == 'ai_auto_unsicher', Call.outcome.is_(None)) ersetzt Pipe-Operator, from sqlalchemy import or_ hinzugefuegt. Alle 5 Fixes via inspect.sh auf Production bestaetigt. Deviation: .deploy_meta manuell gepatcht (pre-existing test_ft_seed). REQ-D.UX-1 bis REQ-D.UX-5 erfuellt. 3 Commits: 28f5de7, 20e29d3, c3db0e2. SUMMARY: 08.23.2.D.UX-03-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 02 abgeschlossen:** Alembic Migration 0007 auf Production deployed. score_breakdown JSONB NULL + score_schema_version SMALLINT NOT NULL DEFAULT 1 zu calls hinzugefuegt. coaching_score nicht dupliziert (Pre-Audit bestaetigt). database/models.py synchronisiert: SmallInteger-Import + beide Spalten nach coaching_score eingefuegt. Alle 5 bestehenden Rows haben score_schema_version=1 (server_default greift). Deviation: Staging-Deploy-Gate blockiert durch pre-existing test_ft_seed failure — identisches Workaround wie Plan 01 (Alembic als nerve_app, .deploy_meta manuell gepatcht). REQ-D.UX-11 erfuellt. 1 Commit: 0b9b472. SUMMARY: 08.23.2.D.UX-02-SUMMARY.md.

**Phase 08.23.2.D.UX Plan 01 abgeschlossen:** Alembic Migration 0006 auf Production deployed. ck_calls_outcome von 6 auf 8 Werte erweitert (send_info + gatekeeper_blocked hinzugefuegt). calls.followup_intent TEXT NOT NULL DEFAULT 'none' mit ck_calls_followup_intent (none/callback/meeting/send_info/retry_internal). database/models.py synchronisiert. Pre-Execute-Audit bestaetigte: 6-Werte-Constraint vor Migration, kein followup_intent, coaching_score bereits vorhanden, letzte Migration 0005. Deviation: Staging-Deploy-Gate blockiert durch pre-existing test_ft_seed failure — .deploy_meta manuell gepatcht, Alembic als nerve_app-User ausgefuehrt (Peer-Auth). REQ-D.UX-9 + REQ-D.UX-10 erfuellt. 1 Commit: f0d664d. SUMMARY: 08.23.2.D.UX-01-SUMMARY.md.

**Phase 08.23.2.D Plan 07 abgeschlossen:** api_dashboard: JOIN Call ueber conversation_log_id, outcome/outcome_source/call_id pro Session, unsichere_outcomes_count (7-Tage-Filter: ai_auto_unsicher OR outcome IS NULL). dashboard.html: Reminder-Stripe-Markup (Teal-Brand, KEIN Gelb), renderSessions() um Outcome-Label + Unsicher-Dot (8px Teal-Outline-Kreis) erweitert, Event-Delegation Click-Handler fuer Inline-Korrektur (5 Buttons, POST /api/calls/<id>/correct_outcome, Row-Update bei Success). nerve.css: .n-outcome-reminder-stripe + .outcome-unsicher-dot + .outcome-correction-inline-row (alle Teal, KEIN #f59e0b/#fbbf24). 4 Runtime-Behavior-Tests. Foundation-Code-Register: 4 kanonische Phase-D-Eintraege (calls.outcome_confidence, calls.outcome_source, calls.outcome_note, calls.conversation_log_id) mit Downstream-Konsumenten Phase E/H/O. REQ-D-8 + REQ-D-9 + REQ-D-10 erfuellt. Checkpoint Task 7.5 approved. 5 Commits: e254525, b7e5ece, 1ca5448, e26f9d6, daa3e62. SUMMARY: 08.23.2.D-07-SUMMARY.md.

**Phase 08.23.2.D Plan 06 abgeschlossen:** pip-launcher.js: state.lastCallId aus api_beenden Response, outcome_ready Handler (dreistufige UX: ai_auto=Auto-Ring 30s, ai_auto_unsicher=Auto-Ring+Teal-Outline-Badge, NULL/low-conf=Korrektur-Modal 5 Buttons+Notiz-Textarea), audio_health_warning Handler (Pulse-Mic-Icon #f59e0b, 5s Auto-Hide), Reconnect-Fallback (GET /api/calls/latest_outcome bei socket connect), _submitOutcomeCorrection() (POST /api/calls/<id>/correct_outcome). nerve.css: .pip-outcome-confirm-ring (Teal), .pip-outcome-badge-unsicher (Teal-Outline, D-07c Override), .pip-outcome-correction-grid (2-col grid, 44px Touch-Target), .pip-audio-warn + @keyframes pip-audio-warn-pulse. D-08 Option a: Notiz-Textarea NUR im Korrektur-Modal. Visuell verifiziert (Task 6.3 approved). REQ-D-4 + REQ-D-5 + REQ-D-7 erfuellt. 2 Commits: c4a45b6, 80fe050. SUMMARY: 08.23.2.D-06-SUMMARY.md.

**Phase 08.23.2.D Plan 05 abgeschlossen:** api_postcall_analysis() erweitert: outcome_service.classify() NACH Sonnet-Block, Schwellenlogik (conf>=0.90->ai_auto, 0.70<=conf<0.90->ai_auto_unsicher, <0.70->NULL), UPDATE calls.outcome/outcome_confidence/outcome_source mit Ownership-Check (V4 ASVS), SocketIO emit('outcome_ready') NUR room-targeted via _session_state-SID-Lookup (KEIN broadcast — Multi-User-Privacy). Zwei neue Endpoints: GET /api/calls/latest_outcome (D-04e Fallback-Pull, Ownership) + POST /api/calls/<id>/correct_outcome (User-Korrektur, anonymize(cache=None), outcome_source='user_corrected'). 10 Runtime-Behavior-Tests (CLAUDE.md-konform). Deviations: separate DB-Sessions, str(uuid4()) SQLite-Compat, outcome_confidence-Persistierung auch bei niedrigem Confidence. 3 Commits: 3431d56, e506899, 5add8c2. SUMMARY: 08.23.2.D-05-SUMMARY.md.

**Phase 08.23.2.D Plan 04 abgeschlossen:** api_beenden() erweitert: UPDATE des bestehenden Early-Call-Records nach ConvLog-Save (REQ-D-2 — kein zweiter INSERT, SPEC-Override: create_call_for_sid() legt Early-Record bei Session-Start an). Felder: ended_at, conversation_log_id, call_mode (aus req_data D-05a). Background-Thread (daemon=True) startet VOR reset_session() mit Flask App-Context: liest word_confidences-Buffer (VOR reset_session() — Race-Condition-Sicherung), berechnet audio_health via outcome_service.calculate_audio_health(), schreibt audio_health_score + CallEvent(event_type='audio_health') (REQ-D-6). call_id im Response fuer Frontend-Fallback-Pull. 6 Runtime-Behavior-Tests (CLAUDE.md-konform, kein Source-Presence). Deviations: UUID-str()-Compat + explizite event_id fuer SQLite-BIGINT-NOT-NULL. 2 Commits: 10c3b3b, c7afd2b. SUMMARY: 08.23.2.D-04-SUMMARY.md.

**Phase 08.23.2.D Plan 03 abgeschlossen:** Word-Confidence-Buffer (D-06) vollstaendig implementiert. services/live_session.py: 'word_confidences': [] als Top-Level-Key + 'audio_warn_active': False als Sub-Key in state-Dict (REQ-D-7). services/deepgram_service.py: statistics-Import, _AUDIO_WARN_TRIGGER_BELOW=0.70 + _AUDIO_WARN_RESET_ABOVE=0.80 + _ROLLING_WINDOW_MS=10_000 Konstanten, _rolling_10s_score() Helper, Word-Confidence-Buffer-Schreibpfad bei is_final=True, Hysterese-Emit audio_health_warning (per-Socket, ausserhalb Lock, non-blocking). tests/test_word_confidence_buffer.py: 7 Unit-Tests (alle gruen). REQ-D-7 erfuellt. 3 Commits: 9bb676f, 0289f5a, 40faa5e. SUMMARY: 08.23.2.D-03-SUMMARY.md.

**Phase 08.23.2.D Plan 02 abgeschlossen:** TDD-implementiertes services/outcome_service.py mit classify() (Claude-Haiku Outcome-Klassifikation, crash-safe, 6 Enum-Werte + confidence 0.0-1.0, Edge-Cases: <30s/Exception/malformed-JSON/invalid-Enum) und calculate_audio_health() (5 deterministische Metriken: mean, median, pct_below_07, longest_uncertain_block_s, stddev + gewichteter Composite-Score 0.0-1.0). Pure-Logik-Service (D-01b/c) — kein Emit, kein DB-Write. TDD: RED 3ba6215 (10 Tests), GREEN 1df87fd. Deviation: MODEL_POSTCALL_HAIKU fehlt in config.py — Fallback auf MODEL_ANALYSE (bestehende Haiku-Konstante). REQ-D-3 + REQ-D-6 erfuellt. SUMMARY: 08.23.2.D-02-SUMMARY.md.

**Phase 08.23.2.D Plan 01 abgeschlossen:** Alembic-Migration 0005 addet 4 nullable Spalten zu calls (conversation_log_id FK, outcome_confidence, outcome_note, outcome_source + CHECK ck_calls_outcome_source). Call-ORM-Modell in database/models.py gespiegelt. Real-Daten-Validation-Test (CLAUDE.md Punkt 13): 4 Tests gruen — Spalten-Inspect, SELECT-Smoke, CHECK-Violation bei invalid_value, NULL+gueltige-Werte erlaubt. Deviation: Downgrade via Raw-SQL CREATE+COPY+DROP statt batch_alter_table (SQLite-Limitation: ORM-CHECK-Constraint kollidiert mit column-drop in temp-Tabelle). REQ-D-1 vollstaendig, REQ-D-2 FK-Prerequisite erfuellt. 3 Commits: f81e61c, eaa2d54, cf1aac0. SUMMARY: 08.23.2.D-01-SUMMARY.md.

**Phase 08.23.2.C.R.F Plan 03 abgeschlossen:** test_mode_switch_event.py vollstaendig ersetzt: 2 tautologische False-Green-Tests (manuelle CallEvent-Instanziierung) durch behavioral Handler-Tests. Handler-Extraktion via register_audio_handlers(mock_sio) mit Dict-Capture. test_mode_switch_payload_persisted_to_db: ruft echten Handler auf, assertiert db.add() mit event_type='mode_switch' + 4 Payload-Keys. test_call_id_none_means_skip_guard_fires: ruft Handler mit call_id=None, assertiert assert_not_called() (Skip-Guard real geprueft). 1 Commit: d8d5656. SUMMARY: 08.23.2.C.R.F-03-SUMMARY.md. Decisions: mock_sio.on-Dict-Capture fuer Closure-Extraktion; database.db.SessionLocal-Patch fuer lokalen Import-Intercept; try/finally fuer State-Cleanup.

**Phase 08.23.2.C.R.F Plan 02 abgeschlossen:** iOS-Style Toggle Switch fuer pip-mode-indicator: base.html inner structure (pip-toggle-track + pip-toggle-knob + pip-toggle-label Spans, kein Whitespace zwischen Elementen). nerve.css: Pill/Badge-Block ersetzt durch iOS-Toggle-CSS (28x16px Track, 10px Knob via translateX(12px), 3-State: gatekeeper/meeting/target). Token-Fix: --page-text-muted / --page-text-secondary (nicht --text-muted / --text-secondary). Meeting-Mode: Track display:none, Label in Brand-Teal. pip-launcher.js: querySelector('.pip-toggle-label') mit else-Fallback (T-RF-07). 2 Commits: 95757af, d805831. SUMMARY: 08.23.2.C.R.F-02-SUMMARY.md. Decisions: Meeting-mode kein binaerer Toggle; Token-Fix Cross-AI-Review MEDIUM; querySelector-Fallback fuer Null-Safety.

**Phase 08.23.2.C.R.F Plan 01 abgeschlossen:** Atomic TOCTOU-Safe Sentinel in create_call_for_sid() (live_session.py): Guard unter _session_state_lock verhindert Doppel-Records bei parallelen Reconnects. Sentinel-Cleanup im except-Block (T-RF-10). create_call_for_sid() Aufruf in handle_start_live_session() (deepgram_service.py): REQ-6 Production-Pfad gefixt — call_id ist jetzt nicht mehr immer None. contact_category_update Session-Init-Emit: liest aus session_state (nicht hardcoded). 2 Commits: 7f84317, df4fa7f. SUMMARY: 08.23.2.C.R.F-01-SUMMARY.md. Decisions: Sentinel '__call_pending__' unter _session_state_lock; externer Check ist Fast-Path-Optimierung; emit liest aus State.

**Phase 08.23.2.C.R Plan 07 abgeschlossen:** Test-Cleanup: test_gatekeeper_classifier.py + test_hysteresis.py geloescht. test_phase_classifier.py: apply_hysteresis Import + test_call_events_phase_change_persisted entfernt. test_session_state_phase_c.py: uwg_blocked-Test geloescht, contact_category/current_mode auf 'gatekeeper' korrigiert (REQ-5 Compliance). test_mode_initial_db.py erstellt: Behavioral-Test fuer mode_initial DB-INSERT (REQ-6 Nachweis) via database.db.SessionLocal Patch. nerve.css: UWG-Banner Kommentar-Residue bereinigt (REQ-2). Alle 8 SPEC.md Acceptance-Greps PASS. 493 Tests PASS, 17 pre-existing Failures unveraendert. 2 Commits: 3c3d118, f76840e. SUMMARY: 08.23.2.C.R-07-SUMMARY.md. Decisions: database.db.SessionLocal Patch-Strategie fuer lokalen Import.

**Phase 08.23.2.C.R Plan 06 abgeschlossen:** pip-launcher.js: uwg_hard_block Socket-Listener + _showUwgBanner() + _wireUwgBannerClose() + Ctrl+G/E keydown-Handler geloescht (REQ-2, REQ-3). 3 Hex-Werte durch CSS-Tokens ersetzt: color:#06060a->var(--btn-primary-text), #F8FAFC->var(--pip-bg), rgba(255,255,255,0.1);color:#c5c9d4->var(--badge-default-bg);var(--badge-default-text) (REQ-8). _updateContactCategory(): 'Vorzimmer'->'Sekretar', 'Cold-Call'->'Entscheider', aria-label dynamisch via setAttribute (REQ-9, D-03b). Klick-Handler auf #pip-mode-indicator mit 300ms Throttle + stopPropagation + manual_mode_toggle emit (REQ-4, D-03i). state.contactCategory als semantisch korrekter Category-Toggle-Key. 2 Commits: 059acc3, 807e4b4. SUMMARY: 08.23.2.C.R-06-SUMMARY.md. Decisions: state.contactCategory fuer Toggle-Check (nicht state.currentMode).

**Phase 08.23.2.C.R Plan 05 abgeschlossen:** nerve.css: 6 neue CSS-Tokens (pip-gatekeeper-bg/text/bg-hover, pip-bg, badge-default-bg/text) + --btn-primary-text auf #06060a aktualisiert. #pip-mode-indicator Button-Reset (border:none, color:inherit, appearance:none, min-height:32px, cursor:pointer). pip-uwg-banner CSS-Bloecke geloescht (REQ-2). pip-mode-indicator[gatekeeper] Token-Migration von pipeline-warning auf pip-gatekeeper (REQ-7). base.html: pip-uwg-banner div geloescht, span->button Migration fuer pip-mode-indicator mit data-mode=gatekeeper + Sekretar-Label + aria-label (REQ-4). 2 Commits: 68b709e, df25d48. SUMMARY: 08.23.2.C.R-05-SUMMARY.md. Decisions: --btn-primary-text Wert-Update #0D1117->#06060a, aria-label zeigt Ziel-Modus (D-03b).

**Phase 08.23.2.C.R Plan 04 abgeschlossen:** mode_switch-INSERT mit Skip-Guard in manual_mode_toggle (deepgram_service.py) + mode_initial-INSERT in create_call_for_sid() (live_session.py) — REQ-6 vollstaendig. Skip-Guard: call_id=None -> log + skip (D-04a). mode_initial nach call_id-Write, cid lokal (Pitfall 2). call_id=cid (UUID-String, nicht int — Plan-Annahme Integer war falsch). Non-fatal Exception-Handling in beiden INSERTs. 2 Commits: 2dd791a, fe91d91. SUMMARY: 08.23.2.C.R-04-SUMMARY.md. Decisions: UUID FK (nicht Integer), Skip-Guard korrekt, Whitelist-Security intakt.

**Phase 08.23.2.C.R Plan 03 abgeschlossen:** claude_service.py classify_contact + apply_hysteresis Block (Z.1080-1183, 104 Zeilen) geloescht — REQ-1 vollstaendig (beide Service-Dateien sauber). live_session.py init_session_state(): contact_category='gatekeeper', current_mode='gatekeeper', uwg_blocked Key entfernt — REQ-5 abgeschlossen. Control-Flow-Audit fand zweiten uwg_blocked-Guard in claude_service.py Z.870 (auto-geloescht). test_live_session_gatekeeper.py: Tests auf korrekte init_session_state()-Signatur fixiert, 3 Tests GRUEN. 2 Commits: 007f414, d0dbe55. SUMMARY: 08.23.2.C.R-03-SUMMARY.md. Decisions: REQ-1 abgeschlossen (zweiter Fundort laut RESEARCH.md Pitfall 6), Default gatekeeper nach DSGVO Single-Speaker-Constraint.

**Phase 08.23.2.C.R Plan 02 abgeschlossen:** gatekeeper.py auf Single-Function-Stub reduziert (245→17 Zeilen): 6 Auto-Erkennungs-Funktionen + alle Dead Imports geloescht, populate_context_notes() Foundation-Stub unveraendert beibehalten. deepgram_service.py: UWG-Guard (Z.47-49) + Trigger-Phrasen-Detection Block (Req-7) + UWG-Hard-Block-Detection Block (Req-8) geloescht (79 Zeilen). 0 Treffer fuer uwg/detect_trigger_phrases/classify_contact nach Prune. manual_mode_toggle Handler intakt. 2 Commits: 41015f3, f67c52d. SUMMARY: 08.23.2.C.R-02-SUMMARY.md. Decisions: gatekeeper.py bleibt als Datei (D-02a), Dead-Code-Prune nach DSGVO Single-Speaker-Constraint.

**Phase 08.23.2.C.R Plan 01 abgeschlossen:** Alembic Migration 0004 mit batch_alter_table (SQLite-safe) erweitert call_events CHECK-Constraint um mode_switch + mode_initial. Chain 0001->0002->0003->0004 (head). alembic upgrade head Exit-Code 0. Deviation: Migration 0003 hatte pre-existing Bug (op.execute ALTER TABLE ADD CONSTRAINT auf SQLite ungueltig) — per batch_alter_table + idempotente add_column via sa_inspect repariert. Test-Scaffolds: tests/test_live_session_gatekeeper.py (3 Tests, RED), tests/test_mode_switch_event.py (2 Tests, 2 PASSED). 3 Commits: 901fee8, b5cf5c6, 33f75ae. SUMMARY: 08.23.2.C.R-01-SUMMARY.md.

**BLOCKER: Phase 08.23.2.C.1 Plan 05 — Checkpoint FAILED (2026-05-20):** Live-Test auf staging.getnerve.app deckte fundamentalen Architektur-Fehler auf. NERVE Cold-Call ist Single-Speaker (DSGVO-Pflicht) — Klassifikator kann Sekretar nicht hoeren, daher Auto-Erkennung in den ersten 5 Sekunden konzeptuell unmoeglich. Trigger-Phrasen-Erkennung greift nie (Sekretar-Audio nie bei NERVE). Zusaetzlich: 3x Plan-07-Drift (hardcoded Farbe im Vorzimmer-Indikator, Tastaturkuerzel-UX unzugaenglich im Cold-Call, fehlender Default-Modus-Indikator) + Plan-09-Drift (Phrasen-Qualitaet nie gegen echte Sekretar-Interaktionen validiert). CLAUDE.md Punkt 11 Modul-Rewrite-Trigger erfuellt (3+ Pflaster + Architektur-Drift). Req-9 OFFEN → deferred zu Phase 08.23.2.C.R. Req-11 (CSRF) BESTANDEN (682d7f6). Phase 08.23.2.C wird NICHT auf Production deployed. SUMMARY: 08.23.2.C.1-05-SUMMARY.md.

**Phase 08.23.2.C.1 Plan 05 — Task 1 abgeschlossen:** DSGVO Analyse.md §8.3 Staging-Datenstrategie eingefuegt (Vault-Datei, nicht Git-tracked): PFLICHT-TRIGGER erster externer User dokumentiert, refresh_staging_from_production.sh-Verweis, Anonymisierungs-Pflichtfelder. CSRF-Patch Z.54-58 verifiziert: 4 WTF_CSRF_ENABLED-Zeilen, git diff aae9aa8 = 0 Aenderungen (Req-11 bestanden). Commit: 682d7f6.

**Phase 08.23.2.C.1 Plan 04 abgeschlossen:** render_as_batch=True in alembic/env.py (REVIEW-MEDIUM-5): context.configure() in run_migrations_online() + run_migrations_offline() — verhindert NotImplementedError bei SQLite ALTER TABLE. Alembic-Auto-Hook in app.py (REVIEW-MEDIUM-4): Python API (AlembicConfig + alembic_command.upgrade) statt subprocess, CWD-unabhaengiger alembic.ini-Pfad via os.path.abspath(__file__), SQLite-only-Check, Postgres-Skip-Log. CSRF-Patch Z.54-58 unveraendert (git diff bestaetigt). 2 Commits: d130e3d, 74bc286.

**Phase 08.23.2.C.1 Plan 03 abgeschlossen:** DB-Sync-Skripte erstellt. scripts/reset_sequences.py: eigenstaendiges Python-Skript (67 Zeilen), verbindet via DATABASE_URL, setzt alle Postgres-Sequences auf GREATEST(MAX(id),1) via PL/pgSQL-DO-Block, idempotent, [DB]-Log-Ausgabe. scripts/refresh_staging_from_production.sh: Bash-Skript mit set -eo pipefail (REVIEW-HIGH-3 Fix), Dump in RAM-Variable + DUMP_SIZE-Check (< 1024 Bytes = ABORT), Bestaetigungs-Prompt [y/N], Pre-Refresh-Backup auf Staging via SSH, SSH-Pipe Production→Staging ohne lokalen Dump (DSGVO-Hygiene), Aufruf reset_sequences.py nach Import. STAGING_IP als Env-Var oder Platzhalter fuer nach Hetzner-Provisionierung. 2 Commits: 20cbac6, 80a22ff.

**Phase 08.23.2.C.1 Plan 02 abgeschlossen:** deploy.sh auf TARGET=staging|production refactored. TARGET-Pflicht-Parameter (kein Default, kein versehentlicher Prod-Deploy). Production Pre-Deploy-Gate: 3 Checks (status==ok, deployed_at <24h, git_head==LOCAL_HEAD) via jq. Staging-Branch: VPS_HOST=root@<STAGING_IP>, SSH_KEY=~/.ssh/nerve_staging, SERVICE_NAME=nerve-staging. /etc/nerve/.env-Check fuer beide Targets. Service-Unit-scp TARGET-spezifisch ohne 2>/dev/null || true. nginx-Config per scp (nginx-staging.conf / nginx-production.conf). REVIEW-HIGH-2 Fix: .deploy_meta Zeile 182 VOR systemctl restart Zeile 187. api_health() gibt git_head + deployed_at zurueck (liest /opt/nerve/.deploy_meta). .env.staging.example committed. 2 Commits: 9ea3047, 108a88a.

**Phase 08.23.2.C.1 Plan 01 abgeschlossen:** Staging-Artefakte erstellt. scripts/setup_staging.sh: idempotentes Bash-Skript fuer Hetzner CX32 (10 apt-Pakete inkl. jq+apache2-utils, nerve_app System-User, /opt/nerve/-Verzeichnisstruktur inkl. backups/pre-refresh, nerve+nerve_test Postgres-DBs mit psql -tAc Guard). deploy/nerve-staging.service: systemd Unit fuer Staging-Gunicorn (nerve-staging, EnvironmentFile=/etc/nerve/.env). deploy/nginx-staging.conf: HTTP-Basic-Auth Server-Ebene + REVIEW-HIGH-1 Fix (auth_basic off fuer /api/health + /socket.io/) + robots.txt Disallow:/. deploy/nginx-production.conf: statische Datei fuer Plan 02 scp (getnerve.app + www-Redirect, kein auth_basic). RUNBOOK-staging.md: 9-Schritt-Checkliste fuer manuellen Erst-Setup. 2 Commits: 0dde184, 6ada4be.

**Phase 08.23.2.C Plan 08 abgeschlossen:** Test-Suite Phase-Gate. 5 Test-Dateien: tests/test_hysteresis.py (8 Tests, Req-3), tests/test_phase_classifier.py (5+1 Tests, Req-2/4/12, F1-Gate mit 10% Noise FALSIFIZIERBAR, f1>=0.75 && f1<=0.95 Sanity-Cap), tests/test_gatekeeper_classifier.py (12+1 Tests, Req-5/7/8/13, skipif gatekeeper_classifier_corpus.json fehlt), tests/test_anonymization_reid.py (1 Test, Req-14, skipif kein API-Key/GLiNER), tests/test_session_state_phase_c.py (8 Tests, Req-11, Pitfall-3+6). 4 Commits: f371f26, eaaee92, 5708155, c3e21dc. Deviations: init_session_state braucht user_id+org_id, UWG-Phrasen angepasst an tatsaechliche Pattern-Abdeckung, Patch-Target ist claude_client nicht _call_haiku. Pre-existing Failures: MODEL_PIP_AUTOVAR, test_anonymization_perf State-Pollution, test_ewb_pipeline, test_exchange_rates, test_profile_schema_v3, test_qa_pipeline_rueckfrage — alle out-of-scope. Phase-Gate bereit sobald gatekeeper_classifier_corpus.json von Andre erstellt wird.

**Phase 08.23.2.C Plan 07 abgeschlossen:** PiP-UI Gatekeeper-Modus. routes/app_routes.py: GET /api/gatekeeper/phrases (filtert mode='gatekeeper', Template-Var-Ersetzung, @login_required). services/deepgram_service.py: manual_mode_toggle Socket-Handler in register_audio_handlers() (Whitelist target|gatekeeper, setzt contact_category + current_mode + Hysterese-Reset, emittet contact_category_update + manual_mode_toggle_ack). static/nerve.css: .pip-uwg-banner, .pip-mode-indicator, .pip-ewb-btn[data-mode-button="gatekeeper"] — alle var(--...) Tokens, 0 Hex. templates/base.html: pip-uwg-banner + pip-mode-indicator DOM eingefuegt. static/pip-launcher.js: Ctrl+G/E Keydown-Handler, _renderGatekeeperButtons() via /api/gatekeeper/phrases, _showUwgBanner(), _wireUwgBannerClose(), Socket-Subscriptions. 3 Commits: 51f83ab, 54dcc7d, 05ba9ef. Task 4 (Live-PiP-Test) deferred — lokale Umgebung (Asset-Loading + Server-Crash) nicht nutzbar; Verifikation auf Production nach Code-Review + Deploy.

**Phase 08.23.2.C Plan 06b abgeschlossen:** Migration 0003 Gatekeeper Seed-Insert. alembic/versions/0003_add_phrases_mode.py: op.bulk_insert mit 10 Gatekeeper-Phrasen (D-05: >=2 Varianten pro 4 Buttons). Button 1 gatekeeper_verbuendeten_bitte: 3 Varianten (Stephan Heinrich + Ulrike Knauer). Button 2 gatekeeper_insider_antwort: 3 Varianten (Tim Taxis + Eduard Klein). Button 3 gatekeeper_voss_label: 2 Varianten (Chris Voss). Button 4 gatekeeper_vornamen_pause: 2 Varianten (Martin Limbeck). Alle Rows: user_id=1 (Admin-MVP), mode='gatekeeper', quality_tier='A'. Texte 1:1 aus Andre-Gate-genehmigter tests/fixtures/gatekeeper_phrases_seed.md. downgrade() loescht Seeds vor drop_column. py_compile OK, Varianten-Verifikation gruen. 1 Commit: 4fb6267.

**Phase 08.23.2.C Plan 06 abgeschlossen:** Gatekeeper-Core-Service-Implementation. services/gatekeeper.py: classify_contact (UNION/CONSENSUS-Voting Review Finding 4), _names_match (RapidFuzz fuzzy threshold=80, Deviation: 85 wuerde Meier/Meyer verfehlen), detect_trigger_phrases, detect_uwg_hard_block, apply_hysteresis (3-Bedingungen: Hints+Dwell+Transitions), populate_context_notes (Foundation-Stub). services/live_session.py: 9 Phase-C-Keys in init_session_state() (contact_category, current_mode, context_notes, phase_hint_count, pending_phase, phase_entered_at, call_id, uwg_blocked=False), create_call_for_sid() Helper. services/claude_service.py: UWG-Guard, classify_contact-Wiring, apply_hysteresis+phase_change-CallEvent-Persist, Socket-Events. services/deepgram_service.py: UWG-Guard, detect_trigger_phrases+trigger_phrase_hint-Emit, detect_uwg_hard_block+uwg_blocked=True+uwg_hard_block-Emit. config/__init__.py: Deviation Rule 3 — re-exportiert config.py-Konstanten (repariert 21 pre-existing Testfehler). 3 Commits: 3e01035, 2169854, 3b56814.

**Phase 08.23.2.C Plan 05 abgeschlossen:** Modus-spezifischer Phasen-Klassifikator (Req-2) + Trigger-Phrasen-Data-Layer (Req-7+Req-8). claude_service.py: _PHASE_NAMES_COLD_CALL (6 Phasen), _PHASE_NAMES_MEETING (6 Phasen), _PHASE_NAMES_GATEKEEPER (4 Phasen), _PHASE_NAMES_BY_MODE Hilfs-Mapping. classify_phase() waehlt phase_names + max_phase per mode-Parameter, Range-Validation 1..max_phase (gatekeeper max=4 enforced, T-08.23.2.C-15 mitigiert). PHASE_CLASSIFIER_PROMPT mit {labels}+{mode} Platzhalter. _PHASE_NAMES Backward-Compat-Alias erhalten fuer Analyse-Loop Z.970/974/983/984. ki_logik.py: TRIGGER_PHRASES (18 Eintraege, 14 Brush-Off + 4 UWG), UWG_HARD_BLOCK_PATTERNS (4 Opt-Out-Regex), _phrase_matches() Wrapper. 2 Commits: e751373, bf1b11c.

**Phase 08.23.2.C Plan 04 abgeschlossen:** GLiNER als zweite NER-Stufe in services/anonymization.py (Union-Voting D-01). _get_gliner(): thread-safe lazy load (Double-Checked Locking, analog _get_nlp), is_pipeline_healthy=False bei Load-Fehler. _apply_ner(): Union-Voting spaCy+GLiNER, native Offsets + re.finditer-Fallback (Review Finding 1). _apply_ner_parallel(): ThreadPoolExecutor concurrent dispatch bereit (Review Finding 2, Latenz-Mitigation). extract_entities(text, cache=None): oeffentliche Funktion fuer gatekeeper.py-Konsens-Voting (D-02). app.py: _get_gliner()-Warmup nach anonymize('Warmup', None) im Pre-Warm-Block. Phase-B-Performance-Gate: 3/3 Tests gruen (0.24s). 3 Commits: f20ca9b, 703b206, d43686c.

**Phase 08.23.2.C Plan 03 abgeschlossen:** Konfigurations-Foundation fuer Hysterese-Logik (Req-3) und Foundation-Code-Register (Req-11). config/__init__.py + config/phase_transitions.py: MIN_PHASE_DURATIONS (3 Modi, D-03-Werte 1:1), ALLOWED_TRANSITIONS, FORBIDDEN_TRANSITIONS, MODE_TRANSITION_AUTO, HYSTERESIS_REQUIRED_HINTS=2. scripts/calibrate_phase_durations.py: Read-only Diagnose-Skript, graceful exit ohne Korpus. .planning/04 Entscheidungen/Foundation-Code-Register.md: populate_context_notes-Stub + context_notes-State-Feld fuer Phase 08.23.2.I. 3 Commits: 9718df8, 1445ef6, b40a418.

**Phase 08.23.2.C Plan 02 abgeschlossen:** Alembic Migration 0003 fuer phrases.mode (VARCHAR(20) NOT NULL DEFAULT 'cold_call') + CHECK-Constraint ck_phrases_mode (cold_call|gatekeeper|meeting). database/models.py: Phrase-Klasse um mode-Column erweitert. alembic history zeigt korrekte Chain 0001->0002->0003 (head). DB-Live-Verifikation deferred auf Server (SQLite local). Req-10 erfuellt. 2 Commits: e8717e0, 182f097.

**Phase 08.23.2.C Plan 01 abgeschlossen:** GLiNER-Foundation Wave 1. gliner>=0.2.24 in requirements.txt. deploy.sh: GLiNER-Pre-Cache-Block (nicht-fatal). scripts/gliner_smoke.py: Latenz-Diagnose + Return-Format-Dump (klaert Open Question 1). scripts/verify_corpus_gate.py: Pre-Execute-Gate (Exit 1 solange Korpora fehlen). tests/fixtures/*_corpus.schema.json: JSON-Schemas fuer beide Korpora (minItems=20/10). tests/fixtures/gatekeeper_phrases_seed.md: 4 Mr.-Miyagi-Buttons (3+3+2+2 Varianten) aus Vault B.6/B.7/Bonus-Block — Andre-Gate abgeschlossen (Resume-Signal "phrase-seed edits done"). 4 Commits: 93a5921, 979c814, 865853a, 2f07f2a.

**Phase 08.23.2.B Plan 10 abgeschlossen:** Security-Test (Req-11) und Performance-Test (Req-12) fuer services/anonymization.py. tests/test_anonymization_security.py: 50 repraesentative deutsche B2B-Mitschrift-Snippets, Re-ID-Test via Claude-Haiku, @pytest.mark.skipif(not ANTHROPIC_API_KEY) CI-Guard, test_snippets_count() ohne API-Key. tests/test_anonymization_perf.py: P95-Latenz-Test auf 1000-Zeichen-Text (100 Runs, frischer Cache), Short-Snippet-Test (<100ms P95), Art-9-Short-Circuit-Diagnose. Checkpoint approved von Andre. 2 Commits: 1248aed, 4ea6120. PHASE 08.23.2.B VOLLSTAENDIG — alle Req-1 bis Req-12 abgedeckt.

**Phase 08.23.2.B Plan 09 abgeschlossen:** Verdrahtungs-Integration-Tests fuer Req-7/8/9 + Fallback A/B/C. 14 pytest-Tests in tests/test_anonymization_wiring.py: INPUT-Pfad (IBAN, Art-9, E-Mail), OUTPUT-Pfad (Briefing-Namen in Claude-Output, Einwand-Zitat, Painpoint, EWB-Antwort), Fallback Kat. A (AnonymizationPipelineUnavailable), Kat. C (degraded via ROLLING_ERROR_THRESHOLD), Lifecycle-Chain (init_anonymisierer -> get_anonymisierer -> pop -> None), Ghost-SID-Guard. autouse Fixture reset_pipeline_health (T-08.23.2.B-TW-01/02). Anpassung: get_pipeline_status() gibt dict zurueck — Tests nutzen result['status']. Kein Source-Presence-Test. 1 Commit: 1fe7f7f.

**Phase 08.23.2.B Plan 08 abgeschlossen:** Unit-Test-Suite fuer services/anonymization.py (Req-1 bis Req-6). 22 Runtime-Behavior-Tests: AnrufAnonymisierer (Token-Format, Stabilitaet, Cross-Session, Thread-Safety), Regex-PII (IBAN, Email, Multiple), Art-9-Filter (Hit/No-Hit, Tuple-Return, 6 Kategorien), anonymize_output() (Reverse-Lookup, Longer-Key-First, None-Cache), register_briefing_pii() (Person, Firma, Empty), Pipeline-Unavailable-Exception, Empty-Text-Edge-Case, Art-9-False-Negative-Gate (30 Snippets x 6 Kategorien, 100%). Rule-1-Auto-Fix: KeyError in get_or_assign_token fuer Regex-PII-Typen (setdefault statt direktem dict-Zugriff). autouse-Fixture fuer Modul-State-Reset (is_pipeline_healthy + _error_timestamps) — notwendig da spaCy lokal nicht installiert. 2 Commits: a275a9c, 5bdf335.

**Phase 08.23.2.B Plan 07.1 abgeschlossen:** Dashboard-Banner fuer Anonymisierungs-Pipeline-Fehler (D-08 Kat. A + C). _record_snippet_error() als neue Funktion in anonymization.py (Z.368) — registriert Snippet-Fehler-Timestamps thread-safe fuer Rolling-Error-Banner-Zaehler; Aufruf in allen 3 anonymize()-Exception-Pfaden. get_pipeline_status() von str auf dict erweitert: {'status': str, 'error_count_10min': int}. /api/health gibt jetzt pipeline_error_count_10min zurueck (routes/app_routes.py Z.1430). CSS: --pipeline-error-bg/text + --pipeline-warning-bg/text Tokens in :root; .n-pipeline-error (rot) + .n-pipeline-warning (gelb) Klassen ohne Hex im Body. dashboard.html: 2 neue Streifen-Divs + JS-Erweiterung im bestehenden health-fetch IIFE. 4 Commits: dcc32de, 9ef1e08, 7455c39, 1ca1a17.

**Phase 08.23.2.B Plan 07 abgeschlossen:** Anonymisierungs-Verdrahtung in app_routes.py an zwei Stellen. /api/session-rating (Z.901-929): anonymize(comment, None) vor latest.kommentar DB-Write; cache=None (Token-Cache nach Session-Ende geloescht, Pitfall 4); Finding 4: [ART9_REDACTED] und [ANON_FEHLER] -> leerer Kommentar (kein Literal in DB); Pipeline-Unavailable: Fail-safe leerer Kommentar; Fail-open fuer unerwartete Exceptions. /api/health (Z.1415-1426): pipeline_status='ok'|'degraded'|'unavailable' aus get_pipeline_status(). get_pipeline_status() in services/anonymization.py (Z.365): liest _error_timestamps Thread-safe — Kat. A = unavailable, Kat. C = degraded, sonst ok. 2 Commits: 7003079, e084686.

**Phase 08.23.2.B Plan 06 abgeschlossen:** OUTPUT-PFAD anonymize_output() in claude_service.py an zwei Stellen verdrahtet. gegenargument_log (Z.882): anonymize_output() fuer einwand_zitat, gegenargument_1, gegenargument_2 — AUSSERHALB gegenargument_log_lock (kein Lock-Nesting, T-CS-04). einwand_typ unveraendert (Typ-Label, T-CS-03). painpoints + conversation_log[type=painpoint] (Z.1453): anonymize_output() fuer _painpoint_anon (ls.painpoints) und _painpoint_log_anon (conversation_log) — Duplikat-Check auf Original-Text (korrekt, vor Anonymisierung). Fail-open Fallback bei Exception. Finding 4 bestaetigt: anonymize_output() gibt keine Sentinel-Werte — kein Skip-Check noetig. 2 Commits: 4d6f601, 398183e.

**Phase 08.23.2.B Plan 05 abgeschlossen:** Deepgram-Anonymisierungs-Verdrahtung — anonymize() und anonymize_output() in deepgram_service.py verdrahtet. INPUT-PFAD (Z.77-106): anonymize(text, cache) vor conversation_log.append(); Art-9-Skip ([ART9_REDACTED]), ANON_FEHLER-Skip (Finding 4), AnonymizationPipelineUnavailable-Handler (D-08 Kat. A). OUTPUT-PFAD (Z.591-602): anonymize_output(_antwort, cache) vor record_ewb_click(); einwand_text=typ unveraendert (Typ-Label, kein Freitext). Ghost-SID Race-Condition via get_anonymisierer()-None-Return abgefangen. Beide Sentinel-Werte explizit abgefangen — kein DB-Spam (Finding 4). 2 Commits: d52673b, f392c94.

**Phase 08.23.2.B Plan 04 abgeschlossen:** AnrufAnonymisierer-Lifecycle in live_session.py verdrahtet. init_anonymisierer(sid): erstellt AnrufAnonymisierer-Instanz per SID mit Ghost-SID Guard und Lazy-Import (verhindert Circular-Import). get_anonymisierer(sid): thread-sicherer Accessor gibt Instanz oder None zurueck. 'anonymisierer': None als neuer Key in init_session_state() (Z.386). pop_session_state() loescht 'anonymisierer' automatisch via dict.pop(). Lifecycle-Test gruen: init -> get(None) -> init_anonymisierer -> get(Instanz) -> pop -> get(None). Ghost-SID-Test gruen. DB-Grep: 0 Treffer (Cache nie in DB). 1 Commit: ac5c09a.

**Phase 08.23.2.B Plan 03 abgeschlossen:** Alembic-Migration 0002 fuer Phrase.quality_tier (VARCHAR(1) NOT NULL DEFAULT 'A') erstellt. Revision-Chain 0001->0002 korrekt. database/models.py: quality_tier = Column(String(1), nullable=False, server_default='A') nach created_at eingefuegt. scripts/delete_pretest_data.py: D-07 Cutover-Skript mit pg_dump-Backup, --dry-run + --backup-only Flags, interaktiver DELETE-Bestaetigung, FK-Reihenfolge ueber 6 Tabellen, Sequence-Reset, audit_log AUSGENOMMEN. Checkpoint approved von Andre. 2 Commits: 8154496, dd7b5ce.

**Phase 08.23.2.B Plan 02 abgeschlossen:** Deployment-Dependencies fuer spaCy-Anonymisierung: spacy>=3.7.0 und phonenumbers>=8.13.0 in requirements.txt. deploy.sh: de_core_news_lg Download nach pip install (Z.82). Finding-2-Fix: nerve.service (--worker-class gthread --workers 1 --threads 4) per scp+daemon-reload deployed — OOM-Schutz auf CX22 (1 Worker x 700MB = 700MB statt N x 700MB). Szenario B: gthread war bereits in nerve.service vorkonfiguriert; Deviation Rule 2: Service-Datei-Installations-Schritt ergaenzt da deploy/ aus TAR_EXCLUDES. 2 Commits: 879cc90, b0d9b2d.

**Phase 08.23.2.B Plan 01 abgeschlossen:** DSGVO-Anonymisierungs-Foundation-Modul erstellt (Greenfield). services/art9_keywords.py: ART9_KEYWORDS Dict mit 6 Kategorien, 198 Keywords, BayLDA-auditierbar. services/anonymization.py: AnrufAnonymisierer-Klasse (Thread-safe Token-Cache), anonymize() 3-stufige Pipeline (Art-9 -> Regex -> spaCy NER), anonymize_output(), register_briefing_pii(), should_persist(), AnonymizationPipelineUnavailable, is_pipeline_healthy. D-05 Tuple-Kontrakt implementiert: bei Art-9-Treffer ('[ART9_REDACTED]', 'C'). Finding 1 Fix: ART9_KEYWORDS als Modul-Level-Import. Finding 4 Fix: should_persist() exportiert. Finding 5 Fix: Pre-Warm anonymize('Warmup', None) in app.py Zeile 2273. 3 Commits: 6876fc6, b448c0c, 28100cd.

**Phase 08.23.2.A Plan 07 abgeschlossen:** Postgres 16 Server-Setup Runbook erstellt und Hetzner-Setup durch Andre ausgefuehrt. docs/postgres-server-setup.md: 9-Sektionen (SQLite-Backup, Postgres-Install, nerve+nerve_test DBs mit de_DE.UTF-8, nerve_app restricted user, pg_hba.conf peer-auth, TCP disabled via listen_addresses='', Linux-User-Setup, Connection-Verify, Dry-Run-Prozedur). Checkpoint "server-setup-complete" bestaetigt: Postgres 16 laeuft, beide DBs existieren, nerve_app verbindet per unix socket, SQLite-Backup auf Laptop. DATABASE_URL noch auf SQLite (aendert sich erst Plan 09). 2 Commits: b723d3d, 17d1ddf. Decisions: DATABASE_URL deferred to Plan 09 cutover (C-5), TRUNCATE via postgres superuser (C-3), ALTER DEFAULT PRIVILEGES fuer kuenftige Phasen.

**Phase 08.23.2.A Plan 06 abgeschlossen:** Alembic Baseline Migration 0001 erstellt. Postgres nicht verfuegbar (psql not found) — manuelle Erstellung per Plan-Fallback. 35 Tabellen (33 Legacy + calls + call_events). CHECK-Constraints via op.execute() fuer calls (call_mode, transcript_storage, outcome) und call_events (event_type). GIN-Index auf call_events.payload. idx_calls_mode_outcome mit postgresql_where. revision='0001', down_revision=None. ft_call_sessions/ft_assistant_events korrekt ausgeschlossen. Muss nach Postgres-Installation verifiziert/regeneriert werden. 1 Commit: 9e9b745. Decision: Manuelle Erstellung weil Postgres 16 noch nicht installiert.

**Phase 08.23.2.A Plan 05 abgeschlossen:** Migration scripts erstellt. validate_postgres_migration.py: 33-table MIGRATE_TABLES, validate_row_count() + validate_sample_rows() als importierbare Funktionen, Standalone __main__ Runner. migrate_to_postgres.py: 33 Tabellen in FK-Dependency-Order, BATCH_SIZE=500, circular FK two-pass (organisations.coach_id + users.active_profile_id), inline Validierung nach jeder Tabelle, DRY_RUN=1 Mode. DRY_RUN gegen lokale SQLite verifiziert (alle 33 Tabellen gelesen). Deviation: Plan sagte 32 Tabellen, models.py hat 33 (crm_notes fehlte in Plan-Count). 2 Commits: 94f618d, a48ecb1.

**Phase 08.23.2.A Plan 04 abgeschlossen:** Routes + tests vollständig von FtCallSession/FtAssistantEvent bereinigt. FtCallSession update block (lines 364-386) aus app_routes.py gelöscht (D-08). 3 FT-Test-Dateien via git rm gelöscht: test_ft_lifecycle.py, test_ft_models.py, test_ft_write_hooks.py (D-10). test_per_sid_migration.py: nur test_write_ft_event_isolation_per_sid chirurgisch gelöscht, 5 DSGVO-kritische Isolation-Tests intakt (D-11). test_ab_stats.py: FtCallSession aus Import entfernt. test_ft_seed.py: keine FT-Refs, unverändert. REQ-4 grep check: 0 Treffer. 2 Commits: 8fd95b5, 533b32c. Deferred: JSONB/SQLite-Inkompatibilität in db_session-Fixture (pre-existing, seit Plan 01/02).

**Phase 08.23.2.A Plan 03 abgeschlossen:** FT dead-code prune in services — FtCallSession writer block deleted from deepgram_service.py (37 lines), _write_ft_assistant_event function + 2 call sites deleted from claude_service.py (188 lines), scripts/export_ft_jsonl.py git-removed. Zero FtCallSession/FtAssistantEvent references remain in services/. 2 Commits: c965dc0, e4fc949. Decisions: D-06 FtCallSession ersatzlos geloescht, D-07 FtAssistantEvent ersatzlos geloescht, D-09 export_ft_jsonl.py git-removed, user_id-Zuweisung behalten (Phase 08.19.4 braucht sie).

**Phase 08.23.2.A Plan 02 abgeschlossen:** Alembic tooling initialized — alembic>=1.13.0 + psycopg2-binary>=2.9.9 in requirements.txt. alembic.ini with DATABASE_URL env-var. alembic/env.py imports database.models (side-effect), target_metadata=Base.metadata, compare_type=True. alembic/versions/.gitkeep tracked. 2 Commits: 6cec015, 4f236d6. Decisions: D-01 DATABASE_URL from os.environ (never hardcoded), D-02 compare_type=True, D-03 psycopg2-binary only.

**Phase 08.19.5.6.2 Plan 01 abgeschlossen:** 3-Button-Modus-Wahl (A/B/C) in Step 4 zu 1-Button lnr-step4-confirm konsolidiert. state.briefingModus vollstaendig aus pip-launcher.js entfernt (0 Treffer). PiP-Tab-Gate von briefingModus==='B' auf precallBriefing.firmenname umgestellt. Toter briefingModus-Kommentar in test_08_20_3.py entfernt. 28 Tests gruen. 4 Commits: d118a4f, df11b67, c3122be, fc9fe08. Decisions: D-01 lnr-step4-confirm ID, D-02 direkte ta.value-Zuweisung, D-03 Kommentar bereinigt.

**Phase 08.19.5.6.1 Plan 02 abgeschlossen:** R-01 + R-04 in pip-launcher.js — _initTeleprompter() Block-Sequenz [openerText?, erlaubnisText?, skriptOrPitchBlocks?]: erlaubnisText aus selectedErlaubnisId via openerItems(type='erlaubnis'), hasOpener/hasErlaubnis Guard ersetzt fruehen Return, blocks via .concat().concat(). _savePersonalizedAndStartCall(): startCall(true) durch fetch(/api/launcher/profile/{id})+renderStep5() ersetzt, is_personalized Filter, Null-Guard mit _showToast, .catch() ruft renderStep5(). Rule-1-Fix: falsche saveBtn-ID entfernt. 2 Commits: 895b5ee, e1e80b0.

**Phase 08.19.5.6.1 Plan 01 abgeschlossen:** R-02/R-03/R-05 in renderStep5() — Null-Optionen ("— kein Opener —" / "— keine Erlaubnisfrage —" / "— keinen Pitch —" / "— kein Skript —") mit value="" in allen 4 Dropdowns. IIFE Preview-Trigger nach innerHTML-Assign: zeigt items[0].inhalt kursiv wenn selId null (state bleibt unverändert per D-03). Hint-Box permanent über Tab-Nav: Reihenfolge (Opener→Erlaubnisfrage→Pitch/Skript) + Skript-Priorität + Null-Option-Erklärung. nerve.css: .launcher-hint-box + .launcher-hint-icon mit ausschließlich var(--...) Tokens. 2 Commits: 234843d, eaa42c3.

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
- [Phase 08.23.2.D.UX.0-01]: CREATE ROLE nerve_anon_worker als Runbook-Step ausserhalb Alembic (Passwort darf nicht in VCS — CLAUDE.md HART Secrets-Regel, D-01)
- [Phase 08.23.2.D.UX.0-01]: alembic upgrade head fuer 0008 muss als postgres-User laufen (nerve_app hat kein CREATE SCHEMA-Recht — korrekt/sicher)
- [Phase 08.23.2.D.UX.0-01]: isinstance(recipients, str)-Normalisierung in _send() schliesst bare-String-Bypass (G-1); ohne diese Zeile iteriert any() ueber Einzelzeichen
- [Phase 08.23.2.D.UX.0-01]: D-07 Finding: nerve_app kein Superuser, postgres Owner von training — GRANT-Isolation D-06 ist aktiv und greift; kein Erzwingungsbedarf diese Phase
- [Phase 08.23.2.D.UX.0-01]: D.UX.1-Migration muss Nummer 0009 verwenden; training.transcript_segments-GRANT gehoert in 0009 (Pitfall 7 eingehalten)
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
| 20260523-cr1 | 08.23.2.C.R.1: cold_call-Phrases Re-Seed — Alembic Migration 0005, 18 Phrasen in 8 objection_types | 2026-05-23 | 6092d3f | [20260523-cr1-cold-call-phrases-reseed](./quick/20260523-cr1-cold-call-phrases-reseed/) |

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

Last session: 2026-05-29T09:32:20.226Z
Stopped at: Phase 08.23.2.D.UX.0 context gathered
Resume file: .planning/phases/08.23.2.D.UX.0-test-user-pattern-drei-schichten-backup-foundation/08.23.2.D.UX.0-CONTEXT.md
