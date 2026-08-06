# BRIEFING: Reicht diese Regel, damit ab jetzt NUR NOCH mehrnutzerfaehig gebaut wird?

**Deine Rolle:** dritte, unabhaengige Sicht. **Zerlege, bestaetige nicht.** Du hast keine Dateizugriffe — alles Noetige steht unten. Antworte auf Deutsch, kompakt, konkret.

---

## 1. DER VORFALL (Ausgangslage, alles am Code belegt)

Produkt: NERVE, Live-Assistent fuer Verkaufsgespraeche. Python/Flask + Socket.IO (`async_mode='threading'`), **EIN Gunicorn-Worker mit 64 Threads**, Postgres, Deepgram-Spracherkennung, Claude-Analyse. Verkauft wird **Tempo** — eine spuerbar spaetere Antwort ist im Live-Gespraech wertlos.

**Gestern erstmals gemessen (Prod):** Analyse-Aufruf Ø 1988 ms, Coaching-Aufruf Ø 2714 ms, Post-Call-Auswertung 15194 ms.

**Der Befund:** Das System traegt keine gleichzeitigen Nutzer.
- Drei Daemon-Schleifen iterieren **sequentiell ueber alle Sitzungen** (`for sid in active_sids`), zwei davon im Live-Pfad, eine danach.
- **Ein globaler, nicht-reentranter Riegel** fuer alle Sitzungen, 105 Erwerbsstellen in 8 Dateien.
- **Kein Zeitlimit** auf den Live-KI-Aufrufen: ein Haenger legt alle Gespraeche bis ~30 min still.
- **5 Anonymisierungs-Fehler eines Nutzers** schalten die DSGVO-Schwaerzung **prozessweit** ab.
- **2-4 eigene DB-Sitzungen pro Analyse-Runde und Sitzung**; bei 20 parallelen Anrufen 40-80 Verbindungen gegen einen Pool von 35 → der Server friert ein, statt langsam zu werden.
- **Der gesamte Live-Zustand liegt im RAM EINES Prozesses**, Socket.IO ohne `message_queue`, `redis` fehlt in `requirements.txt`. Ein zweiter Worker ist heute unmoeglich.
- **Drei HTTP-Eingaenge** loesen fremde Sitzungen/Anrufe ueber geratene Kennungen auf, ohne Eigentuemer-Pruefung (einer davon schreibend).

**Das Entscheidende — es war KEINE Blindheit.** An genau der kritischen Stelle steht seit Monaten dieser Kommentar im Code:

> `# O(N) SEQUENTIAL: Claude-Calls laufen sequentiell pro SID — Loop-Zeit waechst linear.`
> `# Schwellwerte (Messung ausstehend):`
> `#   N=1: ~1-3s, N=5: ~5-15s (KRITISCH), N=20: >20s (nicht mehr Echtzeit)`
> `# Ab N=5 und Cycle-Zeit > 3s: Migration zu ThreadPoolExecutor.`
> `# Naechste Phase: Block-M. Accepted for EA (50 users max).`

Also: gesehen, korrekt eingeschaetzt, als "fuer Early Access akzeptiert" eingestuft — **auf Basis einer ausdruecklich ungemessenen Zahl** — und dann nie wieder aufgerufen. **Zwei Monate.**

**Erschwerend:** Es gab im Juli sogar eine ganze Phase, die genau in diese Richtung ging (Umstellung des Live-Zustands auf "pro Sitzung", 18 Dokumente, 6 Plaene, Waechter-Tests). Sie hat die **Datenvermischung** behoben — den **Durchsatz** nicht, obwohl der Kommentar danebenstand. Der Zuschnitt der Phase ("Datenvermischung") hat die zweite Haelfte ausgeschlossen.

**Zusaetzlich nie belegt:** Es gab **nie zwei gleichzeitige echte Anrufe**. Alle Tests laufen gegen nachgebaute Sitzungen; die Zwei-Konten-Pruefung im Browser steht seit Juli als "deferred", weil kein zweites Firmenkonto anlegbar war.

---

## 2. WAS ICH ALS REGEL VORGESCHLAGEN HABE

Es gibt bereits eine Regel "Foundation-Register": Code, der heute ungenutzt dasteht, aber bewusst bleibt, weil eine spaetere Phase ihn aktiviert, kommt in ein Register mit drei Spalten (was · warum stehen geblieben · welche Phase aktiviert es). Mein Vorschlag erweitert sie um eine zweite Sorte Eintrag:

> **Aufgeschobene Entscheidungen gehoeren ins selbe Register wie Foundation-Code.**
>
> **Ausloeser (Eintrag Pflicht, im selben Arbeitsschritt):** immer wenn in Plan, Audit, Review oder Code-Kommentar sinngemaess steht "reicht fuer jetzt", "akzeptiert fuer Early Access", "spaeter", "Phase X kuemmert sich", "Messung ausstehend" — **und die Sache damit vom Tisch ist, ohne geloest zu sein.**
>
> **Vier Pflichtfelder:** (1) Was wurde zurueckgestellt, in einem Satz. (2) Worauf stuetzt sich das "reicht" — gemessen oder geschaetzt? Geschaetzt wird markiert. (3) Die Bedingung, unter der es zurueckkommt — **pruefbar, kein Datum**. (4) Was passiert, wenn wir die Bedingung verpassen.
>
> **Ein Code-Kommentar erfuellt die Pflicht NICHT** — er wird nur von dem gelesen, der zufaellig die Datei oeffnet. Der Eintrag gehoert ins Register **und** in die Roadmap-Uebersicht.

**Meine eigene Skepsis, die du bitte prueft:** Das ist eine **Merk-Regel, keine Bau-Regel.** Sie verhindert, dass etwas vergessen wird. Sie verhindert **nicht**, dass etwas von vornherein nicht-skalierbar gebaut wird. Und sie greift nur bei **bewussten** Verschiebungen — wer die Frage gar nicht stellt, traegt auch nichts ein.

---

## 3. DIE ANFORDERUNG DES GRUENDERS (woertlich sinngemaess)

> *„Es ist wichtig, dass alles, was wir ab jetzt bauen, auf Multi-User ausgelegt ist und kein User einen Nachteil bei mehreren gleichzeitigen Usern bekommt. Wichtig ist, dass die Bauweise skalierbar ist. Heisst: wenn wir jetzt etwas fuer 500 User bauen, muss es z. B. spaeter auch fuer 5000 skalierbar und nutzbar sein."*

Beschlossen ist bereits: die Live-Engine wird **neu gebaut** (asyncio/FastAPI, Zustand pro Verbindung) — **plus** die Auswertung nach dem Anruf, die im heutigen Entwurf fehlt.

---

## 4. MEINE FRAGEN AN DICH

1. **Wuerde meine Regel den beschriebenen Vorfall verhindert haben?** Ehrlich — ja/nein/teilweise, und woran genau haette sie gegriffen bzw. nicht gegriffen.
2. **Was fehlt, damit die Anforderung des Gruenders erfuellt ist?** Eine Merk-Regel reicht offensichtlich nicht. Was braucht es zusaetzlich — und zwar so, dass es **pruefbar** ist und nicht an Disziplin haengt? Wir haben belegt schlechte Erfahrungen mit Prosa-Regeln: was keinen automatischen Waechter hat, kommt wieder.
3. **Formuliere die fehlenden Bau-Regeln konkret.** Nicht "denkt an Skalierung", sondern Saetze, gegen die man einen fertigen Plan pruefen kann — mit klarem Ausloeser und klarer Verbots-/Gebotsformulierung. Maximal 5-7 Stueck; wir haben belegt, dass ab ~40 gleichzeitig geltenden Regeln die Befolgung stark einbricht, also zaehlt Praezision mehr als Vollstaendigkeit.
4. **Welche dieser Regeln liesse sich automatisch pruefen?** (statische Analyse, Test, Deploy-Tor) — und wie ungefaehr?
5. **Skalierbarkeit 500 → 5000: welche Entscheidungen muessen JETZT richtig fallen, damit das spaeter nur eine Frage von mehr Maschinen ist?** Und welche sind Einbahnstrassen — also: wo ist ein Fehler jetzt spaeter nicht mehr billig korrigierbar? Denk an: Zustandshaltung, Sitzungs-Zuordnung, Datenbank-Zugriffsmuster, Nachrichten-Verteilung, Hintergrundarbeit, Mandantentrennung.
6. **Wo widersprichst du dem Gruender?** Gibt es einen Punkt, an dem "ab jetzt alles auf 5000 auslegen" die falsche Vorgabe waere — etwa weil sie zu Ueberbau fuehrt, bevor das Produkt sich bewiesen hat? Sag es klar, wenn ja.
7. **Welche Frage haette ich stellen muessen und habe sie nicht gestellt?**
