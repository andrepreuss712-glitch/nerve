---
audit: deep-dive-training-learning-coach
erstellt: 2026-04-24
autor: Claudian (Welle-3-Routes-Scan)
scope:
  - routes/training.py (1331 Z., vollständig)
  - routes/learning.py (279 Z., vollständig)
  - routes/coach.py (279 Z., vollständig)
  - services/coaching_service.py (Context für learning.py, Sonnet-Pfad)
  - services/training_service.py (Context für Cost-Tracking + Claude-Call-Sites)
  - services/integration_engine.py (Post-Training-Pfad)
  - Frontend-Kopplung: templates/training.html (kein static/training.js), templates/coach_*.html
basiert_auf:
  - MASTER-AUDIT (Welle 1+2)
  - Stichproben-Vorwissen zu learning.py:268-269 (hardcoded Redeanteil)
  - Welle-2-Finding: Training-Service Cost-Tracking = NULL
---

# Deep-Dive: routes/training.py + learning.py + coach.py

**Scan-Dauer:** ~18 min. Code gilt, Doku ignoriert.
**Methode:** Call-Graph rückwärts (Route → Service), Frontend-Kopplung forward (JS → Route), TODO/Hardcoded/Silent-Failure/Schema-Drift.

---

## EXECUTIVE SUMMARY

Drei Routen-Dateien, drei unterschiedliche Krankheitsbilder:

- **training.py:** funktioniert end-to-end, aber **Cost-Tracking-Blackhole** (5+ Claude-Calls pro Session unsichtbar, plus 1 Haiku-Call inline in der Route selbst). Zusätzlich: Mode-Kollision beim Personality-Pfad + Exception-Leak an Client.
- **learning.py:** hat das bereits bekannte `redeanteil_berater=60/40` Fake-Metrik-Problem als **einziges** hardcoded-Fake. Alle anderen Parameter werden entweder aus Request oder aus `ConversationLog` gelesen. Kein Ghost-State. ABER: `generate_postcall_analysis` wird **ohne `profile_data`-Parameter** aufgerufen — doppelte Bestätigung der H-6 aus Master-Audit.
- **coach.py:** **komplettes Dead-Feature** — Live-Coach-Tipps (Push + Poll) haben null Frontend-Caller. Plus: OwaspV-Lücke bei `firma_einladen` (Owner-Email-Validation fehlt).

**Neue Funde:** 2 HIGH, 7 MEDIUM, 4 LOW. Keine neuen Launch-Blocker, aber **H-NEW-1** (Coach-Live-Tipps Dead) ist ein "Feature-Fake"-Befund ganz in der Reihe von PreCall-Briefing.

---

## ROUTES-MATRIX

### routes/training.py — 17 Endpoints

| # | Route | Methode | Aufrufer-Status | Service-Abhängigkeit |
|---|---|---|---|---|
| 1 | `/training/ping` | GET | **NIEMAND** — dev-only | keiner |
| 2 | `/training` | GET | direkt vom User (Browser) | templates/training.html |
| 3 | `/training/start` | POST | training.html:954 | training_service: 5 Fkt. |
| 4 | `/training/respond` | POST | training.html:1172 | training_service: 3 Fkt. |
| 5 | `/training/help` | POST | training.html:1353 | training_service.generate_help_suggestion |
| 6 | `/training/end` | POST | training.html:1416 | training_service.generate_scoring + _generate_live_preview + integration_engine.run_posttraining_engine |
| 7 | `/training/transcribe` | POST | training.html:1327 | deepgram direkt (nicht services/deepgram_service!) |
| 8 | `/api/training/personalities` | GET | training.html:816,1821 | DB only |
| 9 | `/api/training/personalities/generate` | POST | training.html:863 | **inline Claude-Call** (kein Service) |
| 10 | `/api/training/personalities/save` | POST | **NIEMAND** — tote Route | DB only |
| 11 | `/training/scenarios` | GET | training.html:900,1640 | DB only |
| 12 | `/training/scenarios` | POST | training.html:1771 | DB only |
| 13 | `/training/scenarios/<sid>` | DELETE | training.html:1802 | DB only |
| 14 | `/api/training/stats` | GET | training.html:1895 | DB only |
| 15 | `/api/training/recommendation` | GET | training.html:2042 | DB only |
| 16 | `/api/training/last-session` | GET | training.html:2121 | DB only |
| 17 | `/api/training/phrases` | GET | **NIEMAND** gefunden in HTML/JS | DB only |
| 18 | `/api/training/goal` | POST | training.html:2156 | DB only |

**Orphan-Routes:** #1 (dev), #10 (siehe H-NEW-2), #17 (Phrases-API ohne Reader — `api_training_phrases` wartet auf "Phrase-Gallery"-Feature das nie gebaut wurde; Route ist konsistent und funktionsfähig aber stehen gelassen).

### routes/learning.py — 7 Endpoints

| # | Route | Methode | Aufrufer | Service-Call |
|---|---|---|---|---|
| 1 | `/api/postcall_analysis` | POST | static/app.js:1121 | coaching_service.generate_postcall_analysis |
| 2 | `/api/learning_cards` | GET | app.js:1196,1239,1269 | DB only |
| 3 | `/api/learning_cards/<id>/save` | POST | app.js:1204 | integration_engine.log_learning_event |
| 4 | `/api/learning_cards/<id>/regenerate` | POST | **NIEMAND** in app.js grep | DB only |
| 5 | `/api/learning_cards/<id>/status` | POST | **NIEMAND** in app.js grep (evtl. inline in app.js) | integration_engine.log_learning_event |
| 6 | `/api/learning_cards/<id>/applied` | POST | app.js:1293 | integration_engine.log_learning_event |
| 7 | `/api/learning_cards/<id>/user_text` | POST | app.js:1245 | coaching_service.validate_user_text |
| 8 | `/api/training/postcall-analysis` | POST | **NIEMAND** gefunden in grep | coaching_service.generate_postcall_analysis |

**Kritisch:** #8 (Training-PostCall) hat laut Master-Audit und Welle-2-Bestätigung die **hardcoded Redeanteil-60/40-Lüge**. Die Route selbst wird vom Frontend aktuell nicht aufgerufen (grep auf `/api/training/postcall-analysis` = 0 Treffer in static/templates). **Es ist möglich dass diese Route als ganze toter Code ist** und die Phase-04.12 D-09-Implementierung nie Frontend-Callsite bekam. **Weitere Verifikation nötig.**

### routes/coach.py — 10 Endpoints

| # | Route | Methode | Aufrufer-Status | Findung |
|---|---|---|---|---|
| 1 | `/coach/` | GET | base.html navigation (indirekt) | OK |
| 2 | `/coach/firma/<id>` | GET | coach_dashboard.html:57 | OK |
| 3 | `/coach/firma/einladen` | POST | coach_dashboard.html:147 | siehe H-NEW-3 |
| 4 | `/coach/firma/<id>/profile/neu` | POST | coach_firma.html:266 | OK |
| 5 | `/coach/methodik/uebertragen` | POST | coach_firma.html:239, coach_methodik.html:94 | OK |
| 6 | `/coach/live_tipp` | POST | **NIEMAND** — dead | H-NEW-1 |
| 7 | `/coach/api/tipps` | GET | **NIEMAND** — dead | H-NEW-1 |
| 8 | `/coach/api/my_profiles` | GET | coach_firma.html:220 | OK |
| 9 | `/coach/methodik` | GET | base.html:83 | OK |

---

## 🟠 NEUE HIGH-SEVERITY-FUNDE

### H-NEW-1: Coach-Live-Tipp-Feature komplett tot

**Evidence:**
- `routes/coach.py:199-232` — `live_tipp()` schreibt in `ls.coach_tipps` queue
- `routes/coach.py:237-247` — `api_tipps()` liest + leert queue
- `grep` für `/coach/api/tipps` und `/coach/live_tipp` in `static/**` und `templates/**`: **0 Treffer**
- `grep` für generisches `/api/tipps`: 0 Treffer

**Folge:**
- Coaches können Live-Tipps absenden (UI müsste es geben — unklar ob auch die UI-Trigger fehlen), Berater bekommen sie **nie** zu sehen.
- `services/live_session.py:53-54` hält eine thread-sichere `coach_tipps`-Queue + Lock permanent im Prozess — wächst monoton wenn Coaches tippen, wird nur durch den toten Poll-Pfad geleert.
- Memory-Leak bei aktivem Coach-Use.

**Verdacht:** Feature war Teil einer Coach-Phase (vermutlich 04.8/04.9-Ära), Frontend-Polling wurde nie gebaut oder beim Refactor weggeputzt ohne Backend-Cleanup.

**Fix:** Entscheidung — entweder Frontend-Polling im app.js bauen (Pip-Launcher wäre der Ort), oder beide Routes + `coach_tipps`-Queue in live_session.py entfernen. **Empfehlung:** Entfernen. Live-Coach-Tipps sind keine priorisierte Feature im aktuellen Roadmap-Stand.

**Fix-Aufwand:** 30 min Remove, 4-6h Neubau.

---

### H-NEW-2: `/api/training/personalities/save` tot — Frontend-Aufrufer wurde in Phase 07.2 entfernt

**Evidence:**
- `routes/training.py:984-1013` — `api_training_personality_save()` voll funktionsfähig, persistiert PersonalityType
- `grep "personalities/save"` in static+templates: **0 Treffer** im Live-Code
- `templates/training.html:1633` hat expliziten Kommentar: `// ENTFERNT in 07.2 Wave 3: saveGeneratedPersonality() war nur aus dem Post-Call-` (Orphan-Cleanup nach Scoring-Overlay-Removal)
- Phase-07.2-03-SUMMARY.md: "saveGeneratedPersonality() function removed as orphan: only caller was save-personality-div (inside removed scoring overlay). Re-introduction under POLISH-37"

**Folge:**
- User kann generierte Persönlichkeiten nicht mehr speichern. Die generierte Persona ist pro-Session-Einmal-Nutzung.
- Backend-Route + DB-Table-Spalte `PersonalityType.is_custom=True + user_id` sind Ghost.
- Phase-07.2 hat **Frontend-Caller entfernt ohne Backend-Route zu prunen** — klassischer Phase-Closeout-ohne-Pruning-Muster (Master-Audit Muster 1).

**Fix-Entscheidung nötig:**
- **Option A:** POLISH-37 umsetzen — Save-Button in die Briefing-Card (nach `generateRandomPersonality`) einbauen, dann ist die Backend-Route wieder live.
- **Option B:** Route + zugehörige DB-Felder entfernen, Custom-Personalities werden nie persistiert.

**Empfehlung:** Option A. Der User-Flow (Custom-Kunden wiederverwenden) ist ein echtes UX-Plus. ~1h Frontend-Arbeit.

**Fix-Aufwand:** 1h (A) oder 30 min (B).

---

## 🟡 NEUE MEDIUM-SEVERITY-FUNDE

### M-NEW-1: `firma_einladen` — Owner-Email + Invite ohne Uniqueness-Check

**Evidence:** `routes/coach.py:87-123`.

```python
org = Organisation(name=firmname, plan=plan, max_users=max_users,
                   billing_email=email, coach_id=g.user.id)
db.add(org); db.flush()
token = secrets.token_urlsafe(32)
inv = Invitation(org_id=org.id, email=email, token=token)
```

**Folge:**
- Kein Check ob `email` bereits registriert ist (es gibt keinen `User.query.filter_by(email=email).first()`). Wenn der Owner-User schon existiert (z.B. wechselt Firma), wirft der spätere Register-Flow eine Constraint-Violation → UX-Bruch.
- Kein Check ob `firmenname` bereits existiert → Duplikate möglich.
- Plan-Value `data.get('plan', 'starter')` ist ungeprüft — wenn der Coach JSON mit `"plan": "enterprise"` sendet, wird `enterprise` in die Org geschrieben, obwohl PLANS nur starter/pro/business kennt (config.py-Drift siehe Master-Audit).

**Fix:** 30 min (Validation + 400-Response bei Dupes oder invalid-plan).

---

### M-NEW-2: `/coach/api/tipps` — NoneType-Crash wenn User ohne Org

**Evidence:** `routes/coach.py:244` — `t.get('org_id') == g.org.id or t.get('user_id') == g.user.id`.

Wenn `g.org` None ist (User direkt registriert ohne Org-Context, edge case), wirft `g.org.id` AttributeError. Selbst wenn das in der Praxis nicht passiert, ist es Tech-Debt. Bei dead-feature H-NEW-1 aber moot — sobald die Route entfernt wird, gelöst.

### M-NEW-3: `/coach/api/tipps` fehlt `@coach_required`

**Evidence:** `routes/coach.py:237-239` — nur `@login_required`.

**Bewusst** (Berater ist der Consumer), aber filtert nur nach `org_id == g.org.id`. D.h. jeder User in einer Org kann die Tipp-Queue der eigenen Org leer-pollen. **Nur relevant wenn das Feature live geht** (H-NEW-1-Fix).

### M-NEW-4: Training-Session-State im Modul-globalen `_sessions`-Dict — Multi-Worker-Blocker

**Evidence:** `routes/training.py:40-41`:
```python
_sessions      = {}
_sessions_lock = threading.Lock()
```

Key ist `g.user.id`. Bei Multi-Worker-Deployment (Gunicorn) wird `_sessions` pro Worker separat gehalten → wenn User-Request erst bei Worker A (start) und dann bei Worker B (respond) landet → "Keine aktive Session".

**Kombiniert mit LB-8 (Master-Audit) zu Multi-Worker-Risiko:**
- LB-8 warnt vor n-fach analyse_loop + coaching_loop bei Multi-Worker.
- M-NEW-4 warnt zusätzlich vor User-State-Loss bei Training.

Aktueller Modus ist Single-Worker (SocketIO-threading), also OK. **Aber vor horizontaler Skalierung Pflicht-Fix** — entweder sticky sessions oder DB/Redis-backed session store.

**Fix-Aufwand:** 3-4h (Redis/DB-Migration).

### M-NEW-5: `training_start` Exception-Leak an Client (LB-7-Familie)

**Evidence:** `routes/training.py:401-408`:
```python
except Exception as _start_err:
    tb = traceback.format_exc()
    ...
    last_frame = ' | '.join(lines[-3:]) if len(lines) >= 3 else tb[-300:]
    return jsonify({'ok': False, 'error': f'{last_frame[:500]}'}), 500
```

**500 Zeichen Traceback-Frames** werden an den Client retourniert. Gleiche Klasse wie LB-7 (app.py:1697-1726). Plus: gleicher Leak in Zeile 296-299 (`generate_response`-Wrapper), 603-606 (`training_help`), 978-981 (`personality_generate`), 1007-1011 (`personality_save`).

**Fix:** 30 min (alle traceback-Returns auf generische Message + Server-Log umstellen).

### M-NEW-6: Training-Claude-Calls hardcoded Model × 3

**Evidence:** `services/training_service.py:817, 869, 1004, 1188, 1266` — insgesamt 5 Stellen mit `model="claude-haiku-4-5-20251001"` bzw. `"claude-sonnet-4-6"`. Plus **1 zusätzliche Stelle** in `routes/training.py:966` (inline-Claude-Call für Personality-Generate).

Master-Audit zählte 11 Gesamt-Stellen (9 in claude_service.py + 2 in app_routes.py). **Neue Gesamtzahl: ≥17 Stellen** (11 + 5 in training_service + 1 in routes/training.py). Bei Model-Wechsel 17 Edits.

**Fix:** 30 min (`config.MODEL_HAIKU` / `MODEL_SONNET` Konstanten).

### M-NEW-7: `learning.py` — `/api/training/postcall-analysis` ohne Frontend-Caller

**Evidence:** `routes/learning.py:235-279` voll implementiert. `grep "/api/training/postcall-analysis"` in static/+templates/: **0 Treffer**.

**Folge:** Die gesamte Training-Post-Call-Lernkarten-Pipeline (D-09 aus Phase 04.12) ist **zwar Code-komplett aber nie getriggert**. Das **neutralisiert** den Redeanteil-60/40-Hardcode-Bug (H-5 Master-Audit) **wenn das Feature wirklich tot ist** — aber es bedeutet auch dass die Phase 04.12 D-09-Implementation de facto nie live war.

**Verdacht:** Feature wurde gebaut, Frontend-Trigger kam nie. Gleicher Patterns wie PreCall-Briefing (H-2 Master-Audit).

**Verifikation nötig:** Läuft diese Route irgendwo über automated trigger (z.B. post-training Hook in app.js)? Tiefer-Scan app.js:1121 und Umgebung → der `/api/postcall_analysis` ist für **Live-Calls**, nicht Training. Training-Path müsste eigene Call-Site haben.

**Fix-Entscheidung nötig** — entweder Frontend-Trigger bauen oder Route entfernen.

---

## 🟢 LOW / KOSMETIK

### L-NEW-1: `/training/ping` orphan dev-route

`routes/training.py:45-47` returnt `_CODE_VERSION` (git short hash). Kein Caller. Gedacht für Deploy-Verifikation, aber bei aktivem Auto-Deploy redundant. Entweder löschen oder in `/healthz` zusammenlegen.

### L-NEW-2: `_CODE_VERSION` hardcoded

`routes/training.py:42: _CODE_VERSION = '45b02eb'` — git-short-hash als Python-Konstante. Wird bei jedem Deploy manuell aktualisiert? Driftet garantiert. Sollte via `git rev-parse` in CI injiziert werden oder ganz weg.

### L-NEW-3: `needs_learning_card` dead local var (Master-Audit M-Funding bestätigt)

`services/integration_engine.py:245-264` — Flag wird gesetzt aber nie `return`ed, nie in globalen State geschrieben. Plan-03-Implementierung (Lernkarten-Auto-Generation bei Training-Schwäche) wurde nie gebaut. 3 Zeilen sind tote Signal-Pipeline.

### L-NEW-4: `/training/transcribe` nutzt nicht den gemeinsamen DeepgramClient

`routes/training.py:834-854` instantiiert `DeepgramClient(DEEPGRAM_API_KEY)` direkt statt den globalen aus `services/deepgram_service.py` zu nutzen. Kleine Ineffizienz + Cost-Hook-Bypass (kein `log_api_cost` für Training-STT).

**Verifikation:** Ja, `training_transcribe` hat **0 Cost-Tracking** für STT. Reiht sich in Welle-2-Finding "Training-Service Null Cost-Tracking" ein — aber **hier ist der STT-Weg** (REST-Prerecorded, nicht Socket) und Training-STT-Calls werden zu den Deepgram-Costs addiert ohne in `ApiCostLog` zu landen.

**Fix-Aufwand:** 30 min (Cost-Hook einbauen, Dauer aus Audio-Bytes oder Response schätzen).

---

## ✅ NICHT-FUNDE (zur Entlastung)

Dinge die ich geprüft habe und die **OK** sind:

- **`_ensure_dict()` Helper** (training.py:22-38): robust, handled Double-JSON-Encoding, None, Non-Dict-Strings.
- **`_detect_female()` Heuristik** (training.py:67-86): solide, priorisiert `geschlecht`-Feld korrekt, Namens-Fallback ist ergänzend.
- **Thread-Sicherheit `_sessions`-Dict**: Lock ist konsistent angewandt, WR-04 sauber umgesetzt (Lock für Turn-Count-Read).
- **User-Scoping in allen Routes**: `filter_by(user_id=g.user.id)` oder `org_id=g.org.id` konsistent in allen Learning+Coach+Training-Endpoints gesetzt. T-04.11-02 in learning.py explizit (Ownership-Check).
- **Voice-Fair-Use Monthly-Reset** (training.py:100-117): funktioniert, usage_reset_date + minuten_used werden sauber monatlich genullt.
- **Streak-Update** (training.py:754-768): days_diff-Logik korrekt, same-day no-op respektiert.
- **Points-Level-Mapping** (training.py:812-816): reversed-iteration korrekt, nutzt höchsten erreichten Level.
- **D-01 Event-Logging-Kette** in learning.py: `learning_card_accepted`, `_rejected`, `_applied`, `_custom` alle sauber vor commit gerufen mit silent-exception-handling (kein DB-Bruch).
- **Duplicate-Guard in `generate_postcall_analysis`** (coaching_service.py:61-72): `T-04.11-05` korrekt umgesetzt — LearningCard-Count-Check verhindert Doppel-Sonnet-Calls pro conv_id.

---

## 🔗 VERKOPPLUNGS-MATRIX (Frontend → Route → Service)

```
templates/training.html
  ├── loadPersonalityTypes() ─► GET /api/training/personalities
  ├── generateRandomPersonality() ─► POST /api/training/personalities/generate
  │    └── [DEAD] saveGeneratedPersonality() ─X─► /api/training/personalities/save
  ├── startTraining() ─► POST /training/start ─► training_service.{build_*_prompt, generate_response_with_mood, text_to_speech}
  ├── respond() ─► POST /training/respond ─► training_service.{generate_response, generate_response_with_mood, text_to_speech}
  ├── askForHelp() ─► POST /training/help ─► training_service.generate_help_suggestion
  ├── transcribe() ─► POST /training/transcribe ─► deepgram direkt
  └── endTraining() ─► POST /training/end ─► training_service.{generate_scoring, _generate_live_preview} + integration_engine.run_posttraining_engine

static/app.js (Post-Live-Call-Flow)
  ├── /api/postcall_analysis ─► coaching_service.generate_postcall_analysis [profile_data fehlt — H-6]
  ├── /api/learning_cards (GET/POST save/applied/user_text) ─► integration_engine.log_learning_event
  └── learning_cards/regenerate + status: kein Frontend-Caller im grep — evtl. inline-event-handlers

[UNCOUPLED]
  ├── /coach/live_tipp ──────► nur Backend (kein UI) ─ H-NEW-1
  ├── /coach/api/tipps ──────► nur Backend (kein Poll) ─ H-NEW-1
  ├── /api/training/personalities/save ─► nur Backend ─ H-NEW-2
  ├── /api/training/postcall-analysis ─► nur Backend ─ M-NEW-7
  ├── /api/training/phrases ─► unsicher (grep 0, evtl. in Phrase-Gallery-UI die's nie gab)
  └── /training/ping ─► dev-only
```

---

## 🎯 PRIORISIERUNGS-VORSCHLAG

### Sofort (vor EA-Launch, kombinierbar mit Master-Audit Block 1+2):
1. **M-NEW-5:** Exception-Leaks in `training_start`, `training_help`, `personality_generate` schließen (zusammen mit LB-7). **30 min.**
2. **H-NEW-1:** Entscheidung Coach-Live-Tipps — **entfernen** für EA (30 min), oder später in Phase X komplett neu bauen.
3. **H-NEW-2:** Entscheidung Personality-Save — **wiederherstellen** Button (1h, UX-Gewinn), oder Route+Feld entfernen.
4. **M-NEW-7:** Verifizieren ob `/api/training/postcall-analysis` wirklich tot ist. Wenn ja: zusammen mit H-5 (Redeanteil-Fix) entscheiden ob Feature live oder weg.

### Härtung (nach EA):
5. **M-NEW-4:** Multi-Worker-Session-State. Vor horizontaler Skalierung Pflicht.
6. **M-NEW-6:** Model-Konstanten in config.py.
7. **M-NEW-1:** Coach-Firma-Einladung Email-Uniqueness + Plan-Validation.
8. **L-NEW-4:** Training-STT Cost-Hook.

### Kosmetik:
9. **L-NEW-1,2:** `/training/ping` und `_CODE_VERSION` cleanup.
10. **L-NEW-3:** `needs_learning_card` dead var entfernen.

---

## 📊 HEALTH-SNAPSHOT der 3 Dateien

| Datei | Status | Cost-Tracking | Dead-Code | Frontend-Kopplung | Silent Failures |
|---|---|---|---|---|---|
| `routes/training.py` | 🟡 funktioniert, aber 3 dead endpoints + Exception-Leaks | 🔴 null (nur TTS via service) | 🟠 3 Dead-Routes | 🟢 14/17 verkoppelt | 🟢 print+return sauber |
| `routes/learning.py` | 🟠 Training-PostCall ist Feature-Fake | 🟢 via coaching_service OK | 🟠 1 Dead-Route | 🟡 6/7 verkoppelt | 🟢 OK |
| `routes/coach.py` | 🔴 Live-Tipp komplett tot + Validation-Lücken | 🟢 (keine LLM-Calls) | 🔴 2 Dead-Routes (20%) | 🔴 7/9 verkoppelt (22% tot) | 🟡 NoneType-Risiko |

---

## 🔍 NUDELCODE-MUSTER bestätigt

Alle 5 Nudelcode-Muster aus Master-Audit finden sich auch in diesen 3 Routes wieder:

1. **Phase-Refactor ohne Pruning** → H-NEW-2 (Phase 07.2 Frontend-Cleanup ohne Backend-Prune)
2. **Phase-Closeout ohne Live-Path-Verification** → M-NEW-7 (D-09 implementiert, nie live)
3. **Test-False-Greens** → VERIFICATION.md der Phase 04.9 hat alle 3 Personality-Routes als VERIFIED markiert, ohne Frontend-Integration-Check
4. **Hardcoded Placeholder** → `redeanteil=60/40` (bekannt), `_CODE_VERSION='45b02eb'` (neu)
5. **State-Mutations-Drift** → `coach_tipps`-Queue in live_session.py wird geschrieben, nie gelesen (Writer ohne Reader-Pfad)

---

*Scan abgeschlossen: 2026-04-24, ~18 min. Alle Funde Code-verifiziert. Keine Annahmen aus Doku übernommen.*
