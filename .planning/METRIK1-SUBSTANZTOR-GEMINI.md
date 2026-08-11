# METRIK-1 — drei Entscheidungen, Gegenlesung erbeten

Du bist Gegenleser, nicht Bauarbeiter. Bitte NICHT im Code nachlesen — alles Noetige steht hier.
Antworte knapp, auf Deutsch, und widersprich, wo du anderer Meinung bist. Jede Empfehlung mit
Begruendung. Keine Zustimmung aus Hoeflichkeit.

## Was NERVE ist (Kurzfassung)

Live-Assistent fuer Kaltakquise-Telefonate. Im Kaltakquise-Modus hoert das System aus
Datenschutz-Gruenden NUR den Verkaeufer, nie den Kunden. Nach dem Anruf bekommt der Verkaeufer eine
Rueckmeldung. Zielmarkt: USA.

## Was die Phase METRIK-1 macht

Die alte Punktzahl ("Gespraechsnote 73/100") wird abgeschafft. Ersatz:
- eine Kopfzeile "bester Moment" mit **woertlichem Zitat aus dem Transkript**
- **genau EINE Sache** fuers naechste Mal, ebenfalls belegt
- ein Pruefer, der erfundene Zitate abfaengt (steht das Zitat wirklich so im Transkript?)

## Das Problem, um das es geht: das Substanz-Tor

Vor der Rueckmeldung steht heute ein Tor: es verlangt **mindestens 3 hoch-konfidente
Gespraechs-Momente** (Einwand-Momente). Erst dann wird ueberhaupt bewertet.

Warum das konstruktiv falsch ist:
- Im Kaltakquise-Modus ist die automatische Einwand-Erkennung abgeschaltet (wir hoeren den Kunden
  nicht). Momente entstehen fast nur, wenn der Verkaeufer selbst einen Knopf drueckt.
- Wer weniger als drei drueckt, bekommt NIE eine Rueckmeldung — egal wie gut das Gespraech war.
- Ein Gespraech mit wenigen Einwaenden ist oft das beste. Das Tor bestraft also strukturell Erfolg.

Beschlossen ist: Das Tor wird umgebaut. Neue Frage: **"wurde ueberhaupt genug GESPROCHEN?"** auf
Basis von Sprechzeit und Wortanzahl (seit gestern erstmals erfasst). Einwand-Momente sind nur noch
EIN Signal, nie das alleinige Tor. Ein Tor gegen schlechte Tonqualitaet bleibt bestehen.

## HARTE RANDBEDINGUNG, die alles veraendert

Wir haben 87 Anrufe und 58 Transkripte in der Datenbank. Der Entwickler hat daraus eine Verteilung
gerechnet (Mitte 105 Woerter, Spanne 4 bis 248) und daraus eine Grenze abgeleitet.

**Der Gruender hat das soeben verworfen: Das sind ALLES Testanrufe mit ausgedachten Skripten.
Kein einziger echter Kaltakquise-Anruf ist darunter.** Damit ist die Verteilung wertlos als
Grundlage fuer eine Grenze.

Wir haben also **null echte Daten** und muessen die Grenze trotzdem jetzt festlegen, weil die Phase
sonst nicht gebaut werden kann.

Hausregel dazu (wichtig): Eine Schwelle gilt bei uns als "gebogen" statt "hergeleitet", wenn sie
anders ausfallen wuerde, waere der heutige Istwert ein anderer. Lackmustest: *Kaeme dieselbe Zahl
heraus, wenn die gemessenen Werte andere waeren?*

---

## FRAGE 1 — Woraus leitet man die Grenze her, wenn keine echten Daten existieren?

Mein Vorschlag (Claudian): Die Grenze kommt aus dem **Zweck**, nicht aus der Verteilung.
- Eine Rueckmeldung besteht aus einem **woertlichen Zitat**. Ein zitierfaehiger Satz sind rund
  10 bis 15 Woerter. Unter etwa 20 Woertern gibt es schlicht nicht genug Text, aus dem man einen
  besten Moment UND eine Sache fuers naechste Mal ziehen koennte.
  → **mindestens 20 Woerter**
- Ein einzelner Redeabschnitt ohne jede Pause heisst: es kam nichts zurueck, es war kein Gespraech.
  → **mindestens 2 Redeabschnitte**
- Zusaetzlich: Das Tor **zaehlt und protokolliert jede Ablehnung**, damit wir nachkalibrieren
  koennen, sobald echte Anrufe vorliegen.

Vorteil dieser Herleitung: Sie liefert dieselbe Zahl unabhaengig davon, wie die heutigen Daten
aussehen — sie besteht den Lackmustest.

**Deine Aufgabe:**
- Ist diese Herleitung haltbar, oder ist "20 Woerter" nur eine huebsch begruendete Bauchzahl?
- Gibt es einen grundsaetzlich besseren Weg? Zum Beispiel: das Tor vorerst so durchlaessig wie
  moeglich bauen (nur eindeutige Nicht-Gespraeche raus: Fehlanruf, Anrufbeantworter, acht Sekunden)
  und erst mit echten Anrufen schaerfen?
- Ist "Wortanzahl" ueberhaupt das richtige Mass, oder gibt es ein robusteres (Sprechzeit? Anzahl
  Redeabschnitte? eine Kombination)? Achtung: Reine Dauer ist belegt schlecht — ein Anruf mit
  406 Sekunden Dauer hatte nur 21 Woerter.
- Welche Fehlerrichtung ist teurer: ein zu durchlaessiges Tor (schwache Rueckmeldung auf duennem
  Material) oder ein zu strenges (guter kurzer Anruf bekommt nichts)?

---

## FRAGE 2 — Wie nimmt man ab, dass die KI die RICHTIGE "eine Sache" waehlt?

Das ist das Hauptrisiko der Phase: Liegt die Auswahl daneben, ist die GANZE Rueckmeldung falsch.
Bisheriges Abnahmeverfahren: "rund 10 Rueckmeldungen lesen". Das prueft Belege sauber (steht das
Zitat wirklich so da — ja/nein), prueft aber die Auswahl nicht, weil es dafuer kein Ja/Nein gibt.

Drei vorgeschlagene Kriterien:
- **(a) Halluzinations-Tor allein:** 10 Rueckmeldungen, null erfundene Zitate. Auswahl wird gelesen,
  aber nicht bewertet — die Luecke wird ausdruecklich benannt.
- **(b) Urteil des Gruenders als Zaehlkriterium:** bei mindestens 7 von 10 sagt er "das haette ich
  auch genannt".
- **(c) Negativ-Kriterium:** keine der 10 darf etwas nennen, das im Transkript belegbar nicht
  stattgefunden hat oder das auf der **Streichliste** steht. Streichliste = Dinge, die in grossen
  US-Studien nachweislich NICHT mit Erfolg zusammenhaengen: Fuellwoerter, Anzahl der Fragen,
  Weichmacher wie "I think", Tonfall.

Wichtiger Kontext: Bei uns gilt ausdruecklich, dass der Gruender **nicht der Goldstandard** ist —
er ist kein US-Vertriebsprofi. Und wir haben belegt erlebt, dass ein unerfuellbares oder
formvorschreibendes Abnahmekriterium am Ende das Produkt formt, statt es zu pruefen.

Mein Vorschlag: **(a) + (c)**, und die Auswahl-Guete wird als benannte Restluecke gefuehrt — mit
festem Termin, naemlich sobald der Fokus-Kreislauf laeuft (dann sehen wir an echten Anrufen, ob
eine genannte Sache beim naechsten Mal tatsaechlich umgesetzt wird).

**Deine Aufgabe:**
- Traegt (a)+(c), oder ist das ein Feigenblatt?
- Gibt es ein viertes, besseres Kriterium, das falsifizierbar ist und den Gruender nicht zum
  Massstab macht? (Beispiele, die du pruefen sollst: zwei unabhaengige KI-Laeufe auf denselben
  Anruf und Vergleich, ob dieselbe Sache herauskommt · ein Gegen-Modell, das die Auswahl kritisiert
  · Auswahl gegen den bekannten Ausgang des Anrufs halten)
- Ist es vertretbar, mit einer benannten Restluecke live zu gehen?

---

## FRAGE 3 — Was ist abtrennbar, wenn die Phase zu gross wird?

Die Phase traegt fuenf Brocken:
1. Substanz-Tor umbauen (Frage 1)
2. Zitat-Pruefer anschliessen (existiert, wird aber nirgends aufgerufen)
3. alte Punktzahl-Formel stilllegen
4. neue Form: Kopfzeile + genau eine Sache
5. **Fokus-Katalog** (feste Liste von 8 bis 9 Coaching-Punkten, jeder mit hartem Kriterium) plus
   **Anwendungs-Pruefung** (wurde der Fokus beim naechsten Anruf umgesetzt? drei Mal in Folge?)

Der Entwickler schlaegt vor, Brocken 5 komplett als abtrennbare letzte Welle zu fuehren.

Mein Gegenvorschlag: Die Trennlinie liegt mitten in Brocken 5.
- Der **feste Schluessel** (die eine Sache kommt aus einer festen Liste, nicht als Freitext) darf
  NICHT fallen. Er ist ein Tueroeffner: Geht die Phase mit Freitext live, sind alle Rueckmeldungen
  aus der Zwischenzeit spaeter **nicht nachholbar** — die Daten sind fuer immer unbrauchbar.
- Die **Anwendungs-Pruefung / Serie** ist abtrennbar: Sie liest nur Daten, die ohnehin gespeichert
  werden, und ist jederzeit nachruestbar. Ohne sie geht nichts Halbes live — der Verkaeufer bekommt
  Kopfzeile plus eine Sache, nur noch keine Serie.

**Deine Aufgabe:** Stimmt meine Trennlinie, oder uebersehe ich etwas? Ist der Freitext-Zwischenstand
wirklich unbrauchbar, oder liesse er sich spaeter maschinell auf Schluessel abbilden?

---

## Was ich von dir will

Pro Frage: kurze Antwort, deine Empfehlung, und ausdruecklich das, was du an meinem Vorschlag fuer
falsch oder schwach haeltst. Wenn du bei einer Frage keine bessere Idee hast, sag das auch.
