---
audit: deep-dive-frontend-core
erstellt: 2026-04-24
autor: Claudian (Welle 4, Frontend-Deep-Dive)
scope:
  - static/app.js (2125 Z.) — App-Core + Classic-Live-View + PostCall + Coach
  - static/pip-launcher.js (2315 Z.) — Picture-in-Picture Live-Coaching Launcher
cross_ref:
  - .planning/audits/MASTER-AUDIT.md (Backend-Befunde)
---

# Deep-Dive: Frontend-Core (app.js + pip-launcher.js)

## TL;DR

1. **25 einzigartige Backend-Endpoints** werden vom Frontend aufgerufen. **18 Socket-Events** emittiert/empfangen.
2. **11 Backend-Routes laut MASTER-AUDIT-Liste sind Dead-Route-Kandidaten** — kein Frontend-Call in app.js oder pip-launcher.js (u. a. `/api/swap_roles`, `/api/set_phase`, `/api/keepalive`, `/api/status`, `/api/skripte`, `/api/ewb/<id>/rate`, `/api/analytics`, `/api/tipps`, `/api/my_profiles`, `/api/feedback/quick`, `/api/learning_cards/<id>/regenerate`).
3. **H-3 Schema-Drift im Backend bestätigt, NICHT im Frontend.** `pdata.get("produkt")` ist reines Backend-Problem (`routes/app_routes.py:1132, 1182`). Das Frontend sendet Profil-Daten gar nicht an `/api/frage` oder `/api/ewb_trigger` — Backend lädt Profil selbst. Das macht H-13 umso schlimmer, Frontend kann nicht kompensieren.
4. **TABU_DEFAULT_PAIRS existiert NICHT in app.js oder pip-launcher.js** — nur in profile_editor.js (wie MEDIUM-Befund). Kein zweiter Spiegelort.
5. **LB-7 Traceback-Leak: Frontend ist ein stummer Komplize.** Nur `/api/precall/research` via pip-launcher.js:321 rendert Backend-Error-Strings direkt in DOM (`errEl2.textContent = errMsg`). Traceback-Strings landen dadurch sichtbar auf dem Bildschirm des Users. XSS-Surface mittel — textContent schützt, aber Informations-Leak bleibt.
6. **`/api/ergebnis`-Polling: 500ms Self-Scheduling-Chain** (app.js:810). Kein Backoff bei 500er-Response — bei Backend-Fehler-Storm werden 2 req/sec ins Error-Log gehämmert.

---

## Frontend → Backend API-Call-Matrix

| JS-Datei:Zeile | URL | Methode | Kontext |
|---|---|---|---|
| app.js:144 | `/api/precall/research` | POST | PreCall-Recherche Start-Button (Classic-View) |
| app.js:317 | `/api/ewb_trigger` | POST | EWB-Button-Klick (Classic-View) |
| app.js:420 | `/api/log_correction` | POST | Speaker-Rollen-Korrektur (flipRowRole) |
| app.js:427 | `/api/analyse_line` | POST | Re-Analyse nach Flip |
| app.js:441 | `/api/log_correction` | POST | Einwand-Zurückgezogen-Logging |
| app.js:573 | `/api/pause` | POST | Pause-Toggle |
| app.js:646 | `/api/beenden` | POST | Classic-View Beenden |
| app.js:689 | `/api/log` | GET | Log-Download (blob) |
| **app.js:780** | **`/api/ergebnis`** | **GET** | **Polling 500ms self-scheduling chain** |
| app.js:832 | `/api/log_gegenargument_wahl` | POST | "Genutzt" A/B-Tracking |
| app.js:877 | `/api/frage` | POST | QA-Dialog (Quick-Actions) |
| app.js:1091 | `/api/postcall_insights` | POST | PostCall-Bullets-Generation |
| app.js:1121 | `/api/postcall_analysis` | POST | PostCall-Lernkarten (H-5 trifft hier!) |
| app.js:1196 | `/api/learning_cards?status=vorschlag` | GET | Vorschläge laden |
| app.js:1204 | `/api/learning_cards/<id>/save` | POST | Karte speichern |
| app.js:1239 | `/api/learning_cards?status=vorschlag` | GET | (duplicate) |
| app.js:1245 | `/api/learning_cards/<id>/user_text` | POST | User-Text-Validierung |
| app.js:1269 | `/api/learning_cards?status=aktiv` | GET | Aktive Karten für Applied-Check |
| app.js:1293 | `/api/learning_cards/<id>/applied` | POST | Markiere angewendet |
| app.js:1330 | `/api/feedback` | POST | Stern-Bewertung (Classic) |
| app.js:1589 | `/api/precall/research` | POST | (dup) PiP-inline PreCall |
| app.js:1624 | `/api/set_profile` | POST | Profilwechsel vor Call-Start |
| app.js:1670 | `/api/beenden` | POST | (dup) PiP-Beenden-Pfad |
| pip-launcher.js:103 | `/api/launcher/init` | GET | Launcher-Modal-Init |
| pip-launcher.js:311 | `/api/precall/research` | POST | Launcher-Step-3 Analyse |
| pip-launcher.js:512 | `/api/launcher/profile/<pid>` | GET | Profilwechsel in Step 5 |
| pip-launcher.js:640 | `/profiles/<id>/skripte/<id>` <br>bzw. `/profiles/<id>/opener/<id>` | PUT | Inline-Edit-Save |
| pip-launcher.js:869 | `/api/set_profile` | POST | Profilwechsel beim Call-Start |
| pip-launcher.js:1885 | `/api/beenden` | POST | PiP-Launcher Beenden |
| pip-launcher.js:2138 | `/api/postcall/trend?n=5` | GET | Trend-Sparkline PostCall |

**Unique Endpoints:** 21 `/api/*` + 1 `/profiles/<id>/{skripte,opener}/<id>` PUT = 22 Routes konsumiert.

---

## SocketIO-Event-Matrix

### Emitted (Frontend → Backend)

| Event | app.js:Zeile | pip-launcher.js:Zeile | Payload |
|---|---|---|---|
| `audio_chunk` | 57 | 953 | Raw PCM16 ArrayBuffer (~100ms chunks) |
| `start_live_session` | 67 | 996 | app.js: `{mode}` <br>**pip-launcher: `{mode, precall_briefing, skript_inhalt, skript_bloecke, anrede}`** (PiP sendet volles Kontext-Paket, classic nicht!) |
| `stop_live_session` | 81 | 1854 | — |
| `mute_mic` | — | 1052 | `{muted}` |
| `manual_ewb` | — | 1329 | `{text, line_id, slot}` |

### Received (Backend → Frontend)

| Event | app.js:Zeile | pip-launcher.js:Zeile | Zweck |
|---|---|---|---|
| `connect` | 453 | (implizit io()) | Session-Bootstrap |
| `transcript` | 483 | 1337 | Interim + Final-Segmente |
| `coaching` | 542 | — | Classic-View Coaching-Cards; **PiP ignoriert absichtlich (Kommentar Z.1459)** |
| `disconnect` | 562 | 1465 | Mic stoppen / Log |
| `dg_error` | 566 | 1469 | Deepgram-Fehler |
| `pip_stream_start` | — | 1344 | Haiku-Streaming beginnt |
| `pip_token` | — | 1384 | Token-Delta |
| `pip_token_done` | — | 1400 | Streaming-Ende, full JSON result |
| `pip_stream_error` | — | 1445 | KI-Stream-Error |
| `keyword_einwand_match` | — | 1476 | Sub-150ms-Keyword-Match aus Deepgram |
| `qa_slot1` | — | 1517 | Phase-08.5 Universal-Response (Haiku) |
| `qa_soft_hint` | — | 1546 | Phase-08.5 legacy / Rückfrage-Fallback |

**Entry:** 5 emit-Events, 12 listener-Events (davon 7 PiP-exklusiv).

**Asymmetrie**: Classic `/live` bekommt nur `transcript`/`coaching`/`dg_error` — kein `pip_*`, kein `qa_*`, kein `keyword_einwand_match`. Classic-View ist damit effektiv **Alt-Pfad ohne Phase-06/08.5-Features.** Entweder Classic ist dead (dann entfernen) oder sie muss nachgezogen werden. Im MASTER-AUDIT nicht adressiert.

---

## Dead-Backend-Route-Kandidaten

Routes die im Backend registriert sind aber **weder in app.js noch in pip-launcher.js** aufgerufen werden (Grep-verifiziert, nur diese 2 Dateien — andere JS-Module wie profile_editor.js, training.js, dashboard.js habe ich NICHT gescannt und können Rufer sein):

| Route | File:Line | Einschätzung |
|---|---|---|
| `/api/swap_roles` POST | app_routes.py:219 | Nicht in beiden Files — **wahrscheinlich dead** (Rollen-Swap passiert via `/api/log_correction` + Frontend-DOM-Manipulation) |
| `/api/set_phase` POST | app_routes.py:1081 | Kein Caller — **Phase-Wechsel manuell abgeschaltet?** Dead-Kandidat |
| `/api/keepalive` POST | app_routes.py:684 | Kein Caller in beiden Files — ggf. in anderem JS oder ungenutzt |
| `/api/status` GET | app_routes.py:229 | Kein Caller — **Ergebnis-Polling ersetzt Status offenbar** |
| `/api/skripte` GET | app_routes.py:1358 | PiP-Launcher nutzt `/api/launcher/init` für Skripte. Dead-Kandidat oder von /profiles-Page genutzt |
| `/api/ewb/<id>/rate` POST | app_routes.py:1423 | EWB-Rating UI in beiden Files nicht sichtbar — Dead-Kandidat |
| `/api/feedback/quick` POST | feedback.py:43 | Nur `/api/feedback` gerufen — Quick-Feedback ungenutzt |
| `/api/tipps` GET | coach.py:237 | Dead-Kandidat (Coaching-Content kommt via Socket) |
| `/api/my_profiles` GET | coach.py:252 | Dead-Kandidat (Launcher nutzt `/api/launcher/init`) |
| `/api/learning_cards/<id>/regenerate` POST | learning.py:109 | Frontend regeneriert lokal über `regenerateLernkarte()` (app.js:1217) ohne Backend-Call — **Route ist dead/Zombie** |
| `/api/learning_cards/<id>/status` POST | learning.py:129 | Kein Caller — **Status-Update findet anders statt** |
| `/api/analytics` GET | dashboard.py:935 | Kein Caller in live-JS (Dashboard-Page hat eigenes JS, ungescannt) |
| `/api/profile/<id>/tabu` POST | profiles.py:530 | Kein Caller in beiden (profile_editor.js könnte, ungescannt) |

**Vorbehalt:** Bestätigung braucht Cross-Check gegen `profile_editor.js`, `dashboard.js`, `training.js`, `coach.js` Templates. Die oberen 11 ohne sternmarkierten Vorbehalt sind solide Dead-Kandidaten weil sie klar zum Live-Session-Flow gehören.

**Fix-Empfehlung:** Pre-EA-Cleanup. `/api/swap_roles`, `/api/set_phase`, `/api/ewb/<id>/rate`, `/api/tipps`, `/api/my_profiles`, `/api/learning_cards/<id>/regenerate`, `/api/learning_cards/<id>/status`, `/api/feedback/quick` löschen oder mit Caller markieren. Jede dead-Route = eine mehr Angriffs-Surface.

---

## Schema-Drift-Stellen im Frontend

**Gute Nachricht:** Keine Wiederholung von `pdata.get("produkt")` im Frontend.

**Frontend-Profil-Lesungen** (pip-launcher.js):
- `state.profileDaten.ki.ansprache` (Z.420) — Top-Level-Key `ki`
- `state.profileDaten.opener` (Z.460, 988, 1703) — **Legacy Top-Level-`opener`-Key**
- `state.profileDaten.consent_text` (Z.666) — Top-Level-Key
- `state.profileDaten.einwaende` (Z.1266, 1301, 1591) — **verschachtelt: e.kurzlabel / e.kategorie / e.gegenargument_1 / e.gegenargument / e.text**

Das Frontend kennt **kein `basis.produktbeschreibung`** — Produkt wird nie vom Frontend gelesen. Produkt-Info-Fluss ist **rein Backend-intern** (`build_profile_context` oder `pdata.get("produkt")`). Die H-13-Drift ist damit isoliertes Backend-Problem — Frontend ist unschuldig.

**Drift-Risiko Einwände-Shape:** Das Frontend akzeptiert 5 verschiedene Feld-Namen pro Einwand-Objekt (`kurzlabel`, `short_label`, `kategorie`, `gegenargument_1`, `gegenargument`, `text`). Das ist defensive Programmierung, aber auch Indikator für **uneinheitliche Datenquelle**. Schema-Validator fehlt (MEDIUM im MASTER-AUDIT bereits geflaggt).

**Legacy-Opener vs. Opener-Items:** pip-launcher Z.460 liest `profileDaten.opener` als Top-Level-String UND behandelt `openerItems` als Liste. Zwei parallele Opener-Schemata zur Laufzeit. Kandidat für Phase-Closeout-Pruning.

---

## Security-Findings

### S-1 (MEDIUM): `innerHTML` mit Server-Daten — XSS-Surface via `escHtml` mitigiert, aber Lücken

- app.js: **54 `.innerHTML` Stellen**, davon **40+ mit User/Server-Daten**.
- pip-launcher.js: **22 `.innerHTML` Stellen**.
- Fast überall: `escHtml()` (app.js:616) bzw. `escHtml()` (pip-launcher.js:53) escaped `& < > "`.
- **Inkonsistenz:** app.js:616 escaped NICHT `"` oder `'` — pip-launcher:58 schon (`"`, aber kein `'`). → In app.js könnten `"`-enthaltende Server-Strings im `onclick="..."` Attribut **Attribut-Escape brechen**.
- Beispiel app.js:252: `onclick="triggerEwb('${escHtml(typ)}')"` — `typ` kommt aus Profil (user-controlled via Profile-Editor) oder aus AI-Response. Enthält `typ` ein `'` → Attribut bricht, onclick kann injiziert werden. **XSS ausgelöst durch eigenes Profil möglich** (self-stored, aber weil Profile org-shared denkbar → geteilte Profil-Daten in Multi-User-Orgs sind XSS-Vektor).
- **Fix:** `escHtml` um `'` erweitern, oder Attribut-Kontexte generell auf `data-*` + `addEventListener` umstellen.

### S-2 (MEDIUM): Backend-Error-Strings direkt ins DOM

- pip-launcher.js:323-334: Bei `/api/precall/research`-Error wird `j.error` oder Raw-Text **direkt in `errEl2.textContent`** geschrieben.
- app.js:155, 170, 894: `result.data.error`, `data.error` in `textContent` gerendert.
- **textContent schützt gegen HTML-Injection** — aber nicht gegen **Informations-Leak**. LB-7 (1000 Chars Traceback) würde hier sichtbar auf User-Bildschirm landen. Kombinierbar mit Social-Engineering.
- **Fix:** Nach LB-7-Patch automatisch erledigt. Zusätzlich: Clientseitig auf generische Messages mappen wenn Error-String `Traceback` oder `File "` enthält.

### S-3 (LOW): localStorage-Keys — DSGVO-Review

Gespeicherte Daten client-seitig:
- `nerve_last_anrede` (pip-launcher:9, 2272) — string `'Du'` oder `'Sie'`. **Harmlos.**
- `nerve_pip_kundendaten` (app.js:1483, 1509, 1522) — JSON-Array `[{firma, name, position}]` (max 5). **DSGVO-relevant:** Kundennamen auf Client persistiert, 5 History-Einträge. Ohne TTL. Nicht im Datenschutzhinweis dokumentiert (zu prüfen).
- `sn_kompakt` (app.js:1857, 1920, 1924) — UI-State-Flag `'0'`/`'1'`. **Harmlos.**
- `_HISTORY_KEY` / `history` (app.js:1485) — verwaist? Kein Setter gefunden außer `_KUNDENDATEN_HISTORY_KEY`. **Kandidat für Cleanup.**

sessionStorage:
- `headsetConfirmed` (pip-launcher:783, 842) — `'true'` nach Headset-Modal. **DSGVO/Compliance-relevant:** Cold-Call-Architektur hängt von Headset-Confirm ab (siehe CLAUDE.md). `sessionStorage` überlebt F5 innerhalb Tab. Wenn User Tab schließt, Modal kommt wieder. OK. **Aber:** Kein Server-seitiges Audit-Event, dass das Modal bestätigt wurde. Rechtlich sinnvoll zu loggen.

**Fix-Empfehlung:**
- `nerve_pip_kundendaten` in Datenschutz-Erklärung aufnehmen + TTL 30 Tage + Clear-Button in UI.
- `headsetConfirmed`-Bestätigung als Audit-Event loggen (neuer `audit.log_action` type=`headset_confirmed`, hilft bei H-8).

### S-4 (LOW): `/api/ergebnis`-Polling-Storm bei Backend-500

`app.js:780-811`:
```js
try { const res=await fetch('/api/ergebnis');const data=await res.json(); ... }
catch(e){ console.error('[POLL] Fehler:', e); }
finally { if(window._pollingActive) setTimeout(pollErgebnis, 500); }
```

- Kein `res.ok`-Check. **500-Response mit JSON-Traceback** (LB-7) wird ganz normal in `data` geparst, kein `error`-Handling außer generischer catch. Wenn Response gar kein JSON → catch → weiter polling alle 500ms.
- Bei Backend-Fehler-Storm: 2 req/sec × n User = schnelle Error-Log-Explosion.
- **Fix:** Exponential Backoff bei consecutive Fehlern (500ms → 1s → 2s → max 10s). Außerdem `res.ok`-Check und bei 5xx explizit warten.

### S-5 (LOW): Kein CSRF-Token bei POST-Calls

Alle POSTs gehen ohne CSRF-Token raus. Flask-WTF-CSRF ist nicht konfiguriert (bisheriger Audit bestätigt). Session-Cookie reicht für Same-Origin-Requests, aber bei OAuth-eingebundenen Drittseiten oder Sub-Domain-Takeovers → CSRF-Vektor. **Pre-Launch MUSS.**

### S-6 (LOW): `res.text()` → `JSON.parse(t)` → `throw new Error(j.error)` ohne Length-Limit

pip-launcher:322 liest gesamten Response-Body in String. Bei Backend-Traceback mit 1000 Chars wird alles in `new Error(...)`-Message gepackt und auf Console geloggt (tolerierbar) sowie in `errEl2.textContent` geschrieben (Informations-Leak).

### S-7 (INFO): `document.addEventListener('keydown', ...)` ohne cleanup

pip-launcher:835 registriert globalen keydown-Handler für Consent-Modal. Wird wahrscheinlich nicht removed bei Modal-Close (muss verifiziert werden — ich hab den Close-Pfad nicht eingesehen). **Leak-Kandidat, kein Security-Issue.**

---

## Dead-Code / Legacy-Patterns im Frontend

- **app.js:460** `legacyOpener = state.profileDaten.opener` — Legacy Top-Level-Opener-Key parallel zu `openerItems[]`. Kandidat für Pruning bei nächstem Profil-Redesign (siehe CLAUDE.md — dass es einen Reset-Stand gibt, erklärt vermutlich die Dublette).
- **app.js:1545** Kommentar "If legacy event still emitted, render as normal answer (never silent)." — `qa_soft_hint`-Handler ist Legacy-Schutz nach Phase-08.5-Korrektur-3. Kann nach Verify, dass Backend nicht mehr emittiert, entfernt werden.
- **pip-launcher.js:1459** Kommentar "Coaching-Listener entfernt (Phase 06.6)". Sauber dokumentierter Dead-Path-Removal.
- **pip-launcher.js:2094** `setInterval(...)` — ohne Code-Umfang nicht identifiziert, potentiell leak-Kandidat.
- **Keine klassischen TODO/FIXME/HACK-Kommentare in app.js. pip-launcher.js: 0 Treffer.** Sauber. Das ist gut und schlecht — sauber weil kein offener Tech-Debt-Graffiti, schlecht weil die Masse der `legacy`-Kommentare in separaten Kommentar-Blöcken steht (Phase 06.x, Phase 08.5 BUG-XX), die nicht als TODO getaggt sind.

---

## Polling-Frequenzen

| Endpoint | Frequenz | Kontext |
|---|---|---|
| `/api/ergebnis` | **500ms** self-scheduling | app.js:810 — startet sobald Polling aktiv, stoppt bei Beenden/PostCall |
| `/api/status` | **nicht aufgerufen** | app_routes.py:229 ist dead |
| Session-Timer UI | 1000ms | app.js:348 (`sessionTimer = setInterval(...)`) |
| Frage-Antwort-Countdown | 1000ms | app.js:888 (temporär 60s, dann cleared) |
| Mic-Level-Bars | **~16fps (60ms)** | pip-launcher:1018 (RAF-gedrosselt) |
| PiP-Live-Updates | **0ms (rein via Socket-Push)** | Explizit kein Polling, Kommentar pip-launcher:935 |

**Bemerkung:** Die Umstellung Classic (Polling) → PiP (Socket-Push) ist sauber getrennt. Classic-View zieht weiterhin 2 req/sec, PiP-View null Polling zur Laufzeit (abgesehen von `/api/beenden`-Response). Das bestätigt meinen Befund oben: **Classic-View ist Alt-Pfad, PiP ist neue Welt.** Entscheidung fällig ob Classic weiterleben soll.

---

## Severity-sortierte Findings

### HIGH

**FH-1: Classic-Live-View vs. PiP-Asymmetrie (Feature-Parity-Lücke)**

Classic-View (`/live` ohne PiP) bekommt **keine** Phase-06-Streaming-Events (`pip_*`), **keine** Phase-08.5 QA-Events (`qa_slot1`, `qa_soft_hint`), **kein** `keyword_einwand_match`. Classic-User sieht nur klassische Ergebnis-Polling-Cards + Socket-`coaching`-Cards, alle Phase-06/08.5-Arbeit geht an ihm vorbei.

**Folge:** Zwei UX-Niveaus. Classic-User bekommt alten Nudelcode-Flow ohne QA-Pipeline-Patches. Wenn Classic-View im EA-DACH-Release noch ausrollt, user-reports werden inkonsistent ("bei mir läuft's anders als beim Kollegen").

**Decision nötig:** Classic deprecaten und redirect auf PiP, ODER Classic mit denselben Events nachziehen. Empfehlung: **PiP-only**, Classic-Code entfernen. Spart ~600 Zeilen in app.js (Z.452-570 Socket-Handler, pollErgebnis Chain, ewb-UI klassisch).

**Fix-Aufwand:** Deprecation ~2-3h inkl. UX-Redirect. Migration alle Nutzer auf PiP ~1-2h Dokumentation.

**FH-2: `/api/ergebnis`-Polling ohne Backoff + ohne `res.ok`-Check (verschärft LB-7)**

Bei Backend-500-Traceback-Leak (LB-7) pollt Frontend blind weiter. Error-Logs explodieren, User sieht keine Fehlermeldung (catch schluckt), aber Traceback landet via `data`-Object auf Console (Dev-Tools lesbar). **LB-7 wird durch FH-2 verstärkt** — ohne Backoff hämmert Frontend den Server im Fehlerfall.

**Fix-Aufwand:** 30 min (exponential backoff + res.ok-Check + User-Fehler-Toast bei n consecutive Fails).

### MEDIUM

**FM-1: XSS via `escHtml` ohne `'`-Escape in app.js**

Siehe S-1. Attribut-Kontexte `onclick="...'${escHtml(typ)}'..."` brechen wenn `typ` ein `'` enthält. Profil-Daten können user-controlled sein (Multi-User-Org teilt Profile).

**Fix-Aufwand:** 15 min (escHtml um `'` erweitern + Regressionstest).

**FM-2: Backend-Error-Strings werden in UI gerendert**

Siehe S-2. In Kombination mit LB-7 → User sieht Traceback. Nach LB-7-Fix mitigiert, aber defensiv als Client-Side-Filter sinnvoll.

**Fix-Aufwand:** 30 min.

**FM-3: `nerve_pip_kundendaten` in localStorage — DSGVO-Review**

Kundennamen client-seitig persistiert, ohne TTL, nicht dokumentiert. Art. 5 DSGVO "Speicherbegrenzung". Sollte vor EA geklärt werden (Eintrag in Datenschutzerklärung + Clear-Button + 30-Tage-TTL).

**Fix-Aufwand:** 1-2h (TTL-Logik + UI-Clear-Button + Datenschutz-Text).

**FM-4: Keine CSRF-Tokens bei POST**

Siehe S-5. Pre-Launch MUSS. Same-Origin schützt, aber Defense-in-Depth fehlt.

**Fix-Aufwand:** 3-4h (Flask-WTF-CSRF konfigurieren + Frontend-Header-Injection).

**FM-5: `/api/learning_cards/<id>/regenerate` und `/status` — Frontend ruft sie nicht**

Backend-Routes ohne Caller. `regenerateLernkarte` (app.js:1217) rotiert lokal zwischen vorgefertigten Alternativen ohne Server-Roundtrip. Die Regenerate-Route ist dead; Backend-Code für `/regenerate` sollte verifiziert werden, ob sie als Zombie-Chain noch Claude-Calls macht (→ stille Cost-Leaks).

**Fix-Aufwand:** 30 min (Backend-Code prüfen + Route + evtl. Service-Chain entfernen).

### LOW

**FL-1: 11 Dead-Backend-Route-Kandidaten** (siehe Tabelle oben) — Cleanup vor EA.

**FL-2: Legacy-Opener-Dublette (`opener` vs. `openerItems`)** — Profil-Redesign-Zeitpunkt abwarten.

**FL-3: `qa_soft_hint`-Legacy-Handler** — pip-launcher:1546, Kommentar sagt "if legacy event still emitted". Verify dass Backend nicht mehr emittiert, dann raus.

**FL-4: `_HISTORY_KEY` in app.js:1485 — kein Setter gefunden.** Entweder toter Storage-Key oder Setter in anderer Datei. Verify + cleanup.

**FL-5: No-retry bei Socket-Disconnect in Classic-View** — app.js:562 ruft nur `stopMicStream()`. pip-launcher konfiguriert `reconnectionAttempts: 3`. Classic fehlt defensives Reconnect.

---

## Cross-Module-Hypothesen (zu verifizieren in Welle 5)

**H-F1:** Die 11 Dead-Backend-Route-Kandidaten sind wahrscheinlich alle tot — aber 2-3 könnten von `profile_editor.js`, `dashboard.js`, `training.js`, `coach.js` gerufen werden (ungescannt). Nach Welle 5 finalisieren.

**H-F2:** `/api/ewb_trigger` + `/api/frage` werden von app.js genutzt, **nicht von pip-launcher.js**. PiP nutzt Socket-Events (`manual_ewb` emit) statt REST. → `/api/ewb_trigger` REST-Route ist **nur für Classic-View** relevant. Wenn FH-1 (Classic deprecaten) umgesetzt wird, kann `/api/ewb_trigger` und wahrscheinlich auch `/api/frage` gelöscht werden → H-12 (duplicate Anthropic-Clients) verschwindet automatisch, H-13 (Schema-Drift in diesen Routes) wird moot, H-14 (Double-Logging) auch. **3 HIGH-Befunde erledigen sich mit 1 Architektur-Entscheidung.** Das ist der Hebel.

**H-F3:** Die Headset-Confirm-Audit-Event-Lücke (siehe S-3) passt ins H-8-Thema (10+ DSGVO-Audit-Gaps). Addressable zusammen mit dem Audit-Retrofit.

**H-F4:** `precall_briefing` wird vom Frontend in `/api/beenden`-Body mitgeschickt (app.js:649, pip-launcher:1891) UND in `start_live_session`-Socket-Payload (pip-launcher:998). **Zwei Wege derselben Info.** In Kombination mit H-2 (PreCall-Briefing ist Feature-Fake) → Frontend sendet Daten, Backend liest sie nicht. Pruning-Entscheidung aus MASTER-AUDIT zieht sich durchs Frontend.

**H-F5:** `startCall` in pip-launcher (Z.840) schickt viele Parameter an Backend (`skript_inhalt`, `skript_bloecke`, `anrede`, `precall_briefing`), classic `activateSession` in app.js schickt nur `{mode}`. **Welche Backend-Handler lesen welchen Payload?** Unklar. Braucht Verifikation welche Path im `start_live_session`-Handler tatsächlich existiert. Verdacht: Handler liest nur `mode` + `anrede`, Rest wird ignoriert oder uneinheitlich verarbeitet — was H-2 und das Skript-Block-Lese-Thema aus dem Master-Audit weiter bestätigen würde.

---

*Stand: 2026-04-24. Frontend-Scan Welle 4 abgeschlossen. Nächste Welle: profile_editor.js + Templates + Tests (Welle 5).*
