# NERVE Design System

> Diese Datei ist die einzige Quelle der Wahrheit für alle visuellen Entscheidungen.
> Alle Farben, Abstände und Fonts werden ausschließlich als CSS Custom Properties verwendet.
> Keine Hex-Codes direkt in Templates, keine Inline-Styles, keine Werte in JavaScript hardcoden.
> Claude Code / GSD liest diese Datei vor jeder UI-Arbeit.

---

## Farb-Tokens (CSS Custom Properties)

```css
:root {
  /* Seitenhintergrund */
  --page-bg:              #F0F2F5;
  --page-text-color:      #1a1a1a;
  --page-text-secondary:  #6B7280;
  --page-text-muted:      #9CA3AF;

  /* Glass Panels (.n-glass) */
  --glass-bg:             #FFFFFF;
  --glass-border:         #E2E8F0;
  --glass-border-hover:   #CBD5E1;
  --glass-radius:         20px;
  --glass-shadow:         0 1px 3px rgba(0,0,0,0.08);
  --glass-shadow-hover:   0 4px 12px rgba(0,0,0,0.12);

  /* Primärfarbe: Teal */
  --color-teal:           #00D4AA;
  --color-teal-dark:      #00B894;
  --color-teal-glow:      0 0 20px rgba(0,212,170,0.15);

  /* Akzent: Gold (nur für KI-Elemente) */
  --color-gold:           #d4a853;
  --color-gold-light:     #e8c476;

  /* Status */
  --color-danger:         #f87171;
  --color-success:        #00D4AA;
  --color-warning:        #fbbf24;

  /* Borders & Dividers */
  --color-border:         #E2E8F0;
  --color-border-hover:   #CBD5E1;
}
```

### Dark Mode (Sidebar, Live-Assistent PiP)
```css
/* Sidebar + PiP nutzen Dark Mode */
--sidebar-bg:           #0D1117;
--sidebar-text:         #E2E8F0;
--sidebar-text-muted:   #A0AEC0;
--sidebar-border:       #2D3748;
--sidebar-hover:        rgba(255,255,255,0.06);
--sidebar-active:       rgba(0,212,170,0.12);
```

---

## Typografie

```css
:root {
  --page-font:       'Inter', system-ui, sans-serif;
  --page-font-mono:  'JetBrains Mono', monospace;
}
```

**Verwendung:**
- `Inter` → Alles: Headlines, Labels, Buttons, Body-Text, Navigation
- `JetBrains Mono` → Timer, Prozent-Zahlen, KPI-Werte, Metriken

**Größen-Hierarchie:**
```
Page Title:       24px  (Inter, weight 700)
Section Label:    12px  (Inter, weight 700, uppercase, letter-spacing 0.5px)
Button / Label:   14px  (Inter, weight 600)
Body:             14px  (Inter, weight 400)
Caption / Muted:  11-12px (Inter, weight 400-600)
KPI-Werte:        28px  (JetBrains Mono, weight 600)
```

**WICHTIG:** Kein Playfair Display, kein DM Sans, kein DM Mono. Nur Inter + JetBrains Mono.

---

## Komponenten

### Glass Panel (.n-glass)
```css
.n-glass {
  background:       var(--glass-bg);
  border:           1px solid var(--glass-border);
  border-radius:    var(--glass-radius);  /* 20px */
  box-shadow:       var(--glass-shadow);
  transition:       all 0.2s ease;
}

.n-glass:hover {
  border-color:     var(--glass-border-hover);
  box-shadow:       var(--glass-shadow-hover);
}
```

### Button — Primary (.n-btn-primary)
```css
.n-btn-primary {
  background:       linear-gradient(135deg, #00D4AA, #00B894);
  color:            #0D1117;
  font-size:        14px;
  font-weight:      600;
  border-radius:    9999px;  /* Pill-Form */
  padding:          12px 28px;
  border:           none;
  box-shadow:       var(--color-teal-glow);
}
```

### Button — Accent/KI (.n-btn-accent)
```css
.n-btn-accent {
  background:       linear-gradient(135deg, #d4a853, #e8c476);
  color:            #0D1117;
  border-radius:    9999px;
  padding:          12px 28px;
}
```
**Verwendung:** Nur für KI-bezogene Aktionen (KI-Frage, KI-Analyse).

### Button — Ghost (.n-btn-ghost)
```css
.n-btn-ghost {
  background:       rgba(0,0,0,0.04);
  color:            #1a1a1a;
  border:           1px solid rgba(0,0,0,0.12);
  border-radius:    9999px;
  padding:          12px 28px;
}
```

### Button — Danger (.n-btn-danger)
```css
.n-btn-danger {
  background:       rgba(248,113,113,0.1);
  color:            #f87171;
  border:           1px solid rgba(248,113,113,0.2);
  border-radius:    9999px;
}
```

### KPI Card (.n-kpi)
```css
.n-kpi {
  background:       #FFFFFF;
  border:           1px solid #E2E8F0;
  border-radius:    20px;
  padding:          22px;
  box-shadow:       0 1px 3px rgba(0,0,0,0.08);
}

/* KPI Label */
font-size:        11px;
font-weight:      600;
letter-spacing:   1.5px;
text-transform:   uppercase;
color:            #6B7280;

/* KPI Wert */
font-family:      'JetBrains Mono';
font-size:        28px;
font-weight:      600;
color:            #1a1a1a;

/* Delta Badges */
--kpi-delta-up:   #00D4AA auf rgba(0,212,170,0.08);
--kpi-delta-down: #f87171 auf rgba(248,113,113,0.08);
```

### Badge (.n-badge)
```css
.n-badge {
  border-radius:    9999px;
  padding:          3px 10px;
  font-size:        11px;
  font-weight:      600;
}

/* Varianten */
.n-badge-primary:  #00D4AA auf rgba(0,212,170,0.08)
.n-badge-accent:   #d4a853 auf rgba(212,168,83,0.08)
.n-badge-danger:   #f87171 auf rgba(248,113,113,0.08)
.n-badge-success:  #00D4AA auf rgba(0,212,170,0.08)
.n-badge-warning:  #fbbf24 auf rgba(251,191,36,0.08)
```

### Karten mit Selection-State (Schwierigkeit, Typ, Modus)
```css
/* Nicht ausgewählt */
.card {
  background:       var(--glass-bg);
  border:           1px solid var(--glass-border);
  border-radius:    var(--glass-radius);
  cursor:           pointer;
}

/* Ausgewählt / Aktiv */
.card-active {
  border-color:     #00D4AA;
  box-shadow:       0 0 0 1px #00D4AA;
}
```

---

## Abstände & Radien

```css
:root {
  --radius-sm:   4px;     /* Kleine Elemente */
  --radius-md:   12px;    /* Inputs */
  --radius-lg:   20px;    /* Karten, Panels, KPIs */
  --radius-pill: 9999px;  /* Buttons, Badges */

  --space-xs:    4px;
  --space-sm:    8px;
  --space-md:    16px;
  --space-lg:    24px;
  --space-xl:    32px;
}
```

---

## Sidebar

```
Breite:          240px (collapsible auf Icon-only)
Hintergrund:     #0D1117 (immer Dark)
Logo:            NERVE + "SALES INTELLIGENCE" Subline
Nav-Items:       Icons (Lucide) + Label, 14px, Inter weight 500
Active-State:    Teal-Highlight (#00D4AA), linker Border oder Background-Tint
User-Section:    Avatar + Name + Plan-Badge, unten fixiert
```

---

## Farbverwendung — Wann welche Farbe

| Farbe | Hex | Verwendung |
|-------|-----|------------|
| **Teal** | #00D4AA | Primäre Aktionen, aktive States, Erfolg, Links, Primary Buttons |
| **Gold** | #d4a853 | KI-Elemente (KI-Speaker, KI-Buttons, KI-Badges) |
| **Rot** | #f87171 | Danger, Fehler, Löschen, kritische Alerts |
| **Grün** | #22C55E | Schwierigkeitsgrad "Einsteiger", positive Trends |
| **Orange** | #F59E0B | Schwierigkeitsgrad "Fortgeschritten", Warnungen |
| **Lila** | #8B5CF6 | Sekundäre Akzente, Sekretärin-Modus |
| **Grau** | #6B7280 | Sekundärer Text, Labels, Muted-Elemente |

---

## Regeln für die Implementierung

1. **Niemals** Hex-Codes direkt in HTML-Templates schreiben
2. **Niemals** `style=""` Attribute für Farben nutzen (Ausnahme: dynamische JS-Werte)
3. **Immer** CSS Custom Properties aus nerve.css verwenden
4. **Immer** `.n-glass` für Karten und Panels
5. **Immer** `.n-btn-primary` / `.n-btn-ghost` für Buttons
6. **Immer** Pill-Form (border-radius: 9999px) für Buttons und Badges
7. **Niemals** Playfair Display, DM Sans oder DM Mono verwenden — nur Inter + JetBrains Mono
8. **Gold nur für KI** — nicht als allgemeiner Akzent
9. Neue Farben/Tokens erst in nerve.css definieren, dann verwenden — nie andersrum
10. Jinja `tojson` in `<script>`-Blöcken: **immer `| safe`** am Ende der gesamten Expression

---

*Aktualisiert: 2026-04-11 | NERVE v0.9.4*
*Quelle: nerve.css (live Design System) + base.html + aktive Templates*
*Änderungen hier → wirken sich auf ALLE Screens aus*
