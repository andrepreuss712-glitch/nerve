---
audit: deep-dive-audit-cost-feedback-email
erstellt: 2026-04-24
dateien:
  - services/audit.py (27 Zeilen)
  - services/cost_tracker.py (120 Zeilen)
  - services/feedback_service.py (47 Zeilen)
  - services/email_service.py (72 Zeilen)
autor: Claudian (Vault)
methode: Code komplett gelesen + Call-Graph-Grep (*.py gesamte Codebase) + Cross-Check gegen Welle 1 (claude_service + live_session/ki_logik) + Model-Schema-Check (database/models.py) + ls.state-Writer-Scan (live_session.py, deepgram_service.py)
---

# Deep-Dive: audit.py / cost_tracker.py / feedback_service.py / email_service.py

## TL;DR

Vier Support-Services mit **insgesamt 266 Zeilen Code**, aber **fünf systematische Nudelcode-Muster** bestätigt + drei neue:

1. **`cost_tracker._resolve_org_id_from_live_session()` ist zu 100% ein GHOST-Read** — bestätigt aus Welle 1. `ls.state['org_id']` wird in der **gesamten Codebase nie geschrieben**. Grep `state\['org_id'\]|state\.get\('org_id'\)` → **null Writer**, nur zwei Reader (beide in cost_tracker.py). `_resolve_org_id_from_live_session()` liefert IMMER `None`. Konsequenz: `ApiCostLog.org_id` ist für **alle** Live-Call-Costs NULL, und der Per-Org-Breakdown in `routes/admin_dashboard.py:548-550` (WHERE `ApiCostLog.org_id == org_id`) findet **null Rows**.
2. **`log_api_cost(user_id=None)` wird NICHT verworfen** — er schreibt mit user_id=NULL in die DB (nach Fallback-Resolve). Der Fallback greift nur wenn `ls.state['user_id']` gesetzt ist (das wird in `deepgram_service.py:351` beim Socket-Start gesetzt). **Aber** außerhalb aktiver Live-Sessions (precall, post-call Coaching, weekly Report) greift der Fallback nicht → row bekommt `user_id=NULL`. **14 von 27 Live-Call-Cost-Stellen in claude_service.py haben user_id=None explizit hardcoded** → bei EWB-Pipeline greift Fallback zufällig weil die analyse_loop unter Socket-Session läuft, bei `classify_phase`, `infer_customer_state` aber nur wenn Session aktiv. Silent Per-User-Cost-Miss-Attribution.
3. **`email_service.send_password_reset` / `make_reset_token` / `parse_reset_token` sind KOMPLETT DEAD** (neu gefunden). Grep in Codebase → **null Caller** für alle drei. Es gibt nirgendwo eine `/reset-password` Route. Existiert als Shell seit Phase 04.7-05, nie verdrahtet.
4. **Audit-Coverage-Lücken DSGVO-kritisch** (neu): keine `register`-Audit, kein `password_reset`-Audit, kein `account_delete`-Audit, kein `consent_change`-Audit, kein `data_export`-Audit. Aktuell nur 6 action-types: login, logout, session_start, session_end, profile_update, feedback_in_planning. DSGVO Art. 7/15/17/20 nicht log-gedeckt.
5. **`Feedback` vs. `FeedbackEvent` Schema-Parallelismus** (neu): es existieren ZWEI separate Models (`Feedback` Zeile 401, `FeedbackEvent` Zeile 197) mit unterschiedlichen Feldern. `feedback_service.create_feedback` schreibt nur in `Feedback`. `FeedbackEvent` wird von `routes/app_routes.py:1287` separat angelegt (nach-Call Star-Rating). Zwei parallele Feedback-Pfade ohne gemeinsamen Service — Analytik muss beide Tabellen joinen, tut das nirgends.

**Bestätigte Ghosts/Dead/Zombies:** 1 Ghost-Read (`org_id`), 3 DEAD (`send_password_reset`, `make_reset_token`, `parse_reset_token`), 0 Zombie.
**Silent-Failure-Density gesamt:** audit.py: 1 | cost_tracker.py: 4 | feedback_service.py: 0 | email_service.py: 2 | **Σ = 7**.

---

## 1. Call-Graphs

### 1.1 `services/audit.py`

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `log_action` | 5 | `routes/auth.py:128` (login password), `routes/auth.py:278` (logout), `routes/oauth.py:104+130` (OAuth-login: existing user + new user), `routes/app_routes.py:584+587` (session_start + session_end), `routes/profiles.py:169` (profile_update), `routes/admin_views.py:75` (feedback_in_planning) | **LIVE** | 8 Live-Call-Sites in 5 Route-Files. Korrekt verdrahtet wo verdrahtet. |

**Summary audit.py:** 1 LIVE Funktion. 0 DEAD, 0 Zombie.
**ABER — Coverage-Lücken systematisch (siehe §5):** api_register, password_reset, account_delete, consent_change, data_export, invitation_create, kontoupgrade, subscription_change, admin_impersonate — alles nicht geloggt.

### 1.2 `services/cost_tracker.py`

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `_get_current_fx_rate` | 14 | `log_api_cost:93` (intern) | INTERNAL | Fallback 0.92 für USD→EUR. Fallback-Wert hardcoded, nicht aus ExchangeRate-Table. |
| `_resolve_user_id_from_live_session` | 31 | `log_api_cost:77` (intern) | INTERNAL | Liest `ls.state['user_id']` (Writer existiert in `deepgram_service.py:351`). Greift nur in aktiver Socket-Session. |
| `_resolve_org_id_from_live_session` | 42 | `log_api_cost:79` (intern) | **INTERNAL (Ghost-Reader)** | Liest `ls.state['org_id']` — **NULL Writer in der Codebase**. Gibt IMMER `None` zurück. |
| `log_api_cost` | 51 | 27 Call-Sites in 8 Service-Files (siehe Übersicht unten) | **LIVE** | Nicht-blockierend, by-design. |

**Live-Caller-Übersicht `log_api_cost` (27 Calls):**
| Datei | Zeilen | `user_id` übergeben | `context_tag` |
|---|---|---|---|
| `services/claude_service.py` | 539, 542, 611, 614, 692, 695, 785, 788, 877, 880, 981, 984, 1027, 1030 | **alle `user_id=None`** (14×) | phase_classify, coldcall_infer, live_haiku, pip_stream, pip_autovar, pip_variante, coaching_haiku |
| `services/coaching_service.py` | 96, 100, 329, 333 | `user_id=user_id` (4×, explizit) | postcall_coach, weekly_coach_report |
| `services/deepgram_service.py` | 252 | **`user_id=None`** | stt |
| `services/precall_service.py` | 175, 178 | **`user_id=None`** (2×) | precall |
| `services/qa_pipeline.py` | 347, 350, 467, 470 | **`user_id=None`** (4×) | qa_classifier, qa_response |
| `services/training_service.py` | 1316 | `user_id=uid` (aus Flask-g) | training_tts |

**Summary cost_tracker.py:** 1 LIVE public, 3 INTERNAL (davon 1 Ghost-Reader). 0 DEAD.

### 1.3 `services/feedback_service.py`

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `_ensure_dir` | 11 | `save_screenshot:24` (intern) | INTERNAL | - |
| `save_screenshot` | 15 | `routes/feedback.py:26` | LIVE | 1 Caller — POST `/api/feedback`. |
| `create_feedback` | 31 | `routes/feedback.py:29` (/api/feedback), `routes/feedback.py:56` (/api/feedback/quick) | LIVE | 2 Caller. Routes in `routes/feedback.py` (Blueprint `feedback_bp`). |

**Weitere Feedback-Konsumenten:**
- `routes/admin_views.py:12`: imports `UPLOAD_DIR` Konstante (für Admin-Screenshot-Serving, Zeile 232)
- `routes/admin_views.py:45-81`: `FeedbackAdmin` — Admin-View mit action_mark_in_planning (nutzt `Feedback`-Model direkt, nicht über Service)

**Summary feedback_service.py:** 2 LIVE + 1 INTERNAL. 0 DEAD.

### 1.4 `services/email_service.py`

| Funktion | Zeile | Aufgerufen von | Status | Kommentar |
|---|---|---|---|---|
| `_send` | 17 | intern von `send_welcome`, `send_feedback_in_planning`, `send_password_reset` | INTERNAL | Wraps `resend.Emails.send`. |
| `send_welcome` | 29 | `routes/auth.py:217-218` (nach api_register), `routes/oauth.py:135-136` (nach OAuth-Signup) | LIVE | 2 Caller. |
| `send_feedback_in_planning` | 42 | `routes/admin_views.py:69` (FeedbackAdmin action) | LIVE | 1 Caller. |
| `send_password_reset` | 56 | **NIRGENDS** | **DEAD** | Keine Route `/forgot-password`, kein Caller in Routes/Services/Tests. 8 Zeilen toter Code. |
| `make_reset_token` | 66 | **NIRGENDS** | **DEAD** | Einziger Konsument wäre eine `/forgot-password`-Route, die nicht existiert. |
| `parse_reset_token` | 70 | **NIRGENDS** | **DEAD** | Wie `make_reset_token`. |

**Summary email_service.py:** 3 LIVE + 1 INTERNAL + **3 DEAD** (~17 Zeilen toter Code, Phase 04.7-05-Rest). Kein Feature-Flag, kein Kommentar "noch nicht fertig".

---

## 2. Cost-Tracker — Deep-Dive

### 2.1 Signatur-Verhalten bei `user_id=None`

```
log_api_cost(provider, model, user_id=None, units, unit_type, *, org_id=None, session_id=None, context_tag=None)
```

| Szenario | Pfad | Ergebnis |
|---|---|---|
| Live-Call während aktiver Socket-Session, `user_id=None` übergeben | Z.76-77 → `_resolve_user_id_from_live_session()` → liest `ls.state['user_id']` (in Socket-Session gesetzt in `deepgram_service.py:351`) | `user_id` = echter Wert, sauber geschrieben |
| Precall-Call (HTTP-Request), `user_id=None`, keine aktive Live-Session | Fallback liest `ls.state['user_id']` → kann **stale Wert vom letzten Call eines anderen Users** haben (Multi-User-Shared-State-Smell — **HIGH-Risk** in Phase 09+ wenn Concurrency) | Falscher User wird belastet |
| Admin/Background-Call, kein Socket, `user_id=None` | Fallback liest `ls.state['user_id']` → falls nie initialisiert, `None` | `user_id=NULL` in DB — akzeptiert (Column is nullable=True) |
| `user_id` explizit übergeben (z.B. `training_service:1316` mit `uid` aus `g.user.id`) | Fallback greift nicht | Sauber |
| `org_id=None` (immer, kein einziger Caller übergibt org_id) | Fallback `_resolve_org_id_from_live_session()` → liest `ls.state['org_id']` → **null Writer** → None | **`org_id=NULL` IMMER** |

**Verarbeitung:** Der Call wird NICHT verworfen. Er schreibt mit `user_id=NULL` oder `user_id=<stale>` in `api_cost_log`. Einzig bei fehlender aktiver `ApiRate` (Z.87-90) wird geskippt mit `[CostTracker] no active ApiRate for ...`.

### 2.2 `get_org_id()` — Ghost bestätigt

Such-Protokoll:
- Writer-Grep: `state\['org_id'\] = ` → **0 Treffer** in gesamter Codebase.
- Writer-Grep: `state\[.org_id.\]` → 0 Treffer.
- `live_session.py` `org_id`-Grep → 0 Treffer.
- Alternative (Schreib über `.update()`): kein `state.update({.*org_id`-Muster zu finden.
- Einzige Reader: `cost_tracker.py:46` + Cross-Ref aus Welle 1 (`ki_logik.py` wird dort diskutiert, aber nicht in dieser Datei).

→ **`_resolve_org_id_from_live_session()` gibt garantiert immer `None` zurück.**

**Konsequenz für Downstream:**
- `ApiCostLog.org_id` ist für **100% der geschriebenen Rows** NULL.
- `routes/admin_dashboard.py:548-550` macht `filter(ApiCostLog.org_id == org_id)` → **liefert 0 €** für jede Org. Das Per-Org-Cost-Dashboard zeigt leere Zahlen.
- `routes/admin_dashboard.py:610` (per-User cost) funktioniert nur für Calls wo user_id durch Fallback sauber gesetzt wurde (Live-Session-Contexts), nicht für Precall/QA-Pipeline/Phase-Classify.

### 2.3 Cost-Tiers — Dimensionierung

| Provider/Model | unit_type | units-Formel | Call-Site | Korrektheit |
|---|---|---|---|---|
| anthropic/haiku-4-5 | per_1k_input_tokens | `input_tokens / 1000` | claude_service, qa_pipeline, precall_service | ✅ korrekt |
| anthropic/haiku-4-5 | per_1k_output_tokens | `output_tokens / 1000` | dto | ✅ korrekt |
| anthropic/sonnet-4 | per_1k_input_tokens | `input_tokens / 1000` | coaching_service | ⚠️ **Model-Name inkonsistent:** überall `sonnet-4`, aber Code nutzt `claude-sonnet-4-6` (coaching_service:87). Bei Lookup `ApiRate.filter_by(model='sonnet-4')` muss ApiRate-Seed `sonnet-4` heißen, nicht `claude-sonnet-4-6` oder `sonnet-4-6`. **Ungeprüft ob ApiRate-Seed matcht.** |
| anthropic/sonnet-4 | per_1k_output_tokens | `output_tokens / 1000` | coaching_service | wie oben |
| deepgram/nova-2 | per_minute | `seconds / 60` | deepgram_service:249-253 | ✅ korrekt, aber: Deepgram bucht tatsächlich **pro STT-Sekunde, nicht Socket-Open-Zeit**. `time.time() - opened` misst Socket-Lifetime; bei Muted-Mic zahlt man weiter. **Overcharge-Risk** (zahlen mehr als Deepgram uns berechnet). |
| anthropic/haiku-4-5 | per_1k_input_tokens | wie oben | training_service (für TTS-Prompt? Falsch) | ⚠️ Check needed |
| elevenlabs/multilingual-v2 | per_1k_chars | `len(text) / 1000` | training_service:1308 | ✅ korrekt |

**Rate-Currency / FX:** D-02-Invariante (Kurs beim Schreiben einfrieren) ist implementiert: Zeile 93 holt `fx_rate`, Zeile 95-96 berechnet mit eingefrorenem Rate+FX, Zeile 105/107 persistiert beide Werte → nachträgliche Kursänderungen verfälschen historische Buchungen nicht. ✅

**Fallback-Kurs hardcoded:** Z.28 `return Decimal('0.92')` für USD→EUR wenn keine `ExchangeRate`-Row gefunden. Wenn die `ExchangeRate`-Tabelle leer ist (z.B. direkt nach DB-Migration ohne Seed-Job oder nach `fix_rates`-Script nicht gelaufen), buchen wir alle USD-Kosten mit 0.92. Aktueller EZB-Kurs ist ~0.89. **Potential ±3% systematischer Fehler** wenn Seed-Job hängt. Keine Warn-Log wenn Fallback greift.

### 2.4 Fair-Use / Monthly-Aggregation / Daily-Reset

**Grep nach "quota", "fair_use", "monthly_limit", "reset" in cost_tracker.py + models** → keine Implementation. Fair-Use wird in **CONCERNS.md** behauptet ("Fair-use limits enforced per user/org") — **im Code aktuell nicht enforced**. Es gibt:
- Kein Fair-Use-Check vor Call
- Keine Monthly-Aggregation-Function
- Keine Daily-Reset-Mechanik
- Keine Alert wenn ein User X€ überschreitet

ApiCostLog ist rein passiv — Post-Hoc-Analytics-Tabelle. **Fair-Use ist Doku-Lüge** (Scope nicht in dieser Audit-Datei, aber über CONCERNS.md-Cross-Check geflagged).

### 2.5 `context_tag` — Alle Tag-Werte im aktiven Code

10 distinkte Tags:
`phase_classify`, `coldcall_infer`, `live_haiku`, `pip_stream` (**DEAD** — streaming-Variante in claude_service ist dead laut Welle 1 H2), `pip_autovar`, `pip_variante`, `coaching_haiku`, `postcall_coach`, `weekly_coach_report`, `stt`, `precall`, `qa_classifier`, `qa_response`, `training_tts`.

**`pip_stream` → DEAD-Tag:** Wird aus `analysiere_mit_claude_streaming` (dead function) geschrieben. In `ApiCostLog` erwarten wir 0 neue Rows mit `context_tag='pip_stream'` — sollte beim nächsten Cleanup gelistet werden.

---

## 3. `audit.py` — DSGVO-Deep-Dive

### 3.1 Geloggte Events

Tabelle der tatsächlichen `log_action(...)`-Call-Sites:

| Route/Service | Action | DSGVO-Kategorie | Status |
|---|---|---|---|
| `routes/auth.py:128` | `login` (password) | Zugriffs-Log (Art. 32) | ✅ |
| `routes/oauth.py:104` | `login` (OAuth, existing) | Zugriffs-Log | ✅ |
| `routes/oauth.py:130` | `login` (OAuth, new user) | Zugriffs-Log + Signup | ⚠️ teilweise (Signup nicht explizit als eigene action) |
| `routes/auth.py:278` | `logout` | Zugriffs-Log | ✅ |
| `routes/app_routes.py:584` | `session_start` | Processing-Log (Art. 30) | ✅ |
| `routes/app_routes.py:587` | `session_end` | Processing-Log + Metrics | ✅ |
| `routes/profiles.py:169` | `profile_update` | Änderung (Art. 16) | ✅ |
| `routes/admin_views.py:75` | `feedback_in_planning` | Admin-Aktion | ✅ |

### 3.2 DSGVO-Lücken (Coverage)

| DSGVO-Artikel | Betroffene Aktion | Audit vorhanden? |
|---|---|---|
| Art. 6/7 | Consent-Änderung (user ändert `profile.consent_text` via UI) | ❌ **Nein** — profile_update ist zu grob, details-Dict enthält nur `{'name': p.name}`, kein diff |
| Art. 7 (Widerruf) | Consent-Widerruf | ❌ **Nein** — keine dedicated action |
| Art. 15 | Data-Export / Auskunft | ❌ **Nein** — Feature existiert gar nicht (grep findet keine Export-Route) |
| Art. 16 | Profil-Änderung | ✅ (profile_update, aber ohne Field-Diff) |
| Art. 17 | Löschung / Account-Deletion | ❌ **Nein** — Feature existiert nicht (grep: keine delete_user-Route). Wird bei Launch DSGVO-kritisch. |
| Art. 20 | Portabilität | ❌ **Nein** |
| Art. 32 | Login/Logout | ✅ |
| Art. 33 | Breach-Detection | ❌ **Nein** — kein failed-login-Audit, kein brute-force-Counter |
| - | Signup (Account-Creation) | ❌ **Nein** — `api_register` (routes/auth.py:187-223) loggt nichts. OAuth Signup loggt nur `login`, nicht `register`. |
| - | Invitation-Nutzung | ❌ **Nein** — `routes/auth.py:226+` `register()` via Invitation loggt nichts |
| - | Admin-Impersonate / Superadmin-Aktionen | ⚠️ teilweise (nur feedback_in_planning geloggt, alle anderen Admin-Edits in FeedbackAdmin/UserAdmin/OrgAdmin via Flask-Admin loggen nicht) |
| - | Password-Change / Password-Reset | ❌ **Nein** (Feature existiert eh nicht, siehe §4) |
| - | Subscription/Plan-Change | ❌ **Nein** — `routes/payments.py` verarbeitet Stripe-Events, loggt in RevenueLog aber nicht in AuditLog |

**10 DSGVO-kritische Aktionen NICHT in AuditLog.** Phase 04.7-02 VERIFICATION.md hat das nicht gecheckt (nur Plan-Scope abgehakt).

### 3.3 Retention-Policy für Audit-Logs

**Grep nach `retention|prune|audit_log_cleanup|Zeile löschen`** → **0 Treffer**. Kein Cron, kein Cleanup-Job, kein Retention-Limit.

- DSGVO Art. 5(1)(e) "Speicherbegrenzung" = Daten nur solange speichern wie zweckdienlich.
- Login/Logout-Logs vom 04.2026 werden 2030 noch existieren. Bei Support-Fällen OK (Nachvollziehbarkeit), aber ohne Policy + Löschung nach X Jahren = Gegenargument in jedem AVV/DPIA-Gespräch.

**Und:** Immutable-Trigger (app.py Z.1028-1038) verhindert UPDATE/DELETE → ohne Policy-Bypass-Mechanismus kann auch ein legitimer Retention-Cleanup die Tabelle nicht prunen. Man muss den Trigger temporär droppen + neu bauen.

### 3.4 Payload-Qualität

`details`-Feld (JSON):
- login: `{'method': 'password'|'google'|'microsoft'}` → OK, minimal
- session_start: `{'mode': session_mode}` → OK
- session_end: `{mode, dauer_sekunden, einwaende_total, einwaende_ok}` → OK, Aggregate-only ✅ (kein Transkript, DSGVO-konform)
- profile_update: `{'name': p.name}` → **zu wenig** — welche Felder wurden geändert? Wir können nicht nachvollziehen ob `consent_text` geändert wurde oder nur `ton`. **MEDIUM** für Compliance.
- feedback_in_planning: keine details → OK
- logout: keine details → OK

**`ip_address` + `user_agent`:** werden korrekt aus `request.remote_addr` + `request.headers['User-Agent'][:500]` geholt (Z.19-20). Keine PII-Bedenken (IP ist legit Zugriffslog).

---

## 4. `email_service.py` — Deep-Dive

### 4.1 SMTP / Provider

- Provider: **Resend** (nicht SMTP). `import resend` Z.2, `resend.api_key = os.environ.get('RESEND_API_KEY', '')` Z.5.
- EU-Region: optional via `RESEND_BASE_URL` ENV (Z.6-11). Falls gesetzt, wird `resend.base_url` überschrieben. **Dokumentation in 04.7-05-PLAN.md sagt: EU-Region wird primär via Resend-Account-Setting gesetzt, ENV nur defensiv.** VPS .env hat das nicht — also wird die Account-Level-Region genutzt (muss manuell im Resend-Dashboard als EU konfiguriert sein — **nicht im Code prüfbar, Compliance-Risk falls jemand das Account-Setting ändert**).
- From-Adressen: hardcoded (Z.13-14) `noreply@getnerve.app` + `feedback@getnerve.app` — OK, stabil.

### 4.2 Mail-Typen

| Funktion | Zweck | Live | Template |
|---|---|---|---|
| `send_welcome(to_email, vorname='')` | Willkommensmail nach Signup | ✅ | Inline-HTML (Z.31-37) |
| `send_feedback_in_planning(to_email, feedback_text, vorname='')` | Notify bei Status-Change `in_planning` | ✅ | Inline-HTML |
| `send_password_reset(to_email, reset_url)` | Passwort-Reset-Link | **❌ DEAD** | Inline-HTML |

Template-Engine: **keine**. Alles Inline-HTML-Strings, keine Jinja-Templates, keine DB-Templates, kein Branding-Template-File. Für 3 Mails tragbar, aber jede Text-Änderung = Deploy.

### 4.3 Error-Handling / SMTP-Down

- `_send` (Z.17-26): bei fehlendem API-Key → `print + return False`. Bei Exception während Send → `print + return False`.
- Kein Retry, keine Dead-Letter-Queue, kein Alert.
- **Call-Sites hängen nicht** (keine Exception propagiert) → Request wird nicht gekillt. ✅
- **Aber:** `routes/auth.py:218` (nach api_register) ruft `send_welcome` in try/except mit print-fallback — double-belt. Redundant, aber schadet nicht.

### 4.4 Password-Reset — DEAD chain

`send_password_reset` + `make_reset_token` + `parse_reset_token` → **kein Caller**.

Konsequenz:
- User kann aktuell Passwort **nicht** zurücksetzen über eine Route
- Passwort-Reset nur via Admin (wenn überhaupt)
- Login-Page hat (ungeprüft) keinen "Passwort vergessen?"-Link, der funktioniert

**Recommendation:** Entweder 3 Funktionen entfernen (~17 Zeilen) ODER Route `/forgot-password` + `/reset-password/<token>` implementieren. Vor Launch kritisch (User erwarten Self-Service-Reset).

---

## 5. `feedback_service.py` — Deep-Dive

### 5.1 Feedback-Sammlung

**Routen:**
- `POST /api/feedback` (`routes/feedback.py:10`) — Multipart-Form mit optionalem Screenshot-Upload. Typ-Whitelist: `{bug, idea, praise, question}`. Min-Text: 3 chars.
- `POST /api/feedback/quick` (`routes/feedback.py:43`) — JSON, Rating 1-5, Kontext-Tag ('training'|'live').

**Pfad:** Route → `create_feedback(db, user_id, org_id, typ, text, ...)` → `Feedback`-Row. Screenshots via `save_screenshot` → `/opt/nerve/uploads/feedback/{uuid}.{ext}`. **Nicht** in DB (nur Pfad im Feld `screenshot_path`).

### 5.2 Verarbeitung / Aggregation

**Grep nach `Feedback`-Reads in Codebase:**
- `routes/admin_views.py` — `FeedbackAdmin` (Flask-Admin ModelView), `KpiDashboardView` zählt `feedback_new` + `feedback_planning`.
- Keine Coach-Auswertung, keine Aggregation, keine Analytics-Route für User/Teams.

**Kein Weg erreicht den Coach.** `Feedback` ist ein reiner Admin-Einbahn-Kanal. Der Coach-Service (`coaching_service.py`) referenziert `Feedback` nicht. Falls Coach später mit Feedback-Insights arbeiten soll → Feature-Gap.

### 5.3 Feedback vs. FeedbackEvent — Schema-Parallelismus (neu)

Es existieren **zwei** separate Models:

| Model | Zeile models.py | Zweck | Service | Wird gelesen von |
|---|---|---|---|---|
| `Feedback` | 401-415 | Freiform-Feedback + Screenshots + Rating + Status | `feedback_service.create_feedback` | admin_views |
| `FeedbackEvent` | 197-204 | Star-Rating nach Session (1-5 + comment) | kein Service | `routes/app_routes.py:1287` (direktes `FeedbackEvent(...)`) |

Kein Service wrappt `FeedbackEvent`. Analytics/Coach, die Post-Call-Ratings auswerten wollen, müssten `FeedbackEvent` joinen, tun es aber nirgends. **Doppel-Verwaltung. Developer-Confusion-Risk** (Welches Feedback-Model nehmen für Feature X?).

### 5.4 Screenshot-Upload-Sicherheit

✅ MIME-Whitelist serverseitig (Z.19), Extension-Whitelist (Z.21-22), UUID-Dateiname (Z.25, verhindert Path-Traversal + PII-im-Filename), `secure_filename` Double-Protection (Z.26). **`MAX_CONTENT_LENGTH = 5 MB`** laut Phase 04.7-VERIFICATION Z.51 (in app.py konfiguriert). Sauber.

⚠️ **UPLOAD_DIR Default `/opt/nerve/uploads/feedback`** — absolute Linux-Pfad hardcoded. Auf lokaler Windows-Dev-Maschine muss `FEEDBACK_UPLOAD_DIR` ENV gesetzt werden oder `_ensure_dir` versucht `C:\opt\nerve\...` zu erstellen. Auf VPS funktioniert's.

---

## 6. DB-Zugriffe aller 4 Dateien

| Datei | DB-Session-Quelle | commit/rollback | close-Pattern | Concurrent-Risk |
|---|---|---|---|---|
| `audit.py` | Parameter `db` vom Caller | `db.commit()` Z.23 | **Caller-responsibility** — `log_action` schließt nicht. Alle Call-Sites öffnen + schließen selbst (geprüft in auth.py:276-281, app_routes.py:584+587 im try/finally). | Low — jeder Caller mit eigener Session |
| `cost_tracker.py` | Eigene `SessionLocal()` in `log_api_cost:81` | `db.commit()` Z.112 | `try/finally: db.close()` Z.113-117 inkl. nested try für close-Error ✅ | Low — isolierte Session pro Call. **ABER:** Bei 2s-Ticks + Live-Session → 50+ kurze Sessions/Minute/User. Connection-Pool-Load unter Last. |
| `feedback_service.py` | Parameter `db` vom Caller | `db.commit()` Z.45 | **Caller-responsibility** (`routes/feedback.py` macht try/finally Z.21+40, sauber) | Low |
| `email_service.py` | **Keine DB** | - | - | - |

**Rollback-Handling:** Nur `cost_tracker.py` hat Error-Handling um den commit. `audit.py` und `feedback_service.py` haben KEINE explicit rollback bei db.commit()-Failure. Für `audit.py` wird's durch den äußeren try/except abgefangen (Z.11/24) — kein Request-Kill. Für `feedback_service.py` propagiert der Fehler nach oben (routes/feedback.py:21-40 hat nur `try/finally`, kein except) → **500 zurück an User wenn DB-commit zickt**. MEDIUM — besser als silent-fail, aber kein graceful Error-Handling.

**Context-Manager:** keine. Alle Patterns nutzen manuelles try/finally. Konsistent mit Rest der Codebase.

---

## 7. ls.state-Zugriffe

| Datei | Feld | Op | Lock | Writer | Status |
|---|---|---|---|---|---|
| `cost_tracker.py:37` | `user_id` | read | `state_lock` ✅ | `deepgram_service.py:351` (Socket-Session-Init) | LIVE |
| `cost_tracker.py:46` | `org_id` | read | `state_lock` ✅ | **NIEMAND** | **GHOST-READ** |

Kein weiterer ls.state-Zugriff aus den 4 Audit-Files. Sauber.

---

## 8. Verdachts-Stellen

### 8.1 TODO/FIXME/XXX/HACK

Grep über alle 4 Dateien → **0 Treffer**. Keine markierten Debt-Hotspots. (Was nicht heißt dass es keinen Debt gibt — siehe Findings unten.)

### 8.2 Auskommentierter Code

- `email_service.py:6`: `# optional override, e.g. 'https://api.resend.com'` — Kommentar-Doku, OK.
- Sonst keine Comment-Grabs.

### 8.3 "legacy"/"deprecated"/"Phase 0X"/"temp"

- `cost_tracker.py:1-9`: Phase-04.7.2-Header-Docstring, dokumentiert Design-Intent (D-02 Wechselkurs einfrieren). OK.
- `audit.py:9`: "DSGVO: Kein Transkript, kein Audio, nur Aggregate und Metadaten." — Kommentar, OK.
- `feedback_service.py`: kein Phase-Marker, kein Header-Docstring. Mini-File, OK.
- `email_service.py:13`: "Phase 04.7"-Kontext nur implizit via 04.7-05-SUMMARY.md — kein Header-Comment. OK.

### 8.4 Silent Failures (`except Exception: pass` / ohne Log)

| Datei | Zeile | Code | Severity |
|---|---|---|---|
| `audit.py:24-26` | `except Exception as e: print(f"[AUDIT] log_action failed: {e}")` | Print-only, kein strukturiertes Log, kein Sentry. OK für MVP. Bei Launch: umstellen auf logger.error mit Sentry-Hook. | LOW |
| `cost_tracker.py:26-28` | `except Exception: pass` (exchange-rate read) | **Silent-Swallow** — bei DB-Fehler während FX-Read greift Fallback 0.92. Kein Log, unsichtbar. | **MEDIUM** |
| `cost_tracker.py:38-39` | `except Exception: return None` (user_id resolve) | Silent, kein Log. | LOW (resolve ist best-effort) |
| `cost_tracker.py:47-48` | `except Exception: return None` (org_id resolve) | Silent. Plus: Ghost-Read → IMMER None egal ob Exception. | LOW (Ghost-Problem ist eigentliches Issue) |
| `cost_tracker.py:114-117` | `try: db.close() except Exception: pass` | Silent close-error. Akzeptabel. | LOW |
| `cost_tracker.py:118-119` | `except Exception as e: print(f"[CostTracker] log_api_cost failed ({provider}/{model}): {e}")` | Print-only, kein Sentry. | LOW |
| `email_service.py:8-11` | `try: resend.base_url = _eu_base except Exception: pass` | Silent. Akzeptabel (Lib-API-Unterschiede). | LOW |
| `email_service.py:22-26` | `except Exception as e: print(...) return False` | Print-only. | LOW |

**Silent-Failure-Density:**
- audit.py: **1** (nur der äußere Catch — by design, aber nur print)
- cost_tracker.py: **4** (exchange_rate, user_resolve, org_resolve, outer — alle print oder pass)
- feedback_service.py: **0**
- email_service.py: **2**
- **Total: 7**

### 8.5 Ungenutzte Imports

- `audit.py:1` `import json` — genutzt Z.18 ✅
- `cost_tracker.py:10` `from __future__ import annotations` — genutzt für `int | None`-Syntax ✅
- `feedback_service.py:1-4` alle genutzt ✅
- `email_service.py:1-3` — `resend`, `itsdangerous` genutzt (letzteres nur in dead code `make_reset_token`) ⚠️ falls make_reset_token entfernt wird, kann `itsdangerous`-Import entfernt werden.

### 8.6 Hardcoded IDs/Values

| Datei | Zeile | Wert | Kommentar |
|---|---|---|---|
| `cost_tracker.py:28` | `Decimal('0.92')` | Fallback FX USD→EUR | **Stale Wert** (EZB aktuell ~0.89). Out-of-date. |
| `cost_tracker.py:92` | `rate_currency = rate.currency or 'USD'` | Default 'USD' falls DB-Row leer | OK |
| `email_service.py:13-14` | From-Adressen `noreply@getnerve.app`, `feedback@getnerve.app` | OK |
| `email_service.py:34` | URL `https://app.getnerve.app/dashboard` hardcoded im HTML | Bei Domain-Wechsel: Edit nötig. Kein Config. |
| `email_service.py:71` | `max_age=3600` (Reset-Token-Gültigkeit) | OK, aber Dead-Code |
| `feedback_service.py:6` | `/opt/nerve/uploads/feedback` | Linux-Pfad hardcoded (Fallback wenn ENV nicht gesetzt). Dev auf Win/Mac → ENV nötig. |
| `feedback_service.py:7-8` | Extension + MIME Whitelist | OK |

---

## 9. Findings — Severity-sortiert

### HIGH

**H1. `cost_tracker._resolve_org_id_from_live_session()` ist Ghost — `ApiCostLog.org_id` ist IMMER NULL.**
- Location: `cost_tracker.py:42-48` (Reader), Writer: **keiner** in der Codebase
- Impact: Per-Org-Cost-Dashboard (`admin_dashboard.py:548-550` und Z.610) zeigt falsche (null) Werte. Multi-Tenant-Abrechnung pro Kunde unmöglich. Pre-Launch tragbar (Solo-Founder-Phase), bei ersten Early-Access-Kunden kritisch weil Ist-Kosten-Vergleich nicht pro-Org-aufteilbar.
- Recommendation: In `deepgram_service.py:351` (wo `ls.state['user_id']` geschrieben wird, gleicher `state_lock`-Block) zusätzlich `ls.state['org_id']` aus `User.org_id` setzen. **1-Zeilen-Fix**, macht den Ghost-Reader live.

**H2. `email_service.send_password_reset` / `make_reset_token` / `parse_reset_token` sind DEAD.**
- Location: `email_service.py:56-72` — 17 Zeilen Code, 0 Caller
- Impact: User ohne OAuth können ihr Passwort nicht selbst resetten. Launch-kritisch. Dokumentations-Lüge (Phase 04.7-05 hat "send_password_reset" als Deliverable abgehakt, aber nirgends verdrahtet).
- Recommendation: **Vor Launch** Route `/forgot-password` + `/reset-password/<token>` implementieren. Template, Form, Rate-Limit, AuditLog-Event `password_reset_requested` + `password_reset_completed`. Alternative: 17 Zeilen entfernen + als bekannten Gap dokumentieren.

**H3. Systematischer `user_id=None` bei 21/27 cost_tracker-Calls, Fallback unzuverlässig.**
- Locations: claude_service (14×), deepgram_service (1×), precall_service (2×), qa_pipeline (4×) — alle hardcoded `user_id=None`
- Fallback-Mechanik greift nur in aktiver Socket-Session via `ls.state['user_id']`. Für Precall (HTTP-Route) und QA-Pipeline (innerhalb analyse_loop, OK) inkonsistent. Bei nicht-Session-Calls: user_id=NULL oder **stale vom letzten User** (Multi-User-Horror bei Concurrency).
- Impact: Per-User-Cost-Dashboard (`admin_dashboard.py:610`) liefert für nicht-Session-Cost unvollständige Attribution. Pre-Launch OK, bei zweitem simultanen User kritisch.
- Recommendation: In allen Call-Sites wo bekannt ist wer der User ist (`g.user.id` in HTTP-Context, `ls.state.get('user_id')` unter Lock in Background-Threads), explizit übergeben. Wie `coaching_service.py` es bereits sauber macht (`user_id=user_id` Z.96). Duplikat-Aufwand: ~20 Zeilen.

**H4. DSGVO-Audit-Coverage hat 10+ Lücken (Art. 7, 15, 17, 20 teilweise/ganz ungedeckt).**
- Fehlende Audit-Actions: `register`/`signup`, `password_reset`, `account_delete`, `data_export`, `consent_change` (profile_update ist zu grob), `invitation_accepted`, `subscription_change`, `admin_edit`, `failed_login`, `admin_impersonate`.
- Impact: DPIA/AVV-Gespräche mit Kunden werden schwer. Breach-Forensik unvollständig. Bei ersten Kunden-Auditen sofort Rückfragen zu "wer hat was wann".
- Recommendation: Vor Early-Access Launch:
  1. `api_register` + `register` (via Invitation): `log_action(..., 'register', details={'method': ..., 'via_invitation': bool})`
  2. profile_update details-Feld: gegen `before/after`-Diff statt nur `{'name': ...}` erweitern. Insbesondere `consent_text`-Änderung separat loggen.
  3. Account-Deletion-Feature: zusammen mit neuer Route, Action `account_delete`.
  4. Failed-Login: in `_do_login` bei `return None, '...'` → `log_action(db, None, None, 'login_failed', details={'email_hash': ..., 'reason': 'invalid_pw'})` (Hash, nicht Email im Klartext).
  5. Alle Flask-Admin-Edits hooken: ModelView.on_model_change overriden, AuditLog schreiben.

### MEDIUM

**M1. FX-Rate-Fallback `0.92` hardcoded und stale.**
- Location: `cost_tracker.py:28`
- Aktueller EZB-USD→EUR ~0.89. Bei leerer ExchangeRate-Tabelle buchen wir ~3.4% zu hoch. Kein Warn-Log.
- Recommendation: Fallback auf `0.90` aktualisieren + `print("[CostTracker] WARN: no ExchangeRate row found, using static fallback")` ausgeben wenn Fallback greift. Besser: ExchangeRate-Seed-Job statt Code-Default.

**M2. Deepgram-Cost überberechnet durch Socket-Lifetime statt STT-Sekunden.**
- Location: `deepgram_service.py:249-253`
- `time.time() - opened` misst Socket-Open-Zeit. Deepgram bucht pro STT-verarbeiteter Audio-Sekunde. Bei Pausen/Muted-Mic zahlen wir im Model mehr als Deepgram uns berechnet.
- Impact: Cost-Dashboard zeigt immer **höhere** Deepgram-Kosten als Deepgram-Invoice → Invoice-Reconciliation schlägt fehl, wir denken wir haben ein Leck oder unser Modell ist falsch.
- Recommendation: Deepgram-SDK liefert im Close-Event die tatsächlich verarbeiteten `audio_seconds` (Metadata). Aus SDK-Event abgreifen statt Socket-Clock messen.

**M3. `feedback_service.create_feedback` — keine Rollback bei commit-Error.**
- Location: `feedback_service.py:34-45`
- `db.add + db.commit` ohne try/except. Bei Constraint-Violation propagiert Exception zu `routes/feedback.py:21-40` (nur finally, kein except) → 500 an User, kein AuditLog, kein Retry.
- Recommendation: try/except um commit, `db.rollback()` + `return None`-Sentinel, in Route `if fb is None: return jsonify({'error': 'db'}), 500` mit Logging.

**M4. `audit.py` — kein Retention-Policy / Archival-Strategie.**
- Location: übergreifend (audit_log Tabelle + Immutable-Trigger in app.py:1028-1038)
- Audit-Logs wachsen unbegrenzt. DSGVO Art. 5(1)(e) "Speicherbegrenzung" — ohne Policy tauchen bei jedem DPIA/AVV-Gespräch Fragen auf.
- Recommendation: Policy definieren (z.B. Login/Logout nach 2 Jahren → archivieren; Profile-Update/Session nach 7 Jahren → löschen). Cron-Job der Immutable-Trigger temporär droppt, prunt, Trigger wiederherstellt. Alternativ: separate `audit_log_archive`-Tabelle + INSERT-auf-Alter statt DELETE. Dokumentation in `04 Entscheidungen/NERVE DSGVO Analyse` verlinken.

**M5. Feedback vs. FeedbackEvent — Model-Parallelismus ohne Service-Abstraktion.**
- Location: `models.py:197` (FeedbackEvent) vs. `models.py:401` (Feedback)
- Zwei Feedback-Tabellen, `feedback_service` deckt nur eine ab. Direct-Insert von `FeedbackEvent` in `routes/app_routes.py:1287` ohne Validation, ohne Service.
- Recommendation: 
  - Option A (kurzfristig): FeedbackEvent → `feedback_service.create_quick_rating(user_id, session_log_id, stars, comment)` wrappen. 10 Zeilen, Konsistenz.
  - Option B (sauber): FeedbackEvent in Feedback mergen (Feedback hat bereits `rating` + `kategorie` Felder → FeedbackEvent ist redundant). Schema-Migration.

**M6. Email-Service: kein Resend-Region-Check im Code.**
- Location: `email_service.py:5-11`
- EU-Compliance hängt an Resend-Account-Setting (Dashboard). Code validiert nicht. Wenn jemand das Setting ändert → alle Mails laufen via US-Region, DSGVO-Verletzung.
- Recommendation: Boot-Time-Check: Resend-API abfragen `/account` oder fixed `RESEND_BASE_URL=https://api.resend.com/eu` (falls existiert). Alternative: nach .env.prod policy, `RESEND_BASE_URL` ist Pflicht, ohne → `raise RuntimeError`.

### LOW

**L1. `cost_tracker.py` — `itsdangerous`-Import indirekt nur über `email_service` (dead chain).**
- Location: `email_service.py:3`
- Wenn DEAD password-reset entfernt wird, kann `itsdangerous` aus requirements.txt raus. Leichte Dependency-Vereinfachung.

**L2. `audit.py` — `print` statt strukturiertes Logging.**
- Location: `audit.py:26`
- Vor Launch auf `logger.error` mit Sentry-Hook umstellen.

**L3. `feedback_service.UPLOAD_DIR` Linux-Pfad hardcoded als Fallback.**
- Location: `feedback_service.py:6`
- Dev-Pain auf Windows/Mac. ENV `FEEDBACK_UPLOAD_DIR` muss gesetzt sein — `.env.example` sollte das dokumentieren (Check).

**L4. `email_service` — keine Jinja-Templates, Inline-HTML.**
- Bei weiterer Mail wächst Duplikation. Jetzt (3 Mails) OK, bei Mail #5 refactor-Pflicht.

**L5. `context_tag='pip_stream'` ist Tag für DEAD function.**
- Location: `claude_service.py:787+790` (in dead `analysiere_mit_claude_streaming`)
- Cleanup-Kandidat synchron mit Welle-1-H2-Finding.

**L6. `_send` fehlender Boot-Test.**
- Location: `email_service.py:17-26`
- Keine Startup-Validierung dass Resend-API-Key gültig ist. Erster echter Send könnte 401 sein. Kein Health-Check-Endpoint. Akzeptabel für Solo-Pre-Launch.

**L7. `create_feedback` — kein Content-Check gegen SQL/Shell/Markdown-Injection im `text`-Feld.**
- Location: `feedback_service.py:31-46`
- Text geht als-is in DB, wird in Admin-View angezeigt (Flask-Admin escaped HTML per Default, aber falls custom-rendern → XSS-Risk). 
- Recommendation: optional `html.escape` oder `bleach.clean` vor Persist. Aktuell wird Text nur in Admin angezeigt, kein User-facing → LOW.

---

## 10. Cross-Module-Hypothesen für Master-Audit

1. **ApiRate-Seed-Konsistenz:** Das Model-Lookup `ApiRate.filter_by(provider, model, unit_type, active=True)` scheitert silent wenn kein Seed vorhanden. **Master-Audit muss prüfen:**
   - Gibt es einen Seed-Script / Migration der ApiRate mit den 10 distinkten Kombinationen füllt? (`anthropic/haiku-4-5/per_1k_input_tokens`, `anthropic/haiku-4-5/per_1k_output_tokens`, `anthropic/sonnet-4/per_1k_input_tokens`, `anthropic/sonnet-4/per_1k_output_tokens`, `deepgram/nova-2/per_minute`, `elevenlabs/multilingual-v2/per_1k_chars`)
   - Ist `model='sonnet-4'` in ApiRate-Seed, oder muss es `sonnet-4-6` heißen (Code nutzt `claude-sonnet-4-6` als Model, `cost_tracker`-Call nutzt `'sonnet-4'`)? Namens-Mismatch → alle Coaching-Costs werden silent geskippt (`no active ApiRate`).

2. **ExchangeRate-Seed + Cron:** Gibt es einen täglichen Cron der `ExchangeRate` aus Frankfurter-API aktualisiert (laut PROJECT: Phase 04.7.2 D-05)? Wenn nicht → Fallback `0.92` wird systematisch genutzt → alle USD-Kosten 3% zu hoch gebucht. **Master-Audit: grep Cron/Scheduler + Frankfurter-API-Calls.**

3. **`Feedback` → Coach-Pipeline:** Soll Feedback in Coach-Insights einfließen (LearningCard-Generierung)? Aktuell nicht verdrahtet. Falls Roadmap das vorsieht → Cross-Check gegen `coaching_service.py` + `coach-Modul`-Phase-Planung.

4. **User-Deletion-Flow:** Existiert irgendwo eine Account-Delete-Route? Falls nicht → DSGVO-Launch-Blocker. **Master-Audit: grep nach delete_user / Route `/account/delete` / User-Deaktivierung (`User.aktiv = False` genügt nicht Art. 17).**

5. **AuditLog-Trigger vs. Retention-Cleanup:** Der Immutable-Trigger (app.py:1028) verhindert DELETE. Jede Retention-Policy braucht Trigger-Bypass. **Master-Audit sollte Pattern für Controlled-Delete vorschlagen:** 
   - Option A: Cron-Script setzt Pragma, droppt Trigger, DELETE WHERE created_at < threshold, recreate Trigger.
   - Option B: Separate Archive-Tabelle `audit_log_archive` ohne Trigger, INSERT-Move + DELETE-via-temp-drop.
   - Option C: Trigger erlaubt DELETE wenn `current_session_var('retention_job') = 1`.

6. **`send_password_reset`-DEAD:** Synchronisieren mit Welle 1 / weiteren Wellen ob irgendwo im Frontend ein "Passwort vergessen?"-Link existiert der auf eine nicht-existente Route zielt → UX-Bug + Backend-Gap.

7. **`ls.state['org_id']`-Writer:** **Master-Audit hat Chance den Fix aus H1 in `deepgram_service.py` start_live_session zu propagieren — 1 Zeile.** Synchronisieren mit Welle 1 (ki_logik hat ebenfalls org_id-Reads laut Audit-Report Welle 1 M3).

---

## 11. Zusammenfassung — Welle-Vergleich

| Kategorie | Welle 1 (claude_service + live_session) | Welle 2 (audit + cost + feedback + email) |
|---|---|---|
| DEAD-Funktionen | 2 (`_build_system_prompt`, `analysiere_mit_claude_streaming`) | 3 (`send_password_reset`, `make_reset_token`, `parse_reset_token`) |
| Zombie-Funktionen | 1 (`_get_erfolgsquoten`) | 0 |
| Ghost-Reader | - | **1 bestätigt** (`ls.state['org_id']`) |
| Orphan Writer | - | 0 (ls-State-Seite sauber außer Ghost) |
| Silent-Failure-Density | 7 (claude_service) | 7 (sum 4 files) |
| Hardcoded Werte | 9× Model-Name + 2 Prompts | FX-Fallback, Linux-UPLOAD_DIR, Dashboard-URL |
| DSGVO-Lücken | ✅ Datenflüsse sauber (cold_call anonymisiert) | ❌ **10+ ungedeckte Audit-Actions** (Art. 7/15/17/20) |
| Doku-Drift | ANALYSE_INTERVALL + Streaming-Status | Phase 04.7-05 "send_password_reset verdrahtet" ist Lüge |

**Mein Gefühl nach zwei Wellen:** Das Pattern ist konsistent — Phase-Summaries werden abgehakt ohne Live-Path-Verifikation. Nudelcode entsteht durch Plan-Execute-Closeout-Zyklen, in denen niemand nach 2 Phasen zurückschaut ob das Neue noch ruft oder das Alte noch gerufen wird. H4 (DSGVO-Coverage) ist der einzige **neue-in-Welle-2-Launch-Blocker** den Welle 1 nicht hatte — alles andere ist technical-debt-kategorisch.

---

**Meta:** Audit basiert auf kompletter Lesung der 4 Dateien (266 Zeilen), Call-Graph-Grep über gesamte Codebase, Cross-Check gegen `database/models.py` (Schema), `live_session.py`+`deepgram_service.py` (Writer-Scan), Welle-1-Report (Konsistenz). Keine Assumptions — jeder Ghost/Dead-Claim ist mit Zeilenreferenz + Grep-Null-Treffer verifiziert.
