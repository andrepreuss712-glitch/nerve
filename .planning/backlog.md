# Backlog

**Purpose:** Bug-Fix und Polish-Items, die außerhalb aktiver GSD-Phasen entdeckt wurden und auf eine spätere dedizierte Bug-Fix-Phase warten. Jeder Eintrag enthält ID, Severity, Kontext und vermutete Root-Cause-Hinweise.

**Convention:** IDs folgen dem POLISH-XX Schema (kontinuierlich mit REQUIREMENTS.md POLISH-24..37). Schweregrade: `critical` (blockiert User-Flow), `high` (fehlerhafte Daten), `medium` (Metriken/Persistenz), `low` (Kosmetik).

---

## Open

### POLISH-38 — `ConversationLog.einwaende_gesamt` wird nicht hochgezählt

- **Severity:** medium
- **Entdeckt:** Phase 07.2 UAT-R2 Cold-Call-Checkpoint (2026-04-20), refined in Cold-Call-UAT-R2-Approval (2026-04-21) mit Session #117
- **Symptom:** Sektion 4 "Einwand-Timeline" zeigt 4 ObjectionEvent-Einträge, Metrik "Einwände behandelt" zeigt konkret `0/1` statt `0/4` (d.h. der Counter erfasst nur genau 1 Einwand, nicht alle in der Timeline aufgeführten Events). Ursprünglich beobachtet mit `0/0`-Anzeige bei 3 Events — aktuelle Reproduktion Session #117 Cold-Call-UAT-R2: 4 Timeline-Events vs. `0/1`-Metrik.
- **Vermutete Root-Cause:** Beim `ObjectionEvent`-Insert (wahrscheinlich in `routes/app_routes.py` `/api/ewb` Handler oder in `services/live_session.py` EWB-Klick-Persistenz) fehlt die parallele Inkrement-Logik für `ConversationLog.einwaende_gesamt`. Die Bulk-Insert-Schleife aus Phase 04.7 zählt Events, aber der ConversationLog-Zähler wird nicht synchron hochgezählt. Der aktuelle Counter-Wert `1` legt nahe, dass nur der allererste EWB-Klick den Zähler erhöht (oder nur der letzte ObjectionEvent committed wird) — Folge-Klicks werden ignoriert.
- **Impact:** Score-Hero-Breakdown "Einwände behandelt" prozentualer Anteil falsch. Post-Call-Analytics (Admin-Dashboard) zeigen systematisch zu wenige Einwände für alle Live-Sessions.
- **Betrifft:** `/api/beenden` Handler, `services/live_session.py`, evtl. `database/models.py` falls trigger-basiert.
- **Fix-Skizze:** Nach ObjectionEvent-Bulk-Insert in `api_beenden` (Phase 04.7) ein `conv.einwaende_gesamt = len(ewb_clicks)` setzen und mit `db.add(conv); db.commit()` persistieren. Alternativ SQL-Trigger auf `objection_events` Insert.
- **Repro-Referenz:** Session #117 aus Cold-Call-UAT-R2 — 4 ObjectionEvents in Sektion 4 Timeline, Metrik `0/1`.

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

### POLISH-42 — Skript-Abdeckung zeigt konstant 17% unabhängig vom Gesprächsverlauf

- **Severity:** medium
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21, User-Meldung nach B1-Approval)
- **Symptom:** Live-Breakdown-Block Row "Skript-Abdeckung" zeigt konstant `17%` unabhängig davon, welche Skript-Punkte im Gespräch tatsächlich angesprochen werden. Mehrere Test-Sessions mit unterschiedlichem Verlauf liefern denselben Wert.
- **Vermutete Root-Cause:** Hardcoded Default-Wert oder fehlerhafte Berechnungslogik in `services/claude_service.py` / `services/live_session.py` / `routes/app_routes.py`. Möglichkeiten:
  - Eine Konstante `SKRIPT_ABDECKUNG_DEFAULT = 17` o.ä. wird als Fallback gerendert statt des berechneten Werts.
  - Claude-Haiku-Analyse liefert den Wert nicht, der Reducer fängt das silent ab und fällt auf einen Legacy-Default zurück.
  - Division durch `len(profile['skript_punkte'])` mit einem festen Nenner (z.B. 6) und Zähler `1` → ≈17%.
- **Impact:** Metrik verliert komplett ihre Aussagekraft. User vertraut der Score-Hero-Breakdown nicht mehr.
- **Betrifft:** `services/claude_service.py` (analysiere-Call), `services/live_session.py` (State-Update), `routes/app_routes.py` (/api/beenden Response), evtl. `templates/session_detail.html` (Render-Fallback).
- **Fix-Skizze:** Debug-Log bei `skript_abdeckung`-Update ergänzen, Wert-Fluss Backend-→-Template tracen. Prüfen ob `17` eine hardcoded Konstante ist oder das Ergebnis einer deterministischen Division (1/6 ≈ 16.67 → gerundet 17). Nach Root-Cause-Identifikation: echten Wert aus Haiku-Response persistieren.

---

### POLISH-43 — Einwand-Count-Diskrepanz zwischen Post-Call-Quick-Scoring und Session-Detail

- **Severity:** medium
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21)
- **Symptom:** Post-Call-Overlay-Screen zeigt `1 Einwand`, Session-Detail-Seite zeigt für dieselbe Session `4 Einwände`. Beide Werte stammen vom selben Call, zeigen aber unterschiedliche Counts.
- **Vermutete Root-Cause:** Zwei verschiedene Datenquellen werden konsumiert:
  - Post-Call-Overlay liest vermutlich Runtime-State (`live_session.coaching_buffer` oder `state['einwand_counter']`) bevor der Bulk-Insert vollständig committed ist.
  - Session-Detail liest persistierte `ObjectionEvent`-Records aus der DB (korrekter Wert).
  - Mögliche Race-Condition: Overlay rendert bevor `/api/beenden` den finalen Commit abgeschlossen hat.
- **Impact:** User bekommt widersprüchliche Zahlen in derselben Session. Vertrauen in die Auswertung leidet. Verstärkt POLISH-41-Eindruck ("wurde überhaupt etwas erfasst?").
- **Betrifft:** `static/app.js` oder `static/pip-launcher.js` (Post-Call-Overlay-Render), `routes/app_routes.py` `/api/beenden` Response-Payload, Timing der Bulk-Insert-Sequenz.
- **Fix-Skizze:** Overlay-Render verzögern bis `api_beenden` fertig committed (await auf `log_id`-Response), dann `einwaende_gesamt` aus Response-Payload statt aus Runtime-State lesen. Alternativ: Overlay direkt eliminieren zugunsten des Redirects auf `/session/<id>` (siehe POLISH-41-Fix-Scope).
- **Related:** POLISH-38 (einwaende_gesamt-Counter-Bug), POLISH-41 (Post-Call-Overlay "Kein Gespräch erkannt").

---

### POLISH-44 — Recommendation-Text zu generisch ("mit weniger Druck festigen")

- **Severity:** low (Content-Polish)
- **Entdeckt:** Phase 07.2 Cold-Call-UAT-R2 (2026-04-21)
- **Symptom:** `_derive_practice_recommendations()` Live-Rules erzeugen zu generische `explanation`-Strings wie "mit weniger Druck festigen", ohne Bezug auf den konkreten Einwand-Typ (Preis/Zeit/Entscheider/Bedarf/Vertrauen). Die Einwand-Typ-Information ist im Input-State vorhanden, wird aber im Explanation-Template nicht genutzt.
- **Vermutete Root-Cause:** `_derive_practice_recommendations()` in `routes/dashboard.py` (oder analoger Service) verwendet generische Template-Strings ohne Einwand-Typ-Branching. Beispiel aus bisheriger Implementation: `return {'label': '...', 'explanation': 'mit weniger Druck festigen'}` statt `return {'label': '...', 'explanation': f'{einwand_typ}-Einwände mit weniger Druck festigen'}`.
- **Impact:** Sektion 14 "Verbesserungspotenzial" wirkt beliebig und hilft dem User nicht, konkrete nächste Schritte abzuleiten. Coaching-Value sinkt.
- **Betrifft:** `routes/dashboard.py` `_derive_practice_recommendations()`, evtl. `services/recommendations_service.py` falls extrahiert.
- **Fix-Scope:** **Phase 08** (Content-Pass) — einwand-typ-spezifische Templates für Recommendation-`explanation`. Nicht in Phase 07.2 inline-fixen, da reiner Content-/UX-Polish ohne funktionale Blocker.
- **Fix-Skizze:** Mapping-Dict `EINWAND_TYP_EXPLANATIONS = {'preis': '...', 'zeit': '...', ...}` anlegen, in `_derive_practice_recommendations()` pro Event den Typ lookup'en und in den Output-String interpolieren.

---

### POLISH-29 — Einwand-Behandlungs-Definition standardisieren (EWB-Button-gedrückt = behandelt)

- **Severity:** low (Konzeptuelle Klarstellung, keine Code-Änderung zwingend)
- **Entdeckt:** Ursprünglich früher (exakte Herkunft nicht in aktuellem `.planning/`-Tree auffindbar — siehe Grep-Ergebnis: kein anderer POLISH-29-Eintrag im Repo). Refined 2026-04-21 im Kontext von Phase 07.2 Cold-Call-UAT-R2.
- **User-Definition (Produkt-Entscheidung):** **"EWB-Button gedrückt = Einwand behandelt."** Das ist die verbindliche Standard-Definition für alle Metriken, UI-Labels und Post-Call-Analysen. Keine heuristische Metrik (z.B. "Einwand behandelt wenn innerhalb von 15s ein Gegenargument im Transkript"), sondern die explizite User-Aktion.
- **Impact:** Aktuelle Metriken/Counter (z.B. "Einwände behandelt X/N") müssen diese Definition konsistent anwenden. POLISH-38-Fix muss `ewb_clicks` als Grundlage für `einwaende_gesamt`-Increment nutzen (nicht automatische Heuristik).
- **Betrifft:** Dokumentation (`.planning/REQUIREMENTS.md` falls Metrik-Definition dort), `routes/app_routes.py` `/api/beenden`-Counter-Logik, `services/live_session.py` EWB-State-Tracking, `templates/session_detail.html` Label-Text bei Sektion 4.
- **Fix-Skizze:** Keine eigenständige Code-Change — diese Definition ist die Reference für POLISH-38. Separater Eintrag dient als zitierbare Produkt-Entscheidung für zukünftige Planungsphasen und zur Vermeidung von Re-Diskussionen.
- **Cross-Reference:** Falls in älteren Phase-Dokumenten (z.B. Phase-04.x DEVIATIONS oder pre-GSD-Vault) ein älterer POLISH-29-Eintrag mit abweichender Definition existiert, überschreibt diese User-Definition den Altstand. Siehe Grep 2026-04-21: kein Match in `.planning/**`.

---

### POLISH-49 — `DEEPGRAM_HOST` Environment-Variable wird nicht gelesen (DSGVO-EU-Region inaktiv)

- **Severity:** **critical** (Launch-Blocker für DACH/DSGVO-Compliance)
- **Entdeckt:** Debug-Session POLISH-48 (2026-04-21), Bonus-Finding im `services/deepgram_service.py`-Review
- **Symptom:** `.env.example` deklariert `DEEPGRAM_HOST=api.eu.deepgram.com` (EU-Endpoint für DSGVO-konforme Audio-Verarbeitung), aber der Code liest diese Variable nirgends. `DeepgramClient(DEEPGRAM_API_KEY)` in `services/deepgram_service.py:181` wird ohne Host-Override instanziiert → Default-Host ist `api.deepgram.com` (US-Endpoints).
- **Impact:** **DSGVO-Architektur-Bruch.** NERVE sendet aktuell alle Live-Audio-Chunks an US-Endpoints, obwohl CLAUDE.md-Constraint explizit fordert: "DSGVO: Pflicht von Tag 1 — Server in Deutschland (Hetzner), kein wörtliches Mitschneiden default." Muss vor Launch gefixt werden — sonst Datenschutz-Verstoss bei jeder Live-Session.
- **Betrifft:** `config.py` (Env-Variable laden), `services/deepgram_service.py:181` (ClientOptions mit `url="https://api.eu.deepgram.com"` instanziieren), `.env` (Deploy-Key setzen auf Hetzner-VPS).
- **Fix-Skizze:** In `config.py`: `DEEPGRAM_HOST = os.getenv("DEEPGRAM_HOST", "api.eu.deepgram.com")`. In `deepgram_service.py`: `DeepgramClient(DEEPGRAM_API_KEY, config=DeepgramClientOptions(url=f"https://{DEEPGRAM_HOST}"))`. Deploy auf VPS mit `DEEPGRAM_HOST=api.eu.deepgram.com` in `.env`. Runtime-verify: Netzwerk-Check zeigt Requests an `eu`-Host.
- **Cross-Reference:** Deepgram-SDK `DeepgramClientOptions(url=...)` Pattern siehe SDK v3.10.0.

---

### POLISH-50 — Client-Side Audio-Chunk Start-Race (audio_chunk emittet vor start_live_session)

- **Severity:** low (wenige Frames betroffen, mode-unabhängig)
- **Entdeckt:** Debug-Session POLISH-48 (2026-04-21), Bonus-Finding in `static/pip-launcher.js:877-965`
- **Symptom:** In `_startAudio()` wird der AudioWorklet angelegt (Zeile 923) und emittet sofort `audio_chunk`-Frames. DANACH erst, am Ende von `_startAudio()` (Zeile 965), wird `start_live_session` emittet. Wenige Worklet-Frames zwischen Setup (L920-929) und `start_live_session`-Emit (L965) werden vom Server silent dropped, weil `_deepgram_sessions.get(_sid)` noch `None` zurückgibt.
- **Impact:** Minimaler Audio-Verlust am Session-Start (wenige Millisekunden, typischerweise Stille oder Atem). Nicht user-wahrnehmbar, aber unsauber.
- **Betrifft:** `static/pip-launcher.js:877-965`, `static/app.js:55-57`, Server-Side `handle_audio_chunk` in `services/deepgram_service.py`.
- **Fix-Skizze:** Entweder (a) `start_live_session` VOR der Worklet-Instanziierung emittet und auf Ack warten, oder (b) Server-Side die ersten N Chunks nach `start_live_session` buffern bis Deepgram-Connection ready ist. Option (a) ist sauberer.
- **Gilt für alle Modi** (Cold Call + Meeting) — nicht mode-spezifisch.

---

### POLISH-45 — Headset-Modal-Reset (15-Min-Fix)

- **Severity:** medium (UX-Polish, User-Flow)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Symptom:** Headset-Modal (Phase 06.4 DSGVO-Hardening) persistiert User-Wahl über Session-Grenze hinweg. Wenn der User bei einer Session "Headset bestätigt" klickt und später ohne Headset eine neue Session startet, wird das Modal nicht erneut gezeigt — gefährdet DSGVO-Compliance-Nachweis.
- **Vermutete Root-Cause:** LocalStorage-Key oder Session-Cookie behält Headset-Confirm-State und wird bei neuem `/live`-Aufruf nicht zurückgesetzt. Sollte pro Session (nicht pro Browser-Installation) neu bestätigt werden.
- **Fix-Skizze:** Headset-Confirm-State bei `/live`-Route-Start clearen (z.B. `localStorage.removeItem('headset_confirmed')` oder Session-scoped State in `sessionStorage`). Alternativ Server-Side per-Session-Flag.
- **Fix-Aufwand:** ~15 Min (Frontend-One-Liner + Test).
- **Scope:** separate kleine Phase (POLISH-38-Teilfix + POLISH-45 bundled) nach Phase 07.4.

---

### POLISH-38.1 — Teilfix: success-Flag bei manual_ewb (10-Min-Fix, Ergänzung zu POLISH-38)

- **Severity:** low (Metrik-Präzision)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Parent:** POLISH-38 Counter-Fix in Commit `cf38589` behob `einwaende_gesamt` (zählt jetzt `len(ewb_clicks)`). Offen bleibt: `manual_ewb`-Events (User-Klick ohne Claude-Auto-Detection) haben aktuell kein `success`-Flag — Metriken "erfolgreich behandelt" können nicht zwischen EWB-Klick (counted) und tatsächlich erfolgreicher Behandlung (via Claude-Scoring) diskriminieren.
- **Vermutete Root-Cause:** `ObjectionEvent.success` wird beim manual_ewb-Insert nicht gesetzt (Default vermutlich NULL). Post-Call-Scoring-Heuristik kann daher nur "versucht behandelt" tracken, nicht "erfolgreich".
- **Fix-Skizze:** In `routes/app_routes.py` beim manual_ewb-Insert `success=None` explizit setzen oder per Claude-Re-Evaluation im Post-Call-Flow setzen.
- **Fix-Aufwand:** ~10 Min.
- **Scope:** bundled mit POLISH-45 in einer kleinen Follow-up-Phase.

---

### POLISH-53 — EWB-Feed-Redesign (Phase-07.5-Kandidat)

- **Severity:** medium (UX, löst Slot-Dominanz-Problem)
- **Entdeckt:** Phase 07.4 Debug-Cluster-UAT (2026-04-21)
- **Symptom:** Aktueller EWB-Bereich hat nur 2 Slots die bei neuen Einwänden die alten Einwände überschreiben. User verlieren kontext bei schnellen Gesprächen mit vielen Einwänden. "Slot-Dominanz" — die zuerst angezeigten Einwände verdrängen sich gegenseitig ohne History.
- **Redesign-Idee:** Scrollbarer EWB-Feed statt 2-Slot-Overwrite — aktive + bereits behandelte Einwände in chronologischer Liste. Löst Slot-Dominanz, gibt User historischen Kontext über das Gespräch.
- **Scope-Impact:** nicht-trivial — neue Komponenten-Architektur, UX-Spec-Runde, Template + CSS + JS-State-Management. Gehört als **Phase 07.5** separat geplant (nicht Teil von 07.4).
- **Planung:** via `/gsd-plan-phase 07.5` sobald 07.4-Follow-up abgeschlossen.

---

## Referenzen

- Phase 07.2 UAT-R2 Cold-Call-Checkpoint: 2026-04-20, Session #117 als Test-Referenz
- Phase 07.2 Cold-Call-UAT-R2-Approval: 2026-04-21 (nach B1-Fix: POLISH-42/43/44 neu, POLISH-38 refined, POLISH-29 konsolidiert)
- B1 aus UAT-R2 (Sektion 14 Dubletten) wurde in Phase 07.2 inline gefixt (Commit `e040ee7`)
- POLISH-35, POLISH-36, POLISH-37 bleiben deferred aus Phase 07.1 (siehe ROADMAP.md Zeile 711-717)
- POLISH-44 Fix-Scope ausdrücklich Phase 08 (Content-Pass), nicht Phase 07.2
- Phase 07.4 Debug-Cluster (2026-04-21): POLISH-48/41/49/38/40/39/42/51/52/46 resolved + deploy-verified in Session #124. POLISH-45/-38.1/-53 als Follow-ups herausgelöst.
