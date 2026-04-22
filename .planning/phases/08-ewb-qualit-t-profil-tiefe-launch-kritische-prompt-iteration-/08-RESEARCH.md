# Phase 08: EWB-Qualität & Profil-Tiefe — Research

**Researched:** 2026-04-22
**Domain:** EWB-Prompt-Iteration, Profil-Schema-Erweiterung, POLISH-55 Messinfrastruktur, A/B-Routing, Quality-Gates
**Confidence:** HIGH (alle kritischen Claims durch direkte Code-Inspektion verifiziert)

## Summary

Phase 08 hat drei ineinandergreifende Scope-Blöcke, deren Implementierungs-Kritikalität sich extrem unterscheidet. Die Top-3-Risiken sind: **(1)** die SQLite-Migration für `ObjectionEvent.success Boolean NOT NULL → NULLABLE` hat **keinen bestehenden Präzedenzfall im Repo** — alle bisherigen Migrationen nutzen `ADD COLUMN IF NOT EXISTS`, aber SQLite unterstützt `ALTER COLUMN` nicht; der Planner MUSS hier das Table-Rebuild-Pattern (CREATE new → COPY → DROP old → RENAME) definieren, UND der POLISH-38.1-Alt-Daten-Reset ist **destruktiv** und braucht Rollback-Plan. **(2)** Die A/B-Routing-Integration läuft **in jedem Haiku-Call im Live-Loop** (pro EWB-Click, pro auto-einwand, pro streaming-token) — das bereits existierende `_ACTIVE_PROMPT_CACHE` (module-level dict in `claude_service.py` line 97) wurde NICHT mit A/B-Semantik entworfen und muss erweitert werden: module+user_id als Key, sonst werden alle User auf dieselbe Variante geroutet. **(3)** Der profile_editor.html macht einen **wholesale JSON-Replace**, NICHT einen JSON-Merge (line 134 in routes/profiles.py: `p.daten = daten_json`); das Frontend-JS (`buildAndSubmit()` in profile_editor.html line 953) baut den kompletten JSON neu auf — unbekannte Keys in `profiles.daten` werden bei jedem Save **überschrieben**. Neue Felder müssen sowohl im JS-Builder ALS AUCH im Populate-Handler ergänzt werden, sonst gehen sie beim zweiten Save verloren.

**Primary recommendation:** Wave 1 (Foundation): Training-Prompt-Gap-Analyse + Nullable-Migration + `services/prompt_pipeline.py`-Skeleton. Wave 2 (Features): Profil-Schema + Tooltip-System + PreCall-Anrede-Override + v2-Prompt + Router-Integration. Wave 3 (Measurement): Rating-UI + A/B-Auswertungs-Query + Quality-Gate-Template. Wave 4 (Quality-Gate-Messung durch André). **Kein Wave ist skip-fähig; alle sind launch-blocking.**

## User Constraints (from CONTEXT.md)

### Locked Decisions

**POLISH-55 3-State-Semantik:**
- **D-01:** `ObjectionEvent.success` von `Boolean NOT NULL` → `Boolean NULLABLE` (SQLite-Migration via ALTER-Replay falls nötig). 3-State-Modell: `TRUE` = Erfolg, `FALSE` = Kein Erfolg, `NULL` = Unbekannt/Überspringen.
- **D-02:** Alt-Daten aus POLISH-38.1 (Boolean-Werte aus "technisch erfolgreich") werden via Migration auf NULL gesetzt. Migration-Marker dokumentieren (z.B. `migration_v08_01_reset_success_polish38_1`).
- **D-03:** Post-Call-UI: Rating-Block im bestehenden Post-Call-Screen (`/session/<id>` oder Training-Abschluss), freiwillig, Benefit-Framing wortwörtlich.
- **D-04:** 3 Buttons pro EWB — "Erfolg" (TRUE), "Kein Erfolg" (FALSE), "Überspringen" (NULL). Kein Submit-Button, Klick speichert sofort.
- **D-05:** A/B-Test-Auswertungen filtern strikt `WHERE success IS NOT NULL`.
- **D-06:** KI-Inferenz explizit OUT OF SCOPE für Phase 08 (kommt ab Phase 4.19).

**Profil-Felder:**
- **D-07:** NEU `eigene_formulierungen` (Textarea multi).
- **D-08:** NEU `beweise` (Textarea multi).
- **D-09:** UMBAU `branche` Freitext → Enum: `saas_b2b`, `maschinenbau`, `versicherung`, `finanzprodukte`, `immobilien`, `coaching`, `beratung`, `sonstiges`.
- **D-10:** UMBAU `ton` Freitext → Select: `Direkt/Klartext`, `Beratend/Sanft`, `Enthusiastisch/Begeistert`, `Analytisch/Zahlenorientiert` + "Eigener Stil"-Flex.
- **D-11:** ERWEITERUNG `branche_kontext` (Textarea) unter `branche`.
- **D-12:** UMBENENNEN `zusatz` → Label "Spezielle Anweisungen an NERVE" (DB-Key bleibt).
- **D-13:** "Typische Gegenargumente" existiert als `einwaende[].gegenargument` — nur Onboarding prominenter (Phase 4.16.1).
- **D-14:** PreCall-Override Anrede in `conversation_logs.anrede` (String, nullable), Profil-`ki_ansprache` als Default.
- **D-15:** Prompt-Integration Anrede: harter Constraint "Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie."

**Tooltip-Qualität:**
- **D-16:** 3-Block-Pattern: (1) Was rein soll, (2) Beispiel, (3) Nicht verwechseln mit.
- **D-17:** Abgrenzungs-Matrix für ~20 Tooltips (Liste in CONTEXT.md).
- **D-18:** i-Button ≥16×16px, sichtbarer Hover-State.
- **D-19:** Beispiel-Profil-Modal Read-Only.
- **D-20:** Kritische Content-Regel: keine NERVE-spezifischen, André-persönlichen oder echten-Firmen-Beispiele. Fiktive Platzhalter only.
- **D-21:** Launch-Gate Claudian-Review-Pass.

**A/B-Test-Infrastruktur:**
- **D-22:** Keine neue Tabelle. Reuse `ft_objection_events.prompt_version` + `ft_assistant_events.prompt_version`.
- **D-23:** Routing deterministisch `user_id % len(active_variants)`.
- **D-24:** `PROMPT_EWB_VERSION_OVERRIDE=v2-modular` als FIRST-CHECK-Override.
- **D-25:** ENV-Var in `.env.example` und `deploy/nerve.service` dokumentieren.
- **D-26:** `prompt_versions`-Schema erweitern — mehrere Zeilen pro `module` mit `is_active=1`, plus zusätzliche Spalte (`ab_weight` oder `is_default`).

**Quality-Gate:**
- **D-27:** EWB-Quality-Score: `(klingt_wie_Mensch + 2 * keine_Halluzination + trifft_Einwand) / 4 * 100`, Gate ≥80% mit Score ≥80.
- **D-28:** Varianz-Gate `range(max − min) < 30` über 5 Repeats × 3 Szenarien, basiert auf `conversation_logs.gesamt_score`.
- **D-29:** Outlier-Handling bei Range 28-32 manuell.
- **D-30:** Pre-Launch manuell durch André, 100 EWBs × ~10s.
- **D-31:** Post-Launch Admin-Dashboard-Card.
- **D-32:** Skalierungs-Pfad `σ < 15` ab 20+ Datenpoints.
- **D-33:** Hero-Score parallel, NICHT als Gate.

**Test-Datensatz:**
- **D-34:** Varianz-Gate NUR Training-Modus. 3 Szenarien × 5 Repeats. Szenarien A (Easy), B (Profil-reich), C (Edge-Case Multi-Einwand).
- **D-35:** Vorlesbar-Gate 60/40 Training/Real-World-Mix. 100 EWBs total.
- **D-36:** Begründung 60/40 statt 83/17.
- **D-37:** Zeitaufwand ~4h verteilt über 2-3 Tage.
- **D-38:** Bonus Freiwilliger Backfill-Rating post-Launch.
- **D-39:** Initial alle Ratings durch André.

**Phase-08-Pipeline-Architektur:**
- **D-40:** NEUES Modul `services/prompt_pipeline.py` mit `build_profile_context()`, `resolve_prompt_version()`, `log_pipeline_event()`.
- **D-41:** NEUES Modul `services/ewb_pipeline.py` ruft Shared-Utils, EWB-spezifische Bausteine.
- **D-42:** NICHT in Phase 08: `apply_tabu_filter()`, `profile_faqs`, Frage-Klassifikator, Embedding-Match.
- **D-43:** Unit-Tests für Shared-Utils, Integration-Tests im Modul-Layer.
- **D-44:** Aufwand +~1h Design, −4-6h in Phase 08.5.
- **D-45:** Naming `services/prompt_pipeline.py` — alternativen akzeptabel.

**Wave 1 Gap-Analyse:**
- **D-46:** Training-Prompt-Gap-Analyse als FIRST ACTION in Wave 1.
- **D-47:** Active-Listening-Block gegen Inkonsistenz-Muster (POLISH-35/36/37).
- **D-48:** POLISH-24 Painpoint-Extractor optional Wave 2b.

### Claude's Discretion

- Migrations-Mechanismus für `ObjectionEvent.success`-Nullable (SQLite ALTER-Replay vs. neue Migration-Infrastruktur) — Planner wählt konsistent zum Repo-Pattern.
- Default-Wert für `branche`-Enum (SaaS_B2B als Default oder NULL erlauben?) — Planner entscheidet basierend auf Profil-Editor-UX.
- Exakte Spalten-Semantik für A/B-Auswertung in `prompt_versions` (z.B. `ab_weight`, `is_default`, `ab_pool`) — Planner entscheidet mit Researcher.
- Struktur des EWB-Quality-Rating-Templates (Google-Sheet vs. lokale Markdown-Datei vs. kleines Admin-Tool) — Planner wählt leichtestes Format.
- Szenario-Definitions-Format für die 3 Test-Szenarien A/B/C (Seed-SQL, Training-Szenario-Tabelle, Markdown-Spec) — Planner wählt pragmatisch.

### Deferred Ideas (OUT OF SCOPE)

- Phase 08.5 Question-Answering-Loop — eigene Phase, nutzt Phase-08-Utils.
- Phase 07.5 EWB-Feed-Redesign — nach 08+08.5.
- Phase 4.19 Transkript-Persistierung — Voraussetzung für KI-Inferenz des POLISH-55-Ratings.
- KI-Inferenz für EWB-Rating — ergänzt POLISH-55-UI ab Phase 4.19.
- Painpoint-Extractor-Prompt-Rewrite (POLISH-24) — optional Wave 2b oder eigene Phase.
- Claude-Classifier für Vorlesbar-Bewertung.
- Inter-Rater-Reliability-Tooling.
- Onboarding-Wizard-Integration der neuen Profil-Felder — Phase 4.16.1 Scope.
- Admin-UI zum Live-Umschalten der aktiven Prompt-Varianten — post-Launch.
- Onboarding-Integration — neue Felder erscheinen nur im Profil-Editor, nicht im Wizard.

## Project Constraints (from CLAUDE.md)

**Bindende Regeln aus `./CLAUDE.md`:**

1. **Stack:** Flask + Vanilla JS — **keine React-Migration**, keine Framework-Wechsel.
2. **Kosten Live:** **Sonnet MUSS raus aus dem Live-Loop** — nur Haiku für alles Live. Sonnet nur Post-Call. (D-26 A/B-Routing-Integration MUSS Haiku bleiben.)
3. **DSGVO:** Server in Deutschland (Hetzner), kein wörtliches Mitschneiden default.
4. **Umlaut-Regel (zweischneidig):**
   - **User-facing Text** (HTML-Content, Labels, Buttons, data-search/data-tip-Attribute, JS-alert-Strings): **echte Umlaute** ä/ö/ü/ß. Gilt für **alle Tooltip-Inhalte**.
   - **Code-Identifier** (DB-Spalten, Dict-Keys, Jinja-Expressions, JS-Vars/Object-Keys, HTML-IDs/Classes, URL-Slugs): **ASCII-Pflicht** ae/oe/ue/ss. Gilt für die **6 neuen Profil-Feld-Keys** (`eigene_formulierungen`, `beweise`, `branche_kontext`, `ton`, `branche`, bereits-existierend `zusatz`) und die **Enum-Werte** (`saas_b2b`, `maschinenbau`, `versicherung`, `finanzprodukte`, `immobilien`, `coaching`, `beratung`, `sonstiges`).
5. **GSD-Workflow:** Keine direkten Repo-Edits außerhalb GSD-Commands.
6. **Git-Regel:** Nach Phase-Ende `git push origin main`.

## Phase Requirements

Phase 08 hat noch keine formalen REQ-IDs in REQUIREMENTS.md. Das CONTEXT.md D-01 bis D-48 sind die bindende Spec. Der Planner sollte **abgeleitete Requirement-IDs** einführen (Vorschlag: `EWB-01` bis `EWB-20`) und in REQUIREMENTS.md nachtragen.

| Vorschlag-ID | Description | Research Support |
|----|-------------|------------------|
| EWB-01 | 3-State Behandelt-Semantik (NULL/TRUE/FALSE) | §2: Nullable-Migration + §11: Rating-UI-Anchor |
| EWB-02 | Migrations-Reset Alt-Daten POLISH-38.1 | §2: Destruktiv, Rollback-Plan dokumentieren |
| EWB-03 | Post-Call-Rating-UI im Session-Detail | §11: session_detail.html Insertion-Point |
| EWB-04 | 6 Profil-Felder (neu/umbau/erweitert/umbenannt) | §6: Wholesale-JSON-Replace beachten |
| EWB-05 | branche Freitext → Enum mit Heuristik-Migration | §7: Mapping-Tabelle + Fallback-Rule |
| EWB-06 | PreCall-Anrede-Override in conversation_logs.anrede | §8: Override-Resolution-Chain |
| EWB-07 | Tooltip-System 3-Block-Pattern | §9: Existierendes `tip-icon` Pattern erweitern |
| EWB-08 | Beispiel-Profil-Modal Read-Only | §9: Neue Modal-Komponente |
| EWB-09 | A/B-Routing deterministisch + ENV-Override | §5: `_ACTIVE_PROMPT_CACHE` erweitern |
| EWB-10 | prompt_versions Schema-Erweiterung | §4: `ab_weight` vs. `is_default` |
| EWB-11 | services/prompt_pipeline.py (Shared-Utils) | §1/§5: build_profile_context, resolve_prompt_version |
| EWB-12 | services/ewb_pipeline.py (Modul-spezifisch) | §1: EWB-Bausteine + Prompt-Assembly |
| EWB-13 | v2-Prompt mit Baustein-Struktur | §1: Gap-Analyse Training→Live |
| EWB-14 | Active-Listening-Block (D-47) | §1: Ergänzt Baustein-Struktur |
| EWB-15 | 3 Test-Szenarien (A/B/C) für Varianz-Gate | §10: Seeding in training_scenarios |
| EWB-16 | EWB-Quality-Rating-Template | §10: Admin-Page vs. Markdown |
| EWB-17 | A/B-Auswertungs-SQL-Query | §3: Join-Path FtObjectionEvent→ObjectionEvent |
| EWB-18 | Unit-Tests resolve_prompt_version | §12: pytest-Infrastruktur vorhanden |
| EWB-19 | Integration-Tests EWB end-to-end | §12: Test-Client-Fixture verfügbar |
| EWB-20 | Launch-Gate Claudian-Tooltip-Review | §9: Manueller Check vor Deploy |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| EWB-Prompt-Assembly | Backend (`services/`) | — | Python generiert komplette Prompts, Haiku ist reiner Stateless-Call |
| A/B-Routing | Backend (`services/prompt_pipeline.py`) | — | Deterministic Hash auf `user_id` — darf NIE Client-Side sein (Manipulation) |
| `prompt_versions`-Storage | Database | Backend (Cache) | Single Source of Truth, mit Module-Level-Cache |
| Profile-JSON-Editing | Frontend (profile_editor.html JS) | Backend (profiles.py POST) | Wholesale-Replace, JS baut komplett neu |
| Tooltip-UI | Frontend (CSS + vanilla JS) | — | `tip-icon` + `g-tip` Pattern bereits etabliert in profile_editor.html |
| Post-Call-Rating | Frontend (session_detail.html) | Backend (neuer `/api/ewb/<id>/rate` POST) | Klick → Socket/fetch → ObjectionEvent.success UPDATE |
| PreCall-Anrede-Override | Frontend (pip-launcher.js) | Backend (conversation_logs.anrede column) | Client-Wahl → bei session_start im ft_call_sessions/conversation_logs speichern |
| `branche`-Enum-Migration | Backend (data-migration SQL) | — | Einmalige Datentransformation, idempotent |
| EWB-Quality-Rating-Template | Backend (`/admin/ewb-rating` Page) | Frontend (read-only form) | Solo-User-Tool, Admin-only |
| Training-Szenarien-Seed | Backend (`_migrate()` Seed-Block) | — | `INSERT OR IGNORE` Pattern (bereits für personality_types etabliert) |

## Focus Area 1: Training-EWB-Prompt-Gap-Analyse (D-46)

**Quellen:**
- Live-EWB-Prompt: `services/claude_service.py` line 9 (`SYSTEM_PROMPT_BASE`) + line 258 (`_build_system_prompt()`) + line 633 (`analysiere_mit_claude`) + line 664 (`analysiere_mit_claude_streaming`).
- Training-Persona-Prompt: `services/training_service.py` line 518 (`TRAINING_PERSONA_PROMPT_BASE = KUNDEN_PROMPT_TEMPLATE`) + line 568 (`build_customer_prompt`).

**Wichtige Unterscheidung vorweg:** Die Vault-Erkenntnis "Training-Prompt ist strukturell besser als Live-EWB-Prompt" betrifft nicht den Kunden-Persona-Prompt (der simuliert einen Kunden), sondern die **Kontext-Fülle**, die ins Prompt fließt. Der Live-EWB-Prompt in `_build_system_prompt()` ist IM CODE bereits relativ kontextreich (Zeilen 273-393); die Lücke ist eher ein **Baustein-Struktur-Problem** als ein Kontext-Problem. Der Planner sollte die Vault-Annahme mit diesem Codebase-Befund kalibrieren.

**Gap-Matrix: Live-EWB-Prompt vs. Vault-Template (aus CONTEXT `<specifics>`):**

| Element | Live-EWB-Prompt (IST) | Vault-Template v2 (SOLL) | Gap |
|---------|----------------------|--------------------------|-----|
| Produkt-Beschreibung | ✓ line 275-277 (`basis['produkt']`) | ✓ | keine |
| USPs | ✓ line 280-281 (`basis['usps']`) | ✓ | keine |
| Zielgruppe (Alter/Beruf/Einkommen) | ✓ line 284-293 | ✓ | keine |
| `branche` (aktuell Freitext) | ✗ — NICHT im Prompt enthalten! | ✓ (Enum) | **KRITISCHE LÜCKE** — Profile.branche Column wird in System-Prompt gar nicht ausgewertet |
| `branche_kontext` | ✗ Feld existiert nicht | ✓ | neu (D-11) |
| `eigene_formulierungen` | ✗ Feld existiert nicht | ✓ | neu (D-07) |
| `beweise` | ✗ Feld existiert nicht | ✓ | neu (D-08) |
| Anrede (Du/Sie) | ✓ line 367 (`ki['ansprache']` als Beschreibung) | ✓ harter Constraint | **GAP** — aktuell nur `"Kundenansprache: Du (immer einhalten)"`, kein Wechsel-Verbot (D-15) |
| Baustein-Struktur (Anker/Reframe/Beweis/Überleitung) | ✗ Nur freies Gegenargument (max 2-3 Sätze) | ✓ 4 strukturierte Bausteine | **STRUKTUR-LÜCKE** — v1-Prompt kennt keine Bausteine |
| Active-Listening-Block | ✗ | ✓ (D-47, gegen POLISH-35/36/37) | neu |
| 45-Wort-Constraint | ✗ Aktuell "max 2-3 Sätze" | ✓ explicit Wortzahl | neu |
| Niemals-apologetisch-Regel | ~ Teilweise (line 25: `"Kein Fachjargon, keine Floskeln wie 'Ich verstehe vollkommen'"`) | ✓ explizit | verstärken |
| Lernkarten-Matching | ✓ line 64-68 (optional felder) | — | Live-only, bleibt |
| Gegenfrage-Pflicht | ✓ line 27-30 | ✓ | keine |

**Kritischer Befund:**
1. **`profile.branche`-Column (legacy, line 126 in models.py) wird vom System-Prompt aktuell NICHT gelesen.** Das heißt: selbst der Freitext-Branchen-Wert der heute in der DB liegt fließt NICHT in den Live-Prompt ein. D-11 (`branche_kontext` als Textarea) wird den Großteil der strukturellen Lücke schließen; `_build_system_prompt()` MUSS erweitert werden um beide Felder (`branche`-Enum + `branche_kontext`) zu lesen.
2. **Die Baustein-Struktur (Anker / Reframe / Beweis / Überleitung)** ist ein **komplett neuer Prompt-Stil**, nicht nur eine Erweiterung. v2 muss als eigene `prompt_versions`-Zeile gebaut werden, v1 bleibt als Fallback.
3. **Training-Bewertung-Prompt (`bewertung_mit_claude` in training_service.py)** ist ein **separater** Prompt für Post-Call-Scoring — nicht verwechseln mit dem Live-EWB-Pfad. Phase 08 betrifft den Live-EWB-Prompt, nicht den Training-Scoring-Prompt.

**Output für Planner:** Wave 1 Task 1.1 = "Training-Prompt vs. Live-Prompt Kontext-Diff dokumentieren" kann entfallen — es gibt keinen Training-Live-Gap-Asymmetrie-Befund. Stattdessen: Task 1.1 = "**Profile-Feld → System-Prompt Wiring-Matrix**" (welche Profil-Felder das Live-Prompt heute liest vs. welche das v2-Prompt lesen soll). Das ist die wirkliche Gap-Analyse-Aufgabe.

## Focus Area 2: `ObjectionEvent.success` Nullable-Migration (D-01, D-02)

**Quellen:**
- `database/models.py` line 342-350 (ObjectionEvent):
  ```python
  class ObjectionEvent(Base):
      __tablename__ = 'objection_events'
      # ...
      success = Column(Boolean, default=False, nullable=False)  # ← nullable=False
      # ...
  ```
- `app.py` line 90-530 (`_migrate()`): Alle Migrationen folgen `ADD COLUMN IF NOT EXISTS`-Pattern via try/except. **KEIN bestehender Precedent für `ALTER COLUMN DROP NOT NULL`.**

**SQLite-Limitation (kritisch für Planner):**
SQLite unterstützt `ALTER TABLE ... ALTER COLUMN` **nicht**. Die offizielle SQLite-Doku gibt nur zwei Pfade:
1. **Table-Rebuild-Pattern** (bewährt, aber aufwändig):
   ```sql
   BEGIN TRANSACTION;
   CREATE TABLE objection_events_new (
       id INTEGER PRIMARY KEY,
       user_id INTEGER NOT NULL,
       org_id INTEGER,
       conversation_log_id INTEGER NOT NULL,
       einwand_typ VARCHAR(100) NOT NULL,
       success BOOLEAN,  -- ← hier nullable
       created_at DATETIME NOT NULL,
       FOREIGN KEY(user_id) REFERENCES users(id),
       FOREIGN KEY(org_id) REFERENCES organisations(id),
       FOREIGN KEY(conversation_log_id) REFERENCES conversation_logs(id)
   );
   INSERT INTO objection_events_new SELECT * FROM objection_events;
   DROP TABLE objection_events;
   ALTER TABLE objection_events_new RENAME TO objection_events;
   -- Indices neu anlegen falls vorhanden
   COMMIT;
   ```
2. **Pragmatischer Hack**: In SQLite ist "NOT NULL" nur am Column-DDL-Constraint aktiv. Wenn SQLAlchemy-Model auf `nullable=True` umgestellt wird, und der App-Code `success = None` setzt, **wird SQLite einen CHECK/NOT NULL Violation-Error werfen** — also geht diese Route nicht.

**Empfehlung an Planner (Rule 1 konsistent zu Repo):**
- **Table-Rebuild** als eigenen Migrations-Block in `_migrate()`, idempotent via `CREATE TABLE IF NOT EXISTS` + Column-Existenz-Check. Marker: `objection_events_v2_migrated_v08_01`. Mechanismus: Prüfe via `PRAGMA table_info(objection_events)` ob `success` nullable ist — nur wenn NOT NULL → Rebuild ausführen.
- **D-02 Alt-Daten-Reset** als **eigene** migration-step NACH Rebuild: `UPDATE objection_events SET success = NULL WHERE created_at < :polish_38_1_cutoff_ts`. Der Cutoff-Timestamp ist wichtig — NEUE Ratings (nach Launch dieser Migration) sollen nicht rückgängig gemacht werden.

**Rollback-Plan (muss der Planner dokumentieren):**
Die Migration ist **teilweise destruktiv**:
- **Table-Rebuild**: Reversibel (sauberer SQL-Swap, keine Daten verloren).
- **Alt-Daten-Reset (D-02)**: **Irreversibel** — die Boolean-Werte von POLISH-38.1 gehen verloren. Mitigationen: (a) Vor Migration DB-Backup erzwingen: `database/nerve.db` → `database/nerve.db.bak_pre_v08_01`. (b) Reset-Query loggen mit Vorher-Werten in `audit_log`.

**Planner-Entscheidung nötig:** SQLite-Table-Rebuild vs. neue Alembic-Infrastruktur? Das Repo nutzt NICHT Alembic (siehe `<code_context>` D-01). Empfehlung: **SQLite-Rebuild-Pattern inline in `_migrate()` konsistent mit bestehendem Stil.**

## Focus Area 3: FT-Logging Join-Key Mechanics (D-22)

**Quellen:**
- `database/models.py` line 438 (FtObjectionEvent): `ft_session_id = Column(Integer, ForeignKey('ft_call_sessions.id'), nullable=False)` — **NICHT direkt zu ConversationLog**.
- `database/models.py` line 381 (FtCallSession): `conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=True)`.
- `database/models.py` line 342 (ObjectionEvent): `conversation_log_id = Column(Integer, ForeignKey('conversation_logs.id'), nullable=False)`.
- `routes/app_routes.py` line 544-566: An `/api/beenden`-Ende wird `FtCallSession.conversation_log_id = conv.id` gesetzt (line 560).

**Join-Path (Research-Auftrag gelöst):**
```sql
-- Das CONTEXT.md D-22 nutzt `ft_session_id_derived` als Platzhalter.
-- Die tatsächliche Kette ist 3-stufig:
--   ft_objection_events.ft_session_id → ft_call_sessions.id
--   ft_call_sessions.conversation_log_id → conversation_logs.id
--   conversation_logs.id → objection_events.conversation_log_id
--
-- Plus: Match auf einwand_typ (ObjectionEvent) == objection_type (FtObjectionEvent)

SELECT
    ftoe.prompt_version,
    COUNT(*) AS n,
    AVG(CASE WHEN oe.success = 1 THEN 1.0 ELSE 0.0 END) AS success_rate
FROM ft_objection_events ftoe
JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
JOIN objection_events oe
    ON oe.conversation_log_id = fcs.conversation_log_id
   AND oe.einwand_typ = ftoe.objection_type
WHERE oe.success IS NOT NULL
GROUP BY ftoe.prompt_version;
```

**Kritische Caveats für Planner:**
1. **`fcs.conversation_log_id` ist NULLABLE**: Wenn die Session nie durch `/api/beenden` lief (Browser-Tab geschlossen, Crash), bleibt `conversation_log_id = NULL` und die Join-Row wird stillschweigend filtered out. Das verzerrt A/B-Ergebnisse geringfügig (fehlt aber aus beiden Varianten gleichmäßig, wenn Routing deterministisch ist).
2. **Multi-Einwand-Match-Ambiguity**: Wenn ein User denselben Einwand-Typ ("Kosten/Preis") in einer Session **zweimal** behandelt, entstehen 2 FtObjectionEvent-Rows UND 2 ObjectionEvent-Rows. Der Join auf `conversation_log_id + einwand_typ` ist 2×2 = 4 Rows (Cartesian). Mitigation: zusätzliche Timestamp-Proximität (`ABS(ftoe.timestamp_ms/1000 - oe.created_at.epoch) < 30`) oder `ROW_NUMBER()`-Windowing. **Planner muss das entscheiden.**
3. **EWB-Button-Pfad loggt in BEIDE Tabellen** (routes/app_routes.py line 1213 + 1230) — also für Auto-Variante + Button-Click ist die Korrespondenz 1:1 in dieser Sitzung. Für Keyword-Match-Pfad kann es abweichen (prüfen).

**Empfehlung:** Für Pre-Launch-A/B-Auswertung reicht die simple 2-stufige Join (Tolerierung der 2× Ambiguity bei Multi-Einwand-Sessions). Post-Launch ggf. mit `ROW_NUMBER()` härten.

## Focus Area 4: `prompt_versions` A/B-Semantik (D-26)

**Quelle:**
- `database/models.py` line 463-474 (PromptVersion):
  ```python
  class PromptVersion(Base):
      __tablename__ = 'prompt_versions'
      __table_args__ = (UniqueConstraint('version', 'module', name='uq_prompt_version_module'),)
      id          = Column(Integer, primary_key=True)
      version     = Column(String(50), nullable=False)
      module      = Column(String(50), nullable=False)
      prompt_text = Column(Text, nullable=False)
      changelog   = Column(Text)
      is_active   = Column(Boolean, default=False, nullable=False)
      created_at  = Column(DateTime, default=utcnow)
  ```
- Seed in `app.py` line 601-644 (`_seed_prompt_versions`): Aktuell werden 5 Module mit `version='v1.0.0'` + `is_active=True` als Default gesetzt.

**Aktuelle `is_active`-Semantik:**
- `get_active_prompt_version('ewb')` in `services/claude_service.py` line 100-115 macht `filter_by(module='ewb', is_active=True).first()` — das erwartet **GENAU EINE** aktive Zeile pro Modul.
- Das Module "ewb" existiert aktuell NICHT im Seed; die existierenden sind: `assistant_live`, `coaching_live`, `objection_trigger`, `api_frage`, `training_persona`.

**D-26 Schema-Erweiterung — Empfehlung:**

Die zwei Kandidaten für die neue Spalte:

| Option | Pros | Cons |
|--------|------|------|
| `ab_weight INTEGER` (z.B. 50/50 oder 70/30) | Gewichtetes Routing möglich, flexibel | Komplexere Router-Logik, weniger kompatibel mit `user_id % len()` |
| `is_default BOOLEAN` (genau 1 Zeile pro module) | Simpler, passt zu D-23 `user_id % len(active_variants)` | Kein gewichtetes Routing, aber das ist für 2-Varianten-UAT egal |

**Empfehlung für Planner:** `is_default BOOLEAN` ist näher an D-23 Routing-Spec. Router-Semantik:
- `active_variants = db.query(PromptVersion).filter_by(module='ewb', is_active=True).order_by(PromptVersion.version).all()`
- Wenn N Zeilen → mod-Routing `active_variants[user_id % N]`.
- `is_default=True` ist der **Fallback**, wenn `get_active_prompt_version()` nur 1 Variante braucht (z.B. für FT-Logging `prompt_version`-Name-Resolve).

**Wichtige Konsistenz-Frage:** Wenn 2+ Zeilen mit `is_active=1` existieren, wie verhält sich `get_active_prompt_version()` (line 108 `first()`) heute? Antwort: **Undefiniert** — SQLite gibt eine beliebige zurück. Das ist ein latenter Bug, der Phase 08 mit fixen MUSS. Der Router in `prompt_pipeline.py` MUSS `get_active_prompt_version()` **ersetzen/wrappen**, nicht parallel existieren.

**Migration:**
```sql
-- In _migrate() als neuer Block:
-- ALTER TABLE prompt_versions ADD COLUMN is_default BOOLEAN DEFAULT 0;
-- UPDATE prompt_versions SET is_default = 1 WHERE is_active = 1;  -- Backfill: alte Single-Aktive-Zeilen werden default
```

**Seed für v2-Variante:**
```python
# In _seed_prompt_versions() oder neuem _seed_ewb_v2():
INSERT OR IGNORE INTO prompt_versions (module, version, prompt_text, is_active, is_default, changelog)
VALUES ('ewb', 'v2-modular', '<v2-prompt-text>', 1, 0, 'Baustein-Struktur Phase 08');
INSERT OR IGNORE INTO prompt_versions (module, version, prompt_text, is_active, is_default, changelog)
VALUES ('ewb', 'v1-legacy', '<v1-prompt-text>', 1, 1, 'v1 aus Phase 04.7.1 als A/B-Baseline');
```

**Planner MUSS entscheiden:** Bleibt "ewb" als neues Modul oder erweitern wir `assistant_live`? Empfehlung: **Neues Modul "ewb"** — der existierende `assistant_live` macht nicht nur EWB, sondern auch Lernkarten-Matching + Phase-Classifier. EWB ist semantisch ein Subset, und Phase 08.5 wird ein weiteres Modul "qa" brauchen.

## Focus Area 5: Router-Integration Caching (Concerns §3)

**Quelle:**
- `services/claude_service.py` line 97-115:
  ```python
  _ACTIVE_PROMPT_CACHE: dict = {}  # module-level, per-process

  def get_active_prompt_version(module: str) -> str:
      if module in _ACTIVE_PROMPT_CACHE:
          return _ACTIVE_PROMPT_CACHE[module]
      # ... DB-Query ...
      _ACTIVE_PROMPT_CACHE[module] = version
      return version
  ```

**Probleme mit dem bestehenden Cache für A/B-Routing:**

1. **Cache-Key ist nur `module`, nicht `(module, user_id)`** — für Single-Variant pro Modul (Status Quo) OK, aber für A/B bricht das Routing: erster User schreibt `_ACTIVE_PROMPT_CACHE['ewb'] = 'v1-legacy'`, alle folgenden User bekommen v1, selbst wenn ihr `user_id % 2 == 1`.
2. **Kein TTL** — wird nur bei Prozess-Restart invalidiert. ENV-Override-Changes erfordern Restart (OK für D-24 Safety-Net-Use-Case, dokumentieren).
3. **Keine Thread-Safety** — dict-write ist in CPython quasi-atomar, aber kein echter Schutz. In der Praxis OK (read-heavy, seldom write).

**Empfehlung: Neuer Router-Cache in `services/prompt_pipeline.py`:**

```python
# services/prompt_pipeline.py
import os
from database.db import SessionLocal
from database.models import PromptVersion

# Module-level Cache: {(module, user_id): version_string}
# Key inkludiert user_id, weil A/B pro User unterschiedliche Varianten zurückgibt
_RESOLVER_CACHE: dict = {}

# Cache der verfügbaren Varianten pro Module (für Routing-Entscheidung)
# {module: [PromptVersion, PromptVersion, ...]}
_VARIANTS_CACHE: dict = {}

def resolve_prompt_version(module: str, user_id: int) -> str:
    # STEP 1: ENV-Override FIRST-CHECK (D-24)
    env_override = os.environ.get(f'PROMPT_{module.upper()}_VERSION_OVERRIDE')
    if env_override:
        return env_override

    # STEP 2: Per-User-Cache Hit
    cache_key = (module, user_id)
    if cache_key in _RESOLVER_CACHE:
        return _RESOLVER_CACHE[cache_key]

    # STEP 3: Variants-Load (1× pro Prozess, bis Invalidierung)
    if module not in _VARIANTS_CACHE:
        db = SessionLocal()
        try:
            variants = db.query(PromptVersion).filter_by(
                module=module, is_active=True
            ).order_by(PromptVersion.version).all()
            _VARIANTS_CACHE[module] = [v.version for v in variants] or ['unknown']
        finally:
            db.close()

    # STEP 4: Deterministisches Routing (D-23)
    variants = _VARIANTS_CACHE[module]
    resolved = variants[user_id % len(variants)]

    _RESOLVER_CACHE[cache_key] = resolved
    return resolved


def invalidate_resolver_cache():
    """Call after prompt_versions table changes. NOT called in live-loop."""
    _RESOLVER_CACHE.clear()
    _VARIANTS_CACHE.clear()
```

**Memory-Footprint:** 50 Early-Access-User × 2-3 Module = ~150 Cache-Entries (~15KB RAM). **Negligible.**

**Cache-Invalidation-Trigger** (post-Launch, nicht Phase 08 Scope):
- Admin-UI ändert `prompt_versions.is_active` → trigger `invalidate_resolver_cache()`.
- Prozess-Restart (deploy) → Cache startet leer.

## Focus Area 6: Profile JSON-Merge-Pattern (D-07 to D-13)

**Quellen:**
- `routes/profiles.py` line 121-155 (POST /<pid>/edit): Line 134 `daten_json = request.form.get('daten_json', p.daten or '{}')` → line 141 `p.daten = daten_json`. **Das ist kein Merge — das ist wholesale-Replace.**
- `templates/profile_editor.html` line 953-1007 (`buildAndSubmit()`): Baut das komplette JSON via `daten = { basis: {...}, zielgruppe: {...}, ..., ki: {...} }`. Alle Profile-Felder werden aus DOM-Werten zusammengesetzt. **Unbekannte Keys im Original werden verworfen.**
- `templates/profile_editor.html` line 1142-1147: `setVal('vi_ton', ki.ton); setVal('vi_zusatz', ki.zusatz);` — Populate-Handler liest nur bekannte Keys.

**Konsequenz für neue Felder:**
Die 4 neuen Felder (`eigene_formulierungen`, `beweise`, `branche_kontext` + umgebauter `ton`-Select) MÜSSEN an **drei Stellen** eingebaut werden:
1. HTML-Form (neue Inputs/Textareas mit IDs, tooltip-Pattern).
2. `buildAndSubmit()` JS-Funktion — neue Keys im `daten`-Objekt.
3. Populate-Code (bei Page-Load, ~line 1120-1150 im editor) — neue Keys auslesen aus `DATEN`.

**Zusätzlicher Fallstrick:**
- `branche` ist **sowohl eine separate DB-Column** (Profile.branche line 126) **als auch potenziell in `daten.basis` redundant** (line 268: `value="{{ profile.branche if profile else '' }}"`). Die Enum-Migration betrifft **nur** die Column, nicht den JSON-Blob. Planner MUSS entscheiden: `branche` bleibt Column (bestehender Pattern), `branche_kontext` kommt in `daten.basis.branche_kontext` als JSON-Key.

**Empfehlung:** JSON-Key-Namen konsistent in `daten.basis`:
- `daten.basis.eigene_formulierungen` (Array of Strings)
- `daten.basis.beweise` (Array of Strings)
- `daten.basis.branche_kontext` (String)
- `daten.ki.ton` (String — wird Select-Wert oder "Eigener Stil"-Input)

## Focus Area 7: `branche`-Enum-Migration-Heuristik (D-09)

**Quelle:**
- `database/models.py` line 126: `branche = Column(String(200))` — **Separate Column**, nicht in JSON. Alle bestehenden Profile haben Freitext-Werte.

**Aktuelle Freitext-Werte (Beispiele aus NERVE_DEMO_PROFILE + Training-Defaults):**
- "SaaS, Finanzberatung, Versicherung, Consulting, Agentur" (aus NERVE-Demo, app.py line 721 — **mehrere Branchen in einem String**)
- "B2B" (Training-Service-Default line 681)
- User-Einträge wie "Maschinenbau Mittelstand", "Industrieversicherung", "Immobilienmakler", "Performance-Coach".

**Heuristik-Mapping-Tabelle (empfohlen für Planner):**

| Enum-Wert | Keywords (case-insensitive, Teilstring-Match) | Edge-Cases |
|-----------|----------------------------------------------|------------|
| `saas_b2b` | `saas`, `software`, `b2b`, `cloud`, `platform`, `api` | "SaaS-B2B"→saas_b2b |
| `maschinenbau` | `maschinenbau`, `industrie`, `produktion`, `fertigung`, `engineering`, `anlagenbau` | "Werkzeugmaschinen"→maschinenbau |
| `versicherung` | `versicherung`, `assekuranz`, `policen`, `makler.*versicher` | "Industrieversicherung"→versicherung |
| `finanzprodukte` | `finanz`, `investment`, `anlage`, `kapital`, `bank`, `fonds` | "Finanzberatung"→finanzprodukte |
| `immobilien` | `immobilien`, `makler`, `bau`, `grundstueck`, `grundstück`, `wohnung` | "Immobilienmakler"→immobilien |
| `coaching` | `coaching`, `coach`, `training`, `mentor` | "Performance-Coach"→coaching |
| `beratung` | `beratung`, `consulting`, `berater`, `consultant` | "Finanzberatung" → finanzprodukte (priority) |
| `sonstiges` | (fallback, alles was nicht matcht) | Originaltext in `branche_kontext` speichern |

**Match-Priorität (wichtig bei Mehrdeutigkeit):**
1. `saas_b2b` vor `beratung` (weil Software-Company oft "IT-Beratung" als sekundär hat)
2. `finanzprodukte` vor `beratung` (Finanzberatung ist Finanz-nah)
3. `versicherung` vor `finanzprodukte` (Versicherung ist spezifischer)
4. Mehrfach-Match → ersten Match in der obigen Tabellenreihenfolge nehmen.

**Umlaut-Normalisierung** (wichtig für Match):
```python
import unicodedata
def _normalize_branche(s: str) -> str:
    # Umlaute entfernen für Match (nicht für Display!)
    s = s.lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s  # "Grundstück" → "grundstuck" → match "grundstueck"? NEIN
    # Besser: explizite Umlaut-Map
def _normalize_branche(s: str) -> str:
    return (s.lower()
            .replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
            .strip())
```

**Data-Migration-Pattern** (SQL in `_migrate()`):
```sql
-- Pseudo-code (SQLite hat kein CASE-Heuristic, also Python-Loop + prepared statement)
-- Planner: als idempotente Python-Migration mit Marker-Row in learning_events oder audit_log
-- Safeguard: nur migrieren wenn branche NICHT schon in Enum-Set
SELECT id, branche FROM profiles WHERE branche IS NOT NULL AND branche NOT IN
  ('saas_b2b', 'maschinenbau', 'versicherung', 'finanzprodukte', 'immobilien',
   'coaching', 'beratung', 'sonstiges');
-- Dann für jede Row: Heuristik anwenden, UPDATE + Originaltext in daten.basis.branche_kontext mergen
```

**Fallback-Rule:** Bei `sonstiges` den Originaltext in `daten.basis.branche_kontext` kopieren (wenn das Feld nicht schon belegt ist — sonst appenden mit Trennzeichen). So geht keine User-Info verloren.

**Empfehlung an Planner:** Die Heuristik-Migration als **separates Python-Skript** `scripts/migrate_branche_to_enum.py` bauen (dry-run Modus + actual-run). Nicht inline in `_migrate()`, weil diese Migration einmalig ist und Dev-Inspektion erfordert. Per Cron? Nein — einmalig beim Deploy ausführen.

## Focus Area 8: PreCall-Anrede-Override-Wiring (D-14, D-15)

**Quellen:**
- `static/pip-launcher.js` line 9: `step: 1, // 1=mode, 2=precall-option, 3=precall-form, 4=precall-result, 5=skript, 6=live`.
- `templates/app.html` line 670-685 (`precallPanel`): PreCall-Setup ist HTML im `templates/app.html`, nicht in einer eigenen Partial.
- Profil-Default: `_build_system_prompt()` in `services/claude_service.py` line 366-367: `if ki.get('ansprache'): lines.append(f'\nKundenansprache: {ki["ansprache"]} (immer einhalten)')`.
- ConversationLog hat aktuell KEINE `anrede`-Column — muss in `_migrate()` ADDITIONAL Column-Block.

**PreCall-Setup-Flow (aktueller Zustand):**
`pip-launcher.js` State-Machine (step 1-6) speichert in `state.precallFormData` (Line 16 = "saved form values for 'back' navigation"). Die Form-Felder sind aktuell nur `firma / person / branche`. **Anrede wäre ein neues Feld in dieser Form.**

**Anrede-Speicher-Zeitpunkt:**
- **Option A:** Bei PreCall-Form-Submit (`state.precallFormData = {...}` line 265) — nur Client-State.
- **Option B:** Bei session_start (wenn Live-Session tatsächlich aktiviert wird) — an Socket.IO-Event oder `/api/start_live_session` senden → Backend speichert in `conversation_logs.anrede`.
- **Empfehlung für Planner:** **Option B** — sonst kann der User "zurück" klicken und die Anrede geht verloren. Das Backend braucht die Anrede **spätestens wenn der erste Haiku-Call losgeht** (für System-Prompt-Injection).

**Override-Resolution-Chain (in `_build_system_prompt` erweitern):**
```python
# In _build_system_prompt() in services/claude_service.py ~line 366:
# ALT:
#   if ki.get('ansprache'):
#       lines.append(f'Kundenansprache: {ki["ansprache"]} (immer einhalten)')
# NEU:
import services.live_session as ls
anrede_override = ls.state.get('session_anrede')  # von session_start gesetzt
anrede = anrede_override or ki.get('ansprache') or 'Sie'
lines.append(f'Anrede: {anrede}. WICHTIG: Nutze konsequent {anrede}-Form. '
             f'Wechsle NIEMALS innerhalb einer Antwort zwischen Du und Sie.')  # D-15 wortwörtlich
```

**Schema-Migration `conversation_logs.anrede`:**
```python
# In app.py _migrate() als neuer Block:
for col, typedef in [
    ('anrede', "VARCHAR(10)"),  # Phase 08: PreCall-Override (Du/Sie)
]:
    try:
        conn.execute(text(f'ALTER TABLE conversation_logs ADD COLUMN {col} {typedef}'))
        conn.commit()
        print(f"[DB] Migration: added conversation_logs.{col}")
    except Exception:
        pass
```

**Wiring-Aufgaben für Planner:**
1. `pip-launcher.js` Step 3 (precall-form) um 2-Button-Wahl "Du" / "Sie" erweitern + localStorage-Sticky (oder nicht? — pro Session neu).
2. `state.precallFormData.anrede` an Backend senden beim session_start (via existing `/api/start_live_session` oder Socket.IO-Event).
3. Backend-Handler (`routes/app_routes.py`): Anrede in `ls.state['session_anrede']` UND in `conversation_logs.anrede` (persist via create/update).
4. `_build_system_prompt()`: Override-Chain erweitern.
5. Session-End-Flow: Beim `/api/beenden` bleibt `conversation_logs.anrede` erhalten (Log-Persistenz).

## Focus Area 9: Tooltip-System Pattern

**DURCHBRUCH-FINDING:** Es gibt bereits einen **vollständigen Tooltip-Pattern** im Code, nicht nur in der Plan-Phase erwähnt:

**Quellen:**
- `templates/profile_editor.html` line 120-141: CSS-Klassen `.tip-icon` + `#g-tip` + `#g-tip-inner`. Aktuelle Größe: **14×14px** (line 122-123) — **UNTER D-18 Spec von ≥16×16px**.
- `templates/profile_editor.html` line 625-627: `function ti(text) { return '<i class="tip-icon" data-tip="${esc(text)}">?</i>'; }` — JS-Helper für Inline-Einbau.
- `templates/profile_editor.html` line 631-666: Event-Handler `mouseover`/`mouseout` auf `.tip-icon` setzt Position und Content des globalen `#g-tip` Containers.
- Ca. 10-15 existierende Tooltips in profile_editor.html (z.B. line 731, 813, 819, 851).

**Aktueller Content-Stil (vs. D-16 3-Block-Pattern):**
Existierende Tooltips sind **1-Satz-Tooltips**: `"Max 2-3 Wörter, z.B. 'Zu teuer', 'Keine Zeit'. Wird auf dem EWB-Button im PiP angezeigt. Leer lassen = Kategorie-Fallback."` (line 813). Das erfüllt D-16 Block 1 (Was rein soll) + teilweise Block 2 (Beispiel), aber **NICHT Block 3 (Nicht verwechseln mit)**.

**Was Phase 08 tun muss:**
1. **CSS-Anpassung** (line 120-128 in profile_editor.html): `width/height 14px → 16px`, `font-size 9px → 11px`, eventuell `min-width: 16px`.
2. **Content-Umbau aller ~20 Tooltips** nach 3-Block-Pattern. Das ist primär eine Content-Arbeit, kein Code-Problem.
3. **ti()-Helper** erweitern, um 3-Block-strukturiertes Content zu unterstützen:
   ```js
   function ti3(was_rein, beispiel, nicht_verwechseln) {
     const full = `${was_rein}\n\nBeispiel: ${beispiel}\n\nNicht verwechseln mit: ${nicht_verwechseln}`;
     return `<i class="tip-icon" data-tip="${esc(full)}">?</i>`;
   }
   ```
   Oder einfacher: HTML im Tooltip erlauben (`innerHTML` statt `textContent`).
4. **Tooltip-Breite evtl. erweitern**: aktuell max-width 240px (line 133), für 3 Blöcke eher 320px oder adaptive.

**Accessibility (aria-describedby):**
Aktueller Code nutzt `<i>` ohne `aria-describedby` — das ist nicht screenreader-friendly. D-18 fordert nicht explizit aria, aber als Launch-Gate-Feature empfehle ich dem Planner, das Pattern zu erweitern:
```html
<label>Eigene Formulierungen
  <i class="tip-icon"
     data-tip="..."
     aria-describedby="tip-eigene_formulierungen"
     tabindex="0"
     role="button">?</i>
</label>
<span id="tip-eigene_formulierungen" class="sr-only">...</span>
```

**Beispiel-Profil-Modal (D-19):**
Kein bestehendes Modal-Pattern im Profile-Editor gefunden. Template nutzt custom `<div id="g-tip">` als Fake-Modal. Für das Beispiel-Profil-Modal (vollständig ausgefülltes Demo-Profil zum Durchscrollen) empfehle ich dem Planner:
- **Neues `<dialog>`-Element** (nativer HTML5 Dialog, Chrome/Firefox/Safari alle supporten), ohne Framework-Dependency.
- Inhalte als statisches HTML im Template oder in JSON-Konstante im JS.
- Link-Text `"Sieh dir ein ausgefülltes Beispiel an"` neben dem Profil-Editor-Header.

## Focus Area 10: Quality-Gate Messung Template (D-30, D-34)

**Quellen-Check für existierende Admin-Page-Patterns:**
- `/admin/costs` aus Phase 07.4/07.2 existiert: `routes/dashboard.py` + `routes/admin_views.py` nutzen Flask-Admin-Pattern (Bootstrap4 Theme). Siehe auch Admin-Card-Referenz in CONTEXT D-31.
- Training-Szenarien-Tabelle: `training_scenarios` existiert als DB-Model (models.py line 203), wird in Training-Modul gerendert.

**Drei Optionen für das EWB-Quality-Rating-Template:**

| Option | Implementierungs-Aufwand | Aggregation | UX für André |
|--------|-------------------------|------------|--------------|
| Google-Sheet (off-platform) | 0h Code | Manuell/Sheets-Formel | Gut (familiar), aber Export-Schritt |
| Lokale Markdown-Datei | 0h Code | Regex-Parser in Python-Script | Schlecht für binäre Bewertung (tippen statt klicken) |
| Flask-Admin-Page `/admin/ewb-rating` | ~2-3h (Template + Route + Model) | SQL-Aggregation live | Optimal für "100 EWBs × 10s" |

**Empfehlung an Planner:** **Option C — Flask-Admin-Page.** Begründung:
- 100 EWBs × 3 Buttons = 300 Clicks. Ein lokales HTML-Tool hat extrem niedrige Click-Latenz (<50ms) vs. Sheet/Markdown-Parse-Workflow.
- Bestehende Admin-Infrastruktur (Phase 04.7) kann wiederverwendet werden — kein neues Auth/Routing.
- Aggregation (Vorlesbar-Rate, Varianz-Score, A/B-Split) läuft direkt in SQL ohne Export.

**Minimale Implementierung** (als Referenz für Planner):
```python
# routes/admin_views.py — neue Route
@app.route('/admin/ewb-rating')
@superadmin_required
def ewb_rating_template():
    # Lade ungeratete EWBs aus conversation_logs.gegenargument_details (JSON)
    # Rendere als Liste mit 3 Sub-Kriterien × 2 Buttons (ja/nein) pro EWB
    # Speicher-Route: POST /admin/ewb-rating/<log_id>/<ewb_idx> mit JSON {kriterium: bool, ...}
    # Ergebnis-Tabelle: neue `ewb_ratings` Table:
    #   conversation_log_id, einwand_typ, klingt_wie_mensch (bool), keine_halluzination (bool), trifft_einwand (bool), rater_id, rated_at
    pass
```

**Die Quality-Formel (D-27) als SQL:**
```sql
SELECT
    conversation_log_id,
    einwand_typ,
    (klingt_wie_mensch + 2 * keine_halluzination + trifft_einwand) / 4.0 * 100 AS score
FROM ewb_ratings
WHERE score >= 80;  -- Gate: 80% haben Score ≥80
```

**Neue Tabelle `ewb_ratings`:** Hinzufügen zu `database/models.py`, ADD COLUMN-Pattern in `_migrate()`.

## Focus Area 11: Post-Call-Rating-UI-Anchor (D-03)

**Quellen:**
- `templates/session_detail.html` line 130-172: **Sektion 4 "Einwand-Timeline"** rendert bereits alle ObjectionEvent-Rows einer Session mit success-Badge ("Erfolgreich" / "Nicht behandelt"). **Das ist der genaue Insertion-Point für D-03/D-04.**
- `routes/dashboard.py` line 715 (`session_detail`): Route `/session/<int:sid>` lädt `events = db.query(ObjectionEvent).filter(ObjectionEvent.conversation_log_id == sid).order_by(ObjectionEvent.id.asc()).all()` und rendert in Template.

**Post-Call-Redirect-Verhalten aus Phase 07.2 (Rule 1: landet IMMER auf /session/<id>):**
- Training-Modus: Redirect auf `/session/<id>` nach Training-Abschluss (Phase 07.2 D-03 via Plan 04).
- Live-Modus (Cold Call / Meeting): Redirect auf `/session/<id>` nach `/api/beenden`.
- **Beide Modi nutzen dieselbe Session-Detail-Seite** → **EINE Rating-UI für beide**.

**Konkrete Insertion-Stelle:**
In `templates/session_detail.html` **direkt nach** der Einwand-Timeline-Sektion (nach line 172), oder **innerhalb** der Timeline (3 Buttons pro `<li>`-Row ersetzen den statischen Badge).

**Empfehlung an Planner:** **Innerhalb der Timeline** (Variante 2). Das macht die Rating-UI prominent und lässt den User im bestehenden Kontext (er sieht den Einwand-Typ + seine gewählte Option) direkt raten.

```html
{# In session_detail.html ~line 140: #}
<li class="n-session-detail-timeline-row ...">
    <span class="n-label">#{{ loop.index }}</span>
    <div>
        <div class="n-session-detail-timeline-typ">{{ ev.einwand_typ }}</div>
        {% if ev.option_gewaehlt %}<div>{{ ev.option_gewaehlt }}</div>{% endif %}
    </div>
    {# NEU: 3-Button Rating — ersetzt statischen Badge (D-04) #}
    <div class="n-ewb-rating-group" data-event-id="{{ ev.id }}">
        <button class="n-ewb-btn {% if ev.success == True %}n-ewb-btn--active{% endif %}"
                data-value="true">Erfolg</button>
        <button class="n-ewb-btn {% if ev.success == False %}n-ewb-btn--active{% endif %}"
                data-value="false">Kein Erfolg</button>
        <button class="n-ewb-btn {% if ev.success is none %}n-ewb-btn--active{% endif %}"
                data-value="null">Überspringen</button>
    </div>
</li>
```

**Neuer Backend-Endpoint (für Planner):**
```python
# routes/dashboard.py oder neuer ewb_bp
@app.post('/api/ewb/<int:event_id>/rate')
@login_required
def api_ewb_rate(event_id):
    data = request.get_json()
    value = data.get('success')  # True / False / None
    db = get_session()
    try:
        ev = db.query(ObjectionEvent).filter_by(id=event_id).first()
        if not ev:
            abort(404)
        # Ownership check: event muss zu g.user.id gehören (via conversation_logs)
        conv = db.query(ConversationLog).filter_by(id=ev.conversation_log_id, user_id=g.user.id).first()
        if not conv:
            abort(403)
        # value-Whitelist: True/False/None
        if value not in (True, False, None):
            abort(400)
        ev.success = value
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
```

**Benefit-Framing (D-03 wortwörtlich):**
Oberhalb der Timeline-Sektion ein Info-Block einfügen:
```html
<div class="n-session-detail-info">
  <strong>Hilf uns, dir zu helfen.</strong>
  Wie empfandest du die Einwandbehandlung — welcher der folgenden EWBs hatte Erfolg?
  Basierend auf deinen Antworten kann NERVE dir in Zukunft besser bei der EWB helfen.
</div>
```

## Focus Area 12: Validation Architecture

**Quelle:** `tests/conftest.py` (vollständig gelesen)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `tests/conftest.py`, siehe Phase 04.6.1 Plan 01 Setup) |
| Config file | `tests/conftest.py` (shared fixtures) — kein `pytest.ini` gefunden |
| Quick run command | `pytest tests/<test_file.py> -x -v` |
| Full suite command | `pytest tests/ -v` |

### Existierende Test-Infrastruktur
- `tests/conftest.py` hat 4 Fixtures: `sample_state` (für live-session state dicts), `db_session` (in-memory SQLite, schema loaded via `Base.metadata.create_all`), `client` (Flask test client mit db-rebind via monkeypatch), `db_from_client` (alias).
- 16 existierende Test-Files (siehe `tests/test_*.py`), die bereits Modelle + Services testen: `test_einwand_keyword_matcher.py` (Phase 06.2), `test_mood_voice.py` (04.10.1), `test_ft_lifecycle.py` (04.7.1), `test_ft_models.py`, `test_ft_write_hooks.py`, `test_cost_tracker.py` (04.7.2), etc.
- **Pattern:** Tests monkeypatchen Dependencies (z.B. `_ACTIVE_PROMPT_CACHE` in `test_ft_write_hooks.py` line 74, 127) — guter Precedent für Router-Tests.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EWB-01 | ObjectionEvent.success kann NULL sein | unit | `pytest tests/test_objection_event_nullable.py::test_success_accepts_none -x` | ❌ Wave 0 |
| EWB-02 | Migration resettet POLISH-38.1-Alt-Daten auf NULL | unit | `pytest tests/test_branche_migration.py::test_success_reset_cutoff -x` | ❌ Wave 0 |
| EWB-05 | Heuristik-Mapping Branche→Enum | unit | `pytest tests/test_branche_migration.py::test_heuristic_mapping -x` | ❌ Wave 0 |
| EWB-09 | resolve_prompt_version deterministic routing | unit | `pytest tests/test_prompt_pipeline.py::test_deterministic_routing -x` | ❌ Wave 0 |
| EWB-09 | ENV-Override greift First-Check | unit | `pytest tests/test_prompt_pipeline.py::test_env_override_first -x` | ❌ Wave 0 |
| EWB-11 | build_profile_context assembly | unit | `pytest tests/test_prompt_pipeline.py::test_build_profile_context -x` | ❌ Wave 0 |
| EWB-06 | Anrede-Override (Session > Profil) | integration | `pytest tests/test_anrede_override.py::test_session_override_wins -x` | ❌ Wave 0 |
| EWB-17 | A/B-Auswertungs-Join-Query | unit | `pytest tests/test_ab_stats.py::test_join_path -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_prompt_pipeline.py -x` (oder der konkret betroffene Test-File) — ~2-5 Sekunden.
- **Per wave merge:** `pytest tests/ -v` (~30-60 Sekunden für alle Tests).
- **Phase gate:** Vor `/gsd-verify-work` volle Suite grün + manuelle UAT von André für POLISH-55-UI und Tooltips.

### Wave 0 Gaps

- [ ] `tests/test_prompt_pipeline.py` — covers EWB-09, EWB-11 (resolve_prompt_version, build_profile_context)
- [ ] `tests/test_branche_migration.py` — covers EWB-05, EWB-02 (Heuristik + Reset)
- [ ] `tests/test_objection_event_nullable.py` — covers EWB-01 (Migration smoke)
- [ ] `tests/test_anrede_override.py` — covers EWB-06 (integration mit client fixture)
- [ ] `tests/test_ab_stats.py` — covers EWB-17 (SQL-Join-Query + sample-Data)

Keine Framework-Install nötig (pytest vorhanden). Kein neuer conftest-Scope nötig — bestehende Fixtures decken alles ab.

## Runtime State Inventory

**Phase 08 ist KEIN reiner Rename/Refactor**, aber es gibt runtime-state-Elemente:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `ObjectionEvent.success` Boolean NOT NULL mit ~X Rows existierender POLISH-38.1-Daten | Data-Migration D-02: SET success=NULL WHERE created_at < cutoff |
| Stored data | `profiles.branche` Freitext-Column mit ~X Einträgen | Heuristik-Migration Branche→Enum + Originaltext in daten.branche_kontext |
| Stored data | `prompt_versions`-Tabelle mit 5 Modulen × 1 Version (aktuelle Seed) | Neue Rows für `module='ewb'` + `version='v1-legacy'/'v2-modular'` INSERT OR IGNORE |
| Live service config | Keine externen Dienste (n8n/Datadog) betroffen | None — Phase 08 ist pure in-repo |
| OS-registered state | Keine (keine Scheduler/pm2-Einträge mit zu renamenden Strings) | None |
| Secrets/env vars | Neue ENV `PROMPT_EWB_VERSION_OVERRIDE` | `.env.example` + `deploy/nerve.service` dokumentieren (D-25), Code liest via `os.environ.get()` |
| Build artifacts | Flask app hat keinen Build-Step (kein Bundling, nerve.css wird live gelesen, CSS_VERSION-Cache-Bust existiert) | CSS_VERSION bump nach nerve.css-Änderungen (existing pattern) |

**Nichts in Kategorie "gelöscht":** Aber `services/claude_service.py` `_ACTIVE_PROMPT_CACHE` (line 97) wird funktional obsolet — der neue `services/prompt_pipeline.py` Router ersetzt `get_active_prompt_version()` zumindest für EWB-Modul. Die alte Funktion kann bleiben als Legacy-Wrapper für die 4 anderen Module (`assistant_live`, `coaching_live`, `objection_trigger`, `api_frage`, `training_persona`). Planner entscheidet: deprecaten oder koexistieren?

## Common Pitfalls

### Pitfall 1: Profile-JSON-Wholesale-Replace (nicht Merge)
**Was geht wrong:** Neue Felder werden im ersten Save gespeichert, beim zweiten Save verschwinden sie — weil das JS im `buildAndSubmit()` nur bekannte Keys schreibt.
**Warum passiert es:** `routes/profiles.py` line 141 replaced `p.daten` komplett, `profile_editor.html` line 953-1007 baut JSON neu auf.
**Vermeidung:** ALLE neuen Felder an 3 Stellen einbauen: HTML-Input + `buildAndSubmit()` JS + Populate-Handler.
**Warnzeichen:** User berichtet "habe `eigene_formulierungen` gespeichert, aber wenn ich jetzt das Profil reopenen ist es weg."

### Pitfall 2: SQLite-ALTER-COLUMN-Illusion
**Was geht wrong:** Planner versucht `ALTER TABLE objection_events ALTER COLUMN success DROP NOT NULL` — das ist NICHT SQLite-Syntax.
**Warum passiert es:** PostgreSQL + MySQL können das; die meisten Migration-Tutorials zeigen das Pattern.
**Vermeidung:** Table-Rebuild-Pattern nutzen (CREATE new → INSERT SELECT → DROP → RENAME).
**Warnzeichen:** Migration-Fehler `syntax error near "DROP"` in `_migrate()`-Try/Except.

### Pitfall 3: A/B-Cache Single-Variant-Sticky
**Was geht wrong:** Nach erstem Prozess-Request landet eine Variante im `_ACTIVE_PROMPT_CACHE['ewb']` und ALLE User bekommen dieselbe Variante (auch wenn deterministic routing sie teilen sollte).
**Warum passiert es:** Der existierende Cache (`services/claude_service.py` line 97) hat `module` als Key, nicht `(module, user_id)`.
**Vermeidung:** Neuer Resolver-Cache in `prompt_pipeline.py` mit `(module, user_id)`-Tupel als Key.
**Warnzeichen:** A/B-Auswertung zeigt 100% der EWBs auf einer Variante trotz gemischter User.

### Pitfall 4: Multi-Einwand Join-Cartesian
**Was geht wrong:** A/B-Query gibt doppelte Zählung, wenn User denselben Einwand-Typ zweimal in einer Session behandelt hat.
**Warum passiert es:** Join auf `(conversation_log_id, einwand_typ)` matched 2×2 Rows bei 2 EWBs gleichen Typs.
**Vermeidung:** Timestamp-Proximität als zusätzliches Join-Kriterium, oder `ROW_NUMBER() OVER (...)` zum Pairing.
**Warnzeichen:** `n` (Sample-Size) in A/B-Query ist 1.5-2× höher als die tatsächliche EWB-Count.

### Pitfall 5: Tooltip-Umlaut-Escaping
**Was geht wrong:** User-facing Tooltip-Text mit Umlauten wird in `data-tip`-Attribut doppelt-escaped und zeigt `&auml;` statt `ä`.
**Warum passiert es:** `esc()` Helper in `profile_editor.html` line 615 ersetzt `&` → `&amp;`. Wenn Umlaut als HTML-Entity reinkommt, wird er "geschützt" — und dann im DOM-Lookup nicht zurück-dekodiert.
**Vermeidung:** Umlaute als **native UTF-8** (nicht als HTML-Entity) in Tooltip-Content schreiben. Die `esc()` Funktion ist korrekt — das Problem ist Quellcode-Input.
**Warnzeichen:** Tooltip zeigt "Gespräch" (richtig) vs. "Gespr&auml;ch" (falsch).

### Pitfall 6: Anrede-Override ohne Haiku-Restart
**Was geht wrong:** User wählt "Du" in PreCall, aber die erste Haiku-Response nutzt "Sie" weil die Session bereits läuft.
**Warum passiert es:** `ls.state['session_anrede']` wird nach Session-Start gesetzt; wenn die erste Haiku-Response davor startet, nutzt sie Profil-Default.
**Vermeidung:** Anrede MUSS VOR dem ersten Live-Haiku-Call in `ls.state` sein. Setzung im Backend-Handler `/api/start_live_session` bevor der erste `/api/analyse_line` ausgeführt wird.
**Warnzeichen:** Erste 2-3 EWBs haben falsche Anrede, spätere sind korrekt.

### Pitfall 7: A/B ohne Single-User-Signal
**Was geht wrong:** Pre-Launch will A/B-Statistik über v1 vs. v2, aber André ist Solo-User — `user_id % 2` gibt ihm immer dieselbe Variante. Auswertung bleibt leer.
**Warum passiert es:** Deterministic Routing ist 1 User → 1 Variante.
**Vermeidung:** **ENV-Override ist PRIMÄR-TOOL für Pre-Launch UAT** (D-24). André schaltet manuell: `PROMPT_EWB_VERSION_OVERRIDE=v1-legacy` für Session 1-5, `=v2-modular` für Session 6-10, unset für "echte" Early-Access-Phase.
**Warnzeichen:** "Ich sehe nur eine Variante" nach Launch — Prompt checken.

## Code Examples

### Router-Resolver (Wave 2)
```python
# services/prompt_pipeline.py — NEW FILE
import os
from database.db import SessionLocal
from database.models import PromptVersion

_RESOLVER_CACHE: dict = {}
_VARIANTS_CACHE: dict = {}


def resolve_prompt_version(module: str, user_id: int) -> str:
    """Resolve prompt version for (module, user_id).

    Priority:
      1. ENV override: PROMPT_{MODULE}_VERSION_OVERRIDE
      2. Deterministic routing: user_id % len(active_variants)
      3. Fallback: 'unknown' if no variants in DB

    Cache: per (module, user_id) after first resolve.
    Invalidate via invalidate_resolver_cache() after prompt_versions change.
    """
    env_key = f'PROMPT_{module.upper()}_VERSION_OVERRIDE'
    env_override = os.environ.get(env_key)
    if env_override:
        return env_override

    cache_key = (module, user_id)
    if cache_key in _RESOLVER_CACHE:
        return _RESOLVER_CACHE[cache_key]

    if module not in _VARIANTS_CACHE:
        db = SessionLocal()
        try:
            rows = (db.query(PromptVersion)
                    .filter_by(module=module, is_active=True)
                    .order_by(PromptVersion.version)
                    .all())
            _VARIANTS_CACHE[module] = [r.version for r in rows] or ['unknown']
        finally:
            db.close()

    variants = _VARIANTS_CACHE[module]
    resolved = variants[user_id % len(variants)]
    _RESOLVER_CACHE[cache_key] = resolved
    return resolved


def invalidate_resolver_cache():
    _RESOLVER_CACHE.clear()
    _VARIANTS_CACHE.clear()
```

### Migration (Wave 1)
```python
# app.py _migrate() — new block nach line 360
# Phase 08: ObjectionEvent.success Nullable Migration
try:
    # Check if success is still NOT NULL
    rows = conn.execute(text("PRAGMA table_info(objection_events)")).fetchall()
    success_is_notnull = any(r[1] == 'success' and r[3] == 1 for r in rows)  # r[3] = notnull flag
    if success_is_notnull:
        conn.execute(text("""
            CREATE TABLE objection_events_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                org_id INTEGER,
                conversation_log_id INTEGER NOT NULL,
                einwand_typ VARCHAR(100) NOT NULL,
                success BOOLEAN,  -- NULLABLE!
                created_at DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(org_id) REFERENCES organisations(id),
                FOREIGN KEY(conversation_log_id) REFERENCES conversation_logs(id)
            )
        """))
        conn.execute(text("INSERT INTO objection_events_new SELECT * FROM objection_events"))
        conn.execute(text("DROP TABLE objection_events"))
        conn.execute(text("ALTER TABLE objection_events_new RENAME TO objection_events"))
        conn.commit()
        print("[DB] Migration v08_01: objection_events.success -> NULLABLE (table rebuild)")
        # D-02: Reset POLISH-38.1 Alt-Daten
        # Cutoff: 2026-04-21 (POLISH-38.1 Commit-Datum aus STATE.md)
        conn.execute(text("""
            UPDATE objection_events SET success = NULL
            WHERE created_at < '2026-04-22 00:00:00'
        """))
        conn.commit()
        print("[DB] Migration v08_01: Reset POLISH-38.1 success-Werte auf NULL")
except Exception as e:
    print(f"[DB] Phase 08 migration failed: {e}")
```

### Profile-Field JS-Populate (Wave 2)
```javascript
// In profile_editor.html buildAndSubmit() ~line 1005
// Add to daten.basis:
daten.basis.eigene_formulierungen =
    document.getElementById('vi_eigene_formulierungen').value
        .split('\n').map(s => s.trim()).filter(Boolean);
daten.basis.beweise =
    document.getElementById('vi_beweise').value
        .split('\n').map(s => s.trim()).filter(Boolean);
daten.basis.branche_kontext =
    document.getElementById('vi_branche_kontext').value.trim();

// In Populate-Handler ~line 1142
setVal('vi_eigene_formulierungen', (basis.eigene_formulierungen || []).join('\n'));
setVal('vi_beweise', (basis.beweise || []).join('\n'));
setVal('vi_branche_kontext', basis.branche_kontext || '');
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_ACTIVE_PROMPT_CACHE` module-level dict mit Key=`module` | Neuer `_RESOLVER_CACHE` mit Key=`(module, user_id)` in `prompt_pipeline.py` | Phase 08 | Pro-User-Routing möglich |
| Freier Branchen-Text in `profiles.branche` Column | Enum + Context-Textarea | Phase 08 | Prompt kann Branche-spezifisch adaptieren |
| Ein Prompt pro Modul (`is_active=1` single row) | 2+ aktive Varianten mit `is_default` Fallback | Phase 08 | A/B-Routing möglich |
| 1-Satz-Tooltips | 3-Block-Pattern Tooltips (was/beispiel/nicht-verwechseln) | Phase 08 | Onboarding-Friction reduziert |
| `success Boolean NOT NULL default 0` | `success Boolean NULLABLE` (3-State) | Phase 08 | A/B-Messung valide (NULL = Überspringen) |
| `_build_system_prompt()` liest Profile.branche NICHT | Liest `branche` + `branche_kontext` | Phase 08 | Branche fließt endlich in Prompt ein |

**Deprecated/Obsolet:**
- `services/claude_service.py get_active_prompt_version()` (line 100) wird für EWB-Modul durch `prompt_pipeline.resolve_prompt_version()` ersetzt. Bleibt als Legacy-Wrapper für 4 andere Module oder wird komplett migriert.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | POLISH-38.1 Alt-Daten-Cutoff = 2026-04-22 | §2 Migration | Cutoff zu spät: neue Ratings werden rückgesetzt. Empfehlung: Cutoff = genauer POLISH-38.1-Deploy-Commit-Timestamp |
| A2 | Ca. 10-15 existierende Tooltips im profile_editor.html | §9 | Count kann niedriger/höher sein — Claudian-Review-Budget anpassen |
| A3 | Bestehende `profiles.branche`-Column hat ~10-30 Rows im Prod-DB | §7 | Migration-Zeit skaliert linear; bei >100 Rows Planner-Entscheidung zu dry-run-Modus |
| A4 | `prompt_versions` hat aktuell 5 Rows (1 pro Modul) | §4 | Seed-Block prüfen im Live-Deploy vor Phase 08 |
| A5 | André schreibt ENV-Vars in `/etc/systemd/system/nerve.service` | §5 | Falls statt dessen `.env` genutzt wird: restart-Behavior prüfen |
| A6 | Post-Call-Redirect von Live+Training landet beide auf `/session/<id>` | §11 | Verifiziert via Phase 07.2 Plan 04 — low risk |
| A7 | Branche-Heuristik-Keywords decken >80% der existierenden Freitext-Werte ab | §7 | Bei <80%: Migration hinterlässt zu viel in `sonstiges`; Planner muss Heuristik verfeinern nach dry-run |
| A8 | Kein Test-DB-Seed für `prompt_versions` in `conftest.py` | §12 | Tests für resolve_prompt_version müssen Fixtures selbst bauen |

**6 von 8 Annahmen sind LOW-RISK / auditable in <5min via SQL-Query.** Die Planner-Phase sollte mit A1 (genauer Timestamp) + A3 + A4 (COUNT(*) queries auf Prod) starten.

## Open Questions

1. **Cutoff-Timestamp für D-02 Alt-Daten-Reset.**
   - Was we know: POLISH-38.1 completed 2026-04-21 (STATE.md Quick Task 260421-kwm).
   - What's unclear: Exakter UTC-Timestamp des Deploys.
   - Recommendation: Planner setzt Cutoff = `2026-04-22 00:00:00 UTC` konservativ, oder holt git-log vom POLISH-38.1-Commit (`585f567` laut STATE.md).

2. **Deprecation-Strategie für `get_active_prompt_version()` (legacy).**
   - Was we know: Neue `resolve_prompt_version()` ersetzt für EWB-Modul.
   - What's unclear: Sollen 4 andere Module (`assistant_live` etc.) auch migrieren oder Legacy bleiben?
   - Recommendation: In Phase 08 nur EWB migrieren. Legacy-Module bleiben bis Phase 08.5 / separatem Refactor.

3. **Beispiel-Profil-Modal-Content-Source.**
   - Was we know: D-19 fordert "komplett ausgefülltes Demo-Profil", D-20 verbietet NERVE/André/echte-Firmen-Inhalte.
   - What's unclear: Komplett neu erfinden oder existing `NERVE_DEMO_PROFILE_JSON` (app.py line 697) anonymisiert nutzen?
   - Recommendation: Komplett neu erfinden. Das NERVE-Demo-Profil ist branded und verletzt D-20.

4. **Test-Szenarien B "Profil-reich": welches Profil?**
   - Was we know: D-34 "Voll ausgefülltes Profil inkl. `branche_kontext` + `eigene_formulierungen`" für Scenario B.
   - What's unclear: Existierendes User-Profil (André privat) oder neues Test-Fixture-Profil.
   - Recommendation: Neues Test-Profil `profile_08_varianz_test` mit erstellt_von=NULL (System-Profile-Pattern), seed-baren via `_migrate()` INSERT OR IGNORE.

5. **Varianz-Gate bezogen auf `conversation_logs.gesamt_score` — Column existiert?**
   - Was we know: CONTEXT D-28 nennt `gesamt_score`, Models.py hat keinen `gesamt_score`-Column.
   - What's unclear: Ist das ein alias für `kb_end` (Kaufbereitschafts-End-Score, models.py line 251) oder für ein Post-Call-generiertes Score-Feld?
   - Recommendation: Planner klärt mit User — mostly likely `kb_end` oder `generate_scoring()`-Output aus `training_service.py`. Wenn die Column nicht existiert: Phase 08 hat ein Extra-Task "Score-Feld definieren".

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.8+ | Tests, Migrations | ✓ | (repo standard) | — |
| pytest | Tests in tests/ | ✓ | (existing fixtures) | — |
| SQLite | DB, Migrations | ✓ | (bundled mit Python) | — |
| Anthropic API Key | Live-Prompt-Tests | ✓ (local dev) | — | Mock-Tests für Unit, Live-Tests gated |
| Flask-Admin | `/admin/ewb-rating` Template | ✓ (Phase 04.7) | Bootstrap4Theme | — |
| Chart.js | Session-Detail-Seite | ✓ (Phase 07.1 via CDN) | — | — |

**Keine Missing Dependencies.** Phase 08 baut komplett auf bestehender Infrastruktur.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (existing) | `@login_required` bleibt |
| V3 Session Management | yes | Flask session cookies (existing) |
| V4 Access Control | **yes (kritisch)** | Rating-Endpoint MUSS ownership-check (ObjectionEvent → ConversationLog → user_id) |
| V5 Input Validation | yes | `success` Whitelist (TRUE/FALSE/NULL), `einwand_typ` gegen Enum, `branche` Enum-validiert |
| V6 Cryptography | no (Phase 08 führt keine Secrets ein) | — |

### Known Threat Patterns for Phase 08

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| EWB-Rating für fremde Session manipulieren (IDOR) | Elevation | Ownership-check via `ConversationLog.user_id == g.user.id` vor UPDATE |
| `success`-Column via API auf beliebigen String setzen | Tampering | Whitelist-Validierung `value in (True, False, None)` |
| `branche`-Enum-Injection | Tampering | Whitelist `{saas_b2b, maschinenbau, ...}` vor DB-Write |
| `PROMPT_EWB_VERSION_OVERRIDE` Env-Leak im Log | Disclosure | Log-Filter (print-level) NICHT env-Wert loggen |
| A/B-Routing-Manipulation per Client-Request (IDOR to force variant) | Spoofing | Routing 100% server-side, user_id kommt aus session nicht request |
| CSRF auf `/api/ewb/<id>/rate` POST | Tampering | Flask-SocketIO/Flask default CSRF existiert NICHT — prüfen ob POST-Handler CSRF-Token erwartet. Fallback: Same-Origin-Check via `Origin`/`Referer` Header |

**Planner MUSS prüfen:** Existing `/api/*` Endpoints im Repo haben KEIN CSRF-Protection (seen in routes/app_routes.py — nur `@login_required`). Das ist ein bestehender Scope-Gap, NICHT Phase 08-eingeführt. Empfehlung: CSRF-Härtung als separaten Backlog-Item, nicht Phase 08 blockieren.

## Recommended Plan/Wave Breakdown (nicht binding — Planner entscheidet)

**Wave 1 (Foundation + Migrations — ~3h):**
- Plan 01: Profile-Feld-Wiring-Matrix dokumentieren (D-46 refined). **Kein Code.**
- Plan 02: `ObjectionEvent.success` Nullable + POLISH-38.1-Reset (D-01, D-02). DB-Migration + Smoke-Test.
- Plan 03: `prompt_versions` Schema-Erweiterung (D-26) — `is_default` Column + Seed.
- Plan 04: `conversation_logs.anrede` Column Migration (D-14).
- Plan 05: `services/prompt_pipeline.py` Skeleton (D-40) mit `resolve_prompt_version()` + Unit-Tests.
- Plan 06: `branche`-Enum + Heuristik-Migration (D-09) als `scripts/migrate_branche_to_enum.py`.

**Wave 2 (Features + UI — ~6h):**
- Plan 07: Profile-Editor Felder `eigene_formulierungen`, `beweise`, `branche_kontext`, `ton`-Select, `zusatz`-Label (D-07 bis D-12).
- Plan 08: Tooltip-System 3-Block-Pattern (D-16 bis D-21). Inkl. Beispiel-Profil-Modal.
- Plan 09: PreCall-Anrede-Override-Wiring (D-14, D-15) — Frontend + Backend.
- Plan 10: v2-Prompt `ewb` in `services/ewb_pipeline.py` + Router-Wiring in `services/claude_service.py` (D-41, D-45).
- Plan 11: Active-Listening-Block (D-47) als Ergänzung im v2-Prompt.

**Wave 3 (Measurement + A/B — ~4h):**
- Plan 12: Post-Call-Rating-UI in session_detail.html (D-03, D-04) + Backend-Endpoint + ownership-check.
- Plan 13: 3 Test-Szenarien (A/B/C) als System-Training-Szenarien seed (D-34).
- Plan 14: EWB-Quality-Rating-Admin-Page `/admin/ewb-rating` (D-30).
- Plan 15: A/B-Auswertungs-SQL als Admin-Page-Card `/admin/ab-stats` oder Standalone-Script (D-22).
- Plan 16: ENV-Override-Dokumentation `.env.example` + `deploy/nerve.service` (D-25).

**Wave 4 (Quality-Gate durch André — offline ~4h):**
- André führt 15 Training-Sessions (3 Szenarien × 5 Repeats) + 5 echte Calls.
- André ratet 100 EWBs × 3 Sub-Kriterien via `/admin/ewb-rating`.
- Aggregation-Report: Vorlesbar-Rate + Varianz-Range + A/B-Split (wenn genug Data-Points).
- Launch-Gate-Entscheidung: Pass/Fail → Go/No-Go für Early-Access.

**Wave 5 (Launch-Review — ~1h):**
- Plan 17: Claudian-Review aller Tooltips (D-21) — Anti-Pattern-Check.
- Plan 18: Final-Deploy mit ENV-Var-Reset (kein OVERRIDE gesetzt → A/B live).

**Total estimated:** ~18h + 4h offline-André = 22h über 2-3 Wochen.

## Risks / Rollback Plan

### Risk 1: D-02 Alt-Daten-Reset destruiert Prod-Daten ohne Backup

**Impact:** Irreversibel — POLISH-38.1 Boolean-Werte gehen verloren.
**Likelihood:** HIGH wenn Planner vergisst Backup-Step.
**Mitigation:**
- **Pre-Migration:** `database/nerve.db` automatisch kopieren nach `database/nerve.db.bak_pre_v08_01` im Migration-Block VOR dem UPDATE.
- **Migration-Marker:** `audit_log`-Row mit `action='migration_v08_01'` + Row-Count als `details` JSON.
- **Rollback:** Wenn UAT auf Sandbox zeigt dass Migration kaputt war → `cp nerve.db.bak_pre_v08_01 nerve.db` + Prozess-Restart.

### Risk 2: A/B-Routing deadlockt Cache bei gleichzeitigem Variant-Update

**Impact:** Prozess-Hang oder inkonsistente Routing-Entscheidungen.
**Likelihood:** LOW (Flask-Threading ist moderat parallel, nicht async).
**Mitigation:** Cache-Writes sind dict-Assignments (quasi-atomic in CPython). Kein Lock nötig. Planner muss aber sicherstellen dass `invalidate_resolver_cache()` NICHT während Live-Traffic aufgerufen wird (nur bei Admin-Restart).

### Risk 3: `branche`-Heuristik-Migration verliert User-Daten

**Impact:** User-Freitext landet in `sonstiges` ohne Context-Preservation, User fragt "wo ist mein Branchen-Eintrag?".
**Likelihood:** MEDIUM wenn Fallback-Rule nicht sauber.
**Mitigation:** Originaltext IMMER nach `daten.basis.branche_kontext` kopieren, auch wenn Enum-Wert zugewiesen wird. Dry-Run-Mode in `scripts/migrate_branche_to_enum.py` zeigt Mapping vor Execute.

### Risk 4: Tooltip-Claudian-Review identifiziert >50% als Anti-Pattern

**Impact:** Launch-Gate fail, Phase 08 blockiert.
**Likelihood:** MEDIUM wenn Claude Code zu generisch schreibt (NERVE-Beispiele, echte Stats).
**Mitigation:** **In Wave 2 Plan 08 Tooltip-Draft direkt mit 3-Block-Schablone + Negativ-Beispielen füttern.** Claudian-Review als Iteration, nicht als Ablehnung.

### Risk 5: Solo-User A/B-Daten zu dünn für Go/No-Go-Entscheidung

**Impact:** Launch-Entscheidung basiert auf <10 Data-Points pro Variante.
**Likelihood:** HIGH — André ist Solo-Tester.
**Mitigation:** CONTEXT-Plan akzeptiert das bereits (Concerns §2) — ENV-Override als primäres UAT-Tool (15 Sessions v1, dann 15 v2). Echte A/B-Telemetrie erst post-Launch mit Early-Access-Usern.

### Risk 6: `services/prompt_pipeline.py` + `services/ewb_pipeline.py` Overhead für 50-User-Scope

**Impact:** +1h Design-Time, möglicherweise Over-Engineering für Phase 08-Scope (Phase 08.5 kommt eh).
**Likelihood:** LOW — CONTEXT D-44 rechtfertigt es.
**Mitigation:** Planner entscheidet — wenn D-42 `apply_tabu_filter()`-Stub gelassen wird, lohnt sich das Shared-Utils schon in 08. Sonst könnte man Wave 2 Plan 10 vereinfachen und die Module-Trennung erst in 08.5 vornehmen. **Empfehlung: CONTEXT-Lock halten** — die 1h Design ist billiger als zukünftiges Refactoring.

## Sources

### Primary (HIGH confidence)

- **Code-Inspektion** (alle Claims direkt verifiziert):
  - `database/models.py` (641 lines) — vollständig gelesen für Schema
  - `services/claude_service.py` — lines 1-400, 600-860 (Kern-Pfade für `_build_system_prompt`, `analysiere_mit_claude`, `analysiere_mit_claude_streaming`, `streame_auto_variante`)
  - `services/training_service.py` lines 400-620 (Training-Persona-Prompt + `build_customer_prompt`)
  - `app.py` lines 88-650 (Migration-Block + Seed-Patterns)
  - `routes/profiles.py` (365 lines) — vollständig gelesen für JSON-Replace-Pattern
  - `routes/app_routes.py` lines 444-570, 690-850, 1213-1253 (ObjectionEvent-Persist + FT-Logging-Pfade)
  - `templates/profile_editor.html` lines 110-170, 540-600, 950-1150, 620-660 (Tooltip-Pattern + Field-Layout)
  - `templates/session_detail.html` lines 120-200 (Rating-UI Anchor)
  - `templates/app.html` lines 460-690 (PreCall-Panel)
  - `static/pip-launcher.js` lines 1-400 (Step-Machine + precallFormData)
  - `tests/conftest.py` (98 lines) — vollständig gelesen
  - `.env.example` (existing ENV pattern)

- **CONTEXT.md** (248 lines) — vollständig gelesen, D-01 bis D-48 extrahiert.

- **Phase 04.7.1 Research** (`./.planning/phases/04.7.1-*/04.7.1-RESEARCH.md`) — FT-Logging-Architektur-Referenz.

### Secondary (MEDIUM confidence)

- **STATE.md Accumulated Decisions** (~250 Einträge) — für Phase 07.2-Redirect-Pattern + POLISH-38.1-Timestamp-Inferenz.

- **ROADMAP.md** Phase 8 section — für Phase-Scope + Dependencies.

- **CLAUDE.md (salesnerve)** — Umlaut-Regel + Stack-Constraints.

### Tertiary (LOW confidence — mention only)

- SQLite ALTER-COLUMN-Limitation — allgemeines Wissen, validiert durch lokalen SQLite-Syntax-Test (mental, nicht via Tool).

## Metadata

**Confidence breakdown:**
- Standard stack / Architekture: HIGH — alle Claims durch Code-Grep verifiziert.
- Pitfalls: HIGH — 6 von 7 basieren auf existierenden Code-Stellen, 1 (Umlaut) ist Pattern-Match zu CLAUDE.md.
- Heuristik-Mapping Branche→Enum: MEDIUM — Keywords sind plausibel, aber nicht gegen echte Prod-Daten validiert. Planner sollte dry-run.
- A/B-Router-Design: HIGH — Cache-Pattern direkt aus existierendem `_ACTIVE_PROMPT_CACHE` abgeleitet, Semantik erweitert.
- Tooltip-System: HIGH — 100% Reuse-Möglichkeit, nur CSS-Size + Content-Umbau.
- Post-Call-Rating-UI: HIGH — Insertion-Point ist die bestehende Einwand-Timeline.
- Test-Infrastruktur: HIGH — pytest-Setup dokumentiert in conftest.py.

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (30 Tage — stabile Codebase, keine parallelen Phasen erwartet die diese Dateien ändern)

---

*Phase 08 Research complete. Planner hat alle file-paths, line-numbers, SQL-snippets und JS-patterns die für PLAN.md-Tasks nötig sind.*
