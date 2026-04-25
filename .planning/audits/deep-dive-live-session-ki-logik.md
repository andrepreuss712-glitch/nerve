---
audit: deep-dive-live-session-ki-logik
erstellt: 2026-04-24
dateien:
  - services/live_session.py (616 Zeilen)
  - services/ki_logik.py (204 Zeilen)
---

# Deep-Dive: live_session.py + ki_logik.py

## TL;DR

- **32 State-Keys** insgesamt in `ls.state` gefunden (13 init + 19 lazy-created). **2 ECHTE GHOSTS**: `mode` (read-only, nie geschrieben) + `org_id` (read-only, nie geschrieben). Plus 1 **orphan writer** (`ewb_top2` — nur reset, nirgends ein echter Wert-Write) und 1 **orphan reader** (`precall_briefing` — CONCERNS.md bestätigt: nicht in EWB-Prompt genutzt).
- **HINT_PRIORITY** (ki_logik.py:85) ist eine tote Konstante — nie importiert. Priority-Werte 1-5 sind in `claude_service.py:1269-1285` **hardcoded** stattdessen (Drift-Risiko).
- **Lock-Architektur ist solide**: 18 getrennte Locks + 1 monolithischer `state_lock` über 32 Felder (siehe CONCERNS.md — bekanntes Contention-Problem). Kein Deadlock-Risiko entdeckt (keine verschachtelten Lock-Acquires in beiden Dateien).
- **Unused Import**: `ANALYSE_INTERVALL` in live_session.py:9 — importiert, nie verwendet.
- **Nudelcode-Reste aus Phase 04.8**: `ewb_top2` nur als Reset-Artifact vorhanden, laut app_routes.py:145 Kommentar "legacy (may be None post-04.8)". Pruning übersehen.

---

## live_session.py

### State-Field-Matrix (ALLE Felder)

Legende: ✅ LIVE | ⚠️ ORPHAN | 💀 DEAD | 🧟 GHOST (read-only, nie geschrieben)

| Feld | Writer (Datei:Zeile) | Reader (Datei:Zeile) | Unter Lock? | Status |
|---|---|---|---|---|
| `version` | live_session.py:331 (reset), claude_service.py:1129 (+=), 1334 (+=) | app_routes.py:140 | ✅ state_lock | LIVE |
| `aktiv` | live_session.py:332, claude_service.py:1068, 1128, 1333 | app_routes.py:141 | ✅ state_lock | LIVE |
| `ergebnis` | live_session.py:333, claude_service.py:1126, 1331 | app_routes.py:142 | ✅ state_lock | LIVE |
| `line_id` | live_session.py:334, claude_service.py:1127, 1332 | app_routes.py:143, einwand_keyword_matcher.py:251 | ✅ state_lock | LIVE |
| `kaufbereitschaft` | live_session.py:335, claude_service.py:1130, 1320, 1335, 1587 | app_routes.py:144, claude_service.py:153 | ✅ state_lock | LIVE (legacy mirror of readiness_score) |
| `ewb_top2` | **live_session.py:336 (nur reset, kein echter Wert-Write)** | app_routes.py:145 | ✅ state_lock | ⚠️ **ORPHAN WRITER** (Phase 04.8 leftover — CONCERNS.md line 124 bestätigt) |
| `ewb_clicks` | live_session.py:399 (reset), 428 (setdefault.append) | app_routes.py:407, 564 | ✅ state_lock | LIVE |
| `current_phase` | live_session.py:338, claude_service.py:1180 | app_routes.py:147, 1197, claude_service.py:1162, 1227, 1250 | ✅ state_lock | LIVE |
| `current_phase_name` | live_session.py:339, claude_service.py:1181 | app_routes.py:148, 1198 | ✅ state_lock | LIVE |
| `phase_confidence` | live_session.py:340, claude_service.py:1186 | app_routes.py:149 | ✅ state_lock | LIVE |
| `phase_changed_at` | live_session.py:341, claude_service.py:1182 | **— kein Reader in Code** (nur gepollt in Frontend via /api/ergebnis?) | ✅ state_lock | ⚠️ WRITE-ONLY (nicht in app_routes.py:140-154 im Polling enthalten — prüfen ob Frontend das liest via anderem Key) |
| `phase_change_count` | live_session.py:342, claude_service.py:1183 | claude_service.py:1163 | ✅ state_lock | LIVE |
| `readiness_score` | live_session.py:343, claude_service.py:1318 | app_routes.py:150, 1199 | ✅ state_lock | LIVE |
| `readiness_bucket` | live_session.py:344, claude_service.py:1319 | app_routes.py:151, 1200 | ✅ state_lock | LIVE |
| `score_factors_seen` | live_session.py:345, claude_service.py:1317 | ki_logik.py:106, claude_service.py:1249 | ✅ state_lock | LIVE |
| `active_hint` | live_session.py:346, claude_service.py:1321 | app_routes.py:152 | ✅ state_lock | LIVE |
| `ewb_buttons` | live_session.py:347, claude_service.py:1322 | app_routes.py:153 | ✅ state_lock | LIVE |
| `cold_call_inference` | live_session.py:348, claude_service.py:1236 | app_routes.py:154, 1201, claude_service.py:1251 | ✅ state_lock | LIVE |
| `active_learning_cards` | live_session.py:214 (load), 219 (error), 349 (reset) | claude_service.py:1060 | ✅ state_lock | LIVE |
| `precall_briefing` | live_session.py:350 (reset), deepgram_service.py:309 | app_routes.py:273, claude_service.py:387 | ✅ state_lock | ⚠️ **DEAD DATA PATH** — claude_service.py:387 liest es nur in `_build_system_prompt()` (Legacy, nirgends aufgerufen, siehe CONCERNS.md:13). app_routes.py:273 nur als UI-Render. **Nicht im EWB-Prompt.** |
| `slot1_variant_busy_until` | live_session.py:351, claude_service.py:1479, deepgram_service.py:137 | claude_service.py:1425, deepgram_service.py:133 | ✅ state_lock | LIVE |
| `mic_muted` | live_session.py:352, deepgram_service.py:406 | deepgram_service.py:108 | ✅ state_lock | LIVE |
| `kw_fired_for_line` | live_session.py:354, einwand_keyword_matcher.py:253 | claude_service.py:1422 | ✅ state_lock | LIVE |
| `active_profile_id` | live_session.py:200, 355 | claude_service.py:1427 | ✅ state_lock | LIVE |
| **Lazy-created keys (nicht in init-dict):** | | | | |
| `_phase_cycle_at_last_change` | claude_service.py:1184 | claude_service.py:1164 | ✅ state_lock | LIVE (phase dedupe) |
| `last_einwand_typ` | claude_service.py:1313 | claude_service.py:1310 | ✅ state_lock | LIVE |
| `ft_session_id` | deepgram_service.py:350, app_routes.py:579 | claude_service.py:148, app_routes.py:563, 1243 | ✅ state_lock | LIVE |
| `user_id` | deepgram_service.py:351 | claude_service.py:150, 665, 734, 1423, app_routes.py:1244, cost_tracker.py:37 | ✅ state_lock | LIVE |
| `market` | deepgram_service.py:352 | claude_service.py:151, app_routes.py:1245 | ✅ state_lock | LIVE |
| `language` | deepgram_service.py:353 | claude_service.py:152, app_routes.py:1246 | ✅ state_lock | LIVE |
| `active_sid` | deepgram_service.py:291 | claude_service.py:1071, 1426 | ✅ state_lock | LIVE |
| `session_anrede` | deepgram_service.py:302 | app_routes.py:420, claude_service.py:666, 734, 1424, prompt_pipeline.py:216, 218 | ✅ state_lock | LIVE |
| `aktives_skript_inhalt` | deepgram_service.py:318 | claude_service.py:393 (nur in Legacy `_build_system_prompt`) | ✅ state_lock | ⚠️ **ORPHAN READER (Legacy)** — nur im toten Codepfad gelesen |
| `skript_bloecke` | deepgram_service.py:319 | claude_service.py:394 (dto. Legacy) | ✅ state_lock | ⚠️ **ORPHAN READER (Legacy)** |
| `mode` | **— KEIN Writer in ls.state gefunden** | claude_service.py:149, 1165, 1226, deepgram_service.py:274 (lokale var, nicht ls.state) | ✅ state_lock | 🧟 **GHOST READER** — `ls.state.get('mode')` defaultet IMMER auf 'cold_call' oder 'meeting'. Mode wird in deepgram_service.py:274 aus `data` gelesen aber NIE in `ls.state['mode']` geschrieben. **Cold-call detection + phase detection laufen auf Default-Fallback!** |
| `org_id` | **— KEIN Writer in ls.state gefunden** | cost_tracker.py:46 | ✅ state_lock | 🧟 **GHOST READER** — `cost_tracker.get_org_id()` gibt immer None zurück (fällt auf return None am Ende). |

### Module-Level Globals (non-state)

| Variable | Writer | Reader | Lock | Status |
|---|---|---|---|---|
| `keyword_matchers` (dict) | live_session.py:22, 29 (pop) | live_session.py:20 | ✅ keyword_matchers_lock | LIVE |
| `is_paused` | app_routes.py:213 | claude_service.py:1047, 1552, deepgram_service.py:39, 381, app_routes.py:214, 233 | ✅ pause_lock | LIVE |
| `transcript_buffer` | deepgram_service.py (via _flush_segment :293), reset_session :324 | claude_service.py:1056, diverse | ✅ buffer_lock | LIVE |
| `analysiert_bisher` | reset :325, claude_service.py:1056 (extend) | app_routes.py:176, 1091, claude_service.py:1055, 1160, 1196, 1230, 1571, deepgram_service.py:139, 443 | ⚠️ **KEIN LOCK** bei Reader-Access (buffer_lock wird nur beim .clear gehalten) | ⚠️ **LOCK-DISZIPLIN VERLETZT** — extend + read ohne Lock, in Python halbwegs GIL-safe aber nicht garantiert |
| `coaching_buffer` | _flush_segment:297, reset :327 | coaching_service.py (vermutet) | ✅ coaching_lock | LIVE |
| `analyse_trigger` (Event) | _flush_segment:294 | claude_service.py (analyse_loop) | — Event ist self-synchronized | LIVE |
| `coaching_trigger` (Event) | _flush_segment:298 | coaching_service.py | — | LIVE |
| `painpoints` | reset :329 | claude_service.py:1620 (`ls.painpoints`) | ✅ painpoints_lock | LIVE |
| `coach_tipps` | coach.py:224 (append), 245 (filter-rewrite) | coach.py:243 | ✅ coach_tipps_lock | LIVE |
| `gegenargument_log` | reset :391 (clear), unknown writer (nicht in beiden Dateien) | _build_log_content:553, reset :391 | ✅ gegenargument_log_lock | ⚠️ **WRITER UNKLAR** — in live_session.py keine append-Stelle. Prüfen: wo wird dieser Log gefüllt? |
| `hilfe_log` | reset :393 | _build_log_content:585 | ✅ hilfe_log_lock | ⚠️ **WRITER UNKLAR** — dto. |
| `quick_action_log` | reset :395 | _build_log_content:587 | ✅ quick_action_log_lock | ⚠️ **WRITER UNKLAR** — dto. |
| `phasen_log` | reset :397 | _build_log_content:604 | ✅ phasen_log_lock | ⚠️ **WRITER UNKLAR** — dto. |
| `conversation_log` | reset :322 (clear), deepgram_service.py (append, vermutet) | _build_log_content:446, app_routes.py:452+ | ✅ log_lock | LIVE |
| `roles_swapped` | reset :376 | _build_log_content:448 | ✅ roles_lock | LIVE (+ diverse andere Dateien) |
| `_log_last_sp` | deepgram_service.py:56 | deepgram_service.py:57 | ✅ _log_sp_lock | LIVE |
| `_second_sp_seen` | deepgram_service.py:50 | deepgram_service.py:51 | ✅ _sp2_lock | LIVE |
| `_confirmed_speaker`, `_pending_speaker`, `_pending_since` | stabilize_speaker:231-242 | stabilize_speaker | ✅ _speaker_lock | LIVE |
| `_bof_count` | claude_service.py:1566, 1568 | claude_service.py:1569 | ✅ _bof_lock | LIVE |
| `kaufbereitschaft` (global, nicht state-Key!) | update_kaufbereitschaft:305, reset :378 | claude_service.py (diverse) | ✅ kb_lock | LIVE (aber doppelt geführt zu state['kaufbereitschaft']!) |
| `kaufbereitschaft_verlauf` | update_kaufbereitschaft:307, reset :379 | (wahrscheinlich Post-Call) | ✅ kb_lock | ⚠️ **Reader unklar** |
| `aktive_phase_idx` | reset :381, app_routes.py:1099 | app_routes.py:327, 1102, claude_service.py:452 | ✅ phase_lock | LIVE |
| `covered_phases` | reset :389, app_routes.py:1101, claude_service.py:1217 | app_routes.py:325, (Post-Call) | ✅ covered_phases_lock | LIVE |
| `berater_words`, `kunde_words` | _flush_segment:281,288, reset :383 | get_speech_stats:434 | ✅ speech_lock | LIVE |
| `session_start_time` | reset :387 | get_speech_stats:437 | ✅ speech_lock | LIVE |
| `laengster_monolog_sek`, `_current_monolog_start` | _flush_segment, reset | get_speech_stats | ✅ speech_lock | LIVE |
| `active_profile_data`, `active_profile_name` | set_active_profile:195-196 | get_active_profile:205 | ✅ active_profile_lock | LIVE |
| `last_postcall` | app_routes.py:654 | ??? | ✅ last_postcall_lock | ⚠️ **Reader unklar** — gesetzt, aber kein Reader in Code-Grep gefunden. Ggf. nur von einem anderen app_routes-Endpoint abgerufen. |
| `_merge_pending` | deepgram_service.py:84-100, reset :367-372 | _flush_segment:265 | ✅ _merge_lock | LIVE |

### Locks-Matrix (18 Locks + 1 Counter-Lock)

| Lock | Geschützt: Felder | Nutzer-Funktionen |
|---|---|---|
| `state_lock` | 32 state-Keys (alle oben) | set_active_profile, load_learning_cards, record_ewb_click, reset_session + analyse_loop, deepgram_service, einwand_keyword_matcher, app_routes |
| `keyword_matchers_lock` | keyword_matchers dict | get_matcher, drop_matcher |
| `pause_lock` | is_paused | toggle_pause, analyse_loop, etc. |
| `buffer_lock` | transcript_buffer, analysiert_bisher | _flush_segment (append), reset_session |
| `coaching_lock` | coaching_buffer | _flush_segment, reset_session |
| `painpoints_lock` | painpoints | reset, _build_log_content, claude_service |
| `coach_tipps_lock` | coach_tipps | coach.py |
| `gegenargument_log_lock` | gegenargument_log | reset, _build_log_content |
| `hilfe_log_lock` | hilfe_log | reset, _build_log_content |
| `quick_action_log_lock` | quick_action_log | reset, _build_log_content |
| `phasen_log_lock` | phasen_log | reset, _build_log_content |
| `session_meta_lock` | session_meta | reset |
| `_merge_lock` | _merge_pending | _flush_segment, reset, deepgram_service |
| `_line_id_lock` | _line_id_counter | next_line_id, reset |
| `log_lock` | conversation_log | reset, _build_log_content |
| `roles_lock` | roles_swapped | reset, _build_log_content |
| `_log_sp_lock` | _log_last_sp | reset, deepgram_service |
| `_sp2_lock` | _second_sp_seen | reset, deepgram_service |
| `_speaker_lock` | _confirmed/_pending_speaker, _pending_since | stabilize_speaker, reset |
| `_bof_lock` | _bof_count | reset, claude_service |
| `kb_lock` | kaufbereitschaft, kaufbereitschaft_verlauf | update_kaufbereitschaft, reset |
| `phase_lock` | aktive_phase_idx | reset, app_routes, claude_service |
| `speech_lock` | berater_words, kunde_words, session_start_time, laengster_monolog_sek, _current_monolog_start | _flush_segment, get_speech_stats, reset |
| `covered_phases_lock` | covered_phases | reset, app_routes, claude_service |
| `active_profile_lock` | active_profile_data, active_profile_name | set_active_profile, get_active_profile |
| `last_postcall_lock` | last_postcall | app_routes |

**Deadlock-Analyse:** In beiden Dateien keine verschachtelten Lock-Acquires festgestellt. `reset_session` hält die Locks einzeln nacheinander — kein zirkuläres Warten möglich. `_flush_segment` acquired `speech_lock` → entlässt → `buffer_lock` → entlässt → `coaching_lock`. Sauber.

**Lock-Disziplin-Violation:** `ls.analysiert_bisher` wird in mehreren Dateien (claude_service, deepgram_service, app_routes) ohne Lock gelesen UND geschrieben (extend). Python-Listen sind GIL-protected bei atomic ops, aber `len()`-reads gefolgt von `extend` sind Race-anfällig (wird aber nicht als HIGH gerated — best-effort Snapshot).

### Funktionen in live_session.py

| Funktion | Zeile | Aufgerufen von | Status |
|---|---|---|---|
| `get_matcher(sid)` | 17 | deepgram_service.py:115 | LIVE |
| `drop_matcher(sid)` | 26 | deepgram_service.py:364, 398 | LIVE |
| `next_line_id()` | 96 | deepgram_service.py:44 | LIVE (+ nerve_rt hat eigene Impl) |
| `set_active_profile(name, daten, profile_id)` | 192 | app.py:1259, app_routes.py:116, 995, profiles.py:201 | LIVE |
| `get_active_profile()` | 203 | app_routes.py:322, 1129, 1179, claude_service.py:267, 406, 1212, 1294, 1452, deepgram_service.py:111, 429, prompt_pipeline.py:136 + Tests | LIVE |
| `load_learning_cards(user_id)` | 208 | app_routes.py:118, 996 | LIVE |
| `stabilize_speaker(raw)` | 227 | deepgram_service.py:43 | LIVE |
| `ist_painpoint_duplikat(neu, bestehende)` | 247 | claude_service.py:1620 | LIVE |
| `_flush_segment(key)` | 262 | deepgram_service.py:97 (als threading.Timer callback) | LIVE |
| `update_kaufbereitschaft(delta)` | 301 | claude_service.py:1092, 1583 | LIVE |
| `reset_session()` | 311 | app_routes.py:675 | LIVE |
| `record_ewb_click(...)` | 416 | app_routes.py:1234, deepgram_service.py:452, 459, 474 | LIVE |
| `get_speech_stats()` | 431 | app_routes.py:156, 396, claude_service.py:1595 | LIVE |
| `_build_log_content(user_email, profile_name)` | 444 | app_routes.py:250, 383 | LIVE |

**Alle 14 Funktionen LIVE. Keine toten Funktionen in live_session.py.**

---

## ki_logik.py

### Funktionen

| Funktion | Zeile | Aufgerufen von | Status |
|---|---|---|---|
| `compute_readiness_score(state, transcript_window)` | 94 | claude_service.py:1264, tests/services/test_ki_logik.py | LIVE |
| `select_active_hint(candidates)` | 120 | claude_service.py:1288, tests | LIVE |
| `dynamic_ewb_buttons(phase, base_buttons, last_einwand_typ)` | 138 | claude_service.py:1314, tests | LIVE |
| `detect_phase(raw_phase, raw_confidence, current_phase, phase_change_count, cycles_since_change)` | 160 | claude_service.py:1170, tests | LIVE |
| `infer_cold_call_context(seller_transcript, current_phase, mode, haiku_caller)` | 190 | claude_service.py:1231, tests | LIVE |

**Alle 5 Funktionen LIVE.**

**Auffälligkeit:** `transcript_window`-Parameter in `compute_readiness_score` wird nie benutzt (siehe docstring Z. 99-100 "reserved for future use, currently unused"). Produktionsaufruf claude_service.py:1264 übergibt `[]`. **Tote Signatur-Erweiterung** — LOW.

**Parameter-Diskrepanz `detect_phase`:** Signatur Z. 160 hat Parameter `phase_change_count`, dieser wird aber **in der Funktion nie gelesen** (nur `cycles_since_change`). Call-Site claude_service.py:1170 übergibt beide. **Unused parameter** — LOW.

### Konstanten / Mappings

| Name | Verwendung | Komplett genutzt? |
|---|---|---|
| `SCORE_FACTORS` (10 Keys) | ki_logik.py:107 (compute_readiness_score iteriert alle) + claude_service.py:1244 Import + Test | ✅ Alle 10 Keys via .items()-Iteration |
| `SCORE_BASE` | ki_logik.py:105 + Test | ✅ LIVE |
| `SCORE_MIN`, `SCORE_MAX` | ki_logik.py:110 | ✅ LIVE |
| `BUCKETS` (4 Tupel) | ki_logik.py:113 (Iteration) + Test | ✅ alle 4 verwendet |
| `PHASE_BUTTONS` (Keys 1-6) | ki_logik.py:153, claude_service.py:478 (nur im Kommentar!) + Tests prüfen alle 6 Phasen | ✅ Phase 1-6 alle in Tests + Live-Fallback |
| `EINWAND_FOLLOWUP` (9 Keys: Zeit/Aufschub, Kosten/Preis, Kein Bedarf, Vertrauen, Komplexität, Angst/Risiko, Vergleich, Entscheidungsträger, Abbruch) | ki_logik.py:151,152 | ⚠️ **Keys werden gegen Haiku-Output gematcht** — Prüfung nötig ob Claude-Prompt (einwand_typ-Output) GENAU diese 9 Labels liefert. Wenn nicht → Keys sind faktisch tot. Cross-Module-Hypothese für Master-Audit. |
| `HINT_PRIORITY` (5 Keys) | **— NIRGENDS IMPORTIERT/VERWENDET** | ⚠️ **ORPHAN CONSTANT** — claude_service.py:1269-1285 hardcodet die Werte 1,2,3,4,5 statt den Dict zu nutzen. Drift-Risiko: wenn jemand HINT_PRIORITY ändert, passiert nichts. |

### Imports

- `from typing import Optional` — verwendet in Z. 120, 138, 139, 190, 191. ✅

---

## Verdachts-Stellen

### Orphaned Writers (geschrieben, nie gelesen)
- `state['phase_changed_at']` — gesetzt in reset und claude_service.py:1182. Nicht in `/api/ergebnis`-Polling enthalten, kein direkter Reader in Python. Möglicherweise Frontend-only, aber nicht im Backend-Response-Payload. **Divergenz zur ARCHITECTURE.md prüfen.**
- `state['ewb_top2']` — nur in reset :336 auf None gesetzt, nirgends ein echter Wert-Write gefunden. Legacy-Marker (CONCERNS.md line 124). **Bestätigt orphan.**

### Orphaned Readers (gelesen, nie geschrieben) — GHOST READS
- `state.get('mode')` — claude_service.py:149, 1165, 1226. **KEIN WRITER in ls.state.** Fällt immer auf Default 'cold_call' bzw. 'meeting' zurück. Das heißt: die Phase-Detection-Logik + `infer_cold_call_context`-Branch laufen auf **hardcoded Default**, nicht auf vom User gewählten Modus. → **HIGH Severity**, Cross-Check Master-Audit nötig.
- `state.get('org_id')` — cost_tracker.py:46. Nirgends geschrieben. `get_org_id()` gibt immer None zurück. Ob das ein Problem ist, hängt vom Kontext (Multi-Tenancy?). **MEDIUM**.
- `state.get('aktives_skript_inhalt')` + `state.get('skript_bloecke')` — gesetzt in deepgram_service.py:318-319, gelesen NUR in `_build_system_prompt` (claude_service.py:393-394) → dieser Codepfad ist laut CONCERNS.md:13 nicht live (Legacy-Stub). → **ORPHAN READER via toter Funktion**. Skript-Integration läuft faktisch nicht mehr über diese Keys.
- `state.get('precall_briefing')` — bestätigt aus CONCERNS.md: nicht in EWB-Prompt, nur UI-Render via app_routes.py:273. **Dead data path.**

### Silent Failures
- live_session.py:216-219 — `load_learning_cards` except Exception → print + leere Liste. OK, da fail-open.
- live_session.py:370-371 — Timer.cancel() in reset_session, stumm. OK, best-effort cleanup.
- **Keine anderen bare-except oder pass-except in beiden Dateien.**

### Auskommentierter Code / TODOs
- Keine TODO/FIXME/XXX-Marker in beiden Dateien.
- Kommentare markieren Phase-Zugehörigkeit (04.8, 04.11, 06.2, 08.5) — keine Auskommentierungen.
- ki_logik.py:100 "currently unused" — ehrlicher Hinweis auf `transcript_window` Parameter.

### Unused Imports
- **live_session.py:9** — `ANALYSE_INTERVALL` importiert aus config, **nirgends in der Datei verwendet**. Grep bestätigt: nur im Import. → entfernen.
- Alle anderen Imports (`os`, `threading`, `time`, `datetime`, `MERGE_WINDOW_S`, `SPEAKER_DEBOUNCE_S`, `KATEGORIE_LABEL`) werden verwendet.

### Doppel-Import
- live_session.py:8 `from datetime import datetime` (global)
- live_session.py:419 `import datetime as _dt` (lokal in record_ewb_click) — funktioniert, aber inkonsistent. `datetime.utcnow()` könnte auch im Global stehen. LOW cleanup.

---

## Findings — Severity-sortiert

### HIGH

**H1 — GHOST READ: `state['mode']`**
- Location: `claude_service.py:149, 1165, 1226`
- Impact: Mode-sensitive Logik (Cold-Call vs. Meeting) läuft auf Default-Fallback, nicht auf User-Choice. Phase-Detection-Regression in `detect_phase` und `infer_cold_call_context` werden möglicherweise immer in einem Modus getriggert, nicht im korrekten.
- Root Cause: deepgram_service.py:274 liest `mode = data.get('mode', 'meeting')` in eine lokale Variable, **schreibt sie aber nie in `ls.state['mode']`** (obwohl user_id, market, language, ft_session_id direkt daneben geschrieben werden — Zeilen 350-353).
- Fix: `ls.state['mode'] = mode` in deepgram_service.py:~353 ergänzen. State-Init in live_session.py `state = {...}` um `'mode': 'meeting'` erweitern.
- **Verification-Check dringend nötig**: Prüfen ob Cold-Call-Inference überhaupt jemals korrekt getriggert wurde seit Phase 04.8.

**H2 — Nudelcode-Rest: `ewb_top2` Phase 04.8 Cleanup übersehen**
- Location: live_session.py:110, 336; app_routes.py:145
- Impact: State-Key existiert, ist aber tot. Verwirrt Entwickler, vergrößert state-dict unnötig. Frontend kriegt im Polling ein `ewb_top2: null` Feld dauerhaft.
- Fix: Key aus init + reset + polling-response entfernen. Kommentar in app_routes:145 ("legacy (may be None post-04.8)") ist explizites Todo.

### MEDIUM

**M1 — Orphaned Constant: `HINT_PRIORITY`**
- Location: ki_logik.py:85
- Impact: Priority-Werte 1-5 sind an 2 Stellen im Code dupliziert: einmal als Dict in ki_logik.py (nie gelesen), einmal hardcoded in claude_service.py:1269-1285. Wenn jemand Prio ändert, muss man wissen dass Dict tot ist → Drift-Risiko.
- Fix: Entweder Dict löschen, oder claude_service.py umbauen auf `candidates.append({'priority': HINT_PRIORITY['critical'], ...})`.

**M2 — Legacy-Pfad-Reader: `aktives_skript_inhalt` + `skript_bloecke`**
- Location: deepgram_service.py:318-319 (write) → claude_service.py:393-394 (read in toter Legacy-Funktion `_build_system_prompt`)
- Impact: Skript-Content wird bei jedem Session-Start in state geschrieben, aber nie vom Live-EWB-Prompt gelesen (siehe CONCERNS.md profile-prompt-Gap). Wie `precall_briefing`.
- Fix: Entweder re-wire in `build_ewb_prompt` (Phase 08.x), oder Schreib-Pfad entfernen.

**M3 — GHOST READ: `state['org_id']`**
- Location: cost_tracker.py:46
- Impact: Cost-Tracker kann Org niemals auflösen (immer None). Vermutlich OK in Solo-Founder-Phase, aber Multi-Tenant-Ready wäre anders.
- Fix: Entweder Writer einbauen (wahrscheinlich aus DB bei Session-Start) oder Feature deprecaten.

**M4 — Lock-Disziplin: `analysiert_bisher` unlocked access**
- Location: live_session.py:42 (global), multiple read/extend sites ohne buffer_lock
- Impact: Race condition möglich zwischen `extend(...)` in analyse_loop und `[-20:]`-Snapshot in anderen Threads. Python-GIL macht es meist OK, aber kein Garant.
- Fix: Entweder unter buffer_lock stellen, oder zu einer lock-freien `collections.deque` mit maxlen migrieren.

### LOW

**L1 — Unused Import: `ANALYSE_INTERVALL`** in live_session.py:9.

**L2 — Unused Parameter: `transcript_window`** in `compute_readiness_score` (ki_logik.py:94). Dokumentiert als "reserved for future use".

**L3 — Unused Parameter: `phase_change_count`** in `detect_phase` (ki_logik.py:160). Wird im Body nie gelesen.

**L4 — Inkonsistenter Datetime-Import** in live_session.py:8 (global) vs. :419 (lokal als `_dt`).

**L5 — Writer für `gegenargument_log`, `hilfe_log`, `quick_action_log`, `phasen_log` liegen außerhalb beider Dateien.** In live_session.py werden diese Locks + leere Listen deklariert, aber Writer-Stellen müssen in app_routes.py / claude_service.py gesucht werden (nicht in meinem Scope, Cross-Module-Hypothese).

**L6 — `last_postcall` Reader unklar.** Gesetzt in app_routes.py:654, kein Reader in meinem Grep gefunden.

**L7 — `kaufbereitschaft_verlauf` Reader unklar.** Wird bei jedem update gepusht, aber Leser nicht in diesem Scope sichtbar.

**L8 — Doppelte Führung `kaufbereitschaft`.** Als `state['kaufbereitschaft']` (state_lock) UND als Module-Global `kaufbereitschaft` (kb_lock). Claude_service.py mirrors `readiness_score` in `state['kaufbereitschaft']` (Z. 1320), aber `update_kaufbereitschaft()` (live_session.py:301) fasst `state['kaufbereitschaft']` NIE an — ändert nur das Global. → **Diese zwei Werte können divergieren.** MEDIUM-verdächtig, aber current reads verwenden immer `state['kaufbereitschaft']` (legacy mirror), also nur potenziell problematisch. Cross-check nötig.

---

## Cross-Module-Hypothesen für Master-Audit

1. **`state['mode']` Ghost Read — CRITICAL**: Wer schreibt diesen Key? Falls niemand, dann sind Cold-Call-Inference und Phase-Regression seit Phase 04.8 fehlerhaft. Live-Test auf einem VPS prüfen: `journalctl -u nerve | grep 'mode'`.

2. **`EINWAND_FOLLOWUP`-Keys vs. Haiku-Output**: Die 9 Keys (`Zeit/Aufschub`, `Kosten/Preis`, `Kein Bedarf`, `Vertrauen`, `Komplexität`, `Angst/Risiko`, `Vergleich`, `Entscheidungsträger`, `Abbruch`) müssen EXAKT so aus dem Claude-Prompt zurückkommen, sonst greift der Followup-Pfad nie. Master-Audit sollte EWB-Prompt-Output-Schema gegen diese Keys verifizieren.

3. **Doppelpfad `kaufbereitschaft` Global vs. `state['kaufbereitschaft']`**: Wer liest was? Falls Frontend eine der Variablen liest und analyse_loop die andere schreibt, kann es zu Inkonsistenzen kommen. Sollte konsolidiert werden.

4. **`precall_briefing` DEAD DATA PATH** (aus CONCERNS.md bestätigt): User wartet auf AI-Research, System generiert Text, speichert in state, Live-Prompt ignoriert ihn. Re-wire oder deprecate-Entscheidung nötig.

5. **Legacy `_build_system_prompt`** (claude_service.py:265) ist laut CONCERNS.md nicht aufgerufen, aber liest `precall_briefing`, `aktives_skript_inhalt`, `skript_bloecke`. Wenn wir diesen Stub killen, werden 3 Writer in deepgram_service zu reinen Orphan-Writern. Pruning als Paket planen.

6. **`ewb_top2`** Phase 04.8 Cleanup nachholen — Key aus Init/Reset + Polling-Response streichen. 5-Minuten-Fix, sicherer Gewinn.

7. **Writer für `gegenargument_log` / `hilfe_log` / `quick_action_log` / `phasen_log`** außerhalb live_session.py lokalisieren. Vermutlich in app_routes.py (Button-Handlers) und claude_service.py (Einwand-Erkennung + Phase-Wechsel).

8. **`analysiert_bisher` ohne Lock** — architectural debt, aber nicht bug-producing unter Python-GIL. Niedrige Prio, aber dokumentieren.
