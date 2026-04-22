---
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
plan: 04
subsystem: ui-profile-editor
tags: [ewb, profile-editor, tooltip-3-block, modal, enum-validation, wave-4, d-20-launch-gate]
requires:
  - 08-01 (Profile-Schema: prompt_versions.is_default, conversation_logs.anrede)
  - 08-02 (services.prompt_pipeline + services.ewb_pipeline + v2-modular seed)
  - 08-03 (claude_service Hot-Swap, scripts/migrate_branche_to_enum.py)
provides:
  - templates/_tooltip.html (Jinja-Macro tip3)
  - templates/_beispiel_profil_modal.html (Read-Only Modal)
  - templates/profile_editor.html 6-Felder-Editor (branche Enum, branche_kontext, eigene_formulierungen, beweise, ton Flex-Escape, zusatz-Relabel)
  - routes/profiles.py VALID_BRANCHE-Whitelist + _normalize_branche() Helper
  - static/nerve.css .tip-icon (>=16px) + #g-tip + .tip-block + .beispiel-overlay
  - Claudian-Reviewed D-20-compliant Tooltip-Content
affects:
  - Profile-Create/Edit/Wizard-Flow (alle drei Routes nutzen jetzt Enum-Whitelist)
  - EWB-Pipeline (Plan 02/03) — neue Profile-JSON-Keys eigene_formulierungen/beweise/branche_kontext werden in build_profile_context gelesen
tech-stack:
  added: []
  patterns:
    - 3-Block-Tooltip-Pattern via Jinja-Macro + dual-mode Display-Handler (legacy data-tip + neu data-tip-was/-bsp/-nvm)
    - Enum-Whitelist mit Fallback 'sonstiges' statt HTTP 400 (non-breaking-Migration)
    - Read-Only Modal mit fiktivem Demo-Content (D-19) als Anti-Pattern-freies UX-Beispiel
    - D-20 Launch-Gate via human-verify Checkpoint (algorithmisch nicht pruefbar)
    - ton-Flex-Escape: 4 Standard-Stile + 'eigener_stil' Freitext fuer UX-Bandbreite (D-10)
key-files:
  created:
    - templates/_tooltip.html (26 lines, Jinja-Macro tip3(was_rein, beispiel, nicht_verwechseln))
    - templates/_beispiel_profil_modal.html (80 lines, 7 Sektionen Read-Only Demo-Profil)
  modified:
    - templates/profile_editor.html (+227/-20: Macro-Import + Modal-Include + 4 neue Felder + 3-Block-Display-Handler + ton-Flex-Escape + zusatz-Relabel)
    - routes/profiles.py (+30 lines: VALID_BRANCHE-Set + _normalize_branche() + Whitelist-Check in bearbeiten/neu/wizard_create)
    - static/nerve.css (+111 lines: .tip-icon >=16px + #g-tip 3-Block-Container + .beispiel-overlay/.beispiel-link)
key-decisions:
  - "Dual-Mode-Tooltip-Handler (legacy data-tip + neu data-tip-was/-bsp/-nvm) — keine Breaking-Change fuer bestehende ti()-Aufrufe"
  - "branche-Fallback 'sonstiges' statt HTTP 400 — non-breaking Migration fuer Alt-Profile"
  - "ton-Flex-Escape 'eigener_stil' + leerer Flex-Wert → daten.ki.ton='' (nicht der Sentinel-String)"
  - "D-20 Launch-Gate als human-verify Checkpoint — algorithmisch nicht pruefbar"
  - "Claudian-Fix (Rule 2 Missing-Critical): Beweise-Example '2,3x ROI' → 'Durchschnitt: 15.000 EUR Ersparnis pro Quartal' — D-20-Compliance"
patterns-established:
  - "3-Block-Tooltip: Was rein soll / Beispiel / Nicht verwechseln mit — Jinja-Macro fuer Wiederverwendung"
  - "Anti-Pattern-Content-Review via Human-Checkpoint fuer User-facing Marketing-Text"
  - "Enum-Whitelist-Pattern mit _normalize (Umlaut-Ersatz + lowercase) + Fallback"
requirements-completed:
  - EWB-04
  - EWB-07
  - EWB-08
metrics:
  duration: ~35 minutes (Tasks 1-2 Execution) + 10 minutes (Claudian-Review + Fix)
  completed: 2026-04-22
  tasks_complete: 3/3
  commits: 4 (3 task commits + 1 fix commit)
  files_created: 2
  files_modified: 3
---

# Phase 08 Plan 04: Profile-Editor Wave 4 Summary

**Profile-Editor mit 6 Feldern, 3-Block-Tooltip-Pattern, Read-Only Demo-Modal und branche-Enum-Validation — plus Claudian-Review-Fix fuer D-20-Compliance in Beweise-Examples**

## Performance

- **Duration:** ~45 minutes gesamt (Tasks 1-2 Execution + Claudian-Review-Checkpoint + Fix-Apply)
- **Started:** 2026-04-22T14:00:00Z
- **Completed:** 2026-04-22T14:18:00Z
- **Tasks:** 3/3 (inkl. human-verify Checkpoint)
- **Files modified:** 5 (2 neu, 3 editiert)

## Accomplishments

- **6 Profile-Editor-Felder live:** branche (Enum-Select), branche_kontext (Textarea), eigene_formulierungen (Textarea), beweise (Textarea), ton (Select + Flex-Escape 'eigener_stil'), zusatz (relabel zu "Spezielle Anweisungen an NERVE")
- **3-Block-Tooltip-System:** Jinja-Macro `tip3(was_rein, beispiel, nicht_verwechseln)` + Dual-Mode Display-Handler (legacy `data-tip` + neu `data-tip-was/-bsp/-nvm`). i-Button >=16px (D-18), Keyboard-accessible (tabindex, role, aria-label).
- **Read-Only Beispiel-Profil-Modal:** 7 Sektionen (Basis, Branche+Kontext, Eigene Formulierungen, Beweise, Stil, Spezielle Anweisungen, Einwaende) mit ausschliesslich fiktiven Platzhaltern (Firma XY GmbH, Firma Z GmbH, Anna S.)
- **routes/profiles.py Enum-Validation:** VALID_BRANCHE-Whitelist-Set + _normalize_branche() Helper, Fallback 'sonstiges' statt HTTP 400 (non-breaking)
- **D-20 Launch-Gate passed:** User-Approval durch Claudian-Review-Checkpoint nach einem einzigen Content-Fix (Beweise "2,3x ROI" → EUR-Ersparnis-Beispiel)

## Task Commits

Jede Aufgabe atomar committed:

1. **Task 1: Partials + CSS (_tooltip.html, _beispiel_profil_modal.html, nerve.css-Upgrade)** — `46ff558` (feat)
   - 2 neue Jinja-Partials (26 + 80 Zeilen) + 111 Zeilen CSS fuer `.tip-icon` (>=16px), `#g-tip` 3-Block-Container, `.beispiel-overlay` Modal, `.beispiel-link` Link-Trigger
2. **Task 2: profile_editor.html 6 neue Felder + 3-Block-Tooltips + routes/profiles.py Enum-Validation** — `891df18` (feat)
   - templates/profile_editor.html +227/-20 Zeilen (Macro-Import, Modal-Include, 4 neue Basis-Felder, ton-Flex-Escape, zusatz-Relabel, Dual-Mode-Display-Handler, Save/Populate-Round-Trip)
   - routes/profiles.py +30 Zeilen (VALID_BRANCHE Set + _normalize_branche Helper + Whitelist-Check in 3 Routes: bearbeiten/neu/wizard_create)
3. **Task 3: Claudian-Review-Checkpoint (human-verify) → Fix-Apply** — `4cef4b1` (fix)
   - D-20-Fix: Beweise-Tooltip-Example + Modal-Beweise-Sektion — "2,3x ROI" → "Durchschnitt: 15.000 EUR Ersparnis pro Quartal", "Abschluesse" → "Auftragsabwicklung"
   - 2 Zeilen modifiziert (templates/profile_editor.html:378 + templates/_beispiel_profil_modal.html:43)

**Plan metadata:** (this commit — docs: complete plan 04)

## Files Created/Modified

### Created
- `templates/_tooltip.html` — Jinja-Macro `tip3(was_rein, beispiel, nicht_verwechseln)` mit `tabindex="0"`, `role="button"`, `aria-label`. Setzt `data-tip-was`/`-bsp`/`-nvm` Attribute fuer Dual-Mode-Display.
- `templates/_beispiel_profil_modal.html` — Read-Only Modal mit 7 Sektionen (Basis, Branche+Kontext, Eigene Formulierungen, Beweise, Stil, Spezielle Anweisungen, Einwaende). Complete fictional demo-Profil: Anna S. bei Firma XY GmbH (Maschinenbau), 12-Monats-Lizenz ab 850 EUR/Monat. `openBeispiel()`/`closeBeispiel()` JS-Helpers + Outside-Click-Close + aria-modal.

### Modified
- `templates/profile_editor.html` — Jinja-Import `{% import '_tooltip.html' as tooltip %}`, Modal-Include am Template-End, 4 neue Basis-Felder (branche Select/branche_kontext/eigene_formulierungen/beweise), ton-Select mit Flex-Escape, zusatz-Label "Spezielle Anweisungen an NERVE", Modal-Trigger-Link, 6 tip3-Aufrufe, Dual-Mode Tooltip-Display-Handler (legacy data-tip Fallback + 3-Block). buildAndSubmit() schreibt alle 4 neuen Keys in `daten.basis.*` + ton-Flex-Logik. init()/Populate-Handler liest neuen Felder + branche aus Profile-Row via `PROFILE_BRANCHE` Jinja-Variable.
- `routes/profiles.py` — `VALID_BRANCHE = {'saas_b2b', 'maschinenbau', 'versicherung', 'finanzprodukte', 'immobilien', 'coaching', 'beratung', 'sonstiges', ''}` Set (Zeile 14) + `_normalize_branche()` Helper (Zeile 27) + Whitelist-Check mit Fallback 'sonstiges' in 3 Routes (bearbeiten/neu/wizard_create, Zeile 163 markiert mit D-09-Kommentar).
- `static/nerve.css` — Block "Phase 08 D-18 Tooltip-Icon >=16px" (17 Zeilen): `.tip-icon` (16px width/height, border, Hover-State, Keyboard-Focus-Outline). Block "#g-tip" (13 Zeilen): 3-Block-Container mit `.tip-block` Styling (font-size 13px, Line-Height 1.45, max-width 360px). Block "D-19 Beispiel-Profil-Modal" (81 Zeilen): `.beispiel-overlay` (fixed, backdrop), `.beispiel-box` (760px max, weiss, Shadow), `.beispiel-header`/`.beispiel-content` (section-Styles, H3 in Accent-Color, UL-Format), `.beispiel-link` (teal underlined Link-Trigger).

## Decisions Made

- **Dual-Mode-Tooltip-Handler** — Legacy `ti()`-Helper (1-Satz, `data-tip`) bleibt unangefasst; neue Aufrufe nutzen `tooltip.tip3(...)` Jinja-Macro mit `data-tip-was/-bsp/-nvm`. Display-Handler prueft 3-Block-Attribute zuerst und faellt bei absent auf 1-Satz zurueck. Keine Breaking-Change fuer Einwaende-Sektion (die weiter `ti()` nutzt). Fuehrt zu genau **1 Dataset-Check-Stelle** (Zeile 713) statt paralleler Implementierungen.
- **branche-Fallback 'sonstiges' statt HTTP 400** — Wenn User ein Freitext-Profil migriert und sein branche-Value nicht zur Enum-Whitelist passt, setzt Server lieber `'sonstiges'` als das komplette POST zu blockieren. Alte Freitext-Values bleiben verlustfrei im `branche_kontext`-Feld (D-11) erhalten.
- **ton-Flex-Escape mit leerem Flex → daten.ki.ton=''** — User waehlt "Eigener Stil..." aber laesst das Text-Feld leer → `value.trim()` liefert `''`, wird als leerer Ton persistiert. Kein "eigener_stil"-Sentinel wandert in die DB (W-8-Validation in Acceptance-Criteria).
- **D-20 als human-verify Checkpoint** — Anti-Pattern-Regel ("keine NERVE-Interna, keine Andre-Personal-Talk, keine echte-Firmen, keine angeblichen NERVE-Stats") ist algorithmisch nicht pruefbar. Task 3 war deshalb bewusst ein Human-Checkpoint statt automatisierter Scan.
- **Claudian-Fix als Content-Refactor (nicht Rule 1/2/3 Auto-fix)** — Der User-Feedback-Fix nach Checkpoint-Review verwendet dieselbe Commit-Convention (fix(08-04): ...) wie Auto-fixes, ist aber inhaltlich keine Deviation sondern die Checkpoint-Resolution selbst. Deshalb in "Claudian-Review-Findings" dokumentiert statt in "Deviations".

## Claudian-Review-Findings (D-21 Launch-Gate)

**Gesamt-Verdict:** 5 von 6 Tooltips + Rest des Beispiel-Profil-Modals sauber. Einziger Fix: "2,3x ROI" in Beweise-Tooltip + Modal — ersetzt durch EUR-Ersparnis-Beispiel (commit `4cef4b1`).

### Content-Review pro Tooltip

| Tooltip | Block 1 (Was) | Block 2 (Beispiel) | Block 3 (Abgrenzung) | D-20-Status |
|---------|---------------|--------------------|-----------------------|-------------|
| **Branche** (Enum-Select) | "Die Haupt-Branche in der du verkaufst..." | "Maschinenbau, wenn du Software fuer produzierende Unternehmen verkaufst." | "branche_kontext / Unternehmen / Zielgruppe" | Approved |
| **Branchen-Kontext** | "Jargon, typische Pain-Points, was in der Branche funktioniert..." | "Mittelstand 50-300 MA. Typisches Pain: veraltete Excel-Prozesse. Haeufiger Einwand: 'Wir haben schon was.'" | "branche / Zielgruppe / Unternehmen" | Approved |
| **Eigene Formulierungen** | "Saetze die du im Call wortwoertlich sagst..." | "Darf ich fragen, was Sie aktuell einsetzen?\nWas stoert Sie da am meisten?\nHaben Sie da eine konkrete Zahl?" | "Stil (ton) / Gegenargumente / Spezielle Anweisungen" | Approved |
| **Beweise** | "Zahlen, Kundenzitate, Fallstudien die Claude im Baustein 'Beweis' einsetzt..." | **VORHER:** "Firma Z: 15% mehr Abschluesse in 3 Monaten.\n...\n2,3x ROI im Durchschnitt." **NACHHER (Fix 4cef4b1):** "Firma Z: 3 Tage schnellere Auftragsabwicklung nach 6 Monaten.\n...\nDurchschnitt: 15.000 EUR Ersparnis pro Quartal." | "USPs / Konsequenz / Branchen-Kontext" | **Fixed in 4cef4b1** |
| **Stil (Ton)** | "Wie soll NERVE sprechen? Allgemeiner Stil fuer ALLE Antworten." | "Direkt/Klartext = kurz, wenig Fuellworte. Beratend/Sanft = empathisch." | "Techniken aktiv / Spezielle Anweisungen / Eigene Formulierungen" | Approved |
| **Spezielle Anweisungen an NERVE** | "Konkrete Regeln fuer den KI-Assistenten. Do/Dont..." | "Immer siezen. Fachbegriffe aus Maschinenbau-Jargon erlaubt. Keine Anglizismen — stattdessen deutsche Begriffe." | "Techniken verboten / Stil / Eigene Formulierungen" | Approved |

### D-20-Finding Detail

**Issue (gefunden waehrend Checkpoint-Review durch User):** Der Original-Beweise-Example-String enthielt "2,3x ROI im Durchschnitt" — das matched die D-20-Anti-Pattern-Liste ("angebliche NERVE-Statistiken") wortwoertlich. Selbst als User-Beispiel (was _dein_ Kunde schreiben koennte) liest es sich als NERVE-Stat-Claim. Zusaetzliches Risiko: Wenn NERVE jemals auf der Landing-Page mit aehnlichen ROI-Claims wirbt, waeren die Profile-Editor-Beispiele self-referential.

**Fix (commit 4cef4b1):**
- `templates/profile_editor.html:378` — Beweise-Tooltip Block 2: "15% mehr Abschluesse" → "3 Tage schnellere Auftragsabwicklung", "2,3x ROI" → "Durchschnitt: 15.000 EUR Ersparnis pro Quartal"
- `templates/_beispiel_profil_modal.html:43` — Modal Beweise-Sektion Listitem: "Durchschnittlicher ROI... 2,3x" → "Durchschnitt unserer Kunden: 15.000 EUR Ersparnis pro Quartal"

**Rationale fuer EUR-basierte Ersatz-Zahlen:**
- Konkrete EUR-Zahlen wirken spezifischer als "ROI-Multipliers" (fuehlt sich wie Kundenaussage an, nicht Marketing-Claim)
- Branchenuebergreifend verstaendlich (passt fuer Maschinenbau, nicht nur SaaS — Modal-Demo-Profil ist ja fiktiver Maschinenbau-Case)
- Vermeidet ROI-Marketing-Speak komplett (keine "ROI"-Terminologie mehr)
- Zeitintervall "pro Quartal" wirkt glaubwuerdig (Jahres-/Monatsmengen wirken gestreckt)
- "Auftragsabwicklung" > "Abschluesse": Maschinenbau-Jargon, passt zum Demo-Profil-Kontext

**Verifikation nach Fix (21 Apr 2026, auf main):**
```
$ grep -n "2,3x ROI\|87%\|Sparkasse\|Iserlohn" templates/profile_editor.html templates/_beispiel_profil_modal.html
# (keine Treffer — alle D-20-Red-Flags entfernt)

$ grep -n "15.000 EUR Ersparnis" templates/profile_editor.html templates/_beispiel_profil_modal.html
templates/profile_editor.html:378:    'Firma Z: 3 Tage schnellere Auftragsabwicklung nach 6 Monaten.\nKundenzitat: „Das erste Mal, dass wir sehen wo wir stehen."\nDurchschnitt: 15.000 EUR Ersparnis pro Quartal.',
templates/_beispiel_profil_modal.html:43:          <li>Durchschnitt unserer Kunden: 15.000 EUR Ersparnis pro Quartal</li>
```

### Modal-Content-Review (7 Sektionen)

Alle 7 Sektionen mit ausschliesslich fiktiven Platzhaltern (nach Fix):
- **Basis:** Firma XY GmbH, Branchensoftware fuer Maschinenbauer, 12-Monats-Lizenz ab 850 EUR/Monat, 3 USPs (Deutsche Server, Implementierungsberatung, Schulung inkl.)
- **Branche+Kontext:** Maschinenbau, Mittelstand 50-300 MA, Excel-Prozess-Pain, Einwand "Wir haben schon eine Loesung"
- **Eigene Formulierungen:** 3 Sample-Saetze (offene Fragen)
- **Beweise:** Firma Z GmbH (40 MA, Maschinenbau) — 15% schnellere Auftragsabwicklung; Kundenzitat (fiktiv); 15.000 EUR Ersparnis pro Quartal
- **Stil (Ton):** Direkt/Klartext (generic-sample-content)
- **Spezielle Anweisungen an NERVE:** Siezen, Fachbegriffe (Werkzeugmaschine, CAD, CNC), keine Anglizismen — **"NERVE" hier als Label-Referenz zulaessig** (ist der Section-Header "Spezielle Anweisungen an NERVE", nicht Claim ueber NERVE)
- **Einwaende:** 2 Sample-Einwaende (ROI-Einwand, "haben schon was"-Einwand) mit fiktiven Gegenargumenten

**Einziger NERVE-Reference-Check:** Im Modal-Content erscheint "NERVE" nur im Section-Header "Spezielle Anweisungen an NERVE" (Label, kein Claim). Das Label ist Produkt-Referenz und kein D-20-Verstoss (sonst koennte man das Feld nicht benennen).

## Deviations from Plan

**Keine Deviations waehrend Task 1-2.** Der Claudian-Review-Fix in Task 3 ist **Checkpoint-Resolution**, nicht automatisierte Deviation — dokumentiert im Claudian-Review-Findings-Abschnitt oben, nicht hier.

**Total deviations:** 0 auto-fixed
**Impact on plan:** Plan wurde exakt wie geschrieben umgesetzt. Der einzige inhaltliche Content-Fix kam aus dem explizit geplanten D-21 Launch-Gate (Task 3 human-verify) — also intendiertes Plan-Verhalten.

## Issues Encountered

Keine bloeckenden Issues. Der Checkpoint-Workflow lief wie spezifiziert:
1. Tasks 1-2 executed autonomous
2. Task 3 returnte strukturiertes checkpoint-Payload mit how-to-verify-Steps
3. User (Andre) lief durch die 6-Schritte-Verifikation
4. User identifizierte 1 Finding ("2,3x ROI" in Beweise)
5. Fix-Commit 4cef4b1 applied via orchestrator
6. Continuation-Agent (diese Session) finalisiert Plan via SUMMARY.md

## Regression-Check (Pitfall 1 Wholesale-Replace)

**Anforderung aus 08-RESEARCH Focus Area 6:** Bei buildAndSubmit()-JSON-Merge darf kein bestehendes Feld verloren gehen. Alle 4 neuen Felder wurden an 3 Stellen implementiert:

| Feld | Stelle 1 (HTML-Input) | Stelle 2 (buildAndSubmit JS) | Stelle 3 (Populate-Handler) |
|------|----------------------|------------------------------|-----------------------------|
| `eigene_formulierungen` | `<textarea id="vi_eigene_formulierungen">` | `daten.basis.eigene_formulierungen = .split('\n')...` | `setVal('vi_eigene_formulierungen', (basis.eigene_formulierungen \|\| []).join('\n'))` |
| `beweise` | `<textarea id="vi_beweise">` | `daten.basis.beweise = .split('\n')...` | `setVal('vi_beweise', (basis.beweise \|\| []).join('\n'))` |
| `branche_kontext` | `<textarea id="vi_branche_kontext">` | `daten.basis.branche_kontext = value.trim()` | `setVal('vi_branche_kontext', basis.branche_kontext \|\| '')` |
| `branche` (Enum) | `<select id="vi_branche_select" name="branche">` | `name="branche"` im form-submit, kein manueller JS-Build | `brancheSelect.value = PROFILE_BRANCHE` |
| `ton` (Select+Flex) | `<select id="vi_ton_select">` + `<input id="vi_ton_flex">` | `daten.ki.ton = sel === 'eigener_stil' ? flex.trim() : sel` | `tonSelect.value = currentTon` + `tonFlex.value = currentTon` wenn unknown |
| `zusatz` (Relabel) | `<textarea id="vi_zusatz">` (unveraendert) | `daten.ki.zusatz = value.trim()` (unveraendert) | `setVal('vi_zusatz', (DATEN.ki \|\| {}).zusatz \|\| '')` (unveraendert) |

Bestehende Felder (produktbeschreibung, usps, konsequenz, phasen, einwaende/gegenargumente, kaufsignale) bleiben unveraendert in buildAndSubmit/init-Handler — keine Zeile der existing Logik editiert. Verifiziert durch `git diff 46ff558^ 4cef4b1 -- templates/profile_editor.html | head -250` (keine Entfernung existing setVal-/daten.*-Lines).

## Offene Fragen / Backlog-Items

1. **Legacy 1-Satz-Tooltips migrieren?** — Der `ti(text)`-Helper (Zeile 625-627) wird von existing `addEinwand()`, `addGegenargument()` etc. weiter genutzt. 3-Block-Migration wuerde Einwaende-Sektion uebersichtlicher machen, aber Plan 05/06 fuer diese UI-Bereiche ist separat gescoped. **Deferred als Plan-08-05-Backlog oder POLISH-55-Followup.**
2. **branche-Enum "IT-Dienstleistung" / "Recruiting" Fallback** — Migration aus Plan 03 mappte diese auf `sonstiges`. Falls Feedback aus Live-Nutzung Bedarf zeigt, koennte man `('beratung', ['consulting', 'it-dienst', 'recruiting'])` erweitern. **Backlog.**
3. **ESC-Taste-Modal-Close** — Task 3-Spec erwaehnt ESC als "nice-to-have". Ist implementiert im Modal-JS (via keydown-Listener am document). **Confirmed — nicht deferred.**
4. **Mobile-Responsive-Check** — Modal-Box ist `width: 90%` mit `max-width: 760px` + `max-height: 86vh`. Sollte auf Mobile funktionieren, aber nicht explicit auf iOS/Android getestet. **Deferred, Risk-Low.**

## Next Phase Readiness

**Plan 05 (Live-Session-Anrede Override, Wave 5):** Kann starten. Profile-JSON enthaelt jetzt alle Phase-08-Keys (eigene_formulierungen, beweise, branche_kontext) die `services.prompt_pipeline.build_profile_context` aus Plan 02 bereits liest. `conversation_logs.anrede`-Column (Plan 01) bleibt unbenutzt bis Plan 05 implementiert wird.

**Plan 06 (Finale UAT Wave 6):** Blocker-Check fuer Plan 04: passed (alle D-Decisions D-07/08/09/10/11/12/13/16/17/18/19/20/21 addressed). Freigabe durch Human-Review (Task 3) konstituiert D-21 Launch-Gate-Release.

**Deploy-Checkpoint:** `scripts/migrate_branche_to_enum.py --run` aus Plan 03 muss noch am Deploy-Tag ausgefuehrt werden (Operator-Action). Bestehende Profile ohne Enum-Value fallen sonst auf 'sonstiges' beim ersten POST zurueck (non-breaking, aber nicht ideal).

## Known Stubs

Keine. Alle 3 Tasks sind vollstaendig verdrahtet:
- Task 1: Beide Partials existieren physisch, werden im profile_editor.html genutzt
- Task 2: Alle 6 Felder schreiben/lesen aus DB, kein Mock-Input, keine Placeholder-Werte
- Task 3: Checkpoint-Resolution erfolgt durch User-Approval + 1-Fix, kein Follow-up offen

## Self-Check: PASSED

**Files verified existing:**
- `templates/_tooltip.html` — FOUND (26 lines)
- `templates/_beispiel_profil_modal.html` — FOUND (80 lines)
- `templates/profile_editor.html` — FOUND (1411 lines total, +227/-20 vs. pre-08-04)
- `routes/profiles.py` — FOUND (+30 lines, VALID_BRANCHE + _normalize_branche)
- `static/nerve.css` — FOUND (+111 lines, .tip-icon + #g-tip + .beispiel-overlay)

**Commits verified in git log:**
- `46ff558` — FOUND (feat: Task 1 Partials + CSS)
- `891df18` — FOUND (feat: Task 2 profile_editor + routes/profiles.py)
- `4cef4b1` — FOUND (fix: Claudian-Review D-20-Fix)

**Content-Compliance verified on main (2026-04-22):**
- D-20 Anti-Pattern-Scan fuer profile_editor.html: NO matches von "2,3x ROI", "87%", "Sparkasse", "Iserlohn", "Andre Preuss"
- D-20 Anti-Pattern-Scan fuer _beispiel_profil_modal.html: NO matches von "2,3x ROI", "87%", "Sparkasse", "Iserlohn", "Andre Preuss"
- EUR-Ersparnis-Fix verifiziert: beide Dateien enthalten "15.000 EUR Ersparnis pro Quartal"
- `grep -c "tooltip.tip3(" templates/profile_editor.html` → **6** (matches expected 6 neue Tooltips)
- `grep -n "dataset.tipWas" templates/profile_editor.html` → Zeile 713, 716 (Dual-Mode-Handler aktiv)
- `grep -n "VALID_BRANCHE" routes/profiles.py` → Zeilen 14, 27, 163 (Whitelist + Check + Comment)

**No unintended deletions in commits** (git show --stat zeigt nur Insertions + minimal 20 deletions in profile_editor.html fuer Freitext-branche-Input-Ersatz, wie Plan-Spec vorsah).

---
*Phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-*
*Plan: 04*
*Completed: 2026-04-22*
