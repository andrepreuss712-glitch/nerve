Du bist die unabhängige dritte Sicht (Cross-AI), Gemini 3.1 Pro, im ADVERSARIALEN Modus. Read-only — ändere/führe NICHTS aus. Antworte auf Deutsch.

WICHTIG: Ein vorheriger SCHWÄCHERER Durchlauf (Gemini Flash) hat jede Naht abgelaufen und „OK" gestempelt, ohne Neues zu finden — reine Nacherzählung der Plan-Logik. DU sollst das NICHT tun. Suche AKTIV nach Fehlern, besonders False-Green (Test passt grün, obwohl was kaputt/geleakt ist) und False-Red (Gate bricht ohne echten Grund). Sei streng. Wenn wirklich nichts ist, sag das — aber suche ernsthaft, nicht bestätigend.

KONTEXT: Phase 08.23.2.PGTEST = pytest gegen EINE persistente Postgres-`nerve_test` (statt fresh-per-test SQLite). Deploy-Gate ist FAIL-CLOSED. Lösung „Option A" (gezieltes Test-Härten) + 2 Erweiterungen: (1) cleanup_rows-Teardown-Helfer, (2) autouse Baseline-Cleanup-Wächter (public.* per-test in-pytest als nerve_app; crm.* POST-SUITE via sudo-postgres). Die 4 PLAN-Files + database/db.py + die Enumeration stehen UNTEN INLINE — du brauchst KEINE Tool-Calls.

PRÜFE GEZIELT (das, was ein Rubber-Stamp übersieht):
1. Baseline-Wächter False-Green: Kann er grün durchlassen, obwohl ein Leak existiert? Prüfe: (a) eine public-Daten-Tabelle, die er NICHT im Snapshot hat aber Leaks bekommt; (b) ein Test, der committet aber dessen Rows der per-test-Snapshot-Vergleich nicht erfasst; (c) Timing autouse-Wächter-Teardown vs. test-eigenem cleanup (läuft der Wächter WIRKLICH zuletzt?); (d) was, wenn der Test selbst mit Exception crasht — feuert der Wächter dann noch?
2. cleanup_rows Edge-Cases: Mehr-Mandanten-crm-Test, FK-Reihenfolge, best-effort-Schlucken (versteckt es einen echten Fehler?), nicht-registriertes FK-Kind.
3. Hybrid public/crm: Deckt er ALLE Leak-Pfade? Sieht der POST-SUITE-crm-Check (sudo-postgres) WIRKLICH alle Tenants (RLS-Bypass)? Lücke zwischen „public per-test" und „crm post-suite"?
4. A-1-Tripwire ↔ crm-Baseline=0: Race oder Pfad, in dem die Tripwire-crm-Zeile NICHT auf 0 geht?
5. Persistenz: Ist WIRKLICH keine globale ungescopte count()/all() mehr übrig? Flash bestätigte test_tenant_orgs + test_cost_tracker als gefixt — gibt es einen DRITTEN/übersehenen?
6. Cross-Plan: Plan 03/04 parallel-sicher (disjunkt)? Base-Seed Sequenz-Advance vs. hardcoded id=1 — Kollision?
7. Irgendein Risiko, das KEINE bisherige Sicht (Claudian-Tiefen-Audit, Plan-Checker, Flash) genannt hat.

BEKANNT-ERLEDIGT — NICHT re-litigieren, nur bestätigen falls relevant: Option-2 (Transaktions-Rollback) wurde wegen RLS-GUC-Leak (db.py:92 `if not tid: return` löscht GUC nie + SET LOCAL überlebt Savepoint-Release) verworfen → Option A. test_tenant_orgs:65 + test_cost_tracker:51 globale counts → auf test-eigene IDs gescopt.

AUSGABE: VERDIKT (PASS / FLAG / BLOCK) + Gesamt-Risiko. Pro Fund: Schweregrad (BLOCKER/HOCH/MITTEL/NIEDRIG) + Datei:Zeile + konkreter Fix. Was du nicht gegen den laufenden Server verifizieren kannst: ehrlich sagen.

==================== INLINE-DATEIEN ====================

########## DATEI: .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-01-conftest-fixtures-PLAN.md ##########
---
phase: 08.23.2.PGTEST
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tests/conftest.py
  - tests/test_rls_generic_smoke.py
  - tests/test_baseline_guard.py
  - CLAUDE.md
autonomous: true
requirements: [Req-2, Req-5, Req-9]
complexity: "🔴 (security-near — RLS fixture wiring, DSN redirect away from prod nerve, Baseline-Cleanup-Wächter PUBLIC.*-only in-pytest; crm.* via POST-SUITE-Check in Plan 02)"
user_setup: []
# HYBRID-Entscheidung (André locked 2026-06-15, Option 1): der in-pytest autouse Baseline-Wächter (Task 6)
# prueft NUR public.* Daten-Tabellen (nerve_app liest public unfiltered — kein RLS auf public). crm.* wird
# NICHT aus pytest geprueft (nerve_app ist tenant-gefiltert, saehe Cross-Tenant-Leaks nicht) — stattdessen
# POST-SUITE in deploy.sh (Plan 02) via `sudo -u postgres psql` (peer-auth, passwordless, EXAKT das
# SCHILD-Guard-Muster), das nach dem pytest-Lauf assertet jede crm.* Tabelle == ihre Baseline. Daher KEIN
# NERVE_BASELINE_GUARD_DSN, KEINE postgres-scram-DSN, KEINE BYPASSRLS-Rolle, KEIN Superuser-PW im Test-Env.
# crm.*-Baseline = 0 Rows in jeder crm.* Tabelle (kein app-import-Seeder beruehrt crm.*) → jeder crm-Writer
# (Security-Tests + A-1-Tripwire falls er eine crm.accounts-Row committet + jeder geportete crm-Test) MUSS im
# Teardown auf 0 zurueckraeumen (via cleanup_rows). Cross-ref Plan 02 POST-SUITE-crm-Check.

must_haves:
  truths:
    - "Generische Fixtures db_session + client verbinden gegen Postgres-nerve_test (kein hardcoded sqlite)"
    - "Generische crm-berührende Tests sehen ihre Zeilen (Tenant-Kontext gesetzt, RLS nicht fail-closed)"
    - "Kein Fixture-DSN zeigt im Test-Lauf auf die Produktions-nerve-DB"
    - "Die 3 Spezial-Fixtures (nerve_app_pg_conn / anon_worker_pg_engine / schild_guard_pg_conn) lesen DSNs die auf nerve_test zeigen"
    - "Ein dedizierter A-1-Tripwire auf dem GENERISCHEN db_session-Pfad asserted (a) current_setting('app.tenant_id') == TEST_TENANT_UUID (NON-null, beweist der after_begin-Hook feuerte) UND (b) ein realer crm-Read unter dem Tenant liefert >=1 Zeile — dreht den DATABASE_URL-unset-False-Green (A-1) von silent-green auf loud-red"
    - "Ein Session-Scope Base-Seed (Org+User id=1, trigger-aware, Sequenzen advanced) existiert, sodass FK-tragende generische Tests (user_id=1/org_id=1) auf der leeren nerve_test-PG nicht an FK/NOT-NULL brechen"
    - "Die client-Fixture re-exponiert den _test_session/_test_engine-Vertrag (MODUL-SessionLocal-PG-Session + nerve_test-Engine), sodass db_from_client + die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) WEITER funktionieren (kein AttributeError → kein fail-closed Gate-Block)"
    - "Ein gemeinsamer Cleanup-Helfer (Extension 1: cleanup_rows in conftest.py) existiert, der committete Rows eines Tests in reverse-FK-Reihenfolge unter dem richtigen Tenant-GUC (crm.*) best-effort wieder löscht — die EINE kanonische Teardown-Mechanik für alle committenden Tests"
    - "Eine Konvention ist BEIDE dokumentiert: als Docstring/Kommentar oben in conftest.py UND als neue Regel in CLAUDE.md ('Tests, die Daten in nerve_test committen, räumen ihre eigenen Rows im Teardown via dem gemeinsamen Cleanup-Helfer wieder weg')"
    - "Ein autouse Baseline-Cleanup-Wächter (Extension 2: _baseline_cleanup_guard) existiert, der nach JEDEM Test die PUBLIC.* Daten-Tabellen gegen einen am Session-Start gefrorenen BASELINE-Snapshot prüft (PK-Set pro relevanter public-Tabelle == Baseline). Extra/fehlende Rows → FAIL-CLOSED, nennt nodeid + Tabelle + die leaked/missing PKs. Der Wächter liest public.* via die MODUL-Session (nerve_app, kein RLS auf public). crm.* wird NICHT in-pytest geprueft (nerve_app saehe nur einen Tenant) — die crm.*-Baseline (0 Rows pro crm.* Tabelle) wird POST-SUITE in deploy.sh (Plan 02) via sudo-postgres geprueft (HYBRID, André locked)"
    - "Jeder committende Test (Group A + Group B) ist baseline-sauber: nach seinem Teardown == public-Baseline (in-pytest-Wächter grün) UND jede crm.* Tabelle == 0 Rows (POST-SUITE-crm-Check in Plan 02 grün). Security-Tests (rls_isolation/meeting_save_rls/nerve_app_pg/anon_worker) + der A-1-Tripwire (falls er eine crm.accounts-Row committet) + jeder geportete crm-Test räumen ihre crm.*-Rows in ihrem eigenen Teardown via cleanup_rows auf 0 zurück → POST-SUITE-crm-Check grün; leaken sie → der POST-SUITE-Check (Plan 02) faengt es = echter Fund (gewollt)"
  artifacts:
    - path: "tests/conftest.py"
      provides: "PG-basierte generische Fixtures + TEST_TENANT_UUID-Konstante + tenant_orgs-Seed + set_current_tenant-Aufruf + Session-Scope Base-Seed (Org+User id=1, Sequenz-Advance) + client._test_session/_test_engine-Vertrag (MODUL-SessionLocal) + db_from_client unverändert + cleanup_rows-Helfer (Extension 1) + Konventions-Docstring + _baseline_cleanup_guard autouse-Fixture (Extension 2) PUBLIC.*-only (crm.* POST-SUITE in Plan 02)"
      contains: "TEST_TENANT_UUID"
    - path: "tests/test_rls_generic_smoke.py"
      provides: "A-1-Tripwire: GUC-NON-null-Assertion + crm-Read-≥1-Zeile auf dem generischen db_session-Pfad"
      contains: "current_setting"
    - path: "tests/test_baseline_guard.py"
      provides: "Selbst-Test des Baseline-Wächter-Mechanismus: ein Test der absichtlich eine Row committet und NICHT aufräumt MUSS den Wächter rot machen (beweist der Wächter feuert); ein sauberer Test passiert"
      contains: "_baseline_cleanup_guard"
    - path: "CLAUDE.md"
      provides: "Neue Test-Cleanup-Konventionsregel (committende Tests räumen ihre Rows via cleanup_rows im Teardown weg; public.* vom in-pytest-Baseline-Wächter erzwungen, crm.* vom POST-SUITE-crm-Check in Plan 02 auf 0 Rows erzwungen)"
      contains: "Cleanup-Helfer"
    - path: "prisma/schema.prisma"
      provides: "(n/a — kein Prisma in diesem Projekt; Platzhalter entfällt)"
  key_links:
    - from: "tests/conftest.py db_session/client"
      to: "database.db.set_current_tenant + after_begin-Hook"
      via: "set_current_tenant(TEST_TENANT_UUID) am Fixture-Start"
      pattern: "set_current_tenant\\("
    - from: "tests/conftest.py db_session/client"
      to: "TEST_DATABASE_URL → nerve_test"
      via: "os.environ['TEST_DATABASE_URL'] create_engine"
      pattern: "TEST_DATABASE_URL"
    - from: "tests/conftest.py client._test_session/_test_engine + db_from_client"
      to: "die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)"
      via: "client re-exponiert _test_session = dbmod.SessionLocal() (MODUL, hook-bearing) + _test_engine = engine; db_from_client returnt client._test_session unverändert"
      pattern: "_test_session|_test_engine|db_from_client"
    - from: "tests/conftest.py Base-Seed"
      to: "public.organisations + public.users (id=1) + Sequenz-Advance"
      via: "session-scoped autouse fixture gegen die MODUL-Engine (nerve_test via A-1-DATABASE_URL)"
      pattern: "setval\\('(organisations|users)_id_seq'"
    - from: "tests/test_rls_generic_smoke.py"
      to: "current_setting('app.tenant_id') + crm-Read"
      via: "db_session-Fixture (Hook gefeuert) + SELECT auf crm unter Tenant-GUC"
      pattern: "current_setting\\('app.tenant_id'"
    - from: "tests/conftest.py committende Tests"
      to: "cleanup_rows-Helfer (Extension 1)"
      via: "Test registriert seine committeten Row-IDs + ruft cleanup_rows in der POST-yield-Sektion"
      pattern: "cleanup_rows\\("
    - from: "tests/conftest.py _baseline_cleanup_guard (Extension 2)"
      to: "public-Baseline-Snapshot (Session-Start) vs. Post-Test-public-DB-State"
      via: "autouse per-test fixture, POST-yield NACH dem Test-eigenen Cleanup; NUR public.* via MODUL-Session gelesen (nerve_app, kein RLS); crm.* NICHT in-pytest — POST-SUITE-Check in Plan 02"
      pattern: "_baseline_cleanup_guard"
---

<objective>
<!-- Option-A persistence-hardening fold 2026-06-15: cleanup-helper + baseline-guard (à la SCHILD) + Gruppe-A/B-Fixes; Option-2 verworfen (RLS-GUC-Leak db.py:92). -->
<!-- FK-debt fold 2026-06-15: base-seed (Plan 01) + 5 deltas (Plan 03) — André/Claudian-bestätigte 11-Test-Klassifikation (11 A / admin_dashboard→SAFE / 24 SAFE), kein Split. -->
<!-- revised via --reviews 2026-06-15: Gemini-Findings eingearbeitet — HIGH (client RLS-Hook-Verlust → MODUL-SessionLocal.configure(bind=engine) statt frischer sessionmaker), MEDIUM (SessionLocal.configure(bind=None)-Reset im finally beider Fixtures), LOW (Tenant-Seed-Org-Name uuid-suffixed). -->
<!-- pre-execute audit fold 2026-06-15: A-1 Hook-Präkondition (Hard precondition statt Annahme: db.py registriert den after_begin-Hook beim Import NUR wenn DATABASE_URL — nicht TEST_DATABASE_URL — non-sqlite ist → Gate (Plan 02) MUSS DATABASE_URL=postgres exportieren). F1: test_tenant_orgs-RLS-Proof-Referenz entfernt (public-only, beweist RLS NICHT) und durch dedizierten A-1-Tripwire ersetzt. -->
<!-- db_from_client contract fix + ft_seed/postcall_split precision 2026-06-15 -->
Refactor `tests/conftest.py` so die generischen Fixtures (`db_session`, `client`) gegen die echte
Postgres-Wegwerf-DB `nerve_test` verbinden (statt hardcoded `sqlite:///:memory:`), einen Default-Test-
Mandanten setzen (D-05, sonst RLS-fail-closed → 0 Zeilen), und die 3 bestehenden Spezial-Fixtures
deren DSN-Env-Var so liefert, dass sie auf `nerve_test` (nicht Prod-`nerve`) zeigen. ZUSÄTZLICH (pre-execute
audit, A-1-Tripwire): ein dedizierter Smoke-Test auf dem generischen db_session-Pfad, der beweist dass der
after_begin-RLS-Hook tatsächlich feuert (GUC NON-null) und ein crm-Read >=1 Zeile liefert (nicht 0).
ZUSÄTZLICH (FK-debt fold, Task 4): ein Session-Scope Base-Seed (1 Org + 1 User id=1) gegen nerve_test, damit
die FK-tragenden generischen Tests (user_id=1/org_id=1 auf PUBLIC-Tabellen) auf der schema-only/zero-data
nerve_test-PG nicht an ForeignKey/NOT-NULL brechen (die 11-Test-FK-Klassifikation, 6 davon konsumieren diesen
Base-Seed direkt). KRITISCH (pre-execute blocker fix 2026-06-15): der `client`-Rewrite (MODUL-SessionLocal-
Umbindung) MUSS den bestehenden `_test_session`/`_test_engine`-Vertrag re-exponieren, sodass `db_from_client`
+ die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)
NICHT an AttributeError zerbrechen (sonst fail-closed Gate blockt jeden Deploy).

ZUSÄTZLICH (Option-A persistence-hardening fold 2026-06-15 — André wählte OPTION A, NICHT Option-2-Rollback):
Option-2 (Per-Test-Transaktions-Rollback) ist VERWORFEN — bei Join-External-Transaction teilt sich der ganze
Test EINE Connection, und der RLS-after_begin-Hook (db.py:88) setzt app.tenant_id transaktions-lokal, CLEART
ihn aber NIE (`if not tid: return`, db.py:92) → unter Option-2's einer langer Transaktion + Savepoints würde der
Tenant-GUC zwischen Test-Schritten LEAKEN → RLS-False-Green, genau das was diese Phase eliminiert. Daher KEEPEN
wir das produktionstreue Real-Commit-Modell und HÄRTEN die endliche Liste committender Tests mit ZWEI neuen
conftest-Bausteinen:
(Extension 1, Task 5) ein gemeinsamer `cleanup_rows`-Teardown-Helfer — jeder committende Test registriert seine
erzeugten Row-IDs und löscht sie reverse-FK-clean unter dem richtigen Tenant-GUC (best-effort, à la
test_rls_isolation.py:102-116) — PLUS eine Ein-Zeilen-Konvention, dokumentiert in conftest.py UND in CLAUDE.md.
(Extension 2, Task 6) ein autouse Baseline-Cleanup-WÄCHTER (`_baseline_cleanup_guard`, à la SCHILD-Symptom-Guard):
snapshottet am Session-Start (nach app-import-Seeds + Base-Seed) das erlaubte PK-Set jeder relevanten PUBLIC.*
Daten-Tabelle und asserted nach JEDEM Test, dass der public-DB-State == Baseline ist (kein Test-Müll). Fail-closed,
nennt nodeid+Tabelle+geleakte/fehlende PKs. public.* liest er via die MODUL-Session (nerve_app, kein RLS auf
public → unfiltered). HYBRID-ENTSCHEIDUNG (André locked 2026-06-15, Option 1) zur crm-Sichtbarkeits-Falte: crm.*
hat FORCE-RLS und der Hook cleart den GUC nie → als nerve_app saehe der in-pytest-Wächter crm.* nur tenant-
gefiltert (verpasst Cross-Tenant-Leaks). Statt einen superuser/BYPASSRLS-Lesepfad ins Test-Env zu holen, wird
crm.* NICHT in-pytest geprueft, sondern POST-SUITE in deploy.sh (Plan 02) via `sudo -u postgres psql` (peer-auth,
passwordless — EXAKT das SCHILD-Guard-Muster): nach dem pytest-Lauf assertet ein psql-Schritt, dass jede crm.*
Tabelle == ihrer Baseline ist. Die crm.*-Baseline = 0 Rows in jeder crm.* Tabelle (kein app-import-Seeder beruehrt
crm.*) → jeder crm-Writer (Security-Tests + der A-1-Tripwire falls er eine crm.accounts-Row committet + jeder
geportete crm-Test) MUSS im Teardown via cleanup_rows auf 0 zurueckraeumen. KEIN NERVE_BASELINE_GUARD_DSN, KEINE
postgres-scram-DSN, KEINE BYPASSRLS-Rolle, KEIN Superuser-PW im Test-Env (Briefing-Vorgabe).

Purpose: Req-2 (conftest honoriert Test-DSN), Req-5 (kein Prod-DB-Kontakt), Teil-Grundlage für Req-9.
Diese Fixtures sind die Vertrags-Schicht, gegen die Plan 02 (Gate) und Plan 03 (Klasse-A-Port + 5 Deltas) bauen.
Die Extensions 1+2 sind die STRUKTURELLE Durchsetzung der Baseline-Sauberkeit, gegen die Plan 03 + Plan 04 bauen
(jeder committende Test adoptiert cleanup_rows und MUSS den Baseline-Wächter passieren).
Output: refactored conftest.py mit PG-Fixtures + TEST_TENANT_UUID + tenant_orgs-Seed + A-1-Tripwire-Test +
Session-Scope Base-Seed (Org+User id=1, Sequenz-Advance) + re-exponiertem client._test_session/_test_engine-
Vertrag (MODUL-SessionLocal) + unverändertem db_from_client + cleanup_rows-Helfer + Baseline-Cleanup-Wächter +
CLAUDE.md-Konventionsregel + tests/test_baseline_guard.py-Mechanismus-Selbsttest.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-CONTEXT.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md

<interfaces>
<!-- Verträge aus dem Codebase. Executor nutzt diese direkt — keine Exploration nötig. -->

Aus database/db.py (RLS-GUC-Plumbing, db.py:65-103):
```python
_current_tenant_id = contextvars.ContextVar("nerve_tenant_id", default=None)
def set_current_tenant(tid):  # tid = String-UUID; publiziert in contextvar
def clear_current_tenant():
# after_begin-Hook _set_tenant_txn_local (db.py:87): NUR registriert wenn 'sqlite' not in _DATABASE_URL (db.py:86).
# Hängt zur IMPORT-ZEIT an SessionLocal (Modul-Engine). Liest _current_tenant_id, issued
#   SELECT set_config('app.tenant_id', %s, true)  (transaktions-lokal, parametrisiert)
# Ohne Tenant → GUC NULL → RLS fail-closed → 0 Zeilen.
# WICHTIG: der Hook hängt am MODUL-SessionLocal. Eine FRISCHE sessionmaker(bind=engine) trägt ihn NICHT.
# OPTION-2-KILLER (db.py:92): `if not tid: return` — der Hook CLEART app.tenant_id NIE. Unter einer
#   einzelnen langen Per-Test-Transaktion (Option-2 join-external-txn) + Savepoints würde der GUC zwischen
#   Test-Schritten LEAKEN -> RLS-False-Green. Deshalb Real-Commit-Modell + Baseline-Wächter (Option A).
```

**A-1 HARD PRECONDITION (pre-execute audit 2026-06-15 — KEINE Annahme, eine Voraussetzung):**
Der after_begin-RLS-Hook (db.py:87) wird zur IMPORT-ZEIT registriert AUSSCHLIESSLICH wenn `DATABASE_URL`
(NICHT `TEST_DATABASE_URL`) non-sqlite ist — denn db.py:9 liest `_DATABASE_URL = os.environ.get('DATABASE_URL',
'sqlite:///database/nerve.db')` und db.py:86 entscheidet `if 'sqlite' not in _DATABASE_URL`. DESHALB MUSS das
Gate (Plan 02, FIX 1) in der pytest-Subshell `DATABASE_URL=postgresql://nerve_app@/nerve_test` exportieren —
sonst sieht db.py den sqlite-Default und registriert den Hook NIE. `SessionLocal.configure(bind=engine)`
(diese Plan-01-Fixtures) bewahrt einen import-zeit-registrierten Listener, kann aber KEINEN erzeugen der nie
registriert wurde. Wenn DATABASE_URL fehlt → Hook nie da → set_current_tenant inert → crm-Reads 0 Zeilen →
False-Green. Der A-1-Tripwire (tests/test_rls_generic_smoke.py, dieser Plan) macht diesen Defekt loud-red.
Cross-ref Plan 02 FIX 1 (T-PGTEST-18). **Der Base-Seed (Task 4) hängt am SELBEN A-1-Fakt:** weil das Gate
DATABASE_URL=postgres exportiert, IST die MODUL-Engine (`database.db.engine`/`SessionLocal`/`get_session()`)
beim Import bereits nerve_test-PG — der Base-Seed läuft also gegen live nerve_test mit aktiver RLS-Machinerie
(commit d7d8358 belegt: der Gate-pytest-Subshell exportiert DATABASE_URL=postgresql://nerve_app@/nerve_test).

**Baseline-Wächter PUBLIC.*-only-Mechanismus (Extension 2, Task 6 — HYBRID, André locked 2026-06-15, Option 1):**
Die pytest-Subshell läuft als OS-User `nerve_app` (Plan 02 Z.149 `sudo -u nerve_app ... bash -c '...pytest...'`).
`nerve_app` ist `rolbypassrls=f` + NICHT-Owner von crm.* (RESEARCH Q1a bewiesen) → liest crm.* NUR tenant-gefiltert.
Ein in-pytest Baseline-Wächter, der crm.* als nerve_app liest, sähe IMMER nur EINEN Tenant → er VERPASST
Cross-Tenant-Leaks. ENTSCHEIDUNG (André, gegen das Holen eines Superuser-Lesepfads ins Test-Env): der in-pytest
Wächter prüft NUR public.* (nerve_app liest public unfiltered — kein RLS auf public); crm.* wird POST-SUITE in
deploy.sh (Plan 02) geprüft. Konkret:
- **public.* (in-pytest, dieser Plan):** der `_baseline_cleanup_guard` snapshottet + asserted das PK-Set jeder
  relevanten public Daten-Tabelle über die normale MODUL-Session (nerve_app, kein RLS). Fail-closed pro Test mit
  nodeid+Tabelle+leaked/missing PKs.
- **crm.* (POST-SUITE, Plan 02):** NICHT in pytest. Nach dem pytest-Lauf, VOR dem trap-Teardown, fuehrt deploy.sh
  einen `sudo -u postgres psql -d "$TEST_DB"` Schritt aus (peer-auth, passwordless — EXAKT das SCHILD-Guard-Muster,
  KEINE neue Env-Var, KEIN PW), der `SELECT count(*)` ueber alle crm.* Tabellen summiert und assertet == 0
  (crm.*-Baseline ist leer). Als `postgres` (superuser) bypassed psql FORCE-RLS vollstaendig → es sieht crm.* ALLER
  Tenants → Cross-Tenant-Leaks werden gefangen. Leak (>0) → exit≠0 → kein Restart/Deploy (fail-closed).
- **crm.*-Baseline = 0:** kein app-import-Seeder committet crm.* (PERSISTENCE-ENUMERATION: crm.* leer in der
  Baseline). Daher MUSS jeder crm-Writer (Security-Tests test_rls_isolation/test_meeting_save_rls/anonymizer-
  RLS-Gruppe + der A-1-Tripwire test_rls_generic_smoke falls er eine crm.accounts-Row committet + jeder geportete
  crm-Test) im Teardown via cleanup_rows auf 0 zurueckraeumen. Culprit-Narrowing ist trivial (nur ~4 crm-Writer).
- **KEIN** NERVE_BASELINE_GUARD_DSN, **KEINE** postgres-scram-DSN, **KEINE** BYPASSRLS-Rolle, **KEIN** Superuser-PW
  im Test-Env (Briefing-Vorgabe). `sudo -u postgres psql` nutzt OS-peer-auth — dieselbe passwordless Mechanik, die
  der bestehende SCHILD-Guard-Schritt in Plan 02 bereits verwendet.

**client-Vertrag _test_session/_test_engine + db_from_client (pre-execute blocker fix 2026-06-15 — KEINE Annahme, IST-Stand verifiziert):**
Der IST-`client` (conftest.py:84-86) exponiert ZWEI Attribute, von denen ~20 Gate-Tests abhängen:
```python
# conftest.py:84  c._test_session = TestSession()
# conftest.py:85  c._test_engine = engine
# conftest.py:95-97  db_from_client-Fixture:  return client._test_session
```
KONSUMENTEN (verifiziert gegen live source — würden bei AttributeError im Setup zu pytest exit≠0 → fail-closed Gate → blockt JEDEN Deploy):
- `tests/test_admin_dashboard_auth.py` — 4 Tests nutzen `db_from_client` (z.B. Z.25-26, 34-35, 46-47, 55-56). FK-klassifiziert SAFE → KEINE Test-Datei-Edits nötig, nur der conftest-Vertrag entblockt sie.
- `tests/test_auth_next_redirect.py:106` — `db = client._test_session` (direkter Zugriff). SAFE → keine Edits.
- `tests/test_ewb_rate_api.py` — ~11 Tests nutzen `db_from_client` (Z.75-76, 94-95, … 211-213). Delta #8 (Plan 03 Task 6) deckt die FK-Seite ab; der db_from_client-Vertrag muss intakt sein.
- `tests/test_profile_editor_validation.py` — 4 Tests nutzen `db_from_client` UND `client._test_engine` (Z.57-60, 74-77, 91-94, 108-111). Delta #9 (Plan 03 Task 7) deckt die FK-Seite ab.
DESHALB MUSS der `client`-Rewrite in Task 1 — NACH `dbmod.SessionLocal.configure(bind=engine)` + set_current_tenant, VOR `yield c` — den Vertrag re-exponieren:
```python
c._test_session = dbmod.SessionLocal()   # MODUL-SessionLocal (hook-bearing PG-Session), NICHT eine frische sessionmaker
c._test_engine = engine                  # die nerve_test-PG-Engine
```
und im finally `c._test_session.close()` (best-effort) zusätzlich zum bestehenden `configure(bind=None)` + `engine.dispose()`.
`db_from_client` (conftest.py:95-97) bleibt UNVERÄNDERT (`return client._test_session`) — es returnt jetzt eine
PG-gebundene, hook-tragende MODUL-SessionLocal-Session. So funktionieren die 4 Konsumenten-Dateien WEITER
ohne Edits über die Plan-03-Deltas (#8/#9) hinaus.

Aus database/models.py (Base-Seed-Vertrag — EXAKTE NOT-NULL-Spalten ohne DB-Default, verifiziert):
```
Organisation (__tablename__='organisations'):
  id    Integer PK
  name  String(200) NOT NULL, KEIN Default  ← muss gesetzt werden
  (alle übrigen NOT-NULL-relevanten Spalten haben Python-Defaults: plan='starter', dsgvo_modus=True,
   subscription_status='inactive', plan_typ='bundle', billing_country='Deutschland', diverse Integer-Defaults)
  coach_id  FK→users.id, nullable=True (kein Problem; Org wird VOR User geseedet)

User (__tablename__='users'):
  id            Integer PK
  org_id        Integer FK→organisations.id, NOT NULL  ← = die Base-Org-id (1)
  email         String(200) UNIQUE NOT NULL, KEIN Default  ← z.B. 'pgtest-base@nerve.local'
  passwort_hash String(256) nullable=True  ← darf NULL bleiben (OAuth-Sentinel-Spalte)
  rolle         String(50) default='member'
  is_superadmin Boolean NOT NULL, default=False  ← Python-Default
  is_test_user  Boolean NOT NULL, default=False  ← Python-Default
  market        String(10) NOT NULL, default='dach'  ← Python-Default
  language      String(10) NOT NULL, default='de'   ← Python-Default
```
**KRITISCHER Hinweis (Python-Default ≠ DB-Default):** `is_superadmin`, `is_test_user`, `market`, `language`
sind `nullable=False` ABER haben nur ein SQLAlchemy-PYTHON-`default=` (kein `server_default`). Ein RAW-SQL
`INSERT` (psycopg2/`text()`) würde diese Spalten NICHT füllen → NOT-NULL-Verletzung. DESHALB MUSS der
Base-Seed den ORM-Pfad nutzen (`session.add(Organisation(id=1, name=...))` / `session.add(User(id=1,
org_id=1, email=..., ...))`) ODER beim RAW-Insert diese 4 Spalten EXPLIZIT mitsetzen. ORM-Pfad ist der
robuste Default (Python-Defaults greifen automatisch).

Aus tests/conftest.py (IST-Stand, zu ändern):
- db_session (Z.41-51): `create_engine("sqlite:///:memory:")` + create_all + Session.
- client (Z.54-91): IST-Stand baut eine FRISCHE `TestSession = _sm(...)` (sessionmaker) und
  monkeypatcht database.db.{engine,SessionLocal,db_session} auf diese frische Session +
  `sqlite:///:memory:`-Engine. DIESE frische sessionmaker verliert den after_begin-RLS-Hook
  (der hängt am MODUL-SessionLocal, db.py:87) → MUSS auf MODUL-`SessionLocal.configure(bind=engine)` umgebaut werden.
  WICHTIG: der IST-client exponiert ZUSÄTZLICH `c._test_session = TestSession()` (Z.84) + `c._test_engine = engine`
  (Z.85) — der Rewrite MUSS diesen Vertrag re-exponieren (s.o. client-Vertrag-Block), sonst AttributeError in ~20 Tests.
- db_from_client (Z.94-97): `return client._test_session` — bleibt UNVERÄNDERT, returnt nach dem Rewrite die MODUL-SessionLocal-PG-Session.
- nerve_app_pg_conn (Z.111-132): liest `NERVE_APP_TEST_DSN`, psycopg2, autocommit=False, rollback im finally. SKIP wenn DSN fehlt.
- anon_worker_pg_engine (Z.146-158): liest `ANON_WORKER_TEST_DSN`, SQLAlchemy-Engine. SKIP wenn DSN fehlt.
- schild_guard_pg_conn (Z.172-190): liest `NERVE_SCHILD_TEST_DSN`, psycopg2, autocommit=True. SKIP wenn DSN fehlt.

Aus tests/test_rls_isolation.py:33-54 (Trigger-tenant_orgs-Muster, EXAKT wiederverwenden):
```python
# INSERT org → AFTER-INSERT-Trigger trg_mk_tenant_org erzeugt tenant_orgs-Row automatisch
cur.execute("INSERT INTO public.organisations (name) VALUES (%s) RETURNING id", (...,))
org_id = cur.fetchone()[0]
cur.execute("SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s", (org_id,))
tenant_id = cur.fetchone()[0]  # DIESE UUID ist set_current_tenant-fähig
```

Aus tests/test_rls_isolation.py:82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — für den A-1-Tripwire-crm-Read):
```python
cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))
cur.execute("INSERT INTO crm.accounts (id, tenant_id, name) VALUES (%s, %s, %s)", (acct_id, tid, "[RLS-TEST] account ..."))
cur.execute("INSERT INTO crm.account_memory (id, tenant_id, account_id, meddpicc, context_hooks) VALUES (...)", ...)
```

Aus tests/test_rls_isolation.py:101-116 (Best-Effort-Reverse-FK-Teardown in der POST-yield-Sektion — das EXAKTE Vorbild für cleanup_rows, Extension 1):
```python
# POST-yield (nach dem `yield`): pytest führt das auch bei Assertion-Fehler aus (finally-Äquivalent).
cur = conn.cursor()
try:
    for tid in (tenant_a, tenant_b):
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tid,))   # crm.* nur unter Tenant-GUC löschbar
        cur.execute("DELETE FROM crm.account_memory WHERE tenant_id = %s::uuid", (tid,))
        cur.execute("DELETE FROM crm.accounts WHERE tenant_id = %s::uuid", (tid,))
    conn.commit()
    cur = conn.cursor()
    cur.execute("DELETE FROM public.tenant_orgs WHERE id IN (%s::uuid, %s::uuid)", (tenant_a, tenant_b))
    cur.execute("DELETE FROM public.organisations WHERE id IN (%s, %s)", (org_a, org_b))
    conn.commit()
except Exception:
    conn.rollback()
```

Gate-DSN-Mapping (RESEARCH Q2c — was Plan 02 inline setzt; conftest LIEST diese Env-Vars):
| Env-Var | Wert im Gate |
|---------|--------------|
| DATABASE_URL | postgresql://nerve_app@/nerve_test  (A-1: damit db.py den after_begin-Hook beim Import registriert UND die MODUL-Engine = nerve_test ist, gegen die der Base-Seed läuft) |
| TEST_DATABASE_URL | postgresql://nerve_app@/nerve_test  (peer-socket, NEU für db_session/client) |
| NERVE_APP_TEST_DSN | postgresql://nerve_app@/nerve_test |
| NERVE_SCHILD_TEST_DSN | postgresql://nerve_app@/nerve_test |
| ANON_WORKER_TEST_DSN | postgresql://nerve_anon_worker:<pw>@127.0.0.1:5432/nerve_test (scram) |
| (crm-Baseline-Check) | KEINE Env-Var/DSN — POST-SUITE in deploy.sh (Plan 02) via `sudo -u postgres psql` (peer-auth, passwordless, SCHILD-Muster); assertet jede crm.* Tabelle == 0 Rows. HYBRID (André locked); ersetzt das frühere NERVE_BASELINE_GUARD_DSN |
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Generische Fixtures (db_session + client) auf TEST_DATABASE_URL + nerve_app + Tenant-Kontext umbauen + client._test_session/_test_engine-Vertrag re-exponieren</name>
  <read_first>
    - tests/conftest.py (IST: db_session Z.41-51, client Z.54-91 — die zu ändernden Fixtures; SPEZIELL Z.84-86 `c._test_session = TestSession()` + `c._test_engine = engine`, und Z.94-97 die `db_from_client`-Fixture `return client._test_session` — der zu ERHALTENDE Vertrag)
    - tests/test_admin_dashboard_auth.py (Z.25-26, 34-35, 46-47, 55-56 — 4 db_from_client-Konsumenten, FK-SAFE, keine Edits) + tests/test_auth_next_redirect.py:106 (`client._test_session`, SAFE) + tests/test_ewb_rate_api.py (~11 db_from_client-Nutzer) + tests/test_profile_editor_validation.py (4 db_from_client + `client._test_engine`-Nutzer) — die ~20 Vertrags-Konsumenten, die ohne re-exponierten _test_session/_test_engine an AttributeError zerbrechen
    - database/db.py Z.9 (DATABASE_URL-Default sqlite) + Z.65-103 (set_current_tenant + after_begin-Hook — der Vertrag, gegen den D-05 baut; PRÜFEN: der Hook ist auf das MODUL-SessionLocal registriert, nicht auf eine Fixture-lokale sessionmaker, UND er wird nur registriert wenn DATABASE_URL non-sqlite — A-1 HARD PRECONDITION, vom Gate Plan 02 garantiert)
    - tests/test_rls_isolation.py Z.33-54 (_new_tenant — das Trigger-tenant_orgs-Seed-Muster, EXAKT übernehmen)
    - tests/test_rls_isolation.py Z.82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — Vorbild für den A-1-Tripwire-crm-Read in Task 2)
    - tests/conftest.py Z.111-132 (nerve_app_pg_conn — Vorbild für DSN-aus-Env + SKIP-wenn-fehlt + psycopg2/SQLAlchemy-Connectivity)
    - tests/conftest.py client (Z.54-91) — IST-Stand baut `TestSession = _sm(...)` (frische sessionmaker, RLS-Hook-LOS); dient als Beispiel WAS umzubauen ist (NICHT als Vorbild für die frische sessionmaker)
  </read_first>
  <behavior>
    - db_session: liest os.environ['TEST_DATABASE_URL']; fehlt → pytest.skip (KEIN sqlite-Fallback, D-07-Geist). Bindet das MODUL-`database.db.SessionLocal` via `dbmod.SessionLocal.configure(bind=engine)` an die nerve_test-Engine um (NICHT lokale sessionmaker), seedet EINMAL einen Test-Mandanten (Trigger-Muster), ruft set_current_tenant(TEST_TENANT_UUID) auf, yieldet eine Session aus dem MODUL-SessionLocal, rollback/close + `dbmod.SessionLocal.configure(bind=None)` (Binding-Reset) + engine.dispose() im finally.
    - client: identische DSN-Quelle; bindet das MODUL-`database.db.SessionLocal` EXAKT wie db_session via `dbmod.SessionLocal.configure(bind=engine)` um (KEINE frische `TestSession = sessionmaker(...)` mehr — die trüge den after_begin-RLS-Hook nicht); monkeypatcht NUR `dbmod.engine` auf die nerve_test-Engine; ruft set_current_tenant(TEST_TENANT_UUID) NACH der Umbindung. RE-EXPONIERT VOR `yield c` den Vertrag: `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal-PG-Session, hook-tragend — NICHT eine frische sessionmaker) + `c._test_engine = engine` (die nerve_test-Engine). Im finally `c._test_session.close()` (best-effort) + `dbmod.SessionLocal.configure(bind=None)` + engine.dispose(); KEINE sqlite-URL mehr.
    - db_from_client (Z.94-97): UNVERÄNDERT lassen (`return client._test_session`) — returnt nach dem Rewrite die MODUL-SessionLocal-PG-Session. Die ~20 Konsumenten-Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) funktionieren dadurch WEITER ohne AttributeError; admin_dashboard_auth + auth_next_redirect brauchen GAR KEINE Test-Datei-Edits (FK-SAFE), die conftest-Vertrags-Restauration allein entblockt sie.
    - A-1-PRÄKONDITION (NICHT in diesem Fixture lösbar, hier nur dokumentiert): der after_begin-Hook feuert NUR wenn das Gate (Plan 02) `DATABASE_URL=postgres` exportiert (db.py:86 entscheidet beim Import). `configure(bind=engine)` bewahrt einen import-registrierten Hook, erzeugt aber keinen. Der konkrete Laufzeit-Nachweis dass der Hook feuert ist der A-1-Tripwire in Task 2 (tests/test_rls_generic_smoke.py).
  </behavior>
  <action>
    Ersetze die `sqlite:///:memory:`-Verdrahtung in `db_session` (Z.41-51) und `client` (Z.54-91) durch
    eine Postgres-Verbindung aus `TEST_DATABASE_URL`. KONKRET:

    1. Modul-Konstante / Helper einführen (oben in conftest.py, nach den Imports):
       eine Helper-Funktion `_seed_test_tenant(engine_or_conn) -> str` die das Trigger-Muster aus
       test_rls_isolation.py:_new_tenant repliziert (INSERT organisations → SELECT tenant_orgs.id zurück)
       und die UUID liefert. Tag den Org-Namen `f"[PGTEST-GENERIC] tenant {uuid.uuid4().hex[:8]}"`
       (Identifizierbarkeit + Analytics-Exklusion-Lineage über den `[PGTEST-GENERIC]`-Prefix; der
       angehängte uuid-Suffix verhindert Unique-Constraint-Kollisionen bei xdist / verpasstem Teardown —
       Gemini-LOW). Falls `import uuid` oben noch nicht vorhanden ist → ergänzen.
       `TEST_TENANT_UUID` wird beim Seed gefüllt (Discretion D-05: feste Konstante vs. seed-erzeugt →
       seed-erzeugt, FK-Zwang: crm.* FKs auf public.tenant_orgs(id), eine erfundene UUID würde
       FK-Verletzung werfen — RESEARCH Q4b).

    2. `db_session` — MUSS die MODUL-Engine umbinden (NICHT eine lokale sessionmaker bauen):
       ```python
       @pytest.fixture
       def db_session(monkeypatch):
           dsn = os.environ.get('TEST_DATABASE_URL')
           if not dsn:
               pytest.skip("TEST_DATABASE_URL not set -- generic fixtures require real-PG nerve_test "
                           "(no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.")
           import database.db as dbmod
           from database.db import set_current_tenant, clear_current_tenant
           engine = create_engine(dsn)
           # KRITISCH (A-1 HARD PRECONDITION / RESEARCH Q2c): der RLS-after_begin-Hook (_set_tenant_txn_local,
           # db.py:87) ist zur IMPORT-ZEIT auf das MODUL-SessionLocal registriert — ABER NUR wenn das Gate
           # DATABASE_URL=postgres exportiert hat (db.py:86 `if 'sqlite' not in _DATABASE_URL`). Eine FRISCHE
           # sessionmaker(bind=engine) trägt diesen Hook NICHT → set_current_tenant bliebe inert → RLS
           # fail-closed → 0 Zeilen. Deshalb: das MODUL-SessionLocal an die nerve_test-Engine umbinden (exakt
           # wie `client`) und Sessions aus dem MODUL-SessionLocal ziehen. configure(bind=engine) BEWAHRT
           # einen import-registrierten Hook, ERZEUGT aber keinen — ist DATABASE_URL beim Import sqlite, ist
           # hier nichts zu bewahren (→ A-1-Tripwire, Task 2, schlägt loud-red an).
           monkeypatch.setattr(dbmod, "engine", engine)
           dbmod.SessionLocal.configure(bind=engine)   # behält den auf SessionLocal registrierten Hook
           tenant_uuid = _seed_test_tenant(engine)      # Trigger-Muster, gibt tenant_orgs.id zurück
           set_current_tenant(tenant_uuid)              # D-05: GUC für crm.* reads
           session = dbmod.SessionLocal()               # MODUL-SessionLocal → Hook feuert auf BEGIN
           try:
               yield session
           finally:
               session.rollback()
               session.close()
               clear_current_tenant()
               dbmod.SessionLocal.configure(bind=None)  # Binding-Reset (Gemini-MEDIUM): NICHT an die
                                                        # gleich gedisposte Engine gebunden lassen, sonst
                                                        # leakt eine tote Engine-Bindung in spätere Tests
               engine.dispose()
       ```
       WICHTIG: NICHT `Session = sessionmaker(bind=engine)` lokal bauen. `db_session` MUSS das
       MODUL-`SessionLocal` via `configure(bind=engine)` umbinden und seine Session aus dem MODUL-
       `SessionLocal` ziehen, sonst feuert der after_begin-Hook nicht. Der `configure(bind=None)`-Reset
       im finally ist Pflicht (kein globaler Seiteneffekt einer toten Engine-Bindung).

    3. `client` — EXAKT dieselbe MODUL-SessionLocal-Umbindung wie `db_session` (KEINE frische sessionmaker),
       UND der `_test_session`/`_test_engine`-Vertrag MUSS re-exponiert werden (pre-execute blocker fix):
       Der IST-Stand baut `TestSession = _sm(...)` (frische sessionmaker) und monkeypatcht damit
       `database.db.SessionLocal` auf ein NEUES Objekt — dadurch geht der after_begin-RLS-Hook verloren
       (er hängt am MODUL-SessionLocal, db.py:87) → alle API-Integration-Tests setzen den Tenant-GUC nicht
       → 0 crm-Zeilen → fail-closed False-Green (Gemini-HIGH). ZUSÄTZLICH exponiert der IST-client
       `c._test_session = TestSession()` (Z.84) + `c._test_engine = engine` (Z.85), von denen `db_from_client`
       (Z.95-97) + ~20 Tests abhängen — DIESEN Vertrag NICHT fallenlassen, sonst AttributeError → fail-closed
       Gate. FIX:
       ```python
       @pytest.fixture
       def client(monkeypatch):
           dsn = os.environ.get('TEST_DATABASE_URL')
           if not dsn:
               pytest.skip("TEST_DATABASE_URL not set -- client fixture requires real-PG nerve_test "
                           "(no SQLite fallback by design, Req-2/D-07).")
           import database.db as dbmod
           from database.db import set_current_tenant, clear_current_tenant
           engine = create_engine(dsn)
           monkeypatch.setattr(dbmod, "engine", engine)   # NUR engine monkeypatchen
           dbmod.SessionLocal.configure(bind=engine)      # MODUL-SessionLocal umbinden (Hook bleibt) —
                                                          # KEIN `SessionLocal = sessionmaker(...)`, KEIN
                                                          # monkeypatch von SessionLocal auf ein neues Objekt
           tenant_uuid = _seed_test_tenant(engine)
           set_current_tenant(tenant_uuid)                # D-05, VOR dem app-Import-Pfad
           from app import app as flask_app               # erst NACH der Umbindung importieren
           flask_app.config['TESTING'] = True
           flask_app.config['WTF_CSRF_ENABLED'] = False
           try:
               with flask_app.test_client() as c:
                   # VERTRAG re-exponieren (pre-execute blocker fix 2026-06-15): db_from_client (Z.95-97)
                   # + ~20 Tests (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation)
                   # lesen diese Attribute. MUSS die MODUL-SessionLocal-Session sein (hook-tragend, PG-gebunden),
                   # NICHT eine frische sessionmaker — sonst feuert der RLS-Hook auf der db_from_client-Session nicht.
                   c._test_session = dbmod.SessionLocal()   # MODUL-SessionLocal → PG-gebunden + hook-tragend
                   c._test_engine = engine                  # die nerve_test-PG-Engine
                   yield c
           finally:
               try:
                   c._test_session.close()                  # best-effort, analog IST-client Z.87-90
               except Exception:
                   pass
               clear_current_tenant()
               dbmod.SessionLocal.configure(bind=None)    # Binding-Reset (Gemini-MEDIUM)
               engine.dispose()
       ```
       Entferne `connect_args={'check_same_thread': False}` (sqlite-spezifisch) und die frische
       `TestSession = _sm(...)`-Konstruktion komplett. Die exakte App-Import-/test_client-Mechanik aus
       dem IST-`client` beibehalten — nur die DB-Umbindung wird von „frische sessionmaker" auf
       „MODUL-SessionLocal.configure(bind=engine)" umgestellt, und der `_test_session`/`_test_engine`-Vertrag
       wird auf die MODUL-SessionLocal-PG-Session umgestellt (statt der alten sqlite-TestSession).

    3b. `db_from_client` (Z.94-97) NICHT anfassen — bleibt `return client._test_session`. Nach dem Rewrite
        returnt es die MODUL-SessionLocal-PG-Session (hook-tragend). Verifiziere im read_first dass die Fixture
        unverändert bleibt und jetzt eine PG-Session liefert. KEINE Edits an den 4 Konsumenten-Dateien aus
        diesem Plan heraus (admin_dashboard_auth + auth_next_redirect brauchen GAR KEINE; ewb_rate_api +
        profile_editor_validation kriegen ihre FK-Deltas in Plan 03 #8/#9 — NICHT in files_modified dieses Plans).

    4. NICHT Base.metadata.create_all aufrufen — das Schema baut das Gate (Plan 02) per pg_dump+alembic.
       Die Fixtures verbinden gegen die fertig gebaute nerve_test.

    Kein PW im Code/Log. KEINE BYPASSRLS-Rolle (D-05 abgelehnt — wäre False-Green) für die GENERISCHEN
    Fixtures. (Der Baseline-Wächter in Task 6 nutzt eine SEPARATE superuser/BYPASSRLS-DSN NUR zum LESEN —
    das ist kein Test-Pfad, sondern der Symptom-Guard-Leser; siehe Task 6.)
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -n "sqlite:///:memory:" tests/conftest.py | grep -v "^\s*#"; echo "EXIT_GREP=$?"; grep -nE "_test_session = dbmod.SessionLocal\(\)|_test_engine = engine|return client._test_session" tests/conftest.py'  # erwartet: kein aktiver sqlite-Treffer (Req-2-Acceptance) UND der re-exponierte _test_session/_test_engine-Vertrag + unverändertes db_from_client present. Voll-Beleg = deploy.sh-Gate-Lauf (Plan 02) zeigt generische crm-Tests + API-Integration-Tests (über client) PASSED (crm-Read unter set_current_tenant liefert geseedete Zeile, nicht 0), die ~20 db_from_client/_test_engine-Konsumenten (admin_dashboard_auth/auth_next_redirect/ewb_rate_api/profile_editor_validation) PASSED (kein AttributeError) UND der A-1-Tripwire (Task 2) PASSED.</automated>
  </verify>
  <done>
    `grep "sqlite:///:memory:" tests/conftest.py` liefert keinen Treffer im aktiven Fixture-Code (nur ggf.
    in Kommentaren). db_session UND client binden das MODUL-`database.db.SessionLocal` via
    `dbmod.SessionLocal.configure(bind=engine)` an die nerve_test-Engine um (NICHT lokale/frische sessionmaker,
    KEIN monkeypatch von SessionLocal auf ein neues Objekt), lesen TEST_DATABASE_URL und rufen
    set_current_tenant. Beide setzen im finally `dbmod.SessionLocal.configure(bind=None)` (Binding-Reset, keine
    tote Engine-Bindung). Der `client` re-exponiert `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal,
    hook-tragende PG-Session) + `c._test_engine = engine` (nerve_test-Engine) VOR `yield c` und schließt
    `c._test_session` best-effort im finally; `db_from_client` (Z.95-97) bleibt UNVERÄNDERT und returnt nun die
    MODUL-SessionLocal-PG-Session. ACCEPTANCE: im Gate-Lauf (Plan 02) liefert ein crm-Read unter
    set_current_tenant(TEST_TENANT_UUID) — sowohl über db_session als auch über client/API-Integration — die
    geseedete Zeile zurück (≥1 Zeile, NICHT 0 — Beweis dass der after_begin-Hook auf der genutzten MODUL-Session
    feuert); generische crm-berührende Tests sind PASSED (nicht 0-Zeilen-rot, nicht SKIPPED); die ~20
    db_from_client/_test_engine-Konsumenten (admin_dashboard_auth + auth_next_redirect ohne Edits, ewb_rate_api +
    profile_editor_validation mit Plan-03-Deltas) sind PASSED (kein AttributeError im Setup).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: A-1-Tripwire-Test (tests/test_rls_generic_smoke.py) — GUC-NON-null + crm-Read-≥1-Zeile auf dem generischen db_session-Pfad</name>
  <read_first>
    - tests/conftest.py (NACH Task 1: db_session-Fixture + _seed_test_tenant + TEST_TENANT_UUID — der generische Pfad, den der Tripwire prüft)
    - database/db.py Z.9 + Z.86-103 (A-1: Hook nur registriert wenn DATABASE_URL non-sqlite; der Tripwire ist der Laufzeit-Nachweis dass der Hook feuerte)
    - tests/test_rls_isolation.py Z.82-90 (crm.accounts + crm.account_memory Seed unter Tenant-GUC — EXAKT als Muster für den crm-Read-Arm übernehmen)
    - tests/test_rls_isolation.py Z.101-116 (Best-Effort-Teardown im POST-yield-try/except — analog für etwaigen Seed-Cleanup; HIER via dem cleanup_rows-Helfer aus Task 5)
  </read_first>
  <behavior>
    - Ein dedizierter, scharfer A-1-Tripwire auf dem GENERISCHEN db_session-Pfad (db_session-Fixture aus Task 1,
      mit set_current_tenant(TEST_TENANT_UUID) bereits angewandt) asserted BEIDE Arme:
      (a) `SELECT current_setting('app.tenant_id', true)` unter db_session liefert die TEST_TENANT_UUID (NON-null)
          — beweist DIREKT dass der after_begin-Hook auf der generischen Session feuerte. Wäre DATABASE_URL beim
          Import sqlite-Default gewesen (A-1), wäre dieser Wert NULL → Test RED, nicht silent-green.
      (b) ein realer crm-Read unter dem Tenant liefert >=1 Zeile (vorher 1 crm.accounts-Row mit
          tenant_id=TEST_TENANT_UUID seeden, analog test_rls_isolation.py:82-90) — beweist end-to-end
          tenant-scoped Sichtbarkeit, NICHT 0-Zeilen-fail-closed.
    - Anti-False-Green (CLAUDE.md Test-Regel): der Test asserted Runtime-GUC + echte Row-Count — KEINE
      Source-Presence (kein inspect.getsource/hasattr/grep-on-source). Er ist der Mechanismus, der A-1 von
      silent-green auf loud-red dreht.
    - SKIP nur wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback) — im Gate (Plan 02) läuft er scharf.
    - crm-BASELINE=0-KONFORM (HYBRID, André locked): der Tripwire seedet eine crm.accounts-Row mit
      tenant_id=TEST_TENANT_UUID → er ist selbst ein crm-WRITER und MUSS im Teardown via cleanup_rows (Task 5) auf
      0 zurueckraeumen (crm.accounts == 0 nach dem Test). Da die db_session FUNCTION-SCOPED ist und im finally
      rollbackt, ist der Insert ohnehin transaktions-lokal weg, FALLS der Test nicht zwischendurch committet;
      committet er (z.B. um den Read ueber eine frische Transaktion zu beweisen), GREIFT cleanup_rows. Beide Wege
      enden bei crm.accounts == 0 → der POST-SUITE-crm-Check in Plan 02 (jede crm.* Tabelle == 0) bleibt gruen.
      ALTERNATIVE (falls die Row aus Beweis-Gruenden PERSISTIEREN muesste): dann waere sie der EINZIGE erlaubte
      crm-Baseline-Eintrag und der POST-SUITE-Check in Plan 02 muesste exakt diese eine Row zulassen — das ist
      NICHT der gewaehlte Weg; der gewaehlte Weg ist function-scoped + cleanup_rows → crm.* zurueck auf 0.
  </behavior>
  <action>
    Erstelle `tests/test_rls_generic_smoke.py` mit GENAU EINEM Tripwire-Test, der die db_session-Fixture
    aus conftest (Task 1) nutzt (db_session hat set_current_tenant(TEST_TENANT_UUID) schon angewandt). KONKRET:

    1. Arm (a) — GUC NON-null: über die db_session-Session
       `SELECT current_setting('app.tenant_id', true)` ausführen (z.B. via `db_session.execute(text(...))`)
       und asserten dass der zurückgegebene Wert == die geseedete TEST_TENANT_UUID ist (NON-null, nicht ''/None).
       Das ist der direkte Beweis dass der after_begin-Hook (db.py:87) auf der generischen Session feuerte.
       Importiere TEST_TENANT_UUID aus conftest (von Task 1 exportiert) ODER lies die UUID, die die Fixture
       gesetzt hat — wähle die Mechanik passend zu Task 1's Export.
    2. Arm (b) — crm-Read ≥1 Zeile: vor der Read-Assertion eine crm.accounts-Row mit
       `tenant_id=TEST_TENANT_UUID` (+ id + name `"[PGTEST-SMOKE] account ..."`) über die db_session-Session
       inserten (analog test_rls_isolation.py:82-90; tenant_id MUSS = gesetzter Tenant, sonst RLS WITH CHECK
       violation). Dann `SELECT count(*) FROM crm.accounts WHERE tenant_id = <TEST_TENANT_UUID>::uuid` (bzw.
       ein einfaches SELECT auf crm.accounts unter dem Tenant) und asserten `>= 1` — beweist tenant-scoped
       Sichtbarkeit, NICHT 0-Zeilen-fail-closed.
    3. **Teardown via cleanup_rows (Task 5, crm-Baseline=0-Konformität):** die geseedete crm.accounts-Row in
       der POST-yield-Sektion via dem gemeinsamen `cleanup_rows`-Helfer (Extension 1) löschen — unter dem
       Tenant-GUC (`tenant=TEST_TENANT_UUID`), best-effort. So ist crm.accounts == 0 nach dem Test → der
       POST-SUITE-crm-Check (Plan 02) bleibt grün. (Die db_session ist FUNCTION-SCOPED und rollbackt im finally
       ihre EIGENE Transaktion — falls der Insert in derselben un-committeten Transaktion liegt, ist er ohnehin
       weg; falls der Test committet, GREIFT cleanup_rows. Im Zweifel cleanup_rows aufrufen — idempotent/best-
       effort.) Der in-pytest public-Wächter (Task 6) prueft crm.* NICHT — die crm.*-Sauberkeit verifiziert der
       POST-SUITE-Check in Plan 02.
    4. KEIN sqlite-Fallback: läuft nur wenn db_session nicht skippt (TEST_DATABASE_URL gesetzt). Der Test
       erbt die SKIP-Semantik der db_session-Fixture.

    **Warum dieser Test existiert (im Test-Docstring festhalten):** Er ist der A-1-Tripwire — die einzige
    Assertion, die den DATABASE_URL-unset-False-Green (db.py registriert den Hook beim Import nicht, wenn
    DATABASE_URL sqlite-Default ist) von silent-green auf loud-red dreht. test_tenant_orgs.py kann das NICHT
    leisten (public-only, berührt KEIN crm — siehe F1 in Plan 03). Daher dieser dedizierte generische crm-Tripwire.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy1b.log | grep -E "test_rls_generic_smoke.*PASSED|test_rls_generic_smoke.*passed|current_setting|passed|failed"; echo "EXIT=$?"  # A-1-Tripwire PASSED gegen nerve_test: GUC NON-null (Hook feuerte) + crm-Read ≥1 Zeile. Wäre DATABASE_URL im Gate sqlite-Default → dieser Test RED (loud), nicht silent-green.</automated>
  </verify>
  <done>
    `tests/test_rls_generic_smoke.py` existiert und asserted auf dem GENERISCHEN db_session-Pfad BEIDE Arme:
    (a) current_setting('app.tenant_id', true) == TEST_TENANT_UUID (NON-null → after_begin-Hook feuerte) UND
    (b) ein crm-Read unter dem Tenant liefert ≥1 Zeile (nicht 0). Die geseedete crm.accounts-Row wird im
    Teardown via cleanup_rows (Task 5, tenant=TEST_TENANT_UUID) wieder gelöscht → crm.accounts == 0 nach dem Test
    (POST-SUITE-crm-Check in Plan 02 grün; der in-pytest public-Wächter prueft crm.* nicht). Im
    Gate-Lauf (Plan 02) erscheint der Test als PASSED. Der Test ist eine echte Runtime-GUC- + Row-Count-Assertion
    (keine Source-Presence). Er ist der Mechanismus, der A-1 (DATABASE_URL unset → Hook nie registriert → silent
    False-Green) auf loud-red dreht.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Die 3 Spezial-Fixture-DSNs auf nerve_test umlenken (Doku + SKIP-Texte), Prod-nerve eliminieren</name>
  <read_first>
    - tests/conftest.py Z.100-190 (die 3 Real-PG-Fixtures: nerve_app_pg_conn, anon_worker_pg_engine, schild_guard_pg_conn — IST-Doku zeigt auf `nerve`/Prod)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q2c (DSN→nerve_test-Mapping + scram-Pfad für anon_worker)
  </read_first>
  <behavior>
    - Die 3 Fixtures lesen WEITERHIN ihre Env-Vars (NERVE_APP_TEST_DSN / ANON_WORKER_TEST_DSN / NERVE_SCHILD_TEST_DSN); der Wert wird im Gate (Plan 02) auf nerve_test gesetzt. Kein Code in conftest hardcodet `@/nerve`.
    - Die Fixture-DOCSTRINGS dürfen nicht mehr behaupten, gegen die Prod-`nerve`-DB zu verbinden (Req-5: kein Prod-Kontakt).
  </behavior>
  <action>
    Die 3 Fixtures lesen ihre DSN bereits aus Env — der eigentliche Redirect passiert im Gate (Plan 02
    setzt die Env-Vars auf nerve_test). Diese Aufgabe stellt sicher, dass conftest.py KEINEN hardcoded
    Prod-`nerve`-DSN enthält und die Doku korrekt ist:

    1. `grep "@/nerve\b"` und `grep "nerve_test"` über tests/conftest.py — verifiziere: KEIN hardcoded
       `postgresql://...@/nerve` (ohne `_test`) im aktiven Code (nur Env-Reads). Falls die SKIP-Hinweis-
       Strings oder Docstrings einen `@/nerve`-Beispiel-DSN nennen, ändere ihn auf `@/nerve_test` bzw.
       `@127.0.0.1:5432/nerve_test` (anon_worker scram), damit kein Doc-Drift den Eindruck erweckt, Tests
       liefen gegen Prod.
    2. Aktualisiere die Fixture-Docstrings: ersetze Formulierungen wie "to the real `nerve` DB" /
       "real Production `nerve` database" durch "to the disposable `nerve_test` DB (Req-5: never touches
       Production `nerve`)". Die anon_worker-Doku nennt den scram-Pfad (`@127.0.0.1:5432`, PW aus
       ionos-s3.env via Gate), nicht peer.
    3. KEINE funktionale Änderung an der Connectivity-Logik (psycopg2/SQLAlchemy, autocommit-Flags,
       SKIP-wenn-fehlt) — die bleibt; nur DSN-Ziel-Doku + Env-Wert (Gate) ändern sich. Das Real-Commit-
       Muster der RLS-Gruppe (D-04) bleibt unangetastet — es existiert bereits in test_rls_isolation.py.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "@/nerve([^_]|$)|/nerve\"" tests/conftest.py'; echo "EXIT=$?"  # erwartet: kein aktiver hardcoded Prod-nerve-DSN. Voll-Beleg im Gate-Log: Fixtures verbinden gegen nerve_test.</automated>
  </verify>
  <done>
    conftest.py enthält keinen hardcoded `@/nerve`-DSN (ohne `_test`) im aktiven Code; alle 3 Fixtures
    lesen ihre Env-Var (vom Gate auf nerve_test gesetzt); Docstrings nennen nerve_test, nicht Prod-nerve.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Session-Scope Base-Seed (1 Org + 1 User id=1) gegen nerve_test fuer FK-tragende generische Tests</name>
  <read_first>
    - tests/conftest.py (NACH Task 1: die _seed_test_tenant-Helper-Struktur, der db_session/TEST_TENANT_UUID-Seed — der Base-Seed ist SEPARAT vom generischen [PGTEST-GENERIC]-Tenant; beide koexistieren: die Base-Org id=1 ist die FK-Bridge für user_id=1/org_id=1-Tests, der [PGTEST-GENERIC]-Tenant ist der RLS-Tenant für crm-Reads)
    - database/models.py Z.19-63 (Organisation — NUR `name` ist NOT-NULL ohne Default) + Z.65-135 (User — NOT-NULL ohne Default: `org_id`, `email`; NOT-NULL mit nur PYTHON-Default: `is_superadmin`, `is_test_user`, `market`, `language` → ORM-Insert nutzen, sonst NOT-NULL-Bruch; `passwort_hash` ist nullable=True). Verifiziere die Sequenz-Namen (PG-Konvention `organisations_id_seq` / `users_id_seq`).
    - tests/test_rls_isolation.py:33-54 (Trigger-Read-Back-Muster — der Base-Org-INSERT feuert trg_mk_tenant_org; die tenant_orgs-Row entsteht automatisch — NICHT manuell tenant_orgs inserten, sonst UNIQUE(legacy_org_id)-Bruch, F1-Lektion)
    - database/db.py:84-103 (after_begin-Hook-Präkondition: die MODUL-Engine ist beim Import bereits nerve_test-PG weil das Gate DATABASE_URL=postgres exportiert, commit d7d8358 — der Base-Seed läuft gegen live nerve_test mit aktiver RLS-Machinerie)
  </read_first>
  <behavior>
    - Eine session-scoped autouse Fixture in conftest.py, die EINMAL vor allen Tests läuft, gegen die
      MODUL-Engine (`database.db.engine`/`SessionLocal`/`get_session()`) — die ist beim Import bereits
      nerve_test-PG, weil das Gate (Plan 02 FIX1, T-PGTEST-18) DATABASE_URL=postgresql://nerve_app@/nerve_test
      exportiert (A-1-Abhängigkeit explizit; cross-ref Plan 02 FIX1).
    - Seedet EXAKT: 1 Organisation (id=1) + 1 User (id=1, org_id=1). NOT-NULL-Spalten ohne DB-Default
      vollständig (Org: name; User: org_id, email UNIQUE z.B. 'pgtest-base@nerve.local'). Da `is_superadmin`/
      `is_test_user`/`market`/`language` nullable=False aber nur Python-`default=` haben (kein server_default),
      MUSS der Seed über den ORM-Pfad laufen (`session.add(Organisation(id=1, name=...))` /
      `session.add(User(id=1, org_id=1, email=...))`) — dann greifen die Python-Defaults; ein RAW-SQL-INSERT
      würde diese 4 Spalten NICHT füllen → NOT-NULL-Bruch (im read_first models.py verifiziert).
    - Der Org-INSERT feuert trg_mk_tenant_org → tenant_orgs-Row entsteht AUTOMATISCH. KEIN manueller
      tenant_orgs-Insert (sonst UNIQUE(legacy_org_id)-Verletzung, F1-Lektion).
    - Nach den explizit-id-Inserts: Sequenzen advancen
      (`SELECT setval('organisations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organisations))` + dasselbe für
      `users_id_seq`), damit spätere serielle Inserts anderer Tests nicht id=1 retry'en (PG-Gotcha: explizite
      id advanced die serial-Sequenz NICHT → ein späterer serieller Insert würde id=1 retry'en → UNIQUE-Bruch).
    - COMMIT des Seeds (session-scoped, persistiert über alle Tests; nerve_test wird vom Gate-Trap am Ende
      gedroppt → kein Teardown nötig). WICHTIG: der generische function-scoped db_session-Rollback (Task 1)
      darf den Base-Seed NICHT wegwischen — der Base-Seed committet auf seiner EIGENEN Connection/Session
      BEVOR db_session's Per-Test-Transaktion beginnt.
    - WICHTIG (Extension-2-Reihenfolge): dieser Base-Seed MUSS VOR dem Baseline-Snapshot (Task 6) laufen — der
      Snapshot friert den Zustand NACH app-import-Seeds + Base-Seed als „erlaubte Baseline" ein. Die Org id=1 +
      ihre Trigger-tenant_org + User id=1 GEHÖREN zur Baseline (kein Leak). Stelle die Fixture-Ordering sicher
      (Base-Seed-Fixture als Dependency des Snapshot-Fixtures ODER explizite pytest-Ordering — siehe Task 6).
  </behavior>
  <action>
    Füge eine session-scoped autouse Fixture (z.B. `_pgtest_base_seed`) in conftest.py hinzu, die EINMALIG
    vor allen Tests den FK-tragenden Base-Datensatz gegen nerve_test legt. KONKRET:

    1. **Fixture-Signatur:** `@pytest.fixture(scope="session", autouse=True)`. Am Anfang: wenn
       `os.environ.get('TEST_DATABASE_URL')` (bzw. das A-1-DATABASE_URL) NICHT gesetzt → `return`/no-op
       (KEIN Seed lokal; nur im Gate scharf, kein sqlite-Fallback). Im Gate ist die MODUL-Engine bereits
       nerve_test-PG (DATABASE_URL=postgres, A-1).

    2. **Seed über ORM gegen die MODUL-Engine:** `import database.db as dbmod`, eine Session aus dem
       MODUL-`dbmod.SessionLocal()` (ODER `dbmod.get_session()`) ziehen. Prüfe zuerst idempotent ob die
       Base-Org/-User schon existieren (z.B. `session.get(Organisation, 1)` / `session.get(User, 1)`); wenn
       ja → skip (Idempotenz, falls die Fixture in einem Re-Run gegen eine nicht frisch gedroppte DB läuft).
       Sonst:
       ```python
       org  = Organisation(id=1, name="[PGTEST-BASE] org")
       session.add(org); session.flush()         # flush feuert trg_mk_tenant_org → tenant_orgs-Row auto
       user = User(id=1, org_id=1, email="pgtest-base@nerve.local")
       # is_superadmin/is_test_user/market/language kommen aus Python-default= (ORM-Pfad) — NICHT explizit nötig
       session.add(user)
       session.commit()
       ```
       KEIN manueller `TenantOrg(...)`-Insert — der Trigger erzeugt die tenant_orgs-Row (F1-Lektion:
       manuelles Doppeln → UNIQUE(legacy_org_id)-IntegrityError).

    3. **Sequenz-Advance** (PG explicit-id-no-sequence-advance-Gotcha) NACH dem Commit, auf derselben Session:
       ```python
       session.execute(text("SELECT setval('organisations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organisations))"))
       session.execute(text("SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id),1) FROM users))"))
       session.commit()
       ```
       Verifiziere die exakten Sequenz-Namen im read_first (PG-Default `<table>_<pk>_seq` → `organisations_id_seq`
       / `users_id_seq`; falls die DB abweichende Namen hat → an die tatsächlichen anpassen). Danach
       `session.close()`.

    4. **Reconciliation mit dem generischen Tenant (Task 1):** die Base-Org id=1 ist SEPARAT vom
       `[PGTEST-GENERIC]`-Tenant aus _seed_test_tenant — beide koexistieren. Die Base-Org dient den
       FK-tragenden generischen Tests (user_id=1/org_id=1 auf PUBLIC-Tabellen: calls/conversation_logs etc.);
       der [PGTEST-GENERIC]-Tenant dient dem crm-RLS-Read-Pfad. Kein Konflikt: verschiedene Org-Namen,
       verschiedene ids (Base=1, generischer Tenant = fresh-serial nach setval).

    5. **Completeness-Lineage (im SUMMARY festhalten):** die frühere `create_all|sqlite`-Map verfehlte die
       get_session-direkte FK-Klasse (Tests die user_id=1/org_id=1 ohne ORM-Seed annahmen — auf SQLite mit
       FK-enforcement-off lautlos grün, auf nerve_test FK-rot). Die 36-File-Klassifikation (11 A / admin_dashboard
       →SAFE / 24 SAFE, André+Claudian deep-checked, kein verstecktes (B)) ist die korrigierte Map. Der Base-Seed
       deckt 6 der 11 (test_postcall_outcome_route, test_api_beenden_calls_update, test_dashboard_outcome_reminder,
       test_cost_tracker, test_per_sid_migration, test_migration_0005 — alle referenzieren user_id=1/org_id=1 auf
       PUBLIC-Tabellen); die 5 Deltas (Plan 03) sind test-spezifisch.

    Kein PW im Code/Log. KEINE BYPASSRLS-Rolle. Org/User sind PUBLIC-Tabellen (kein crm-RLS); der Seed
    braucht keinen gesetzten Tenant-GUC (organisations/users/calls/tenant_orgs sind RLS-frei).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy1c.log | grep -E "test_postcall_outcome_route|test_api_beenden_calls_update|test_dashboard_outcome_reminder|test_cost_tracker|test_per_sid_migration|test_migration_0005|passed|failed|error|ForeignKey|NotNull"; echo "EXIT=$?"  # nach dem Gate-Lauf sind die 6 FK-Konsumenten PASSED (kein FK-/NOT-NULL-Error). Ferner grep-style: `grep -nE "scope=.session.*autouse|setval\('(organisations|users)_id_seq'" tests/conftest.py` → Base-Seed-Fixture present (session-scope + autouse + Sequenz-Advance).</automated>
  </verify>
  <done>
    Eine session-scoped autouse Fixture in conftest.py seedet EINMAL 1 Organisation(id=1) + 1 User(id=1,
    org_id=1, email UNIQUE) gegen die MODUL-Engine (= nerve_test-PG via A-1-DATABASE_URL, commit d7d8358) über
    den ORM-Pfad (Python-Defaults für is_superadmin/is_test_user/market/language greifen), feuert den Trigger
    trg_mk_tenant_org (kein manueller tenant_orgs-Insert) und advanced `organisations_id_seq` + `users_id_seq`
    via setval. Der Seed committet auf eigener Session (überlebt den function-scoped db_session-Rollback) und läuft
    VOR dem Baseline-Snapshot (Task 6) — die Base-Rows gehören zur erlaubten Baseline. Im Gate-Lauf (Plan 02) sind
    die 6 FK-Konsumenten (test_postcall_outcome_route, test_api_beenden_calls_update, test_dashboard_outcome_reminder,
    test_cost_tracker, test_per_sid_migration, test_migration_0005) PASSED — nicht ForeignKeyViolation/NOT-NULL-Error.
    grep zeigt session-scope + autouse + setval('organisations_id_seq'/'users_id_seq'). A-1/DATABASE_URL-Abhängigkeit
    + Sequenz-Advance-Gotcha sind in Fixture-Kommentar + SUMMARY dokumentiert.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: Extension 1 — gemeinsamer cleanup_rows-Teardown-Helfer (reverse-FK unter Tenant-GUC) + Ein-Zeilen-Konvention in conftest.py UND CLAUDE.md</name>
  <read_first>
    - tests/conftest.py (NACH Task 1-4: die _seed_test_tenant/Base-Seed-Struktur + set_current_tenant-Import — der Helfer lebt hier, koexistiert mit den generischen + 3 Spezial-Fixtures)
    - tests/test_rls_isolation.py Z.101-116 (das EXAKTE Vorbild: POST-yield `cur = conn.cursor(); try: SET set_config(tenant); DELETE crm.account_memory; DELETE crm.accounts; commit; ... DELETE tenant_orgs; DELETE organisations; commit; except: rollback` — reverse-FK, best-effort, unter Tenant-GUC für crm.*)
    - database/db.py Z.68-103 (set_current_tenant + after_begin-Hook: crm.*-DELETEs greifen nur unter gesetztem Tenant-GUC; public.* brauchen keinen GUC)
    - database/models.py (FK-Richtungen der relevanten Tabellen — für die reverse-FK-Reihenfolge: crm.account_memory→crm.accounts→public.tenant_orgs→public.organisations; public.objection_event→conversation_log→user→org; api_cost_log etc.)
    - PERSISTENCE-ENUMERATION.md Gruppe A + Gruppe B (welche Tabellen die committenden Tests berühren — der Helfer muss die crm.*- UND public.*-Familien abdecken)
    - CLAUDE.md Punkt 23 (SCHILD-Konventions-Stil — die neue Cleanup-Regel wird im selben knappen Stil ergänzt)
  </read_first>
  <behavior>
    - EIN gemeinsamer, wiederverwendbarer Teardown-Helfer in conftest.py (z.B. `cleanup_rows(conn_or_session, spec)`),
      den jeder committende Test in seiner POST-yield-Sektion aufruft, um seine EIGENEN committeten Rows
      reverse-FK-clean wieder zu löschen. Best-effort (try/except, rollback bei Fehler — analog
      test_rls_isolation.py:101-116). Für crm.*-Rows setzt der Helfer den passenden Tenant-GUC (set_config /
      set_current_tenant) VOR dem DELETE (sonst RLS fail-closed → DELETE trifft 0 Rows → Leak bleibt). Für public.*
      ist kein GUC nötig.
    - Signatur-Geist (Discretion D-05, vom Briefing vorgegeben): `cleanup_rows(conn_or_session, {Model_or_table: [ids...]}, tenant=<uuid|None>)`
      — der Test registriert/sammelt seine erzeugten Row-IDs (pro Tabelle) und übergibt sie; der Helfer löscht in
      reverse-FK-Reihenfolge. Akzeptiere EXAKT die Form, die zu den IST-Tests passt (psycopg2-conn ODER SQLAlchemy-
      Session — beide Pfade existieren in der Suite; der Helfer soll beide unterstützen ODER es gibt zwei dünne
      Varianten. Wähle die einfachste robuste Form; dokumentiere sie im Docstring).
    - Die Reverse-FK-Reihenfolge ist im Helfer KODIFIZIERT (eine feste, dokumentierte Ordnung der bekannten
      Tabellen-Familien), sodass die einzelnen Tests sie nicht selbst kennen müssen — sie übergeben nur {Tabelle: ids}.
    - PLUS eine Ein-Zeilen-Konvention, dokumentiert an ZWEI Orten (Briefing-Pflicht):
      (i) als Docstring/Kommentar-Regel oben in conftest.py (beim Helfer), UND
      (ii) als neue kurze Regel in CLAUDE.md (project root).
  </behavior>
  <action>
    1. **Helfer in conftest.py** (nach den Imports / bei den Seed-Helfern aus Task 1): implementiere
       `cleanup_rows(...)` modelliert EXAKT auf test_rls_isolation.py:101-116. KONKRET:
       - Akzeptiert eine Connection ODER Session + ein Mapping `{tabelle_oder_model: [ids]}` + optional `tenant`.
       - Löscht in einer FESTEN reverse-FK-Reihenfolge (kodifiziere die bekannten Familien, z.B. zuerst
         crm.account_memory, dann crm.accounts, dann public.objection_event/conversation_log/calls, dann
         public.users, dann public.tenant_orgs, dann public.organisations — die genaue Ordnung aus models.py-FKs
         verifizieren). Nur die übergebenen Tabellen/IDs werden angefasst.
       - Für crm.*-Tabellen: `SET set_config('app.tenant_id', tenant, true)` (bzw. set_current_tenant(tenant) +
         eine frische Transaktion) VOR dem DELETE. Tenant ist Pflicht-Arg wenn crm.*-Tabellen im Spec sind;
         fehlt er → klare Exception (nicht still 0 Rows löschen).
       - Best-effort: `try: <deletes>; commit except Exception: rollback`. Niemals den Test selbst zum Absturz
         bringen (Teardown-Robustheit). KEIN Löschen von Baseline-Rows (id=1 / [PGTEST-BASE] / app-import-Seeds) —
         der Helfer löscht NUR die explizit übergebenen test-eigenen IDs.
       - Docstring: nenne das Vorbild (test_rls_isolation.py:101-116), die reverse-FK-Ordnung, die Tenant-GUC-
         Pflicht für crm.*, und die Konvention (s.u.).
    2. **Konvention #1 — conftest.py-Docstring/Kommentar** (oben in der Datei, prominent): eine Ein-Zeilen-Regel,
       z.B.:
       ```
       # KONVENTION (Baseline-Sauberkeit, Phase 08.23.2.PGTEST Option-A): Jeder Test, der Daten in nerve_test
       # COMMITTET, registriert seine erzeugten Row-IDs und ruft cleanup_rows(...) in seiner POST-yield-Sektion,
       # um sie reverse-FK-clean (crm.* unter Tenant-GUC) wieder zu loeschen. Erzwungen vom autouse
       # _baseline_cleanup_guard (Extension 2). Nicht aufgeraeumte Rows => Waechter rot => Gate blockt Deploy.
       ```
    3. **Konvention #2 — CLAUDE.md (project root)**: füge eine neue kurze Regel im SCHILD-Punkt-23-Stil hinzu
       (knapp, eine Regel, kein Roman). Empfohlene Platzierung: direkt NACH dem Test-Qualitaets-Regel-Abschnitt
       („Integration-Assertion vs. Source-Presence-False-Green") ODER als neuer nummerierter Punkt. Exakter Text
       (Briefing-Vorgabe, ASCII-Code-Identifier, Umlaute im Fliesstext erlaubt):
       „Tests, die Daten in nerve_test committen, raeumen ihre eigenen Rows im Teardown via dem gemeinsamen
       Cleanup-Helfer (`cleanup_rows` in tests/conftest.py) wieder weg (Baseline-Sauberkeit, vom Test-Cleanup-
       Waechter `_baseline_cleanup_guard` erzwungen)." (Code-Identifier `cleanup_rows`/`_baseline_cleanup_guard`
       bleiben ASCII; „raeumen/weg" im Fliesstext dürfen echte Umlaute sein, Doc-Stil egal — CLAUDE.md erlaubt
       beides.)
    4. KEINE funktionale Aenderung an den IST-Fixtures aus Task 1-4 — nur der Helfer + die zwei Doku-Stellen
       kommen hinzu. Der Helfer wird in Plan 03 + Plan 04 von den committenden Tests ADOPTIERT (dort referenziert).
    5. Anti-False-Green: der Helfer ist Infrastruktur (kein Test) — er hat keine Assertions; seine Korrektheit
       wird durch den Baseline-Waechter (Task 6) + die committenden Tests (Plan 03/04) end-to-end belegt.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "def cleanup_rows\(|cleanup_rows" tests/conftest.py; echo "--- CLAUDE ---"; grep -nE "cleanup_rows|Cleanup-Helfer|_baseline_cleanup_guard" CLAUDE.md'; echo "EXIT=$?"  # erwartet: cleanup_rows-Def in conftest.py present + Konventions-Kommentar; CLAUDE.md enthaelt die neue Cleanup-Regel (Cleanup-Helfer + _baseline_cleanup_guard). Voll-Beleg: Plan 03/04-Tests adoptieren cleanup_rows + Baseline-Waechter gruen.</automated>
  </verify>
  <done>
    `tests/conftest.py` enthält den gemeinsamen `cleanup_rows(...)`-Helfer (modelliert auf
    test_rls_isolation.py:101-116: reverse-FK, best-effort try/except, crm.* unter Tenant-GUC, löscht NUR
    die übergebenen test-eigenen IDs, fasst Baseline-Rows nicht an) + den Konventions-Kommentar. `CLAUDE.md`
    enthält die neue Ein-Zeilen-Cleanup-Regel (committende Tests räumen via cleanup_rows im Teardown auf, vom
    `_baseline_cleanup_guard` erzwungen) im SCHILD-Stil. Code-Identifier sind ASCII. Der Helfer wird in Plan 03/04
    von den committenden Tests adoptiert (dort verifiziert über den grünen Baseline-Wächter). grep zeigt
    `def cleanup_rows(` in conftest.py + die Regel in CLAUDE.md.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 6: Extension 2 — autouse Baseline-Cleanup-Waechter (_baseline_cleanup_guard, à la SCHILD) PUBLIC.*-only (crm.* via POST-SUITE-Check in Plan 02) + Mechanismus-Selbsttest (tests/test_baseline_guard.py)</name>
  <read_first>
    - tests/conftest.py (NACH Task 1-5: Base-Seed (Task 4), cleanup_rows (Task 5), die 3 Spezial-Fixtures, db_session/client — der Waechter koexistiert mit allen; KRITISCH die Fixture-ORDERING: der Snapshot muss NACH dem session-scoped Base-Seed + app-import-Seeds entstehen, und die per-test-Pruefung muss NACH dem Test-eigenen cleanup_rows laufen)
    - tests/test_schild_guard.py (das SCHILD-Symptom-Guard-Vorbild: prueft DB-STATE gegen Postgres-Katalog, fail-closed, skippt ohne DSN, nennt das offending Objekt — der Baseline-Waechter ist dieselbe Philosophie auf DATEN-State statt pg_description)
    - tests/conftest.py Z.172-190 (schild_guard_pg_conn — das Muster fuer eine read-only psycopg2-Katalog-Connection; der in-pytest-Waechter liest aber NUR public.* ueber die MODUL-Session, kein psycopg2-Katalog-Conn noetig)
    - database/db.py Z.86-103 (FORCE-RLS + after_begin-Hook cleart GUC nie → als nerve_app saehe ein in-pytest-Waechter crm.* nur tenant-gefiltert → er VERPASST Cross-Tenant-Leaks → DESHALB crm.* NICHT in-pytest, sondern POST-SUITE via sudo-postgres in Plan 02; HYBRID, André locked)
    - .planning/.../08.23.2.PGTEST-02-deploy-gate-block-PLAN.md (der POST-SUITE-crm-Check: nach dem pytest-Lauf, vor dem trap-Teardown, ein `sudo -u postgres psql -d "$TEST_DB"` Schritt der jede crm.* Tabelle == 0 assertet — EXAKT das SCHILD-Guard-sudo-postgres-Muster, KEINE neue Env-Var, KEIN PW. Cross-ref Plan 02.)
    - PERSISTENCE-ENUMERATION.md Baseline-Contract (welche PUBLIC-Tabellen NICHT-leer in der Baseline sind: organisations, users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios, changelog, etc. — die „relevanten public Daten-Tabellen", deren PK-Set der in-pytest-Waechter snapshottet. crm.* ist leer in der Baseline (Baseline = 0 Rows pro crm.* Tabelle) und wird POST-SUITE in Plan 02 geprueft, NICHT in-pytest)
    - database/models.py (die public Daten-Tabellen-Liste fuer den Snapshot: organisations, users, tenant_orgs, calls, conversation_logs, api_cost_log, revenue_log, ewb_ratings, prompt_versions, training_scenarios, changelog, fixed_costs, api_rates, profiles, profile_opener, exchange_rates — alle public Tabellen, in die Tests committen; crm.* AUSGENOMMEN, die deckt der POST-SUITE-Check in Plan 02)
  </read_first>
  <behavior>
    - SESSION-START-SNAPSHOT (PUBLIC.*-only): eine session-scoped Fixture (die NACH den app-import-Seeds + dem
      Base-Seed (Task 4) laeuft — Fixture-Dependency/Ordering explizit) friert pro RELEVANTER public Daten-Tabelle
      das erlaubte PK-Set (bzw. einen stabilen Fingerprint, z.B. sortierte PK-Liste oder count+hash) als BASELINE
      ein. Relevante public Tabellen (die committed-data-Tabellen aus dem Baseline-Contract, aus models.py public
      abgeleitet): organisations, users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios,
      changelog, calls, conversation_logs, api_cost_log, revenue_log, ewb_ratings, profiles, profile_opener,
      exchange_rates — die, in die Tests committen. crm.* (accounts, account_memory, contacts, meetings,
      user_preferences) ist NICHT Teil dieses in-pytest-Snapshots — die crm.*-Baseline (0 Rows pro crm.* Tabelle)
      wird POST-SUITE in deploy.sh (Plan 02) via sudo-postgres geprueft (HYBRID, André locked).
    - PER-TEST-PRUEFUNG (autouse, POST-yield NACH dem Test-eigenen cleanup_rows): eine autouse function-scoped
      Fixture liest pro relevanter PUBLIC Tabelle das AKTUELLE PK-Set (ueber die MODUL-Session, nerve_app, kein RLS
      auf public) und asserted == Baseline-PK-Set. Extra-PKs (Leak: Test hat committed + nicht aufgeraeumt) ODER
      fehlende Baseline-PKs (Test hat Baseline-Row geloescht) → FAIL-CLOSED, mit klarer Message: nodeid (welcher
      Test) + Tabelle + die konkreten extra/missing PKs. crm.* wird hier NICHT geprueft (POST-SUITE in Plan 02).
    - ORDERING (KRITISCH, explizit flaggen): die Pruefung MUSS NACH dem Test-eigenen Teardown laufen, sonst
      sieht sie noch die un-aufgeraeumten Rows und meldet False-Positives fuer einen Test, der korrekt aufraeumt.
      In pytest heisst das: der Waechter-Yield-Teardown muss SPAETER greifen als der Test-Fixture-Teardown, der
      cleanup_rows aufruft → der Waechter ist eine der AEUSSERSTEN autouse-Fixtures (frueh im Setup angefordert,
      damit sein Teardown zuletzt laeuft). Dokumentiere diese Ordering-Anforderung im Fixture-Docstring + setze
      sie konkret um (autouse + fruehe Anforderung / hoher Scope-Trick). Falls per-test-Ordering nicht robust
      erreichbar ist, dokumentiere den Tradeoff + nutze den POST-SUITE-Fallback (D-08 erlaubt ~+Zeit, aber dann
      nennt der Waechter nicht den einzelnen Test-nodeid — Tradeoff explizit machen).
    - crm-POST-SUITE-CHECK (HYBRID, André locked — NICHT in diesem Fixture): crm.* wird NICHT in-pytest geprueft
      (nerve_app saehe nur einen Tenant). Stattdessen prueft deploy.sh (Plan 02) NACH dem pytest-Lauf, VOR dem
      trap-Teardown, via `sudo -u postgres psql -d "$TEST_DB"` (peer-auth, passwordless, SCHILD-Muster), dass jede
      crm.* Tabelle == 0 Rows ist (als postgres bypassed psql FORCE-RLS → sieht ALLE Tenants → faengt Cross-Tenant-
      Leaks). Dieser Fixture hat KEINEN crm.*-Arm, KEINE separate superuser-Connection, KEIN NERVE_BASELINE_GUARD_DSN.
      Der Fixture-Docstring nennt explizit: „crm.* wird POST-SUITE in deploy.sh (Plan 02) geprueft, nicht hier."
    - SECURITY-TESTS PASSEN: rls_isolation/meeting_save_rls/nerve_app_pg/anon_worker committen + loeschen in ihrem
      eigenen POST-yield-Teardown (test_rls_isolation.py:101-116, via cleanup_rows) → ihre public-Rows == Baseline
      (in-pytest-Waechter gruen) UND ihre crm.*-Rows == 0 (POST-SUITE-crm-Check Plan 02 gruen). Leaken sie public →
      in-pytest-Waechter faengt es; leaken sie crm → der POST-SUITE-Check (Plan 02) faengt es = ein ECHTER Fund
      (André: gewollt, surface it, nicht ausnehmen). Es gibt nur ~4 crm-Writer → Culprit-Narrowing trivial.
    - SELBSTTEST (tests/test_baseline_guard.py): ein dedizierter Test, der den Waechter-MECHANISMUS beweist —
      ein Sub-Test committet absichtlich eine Row und raeumt sie NICHT auf und erwartet, dass der Waechter rot
      wird (z.B. via pytester/in-process-Assertion ODER ein bewusst-leakender Test + xfail-Mechanik); plus ein
      sauberer Test, der gruen bleibt. Das ist eine echte Runtime-Assertion auf das Waechter-Verhalten (keine
      Source-Presence).
  </behavior>
  <action>
    1. **Snapshot-Fixture** (session-scoped, depends on dem Base-Seed aus Task 4 → laeuft danach): liest pro
       relevanter PUBLIC Tabelle das PK-Set ueber die MODUL-Session (nerve_app, kein RLS auf public). Speichere
       `BASELINE = {tabelle: frozenset(pks)}` in einem session-globalen Objekt. KEINE crm.*-Arme, KEINE separate
       superuser-Connection, KEIN NERVE_BASELINE_GUARD_DSN — crm.* deckt der POST-SUITE-Check in Plan 02. Die
       public-Tabellen-Liste aus models.py public ableiten (organisations, users, tenant_orgs, api_rates,
       fixed_costs, prompt_versions, training_scenarios, changelog, calls, conversation_logs, api_cost_log,
       revenue_log, ewb_ratings, profiles, profile_opener, exchange_rates).
    2. **Waechter-Fixture** (`@pytest.fixture(autouse=True)`, function-scoped): NACH `yield` (also nach dem Test
       UND nach dem Test-eigenen cleanup_rows-Teardown — Ordering via frueher Anforderung, s. behavior) liest sie
       pro PUBLIC Tabelle das aktuelle PK-Set (MODUL-Session, nerve_app) und asserted `current_pks == BASELINE[tabelle]`.
       Bei Abweichung: `pytest.fail(f"[BASELINE-GUARD] {request.node.nodeid}: Tabelle {t} drifted — "
       f"leaked={current-baseline}, missing={baseline-current}")` (fail-closed). KEINE crm.*-Arme — crm.*-Sauberkeit
       (jede crm.* Tabelle == 0) verifiziert der POST-SUITE-Check in deploy.sh (Plan 02, sudo-postgres).
    3. **Ordering konkret:** mache den Waechter zu einer der zuerst-angeforderten autouse-Fixtures (z.B. indem die
       test-eigenen committenden Fixtures in Plan 03/04 den Waechter NICHT direkt anfordern, aber der Waechter
       autouse + frueh im conftest definiert ist; pytest fuehrt Teardowns in umgekehrter Setup-Reihenfolge aus →
       frueh aufgesetzt = spaet abgebaut = sieht den finalen, aufgeraeumten Zustand). Dokumentiere die Anforderung
       im Docstring. Falls nicht robust erreichbar → POST-SUITE-Fallback (session-finalizer, nennt dann Tabelle +
       PKs, aber nicht den einzelnen nodeid; Tradeoff dokumentieren, D-08).
    4. **crm.*-Abdeckung = POST-SUITE in Plan 02 (HYBRID, André locked — KEINE Env-Var-Kopplung):** dieser in-
       pytest-Waechter prueft NUR public.*. Die crm.*-Sauberkeit (jede crm.* Tabelle == 0 Rows) prueft deploy.sh
       (Plan 02) NACH dem pytest-Lauf, VOR dem trap-Teardown, via `sudo -u postgres psql -d "$TEST_DB"` (peer-auth,
       passwordless, EXAKT das SCHILD-Guard-Muster). KEIN NERVE_BASELINE_GUARD_DSN, KEINE postgres-scram-DSN,
       KEINE BYPASSRLS-Rolle, KEIN PW in conftest oder im Test-Env (Briefing-Vorgabe). Plan 02 traegt den
       POST-SUITE-crm-Check (cross-ref Plan 02). Dieser Plan setzt VORAUS, dass jeder crm-Writer im Teardown via
       cleanup_rows auf 0 zurueckraeumt (sonst faengt der POST-SUITE-Check den Leak).
    5. **Selbsttest tests/test_baseline_guard.py:** beweise den Mechanismus runtime — z.B. mit dem `pytester`/
       `pytest.Pytester`-Plugin einen Mini-Test ausfuehren, der eine Row committet ohne cleanup, und asserten dass
       der Waechter ihn rot macht; plus ein sauberer Fall der gruen bleibt. ALTERNATIV (wenn pytester zu schwer):
       ein Test, der den Waechter-Vergleichs-Kern (current_pks vs baseline) als Funktion direkt aufruft mit
       konstruierten PK-Sets (leaked/missing/clean) und die fail/pass-Logik asserted. Echte Runtime-Assertion auf
       das Waechter-Verhalten — KEINE Source-Presence (kein inspect.getsource/grep). SKIP server-side-only wenn
       noetig (TEST_DATABASE_URL), aber der Vergleichs-Kern-Test kann DSN-frei laufen.
    6. **Naming:** Waechter-Fixture `_baseline_cleanup_guard` (autouse) + Snapshot-Fixture z.B.
       `_baseline_snapshot` (session). Selbsttest-Datei `tests/test_baseline_guard.py`.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy1d.log | grep -E "test_baseline_guard|_baseline_cleanup_guard|BASELINE-GUARD|crm.* nicht leer|baseline|passed|failed|drifted"; echo "EXIT=$?"  # Im Gate: _baseline_cleanup_guard laeuft autouse nach jedem Test (PUBLIC.*-only); tests/test_baseline_guard.py PASSED (Mechanismus beweist: leakender public-Test => rot, sauberer => gruen); kein BASELINE-GUARD-drifted-FAIL fuer korrekt aufraeumende Tests; der POST-SUITE-crm-Check (Plan 02) meldet keine crm.*-Leak-Rows. grep-style: `grep -nE "_baseline_cleanup_guard|_baseline_snapshot" tests/conftest.py` present; `grep -n "NERVE_BASELINE_GUARD_DSN" tests/conftest.py` LEER (kein superuser-DSN-Pfad mehr).</automated>
  </verify>
  <done>
    `tests/conftest.py` enthält den session-scoped `_baseline_snapshot` (friert nach Base-Seed (Task 4) +
    app-import-Seeds das PK-Set jeder relevanten PUBLIC Daten-Tabelle ein, via MODUL-Session/nerve_app — KEINE
    crm.*-Arme, KEIN superuser-Conn, KEIN NERVE_BASELINE_GUARD_DSN) + die autouse function-scoped
    `_baseline_cleanup_guard` (asserted nach JEDEM Test — NACH dem Test-eigenen cleanup_rows — current_pks ==
    baseline pro PUBLIC Tabelle; Drift → fail-closed mit nodeid + Tabelle + leaked/missing PKs). crm.* wird NICHT
    in-pytest geprueft — die crm.*-Sauberkeit (jede crm.* Tabelle == 0 Rows) verifiziert der POST-SUITE-Check in
    deploy.sh (Plan 02, `sudo -u postgres psql`, peer-auth, passwordless, SCHILD-Muster). Die Ordering-Anforderung
    (Pruefung nach Test-Teardown) ist umgesetzt + im Docstring dokumentiert (Fallback POST-SUITE mit Tradeoff).
    `tests/test_baseline_guard.py` beweist den Mechanismus runtime (leakender public-Test → Waechter rot; sauberer →
    gruen) als echte Assertion (keine Source-Presence). Die Security-Tests (rls_isolation/meeting_save_rls/nerve_app/
    anon_worker) passieren den public-Waechter (eigener Teardown) + raeumen ihre crm.*-Rows auf 0 (POST-SUITE-Check
    Plan 02 gruen); leaken sie public → in-pytest-Waechter faengt es, leaken sie crm → POST-SUITE-Check faengt es
    (echter Fund). KEIN NERVE_BASELINE_GUARD_DSN (HYBRID, André locked: crm.* via POST-SUITE statt superuser-DSN).
    Im Gate-Lauf: kein faelschlicher Drift-FAIL fuer korrekt aufraeumende Tests; test_baseline_guard PASSED; der
    POST-SUITE-crm-Check (Plan 02) meldet 0 Leak-Rows.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test-Fixture → Postgres-Rolle | Fixtures verbinden als nerve_app/nerve_anon_worker (rolbypassrls=f) — RLS engaged |
| conftest-DSN → DB-Ziel | DSN-Wert entscheidet ob nerve_test (sicher) oder nerve (Prod, verboten) berührt wird |
| db.py-Import-DATABASE_URL → Hook-Registrierung | DATABASE_URL beim Import entscheidet ob der after_begin-RLS-Hook überhaupt existiert (A-1) |
| Base-Seed → schema-only nerve_test | FK-tragende generische Tests setzen user_id=1/org_id=1 voraus — ohne Base-Seed FK/NOT-NULL-Bruch auf der zero-data PG |
| client._test_session/_test_engine → ~20 Konsumenten-Tests | der client-Rewrite-Vertrag entscheidet ob db_from_client + 4 Test-Dateien laufen oder an AttributeError zerbrechen (fail-closed Gate) |
| committender Test → persistentes nerve_test (Baseline) | committete + nicht-aufgeraeumte Rows driften die Baseline → False-Green/Red Folge-Tests; cleanup_rows (Ext 1) + Baseline-Waechter (Ext 2) sind die Gegenmittel |
| in-pytest-Waechter → public.* | der in-pytest `_baseline_cleanup_guard` prueft NUR public.* (nerve_app liest public unfiltered, kein RLS) |
| POST-SUITE-crm-Check (Plan 02) → crm.* (FORCE-RLS) | als nerve_app saehe ein in-pytest-Waechter crm.* nur tenant-gefiltert → Cross-Tenant-Leak unsichtbar → daher crm.* POST-SUITE via `sudo -u postgres psql` (peer, bypasses RLS) in Plan 02, HYBRID; jeder crm-Writer raeumt im Teardown auf 0 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-01 | Tampering | Fixture-DSN zeigt versehentlich auf Prod-`nerve` | mitigate | Kein hardcoded `@/nerve` in conftest (grep-verifiziert Task 3); DSN-Wert kommt ausschließlich vom Gate (Plan 02 setzt nerve_test) |
| T-PGTEST-02 | Information Disclosure | BYPASSRLS-Rolle für generische Tests → RLS-Defekt unsichtbar (False-Green) | mitigate | D-05: generische Fixtures verbinden als nerve_app (rolbypassrls=f, RESEARCH Q1a bewiesen) + set_current_tenant; KEINE Superuser/BYPASSRLS-Rolle FUER TEST-PFADE. (Der Baseline-Waechter Task 6 nutzt superuser NUR als READ-ONLY-Symptom-Leser, kein Test-Pfad — T-PGTEST-25.) |
| T-PGTEST-03 | Information Disclosure | crm-Tests ohne Tenant-Kontext ODER mit frischer sessionmaker (Hook feuert nicht) → RLS fail-closed → 0 Zeilen (Test grün trotz kaputt) | mitigate | D-05 set_current_tenant(TEST_TENANT_UUID) + tenant_orgs-Seed; SOWOHL db_session ALS AUCH client binden das MODUL-SessionLocal via `dbmod.SessionLocal.configure(bind=engine)` um (NICHT frische `TestSession = sessionmaker(...)`, NICHT monkeypatch von SessionLocal auf ein neues Objekt — Gemini-HIGH), damit der after_begin-Hook auf JEDER genutzten Session feuert (db_session UND API-Integration über client); Gate verifiziert crm-Read liefert geseedete Zeile (≥1, nicht 0) auch über den client-Pfad |
| T-PGTEST-04 | Information Disclosure | anon_worker-PW in conftest hardcodet/geloggt | accept | PW lebt nur in Gate-Env (Plan 02 sourct ionos-s3.env); conftest liest nur die fertige DSN-Env-Var, nie das nackte PW |
| T-PGTEST-16 | Tampering | `SessionLocal.configure(bind=engine)` ohne Reset → nach engine.dispose() bleibt das MODUL-SessionLocal an eine tote Engine gebunden, leakt in spätere Tests | mitigate | Gemini-MEDIUM: beide Fixtures (db_session + client) rufen im finally `dbmod.SessionLocal.configure(bind=None)` NACH engine.dispose() → keine tote Engine-Bindung im Modul-Zustand |
| T-PGTEST-18 | Spoofing/Information Disclosure | DATABASE_URL unset im pytest-Prozess (Gate-Subshell) → db.py:9 picked den sqlite-Default beim Import → der after_begin-RLS-Hook (db.py:87) wird NIE registriert (db.py:86) → set_current_tenant inert (contextvar von niemandem gelesen) → generische crm-Reads 0 Zeilen, Tests passen STILL (False-Green) | mitigate | A-1 HARD PRECONDITION (Fixture-Seite, Spiegel zu Plan 02 FIX 1): die db_session/client-Umbindung via `configure(bind=engine)` BEWAHRT nur einen import-registrierten Hook — die Registrierung selbst garantiert das Gate (Plan 02 exportiert DATABASE_URL=postgres in der pytest-Subshell). Der DEDIZIERTE A-1-Tripwire (tests/test_rls_generic_smoke.py, Task 2) asserted (a) current_setting('app.tenant_id') == TEST_TENANT_UUID NON-null + (b) crm-Read ≥1 Zeile auf dem generischen db_session-Pfad → dreht den Defekt von silent-green auf loud-red. Cross-ref Plan 02 T-PGTEST-18. |
| T-PGTEST-20 | Denial | Generische Tests inserten FK-tragende Rows (user_id=1/org_id=1) in die schema-only/zero-data nerve_test → ForeignKeyViolation/NOT-NULL → fail-closed Gate blockt jeden Deploy (False-Red blocker-class wie test_08_14/test_tenant_orgs) | mitigate | Task 4: Session-Scope Base-Seed (1 Org id=1 + 1 User id=1) über den ORM-Pfad (Python-Defaults für is_superadmin/is_test_user/market/language) + Sequenz-Advance (setval organisations_id_seq + users_id_seq, PG-explicit-id-Gotcha) + trigger-aware (trg_mk_tenant_org erzeugt tenant_orgs, kein manueller Insert). Hängt am A-1-Fix (DATABASE_URL=postgres → MODUL-Engine ist nerve_test, Hook aktiv). Deckt 6 der 11 FK-Tests (André/Claudian-Klassifikation); die 5 Deltas in Plan 03. |
| T-PGTEST-22 | Denial | Der `client`-Rewrite (`dbmod.SessionLocal.configure(bind=engine)` + monkeypatch von engine) lässt den bestehenden `_test_session`/`_test_engine`-Attribut-Vertrag (IST-conftest Z.84-85) fallen → `db_from_client` (Z.95-97 `return client._test_session`) + `client._test_session`/`client._test_engine`-Direktzugriffe werfen AttributeError im Setup von ~20 Gate-Tests (test_admin_dashboard_auth 4×, test_auth_next_redirect:106, test_ewb_rate_api ~11×, test_profile_editor_validation 4×) → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy | mitigate | pre-execute blocker fix 2026-06-15: der `client`-Rewrite (Task 1) re-exponiert NACH `configure(bind=engine)` + set_current_tenant, VOR `yield c`: `c._test_session = dbmod.SessionLocal()` (MODUL-SessionLocal — hook-tragende PG-Session, NICHT eine frische sessionmaker) + `c._test_engine = engine` (nerve_test-PG-Engine); im finally `c._test_session.close()` (best-effort). `db_from_client` (Z.95-97) bleibt UNVERÄNDERT und returnt nun die MODUL-SessionLocal-PG-Session → die 4 Konsumenten-Dateien laufen WEITER (admin_dashboard_auth + auth_next_redirect ohne jede Edit; ewb_rate_api + profile_editor_validation mit den FK-Deltas #8/#9 in Plan 03 — NICHT in files_modified dieses Plans). |
| T-PGTEST-24 | Denial (False-Red/False-Green) | Ein committender Test laesst seine Rows in nerve_test liegen (kein Teardown / Teardown lief nicht) → Baseline-Drift: Folge-Tests sehen Fremd-Rows → globale counts/Reads kippen (False-Red) ODER ein RLS-Leak-Test sieht eine fremde Row die er nicht sehen duerfte (False-Green). Persistentes nerve_test (D-03 1x-Build) verstaerkt das ueber den ganzen Lauf. | mitigate | Extension 1 (Task 5): gemeinsamer `cleanup_rows`-Helfer (reverse-FK, crm.* unter Tenant-GUC, best-effort, POST-yield analog test_rls_isolation.py:101-116) + Ein-Zeilen-Konvention in conftest.py UND CLAUDE.md. Extension 2 (Task 6): autouse `_baseline_cleanup_guard` erzwingt die PUBLIC.*-Sauberkeit strukturell (public-DB == Session-Start-Baseline nach jedem Test, fail-closed, nennt nodeid+Tabelle+geleakte PKs); crm.*-Sauberkeit (jede crm.* Tabelle == 0) erzwingt der POST-SUITE-Check in Plan 02 (sudo-postgres). Jeder committende Test (Group A/B, Plan 03/04) adoptiert cleanup_rows. Security-Tests + die ~4 crm-Writer raeumen selbst auf → in-pytest-Waechter (public) + POST-SUITE-crm-Check gruen. |
| T-PGTEST-25 | Information Disclosure | Ein in-pytest-Waechter, der crm.* als nerve_app liest (tenant-gefiltert, FORCE-RLS + GUC nie gecleart), sieht nur EINEN Tenant → eine geleakte Row mit FREMDEM tenant_id ist fuer ihn unsichtbar → Cross-Tenant-Leak rutscht durch (False-Green) | mitigate | HYBRID (André locked 2026-06-15, Option 1): crm.* wird NICHT in-pytest geprueft (vermeidet sowohl den nerve_app-Blindfleck ALS AUCH das Holen eines Superuser/BYPASSRLS-Lesepfads ins Test-Env). Stattdessen prueft deploy.sh (Plan 02) crm.* POST-SUITE — nach dem pytest-Lauf, VOR dem trap-Teardown — via `sudo -u postgres psql -d "$TEST_DB"` (peer-auth, passwordless, EXAKT das bestehende SCHILD-Guard-sudo-postgres-Muster, KEINE neue Env-Var, KEIN PW): als postgres bypassed psql FORCE-RLS → assertet jede crm.* Tabelle == 0 Rows ueber ALLE Tenants → faengt Cross-Tenant-Leaks; Leak (>0) → exit≠0, kein Restart/Deploy. crm.*-Baseline = 0 (kein app-import-Seeder beruehrt crm.*); jeder crm-Writer (~4: rls_isolation/meeting_save_rls/anonymizer-RLS-Gruppe + A-1-Tripwire falls er committet + geportete crm-Tests) raeumt im Teardown via cleanup_rows auf 0. KEIN NERVE_BASELINE_GUARD_DSN, KEINE postgres-scram-DSN, KEINE BYPASSRLS-Rolle. Der in-pytest-Waechter (T-PGTEST-24) prueft public.* (nerve_app, unfiltered). T-PGTEST-02 (kein BYPASSRLS-Test-Pfad) bleibt vollstaendig gewahrt — der POST-SUITE-psql-Check ist kein Test-Pfad, sondern ein deploy.sh-Guard-Schritt. |

</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen

- `public.organisations` (schreiben — generischer Seed via Trigger-Muster UND Base-Seed id=1) — Trigger `trg_mk_tenant_org` legt automatisch die `tenant_orgs`-Row an
- `public.users` (schreiben — Base-Seed id=1, org_id=1, email UNIQUE) — PUBLIC, kein RLS
- `public.tenant_orgs` (lesen — die vom Trigger erzeugte UUID; Quelle für set_current_tenant + crm.*-FK; vom Base-Org-Insert ebenfalls automatisch erzeugt)
- `crm.accounts` (schreiben + lesen — der A-1-Tripwire seedet 1 Row mit tenant_id=TEST_TENANT_UUID und liest sie unter dem Tenant-GUC zurück; cleanup_rows loescht sie wieder) — RLS engaged
- `crm.*` (lesen, indirekt über generische crm-berührende Tests / Plan-03-Ports; der POST-SUITE-crm-Check in Plan 02 liest crm.* UNGEFILTERT via `sudo -u postgres psql` und assertet == 0 Rows) — RLS engaged unter dem gesetzten Tenant-GUC (Tests) bzw. RLS-bypassed (POST-SUITE-psql-Leser, Plan 02)
- PUBLIC committed-data-Tabellen (in-pytest-Baseline-Snapshot-Ziel von Extension 2): public.{organisations,users,tenant_orgs,api_rates,fixed_costs,prompt_versions,training_scenarios,changelog,calls,conversation_logs,api_cost_log,revenue_log,ewb_ratings,profiles,profile_opener,exchange_rates} — der in-pytest-Waechter snapshottet ihr PK-Set
- crm.{accounts,account_memory,contacts,meetings,user_preferences} — NICHT im in-pytest-Snapshot; Baseline = 0 Rows pro Tabelle, geprueft POST-SUITE in Plan 02 via sudo-postgres

### inspect.sh / Katalog-Beleg (zitiert aus RESEARCH + models.py + ENUMERATION)

`tenant_orgs` wird vom AFTER-INSERT-Trigger auf `organisations` erzeugt — verbatim aus
test_rls_isolation.py:33-54 (RESEARCH Q4, „Trigger-tenant_orgs-Muster"):
```
INSERT INTO public.organisations (name) VALUES (%s) RETURNING id
SELECT id::text FROM public.tenant_orgs WHERE legacy_org_id = %s   -- trg_mk_tenant_org füllt das
```
Base-Seed-NOT-NULL-Beleg (models.py:19-135, verifiziert): Organisation hat NUR `name` als NOT-NULL ohne
Default; User hat `org_id`+`email` als NOT-NULL ohne Default und `is_superadmin`/`is_test_user`/`market`/
`language` als NOT-NULL mit nur PYTHON-`default=` (kein server_default) → ORM-Insert-Pfad Pflicht, sonst
NOT-NULL-Bruch. `passwort_hash` ist nullable=True (OAuth-Sentinel). Sequenz-Namen PG-Default:
`organisations_id_seq`, `users_id_seq` (im read_first an der DB zu verifizieren).

Baseline-Contract (PERSISTENCE-ENUMERATION.md): `from app import app` committet app-import-Seeds (demo
Organisation+User, ApiRate+FixedCost, ~4-6 PromptVersion inkl. 2 ewb, TrainingScenario, Changelog) +
tenant_orgs via Trigger; PLUS Base-Seed (Org+User id=1). → NICHT-leere Baseline-Tabellen: organisations,
users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios, changelog. crm.* ist in der
Baseline LEER (PK-Set {}). Diese Mengen sind der Snapshot-Inhalt von Extension 2.

crm-POST-SUITE-Check (Plan 02, HYBRID, André locked — KEINE Env-Var im Test-Env): der in-pytest-Waechter laeuft
als OS-User nerve_app und kann crm.* nur tenant-gefiltert lesen → daher prueft er crm.* NICHT. Stattdessen fuehrt
deploy.sh (Plan 02) NACH dem pytest-Lauf, VOR dem trap-Teardown, einen `sudo -u postgres psql -d "$TEST_DB"`
Schritt aus (peer-auth, passwordless — EXAKT das bestehende SCHILD-Guard-sudo-postgres-Muster). Da der deploy.sh-
heredoc-Block als root laeuft, gelingt `sudo -u postgres` per peer (kein PW). Als postgres bypassed psql FORCE-RLS
→ es summiert `SELECT count(*)` ueber alle crm.* Tabellen und assertet == 0 (Baseline leer). KEIN
NERVE_BASELINE_GUARD_DSN, KEINE postgres-scram-DSN, KEINE BYPASSRLS-Rolle. Das ist dasselbe peer-postgres-Muster,
mit dem deploy.sh ohnehin CREATE/DROP DATABASE + den Schema-Dump fuehrt.

crm-RLS-Treue (aus RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test bewiesen):
7 crm-RLS-Policies, ENABLE+FORCE auf allen 5 crm-Tabellen (`relrowsecurity=t, relforcerowsecurity=t`),
GRANTs nerve_app=DML / nerve_anon_worker=SELECT. → crm.* liefert ohne Tenant-GUC 0 Zeilen (fail-closed);
MIT gesetztem Tenant die geseedete Zeile; als superuser (Waechter) ALLE Zeilen (RLS-bypassed).

client._test_session/_test_engine-Vertrag (IST-conftest Z.84-97, live-source verifiziert): unveraendert wie zuvor.

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| `TEST_TENANT_UUID` | Seed-Helper liest `tenant_orgs.id` zurück | DB-Spalte `public.tenant_orgs.id` (UUID, vom Trigger erzeugt) | ✓ Trigger-Muster bewiesen (test_rls_isolation.py:33-54, RESEARCH Q4) |
| Base-Seed Org(id=1) + User(id=1) | ORM-INSERT in `organisations`/`users` (Python-Defaults greifen) | DB-Tabellen `public.organisations`/`public.users` (PUBLIC, kein RLS) | ✓ models.py:19-135 NOT-NULL-Map verifiziert; ORM-Pfad Pflicht |
| `set_current_tenant(uuid)` → `app.tenant_id` GUC | after_begin-Hook auf MODUL-SessionLocal | transaktions-lokaler GUC (set_config, NICHT DB-Spalte) | ✓ db.py:87; greift via MODUL-SessionLocal-Umbindung + DATABASE_URL=postgres (A-1) |
| `client._test_session` / `client._test_engine` | client-Rewrite re-exponiert; db_from_client returnt _test_session | MODUL-SessionLocal-PG-Session (hook-tragend) + nerve_test-Engine | ✓ IST-conftest Z.84-97; T-PGTEST-22 |
| `cleanup_rows({tabelle: ids}, tenant)` | committender Test ruft im POST-yield-Teardown | reverse-FK DELETE der test-eigenen Rows (crm.* unter Tenant-GUC, public.* ohne) | ✓ Vorbild test_rls_isolation.py:101-116; loescht NUR uebergebene IDs, nie Baseline (T-PGTEST-24) |
| `_baseline_snapshot` PK-Sets | Session-Start nach Base-Seed: NUR public.* MODUL-Session | in-memory `{tabelle: frozenset(pks)}` (Vergleichsbasis, public-only) | ✓ Baseline-Contract (ENUMERATION); crm.* NICHT im Snapshot (POST-SUITE Plan 02) |
| `_baseline_cleanup_guard` Vergleich | autouse POST-yield NACH Test-cleanup: current_pks vs baseline (public-only) | DB-State-Read (public.* MODUL-Session) | ✓ fail-closed bei Drift; Ordering: Pruefung nach Test-Teardown (Docstring + frueh-angefordert) |
| crm.* == 0 (POST-SUITE-Check) | deploy.sh (Plan 02) NACH pytest, VOR trap: `sudo -u postgres psql` summiert count(*) ueber crm.* | DB-State-Read (crm.* als postgres, RLS-bypassed) | ✓ HYBRID (André locked); peer-auth, passwordless, SCHILD-Muster; KEINE Env-Var/DSN; jeder crm-Writer raeumt auf 0 |

### Bei Diskrepanz: STOP + Replan
(z.B. Base-Seed RAW-SQL statt ORM → NOT-NULL-Bruch → ORM-Pfad; manueller tenant_orgs-Insert → UNIQUE-Bruch
→ Trigger nutzen; client-Rewrite ohne _test_session-Re-Exposition → AttributeError → Vertrag re-exponieren;
in-pytest-Waechter prueft crm.* als nerve_app → Cross-Tenant-Leak unsichtbar → STOP, crm.* gehoert in den
POST-SUITE-Check (Plan 02, sudo-postgres), NICHT in-pytest; Waechter-Pruefung VOR dem Test-cleanup → False-Positive
fuer korrekt aufraeumende Tests → STOP, Ordering fixen (Pruefung nach Test-Teardown); irgendjemand fuehrt
NERVE_BASELINE_GUARD_DSN/eine postgres-scram-DSN/eine BYPASSRLS-Rolle ins Test-Env ein → STOP, das ist verworfen
(HYBRID: crm.* via POST-SUITE-sudo-postgres-peer, kein Superuser-PW im Test-Env))

<verification>
- Req-2: `grep "sqlite:///:memory:" tests/conftest.py` → kein aktiver Treffer (server-side gegen deployed conftest).
- Req-5: kein hardcoded `@/nerve` (ohne `_test`) in conftest; im Gate-Log verbinden alle DSNs gegen nerve_test.
- Req-9 (Teilbeitrag): schild_guard_pg_conn liest weiterhin NERVE_SCHILD_TEST_DSN (Gate setzt nerve_test) — Schild-Guard bleibt lauffähig.
- A-1-Tripwire: tests/test_rls_generic_smoke.py PASSED im Gate-Lauf (GUC NON-null + crm-Read ≥1 Zeile).
- client-Vertrag (T-PGTEST-22): re-exponierter Vertrag + unverändertes db_from_client present; die ~20 Konsumenten PASSED (kein AttributeError).
- Base-Seed (T-PGTEST-20): die 6 FK-Konsumenten PASSED im Gate-Lauf; session-scope + autouse + setval grep-verifiziert; Base-Seed laeuft VOR dem Baseline-Snapshot.
- Extension 1 (T-PGTEST-24): `grep "def cleanup_rows(" tests/conftest.py` + `grep cleanup_rows CLAUDE.md` → present; Helfer modelliert auf test_rls_isolation.py:101-116; CLAUDE.md traegt die Konventionsregel.
- Extension 2 (T-PGTEST-24/25): `grep "_baseline_cleanup_guard" tests/conftest.py` present (PUBLIC.*-only); `grep "NERVE_BASELINE_GUARD_DSN" tests/conftest.py` LEER (kein superuser-DSN-Pfad mehr); im Gate laeuft der Waechter autouse nach jedem Test (public.*); tests/test_baseline_guard.py PASSED (Mechanismus-Beweis: leakender public-Test → rot); kein faelschlicher Drift-FAIL fuer korrekt aufraeumende Tests; jeder committende Test (Plan 03/04) == public-Baseline nach Teardown.
- crm-POST-SUITE-Check (HYBRID, André locked): crm.*-Sauberkeit (jede crm.* Tabelle == 0) prueft Plan 02 POST-SUITE via `sudo -u postgres psql` (peer, passwordless, SCHILD-Muster) — KEIN NERVE_BASELINE_GUARD_DSN, KEIN Superuser-PW im Test-Env; im Gate-Log meldet der Check 0 crm.*-Leak-Rows.
- Voll-Beleg erst im Plan-02-Gate-Lauf: generische crm-Tests + API-Integration + A-1-Tripwire + die 6 FK-Konsumenten + die ~20 db_from_client-Konsumenten + der Baseline-Waechter (gruen fuer alle korrekt aufraeumenden Tests, test_baseline_guard PASSED) PASSED.
</verification>

<success_criteria>
- db_session + client verbinden gegen TEST_DATABASE_URL (nerve_test), kein sqlite im aktiven Pfad.
- TEST_TENANT_UUID/Seed via Trigger-Muster vorhanden (Org-Name uuid-suffixed); set_current_tenant am Fixture-Start aufgerufen.
- db_session UND client binden das MODUL-`database.db.SessionLocal` via `configure(bind=engine)` um (NICHT frische sessionmaker) → after_begin-Hook feuert auf beiden Pfaden; crm-Read liefert ≥1 Zeile (nicht 0).
- Der `client` re-exponiert `_test_session`/`_test_engine` (MODUL-SessionLocal, hook-tragend) → die ~20 Konsumenten-Tests laufen ohne AttributeError (T-PGTEST-22); `db_from_client` unverändert.
- Beide Fixtures resetten im finally `SessionLocal.configure(bind=None)`.
- A-1-Tripwire (tests/test_rls_generic_smoke.py) asserted GUC NON-null + crm-Read ≥1 Zeile; im Gate PASSED; raeumt seine crm-Row via cleanup_rows wieder weg (baseline-sauber).
- Session-Scope Base-Seed (Org id=1 + User id=1) existiert, trigger-aware, ORM-Pfad, Sequenzen advanced, laeuft VOR dem Baseline-Snapshot → die 6 FK-Konsumenten brechen nicht an FK/NOT-NULL.
- 3 Spezial-Fixturen DSN-Ziel-Doku = nerve_test; keine hardcoded Prod-nerve-DSN.
- EXTENSION 1: gemeinsamer `cleanup_rows`-Helfer in conftest.py (reverse-FK, crm.* unter Tenant-GUC, best-effort, loescht nur test-eigene IDs) + Ein-Zeilen-Konvention in conftest.py-Docstring UND als neue CLAUDE.md-Regel (committende Tests raeumen via cleanup_rows auf, vom Waechter erzwungen). Code-Identifier ASCII.
- EXTENSION 2 (PUBLIC.*-only, HYBRID, André locked): autouse `_baseline_cleanup_guard` + session `_baseline_snapshot` — snapshottet nach Base-Seed das PK-Set jeder relevanten PUBLIC Daten-Tabelle (via MODUL-Session/nerve_app, unfiltered — kein RLS auf public), asserted nach jedem Test (NACH dem Test-cleanup) public-DB == Baseline, fail-closed mit nodeid+Tabelle+leaked/missing PKs. crm.* wird NICHT in-pytest geprueft — KEIN NERVE_BASELINE_GUARD_DSN, KEINE postgres-scram-DSN, KEINE BYPASSRLS-Rolle, KEIN Superuser-PW im Test-Env. Ordering: Pruefung nach Test-Teardown (Docstring + frueh-angefordert; POST-SUITE-Fallback dokumentiert). Security-Tests passieren den public-Waechter (eigener Teardown); leaken sie public → echter Fund. tests/test_baseline_guard.py beweist den Mechanismus runtime (leakender public-Test → rot).
- crm.*-Sauberkeit (jede crm.* Tabelle == 0 Rows) wird POST-SUITE in deploy.sh (Plan 02) via `sudo -u postgres psql` (peer-auth, passwordless, SCHILD-Muster) erzwungen — fail-closed (Leak → exit≠0, kein Restart). Jeder crm-Writer (~4) raeumt im Teardown via cleanup_rows auf 0.
- Jeder committende Test (Group A + Group B, Plan 03 + Plan 04) ist nach seinem Teardown == public-Baseline (in-pytest-Waechter GRUEN) UND seine crm.*-Rows == 0 (POST-SUITE-crm-Check Plan 02 GRUEN).
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-01-SUMMARY.md`
</output>

########## DATEI: .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-02-deploy-gate-block-PLAN.md ##########
---
phase: 08.23.2.PGTEST
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - deploy.sh
autonomous: true
requirements: [Req-1, Req-3, Req-4, Req-5, Req-7, Req-8, Req-9]
complexity: "🔴 (security-near — CREATE/DROP DATABASE auf Prod-Instanz, anon_worker-PW-Handling, fail-closed)"
user_setup: []

must_haves:
  truths:
    - "Das deploy.sh-Gate provisioniert nerve_test, baut Schema per pg_dump-Restore vom Prod-nerve + upgrade-only-neue-Revs, fährt pytest dagegen, räumt nerve_test ab"
    - "CREATE/DROP DATABASE + alle 4 Test-DSNs zielen ausschliesslich auf nerve_test (Whitelist-Guard, Abbruch statt Raten)"
    - "Jeder Schritt (Pre-DROP, CREATE, schema-dump, stamp-dump, upgrade, pytest) bricht bei Fehler mit eigenem Klartext-Grund ab — kein SQLite/Prod-Ausweich"
    - "trap cleanup EXIT garantiert DROP nerve_test auch bei Test-Fehler/SIGTERM; Pre-Run-DROP entfernt verwaiste nerve_test"
    - "anon_worker-PW wird aus ionos-s3.env gesourct und nie geloggt; Schild-Guard läuft gegen nerve_test"
    - "Der dump-gebaute nerve_test trägt die echten crm-RLS-Policies/FORCE/GRANTs treu (kein False-Green) — inline-Katalog-Gate prüft das bei JEDEM Deploy"
    - "Die pytest-Subshell exportiert DATABASE_URL=postgresql://nerve_app@/nerve_test (NICHT nur TEST_DATABASE_URL) — sonst sieht db.py beim Import den sqlite-Default, der after_begin-RLS-Hook wird NIE registriert und set_current_tenant bleibt inert (A-1 False-Green-Killer)"
    - "Die gesamte Phase (Plan 01 + 02 + 03 + 04) wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM alle Pläne committet sind — kein Zwischen-Deploy nach Wave 1 (das Gate self-testet den deployten Baum, der nur mit Wave-2-Code konsistent ist)"
    - "NACH dem pytest-Lauf, VOR dem trap-Teardown, prueft ein POST-SUITE-crm-Baseline-Schritt via `sudo -u postgres psql -d nerve_test` (peer-auth, passwordless, SCHILD-Muster), dass jede crm.* Tabelle == 0 Rows ist (crm.*-Baseline leer) — als postgres RLS-bypassed ueber ALLE Tenants → Cross-Tenant-Leak (>0) bricht fail-closed (exit≠0, kein Restart/Deploy). HYBRID (André locked): crm.* wird NICHT in-pytest geprueft (Plan 01-Waechter ist public.*-only); KEIN NERVE_BASELINE_GUARD_DSN, KEIN Superuser-PW im Test-Env"
  artifacts:
    - path: "deploy.sh"
      provides: "Postgres-Test-Gate-Block (Provision → pg_dump-Restore-Build → inline-Katalog-Treue-Gate → pytest 4-DSN+DATABASE_URL → POST-SUITE-crm-Baseline-Check (sudo-postgres, crm.* == 0) → Teardown) mit Whitelist-Guard + pipefail + fail-closed"
      contains: "nerve_test"
  key_links:
    - from: "deploy.sh Gate-Block"
      to: "pg_dump --schema-only nerve | psql nerve_test  +  pg_dump --data-only --table=alembic_version  +  alembic upgrade head"
      via: "DATABASE_URL=postgresql://postgres@/nerve_test als postgres, set -o pipefail in den Dump-Pipes"
      pattern: "pg_dump --schema-only|--table=alembic_version|upgrade head|set -o pipefail"
    - from: "deploy.sh Gate-Block"
      to: "pytest tests/ mit 4 nerve_test-DSNs + DATABASE_URL"
      via: "sudo -u nerve_app ANON_PW=... TEST_DB=... bash -c '...' (Env-Übergabe, single-quoted inner), DATABASE_URL gesetzt damit db.py-Import den RLS-Hook registriert"
      pattern: "DATABASE_URL=postgresql://nerve_app@/|TEST_DATABASE_URL=postgresql://nerve_app@/"
---

<objective>
<!-- revised via --reviews 2026-06-15: Gemini-Findings eingearbeitet — HIGH (set -o pipefail in beide pg_dump-Pipes), HIGH (Dump-Treue-Katalog-Check als harter Inline-deploy.sh-Schritt statt nur manueller SSH-One-Off), MEDIUM (ANON_PW via Env-Var an sudo + single-quoted inner bash -c statt String-Interpolation). -->
<!-- pre-execute audit fold 2026-06-15: A-1 DATABASE_URL (load-bearing) — pytest-Subshell exportiert DATABASE_URL=postgres, sonst registriert db.py den after_begin-RLS-Hook beim Import NICHT (sqlite-Default) -> False-Green. Plus MED(2) test_schild_guard PASSED-Assertion, MED(3) Ein-Deploy-Constraint. -->
Ersetze die kaputte SQLite-Test-Stufe in `deploy.sh` (Z.130-143) durch einen echten Postgres-Test-Gate-
Block: provisioniere die Wegwerf-DB `nerve_test` auf der Prod-Instanz (als `postgres`), baue ihr Schema
per **pg_dump-Restore vom Prod-`nerve`** (carries Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments) + Stamp-Row-
Dump (`alembic_version`) + `alembic upgrade head` (wendet NUR neue Revs über prod-head an, z.B. 0015→0016),
prüfe inline die Dump-Treue (crm-RLS-Policies/FORCE/GRANTs — fail-closed False-Green-Guard),
fahre pytest mit `DATABASE_URL` + 4 nerve_test-DSNs dagegen, und räume garantiert ab. Fail-closed pro Schritt,
`set -o pipefail` in den Dump-Pipes, Whitelist-Guard `nerve_test` (D-02).

**A-1 (load-bearing, pre-execute audit 2026-06-15):** Die pytest-Subshell MUSS `DATABASE_URL=postgresql://nerve_app@/nerve_test`
exportieren — NICHT nur `TEST_DATABASE_URL`. Grund: `database/db.py:9` defaultet `_DATABASE_URL` auf sqlite,
und der after_begin-RLS-Hook (`_set_tenant_txn_local`, db.py:87) wird zur IMPORT-ZEIT nur registriert wenn
`'sqlite' not in _DATABASE_URL` (db.py:86). Ohne gesetztes `DATABASE_URL` sieht db.py im pytest-Prozess den
sqlite-Default → Hook wird NIE registriert → Plan 01's `SessionLocal.configure(bind=engine)` rebindet zwar auf
PG, kann aber einen nie-registrierten Hook nicht auferstehen → `set_current_tenant` schreibt in einen contextvar,
den niemand liest → GUC bleibt NULL → generische crm-Reads liefern 0 Zeilen → Tests grün trotz kaputt (False-Green,
verletzt Req-4 Honesty + Req-7 fail-closed). `DATABASE_URL` ist nerve_app-peer-socket (PW-frei) → log-safe.

**WARUM pg_dump statt create_all+stamp+upgrade (empirisch verriegelt, RESEARCH „⚑ BUILD-PATH LOCKED"):**
Die ursprünglich geplante Sequenz `create_postgres_schema.py (create_all) → alembic stamp 0001 → upgrade head`
KOLLIDIERT bewiesen bei Migration 0002 (create_all baut das VOLLE aktuelle Modell inkl. `phrases.quality_tier`/
`users.is_test_user`; der `upgrade`-Replay von 0002's `add_column` hat kein `IF NOT EXISTS` → „column already
exists"). From-scratch `upgrade head` scheitert bei 0008 (0001 ist No-op-Marker → `public.users` existiert nie).
Der pg_dump-Pfad ist der EINZIGE, der kollisionsfrei baut UND die echten RLS/GRANTs treu trägt. Supervised
gegen einen Wegwerf-`nerve_test` bewiesen (André Punkt-22, danach geteardownt): 7 crm-RLS-Policies + ENABLE/
FORCE auf allen 5 crm-Tabellen + GRANTs alle vom Dump getragen; echter Cross-Tenant-Test (test_rls_isolation
+ test_anonymizer_worker) = **11 passed** (echte Isolation, nicht 0-Zeilen); `upgrade head` applizierte nur
0016 (`Running upgrade 0015 -> 0016`), keine 0002-Kollision; beide Rollen connecten (peer + scram).

**MED(3) Ein-Deploy-Constraint (pre-execute audit 2026-06-15):** Die Phase wird durch GENAU EINEN
`deploy.sh production`-Lauf validiert, NACHDEM Plan 01 + 02 + 03 zusammen committet sind. KEIN Zwischen-Deploy
nach Wave 1 — das Gate self-testet den deployten Baum, und ein Baum mit Wave-1-Gate aber OHNE Wave-2
(Listener-Entfernung + Klasse-A-Port) ist inkonsistent (test_08_14 würde „unknown database crm" werfen,
Plan-01-conftest-Refactor wäre noch nicht da). Der `<verify>`-deploy.sh-Lauf jedes Plans IST dieser eine
finale integrierte Gate-Lauf, kein Per-Plan-Deploy.

Purpose: Req-1 (pytest gegen echtes PG), Req-3 (Schema-End-Zustand = head + crm/training-Schemas + RLS,
via dump-restore + upgrade-only-neue-Revs — bewusste André-autorisierte Abweichung vom Wortlaut „via upgrade
head", siehe Acceptance-Rationale), Req-4 (RLS/Anon laufen — DSNs + DATABASE_URL gesetzt), Req-5 (alle DSNs → nerve_test),
Req-7 (fail-closed), Req-8 (Teardown), Req-9 (Prod + Schild-Guard grün). Output: umgebauter deploy.sh-Test-Block.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-CONTEXT.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md

<interfaces>
<!-- Verträge + Production-Fakten (RESEARCH, alle live bewiesen). Executor baut daraus, ohne zu raten. -->

deploy.sh IST-Stand (relevant):
- Z.99 `ssh ... bash -s << ENDHEREDOC` mit `set -e`; der gesamte Server-Block läuft als root.
- Z.130-143 = die zu ERSETZENDE SQLite-pytest-Stufe (`pytest tests/` ohne DSN → SQLite; PYTEST_EXIT-Check existiert).
- Z.145-156 = Schild-Guard-Stufe (`sudo -u nerve_app bash -c '... NERVE_SCHILD_TEST_DSN=postgresql://nerve_app@/nerve ...'`) → DSN auf nerve_test umlenken (Req-5/Req-9).
- Z.158-169 = .deploy_meta + systemctl restart — NACH dem Gate, NICHT brechen.

A-1-Vertrag (database/db.py — load-bearing, pre-execute audit 2026-06-15):
- db.py:9 `_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')` → Default sqlite.
- db.py:86 `if 'sqlite' not in _DATABASE_URL:` → db.py:87 `@event.listens_for(SessionLocal, "after_begin")`.
  Diese Entscheidung fällt EINMAL zur IMPORT-ZEIT. Ist `DATABASE_URL` im pytest-Prozess unset → sqlite-Default →
  Hook NIE registriert → set_current_tenant inert → crm-Reads 0 Zeilen → False-Green.
- FOLGE für das Gate: die pytest-Subshell MUSS `DATABASE_URL=postgresql://nerve_app@/nerve_test` setzen (gleicher
  Wert wie TEST_DATABASE_URL), damit db.py beim Import den Hook registriert. Cross-ref Plan 01 (hängt von diesem
  Hook ab — db_session/client binden das MODUL-SessionLocal um, was den Hook erhält aber nicht erzeugt).

Production-Fakten (RESEARCH, verbatim-belegt):
- postgres = super+createdb (CREATE/DROP DATABASE bewiesen). OWNER-Klausel MUSS `OWNER postgres` sein
  (NICHT nerve_app — sonst crm-Tabellen nerve_app-owned → RLS bypassed → False-Green, Migration 0012-Doku).
- pg_dump --schema-only MUSS owners+privileges tragen (NICHT --no-privileges, NICHT --no-owner) — sonst
  fallen RLS-Policies/FORCE/GRANTs weg → False-Green. Empirisch bewiesen: trägt alle 7 crm-Policies + FORCE + GRANTs.
- nerve_app: peer-socket, KEIN PW → DSN `postgresql://nerve_app@/nerve_test`. OS-User nerve_app existiert.
- nerve_anon_worker: KEIN OS-User → peer unmöglich → scram-host:
  `postgresql://nerve_anon_worker:<pw>@127.0.0.1:5432/nerve_test`; PW = `NERVE_ANON_WORKER_DB_PASSWORD`
  in `/etc/nerve/ionos-s3.env` (als root via sudo grep sourcen, VOR sudo -u nerve_app, nie loggen).
- Live HEAD = 0015 (Repo kann höher sein, z.B. 0016) → `alembic upgrade head` (NICHT hardcoden, D-09).
  Der Dump trägt die Stamp-Row 0015 → upgrade applied NUR neue Revs darüber (0016) → keine 0002-Kollision.
- Eine verwaiste leere `nerve_test`-DB existiert HEUTE auf Prod (owner postgres) → Pre-Run-DROP zwingend (D-06).
- scripts/create_postgres_schema.py: NICHT mehr Gate-Baustein (bleibt im Repo für den echten Cutover-Pfad).

Build-Pfad-Skelett (RESEARCH „⚑ BUILD-PATH LOCKED" — exakt so strukturiert übernehmen; pipefail + ANON_PW-Env + Inline-Katalog-Gate per Gemini-Review ergänzt; DATABASE_URL in der pytest-Subshell per pre-execute audit ergänzt):
```bash
TEST_DB="nerve_test"
if [ "$TEST_DB" != "nerve_test" ]; then echo "[deploy] FATAL: ... Prod-Schutz D-02"; exit 1; fi
cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" 2>/dev/null || true; }
trap cleanup EXIT
sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" || { echo FEHLER; exit 1; }
sudo -u postgres psql -c "CREATE DATABASE \"$TEST_DB\" OWNER postgres;" || { echo FEHLER; exit 1; }
# Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments vom Prod-nerve übertragen (read-only auf nerve):
# set -o pipefail: ohne das maskiert ein psql-Exit-0 einen pg_dump-Crash → leere DB → silent False-Green.
sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" || { echo FEHLER; exit 1; }
# Stamp-Row (= prod-head) übertragen, damit upgrade nur neue Revs anwendet:
sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d $TEST_DB" || { echo FEHLER; exit 1; }
sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" || { echo FEHLER; exit 1; }
# --- INLINE DUMP-TREUE-KATALOG-GATE (fail-closed False-Green-Guard, NACH upgrade, VOR pytest) ---
POLICIES=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "$TEST_DB")
[ "$POLICIES" -ge 7 ] || { echo "[deploy] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz greift)"; exit 1; }
FORCED=$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "$TEST_DB")
[ "$FORCED" -ge 5 ] || { echo "[deploy] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
GRANTS=$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "$TEST_DB")
[ "$GRANTS" -ge 5 ] || { echo "[deploy] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
# --- pytest: ANON_PW via Env an sudo, single-quoted inner bash -c (keine String-Interpolation des PW) ---
# A-1: DATABASE_URL gesetzt (gleicher PG-Wert wie TEST_DATABASE_URL) -> db.py registriert beim Import den after_begin-RLS-Hook.
ANON_PW=$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)
sudo -u nerve_app ANON_PW="$ANON_PW" TEST_DB="$TEST_DB" bash -c '
  cd /opt/nerve/app && \
  DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  TEST_DATABASE_URL="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_APP_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/${TEST_DB}" \
  ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:${ANON_PW}@127.0.0.1:5432/${TEST_DB}" \
  /opt/nerve/venv/bin/pytest tests/ --tb=short -q
' || { echo "[deploy] FEHLER: pytest gegen nerve_test ROT -- kein Restart, kein Deploy"; exit 1; }
# --- POST-SUITE crm-BASELINE-CHECK (HYBRID, André locked; NACH pytest, VOR trap-Teardown; SCHILD-sudo-postgres-Muster) ---
# Plan 01's in-pytest-Waechter prueft NUR public.* (nerve_app tenant-gefiltert auf crm.*). crm.*-Baseline = 0 Rows
# pro Tabelle (kein app-import-Seeder beruehrt crm.*). Als postgres (peer, passwordless) bypassed psql FORCE-RLS ->
# sieht crm.* ALLER Tenants -> faengt Cross-Tenant-Leaks. KEINE neue Env-Var, KEIN PW.
CRM_LEFTOVER=$(sudo -u postgres psql -tAc "SELECT coalesce(sum(c),0) FROM (SELECT count(*) c FROM crm.account_memory UNION ALL SELECT count(*) FROM crm.accounts UNION ALL SELECT count(*) FROM crm.contacts UNION ALL SELECT count(*) FROM crm.meetings UNION ALL SELECT count(*) FROM crm.user_preferences) s" -d "$TEST_DB")
[ "$CRM_LEFTOVER" = "0" ] || { echo "[deploy] FEHLER: crm.* nicht leer nach Test-Lauf ($CRM_LEFTOVER Leak-Rows) -- Security-Test-Teardown liess Daten liegen (Cross-Tenant-Leak ODER fehlendes cleanup_rows)"; exit 1; }
echo "[deploy] POST-SUITE crm-Baseline-Check OK: alle crm.* Tabellen leer (0 Leak-Rows)"
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: SQLite-Test-Stufe durch Postgres-Gate-Block ersetzen (Provision → pg_dump-Restore-Build → inline-Katalog-Treue-Gate → pytest DATABASE_URL+4-DSN → Teardown)</name>
  <read_first>
    - deploy.sh Z.99-156 (IST: heredoc set -e, SQLite-pytest-Stufe Z.130-143, Schild-Guard Z.145-156)
    - database/db.py Z.9 (DATABASE_URL-Default sqlite) + Z.86-103 (after_begin-Hook NUR wenn 'sqlite' not in _DATABASE_URL — der A-1-Grund warum DATABASE_URL=postgres in der pytest-Subshell stehen MUSS)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md „⚑ BUILD-PATH LOCKED" (der bewiesene pg_dump-Pfad — SUPERSEDET Q3), Q1 (DSN-Formen + OWNER postgres + pg_dump-Read-Rechte), Q2c (4-DSN-Mapping)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q3 (NUR als Begründung WARUM nicht bare upgrade head / nicht create_all — historischer Kontext)
  </read_first>
  <behavior>
    - Innerhalb des ENDHEREDOC-Blocks (läuft als root, set -e aktiv): die SQLite-pytest-Stufe (Z.130-143) wird ersetzt durch den Gate-Block.
    - Whitelist-Guard: TEST_DB ≠ "nerve_test" → sofort exit 1 mit Prod-Schutz-Grund (D-02).
    - trap cleanup EXIT registriert DROP DATABASE IF EXISTS nerve_test (garantiert auch bei pytest-Fehler/SIGTERM, D-06).
    - Pre-Run-DROP der verwaisten nerve_test, dann CREATE OWNER postgres.
    - Schema-Build als postgres: `set -o pipefail; pg_dump --schema-only nerve | psql nerve_test`; dann `set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql nerve_test`; dann alembic upgrade head. Jeder Schritt eigener Exit-Check + Klartext-Grund (D-07). KEIN create_postgres_schema.py, KEIN stamp 0001 (würde bei 0002 kollidieren).
    - **Inline-Dump-Treue-Katalog-Gate (Gemini-HIGH, NACH upgrade, VOR pytest):** harte fail-closed psql-Counts — crm-RLS-Policies ≥7, FORCE auf ≥5 crm-Tabellen, nerve_anon_worker-SELECT-GRANTs ≥5. Jede Assertion `|| exit 1` mit Klartext-Grund. Das ist der automatisierte False-Green-Guard bei JEDEM Deploy (nicht nur ein manueller One-Off-SSH-Build).
    - pytest als nerve_app mit **DATABASE_URL + 4 DSNs**; **A-1 (pre-execute audit):** `DATABASE_URL=postgresql://nerve_app@/${TEST_DB}` wird ZUSÄTZLICH zu den 4 Test-DSNs in der Subshell gesetzt — sonst registriert db.py beim Import den after_begin-RLS-Hook NICHT (db.py:86 sieht den sqlite-Default) und set_current_tenant bleibt inert → crm-Reads 0 Zeilen → False-Green. ANON_PW + TEST_DB werden als ENV an `sudo -u nerve_app` übergeben, der innere `bash -c` ist SINGLE-quoted und expandiert `${ANON_PW}`/`${TEST_DB}` aus der Prozess-Env (KEINE String-Interpolation des PW in die Befehlszeile — Gemini-MEDIUM). ANON_PW vorab als root aus ionos-s3.env, nie geloggt. DATABASE_URL ist nerve_app-peer-socket (PW-frei) → log-safe, darf geechot werden.
    - **POST-SUITE-crm-Baseline-Check (HYBRID, André locked; NACH dem pytest-Lauf, VOR dem trap-Teardown):** ein
      `sudo -u postgres psql -d "\$TEST_DB"` Schritt (peer-auth, passwordless — EXAKT das SCHILD-Guard-sudo-postgres-
      Muster, KEINE neue Env-Var, KEIN PW) summiert `SELECT count(*)` ueber alle 5 crm.* Tabellen (account_memory,
      accounts, contacts, meetings, user_preferences) und assertet == 0. Plan 01's in-pytest-Waechter prueft NUR
      public.* (nerve_app saehe crm.* nur tenant-gefiltert); als postgres bypassed psql FORCE-RLS → sieht crm.* ALLER
      Tenants → faengt Cross-Tenant-Leaks. Leak (>0) → exit 1, kein Restart/Deploy (fail-closed). crm.*-Baseline = 0
      (kein app-import-Seeder beruehrt crm.*); jeder crm-Writer raeumt im Teardown via cleanup_rows auf 0 zurueck.
    - Jeder Schritt fail-closed (exit 1), kein || -Zweig der auf SQLite/Prod ausweicht.
  </behavior>
  <action>
    Ersetze in deploy.sh die SQLite-pytest-Stufe (Z.130-143, inkl. des Kommentars Z.131-134 der den
    conftest-Refactor als Folge-Phase nennt — der ist jetzt erledigt) durch den folgenden Block. Baue ihn
    nach dem „⚑ BUILD-PATH LOCKED"-Skelett (interfaces oben), heredoc-konform (im `<< ENDHEREDOC` werden
    lokale `$` escaped wie heute `\$PYTEST_EXIT` — beachte: TEST_DB/ANON_PW/POLICIES/FORCED/GRANTS sind
    SERVER-seitige Vars, also `\$` escapen wo sie erst auf dem Server expandieren sollen):

    1. `TEST_DB="nerve_test"` + Whitelist-Guard:
       `if [ "\$TEST_DB" != "nerve_test" ]; then echo "[deploy] FATAL: Test-DB-Name != nerve_test — Abbruch (Prod-Schutz D-02)"; exit 1; fi`
    2. `cleanup() { sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" 2>/dev/null || true; }` + `trap cleanup EXIT`
    3. Pre-Run-DROP: `sudo -u postgres psql -c "DROP DATABASE IF EXISTS \"\$TEST_DB\";" || { echo "[deploy] FEHLER: Pre-Run-DROP nerve_test fehlgeschlagen"; exit 1; }`
    4. CREATE: `sudo -u postgres psql -c "CREATE DATABASE \"\$TEST_DB\" OWNER postgres;" || { echo "[deploy] FEHLER: CREATE DATABASE nerve_test fehlgeschlagen"; exit 1; }`
    5. **Schema-Dump** (Schema+RLS+FORCE+GRANTs+FK+CHECK+Comments vom Prod-nerve, read-only auf nerve) — MIT `set -o pipefail`:
       `sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: pg_dump --schema-only nerve → nerve_test fehlgeschlagen"; exit 1; }`
       WICHTIG: `set -o pipefail` ist Pflicht (Gemini-HIGH) — sonst maskiert ein psql-Exit-0 einen pg_dump-Crash → leere/teilweise DB → silent False-Green. KEIN `--no-privileges`, KEIN `--no-owner` — die GRANTs/Owner tragen die RLS-Treue (False-Green-Schutz).
    6. **Stamp-Row-Dump** (carry die alembic_version-Row = prod-head, damit upgrade nur neue Revs anwendet) — MIT `set -o pipefail`:
       `sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d \$TEST_DB" || { echo "[deploy] FEHLER: alembic_version-Stamp-Dump → nerve_test fehlgeschlagen"; exit 1; }`
    7. **upgrade**: `sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/\$TEST_DB /opt/nerve/venv/bin/alembic upgrade head" || { echo "[deploy] FEHLER: alembic upgrade head gegen nerve_test fehlgeschlagen"; exit 1; }`  (NICHT hardcoden — `head`, D-09; wendet nur Revs über prod-head an, z.B. 0015→0016 — keine 0002-Kollision).
    8. **Inline-Dump-Treue-Katalog-Gate (Gemini-HIGH — automatisierter False-Green-Guard, NACH upgrade, VOR pytest):**
       ```
       POLICIES=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_policies WHERE schemaname='crm';" -d "\$TEST_DB")
       [ "\$POLICIES" -ge 7 ] || { echo "[deploy] FEHLER: crm-RLS-Policies < 7 (Dump trug RLS nicht treu -> False-Green-Schutz greift)"; exit 1; }
       FORCED=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='crm') AND relkind='r' AND relforcerowsecurity;" -d "\$TEST_DB")
       [ "\$FORCED" -ge 5 ] || { echo "[deploy] FEHLER: crm FORCE ROW LEVEL SECURITY nicht auf allen 5 Tabellen"; exit 1; }
       GRANTS=\$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.role_table_grants WHERE table_schema='crm' AND grantee='nerve_anon_worker' AND privilege_type='SELECT';" -d "\$TEST_DB")
       [ "\$GRANTS" -ge 5 ] || { echo "[deploy] FEHLER: nerve_anon_worker SELECT-GRANTs auf crm.* fehlen (Dump-Treue)"; exit 1; }
       echo "[deploy] Dump-Treue-Katalog-Gate OK: crm-Policies=\$POLICIES, FORCE=\$FORCED, anon-SELECT-GRANTs=\$GRANTS"
       ```
       Falls eine Assertion fehlschlägt → exit 1, KEIN Restart, KEIN Deploy (der Dump trug RLS/FORCE/GRANTs nicht treu → False-Green-Gefahr). Diese drei Counts sind die automatisierte Dump-Treue-Garantie pro Deploy.
    9. ANON_PW + pytest — Env-Übergabe statt String-Interpolation (Gemini-MEDIUM), **DATABASE_URL gesetzt (A-1, pre-execute audit)**:
       `ANON_PW=\$(sudo grep ^NERVE_ANON_WORKER_DB_PASSWORD= /etc/nerve/ionos-s3.env | cut -d= -f2-)` — danach NIE in echo/set -x sichtbar machen.
       ```
       sudo -u nerve_app ANON_PW="\$ANON_PW" TEST_DB="\$TEST_DB" bash -c '
         cd /opt/nerve/app && \
         DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
         TEST_DATABASE_URL="postgresql://nerve_app@/\${TEST_DB}" \
         NERVE_APP_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
         NERVE_SCHILD_TEST_DSN="postgresql://nerve_app@/\${TEST_DB}" \
         ANON_WORKER_TEST_DSN="postgresql://nerve_anon_worker:\${ANON_PW}@127.0.0.1:5432/\${TEST_DB}" \
         /opt/nerve/venv/bin/pytest tests/ --tb=short -q
       ' || { echo "[deploy] FEHLER: pytest gegen nerve_test ROT — kein Restart, kein Deploy"; exit 1; }
       ```
       **A-1 (load-bearing):** `DATABASE_URL` MUSS in der Subshell stehen — auf denselben PG-Wert wie TEST_DATABASE_URL.
       Sonst sieht `database/db.py:9` im pytest-Prozess den sqlite-Default → der after_begin-RLS-Hook (db.py:87)
       wird beim Import NICHT registriert (db.py:86 `if 'sqlite' not in _DATABASE_URL`) → set_current_tenant inert →
       generische crm-Reads 0 Zeilen → Tests grün trotz kaputt (False-Green). DATABASE_URL ist nerve_app-peer-socket
       (PW-frei) → log-safe.
       Der innere `bash -c`-Block ist SINGLE-quoted: `${ANON_PW}`/`${TEST_DB}` expandieren aus der
       nerve_app-Prozess-Env — bullet-proof gegen `"`, Backtick, `$` im PW; das PW landet NIE als
       String-Literal in der Befehlszeile. (Beachte heredoc-Escaping: damit `${ANON_PW}` erst auf dem Server
       in der single-quoted Subshell expandiert, im `<< ENDHEREDOC` als `\${ANON_PW}` schreiben.)
       Log-Echo der DSN (Req-1-Acceptance: Beleg dass postgresql://…/nerve_test lief, inkl. DATABASE_URL) — aber NUR die
       nerve_app-DSNs echoen, NIE die anon_worker-DSN (enthält PW). Z.B.
       `echo "[deploy] pytest gegen DATABASE_URL=postgresql://nerve_app@/\$TEST_DB (+ 4 Test-DSNs)"`.
    10. **POST-SUITE-crm-Baseline-Check (HYBRID, André locked — NACH dem pytest-Schritt 9, VOR dem trap-Teardown):**
       Plan 01's in-pytest `_baseline_cleanup_guard` prueft NUR public.* (nerve_app liest crm.* nur tenant-gefiltert).
       crm.* wird hier POST-SUITE geprueft — als postgres (peer, passwordless, SCHILD-Muster) RLS-bypassed ueber alle
       Tenants. crm.*-Baseline = 0 Rows pro Tabelle (kein app-import-Seeder beruehrt crm.*). heredoc-escape `\$` wo
       server-seitig expandiert:
       ```
       CRM_LEFTOVER=\$(sudo -u postgres psql -tAc "SELECT coalesce(sum(c),0) FROM (SELECT count(*) c FROM crm.account_memory UNION ALL SELECT count(*) FROM crm.accounts UNION ALL SELECT count(*) FROM crm.contacts UNION ALL SELECT count(*) FROM crm.meetings UNION ALL SELECT count(*) FROM crm.user_preferences) s" -d "\$TEST_DB")
       [ "\$CRM_LEFTOVER" = "0" ] || { echo "[deploy] FEHLER: crm.* nicht leer nach Test-Lauf (\$CRM_LEFTOVER Leak-Rows) -- Security-Test-Teardown liess Daten liegen (Cross-Tenant-Leak ODER fehlendes cleanup_rows)"; exit 1; }
       echo "[deploy] POST-SUITE crm-Baseline-Check OK: alle crm.* Tabellen leer (0 Leak-Rows)"
       ```
       KEINE neue Env-Var, KEIN NERVE_BASELINE_GUARD_DSN, KEIN PW — `sudo -u postgres` peer-auth (der heredoc-Block
       laeuft als root → peer gelingt), dieselbe Mechanik wie CREATE/DROP/Schema-Dump. Leak (>0) → exit 1, kein
       Restart. Dieser Schritt deckt die crm.*-Seite der Baseline-Sauberkeit ab, die Plan 01's in-pytest-Waechter
       (public.*-only) NICHT abdeckt (cross-ref Plan 01 Task 6).

    KEIN Code-Zweig der bei Fehler auf SQLite/Prod ausweicht (Req-7). `set -e` bleibt, aber jeder Schritt
    hat zusätzlich seinen expliziten `|| { echo FEHLER; exit 1; }` (D-07: Klartext-Grund pro Schritt).
    KEIN `scripts/create_postgres_schema.py`, KEIN `alembic stamp 0001` im Gate — beide würden kollidieren
    (RESEARCH „⚑ BUILD-PATH LOCKED"). Die create_all-Build-Ordering-Frage (A1/Q3d) ist damit GEGENSTANDSLOS.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy.log; grep -E "pytest gegen DATABASE_URL=postgresql://nerve_app@/nerve_test|set -o pipefail; pg_dump --schema-only nerve|Dump-Treue-Katalog-Gate OK|Running upgrade 0015 -> 0016|upgrade head" /tmp/pgtest_deploy.log; echo "EXIT=$?"  # Req-1/Req-3/A-1-Beleg: Gate lief gegen nerve_test mit DATABASE_URL=postgres (RLS-Hook registriert), baute via pg_dump-Restore (pipefail), inline-Katalog-Gate grün, upgrade applied nur neue Revs (kein "already exists").</automated>
  </verify>
  <done>
    deploy.sh enthält den Postgres-Gate-Block: Whitelist-Guard + trap cleanup EXIT + Pre-Run-DROP + CREATE
    OWNER postgres + `set -o pipefail; pg_dump --schema-only nerve→nerve_test` + `set -o pipefail`-alembic_version-Stamp-Dump
    + alembic upgrade head + **inline-Dump-Treue-Katalog-Gate (crm-Policies≥7 + FORCE≥5 + anon-SELECT-GRANTs≥5, fail-closed)**
    + pytest mit **DATABASE_URL (A-1) + 4 nerve_test-DSNs** (ANON_PW via Env an sudo, single-quoted inner bash -c)
    + **POST-SUITE-crm-Baseline-Check** (`sudo -u postgres psql`, crm.* == 0 Rows, fail-closed; NACH pytest, VOR trap), jeder Schritt fail-closed
    mit Klartext-Grund. **crm-Acceptance (HYBRID):** das Deploy-Log zeigt `POST-SUITE crm-Baseline-Check OK: alle crm.* Tabellen leer (0 Leak-Rows)`;
    bei einem Leak (>0) bricht der Deploy mit `crm.* nicht leer nach Test-Lauf`-Grund (exit≠0, kein Restart). **A-1-Acceptance:** das Deploy-Log zeigt `DATABASE_URL=postgresql://nerve_app@/nerve_test` in der
    pytest-Env (PW-frei, log-safe) — damit db.py beim Import den after_begin-RLS-Hook registriert; ein generischer
    crm-Read unter set_current_tenant liefert ≥1 Zeile (Plan 01's Tripwire), NICHT 0. Deploy-Log belegt zusätzlich
    `set -o pipefail; pg_dump --schema-only nerve` piped in nerve_test (NICHT create_all), `Dump-Treue-Katalog-Gate OK`,
    und `Running upgrade 0015 -> 0016` (kein „already exists"-Fehler). anon_worker-PW nirgendwo geloggt:
    `grep -i "nerve_anon_worker:" /tmp/pgtest_deploy.log` zeigt KEIN Klartext-PW (Env-Übergabe, nicht interpoliert).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Inline-Dump-Treue-Gate dokumentieren/verifizieren (manueller SSH-Build als Pre-Execute-Zusatzbeleg) + Schild-Guard-DSN auf nerve_test umlenken (Req-9) + test_schild_guard PASSED-Assertion (MED-2)</name>
  <read_first>
    - deploy.sh Z.145-156 (Schild-Guard-Stufe — DSN `@/nerve` → `@/nerve_test`)
    - deploy.sh Task-1-Inline-Katalog-Gate (die harten Counts POLICIES/FORCED/GRANTS — DIESE sind der automatisierte Guard, hier nur dokumentiert/verifiziert)
    - tests/test_schild_guard.py (SKIP-Bedingung: skippt wenn NERVE_SCHILD_TEST_DSN fehlt/sqlite — MED-2: im Gate MUSS er PASSED erscheinen, nicht SKIPPED, sobald DSN auf nerve_test zeigt)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md „⚑ BUILD-PATH LOCKED" (die bewiesenen Katalog-Werte: 7 Policies, FORCE auf 5 Tabellen, GRANTs, alembic_version=0016) + Assumption A3 (Schild-Guard-Aussagekraft gegen frische DB)
  </read_first>
  <behavior>
    - Die automatisierte Dump-Treue-Garantie ist das INLINE-Katalog-Gate in Task 1 (läuft bei JEDEM Deploy, fail-closed). Diese Task ist die DOKUMENTATION + ein zusätzlicher manueller SSH-Build-Beweis VOR Execute (verbatim-Katalog-Output ins SUMMARY) — NICHT der einzige Fidelity-Check (Gemini-HIGH: der einzige Check darf nicht manuell sein).
    - Schild-Guard: läuft gegen nerve_test (nicht Prod-nerve), bleibt grün, behält Aussagekraft (head-Schilder in nerve_test vorhanden, da Schema vom Prod-nerve gedumpt + auf head migriert).
    - **MED-2 (pre-execute audit):** `test_schild_guard.py` MUSS im Haupt-pytest-Lauf des Gates (mit NERVE_SCHILD_TEST_DSN → nerve_test) als PASSED erscheinen — NICHT SKIPPED, NICHT error. (Der Test skippt lokal/sqlite by design; im Gate mit gesetztem nerve_test-DSN läuft er scharf.)
  </behavior>
  <action>
    1. **Inline-Gate ist der automatisierte Guard (Task 1) — diese Task dokumentiert + liefert Zusatzbeleg:**
       Der harte fail-closed Katalog-Check (POLICIES≥7 / FORCED≥5 / GRANTS≥5) läuft bei jedem Deploy IN
       deploy.sh (Task 1, Schritt 8). Zusätzlich (Pre-Execute-Proof, NICHT der einzige Check): ein gezielter
       manueller Build gegen einen Wegwerf-`nerve_test` + verbose Katalog-Query, um die verbatim-Outputs ins
       SUMMARY zu schreiben — server-side als postgres:
       ```
       ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'sudo -u postgres psql -c "DROP DATABASE IF EXISTS nerve_test;" && \
         sudo -u postgres psql -c "CREATE DATABASE nerve_test OWNER postgres;" && \
         sudo -u postgres bash -c "set -o pipefail; pg_dump --schema-only nerve | psql -v ON_ERROR_STOP=1 -d nerve_test" && \
         sudo -u postgres bash -c "set -o pipefail; pg_dump --data-only --table=alembic_version nerve | psql -v ON_ERROR_STOP=1 -d nerve_test" && \
         sudo -u postgres bash -c "cd /opt/nerve/app && DATABASE_URL=postgresql://postgres@/nerve_test /opt/nerve/venv/bin/alembic upgrade head" && \
         sudo -u postgres psql -d nerve_test -c "\dn" && \
         sudo -u postgres psql -d nerve_test -c "SELECT version_num FROM alembic_version;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT count(*) FROM pg_policies WHERE schemaname=\$\$crm\$\$;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT relname, relforcerowsecurity FROM pg_class WHERE relnamespace=(SELECT oid FROM pg_namespace WHERE nspname=\$\$crm\$\$) AND relkind=\$\$r\$\$;" && \
         sudo -u postgres psql -d nerve_test -c "SELECT grantee, table_name, privilege_type FROM information_schema.role_table_grants WHERE table_schema=\$\$crm\$\$ AND grantee IN (\$\$nerve_app\$\$,\$\$nerve_anon_worker\$\$) ORDER BY grantee, table_name;" && \
         sudo -u postgres psql -c "DROP DATABASE nerve_test;"'
       ```
       ERWARTUNG (RESEARCH „⚑ BUILD-PATH LOCKED", bewiesen):
       - `\dn` zeigt crm + training (+ public).
       - `alembic_version` = Repo-HEAD (heute 0016).
       - `pg_policies` schemaname='crm' → **≥7 Zeilen** (account_memory ×3, accounts/contacts/meetings/user_preferences tenant_isolation).
       - `relforcerowsecurity=t` auf **allen 5 crm-Tabellen**.
       - `role_table_grants`: nerve_app = INSERT/SELECT/UPDATE/DELETE auf crm.*; nerve_anon_worker = SELECT auf crm.*.
       Diese drei Katalog-Werte sind der False-Green-Guard — IM Deploy automatisiert (Task 1, Schritt 8), hier
       zusätzlich verbatim dokumentiert. Dokumentiere die Outputs im SUMMARY.
       FALLS eine Assertion fehlschlägt (z.B. 0 crm-Policies → Dump trug RLS nicht): STOP + Eskalation
       (pg_dump-Flags prüfen: --no-privileges/--no-owner versehentlich gesetzt?) — NICHT weiterbauen.
    2. **Schild-Guard-DSN umlenken (Req-9/Req-5):** In deploy.sh Z.151 ändere
       `NERVE_SCHILD_TEST_DSN=postgresql://nerve_app@/nerve` → `...@/nerve_test`. Da die Schild-Guard-Stufe
       NACH dem Gate-Block läuft, nerve_test aber vom trap am EXIT gedroppt wird: ziehe den Schild-Guard IN
       den Gate-Block (der Haupt-`pytest tests/`-Lauf in der nerve_app-Gate-Subshell deckt test_schild_guard.py
       bereits ab, da NERVE_SCHILD_TEST_DSN dort gesetzt ist).
       → die separate Z.145-156-Stufe wird damit redundant; ersetze sie durch einen Hinweis-Kommentar, dass
       der Schild-Guard jetzt im Postgres-Gate gegen nerve_test mitläuft. Verifiziere A3: der dump-gebaute
       nerve_test trägt die head-Schilder (pg_description vom Prod-nerve mitgedumpt) → Schild-Guard grün.
    3. **MED-2 — test_schild_guard PASSED-Assertion:** Verifiziere im Gate-Lauf-Log explizit, dass
       `test_schild_guard.py` als **PASSED** erscheint (NICHT SKIPPED, NICHT error) — der Beweis, dass
       NERVE_SCHILD_TEST_DSN tatsächlich auf nerve_test zeigt und der Guard scharf gegen das dump-gebaute
       Schema lief. Im SUMMARY den `test_schild_guard ... PASSED`-Eintrag aus dem `-v`/`-q`-Output zitieren.
       (Der Test skippt lokal/sqlite by design — im Gate mit gesetztem nerve_test-DSN MUSS er laufen.)
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "NERVE_SCHILD_TEST_DSN" deploy.sh'; echo "---"; bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy2.log | grep -E "test_schild_guard.*PASSED|test_schild_guard.*passed|Dump-Treue-Katalog-Gate OK|alembic_version|crm|nerve_test|relforcerowsecurity|nerve_anon_worker"; echo "EXIT=$?"  # Schild-Guard gegen nerve_test PASSED (nicht SKIPPED, MED-2); inline-Katalog-Gate OK (crm-Policies≥7 + FORCE + GRANTs).</automated>
  </verify>
  <done>
    Inline-Dump-Treue-Gate (Task 1) ist der automatisierte fail-closed Guard pro Deploy; zusätzlich verbatim-
    Katalog-Output im SUMMARY dokumentiert: `pg_policies` crm ≥7, `relforcerowsecurity=t` auf allen 5 crm-Tabellen,
    `role_table_grants` nerve_app=DML + nerve_anon_worker=SELECT, `alembic_version`=Repo-HEAD, `\dn` zeigt crm+training
    (Req-3 End-Zustand). Schild-Guard läuft im Gate gegen nerve_test (kein `@/nerve` ohne `_test` mehr in deploy.sh)
    und ist grün (Req-9). **MED-2:** `test_schild_guard.py` erscheint im Gate-Log als PASSED (NICHT SKIPPED, NICHT error) —
    Beweis dass NERVE_SCHILD_TEST_DSN auf nerve_test zeigt und der Guard scharf lief; der PASSED-Eintrag ist im SUMMARY zitiert.
    Voller deploy.sh production endet grün; Prod-`nerve` unverändert (kein Test-DSN/CREATE/DROP
    zeigt drauf; pg_dump war read-only).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| deploy.sh (root) → postgres-Rolle | CREATE/DROP DATABASE auf der Prod-Instanz — ein falscher Name = Prod-Verlust |
| deploy.sh → Prod-nerve (pg_dump) | pg_dump liest die Prod-DB read-only — darf nie schreiben/droppen auf nerve |
| deploy.sh → ionos-s3.env | anon_worker-PW-Secret quert in die Gate-Subshell-Env |
| Gate-pytest → nerve_test | alle 4 DSNs + DATABASE_URL müssen nerve_test treffen, nie Prod-nerve |
| POST-SUITE-Check → crm.* (FORCE-RLS) | `sudo -u postgres psql` (peer, RLS-bypassed) liest crm.* aller Tenants → assertet == 0; faengt Cross-Tenant-Leaks die der public.*-only-in-pytest-Waechter (Plan 01) nicht sieht |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-05 | Tampering/Denial | `DROP DATABASE` Tippfehler trifft Prod-`nerve` | mitigate | D-02 Whitelist-Guard `[ "$TEST_DB" != "nerve_test" ] && exit 1` VOR jedem CREATE/DROP; TEST_DB ist EINZIGE Quelle des Namens; grep-verifiziert |
| T-PGTEST-06 | Information Disclosure | anon_worker-PW landet im Deploy-Log ODER bricht den Parser bei Sonderzeichen | mitigate | Gemini-MEDIUM: ANON_PW + TEST_DB via `sudo -u nerve_app ANON_PW="\$ANON_PW" TEST_DB="\$TEST_DB" bash -c '...'` als ENV übergeben; innerer `bash -c` SINGLE-quoted, expandiert `${ANON_PW}` aus der Prozess-Env → KEINE String-Interpolation (bullet-proof gegen `"`/Backtick/`$` im PW), PW nie als String-Literal in der Befehlszeile; nur nerve_app-DSNs (PW-frei) + DATABASE_URL (PW-frei) werden geloggt; Code-Review-grep nach Klartext-PW im Log |
| T-PGTEST-07 | Tampering | Test-DSN zeigt auf Prod-`nerve` → Test mutiert Prod | mitigate | alle 4 DSNs + DATABASE_URL hartkodiert auf `\$TEST_DB`=nerve_test (Req-5); Schild-Guard-DSN auf nerve_test umgelenkt; pg_dump auf nerve ist read-only |
| T-PGTEST-08 | Denial/Spoofing | Gate skippt still bei nicht-provisionierbarer DB ODER pg_dump-Crash wird durch psql-Exit-0 maskiert → False-Green-Deploy | mitigate | D-07 fail-closed pro Schritt (exit 1 + Klartext-Grund); `set -o pipefail` in BEIDEN pg_dump-Pipes (Gemini-HIGH — ein pg_dump-Crash propagiert jetzt als Pipeline-Exit≠0, statt durch psql-Exit-0 maskiert zu werden); `psql -v ON_ERROR_STOP=1` bei beiden Dump-Restores; KEIN SQLite/Prod-Ausweich-Zweig; trap droppt nerve_test |
| T-PGTEST-09 | Tampering | nerve_test OWNER nerve_app ODER --no-privileges-Dump → crm-Tabellen owner-bypassen RLS / RLS-Policies fehlen (False-Green) | mitigate | CREATE DATABASE ... OWNER postgres (RESEARCH Q1e/0012-Doku); pg_dump --schema-only MIT owners+privileges (NICHT --no-privileges/--no-owner). **AUTOMATISIERTER GUARD (Gemini-HIGH):** Inline-Dump-Treue-Katalog-Gate in deploy.sh (Task 1, NACH upgrade, VOR pytest) — harte fail-closed Counts crm-RLS-Policies ≥7, FORCE auf ≥5 crm-Tabellen, nerve_anon_worker-SELECT-GRANTs ≥5; bei Drift exit 1 (kein Restart). **EMPIRISCH BEWIESEN (RESEARCH „⚑ BUILD-PATH LOCKED"):** der Dump trug alle 7 crm-RLS-Policies + ENABLE/FORCE auf allen 5 crm-Tabellen + GRANTs; der echte Cross-Tenant-Test test_tenant_a_cannot_read_tenant_b_account_memory PASSED gegen das dump-gebaute nerve_test (11 passed gesamt) = genuine Isolation, NICHT 0-Zeilen-False-Green. Task-2 dokumentiert die Katalog-Werte verbatim als Pre-Execute-Zusatzbeleg. |
| T-PGTEST-10 | Denial | verwaiste nerve_test (existiert HEUTE) blockiert CREATE | mitigate | D-06 Pre-Run-DROP IF EXISTS vor CREATE; trap cleanup EXIT für Lauf-Ende |
| T-PGTEST-15 | Tampering | upgrade head replayt 0002 gegen schon-vorhandene Spalte → „column already exists" → Gate bricht / falsch grün | mitigate | Stamp-Row-Dump (`pg_dump --data-only --table=alembic_version`) trägt prod-head 0015 → upgrade applied NUR neue Revs (0016); empirisch `Running upgrade 0015 -> 0016`, keine 0002-Kollision (RESEARCH „⚑ BUILD-PATH LOCKED"). create_all+stamp 0001 explizit verworfen. |
| T-PGTEST-29 | Information Disclosure | Ein crm-Writer (Security-Test/A-1-Tripwire/geporteter crm-Test) laesst eine crm.*-Row liegen (fehlendes/falsches cleanup_rows ODER ein echter Cross-Tenant-Leak) → Plan 01's in-pytest-Waechter sieht es NICHT (public.*-only; nerve_app saehe crm.* nur tenant-gefiltert) → False-Green | mitigate | HYBRID (André locked 2026-06-15, Option 1): POST-SUITE-crm-Baseline-Check in deploy.sh (NACH pytest, VOR trap) via `sudo -u postgres psql -d "$TEST_DB"` (peer-auth, passwordless, EXAKT das SCHILD-Guard-sudo-postgres-Muster) summiert count(*) ueber alle 5 crm.* Tabellen und assertet == 0; als postgres RLS-bypassed → sieht crm.* ALLER Tenants → faengt Cross-Tenant-Leaks. Leak (>0) → exit 1, kein Restart/Deploy. KEINE neue Env-Var, KEIN NERVE_BASELINE_GUARD_DSN, KEIN Superuser-PW im Test-Env (dieselbe peer-postgres-Mechanik wie CREATE/DROP/Schema-Dump). crm.*-Baseline = 0 (kein app-import-Seeder beruehrt crm.*); ~4 crm-Writer raeumen via cleanup_rows auf 0. Cross-ref Plan 01 Task 6 (public.*-only-Waechter). |
| T-PGTEST-18 | Spoofing/Information Disclosure | DATABASE_URL unset in der pytest-Subshell → db.py:9 picked den sqlite-Default beim Import → der after_begin-RLS-Hook (db.py:87) wird NIE registriert (db.py:86 `if 'sqlite' not in _DATABASE_URL`) → set_current_tenant inert → generische crm-Reads liefern 0 Zeilen, Tests passen STILL (False-Green; verletzt Req-4 Honesty + Req-7 fail-closed) | mitigate | pre-execute audit 2026-06-15 (A-1): die pytest-Subshell exportiert EXPLIZIT `DATABASE_URL=postgresql://nerve_app@/\$TEST_DB` (gleicher PG-Wert wie TEST_DATABASE_URL), sodass db.py beim Import `'sqlite' not in _DATABASE_URL` als TRUE wertet und den Hook registriert. DATABASE_URL ist nerve_app-peer-socket (PW-frei) → log-safe, wird geechot (Acceptance-Beleg). Plan 01 fügt einen direkten Tripwire hinzu (current_setting('app.tenant_id') NON-null + crm-Read ≥1 Zeile auf dem generischen db_session-Pfad), der diesen Defekt von silent-green auf loud-red dreht. Cross-ref Plan 01 hook-dependency. |

</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen / Schemas

Dieser Plan BAUT das gesamte nerve_test-Schema (alle public.* + crm.* + training.*) per pg_dump-Restore
vom Prod-`nerve`. Die Treue dieser gebauten Schicht IST der Kern-Verify (False-Green-Guard).

- `nerve` (Prod, **read-only** via pg_dump — niemals Schreib-/DROP-Pfad)
- `nerve_test` (gebaut: Schema+Daten-Stamp übertragen, dann upgrade head, am Ende gedroppt)
- `crm.*` (account_memory/accounts/contacts/meetings/user_preferences) — RLS/FORCE/GRANTs müssen treu getragen sein (inline-Gate prüft das); ZUSAETZLICH wird crm.* POST-SUITE (NACH pytest, VOR trap) via `sudo -u postgres psql` auf == 0 Rows geprueft (HYBRID-crm-Baseline-Check, fail-closed)
- `training.*` (inkl. `training.transcript_archive`, ORM-los — kommt mit dem Schema-Dump mit)
- `public.alembic_version` (Stamp-Row vom Prod-nerve übertragen)

### Katalog-Beleg (verbatim aus RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test)

```
pg_policies (schemaname='crm') → 7 Policies:
  account_memory: anon_worker_read, anon_worker_stamp, tenant_isolation
  accounts/contacts/meetings/user_preferences: tenant_isolation
pg_class (crm, relkind='r') → relrowsecurity=t UND relforcerowsecurity=t auf allen 5 crm-Tabellen
role_table_grants (crm) → nerve_app: DELETE/INSERT/SELECT/UPDATE ; nerve_anon_worker: SELECT (alle 5 Tabellen)
alembic upgrade head → "Running upgrade 0015 -> 0016", final version_num = 0016
Cross-Tenant-Realtest → tests/test_rls_isolation.py + tests/test_anonymizer_worker.py = 11 passed
  (test_tenant_a_cannot_read_tenant_b_account_memory PASSED = echte Isolation, nicht 0-Zeilen)
```

### Cross-Layer-Konsistenz-Tabelle

| Datum / Annahme | Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| crm-RLS-Policies | pg_dump --schema-only nerve → nerve_test (pipefail) | `pg_policies` (Katalog) | ✓ 7 Policies bewiesen; inline-Gate (Task 1) re-assertet ≥7 pro Deploy |
| crm FORCE ROW LEVEL SECURITY | pg_dump (mit owner) | `pg_class.relforcerowsecurity` | ✓ t auf 5 Tabellen; inline-Gate re-assertet ≥5 |
| crm GRANTs (nerve_app DML / anon SELECT) | pg_dump (MIT privileges) | `information_schema.role_table_grants` | ✓ bewiesen; inline-Gate re-assertet anon-SELECT ≥5; --no-privileges würde es brechen |
| prod-head Stamp-Row | pg_dump --data-only --table=alembic_version (pipefail) | `public.alembic_version.version_num` | ✓ trägt 0015 → upgrade applied nur 0016 |
| neue Revs über prod-head | alembic upgrade head | Migrations-Apply (0015→0016) | ✓ keine 0002-Kollision |
| DATABASE_URL=postgres in pytest-Subshell (A-1) | `database/db.py:9` Import → db.py:86 Hook-Registrierung | Prozess-Env (NICHT DB-Spalte) → entscheidet ob after_begin-RLS-Hook registriert wird | ✓ pre-execute audit: ohne DATABASE_URL=postgres bleibt der Hook unregistriert → False-Green; Plan 01-Tripwire (GUC NON-null + crm-Read ≥1) macht es loud-red |
| training.transcript_archive | Schema-Dump (ORM-los) | `training`-Schema-Tabelle | ✓ kommt mit Schema-Dump; Plan-03-Port nutzt sie |
| crm.* == 0 nach Test-Lauf (POST-SUITE-Check, HYBRID) | `sudo -u postgres psql` summiert count(*) ueber crm.account_memory/accounts/contacts/meetings/user_preferences, assertet == 0 | DB-State-Read (crm.* als postgres, RLS-bypassed) | ✓ HYBRID (André locked); peer-auth, passwordless, SCHILD-Muster; KEINE Env-Var/DSN; deckt die crm.*-Seite, die Plan 01's public.*-only-Waechter nicht prueft; jeder crm-Writer raeumt via cleanup_rows auf 0 |

### Bei Diskrepanz: STOP + Replan
(z.B. 0 crm-Policies nach Dump → inline-Gate exit 1 → --no-privileges/--no-owner versehentlich gesetzt → False-Green-Gefahr → Eskalation, nicht weiterbauen)

<verification>
- Req-1: Deploy-Log zeigt `pytest gegen DATABASE_URL=postgresql://nerve_app@/nerve_test` + `set -o pipefail; pg_dump --schema-only nerve`.
- A-1 (pre-execute audit): Deploy-Log belegt `DATABASE_URL=postgresql://nerve_app@/nerve_test` in der pytest-Env (PW-frei) → db.py registriert den after_begin-RLS-Hook beim Import; Plan-01-Tripwire (GUC NON-null + crm-Read ≥1 Zeile) ist GRÜN (nicht 0-Zeilen-False-Green).
- Req-3 (End-Zustand-Acceptance, André-autorisierte Mechanismus-Abweichung): Inline-Katalog-Gate + Katalog-Query
  gegen nerve_test (Task 2) → `alembic_version`=Repo-HEAD (0016) + crm/training-Schemas (`\dn`) + ≥7 crm-RLS-Policies + FORCE.
  RATIONALE: Req-3 prüft den End-Zustand (head + Schemas + RLS vorhanden) — alle erfüllt. Der MECHANISMUS
  (dump-restore + upgrade-nur-neue-Revs statt from-scratch „upgrade head") ist eine BEWUSSTE, von André
  autorisierte Abweichung vom Req-3-Wortlaut „via alembic upgrade head", weil from-scratch unmöglich (0001
  no-op → 0008-Bruch) UND create_all+replay kollidiert (0002 „already exists"). Empirisch verriegelt (RESEARCH).
- Req-5: kein `@/nerve` (ohne `_test`) in deploy.sh-DSNs; alle 4 + DATABASE_URL zeigen auf nerve_test; pg_dump auf nerve read-only.
- Req-7: simulierter Fehler (z.B. falsche Rolle / gestopptes PG / ON_ERROR_STOP / pg_dump-Crash unter pipefail) → exit≠0,
  kein systemctl restart, expliziter Log-Grund — MANUELL via Manual-Only-Verification (VALIDATION.md).
- Req-8: nach Lauf `sudo -u postgres psql -c "\l"` → kein nerve_test (trap + Pre-Run-DROP).
- crm-POST-SUITE-Check (HYBRID, André locked, T-PGTEST-29): das Deploy-Log zeigt `POST-SUITE crm-Baseline-Check OK: alle crm.* Tabellen leer (0 Leak-Rows)`; bei einem Leak bricht der Deploy mit `crm.* nicht leer nach Test-Lauf (N Leak-Rows)` (exit≠0, kein Restart). `sudo -u postgres psql` peer-auth, KEINE neue Env-Var, KEIN PW. Deckt die crm.*-Seite, die Plan 01's public.*-only-in-pytest-Waechter nicht prueft.
- Req-9: voller deploy.sh production grün (Tests + Schild-Guard gegen nerve_test als PASSED nicht SKIPPED + crm-POST-SUITE-Check OK + Restart); Prod-nerve unverändert.
- MED-2: `test_schild_guard.py` erscheint im Gate-Log als PASSED (nicht SKIPPED, nicht error) sobald NERVE_SCHILD_TEST_DSN → nerve_test.
- MED-3 (Ein-Deploy-Constraint): die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03+04 zusammen committet sind; kein Zwischen-Deploy nach Wave 1 (der `<verify>`-deploy.sh-Lauf ist der eine finale integrierte Gate-Lauf).
</verification>

<success_criteria>
- Gate-Block in deploy.sh: Whitelist-Guard + trap EXIT + Pre-Run-DROP + CREATE OWNER postgres + pg_dump-Restore-Build (schema + alembic_version-Stamp, BEIDE mit `set -o pipefail` + upgrade head) + inline-Dump-Treue-Katalog-Gate (≥7 crm-Policies + FORCE≥5 + anon-SELECT-GRANTs≥5, fail-closed) + pytest **DATABASE_URL (A-1) + 4-DSN** (ANON_PW via Env, single-quoted inner) + **POST-SUITE-crm-Baseline-Check** (`sudo -u postgres psql`, crm.* == 0 Rows, NACH pytest VOR trap, fail-closed), alles fail-closed.
- POST-SUITE-crm-Baseline-Check (HYBRID, André locked, T-PGTEST-29): crm.* == 0 Rows via `sudo -u postgres psql` (peer-auth, passwordless, SCHILD-Muster) — KEIN NERVE_BASELINE_GUARD_DSN, KEIN Superuser-PW im Test-Env; deckt die crm.*-Seite, die Plan 01's public.*-only-in-pytest-Waechter nicht prueft; Leak (>0) → exit≠0, kein Restart.
- A-1: `DATABASE_URL=postgresql://nerve_app@/nerve_test` steht in der pytest-Subshell (gleicher Wert wie TEST_DATABASE_URL) → db.py registriert den after_begin-RLS-Hook beim Import; Plan-01-Tripwire grün (GUC NON-null + crm-Read ≥1 Zeile).
- Dump-Treue automatisiert pro Deploy (inline-Gate) + verbatim im SUMMARY dokumentiert; Schild-Guard gegen nerve_test PASSED (MED-2, nicht SKIPPED).
- MED-3: Ein-Deploy-Constraint — Phase validiert durch genau EINEN deploy.sh production-Lauf nach gemeinsamem Commit aller 3 Pläne; kein Zwischen-Deploy nach Wave 1.
- KEIN create_postgres_schema.py / stamp 0001 im Gate (kollisionsfrei via pg_dump). anon_worker-PW nie geloggt/interpoliert; alle DSNs + DATABASE_URL → nerve_test; Prod-nerve unberührt.
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-02-SUMMARY.md`
</output>

########## DATEI: .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-03-remove-sqlite-port-klasse-a-PLAN.md ##########
---
phase: 08.23.2.PGTEST
plan: 03
type: execute
wave: 2
depends_on: [1, 2]
files_modified:
  - database/db.py
  - app.py
  - tests/test_account_memory_briefing.py
  - tests/test_anonymizer_worker.py
  - tests/test_08_14_apirate_seed.py
  - tests/test_tenant_orgs.py
  - tests/test_postcall_split.py
  - tests/test_ewb_rate_api.py
  - tests/test_profile_editor_validation.py
  - tests/test_ft_seed.py
  - tests/test_ab_stats.py
  - tests/test_cost_tracker.py
autonomous: true
complexity: "🔴 (security-near — entfernt SQLite-Emulation; Klasse-A-Tests müssen im selben Zug auf PG portiert werden, sonst Collection-Error)"
requirements: [Req-4, Req-6]
user_setup: []

must_haves:
  truths:
    - "Der cf5de6d ATTACH-Listener (db.py) und der app.py SQLite-Alembic-Hook sind entfernt"
    - "test_account_memory_briefing.py + die anonymizer Logic-Group laufen gegen nerve_test-PG (nicht SQLite-StaticPool)"
    - "Die volle Suite läuft grün im Gate OHNE die SQLite-Pflaster"
    - "test_rls_isolation.py + test_anonymizer_worker.py RLS-Gruppe erscheinen als PASSED (nicht SKIPPED)"
    - "Die volle Suite collected + läuft grün im Gate OHNE SQLite-Emulations-Pflaster UND ohne verwaisten Listener-abhängigen Test — test_08_14_apirate_seed.py ist entblockt (create_all auf die public ApiRate-Tabelle gescopet, kein 'unknown database crm')"
    - "test_tenant_orgs.py ist auf PG-Trigger-Semantik portiert (F1): es ERWARTET die vom AFTER-INSERT-Trigger trg_mk_tenant_org auto-erzeugte tenant_orgs-Row statt Python-seitig zu doppeln — kein UNIQUE(legacy_org_id)-Kollisions-Error mehr auf nerve_test, das Gate bleibt grün"
    - "Die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03 zusammen committet sind — kein Zwischen-Deploy nach Wave 1"
    - "Die volle pytest-Suite (inkl. der 11 SQLite-Laxheits-Tests) ist im Gate GRÜN gegen nerve_test ohne stillgelegte/geskippte real-rote Tests — die 5 test-spezifischen FK-Deltas (test_postcall_split CONSUME base-seed, test_ewb_rate_api unique-email, test_profile_editor_validation parents/tenant, test_ft_seed HONEST/investigativ — echte Ursache verifizieren statt vermutete maskieren, test_ab_stats base-org) sind angewandt"
    - "Kein Test asserted eine GLOBALE, ungefilterte count()/all() auf einer Tabelle, die der Base-Seed (Plan 01 Task 4) befuellt ODER in die Code-under-test auf eigener Session committet — solche Assertions werden auf test-eigene IDs / baseline-delta gescoped (persistentes nerve_test, D-03 1x-Build). Konkret behoben: test_tenant_orgs:65 (BLOCKER, globale count==3) auf test-eigene Org/User/TenantOrg-IDs; test_cost_tracker:51 (count()==0) baseline-delta/provider-gefiltert (log_api_cost committet auf eigener SessionLocal-Session, Rows persistieren)"
  artifacts:
    - path: "database/db.py"
      provides: "RLS-GUC-Plumbing OHNE SQLite-ATTACH-Listener"
      contains: "set_current_tenant"
    - path: "tests/test_account_memory_briefing.py"
      provides: "Briefing-Merge-Test gegen nerve_test-PG"
    - path: "tests/test_tenant_orgs.py"
      provides: "tenant_orgs-Seed/Backfill-Test gegen nerve_test-PG mit Trigger-Semantik (kein Python-Doppel-Seed), alle Assertions auf test-eigene IDs gescoped (nicht global)"
    - path: "tests/test_cost_tracker.py"
      provides: "Cost-Tracker-Test gegen nerve_test-PG; die count()==0-Assertion in test_missing_rate_no_raise ist persistence-robust (baseline-delta / provider='unknown'-Filter) statt globaler count"
  key_links:
    - from: "tests/test_account_memory_briefing.py"
      to: "nerve_test-PG (über conftest-Fixture aus Plan 01)"
      via: "PG-Session statt sqlite-StaticPool"
      pattern: "TEST_DATABASE_URL|nerve_app_pg|get_session"
    - from: "database/db.py"
      to: "(entfernt) _sqlite_attach_crm_training_schemas"
      via: "Listener gelöscht"
      pattern: "_sqlite_attach_crm_training_schemas"
    - from: "tests/test_tenant_orgs.py"
      to: "nerve_test-PG trg_mk_tenant_org"
      via: "Trigger-auto-erzeugte tenant_orgs-Row zurücklesen (kein manueller TenantOrg-Insert), Assertions auf test-eigene IDs gefiltert (nicht global gegen Base-Seed)"
      pattern: "tenant_orgs|trg_mk_tenant_org|legacy_org_id.in_"
---

<objective>
<!-- FK-debt fold 2026-06-15: base-seed (Plan 01) + 5 deltas (Plan 03) — André/Claudian-bestätigte 11-Test-Klassifikation (11 A / admin_dashboard→SAFE / 24 SAFE), kein Split. -->
<!-- revised via --reviews 2026-06-15: Gemini-Finding eingearbeitet — MEDIUM (Reverse-FK-Teardown der Klasse-A-Tests MUSS im Fixture-POST-yield laufen, sonst leaken Rows bei Assertion-Fehler in nerve_test → State-Leakage für nachfolgende Tests auf derselben Connection). -->
<!-- pre-execute blocker fix 2026-06-15: Claudian-Deep-Audit fand einen GOAL-KILLER — der globale cf5de6d ATTACH-Listener trägt einen DRITTEN Test (test_08_14_apirate_seed.py, fresh_engine Z.14-19), der NICHT in Task 2 portiert war. Nach Listener-Entfernung würde `Base.metadata.create_all` dort "unknown database crm" werfen → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy. Neuer Task 3 (Option B: create_all auf die public ApiRate-Tabelle scopen) schließt die Lücke. Vollständige create_all|sqlite-Map über tests/ verifiziert: nur test_08_14 war ungedeckt; test_08_20_3 (raw single-table, kein create_all/crm) + test_meeting_form_dsgvo (Kommentar) sind safe. Sekundär: WAL-Hook-"prüfen" → explizite KEEP-Entscheidung. -->
<!-- db_from_client contract fix + ft_seed/postcall_split precision 2026-06-15 -->
<!-- pre-execute audit fold 2026-06-15: F1 — test_tenant_orgs.py bricht auf nerve_test-PG (es doppelt Python-seitig die vom Trigger trg_mk_tenant_org bereits erzeugte tenant_orgs-Row → UNIQUE(legacy_org_id)-IntegrityError + count-Asserts == 3 halten nicht → Gate ROT → blockt jeden Deploy, blocker-class wie test_08_14). Neuer Task 4 portiert es auf Trigger-Semantik. MED-1: jede "try...finally analog test_rls_isolation.py:103-113"-Formulierung präzisiert zu "POST-yield try/except analog test_rls_isolation.py:102-116" (das zitierte Cleanup ist try/except-NACH-yield, NICHT ein literales try...finally im Test-Body). -->
<!-- Option-A persistence-hardening fold 2026-06-16: cleanup-helper + baseline-guard (à la SCHILD) + Gruppe-A/B-Fixes; Option-2 verworfen (RLS-GUC-Leak db.py:92). PHASE-WEITE DIREKTIVE für DIESEN Plan: JEDER committende Test in Plan 03 (Tasks 2/4/5/6/7/9/10) adoptiert den gemeinsamen cleanup_rows-Helfer (Plan 01 Task 5) in seiner POST-yield-Teardown-Sektion (reverse-FK, crm.* unter Tenant-GUC) und MUSS den public-Baseline-Wächter (Plan 01 Task 6) bestehen — DB == Baseline nach dem Test, kein Leak. crm.*-Schreiber (Task 2 anonymizer-RLS) zusätzlich vom POST-SUITE-sudo-postgres-crm-Check (Plan 02) abgedeckt. Die ab_stats/per_sid_migration/dashboard_outcome_reminder-Overlap-Bereinigung: ab_stats bleibt hier (Task 9, hat bereits POST-yield-Teardown); per_sid_migration + dashboard_outcome_reminder gehören zu Plan 04 Task 7. -->
<!-- Gemini-3.1-Pro Delta-Review-2 fold 2026-06-15: globale count-Assertions vs. persistentes nerve_test + Base-Seed (test_tenant_orgs:65 BLOCKER, test_cost_tracker:51 sibling) -> ID-gescoped/baseline-delta. -->
Entferne die beiden SQLite-Emulations-Pflaster (Req-6): den `cf5de6d`-ATTACH-Listener in `database/db.py`
(Z.29-49) und den SQLite-only Alembic-Auto-Hook in `app.py` (Z.1105-1127, der `if startswith('sqlite')`-
Zweig). Da der ATTACH-Listener von zwei Klasse-A-Tests gebraucht wird (sie bauen lokal `sqlite://`+StaticPool
+ crm/training-create_all), MÜSSEN diese im selben Zug auf nerve_test-Postgres portiert werden — sonst
werfen sie "unknown database crm" bei der Collection (RESEARCH Q6 Klasse A, Pitfall 2). Ein DRITTER Test
(test_08_14_apirate_seed.py) hängt ebenfalls am globalen Listener — er wird in Task 3 entblockt (Option B:
sein create_all wird auf die PUBLIC ApiRate-Tabelle gescopet, kein crm/training mehr nötig). Ein VIERTER Test
(test_tenant_orgs.py) bricht aus einem ANDEREN Grund auf echtem PG: er doppelt Python-seitig die vom Trigger
`trg_mk_tenant_org` bereits erzeugte tenant_orgs-Row → er wird in Task 4 auf Trigger-Semantik portiert (F1).

Purpose: Req-6 (SQLite-Emulation entfernt, kein toter Pfad), Req-4 (RLS+Anon laufen WIRKLICH — der ganze
Suite-Lauf wird erst grün, wenn die Klasse-A-Tests portiert sind, test_tenant_orgs trigger-tauglich ist und
die RLS-Gruppen-DSNs gesetzt sind).
Output: db.py + app.py ohne Pflaster; beide Klasse-A-Tests gegen PG; test_08_14 entblockt (public-Tabelle);
test_tenant_orgs auf Trigger-Semantik portiert.

Wave-Kopplung (DEEP-WORK-Regel): Req-6 + Klasse-A-Port MÜSSEN zusammen — daher in EINEM Plan/Wave.
Depends_on Plan 01 (conftest-PG-Fixtures als Vorbild/Quelle der PG-Session) + Plan 02 (Gate baut nerve_test,
sonst gibt es nichts, wogegen die portierten Tests laufen).

MED-3 (Ein-Deploy-Constraint, pre-execute audit): die Phase wird durch GENAU EINEN `deploy.sh production`-Lauf
validiert NACHDEM Plan 01 + 02 + 03 zusammen committet sind. KEIN Zwischen-Deploy nach Wave 1 — das Gate
self-testet den deployten Baum, der nur mit Wave-2 (Listener-Entfernung + Klasse-A-Port + test_tenant_orgs-Port)
konsistent ist. Ein Deploy mit Wave-1-Gate aber ohne Wave-2 würde „unknown database crm" (test_08_14) +
UNIQUE-Kollision (test_tenant_orgs) werfen → Gate ROT.

GLOBAL-COUNT-vs-PERSISTENZ-Regel (Gemini-Delta-Review-2, 2026-06-15): nerve_test wird EINMAL gebaut (D-03)
und ist PERSISTENT über den ganzen Gate-Lauf. Committete Rows akkumulieren aus (a) dem session-scoped
Base-Seed (Plan 01 Task 4 committet Org id=1 + die vom Trigger erzeugte tenant_org + User id=1) und (b)
Code-under-test, der auf SEINER EIGENEN Session committet (z.B. `log_api_cost` öffnet `_db_mod.SessionLocal()`
+ `db.commit()`). Jede Assertion einer GLOBALEN, ungefilterten `count()`/`all()` auf einer so befüllten Tabelle
ist garantiert False-Red → fail-closed Gate blockt JEDEN Deploy. Daher: solche Assertions werden auf
test-EIGENE IDs ODER baseline-delta gescoped (Task 4 für test_tenant_orgs, Task 10 für test_cost_tracker, plus
die generelle Regel in success_criteria).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md

<interfaces>
<!-- Verträge. Die portierten Tests laufen gegen die nerve_test-DB, die das Gate (Plan 02) baut. -->

database/db.py (zu entfernen):
- Z.29-49 `_sqlite_attach_crm_training_schemas` (@event.listens_for(Engine,"connect")) — der cf5de6d-Listener.
- Behalten: WAL-Hook Z.22-27. KEEP-ENTSCHEIDUNG (pre-execute 2026-06-15, war "prüfen"): Der WAL-Hook ist auf der
  MODUL-Engine registriert und durch `if 'sqlite' in _DATABASE_URL` (Z.22) beim Import geguardet. Im PG-Gate
  (DATABASE_URL=postgres) wird er NIE registriert → inert im Gate. Er schützt genuine lokale Dev-SQLite
  (DATABASE_URL-Default `sqlite:///database/nerve.db`) — ECHTE SQLite-Nutzung AUSSERHALB der Tests, NICHT die
  crm/training-Emulation. Er ist KEIN Req-6-Ziel (Req-6 = crm/training-ATTACH-Emulation + app.py-sqlite-Alembic-
  Hook). → WAL-Hook bleibt UNANGETASTET (Foundation-Register-Note, kein offenes TODO).
- Behalten: set_current_tenant/after_begin-Hook Z.56-103 (RLS-Plumbing, bleibt).

app.py Z.1105-1127 (zu entfernen):
- Der `if _db_url_str.startswith('sqlite'):` Zweig der `alembic_command.upgrade(cfg,'head')` fährt.
- Der `else`-Print "Alembic-Hook uebersprungen (Postgres...)" kann bleiben oder der ganze Block entfällt
  (Postgres-Schema kommt von deploy.sh). Postgres-only für Tests = André-Entscheidung (D, SPEC Req-6).

services/cost_tracker.py (Task 10 — Persistenz-Beleg, NICHT ändern):
- `log_api_cost` (Z.~99/132): öffnet eine EIGENE `_db_mod.SessionLocal()` und `db.commit()` — die geschriebene
  ApiCostLog-Row persistiert im nerve_test über Test-Grenzen hinweg (eigene Session, nicht die db_session-Fixture).
  Deshalb ist eine GLOBALE `query(ApiCostLog).count() == 0`-Assertion (test_cost_tracker:51) persistence-fragil.

tests/test_account_memory_briefing.py (Klasse A — IST):
- `_patched_session` (Z.20-55): create_engine("sqlite://", StaticPool) + ATTACH(via globalem Listener) + create_all(crm.*) + monkeypatch precall.get_session.
- 4 Tests prüfen merge_account_memory: meddpicc surfaced, graceful-absent, no-account-id-noop, pii-cache-preseed.

tests/test_anonymizer_worker.py (Klasse A LOGIC-GROUP — IST):
- `mem_engine` (Z.57-96): create_engine("sqlite://", StaticPool) + create_all + raw CREATE TABLE training.transcript_archive.
- 6 Logic-Tests (process_unstamped MERGE/FILTER/HASH/GATING via _fake_anonymize-Stub).
- `_seed_account` (Z.99-140): org/user/conversation_log/call/account/account_memory-Kette (+ optional segments). `_seg_id` itertools.count für BIGSERIAL-Workaround.
- RLS-GROUP (Z.247+): bereits REAL-PG (nerve_app + nerve_anon_worker), läuft sobald DSNs gesetzt (Gate, Plan 02). NICHT anfassen außer Verifikation.

tests/test_08_14_apirate_seed.py (Listener-abhängig — IST, Task 3 entblockt):
- `fresh_engine` (Z.14-19): `from database.models import Base` + create_engine('sqlite:///:memory:') + `Base.metadata.create_all(engine)`. Heute funktioniert das NUR weil der globale cf5de6d-Listener crm/training auf diese frische Engine ATTACHed; nach Listener-Entfernung wirft create_all "unknown database crm".
- `ApiRate` (models.py:524-540) ist eine PUBLIC-Tabelle (`__tablename__='api_rates'`, `__table_args__` nur UniqueConstraint + comment — KEIN {'schema':'crm'}). Das Schema-Problem entsteht nur, weil `Base.metadata.create_all` ALLE Tabellen inkl. crm.* baut. Scopen auf `ApiRate.__table__.create(engine)` baut nur die public api_rates-Tabelle → kein crm → DSN-unabhängig (läuft im Gate UND lokal), bleibt echte SQLite-Runtime-Write-Regression (NOT-NULL last_checked_at).

tests/test_tenant_orgs.py (SQLite-Annahme-Test — IST, Task 4 portiert auf PG-Trigger-Semantik, F1; PLUS Delta-Review-2 ID-Scoping):
- Docstring (verbatim): "SQLite in-memory has NO triggers ... the *live* Postgres dual-write trigger `trg_mk_tenant_org` and the migration's post-backfill `RAISE EXCEPTION` guard are NOT exercised here". Importiert nur `TenantOrg, Organisation, User, Call` — berührt AUSSCHLIESSLICH public.*, ZERO crm.
- Auf SQLite (heute): `_seed_tenant_orgs` (Z.38-46) macht Python-seitiges INSERT TenantOrg pro Org; `test_dualwrite_trigger_fires` (Z.70-82) + `test_dualwrite_idempotent` (Z.85-94) machen manuelle `db_session.add(TenantOrg(...legacy_org_id=org.id...))`.
- Auf nerve_test-PG (Problem F1): Migration 0011's AFTER-INSERT-Trigger `trg_mk_tenant_org` auf `organisations` erzeugt die tenant_orgs-Row AUTOMATISCH bei jedem `INSERT organisations`. Die Python-seitigen `_seed_tenant_orgs` + manuellen TenantOrg-Inserts DOPPELN diese Trigger-Row → kollidieren mit `UNIQUE(legacy_org_id)` → IntegrityError WO der Test ihn NICHT erwartet.
- Auf nerve_test-PG (Problem Delta-Review-2, BLOCKER): `test_seed_one_row_per_org` (Z.65) asserted `db_session.query(TenantOrg).count() == db_session.query(Organisation).count() == 3` — eine GLOBALE, UNGEFILTERTE count. Der committete Base-Seed (Plan 01 Task 4: Org id=1 + dessen Trigger-tenant_org + User id=1) plus etwaige generische [PGTEST-GENERIC]-Tenants aus `_seed_test_tenant` sind bereits präsent → global count > 3 → FAILS. Zusätzlich iterieren `_seed_tenant_orgs` (Z.40-46) und `_backfill_calls_tenant_id` (Z.50-55) `query(Organisation).all()` / `query(User).all()` / `query(TenantOrg).all()` GLOBAL — sie sehen jetzt auch die Base-Seed-Rows. (Der `_seed_tenant_orgs`-Existing-Check Z.40-43 ist idempotent → keine Doppel-Insertion der Base-Trigger-Row, aber die COUNT-Assertion :65 ist die harte Failure.)
- ECHTE Idempotenz-Assertion (BEHALTEN): `test_dualwrite_idempotent` (Z.85-94) erwartet EINEN IntegrityError auf einen WIRKLICHEN Duplikat-Insert (zweiter TenantOrg mit gleichem legacy_org_id) — diese Assertion bleibt valide.

tests/test_cost_tracker.py (Base-Seed-Consumer — IST, FK-solved durch Plan 01 Task 4; Task 10 macht :51 persistence-robust):
- `test_freeze_fx_on_write` (passiert jetzt, weil Base-Seed user id=1 liefert) committet eine ApiCostLog-Row via `log_api_cost` (eigene SessionLocal-Session) → die Row PERSISTIERT in nerve_test.
- `test_missing_rate_no_raise` (Z.51): asserted `db_session.query(ApiCostLog).count() == 0`. Intent = "unbekannter Provider → log_api_cost schreibt NICHTS". Aber die persistierte Row aus dem früheren Test → global count > 0 → FAILS, OHNE dass der Intent verletzt ist (False-Red, sibling der test_tenant_orgs-Klasse).

Vorbild für PG-Session in Tests (aus Plan 01 conftest + test_rls_isolation.py):
- nerve_app_pg_conn-Fixture (psycopg2) ODER db_session/db_from_client (SQLAlchemy gegen TEST_DATABASE_URL — bindet das MODUL-SessionLocal um, damit der RLS-Hook feuert).
- Trigger-tenant_orgs-Muster: INSERT organisations → SELECT tenant_orgs.id (für crm-FK + set_current_tenant). test_rls_isolation.py:33-54.
- crm.account_memory.tenant_id muss = gesetzter Tenant sein (RLS WITH CHECK); set_current_tenant vor crm-Writes.
- Best-Effort-Teardown in der Fixture-POST-yield-Sektion (NACH `yield`) als `try/except` — test_rls_isolation.py:102-116. WICHTIG (MED-1, pre-execute audit): das zitierte Cleanup ist `cur = conn.cursor(); try: <deletes>; conn.commit() except Exception: conn.rollback()` NACH dem yield. pytest führt die POST-yield-Sektion auch bei Test-Fehler aus (das IST das finally-Äquivalent) — es ist KEIN literales `try...finally` im Test-Body. Reverse-FK-Reihenfolge.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: cf5de6d-ATTACH-Listener (db.py) + app.py SQLite-Alembic-Hook entfernen</name>
  <read_first>
    - database/db.py Z.1-53 (ATTACH-Listener Z.29-49 + Engine-Setup drumherum; WAL-Hook Z.22-27 bleibt)
    - app.py Z.1103-1128 (der startswith('sqlite')-Alembic-Hook)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q6 Klasse A (warum der Listener 2 Tests trägt) + SPEC Req-6
    - .planning/_testgate_gemini_OUT.md (Cross-AI: Listener ist statisch korrekt aber bleibt SQLite-Pflaster — bestätigt Entfernung)
  </read_first>
  <behavior>
    - `_sqlite_attach_crm_training_schemas` (db.py Z.41-49) + sein Doc-Kommentar (Z.29-40) gelöscht.
    - Der app.py `if _db_url_str.startswith('sqlite'):` alembic-upgrade-Zweig entfernt (Postgres-Schema kommt von deploy.sh).
    - `import sqlite3` in db.py entfernen, wenn nach Löschung ungenutzt.
    - Nach Entfernung: kein aktiver Code-Pfad hängt an SQLite-Schema-Emulation oder SQLite-Auto-Alembic.
    - Der WAL-Hook (Z.22-27) bleibt UNANGETASTET — KEEP-Entscheidung (siehe action Schritt 1): Modul-Engine,
      sqlite-geguardet → inert im PG-Gate; schützt lokale Dev-SQLite (echte SQLite-Nutzung außerhalb der Tests);
      KEIN Req-6-Emulations-Ziel. Es bleibt KEIN offenes "prüfen"-TODO zurück.
  </behavior>
  <action>
    1. **db.py:** Lösche den Block Z.29-49 vollständig (Kommentar-Header Z.29-40 + die Funktion
       `_sqlite_attach_crm_training_schemas` Z.41-49). Prüfe, ob `import sqlite3` (Z.2) danach noch
       irgendwo genutzt wird; wenn nicht → entfernen. Den WAL-Hook (Z.22-27) NICHT anfassen — explizite
       KEEP-ENTSCHEIDUNG (pre-execute 2026-06-15, ersetzt das frühere "prüfen"): Der Hook ist auf der
       MODUL-Engine registriert und durch `if 'sqlite' in _DATABASE_URL` beim Import geguardet → im PG-Gate
       (DATABASE_URL=postgres) NIE registriert (inert). Er schützt die genuine lokale Dev-SQLite-DB
       (DATABASE_URL-Default `sqlite:///database/nerve.db`) — echte SQLite-Nutzung AUSSERHALB der Tests, NICHT
       die crm/training-ATTACH-Emulation. Er ist KEIN Req-6-Ziel (Req-6 = crm/training-ATTACH-Emulation +
       app.py-sqlite-Alembic-Hook). Daher bleibt er. Den set_current_tenant/after_begin-RLS-Block (Z.56-103)
       ebenfalls NICHT anfassen.
    2. **app.py:** Entferne den `if _db_url_str.startswith('sqlite'):`-Zweig (Z.1114-1125), der
       `alembic_command.upgrade(cfg, 'head')` ausführt. Der `else`-Print (Z.1126-1127, "Alembic-Hook
       uebersprungen (Postgres)") darf bleiben (informativ) ODER der ganze Hook-Block (Z.1105-1127) entfällt
       — wähle: ganzen Block entfernen, da Tests jetzt Postgres-only sind und Prod-Schema von deploy.sh kommt.
       Behalte `_migrate()` (Z.1103) — das ist eine separate Spalten-Migration, NICHT der alembic-Hook.
    3. KEINE Migration umschreiben (Anti-Pattern, SPEC Constraint). KEIN neues SQLite-Pflaster.
    Der WAL-Hook-Rest ist mit obiger KEEP-Begründung im SUMMARY als Foundation-Register-Eintrag zu vermerken
    (SPEC Req-6 erlaubt begründete Reste); es bleibt KEIN offenes "prüfen"-TODO.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "_sqlite_attach_crm_training_schemas|startswith\(.sqlite.\)" database/db.py app.py'; echo "EXIT=$?"  # erwartet: kein Treffer (Req-6-Acceptance). Voll-Beleg: Gate-Suite grün ohne Pflaster.</automated>
  </verify>
  <done>
    `grep _sqlite_attach_crm_training_schemas database/db.py` → leer; `grep "startswith('sqlite')" app.py`
    → kein alembic-upgrade-Zweig mehr. Listener + Hook entfernt (oder begründeter Rest im SUMMARY-Foundation-
    Register). Der WAL-Hook bleibt bewusst (KEEP-Begründung im SUMMARY, kein offenes TODO). Die Suite läuft
    grün ohne diese Pflaster (Beleg im Gate-Lauf, Plan 02).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Klasse-A-Tests auf nerve_test-PG portieren (test_account_memory_briefing + anonymizer Logic-Group)</name>
  <read_first>
    - tests/test_account_memory_briefing.py (ganze Datei — _patched_session + 4 Tests)
    - tests/test_anonymizer_worker.py Z.1-245 (Header, mem_engine, _seed_account, _run, die 6 Logic-Tests)
    - tests/conftest.py (NACH Plan 01: db_session/db_from_client/nerve_app_pg_conn + TEST_TENANT_UUID/Seed-Helper — das PG-Vorbild; db_session bindet das MODUL-SessionLocal um, damit der RLS-Hook feuert)
    - tests/test_rls_isolation.py Z.33-90 (_new_tenant Trigger-Muster + crm.accounts/account_memory-Seed unter Tenant-GUC — D-04-Muster) + Z.101-116 (Best-Effort-Reverse-FK-Teardown in der POST-yield-Sektion: cur/try/except NACH dem yield, läuft auch bei Assertion-Fehler — das IST das finally-Äquivalent, KEIN literales try...finally im Body, MED-1)
    - .planning/.../08.23.2.PGTEST-RESEARCH.md Q6 Klasse A + Q4 (Real-Commit + Tenant-Seed) + Klasse D (BIGSERIAL/JSONB-Hinweise)
  </read_first>
  <behavior>
    - test_account_memory_briefing.py: die 4 merge-Tests laufen gegen nerve_test-PG (crm.account_memory echt), nicht sqlite-StaticPool. Assertions bleiben Runtime-Integration (meddpicc/context_hooks surfaced, graceful-absent, noop, pii-preseed) — KEINE Source-Presence-Checks.
    - test_anonymizer_worker.py Logic-Group: die 6 Tests laufen gegen nerve_test-PG (transcript_archive echt via dump-gebautes Schema, KEIN raw CREATE TABLE mehr). MERGE/FILTER/HASH/GATING-Logik bleibt geprüft (_fake_anonymize-Stub bleibt — kein NLP-Load).
    - Beide nutzen das Trigger-tenant_orgs-Seed + set_current_tenant (crm-FK + RLS) und committen real mit deterministischem Teardown (Wegwerf-DB, aber Intra-Lauf-Leak-Schutz). Der Reverse-FK-Teardown läuft ZWINGEND in der Fixture-POST-yield-Sektion (try/except NACH dem yield, analog test_rls_isolation.py:102-116), sodass die Cleanup-Deletes auch bei einem Assertion-Fehler ausgeführt werden (sonst leaken Rows in nerve_test → State-Leakage für nachfolgende Tests auf derselben Connection — Gemini-MEDIUM).
    - Die RLS-Gruppe in test_anonymizer_worker.py (Z.247+) bleibt unverändert und läuft (DSNs vom Gate).
  </behavior>
  <action>
    Ersetze die SQLite-StaticPool-Fixtures durch PG-Fixtures gegen nerve_test. KONKRET:

    1. **test_account_memory_briefing.py — `_patched_session` (Z.20-55):**
       Ersetze die `create_engine("sqlite://", StaticPool)` + `create_all`-Logik durch eine PG-Session
       gegen TEST_DATABASE_URL. Nutze das Vorbild aus conftest (Plan 01): entweder die `db_session`-Fixture
       direkt verwenden ODER eine lokale Fixture, die das MODUL-`database.db.SessionLocal` an
       `create_engine(os.environ['TEST_DATABASE_URL'])` umbindet (wie db_session/client, damit der RLS-Hook
       feuert — NICHT eine frische lokale sessionmaker), einen Test-Tenant via Trigger-Muster seedet,
       `set_current_tenant(tenant_uuid)` aufruft, und `precall.get_session` auf eine PG-Session aus dem
       MODUL-SessionLocal monkeypatcht. SKIP wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback). Das Schema
       NICHT mit create_all bauen — es existiert (Gate, pg_dump+alembic). Die crm.account_memory-Inserts der
       Tests brauchen `tenant_id` = der gesetzte Test-Tenant (RLS WITH CHECK) und ein vorhandenes account-FK-
       Ziel (crm.accounts) — passe die Test-Inserts an: vor dem AccountMemory-Insert eine crm.accounts-Row mit
       demselben tenant_id + account_id anlegen (analog test_rls_isolation.py:82-90).
       **Deterministischer Teardown ZWINGEND in der Fixture-POST-yield-Sektion** (Gemini-MEDIUM, MED-1): die
       getaggten Rows (`[PGTEST-...]`) unter dem Tenant-GUC in reverse-FK-Reihenfolge löschen (account_memory
       → accounts → tenant_orgs → organisations) — EXAKT analog test_rls_isolation.py:101-116, wo das Cleanup
       als `cur = conn.cursor(); try: <deletes>; commit; except Exception: rollback` NACH dem `yield` steht.
       pytest führt diese POST-yield-Sektion auch bei AssertionError aus (das IST das finally-Äquivalent), also
       läuft das Cleanup auch wenn ein Test fehlschlägt — sonst bleiben Rows in nerve_test für nachfolgende
       Tests auf derselben Connection liegen (State-Leakage). Es ist KEIN literales `try...finally` im
       Test-Body — die POST-yield-Platzierung ist das Mittel.
    2. **test_anonymizer_worker.py — `mem_engine` (Z.57-96):**
       Ersetze sqlite-StaticPool + raw `CREATE TABLE training.transcript_archive` durch eine Engine gegen
       TEST_DATABASE_URL (Schema vom Gate via pg_dump+alembic — training.transcript_archive existiert dann echt,
       kein hand-DDL mehr). SKIP wenn DSN fehlt. ENTFERNE den `_seg_id = itertools.count` BIGSERIAL-Workaround
       NUR falls die Inserts die id-Spalte nicht mehr explizit setzen müssen (PG BIGSERIAL vergibt selbst) —
       prüfe `_seed_account` (Z.127-130 setzt `id=next(_seg_id)` für TranscriptSegment): gegen PG mit echtem
       BIGSERIAL die explizite id WEGLASSEN (Sequenz übernimmt), sonst RESEARCH-Klasse-D-Kollision. account/
       account_memory unter set_current_tenant + tenant_orgs-Seed (RLS). `_run`/`_archive_rows`/`_anonymized_at`
       (Z.143-165) funktionieren gegen PG unverändert (sie nutzen text()-SQL auf crm./training.). Der
       anonymizer arbeitet als nerve_app — prüfe, ob process_unstamped gegen die crm.*-RLS Tenant-Kontext
       braucht; falls ja, set_current_tenant vor `_run`.
       **Auch hier: der Reverse-FK-Teardown der geseedeten Rows (account_memory/accounts/transcript_archive/
       tenant_orgs/organisations) MUSS in der Fixture-POST-yield-Sektion liegen** (Gemini-MEDIUM, MED-1; try/except
       NACH dem yield, analog test_rls_isolation.py:101-116), damit er bei Assertion-Fehler eines der 6
       Logic-Tests trotzdem läuft (kein State-Leak auf die geteilte nerve_test-Connection).
    3. **Anti-False-Green (CLAUDE.md Test-Regel):** KEINE `inspect.getsource`/`hasattr`/grep-on-source-
       Assertions einführen. Die Tests bleiben Integration-Assertions auf echte DB-Rows / Return-Werte /
       gestampte anonymized_at — exakt wie heute, nur Backend PG statt SQLite. Der `_fake_anonymize`-Stub
       bleibt (kein NLP-Load — das ist ein I/O-Mock, kein Source-Presence-Check).
    4. RLS-Gruppe (Z.247+) NICHT ändern — sie ist bereits Real-PG und läuft sobald die DSNs gesetzt sind
       (Gate, Plan 02). Nur verifizieren, dass sie im Gate-Lauf PASSED erscheint (Req-4).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy3.log | grep -E "test_account_memory_briefing|test_anonymizer_worker|test_rls_isolation|PASSED|SKIPPED|passed|failed"; echo "EXIT=$?"  # Req-4/Req-6: Klasse-A-Tests grün gegen PG; RLS+Anon-RLS-Gruppe PASSED nicht SKIPPED; keine Collection-Errors; kein Reststate-Leak (POST-yield-Teardown).</automated>
  </verify>
  <done>
    test_account_memory_briefing.py + test_anonymizer_worker.py Logic-Group laufen gegen nerve_test-PG
    (kein sqlite-StaticPool, kein hand-DDL training.transcript_archive); die volle Suite collected + läuft
    grün im Gate OHNE den ATTACH-Listener. Der Reverse-FK-Teardown beider Test-Gruppen liegt in der
    Fixture-POST-yield-Sektion (try/except nach dem yield, analog test_rls_isolation.py:101-116) → Cleanup läuft
    auch bei Assertion-Fehler, kein State-Leak in nerve_test. test_rls_isolation.py + test_anonymizer_worker.py
    RLS-Gruppe erscheinen im Gate-Log als PASSED (nicht SKIPPED) — Req-4. Falls ein Test an einem ECHTEN App-Bug
    rot wird (Klasse D/E, z.B. test_ft_seed) → im SUMMARY als Fund ESKALIEREN, NICHT still patchen (SPEC out-of-scope).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: test_08_14_apirate_seed.py entblocken (create_all auf ApiRate-Tabelle scopen, NICHT Base.metadata)</name>
  <read_first>
    - tests/test_08_14_apirate_seed.py (ganze Datei — `fresh_engine` Z.14-19 + SEED_ROWS Z.23-32 + die TestApiRateSeed-Klasse mit den 4 INSERT/COUNT-Tests Z.35-91; speziell die 8-rows-Assertion + die NOT-NULL-last_checked_at-Regression Z.53-59)
    - database/models.py Z.524-540 (`ApiRate` — `__tablename__='api_rates'`, `__table_args__` nur UniqueConstraint + comment, KEIN {'schema':'crm'} → PUBLIC-Tabelle)
    - database/db.py Z.29-49 (der cf5de6d-Listener, der in Task 1 ENTFERNT wird — DESHALB funktioniert `Base.metadata.create_all` heute, weil er crm/training auf die frische fresh_engine-Connection ATTACHed; nach Entfernung wirft create_all "unknown database crm")
  </read_first>
  <behavior>
    - Nach Listener-Entfernung (Task 1) baut der Test nur noch die PUBLIC `api_rates`-Tabelle (kein crm/training),
      sodass `create_all` nicht mehr "unknown database crm" wirft → kein Collection-/Setup-Error mehr.
    - Die NOT-NULL-last_checked_at-Regression-Assertion (test_seed_rows_have_last_checked_at) bleibt intakt auf
      echten SQLite-Writes — es bleibt ein Runtime-Write-Test (CLAUDE.md Test-Qualitaets-Regel), KEIN Source-Presence-Check.
    - Der Test bleibt DSN-unabhängig (in-memory SQLite), läuft also IM Gate (DATABASE_URL=postgres) UND außerhalb —
      er wird NICHT geskippt und NICHT an TEST_DATABASE_URL gekoppelt.
    - SEED_ROWS, die 3 INSERT-Tests + die 8-rows-Assertion bleiben UNVERÄNDERT.
  </behavior>
  <action>
    Option B — den create_all-Aufruf auf die public ApiRate-Tabelle scopen (Begründung unten). KONKRET in
    `tests/test_08_14_apirate_seed.py`, NUR in der `fresh_engine`-Fixture (Z.14-20):

    1. Importzeile in der Fixture ändern: `from database.models import Base` → `from database.models import ApiRate`.
    2. `Base.metadata.create_all(engine)` → `ApiRate.__table__.create(engine)` (baut NUR die public `api_rates`-
       Tabelle, kein crm/training → kein "unknown database crm" mehr nach Listener-Entfernung).
    3. Falls `Base` danach in der Datei nirgends mehr genutzt wird (ist es nicht — der Import steht nur lokal in
       der Fixture), bleibt der `ApiRate`-Import die einzige Modell-Referenz. Keinen ungenutzten `Base`-Import
       stehen lassen.
    4. ALLES ANDERE unverändert: `engine = create_engine('sqlite:///:memory:')` bleibt (in-memory SQLite,
       DSN-unabhängig), SEED_ROWS (Z.23-32) bleibt, die 4 Tests in TestApiRateSeed (INSERT/COUNT/idempotent/
       models-present) bleiben Wort für Wort, die 8-rows-Assertion bleibt.

    **Option-B-Rationale (im SUMMARY festhalten):** `ApiRate` ist eine PUBLIC-Tabelle (kein {'schema':'crm'},
    models.py:526-530) — eine NOT-NULL-Seed-Regression auf einer public Tabelle ist KEINE crm/training-Emulation.
    Req-6 zielt auf die crm/training-EMULATION (das False-Green), NICHT auf JEDE SQLite-Nutzung. Ein einzelner
    public-Tabellen-SQLite-Regressionstest bleibt daher legitim auf in-memory SQLite: schnell + DSN-unabhängig
    (läuft im Gate UND lokal, nicht nur wenn ein PG-DSN gesetzt ist) + echte Runtime-Write-Assertion. Ein Port auf
    PG wurde VERWORFEN: er fügt eine skip-when-DSN-missing-Kopplung hinzu für null Korrektheits-Gewinn (die
    Regression reproduziert identisch auf SQLite, keine crm/RLS/PG-spezifische Semantik). Hinweis: dieser Test
    nutzt eine FRISCHE in-memory SQLite-Engine pro Lauf → KEINE Base-Seed-/Persistenz-Falle (im Gegensatz zu den
    nerve_test-Tests); die 8-rows-Assertion ist hier sicher, weil sie nur die selbst-geseedeten Rows zählt.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "Base.metadata.create_all|ApiRate.__table__.create" tests/test_08_14_apirate_seed.py'; echo "EXIT=$?"  # erwartet: Base.metadata.create_all WEG, ApiRate.__table__.create PRESENT. Voll-Beleg: Gate-Lauf zeigt test_08_14 PASSED (nicht error/SKIPPED), kein "unknown database crm".</automated>
  </verify>
  <done>
    test_08_14_apirate_seed.py collected + läuft GRÜN im Gate mit dem entfernten ATTACH-Listener — kein
    "unknown database crm". `grep Base.metadata.create_all tests/test_08_14_apirate_seed.py` → leer;
    `grep ApiRate.__table__.create ...` → Treffer. Der Test bleibt in-memory SQLite (DSN-unabhängig, nicht
    geskippt) und eine echte NOT-NULL-Runtime-Regression (keine Source-Presence). Die 4 Tests (8-rows,
    last_checked_at-NOT-NULL, idempotent, models-present) passen unverändert.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: test_tenant_orgs.py auf PG-Trigger-Semantik portieren (F1) + ID-Scoping aller count/all-Assertions (Delta-Review-2 BLOCKER)</name>
  <read_first>
    - tests/test_tenant_orgs.py (ganze Datei — Docstring Z.9-21 SQLite-vs-PG-Boundary; Helpers `_seed_tenant_orgs` Z.38-46, `_backfill_calls_tenant_id` Z.48-56; die 6 Tests Z.59-141, speziell `test_seed_one_row_per_org` Z.59-67 mit der GLOBALEN `query(TenantOrg).count() == query(Organisation).count() == 3`-Assertion Z.65, `test_dualwrite_trigger_fires` Z.70-82 mit manuellem TenantOrg-add Z.77, `test_dualwrite_idempotent` Z.85-94 mit dem ECHTEN Duplikat-IntegrityError-Test)
    - tests/conftest.py (NACH Plan 01: db_session bindet das MODUL-SessionLocal an nerve_test um — der PG-Pfad für diesen Test)
    - **tests/conftest.py — Plan 01 Task 4 Base-Seed (KRITISCH für Delta-Review-2):** der session-scoped Base-Seed committet Org id=1 + die vom Trigger trg_mk_tenant_org erzeugte tenant_org + User id=1 in das PERSISTENTE nerve_test. Plus etwaige generische [PGTEST-GENERIC]-Tenants aus `_seed_test_tenant`. DIESE committeten Rows sind beim Lauf von test_tenant_orgs bereits präsent → JEDE globale, ungefilterte count()/all() in test_tenant_orgs sieht sie → poisoned.
    - tests/test_rls_isolation.py Z.33-54 (Trigger-tenant_orgs-Read-Back-Muster: INSERT organisations → SELECT tenant_orgs.id zurück — das ist die PG-Semantik, die test_tenant_orgs ERWARTEN muss) + Z.101-116 (POST-yield Best-Effort-Teardown, MED-1)
    - alembic/versions/*0011* (Migration 0011 — der AFTER-INSERT-Trigger `trg_mk_tenant_org` auf organisations + das UNIQUE(legacy_org_id) auf tenant_orgs)
  </read_first>
  <behavior>
    - test_tenant_orgs.py läuft gegen nerve_test-PG (db_session aus Plan 01) statt in-memory SQLite. Es ERWARTET
      jetzt den AFTER-INSERT-Trigger `trg_mk_tenant_org`: ein `INSERT organisations` erzeugt die tenant_orgs-Row
      AUTOMATISCH. Der Test liest die auto-erzeugte `tenant_orgs.id` zurück (Trigger-Read-Back-Muster,
      test_rls_isolation.py:33-54) statt Python-seitig eine eigene TenantOrg-Row zu inserten.
    - KEIN Python-seitiges Doppel-Seed mehr: `_seed_tenant_orgs` (Python-INSERT pro Org) entfällt bzw. wird zum
      No-op/Read-Back, und die manuellen `db_session.add(TenantOrg(...))` in test_dualwrite_trigger_fires werden
      durch ein Zurücklesen der vom Trigger erzeugten Row ersetzt — sonst UNIQUE(legacy_org_id)-Kollision auf PG.
    - **ID-SCOPING (Delta-Review-2 BLOCKER, F1-Sibling):** JEDE count()/all()-Assertion UND die Helper
      `_seed_tenant_orgs`/`_backfill_calls_tenant_id` werden auf die vom TEST SELBST erzeugten Org/User/TenantOrg-IDs
      gescoped — NIEMALS global. Der persistente Base-Seed (Plan 01 Task 4: Org id=1 + dessen Trigger-tenant_org +
      User id=1) und etwaige [PGTEST-GENERIC]-Tenants dürfen NICHT in die Assertions einfließen. Konkret:
      `test_seed_one_row_per_org` (Z.65) wird von `query(TenantOrg).count() == query(Organisation).count() == 3`
      (global) auf `query(Organisation).filter(Organisation.id.in_([a.id,b.id,c.id])).count() == 3` UND
      `query(TenantOrg).filter(TenantOrg.legacy_org_id.in_([a.id,b.id,c.id])).count() == 3` umgestellt, wo a,b,c die
      3 vom Test erzeugten Orgs sind. `legacy_ids` wird NUR aus diesen 3 Orgs gebaut. `_seed_tenant_orgs`/`_backfill`
      iterieren NUR über die test-eigenen Orgs/Users (übergebene IDs oder Filter), nicht `query(...).all()` global.
    - Die ECHTE Idempotenz-Assertion bleibt: `test_dualwrite_idempotent` erwartet WEITERHIN einen IntegrityError
      auf einen WIRKLICHEN Duplikat-Insert (ein zweiter TenantOrg mit gleichem legacy_org_id, manuell forciert) —
      das testet die UNIQUE-Constraint, auf die der Trigger's ON CONFLICT baut. Dieser eine erwartete IntegrityError
      bleibt unverändert valide.
    - Alle Assertions bleiben echte Row-Reads (count/legacy_id-Liste/backfill-join-Ergebnis) — KEINE Source-Presence.
    - Deterministischer Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except NACH yield, reverse-FK:
      tenant_orgs → organisations bzw. calls → users → orgs), getaggte/test-eigene Rows, analog test_rls_isolation.py:101-116 (MED-1).
    - SKIP wenn TEST_DATABASE_URL fehlt (kein sqlite-Fallback — der Test ist jetzt trigger-/PG-abhängig).
  </behavior>
  <action>
    Portiere `tests/test_tenant_orgs.py` von der SQLite-no-trigger-Annahme auf die nerve_test-PG-Trigger-Semantik
    UND scope ALLE count/all-Assertions + Helper auf test-eigene IDs (Delta-Review-2 BLOCKER). KONKRET:

    1. **Trigger ERWARTEN statt Python-doppeln:** Auf nerve_test erzeugt der AFTER-INSERT-Trigger
       `trg_mk_tenant_org` (Migration 0011) bei jedem `INSERT organisations` automatisch die passende
       tenant_orgs-Row. Daher:
       - `_mk_org` (Z.31-35) bleibt (INSERT organisations), aber danach wird die tenant_orgs-Row vom Trigger
         ZURÜCKGELESEN (SELECT tenant_orgs.id WHERE legacy_org_id = org.id — test_rls_isolation.py:33-54-Muster),
         NICHT manuell ge-insertet. Gib die erzeugte Org (mit .id) an den Aufrufer zurück, damit der Test die
         test-eigenen IDs sammeln kann.
       - `_seed_tenant_orgs` (Z.38-46): entfällt als Python-Seed (der Trigger seedet). Falls die Tests die
         Funktion strukturell brauchen, mach sie zu einem reinen Read-Back/No-op (sie darf KEINE neue TenantOrg-
         Row inserten — sonst Doppel + UNIQUE-Kollision). **WICHTIG (Delta-Review-2):** wenn die Funktion intern
         `query(Organisation).all()` iteriert, ÄNDERE das auf eine ÜBERGEBENE Liste der test-eigenen Orgs (oder
         `filter(Organisation.id.in_(own_ids))`) — sie darf die persistente Base-Seed-Org id=1 NICHT mehr sehen.
    2. **ID-SCOPING der count-Assertion (Delta-Review-2 BLOCKER, der HARTE Failure-Punkt):**
       - `test_seed_one_row_per_org` (Z.59-67): erzeuge die 3 Test-Orgs explizit (a,b,c = `_mk_org(...)` ×3) und
         sammle ihre IDs in einer lokalen Liste `own_org_ids = [a.id, b.id, c.id]`. Ersetze die GLOBALE Assertion
         Z.65 `query(TenantOrg).count() == query(Organisation).count() == 3` durch ZWEI GEFILTERTE Assertions:
         `query(Organisation).filter(Organisation.id.in_(own_org_ids)).count() == 3` UND
         `query(TenantOrg).filter(TenantOrg.legacy_org_id.in_(own_org_ids)).count() == 3`.
         Die `legacy_ids`-Liste-Assertion baut NUR aus `own_org_ids` (read-back der Trigger-Rows der test-eigenen
         Orgs) — NICHT aus `query(TenantOrg).all()` global. Begründung: der persistente Base-Seed (Plan 01 Task 4:
         Org id=1 + dessen Trigger-tenant_org) + generische Tenants sind bereits in nerve_test → eine globale
         count wäre > 3 → garantierter False-Red → fail-closed Gate blockt jeden Deploy.
    3. **test_dualwrite_trigger_fires** (Z.70-82): ersetze den manuellen `db_session.add(TenantOrg(...))` (Z.77)
       durch ein Zurücklesen der vom Trigger bei `_mk_org("Brand New GmbH")` erzeugten Row; filtere den Read-Back
       auf die test-eigene Org-ID (`filter(TenantOrg.legacy_org_id == new_org.id)`); asserte `len(rows) == 1` +
       `rows[0].name == "Brand New GmbH"` auf der TRIGGER-Row (das testet den Dual-Write jetzt ECHT auf PG, nicht
       mehr nur als Python-Analog). KEINE globale count.
    4. **Echte Idempotenz BEHALTEN:** `test_dualwrite_idempotent` (Z.85-94) — der erwartete IntegrityError auf
       einen FORCIERTEN zweiten TenantOrg mit gleichem legacy_org_id bleibt unverändert (er testet die
       UNIQUE-Constraint, die der Trigger's ON CONFLICT braucht). Hinweis: auf PG existiert nach `_mk_org` bereits
       die Trigger-Row, also reicht EIN zusätzlicher manueller Duplikat-Insert um den IntegrityError zu provozieren
       (statt zwei). Passe die Setup-Zeilen so an, dass genau ein echter Duplikat-Insert den erwarteten Error wirft.
    5. **Backfill-Tests** (`test_calls_tenant_id_backfilled` Z.97-111, `test_no_orphan_calls_after_backfill`
       Z.121-141): die tenant_orgs-Rows kommen vom Trigger (über `_mk_org`); `_backfill_calls_tenant_id` (Python-
       Analog der Migrations-0011-Step-4-UPDATE-Join) bleibt als Logik-Test gültig, liest die Trigger-tenant_orgs.id
       als Bridge-Ziel — ABER NUR über die test-eigenen Orgs/Users/Calls (Delta-Review-2): falls
       `_backfill_calls_tenant_id` intern `query(User).all()` / `query(TenantOrg).all()` iteriert, scope das auf die
       test-eigenen IDs (übergebene Liste oder `filter(...in_(own_ids))`), damit die persistenten Base-Seed-User/-Org
       (id=1) NICHT in den Backfill-Join/orphan_count einfließen. Assertions (call.tenant_id == tenant.id;
       orphan_count über NUR die test-eigenen Calls == 0) bleiben echte Row-Reads. `test_calls_tenant_id_stays_nullable`
       (Z.114-118) bleibt (Column-Constraint-Assertion via sa_inspect — OK).
    6. **Teardown** in der Fixture-POST-yield-Sektion (MED-1, try/except NACH yield analog
       test_rls_isolation.py:101-116): reverse-FK DELETE der test-eigenen Rows (calls → users → tenant_orgs →
       organisations bzw. die im Test angelegten). Läuft auch bei Assertion-Fehler. KEIN literales try...finally
       im Test-Body — die POST-yield-Platzierung ist das Mittel. Der Base-Seed (id=1) wird NICHT angefasst.
    7. **Docstring aktualisieren:** die SQLite-vs-PG-Boundary-Note (Z.9-21) umschreiben — der Test läuft jetzt
       GEGEN PG und übt den Trigger `trg_mk_tenant_org` + UNIQUE(legacy_org_id) WIRKLICH aus (nicht mehr nur als
       SQLite-Analog), und alle Assertions sind auf test-eigene IDs gescoped (persistentes nerve_test + Base-Seed).
       Das ist ein SQLite-Annahme-Test (wie test_08_14), der auf PG portiert wird, NICHT geskippt.
    8. **Anti-False-Green (CLAUDE.md):** alle Assertions bleiben echte DB-Row-Reads (gefilterte count, legacy_id-Liste,
       backfill-join, erwarteter IntegrityError) — KEINE inspect.getsource/hasattr/grep-on-source.

    **F1-Rationale (im SUMMARY festhalten):** test_tenant_orgs berührt NUR public.* (TenantOrg/Organisation/
    User/Call), ZERO crm — deshalb war es NIE ein gültiger RLS-Proof (das war eine falsche Annahme in Plan 01,
    dort entfernt; der echte RLS-Tripwire ist tests/test_rls_generic_smoke.py aus Plan 01). Auf echtem PG bricht
    es aus ZWEI Gründen: (F1) Python-Doppel-Seed kollidiert mit der Trigger-Row; (Delta-Review-2) globale count
    sieht den persistenten Base-Seed (Plan 01 Task 4) → > 3 → False-Red. Es ist ein SQLite-Annahme-Test (wie
    test_08_14), der auf PG-Trigger-Semantik portiert + auf test-eigene IDs gescoped — nicht geskippt — werden
    MUSS, sonst Gate ROT.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy4.log | grep -E "test_tenant_orgs|test_seed_one_row_per_org|test_dualwrite|test_calls_tenant_id|PASSED|passed|failed|error"; echo "EXIT=$?"  # F1+Delta-Review-2: test_tenant_orgs PASSED gegen nerve_test (Trigger-Semantik, kein UNIQUE-Kollisions-Error, count auf test-eigene IDs gefiltert == 3 trotz persistentem Base-Seed).</automated>
  </verify>
  <done>
    test_tenant_orgs.py läuft gegen nerve_test-PG und ERWARTET den AFTER-INSERT-Trigger `trg_mk_tenant_org`:
    `_mk_org` liest die vom Trigger auto-erzeugte tenant_orgs-Row zurück (kein Python-Doppel-Seed, kein manueller
    TenantOrg-Insert in test_dualwrite_trigger_fires) → kein UNIQUE(legacy_org_id)-Kollisions-Error mehr. ALLE
    count/all-Assertions UND die Helper `_seed_tenant_orgs`/`_backfill_calls_tenant_id` sind auf die test-eigenen
    Org/User/TenantOrg-IDs gescoped (Delta-Review-2): `test_seed_one_row_per_org` filtert
    `Organisation.id.in_(own_org_ids)` / `TenantOrg.legacy_org_id.in_(own_org_ids)` == 3 statt global — der
    persistente Base-Seed (Plan 01 Task 4: Org id=1 + Trigger-tenant_org + User id=1) + generische Tenants
    poisonen die Assertions NICHT mehr. Die echte Idempotenz-Assertion (erwarteter IntegrityError auf einen
    forcierten Duplikat-Insert) bleibt valide. Backfill-Tests lesen die Trigger-tenant_orgs.id als Bridge über
    NUR die test-eigenen Rows. Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, analog
    test_rls_isolation.py:101-116) → kein State-Leak, Base-Seed unangetastet. Im Gate-Lauf erscheint
    test_tenant_orgs als PASSED (nicht error/SKIPPED). Alle Assertions sind echte Row-Reads (keine Source-Presence).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: FK-Delta test_postcall_split — eigenen Org/User-id=1-Insert entfernen, Base-Seed konsumieren</name>
  <read_first>
    - tests/test_postcall_split.py (ganze Datei — speziell `_seed_user_and_conv` Z.24-46: nutzt `db = get_session()` + `db.add(Organisation(id=org_id, name='Test-Org'))` / `db.add(User(id=user_id, org_id=org_id, ...))`, MIT bestehendem idempotentem Guard `if db.query(Organisation).filter_by(id=org_id).first() is None` Z.32 bzw. dem User-Guard Z.35 — plus die Call/outcome-Split-Assertions)
    - tests/conftest.py (NACH Plan 01 Task 4: der Session-Scope Base-Seed Org(id=1)+User(id=1) — der Vertrag, den dieser Test JETZT konsumiert statt selbst die Test-Org id=1 zu inserten)
  </read_first>
  <behavior>
    - test_postcall_split self-seedet seine Test-Org/-User aktuell in `_seed_user_and_conv` (Z.24-46) via `get_session()` + `db.add(Organisation(id=1, name='Test-Org'))` / `db.add(User(id=1, ...))`, beide bereits HINTER einem idempotenten `... .first() is None`-Guard (Z.32/Z.35). Dieser Guard verhindert auf der persistenten nerve_test schon eine harte PK-Doppel-IntegrityError (der Insert wird uebersprungen, wenn id=1 vom Base-Seed bereits da ist).
    - Die Aenderung ist daher eine Klarheits-/Konsistenz-Verbesserung (KEIN harter break-fix): der Test soll die EINE Base-Org/-User (id=1) aus dem Plan-01-Base-Seed KONSUMIEREN, statt parallel eine zweite „Test-Org"-Definition (Name 'Test-Org' vs Base-Name '[PGTEST-BASE] org') fuer dieselbe id=1 zu fuehren. Zwei Quellen, die beide „die Test-Org id=1" meinen, sind verwirrend und drift-anfaellig — eine reicht.
    - Die echten Call/outcome-Split-Assertions bleiben unveraendert (Runtime-Integration, kein Source-Presence). `_seed_user_and_conv` legt WEITERHIN den ConversationLog an (Z.41-43) — nur die Org/User-Parent-Inserts entfallen zugunsten des Base-Seeds.
  </behavior>
  <action>
    1. In `_seed_user_and_conv` (Z.24-46): ENTFERNE die Org/User-Self-Inserts —
       konkret den `if db.query(Organisation).filter_by(id=org_id).first() is None: db.add(Organisation(id=org_id, name='Test-Org')); db.commit()`-Block (Z.32-34) und den analogen
       `db.add(User(id=user_id, org_id=org_id, ...))`-Block (Z.35-40). Der Plan-01-Base-Seed (Task 4) liefert
       Org id=1 + User id=1 bereits session-scoped. Der bestehende idempotente Guard (`... .first() is None`)
       hat zwar bereits einen harten PK-Doppel-Insert verhindert — die Entfernung ist die saubere Konsequenz:
       EINE Quelle der Wahrheit fuer die Base-Org/-User id=1 (kein paralleles 'Test-Org'-Duplikat fuer dieselbe id).
    2. Falls der Test die Org/User-Objekte als lokale Variablen braucht, hole sie READ-ONLY via
       `db.query(Organisation).filter_by(id=org_id).first()` / `db.query(User).filter_by(id=user_id).first()`
       (bzw. `db.get(Organisation, org_id)`) — Read, kein Insert. Der `ConversationLog`-Insert (Z.41-43) bleibt.
    3. ALLE Call-Erstellungs- und outcome-Split-Assertions bleiben Wort fuer Wort — nur die Org/User-Parent-Seeds entfallen.
    4. Anti-False-Green (CLAUDE.md): die Assertions bleiben echte Row-/Return-Checks auf den Split — KEINE
       inspect.getsource/hasattr/grep-on-source.
    Rationale (#3, W2-praezisiert): der Test nutzt `get_session()` + `db.add(Organisation(id=1,...))` (NICHT `db_session.add`)
    und HAT bereits einen idempotenten `.first() is None`-Guard (Z.32/35) — „self-inserting id=1" wuerde also nicht hart
    an einem PK-Doppel brechen. Die Aenderung CONSUMET den Base-Seed statt eine zweite Test-Org-Definition fuer dieselbe
    id=1 zu fuehren: Klarheit/Konsistenz (eine Quelle), kein harter break-fix.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy5.log | grep -E "test_postcall_split|passed|failed|error|UniqueViolation|IntegrityError"; echo "EXIT=$?"  # test_postcall_split PASSED gegen nerve_test (kein id=1-Doppel-Insert-Konflikt mit dem Base-Seed).</automated>
  </verify>
  <done>
    `_seed_user_and_conv` in test_postcall_split.py inserted KEINE eigene Organisation(id=1)/User(id=1) mehr
    (die `get_session()`+`db.add(Organisation/User)`-Bloecke Z.32-40 entfernt), sondern konsumiert den
    Plan-01-Base-Seed (id=1) read-only; der ConversationLog-Insert (Z.41-43) bleibt. Der bestehende idempotente
    `.first() is None`-Guard hatte schon einen harten PK-Doppel verhindert — die Aenderung ist die saubere
    Konsequenz (eine Quelle fuer die Base-Org/-User id=1). Die Call/outcome-Split-Assertions bleiben echte
    Row-/Return-Checks; im Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 6: FK-Delta test_ewb_rate_api — unique email pro Run, trigger-aware Org (kein manueller tenant_orgs)</name>
  <read_first>
    - tests/test_ewb_rate_api.py (ganze Datei — der Org->User->ConvLog->ObjectionEvent-Self-Seed + die rate-API-Assertions)
    - tests/test_rls_isolation.py:33-54 (Trigger-Read-Back: INSERT organisations -> tenant_orgs.id vom Trigger; kein manueller tenant_orgs-Insert) + Z.101-116 (POST-yield Best-Effort-Teardown, MED-1)
    - database/models.py Z.65-135 (User.email UNIQUE NOT NULL — die Kollisions-Quelle auf persistenter PG)
  </read_first>
  <behavior>
    - test_ewb_rate_api self-seedet weiterhin seine eigene Org->User->ConversationLog->ObjectionEvent-Kette (PUBLIC-Tabellen, KEIN crm — Claudian bestaetigt), laeuft aber jetzt gegen die persistente nerve_test: deshalb (a) eine UNIQUE email pro Run (sonst users.email-Kollision wenn der Test mehrfach/neben anderen laeuft) und (b) die Org wird via Trigger trg_mk_tenant_org versorgt — KEIN doppelter manueller tenant_orgs-Insert.
    - Die ObjectionEvent/rate-Assertions bleiben echte Runtime-Checks.
  </behavior>
  <action>
    1. UNIQUE email pro Run: ersetze die hardcodete Test-Email durch `f"ewb-rate-{uuid.uuid4().hex[:8]}@nerve.local"`
       (bzw. eine eindeutige Variante) — sonst wirft users.email UNIQUE NOT NULL eine IntegrityError auf der
       persistenten nerve_test, wenn der Test neben anderen email-seedenden Tests laeuft. (`import uuid` ergaenzen.)
    2. Org-Seed trigger-aware: der `INSERT organisations` feuert trg_mk_tenant_org -> tenant_orgs entsteht
       automatisch. Falls der Test bisher MANUELL eine TenantOrg-Row inserted -> entfernen (sonst
       UNIQUE(legacy_org_id)-Bruch, F1-Lektion). Falls er tenant_orgs NICHT braucht (ObjectionEvent/ConvLog
       sind public, kein crm-FK) -> einfach NICHT doppelt inserten.
    3. ConversationLog/ObjectionEvent/rate-Assertions bleiben Wort fuer Wort (PUBLIC, kein crm — kein
       set_current_tenant noetig).
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       objection_event -> conversation_log -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), damit
       die self-geseedeten Rows nicht in nerve_test leaken.
    5. Anti-False-Green (CLAUDE.md): rate-Assertions bleiben echte Response-/Row-Checks — kein Source-Presence.
    Rationale (#8): bricht nur an (a) trg_mk_tenant_org-Doppel + (b) users.email UNIQUE auf persistenter PG.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy6.log | grep -E "test_ewb_rate_api|passed|failed|error|UniqueViolation|legacy_org_id"; echo "EXIT=$?"  # test_ewb_rate_api PASSED gegen nerve_test (unique email, kein tenant_orgs-Doppel).</automated>
  </verify>
  <done>
    test_ewb_rate_api.py nutzt eine UNIQUE email pro Run (kein users.email-UNIQUE-Bruch), seedet die Org
    trigger-aware (kein manueller tenant_orgs-Doppel-Insert -> kein UNIQUE(legacy_org_id)-Bruch); die
    ObjectionEvent/rate-Assertions bleiben echte Runtime-Checks; Teardown in der POST-yield-Sektion; im
    Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 7: FK-Delta test_profile_editor_validation — Parents present + Tenant-Kontext (falls Route crm liest)</name>
  <read_first>
    - tests/test_profile_editor_validation.py (ganze Datei — der client-Fixture-Self-Seed Org/User/Profile + die Validation-Assertions)
    - tests/conftest.py (NACH Plan 01: client bindet das MODUL-SessionLocal um + set_current_tenant; Base-Seed Org/User id=1 verfuegbar)
    - database/models.py Z.137+ (Profile — FK auf org/user; profiles ist PUBLIC, kein crm — Claudian bestaetigt KEINE RLS-Luecke)
  </read_first>
  <behavior>
    - test_profile_editor_validation self-seedet Org/User/Profile via die client-Fixture; gegen die persistente nerve_test muessen die org/user-Parents present sein (entweder den Base-Seed id=1 konsumieren ODER korrekt selbst seeden) und — falls die getestete Route crm beruehrt — der Tenant-Kontext gesetzt sein (die client-Fixture aus Plan 01 ruft set_current_tenant bereits auf).
    - Claudian-Befund: profiles ist PUBLIC, KEINE crm-RLS-Luecke — der Tenant-Kontext ist nur relevant falls die Route selbst crm liest.
    - Die Validation-Assertions bleiben echte Response-/Row-Checks.
  </behavior>
  <action>
    1. Parents present sicherstellen: entweder den Plan-01-Base-Seed (Org id=1 + User id=1) konsumieren
       (`db_session.get(...)` / Profile mit org_id=1,user_id=1 anlegen) ODER — wenn der Test eigene Org/User
       braucht — diese mit UNIQUE email (uuid-suffixed) korrekt selbst seeden (kein id=1-Doppel mit dem
       Base-Seed). Profile-FK-Ziele (org_id/user_id) muessen auf existierende Parents zeigen.
    2. Tenant-Kontext: die client-Fixture aus Plan 01 ruft set_current_tenant bereits auf — falls die
       Profile-Editor-Route crm liest, ist der Kontext damit gesetzt. (Claudian: profiles selbst ist public,
       keine zusaetzliche RLS-Behandlung noetig.)
    3. Die Validation-Assertions (gueltige/ungueltige Profile-Eingaben -> erwartete Response/Fehlermeldung)
       bleiben Wort fuer Wort.
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       profile -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), fuer selbst-geseedete Rows.
    5. Anti-False-Green (CLAUDE.md): echte Response-/Row-Assertions, kein Source-Presence.
    Rationale (#9): braucht org/user-Parents present + ggf. Tenant-Kontext; profiles public, keine RLS-Luecke.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy7.log | grep -E "test_profile_editor_validation|passed|failed|error|ForeignKey|IntegrityError"; echo "EXIT=$?"  # test_profile_editor_validation PASSED gegen nerve_test (Parents present, ggf. Tenant-Kontext).</automated>
  </verify>
  <done>
    test_profile_editor_validation.py hat die org/user-Parents present (Base-Seed konsumiert ODER korrekt
    selbst geseedet mit unique email), der Tenant-Kontext ist ueber die Plan-01-client-Fixture gesetzt (falls
    Route crm liest); die Validation-Assertions bleiben echte Response-/Row-Checks; Teardown in der
    POST-yield-Sektion; im Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 8: test_ft_seed HONEST gegen schema-only nerve_test laufen lassen — echte Fehlerursache verifizieren, NICHT eine vermutete maskieren</name>
  <read_first>
    - tests/test_ft_seed.py (ganze Datei — `test_prompt_seed` Z.14-21 ruft `_seed_prompt_versions(db_session)` SELBST und prueft je-Modul row+version+prompt_text; `test_seed_idempotent` Z.24-30 ruft `_seed_prompt_versions(db_session)` ZWEIMAL und asserted `count == 4` nach jedem Aufruf — der Test seedet also SELBST, er erwartet KEINE vor-existierenden Rows)
    - app.py — `_seed_prompt_versions` (idempotenter check-then-insert von EXAKT 4 aktiven Modulen: assistant_live/coaching_live/objection_trigger/training_persona; `is_active=True`, `version='v1.0.0'`). EXAKTE Zeile beim Lesen verifizieren (grep `def _seed_prompt_versions`).
    - alembic/versions/* — VERIFIZIERT (grep `INSERT INTO prompt_versions` / `bulk_insert.*prompt`): KEINE Migration seedet prompt_versions-DATEN; 0015 setzt nur COMMENT/Schild. nerve_test wird per `pg_dump --schema-only` (ZERO data rows) gebaut -> prompt_versions ist beim Test-Start LEER.
    - .planning/.../08.23.2.PGTEST-SPEC.md (Klasse-E / Stufe-2 pre-existing failure: test_ft_seed ist der bekannte rote Stufe-2-Test, dessen WIRKLICHE Ursache NICHT etabliert ist — NICHT out-of-scope wegmaskieren)
  </read_first>
  <behavior>
    - KORREKTUR der frueheren Annahme (W1, pre-execute 2026-06-15): die alte Diagnose "alembic pre-seedet prompt_versions -> `assert count == 4` bricht" ist FALSCH. nerve_test ist SCHEMA-ONLY (`pg_dump --schema-only`, ZERO data — grep-verifiziert: keine Migration seedet prompt_versions-Daten). `_seed_prompt_versions` ist idempotenter check-then-insert von EXAKT 4 Modulen, und der Test ruft ihn SELBST auf der leeren Tabelle auf -> `count == 4` haelt auf der schema-only DB sehr WAHRSCHEINLICH (kein Pre-Seed-Konflikt). test_ft_seed ist der bekannte Stufe-2/Klasse-E pre-existing failure, dessen ECHTE Ursache NICHT etabliert ist.
    - HINWEIS (Delta-Review-2-Konsistenz): test_ft_seed asserted `count == 4` auf prompt_versions — das ist eine GLOBALE count. Sie ist HIER NUR sicher, weil (a) KEINE Migration prompt_versions seedet (grep-verifiziert) und (b) der Base-Seed (Plan 01 Task 4) NUR organisations/tenant_orgs/users befuellt, NICHT prompt_versions, UND (c) kein anderer Test auf eigener Session prompt_versions committet. Falls eine dieser drei Annahmen am Execute NICHT haelt (Gate zeigt count != 4 wegen vor-existierender Rows), ist das genau der globale-count-vs-persistent-Hazard -> dann auf test-eigene/baseline-delta scopen (analog Task 4/Task 10), NICHT die Assertion blind aufweichen. Sonst bleibt die globale count==4 zulaessig.
    - DESHALB: KEINE presumptive count-on-empty-"Toleranz" einbauen. Erst die WIRKLICHE Ursache im Gate beobachten. Der Test soll genuin den Seed ueben (4 Module insert + je-Modul-Pruefung + Idempotenz), nicht durch eine aufgeweichte Assertion gruen-gefaerbt werden.
  </behavior>
  <action>
    1. **HONEST laufen lassen:** test_ft_seed gegen die schema-only nerve_test im Gate laufen lassen WIE ER IST
       (er seedet selbst via `_seed_prompt_versions(db_session)`, dann `count == 4` / je-Modul-Assertions). KEINE
       presumptive Aenderung an der Assertion VOR der Beobachtung — die alte "assert >=4 / expected-set"-Aufweichung
       (basierend auf der widerlegten Pre-Seed-Story) NICHT blind einbauen.
    2. **Tolerante Assertion NUR als bewusste Defensiv-Massnahme — und nur falls der Seed echt geuebt bleibt:**
       Eine tolerantere Form (`count >= 4` PLUS `EXPECTED_MODULES.issubset(present_modules)`, OHNE eigene
       Row-Inserts) ist NUR dann akzeptabel, wenn (a) der Gate-Lauf zeigt dass tatsaechlich Rows vor-existieren
       (was nach grep UNERWARTET waere — dann die Quelle finden, nicht zudecken — das ist der globale-count-vs-
       persistent-Hazard, vgl. Task 4/10) UND (b) der Test weiterhin `_seed_prompt_versions` aufruft und die
       je-Modul-Eigenschaften (version='v1.0.0', prompt_text>30) echt prueft. Wird sie eingebaut, im Test-Kommentar
       die BEOBACHTETE Ursache dokumentieren — nicht die vermutete.
    3. **Wenn test_ft_seed im Gate ROT ist:** den ECHTEN tatsaechlichen Fehler-Output (assert-Diff / Exception /
       Traceback) im SUMMARY VERBATIM festhalten. Ist es ein echter App-Bug (Klasse-E, SPEC-Boundary — z.B.
       `_seed_prompt_versions` verhaelt sich auf PG anders, ConversationLog-FK, JSONB-Cast, was-auch-immer) ->
       ESKALIEREN (eigene Bugfix-Phase), NICHT mit einer aufgeweichten Assertion maskieren/skippen.
    4. **Harte Regeln (unveraendert):** der Test inserted KEINE eigenen prompt_versions-Rows ueber
       `_seed_prompt_versions` hinaus; KEINE Source-Presence-Pruefung (inspect.getsource/grep-on-source) — die
       Assertion bleibt ein echter DB-Row-Read (count/Modul-Set/Feldwerte).
    Rationale (#10, W1-korrigiert): nicht einen VERMUTETEN Fehlermodus (count-on-empty gegen angeblich
    pre-seedete Rows) fixen — die WIRKLICHE Ursache am Execute verifizieren. Schema-only nerve_test + selbst-seedender
    Test => count==4 haelt wahrscheinlich; bleibt der Test rot, ist es ein anderer (echter) Bug -> eskalieren.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy8.log | grep -E "test_ft_seed|test_prompt_seed|test_seed_idempotent|passed|failed|error|assert"; echo "EXIT=$?"  # test_ft_seed gegen schema-only nerve_test: ENTWEDER PASSED (Seed uebt sauber, count==4 haelt) ODER der ECHTE Fehler-Output wird sichtbar -> im SUMMARY verbatim festhalten + eskalieren falls echter App-Bug (KEINE Aufweichung als Maskierung).</automated>
  </verify>
  <done>
    test_ft_seed laeuft im Gate gegen die schema-only nerve_test, seedet weiterhin selbst via
    `_seed_prompt_versions(db_session)` und prueft die 4 Module + Idempotenz als echte Row-Reads (keine
    Source-Presence). Die widerlegte Pre-Seed-Story ist NICHT als presumptive Aufweichung eingebaut. ENTWEDER der
    Test ist PASSED (count==4 haelt auf der leeren Tabelle), ODER der tatsaechliche Fehler-Output ist im SUMMARY
    verbatim dokumentiert und — falls echter App-Bug (Klasse-E) — eskaliert (nicht maskiert/geskippt). Eine
    tolerante Assertion existiert nur falls der Gate-Lauf vor-existierende Rows BEWIESEN hat (dann mit
    beobachteter Ursache kommentiert, globale-count-Hazard-konform) UND der Seed weiterhin echt geuebt wird.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 9: FK-Delta test_ab_stats — Base-Org present, _seed_ewb_scenarios braucht keinen extra Parent</name>
  <read_first>
    - tests/test_ab_stats.py (ganze Datei — der eigene org/user/conv/rating-Self-Seed + die A/B-Stats-Assertions)
    - tests/conftest.py (NACH Plan 01 Task 4: Base-Seed Org id=1 verfuegbar)
    - database/models.py (TrainingScenario.erstellt_von — nullable; daher braucht `_seed_ewb_scenarios` keinen extra User-Parent)
  </read_first>
  <behavior>
    - test_ab_stats self-seedet seine eigene org/user/conversation/rating-Kette; gegen die persistente nerve_test muss die Base-Org present sein (Plan-01-Base-Seed) und es ist zu verifizieren, dass `_seed_ewb_scenarios` keinen zusaetzlichen Parent braucht (TrainingScenario.erstellt_von ist nullable -> clean).
    - Minimale Aenderung: kein Re-Architecting, nur Base-Org-Praesenz sicherstellen + den nullable-erstellt_von-Pfad bestaetigen. Die A/B-Stats-Assertions bleiben echte Runtime-Checks.
    - Delta-Review-2-Check: falls die A/B-Stats-Aggregation eine count/all auf einer base-seed-/eigen-committenden Tabelle macht, auf test-eigene IDs scopen (sonst sieht sie Fremd-Rows). Falls die Aggregation bereits auf die test-eigene conversation/rating-Kette gefiltert ist, ist sie sicher.
  </behavior>
  <action>
    1. Base-Org present: stelle sicher dass die org/user-Parents present sind — entweder den Plan-01-Base-Seed
       (Org id=1 + User id=1) konsumieren ODER die self-geseedete Kette mit UNIQUE email (uuid-suffixed)
       korrekt anlegen (kein id=1-Doppel mit dem Base-Seed).
    2. `_seed_ewb_scenarios`-Pfad bestaetigen: TrainingScenario.erstellt_von ist nullable -> der Scenario-Seed
       braucht KEINEN extra User-Parent. Verifiziere das im read_first (models.py) und stelle sicher dass der
       Scenario-Seed keinen NOT-NULL-FK auf einen fehlenden Parent setzt. Minimale Aenderung — kein
       Re-Architecting.
    3. Die A/B-Stats-Assertions (rating-Aggregation/Split-Ergebnis) bleiben Wort fuer Wort echte Row-Reads. Falls
       eine Aggregation global zaehlt (statt auf die test-eigene Kette gefiltert), auf test-eigene IDs scopen
       (Delta-Review-2 — sonst poisonen Base-Seed/Fremd-Rows die Stats).
    4. Best-Effort-Teardown in der Fixture-POST-yield-Sektion (try/except nach yield, reverse-FK:
       rating -> conversation -> user -> org), analog test_rls_isolation.py:101-116 (MED-1), fuer self-geseedete Rows.
    5. Anti-False-Green (CLAUDE.md): echte Stats-/Row-Assertions, kein Source-Presence.
    Rationale (#11): nur Base-Org-Praesenz + nullable erstellt_von verifizieren; minimaler Eingriff.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy9.log | grep -E "test_ab_stats|passed|failed|error|ForeignKey|IntegrityError"; echo "EXIT=$?"  # test_ab_stats PASSED gegen nerve_test (Base-Org present, _seed_ewb_scenarios clean via nullable erstellt_von).</automated>
  </verify>
  <done>
    test_ab_stats.py hat die org/user-Parents present (Base-Seed konsumiert ODER unique self-seed), und es ist
    bestaetigt dass `_seed_ewb_scenarios` keinen extra Parent braucht (TrainingScenario.erstellt_von nullable);
    die A/B-Stats-Assertions bleiben echte Row-Reads (auf test-eigene IDs gescoped falls aggregierend); Teardown
    in der POST-yield-Sektion; im Gate-Lauf PASSED.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 10: test_cost_tracker:51 persistence-robust machen (Delta-Review-2 sibling — log_api_cost committet auf eigener Session)</name>
  <read_first>
    - tests/test_cost_tracker.py (ganze Datei — speziell `test_missing_rate_no_raise` Z.~45-55 mit der GLOBALEN `db_session.query(ApiCostLog).count() == 0`-Assertion Z.51; UND der frueher laufende `test_freeze_fx_on_write`, der via log_api_cost eine ApiCostLog-Row committet)
    - services/cost_tracker.py Z.~95-135 (`log_api_cost`: oeffnet eine EIGENE `_db_mod.SessionLocal()` + `db.commit()` Z.~99/132 — die geschriebene Row persistiert im nerve_test ueber Test-Grenzen, NICHT in der db_session-Fixture)
    - tests/conftest.py (NACH Plan 01 Task 4: Base-Seed User id=1 — DESHALB passiert test_freeze_fx_on_write jetzt (FK-solved) und committet die ApiCostLog-Row, die :51 vergiftet)
  </read_first>
  <behavior>
    - `test_missing_rate_no_raise` (Z.51) asserted `db_session.query(ApiCostLog).count() == 0`. Der INTENT ist:
      "unbekannter Provider -> log_api_cost schreibt NICHTS". Das ist eine valide Runtime-Assertion und bleibt
      Runtime (kein Source-Presence).
    - PROBLEM (Delta-Review-2 sibling): `log_api_cost` oeffnet seine EIGENE `_db_mod.SessionLocal()` und committet
      (services/cost_tracker.py:99/132). Der frueher laufende `test_freeze_fx_on_write` (jetzt passing, weil der
      Base-Seed user id=1 liefert) committet via log_api_cost eine ApiCostLog-Row -> sie PERSISTIERT im
      persistenten nerve_test (D-03 1x-Build). Beim Lauf von test_missing_rate_no_raise ist die globale
      `count() == 0` daher > 0 -> FAILS, OHNE dass der Intent verletzt ist (False-Red).
    - FIX: die Assertion persistence-robust machen OHNE den echten Intent zu maskieren ("unknown provider ->
      log_api_cost schreibt NICHTS NEUES"). Sie bleibt eine echte Runtime-Row-Assertion.
  </behavior>
  <action>
    Mach die `count() == 0`-Assertion in `test_missing_rate_no_raise` persistence-robust. WAEHLE die sauberere
    der zwei Optionen (Planner-Empfehlung: Option a, weil sie genau "kein NEUER Write durch DIESEN Call" prueft):

    a) **Baseline-Delta (empfohlen):** unmittelbar VOR dem `log_api_cost('unknown', ...)`-Call
       `before = db_session.query(ApiCostLog).count()` erfassen; nach dem Call asserten
       `db_session.query(ApiCostLog).count() == before`. Das prueft EXAKT den Intent ("der unknown-Call hat NICHTS
       geschrieben") unabhaengig davon, wie viele Rows der persistente nerve_test aus frueheren Tests bereits traegt.
    ODER
    b) **Provider-Filter:** `db_session.query(ApiCostLog).filter_by(provider='unknown').count() == 0` — prueft, dass
       fuer den unbekannten Provider KEINE Row geschrieben wurde (die persistente FX-Row aus test_freeze_fx_on_write
       hat einen ANDEREN provider und wird ausgefiltert).

    1. Ersetze die globale `db_session.query(ApiCostLog).count() == 0`-Assertion (Z.51) durch die gewaehlte Form.
       Setze einen kurzen Kommentar: `# persistence-robust (Delta-Review-2): nerve_test ist persistent (D-03);
       log_api_cost committet auf eigener Session -> Rows aus frueheren Tests persistieren. Baseline-Delta/Filter
       statt globaler count==0.`
    2. WICHTIG (Session-Sichtbarkeit): `log_api_cost` committet auf einer EIGENEN `_db_mod.SessionLocal()`-Session,
       NICHT auf db_session. Damit `db_session.query(ApiCostLog).count()` die ggf. von einem parallelen Pfad
       committeten Rows sieht, ggf. `db_session.expire_all()` / ein frisches Query nach dem Call verwenden (die
       Row ist committet, also in der DB sichtbar; bei Bedarf `db_session.rollback()`/`expire_all()` um den
       Snapshot zu aktualisieren). Das aendert NICHT den Intent — es stellt nur sicher, dass die Assertion den
       echten DB-Stand liest. NICHT die eigene SessionLocal von log_api_cost umbauen (das ist Code-under-test).
    3. Der echte Intent bleibt: der `log_api_cost('unknown', ...)`-Call wirft NICHT und schreibt NICHTS NEUES.
       KEINE Source-Presence (inspect.getsource/grep-on-source) — es bleibt ein echter Row-Count-Read.
    4. KEINE Aenderung an services/cost_tracker.py (Code-under-test) — nur der Test wird persistence-robust.
    Rationale (Delta-Review-2 sibling): identische Klasse wie test_tenant_orgs:65 — globale, ungefilterte count auf
    einer Tabelle, in die ein FRUEHERER Test (via log_api_cost, eigene Session) committet hat. Auf baseline-delta /
    provider-Filter gescoped -> persistence-robust, Intent erhalten.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy10.log | grep -E "test_cost_tracker|test_missing_rate_no_raise|test_freeze_fx_on_write|passed|failed|error"; echo "EXIT=$?"  # test_missing_rate_no_raise PASSED gegen persistentes nerve_test (baseline-delta/provider-Filter statt globaler count==0).</automated>
  </verify>
  <done>
    `test_missing_rate_no_raise` in test_cost_tracker.py asserted NICHT mehr global `query(ApiCostLog).count() == 0`,
    sondern persistence-robust (baseline-delta: `count() == before` um den unknown-Call herum, ODER
    `filter_by(provider='unknown').count() == 0`) mit dokumentiertem Kommentar. Der echte Intent ("unknown provider
    -> log_api_cost schreibt nichts Neues") bleibt eine echte Runtime-Row-Assertion (keine Source-Presence). Die
    von test_freeze_fx_on_write via log_api_cost (eigene SessionLocal) committete persistente ApiCostLog-Row
    vergiftet die Assertion nicht mehr. services/cost_tracker.py bleibt unveraendert (Code-under-test). Im Gate-Lauf PASSED.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Klasse-A-Test → nerve_test crm.* | portierte Tests schreiben crm-Rows als nerve_app (RLS engaged) |
| Code-Pfad → SQLite-Emulation | nach Entfernung darf KEIN aktiver Pfad SQLite-Schema-Emulation voraussetzen |
| test_tenant_orgs → nerve_test public.* + Trigger | der Test schreibt organisations und ERWARTET die Trigger-erzeugte tenant_orgs-Row (kein Python-Doppel) |
| Test-Assertion → persistentes nerve_test (D-03 1x-Build) | committete Rows (Base-Seed Plan 01 Task 4 + Code-under-test auf eigener Session, z.B. log_api_cost) akkumulieren; globale count/all-Assertions sind dadurch False-Red-anfaellig |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-11 | Denial | ATTACH-Listener entfernt → Klasse-A-Tests werfen "unknown database crm" (Collection-Error) | mitigate | Req-6 + Port im SELBEN Plan/Wave (Wave-Kopplung); Tests gegen nerve_test-PG portiert bevor/während Listener-Entfernung |
| T-PGTEST-12 | Information Disclosure | portierte crm-Tests ohne Tenant-Kontext ODER frische sessionmaker (Hook feuert nicht) → RLS fail-closed 0 Zeilen ODER BYPASSRLS-Umgehung | mitigate | set_current_tenant(TEST_TENANT_UUID) + tenant_orgs-Seed (D-05); MODUL-SessionLocal-Umbindung (Plan-01-Vorbild) damit der RLS-Hook feuert; nerve_app rolbypassrls=f; keine Superuser-Rolle |
| T-PGTEST-13 | Tampering | Test schlägt mit AssertionError fehl BEVOR der reverse-FK-Teardown läuft (Teardown NICHT in der POST-yield-Sektion) → geseedete crm/tenant_orgs-Rows leaken in nerve_test → State-Leakage für nachfolgende Tests (gleiche Connection) → False-Green/False-Red Folge-Tests | mitigate | Gemini-MEDIUM (MED-1 präzisiert): der Reverse-FK-Teardown beider Klasse-A-Gruppen + test_tenant_orgs liegt ZWINGEND in der Fixture-POST-yield-Sektion (try/except NACH dem `yield`, analog test_rls_isolation.py:101-116) — pytest führt die POST-yield-Sektion auch bei Assertion-Fehler aus (das IST das finally-Äquivalent), sodass das Cleanup (account_memory → accounts → tenant_orgs → organisations) auch bei Assertion-Fehler läuft; KEIN literales `try...finally` im Test-Body. Klasse-A sind LOGIK-Tests (merge/filter/hash), die RLS-Cross-Tenant-Prüfung bleibt im D-04-Real-Commit-Pfad der RLS-Gruppe (unverändert) |
| T-PGTEST-14 | Spoofing | echter App-Bug wird still im Test gepatcht statt eskaliert (Req-7-Geist verletzt) | mitigate | Klasse D/E-Brüche im SUMMARY ESKALIEREN (eigene Bugfix-Phase), Test NICHT stilllegen/skippen |
| T-PGTEST-17 | Denial | ATTACH-Listener entfernt, aber ein DRITTER Listener-abhängiger Test (test_08_14_apirate_seed.py, fresh_engine Z.14-19) bleibt unportiert → `Base.metadata.create_all` wirft "unknown database crm" → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy (GOAL-KILLER) | mitigate | Task 3 scopet den create_all auf die PUBLIC ApiRate-Tabelle (`ApiRate.__table__.create`) — kein crm/training nötig, DSN-unabhängig. Vollständigkeits-grep `create_all\|sqlite` über tests/ verifiziert (orchestrator-confirmed): NUR test_08_14 war ungedeckt; test_08_20_3 (raw single-table CREATE TABLE profile_opener, KEIN create_all/crm) + test_meeting_form_dsgvo (Kommentar-only, kein Engine/Fixture) bestätigt SAFE; conftest.py:43/67 → Plan 01; test_account_memory_briefing + test_anonymizer_worker → Task 2 |
| T-PGTEST-19 | Denial | test_tenant_orgs.py (SQLite-no-trigger-Annahme) doppelt auf nerve_test-PG die vom AFTER-INSERT-Trigger trg_mk_tenant_org bereits erzeugte tenant_orgs-Row → UNIQUE(legacy_org_id)-IntegrityError WO der Test ihn nicht erwartet + count==3-Asserts halten nicht → Test errort → pytest exit≠0 → fail-closed Gate blockt JEDEN Deploy (blocker-class wie test_08_14) | mitigate | F1 (pre-execute audit 2026-06-15): Task 4 portiert test_tenant_orgs auf Trigger-Semantik — `_mk_org` liest die vom Trigger auto-erzeugte tenant_orgs-Row zurück (test_rls_isolation.py:33-54-Muster) statt Python-seitig zu doppeln; `_seed_tenant_orgs` wird Read-Back/No-op; test_dualwrite_trigger_fires liest die Trigger-Row statt manuell zu inserten; die ECHTE Idempotenz-Assertion (erwarteter IntegrityError auf forcierten Duplikat) bleibt valide. SQLite-Annahme-Test (wie test_08_14) → portiert, nicht geskippt. SEPARAT: test_tenant_orgs berührt ZERO crm → war nie ein gültiger RLS-Proof (falsche Annahme in Plan 01, dort entfernt; echter RLS-Tripwire = tests/test_rls_generic_smoke.py, Plan 01 Task 2) |
| T-PGTEST-21 | Denial | 5 test-spezifische FK-Deltas brechen auf der persistenten/zero-data nerve_test aus EINZEL-Gruenden: test_postcall_split (id=1-Doppel mit Base-Seed), test_ewb_rate_api (users.email UNIQUE + tenant_orgs-Doppel), test_profile_editor_validation (fehlende org/user-Parents), test_ft_seed (Stufe-2/Klasse-E pre-existing failure, echte Ursache NICHT etabliert — nerve_test ist schema-only/zero-data, der Test seedet selbst via _seed_prompt_versions, count==4 haelt wahrscheinlich; KEIN bewiesener Pre-Seed-Konflikt), test_ab_stats (fehlende Base-Org) -> je ein roter Test -> fail-closed Gate blockt jeden Deploy (blocker-class) | mitigate | Tasks 5-9 (FK-debt fold 2026-06-15): #3 CONSUME Base-Seed statt id=1-Doppel; #8 unique email pro Run + trigger-aware Org (kein manueller tenant_orgs); #9 Parents present + Tenant-Kontext via Plan-01-client (profiles public, keine RLS-Luecke); #10 (W1-korrigiert) test_ft_seed HONEST gegen schema-only nerve_test laufen lassen — KEINE presumptive count-on-empty-Aufweichung; echte Fehlerursache am Execute verifizieren, bei echtem App-Bug eskalieren (tolerante >=4/expected-set-Assertion NUR falls Gate vor-existierende Rows beweist UND der Seed echt geuebt bleibt); #11 Base-Org present + nullable erstellt_von bestaetigt. Alle behalten echte Runtime-Row/Return-Assertions (CLAUDE.md Test-Regel), Best-Effort-Teardown in der POST-yield-Sektion (test_rls_isolation.py:101-116, MED-1). Haengt am Plan-01-Base-Seed (T-PGTEST-20) + A-1-DATABASE_URL. |
| T-PGTEST-23 | Denial (False-Red) | persistentes nerve_test (D-03 1x-Build) + committete Rows aus dem session-scoped Base-Seed (Plan 01 Task 4: Org id=1 + Trigger-tenant_org + User id=1) ODER aus Code-under-test, der auf SEINER EIGENEN Session committet (z.B. log_api_cost → `_db_mod.SessionLocal()` + commit) + eine GLOBALE, ungefilterte count()/all()-Assertion auf so einer Tabelle → garantiert roter Test (global count > erwartet) → fail-closed Gate blockt JEDEN Deploy. Belegt: test_tenant_orgs:65 (`query(TenantOrg).count()==query(Organisation).count()==3` — Base-Seed-Org id=1 + generische Tenants bereits da, BLOCKER), test_cost_tracker:51 (`query(ApiCostLog).count()==0` — test_freeze_fx_on_write hat via log_api_cost bereits eine Row committet, sibling) | mitigate | Delta-Review-2 (Gemini 3.1 Pro, 2026-06-15): Task 4 scopet ALLE count/all-Assertions + Helper (`_seed_tenant_orgs`/`_backfill`) in test_tenant_orgs auf test-eigene Org/User/TenantOrg-IDs (`Organisation.id.in_(own_ids)` / `TenantOrg.legacy_org_id.in_(own_ids)` statt global); Task 10 macht test_cost_tracker:51 persistence-robust (baseline-delta `count()==before` um den unknown-Call ODER `filter_by(provider='unknown').count()==0`). GENERELLE REGEL (success_criteria + must_haves truth): kein Test asserted eine globale, ungefilterte count()/all() auf einer base-seed-befuellten ODER eigen-committenden Tabelle — immer test-eigene IDs / baseline-delta. Alle Assertions bleiben echte Runtime-Row-Reads (CLAUDE.md, keine Source-Presence). Intent erhalten (kein Maskieren). Haengt am Plan-01-Base-Seed (T-PGTEST-20). |
</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen / Schemas

- `crm.accounts` (schreiben — FK-Ziel für account_memory; Test-Insert mit tenant_id) — RLS engaged
- `crm.account_memory` (schreiben + lesen — die merge-Tests; tenant_id muss = gesetzter Tenant, RLS WITH CHECK)
- `training.transcript_archive` (schreiben + lesen — anonymizer Logic-Group; ORM-los, existiert via Gate-Schema-Dump)
- `public.organisations` + `public.tenant_orgs` (Seed-Kette via Trigger trg_mk_tenant_org — für crm-FK + set_current_tenant; UND der primäre Test-Gegenstand von test_tenant_orgs/Task 4)
- `public.users` + `public.calls` (test_tenant_orgs backfill-Tests — calls.tenant_id-Bridge via users.org_id → tenant_orgs.id)
- `public.api_rates` (schreiben + lesen — test_08_14, in-memory SQLite via `ApiRate.__table__.create`; PUBLIC-Tabelle, KEIN crm-Schema, KEIN RLS — reine NOT-NULL-Seed-Regression)
- `public.api_cost_log` (schreiben + lesen — test_cost_tracker; log_api_cost committet auf EIGENER `_db_mod.SessionLocal()`-Session → persistente Rows in nerve_test → Task 10 baseline-delta/Filter statt globaler count==0)

### Katalog-Beleg (zitiert aus RESEARCH; Schema kommt 1:1 vom Prod-nerve-Dump, Plan 02)

`training.transcript_archive` ist eine ORM-LOSE Tabelle (nur im DB-Schema, nicht in models.py) — der
Schild-Guard fängt sie genau deshalb über `pg_description` (CLAUDE.md Punkt 23). Sie wird vom
`pg_dump --schema-only nerve` getragen (Plan 02 Dump-Treue-Assertion) → KEIN hand-DDL `CREATE TABLE
training.transcript_archive` mehr nötig im Test.

`trg_mk_tenant_org` (Migration 0011) ist ein AFTER-INSERT-Trigger auf `public.organisations`, der bei jedem
`INSERT organisations` eine `tenant_orgs`-Row mit `legacy_org_id = NEW.id` per ON CONFLICT (legacy_org_id)
DO NOTHING anlegt. `tenant_orgs` hat ein `UNIQUE(legacy_org_id)`. Auf nerve_test (vom Prod-nerve gedumpt +
auf head migriert) ist dieser Trigger AKTIV → test_tenant_orgs MUSS die Trigger-Row erwarten statt sie zu
doppeln (F1, Task 4). PLUS: der session-scoped Base-Seed (Plan 01 Task 4) committet Org id=1 → dessen
Trigger-tenant_org persistiert → eine GLOBALE count in test_tenant_orgs:65 sähe sie → Task 4 scopet auf
test-eigene IDs (Delta-Review-2).

`api_rates` (models.py:524-540) ist eine PUBLIC-Tabelle (`__tablename__='api_rates'`, `__table_args__` nur
UniqueConstraint `uix_api_rate_active` + comment, KEIN {'schema':'crm'}). Sie hat eine NOT-NULL-Spalte
`last_checked_at` (DateTime, default=utcnow, nullable=False, Z.538) — genau die Regression, die test_08_14
prüft. Da public, baut `ApiRate.__table__.create(engine)` sie ohne crm/training-ATTACH → kein
"unknown database crm" nach Listener-Entfernung. (Frische in-memory SQLite-Engine pro Lauf → keine Base-Seed-Falle.)

`api_cost_log` (services/cost_tracker.py-Schreiber): `log_api_cost` öffnet eine EIGENE `_db_mod.SessionLocal()`
und committet (Z.~99/132). Geschriebene Rows sind transaktions-COMMITTET → persistieren im persistenten
nerve_test über Test-Grenzen (NICHT in der db_session-Fixture gehalten/zurückgerollt). Daher ist
`db_session.query(ApiCostLog).count() == 0` (test_cost_tracker:51) persistence-fragil → Task 10
baseline-delta / `provider='unknown'`-Filter.

crm-RLS/FORCE/GRANTs (RESEARCH „⚑ BUILD-PATH LOCKED", empirisch gegen dump-gebautes nerve_test):
7 crm-RLS-Policies, ENABLE+FORCE auf account_memory/accounts/contacts/meetings/user_preferences, GRANTs
nerve_app=DML / nerve_anon_worker=SELECT. crm.account_memory hat eine `tenant_id`-Spalte mit FK →
`public.tenant_orgs(id)` (RESEARCH Q4b — eine erfundene UUID würde FK-Verletzung werfen, daher Seed).

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| `account_memory.tenant_id` | Test-Insert in merge-Tests | DB-Spalte `crm.account_memory.tenant_id` (FK→tenant_orgs, RLS WITH CHECK) | ✓ RESEARCH Q4b + RLS-Treue-Beweis |
| `account_memory` merge-Felder (meddpicc/context_hooks) | merge_account_memory liest/schreibt | DB-Spalten in `crm.account_memory` (JSONB) | ✓ Schema vom Prod-nerve-Dump (Plan 02) |
| `crm.accounts` FK-Ziel | Test legt accounts-Row vor account_memory an | DB-Tabelle `crm.accounts` mit RLS | ✓ test_rls_isolation.py:82-90-Muster |
| `transcript_archive` (anonymized_at-Stamp) | anonymizer _run schreibt | DB-Tabelle `training.transcript_archive` (ORM-LOS — kein models.py-Eintrag, nur DB) | ✓ via Schema-Dump; KEIN hand-DDL mehr |
| `id` (TranscriptSegment) | _seed_account-Insert | DB-Spalte BIGSERIAL (PG vergibt selbst) | ✓ explizite id WEGLASSEN gegen PG (Klasse-D-Hinweis) |
| `tenant_orgs` (test_tenant_orgs) | `_mk_org` INSERT organisations → Trigger erzeugt Row → Test liest sie zurück, gefiltert auf test-eigene legacy_org_id | DB-Tabelle `public.tenant_orgs` (UNIQUE legacy_org_id; vom Trigger trg_mk_tenant_org gefüllt; persistenter Base-Seed id=1 NICHT in Assertion) | ✓ F1/Task 4: kein Python-Doppel-Seed; test_rls_isolation.py:33-54-Read-Back-Muster + Delta-Review-2 ID-Scoping |
| `calls.tenant_id` (backfill-Tests) | `_backfill_calls_tenant_id` UPDATE-Join über test-eigene Orgs/Users | DB-Spalte `public.calls.tenant_id` (nullable, Bridge via users.org_id → tenant_orgs.id) | ✓ Logik-Analog der Migration 0011 Step 4; Row-Read-Assertion auf test-eigene IDs (Delta-Review-2) |
| `geseedete Rows (Teardown)` | reverse-FK-DELETE in der POST-yield-Sektion (nur test-eigene Rows) | crm.*/tenant_orgs/organisations/users/calls | ✓ POST-yield try/except (test_rls_isolation.py:101-116, MED-1) → kein Leak bei Assertion-Fehler; Base-Seed unangetastet |
| `set_current_tenant` → `app.tenant_id` GUC | vor crm-Writes | transaktions-lokaler GUC (NICHT DB-Spalte) — gelesen von RLS-Policies | ✓ db.py:87; greift via MODUL-SessionLocal (Plan-01-Umbindung) + DATABASE_URL=postgres im Gate (A-1, Plan 02) |
| `api_rates.last_checked_at` | test_08_14 INSERT + NOT-NULL-COUNT-Assertion | DB-Spalte `public.api_rates.last_checked_at` (DateTime, NOT NULL) — in-memory SQLite via `ApiRate.__table__.create` | ✓ models.py:538 (nullable=False); PUBLIC-Tabelle, kein crm → kein ATTACH nötig; frische Engine → keine Persistenz |
| `ApiCostLog` count (test_cost_tracker:51) | `test_missing_rate_no_raise` baseline-delta/provider-Filter | DB-Tabelle `public.api_cost_log` — log_api_cost committet auf EIGENER `_db_mod.SessionLocal()` → persistent in nerve_test | ✓ cost_tracker.py:99/132 (eigener commit); Task 10 baseline-delta / `provider='unknown'`-Filter statt globaler count==0 (Delta-Review-2) |

### Bei Diskrepanz: STOP + Replan
(z.B. account_memory-Insert ohne tenant_id → RLS WITH CHECK violation; transcript_archive nicht im Schema → Dump-Lücke → zurück an Plan 02; ApiRate wäre wider Erwarten crm-scoped → Option B ungültig, STOP; test_tenant_orgs UNIQUE-Kollision trotz Port → trg_mk_tenant_org-Read-Back nicht korrekt umgesetzt → STOP; test_tenant_orgs:65 ODER test_cost_tracker:51 trotz ID-Scoping/baseline-delta rot → globale-count-Hazard nicht vollständig gescoped → STOP, alle count/all-Assertions des Tests gegen Base-Seed/eigen-committende Rows prüfen)

<verification>
- Req-6: `grep _sqlite_attach_crm_training_schemas database/db.py` + `grep "startswith('sqlite')" app.py` → leer; Suite grün ohne Pflaster.
- Req-4: test_rls_isolation.py + test_anonymizer_worker.py (RLS-Gruppe) PASSED (nicht SKIPPED) im Gate-Log.
- Klasse-A: test_account_memory_briefing + anonymizer Logic-Group PASSED gegen nerve_test (keine Collection-Errors); Reverse-FK-Teardown in der POST-yield-Sektion (try/except nach yield, test_rls_isolation.py:101-116, MED-1 — kein State-Leak bei Assertion-Fehler).
- test_08_14: `grep Base.metadata.create_all tests/test_08_14_apirate_seed.py` → leer; `grep ApiRate.__table__.create ...` → Treffer; im Gate-Lauf PASSED (nicht error/SKIPPED), kein "unknown database crm".
- F1/test_tenant_orgs: im Gate-Lauf PASSED (Trigger-Semantik, kein UNIQUE(legacy_org_id)-Kollisions-Error, count auf test-eigene IDs gefiltert == 3 trotz persistentem Base-Seed); `_seed_tenant_orgs` doppelt die Trigger-Row nicht mehr; test_dualwrite_trigger_fires liest die Trigger-Row zurück.
- Delta-Review-2 (globale count vs. persistentes nerve_test): test_tenant_orgs:65 ist auf `Organisation.id.in_(own_ids)`/`TenantOrg.legacy_org_id.in_(own_ids)`==3 gescoped (nicht global); test_cost_tracker:51 ist baseline-delta (`count()==before`) ODER `filter_by(provider='unknown').count()==0`; beide PASSED gegen das persistente nerve_test (Base-Seed Org id=1 + log_api_cost-Row poisonen nicht mehr). KEIN Test mit globaler ungefilterter count/all auf base-seed-/eigen-committender Tabelle bleibt.
- WAL-Hook (db.py Z.22-27): bewusst BEHALTEN (KEEP-Entscheidung, Modul-Engine + sqlite-Guard → inert im PG-Gate; schützt lokale Dev-SQLite; kein Req-6-Ziel) — kein offenes "prüfen"-TODO.
- Klasse D/E (test_ft_seed etc.): falls rot durch echten App-Bug → SUMMARY-Eskalation, nicht gepatcht.
- MED-3 (Ein-Deploy-Constraint): die Phase wird durch GENAU EINEN deploy.sh production-Lauf validiert NACHDEM Plan 01+02+03 zusammen committet sind; kein Zwischen-Deploy nach Wave 1 (der `<verify>`-deploy.sh-Lauf ist der eine finale integrierte Gate-Lauf).
</verification>

<success_criteria>
- ATTACH-Listener + SQLite-Alembic-Hook entfernt; kein toter SQLite-Emulations-Pfad.
- WAL-Hook (db.py Z.22-27) bewusst BEHALTEN — KEEP-Entscheidung dokumentiert (Modul-Engine, sqlite-geguardet → inert im PG-Gate; schützt echte lokale Dev-SQLite außerhalb der Tests; kein Req-6-Emulations-Ziel). Kein offenes "prüfen"-TODO mehr.
- Beide Klasse-A-Test-Gruppen gegen nerve_test-PG, Integration-Assertions intakt (kein Source-Presence).
- test_08_14_apirate_seed.py entblockt: create_all auf die public ApiRate-Tabelle gescopet (`ApiRate.__table__.create`), DSN-unabhängig (in-memory SQLite, nicht geskippt), echte NOT-NULL-Runtime-Regression intakt, kein "unknown database crm" nach Listener-Entfernung.
- F1: test_tenant_orgs.py auf PG-Trigger-Semantik portiert — erwartet die vom trg_mk_tenant_org auto-erzeugte tenant_orgs-Row (kein Python-Doppel-Seed), kein UNIQUE(legacy_org_id)-Kollisions-Error, count auf test-eigene IDs gefiltert == 3, echte Idempotenz-Assertion (erwarteter IntegrityError auf forcierten Duplikat) bleibt; im Gate PASSED (nicht error/SKIPPED).
- GLOBALE-COUNT-REGEL (Delta-Review-2): Kein Test asserted eine GLOBALE, ungefilterte count()/all() auf einer Tabelle, die der Base-Seed (Plan 01 Task 4) befuellt ODER in die Code-under-test auf eigener Session committet — solche Assertions sind auf test-eigene IDs / baseline-delta gescoped (persistentes nerve_test, D-03 1x-Build). Konkret behoben: test_tenant_orgs:65 (`...id.in_(own_ids)`/`legacy_org_id.in_(own_ids)`==3) und test_cost_tracker:51 (baseline-delta `count()==before` ODER `filter_by(provider='unknown').count()==0`). Intent erhalten, kein Maskieren.
- Reverse-FK-Teardown aller portierten Test-Gruppen in der Fixture-POST-yield-Sektion (try/except nach yield, analog test_rls_isolation.py:101-116, MED-1) → läuft auch bei Assertion-Fehler, kein State-Leak in nerve_test; Base-Seed unangetastet.
- RLS+Anon-RLS-Gruppe PASSED im Gate; volle Suite grün ohne Pflaster (inkl. test_08_14 + test_tenant_orgs + test_cost_tracker entblockt — kein verwaister Listener-/Trigger-inkompatibler Test, keine globale-count-False-Red).
- MED-3: Ein-Deploy-Constraint — Phase validiert durch genau EINEN deploy.sh production-Lauf nach gemeinsamem Commit aller 3 Pläne; kein Zwischen-Deploy nach Wave 1.
- Etwaige Klasse-D/E-App-Bugs eskaliert, nicht still gepatcht.
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-03-SUMMARY.md`
</output>

########## DATEI: .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-04-persistenz-haertung-gruppe-a-b-PLAN.md ##########
---
phase: 08.23.2.PGTEST
plan: 04
type: execute
wave: 2
depends_on: [1, 2]
files_modified:
  - tests/test_eur_calculator.py
  - tests/test_ewb_pipeline.py
  - tests/test_prompt_pipeline.py
  - tests/test_admin_dashboard_auth.py
  - tests/test_exchange_rates.py
  - tests/test_profitability.py
  - tests/test_auth_next_redirect.py
  - tests/test_models_04_7_2.py
  - tests/test_revenue_webhook.py
  - tests/test_08_20_3.py
  - tests/test_postcall_outcome_route.py
  - tests/test_per_sid_migration.py
  - tests/test_dashboard_outcome_reminder.py
autonomous: true
complexity: "🔴 (security-near — persistente-nerve_test-Haertung: globale-count-Scoping + crm/public-Teardown via cleanup_rows; Baseline-Waechter-Konformitaet erzwungen)"
requirements: [Req-4, Req-6, Req-7]
user_setup: []

must_haves:
  truths:
    - "Die Gruppe-A-Rest-Tests (test_eur_calculator, test_ewb_pipeline, test_prompt_pipeline) sind gegen die persistente Baseline gehaertet: unfiltered-Summen/global-counts auf test-eigene Daten/baseline-delta gescoped; idempotente Re-Seed-Guards / unique module-Namen statt UNIQUE(version,module)-Kollision"
    - "Die Gruppe-B-Rest-Tests (test_admin_dashboard_auth, test_exchange_rates, test_profitability, test_auth_next_redirect, test_models_04_7_2, test_revenue_webhook, test_08_20_3, test_per_sid_migration, test_dashboard_outcome_reminder) raeumen ihre EIGENEN committeten Rows im Teardown via dem gemeinsamen cleanup_rows-Helfer (Extension 1) wieder weg. NICHT in diesem Plan: test_ab_stats — seine cleanup_rows-Adoption gehoert Plan-03-Task 9 (files_modified-disjoint, flag3)"
    - "test_postcall_outcome_route raeumt seine committeten Rows via cleanup_rows weg (Gruppe-B-Behandlung) — der STALE 6-vs-8 VALID_OUTCOMES-Assert (:156) bleibt UNANGETASTET (Gruppe-C, out-of-scope, vom Orchestrator separat eskaliert)"
    - "Jeder committende Test in diesem Plan ist nach seinem Teardown == public-Baseline → der autouse _baseline_cleanup_guard (Plan 01 Task 6, PUBLIC.*-only) ist GRUEN (kein Drift-FAIL); seine crm.*-Rows == 0 → POST-SUITE-crm-Check (Plan 02) GRUEN"
    - "Cross-cutting: ALLE committenden Tests der Phase nutzen den gemeinsamen cleanup_rows-Helfer statt ad-hoc-DELETE-Bloecke und passieren den Baseline-Waechter (public via in-pytest Plan 01 Task 6, crm via POST-SUITE Plan 02) — eine kanonische Teardown-Mechanik. Die Plan-03-eigenen Tests bekommen ihre cleanup_rows-Adoption in IHREM Plan-03-Task (Orchestrator hand-edit); dieser Plan fasst KEINE Plan-03-Datei an (files_modified-disjoint, flag3)"
    - "Keine Aenderung maskiert einen echten App-Bug (Req-7): echte Klasse-C/E-Bruche werden im SUMMARY eskaliert, nicht still gepatcht/geskippt"
  artifacts:
    - path: "tests/test_eur_calculator.py"
      provides: "EUR-Calculator-Test, FixedCost-Summe auf test-eigene/baseline-delta gescoped (Gruppe A)"
    - path: "tests/test_ewb_pipeline.py"
      provides: "EWB-Pipeline-Test mit idempotentem ewb-Re-Seed-Guard / unique module-Name (kein UNIQUE(version,module)-Bruch, Gruppe A)"
    - path: "tests/test_prompt_pipeline.py"
      provides: "Prompt-Pipeline-Test mit idempotentem variant-Re-Seed-Guard (Gruppe A)"
    - path: "tests/test_postcall_outcome_route.py"
      provides: "committet-eigene-Rows via cleanup_rows weggeraeumt (Gruppe B); stale 6-vs-8 VALID_OUTCOMES-Assert UNANGETASTET (Gruppe C, eskaliert)"
  key_links:
    - from: "die Gruppe-A/B-Tests dieses Plans"
      to: "tests/conftest.py cleanup_rows (Plan 01 Task 5) + _baseline_cleanup_guard (Plan 01 Task 6)"
      via: "Test registriert committete Row-IDs + ruft cleanup_rows in der POST-yield-Sektion; Waechter verifiziert DB==Baseline danach"
      pattern: "cleanup_rows\\("
    - from: "Gruppe-A-Tests (eur_calculator/ewb_pipeline/prompt_pipeline)"
      to: "test-eigene Daten / idempotente Seed-Guards (statt globaler Summe / UNIQUE-Kollision)"
      via: "baseline-delta / filter auf test-eigene IDs / unique module-Name / check-then-insert"
      pattern: "filter|in_\\(|baseline|before|ON CONFLICT|first\\(\\) is None"
---

<objective>
<!-- Option-A persistence-hardening fold 2026-06-15: cleanup-helper + baseline-guard (à la SCHILD) + Gruppe-A/B-Fixes; Option-2 verworfen (RLS-GUC-Leak db.py:92). -->
<!-- NEU 2026-06-15: Plan 04 entsteht im Option-A-Fold, um die NICHT-bereits-in-Plan-03-abgedeckten Gruppe-A-Rest- + Gruppe-B-Tests zu haerten, OHNE Plan 03 (849 Z., 10 Tasks, viele prior fixes) aufzublaehen oder zu clobbern. Die in Plan 03 bereits getaskten Tests (tenant_orgs/cost_tracker/ft_seed/postcall_split/profile_editor/ewb_rate_api/ab_stats) behalten ihre Plan-03-Tasks; test_per_sid_migration + test_dashboard_outcome_reminder gehoeren DIESEM Plan (Task 7); dieser Plan deckt den REST + die cross-cutting cleanup_rows-Adoption. -->
André wählte OPTION A (gezielte Härtung der endlichen committenden-Test-Liste + Cleanup-Helfer + Baseline-Wächter),
NICHT Option-2 (Per-Test-Transaktions-Rollback — verworfen: der RLS-after_begin-Hook cleart app.tenant_id nie
(db.py:92), unter einer langen Per-Test-Transaktion + Savepoints leakt der Tenant-GUC zwischen Schritten →
RLS-False-Green). Dieser Plan (Wave 2, depends_on Plan 01 cleanup_rows+Baseline-Wächter+Base-Seed + Plan 02 Gate)
härtet die in Plan 03 NOCH NICHT getaskten committenden Tests gegen die persistente nerve_test (D-03 1x-Build):

GRUPPE A (Rest, ~3) — Baseline-Konflikte, brauchen Test-Fixes UNABHAENGIG von Isolation (Baseline-Row liegt vor
jeder Test-Transaktion): test_eur_calculator (unfiltered FixedCost-Summe zieht Baseline-FixedCosts rein →
vor-loeschen/scope/delta), test_ewb_pipeline + test_prompt_pipeline (`_seed_ewb_variants`/`_seed_variants`
re-inserten module='ewb'/variants, die die Baseline schon hat → UNIQUE(version,module)-Kollision → idempotenter
Guard / unique module-Name). Per PERSISTENCE-ENUMERATION.md Gruppe A.

GRUPPE B (Rest, ~7 — files_modified-DISJOINT von Plan 03, flag3) — Akkumulations-Tests, die jetzt (Option-2's
freier Fix ist weg) gezielte Teardown-Cleanups brauchen: test_admin_dashboard_auth, test_exchange_rates,
test_profitability, test_auth_next_redirect, test_models_04_7_2, test_revenue_webhook, test_08_20_3 — jeder
committende davon registriert seine erzeugten Row-IDs und ruft cleanup_rows (Extension 1) in der POST-yield-Sektion.
OWNERSHIP (flag3 final, 2026-06-16, files_modified-disjoint): test_per_sid_migration +
test_dashboard_outcome_reminder gehoeren DIESEM Plan (Task 7, in files_modified). NUR test_ab_stats bleibt
Plan 03 (Task 9, hat bereits POST-yield-Teardown; seine cleanup_rows-Adoption ist via die phasen-weite Direktive
im Plan-03-Objective 2026-06-16 abgedeckt). Plan 03 + Plan 04 fassen KEINE gemeinsame Datei an (disjunkt) →
same-wave parallel-sicher.

GRUPPE C (out-of-scope, NICHT fixen): test_postcall_outcome_route:156 `test_valid_outcomes_match_check_constraint`
asserted die ALTEN 6 Outcome-Werte, VALID_OUTCOMES hat jetzt 8 — ein echter Pre-Existing-Test-Bug, bricht auf
JEDEM Backend, vom Orchestrator SEPARAT in den Backlog eskaliert. Dieser Plan fasst die stale 6-vs-8-Assertion
NICHT an. ABER test_postcall_outcome_route committet AUCH eigene Rows → es bekommt die Gruppe-B-cleanup_rows-
Teardown-Behandlung fuer DIESE Rows (nur der stale Assert bleibt unberuehrt).

CROSS-CUTTING (Task 1 dieses Plans): die kanonische Adoption des gemeinsamen cleanup_rows-Helfers — fuer die
NICHT-Plan-03-Dateien dieses Plans + die phasenweite Verifikation (kein ad-hoc-DELETE-Block ohne cleanup_rows).
Die Plan-03-eigenen Tests bekommen ihre cleanup_rows-Adoption in IHREM Plan-03-Task (Orchestrator hand-editiert
Plan 03 — flag3), NICHT hier: dieser Plan editiert KEINE Plan-03-Datei (files_modified-disjoint). So gibt es EINE
Teardown-Mechanik phasenweit, JEDER committende Test passiert den Baseline-Waechter (public in-pytest Plan 01 Task 6,
crm POST-SUITE Plan 02), und Plan 03 + Plan 04 sind same-wave parallel-sicher (kein gemeinsamer Datei-Edit).

Purpose: Req-4 (RLS/Anon laufen ehrlich — kein Test-Muell maskiert Defekte), Req-6 (kein SQLite-Pflaster),
Req-7 (echte Bugs eskaliert, nicht maskiert). Grundlage: Plan 01 cleanup_rows + Baseline-Waechter + Base-Seed.
Output: die ~10 Gruppe-A-Rest- + Gruppe-B-Tests dieses Plans gehaertet (Scoping + cleanup_rows-Teardown,
files_modified-disjoint von Plan 03) + cross-cutting cleanup_rows-Adoption fuer die NICHT-Plan-03-Dateien +
jeder committende Test dieses Plans == public-Baseline (in-pytest-Waechter gruen) + crm.* == 0 (POST-SUITE Plan 02).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-SPEC.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-CONTEXT.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-RESEARCH.md
@.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md

<interfaces>
<!-- Verträge aus Plan 01 (Wave 1) + Codebase. Die Tests dieses Plans laufen gegen die vom Gate (Plan 02) gebaute nerve_test. -->

Aus tests/conftest.py (NACH Plan 01):
- `cleanup_rows(conn_or_session, {tabelle_oder_model: [ids]}, tenant=<uuid|None>)` (Extension 1, Task 5):
  reverse-FK-clean best-effort DELETE der UEBERGEBENEN test-eigenen Rows. crm.* unter Tenant-GUC (set_config),
  public.* ohne. Modelliert auf test_rls_isolation.py:101-116. Loescht NIE Baseline-Rows. In der POST-yield-
  Sektion aufrufen (laeuft auch bei Assertion-Fehler).
- `_baseline_cleanup_guard` (Extension 2, Plan 01 Task 6): autouse, asserted NACH JEDEM Test (nach dem
  Test-cleanup) das PUBLIC.* PK-Set == Session-Start-Baseline pro relevanter public-Tabelle. Drift → fail-closed
  (nodeid + Tabelle + leaked/missing PKs). PUBLIC.*-only (nerve_app liest public unfiltered). KEIN Test muss ihn
  anfordern — er ist autouse; jeder committende Test MUSS ihn passieren (== public aufraeumen).
- crm.*-Sauberkeit (HYBRID, André locked): NICHT in-pytest. deploy.sh (Plan 02) prueft POST-SUITE (nach pytest,
  vor trap) via `sudo -u postgres psql`, dass jede crm.* Tabelle == 0 Rows ist. Jeder crm-committende Test MUSS
  im Teardown via cleanup_rows(tenant=...) auf crm.* == 0 zurueckraeumen, sonst bricht der POST-SUITE-Check.
- `db_session` / `client` / `db_from_client`: PG-gegen-nerve_test, MODUL-SessionLocal (hook-tragend),
  set_current_tenant(TEST_TENANT_UUID) gesetzt. Base-Seed Org id=1 + User id=1 verfuegbar (Task 4).
- `_seed_test_tenant(engine)` / `TEST_TENANT_UUID`: Trigger-tenant_orgs-Seed (test_rls_isolation.py:33-54-Muster).

Aus PERSISTENCE-ENUMERATION.md (die Klassifikation, Quelle der Wahrheit pro Test):
- Gruppe A (Baseline-Konflikt, Test-Fix unabhaengig): test_ft_seed*, test_tenant_orgs*, test_eur_calculator,
  test_cost_tracker*, test_ewb_pipeline, test_prompt_pipeline. (* = bereits in Plan 03 getaskt.)
- Gruppe B (Akkumulation): test_ab_stats*, test_admin_dashboard_auth, test_ewb_rate_api*, test_exchange_rates,
  test_per_sid_migration, test_profitability, test_auth_next_redirect, test_models_04_7_2, test_revenue_webhook,
  test_08_20_3, test_postcall_split*, test_profile_editor_validation*, test_dashboard_outcome_reminder.
  (* = Plan-03-eigen → NICHT in Plan 04 files_modified, flag3. Plan 04 deckt: admin_dashboard_auth,
  exchange_rates, profitability, auth_next_redirect, models_04_7_2, revenue_webhook, 08_20_3,
  test_per_sid_migration + test_dashboard_outcome_reminder [Task 7].)
- Gruppe C (echte Pre-Existing-Bugs, eskalieren, NICHT fixen): test_postcall_outcome_route:156 (6-vs-8 VALID_OUTCOMES).

Aus test_rls_isolation.py:101-116 (das cleanup_rows-Vorbild — Plan 01 Task 5 hat es zum Helfer extrahiert):
POST-yield `cur=conn.cursor(); try: SET set_config(tenant) je crm-Tenant; DELETE crm.account_memory; DELETE
crm.accounts; commit; DELETE public.tenant_orgs; DELETE public.organisations; commit; except: rollback`.

KONFLIKT-AUFLOESUNG mit Plan 03 (flag3, 2026-06-15 — files_modified jetzt DISJOINT):
Plan 03 files_modified: db.py, app.py, account_memory_briefing, anonymizer_worker, 08_14, tenant_orgs,
postcall_split, ewb_rate_api, profile_editor_validation, ft_seed, ab_stats, cost_tracker.
Plan 04 files_modified (final): eur_calculator, ewb_pipeline, prompt_pipeline, admin_dashboard_auth,
exchange_rates, profitability, auth_next_redirect, models_04_7_2, revenue_webhook, 08_20_3,
postcall_outcome_route, test_per_sid_migration, test_dashboard_outcome_reminder (Task 7). → KEINE gemeinsame
Datei mit Plan 03 (test_ab_stats ist NUR Plan 03/Task 9). Plan 03 + Plan 04 sind damit same-wave (Wave 2)
PARALLEL-SICHER (disjunkte files_modified). Siehe WAVE-NOTE unten.
</interfaces>

<wave_note>
WAVE/PARALLEL-SICHERHEIT (flag3 final, 2026-06-16 — files_modified DISJOINT): Plan 03 + Plan 04 sind beide
Wave 2 und teilen KEINE Datei. test_ab_stats ist NUR Plan 03 (Task 9); test_per_sid_migration +
test_dashboard_outcome_reminder gehoeren Plan 04 (Task 7). Damit sind Plan 03 + Plan 04 same-wave PARALLEL-SICHER
(disjunkte files_modified, keine Sequenz-Kopplung noetig). Plan 03's cleanup_rows-Adoption fuer SEINE committenden
Tests (inkl. ab_stats) ist via die phasen-weite Direktive im Plan-03-Objective (2026-06-16) abgedeckt. MED-3
(Ein-Deploy-Constraint) bleibt: die GANZE Phase (Plan 01+02+03+04) wird durch GENAU EINEN deploy.sh production-Lauf
validiert NACHDEM alle 4 Plaene committet sind — kein Zwischen-Deploy.
</wave_note>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Cross-cutting — gemeinsame cleanup_rows-Adoption ueber ALLE committenden Tests der Phase (kanonische Teardown-Mechanik, Baseline-Waechter-Konformitaet)</name>
  <read_first>
    - tests/conftest.py (NACH Plan 01: cleanup_rows (Task 5) + _baseline_cleanup_guard (Task 6) — die zu adoptierende Mechanik + der Erzwinger)
    - tests/test_rls_isolation.py Z.101-116 (das Muster, das cleanup_rows extrahiert — die in Plan 03 getaskten Tests tragen diesen ad-hoc-Block; hier auf den Helfer umstellen)
    - PERSISTENCE-ENUMERATION.md Gruppe A + Gruppe B (die VOLLSTAENDIGE Liste committender Tests — der Scope dieser Adoption)
    - die Plan-03-getaskten Test-Dateien (account_memory_briefing, anonymizer_worker, tenant_orgs, postcall_split, ewb_rate_api, profile_editor_validation, ab_stats, ft_seed, cost_tracker — NUR ZUM LESEN/Inventarisieren; dieser Plan editiert sie NICHT, Plan 03 deckt ihre cleanup_rows-Adoption via phasen-weite Direktive im Plan-03-Objective)
  </read_first>
  <behavior>
    - Eine kanonische Teardown-Mechanik phasenweit: jeder committende Test ruft `cleanup_rows(...)` in seiner
      POST-yield-Sektion (statt eines ad-hoc-DELETE-Blocks). Wo Plan 03 bereits einen POST-yield-DELETE-Block
      eingefuehrt hat (account_memory_briefing/anonymizer_worker/tenant_orgs/etc.), wird dieser auf den
      gemeinsamen Helfer umgestellt — IDENTISCHES Verhalten (reverse-FK, crm.* unter Tenant-GUC, best-effort),
      nur EINE Quelle.
    - WICHTIG (flag3, kein Clobbern): Plan 03 (Datei + die von ihm getaskten Test-Dateien) wird von DIESEM Plan
      NICHT angefasst — der Orchestrator hand-editiert Plan 03 fuer die cleanup_rows-Adoption seiner eigenen Tests.
      Plan 04 files_modified ist DISJUNKT von Plan 03 (flag3) → kein paralleler Same-Wave-Edit moeglich.
    - Resultat: der autouse _baseline_cleanup_guard (PUBLIC.*-only, Plan 01 Task 6) ist fuer JEDEN committenden
      Test gruen (public-DB==Baseline nach Teardown); zusaetzlich ist crm.* == 0 (POST-SUITE-Check Plan 02).
      Ad-hoc-DELETE-Bloecke, die public-Rows uebersehen, werden vom in-pytest-Waechter gefangen; crm.*-Leaks vom
      POST-SUITE-Check. Beide → auf cleanup_rows umgestellt (public ohne, crm.* mit Tenant-GUC).
  </behavior>
  <action>
    1. Inventarisiere (grep) alle committenden Tests (POST-yield-DELETE-Bloecke + `commit()`-Aufrufe ueber die
       Enumeration Gruppe A/B). Fuer jeden: stelle den POST-yield-Teardown auf `cleanup_rows({...}, tenant=...)`
       um (oder fuege ihn hinzu, falls fehlend). Der Test registriert die von ihm erzeugten Row-IDs (sammeln
       waehrend des Test-Bodys) und uebergibt sie.
    2. Fuer crm.*-committende Tests: tenant-Arg setzen (der Test-Tenant, unter dem die Rows geseedet wurden) —
       sonst loescht cleanup_rows unter falschem/keinem GUC 0 Rows → Leak → Waechter rot.
    3. KEINE Verhaltens-/Assertion-Aenderung an den Tests — nur die Teardown-Mechanik wird vereinheitlicht.
    4. DELEGATIONS-REGEL (flag3, files_modified-disjoint — Anti-Clobber, HART): dieser Plan editiert KEINE
       Plan-03-eigene Test-Datei. Alle Plan-03-eigenen Tests (account_memory_briefing, anonymizer_worker,
       tenant_orgs, postcall_split, ewb_rate_api, profile_editor_validation, ab_stats, ft_seed, cost_tracker)
       bekommen ihre cleanup_rows-Adoption in Plan 03 (phasen-weite Direktive im Plan-03-Objective, 2026-06-16).
       test_per_sid_migration + test_dashboard_outcome_reminder gehoeren DIESEM Plan (Task 7). Dieser Task 1 deckt
       die NICHT-Plan-03-Dateien dieses Plans + die cross-cutting Verifikation (grep), dass am Ende KEINE
       ad-hoc-DELETE-Bloecke ohne cleanup_rows mehr existieren. (Adoptions-Matrix im SUMMARY: pro committendem Test
       welcher Plan/Task seinen cleanup_rows-Teardown setzt.)
    5. Anti-False-Green (CLAUDE.md): cleanup_rows ist Infrastruktur, keine Assertion. Die Test-Assertions bleiben
       echte Row-/Response-Reads.
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -rlnE "DELETE FROM (crm|public)\." tests/ | xargs -r grep -Ln "cleanup_rows" ; echo "--- committende ohne cleanup_rows (sollte leer/erklaert sein) ---"'; echo "EXIT=$?"  # Ziel: kein committender Test mit ad-hoc-DELETE OHNE cleanup_rows (Ausnahmen: cleanup_rows-Def selbst + rls_isolation falls bewusst nativ). Voll-Beleg: Gate-Lauf — _baseline_cleanup_guard (public.*-only, Plan 01 Task 6) gruen fuer alle committenden Tests, kein Drift-FAIL; POST-SUITE-crm-Check (Plan 02) meldet 0 crm.*-Leak-Rows.</automated>
  </verify>
  <done>
    Phasenweit nutzt jeder committende Test den gemeinsamen `cleanup_rows`-Helfer in seiner POST-yield-Sektion
    (crm.* unter Tenant-GUC, reverse-FK, best-effort) — ad-hoc-DELETE-Bloecke aus Plan 03 sind auf den Helfer
    umgestellt (in der jeweiligen Datei; bei Plan-03-files_modified-Dateien im Plan-03-Task, nicht doppelt). Die
    Adoptions-Matrix (Test → Plan/Task, inkl. „Plan 03 (Orchestrator hand-edit)" fuer die Plan-03-eigenen Tests)
    ist im SUMMARY. Im Gate-Lauf ist der autouse _baseline_cleanup_guard (public.*-only, Plan 01 Task 6) fuer JEDEN
    committenden Test gruen (public-DB==Baseline nach Teardown) UND crm.* == 0 (POST-SUITE-Check Plan 02), kein
    Drift-FAIL. grep zeigt keinen committenden Test mit ad-hoc-DELETE ohne cleanup_rows (begruendete Ausnahmen
    dokumentiert). Dieser Plan editiert KEINE Plan-03-Datei (files_modified-disjoint, flag3).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Gruppe-A-Rest — test_eur_calculator (unfiltered FixedCost-Summe → test-eigene/baseline-delta) + cleanup_rows-Teardown</name>
  <read_first>
    - tests/test_eur_calculator.py (ganze Datei — die FixedCost-Summe/Aggregation, die aktuell GLOBAL ueber alle fixed_costs zieht; speziell wo `query(FixedCost)` / `sum(...)` ohne Filter laeuft)
    - PERSISTENCE-ENUMERATION.md Gruppe A (test_eur_calculator: „unfiltered FixedCost-Summe zieht Baseline-FixedCosts rein → vor-loeschen/scope/delta")
    - tests/conftest.py (cleanup_rows + Base-Seed + die app-import-geseedeten FixedCost-Baseline-Rows aus _seed_founder_dashboard_defaults)
    - database/models.py (FixedCost — Spalten/FK, fuer das Scoping + ggf. einen unterscheidenden Marker)
  </read_first>
  <behavior>
    - test_eur_calculator aggregiert FixedCosts; auf der persistenten nerve_test enthaelt fixed_costs bereits die
      app-import-Baseline (_seed_founder_dashboard_defaults) → eine GLOBALE unfiltered Summe zieht Fremd-Rows rein
      → die erwartete EUR-Summe stimmt nicht → False-Red.
    - FIX: die Aggregation auf die test-EIGENEN FixedCost-Rows scopen (filter auf test-eigene IDs / einen
      test-Marker / org_id) ODER baseline-delta (vorher-Summe erfassen, Differenz pruefen). Intent (korrekte
      EUR-Berechnung) bleibt eine echte Runtime-Assertion.
    - Falls der Test eigene FixedCost-Rows committet → im Teardown via cleanup_rows weg (Baseline-Sauberkeit).
  </behavior>
  <action>
    1. Identifiziere die unfiltered FixedCost-Aggregation. Scope sie auf test-eigene Rows: entweder
       `filter(FixedCost.id.in_(own_ids))` / `filter_by(org_id=<test-org>)` ODER baseline-delta
       (`before = <summe>` vor dem test-eigenen Insert, danach `after - before` pruefen). Waehle die Form, die
       den Intent (EUR-Berechnung der test-eigenen Kosten) exakt trifft.
    2. Falls der Test FixedCost-Rows committet (eigene Session) → registriere ihre IDs + cleanup_rows im
       POST-yield-Teardown (public.fixed_costs, kein crm-GUC noetig).
    3. Assertions bleiben echte Summen-/Row-Reads (kein Source-Presence).
    Rationale (ENUMERATION Gruppe A): Baseline-FixedCosts liegen persistent vor jedem Test → globale Summe
    poisoned → scope/delta. Unabhaengig von jeder Isolations-Strategie noetig.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy04_2.log | grep -E "test_eur_calculator|passed|failed|error"; echo "EXIT=$?"  # test_eur_calculator PASSED gegen persistentes nerve_test (Summe auf test-eigene/delta gescoped, kein Baseline-FixedCost-Poison); Waechter gruen.</automated>
  </verify>
  <done>
    test_eur_calculator scopet seine FixedCost-Aggregation auf test-eigene Rows / baseline-delta (nicht global) →
    kein Baseline-FixedCost-Poison; committete Rows via cleanup_rows weggeraeumt; Assertions echte Summen-Reads;
    im Gate PASSED, Baseline-Waechter gruen.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Gruppe-A-Rest — test_ewb_pipeline + test_prompt_pipeline (idempotenter Re-Seed-Guard / unique module-Name gegen UNIQUE(version,module)-Kollision) + cleanup_rows</name>
  <read_first>
    - tests/test_ewb_pipeline.py (ganze Datei — `_seed_ewb_variants`/aehnlich, das module='ewb'-PromptVersion-Rows re-inserted, die die Baseline aus _seed_prompt_versions/_seed_ewb_v2 schon hat)
    - tests/test_prompt_pipeline.py (ganze Datei — `_seed_variants`/aehnlich, analoger variant-Re-Insert)
    - PERSISTENCE-ENUMERATION.md Gruppe A (beide: „_seed_ewb_variants/_seed_variants re-inserten module='ewb' (version) die Baseline schon hat → UNIQUE(version,module)-Kollision → idempotenter Guard / unique module-Name")
    - app.py `_seed_prompt_versions` / `_seed_ewb_v2` (die Baseline-PromptVersions inkl. 2 ewb — die Kollisions-Quelle) + database/models.py (PromptVersion UNIQUE(version,module)-Constraint verifizieren)
    - tests/conftest.py (cleanup_rows)
  </read_first>
  <behavior>
    - Beide Tests re-seeden PromptVersion-Variants (module='ewb' bzw. andere) mit (version, module)-Werten, die die
      app-import-Baseline (_seed_prompt_versions/_seed_ewb_v2) auf der persistenten nerve_test BEREITS enthaelt →
      `UNIQUE(version, module)`-IntegrityError beim Test-Seed → False-Red/Error.
    - FIX (zwei akzeptable Wege, pro Test den passenden): (a) idempotenter check-then-insert-Guard
      (`... .first() is None` / `ON CONFLICT DO NOTHING`) sodass der Test die vorhandene Baseline-Row KONSUMIERT
      statt zu doppeln, ODER (b) ein UNIQUE test-eigener module-Name (z.B. `module=f'ewb-test-{uuid8}'`), sodass
      keine Kollision mit der Baseline entsteht. Waehle pro Test die, die den Test-Intent (Pipeline-Verhalten)
      erhaelt.
    - Test-eigene committete Variant-Rows → cleanup_rows im Teardown.
  </behavior>
  <action>
    1. test_ewb_pipeline: finde den ewb-variant-Re-Seed. Entweder idempotenter Guard (check-then-insert /
       ON CONFLICT) ODER unique test-module-Name. Bewahre den Pipeline-Test-Intent (was der Test wirklich prueft).
    2. test_prompt_pipeline: analog fuer seinen variant-Re-Seed.
    3. Falls die Tests Variant-Rows committen (eigene Session) → IDs registrieren + cleanup_rows
       (public.prompt_versions; kein crm-GUC) im POST-yield-Teardown. Bei unique-module-Name sind die Rows
       eindeutig test-eigen → sauber loeschbar.
    4. Assertions bleiben echte Pipeline-/Row-Reads (kein Source-Presence).
    Rationale (ENUMERATION Gruppe A): die Baseline traegt module='ewb'-Versions → Re-Insert kollidiert auf
    UNIQUE(version,module) → idempotenter Guard / unique module. Unabhaengig von Isolation noetig.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy04_3.log | grep -E "test_ewb_pipeline|test_prompt_pipeline|passed|failed|error|UniqueViolation|IntegrityError"; echo "EXIT=$?"  # beide PASSED gegen persistentes nerve_test (kein UNIQUE(version,module)-Bruch); Waechter gruen.</automated>
  </verify>
  <done>
    test_ewb_pipeline + test_prompt_pipeline brechen NICHT mehr an UNIQUE(version,module) (idempotenter
    check-then-insert-Guard ODER unique test-module-Name); test-eigene Variant-Rows via cleanup_rows weggeraeumt;
    Pipeline-Assertions echte Row-Reads; im Gate PASSED, Baseline-Waechter gruen.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Gruppe-B-Rest A — test_admin_dashboard_auth + test_exchange_rates + test_profitability cleanup_rows-Teardown + Akkumulations-Scoping</name>
  <read_first>
    - tests/test_admin_dashboard_auth.py (ganze Datei — nutzt db_from_client (Plan 01 entblockt es); welche Rows committet es? org/user/dashboard-Daten)
    - tests/test_exchange_rates.py (ganze Datei — committet exchange_rate-Rows; ggf. globale count/Aggregation)
    - tests/test_profitability.py (ganze Datei — committet cost/revenue-Rows; ggf. globale Profitabilitaets-Aggregation)
    - PERSISTENCE-ENUMERATION.md Gruppe B (alle drei: Akkumulation, brauchen Teardown-Cleanup)
    - tests/conftest.py (cleanup_rows + _baseline_cleanup_guard + Base-Seed)
  </read_first>
  <behavior>
    - Alle drei committen eigene Rows, die auf der persistenten nerve_test akkumulieren → ohne Teardown driften
      sie die Baseline (Waechter rot) und poisonen ggf. eigene/fremde Aggregationen.
    - FIX: jeder registriert seine committeten Row-IDs + cleanup_rows im POST-yield-Teardown. Falls ein Test eine
      GLOBALE count/Aggregation macht (exchange_rates/profitability sind aggregations-nah), auf test-eigene IDs /
      baseline-delta scopen (sonst Fremd-/Baseline-Rows verzerren das Ergebnis — Delta-Review-2-Klasse).
    - test_admin_dashboard_auth ist FK-SAFE (Plan 01 db_from_client-Vertrag entblockt es ohne Edits) — hier NUR
      die cleanup_rows-Teardown-Adoption falls es committet; falls es read-only ist (nur Auth-Checks), KEIN
      cleanup noetig (dann no-op, im SUMMARY vermerken).
  </behavior>
  <action>
    1. test_admin_dashboard_auth: pruefe ob es committet (org/user/dashboard-Rows). Wenn ja → IDs registrieren +
       cleanup_rows (public.*; ggf. crm-GUC falls crm beruehrt — pruefen). Wenn read-only → keine Aenderung,
       im SUMMARY als „read-only, kein cleanup noetig" vermerken.
    2. test_exchange_rates: cleanup_rows fuer die committeten exchange_rate-Rows; falls eine globale count/
       Aggregation → auf test-eigene IDs / baseline-delta scopen.
    3. test_profitability: cleanup_rows fuer committete cost/revenue-Rows; falls globale Profitabilitaets-
       Aggregation → auf test-eigene Daten scopen (sonst Baseline-/Fremd-Rows verzerren).
    4. Assertions bleiben echte Row-/Aggregations-Reads (kein Source-Presence). Echte App-Bugs eskalieren (Req-7).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy04_4.log | grep -E "test_admin_dashboard_auth|test_exchange_rates|test_profitability|passed|failed|error"; echo "EXIT=$?"  # alle drei PASSED; Waechter gruen (committete Rows weggeraeumt, Aggregationen gescoped).</automated>
  </verify>
  <done>
    test_admin_dashboard_auth (cleanup falls committend, sonst dokumentiert read-only), test_exchange_rates +
    test_profitability raeumen ihre committeten Rows via cleanup_rows weg + scopen etwaige globale Aggregationen
    auf test-eigene/baseline-delta; Assertions echte Row-Reads; im Gate PASSED, Baseline-Waechter gruen.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: Gruppe-B-Rest B — test_auth_next_redirect + test_models_04_7_2 + test_revenue_webhook + test_08_20_3 cleanup_rows-Teardown</name>
  <read_first>
    - tests/test_auth_next_redirect.py (ganze Datei — nutzt client._test_session (Plan 01 entblockt); committet user/org fuer den Redirect-Flow; unique-email-Re-Seed laut ENUMERATION)
    - tests/test_models_04_7_2.py (ganze Datei — committet model-Rows)
    - tests/test_revenue_webhook.py (ganze Datei — committet revenue/subscription-Rows via Webhook-Pfad)
    - tests/test_08_20_3.py (ganze Datei — raw single-table Insert (profile_opener laut Plan 03 T-PGTEST-17-Note); committet eine Row)
    - PERSISTENCE-ENUMERATION.md Gruppe B (alle vier) + Plan 03 T-PGTEST-17-Note (test_08_20_3: raw single-table CREATE TABLE profile_opener, KEIN crm/create_all — safe von der Listener-Seite, aber committet → braucht cleanup)
    - tests/conftest.py (cleanup_rows + Base-Seed; test_auth_next_redirect ist FK-SAFE via db_from_client-Vertrag)
  </read_first>
  <behavior>
    - Alle vier committen eigene Rows → ohne Teardown Baseline-Drift (Waechter rot).
    - FIX: cleanup_rows im POST-yield-Teardown pro Test fuer die committeten Rows. test_auth_next_redirect nutzt
      zusaetzlich unique-email pro Run (ENUMERATION: „unique-email re-seed") falls es user-Rows committet — sonst
      users.email-UNIQUE-Bruch auf der persistenten DB.
    - test_08_20_3: committet eine Row (profile_opener o.ae.) → cleanup_rows; es ist von der SQLite-Listener-Seite
      safe (Plan 03 T-PGTEST-17 bestaetigt), aber persistenz-seitig braucht es Teardown.
  </behavior>
  <action>
    1. test_auth_next_redirect: unique-email (uuid-suffixed) falls es user committet; IDs registrieren +
       cleanup_rows (public.users/organisations + ggf. der Redirect-Flow-Rows).
    2. test_models_04_7_2: cleanup_rows fuer die committeten model-Rows.
    3. test_revenue_webhook: cleanup_rows fuer revenue/subscription-Rows (reverse-FK falls Kette).
    4. test_08_20_3: cleanup_rows fuer die committete Single-Row.
    5. Falls eine globale count/Aggregation in einem der Tests → auf test-eigene IDs scopen. Assertions bleiben
       echte Row-/Response-Reads (kein Source-Presence). Echte App-Bugs eskalieren (Req-7).
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | tee /tmp/pgtest_deploy04_5.log | grep -E "test_auth_next_redirect|test_models_04_7_2|test_revenue_webhook|test_08_20_3|passed|failed|error|UniqueViolation"; echo "EXIT=$?"  # alle vier PASSED; Waechter gruen.</automated>
  </verify>
  <done>
    test_auth_next_redirect (unique-email + cleanup), test_models_04_7_2, test_revenue_webhook, test_08_20_3
    raeumen ihre committeten Rows via cleanup_rows weg (reverse-FK, public.*); Assertions echte Row-/Response-Reads;
    im Gate PASSED, Baseline-Waechter gruen.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 6: Gruppe-B + Gruppe-C-Teardown — test_postcall_outcome_route committet-eigene-Rows via cleanup_rows (stale 6-vs-8 VALID_OUTCOMES-Assert UNANGETASTET, eskaliert)</name>
  <read_first>
    - tests/test_postcall_outcome_route.py (ganze Datei — speziell `test_valid_outcomes_match_check_constraint`:156 mit der STALEN 6-vs-8 VALID_OUTCOMES-Assertion = Gruppe C, NICHT anfassen; UND die uebrigen Tests, die org/user/call/outcome-Rows committen = Gruppe-B-Teil, cleanup noetig)
    - PERSISTENCE-ENUMERATION.md Gruppe C (test_postcall_outcome_route:156 — echter Pre-Existing-Bug, eskalieren, NICHT fixen) + die Base-Seed-Note (Plan 01 Task 4 deckt seine FK-Parents user_id=1/org_id=1)
    - services/.../VALID_OUTCOMES (8 Werte inkl. send_info/gatekeeper_blocked — der Grund warum die 6-Wert-Assertion stale ist; NUR zum Verstehen, NICHT aendern)
    - tests/conftest.py (cleanup_rows + Base-Seed)
  </read_first>
  <behavior>
    - test_postcall_outcome_route hat ZWEI Naturen: (C) der stale Assert `test_valid_outcomes_match_check_constraint`
      (:156) prueft 6 statt 8 VALID_OUTCOMES → echter Pre-Existing-Bug, bricht auf JEDEM Backend → OUT OF SCOPE,
      vom Orchestrator separat in den Backlog eskaliert → NICHT anfassen (weder Assert aendern noch skippen).
    - (B) die UEBRIGEN Tests committen org/user/call/outcome-Rows (FK-Parents via Base-Seed Plan 01 Task 4
      gedeckt) → diese committeten Rows brauchen cleanup_rows im Teardown (Baseline-Sauberkeit), sonst Waechter rot.
    - WICHTIG: der stale 6-vs-8-Test wird WEITER ROT/eskaliert sein (das ist erwartet + out-of-scope). Der
      Baseline-Waechter darf NICHT wegen DIESES erwarteten Fails die anderen Tests verfaelschen — der Waechter
      laeuft pro Test; ein roter Gruppe-C-Test raeumt trotzdem (oder hat keine eigenen Rows) → kein Leak.
      Dokumentiere im SUMMARY: 6-vs-8 bleibt rot/eskaliert; alle ANDEREN postcall_outcome_route-Tests gruen +
      baseline-sauber.
  </behavior>
  <action>
    1. NICHT anfassen: `test_valid_outcomes_match_check_constraint` (:156) — die 6-vs-8 VALID_OUTCOMES-Assertion
       bleibt Wort fuer Wort. KEIN Assert-Update auf 8, KEIN skip/xfail (das waere Maskieren; der Orchestrator
       hat es separat eskaliert). Im SUMMARY als „Gruppe C, out-of-scope, eskaliert — bewusst nicht gefixt" vermerken.
    2. Fuer die UEBRIGEN Tests (die committen): registriere die erzeugten org/user/call/outcome-Row-IDs +
       cleanup_rows im POST-yield-Teardown (reverse-FK: outcome/call → conversation_log → ... ; public.*; falls
       crm beruehrt → Tenant-GUC). FK-Parents (user_id=1/org_id=1) liefert der Base-Seed → NICHT selbst inserten.
    3. Assertions der uebrigen Tests bleiben echte Row-/Response-Reads (kein Source-Presence).
    Rationale: Gruppe-C-Bug ist out-of-scope (eskaliert), aber der Test COMMITTET → Gruppe-B-cleanup_rows fuer
    SEINE Rows ist trotzdem noetig (nur der stale Assert bleibt unberuehrt).
  </action>
  <verify>
    <automated>ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && grep -nE "VALID_OUTCOMES|cleanup_rows" tests/test_postcall_outcome_route.py'; echo "EXIT=$?"  # erwartet: die VALID_OUTCOMES-Assertion (6-vs-8) UNVERAENDERT present; cleanup_rows in den committenden Tests present. Gate-Lauf: 6-vs-8 bleibt rot/eskaliert (erwartet), alle anderen postcall_outcome_route-Tests gruen + Waechter gruen fuer sie.</automated>
  </verify>
  <done>
    Die stale `test_valid_outcomes_match_check_constraint`-Assertion (6-vs-8 VALID_OUTCOMES, :156) ist UNANGETASTET
    (nicht gefixt, nicht geskippt — Gruppe C, vom Orchestrator separat eskaliert; im SUMMARY vermerkt). Die uebrigen
    committenden Tests in test_postcall_outcome_route raeumen ihre org/user/call/outcome-Rows via cleanup_rows im
    Teardown weg (FK-Parents via Base-Seed); ihre Assertions bleiben echte Row-/Response-Reads. Im Gate bleibt der
    6-vs-8-Test rot/eskaliert (erwartet), alle anderen sind gruen + baseline-sauber (Waechter gruen fuer sie).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 7: Gruppe-B-Rest C — test_per_sid_migration + test_dashboard_outcome_reminder (Baseline-Sauberkeit verifizieren / cleanup_rows adoptieren)</name>
  <read_first>
    - tests/test_per_sid_migration.py (test_load_profile_cache_populates_sid: schreibt User/Profile unter org_id=1 — committet es auf eigener Session oder nur flush() auf db_session?)
    - tests/test_dashboard_outcome_reminder.py (committet Call/ConversationLog via eigenem get_session(); `_cleanup`-finally laeuft heute nur bei Erfolg)
    - tests/conftest.py (Plan 01 Task 5 cleanup_rows-Helfer + Task 6 Baseline-Waechter — der erzwingt Baseline-Sauberkeit)
    - .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md (Gruppe B: per_sid_migration=ISO-FIXES/flush-only, dashboard_reminder=eigener-commit)
  </read_first>
  <behavior>
    - test_per_sid_migration: WENN der Test nur `db_session.flush()` (kein eigener-Session-commit) macht, raeumt der db_session-Rollback (D-03) auf → baseline-sauber, KEIN cleanup_rows noetig (im SUMMARY als „rollback-covered" vermerken). WENN er auf eigener Session committet → cleanup_rows im Teardown.
    - test_dashboard_outcome_reminder: committet eigene Call/ConversationLog-Rows (unter user_id=1/org_id=1 Base-Seed) → cleanup_rows im Teardown in reverse-FK-Reihenfolge, GARANTIERT laufend (post-yield try/except, NICHT nur bei Erfolg) → Waechter gruen.
  </behavior>
  <action>
    1. test_per_sid_migration: pruefe per `read_first`, ob `test_load_profile_cache_populates_sid` auf eigener Session committet. Falls NUR flush() auf db_session → keine Aenderung noetig (Rollback raeumt auf); dokumentiere das. Falls eigener-Session-commit → registriere die erzeugten User/Profile-IDs und raeume sie via `cleanup_rows(...)` im post-yield-Teardown weg.
    2. test_dashboard_outcome_reminder: das heutige `_cleanup`-finally laeuft nur bei Test-Erfolg — verlege das Loeschen der committeten Call/ConversationLog-Rows in einen POST-yield try/except-Block (analog test_rls_isolation.py:102-116) bzw. nutze `cleanup_rows({Call:[ids], ConversationLog:[ids]})`, sodass es AUCH bei Assertion-Fehler laeuft. Behalte das `Call.id.in_(ids)`-Scoping der Reader-Assertions (Delta-Review-2-Klasse).
    3. Beide bleiben echte Row-/Response-Reads (kein Source-Presence). Der Baseline-Waechter (Plan 01 Task 6) ist der Backstop: laeuft einer der beiden nicht baseline-sauber, faerbt der Waechter den schuldigen Test rot.
  </action>
  <verify>
    <automated>bash deploy.sh production 2>&1 | grep -E "test_per_sid_migration|test_dashboard_outcome_reminder|baseline|PASSED|passed|FEHLER"; echo "EXIT=$?"  # erwartet: beide PASSED + Baseline-Waechter gruen fuer sie (keine Leak-Rows in public.* nach dem Test).</automated>
  </verify>
  <done>
    test_per_sid_migration ist baseline-sauber (rollback-covered ODER cleanup_rows — im SUMMARY vermerkt welcher). test_dashboard_outcome_reminder raeumt seine committeten Call/ConversationLog-Rows GARANTIERT (post-yield, auch bei Fehler) via cleanup_rows weg; beide bestehen den public-Baseline-Waechter (kein Leak), keine globale unfiltered count-Assertion bleibt.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| committender Test → persistentes nerve_test (Baseline) | committete + nicht-aufgeraeumte Rows driften die Baseline → False-Green/Red; cleanup_rows + Baseline-Waechter (Plan 01) sind die Gegenmittel |
| Gruppe-A-Test → app-import-Baseline-Rows (FixedCost/PromptVersion) | unfiltered Summen / Re-Seed kollidieren mit der persistenten Baseline → Scoping / idempotenter Guard noetig |
| Plan-03 ∩ Plan-04 files_modified | flag3 (final 2026-06-16): DISJUNKT — NUR test_ab_stats ist Plan 03 (Task 9); test_per_sid_migration + test_dashboard_outcome_reminder sind Plan 04 (Task 7) → kein gemeinsamer Datei-Edit, same-wave parallel-sicher |
| stale Gruppe-C-Assert (6-vs-8) → Phase-Scope | out-of-scope eskaliert; darf NICHT maskiert (skip/xfail/assert-update) werden — bleibt sichtbar rot |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PGTEST-24 | Denial (False-Red/False-Green) | committende Gruppe-A/B-Tests lassen Rows in nerve_test liegen → Baseline-Drift → Folge-Tests kippen / RLS-Leak unsichtbar | mitigate | Jeder committende Test dieses Plans registriert seine Row-IDs + ruft cleanup_rows (Plan 01 Task 5, reverse-FK, crm.* unter Tenant-GUC, POST-yield) → DB==Baseline nach Teardown → autouse _baseline_cleanup_guard (Plan 01 Task 6) gruen. Cross-cutting Task 1 vereinheitlicht die Mechanik phasenweit. |
| T-PGTEST-26 | Denial (False-Red) | Gruppe-A-Tests (eur_calculator/ewb_pipeline/prompt_pipeline) brechen an der app-import-Baseline (unfiltered FixedCost-Summe / UNIQUE(version,module)-Re-Seed-Kollision) — Baseline-Row liegt VOR jeder Test-Transaktion, durch Isolation nicht entfernbar | mitigate | Task 2: FixedCost-Summe auf test-eigene/baseline-delta gescoped. Task 3: idempotenter check-then-insert-Guard / unique test-module-Name gegen UNIQUE(version,module). Per PERSISTENCE-ENUMERATION.md Gruppe A — Test-Fix unabhaengig von jeder Isolations-Strategie. |
| T-PGTEST-27 | Denial (Clobber) | gemeinsame Test-Datei in Plan 03 + Plan 04 files_modified → paralleler Same-Wave-Edit ueberschreibt einer den anderen | mitigate | RESOLVED via flag3 (final 2026-06-16): NUR test_ab_stats bleibt Plan 03 (Task 9). test_per_sid_migration + test_dashboard_outcome_reminder gehoeren Plan 04 (Task 7, in files_modified). Plan 04 files_modified ist DISJUNKT von Plan 03 → 03+04 same-wave parallel-sicher, kein Clobber moeglich. Plan 03's cleanup_rows-Adoption (inkl. ab_stats) ist via phasen-weite Direktive im Plan-03-Objective (2026-06-16) abgedeckt. |
| T-PGTEST-28 | Spoofing (Maskierung) | der stale Gruppe-C-Assert (6-vs-8 VALID_OUTCOMES) wird „gefixt"/geskippt/xfailed statt eskaliert → echter Pre-Existing-Bug verschwindet aus der Sicht (Req-7-Verletzung) | mitigate | Task 6: die 6-vs-8-Assertion bleibt UNANGETASTET (kein assert-Update auf 8, kein skip/xfail); im SUMMARY als Gruppe C / out-of-scope / vom Orchestrator separat eskaliert dokumentiert. Nur die committeten Rows des Tests kriegen cleanup_rows. |
</threat_model>

## 5. Persistenz-Schicht-Verifikation

### Angefasste Tabellen

- `public.fixed_costs` (lesen/aggregieren — test_eur_calculator; app-import-Baseline via _seed_founder_dashboard_defaults persistent → Scoping/Delta)
- `public.prompt_versions` (schreiben — test_ewb_pipeline/test_prompt_pipeline variant-Re-Seed; UNIQUE(version,module); app-import-Baseline via _seed_prompt_versions/_seed_ewb_v2)
- `public.{organisations,users,calls,conversation_logs,...}` (schreiben — Gruppe-B-Tests committen FK-Ketten; FK-Parents user/org id=1 via Base-Seed Plan 01 Task 4; cleanup_rows reverse-FK)
- `public.{exchange_rates,api_cost_log,revenue/subscription,profile_opener,model-Rows,reminder/outcome}` (schreiben — die jeweiligen Gruppe-B-Tests; cleanup_rows)
- ggf. `crm.*` falls ein Gruppe-B-Test crm beruehrt (dann cleanup_rows mit Tenant-GUC) — pro Test im read_first verifizieren

### Katalog-Beleg (zitiert aus PERSISTENCE-ENUMERATION.md + app.py + models.py)

Baseline-Contract (ENUMERATION): `from app import app` committet u.a. ApiRate+FixedCost
(_seed_founder_dashboard_defaults) + ~4-6 PromptVersion inkl. 2 ewb (_seed_prompt_versions/_seed_ewb_v2). →
fixed_costs + prompt_versions sind in der Baseline NICHT-leer → test_eur_calculator's unfiltered FixedCost-Summe
zieht Baseline-Rows rein (T-PGTEST-26), und test_ewb_pipeline/test_prompt_pipeline's Re-Seed kollidiert auf
UNIQUE(version,module) (T-PGTEST-26). PromptVersion UNIQUE(version,module) im read_first an models.py zu verifizieren.

cleanup_rows (Plan 01 Task 5) + _baseline_cleanup_guard (Plan 01 Task 6): die kanonische Teardown- +
Erzwinger-Mechanik; jeder committende Test dieses Plans haengt daran (T-PGTEST-24).

### Cross-Layer-Konsistenz-Tabelle

| Code-Variable / Feld | Lese-/Schreib-Pfad | Persistenz-Schicht | Verifiziert? |
|---|---|---|---|
| FixedCost-Summe (eur_calculator) | unfiltered → test-eigene/baseline-delta gescoped | DB-Tabelle public.fixed_costs (app-import-Baseline persistent) | ✓ ENUMERATION Gruppe A; Scoping/Delta |
| PromptVersion variant Re-Seed (ewb/prompt_pipeline) | check-then-insert / unique test-module statt blindem Insert | DB-Tabelle public.prompt_versions UNIQUE(version,module) (Baseline traegt module='ewb') | ✓ ENUMERATION Gruppe A; idempotenter Guard / unique module — models.py-Constraint verifizieren |
| committete Gruppe-B-Rows | cleanup_rows im POST-yield-Teardown | public.* (ggf. crm.* mit Tenant-GUC) | ✓ Vorbild test_rls_isolation.py:101-116; FK-Parents via Base-Seed |
| stale VALID_OUTCOMES (postcall_outcome_route:156) | Assertion 6-vs-8 — NICHT angefasst | (Test-Assertion, kein DB-Schreibpfad) | ✓ Gruppe C, out-of-scope, eskaliert (T-PGTEST-28) |
| _baseline_cleanup_guard Verifikation (PUBLIC.*-only) | autouse nach jedem Test | public-DB-State == Session-Start-Baseline | ✓ Plan 01 Task 6; jeder committende Test == public-Baseline nach Teardown |
| crm.* == 0 (POST-SUITE-Check) | deploy.sh (Plan 02) NACH pytest, VOR trap: `sudo -u postgres psql` summiert count(*) ueber crm.* | DB-State-Read (crm.* als postgres, RLS-bypassed) | ✓ HYBRID (André locked, Plan 02); jeder crm-Writer raeumt via cleanup_rows(tenant=...) auf 0 |

### Bei Diskrepanz: STOP + Replan
(z.B. eur_calculator weiter rot trotz Scoping → unfiltered-Pfad uebersehen → alle FixedCost-Aggregationen pruefen;
ewb/prompt_pipeline weiter UNIQUE-Bruch → Guard greift nicht / module-Name nicht unique → STOP; ein committender
Test bleibt public-Waechter-rot → cleanup_rows-Spec unvollstaendig (Tabelle/IDs fehlt) → STOP; POST-SUITE-crm-Check
(Plan 02) meldet crm.* != 0 → ein crm-Writer raeumte nicht via cleanup_rows(tenant=...) auf 0 → STOP, Tenant-GUC/IDs
ergaenzen; dieser Plan fasst doch eine NUR-Plan-03-Datei an (z.B. test_ab_stats)
→ STOP, files_modified-disjoint-Verletzung (flag3), gehoert in Plan 03; jemand „fixt" die 6-vs-8-Assertion → STOP,
Gruppe C bleibt unberuehrt + eskaliert)

<verification>
- Gruppe A (T-PGTEST-26): test_eur_calculator (Summe gescoped) + test_ewb_pipeline/test_prompt_pipeline (idempotenter Guard / unique module) PASSED im Gate; kein UNIQUE(version,module)-Bruch, kein Baseline-FixedCost-Poison.
- Gruppe B (T-PGTEST-24): die ~7 Akkumulations-Tests dieses Plans (admin_dashboard_auth, exchange_rates, profitability, auth_next_redirect, models_04_7_2, revenue_webhook, 08_20_3) raeumen via cleanup_rows auf → _baseline_cleanup_guard (public.*-only) gruen + crm.* == 0 (POST-SUITE Plan 02). PLUS in diesem Plan (Task 7): per_sid_migration + dashboard_outcome_reminder. NICHT in diesem Plan: ab_stats (Plan-03-Task 9, flag3).
- Gruppe C (T-PGTEST-28): test_postcall_outcome_route:156 (6-vs-8) UNANGETASTET — `grep VALID_OUTCOMES tests/test_postcall_outcome_route.py` zeigt die alte Assertion unveraendert; im SUMMARY als eskaliert dokumentiert; die UEBRIGEN postcall_outcome_route-Tests gruen + baseline-sauber.
- Cross-cutting (Task 1): kein committender Test mit ad-hoc-DELETE ohne cleanup_rows (grep); Adoptions-Matrix im SUMMARY.
- Konflikt (T-PGTEST-27, RESOLVED via flag3): Plan 04 files_modified ist DISJUNKT von Plan 03 — NUR test_ab_stats bleibt Plan 03 (Task 9); test_per_sid_migration + test_dashboard_outcome_reminder gehoeren Plan 04 (Task 7); kein gemeinsamer Datei-Edit → 03+04 same-wave parallel-sicher. Plan 03 cleanup_rows-Adoption via phasen-weite Direktive im Plan-03-Objective.
- Baseline-Waechter-Konformitaet: im EINEN Gate-Lauf (MED-3, nach Commit aller 4 Plaene) ist _baseline_cleanup_guard (public.*-only, Plan 01 Task 6) fuer JEDEN committenden Test gruen (public-DB==Baseline nach Teardown) UND der POST-SUITE-crm-Check (Plan 02) meldet crm.* == 0 — kein faelschlicher Drift-FAIL.
- Req-7: echte Klasse-C/E-Bruche eskaliert (SUMMARY), nicht still gepatcht/geskippt.
</verification>

<success_criteria>
- Gruppe-A-Rest (eur_calculator/ewb_pipeline/prompt_pipeline) gegen die persistente Baseline gehaertet: unfiltered FixedCost-Summe auf test-eigene/baseline-delta gescoped; ewb/variant-Re-Seed idempotent (check-then-insert / unique test-module-Name) statt UNIQUE(version,module)-Kollision.
- Gruppe-B-Rest (admin_dashboard_auth/exchange_rates/profitability/auth_next_redirect/models_04_7_2/revenue_webhook/08_20_3/dashboard_outcome_reminder/per_sid_migration/ab_stats) raeumen ihre committeten Rows via cleanup_rows im POST-yield-Teardown weg; globale Aggregationen auf test-eigene/baseline-delta gescoped.
- test_postcall_outcome_route: committete Rows via cleanup_rows weggeraeumt (Gruppe B); die stale 6-vs-8 VALID_OUTCOMES-Assertion (:156) UNANGETASTET (Gruppe C, vom Orchestrator separat eskaliert — kein assert-Update, kein skip/xfail).
- CROSS-CUTTING: kanonische cleanup_rows-Adoption phasenweit (auch Plan-03-Tests auf den Helfer umgestellt, in der jeweiligen Datei/Plan — kein Clobbern von Plan 03); Adoptions-Matrix im SUMMARY.
- Jeder committende Test dieses Plans ist nach seinem Teardown == public-Baseline → autouse _baseline_cleanup_guard (Plan 01 Task 6, PUBLIC.*-only) GRUEN, kein Drift-FAIL; UND seine crm.*-Rows == 0 → POST-SUITE-crm-Check (Plan 02, sudo-postgres) GRUEN.
- files_modified DISJUNKT von Plan 03 (flag3): NUR test_ab_stats bleibt Plan 03 (Task 9); test_per_sid_migration + test_dashboard_outcome_reminder gehoeren Plan 04 (Task 7) → kein paralleler Same-Wave-Edit, 03+04 parallel-sicher. Plan 03 cleanup_rows-Adoption via phasen-weite Direktive im Plan-03-Objective.
- Alle Assertions bleiben echte Runtime-Row-/Response-/Stats-Reads (CLAUDE.md, keine Source-Presence). Echte App-Bugs (Klasse C/E) eskaliert, nicht maskiert (Req-7).
- MED-3: validiert durch GENAU EINEN deploy.sh production-Lauf NACH Commit aller 4 Plaene (kein Zwischen-Deploy).
</success_criteria>

<output>
After completion, create `.planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-04-SUMMARY.md`
</output>

########## DATEI: database/db.py ##########
import os
import sqlite3
import contextvars
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, scoped_session

# Resolve relative SQLite paths relative to project root
_DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database/nerve.db')

if _DATABASE_URL.startswith('sqlite:///') and not _DATABASE_URL.startswith('sqlite:////'):
    _rel = _DATABASE_URL[len('sqlite:///'):]
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _abs  = os.path.join(_root, _rel)
    os.makedirs(os.path.dirname(_abs), exist_ok=True)
    _DATABASE_URL = f'sqlite:///{_abs}'

_connect_args = {'check_same_thread': False} if 'sqlite' in _DATABASE_URL else {}
engine = create_engine(_DATABASE_URL, connect_args=_connect_args)

# ── Enable WAL mode for SQLite (concurrent reads + writes under threading) ─────
if 'sqlite' in _DATABASE_URL:
    @event.listens_for(engine, 'connect')
    def set_wal_mode(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()

# ── Test-only: SQLite-Schema-Emulation fuer crm.* / training.* ─────────────────
# Die crm-/training-Modelle (models.py) sind __table_args__ {'schema': 'crm'|'training'}.
# SQLite kennt keine Schemas -> Base.metadata.create_all() wirft "unknown database crm"
# und bricht das deploy.sh-Pytest-Gate schon bei der COLLECTION (jeder Test, der app/models
# importiert). Wir ATTACHen pro SQLite-Verbindung eine In-Memory-DB namens crm/training, sodass
# schema-qualifiziertes create_all + alle Queries aufloesen (generalisiert das StaticPool+ATTACH-
# Muster aus test_account_memory_briefing.py / test_anonymizer_worker.py auf JEDE SQLite-Engine —
# auch die im Test-Suite-Code separat erzeugten). Die crm/training-Modelle tragen ausschliesslich
# Soft-Links (KEIN FK, D-08/D-17) -> create_all emittiert keine cross-database REFERENCES.
# GLOBAL auf der Engine-Klasse registriert (nicht nur auf der Modul-Engine), damit es Test-Engines
# aus conftest/tests/ ebenfalls erfasst. Postgres-Verbindungen sind psycopg2, kein sqlite3.Connection
# -> unberuehrt (echte Schemas in Produktion).
@event.listens_for(Engine, "connect")
def _sqlite_attach_crm_training_schemas(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        try:
            cur.execute("ATTACH DATABASE ':memory:' AS crm")
            cur.execute("ATTACH DATABASE ':memory:' AS training")
        finally:
            cur.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionLocal)


# ── Phase 08.23.2.G-MEET Wave 2 — Multi-Tenant RLS GUC plumbing (D-11, D-12.1, D-12.3) ──
# The crm.* RLS policies filter on current_setting('app.tenant_id', true)::uuid. We publish the
# request/thread tenant UUID into a contextvar, and a SQLAlchemy Session `after_begin` hook issues
# a TRANSACTION-LOCAL set_config('app.tenant_id', <uuid>, true) at transaction start. Because the
# SET fires when the transaction begins (BEFORE its queries), the SET and the tenant-scoped queries
# share ONE transaction by construction (fixes B-1 connection-affinity). set_config(...,true) is
# SET LOCAL: it clears AUTOMATICALLY at COMMIT/ROLLBACK -> NO checkin RESET needed, pooler-agnostic
# (immune if a pooler is ever added, e.g. 08.23.2.STAGING), and safe for out-of-request worker
# threads (the GUC lives only for the worker's own transaction).
_current_tenant_id = contextvars.ContextVar("nerve_tenant_id", default=None)


def set_current_tenant(tid):
    """Publish the active tenant UUID (string) for the current request/thread.

    Called from before_request (request path) AND by any worker thread before its session work
    (so the after_begin hook can issue the transaction-local SET on the worker's own transaction).
    """
    _current_tenant_id.set(tid)


def clear_current_tenant():
    """Reset the contextvar (hygiene). The actual tenant control is the transaction-local SET,
    which auto-clears at COMMIT/ROLLBACK -- this only prevents the contextvar surviving into the
    next request on a reused thread."""
    _current_tenant_id.set(None)


# Postgres-only: SQLite has no set_config / RLS, so the in-memory test schema is unaffected
# (inverse of the SQLite WAL hook above).
if 'sqlite' not in _DATABASE_URL:
    @event.listens_for(SessionLocal, "after_begin")
    def _set_tenant_txn_local(session, transaction, connection):
        # Fires when a transaction begins, BEFORE its queries, on the SAME connection
        # => the GUC is transaction-local for exactly the queries that follow.
        tid = _current_tenant_id.get()
        if not tid:
            # No tenant context (pre-login / static / worker w/o tenant) -> GUC unset
            # -> current_setting('app.tenant_id', true) is NULL -> RLS fails closed (0 rows).
            return
        # Third arg true = transaction-local (SET LOCAL). PARAMETERIZED (bound param) ->
        # SQL-injection-safe (T-G2-05): never f-string/%-format the UUID into SQL.
        # NOTE: NO `RESET app.tenant_id` / checkin listener exists -- transaction-local
        # auto-clears at COMMIT/ROLLBACK, so a returned/reused connection carries no residual
        # tenant GUC (T-G2-03 solved by construction).
        connection.exec_driver_sql(
            "SELECT set_config('app.tenant_id', %s, true)", (str(tid),)
        )


class Base(DeclarativeBase):
    pass


# Alias so routes can do: from database.db import db
db = Base


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_session():
    """Returns a new DB session (for use outside request context)."""
    return SessionLocal()

########## DATEI: .planning/phases/08.23.2.PGTEST-echtes-postgres-test-gate/08.23.2.PGTEST-PERSISTENCE-ENUMERATION.md ##########
# PGTEST — Persistenz-Annahmen-Enumeration (alle 64 Test-Files)

**Erstellt:** 2026-06-15 · **Zweck:** Architektur-Weiche Test-Isolation (André STEP 1). Wahre Größe + Klassifikation, BEVOR Flick-vs-Wurzel entschieden wird. **Noch kein Fix, kein conftest-Change committet.**

## Methode
8 parallele Read-only-Klassifizierer über alle 64 `tests/test_*.py`. Pro Test: läuft-gegen-PG? · Annahme-Typ · Verdikt (SAFE / TARGETED-A / SYSTEMIC / REAL-BUG-B) · **Diskriminator: löst Option-2 (Per-Test-Transaktions-Rollback-Isolation) es, oder braucht es einen Test-Fix UNABHÄNGIG?**

## Baseline-Contract (was persistent in nerve_test liegt, BEVOR ein Test-Body läuft)
`from app import app` führt MODUL-TOP-LEVEL-Seeder aus, die committen: demo Organisation+User (`_seed` app.py:1724), ApiRate+FixedCost (`_seed_founder_dashboard_defaults` :1130), ~4-6 PromptVersion inkl. 2 ewb (`_seed_prompt_versions`/`_seed_ewb_v2` :1196/:1316), TrainingScenario (`_seed_training_scenarios`+`_seed_system_training_scenarios` :1869/:1994), Changelog (`_seed_changelog` :2081), + tenant_orgs via Trigger. PLUS Base-Seed (Org+User id=1). → NICHT-leer: organisations, users, tenant_orgs, api_rates, fixed_costs, prompt_versions, training_scenarios, changelog.

## Ergebnis (64 Files)

### ~40 SAFE (kein Handlungsbedarf)
Pure-Logic / gemockte DB / eigene sqlite-Engine / read-only / by-design-PG-Security-Fixtures (test_rls_isolation, test_meeting_save_rls, test_schild_guard, test_anonymizer_worker RLS-Gruppe — bleiben auf Real-Commit-Pfad, opt-out).

### Gruppe A — NEEDS-TARGETED UNABHÄNGIG von Isolation (~6) ← der harte Kern
Diese brechen, weil die Konflikt-Row im **persistenten Baseline** liegt (app-import/base-seed committed VOR jeder Test-Transaktion) → Rollback-Isolation kann sie NICHT entfernen. Brauchen einen Test-Fix egal welche Strategie:
- **test_ft_seed.py:29** — global `query(PromptVersion).count()==4`, Baseline hat ~6 → scope auf EXPECTED_MODULES / baseline-delta.
- **test_tenant_orgs.py:65** — global `count()==3` + `_seed_tenant_orgs` iteriert ALLE orgs → scope auf test-eigene IDs.
- **test_eur_calculator.py** — unfiltered FixedCost-Summe zieht Baseline-FixedCosts rein → vor-löschen/scope/delta.
- **test_cost_tracker.py** — `filter_by(provider='anthropic').first()` greift evtl. Baseline-ApiRate → `filter_by(provider, model='haiku-test')`.
- **test_ewb_pipeline.py** + **test_prompt_pipeline.py** — `_seed_ewb_variants`/`_seed_variants` re-inserten module='ewb' (version) die Baseline schon hat → UNIQUE(version,module)-Kollision → idempotenter Guard / unique module-Name.

### Gruppe B — ISO-FIXES (Option-2-Rollback allein löst es, KEIN Test-Edit) (~8-10)
Brechen nur durch AKKUMULATION (own-session-commit / cross-test). Proper Option-2 (ALLE Sessions inkl. code-`get_session()` auf EINE Connection + Savepoint-Rollback) räumt sie ohne Test-Änderung:
test_ab_stats, test_admin_dashboard_auth, test_ewb_rate_api, test_exchange_rates, test_per_sid_migration, test_profitability, test_auth_next_redirect (unique-email re-seed), test_models_04_7_2, test_revenue_webhook, test_08_20_3, test_postcall_split, test_profile_editor_validation, test_dashboard_outcome_reminder.
*(Voraussetzung: Option-2 MUSS code-seitige `SessionLocal()`-Commits einfangen — sonst fallen diese in Gruppe A. Das ist der „join-external-transaction"-Pattern-Punkt.)*

### Gruppe C — echte Pre-Existing-Bugs (nicht Persistenz, eskalieren) (~1-2)
- **test_postcall_outcome_route.py:156** — `test_valid_outcomes_match_check_constraint` asserted die ALTEN 6 Outcome-Werte, `VALID_OUTCOMES` hat jetzt 8 (`send_info`, `gatekeeper_blocked`) → bricht auf JEDEM Backend (sqlite wie PG). Echter Test-Bug, unabhängig von dieser Phase → eskalieren/separat fixen.
- (Hinweis: `calls.user_id=999/42` dangling ist KEIN Problem — FK ist laut models.py:682 auf Phase 08.23.2.F deferred, also aktuell nicht enforced.)

## Diskriminator-Bilanz (der Entscheidungs-Kern)
- **Proper Option-2 Isolation** löst Gruppe B (~8-10 Tests) MIT NULL Test-Edits + macht den Base-Seed + die meisten FK-Debt-Einzelfixes überflüssig (Tests rollen ihre eigenen Parents zurück, brauchen keine committed Foundation — Detail: user_id=1-Tests brauchen evtl. weiter EINE committed Baseline-User-Row).
- **Gruppe A (~6) braucht Test-Fixes EGAL welche Strategie** — Baseline-Konflikte sind durch Isolation nicht lösbar.
- **Gruppe C (~1-2)** sind echte Bugs → eskalieren.
- **Security-Tests** bleiben auf ihrem Real-Commit-Pfad (eigene psycopg2-Fixtures, opt-out) — kompatibel mit Option-2.

## Empfehlung (Daten-gestützt, deckt sich mit André-Hypothese)
**Wurzel-Fix = Proper Option-2 (Per-Test-Transaktions-Isolation, generischer Pfad)** + die ~6 Gruppe-A-Tests gezielt fixen + die ~1-2 Gruppe-C-Bugs eskalieren. Vorteile: löst die Akkumulations-Klasse systemisch (nicht-konvergierendes Whack-a-Mole endet), macht Base-Seed + viele FK-Ports überflüssig, Security-Tests unberührt. **Kosten:** conftest-Refactor (alle Sessions inkl. code-`get_session()` an EINE Connection binden = „join external transaction"-Pattern) — nicht trivial, aber Industrie-Standard für pytest-gegen-PG.

**Alternative (reiner Targeted-Fix, kein Isolations-Refactor):** ~16-18 Tests einzeln härten + Base-Seed behalten → mehr Edits, fragiler, das Whack-a-Mole-Risiko bleibt (jede Runde fand neue Mitglieder).

**Offen für STEP 2:** Gemini-3.-Sicht auf die Architektur-Wahl (read-only); dann André entscheidet.
