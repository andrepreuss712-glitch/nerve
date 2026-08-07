# BRIEFING — Ist unser Vault-Wächter falsch konstruiert?

Du bist Gegenleser. **Nichts lesen, nichts schreiben, nichts ausführen** — alle nötigen Fakten stehen unten. Antworte auf Deutsch, direkt, ohne Höflichkeitsfloskeln. Wenn du meinst, wir liegen falsch, sag es hart.

## Kontext in drei Sätzen

Ein Ein-Mann-Projekt (Gründer André, nicht-technisch) pflegt ein Obsidian-Vault als "zweites Gehirn" für ein Software-Produkt vor dem Marktstart. Die KI (Claudian) arbeitet täglich darin. Weil Verhaltens-Regeln im Vault nachweislich nicht gehalten haben (46 von 50 Planungs-Dateien standen fälschlich auf "aktiv", ein ganzer Arbeitstag fehlte im Changelog, die Orientierungs-Sektion stand 3 Monate veraltet), wurde am 02.08.2026 ein **Wächter-Skript** gebaut, das bei jedem Sitzungsstart läuft und ROT meldet, bevor gearbeitet wird.

## Was der Wächter heute prüft (sein vollständiger Prüfkatalog)

1. **Fehlende Kopfzeilen** — jede Notiz braucht `status` + `beschreibung` (ein Satz)
2. **"aktiv", aber >60 Tage nicht angefasst** — verdächtig, wahrscheinlich in Wahrheit erledigt
3. **Größen-Schwellen:**
   - `05 Log.md` (Changelog, neueste oben): max **1000 Zeilen**
   - `CLAUDE.md` (die Regeldatei, wird in jede KI-Sitzung geladen): max **900 Zeilen** — ausdrücklich als reiner "Wachstums-Alarm" gewidmet, kein Qualitätsmaß
   - `CLAUDE.md`: max **40 immer geltende harte Regeln** (Überschriften-Zählung) — das ist das belegte Maß, hergeleitet aus einer Messkurve (ab ~40 gleichzeitigen Regeln fällt die Befolgungsquote eines LLM auf 9–31 %)
   - Ordner `03 Planung/` (aktive Arbeits-Dokumente): max **25 Dateien**
4. **`02 Stand.md` älter als 30 Tage** — die Datei, die als einzige Wahrheit über den Systemzustand gilt
5. **Log-Lücken** — Tage mit Code-Commits, aber ohne Changelog-Eintrag (Toleranz 2 Tage)
6. **Kaputte Wikilinks**

Exit-Code 1 bei rot. Die Übersicht wird bei jedem Lauf **live aus dem echten Dateibestand** erzeugt — bewusst keine gespeicherte Index-Datei.

## Die geltende Regel dazu (aus CLAUDE.md, Ablage-Regel §7③)

> **Ein Wächter, der DAUERHAFT rot ist, ist kaputt — auch wenn er recht hat.**
> Rot heißt "handeln". Bleibt ein Befund über mehrere Sitzungen rot, entsteht Alarm-Müdigkeit: Man kennt ihn, überliest ihn — und übersieht dann auch die *neuen* Befunde daneben.
> Reaktion bei anhaltendem Rot, in dieser Reihenfolge: (a) den Befund abarbeiten, oder (b) die Schwelle **kalibrieren** — knapp über dem *belegt erreichbaren* Boden, mit konkreter Restliste im Wächter-Code, oder (c) den Befund als bewusste Ausnahme dokumentieren.
> **Verboten:** die Schwelle auf den Istwert heben, damit es grün wird. Der Unterschied ist die **Herleitung**: kalibriert kommt aus dem, was erreichbar ist; gebogen kommt aus dem, was gerade herauskam.

## DAS PROBLEM — was tatsächlich passiert ist (Tatsachen, keine Vermutung)

| Datum | Ereignis |
|---|---|
| 02.08. | Wächter gebaut. Mehrere rote Befunde, abgearbeitet. |
| 03.08. | ROT: Log 1070/1000, Regeldatei 803/700. Ein halber Arbeitstag Komprimierung → Log 917, Regeldatei 697. **Erstmals komplett grün.** Im selben Zug wurde die Regeldatei-Schwelle nach Literatur-Recherche von 700 auf 900 umgewidmet. |
| 03.08. | Beim Komprimieren ging ein Datums-Anker verloren → der Wächter meldete daraufhin **fälschlich** eine Log-Lücke. Also: die Aufräum-Arbeit, die der Wächter erzwang, hat einen Fehlalarm im Wächter selbst erzeugt. |
| 07.08. | **Vier Arbeitstage später wieder ROT:** Log 1029/1000, `03 Planung/` 26/25. |

Weitere belegte Vorfälle:
- Der Wächter hat sich **viermal falsch-rot** gemeldet (ein `.md`-only-Verweischeck hielt ein existierendes Bild für fehlend und wurde einen ganzen Tag lang als "Bild fehlt" weitergereicht; ein verlorener Datums-Anker; zwei weitere).
- **`03 Planung/` bei 26 Dateien: alle 26 stehen auf "aktiv", keine einzige auf "erledigt".** Von fünf geprüften Archiv-Kandidaten tragen **vier einen ausdrücklichen Sperrvermerk in der Kopfzeile ("NICHT archivieren")**. Der Wächter fordert also eine Handlung, die für die Mehrzahl der Kandidaten ausdrücklich untersagt ist.
- Das Log ist per Definition **monoton wachsend** (Changelog, jeder Arbeitstag ein Eintrag, ~25–40 Zeilen pro Eintrag bei diesem Schreibstil). Die 1000-Zeilen-Grenze wird damit **strukturell etwa alle 1–2 Wochen** wieder gerissen.
- Die vorgeschriebene Reaktion ("komprimieren, nicht splitten": Einträge älter als 21 Tage werden Einzeiler mit Datum, Volltext ins externe Archiv) ist **Handarbeit** und wurde bisher immer von der KI erledigt — mit dem oben belegten Risiko, dabei Anker zu zerstören.

**Andrés Urteil heute wörtlich:** *"wir sollten nochmal über unsere Regel für den Wächter nachdenken. das scheint für uns so nicht zu funktionieren."*

## Die Frage an dich

**Ist die Größen-Schwelle überhaupt das richtige Instrument — oder misst der Wächter an dieser Stelle die falsche Sache?**

Bitte konkret:

1. **Diagnose.** Was ist hier eigentlich kaputt? Die Schwellen-Werte? Die Wahl "Zeilenzahl/Dateizahl" als Messgröße? Das Ein-Stufen-Modell (nur ROT)? Die Vermischung von "Risiko" und "Hausarbeit" in einem Alarm? Etwas, das ich gar nicht auf dem Zettel habe?

2. **Mindestens drei konkurrierende Lösungswege**, nebeneinandergelegt, nicht einer verteidigt. Für jeden: was er kostet, was er nicht löst, wie er scheitern kann. Wenn dir einer davon offensichtlich erscheint, misstraue dem.

3. **Deine Empfehlung** — genau eine, mit Begründung. Und ausdrücklich: **was spricht dagegen?**

4. **Der Selbst-Widerspruch, den ich sehe** — prüfe ihn: Wenn wir die Größen-Schwellen entschärfen, weil sie ständig anschlagen, ist das dann nicht genau die verbotene Bewegung ("Schwelle auf den Istwert heben, damit es grün wird")? Oder ist der Unterschied echt? Wo genau verläuft die Grenze?

5. **Was würdest du am Prüfkatalog ERSETZEN oder STREICHEN**, nicht nur ergänzen? Bei uns gilt "Ein Rein, eins Raus" — jede neue Regel benennt, welche alte sie ablöst. Halte dich daran.

6. **Ein Punkt, der mir wichtig ist:** Die eigentliche Krankheit war nie die Dateigröße. Sie war: *"Was JETZT gilt, war von dem, was mal galt, nicht mehr unterscheidbar."* Misst irgendeiner unserer sechs Prüfpunkte diese Krankheit wirklich — oder messen wir nur, was leicht zählbar ist?

Antworte in Fließtext mit klaren Zwischenüberschriften. Keine Code-Vorschläge nötig, es geht um das Konzept.
