# BRIEFING — Vierte Spalte bauen oder nicht? Und: ich habe einen Fund widerlegt — halte ich stand?

Du bist Gegenleser. **Nichts lesen, nichts schreiben, nichts ausführen** — alle Fakten stehen unten. Antworte auf Deutsch, direkt, ohne Floskeln. **Deine Aufgabe ist NICHT zuzustimmen.** Greif an, wo es hält.

## Kontext

NERVE = Live-Assistent für Verkaufstelefonate. Ein-Mann-Projekt, vor Marktstart, **keine zahlenden Kunden**. Der Bau-Agent (GSD) hat eine kleine Phase geplant: **Sprech-Zeiten dauerhaft speichern**, damit Redeanteil, Sprechtempo, Redeblock-Länge und Pausenlänge überhaupt rechenbar werden. Heute wird nur der *Beginn* eines Gesprächsabschnitts gespeichert, und der ist auf **ganze Sekunden** gerundet.

Beschlossen sind drei neue Werte je Abschnitt: **Beginn, Ende, Wortanzahl** — alle aus den Zeitangaben des Spracherkenners (millisekundengenau), getrennt von der alten groben Uhr.

## Streitpunkt 1 — eine VIERTE Spalte?

Ich hatte eine Vorgabe gemacht: *„Reißt die Verbindung mitten im Anruf, ist die Pause an dieser Stelle **unbekannt**, nicht **0**."* Begründung: Eine 0 ist ein Wert und wird in jeden Mittelwert eingerechnet; eine Naht ist aber keine kurze Pause, sondern eine unbekannte. (Dieselbe Logik wenden wir eine Zeile weiter oben schon an: fehlende Wortanzahl = „unbekannt", nicht 0.)

GSD leitet daraus eine **vierte Spalte** ab, die solche Nähte markiert — weil sich „unbekannt" mit drei reinen Zahlen-Spalten nicht ausdrücken lässt. Er markiert sie ausdrücklich als **vorläufig, nicht freigegeben**.

**Und dann liefert er selbst das Gegenargument:** Es gibt **zwei** mögliche Nahtquellen, und **keine davon ist heute erreichbar** —
- **Pause:** Das Pause-Merkmal hat **null Setzer** bei sieben Fundstellen (ich habe nachgezählt: alle Treffer sind Lesezugriffe plus eine Initialisierung auf „falsch"). Der Mikrofon-Knopf schaltet nur die Tonspur stumm — es fließt weiter Stille, die Uhr läuft mit.
- **Wiederverbindung:** dazu Streitpunkt 2.

## Meine Position (greif sie an)

**Vierte Spalte jetzt NICHT bauen.** Begründung:
1. Es gibt heute **keine Naht, die entstehen könnte** → die Spalte enthielte nie etwas anderes als ihren Leerwert. Das ist **eine Spalte ohne Schreiber** — genau die Fehlerklasse, die wir in diesem Projekt in einer Woche dreimal gefunden haben („bezahlte Arbeit ohne Empfänger": ein Termin-Feld, das niemand liest; eine Kundenakte ohne Schreiber; ein Lesepfad, der immer leer läuft).
2. **Wir verlieren nichts durch Warten.** Unsere Türöffner-Regel schützt vor unwiederbringlichen Datenlücken — hier gibt es nichts zu erfassen, also nichts zu verlieren.
3. Eine Spalte ist nicht gratis: Schema-Fläche, Doku-Schild, Tests, und irgendwann liest sie jemand und nimmt an, sie bedeute etwas.
4. Sobald Wiederverbindung oder Pause erreichbar werden, **muss** die Markierung in derselben Phase mitkommen — als harte Notiz festgehalten.

## Streitpunkt 2 — ich habe GSDs größten Fund widerlegt. Halte ich stand?

GSD meldete als wichtigsten Befund der ganzen Phase:
> *„Der Wiederverbindungs-Pfad ruft `pop_session_state` + `init_session_state`, bevor die `call_id`-Prüfung greift — er löscht den kompletten `conversation_log`. Bei einem Verbindungsabriss ist nicht die Zeitmessung weg, sondern das ganze bisherige Transkript des Anrufs. Und `pip-launcher.js` versucht keine Wiederverbindung."*

Das wäre gravierend — in diesem Projekt gilt die unverhandelbare Regel **„Gesprächs-Protokolle werden NIE gelöscht"** (sie sind Trainingsmaterial für eine eigene spätere KI).

**Ich habe es am Code nachgeprüft und komme zu drei Gegenbefunden:**
1. Die Lösch-Stelle sitzt im **Anruf-Start-Behandler**, nicht in einem Wiederverbindungs-Pfad. Der Kommentar dort sagt: „Neu-Initialisierung folgt sofort."
2. Der Startbefehl (`start_live_session`) wird an **genau einer Stelle** im Browser-Code gesendet — im Start-Ablauf. Der Wiederverbindungs-Zweig (`socket.on('connect')`) sendet ihn **nicht**; er holt nur den Anruf-Ausgang nach.
3. Der Browser **versucht sehr wohl** eine Wiederverbindung: automatisch, **3 Versuche, 2 Sekunden Abstand** (Einstellung im Verbindungsaufbau). GSDs Gegenteil-Behauptung ist falsch.

**Daraus folgere ich:** Die beschriebene Ursachen-Kette trägt nicht. **Aber ich behaupte ausdrücklich NICHT, dass alles in Ordnung ist** — was bei einer Wiederverbindung tatsächlich passiert, habe ich **nicht** geklärt. Ich lasse es als offene Frage stehen, statt eine Ersatz-Erklärung zu erfinden (wir haben eine harte Regel gegen erfundene Ursachen-Ketten).

⚠ **Und der Punkt, der mir Sorge macht:** GSDs *Schlussfolgerung* („eine Naht kann heute nicht entstehen") ist vermutlich **richtig** — aber teils aus einer **falschen** Begründung. Eine richtige Antwort mit falscher Begründung hält nur, bis jemand die Begründung prüft.

## Deine Fragen

1. **Zur vierten Spalte: hat meine Begründung Löcher?** Insbesondere — ist „keine Naht möglich, also keine Spalte" wirklich sicher, oder übersehe ich eine dritte Nahtquelle, die weder Pause noch Wiederverbindung ist? Denk an: Serverneustart mitten im Anruf, Ausrollen während eines Gesprächs, Netzwechsel (WLAN → Mobilfunk), Standby des Rechners, Browser-Tab im Hintergrund, mehrere Tabs, Abbruch beim Spracherkenner selbst.
2. **Gegenposition zwingend formulieren:** Was spricht dafür, die Spalte **doch jetzt** zu bauen? Nimm den stärksten Fall, den du bauen kannst — nicht den schwächsten.
3. **Zu meiner Widerlegung:** Ist meine Beweisführung tragfähig, oder habe ich zu schnell entwarnt? Was müsste ich prüfen, um von „die Kette trägt nicht" zu „bei Wiederverbindung passiert Folgendes" zu kommen?
4. **Das methodische Problem:** Wie geht man damit um, wenn eine Schlussfolgerung stimmt, aber die Begründung falsch war? Durchwinken, weil das Ergebnis passt — oder Begründung nachziehen? Was ist hier verhältnismäßig?
5. **Eine Empfehlung** zu Streitpunkt 1, mit dem, was dagegen spricht.

Kurz und dicht. Kein Code nötig.
