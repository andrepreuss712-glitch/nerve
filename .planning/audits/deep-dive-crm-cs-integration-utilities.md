# Deep-Dive Audit — Welle 2: CRM / Customer-Success / Integration-Engine / Profile-Migration / EUR / FX / Auth

**Datum:** 2026-04-24
**Scope:** 7 verbleibende Service-Dateien
**Methode:** Vollständig gelesen, Grep-Call-Graph über gesamte Codebase, Doc-vs-Code-Cross-Check
**Kernregel:** Code gilt. Doku kann lügen.

**Dateien (alle gelesen [x]):**
- [x] `services/crm_service.py` (67 Zeilen)
- [x] `services/customer_success_service.py` (178 Zeilen)
- [x] `services/integration_engine.py` (277 Zeilen)
- [x] `services/profile_migration.py` (107 Zeilen)
- [x] `services/eur_calculator.py` (173 Zeilen)
- [x] `services/exchange_rates.py` (174 Zeilen)
- [x] `services/auth_decorators.py` (12 Zeilen)

---

## TL;DR

| Datei | Status | Haupt-Befund |
|---|---|---|
| `crm_service.py` | LIVE, sauber | Eager module-level `anthropic.Anthropic()` Client — unnötige API-Key-Dependency beim Import. Kein Retry/Timeout, kein JSON-Validate. |
| `customer_success_service.py` | LIVE, sauber | Mini-Bug: `_days_inactive` ruft `.get()` auf SQLAlchemy-User-Objekt (letzte_aktivitaet), das funktioniert nicht. Nur relevant wenn u['last_call']=None. |
| `integration_engine.py` | LIVE, funktionsreich | SQLite-lock-in (`json_extract`), `ga_details`-Parameter unused, `needs_learning_card`-Flag tot (nie an Caller zurückgegeben). |
| `profile_migration.py` | LIVE, sauber | Einzige Fundstelle von Tests (test_tabu_migration.py). Nur EIN Call-Site in routes/profiles.py:181. |
| `eur_calculator.py` | LIVE, sauber | Gut getestet (9 Tests). Stripe-VAT-Hardcode 0.19 — semi-legitim. |
| `exchange_rates.py` | LIVE, mit bekanntem Bug | `get_current_rate()` leakt auf Live-DB (2 Tests failen, in 04.7.2-VERIFICATION dokumentiert, bewusst nicht gefixt). |
| `auth_decorators.py` | LIVE, minimal | **Nur `superadmin_required`**. Kein `login_required` darin — Doku in STRUCTURE.md lügt. |

Kein krasser Nudelcode gefunden. Aber **mehrere kleine Abweichungen zwischen Doku und Code**, ein paar tote Variablen, und der bekannte FX-Test-Leak.

---

## 1) services/crm_service.py

**Zweck:** Post-Call Claude-Haiku-Call, erzeugt CRM-Notiz + Follow-up-Email + nächste Schritte (JSON).

**Kein Stub, echtes Feature.** DSGVO-Modus-Switch funktioniert via Prompt-Instruction.

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `generate_crm_export(...)` | **LIVE** | `routes/app_routes.py:353-361` (Post-Call-Hook in `api_beenden`). Einzige Produktiv-Aufrufstelle. |

Keine externen CRMs (HubSpot, Salesforce, Pipedrive, Zendesk) werden angesprochen. Trotz STRUCTURE.md-Kommentar `# CRM integration (Hubspot, Salesforce stubs)` sind **keine Stubs** für externe Systeme vorhanden. Der Dateiname ist irreführend — es geht um Claude-generierte Gesprächsnotizen, nicht um CRM-APIs.

### Befunde

| # | Schwere | Befund |
|---|---|---|
| CRM-1 | Low | **Eager Client-Initialisierung:** `_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)` bei Modul-Import (Z.5). Wenn ANTHROPIC_API_KEY fehlt, crasht der gesamte `from services.crm_service import` — trotz `try/except` in `app_routes.py:352` (das wird getriggert, aber der Import-Aufruf wiederholt sich bei jedem Call → Initialisierung wird bei jedem Call neu angestoßen, da in `try` drin. Eher ineffizient als broken). |
| CRM-2 | Low | **Kein Timeout/Retry.** Wenn Claude 10s hängt, blockiert der gesamte `/api/beenden`-Request. |
| CRM-3 | Low | **Blindes `json.loads(text[start:end])`** (Z.67) — kein Validate ob `crm_notiz` / `followup_email` / `naechste_schritte` tatsächlich vorhanden. `api_routes.py` ruft `.get(...)` mit Default, absichert also den Fall — aber schlechter Service-Contract. |
| CRM-4 | Low | **DSGVO-Schutz reiner Prompt-Hint.** Keine technische Durchsetzung — Claude kann im Zweifel Kundennamen zurückschreiben, wenn er das Transkript ehrlich liest. Müsste man mit Post-Regex-Scrub verhärten wenn das ein echtes Rechtsrisiko wird. (CONCERN: siehe 04 Entscheidungen/NERVE DSGVO Analyse) |
| CRM-5 | Info | **Modell-Hardcode:** `claude-haiku-4-5-20251001` (Z.60) — zentral, aber nicht aus `config.py`. Bei Model-Migration muss man manuell durch alle Services. |
| CRM-6 | Info | **Feature-Flag:** `org.dsgvo_modus` (vom Caller übergeben) — Default True. Kein Flag der das ganze Modul abschaltet. |

### DB-Zugriffe
Keine. Nur `config.ANTHROPIC_API_KEY` + Claude-HTTP-Call.

---

## 2) services/customer_success_service.py

**Zweck:** Aggregiert Call-Stats pro User + berechnet Status-Badge (top/aktiv/ruhig/churn) + Follow-up-Hints. Phase 04.14.

**Echte Business-Logic**, klar strukturiert. Per D-03/D-01/D-02/D-09/D-10 gebaut.

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `get_all_user_crm_data(db)` | **LIVE** | `routes/admin_views.py:177` (`CrmView.index`) |
| `get_followup_hints(users_crm)` | **LIVE** | `routes/admin_views.py:178` |
| `STATUS_LABELS` | **LIVE** | exported via `from ... import ...` in Plan, genutzt in `get_all_user_crm_data` |
| `_compute_status(...)` | INTERNAL | nur intern |
| `_days_inactive(u)` | INTERNAL | nur in `get_followup_hints` |
| `_days_since_call(u)` | INTERNAL | nur in `get_followup_hints` |

### Befunde

| # | Schwere | Befund |
|---|---|---|
| CS-1 | **Mittel** | **`_days_inactive(u)` greift auf `u.get('letzte_aktivitaet')`** (Z.168). Der `u`-Dict wird in `get_all_user_crm_data` aus `{'letzte_aktivitaet': u.letzte_aktivitaet}` (Z.76) korrekt befüllt — OK. Aber Kommentar in CONTEXT/RESEARCH behauptet `u` enthält das SQLAlchemy-Objekt direkt. Hier ist Code korrekter als Doku. **Kein Bug, nur Verwirrungspotential.** |
| CS-2 | Low | **Skalierung:** `db.query(CrmNote).all()` + `db.query(User).filter(...).all()` — OK für Dutzende bis Hunderte User, bei 10k+ Users O(N) Memory. Kommentar Z.47 erwähnt "small table" — validiert. |
| CS-3 | Low | **`einwand_rate=0` wenn `einwaende_total=0`** (Z.59-61) — korrekt, keine Division-by-zero. |
| CS-4 | Low | **`cutoff_30d` wird nur als Filter für call_stats verwendet**, `cutoff_7d`/`cutoff_14d` an `_compute_status` weitergegeben. Sauber. |
| CS-5 | Info | **Sort-Order** `churn>ruhig>aktiv>top` (0,1,2,3) — Churn-Gefahr oben, richtig priorisiert. |
| CS-6 | Info | **D-10 Performance-Hints** (Z.144-159) generieren bei avg_kb<40 ODER einwand_rate<30 einen Hint — kann pro User mehrere Hints erzeugen. Bewusst so. |

### DB-Zugriffe
- Session wird vom Caller (`admin_views.CrmView.index`) via `get_session()` + `try/finally db.close()` verwaltet (korrekt, kommentiert Z.19-21).
- Kein `db.commit()` hier — Service ist read-only.

---

## 3) services/integration_engine.py

**Zweck:** Phase 04.12 — Synchrone Post-Call und Post-Training Engine. Event-Logging + Pattern-Detection für Training-Empfehlungen. Kein Background-Worker.

**Größter Service dieser Welle, voll implementiert.** Nicht trivial.

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `log_learning_event(...)` | **LIVE** | `services/integration_engine.py` selbst (4x), `routes/app_routes.py:1309` (call_rated), `routes/learning.py:98,157,190,224` (4 learning-card-Events) |
| `run_postcall_engine(...)` | **LIVE** | `routes/app_routes.py:637` (nach `api_beenden` commit) |
| `run_posttraining_engine(...)` | **LIVE** | `routes/training.py:780` (nach Training-Session) |
| `_escape_like(value)` | INTERNAL | nur in `_persist_training_recommendation` |
| `_persist_training_recommendation(...)` | INTERNAL | 2 Call-Sites innerhalb des Moduls |
| `_maybe_clear_training_recommendation(...)` | INTERNAL | nur in `run_posttraining_engine` |
| `VALID_EVENT_TYPES` / `VALID_SOURCE_MODULES` | Konstanten | Validator-Whitelist |

### Befunde

| # | Schwere | Befund |
|---|---|---|
| IE-1 | **Mittel** | **`ga_details` Parameter in `run_postcall_engine` (Z.129) wird nie benutzt.** Im Funktionskörper kein einziges Vorkommen. Caller (`app_routes.py:643`) übergibt `ga_details=ga_details`. Klassischer **orphan parameter**. Kein funktionaler Bug, aber Abrieb bei Refactoring. |
| IE-2 | **Mittel** | **`needs_learning_card` Flag ist tot** (Z.245, Z.264). Wird in `run_posttraining_engine` lokal gesetzt, aber **nie returned**, **nie propagiert**. Phase 04.12-02-PLAN.md Z.144-145 sagt explizit: "Das needs_learning_card Flag wird in Plan 03 verwendet". Plan 03 der Phase 04.12 wurde offenbar gebaut aber das Flag wurde dort nicht angebunden. Eher Doku-Artefakt als aktiver Code-Pfad. |
| IE-3 | **Mittel** | **SQLite-Lock-in über `json_extract()`** (Z.163, Z.190, Z.257). Auskommentiert "NOTE: json_extract() is SQLite-specific. For PostgreSQL migration, replace with ->> operator". Harter Blocker für PostgreSQL-Migration die laut 02 Stand geplant ist. Dokumentiert → OK aber **muss auf die Migrations-Checkliste**. |
| IE-4 | Low | **Silent-Failure by design** (D-03/D-04). Alle drei Exception-Handler loggen nur `print(...)`. Kein `logger.exception()`. Wenn Engine silent scheitert, sieht das nur wer in journalctl guckt. Für Post-Launch: Sentry-Hook oder strukturiertes Logging. |
| IE-5 | Low | **`break` nach erster Empfehlung** (Z.173) — nur eine Empfehlung pro Engine-Lauf. Bewusst, kommentiert. |
| IE-6 | Low | **`datetime.now()` statt `datetime.utcnow()`** (Z.139, Z.248, Z.93). `_compute_status` in customer_success_service nutzt `utcnow()`. **Inkonsistenz** — LearningEvent-Timestamps sind lokal, ConversationLog-cutoffs sind UTC. In DE sommers 2h Diff. Eher Low weil Lookback 30 Tage, aber am Tagesgrenzrand Fehlerquelle. |
| IE-7 | Low | **`_persist_training_recommendation` committed selbst** (Z.97) — während `log_learning_event` den Commit dem Caller überlässt. Pattern-Inkonsistenz, aber dokumentiert in Docstring. |
| IE-8 | Info | **Print-Statement-Logging** durchgehend statt `logging` module. |

### DB-Zugriffe
- Lazy imports (`from database.models import LearningEvent` etc.) innerhalb der Funktionen — verhindert Zirkular-Imports, Pattern konsistent.
- Session-Ownership: Caller committet bei `log_learning_event`; Engine-Entrypoints committen selbst am Ende.
- `db_session.commit()` auf Line 154, 242, 97, 120. Keine `db_session.close()` — korrekt, Caller schließt.

---

## 4) services/profile_migration.py

**Zweck:** Phase 08.5 Korrektur. Migriert `profile.daten.basis.tabu_begriffe` von String-List auf Object-List mit `{begriff, alternative}`.

**Sauber, testabgedeckt, idempotent.** Einziges Service-Modul mit echten Tests (`tests/test_tabu_migration.py`).

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `migrate_tabu_begriffe(profile_daten)` | **LIVE** | `routes/profiles.py:8` (import), `routes/profiles.py:181` (Aufruf beim Laden eines Profils) |
| `TABU_DEFAULT_PAIRS` | **LIVE** | Re-exportiert, 13 Default-Paare |
| `_DEFAULT_OBJECTS` | INTERNAL | intern im Modul |
| `_normalize_entry(entry)` | INTERNAL | intern |

Frontend (`static/profile_editor.js:131-154`) dupliziert die `TABU_DEFAULT_PAIRS`-Liste manuell. Bei Änderung müssen **beide Stellen synchron** gehalten werden. Kommentar im JS erwähnt das explizit ("mirror services/profile_migration.py"). Sauber dokumentiert, aber Abrieb-Quelle.

### Befunde

| # | Schwere | Befund |
|---|---|---|
| PM-1 | Low | **Frontend/Backend Source-of-Truth-Duplikat** — `TABU_DEFAULT_PAIRS` in Python UND JavaScript separat gepflegt. Nur durch Kommentar verbunden. |
| PM-2 | Low | **`not isinstance(raw, list)` → reset auf Defaults** (Z.89-91). Bedeutet: wenn jemand `tabu_begriffe: "Kosten"` (String statt Liste) in DB hat, wird das überschrieben ohne Warnung. Für jetzt OK, Reset-Stand. |
| PM-3 | Info | **Python 3.10+ Syntax:** `list[tuple[str, str]]`, `dict | None` (Z.20, Z.41). Setzt Python >=3.10 voraus — in Hetzner-VPS-Deploy-Env prüfen. |
| PM-4 | Info | **Nur 1 Call-Site** in `routes/profiles.py`. Sollten weitere Profil-Laden-Stellen existieren (Live-Session-Init?), muss dort auch migriert werden. Siehe Welle 1 — `live_session._load_initial_profile` wurde als Load-Pfad identifiziert. **Hier prüfen ob Live-Session den migrierten Datensatz sieht oder den DB-Rohzustand lädt.** |

### DB-Zugriffe
Keine. Pure Python — arbeitet auf dict in-place. Caller (`routes/profiles.py:181`) hat die Session.

---

## 5) services/eur_calculator.py

**Zweck:** Phase 04.7.2. Berechnet Anlage-EÜR + USt-VA für einen Zeitraum. §13b Reverse-Charge-Logik. Steuerkritisch.

**Voll implementiert, 9 Unit-Tests.** Sign-Off HT-04 (count.tax) laut File-Docstring vor erstem produktiven Einsatz nötig.

### Call-Graph

| Funktion / Konstante | Status | Caller |
|---|---|---|
| `compute_eur(...)` | **LIVE** | `routes/admin_dashboard.py:652, 675, 699, 825` (4 Endpunkte: eur_data, eur_pdf, eur_csv, eur_preview) |
| `RC_13B_PROVIDERS` | **LIVE** | `tests/test_eur_calculator.py:133-136` — im Produktivcode **nur intern** in compute_eur referenziert. Export-Konstante aber nicht von außen genutzt. |
| `EUR_LINES` | **DEAD-ish** | Wird **nirgendwo importiert** außer vom Test-Plan erwähnt. Export-Constant ohne Consumer. |
| `UST_KZ` | **DEAD-ish** | Analog zu EUR_LINES. |
| `_cents_to_eur(c)` | INTERNAL | intern |
| `_sum_treatment(...)` | INTERNAL | intern |
| `_sum_provider(...)` | INTERNAL | intern |

### Befunde

| # | Schwere | Befund |
|---|---|---|
| EUR-1 | Low | **`EUR_LINES` und `UST_KZ` Export-Konstanten sind faktisch ungenutzt.** Phase-Plan 04.7.2-06 deklariert sie als Exports, aber **kein Template, kein PDF-Renderer, keine Route** importiert sie. Nur im Code selbst zur Dokumentation. Könnten gelöscht oder in Template-Layer gezogen werden. |
| EUR-2 | Low | **Stripe-Gebühr hardcoded 19% VAT** (Z.107-109) — richtig für Stripe Deutschland-Konto, aber als Magic Number. Sollte aus FixedCost-Config kommen wenn skalierbar. |
| EUR-3 | Low | **`home_days`-Param default 0** (Z.59) — wenn jemand beim CSV-Export vergisst, Home-Days zu übergeben, wird Z65_homeoffice mit 0 berechnet und das Ergebnis ist falsch. Alle 4 Call-Sites in `admin_dashboard.py` übergeben `home_days` explizit — OK. |
| EUR-4 | Low | **Kein `try/except` um DB-Queries** — wenn `db.query(RevenueLog)` crasht, crasht die gesamte EÜR-Berechnung. Für admin-only Dashboard akzeptabel. |
| EUR-5 | Low | **`fc_by_line = {52: [], 57: [], 65: []}`** (Z.82) — hardcoded Lines. Wenn `fc.eur_line` auf eine andere Line als 52/57/65 zeigt (z.B. 14), wird sie per `fc_by_line.setdefault(line, [])` (Z.96) hinzugefügt — aber **nie in Output aggregiert**. Z.14 wäre eine Einnahmen-Line und gehört da eh nicht hin; aber wenn jemand `eur_line=26` einträgt (Z26 Fremdleistungen), landet das im `fc_by_line[26]` und verschwindet aus dem Ausgaben-Total. **Silent Data Loss möglich.** |
| EUR-6 | Info | **KZ67 = KZ85 Invariant** (Z.120) — per §13b immer identisch. Test `test_reverse_charge_13b` prüft das grün. |

### DB-Zugriffe
- Session wird als Parameter reingereicht — Caller-Ownership.
- Nur Reads (query/scalar/sum). Kein commit, kein close.

---

## 6) services/exchange_rates.py

**Zweck:** Phase 04.7.2. Frankfurter-API USD→EUR Daily-Sync via APScheduler, mit Multi-Worker-File-Lock.

**Funktional, aber bekannter Bug** in `get_current_rate()` aus 04.7.2-VERIFICATION.md.

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `fetch_usd_eur()` | LIVE | intern (`update_daily_rate`); Tests. Keine externen Caller. |
| `update_daily_rate()` | LIVE | intern (Scheduler-Job `fx_daily`); `start_scheduler()`-Initial-Run; Tests. |
| `get_current_rate(...)` | **LIVE** | `routes/admin_dashboard.py:429-430` (**einziger** Produktiv-Call). |
| `_acquire_worker_lock()` | INTERNAL | intern |
| `start_scheduler()` | **LIVE** | `app.py:792` beim Startup. |

**`cost_tracker._get_current_fx_rate` ist eine DUPLIKAT-Implementierung** (Z.14-28 in cost_tracker.py) der gleichen Logik ohne exchange_rates-Service zu nutzen. Cost_tracker ignoriert `exchange_rates.get_current_rate()` komplett und queryt `ExchangeRate` selbst. Zwei Pfade, ein Truth → Abrieb-Risiko.

### Befunde

| # | Schwere | Befund |
|---|---|---|
| FX-1 | **Mittel** | **`get_current_rate()` Live-DB-Leak** (bekannt, in 04.7.2-VERIFICATION.md dokumentiert, nicht gefixt). Die Funktion ruft `get_session()` selbst auf, ignoriert pytest-db_session-Fixture. 2 Tests failen deshalb permanent. Wurde "out-of-scope" verschoben. **Muss gefixt werden bevor Phase 04.7.2 wirklich als done zählt.** |
| FX-2 | **Mittel** | **Duplizierte FX-Rate-Abfrage in cost_tracker.py:14-28** (`_get_current_fx_rate`). Wenn sich Fallback-Kurs (0.92) ändert oder neue Currency-Pairs dazukommen, müssen beide Stellen editiert werden. Ein Pfad zu einem Source-of-Truth zusammenführen. |
| FX-3 | Low | **Fallback-Kurs 0.92 ist hart** (Z.94). Bei leerer Tabelle und FX-Down nutzt die ganze Anwendung einen 2-Jahre-alten Wert ohne Warnung. Min. Log-Warn bei Fallback-Einsatz wäre besser. |
| FX-4 | Low | **`_scheduler_instance` globaler Module-State** (Z.17) — für Test-Isolation problematisch, für Single-Process-Deploy OK. |
| FX-5 | Low | **Kein Lock-TTL / Stale-Lock-Handling perfekt:** wenn PID-Check via `os.kill(pid, 0)` auf Windows (Dev) falsch reagiert, könnte Lock nie freigegeben werden. Auf Hetzner-VPS Linux egal. |
| FX-6 | Info | **APScheduler optional** (try/except ImportError Z.152-155) — Scheduler wird silent disabled wenn nicht installiert. Sollte mindestens einmal am Start laut loggen. |
| FX-7 | Info | **Frankfurter-Fehler = silent skip, letzter Kurs bleibt gültig** — bewusst (Docstring). Gut. |

### DB-Zugriffe
- `update_daily_rate()` und `get_current_rate()` öffnen eigene Sessions via `get_session()` + `try/finally close()`. Korrekt, aber macht Test-Mocking unmöglich (daher FX-1).

---

## 7) services/auth_decorators.py

**Zweck:** Flask-Decorator für Superadmin-Gate. 12 Zeilen.

**Minimal, sauber. Kein `login_required` hier drin — trotz Behauptung der Doku.**

### Call-Graph

| Funktion | Status | Caller |
|---|---|---|
| `superadmin_required(f)` | **LIVE** | `routes/admin_dashboard.py` (**17x**), `routes/admin_views.py:222,225`, `routes/admin_ewb.py:21,56,125,174` (3x) → **insgesamt ~21 Routes gated** |

### Befunde

| # | Schwere | Befund |
|---|---|---|
| AUTH-1 | **Mittel (Doku-Drift)** | **STRUCTURE.md Z.35 behauptet:** `auth_decorators.py          # login_required, admin_required decorators`. **CODE:** nur `superadmin_required`. Kein `login_required`, kein `admin_required`. **`login_required` lebt tatsächlich in `routes/auth.py:42`** — ARCHITECTURE.md Z.308 behauptet das Gleiche falsch. Doku-Korrektur Pflicht. |
| AUTH-2 | Low | **Keine Session-Validierung hier** — `superadmin_required` liest nur `g.user`, setzt aber nicht. `login_required` in `routes/auth.py` muss vorher laufen. **Reihenfolge-kritisch:** `@login_required` MUSS vor `@superadmin_required` stehen — sonst ist `g.user` None und direkter 403 ohne Login-Redirect. |
| AUTH-3 | Low | **Keine Role-Enum, nur Bool `is_superadmin`.** Per D-08 bewusst. Wenn mehr Rollen (Admin, Billing-Admin) kommen, muss der Decorator erweitert werden. |
| AUTH-4 | Info | **`getattr(g, 'user', None)` Double-Guard** (Z.8) — korrekt, kein AttributeError wenn `g.user` nie gesetzt wurde. |

### DB-Zugriffe
Keine. Liest nur `g.user`.

---

## Cross-File-Observations

### A) Parallele Exchange-Rate-Logik (cost_tracker vs exchange_rates)
`services/cost_tracker.py:14-28` dupliziert `exchange_rates.get_current_rate()` als `_get_current_fx_rate()`. **Zwei Wahrheiten für dieselbe Abfrage.** Konsolidieren auf einen Service-Entry-Point — idealerweise eine Funktion die optional eine db-Session akzeptiert (→ fixt gleichzeitig FX-1).

### B) Engine-Parameter-Drift (ga_details orphan)
`run_postcall_engine(..., ga_details)` akzeptiert einen Parameter der nicht benutzt wird. Caller übergibt ihn. Entweder (a) raus oder (b) endlich einen Use-Case implementieren (z.B. `successful_einwaende` für feingranulare Events).

### C) Tote Flag-Kette `needs_learning_card`
Phase 04.12-02 setzt `needs_learning_card=True` in `run_posttraining_engine`, aber Plan 03 wurde offenbar nie anschlossen. Flag hat keine Wirkung. Entweder entfernen oder Lernkarten-Hook bauen.

### D) Doku-Lügen ausgeräumt
| Doku-Quelle | Behauptung | Realität |
|---|---|---|
| `STRUCTURE.md:31` | `crm_service.py # CRM integration (Hubspot, Salesforce stubs)` | Kein HubSpot/Salesforce-Stub. Reine Claude-Haiku-Notiz-Generierung. |
| `STRUCTURE.md:32` | `customer_success_service.py # Customer support coordination` | Präziser: Status-Badge + Follow-up-Hints für internes CRM-Dashboard. |
| `STRUCTURE.md:35` | `auth_decorators.py # login_required, admin_required decorators` | Nur `superadmin_required`. `login_required` sitzt in `routes/auth.py:42`. |
| `ARCHITECTURE.md:308` | `auth_decorators.py: Validates user_id in session, attaches to Flask g` | Falsch. Attaching erfolgt in `routes/auth.py login_required`. |

### E) `json_extract` SQLite-Lock
Hart eincodiert in `integration_engine.py` an 3 Stellen. PostgreSQL-Migration (per 02 Stand geplant) kann nicht ohne Refactoring dieses Services laufen. **Pruning-Pflicht erwähnen in 05 Log.**

### F) Superadmin-Decorator-Benchmark
~21 Routes nutzen `@superadmin_required`. Aus Security-Perspektive solide Konvention. Eine Fuzz-Route (`admin_feedback_screenshot` in `admin_views.py:222-232`) hat den Decorator dynamisch durch `app.route` — easier zu übersehen. Grep-Check auf alle Admin-Routes könnte periodisch automatisiert werden (vielleicht in Pre-Commit Hook).

---

## Priorisierte Fix-Liste

### MUSS (vor Launch / vor nächstem Schema-Schwenk)

1. **FX-1:** `exchange_rates.get_current_rate()` DB-Session-injizierbar machen. 2 pre-existing Test-Failures grün kriegen. *(Test-Fix + Prod-Hardening in einem)*
2. **FX-2 / Cross-A:** `cost_tracker._get_current_fx_rate` → `exchange_rates.get_current_rate` konsolidieren. Ein Fallback, eine Wahrheit.
3. **AUTH-1 / Cross-D:** STRUCTURE.md + ARCHITECTURE.md bzgl. `auth_decorators.py` korrigieren. 5-Minuten-Fix.
4. **IE-3:** SQLite `json_extract`-Stellen in integration_engine.py als "MIGRATION-BLOCKER" in ROADMAP markieren.

### SOLLTE (Abrieb vermeiden)

5. **IE-1:** `ga_details`-Parameter aus `run_postcall_engine` raus oder Use-Case bauen.
6. **IE-2 / Cross-C:** `needs_learning_card`-Flag entfernen oder Lernkarten-Integration nachholen.
7. **EUR-5:** `fc_by_line` um Validate-Check erweitern — unbekannte `eur_line` warnen/fehlschlagen statt silent drop.
8. **CRM-1:** `crm_service._client` in lazy-init umbauen (lock + globals) — kein Crash bei Import ohne API-Key.
9. **EUR-1:** `EUR_LINES` / `UST_KZ` exports entweder nutzen (im Template/PDF-Renderer) oder private machen.

### NICE TO HAVE

10. **CRM-2:** Claude-Call in `crm_service` mit Timeout 15s + 1 Retry umbauen.
11. **IE-6:** `datetime.now()` → `datetime.utcnow()` in integration_engine (UTC-Konsistenz mit Rest der Codebase).
12. **PM-1:** Zentrale JSON-Konstante für `TABU_DEFAULT_PAIRS` die Backend und Frontend teilen (build-time import oder API-Endpoint).

---

## Status: Audit abgeschlossen

Kein Nudelcode auf Phase-08.5-Niveau gefunden. Aber mehrere Doku-Drifts, 1 bekannter nicht-gefixter Bug (FX-1), 2 orphan-Parameter/Flags, und ein Source-of-Truth-Duplikat (FX-Rate-Lookup). Das ist der Normalzustand einer Codebase die unter Druck gebaut wurde — nicht bedrohlich, aber pflegebedürftig bevor PostgreSQL-Migration oder echter Launch ansteht.
