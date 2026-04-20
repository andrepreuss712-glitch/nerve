# Phase 07.1 — Deferred Items

Issues discovered during UAT-R3 scan that are **out of scope** for the current
bug-fix sweep. Tracked here for later planning.

---

## D-1: `window._profileEinwände` Umlaut-Identifier (app.html / app.js)

- **Discovered during:** UAT-R3 preventive Umlaut scan (2026-04-18)
- **Files:**
  - `templates/app.html:1221` (JS-Template-Expression setzt Variable)
  - `static/app.js:244, 2037, 2038, 2071, 2072` (5 Read-Zugriffe)
- **Issue:** `window._profileEinwände` is a JS global identifier with `ä` —
  violates CLAUDE.md code-identifier rule (ASCII-only für Identifier).
- **Why deferred:**
  - No mismatch: Definition + alle Reads nutzen konsistent den Umlaut-Namen.
    Kein aktueller Bug, nur Konventions-Abweichung.
  - Pfad ist **live-session-kritisch** (Einwand-Erkennung während Live-Call).
    Fehler beim Rename würde Live-Sessions brechen — zu risky für UAT-R3-Scope.
- **Suggested fix:** Rename zu `window._profileEinwaende` über alle 6 Stellen
  in einem eigenen Commit mit Full-Regression-Test der Live-Session.
- **Priority:** P2 — Konvention, kein Runtime-Bug.

---
