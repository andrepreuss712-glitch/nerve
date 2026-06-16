# ADVERSARIAL RE-REVIEW (RUNDE 3) — Phase 08.23.2.PGTEST (echtes Postgres-Test-Gate)

Du bist ein Senior-Datenbank/DevOps-Engineer und adversarialer Plan-Reviewer. Du siehst diese 4 Plan-Dateien in ihrer FINALEN Form und musst entscheiden: bau-freigeben (PASS) oder blockieren (BLOCK). Du bist bewusst kritisch. Du bist NICHT der Autor.

## Was diese Phase tut (Kontext)
Sie ersetzt das alte SQLite-Test-Gate im `deploy.sh` durch ein echtes Postgres-Gate: Bei jedem Production-Deploy wird eine **Wegwerf-Datenbank `nerve_test`** aus einem `pg_dump --schema-only` der Produktion + `alembic upgrade head` gebaut, die volle Pytest-Suite läuft gegen diese echte, über den ganzen Lauf **persistente** Postgres-DB (inkl. echter RLS-Isolations- und Anonymizer-Tests), und nur bei Grün wird deployed. **Ziel der Phase: False-Green / Silent-Failure ausrotten** — aber AUCH keine False-Reds (ein Gate, das jeden Deploy grundlos blockt, ist genauso wertlos). Produktion (`nerve`) darf NIE berührt werden (Whitelist-Guard nur `nerve_test`; trap-Teardown).

## Verlaufs-Kontext (wichtig — Konvergenz)
Diese Pläne wurden über mehrere Pro-Runden gehärtet. Konvergenz der Funde: Runde 1 = 5, Runde 2 = 3, Runde 3 = 1 — alle eingearbeitet:
- **#1–#5** (Runde 1): sudo-`env`-Syntax · session-scope Guard-Read-Engine (UnboundExecutionError) · ft_seed-Scope · training.transcript_archive POST-SUITE-Check · cleanup_rows laute Warnung. Von Pro bestätigt.
- **#6 (BLOCKER)** cleanup_rows macht jetzt als ALLERERSTE Aktion unbedingt `rollback()`, DANN reverse-FK-DELETEs + commit. Von Pro bestätigt.
- **#7 (HOCH)** Baseline-Wächter snapshottet `{pk: xmin}` statt nur PK-Set → fängt committete UPDATE-Mutationen. Von Pro bestätigt.
- **#8 (MITTEL)** `cleanup_tracker(db_session)`-Fixture statt `yield` im Plain-Test-Body. Von Pro bestätigt.
- **#9 (BLOCKER, zuletzt)** die `_baseline_snapshot`-Fixture (Plan 01 Task 6) führt jetzt als ALLERERSTE Aktion `from app import app` aus (erzwingt die Modul-Seeder _seed_prompt_versions/_seed_ewb_v2/_seed_founder_dashboard_defaults gegen nerve_test), BEVOR die {pk:xmin}-Queries laufen — sonst False-Red beim ersten Test. sys.modules-Caching macht den späteren client-app-Import idempotent.

## DEINE AUFGABE — zwei Teile

### Teil 1: Verifiziere den zuletzt eingearbeiteten Fix (#9)
Prüfe: korrekt UND vollständig behoben (wirklich baubar geschlossen)? Führt der frühe `from app import app` in der Snapshot-Fixture einen NEUEN Fehler ein? Konkret:
- Feuern dadurch die Modul-Seeder garantiert VOR dem {pk:xmin}-Snapshot, sodass die Baseline prompt_versions/api_rates/fixed_costs korrekt enthält?
- Ist das sys.modules-Caching-Argument stichhaltig (kein Doppel-Seed beim späteren client-Import)?
- Kollidiert der frühe app-Import mit der bewussten SPÄT-Import-Strategie der client-Fixture (Task 1, „erst nach der Umbindung")? Seedet er gegen die richtige DB (nerve_test via A-1/DATABASE_URL)?
- Bestätige auch, dass #1–#8 unangetastet/intakt sind.

### Teil 2: Frischer adversarialer Sweep (NEUE Probleme)
Unabhängig von #1–#9. Pflicht-Achsen:
- **False-Green:** Gate grün, obwohl RLS/Anonymisierung/Isolation kaputt?
- **False-Red:** Gate rot, obwohl alles korrekt (deterministische Blockade jedes Deploys)?
- **Silent-Failure:** Pipe/Skript/Test schluckt Fehler (exit 0 trotz Crash, leere DB, als PASSED zählender Skip)?
- **Persistente-DB-State-Leak:** geteilte `nerve_test` über den ganzen Lauf — committete Rows, Sequenz-Werte, GUC/Session-Settings, Baseline-Mutation, die einen späteren Test fälschen?
- **Produktions-Sicherheit:** irgendein Pfad, der doch `nerve` statt `nerve_test` berührt? trap/Whitelist wasserdicht?
- **Fixture-/Import-Reihenfolge:** weitere verdeckte Ordering-Annahmen (wie #9) zwischen session-scoped Snapshot, Base-Seed, app-Import, per-Test-Fixtures?

## OUTPUT-FORMAT
Pro Fund: **[SCHWEREGRAD: BLOCKER/HOCH/MITTEL/NIEDRIG]** — Plan-Datei + Task-ID — konkretes Problem — warum False-Green/False-Red/Silent-Failure/Prod-Risiko — präziser Fix.
Für #9 explizit: OK oder nicht-OK (mit Grund); #1–#8 intakt? Am Ende: **GESAMT-VERDIKT: PASS** (bau-frei) **oder BLOCK** (Blocker-Liste) + Gesamt-Risiko (LOW/MED/HIGH).
Sei ehrlich: nichts Neues finden ist ein legitimes Ergebnis — erfinde nichts, nur um etwas zu liefern. Aber wenn etwas Stilles durchrutscht, ist das genau der Fehler, den diese Phase verhindern soll.

---
# UNTEN: Die 4 finalen Plan-Dateien + database/db.py + Persistenz-Enumeration (verbatim)
---
