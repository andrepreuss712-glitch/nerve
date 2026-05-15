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
