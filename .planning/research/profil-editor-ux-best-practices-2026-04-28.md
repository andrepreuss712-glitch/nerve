# Profil-Editor UX Best-Practice-Synthese — NERVE Phase 08.19.2

> **Erstellt:** 2026-04-28 von Claudian
> **Zweck:** Spec-Input für GSD-Plan-Cycle Profil-Editor-Redesign (Phase 08.19.2). Synthetisiert Best-Practices aus etablierten B2B-SaaS-Tools (HubSpot, Salesforce, Notion, Stripe, Linear, Airtable, Apollo) und UX-Literatur (Nielsen Norman Group, Refactoring UI, Carbon Design System) für die NERVE-Profil-Konfigurations-UI.
> **Kontext:** Aktuell ca. 12-15 Sektionen, sektions-organisiert, hat Reihenfolge-/Konsolidierungs-Probleme. Ziel: User soll sich "wohlig" fühlen weil er Patterns aus anderen B2B-Tools wiedererkennt (Familiarity-Bias).

---

## TL;DR

Der etablierte B2B-SaaS-Standard für Settings/Profile-Editoren mit 10+ Sektionen ist **vertikale Sidebar-Navigation links + Content-Pane rechts** (HubSpot, Salesforce, Stripe, Linear, GitHub Settings). Sektions-Reihenfolge folgt **"Setup zuerst, Personalisierung später, Danger-Zone unten"** mit Pflicht-Felder vor Optional-Felder. Inline-Description-Text unterhalb des Labels schlägt Tooltip-on-Hover für alles was zum Befüllen wichtig ist; Tooltips bleiben für Definitionen/Beispiele. Empty-States werden mit Branchen-Templates statt blanken Feldern gefüllt (Notion/Airtable-Pattern). Premium-Feel kommt aus typografischer Hierarchie + großzügigem Whitespace, nicht aus Farb-Akzenten — Linear/Stripe/Notion arbeiten primär mit Schriftgröße und -gewicht. Konkrete NERVE-Empfehlung: Sidebar-Nav mit 5-7 Top-Level-Sektionen (statt 12-15 lose), Quick-Wizard-Onboarding mit Branchen-Template-Auswahl, einheitliches Description-Text-Pattern unter jedem Label, Sonnet-EWB-Kontext-Vorschau pro Sektion zeigen ("Diese Daten kommen im EWB-Prompt an").

---

## Sektion 1: Section-Layout-Patterns

### Bewertete Patterns

| Pattern | Wann passend | Wann nicht | B2B-Beispiele |
|---------|--------------|------------|---------------|
| **Vertikale Sidebar links + Content rechts** | 8+ Sektionen, hierarchisch (Top-Level + Sub-Sections), häufige Cross-Section-Navigation | Mobile-First, <5 Sektionen | HubSpot Settings, Salesforce Setup, Stripe Dashboard, GitHub Settings, Linear Settings, Notion Settings |
| **Horizontale Tabs oben** | 3-6 gleichwertige Sektionen, "alle Tabs gleich wichtig" | >6 Sektionen (Tab-Overflow), Sub-Hierarchie nötig | Slack Preferences, einfache Settings-Pages |
| **Single-Page-Scroll mit Anker-Links** | Wenige Felder, sequentieller Lesefluss erwünscht (Onboarding-ähnlich) | Komplex, hohe Edit-Häufigkeit (Scroll-Fatigue) | Vercel Project Settings, Cloudflare Domain-Settings |
| **Wizard / Multi-Step** | Erstmaliges Setup, Pflicht-Reihenfolge, Conditional-Logic | Wiederkehrende Edits (Wizard erzwingt jedes Mal Durchklicken) | Airtable Onboarding, Stripe Account-Setup, Apollo Sequence-Builder |
| **Accordion (kollabierbar)** | Lange Liste gleichartiger Items (z.B. Einwände-Array) | Top-Level-Navigation (Discoverability schlecht) | Notion Page Properties, Airtable Field-Editor |

### Konsens aus B2B-Tools

Die NN/G und Eleken-Quellen sind eindeutig: **Tabs funktionieren nur bei 3-6 gleichrangigen Sektionen.** Sobald Hierarchie reinkommt oder mehr als 6 Top-Level-Items existieren, ist Sidebar-Navigation Standard. NERVE hat aktuell 12-15 Sektionen — Tabs wären Überlauf.

HubSpot, Salesforce, Stripe, Linear, GitHub haben alle dasselbe Pattern: **kollabierbare Sidebar links** (mit Icons + Labels, optional collapse-bar), Content-Pane rechts mit aktiver Sektion. Andre's "wohlig vertraut"-Anforderung ist mit diesem Pattern erfüllt — jeder B2B-Sales-Vertriebler mit 5+ Jahren CRM-Erfahrung hat das in HubSpot/Salesforce gesehen.

### Empfehlung NERVE

**Vertikale Sidebar links (250-280px Breite) + Content-Pane rechts.**

- 5-7 Top-Level-Gruppen statt 12-15 lose Sektionen (Konsolidierung-Mandate, siehe Sektion 2)
- Sidebar-Items mit Icon + Label (Familiarity-Boost)
- Aktive Sektion farblich hervorgehoben (Akzent-Farbe oder Background-Tint)
- Sub-Sektionen erscheinen entweder als Accordion in der Sidebar (Notion-Pattern) oder als Anker-Sprungmarken im Content-Pane (Stripe-Pattern). NERVE-Empfehlung: **Accordion in Sidebar** weil Top-Level-Gruppen klar abgrenzbar sind (Firma vs. Zielgruppe vs. KI-Stil).
- Mobile/Tablet: Sidebar wird zu Hamburger-Drawer (Standard-Responsive-Pattern). Pre-Launch Solo-Founder-Use-Case ist allerdings Desktop — Mobile ist Sekundär.

---

## Sektion 2: Information-Hierarchy / Reihenfolge-Logik

### Konkurrierende Ordering-Prinzipien

| Prinzip | Logik | Wer macht's so |
|---------|-------|----------------|
| **Setup → Config → Polish** | Erst-Aufruf-Reihenfolge: Was muss zuerst sein damit das Tool überhaupt läuft? | Stripe (Account → Products → Tax → Branding), HubSpot Onboarding |
| **Pflicht → Optional** | User füllt erst Required-Felder, dann Nice-to-haves | Salesforce Object Manager, Notion Database-Properties |
| **Häufig → Selten genutzt** | Frequency-of-Use-Ordering, Power-User-optimiert | NN/G-Empfehlung, Linear Settings |
| **Allgemein → Spezifisch** | Top-Down-Logik (Account → Workspace → User → Feature) | GitHub Settings, Atlassian Tools |
| **Danger-Zone unten** | Destruktive Aktionen (Delete, Reset) am Ende | Universal — alle obigen Tools |

### Konsens aus NN/G + Form-UX-Literatur

Die NN/G-Forschung zeigt klar: **Erst einfache, vertraute Felder — dann komplexe.** Das schafft Momentum (User investiert Zeit, bleibt dran). Bei Settings-Editoren (nicht Onboarding-Forms) wird das ergänzt durch **Frequency-of-Use** für Power-User: was häufig editiert wird steht oben, was selten editiert wird unten oder hinter Progressive-Disclosure.

Stripe und HubSpot kombinieren beides: **Onboarding-Flow erzwingt Setup-Reihenfolge** (Wizard), aber **Settings-Page nach Onboarding ist Frequency-Ordered** (Sidebar-Items in der Reihenfolge "wie oft greift Power-User darauf zu").

### Empfehlung NERVE — konkrete Sektions-Reihenfolge

Vorgeschlagene 5-7 Top-Level-Gruppen, in Reihenfolge:

1. **Firma & Produkt** (Setup-Pflicht, häufig editiert bei Pivots) — Unternehmen, Produkt, Preismodell, USPs, Beweise, Branche
2. **Zielgruppe & Markt** (Setup-Pflicht, mittel-häufig) — ICP-Definition, Zielkunde, Branchen-Kontext
3. **Gesprächsleitfaden** (Häufigster Edit-Bereich für Sales-Vertriebler) — Opener, Pitch, Erlaubnisfrage, Übergänge
4. **Einwände & Antworten** (Mittel-häufig, wachstumsstark — User fügt nach jedem Call neue Einwände hinzu) — Einwände-Array, FAQs, Kaufsignale
5. **KI-Verhalten** (Selten editiert nach Initial-Setup) — Ton, Stil, Anrede, Tabu-Begriffe, Antwortlänge, Sensitivität
6. **Compliance & Sicherheit** (Einmalig, gesetzlich) — Consent-Vorlesetext, DSGVO-Hinweise, Headset-Bestätigung
7. **Account & Konto** (Standard-Settings, Danger-Zone) — Profilbild, Email, Passwort, Subscription, Account-Löschung

**Begründung der Reihenfolge:**
- Setup-Logik vorne (1-3): User MUSS Firma/Produkt/Zielgruppe haben damit EWB überhaupt sinnvoll arbeitet
- Wachstumsbereiche (4): User kommt regelmäßig zurück um neue Einwände einzupflegen — verdient eigene Top-Level-Sektion (statt versteckt unter "Leitfaden")
- Selten-Edits (5-6): Einmal eingestellt, kaum angefasst — weiter unten
- Danger-Zone (7): Universal-Konvention, immer am Ende

**Wichtig:** Innerhalb jeder Sektion gilt **Pflicht → Optional** (Required-Felder oben, Nice-to-haves unten). Das matched NN/G-Empfehlung "leichte Felder zuerst → Momentum aufbauen".

---

## Sektion 3: Inline-Hilfe + Education-Patterns

### Inline-Description vs. Tooltip — die Hauptregel

Aus UX-Movement und HubSpot-Inline-Help-Docs ist die Regel klar:

- **Wenn der User die Information BRAUCHT um das Feld korrekt zu befüllen → Inline-Description-Text unter dem Label.** Sichtbar, immer.
- **Wenn die Information NICE-TO-HAVE ist (Definition, Beispiel, Ausnahme) → Tooltip on Hover/Click.** Versteckbar, on-demand.

NERVE-Beispiele:

| Feld | Information-Typ | UX-Lösung |
|------|-----------------|-----------|
| `usps` | Pflicht-Wissen ("Was sind USPs? Wie viele?") | Inline-Description: "3-5 prägnante Alleinstellungsmerkmale die deine Konkurrenz nicht hat." |
| `tabu_begriffe` | Pflicht-Wissen + Beispiel | Inline-Description: "Wörter die NERVE in EWB-Antworten vermeidet. Beispiel: Versicherungs-Vertriebler hinterlegt 'Provision' statt 'Beratungshonorar'." |
| `branche_kontext` | Optional-Erklärung | Tooltip-Icon (i): "Wird genutzt um die PreCall-Recherche branchenspezifisch zu fokussieren." |
| `ki.sensitivitaet` | Definition (was bewirkt der Slider?) | Tooltip: "Hoch = NERVE meldet sich öfter mit Hinweisen. Niedrig = NERVE wartet auf klare Trigger." |

### "Why this matters?"-Pattern

Stripe und Notion nutzen eine spezielle Variante: **"Why this matters?"-Mini-Link** unter dem Feld der bei Klick einen Hilfe-Drawer öffnet (nicht Modal — Drawer hat den Vorteil dass das Formular sichtbar bleibt).

Für NERVE besonders relevant bei den Feldern wo User unsicher sind WAS das Feld bewirkt:
- "Eigene Formulierungen" — was ist der Unterschied zum "Ton"?
- "Beweise" — wofür werden die genutzt?
- "Übergänge" — wann werden die ausgespielt?

Empfehlung: Pro kritisches Feld einen "Was bewirkt das?"-Inline-Link der einen seitlichen Drawer mit 2-3 Sätzen Erklärung + 1 konkretes Beispiel öffnet. **Drawer schließt nicht das Formular** — User kann Erklärung lesen und gleichzeitig das Feld editieren.

### Live-Preview-Pattern (Zapier, Make, Notion)

Für den NERVE-EWB-Kontext-Aspekt sehr wertvoll: **Live-Preview "So sieht es im EWB-Prompt aus"** als kollabierbares Panel pro Sektion.

User editiert "USPs" → unter dem Feld kollabierbares Panel "Vorschau: So liest die KI deine USPs":

```
Aus dem Profil von Andre Preuß (Maschinenbau):
USPs:
- 24h-Reaktionszeit bei Maschinenausfall
- 15 Jahre Branchen-Erfahrung
- Festpreisgarantie ohne Nachverhandlung
```

Das adressiert direkt Andre's Audit-Frage: **"Kommen meine Daten überhaupt im EWB-Prompt an?"** — User kann visuell verifizieren statt zu raten. Anti-Audit-Pflaster: User sieht JETZT was reingeht statt 6 Monate später zu merken dass Felder tot sind.

### Empfehlung NERVE

1. Einheitliches Inline-Description-Pattern unter jedem Label (Schriftgröße kleiner als Label, grauer Text — Standard-Material/Carbon-Pattern)
2. Tooltips nur für sekundäre Informationen, max. 150 Zeichen
3. "Was bewirkt das?"-Drawer für 8-10 ausgewählte Felder wo User-Verständnis kritisch ist
4. Live-Preview-Panel "Im EWB-Prompt sieht das so aus" pro Sektion — kollabierbar, default kollabiert (sonst zu viel visuelles Noise), kann pro Sektion ein-/ausgeklappt werden

---

## Sektion 4: Empty-State + Default-Vorbefüllung

### Drei Empty-State-Strategien (Userpilot, Carbon, Eleken)

| Strategie | Pattern | Beispiel |
|-----------|---------|----------|
| **Blanke Felder + gute Placeholder** | Minimal, aber kognitiv hart | Slack |
| **Demo-/Sample-Daten** | Vorgefüllte Beispiel-Werte (löschbar) | Notion-Templates, Monday |
| **Wizard-Guided-Setup** | User wird durch Pflicht-Felder geleitet, Templates basierend auf Auswahl | Airtable, Stripe, HubSpot Onboarding |

Konsens-Empfehlung: **Mische die Strategien.** Onboarding-Wizard für Erst-User → bricht Komplexität auf wenige Pflicht-Entscheidungen runter. Settings-Page danach mit guten Default-Templates die je nach Branchen-Auswahl vorbefüllt sind.

### Branchen-Template-Pattern (für NERVE Phase 08.22 hochrelevant)

Notion macht das vorbildlich: **"Choose a template"-Karten-Auswahl** zu Beginn. Marketing-Team, Sales-Team, Engineering-Team — jedes Template lädt eine vorkonfigurierte Datenbank-Struktur. User kann editieren oder bei Null anfangen.

Airtable: **Onboarding-Wizard fragt Use-Case** → "Project Management", "CRM", "Content Calendar" → lädt Field-Setup mit Beispiel-Records.

Stripe: **"Account-Type-Auswahl"** → "Business", "Individual", "Non-Profit" → konfiguriert Compliance-Felder branchenspezifisch.

### Empfehlung NERVE — Branchen-Template-Architektur

**Block N Quick-Wizard (Phase 08.22):**

1. Schritt 1: "Was verkaufst du?" — Branchen-Auswahl (8-12 Karten):
   - Maschinenbau / Industrie
   - SaaS / IT-Lösungen
   - Versicherungen / Finanzen
   - Beratung / Consulting
   - Werkzeug & Equipment
   - Personalvermittlung
   - Bauwesen / Handwerk
   - Energie / Erneuerbare
   - Sonstiges (Freitext)

2. Schritt 2 (basierend auf Branchen-Auswahl): Vorbefüllte Beispiel-Daten in den kritischen Sektionen:
   - 3 Standard-Einwände der Branche ("zu teuer", "kein Bedarf", "Bestandslieferant")
   - 2 typische USPs als Platzhalter zum Editieren
   - Branchentypischer Ton (Maschinenbau: nüchtern-fachlich; SaaS: locker-modern; Versicherungen: vertrauensvoll-strukturiert)
   - Tabu-Begriffe-Default (Versicherung: "Provision" → "Beratungshonorar"; SaaS: "Vendor-Lock-In" → "langfristige Partnerschaft")

3. Schritt 3: User springt in vollen Profil-Editor mit bereits 60-70% gefüllten Feldern und kann verfeinern.

**Wichtig — vermeide Wizard-Falle:** Wizard NUR beim ersten Setup. Nach Onboarding direkt in Settings-Editor. Wizard ist nicht der Default-Edit-Modus (NN/G-Anti-Pattern: Wizard für wiederkehrende Edits frustriert Power-User).

### Empty-Field-Patterns innerhalb Settings-Editor

Wenn User später im Settings-Editor ein Feld öffnet und es ist leer:

- **Placeholder-Text mit Beispiel:** Nicht "Beschreibung..." sondern "z.B. Wir liefern in 24h, Festpreis-Garantie, 15 Jahre Erfahrung"
- **"Beispiel laden"-Button** neben dem Feld bei Multi-Item-Listen (Einwände, FAQs, Tabu-Begriffe) — fügt 1-2 Beispiel-Items ein die User bearbeiten/löschen kann
- **"Aus Branche füllen"-Button** auf Sektions-Ebene — re-applies Branchen-Template auf leere Felder der Sektion (bestehende Werte unangetastet)

---

## Sektion 5: Visual-Hierarchy + Heading-Konsistenz

### Premium vs. Amateur — was unterscheidet's?

Aus der Refactoring-UI / Linear / Stripe / Notion-Research:

**Premium-Tools machen:**
- **Typografie-First-Hierarchie** — Heading-Größe und -Gewicht macht Hierarchie sichtbar, nicht Farbe. Linear h1 ist nicht blau, sondern größer und fetter.
- **Großzügiger Whitespace** — Section-Padding 32-48px, Field-Gap 16-24px, generöses Line-Height (1.5+)
- **Akzentfarbe sparsam** — nur für aktive States, Interactive-Elemente, Errors. Niemals dekorativ.
- **Konsistentes Spacing-System** — 4/8/16/24/32/48px-Skala (Stripe nutzt 4er-Skala, Linear 8er-Skala). Keine zufälligen 13px-Margins.
- **Subtle-Shadows / kein-Shadows** — Linear hat fast keine Shadows, Stripe nur sehr subtile. Schwere Drop-Shadows wirken amateurhaft.
- **Border-Radius einheitlich** — meist 6-8px für Cards/Inputs, 4px für Buttons. Niemals gemischt.

**Amateur-Tools machen:**
- Bunte Section-Header (jede Sektion eigene Farbe → Karneval-Effekt)
- H1-Größe für jeden Abschnitt (keine echte Hierarchie)
- Inkonsistente Padding (mal 12px, mal 18px, mal 25px)
- Schwere bunte Buttons mit Gradient + Shadow + Border-Radius 20px
- Dekorative Icons in jeder Sektion (Emoji-Spam)

### Heading-Hierarchie (Linear/Stripe-Konvention)

| Ebene | Größe | Gewicht | Verwendung |
|-------|-------|---------|------------|
| h1 | 28-32px | 600-700 | Einmal pro Page (Page-Title: "Profil") |
| h2 | 20-22px | 600 | Top-Level-Sektion ("Firma & Produkt") |
| h3 | 16-18px | 600 | Sub-Sektion ("USPs", "Beweise") |
| h4 / Label | 14px | 500-600 | Field-Label ("Unternehmen") |
| Body | 14-16px | 400 | Field-Inhalt, Description |
| Caption | 12-13px | 400 | Inline-Description, Helper-Text, Tooltip |

**Konsistenz-Pflicht:** Niemals h2-Größe für h3-Inhalte verwenden weil "es schöner aussieht". Hierarchie ist der einzige Weg wie User die Struktur visuell parsen.

### Spacing-System (8-Punkt-Grid empfohlen)

Linear-/Material-Konvention: **alles ist Vielfaches von 8px** (oder 4px bei dichten UI-Bereichen).

- Field-Vertical-Gap: 16px oder 24px
- Section-Vertical-Gap: 48px (deutliche Trennung)
- Field-Internal-Padding: 12px Vertical, 16px Horizontal (Input-Padding)
- Card/Container-Padding: 24px oder 32px
- Sidebar-Item-Padding: 8px Vertical, 16px Horizontal

### Farb-Verwendung — Akzent-Strategie

NERVE-Marken-Farbe: vermutlich vorhandene Akzentfarbe (aus Brand-Doc auslesen). Empfehlung:

- **Akzent-Farbe nur für:** aktive Sidebar-Items, Primary-Buttons, Focus-Rings auf Inputs, Active-Tab-Indikator, Save-Confirmation
- **Grau-Skala für:** Borders, Inactive-States, Dividers, Disabled-Elements, Background-Tints
- **Rot nur für:** Errors, Destructive-Actions (Delete, Reset)
- **Grün nur für:** Success-Confirmation, "Gespeichert"-Toast

**Kein dekoratives Color-Coding der Sektionen.** Wenn jede Sektion eine andere Akzentfarbe hat, verliert die Akzentfarbe ihre Funktion (Aktiv-Hervorhebung).

### Empfehlung NERVE

1. Heading-Hierarchie strikt einhalten: h1 nur Page-Title, h2 für die 5-7 Top-Level-Sektionen, h3 für Sub-Sektionen, Label-Style 14px Medium
2. 8px-Spacing-Grid einführen, alle Margins/Paddings auf 8/16/24/32/48 normalisieren
3. Akzentfarbe sparsam — Sidebar-Active-State, Primary-Buttons, Focus-Rings
4. Border-Radius einheitlich (Empfehlung: 6px Cards/Inputs, 4px Buttons)
5. Field-Description-Text in 12-13px Caption-Style, hellgrau (z.B. neutral-500)
6. Section-Padding 32px innen, 48px Vertical-Gap zwischen Sektionen
7. Keine Drop-Shadows auf normalen Cards. Optional: Subtle-Border (1px neutral-200) statt Shadow
8. Ein einheitliches Icon-Set (Heroicons, Lucide, oder Material) — nie gemischt

---

## Konkrete Implementations-Empfehlungen für NERVE Profil-Editor

Actionable Liste für GSD-Plan-Phase 08.19.2. Sortiert nach Implementation-Priorität.

### Architektur (Strukturelle Decisions)

1. **Layout-Switch von aktueller Struktur → Vertikale Sidebar links + Content-Pane rechts.** Sidebar 250-280px, kollabierbar zu Icon-only-Mode (~64px). Aktive Sektion via Akzentfarbe + Background-Tint hervorgehoben.

2. **Konsolidierung 12-15 Sektionen → 5-7 Top-Level-Gruppen** mit dieser Reihenfolge: (1) Firma & Produkt, (2) Zielgruppe & Markt, (3) Gesprächsleitfaden, (4) Einwände & Antworten, (5) KI-Verhalten, (6) Compliance & Sicherheit, (7) Account & Konto. Sub-Sektionen als Accordion in Sidebar oder als Anker-Sprungmarken.

3. **Innerhalb jeder Sektion: Pflicht-Felder oben, Optional-Felder unten.** Pflicht-Felder mit dezentem rotem Asterisk, Optional ohne Marker (Default-Konvention).

### Onboarding & Empty-States

4. **Branchen-Template-Wizard beim Erst-Setup** (Phase 08.22). 8-12 Branchen-Karten, lädt vorkonfigurierte Defaults für USPs, Einwände, Tabu-Begriffe, KI-Ton. User landet danach im Settings-Editor mit 60-70% gefüllt.

5. **"Aus Branche füllen"-Button auf Sektions-Ebene** — re-applied Branchen-Template auf leere Felder, lässt befüllte Felder unangetastet. Gibt Power-Usern Schnellfüllung-Option ohne Wizard-Zwang.

6. **"Beispiel laden"-Button auf Multi-Item-Listen** (Einwände, FAQs, Tabu-Begriffe) — fügt 1-2 Beispiel-Items ein. User editiert oder löscht.

### Inline-Education

7. **Einheitliches Inline-Description-Pattern unter jedem Label.** Schriftgröße 12-13px Caption-Style, neutral-500-Farbe. Kurz und konkret (max. 1 Satz + Beispiel). Pflicht für jedes Feld wo User raten könnte was reinkommt.

8. **Tooltip-Icons (i) nur für sekundäre Definitionen.** Max. 150 Zeichen Inhalt. Niemals für kritische Befüll-Information (das ist Inline-Description).

9. **"Was bewirkt das?"-Drawer-Links** für 8-10 kritische Felder wo User-Verständnis hoch ist (eigene_formulierungen, beweise, übergänge, ki.sensitivitaet, branche_kontext). Klick öffnet Side-Drawer mit 2-3 Sätzen + 1 Live-Beispiel. Drawer schließt Formular nicht.

10. **Live-EWB-Prompt-Preview-Panel pro Sektion.** Kollabierbar, default zu. Zeigt: "So liest die KI deine Daten." User editiert ein Feld → Preview aktualisiert. Adressiert Andre's Audit-Findings direkt — User sieht ob Daten ankommen.

### Visual-Polish

11. **Heading-Hierarchie strikt einhalten:** h1 (28-32px/700) nur als Page-Title "Profil", h2 (20-22px/600) für Top-Level-Sektionen, h3 (16-18px/600) für Sub-Sektionen, Labels 14px/500.

12. **8px-Spacing-Grid einführen.** Alle Margins/Paddings auf 8/16/24/32/48 normalisieren. Section-Padding 32px innen, 48px Section-Gap, 16-24px Field-Gap.

13. **Akzentfarbe sparsam.** Nur für Sidebar-Active, Primary-Buttons, Focus-Rings, Save-Confirmation. Niemals dekorativ pro Sektion. Borders/Dividers in neutral-200, Inactive-Text in neutral-500.

14. **Border-Radius einheitlich:** 6px Cards/Inputs/Containers, 4px Buttons. Konsistenz wichtiger als spezifischer Wert.

15. **Save-Verhalten: Auto-Save + sichtbarer Indicator** (Linear/Notion-Pattern). Kein expliziter "Speichern"-Button für Einzelfelder. Statt dessen: oben rechts "Alle Änderungen gespeichert"-Indicator, bei aktivem Editieren "Wird gespeichert..." mit Spinner. Reduziert kognitive Last (User muss nicht überlegen "habe ich gespeichert?").

---

## Quellen-Liste

### Section-Layout-Patterns
- [Tabs UX: Best Practices, Examples, and When to Avoid Them — Eleken](https://www.eleken.co/blog-posts/tabs-ux)
- [The Ultimate Guide to Tab Design — Lollypop](https://lollypop.design/blog/2025/december/tabs-design/)
- [The 6 types of UX navigation for SaaS — Merveilleux](https://www.merveilleux.design/en/blog/article/comprehensive-guide-for-saas-products-on-ux-navigation-types)
- [SaaS UI workflow patterns curated list — GitHub Gist](https://gist.github.com/mpaiva-cc/d4ef3a652872cb5a91aa529db98d62dd)
- [A guide to HubSpot's navigation — HubSpot Knowledge Base](https://knowledge.hubspot.com/help-and-resources/a-guide-to-hubspots-navigation)
- [Anatomy of an Effective SaaS Navigation Menu Design — Lollypop](https://lollypop.design/blog/2025/december/saas-navigation-menu-design/)

### Information-Hierarchy & Form-Ordering
- [Website Forms Usability: Top 10 Recommendations — NN/G](https://www.nngroup.com/articles/web-form-design/)
- [Few Guesses, More Success: 4 Principles to Reduce Cognitive Load in Forms — NN/G](https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/)
- [Less Effort, More Completion: The EAS Framework — NN/G](https://www.nngroup.com/articles/eas-framework-simplify-forms/)
- [Better Forms Through Visual Organization — NN/G Video](https://www.nngroup.com/videos/better-forms-visual-organization/)
- [Progressive Disclosure — NN/G](https://www.nngroup.com/articles/progressive-disclosure/)
- [What is Progressive Disclosure? — IxDF](https://ixdf.org/literature/topics/progressive-disclosure)
- [Must-Follow UX Best Practices When Designing A Multi Step Form — Growform](https://www.growform.co/must-follow-ux-best-practices-when-designing-a-multi-step-form/)

### Inline-Hilfe & Tooltips
- [Help Text vs Tooltips: Which Is Better for Forms — UX Movement](https://uxmovement.substack.com/p/help-text-vs-tooltips-which-is-better)
- [What Is a Tooltip? Types, Best Practices & Design Tips — UXPin](https://www.uxpin.com/studio/blog/what-is-a-tooltip-in-ui-ux/)
- [Tooltip Component Usage — Carbon Design System](https://carbondesignsystem.com/components/tooltip/usage/)
- [Inline Help Text for Fields and Modules — HubSpot Developers](https://developers.hubspot.com/changelog/inline-help-text-for-fields-and-modules)
- [Designing effective tooltips — Formsort](https://formsort.com/article/tooltips-design-signup-flows/)

### Empty-States & Onboarding-Wizards
- [Empty State UX Examples and Design Rules — Eleken](https://www.eleken.co/blog-posts/empty-state-ux)
- [Empty State in SaaS Applications — Userpilot](https://userpilot.com/blog/empty-state-saas/)
- [Empty States Pattern — Carbon Design System](https://carbondesignsystem.com/patterns/empty-states-pattern/)
- [Onboarding UX Patterns: Empty States — UserOnboard](https://www.useronboard.com/onboarding-ux-patterns/empty-states/)
- [Airtable Onboarding Wizard: Step-by-Step Flow — Candu Blog](https://www.candu.ai/blog/airtables-best-wizard-onboarding-flow)
- [Empty State UX Examples & Best Practices — Pencil & Paper](https://www.pencilandpaper.io/articles/empty-states)

### Visual-Hierarchy & Premium-Design
- [16 Design Case Studies — Blake Crosley](https://blakecrosley.com/blog/design-studies-collection)
- [styleseed: Design system with Toss/Stripe/Linear/Vercel/Notion brand skins — GitHub](https://github.com/bitjaru/styleseed)
- [Top SaaS UX Design Strategies for 2025 — Webstacks](https://www.webstacks.com/blog/saas-ux-design)
- [Best UI/UX Practices for B2B SaaS Platforms — Moken Digital](https://www.moken.digital/post/best-ui-ux-practices-for-b2b-saas-platforms)

### Sales-Tool-Konkurrenz-Beispiele
- [HubSpot vs Salesloft vs Outreach vs Apollo (2025) — Buzzlead](https://www.buzzlead.io/blogs/blogs-hubspot-vs-salesloft-vs-outreach-vs-apollo-the-sales-engagement-comparison-nobod)
- [Apollo.io Knowledge Base](https://knowledge.apollo.io/hc/en-us)

---

*Erstellt 2026-04-28 von Claudian. Dient als Spec-Input für GSD-Plan-Cycle Phase 08.19.2 (Profil-Editor-Redesign). Synthesegrundlage für UI-Entscheidungen — Plan-Phase übersetzt diese Empfehlungen in konkrete Code-Tasks (Frontend-Komponenten, Routing, State-Management).*
