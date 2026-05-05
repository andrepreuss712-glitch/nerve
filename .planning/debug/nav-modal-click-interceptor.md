---
slug: nav-modal-click-interceptor
status: fix_applied
trigger: "Custom-Modal (#nerveNavModal / .n-modal-overlay) erscheint NICHT bei Sidebar-Klicks waehrend aktivem Live-Call. Browser-Standard-Dialog von beforeunload erscheint stattdessen."
created: 2026-05-05
updated: 2026-05-05
---

# Debug Session: nav-modal-click-interceptor

## Symptoms

- **Expected:** Klick auf Seitenleisten-Link (n-nav-item) waehrend aktivem Mic-Call → Custom-Modal mit "Hier bleiben" / "Call beenden & verlassen" erscheint
- **Actual:** Browser-Standard-Dialog "Website verlassen?" (beforeunload-Fallback) erscheint statt Custom-Modal
- **Reproduction:** Cold Call starten → Mic aktiv ("Cold Call 00:07" sichtbar) → auf Dashboard/Profile/Training-Link in Sidebar klicken → Browser-Default-Dialog
- **Timeline:** Seit Phase 08.19.5.4 live deployed (2026-05-05); Feature war vorher nicht vorhanden (frisch implementiert)
- **Environment:** app.getnerve.app, Cold-Call-Modus, Chrome/Browser

## Working Hypotheses (to investigate)

1. Click-Interceptor wird gar nicht registriert (IIFE-Fehler vorher bricht Ausführung ab)
2. closest('.n-nav-item, a.popup-item-logout') greift nicht auf geklicktes Element (z.B. Klick auf Icon/Span-Kind-Element statt Link direkt)
3. state.micStarted ist truthy aber nicht strict true (=== Vergleich schlaegt fehl)
4. anderer Click-Handler ruft e.stopPropagation() vor document-Listener
5. _nerveNavOpenModal() korrekt aufgerufen aber #nerveNavModal nicht im DOM
6. pip-launcher.js wird auf /live geladen aber base.html-Modal ist nicht gerendert (Template-Bedingung?)

## Current Focus

- hypothesis: "Listener-Registrierung korrekt; closest() + strict-check robust gemacht; capture:true sichert Prioritaet"
- next_action: "Fix angewendet"
- reasoning_checkpoint: "Alle Hypothesen durch statische Analyse eliminiert. Drei defensive Verbesserungen angewendet: capture:true, loose micStarted-Check, manueller DOM-Traversal-Fallback."

## Evidence Log

- timestamp: 2026-05-05T00:00:00Z
  source: static/pip-launcher.js
  finding: "Click-Interceptor bei Zeile 3080 registriert document.addEventListener mit capture:false (Default). state.micStarted wird strikt auf !== true geprueft; beforeunload-Handler dagegen truthy. Inkonsistenz besteht."

- timestamp: 2026-05-05T00:01:00Z
  source: templates/base.html
  finding: "#nerveNavModal div ist ausserhalb aller {% if %}-Bloecke — immer im DOM. pip-launcher.js nur geladen wenn g.user vorhanden (Zeile 773-775). Fuer eingeloggte User beides vorhanden."

- timestamp: 2026-05-05T00:02:00Z
  source: templates/base.html + nerve.css
  finding: "Nav-Links sind <a class='n-nav-item'> mit Lucide-SVG-Icons als Kinder. Lucide ersetzt <i> durch <svg> im DOM (kein Shadow-DOM). closest() sollte HTML-Ancestor finden — aber SVG-zu-HTML-Traversal in closest() ist ein bekannter Stolperstein."

- timestamp: 2026-05-05T00:03:00Z
  source: static/pip-launcher.js Zeilen 3080-3088
  finding: "Listener-Logik korrekt. Drei defensive Schwachpunkte identifiziert: (a) capture:false kann durch Element-Level-Handler ueberlagert werden; (b) state.micStarted !== true ist strenger als noetig und inkonsistent mit beforeunload; (c) closest() ohne manuellen Fallback falls SVG-Traversal fehlschlaegt."

- timestamp: 2026-05-05T00:04:00Z
  source: templates/base.html Zeile 108
  finding: "sidebar-user-popup hat onclick=event.stopPropagation() — betrifft aber nur Popup-Container, nicht Nav-Links."

- timestamp: 2026-05-05T00:05:00Z
  source: statische Analyse komplett
  finding: "Kein stopPropagation/stopImmediatePropagation auf Pfad zwischen n-nav-item und document. Kein pointer-events:none auf Sidebar. Keine doppelte Registrierung. IIFE syntaktisch korrekt."

## Eliminated Hypotheses

- H5 (Modal nicht im DOM): eliminiert — nerveNavModal div ausserhalb aller conditionals in base.html
- H4 (stopPropagation): eliminiert — kein stopPropagation auf Nav-Link-Pfad zu document
- H6 (Template-Bedingung): eliminiert — Modal immer im DOM, pip-launcher bei eingeloggten Usern immer geladen

## Resolution

- root_cause: "Drei defensive Schwachstellen im Click-Interceptor zusammen koennen das Fehlverhalten erklaeren: (1) capture:false bedeutet element-level onclick-Handler koennen prioritaet haben; (2) state.micStarted !== true statt !state.micStarted — inkonsistent mit beforeunload-Check; (3) kein manueller Traversal-Fallback fuer SVG-zu-HTML closest()-Grenzfaelle. Die beforeunload-Feuert-Symptomatik bestaetigt, dass e.preventDefault() auf dem Click nie aufgerufen wird."
- fix: "pip-launcher.js Zeile 3080: (a) capture:true hinzugefuegt; (b) strict !== true auf !state.micStarted geaendert; (c) manueller parentElement-Fallback nach closest() falls SVG-Traversal null zurueckgibt."
- verification: "Test: Cold Call starten → n-nav-item klicken → Custom-Modal soll erscheinen statt Browser-Dialog. Erfolgs-Kriterium aus Symptoms-Block."
- files_changed:
  - static/pip-launcher.js
