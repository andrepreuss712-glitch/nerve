# Phase 08: EWB-Qualität & Profil-Tiefe — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `08-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 08-ewb-qualit-t-profil-tiefe-launch-kritische-prompt-iteration
**Areas discussed:** A/B-Infrastruktur, Quality-Gate-Messung, Test-Datensatz, Phase-08.5-Architektur-Check

---

## A/B-Test-Infrastruktur

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `ft_objection_events` + Routing per `user.id` mod 2 | Keine neue Tabelle. `prompt_versions` bekommt mehrere `is_active`-Einträge pro `module`. Router picks v1/v2 per user_id%2 deterministisch. | |
| Reuse + Admin-Override per ENV-Var | Gleich wie oben, aber Variante global via ENV `PROMPT_EWB_VERSION=v2` steuerbar. Kein Random-Routing. | |
| Neue Tabelle `ft_prompt_ab_results` | Dedizierte Aggregations-Tabelle, täglich via Cron aus `ft_objection_events` aggregiert. | |
| **Kombination 1 + 2 (User-Choice)** | Variante 1 als Default (`user_id % len(active_variants)`) PLUS ENV-Override `PROMPT_EWB_VERSION_OVERRIDE` als Safety-Net. ENV-Var = FIRST-CHECK. Skalierbar auf 3+ Varianten. | ✓ |

**User's choice:** Kombination 1+2 (deterministisches Routing + ENV-Override).
**Notes:** KISS — keine neue Tabelle bei 50 EA. Deterministisches User-Erlebnis. Emergency-Rollback ohne Code-Deploy. UAT-Kontrolle. Skalierbar via `len(active_variants)`. Router-Logik: ENV-Var als FIRST-CHECK, erst wenn leer mod-Routing. ENV-Var-Name in `.env.example` + `deploy/nerve.service` dokumentieren.

---

## Quality-Gate-Messung

### Messung-Methode

| Option | Description | Selected |
|--------|-------------|----------|
| **Manuell Pre-Launch + POLISH-55 Post-Launch** | André bewertet binär ~100 EWBs aus 20 Test-Calls (~17min). POLISH-55-Success-Rate als ongoing Signal. | ✓ |
| Nur Manuell Pre-Launch | Keine Post-Launch-Monitoring-Metrik. | |
| Automatischer Claude-Classifier | Haiku-grader pro EWB. LLM-Varianz verzerrt Messung. | |

**User's choice:** Manuell + POLISH-55 (implizit aus Begründung der weiteren Details).

### EWB-Quality-Score Komposition

**User's specification (keine Alternativen zur Auswahl gestellt):**

Skala 0-100:
- `klingt_wie_Mensch` (Gewicht 1x)
- `keine_Halluzination` (Gewicht 2x — größtes Launch-Risiko)
- `trifft_Einwand` (Gewicht 1x)
- Formel: `(klingt + 2*keine_halluzination + trifft_einwand) / 4 * 100`
- Vorlesbar-Gate: ≥80% der bewerteten EWBs haben Score ≥80

### Varianz-Range-Definition

**User's specification:** `range(max − min) < 30` über 5 Repeats pro Szenario in ALLEN 3 Szenarien.

**Outlier-Handling:** Range 28-32 manuell prüfen (Bug-Outlier vs. echte Varianz). Outlier mit Dokumentation entfernen, Recompute über n=4 erlaubt. Kein blindes Pass/Fail.

**Post-Launch-Skalierung:** Ab 20+ Datenpoints pro Szenario zusätzlich auf `σ < 15` umschalten.

**Parallel-Metrik:** Hero-Score wird parallel getrackt, aber NICHT als Gate. Divergenz = Signal für Score-Kalibrierung (Phase 07.3 Scope).

---

## Test-Datensatz

| Option | Description | Selected |
|--------|-------------|----------|
| Training-Modus + 2-3 echte Cold-Calls | Varianz: 15 Training-Sessions. Vorlesbar: ~75 Training-EWBs + ~15 echte. 83/17-Mix. | |
| Nur Training-Modus | Rein synthetisch, reproduzierbar, keine Real-World-Validation. | |
| Training-Modus + Backfill bestehender Sessions | POLISH-55-Retrospektiv-Rating an Vertriebler. Recall-Bias-Risiko. | |
| **Modifiziertes Option 1 (User-Choice)** | Varianz: NUR Training (A "Easy", B "Profil-reich", C "Edge-Case"). Vorlesbar: 60/40 Training/Real-World. Bonus-Backfill-Email post-Launch. | ✓ |

**User's choice:** Modifiziertes Option 1.

**Notes:**
- **Varianz-Gate**: 3 Szenarien × 5 Repeats, Szenario A="Easy" (Zu teuer + einfaches SaaS-Profil), B="Profil-reich" (voll mit `branche_kontext` + `eigene_formulierungen`), C="Edge-Case" (Multi-Einwand "Zu teuer" → "Haben schon was ähnliches").
- **Vorlesbar-Gate**: 60/40 statt 83/17 — Real-World-Validierung ist genau hier wichtig. Training-Bot ist nice-guy-Claude, echte Kunden unberechenbarer.
- **Zeitaufwand André**: ~4h verteilt über 2-3 Tage (15 Training ~2h, 5 echte Calls ~1h, 100 EWBs bewerten ~17min, Setup ~30min).
- **Bonus-Quelle**: Freiwilliger Email-Backfill-Call an EA-User post-Launch. Nicht als Gate.
- **Rating-Verantwortung**: Initial alles André. Inter-Rater-Reliability erst ab Team/Coach (Phase 4.15+).

---

## Phase-08.5-Architektur-Check

| Option | Description | Selected |
|--------|-------------|----------|
| **Generic Utils + EWB-Pipeline separat** | `services/prompt_pipeline.py` als Utils-Layer (`build_profile_context`, `resolve_prompt_version`, `log_pipeline_event`) + `services/ewb_pipeline.py` für EWB-spezifische Bausteine. Phase 08.5 kann `qa_pipeline.py` parallel legen. | ✓ |
| EWB-Monolith in Phase 08, Refactor in 08.5 | EWB-first pragmatisch, Abstraktion in 08.5. Risiko: Refactoring in gelocktem Pfad. | |
| Vollabstrakte Plugin-Pipeline | Baustein-Registry, konfigurierbare Pipeline pro Module. Over-Engineering bevor Phase 08.5 spezifiziert. | |

**User's choice:** Generic Utils + EWB-Pipeline separat.

**User's Scope-Abgrenzung:**

**IN `services/prompt_pipeline.py` (Shared Utils, Phase 08):**
- `build_profile_context(user_id, mode)` — Profil-Kontext-Block (Produkt, USPs, `branche`, `branche_kontext`, `stil`, `eigene_formulierungen`, Anrede aus Session)
- `resolve_prompt_version(module, user_id)` — A/B-Routing `user_id % len(active_variants)` + ENV-Override
- `log_pipeline_event(event_type, module, data)` — strukturiertes Logging-Interface, modul-agnostisch

**NICHT in Utils (bleibt in `ewb_pipeline.py` bzw. `qa_pipeline.py`):**
- Baustein-Logik (Anker/Reframe/Beweis/Überleitung für EWB, FAQ-Match + Tabu-Filter für Q&A)
- Prompt-Assembly
- Output-Parsing

**Bewusst NICHT in Phase 08 (kommt in 08.5):**
- `apply_tabu_filter()` — Kann als leere Stub-Funktion vorgesehen werden, oder komplett später. Planner entscheidet.

**Test-Strategie:**
- Unit-Tests für Shared-Utils (`build_profile_context`, `resolve_prompt_version`)
- Integration-Tests im Modul-Layer (EWB end-to-end)
- Phase 08.5 kann Shared-Unit-Tests übernehmen

**Naming:** `prompt_pipeline.py` als Default. Bike-Shedding — Planner darf abweichen.

**Aufwand-Kalkül:** +1h Design in Phase 08, −4-6h in Phase 08.5 = Netto 3-5h Ersparnis. Vermeidet Refactoring in gelocktem Pfad (CLAUDE.md Abrieb-Prinzip).

---

## Claude's Discretion

Vom User explizit delegiert an den Planner:
- Migrations-Mechanismus für `ObjectionEvent.success`-Nullable (konsistent zum Repo-Pattern).
- Default-Wert für `branche`-Enum.
- `prompt_versions`-Spalten-Erweiterung für A/B (`ab_weight` vs. `is_default` vs. `ab_pool`).
- Struktur des Rating-Templates (Google-Sheet, Markdown, Admin-Tool).
- Szenario-Definitions-Format für A/B/C.
- Entscheidung `apply_tabu_filter()`-Stub in Phase 08 vs. komplett später.
- Naming `prompt_pipeline.py` vs. Alternative.

---

## Deferred Ideas

Alle Ideen die im Gespräch auftauchten aber nicht in Phase 08 gehören — siehe `<deferred>`-Sektion in `08-CONTEXT.md`:
- Phase 08.5 Question-Answering-Loop
- Phase 07.5 EWB-Feed-Redesign
- Phase 4.19 Transkript-Persistierung
- KI-Inferenz für EWB-Rating (post 4.19)
- Painpoint-Extractor-Prompt-Rewrite POLISH-24 (optional Wave 2b oder eigene Phase)
- Claude-Classifier für Vorlesbar-Bewertung
- Inter-Rater-Reliability-Tooling
- Onboarding-Wizard-Integration neuer Profil-Felder (Phase 4.16.1)
- Admin-UI für Live-Prompt-Varianten-Umschalten

---

## Prozess-Anmerkung (Discuss-Session)

Der Checkpoint-Schreib-Schritt aus dem `discuss-phase.md`-Workflow wurde initial übersprungen und erst nach User-Rückfrage nachträglich geschrieben. State wäre bei Clear verloren gewesen. Für zukünftige Discuss-Phase-Läufe: `08-DISCUSS-CHECKPOINT.json` nach JEDER resolved Area persistieren — nicht erst am Ende. Regel steht in `discuss-phase.md` §"Incremental checkpoint — save after each area completes", wurde hier zunächst missachtet. User-Interventions-Hinweis angenommen.
