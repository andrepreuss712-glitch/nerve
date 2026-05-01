---
slug: phase0820-prod-bugs
status: resolved
trigger: "Phase 08.20.3 Live-UAT auf Production (getnerve.app) — 3 Production-Bugs gefunden. Phase NICHT approved."
created: 2026-05-01
updated: 2026-05-01
resolved: 2026-05-01
---

## Symptoms

### Bug A (KRITISCH): 500 Internal Server Error auf /api/precall/personalize/save
- **Expected:** User durchläuft Modus-C-Flow → Vorher/Nachher-Modal erscheint mit OK Output → Klick auf "Personalisiert nutzen + Call ▶" → Call startet
- **Actual:** Frontend zeigt rote Schrift unter Original "internal server error"
- **Error:** `POST https://app.getnerve.app/api/precall/personalize/save 500`
- **Console:** `pip-launcher.js?v=1777622301:643 _savePersonalizedAndStartCall` / `pip-launcher.js?v=1777622301:633 document.getElementById.onclick`
- **Reproduction:** Modus-C-Flow → Vorher/Nachher-Modal → Klick "Personalisiert nutzen + Call ▶"

### Bug B: PiP-Briefing-Tab klappt nicht auf
- **Expected:** Klick auf "▶ Briefing: {firmenname} ▼" Header im PiP-Window → Tab klappt auf
- **Actual:** Kein Toggle, kein Aufklappen
- **Reproduction:** Modus B aktiviert → Live-Call → PiP-Window → Klick auf Briefing-Header

### Bug C: Anrede + Vorwissen-Buttons NICHT funktional (R3/R4 Regression)
- **Expected:** Anrede-Toggle (Du/Sie) und Vorwissen-Picker im PiP funktionieren
- **Actual:** Click hat KEINE Wirkung — exakt die Bugs die am 2026-04-30 mit Commit f1916e2 (R3/R4 fix, Event-Delegation Pattern) gefixt wurden
- **Timeline:** Regression eingeführt durch Plan 04 PiP-Briefing-Tab-Hinzufügung
- **Reproduction:** Live-Call → PiP-Window → Anrede oder Vorwissen-Button klicken

## Hypotheses

### Bug A Hypotheses
- H1: CR-01-Fix (org_id-Isolation, Commit 5637098) hat Save-Route gebrochen
- H2: WR-02-Fix (Atomic Transaction mit_for_update, Commit afd97e5) — SQLite kompatibilitäts-Issue (SELECT FOR UPDATE nicht unterstützt)
- H3: DB-Migration nicht oder unvollständig auf Production gelaufen (parent_id, is_personalized, briefing_source_firma fehlen)
- H4: Pydantic/Schema-Validation-Fehler bei neuen Feldern (z.B. briefing_source_firma als nicht-NULL gefordert aber NULL übergeben)

### Bug B + C Hypotheses (gemeinsame Wurzel vermutet)
- H1: Plan 04 PiP-Briefing-Tab-Hinzufügung hat Event-Delegation in _wirePipButtons() gebrochen
- H2: Briefing-Tab-Container fängt Click-Events ab (event.stopPropagation oder z-index-overlay)
- H3: PiP-Window-Setup-Reihenfolge wurde durch Briefing-Tab-Init durcheinander gebracht
- H4: pipEl()-Helper findet Tab-Container nicht im PiP-Window-Document (Cross-Window-DOM-Context-Bug)

## Current Focus

hypothesis: "CONFIRMED — alle 3 Bugs vollständig diagnostiziert."
test: "VPS-Logs + Code-Review"
expecting: "Fixes anwenden"
next_action: "Fixes anwenden in app_routes.py (Bug A) und pip-launcher.js (Bug B+C)"

## Evidence

- timestamp: 2026-05-01T09:22:52
  source: VPS journalctl
  content: "sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session. at app_routes.py line 1176 in api_personalize_skript_save — with _db.begin() called after implicit transaction already started by pre-check queries at lines 1155+1160"

- timestamp: 2026-05-01T09:22:52
  source: VPS journalctl
  content: "HTTP 500 for POST /api/precall/personalize/save confirmed in logs at 09:22:52, 09:22:56, 09:24:20, 09:24:22"

- timestamp: 2026-05-01
  source: static/pip-launcher.js lines 1649+1666
  content: "Briefing-tab-toggle block uses 'e' (undefined) instead of 'ev' (the event param). 'if (e.target.closest(...)' throws ReferenceError on EVERY click. This kills the entire event handler before reaching Anrede (line 1674) and Vorwissen (line 1704) handlers. Shared root cause for Bug B and Bug C."

## Eliminated

- H3 (fehlende DB-Migration): Nicht getestet aber irrelevant — Bug A crasht vorher auf with _db.begin()
- H4 (Pydantic-Validation): Irrelevant — crash ist in Transaktions-Setup
- Bug B H2/H3/H4: Verworfen — klarer Typo e→ev als alleinige Ursache

## Resolution

root_cause: |
  Bug A: `api_personalize_skript_save` in routes/app_routes.py führt zwei SELECT-Queries
  (Org-Check line 1155, Opener-Check line 1160) aus, bevor `with _db.begin()` (line 1176)
  aufgerufen wird. SQLAlchemy (autocommit=False) startet bei der ersten Query automatisch
  eine implizite Transaktion. Der anschließende `with _db.begin()` trifft auf eine bereits
  aktive Transaktion und wirft `InvalidRequestError: A transaction is already begun on this Session.`

  Bug B+C (gemeinsame Wurzel): In `_wirePipButtons()` in static/pip-launcher.js wurde beim
  Plan-04-Briefing-Tab-Block (line 1649) der Event-Parameter `ev` als `e` referenziert
  (`if (e.target.closest('[data-briefing-toggle]'))`). Da `e` nicht deklariert ist, wirft
  jeder Klick im PiP-Fenster einen `ReferenceError`, der den gesamten Event-Handler abbricht.
  Dadurch werden alle nachfolgenden Handler (Anrede line 1674, Vorwissen line 1704) nie
  erreicht — sowohl Tab-Toggle (Bug B) als auch Anrede/Vorwissen (Bug C) sind defekt.

fix: |
  Bug A: `with _db.begin()` entfernen. Stattdessen den gesamten Body (Cap-Check, Delete,
  Insert) direkt im bestehenden Session-Kontext ausführen. Explizites `_db.commit()` am Ende,
  `_db.rollback()` im except-Block. Die _CapExceeded-Exception bleibt erhalten.

  Bug B+C: In `_wirePipButtons()` (pip-launcher.js line 1649 und 1666) `e` durch `ev`
  ersetzen: `if (ev.target.closest('[data-briefing-toggle]'))` und `ev.stopPropagation()`.

verification: |
  Bug A: POST /api/precall/personalize/save → HTTP 200, item_id zurück, VPS-Logs kein Traceback
  Bug B: PiP Briefing-Tab-Header click → Tab klappt auf/zu
  Bug C: Anrede-Button und Vorwissen-Pill im PiP reagieren auf Klick

files_changed:
  - routes/app_routes.py (Bug A: transaction restructure at api_personalize_skript_save)
  - static/pip-launcher.js (Bug B+C: e → ev typo fix in _wirePipButtons)
