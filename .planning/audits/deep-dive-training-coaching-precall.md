---
audit: deep-dive-training-coaching-precall
erstellt: 2026-04-24
dateien:
  - services/training_service.py (1326 Zeilen)
  - services/coaching_service.py (436 Zeilen)
  - services/precall_service.py (197 Zeilen)
autor: Claudian (Vault) — Welle 2 Deep-Dive
methode: Alle 3 Dateien komplett gelesen + Call-Graph-Grep (codebase-weit) + Cross-Check gegen Welle 1 (claude_service + pipelines) + profil-prompt-integration-matrix + CONCERNS.md
---

# Deep-Dive: training + coaching + precall

## TL;DR

Drei Service-Dateien, drei unterschiedliche Nudelcode-Signaturen:
1. **training_service.py** — Haupt-Modul für Training (Phase 04.9+08.5). Alle Top-Level-Funktionen sind LIVE (keine Dead-Funktions hier, anders als claude_service). **ABER:** alle 3 `log_pipeline_event`-Calls sind faktisch silent-fail weil `services/finetune_logging.py` NICHT im Repo existiert (bestätigt Welle 1 Finding — dieselbe Illusion läuft in qa_pipeline.py UND hier). FT-Tagging für Training-Modul existiert nur auf dem Papier.
2. **coaching_service.py** — 5 Funktionen, alle LIVE. **Tod-durch-Signature**: `generate_postcall_analysis(... profile_data=None)` hat Parameter `profile_data` in der Signatur, aber KEIN Call-Site übergibt ihn jemals (verifiziert an `routes/learning.py:31` und `:261`). Innerhalb der Funktion wird `profile_data` NIE gelesen (grep-verifiziert). Parameter ist toter Ballast → Sonnet Post-Call Coach fährt ohne Profil-Kontext.
3. **precall_service.py** — Schlank, 4 Funktionen, alle LIVE. PreCall-Output fließt über DB (`ConversationLog.precall_briefing`) und `ls.state['precall_briefing']`. Letzteres wird in CLAUDE-ANALYSE NUR in `_build_system_prompt` (Z.387) konsumiert — das ist **DEAD CODE** laut Welle 1. → **PreCall-Briefing landet in keinem Live-LLM-Pfad. Damit ist das gesamte Phase-04.13-Feature faktisch blind für EWB und Coach.**

Quer-finding: hardcoded `user_id=None` in allen Cost-Tracker-Calls dieser 3 Dateien (precall_service:175/178, training_service:1316). Plus: `g.user.id`-Lookup via Flask `g` im TTS-Pfad ist Best-Effort — funktioniert nur im Request-Kontext, nicht in Background-Threads.

## Call-Graph

### training_service.py

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `mood_to_voice_settings` | 147 | `routes/training.py:314/534`, `tests/test_mood_voice.py` (9×) | LIVE | Phase 04.10.1 Voice-Zones. 2 Live-Call-Sites. |
| `_random_persona` | 522 | `routes/training.py:222` | INTERNAL LIVE | Nur 1 Call-Site, konsistent verwendet. |
| `build_sekretaerin_prompt` | 537 | `tests/test_08_5_05_training_pipeline_t2.py:168` + `TRAINING_PERSONA_PROMPT_BASE`-Alias Z.519 | **TEST-ONLY** | **Finding:** In `routes/training.py` wird NICHT `build_sekretaerin_prompt` aufgerufen, sondern `build_sekretaerin_type_prompt`. Die alte SEKRETAERIN_PROMPT-Variante ist faktisch tot — nur als Fallback-Template in `_TRAINING_FALLBACKS['training_sek']` (Z.691) und Tests. |
| `build_sekretaerin_type_prompt` | 547 | `routes/training.py:283` | LIVE | Aktive Sekretärin-Pipeline (D-06). |
| `build_customer_prompt` | 569 | `routes/training.py:258` | LIVE | Classic-Pfad (kein personality_data). |
| `_load_training_prompt_template` | 697 | `generate_response:806`, `generate_response_with_mood:858/859`, `generate_scoring:1107` | INTERNAL LIVE | Lädt prompt_versions aus DB, fällt auf _TRAINING_FALLBACKS. |
| `build_personality_prompt` | 724 | `routes/training.py:247/454` | LIVE | Phase 04.9 Personality-Pfad. |
| `generate_response` | 798 | `routes/training.py:295/486/564` | LIVE | Non-JSON Haiku. Verwendet von Sekretärin + Fallback. |
| `generate_response_with_mood` | 839 | `routes/training.py:292/463` | LIVE | JSON-Haiku mit Mood-Parse + letzte_chance/aufgelegt. |
| `generate_help_suggestion` | 919 | `routes/training.py:599` | LIVE | Haiku, phase-aware. |
| `_repair_scoring_json` | 1020 | `generate_scoring:1208` (selbe Datei) + implizit | INTERNAL LIVE | JSON-Repair Layer für Sonnet-Truncation. |
| `generate_scoring` | 1097 | `routes/training.py:624` | LIVE | **EINZIGER Sonnet-Call in training_service** (Z.1188, sonnet-4-6). |
| `_generate_live_preview` | 1235 | `routes/training.py:654` | INTERNAL LIVE | Haiku, zeigt "was NERVE live geholfen hätte". |
| `text_to_speech` | 1281 | `routes/training.py:317/537/567` | LIVE | ElevenLabs TTS mit Cost-Tracking. |

**Summary:**
- LIVE: 12 Funktionen
- INTERNAL LIVE: 4 (alle lokal gerufen)
- TEST-ONLY: 1 (`build_sekretaerin_prompt` — hat unter Phase 04.9/D-06-Migration den Live-Call-Platz an `build_sekretaerin_type_prompt` verloren)
- DEAD (echt): 0

**Persona-Build-Funktionen:** `build_customer_personality_prompt` aus der Aufgabenbeschreibung EXISTIERT NICHT. Die Liste enthält einen Phantom-Namen. Die echten 4 sind: `build_customer_prompt`, `build_sekretaerin_prompt`, `build_sekretaerin_type_prompt`, `build_personality_prompt` → davon ist **1 (build_sekretaerin_prompt) test-only**.

### coaching_service.py

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `generate_postcall_analysis` | 51 | `routes/learning.py:31` (live: `/api/analysis/:conv_id`), `routes/learning.py:261` (training post-call) | LIVE | Signatur hat `profile_data=None`, aber NIEMAND übergibt ihn (beide Call-Sites fehlen). Body liest ihn auch NICHT. → Dead parameter. |
| `validate_user_text` | 145 | `routes/learning.py:217` (`/api/cards/:id/validate`) | LIVE | Haiku, JSON-Parser. |
| `get_active_cards` | 165 | `routes/dashboard.py:564`, `services/live_session.py:211-212` (Warm-Load auf Session-Start) | LIVE | 2 Call-Sites. |
| `get_or_generate_weekly_report` | 183 | `routes/dashboard.py:565` | LIVE | DB-gecachter Sonnet-Call (D-08 Training-Integration). |
| `get_longterm_data` | 386 | `routes/dashboard.py:566` | LIVE | Reine DB-Aggregation, kein LLM. |

**Summary:** Alle 5 Funktionen LIVE. Keine Dead-Funktionen, keine Zombies. Aber **1 dead parameter** (`profile_data`) und **1 Sonnet-Hot-Path** der das Profil nicht kennt (siehe Findings HIGH-01).

### precall_service.py

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `recherche_firma` | 43 | `routes/app_routes.py:1386` (`/api/precall/research`) | LIVE | Einzige Call-Site. |
| `_brave_search` | 95 | `recherche_firma:76` | INTERNAL | OK. |
| `_generiere_briefing` | 127 | `recherche_firma:81` | INTERNAL | OK. |
| `ist_verfuegbar` | 195 | `routes/app_routes.py:120/1027` (Dashboard-Flag) | LIVE | 2 Call-Sites. |

**Summary:** Schlank. Keine Dead-Funktionen.

## Claude-API-Calls

| Datei | Zeile | Funktion | Model | max_tokens | System-Prompt Quelle | User-Msg Quelle | Cost-Tracker? | Status |
|---|---|---|---|---|---|---|---|---|
| training_service.py | 816 | `generate_response` | haiku-4-5-20251001 | 400 | `system_prompt` param (pre-built by caller) | `conversation_history` | ❌ KEIN Cost-Tracker | LIVE |
| training_service.py | 868 | `generate_response_with_mood` | haiku-4-5-20251001 | 500 | `system_prompt` param (pre-built) | `conversation_history` | ❌ KEIN Cost-Tracker | LIVE |
| training_service.py | 1003 | `generate_help_suggestion` | haiku-4-5-20251001 | 200 | — (nur user message) | `prompt` inline f-string | ❌ KEIN Cost-Tracker | LIVE |
| training_service.py | 1187 | `generate_scoring` | **sonnet-4-6** | 3000 | — | `prompt` inline f-string mit Gespräch+Profile | ❌ KEIN Cost-Tracker | LIVE |
| training_service.py | 1265 | `_generate_live_preview` | haiku-4-5-20251001 | 600 | — | `prompt` inline f-string | ❌ KEIN Cost-Tracker | INTERNAL LIVE |
| coaching_service.py | 86 | `generate_postcall_analysis` | **sonnet-4-6** | 1500 | — | `prompt_text` (POSTCALL_PROMPT-Format) | ✅ `context_tag='postcall_coach'`, user_id=user_id | LIVE |
| coaching_service.py | 148 | `validate_user_text` | haiku-4-5-20251001 | 200 | — | inline f-string | ❌ KEIN Cost-Tracker | LIVE |
| coaching_service.py | 319 | `get_or_generate_weekly_report` | **sonnet-4-6** | 800 | — | `report_prompt` inline | ✅ `context_tag='weekly_coach_report'`, user_id=user_id | LIVE |
| precall_service.py | 161 | `_generiere_briefing` | haiku-4-5-20251001 | 800 | `PRECALL_SYSTEM_PROMPT` (Modul-Konstante, hardcoded) | inline `user_msg` | ✅ `context_tag='precall'`, user_id=None | LIVE |

**Kritische Beobachtungen:**

1. **training_service.py hat KEINEN einzigen Cost-Tracker-Call für seine 5 Claude-Calls** — ausser TTS (Z.1316). Phase 04.7.2 Cost-Hook wurde für Training übersprungen. Das ist ein **völlig blinder Spot** im Founder-Dashboard. Bei aktiver Training-Nutzung mit Sonnet Scoring (3000 max_tokens!) entstehen Kosten, die nirgendwo getrackt werden.
2. **coaching_service.py ist der einzige Spot in dieser Welle mit echtem `user_id`-Threading** in Cost-Calls. Lobenswert.
3. **precall_service.py trackt mit `user_id=None`** (Z.175/178) — konsistent mit claude_service Problem. User-Attribution geht verloren.
4. **3 Sonnet-Call-Stellen in dieser Welle:** training_service:1188 (Scoring), coaching_service:86 (PostCall-Coach), coaching_service:319 (Weekly Report). **Kein einziger nutzt System-Prompt!** Alles im User-Message. Prompt-Caching (D-14 Roadmap: EWB-Wechsel auf Sonnet 4.5 + Caching) würde hier signifikant wirken — ist aber nicht vorbereitet.
5. **Keiner der Sonnet-Calls ist über `prompt_versions` DB-versioniert.** Nur `generate_scoring` versucht `_load_training_prompt_template('training_scoring', ...)` zu lesen, aber der Inhalt wird als `_scoring_preamble` gespeichert und **nie verwendet** (grep in training_service.py: `_scoring_preamble` kommt nach Z.1107 nie wieder vor — dead local variable, nur Parity-Tagging!).

## DB-Zugriffe

| Datei | Funktion | Model | Operation | Session-Pattern |
|---|---|---|---|---|
| training_service.py | `_load_training_prompt_template` | PromptVersion | read | `SessionLocal()` + try/finally close ✅ |
| coaching_service.py | `generate_postcall_analysis` | LearningCard | read+write | 2× getrennte Sessions (check + persist), beide try/finally ✅ |
| coaching_service.py | `get_active_cards` | LearningCard | read | try/finally ✅ |
| coaching_service.py | `get_or_generate_weekly_report` | CoachingReport, ConversationLog | read+write | try/finally ✅ (aber **1 Nested `try` ohne explicites `rollback`** siehe MEDIUM-02) |
| coaching_service.py | `get_longterm_data` | ConversationLog | read | try/finally ✅ |
| precall_service.py | — | — | — | Keine DB-Zugriffe (In-Memory Cache) |

**Beobachtung:** Konsistent `db = get_session() / try / finally db.close()`. Kein Context-Manager (`with`-Statement), aber korrekt. Coaching_service:132 hat ein `rollback()` bei DB-Fehler in `generate_postcall_analysis` — gut. Coaching_service hat ABER ein subtiles Problem in `get_or_generate_weekly_report`: bei Sonnet-Exception wird zwar geloggt, aber **kein rollback, sondern direkt `db.add(report)+db.commit()` mit Fallback-Text weitergefahren** (Z.345-365). Das ist gewollt (Fallback statt Komplett-Fail), aber riskant falls die DB-Session durch einen früheren Fehler korrupt ist.

## Hardcoded Parameters — Zero-Profile-Call-Check

Wie im QA-Dispatch (Welle 1, qa_pipeline.py mit leerem `{}`) systematisch prüfen.

| Call-Site | Was wird gerufen | Kritischer Parameter | Wert | Ist das ein Problem? |
|---|---|---|---|---|
| `routes/learning.py:31` | `generate_postcall_analysis(...)` | `profile_data` | **NICHT ÜBERGEBEN** (defaultet zu None) | **JA → HIGH-01.** Sonnet-PostCall-Coach hat keinen Profil-Kontext, generiert generische Lernkarten. |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `profile_data` | **NICHT ÜBERGEBEN** | **JA → HIGH-01.** Selbes Problem im Training-PostCall-Pfad. |
| `routes/learning.py:31` | `generate_postcall_analysis(...)` | `kaufsignale` | `data.get('kaufsignale', [])` | OK. |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `kaufsignale` | **NICHT ÜBERGEBEN** (defaultet zu `None`) | Minor — im Prompt wird `kaufsignale or []` aufgelöst (coaching_service:76). Kein Crash. |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `painpoints` | **`[]` hardcoded** | MEDIUM — Training-PostCall verliert Painpoint-Analyse (keine aus Training extrahiert). |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `kb_start` | **`0` hardcoded** | MEDIUM — Training hat keinen Start-Kaufbereitschafts-Score verfügbar. Acceptable aber generiert Müll-Delta im Prompt. |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `redeanteil_berater/kunde` | **`60`/`40` hardcoded** | **HIGH-02** — Training misst keinen Redeanteil, aber diese Werte werden als echte Zahlen in den Sonnet-Prompt geschoben. Sonnet "glaubt" die Zahlen sind gemessen → halluziniert Begründungen auf Basis erfundener 60/40. |
| `routes/learning.py:261` | `generate_postcall_analysis(...)` | `skript_abdeckung` | `scoring.get('gesamt_score', 0)` | **Semantisch falsch** — `gesamt_score` ist der Trainings-Gesamt-Score (0-100), nicht Skript-Abdeckung. Param-Name-Missmatch. |
| `routes/training.py:624` | `generate_scoring(...)` | `profile_data=session['profile_data']` | Aus Session geladen | OK. |
| `routes/app_routes.py:1413` | `recherche_firma(...)` | `profil_daten=profil_daten` | Aus aktivem Profil geladen ODER None | OK. Fallback-Logik sauber. |
| `precall_service.py:175/178` | `log_api_cost(user_id=None, ...)` | `user_id` | `None` hardcoded | MEDIUM — User-Attribution fehlt. |
| `training_service.py:1310-1315` | TTS Cost-Hook | `uid` | `g.user.id` via try/except | OK im Request-Kontext, None sonst. Defensiv geschrieben. |

**Fazit Zero-Profile-Check:**
- `generate_postcall_analysis` ist der **schwerwiegendste Fall** — der einzige Sonnet-PostCall-Coach-Pfad im gesamten System läuft ohne Profil-Kontext. Tabu-wirksam genauso wie QA-Dispatch-Leeres-Dict-Problem.
- `get_or_generate_weekly_report` ist ebenfalls **profil-blind** (generiert Weekly-Report ohne Profil-Daten). Das mag akzeptabel sein (Wochen-Aggregat), aber konsistent mit dem Muster.

## ls.state-Zugriffe

| Feld | Operation | Funktion | Lock-Status |
|---|---|---|---|
| — | training_service.py hat KEINE ls.state-Zugriffe (reine Persona/LLM-Pipeline) | — | — |
| — | coaching_service.py hat KEINE ls.state-Zugriffe (reine DB-Operation) | — | — |
| — | precall_service.py hat KEINE ls.state-Zugriffe direkt (schreibt über Route nach app_routes.py:454 in DB + deepgram_service.py:309 in ls.state) | — | — |

**Kein `state['mode']` Ghost Read** in diesen 3 Dateien. Welle-1-Finding (claude_service: `mode`-Ghost) bleibt auf claude_service.py isoliert.

**Aber** (Cross-Modul): Precall-Briefing wird in `services/deepgram_service.py:309` nach `ls.state['precall_briefing']` geschrieben und in `services/claude_service.py:387` in der **DEAD Funktion `_build_system_prompt`** gelesen. Damit ist der PreCall→LLM-Fluss komplett broken. Details in Findings HIGH-03.

## Verdachts-Stellen

### TODOs / FIXMEs
Keine TODO/FIXME/XXX/HACK-Kommentare in allen 3 Dateien (grep-verifiziert).

### Silent Failures

| Datei | Zeile | Pattern | Bewertung |
|---|---|---|---|
| training_service.py | 833-834 | `except Exception as _e: print(f"[Training] log_pipeline_event skipped: {_e}")` | **Double-Silent:** `log_pipeline_event` selbst swallowed (siehe Welle 1), hier nochmal umwickelt mit silent-print. Doppelter Absicherungslayer gegen etwas das ohnehin nie crasht. |
| training_service.py | 906-907 | Analog wie oben für `training_stimmung` | Siehe oben. |
| training_service.py | 1229-1230 | Analog wie oben für `training_scoring` | Siehe oben. |
| training_service.py | 909-916 | JSON-Parse-Fallback: setzt neutrale Werte, gibt plain text zurück | **Vertretbar** (Robustness-Pattern), aber das bedeutet: wenn Haiku das JSON-Format verliert, fällt Mood-Tracking silent auf current_mood zurück. Keine Sentry-Notification, kein Counter. |
| training_service.py | 929-934 | JSON-String-in-Dict-Profile-Decode silent except | Defensive Dict-Normalization, OK. |
| training_service.py | 1274-1278 | `_generate_live_preview` JSON-Parse failure → `return {'momente': [], 'zusammenfassung': ''}` | Silent — User sieht leere Preview, kein Error. |
| training_service.py | 1319-1320 | Cost-Hook TTS silent print | OK. |
| coaching_service.py | 70-72 | Duplicate-Guard: "already exist → return []" | **Subtil:** bei bereits existierenden Suggestions wird genau das gleiche zurückgegeben wie bei Sonnet-Fail (leere Liste → Z.142). Frontend unterscheidet beide Fälle nicht. |
| coaching_service.py | 104-105 | `print(f"[CostHook] postcall_coach skipped: {_ce}")` | OK. |
| coaching_service.py | 132-135 | DB-Persist-Fail → `rollback; return []` | **Problem:** Die Sonnet-Call hat bereits Tokens kostet, die Karten wurden aber nicht gespeichert. Kein Retry, kein User-Feedback (nur leere Liste). |
| coaching_service.py | 160-162 | validate_user_text exception → fallback JSON | OK, vertretbar. |
| coaching_service.py | 252-253 / 272-273 / 283-284 | 3× `except Exception: pass` beim JSON-Loads von phasen_details/gegenargument_details | **Silent data loss** — wenn ein Call korruptes JSON in der DB hat, wird es kommentarlos übersprungen. Kein Warn-Print. |
| coaching_service.py | 345-348 | Weekly-Report Sonnet-Fail → Fallback-Text ohne suggested_card | Vertretbar. |
| coaching_service.py | 379-381 | Top-Level Exception → return None | Top-Level fetch-all: schluckt alle Fehler. |
| precall_service.py | 90-92 | Top-Level `except Exception as e: print(...)` | Silent-Prints, aber Error-Tuple-Return. OK. |
| precall_service.py | 122-124 | Brave-Search-Fehler → None | Silent. User bekommt "Keine Suchergebnisse" Error zurück, Ursache nirgends geloggt außer stdout. |
| precall_service.py | 181-182 | `except Exception: pass` im Cost-Hook | Pattern konsistent mit Rest der Codebase. |
| precall_service.py | 190-192 | Claude-Briefing-Fehler → None | Silent. |

### Auskommentierter Code
Keine auskommentierten Code-Blöcke >1 Zeile gefunden.

### Ungenutzte Imports

| Datei | Import | Genutzt? |
|---|---|---|
| training_service.py | `from datetime import datetime` (Z.5) | **NICHT GENUTZT** (grep: `datetime` kommt nach Z.5 nie vor) → **LOW-01 Toter Import.** |
| training_service.py | `requests` (Z.4) | LIVE (Z.1303 ElevenLabs POST). |
| training_service.py | alle anderen | LIVE. |
| coaching_service.py | `from datetime import datetime, timezone` (Z.4) | **`timezone` NICHT GENUTZT** (nur `datetime`). → **LOW-02.** |
| coaching_service.py | `threading` (Z.3) | LIVE (`_analysis_lock`). |
| precall_service.py | Alle LIVE. | — |

### Legacy-Marker

| Datei | Zeile | Marker | Bedeutung |
|---|---|---|---|
| training_service.py | 25-27 | `# backwards compat` + `VOICE_MALE`/`VOICE_FEMALE = VOICE_POOL_*[0]['id']` | Dead-API-Backwards-Compat, grep-Check: `VOICE_MALE` / `VOICE_FEMALE` werden **nirgends extern referenziert** → Zombies. **LOW-03.** |
| training_service.py | 468-469 | `# Fall back to English pool for remaining languages` | OK, intentionale Sparse-Config. |
| training_service.py | 519 | `TRAINING_PERSONA_PROMPT_BASE = KUNDEN_PROMPT_TEMPLATE` | **Alias-Zombie.** grep-Check: `TRAINING_PERSONA_PROMPT_BASE` wird nirgends referenziert. **LOW-04.** |
| training_service.py | 674-677 | `# ══ Phase 08.5: v2-modular ... ═══` Comment-Block | Information. Beschreibt die Pipeline-Intention. |
| training_service.py | 711-714 | `"Placeholder v1"`-Detect Code | Defensive Fallback-Logik für leere DB-Seeds. OK. |
| training_service.py | 799 | `# Phase 08.5 v2-modular: resolve prompt version for FT traceability.` | OK, Dokumentation der Intention. |
| training_service.py | 854 | `# user_id defaults to 0 (D-07 Step F: per-user A/B routing deferred until user_id threading added)` | **TECHNICAL DEBT-MARKER.** Bestätigt Welle 1: user_id-Threading ist systematisch deferred, nicht nur in claude_service. |
| training_service.py | 1102-1105 | Analog user_id=0 + deferred. | Siehe oben. |
| precall_service.py | 1 | `# ── Phase 04.13: PreCall Intelligence ──` | OK. |
| coaching_service.py | - | Keine expliziten Legacy-Marker | — |

## Findings — Severity-sortiert

### HIGH

**HIGH-01 — `generate_postcall_analysis` ist profil-blind (dead parameter)**
- **Datei:** services/coaching_service.py:51-142
- **Symptom:** Die Sonnet-Post-Call-Coach-Funktion hat `profile_data=None` als Parameter, aber:
  1. `routes/learning.py:31-44` (Live Call Analysis) übergibt `profile_data` NICHT
  2. `routes/learning.py:261-273` (Training Post-Call Analysis) übergibt `profile_data` NICHT
  3. Der Funktionsbody liest `profile_data` kein einziges Mal (grep: nur in der Signatur)
- **Folge:** Sonnet-Post-Call-Coach generiert die 3 wichtigsten Lernkarten ohne Kenntnis von Produkt, USPs, Zielgruppe, Einwandkatalog. Die generierten Karten fühlen sich dadurch generisch an ("Wenn Kunde sagt X..."), ohne den Käufer-Kontext des Beraters zu berücksichtigen.
- **Parallelen:** Identisches Muster wie QA-Pipeline mit leerem `{}` (Welle 1). Signatur-Vortäuschung, Body-Nichtnutzung.
- **Fix-Scope:** Parameter-Drop ODER Parameter-Echte-Integration in POSTCALL_PROMPT (aktuell Z.12-48). Beides 30-60min.

**HIGH-02 — Training-PostCall-Analysis sendet erfundene Redeanteil-Zahlen an Sonnet**
- **Datei:** routes/learning.py:268-269
- **Symptom:** `redeanteil_berater=60, redeanteil_kunde=40` hardcoded — beide Werte werden niemals aus Trainingsdaten extrahiert, sondern als konstante Literal an die Sonnet-Post-Call-Analyse übergeben.
- **Folge:** Sonnet sieht in seinem Prompt: `Redeanteil Berater: 60% / Kunde: 40%` — und leitet daraus "Verbesserungsvorschläge" ab. Das sind sachlich falsche Trainingsdaten, auf deren Basis reales Coaching generiert wird.
- **Fix-Scope:** Entweder Redeanteil aus Training-Konversationshistorie berechnen (dauer_pro_speaker via Wortcount), oder Parameter als "optional / nicht gemessen" in den Sonnet-Prompt durchleiten.

**HIGH-03 — PreCall-Briefing fließt in keinen Live-LLM-Pfad**
- **Dateien:** services/precall_service.py + services/claude_service.py:387 (der tote Leser) + services/deepgram_service.py:309 (Writer) + routes/app_routes.py:454 (DB-Persister)
- **Symptom:** Der Output von `recherche_firma` wird an zwei Stellen persistiert:
  1. `ConversationLog.precall_briefing` (DB, durch app_routes.py:454)
  2. `ls.state['precall_briefing']` (In-Memory, durch deepgram_service.py:309)
  Konsum:
  1. DB-Feld wird nur in `session_detail.html` (Post-Call View) gerendert — OK, aber kein Einfluss auf Live-Assistent.
  2. `ls.state['precall_briefing']` wird NUR in `claude_service._build_system_prompt:387` gelesen — und diese Funktion ist DEAD (Welle 1 bestätigt).
- **Folge:** **Phase 04.13 + Quick-260414-kf8 sind faktisch Feature-Fakes.** Der Berater sieht vor dem Call ein Briefing, das nichts in den EWB-, Coach- oder QA-Pipelines bewirkt. User-Versprechen vs. Realität divergieren stark.
- **Fix-Scope:** `precall_briefing` muss in den lebenden Haiku-EWB-System-Prompt (`build_ewb_prompt` in services/ewb_pipeline.py) injiziert werden. ODER: in den `_build_coaching_prompt` (Z.404 claude_service). 1-2h.

**HIGH-04 — Alle 3 `log_pipeline_event`-Calls im training_service sind silent-fail**
- **Datei:** services/training_service.py:829, 901, 1225 + services/prompt_pipeline.py:240-244
- **Symptom:** `log_pipeline_event` importiert `services.finetune_logging.log_ft_event`. **`services/finetune_logging.py` existiert NICHT im Repo** (nur `ki_logik.py` in services/, keine finetune-Datei). Beim Import wird Exception gefangen, Print-Warning ausgegeben, Rückkehr. Keine Events erreichen irgendeinen FT-Logger.
- **Folge:** Alle drei Training-Module (`training_kunde`, `training_stimmung`, `training_scoring`) haben **keinerlei FT-Daten-Sammlung**. Die in Phase 08.5 aufgebaute "Pipeline-Traceability für Fine-Tuning" ist eine komplette Illusion. Auch in qa_pipeline.py (Welle 1-Finding) dieselbe Lücke — die Lücke ist **systematisch, nicht nur in training**.
- **Folge²:** Die Test-Suite `test_08_5_05_training_pipeline_t2.py` checkt **nur Source-Code-Presence** des Aufrufs (`assert 'log_pipeline_event(' in src`) — nicht die reale Log-Schreib-Funktionalität. False-Green-Tests.
- **Fix-Scope:** Entweder `services/finetune_logging.py` endlich implementieren (Schema in ConversationLog bereits da? prüfen) ODER die fake-Aufrufe entfernen + Tests korrigieren.

**HIGH-05 — training_service hat keinerlei Cost-Tracking für 5 Claude-Calls**
- **Datei:** services/training_service.py (Z.816, 868, 1003, 1187, 1265)
- **Symptom:** Phase 04.7.2 hat überall Cost-Tracker eingebaut (claude_service, coaching_service, precall_service). **training_service komplett übersprungen.** Einzige Cost-Tracker-Präsenz: TTS-Call (Z.1316).
- **Folge:** Training ist der teuerste Modus (Sonnet Scoring mit 3000 max_tokens + 5 Haiku-Calls pro Trainingsession). Im Founder-Dashboard laut Phase 04.7.2 unsichtbar.
- **Fix-Scope:** 30min pro Call-Site, 5× einfügen analog coaching_service.

### MEDIUM

**MEDIUM-01 — `build_sekretaerin_prompt` ist test-only (D-06 Migration unvollständig)**
- **Datei:** services/training_service.py:537 + 472 (SEKRETAERIN_PROMPT)
- **Symptom:** Unter Phase 04.9/D-06 wurden 3 Sekretärin-Typen in `SEKRETAERIN_TYPES` (Z.61-136) eingeführt. Die neue Route nutzt `build_sekretaerin_type_prompt` (Z.547). Die alte `build_sekretaerin_prompt` wird aus `routes/training.py` NICHT mehr gerufen — nur Tests + `_TRAINING_FALLBACKS['training_sek']` Z.691 referenzieren sie.
- **Folge:** ~25 Zeilen Prompt-Template + Build-Funktion als Legacy-Reste. Nicht dead im strengen Sinn (Fallback-Registrierung), aber Wartungslast.
- **Fix-Scope:** Entweder expliziter Legacy-Kommentar + Fallback-Rationale, oder Entfernung und Fallback-Registry anpassen auf `build_sekretaerin_type_prompt`.

**MEDIUM-02 — `_scoring_preamble` dead local variable**
- **Datei:** services/training_service.py:1107
- **Symptom:** `_scoring_preamble = _load_training_prompt_template('training_scoring', _scoring_version)` — das Ergebnis wird einer lokalen Variablen zugewiesen und **nie wieder verwendet**. Der Zweck war laut Kommentar Z.1105-1106 "if a non-placeholder row exists in DB, it will be used as system preamble". Genau das passiert nicht.
- **Folge:** DB-versioniertes Scoring-Template ist faktisch nicht aktivierbar. Fine-Tune-Tagging-Parity nur für prompt_version, nicht für tatsächlichen Prompt-Content.
- **Fix-Scope:** Entweder die Variable nutzen (als `system=_scoring_preamble` im Claude-Call Z.1187 und den Inline-Prompt in User-Message) oder löschen + Kommentar-Realigenierung.

**MEDIUM-03 — `training_service:806 _load_training_prompt_template` Parity-Only**
- **Datei:** services/training_service.py:806, 858-859
- **Symptom:** In `generate_response` und `generate_response_with_mood` wird `_load_training_prompt_template` aufgerufen, das geladene Template aber **nie verwendet** — der system_prompt wird vom Caller übergeben. Die Funktion dient nur dem "FT tagging parity"-Trick.
- **Folge:** DB-Versionierung hat keinen Einfluss auf die tatsächlich gerufenen Prompts. Pattern identisch zu MEDIUM-02.
- **Fix-Scope:** Dokumentieren oder echten Swap implementieren. Aktueller Zustand ist Cargo-Cult-Pipeline.

**MEDIUM-04 — Coaching_service `get_or_generate_weekly_report` Weekly-Sonnet ohne Profil-Kontext**
- **Datei:** services/coaching_service.py:183-378
- **Symptom:** Weekly-Report wird via Sonnet (Z.319) generiert. Prompt (Z.301-316) enthält aggregierte Wochen-Metriken, aber **kein Profil-Kontext** (Produkt, USPs, typische Einwände). Resultierender Report ist generisch ("Du hattest diese Woche X Calls mit Ø Score Y").
- **Folge:** Report fühlt sich unpersönlich an — parallelesystemisches Muster zu HIGH-01.
- **Fix-Scope:** Optional. 30-60min wenn gewünscht.

**MEDIUM-05 — Training-PostCall mit semantisch falschen Param-Mappings**
- **Datei:** routes/learning.py:267/271
- **Symptom:**
  - `kb_end=conv.kb_end or scoring.get('gesamt_score', 0)` — `kb_end` ist 0-100 Kaufbereitschaft, `gesamt_score` ist 0-100 Training-Score. Unterschiedliche Skalen mit identischer Range. Kein Type-Mismatch, aber semantisches Chaos.
  - `skript_abdeckung=scoring.get('gesamt_score', 0)` — explizit falsch. Skript-Abdeckung ist eine eigene Metrik, nicht das Gesamt-Score.
- **Folge:** Sonnet-Prompt enthält inkonsistente Metriken → schlechtere Lernkarten-Qualität.
- **Fix-Scope:** 30min. Parameter-Mapping sauber trennen oder None senden.

**MEDIUM-06 — Silent JSON-Loads mit `except Exception: pass` verschlucken Datenkorruption**
- **Datei:** services/coaching_service.py:252-253, 272-273, 283-284
- **Symptom:** In `get_or_generate_weekly_report` werden `phasen_details` und `gegenargument_details` von alten ConversationLog-Entries als JSON geparsed. Bei Parse-Fehler: `pass` — kein Warn-Log, kein Counter.
- **Folge:** Aggregation überspringt silent fehlerhafte Datensätze. Weekly-Report basiert auf "sauberen" Einträgen — datentechnisch OK, aber ohne Observability.
- **Fix-Scope:** Print-Warning mit call_id + kurzer Fehler. 10min.

**MEDIUM-07 — Precall-Cache ist pro-Prozess / nicht cross-worker**
- **Datei:** services/precall_service.py:17-18 (`_briefing_cache = {}`)
- **Symptom:** In-Memory dict. Bei Gunicorn mit mehreren Workern ist jeder Worker sein eigener Cache. TTL 5min ist nicht cross-worker shared.
- **Folge:** Ein Berater der zweimal das gleiche Firmenbriefing abruft, könnte bei Worker-2-Hit den Cache-Miss bekommen und eine neue Brave-Search + Haiku-Call auslösen. Kostenmehrung.
- **Fix-Scope:** Entweder Redis-Cache (Phase 05+) oder Accept-it-as-is (Single-VPS, 1 Worker).

### LOW

**LOW-01** — Ungenutzter Import `datetime` in training_service.py:5 (verifiziert: `datetime` wird im File nie referenziert).
**LOW-02** — Ungenutzter Import `timezone` in coaching_service.py:4 (nur `datetime` aus demselben Import wird genutzt).
**LOW-03** — Dead-Konstanten `VOICE_MALE`/`VOICE_FEMALE` in training_service.py:26-27 (nirgends extern referenziert).
**LOW-04** — Dead-Alias `TRAINING_PERSONA_PROMPT_BASE = KUNDEN_PROMPT_TEMPLATE` Z.519 (nirgends referenziert).
**LOW-05** — Training-TTS `g.user.id` via try/except nur im Request-Kontext — Background-Thread-Calls wären `user_id=None`. Aktuell nicht verwendet in Background, aber latenter Fallstrick.
**LOW-06** — Precall `print(f"[PreCall] Cache hit: {firmenname}")` Z.68 — Log-Noise ohne Log-Level, landet in stdout/journalctl.
**LOW-07** — `_repair_scoring_json` ist 75 Zeilen state-machine für JSON-Repair. Solides aber komplexes Stück — einziger Test: `_repair_scoring_json` gibt es in test_08_5_05_... nur indirekt. Formal untested.
**LOW-08** — `validate_user_text` Z.158-159 macht kein Exception-Handling um `json.loads(text[start:end])`. Wenn Claude `{broken:json}` liefert, crasht die Funktion ohne den Exception-Handler auf Zeile 160 zu erreichen, da `start` und `end` gefunden werden. Dann greift Z.160-162 doch → OK, aber Logik ist fragil.
**LOW-09** — `get_longterm_data` Z.423-425 hat eine Division durch 0 guards, aber `len(weekly[k]['kb_scores'])` kann 0 sein → **unmöglich weil Eintrag immer via w['kb_scores'].append() gefüllt wird**. Redundant aber safe.

## Cross-Module-Hypothesen für Master-Audit

1. **Silent-Logging-Systematik:** `log_pipeline_event` fällt überall (training × 3, qa_pipeline × 2) silent auf fehlende finetune_logging.py zurück. Das ist kein Einzelfall-Bug, sondern **Phase 08.5 wurde zu 50% gebaut**. Datei-Erstellung vergessen oder bewusst deferred — aber alle davon abhängigen Call-Sites denken sie liefern Daten. Master-Audit sollte **alle log_pipeline_event-Calls inventarisieren** und entweder finetune_logging.py schreiben oder die Calls removen.

2. **Profil-Blind-Sonnet-Pattern:** Drei Sonnet-Pfade (coaching.postcall, coaching.weekly, training.scoring) haben jeweils einen eigenen Umgang mit profile_data — `generate_scoring` nutzt es voll, `get_or_generate_weekly_report` ignoriert es, `generate_postcall_analysis` hat einen dead parameter. **Keine konsistente Policy.** Master-Audit: Policy definieren — entweder alle Sonnet-Coach-Calls bekommen profile_data oder keiner.

3. **Prompt-Versioning-Cargo-Cult:** `_load_training_prompt_template` wird an 4 Stellen in training_service aufgerufen. An **keiner einzigen** wird das Rückgabe-Template tatsächlich verwendet — nur die Version-ID für Tagging. Das ist "Observability ohne Effekt". Parallel dazu hat Welle 1 in claude_service ähnliches gezeigt (prompt_versions für EWB). Master-Audit: **ist die prompt_versions-Infrastruktur überhaupt für was außer Metadata-Tagging gut?**

4. **PreCall-Feature ist technisch tot:** Phase 04.13 + Quick-260414-kf8 haben Briefing generiert, in DB + state geschrieben. Der einzige LLM-Konsument ist DEAD CODE. Nutzerseitig zeigt Obsidian-Doku es als "läuft" — Code sagt "nie live konsumiert". Klassischer Nudelcode-Fall. Master-Audit: Feature-Liste gegen realen Code-Pfad prüfen (GSD `/gsd-audit-milestone`-Lauf auf Phase 04.13 könnte das ungeschönt zeigen).

5. **Cost-Tracking-Lücken Map:** Welle 1 → user_id=None systematisch. Welle 2 → training_service komplett ohne Cost-Tracker, coaching_service mit echter user_id, precall_service mit None. **Inkonsistente Governance.** Master-Audit: eine Cost-Tracking-Policy-Datei in .planning/decisions/ anlegen.

6. **Hardcoded-Magic-Values-Problem:** `routes/learning.py:261-273` enthält 6 hardcoded Werte für die Sonnet-Post-Call-Coach-Integration, von denen 2 semantisch falsch sind (MEDIUM-05), 1 komplett erfunden (HIGH-02), 1 dead parameter (HIGH-01). Eine gemeinsame Ursache: Training-Daten haben ein anderes Metriken-Schema als Live-Call-Daten, aber der Coach-Call ignoriert diesen Unterschied. Master-Audit: Training-vs-Live-Metriken-Schema explizit trennen oder Coaching zwei eigene Einstiegs-Funktionen geben.

7. **Test-False-Greens:** `test_08_5_05_training_pipeline_t2.py` prüft nur Source-Presence von `log_pipeline_event(` und `_load_training_prompt_template(`. Beide Infrastrukturen liefern real 0 Effekt (siehe HIGH-04, MEDIUM-02). Tests sind grün, Produktion ist kaputt. **Pattern: Assertions gegen Code-Text statt gegen Verhalten.** Master-Audit: alle `inspect.getsource(...)`-Asserts auflisten + durch Verhalten-Asserts ersetzen.

---

## Vertrauens-Hinweis

Geprüft direkt im Code (alle 3 Dateien komplett gelesen). Call-Graph via `Grep` codebase-weit. Cross-Check gegen Welle 1 (deep-dive-claude-service.md + deep-dive-pipelines.md) und profil-prompt-integration-matrix.md. Nichts aus Doku übernommen ohne Code-Verifikation.

Unsicher / nicht final geprüft:
- `CoachingReport` DB-Model-Schema (habe nur die Zugriffe im coaching_service gesehen, nicht die Column-Definitionen).
- Exakte Anzahl aktiver Worker (Gunicorn-Config für MEDIUM-07).
- Ob `session_detail.html` das DB-Feld `precall_briefing` wirklich rendert oder nur in die HTML schreibt ohne Anzeige.
