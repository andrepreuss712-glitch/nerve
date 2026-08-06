# Brainstorming: Muessen wir den Gespraechstext ueberhaupt schwaerzen?

**Wichtig vorab:** Du kannst hier nicht recherchieren. Eine parallele Recherche mit Quellen laeuft bereits — **deine Aufgabe ist die andere Haelfte: Denkfehler finden und Alternativen erfinden.** Wo du auf Rechtswissen zurueckgreifst, kennzeichne es ausdruecklich als unbelegt.

## Das Produkt

NERVE ist ein Live-Assistent fuer Verkaufsgespraeche. Markt: USA. Gruender ist deutscher Einzelunternehmer.

- **Kaltakquise-Modus:** Das System hoert ueber ein Pflicht-Headset **ausschliesslich die Stimme des Verkaeufers**. Die Stimme des angerufenen Kunden erreicht das System technisch nie. Bringt der Kunde einen Einwand, drueckt der Verkaeufer einen Knopf.
- **Meeting-Modus:** Zustimmungstext wird vorgelesen; bei Zustimmung wird beidseitig mitgehoert, sonst Rueckfall auf Kaltakquise-Modus.
- **Kein Audio wird je gespeichert.** Ton rein, Analyse, Ton geloescht.
- **Der Gespraechstext wird geschwaerzt**, bevor er an Claude geht: Namen, Firmen, Telefonnummern, E-Mails werden durch Platzhalter ersetzt. Das geschwaerzte Transkript wird gespeichert (Auswertung + spaeteres eigenes KI-Training).
- Positionierung nach aussen: **"NERVE zeichnet NICHTS auf."**

## Was die Schwaerzung uns kostet

- Sie laeuft mit Sprachmodellen auf dem Prozessor (spaCy, GLiNER) **im Live-Pfad** — bei vielen gleichzeitigen Anrufen ist genau das ein Engpass.
- Sie zerschneidet Woerter (bekannter, offener Fehler).
- Ein Fehler in ihr schaltet sie derzeit prozessweit fuer **alle** Nutzer ab.
- Sie ist im geplanten Neubau der Live-Engine noch gar nicht drin — die Wahl, **wo** sie sitzt, ist also gerade frei.

Der Gruender: *"Ich nehme zwar an, dass unser Weg passt, aber vielleicht geht es auch wesentlich simpler und einfacher fuer uns."*

## Meine Fragen an dich

1. **Wofuer genau schuetzt die Schwaerzung uns — und wovor nicht?** Trenne sauber: Schutz vor Rechtsfolgen · Schutz vor Reputationsschaden · Schutz vor dem KI-Anbieter · Schutz des Endkunden. Bei welchen davon ist die Schwaerzung das *richtige* Werkzeug, und bei welchen loest sie ein Problem, das anders billiger zu loesen waere (Vertrag, Aufbewahrungsfrist, Zugriffsrechte)?

2. **Welche Denkfehler stecken in unserem Aufbau?** Insbesondere: Wir schwaerzen **vor** dem KI-Aufruf. Ist das die richtige Stelle? Welche anderen Stellen gibt es (vor dem Puffer / vor dem Speichern / vor der Anzeige), und was aendert die Wahl jeweils an Risiko, Tempo und Nutzen?

3. **Ein Nutzenverlust, den wir moeglicherweise unterschaetzen:** Wenn Namen und Firmen geschwaerzt sind, kann die KI Saetze wie "Herr Meyer von der Bosch AG hat letztes Jahr abgelehnt" nicht mehr verstehen. Wie gross ist der Qualitaetsverlust fuer einen Verkaufs-Assistenten wirklich — und gibt es einen Mittelweg, bei dem die KI den Kontext behaelt, ohne dass echte Daten den Rechner verlassen?

4. **Nenne mir drei bis fuenf ALTERNATIVE Ansaetze**, die wir nicht auf dem Schirm haben. Nicht "schwaerzen ja/nein", sondern andere Konstruktionen — Pseudonymisierung mit umkehrbarer Zuordnung, Schwaerzung nur beim Speichern, Trennung nach Datenart, kundenseitige Schluessel, was auch immer dir einfaellt. Fuer jeden: was er loest, was er kostet, wo sein Haken liegt.

5. **Wo wuerdest du an unserer Stelle Geld fuer einen Anwalt ausgeben und wo nicht?** Welche Fragen kann ein Gruender selbst entscheiden, welche brauchen zwingend juristische Pruefung?

6. **Welche Frage haetten wir stellen muessen und haben sie nicht gestellt?**

Kompakt, konkret, auf Deutsch. Kennzeichne Vermutungen als Vermutungen.
