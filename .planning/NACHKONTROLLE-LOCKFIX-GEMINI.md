# Adversariale Nachkontrolle — Riegel pro conv_id (Phase 08.23.2.MEHRNUTZER-REST-1)

Du bist ein erfahrener Python-Nebenlaeufigkeits-Spezialist, der diesen Code ZUM ERSTEN MAL sieht
und ihn fuer die Freigabe annehmen oder ablehnen muss. Du bist bewusst kritisch und hast keine
Bindung an den Code. **Deine Aufgabe ist, ihn zu WIDERLEGEN, nicht ihn zu bestaetigen.**

Finde mindestens DREI konkrete Probleme. Findest du weniger, hast du nicht gruendlich genug gesucht.
Falls du wirklich keines findest, sage das ausdruecklich — aber begruende dann fuer JEDE der unten
gestellten Angriffsfragen einzeln, warum sie ins Leere geht.

## Kontext in drei Saetzen

Vorher hielt `services/coaching_service.py` **einen prozessweiten `threading.Lock`** ueber dem
gesamten Rumpf von `generate_postcall_analysis()` — inklusive eines HTTP-Aufrufs an ein
Sprachmodell mit bis zu 45 s Timeout. Jeder Nutzer wartete auf jeden anderen.
Der Fix ersetzt ihn durch **einen Riegel pro `conv_id`** mit Nehmer-Zaehler und Aufraeumen.
Der Duplikatschutz (nur EINE Analyse pro Gespraech) muss dabei **exakt gleich stark** bleiben.

## Was du lesen sollst (echter Code, nur lesen)

- `services/coaching_service.py` — die Funktion `_analysis_lock_for()` und ihre Verwendung
  in `generate_postcall_analysis()` (der `count()`-Duplikat-Guard liegt INNERHALB des Riegels).
- `routes/learning.py` — die beiden Aufrufer (`/api/postcall_analysis`, `/api/postcall_cards`).

Laufzeit-Umgebung: gunicorn `--worker-class gthread --workers 1 --threads 64`.
Es gibt **keinen** Unique-Constraint auf `learning_cards.call_id` (bewusst: bis zu 3 Karten pro Call).
Der Duplikatschutz haengt damit **allein** an diesem Riegel.

## Die Angriffsfragen — beantworte JEDE einzeln

1. **Last-Szenario:** Der mitgelieferte Test prueft ZWEI gleichzeitige Faeden. Konstruiere ein
   Szenario mit 40 gleichzeitigen Faeden (gemischt: gleiche und verschiedene conv_id, einige mit
   Exception im Rumpf, einige mit Timeout im HTTP-Aufruf). Bricht dabei der Duplikatschutz?
   Kann ein Eintrag in `_conv_locks` dauerhaft haengen bleiben?

2. **Zaehler-Integritaet:** Gibt es einen Ablauf, nach dem der Nehmer-Zaehler dauerhaft > 0 bleibt,
   obwohl kein Faden mehr im kritischen Abschnitt ist? Oder umgekehrt: kann er auf 0 fallen,
   waehrend noch jemand drin ist?

3. **Reihenfolge:** `release()` steht VOR dem Dekrement, das Dekrement steht unter dem
   Ablage-Riegel, und das Loeschen prueft `_conv_locks.get(key) is eintrag`.
   Findest du eine Verschraenkung von zwei oder drei Faeden, bei der diese Reihenfolge trotzdem
   zu zwei gleichzeitigen Riegeln unter demselben Key fuehrt?

4. **Verklemmung:** Kann es zu einer Verklemmung kommen — insbesondere: nimmt irgendein Pfad den
   Ablage-Riegel, waehrend er den conv-Riegel haelt, oder umgekehrt? Gibt es einen re-entranten
   Pfad (Funktion ruft sich mittelbar selbst)?

5. **Key-Bildung:** Der Schluessel ist `str(conv_id)`. Die Aufrufer lesen `conv_id` ungecastet aus
   JSON. Findest du einen Fall, in dem zwei Anfragen, die DENSELBEN Datensatz meinen,
   VERSCHIEDENE Schluessel bekommen — oder umgekehrt zwei verschiedene Datensaetze denselben?

6. **Was der Fix NICHT loest:** Wir behaupten, er beseitige die Wartezeit, nicht den
   Thread-Verbrauch (50 Anruf-Enden belegen weiterhin 50 von 64 Threads, nur ~45 s statt ~37 min).
   Stimmt diese Aussage? Oder uebersehen wir eine Verschlechterung — z.B. dass jetzt 50 HTTP-Aufrufe
   GLEICHZEITIG statt nacheinander laufen (Rate-Limit beim Anbieter, Speicher, Verbindungs-Pool)?

7. **Der ehrlich benannte Restfall:** Zwischen der Rueckkehr von `acquire()` und dem Setzen des
   Flags `erworben = True` liegt eine Bytecode-Grenze. Wir behaupten, das sei praktisch nicht
   erreichbar, weil CPython Signale nur im Hauptthread ausliefert und diese Funktion immer in
   einem Worker-Thread laeuft. **Stimmt das?** Gibt es andere Wege, dort hineinzugeraten
   (z.B. `Thread.stop`-aehnliche Mechanismen, `gevent`/Monkey-Patching, Prozess-Signale unter
   gthread)?

## Ausgabeformat

Pro Angriffsfrage: **BEFUND** oder **GEHT INS LEERE**, mit Begruendung in maximal 5 Saetzen.
Am Ende: eine Gesamtempfehlung (FREIGEBEN / NACHBESSERN / ABLEHNEN) mit einem Satz Begruendung.
Sei knapp. Kein Lob, keine Zusammenfassung des Codes — nur Befunde.
