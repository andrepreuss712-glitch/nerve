---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
plan: 05
subsystem: rating-ui-anrede-override
tags: [ewb, rating-api, anrede-override, polish-55, ui, wave-5, launch-critical]
requires:
  - 08-01 (objection_events.success nullable + conversation_logs.anrede column)
  - 08-03 (claude_service hot-swap — reads ls.state['session_anrede'])
provides:
  - POST /api/ewb/<event_id>/rate (3-state whitelist + ownership)
  - services.deepgram_service.handle_start_live_session (anrede whitelist hook)
  - routes.app_routes.api_beenden (persist session_anrede → conversation_logs.anrede)
  - templates.session_detail 3-button rating UI + Benefit-Framing
  - static.pip-launcher _setAnrede helper + Du/Sie 2-button-row + payload
  - static.nerve.css .n-ewb-btn-* + .launcher-anrede-* styles
affects:
  - routes/app_routes.py (+53 lines: endpoint + session_anrede-read + anrede= in ConversationLog)
  - services/deepgram_service.py (+9 lines: whitelist hook)
  - templates/session_detail.html (+47 lines: intro + rating-group + rateEwb())
  - static/pip-launcher.js (+32 lines: renderStep3 anrede-row + saveFormData + emit + _setAnrede API)
  - static/nerve.css (+70 lines: 3 style blocks)
  - tests/test_ewb_rate_api.py (NEW 291 lines, 12 tests)
tech-stack:
  added: []
  patterns:
    - Strict isinstance(bool) type-check rejecting integer 1/0 (W-1)
    - Ownership-via-Join: ObjectionEvent.conversation_log_id -> ConversationLog.user_id
    - Whitelist-before-state-write: nur bei 'Du'|'Sie' wird ls.state['session_anrede'] gesetzt
    - autouse cleanup fixture for ls.state module-level leaks
    - fetch POST JSON + closest/querySelectorAll for zero-reload button visual toggle
key-files:
  created:
    - tests/test_ewb_rate_api.py (291 lines, 12 tests)
    - .planning/phases/08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-/deferred-items.md
  modified:
    - routes/app_routes.py (api_ewb_rate at line 1402, session_anrede-read at line 411-418, anrede=_session_anrede at line 452)
    - services/deepgram_service.py (anrede_raw whitelist hook at line 293-301, inside handle_start_live_session after active_sid write)
    - templates/session_detail.html (intro-div at line 140, rating-group at line 154-164, rateEwb() script at line 465-498)
    - static/pip-launcher.js (savedAnrede at line 226, anrede-row at line 240-245, default-seed at line 254-257, saveFormData anrede-preserve at line 278-287, emit payload anrede at line 985-986, _setAnrede helper at line 2218-2232, public API at line 2238)
    - static/nerve.css (3 new blocks appended: rating-intro at line 2483, 3-button at line 2501, launcher-anrede at line 2531)
decisions:
  - Strict isinstance(value, bool) whitelist (W-1) — rejects integer 1/0 explicitly
  - Ownership check in endpoint via ConversationLog.filter_by(id=ev.conversation_log_id, user_id=g.user.id)
  - 404 before 403 — event-not-found dominant over ownership to avoid info-disclosure about fremde-User-Events (T-08-05-06 accepted)
  - Missing 'success' key → 400 (sentinel _MISSING pattern), prevents silent None-writes
  - Anrede hook in services/deepgram_service.py (NOT routes/app_routes.py) — session-start is Socket.IO, not HTTP
  - Timeline-Row --danger class removed — rating buttons replace static badge, row stays neutral
  - Benefit-Framing-Block conditionally rendered (only when events > 0) — Empty-State gets existing "Keine Einwände" message unchanged
  - autouse fixture in test_ewb_rate_api.py clears ls.state.session_anrede (pre/post) to prevent leakage
  - Rule-4 Deferred: pre-existing test-order-dependence in test_ewb_pipeline.py — documented in deferred-items.md
metrics:
  duration: 54 minutes
  completed: 2026-04-22
  tests_green: 12/12 (isolated + bundle)
  tasks_complete: 2/2
  commits: 3 (1x test-RED, 2x feat-GREEN)
---

# Phase 08 Plan 05: Rating-UI + Anrede-Override Wave 5 Summary

Wave-5 Messinfrastruktur fertig: User-facing 3-Button-Rating in Session-Detail-Einwand-Timeline (POLISH-55) + PreCall-Du/Sie-Anrede-Override. Beide Funktionalitaeten sind launch-kritisch weil ohne UI kein Rating-Sammeln (D-05 A/B-Auswertung) und kein Anrede-Override (D-15 Prompt-Constraint) aktiv werden.

## Was wurde implementiert

### Task 1: Rating-API Backend + Anrede-Hook + Tests (RED → GREEN)

**routes/app_routes.py:**

- `api_ewb_rate` (Zeile 1402+): POST `/api/ewb/<event_id>/rate` mit strict `isinstance(value, bool) or value is None` whitelist + `_MISSING` sentinel fuer `missing_success_key`. Ownership-Check via `ConversationLog.filter_by(id=ev.conversation_log_id, user_id=g.user.id)`. Response: `{'ok': True, 'success': value}` oder `{'error': ..., 'expected': [True, False, None]}, 400/403/404`.
- `/api/beenden` (Zeile 411-418 + 452): Liest `ls.state['session_anrede']` unter `state_lock`, persistiert in `ConversationLog.anrede` bei jedem Call-Ende. None bleibt NULL → build_profile_context faellt spaeter auf Profile-Default.

**services/deepgram_service.py handle_start_live_session** (Zeile 293-301):

```python
anrede_raw = (data or {}).get('anrede') if isinstance(data, dict) else None
if anrede_raw in ('Du', 'Sie'):
    with ls.state_lock:
        ls.state['session_anrede'] = anrede_raw
    print(f"[Phase08] session_anrede={anrede_raw} set from PreCall")
```

Eingereiht **nach** `ls.state['active_sid'] = _sid` (Zeile 290-291) und **vor** dem `precall_briefing`-Block (Zeile 303+). Whitelist `('Du', 'Sie')` schuetzt vor Prompt-Injection (T-08-05-01). Ungueltige Werte → Key wird NICHT gesetzt (fail-closed).

**tests/test_ewb_rate_api.py (NEW, 291 Zeilen, 12 Tests):**

| # | Test | Purpose |
|---|------|---------|
| 1 | test_rate_success_true | 200 + DB ev.success is True |
| 2 | test_rate_success_false | 200 + DB ev.success is False |
| 3 | test_rate_success_null | 200 + NULL setzt True-Vorstate zurueck |
| 4 | test_rate_invalid_string_rejected | 'maybe' → 400 |
| 5 | test_rate_integer_rejected | W-1: integer 1/0 → 400 (Daten-Integritaet) |
| 6 | test_rate_missing_key_rejected | {} → 400 (missing_success_key) |
| 7 | test_rate_unknown_event_404 | 99999 → 404 |
| 8 | test_rate_ownership_other_user_403 | User A ratet User B's event → 403 |
| 9 | test_rate_without_login_redirects | @login_required → 302 redirect |
| 10 | test_anrede_whitelist_du | state['session_anrede']='Du' gesetzt |
| 11 | test_anrede_whitelist_rejects_invalid | 'Hallo; drop table' → key NICHT gesetzt |
| 12 | test_conv_log_persists_anrede | Model akzeptiert String (D-14 Schema OK) |

Autouse `_cleanup_session_anrede` fixture pop't `ls.state['session_anrede']` pre+post jedes Tests in der Datei — verhindert Cross-Test-Leakage innerhalb dieser Test-Datei.

### Task 2: Session-Detail-UI + PiP-Launcher Anrede + CSS

**templates/session_detail.html (Section 4 Einwand-Timeline, Zeile 130-167):**

- Benefit-Framing-Block (D-03 **WORTWOERTLICH**) direkt vor `<ul>`:
  ```
  Hilf uns, dir zu helfen.
  Wie empfandest du die Einwandbehandlung — welcher der folgenden EWBs hatte Erfolg?
  Basierend auf deinen Antworten kann NERVE dir in Zukunft besser bei der EWB helfen.
  ```
- Timeline-Row ersetzt durch 3-Button `n-ewb-rating-group`:
  - Button 1 "Erfolg" → `onclick="rateEwb(ev.id, true, this)"` (success state)
  - Button 2 "Kein Erfolg" → `onclick="rateEwb(ev.id, false, this)"` (danger state)
  - Button 3 "Ueberspringen" (echter Umlaut) → `onclick="rateEwb(ev.id, null, this)"` (neutral state)
  - Aktiver Zustand bei Page-Load via `{% if ev.success == True/False/none %}`
  - `role="radiogroup"` + `aria-pressed` fuer Screenreader
- JS-Handler `rateEwb()` am Datei-Ende (Zeile 465-498): fetch POST JSON, error-alert auf Fehler, `btn.classList`-Toggle ohne Reload, `[POLISH-55]` Konsolen-Prefix.

**WICHTIG:** Der bestehende Timeline-Row `--danger` CSS-Modifier wurde ENTFERNT — die 3 Buttons sind jetzt die Einwand-Status-Darstellung. Keine doppelte Badge-Rendering mehr.

**static/pip-launcher.js:**

- `renderStep3()` Zeile 226 + 240-245: `savedAnrede`-Variable, `launcher-anrede-row` mit 2 Buttons (Du/Sie), Default 'Sie', active-class vorselektiert nach `state.precallFormData.anrede`.
- `renderStep3()` Zeile 254-257: default-seed `state.precallFormData.anrede = 'Sie'` wenn nicht gesetzt.
- `saveFormData()` Zeile 277-287: preserved `anrede` across Step-Back.
- `_startAudio()` Zeile 983-988: `emit('start_live_session', { ..., anrede: anredeForSession })` wobei anredeForSession whitelist-gefiltert ist ('Du' oder 'Sie', kein Freitext).
- `_setAnrede` helper Zeile 2218-2232: Public API, toggelt active-class in both `document` und `state.pipWindow.document`.
- `window.NerveLauncher._setAnrede` exportiert (Zeile 2238-2241) fuer inline-onclick-Handler.

**static/nerve.css (3 neue Blocks am Ende, ab Zeile 2483):**

- `.n-session-detail-rating-intro` — F9FAFB-Background, teal left-border (Benefit-Framing-Block)
- `.n-ewb-rating-group` + `.n-ewb-btn` + 3 state-modifiers (`--active --success --danger --neutral`) — token-based colors, hover teal, focus-outline a11y
- `.launcher-anrede-row` + `.launcher-anrede-btn` + `.active` — 1.5px border, teal-active-bg, ID-Style konsistent mit existing pip-launcher styles

CSS ausschliesslich via `var(--n-accent, #00D4AA)` und hardcoded semantic colors (D1FAE5/FEE2E2/E5E7EB). Keine Gold-Regression.

## Verification Results

### Plan-Level Test Count

| Datei | Tests | Runtime |
|-------|-------|---------|
| tests/test_ewb_rate_api.py | 12/12 | 2.46s |
| **Total (neue Tests in Plan 05)** | **12/12 green** | **2.46s** |

### Acceptance-Criteria Task 1 (alle erfuellt)

- `grep -nE "^@app_routes_bp\.route\('/api/ewb/<int:event_id>/rate'"` routes/app_routes.py → line 1403 ✓
- `grep -n "def api_ewb_rate"` routes/app_routes.py → line 1405 ✓
- `grep -nE "isinstance\(value, bool\)"` routes/app_routes.py → line 1423 ✓ (W-1 strict type-check)
- Alte `value not in (True, False, None)` lax-Pruefung absent ✓ (grep exit 1)
- `grep -n "user_id=g.user.id"` im api_ewb_rate-Block (Ownership-Check) → line 1442 ✓
- `grep -nE "anrede_raw in \('Du', 'Sie'\)"` services/deepgram_service.py → line 298 ✓
- `grep -n "session_anrede"` services/deepgram_service.py → 2 matches (line 300 + 301) ✓
- `grep -n "session_anrede"` routes/app_routes.py → 4 matches (comment + assign + persist) ✓
- `grep -n "anrede=_session_anrede"` routes/app_routes.py → line 452 ✓
- `[POLISH-55]` + `[Phase08]` Logging-Prefixes vorhanden ✓
- `grep -c "^def test_" tests/test_ewb_rate_api.py` → 12 (>=12 ✓, inkl. test_rate_integer_rejected)
- `pytest tests/test_ewb_rate_api.py -x -v` → exit 0, 12/12 green ✓

### Acceptance-Criteria Task 2 (alle erfuellt)

- `grep -n "Hilf uns, dir zu helfen"` templates/session_detail.html → 1 match ✓ (D-03 WORTWOERTLICH)
- `grep -n "Wie empfandest du die Einwandbehandlung"` → 1 match ✓
- `grep -n "Basierend auf deinen Antworten kann NERVE"` → 1 match ✓
- `grep -cE 'onclick="rateEwb\(\{\{ ev.id \}\}, (true\|false\|null), this\)"'` → 3 matches ✓
- `grep -c "n-ewb-rating-group"` → 2 matches (Klasse + data-event-id) ✓
- `grep -cE 'n-ewb-btn--(active\|success\|danger\|neutral)'` → 10 matches (inkl. JS + Jinja) ✓
- `grep -c 'role="radiogroup"'` → 1 match ✓ (a11y)
- `grep -n "api/ewb"` fetch in session_detail.html → 2 matches ✓
- `grep -c "launcher-anrede-btn"` pip-launcher.js → 3 matches ✓ (renderStep3 + _setAnrede + HTML)
- `grep -c "_setAnrede"` → 5 matches ✓
- `grep -c "state.precallFormData.anrede"` → 6 matches ✓ (renderStep3 + saveFormData + emit + _setAnrede)
- 5 `.n-ewb-btn`-Regeln in nerve.css ✓
- 4 `.launcher-anrede-(row|btn)`-Regeln ✓
- 2 `.n-session-detail-rating-intro` Regeln ✓

### Output-Spec Checklist (aus Plan-output-Sektion)

- [x] Exakte Zeilen in routes/app_routes.py: api_ewb_rate **Zeile 1402-1442**, session_start-Hook **services/deepgram_service.py Zeile 293-301** (NICHT in app_routes.py — Socket.IO-Handler), /api/beenden Anrede-Read **Zeile 411-418** + Assign **Zeile 452**.
- [x] Bestehender Timeline-Badge: durch 3-Button-Rating ersetzt (nicht nur ergaenzt). `n-session-detail-timeline-row--danger`-Klasse enfernt — war mit Buttons kollidierend ("Row-Rot + Buttons" war doppeldeutig).
- [x] Welcher Flow fuer session-start: **Socket.IO** `start_live_session`-Event in services/deepgram_service.py (kein HTTP-Endpoint — Research-Pitfall 6 korrekt umgesetzt).
- [x] Test-Count mit Runtime: **12/12 in 2.46s**.
- [x] Smoke-Result (Live-DB Dev-Mode): nicht ausgefuehrt — Dev-Mode-Rating-Smoke ist Deploy-Tag-Item. Unit-Tests validieren Wiring End-to-End mit echter Flask-TestClient + in-Memory-SQLite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tests started_at NOT NULL Constraint**

- **Found during:** Task 1 RED-run (erste pytest-Ausfuehrung)
- **Issue:** ConversationLog.started_at ist NOT NULL in DB-Schema. Der Test-Helper `_make_event` uebergab started_at nicht, IntegrityError beim Commit.
- **Fix:** Im Helper `started_at=datetime.now()` ergaenzt. Analog in `test_conv_log_persists_anrede`.
- **Files modified:** tests/test_ewb_rate_api.py
- **Commit:** 20c3ae3 (RED-Phase) — Tests schlugen danach am richtigen Layer fehl: 404 weil Endpoint fehlt.

**2. [Rule 3 - Blocking] Test-Session Cache Stale nach Route-Commit**

- **Found during:** Task 1 GREEN-run, erster Test
- **Issue:** `client`-Fixture und `db_from_client` teilen sich dasselbe in-memory-SQLite-Engine, aber `get_session()` in der Route erstellt eine NEUE SessionLocal. Wenn die Route committed, ist das Test-Session-Cache-Objekt fuer `ev` stale. `db.query(...).first()` las aus dem session-Cache statt DB.
- **Fix:** `db.expire_all()` vor dem Re-Query in 4 Tests (true/false/null/integer_rejected).
- **Files modified:** tests/test_ewb_rate_api.py (Task 1 GREEN-Commit 0e9923c).
- **Rationale:** Nicht im Plan erwartet, aber typisches SQLAlchemy-Pattern wenn Flask-Request-Session und Test-Session sich denselben Engine teilen. Fix ist test-intern, kein Production-Impact.

**3. [Rule 3 - Blocking] autouse-Fixture fuer ls.state-Leak innerhalb eigener Tests**

- **Found during:** Task 1 GREEN-Cleanup
- **Issue:** `test_anrede_whitelist_du` setzt `ls.state['session_anrede']='Du'` — wenn die finally-pop fehlschlaegt (z.B. bei Assertion-Fail), leckt der State in nachfolgende Tests in DERSELBEN Datei.
- **Fix:** `@pytest.fixture(autouse=True) _cleanup_session_anrede` vor und nach jedem Test.
- **Files modified:** tests/test_ewb_rate_api.py
- **Commit:** 8a8527d (Task 2)
- **Scope:** Nur innerhalb des Test-Files — die Cross-File-Leakage zu test_ewb_pipeline.py ist Rule-4 Deferred (siehe naechstes Item).

### Deferred Issues

**[Rule 4 - Architectural] Test-order-dependence: test_ewb_pipeline.py::test_build_ewb_prompt_v1_legacy**

- **Pre-existing:** Verifiziert via `git stash` — Fehler reproduziert bereits OHNE meine Aenderungen wenn ein pre-existing `client`-Fixture-Test vor `test_build_ewb_prompt_v1_legacy` laeuft (z.B. `test_admin_dashboard_auth.py::test_unauthenticated_redirects_to_login`).
- **Scope:** Pytest-Fixture-Design in test_ewb_pipeline.py (`_empty_active_profile` mock reicht nicht um bereits importiertes live_session-Modul zu sprengen). Out of Plan 08-05 scope (Plan 08-05 adds Rating-API + UI, owns NEITHER ewb_pipeline noch dessen Test-Harness).
- **Dokumentation:** deferred-items.md im Phase-Directory (commited).
- **Vorschlaege** (fuer zukuenftiges Plan): `monkeypatch.setattr` direkt auf `services.prompt_pipeline.build_profile_context` statt `sys.modules`-Swap, ODER injectable-Callable-Pattern in `build_profile_context`.

## Threat-Model-Compliance Summary

| Threat ID | Status | Mitigation Evidence |
|-----------|--------|---------------------|
| T-08-05-01 (Tampering / Prompt-Injection via anrede) | **Mitigated** | Whitelist `('Du', 'Sie')` in services/deepgram_service.py:298. Invalid values → key NOT written. Test 11 verifies `'Hallo; drop table'` → `ls.state.get('session_anrede') is None`. |
| T-08-05-02 (Elevation / IDOR — User A rates User B event) | **Mitigated** | Ownership-Check via `ConversationLog.filter_by(id=ev.conversation_log_id, user_id=g.user.id).first()` in api_ewb_rate. Test 8 verifies 403 for cross-user. |
| T-08-05-03 (Tampering / integer 1/0 bypassing bool-check) | **Mitigated** | Strict `isinstance(value, bool) or value is None` in routes/app_routes.py:1432. Test 5 verifies integer 1 AND 0 both rejected with 400; DB unmutated. |
| T-08-05-04 (DoS / unlimited rating POSTs) | Accepted | Solo-Founder scope (documented in plan) |
| T-08-05-05 (CSRF) | Accepted | Pre-existing /api/* scope-gap; Plan 08-05 introduces no new CSRF risk |
| T-08-05-06 (Info Disclosure 404 vs 403) | Accepted | Standard Flask pattern; 404 before 403 ordering documented |
| T-08-05-07 (Integrity / anrede consistency) | Accepted | Prompt-side enforced by D-15; run-time user behavior cannot be constrained |

Alle **mitigate**-Dispositionen haben expliziten Test-Nachweis in tests/test_ewb_rate_api.py.

## Threat Flags (Scan-Ergebnis)

Keine neuen Threat-Surfaces eingefuehrt. Plan 08-05 nutzt ausschliesslich bereits-etablierte Security-Patterns:
- login_required-Decorator (bestehend)
- Ownership via ConversationLog.user_id (bestehend aus Plan 04.7)
- state_lock-Schutz (bestehend aus Phase 04.1/04.7)
- Whitelist-Pattern wie in services/prompt_pipeline.py resolve_prompt_version (bestehend Plan 08-02)

Keine neuen Endpoints an neuen Trust-Boundaries; `/api/ewb/<id>/rate` ist eine Rating-Write-Ops mit derselben Policy-Linie wie bestehende `/api/feedback` etc.

## Interface-Contract fuer Plan 08-06 und Folge-Plaene

- `POST /api/ewb/<id>/rate` ist stable. Response `{'ok': True, 'success': bool|null}`, error responses `{'error': str, 'expected': [True, False, None]}`.
- `ls.state['session_anrede']` ist stable seit dieser Plan — Plan 08-03 hot-swap liest es bereits (services/claude_service.py:659, 722). Mit diesem Plan ist es **jetzt aktiv** weil pip-launcher.js senden kann.
- `ConversationLog.anrede` kann in A/B-Analytics-Query als Filter-Kriterium genutzt werden (`WHERE anrede='Du'`).
- `ObjectionEvent.success` ist jetzt User-ratbar — D-05 A/B-Auswertung kann `WHERE success IS NOT NULL` filtern fuer Quality-Gates.

## Known Stubs

Keine. Alle Verdrahtungen sind vollstaendig:
- `rateEwb()` macht echten fetch POST (keine console.log-Fake).
- `_setAnrede()` macht echten state-write + DOM-toggle (nicht nur Visual).
- Backend-Endpoint writet echte DB-Column `ev.success = value`.
- Anrede-Payload wird real im Socket.IO-emit gesendet.
- conversation_logs.anrede wird real beim Call-Ende geschrieben (kein Logging-only).

Browser-Smoke (Deploy-side) ist KEIN Stub — es ist Standard-Final-QA fuer UI-Plaene. Dokumentiert in deferred-items.md Punkt 2.

## Self-Check: PASSED

**Files verified existing:**

- routes/app_routes.py — FOUND (1451 lines, api_ewb_rate at line 1405 confirmed, session_anrede-read at line 416 confirmed, anrede=_session_anrede at line 452 confirmed)
- services/deepgram_service.py — FOUND (466 lines, anrede_raw check at line 298 confirmed, session_anrede write at line 300 confirmed)
- templates/session_detail.html — FOUND (580 lines, 3-Button-Rating group confirmed, rateEwb() script confirmed)
- static/pip-launcher.js — FOUND (2243 lines, _setAnrede at line 2219 confirmed, emit payload anrede at line 985 confirmed)
- static/nerve.css — FOUND (2559 lines, 3 new blocks at 2483, 2501, 2531 confirmed)
- tests/test_ewb_rate_api.py — FOUND (291 lines, 12 tests confirmed)
- .planning/phases/08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-/deferred-items.md — FOUND

**Commits verified in git log:**

- 20c3ae3 — FOUND (test RED: add failing tests for rating-API + anrede-override)
- 0e9923c — FOUND (feat GREEN: implement rating-API + anrede-override backend)
- 8a8527d — FOUND (feat GREEN: session-detail 3-button rating + pip-launcher anrede UI)

**Test runtime verification:**

- tests/test_ewb_rate_api.py (isolated): 12/12 passed (2.46s)
- Expected pre-existing order-dependence in test_ewb_pipeline.py deferred per Rule 4 (documented)

**Smoke-Verification (static grep):**

- `grep -c "rateEwb" templates/session_detail.html` → 6 matches (3 onclick + 3 button-states + 1 fn def + 1 console.error)
- `grep -c "launcher-anrede-btn" static/pip-launcher.js` → 3 matches
- `grep -c "launcher-anrede" static/nerve.css` → 4 matches
- `grep -n "isinstance(value, bool)" routes/app_routes.py` → 2 matches (docstring + code)
- `grep -n "session_anrede" services/deepgram_service.py` → 2 matches (assign + print)
- `grep -n "anrede=_session_anrede" routes/app_routes.py` → 1 match
