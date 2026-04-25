---
audit: deep-dive-claude-service
erstellt: 2026-04-24
datei: services/claude_service.py (1666 Zeilen)
autor: Claudian (Vault)
methode: Code-komplett gelesen + Call-Graph-Grep (*.py gesamt-codebase) + Cross-Check gegen CONCERNS.md + profil-prompt-integration-matrix.md
---

# Deep-Dive: claude_service.py

## TL;DR

Das Modul ist der zentrale Claude-API-Orchestrator: 16 Top-Level-Funktionen, 7 Claude-API-Call-Stellen (alle Haiku-4-5-20251001, keine Sonnet-Calls hier drin). Zwei große Threads (`analyse_loop`, `coaching_loop`) sind die Herzstücke. **Bestätigte tote Funktionen:** `_build_system_prompt` (265-401, 136 Zeilen) + `_get_erfolgsquoten` (206-262, 57 Zeilen) — zusammen **~193 Zeilen toter Code**, nur indirekt aus `_build_system_prompt` gerufen, das seinerseits tot ist. **Neue Findings über CONCERNS.md hinaus:** (1) `_get_erfolgsquoten` als Zombie-Funktion (nirgends in CONCERNS.md erwähnt); (2) Schema-Inkonsistenz in der Profil-Lesung (`techniken` vs. `techniken_aktiv`/`techniken_verboten` — Audit-Matrix benutzt flache Namen, Code benutzt Nested-Access); (3) `_parse_json` ist rudimentär (nur `{...}` — kein Array-Support, kein Nested-Escape-Fix); (4) 2 Warn-Prints über leeren `user_id` zeigen latenten A/B-Routing-Bug; (5) Cost-Tracker erhält konsistent `user_id=None` — Org-Quoten ungenau; (6) `ANALYSE_INTERVALL=4s` (config.py Z37), CONCERNS.md schreibt 2s — Doku-Drift.

## Call-Graph (alle Top-Level-Funktionen)

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `get_active_prompt_version` | 107 | `_write_ft_assistant_event` (selbe Datei Z.195) + `routes/app_routes.py:1240/1262` (objection_trigger FT-log) | LIVE | Cache für 5 Non-EWB-Module. Legacy laut Kommentar Z.8-10, aber nach wie vor live genutzt. |
| `_write_ft_assistant_event` | 125 | `analyse_loop:1139`, `coaching_loop:1654`, `analysiere_mit_claude_streaming:794` + Tests | LIVE | FT-Logging in DB. Silent-Fail by design. |
| `_get_erfolgsquoten` | 206 | NUR `_build_system_prompt:383` (welcher selbst tot ist) | **DEAD (Zombie)** | **Nicht in CONCERNS.md!** 57 Zeilen DB-Query + String-Build, werden niemals live konsumiert. Zombie-Code unter Zombie-Code. |
| `_build_system_prompt` | 265 | NUR Tests (`tests/test_claude_service_phase08.py:82` asserts existence + absence-from-active-paths). Kein Live-Aufruf. | **DEAD** | Bestätigt CONCERNS.md + Matrix-Audit. `system=_build_system_prompt()` in Codebase-Suche: 0 Live-Treffer (nur Test-Assertions die verbieten). |
| `_build_coaching_prompt` | 404 | `analysiere_coaching:1017` → `coaching_loop:1573` (Thread) | LIVE | Indirect Live via coaching_loop. |
| `_parse_json` | 463 | `analysiere_mit_claude:701`, `analysiere_mit_claude_streaming:774`, `analysiere_coaching:1036`, `services/qa_pipeline.py:312` (Cross-Modul-Import) | LIVE | Cross-Modul. Rudimentär — sucht nur `{` und `}`, kein Array-Support. |
| `classify_phase` | 514 | `analyse_loop:1167` | LIVE | Haiku-Call, alle 5 Zyklen. |
| `infer_customer_state` | 591 | Parameter an `ki_logik.infer_cold_call_context` via `analyse_loop:1233` (`haiku_caller=infer_customer_state`) | LIVE | Cold-Call-only (ls.state['mode']=='cold_call'). |
| `analysiere_mit_claude` | 647 | `analyse_loop:1077/1079` (beide Branches identisch!) + `routes/app_routes.py:179` (`/api/analyse_line` POST) | LIVE | **Finding:** Z.1077 und Z.1079 sind identisch (if/else-Branches — toter if-Zweig, siehe Findings). |
| `analysiere_mit_claude_streaming` | 704 | NICHT aufgerufen in aktiver Codebase — nur Tests referenzieren es | **DEAD / Test-Only** | **Neues Finding.** Phase 06.3 hat analyse_loop auf non-streaming zurückgeführt (Z.1073 Kommentar). Streaming-Variante bleibt als Dead Code ~100 Zeilen. Tests (`test_claude_service_phase08.py:50`) verifizieren nur dass die Funktion die Pipeline nutzt, nicht dass sie aufgerufen wird. |
| `streame_auto_variante` | 808 | `services/deepgram_service.py:140-144` (Keyword-Matcher → sio.start_background_task) | LIVE | Parallel-Pfad für Slot 1 bei Keyword-Trigger. |
| `streame_manual_ewb_variante` | 897 | `services/deepgram_service.py:445-449` (Manual-EWB-Button-Klick-Socket-Handler) | LIVE | Hardcoded Coach-Prompt (bestätigt CONCERNS.md) — kein Profil-Kontext. |
| `analysiere_coaching` | 1006 | `coaching_loop:1573` | LIVE | Via `_build_coaching_prompt` (separater Pfad von EWB). |
| `analyse_loop` | 1039 | `app.py:1773/1776` (Thread-Start bei App-Boot) | LIVE | Main analysis thread. |
| `_qa_load_tabu` | 1342 | `_qa_pipeline_dispatch:1456` (selbe Datei) | INTERNAL (Live via dispatch) | Phase 08.5 helper. |
| `_qa_load_faqs` | 1381 | `_qa_pipeline_dispatch:1500` (selbe Datei) | INTERNAL (Live via dispatch) | Phase 08.5 helper. |
| `_qa_pipeline_dispatch` | 1405 | `analyse_loop:1083` + Tests | LIVE | Universal Response Loop Phase 08.5. |
| `coaching_loop` | 1543 | `app.py:1774/1777` (Thread-Start bei App-Boot) | LIVE | Parallel coaching thread. |

**Summary:**
- LIVE: 13 Funktionen
- DEAD: 2 (`_build_system_prompt`, `analysiere_mit_claude_streaming`)
- ZOMBIE: 1 (`_get_erfolgsquoten` — wird von DEAD-Code gerufen)
- TEST-ONLY: 0 (alle Tests prüfen Live-Funktionen oder Symbol-Präsenz)

## Claude-API-Calls (7 Stellen)

| Zeile | Funktion | Model | max_tokens | System-Prompt Quelle | User-Msg Quelle | Cost-Tracker? | Dead? |
|---|---|---|---|---|---|---|---|
| 527 | `classify_phase` | haiku-4-5 | 60 | Inline Template `PHASE_CLASSIFIER_PROMPT` (hardcoded Z.489-511) | Formatted transcript window + state | ✅ `context_tag='phase_classify'`, user_id=None | LIVE |
| 599 | `infer_customer_state` | haiku-4-5 | 120 | Inline Template `COLDCALL_INFER_PROMPT` (hardcoded Z.574-588) | Formatted seller_transcript + phase | ✅ `context_tag='coldcall_infer'`, user_id=None | LIVE |
| 679 | `analysiere_mit_claude` | haiku-4-5 | 400 | `build_ewb_prompt(profile_data=None, anrede, version, user_id)` → EWB-Pipeline | kontext + neuer_text | ✅ `context_tag='live_haiku'`, user_id=None | LIVE |
| 749 | `analysiere_mit_claude_streaming` | haiku-4-5 | 400 | `build_ewb_prompt(...)` (gleich wie oben) | kontext + neuer_text | ✅ `context_tag='pip_stream'`, user_id=None | **DEAD Call-Site** |
| 857 | `streame_auto_variante` | haiku-4-5 | 200 | **Hardcoded** `"Du bist ein erfahrener Sales-Coach im DACH-B2B..."` | profile_einwaende (Top-10) + kontext + neuer_text | ✅ `context_tag='pip_autovar'`, user_id=None | LIVE |
| 945 | `streame_manual_ewb_variante` | haiku-4-5 | 250 | **Hardcoded** `"Du bist ein erfahrener Sales-Coach..."` | `profile_einwand.gegenargument_1` + kontext | ✅ `context_tag='pip_variante'`, user_id=None | LIVE |
| 1014 | `analysiere_coaching` | haiku-4-5 | 200 | `_build_coaching_prompt()` | segmente + kontext | ✅ `context_tag='coaching_haiku'`, user_id=None | LIVE |

**Kritische Beobachtungen:**
1. **ALLE 7 Calls nutzen `user_id=None`** im cost_tracker (Z.692, 785, 877, 539, 611, 981, 1027). Kein User-spezifisches Cost-Tracking — schwächt Fair-Use-Quoten und Post-Launch-Billing-Analyse.
2. **3 Pfade hardcoden System-Prompts** direkt im Code (Z.860, 948, + `PHASE_CLASSIFIER_PROMPT` Z.489, `COLDCALL_INFER_PROMPT` Z.574). Keine DB-backed Prompt-Versioning, kein A/B-Routing. Prompt-Versioning-Infrastruktur (Phase 04.7.1 + 08) wird also nicht konsistent genutzt.
3. **Zwei hardcoded System-Prompts sind wörtlich identisch** (Z.860 und Z.948 — `streame_auto_variante` und `streame_manual_ewb_variante`). Dupliziert, kein Modul-Konstante.
4. **Phase 08.5 QA-Pipeline-Calls laufen nicht hier**, sondern in `services/qa_pipeline.py`. `_qa_pipeline_dispatch` ruft sie zwar auf, aber die Claude-API-Calls selbst sind extern (abgedeckt durch Cross-Modul-Audit).

## ls.state-Zugriffe

Alle Zugriffe sind **unter Lock** (state_lock, pause_lock, kb_lock, buffer_lock, coaching_lock, log_lock, gegenargument_log_lock, _bof_lock, painpoints_lock, phasen_log_lock, phase_lock, covered_phases_lock). Keine Lock-losen Writes gefunden.

| Feld | Operation | Funktion (Zeile) | Lock |
|---|---|---|---|
| `ft_session_id` | read | `_write_ft_assistant_event:148` | state_lock ✅ |
| `mode` | read | `_write_ft_assistant_event:149`, `analyse_loop:1165/1226` | state_lock ✅ |
| `user_id` | read | `_write_ft_assistant_event:150`, `analysiere_mit_claude:665`, `...streaming:734`, `_qa_pipeline_dispatch:1423` | state_lock ✅ |
| `market`, `language`, `kaufbereitschaft` | read | `_write_ft_assistant_event:151-153` | state_lock ✅ |
| `precall_briefing` | read | `_build_system_prompt:387` | **NO LOCK** ⚠️ (in dead code — egal, aber Pattern-Smell) |
| `aktives_skript_inhalt`, `skript_bloecke` | read | `_build_system_prompt:393/394` | state_lock ✅ (nur in dead code) |
| `active_learning_cards` | read | `analyse_loop:1060` | state_lock ✅ |
| `aktiv` | write | `analyse_loop:1068/1128/1333` | state_lock ✅ |
| `active_sid` | read | `analyse_loop:1071`, `_qa_pipeline_dispatch:1426` | state_lock ✅ |
| `ergebnis`, `line_id`, `version` | write | `analyse_loop:1126-1129/1331-1334` | state_lock ✅ |
| `kaufbereitschaft` | write | `analyse_loop:1130/1320/1335`, `coaching_loop:1587` | state_lock ✅ |
| `current_phase`, `current_phase_name`, `phase_changed_at`, `phase_change_count`, `_phase_cycle_at_last_change`, `phase_confidence` | write | `analyse_loop:1180-1186` | state_lock ✅ |
| `cold_call_inference` | write | `analyse_loop:1236` | state_lock ✅ |
| `score_factors_seen`, `readiness_score`, `readiness_bucket`, `active_hint`, `ewb_buttons` | write | `analyse_loop:1317-1322` | state_lock ✅ |
| `last_einwand_typ` | read/write | `analyse_loop:1310/1313` | state_lock ✅ |
| `kw_fired_for_line` | read | `_qa_pipeline_dispatch:1422` | state_lock ✅ |
| `session_anrede` | read | `analysiere_mit_claude:666`, `...streaming:735`, `_qa_pipeline_dispatch:1424` | state_lock ✅ |
| `slot1_variant_busy_until` | read/write | `_qa_pipeline_dispatch:1425/1479` | state_lock ✅ |
| `active_profile_id` | read | `_qa_pipeline_dispatch:1427` | state_lock ✅ |

**Keine Orphan-Writer oder Orphan-Reader gefunden in dieser Datei.** Alle lesen/schreiben in Paaren. Der CONCERNS.md-Fund `ewb_top2` liegt außerhalb dieser Datei (live_session.py Writer in Reset-Funktion, Reader nur in app_routes.py — nicht hier).

## Verdachts-Stellen

### TODOs/FIXMEs
- **Keine** TODO/FIXME/XXX/HACK in der gesamten Datei. (Grep = 0 matches.)

### "Legacy"-Indikatoren (alle geprüft)
- Z.7-10: Phase 08-Doku-Kommentar — besagt `_build_system_prompt` sei "Legacy". **Stimmt, aber Unterschätzung — _build_system_prompt ist NICHT nur Legacy, sondern komplett DEAD.** Die dort zitierten "4 anderen Module" (assistant_live, coaching_live, objection_trigger, api_frage, training_persona) nutzen `_build_system_prompt` ebenfalls NICHT direkt — sie nutzen eigene Templates (siehe CONCERNS.md und Matrix-Audit Pfade 11-12, Training-Pfad via training_service.py). Der Kommentar ist **irreführend** und sollte aktualisiert werden.
- Z.654-660: Phase 08-Kommentar in `analysiere_mit_claude` — inhaltlich korrekt.
- Z.1320: `'kaufbereitschaft' = score_p4  # legacy mirror (RESEARCH Q2 R2)` — dokumentiert, OK.

### Silent Failures (except ohne Logging, nur Re-Assignment)
- **Z.119**: `except Exception: version = 'unknown'` — FT-Logging-Fallback in `get_active_prompt_version`. Silent, aber by design (DB-Unavailability darf FT-Writes nicht blocken). Akzeptabel.
- **Z.172**: `except Exception: return None` — in `_write_ft_assistant_event._jdump`. Silent JSON-Failure. Akzeptabel für Logging-Pfad.
- **Z.223**: `except Exception: continue` — in `_get_erfolgsquoten` (DEAD). Egal.
- **Z.472**: `except json.JSONDecodeError: return {}` — `_parse_json`. **Silent Failure in Hot-Path!** Jeder API-Response der invalides JSON zurückgibt ergibt leer-dict `{}`, das nach außen wie "kein Einwand" aussieht. Wird nicht gelogt. → LOW-MEDIUM Risiko: bei Haiku-Outages mit kaputtem JSON verschwinden EWBs unauffällig.
- **Z.1301**: `except Exception: base_buttons = None` — Profile-Load-Failure fällt auf None. Kein Logging. → Wenn Profil-DB zickt, verschwinden Buttons still.
- **Z.1453**: `except Exception: _profile_daten = {}` — QA-Pipeline-Profile-Load-Failure. Kein Logging.
- **Z.1605**: `except Exception: pass` — Speech-Stats-Fallback in `coaching_loop`. Silent, aber OK (Behavioral-Tips sind Best-Effort).

### Auskommentierter Code
- Z.476-478: "rank_ewb / EWB-Ranking Haiku call REMOVED per Phase 04.8 D-08 + user override." — **Kommentar-Grab** für entfernte Funktion. 3 Zeilen. Sauber dokumentiert. OK.
- Z.1637-1643: Coaching-WebSocket-Emit entfernt (Phase 06.6). 7 Zeilen Kommentar-Grab. Sauber dokumentiert. OK.

### Hardcoded Werte die konfigurierbar sein sollten
- **7x wörtlich `'claude-haiku-4-5-20251001'`** (Zeilen 528, 600, 680, 750, 858, 946, 1015, 1143, 1658). Kein Modell-Wrapper, kein Config-Einstieg. Bei Model-Wechsel: 9 Edit-Stellen.
- **PHASE_CLASSIFIER_PROMPT + COLDCALL_INFER_PROMPT** (Z.489 + 574) hardcoded als Modul-Konstanten, nicht DB-backed. Inconsistent mit Phase 04.7.1-Prompt-Versioning-Architektur für andere Module (`assistant_live`, `ewb`, etc.).
- **2 hardcoded System-Prompts** "Du bist ein erfahrener Sales-Coach im DACH-B2B..." in Z.860 + Z.948 — **wörtlich identisch**, nicht als Konstante extrahiert.

### Duplicate Branch (if/else identisch)
- **Z.1070-1079**: 
  ```python
  if active_sid:
      ergebnis = analysiere_mit_claude(neuer_text, kontext)
  else:
      ergebnis = analysiere_mit_claude(neuer_text, kontext)
  ```
  Beide Zweige sind identisch. Der Phase 06.3-Kommentar sagt "analyse_loop no longer renders into PiP slots" → der if-Zweig wurde früher für streaming genutzt, ist jetzt aber merged. **Tote if/else-Struktur** — kann zu `ergebnis = analysiere_mit_claude(neuer_text, kontext)` vereinfacht werden. Cleanup-Kandidat.

### Divergenz Doku vs. Code
- **ANALYSE_INTERVALL**: CONCERNS.md Z.181 schreibt "runs every 2 seconds per config.py". **config.py Z.37: `ANALYSE_INTERVALL = 4`** (Phase 06.3 Änderung). Doku-Drift in CONCERNS.md.
- **`_build_system_prompt` als "intentional legacy stub"** (CONCERNS.md Z.13-28): Der Code hat inzwischen auch `_get_erfolgsquoten` (57 Zeilen, Z.206-262) als Zombie, wird **nur von `_build_system_prompt` gerufen**. CONCERNS.md erwähnt dies nicht. → 193 Zeilen tot, nicht "nur 265 Zeilen".
- **`analysiere_mit_claude_streaming` aufgerufen?** CONCERNS.md impliziert Z.1039-1340 blocke auf streaming-Call. Tatsächlich: `analyse_loop` ruft seit Phase 06.3 die **non-streaming** Variante (Z.1077/1079). Streaming-Variante hat keinen Live-Caller in der aktuellen Codebase (nur Tests). → Performance-Aussage in CONCERNS.md Z.180-186 ist auf Basis veralteter Annahme.

### ARCHITECTURE.md-Hypothese widerlegt
Die Aufgabenstellung warnt: ARCHITECTURE.md behauptet "PreCall in EWB injiziert" — **stimmt nicht**.
- `analysiere_mit_claude:647-701` und `analysiere_mit_claude_streaming:704-805` rufen `build_ewb_prompt(profile_data=None, ...)` mit **explizit `profile_data=None`** — das baut Profil-Kontext intern via user_id-Lookup.
- Weder `ls.state.get('precall_briefing')` noch PreCall-Daten tauchen in den EWB-Call-Pfaden auf. Nur `_build_system_prompt:387` (DEAD) liest PreCall.
- **→ Matrix-Audit und CONCERNS.md haben recht, ARCHITECTURE.md lügt.**

## Phase 08/08.5 Integration-Check

**`build_ewb_prompt` wird korrekt gerufen?** ✅
- Z.673 (in `analysiere_mit_claude`): `build_ewb_prompt(profile_data=None, anrede=_anrede, version=_ewb_version, user_id=_user_id)` — korrekte Signatur.
- Z.742 (in `analysiere_mit_claude_streaming`): identischer Aufruf. (Aber Funktion ist DEAD.)
- Nicht in `streame_auto_variante` (Z.860 hardcoded) und nicht in `streame_manual_ewb_variante` (Z.948 hardcoded) — **2 Live-Pfade umgehen die Pipeline bewusst.**

**`resolve_prompt_version` immer vor `build_ewb_prompt`?** ✅ in den 2 Pfaden die sie benutzen (Z.672 + Z.741). Korrekt.

**Tabu-System integriert?** ✅ in `_qa_pipeline_dispatch` (Z.1456, 1493, 1505, 1533). Lädt Tabu-Liste aus Profil und wendet `apply_tabu_filter` auf generierte Antworten. Bei Treffer → `_emit_soft_hint(reason='tabu_filtered')`. Sauber.
- ⚠️ **Tabu-Block fehlt in `streame_auto_variante` und `streame_manual_ewb_variante`.** Die hardcoded Coach-Prompts können Tabu-Wörter ungefiltert ausspielen. → Korreliert mit CONCERNS.md-Finding zu Manual-Button (kein Profil-Kontext).

**QA-Pipeline-Dispatch sauber?** ✅ Dispatch-Logik in `_qa_pipeline_dispatch` (Z.1405-1540) ist robust:
- D-02 Guard (kw_fired_for_line) ✅
- Slot-1-Mutex ✅
- Try/Except wrappt alles (MUST NOT raise) ✅
- Classify → Unknown/Frage Routing ✅
- FAQ-Match Fallback ✅
- Confidence-Threshold ✅
- Soft-Hint Fallback-Codes (6 reasons: low_confidence, empty_response, tabu_filtered, tabu_filtered_faq, no_faq_low_conf, no_faq_empty, no_faq_tabu) ✅

Aber: CONCERNS.md und Matrix-Audit decken Profil-Kontext-Mangel im QA-Pipeline bereits ab. Hier bestätigt: `_qa_pipeline_dispatch` übergibt nur `_anrede` und Tabu-Liste an `generate_qa_response(neuer_text, 'einwand_unknown', {}, _anrede, '', _user_id)` — das leere Dict und der leere String sind Placeholder wo Profil-Kontext hin sollte.

## Findings — Severity-sortiert

### HIGH

**H1. `_get_erfolgsquoten` Zombie-Funktion unter Zombie-Code (NEU — nicht in CONCERNS.md).**
- Location: Z.206-262 (57 Zeilen inkl. DB-Query auf ConversationLog mit 50-Row-Limit)
- Caller: NUR `_build_system_prompt:383`. `_build_system_prompt` selbst ist tot. → Transitiv tot.
- Impact: Code macht DB-Query-Infrastruktur (ConversationLog-Scan für Gegenargument-Erfolgsquoten), die nie konsumiert wird. Läuft niemals. Ballast + verwirrt Entwickler die annehmen "Lern-Loop ist aktiv".
- Recommendation: Entweder mit `_build_system_prompt` zusammen entfernen, oder in `build_profile_context` / `build_ewb_prompt` re-integrieren (wäre wertvoll — wir haben reale Gegenargument-Erfolgs-Telemetrie, die niemand nutzt).

**H2. `analysiere_mit_claude_streaming` ist ein toter Call-Site (NEU — CONCERNS.md nennt es als Performance-Bottleneck).**
- Location: Z.704-805 (102 Zeilen)
- Caller: Kein Live-Aufruf in der Codebase (nur Tests). `analyse_loop:1077/1079` ruft die **non-streaming** Variante `analysiere_mit_claude`.
- Impact: (1) Phase 06.3-Intent ("keyword-matcher ist Primary für Slot 0 + Slot 1") hat die Streaming-Pipeline entwertet, aber Code wurde nicht entfernt. (2) CONCERNS.md Performance-Kritik basiert auf Annahme dass analyse_loop streaming callt — diese Analyse ist veraltet. (3) 102 Zeilen toter Code inkl. `on_einwand_detected`-Early-Callback, Stream-Token-Emission, Regex-basierter Callback-Logik — alles ungenutzt.
- Recommendation: Entweder Streaming-Variante wiederverwenden (wenn Slot-0-Streaming-UX gewünscht) oder entfernen. **Dringend klären mit André bevor geändert wird** — könnte Teil eines Feature-Plans sein den der Reset nicht mitreißt.

**H3. `streame_auto_variante` und `streame_manual_ewb_variante` umgehen Profil + Tabu + Prompt-Versioning.**
- Locations: Z.808-894 (auto) und Z.897-1003 (manual)
- Live-Pfade: Beide werden aus `deepgram_service.py` aufgerufen (Keyword-Match für auto, Button-Klick für manual).
- Impact: 
  - System-Prompt hardcoded + wörtlich identisch in beiden Funktionen (Z.860, Z.948). Keine Einheitlichkeit mit EWB-Pipeline.
  - Kein Tabu-Check auf Output → Tabu-Begriffe können ungefiltert ausgespielt werden.
  - Kein Prompt-Versioning → A/B-Tests auf diesen Pfaden unmöglich.
  - User sieht: Slot 0 (Profil-Gegenargument) hat Tabus korrekt, Slot 1 (Haiku-Variante) kann sie ignorieren. Inkonsistente UX.
- Recommendation: Einheitliches System-Prompt-Konstante extrahieren ODER über Pipeline-Wrapper leiten der Tabu-Check einbaut.

### MEDIUM

**M1. Alle cost_tracker-Calls nutzen `user_id=None`.**
- Locations: 7 Claude-Calls × je 2 cost_tracker-calls = 14 Stellen (alle mit `user_id=None`)
- Impact: Fair-Use-Quoten werden nicht user-spezifisch buchbar; Post-Launch-Abrechnung pro Tenant unmöglich; Kostenanomalie-Detection schwach.
- Recommendation: `user_id = ls.state.get('user_id')` lesen (ist bereits unter state_lock in 3 der 7 Funktionen verfügbar). In den 4 restlichen Funktionen (`classify_phase`, `infer_customer_state`, `streame_auto_variante`, `streame_manual_ewb_variante`) user_id aus ls.state injizieren.

**M2. Dupliziertes if/else in `analyse_loop` Z.1070-1079.**
- Beide Branches identisch. Kann zu einzelnem Statement vereinfacht werden. Leichte Verwirrung beim Lesen — wirkt wie "hier steht noch etwas was mal unterschiedlich war".

**M3. Silent Failure in `_parse_json` Z.472.**
- `except json.JSONDecodeError: return {}` ohne Logging. 
- Impact: Haiku liefert gelegentlich malformed JSON (besonders unter Last oder bei prompt-injection-artigen User-Inputs). Ergebnis: leer-dict → wird als "kein Einwand" interpretiert → EWB verschwindet still.
- Recommendation: `print(f"[parse_json] malformed: {raw[:200]!r}")` oder strukturiertes Logging einführen. Trägt zur Post-Launch-Debug-Telemetrie bei.

**M4. `classify_phase` und `infer_customer_state` hardcoden Prompt-Templates trotz vorhandener Prompt-Versioning-Infrastruktur.**
- `PHASE_CLASSIFIER_PROMPT` (Z.489-511) und `COLDCALL_INFER_PROMPT` (Z.574-588) sind Modul-Konstanten, nicht DB-backed.
- Impact: Diese Prompts können nicht A/B-getestet oder ohne Deploy geändert werden. Inconsistent mit Phase 04.7.1-Infrastruktur die für 5+ andere Module existiert (`prompt_versions`-Table).
- Recommendation: In `prompt_versions` seeden oder explizit dokumentieren warum nicht.

**M5. `_build_system_prompt` Schema-Inkonsistenz Profil-Felder (beobachtet im Legacy-Code).**
- Z.277: `techniken  = pdata.get('techniken', {})` — liest `techniken` als Dict.
- Z.360-366: Greift auf `techniken.get('verboten', [])`, `techniken.get('aktiv', [])`, `techniken.get('offene_fragen')`.
- **Matrix-Audit** spricht hingegen von `techniken_aktiv` / `techniken_verboten` / `offene_fragen` als **flache** Top-Level-Felder.
- → Entweder hat sich das Profil-Schema zwischen dead `_build_system_prompt` und aktiver `build_profile_context` geändert (wahrscheinlich), oder eine der beiden Seiten ist falsch. Relevant nur wenn `_build_system_prompt` re-aktiviert wird — für Redesign wichtig zu wissen.

**M6. Haiku-Model-Name 9x hardcoded als String-Literal.**
- Z.528, 600, 680, 750, 858, 946, 1015, 1143, 1658.
- Bei Model-Wechsel (z.B. Haiku-5) → 9 Edits nötig + Risiko dass eine Stelle vergessen wird.
- Recommendation: Konstante `LIVE_HAIKU_MODEL = 'claude-haiku-4-5-20251001'` am Modul-Kopf extrahieren.

### LOW

**L1. Doku-Drift: ANALYSE_INTERVALL = 4s (Code), CONCERNS.md sagt 2s.**
- Korrektur-Vorschlag für CONCERNS.md.

**L2. `_build_system_prompt` Z.387 liest `ls.state['precall_briefing']` ohne Lock.**
- Nur relevant in dead code. Aber wenn jemand die Funktion re-aktiviert: Race-Condition-Anfälligkeit.

**L3. Kommentar Z.8-10 ist irreführend.**
- "die 4 anderen Module... bleiben bewusst auf _ACTIVE_PROMPT_CACHE + _build_system_prompt (Legacy)" — **falsch**. `_build_system_prompt` wird von KEINEM der 5 Module mehr gerufen. `_ACTIVE_PROMPT_CACHE` wird für FT-Logging (`get_active_prompt_version`) genutzt, nicht für Prompt-Building. Kommentar aktualisieren.

**L4. `_build_coaching_prompt` liest PreCall nicht.**
- Nicht in Matrix-Audit explizit erwähnt — Coaching-Live-Pfad hat ebenso kein PreCall. Konsistent mit CONCERNS.md Befund. Low-Impact.

**L5. Coaching-Pfad hat keinen Tabu-Check.**
- `analysiere_coaching`/`_build_coaching_prompt` liest Tabu nicht. Coaching-Output wird aber onscreen NICHT angezeigt (Phase 06.6-Kommentar Z.1637-1643) — nur in FT-Log. Low-Impact, aber: FT-Trainingsdaten könnten Tabu-Wörter enthalten.

## Cross-Module-Hypothesen für Master-Audit

1. **`build_ewb_prompt` und `build_profile_context` (prompt_pipeline.py + ewb_pipeline.py):** Was liest `build_profile_context` tatsächlich? Matrix-Audit sagt "nur ~10 Felder". **Master-Audit muss prompt_pipeline.py:180-250 + ewb_pipeline.py komplett prüfen** um zu bestätigen welche Profil-Felder wirklich ankommen. Dort entscheidet sich ob H1 (`_get_erfolgsquoten`) reintegriert werden kann.

2. **Routes vs. claude_service Coupling:** `routes/app_routes.py:179` ruft `analysiere_mit_claude` direkt (synchron über `/api/analyse_line`-POST). Das bypassed den `analyse_loop`-Thread + bypassed das `_qa_pipeline_dispatch` + FT-Logging. **Master-Audit prüfen:** Wird dieser Pfad noch live aufgerufen von `static/app.js` oder ist er ebenfalls tot? Falls live: Button-Klick-Antwort läuft über EWB-Pipeline aber ohne FT-Log und ohne QA-Dispatch — Dokumentations-Lücke und evtl. Training-Data-Lücke.

3. **`_qa_pipeline_dispatch` → `qa_pipeline.generate_qa_response`:** Was genau landet im QA-System-Prompt? Matrix-Audit Pfad 4 sagt "nur Tabu + Anrede". **Master-Audit: qa_pipeline.py komplett verifizieren.**

4. **`ki_logik.compute_readiness_score`, `select_active_hint`, `dynamic_ewb_buttons`:** Diese 3 Funktionen werden in `analyse_loop:1243-1323` intensiv verwendet und bilden den neuen Readiness-Stack. **Master-Audit muss ki_logik.py prüfen**: (a) sind die Formeln robust? (b) woher kommen die Factor-Keys (`score_factors_seen`)? (c) was bestimmt `bucket == 'closing'`?

5. **Deepgram-Service ↔ claude_service Shared State:** `slot1_variant_busy_until` wird in 3 Callsites geschrieben (Deepgram-Keyword-Handler, streame_auto_variante-Trigger, _qa_pipeline_dispatch). Race-Conditions möglich? **Master-Audit: deepgram_service.py Z.130-150 + state_lock-Kontrakt prüfen.**

6. **Cost-Tracker user_id-None-Problem:** Wenn durchgängig user_id=None übergeben wird — wie wird Per-User-Cost überhaupt jemals gebucht? **Master-Audit: services/cost_tracker.py prüfen**: gibt es einen Fallback-Mechanismus via ls.state oder Flask-g, oder ist das ein systematisches Leak?

7. **`_build_system_prompt` Re-Aktivierung via feature flag?** Matrix-Audit Offene-Frage-1 fragt ob ein Pfad existiert den wir übersehen haben. **Master-Audit:** nach `SYSTEM_PROMPT_BASE` und Mock-/Test-Patterns greppen die evtl. conditional re-activaten.

---

**Meta:** Dieser Audit basiert auf 1-Datei-Deep-Read. Alle Claims mit Zeilenreferenzen sind direkt verifiziert. Claims die "Master-Audit" brauchen, sind explizit als Cross-Module-Hypothesen markiert.
