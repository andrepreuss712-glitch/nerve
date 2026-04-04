# Phase 4.5: Training Analytics & Tools — Plan Index

**Phase Goal:** Die Training-Seite zeigt rechts neben den Einstellungen sinnvolle Statistiken und intelligente Tools — der leere Platz ist vollstaendig genutzt.

**Plans:** 4 plans in 4 waves (sequential dependency chain)
**Requirements:** TA-01 through TA-09

## Wave Structure

| Wave | Plan | Autonomous | Description |
|------|------|------------|-------------|
| 1 | 04.5-01 | yes | DB foundation + ConversationLog persistence |
| 2 | 04.5-02 | yes | 5 API endpoints |
| 3 | 04.5-03 | yes | Frontend: HTML/CSS/JS analytics panel |
| 4 | 04.5-04 | no (checkpoint) | Quick-Training integration + visual verification |

## Plans

| Plan | Goal | Tasks | Files Modified | Requirements |
|------|------|-------|----------------|--------------|
| 04.5-01 | DB-Schema + ConversationLog-Persistenz fuer Training-Sessions | 2 | models.py, app.py, training.py, training_service.py | TA-01, TA-05 |
| 04.5-02 | 5 neue API-Endpoints (stats, recommendation, phrases, goal, last-session) | 2 | training.py | TA-01, TA-02, TA-05, TA-06, TA-07 |
| 04.5-03 | Frontend Analytics Panel: 7 Cards + Chart.js + JS Fetch Logic | 2 | training.html, nerve.css | TA-01, TA-03, TA-05, TA-06, TA-07, TA-08, TA-09 |
| 04.5-04 | Quick-Training Flow + Visual Verification (Checkpoint) | 2 | training.html, training.py | TA-04, TA-08, TA-09 |

## Requirement Coverage

| Req | Description | Plan(s) | Coverage |
|-----|-------------|---------|----------|
| TA-01 | GET /api/training/stats liefert Sessions, Dauer, Streak, Heatmap | 01, 02, 03 | Full |
| TA-02 | GET /api/training/recommendation liefert regelbasierte Empfehlung | 02 | Full |
| TA-03 | Einwand-Heatmap zeigt 7 Typen als farbige Kacheln | 03 | Full |
| TA-04 | Klick auf Heatmap-Kachel startet Quick-Training | 03, 04 | Full |
| TA-05 | Phrasen-Bank zeigt Wendepunkt-Saetze, filterbar | 01, 02, 03 | Full |
| TA-06 | Wochenziel-Card mit editierbarem Ziel + Fortschrittsbalken | 02, 03 | Full |
| TA-07 | Letzte Session Card mit Zusammenfassung | 02, 03 | Full |
| TA-08 | Design: #FFFFFF Cards, 12px radius, teal accents | 03, 04 | Full |
| TA-09 | Keine neuen Farben, keine Gradienten, Sidebar unveraendert | 03, 04 | Full |

## Execution

```
/gsd:execute-phase 04.5
```

Plans execute sequentially (each depends on the previous). Plan 04 includes a human verification checkpoint.
