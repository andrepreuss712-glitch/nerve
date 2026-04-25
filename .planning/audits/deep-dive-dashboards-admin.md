---
audit: deep-dive-dashboards-admin
erstellt: 2026-04-24
autor: Claudian (Welle 3 Deep-Dive-Agent)
scope:
  - routes/dashboard.py (988 Zeilen — User-Dashboard, Session-Detail, Nudges, Analytics)
  - routes/admin_dashboard.py (878 Zeilen — Founder-Cost-Dashboard, Phase 04.7.2)
  - routes/admin_views.py (232 Zeilen — Flask-Admin ModelViews + Custom-Views)
basiert_auf:
  - .planning/audits/MASTER-AUDIT.md (LB-5 `org_id` Ghost bekannt)
  - Gegen-verifiziert: services/auth_decorators.py, routes/auth.py (login_required),
    database/models.py (ApiCostLog, RevenueLog, ConversationLog, FixedCost, User),
    app.py Z.1728-1764 (Admin-Blueprint-Registrierung, SecureIndexView),
    services/customer_success_service.py, templates/analytics.html
---

# Deep-Dive — Dashboards & Admin-Routes

**Budget:** ~18 Min. Kernbefund: 2 neue Launch-Blocker (**LB-9 + LB-10**),
4 HIGH-Severity, mehrere MEDIUMs. Auth-Gating grundsätzlich sauber (alle
Admin-Pfade `@superadmin_required` + Flask-Admin `is_accessible`-Gate), aber
**zwei Ghost-Columns sprengen Flask-Admin-Sessions-View + Analytics-Seite
komplett** und mindestens ein weiteres silent-failure-Muster im KPI-Dashboard.

---

## EXECUTIVE SUMMARY

| Severity | Count | Worst |
|---|---|---|
| 🔴 Launch-Blocker | 2 (neu) | LB-9 Flask-Admin Sessions-View wirft AttributeError |
| 🟠 HIGH | 4 | H-16 Analytics-Seite zeigt für jede Session 0 Einwände (Ghost-Reader) |
| 🟡 MEDIUM | 7 | KPI-Dashboard `feedback_new/planning`-Count läuft auf falsche Tabelle |
| 🟢 LOW | 5 | ROI-Rechnung hat Branche hardcoded auf 'Sonstiges' |

**Kernbefund:** admin_dashboard.py selbst ist **solide gebaut** — Gating,
Period-Parsing, CSV-Export, SQL-Aggregationen sind diszipliniert. Der
Launch-Blocker-Grund (LB-5, alle `ApiCostLog.org_id = NULL` → Kunden-Tab
zeigt 0 € pro Org) liegt NICHT in admin_dashboard.py, sondern im Writer in
`deepgram_service.py:351`. Die Route ist Opfer, nicht Täter.

admin_views.py hat ein **Ghost-Column-Bug-Duo** (`einwaende_total` /
`einwaende_ok`) das Flask-Admin-Sessions-View + Analytics-Seite still oder
laut brechen lässt — seit Phase 04.7-05 drin, nie verifiziert.

dashboard.py ist User-Dashboard-Machinerie mit vielen Stil- und
Hardcode-Sünden, aber keine Launch-Blocker. Ghost-Reader für
`state['precall_briefing']` ist der einzige funktional-kritische Befund —
bestätigt H-2 aus MASTER-AUDIT (PreCall-Briefing Feature-Fake) auch hier.

---

## 🔴 LAUNCH-BLOCKER

### LB-9: Flask-Admin Sessions-View crasht auf Ghost-Columns (NEU)

**Evidence:** `routes/admin_views.py:96-97`:
```python
class ConvLogAdmin(SecureModelView):
    column_list = ('id', 'user_id', 'session_mode', 'dauer_sekunden', 'einwaende_total',
                   'einwaende_ok', 'started_at', 'ended_at')
```
**Gegen-verifiziert** in `database/models.py` Z.244-261: `ConversationLog` hat
**KEINE** Columns `einwaende_total` oder `einwaende_ok`. Die echten Namen
sind `einwaende_gesamt` und `einwaende_behandelt` (Z.257-258).

**Grep-Bestätigung:** `einwaende_total|einwaende_ok` = 0 Treffer in
`database/models.py`. Überall wo der Name auftaucht wird er aus
`einwaende_gesamt/_behandelt` umbenannt — außer in admin_views.py und
analytics.html.

**Folge:** Sobald ein Superadmin `/admin/convlog/` öffnet (Flask-Admin
ModelView) wirft Flask-Admin `AttributeError: 'ConversationLog' object has
no attribute 'einwaende_total'`. Je nach Flask-Admin-Version entweder
500-Error-Seite (LB-7 würde Traceback leaken!) oder leere Tabelle.

**Phase-Doku-Lüge:** Phase-04.7-05-PLAN Z.299 baute diesen Fehler ein und
nie jemand hat `/admin/convlog/` tatsächlich geöffnet.

**Fix-Aufwand:** 1 min. `column_list` auf `einwaende_gesamt, einwaende_behandelt`
umbenennen. Gleichzeitig analytics.html-Template-Bug (H-16) mitfixen.

### LB-10: ROI-Berechnung im User-Dashboard bucht auf Fantasie-Branche (NEU)

**Evidence:** `routes/dashboard.py:367-368`:
```python
branche  = 'Sonstiges'
avg_deal = DEAL_VALUES.get(branche, 4000)
```
`branche` ist **hart-codiert auf 'Sonstiges'** — die Zeile sieht aus als
sollte sie aus `org` oder `user` gelesen werden, tut es aber nicht. Der
DEAL_VALUES-Dict (Z.362-366) mit 9 Branchen (SaaS 5000 EUR, Consulting 8000
EUR, Immobilien 10000 EUR, etc.) **ist Dead-Code**. Jeder User sieht
avg_deal=4000, geschätzter_mehrwert = behandelt * 0.10 * 4000, roi_faktor
aus dem Nichts.

**Folge:** Das Dashboard zeigt jedem SaaS-User (avg_deal sollte 5000 EUR
sein) und jedem Immobilien-User (10000 EUR) denselben ROI aus einer
zufälligen 4000-EUR-Annahme. Marketing-kritisch: "NERVE hat dir diese
Woche 3.2 Deals gebracht" ist gelogene Fantasie-Zahl die wir dem User
anzeigen.

**Severity-Grund LB statt H:** Das ist die Metrik mit der wir gegenüber
Early-Access-Kunden **Wert beweisen**. Eine falsche ROI-Zahl = broken USP.
Wenn ein Early-Access-Kunde erkennt dass die Zahl konstant ist egal was er
eingibt → Vertrauensverlust.

**Fix-Aufwand:** 1-2h. Entweder `user.org.branche` lesen (falls Feld
existiert — prüfen) oder ROI-Block deaktivieren bis Branchen-Mapping
gebaut ist. **Empfehlung:** ROI-Card auf Dashboard verstecken bis
Phase-B-Profil-Redesign Branchen-Feld kanonisiert.

---

## 🟠 HIGH-Severity

### H-16: Analytics-Seite zeigt immer 0 Einwände (Ghost-Reader im Template)

**Evidence:**
- `routes/dashboard.py:694-710` `/analytics` Route liefert `sessions=rows`
  (raw `ConversationLog`-Rows) an Template.
- `templates/analytics.html:24-25`:
  ```jinja
  <td>{{ s.einwaende_total or 0 }}</td>
  <td>{{ s.einwaende_ok or 0 }}</td>
  ```
- Felder existieren nicht am Model → Jinja gibt `None` → `or 0` → jede
  Zeile zeigt "0 Einwände / 0 Erfolg".

**Weniger crashy als LB-9** (Jinja wirft bei missing attribute Undefined,
`or 0` fängt das), aber **silent data loss**: jede Analytics-Seite jedes
Users lügt. Gesprächs-Erfolgs-History ist nicht einsehbar.

**Fix-Aufwand:** 1 min. Template auf `einwaende_gesamt`, `einwaende_behandelt`.

### H-17: KPI-Dashboard nutzt falsche Feedback-Tabelle

**Evidence:** `admin_views.py:120-123` (`KpiDashboardView`):
```python
'feedback_new':      db.query(func.count(Feedback.id)).filter(
                         Feedback.status == 'new').scalar() or 0,
'feedback_planning': db.query(func.count(Feedback.id)).filter(
                         Feedback.status == 'in_planning').scalar() or 0,
```
Läuft auf Model `Feedback` (Z.405-416 in models.py) — das ist die
Admin-Beta-Feedback-Tabelle mit Status-Workflow. MASTER-AUDIT LB-Kontext
+ Welle-2-Audit zeigen: `/api/feedback` (User-Feedback-Button) schreibt in
**`FeedbackEvent`** (Z.197-204) — NICHT in `Feedback`. Zwei parallele
Tabellen, ein Service.

**Folge:** KPI-Dashboard zeigt nur Admin-Feedback-Items (manuelle Einträge)
als "new/in_planning" an, nie User-Feedback-Events. Wenn kein
Admin-Beta-Feedback erstellt wurde → KPI-Widget zeigt immer 0/0.

**Fix-Aufwand:** 1-2h. Entscheidung über die 2 Tabellen (siehe MASTER-AUDIT
MEDIUM: "Feedback vs. FeedbackEvent"). Entweder mergen oder explizit
dokumentieren welche Tabelle wofür zählt.

### H-18: Weekly-Summary-Claude-Call ohne Cost-Tracking (Dashboard)

**Evidence:** `routes/dashboard.py:299-353` `_generate_weekly_summary()`:
- Instanziert eigenen `anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)` —
  NICHT den globalen `claude_service.claude_client`.
- Ruft `claude-haiku-4-5-20251001`, `max_tokens=200`.
- **Kein `log_api_cost`-Hook.**
- Ruft bei jedem Dashboard-Reload auf (Cache-File ja — aber Cache-Read
  silent-fails in `try/except pass`, d.h. bei IO-Error Re-Call).

**Folge:** Zu den in MASTER-AUDIT H-12 gefundenen 2 inline-Claude-Routes
(`/api/frage`, `/api/ewb_trigger`) kommt diese dritte dazu. Alle drei sind
unsichtbar im Founder-Cost-Dashboard.

**Fix-Aufwand:** 30 min. Cost-Hook hinzufügen. Gleichzeitig Cache-Fail-Log
ergänzen (silent `except Exception: pass` in Z.296, 351).

### H-19: ROI-Calculation silent falsch bei leerem Org-Plan

**Evidence:** `routes/dashboard.py:376`:
```python
plan_kosten    = int(getattr(org, 'plan_preis', None) or 49)
```
Fallback ist `49` (Starter-Preis — stimmt zufällig mit config.py PLANS
überein). Aber MASTER-AUDIT MEDIUM bestätigt: **alle PLANS in config.py
haben `max_users:1, minuten_limit:1000, training_voice_limit:50`** —
Starter/Pro/Business gleich konfiguriert. Gleichzeitig `Organisation.plan`
Spalte vs. `config.py` Plan-Keys haben Drift.

**Folge:** ROI-Faktor (`geschaetzter_mehrwert / plan_kosten`) rechnet
unabhängig vom echten Plan immer gegen `49 EUR`. Business-User (sollte
höherer Preis sein wenn PLANS fixed werden) bekommt scheinbar 20x ROI, in
Wahrheit falsche Darstellung.

**Fix-Aufwand:** zusammen mit LB-10 lösen.

---

## 🟡 MEDIUM-Severity

### M-1: `_parse_log_meta` liest Legacy-Logfiles in dashboard.py:69-113

Parst `nerve_log_U{uid}_*.txt` mit Regex + Inhalts-Grep. Relikt aus
Pre-DB-Zeit. DB-Path ist `get_recent_calls_db` (Z.132-152). **Beide werden
an Template übergeben** (Z.583-584). Template muss doppelten Datensatz
handhaben. Alte File-Based-Kette ist nicht entfernt. Kandidat für Pruning
(MASTER-AUDIT Muster 1).

### M-2: `get_recent_logs` iteriert Filesystem bei JEDEM Dashboard-Load

`os.listdir(LOG_DIR)` + pro File `open().read()` + Regex-Grep. Bei 1000
Call-Logs wird jedes Dashboard-Rendering I/O-heavy. Cache fehlt.

### M-3: Streak-Update mutiert User bei jedem Dashboard-Open

`dashboard.py:434-447` — Streak-Logik läuft in GET `/dashboard` als
Side-Effect. Race-Condition-Risiko wenn User auf zwei Geräten gleichzeitig
Dashboard öffnet. Kein Lock.

### M-4: Analytics-Route hat keine Mode-Validation für 'cold_call' vs. legacy

`dashboard.py:702` lässt nur 3 Modi durch. Aber legacy-Sessions (pre
Phase 04.8) haben evtl. NULL `session_mode`. Filter trifft nicht → Liste
zeigt leeren State ohne Hinweis.

### M-5: Session-Detail erlaubt keinen Admin-Zugriff auf fremde Sessions

`dashboard.py:722-725`: `.filter(CL.user_id == g.user.id)` → 404 wenn
fremde Session. Support-Fall: Kunde meldet Bug, Admin will Transkript
sehen — geht nicht über normale Route. Kein Admin-Override. Support-Team
muss Flask-Admin nutzen (siehe LB-9 — das ist auch kaputt).

### M-6: `compute_org_profitability` leidet unter LB-5 (kein eigener Bug)

`admin_dashboard.py:541-557` filtert `ApiCostLog.org_id == org_id`. Da
LB-5 alle org_id=NULL schreibt, gibt Filter immer 0 zurück → margin_pct
immer 100% → alle Orgs als 'healthy' klassifiziert (classify_margin > 70).
**Entsteht visuelle Lüge**: "alle unsere Kunden sind profitabel" obwohl
wir gar nicht wissen ob sie es sind.

### M-7: `kunden_drilldown` ist einzige Stelle die ApiCostLog.user_id filtert

`admin_dashboard.py:608-612` — hier hängt Billing an user_id. Kombiniert
mit LB-4 (Cost-Tracker schreibt stale user_id bei Concurrency) bedeutet:
Das Drilldown zeigt potentiell falsche Cost-Attribution zu falschen
Usern. Der Drilldown ist technisch korrekt geschrieben, aber Input-Daten
sind schmutzig.

---

## 🟢 LOW / Kosmetik

- **Dashboard `DEAL_VALUES`-Dict Z.362-366** wird nur via hart-kodiertem
  `'Sonstiges'`-Key gelesen — die 8 anderen Branchen-Werte sind Dead Data
  (siehe LB-10).
- **Quote-of-Day** hash-basiert, kein Test — wenn md5 umgestellt wird
  ändert sich alle User sehen andere Quote. Irrelevant.
- **`_check_achievements`** mischt `.einwaende_behandelt` (korrekt,
  Z.177) mit **im Template: s.einwaende_ok** — siehe H-16.
- **CSV-BOM** in `admin_dashboard._csv_response` korrekt (Z.722) — gut
  für Excel. Low-praise.
- **`admin_dashboard.api_rate_new_price` FX-Fallback 0.92** (Z.432) —
  MASTER-AUDIT MEDIUM: "FX-Fallback hardcoded + stale (EZB aktuell ~0.89)".

---

## 🔐 AUTH-GATE-CHECK (Privilege-Escalation-Pfade)

**Verifiziert sauber:**

| Route-Block | Gate | Befund |
|---|---|---|
| `routes/admin_dashboard.py` (22 Endpoints) | Jeder mit `@login_required` + `@superadmin_required` | ✅ Konsistent |
| `routes/admin_views.py` Flask-Admin-ModelViews | `SecureModelView.is_accessible` → `_is_superadmin()` | ✅ |
| `routes/admin_views.py` Custom-Views (KPI, Planning, CRM) | Eigene `is_accessible` → `_is_superadmin()` | ✅ |
| `register_admin_screenshot_route` im Admin-Views | `@superadmin_required` | ✅ |
| Flask-Admin `/admin` Index | `app.py:1734` `SecureIndexView.is_accessible` → `is_superadmin` | ✅ |
| `routes/dashboard.py` | Alle Routes `@login_required`, keine Admin-Pfade | ✅ |

**Keine Privilege-Escalation-Pfade gefunden.** Nicht-Superadmin-User kann
weder `/admin/dashboard/*` (aborted 403 via Decorator) noch `/admin/*`
Flask-Admin (Index redirect + 403) erreichen. CrmView + PlanningListView +
KpiDashboardView haben alle eigene `is_accessible` → `_is_superadmin()`.

**Keine Role-String-Escalation** (kein `rolle == 'admin'`-Bypass irgendwo
zu Superadmin — `is_superadmin` ist eigenes Boolean, Z.62 models.py,
ENV-Seed nur bei `SUPERADMIN_EMAIL`-Match in auth.py:102-104).

**Potentielle Schwachstelle:** `_is_superadmin()` liest `g.user` — gesetzt
nur in `login_required`-Decorator. Flask-Admin `is_accessible` wird
allerdings AUCH ohne `login_required` aufgerufen (Flask-Admin ist außer-Flask).
`g.user` ist dann `None` → `getattr(g, 'user', None)` → False → access denied.
**Verifiziert safe** via `getattr`-Pattern.

---

## 🎯 PreCall-Briefing-Konsumenten-Suche (Hypothese 7)

**Grep `precall_briefing` in `routes/` + `services/claude_service.py`:**

Reader im Live-Pfad:
1. `routes/app_routes.py:266-281, 454` — liest aus request / fallback
   `ls.state['precall_briefing']`, schreibt in `ConversationLog.precall_briefing`
   (DB-Column) bei Session-Ende. **Nur Write-Path.**
2. `services/claude_service.py:387` — liest `ls.state.get('precall_briefing')`
   in `_build_system_prompt` (Z.265-401). **Dieser Builder ist DEAD
   seit Phase 08** (MASTER-AUDIT H-4). Damit ist der einzige Live-LLM-Reader
   Zombie-Code.

**Kein Reader in:**
- `routes/dashboard.py` — 0 Treffer
- `routes/admin_dashboard.py` — 0 Treffer
- `routes/admin_views.py` — 0 Treffer
- EWB-Pipeline (`build_profile_context`) — bestätigt MASTER-AUDIT H-2
- QA-Pipeline — bestätigt

**Bestätigt endgültig MASTER-AUDIT H-2:** PreCall-Briefing-Feature ist
Feature-Fake. Sonnet-PostCall-Analyse könnte theoretisch via
`ConversationLog.precall_briefing`-DB-Column lesen — tut aber nicht (zu
verifizieren in coaching_service.py, aber Welle-2 hat das als "dead data
path" bestätigt).

**Neuer Befund:** Dashboard.py `session_detail` (Z.713-932) rendert
session_detail.html — **kein Template-Context-Key `precall_briefing`**
(Z.909-930). Also auch kein UI-Reader im Detail-View. Die einzige UI die
precall_briefing je zeigt ist (laut Grep) `pip-launcher.js` Frontend.

---

## 🕳️ Silent-Failure-Patterns

Gefunden in den 3 Routes:

| Stelle | Muster |
|---|---|
| `dashboard.py:296` | `try/except: pass` um Cache-Read (weekly_summary) |
| `dashboard.py:351` | `try/except: pass` um Cache-Write |
| `dashboard.py:354` | `try/except: return None` um gesamten Claude-Call |
| `dashboard.py:557` | `try/except: pass` um training_recommendation JSON |
| `dashboard.py:568` | `print(f"[Coach] Dashboard data error: {_ce}")` — nur Stdout, kein Log-Channel |
| `dashboard.py:905-906` | `try/except: _pp_raw = []` für painpoints_details |
| `admin_dashboard.py:431-432` | FX-Fallback 0.92 bei Exception |
| `admin_views.py:214-215` | `jsonify({'ok': False, 'error': str(e)})` — **leakt Exception-Message** an Client wie LB-7/H-15 |

**Neuer HIGH-Kandidat (H-20):** `admin_views.py:214` `except Exception as e:
return jsonify({'error': str(e)})` in `CrmView.save_note` — gleicher
Fehler wie H-15 aus MASTER-AUDIT, aber Admin-only (weniger exploitabel
da bereits privilegierter User).

---

## 🗑️ TODO/FIXME/unused imports

- `dashboard.py:8` `from routes.auth import login_required` — korrekt (login_required sitzt in auth.py, NICHT auth_decorators.py — STRUCTURE.md Z.35-Doku-Lüge aus MASTER-AUDIT damit nochmal verifiziert).
- `dashboard.py:426-430` Wizard-Redirect auskommentiert mit Kommentar
  "wird in einer späteren Phase neu gebaut" — **TODO offiziell
  dokumentiert aber nirgends tracked**.
- `admin_dashboard.py:848` D-07 DATEV-Export ist explizit STUB: `"NICHT
  DATEV-format-konform. Volle Implementierung wartet auf count.tax"` — OK,
  ehrlich dokumentiert.
- Keine verwaisten Imports gefunden (alle `from x import y` werden im
  File benutzt).

---

## 📊 CrmView / PlanningListView / KpiDashboardView — echt oder Stub?

| View | Status | Befund |
|---|---|---|
| **CrmView** (admin_views.py:161-218) | 🟢 **Echt, funktional** | Ruft `get_all_user_crm_data` + `get_followup_hints` aus customer_success_service. Service hat echte SQL-Aggregationen (bestätigt Welle 2). POST `/note` speichert CrmNote in DB. |
| **PlanningListView** (admin_views.py:132-156) | 🟢 **Echt, funktional** | Liest `PlanningFeedbackLink`-Rows, erlaubt Status-Toggle (backlog/active/done). Arbeitet mit FeedbackAdmin-Action `mark_in_planning`. Zusammenhängend. |
| **KpiDashboardView** (admin_views.py:102-129) | 🟡 **Echt aber Feedback-Zählung falsch** | Siehe H-17. Rest (users_total, orgs_total, sessions_week, audit_week) ist korrekt gezählt. |
| **admin_dashboard.index + api_overview + 12m-Chart** (admin_dashboard.py:61-180) | 🟢 **Echt, funktional** | Aggregiert echte DB-Daten, 12-Monats-Serie rückwärts. KEINE Mocks. Kaputt nur durch LB-5. |
| **admin_dashboard Performance-Charts (30-Tage-Serie, margin_12m)** | 🟢 **Live aus DB** | `daily_30` (Z.336-345) iteriert täglich über ApiCostLog. `margin_12m` (Z.124-158) über RevenueLog+ApiCostLog+FixedCost. Keine Mocks, keine hardcoded Arrays. |

**Keine Mock-Dashboards.** Alles ist SQL-backed. Die Datenqualität dahinter
ist das Problem (LB-4, LB-5, H-9).

---

## 🔀 Call-Graph / Daten-Flow

```
User-Dashboard (dashboard.py):
  /dashboard (index)
    → UserModel (streak update, side-effect write!)
    → ConversationLog (30d window + 7d/14d Trend)
    → _check_achievements (Achievements aus logs.einwaende_behandelt)
    → _get_level (User.total_points lookup)
    → _generate_weekly_summary (CLAUDE CALL, no cost-tracking — H-18)
    → _generate_improvement_tip (rein aus logs + user)
    → Profile.filter_by(org_id=g.org.id).first()
    → get_recent_logs (FILESYSTEM — M-2)
    → get_recent_calls_db (DB)
    → _calculate_roi (LB-10 — hardcoded branche)
    → coaching_service.get_active_cards/weekly_report/longterm_data

  /session/<sid>
    → ConversationLog.filter(user_id=g.user.id) — M-5 keine Admin-Override
    → ObjectionEvent
    → PersonalityType (Training)
    → _calc_call_score (aus app_routes)
    → _derive_practice_recommendations (aus app_routes)
    → _dedupe_painpoints (SequenceMatcher > 0.60)

  /analytics
    → ConversationLog raw rows → template (H-16 Ghost-Reader)

  /api/nudge, /api/nudge/dismiss, /api/notifications
    → UserModel + ConversationLog, simple Logik

  /api/analytics
    → ConversationLog aggregation, JSON response

Founder-Dashboard (admin_dashboard.py):
  /admin/dashboard/ (index) → render_template + active_tab
  /api/overview → MRR + Revenue + ApiCosts + FixedCosts + Active-Users + 12m
  /einnahmen → RevenueLog (by tax_treatment, plan_key, country, paginated txs)
  /ausgaben → ApiCostLog (by provider), FixedCost, ApiRate, 30d-Serie
  /api_rates/*/mark_checked, /new_price → ApiRate admin
  /fixed_costs (POST + PATCH) → FixedCost CRUD
  /kunden → alle active Orgs (AFFECTED by LB-5)
  /kunden/<org_id>/users → User-Drilldown (AFFECTED by LB-4)
  /eur → eur_calculator.compute_eur
  /export/{eur.html,eur.pdf,einnahmen.csv,ausgaben.csv,ustva.csv,datev_stub.csv}

Flask-Admin (admin_views.py via app.py:1756-1764):
  /admin/ (SecureIndexView)
  /admin/user/ (UserAdmin)
  /admin/organisation/ (OrgAdmin)
  /admin/feedback/ (FeedbackAdmin, mit Action mark_in_planning)
  /admin/auditlog/ (AuditLogAdmin, read-only)
  /admin/convlog/ (ConvLogAdmin — BROKEN via LB-9)
  /admin/kpi/ (KpiDashboardView — H-17)
  /admin/planning/ (PlanningListView)
  /admin/crm_view/ (CrmView)
  /admin/feedback/screenshot/<rel> (register_admin_screenshot_route)
```

---

## 🔢 PRIORISIERTER FIX-PLAN (für Welle 3 Rollup)

### In Stabilisierungs-Phase Block 1 (vor EA):
1. **LB-9 Ghost-Columns fixen** — 1 min.
2. **H-16 analytics.html Template** — 1 min (gleicher Fix).
3. **LB-10 ROI-Branche** — 1-2h ODER ROI-Card verstecken (10 min).
4. **H-18 Cost-Hook für Weekly-Summary** — 30 min.

### In Stabilisierungs-Phase Block 2:
5. **H-17 KPI-Dashboard Feedback-Tabelle-Entscheidung** — zusammen mit
   MASTER-AUDIT MEDIUM "Feedback vs. FeedbackEvent".
6. **M-6 gelöst durch LB-5-Fix** (keine zusätzliche Arbeit).

### In Härtungs-Phase:
7. **M-5 Admin-Session-Detail-Override** — 1h (separater `/admin/session/<id>`-Pfad mit Audit-Event).
8. **M-1/M-2 Log-Filesystem-Pfad pruning** — 1h. DB-Path ist Authority.
9. **M-3 Streak-Write-Race** — 30 min (SELECT FOR UPDATE oder UPSERT).
10. **H-19 plan_preis-Drift zusammen mit PLANS-config-Fix** (MASTER-AUDIT MEDIUM).

---

## 🧾 Neue Doku-Lügen

Keine neue Doku-Lüge in ARCHITECTURE/STRUCTURE entdeckt die Dashboards
betrifft. Aber:

- **`einwaende_total`/`einwaende_ok`-Naming** taucht in 4 Phase-Plans auf
  (04.7-02/05/06-PLAN, 04.11-04-PLAN, 04.14-01-PLAN) und wurde als
  "nur Template-Variable" gemeint, aber in admin_views.py als DB-Column
  falsch verstanden. **Nudelcode-Muster 4 (Hardcoded Placeholder):** Phase-Plan
  schreibt Template-Code, jemand kopiert ins Admin-Model ohne Column-Check.

---

## 📌 Message an MASTER-AUDIT-Rollup

**Neue Launch-Blocker zum Aufnehmen:**
- LB-9 (Flask-Admin ConvLog-View crasht)
- LB-10 (Dashboard-ROI lügt über Branche)

**Neue HIGH-Severity:**
- H-16 (analytics.html Ghost-Reader)
- H-17 (KPI-Dashboard Feedback-Tabelle falsch)
- H-18 (Weekly-Summary Claude ohne Cost-Hook)
- H-19 (plan_preis-Drift)
- H-20 (Admin-CrmView jsonify Exception-Leak)

**Bestätigung vorhandener Befunde:**
- LB-5 trifft admin_dashboard.py:548-550 exakt wie vermutet. Route ist
  Opfer, Writer-Fix in deepgram_service.py:351 löst es vollständig.
- H-2 PreCall-Briefing: kein neuer Reader in den 3 Routes gefunden.
  Feature-Fake-Diagnose bleibt.
- STRUCTURE.md Z.35 "login_required in auth_decorators.py" falsch —
  dashboard.py importiert korrekt `from routes.auth import login_required`.

**Keine Privilege-Escalation.** Auth-Gating in allen 3 Routes konsistent
sauber (Superadmin-Pfade + login-Pfade klar getrennt). Das ist die gute
Nachricht.

---

*Audit abgeschlossen: 2026-04-24, ~18 min. Weiter für Welle 3: routes/profiles.py,
routes/training.py, routes/payments.py, routes/oauth.py.*
