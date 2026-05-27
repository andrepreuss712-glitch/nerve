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
