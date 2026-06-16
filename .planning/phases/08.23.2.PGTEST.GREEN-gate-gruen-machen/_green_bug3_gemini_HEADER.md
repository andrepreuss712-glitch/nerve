# CROSS-AI DESIGN-REVIEW — Mutual-FK-Cleanup-Strategie (Phase 08.23.2.PGTEST.GREEN, Bug 3)

Du bist Senior-Datenbank/Test-Infrastruktur-Engineer und unabhängige 3. Sicht. Lies den echten Code unten + entscheide eine konkrete Design-Frage. Sei kritisch, NICHT der Autor.

## Kontext
Ein Postgres-Deploy-Tor hat einen Auto-Reset-Wächter: nach jedem Test werden test-erzeugte EXTRA-Rows (Lecks) gelöscht, damit die geteilte Wegwerf-DB sauber bleibt. Dafür braucht es eine reverse-FK-Lösch-Reihenfolge (Kind vor Eltern), abgeleitet via topo-Sort aus pg_constraint über mehrere Schemas (public + crm).

## Das Problem (empirisch, am echten 43-Tabellen-Schema)
Das reale Schema hat **Mutual-FK-2-Zyklen** (rein intra-public): `users <-> organisations` und `users <-> profiles`. Ein reiner Kahn-topo-Sort setzt einen DAG voraus → diese Zyklen blockieren ihn → 36/43 Tabellen blieben "Reste".

GSD hat das mit ZWEI Mechanismen adressiert (beide im Code unten):
- **(A) zyklus-bewusster topo-Sort** (`_kahn_topo_sort`): bei leerer Queue + Rest wird eine Zyklus-Kante bewusst gebrochen (Rest-Knoten mit kleinstem residualem reverse_in_degree), dann Kahn fortgesetzt.
- **(B) FK-sicherer Cleanup-Retry-Loop** (`_fk_safe_delete_rows`): Savepoint pro Tabelle + Retry bis 0 Fortschritt; eine FK-Violation rollt nur den Savepoint zurück. BEIDE Lösch-Pfade (Auto-Delete-Wächter + cleanup_rows) routen durch diesen Helfer.

ABER: test_06 schlägt weiter fehl — die resultierende Order ist `crm.accounts` Index **35**, `public.tenant_orgs` Index **20** → also public VOR crm (FALSCH für die Cross-Schema-Beziehung crm.accounts->public.tenant_orgs; das Kind crm.accounts müsste vor dem Eltern public.tenant_orgs stehen). Die ersten 20 Plätze sind ALLE public.

## DEINE ENTSCHEIDUNG (begründet, am Code)
1. **Ist die topo-ORDER eine Korrektheits-Anforderung ODER eine Optimierung?** Konkret: Wenn (B) der Retry-Loop FK-Violationen robust auflöst (löscht in JEDER Reihenfolge sicher), ist die exakte Order dann noch nötig — oder nur eine Effizienz-Optimierung (weniger Retries)?
2. **Daraus folgend — der richtige Fix:**
   - (a) Den zyklus-bewussten Sort REPARIEREN, sodass er garantiert crm-vor-public (Kind-vor-Eltern für alle NICHT-Zyklus-Kanten) liefert? Wenn ja: wo ist der Ordering-Bug im `_kahn_topo_sort` (warum landet crm bei 35 statt vor public)?
   - (b) ODER test_06's strenge „crm-vor-public-Index"-Assertion LOCKERN/ERSETZEN durch eine, die die echte Korrektheit prüft (der Retry-Loop löscht crm+public-Leaks FK-violation-frei + lässt nichts zurück)? Wenn ja: ist das LEGITIM (die Order ist mit Mutual-FKs eh nicht perfekt garantierbar + der Retry-Loop ist die Korrektheit) oder ist das **Maskieren** eines echten Bugs (Req-7)?
3. **Sicherheits-Check:** Garantiert der Retry-Loop `_fk_safe_delete_rows` wirklich, dass am Ende ALLE löschbaren Leak-Rows weg sind (kein stiller Rest)? Edge-Cases (echter Daten-Zyklus, Savepoint-Semantik, "transaction aborted")?
4. Was übersehen wir?

Antworte strukturiert + konkret. Wenn (b) richtig ist, sag explizit warum es KEIN Maskieren ist (oder dass es eins wäre). Wenn (a) richtig ist, zeig den Ordering-Bug.

---
# UNTEN: _schema_introspect.py (topo-Sort A) + conftest.py (Retry-Loop B + Wächter) + test_baseline_autoreset.py (test_06)
---
