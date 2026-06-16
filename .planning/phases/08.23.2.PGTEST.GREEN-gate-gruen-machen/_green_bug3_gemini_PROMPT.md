Du bist Gegenleser (3. Sicht), reiner Antwortmodus — KEINE Datei anfassen, KEIN Code schreiben.
Kontext: Python/pytest Test-Gate gegen ein Wegwerf-Postgres `nerve_test`. DB-Rolle `nerve_app`
ist KEIN Superuser: KEIN `session_replication_role=replica`, KEINE Annahme dass FKs DEFERRABLE sind.

PROBLEM (empirisch bestätigt): Der Cleanup-Helfer ordnet Tabellen per Kahn-Topo-Sort (reverse-FK,
Kind-vor-Eltern) bevor er Rows per PK löscht. Das reale Schema hat aber MUTUAL-FK-2-Zyklen:
  - public.users -> public.organisations  UND  public.organisations -> public.users
  - public.users -> public.profiles       UND  public.profiles -> public.users
Kahn setzt einen DAG voraus -> diese Zyklen + alles transitiv Referenzierende (36 von 43 Tabellen,
inkl. alle crm.* via crm.accounts->public.tenant_orgs->public.organisations) landen unsortiert
("remaining") und werden derzeit alphabetisch ans Ende gehängt = potenziell FALSCHE Löschorder
-> FK-Violation-Risiko beim DELETE.

ZWEI DELETE-Pfade (beide single-pass in Topo-Order, eine Transaktion):
  1) Auto-Delete geleakter Rows im autouse-Wächter: `with engine.begin() as conn:` dann pro Tabelle
     `DELETE FROM {tbl} WHERE {pk_col}::text = ANY(:ids)`. Bei FK-Violation bricht die GANZE TX ab
     ("current transaction is aborted") -> Rest der Schleife unmöglich.
  2) cleanup_rows(): löscht vom Caller übergebene IDs, ähnlich single-pass, on-exception rollback+warn.

GELÖSCHT WIRD IMMER NUR EINE MENGE EXPLIZITER PK-IDs (geleakte/test-eigene Rows), NIE die ganze Tabelle.
Die zu löschenden Rows referenzieren meist Baseline-Rows (id=1), selten einander.

MEIN GEPLANTER FIX (bitte prüfen + Lücken finden):
(A) Topo-Sort zyklus-bewusst machen: wenn die Kahn-Queue leer ist aber Knoten bleiben, NICHT
    alphabetisch dumpen, sondern iterativ den Rest-Knoten mit kleinstem residualem reverse_in_degree
    freigeben (eine Zyklus-Kante bewusst brechen, geloggt), Kahn fortsetzen. Bricht Zyklen am
    am-wenigsten-gekoppelten Punkt; alle Nicht-Zyklus-Kanten (inkl. cross-schema crm->public) bleiben
    erhalten -> crm-vor-public-Order bleibt korrekt.
(B) DELETE-Retry-Loop in beiden Pfaden: pro Tabelle ein SAVEPOINT (begin_nested); FK-Violation
    rollt nur den Savepoint zurück; fehlgeschlagene Tabellen werden in der nächsten Runde erneut
    versucht, bis eine Runde 0 Fortschritt macht. Bei 0-Fortschritt-Stall: laut loggen (+ ggf. fail).

FRAGEN:
1. Ist (A)+(B) die richtige Strategie für nerve_app (kein Superuser)? Bessere/robustere Alternative?
2. SAVEPOINT/begin_nested-Retry: korrekt um den "transaction aborted"-Abbruch zu umgehen? Fallstricke
   (z.B. psycopg2-Autocommit, Savepoint-Namen, Performance bei 43 Tabellen)?
3. HARD-STALL: echtes 2-Cycle wo BEIDE Tabellen Rows haben die sich gegenseitig referenzieren ->
   Retry-Loop konvergiert nie. Reicht für TEST-Row-Cleanup der Retry-Loop (weil Test-Rows fast nie
   einander referenzieren), oder MUSS ich eine NULL-able FK-Spalte vor dem DELETE auf NULL setzen
   (zwei-Phasen: erst FK nullen, dann löschen)? Wie würdest du den Stall-Fall ohne Superuser lösen?
4. Übersehe ich etwas Grundlegenderes (z.B. die geleakten Rows einfach per einer einzigen
   `DELETE ... USING`/CTE-Anweisung, oder FKs temporär droppen, oder TRUNCATE ... CASCADE auf einer
   Wegwerf-DB)? nerve_app besitzt die public-Tabellen (kann also ALTER/TRUNCATE), crm.* sind RLS-forced.
5. test_06 prüft "crm.accounts steht vor public.tenant_orgs in der Order". Bleibt das mit (A) korrekt
   garantiert, oder muss die Assertion an die Mutual-FK-Realität angepasst werden?

Antworte knapp und konkret, priorisiere Fallstricke und den Hard-Stall-Fall (Frage 3).
