---
status: partial
trigger: "Phase 08.23.2.PGTEST.GREEN — drei Wave-1-3-Code-Bugs, empirisch via deploy.sh production gefangen (eigene Tests rot). Kein Local-Dev (HART): Re-Run-Validierung laeuft server-side via deploy.sh production / triage.sh durch Claudian."
created: 2026-06-16
updated: 2026-06-16
phase_ref: 08.23.2.PGTEST.GREEN
multisegment_note: "Pfad hartkodiert .planning/phases/08.23.2.PGTEST.GREEN-gate-gruen-machen/ (gsd-tools misresolved 08.23.2)"
---

# Debug: PGTEST.GREEN Wave-1-3 Bugs (3 Reste nach Claudian-Fix 4a3771d)

Vorlauf: EIN Bug bereits gefixt (Claudian 4a3771d — derive_baseline_tables strippt confdeltype
VOR _kahn_topo_sort, das jetzt 2-Tupel nimmt; test_schema_introspect 01/02/03 gruen).
Methode: Logging-First, nicht raten. Empirischer Re-Run = deploy.sh production (Server, kein local pytest).

## Current Focus

hypothesis: Bug 1 sicher gefixt; Bug 2 + Bug 3 brauchen EINEN empirischen Server-Lauf zur Diagnose-Bestaetigung (Instrumentierung gesetzt).
next_action: Claudian faehrt deploy.sh production -> die neuen [PGTEST-INTROSPECT]-Logzeilen liefern die Evidenz fuer Bug 2 (Modul-Identitaet + Fill-Laengen) und Bug 3 (Zyklus-Kern-Kanten). Danach gezielter Fix.

---

## Bug 1 — test_schema_introspect::test_05 (TEST-BUG) ✅ GEFIXT

root_cause: Assertion suchte Singular `'public.objection_event'`; echter Tabellenname ist
`objection_events` (Plural — bewiesen: database/models.py:407 `__tablename__ = 'objection_events'`).
derive lieferte korrekt `public.objection_events`, Assertion verfehlte -> rot.
fix: Assertion + Test-Name + Docstring auf `objection_events` (Plural) korrigiert (test_schema_introspect.py).
verification: py_compile OK; grep bestaetigt 0 verbleibende Singular-Assertions. Voll-Gruen via naechstem deploy.sh-Lauf.
status: resolved

## Bug 2 — test_baseline_autoreset test_01 + test_06 (CACHE-EMPTY) ✅ GEFIXT (commit 0d0ffab)

ROOT-CAUSE (empirisch via scripts/triage.sh, NICHT die instrumentierte Vermutung): die PK-Katalog-Abfrage
im SQLAlchemy-Zweig von `_fetch_pk_for_table` (+ Duplikat `primary_key_column`) mischte named-param + Cast:
`WHERE i.indrelid = :tbl::regclass`. Ueber eine SQLAlchemy-Connection (`_baseline_guard_engine.connect()`)
-> `psycopg2: syntax error at or near ":"` -> JEDE ~45 Tabellen wirft -> pk_count=0 -> alles in
foundation_register ("no watchable PK") -> baseline_table_list + _DERIVED_PK_COLS LEER -> Cache leer.
Die instrumentierte DUAL-MODULE-Hypothese war FALSCH; das Fill-Log haette len(pk_cols)=0 gezeigt (PK-PASS-FAIL).
Nur der SQLAlchemy-Pfad (conftest) war betroffen; test_schema_introspect (psycopg2-DSN) traf den
funktionierenden %s::regclass-Zweig -> gruen.
fix: SQLAlchemy-Zweig auf inline f-string `'{qualified}'::regclass` (Muster aus _fetch_fk_edges,
injection-sicher), Duplikat konsolidiert (_fetch_pk_for_table delegiert an primary_key_column).
verification: py_compile OK; grep 0 verbleibende `:tbl::regclass`-SQL. Voll-Gruen via triage.sh/deploy.sh.
status: resolved

### (historisch) Bug 2 — vorherige Instrumentierungs-Phase

symptom: `_DERIVED_PK_COLS`/`_DERIVED_FK_ORDER` erscheinen dem Test leer ({}/[]) nach Session-Start
-> cleanup_rows faellt still auf `_CLEANUP_FK_ORDER` zurueck (Fund-#7-Meta-False-Green).

statisch widerlegte Annahme: "_baseline_schema laeuft nicht". FALSCH — der autouse
`_baseline_cleanup_guard` (conftest.py:459) haengt an `_baseline_snapshot` (435) -> `_baseline_schema` (370);
beide Tests fordern `_baseline_snapshot` zusaetzlich explizit an. Die session-scoped Fixture LAEUFT also
garantiert vor test_01/test_06. Und derive LAEUFT (Bug-3-Zyklus-Warnung beweist einen 38-Knoten-Lauf).

drei verbliebene Hypothesen (statisch nicht entscheidbar ohne Lauf):
  (a) DUAL-MODULE: pytest laedt conftest doppelt (`conftest` + `tests.conftest`) -> `global`-Rebind
      in _baseline_schema landet in EINEM Modul, der Test liest via `import tests.conftest` das ANDERE.
  (b) EMPTY-DERIVE: derive lieferte leere Listen (unwahrscheinlich — Zyklus-Warnung zeigt 38 Knoten).
  (c) PK-PASS-FAIL: zweiter Pass (_fetch_pk_for_table) baute kein pk_cols.
instrumentation: _baseline_schema (conftest.py) loggt jetzt nach dem Fill: `__name__`, `id(self)`,
  `sys.modules['conftest']`/`['tests.conftest']`-ids + DUAL_MODULE-Flag, und len(table_list/fk_order/pk_cols).
  -> der naechste Lauf unterscheidet (a)/(b)/(c) eindeutig.
status: instrumented — awaiting empirical evidence

## Bug 3 — _kahn_topo_sort Zyklen auf echtem Schema ✅ FIX ANGEWENDET (awaiting triage.sh-Bestaetigung)

ROOT-CAUSE (empirisch via triage.sh, instrumentierte Diagnose hat geliefert): das reale Schema hat
ECHTE MUTUAL-FK-2-ZYKLEN: public.users<->public.organisations UND public.users<->public.profiles.
Kahn setzt DAG voraus -> die SCC {users,organisations,profiles} + ALLES transitiv davon Abhaengige
(36/43, inkl. alle crm.* via accounts->tenant_orgs->organisations) blieben "Rest" und wurden
alphabetisch ans Ende gehaengt. Nach dem `reversed()` landete public.tenant_orgs VOR crm.accounts
-> test_06-Assertion (crm vor public) rot + FK-Violation-Risiko beim Cleanup.

FIX (Design (A)+(B), nerve_app ohne Superuser):
  (A) _schema_introspect._kahn_topo_sort zyklus-bewusst: bei leerer Queue + Rest-Knoten wird EINE
      Zyklus-Kante bewusst gebrochen (Rest-Knoten mit kleinstem residualem reverse_in_degree
      freigegeben, geloggt), dann Kahn fortgesetzt. ALLE Nicht-Zyklus-Kanten (inkl. cross-schema
      crm->public) bleiben erhalten -> crm-vor-public-Order korrekt (test_06 gruen); nur INNERHALB
      eines Mutual-Paares keine perfekte Order.
  (B) conftest._fk_safe_delete_rows (NEU): FK-violation-robustes Loeschen — SAVEPOINT pro Tabelle
      (SQLAlchemy begin_nested / psycopg2 SAVEPOINT), FK-Violation rollt nur den Savepoint zurueck,
      fehlgeschlagene Tabellen werden in Folge-Runden erneut versucht bis 0 Fortschritt. Loest Zyklen
      OHNE Superuser/session_replication_role/DEFERRABLE. Beide DELETE-Pfade (autouse-Waechter
      Auto-Delete + cleanup_rows) routen jetzt durch den Helfer (Duplikat-Delete-Loops entfernt).
  Option (C) session_replication_role=replica verworfen (braucht Superuser, nerve_app hat das nicht).
HARD-STALL (Q3, selbst aufgeloest, da Gemini-CLI headless nicht lief): Retry-Loop reicht fuer
Test-Row-Cleanup (Test-Rows referenzieren ~nie einander; echte mutual-referencing Rows sind ohne
DEFERRABLE gar nicht einfuegbar). Bei dennoch-Stall: laute Warnung + missing/mutated-Guard/POST-SUITE
bleiben fail-closed Backstop. KEIN NULL-FK-Hack noetig.
NEBENFIX: _CLEANUP_FK_ORDER-Fallback-Typo public.objection_event -> objection_events korrigiert.
verification: py_compile OK; grep bestaetigt cycle-break + Helfer-Wiring beider Pfade. Voll-Gruen +
keine-FK-Violation via Claudian-triage.sh test_06 (Server). Gemini-3.-Sicht-Konsult vorbereitet
(_green_bug3_gemini_PROMPT.md im Phasen-Verzeichnis), CLI lief headless nicht -> optional interaktiv.
status: fix-applied (awaiting empirical triage.sh confirmation)

KORREKTUR (Gemini-3.1-Pro 3.-Sicht, _green_bug3_gemini_OUT.md, Punkt-24-Beleg): der erste (A)-Brecher
waehlte das Opfer per min(reverse_in_degree) = ein BLATT (crm.accounts) -> als Root frueh -> nach
reversed() spaet -> crm.accounts HINTER public.tenant_orgs -> eine legitime Nicht-Zyklus-Kante
(accounts->tenant_orgs) invertiert -> test_06 weiter rot + FK-Risiko. FIX: victim = max(blockierte
Rest-Kinder) = der echte Zyklus-HUB (organisations) als Root -> spaet geloescht, nur eine Intra-SCC-Kante
(organisations->users) gebrochen, alle cross-schema-Kanten erhalten -> crm-vor-public -> test_06 gruen.
test_06 bewusst NICHT gelockert (Gemini: Maskieren). Quick-Task 20260616-bug3-cycle-breaker-hub.

### (historisch) Bug 3 — vorherige Instrumentierungs-Phase

symptom: `[PGTEST-INTROSPECT] 31 Knoten mit Zyklen ans Ende angehaengt` auf dem echten public-Schema.
Unit-Tests (kleine Graphen) gruen, aber 31/38 Rest riecht nach echtem Mutual-FK-Zyklus nahe einem
Root-Hub (z.B. organisations<->users), der den ganzen Teilbaum blockiert.

ausgeschlossen (statisch): Richtungs-/Strip-Fehler aus 4a3771d. derive Z.266 strippt sauber
`[(c, p) for c, p, _ in fk_edges]` (child/parent-Reihenfolge erhalten). Ein globaler Swap wuerde nur
die ORDER drehen, KEINE Zyklen erzeugen. 31/38 = echte gegenseitige Erreichbarkeit, kein Direction-Bug.
FK-Risiko: eine falsche/Zyklus-Restorder ist NICHT garantiert Kind-vor-Eltern -> cleanup_rows koennte
auf dem echten Schema eine FK-Violation werfen. MUSS gefixt werden, auch wenn Bug 2 separat geloest wird.
instrumentation: _kahn_topo_sort (_schema_introspect.py) dumpt bei `remaining` jetzt 3 Sichten:
  (a) Kern-Kanten child->parent (beide im Rest) = der Zyklus-Kern,
  (b) Rest-reverse_in_degree>0 = wie viele Eltern noch haengen,
  (c) FK-Eltern pro Rest-Knoten.
  -> der naechste Lauf zeigt den ECHTEN Zyklus-Kern; Fix dann gezielt (Mutual-FK brechen, z.B. via
  NULLable-FK-Erkennung oder bewusstes Kanten-Drop fuer den Zyklus-Kern).
status: instrumented — awaiting empirical evidence

---

## Evidence

- timestamp: 2026-06-16 — models.py:407 `__tablename__ = 'objection_events'` (Plural) -> Bug 1 Root-Cause bewiesen (statisch).
- timestamp: 2026-06-16 — derive Z.266 `[(c, p) for c, p, _ in fk_edges]` -> Bug-3-Direction-Swap statisch ausgeschlossen.
- timestamp: 2026-06-16 — autouse-Kette conftest.py:459->435->370 -> "_baseline_schema laeuft nicht"-Annahme statisch widerlegt (Bug 2).

## Eliminated

- hypothesis: Bug 3 = Direction-/Strip-Fehler aus 4a3771d -> ELIMINIERT (Z.266 erhaelt child/parent-Order; Swap erzeugt keine Zyklen).
- hypothesis: Bug 2 = "_baseline_schema laeuft fuer diese Tests nicht" -> ELIMINIERT (autouse-Dependency-Kette erzwingt den Lauf).
