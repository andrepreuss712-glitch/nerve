# UI-Audit Ergebnis — 2026-05-03

**Erstellt:** 2026-05-03
**Methode:** Claude-autonomer Code-Scan (Step 1 von 2) + André+Claude Live-Durchgang (Step 2 — Checkpoint)
**Status:** Step 1 vollständig — Step 2 ausstehend

---

## Kritische Findings

| # | Was | Wo (Datei:Zeile) | Warum problematisch | Vorschlag-Fix | Quelle |
|---|-----|-----------------|---------------------|---------------|--------|
| K-01 | Session-Rows ohne onclick/href — Klick navigiert nirgendwo hin | `dashboard.html:729` (renderSessions-Funktion) | User klickt auf Session-Row, Seite lädt neu ohne Navigation. Das Pattern existiert 20 Zeilen tiefer bei `db2-reco-item:749` korrekt. | `onclick="location.href='/session/' + s.id" style="cursor:pointer"` analog zu db2-reco-item — **bereits in Wave-2-Plan abgedeckt** | Claude-autonom |
| K-02 | Profil-Wizard POST gibt 400 / Netzwerkfehler | `profiles_list.html:388` (submitWizard-Funktion), `routes/profiles.py:98-131` | Frontend sendet JSON mit Feldern `name/branche/produkt/preismodell/einwaende/phasen`, Backend liest `request.form.get('firma', ...)` — Feldnamen-Mismatch + Content-Type-Konflikt. Kein X-CSRFToken-Header im Wizard-fetch. | Backend auf `request.get_json(force=True)` umstellen + X-CSRFToken-Header via `_getCsrfToken()` ergänzen — **bereits in Wave-2-Plan abgedeckt** | Claude-autonom |
| K-03 | Sterne-Bewertung: Feature existiert im Backend, hat aber keinen sichtbaren Entry-Point | `routes/app_routes.py:900` (api_session_rating), kein Template-Element | POST `/api/session-rating` ist implementiert und schreibt in DB, aber kein Button/UI-Element ruft diese Route auf. Weder in session_detail.html noch in base.html (PiP) ist eine Sterne-Bewertungs-Oberfläche vorhanden. André wusste selbst nicht, dass das Feature existiert. | Sterne-UI in session_detail.html oder PiP-Postcall-View einbauen (5-Sterne-Widget, onclick→fetch zu /api/session-rating) | Claude-autonom |
| K-04 | Nav-Label "Profil" statt "Profile" | `base.html:56` | Inkonsistente Sprache (DE statt EN) in der Hauptnavigation — alle anderen Labels sind Englisch (Dashboard, Training, Analytics) | `<span class="n-nav-label">Profile</span>` — **bereits in Wave-2-Plan abgedeckt** | Claude-autonom |

---

## Mittel-Findings

| # | Was | Wo (Datei:Zeile) | Warum problematisch | Vorschlag-Fix | Quelle |
|---|-----|-----------------|---------------------|---------------|--------|
| M-01 | Hidden Legacy Nav Items (display:none) — Team, Coach-Dashboard, Changelog nicht sichtbar | `base.html:77-90` | 3 Nav-Links sind im DOM aber nicht sichtbar: `/org/team`, `/coach/`, `/coach/methodik`, `/changelog`. User mit Coach-Rolle oder Owner sieht sein Coach-Dashboard und Team-Verwaltung nicht. Changelog nicht auffindbar. | Nav-Items entweder vollständig entfernen oder sichtbar machen. Coach-Dashboard hat eigene Route — muss sichtbar sein für Coach-User. | Claude-autonom |
| M-02 | PiP-Schließ-Bug: PiP schließt sich bei App-Navigation | `static/pip-launcher.js` (startCall-Funktion, ~Zeile 1285+) | `window.documentPictureInPicture.requestWindow()` bindet PiP an Lebensdauer der Ursprungsseite. Klick auf Nav-Link → PiP schließt sich. | BroadcastChannel + localStorage State-Transfer oder Service Worker — Architekturentscheidung erforderlich, **bereits in Wave-2-Plan abgedeckt** | Claude-autonom |
| M-03 | Live-Call Seite nicht über direkten Link erreichbar, nur über Launcher-Modal | `base.html:42` (Nav), `routes/app_routes.py` (/live-Route) | Nav-Link "Live-Assistent" ruft `window.NerveLauncher.open()` auf — kein direkter Href. Wenn JS nicht lädt, ist Feature komplett unerreichbar. | Fallback-href="/live" zum `<a>`-Tag ergänzen | Claude-autonom |
| M-04 | Logs-Seite: kein direkter Link zur Session-Detail aus der Logs-Tabelle | `logs_page.html:43-78` | Logs-Tabelle zeigt Gespräche aber bietet nur Download-Button, keinen Link zur Session-Detail-Ansicht (`/session/<id>`). Der `session_detail`-Link fehlt vollständig. | "Details"-Button analog zu analytics.html (Zeile 27) in die Logs-Tabelle ergänzen | Claude-autonom |
| M-05 | Analytics-Seite: veraltetes Dark-Theme-Design, nicht mit rest of App konsistent | `analytics.html:36-40` | `n-table` hat `background:#1C2333;color:#fff` (Dark-Mode) während rest of App Light-Mode-Design hat. Visuell inkonsistent, verwirrt User. | Styles auf nerve.css Standard-Tbl-Klassen umstellen | Claude-autonom |
| M-06 | Profile-Wizard: Feldnamen-Mismatch — Frontend-Felder `preismodell` und `phasen` werden nicht im Backend gespeichert | `profiles_list.html:382-385` (submitWizard-Payload) | Frontend sendet `preismodell` und `phasen` als separate Payload-Felder, Backend-Schema kennt diese Felder nicht als Top-Level. Wizard löscht Eingaben still. | Wizard-Payload auf Backend-Schema-Felder mappen (firma/branche/rolle/produkt/zielkunden/einwaende) — **Teil von Wave-2-Fix 1** | Claude-autonom |
| M-07 | profile_wizard.html existiert als separates Template, wird aber nicht verwendet — profiles_list.html hat eigenen Wizard-Modal | `templates/profile_wizard.html` | Zwei Wizard-Implementierungen im Codebase: `profile_wizard.html` (Route `/profiles/wizard` GET) und Wizard-Modal in `profiles_list.html`. Route `/profiles/wizard` GET rendert das separate Template, aber Klick auf "+ Neues Profil" öffnet den Modal-Wizard in `profiles_list.html`. Unklare Architektur. | `profile_wizard.html` entweder entfernen oder als einzige Implementierung nutzen | Claude-autonom |

---

## Kosmetische Findings

| # | Was | Wo (Datei:Zeile) | Warum problematisch | Vorschlag-Fix | Quelle |
|---|-----|-----------------|---------------------|---------------|--------|
| C-01 | "Alle anzeigen →"-Link im Dashboard-Sessions-Widget verlinkt auf `/dashboard` statt auf Analytics/Logs | `dashboard.html:328` | `<a href="/dashboard">Alle anzeigen →</a>` führt zur selben Seite zurück. Sollte auf `/logs` oder `/analytics` zeigen. | href auf `/logs` oder `/analytics` ändern | Claude-autonom |
| C-02 | Coach-Dashboard: Typo "openNeueFiremModal" statt "openNeueFirmaModal" | `coach_dashboard.html:50` (JS-Funktionsname) | Typo im Funktionsaufruf `openNeueFiremModal()` — falls die Funktion korrekt benannt ist funktioniert der Button nicht. Funktionsnamen konsistent machen. | Alle Aufrufe/Definition auf `openNeueFirmaModal` korrigieren | Claude-autonom |
| C-03 | Changelog nicht auffindbar in Hauptnavigation | `base.html:86-89` (display:none) | Changelog ist im Hidden-Legacy-Block. Wenn André Changelogs schreibt, sehen User sie nicht (kein Link). | Changelog-Link aus `display:none`-Block in sichtbare Nav verschieben oder in User-Popup aufnehmen | Claude-autonom |
| C-04 | Dashboard: KPI-Kachel "Deals gesamt" und "Umsatz / Monat" zeigen "—" wenn keine Daten — kein Hinweis wie man Daten eingibt | `dashboard.html:63-71` | User sieht leere KPI-Kacheln ohne Erklärung. Deal-Wert-Modal öffnet sich automatisch einmalig, danach nicht mehr. Es gibt keinen sichtbaren "Deal-Wert eintragen"-Button. | Kleiner Info-Text oder Link in leere KPI-Kacheln einfügen | Claude-autonom |
| C-05 | Settings-Seite: "Tarif upgraden" im User-Popup führt zu `/settings#billing`, aber Billing-Tab nur sichtbar für owner/admin | `base.html:129` | User mit `member`-Rolle klickt "Tarif upgraden", landet auf Settings, sieht keinen Billing-Tab. Frustrierend. | Link nur für owner/admin-Rolle anzeigen | Claude-autonom |
| C-06 | Training-Seite: Sterne-Bewertungs-Hinweis fehlt — kein Hinweis dass Gespräch bewertbar ist | `training.html` (Postcall-Bereich) | Nach Training-Abschluss gibt es keinen Hinweis auf die Sterne-Bewertungsfunktion. Feature ist undiscoverable. | Post-Training-Screen mit Sterne-Widget ausstatten | Claude-autonom |
| C-07 | Onboarding: `profile_result`-Element initial unsichtbar, kein Fallback-Text wenn KI-Generierung fehlschlägt | `onboarding.html` (profile-result-Klasse) | `<div class="profile-result">` startet mit `display:none` und wird nur via JS sichtbar. Kein sichtbarer Ladezustand für User. | Loading-Spinner + Error-Fallback beim Profil-Generieren ergänzen | Claude-autonom |

---

## Seiten-Inventur

### 1. Dashboard (`templates/dashboard.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| "🟢 Call starten"-Button | `<a>` | `onclick="window.NerveLauncher && window.NerveLauncher.open()"` | Ja (JS-abhängig) | Kein Fallback-href wenn JS nicht lädt |
| "Training"-Button | `<a href="/training">` | href="/training" | Ja | OK |
| "Echte Daten / Simulation"-Toggle | `<button>` | `onclick="perfSetMode('real'/'sim')"` | Ja | OK |
| Slider (Simulation) | `<input type="range">` | `oninput="simUpdate()"` | Ja | OK |
| "Kein Deal-Wert hinterlegt — jetzt eintragen" | `<a href="#">` | `onclick="openDealWertModal();return false"` | Ja | OK |
| Deal-Wert-Modal: "Speichern"-Button | `<button>` | `onclick="saveDealWert()"` | Ja, fetch zu `/api/user/deal-wert` | OK |
| Deal-Wert-Modal: "Später"-Button | `<button>` | `onclick="closeDealWertModal()"` | Ja | OK |
| Session-Rows (Letzte Sessions) | `<div class="db2-session-row">` | **Kein onclick/href** | **NEIN — K-01** | Bug: Klick navigiert nirgendwo hin |
| Empfehlungen (db2-reco-item) | `<div>` | `onclick="location.href=r.url"` wenn r.url vorhanden | Ja (bedingt) | OK |
| "Alle anzeigen →" | `<a href="/dashboard">` | href="/dashboard" | Ja, aber falsch | C-01: Sollte auf /logs zeigen |
| Wochenbericht-Charts | `<canvas>` | — | Ja (read-only) | Kein klickbares Element |
| Ergebnis-Tagging (Sterne/Tags) | `<button data-tag>` | onclick → fetch | Ja | Sterne-Tagging vorhanden im Session-Detail |

**Discoverability-Check:**
- Deal-Wert-Eintragung: erscheint als Modal automatisch, danach kein sichtbarer Einstiegspunkt (C-04)
- Session-History: Rows nicht klickbar → User vermutet keine Navigation (K-01)
- Training-Empfehlung: nur sichtbar wenn Backend Empfehlung liefert

---

### 2. Profile (`templates/profiles_list.html`, `profile_editor.html`)

**Klickbare Elemente in profiles_list.html:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| "+ Neues Profil"-Button | `<button>` | `onclick="openWizard()"` | Ja | Öffnet Modal-Wizard |
| Profil-Karte (onclick) | `<div>` | `onclick="openWizard()"` (nur leere Karte) | Ja | OK |
| "Aktivieren"-Button | `<form method="post">` | action="/profiles/{{ p.id }}/activate" | Ja + CSRF-Token | OK |
| "Bearbeiten"-Link | `<a href="/profiles/{{ p.id }}/edit">` | href | Ja | OK |
| "Löschen"-Button | `<form method="post">` + confirm | action="/profiles/{{ p.id }}/delete" | Ja + CSRF-Token | OK |
| Wizard: "Weiter"-Button | `<button id="wiz-next-btn">` | onclick → JS-Flow | Ja | OK |
| Wizard: "Profil erstellen ✓"-Button | `<button id="wiz-next-btn">` | `submitWizard()` | **NEIN — K-02** | Bug: POST gibt 400 |
| Wizard: "✕"-Schließ-Button | `<button class="wiz-close">` | `onclick="closeWizard()"` | Ja | OK |
| Wizard: Template-Laden | `<button class="btn-load-tmpl">` | `onclick="loadTemplate()"` | Ja | OK |

**Discoverability-Check:**
- "+ Neues Profil" nur sichtbar für owner/admin (korrekt)
- Wizard-Funktion hat 2 parallele Implementierungen (`profile_wizard.html` + Modal) — unklar welche genutzt wird (M-07)

---

### 3. Live-Call / PiP-Launcher (`templates/base.html` — PiP in DOM, `static/pip-launcher.js`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Nav "Live-Assistent"-Link | `<a href="javascript:void(0)">` | `onclick="window.NerveLauncher && window.NerveLauncher.open()"` | JS-abhängig | **M-03: Kein Fallback-href** |
| Dashboard "🟢 Call starten" | `<a>` | `onclick="window.NerveLauncher && window.NerveLauncher.open()"` | JS-abhängig | Gleicher Mangel |
| PiP-Modal: Launcher-Steps 1-5 | komplexes JS-UI | pip-launcher.js | Ja (komplex) | OK |
| PiP: "Call starten"-Button (Step 5) | `<button id="lnr-step5-start">` | onclick → startCall() | Ja | OK |
| PiP: "Call beenden"-Button | `<button id="nlp-btn-beenden">` | onclick → endCall() | Ja | OK |
| PiP: EWB-Buttons (Einwand-Tracking) | `<button class="pip-ewb-btn">` | event delegation → _triggerEwb() | Ja | OK |
| PiP: Schließ-Bug bei Navigation | — | documentPictureInPicture-API | **NEIN — M-02** | PiP schließt sich bei Seitennavigation |

**Discoverability-Check:**
- Live-Call-Feature ist auffindbar über Nav + Dashboard-Button
- EWB-Buttons werden nur aus Profil geladen — kein Profil = keine Buttons (kein Hinweis)
- Sterne-Bewertung nach Call nicht vorhanden im PiP-Postcall (K-03)

---

### 4. Training (`templates/training.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Profil-Select | `<select id="t-profileSelect">` | `onchange="checkReady()"` | Ja | OK |
| Schwierigkeits-Karten | `<div class="t-diff-card">` | `onclick="selectDiff('{{ key }}')"` | Ja | OK |
| Kundentyp-Karten | dynamisch via JS | onclick → Kundentyp-Selektion | Ja | OK |
| "Training starten"-Button | `<button class="t-call-btn">` | fetch POST zu `/training/start` | Ja | OK |
| Chat: Senden-Button | `<button>` | onclick → sendMessage() | Ja | OK |
| "Bewerten"-Button (Postcall) | keiner gefunden | — | **Fehlt** | K-03: Kein Sterne-Rating vorhanden |
| "Nochmal trainieren"-Button | `<button>` oder Link | — | Ja (in session_detail.html) | OK |

**Discoverability-Check:**
- Training-Flow klar: Profil wählen → Schwierigkeit → Kundentyp → Start
- Kein Hinweis auf Sterne-Bewertung nach Training (C-06)
- Wenn kein Profil vorhanden: Hinweis "bitte erst Profil anlegen" vorhanden (gut)

---

### 5. Coach-Dashboard (`templates/coach_dashboard.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| "Neue Firma einladen"-Button | `<button>` | `onclick="openNeueFiremModal()"` | **Möglicherweise kaputt** | C-02: Typo im Funktionsnamen ("Firem" statt "Firma") |
| Firma-Karte | `<div class="firma-card">` | `onclick="window.location='/coach/firma/{{ f.org.id }}'"` | Ja | OK |
| "+ Neue Firma einladen" (leer) | `<div>` | `onclick="openNeueFiremModal()"` | **Möglicherweise kaputt** | C-02: Typo |
| Nav: Coach-Dashboard | `<a href="/coach/">` (hidden) | hidden | **NEIN — M-01** | Im display:none-Block versteckt |

**Discoverability-Check:**
- Coach-Dashboard nicht in sichtbarer Nav (M-01) — nur erreichbar wenn User die URL kennt
- Für normalen Coach-User kein Entry-Point sichtbar

---

### 6. Admin-Bereich (`templates/admin/dashboard.html`, `admin/crm_overview.html`)

**Klickbare Elemente in admin/dashboard.html:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Tab-Buttons (Übersicht/Einnahmen/etc.) | `<button class="fcd-tab">` | data-tab-Attribute + admin_dashboard.js | Ja | OK |
| Zeitraum-Input | `<input type="month">` | onchange via admin_dashboard.js | Ja | OK |
| Alle Detail-Buttons | via `admin_dashboard.js` | — | Ja | OK |

**Nav-Zugang:**
- Admin-Links (Admin, CRM, EWB bewerten, EWB Qualität) nur sichtbar für `g.user.is_superadmin` | OK

**Discoverability-Check:**
- Admin-Bereich korrekt hinter Superadmin-Guard

---

### 7. Settings (`templates/settings.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Tab-Buttons (Profil/Abrechnung/etc.) | `<button class="tab-btn">` | `onclick="showTab('...')"` | Ja | OK |
| "Änderungen speichern"-Button | `<button>` | `onclick="saveProfile()"` | Ja, fetch zu `/settings/profile` | OK |
| Sprach-Select | `<select>` | `onchange="saveLangPref(this.value)"` | Ja, fetch zu `/settings/language` | OK |
| "Standard / Mein Stil"-Buttons | `<button>` | `onclick="toggleStil()"` | Ja | OK |
| "Vorschau generieren"-Button | `<button>` | `onclick="previewStil()"` | Ja | OK |
| Billing-Tab: Tarif-Plan-Cards | `<div class="plan-card">` | — | Read-only (kein Button für Upgrade sichtbar) | Hinweis-Text vorhanden |
| Datenschutz-Tab: Toggles | `<input type="checkbox">` | onchange → fetch | Ja | OK |
| "Abo kündigen" | `<button>` | onclick → Modal + fetch | Ja | OK |
| "Tarif upgraden" im User-Popup | `<a href="/settings#billing">` | href | Ja, aber C-05 | Billing-Tab nur für owner/admin |

**Discoverability-Check:**
- Settings klar strukturiert via Tabs
- Billing-Tab für Member-User nicht sichtbar, aber Link führt dorthin (C-05)

---

### 8. Logs / Analytics (`templates/logs_page.html`, `analytics.html`)

**Klickbare Elemente in logs_page.html:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| "⬇ Download"-Button | `<a href="/logs/download/{{ log.filename }}">` | href | Ja | OK |
| Session-Link (zur Detail-Ansicht) | **fehlt** | — | **NEIN — M-04** | Kein Link zu /session/<id> aus Logs |

**Klickbare Elemente in analytics.html:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Mode-Filter-Select | `<select>` | `onchange="this.form.submit()"` | Ja | OK |
| "Details"-Link pro Session | `<a class="n-btn">` | `url_for('dashboard.session_detail', sid=s.id)` | Ja | OK |

**Discoverability-Check:**
- Logs nur als Download verfügbar, kein direkter Link zur Session-Analyse (M-04)
- Analytics ist das "bessere" Logs mit Details-Link — aber Logs-Seite hat keinen Hinweis darauf

---

### 9. Changelog (`templates/changelog.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| Changelog-Einträge | `<div class="changelog-entry">` | Kein onclick | Read-only | OK — kein Link nötig |
| Nav-Link zu Changelog | `<a href="/changelog">` | hidden (display:none) | **NEIN — C-03** | Nicht in sichtbarer Nav |

**Discoverability-Check:**
- Changelog nicht über Nav erreichbar (C-03)
- Kein Entry-Point für normale User (URL-Kenntnis erforderlich)
- NEU-Badge vorhanden in Legacy-Nav aber nie sichtbar

---

### 10. Performance (`routes/performance.py` — kein eigenes Template gefunden)

**Befund:** Kein separates `templates/performance.html` vorhanden. Route `/performance` existiert als Blueprint (`performance_bp`), aber rendert vermutlich in ein generisches Template oder wird als Tab in Analytics gerendert.

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| `/performance`-Route | Blueprint | performance_bp | Ja (Backend) | Template-Lage unklar — kein eigenes Template im templates/-Verzeichnis |

**Discoverability-Check:**
- Kein eigener Nav-Eintrag für Performance-Seite
- Nicht direkt zugänglich über UI ohne URL-Kenntnis

---

### 11. Onboarding (`templates/onboarding.html`)

**Klickbare Elemente:**

| Element | Typ | Handler/href | Funktioniert? | Notes |
|---------|-----|-------------|---------------|-------|
| "Weiter"-Button (Schritt-Navigation) | `<button class="btn-next">` | onclick → JS nextStep() | Ja | OK |
| "Zurück"-Button | `<button class="btn-back">` | onclick → JS prevStep() | Ja | OK |
| "Überspringen"-Button | `<button class="btn-skip">` | onclick → JS skip() | Ja | OK |
| Erfahrungs-Level-Karten | `<div class="level-card">` | onclick → JS selectLevel() | Ja | OK |
| Branchen-Karten | `<div class="branche-card">` | onclick → JS selectBranche() | Ja | OK |
| Mic-Test-Button | `<div class="mic-btn">` | onclick → Mic-Test | Ja | OK |
| CTA-Cards am Ende | `<div class="cta-card">` | onclick → Navigation | Ja | OK |
| "Diesen Kunden nehmen"-Button | `<button>` | `onclick="confirmGeneratedPersonality()"` | Ja | OK |
| "Nochmal würfeln"-Button | `<button>` | `onclick="generateRandomPersonality()"` | Ja | OK |
| profile_result-Div | `<div class="profile-result">` | — | JS-abhängig | C-07: Kein Lade-Status sichtbar |

**Discoverability-Check:**
- Onboarding-Flow strukturiert und klar
- `profile_result`-Element startet invisible (C-07)
- Kein Fallback wenn Profil-Generierung fehlschlägt

---

## André+Claude Live-Durchgang — Ergänzungen

_[Leer — wird im Checkpoint gefüllt]_

---

*Nächster Schritt: Wave 1 Step 2 — André+Claude Live-Durchgang (Checkpoint ausstehend)*
*Bericht: Step 1 Claude-autonom abgeschlossen. Step 2 (André-UX) nach Live-Durchgang ergänzen.*
