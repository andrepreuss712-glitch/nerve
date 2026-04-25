---
audit: MASTER-AUDIT
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault) + 7 parallele Deep-Dive-Agenten
basiert_auf:
  - .planning/audits/profil-prompt-integration-matrix.md (Phase A, manuell)
  - .planning/audits/deep-dive-claude-service.md (Welle 1)
  - .planning/audits/deep-dive-live-session-ki-logik.md (Welle 1)
  - .planning/audits/deep-dive-deepgram-keyword.md (Welle 1)
  - .planning/audits/deep-dive-pipelines.md (Welle 1)
  - .planning/audits/deep-dive-training-coaching-precall.md (Welle 2)
  - .planning/audits/deep-dive-audit-cost-feedback-email.md (Welle 2)
  - .planning/audits/deep-dive-crm-cs-integration-utilities.md (Welle 2)
  - Routes-Stichproben (Claudian direkt): auth.py, learning.py, admin_ewb.py, legal.py
  - Salesnerve-Commit: 6464ec9 (2026-04-24)
scope:
  - Alle 20 Services-Dateien: 100% gelesen
  - Routes: 4/20 direkt gelesen, Rest wartet auf Welle 3 Retry (Rate-Limit-Reset 19:20)
  - Frontend + DB + Config + Tests: wartet auf Welle 4+5
---

# MASTER-AUDIT — NERVE Codebase Deep-Dive

**Stand-Tag:** 2026-04-24, 15:40 Uhr
**Status:** Services komplett. Routes zu 20% direkt verifiziert (4/20). Frontend/DB/Tests offen bis 19:20 Rate-Limit-Reset.

---

## EXECUTIVE SUMMARY

Die NERVE-Codebase ist in **deutlich schlechterem Zustand** als die vorhandene Dokumentation suggeriert. 7 parallele Deep-Dive-Agenten und 4 manuell auditierte Routes haben eine Nudelcode-Dichte offengelegt die Launch-kritisch ist.

**Kernbefund:** Die Phase-Abschluss-Doku (Handoffs, Verification-Files) ist systematisch optimistischer als der tatsächliche Code. Features werden als "verdrahtet" abgehakt ohne Live-Pfad-Verifikation. Das ist das **Muster** hinter dem Nudelcode — nicht einzelne Fehler.

**Zahlen (konservativ):**
- ~325 Zeilen **dead code** in Services (claude_service.py: 295, andere: ~30)
- ~17 Zeilen **dead code** in email_service (Password-Reset-Chain)
- ~50+ Zeilen **Zombie-Code** (wird nur von dead code gerufen)
- **11 HIGH-Severity-Funde** (Launch-Blocker + Datenintegrität)
- **~15 MEDIUM-Severity-Funde**
- **5 Doku-Lügen** in GSDs ARCHITECTURE/STRUCTURE gegen Code verifiziert

**Wichtigste Ursachenkategorie:** Phase-08-Refactor (Prompt-Pipeline-Umstellung) hat Legacy nicht geprunt. Phase-04.13, 04.7.2 und 04.11 haben Features als "fertig" geschlossen die nie live verdrahtet waren.

---

## 🔴 LAUNCH-BLOCKER (muss VOR DACH-EA gefixt werden)

### LB-1: Password-Reset komplett fehlt

**Evidence:** Direkt verifiziert in `routes/auth.py` (288 Zeilen). Kein `/api/password_reset_request`, kein `/password_reset`-HTML-Route, kein Caller für `email_service.send_password_reset` / `make_reset_token` / `parse_reset_token`.

**Folge:** User die Passwort vergessen → gesperrt, kein Self-Service-Recovery.

**Phase-Doku-Lüge:** Phase-04.7-05-Summary hat Password-Reset als "verdrahtet" abgehakt. War falsch.

**Fix-Aufwand:** ~3-4h. Route + Template + Caller-Verdrahtung + Audit-Event.

### LB-2: DSGVO-Rechte-Routen fehlen komplett

**Evidence:** `routes/legal.py` ist 15 Zeilen. Nur `/impressum`, `/agb`, `/datenschutz` als Static-HTML. Keine einzige funktionale DSGVO-Route.

**Fehlend:**
- `/dsgvo/data_export` (Art. 15 — Auskunft)
- `/dsgvo/account_delete` (Art. 17 — Löschung)
- `/dsgvo/data_portability` (Art. 20)
- `/dsgvo/consent_withdraw` (Art. 7)

**Folge:** NERVE positioniert "DSGVO als USP", aber die Rechte sind technisch ungedeckt. **Abmahn-Risiko** vor EA-Start, besonders bei B2B mit 50 Early-Access-Usern die ihre Daten kontrollieren wollen.

**Fix-Aufwand:** ~8-12h (4 Routes + DB-Löschkaskaden + Audit-Events).

### LB-3: Tabu-System im QA-Pfad komplett wirkungslos

**Evidence:** Direkt verifiziert in `claude_service.py:1488-1490` und `:1528-1530`:
```python
_antwort = generate_qa_response(
    neuer_text, 'einwand_unknown', {}, _anrede, '', _user_id
)
```
- Parameter 3 `profile_data` = `{}` (**hardcoded leeres Dict**)
- Parameter 5 `confidence` = `''` (**leerer String**)

**Folge:**
- `build_tabu_instruction({})` → leerer Tabu-Block im System-Prompt
- `build_protected_words({}, [])` → leerer Set → Safety-Net hat keine Protected-Words
- `float('')` throws ValueError → von `except` geschluckt → fallback zu `_FALLBACK_RUECKFRAGE`

**Das erklärt Andrés UAT-Finding vom 24.04.:** "Tabu mit 'zu teuer' — 50% Hit-Rate, eine Antwort enthielt 'Kosten'." → EWB-Pfad respektierte Tabu (via `build_profile_context`), QA-Pfad war nackt.

**Die komplette Phase-08.5-Korrektur-Arbeit am Tabu-System war im QA-Pfad de facto nie live.**

**Fix-Aufwand:** ~1h (profile_data laden + als Parameter durchreichen + confidence als float/None).

### LB-4: Cost-Tracking schreibt falschen User zu

**Evidence:** `services/cost_tracker.py` Welle-2-Audit: 21/27 `log_api_cost`-Calls mit `user_id=None`. Wird NICHT verworfen, sondern mit NULL ODER **stale user_id vom letzten Socket-User** geschrieben.

**Folge bei Concurrency:**
- User A startet Session → user_id gesetzt
- User B startet parallel Session → Socket überschreibt user_id
- Cost-Hook ohne user_id → nimmt letzten gesetzten Wert → bucht Kosten auf User B die User A verursacht hat

**Multi-User-Billing-Horror.** Fair-Use-Limits fallen aus, Chargebacks möglich.

**Fix-Aufwand:** ~2-3h (explizite user_id in allen Cost-Calls, Test mit Parallel-Sessions).

### LB-5: `ls.state['org_id']` Ghost — alle ApiCostLog NULL

**Evidence:** `services/cost_tracker._resolve_org_id_from_live_session()` liest `ls.state['org_id']`. **Null Writer in gesamter Codebase.** → Funktion gibt immer None → **alle `ApiCostLog.org_id`-Werte sind NULL** → Per-Org-Dashboard (`admin_dashboard.py:548-550`) zeigt für jede Org **0 €**.

**Folge:** Billing-relevante Daten sind leer. Founder-Cost-Dashboard (Phase 04.7.2) liefert falsche Zahlen.

**Fix-Aufwand:** 5 Minuten — 1 Zeile in `deepgram_service.py:351` ergänzen.

### LB-6: `state['mode']` Ghost Read

**Evidence:** `claude_service.py` liest `ls.state['mode']` 3x (Cold-Call-Logik, Phase-Detection, Inference-Trigger). **Nie geschrieben.** `deepgram_service.py:274` liest `mode` aus Request-Data in lokale Variable, vergisst aber im Init-Block 350-353 (wo user_id/market/language/ft_session_id gesetzt werden) auch `ls.state['mode'] = mode` zu schreiben.

**Folge:** Cold-Call-Inference + Mode-sensitive DSGVO-Logik läuft seit Phase 04.8 auf Default-Fallback (`'cold_call'`). Meeting-Modus evtl. betroffen — weitere Verifikation nötig.

**Fix-Aufwand:** 5 Minuten — 1 Zeile in `deepgram_service.py:351` ergänzen (selbe Stelle wie LB-5).

---

## 🟠 HIGH-Severity (keine Launch-Blocker, aber System-Integritäts-Risiken)

### H-1: `services/finetune_logging.py` existiert nicht im Repo

**Evidence:** Glob in Codebase = 0 Treffer.

**Folge:** Alle `log_pipeline_event`-Calls (qa_pipeline 2x, training_service 3x) scheitern silent beim Import, returnen mit `[Pipeline] log_pipeline_event unavailable`. **Kein FT-Training-Material wird persistiert**, trotz `FtQaEvent`-DB-Tabelle.

**Tests sind False-Greens** — prüfen nur Source-Presence, nicht tatsächliches Schreiben.

**Fix-Aufwand:** ~4-6h (finetune_logging.py bauen + DB-Write testen + Live-Verifikation).

### H-2: PreCall-Briefing ist Feature-Fake

**Evidence:** Multi-Audit-Bestätigung. `precall_service.recherche_firma` funktioniert, schreibt in `ls.state['precall_briefing']`. Aber **kein Live-LLM-Pfad liest das State-Feld** — einziger Konsument war `_build_system_prompt`, das selbst dead code ist.

**Folge:** Die Phase 04.13 PreCall-Intelligence + Quick-260414-kf8 war nie wirklich live. User sieht Briefing in UI, Live-KI ignoriert es komplett.

**Fix-Aufwand:** ~3-4h (re-wire in `build_profile_context` ODER explizit deprecaten).

### H-3: `analysiere_mit_claude_streaming` (102 Zeilen) ist DEAD

**Evidence:** `claude_service.py:704-805`. Phase 06.3 hat `analyse_loop` auf non-streaming umgestellt, Streaming-Variante wurde nicht entfernt.

**Folge:** 102 Zeilen ungenutzter Code. GSDs CONCERNS.md-Performance-Kritik basierte auf veralteter Annahme der Streaming-Nutzung.

**Fix-Aufwand:** 15 Minuten (löschen + Tests anpassen).

### H-4: `_build_system_prompt` + `_get_erfolgsquoten` Dead/Zombie (195 Zeilen)

**Evidence:** Welle-1-Audit. `_build_system_prompt` (Z.265-401, 136 Z.) dead seit Phase 08. `_get_erfolgsquoten` (Z.206-262, 57 Z.) Zombie — nur vom dead Builder gerufen.

**Fix-Aufwand:** 30 Minuten. Aber: Entscheidung nötig ob Felder (Einwände-Liste, Zielgruppe, Wettbewerber, etc.) die dieser Builder kannte in `build_profile_context` portiert werden sollen — das ist eine Profil-Redesign-Frage (siehe Phase-A-Audit).

### H-5: Training-PostCall-Analyse füttert Sonnet mit Fake-Zahlen

**Evidence:** Direkt verifiziert in `routes/learning.py:268-269`:
```python
redeanteil_berater=60,
redeanteil_kunde=40,
```
Hardcoded. Sonnet analysiert auf Basis erfundener Messwerte und liefert Coach-Tipps die diese Lüge zitieren.

**Fix-Aufwand:** 2-3h (Redeanteil aus conversation_log berechnen, fallback wenn keine Daten).

### H-6: `generate_postcall_analysis` Dead Parameter

**Evidence:** `coaching_service.py`. Signatur hat `profile_data=None`. Body referenziert es nie. **Beide Sonnet-PostCall-Call-Sites (Live + Training) sind profil-blind.**

**Folge:** Post-Call-Coach-Tipps ohne Profil-Kontext — generisch.

**Fix-Aufwand:** 1-2h (profile_data ins Prompt einbauen, Test).

### H-7: `kw_fired_for_line` D-02 Guard Race-Condition

**Evidence:** Welle 1. Matcher läuft auf Interim-Transcripts, setzt `kw_fired_for_line = ls.state['line_id']`. Aber `line_id` wird nur bei Final-Segments geschrieben → referenziert ZULETZT analysierte Line, nicht aktuelle Interim-Line.

**Folge:** Doppel-Emit Keyword + qa_pipeline möglich. `slot1_variant_busy_until` fängt nur zufällig.

**Fix-Aufwand:** 3-4h (eigene Interim-Line-ID oder Timestamp-basierter Dedup).

### H-8: 10+ DSGVO-Audit-Coverage-Gaps

**Evidence:** Welle 2. Nur 6 Action-Types in `audit.log_action` gefunden (login, logout, session_start, session_end, profile_update, feedback). Fehlt: **register, password_reset, account_delete, data_export, consent_change, failed_login**, Flask-Admin-Hooks.

**Folge:** Art. 7/15/17/20 DSGVO technisch nicht überprüfbar.

**Fix-Aufwand:** 4-6h (Audit-Events in relevante Routes einbauen + Retention-Policy definieren).

### H-9: Deepgram Overcharge

**Evidence:** Welle 2. `cost_tracker` misst Socket-Lifetime (Verbindung offen) statt STT-Sekunden (audio processed). → Wir loggen höhere Kosten als Deepgram uns in Rechnung stellt.

**Folge:** Founder-Dashboard zeigt zu hohe Costs, Fair-Use schlägt zu früh an.

**Fix-Aufwand:** 2-3h (Deepgram-SDK-Usage-Event nutzen statt Socket-Timer).

### H-10: `_parse_json` Silent-Failure im Hot-Path

**Evidence:** `claude_service.py:472`. `except json.JSONDecodeError: return {}` ohne Log.

**Folge:** Malformed Haiku-Responses verschwinden als "kein Einwand". Unauffällige EWB-Drop-Outs wahrscheinlich — kein Monitoring möglich.

**Fix-Aufwand:** 30 Minuten (Log mit Text-Snippet + Metric).

### H-11: ANALYSE_INTERVALL Drift + tote if/else-Struktur

**Evidence:** Welle 1. `config.py::ANALYSE_INTERVALL = 4` (nicht 2 wie CONCERNS.md behauptet). `claude_service.py:1070-1079` analyse_loop hat if/else wo beide Branches `analysiere_mit_claude()` rufen (leftover vom entfernten Streaming-Branch).

**Fix-Aufwand:** 15 Minuten (Doku fixen + if/else aufräumen).

---

## 🟡 MEDIUM-Severity (Technische Schulden, Abrieb-Quellen)

- **`apply_tabu_filter` deprecated aber einzig-wirksame Tabu-Firewall im QA-Pfad** (weil LB-3). Nach LB-3-Fix dann wirklich deprecated markieren.
- **`_FALLBACK_QA_RESPONSE_PROMPT` dead** — `_load_qa_template('qa_response', ...)` wird nirgends gerufen, DB-A/B für QA-Response nicht verdrahtet.
- **Resolver-Cache nicht thread-safe** — kleines Race, Perf-Drift, nie live invalidiert (keine Admin-Route für Prompt-Edits).
- **HINT_PRIORITY orphaned constant** — `ki_logik.py:85` definiert, `claude_service.py:1269-1285` hardcodet Werte 1-5 separat → Drift-Risiko.
- **Legacy-Reader-Kette** — `aktives_skript_inhalt`, `skript_bloecke`, `precall_briefing` nur von dead `_build_system_prompt` gelesen.
- **Unused imports/params** — `ANALYSE_INTERVALL` in live_session.py:9, `transcript_window` + `phase_change_count` in ki_logik.
- **`kaufbereitschaft` Doppelführung** — Global + `state[...]`, aktuell durch Mirror-Write synchron gehalten aber fragil.
- **`state['phase_changed_at']` kein Python-Reader** — evtl. nur Frontend via Polling, aber Feld ist NICHT im `/api/ergebnis`-Payload — effektiv orphan.
- **FX-Fallback 0.92 hardcoded + stale** (EZB aktuell ~0.89).
- **Duplizierte FX-Logik** — `cost_tracker._get_current_fx_rate` dupliziert `exchange_rates.get_current_rate` ohne Service zu nutzen.
- **FX-1 Test-Leak** — `exchange_rates.get_current_rate()` leakt auf Live-DB, 2 Tests failen seit Phase 04.7.2.
- **`ga_details` orphan Parameter** in `run_postcall_engine`.
- **`needs_learning_card` tote Flag-Kette** in `run_posttraining_engine` (Phase 04.12-Plan-03 nie gebaut).
- **SQLite `json_extract` Lock-in** in integration_engine (3 Stellen) — PostgreSQL-Migrations-Blocker.
- **`build_sekretaerin_prompt` test-only**, `TRAINING_PERSONA_PROMPT_BASE` unreferenziert, `_scoring_preamble` dead local var.
- **Training-Service hat NULL Cost-Tracking** — 5 Claude-Calls (inkl. Sonnet 3000 max_tokens) unsichtbar.
- **`reset_keyword`/`reset_all`** im Keyword-Matcher nur in Tests gerufen — Klasse wirkt stateful-mit-Reset, ist aber per-sid-throwaway.
- **Profile-JSON kein Schema-Validator** — Regex-Patterns können malformed sein, Matcher failt silent.
- **Conversation-Log kein Schema-Validator** — Format-Drift würde Postcall silent brechen.
- **`create_feedback` ohne DB-Rollback** → 500 an User bei Constraint-Violation.
- **Kein Audit-Log-Retention** + Immutable-Trigger-Konflikt mit DSGVO Speicherbegrenzung.
- **`Feedback` vs. `FeedbackEvent`** zwei Models, ein Service (Schema-Parallelismus).
- **Resend EU-Region** hängt an Account-Setting, Code validiert nicht.
- **`create_feedback` ohne Rollback** → 500 bei Constraint-Violation.
- **`crm_service._client` eager beim Import** — nicht robust.
- **`EUR_LINES` / `UST_KZ` Konstanten** in `eur_calculator.py` nirgends extern importiert — Zombie-Exports.
- **`integration_engine`** mischt `datetime.now()` (lokal) mit `utcnow()` im Rest der Codebase.
- **`profile_migration.TABU_DEFAULT_PAIRS`** in `static/profile_editor.js:131` manuell gespiegelt — Source-of-Truth-Duplikat.
- **`kompliziert → datenschutz` Alias** semantisch falsch in Keyword-Matcher.
- **Alias-Overlap** `ueberlegen`/`falscher_ansprechpartner` auf `entscheider` — erster Regex-Treffer gewinnt, Reihenfolge undokumentiert.

---

## 🟢 LOW / Kosmetik

- 3× Import `time` in deepgram_service.py
- STT-Cost-Hook mit hardcoded `user_id=None`
- Kein Reconnect für Deepgram-WebSocket
- Hardcoded Modelle (Model-Name 9x `"claude-haiku-4-5-20251001"` in claude_service.py — 9 Edits bei Wechsel)
- `eur_calculator.fc_by_line` silent-swallows bei unbekannten `eur_line` Werten

---

## 📚 Doku-Lügen gegen Code verifiziert

| Quelle | Behauptung | Realität |
|---|---|---|
| ARCHITECTURE.md Z.186 | "PreCall stored in ls.state — Injected into EWB prompts via build_profile_context (D-40)" | **Falsch.** Wird nie gelesen. |
| ARCHITECTURE.md Z.93, 183-185 | Impliziert precall_briefing-Injection in EWB | **Falsch.** |
| CONCERNS.md Z.128 | "precall_briefing — Never read" | **Ungenau.** Gelesen in totem `_build_system_prompt`-Pfad. |
| CONCERNS.md | "ANALYSE_INTERVALL = 2s" | **Falsch.** Code sagt 4s. |
| STRUCTURE.md Z.31 | "crm_service.py hat HubSpot/Salesforce-Stubs" | **Falsch.** Reine Claude-Haiku-Generierung. |
| STRUCTURE.md Z.35 + ARCHITECTURE.md Z.308 | "login_required in auth_decorators.py" | **Falsch.** Sitzt in auth.py:42. auth_decorators.py hat nur `superadmin_required`. |
| Phase-04.7-05-Summary | "Password-Reset verdrahtet" | **Lüge.** Chain ist dead. |
| Phase 04.13 + Quick-260414-kf8 | "PreCall-Briefing Live-Feature" | **Feature-Fake.** Output landet in ls.state, wird nirgends gelesen. |

---

## 🏗️ Nudelcode-Ursachen-Analyse

**Muster 1: Phase-Refactor ohne Pruning.**
Phase 08 baute neue EWB-Pipeline, ließ `_build_system_prompt` stehen "für Legacy-Module". Kein Legacy-Modul nutzt es. Phase 06.3 stellte auf non-streaming um, ließ `analysiere_mit_claude_streaming` stehen.

**Muster 2: Phase-Closeout ohne Live-Path-Verification.**
Phase-04.7-05 schrieb "Password-Reset verdrahtet" in Summary — stimmte nie. Phase-04.13 schrieb "PreCall live in EWB" — stimmte nie. Phase-08.5 schrieb "FT-Logging aktiviert" — `finetune_logging.py` existiert nicht.

**Muster 3: Test-False-Greens.**
Tests prüfen Source-Presence statt Integration. Beispiel: QA-Pipeline-Tests bestätigen dass `log_pipeline_event` gerufen wird — nicht dass es tatsächlich in DB schreibt.

**Muster 4: Hardcoded Placeholder die nie ersetzt wurden.**
`generate_qa_response({}, _anrede, '', _user_id)` in claude_service.py. `redeanteil_berater=60` in learning.py. Beide wurden als "TODO: später echt" gebaut und nie angefasst.

**Muster 5: State-Mutations-Drift.**
`ls.state['mode']`, `ls.state['org_id']` werden gelesen aber nicht geschrieben. Writer-Funktion existierte mal, wurde umgebaut, State-Write wurde vergessen.

---

## 🔧 PRIORISIERTER FIX-PLAN

### Phase "Stabilisierung" (vor EA-Launch, ~20-30h)

**Block 1: Launch-Blocker-Fixes (~20h)**
1. LB-1 Password-Reset-Flow bauen — 3-4h
2. LB-2 DSGVO-Routen (Data-Export, Account-Delete, Consent-Withdraw, Portability) — 8-12h
3. LB-3 QA-Pipeline profile_data + confidence fixen — 1h
4. LB-4 Cost-Tracker user_id durchreichen — 2-3h
5. LB-5 + LB-6 `ls.state['org_id']` + `ls.state['mode']` in deepgram_service.py:351 setzen — 5 min
6. H-5 Training-PostCall Redeanteil echt berechnen — 2-3h
7. H-8 DSGVO-Audit-Events einbauen — 4-6h

**Block 2: Dead-Code-Prune + Struktur-Cleanup (~3h)**
8. H-3 `analysiere_mit_claude_streaming` löschen — 15 min
9. H-4 Entscheidung `_build_system_prompt` + `_get_erfolgsquoten`: LÖSCHEN (Felder nicht portieren — das ist Profil-Redesign-Thema) — 30 min
10. H-11 if/else in analyse_loop aufräumen, ANALYSE_INTERVALL-Doku fixen — 15 min
11. H-1 Entscheidung `finetune_logging.py` — entweder implementieren (4-6h) oder alle log_pipeline_event-Calls removen und DB-Tabelle droppen (1h). Empfehlung: removen für EA, später gezielt implementieren.
12. H-6 `generate_postcall_analysis` profile_data verdrahten — 1-2h
13. H-10 `_parse_json` Logging — 30 min

### Phase "Härtung" (nach EA-Start, ~20-25h)

14. H-2 PreCall-Briefing Entscheidung: re-wire in EWB (3-4h) oder deprecaten
15. H-7 Keyword-Matcher Race-Fix — 3-4h
16. H-9 Deepgram-Cost-Berechnung — 2-3h
17. Alle MEDIUM-Punkte nach Priorität angehen — ~10-15h

### Phase "Profil-Redesign" (separat, wie geplant)

18. Phase-A-Audit als Input
19. Phase-B (Sales-Literatur-Research)
20. Phase-C (Schema + Integration-Map neu)
21. Re-Implementation der toten Felder (nogos, wettbewerber, uebergaenge, kaufsignale, etc.) in `build_profile_context`

---

## 📋 NACH-TEIL — Claudian direkt gelesen (15:40-16:40)

### config.py, database/db.py, database/models.py (komplett), app.py (strukturell), app_routes.py (kritische Pfade)

**Neue Launch-Blocker-Kandidaten:**

### LB-7: Error-Handler leakt Traceback an Client

**Evidence:** `app.py:1697-1726`. Sowohl `@app.errorhandler(500)` als auch `@app.errorhandler(Exception)` returnen 1000 Chars Traceback als JSON (`tb_str[-1000:]`) oder volle Traceback als plain/text bei non-JSON-Requests.

**Folge:** Angreifer kann durch fehlerhafte Requests Server-Code, Dateipfade, DB-Schema auslesen. Stack-Traces enthüllen Logik-Details.

**Fix:** Traceback nur loggen (print OK), an Client generische Message. Prod-Check über `not FLASK_DEBUG`.

**Fix-Aufwand:** 30 min.

### LB-8: Multi-Worker-Kostenexplosion-Risiko

**Evidence:** `app.py:1776-1777`:
```python
threading.Thread(target=analyse_loop, daemon=True).start()
threading.Thread(target=coaching_loop, daemon=True).start()
```
Bei jedem App-Start werden analyse_loop + coaching_loop gestartet. Bei Multi-Worker-Deployment (Gunicorn) → n-fach Loops → n-fach Claude-API-Calls parallel. Single-worker ist aktueller Modus (SocketIO-threading), aber explizit nicht gegen Skalierung geschützt.

**Fix:** Worker-Guard (nur Master-Worker startet Loops) oder dedizierter Background-Worker. Vor horizontaler Skalierung Pflicht.

**Fix-Aufwand:** 2-3h.

### Neue HIGH-Severity-Befunde

**H-12: Zwei inline-Anthropic-Routes ohne Cost-Tracking**
- `/api/frage` (`app_routes.py:1118-1160`) und `/api/ewb_trigger` (`:1163-1272`) erstellen jeweils **eigene** `anthropic.Anthropic`-Clients pro Request (nicht wie alle anderen Pfade den globalen `claude_service.claude_client`).
- **Kein `log_api_cost`** in beiden — diese Claude-Calls sind unsichtbar im Founder-Cost-Dashboard.
- Hardcoded `claude-haiku-4-5-20251001` in beiden Routes — **zusätzlich zu den 9 Stellen in claude_service.py** (jetzt 11 total).
- Fix: ~1h (Cost-Hook + geteilter Client).

**H-13: Profil-Feld-Lese-Drift in Routes-Prompts**
- `/api/frage` + `/api/ewb_trigger` lesen `pdata.get("produkt")` — **Top-Level-Key**.
- Aktuelles Profile-JSON-Schema hat aber `basis.produktbeschreibung` (Phase-08-Schema).
- Folge: `profile_ctx` ist meistens leer an Claude → beide Routes operieren effektiv ohne Produkt-Kontext.
- **Dasselbe Muster wie LB-3** (leeres profile_data in QA-Pipeline).
- Fix: 30 min.

**H-14: Duplicate Logging für EWB-Clicks**
- `/api/ewb_trigger` ruft sowohl `record_ewb_click()` als auch `FtObjectionEvent`-INSERT parallel — zwei verschiedene Logging-Wege für dasselbe Event.
- Fix: ~1h (einen Pfad behalten, nicht beide).

**H-15: Error-Response-Leaks in API-Routes**
- `jsonify({'error': str(e)})` in `/api/frage:1160` und `/api/ewb_trigger:1272`. Exception-Message direkt an Client.
- Weniger schlimm als LB-7 (kein Stack-Trace), aber zusätzliche Angriffs-Surface.
- Fix: zusammen mit LB-7.

### Neue MEDIUM-Befunde

- **CORS_ORIGIN Domain-Drift** — `config.py:13` fallback `'https://nerve.app'`, echte Domain ist `getnerve.app`. Fix: 1 min.
- **PLANS identisch** — Starter/Pro/Business haben alle `max_users:1, minuten_limit:1000, training_voice_limit:50`. Rabatt ohne Mehrwert — absichtlich oder Bug? Klären.
- **`Organisation.plan` Kommentar-Drift** — Model sagt "starter/team/business/enterprise", config.py hat "starter/pro/business". Doku-Lüge intern.
- **`Organisation.max_users` default 5** in Model, aber config.py PLANS haben alle `max_users:1`. Default widerspricht Plan-Lookup.
- **`PromptVersion.is_default` Dead Column** — Phase-08-D-26 designed, aber `prompt_pipeline.resolve_prompt_version` ignoriert es, nutzt `user_id % len(variants)`.
- **`Feedback` vs. `FeedbackEvent` Parallelismus bestätigt** — zwei Tabellen im Schema (Z.197 + Z.401). `/api/feedback` schreibt in `FeedbackEvent`, `feedback_service` nutzt `Feedback`.
- **`ConversationLog.precall_briefing` Column** existiert — wird geschrieben bei Session-Ende (vermutet, zu verifizieren in api_beenden), aber von keinem Live-Pfad gelesen → Dead-Data-Path-Verstärkung.
- **Ad-hoc-Migrations-System in `app.py:_migrate`** — manuelle ALTER TABLE mit try/except pass. Keine alembic-Versionierung. Risiko bei zukünftigen Schema-Änderungen.

### Blueprint-Registrierung verifiziert

Alle 20 Blueprints sauber registriert in app.py Z.1640-1659. Analyse-Loop + Coaching-Loop als Daemon-Threads gestartet Z.1776-1777 (s. LB-8).

### `ls.state['ewb_top2']` Orphan-Reader direkt bestätigt

`app_routes.py:145`: `'ewb_top2': ls.state.get('ewb_top2'),  # legacy (may be None post-04.8)` — der Reader existiert in `/api/ergebnis`-Polling-Response, mit "legacy"-Kommentar. Welle-1-Befund damit nochmal verifiziert.

---

## 🕐 NOCH OFFEN — wartet auf 19:20 Rate-Limit-Reset

**Routes (15/20 noch ungescannt):**
- `app_routes.py` (1462 Z.) — nur kritische Pfade gelesen, Rest offen
- `profiles.py` (577 Z.), `training.py` (1331 Z.), `coach.py` (279 Z.)
- `dashboard.py` (988 Z.), `admin_dashboard.py` (878 Z.), `admin_views.py` (232 Z.)
- `organisations.py` (133 Z.), `payments.py` (334 Z.), `performance.py` (472 Z.)
- `feedback.py` (67 Z.), `onboarding.py` (212 Z.), `changelog.py` (100 Z.)
- `logs_routes.py` (46 Z.), `waitlist.py` (153 Z.), `oauth.py` (241 Z.), `settings.py` (223 Z.)

**Frontend (0% gescannt):**
- `static/app.js` (2125 Z.), `static/pip-launcher.js` (2315 Z.) — die zwei großen
- `static/profile_editor.js` (460 Z.), andere kleinere
- 27 Templates (HTML)

**Tests (0% gescannt):**
- 35 Test-Dateien
- Coverage-Check + False-Green-Identifikation (wie viele prüfen Source-Presence statt Integration)

**Verdachts-Hypothesen die Welle 3-5 noch klären muss:**
1. Weitere hardcoded-empty-profile-Patterns in Routes?
2. Weitere `pdata.get("produkt")`-Schema-Drifts in anderen Routes?
3. DSGVO-Rechte-Routen in irgendeinem ungescannten Blueprint versteckt? (unwahrscheinlich, legal.py geprüft)
4. Stripe-Payment-Webhook-Handler sicher gegen Replay? (payments.py offen)
5. OAuth-State-Parameter CSRF-Schutz? (oauth.py offen)
6. Frontend-Kopplung: welche `/api/`-Calls werden von welchem JS getriggert? Welche Routes sind dead weil Frontend sie nie aufruft?
7. Test-False-Greens: wie viele der 35 Tests prüfen tatsächlich Integration vs. nur Source-Presence?

---

## 📊 Gesamt-Health-Score

Gemessen an: Launch-Readiness, Datenintegrität, DSGVO-Konformität, Dead-Code-Dichte

| Dimension | Status | Kommentar |
|---|---|---|
| **Core-EWB-Pipeline** | 🟡 Funktioniert aber nudelig | EWB läuft, aber nur ~21% Profil-Integration |
| **QA-Pipeline (08.5)** | 🔴 De facto kaputt | Leeres profile_data macht Tabu wirkungslos |
| **PreCall** | 🔴 Feature-Fake | Output wird nirgends konsumiert |
| **FT-Logging** | 🔴 Nicht existent | Modul fehlt im Repo |
| **Cost-Tracking** | 🔴 Multi-User-Horror | Falsche User-Zuordnung + NULL org_id |
| **Auth** | 🟠 Password-Reset fehlt | Launch-Blocker |
| **DSGVO** | 🔴 Rechte nicht implementiert | Abmahn-Risiko |
| **Training** | 🟡 Coach lügt mit Fake-Redeanteilen | |
| **Live-Analysis-Loop** | 🟢 Solide Thread-Architektur | Locks sauber |
| **Keyword-Matcher** | 🟡 Race-Condition-Risiko | Funktioniert meistens |
| **Doku-Integrität** | 🔴 Systematisch optimistisch | Code ≠ Doku |

---

## 🎯 Top-3-Message an André

1. **Kein DACH-EA-Launch vor Password-Reset + DSGVO-Routen + QA-Tabu-Fix.** Das sind 3 Blöcke = ~15-20h. Ohne die geht nix raus.

2. **Die Doku-Lügen sind das eigentliche Gift.** Jede Phase hat zukünftige Claudian-Sessions beruhigt ("Feature X ist live") während Code was anderes sagte. Fix-Regel für die Zukunft in [[CLAUDE.md]] verankern: **"Phase-Closeout braucht Live-Path-Verifikation, nicht Handoff-Check."**

3. **Profil-Schema-Redesign ist NICHT die dringende Arbeit.** Die Prompt-Integration-Kaputtheit ist Infrastruktur-Problem, nicht Schema-Problem. Erst die Infrastruktur reparieren (Block 1+2 = ~23h), dann das Schema neu designen (Phase B+C).

---

*Stand-Tag: 2026-04-24, 15:40. Weiter-Scan ab 19:20 (Rate-Limit-Reset) mit Welle 3 (Routes) + Welle 4 (Frontend+DB+Config) + Welle 5 (Tests).*
