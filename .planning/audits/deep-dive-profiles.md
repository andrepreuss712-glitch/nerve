---
audit: deep-dive-profiles
phase: Welle 3 (Routes)
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault)
scope:
  - routes/profiles.py (577 Zeilen, 100% gelesen)
  - Cross-refs: database/models.py (Profile/ProfileSkript/ProfileFaq/ProfileOpener), app.py _seed_demo_profiles, services/profile_migration.py, services/einwand_keyword_matcher.py, static/profile_editor.js, routes/auth.py api_register
stand_code: HEAD 2026-04-24
basiert_auf:
  - .planning/audits/MASTER-AUDIT.md
  - .planning/audits/profil-prompt-integration-matrix.md
---

# Deep-Dive: `routes/profiles.py`

## TL;DR

`profiles.py` ist sauberer als viele andere Route-Module — aber es sitzt auf **drei systemischen Defekten** die alle Launch-relevant sind:

1. **Kein Schema-Validator.** Profile.daten akzeptiert beim Save jedes JSON, solange es `json.loads`-bar ist. Ein User kann `{"foo": "bar"}` speichern und bekommt "Profil gespeichert" — die UI rendert beim nächsten Load leere Felder und die KI liest nichts. Silent Data Loss.
2. **Regex-Patterns in `einwaende[]` werden beim Save nie gegen `re.compile` geprüft.** Der Matcher prüft gar keine Profile-definierten Regex — er hat eine eigene hartkodierte `DEFAULT_KEYWORDS`-Liste (einwand_keyword_matcher.py:85-100). Das heißt die Hypothese "malformed Regex failt silent im Matcher" ist **neutralisiert, weil User-Regex gar nicht gelesen werden** — aber das ist selbst ein Fund: `einwaende[].pattern` (falls existent) oder benutzerdefinierte Regex-Felder sind komplett tot.
3. **Org-Scoping ist konsistent** bei Profile-CRUD und FAQ-CRUD — aber **Skripte- und Opener-CRUD-GETs sind unter-geschützt**: jeder eingeloggte User der Profile-ID kennt kann die Sub-Listen lesen, solange das Profil seiner Org gehört — das ist OK. Aber ProfileSkript/ProfileOpener haben **keinen eigenen org_id-Column**, die Isolation hängt 100% daran dass der Parent-Profile-Check nicht übersprungen wird. Aktuell ist der Check drin, aber sehr fragil gegen Refactor.

**Weitere kritische Funde siehe Detail-Sektionen unten.**

---

## 1. Routes-Inventar

| Route | Methoden | Auth | Rolle | Org-Scope | Audit | Anmerkung |
|---|---|---|---|---|---|---|
| `/profiles/` | GET | login | alle | ✅ (via g.org.id) | ❌ | Liste |
| `/profiles/new` | GET,POST | login | owner/admin | ✅ | ❌ | **Kein Audit-Event bei Erstellung** |
| `/profiles/wizard` | GET | login | alle | N/A | ❌ | Template only |
| `/profiles/wizard` | POST | login | **ALLE (nicht nur owner/admin)** | ✅ | ❌ | Inkonsistenz — `neu` verlangt owner/admin, `wizard_create` nicht |
| `/profiles/<pid>/edit` | GET,POST | login | owner/admin | ✅ | ✅ partiell | `profile_update` gelogged, `details` nur `{'name': p.name}` — H-8-Coverage-Gap bestätigt |
| `/profiles/<pid>/activate` | POST | login | **alle** | ✅ | ❌ | Auch Member dürfen aktivieren |
| `/profiles/<pid>/delete` | POST | login | owner/admin | ✅ | ❌ | **Löschung ohne Audit-Event** — DSGVO-Coverage-Gap |
| `/profiles/<pid>/skripte` | GET | login | alle | ✅ (via parent) | ❌ | |
| `/profiles/<pid>/skripte` | POST | login | owner/admin | ✅ | ❌ | |
| `/profiles/<pid>/skripte/<sid>` | PUT | login | owner/admin | ✅ | ❌ | |
| `/profiles/<pid>/skripte/<sid>` | DELETE | login | owner/admin | ✅ | ❌ | |
| `/profiles/<pid>/opener` | GET,POST | login | alle / owner-admin | ✅ | ❌ | |
| `/profiles/<pid>/opener/<oid>` | PUT,DELETE | login | owner/admin | ✅ | ❌ | |
| `/profiles/api/profile/<pid>/faqs` | GET,POST | login | **alle!** | ✅ | ❌ | **FAQ-Create erlaubt auch Member** — Rollen-Drift gegen Skripte/Opener |
| `/profiles/api/profile/faqs/<fid>` | PUT,DELETE | login | **alle!** | ✅ | ❌ | Dito — keine `_rolle()`-Prüfung |
| `/profiles/api/profile/<pid>/tabu` | POST | login | **alle!** | ✅ | ❌ | Dito |

---

## 2. LAUNCH-BLOCKER-Kandidaten

### LB-9: Neu-registrierte User bekommen KEIN Startprofil

**Evidence:**
- `routes/auth.py::api_register` (Z.186-223) → ruft `_create_org_and_user` + `_login_user`. **Kein Profile-Insert.**
- `app.py::_seed_demo_profiles` (Z.1266) läuft beim App-Start (Z.1611) und **nur für Org "NERVE Alpha"** — hardcoded (`db.query(Organisation).filter_by(name='NERVE Alpha').first()`). Keine der drei Demo-Profile-Insert-Logiken wird beim User-Register getriggert.
- `_create_org_and_user` (nicht gelesen, aber per Kontext: erstellt neue Org mit Custom-Firmenname). → Neue Org ≠ "NERVE Alpha" → Seed greift nicht.

**Folge:** EA-User registriert sich → landet im Dashboard → **kein aktives Profil** → Live-EWB fällt auf Default-Fallback (leeres `build_profile_context`) → KI kennt weder Produkt noch USPs → alle Antworten generisch.

**Verstärkt LB-3 und H-13:** Selbst wenn QA-Pipeline profile_data durchreichen würde — ohne Profil ist der Context leer.

**Der Wizard (`/profiles/wizard`) existiert als Lösung, wird aber nicht erzwungen.** Keine Redirect-Logik in `login_required` die User ohne Profil zum Wizard schickt (Onboarding-Redirect ist in auth.py:60-62 **explizit auskommentiert**).

**Fix-Aufwand:** 1-2h
- Option A: `_create_org_and_user` fügt automatisch ein leeres/template Profil hinzu + setzt `active_profile_id`
- Option B: `login_required` redirectet zum Wizard wenn User `active_profile_id == None` hat
- Option C: Demo-Profile-Seed auch für neue Orgs triggern (in `_create_org_and_user`)

**Empfehlung: B + C.** Wizard ist schon gebaut, nur nicht erzwungen. Zusätzlich 1-2 Demo-Profile seeden als Referenz.

---

### LB-10: Concurrent-Write "letzter gewinnt" + `active_profile_id` Ghost-Session-Drift

**Evidence:**
- `Profile.aktualisiert_am` (models.py:130) existiert mit `onupdate=utcnow`, aber **kein `version`-Column für Optimistic Locking**.
- `bearbeiten` liest kein `version`/`etag` aus Form, prüft keinen Timestamp. → Letzter Write gewinnt.
- Schlimmer: `aktivieren` (Z.187-209) **schreibt `u.active_profile_id`** am Ende mit `db.commit()`, aber der `set_active_profile`-Call (Z.201) geht direkt ins `live_session`-State-Singleton → bei parallelen Sessions zweier User derselben Org überschreiben sie sich gegenseitig das globale `ls.state`.

**Folge:**
- User A öffnet Profil-Editor → Tab bleibt offen. User B (owner) editiert → speichert. User A speichert → **alle Änderungen von User B weg**. Stumm.
- Außerdem: Wenn User A und User B gleichzeitig "Profil X aktivieren" klicken, ist `ls.set_active_profile` nicht pro Org isoliert. Ghost-Profil-State in der Live-Session, bekannt aus Welle 1.

**Fix-Aufwand:** 3-4h
- `version`-Spalte + If-Match-Header oder `aktualisiert_am`-Vergleich
- `set_active_profile` muss pro-Org/pro-Session-State sein (größerer Fix, siehe Welle-1-Live-Session-Befunde)

**Severity:** Wahrscheinlich HIGH statt Launch-Blocker, weil:
- Solo-Owner-Szenario (EA: 50 Plätze, viele davon Solo-Founder) minimiert Kollisions-Wahrscheinlichkeit
- Aber: Multi-User-Plan (Team/Business) hat das Problem sofort

---

### LB-11: Profile.daten ohne Schema-Validator — Silent Data Loss

**Evidence:**
- `neu` (Z.62-66): `json.loads(daten_json)` — akzeptiert ALLES was valides JSON ist. `daten_json = '{}'` als Fallback wenn Parse fehlschlägt. Kein Type-Check, kein Shape-Check.
- `bearbeiten` (Z.158-162): Dito.
- `wizard_create` (Z.115-121): Baut einen Dict aus 5 Top-Level-Feldern (firma/produkt/zielkunden/rolle/einwaende) — **widerspricht dem Schema dass der Editor erwartet** (`basis.produktbeschreibung`, `basis.unternehmen`, etc.).

**Folge:**
- **Schema-Drift Wizard vs. Editor:** Wizard schreibt `produkt` auf Top-Level. Editor rendert aber `basis.produktbeschreibung`. → User füllt Wizard aus → öffnet Editor → alle Felder leer → "Oh, nix gespeichert" → User tippt nochmal ein → Top-Level-Key vom Wizard bleibt orphan daneben.
- **Dieselbe Root-Cause wie H-13** (MASTER-AUDIT: `/api/frage` und `/api/ewb_trigger` lesen `pdata.get("produkt")` flach, nicht `basis.produktbeschreibung`).
- Frontend-Bugs beim JSON-Serialisieren (z.B. Escaping-Fehler in `daten_json`-Hidden-Input) werden **nicht erkannt** — Fallback zu leerem Objekt, User sieht "Profil gespeichert".

**Fix-Aufwand:** 4-6h
- Pydantic-Schema für Profile.daten definieren (Phase-A-Audit hat die Feld-Liste)
- `neu`/`bearbeiten`/`wizard_create` validieren gegen Schema → bei Fehler 400 mit Feld-Diagnose
- `wizard_create` auf Schema-konforme Struktur umbauen (`{'basis': {'produktbeschreibung': ...}}`)
- **Teil des Profil-Redesign-Tracks (Phase C).** Für EA-Launch Minimum: Wizard-Struktur auf `basis.*` angleichen (~1h).

---

## 3. HIGH-Severity-Funde

### H-16: Rollen-Drift — FAQ/Tabu-API ohne owner/admin-Check

**Evidence:**
- Line 248, 269, 295, 330, 351, 377: Skripte + Opener CRUD-Mutations haben alle `if _rolle() not in ('owner', 'admin'): return 403`.
- Line 443 (`api_faqs_create`), Line 475 (`api_faqs_update`), Line 511 (`api_faqs_delete`), Line 530 (`api_tabu_update`): **Keine Rollen-Prüfung.** Nur `login_required` + Org-Check.

**Folge:** Member (non-owner/admin) können FAQs und Tabu-Begriffe anlegen/ändern/löschen, obwohl sie Profile nicht bearbeiten dürfen (Z.148). Inkonsistent.

**Bei Team-Plan relevant:** Junior-Vertriebler ändert Tabu-Listen ohne Freigabe des Owners → KI-Antworten driften ohne dass Owner merkt.

**Fix-Aufwand:** 15 min (4 Zeilen `_rolle()`-Check hinzufügen).

---

### H-17: Audit-Coverage für Profile-CRUD extrem dünn

**Evidence:**
- Einziges `log_action` in der gesamten Datei: `bearbeiten` mit `'profile_update'` + `details={'name': p.name}` (Z.169).
- **Fehlen:**
  - `profile_create` (neu + wizard_create + Skript/Opener/FAQ-Creates)
  - `profile_delete` (löschen)
  - `profile_activate` (aktivieren)
  - Feld-Diff bei `profile_update` (`{'name': p.name}` sagt nicht was geändert wurde)
  - Tabu-Änderungen (api_tabu_update)
  - FAQ-Änderungen (api_faqs_*)
  - consent_text-Änderungen — direkt DSGVO-relevant

**Folge:** MASTER-AUDIT H-8 konkretisiert sich in dieser Route. DSGVO Art. 5 Abs. 2 (Rechenschaftspflicht) ist bei Profile-Daten nicht erfüllt — speziell `consent_text` (Meeting-Consent-Vorlesetext) ist rechtlich kritisch und seine Änderungshistorie ist nicht nachvollziehbar.

**Fix-Aufwand:** 2-3h (log_action in jede Mutation + Diff-Generator für Feld-Änderungen).

---

### H-18: `aktivieren` commit-Reihenfolge — Race-Condition mit set_active_profile

**Evidence (Z.187-209):**
```python
flask_session['active_profile_id'] = p.id          # (1) Flask-Session
ls_mod.set_active_profile(p.name, daten, ...)      # (2) Globales ls.state
u.active_profile_id = p.id                          # (3) DB
db.commit()                                         # (4) Commit
```

**Folgen:**
1. Wenn `db.commit()` wirft (constraint violation), ist `ls.state` schon überschrieben aber DB noch alt.
2. `set_active_profile` setzt ein **Prozess-globales State** (Welle 1 Befund) — nicht pro User. Zwei User derselben Org die gleichzeitig aktivieren stepping on each other.
3. Kein Rollback auf Flask-Session-Level bei Fehler.

**Fix-Aufwand:** 1-2h — State-Reihenfolge ändern (DB zuerst, dann State), Rollback-Safe machen, pro-Session-Scoping überlegen.

---

### H-19: `wizard_create` — kein Rollen-Check, Org-kompromittierend

**Evidence:** `wizard_create` (Z.91-142) hat **keinen** `_rolle()`-Check. Jeder eingeloggte Member der Org kann Profile anlegen.

**Vergleich:** `neu` (Z.56-58) hat Check.

**Folge:** Junior-Member kann Profile in der Org anlegen die Owner nicht genehmigt hat. Auch: Member kann sich selbst ein eigenes Profil aktivieren (auch `aktivieren` ohne Rollen-Check) und damit Live-EWB mit eigenem Content fahren.

**Fix-Aufwand:** 5 min (Rollen-Check hinzufügen) — aber **erst nach LB-9-Entscheidung** (wenn Wizard-Onboarding erzwungen wird, muss jeder User initial eins anlegen dürfen → dann nicht Rolle sondern "erstes Profil der Org"-Check).

---

### H-20: Regex-Patterns in Profil nicht validiert beim Save — und auch nie gelesen

**Evidence:**
- User kann beim Einwand `{"pattern": "[unclosed"}` speichern. Kein `re.compile()`-Check in `profiles.py`.
- Matcher (`einwand_keyword_matcher.py:85-100`) liest **hardcoded `DEFAULT_KEYWORDS`-Dict**, nicht Profile-Einwände-Patterns.
- Profile-Einwände werden nur über `kurzlabel`/`kategorie`/`typ` als String-Alias gematched (Z.154-168), keine User-definierten Regex.

**Folge:** Hypothese "malformed Regex failt silent" aus dem Briefing: **faktisch irrelevant — weil User-Regex gar nicht existieren im Matcher-Flow.** Aber das ist selbst ein Finding: wenn Profile-Schema ein `pattern`-Feld vorsieht (oder der Editor eins anbietet), ist es **toter Input**.

**Phase-A-Audit-Cross-Check:** Matrix zeigt `einwaende[].varianten`/`technik`/`intensitaet` sind tot. Kein `pattern`-Feld erwähnt — also wahrscheinlich ungetestet/angedeutet in der UI aber nicht im Schema.

**Fix-Aufwand:** 30 min Verifikation + Entscheidung ob die UI Regex-Felder anbietet die nirgends gelesen werden.

---

## 4. MEDIUM-Severity-Funde

### M-1: `wizard_create` Session-Leak — `active_profile_id` wird nicht in Flask-Session geschrieben

**Evidence (Z.135-138):**
```python
user = db.query(UserModel).get(g.user.id)
if user:
    user.active_profile_id = profile.id
db.commit()
```
DB wird aktualisiert, aber `flask_session['active_profile_id']` nicht. Im Gegensatz zu `aktivieren` (Z.195).

**Folge:** User macht Wizard fertig → Dashboard liest `flask_session['active_profile_id']` → `None` → `app_routes.py:85-90` hat zum Glück einen DB-Fallback, der die Session refillt. Funktioniert im Endeffekt, ist aber implicit-contract-basiert. Bei Refactor der Route-Struktur brittle.

**Fix-Aufwand:** 1 min — 1 Zeile ergänzen.

---

### M-2: `loeschen` Cascade-Delete — Waisen in ProfileSkript/ProfileOpener/ProfileFaq

**Evidence:**
- Keine `cascade='all, delete'` oder `ondelete='CASCADE'` in den FK-Definitionen von ProfileSkript/ProfileOpener/ProfileFaq.
- `loeschen` (Z.212-229) macht `db.delete(p)` + `db.commit()`.

**Unverifiziert:** Ob SQLAlchemy die Child-Rows automatisch löscht, hängt vom Relationship-Setup (nicht gezeigt in models.py-Ausschnitt). Wenn FK ohne `ON DELETE CASCADE` → DB-Constraint-Fehler beim Delete wenn Skripte/Opener/FAQs existieren, oder Waisen wenn FK ohne Constraint.

**Fix-Aufwand:** 30 min Verifikation + ggf. explizites `db.query(ProfileSkript).filter_by(profile_id=pid).delete()` vor Profile-Delete.

---

### M-3: `_require_own_profile` leakt db-Session bei Nichtexistenz

**Evidence (Z.405-415):**
```python
def _require_own_profile(profile_id):
    db = get_session()
    p = db.query(Profile).filter_by(id=profile_id).first()
    if not p:
        return None, db          # Caller muss db.close()
    if ...not match org...:
        return None, db          # Caller muss db.close()
    return p, db
```

Alle Caller machen `try: ... finally: db.close()` — aber **convention über nicht-trivialen Contract**. Ein einzelner Caller der das vergisst leakt Connection. Für Phase-08.5-Neueinsteiger risiko.

**Fix-Aufwand:** 15 min — Context-Manager oder Helper der db-Close selbst macht.

---

### M-4: `TABU_DEFAULT_PAIRS` Source-of-Truth-Duplikat (bereits bekannt)

**Evidence bestätigt:** `services/profile_migration.py:20-34` (Python) vs. `static/profile_editor.js:132-146` (JS). 13 Paare identisch, kein Programmatic Sync. Kommentar im JS verweist auf Python-Source, aber nur verbal.

**Drift-Risiko:** Jemand ändert Python, vergisst JS (oder umgekehrt). Default-Pairs-Seed beim Editor-Load (via `migrate_tabu_begriffe`) füllt dann DB mit Python-Version, UI zeigt aber JS-Alternatives als Placeholder. Auseinandertreiben kann lange unbemerkt bleiben.

**Fix-Aufwand:** 2-3h — API-Endpoint `/api/tabu_defaults` der Python-Konstante serviert, JS fetched statt hardcoded. Oder: Build-time-Sync via Jinja-Render von `TABU_DEFAULT_PAIRS` in die Template-HTML als `data-*`-Attribute.

---

### M-5: `VALID_BRANCHE` Whitelist — stiller Daten-Clobber bei Legacy-Werten

**Evidence (Z.15-30):** Jeder Freitext-Wert außer den 8 Enum-Keys wird zu `'sonstiges'`. Kein Fehler an User.

**Folge:** Legacy-Profile mit "SaaS / KI-Software" (siehe `_seed_demo_profiles` Z.1235) werden beim Edit auf `'sonstiges'` gecrushed wenn User die Form submittet ohne den Wert bewusst zu ändern. `_normalize_branche(request.form.get('branche', p.branche or ''))` — wenn Form das alte Legacy-Label zurückschickt, wird es weggewischt.

**Verifikation nötig:** Sendet das HTML-Select tatsächlich den aktuellen DB-Wert zurück wenn er nicht im Enum ist? Wenn das Select keine Option für "SaaS / KI-Software" hat → Browser rendert wahrscheinlich leeren Wert → wird auch nicht gesetzt → OK.
Aber wenn UI ein `<input type="text">` ist → Freitext-Wert kommt zurück → wird auf `'sonstiges'` gemappt.

**Fix-Aufwand:** 30 min Verifikation + evtl. Migration-Script für Altbestand.

---

### M-6: `_normalize_branche` nicht im Wizard-Preview-Response

**Evidence:** Wizard normalisiert beim Save (Z.98), UI-Preview zeigt aber Freitext vor Save. Bei Server-Validation-Error (gibt aber keinen) würde User eine Diskrepanz sehen.

**Low, kosmetisch.**

---

### M-7: `bearbeiten` — name.strip() auf `None` möglich

**Evidence (Z.163):** `p.name = request.form.get('name', p.name).strip()`. Wenn Form "name" fehlt UND p.name == None (sollte nicht vorkommen wegen `nullable=False`, aber SQLite ist lax), wirft `.strip()` AttributeError.

**Niedrig-wahrscheinlich aber nicht null.**

**Fix:** `request.form.get('name', p.name) or ''`.

---

### M-8: Skripte/Opener/FAQ — keine Length-Caps auf `inhalt`

**Evidence:**
- ProfileFaq hat `_MAX_FRAGE_LEN=2000`, `_MAX_ANTWORT_LEN=2000` (Z.399-400). ✅
- ProfileSkript.inhalt und ProfileOpener.inhalt: **keine Length-Cap.** User kann 10MB Text reinschreiben. DB ist `Text`, akzeptiert.

**Folge:** Prompt-Pipeline-Pfade die Skripte/Opener lesen (falls sie das tun — Welle 1 sagt eher nicht) blasen Token-Budgets. Kein Hard-Crash, aber Cost-Explosion möglich.

**Fix-Aufwand:** 15 min — Length-Cap analog zu FAQ.

---

### M-9: Skripte/Opener CRUD — Fehlen `updated_at`-Felder

**Evidence (models.py:134-141, 157-164):** Nur `created_at`, kein `updated_at`/`aktualisiert_am`. Im Gegensatz zu Profile selbst.

**Folge:** Audit-Trail für Skript/Opener-Änderungen nicht möglich. H-17-Verstärkung.

**Fix-Aufwand:** 30 min — Spalten + Migration.

---

### M-10: `api_tabu_update` schreibt `daten` komplett um — kein Partial-Update-Schutz

**Evidence (Z.560-574):** Liest Profile.daten als JSON, überschreibt nur `basis.tabu_begriffe`, schreibt komplettes JSON zurück. Bei parallelem Save (User A editiert Profil im Haupt-Editor, User B ändert Tabu via API) gewinnt letzter Write → H-17/LB-10-Verstärkung. Kein Optimistic-Lock.

**Fix:** Zusammen mit LB-10 (Version-Column).

---

## 5. Silent Failures / TODOs

**Silent try/except Pass in der Datei: 0** — gut.
**Silent fallbacks bei JSON-Parse-Fehler: 4** (Z.65, 107, 159, 199) — User bekommt kein Feedback. In `neu`/`bearbeiten` führt das zu leerem `{}` statt Fehler. **User glaubt Save erfolgreich, aber Daten sind weg.**

**TODO/FIXME: 0 gefunden.**

---

## 6. Unused Imports / Dead Code

Gesamtes File: Alle Imports werden genutzt. `flash` eingesetzt, `g` eingesetzt, `jsonify` eingesetzt. **Null dead code in dieser Datei.** Sauber.

---

## 7. Hypothesen-Check

| Hypothese aus Briefing | Status | Befund |
|---|---|---|
| H1: Schema-definiert oder "alles geht"? | **Bestätigt** | Alles geht. Silent Fallback bei Parse-Fehler. **LB-11.** |
| H2: Regex-Validity geprüft? | **N/A (irrelevant)** | Matcher liest User-Regex nicht. Siehe H-20. |
| H3: Org-Scoping konsistent? | **Bestätigt mit einer Lücke** | Profile+FAQ-Pfade sauber. Skripte/Opener hängen an Parent-Check (kein eigener org_id — fragil). |
| H4: Concurrent-Write-Safety? | **Bestätigt — keine** | Kein Optimistic Lock, kein Version-Column. **LB-10.** |
| H5: Welche CRUD-Routes existieren? | **Bestätigt** | Profile, ProfileSkript, ProfileOpener, ProfileFaq — alle 4 Tables haben CRUD. Plus `api/tabu` als Sub-Operation auf Profile.daten. |
| H6: `consent_text` gelesen? | **Wie Welle 1** | Geschrieben in `bearbeiten` (Z.167). Nirgends gelesen von LLM-Pfad (Phase-A-Matrix bestätigt). Nur im HTML-Editor-Template. |
| H7: Audit-Event bei Profile-Change? | **Partiell** | Nur `profile_update` bei `bearbeiten`. Kein create/delete/activate/tabu/faq/skript/opener. **H-17.** |
| H8: `_seed_demo_profiles` beim Registrieren? | **Widerlegt — kritisch** | Seed läuft 1x beim App-Start, nur für Org "NERVE Alpha". Neue User bekommen nichts. **LB-9.** |
| H9: Tabu-Drift Python ↔ JS? | **Bestätigt** | M-4. |

---

## 8. Sicherheits-Check (Bonus)

- **CSRF:** Nicht in der Datei sichtbar — hängt an globalem Flask-Setup. Nicht geprüft.
- **Input-Sanitization:** `.strip()` auf Name/Branche. Kein HTML-Escape. DB speichert roh. Rendering muss Template-Escape vertrauen. Rich-Text-Bodies (inhalt) werden 1:1 an Frontend geschickt — bei XSS-Reflection möglich wenn Frontend `innerHTML` nutzt statt `textContent`. **Cross-Check mit Frontend-Audit in Welle 4 nötig.**
- **File-Upload:** Keine Upload-Endpoints in dieser Datei.
- **SQL-Injection:** ORM-only, keine Raw-SQL. ✅
- **Rate-Limiting:** Keine Decorator sichtbar. Wenn globales Rate-Limit in app.py fehlt → API-FAQ/Tabu können gespammt werden.

---

## 9. Empfehlungen priorisiert

### Vor EA-Launch (Launch-Blocker)
1. **LB-9** beheben — Onboarding-Redirect aktivieren oder Auto-Seed bei Register (1-2h). **Ohne das ist EA-UX gebrochen.**
2. **H-16** Rollen-Check für FAQ/Tabu-API (15 min). Einfach.
3. **H-19** Rollen-Check in `wizard_create` nach LB-9-Entscheidung (5 min).
4. **Wizard-Schema-Alignment** — `wizard_create` muss in `basis.*` Struktur schreiben statt Top-Level (Teil von H-13 Cross-Route-Fix, ~1h).
5. **H-17** Audit-Events für create/delete/activate + Feld-Diff in update (2-3h) — mindestens für DSGVO-relevante Felder (consent_text).

### Phase Stabilisierung (vor Multi-User-Plänen)
6. **LB-10** Optimistic Lock + pro-Session Active-Profile-State (3-4h).
7. **LB-11** Pydantic-Schema für Profile.daten (4-6h, Teil Phase-C Profil-Redesign).
8. **H-18** aktivieren Commit-Reihenfolge (1-2h).
9. **M-4** Tabu-Default-Pairs Backend-Source (2-3h).
10. **M-2** Cascade-Delete verifizieren + absichern (30 min).

### Technische Schulden
11. M-1, M-3, M-5, M-7, M-8, M-9, M-10 — insgesamt ~4-5h sammelbar.
12. H-20 Verifikation ob UI Regex-Felder offeriert die tot sind — 30 min.

---

## 10. Cross-Refs & Pattern-Bestätigung

- **H-13 (MASTER-AUDIT) bestätigt:** `wizard_create` schreibt `produkt` Top-Level → `/api/frage` liest `pdata.get("produkt")` Top-Level. Zwei Routes teilen denselben Schema-Drift-Fehler. Der Editor hingegen rendert `basis.produktbeschreibung`. → Drei Parteien, drei Schemas. **Der Wizard ist eine dritte Schema-Definition.**
- **LB-3 (QA-Pipeline leerer profile_data) × LB-9 (kein Startprofil):** Multiplikativer Effekt. Selbst wenn LB-3 gefixt — ohne Profil ist Context sowieso leer. Beides muss für EA laufen.
- **Phase-A-Matrix bestätigt:** `consent_text` im Editor editierbar → Feld existiert in DB → LLM liest es nie. Feature-Fake-Pattern wie PreCall.
- **Welle-2-Befund "Profile.daten kein Schema-Validator":** Hier mit Code-Referenz belegt (Z.62-66, 158-162).

---

## 11. Zahlenbilanz dieser Datei

| Dimension | Wert |
|---|---|
| Zeilen gesamt | 577 |
| Routes | 17 (inkl. GET+POST-Paare) |
| Launch-Blocker-Kandidaten (neu) | 3 (LB-9, LB-10, LB-11) |
| HIGH-Severity-Funde | 5 (H-16 bis H-20) |
| MEDIUM-Severity-Funde | 10 (M-1 bis M-10) |
| Silent fallbacks | 4 |
| Dead code | 0 |
| Unused imports | 0 |
| Audit-Events | 1 von ~14 nötig |
| Rollen-inkonsistente Routes | 4 (wizard_create, aktivieren, FAQ-CRUD, Tabu-Update) |

---

*Audit abgeschlossen 2026-04-24 durch Code-Reading von routes/profiles.py + Cross-Refs. Routes in Welle 3 als nächstes: app_routes.py, training.py, coach.py, admin_dashboard.py — unabhängig vom Rate-Limit-Reset bereits ausgeführt.*
