# ADVERSARIAL RE-REVIEW (RUNDE 2) — Phase 08.23.2.PGTEST (echtes Postgres-Test-Gate)

Du bist ein Senior-Datenbank/DevOps-Engineer und adversarialer Plan-Reviewer. Du siehst diese 4 Plan-Dateien in ihrer FINALEN Form und musst entscheiden: bau-freigeben (PASS) oder blockieren (BLOCK). Du bist bewusst kritisch. Du bist NICHT der Autor.

## Was diese Phase tut (Kontext)
Sie ersetzt das alte SQLite-Test-Gate im `deploy.sh` durch ein echtes Postgres-Gate: Bei jedem Production-Deploy wird eine **Wegwerf-Datenbank `nerve_test`** aus einem `pg_dump --schema-only` der Produktion + `alembic upgrade head` gebaut, die volle Pytest-Suite läuft gegen diese echte, über den ganzen Lauf **persistente** Postgres-DB (inkl. echter RLS-Isolations- und Anonymizer-Tests), und nur bei Grün wird deployed. **Ziel der Phase: False-Green / Silent-Failure ausrotten** — Fälle, in denen das Gate "grün" meldet, obwohl RLS-Mandantentrennung oder Anonymisierung in Wahrheit kaputt sind. Produktion (`nerve`) darf NIE berührt werden (Whitelist-Guard nur `nerve_test`; trap-Teardown).

## Verlaufs-Kontext (wichtig)
Diese Pläne wurden bereits in mehreren Pro-Runden gehärtet. Zuletzt (Runde 1) hast du 5 Funde bestätigt-gefixt und 3 NEUE State-Leak-Funde gemeldet, die jetzt EINGEARBEITET wurden:
- **#6 BLOCKER (Plan 01 Task 5, T-PGTEST-24):** `cleanup_rows` macht jetzt als ALLERERSTE Aktion bedingungslos `rollback()`, DANN erst reverse-FK-DELETEs der committeten IDs + commit (verwirft uncommitteten Müll eines abgestürzten Tests).
- **#7 HOCH (Plan 01 Task 6, T-PGTEST-33):** der Baseline-Wächter snapshottet jetzt `{pk: xmin}` statt nur das PK-Set → committete UPDATE-Mutationen an Baseline-Rows ändern `xmin` → fail-closed. Selbsttest um UPDATE-Fall erweitert.
- **#8 MITTEL (Plan 03/04, T-PGTEST-34):** Executor-Regel: nie `yield` im Plain-Test-Body (→ Generator → Silent-Skip); Cleanup via `cleanup_tracker(db_session)`-Fixture per Argument.

## DEINE AUFGABE — zwei Teile

### Teil 1: Verifiziere die 3 zuletzt eingearbeiteten Fixes (#6/#7/#8)
Prüfe für JEDEN: korrekt UND vollständig behoben (wirklich baubar geschlossen, nicht nur erwähnt)? Führt der Fix selbst einen NEUEN Fehler ein?
- **#6:** Ist die rollback-zuerst-Reihenfolge an JEDER cleanup_rows-Nutzung wirksam? Verwirft der initiale `rollback()` versehentlich auch schon-committete Arbeit (nein, commit ist persistent) — oder genau richtig nur den pending State? Greift es auch, wenn cleanup_rows eine separate Connection statt der Test-Session nutzt?
- **#7:** Ist `{pk: xmin}` der richtige Mechanismus? Deckt der Snapshot ALLE relevanten public-Tabellen ab, in die Tests committen könnten? Kann `xmin` durch etwas anderes als eine echte Test-Mutation wandern (VACUUM/FREEZE während des Laufs)? Ist der Selbsttest aussagekräftig?
- **#8:** Ist die Anweisung glasklar genug, dass ein Executor-Agent NICHT in die yield-im-Body-Falle tappt? Gibt es noch andere Plan-Stellen, die "POST-yield" für Plain-Tests sagen, ohne die Fixture-Regel?

### Teil 2: Frischer adversarialer Sweep (NEUE Probleme)
Unabhängig von #6/#7/#8. Pflicht-Achsen:
- **False-Green:** Wo könnte das Gate grün melden, obwohl RLS/Anonymisierung/Isolation kaputt ist?
- **Silent-Failure:** Wo schluckt eine Pipe/ein Skript/ein Test einen Fehler (exit 0 trotz Crash, leere DB, als PASSED zählender Skip)?
- **Persistente-DB-State-Leak:** geteilte `nerve_test` über den ganzen Lauf — wo kann ein Test State hinterlassen (committete Rows, Sequenz-Werte, GUC/Session-Settings, veränderte Baseline), der einen späteren Test grün/rot fälscht?
- **Produktions-Sicherheit:** irgendein Pfad, der doch `nerve` statt `nerve_test` berühren könnte? trap/Whitelist wasserdicht?
- **Baseline-Seed-Kollisionen:** App-Import sät Rows in die persistente Test-DB — welche globalen `count()`/Unique-Annahmen könnten daran zerschellen?

## OUTPUT-FORMAT
Pro Fund: **[SCHWEREGRAD: BLOCKER/HOCH/MITTEL/NIEDRIG]** — Plan-Datei + Task-ID — konkretes Problem — warum False-Green/Silent-Failure/Prod-Risiko — präziser Fix.
Für #6/#7/#8 explizit: OK oder nicht-OK (mit Grund). Am Ende: **GESAMT-VERDIKT: PASS** (bau-frei) **oder BLOCK** (Blocker-Liste) + Gesamt-Risiko (LOW/MED/HIGH).
Sei ehrlich: nichts Neues finden ist ein legitimes Ergebnis — erfinde nichts. Aber wenn etwas Stilles durchrutscht, ist das genau der Fehler, den diese Phase verhindern soll.

---
# UNTEN: Die 4 finalen Plan-Dateien + database/db.py + Persistenz-Enumeration (verbatim)
---
