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

## Bug 2 — test_baseline_autoreset test_01 + test_06 (CACHE-EMPTY) 🔬 INSTRUMENTIERT

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

## Bug 3 — _kahn_topo_sort 31 Zyklen auf 38-Tabellen-Schema 🔬 INSTRUMENTIERT

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
