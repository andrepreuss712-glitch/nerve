# PiP Window Resize (Document Picture-in-Picture)

Blueprint for auto-widening the Document-PiP coaching window into a side-by-side
layout (Coaching rechts, Transkript-Panel links) during a live call. Target:
Phase 08.23.2.D.UX.2, feature PT-01 ("Transkript einblenden" im PiP).

## Requirements

Non-negotiable design decisions (from MANIFEST.md, André-Direktive 2026-06-03):

- **Auto-widening must be triggered by a user gesture (button click).** Chrome
  gates `resizeTo`/`resizeBy` behind transient activation. The "Transkript
  einblenden"-Toggle-Klick *is* that gesture — use it. **No timer-/auto-resize
  without a click** — it does not work.
- **Manual window-dragging is NOT an accepted fallback.** If side-by-side cannot
  be reached programmatically, the PiP transcript part does not get built — STOP
  and report alternatives to André.
- **Target side-by-side width ≈ 960px** (Coaching ~480 + Transkript ~480). Must
  fit inside Chrome's ~80%-work-area clamp on the target machine.
- **Minimum Chrome 121** for Document-PiP resize support.
- **Measure-and-fallback, don't assume a width** (PT-GATE-Auflage, André 2026-06-03):
  achievable width is screen-dependent. On the toggle, request ~960, **measure** the
  width actually reached, then **≥~900px → Side-by-side** (the target state, optimize
  for it), **<~900px → fallback** (overlay/stacked) as a safety net. The target
  audience mostly sits at a 2nd monitor / large screen, so optimize side-by-side;
  fallback covers the bare-small-laptop exception.

## How to Build It

The proven approach is **Approach A — open narrow, widen on toggle-click**:

1. **Open the PiP narrow**, exactly as today's launcher does
   (`static/js/pip-launcher.js` around the `requestWindow` call — the spike
   references `pip-launcher.js:1540`):
   ```js
   const pip = await documentPictureInPicture.requestWindow({
     width: 480,   // Coaching-only, current behavior
     height: 900,
   });
   ```

2. **On the "Transkript einblenden ▶" toggle click**, call `resizeTo` from
   inside the click handler so the gesture's transient activation authorizes it:
   ```js
   transkriptToggleBtn.addEventListener('click', () => {
     // The click itself is the required user gesture — no extra activation needed.
     pip.resizeTo(960, 900);          // widen to side-by-side
     renderTranskriptPanel(pip);      // inject the left-hand panel
   });
   ```
   Use `resizeTo(w, h)` for an absolute target, or `resizeBy(dw, dh)` for a delta.

3. **Build the layout inside the PiP document** as side-by-side: Transkript-Panel
   left (~480px), Coaching right (~480px). Vanilla JS + injected DOM/CSS into the
   PiP window's `document` (no framework — see CONVENTIONS).

4. **Measure the achieved width and branch on it** (this is a hard build rule, not
   just diagnostics). Resize is async and Chrome clamps to ~80% work area, which is
   screen-dependent. After `resizeTo`, re-measure ~350ms later and decide the layout
   from the *actual* width — `≥~900px` → side-by-side, else fallback. Reuse the
   spike harness's measurement pattern (`sources/.../pip-resize-spike.html`):
   ```js
   const requested = 960, MIN_SIDE_BY_SIDE = 900;
   const before = pip.innerWidth;
   pip.resizeTo(requested, 900);
   setTimeout(() => {
     const after = pip.innerWidth;
     if (after >= MIN_SIDE_BY_SIDE) {
       renderSideBySide(pip);     // target state: Transkript links, Coaching rechts
     } else {
       renderFallback(pip);       // overlay / stacked — safety net for small screens
     }
     // log {requested, before, after, layout}
   }, 350);
   ```

5. **PT-GATE already passed** — on André's machine (Chrome 148, ~1707px screen) the
   widest reached width was **915px**, so side-by-side ≥900px is reachable and PT-01
   is cleared to build. The measure-and-fallback branch above is the standing
   requirement, since other users' screens may land below 900.

## What to Avoid

- **Timer/auto-resize without a click** (`setTimeout(() => resizeTo(...))`) —
  blocked by Chrome's gesture requirement. The spike includes this as a negative
  test precisely to prove it fails. Do not rely on it.
- **Setting window position** — Document-PiP exposes size only, never position
  (`resizeTo` works, there is no `moveTo`). Don't design around positioning.
- **Opening directly wide** (`requestWindow({width: 960})`) as the primary path —
  new PiP windows without a cached size can start at ~20% work-area and get
  clamped, and it forces the transcript to always be open. This is Approach B,
  kept only as a fallback/comparison, not the chosen UX.
- **Manual window-dragging as a fallback** — explicitly rejected by André. If
  programmatic widening fails, the feature is not built.
- **Assuming the clamp width** — the real max is display-dependent. At 1920px
  width, 80% ≈ 1536px (plenty); on a small laptop it must be measured.

## Constraints

- **Chrome 121+ Desktop** required for `pipWindow.resizeTo`/`resizeBy`.
- **Resize needs transient activation** (a user gesture, e.g. the toggle click).
- **Max size ≈ 80% of the work area**; Chrome may clamp any requested value below
  it. New windows without a cached size may start ~20%.
- **Size only** — window position cannot be set.
- `file://` counts as a secure context, so the API is available there (relevant
  for spiking, not for the deployed app).
- Side-by-side needs ~900–960px to be usable.

## PT-GATE Result (VALIDATED 2026-06-03)

Run on André's machine, **Chrome 148**:

- API present ✓, resize-per-toggle-click (gesture) works ✓.
- Widest window width reached: **915px** on a ~1707px work area.
- Side-by-side (≥900px) reachable: **JA** → **PT-GATE = JA, PT-01 cleared to build.**
- Timer-resize without click: blocked as expected (gesture requirement confirmed).

Standing build constraint: achievable width is screen-dependent (915 here; more on
large/second monitors; possibly <900 on bare small laptops), so the measure → branch
→ fallback rule above is mandatory, not optional. Optimize side-by-side (target
audience mostly on 2nd monitor / large screen); fallback covers the exception.

## Origin

Synthesized from spikes: 001 (verdict VALIDATED — PT-GATE = JA, Chrome 148, 915px).
Source files available in: `sources/001-pip-window-resize-side-by-side/`
(README.md + pip-resize-spike.html measurement harness).
