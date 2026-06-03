# Spike Manifest

## Idea

PiP-Transkript-Panel für Phase 08.23.2.D.UX.2: Während eines Live-Calls soll der Cold-Caller
das Transkript direkt im Document-Picture-in-Picture-Fenster sehen — **side-by-side**: Coaching
rechts, Transkript-Panel links, im **automatisch verbreiterten** PiP-Fenster. Vor jedem Bau steht
ein harter Pflicht-Spike (PT-GATE): Lässt sich das Document-PiP-Fenster überhaupt per JS
automatisch verbreitern (Chrome), oder nicht? Das Ergebnis entscheidet, ob der PiP-Teil dieser
Phase gebaut wird. Reiter-System, Dashboard-Reiter und Text-Tools sind vom Spike-Ergebnis
unabhängig und können getrennt geplant werden.

## Requirements

Design-Entscheidungen, die für den echten Bau verbindlich sind (entstehen beim Spiken):

- **Auto-Verbreitern muss per Button-Klick (Nutzer-Geste) erfolgen** — `resizeTo`/`resizeBy` brauchen
  laut Chrome transient activation. Der „Transkript einblenden"-Toggle-Klick liefert sie. Kein
  Timer-/Auto-Resize ohne Klick (geht nicht).
- **Manuelles Fenster-Ziehen ist KEIN akzeptierter Fallback** (André-Direktive 2026-06-03).
- **Zielbreite side-by-side ≈ 960px** (Coaching ~480 + Transkript ~480). Muss innerhalb Chromes
  ~80%-Arbeitsflächen-Klemme passen — auf der Zielmaschine zu verifizieren.
- **Mindest-Chrome-Version 121** für Resize-Support.
- **Measure-and-fallback statt Annahme (PT-GATE-Auflage, André 2026-06-03):** erreichbare Breite
  ist bildschirm-abhängig (auf André ~1707px-Schirm: 915px). Bau muss die tatsächlich erreichte
  Breite MESSEN: ≥~900px → Side-by-side (Zielzustand, zu optimieren); <~900px → Fallback
  (Overlay/gestapelt) als Netz. Zielgruppe sitzt meist mit 2. Monitor/großem Schirm.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | pip-window-resize-side-by-side | standard | PiP per Toggle-Klick auf side-by-side-Breite auto-verbreitern (ohne manuelles Ziehen) | VALIDATED | pip, document-picture-in-picture, resize, ux, chrome, pt-gate |
