---
status: resolved
trigger: "Live-UAT Phase 08.23.2.D.UX.4 (Production): nach Outcome-Bestätigung bleibt PiP leer — Score erscheint nicht. NEW-1-Blocker-Symptom."
created: 2026-05-31
updated: 2026-05-31
phase: 08.23.2.D.UX.4
mode: logging-first (CLAUDE.md Punkt 15) — kein Blind-Fix, Andre reproduziert live
---

## Symptoms

- **Expected:** Nach Bestätigen SOFORT Score + KB/Redeanteil/Einwände im PiP sichtbar.
- **Actual:** PiP leer nach Bestätigen — kein Score, keine Stats. Sieht aus wie leerer/Setup-Zustand (Anrede/Sekretär-Kopf sichtbar, Rest leer).
- **Repro (Prod, Test-User, echter Mini-Cold-Call):** Call start → Sätze sprechen → Beenden halten → Mic stop + Ladebalken 1 → Outcome-Screen erscheint → Outcome bestätigt → PiP leer.
- **Timeline:** Erste Live-UAT nach manual-direct-prod-Deploy 2026-05-31 (Plan 01+02+03).

## Current Focus

hypothesis: endCall startet (Hold-to-end feuert, neue JS geladen), laeuft _stopTimer/_stopMic/_resetLiveState, aber der neue Outcome/Score-Flow (_showLadebalken1 3018 → /api/beenden → postcall_outcome → _renderOutcomeUx) wird NICHT erreicht. WO genau bricht es ab? Kandidaten: (a) endCall wirft NACH _resetLiveState (catch im Hold-Handler 1982 wuerde "[DBG-UX4] endCall THREW" loggen); (b) /api/beenden antwortet nicht ok / stale-guard greift; (c) postcall_outcome liefert kein call_id → _renderOutcomeUx nie aufgerufen; (d) _showLadebalken1 lief still (kein eigenes Log) und Flow lief weiter — dann muss der beenden-resp-Log erscheinen. RUND-2-Trace klaert das.
test: 9 Flow-Trace-Logs ([DBG-UX4]) ueber den ganzen endCall-Pfad: hold-fired (1981), endCall ENTER (3010), post-reset/LB1 (3018), beenden resp (3032), 9s-timeout (3081), postcall_outcome resp (3113), _renderOutcomeUx ENTER (3837), endCall THREW (catch 1982).
expecting: Die LETZTE [DBG-UX4]-Zeile zeigt, wo der Flow stoppt. Kein "endCall ENTER" → Hold ruft anderen Pfad. ENTER aber kein "beenden resp" → Exception oder Fetch-Fehler dazwischen. "beenden resp stale=true" → Generation-Guard/Race. resp ok aber kein "_renderOutcomeUx ENTER" → postcall_outcome ohne call_id / Fehler.
next_action: Round-2-Log-Build deployed (commit 2d99915). Andre: Hard-Refresh + DevTools-Console, Cold-Call beenden, ALLE [DBG-UX4]-Zeilen + etwaige rote Errors liefern. DANN diagnose.
reasoning_checkpoint: Auch [QA] qa_soft_hint NACH Reset beobachten (Andre-Hinweis Event-Reihenfolge) — Live-Coaching-Event feuert post-reset, evtl. relevant.

## Eliminated

- hypothesis: Score-Karten-Skelett fehlt beim Confirm-Reveal (pipEl-Section leer). WIDERLEGT durch Round-1-UAT: KEINE einzige [DBG-UX4]-Confirm-Zeile erschien → der Confirm-Pfad wird gar nicht erreicht. Der Bug sitzt UPSTREAM in endCall (neuer Flow wird uebersprungen), nicht im Reveal. (2026-05-31)

## Evidence

- timestamp: 2026-05-31 — Code-Read pip-launcher.js: confirm-handler reveal nutzt pipEl('nlp-section-postcall') (4020) + pipEl('nlp-postcall-score') (4025). _showPostcall (3182) wird laut Plan 03 NICHT mehr im Beenden-Pfad aufgerufen (pendingPostcall-Stash bei 3044 stattdessen). Score-Karten-Skelett-Bau dadurch evtl. nie ausgeführt. Hypothese, nicht bestätigt.

## Eliminated

(noch keine)

## Resolution

root_cause: `_showLadebalken1` (pip-launcher.js:2980-2981 alt) setzte `#nlp-section-postcall` auf `display:none`. Diese Section IST aber der sichtbare Container, in den sowohl Ladebalken 1 (host 2992) als auch der Outcome-Screen (`_renderOutcomeUx`-host 3851, da `#pip-postcall` nicht existiert → Fallback auf `#nlp-section-postcall`) gerendert werden. Nichts machte die Section vor dem Confirm-Handler (4032) wieder sichtbar → Ladebalken + Outcome-Screen unsichtbar → User kann „Bestätigen" nie klicken → Confirm feuert nie → leeres PiP. Plan-03-F9 („Score bis Confirm verstecken") versteckte faelschlich den GANZEN Container statt nur die Score-Zahl. NICHT Hypothese (a): `_renderOutcomeUx` nutzt bereits korrekt `pipEl`/`_doc`; Section liegt im PiP-Doc (in `#pip-live-window`, base.html 472→598), kein Wrong-Document-Bug.
fix: `_showLadebalken1` schaltet `#nlp-section-postcall` jetzt `display:flex` (sichtbar) und versteckt nur die Score-Karten-Kinder (Zahl `#nlp-postcall-score`, `.pip-postcall-label`, `.pip-postcall-actions`) bis Confirm. Leere Kinder (trend/sparkline/quickstats/tags) blendet CSS `:empty` aus. Confirm-Handler blendet die Kinder wieder ein + schreibt `final_score`. Minimal, kein Refactor.
verification: Andre Live-Re-Test PASS 2026-05-31 — Ladebalken 1 sichtbar, Outcome-Screen sichtbar (Unsicher-Pfad: rot + Disclaimer + Confirm-nach-Tap OK), nach Bestätigen erscheinen Score + Kaufbereitschaft/Dauer/Einwände/Redeanteil/Skript-Abdeckung im PiP. Blocker tot.
files_changed: static/pip-launcher.js (fix commit 82b25ec; [DBG-UX4]-Logs gestrippt in a718a4e)

