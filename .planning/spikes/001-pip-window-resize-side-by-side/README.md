---
spike: 001
name: pip-window-resize-side-by-side
type: standard
validates: "Given ein offenes Document-PiP-Fenster in Chrome, when ein Button-Klick im PiP resizeTo() auslöst, then verbreitert sich das Fenster automatisch auf side-by-side-Breite (Coaching rechts, Transkript links) ohne manuelles Ziehen"
verdict: PENDING
related: []
tags: [pip, document-picture-in-picture, browser-api, resize, ux, chrome, pt-gate]
---

# Spike 001: PiP-Fenster automatisch verbreitern (PT-GATE)

## What This Validates

**Given** ein offenes Document-PiP-Fenster (`documentPictureInPicture.requestWindow`) in Chrome,
**when** der Nutzer im PiP auf „Transkript einblenden" klickt und das einen `resizeTo()`-Aufruf auslöst,
**then** verbreitert sich das Fenster automatisch auf side-by-side-Breite (Coaching rechts, Transkript-Panel links) — **ohne dass der Nutzer das Fenster manuell ziehen muss**.

Das ist das **harte Gate (PT-GATE)** der Phase 08.23.2.D.UX.2. André-Direktive 2026-06-03:
- **JA →** PiP-Transkript-Panel (PT-01) bauen.
- **NEIN →** STOPP, kein Bau. Alternativen an André melden.
- **Manuelles Fenster-Ziehen ist KEIN akzeptierter Fallback.**

## Research

Geprüft am 2026-06-03 (Chrome for Developers Doku, MDN, Chrome Platform Status, w3c-Issues).

### Befunde

| Frage | Antwort | Quelle |
|-------|---------|--------|
| Kann das PiP-Fenster nach dem Öffnen per JS verkleinert/vergrößert werden? | **Ja**, via `pipWindow.resizeTo(w,h)` / `resizeBy(dw,dh)` | Chrome for Developers, MDN |
| Ab welcher Chrome-Version? | **Chrome 121** | Chrome for Developers |
| Braucht der Resize eine Nutzer-Geste? | **Ja** — `resizeTo`/`resizeBy` brauchen transient activation (Klick) | Chrome for Developers, chromestatus „require user gesture for resize" |
| Gibt es eine Max-Größe? | **Ja, ~80% der Arbeitsfläche** (work area). Neue Fenster ohne gecachte Größe starten ~20%. Chrome darf angeforderte Werte klemmen. | Google-Chrome-Community-Thread, w3c/picture-in-picture#163 |
| Funktioniert die API von `file://`? | **Ja** — `file://` gilt als „Potentially Trustworthy" / secure context. | W3C Secure Contexts, MDN |
| Kann die Fenster-Position gesetzt werden? | **Nein** — nur Größe, nie Position. (Für uns irrelevant.) | WICG-Spec |

### Approach-Vergleich

| Ansatz | Mechanik | Pro | Contra | Status |
|--------|----------|-----|--------|--------|
| **A — Schmal öffnen, auf Toggle-Klick verbreitern** | `requestWindow({width:480})` → später `resizeTo(960)` im Klick-Handler | Exakt die gewünschte UX (Transkript bei Bedarf), Klick liefert die Pflicht-Geste | Resize ist async, Chrome kann klemmen | **gewählt** (Test 2) |
| B — Direkt breit öffnen | `requestWindow({width:960})` | Kein Nach-Resize nötig | Chrome startet neue Fenster evtl. bei ~20% Arbeitsfläche → könnte geklemmt werden; Transkript wäre immer offen | Fallback / Vergleich (Test 3) |
| C — Auto-Resize per Timer ohne Klick | `setTimeout(()=>resizeTo(960))` | „Automatisch" ohne Nutzer-Aktion | **Geht laut Doku nicht** (Gesture-Pflicht) → Negativ-Test | verworfen (Test 4 beweist) |

**Chosen approach:** A — schmal öffnen (wie heute `pip-launcher.js:1540`), bei „Transkript einblenden"-Klick `resizeTo(960,900)`. Der Toggle-Klick **ist** die geforderte Nutzer-Geste, daher kein Widerspruch zur Gesture-Pflicht und **kein** manuelles Ziehen nötig.

### Zentrale Rest-Unsicherheit (nur empirisch klärbar — darum dieser Spike)

Die Doku sagt „Chrome darf klemmen" und „Max ~80% Arbeitsfläche", aber **wie breit es auf Andrés echtem Bildschirm wirklich wird, ist display-abhängig**. Side-by-side braucht ~900–960px. Bei 1920px-Breite sind 80% ≈ 1536px → reicht locker. Bei kleinem Laptop muss es gemessen werden. → Spike misst die echte Klemm-Grenze auf der Zielmaschine.

## How to Run

**Kein Server, kein Build, kein Local-Dev-App-Start** (respektiert die HART-Regel — dies ist eine throwaway-HTML-Datei, nicht die NERVE-App).

1. In **Google Chrome ≥ 121** (Desktop) öffnen:
   - Datei doppelklicken **oder** in die Adresszeile ziehen:
     `file:///C:/Users/andre/dev/salesnerve/.planning/spikes/001-pip-window-resize-side-by-side/pip-resize-spike.html`
2. Oben links die **Umgebung** prüfen (Chrome-Version ≥121, API „vorhanden ✓").
3. Tests rechts **von oben nach unten** durchklicken (1 → 5).
4. Bei **Test 2**: im PiP-Fenster auf **„Transkript einblenden ▶"** klicken — beobachten, ob das Fenster automatisch breiter wird und das Transkript links erscheint.
5. Bei **Test 5**: im PiP die Breiten-Knöpfe (700/960/1200/Max) klicken — unten im PiP wird die *tatsächliche* Breite angezeigt.
6. **„⬇ Log als JSON exportieren"** klicken und die Datei hier zurückmelden (oder die Verdict-Pills oben links beschreiben).

## What to Expect

- **Umgebung:** Chrome ≥121, `documentPictureInPicture vorhanden ✓`, Prognose Max-Breite ≈ 80% deiner Arbeitsfläche.
- **Test 1:** schmales PiP (480px), nur Coaching sichtbar — wie heute.
- **Test 2 (Kern):** Klick auf „Transkript einblenden" → Fenster **wächst automatisch** auf ~960px, Transkript-Panel erscheint links neben dem Coaching. **Das ist der JA-Beweis.**
- **Test 3:** PiP öffnet direkt breit *oder* Chrome klemmt auf ~20% — Log zeigt `clamped: true/false`.
- **Test 4:** Timer-Resize ohne Klick → **blockiert** (Verdict-Pill „wie erwartet blockiert ✓"). Beweist, dass die Geste nötig ist, der Toggle-Klick sie aber liefert.
- **Test 5:** zeigt die echte Obergrenze (Max-Knopf 9999 → klemmt auf ~80% Arbeitsfläche).

**Verdict-Logik (oben links live):**
- `Resize per Button-Klick = JA ✓` **und** `Side-by-side (≥900px) erreichbar = JA ✓` → **PT-GATE = JA**, PiP-Teil baubar.
- `API fehlt` **oder** `Resize blockiert` **oder** Side-by-side klemmt zu schmal → **PT-GATE = NEIN**, STOPP + Alternativen.

## Observability

Forensik-Log-Schicht eingebaut:
1. **Event-Log** mit ms-Timestamps (relativ zum Start), Kategorie-Tags (`INFO`/`OK`/`WARN`/`BAD`/`MEAS`).
2. **Mess-Layer:** jeder `resizeTo` loggt `requested` vs. `before`/`after` (inner & outer width), `grew`-Flag, async-Remeasure nach 350ms.
3. **Export:** „Log als JSON exportieren" → `spike-001-pip-resize-log.json` mit `env`, `summary`, `events`.
4. **Live-Verdict-Pills** oben links + `summary.verdict_hint` im Export.
5. **Im PiP unten:** Live-Anzeige `angefordert:` vs. `tatsächlich:` Breite.

## Investigation Trail

- **2026-06-03 — Research:** Doku bestätigt Resize ab Chrome 121 mit Gesture-Pflicht und ~80%-Work-Area-Klemme; `file://` ist secure context. Kern-Unsicherheit ist die display-abhängige Klemm-Grenze → Harness gebaut, der genau das misst, plus den Gesture-Mechanismus (Toggle-Klick) und einen Negativ-Test (Timer ohne Klick).
- **PENDING — André-Run:** Harness muss auf Andrés echtem Chrome/Bildschirm laufen. Verdict erst danach.

## Results

**Verdict: PENDING** — wartet auf André-Run in Chrome.

_(Wird nach dem Run gefüllt: erreichte Max-Breite, ob side-by-side ≥900px klappt, ob der Toggle-Klick den Resize autorisiert, ob der Timer-Test wie erwartet blockiert. Daraus folgt JA → PT-01 bauen, oder NEIN → Alternativen an André.)_
