---
type: quick
slug: hide-live-controls-postcall
status: complete
created: 2026-06-05
completed: 2026-06-05
files_modified:
  - static/pip-launcher.js
cross_ai: skipped
---

# Summary: Live-Only-Precall-Controls im Post-Call ausblenden

## Was gemacht wurde

| Hook | Änderung |
|---|---|
| `_showLadebalken1()` (Call-Ende) | `pip-anrede-row`, `pip-vorwissen-indicator`, `pip-vorwissen-edit`, `pip-mode-indicator` zur bestehenden Hide-`forEach`-Liste hinzugefügt → ab "Call beenden" weg (nicht erst ab Scoreboard), nicht klickbar. |
| `_showPipLive()` (Call-Start) | Neben dem `#pip-header`-Restore die 4 wieder eingeblendet mit Markup-Default-Display (anrede-row=flex, vorwissen-indicator=flex, vorwissen-edit=none, mode-indicator=''). |

## Root-Cause

Die 3 Controls sind in `templates/base.html` **Geschwister** von `#pip-header` (nicht Kinder).
`_showLadebalken1` versteckte `#pip-header` + Live-Liste, aber nicht diese Geschwister.

## Verifikation

- `node --check static/pip-launcher.js` → **OK**
- Control-Flow goal-backward: `_showLadebalken1` hide ✓ · `_showPipLive` re-show mit korrekten
  Display-Werten ✓ · `_resetLiveState` bewusst NICHT genutzt (läuft auch bei Call-Start) ✓
- **Ausstehend (Andre):** Deploy + Cold/Meeting-Call → beenden → 3 weg → 2. Call → 3 wieder da + funktional.

## Plus-Check: weitere Live-only-Controls im Post-Call

- **`#pip-briefing-tab`** (Briefing-Klapp-Tab, Geschwister von `#pip-header`): wurde bei
  vorhandenem Briefing während des Calls via `display='block'` eingeblendet (~Z.2067), aber in
  `_showLadebalken1` nicht versteckt → blieb post-call sichtbar. **✅ NACHGEZOGEN (André-OK
  2026-06-05):** zur Hide-Liste in `_showLadebalken1` hinzugefügt + Reset auf `'none'` in
  `_showPipLive`. Punkt-14-Edge: der Briefing-Block direkt nach `_showPipLive` (Caller-~Z.2062)
  blendet den Tab beim 2. Call MIT Briefing wieder als `'block'` ein (OHNE Briefing bleibt er aus).
- `#pip-anrede-toast`: nur transienter Toast (default display:none, auto-dismiss) — unkritisch, nicht angefasst.
- Mic-Level / `pip-header-mic-area`: liegt INNERHALB `#pip-header` → wird mit Header versteckt, OK.

## Deviations

None — exakt nach Plan; Root-Cause vorab verifiziert.
