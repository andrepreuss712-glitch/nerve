---
phase: quick-260421-kwm
plan: 01
subsystem: "live-session/base-template"
tags: [bug-fix, dsgvo, metrics, polish-45, polish-38.1]
dependency_graph:
  requires: []
  provides:
    - "DSGVO-konformer Headset-Consent-Reset pro Login-Session (templates/base.html public-branch script)"
    - "Korrektes success-Flag auf ObjectionEvent fuer manual_ewb-Klicks (services/deepgram_service.py)"
  affects:
    - "Alle logged-out-Page-Renderings in NERVE (clearing sessionStorage.headsetConfirmed)"
    - "Post-Call-Scoring-Heuristik 'Einwaende behandelt' (POLISH-29-konformer Count)"
tech_stack:
  added: []
  patterns:
    - "Jinja {% if not g.user %}-Block als clean separation von public vs. authenticated Rendering"
    - "spawn-then-record Pattern: _ewb_success-Flag erst nach start_background_task setzen fuer korrekte Semantik"
key_files:
  created: []
  modified:
    - templates/base.html
    - services/deepgram_service.py
decisions:
  - "POLISH-45: Inline-Script nach dem sidebar </nav> Tag (nach {% endif %} der g.user-Sidebar) platziert — fruehzeitig genug, unabhaengig vom {% block content %}-Kontext"
  - "POLISH-45: Existierender onclick-Handler auf Abmelden-Link bleibt unveraendert (belt-and-suspenders)"
  - "POLISH-38.1: record_ewb_click NACH sio.start_background_task platziert — erlaubt Spawn-Error-Detection und korrektes success=False"
  - "POLISH-38.1: success=True ist Normalfall (POLISH-29 User-Definition: EWB-Button gedrueckt = Einwand behandelt)"
metrics:
  duration_minutes: 3
  completed_date: "2026-04-21"
  tasks_completed: 2
  files_modified: 2
  commits: 2
---

# Quick Task 260421-kwm: POLISH-45 + POLISH-38.1 Nachzug Summary

**One-liner:** DSGVO-konformer Headset-Consent-Reset auf allen logged-out-Pages (POLISH-45) + manual_ewb ObjectionEvent-Success-Flag korrigiert (POLISH-38.1) in zwei atomic Commits + Push.

## Objective Recap

Zwei kleine Bug-Fix-Nachzuege aus dem Phase-07.4-Debug-Cluster, die als Follow-up-Tasks herausgeloest wurden:

1. **POLISH-45** (DSGVO-UX): Headset-Confirm-sessionStorage persistierte ueber Logout/Re-Login im gleichen Browser-Tab. Nach Fix wird Consent pro Login-Session neu angefordert.
2. **POLISH-38.1** (Metrik-Praezision): `handle_manual_ewb` in deepgram_service.py hardcodete `success=False` auf alle ObjectionEvents. Nach Fix spiegelt die Persistenz die POLISH-29 User-Definition wider ("EWB-Button gedrueckt = Einwand behandelt").

## Completed Tasks

| Task | Name                                                                 | Commit    | Files                          |
| ---- | -------------------------------------------------------------------- | --------- | ------------------------------ |
| 1    | POLISH-45: Headset-Confirm-State bei jedem logged-out-Render cleanen | `e9acc10` | `templates/base.html`          |
| 2    | POLISH-38.1: manual_ewb success=True bei erfolgreichem Spawn         | `585f567` | `services/deepgram_service.py` |
| 3    | `git push origin main`                                               | —         | — (remote-sync)                |

## Key Changes

### Task 1 — `templates/base.html` (POLISH-45)

**Platzierung:** Nach dem sidebar `</nav>`-Tag (Zeile 139), vor dem `<div class="g-content">`-Hauptlayout.

**Vorher:** Nur der onclick-Handler auf dem Abmelden-Link clearte den headsetConfirmed-Key — deckte ausschliesslich den Click-Path ab, nicht `/logout?auto=1`, Session-Timeout, oder direkte URL-Navigation.

**Nachher:** Neuer `{% if not g.user %}`-Block mit Inline-Script feuert auf ALLEN logged-out-Pages und clearing `sessionStorage.headsetConfirmed` idempotent. Deckt damit alle Logout-Pfade ab.

```html
{% if not g.user %}
<script>
  // POLISH-45: Headset-Confirm-State pro Login-Session neu anfordern (DSGVO).
  // Feuert auf allen logged-out-Pages — deckt ALLE Logout-Pfade ab
  // (manuell, /logout?auto=1, Session-Timeout, direkt-URL-Nav).
  try { sessionStorage.removeItem('headsetConfirmed'); } catch (e) {}
</script>
{% endif %}
```

### Task 2 — `services/deepgram_service.py` (POLISH-38.1)

**Vorher** (Zeile 411-414 alt): Hardcoded `ls.record_ewb_click(typ, success=False)` unmittelbar nach Handler-Entry — alle manuell getriggerten EWB-Klicks wurden als "nicht gemeistert" persistiert.

**Nachher** (Zeile 444-455 neu): `record_ewb_click` NACH `sio.start_background_task(_run)` platziert, mit `_ewb_success`-Flag das `True` im Normalfall und `False` nur bei Spawn-Exception setzt. Semantik: EWB-Klick fuehrt zu Haiku-Gegenargument-Stream → Einwand gilt als behandelt (POLISH-29).

```python
# POLISH-38.1: success=True bei erfolgreichem Spawn (User erhaelt Gegenargument,
# EWB-Klick = Einwand behandelt per POLISH-29). success=False nur bei Spawn-Error.
_ewb_success = True
try:
    sio.start_background_task(_run)
except Exception as _spawn_err:
    _ewb_success = False
    print(f"[PiP] manual_ewb spawn error (sid={_sid}): {_spawn_err}")
try:
    ls.record_ewb_click(typ, success=_ewb_success)
except Exception as e:
    print(f"[PiP] record_ewb_click error (sid={_sid}): {e}")
```

## Verification Results

### Automated (während Execution)

- **Task 1 grep-count:** 2 occurrences von `sessionStorage.removeItem('headsetConfirmed')` in `templates/base.html` (alt: onclick-Handler, neu: `{% if not g.user %}`-Block) — OK
- **Task 1 Jinja parse:** `env.get_template('base.html')` laedt ohne Fehler — OK
- **Task 2 Python AST parse:** `ast.parse('services/deepgram_service.py')` → syntax-OK
- **Task 2 grep-checks:** `record_ewb_click(typ, success=_ewb_success)` vorhanden (Line 453), `_ewb_success = True` vorhanden (Line 446), 0 Matches fuer altes `record_ewb_click(typ, success=False)` — OK
- **Task 2 import smoke:** `import services.deepgram_service as dg` → OK
- **Full-app smoke:** `import app` → OK (DB-Migrations durchlaufen, aktives Profil geladen)
- **Task 3 git-log grep:** beide Commits `POLISH-45` + `POLISH-38.1` sind die 2 juengsten auf main (wc -l = 2) — OK
- **Push remote-sync:** `git push origin main` returned `c566e90..585f567  main -> main` — OK

### Manual-Verify (User-Action, nach Deploy auf getnerve.app)

**POLISH-45:**
1. Einloggen in NERVE
2. Cold-Call starten → Headset-Modal bestaetigen
3. Abmelden → landing (/)
4. Wieder einloggen (gleicher Tab!)
5. Cold-Call starten → **Headset-Modal MUSS wieder erscheinen**

**POLISH-38.1:**
1. Live-Session mit PiP starten
2. manual_ewb-Button klicken (Einwand-Typ z.B. "Preis")
3. Gegenargument im PiP sichtbar
4. Session beenden
5. `sqlite3 database/salesnerve.db "SELECT einwand_typ, success, created_at FROM objection_events ORDER BY id DESC LIMIT 3;"`
6. Neuer Row MUSS `success=1` (True) haben

_Manual-Verify noch nicht durchgefuehrt — wird durch User nach Deploy erledigt._

## Deviations from Plan

**Keine.** Plan wurde exakt wie geschrieben ausgefuehrt:
- Task 1: Code-Snippet und Platzierung 1:1 aus Plan uebernommen
- Task 2: Handler-Refactoring exakt gemaess Schritt-fuer-Schritt-Anweisung (hardcoded `success=False`-Block entfernt, record-then-spawn zu spawn-then-record umgestellt)
- Task 3: `git push origin main` ohne Konflikt/Rebase

Keine Rule-1/2/3-Auto-Fixes noetig. Kein Checkpoint getriggert.

## Known Stubs

**Keine.** Beide Fixes sind vollstaendige Implementierungen ohne Platzhalter, TODOs oder mock-Daten.

## Threat Flags

**Keine.** Keine neue Security-Surface eingefuehrt:
- POLISH-45 aendert nur Client-Side sessionStorage (nicht Server-Side Session/Cookie)
- POLISH-38.1 aendert nur das `success`-Feld auf bestehendem ObjectionEvent-Model (keine neue Trust-Boundary)

## Decision im Scope fuer User

**Backlog-Hygiene** — nach erfolgreichem Manual-Verify auf getnerve.app:
- POLISH-45 in `.planning/backlog.md` von "## Open" entfernen und in neue "## Done"-Section (oder direkt streichen, da backlog.md typischerweise nur offene Items trackt).
- POLISH-38.1 analog.

Fuer jetzt bleiben beide Items in `.planning/backlog.md` unter "## Open" — erst nach User-Manual-Verify wird backlog bereinigt (separater Commit). Nicht in diesem Summary-Commit enthalten.

## Git State

```
585f567 fix(POLISH-38.1): set success flag on manual_ewb objection events
e9acc10 fix(POLISH-45): clear headset confirm state on logout
c566e90 docs(backlog): add POLISH-45 + POLISH-38.1 + POLISH-53 as phase-07.4 followups and 07.5 candidate
```

**Branch:** main, up-to-date with origin/main
**Remote sync:** ✓ (push erfolgreich)

## Self-Check: PASSED

- `templates/base.html` modified — FOUND (git diff shows 8 lines added)
- `services/deepgram_service.py` modified — FOUND (git diff shows 12+/5- lines)
- Commit `e9acc10` — FOUND in `git log --oneline`
- Commit `585f567` — FOUND in `git log --oneline`
- SUMMARY.md created at expected path — FOUND (dieses File)
- git push origin main — FOUND (remote-sync confirmed)
- Flask app import — PASSED (`import app` loads successfully)
- Jinja template parse — PASSED (base.html loads without error)
