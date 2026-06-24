---
status: investigating
trigger: "[PERSON_A] (anonymisierte Version) erscheint kurz auf dem SCHIRM beim Umschalten Sekretär(Gatekeeper)→CEO(Zielperson) im Cold-Call. Live-Test 23.06.2026, André. Folge-Bug aus Plan 09 (TAXO2 anon-live-vs-stored, commits 58c5124/b6dd32b/6ca971e, live auf Production). Plan 09 bleibt offen bis sauber."
created: 2026-06-24T00:00:00.000Z
updated: 2026-06-24T12:00:00.000Z
---

## Evidence

- timestamp: 2026-06-24T12:00:00Z
  checked: "static/pip-launcher.js — alle Slot-Body-Schreibpfade (pip-slot-body-0/1)"
  found: |
    Slot-Bodies werden NUR von diesen Handlern beschrieben: pip_stream_start (clear),
    pip_token (raw-stream), pip_token_done -> _renderSlotResult, keyword_einwand_match
    -> _renderSlotResult, qa_slot1, qa_soft_hint, pip_stream_error, _showProactiveContent.
  implication: "Universeller Render-Funnel = _renderSlotResult (Slot 0 keyword + Slot pip_token_done). Plus Live-Stream pip_token + qa_slot1."

- timestamp: 2026-06-24T12:00:00Z
  checked: "_updateContactCategory (pip-launcher.js:2613) — der contact_category_update-Handler"
  found: |
    Setzt NUR Mode-Indikator + re-rendert EWB-Buttons (_renderGatekeeperButtons /
    _renderStandardEwbButtons via /api/gatekeeper/phrases-Fetch). Er TOUCHT die
    Slot-Bodies NICHT — KEIN Slot-Clear beim Wechsel.
  implication: "STALE-Slot-Hypothese gestaerkt: anonymisierter Slot-Inhalt aus der Gatekeeper-Phase bleibt beim Switch sichtbar, weil der Switch-Handler die Slots nie leert."

- timestamp: 2026-06-24T12:00:00Z
  checked: "deepgram_service.py:1056 Mode-Switch-Emit + :237 keyword_einwand_match-Emit"
  found: |
    Mode-Switch emittiert nur contact_category_update + manual_mode_toggle_ack (kein
    Vorschlagstext — bestaetigt Static Elimination). keyword_einwand_match emittiert
    profile_einwand (roh aus Profil) -> gegenargument_1 ist Berater-Text, kein [PERSON_].
  implication: "Frischer Emit beim Switch traegt kein [PERSON_]. Flash muss aus bereits-im-Slot-stehendem Inhalt ODER einem koinzidenten Slot-1-Stream kommen."

- timestamp: 2026-06-24T12:00:00Z
  checked: "claude_service.py:669-694 (Plan-09-Fix streame_auto_variante Display vs Storage)"
  found: |
    display_result/cleaned_display = roh (Plan 09); cleaned_storage separat anonymisiert.
    Eigenes Display-Dict, nie mutiert. Plan-09-Vertrag im Code korrekt.
  implication: "WENN cleaned_display dennoch [PERSON_ traegt, ist der Anonymisierer-Cache in den Display-Pfad geleakt — Marker-5 beweist das live."

## Instrumentation (Logging-First Pass — 5 Marker, observe-only)

- M1 — static/pip-launcher.js  _renderSlotResult (~Z.2727, nach body.textContent-Write):
    console.log '[ANON-FLASH] M1' — jeder Slot-Write via Render-Funnel, flag anon=[PERSON_ im Text.
- M2 — static/pip-launcher.js  pip_token raw-stream (~Z.2355):
    console.log '[ANON-FLASH] M2' — feuert NUR wenn gestreamter Slot-Text [PERSON_ enthaelt (kein Token-Spam).
- M3 — static/pip-launcher.js  _updateContactCategory (~Z.2613, ganz am Anfang):
    console.log '[ANON-FLASH] M3' — Zustand BEIDER Slot-Bodies IM MOMENT des Mode-Switch (Stale-Slot-Smoking-Gun).
- M4 — static/pip-launcher.js  qa_slot1-Handler (~Z.2495):
    console.log '[ANON-FLASH] M4' — QA-Slot-1-Write, flag anon.
- M5 — services/claude_service.py  streame_auto_variante Display-Emit (~Z.681):
    print '[ANON-FLASH] M5' — beweist ob LIVE-emittierter Text roh ist oder Cache-Leak [PERSON_ traegt.

Erwartung: M3 zeigt vermutlich anon=true auf einem Slot beim Switch (Stale).
Falls stattdessen M1/M2/M4/M5 anon=true direkt beim Switch feuert -> frischer Emit-Bug statt Stale.

## Symptoms

expected: |
  Die dem Berater LIVE gezeigte Antwort soll IMMER ECHTE Namen tragen (ANON-LIVE-ANSWER / Plan 09).
  Beim Umschalten von Gatekeeper (Sekretär) auf Zielperson (CEO) bleibt die Anzeige roh —
  keine anonymisierte [PERSON_A]-Variante darf je auf dem Schirm erscheinen.
actual: |
  Beim Modus-Wechsel Gatekeeper→Target erscheint [PERSON_A] (anonymisierter Platzhalter)
  KURZ auf dem Schirm, bevor (vermutlich) die rohe Version nachgeladen wird.
  "kurz" → transienter Verdacht, Frontend-Slot-Re-Render mit STALE Inhalt aus Gatekeeper-Phase.
errors: |
  Kein Error — falscher Anzeigeinhalt (anonymisierte statt rohe Antwort), transient sichtbar.
timeline: "Aufgetreten im Live-Test 23.06.2026 nach Plan-09-Deploy. Plan 09 hat Auto-Variante/QA/Knopf-Display bereits roh gemacht."
reproduction: "Cold-Call live, Wechsel Sekretär(Gatekeeper) → CEO(Zielperson) auslösen. André reproduziert den Wechsel EINMAL mit aktivem Logging auf Production."

## Static Elimination (Claudian — NICHT nochmal durchkauen)

- Auto-Variante-Display (claude_service streame_auto_variante / pip_token_done): roh (Plan 09 gefixt+verifiziert).
- qa_slot1 + FAQ-Antwort (claude_service ~1627/1639/1671): _antwort/_faq_antwort ROH (generate_qa_response anonymisiert NICHT intern).
- Knopf-Display (streame_manual_ewb_variante:823): roh.
- Mode-Switch-Handler (deepgram_service.py:1056): NUR Status-Events (contact_category_update / manual_mode_toggle_ack), kein Vorschlagstext.
- Übrige anonymize_output-Aufrufe (claude_service 1036/1100/1572/1787, einwand_keyword_matcher:306): Speicher-Log ODER triggering_text fürs intent_event — KEIN Display-Emit.

## Investigation Constraints (vom User vorgegeben)

- LOGGING-FIRST (CLAUDE.md Punkt 15): KEIN Fix im ersten Pass. Zuerst 3-5 Marker an die DISPLAY-Pfade,
  die beim Gatekeeper→Target-Wechsel feuern könnten, um zu fangen WO [PERSON_A] auf die Anzeige kommt.
- Verdächtige Display-Pfade für Marker:
  1. pip-launcher.js: Slot-A/Slot-B-Render bei contact_category_update — wird STALE/alter Slot-Inhalt
     (aus Gatekeeper-Phase, evtl. anonymisiert) beim Re-Render kurz gezeigt statt geleert?
  2. keyword_einwand_match-Emit (Slot A): Inhalt + roh vs. anonymisiert.
  3. Jede Opener-/Vorschlags-(Re)generierung, die der Wechsel zur Zielperson auslöst
     (Briefing-Name = echter CEO-Name aus PreCall).
- André reproduziert den Wechsel EINMAL mit aktivem Logging. ERST nach dem Output: Diagnose + Fix.
- Wahrscheinliche Fix-Klasse: dasselbe Entkopplungs-Muster wie Plan 09 ODER ein Frontend-Slot-Clear beim Wechsel.
- Verify = Production (kein Local-Dev). NICHT neu bauen, KEINEN Execute fortsetzen.

## Current Focus

hypothesis: "STALE-Slot: _updateContactCategory leert die Slot-Bodies NICHT — anonymisierter Inhalt aus der Gatekeeper-Phase bleibt beim Switch sichtbar. Alternativ: koinzidenter Slot-1-Stream (pip_token) ODER Cache-Leak in den Live-Display-Emit (M5)."
test: "5 observe-only Marker platziert (M1-M5). André deployt -> reproduziert Gatekeeper->Target-Wechsel EINMAL -> liefert [ANON-FLASH]-Logs zurueck. M3 zeigt Slot-Zustand beim Switch; M5 (Backend-Print) beweist roh-vs-Cache-Leak."
expecting: "M3 anon=true auf einem Slot = Stale-Slot (Fix: Slot-Clear im Switch). M5 anon=true = Backend-Cache-Leck. M2 anon=true = koinzidente anonymisierte Slot-1-Variante."
next_action: "CHECKPOINT: André committet+deployt Marker auf Production (bash deploy.sh production), reproduziert den Wechsel EINMAL, zieht Logs via inspect.sh logs (Backend M5) + Browser-DevTools-Konsole (Frontend M1-M4), liefert [ANON-FLASH]-Zeilen zurueck. ERST DANN Diagnose + Fix (naechster Pass)."
```
