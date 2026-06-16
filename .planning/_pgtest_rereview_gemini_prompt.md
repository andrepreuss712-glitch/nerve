Du bist die unabhängige dritte Sicht (Cross-AI Review) im NERVE-Projekt. Antworte AUSSCHLIESSLICH auf Deutsch, knapp und konkret, ADVERSARIAL. Du bist Gegenleser, KEIN Bauarbeiter.

WICHTIG: Die KOMPLETTEN realen Dateien stehen unten im Input (nach diesem Prompt), markiert mit `===== FILE: <pfad> =====`. Ganze Dateien. Bewerte direkt daran.

## Kontext — das ist ein RE-REVIEW
Phase 08.23.2.PGTEST (deploy.sh-Test-Gate gegen persistente app-geseedete Postgres-`nerve_test`, fail-closed, Option-A-Härtung). In DEINEM vorigen adversarialen Review (gemini-3.1-pro) hast du 5 Funde geliefert; alle wurden eingearbeitet:
- **#1** sudo-Env-Crash → `sudo -u nerve_app env ANON_PW=... TEST_DB=... bash -c` (env-Kommando eingefügt, 4 Spots + T-PGTEST-06/32).
- **#2** Baseline-Wächter las disposed Engine → Wächter nutzt jetzt eigene SESSION-SCOPE Read-Engine (`_baseline_guard_engine`), entkoppelt vom per-Test-MODUL-SessionLocal-dispose (T-PGTEST-31).
- **#3** test_ft_seed global count==4 (app-import sät ≥6) → auf test-eigene Module gescoped / baseline-delta (wie tenant_orgs/cost_tracker).
- **#4** Leak-Blindspot training.transcript_archive → POST-SUITE-Check (Plan 02, sudo-postgres) um `training.transcript_archive==0` erweitert (T-PGTEST-30).
- **#5** cleanup_rows schluckte Fehler still → lautes logger.warning im except.

## DEINE AUFGABE (RE-REVIEW)
Zwei Dinge, beide adversarial am realen Code + den 4 Plans:

A) **Sind die 5 Fixes KORREKT + VOLLSTÄNDIG eingearbeitet?** Pro Fix: OK / NICHT-GANZ (was fehlt) / FALSCH. Konkret:
   - #1: ist `env` an ALLEN 4 Spots (interfaces-Skeleton plain-`$`, Task-1-action heredoc-`\$`, key_links-via, T-PGTEST-06)? Stimmt die heredoc-Escapes? Bricht das single-quoted-inner-`bash -c` mit `${ANON_PW}`/`${TEST_DB}` noch korrekt?
   - #2: nutzt der Wächter (Plan 01 Task 6) WIRKLICH eine eigene session-scope Engine, die NICHT vom per-Test-db_session/client-`engine.dispose()` getötet wird? Wird sie am Session-ENDE disposed? Liest sie public.* korrekt (nerve_app, kein RLS auf public)? Ordering noch konsistent (Teardown nach Test-Cleanup)?
   - #3: ist Task 8 jetzt ein konkreter Scope-Fix (`module.in_(EXPECTED_MODULES)` / baseline-delta), KEIN "honest-run" mehr? Sind EXPECTED_MODULES die richtigen 4 (nicht die 2 ewb)?
   - #4: deckt der POST-SUITE-Check jetzt training.transcript_archive==0 ab, fail-closed, als postgres? Ist die Baseline-Annahme (0) korrekt (kein app-import-Seeder schreibt transcript_archive)?
   - #5: laute Warnung im except — bleibt es best-effort (kein Hard-Raise, Wächter = Backstop)?

B) **FRISCHER adversarialer Sweep** (du hast letztes Mal 5 gefunden, die alle anderen übersahen — grabe genauso tief): gibt es einen WEITEREN Blocker/Concern? Achte besonders auf:
   - weitere Leak-Blindspots (ORM-lose / nicht-public Tabellen, in die Tests schreiben, die WEDER public-Wächter NOCH POST-SUITE-Check sieht)
   - Fixture-/Engine-Lifecycle-Fallen (Reihenfolge session- vs function-scope; wer disposed wann; sieht der Wächter wirklich die committeten Rows = autocommit/Transaktions-Sichtbarkeit über getrennte Engines?)
   - deploy.sh-heredoc-Escaping-Fehler (`$` vs `\$`), sudo-Fallen, fail-closed-Lücken
   - False-Green-Pfade (ein echter Defekt bleibt grün) ODER False-Red (ein sauberer Test bricht)
   - Architektur-Widersprüche über die 4 Plans

## Schluss
Pro Fix-#: Verdikt. Plus Sweep-Funde. Gesamt: BLOCK (noch offene Blocker) oder PASS (sauber). Gesamt-Risiko LOW/MED/HIGH + Top-Concerns priorisiert. Wenn nicht am Code verifizierbar, sag es. Code im Ruhezustand ≠ Live — Befunde ggf. „gegen Live gegenprüfen".

--- INPUT (komplette Dateien) folgt ---
