---
id: SEED-001
status: dormant
planted: 2026-05-30
planted_during: v0.9.4 — Phase 08.23.2.D.UX.0 (4/4 Plans done)
trigger_when: G/MEET Wave 1 Start — sobald die G/MEET-Migration (crm.*-Schema-Umzug) als Milestone/Phase geplant wird
scope: Large
---

# SEED-001: G/MEET Wave 1 muss conversation_logs (Integer) und calls (UUID) WIRKLICH zusammenlegen — nicht nur ins crm.*-Schema umziehen

## Why This Matters

Heute existieren **zwei parallele Anruf-Tabellen** mit inkompatiblen Primary-Keys:

- `conversation_logs` — Legacy-Tabelle, `id` = **Integer** (`database/models.py:266`). Originär das "Gespräch"-Modell mit `einwaende`, Transkript-Logik, Coach-/Phrase-/EWB-Anbindung.
- `calls` — Neue Architektur (Phase 08.23.2.A+), `id` = **UUID** (`database/models.py:645`). CRM-fähig (`tenant_id`, `account_id`, `contact_id` als UUID), Outcome/Score/MEDDPICC.

Die neue `calls`-Tabelle hat bereits eine **Soft-Link-Brücke** zur alten: `calls.conversation_log_id → conversation_logs.id` (`database/models.py:670`, Migration 0006, REQ-D-1). Das heißt: ein Anruf existiert heute potenziell in BEIDEN Tabellen als zwei Zeilen mit zwei verschiedenen ID-Typen. Das ist technische Schuld, die mit jedem Feature wächst.

**Gefahr bei naivem G/MEET-Umzug:** Wenn G/MEET Wave 1 nur die beiden Tabellen ins `crm.*`-Schema *verschiebt* (Schema-Rename), bleibt der Dualismus erhalten — dann hat man ihn nur in ein hübscheres Schema einzementiert. Der einzig richtige Zeitpunkt zum **Verschmelzen** ist genau dieser Umzug: einmal anfassen, einmal migrieren, danach eine einzige Source-of-Truth-Anruf-Tabelle mit UUID-PK.

## When to Surface

**Trigger:** G/MEET Wave 1 Start — beim Planen des crm.*-Schema-Umzugs.

Dieser Seed soll während `/gsd-new-milestone` präsentiert werden, wenn der Milestone-Scope eine dieser Bedingungen trifft:
- G/MEET-Integration / Wave 1 wird geplant
- `crm.*`-Schema eingeführt oder Tabellen dorthin verschoben werden
- `calls` und/oder `conversation_logs` ins neue Schema umziehen
- UUID-Migration der Core-Tabellen ansteht (verwandt: Phase 08.23.2.F users→UUID, tenant_orgs-FKs)

**Harte Anforderung an den Plan:** Wave 1 darf NICHT als reiner Schema-Move geplant werden. Plan muss explizit "MERGE statt MOVE" als Akzeptanzkriterium führen.

## Scope Estimate

**Large** — eigene Phase oder Sub-Milestone. Umfasst:

1. **INT→UUID-Mapping-Skript** über alle FK-Tabellen, die heute auf `conversation_logs.id` (Integer) zeigen:
   - `phrases.session_id` → `conversation_logs.id` (`database/models.py:329`)
   - `objection_events.conversation_log_id` (`database/models.py:393`)
   - `ewb_ratings.conversation_log_id` (`database/models.py:416`)
   - `learning_cards.call_id` → `conversation_logs.id` (`database/models.py:584`)
   - `calls.conversation_log_id` → `conversation_logs.id` (`database/models.py:670`) — die Soft-Link-Brücke selbst
   - (André: "6 FK-Tabellen" — sechste vor Execute via `inspect.sh constraints` auf Production verifizieren; ggf. in Migrations 0005–0009 oder einer noch nicht im ORM gespiegelten Tabelle. **Nicht raten — Live-Schema ist Source-of-Truth.**)
2. **Konsistente UUID-Generierung für bestehende `conversation_logs`-Zeilen** — jeder Legacy-Integer-Row braucht eine deterministisch/stabil zugewiesene UUID (Backfill), damit FKs umgeschrieben werden können ohne Daten-Verlust. Bestehende `calls`-Zeilen mit gesetztem `conversation_log_id` müssen auf dieselbe UUID gemappt werden (Dedup statt Doppelzeile).
3. **6 FK-Tabellen-Rewrite** — Spalten-Typ INT→UUID, FK-Constraints neu, Indizes neu.
4. **Merge-Logik** — Felder aus `conversation_logs` (einwaende, Transkript-Meta) in das `calls`-Zielmodell überführen; entscheiden welche Spalten kanonisch bleiben.
5. **Rollback-Strategie + Real-Daten-Validation auf Production** (CLAUDE.md Punkt 13 + 21 — Persistenz-Schicht-Verifikation Pflicht).

## Breadcrumbs

Relevante Code- und Migrations-Referenzen im aktuellen Stand (`C:\Users\andre\dev\salesnerve\`):

- `database/models.py:266` — `class ConversationLog` (Integer-PK, Legacy)
- `database/models.py:645` — `class Call` (UUID-PK, neue Architektur, `default=uuid.uuid4`)
- `database/models.py:670` — `calls.conversation_log_id` Soft-Link-Brücke (Migration 0006, REQ-D-1)
- `database/models.py:700` — `class CallEvent` (`call_id → calls.id`, UUID, CASCADE)
- FK-Tabellen auf `conversation_logs.id`: `database/models.py:329` (phrases), `:393` (objection_events), `:416` (ewb_ratings), `:584` (learning_cards), `:670` (calls)
- Migrations-Historie der calls-Tabelle: `alembic/versions/0005_add_outcome_fields_to_calls.py`, `0006_extend_outcome_and_followup_intent.py`, `0007_add_score_fields_to_calls.py`, `0008_training_schema_foundation.py`
- Services die beide Modelle berühren: `services/outcome_service.py`, `services/live_session.py`, `routes/learning.py`, `routes/performance.py`, `routes/app_routes.py`

**Pre-Plan-Pflicht (CLAUDE.md HART-Erweiterung):** Live-Schema + Constraints + Row-Counts via `inspect.sh schema|constraints|count` von Production ziehen, NICHT lokal raten. Insbesondere die "sechste" FK-Tabelle so verifizieren.

## Notes

- Verwandte zukünftige Phase: **08.23.2.F** (users→UUID, tenant_orgs/accounts/contacts-FKs nachreichen) — dort werden `calls.tenant_id/account_id/contact_id/user_id` ohnehin auf UUID-FKs gehoben. Mapping-Skript dieses Seeds sollte mit 08.23.2.F koordiniert werden, evtl. gemeinsame Migration.
- Komplexitäts-Marker: 🔴 **komplex** (Schema + Migration + Multi-FK + Real-Daten) → Cross-AI-Plan-Review PFLICHT vor Execute (CLAUDE.md GSD-Workflow-Pflichten).
- DSGVO-Hinweis: `calls.followup_intent` hat bereits eine dokumentierte Rechtsgrundlage (NERVE DSGVO Analyse.md). Beim Merge prüfen, dass conversation_logs-Transkript-Daten nicht versehentlich über die Aufbewahrungsfrist hinaus mitwandern.
- Kontext zur Planted-Phase: gesät während v0.9.4, Pre-Launch (Early Access in Vorbereitung).
