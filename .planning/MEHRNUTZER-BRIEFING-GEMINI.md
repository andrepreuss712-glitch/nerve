# BRIEFING: Ist NERVE mehrnutzerfaehig? — Bestandsaufnahme am Code, Bitte um Zerlegung

**Deine Rolle:** Du bist die dritte, unabhaengige Sicht. **Deine Aufgabe ist NICHT, diese Befunde zu bestaetigen, sondern sie zu ZERLEGEN.** Suche gezielt nach dem, was hier uebersehen, falsch eingeordnet oder zu optimistisch bewertet wurde. Du hast Leseerlaubnis auf `C:\Users\andre\dev\salesnerve` — pruefe strittige Punkte selbst am Code nach, statt mir zu glauben.

**Kontext in drei Saetzen:** NERVE ist ein Live-Assistent fuer Verkaufsgespraeche (Deepgram-Spracherkennung + Claude-Analyse, Flask + Socket.IO, Postgres, ein Gunicorn-Worker mit 64 Threads). Das Produkt verkauft **Tempo** — eine Antwort, die spuerbar spaeter kommt, ist im Live-Gespraech wertlos. Vor dem Early-Access-Start (Plaetze werden verkauft, mehrere Berater telefonieren gleichzeitig) ist die Frage: **Traegt die Architektur mehrere gleichzeitige Nutzer?**

**Heute erstmals gemessen (Prod, echter Anruf):** Analyse-Aufruf Ø 1988 ms, Coaching-Aufruf Ø 2714 ms (beide Haiku 4.5), Phasen-Erkennung 1742 ms, Kaltakquise-Einschaetzung 1642 ms, Einwand-Antwort erstes Token nach 1035 ms / komplett 3250 ms, Post-Call-CRM-Schritt 15194 ms.

---

## TEIL 1 — WAS BELEGT FUNKTIONIERT

1. **Zustand pro Anruf ist gemacht.** Phase `08.23.2.PERSID` (18 Dokumente, 6 Plaene, alle mit SUMMARY) hat den Live-Pfad auf per-Session umgestellt. `_session_state[sid]`, `_per_sid_profile`, `_per_sid_transcript`, `_per_sid_coaching_buffer`, `keyword_matchers` — alle sid-gekeyt (`services/live_session.py:373`, `:278`, `:379`, `:385`, `:18`). Inventur-Ergebnis: **0 Fundstellen belegter Datenvermischung zwischen zwei parallelen Anrufen.**
2. **Wachtertests sichern das ab.** `tests/test_no_live_global_state.py` (AST-Sweep, `_PENDING_MIGRATION == frozenset()` → jede neue nicht-per-sid Zuweisung ist sofort rot), `tests/test_persid_concurrency.py` (27 KB, zwei Sessions in zwei verschiedenen Orgs), `test_session_scoping.py`, sechs `test_persid_*`-Dateien.
3. **Auslieferung sauber:** alle 11 `sio.emit` im Live-Pfad tragen `room=sid`, kein Broadcast (verifiziert `deepgram_service.py:127/214/259/292/320/609/854/1006/1237/1275`, `claude_service.py:1051`).
4. **Mandanten-Fundament existiert.** Phase `TENANT-FOUND`: `resolve_tenant_uuid_for_user` (`database/db.py:108-123`), RLS-Hook `@event.listens_for(SessionLocal, "after_begin")` → `set_config('app.tenant_id', ..., true)` (`database/db.py:88-105`), Request-Publikation `app.py:2284-2293`, Daemon-Klammer `services/slow_lane.py:823/:843`. RLS aktiv (ENABLE + FORCE + Policy `tenant_isolation`, fail-closed) auf **8 Tabellen**: `crm.accounts/contacts/account_memory/meetings/user_preferences`, `public.suggestion_reactions/rubric_score/abstain_log`.
5. **Kapazitaet wurde schon einmal erhoeht:** gunicorn `--threads 4 → 64` (Phase STABIL-1), DB-Pool 20+15 mitgezogen (`config.py:42-50`).
6. **Zwei Sperren pro Session existieren bereits** (Objektebene): `AnrufAnonymisierer._lock` (`anonymization.py:197`, Instanz pro sid) und `EinwandKeywordMatcher._lock` (`einwand_keyword_matcher.py:219`).

---

## TEIL 2 — WAS BELEGT NICHT TRAEGT

### A. Durchsatz: drei Ein-Bearbeiter-Schleifen
- `analyse_loop` (`services/claude_service.py:1217`, Start `app.py:2415`): EIN Daemon-Thread, `for sid in active_sids:` (`:1237`), sequentieller Claude-Aufruf pro SID.
- `coaching_loop` (`claude_service.py:2029`, Start `app.py:2416`): identisches Muster (`:2042`).
- `slow_lane_consumer` (`services/slow_lane.py:790`, Start `app.py:2434`): EINE globale Queue (`:145`), ein Consumer, alle Mandanten sequentiell. **Das ist der Post-Call-Pfad (15 s pro Anruf).**
- Der Code beziffert es selbst (`claude_service.py:1224-1230`): *"O(N) SEQUENTIAL … N=1: ~1-3s, N=5: ~5-15s (KRITISCH), N=20: >20s (nicht mehr Echtzeit) … Ab N=5 und Cycle-Zeit > 3s: Migration zu ThreadPoolExecutor … Accepted for EA (50 users max)."* Zusatz im Code: **"Messung ausstehend"** — die Schwellwerte sind geschaetzt.
- **Nicht** betroffen: der Einwand-Knopf. `streame_manual_ewb_variante` laeuft in einem eigenen Thread pro Klick (`deepgram_service.py:1133 def _run()`), nicht in der Schleife.

### B. Ein globaler Riegel fuer alle Sessions
`_session_state_lock` (`live_session.py:374`), **105 Erwerbsstellen in 8 Dateien** (claude_service 41, live_session 28, deepgram_service 22, app_routes 4, weitere 10). Bewusst **nicht** reentrant (`:308-310`). Keine Sperre pro Session fuer `_session_state[sid]`.
Zwei Produktionsvorfaelle belegt: 30.07. py-spy-Abzug — 1415 von 1416 blockierten Frames an einer Stelle (`live_session.py:112-115`); 31.07. — *"Thread-3 (coaching_loop), gehalten=133.2s"* (`live_session.py:471-473`).
Gegenmassnahmen existieren als Notausgang, nicht als Loesung: `wait_session_state_lock_free()` (2-s-Probe, `:148-174`), `_TracedLock` mit Halter-Aufzeichnung, Wachhund `_lockwatch_tick()`.

### C. Kein Zeitlimit auf den Live-KI-Aufrufen
`claude_client` (`claude_service.py:27`) bewusst ohne `timeout` erzeugt. Ein Client MIT Limit existiert (`http_llm_client`, 20 s/45 s), wird von **keinem** Live-Aufruf benutzt. SDK-Default `anthropic 0.86.0`: read=600 s, max_retries=2 → Worst Case ~30 min fuer EINEN haengenden Aufruf, waehrend dessen **alle anderen Sessions in derselben Schleife stillstehen**. Der Wachhund ueberwacht den Riegel, nicht die Schleife.

### D. Ein Nutzer kann die DSGVO-Schwaerzung fuer alle abschalten
`services/anonymization.py:19-24`: `is_pipeline_healthy` (Modul-global) + `_error_timestamps` (rollierendes 10-Min-Fenster ueber ALLE Anrufe gemischt). `>5` Fehler in 600 s → `is_pipeline_healthy = False` **prozessweit** (`:534`). Fehler aus Anruf A schalten die Schwaerzung fuer Anruf B ab.

### E. Post-Call-Analyse durch globale Sperre serialisiert
`services/coaching_service.py:59` `with _analysis_lock:` umschliesst einen Sonnet-Aufruf (`:84`, `long_running=True`, 45 s Limit). Zwei gleichzeitig beendete Anrufe: der zweite wartet die komplette Generierung des ersten ab.

### F. Drei HTTP-Eingaenge ohne Eigentuemer-Pruefung (sicherheitsrelevant)
- `routes/app_routes.py:184-189`: Stufe-1-SID-Aufloesung in `/api/beenden` scannt `_session_state` nach geposteter `call_id` **ohne** `user_id`-Vergleich (Stufe 2 auf `:201` filtert korrekt). Fremde `call_id` → fremder Session-State → fremdes Transkript (`:283`), Briefing (`:245`), Sprachstatistik (`:257-261`).
- `routes/app_routes.py:782` und `:828`: `calls`-UPDATE gefiltert nur auf `id`, kein `user_id`. Schreibend (`ended_at`, `conversation_log_id`, `call_mode`, `score_breakdown`).
- `routes/app_routes.py:2076-2085`: `sid` aus dem Query-String, keine Eigentuemer-Pruefung, liefert `active_profile_data`/`_briefing` des fremden Zustands.
Alle drei sind `@login_required`, aber ohne Besitzpruefung. Ghost-SID-Guards pruefen **Lebendigkeit**, nicht **Eigentuemerschaft**.

### G. RLS deckt nur 8 Tabellen
Ohne RLS und rein anwendungsseitig gefiltert: `calls` (im Code vermerkt: *"calls hat KEINE RLS"*, `live_session.py:937`), `call_events`, `intent_event`, `transcript_segments`, `conversation_logs`, `profiles`, `users`, `api_cost_log`, `audit_log`. Granularitaet uneinheitlich (profiles org-weit, calls user-weit).

### H. Kein Kapazitaetslimit, kein Aufraeumer, kein Timeout
- `handle_start_live_session` prueft **nichts** ausser Auth. Kein Zaehler, kein 503-bei-voll. Der 65. Nutzer startet und bekommt keinen Thread.
- Zombie-Pfade, vom Code selbst benannt: Riegel >2 s bei `pop_session_state` → *"bleibt im Speicher liegen und wird beim naechsten Aufraeumen mitgenommen"* (`live_session.py:692-695`) — **ein solcher Sweeper existiert nicht** (kein Kandidat im Repo). Riegel >2 s bei `stash_ended_session` → Snapshot wird verworfen (`:735-739`). Deepgram-`finish()` nach 5 s → *"wird NICHT aufgeraeumt und NICHT erneut finish() gerufen"* (`deepgram_service.py:578-582`).
- Tab-Schliessen: `beforeunload` setzt nur `returnValue` (`static/pip-launcher.js:3880-3885`), **kein `sendBeacon`** → `calls.ended_at` bleibt NULL bis zum 2-h-Fallback oder nie.
- Kein Server-Timer beendet je eine Session.

---

## TEIL 3 — DIE ENGINE (`nerve_rt/`) — Rohbau, nicht Ersatzteil

- **Zweck laut Docstring** (`nerve_rt/services/session_manager.py:1-12`): *"per-connection lifecycle … Replaces Flask's live_session.py globals + claude_service.py analyse_loop threading … NO module-level globals. NO threading.Lock. All state is per-session."* FastAPI auf Port 8001 neben Flask auf 5000.
- **Loest den Durchsatz architektonisch:** `_Session` pro WS-Verbindung (`:101-151`), drei nebenlaeufige Tasks **pro Session** via `asyncio.gather` (`:220-226`), `_analysis_loop` pro Session (`:321-378`), `AsyncAnthropic` (`claude_adapter.py:29/:92`), Deepgram `asyncwebsocket`, blockierende DB-Arbeit in `run_in_executor`. Kein globaler Riegel, kein `for sid in ...`.
- **Groesse:** 1.020 Zeilen gegen 5.072 Zeilen Flask-Live-Pfad (`claude_service.py` 2.197 + `deepgram_service.py` 1.277 + `live_session.py` 1.598).
- **Keine Schwaerzung:** grep `anonym` in `nerve_rt/` = **0 Treffer**. Roher Deepgram-Text → Puffer (`session_manager.py:298`) → Prompt (`:337-351`) → Anthropic (`claude_adapter.py:92`). `nerve_rt/README.md` ist vollstaendig eine Stopp-Warnung.
- **Nicht angeschlossen:** Der Redis-Vertrag verlangt, dass Flask `nerve:session:{token}` schreibt. Repoweiter grep ueber `app.py`, `routes/`, `services/`: **kein Schreiber, kein Redis-Client, `redis` nicht in `requirements.txt`** (nur in `requirements-rt.txt`). Kein Frontend-Code verbindet sich mit `/ws/`. Der Kontrollkanal `subscribe_control`/`listen_control` hat **keinen Aufrufer**. Dienst laeuft laut README seit 28.07. mit **0 Verbindungen**.
- **Typ-Bruch an der Naht:** `get_session` liefert `hgetall` mit `decode_responses=True` → flache String→String-Paare. `_Session` erwartet `profile_data: dict` (`:196`, `:117`). Es gibt nirgends ein `json.loads` auf dem Weg.
- **Feature-Abdeckung:** vorhanden sind Deepgram-Transport (nova-3-Paritaet, mit Wachtertest), LLM-Transport, Kosten-Buchung STT + LLM. **Nicht vorhanden:** Schwaerzung, Prompt-Bau (kommt fertig als String), Profil-Laden, Coaching-Aufruf, Phasen-Klassifikator, Kaltakquise-Inferenz, Readiness/Hints/EWB-Buttons, Kaufbereitschaft, Keyword-Matcher, QA/FAQ/Tabu, `intent_event`/Momente, Slow-Lane/Post-Call, `conversation_log`-Persistenz, Call-Record, Beenden-Naht, Keyterms, Merge-Fenster, UtteranceEnd, Audio-Health, Sprecher-Stabilisierung, Mute, KeepAlive/Reconnect, PreCall-Briefing, Anrede/Vorwissen, Lernkarten, Counterpart-Umschaltung.
- **Kein Kapazitaetslimit, kein Abraeumen beim Herunterfahren, kein Timeout** auch in der Engine.
- **Wichtig:** Die Engine deckt den **Post-Call-Pfad nicht ab** — der Slow-Lane-Engpass (E, A3) bliebe unveraendert bestehen.

---

## TEIL 4 — WAS EIN "KASSENSYSTEM PRO NUTZER" MITBEKOMMEN MUESSTE

Ein isolierter Anruf braucht heute: aktives Profil (`User.active_profile_id` → `Profile.daten`, geladen bei Session-Start, `deepgram_service.py:743-760`), Profil-Cache (Opener/FAQ/Branche/Vorname, `live_session.py:1010-1082`), PreCall-Briefing (`_session_state[sid]['_briefing']`, zwei Zulieferwege), Einwand-Katalog, FAQ (zwei Wege: Session-Start-Cache LIMIT 20 **und** DB-Abfrage pro Frage-Klassifikation ohne Limit, `claude_service.py:1780-1791`), Tabu-Liste, Keyword-Matcher (Konstanten global, Zustand per-SID), Counterpart, Modus, Anrede/Vorwissen, Anonymisierer-Instanz, A/B-Prompt-Version.

**Drei getrennte System-Prompts im Live-Pfad**, nicht einer: Analyse-Prompt (Modul-Konstante, **nicht** nutzerspezifisch), Coaching-Prompt (eigener Profil-Renderer, `claude_service.py:170-234`), Antwort-Prompt (die 9-Sektionen-Kette in `prompt_pipeline.py:111-484` mit Cache-Breakpoint am Split-Anker `'## PreCall-Briefing'`).

**DB-Zugriffe pro Anruf:** ~9 Lesezugriffe + 2 Schreibvorgaenge beim Start in 4 verschiedenen DB-Sessions; pro Analyse-Tick 2–4 separate DB-Sessions (je 2 SELECT + 1 INSERT + COMMIT) allein fuer die Kostenbuchung; dazu `intent_event`-INSERT pro erkanntem Intent und FAQ-SELECT+UPDATE pro Frage. **Alles multipliziert linear mit N.**

**Ein Profilwechsel mitten im Anruf wirkt nicht** — `/api/set_profile` (`app_routes.py:1336-1362`) schreibt nur die DB, ruft weder `set_profile_for_sid` noch `_load_profile_cache`.

**Lernkarten sind tot:** `load_learning_cards` (`live_session.py:1085-1099`) hat **0 produktive Aufrufer**; `active_learning_cards` bleibt `[]`, der Injektionsblock `claude_service.py:1262-1268` ist faktisch tot.

---

## MEINE FRAGEN AN DICH — bitte in dieser Reihenfolge

1. **Was ist an dieser Bestandsaufnahme falsch oder zu optimistisch?** Insbesondere: Ist die Aussage "0 Fundstellen Datenvermischung" haltbar, wenn gleichzeitig drei HTTP-Eingaenge ohne Eigentuemerpruefung existieren (Teil 2F)? Pruefe 2F selbst am Code nach.
2. **Habe ich eine Klasse von Mehrnutzer-Problemen komplett uebersehen?** Denk an: Gunicorn-Modell (1 Worker, 64 Threads, `async_mode='threading'`), GIL, DB-Pool-Erschoepfung, Deepgram-Verbindungslimits, Anthropic-Ratenbegrenzung pro Konto, Socket.IO ohne `message_queue` bei >1 Worker, Speicherverbrauch pro Session, die geteilten ML-Modelle (spaCy/GLiNER/sentence-transformers, Inferenz ohne Sperre).
3. **Ist die Reihenfolge, in der die Engpaesse angegangen werden muessten, aus dem Befund ableitbar?** Was MUSS vor einem Verkauf an mehrere Kunden geloest sein, was kann danach? Begruende an den Befunden, nicht am Gefuehl.
4. **Engine weiterbauen, Engine neu schreiben, oder Flask ertuechtigen?** Der Gruender neigt zu "Engine neu schreiben, weil der Bestand vermutlich veraltet ist". Ich habe dagegen eingewandt, dass zwei der vier fertigen Bausteine Wachtertests haben und der Bestand nur 1.020 Zeilen ist. **Wer hat recht — und welche dritte Moeglichkeit uebersehen wir beide?** Beachte: die Engine deckt den Post-Call-Pfad nicht ab.
5. **Welche Frage haette ich stellen muessen und habe sie nicht gestellt?**

**Antworte auf Deutsch, kompakt, mit Datei:Zeile-Belegen wo du selbst nachgeprueft hast. Kennzeichne klar, was du am Code verifiziert hast und was du aus meinem Briefing uebernimmst.**
