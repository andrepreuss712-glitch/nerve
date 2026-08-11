# TAXO 3-Wege-Interlock + Probe-Bau — Funde (2026-06-13)

> ## ⚠ ALTERS-WARNUNG — DER BEWERTUNGS-TEIL DIESER DATEI IST ÜBERHOLT (eingefügt 2026-08-11)
>
> Diese Datei ist vom **13.06.** und beschreibt durchgehend eine **Noten-Engine, die `calls.coaching_score` schreibt** — inklusive Funden wie *„TAXO2-04 löscht `_calc_process_score` → halb-gelöschter Pfad"* und *„`coaching_score` bleibt ewig NULL, still"*.
> **Fünfzehn Tage später, am 28.06., wurde diese Engine abgeschafft:** NERVE zeigt **keine Zahl mehr, die Qualität bewertet**. Statt einer Note gibt es Beobachtungen mit wörtlichem Beleg-Zitat plus **genau EINE Sache fürs nächste Mal**. Verbindlich: `Nerve-Vault/04 Entscheidungen/NERVE Konstrukt - Soll-Verhalten.md` §6.
> **Weil die Datei sich selbst als „Pflicht-Pre-Read" deklariert, wurde sie beim Planen zwangsweise mitgelesen** — mit einem Bewertungs-Modell, das es nicht mehr gibt. Gefunden bei einer Drift-Suche über alle GSD-Kontextdateien am 11.08.
>
> **Was weiter gilt und wertvoll bleibt:** alle Funde zu **Nebenläufigkeit, Sperren, per-Sitzung-Zustand, Moment-Klammer (`interaction_id`) und Schema/Persistenz**. Die wurden unabhängig von der Bewertungs-Frage gefunden und sind mehrfach am Code bestätigt.
> **Was NICHT mehr gilt:** alles, was `coaching_score`, `rubric_score`, Gewichtungen, Gesamtnoten oder den Noten-Cutover als Ziel beschreibt.
>
> **Zweck (ursprünglich):** Konsolidierte Funde aus dem vollen 3-Wege-Interlock VOR dem TAXO-Bau. Pflicht-Pre-Read für die TAXO1-03/04-Überarbeitung — **für den Bewertungs-Teil ausdrücklich NICHT mehr.** Quellen: Claudian-Erstdurchgang + Gemini 3.1 (unabhängig, interlock) + Opus-Probe-Bau (Trockenbau am echten Code, Prod-HEAD 0015). Fable-Probe-Bau war geplant, aber Fable 5 wurde 13.06. per US-Exportkontroll-Anordnung suspendiert (kein ETA) → Opus stattdessen.
> **Verifikations-Stand:** Claudian hat IL-2 + B-A + B-B am echten Code bestätigt. Rest code-gegründet (Opus zitierte Zeilen-Nr.), markierte Live-Server-Checks unten.

## BLOCKER (vor Bau auflösen)

- **IL-2 (TAXO3↔TAXO1, Gemini+Claudian verifiziert):** TAXO3 (`build_answer_context`) liest live pro-SID `intent_type`(primary_intent)+`confidence`; TAXO1-04 schreibt sie nur in die DB, NICHT in `_session_state[sid]`. mode (TAXO1-07) + interaction_id (TAXO1-03) liegen im RAM, intent_type+confidence NICHT. → **TAXO1-04-Rework: Medium-Lane muss intent_type+confidence in `_session_state[sid]['state']` ablegen, bevor Antwort getriggert wird (Live-Übergabe-Vertrag).**
- **B-A (TAXO1-03↔TAXO1-04, Opus, Claudian verifiziert `live_session.py:732/770/789`):** reset_session() nullt `line_id`/`kw_fired_for_line` im modul-globalen Store; TAXO1-03 migriert Anker auf per-SID + löscht global, listet aber die Reset-Pfade NICHT → Halbmigration, Doppel-Feuer-Schutz sporadisch wirkungslos. → **TAXO1-03-Scope: reset_session/Reset-Pfade (live_session.py:770/789) explizit aufnehmen.**
- **B-B (TAXO1-03 Task 4 org_id, Opus, Claudian verifiziert `cost_tracker.py:44/60`):** `_resolve_org_id_from_live_session` + user_id-Resolver machen `for _st in _session_state.values(): return` → erste beliebige Session → falsche Multi-Call-Zuordnung. TAXO1-03 Task 4 nennt nur 4 live_haiku-Stellen. → **TAXO1-03-Scope: den Resolver SELBST fixen (nicht nur 4 Stellen patchen) + ALLE log_api_cost-Aufrufer (Banner sagt ~14, Task-Text nur 4 — Diskrepanz auflösen).**

## HOCH

- **H-1 (TAXO2-04):** correct_outcome (`app_routes.py:2001-2005`) liest `score_breakdown`-Stash + Fallback auf `_calc_process_score`; api_beenden (`:659`) stasht. TAXO2-04 löscht `_calc_process_score` → halb-gelöschter Pfad = `NameError` bei Stash-Miss. → Stash→Read-Vertrag als EINE Einheit behandeln.
- **H-2 (TAXO2-04 Sweep-Owner fehlt):** Hang-Fix (outcome nie gesetzt) braucht periodischen Sweep, aber Slow-Lane-Consumer blockt auf `queue.get()` (nie periodisch). KEIN Plan baut den Timer/Scheduler. → **Sweep-Daemon explizit spezifizieren (analog IL-2-Rework).**
- **H-3 (Slow-Lane Bootstrap-Re-Queue fehlt):** Consumer startet mit leerer Queue; nichts re-derived `WHERE handling_status='pending'` aus der DB bei Restart. → pending-Events bleiben nach Crash/Deploy liegen. „Re-derivierbar"-Anspruch unerfüllt. → **Bootstrap-Re-Queue bauen.**
- **H-4 (TAXO1-04 abstain-Emit):** `claude_service.py:1279` [QA-INT]-skip ist Doppel-Feuer-Schutz (NICHT low-conf-Drop); abstain-Emit dort mit confidence=None → abstained=True für JEDEN keyword-vorgefeuerten Moment → flutet intent_event. 6 Marker-Stellen (:1279/:1284/:1310/:1319/:1335/:1398) nicht sauber unterschieden. → **TAXO1-04-Rework: die [QA-INT]-Stellen klassifizieren (echter Drop vs. Doppel-Feuer-Skip vs. roles_confirmed-Gate), Emit nur am richtigen.**
- **H-5 (TAXO3-04 Prewarm):** `prewarm_answer_cache` feuert echten Sonnet-Call pro Session-Start → bei 50 parallelen Calls 50 Extra-Calls (Rate-Limit + Kosten + org_id-Roulette + Cache evtl. >5min kalt vor erstem Einwand). → Prewarm-Strategie überdenken.

## MITTEL

- **M-1:** abstain_log.interaction_id ohne FK → dangling nach Call-Löschung (Cascade via event_id deckt DSGVO; nur dokumentieren).
- **M-2:** TAXO1-04 liest mode aus `_session_modes` (deepgram_service); TAXO1-07 löscht/konsolidiert das → TAXO1-07 muss den TAXO1-04-Emit-mode-Read mit-migrieren.
- **M-3:** Dashboard-Einwand-Zähler (`dashboard.py:736`) zählt nach TAXO2-05-Umzug intent_event — aber Moment-Klammer = mehrere Zeilen/Moment → naiver COUNT verdreifacht. → **Reader auf DISTINCT interaction_id / source=ui_asserted filtern.**
- **M-4 (höchstes stilles Risiko):** rubric_score RLS FORCE (TAXO2-01) + Slow-Lane-Daemon-Write (TAXO2-04, eigene get_session, KEIN Request-Context) → after_begin-GUC `app.tenant_id` evtl. leer → WITH CHECK fail-closed → Engine-Write abgelehnt → **coaching_score bleibt ewig NULL, still.** → **Daemon-Thread muss tenant_id-GUC vor rubric_score-INSERT setzen.**
- **M-5:** TAXO3-03 Auto-Pfad primary_intent-Quelle unklar im keyword-Trigger-Fall (noch kein Haiku-Intent) → „erste aus Liste"-Heuristik widerspricht REQ-5 (EIN deterministischer Intent). → Quelle eindeutig spezifizieren.

## NIEDRIG

- **N-1:** TAXO1-02 `signal.signal(SIGTERM)` evtl. nicht im Prozess-Main-Thread unter Gunicorn/gthread → ValueError beim Start. Live-prüfen.
- **N-2:** TAXO1-06 Cache-Invalidierung via Deploy-Restart — ok, kein In-Call-Clear nötig.
- **N-3:** TAXO1-01 payload_jsonb ORM=`JSON` vs. Migration=`JSONB` — DB gewinnt (harmlos), Konsistenz prüfen (JSON_TYPE-Muster).
- **N-4:** Namens-Wirrwarr `session_mode` (rubric_score/mode_weight_config) vs. `call_mode` (calls, echt) + `meeting` vs. `meeting_consented` → konsistent durchziehen, sonst leeres mode_config-Lookup.

## Gegen Live-Server zu prüfen (Code im Ruhezustand gesehen)
- M-4: setzt der Slow-Lane-Daemon-Thread `app.tenant_id`-GUC?
- N-1: läuft App-Bootstrap unter Gunicorn `--threads 4` im Prozess-Main-Thread?
- B-B/H-5: echte org_id-Verteilung Multi-Call + Anthropic-Rate-Limit-Headroom für Prewarm.
- H-3: werden pending-intent_event nach `systemctl restart` je wieder verarbeitet?

## Struktur-Einsicht (Opus)
H-2 (Sweep) + H-3 (Re-Queue) brauchen BEIDE einen periodischen Daemon, den die TAXO1-02-`queue.get()`-Architektur nicht hergibt. → Slow-Lane-Design braucht eine periodische Timer-Komponente, die kein Plan baut.

## Rework-Ziele (wohin die Funde fallen)
- **TAXO1-03 (Putzliste):** B-A (Reset-Pfade) · B-B (Resolver-Fix + alle cost-Stellen) · N-4 (Naming).
- **TAXO1-04 (Cutover):** IL-2 (Live-Übergabe) · H-4 (abstain-Emit-Stellen) · M-2 (mode-Read cross-wave mit TAXO1-07).
- **TAXO2 (02/03/04/05):** H-1 (Stash-Vertrag) · H-2 (Sweep-Daemon) · H-3 (Re-Queue-Bootstrap) · M-3 (Zähler DISTINCT) · M-4 (RLS-GUC im Daemon).
- **TAXO3 (03/04):** H-5 (Prewarm) · M-5 (primary_intent-Quelle).
- **Slow-Lane-Design (TAXO1-02):** periodische Timer-Komponente (Herzstück für H-2/H-3/M-4).
