# ADVERSARIAL PLAN-RE-REVIEW (RUNDE 2) — VERDIKT: BLOCK 🔴

Ich habe die gefoldeten Pläne, `PATTERNS.md` und den bestehenden Code (`conftest.py`, `deploy.sh`) als 3. Instanz geprüft.

## Teil 1: Verifikation der Funde aus Runde 1

*   **#1 BLOCKER (Plan 01 topo-Sort): OK.** Alle FK-Kanten (auch CASCADE) fließen jetzt in den Sort-Graphen ein. Damit ist die *Leaves-vor-Roots*-Garantie auch für `CASCADE -> RESTRICT`-Ketten gesichert und ein Wächter-DoS ausgeschlossen. Die Zyklusbrechung bleibt intakt.
*   **#2 HOCH (Plan 01 Auto-Delete): NICHT GANZ OK (siehe Neue Funde / Fund A).** Der Cast `::text` und die Ableitung der Spalte sind drin, aber der Edge-Case "Composite PK" (mehrere PK-Spalten) führt bei der Katalog-Query zu SQL-Fehlern oder fatalem Over-Deletion.
*   **#3 HOCH (cleanup_rows): OK.** Die Modul-Cache-Lösung (`_DERIVED_FK_ORDER`, `_DERIVED_PK_COLS`) mit Fallback ist signatur-kompatibel, entkoppelt von der per-Test-Engine und erzeugt keine per-Call-Queries. (Kleine Ausführungs-Lücke siehe Fund C).
*   **#4 NIEDRIG (Plan 02 crm_leak_count): OK.** Das 3-Tupel wird korrekt entpackt, die Iteration ist sicher.
*   **Konsistenz PATTERNS.md: OK.** Die Doku spiegelt die korrekten neuen Verhaltensweisen (insb. CASCADE-Edge-Einschluss) wider.

---

## Teil 2: Frischer adversarialer Sweep (Neue Funde)

**[BLOCKER] — Plan 03 + Task 1 — Bash Argument Expansion in `triage.sh`**
*   **Problem:** Der Plan fordert, den pytest-Aufruf zu `... /opt/nerve/venv/bin/pytest "$@"` zu ändern, verbietet aber explizit das Aufbrechen des `single-quoted inner bash -c` (`sudo bash -c '...'`).
*   **Warum (Silent Failure / Feature Break):** Innerhalb von Single-Quotes (`'...'`) expandiert die äußere Shell (`triage.sh`) die `$@`-Variable NICHT. Die innere Subshell hat keine eigenen Argumente erhalten. Resultat: `triage.sh tests/test_x.py` startet **immer die gesamte Test-Suite**, weil `"$@"` in der Subshell leer evaluiert wird. Der Triage-Harness verliert komplett seine Fähigkeit für "targeted runs" (gezielte Tests).
*   **Fix:** Die Argumente müssen hart an die innere Subshell weitergereicht werden. Der Plan muss das korrekte Bash-Forwarding-Muster vorschreiben. Die Kommandozeile muss so enden:
    `sudo -u nerve_app env ... bash -c '... /opt/nerve/venv/bin/pytest "$@"' _ "$@"`
    *(Das `_` belegt `$0` der inneren bash, danach folgen die übergebenen Argumente `"$@"` der äußeren Shell).*

**[HOCH] — Plan 01 + Task 1 — Composite PKs (Zusammengesetzte Primärschlüssel) (Fund A)**
*   **Problem:** Die Query `SELECT a.attname ... indisprimary` liefert bei zusammengesetzten PKs (z.B. Tabelle mit `(org_id, event_id)`) **mehrere Zeilen** zurück.
*   **Warum (False-Red / Datenverlust):** Wenn der Python-Code hier einfach z.B. `.scalar()` oder `.fetchone()[0]` aufruft, schnappt er sich willkürlich nur die erste Spalte. Ein `DELETE FROM tbl WHERE org_id::text = ANY(...)` löscht dann viel mehr Rows als es sollte (massives Over-Deletion-Risiko), oder die Syntax crasht komplett.
*   **Fix:** In `primary_key_column` (Task 1) MUSS geprüft werden, ob die Abfrage `> 1` Zeile (also `len(pk_cols) != 1`) zurückgibt. Ist das der Fall, darf die Tabelle **nicht** für das Auto-Delete freigegeben werden, sondern muss mit der Begründung `"composite PK not supported for auto-delete"` ins `foundation_register` (Denylist) wandern.

**[MITTEL] — Plan 01 + Task 2 — Garantierte Modul-Cache-Initialisierung (Fund C)**
*   **Problem:** Es ist nicht hart garantiert, dass die Fixture `_baseline_schema` (welche den Modul-Cache füllt) rechtzeitig vor jedem anderen Test läuft.
*   **Warum (Silent Fallback):** Wenn `_baseline_schema` keine `autouse=True`-Fixture ist oder nicht von `_baseline_snapshot` explizit als Dependency referenziert wird, bleibt der Cache `_DERIVED_PK_COLS` leer, bis ein Test explizit danach fragt. `cleanup_rows` fällt dann immer lautlos auf den alten Hardcode-Fallback zurück -> Req-9 (dynamische Listen) wäre in der Praxis wirkungslos.
*   **Fix:** Im Plan Task 2 explizit ergänzen, dass `_baseline_schema` zwingend von der ohnehin früh laufenden `_baseline_snapshot`-Fixture als Abhängigkeit (Parameter) angefordert wird, um die Ausführungsreihenfolge hart zu garantieren.

---

## GESAMT-VERDIKT: BLOCK 🔴
**Risiko:** HIGH

**Fazit:** Der Ansatz ist strukturell jetzt extrem reif (die Auto-Reset-Spaltung und der Modul-Cache sind exzellente und sichere Pattern). Der Bash-Quoting-Blocker in `triage.sh` ist allerdings kritisch, weil er die empirische Triage (Plan 04) unmöglich macht. Die Composite-PK-Sicherheit muss zwingend als Guardrail rein, bevor wir automatisierte Katalog-Deletes auf die Datenbank loslassen. Nach Behebung dieser 3 Funde ist der Plan bereit für Execute.
