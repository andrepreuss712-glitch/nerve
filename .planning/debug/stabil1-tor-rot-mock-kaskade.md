---
status: fix-applied-awaiting-gate
trigger: "STABIL-1-Tor rot: 21 failed + 58 errors nach claude_client->http_llm_client Rename; Produktionscode gesund (Claudian verifiziert). Universeller Fix: Test-Mock-Helfer retargeten."
created: 2026-07-24
updated: 2026-07-24
---

## Resolution (Fix angewandt 2026-07-24, Verifikation am Tor durch Claudian ausstehend)

Universeller Fix auf 13 Test-Dateien angewandt (nur `tests/`, 46 Insertions, 0 Deletions, KEIN
Produktionscode). Commits `dbf87d5` (Pattern A) + `f851cb6` (Pattern B).

- **Pattern A (MagicMock):** 28 Stellen `<mock>.with_options.return_value = <mock>` in
  test_outcome_service (7), test_08_20_3 (3), test_precall_schema (1), test_adoption_runner (4),
  test_qa_pipeline (4), test_phase_classifier (4), test_heiler_resolved (1),
  test_ewb_autovar_global_regression (1), test_judge_runner (3, via ALSO-CHECK gefunden).
- **Pattern B (_FakeClient-Klassen):** `def with_options(self,*a,**k): return self` in
  test_medium_lane_intent_event_live, test_qa_pipeline_rueckfrage (2 Klassen),
  test_anon_live_vs_stored, test_08_5_05_training_pipeline_t2 (2 Klassen).
- `test_stabil1_http_llm_timeout.py` unberührt (war bereits korrekt = Vorbild).

AST-Parse aller 13 Dateien grün (Vorabsignal). **HART: kein lokales pytest gelaufen.**
Verbindliches Tor = `deploy.sh production` (Claudian). Bei Rest-Rot → hier reopnen.

## Runde 2 (Tor #3, 2026-07-24): Retarget wirkte 21→5. Rest = EINE Datei

`5 failed, 1011 passed, 58 errors`. Fable-verifizierter Retarget-Fix (870a80e) + meine 13-Datei-
Version haben die Mock-Kaskade behoben. Der GESAMTE Rest kommt aus `tests/test_stabil1_beenden_guard.py`
(mein Guard-Test) — er ist selbst der Poisoner. Zwei Test-Defekte, KEIN Produktionsdefekt (Guard
`_bs is None and not _posted_call_id` @app_routes.py:206 korrekt, Claudian am Code verifiziert):

1. **Baseline-Wilderei:** Test operiert auf geschützten Base-Rows User id=1 / Org id=1. Der volle
   Beenden-Pfad (fair-use/Punkte-Block :614-647 mutiert users[1] + organisations[1].live_minutes_used)
   → `_baseline_cleanup_guard` failt im Teardown (mutated=[1]) → 58 Kaskaden-ERRORS. `_UserCounterSnapshot`
   ist zu fragil (deckt nicht alle mutierten Spalten). **Fix: eigene Wegwerf-User UND -Org (Fixture),
   nie auf id=1 schreiben; alles via cleanup_rows wegräumen.**
2. **Session-Leak:** `test_beenden_ohne_session_ist_noop` postet ohne call_id, erwartet no_session —
   aber `_load_beenden_state` fand eine GELEAKTE Session (Modul-globaler `ls._session_state`, Stufe-2-
   Scan per user_id) → `_bs` nicht None → Guard feuert NICHT → voller Pfad. **Fix: vor dem POST
   Session-Maps für den Test-User leeren / sicherstellen dass keine Session existiert.** (Wegwerf-User-ID
   entkoppelt zusätzlich vom geleakten user_id=1.)
3. Fallback-Tests brauchen eigene `calls`-Rows unter Wegwerf-User (sonst verschmutzen fremde offene
   Calls auf user_id=1 die Eindeutigkeits-Prüfung → Positiv-Fallback-Test schlägt fehl).

Korrektur an Runde-1-Doku: die „conftest.py:642 json.dumps"-Ursache war falsch (0 json.dumps;
echter Kaskaden-Mech = mutated-Baseline, nicht json).

5 betroffene Tests: test_beenden_ohne_session_ist_noop, test_geposteter_call_id_umgeht_den_guard,
test_fallback_nimmt_eindeutigen_frischen_call, test_fallback_raet_nicht_bei_zwei_offenen_calls,
test_fallback_ignoriert_veralteten_call.

### Runde-2-Fix angewandt (2026-07-24, Commit 8e15302)

`tests/test_stabil1_beenden_guard.py` komplett neu (nur diese Datei, +214/-210, AST grün). Muster
`tests/test_logs_org_boundary.py` (throwaway Org+User via ORM+flush) + `test_postcall_outcome_route.py`
(cleanup_rows-Stil).
- **`throwaway`-Fixture:** Organisation(plan='starter') → `db.add`+`flush()` (feuert trg_mk_tenant_org →
  tenant_orgs auto) → User darunter → commit. Client als dieser User authentifiziert. Tracker-Dict
  (user_id/org_id/call_ids/conv_ids). **Nie id=1.**
- **Teardown (reverse-FK via cleanup_rows):** audit_log (manuell, target_type-gefiltert) → EIN
  cleanup_rows-Aufruf {Call, ConversationLog, User, tenant_orgs, Organisation} (Savepoint-Retry löst
  FK-Zyklen selbst).
- **Session-Isolation:** `_clear_leaked_sessions_for_user()` popt vor dem No-Op-POST alle
  `ls._session_state`-Einträge des Test-Users (unter Lock). Verifiziert: `_session_state` ist die
  einzige Stufe-2-Scan-Quelle + einziges Modul-Global (Punkt 28) — keine Sibling-Maps.
- `_UserCounterSnapshot` entfernt (überflüssig — Mutationen treffen nur Wegwerf-Rows, die weg müssen).
- Alle 7 Tests behalten Intent+Assertions, nur auf Wegwerf-User/-Org umgezogen.

**Offen für Claudian am Tor (Flags):** (1) kein RLS-GUC für die Wegwerf-Org gesetzt — alle berührten
Tabellen sind public.* (kein RLS), konsistent mit test_logs_org_boundary; falls eine dieser Tabellen je
RLS bekommt, hier nachziehen. (2) Fallback-Eindeutigkeit (Tests 5-7) hängt daran, dass der Wegwerf-User
0 Fremd-Calls hat — pro Test frische User-ID, daher kollisionsfrei auch unter xdist (nicht lokal
verifizierbar). HART: kein lokales pytest gelaufen — AST-Vorabsignal grün.

status → fix-applied-awaiting-gate (Runde 2). Bei Rest-Rot hier reopnen.

## Current Focus
- hypothesis: Baseline-sicherer + session-isolierter Guard-Test behebt 5 FAILED + 58 ERRORS ohne Produktionscode
- next_action: ANHALTEN — Claudian fährt das Tor. Bei Rest-Rot Session reopnen.

# Debug: STABIL-1 Tor ROT — Test-Kaskade nach claude_client → http_llm_client Rename

## Root Cause (Claudian-diagnostiziert, DIALOG-GSD-CLAUDIAN.md Commit 8f8a2cb)

Plan 01 hat 15 HTTP-Call-Sites von `claude_client.messages.create(...)` auf
`http_llm_client().messages.create(...)` umgestellt. `http_llm_client()` gibt
`claude_client.with_options(timeout, max_retries)` zurück. Jeder Test, der `claude_client`
durch ein MagicMock ersetzt, bekommt aus `mock.with_options(...)` ein **frisches,
unkonfiguriertes** MagicMock → `.messages.create()` liefert ein nacktes MagicMock statt der
konfigurierten Antwort → (a) 21 FAILED Assertions; (b) nacktes MagicMock fließt in DB-/Cost-Log-
Write → `_baseline_cleanup_guard` (conftest.py:642 json.dumps) verschluckt sich → Wächter
vergiftet → 58 ERRORs kaskadieren über fremde Tests. **Produktionscode gesund — reine Test-
Contract-Breakage. Kein Code-Rückbau.**

## Universeller Fix (mechanisch, sicher, idempotent)

- **MagicMock-Mock-Helfer:** `<mock>.with_options.return_value = <mock>` an der Mock-Config-Stelle.
- **`_FakeClient`-Custom-Klassen:** Methode `def with_options(self, *a, **k): return self`.

Angewandt auf ALLE `claude_client`-Mock-Helfer (14 Test-Dateien; `test_stabil1_http_llm_timeout.py`
ist bereits korrekt = Vorbild). HART: kein lokales pytest — GSD editiert, Claudian fährt das Tor.

## Current Focus
- hypothesis: Universeller Mock-Retarget behebt FAILED + ERRORs ohne Produktionscode-Änderung
- next_action: Fix auf alle claude_client-Mock-Helfer anwenden, committen, ANHALTEN (Claudian testet)
