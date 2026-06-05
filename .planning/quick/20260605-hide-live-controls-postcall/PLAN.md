---
type: quick
slug: hide-live-controls-postcall
created: 2026-06-05
files_modified:
  - static/pip-launcher.js
cross_ai: skipped   # Cleanup/Bugfix mit klarer Root-Cause (CLAUDE.md Punkt 7)
---

# Quick: Live-Only-Precall-Controls im Post-Call ausblenden

## Objective

3 Live-Anruf-Bedienelemente im PiP-Kopf bleiben nach Call-Ende sichtbar UND klickbar
(bis ins Scoreboard) — gehören in den Post-Call-Zustand versteckt:
1. Anrede-Toggle (Du/Sie) — `#pip-anrede-row` (enthält pip-anrede-du/sie/badge)
2. Vorwissen-Indikator + Edit-Panel — `#pip-vorwissen-indicator` / `#pip-vorwissen-edit`
3. Sekretär/Entscheider-Modus-Toggle — `#pip-mode-indicator`

## Root-Cause (verifiziert)

Die 3 Controls sind in `templates/base.html` **Geschwister** von `#pip-header` (schließt
~Z.492), NICHT dessen Kinder. Die Post-Call-Transition `_showLadebalken1()` versteckt
`#pip-header` + `['nlp-btn-beenden','nlp-ewb-row','pip-section-live']`, aber NICHT diese 3
Geschwister → sie bleiben sichtbar+klickbar.

## Fix

- **Hide:** in `_showLadebalken1()` (Call-Ende-Transition) die 3 IDs + `pip-vorwissen-edit`
  zur bestehenden Hide-`forEach`-Liste hinzufügen.
- **Re-Show (CLAUDE.md Punkt 14):** in `_showPipLive()` (kanonischer Call-Start-Reveal,
  „regardless of how we arrived — nextCall, consent-accept path") neben dem `#pip-header`-
  Restore wieder einblenden, mit Markup-Default-Display: anrede-row=flex, vorwissen-indicator=
  flex, vorwissen-edit=none (collapsed), mode-indicator='' (CSS-getrieben).

**Warum nicht `_resetLiveState`?** Wird sowohl bei Call-Start (via `_showPipLive`, Z.2163)
als auch Call-Ende (`endCall`, Z.3034) aufgerufen → Hide dort würde auch beim Start verstecken.

## Verify (Production-only, CLAUDE.md HART)

- `node --check static/pip-launcher.js` OK
- Deploy `bash deploy.sh production` (JS-only, statisch via nginx)
- Andre: Cold-Call ODER Meeting → beenden → die 3 weg (auch im Scoreboard)? → 2. Call starten
  → die 3 wieder da + funktional (Anrede umschalten, Vorwissen öffnen, Modus toggeln)?
