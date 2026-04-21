---
slug: backend-persistence-bundle
status: resolved
trigger: "POLISH-38/39/40/42 Backend-Persistenz-Bundle — /api/beenden-Handler persistiert 4 Runtime-State-Felder nicht: einwaende_gesamt (Counter), phasen_details (JSON), precall_briefing (Text), skript_abdeckung (Percent)"
created: 2026-04-21
updated: 2026-04-21
priority: launch-critical
cluster: "Live-Assistent Pipeline-Fix Session 3 of 4"
related: [POLISH-38, POLISH-39, POLISH-40, POLISH-42, POLISH-29, POLISH-43]
---

## Symptoms (4 related bugs, same root-area)

### POLISH-38 — einwaende_gesamt zählt nur 1 statt alle
- Session #117 Cold Call: 4 ObjectionEvents in Timeline sichtbar, `ConversationLog.einwaende_gesamt` zeigt `1` (nicht `4`).
- Per POLISH-29: User-Definition ist **"EWB-Button gedrückt = behandelt"** — Counter soll also `len(ewb_clicks)` sein (alle EWB-Klicks gezählt, unabhängig von erfolgreicher Behandlung).
- Aktuelle Metrik "Einwände behandelt 0/1" falsch (sollte z.B. 2/4 sein).

### POLISH-39 — phasen_details NULL trotz Klassifikation
- Session #117 lief 77s. Backend-Log: `[phase_classify] 1→2 (Qualifizierung) conf=0.85` — Phasen-Classifier läuft erfolgreich.
- Nach Session-Ende: `ConversationLog.phasen_details` ist `NULL`.
- Phasen-Strip in Session-Detail bleibt leer trotz >60s Dauer.

### POLISH-40 — precall_briefing NULL trotz Runtime-Save
- Log: `[DG] PreCall-Briefing gespeichert (1540 Zeichen)` — Briefing wird generiert und im Runtime-State abgelegt.
- Nach Session-Ende: `ConversationLog.precall_briefing` ist `NULL`.
- PreCall-Briefing-Collapsible im Session-Detail bleibt leer.

### POLISH-42 — skript_abdeckung immer 17% (Hardcoded oder Hook-Lücke)
- Skript-Abdeckung zeigt **konstant 17%** unabhängig vom Gesprächsverlauf.
- Vermutung: Default-Wert oder fehlerhafte Berechnungs-Persistenz.
- Unterschied zu -38/-39/-40: dieser Bug ist evtl. NICHT im Persist-Layer, sondern in der Berechnungs-Logik selbst (17% konstant deutet auf Hardcode oder einen statischen Script-Abdeckungs-Wert hin).

## Current Focus

hypothesis: Alle 4 Bugs haben DIFFERENZIERTE Root-Causes, NICHT systematischer Skip:

1. **POLISH-38** (wrong source): `einwaende_gesamt=len(einwaende_liste)` auf Zeile 404 zählt AI-detected Einwände (aus `conversation_log` type='analyse'), aber User-Decision POLISH-29 sagt "EWB-Button gedrückt = behandelt". Fix: `len(ewb_clicks)` statt `len(einwaende_liste)`.

2. **POLISH-39** (wrong source): `ph_details = list(ls.phasen_log)` liest nur manuelle Phase-Advances via `/api/set_phase`. Der AI-Phasen-Classifier in `claude_service.py:1112-1120` updated nur `ls.state['current_phase']` aber appended NICHT an `phasen_log`. Fix: Classifier soll bei Phase-Wechsel zusätzlich an `phasen_log` appenden.

3. **POLISH-40** (type mismatch + wrong source): Frontend `pip-launcher.js:1805` sendet `precall_briefing: state.precallBriefing` als **Object** `{text, company, ...}`. Backend `app_routes.py:261` prüft `isinstance(precall_briefing, str)` — nicht-String wird silent auf `None` gesetzt. Zusätzlich: `ls.state['precall_briefing']` ist korrekt befüllt aber wird nie gelesen. Fix: Backend soll Object unwrappen (`.text`-Feld) ODER Fallback auf `ls.state.get('precall_briefing')`.

4. **POLISH-42** (wrong source — same pattern as POLISH-39): `covered_phases` Set wird nur via manuellem `/api/set_phase` populiert. Profile hat 6 Phasen (Standard), nur `aktive_phase_idx=0` bleibt drin → `1/6 = 16.67% → round = 17%`. AI-Classifier changed `current_phase` aber added nie den neuen Index an `covered_phases`. Fix: Classifier soll bei Phase-Wechsel zusätzlich an `covered_phases` adden.

test: n/a — direkt Code-Verify via Read/Grep erledigt.

expecting: Vier atomic commits, jeweils ein POLISH-ID. Fixes konzentriert in:
- `routes/app_routes.py::api_beenden` (POLISH-38 + POLISH-40)
- `services/claude_service.py::analyse_loop` (POLISH-39 + POLISH-42)

next_action: Fix anwenden, dann atomic commits.

reasoning_checkpoint: "Alle 4 Bugs sind KEIN systematischer Migration-Skip — es sind 4 INDIVIDUELLE Disconnects zwischen Runtime-Tracking und DB-Persistenz. POLISH-38 ist ein Source-Mismatch (AI-Detection vs. User-Action), POLISH-39 und POLISH-42 sind beide Auswirkung desselben Bugs: der AI-Phasen-Classifier hat keinen Sync-Path zu den beiden downstream-Strukturen (`phasen_log` und `covered_phases`). POLISH-40 ist Frontend/Backend Contract-Mismatch plus Redundanz (State-Dict hat Daten, wird ignoriert)."

## Evidence

- timestamp: 2026-04-21 (investigation)
  finding: "Handler /api/beenden gefunden bei routes/app_routes.py:254-565. Handler schreibt ALREADY alle 4 Felder in DB (einwaende_gesamt=404, skript_abdeckung=418, phasen_details=421, precall_briefing=424) — Hypothese vom ursprünglichen Debug-File (fehlende conv.<field>=<source> Assignments) ist FALSCH."
  eliminates: "Hypothesis: 3 fehlende Assignments vor db.commit()"

- timestamp: 2026-04-21
  finding: "POLISH-38: `einwaende_gesamt=len(einwaende_liste)` liest `log_entries` mit type='analyse' + data.einwand — das sind AI-detected Einwände. `ewb_clicks` (Zeile 435) wird NACH dem Commit für ObjectionEvent-Inserts verwendet. Per POLISH-29 User-Definition soll Counter `len(ewb_clicks)` sein."
  source: "routes/app_routes.py:292-300 (einwaende_liste build), 404 (current einwaende_gesamt), 434-435 (ewb_clicks read)"

- timestamp: 2026-04-21
  finding: "POLISH-39: `ls.phasen_log` wird NUR in `/api/set_phase` (routes/app_routes.py:976-981) appended — manueller Phase-Button-Klick. AI-Classifier in claude_service.py:1112-1120 setzt nur `ls.state['current_phase']`, `current_phase_name`, `phase_changed_at`, `phase_change_count` — schreibt NIE an `phasen_log`."
  source: "claude_service.py:1088-1120 (classifier block), routes/app_routes.py:965-986 (set_phase endpoint)"

- timestamp: 2026-04-21
  finding: "POLISH-40 Contract-Mismatch: `pip-launcher.js:1805` sendet `precall_briefing: state.precallBriefing`. `state.precallBriefing` ist OBJECT mit `.text/.company/...` (gesetzt bei pip-launcher.js:329 aus `data.briefing`). Backend `routes/app_routes.py:260-264`: `if not isinstance(precall_briefing, str): precall_briefing = None` — Object wird silent gedroppt. Gleichzeitig `ls.state['precall_briefing']` IS populated korrekt (services/deepgram_service.py setzt bei start_live_session). Handler liest nie aus State."
  source: "pip-launcher.js:329, pip-launcher.js:1805, routes/app_routes.py:259-264, services/deepgram_service.py:~240 (DG PreCall-Briefing gespeichert log)"

- timestamp: 2026-04-21
  finding: "POLISH-42 Math confirmed: `_PHASE_NAMES` in claude_service.py:466-473 hat 6 Phasen. `covered_phases` ist eine SET (services/live_session.py:181), populiert nur via `/api/set_phase` (app_routes.py:984-985). In `/api/beenden` Zeile 310: `cp_snapshot.add(ls.aktive_phase_idx)` fügt nur die aktuelle Index hinzu (Default: 0). Wenn User NIE Phase manuell advanced und AI nur state updated (nicht covered_phases), bleibt genau 1 Phase abgedeckt: 1/6 = 16.67% → `round()` = 17%. EXAKT das symptomatische 17%."
  math: "round(1/6 * 100) = 17  ✓ match"
  source: "services/live_session.py:180-181, routes/app_routes.py:305-320, services/claude_service.py:466-473"

- timestamp: 2026-04-21
  finding: "Profile phasen (z.B. onboarding.py:22-28) haben 5 Phasen und sind 0-indexed. AI _PHASE_NAMES sind 1-6 indexed. Diese zwei Phase-Systeme sind NICHT aligned — POLISH-42 Fix muss auf einem der beiden Systeme aufsetzen, nicht mischen."
  source: "routes/onboarding.py:22-28, services/claude_service.py:466-473"

## Eliminated

- "Handler schreibt einzelne Felder gar nicht" — FALSE (alle 4 schreiben sie, Zeile 404/418/421/424)
- "DB-Migration fehlt" — FALSE (Schema in database/models.py:244,261,268,281 hat alle Felder korrekt)
- "Runtime-State wird beim Session-End nicht geflusht" — FALSE (Handler liest log_entries, ewb_clicks, ls.state korrekt — liest nur falsche Quellen/falsche Felder)
- "POLISH-42 ist ein Hardcode" — FALSE (ist berechnet, aber auf falschem Datensatz — die Berechnung stimmt, die Source ist leer)

## Root Causes (per bug)

| Bug | Root Cause | Fix Location |
|-----|------------|--------------|
| POLISH-38 | `einwaende_gesamt=len(einwaende_liste)` zählt AI-Detection, soll aber EWB-Clicks zählen | routes/app_routes.py:404 |
| POLISH-39 | AI-Classifier schreibt NICHT an `phasen_log` | services/claude_service.py:1112-1120 |
| POLISH-40 | Frontend sendet Object statt String; Backend Fallback auf state fehlt | routes/app_routes.py:259-264 + pip-launcher.js:1805 ODER nur Backend (Defensive) |
| POLISH-42 | AI-Classifier schreibt NICHT an `covered_phases` | services/claude_service.py:1112-1120 |

## Test Session Available

- Session #117 (Cold Call, 4 EWB-Klicks, PreCall-Briefing generiert, 77s Dauer, Phasen-Classifier aktiv) — Referenz-Case für POLISH-38/39/40
- Session #121 (Cold Call, 4 Einwände, Painpoint, kb_verlauf) — frischer Post-POLISH-48 Test-Case

## Expected Fix Bundle

Ziel: Ein Commit pro Bug (atomic) ODER ein gemeinsamer Commit wenn alle 4 Fixes im selben Handler-Block sitzen. User's Verify-Matrix:
- POLISH-38: `conv.einwaende_gesamt = 4` nach Test-Session mit 4 EWB-Klicks
- POLISH-39: `conv.phasen_details` JSON befüllt nach >60s Call mit Phasen-Logs
- POLISH-40: `conv.precall_briefing` nach User-PreCall-Eingabe in DB
- POLISH-42: `skript_abdeckung` variabel (abhängig von Gesprächsinhalt), nicht konstant 17%

## Related Files (to investigate)

- `routes/app_routes.py` — `/api/beenden`-Handler (oder `api_beenden`)
- `services/live_session.py` — Runtime-State-Dict + Finalize-Hook
- `services/claude_service.py` — Phasen-Classifier (POLISH-39-Quelle)
- `services/precall_briefing.py` oder ähnlich (POLISH-40-Quelle)
- `database/models.py` — ConversationLog Schema (Defaults, Nullable, skript_abdeckung-Type)
- Script-Abdeckungs-Berechnung — grep `skript_abdeckung`, `abdeckung`, `coverage`

## Cluster Plan (Status)

- Session 1 POLISH-48 (Meeting-Transcription) — ✓ RESOLVED, runtime-verified
- Session 2 POLISH-41 (Post-Call Guard) — ✓ FIXED, commit `4509863`
- POLISH-49 (EU-Host DSGVO) — ✓ FIXED inline, commit `57561cd`
- Session 3 (this) POLISH-38/39/40/42 — root cause identified, applying fixes
- Session 4 POLISH-46 (Keyword-Matcher-Flexion) — pending; new evidence from Session #121 already logged


## Resolution

All 4 bugs fixed with atomic commits (separate commit per POLISH-ID):

| Commit | POLISH | File | Change |
|--------|--------|------|--------|
| `cf38589` | POLISH-38 | `routes/app_routes.py` | `einwaende_gesamt = len(ewb_clicks)` (User-action based, per POLISH-29). ewb_clicks read moved up before ConversationLog-Insert. |
| `d52bb72` | POLISH-40 | `routes/app_routes.py` | precall_briefing: accept string, unwrap dict (.text), or fall back to `ls.state['precall_briefing']`. Truncate to 2000 chars at the end. |
| `0bd342e` | POLISH-39 | `services/claude_service.py` | AI phase-classifier appends to `ls.phasen_log` when detecting a phase change. Entry carries `name`, `typ` (template fields), `von_phase`, `nach_phase`, `ts`, `segment_count`, `source='ai_classifier'`, `confidence`. |
| `af8f6c9` | POLISH-42 | `services/claude_service.py` | AI phase-change also adds `(new_phase - 1)` to `ls.covered_phases` (clamped to profile-phase count). skript_abdeckung rises naturally instead of flatlining at 1/6 = 17%. |

**Root Cause Summary (per bug — no systematic skip):**
- POLISH-38: source mismatch (AI-detection vs user-action)
- POLISH-39 + POLISH-42: AI classifier had no sync path to downstream `phasen_log` and `covered_phases` (same missing link, two symptoms)
- POLISH-40: frontend/backend type-contract mismatch (object vs string) + no fallback to the correct runtime-state field

**Verification (post-deploy, Session 122+):**
- POLISH-38: `conv.einwaende_gesamt == len(ewb_clicks)` (4 clicks -> 4)
- POLISH-39: `conv.phasen_details` is a non-empty JSON list with name/typ/nach_phase per AI-detected transition
- POLISH-40: `conv.precall_briefing` contains the text (non-null) when user ran PreCall recherche
- POLISH-42: `conv.skript_abdeckung` varies between sessions (no longer constant 17%)

**Defensive fallbacks added in every fix** — all four changes log-and-continue on error rather than raising into the live analysis loop or the call-end handler.
