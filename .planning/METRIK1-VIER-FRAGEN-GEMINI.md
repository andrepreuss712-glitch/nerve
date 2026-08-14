# METRIK-1 — vier Entscheidungen vor dem Bau. Gegenlesung erbeten.

Du bist Gegenleser, nicht Bauarbeiter. **Bitte NICHT im Code nachlesen** — alles Noetige steht hier.
Antworte knapp, auf Deutsch, und widersprich, wo du anderer Meinung bist. Keine Zustimmung aus
Hoeflichkeit. Sag ausdruecklich, wo du dir unsicher bist.

## Lage in vier Saetzen

NERVE ist ein Live-Assistent fuer Kaltakquise-Telefonate (Zielmarkt USA). Im Kaltakquise-Modus hoert
das System aus Datenschutz-Gruenden nur den Verkaeufer, nie den Kunden. Die laufende Phase
**METRIK-1** schafft die alte Gesamtnote ab und ersetzt sie durch: eine Kopfzeile („bester Moment")
mit **woertlichem Zitat aus dem Transkript** plus **genau EINE Sache** fuers naechste Mal. Ein
Zitat-Pruefer verwirft jede Beobachtung, deren Zitat nicht wirklich im Transkript steht.

Der Plan steht (10 Plaene, 8 Wellen). Vier Entscheidungen sind offen, weil sie festgezurrte
Beschluesse umdeuten. Der Entwickler hat zu jeder eine Empfehlung; ich (Claudian) folge ihm bei drei
und widerspreche bei einer.

---

## FRAGE 1 — Bleibt ein Belaestigungs-Befund stehen, wenn sein Beleg-Zitat erfunden war?

Es gibt einen Sonderbefund „Compliance": Der Verkaeufer hat nach **mehrfacher klarer Ablehnung**
weiter gedrueckt. Das ist kein Coaching-Thema, sondern ein Rechtsrisiko (US-Anrufrecht).
Die Grundregel der Phase lautet ohne Ausnahme: **erfundenes Zitat → die GANZE Beobachtung faellt
weg.** Der Entwickler hat fuer diesen einen Befund eine Ausnahme gebaut: Zitat wird geleert, der
Befund bleibt.
**Heutiger Zustand der Anzeige in diesem Fall:** voller Alarm-Kasten („…das ist kein Verkauf,
sondern Belaestigung"), **ohne Zitat und ohne jeden Hinweis, dass der Beleg nicht pruefbar war.**

- **(a)** Befund bleibt, Anzeige wird ehrlich: zusaetzlicher Satz „Verstoss gemeldet, Beleg nicht
  verifizierbar — bitte selbst pruefen."
- **(b)** Regel ohne Ausnahme: die ganze Beobachtung faellt weg und wird als verworfen gezaehlt.
  Preis: ein halluziniertes Zitat kann einen echten Belaestigungs-Befund unsichtbar machen.

**Empfehlung Entwickler + Claudian: (a)**, mit der Begruendung, dass die Fehler **ungleich schwer**
sind (uebersehener echter Fall = Rechtsrisiko; Fehlalarm mit ehrlichem Unsicherheits-Hinweis =
Aergernis). Claudians Zusatz: **diese Faelle getrennt zaehlen** — haeufen sie sich, ist nicht das
Zitat kaputt, sondern die Belaestigungs-Erkennung.

**Deine Aufgabe:** Traegt (a)? Gegenargument, das wir uebersehen: Wenn das Modell das Zitat
erfindet, wie wahrscheinlich ist es, dass es auch den Befund erfunden hat? Wenn hoch — ist (a) dann
nicht ein System, das unbelegte Vorwuerfe systematisch stehen laesst? Gibt es einen dritten Weg?

---

## FRAGE 2 — Darf der Pruef-Text eine technische Kennung weglassen?

Beschluss: Bewerter und Zitat-Pruefer arbeiten gegen **exakt denselben** gerenderten Text (sonst
entstehen hausgemachte Beinahe-Treffer). Der Entwickler hat es so gebaut, dass der **Pruef-Text**
eine technische Vorspann-Kennung je Textstueck (`[#1 berater 500ms]`) **weglaesst**, waehrend der
Text an die KI sie traegt.
Sein Argument: Die Kennung ist Verpackung, kein gesprochener Text. Im Pruef-Text wuerde sie den
Vergleichs-Nenner mit Rahmen-Woertern fuellen und den Pruefer **schwaecher** machen — erfundene
Zitate kaemen leichter durch. Geschuetzt sein sollen Auswahl, Filter und Reihenfolge der
Textstuecke; die sind identisch.

- **(a)** so lassen (ohne Kennung), plus ein Test, der die Kennungs-Freiheit festnagelt.
- **(b)** wortlaut-treu, mit Kennung.

**Empfehlung Entwickler + Claudian: (a).**
**Deine Aufgabe:** Stimmt die Richtung des Effekts (Kennung im Pruef-Text = schwaecherer Pruefer)?
Oder uebersehen wir einen Fall, in dem „nicht exakt derselbe Text" beisst?

---

## FRAGE 3 — Ein Zaehler ohne echten Leser

Bedingung des Gruenders: Verworfene Beobachtungen werden **gezaehlt und protokolliert** — sonst
wird aus einem Schutz eine unsichtbare Qualitaets-Bremse.
Der Entwickler hat den Wert je Anruf gespeichert, aber die Anzeige, die er gebaut hat, **liest ihn
gar nicht** — sie liest einen anderen Zaehler mit anderer Bedeutung (aufsummiert seit Neustart,
je Arbeitsprozess). Er sagt das von sich aus und raeumt ein, dass seine technische Begruendung
dafuer nicht traegt.

- **(a)** echter Leser je Anruf, in der Gruender-/Diagnose-Sicht (nicht in der Coaching-Ansicht).
- **(b)** ausdruecklich als „noch kein Leser bis TERMIN" benennen, mit Datum.

**Empfehlung Entwickler + Claudian: (a).**
**Deine Aufgabe:** Reicht (a)? Was muesste die Anzeige zeigen, damit sie tatsaechlich frueh warnt,
statt nur formal zu existieren?

---

## FRAGE 4 — HIER WIDERSPRECHE ICH DEM ENTWICKLER. Bitte besonders kritisch.

Auf dem Wochen-Dashboard steht ein Liniendiagramm mit dem Titel **„Kaufbereitschafts-Score"**:
Wochenverlauf der **Kaufbereitschaft der Kunden**, feste Achse 0 bis 100.
Wichtig zum Verstaendnis: Genau dieses Feld war die Wurzel des Problems — an anderer Stelle wurde
derselbe Wert als **„Ø Score"** ausgegeben, also die **durchschnittliche Kauflaune der Kunden als
Leistung des Verkaeufers**. Das wird in dieser Phase entfernt. Ebenso ein Trend-Streifen
(„+5 % gegenueber den letzten fuenf") — **ersatzlos**, mit der Begruendung „lieber eine ehrliche
Leerstelle als eine huebsche Zahl ohne Bedeutung".

- **(a) Entwickler:** Das Diagramm **bleibt**. Sein Titel ist ehrlich — er nennt die Kaufbereitschaft
  des Kunden und schreibt sie niemandem als Leistung zu. Dieselbe Begruendung traegt an anderer
  Stelle die Zeile „Kaufbereitschaft Ende: 62/100", die bewusst stehenbleibt. Der Beschluss lautet
  „keine **Gesamtnote**" — eine korrekt benannte Kunden-Kennzahl ist keine Note. Es faellt spaeter
  gemeinsam mit seiner Datenquelle.
- **(b) Claudian:** Es faellt **jetzt** mit.

**Claudians drei Gruende:**
1. **Die Datenquelle wird in der DIREKT FOLGENDEN Phase abgeschaltet** (die Kaufbereitschaft
   verschwindet komplett, seit Anfang August beschlossen). Bleibt das Diagramm, ueberlebt es genau
   **eine** Phase und **friert dann still ein** — es zeigt weiter alte Wochen, als waeren sie
   aktuell. Ein Diagramm, das heimlich aufhoert sich zu fuellen, ist schlimmer als ein entferntes.
2. Im Kartentitel steht das Wort **„Score"**.
3. Eine Linie ueber Wochen auf einer 0-bis-100-Achse liest jeder als **seine eigene Entwicklung** —
   unabhaengig davon, was darueber geschrieben steht. Und auf **demselben Bildschirm** entfernen wir
   zwei Stunden vorher einen Trend-Streifen ersatzlos. Beides zugleich ist inkonsequent.

**Deine Aufgabe:** Wer hat recht? Ist Grund 1 (die Quelle stirbt naechste Phase) wirklich das
staerkste Argument — oder ist es umgekehrt ein Argument fuer (a), weil es dann ohnehin bald faellt
und man jetzt keinen zusaetzlichen Umbau bezahlt? Gibt es einen dritten Weg (z. B. Diagramm bleibt,
aber Titel und Achse aendern)? Und: Ist der Unterschied zwischen **einem Einzelwert** („dieser Kunde
war bei 62") und einer **Wochen-Trendlinie** wirklich so bedeutsam, wie ich behaupte — oder rede ich
mir das ein?

---

## Zum Schluss

Sag pro Frage klar: Empfehlung + was du an unserer Begruendung fuer schwach haeltst. Wenn du bei
einer Frage keine bessere Idee hast, sag auch das.
