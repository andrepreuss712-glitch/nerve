# ADVERSARIAL RE-REVIEW — Phase 08.23.2.PGTEST (echtes Postgres-Test-Gate)

Du bist ein Senior-Datenbank/DevOps-Engineer und adversarialer Plan-Reviewer. Du siehst diese 4 Plan-Dateien zum ersten Mal in ihrer FINALEN Form und musst entscheiden: bau-freigeben oder blockieren. Du bist bewusst kritisch. Du bist NICHT der Autor.

## Was diese Phase tut (Kontext)
Sie ersetzt das alte SQLite-Test-Gate im `deploy.sh` durch ein echtes Postgres-Gate: Bei jedem Production-Deploy wird eine **Wegwerf-Datenbank `nerve_test`** aus einem `pg_dump --schema-only` der Produktion + `alembic upgrade head` gebaut, die volle Pytest-Suite läuft gegen diese echte Postgres-DB (inkl. echter RLS-Isolations- und Anonymizer-Tests), und nur bei Grün wird deployed. **Das Ziel der ganzen Phase ist es, False-Green / Silent-Failure auszurotten** — also Fälle, in denen das Gate "grün" meldet, obwohl die Sicherheit (RLS-Mandantentrennung, Anonymisierung) in Wahrheit kaputt ist. Produktions-Daten dürfen NIE berührt werden (Whitelist-Guard: nur `nerve_test`, nie `nerve`; trap-Teardown).

## DEINE AUFGABE — zwei Teile

### Teil 1: Verifiziere die 5 zuletzt eingearbeiteten Fixes
Eine vorige Pro-Runde fand 5 Funde, die jetzt gefoldet wurden. Prüfe für JEDEN, ob er KORREKT und VOLLSTÄNDIG behoben ist (nicht nur erwähnt — wirklich baubar geschlossen), und ob der Fix selbst keinen NEUEN Fehler einführt:
- **#1 (Plan 02):** `sudo -u nerve_app ANON_PW=val bash -c` war ein Syntax-Crash (sudo behandelt `ANON_PW=val` als auszuführenden Befehl). Fix: `env`-Kommando voranstellen. Sind ALLE Vorkommen (≥4 Spots + Task T-PGTEST-06/T-PGTEST-32) korrekt umgestellt? Ist die Env-Übergabe an `sudo` wirklich syntaktisch korrekt (sudo + env + bash -c Verschachtelung)?
- **#2 (Plan 01 T1 vs T6 → T-PGTEST-31):** Der Aufräum-Wächter (Baseline-Guard) lief im Teardown NACH `engine.dispose()` der db_session/client-Fixtures → er las eine verworfene/unbound Engine → UnboundExecutionError. Fix: Wächter nutzt eine EIGENE session-scope Read-Engine. Ist die Lebensdauer/Reihenfolge jetzt wirklich sauber (Wächter-Engine lebt länger als die Test-Fixture-Engines, wird selbst korrekt entsorgt)?
- **#3 (Plan 03 T8):** `test_ft_seed`/prompt_versions-Test hatte globale `count()==4`, aber der App-Import sät ≥6 prompt_versions (`_seed_prompt_versions`=4 + `_seed_ewb_v2`=2) → deterministischer Fail. Fix: auf test-eigene Module scopen (`filter(module.in_(EXPECTED_MODULES))`) oder baseline-delta. Ist das jetzt robust gegen die persistente nerve_test mit Baseline-Seed?
- **#4 (Plan 01 T6 + Plan 02 → T-PGTEST-30):** Leak-Blindspot `training.transcript_archive` (training-Schema, ORM-los, Mig 0008) — vom public-Wächter UND vom crm-only POST-SUITE-Check ungedeckt; `test_anonymizer_worker` schreibt rein → False-Green. Fix: POST-SUITE-Check um `training.transcript_archive == 0` erweitern. Ist jetzt JEDE Tabelle, in die Tests schreiben, von irgendeinem Leak-Check gedeckt? Gibt es weitere ungedeckte Schreib-Ziele (andere non-public Schemas / ORM-lose Tabellen)?
- **#5 (Plan 01 T5):** `cleanup_rows` schluckte FK-Fehler still (bare except) → defekter Teardown unbemerkt. Fix: lautes `logger.warning` im except. Ist das ausreichend, oder sollte ein nicht-leerer Teardown-Fehler das Gate sogar ROT machen?

### Teil 2: Frischer adversarialer Sweep
Unabhängig von den 5 Fixes: finde NEUE Probleme. Pflicht-Achsen:
- **False-Green:** Wo könnte das Gate grün melden, obwohl RLS/Anonymisierung/Isolation in Wahrheit kaputt ist?
- **Silent-Failure:** Wo schluckt eine Pipe/ein Skript/ein Test einen Fehler (exit 0 trotz Crash, leere DB, übersprungener Test der als PASSED zählt)?
- **Test-Reihenfolge / State-Leak:** persistente `nerve_test` über den Lauf — wo kann ein Test State hinterlassen, der einen späteren Test grün/rot fälscht?
- **Produktions-Sicherheit:** irgendein Pfad, der doch `nerve` (Prod) statt `nerve_test` berühren könnte? trap/Whitelist wasserdicht?
- **Baseline-Seed-Kollisionen:** der App-Import sät Rows in die persistente Test-DB — welche weiteren globalen `count()`-Assertions oder Unique-Constraints könnten daran zerschellen (wie #3 schon zeigte)?

## OUTPUT-FORMAT
Pro Fund: **[SCHWEREGRAD: BLOCKER/HOCH/MITTEL/NIEDRIG]** — Plan-Datei + Task-ID — konkretes Problem — warum es False-Green/Silent-Failure/Prod-Risiko ist — präziser Fix.
Wenn die 5 Fixes sauber sind, sag das explizit pro Fix (#1 OK / #2 OK ...). Am Ende: **GESAMT-VERDIKT: PASS** (bau-frei) **oder BLOCK** (Liste der Blocker) + Gesamt-Risiko (LOW/MED/HIGH).
Sei ehrlich: wenn du nichts Neues findest, erfinde nichts. Aber wenn etwas stilles durchrutscht, ist das genau der Fehler, den diese Phase verhindern soll.

---
# UNTEN: Die 4 finalen Plan-Dateien + database/db.py + Persistenz-Enumeration (verbatim)
---
