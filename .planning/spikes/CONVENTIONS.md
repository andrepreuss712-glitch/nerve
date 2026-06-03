# Spike Conventions

Patterns and stack choices established across spike sessions. New spikes follow these unless the
question requires otherwise.

## Stack

- **Frontend-Spikes:** Eine einzige selbst-enthaltene `.html`-Datei, Vanilla JS, kein Build, kein
  npm/pip, kein Server. Passt zum NERVE-Constraint (Flask + Vanilla JS, kein React).
- **Ausführung:** Direkt via `file://` in Chrome öffnen (`file://` ist secure context — reicht für
  Browser-APIs wie Document-PiP). **Kein lokaler App-Start** — respektiert die HART-Regel „Kein
  Local-Dev" (Spike-HTML ist throwaway, nicht die NERVE-App).

## Structure

- Ein Verzeichnis pro Spike: `.planning/spikes/NNN-kebab-name/`.
- `README.md` (Frontmatter + Research + How-to-Run + Observability + Investigation Trail + Results)
  + die Experiment-Datei(en) daneben.

## Patterns

- **Forensik-Log-Schicht** in jedem interaktiven Spike: Event-Array mit ms-Timestamps, Kategorie-Tags
  (`INFO`/`OK`/`WARN`/`BAD`/`MEAS`), Live-Render auf der Seite, „Export als JSON"-Knopf inkl. `env`
  + `summary` + `events`.
- **Live-Verdict-Pills** auf der Seite, die sich aus den Tests füllen — André sieht das Ergebnis,
  ohne den Log zu lesen.
- **Erlebbar statt nur Stdout:** Spike rendert das echte Ziel-Layout (hier: side-by-side Coaching/
  Transkript im PiP), damit André es *fühlt*, nicht nur abgelesen bekommt.
- **Mess statt Vermutung:** bei display-/browser-abhängigen Fragen `requested` vs. `actual` loggen,
  inkl. async-Remeasure (Resize ist nicht synchron).
- **Brand:** kein Gelb (CLAUDE.md Punkt 8) — Highlights in Brand-Blau/Grün.

## Tools & Libraries

- Keine externen Libraries in Spikes — reines Browser-API + Vanilla JS.
- Ziel-Browser für PiP-Spikes: **Google Chrome Desktop ≥ 121** (Document-PiP-Resize-Support).
