# Foundation-Code-Register

**Zweck:** Stubs/leere Strukturen die heute angelegt werden um spaetere Phasen ohne Refactor zu aktivieren. Jeder Eintrag dokumentiert: Was es ist, warum es leer ist, welche Phase es aktiviert.

**Regel:** Stubs duerfen nur leere Bodies (`pass`) oder leere Container (`[]`, `{}`) sein. Keine "fake" Implementierung. Aktivierung erfolgt durch die in "Aktiviert von" genannte Phase.

---

## Eintrag 1: `populate_context_notes(state, entity) -> None`

| Feld | Wert |
|------|------|
| Stub-Funktion | `populate_context_notes(state, entity) -> None: pass` |
| Modul | `services/gatekeeper.py` (Phase 08.23.2.C P06) |
| Angelegt von | Phase 08.23.2.C (D-02) |
| Aktiviert von | Phase 08.23.2.I (Sekretaer-Uebergabe-Feature / Live-Notizblock) |
| State-Key | `_session_state[sid]['state']['context_notes']` (initialisiert als `[]` in `init_session_state()`) |
| Aktueller Stand | Stub mit pass-Body, kein Aufruf im Live-Loop. context_notes-Liste bleibt leer. |
| Aktivierungs-Trigger | Phase 08.23.2.I implementiert NER-Extraktion auf Gatekeeper-Aussagen (z.B. "Herr Schmidt ist im Termin bis 14 Uhr") und ruft `populate_context_notes(state, entity)` auf -- Funktion fuellt `context_notes` mit strukturierten Hinweisen. |

**Rationale (Phase 08.23.2.C):** State-Feld + Stub-Funktion werden jetzt angelegt, damit Phase 08.23.2.I nur die Body-Implementierung schreibt -- ohne Session-State-Migration oder neue Import-Pfade.

---

## Eintrag 2: `context_notes`-State-Feld

| Feld | Wert |
|------|------|
| State-Pfad | `_session_state[sid]['state']['context_notes']` |
| Initial-Wert | `[]` (leere Liste) |
| Modul | `services/live_session.py` `init_session_state()` (Phase 08.23.2.C P06) |
| Angelegt von | Phase 08.23.2.C (Req-11) |
| Aktiviert von | Phase 08.23.2.I |
| Reset-Verhalten | `pop_session_state(sid)` loescht die Liste automatisch via `dict.pop`. |
| Aktueller Stand | Liste wird angelegt, aber nie befuellt. Kein UI-Konsument. |

---

*Register erstellt: 2026-05-15 (Phase 08.23.2.C Plan 03)*

---

## Eintrag: `calls.outcome_confidence`

| Feld | Wert |
|------|------|
| DB-Spalte | `calls.outcome_confidence` (Float, nullable) |
| Angelegt von | Phase 08.23.2.D (REQ-D-1, Migration 0005) |
| Schreib-Pfade | `routes/learning.py::api_postcall_analysis` (Haiku-Classifier-Result); `routes/app_routes.py::api_calls_correct_outcome` laesst Feld unveraendert (Audit-Trail) |
| Lese-Pfade (downstream) | **Phase E (DPO-Paar-Sammler):** Gate-Logic `WHERE outcome_confidence >= 0.90 AND audio_health_score >= 0.80` fuer Trainings-Korpus-Aufnahme; **Phase H (Vorschlags-System):** Confidence-Trend-Analyse fuer adaptive UX |
| Kalibrierungs-Trigger | Post-Launch nach 100 EA-Calls: `SELECT outcome, outcome_source, COUNT(*) FROM calls GROUP BY outcome, outcome_source ORDER BY COUNT(*) DESC;` — falls >40% in ai_auto_unsicher landen, Schwelle nach unten korrigieren |

**Rationale (Phase 08.23.2.D):** Die 70%/90%-Confidence-Schwellen (REQ-D-4) sind initial-Default und brauchen Real-Daten-Kalibrierung. Eintrag dokumentiert downstream-Konsumenten + Kalibrierungs-Plan.

---

## Eintrag: `calls.outcome_source`

| Feld | Wert |
|------|------|
| DB-Spalte | `calls.outcome_source` (Text, nullable, CHECK in `('ai_auto','ai_auto_unsicher','user_corrected')` OR NULL) |
| Angelegt von | Phase 08.23.2.D (REQ-D-1) |
| Schreib-Pfade | `routes/learning.py::api_postcall_analysis` (Schwellenlogik aus REQ-D-4); `routes/app_routes.py::api_calls_correct_outcome` setzt `'user_corrected'` |
| Lese-Pfade (downstream) | **Phase E (DPO-Gate):** Filter `WHERE outcome_source IN ('ai_auto','user_corrected')` — `ai_auto_unsicher` wird vom Trainings-Korpus AUSGESCHLOSSEN; **Phase H (Korrektur-Statistik):** Counter `user_corrected` als Klassifikator-Qualitaets-KPI; **routes/performance.py::api_dashboard:** Filter fuer 7-Tage-Reminder (REQ-D-8) |
| Kalibrierungs-Hinweis | Wenn `user_corrected`-Anteil > 20% → Prompt-Engineering-Review fuer Classifier |

**Rationale (Phase 08.23.2.D):** Dreistufiges Provenance-Modell (REQ-D-4) ist Foundation fuer Phase E DPO-Gate-Auswahl. Ohne diese Spalte koennte Phase E nicht zwischen high-quality + low-quality Trainings-Daten diskriminieren.

---

## Eintrag: `calls.outcome_note`

| Feld | Wert |
|------|------|
| DB-Spalte | `calls.outcome_note` (Text, nullable) |
| Angelegt von | Phase 08.23.2.D (REQ-D-1, REQ-D-5) |
| Constraint | **IMMER** anonymisiert via `services/anonymization.py::anonymize()` vor DB-Insert (REQ-D-5 Defense-in-Depth) |
| Schreib-Pfade | `routes/app_routes.py::api_calls_correct_outcome` ruft `anonymize(text, cache=None)` und persistiert das Ergebnis (oder NULL bei `[ART9_REDACTED]`/`[ANON_FEHLER]`) |
| Lese-Pfade (downstream) | Aktuell keine (Dashboard-Display deferred per D-08 Option a); **Phase O Analytics:** potentielle Aggregat-Auswertung (anonymisiert) |

**Rationale (Phase 08.23.2.D):** D-08 Option a entschied gegen Note-Display im Dashboard (Aufwand vs. Nutzen). Spalte existiert + wird gefuellt fuer spaetere Read-Pfade ohne Schema-Migration in Phase O.

---

## Eintrag: `calls.conversation_log_id`

| Feld | Wert |
|------|------|
| DB-Spalte | `calls.conversation_log_id` (Integer FK → `conversation_logs.id`, nullable) |
| Angelegt von | Phase 08.23.2.D (REQ-D-1, Migration 0005) |
| Schreib-Pfade | `routes/app_routes.py::api_beenden` (UPDATE nach ConvLog-Save, Plan 04 REQ-D-2) |
| Lese-Pfade (downstream) | **routes/performance.py::api_dashboard:** JOIN `Call.conversation_log_id = ConversationLog.id` fuer Outcome-Daten pro Session (REQ-D-8/9); **Phase E:** FK-Traversal Call → ConvLog fuer Trainings-Korpus-Reichhaltigkeit (Transcript-Snippets + Outcome) |
| Nullable-Rationale | Early-Call-Records aus `create_call_for_sid()` haben noch keinen ConvLog — FK wird erst in `api_beenden` gesetzt |

**Rationale (Phase 08.23.2.D):** FK ist die einzige Bruecke zwischen `calls` (Outcome-Welt) und `conversation_logs` (Transcript-Welt). Phase E benoetigt diese Verbindung fuer DPO-Paar-Erstellung — daher kanonisch dokumentiert.

---

## Eintrag: PIP.2 — Coaching-Signal-Anzeige (`_showProactiveContent` / `_showProactiveTipp` + Datenversorgung)

| Feld | Wert |
|------|------|
| Foundation-Code | `_showProactiveContent(slot, result)` (static/pip-launcher.js:2754) + `_showProactiveTipp(slot, tipp)` (:2773) — FE-Funktionen die heute Phase/Kaufbereitschaft als TEXT rendern |
| Datenversorgung | `pip_token_done`-Payload-Felder `result.phase` / `result.kb` (gelesen @ pip-launcher.js:2407-2408 im Zweig `if (!d.result.einwand)`). BE-Compute: `phase` in `services/claude_service.py::analysiere_mit_claude` (Z.418-423); Kaufbereitschaft/readiness via `compute_readiness_score` (1339) / `ls.kaufbereitschaft` / `score_p4` (1407-1419) — **slot-0-Analyse-Pfad**, NICHT die EWB-Auto-Streamer |
| Angelegt von | Phase 08.23.2.PIP (Plan 01, Item d) — beim Anzeige-Trennungs-Umbau erhalten gehalten |
| Aktiviert von | **Phase PIP.2 (Coaching als Symbole / Rahmenfarbe)** |
| Aktueller Stand (nach PIP.1) | Funktions-DEFINITIONEN + der Aufruf @2408 BLEIBEN. NUR der Schreib-Seiteneffekt in die Lese-Zone (slot 1) ist per Guard `if (slot === 1) return;` (erste Zeile beider Funktionen) abgeschaltet. Coaching-Text erscheint nicht mehr in slot 1; in slot 0 (1-slot===0) unveraendert. Die Daten (`result.phase`/`result.kb`) kommen weiterhin im FE-Payload an und werden den Funktionen uebergeben. |
| Aktivierungs-Trigger (PIP.2) | PIP.2 rendert die bereits ankommenden Coaching-Daten **Text → Symbol/Rahmenfarbe** um — d.h. die Body-Logik von `_showProactiveContent`/`_showProactiveTipp` wird auf Symbol-Darstellung umgebaut. **Die Daten-Pipeline (Compute + Emit + result.phase/result.kb) ist bereits live und muss NICHT neu gebaut werden** — nur die Render-Schicht wechselt. |
| Anti-Abrieb-Regel | Diese Pipeline (Compute/Emit/Datenfluss) NICHT loeschen/prunen/kappen. Wer den slot-0-Analyse-Pfad oder die pip_token_done-Felder anfasst, prueft dass `result.phase`/`result.kb` weiter ankommen. Tagline: **"Text → Symbol re-render; pipeline must stay alive, do not rebuild."** |

**Rationale (Phase 08.23.2.PIP, André-Direktive 2026-06-29):** Item (d) sollte NUR den Coaching-TEXT aus der Lese-Zone (slot 1) entfernen, NICHT die Coaching-Signal-Datenpipeline. PIP.2 (Coaching als Symbole/Rahmenfarbe) soll die Daten nur anders rendern, nicht die Pipeline neu aufbauen. grep-Beleg (2026-06-29): `streame_auto_variante`/`streame_manual_ewb_variante` emittieren ihr result IMMER mit `einwand:True` und tragen kein phase/kb → die in PIP.1 Plan 01 Task 1 geprunten Auto-Lese-Zonen-Pfade beruehren die Coaching-Daten NICHT. Eintrag verhindert versehentliches Prunen der Foundation. Referenziert von `.planning/phases/08.23.2.PIP-.../08.23.2.PIP-01-anzeige-trennung-PLAN.md` (Task 2 C).

---

## Eintrag: PIP.4 — `streame_auto_variante` (inkl. dormanter TTFT-Circuit-Breaker)

| Feld | Wert |
|------|------|
| Foundation-Code | `streame_auto_variante(neuer_text, einwaende, kontext, sid, slot, trigger)` (services/claude_service.py:577) + die modul-globalen `_ewb_ttft_history` (Z.18), `_ewb_fallback_until` (Z.19), `_ewb_circuit_lock` (Z.20) + das Cost-Tracking (`log_api_cost`-Hooks, `_cache_writes`) im Funktions-Body |
| Angelegt von | urspruenglich BUG-10 r3 (Auto-Variante Slot 1); als Foundation markiert in Phase 08.23.2.PIP (Plan 01, Item a) |
| Aktiviert von | **Phase PIP.4 (KI-Antwort-Default + Vorgenerierung/Caching bekannter Einwaende, TAXO3-gegated)** |
| Aktueller Stand (nach PIP.1) | **Write-only / dormant — KEIN Aufrufer im Produktiv-Pfad.** Der einzige bisherige Caller (deepgram_service.py Keyword-Pfad) wurde in Plan 01 durch ein direktes `ewb_signal`-Button-Signal ersetzt (kein Haiku im Live-Highlight-Pfad, Punkt 25 Latenz). Funktions-Body + Circuit-Breaker bleiben UNVERAENDERT erhalten (kein Prune, kein Refactor — Punkt 17). |
| Circuit-Breaker-Removal-Audit (Cross-AI MEDIUM #1) | grep gegen den Produktiv-Code (2026-06-29): `_ewb_fallback_until` / `_ewb_ttft_history` / `_ewb_circuit_lock` werden **ausschliesslich innerhalb von `streame_auto_variante`** gelesen/gesetzt (claude_service.py:18-20 Defs + 591/595/638/639/661-668 Body). **KEIN externer Produktiv-Reader/-Schreiber.** Einzige weitere Referenz: `tests/test_ewb_autovar_global_regression.py` (Regressions-Test fuer den `global _ewb_fallback_until`-Bug). → Kalt-Stellen ist sicher: der dormante Circuit-Breaker hat keine lebenden Abhaengigen. |
| Konsequenz / Anti-Abrieb-Hinweis | Mit dem Kalt-Stellen entfaellt auch der `record_suggestion_offer(slot='B', source='auto_variante')`-Capture (claude_service.py:739) — es wird keine Auto-Variante mehr generiert, also gibt es keine Auto-Suggestion mehr zu erfassen (inhaerent durch die LOCKED-Decision (a): Auto = nur Highlight, keine Generierung). Falls der TAXO2/DPO-Korpus die `slot='B'/auto_variante`-Vorschlaege spaeter doch braucht, ist das in PIP.4 (Vorgenerierung) oder separat wieder zu aktivieren. **NICHT loeschen** (Zombie-Regel CLAUDE.md Punkt 23). |
| Aktivierungs-Trigger (PIP.4) | PIP.4 ruft `streame_auto_variante` wieder auf (oder eine Vorgenerierungs-Variante davon) fuer das KI-Antwort-Default + Caching bekannter Einwaende — der Circuit-Breaker wird dann automatisch wieder aktiv. |

**Rationale (Phase 08.23.2.PIP, Plan 01, Cross-AI MEDIUM #1):** Beim strukturellen Kappen des Auto→slot-1-Schreibpfads wird `streame_auto_variante` nicht mehr aufgerufen. Statt es als toten Code zu loeschen (es traegt den TTFT-Circuit-Breaker + ist PIP.4-Vorgenerierungs-Fundament), wird es per Audit als reader-frei belegt und als dormante Foundation markiert. Tagline: **"dormant auto-generator — wake in PIP.4, do not delete."**
</content>
