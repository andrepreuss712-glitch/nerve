# Phase 08: EWB-Qualität & Profil-Tiefe — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning
**Launch-kritisch:** ja (blockiert Early-Access-Go-Live wenn EWB-Qualität nicht messbar)

<domain>
## Phase Boundary

Phase 08 liefert drei zusammenhängende Outcomes vor Launch:

1. **EWB-Qualität messbar machen** — POLISH-55 3-State-Behandelt-Rating als Datengrundlage, A/B-fähige Prompt-Pipeline mit deterministischem Routing, Pre-Launch-Quality-Gates (80% sofort-vorlesbar, Varianz-Range < 30).
2. **Profil-Tiefe ausbauen** — 2 neue Felder (`eigene_formulierungen`, `beweise`), 2 Umbau-Felder (`branche` Freitext → Enum, `ton` Freitext → Select+Flex), 1 Erweiterung (`branche_kontext`), 1 Umbenennung (`zusatz` → "Spezielle Anweisungen an NERVE"), PreCall-Override für Anrede pro Session in `conversation_logs.anrede`.
3. **Tooltip-Qualität als Launch-Gate** — ~20 Tooltips mit 3-Block-Pattern (Was rein soll / Beispiel / Nicht verwechseln mit), sichtbarer i-Button ≥16×16px, Read-Only Beispiel-Profil-Modal, Anti-Pattern-Review vor Launch.

**NICHT in Scope (bewusst separiert):**
- KI-Inferenz für EWB-Rating (kommt Phase 4.19 wenn Transkript-Persistierung steht)
- Phase 08.5 Question-Answering-Loop (eigene Phase, nutzt aber Phase-08-Pipeline-Utils)
- Phase 07.5 EWB-Feed-Redesign (eigene Phase, nach 08+08.5)
- Onboarding-Wizard-Integration für neue Profil-Felder (Phase 4.16.1)
- Painpoint-Extractor-Prompt-Rewrite aus POLISH-24 (kann in Phase 08 Wave 2b mitgenommen werden, falls Zeit — sonst eigene Phase)
- Inter-Rater-Reliability-Tooling (ab Team/Coach, Phase 4.15+)

</domain>

<decisions>
## Implementation Decisions

### POLISH-55: 3-State Behandelt-Semantik (LOCKED vor Discuss)

- **D-01:** `ObjectionEvent.success` wird von `Boolean NOT NULL` → `Boolean NULLABLE` (SQLite-Migration via ALTER-Replay falls nötig). 3-State-Modell: `TRUE` = Erfolg, `FALSE` = Kein Erfolg, `NULL` = Unbekannt/Überspringen.
- **D-02:** Migrations-Teil: Alt-Daten aus POLISH-38.1 (Boolean-Werte aus "technisch erfolgreich") werden via Migration auf NULL gesetzt. Ohne diesen Reset wären A/B-Auswertungen durch Alt-Daten verzerrt. Migration-Marker dokumentieren (z.B. `migration_v08_01_reset_success_polish38_1`).
- **D-03:** Post-Call-UI: Rating-Block im bestehenden Post-Call-Screen (`/session/<id>`-Ankunfts-Seite oder Training-Abschluss), freiwillig (kein Pflichtfeld), Benefit-Framing wortwörtlich: *"Hilf uns, dir zu helfen. Wie empfandest du die Einwandbehandlung — welcher der folgenden EWBs hatte Erfolg? Basierend auf deinen Antworten kann NERVE dir in Zukunft besser bei der EWB helfen."*
- **D-04:** Pro EWB: 3 Buttons — "Erfolg" (`success=TRUE`), "Kein Erfolg" (`success=FALSE`), "Überspringen" (`success=NULL`). Kein Submit-Button, Klick speichert sofort.
- **D-05:** A/B-Test-Auswertungen filtern strikt `WHERE success IS NOT NULL`.
- **D-06:** KI-Inferenz (automatische Vorbefüllung des Ratings durch Post-Call-Sonnet-Analyse des Transkripts) ist explizit OUT OF SCOPE für Phase 08. Kommt als Ergänzung ab Phase 4.19 (Transkript-Persistierung). User bestätigt/korrigiert dann per Klick — Mechanik bleibt identisch.

### Profil-Felder — Netto-Änderung (LOCKED vor Discuss)

- **D-07: NEU** `eigene_formulierungen` (Textarea multi) — Sätze die der User im Call wortwörtlich sagt. Ziel: Claude imitiert User-Stil statt generisches Vertriebs-Sprech.
- **D-08: NEU** `beweise` (Textarea multi) — Zahlen, Kundenzitate, Fallstudien. Claude setzt sie im Baustein "Beweis" ein.
- **D-09: UMBAU** `branche` Freitext → Select-Enum mit fixen Werten: `saas_b2b`, `maschinenbau`, `versicherung`, `finanzprodukte`, `immobilien`, `coaching`, `beratung`, `sonstiges`. Bestehende Freitext-Werte migrieren in `sonstiges` (mit Originaltext in `branche_kontext`) oder via Heuristik-Mapping (in Plan entscheiden).
- **D-10: UMBAU** `ton` Freitext → Select mit 4 Stilen + Flex-Escape: Optionen `Direkt/Klartext`, `Beratend/Sanft`, `Enthusiastisch/Begeistert`, `Analytisch/Zahlenorientiert`, plus "Eigener Stil"-Textfeld das nur erscheint wenn nichts davon passt. Klarer Default-Wert empfohlen (in Plan entscheiden).
- **D-11: ERWEITERUNG** `branche_kontext` (Textarea) als neues Sub-Feld direkt unter `branche`. Jargon, typische Pain-Points, was in der Branche funktioniert vs. nicht.
- **D-12: UMBENENNEN** `zusatz` → User-sichtbares Label "Spezielle Anweisungen an NERVE". DB-Key bleibt `zusatz` (keine Migration), nur Template-Label ändert sich.
- **D-13: NICHT NEU** "Typische Gegenargumente" — existiert bereits als `einwaende[].gegenargument`. Nur im Onboarding prominenter positionieren (Phase 4.16.1 Scope).
- **D-14: PRECALL-OVERRIDE** Anrede (Du/Sie) wird pro Session im PreCall-Setup abgefragt (2-Button-Wahl). Gespeichert in neuer Spalte `conversation_logs.anrede` (String, nullable — fallback auf Profil-Default). Profil-Feld `ki_ansprache` bleibt als Default bestehen. Prompt nutzt Override > Profil-Default.
- **D-15: Prompt-Integration Anrede** Alle EWB-Prompts bekommen harten Constraint im System-Prompt: *"Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie."*

### Tooltip-Qualität (LOCKED vor Discuss)

- **D-16: 3-Block-Pattern pro erklärungsbedürftigem Feld:** (1) Was rein soll (1-2 Sätze klar), (2) Beispiel (konkret, kurz, neutral, fiktive Platzhalter), (3) Nicht verwechseln mit (Abgrenzung zu 2-4 ähnlichen Feldern mit je 1 Satz Unterschied).
- **D-17: Abgrenzungs-Matrix** (~20 Tooltips):
  - `eigene_formulierungen` ↔ Stil (`ton`) / Gegenargumente / Zusatz
  - `beweise` ↔ USPs / Konsequenz / `branche_kontext`
  - `branche_kontext` ↔ `branche` (Enum) / Zielgruppe / Unternehmen
  - `ton` (Stil) ↔ Techniken aktiv / Zusatz / `eigene_formulierungen`
  - `gegenargument` ↔ Techniken aktiv / `eigene_formulierungen`
  - `branche` (Enum) ↔ `branche_kontext` / Unternehmen
  - `zusatz` (Spezielle Anweisungen) ↔ Techniken verboten / Stil
- **D-18: i-Button-UI** mindestens 16×16px, sichtbarer Hover-State, nicht winzig versteckt. Konsistentes Design über alle Felder.
- **D-19: Beispiel-Profil-Modal** Read-Only-Modal im Profil-Editor mit komplett ausgefülltem Demo-Profil. Link-Text "Sieh dir ein ausgefülltes Beispiel an". Anderer Lerntyp als Tooltip-Text.
- **D-20: KRITISCHE CONTENT-REGEL** Keine NERVE-spezifischen, André-persönlichen oder echten-Firmen-Beispiele in Tooltips. Nur neutral/generisch mit fiktiven Platzhaltern ("Firma XY", "Anna S.", "Branche Maschinenbau"). Bei Stil-Bandbreite: mehrere Beispiele über verschiedene Stile zeigen.
  - **Anti-Pattern (nicht machen):** "Guck mal, du kennst das — im 10. Call..." (= André-Ton), "87% unserer Kunden..." (= NERVE-Stat), "Sparkasse Iserlohn nutzt..." (= echte Firma).
  - **Richtig:** "Darf ich fragen, was Sie aktuell einsetzen?" / "Die Firma XY hat nach 3 Monaten 15% mehr Abschlüsse gefahren."
- **D-21: Launch-Gate** Claudian-Review-Pass (~30 Min) auf alle Tooltips mit Anti-Pattern-Liste. Kein Tooltip geht live ohne diesen Check. Review-Verantwortung: Claudian (Vault-Instanz) nach erstem Draft durch Claude Code.

### A/B-Test-Infrastruktur (Discuss-Finding a)

- **D-22: Keine neue Tabelle.** Wiederverwendung der bestehenden FT-Logging-Infrastruktur aus Phase 4.7.1: `ft_objection_events.prompt_version` + `ft_assistant_events.prompt_version` loggen bereits die Variante pro Event. A/B-Auswertung per JOIN:
  ```sql
  SELECT ftoe.prompt_version, COUNT(*) AS n,
         AVG(CASE WHEN oe.success = TRUE THEN 1.0 ELSE 0.0 END) AS success_rate
  FROM ft_objection_events ftoe
  JOIN objection_events oe ON oe.conversation_log_id = ftoe.ft_session_id_derived
                           AND oe.einwand_typ = ftoe.objection_type
  WHERE oe.success IS NOT NULL
  GROUP BY ftoe.prompt_version;
  ```
  (Die exakte Join-Key-Mechanik ist Researcher-Aufgabe — `ft_session_id` → `conversation_log_id` Mapping prüfen.)
- **D-23: Routing-Strategie** Deterministisch per `user_id % len(active_variants)`. Gleicher User sieht immer dieselbe Variante (konsistenter User-Eindruck). Skalierbar auf 3+ Varianten via `len(active_variants)`, nicht hardcoded mod 2.
- **D-24: ENV-Override als Safety-Net** `PROMPT_EWB_VERSION_OVERRIDE=v2-modular` forciert alle User auf die angegebene Variante, ignoriert Routing wenn gesetzt. Router-Logik: ENV-Var-Check als **FIRST CHECK**, erst wenn leer/unset greift mod-basiertes Routing. Use-Cases: Emergency-Rollback ohne Code-Deploy, saubere UAT (alle User = v2), Debug-Support.
- **D-25: ENV-Var-Dokumentation** `PROMPT_EWB_VERSION_OVERRIDE` in `.env.example` und `deploy/nerve.service` dokumentieren (Kommentar: leer = A/B-Routing aktiv, gesetzt = forcierte Variante).
- **D-26: `prompt_versions`-Schema** In Phase 4.7.1 gibt es `is_active=1` pro `module`. Für A/B-Test wird dieses Feld um Semantik erweitert: mehrere Zeilen pro `module` können `is_active=1` haben (alle werden in Router-Variante-Liste geladen). Variante-Priorität bzw. Default-Fallback via eine zusätzliche Spalte (z.B. `ab_weight` oder `is_default` — Planner entscheidet basierend auf Produkt-Semantik).

### Quality-Gate Messung (Discuss-Finding b)

- **D-27: EWB-Quality-Score Komposition** Jeder bewertete EWB-Output bekommt 3 binäre Sub-Kriterien, die zu einem 0-100 Score gewichtet werden:
  - `klingt_wie_Mensch` (Gewicht 1x)
  - `keine_Halluzination` (Gewicht 2x — größtes Launch-Risiko)
  - `trifft_Einwand` (Gewicht 1x)
  - Formel: `(klingt_wie_Mensch + 2 * keine_Halluzination + trifft_Einwand) / 4 * 100` → Skala 0-100
  - Vorlesbar-Gate: ≥80% der bewerteten EWBs haben Score ≥80
- **D-28: Varianz-Gate** `range(max − min) < 30` über 5 Repeats pro Szenario in ALLEN 3 Szenarien. Score-Basis: Gesamt-Score der Session aus Scoring-Pipeline (`gesamt_score` in `conversation_logs`).
- **D-29: Outlier-Handling Varianz** Bei Range knapp an Grenze (28-32) manuell prüfen: Outlier (Bug — Latenz, Prompt-Injection, API-Fehler, Race-Condition) oder echte Varianz? Outlier darf mit Dokumentation im Review-Template entfernt werden, dann Range über n=4 neu berechnen. Kein blindes Pass/Fail.
- **D-30: Messung Pre-Launch** Manuell durch André. 100 EWBs × ~10s binäre Bewertung ≈ 17min + Setup. Template mit 3 Sub-Kriterien pro EWB.
- **D-31: Messung Post-Launch** POLISH-55-Success-Rate als ongoing Signal via Admin-Dashboard-Card (`/admin/ewb-quality` oder Integration in bestehendes `/admin/costs`). Kein Claude-Classifier (LLM-Varianz würde Varianz-Messung zirkulär kompromittieren).
- **D-32: Skalierungs-Pfad Post-Launch** Sobald 20+ Datenpoints pro Szenario (2-3 Wochen Prod): Monitoring zusätzlich auf `σ < 15` umstellen — präziser, aber erst ab ausreichend n statistisch belastbar.
- **D-33: Hero-Score als Parallel-Metrik** Hero-Score aus bestehendem Coach-System wird parallel getrackt, aber NICHT als Gate verwendet. Divergenz zwischen EWB-Quality-Score und Hero-Score nach Launch = Signal für Score-Kalibrierungs-Arbeit (Phase 07.3 Scope, nicht 08).

### Test-Datensatz (Discuss-Finding c)

- **D-34: Varianz-Gate Quelle** NUR Training-Modus. 3 Szenarien × 5 Repeats = 15 Sessions. Identische Inputs = Kontrolle. Szenarien:
  - **A "Easy":** Standard-Einwand "Zu teuer" bei einfachem SaaS-Profil (wenige Profil-Felder gefüllt).
  - **B "Profil-reich":** Voll ausgefülltes Profil inkl. `branche_kontext` + `eigene_formulierungen`. Testet ob tiefer Profil-Input konsistent greift.
  - **C "Edge-Case":** Multi-Einwand-Sequenz "Zu teuer" → "Haben schon was Ähnliches".
- **D-35: Vorlesbar-Gate Quelle** 60/40 Training/Real-World-Mix. ~60 Training-EWBs (aus den 15 Varianz-Sessions fallen ~75 EWBs ab, davon 60 für Vorlesbar nutzen, 15 skippen). ~40 EWBs aus 5+ echten Calls (Cold-Call oder Meeting mit Consent). Total 100 EWBs via Template bewertet durch André.
- **D-36: Begründung 60/40 statt 83/17** Vorlesbar-Qualität = Frage wo Real-World-Validierung am wichtigsten ist. Training-Bot ist ein freundliches Claude-Modell, echte Kunden sind unberechenbarer. 15 echte EWBs zu wenig für belastbares Signal.
- **D-37: Zeitaufwand André** ~4h verteilbar über 2-3 Tage: 15 Training-Sessions ~2h, 5 echte Calls ~1h, 100 EWBs bewerten ~17min, Setup/Dokumentation ~30min.
- **D-38: Bonus-Datenquelle post-Launch** Freiwilliger Backfill-Rating-Call per Email an EA-User ("3 alte Sessions rückwirkend raten, 2 Min, macht NERVE besser"). Nicht als Gate-Source geeignet (Recall-Bias, niedrige Rücklaufquote). Pure Bonus-Signal.
- **D-39: Bewertungs-Verantwortung** Initial alle Ratings durch André (Solo-Founder). Inter-Rater-Reliability erst relevant wenn Team/Coach dazukommt (Phase 4.15+).

### Phase-08-Pipeline-Architektur für 08.5-Reuse (Discuss-Finding d)

- **D-40: Shared-Utils-Modul `services/prompt_pipeline.py` (NEU in Phase 08).** Enthält die Phase-08.5-relevanten wiederverwendbaren Funktionen:
  - `build_profile_context(user_id, mode)` — standardisierter Profil-Kontext-String (Produkt, USPs, `branche`, `branche_kontext`, `stil`/`ton`, `eigene_formulierungen`, Anrede aus Session-Override oder Profil-Default).
  - `resolve_prompt_version(module: str, user_id: int) -> str` — A/B-Routing gemäß D-23/D-24 (ENV-First-Check, dann `user_id % len(active_variants)`). `module` ist Argument, nicht hardcoded.
  - `log_pipeline_event(event_type: str, module: str, data: dict)` — strukturiertes Logging-Interface, schreibt modul-agnostisch in die jeweilige FT-Tabelle (`ft_objection_events` Phase 08, `ft_qa_events` Phase 08.5).
- **D-41: Modul-spezifische Pipeline `services/ewb_pipeline.py` (NEU in Phase 08).** Ruft Shared-Utils, definiert EWB-spezifische Bausteine (Anker / Reframe / Kern-Gegenargument / Beweis / Überleitung / Alternativ-Close), Prompt-Assembly, Output-Parsing. Keine generische Bausteinen-Registry — direkt EWB-Flow.
- **D-42: NICHT in Phase 08 gebaut (kommt in 08.5)** `apply_tabu_filter()`, `profile_faqs`-Tabelle, Frage-Klassifikator, Embedding-Match. Planner entscheidet, ob `apply_tabu_filter()` als leere Stub-Funktion in 08 vorgesehen wird (nur wenn trivial und keine Test-Last).
- **D-43: Test-Strategie** Unit-Tests für Shared-Utils (`build_profile_context`, `resolve_prompt_version`). Integration-Tests im Modul-Layer (EWB end-to-end). Phase 08.5 kann Shared-Unit-Tests 1:1 übernehmen.
- **D-44: Aufwand-Kalkül** +~1h Design in Phase 08 (Trennung Utils/Modul statt Monolith), −4-6h in Phase 08.5 durch vermiedenes Refactoring. Netto-Ersparnis 3-5h. Plus: Vermeidet Refactoring in gelocktem Pfad → CLAUDE.md Abrieb-Prinzip.
- **D-45: Naming** `services/prompt_pipeline.py` als Default. Alternativen akzeptabel (`prompt_utils.py`, `prompt_core.py`) — Bike-Shedding, Planner entscheidet pragmatisch basierend auf Repo-Konventionen.

### Zusätzliche Gap-Analyse Wave 1 (aus Vault: Training-EWB-Prompt als Referenz)

- **D-46: Training-Prompt-Gap-Analyse als erste Action in Wave 1.** Vault-Erkenntnis: Training-EWB-Prompt ist strukturell besser als Live-EWB-Prompt (Beispiel Kuschewsky-Session). Bevor modulare v2-Prompts geschrieben werden: Training-Prompt in `services/claude_service.py` oder `services/training_service.py` komplett analysieren, Kontext-Elemente dokumentieren, Gap zum Live-EWB-Pfad kartieren. Als RESEARCH.md-Input für den Planner.
- **D-47: Active-Listening-Block** Zusätzlicher Prompt-Block gegen die Inkonsistenz-Muster aus der Köhler-Session (POLISH-35: Geschlechts-Erkennung, POLISH-36: Hypothesen vor Bedarf, POLISH-37: ignoriert Korrekturen). Ergänzt die Baustein-Struktur, kein Ersatz.
- **D-48: Painpoint-Extractor-Prompt (POLISH-24)** Kann als optionale Wave 2b mitgenommen werden, falls Zeit. Sonst explizit an Backlog — nicht in Phase 08 erzwingen.

### Claude's Discretion

- Migrations-Mechanismus für `ObjectionEvent.success`-Nullable (SQLite ALTER-Replay vs. neue Migration-Infrastruktur) — Planner wählt konsistent zum Repo-Pattern.
- Default-Wert für `branche`-Enum (SaaS_B2B als Default oder NULL erlauben?) — Planner entscheidet basierend auf Profil-Editor-UX.
- Exakte Spalten-Semantik für A/B-Auswertung in `prompt_versions` (z.B. `ab_weight`, `is_default`, `ab_pool`) — Planner entscheidet mit Researcher.
- Struktur des EWB-Quality-Rating-Templates (Google-Sheet vs. lokale Markdown-Datei vs. kleines Admin-Tool) — Planner wählt leichtestes Format.
- Szenario-Definitions-Format für die 3 Test-Szenarien A/B/C (Seed-SQL, Training-Szenario-Tabelle, Markdown-Spec) — Planner wählt pragmatisch.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase-08-Briefing (MUST READ)
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Phase 08 EWB-Qualität.md` — Vollständiges Phase-08-Briefing inkl. LOCKED-Decisions-Block 22.04.2026, EWB-Prompt-Template, Baustein-Struktur, Varianz-Problem-Beschreibung, Training-vs-Live-Gap-Analyse, POLISH-24-Painpoint-Extractor-Problem. **Abschnitt "UPDATE 22.04.2026 — LOCKED Decisions vor Discuss-Phase" ist bindend.**

### Abhängigkeiten & Parallelfragen
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Phase 08.5 Question-Answering-Loop.md` — Relevant für D-40 bis D-45 (Architektur-Reuse). Definiert was 08.5 zusätzlich braucht (Frage-Klassifikator, `profile_faqs`, Exclusion-Liste).
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE Finaler Polish Pass.md` §POLISH-55 — Behandelt-Semantik-Detail-Spec (3-State, Benefit-Framing, Button-Layout).

### Architektur-Grundlage aus Prior Phases
- `.planning/phases/04.7.1-finetuning-logging-grundlage-inserted/04.7.1-CONTEXT.md` — FT-Logging-Architektur, `ft_*`-Tabellen-Schema, `prompt_versions`-Seed-Strategie. Phase 08 nutzt diese Infrastruktur (D-22).
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\02 Projekte\NERVE FineTuning Logging Architektur.md` — Detail-Spec für FT-Tabellen, DSGVO-Regeln, Export-Format.

### DSGVO- & App-Constraints (bindend)
- `C:\Users\andre\OneDrive\Desktop\Nerve-Vault\CLAUDE.md` §"NERVE Architektur-Entscheidungen" — Cold-Call loggt keine Kundenstimme, Meeting nur mit Consent, kein Audio-Storage, EU-Only Stack. Plus "Abrieb-Prinzip" (relevant für D-40 bis D-45).
- `CLAUDE.md` (salesnerve) — Umlaut-Regel (User-Text mit Umlauten, Code-Identifier ASCII). Relevant für Tooltip-Content (User-facing) vs. Profil-Field-Keys (ASCII).

### Code-Anker (zu lesen durch Researcher/Planner)
- `database/models.py` — `ObjectionEvent` (line 342), `Profile` (121), `ConversationLog` (231), `PromptVersion` (463), `FtCallSession` (381), `FtAssistantEvent` (410), `FtObjectionEvent` (438).
- `services/claude_service.py` — EWB-Prompt-Pipeline (`analysiere_mit_claude` line 633, Streaming-Variante line 664). Training-EWB-Prompt-Gap-Analyse startet hier.
- `services/training_service.py` — Training-Modus-Prompt-Struktur (D-46 Gap-Analyse).
- `templates/profile_editor.html` — Profil-Editor-UI (einwaende, branche, ki_ansprache, zusatz). Neue Felder/Umbau/Tooltip-Integration hier.
- `routes/profiles.py` — Profil-CRUD-Endpoints.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (aus Prior-Phases & Codebase-Scout)
- **`ObjectionEvent`-Model** existiert seit Phase 4.7 mit `success Boolean NOT NULL`. Phase 08 macht es nullable (D-01) und resettet Alt-Daten (D-02).
- **`PromptVersion`-Model** existiert seit Phase 4.7.1 mit `UniqueConstraint('version', 'module')` und `is_active`-Flag. Phase 08 erweitert die `is_active=1`-Semantik um A/B-Support (D-26) — mehrere aktive Zeilen pro `module`.
- **`ft_objection_events.prompt_version`** loggt bereits pro EWB die Variante. Phase 08 fügt nur Router + ENV-Override + Routing-Wiring hinzu (D-23/D-24). Keine neue Logging-Tabelle.
- **`ft_assistant_events.prompt_version`** loggt jeden Hint — für allgemeines EWB-A/B-Querying zusätzlich zu `ft_objection_events`.
- **`FtCallSession.user_rating`** existiert für Session-Level-Rating (Phase 4.7.1). Ergänzung durch per-EWB-Rating via `ObjectionEvent.success` (D-01 bis D-04).
- **Profil-Editor (`templates/profile_editor.html`)** hat bereits Struktur für neue Sektion "EWB-Feinschliff" (einwaende-list, ki_ansprache-radios, vi_zusatz-textarea). Neue Felder (`eigene_formulierungen`, `beweise`, `branche_kontext`, `ton`-Select) reihen sich in bestehende Sektion ein.
- **`einwaende[].gegenargument`** (in Profile.daten JSON) existiert bereits — wird von D-13 NICHT ersetzt, nur im Onboarding prominenter positioniert (Phase 4.16.1).
- **ENV-Var-Pattern** etabliert in `.env.example` (Fernet-Keys aus Phase 4.6.1, Resend-Keys aus 4.7). `PROMPT_EWB_VERSION_OVERRIDE` reiht sich ein (D-25).
- **Consent-Modal-Pattern** aus Phase 06.5 — Struktur wiederverwendbar für PreCall-Anrede-Overlay (D-14).

### Established Patterns
- **DB-Migrations** werden in `app.py` `_migrate()` inline ausgeführt (Phase 4.7.1 Pattern). Neue Spalten via `ADD COLUMN IF NOT EXISTS`-Äquivalent in SQLite. Alembic wird im Repo NICHT genutzt.
- **Profile-Daten als JSON-String** in `profiles.daten` TEXT-Spalte — neue Felder über Profile-Editor-Form + JSON-Merge in `routes/profiles.py`. `branche` bleibt separate Column (Legacy).
- **Blueprint-basiertes Routing** pro Domain (`auth_bp`, `profiles_bp`, `app_routes_bp`). Neue Endpoints (falls nötig) als `profiles_bp`-Erweiterung oder neues `ewb_bp`.
- **CSS-Tokens** in `nerve.css` — Tooltip-UI nutzt existing `var(--n-border)`, `var(--n-accent)`, Card-Styles (Phase 7 MAIN DESIGN).
- **i-Button-UI** es gibt noch kein etabliertes i-Button-Pattern — Phase 08 legt dieses Pattern an. Positionsierung neben jedem Label in der Profil-Editor-Sektion.
- **Migration-Idempotenz** `INSERT OR IGNORE` für Seed-Daten (Phase 4.9 Pattern). Relevant für neue `prompt_versions`-Zeilen mit v2-Variante.

### Integration Points
- `ObjectionEvent.success` Migration → `app.py` `_migrate()` + `database/models.py` Column-Def.
- PreCall-Anrede-Overlay → `templates/app.html` oder `static/pip-launcher.js` (Phase 06.5-PreCall-Flow).
- `conversation_logs.anrede` → `database/models.py` + `_migrate()` + `routes/app_routes.py` Session-Start-Hook.
- Profil-Editor neue Felder → `templates/profile_editor.html` + `static/profile_editor.js` + `routes/profiles.py` POST-Handler (JSON-Merge).
- `branche`-Enum-Migration → Data-Migration SQL, heuristisches Mapping Freitext → Enum.
- Tooltip-System → neues Partial-Template `templates/_tooltip.html` + `static/nerve.css` Tooltip-Styles.
- Beispiel-Profil-Modal → neues Modal-Template + `profile_editor.html`-Link + seed-daten (separater JSON oder Hardcoded in Template).
- `services/prompt_pipeline.py` (NEU) → wird von `services/claude_service.py` aufgerufen, nicht umgekehrt.
- Router-Integration in `services/claude_service.py` → EWB-Prompt-Funktion ruft `resolve_prompt_version('ewb', user_id)` → lädt Prompt-Text aus `prompt_versions` WHERE `module='ewb' AND version=resolved`.
- Post-Call-Rating-UI → `templates/session_detail.html` (Phase 07.1-Seite) — neue Sektion nach bestehenden 14 Sektionen ODER im Training-Abschluss-Flow.

### Concerns / Risiken
- **`branche`-Migration** kann User-Daten zerstören wenn Freitext nicht sauber gemappt wird. Strategie: Originaltext in `branche_kontext` konservieren, Enum-Wert auf `sonstiges` setzen wenn Mapping unklar. Planner dokumentiert Heuristik explizit.
- **A/B-Test-Validität bei Solo-User** André ist der einzige belastbare Test-User in Pre-Launch. `user_id % 2`-Routing landet ihn auf 1 fixe Variante → für Cross-User-A/B-Vergleich reicht das nicht. **Deswegen ENV-Override als primäres UAT-Werkzeug** (D-24): André schaltet manuell zwischen v1 und v2, bewertet beide. Echte A/B-Telemetrie entsteht erst mit EA-Usern nach Launch.
- **FT-Logging-Schreib-Pfad** synchron in der Haiku-Response-Funktion. Bei Router-Resolve + Prompt-Load kommt ein DB-Round-Trip hinzu. Planner sollte Caching (profile-scoped oder request-scoped) prüfen.
- **Tooltip-Content-Qualität** Anti-Pattern-Regel (D-20) ist nicht algorithmisch prüfbar. Claudian-Review vor Launch (D-21) ist der einzige Gate — entsprechend Review-Zeit einplanen.

</code_context>

<specifics>
## Specific Ideas

- EWB-Prompt-Template aus Vault (Teil 4 in `NERVE Phase 08 EWB-Qualität.md`) ist die konkrete Blaupause für v2-Prompt: Kontext-Block mit Produkt/Zielgruppe/USPs/branche_kontext/Anrede/Stil, 4 Bausteine (Anker/Reframe/Beweis/Überleitung), harte Regeln (45 Wörter max, niemals apologetisch, Anrede konsequent).
- Benefit-Framing-Text für POLISH-55-UI (D-03) ist wortwörtlich festgelegt — in Plan kein Paraphrasieren.
- "Eigener Stil"-Textfeld im `ton`-Select (D-10) ist Flex-Escape, kein Default — erscheint nur wenn User keinen der 4 Stile wählt.
- Post-Call-Rating-Buttons (D-04): keine Submit-Aktion, Klick speichert sofort (UX-Regel).
- 3-Block-Tooltip-Pattern (D-16) **muss** alle 3 Blöcke enthalten — keine Kurz-Tooltips ohne "Nicht verwechseln mit". Das ist der Kern der Qualitäts-Verbesserung.
- Training-Modus-Szenarien A/B/C (D-34) nutzen bestehende Training-Infrastruktur (Phase 4.9-Szenarien-Tabelle). Planner prüft ob neue Szenarien als System-Scenarios (`erstellt_von=NULL`) angelegt werden oder User-Scenarios für André.
- Naming-Präferenz (D-45): `prompt_pipeline.py` — Planner darf abweichen wenn Repo-Konvention dagegen spricht.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 08.5 Question-Answering-Loop** — eigene Phase, nutzt Phase-08-Utils (`services/prompt_pipeline.py`). Scope inkl. `profile_faqs`-Tabelle, Embedding-Match, Tabu-Begriffe, Frage-Klassifikator.
- **Phase 07.5 EWB-Feed-Redesign** — nach 08+08.5. Feed muss beide Antwort-Typen (EWB + Q&A) tragen.
- **Phase 4.19 Transkript-Persistierung** — Voraussetzung für KI-Inferenz des POLISH-55-Ratings. Bis dahin: Rating bleibt User-manuell.
- **KI-Inferenz für EWB-Rating** — ergänzt POLISH-55-UI ab Phase 4.19. User bestätigt/korrigiert mit einem Klick.
- **Painpoint-Extractor-Prompt-Rewrite (POLISH-24)** — kann als optionale Wave 2b in Phase 08 mitgenommen werden, sonst eigene Phase.
- **Claude-Classifier für Vorlesbar-Bewertung** — erst wenn manueller Aufwand Bottleneck wird (skaliert nicht über EA hinaus relevant).
- **Inter-Rater-Reliability-Tooling** — ab Team/Coach-Skalierung (Phase 4.15+).
- **Onboarding-Wizard-Integration der neuen Profil-Felder** — Phase 4.16.1 Scope (mindestens Anrede, Stil, 1 eigenes Gegenargument).
- **Admin-UI zum Live-Umschalten der aktiven Prompt-Varianten** — erst nach Launch, wenn A/B-Test-Zyklen enger getaktet sind.
- **Phase 08 baut noch keine Onboarding-Integration** — neue Felder erscheinen nur im Profil-Editor, nicht im Wizard.

### Reviewed Todos (not folded)
Keine Todo-Matches aus `todo match-phase 08` in diesem Discuss-Run aufgetaucht (Tool-Output leer).

</deferred>

---

*Phase: 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration*
*Context gathered: 2026-04-22*
