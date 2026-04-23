---
status: code_complete_wave7_deferred
phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration-
source: [08-VERIFICATION.md]
started: 2026-04-22T00:00:00Z
updated: 2026-04-23T00:00:00Z
uat_approved: 2026-04-23
wave7_deferred: true
wave7_reason: Training-Pipeline nutzt noch v1 (nicht v2-modular aus Phase 08). Wave 7 nach Phase 08.5, wenn Training auf v2-modular läuft — erst dann liefern die Quality-Gate-Daten ehrliche Metriken.
---

## Current Test

[awaiting human testing]

## Tests

### 1. Admin-Dashboard /admin/ewb/quality rendert im Browser
expected: |
  Seite lädt ohne 500. Cards für A/B-Stats + Score-Gate + Varianz-Range sichtbar.
  Bei leerer DB: Placeholder-Text "Noch keine Ratings mit success IS NOT NULL".
result: [pending]

### 2. Admin-Rating-Tool /admin/ewb/rating-template rendert + 3-Kriterien-Radio-Roundtrip
expected: |
  Tabelle mit ObjectionEvents. User klickt Ja/Nein-Paare für klingt/halluzi/trifft bei einer Row.
  Nach 3. Klick: Grüner Flash-Hintergrund. Row persistiert in ewb_ratings-Tabelle mit rater_id = g.user.id.
result: [pending]

### 3. PreCall-Anrede-Wahl (Du/Sie) in PiP-Launcher Step 3
expected: |
  Zwei Buttons sichtbar, Default "Sie" aktiv. Klick auf "Du" toggelt Active-Class.
  State persistiert in state.precallFormData.anrede. Session-Start emitted { anrede: "Du" }.
  Server schreibt ls.state['session_anrede']="Du". Nach Call-End landet "Du" in conversation_logs.anrede.
result: [pending]

### 4. Session-Detail 3-Button-Rating (Erfolg/Kein Erfolg/Überspringen) pro ObjectionEvent
expected: |
  Benefit-Framing-Block "Hilf uns, dir zu helfen…" sichtbar oberhalb Timeline. 3 Buttons pro Event.
  Klick updated Button-Class ohne Reload, POST /api/ewb/<id>/rate gibt 200 mit success=true/false/null.
  Bereits-gerated-Events zeigen aktiven Button bei Page-Load.
result: [pending]

### 5. Profile-Editor Tooltip-3-Block-Display
expected: |
  Hover/Focus auf i-Button (>=16x16px) für jedes der 6 neuen/geänderten Felder
  (branche, branche_kontext, eigene_formulierungen, beweise, ton, zusatz) zeigt
  3 Text-Blöcke "Was rein soll / Beispiel / Nicht verwechseln mit".
  Keine D-20-Verletzungen (keine NERVE-Claims, keine echten Firmen, kein "2,3x ROI").
result: [pending]

### 6. Profile-Editor Beispiel-Profil-Modal Open/Close
expected: |
  Klick auf "Sieh dir ein ausgefülltes Beispiel an" öffnet Modal mit 7 Sektionen
  (Anna S., Firma XY GmbH, Firma Z GmbH). Schließen per X, Outside-Click und ESC.
  Nur fiktive Platzhalter.
result: [pending]

### 7. Profile-Editor Save-Roundtrip mit 4 neuen Feldern (Pitfall 1 Regression)
expected: |
  User füllt eigene_formulierungen (2 Zeilen), beweise (2 Zeilen), branche_kontext (1 Satz),
  wählt branche=Maschinenbau, ton=Direkt/Klartext. Save → Success-Flash.
  Reload der Seite: ALLE 4 Felder + branche + ton noch befüllt.
  Kein Data-Loss durch Wholesale-JSON-Replace.
result: [pending]

### 8. ton-Flex-Escape Dynamic-Show/Hide (eigener_stil)
expected: |
  ton-Select auf "Eigener Stil" setzen → Flex-Input erscheint dynamisch.
  Wert eingeben, Save, Reload → Wert bleibt erhalten und Flex-Input ist wieder sichtbar.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Gaps
