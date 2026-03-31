# NERVE Design System

> Diese Datei ist die einzige Quelle der Wahrheit für alle visuellen Entscheidungen.
> Alle Farben, Abstände und Fonts werden ausschließlich als CSS Custom Properties verwendet.
> Keine Hex-Codes direkt in Templates, keine Inline-Styles, keine Werte in JavaScript hardcoden.

---

## Farb-Tokens (CSS Custom Properties)

```css
:root {
  /* Backgrounds */
  --color-bg:           #0C0C0C;
  --color-bg-elevated:  #141414;
  --color-card:         rgba(255, 255, 255, 0.06);
  --color-card-hover:   rgba(255, 255, 255, 0.09);

  /* Gradient (Amber → Gold) — das Markenzeichen */
  --gradient-primary:   linear-gradient(135deg, #E8922A 0%, #C9A84C 100%);
  --gradient-primary-h: linear-gradient(135deg, #F09A30 0%, #D4B458 100%); /* hover */
  --gradient-text:      linear-gradient(135deg, #E8922A, #C9A84C);

  /* Accent Farben einzeln (für Schatten, Borders) */
  --color-amber:        #E8922A;
  --color-gold:         #C9A84C;

  /* Text */
  --color-text-primary:   #F5F5F5;
  --color-text-secondary: #888888;
  --color-text-muted:     #555555;

  /* Borders & Dividers */
  --color-border:       rgba(255, 255, 255, 0.10);
  --color-border-gold:  rgba(201, 168, 76, 0.35);

  /* Status */
  --color-danger:       #EF4444;
  --color-success:      #22C55E;
  --color-live:         #E8922A;

  /* Shadows */
  --shadow-button:      0 4px 16px rgba(232, 146, 42, 0.35);
  --shadow-card:        0 8px 32px rgba(0, 0, 0, 0.6);
  --shadow-panel:       0 16px 48px rgba(0, 0, 0, 0.8);
}
```

---

## Typografie

```css
:root {
  --font-headline: 'Playfair Display', Georgia, serif;
  --font-body:     'DM Sans', system-ui, sans-serif;
  --font-mono:     'DM Mono', 'Courier New', monospace;
}
```

**Verwendung:**
- `--font-headline` → Alle h1, h2, Alert-Titel ("Einwand erkannt"), Dashboard-Begrüßung
- `--font-body` → Alles andere: Labels, Buttons, Body-Text, Navigation
- `--font-mono` → Timer, Prozent-Zahlen, Metriken

**Größen-Hierarchie:**
```
Hero / Panel-Headline:  2rem    (Playfair Display, bold)
Section Headline:       1.25rem (Playfair Display, semibold)
Button / Label:         0.875rem (DM Sans, medium 500)
Body:                   0.875rem (DM Sans, regular 400)
Caption / Muted:        0.75rem  (DM Sans, regular 400)
Timer / Zahlen:         1rem     (DM Mono)
```

---

## Komponenten

### Button — Primary (Gradient)
```css
.btn-primary {
  background:    var(--gradient-primary);
  color:         #0C0C0C;
  font-family:   var(--font-body);
  font-weight:   600;
  font-size:     0.875rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 6px;
  padding:       10px 20px;
  border:        none;
  box-shadow:    var(--shadow-button),
                 inset 0 1px 0 rgba(255,255,255,0.20); /* 3D Bevel oben */
  transition:    all 0.15s ease;
  cursor:        pointer;
}

.btn-primary:hover {
  background:    var(--gradient-primary-h);
  box-shadow:    0 6px 20px rgba(232, 146, 42, 0.50),
                 inset 0 1px 0 rgba(255,255,255,0.25);
  transform:     translateY(-1px); /* leichtes Heben */
}

.btn-primary:active {
  transform:     translateY(0);
  box-shadow:    0 2px 8px rgba(232, 146, 42, 0.30),
                 inset 0 2px 4px rgba(0,0,0,0.20); /* gedrückt */
}
```

### Button — Secondary (Ghost)
```css
.btn-secondary {
  background:    transparent;
  color:         var(--color-gold);
  font-family:   var(--font-body);
  font-weight:   500;
  font-size:     0.875rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 6px;
  padding:       10px 20px;
  border:        1px solid var(--color-border-gold);
  transition:    all 0.15s ease;
  cursor:        pointer;
}

.btn-secondary:hover {
  background:    rgba(201, 168, 76, 0.08);
  border-color:  var(--color-gold);
}
```

### Karte — Glassmorphism
```css
.card {
  background:    var(--color-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border:        1px solid var(--color-border);
  border-radius: 12px;
  box-shadow:    var(--shadow-card);
}

/* Alert-Karte mit Gradient-Rand links */
.card-alert {
  border-left:   3px solid transparent;
  border-image:  var(--gradient-primary) 1;
}
```

### Badge — Live / Status
```css
.badge-live {
  background:    var(--gradient-primary);
  color:         #0C0C0C;
  font-family:   var(--font-body);
  font-weight:   700;
  font-size:     0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border-radius: 4px;
  padding:       2px 8px;
}
```

### Gauge — Kaufbereitschaft (Semicircle Speedometer)
```
Hintergrund-Arc:  rgba(255,255,255,0.08)
Fill-Arc:         Gradient von --color-amber zu --color-gold
Nadel:            --color-gold, 2px breit
Zahl im Zentrum:  Playfair Display, 2rem, --color-text-primary
Label darunter:   DM Sans, 0.7rem, --color-text-secondary, uppercase
```

### Phasen-Tabs
```css
.phase-tab {
  font-family:   var(--font-body);
  font-size:     0.75rem;
  font-weight:   500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color:         var(--color-text-muted);
  padding-bottom: 6px;
  border-bottom: 2px solid transparent;
}

.phase-tab.active {
  color:           var(--color-text-primary);
  border-image:    var(--gradient-primary) 1;
  border-bottom:   2px solid transparent;
}
```

---

## Abstände & Radien

```css
:root {
  --radius-sm:   4px;   /* Badges, kleine Elemente */
  --radius-md:   6px;   /* Buttons */
  --radius-lg:   12px;  /* Karten, Panels */
  --radius-xl:   16px;  /* Große Container */

  --space-xs:    4px;
  --space-sm:    8px;
  --space-md:    16px;
  --space-lg:    24px;
  --space-xl:    32px;
}
```

**Regel:** Maximaler Border-Radius für Buttons = 6px. NERVE ist ein professionelles Werkzeug, keine Consumer-App. Keine Pillen-Buttons.

---

## Live-Assist Panel (380px)

```
Breite:         380px (fest, floating)
Hintergrund:    var(--color-bg)
Border-radius:  var(--radius-xl)
Box-shadow:     var(--shadow-panel)

Innenabstand:   var(--space-md) überall

Aufbau (oben → unten):
1. Header-Bar      — Phasen-Tabs + Timer
2. Alert-Card      — Badge + Headline + Text + Links-Border
3. Action-Buttons  — Primary + Secondary, volle Breite
4. Gauge-Section   — Kaufbereitschaft Speedometer
5. Footer-Bar      — "NERVE KI AKTIV" + Redeanteil
```

---

## Regeln für die Implementierung

1. **Niemals** Hex-Codes direkt in HTML-Templates schreiben
2. **Niemals** `style=""` Attribute für Farben nutzen
3. **Immer** CSS Custom Properties: `var(--color-amber)` statt `#E8922A`
4. Gradient als `var(--gradient-primary)` referenzieren, nicht inline
5. Alle Komponenten-Klassen in einer zentralen `design-tokens.css` definieren
6. Neue Farben erst hier definieren, dann verwenden — nie andersrum

---

*Erstellt: 2026-03-30 | NERVE v0.9.4 → v1.0*
*Basis: Stitch-Sessions + Design-Analyse Pinterest-Referenzen*
*Änderungen hier → wirken sich auf ALLE Screens aus*
