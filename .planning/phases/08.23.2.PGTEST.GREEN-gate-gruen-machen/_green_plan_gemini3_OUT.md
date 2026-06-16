**ADVERSARIAL PLAN-RE-REVIEW (RUNDE 3) — Phase 08.23.2.PGTEST.GREEN**

### TEIL 1 — Verifikation der Runde 2 Funde

*   **#5 BLOCKER (triage.sh Forwarding): OK.** Das Konstrukt `bash -c '... pytest "$@"' _ "$@"` bindet das äußere Argument-Array perfekt an die innere Subshell. `_` belegt `$0`, und die echten Argumente wandern in `$1` etc. Targeted Runs funktionieren damit.
*   **#6 HOCH (Composite-PK): NICHT GANZ OK.** (Siehe neuen Fund 2 unten). Der Crash/Over-Deletion ist behoben, aber der Plan reißt durch den Ausschluss ein unbemerktes Loch auf und lügt über dessen Sicherheit.
*   **#7 MITTEL (Cache-Init Ordering): OK.** Die Fixture-Dependency `_baseline_snapshot(..., _baseline_schema)` ist eine harte Garantie. Der Modul-Cache ist bei Session-Start nachweislich gefüllt, bevor ein Fallback triggern kann.
*   **#1-#4 (aus Runde 1): OK.** Kanten-Einschluss, PK-Derivation und crm-Count sind intakt. PATTERNS.md ist konsistent.

---

### TEIL 2 — Frischer adversarialer Sweep (NEUE FUNDE)

**[BLOCKER] — Datei: tests/conftest.py + tests/_schema_introspect.py (Plan 01) — Cross-Schema FK Violation in cleanup_rows**
*   **Problem:** `conftest.py` ruft `derive_baseline_tables(schema='public')` auf. Der Modul-Cache `_DERIVED_FK_ORDER` enthält somit *ausschließlich* `public.*` Tabellen.
*   **Warum:** Die Teardown-Funktion `cleanup_rows` wird von Tests genutzt, um `crm` UND `public` Zeilen abzuräumen. Da `crm`-Tabellen im public-only Cache fehlen, fallen sie in den Fallback-Bucket (`ordered += [t for t in norm if t not in _DERIVED_FK_ORDER]`) und werden ganz ans ENDE der Löschliste gehängt. `crm`-Tabellen haben aber Foreign Keys auf `public`-Tabellen (z.B. `crm.accounts` -> `public.tenant_orgs`). `public` wird nun zuerst gelöscht -> **Harte FK-Violation**. Jeder generische Test, der crm- und public-Daten aufräumt, crasht. Die alte hardcoded `_CLEANUP_FK_ORDER` verhinderte das, weil sie `crm.*` explizit *vor* `public.*` sortierte. Zudem kennt `_DERIVED_PK_COLS` keine crm-Tabellen, was bei non-id-PKs in crm ebenfalls zum Crash führt.
*   **Fix:** `derive_baseline_tables` muss (analog zum SCHILD-Guard) ein Tuple von Schemas akzeptieren: `n.nspname IN %s` (z.B. `('public', 'crm', 'training')`). `conftest.py` initialisiert den Cache für ALLE diese Schemas, damit die globale FK-Order stimmt. Für den Snapshot-Wächter filtert `conftest.py` die zurückgegebene `table_list` einfach lokal: `[t for t in table_list if t.startswith('public.')]`.

**[HOCH] — Datei: 08.23.2.PGTEST.GREEN-01-introspect-autoreset-PLAN.md (Plan 01) — False Green Blindspot bei Composite PKs**
*   **Problem:** Plan 01 schließt Composite-PK-Tabellen aus der `baseline_table_list` aus. Gleichzeitig behauptet der Plan in der THEMA-KLAMMER R2 explizit: *"Ein dortiger Leak wuerde stattdessen ueber den missing/mutated-bzw.-Snapshot-Pfad sichtbar"*.
*   **Warum:** Diese Behauptung ist technisch unmöglich. Wenn eine Tabelle nicht in der `baseline_table_list` ist, iteriert `_snapshot_public_tables` überhaupt nicht über sie. Sie fehlt im `current` und im `baseline` Dict. `_diff_baseline` sieht sie niemals. Eine Composite-PK-Tabelle ist damit ein komplett blindes Loch für Leaks und Mutationen (False Green).
*   **Fix:** Ehrlich sein. Da `_snapshot_public_tables` aktuell einen Single-Column PK als Key im Dict nutzt, kann es Composite-PKs ohne Umbau nicht snapshotten. Wenn die Tabelle ausgeschlossen wird, muss der Plan das offen als "Bekannte Tor-Lücke: Composite-PK-Tabellen werden vorerst nicht überwacht" im Foundation-Register dokumentieren. Die falsche Behauptung der Snapshot-Sichtbarkeit muss raus. Alternativ: `_snapshot_public_tables` so umbauen, dass es bei Composite-PKs alle Spalten als Tuple-Key verwendet.

---

### GESAMT-VERDIKT

**BLOCK**
**Risiko:** HIGH. Die public-only Schema-Ableitung zerschießt die Test-Teardowns der gesamten Suite für das crm-Schema massiv. Ohne Korrektur dieses Blockers läuft die Pipeline sofort in harte FK-Violations. Fixe den Cross-Schema-Support und bereinige den False-Green Widerspruch bei den Composite-PKs.
