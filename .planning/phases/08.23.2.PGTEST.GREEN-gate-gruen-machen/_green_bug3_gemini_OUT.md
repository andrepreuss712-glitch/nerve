**1. Ist die topo-ORDER eine Korrektheits-Anforderung ODER eine Optimierung?**

Sie ist **beides**, primär aber eine **Korrektheits-Baseline für Log-Hygiene und Performance**. 
Zwar ist der Retry-Loop (B) robust genug, um (via Savepoint-Rollbacks) irgendwann alle Rows zyklusfrei abzuräumen. Ohne eine saubere Topologie würde aber *jeder* Teardown unzählige FK-Violations werfen, was extrem teuer ist und das Postgres-Log der `nerve_test`-DB mit `ERROR`-Spam flutet (Monitoring-Alarme). Zudem fordert `test_06` die `crm-vor-public`-Order als Beweis, dass die Cross-Schema-Katalogauslese funktioniert. Wenn die Order falsch ist, existiert ein Logik-Bug im Sortierer.

**2. Der richtige Fix: (a) Den zyklus-bewussten Sort REPARIEREN.**

Es ist ein harter Ordering-Bug in `_kahn_topo_sort`. Das Löschen von `test_06` (Option b) wäre ein massives Maskieren dieses Bugs.

**Hier ist der Ordering-Bug:**
Der Kahn-Sort baut die Liste als `[Roots ... Leaves]` auf und dreht sie am Ende via `reversed()` um. Damit Kinder (Leaves) *zuerst* gelöscht werden, müssen sie im Kahn-Lauf *zuletzt* verarbeitet werden.

Wenn ein Zyklus vorliegt, bleibt Kahn stecken. Das `stuck`-Array enthält dann **nicht nur den Zyklus**, sondern **auch alle blockierten Kinder** (wie `crm.accounts` via `tenant_orgs`).
Die aktuelle Zyklus-Brecher-Logik sucht sich das Opfer so aus:
`victim = min(stuck, key=lambda n: (reverse_in_degree[n], n))`

`reverse_in_degree` ist die Anzahl der *Eltern*. Eine Leaf-Tabelle wie `crm.accounts` hat naturgemäß die wenigsten Eltern. Die `min()`-Logik wählt also zielsicher das reinste **Kind** im `stuck`-Array als Opfer!
Indem dessen In-Degree auf 0 gesetzt wird, behandelt Kahn das Kind plötzlich als **Root** (Eltern-los) und reiht es ganz *früh* in die Kahn-Queue ein.
Nach dem `reversed()` am Ende landet dieses Kind (`crm.accounts`) ganz hinten in der Lösch-Liste (Index 35), noch hinter seinen wahren Eltern (`tenant_orgs`, Index 20). **Der Algorithmus invertiert aktiv die Abhängigkeit von völlig legitimen Nicht-Zyklus-Kanten!**

**Die Lösung (Fix für _kahn_topo_sort):**
Man darf nicht das Kind (`min(in_degree)`) als Opfer wählen, sondern muss die am stärksten blockierende **Eltern-Tabelle** im Rest-Graph aufbrechen. Also den Knoten, der die meisten blockierten Kinder hat (höchster Out-Degree im Rest-Graph).

```python
        stuck_set = set(stuck)
        # Opfer: Der Knoten, der die MEISTEN blockierten Kinder im Rest-Graph hat (echter Zyklus-Kern)
        victim = max(
            stuck, 
            key=lambda n: (sum(1 for child in reverse_adj[n] if child in stuck_set), n)
        )
```
Damit wird `organisations` (viele Kinder) zum Root gemacht (spät gelöscht) und `crm.accounts` (0 Kinder) bleibt in der natürlichen Abhängigkeit (früh gelöscht). `test_06` wird sofort grün.

**3. Sicherheits-Check zum Retry-Loop `_fk_safe_delete_rows`**

Der Helfer garantiert das Abräumen aller *löschbaren* Rows ohne stille Leaks.
*   **Savepoint-Isolierung:** `SAVEPOINT pgtest_fk_sp` kapselt das Einzel-DELETE. Schlägt es fehl (FK-Violation), wird *nur* dieser Savepoint gerollt. Die Haupt-Transaktion "aborted" nicht und der Loop läuft mit der nächsten Tabelle weiter.
*   **Hard-Stall Edge Case:** Sollte es einen echten Daten-Zyklus geben (Row A referenziert Row B, und umgekehrt) und die Constraints sind nicht `DEFERRABLE`, *können* diese mit Single-Table-Deletes schlicht nicht gelöscht werden (der Loop stagniert auf `failed == pending`). In diesem Fall bricht der Loop ab und retourniert die Tabellen. Der Caller loggt laut, und der `_baseline_cleanup_guard` (bzw. `deploy.sh`) fängt den zurückbleibenden Leak fail-closed auf. Nichts verpufft still.

**4. Was übersehen wir?**
Den Einfluss auf CI-Logs. Option (B) existiert, um die (in einem Schema mit `users <-> organisations` unvermeidbare) allerletzte Zyklus-Kante sanft aufzufangen. Sie ist ein Airbag. Der Airbag darf aber nicht bei *jedem* regulären Kind->Eltern-Cleanup auslösen. Der Fix von `min` auf `max` stellt sicher, dass der Airbag nur exakt für die echte Zyklus-Brücke zündet, und die perfekten 95% des Graphen ohne FK-Fehler in einem Durchgang durchlaufen.
