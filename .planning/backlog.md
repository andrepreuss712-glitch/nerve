# Backlog

**Purpose:** Bug-Fix und Polish-Items, die außerhalb aktiver GSD-Phasen entdeckt wurden und auf eine spätere dedizierte Bug-Fix-Phase warten. Jeder Eintrag enthält ID, Severity, Kontext und vermutete Root-Cause-Hinweise.

**Convention:** IDs folgen dem POLISH-XX Schema (kontinuierlich mit REQUIREMENTS.md POLISH-24..37). Schweregrade: `critical` (blockiert User-Flow), `high` (fehlerhafte Daten), `medium` (Metriken/Persistenz), `low` (Kosmetik).

---

## Open

### POLISH-38 — `ConversationLog.einwaende_gesamt` wird nicht hochgezählt

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Sektion 4 "Einwand-Timeline" zeigt 3 ObjectionEvent-Einträge (Preis/Zeit/Entscheider), Metrik "Einwände behandelt" zeigt `0/0` statt `0/3` bzw. `X/3`.
- **Vermutete Root-Cause:** Beim `ObjectionEvent`-Insert (wahrscheinlich in `routes/app_routes.py` `/api/ewb` Handler oder in `services/live_session.py` EWB-Klick-Persistenz) fehlt die parallele Inkrement-Logik für `ConversationLog.einwaende_gesamt`. Die Bulk-Insert-Schleife aus Phase 04.7 zählt Events, aber der ConversationLog-Zähler wird nicht synchron hochgezählt.
- **Impact:** Score-Hero-Breakdown "Einwände behandelt" prozentualer Anteil falsch. Post-Call-Analytics (Admin-Dashboard) zeigen systematisch 0 Einwände für alle Live-Sessions.
- **Betrifft:** `/api/beenden` Handler, `services/live_session.py`, evtl. `database/models.py` falls trigger-basiert.
- **Fix-Skizze:** Nach ObjectionEvent-Bulk-Insert in `api_beenden` (Phase 04.7) ein `conv.einwaende_gesamt = len(ewb_clicks)` setzen und mit `db.add(conv); db.commit()` persistieren. Alternativ SQL-Trigger auf `objection_events` Insert.

---

### POLISH-39 — `ConversationLog.phasen_details` bleibt NULL trotz aktiver Phasen-Klassifikation

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Session #117 lief 77 Sekunden, Backend loggt explizit `[phase_classify] 1→2 (Qualifizierung) conf=0.85`, aber `ConversationLog.phasen_details` ist NULL nach Session-Ende. Sektion 5 "Phasen-Strip" bleibt leer trotz ausreichender Dauer.
- **Vermutete Root-Cause:** Phase-Classifier (in `services/claude_service.py` oder ähnlich) hält die Klassifikationen im Runtime-State (`live_session.state`) aber die `api_beenden`-Persist-Logik liest diesen State nicht in `phasen_details` zurück. Es gibt einen Disconnect zwischen Runtime-Tracking und DB-Write.
- **Impact:** Phasen-Strip-Section (Sektion 5) permanent leer bei Live-Sessions. OBS-02 Recidiv-Risiko, obwohl Backend-Intelligence funktioniert.
- **Betrifft:** `routes/app_routes.py` `/api/beenden`-Handler, `services/live_session.py` state-Extraktion.
- **Fix-Skizze:** In `api_beenden` vor dem Commit: `conv.phasen_details = json.dumps(live_session.state.get('phasen_klassifikationen', []))`. Prüfen ob Payload-Format mit Template-Rendering übereinstimmt.

---

### POLISH-40 — `ConversationLog.precall_briefing` bleibt NULL trotz generiertem Briefing

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Log zeigt `[DG] PreCall-Briefing gespeichert (1540 Zeichen)` — Briefing wurde generiert und im Runtime-State abgelegt. Nach Session-Ende ist `ConversationLog.precall_briefing` NULL. Collapsible "PreCall-Briefing" im Session-Detail bleibt leer.
- **Vermutete Root-Cause:** Analog zu POLISH-39. `services/precall_service.py` oder `routes/app_routes.py` `/api/precall/recherche` schreibt Ergebnis in `live_session.state['precall_briefing']`, aber `/api/beenden` liest diesen Key nicht aus und persistiert ihn nicht.
- **Impact:** User verliert Zugriff auf die PreCall-Vorbereitung nach Session-Ende. Knowledge-Retention für Coaching-Review kaputt.
- **Betrifft:** `routes/app_routes.py` `/api/beenden`-Handler, `services/live_session.py`, evtl. `services/precall_service.py`.
- **Fix-Skizze:** In `api_beenden`: `conv.precall_briefing = live_session.state.get('precall_briefing') or None` vor Commit. Evtl. Hash/Ref statt Volltext für DB-Size-Kontrolle.

---

### POLISH-41 — Post-Call-Screen zeigt "Kein Gespräch erkannt" trotz kompletter Session-Persistenz (KRITISCH)

- **Severity:** critical
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20)
- **Symptom:** Cold-Call Session #117 wird korrekt beendet — alle Einwände, Painpoints, Skript-Abdeckung, `kb_end=74` sind in der DB. Nach "Beenden"-Klick zeigt der Post-Call-Overlay-Screen jedoch "Kein Gespräch erkannt". User denkt der Call sei verloren und navigiert nicht zur Detail-Seite. Session ist aber via `/analytics` → Session-Detail vollständig abrufbar.
- **Vermutete Root-Cause:** Frontend-Bug im Post-Call-Overlay-Rendering in `static/app.js` oder PiP-Launcher (`static/pip-launcher.js`). Die "Kein Gespräch erkannt"-Guard prüft vermutlich falsche Indikatoren (z.B. `words < 20` oder `sessionSeconds < 10`), obwohl Backend-Response `log_id` korrekt zurückliefert. Cold-Call hat keine Speaker-Diarization → `berater_words` kann 0 bleiben trotz aktivem Call. Der Guard ist nicht typ-aware (analog OBS-02 Redeanteil-Regel in `_derive_practice_recommendations`).
- **Impact:** KRITISCHER User-Flow-Blocker. User verliert Vertrauen in die Session-Erfassung. Kein Redirect auf `/session/<id>` bei Cold-Call in der Praxis → gesamter Phase-07.2-Konsolidierungs-Flow kaputt für Cold-Call.
- **Betrifft:** `static/app.js` (No-Conversation-Guard), `static/pip-launcher.js` (Post-Call-Screen), evtl. `/api/beenden` Response-Payload.
- **Fix-Skizze:** No-Conversation-Guard typ-aware machen: bei `session_mode === 'cold_call'` nur `sessionSeconds < 10` prüfen (keine Word-Count-Guard, da single-speaker). Alternativ: Guard auf Server-Seite verlagern und Frontend nur auf `log_id`-Rückgabe reagieren. Regression-Test mit kurzer Cold-Call-Session (~15s).

---

## Referenzen

- Phase 07.2 UAT-R2 Cold-Call-Checkpoint: 2026-04-20, Session #117 als Test-Referenz
- B1 aus UAT-R2 (Sektion 14 Dubletten) wurde in Phase 07.2 inline gefixt (Commit `e040ee7`)
- POLISH-35, POLISH-36, POLISH-37 bleiben deferred aus Phase 07.1 (siehe ROADMAP.md Zeile 711-717)
