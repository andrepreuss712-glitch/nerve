---
audit: deep-dive-deepgram-keyword
erstellt: 2026-04-24
dateien:
  - services/deepgram_service.py (476 Zeilen)
  - services/einwand_keyword_matcher.py (271 Zeilen)
---

# Deep-Dive: deepgram_service.py + einwand_keyword_matcher.py

## TL;DR

1. **HIGH:** `kw_fired_for_line` wird im Matcher mit `ls.state['line_id']` gesetzt — aber der Matcher feuert auf **Interim**-Transkripten, während `ls.state['line_id']` erst von `analyse_loop` auf Final-Ergebnisse geschrieben wird. Das Flag zeigt auf eine **alte Line-ID** und der D-02-Guard schützt nicht zuverlässig (Race).
2. **HIGH:** `_profile_daten = ls.get_active_profile()` wird **ohne jeden Lock** aus dem Deepgram-Callback-Thread aufgerufen (Zeile 111) — zwar kopiert `get_active_profile()` intern mit `active_profile_lock`, aber `ls.state.get('mic_muted', False)` wird direkt davor im `state_lock` gelesen — ordentlich; Befund OK beim Nach-Prüfen. **Downgrade auf LOW.**
3. **MEDIUM:** CONCERNS.md behauptet `ls.state['precall_briefing']` werde NIE gelesen — **falsch.** `claude_service.py:387` liest es in `_build_system_prompt()`. Allerdings: `_build_system_prompt` selbst ist laut CONCERNS.md Dead-Code (nicht im Live-Pfad). Das bedeutet `precall_briefing` fließt in die tote Funktion → **effektiv Dead-Reader**, aber Divergenz zur Audit-Aussage "never read".
4. **MEDIUM:** Silent `except Exception: pass`/nur-print in 5+ Pfaden (Zeilen 27, 148, 150, 178, 388, 465, 472, 476, 255 in matcher).
5. **LOW-MEDIUM:** `reset_keyword` nirgendwo im Live-Code aufgerufen — nur in Tests. Dead-API, Kommentar bei `_make_on_utterance_end` erklärt warum.

---

## deepgram_service.py

### Funktionen

| Funktion | Zeile | Aufgerufen von | Status |
|---|---|---|---|
| `_get_speaker(result)` | 16 | `_make_on_message` → on_message | LIVE |
| `_make_on_message(sid)` | 31 | `_open_deepgram_connection` | LIVE |
| `_make_on_open(sid)` | 154 | `_open_deepgram_connection` | LIVE |
| `_make_on_error(sid)` | 160 | `_open_deepgram_connection` | LIVE |
| `_make_on_close(sid)` | 168 | `_open_deepgram_connection` (POLISH-48) | LIVE |
| `_make_on_utterance_end(sid)` | 183 | `_open_deepgram_connection` | LIVE — **aber Handler-Body ist `pass`** (Phase 06.2-r1 Feedback-Loop-Schutz) |
| `_open_deepgram_connection(sid, mode)` | 195 | `handle_start_live_session` | LIVE |
| `_close_deepgram_connection(sid)` | 240 | `handle_stop_live_session`, `handle_disconnect` | LIVE |
| `register_audio_handlers(sio)` | 266 | `app.py:1775` | LIVE (einmal beim Start) |
| `handle_start_live_session(data, sid)` | 268 | SocketIO `start_live_session` | LIVE |
| `handle_stop_live_session(sid)` | 359 | SocketIO `stop_live_session` | LIVE |
| `handle_audio_chunk(data, sid)` | 373 | SocketIO `audio_chunk` | LIVE |
| `handle_disconnect(sid)` | 392 | SocketIO `disconnect` | LIVE |
| `handle_mute_mic(data, sid)` | 401 | SocketIO `mute_mic` | LIVE |
| `handle_manual_ewb(data, sid)` | 414 | SocketIO `manual_ewb` | LIVE |

**Keine Dead-Funktion in diesem Modul.** Alle Closures werden bei `register_audio_handlers`-Aufruf in Flask-SocketIO registriert und laufen event-getrieben.

### ls.state-Interaktionen (deepgram_service.py)

| Feld | Operation | Zeile | Unter `state_lock`? |
|---|---|---|---|
| `mic_muted` | READ | 108 | JA |
| `slot1_variant_busy_until` | READ | 133 | JA |
| `slot1_variant_busy_until` | WRITE | 137 | JA |
| `active_sid` | WRITE | 291 | JA |
| `session_anrede` | WRITE | 302 | JA |
| `precall_briefing` | WRITE | 309 | JA |
| `aktives_skript_inhalt` | WRITE | 318 | JA |
| `skript_bloecke` | WRITE | 319 | JA |
| `ft_session_id` | WRITE | 350 | JA |
| `user_id` | WRITE | 351 | JA |
| `market` | WRITE | 352 | JA |
| `language` | WRITE | 353 | JA |
| `mic_muted` | WRITE | 406 | JA |

**Auch indirekt (nicht via ls.state_lock):**
- `ls.is_paused` via `ls.pause_lock` — Zeile 38, 381
- `ls.conversation_log` via `ls.log_lock` — Zeile 70–75 (APPEND)
- `ls._second_sp_seen` via `ls._sp2_lock` — Zeile 48–51
- `ls._log_last_sp` via `ls._log_sp_lock` — Zeile 54–57
- `ls._merge_pending` via `ls._merge_lock` — Zeilen 83–100
- `ls.buffer_lock` (nur READ `ls.analysiert_bisher`) — Zeilen 138–139, 442–443
- `ls.session_start_time`, `ls.berater_words`, `ls.kunde_words` via `ls.speech_lock` — Zeilen 285–288

**Lock-Disziplin:** Sauber. Alle ls.state-Zugriffe sind unter `state_lock`. Kein nackter Zugriff.

**Was SOLLTE geschrieben werden laut Architektur, wird aber nicht?**
- Keine bekannten offenen Writes. `precall_briefing` wird geschrieben wie geplant.
- Divergenz zur CONCERNS.md-Aussage Line 128 "precall_briefing — Never read": siehe Findings.

### PreCall-Briefing-Lifecycle

**Flow:**
1. Client POSTet Briefing an `/api/precall/recherche` → speichert im Frontend.
2. Client startet Call → emits `start_live_session` mit `precall_briefing` im `data`-Payload.
3. `handle_start_live_session` Zeile 275: `precall_briefing = data.get('precall_briefing', None)`.
4. Zeile 305–310: truncate auf 2000 chars, schreibt nach `ls.state['precall_briefing']`.
5. **Lese-Pfad:**
   - `claude_service.py:387` — liest in `_build_system_prompt()`. Aber: `_build_system_prompt` ist laut CONCERNS.md ab Phase 08 **NICHT mehr im Live-Pfad** (analysiere_mit_claude nutzt `build_ewb_prompt` ≠ `_build_system_prompt`).
   - `routes/app_routes.py:273` — liest beim `/api/beenden` für Persist in ConversationLog.precall_briefing (Fallback wenn Client nichts sendet).
6. Session-Ende: `reset_session` (live_session.py:350) setzt auf `None` zurück.

**Befund:** Briefing wird gespeichert, beim Call-Ende persistiert — aber **nicht in den aktiven EWB-Prompt injiziert**. Das bestätigt den CONCERNS.md-Befund teilweise. Es gibt EINEN Reader-Pfad (claude_service.py:387), der aber im toten `_build_system_prompt` liegt.

**Divergenz zur CONCERNS.md:**
- CONCERNS.md Zeile 128 ("Never read") ist technisch ungenau. Korrekt wäre: "Nur im toten `_build_system_prompt`-Pfad gelesen — erreicht keinen Live-Claude-Call."
- ARCHITECTURE.md behauptet Integration — ist falsch.

### Transcript-Buffering + Keyword-Dispatch

**Final-Pfad (is_final=True, Zeilen 42–100):**
1. `stabilize_speaker` via `_speaker_lock`.
2. `next_line_id()` generiert neue Line-ID.
3. SocketIO `transcript` (`type=final`) an Client emitted.
4. Append in `ls.conversation_log` unter `ls.log_lock`.
5. Satz-Merger: in `ls._merge_pending` gepuffert, Timer auf `MERGE_WINDOW_S` — `ls._flush_segment` triggert analyse_trigger.

**Interim-Pfad (is_final=False, Zeilen 101–148):**
1. SocketIO `transcript` (`type=interim`) emitted.
2. **Keyword-Match:**
   - Mute-Check (`ls.state['mic_muted']`).
   - `ls.get_active_profile()` → Einwaende-Liste.
   - `matcher.match_with_dedup(text, einwaende)` — per-sid Matcher aus `ls.get_matcher(sid)`.
   - Bei Hit: emit `keyword_einwand_match` + spawn `streame_auto_variante` (Slot 1) via `sio.start_background_task`.
3. Slot-1 busy-guard via `slot1_variant_busy_until` verhindert parallele Haiku-Calls.

**Wer schreibt wer liest Transcript-Buffer:**
- **Writer** `ls.conversation_log`: `deepgram_service.py:71` (nur dieses Modul). Log-Lock sauber.
- **Writer** `ls.transcript_buffer`: `ls._flush_segment` (in live_session.py).
- **Reader** `ls.analysiert_bisher`: analyse_loop in claude_service.py liest in buffer_lock.

### Interim-Latenz-Overhead des Matchers

- Pro Interim-Transcript (ca. 100ms-Intervalle laut CONCERNS.md): 8 kompilierte Regex-Searches in `match_keyword` → typisch <1ms (SDK compiled). Kein Caching pro Session nötig.
- Zusätzlich `_match_profile_einwand` — Loop über profile_einwaende (typisch 5–20).
- Bei Match zusätzlich Haiku-Call asynchron, **nicht blocking** für Deepgram-Thread.

**Kein echtes Latenz-Problem sichtbar.** CONCERNS.md-Einschätzung LOW-MEDIUM stimmt.

### Speaker-Diarisierung

- Kommt von **Deepgram** (`diarize=is_meeting`, Zeile 224) — nur im Meeting-Modus aktiv.
- Cold-Call-Modus: `diarize=False` → kein Speaker-Tracking von Deepgram. Das ist DSGVO-konform (Single-Speaker-Architektur, Berater-Stimme only).
- Lokal: `stabilize_speaker` (live_session.py:227) + `SPEAKER_DEBOUNCE_S` decken Flackern ab.
- `_get_speaker(result)` Zeile 16: Nimmt `speaker` pro Wort, wählt Majority-Vote. Silent fallback `return None` bei Exception (Zeile 27) — grenzwertig, aber ok.

### DSGVO-Check

**Audio-Persistenz:** **NEIN.** 
- `handle_audio_chunk` Zeile 387: `connection.send(data)` — leitet direkt an Deepgram WS weiter, kein `open(..., 'wb')`, kein DB-Write, kein Disk-IO.
- Kein Buffer für Audio-Bytes (nur Deepgram-Chunk-Counter `_chunk_counts[sid]`).
- Ephemeral Processing bestätigt.

**Transcript-Persistenz:**
- `conversation_log` wird in-memory gepflegt, am Session-Ende in DB gespeichert (via `/api/beenden`).
- Zeile 66 `print(f"[DG] [{sp_label}] {text}")` — **Transcript wird im Server-Log geprintet.** Das ist ein DSGVO-Grauton: stdout → systemd → journalctl auf Hetzner = persistiert auf deutschem Server. Anonymisierung in Phase 04.19 Pipeline passiert NACH diesem Print.
- **DSGVO-Risiko LOW** (Server in Frankfurt/Nürnberg, verschlüsselte Disks), aber erwähnenswert.

**Deepgram-Endpoint:** `DEEPGRAM_HOST` → laut Kommentar POLISH-49 `api.eu.deepgram.com` default. EU-Data-Residency erfüllt, sofern config.py das so hält.

### WebSocket-Lifecycle

- **Start:** `handle_start_live_session` → `_open_deepgram_connection` → `client.listen.websocket.v("1")` → `connection.start(options)`.
- **Reconnect:** **Kein Reconnect-Logik.** Wenn Deepgram-WS stirbt, muss Client neu `start_live_session` senden. Launch-Readiness-Review (20260421) hat bereits vorgeschlagen: exponential backoff in `_open_deepgram_connection`. Offen.
- **Ende:** `handle_stop_live_session` oder `handle_disconnect` → `_close_deepgram_connection` → `connection.finish()`.
- **Error:** `_make_on_error` emitted `dg_error`, aber keine Recovery.
- **Close:** `_make_on_close` POLISH-48 — emitted `dg_close` an Client.

### Token/Cost-Usage-Tracking

- `_cost_opened_at[sid] = time.time()` bei Open.
- `_close_deepgram_connection` berechnet `seconds → minutes` und ruft `log_api_cost('deepgram', 'nova-2', units=minutes, unit_type='per_minute', context_tag='stt')`.
- Sauber, aber: **user_id=None** wird hardcoded übergeben (Zeile 252). Kein per-User-Tracking. Bei Kosten-Aggregation global pro Session_id. Fair-Use Limits wären so nicht direkt enforceable.

**Befund (LOW):** STT-Cost-Hook hat keinen user_id-Bezug → Cost-Tracking ist pro SID, nicht pro User. Für Abrechnung später müsste user_id nachgezogen werden.

---

## einwand_keyword_matcher.py

### Funktionen

| Funktion | Zeile | Aufgerufen von | Status |
|---|---|---|---|
| `_get_ls()` | 27 | `match_with_dedup` (intern) | LIVE (lazy) |
| `_profile_gegenargument(pe)` | 132 | `_match_profile_einwand` | LIVE |
| `_match_profile_einwand(kw, list)` | 145 | `match_keyword` | LIVE |
| `match_keyword(transcript, list)` | 176 | `EinwandKeywordMatcher.match_with_dedup`, tests, qa_pipeline (mirror) | LIVE |
| `EinwandKeywordMatcher.__init__` | 216 | `live_session.get_matcher` | LIVE |
| `.match_with_dedup(transcript, list)` | 221 | `deepgram_service.py:116` | LIVE |
| `.reset_keyword(keyword)` | 260 | **Nur Tests** — `test_einwand_keyword_matcher.py:395` | **DEAD-API in Production** |
| `.reset_all()` | 268 | **Nur Tests + 1 Kommentar-Referenz** | **DEAD-API in Production** |

**Wichtig:** `reset_keyword` und `reset_all` werden im Live-Code **nirgendwo** aufgerufen. `_make_on_utterance_end` (deepgram_service.py:183) hat einen Kommentar (Phase 06.2-r1), der begründet warum: Feedback-Loop-Schutz — Berater liest Gegenargument vor, Dedup würde sonst neu triggern. 10s-Dedup pro Keyword reicht.

**Konsequenz:** Matcher lebt nur während der sid-Session; bei `drop_matcher(sid)` in `handle_stop_live_session`/`handle_disconnect` wird Instanz komplett verworfen. Reset-APIs sind damit effektiv tot — ok so, aber Dead-Code-Signal.

### DEFAULT_KEYWORDS — Nutzungs-Check

| Keyword | In `KEYWORD_TO_PROFILE_ALIASES`? | Echter Use (Alias → DB-Kategorie)? |
|---|---|---|
| `keine_zeit` | JA | `zeit`, `zeit/aufschub`, `keine zeit`, `zeitdruck` — **`zeit` = DB-kategorie "Zeit" ✓** |
| `zu_teuer` | JA | `preis`, `kosten/preis`, `zu teuer`, `kosten`, `budget` — **`preis` = DB-kategorie "Preis" ✓** |
| `kein_interesse` | JA | `bedarf`, `kein bedarf`, `kein interesse` — **`bedarf` = DB-kategorie "Bedarf" ✓** |
| `ueberlegen` | JA | `zeit/aufschub`, `entscheider`, `entscheidungstraeger`, `ueberlegen`, `bedenkzeit` — **OVERLAPS mit `keine_zeit` (zeit/aufschub) und `falscher_ansprechpartner` (entscheider)** |
| `skeptisch` | JA | `vertrauen`, `skepsis`, `skeptisch` — **DB-kategorie "Vertrauen"/"Skepsis" ✓** |
| `haben_schon` | JA | `wettbewerb`, `vergleich`, `haben schon`, `konkurrenz` — **DB-kategorie "Wettbewerb" ✓** |
| `falscher_ansprechpartner` | JA | `entscheider`, `entscheidungstraeger`, `falscher ansprechpartner` — **OVERLAP mit `ueberlegen`** |
| `kompliziert` | JA | `datenschutz`, `kompliziert` — **DB-kategorie "Datenschutz" — Zuordnung fragwürdig!** |

**Befund (MEDIUM):**
- `kompliziert` → `datenschutz`: Semantik stimmt nicht. "Zu kompliziert" heißt nicht DSGVO-Problem. Wahrscheinlich plan-draft Residuum, nicht geprüft.
- `ueberlegen` und `falscher_ansprechpartner` teilen `entscheider` — bei Doppelmatch wird das Erste gefundene Profil zurückgegeben (Feldpriorität kurzlabel>kategorie>typ). Kann zu falscher Profil-Einwand-Zuordnung führen.

### KEYWORD_TO_PROFILE_ALIASES — Stale-Check

**Kommentar Zeile 111–113:** "Verifiziert an echten DB-Profilen aus database/salesnerve.db". Laut STATE.md:344 wurde das in Phase 06.2 gemacht.

**Aktuelle DB-Enums (laut Kommentar):** Preis, Zeit, Bedarf, Vertrauen, Wettbewerb, Entscheider, Datenschutz, Skepsis.

| Alias | Match zu DB | Status |
|---|---|---|
| `preis`, `zeit`, `bedarf`, `vertrauen`, `wettbewerb`, `entscheider`, `skepsis` | Direkt ✓ | OK |
| `datenschutz` → nur `kompliziert` zugeordnet | **Semantisch falsch** | STALE/FEHLZUORDNUNG |
| `skepsis` → nur bei `skeptisch` | Overlaps `vertrauen` — aber eigene | OK |
| `entscheidungstraeger` (ohne Umlaut) | Muss in DB als `Entscheidungstraeger` existieren — sonst toter Alias | UNSICHER |
| `kosten/preis`, `zeit/aufschub`, `kein bedarf` | Alte Demo-Profile typ-Feld | Wahrscheinlich noch im Seed-Data — OK wenn Seed aktiv |

**Action:** Querlauf gegen `database/salesnerve.db`-Seed-Daten empfohlen; speziell `kompliziert → datenschutz` prüfen.

### Dedup-Guard — Verhalten

- **Fenster:** 10s pro Keyword.
- **Thread-Safe:** `threading.Lock`.
- **False positives möglich:** Wenn Berater innerhalb 10s dasselbe Keyword sagt (z.B. "also das Preis-Thema..." + "zum Preis zurück..."): zweiter Match suppressed. Gewollt.
- **False negatives möglich:** Interim-Transkripte kommen schneller als Sätze fertig werden. Wenn "zu teu" in Interim 1 und "zu teuer" in Interim 2 innerhalb 10s beide matchen würden — suppressed ist OK; **aber** wenn Kunde erst "zu teuer, aber..." sagt und 3s später "zu aufwendig" (kompliziert) sagt — unabhängig, beides feuert. Richtig so.

### kw_fired_for_line — Integration mit qa_pipeline

**Befund (HIGH):** Race zwischen Final-Line und Interim-Match.

**Details:**
1. `match_with_dedup` läuft im Deepgram-Thread auf **Interim**-Transcripts.
2. In Zeile 252: `current_line = _ls.state.get('line_id')`.
3. **`ls.state['line_id']` wird nur von `analyse_loop` in claude_service.py geschrieben** (Zeilen 1127, 1332) — und zwar als ID des gerade klassifizierten Final-Segments.
4. In `_make_on_message` Zeile 44 wird zwar `ls.next_line_id()` für das Final-Segment geholt — aber NIE nach `ls.state['line_id']` geschrieben.

**Konsequenz:**
- Wenn Interim-Text "zu teuer" auf Line N+1 matched, setzt Matcher `kw_fired_for_line = N` (alte Final-Line).
- Analyse-Loop bearbeitet Line N+1 später, liest `kw_fired_for_line = N ≠ N+1` → **D-02 Skip greift nicht** → qa_pipeline klassifiziert trotzdem → Slot 1 wird doppelt bedient (Keyword-Slot 1 spawn + qa_pipeline-Slot 1 spawn).

**Rettung:** Der `slot1_variant_busy_until`-Guard (6s bzw. 8s) fängt den Race oft ab — aber nicht deterministisch:
- Keyword setzt busy bei `now + 6`.
- qa_pipeline liest busy vor seinem Emit (claude_service.py:1435) — skipt wenn busy.
- Wenn Keyword-Haiku innerhalb 6s fertig ist und qa_pipeline 7s später läuft → busy-Guard tot → Doppel-Emit möglich.

**Test-Kontext:** `tests/test_08_5_03_integration.py:52` "test_match_hit_sets_kw_fired_for_line" — setzt `ls.state['line_id']='line-42'` MANUELL und erwartet `kw_fired_for_line='line-42'`. Test passt nur, weil er line_id vorher selbst setzt. **Test validiert nicht den Produktions-Race.**

**Fix-Richtungen:**
- (a) Matcher sollte `line_id` aus dem eigenen Interim-Kontext bekommen (z.B. als Argument) — nicht aus ls.state.
- (b) Oder: `ls.state['line_id']` muss auch auf Interim-Segmente aktualisiert werden.
- (c) Oder: Keyword-Match erst auf Final-Events schalten (Latenz-Trade-off).

---

## Verdachts-Stellen

### TODOs

**Keine TODO/FIXME/XXX-Marker** in beiden Dateien gefunden (`grep -n "TODO\|FIXME\|XXX"` = 0).

### Silent Failures (except Exception: pass oder print-only)

| Datei | Zeile | Code | Severity |
|---|---|---|---|
| deepgram_service.py | 27–28 | `_get_speaker` → `except Exception: return None` | LOW (graceful) |
| deepgram_service.py | 147–148 | Keyword-Match-Block → `except Exception as _kw_err: print(...)` — Fehler wird verschluckt, nur stdout | MEDIUM |
| deepgram_service.py | 149–150 | on_message outer try → `except Exception as e: print(...)` | LOW |
| deepgram_service.py | 177–179 | on_close emit-wrap → `except Exception: pass` — **stumm** | LOW |
| deepgram_service.py | 254–256 | Cost-Hook → `except Exception as _e: print(...)` | LOW |
| deepgram_service.py | 260–262 | connection.finish → `except Exception as e: print(...)` | LOW |
| deepgram_service.py | 355–356 | FT-Session-Insert → `except Exception as _e: print(...)` — DB-Fail wird nur geprintet, FT-Logging bricht silent ab | MEDIUM |
| deepgram_service.py | 427–430 | `ls.get_active_profile()` → `except Exception: profile_daten = {}` | LOW |
| deepgram_service.py | 454–461 | record_ewb_click error paths 3x | LOW |
| deepgram_service.py | 463–465 | pip_stream_error emit → `except Exception: pass` | LOW |
| deepgram_service.py | 471–476 | manual_ewb spawn error | LOW |
| einwand_keyword_matcher.py | 33–35 | `_get_ls` → `except Exception: pass` — lazy-load schlägt silent fehl | LOW (dokumentiert) |
| einwand_keyword_matcher.py | 255–256 | kw_fired_for_line Write-Block → `except Exception: print(...)` | LOW |

**MEDIUM-Kandidaten:**
- Zeile 147 (Keyword-Match-Wrapper): Wenn der Matcher eine Exception wirft (z.B. defekte Regex in Profil-Einwand), wird es nur geprintet. Live-Debugging unmöglich, kein Event an Client. Siehe CONCERNS.md 412–423 — gleicher Befund.
- Zeile 355 (FT-Insert-Fail): Bei DB-Down würde die Session ohne FT-Logging weiterlaufen. Das ist bewusst so (Session > Analytics), aber sollte eine metric sein.

### Auskommentierter Code (>1 Zeile)

**Keiner gefunden.** Beide Dateien sind sauber. Nur explikative Kommentare, keine Code-Leichen.

### Ungenutzte Imports

**deepgram_service.py:**
- `import time as _time_mod` Zeile 7 — verwendet in Zeile 134 (`_time_mod.monotonic()`). OK.
- `import time` Zeile 2 — verwendet mehrfach. OK.
- `import time as _time` Zeile 284 (innerhalb Funktion, shadow) — verwendet Zeile 286. OK aber unsauber (doppelt importiert).

**Befund (LOW):** Doppel-Import `time` (modul-level) + `time as _time` (function-level) + `time as _time_mod` (modul-level). Dreifache Aliase auf dasselbe Modul. Kosmetik.

**einwand_keyword_matcher.py:**
- Alle Imports verwendet. Sauber.

### Legacy-Marker / Phase-Tags

| Datei | Zeile | Marker |
|---|---|---|
| deepgram_service.py | 12 | "Phase 04.7.2 STT-minute tracking" |
| deepgram_service.py | 105 | "BUG-10-LAT Wave 2" |
| deepgram_service.py | 169 | "POLISH-48" |
| deepgram_service.py | 185 | "06.2-r1" |
| deepgram_service.py | 196 | "POLISH-49" |
| deepgram_service.py | 209 | "POLISH-48: smart_format=True..." |
| deepgram_service.py | 245 | "Phase 04.7.2 Cost-Hook" |
| deepgram_service.py | 281 | "POLISH-22 Bugfix" |
| deepgram_service.py | 289 | "Phase 06" |
| deepgram_service.py | 293 | "Phase 08 D-14" |
| deepgram_service.py | 314 | "T-06-07" |
| deepgram_service.py | 322 | "Phase 04.7.1" |
| deepgram_service.py | 366 | "POLISH-48" |
| deepgram_service.py | 409 | "06.1-r2 r4" |
| deepgram_service.py | 435 | "06.1-r2 BUG-14c" |
| deepgram_service.py | 467 | "POLISH-38.1" |
| einwand_keyword_matcher.py | 46 | "POLISH-46 Flexions-Fix" |
| einwand_keyword_matcher.py | 24 | "D-02 Phase 08.5" |
| einwand_keyword_matcher.py | 244 | "Phase 08.5 D-02" |

**Viele Phase-Tags, aber alle erklärend — keine Code-Leichen.** Jedes Kommentar ist deskriptiv ("was hier gelöst wurde"). Das ist gut für Post-Mortem, macht den Code aber kommentar-lastig.

### Deepgram-SDK-Versions-Abhängigkeit

- Import: `from deepgram import DeepgramClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions` (Zeile 4).
- `client.listen.websocket.v("1")` — SDK v3-Muster (laut Deepgram Python SDK docs >= 3.0).
- Event-Handler nutzen SDK-Events: `Transcript, Open, Error, Close, UtteranceEnd` — SDK v3-konform.
- `getattr(w, 'speaker', None)` defensiv — würde SDK-Attribut-Umbenennung überleben.
- `result.channel.alternatives[0].words` — hardcoded SDK-Response-Schema. Bei SDK-Breaking-Change tot.

**Befund (LOW):** SDK-Version nicht gepinned (CONCERNS.md 383 bestätigt). `requirements.txt` muss geprüft werden (ausserhalb dieses Audits). Integration-Test auf Interim-Transcript-Format empfohlen.

---

## Findings — Severity-sortiert

### HIGH

1. **`kw_fired_for_line` Race — D-02 Guard unzuverlässig.**
   - Matcher setzt `kw_fired_for_line = ls.state['line_id']`, aber dieser Wert spiegelt die ZULETZT analysierte Final-Line, nicht die aktuelle Interim-Line.
   - qa_pipeline vergleicht `kw_fired_for_line == line_id` (aktuelle Final-ID): stimmen selten überein.
   - Back-up-Guard `slot1_variant_busy_until` fängt NICHT deterministisch ab (Timing-abhängig).
   - **Folge:** Doppel-Emit `keyword_einwand_match` + `qa_slot1` auf identische Kunden-Äußerung möglich.
   - **Fix:** line_id als Argument an match_with_dedup übergeben, oder ls.state['line_id'] auch für Interim-Segmente aktualisieren.

2. **`reset_keyword`/`reset_all` — Dead-API in Production.**
   - Beide werden im Live-Code nie aufgerufen. Nur in Tests. Matcher-Lifecycle = sid-Lifetime (drop_matcher).
   - Code-Bloat + verwirrend für neue Entwickler (Klasse sieht "stateful mit Reset" aus, ist aber effektiv per-sid-throwaway).
   - **Fix:** Entweder entfernen und Kommentar "Matcher lebt nur pro sid" an die Klasse; oder im Cold-Call-Consent-Flow nach Mute-Toggle reset_all() aufrufen (falls Semantik gewünscht).

### MEDIUM

3. **CONCERNS.md-Divergenz: precall_briefing "never read".**
   - Stimmt nicht. `claude_service.py:387` liest es. Allerdings in `_build_system_prompt`, das laut gleicher CONCERNS.md als Dead-Code geführt wird.
   - **Divergenz:** Doku-Aussage "never read" ist überbewertet; Realität ist "liest-in-totem-Pfad". Für Master-Audit relevant: der PreCall-Flow hat eine Zombie-Brücke zu einer toten Funktion.

4. **`kompliziert → datenschutz` Alias fragwürdig.**
   - Semantik stimmt nicht. "Zu kompliziert" ≠ DSGVO-Problem. Vermutlich Plan-Draft-Rest.
   - **Fix:** Alias entfernen oder durch eigenen `datenschutz`-Keyword in DEFAULT_KEYWORDS ersetzen (Regex: `datenschutz|dsgvo|gdpr|privat(spha|sphar)e`).

5. **Alias-Overlap `ueberlegen` ↔ `falscher_ansprechpartner` auf `entscheider`.**
   - Beide mappen auf gleiches Profil-Einwand-Kategorie. Bei echtem Profil-Match wählt der erste Regex-Hit → Reihenfolge in DEFAULT_KEYWORDS bestimmt Gewinner.
   - **Fix:** Klar trennen oder in Reihenfolge dokumentieren.

6. **Silent-fail in Keyword-Match-Wrapper (Zeile 147).**
   - Alle Exceptions im Keyword-Pfad werden zu stdout-Print. Bei defektem Profil-Regex oder ls.state-Corruption kein Client-Feedback.
   - **Fix:** `sio.emit('kw_error', ...)` + metric.

7. **FT-Session-Insert-Fail silent (Zeile 355).**
   - Bei DB-Down läuft Session ohne FT-Logging weiter → Analytics-Lücke, aber Session funktioniert. Akzeptabel, sollte als metric instrumentiert werden.

### LOW

8. **Transcript wird per `print` geloggt (Zeile 66, 129).**
   - systemd/journalctl-Persistenz auf Frankfurt-Hetzner — DSGVO-technisch unkritisch, aber erwähnenswert: Anonymisierung läuft nach Print.

9. **Dreifach-Import von `time`.**
   - `time`, `_time_mod`, `_time` — kosmetisch.

10. **STT-Cost-Hook hat `user_id=None`.**
    - Cost-Tracking pro sid, nicht pro User. Bei Fair-Use-Enforcement später nachzuziehen.

11. **Kein Reconnect-Logic für Deepgram-WS.**
    - Bereits in Launch-Readiness-Review dokumentiert (20260421). Hier bestätigt.

12. **SDK-Version nicht gepinned.**
    - Bestätigung CONCERNS.md 383.

13. **`on_close` emit-wrap mit `except: pass` (Zeilen 177–179).**
    - Wenn sio-emit fehlschlägt: silent. Close-Info geht verloren. LOW.

---

## Cross-Module-Hypothesen für Master-Audit

Basierend auf dem Mustern in diesen 2 Dateien — Verdachtsmomente für andere Module:

1. **ls.state-Felder mit "zombie readers/writers":** CONCERNS.md listet `ewb_top2` (orphaned writer), `precall_briefing` (orphaned reader). Wahrscheinlich mehr Legacy-State, besonders nach Phase 08-Refactor. Master-Audit sollte **jedes Feld in ls.state** auf Writer/Reader-Paar prüfen — nicht nur die in CONCERNS.md gelisteten 5.

2. **line_id-Inkonsistenz:** Der Befund oben (line_id wird nur im Final-Pfad generiert, aber in Interim gelesen) ist ein **Muster**: Es gibt zwei Zeitachsen (Interim ~100ms, Final/Analyse ~2s), die über ls.state kommunizieren. Master-Audit sollte **alle ls.state-Felder, die von zwei Threads mit unterschiedlicher Frequenz berührt werden**, auf Race-Conditions prüfen: `slot1_variant_busy_until`, `active_hint`, `ewb_buttons`, `readiness_score`.

3. **Dead-API-Pattern (reset_keyword/reset_all):** Wahrscheinlich weitere Funktionen in anderen Modulen, die seit Phase 06/07/08 nicht mehr gerufen werden. Methodisch: grep jedes `def name(` → prüfe in Codebase ob `name(` irgendwo außer Tests/Docs.

4. **Silent-Failure-Density:** deepgram_service.py hat ~10 `except: print()`-Blöcke. Master-Audit sollte pro Modul die Silent-Failure-Density zählen. >5 pro 500 Zeilen = Warning-Signal.

5. **Alias-/Taxonomie-Drift:** `KEYWORD_TO_PROFILE_ALIASES` hat einen semantisch falschen Eintrag (`kompliziert → datenschutz`). Weitere Taxonomien: Profil-Kategorien (Preis/Zeit/Bedarf/...), Phasen-Labels (Opener/Discovery/...), Einwand-Typen. Sollten gegen DB-Seed-Daten verifiziert werden.

6. **Phase-Tag-Kommentar-Dichte:** Beide Dateien tragen viele "Phase X/POLISH-Y"-Tags. Master-Audit könnte einen "Legacy-Indicator-Score" pro Modul errechnen: Anzahl Phase-Tags / Zeilenanzahl. Module mit hohem Score = hohe Änderungsfrequenz = hohes Nudelcode-Risiko.

7. **`_build_system_prompt` als Lock-In-Zombie:** CONCERNS.md bestätigt, dass `_build_system_prompt` tot ist, aber precall_briefing fließt dort hinein. Master-Audit sollte alle "toten" Funktionen auf Zombie-Brücken prüfen: liest die tote Funktion State, der nur für sie gesetzt wird?

8. **Tests vs. Runtime-Realität:** `test_08_5_03_integration.py` validiert `kw_fired_for_line` korrekt — aber setzt `line_id` manuell. Der echte Race (Interim-vs-Final) wird nicht getestet. Master-Audit: "welche Tests setzen Preconditions, die in Produktion so nicht vorkommen?"
