---
name: spike-findings-salesnerve
description: Implementation blueprint from spike experiments. Requirements, proven patterns, and verified knowledge for building salesnerve (NERVE). Auto-loaded during implementation work.
---

<context>
## Project: salesnerve (NERVE)

NERVE ist ein KI-gestützter Echtzeit-Vertriebsassistent (SaaS) für B2B-Vertriebler
im DACH-Markt. Spikes here de-risk hard, empirically-uncertain build questions
before they enter a real phase. The first spike targets Phase 08.23.2.D.UX.2: the
PiP-Transkript-Panel — widening the Document-Picture-in-Picture coaching window into
a side-by-side layout (Coaching rechts, Transkript-Panel links) during a live call.

Spike sessions wrapped: 2026-06-03
</context>

<requirements>
## Requirements

Non-negotiable design decisions that emerged during spiking. Every feature-area
reference must honor these.

- **Auto-widening must be triggered by a user gesture (button click)** — Chrome
  gates `resizeTo`/`resizeBy` behind transient activation; the "Transkript
  einblenden"-Toggle-Klick supplies it. No timer-/auto-resize without a click.
- **Manual window-dragging is NOT an accepted fallback** (André-Direktive
  2026-06-03). If side-by-side can't be reached programmatically, the PiP part is
  not built — STOP and report alternatives.
- **Target side-by-side width ≈ 960px** (Coaching ~480 + Transkript ~480), must fit
  inside Chrome's ~80%-work-area clamp on the target machine.
- **Minimum Chrome 121** for Document-PiP resize support.
- **Measure-and-fallback, don't assume a width** (PT-GATE-Auflage, André 2026-06-03)
  — achievable width is screen-dependent (915px on André's ~1707px screen). On the
  toggle: request ~960, **measure** the width actually reached, then ≥~900px →
  Side-by-side (optimize for this), <~900px → fallback (overlay/stacked) as a net.
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| PiP Window Resize (Document Picture-in-Picture) | references/pip-window-resize.md | VALIDATED (PT-GATE=JA, Chrome 148, 915px reached). Open narrow, `resizeTo(960,900)` from the toggle-click handler (gesture-gated); measure achieved width → ≥900 side-by-side, else fallback |

## Source Files

Original spike source files are preserved in `sources/` for complete reference —
including `pip-resize-spike.html`, a self-contained measurement harness that logs
`requested` vs. actual width and proves the gesture requirement.
</findings_index>

<metadata>
## Processed Spikes

- 001-pip-window-resize-side-by-side
</metadata>
