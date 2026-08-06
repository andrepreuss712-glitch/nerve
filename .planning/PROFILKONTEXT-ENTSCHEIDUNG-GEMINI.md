# Entscheidung: jetzt anschliessen oder fuer den Neubau vermerken?

Du brauchst keine Dateien und keinen Code — alles Noetige steht unten. **Antworte direkt.** Eine parallele Pruefung am echten Code laeuft bereits; **deine Aufgabe ist die strategische Sicht und das Finden von Denkfehlern.**

## Das Produkt

**NERVE** — Live-Assistent fuer Verkaufsgespraeche, Markt USA, **vor dem Start** (Early Access vorbereitet, noch keine zahlenden Kunden). Solo-Gruender, deutscher Einzelunternehmer.

Der Verkaeufer telefoniert. NERVE hoert ueber ein Pflicht-Headset **nur ihn** (nie den Kunden), erkennt Einwaende und blendet waehrend des Gespraechs Antworten auf den Bildschirm ein. Gemessen: erstes Wort nach 1,0 s, komplette Antwort 3,3 s.

## Der Befund von heute (am Code belegt)

Es gibt **sechs lebende KI-Aufrufe** im Live-Pfad. Geprueft wurde, welche Daten in ihren Auftrag eingebaut werden:

| Aufruf | Profil-Stammdaten | Vorab-Briefing |
|---|---|---|
| **Dauer-Analyse** (laeuft alle ~2 s, entscheidet: liegt ein Einwand vor?) | **NEIN** | **NEIN** |
| Phasen-Erkennung | NEIN | NEIN |
| Kaltakquise-Ableitung | NEIN | NEIN |
| Live-Coaching | teilweise (Produkt+Firma; **kein** Preis, Alleinstellung, Tabus) | NEIN |
| **Knopf-Antwort** (Verkaeufer drueckt Einwand-Knopf) | **JA, alles** | **JA** |

**Kernproblem:** Der Aufruf, der **permanent mitlaeuft und entscheidet, ob ueberhaupt etwas passiert**, weiss nicht, was der Nutzer verkauft, an wen, zu welchem Preis. Er sieht nur die Woerter. Der gute, vollinformierte Antwort-Aufruf haengt also an einem Tuersteher, der den Kontext nicht kennt.

**Zusaetzlich:** Mehrere Profilfelder, die der Nutzer im Einrichtungs-Assistenten muehsam pflegt, landen **nie** in einem Live-Auftrag (Zielkunden, ROI-Argumente, No-Gos, Techniken, Antwortlaenge, und von jedem hinterlegten Einwand die Varianten/Technik/Intensitaet). Der Nutzer fuellt Felder aus, die nichts bewirken.

**Die Aussage des Gruenders, die das ausgeloest hat:** *„Damit die KI moeglichst gute Vorschlaege machen kann, braucht sie den ganzen Kontext aus dem Profil — nicht nur die hinterlegten Einwand-Antworten. Ohne Kontext wird die KI gerade in laengeren Gespraechen niemals richtig gut sein koennen, weil sie das Produkt, den User, das Unternehmen des Users gar nicht versteht."*

## Die Lage drumherum — wichtig fuer die Abwaegung

**Vor drei Tagen wurde beschlossen: die Live-Engine wird NEU GESCHRIEBEN.** Grund: Sie ist nicht auf mehrere gleichzeitige Nutzer ausgelegt (globaler Zustand, ein Arbeiter fuer alle, ein globaler Riegel). Das ist ein grosser Brocken und der naechste grosse Schritt.

**Aber:** Eine Pruefung heute hat ergeben, dass der Neubau den bestehenden **Auftrags-Bau gar nicht ersetzt**. Er hat einen eigenen Adapter, der einen **fertigen Auftrag von aussen entgegennimmt**. Der Profil-Block wird also nicht neu gebaut, sondern durchgereicht. **Was heute angeschlossen wird, ueberlebt den Neubau unveraendert.**

**Was aktuell auf der Liste vor dem Neubau steht:**
1. Eine Sicherheits-Phase (Besitzpruefung an acht Eingaengen + Zeitlimits) — **laeuft gerade, Welle 1 ist heute live**
2. Drei kleine Mehrnutzer-Stellen ausserhalb der Engine (einer davon start-blockierend)
3. Eine Kennzahlen-Ueberarbeitung
4. Die Schwaerzung neu einsortieren

**Jeder Einschub verschiebt den Neubau.**

## Was heute noch passiert ist (fuer die Einordnung der Arbeitsweise)

Wir haben heute eine **Zwei-Konten-Gegenprobe** im Browser gefahren: Konto A (Firma 1) versucht sechsmal, an die Daten von Konto B (Firma 2) zu kommen — alle abgeprallt. Dazu drei Gegenproben, die beweisen sollten, dass der Schutz nicht einfach *alles* verbietet.

**Zwei Lehren daraus, die fuer die jetzige Entscheidung zaehlen:**
- Eine der Proben war **gruen, ohne etwas zu pruefen** — die abgefragten Felder waren leer, aber sie waren auch ohne jeden Schutz leer. Der Gruender hat das selbst bemerkt: *„ich hatte aber gar kein Briefing gemacht."* Wir haben sie **nicht** gruen gefaerbt, sondern als „nicht durchfuehrbar" dokumentiert.
- Bei der Fehlersuche danach fiel der ganze Befund oben ueberhaupt erst auf. **Der Befund ist ein Nebenprodukt eines Tests, nicht das Ergebnis einer Suche.**

## Die Entscheidung, vor der wir stehen

**Weg A — JETZT anschliessen.** Den bestehenden Profil-Block (existiert und funktioniert bereits fuer die Knopf-Antwort) zusaetzlich an die Dauer-Analyse und ans Coaching geben. Kein Neubau, ein Anschluss.

**Weg B — NUR fuer den Neubau vermerken.** Als Anforderung in die Bau-Liste der neuen Engine schreiben und dort einmal richtig machen.

**Die Empfehlung, die ich dem Gruender gegeben habe (Weg A) — und ihre Begruendung:**
> Nicht wegen des sofortigen Nutzens, sondern weil **wir nicht wissen, ob es funktioniert.** Mehr Kontext koennte die Erkennung besser machen — oder schlechter (mehr Text, mehr worin sich das Modell verlieren kann). Und er kostet Zeit im schnellsten Pfad, den wir haben. Schreiben wir eine ungepruefte Vermutung als Pflicht in den Neubau, bauen wir das Fundament auf einer Annahme. Bauen wir es vorher, wissen wir beim Neubau drei Dinge: Wird die Erkennung wirklich besser? Was kostet es an Zeit? Greift der Zwischenspeicher?

**Ein technischer Punkt, der mit hineinspielt:** Anthropic speichert stabile Auftrags-Anfaenge zwischen und berechnet sie dann fast nichts — aber erst ab einer Mindestlaenge (schnelles Modell: 4096 Token). Der Analyse-Auftrag liegt heute bei ~2000 Token, also darunter. Mit einem vollen Profil-Block laege er bei grob 3200–4500 — **um die Grenze herum**. Bei gut gepflegten Profilen wuerde er gespeichert, bei duennen nicht.

## Meine Fragen an dich

1. **Welchen Weg wuerdest du gehen — und warum?** Bitte nicht diplomatisch: nenn einen.

2. **Wo steckt der Denkfehler in meiner Begruendung?** Ich argumentiere „erst messen, dann als Pflicht festschreiben". Ist das hier wirklich der richtige Massstab, oder rede ich mir einen Einschub schoen, den ein disziplinierter Gruender verschieben wuerde?

3. **Die unbequeme Gegenfrage:** Ist „mehr Kontext = bessere Vorschlaege" bei einem Sprachmodell ueberhaupt so sicher, wie wir annehmen? Was ist an Gegenbeobachtungen bekannt — wo kippt zusaetzlicher Kontext in schlechtere Ergebnisse (Verduennung, Ablenkung, Widersprueche im Auftrag)? **Wenn es dafuer Belege gibt, will ich sie hoeren, bevor wir bauen.**

4. **Wie wuerdest du messen, ob es wirklich hilft?** Wir haben seit drei Tagen Messgeraete fuer Antwortzeiten. Aber „bessere Vorschlaege" ist keine Zeit-Zahl. Wie misst ein Ein-Mann-Team ohne Nutzer-Basis, ob die Vorschlaege besser geworden sind — ohne sich selbst zu belaugen?

5. **Der Punkt, den wir vielleicht ganz uebersehen:** Der Nutzer pflegt Felder, die nie wirken. Ist das eigentlich der wichtigere Befund? Und was folgt daraus — anschliessen oder aus dem Editor entfernen?

6. **Was wuerdest du an unserer Stelle NICHT tun?**

Kompakt, konkret, auf Deutsch. Kennzeichne Vermutungen als Vermutungen.
