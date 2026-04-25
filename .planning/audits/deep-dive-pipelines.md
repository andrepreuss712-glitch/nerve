---
audit: deep-dive-pipelines
erstellt: 2026-04-24
stand_code: salesnerve/ HEAD 2026-04-24 (nach Phase 08.5 Fix-Runs, nach Korrektur 260424-h7u)
dateien:
  - services/qa_pipeline.py (533 Zeilen)
  - services/prompt_pipeline.py (255 Zeilen)
  - services/ewb_pipeline.py (89 Zeilen)
zweck: 100%-Deep-Dive der drei Live-Prompt-Pipelines. Erganzt/korrigiert profil-prompt-integration-matrix.md.
---

# Deep-Dive: qa_pipeline + prompt_pipeline + ewb_pipeline

## TL;DR

1. **NEUER HIGH-Befund (nicht in Vor-Audit):** `_qa_pipeline_dispatch` (claude_service.py:1488 + 1528) ruft `generate_qa_response(..., profile_data={}, ...)` mit **hartkodiertem leerem Dict**. Folge: `build_tabu_instruction` liefert IMMER leeren String, `build_protected_words` liefert IMMER leeres Set. Die Unknown-Einwand-Antworten laufen live komplett **ohne Tabu-Schutz und ohne Protected-Words-Gate**. Die Funktion sieht im Code vollstaendig aus, ist aber durch die Call-Site kastriert.
2. **NEUER HIGH-Befund:** `services/finetune_logging.py` **existiert nicht** im Repo (Glob = 0 Treffer). `log_pipeline_event` scheitert garantiert im ersten try-Block, printet "unavailable module=..." und returnt. ALLE FT-Log-Aufrufe (qa_pipeline: 2x, training_service: 3x) sind no-ops. Kein FT-Training-Datensatz wird geschrieben.
3. **Bestaetigt:** PreCall-Briefing fliesst weder in `build_ewb_prompt` noch in `build_profile_context` ein. Kein einziger Lese-Zugriff auf `ls.state['precall_briefing']` in den drei Dateien.
4. **Bestaetigt + prazisiert:** `build_profile_context` liest **genau 11 Profil-Felder + 1 Session-Override** (Matrix in Vor-Audit war korrekt; Zeilen unten).
5. **Neu:** `apply_tabu_filter` ist Legacy (deprecated-Docstring), wird aber weiterhin **live** im `_qa_pipeline_dispatch` (claude_service.py:1493, 1505, 1533) gerufen — parallel zum neuen Safety-Net-System. Doppelte Tabu-Logik: Safety-Net substituiert innerhalb generate_qa_response, dann filtert der Dispatcher nochmal mit der Legacy-Funktion und emittet bei Treffer `qa_soft_hint`. Inkonsistent.

## Funktions-Matrix (alle 3 Dateien zusammengefasst)

| Funktion | Datei:Zeile | Aufgerufen von | Status |
|---|---|---|---|
| `build_ewb_prompt` | ewb_pipeline.py:31 | claude_service.py:673 (analysiere_mit_claude), :742 (streaming) | **LIVE** |
| `_load_prompt_template` | ewb_pipeline.py:69 | ewb_pipeline.py:51 (intern) | **LIVE (INTERNAL)** |
| `_FALLBACK_V1_PROMPT` const | ewb_pipeline.py:23 | _load_prompt_template:89 | **LIVE (fallback)** |
| `resolve_prompt_version` | prompt_pipeline.py:31 | claude_service.py:672, :741; qa_pipeline.py:294; training_service.py (mehrere) | **LIVE** |
| `_load_active_variants` | prompt_pipeline.py:73 | resolve_prompt_version:57 (intern) | **LIVE (INTERNAL)** |
| `invalidate_resolver_cache` | prompt_pipeline.py:100 | tests/test_prompt_pipeline.py:105 + tests/test_ewb_pipeline.py (fixture) | **TEST-ONLY** (kein prod-Aufruf) |
| `build_profile_context` | prompt_pipeline.py:112 | ewb_pipeline.py:54 | **LIVE** (nur aus ewb_pipeline) |
| `_resolve_anrede` | prompt_pipeline.py:203 | build_profile_context:185 (intern) | **LIVE (INTERNAL)** |
| `log_pipeline_event` | prompt_pipeline.py:228 | qa_pipeline.py:331, :449; training_service.py:829, :901, :1225 | **ZOMBIE** (import-Target existiert nicht, siehe Finding HIGH-2) |
| `classify_utterance` | qa_pipeline.py:285 | claude_service.py:1458 (_qa_pipeline_dispatch) | **LIVE** |
| `generate_qa_response` | qa_pipeline.py:364 | claude_service.py:1488, :1528 | **LIVE** (mit kritischem Bug am Call-Site, siehe HIGH-1) |
| `match_faq` | qa_pipeline.py:484 | claude_service.py:1501 | **LIVE** |
| `build_tabu_instruction` | qa_pipeline.py:139 | prompt_pipeline.py:194 (im build_profile_context), qa_pipeline.py:377 (innerhalb generate_qa_response) | **LIVE** (2 Call-Sites) |
| `build_protected_words` | qa_pipeline.py:191 | qa_pipeline.py:438 (innerhalb generate_qa_response) | **LIVE (INTERNAL)** |
| `apply_tabu_safety_net` | qa_pipeline.py:254 | qa_pipeline.py:439 | **LIVE (INTERNAL)** |
| `apply_tabu_filter` | qa_pipeline.py:517 | claude_service.py:1493, :1505, :1533 (im _qa_pipeline_dispatch) | **LIVE trotz Docstring "Deprecated"** |
| `_get_embedding_model` | qa_pipeline.py:95 | match_faq:493 (intern) | **LIVE (INTERNAL, lazy)** |
| `_load_qa_template` | qa_pipeline.py:112 | classify_utterance:295 | **LIVE (INTERNAL)** |
| `_FALLBACK_CLASSIFIER_PROMPT` | qa_pipeline.py:48 | _load_qa_template:132 | **LIVE (fallback)** |
| `_FALLBACK_QA_RESPONSE_PROMPT` | qa_pipeline.py:63 | _load_qa_template:134 | **DEAD** — Placeholder-Template fuer module='qa_response'. `generate_qa_response` nutzt tatsaechlich **nicht** `_load_qa_template('qa_response', ...)` sondern den **hardcoded `_SYSTEM_PROMPT_QA` inline-string** (qa_pipeline.py:74-86). `_FALLBACK_QA_RESPONSE_PROMPT` hat **keinen Call-Site im Live-Pfad**. |
| `_SYSTEM_PROMPT_QA` const | qa_pipeline.py:74 | generate_qa_response:397 (intern) | **LIVE (hardcoded inline template)** |
| `_FALLBACK_RUECKFRAGE` | qa_pipeline.py:88 | generate_qa_response (mehrfach) | **LIVE (fallback)** |

## Prompt-Assembly-Flow (definitive Version)

### EWB-Pfad (Live-EWB, Haiku, Hauptsystem)

```
deepgram_service.analyse_loop  (thread)
  -> claude_service.analysiere_mit_claude / analysiere_mit_claude_streaming
      [liest ls.state['user_id'] + ls.state['session_anrede'] UNTER ls.state_lock]
      -> prompt_pipeline.resolve_prompt_version('ewb', user_id)
           [ENV-Check PROMPT_EWB_VERSION_OVERRIDE → cache → DB-Query prompt_versions(module='ewb', is_active=True) → 'unknown']
      -> ewb_pipeline.build_ewb_prompt(profile_data=None, anrede, version, user_id)
           -> _load_prompt_template(version)  -- prompt_versions(module='ewb', version=X, is_active=True) -> else _FALLBACK_V1_PROMPT
           -> prompt_pipeline.build_profile_context(user_id)
                -> live_session.get_active_profile()  -- liest ins Modul-Global
                -> 11 Profil-Felder (siehe unten)
                -> _resolve_anrede (ls.state['session_anrede'] UNTER lock > ki.ansprache > 'Sie')
                -> qa_pipeline.build_tabu_instruction(pdata)  -- 2-Sektionen-Block wenn komplette Pairs
           -> '\n'.join([template_text, '\n--- AKTIVES VERKAUFSPROFIL ---', context_block])
  -> claude_client.messages.create(system=system_prompt, model=haiku-4-5, max_tokens=400)
```

### QA-Pfad (Phase 08.5 Universal Response Loop)

```
analyse_loop  (nach analysiere_mit_claude Block)
  -> claude_service._qa_pipeline_dispatch(neuer_text, line_id, kontext, ls, sio)
      [D-02-Guard: skip wenn kw_fired_for_line == line_id]
      [Mutex-Guard: skip wenn slot1_variant_busy_until > now]
      [skip wenn _active_sid leer]

      -> _qa_load_tabu(profile_id, profile_daten)     -- DB + Profil-Fallback
      -> qa_pipeline.classify_utterance(text, kontext, user_id)
           -> resolve_prompt_version('classifier', user_id)
           -> _load_qa_template('classifier', version) -- DB miss -> _FALLBACK_CLASSIFIER_PROMPT
           -> claude_client.messages.create(haiku-4-5, max_tokens=150)
           -> _parse_json (aus claude_service)
           -> FT-log (no-op, s. HIGH-2) + cost-hook
           -> return {kategorie, confidence, einwand_zitat}

      Branch A: kategorie == 'einwand_unknown'
        if conf < 0.80: emit qa_soft_hint(reason=low_confidence)
        else:
          -> generate_qa_response(text, 'einwand_unknown', {}, anrede, '', user_id)    # <- LEERES DICT!
               -> build_tabu_instruction({}) -> ''                                      # <- IMMER LEER
               -> tabu_pairs = []                                                       # <- IMMER LEER
               -> is_low_confidence = (1.0 < 0.80) = False                              # confidence-Param = '' float-cast wirft nicht, aber…
               -> system_prompt = _SYSTEM_PROMPT_QA.format(tabu_block='', anrede='Sie')
               -> claude_client.messages.create(haiku-4-5, max_tokens=400)
               -> text = msg.content[0].text.strip()
               -> high-confidence Branch:
                   -> protected = build_protected_words({}, [])  -> set()
                   -> apply_tabu_safety_net(text, [], set())    -> text (no-op)
               -> return text
          if not _antwort: emit soft_hint(reason=empty_response)
          elif apply_tabu_filter(_antwort, _tabu_begriffe):       # <- Legacy-Filter mit ECHTER Tabu-Liste
              emit soft_hint(reason=tabu_filtered)                # <- aktuelle Firewall statt Alternative-Substitution
          else: emit qa_slot1(_antwort)

      Branch B: kategorie == 'frage'
        -> _qa_load_faqs(profile_id)  [DB ProfileFaq]
        -> match_faq(text, faqs, threshold=0.75)  [local sentence-transformers]
        if matched:
          if apply_tabu_filter(faq_antwort, _tabu_begriffe): emit soft_hint(tabu_filtered_faq)
          else: emit qa_slot1(faq_antwort) + increment FAQ.used_count in DB
        else:
          if conf < 0.80: emit soft_hint(no_faq_low_conf)
          else: generate_qa_response(text, 'frage', {}, anrede, '', user_id) -- SELBER BUG
                emit qa_slot1 oder soft_hint je nach Ergebnis

      Branch C: 'smalltalk_none' / 'einwand_known' -> no-op (Slot bleibt)
```

**Kritischer Unterschied zur `generate_qa_response`-Docstring (Zeile 367-372):** Laut Signature `confidence >= 0.80 → direct answer`, `confidence < 0.80 → Rueckfrage-Branch`. Aber der Caller `_qa_pipeline_dispatch` ruft `generate_qa_response` **nur im high-confidence-Branch auf** (`else` zu `if _conf < CLASSIFIER_CONFIDENCE_THRESHOLD`) und uebergibt `confidence=''` (leer!). Der Low-Confidence-Branch in `generate_qa_response` wird im Live-Pfad nie erreicht (`float('') -> ValueError` wird von `except` geschluckt, fallt auf `_FALLBACK_RUECKFRAGE`). **De facto verwendet die Produktion den Rueckfrage-Branch von generate_qa_response nie** — Low-Confidence wird bereits im Dispatcher als `qa_soft_hint` abgefangen.

### Welche Profil-Felder fliessen WIRKLICH in welchen Prompt? (Zeilen-Nachweis)

**`build_profile_context` (prompt_pipeline.py) — in EWB-Prompt via ewb_pipeline.py:54:**

| Feld | Zeile | Ausgabe-Praefix |
|---|---|---|
| `pdata.basis.unternehmen` | 150 | `Unternehmen: ...` |
| `pdata.basis.produktbeschreibung` | 152 | `Produkt: ...` |
| `pdata.basis.preismodell` | 154 | `Preismodell: ...` |
| `pdata.basis.usps` (list, join `, `) | 156-158 | `Alleinstellungsmerkmale (USPs): ...` |
| `pdata.basis.konsequenz` | 159 | `Konsequenz wenn Kunde nicht kauft: ...` |
| `pdata.basis.branche_kontext` | 163 | `Branchen-Kontext: ...` |
| `pdata.basis.eigene_formulierungen` (list) | 167-171 | `Eigene Formulierungen (User-Stil ...)` + Bullet-Liste |
| `pdata.basis.beweise` (list) | 174-178 | `Beweise (in Baustein "Beweis" einsetzen):` + Bullet-Liste |
| `pdata.ki.ton` | 181 | `Ton/Stil: ...` |
| `pdata.ki.ansprache` (nur Fallback wenn `session_anrede` leer) | 223 | Anrede-Resolution |
| Session-Override `ls.state['session_anrede']` (unter lock) | 216-220 | Anrede-Resolution |
| `pdata.basis.tabu_begriffe` (via `build_tabu_instruction`) | 192-198 | Tabu-Alternativen-Block |

**Total: 11 Profil-Felder + 1 Session-Override. Bestaetigt profil-prompt-integration-matrix.md Zeile 38-48 exakt.**

**NICHT gelesen (alle Zeilen durchgescannt):** `basis.name`, `basis.branche` Enum, `opener`, `erlaubnis`, `pitch`, `zielgruppe.*` (alle 7), `einwaende[]` (die ganze Liste), `faqs[]`, `kaufsignale`, `nogos`, `wettbewerber`, `uebergaenge`, `techniken.*`, `schmerzen.*`, `ki.stil`, `ki.antwortlaenge`, `ki.sensitivitaet`, `ki.zusatz`, `consent_text`, `ls.state['precall_briefing']`, `aktives_skript_inhalt`.

**`generate_qa_response` (qa_pipeline.py:364):**
- Was der Code theoretisch liest (Zeilen 377-388): `profile_data.daten.basis.tabu_begriffe`.
- Was de facto ankommt im Live-Pfad: **GAR NICHTS**, weil `_qa_pipeline_dispatch` `{}` uebergibt (claude_service.py:1489, :1529). `build_tabu_instruction({}) == ''`, `tabu_pairs == []`, `build_protected_words({}, []) == set()`, `apply_tabu_safety_net(text, [], set()) == text` (no-op).
- Anrede: ueber Parameter `anrede` — _qa_pipeline_dispatch liest `ls.state['session_anrede']` und reicht durch.
- FAZIT: Der Live-QA-Response-Prompt enthaelt NULL Profil-Felder. System-Prompt = `_SYSTEM_PROMPT_QA` (74-86) hardcoded + leerer Tabu-Block + Anrede.

**`classify_utterance` (qa_pipeline.py:285):**
- System-Prompt aus DB (`module='classifier'`) oder `_FALLBACK_CLASSIFIER_PROMPT`. **Keine Profil-Referenz.**
- User-Msg: `kontext` + letzte Utterance. Kein Profil-Inhalt.

## A/B-Router Analysis

**Cache-Mechanik (`resolve_prompt_version`):**
- Zwei Modul-Level Dicts: `_RESOLVER_CACHE: dict[(module, user_id), version]`, `_VARIANTS_CACHE: dict[module, list[version]]`.
- **NICHT thread-safe.** Python-`dict` Insert/Get ist in CPython wegen GIL atomar, aber das Lookup/Miss/Write-Pattern hat ein **kleines Race-Window**: zwei Threads koennen gleichzeitig `_VARIANTS_CACHE`-Miss erkennen und beide `_load_active_variants` laufen lassen. Kein Datenverlust, nur doppelte DB-Query + evtl. unterschiedliche Reihenfolge wenn Row-Writes dazwischenfunken. Akzeptabel in der Praxis, **nicht dokumentiert** als Einschraenkung.
- Cache wird nie invalidiert ausser via `invalidate_resolver_cache()` — im Live-Code (prod) gibt es keinen Call, nur in Tests. Prod-Restart = Cache leer. Admin-Aendert prompt_versions zur Laufzeit → Live-Nodes sehen Aenderung erst nach Neustart.

**ENV-Override:**
- Pattern `PROMPT_{MODULE}_VERSION_OVERRIDE` (Zeile 45). Dokumentiert `PROMPT_EWB_VERSION_OVERRIDE` in .env.example + nerve.service.
- **Nicht dokumentiert:** `PROMPT_CLASSIFIER_VERSION_OVERRIDE` / `PROMPT_QA_RESPONSE_VERSION_OVERRIDE` / `PROMPT_TRAINING_VERSION_OVERRIDE` etc. funktionieren mechanisch, sind aber nirgends als Ops-Tool aufgelistet.
- **FIRST-CHECK geht am Cache vorbei** (Zeile 45-48 before 51-54) — wird nie gecached. Jeder Call macht `os.environ.get`. Ok fuer Perf, aber dokumentieren.

**DB-Lookup (`_load_active_variants`):**
- SELECT versions WHERE `module=X AND is_active=True` ORDER BY version.
- Leer/Fehler → return `['unknown']`. Das `'unknown'` wird dann von `_load_prompt_template` wiederum nicht matchen und auf `_FALLBACK_V1_PROMPT` fallen. Kette ist **fail-open**, aber jeder Miss loggt `[Pipeline] variants empty` bzw. `[EWB] template miss`.
- Module im Code verwendet: `'ewb'` (ewb_pipeline), `'classifier'` und `'qa_response'` (qa_pipeline._load_qa_template). Seeds in app.py:845 fuer `'ewb'`. Seeds fuer `classifier`, `training_kunde`, `training_scoring`, `training_stimmung`, `qa_response` laut 08.5-01 Plan. **Nicht verifiziert** ob `qa_response` Seed wirklich existiert — der Code uebergibt `module='qa_response'` an `_load_qa_template` aber **`generate_qa_response` selbst ruft `_load_qa_template` gar nicht auf** (siehe Funktions-Matrix). Der `_FALLBACK_QA_RESPONSE_PROMPT`-Pfad ist tot. Nur `module='classifier'` wird live geladen.

## Tabu-System End-to-End

**Ort 1: EWB-Prompt-Injection (sauber implementiert)**
- `build_profile_context` (prompt_pipeline.py:192-198) importiert lazy `build_tabu_instruction` und haengt den 2-Sektionen-Block an. EWB-System-Prompt bekommt das ueber `build_ewb_prompt`.
- Block enthaelt: "Nutze bevorzugt die Alternative WENN es um UNSER Angebot geht / BEHALTE das Tabu-Wort BEWUSST wenn Schaden/Verlust beim Kunden / Respekt vor User-Gegenargumenten".
- **Funktioniert wie dokumentiert.**

**Ort 2: QA-Response-Prompt-Injection (im Code vorhanden, im Live-Pfad NEUTRALISIERT)**
- `generate_qa_response` ruft `build_tabu_instruction(profile_data)` (Zeile 377).
- Problem: `profile_data == {}` (Call-Site `_qa_pipeline_dispatch`). `build_tabu_instruction({}) == ''`. Tabu-Block wird nie in den QA-Response-Prompt injiziert.
- Safety-Net (`apply_tabu_safety_net`) laeuft mit `tabu_pairs=[]` → no-op.
- Protected-Words (`build_protected_words`) laeuft mit `tabu_begriffe=[]` → `set()`.

**Ort 3: Legacy-Gate im Dispatcher**
- `_qa_pipeline_dispatch` ruft `apply_tabu_filter(_antwort, _tabu_begriffe)` (claude_service.py:1493, 1505, 1533) **nach** `generate_qa_response` zurueckkehrt. `_tabu_begriffe` kommt aus `_qa_load_tabu(profile_id, profile_daten)` — hier ist die ECHTE Liste.
- Bei Treffer → `qa_soft_hint` statt Ausspielen. Das ist die **einzige tatsaechlich wirkende Tabu-Firewall** auf dem Live-QA-Pfad. Aber: Sie substituiert nicht (ersetzt kein Wort), sie **verwirft komplett** und ersetzt durch generischen "Neuer Einwand — noch kein Vorschlag"-Text.

**Inkonsistenz:** Im EWB-Pfad macht das System intelligente Wortersetzung (Alternative), im QA-Pfad wird die ganze Antwort verworfen. Der User-faehige Teil (Alternatives statt Verwerfen) ist implementiert, wird aber wegen Call-Site-Bug nie durch die Tabu-Liste getriggert.

## Fallback-Prompts — Aktualitaets-Check

| Fallback-Konstante | Wird genutzt? | Aktuell? |
|---|---|---|
| `_FALLBACK_V1_PROMPT` (ewb_pipeline.py:23) | Ja, wenn DB-Load scheitert oder Version='unknown' | **Phase-04-Artefakt-Gefuehl** — 3 Saetze, keinerlei Baustein-Struktur. Wenn DB mal leer ist, kollabiert die Prompt-Qualitaet total. |
| `_FALLBACK_CLASSIFIER_PROMPT` (qa_pipeline.py:48) | Ja, wenn `module='classifier'` DB-Miss | Aktuell; 4-Kategorien-JSON-Format stimmt mit Code-Validation (Zeile 316) ueberein |
| `_FALLBACK_QA_RESPONSE_PROMPT` (qa_pipeline.py:63) | **NEIN — Dead.** `_load_qa_template('qa_response', ...)` wird nirgends aufgerufen. `generate_qa_response` nutzt `_SYSTEM_PROMPT_QA` hardcoded | Text-Placeholders `{anrede}` + `{profile_context}` werden NIE gefillt weil der Call-Site fehlt |
| `_SYSTEM_PROMPT_QA` (qa_pipeline.py:74) | Ja, live in generate_qa_response:397 | Aktuell |
| `_FALLBACK_RUECKFRAGE` (qa_pipeline.py:88) | Ja, mehrere defensive Fallbacks | Aktuell; generische `'Frag nach: Wie meinen Sie das genau?'` |

## ls.state-Interaktionen

| Feld | Operation | Datei:Zeile | Kommentar |
|---|---|---|---|
| `session_anrede` | READ (unter state_lock) | prompt_pipeline.py:215-217 | Via `_resolve_anrede`. Korrekt gelockt. |
| `session_anrede` | READ (unter state_lock) | indirekt via claude_service.py:665, :734 (vorher geladen, uebergeben an `build_ewb_prompt`) | Korrekt gelockt. |
| `user_id` | READ (indirekt) | Caller ist verantwortlich (claude_service.py:665) — `build_profile_context` bekommt user_id als Param; wirft nicht, auch wenn 0 | — |
| `state` / `state_lock` | GET-ATTR (None-safe) | prompt_pipeline.py:211-213 | `getattr(ls, 'state', None)` — defensiv. |
| `precall_briefing` | — | **NIRGENDS** in ewb_pipeline, prompt_pipeline, qa_pipeline. **Bestaetigt Vor-Audit.** | Dead-Flow |

Fazit: Keine Schreibzugriffe auf `ls.state` aus den drei Dateien. Nur saubere Leser unter Lock.

## Verdachts-Stellen

### TODOs / FIXMEs
Keine `TODO`, `FIXME`, `XXX`-Marker in den drei Dateien.

### Silent Failures
- `prompt_pipeline.py:221` — `except Exception: pass` im `_resolve_anrede`. Schluckt alles, kein Log. Im Sinne der fail-open-Garantie ok, aber ein Debug-Print waere besser (Session-Anrede-Resolution-Bug schwer aufzuspueren).
- `qa_pipeline.py:389` — `except Exception: pass` beim tabu_pairs-Extract in generate_qa_response. Kein Log. Akzeptabel, aber leise.
- `qa_pipeline.py:321` — `except Exception: conf = 0.0` beim confidence-float-Cast. Kein Log. Okay.
- `qa_pipeline.py:319, 389, 321` — alle 3 still; das Gesamt-`except Exception as e: print(...)` am Funktionsende (Zeile 358, 477) faengt spaetere Faelle.
- `prompt_pipeline.py:243, 254` — `log_pipeline_event` swallowed. Wegen HIGH-2 laeuft diese Funktion permanent im Swallow-Pfad — alle FT-Events gehen verloren, nur ein `[Pipeline] log_pipeline_event unavailable` im Log.

### Auskommentierter Code (>1 Zeile)
Keine auskommentierten Bloecke in den drei Dateien.

### Ungenutzte Imports
Alle Imports verwendet. (`Optional` aus typing in ewb_pipeline.py:17 korrekt genutzt; `Any` in prompt_pipeline.py:19 nur fuer `_resolve_anrede`-Signatur; `threading as _threading` genutzt.)

### Legacy-Marker
- `ewb_pipeline.py:33` — default `version='v1-legacy'`. Name signalisiert "Phase < 08 Legacy-Prompt". Laut DB-Seed existiert diese Variante mit `is_default=1`.
- `qa_pipeline.py:517` — `apply_tabu_filter` Docstring sagt "Legacy / Deprecated: use build_tabu_instruction + apply_tabu_safety_net instead". Wird aber 3x in claude_service._qa_pipeline_dispatch live genutzt. **Deprecation-Marker ist unehrlich** — Funktion ist NICHT abgeloest, sondern parallel aktiv.
- `qa_pipeline.py:63` — `_FALLBACK_QA_RESPONSE_PROMPT` ist faktisch dead (siehe Fallback-Check).

### Hardcoded Prompt-Strings
- `_SYSTEM_PROMPT_QA` (qa_pipeline.py:74-86) — **hardcoded**, aber **dokumentiert als DB-Load-Kandidat** im Plan (`module='qa_response'`). Der DB-Pfad wurde angelegt (Seed + `_load_qa_template`-Zweig), aber **nicht verdrahtet**. Migration unvollstaendig.
- `_FALLBACK_V1_PROMPT` (ewb_pipeline.py:23) — bewusst hardcoded als last-resort.
- `_FALLBACK_CLASSIFIER_PROMPT` (qa_pipeline.py:48) — hardcoded als Fallback ok.

## Findings — Severity-sortiert

### HIGH

**H-1: `generate_qa_response` wird live mit leerem profile_data gerufen → Tabu-System im QA-Pfad komplett neutralisiert**
- Datei: claude_service.py:1488-1490 und :1528-1530
- Code: `generate_qa_response(neuer_text, 'einwand_unknown', {}, _anrede, '', _user_id)`
- Konsequenz: `build_tabu_instruction({}) == ''`, `tabu_pairs == []`, `build_protected_words({}, []) == set()`, `apply_tabu_safety_net` no-op. Die ganze Phase-08.5-Korrektur 1+3 (260424-h7u) hat im QA-Dispatch **null Wirkung**. Die Tabu-Firewall besteht hier nur noch aus dem Legacy-`apply_tabu_filter` Gate, das komplette Antworten verwirft statt zu substituieren.
- Confidence-Parameter wird als `''` (leerer String) uebergeben → `float('')` wirft → `except` schluckt → Antwort geht zum `_FALLBACK_RUECKFRAGE`. Effektiv: **Jede einwand_unknown-Antwort im High-Confidence-Branch stottert zunaechst durch den Fallback oder kommt nur durch weil das aeussere try im Call-Pfad den Fehler abfaengt**. Zu pruefen: wirft `float('')` oder nicht? Python: `float('')` wirft `ValueError`. → Hits `except Exception as e: print("[QA] generate_qa_response failed: ...")` → returns `_FALLBACK_RUECKFRAGE`. **Das ist der wahrscheinliche Grund fuer die Beobachtung "die KI sagt immer nur 'Frag nach: Wie meinen Sie das genau?'" im Live-Betrieb.**
- Fix: (a) `_qa_pipeline_dispatch` muss `_profile_daten` (bereits geladen auf Zeile 1452) als profile_data uebergeben, (b) `confidence=_conf` statt `''` uebergeben.

**H-2: `services/finetune_logging.py` existiert nicht — alle FT-Logs sind no-ops**
- Glob `services/finetune_logging*` → 0 Treffer.
- `prompt_pipeline.log_pipeline_event:240` tries to import und faellt im except-Block mit `[Pipeline] log_pipeline_event unavailable module=...` silent zurueck.
- Callers: qa_pipeline.py:331 (classifier), :449 (qa_response); training_service.py:829, :901, :1225.
- Konsequenz: Es gibt derzeit **keine persistierten FT-Events aus Live-Calls**, nur die bereits bestehende `FtQaEvent`-Tabelle aus Phase 08.5-01 (DB-Modell exists, aber kein Writer-Code).
- Impact: Trainingsmaterial-Sammelsystem (geplant fuer eigene KI laut CLAUDE.md) existiert **konzeptionell**, aber im Code wird aktiv nichts gesammelt.
- Fix: Entweder `services/finetune_logging.py` mit `log_ft_event(phase, model, module, **kwargs)` anlegen, das in `FtQaEvent` oder eine `FtEvent`-Tabelle schreibt — oder `log_pipeline_event` direkt auf die DB binden.

**H-3: `_FALLBACK_QA_RESPONSE_PROMPT` dead — DB-gesteuerte QA-Response-Prompts nicht verdrahtet**
- `_load_qa_template` hat einen `module='qa_response'` Zweig (Zeile 133-134), aber `generate_qa_response` ruft ihn nicht auf. Stattdessen hardcoded `_SYSTEM_PROMPT_QA` inline.
- Placeholders `{anrede}` + `{profile_context}` in `_FALLBACK_QA_RESPONSE_PROMPT` sind nie gefillt.
- Konsequenz: QA-Response-Prompt ist nicht A/B-fahig. Aenderungen nur via Code-Deploy, nicht via DB-Row wie bei EWB/Classifier.

### MEDIUM

**M-1: `apply_tabu_filter` Deprecated-Docstring widerspricht Live-Usage**
- qa_pipeline.py:520 sagt "Deprecated: use build_tabu_instruction + apply_tabu_safety_net instead".
- Aber 3 live-Aufrufe in claude_service.py:1493, :1505, :1533.
- Wegen H-1 ist das sogar die **einzige wirksame** Tabu-Firewall im QA-Pfad. Entweder Deprecated-Label entfernen, oder die neuen Funktionen korrekt wiring und Legacy entfernen.

**M-2: Resolver-Cache nicht thread-safe (minor Race)**
- `_VARIANTS_CACHE`-Miss + `_load_active_variants`-Call + Dict-Set ist nicht atomar. In hot-start kann DB-Query doppelt laufen.
- Impact niedrig (nur Perf-Drift ms, keine Datenkorruption). Aber: dokumentieren oder `_threading.Lock()` wie bei `_MODEL` in qa_pipeline.

**M-3: Resolver-Cache wird nie live invalidiert**
- `invalidate_resolver_cache()` existiert, hat aber **keinen Prod-Caller**.
- Folge: Aendert Admin/App-Code die `prompt_versions`-Tabelle, sehen Live-Worker die Aenderung erst nach Neustart. Kein Hot-Reload-Mechanismus (wo UI/API Variants editiert). Sollte dokumentiert oder fixed werden (z.B. nach SIGHUP oder nach POST /api/admin/prompts).

**M-4: `_FALLBACK_V1_PROMPT` ist zu duenn fuer Fallback**
- 3 Saetze, keine Baustein-Struktur, keine Branche, keine Beweise. Wenn DB-Load mal scheitert, geht EWB-Qualitaet von "strukturiert" auf "hope-for-the-best".
- Fuer Prod-Fallback sollte wenigstens die v2-modular-Kern-Instruktion gemirrort sein.

**M-5: `session_anrede` Silent-Swallow in `_resolve_anrede`**
- Debugging von Anrede-Bugs (Du vs Sie Durchbrueche D-15) schwer ohne Log.
- Kleines `print(f"[Pipeline] anrede-resolve error: {e}")` vor `pass` wuerde helfen.

### LOW

**L-1: "Neuer Einwand — noch kein Vorschlag" ist Unicode-escape**
- claude_service.py:1467: `'Neuer Einwand — noch kein Vorschlag'`. Kosmetisch inkonsistent zum restlichen Code (einige Stellen Unicode-literal, andere `—` escape). Keine Bug-Wirkung.

**L-2: `build_ewb_prompt` print-Statement mit Length-Log**
- ewb_pipeline.py:65 — `print(f"[EWB] v{version} assembled user_id={user_id} len={len(prompt)}")`. Jeder Analyse-Tick (2s) loggt das. In 14-Stunden-Session = 25.200 Log-Zeilen.

**L-3: `build_profile_context` returnt `''` ohne explizites Logging**
- prompt_pipeline.py:142 — `if not pdata: return ''`. Kein Debug-Print. Caller (`build_ewb_prompt`) detects leeren Kontext und fallback-log'd nicht. Schwer zu diagnostizieren "warum hat mein Profil nicht gegriffen".

**L-4: `CONFIDENCE_THRESHOLD` in qa_pipeline.py (0.80) dupliziert `config.CLASSIFIER_CONFIDENCE_THRESHOLD`**
- qa_pipeline.py:45 setzt hardcoded `CONFIDENCE_THRESHOLD = 0.80`. claude_service nutzt aber `config.CLASSIFIER_CONFIDENCE_THRESHOLD` (env-faehig). `generate_qa_response` nutzt den hardcoded Wert (Zeile 393). Wenn Admin env auf 0.95 stellt, wirkt das NUR im Dispatcher, nicht in generate_qa_response's internen Low-High-Branch. Derzeit wegen H-1 nicht erkennbar, wird aber nach Fix relevant.

## Cross-Module-Hypothesen fuer Master-Audit

1. **"Leere profile_data"-Pattern pruefen in allen claude_service-Call-Sites.** `_qa_pipeline_dispatch` uebergibt `{}` — gibt es weitere Caller von `generate_qa_response` oder `build_tabu_instruction` die das Profil nicht korrekt durchreichen? (Test-Mocks zaehlen nicht.)

2. **FT-Logging-Ghost.** `log_pipeline_event` als Zombie erklaert warum GSD-Doku "FT-Training-Daten werden gesammelt" behauptet, aber keine Eintraege in `FtQaEvent` oder analogen Tabellen existieren. In Master-Audit sollte die `FtQaEvent`-Tabelle in der Live-DB (VPS) inspected werden — Erwartung: leer oder fast leer.

3. **DB-gesteuerte Prompt-Variants Ende-zu-Ende:** Welche Module ausser `ewb` und `classifier` haben aktive DB-Rows? `qa_response` Seed existiert laut Plan — aber `generate_qa_response` laedt nicht aus DB. Pruefen: welche Module werden real genutzt vs. nur geseedet-und-vergessen.

4. **ENV-Override-Surface:** Nur `PROMPT_EWB_VERSION_OVERRIDE` ist in .env.example + nerve.service dokumentiert. `PROMPT_CLASSIFIER_VERSION_OVERRIDE` funktioniert mechanisch (Zeile 45 Code: generisch uppercase), ist aber Ops-unsichtbar. Sollte dokumentiert oder explizit deaktiviert werden.

5. **ARCHITECTURE.md-Abweichung:** Das File (Zeile 151, 296) behauptet `_load_prompt_template` + Fallback; behauptet aber **implizit**, dass precall_briefing injected wird (Zeile 93, 183-185). Der Input-Kontext warnt korrekt davor. Bestaetigt: Doku ist optimistisch, Code ist die Wahrheit.

6. **Lessons fuer die Prompt-Redesign-Phase:** (a) Jede neue Prompt-Assembly-Funktion muss einen "smoke-test" Call-Site-Audit bekommen (Contract-First-Regel aus CLAUDE.md). (b) Deprecated-Docstrings mit aktiven Callern sind ein Nudelcode-Symptom — entweder Doc updaten oder Caller entfernen. (c) Ein log-Pipeline-Event das importiert und silent wegfaellt ist ein klassischer Silent-Drift.

---

*Audit abgeschlossen 2026-04-24 durch komplettes Lesen der 3 Dateien + Call-Graph-Grep aller Public-Funktionen + Cross-Check mit claude_service.py:1405-1540, app.py:845-914, config.py:42-43. Vor-Audit profil-prompt-integration-matrix.md ist in den Kern-Befunden bestaetigt; zwei neue HIGH-Befunde (H-1 Leeres profile_data, H-2 finetune_logging fehlt) waren im Vor-Audit nicht enthalten.*
