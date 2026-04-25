---
audit: deep-dive-tests
welle: 5
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault)
scope:
  - 36 test-Dateien (tests/*.py + tests/services/*.py)
  - 5063 Zeilen Test-Code gesamt
  - Abgleich gegen MASTER-AUDIT LB-1..LB-8 + H-1..H-15
input:
  - .planning/audits/MASTER-AUDIT.md
  - Codebase-Stichproben services/ + routes/
---

# Deep-Dive: Test-Suite

**TL;DR — Konfidenz HIGH:**
- 36 Test-Dateien, **0 skipped, 0 xfail**. Aber: die "grüne" Suite schützt Launch NICHT.
- **~45-55 Tests (≈20% der Test-Count)** sind **False-Greens** — prüfen Source-Presence via `inspect.getsource`, `hasattr`, Import-Existenz, Substring-Matches, anstatt Integration.
- **Kein einziger Test** für die 4 Launch-Blocker mit fehlender Route/Funktion (LB-1 Password-Reset, LB-2 DSGVO-Routen, H-1 finetune_logging, LB-7 Traceback-Leak).
- **Alle Launch-Blocker-Fehler wurden von False-Green-Tests gedeckt** — die Tests bestätigen, dass Funktionen existieren/aufgerufen werden. Sie bestätigen nicht, dass die Aufrufe mit sinnvollen Parametern erfolgen.
- Test-Daten sauber: Alles `sqlite:///:memory:` — kein Live-DB-Leak.

---

## 1. Test-Datei-Inventar

| Datei | Zeilen | Modul getestet | Stil | False-Green? |
|---|---:|---|---|---|
| `conftest.py` | 97 | Fixtures (db_session, client, db_from_client) | Infra | — |
| `test_08_5_03_integration.py` | 221 | claude_service._qa_pipeline_dispatch + einwand_keyword_matcher | Unit+Mock | Teilweise |
| `test_08_5_05_training_pipeline_t1.py` | 152 | training_service._load_training_prompt_template | **Source-Presence+Unit** | JA (Test 8 nur `inspect.getsource`) |
| `test_08_5_05_training_pipeline_t2.py` | 231 | training_service.generate_response* | **Source-Presence** + 2 Mocked-Calls | **JA (11/14 `inspect.getsource`)** |
| `test_ab_stats.py` | 276 | EwbRating Model, _seed_ewb_scenarios, A/B-SQL-Join | Integration (DB) | Nein |
| `test_admin_dashboard_auth.py` | 61 | routes/admin_dashboard Auth-Gate | Integration (Flask+DB) | Nein |
| `test_admin_ewb_datetime.py` | 57 | routes/admin_ewb._to_datetime | Unit | Nein |
| `test_auth_next_redirect.py` | 188 | routes/auth.safe_next + login-flow | Integration (Flask+DB) | Nein |
| `test_branche_migration.py` | 132 | scripts/migrate_branche_to_enum | Unit (pure) | Nein |
| `test_claude_service_phase08.py` | 105 | claude_service.analysiere_mit_claude* | **Source-Presence (inspect.getsource)** | **JA (7/7 Tests)** |
| `test_cost_tracker.py` | 81 | cost_tracker.log_api_cost | Integration (DB) | Nein |
| `test_einwand_keyword_matcher.py` | 449 | einwand_keyword_matcher | Unit (pure) | Nein |
| `test_eur_calculator.py` | 136 | eur_calculator.compute_eur | Integration (DB) | Nein |
| `test_eur_pdf.py` | 12 | WeasyPrint-Smoke | Smoke | Nein (importorskip) |
| `test_ewb_pipeline.py` | 153 | ewb_pipeline.build_ewb_prompt + _seed_ewb_v2 | Integration (DB) | Nein |
| `test_ewb_rate_api.py` | 346 | /api/ewb/<id>/rate Ownership-Whitelist | Integration (Flask+DB) | Nein |
| `test_exchange_rates.py` | 81 | exchange_rates | Integration (DB) | Nein |
| `test_ft_lifecycle.py` | 84 | FtObjectionEvent+FtAssistantEvent + export-script | Integration (DB) | Nein |
| `test_ft_models.py` | 53 | database.models (FT-Tables) | Schema | Nein |
| `test_ft_seed.py` | 31 | _seed_prompt_versions | Integration (DB) | Nein |
| `test_ft_write_hooks.py` | 199 | claude_service._write_ft_assistant_event | Integration (DB) | Nein |
| `test_models_04_7_2.py` | 59 | Schema-Smoke 6 Models | Schema | Nein |
| `test_mood_voice.py` | 118 | training_service.mood_to_voice_settings | Unit (pure) | Nein |
| `test_phase_08_migration.py` | 106 | app.py migration blocks (A-E) | **String-Grep in app.py** | **JA (6/6 Tests)** |
| `test_phase_08_models.py` | 60 | database.models Column-Definitions | Schema | Nein |
| `test_profile_editor_validation.py` | 130 | /profiles/api/profile/<id>/tabu | Integration (Flask+DB) | Nein |
| `test_profitability.py` | 90 | admin_dashboard.compute_org_profitability | Integration (DB) | Nein |
| `test_prompt_pipeline.py` | 218 | prompt_pipeline.resolve_prompt_version + build_profile_context + log_pipeline_event | Integration (DB) + 1 False-Green | Teilweise (H-1) |
| `test_qa_pipeline.py` | 216 | qa_pipeline.* | Unit+Mock | Nein |
| `test_qa_pipeline_rueckfrage.py` | 199 | qa_pipeline.build_tabu_instruction + generate_qa_response | Unit+Mock | Nein (aber Production-Call-Site ruft mit `{}` auf — LB-3) |
| `test_qa_pipeline_t1.py` | 43 | qa_pipeline RED-gate | **Subprocess grep + hasattr** | **JA (4/4 Tests)** |
| `test_revenue_webhook.py` | 87 | routes/payments._record_revenue | Integration (DB+Mock) | Nein |
| `test_tabu_migration.py` | 86 | profile_migration.migrate_tabu_begriffe | Unit (pure) | Nein |
| `tts_comparison.py` | 222 | TTS-Vergleichsscript | **NICHT pytest** (`print`-based) | — (kein Test-Asset) |
| `services/test_ki_logik.py` | 284 | ki_logik pure functions | Unit (pure) | Nein |

**Summe:** 35 Tests-Dateien (tts_comparison.py ist **kein pytest-Test**, nur ein manuelles Vergleichsscript).

---

## 2. False-Green-Identifikation

### 2.1 Absolute Zahlen

**Muster 1: `inspect.getsource()` + Substring-Match** (32 Tests):
- `test_claude_service_phase08.py`: **7/7 Tests** — Alle Tests nutzen `inspect.getsource()` auf `services.claude_service` und matchen Substrings wie `'from services.prompt_pipeline import resolve_prompt_version' in src` oder `'build_ewb_prompt(' in src`.
- `test_08_5_05_training_pipeline_t1.py`: **1/8 Tests** (Test 8 `test_prompt_pipeline_imports_wired` — `inspect.getsource` + `in src`).
- `test_08_5_05_training_pipeline_t2.py`: **11/14 Tests** — `inspect.getsource(ts.generate_response)` + Substring-Prüfung `'_load_training_prompt_template(' in src`, `'log_pipeline_event(' in src`, `'training_scoring' in src`. Nur 3 Tests machen echte mocked Call-Tests.
- `test_phase_08_migration.py`: **6/6 Tests** — liest `app.py` via `open()` + `read()` und greppt nach Markern wie `'Phase 08 D-01' in src`, `'CREATE TABLE objection_events_new' in src`. Prüft nicht, dass die Migration jemals ausgeführt wurde.

**Muster 2: `hasattr` + `callable` Existenz-Check** (8 Tests):
- `test_claude_service_phase08.py:80-105` — `test_legacy_symbols_preserved`, `test_import_smoke_no_side_effects`.
- `test_08_5_05_training_pipeline_t1.py:43-44, 146-147` — `callable(_load_training_prompt_template)`, `callable(ts.resolve_prompt_version)`, `callable(ts.log_pipeline_event)`.
- `test_ft_models.py:4-9` — `required.issubset(tables)`.

**Muster 3: Subprocess-grep in Source** (1 Test):
- `test_qa_pipeline_t1.py:31-39` — `test_haiku_model_id_in_file` ruft `subprocess.run(['grep', '-c', 'claude-haiku-4-5-20251001', 'services/qa_pipeline.py'])`.

**Muster 4: RED-Gate-Tests** (3 Tests, in test_qa_pipeline_t1.py):
- `test_import_classify_utterance`, `test_apply_tabu_filter_basic`, `test_match_faq_stub` — prüfen nur, dass Import funktioniert und dass die Funktion einen dict mit bestimmten Keys zurückgibt. Keine Produktions-Integration.

**Gesamt-False-Green-Count: ~51 Tests** (von ca. 250-280 Tests in 35 Dateien — grobe Schätzung 18-22%).

### 2.2 Beispiele (konkrete Evidence)

**Beispiel 1 — Der "klassische" False-Green:**
```python
# test_claude_service_phase08.py:46-47
assert 'system=_build_system_prompt()' not in src, \
    'analysiere_mit_claude darf system=_build_system_prompt() NICHT mehr nutzen'
```
Bestätigt: Legacy-Aufruf ist weg. Bestätigt NICHT: Neuer Pfad funktioniert. Genau das LB-3-Muster.

**Beispiel 2 — H-1 finetune_logging:**
```python
# test_prompt_pipeline.py:213-218
def test_log_pipeline_event_handles_missing_module(monkeypatch):
    """If services.finetune_logging does not exist at all, must still swallow."""
    monkeypatch.delitem(sys.modules, 'services.finetune_logging', raising=False)
    # Must not raise:
    pp.log_pipeline_event('assistant', 'ewb', {'model': 'haiku'})
```
Der Test verifiziert **explizit**, dass das System weiterläuft, wenn `finetune_logging.py` fehlt. Er ist grün — genau weil die Datei nicht existiert. **Production hat die Konsequenz: Kein FT-Training-Material wird persistiert.** Der Test sollte eigentlich rot sein (RED-Gate zur DB-Write-Verifikation).

**Beispiel 3 — Migration-Tests:**
```python
# test_phase_08_migration.py:26-33
def test_block_a_backup_present():
    src = _read_app()
    assert 'nerve.db.bak_pre_v08_01' in src
    assert 'shutil.copy' in src
```
Grep in `app.py`. Keine Prüfung, ob der Backup beim App-Start wirklich ausgeführt wird oder die Datei entsteht.

**Beispiel 4 — Training-Service (dasselbe Muster wie claude_service_phase08):**
```python
# test_08_5_05_training_pipeline_t2.py:44-50
def test_source_has_4_loader_calls():
    src = inspect.getsource(ts)
    count = src.count('_load_training_prompt_template(')
    assert count >= 4, f"_load_training_prompt_template call count < 4: {count}"
```
Zählt String-Vorkommen. Kein Live-Call, kein DB-Write-Check.

---

## 3. Coverage-Gap-Matrix

### 3.1 services/ — 22 Module

| Service | Test-Datei | Test-Qualität |
|---|---|---|
| `audit.py` | **KEINE** | ❌ GAP (H-8 Audit-Events) |
| `auth_decorators.py` | implicit (via `test_admin_dashboard_auth.py`) | Marginal |
| `claude_service.py` | 3× (phase08, ft_write_hooks, 08_5_03_integration) | **Source-Presence + 1 echter Integration-Test (_write_ft_assistant_event)** |
| `coaching_service.py` | **KEINE** | ❌ GAP (H-6 profile_data dead param) |
| `cost_tracker.py` | `test_cost_tracker.py` | Integration, aber nur 4 Tests — kein user_id-Concurrency-Test (LB-4) |
| `crm_service.py` | **KEINE** | ❌ GAP |
| `customer_success_service.py` | **KEINE** | ❌ GAP |
| `deepgram_service.py` | implicit (via `test_ewb_rate_api.py` für Anrede-Whitelist) | Marginal — **Kein Test für `ls.state['mode']`/`['org_id']` Writer (LB-5/6)** |
| `einwand_keyword_matcher.py` | `test_einwand_keyword_matcher.py` + `test_08_5_03_integration.py` | Unit-solid, aber **H-7 Race-Condition nicht getestet** (line_id-Drift zwischen Interim/Final) |
| `email_service.py` | **KEINE** | ❌ GAP (LB-1 Password-Reset-Chain dead) |
| `eur_calculator.py` | `test_eur_calculator.py` | Integration-solid |
| `ewb_pipeline.py` | `test_ewb_pipeline.py` | Integration-solid |
| `exchange_rates.py` | `test_exchange_rates.py` | Integration-solid |
| `feedback_service.py` | **KEINE** | ❌ GAP (MEDIUM — rollback fehlt) |
| `integration_engine.py` | **KEINE** | ❌ GAP (MEDIUM — SQLite-lock-in) |
| `ki_logik.py` | `tests/services/test_ki_logik.py` | Unit-solid (pure functions) |
| `live_session.py` | **KEINE direkt** (nur via anderen Tests) | Marginal |
| `precall_service.py` | **KEINE** | ❌ GAP (H-2 Feature-Fake) |
| `profile_migration.py` | `test_tabu_migration.py` + `test_branche_migration.py` (scripts/) | Unit-solid |
| `prompt_pipeline.py` | `test_prompt_pipeline.py` | Integration-solid, **aber H-1-False-Green** |
| `qa_pipeline.py` | 3× (`test_qa_pipeline.py`, `_t1.py`, `_rueckfrage.py`) | Unit+Mock solid — **aber testet isolated, nicht den kaputten Call-Site (LB-3)** |
| `training_service.py` | 3× (mood_voice, 08_5_05_t1, 08_5_05_t2) | **11/14 Tests Source-Presence** |

**GAP-Count: 7 Services ohne Tests** (`audit`, `coaching_service`, `crm_service`, `customer_success_service`, `email_service`, `feedback_service`, `integration_engine`, `precall_service`) — davon **4 mit HIGH/LB-Relevanz**.

### 3.2 routes/ — 22 Blueprints

| Route | Test-Datei |
|---|---|
| `admin_dashboard.py` | `test_admin_dashboard_auth.py` + `test_profitability.py` |
| `admin_ewb.py` | `test_admin_ewb_datetime.py` |
| `admin_views.py` | **KEINE** |
| `app_routes.py` | **KEINE direkt** (kritisch: /api/frage + /api/ewb_trigger — H-12/H-13) |
| `auth.py` | `test_auth_next_redirect.py` |
| `changelog.py` | **KEINE** |
| `coach.py` | **KEINE** |
| `dashboard.py` | **KEINE** |
| `feedback.py` | **KEINE** |
| `learning.py` | **KEINE** (H-5 Fake-Redeanteil) |
| `legal.py` | **KEINE** (LB-2 DSGVO) |
| `logs_routes.py` | **KEINE** |
| `oauth.py` | **KEINE** |
| `onboarding.py` | **KEINE** |
| `organisations.py` | **KEINE** |
| `payments.py` | `test_revenue_webhook.py` (nur Stripe-Webhook + tax-classify) |
| `performance.py` | **KEINE** |
| `profiles.py` | `test_profile_editor_validation.py` (nur Tabu-Sub-Endpoint) |
| `settings.py` | **KEINE** |
| `training.py` | **KEINE** (1331 Zeilen!) |
| `waitlist.py` | **KEINE** |

**GAP-Count: 15 von 22 Blueprints haben KEINE Tests.** Nur 7 teilgetestet. `training.py` (1331 Zeilen) ist der größte ungetestete Blueprint.

---

## 4. Bekannte Kaputt-Bereiche × Test-Coverage

| Finding | Severity | Tests vorhanden? | Details |
|---|---|---|---|
| **LB-1** Password-Reset-Flow | Launch-Blocker | **NEIN** | `email_service.send_password_reset` + `make_reset_token` haben keinen Test. Keine Route = kein Integration-Test. |
| **LB-2** DSGVO-Routen (export/delete/portability/consent) | Launch-Blocker | **NEIN** | `legal.py` hat keine Tests. Routes existieren nicht = nicht testbar. |
| **LB-3** QA-Pipeline profile_data `{}` / confidence `''` | Launch-Blocker | **NEIN (kritische Lücke)** | `test_qa_pipeline_rueckfrage.py` ruft `generate_qa_response()` mit **korrektem profile_data + confidence=0.90** auf. Bestätigt: Die Funktion funktioniert WENN korrekt aufgerufen. Bestätigt NICHT: Der tatsächliche Call-Site in `claude_service.py:1488-1490` ruft mit `{}` und `''` auf. Dieser Call-Site-Fehler ist **komplett ungetestet**. |
| **LB-4** Cost-Tracker Multi-User user_id-Drift | Launch-Blocker | **NEIN** | `test_cost_tracker.py` hat 4 Tests, alle mit `user_id=1` (einzelner User). Kein Concurrency-Test, kein "user_id=None fallback"-Test. |
| **LB-5** `ls.state['org_id']` Ghost (Reader ohne Writer) | Launch-Blocker | **NEIN** | Keine Test-Datei prüft, ob `deepgram_service.start_live_session` `ls.state['org_id']` schreibt. |
| **LB-6** `ls.state['mode']` Ghost | Launch-Blocker | **Teilweise, falsch** | `test_ft_write_hooks.py` setzt `mode` manuell über `_setup_ls_state(mode='cold_call')`. Bestätigt: WENN mode gesetzt ist, funktioniert Code. Bestätigt NICHT: deepgram_service schreibt mode jemals. |
| **LB-7** Traceback-Leak `errorhandler` | Launch-Blocker | **NEIN** | Keine Test-Datei prüft `app.py:1697-1726` Error-Handler-Response. |
| **LB-8** Multi-Worker analyse_loop/coaching_loop | Launch-Blocker | **NEIN** | Keine Tests für Worker-Guard-Pattern. |
| **H-1** `services/finetune_logging.py` existiert nicht | HIGH | **FALSE-GREEN** | `test_prompt_pipeline.py:213` explizit Test-Design "dass es schweigt wenn Modul fehlt". Grün bestätigt Kaputtheit. |
| **H-2** PreCall-Briefing Feature-Fake | HIGH | **NEIN** | `precall_service.py` ohne Tests. Kein Test prüft, ob `ls.state['precall_briefing']` live gelesen wird. |
| **H-3** `analysiere_mit_claude_streaming` dead (102 Zeilen) | HIGH | **FALSE-GREEN** | `test_claude_service_phase08.py:50-59` testet **aktiv die Streaming-Variante**. Grün-Test hält dead code am Leben. Bei Prune → Tests brechen. |
| **H-4** `_build_system_prompt` + `_get_erfolgsquoten` Dead | HIGH | **FALSE-GREEN** | `test_claude_service_phase08.py:82-87` — `hasattr(cs, '_build_system_prompt')` wird positiv assertiert. Test schützt dead code vor Prune. |
| **H-5** Training-PostCall Fake-Redeanteil | HIGH | **NEIN** | Kein Test in gesamter Suite grept nach `redeanteil_berater=60` / `learning.py:268`. |
| **H-6** `generate_postcall_analysis` dead parameter `profile_data` | HIGH | **NEIN** | `coaching_service.py` komplett ungetestet. Kein Test für Signatur/Body-Konsistenz. |
| **H-7** `kw_fired_for_line` Race | HIGH | **Teilweise** | `test_08_5_03_integration.py` testet den Guard, aber nicht das Race zwischen Interim- und Final-Segments. |
| **H-8** DSGVO Audit-Event-Coverage | HIGH | **NEIN** | `audit.py` komplett ungetestet. Kein Test für register/password_reset/account_delete/data_export-Events. |
| **H-9** Deepgram Overcharge (Socket-Lifetime statt STT-Sekunden) | HIGH | **NEIN** | Cost-Tracker-Tests nutzen `units=10.0` hardcoded, keine Socket-Lifetime-Simulation. |
| **H-10** `_parse_json` Silent-Failure | HIGH | **NEIN** | Kein Test in `claude_service` für JSON-Decode-Fallback + Logging. |
| **H-11** ANALYSE_INTERVALL Drift + if/else dead branch | HIGH | **NEIN** | Kein Test für `analyse_loop`-Timing oder Branch-Coverage. |
| **H-12** `/api/frage` + `/api/ewb_trigger` Cost-Tracking fehlt | HIGH | **NEIN** | `app_routes.py` Routes 1118-1272 komplett ungetestet. |
| **H-13** Profil-Feld-Drift `pdata.get("produkt")` in Routes | HIGH | **NEIN** | Kein Test für diese beiden Routes. |
| **H-14** Duplicate-Logging EWB-Clicks | HIGH | **NEIN** | Kein Test auf Counter-Parity `record_ewb_click` vs `FtObjectionEvent` |
| **H-15** `jsonify({'error': str(e)})` Error-Response-Leak | HIGH | **NEIN** | Kein Test-Pattern sucht nach Exception-Message in Response. |

**Kritische Beobachtung:** 
- **Tests bestätigen die Kaputtheit: H-1, H-3, H-4 sind grün WEIL sie designed sind, Legacy-/Dead-Code zu akzeptieren.** Ein Prune bricht die Test-Suite.
- **Alle Launch-Blocker (LB-1..LB-8) haben 0 echte Test-Coverage.**

---

## 5. Flaky / Skipped Tests

**Ergebnis:** Absolute Null.

- **`@pytest.mark.skip` / `xfail` / `skipif`:** 0 Treffer in gesamter Suite (Grep bestätigt).
- **Flaky-Kommentare:** 0 Treffer für "fail permanent", "out of scope", "flaky".
- Einziges legitimes Skip: `test_eur_pdf.py:4` `pytest.importorskip("weasyprint")` — hängt von externer Lib ab, sauber begründet.

Bedeutet: **Die Suite ist sauber grün** — aber wie oben gezeigt, ist das die False-Positive-Sauberkeit. Niemand hat einen Test geparkt mit "später fixen". Alles ist "fertig". Das ist genau Muster 2 aus MASTER-AUDIT ("Phase-Closeout ohne Live-Path-Verification") übertragen auf Tests.

---

## 6. Test-Daten / Live-DB-Leak-Prüfung

**Sauber.**

- `conftest.py:43` + `:66` — ausschließlich `sqlite:///:memory:`
- Fixture `db_session`: In-Memory, per-Test-disposed
- Fixture `client`: monkeypatcht `database.db.engine`, `SessionLocal`, `db_session` auf In-Memory vor App-Import — kein Write auf Produktions-DB möglich.
- **Einzige Ausnahme:** `services/exchange_rates.get_current_rate()` leakt in MASTER-AUDIT FX-1 "auf Live-DB, 2 Tests failen seit Phase 04.7.2". In der aktuellen Test-Suite `test_exchange_rates.py` sind die Tests grün (mit Mock-Patches) — der Leak passiert wohl außerhalb der Test-Suite (im Live-Code), nicht in den Tests selbst.

Keine `stripe_invoice.json`-Fixture schreibt auf Live-Stripe (`_mock_customer` mockt alles).

---

## 7. Integration-Tests / E2E

**Kein E2E-User-Flow-Test.**

Suche nach: Register → Profile anlegen → Call starten → End.

- **Register:** 0 Tests (keine Datei greppt `/api/register` oder `/register`).
- **Profile erstellen:** `test_profile_editor_validation.py` testet den Tabu-Sub-Endpoint eines existierenden Profils. Kein Profile-Create-Test.
- **Call starten:** `test_ewb_rate_api.py` + `test_08_5_03_integration.py` testen EINZELNE Socket-Events / Dispatches. Kein Test `start_live_session` → `/api/beenden` vollständig durch.
- **End:** Keine `/api/beenden`-Tests.

Vorhandene **Cross-Cutting-Integration:**
- `test_admin_dashboard_auth.py`: unauth → 302 → 200 Auth-Flow — aber nur Admin, kein normaler User-Flow.
- `test_auth_next_redirect.py`: Login-Flow + next-Parameter — guter Single-Flow-Test.
- `test_ewb_rate_api.py`: End-to-End Rating-API mit DB-Verifikation — gut.

**Aber:** Kein Test für den KRITISCHEN Pfad "User beginnt Cold Call → Keyword triggert → EWB emittiert → User rated → DB-Row wird geschrieben → Post-Call-Analyse läuft → Coach-Tipps generiert". Dieser Pfad ist der USP von NERVE — er hat NULL End-to-End-Test.

---

## 8. Severity-Klassifizierung

### HIGH — Coverage-Lücken für Launch-Blocker

1. **LB-1 Password-Reset:** 0 Tests für Reset-Flow. Vor Launch Pflicht: Integration-Test Register → Forgot-Password → Token-Mail → Reset → Login mit neuem Password.
2. **LB-2 DSGVO-Routen:** 0 Tests für `/dsgvo/*`. Nach Implementation Pflicht: Integration-Test für Data-Export, Account-Delete (mit Kaskaden-Check), Consent-Withdraw.
3. **LB-3 QA-Pipeline Call-Site:** Unit-Tests von `generate_qa_response` sind grün, aber das verbirgt den Fehler. **Test-Gap:** Integration-Test der `_qa_pipeline_dispatch` mit echtem geladenem profile_data statt `{}` — und Tabu-Assertion "Wort 'Kosten' darf NICHT in Response sein wenn profile.tabu_begriffe `Kosten→Investition` enthält".
4. **LB-4 Cost-Tracker Multi-User:** 0 Concurrency-Tests. Pflicht vor Launch: 2 parallele Sessions → Cost-Events korrekt zugeordnet.
5. **LB-5/LB-6 State-Writer-Tests:** Gar kein Test verifiziert, dass `deepgram_service.start_live_session` `ls.state['org_id']` + `ls.state['mode']` schreibt.
6. **LB-7 Error-Handler:** 0 Tests für Traceback-Leak-Verhinderung.
7. **H-1 finetune_logging:** Bestehender Test IST False-Green. Nach Fix: Test umdrehen — "log_pipeline_event MUSS in DB schreiben".
8. **H-5/H-6 Training-PostCall:** Gar keine Tests für `coaching_service` + `learning.py:268` Hardcoded-Zahlen.
9. **H-12/H-13 Inline-Anthropic-Routes:** `/api/frage` + `/api/ewb_trigger` komplett ungetestet.

### MEDIUM — False-Greens die dead code schützen

10. **Source-Presence-Muster entfernen:** `test_claude_service_phase08.py` + `test_08_5_05_training_pipeline_t2.py` + `test_phase_08_migration.py` — 24 Tests umschreiben auf Integration oder löschen. Diese Tests werden aktiv BRECHEN wenn dead code weg ist (H-3, H-4) — das ist ein Prune-Blocker.
11. **Migration-Tests:** `test_phase_08_migration.py` komplett umbauen: Tatsächlicher Migration-Lauf auf Fresh-DB + PRAGMA-Checks + Row-Migration verifizieren.
12. **Coverage-Lücken audit.py / email_service.py / feedback_service.py:** Mittlere Priorität, vor Launch Skeleton-Tests.

### LOW — Hygiene

13. **`tts_comparison.py`:** Datei ist kein pytest-Test (print-basiert). Entweder zu `scripts/` verschieben oder in pytest-Form bringen.
14. **`test_qa_pipeline_t1.py`:** Subprocess-grep gegen Source — ersetzen durch Integration-Test auf den Production-Pfad.
15. **Test-Namenskonvention Drift:** `test_08_5_03_integration.py`, `test_08_5_05_training_pipeline_t1.py` mit Phase-Nummer im Namen. Bei Phase-Abschluss-Archivierung umbenennen oder in `tests/archive/` verschieben.

---

## 9. Ursachen-Analyse (MASTER-AUDIT-Kontext)

Die Test-Suite leidet an **demselben Muster 3** wie die Codebase (siehe MASTER-AUDIT Z.287-289):

> **Muster 3: Test-False-Greens.** Tests prüfen Source-Presence statt Integration. Beispiel: QA-Pipeline-Tests bestätigen dass `log_pipeline_event` gerufen wird — nicht dass es tatsächlich in DB schreibt.

**Aber schlimmer:** Die Tests wurden im TDD-RED-Gate-Stil geschrieben ("Test MUST fail before Task 1 edits"), aber nach dem GREEN-Phase-Übergang wurden **zu viele Tests nicht zu echten Integration-Tests weiterentwickelt**. Die "RED → GREEN → REFACTOR"-Schleife ist bei REFACTOR stehengeblieben.

**Zweitens:** TDD-Tests die nur Substring-Matches machen sind **nützlich zum Entwickeln** (sicherer Handover zwischen Plan und Implementation), aber sie sind **kein Ersatz für Integration-Tests**. Die Phase-Closeout-Checkliste hat diese Unterscheidung nie eingezogen.

**Drittens:** Einige Tests sind aktiv **anti-Prune-Wälle**: `test_claude_service_phase08.py:80-87` schützt `_build_system_prompt` + `_ACTIVE_PROMPT_CACHE` explizit vor Löschung. Das ist die codifizierte Dead-Code-Schutzregel — und bedeutet, dass der H-4-Fix ("_build_system_prompt löschen") die Suite rot macht, was die Prune-Arbeit verzögert.

---

## 10. Empfehlungen für Stabilisierungs-Phase

**Block-T1 (vor LB-Fixes): Test-Infrastructure-Cleanup (~4h)**
1. `test_claude_service_phase08.py`: 7 Tests komplett löschen oder auf Mocked-Integration umbauen. Inspect-Source-Tests sind wertlos nach Phase-Abschluss.
2. `test_08_5_05_training_pipeline_t2.py`: 11/14 Tests löschen, Core-3 Tests mit Mock-Client behalten.
3. `test_phase_08_migration.py`: 6 Tests umbauen auf tatsächlichen Migration-Run mit fresh DB.
4. `test_qa_pipeline_t1.py`: 4 Tests löschen (RED-Gate ist vorbei).

**Block-T2 (parallel zu LB-Fixes): Launch-Blocker-Tests schreiben (~10-15h)**

5. LB-1: Integration-Test Password-Reset-Flow (3-4 Tests: happy-path, invalid-token, expired-token).
6. LB-2: Integration-Tests für 4 DSGVO-Routen (je 2-3 Tests: happy-path, unauth, auth-wrong-org).
7. LB-3: Test in `test_08_5_03_integration.py` erweitern — `_qa_pipeline_dispatch` mit geladenem Profil (tabu + einwände) + Assertion "response darf keine Tabu-Begriffe enthalten".
8. LB-4: Concurrency-Test mit 2 parallelen `log_api_cost`-Calls unterschiedliche user_id.
9. LB-5/LB-6: Unit-Test in neuer `test_deepgram_service.py` — `start_live_session` schreibt `ls.state['org_id']` + `ls.state['mode']`.
10. LB-7: Integration-Test Error-Handler — ausgelöste Exception → Response enthält KEIN Traceback.

**Block-T3 (während Härtung): HIGH-Coverage (~8-10h)**

11. H-1: Test `log_pipeline_event` IN finetune_logging.py schreibt `FtPipelineEvent` DB-Row.
12. H-5/H-6: Test `generate_postcall_analysis` mit echtem `profile_data` — Prompt enthält Profil-Fakten.
13. H-12/H-13: Integration-Tests `/api/frage` + `/api/ewb_trigger` — Cost-Event + Profil-Context-Leer-Fehler.

**Block-T4 (langfristig): End-to-End-Test-Infrastruktur (~6-8h)**

14. `test_e2e_cold_call.py`: Register → Profile → Headset-Consent → start_live_session → Fake-Transcript → EWB → Rate → beenden → PostCall-Analyse prüfen.
15. `test_e2e_training.py`: Register → Training-Start → Mood-Change → Scoring → End.

---

## Top-3-Message an André

1. **Die Test-Suite ist false-grün. 0 skipped, 0 xfail — aber ~20% der Tests sind Source-Presence-Matches die keine echten Bugs fangen.** Bevor du irgendwas fixt: Die Tests die AKTIV DEAD CODE SCHÜTZEN (test_claude_service_phase08 etc.) müssen weg, sonst blockiert jede Prune-Arbeit an H-3/H-4 die Pipeline.

2. **Die Launch-Blocker sind alle ungetestet.** Auch die "funktionalen" Tests wie `test_qa_pipeline_rueckfrage.py` testen die Isolierte-Funktion korrekt, aber nicht den Call-Site-Bug (`{}` + `''`). Deine Stabilisierungs-Phase braucht parallel ~10-15h Test-Schreib-Arbeit um nicht blind zu fixen.

3. **Test-Muster-Regel für CLAUDE.md: "Ein Test ist nur dann grün, wenn er eine Integration-Assertion macht."** Source-Presence-Matches sind TDD-Zwischenstufen, kein Phase-Closeout. Die Phase-Closeout-Checkliste muss: "Tests prüfen Live-Path (DB-Write/API-Response/State-Mutation), nicht Code-Vorhandensein."

---

*Stand: 2026-04-24. Scan-Dauer: ~25 min. Grep-Fokus: False-Green-Muster + LB/H-Abgleich. Volle Test-Body-Inspektion nur für kritische Dateien.*
