---
slug: phase0820-reuat-bugs
status: resolved
trigger: "Phase 08.20.3 Re-UAT — 2 weitere Bugs: Bug E (personalisierter Opener nicht im Live-Call aktiv) und Bug D (PiP-Briefing-Tab klappt nicht auf, separates Issue von B+C)"
created: 2026-05-01
updated: 2026-05-01
---

## Symptoms

### Bug E (KRITISCH): Personalisierter Opener nicht im Live-Call aktiv
- **Expected:** Modus-C-Flow → "Personalisiert nutzen + Call ▶" → speichert Item + setzt es als aktiv für den aktuellen Call → Call startet mit personalisiertem Opener
- **Actual:** DB-Save funktioniert (neues ProfileOpener-Item mit is_personalized=True erstellt, ✨-Badge im Profile-Editor sichtbar). ABER: im Live-Call wird NICHT der personalisierte Opener verwendet, sondern der ursprüngliche/aktive Opener (vor Personalisierung)
- **No error messages** — kein 500, alles läuft durch, aber falsche Daten
- **Timeline:** Erstmals aufgetreten nach Bug-A-Fix (2026-05-01)
- **Reproduction:** Modus-C-Flow komplett durchlaufen → Vorher/Nachher-Modal → "Personalisiert nutzen + Call ▶" → Live-Call beobachten welcher Opener-Text erscheint

### Bug D: PiP-Briefing-Tab klappt nicht auf (separates Bug zu B+C)
- **Expected:** Klick auf "▶ Briefing: {firmenname} ▼" Header → Tab klappt auf/zu
- **Actual:** Kein Toggle — Tab klappt nicht auf. Anrede + Vorwissen-Buttons funktionieren jetzt (Bug-C-Fix aktiv). Bug D ist SEPARATES Issue.
- **Timeline:** Briefing-Tab wurde durch Plan 04 hinzugefügt, hat nie funktioniert
- **Reproduction:** Modus B → Live-Call → PiP-Window → Klick auf Briefing-Header

## Hypotheses

### Bug E Hypotheses
- H1: Save-Flow speichert in DB, aber state.selectedOpenerId wird NICHT auf neue Item-ID umgesetzt. Live-Call-Logik liest state.selectedOpenerId → bekommt alten Opener.
- H2: Save-Response gibt neue Item-ID zurück, aber Frontend ignoriert sie und navigiert direkt zu Step 5 mit unverändertem state.
- H3: Live-Call-Pipeline (build_profile_context oder ähnlich) liest aus bestimmtem Profil-Field das bei Save nicht aktualisiert wird.

### Bug D Hypotheses
- H1: Click-Handler für Tab-Header nicht angebunden in _wirePipButtons() — Variable-Naming-Fix (e→ev) hat andere Handler repariert aber nicht den Tab-Toggle.
- H2: CSS-Toggle (.expanded oder analog) wird gesetzt aber überlagert durch andere Style-Regel.
- H3: Tab-Container hat z-index/overflow-Issue → klappt im DOM auf aber visuell unsichtbar.

## Investigation Notes

### Bug E — Root Cause Confirmed (H1/H2)
Read `_savePersonalizedAndStartCall()` (pip-launcher.js line 638ff):
- API `/api/precall/personalize/save` returns `{item_id: int, ok: true}` on success
- JS success handler ignores `data.item_id` completely — never sets `state.selectedOpenerId = data.item_id`
- Worse: `state._personalizedSkriptText` (the personalized text) is set to null BEFORE being saved anywhere useful
- `_collectEditedTexts()` reads the Step-5 inline-edit textarea, not the personalized text — provides no help
- `startCall()` resolves opener via: `state._editedOpenerText` first, then `state.openerItems.find(o => o.id === state.selectedOpenerId)`
- `state.selectedOpenerId` = old ID → finds old opener in `state.openerItems` → old text in live call

### Bug D — Root Cause Confirmed (Browser CSS API behavior)
- Handler IS registered on `pipWindow.document` (line 1596, capture phase)
- `data-briefing-toggle` IS in `base.html` (line 491) on `#pip-briefing-tab-header`
- `#pip-briefing-tab` IS inside `#pip-live-window` → correctly moved to PiP document
- `_isBriefingTabExpanded()` at line 1794 checks `body.style.maxHeight !== '0'`
- BUT: inline style `max-height:0` in base.html is returned by browser as `'0px'` not `'0'`
- So `'0px' !== '0'` is TRUE → isExpanded wrongly returns true on first click
- First click: `_collapseBriefingTab()` called → sets maxHeight to '0' → no visual change (already 0)
- Second click: maxHeight is now '0' (set programmatically) → correctly detects collapsed → expands

## Current Focus

hypothesis: "RESOLVED — both bugs found and fixed"
test: "Deploy to VPS and verify Modus-C call uses personalized opener + briefing tab toggles on first click"
expecting: "Bug E: live call shows personalized opener text. Bug D: single click opens tab."
next_action: "Deploy"

## Evidence

- timestamp: 2026-05-01T00:00:00Z
  type: code_read
  finding: "_savePersonalizedAndStartCall success handler (line 656-670): data.item_id received from API but never applied to state. state._personalizedSkriptText cleared before being saved to _editedOpenerText."

- timestamp: 2026-05-01T00:00:00Z
  type: code_read
  finding: "_isBriefingTabExpanded() returns body.style.maxHeight !== '0' — fails for initial browser-parsed '0px' from inline style max-height:0."

## Eliminated

- Bug D: H1 (missing handler) — handler exists at line 1649
- Bug D: H2 (CSS class overriding) — toggle uses inline style maxHeight, not class
- Bug D: H3 (z-index/DOM invisible) — elements are correctly in PiP document
- Bug E: H3 (build_profile_context reads wrong field) — bug is fully in frontend state before call start

## Resolution

root_cause: "Bug E: _savePersonalizedAndStartCall clears state._personalizedSkriptText before saving it to state._editedOpenerText; live call resolves opener via old selectedOpenerId and gets original text. Bug D: _isBriefingTabExpanded() checks maxHeight !== '0' but browser returns '0px' for inline style max-height:0, making first click always a no-op collapse."
fix: "Bug E: Added state._editedOpenerText = state._personalizedSkriptText || '' BEFORE clearing _personalizedSkriptText in the save success handler (pip-launcher.js). Bug D: Updated _isBriefingTabExpanded() to also reject '0px' — return mh !== '' && mh !== '0' && mh !== '0px' (pip-launcher.js)."
verification: "Deploy to VPS, run Modus-C flow → verify personalized opener text appears in live call. Run Modus-B flow → verify single click on Briefing header expands tab."
files_changed: "static/pip-launcher.js"
