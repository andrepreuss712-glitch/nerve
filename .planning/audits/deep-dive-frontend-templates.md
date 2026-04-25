---
audit: deep-dive-frontend-templates
phase: Welle 4 (Frontend + Templates)
erstellt: 2026-04-24
autor: Claudian (Obsidian-Vault)
scope:
  - static/profile_editor.js (460 Z.)
  - static/audio-processor.js (27 Z.)
  - static/feedback.js (47 Z.)
  - static/admin_dashboard.js (69 Z.)
  - 27 HTML-Templates (templates/*.html + templates/admin/*.html)
  - Jinja-Variablen vs. Route-Kontext
  - Include-/Extends-Graph
  - Orphan-Templates
basiert_auf:
  - .planning/audits/MASTER-AUDIT.md (Stand 2026-04-24 15:40)
  - Salesnerve-Repo Stand 2026-04-24
excluded:
  - static/app.js (2125 Z.) — nur Punkt-Stichproben
  - static/pip-launcher.js (2315 Z.) — nur Punkt-Stichproben
  - static/vendor/ (Third-Party-Libs)
---

# Deep-Dive: Frontend-Rest + Templates

## TL;DR

**7 Findings gesamt** (0 LAUNCH-BLOCKER, 3 HIGH, 3 MEDIUM, 1 LOW).

Die vier kleinen JS-Dateien sind **weitgehend sauber**. Haupt-Problem in profile_editor.js ist bereits als MEDIUM in MASTER-AUDIT erfasst (TABU-Duplikat Z.131).

Bei den 27 Templates die größten Befunde:
- **2 Orphan-Templates** (rendered nirgends): `login.html`, `admin/feedback_notification.html`
- **Admin-Gating via Session-Role** ist konsistent umgesetzt — **kein Admin-Feld-Leak** in User-Templates gefunden
- **Keine kritischen Jinja-Variables ohne Route-Kontext** (Silent-Blank-Renders) bei den GET-Rendering-Routes
- **`| safe` wird 13x benutzt** — alle Aufrufe sind über `| tojson` oder pre-sanitized (markdown-Filter) geleitet, keine rohen User-HTML-Injects

---

## Template-Inventar (27 Dateien, gruppiert)

### Standalone-Pages (kein base.html-Extend)

| Template | Route | Zweck | Status |
|---|---|---|---|
| `app.html` (86 KB) | `GET /app` via `app_routes.py:124` | Live-Assistent-UI (Cold/Meeting), Skripte, EWB, PiP-Launcher | ✅ Aktiv, Main-Frontend |
| `landing.html` (52 KB) | `GET /` via `dashboard.py:407/413` | Marketing-Landing + Login-Modal + Waitlist | ✅ Aktiv |
| `register.html` | `auth.py:245/248/251/263` | Einladungs-Registrierung per Token | ✅ Aktiv (nur invited-flow) |
| `onboarding.html` (29 KB) | `onboarding.py:162` | 1st-Run-Wizard nach Registration | ✅ Aktiv |
| `login.html` | **KEINE** (auth.py:77 redirectet zu `/?modal=login`) | Legacy Stand-Alone-Login | 🟠 **ORPHAN** (siehe F-4) |

### base.html-Extender (User-Pages)

| Template | Route | Zweck | Kontext-Vars |
|---|---|---|---|
| `base.html` (44 KB) | — | Global Layout (Header + Sidebar + Footer + Feedback-Modal) | g.user, g.org, session, url_for, get_flashed_messages |
| `dashboard.html` (45 KB) | `dashboard.py:573` | User-Dashboard (Stats, Coach, Streak) | stats, activity_map, achievements, level_info, improvement_tip, weekly_summary, qotd, streak, recent_logs, recent_calls, active_profile, profiles, welcome_trial, usage, roi, learning_cards, weekly_report, longterm_data_json |
| `analytics.html` | `dashboard.py:706` | Analytics-Seite | (separat, wenig Complexity) |
| `session_detail.html` (33 KB) | `dashboard.py:909` | Session-Nachbesprechung (Score, Wendepunkte, Coach-Tipps) | conv, events, pt, trend_avg, chart_data_json, schwierigkeit_label, recommendations, score_total, kb_end_effective, painpoints, scoring_kategorien, scoring_wendepunkte_detail, scoring_verbesserungen, kunden_name, kunden_alter, kunden_display_name, kunden_display_icon, schwierigkeit_raw |
| `profiles_list.html` (20 KB) | `profiles.py:48` | Profil-Liste + Delete-Actions | profiles, active_id |
| `profile_editor.html` (83 KB) | `profiles.py:81, 182` | Profil-Formular (4 Sektionen + FAQs + Tabu-UI) | profile, daten |
| `profile_wizard.html` | `profiles.py:88` | Schnellprofil-Wizard | (kein Backend-Kontext) |
| `training.html` (107 KB) | `training.py:57` | Training-Personas + Start-UI | training_languages, PLAN_TYP, preferred_language, … |
| `settings.html` (34 KB) | `settings.py:40, 223` | Settings + Billing + Integrations | usage, active_tab |
| `help.html` (12 KB) | `settings.py:211` | Hilfe-Seite | (statisch, kein Kontext) |
| `team.html` | `organisations.py:31` | Team-Mgmt | users, invitations |
| `logs_page.html` | `logs_routes.py:30` | Log-Downloads | logs |
| `changelog.html` | `changelog.py:22` | Public Changelog | entries |
| `impressum.html` / `agb.html` / `datenschutz.html` | `legal.py:7/11/15` | Legal | — |
| `waitlist_admin.html` | `waitlist.py:151` (owner-only) | Admin-Waitlist | entries, stats |
| `coach_dashboard.html` | `coach.py:53` | Coach-Übersicht | firmen |
| `coach_firma.html` (12 KB) | `coach.py:78` | Coach-Firma-Detail | — |
| `coach_methodik.html` | `coach.py:277` | Coach-Methodik | profiles, orgs |

### Admin-Subfolder (templates/admin/*)

| Template | Route | Zweck |
|---|---|---|
| `admin/dashboard.html` | `admin_dashboard.py:70` | Founder-Cost-Dashboard (Tabs) |
| `admin/_tab_uebersicht.html` | include | Übersichts-Tab |
| `admin/_tab_einnahmen.html` | include | Einnahmen-Tab |
| `admin/_tab_ausgaben.html` | include | Ausgaben-Tab |
| `admin/_tab_kunden.html` | include | Kunden-Tab |
| `admin/_tab_eur.html` | include | EÜR-Tab |
| `admin/_tab_export.html` | include | Export-Tab |
| `admin/eur_pdf.html` | `admin_dashboard.py:678, 702` | EÜR-PDF-Render |
| `admin/ewb_quality.html` | `admin_ewb.py:112` | EWB-Quality-Dashboard |
| `admin/ewb_rating_template.html` | `admin_ewb.py:167` | EWB-Rating-Tool |
| `admin/kpi_dashboard.html` | `admin_views.py:127` (Flask-Admin) | KPI-Dashboard |
| `admin/crm_overview.html` | `admin_views.py:184` | CRM-Übersicht |
| `admin/planning_list.html` | `admin_views.py:154` | Planning-List |
| `admin/feedback_notification.html` | **KEINE** | **🟠 ORPHAN** (siehe F-5) |

### Partials/Includes

| Template | Use-Site | Zweck |
|---|---|---|
| `_beispiel_profil_modal.html` | included in `profile_editor.html:755` | Fiktives Beispiel-Profil-Modal (Phase 08 D-19) |
| `_tooltip.html` | ? | Tooltip-Partial (nicht verifizert — kein Include-Hit) |

**Total: 27 Templates.** 2 Orphans identifiziert.

---

## JS-Findings

### profile_editor.js (460 Z.)

**Zweck:** Phase-08.5-Erweiterung für FAQ-CRUD (sec-faqs) + Tabu-Begriffe-2-Spalten-UI (sec-tabu). Wird nach dem Inline-Script in `profile_editor.html` geladen und hakt sich in `window.buildAndSubmit` ein.

#### 1. Schema-Validation client-seitig — sehr dünn

- profile_editor.html:1147 — einziger Pflichtfeld-Check: `if(!name) alert('Profilname ist Pflichtfeld.')`
- Gesamt nur **9 HTML5-validation-Attribute** (required/maxlength/pattern/min/max) im 83-KB-Template
- profile_editor.js validiert nur Tabu-Rows (nicht-leer-Paar) + FAQ-Rows (Frage+Antwort).
- **Kein JSON-Schema-Check, keine Trim-Limit-Validation, kein Typ-Check auf numerische Trigger-Felder (tr_verlust, tr_familie…).**
- Server-seitig existiert laut MASTER-AUDIT **auch keine** strenge Schema-Validation → der MEDIUM-Fund **"Profile-JSON kein Schema-Validator"** beschreibt die End-to-End-Lücke: **weder Client noch Server prüfen**. User kann invalides Profil speichern, das erst Wochen später im Prompt-Matcher silent failt (siehe MEDIUM im MASTER-AUDIT: "Regex-Patterns können malformed sein, Matcher failt silent").

**Severity: MEDIUM** (F-1) — **verstärkt** den bestehenden MASTER-AUDIT-MEDIUM.

#### 2. Schema-Mismatch-Frage — Top-Level `produkt` vs. `basis.produktbeschreibung`

MASTER-AUDIT H-13 meldet dass `routes/app_routes.py` (`/api/frage`, `/api/ewb_trigger`) `pdata.get("produkt")` als Top-Level-Key liest. Gegen-Check im Client:

- **profile_editor.js selbst referenziert kein Schema-Feld direkt** (außer `basis.tabu_begriffe` in Z.401 für LoadTabu).
- **profile_editor.html:1169** schreibt das Produkt korrekt als `basis.produktbeschreibung` (Phase-08-Schema).
- profile_editor.html:1379 hat einen **Legacy-Fallback** für Alt-Profile: `setVal('vi_produkt',[DATEN.beschreibung||'',DATEN.produkt||''].filter(Boolean).join('\n'));` — **beim Laden** toleriert er noch das alte Top-Level-Schema. Das ist korrekt für Migration.

**Ergebnis Client:** Korrektes Schema. **Der Schema-Drift sitzt allein server-seitig in 2 Routes.** H-13 bleibt unverändert valid, Client-Code ist nicht der Täter.

#### 3. TABU_DEFAULT_PAIRS-Duplikat (MASTER-AUDIT MEDIUM)

Z.132-146 spiegelt `services/profile_migration.TABU_DEFAULT_PAIRS` manuell. Verifiziert: **Reihenfolge + Content identisch** (13 Paare, gleiche Umlaute).

Bekannter MEDIUM-Fund — keine neue Severity. Fix-Pfad: JSON-Endpoint `/profiles/api/profile/tabu_defaults` als Single-Source-of-Truth, Client fetcht beim Init.

#### 4. Konsumierte Backend-Routes (alle verifiziert)

| JS-Call (Zeile) | Method | Route | In routes/profiles.py |
|---|---|---|---|
| 49 | GET | `/profiles/api/profile/<pid>/faqs` | ✅ Z.418 |
| 89 | PUT | `/profiles/api/profile/faqs/<id>` | ✅ Z.475 |
| 98 | POST | `/profiles/api/profile/<pid>/faqs` | ✅ Z.443 |
| 117 | DELETE | `/profiles/api/profile/faqs/<id>` | ✅ Z.511 |
| 377 | POST | `/profiles/api/profile/<pid>/tabu` | ✅ Z.530 |

**Alle Calls matchen Routes.** Keine toten Calls.

#### 5. Kein TODO/FIXME/HACK-Marker

Grep auf alle 4 kleinen JS-Files: 0 Dead-Code-Marker.

### audio-processor.js (27 Z.)

**Zweck:** AudioWorklet-Processor, Float32 → Int16 PCM, 100ms-Chunks (1600 samples @ 16kHz). Keine Routes, keine Findings.

### feedback.js (47 Z.)

**Zweck:** Feedback-Modal-Logik im base.html (Feedback-Button unten rechts).

**Backend-Route:** POST `/api/feedback` (Z.11) — existiert in `routes/feedback.py` (67 Z., laut MASTER-AUDIT Welle 3 noch offen). Wird laut MASTER-AUDIT-H-M-Fund "Feedback vs. FeedbackEvent" in `FeedbackEvent` geschrieben (nicht in `Feedback`).

**Sauberkeit:** Clean. Error-Handling vorhanden (alert + toast). Credentials same-origin. Kein XSS-Risiko (textContent statt innerHTML beim Toast).

### admin_dashboard.js (69 Z.)

**Zweck:** Tab-Switcher + 2 Chart.js-Renderer für Founder-Cost-Dashboard (Phase 04.7.2).

**Backend-Route:** GET `/admin/dashboard/api/overview?period=X` (Z.29) — existiert in `routes/admin_dashboard.py:79`. ✅

**Dependency:** `window.Chart` (chart.umd.min.js). Graceful return falls nicht geladen.

**Keine Findings.**

---

## Template-Findings

### F-4: `login.html` ist Orphan-Template

**Evidence:**
- `routes/auth.py:67-77`: `/login`-Route redirectet zu `/?modal=login` — **rendert niemals `login.html`.**
- Grep `render_template.*login\.html` über gesamten Python-Code: **0 Treffer.**
- Template enthält legacy orange `#E8B040` (pre-Phase-04.3-Design) + deploy-test-comment v7.

**Folge:**
- 45 Zeilen Template-Müll.
- Bei zukünftigem Login-Redesign könnte Entwickler irrtümlich dieses Template updaten ohne dass es je sichtbar wird → **Nudelcode-Risiko** (Phase-04.3-VERIFICATION.md Z.113 hat das Template noch als "legacy" markiert — aber keiner hat es dann gelöscht).

**Severity: LOW** (F-4) — Aufräum-Aufgabe.

**Fix:** Datei löschen.

### F-5: `admin/feedback_notification.html` ist Orphan-Template

**Evidence:**
- Grep `feedback_notification` über gesamten Python-Code: **0 render-Treffer, 0 Include-Treffer.**
- Template-Inhalt: 1 Zeile `<div class="alert alert-warning">{{ stats.feedback_new }} neue Feedback-Tickets warten.</div>`

**Folge:**
- Partial der nirgends included/rendered wird.
- Entweder Relikt aus Phase-Refactor (Admin-Bell-Notification die nie live geschaltet wurde) oder vorgesehen für Phase die nie kam.

**Severity: LOW** (F-5) — Aufräum-Aufgabe.

**Fix:** Datei löschen oder als tatsächlichen Include in `admin/dashboard.html` verdrahten — Entscheidung André.

### F-6: `_tooltip.html` — Include-Status unklar

**Evidence:**
- Datei existiert (976 B).
- Grep `include.*_tooltip` findet **nichts** im Template-Code.

**Folge:** Vermutlich weiteres Orphan-Partial, muss in Welle 5 gegen JS-Referenzen geprüft werden (evtl. per `fetch().then(html)`-Injection genutzt — unwahrscheinlich, da keine JS-Call-Site für `.html`-Partials gefunden).

**Severity: LOW** — Verifizieren, dann löschen.

### F-7: `conv.precall_briefing` wird in session_detail.html gerendert — UI-Zombie

**Evidence:** session_detail.html:267-270:
```jinja
{% if conv.precall_briefing %}
  <div class="n-session-detail-precall-body">{{ conv.precall_briefing | markdown | safe }}</div>
{% endif %}
```

**Backend-Path:** MASTER-AUDIT bestätigt `ConversationLog.precall_briefing` Column wird befüllt (bei Session-Ende), aber **Live-KI konsumiert das Feld nie** (H-2: PreCall Feature-Fake). Post-Call-Anzeige ist also der **einzige wirkliche Konsument** des Feldes — User sieht in der Session-Nachbesprechung sein Briefing, aber die Live-KI hat's nie bekommen.

**Gefahr:** Verstärkt den Eindruck dass PreCall "funktioniert" (User sieht's ja) obwohl es faktisch nie in einen Prompt floss. Dies ist **nicht neu** — H-2 im MASTER-AUDIT fasst das zusammen. **Entscheidung (re-wire oder deprecate) muss auch über die UI-Anzeige fallen:** bei Deprecation muss session_detail.html:267-270 mit entfernt werden, sonst verkauft die Nachbesprechung ein Feature das es nicht gibt.

**Severity: HIGH** (F-7) — **Verstärkt MASTER-AUDIT H-2**, zeigt dass PreCall-Feature-Fake auch in session_detail.html weiterlebt.

**Fix:** Im H-2-Fix entscheiden — wenn "re-wire in EWB", dann Anzeige bleibt; wenn "deprecate", dann Z.267-270 entfernen.

### F-8: app.js liest weiterhin `data.ewb_top2` — Legacy-Reader aktiv

**Evidence:**
- `app_routes.py:145`: `/api/ergebnis`-Response enthält `'ewb_top2': ls.state.get('ewb_top2')` mit `# legacy (may be None post-04.8)`.
- `static/app.js:798-799`:
```js
if(data.ewb_top2 && Array.isArray(data.ewb_top2) && data.ewb_top2.length >= 2){
  renderPipEwbButtons(data.ewb_top2);
}
```
- Ist also **kein toter Response-Zombie** wie man bei "legacy (may be None post-04.8)" annehmen könnte — Frontend **konsumiert aktiv**, und wenn `ls.state` kein `ewb_top2` mehr schreibt (post-04.8), rendert Frontend stattdessen den neuen EWB-Pfad.

**Folge:** Entweder ist der `ewb_top2`-Writer in der Codebase noch aktiv (dann ist der "legacy may be None"-Kommentar eine **Doku-Lüge**), oder der Reader im Frontend ist **dead branch** der niemals triggert. Welle 5 muss klären: gibt es noch einen `ls.state['ewb_top2'] = ...`-Write?

**Severity: HIGH** (F-8) — potentieller doppelter EWB-Render-Pfad oder Dead-Code im Hot-Path.

**Fix:** Writer-Suche nach `ewb_top2`-Assignment. Falls kein Writer → app.js:798-799 + app_routes.py:145 entfernen. Falls Writer existiert → architektonische Klärung (neuer + alter EWB-Pfad parallel?).

### F-9: pip-launcher.js + app.js posten `precall_briefing` an Backend — reines Frontend-Ping-Pong

**Evidence:**
- `static/pip-launcher.js:998`: `precall_briefing: briefingText,` (POST zu `/api/precall/...`)
- `static/pip-launcher.js:1891`: `precall_briefing: state.precallBriefing`
- `static/app.js:649`: POST zu beenden/start mit `precall_briefing: precallBriefingText`
- `static/app.js:1675`: ebenfalls

**Folge kombiniert mit MASTER-AUDIT H-2:** Frontend sammelt PreCall-Briefing, postet es an 3+ Backend-Routes, Backend schreibt es in `ls.state['precall_briefing']`, und **kein Live-LLM-Pfad liest das je wieder**. Der User-Code sieht "Feature live" — gibt Briefing ein → schickt ab → bekommt Confirmation → während im Backend nichts passiert. UI-Feedback-Loop funktioniert, Business-Logic nicht.

**Severity: HIGH** (F-9) — ist die Frontend-Hälfte von MASTER-AUDIT H-2. **Zusammen mit F-7** zeigt das: die Doku-Lüge "PreCall live" ist über **3 Schichten** aufrechterhalten worden: Frontend sendet → Backend speichert → session_detail zeigt an. Nur der mittlere Prompt-Pfad fehlt.

**Fix:** Teil der H-2-Entscheidung.

### Silent-Blank-Render-Kandidaten: KEINE

Alle GET-Routes die base.html-Templates rendern, **liefern ihre Kontext-Variablen korrekt**. Stichproben-Check:

| Template-Variable | Route liefert? |
|---|---|
| `longterm_data_json` | ✅ dashboard.py:593 |
| `chart_data_json` | ✅ dashboard.py:915 |
| `active_profile`, `active_phasen`, `profiles_for_pip`, `active_profile_daten`, `precall_verfuegbar` | ✅ app_routes.py:124-129 |
| `scoring_kategorien`, `kunden_name`, `schwierigkeit_raw` | ✅ dashboard.py:922-929 |
| `conv`, `events`, `pt`, `trend_avg` etc. | ✅ dashboard.py:909-930 |
| `profile`, `daten` | ✅ profiles.py:182 |
| `entries`, `stats` | ✅ waitlist.py:151 |
| `usage`, `active_tab` | ✅ settings.py:40/223 |
| `training_languages`, `PLAN_TYP`, `preferred_language` | ✅ training.py:57 (implizit via kwargs) |
| `log.datum`, `log.profil`, `log.dauer`, `log.segmente`, `log.einwaende`, `log.painpoints`, `log.filename`, `log.uhrzeit` | ✅ logs_routes.py:30 via `_parse_log_meta` |

**Keine Templates mit referenzierten aber nicht-gelieferten Jinja-Variablen gefunden.**

### Security: `| safe` Audit (13 Treffer)

Alle 13 `| safe`-Aufrufe sind **sicher**:

| Datei:Zeile | Pattern | Safety |
|---|---|---|
| app.html:1221, 1222 | `active_profile.daten \| tojson \| safe` | ✅ tojson escaped |
| app.html:1224 | `profiles_for_pip \| tojson \| safe` | ✅ tojson escaped |
| app.html:1402 | `active_phasen \| tojson \| safe` | ✅ tojson escaped |
| dashboard.html:876 | `longterm_data_json \| safe` | ✅ Backend macht `json.dumps(..., ensure_ascii=False)` (dashboard.py:593) |
| settings.html:220 | `... \| tojson \| safe` | ✅ tojson escaped |
| session_detail.html:116 | `chart_data_json \| safe` | ✅ Backend json.dumps |
| session_detail.html:270 | `conv.precall_briefing \| markdown \| safe` | ✅ markdown-Filter ist bleach-gesichert (laut MASTER-AUDIT-Kontext Phase-08-Hardening) |
| profile_editor.html:758, 766 | `daten \| tojson \| safe` | ✅ tojson escaped |
| training.html:738, 739, 740 | `... \| tojson \| safe` | ✅ tojson escaped |

**Kein roher User-HTML-Inject.** Der markdown-Filter ist die einzige semi-User-Content-Stelle und laut Phase-08-Handoff bereits bleach-gesichert.

### Privacy: Admin-Feld-Leak an User-Templates — keine gefunden

Alle Admin-Gating-Checks in User-Templates verwenden `session.get('rolle') in ('owner', 'admin')` oder `g.user.is_superadmin`:

- `base.html:57` — Superadmin-Link
- `base.html:78` — Admin-Sidebar
- `base.html:81` — Coach-Sidebar
- `profiles_list.html:100, 138, 149` — Admin-Delete-Buttons
- `settings.html:115, 236` — Admin-Tabs
- `logs_page.html:23` — Admin-Hint "nur deine"
- `team.html:89` — Non-Self-Action-Buttons
- `waitlist.py:140` — Route-Level `owner`-Only

**Konsistentes Pattern**, keine Felder in Templates durchgereicht die Admin-only wären.

---

## Severity-Zusammenfassung

| # | ID | Severity | Titel | Relation zu MASTER-AUDIT |
|---|---|---|---|---|
| F-1 | Profile-Validation Client-dünn | MEDIUM | 9 HTML5-attrs, kein Schema-Check — zusammen mit Server-Lücke keine Validation-Firewall | **verstärkt** MEDIUM "Profile-JSON kein Schema-Validator" |
| F-2 | (Schema-Mismatch Client) | — | Kein Finding — Client schreibt korrekt `basis.produktbeschreibung` | Bestätigt H-13 als rein Server-seitig |
| F-3 | TABU-Duplikat | MEDIUM | profile_editor.js:131 spiegelt profile_migration.TABU_DEFAULT_PAIRS | **bereits in MASTER-AUDIT MEDIUM** (keine Doppelzählung) |
| F-4 | `login.html` Orphan | LOW | Template rendered nirgends, legacy Design | neu |
| F-5 | `admin/feedback_notification.html` Orphan | LOW | Include rendered nirgends | neu |
| F-6 | `_tooltip.html` Include-Status unklar | LOW | keine Include-Site gefunden | neu |
| F-7 | `conv.precall_briefing` in session_detail | HIGH | UI zeigt Feature das im Live-Pfad nicht existiert | **verstärkt** H-2 |
| F-8 | `ewb_top2` aktiver Reader im app.js | HIGH | Legacy-Reader rendert noch, Writer-Status unklar | **neu, muss Welle 5 klären** |
| F-9 | Frontend-PreCall-Ping-Pong | HIGH | Frontend sendet, Backend speichert, niemand liest | **verstärkt** H-2 (Frontend-Hälfte) |

**Neue Findings: 4 LOW + 2 HIGH (F-8 eigenständig, F-4/F-5/F-6/F-7/F-9 als Verstärkung/Aufräumung).**

---

## Empfehlungen an André

1. **H-2 PreCall-Entscheidung ist dringender als sie aussah.** Die Feature-Fake-Kette zieht sich durch **drei Schichten** (Frontend-Send → Backend-Store → UI-Anzeige in session_detail). Jede Woche ohne Entscheidung lügt das System den User weiter an.

2. **F-8 `ewb_top2`-Writer-Check priorisieren** — wenn der Writer existiert, haben wir einen zweiten EWB-Render-Pfad neben dem neuen. Wenn nicht, sind `app.js:798-799` + `app_routes.py:145` Dead-Reader-Kette.

3. **Orphan-Templates jetzt wegräumen** (F-4, F-5, F-6). Keine Funktion betroffen, reduziert Nudelcode-Oberfläche. 5 Minuten Arbeit.

4. **Schema-Validation-Härtung** (F-1) ist Teil des Profil-Redesign-Themas. Nicht einzeln angehen.

5. **Alle 4 kleinen JS-Files + 27 Templates: keine LAUNCH-BLOCKER gefunden.** Frontend-Layer ist deutlich sauberer als Service-Layer.

---

*Stand 2026-04-24, Welle 4 komplett für kleine JS + Templates. `static/app.js` + `static/pip-launcher.js` wurden nur punktuell (Grep auf kritische Schlüssel) gescannt — vollständige Analyse empfiehlt sich separat (4440 Z. kombiniert).*
