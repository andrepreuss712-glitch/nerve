# Spike Wrap-Up Summary

**Date:** 2026-06-03
**Spikes processed:** 1
**Feature areas:** PiP Window Resize (Document Picture-in-Picture)
**Skill output:** `./.claude/skills/spike-findings-salesnerve/`

## Processed Spikes

| # | Name | Type | Verdict | Feature Area |
|---|------|------|---------|--------------|
| 001 | pip-window-resize-side-by-side | standard | PENDING (research conclusive, empirical run open) | PiP Window Resize |

## Key Findings

- **Document-PiP windows can be resized via JS** (`pipWindow.resizeTo`/`resizeBy`)
  from **Chrome 121+** — confirmed by docs (Chrome for Developers, MDN).
- **Resize is gesture-gated**: it needs transient activation. The "Transkript
  einblenden"-Toggle-Klick supplies it, so the chosen UX (open narrow → widen on
  click) is compatible — **no manual window-dragging needed**, which André rejected
  as a fallback.
- **Chosen approach: A — open narrow (~480px), widen to ~960px on the toggle
  click.** Build side-by-side layout (Transkript links, Coaching rechts) inside the
  PiP document.
- **Max size ≈ 80% of work area**; Chrome may clamp. Window **position** cannot be
  set (size only).
- **Open PT-GATE:** the real clamp width on André's screen is display-dependent and
  **not yet measured**. `pip-resize-spike.html` is a ready measurement harness for
  the target machine. JA (side-by-side ≥900px reachable via click) → build PT-01;
  NEIN → STOP + alternatives to André.
- **Spike method established:** self-contained throwaway `.html` opened via
  `file://` in Chrome, Vanilla JS, no server/build, forensic JSON log + live
  verdict pills, `requested` vs. `actual` measurement with async re-measure (see
  CONVENTIONS.md).
