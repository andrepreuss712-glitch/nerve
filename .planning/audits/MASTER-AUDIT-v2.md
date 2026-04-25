---
audit: MASTER-AUDIT-v2
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault) — Konsolidierung aus 11 Deep-Dive-Audits
basiert_auf:
  - .planning/audits/MASTER-AUDIT.md (v1, Welle 1+2 + Claudian-Stichproben)
  - Welle 3-5 (parallele Agenten, 2026-04-24 ab 19:20):
    - .planning/audits/deep-dive-app-routes-rest.md
    - .planning/audits/deep-dive-auth-oauth-settings.md
    - .planning/audits/deep-dive-profiles.md
    - .planning/audits/deep-dive-training-learning-coach.md
    - .planning/audits/deep-dive-dashboards-admin.md
    - .planning/audits/deep-dive-business-small-routes.md
    - .planning/audits/deep-dive-frontend-core.md
    - .planning/audits/deep-dive-frontend-templates.md
    - .planning/audits/deep-dive-tests.md
  - Salesnerve-Stand: 2026-04-24, Commit 6464ec9
scope_coverage:
  - Services: 20/20 (100%)
  - Routes: 22/22 (100%)
  - Frontend JS: 4/4 vollständig + app.js/pip-launcher Punktscans
  - Templates: 27/27
  - Tests: 36/36
  - DB-Schema: models.py gelesen
  - Config + app.py: gelesen
ersetzt: MASTER-AUDIT.md (v1)
---

# MASTER-AUDIT v2 — NERVE Codebase Full-Stack-Sweep

**Stand:** 2026-04-24, nach 4 Wellen + Claudian-Stichproben
**Dateien analysiert:** ~95 (services, routes, frontend, templates, tests, db, config)
**Findings konsolidiert:** 13 Launch-Blocker, 31 HIGH, 45+ MEDIUM, 20+ LOW

---

> **⚠️ Disclaimer 2026-04-25 — Stundenangaben veraltet:**
>
> Alle Aufwandsschätzungen in diesem Dokument (z.B. "~4-6h", "~12-15h", "~100-120h") wurden vor dem ersten realen Block-Durchlauf erstellt und sind systematisch um Faktor 5-10 zu hoch. Beweise: Block A geschätzt 30 Min ≈ tatsächlich 30 Min ✓, Block H geschätzt 4h → tatsächlich 25 Min. Gemeinsame Diagnose: Schätzungen rechnen in "Mensch programmiert manuell + Buffer"-Stunden, GSD ist bei mechanischen Tasks 5-10× schneller.
>
> **Maßgeblich sind die Komplexitäts-Marker** (🟢 trivial / 🟡 mittel / 🔴 komplex), nicht die Stundenzahlen. Stundenangaben werden NICHT mehr aktualisiert — Datei bleibt als historisches Audit-Dokument. Live-Stand: [[01 Roadmap]] im Vault.
>
> Regel ab 2026-04-25 (CLAUDE.md): Keine Stundenangaben mehr in Plänen, Audits, Roadmaps, Logs.

---

## EXECUTIVE SUMMARY — Update gegenüber v1

v1-Befund bestätigt und verschärft: NERVE ist in **deutlich schlechterem Zustand** als die Doku suggeriert. Die vier neuen Welle-3/4/5-Audits haben:

- **5 weitere Launch-Blocker** (von 8 → 13)
- **16 weitere HIGH-Severity-Funde**
- **Den Hebel "Classic-View deprecaten"** identifiziert — eine Architekturentscheidung löscht 3 HIGH-Funde auf einmal
- **Systematische Test-False-Greens** nachgewiesen — ~20% der Tests sind Source-Presence-Matches die Launch-Blocker **aktiv decken**. Der H-3/H-4-Prune scheitert an Test-Schutzwall.
- **Onboarding als Schema-Drift-Zentrum** entlarvt — erste 50 EA-User starten mit de-facto leeren Profilen weil Onboarding-Templates das Top-Level-Schema (`produkt`) schreiben das die Live-KI nicht liest
- **Classic-Live-View als zweiten UX-Track** bestätigt — ohne Phase-06/08.5-Features, Feature-Parität gebrochen

**Kernbefund-Verschärfung:** Die Phase-Closeout-Doku-Lüge (v1) setzt sich in der Test-Suite fort. Tests wurden als RED-Gates geschrieben und nie auf Integration weiterentwickelt. Phase-Closeout-Checkliste fehlt der Gate **"Test prüft Live-Path"**.

---

## 🔴 LAUNCH-BLOCKER — Konsolidierte Nummerierung (LB-1 bis LB-13)

> **Hinweis zur Nummerierung:** Welle-3-Agenten haben unabhängig LB-9/10/11 vergeben, die hier als LB-9 bis LB-13 eingeordnet sind. Der Profile-Audit seine LB-14/15 (Concurrent-Write + Schema-Validator) sind auf HIGH heruntergestuft — siehe Begründung unten.

### LB-1: Password-Reset komplett fehlt *(aus v1)*
- **Evidence:** `routes/auth.py` keine Reset-Route, `email_service.send_password_reset` ist Zombie, 0 Caller.
- **Fix:** ~3-4h Route + Template + Verdrahtung + Audit-Event.

### LB-2: DSGVO-Rechte-Routen fehlen komplett *(aus v1)*
- **Evidence:** `routes/legal.py` = 15 Z. Static-HTML. Keine `/dsgvo/*`-Route. `settings.delete_account` nur Soft-Flag (H-AU-4).
- **Fix:** ~8-12h für Data-Export, Account-Delete mit Kaskaden, Consent-Withdraw, Portability.

### LB-3: Tabu-System im QA-Pfad wirkungslos *(aus v1)*
- **Evidence:** `claude_service.py:1488-1490` + `:1528-1530` ruft `generate_qa_response(..., {}, '', ...)` mit leerem profile_data + confidence ''.
- **Folge:** QA-Pfad-Tabu-Block leer, Phase-08.5-Arbeit im QA-Pfad nie live.
- **Fix:** ~1h.

### LB-4: Cost-Tracking schreibt stale/falsche user_id *(aus v1)*
- **Evidence:** 21/27 `log_api_cost`-Calls ohne explizite user_id → Multi-User-Concurrency ordnet falsch zu.
- **Fix:** ~2-3h.

### LB-5: `ls.state['org_id']` Ghost — alle ApiCostLog NULL *(aus v1)*
- **Evidence:** Reader in cost_tracker, 0 Writer.
- **Fix:** 5 min — 1 Zeile in `deepgram_service.py:351`.

### LB-6: `ls.state['mode']` Ghost Read *(aus v1)*
- **Evidence:** 3× in claude_service gelesen, nie geschrieben.
- **Fix:** 5 min (gleiche Zeile wie LB-5).

### LB-7: Error-Handler leakt Traceback *(aus v1, verstärkt durch Frontend-Audit)*
- **Evidence:** `app.py:1697-1726` + 5 weitere in `routes/training.py` + `app_routes.py:1160/1272` + `admin_views.py:214`. Frontend (pip-launcher.js:323) rendert Error-Strings ins DOM → **Traceback sichtbar für User** (FM-2 aus Welle 4).
- **Fix:** 30 min zentral + 30 min Frontend-Filter.

### LB-8: Multi-Worker-Kostenexplosion-Risiko *(aus v1)*
- **Evidence:** `app.py:1776-1777` startet analyse_loop + coaching_loop unconditional.
- **Welle-3-Verstärkung (M-NEW-4):** Training-Service `_sessions`-Dict ist worker-lokal → Multi-Worker verliert User-State.
- **Fix:** ~2-3h Worker-Guard oder dedizierter Background-Worker.

### LB-9: CSRF-Protection fehlt auf allen POST-Routen *(NEU, Welle 3 Auth)*
- **Evidence:** Grep `csrf|CSRF` in salesnerve-Code = 0 Treffer. Keine `CSRFProtect(app)`, keine Flask-WTF. Betrifft /api/login, /api/register, 10× /settings/*, OAuth-Callbacks, Stripe-Checkout-Triggers.
- **Angriffe:** Abo kündigen, Account löschen, Billing-Adresse umstellen via CSRF-Link.
- **Folge:** B2B-DSGVO-USP-Bruch, Abmahn-Vorlage.
- **Fix:** 3-4h (CSRFProtect + Frontend-Token-Header + Webhook-Exempts).

### LB-10: Session-Cookie-Hardening fehlt komplett *(NEU, Welle 3 Auth)*
- **Evidence:** `app.py:26-29` setzt SECRET_KEY + SESSION_PERMANENT=True, aber KEIN `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE`, KEIN `PERMANENT_SESSION_LIFETIME`. Default = 31 Tage, JS-lesbar, cross-site.
- **Wechselwirkung mit LB-9:** Ohne SameSite funktioniert CSRF trivial.
- **Fix:** 15 min (5 Zeilen in app.py).

### LB-11: Neue User bekommen kein Startprofil *(NEU, Welle 3 Profiles)*
- **Evidence:** `auth.py::api_register` erstellt User ohne Profile. `_seed_demo_profiles` läuft nur für Org "NERVE Alpha" beim App-Start. Onboarding-Redirect explizit auskommentiert.
- **Folge:** EA-User landet im Dashboard → kein aktives Profil → `build_profile_context` leer → alle KI-Antworten generisch. Multipliziert LB-3 und LB-15/H-32.
- **Fix:** 1-2h (Wizard-Redirect-Aktivierung + optional Auto-Seed Demo-Profil).

### LB-12: Flask-Admin Sessions-View crasht auf Ghost-Columns *(NEU, Welle 3 Admin)*
- **Evidence:** `admin_views.py:96-97` referenziert `einwaende_total` + `einwaende_ok`. Echte Column-Namen sind `einwaende_gesamt` + `einwaende_behandelt`. Gleicher Fehler in `analytics.html:24-25` → User-Analytics-Seite zeigt immer 0.
- **Folge:** AttributeError beim Öffnen `/admin/convlog/` — in Kombination mit LB-7 **leakt das den Traceback öffentlich sichtbar**.
- **Fix:** 2 min (1 Admin-View + 1 Template-Fix).

### LB-13: Dashboard-ROI hart-codiert auf Fantasie-Branche *(NEU, Welle 3 Dashboard)*
- **Evidence:** `dashboard.py:367-368`: `branche = 'Sonstiges'; avg_deal = DEAL_VALUES.get(branche, 4000)`. DEAL_VALUES-Dict (9 Branchen) ist Dead-Code. Jeder User sieht denselben ROI aus 4000 EUR-Annahme.
- **Folge:** ROI-Card ist die Metrik mit der NERVE Wert beweist. Konstante Fantasie-Zahl = Vertrauensbruch sobald ein EA-Kunde merkt "die Zahl ist immer gleich". Marketing-USP-Bruch.
- **Fix:** 10 min (Card verstecken) oder 1-2h (Branche aus org lesen).

---

## 🟠 HIGH-Severity — Konsolidiert (H-1 bis H-31)

### Aus v1 (Services + Routes-Stichproben)

- **H-1:** `services/finetune_logging.py` existiert nicht — FT-Training-Material wird silent nicht persistiert. Tests decken das als False-Green.
- **H-2:** PreCall-Briefing Feature-Fake. Bestätigt durch Welle-3-Dashboard-Audit + Welle-4-Frontend+Template-Audit: Frontend sendet → Backend speichert → session_detail.html zeigt an → **aber kein Live-LLM-Pfad liest.** Drei-Schichten-Illusion.
- **H-3:** `analysiere_mit_claude_streaming` (102 Z.) dead. Wird durch test_claude_service_phase08.py:50-59 aktiv geschützt (False-Green).
- **H-4:** `_build_system_prompt` + `_get_erfolgsquoten` (195 Z.) dead/zombie. Wird durch test_claude_service_phase08.py:82-87 vor Prune geschützt.
- **H-5:** Training-PostCall-Analyse füttert Sonnet mit hardcoded `redeanteil_berater=60/40`. Verschärft durch Welle-3-Finding M-NEW-7: `/api/training/postcall-analysis` hat **0 Frontend-Caller** → Route ist möglicherweise komplett Dead-Feature.
- **H-6:** `generate_postcall_analysis` profile_data-Parameter dead.
- **H-7:** `kw_fired_for_line` D-02 Guard Race-Condition.
- **H-8:** 10+ DSGVO-Audit-Coverage-Gaps. Welle-3 liefert konkrete Stellen: `auth.api_register`, OAuth-Neuanlage-Branch, alle settings.py-Routes, alle Profile-CRUD außer update, alle Org-Mgmt-Routes, Feedback-Route, Changelog-Admin.
- **H-9:** Deepgram-Overcharge (Socket-Lifetime statt STT-Sekunden).
- **H-10:** `_parse_json` Silent-Failure im Hot-Path.
- **H-11:** ANALYSE_INTERVALL Drift + tote if/else-Branch.

### Aus v1 Claudian-Stichproben

- **H-12:** Inline-Anthropic-Clients ohne Cost-Tracking — **Count korrigiert auf 5** (statt 2): `/api/frage`, `/api/ewb_trigger`, `/api/postcall_insights` (Welle 3), Dashboard `_generate_weekly_summary` (Welle 3), routes/training.py:966 Personality-Generate (Welle 3).
- **H-13:** Profil-Feld-Lese-Drift `pdata.get("produkt")` in `/api/frage` + `/api/ewb_trigger`. Welle-4-Bestätigung: Frontend liest korrekt `basis.produktbeschreibung` → **Schema-Drift ist rein server-seitig**. Frontend kann nicht kompensieren.
- **H-14:** Duplicate-Logging `record_ewb_click` + `FtObjectionEvent` für dasselbe EWB-Event.
- **H-15:** Error-Response-Leaks in API-Routes (`jsonify({'error': str(e)})`).

### NEU aus Welle 3 Auth/OAuth

- **H-16: Register-Audit-Event fehlt in 3 Pfaden** (Email + Invitation + OAuth-Neuanlage).
- **H-17: Session-Fixation nur OAuth-Pfad geschützt.** Email-`_login_user` macht kein session.clear.
- **H-18: Microsoft-OAuth Email-Hijacking-Risiko.** Kein `email_verified`-Check (Google hat es). Feindlicher Azure-Tenant kann via `preferred_username=opfer@bigcorp.de` Account-Takeover.
- **H-19: `settings.delete_account` ≠ DSGVO Art. 17.** Soft-Delete per `aktiv=False`. Conversation-Logs, Profile, Stripe-Daten bleiben → DSGVO-USP-Lüge. **Zusammen mit LB-2 zu bündeln.**
- **H-20: Brute-Force-Schutz fehlt** auf `/api/login`. Kein flask-limiter, keine CAPTCHA, keine failed_login-Audit-Events.
- **H-21: `oauth_id` ohne UNIQUE-Constraint.** Doppel-User möglich.

### NEU aus Welle 3 Routes (app_routes Rest + profiles + training/learning/coach + admin + business-small)

- **H-22: `api_postcall_insights` Silent-Swallow + Prompt-Injection-Vektor.** `{'ok': True, 'bullets': [...]}` bei jeder Exception + f-String mit unvalidiertem einwaende/painpoints-Input.
- **H-23: `api_beenden` TOCTOU auf `ewb_clicks`.** Zwischen Z.406 und Z.564 liegen 160 Zeilen mit Lock-Release → `einwaende_gesamt` und `buttons_pressed` aus unterschiedlichen Snapshots.
- **H-24: `api_set_phase` keine Validation.** Negative/OOR-Integers korrumpieren `covered_phases` → FT-Trainingsdaten verschmutzt.
- **H-25: Rollen-Drift Profiles-API.** FAQ/Tabu-CRUD + `wizard_create` + `aktivieren` haben KEINEN `_rolle()`-Check. Member kann Tabu-Listen ändern ohne Owner-Freigabe.
- **H-26: Profile-CRUD Audit-Coverage extrem dünn.** Nur `profile_update` geloggt (ohne Feld-Diff). Create/Delete/Activate/Tabu/FAQ/Skript/Opener-Writes haben 0 Audit-Events. `consent_text` (DSGVO-relevant) ohne Änderungshistorie.
- **H-27: Coach-Live-Tipp-Feature komplett tot.** `/coach/live_tipp` + `/coach/api/tipps` haben 0 Frontend-Caller. Memory-Leak in `ls.coach_tipps`-Queue.
- **H-28: `/api/training/personalities/save` tot** seit Phase-07.2 Wave 3. Backend-Route blieb, Frontend-Caller weg.
- **H-29: Weekly-Summary-Claude + Dashboard-Claude ohne Cost-Tracking.** Bestätigt durch Welle 3 Admin-Audit.
- **H-30: KPI-Dashboard zählt falsche Feedback-Tabelle.** `Feedback` statt `FeedbackEvent`. Immer 0/0.
- **H-31: Onboarding schreibt Profil-Schema-Drift direkt rein** (HSR-2). `BRANCHE_TEMPLATES` erzeugt Top-Level `produkt`/`einwaende`/`phasen` statt `basis.*`. **Jeder neu-onboardete EA-User startet mit für Live-KI unlesbarem Profil.** Root-Cause-Bestätigung zu H-13.

### NEU aus Welle 3 Business-Small

- **H-32: `BillingEvent.org_id=1`-Fallback** im Stripe-Webhook bei ungelöster Org-Zuordnung → falsche Kunden-Metriken im Founder-Dashboard.
- **H-33: Waitlist-Invite schickt keine E-Mail.** Admin muss Link manuell kopieren.

### NEU aus Welle 4 Frontend

- **H-34: Classic-Live-View vs. PiP-Asymmetrie.** Classic (`/live` ohne PiP) bekommt keine `pip_*`/`qa_slot1`/`qa_soft_hint`/`keyword_einwand_match`-Events. **Classic-User sieht Legacy-UX ohne Phase-06/08.5-Arbeit.** Strategische Entscheidung nötig.
- **H-35: `/api/ergebnis`-Polling ohne Backoff + ohne `res.ok`-Check.** Verschärft LB-7 — 2 req/sec in Error-Storm.
- **H-36: `ewb_top2`-Legacy-Reader aktiv in app.js:798-799.** Wenn Writer existiert → zwei parallele EWB-Render-Pfade. Wenn nicht → Dead-Branch im Hot-Path. **Writer-Verifikation steht aus.**
- **H-37: `conv.precall_briefing` in session_detail.html gerendert.** Dritte Schicht der PreCall-Feature-Fake-Illusion (siehe H-2).

### NEU aus Welle 3 Profiles (heruntergestuft von LB)

- **H-38: Profile Concurrent-Write ohne Optimistic Lock.** Solo-Founder-Szenario minimiert Wahrscheinlichkeit → HIGH statt LB. `set_active_profile` setzt prozess-globalen State nicht pro Org.
- **H-39: Profile.daten ohne Schema-Validator.** Silent-Fallback zu `{}` bei Parse-Fehler. Wizard + Editor + Onboarding nutzen **drei verschiedene Schemas**.

---

## 🟡 MEDIUM-Severity (zusammengefasst, ~45 Funde)

**Schema + Consistency:**
- Wizard vs. Editor vs. Onboarding: 3 Profile-Schemas (H-39-Root-Cause)
- `TABU_DEFAULT_PAIRS` doppelt (Python + JS, 13 Paare manuell synchronisiert)
- `Feedback` vs. `FeedbackEvent` — zwei Tabellen, zwei Services, inkonsistent benutzt
- `Organisation.plan` Kommentar-Drift vs. config.py PLANS
- PLANS identisch konfiguriert — Starter/Pro/Business alle `max_users:1, minuten_limit:1000, training_voice_limit:50` (Bug?)
- `PromptVersion.is_default` Dead-Column (Phase-08-D-26 nie umgesetzt)
- `ConversationLog.precall_briefing` Column ohne Live-Reader

**Silent Failures / Error Handling:**
- `_parse_json` silent (H-10)
- `api_postcall_insights` silent-swallow (H-22)
- 7+ silent-swallows in `api_beenden`
- `weekly_summary` Cache-Read/Write silent (H-29)
- Welcome-Email-Fail silent × 2 (Email + OAuth)
- `exchange_rates.get_current_rate` leakt auf Live-DB (2 Tests failen seit Phase 04.7.2)
- Payments `_record_revenue` silent bei Revenue-Log-Fails

**Validation/Security-Medium:**
- Settings-Org-Scoping ohne Defense-in-Depth-Assertion
- USt-ID ohne Regex/VIES-Check
- `update_profile` keine String-Length-Caps
- Skripte/Opener ohne Length-Cap (`Text`-Column unbounded)
- `escHtml` in app.js escaped kein `'` → Attribut-Break in `onclick`
- `nerve_pip_kundendaten` localStorage ohne TTL / DSGVO-Doku
- `_is_known_oauth_tenant` Timing-Side-Channel für User-Enumeration
- Changelog String-Compare `'0.9.0' > '0.10.0'` = True (Bug)

**Payments/Billing:**
- `automatic_tax=True` ohne try/except (Tax-Registration fehlt → LB-7-Leak)
- Checkout-Success Race gegen Webhook-Delay
- `stripe.Customer.retrieve` synchron im Webhook (Timeout-Risiko)
- `cancel_subscription` ohne Cron-Enforcement

**Concurrency + Performance:**
- `_letzte_gemeldete_version`-Dict ohne LRU
- `_sessions`-Dict worker-lokal (Training)
- `_calc_call_score` Server-JS-Formel-Duplikat
- Dashboard-Streak-Write als Side-Effect bei jedem Open
- `get_recent_logs` Filesystem-I/O pro Dashboard-Load

**Orphan-Routes/Routes-Hygiene:**
- `/api/swap_roles`, `/api/status`, `/api/keepalive` — keine Frontend-Caller
- `/api/skripte` — Duplikat zu `/api/launcher/*`
- `/api/learning_cards/<id>/regenerate` + `/status` — keine Frontend-Caller (Regenerate rotiert clientseitig)
- `/api/ewb/<id>/rate` — evtl. tot (templates/session_detail.html ruft es, aber UI prüfen)
- `/coach/api/my_profiles` — Duplikat zu `/api/launcher/init`
- `/api/feedback/quick` — nur `/api/feedback` gerufen
- `/training/ping` — dev-only, redundant bei Auto-Deploy

**Cost-Tracking-Extras:**
- FX-Fallback 0.92 hardcoded + stale (EZB ~0.89)
- FX-Logik dupliziert in `cost_tracker._get_current_fx_rate`
- Training-Service 5 Claude-Calls unsichtbar
- `/training/transcribe` nutzt nicht globalen DeepgramClient

**Frontend-Legacy:**
- `opener` vs. `openerItems` Doppel-Schema
- `qa_soft_hint`-Legacy-Handler
- `_HISTORY_KEY` orphan storage key

**Templates:**
- `login.html` orphan
- `admin/feedback_notification.html` orphan
- `_tooltip.html` Include-Status unklar

**DSGVO/Audit-Medium:**
- Kein Audit-Log-Retention + Immutable-Trigger-Konflikt
- `audit.log_action` für feedback fehlt in /api/feedback
- `headset_confirmed`-Audit-Event fehlt

---

## 🟢 LOW / Kosmetik (zusammengefasst)

- 3× Import `time` in deepgram_service
- STT-Cost-Hook hardcoded `user_id=None`
- 12 Stellen hardcoded Claude-Model-String (`claude_service.py` 9× + `app_routes.py` 3× + `training_service.py` 5× + `routes/training.py` 1× + `dashboard.py` 1× = **17 Gesamtstellen**)
- `_CODE_VERSION = '45b02eb'` hardcoded in training.py
- 10 Sprachen in Settings aber nur DE-Content
- Theme-Fallback silent-overwrite
- Logout akzeptiert GET-Requests
- `integration_engine` mischt `datetime.now()` und `utcnow()`
- Orphan-Import `BillingEvent` in organisations.py
- `redirect, url_for` unused in settings.py

---

## 📚 Doku-Lügen gegen Code verifiziert — Update v1

| Quelle | Behauptung | Realität |
|---|---|---|
| ARCHITECTURE.md Z.186 | PreCall injected via build_profile_context | **Falsch** (H-2, F-7, F-9) |
| CONCERNS.md | ANALYSE_INTERVALL = 2s | Code = 4s |
| STRUCTURE.md Z.31 | crm_service HubSpot-Stubs | Reine Claude-Generierung |
| STRUCTURE.md Z.35 | login_required in auth_decorators | Sitzt in auth.py |
| Phase-04.7-05-Summary | Password-Reset verdrahtet | **Lüge** |
| Phase 04.13 + Quick-260414-kf8 | PreCall Live-Feature | **Feature-Fake, 3 Schichten** |
| Phase-07.2-03-SUMMARY | Personality-Save Route verifiziert | **Frontend-Caller entfernt, Backend-Prune vergessen** |
| **NEU:** Phase-04.9 VERIFICATION | Personality-Routes VERIFIED | Ohne Frontend-Integration-Check |
| **NEU:** app_routes.py Z.145 Kommentar | "ewb_top2 legacy may be None post-04.8" | Frontend konsumiert aktiv → Kommentar oder Code lügt |
| **NEU:** `oauth.py` Session-Fixation-Kommentar | "Session-Keys löschen" | Nur OAuth-Pfad, Email-Pfad nicht (H-17) |
| **NEU:** Handoff: "Password-Reset + DSGVO-Routen bekannt" | — | 0 Tests für beide LBs (Welle 5) |

---

## 🎯 MUSTER-ANALYSE: Fixes die mehrere Findings gleichzeitig lösen

Die konsolidierte Analyse offenbart 7 Hebel bei denen **eine Entscheidung oder ein Fix mehrere Findings eliminiert**:

### Hebel 1: Classic-View deprecaten (H-34 Entscheidung)

**Löst automatisch:**
- H-12 Teil 1 (`/api/frage` + `/api/ewb_trigger` inline-Anthropic) — PiP nutzt Socket, braucht REST nicht
- H-13 (Schema-Drift `pdata.get("produkt")`) — die 2 betroffenen Routes verschwinden
- H-14 (Duplicate EWB-Logging) — nur Classic nutzt beide Wege
- H-15-Teil (Error-Response-Leaks in diesen Routes)
- H-35 (`/api/ergebnis`-Polling ohne Backoff) — nur Classic polled
- F-8/H-36 (`ewb_top2`-Legacy-Reader) — nur Classic rendert ihn

**Einsparung:** ~600 Zeilen in app.js + 3 HIGH-Routes im Backend weg
**Aufwand:** 3-5h inkl. Nutzer-Migration-Doc
**Entscheidung:** André. Empfehlung: **PiP-only**. Classic war Phase-04-Ära, PiP ist neue Welt.

### Hebel 2: State-Writer-Fix in deepgram_service.py:351 (1 Zeile)

**Löst:**
- LB-5 (`ls.state['org_id']` Ghost)
- LB-6 (`ls.state['mode']` Ghost)

**Aufwand:** 5 min. Einmalig einbauen, alle Downstream-Pfade erholen sich sofort.

### Hebel 3: CSRF + Session-Flags-Paket

**Löst zusammen:**
- LB-9 (CSRF)
- LB-10 (Session-Cookie-Hardening)
- Hälfte von H-20 (Brute-Force — CSRF allein nicht, aber Credential-Stuffing schwieriger)
- FM-4 (Frontend CSRF-Tokens)

**Aufwand:** 3-4h + 15 min.
**Warum Paket:** Beide gleichen Root-Cause "Security-Baseline nie gesetzt".

### Hebel 4: Schema-Ghost-Columns (einwaende_total/_ok)

**Löst:**
- LB-12 (Flask-Admin-View-Crash)
- H-Template-Bug (analytics.html zeigt 0 Einwände)

**Aufwand:** 2 min (Rename in 2 Stellen).
**Blast-Radius:** LB-12 ist Trigger für LB-7-Leak (Traceback sichtbar) → doppelte Entschärfung.

### Hebel 5: DSGVO-Paket (Password-Reset + Routen + Audit-Events)

**Löst als Bündel:**
- LB-1 (Password-Reset)
- LB-2 (DSGVO-Routen)
- H-8 (DSGVO-Audit-Coverage — register/password_reset/data_export/account_delete als Events)
- H-16 (Register-Audit-Event — Teil von H-8)
- H-19 (delete_account DSGVO-konform — Teil von LB-2)
- H-26 Teil (consent_text-Audit — Teil von H-8)
- MSR-2 (Org-Management-Audit-Events — Teil von H-8)

**Aufwand:** ~16-20h (eine strukturierte Phase 04.x-DSGVO-Launch).
**Warum Paket:** Audit-Events wollen konsistenten Dispatcher, getrennte Einzelfixes erzeugen Drift.

### Hebel 6: Inline-Anthropic-Konsolidierung

**Löst:**
- H-12 (alle 5 inline-Anthropic-Clients + Cost-Tracking)
- H-29 (Weekly-Summary + Dashboard-Claude + Personality-Gen ohne Hook)
- LOW hardcoded-Model in 17 Stellen (CH-01 + M-NEW-6)
- Teil H-22 (postcall_insights Cost-Hook)

**Aufwand:** ~2-3h (geteilter `claude_service.claude_client` + `config.MODEL_HAIKU/SONNET` Konstanten + `log_api_cost` überall).
**Zusatzgewinn:** Model-Update "Haiku 4.5 → 4.6" ist dann 2 Zeilen statt 17 Edits.

### Hebel 7: Test-False-Greens entfernen VOR Dead-Code-Prune

**Löst Prune-Blockade für:**
- H-3 (`analysiere_mit_claude_streaming` → test_claude_service_phase08.py:50-59 schützt)
- H-4 (`_build_system_prompt` → test_claude_service_phase08.py:82-87 schützt)

**Aufwand:** 4h — 24 Tests löschen/umschreiben (test_claude_service_phase08.py, test_08_5_05_training_pipeline_t2.py teilweise, test_phase_08_migration.py, test_qa_pipeline_t1.py).
**Warum zuerst:** Jede Prune-Phase scheitert an grüner Test-Suite die Dead-Code aktiv schützt.

---

## 🔧 PRIORISIERTER FIX-PLAN IN BLÖCKEN

> **Prinzip:** Blöcke statt Einzel-Bugs. Jeder Block hat thematische Kohärenz, gemeinsame Test-Anforderungen und ein klares "done"-Kriterium. Reihenfolge respektiert Abhängigkeiten (Test-Cleanup vor Prune, CSRF vor DSGVO-Routes mit State-changing-POSTs).

### ✅ BLOCK A — Quick-Win-Fixes (ABGESCHLOSSEN 2026-04-24, GSD-Phase 08.6)

**Status:** Komplett, 12 Commits gepusht. Dauer Plan+Execute+Review-Fix: ~30 Min wie geschätzt.

1. ✅ LB-5 + LB-6: `ls.state['org_id']` + `ls.state['mode']` in `deepgram_service.py` geschrieben
2. ✅ LB-12: Column-Rename in `admin_views.py` + `analytics.html` (keine DB-Migration nötig — Columns waren in models.py bereits korrekt benannt, nur Code-Referenzen falsch)
3. ✅ LB-13: ROI-Card im Dashboard versteckt (Backend-Dead-Code mit Deaktivierungs-Kommentar stehen geblieben für späteren Branche-Fix)
4. ✅ CORS_ORIGIN: `nerve.app` → `getnerve.app`
5. ✅ Unused-Imports raus (settings.py, organisations.py)
6. ✅ Theme-Silent-Overwrite → 400
7. ✅ Languages-Liste auf ['de','en'] reduziert
8. ✅ **Bonus:** 4 Code-Review-Warnings im selben Phase-Block mitgefixt (WR-01 ValueError-Guard, WR-02 Unicode-Fix analytics.html, WR-03 Duplicate-Display dashboard.html, WR-04 Language-400-Konsistenz)

**Ergebnis:** 4 Launch-Blocker weg (LB-5, LB-6, LB-12, LB-13). 9 Launch-Blocker noch offen (LB-1/2/3/4/7/8/9/10/11).

**Commits:** Siehe `.planning/phases/08.6-stabilisierung-block-a-quick-wins/` + [[05 Log]] Eintrag 2026-04-24 spätabends.

### BLOCK B — Auth-Härtung (EA-Launch-Pflicht, ~12-15h)

Thema: Security-Baseline die nie gesetzt wurde.

1. LB-9 CSRF-Protection flächendeckend — 3-4h
2. LB-10 Session-Cookie-Flags — 15 min
3. H-17 Session-Fixation uniform (session.clear in _login_user) — 10 min
4. H-20 flask-limiter für /api/login + /api/register — 2-3h
5. M-AU-1 Org-Scoping-Assertion — 15 min
6. H-21 oauth_id UNIQUE-Constraint + Migration — 30 min
7. H-18 Microsoft-OAuth Email-Hijacking-Mitigation (Option A: Confirmation-Email) — 2-3h
8. LB-7 zentraler Error-Handler + Frontend-Traceback-Filter — 1-2h
9. H-15 + M-NEW-5 Route-Exception-Message-Leaks reduzieren — 1h

**Gesamt:** ~12-15h. Ideal als `/gsd-secure-phase` + Threat-Model.
**Kandidat für Phase:** "04.x Auth-Launch-Härtung"

### BLOCK C — Schema-Drift-Cleanup (EA-Launch-Pflicht, ~6-10h)

Thema: Profile-Schema-Harmonisierung quer durch Wizard/Onboarding/Routes/Editor.

1. LB-11 Onboarding-Redirect aktivieren (`auth.py:60-62` reaktivieren) — 1-2h
2. H-31 (HSR-2) `BRANCHE_TEMPLATES` auf `basis.*`-Schema umstellen — 1-3h
3. Wizard-Create (`profiles.py:wizard_create`) auf `basis.*` angleichen — 1h
4. LB-3 QA-Pipeline profile_data + confidence-Parameter durchreichen — 1h
5. H-13 `/api/frage` + `/api/ewb_trigger` auf `basis.produktbeschreibung` lesen (oder bei Block-E-Entscheidung entfernen) — 30 min
6. H-25 Rollen-Check `_rolle()` für `wizard_create`, `aktivieren`, FAQ-API, Tabu-API — 30 min

**Gesamt:** ~6-10h. Löst LB-3, LB-11, H-13, H-25, H-31 gleichzeitig + bereitet LB-15/H-39 Pydantic-Schema vor.

### BLOCK D — DSGVO-Paket (EA-Launch-Pflicht, ~16-20h)

Thema: Rechtliche Basis + Audit-Transparenz.

1. LB-1 Password-Reset-Flow komplett (Route + Template + Email-Verdrahtung + Audit-Events) — 3-4h
2. LB-2 DSGVO-Routen: `/dsgvo/data_export`, `/dsgvo/account_delete`, `/dsgvo/consent_withdraw`, `/dsgvo/data_portability` — 8-12h
3. H-19 `settings.delete_account` → Umleitung auf `/dsgvo/account_delete` — Teil von LB-2
4. H-8 + H-16 + H-26 + MSR-2: Audit-Events für register, password_reset, account_delete, data_export, consent_change, failed_login, profile-create/delete/activate, tabu/faq-Änderungen, org-invite/revoke/deactivate — 4-6h
5. DSGVO-Löschkaskaden verifizieren (Cascade-FKs in Profile/ConversationLog/etc.) — 1h (Teil M-2 aus Profile-Audit)
6. `consent_text`-Änderungshistorie + `headset_confirmed`-Audit — 30 min
7. Retention-Policy definieren (Audit-Log nicht ewig halten, aber Immutable-Trigger-Konflikt lösen) — 1h

**Gesamt:** ~16-20h. **Paket mit LB-2 als Kern.** Ohne diesen Block kein Public-EA.

### BLOCK E — Cost-Tracking + Model-Modernisierung (EA-Launch-Pflicht, ~14-16h)

Thema: Billing-Integrität + Caching + Sonnet-Upgrade + Latenz-Messung. Strategische Entscheidung 2026-04-24: einmaliger Durchgang durch alle 17 Claude-Call-Sites statt später nachziehen (ein Durchgang statt drei).

1. LB-4 Cost-Tracker explizite user_id in allen Call-Sites + Concurrency-Test — 2-3h
2. H-12 + H-29 5 inline-Anthropic-Clients → geteilter `claude_service.claude_client` — 1-2h
3. H-22 `api_postcall_insights` Cost-Hook + Sanitize-Patch — 1h
4. **Model-Konstanten pro Call-Site in config.py** (ENV-basiert, Runtime-switchbar via `.env` + `systemctl restart nerve`) + 17 Stellen migrieren — 1h
   - Defaults Sonnet wo User liest/hört: MODEL_EWB, MODEL_QA, MODEL_TRAINING_HELP, MODEL_TRAINING_SCORING, MODEL_POSTCALL_INSIGHTS, MODEL_POSTCALL_ANALYSIS, MODEL_WEEKLY_SUMMARY, MODEL_PRECALL, MODEL_CRM
   - Defaults Haiku wo intern/latenz-kritisch: MODEL_ANALYSE, MODEL_TRAINING_DIALOG, MODEL_PERSONALITY_GEN
5. **Prompt-Caching (POLISH-58)** für EWB + QA + Analyse-Loop — 2-3h
   - `cache_control: {type: "ephemeral"}` auf System-Prompt-Block
   - Verifikation: System-Prompt byte-identisch pro Session
   - Cache-Hit-Rate aus `response.usage.cache_read_input_tokens` loggen
6. **Sonnet-Upgrade für Live-Pfade** (EWB + QA mit Streaming-Config-Check) — 1h
7. **Sonnet-Upgrade für Low-Volume-User-Outputs** (PostCall-Insights, Weekly-Summary, PreCall-Recherche, Training-Help, CRM) — 30 min
8. H-9 Deepgram-Cost-Fix (STT-Sekunden statt Socket-Lifetime) — 2-3h
9. **Latenz-Logging** in ApiCostLog (neue Spalten `latency_ms` + `call_site`) + Founder-Dashboard p50/p95/p99 pro Call-Site — 1-2h
10. L-NEW-4 Training-STT Cost-Hook — 30 min
11. FX-Fallback aktualisieren + FX-Logik-Duplikat entfernen — 30 min

**Ausdrücklich NICHT umgestellt auf Sonnet:**
- Analyse-Loop (Haiku bleibt — alle 4s Latenz-kritisch, User sieht nur aggregierte Flags)
- Training-Dialog (Haiku bleibt — ElevenLabs-Kosten + Realismus: echte Kunden sprechen nicht druckreif)

**Kombinations-Hebel:** Sonnet + Caching-Hit = $0.30/MT Input vs. Haiku ohne Cache = $0.80/MT. Für input-schwere Calls (4000-Token System-Prompt) ist **Sonnet gecacht ~2.7× BILLIGER als Haiku ungecacht** für den System-Prompt-Anteil.

**Gesamt:** ~14-16h. Löst LB-4, H-9, H-12, H-22, H-29, POLISH-58 (Prompt-Caching), 17 hardcoded-Model-Stellen + Sonnet-Qualitäts-Problem (André-UAT: "Haiku-Sprache unterirdisch, Grammatikfehler").

### BLOCK F — Classic-View-Deprecation (EA-Launch-Pflicht, ~3-5h)

Thema: **Eine Architekturentscheidung eliminiert 3 HIGH-Findings + 600 Z. Code.**
**Entscheidung 2026-04-24:** Classic-View komplett raus. PiP-only. Begründung André: "Nutzt niemand, gibt nur Anlass dass später wieder was daran verkoppelt wird und Probleme auslöst."
2. `/live`-Route redirectet auf PiP-Launcher-Flow — 30 min
3. Classic-Socket-Handler in app.js entfernen (Z.452-570) — 1h
4. Polling-Chain + Legacy-EWB-Render entfernen (app.js:780-811, 798-799) — 30 min
5. `/api/frage`, `/api/ewb_trigger`, `/api/ergebnis`, `/api/swap_roles`, `/api/log_correction`-Classic-Parts im Backend entfernen — 2h
6. Nutzer-Migration-Doc + UX-Redirect — 30 min
7. Manual-Test: alle 5 EA-Flows noch intakt — 30 min

**Löst:** H-12 Teil, H-13, H-14, H-15-Teil, H-34, H-35, H-36
**Aufwand:** ~3-5h

### BLOCK G — PreCall-Briefing Re-wire (EA-Launch-Pflicht, ~3-4h)

Thema: 3-Schichten-Feature-Fake durch echte Integration beenden.
**Entscheidung 2026-04-24:** Re-wire statt Deprecate. Begründung André: "PreCall in EWB-Kontext ergibt bessere Einwandbehandlung — Firmen-Kontext rein, bessere Antworten raus." Plus: Caching (Block E.5) hält den vergrößerten System-Prompt preis-neutral. Der Kombi-Gedanke.

1. `build_profile_context` um `precall_briefing`-Sektion erweitern (aus `ls.state['precall_briefing']`) — 1-2h
2. `coaching_service.generate_postcall_analysis` liest `ConversationLog.precall_briefing` + Prompt-Integration — 1h
3. Teil-Fix H-6: `generate_postcall_analysis` `profile_data`-Parameter durchreichen und in Prompt einbauen — 1h
4. Smoke-Test: Session mit PreCall-Briefing starten, EWB triggern, verifizieren dass Briefing-Info im System-Prompt landet — 30 min

**Löst:** H-2, H-6, H-37 (session_detail-UI bleibt, ist jetzt ehrlich), F-9 (Frontend-Ping-Pong wird zu echter Pipeline)
**Gewinn:** Caching (Block E.5) hält steigenden System-Prompt preis-neutral. Kombi-Entscheidung mit E macht das tragbar.
**Kein Frontend-Change nötig:** Frontend sendet bereits korrekt (app.js:649, pip-launcher:998, 1891).

### ✅ BLOCK H — Test-False-Greens entfernen (ABGESCHLOSSEN 2026-04-25, GSD-Phase 08.7)

**Status:** Komplett. Test-Suite-Delta: 295 → 268 passing, 0 neue Failures.

1. ✅ `test_qa_pipeline_t1.py` — 4 RED-Gate-Stubs gelöscht
2. ✅ `test_claude_service_phase08.py` — 7 inspect.getsource/hasattr-Tests gelöscht → H-3/H-4 Prune-Blockade aufgehoben
3. ✅ `test_08_5_05_training_pipeline_t2.py` — 11→3 (3 echte Mocked-Integration-Tests behalten: 12/13/14)
4. ✅ `test_phase_08_migration.py` — nach `tests/archive/` mit pytest.ini-Exclusion via `norecursedirs`
5. ✅ `tts_comparison.py` → `scripts/` (kein pytest-Test, print-basiert)
6. ✅ `salesnerve/CLAUDE.md` — Regel codifiziert: "Test ist grün nur wenn Integration-Assertion (DB-Write/API-Response/State-Mutation), nicht Source-Presence." Präzise Trennung: `inspect.getsource → DELETE, inspect.signature → OK`

**Aufwand:** ~25 Min (Plan 12 Min + Execute 12 Min). Geplant 4h, war deutlich schneller weil mechanisch.

**Block I damit entsperrt** — H-3 + H-4 sind jetzt frei zum Löschen.

### BLOCK I — Dead-Code-Prune (vor EA empfohlen, ~4-6h)

Thema: Nudelcode-Reduktion nach Block H.

1. H-3 `analysiere_mit_claude_streaming` (102 Z.) löschen — 15 min
2. H-4 `_build_system_prompt` + `_get_erfolgsquoten` (195 Z.) löschen — 30 min
3. H-11 if/else-Branch in analyse_loop + CONCERNS.md-Doku korrigieren — 15 min
4. H-1 `finetune_logging.py` Entscheidung: **Empfehlung: removen** für EA (1h) — alle log_pipeline_event-Calls entfernen, `FtPipelineEvent`-Tabelle droppen. Später implementieren wenn FT-Training startet.
5. H-27 `/coach/live_tipp` + `/coach/api/tipps` + ls.coach_tipps entfernen — 30 min
6. H-28 Personality-Save Entscheidung: **Empfehlung: Route + Feld entfernen** für EA (30 min). POLISH-37 später.
7. Orphan-Routes: `/api/swap_roles`, `/api/status`, `/api/keepalive`, `/api/skripte`, `/api/my_profiles`, `/api/feedback/quick`, `/api/learning_cards/<id>/regenerate + status`, `/api/phrases`, `/training/ping` entscheiden + prunen — 1h
8. M-NEW-7 `/api/training/postcall-analysis` Status klären (tot oder live? wenn tot: entfernen inkl. H-5 Redeanteil-Fake) — 30 min
9. Orphan-Templates `login.html`, `admin/feedback_notification.html`, `_tooltip.html` — 15 min
10. F-8/H-36 `ewb_top2`-Writer suchen + entfernen (Reader in app.js:798-799 + Response-Key in app_routes.py:145) — 30 min
11. Legacy-`opener` vs. `openerItems` — Pruning-Entscheidung — 30 min

**Gesamt:** ~4-6h. **~500-800 Zeilen weg.** Nudelcode-Oberfläche signifikant reduziert.

### BLOCK J — Routes-Härtung + Validation (EA-Launch-empfohlen, ~4-6h)

Thema: Robustheit gegen kaputte Requests.

1. H-22 `api_postcall_insights` Input-Sanitize — 30 min (zusammen mit E.3)
2. H-23 `api_beenden` TOCTOU-Fix — 15 min
3. H-24 `api_set_phase` Validation — 15 min
4. HSR-1 `BillingEvent.org_id=1`-Fallback entfernen — 1h
5. MSR-3 Stripe-Checkout try/except — 30 min
6. MSR-4 Checkout-Success Race (Webhook-Wait oder Dashboard-Härtung) — 1-2h
7. MSR-1 + MSR-2 Org-Invite-Email + Audit-Events — 1h (überlappt mit Block D.4)
8. HSR-3 Waitlist-Invite-Email — 2h
9. M-AU-2 USt-ID-Validation — 1-2h

**Gesamt:** ~6-9h. Einige Stunden überlappen mit Block D.

### BLOCK K — DSGVO-Localstorage + UI-Mini-Fixes (EA-Launch-Kür, ~2-3h)

Thema: Frontend-DSGVO-Lücken.

1. FM-3 `nerve_pip_kundendaten` TTL + Clear-Button + Datenschutz-Text — 1-2h
2. S-3 `headset_confirmed` als Audit-Event — 30 min
3. F-7 bei Block-G-Deprecate-Entscheidung: session_detail.html anpassen — 5 min
4. FM-1 `escHtml` um `'` erweitern — 15 min

**Gesamt:** ~2-3h.

### BLOCK L — Test-LB-Coverage (parallel zu A-E, ~10-15h)

Thema: Launch-Blocker absichern mit Integration-Tests.

1. LB-1 Password-Reset-Flow-Test (3-4 Tests) — 2h
2. LB-2 DSGVO-Routen-Tests (je 2-3 Tests × 4 Routen) — 3h
3. LB-3 `_qa_pipeline_dispatch` mit geladenem Profil + Tabu-Assertion — 1-2h
4. LB-4 Cost-Tracker Concurrency-Test — 1h
5. LB-5/LB-6 `test_deepgram_service.py` Writer-Test — 1h
6. LB-7 Error-Handler-Integration-Test — 1h
7. LB-9 CSRF-Integration-Tests — 1-2h
8. LB-11 Onboarding-Profil-Auto-Redirect-Test — 30 min
9. LB-13 ROI-Berechnungs-Test (verhindert erneutes Fantasiebranchen-Regression) — 30 min

**Gesamt:** ~10-15h. **Parallel-Track** während Block A-E läuft.

### BLOCK M — Härtung nach EA-Start (Post-Launch, ~15-20h)

Thema: Stabilität + Edge-Cases.

1. H-7 Keyword-Matcher Race-Fix — 3-4h
2. LB-8 Multi-Worker-Guard — 2-3h
3. M-NEW-4 Training-Session-State Redis-Migration — 3-4h
4. MSR-5 Revenue-Record async/cache — 2-3h
5. MSR-9 Semver-Compare — 1h
6. Alle MEDIUM-Punkte-Sammelrunde — 5-8h

### BLOCK N — Profil-Redesign (separat, wie geplant)

Thema: Phase-B/C — bleibt unangetastet von Block A-M.

1. Phase-A-Audit als Input (bereits fertig)
2. Phase-B Sales-Literatur-Research
3. Phase-C Pydantic-Schema für Profile.daten (H-39, LB-15 aus Welle 3)
4. Tote Felder re-integrieren (nogos, wettbewerber, uebergaenge, kaufsignale, consent_text Live-Pfad)
5. TABU_DEFAULT_PAIRS Backend-Source-of-Truth (M-4, 2-3h)

---

## 🗺️ ROADMAP-UPDATE — Reihenfolge der Blöcke

### **Phase 1: EA-Launch-Reparatur** (Pflicht, ~100-120h)

**Strategische Entscheidung 2026-04-25 (André):** **Alle 14 Blöcke (A-M) werden vor EA-Launch abgearbeitet.** Block N (Profil-Redesign) bleibt separater Post-Launch-Track. Begründung: "Erst wenn die ganze App bereinigt wurde, fangen wir an dort wieder was drauf zu bauen. Kein 'das ist nicht launch-entscheidend'." Konsistent mit CLAUDE.md "Lieber einmal richtig" + Anti-Abrieb-Prinzip. Block M später während laufendem EA einbauen würde Bugs in User-Daten einfrieren = Abrieb-Quelle.

**Entscheidungen 2026-04-24 gefällt:**
- Block F: Classic-View komplett raus (PiP-only)
- Block G: PreCall re-wire (nicht deprecate) — Kombi-Entscheidung mit E.5 Caching
- Block E erweitert: +Caching (POLISH-58), +Sonnet-Upgrade für User-sichtbare Outputs, +ENV-basierte Model-Switchbarkeit, +Latenz-Logging

**Erledigt:**
- ✅ Block A (Phase 08.6, 2026-04-24) — 4 LBs + Bonus-Fixes
- ✅ Block H (Phase 08.7, 2026-04-25) — Test-Suite gereinigt

**Aktiv:**
- Block I (Dead-Code-Prune, 4-6h) — H-3/H-4 jetzt frei, läuft als nächstes (vermutlich Phase 08.8)

**Danach Parallel-Track:**
- Block B (Auth-Härtung, 12-15h) — als `/gsd-secure-phase`, Cross-AI-Plan-Review mit Gemini
- Block C (Schema-Drift, 6-10h)
- Block E (Cost-Tracking + Caching + Sonnet, 14-16h) — Cross-AI-Plan-Review mit Gemini

**Danach:**
- Block D (DSGVO-Paket, 16-20h) — der dickste Block, Cross-AI-Plan-Review mit Gemini pflicht
- Block J (Routes-Härtung, 6-9h)
- Block L (Test-LB-Coverage, 10-15h, parallel-Track)

**Letzte Welle vor Launch:**
- Block F (Classic-Deprecation, 3-5h)
- Block G (PreCall Re-wire, 3-4h) — idealerweise nach Block E.5 (Caching live)
- Block K (DSGVO-Frontend, 2-3h)
- **Block M (Härtung, 15-20h) — NEU vor Launch verschoben:** Keyword-Matcher-Race, Multi-Worker-Guard, Training-Redis-Migration, Revenue-Webhook-Cache. Verschoben aus Post-Launch nach Andrés Anti-Abrieb-Entscheidung.

**Gesamt Phase 1:** ~100-120h (12-15 Arbeitstage bei 8h/Tag) — nach Block-M-Verschiebung in Pre-Launch (+15-20h gegenüber 82-100h-Schätzung vom 24.04.).

### **Phase 2: Profil-Redesign** (wie geplant, Post-Launch)

- Block N

---

## 🚨 ALLE BLÖCKE EA-LAUNCH-BLOCKIEREND (Entscheidung 2026-04-25)

Frühere Trennung "Pflicht vs. Härtung" aufgehoben. Alle 14 Blöcke A-M sind Pre-Launch-Pflicht.

| Block | Status | Grund-Kategorie |
|---|---|---|
| **A** Quick-Wins | ✅ done | Trivial, LB-5/6/12/13 |
| **H** Test-Cleanup | ✅ done | Prune-Blockade lösen |
| **I** Dead-Code-Prune | 🔴 aktiv | Nudelcode-Reduktion vor Block B/D arbeit |
| **B** Auth-Härtung | 🟠 wartet | CSRF-Löcher + Session-Cookies → DSGVO-USP-Bruch |
| **C** Schema-Drift | 🟠 wartet | Ohne LB-11-Fix EA-User mit leeren Profilen |
| **D** DSGVO-Paket | 🟠 wartet | Password-Reset + Routen + Audit = rechtliche Basis |
| **E** Cost+Caching+Sonnet | 🟠 wartet | LB-4 Multi-User-Billing + Sonnet-Sprachqualität |
| **F** Classic-Deprecate | 🟠 wartet | Beschlossen 2026-04-24 |
| **G** PreCall-Rewire | 🟠 wartet | Beschlossen 2026-04-24, Kombi mit E.5 |
| **J** Routes-Härtung | 🟠 wartet | TOCTOU + Validation + Stripe-Edge-Cases |
| **K** Frontend-DSGVO | 🟠 wartet | localStorage-TTL + Audit-Events |
| **L** LB-Tests | 🟠 wartet (parallel) | Regression-Schutz |
| **M** Härtung | 🟠 wartet | **Verschoben aus Post-Launch.** Ohne Block M würden User-Daten in EA-Bugs einfrieren. |
| **N** Profil-Redesign | 🟢 Post-Launch | Separater Track |

---

## 📊 Gesamt-Health-Score — Update v2

| Dimension | v1-Status | v2-Status | Veränderung |
|---|---|---|---|
| **Core-EWB-Pipeline** | 🟡 Nudelig | 🟡 Nudelig | — |
| **QA-Pipeline (08.5)** | 🔴 De facto kaputt | 🔴 De facto kaputt | — |
| **PreCall** | 🔴 Feature-Fake | 🔴 3-Schicht-Feature-Fake bestätigt | verschärft |
| **FT-Logging** | 🔴 Nicht existent | 🔴 Nicht existent + Tests decken es | verschärft |
| **Cost-Tracking** | 🔴 Multi-User-Horror | 🔴 + 5 inline-Anthropic-Clients | verschärft |
| **Auth** | 🟠 Reset fehlt | 🔴 + CSRF + Session-Cookies + OAuth-Hijack | **stark verschärft** |
| **DSGVO** | 🔴 Routen fehlen | 🔴 + 10+ Audit-Gaps + Delete-Lüge | verschärft |
| **Onboarding** | 🟡 Unbekannt | 🔴 Schema-Drift + kein Startprofil | **NEU ROT** |
| **Training** | 🟡 Fake-Redeanteile | 🟠 Dead-Features + ungetestet | — |
| **Live-Analysis-Loop** | 🟢 Solide | 🟢 Solide | — |
| **Keyword-Matcher** | 🟡 Race | 🟡 Race | — |
| **Doku-Integrität** | 🔴 Optimistisch | 🔴 + 3 neue Doku-Lügen | verschärft |
| **Admin-Flask-Views** | nicht gescannt | 🔴 Ghost-Columns → Crash | **NEU ROT** |
| **Dashboard-ROI** | nicht gescannt | 🔴 Fantasiebranche | **NEU ROT** |
| **Classic-Live-View** | nicht gescannt | 🟡 Alt-Pfad ohne Phase-06/08.5 | **NEU GELB** |
| **Tests** | nicht gescannt | 🔴 20% False-Greens + LB-Coverage 0% | **NEU ROT** |
| **Frontend-Security** | nicht gescannt | 🟠 CSRF + Traceback-DOM + XSS-Attributbreak | **NEU ORANGE** |
| **Frontend-Schema** | nicht gescannt | 🟢 Korrekt `basis.*` | **NEU GRÜN** |

---

## 🎯 Top-5-Message an André

1. **EA-Launch ist weiter weg als v1 suggerierte.** ~82-100h Pflicht-Arbeit (vs. v1-Schätzung ~30h). Grund: Welle-3-Auth-Löcher (CSRF + Cookies) sind nicht optional für DSGVO-B2B. Plus Onboarding-Schema-Drift bedeutet: **ohne Fix starten alle 50 EA-User mit leeren Profilen.** Plus Block-E-Erweiterung um Caching + Sonnet-Upgrade (Entscheidung 2026-04-24, löst Haiku-Sprachqualitätsproblem).

2. **Classic-View-Deprecation beschlossen** (Block F). Eine Architekturentscheidung eliminiert 3 HIGH-Findings, 600 Z. Code und reduziert Wartungsfläche für zukünftige Phasen drastisch. Begründung André: "Nutzt niemand, gibt nur Anlass dass später was daran verkoppelt wird."

3. **PreCall re-wired statt deprecaten** (Block G). Feature liefert echten EWB-Value (Firmen-Kontext → bessere Einwandbehandlung). Kombi-Entscheidung mit Block E.5 (Caching): vergrößerter System-Prompt bleibt preis-neutral durch 90%-Cache-Read-Rabatt. Sonnet gecacht ist ~2.7× BILLIGER als Haiku ungecacht für Input-heavy Calls.

4. **Der Prune (Block I) ist blockiert durch Tests die aktiv Dead-Code schützen.** Block H (Test-Cleanup) muss VOR Block I kommen. ~4h Test-Arbeit vor ~4-6h Prune-Arbeit. Sonst scheitert jede Dead-Code-Löschung an roten Tests.

5. **Kein DACH-EA vor Block A+B+C+D+E+F+G+H+L abgeschlossen.** Das sind die harten LB-Fixes + Classic-Deprecate + PreCall-Rewire. Block I/J/K sind Hebel-/Nice-to-have, können nach EA-Start parallel laufen.

---

*Ende MASTER-AUDIT v2. Erstellt 2026-04-24 16:40. Aktualisiert 2026-04-24 abends nach André-Entscheidungen zu Block F (Classic raus), Block G (PreCall rewire), Block E erweitert (+Caching +Sonnet +ENV-Switchbarkeit +Latenz-Logging). Nächster Schritt: Block A starten (~30 min, Quick-Wins).*
