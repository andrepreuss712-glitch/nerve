# Bau-Regeln 13, 14, 20 — Vollfassungen

> **Angelegt 2026-08-02.** Diese drei Regeln wurden beim Vault-Aufräumen aus `Nerve-Vault/CLAUDE.md` auf Anker-Sätze gekürzt — mit der Begründung, die Vollfassung stehe im Code-Repo. **Das stimmte für diese drei nicht** (Fable-Gegenprüfung 02.08.: Punkt 13 war sogar ein Zirkelverweis zurück ins Vault). Hier stehen sie vollständig. Der Vault-Anker verweist hierher.
>
> **Adressat:** GSD Plan-Author, Plan-Checker, Executor, Code-Reviewer.

---

## Punkt 13 — Schema-Phasen validieren gegen REAL-DATEN, nie nur gegen Theorie-Specs

**Anlass (2026-04-27, Phase 08.19):** Ein Pydantic-Schema wurde mit `extra='forbid'` gebaut, abgeleitet aus einer Theorie-Recherche („welche Felder *sollte* ein gutes Profil haben?"). Die Migration lief auf 6 Produktions-Profilen sauber durch. Aber das Schema bildete die ECHTEN existierenden Felder nicht ab (`phasen`, `einwaende` als Top-Level, `fragen`/`nogos` als `List[Object]`, `ki.antwortlaenge`, `zielgruppe.beruflicher_hintergrund` als Liste). Folge: **Strict-Mode lehnte jeden Save mit ValidationError ab** → Production-Bug. Hotfix `extra='ignore'` + Type-Unions.

**Kern-Einsicht:** Strict-Mode ist nur dann ein Schutz, wenn das Schema die REALITÄT abbildet. Bildet es nur die Theorie ab, ist Strict-Mode ein **Selbstschuss** — valide User-Daten werden blockiert.

### Pflicht-Schritte VOR Plan-Approval bei jeder Schema-/Datenmodell-Phase

1. **Real-Daten-Sample ziehen** — alle bestehenden Produktions-Records des betroffenen Typs exportieren:
   `ssh -i ~/.ssh/nerve_vps root@178.104.82.166 'cd /opt/nerve/app && bash scripts/inspect.sh sample <tabelle> 100'`
2. **Sample durch das neue Schema laufen lassen** — Loop über alle Records: `Schema.model_validate(record, strict=True)`. Sammeln: welche Felder/Records failen, und wie.
3. **Findings-Tabelle in die Plan-Verifikation:** Welche real existierenden Felder bildet das neue Schema nicht ab? Welche Type-Konvertierungen sind nötig? Welche Records brauchen Migrations-Logik?
4. **Plan ist erst approved wenn:** entweder (a) das Schema bildet 100 % der Real-Daten ab und die Migration konvertiert offene Type-Differenzen, ODER (b) es gibt eine explizite Entscheidung, dass bestimmte Felder gelöscht werden — und die Migration löscht sie sicher.
5. **Test-Pflicht:** Die Suite enthält einen Test, der ALLE Produktions-Records (oder ein repräsentatives Sample) mit `strict=True` durchs neue Schema schickt und passing erwartet.

**Plan-Checker:** Fehlt der Real-Daten-Validierungs-Schritt → **BLOCK**.
**Cross-AI-Briefing:** Muss explizit fragen, ob Real-Daten gegen die Schema-Definition gelaufen sind. Ein Reviewer, der nur die Theorie-Spec prüft, hat denselben blinden Fleck wie der Plan-Author.

---

## Punkt 14 — Pre-Insert-Control-Flow-Audit: fünf Schichten vor jedem Code-Einschub

**Anlass (2026-05-09):** Drei Bugs hintereinander in derselben Phasen-Familie, alle mit derselben Wurzel — Code wurde eingefügt, ohne den umgebenden Control-Flow vollständig zu lesen. Beispiele: (a) Ein Flag-Skip wirkte nicht, weil die konsumierende Schleife in einem separaten Thread/Datei lief und das Flag nie las. (b) Ein neuer Block stand **hinter zwei `return`-Statements** → Dead Code, beim Skript-Vortrag nie erreicht.

### Die fünf Pflicht-Schichten — im Plan-Dokument als eigene Sektionen

**## 1. Lokaler Kontext**
30 Zeilen VOR und 30 Zeilen NACH der Insertion-Site, **verbatim aus dem aktuellen Code zitiert**. Plus explizite Liste aller `return`/`continue`/`break`/`raise`/early-`if` in diesem Fenster **mit Zeilennummer**. Begründung, warum der Insert die identifizierten Pfade beachtet (oder explizit, warum sie nicht relevant sind).

**## 2. Funktions-Skelett**
Die ganze betroffene Funktion in Strukturform: „Z.X if-Branch → return / Z.Y try → except → return / Z.Z finaler Branch → …". Damit ist sichtbar, wo alle Ausgangs-Pfade liegen und ob der Insert vor oder nach welchen Branches sitzen muss.

**## 3. Cross-File-Awareness**
`grep -rn "<symbol>" services/ routes/ static/ tests/` — **Output direkt ins Plan-Dokument**, mit Bedeutung pro Treffer. Besonders: andere Threads, Background-Tasks, separate Module, die das Symbol lesen oder schreiben. Fängt Bugs vom Typ „Skip greift nicht, weil der Code in einem separaten Pfad läuft".

**## 4. Edge-Case-Analyse**
Mindestens 2 Edge-Cases, die brechen könnten, + geplante Behandlung. Was, wenn die Variable null/leer ist? Wenn die Funktion zweimal hintereinander läuft? Wenn sich der State zwischen Insert und nächstem Read ändert?

**### Race-Condition-Audit (Unter-Sektion, Pflicht bei Threads/WebSocket/Audio/Timer/Multi-Tab)**
Alle vier Fragen explizit beantworten — „betrifft uns nicht" ohne Begründung ist **nicht** erlaubt:
1. **Gleichzeitiges Feuern:** Was, wenn A und B im selben Moment laufen? Welcher Zustand ist danach garantiert? Treffe ich eine Reihenfolge-Annahme, die nicht stimmt?
2. **Verbindungsabbruch mid-Operation:** Was, wenn Deepgram-Audio / Claude-Request / Browser-Audio während der Operation abbricht? Bleibt ein halb-fertiger Zustand? Wer räumt auf?
3. **Reconnect mit altem Zustand:** Was, wenn nach dem Wiederverbinden eine alte Session-ID, ein alter Handler oder ein alter Tab noch lebt? Wird er invalidiert oder feuert er parallel?
4. **Tab im Hintergrund:** Was, wenn Timer pausiert werden und der Tab nach 30 Minuten mit veraltetem Zustand zurückkommt?

**## 5. Persistenz-Schicht-Verifikation** (aus Punkt 21) — bei Plänen, die Daten lesen/schreiben.

### Erzwingung
- **Plan-Checker:** Fehlt auch nur eine der Sektionen → **BLOCK-Verdikt**, kein Cross-AI-Review bis nachgeholt.
- **Cross-AI-Briefing:** Muss fragen, ob alle Schichten *substanziell* befüllt sind — nicht nur vorhanden.
- **Geltungsbereich:** Code-Insert in EXISTIERENDE Funktionen. Bei komplett neuen Dateien/Klassen gibt es keinen bestehenden Control-Flow.

### Edit-Workflow-Snippet (auch für `/gsd-quick`)
```
1. Lies 30 Zeilen vor und nach der Insertion-Site
2. Beschreibe den Control-Flow, den du dort siehst (early returns, conditions, loops, try/except)
3. grep alle Stellen, wo das angefasste Symbol sonst verwendet wird
4. Erkläre, wie dein Edit mit JEDEM Pfad interagiert
5. Nenne 2 Edge Cases, die brechen könnten, + Behandlung
6. ERST DANN: Code einfügen
```

---

## Punkt 20 — Pflicht-grep: Wird die Tabelle/Funktion im echten Production-Pfad überhaupt gelesen?

**Zwei Anlässe (2026-05-24), dieselbe Fehlerklasse:**
- **C.R.F-Wurzel:** `create_call_for_sid()` existierte mit kompletter INSERT-Logik in `services/live_session.py` — wurde im Production-Code **nirgends aufgerufen** (nur in einer Testdatei). Folge: Pytest grün, Production-Workflow strukturell broken. Erst durch Andrés Live-Test entdeckt. **~3-4 h verloren.**
- **C.R.1:** Eine Migration schrieb 18 `cold_call`-Phrasen in die DB — die im echten Code-Pfad nirgends gelesen werden (`/api/gatekeeper/phrases` filtert hart auf `Phrase.mode == 'gatekeeper'`). Wären toter DB-Code geworden. **~30 min verloren.**

### Pflicht vor jedem `/gsd-quick` mit Daten-Migration ODER Code-Insert

```bash
# Pattern A — Tabelle/Spalte
grep -rn "<TableName>\.query\|FROM <table_name>\|<TableName>(" services/ routes/ static/

# Pattern B — Funktion
grep -rn "<func_name>(" services/ routes/ static/ --include="*.py" --include="*.js"
```

### Auswertung
- **0 Treffer im aktiven Code-Pfad** (außer Tests, Migrations-Datei und der Definition selbst) → **STOPP.** Entweder ist die geplante Aktion sinnlos (kein Lese-Pfad), oder es gibt woanders einen echten Bug, der erst untersucht werden muss. Bewusster Foundation-Code → Eintrag in `Nerve-Vault/04 Entscheidungen/Foundation-Code-Register.md` mit klarer Aktivierungs-Phase; sonst löschen.
- **Treffer da** → prüfen, ob der Filter im Lese-Pfad (`WHERE mode='X'`, `if user.role == 'Y'`) den geplanten Schreib-Pfad überhaupt erreicht. Wenn nein → Mismatch, die Aktion macht keinen funktionalen Sinn.

### Geltungsbereich
**Pflicht** bei: jeder Daten-Migration, die Production-Daten setzt · jeder neuen Funktion, die aufgerufen werden soll · jeder Schema-Änderung mit erwarteter App-seitiger Konsum-Logik.
**Skip OK** bei: rein internen Refactorings, Test-Fixes, mechanischen Cleanups ohne neue Code-Pfade.

**2 Minuten Aufwand, spart Stunden.** Beide Anlass-Fälle wären damit verhindert worden.

---

## ⚠ Nummerierungs-Falle zwischen den Dateien

Die Punkt-Nummern in `Nerve-Vault/CLAUDE.md` und `salesnerve/CLAUDE.md` sind **NICHT identisch**. Beispiel: Vault-Punkt 22 (Async-Bereitschafts-Naht) heißt im Code-Repo **Punkt 26**; der dortige Punkt 22 ist etwas völlig anderes (Verbindungs-Karten-Pflicht). **Wer einem Verweis „siehe Punkt N" folgt, prüft zuerst, in WELCHER Datei gezählt wird.** Sicherer: über den Regel-NAMEN suchen, nicht über die Nummer.
