---
status: resolved
trigger: "Phase 08.20.2 Live-UAT: Bug1 EWB-Antworten generisch kein Profil/Briefing + Bug2 Anrede/Vorwissen-Buttons im PiP funktionslos"
created: 2026-04-30
updated: 2026-04-30
---

## Symptoms

DATA_START
BUG 1 (KRITISCH — Pre-Launch-Showstopper):
- PreCall mit "SAP SE" durchgeführt, Briefing korrekt generiert
- Live-Session gestartet, mehrere EWB-Buttons geklickt ("zu teuer", "kein Bedarf", etc.)
- Alle EWB-Antworten komplett generisch — kein SAP-Bezug, keine Profil-USPs, kein Branchen-Kontext
- Sprachgefühl: nicht wie Sonnet, eher Haiku-Qualität → Verdacht Haiku-Fallback läuft
- Erwartung Phase 08.20: Voll-Profil-EWB-Pipeline, MODEL_PIP_AUTOVAR/VARIANTE=Sonnet 4.5, build_profile_context()

Hypothesen H1-H6 (alle zu verifizieren):
H1: Manual-EWB-Klick triggert alten Live-Loop-Haiku-Pfad statt MODEL_PIP_AUTOVAR/VARIANTE-Pfad
H2: build_profile_context() wird im EWB-Pfad NICHT aufgerufen
H3: build_profile_context() aufgerufen aber _per_sid_briefing[sid]=None (sid-Mismatch PreCall vs Live)
H4: EWB-System-Prompt hat kein {profile_context}-Placeholder mehr (LB-3-Regression)
H5: Circuit-Breaker hat auf Haiku-Fallback umgeschaltet (TTFT >1500ms in 3/5)
H6: _profile_cache leer / user_id=None hardcoded

BUG 2 (Mittel — UX):
- pipEl()-Fix aus Commit a80d6cc ist live (verifiziert via grep auf getnerve.app)
- R3-fix/R4-fix/state.socket-Pattern im Production-Code bestätigt
- ABER: Anrede-Toggle + Vorwissen-Picker reagieren immer noch nicht
- Cursor zeigt pointer beim Hover, onclick=pipSetAnrede('du') korrekt im Inspector
- Keine Console-Errors, keine visuelle Reaktion, kein Backend-Effekt
- Neue Hypothese: pipSetAnrede wird im PiP-Window-Scope aufgerufen, kann aber kein state/socket aus Haupt-Window erreichen (Cross-Window-Scope-Problem)
DATA_END

## Timeline

DATA_START
- Bug 1: Phase 08.20 dokumantierte EWB-Profil-Pipeline als "fertig" — aber Live-Verhalten zeigt generische Antworten → Code ist Wahrheit, Doku ist falsch
- Bug 2: Commit a80d6cc hat pipEl()-Fix eingebaut — live deployed, aber Bug persisitiert → Fix unvollständig oder falscher Root Cause
- Beide Bugs: 2026-04-30 von Andre live auf getnerve.app verifiziert
DATA_END

## Reproduction

DATA_START
Bug 1: PreCall mit Firma starten → Live-Session → EWB-Button klicken → Antwort beobachten (generisch = Bug)
Bug 2: Live-Session starten → PiP-Window öffnet → Anrede-Button klicken → kein Effekt (Bug)
DATA_END

## Current Focus

hypothesis: "BUG 1: precall_briefing gespeichert in ls.state['precall_briefing'] (global), aber build_profile_context() liest via get_briefing_for_sid(sid) aus _session_state[sid]['_briefing'] — zwei verschiedene Storage-Locations, keine Bridge. BUG 2: pipSetAnrede/pipVorwissenEdit/pipSetVorwissen sind als window.X auf dem Haupt-Window definiert, aber onclick-Attribute feuern im PiP-Window-Scope wo diese Funktionen nicht existieren."
test: "Code-Analyse: deepgram_service.py:364-365 schreibt ls.state['precall_briefing']; live_session.py:252-255 liest _session_state[sid]['_briefing']; keine Verbindung zwischen beiden."
expecting: "Fix: deepgram_service.py soll set_briefing_for_sid(_sid, precall_briefing) aufrufen statt ls.state['precall_briefing'] zu setzen."
next_action: "Fixes anwenden — beide Bugs haben klaren Root Cause"
reasoning_checkpoint: "H3 bestätigt (Storage-Mismatch). H1/H2/H4/H5/H6 sekundär — Haiku läuft korrekt, aber ohne Profil-Kontext weil Briefing nie in _session_state[sid] landet."

## Evidence

- timestamp: 2026-04-30T10:00:00Z
  file: services/deepgram_service.py
  lines: 361-366
  finding: "precall_briefing aus socket-payload wird in ls.state['precall_briefing'] (global) gespeichert — NICHT in _session_state[sid]['_briefing']"
  verdict: ROOT_CAUSE_BUG1

- timestamp: 2026-04-30T10:01:00Z
  file: services/live_session.py
  lines: 252-255
  finding: "get_briefing_for_sid() liest aus _session_state.get(sid, {}).get('_briefing') — völlig anderer Speicherort als ls.state['precall_briefing']"
  verdict: CONFIRMS_BUG1

- timestamp: 2026-04-30T10:02:00Z
  file: services/live_session.py
  lines: 258-283
  finding: "init_session_state() erstellt _session_state[sid] ohne '_briefing' Key — wird nach dem ls.state-Write aufgerufen (line 442), überschreibt aber nur _session_state, nicht den Bridge-Pfad"
  verdict: CONFIRMS_BUG1

- timestamp: 2026-04-30T10:03:00Z
  file: services/precall_service.py
  lines: 206-210
  finding: "set_briefing_for_sid() wird von precall_service.py aufgerufen — aber NUR wenn sid!=None. Bei PreCall via HTTP-Endpoint kommt sid=None weil Frontend es nicht mitschickt (pip-launcher.js fetch body enthält kein sid-Feld)"
  verdict: CONFIRMS_BUG1

- timestamp: 2026-04-30T10:04:00Z
  file: static/pip-launcher.js
  lines: 333-341
  finding: "PreCall-Fetch an /api/precall/research sendet kein 'sid' Feld → routes/app_routes.py:954 liest sid=None → recherche_firma(sid=None) → set_briefing_for_sid nie aufgerufen"
  verdict: CONFIRMS_BUG1

- timestamp: 2026-04-30T10:05:00Z
  file: static/pip-launcher.js + services/deepgram_service.py
  lines: 1083-1120 + 361-366
  finding: "briefingText = state.precallBriefing.text (main window state) → emitted als precall_briefing im start_live_session socket event → deepgram_service speichert in ls.state['precall_briefing'] (global) — aber build_profile_context() liest nie von dort"
  verdict: CONFIRMS_BUG1_FULL_PATH

- timestamp: 2026-04-30T10:06:00Z
  file: templates/base.html + static/pip-launcher.js
  lines: base.html:490-493, pip-launcher.js:2457-2468
  finding: "pip-anrede-du/sie Buttons haben onclick='pipSetAnrede(...)' — diese HTML-Nodes werden in PiP-Window verschoben. Wenn onclick im PiP-Window-Kontext feuert, sucht Browser pipSetAnrede auf PiP-window.pipSetAnrede — nicht auf Haupt-window.pipSetAnrede. Funktion nicht gefunden → stilles Versagen."
  verdict: ROOT_CAUSE_BUG2

- timestamp: 2026-04-30T10:07:00Z
  file: static/pip-launcher.js
  lines: 1271-1328
  finding: "_wirePipButtons() verwendet Event-Delegation für EWB und Beenden — aber NICHT für Anrede/Vorwissen. Diese bleiben auf onclick-Attributen die im falschen Scope auflösen."
  verdict: CONFIRMS_BUG2

## Eliminated

- H1 (falscher Pfad): NEIN — streame_manual_ewb_variante wird korrekt aufgerufen
- H4 (kein {profile_context} Placeholder): NEIN — build_profile_context() gibt vollen System-Prompt zurück, kein Placeholder-Pattern
- H5 (Circuit-Breaker Haiku): NEIN — Modell ist config.MODEL_PIP_VARIANTE, kein Circuit-Breaker im Pfad
- H6 (user_id=None): TEILWEISE — user_id kommt aus ls.state['user_id'] das gesetzt wird; profile_daten werden via get_profile_for_sid(_sid) geladen — aber Briefing fehlt wegen H3

## Resolution

root_cause: "BUG1: precall_briefing Socket-Payload wird in ls.state['precall_briefing'] (global, deepgram_service.py:365) gespeichert, aber build_profile_context() liest Briefing via get_briefing_for_sid(sid) aus _session_state[sid]['_briefing'] — zwei Storage-Locations ohne Bridge. BUG2: onclick='pipSetAnrede()' in base.html HTML-Nodes feuert im PiP-Window-Scope; pipSetAnrede ist nur auf Haupt-window.pipSetAnrede definiert, nicht auf PiP-window — stilles ReferenceError."
fix: "BUG1: deepgram_service.py handle_start_live_session: ls.state['precall_briefing'] ersetzen durch ls.set_briefing_for_sid(_sid, precall_briefing) — nach setdefault-Guard, vor init_session_state. BUG2: _wirePipButtons() Event-Delegation um Anrede/Vorwissen-Klicks erweitern (data-anrede / data-vorwissen Attribute), onclick-Attribute aus base.html entfernen."
verification: "BUG1: set_briefing_for_sid(_sid, precall_briefing) called after init_session_state at deepgram_service.py:452-454 — confirmed via grep. BUG2: onclick attrs removed from base.html (verified no matches); event delegation for data-anrede, data-vorwissenedit, .pip-vorwissen-pill added to _wirePipButtons() at pip-launcher.js:1327-1380. Commits: c1e2655 (Bug1), f1916e2 (Bug2)."
files_changed: "services/deepgram_service.py, templates/base.html, static/pip-launcher.js"
