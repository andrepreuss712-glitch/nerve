---
audit: Deep-Dive Auth + OAuth + Settings
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault, Welle 3 Retry)
scope:
  - routes/auth.py (287 Z., Verifikation + Tiefencheck)
  - routes/oauth.py (241 Z., Erstscann)
  - routes/settings.py (223 Z., Erstscann)
kontext:
  - MASTER-AUDIT 2026-04-24 (LB-1 Password-Reset dead bereits bestaetigt)
  - services/audit.log_action Signatur
  - database/models.py (User + Organisation)
  - app.py Session-Config
---

# Deep-Dive Auth / OAuth / Settings

**Stand:** 2026-04-24, Welle 3
**Status:** 3 Dateien (751 Z. total) komplett gelesen + gegengeprueft gegen Models/Config/services/audit.

---

## TL;DR

Die drei Dateien sind **deutlich gefaehrlicher** als LB-1 allein suggeriert. Zusaetzlich zu Password-Reset-Dead finden sich:

- **1 neuer Launch-Blocker-Kandidat (LB-9):** **Null CSRF-Protection** auf saemtlichen state-changing POSTs — Login, Register, Settings (Plan-Kuendigung, Account-Loeschung, Billing), OAuth-Callback-Fluesse. Flask-WTF/CSRFProtect ist nicht registriert. Jede eingeloggte Session kann durch boeswilligen Link auf externer Seite zwangs-gekuendigt oder zwangs-geloescht werden.
- **1 neuer Launch-Blocker-Kandidat (LB-10):** **Session-Cookie-Hardening fehlt komplett** — kein `SESSION_COOKIE_SECURE`, kein `SESSION_COOKIE_HTTPONLY`, kein `SESSION_COOKIE_SAMESITE`, kein `PERMANENT_SESSION_LIFETIME` → Session-Cookies laufen standardmaessig **31 Tage**, sind per JS auslesbar, reisen ueber HTTP, koennen cross-site mitgeschickt werden.
- **Password-Reset Chain bestaetigt tot** (MASTER-AUDIT LB-1): Grep `password_reset|reset_token|make_reset|parse_reset` in `routes/` = **0 Treffer**. Weder in oauth.py noch settings.py versteckt.
- **OAuth-state-Parameter CSRF-Schutz:** Authlib-intern korrekt (Default via Flask-Session), aber **nicht verifiziert dokumentiert** — und bricht, sobald Session-Cookie-Hardening falsch konfiguriert wird (Wechselwirkung mit LB-10).
- **Register-Audit-Event fehlt in Email + OAuth + Invitation-Pfad** — MASTER-AUDIT H-8 bestaetigt, 3 Stellen ergaenzen.
- **`delete_account` hinterlaesst Tombstone ohne DSGVO-Loeschkaskade** — nur `aktiv=False`-Flag, keine Datenloeschung. Widerspruch zu Art. 17.
- **Settings-Routes ohne Org-Scoping-Defense-in-Depth:** `user.id`-Lookup ohne Gegenpruefung `user.org_id == g.org.id` → theoretisch manipulierbar falls `g.user` oder `g.org` inkonsistent gesetzt wuerde.

**Neue Funde-Zaehlung:** 2 LB-Kandidaten, 7 HIGH, 6 MEDIUM, 4 LOW.

---

## Hypothesen-Check aus Briefing

| # | Hypothese | Ergebnis |
|---|---|---|
| 1 | OAuth-`state`-Parameter CSRF-Schutz validiert? | **Teilweise** — Authlib default macht es via `session['_state_...']`, aber nirgends **explizit verifiziert** und bricht mit LB-10 |
| 2 | OAuth-Token-Refresh-Pattern implementiert? | **Nein** — kein Refresh-Token gespeichert, kein Graph-/People-API-Call spaeter. NERVE braucht es aktuell nicht, aber Scope-Creep-Falle wenn Calendar/Contacts dazukommen |
| 3 | OAuth-Account-Linking mit existierendem Email-Account? | **Ja, automatisch** — oauth.py:84-99. **Sicherheits-Risiko:** Angreifer der Google-Account mit Opfer-Email registriert, kann sich ohne weiteren Consent in NERVE einloggen wenn Email-User existiert. Google-Pfad schuetzt durch `email_verified`-Check (Z.172). **Microsoft-Pfad: KEIN Check** (Z.227: `# Microsoft: KEIN email_verified-Check`). |
| 4 | DSGVO-Audit-Events fuer OAuth-Register/-Login? | **Login ja, Register nein** — `log_action(..., 'login', details={'method': provider})` fuer beide Pfade. **Aber: Register-Event fehlt** — neuer User wird angelegt, Event ist nur `login`, nicht `register`. Bestaetigt MASTER H-8. |
| 5 | Settings-Routes: welche Felder editierbar? Org-Scoping konsistent? | **Editierbar:** profile (6 Felder), billing (6 Felder), cancel, reactivate, privacy (dsgvo_modus), theme, language, notifications (5), delete. **Org-Scoping:** nur ueber `g.org.id`, **keine Defense-in-Depth-Pruefung** dass `user.org_id == g.org.id` |
| 6 | auth.py Rate-Limit bei Failed-Login? | **Nein** — Grep `rate_limit|Limiter` in salesnerve/ = 0 Treffer im Code. `api_login` retourniert einfach 401 ohne Counter. Brute-Force-Schutz komplett fehlt. |
| 7 | Session-Fixation-Schutz (neue Session-ID nach Login)? | **Nur in OAuth-Pfad** (`session.clear()` vor `_login_user()` in oauth.py:102, 128). **Email-Pfad (`_do_login`) macht KEIN `session.clear()` vor `_login_user`** → theoretisch Session-Fixation moeglich, wenn Angreifer Pre-Auth-Session-Cookie setzt. |

---

## Findings — Severity-Sortiert

### LB-9 (NEU): Keine CSRF-Protection auf POST-Routen

**Severity:** Launch-Blocker (unstrittig fuer B2B-DSGVO-Claim)
**Evidence:**
- Grep `csrf|CSRF` in salesnerve Code (exklusiv .planning/, tests/): **0 Code-Treffer**. Keine `CSRFProtect(app)`, keine `Flask-WTF`-Integration, kein manuelles Token-Pattern.
- Templates verifiziert: keine `csrf_token()`-Calls im Quellcode der HTML/JS.
- `/api/login`, `/api/register`, alle 10 `/settings/*`-POST-Routen, OAuth-Callbacks akzeptieren rohe JSON-Bodies ohne Token.

**Angriffs-Szenarien:**
1. Opfer eingeloggt → klickt auf Angreifer-Link → Angreifer-Site submittet via JavaScript `fetch('https://getnerve.app/settings/cancel', {method:'POST', credentials:'include', body:'{}'})` → Abo gekuendigt.
2. Dasselbe fuer `/settings/delete_account` mit `confirmation:'LÖSCHEN'` → Account-Loeschung.
3. `/settings/billing` → Rechnungsadresse auf Angreifer umstellen (USt-ID, billing_email setzen).

**Warum Launch-Blocker:** B2B-Kontext + DSGVO-USP. Einmal publik = juristisches Desaster. Fix ist technisch trivial.

**Fix:** Flask-WTF `CSRFProtect(app)` registrieren, POSTs erwarten `X-CSRF-Token`-Header, Frontend holt Token aus `/api/csrf`. Ausnahmen: Stripe-Webhook, Deepgram-Callback (nicht Browser-Origin).
**Aufwand:** 3-4h (inkl. Frontend-Anpassung + Test-Suite).

---

### LB-10 (NEU): Session-Cookie-Hardening fehlt

**Severity:** Launch-Blocker
**Evidence:** `app.py:26-29`:
```python
app.config['SECRET_KEY']           = SECRET_KEY
app.config['SESSION_PERMANENT']    = True
app.config['CSS_VERSION']          = '20260421-1'
app.config['MAX_CONTENT_LENGTH']   = 5 * 1024 * 1024
```
**Fehlt:**
- `SESSION_COOKIE_SECURE = True` → Cookie wuerde auch ueber HTTP reisen
- `SESSION_COOKIE_HTTPONLY = True` → JavaScript kann Cookie lesen (default ist zwar True in Flask, aber nicht explizit gesichert)
- `SESSION_COOKIE_SAMESITE = 'Lax'` → Cross-Site-Requests senden Cookie mit, verstaerkt LB-9
- `PERMANENT_SESSION_LIFETIME` → Flask-Default ist **31 Tage**. Stealing eines Cookies = Monats-Zugriff.

**Wechselwirkung mit LB-9:** Ohne `SameSite=Lax|Strict` funktioniert CSRF-Angriff trivial. Mit `SameSite=Lax` bereits deutlich reduziert (keine cross-site POSTs).

**Fix:** 5 Zeilen in `app.py` direkt nach SECRET_KEY-Zuweisung.
**Aufwand:** 15 Minuten + Smoke-Test auf VPS (HTTPS ueber nginx noetig, sonst kickt Secure-Flag Login-Flow).

---

### H-AU-1: Register-Audit-Event fehlt in 3 Pfaden (MASTER H-8 Unterstrich)

**Evidence:**
- `auth.api_register` (Z.186-223): `log_action` wird **nicht** aufgerufen trotz User-Anlage. Nur `_login_user` setzt Session.
- `auth.register` (Invitation-Pfad, Z.226-265): **Keine** `log_action`-Aufrufe.
- `oauth._oauth_login_or_create` Neuanlage-Branch (Z.113-143): nur `log_action(..., 'login', details={'method': provider})` — Event sagt "login" obwohl Register stattfand.

**Folge:** DSGVO-Art.-7-Consent-Nachweis technisch nicht auffindbar. "Wer hat wann registriert" = nicht rekonstruierbar aus Audit-Log.

**Fix:**
```python
log_action(db, user.id, user.org_id, 'register',
           target_type='user', target_id=user.id,
           details={'method': 'email' or 'invitation' or provider}, request=request)
```
**Aufwand:** 30 min (3 Stellen + Tests).

---

### H-AU-2: Session-Fixation nur teilweise geschuetzt

**Evidence:**
- `oauth._oauth_login_or_create` Z.102 + Z.128: `session.clear()` vor `_login_user()` — **korrekt**.
- `auth._do_login` (Z.116-133): ruft `_login_user(db, user)` **ohne** vorher `session.clear()`.
- `auth._login_user` (Z.80-113): setzt `session.permanent = True` + diverse Keys, aber **keinerlei** `session.clear()` am Anfang → Attacker-gesetzte Pre-Auth-Session-Keys (csrf_seed, tracking, etc.) bleiben erhalten.

**Angriffs-Szenario:** Attacker setzt Opfer-Browser (XSS auf anderer Domain mit geteiltem Cookie-Scope — nicht direkt, aber: Sub-Domain-Takeover wenn getnerve.app Subdomains nutzt) pre-login, Opfer loggt ein, Attacker kennt Session-ID.

**Folge:** Weniger exploitable als LB-9/LB-10, aber stilistisch inkonsistent und best-practice-Bruch.

**Fix:** `session.clear()` am Anfang von `_login_user()` — **eine** Zeile schuetzt beide Pfade (Email + OAuth) uniform. OAuth-Pfad kann dann sein eigenes `session.clear()` entfernen.
**Aufwand:** 10 Minuten.

---

### H-AU-3: Microsoft OAuth — Email-Hijacking-Risiko

**Evidence:** `oauth.microsoft_callback` Z.227:
```python
# Microsoft: KEIN email_verified-Check (siehe RESEARCH.md)
email = userinfo.get('email') or userinfo.get('preferred_username') or ''
```
Kombiniert mit Z.83-112 (Email-Match → loggt existierenden User ein, zieht OAuth-Felder nach):

**Szenario:**
1. Opfer `bob@bigcorp.de` hat NERVE-Email-Account (kein OAuth).
2. Azure-Admin bei BigCorp setzt fuer `bob@bigcorp.de` in Azure den Email-Alias / UPN `evil@smallcorp.de` um — oder Attacker kontrolliert einen Azure-Tenant wo er `bob@bigcorp.de` als preferred_username setzt.
3. Attacker loggt via MS-OAuth ein. `preferred_username` = `bob@bigcorp.de`. NERVE findet Match → **loggt als Bob ein**, setzt `oauth_provider='microsoft'` und `oauth_id=Attacker-Sub`.

**Abschwaechung aktuell:** `/organizations/`-Endpoint + Personal-Tenant-Block (Z.221-226). Aber Multi-Tenant = jedes Azure-Business kann `preferred_username` frei waehlen. **Kein Schutz gegen feindliche Tenants.**

**Folge:** Account-Takeover ueber Microsoft-OAuth gegen Email-only-User moeglich. Google-Pfad schuetzt durch `email_verified` (Z.172).

**Fix:** Option A — Bei Email-Match via Microsoft OAuth: **nicht einloggen, sondern Confirmation-Email an existierenden User senden** ("Microsoft-Login fuer deinen Account aktivieren?"). Option B — `tid` (Tenant-ID) im User speichern, nur akzeptieren wenn ersten Login. Option C — Email-Domain-Whitelist pro Org.
**Aufwand:** 2-3h Option A, 4h Option B.

---

### H-AU-4: `delete_account` erfuellt Art. 17 DSGVO nicht

**Evidence:** `settings.delete_account` Z.196-205:
```python
db.query(User).filter_by(org_id=g.org.id).update({'aktiv': False})
org = db.query(Organisation).get(g.org.id)
org.aktiv = False
db.commit()
```
Soft-Delete per Flag. **Keine Loeschung von:**
- Conversation-Logs, Call-Logs, Training-Logs (enthalten Kundendaten!)
- Profile-JSON (Produktbeschreibung, ICP, PII)
- Feedback-Events
- Audit-Logs (kollidieren ohnehin mit Retention-Policy — siehe MASTER MEDIUM)
- Stripe-Kundennummer, billing_vat_id

**Folge:** User loescht Account → NERVE behaelt weiterhin personenbezogene Daten. DSGVO-Art.-17-Verstoss. USP "DSGVO-First" wird zur Luege.

**Fix:** Eigene DSGVO-Route `/dsgvo/account_delete` mit **echter** Kaskadenloeschung + Audit-Event + Consent-Modal. Aktuelle Settings-Route entweder umbenennen zu `/settings/deactivate` oder komplett auf DSGVO-Route umleiten.
**Aufwand:** 6-8h (ueberlappt mit MASTER LB-2, zusammen mit `/dsgvo/data_export` und Portability).

---

### H-AU-5: Brute-Force-Schutz fehlt auf `/api/login`

**Evidence:** `auth.api_login` Z.169-183: Rate-Limiting nicht vorhanden, kein `failed_login`-Counter, kein Lockout.
**Folge:** Password-Stuffing/Brute-Force unbegrenzt moeglich. Kombiniert mit fehlendem CAPTCHA = Credential-Stuffing-Einfallstor.
**Fix:** `flask-limiter` einbauen, `/api/login` auf `5 per minute per IP`, `/api/register` auf `3 per hour per IP`. Bonus: `failed_login` als Audit-Event loggen (schliesst auch MASTER H-8 weiter).
**Aufwand:** 2-3h.

---

### H-AU-6: `oauth_id` hat keinen UNIQUE-Constraint

**Evidence:** `database/models.py:113-114`:
```python
oauth_provider        = Column(String(50),  nullable=True)
oauth_id              = Column(String(200), nullable=True)
```
Keine `UniqueConstraint(('oauth_provider', 'oauth_id'))` und auch kein Index.

**Folge:**
- Zwei User mit derselben `oauth_id` moeglich (z.B. wenn Admin manuell provisioniert + OAuth-Login nachzieht mit `oauth_id` schon vergeben).
- Performance: Lookup ueber oauth_id = Full-Scan, wenn das je als Primaer-Pfad gebaut wird.
- Aktuell ist der Login-Pfad `email`-basiert → oauth_id ist nur Marker, deshalb HIGH statt LB.

**Fix:** Alembic-Migration (eigentlich: ad-hoc `_migrate` in app.py) fuer `UNIQUE(oauth_provider, oauth_id) WHERE oauth_id IS NOT NULL`.
**Aufwand:** 30 min + Migration-Test.

---

### H-AU-7: `_is_known_oauth_tenant` Timing-Side-Channel

**Evidence:** `oauth.py:18-37`. Die Funktion prueft existierende User einer Email-Domain beim MS-Login. Unterscheidbare Response-Zeiten zwischen "Domain bekannt" (DB-Read + Zeile gefunden) vs. "Domain unbekannt" (DB-Read, keine Zeile) + unterschiedliche OAuth-Flow-Weichen (prompt=consent ja/nein).

**Folge:** Externer Angreifer kann durch Messung von Redirect-Zeiten oder Analyse der `prompt=consent`-Parameter im Authorization-URL herausfinden, ob eine Email-Domain bereits NERVE-User hat. **User-Enumeration auf Domain-Ebene.** Fuer B2B-Reconnaissance interessant.

**Folge-Schweregrad:** NIEDRIG fuer tatsaechliche Sicherheit (nur Domain, nicht Email), aber Datenschutz-Relevant.

**Fix:** Entweder `prompt=consent` immer senden (verliert Silent-SSO-Vorteil) oder Random-Delay einfuehren. Alternative: Akzeptieren + in DSGVO-FAQ dokumentieren.
**Aufwand:** 30 min + Entscheidung.

---

### M-AU-1: Settings-Org-Scoping hat keine Defense-in-Depth

**Evidence:** Alle Settings-Routes nutzen `g.user.id` und `g.org.id` als gegeben. `g.user` wird in `login_required` gesetzt aus `session['user_id']`. **Nirgends** in settings.py wird geprueft, dass `user.org_id == g.org.id`.

**Aktuell nicht exploitable** weil `g.org` direkt aus `g.user.org_id` kommt (auth.py:55). Aber wenn in Zukunft jemand `/settings/billing` von `g.user.org_id` entkoppelt (z.B. "Admin kann andere Org einsehen"), haben wir silent Privilege-Escalation.

**Fix:** Assertion in `login_required`:
```python
assert g.user.org_id == g.org.id, 'g.user/g.org mismatch'
```
Oder Decorator `@require_own_org`.
**Aufwand:** 15 min.

---

### M-AU-2: `/settings/billing` validiert USt-ID nicht

**Evidence:** `update_billing` Z.60-76 akzeptiert `billing_vat_id` als beliebigen String.
**Folge:** User kann ungueltige USt-ID eintragen → Rechnung nicht reverse-charge-faehig → Steuer-Problem bei EU-B2B-Billing.
**Fix:** Regex `[A-Z]{2}[0-9A-Z]+`, optional VIES-Check via `pyVIES`. Mindestens Syntaktik.
**Aufwand:** 1-2h.

---

### M-AU-3: `/settings/cancel` ohne sofortige Wirkung, ohne Cron

**Evidence:** `cancel_subscription` Z.79-99 setzt nur `org.cancelled_at = datetime.now()`. **Welcher Job** respektiert das Feld? Grep in Codebase zeigt:
- payments.py nutzt es bei Stripe-Subscription-Pause (nicht verifiziert).
- Kein Cronjob in app.py der bei `cancelled_at + 30d` `org.aktiv = False` setzt.

**Folge:** User kuendigt, Abo laeuft ewig weiter intern. Stripe cancelt vielleicht, aber NERVE-Intern bleibt `aktiv=True` bis zur Heat-Death.
**Fix:** Cron-Job (APScheduler oder systemd) — pruefen ob existiert, ggf. bauen. Evtl. in payments.py schon vorhanden, muss verifiziert werden.
**Aufwand:** 2-3h Verifikation + Patch.

---

### M-AU-4: `_create_org_and_user` hardcoded `size_to_plan` widerspricht Plan-Katalog

**Evidence:** auth.py:143:
```python
size_to_plan = {'1-5': 'starter', '6-15': 'starter', '16-30': 'business', '30+': 'business'}
```
MASTER-AUDIT-Feststellung: alle PLANS haben `max_users=1`. Hier wird Team-Groesse abgefragt aber nie sinnvoll aufgeloest. `'16-30'` → `business` aber `business.max_users=1` → widersprueche User-Erwartung.

**Folge:** Self-Service-Register von Team-Accounts fuehrt zu inkonsistenten Plans.
**Fix:** Zusammen mit MASTER-Medium-Befund zu PLAN-Katalog-Redesign loesen.
**Aufwand:** 1-2h (blocked by Plan-Entscheidung Andre).

---

### M-AU-5: `oauth.py` importiert `_create_org_and_user` + `_login_user` ueber private Namen

**Evidence:** `oauth.py:7`: `from routes.auth import _login_user, _create_org_and_user`. Unterstrich-Praefix suggeriert "private", ist aber modul-overreaching geteilt.

**Folge:** Nicht-funktional, aber API-Hygiene-Schuld. Refactor-Bruch-Risiko.
**Fix:** Entweder `_`-Praefix entfernen und als public markieren (add to `__all__`), oder in `services/user_service.py` extrahieren.
**Aufwand:** 30 min.

---

### M-AU-6: Welcome-Email-Fehler wird silent geschluckt (2x)

**Evidence:**
- `auth.api_register` Z.216-220: `try: send_welcome(...); except Exception as e: print(...)`
- `oauth._oauth_login_or_create` Z.134-138: gleiches Muster

**Folge:** Email-Service-Ausfall (Resend-API down, Rate-Limit, EU-Region-Misconfig) → neuer User sieht **nichts**. Founder bemerkt es nur per journalctl-Grep. Consent-Nachweis verloren wenn Welcome-Email als AGB-Bestaetigung zaehlt.
**Fix:** Logging in `services/email_service` statt nur print, Failure-Counter, bei n Failures Alert. Schliesst auch MASTER-AUDIT-Befund zu Resend-EU-Region-Validation.
**Aufwand:** 1-2h.

---

### L-AU-1: `settings.update_profile` akzeptiert beliebige String-Laenge

**Evidence:** Kein Max-Length-Check auf `persoenlich`, `schmerzpunkt`, `dashboard_stil`. Model sagt `Text` (unbounded).
**Folge:** DB-Bloat moeglich, Unicode-Bomb-DoS moeglich.
**Fix:** Server-side Clamp auf 2000 Zeichen. 15 min.

---

### L-AU-2: `settings.settings_theme` Theme-Fallback ueberschreibt still

**Evidence:** Z.141-142: `if theme not in ('light', 'dark'): theme = 'dark'`. User schickt `theme='matrix'` → bekommt `ok:True, theme:'dark'` ohne Warn-Hinweis.
**Folge:** UI-Verwirrung. Nicht-funktionales Problem.
**Fix:** 400 statt silent-overwrite. 5 min.

---

### L-AU-3: `settings.settings_language` Sprachliste inkonsistent

**Evidence:** Z.158: `allowed = ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'cs', 'tr']`. NERVE-Positionierung ist DACH. 10 Sprachen suggerieren Multi-Lang-UI die nicht existiert.
**Folge:** User waehlt 'tr' → UI bleibt deutsch → Bug-Report-Risiko.
**Fix:** Liste auf `['de', 'en']` reduzieren bis multi-lang-Content existiert. 5 min.

---

### L-AU-4: `auth.logout` ohne CSRF-Schutz — GET-Request

**Evidence:** `@auth_bp.route('/logout')` ohne `methods=...`-Einschraenkung → akzeptiert GET.
**Folge:** Angreifer kann per `<img src=https://getnerve.app/logout>` Opfer ausloggen. **Nur DoS-Qualitaet**, kein Datenleck. Best-Practice-Bruch.
**Fix:** `methods=['POST']` + CSRF (kommt mit LB-9). Im Uebergang: CSRF-Token als Query-Param akzeptieren.
**Aufwand:** teil von LB-9.

---

## Scan-Protokoll-Einzelbefunde

### Silent Failures

| Stelle | Muster | Severity |
|---|---|---|
| `auth.logout:282-283` | `except Exception: pass` | LOW (audit-only) |
| `auth.api_register:219` | `except Exception as e: print(...)` welcome mail | M-AU-6 |
| `oauth._oauth_login_or_create:137` | dito | M-AU-6 |
| `oauth.google_callback:168-170` | `except Exception as e: print(f'...{type(e).__name__}')` — verliert Exception-Details | LOW |
| `oauth.microsoft_callback:213-215` | dito | LOW |

### TODO/FIXME in den 3 Dateien

| Datei:Zeile | Text |
|---|---|
| oauth.py:156 | `# TODO: Frontend kann ?login_hint=<email> mitsenden wenn User Email kennt.` |
| oauth.py:196 | dito |

Beide sind Hints, keine Bugs.

### Unused Imports

| Datei | Import | Genutzt? |
|---|---|---|
| auth.py:5 | `render_template` | **Ja** (Z.245, 248, 251, 263) |
| auth.py:8 | `Invitation` | **Ja** (Z.235) |
| settings.py:1 | `redirect, url_for` | **Nein** — importiert aber nirgends gerufen |
| settings.py:4 | `Organisation` | **Ja** (mehrfach) |

**Unused:** `redirect` und `url_for` in settings.py → 15-sek-Cleanup.

### Hardcoded Credentials/Secrets

Keine im Code. `GOOGLE_CLIENT_SECRET`/`MICROSOFT_CLIENT_SECRET` kommen aus config.py → os.environ. Clean.

### Schema-Validation-Luecken

| Route | Fehlende Validation |
|---|---|
| `auth.api_login` | Email-Format (nur `strip().lower()`, kein Regex) |
| `auth.api_register` | Email-Format, firmenname-Length, branche-Whitelist |
| `settings.update_profile` | String-Length (L-AU-1) |
| `settings.update_billing` | billing_country-Whitelist, billing_vat_id-Regex (M-AU-2) |
| `settings.cancel_subscription` | `reason`-Whitelist, `feedback`-Length |

### Call-Graph (3 Dateien)

```
HTTP → auth_bp.login (GET/POST) → redirect landing modal
HTTP → auth_bp.api_login → _do_login → _login_user → log_action('login')
HTTP → auth_bp.api_register → _create_org_and_user + _login_user + send_welcome
HTTP → auth_bp.register (GET/POST with token) → Invitation-Lookup → User-Create [KEIN log_action]
HTTP → auth_bp.logout → log_action('logout') + session.clear

HTTP → oauth_bp.google_login → Authlib authorize_redirect
HTTP → oauth_bp.google_callback → Authlib authorize_access_token → _oauth_login_or_create
HTTP → oauth_bp.microsoft_login → Authlib authorize_redirect (+ prompt=consent via _is_known_oauth_tenant)
HTTP → oauth_bp.microsoft_callback → Authlib authorize_access_token → _oauth_login_or_create
                                                                          → _create_org_and_user
                                                                          → _login_user
                                                                          → log_action('login', details.method=provider)
                                                                          → send_welcome [silent-swallow]

HTTP → settings_bp.index → render_template
HTTP → settings_bp.update_profile (8 Felder)
HTTP → settings_bp.update_billing (6 Felder) [role-gated owner/admin]
HTTP → settings_bp.cancel_subscription [role-gated]
HTTP → settings_bp.reactivate_subscription [role-gated]
HTTP → settings_bp.update_privacy (dsgvo_modus) [role-gated]
HTTP → settings_bp.settings_theme
HTTP → settings_bp.settings_language
HTTP → settings_bp.update_notifications (5 Flags)
HTTP → settings_bp.delete_account [role-gated owner only] → Soft-Delete
HTTP → settings_bp.help_center / upgrade → render_template
```

**Keine Settings-Route loggt Audit-Events.** Profile-Update, Billing-Update, Privacy-Toggle, **Account-Delete** — null Audit-Trail. Kritisch fuer DSGVO-Art.-5/7 (Rechenschaftspflicht).

---

## Doku-Lueen-Check

| Quelle | Behauptung | Realitaet |
|---|---|---|
| `oauth.py:101` Inline-Kommentar | "Session-Fixation-Schutz: alte Session-Keys loeschen" | **Nur OAuth-Pfad geschuetzt**, Email-Pfad nicht — inkonsistent |
| `auth.py:121-122` Kommentar | "Identischer Errortext verhindert User-Enumeration" | **Stimmt**, sauber umgesetzt. |
| `oauth.py:59-60` Kommentar | "/organizations/ endpoint: nur Work/School-Accounts" | **Stimmt**, plus Defense-in-Depth-Check in Z.221-226 |
| MASTER LB-1 | "Password-Reset komplett fehlt" | **Re-verifiziert:** keine Spur in auth/oauth/settings |

---

## Neue Funde — Prioritaets-Tabelle

| ID | Titel | Severity | Aufwand | Abhaengig von |
|---|---|---|---|---|
| LB-9 | CSRF-Protection fehlt | LB | 3-4h | — |
| LB-10 | Session-Cookie-Hardening fehlt | LB | 15 min | HTTPS (vorh.) |
| H-AU-1 | Register-Audit-Event fehlt (3 Pfade) | HIGH | 30 min | — |
| H-AU-2 | Session-Fixation nur OAuth geschuetzt | HIGH | 10 min | — |
| H-AU-3 | Microsoft-OAuth Email-Hijacking | HIGH | 2-3h | Design-Call |
| H-AU-4 | `delete_account` ≠ DSGVO-Loeschung | HIGH | 6-8h | MASTER LB-2 bundling |
| H-AU-5 | Brute-Force-Schutz auf /api/login fehlt | HIGH | 2-3h | flask-limiter |
| H-AU-6 | `oauth_id` ohne UNIQUE-Constraint | HIGH | 30 min | Migration |
| H-AU-7 | `_is_known_oauth_tenant` Timing-Side-Channel | HIGH/MED | 30 min + Decision | — |
| M-AU-1 | Org-Scoping Defense-in-Depth | MEDIUM | 15 min | — |
| M-AU-2 | USt-ID-Validierung fehlt | MEDIUM | 1-2h | — |
| M-AU-3 | `cancel_subscription`-Cron unverifiziert | MEDIUM | 2-3h | payments.py-Audit |
| M-AU-4 | `size_to_plan` vs. PLAN-Katalog | MEDIUM | 1-2h | Plan-Decision |
| M-AU-5 | Private-Name-Overreach ueber Module | MEDIUM | 30 min | — |
| M-AU-6 | Welcome-Mail-Failure silent | MEDIUM | 1-2h | — |
| L-AU-1 | Profile-String ohne Max-Length | LOW | 15 min | — |
| L-AU-2 | Theme-Fallback silent | LOW | 5 min | — |
| L-AU-3 | 10 Sprachen aber 1 Content-Lang | LOW | 5 min | — |
| L-AU-4 | Logout akzeptiert GET | LOW | teil LB-9 | LB-9 |

---

## Empfohlener Fix-Block (Minimum fuer DACH-EA-Launch)

**Block "Auth-Haertung" (~12-15h) — PFLICHT vor Public-EA:**

1. LB-9 CSRF-Protection flaechendeckend (3-4h)
2. LB-10 Session-Cookie-Flags (15 min)
3. H-AU-1 Register-Audit-Event (30 min)
4. H-AU-2 Session-Fixation Uniform (10 min)
5. H-AU-5 flask-limiter fuer /api/login + /api/register (2-3h)
6. M-AU-1 Org-Scoping-Assertion (15 min)
7. H-AU-6 oauth_id UNIQUE-Constraint (30 min)
8. H-AU-3 Microsoft-Email-Hijacking-Mitigation (2-3h, Option A)

Passt in einen GSD-Phasen-Block "04.x-Auth-Launch-Haertung" — idealer Kandidat fuer `/gsd-secure-phase` + Threat-Model.

**Block "DSGVO-Auth-Integration" (spaeter, ~8-10h):**

9. H-AU-4 zusammen mit MASTER LB-2 als `/dsgvo/account_delete` echt umsetzen
10. Audit-Events fuer alle Settings-Writes (profile, billing, privacy, delete) — schliesst MASTER H-8 weiter

---

## Top-3-Message an Andre

1. **CSRF + Session-Flags sind Show-Stopper.** 15 Minuten Arbeit fuer Session-Flags, 3h fuer CSRF. Nicht optional wenn wir "DSGVO-First" als Positionierung nutzen. Sonst reicht **ein** twitternder Sec-Researcher und die Positionierung ist tot.

2. **Microsoft-OAuth Email-Matching ist eine Account-Takeover-Luecke.** Google-Pfad hat `email_verified`-Check. MS-Pfad nicht — RESEARCH.md hat das dokumentiert aber nicht entschaerft. Fix nicht aufschieben, B2B-Segment ist **genau** der Angriffsvektor.

3. **`delete_account` ist Etikettenschwindel.** User klickt "Account loeschen", NERVE setzt `aktiv=False`. Alle Call-Logs, Profile, Trainings bleiben. DSGVO-USP = Luege. Muss mit MASTER LB-2 gebuendelt werden — sonst Abmahn-Vorlage.

---

*Stand 2026-04-24, Welle 3. Nicht in Scope: tests/, frontend JS-Kopplung an diese Routes, payments.py (Stripe-Kuendigungs-Cron).*
