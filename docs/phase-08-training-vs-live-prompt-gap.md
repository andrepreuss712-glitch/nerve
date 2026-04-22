# Phase 08: Training-EWB-Prompt vs. Live-EWB-Prompt Gap-Analyse

**Erstellt:** 2026-04-22 (Wave 1 Plan 01 Task 3)
**Quelle:** RESEARCH Focus Area 1 + Direkte Code-Inspektion (`services/claude_service.py:258-394`, `services/training_service.py:495-619`)
**Ziel:** Input für Wave 2 Plan 02 (v2-modular Prompt-Text in prompt_versions)

## 1. Scope

Dieser Gap-Report dokumentiert welche Profil-Felder der heutige Live-EWB-Prompt
(`services/claude_service.py` Zeile 258-394 `_build_system_prompt()`) aktuell liest,
welche das v2-modular Prompt-Template (Vault `NERVE Phase 08 EWB-Qualität.md`
Teil 4) lesen SOLL, und welche Änderungen Wave 2 Plan 02 am Prompt-Pipeline-Layer
(neue Datei `services/ewb_pipeline.py` laut D-41) vornehmen MUSS.

**Wichtige Kalibrierung vorab:** Die Vault-Erkenntnis "Training-Prompt ist strukturell
besser als Live-EWB-Prompt" betrifft nicht den Kunden-Persona-Prompt in
`services/training_service.py:495 KUNDEN_PROMPT_TEMPLATE` (der simuliert einen Kunden,
also das Gegenteil vom EWB-Assistenten), sondern die **Kontext-Fülle** und
**Baustein-Struktur**, die in den Live-EWB-Prompt einfliessen.

## 2. Gap-Matrix

Alle 14 Zeilen aus RESEARCH Focus Area 1 inkl. Kategorisierung (keine/neu/Lücke/verstärken):

| # | Element | Live-EWB-Prompt (IST) | Vault-Template v2 (SOLL) | Gap |
|---|---------|-----------------------|--------------------------|-----|
| 1 | Produkt-Beschreibung | ja — Zeile 275-277 (`basis['produkt']`) | ja | keine |
| 2 | USPs | ja — Zeile 280-281 (`basis['usps']`) | ja | keine |
| 3 | Zielgruppe (Alter/Beruf/Einkommen) | ja — Zeile 284-293 | ja | keine |
| 4 | `branche` (aktuell Freitext) | nein — NICHT im Prompt enthalten | ja (Enum D-09) | KRITISCHE LÜCKE — Profile.branche Column (legacy, line 126 in models.py) wird in System-Prompt gar nicht ausgewertet |
| 5 | `branche_kontext` | nein — Feld existiert nicht | ja (D-11) | neu (D-11 Profil-Erweiterung) |
| 6 | `eigene_formulierungen` | nein — Feld existiert nicht | ja (D-07) | neu (D-07 Profil-Erweiterung) |
| 7 | `beweise` | nein — Feld existiert nicht | ja (D-08) | neu (D-08 Profil-Erweiterung) |
| 8 | Anrede (Du/Sie) | ja — Zeile 367 (`ki['ansprache']` als Beschreibung) | ja (harter Constraint D-15) | GAP — IST nur "Kundenansprache: Du (immer einhalten)", SOLL "Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie" (D-15) |
| 9 | Baustein-Struktur (Anker/Reframe/Beweis/Überleitung) | nein — nur freies Gegenargument (max 2-3 Sätze) | ja (4 strukturierte Bausteine) | STRUKTUR-LÜCKE — v1-Prompt kennt keine Bausteine |
| 10 | Active-Listening-Block | nein | ja (D-47, gegen POLISH-35/36/37) | neu (D-47) |
| 11 | 45-Wort-Constraint | nein — aktuell "max 2-3 Sätze" | ja (explizit Wortzahl) | neu |
| 12 | Niemals-apologetisch-Regel | teilweise — Zeile 25 (`"Kein Fachjargon, keine Floskeln wie 'Ich verstehe vollkommen'"`) | ja (explizit) | verstärken |
| 13 | Lernkarten-Matching | ja — Zeile 64-68 (optional felder) | — | Live-only, bleibt |
| 14 | Gegenfrage-Pflicht | ja — Zeile 27-30 | ja | keine |

## 3. Konsequenzen für Wave 2 Plan 02

Wave 2 Plan 02 MUSS drei grundlegende Änderungen im neuen Prompt-Pipeline-Layer
(`services/ewb_pipeline.py` gemäß D-41) vornehmen, welche die Konstruktion des
EWB-System-Prompts aus den heute `services/claude_service.py`-gelesenen Feldern übernimmt:

1. **Branche-Kontext lesen und rendern** — `profile.branche` (Top-Level-Column, aktuell nur als
   DB-Feld vorhanden, aber in `_build_system_prompt` NICHT ausgewertet) UND
   `daten.basis.branche_kontext` (neu via D-11). In Wave 2: beide in den Kontext-Block
   einfügen. Referenz-Code: Analog Zeile 275-277 aus `services/claude_service.py`.

2. **Neue Profil-Listen lesen und rendern** — `daten.basis.eigene_formulierungen` (List, neu via
   D-07) + `daten.basis.beweise` (List, neu via D-08). Beide fliessen in den Baustein "Beweis"
   und den Stil-Baustein "Reframe" ein. Referenz-Stil: Analog zum Einwand-Rendering
   Zeile 320-336 (Iteration über Liste mit strukturiertem Präfix).

3. **Anrede-Constraint verschärfen** — Zeile 367 ersetzen: aus `f'Kundenansprache: {ki["ansprache"]}
   (immer einhalten)'` wird `f'Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form.
   Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie'` — wobei `{anrede}` aus
   `conversation_logs.anrede` (PreCall-Override, Phase 08 Task 2 Block D) ODER Fallback
   `Profile.daten.ki.ansprache` gelesen wird (Priorität PreCall > Profile).

## 4. v2-Prompt-Struktur (Ziel für Wave 2)

Die Baustein-Reihenfolge in v2-modular gemäß Vault-Template:

1. **Kontext-Block** — Profil-Kontext-String aus `build_profile_context()` (Shared-Utility gemäß D-40):
   Produkt, USPs, `branche` (Enum) + `branche_kontext`, `ton`/`stil`, `eigene_formulierungen`, Anrede.
2. **Bausteine (4)** — in fester Reihenfolge:
   - **Anker** (kurz spiegeln was gehört wurde, ~1 Satz)
   - **Reframe** (neuer Winkel, gegen apologetische Muster, ~1-2 Sätze)
   - **Kern-Gegenargument + Beweis** (konkret, nutzt `beweise`-Liste wenn verfügbar)
   - **Überleitung / Alternativ-Close** (Gegenfrage oder nächster Call-To-Action)
3. **Active-Listening-Block** (D-47) — gegen die POLISH-35/36/37 Inkonsistenz-Muster
   (Geschlechts-Erkennung, Hypothesen vor Bedarf, ignoriert Korrekturen). Ergänzt die
   Baustein-Struktur, ersetzt sie NICHT.
4. **Harte Regeln** — max 45 Wörter, keine Apologetik, Anrede konstant (`Wechsle NIEMALS`).

## 5. Anti-Regression-Checks

Wave 2 darf die folgenden bestehenden Prompt-Features NICHT verlieren:

- `profile.branche` MUSS in Live-Prompt sichtbar sein (grep nach `Branche:` oder `branche:`
  im generierten Prompt-String — heute nie vorhanden, ab Wave 2 immer).
- Anrede-Text MUSS die Formulierung `Wechsle NIEMALS` enthalten (D-15 Wortlaut-Lock).
- `Active-Listening`-Baustein muss präsent sein (D-47).
- Bestehende USPs/Zielgruppe/Konsequenz-Ausgaben (Zeile 280-283, 284-293) dürfen NICHT
  entfernt werden — v2 ergänzt, ersetzt keinen existierenden Kontext.
- Lernkarten-Matching (Zeile 64-68 in SYSTEM_PROMPT_BASE) bleibt unverändert (Live-only).
- Gegenfrage-Pflicht (Zeile 27-30 in SYSTEM_PROMPT_BASE) bleibt Pflicht.

## 6. Entscheidungs-Referenzen

Diese Doku referenziert folgende Phase-08-Decisions (siehe 08-CONTEXT.md):

- **D-07** NEU `eigene_formulierungen` (Textarea) — User-Stil-Imitation statt generisches Vertriebs-Sprech.
- **D-08** NEU `beweise` (Textarea) — Zahlen, Kundenzitate, Fallstudien. Claude setzt sie im Baustein "Beweis" ein.
- **D-11** ERWEITERUNG `branche_kontext` (Textarea) — Jargon, typische Pain-Points, was in der Branche funktioniert.
- **D-15** Prompt-Integration Anrede — harter Constraint mit "Wechsle NIEMALS".
- **D-46** Training-Prompt-Gap-Analyse als erste Action in Wave 1 (= dieses Dokument).
- **D-47** Active-Listening-Block — Zusatz gegen POLISH-35/36/37 Inkonsistenzen.

## 7. Nächste Schritte (Wave 2 Plan 02)

1. Neue Datei `services/ewb_pipeline.py` (D-41) mit Funktion `build_ewb_prompt(profile, session_data)`.
2. v2-modular Prompt-Text als `prompt_versions`-Row (module="ewb", version="v2-modular",
   is_active=1, is_default=0) im Seed einfügen.
3. v1-legacy als parallele Row (module="ewb", version="v1-legacy", is_active=1, is_default=1)
   als A/B-Baseline.
4. Router-Logik (`resolve_prompt_version`) nach `user_id % len(active_variants)` mit
   ENV-Override `PROMPT_EWB_VERSION_OVERRIDE` (D-23/D-24).
