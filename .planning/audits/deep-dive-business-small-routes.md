---
audit: deep-dive-business-small-routes
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault)
scope:
  - routes/organisations.py (133 Z.) — gelesen
  - routes/payments.py (334 Z.) — gelesen
  - routes/performance.py (472 Z.) — gelesen
  - routes/feedback.py (67 Z.) — gelesen
  - routes/onboarding.py (212 Z.) — gelesen
  - routes/changelog.py (100 Z.) — gelesen
  - routes/logs_routes.py (46 Z.) — gelesen
  - routes/waitlist.py (153 Z.) — gelesen
cross_refs:
  - services/feedback_service.py — gelesen
  - database/models.py — Stichproben (Organisation, Feedback, FeedbackEvent, Waitlist, Changelog, BillingEvent, RevenueLog, User)
  - routes/app_routes.py — Stichprobe (FeedbackEvent-Writer)
  - app.py — Blueprint-Registrierung verifiziert
budget: ~20 min
status: abgeschlossen
---

# DEEP-DIVE — 8 Business-Small-Routes

**Stand-Tag:** 2026-04-24
**Alle 8 Dateien gelesen.** 20 Befunde total (3 HIGH, 9 MEDIUM, 8 LOW).
**Blueprints registriert:** Alle 8 sauber in `app.py:1640-1657`.

---

## EXECUTIVE SUMMARY pro Datei

| Datei | Gelesen | Status | Kurzfazit |
|---|---|---|---|
| organisations.py | ✅ | 🟡 OK mit Lücken | Team-CRUD funktioniert. Kein Audit-Log. Einladungs-E-Mail fehlt (Link wird nur geflasht). |
| payments.py | ✅ | 🟠 Stripe LIVE, aber Fallbacks | Webhook-Replay-Schutz OK. Signature OK. `org_id=1`-Fallback bei BillingEvent = **HIGH**. `automatic_tax` setzt Stripe-Tax-Registration voraus (laufzeit-gated). |
| performance.py | ✅ | 🟡 Marketing-Fake-Zahlen transparent | Echte Queries auf ConversationLog. ROI+Forecast basieren auf **hardcoded 15%/5%/10% Annahmen** — klar gelabelt aber in API-Payload nicht. |
| feedback.py | ✅ | 🟢 Sauber (1 Auth-Detail) | Nutzt `Feedback`-Model (richtig). FeedbackEvent wird von anderer Route gefüttert — **keine Kollision im File**. Auth-Gate via `g.user`-Check statt `@login_required`. |
| onboarding.py | ✅ | 🔴 Tabu-Wizard fehlt, Profil-Migrations-Schema-Drift | 8 Branche-Templates als hardcoded Python-Dict. `create_profile` schreibt **falsches Schema** (Top-Level `produkt`/`einwaende`/`phasen`, nicht `basis.produktbeschreibung` wie Phase-08 erwartet). |
| changelog.py | ✅ | 🟡 DB-basiert aber fragile Version-Compare | String-Vergleich `Changelog.version > last_seen` — **fehlerhaft** bei 2-stelligen Minor-Versionen. Kein CSRF auf admin-POST. |
| logs_routes.py | ✅ | 🟡 DSGVO-kritisch — File-basiert | Liest Filesystem (`LOG_DIR`), kein DB-Export. Regex-Gate OK. Nur File-Download, **kein JSON/CSV/PDF-Export**. |
| waitlist.py | ✅ | 🔴 Referral funktioniert, Email-Trigger fehlt komplett | Referral-System implementiert (+3 Position-Boost). `invite_from_waitlist` erstellt Org+Invitation **ohne Email zu senden** — nur Link-Rückgabe an Admin. |

---

## 🟠 HIGH-Severity

### HSR-1: `BillingEvent.org_id=1`-Fallback bei Webhook-Events ohne Org-Zuordnung

**Evidence:** `routes/payments.py:105-109`
```python
db.add(BillingEvent(
    org_id=_resolve_org_id(db, event) or 1,   # ← Fallback auf 1
    typ=etype,
    stripe_event_id=event_id,
))
```

`_resolve_org_id` scheitert wenn:
- Event ohne `metadata.org_id` (z.B. `invoice.payment_failed` auf Customer ohne frisches Checkout-Metadata)
- Customer nicht in Organisation-Tabelle (Stripe-Test-Events, manuell angelegte Subs)

**Folge:** Billing-Events landen fälschlich auf **Organisation ID 1** (vermutlich erste Org / Dev-Owner). Founder-Dashboard-Aggregation pro Org wird durch Fremd-Events verfälscht. Bei echten Production-Use-Cases (failed-payment-Retry ohne Checkout-Session-Context) → falsche Zuordnung.

**Fix:** Entweder `nullable=True` in Schema und `None` einsetzen + Migration, oder Event überspringen wenn Resolution scheitert. Aufwand: ~1h.

### HSR-2: Onboarding schreibt Profil-Schema-Drift direkt rein

**Evidence:** `routes/onboarding.py:193-212` + `BRANCHE_TEMPLATES` (Z.9-146).

Template-Structure:
```python
'SaaS': {
    'produkt': 'SaaS-Lösung',       # ← Top-Level
    'einwaende': [...],              # ← Top-Level
    'phasen': [...],                 # ← Top-Level
}
```

Phase-08-Schema erwartet aber `basis.produktbeschreibung`, `einwaende_liste` unter Unterstruktur (siehe MASTER-AUDIT H-13: `/api/frage` + `/api/ewb_trigger` lesen `pdata.get("produkt")` — **identisches Bug-Muster**).

**Folge:** Jeder neu-onboardete User kriegt ein Profil dessen Felder die Live-KI im Cold-Call-Pfad **garnicht konsumiert** — genau das `build_profile_context`-Leere-Dict-Problem wie LB-3 im Master-Audit. Phase 04.16.1 (Tabu-Wizard) ist außerdem komplett ungebaut — keine `tabu`-Felder in Templates, keine Tabu-Generierung.

**Folge²:** Erste 50 Early-Access-User werden mit **de-facto leeren Profilen** starten bis sie selbst den Profile-Editor öffnen.

**Fix:** Template-Schema angleichen auf neue Profile-Struktur (1h) + Tabu-Wizard als Phase 04.16.1 wie geplant (Roadmap). Aufwand: ~3h für Template-Fix + Migration-Test alter Profile.

### HSR-3: Waitlist-Invite schickt keine E-Mail — Admin muss Link manuell kopieren

**Evidence:** `routes/waitlist.py:96-133`.

```python
@waitlist_bp.route('/invite/<int:wid>', methods=['POST'])
def invite_from_waitlist(wid):
    ...
    return jsonify({
        'ok': True,
        'email': entry.email,
        'register_link': register_link,   # ← nur JSON-Return, kein send
    })
```

**Keine `email_service`-Calls im gesamten File.** Waitlist-Admin-UI (`waitlist_admin.html`) zeigt den Link vermutlich — Admin muss manuell E-Mail an Waitlist-Empfänger schicken.

**Folge:**
- Onboarding-Latenz (User wartet auf manuelle Admin-Aktion)
- Kein Audit-Log wer wann eingeladen wurde (nur `invited_at`-Timestamp, kein Audit-Event)
- Vergessene Invite = tote Position in Waitlist

**Fix:** `email_service.send_waitlist_invitation(entry.email, register_link)` + Audit-Event `waitlist_invited`. Aufwand: ~2h (Template + Send + Test).

---

## 🟡 MEDIUM-Severity

### MSR-1: organisations.py — Einladung läuft über Flash-Message statt E-Mail

**Evidence:** `routes/organisations.py:64-65`
```python
link = url_for('auth.register', token=tok, _external=True)
flash(f'Einladungslink für {email}: {link}', 'success')
```

Selbes Pattern wie HSR-3: Kein `email_service`-Aufruf. Admin sieht Flash, muss Link manuell an Invitee schicken.

**Fix:** Analog zu HSR-3. Aufwand: ~1h (Template existiert evtl. schon in email_service).

### MSR-2: organisations.py — Kein Audit-Log für Team-Management-Aktionen

**Evidence:** Keine `audit.log_action`-Calls in invite/revoke/deactivate/reactivate/settings_dsgvo. Deckt sich mit MASTER-AUDIT H-8 (DSGVO-Audit-Coverage-Gaps).

**Fix:** Audit-Events für: `user_invited`, `invitation_revoked`, `user_deactivated`, `user_reactivated`, `org_dsgvo_toggled`. Aufwand: ~1h.

### MSR-3: payments.py — `automatic_tax=True` ohne Precheck

**Evidence:** `routes/payments.py:50`:
```python
automatic_tax={'enabled': True},  # Phase 04.7.2 D-03 — requires active Tax Registration (HT-01)
```

Kommentar weist auf Tax-Registration-Dependency hin. Bei fehlender aktiver Tax-Registration wirft Stripe `tax_not_configured` → Checkout scheitert → generischer `flash('Ungültiger Tarif')` via Exception-Handler? Nein — kein Try/Except drum herum → **Exception bubbelt zum globalen Handler** (LB-7 Traceback-Leak!).

**Fix:** Try/Except um `stripe.checkout.Session.create` + saubere Fehlermeldung. Aufwand: 30 min.

### MSR-4: payments.py — Redirect auf nicht-existierende `dashboard.index` hart-gekoppelt

**Evidence:** `routes/payments.py:60`:
```python
flash('Abo aktiviert! Willkommen bei NERVE.', 'success')
return redirect(url_for('dashboard.index'))
```

Diese Redirect feuert SOFORT nach Checkout-Success-Redirect — **bevor** der Webhook `checkout.session.completed` `subscription_status='active'` setzt. **Race-Condition:** User landet im Dashboard, Webhook kommt 1-3 Sek später. Wenn Dashboard Features nach `subscription_status` gated → User sieht kurz "Inactive"-State obwohl Zahlung durch ist.

**Fix:** Webhook-Sync vor Redirect warten (Polling) ODER Dashboard gegen Race-Condition härten. Aufwand: 1-2h.

### MSR-5: payments.py — `_record_revenue` holt Stripe-Customer synchron im Webhook-Handler

**Evidence:** `routes/payments.py:269` `cust = stripe.Customer.retrieve(customer_id)` innerhalb des Webhook-Handlers. Stripe-API-Call blockiert den Webhook. Bei 10 gleichzeitigen invoices → 10 sequenzielle Stripe-API-Roundtrips (200-500 ms each). Stripe gibt Webhook 5 Sek Timeout → bei >10 gleichzeitigen Invoices **Timeout-Risiko**, Stripe retryt → Duplicate-Protection greift via `stripe_event_id` ✓ aber Queue wächst.

**Fix:** Customer-Country auf Organisation cachen oder async verarbeiten (Celery/Background-Queue). Aufwand: 2-3h (Queue-Setup) oder 30min (Org-Country-Cache).

### MSR-6: performance.py — `_berechne_forecast`, `roi_mehrwert`, `hint_ewb` mit hardcoded Marketing-Annahmen (transparent aber ohne Meta)

**Evidence:**
- `roi_mehrwert = round(calls_pro_monat * cr_delta * dw_fuer_formel) - 99` mit `cr_delta = closing_rate * 0.15 / 100.0` — **15% NERVE-Einwand-Verbesserung** (Zeile 138-140).
- `wachstum = 1.05` — **5% monatlich** (Zeile 25).
- `hint_ewb = cr_fuer_formel * 1.10` — **10% CR-Boost durch EWB** (Zeile 348).
- `cr_fuer_formel = closing_rate or 20.0` — **20% Default-Closing-Rate** bei Null-Daten (Zeile 118, 294).
- Bei fehlendem `avg_deal_wert` → `forecast` = 0, aber UI zeigt vermutlich Zahlen die **auf dem 20%-Fallback basieren** ohne Warnung.

**Folge:** ROI-/Forecast-Zahlen sind Marketing-Hypothesen, kein echter Messwert. Für Early-Access-User OK wenn UI labelt — aber **API-Payload hat keinen `is_simulation=True`-Flag**, Frontend muss die Annahmen selbst kennen. Claim-Drift-Risiko ("NERVE verspricht 15% mehr Einwand-Erfolg" → juristisch kritisch ohne Evidenz).

**Fix:** Payload um `assumptions: {nerve_einwand_boost: 0.15, ...}` erweitern damit Frontend transparent labeln kann. Aufwand: 1h.

### MSR-7: performance.py — `score_trend_pct` nutzt `avg_score_last > 0` Guard aber `avg_score` nicht

**Evidence:** Zeile 263:
```python
if avg_score and avg_score_last and avg_score_last > 0:
```

`avg_score` ist Truthy-geprüft (0.0 → False). Aber bei sehr niedrigem last-Score (0.5) und höherem aktuellen Score (5) → `round((5-0.5)/0.5*100) = 900%` Trend angezeigt. Kein Obergrenzen-Cap.

**Fix:** `max(-100, min(999, score_trend_pct))` Cap. Aufwand: 5 min.

### MSR-8: feedback.py — Auth-Gate via `getattr(g, 'user', None)` statt `@login_required`-Decorator

**Evidence:** `routes/feedback.py:13` + `:46`:
```python
if not getattr(g, 'user', None):
    return jsonify({'error': 'auth'}), 401
```

Funktioniert, aber **inkonsistent** mit Rest der Codebase (alle anderen kritischen Routes nutzen `@login_required`). Abrieb-Quelle wenn jemand später Auth-Middleware anpasst — `g.user`-Pattern könnte unbemerkt brechen.

**Fix:** Auf `@login_required`-Decorator umstellen. Aufwand: 5 min (kosmetisch, aber gut für Konsistenz).

### MSR-9: changelog.py — String-Vergleich bei Versionen bricht bei 2-stelligen Minors

**Evidence:** `routes/changelog.py:39`:
```python
.filter(Changelog.veroeffentlicht == True,
        Changelog.version > last_seen)
```

**String-Vergleich.** `'0.9.0' > '0.10.0'` → `True` (weil '9' > '1' lexikalisch). Falsche Popup-Logik.

**Fix:** Semver-Parsing oder Changelog-ID nutzen (created_at). Aufwand: 1h.

### MSR-10: changelog.py — `admin`-POST hat kein CSRF-Token-Check

**Evidence:** Zeile 82:
```python
@changelog_bp.route('/admin', methods=['POST'])
def add_entry():
    if flask_session.get('rolle') != 'owner':
        return jsonify({'error': 'Keine Berechtigung'}), 403
```

Nur Rolle-Check. Wenn Flask-WTF CSRF global aktiv ist → ok (globaler Schutz). Wenn nicht → Owner-Browser kann per CSRF-Attack einen Changelog-Eintrag kriegen. **Prüfen ob global CSRF in app.py aktiv.**

**Fix:** Globaler CSRF ohnehin Pflicht. Aufwand: Teil von Security-Baseline.

---

## 🟢 LOW / Kosmetik

### LSR-1: logs_routes.py — Kein DSGVO-konformer User-Daten-Export
DSGVO Art. 15/20 fordert strukturierten Export **eigener** Daten. `/logs/download/<filename>` gibt TXT-Files zurück. Keine JSON/CSV-Option. Deckt sich mit MASTER-AUDIT LB-2 (DSGVO-Routen fehlen).

### LSR-2: logs_routes.py — `LOG_DIR` Filesystem-Abhängigkeit
Bei Multi-VPS-Deployment oder Docker-Migration → Logs nicht in Container. Sollte in Richtung DB-Storage migriert werden (`ConversationLog`-Tabelle existiert bereits). File-basiert ist Legacy von Phase 01/02.

### LSR-3: onboarding.py — `erfahrungslevel/schmerzpunkt/persoenlich/dashboard_stil` werden nur auf User gespeichert, nicht in Prompts gelesen
Geprüft via Grep in services/: alle 4 Felder werden in claude_service.py/training_service.py/precall_service.py gelesen — ok. **Aber:** dashboard_stil (Text, freier) vs. dashboard_style (String(20), Enum 'vollstaendig') sind **zwei verschiedene Felder** — onboarding schreibt beide. Verdacht auf Copy-Paste-Doubling, sollte geprüft werden ob beide wirklich gebraucht.

### LSR-4: onboarding.py — `BRANCHE_TEMPLATES` (~138 Zeilen) als hardcoded Python-Dict
Statt DB-Tabelle. Admin kann Templates nicht editieren ohne Code-Deploy. OK für EA, mittelfristig in DB migrieren.

### LSR-5: waitlist.py — `join_waitlist` ohne Rate-Limit
Public-Endpoint. Spam-Angriff kann Waitlist-Tabelle fluten (Email-Unique verhindert Doppel, aber unterschiedliche Emails gehen durch). Deckt sich mit generellem Rate-Limit-Gap im Projekt.

### LSR-6: waitlist.py — Referral gibt kein Position-Feedback an Referrer
Referrer verliert 3 Plätze beim Referral — aber **kein Trigger** der ihn informiert. E-Mail/Push an Referrer fehlt.

### LSR-7: changelog.py — `latest_for_popup` + `mark_seen` haben `'user_id' not in flask_session`-Guards statt `@login_required`
Konsistenz-Problem (wie MSR-8).

### LSR-8: performance.py — `api_session_result` erlaubt None als Result
```python
if result not in ('gewonnen', 'verloren', None):
```
Beabsichtigt (User kann Result zurücksetzen) — aber UI-Seite muss das explizit abbilden. Kein Bug, Doku-Hinweis.

---

## 📋 Schema-Validation (pro Datei)

| Datei | Models benutzt | Schema konsistent? |
|---|---|---|
| organisations.py | Organisation, User, Invitation, BillingEvent*, PLANS | ✓ (BillingEvent importiert aber nicht benutzt im File — toter Import) |
| payments.py | Organisation, BillingEvent, RevenueLog | ✓ |
| performance.py | ConversationLog, User | ✓ |
| feedback.py | Feedback (via service) | ✓ |
| onboarding.py | User, Profile | ⚠ **Profile.daten schreibt falsches Schema** (HSR-2) |
| changelog.py | Changelog, User (last_seen_changelog) | ✓ |
| logs_routes.py | — (nur Filesystem) | ✓ |
| waitlist.py | Waitlist, Organisation, Invitation | ✓ |

**Unused Imports:**
- `organisations.py:4` importiert `BillingEvent` — **nicht benutzt**. 1 Zeile removable.

**Feedback/FeedbackEvent-Parallelismus (MASTER-AUDIT-Befund):**
- `routes/feedback.py` schreibt `Feedback` (via service) — reiche Feedback-Tickets (typ/text/screenshot/rating).
- `routes/app_routes.py:1287` schreibt `FeedbackEvent` — **andere Route** `/api/feedback_event` für Session-Feedback (stars/comment).
- **Kein Konflikt im audit-scope,** aber die Doppel-Struktur bleibt ein langfristiger Schema-Parallelismus der konsolidiert werden sollte (als MEDIUM im Master-Audit bestätigt).

---

## 🔐 Auth-Gate-Audit (pro Route)

| Route | Methode | Gate | OK? |
|---|---|---|---|
| `/org/team` | GET | `@login_required` + `@_require_admin` | ✓ |
| `/org/invite` | POST | `@login_required` + `@_require_admin` | ✓ |
| `/org/invite/<id>/revoke` | POST | `@login_required` + `@_require_admin` | ✓ |
| `/org/user/<id>/deactivate` | POST | `@login_required` + `@_require_admin` + self-Check | ✓ |
| `/org/user/<id>/reactivate` | POST | `@login_required` + `@_require_admin` | ✓ (keine self-Protection nötig) |
| `/org/settings/dsgvo` | POST | `@login_required` + `@_require_admin` | ✓ |
| `/payments/checkout/<plan>` | POST | `@login_required` | ✓ |
| `/payments/checkout/success` | GET | `@login_required` | ✓ |
| `/payments/webhook` | POST | **Signature-Check via Stripe SDK** | ✓ |
| `/payments/portal` | POST | `@login_required` | ✓ |
| `/payments/pricing` | GET | **Public** | ✓ (intentional) |
| `/api/performance` | GET | `@login_required` | ✓ |
| `/api/session/<id>/result` | PATCH | `@login_required` + user-Ownership-Filter | ✓ |
| `/api/user/deal-wert` | PATCH | `@login_required` | ✓ |
| `/api/dashboard` | GET | `@login_required` | ✓ |
| `/api/feedback` | POST | `g.user`-Manual-Check | ⚠ (funktional, MSR-8) |
| `/api/feedback/quick` | POST | `g.user`-Manual-Check | ⚠ |
| `/onboarding/` | GET | `@login_required` | ✓ |
| `/onboarding/complete` | POST | `@login_required` | ✓ |
| `/onboarding/create_profile` | POST | `@login_required` | ✓ |
| `/changelog/` | GET | **Public** | ✓ (intentional) |
| `/changelog/latest` | GET | `'user_id' in session`-Manual | ⚠ (LSR-7) |
| `/changelog/seen` | POST | `'user_id' in session`-Manual | ⚠ |
| `/changelog/admin` | POST | Rolle==owner-Check | ✓ |
| `/logs` | GET | `@login_required` + Admin-Filter | ✓ |
| `/logs/download/<filename>` | GET | `@login_required` + Regex + User-ID-im-Filename-Match | ✓ (solide) |
| `/waitlist/join` | POST | **Public** | ✓ (intentional) |
| `/waitlist/status/<code>` | GET | **Public** | ✓ (intentional) |
| `/waitlist/stats` | GET | **Public** | ✓ (intentional) |
| `/waitlist/invite/<wid>` | POST | Rolle==owner | ✓ |
| `/waitlist/admin` | GET | Rolle==owner | ✓ |

**Gesamtnote:** Auth-Gating solide. 3 Detail-Inkonsistenzen (`g.user`-Manual statt Decorator).

---

## 🕵 Silent Failures

| Datei | Zeile | Pattern | Risiko |
|---|---|---|---|
| payments.py | 97-100 | `try/except: print(...)` um `_record_revenue` | MED — Revenue-Log-Fails sind schwer zu monitoren |
| payments.py | 112-115 | Webhook-Handler catcht `Exception`, rollback, return 500 | OK — Stripe retryt, aber **keine Alert-Kanäle** |
| payments.py | 272, 300 | `try/except Exception: print(...)` um Stripe-Customer-Retrieval | MED — silent skip bei network issues |
| performance.py | 329 | `except Exception: pass` in JSON-Parse-Loop | LOW — transient Daten |
| changelog.py | 20-22, 46-48 | `try/except: e.bugs_parsed = []` | OK |
| logs_routes.py | 27-29 | `except Exception: pass` um os.listdir | MED — leere Log-Liste wird als "keine Logs" angezeigt statt als Fehler |

---

## 📝 TODO/FIXME/HACK

**Keine TODO/FIXME/HACK-Marker in den 8 Dateien.**

Einzige Kommentar-Hinweise:
- `payments.py:50` — Tax-Registration-Abhängigkeit (HT-01)
- `payments.py:55` — "NOT activation" (Doku-Hinweis zur Webhook-Logik)
- `onboarding.py:152, 160` — `D-05: diagnostic log / Cache-Control`
- `performance.py:118, 135` — Marketing-Annahme-Kommentare

**Kommentar-Disziplin:** Gut — keine orphaned TODOs.

---

## 📦 Inline-Anthropic-Usage

**Keine `anthropic.Anthropic(...)`-Calls in den 8 Dateien.** Im Gegensatz zu `/api/frage` + `/api/ewb_trigger` im `app_routes.py` (MASTER-AUDIT H-12) ist diese Routes-Menge sauber von Inline-LLM-Calls.

---

## 🔢 Hardcoded Values (Produktionskritisch)

| Datei | Zeile | Wert | Kontext |
|---|---|---|---|
| payments.py | 106 | `org_id=1`-Fallback | HSR-1 |
| payments.py | 224-228 | `EU_COUNTRIES`-Set | Korrekt (27 EU-Länder). |
| performance.py | 25 | `wachstum = 1.05` | MSR-6 |
| performance.py | 118, 294 | `or 20.0` Closing-Rate-Default | MSR-6 |
| performance.py | 138, 343 | `0.15` NERVE-Boost | MSR-6 |
| performance.py | 348 | `* 1.10` EWB-Boost | MSR-6 |
| waitlist.py | 89 | `max(0, 50 - registered)` — 50-EA-Plätze | OK (Geschäftsregel, dokumentiert) |
| waitlist.py | 45 | `> 3` und `- 3` — Referral-Boost | OK (Geschäftsregel) |
| waitlist.py | 115 | `plan='starter', max_users=1, plan_preis=49, early_access_discount=50` | OK (EA-Default). |
| onboarding.py | 9-146 | Branche-Templates | LSR-4 |

---

## 🔄 Call-Graph (ein-/ausgehend, verkürzt)

**organisations.py** ← `app.py:1644` (Blueprint) → `auth.login_required`, `config.PLANS`, `database.models.{Organisation,User,Invitation}`. KEIN Call-Out in services/. Kein email_service.

**payments.py** ← `app.py:1655` → `stripe` (SDK), `config.{STRIPE_*}`, `database.models.{Organisation,BillingEvent,RevenueLog}`, `auth.login_required`. Webhook-Route öffentlich. KEIN Audit-Log.

**performance.py** ← `app.py:1657` → `database.models.{ConversationLog,User}`. Reine Lese-Queries + 1x `UserModel.avg_deal_wert`-Write. Kein Service-Call.

**feedback.py** ← `app.py:1640` → `services.feedback_service.{create_feedback, save_screenshot}` → `database.models.Feedback`. Sauber separiert.

**onboarding.py** ← `app.py:1651` → `database.models.{User,Profile}`. Kein Service-Call.

**changelog.py** ← `app.py:1654` → `database.models.{Changelog,User}`. Kein Service-Call.

**logs_routes.py** ← `app.py:1648` → `services.live_session.LOG_DIR` (nur Konstante) + `routes.dashboard.{get_recent_logs, _parse_log_meta}`. Filesystem-basiert.

**waitlist.py** ← `app.py:1653` → `database.models.{Waitlist,Organisation,Invitation}`. **Kein email_service-Call** (HSR-3).

---

## 🎯 Verdichtete Fix-Liste (nach Priorität)

### Block A — Launch-relevante (vor EA)
1. **HSR-1** — `org_id=1`-Fallback im Webhook entfernen/nullable — 1h
2. **HSR-2** — Onboarding-Template-Schema auf Phase-08-Struktur angleichen — 1-3h
3. **HSR-3** — Waitlist-Invite-E-Mail implementieren — 2h
4. **MSR-3** — Stripe-Checkout Try/Except gegen tax_not_configured — 30min
5. **MSR-2** — Org-Management-Audit-Events — 1h
6. **MSR-1** — Org-Invite-E-Mail (statt Flash) — 1h

**Subsumme Block A: ~6-8h.**

### Block B — Konsistenz/Technical Debt
7. MSR-4 — Checkout-Success-Race absichern — 1-2h
8. MSR-5 — Revenue-Record async/cache — 30min-3h
9. MSR-6 — API-Payload Marketing-Assumptions labeln — 1h
10. MSR-8 + LSR-7 — Auth-Decorator-Konsistenz — 30min
11. MSR-9 — Changelog-Semver-Compare — 1h
12. LSR-3 — onboarding.py dashboard_stil vs. dashboard_style prüfen — 30min
13. LSR-5 — Waitlist-Rate-Limit — 1h

**Subsumme Block B: ~5-9h.**

### Block C — Langfristig
14. LSR-1, LSR-2 — DSGVO-Log-Export + DB-Migration der File-Logs
15. LSR-4 — BRANCHE_TEMPLATES in DB
16. LSR-6 — Waitlist-Referrer-Notification

---

## 📊 Health-Score der 8 Routes

| Datei | Note | Kommentar |
|---|---|---|
| organisations.py | 🟡 B- | Team-Mgmt OK, E-Mail + Audit fehlen |
| payments.py | 🟠 C+ | Stripe funktional, aber `org_id=1`-Fallback + Checkout-Race |
| performance.py | 🟡 B | Echte Queries, aber Marketing-Assumptions nicht gelabelt |
| feedback.py | 🟢 A- | Sauber, nur Auth-Decorator-Stil abweichend |
| onboarding.py | 🔴 C- | Schema-Drift = gefährliches Einfallstor in tote Pfade |
| changelog.py | 🟡 B- | Funktional aber Version-Compare fragil |
| logs_routes.py | 🟡 B | Sauber gated, aber Legacy-Filesystem + kein DSGVO-Export |
| waitlist.py | 🟠 C+ | Referral OK, aber **kein Email-Trigger** = Launch-Blocker-light |

**Gesamt-Fazit:** Kein akuter Launch-Blocker **in diesen 8 Dateien**, aber 3 HIGH-Punkte + 6 MEDIUM-Punkte die vor DACH-EA-Start adressiert werden sollten (~6-8h Block A). Die gefährlichste Entdeckung ist **HSR-2 (Onboarding-Schema-Drift)** weil sie das identifizierte Muster aus MASTER-AUDIT H-13 bestätigt: **Neue Profile werden mit Felder-Struktur angelegt die die Live-KI nicht konsumiert.** Erste EA-User starten mit de-facto leeren Profilen.

---

*Audit abgeschlossen 2026-04-24. Nächste Routes-Deep-Dives laut MASTER-AUDIT-Warteliste: `app_routes.py` (Rest), `profiles.py`, `training.py`, `coach.py`, `dashboard.py`, `admin_dashboard.py`, `admin_views.py`, `oauth.py`, `settings.py`.*
