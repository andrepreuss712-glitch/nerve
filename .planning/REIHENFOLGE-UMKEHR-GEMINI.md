# BRIEFING — Der Gründer will die Reihenfolge umdrehen. Was kostet das, was übersehen wir?

Du bist Gegenleser. **Nichts lesen, nichts schreiben, nichts ausführen** — alle Fakten stehen unten. Antworte auf Deutsch, direkt, ohne Höflichkeitsfloskeln. **Deine Aufgabe ist ausdrücklich NICHT, dem Gründer zuzustimmen.** Wenn sein Vorschlag schlechter ist als der bestehende Plan, sag das hart.

## Worum es geht

NERVE ist ein Live-Assistent für Verkaufstelefonate (Ein-Mann-Projekt, vor dem Marktstart, keine zahlenden Kunden). Es gibt zwei Betriebsarten: **Kaltakquise** (NERVE hört NUR den Verkäufer, der Kunde ist rechtlich und technisch nicht zu hören) und **Meeting** (beide Seiten, mit Einwilligung).

## Die bisher beschlossene Reihenfolge

1. **METRIK-1** — die Bewertung nach dem Anruf wird abgelöst. Ablöse-Phase, keine Reparatur: die komplette Kaufbereitschafts-Familie fällt weg, drei alte Noten-Rechner fallen weg, von ~30 Werten überleben ~9. Der Nachfolger (Bewerter mit Beleg-vor-Note) existiert bereits im Code, muss nur hochgezogen werden.
2. **4a** — der „Coaching-Aufruf" wird gestrichen. Er feuert nach jedem Satz, ist der teuerste und langsamste Live-Pfad, und sein sichtbarster Ausgabe-Teil wird seit Monaten gar nicht angezeigt. **Er ist der Erzeuger der Kaufbereitschaft — deshalb erst NACH METRIK-1**, das deren Verbraucher entfernt. (Er erzeugt allerdings auch die Schmerzpunkte, die angezeigt werden — die brauchen vorher ein neues Zuhause.)
3. **4c** — die Live-Maschinerie wird **neu gebaut** (bereits beschlossen, 🔴 Blocker), erweitert auf den Verarbeitungsweg nach dem Anruf. Heute hängt alles an einem Prozess, die Auswertung nach dem Anruf hat einen einzigen Bearbeiter für alle Firmen.

Begründung für „Bewertung vor Maschinerie": Baut man die Maschinerie zuerst, baut man sie um Werte herum (Kaufbereitschaft), die danach abgeschafft werden.

## Der Gegenvorschlag des Gründers (wörtlich)

> „Wir bauen jetzt ein Bewertungssystem für ein altes Kassensystem, bzw. wir bauen jetzt ein neues Bezahlsystem und bauen danach ein neues Kassensystem, von dem du selber mal geschrieben hast: ‚das neue Kassensystem ist nicht einfach Copy-und-Paste vom bestehenden, um mehr Kassen zu öffnen'. Also ganz ehrlich? Das nennt sich auch das Pferd von hinten aufsatteln.
>
> In meiner Denkweise macht es mehr Sinn, erstmal Cold Call und Meeting voneinander zu entkoppeln. Beide bekommen einen eigenen Button in der Sidebar und einen eigenen Weg bis in den Live-Assistenten. Wenn das fertig ist, bauen wir jeweils die neuen Kassensysteme drauf, weil die sich ja minimal zwischen Kaltakquise und Meeting unterscheiden werden. UND DANN bauen wir das neue Bezahlsystem oben drauf."

Sein Bild: **Kassensystem = die Live-Maschinerie. Bezahlsystem = die Auswertung/Bewertung.**

**Seine Reihenfolge wäre also:**
0. (Zusatz des Assistenten, vom Gründer akzeptiert) Festlegen, **was** bewertet werden soll — reines Dokument, kein Code.
1. **Kaltakquise und Meeting entkoppeln** — je ein eigener Knopf in der Seitenleiste, je ein eigener Weg bis in den Live-Assistenten.
2. Neue Maschinerie **je Modus** bauen.
3. Neue Auswertung oben drauf.

## Die Messung dazu (heute erhoben, keine Schätzung)

Anzahl der Stellen, die zwischen den beiden Betriebsarten verzweigen:

| Datei | Verzweigungen |
|---|---|
| `services/claude_service.py` | 37 |
| `services/deepgram_service.py` | 21 |
| `static/pip-launcher.js` | 17 |
| `routes/app_routes.py` | 14 |
| `services/live_session.py` | 13 |
| **Summe** | **102** |

In der Seitenleiste gibt es **einen** Live-Eintrag, der ein Fenster mit zwei Karten öffnet (eine je Betriebsart). Es sind also heute **ein Weg mit Schaltern**, nicht zwei Wege.

## Weitere harte Randbedingungen

- **Der Markt ist US-first.** Eine Recherche liegt vor, die vier bisherige Bewertungs-Annahmen widerlegt (u. a.: längere Redeblöcke sind bei Kaltakquise besser, die Fragenanzahl wirkt nicht, der Redeanteil läuft gegenläufig zum Bedarfsgespräch).
- **Geld:** Der Coaching-Aufruf kostet bei jedem Anruf Geld und ist der langsamste Live-Pfad. Unter der Reihenfolge des Gründers rutscht sein Wegfall (Punkt 4a) **weit nach hinten**, weil er hinter der Bewertungs-Ablöse hängt. Das Bluten läuft also länger.
- **Es gibt noch keine zahlenden Kunden** — Umbauten sind jetzt billig, später nicht.
- **Eigene Regel:** „Lieber einmal richtig als alles zwölfmal anpacken." Jede Neuplanung erzeugt Abrieb. Und: „Einfachster tragfähiger Weg zuerst."
- **Eigene Regel:** Neubau gilt für **einzelne Module**, nie für die ganze App.

## Deine Fragen — alle beantworten

1. **Hat der Gründer recht?** Ist „erst Fundament trennen, dann Maschinerie, dann Auswertung" die bessere Reihenfolge — oder ist der bestehende Plan besser? Entscheide dich klar, kein Sowohl-als-auch.
2. **Das Gegenargument prüfen:** Der bestehende Plan begründet „Bewertung zuerst" damit, dass die neue Maschinerie sonst um bald abgeschaffte Werte herum gebaut wird. Löst der vorgeschaltete Schritt 0 (auf Papier festlegen, was gemessen wird) dieses Problem **wirklich** — oder ist das Wunschdenken, weil Papier und Code auseinanderlaufen?
3. **Die Entkopplung selbst — Segen oder Falle?** 102 Verzweigungen zu zwei getrennten Wegen zu machen bedeutet auch: **doppelter Code, der auseinanderdriften kann.** Zwei Wege, die zu 90 % gleich sind, sind eine bekannte Falle. Wo verläuft die Grenze zwischen „sauber getrennt" und „zweimal dasselbe gepflegt"? Was gehört wirklich getrennt, was muss geteilt bleiben?
4. **Ist die Entkopplung überhaupt eine Architektur-Sache** — oder ist „eigener Knopf in der Seitenleiste" nur Oberfläche, während die 102 Verzweigungen davon völlig unberührt bleiben? Das ist die Frage, an der sich entscheidet, ob der Vorschlag trägt.
5. **Was kostet die Umstellung?** Konkret: Was von der bereits geleisteten Planungsarbeit wird wertlos? Was verschiebt sich um wie viel? Was blutet länger?
6. **Was übersehen wir bei der Umstellung?** Der wichtigste Punkt. Nenne konkret, was in der neuen Reihenfolge durchs Raster fällt und in der alten nicht.
7. **Drei Wege nebeneinander**, nicht einer verteidigt — der bestehende Plan, der Gründer-Vorschlag, und mindestens ein dritter, der beiden überlegen sein könnte. Je Weg: Aufwand, was er nicht löst, wie er scheitert.
8. **Genau eine Empfehlung** mit Begründung, plus ausdrücklich: was spricht dagegen?

Fließtext mit Zwischenüberschriften. Kein Code nötig.
