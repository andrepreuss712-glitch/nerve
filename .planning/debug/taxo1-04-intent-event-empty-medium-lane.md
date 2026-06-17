---
status: diagnosed
trigger: "Welle 4 deployed; intent_event nach 4 Test-Calls KOMPLETT LEER (0 Zeilen, psql). Kein '[intent_event] emit failed' im Log -> emit wird im Live-Pfad nicht erreicht."
created: 2026-06-17
updated: 2026-06-17
phase: 08.23.2.TAXO1-04
severity: blocker (Kernfeature des Cutovers tot)
fix_status: PENDING ANDRE/CLAUDIAN SCOPE-ENTSCHEID (reaktiviert ruhende Subsysteme -> Cross-AI + supervised Re-Test noetig, kein Blind-Quick-Fix)
---

## Empirische Belege (logging-first, KEIN Raten — Logs + Prod-DB + Code + git)
- Prod-Log: `[Claude-1] ... Ergebnis (Latenz 9.25s): {}` — analysiere_mit_claude liefert systematisch EIN LEERES dict (99 [Claude-1]-Laeufe).
- Prod-Log: KEIN `[claude] empty content` (msg.content nicht leer) -> `_parse_json` findet kein JSON -> {}.
- Prod-DB `prompt_versions` (module='ewb', v1-legacy + v2-modular): beide sind ANTWORT-Prompts ("liefere EINE Gegenargumentation in 2-3 Saetzen") — KEINE JSON-Schema-Anweisung.
- Code: analysiere_mit_claude (claude_service.py:536) setzt `_system = build_ewb_prompt(...)` (= EWB-Antwort-Template aus prompt_versions), parst die Antwort dann mit `_parse_json` (:588). Prosa-Antwort -> _parse_json -> {}.
- git: build_ewb_prompt als analyse-System-Prompt stammt aus altem Hot-Swap (d2a4875 "swap EWB call-sites to Phase 08 pipeline"); Welle 3 (d784753) hat nur user_id/anrede per-SID am selben Call geaendert. -> Bug ist PRE-EXISTING & latent; Welle 4 DEPENDET erstmals darauf (Medium-Lane-Emit gated auf ergebnis.get('einwand')).
- Deploy-Grenze: PID-Wechsel 1053267 (12:xx, Welle 3) -> 1062617 (14:xx, Welle 4). Die 4 Test-Calls = 14:xx.

## Root Cause (PRIMAER, bestaetigt)
`analysiere_mit_claude` nutzt den EWB-ANTWORT-Prompt (build_ewb_prompt) als System-Prompt statt das JSON-Einwand-Schema (`SYSTEM_PROMPT_BASE`, claude_service.py:33-109 — von Welle 4 bereits um intent_type+confidence erweitert). Haiku schreibt deshalb PROSA (eine Gegenargumentation), `_parse_json` gibt {} zurueck. Folge: `ergebnis.get('einwand')` ist IMMER falsy -> Medium-Lane `emit_intent_event` (claude:1038) feuert NIE. Da die 4 Test-Calls keine Keyword-Treffer (Fast-Lane) und keine Button-Klicks (0 emit-skip-Logs, 0 [KW] in 14:xx) hatten, war die Medium-Lane der einzige erwartete Schreibpfad -> intent_event = 0.

Kaskade (dasselbe {}): kaufbereitschaft/Phase-Signale/FT-Events/alte Einwand-Buttons aus `ergebnis` sind seit dem Hot-Swap latent tot -> erklaert mutmasslich auch "EWB feuerte nicht mehr"/"kein Gespraech erkannt" (Auswertung findet keine Events).

## Sekundaer-Befunde
- **Modus-Mismatch (gatekeeper):** state['current_mode'] DEFAULTET 'gatekeeper' (live_session.py:357/358); start_live_session(cold_call) schreibt mode nach _session_modes (deepgram:437) + call_mode, aber NICHT nach state['current_mode']. mode_initial liest current_mode (:582) -> schreibt 'gatekeeper'. **BLOCKIERT den Emit NICHT** (Medium-Emit ist nicht mode-gegated; Matcher/Button lesen _session_modes=cold_call). Eigener Bug, eigener Fix.
- **Fast-Lane Matcher / Button:** Emit-Code ist erreichbar (NICHT nach return), 0 emit-skip-Logs. In den 4 Calls schlicht nicht getriggert (keine Keyword-Treffer/Klicks) -> nicht als defekt belegt, aber auch nicht als funktionierend live-bewiesen.
- **Lifecycle (Outcome-Frage weg ab Call 2, Frontend Opener->Modus):** wahrscheinlich Folge des leeren ergebnis (Auswertung) + ggf. per-SID-Reset zwischen Calls; braucht Live-Reproduktion nach Primaer-Fix.

## Proposed Fix (PENDING SCOPE-ENTSCHEID — reaktiviert ruhende Logik, daher Cross-AI + supervised)
1. **Primaer:** analysiere_mit_claude muss `SYSTEM_PROMPT_BASE` (JSON-Einwand-Schema) als System-Prompt nutzen, NICHT build_ewb_prompt. (Profil-Kontext bei Bedarf zusaetzlich anhaengen, NICHT statt des Schemas.) -> ergebnis enthaelt wieder {einwand, intent_type, confidence, ...} -> Medium-Lane-Emit feuert. **ACHTUNG: reaktiviert kaufbereitschaft/Phase/FT/Einwand-Buttons (breite Verhaltensaenderung) -> Cross-AI (Gemini, 🔴 Kernpfad) + supervised Live-Re-Test Pflicht.**
2. **Mode:** state['current_mode']/contact_category beim Start aus dem echten mode setzen (cold_call->'cold_call'), damit mode_initial korrekt schreibt.
3. **Netz-Ratsche (Punkt 20, Prozess-Lehre):** Integration-Assertion, die beweist dass aus dem Live-DISPATCH heraus eine intent_event-Zeile entsteht (nicht nur emit_intent_event isoliert) — z.B. analyse_loop-Tick mit gemocktem Haiku-JSON {einwand:true,...} -> assert eine intent_event-Zeile geschrieben. "Tests gruen" != "live geschrieben".

## Warum kein Blind-Fix in diesem Quick
Primaer-Fix reaktiviert ruhende Kern-Subsysteme (Anti-Abrieb, 🔴 Kernpfad, CLAUDE.md Punkt 7/24 Cross-AI-Pflicht + Punkt 19 Pre-Execute). Scope (nur Emit reparieren vs. ganze ergebnis-Kaskade) ist eine Andre-Entscheidung. "logging-first, nicht raten" eingehalten: Root empirisch belegt; Anwendung braucht supervised Re-Test.
