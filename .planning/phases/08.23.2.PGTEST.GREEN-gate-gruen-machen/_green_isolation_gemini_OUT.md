Hier ist mein Cross-AI-Review der Isolations-Mechanismen für das Postgres-Tor, basierend auf dem echten Code und der `GREEN-SPEC`.

### 1. Die Entscheidung: Welche Option ist die richtige Grundrichtung?

**Option 1 (Auto-Reset, GESPALTEN)** ist die einzig tragfähige und architektonisch korrekte Richtung. 

**Begründung gegen den Code:** 
Die NERVE-Testarchitektur erzwingt "Real-Commits" (RLS-Hooks feuern auf `AFTER BEGIN` für die existierende Connection, Trigger wie `trg_mk_tenant_org` erwarten echte Inserts). Du hast explizit Tests wie in `test_rls_isolation.py` oder Worker-Tests (`test_anonymizer_worker.py`), die über eigene Verbindungen (`nerve_app_pg_conn`) echte Transaktions-Grenzen überschreiten. 
Option 1 trennt sauberes State-Management von Test-Faulheit: "Der Test war zu faul seine eigenen erzeugten Rows zu löschen" (Extra-Rows → Wächter löscht sie + warnt laut) wird getrennt von "Der Test hat globale Basis-Daten zerstört" (Missing/Mutated Baseline → Gate blockt rot).

### 2. Risiken und Schwächen JEDER Option

*   **Option 3 (Transaktions-Rollback): FÄLLT DURCH.** 
    *   *Schwäche:* Versteckt Commit-Zeit-Verhalten und bricht Tests, die Side-Band-Connections nutzen (z.B. Background-Worker-Emulation, Cap-Enforcement). Ein globaler Test-Wrapper kann diese Commits nicht zurückrollen, sie würden dauerhaft leaken.
*   **Option 2 (Reiner Auto-Reset): FÄLLT DURCH.** 
    *   *Schwäche:* Verletzt Req-7 gravierend. Ein Wächter, der fehlende Baseline-Rows stumm oder laut wiederherstellt, maskiert App-Bugs. Wenn ein Entwickler aus Versehen eine Route schreibt, die die `is_test_user`-Organisation id=1 löschen kann, fängt Option 2 das nicht mehr als harten Fehler.
*   **Option 1 (Gespalten): GEWINNER, aber mit Risiko.**
    *   *Schwäche:* Erfordert Nachbesserung der 7 bekannten Base-Seed-Delete-Bugs von Hand, da der Wächter hier (korrekterweise) blockt.
    *   *Risiko:* Das Auto-Deleten der Extra-Rows durch den Wächter muss exakt die Foreign-Key-Constraints respektieren, sonst stirbt der Wächter selbst beim Aufräumen.

### 3. Auto-Reset: Kann der Wächter eine fehlende Baseline-Row sauber heilen?

**Nein, ein Re-Insert ist bei eurer Architektur hochgradig gefährlich.**
*Beweis:* Conftest Zeile 83 (`_seed_test_tenant`) dokumentiert, dass ein Insert in `organisations` sofort den Trigger `trg_mk_tenant_org` auslöst, der eine neue `tenant_orgs`-Row anlegt. 
Wenn ein Test `organisations` id=1 löscht (was per CASCADE auch `tenant_orgs` löschen würde) und der Wächter versucht das durch einen einfachen Re-Insert zu "heilen", generiert der Trigger eine **neue UUID** für diesen Tenant. Folge-Tests, deren Fixtures oder Caches sich auf die alte Baseline-UUID verlassen, schlagen irreproduzierbar fehl. 
Auch Mutationen (`xmin` geändert) zu heilen bedeutet ein explizites `UPDATE`, das `updated_at`-Trigger auslöst. 
**Fazit:** Fehlende/Mutierte Rows MÜSSEN zu einem harten `pytest.fail` führen.

### 4. Reverse-FK-Lösch-Reihenfolge (Auto-Delete) vs. Req-9 (Dynamische Listen)

Hier ist euer größter Fallstrick für die Implementierung:
Die `GREEN-SPEC` verlangt (Req-9), dass Wächterlisten schema-abgeleitet (`information_schema`) statt hardcoded sind. Wenn der Wächter die `leaked` IDs auto-löscht, muss er das reverse-FK tun. 
*Wenn du die Liste dynamisch machst, verlierst du die hardcodierte `_CLEANUP_FK_ORDER`!*
*   **Fallstrick:** Wenn der Wächter in alphabetischer Reihenfolge löscht, knallt es sofort (z.B. `users` hat FK auf `organisations`).
*   **Lösung:** Du musst entweder die FK-Abhängigkeiten (`pg_constraint`) zur Laufzeit auslesen und einen topologischen Sort machen (komplex), ODER in der Wächter-Cleanup-Transaktion einen Zwei-Pass-Ansatz fahren (zuerst Kind-Tabellen, dann Eltern-Tabellen). 

### 5. Was übersehen wir? Edge-Cases

*   **Multi-Connection Race-Conditions:** Der Wächter (`_baseline_guard_engine`) läuft in seiner eigenen Connection. Wenn der App-Code oder Test asynchron Queries in einer noch nicht beendeten Worker-Connection laufen lässt, könnten beim Wächter-Snapshot oder Cleanup Row-Locks kollidieren.
*   **UUID vs. INT-Cast (Bug 10e5d0a):** Beim Auto-Delete durch den Wächter musst du exakt aufpassen. Das Problem, das du in Phase PGTEST in `cleanup_rows` gefixt hast (`WHERE id::text = ANY(...)`), muss der Auto-Reset-Wächter beim Löschen der Extra-Rows replizieren, da public-Tabellen gemischt UUID und INT PKs haben.

### 6. Konkrete Umsetzungs-Wachpunkte für Option 1

1.  **Strict Split:** Programmiere `_diff_baseline` so, dass `leaked` zurückgegeben wird zum Löschen, aber `missing` und `mutated` einen sofortigen `pytest.fail` werfen (mit Ausgabe der NodeID).
2.  **Attribution (Req-3):** Das Auto-Delete darf nicht stumm sein. Es muss zwingend ein `logging.warning(f"[BASELINE-AUTO-FIX] {request.node.nodeid} leaked rows in {tbl}: {ids}")` feuern.
3.  **Topologischer Sort für Req-9:** Ignoriere das nicht. Wenn du `_BASELINE_PUBLIC_TABLES` dynamisch machst, musst du dem Wächter-Auto-Delete eine statische Sortier-Logik beibringen (z.B. erst `profiles`, dann `users`, dann `tenant_orgs`, dann `organisations`).
4.  **Wächter Transaktions-Hygiene:** Der Wächter muss für seine Lösch-Aktion explizit `begin()` und `commit()` auf seiner `_baseline_guard_engine` aufrufen, damit die Rows für den nächsten Test wirklich weg sind.

**Empfehlung:** Setze Option 1 um. Es löst das Leak-Problem der 61 Files, bewahrt die Integrität der Base-Seeds und respektiert die Real-Commit-Mechanik eurer Suite.
