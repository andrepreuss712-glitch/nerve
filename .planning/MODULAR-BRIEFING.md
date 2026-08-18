# NERVE — Modularer Umbau der GANZEN App + sechs Strategie-Themen

## ⛔ VORWEG: DIE ENTSCHEIDUNG IST GEFALLEN. GEGENREDE IST NICHT DIE AUFGABE.

Andre (Gruender, Auftraggeber) hat am 2026-08-17 entschieden: **Die App wird modular neu
geschnitten. Ganze App, nicht nur einzelne Pfade.** Woertlich: *„zauberwort: modulare bauweise.
ab jetzt. nur noch."* Und: *„komm mir nicht zurueck mit 'die anderen raten davon ab'. ist mir
scheiss egal."*

**Was das fuer dich heisst:**
- **Deine Aufgabe ist der SCHNITT, nicht die Frage ob.** „Zu teuer", „zu riskant", „lieber
  schrittweise" ist **keine** verwertbare Antwort.
- **Risiken benennst du als AUFLAGE IM SCHNITT**, nicht als Gegenrede. Beispiel: nicht *„den
  Live-Pfad wuerde ich nicht anfassen"*, sondern *„Baustein X wird zuletzt geschnitten, mit
  folgendem Sicherheitsnetz, weil dort die Latenz haengt."*
- Wenn ein Schnitt fachlich unmoeglich ist, sag es — **aber mit dem Alternativ-Schnitt daneben.**

---

## Warum der Umbau kommt — die Belege der letzten Woche

Vier Fehler, vier Tage, **immer dieselbe Wurzel**:

| Fehler | Wurzel |
|---|---|
| „Naechster Call" raeumt den Nach-Anruf-Zustand nicht auf (`nextCall()` ruft `_resetLiveState()` nicht) | Aufraeumen liegt bei **jedem Weg einzeln** — einer vergisst es |
| Spracherkennung hart auf `language="de"` (`deepgram_service.py:583`), obwohl die Sitzung ihre Sprache kennt (`:836`) | Konfiguration wird **nicht besessen**, jeder greift selbst zu |
| Redeanteil-Norm in **zwei** Dateien (`judge_runner.py`, `judge_dimensions.py`) — eine Loeschung haette die andere uebersehen | **Dieselbe Fachregel an zwei Orten** |
| Die alte Note an **zwoelf** Lesestellen, drei davon nur ueber Fliesstext in KI-Auftraegen auffindbar | **Kein Besitzer** — jeder liest direkt in die Rohdaten |

**Der gemeinsame Nenner: Nichts gehoert jemandem.** Werte und Regeln liegen frei herum, jeder
Aufrufer greift direkt zu, Aufraeumen ist Hoeflichkeit statt Bauart. **Deshalb halten unsere
Waechter nicht** — sie bewachen eine Stelle, waehrend dieselbe Sache an vier anderen offenliegt.

**Der Leitsatz, an dem sich jeder Schnitt messen lassen muss:**
> **Jedes Ding hat genau einen Besitzer. Wer es braucht, fragt ihn — niemand greift daran vorbei.**

---

## Was NERVE ist (fuer die Aussensicht)

Live-Assistent fuer Kaltakquise-Telefonate, Zielmarkt **USA**, vor dem Start (keine echten Kunden).
Waehrend des Anrufs hoert das System aus Datenschutz-Gruenden **nur den Verkaeufer**, nie den
Kunden, und gibt ihm live Hinweise. Nach dem Anruf eine Rueckmeldung mit woertlichem Zitat.
**Es wird kein Audio gespeichert.** Technisch: Python/Flask + Postgres auf einem Server, Browser-
Oberflaeche mit einem kleinen Zusatzfenster waehrend des Anrufs, Spracherkennung und Sprachmodell
als fremde Dienste. **Latenz ist ein Dealbreaker** — eine Antwort, die im Gespraech zu spaet kommt,
ist wertlos.

---

# AUFGABE A — DER MODULARE SCHNITT DER GANZEN APP

**Liefere einen konkreten Bauplan, keine Prinzipien-Liste.** Erwartet:

1. **Die Bausteine.** Welche gibt es, wie heissen sie, **was besitzt jeder** (Daten, Regeln,
   Zustand)? Deutsche Namen, die ein Nicht-Entwickler versteht.
2. **Die Vertraege.** Was darf ein Baustein von aussen? Was ist ausdruecklich verboten?
3. **Die Zuordnung.** Welche heutige Datei/Funktion wandert in welchen Baustein — und **was
   zerfaellt**, weil es heute zwei Dinge gleichzeitig tut.
4. **Die Reihenfolge.** Welcher Baustein zuerst, welcher zuletzt, **und warum**. Wo braucht es ein
   Sicherheitsnetz, damit unterwegs nichts kaputtgeht.
5. **Die vier Fehler oben:** Zeig **je Fehler**, welcher Baustein ihn kuenftig **per Bauart**
   unmoeglich macht. Wenn dein Schnitt einen davon nicht faengt, ist der Schnitt falsch.
6. **Was dabei WEGFAELLT.** Der Umbau muss Code **entfernen**, nicht nur umschichten. Nenne
   konkret, was ersatzlos verschwindet.
7. **Die Grenze zur Latenz.** Welcher Baustein liegt im schnellen Live-Pfad? Dort ist jede
   zusaetzliche Schicht ein Risiko — sag, wie du ihn schneidest, **ohne** eine Schicht dazwischen
   zu legen.

⚠ **Nicht abstrakt bleiben.** „Trenne Zustaendigkeiten" ist wertlos. Ich will Datei- und
Funktionsnamen.

---

# AUFGABE B — SECHS THEMEN VON ANDRE

Andres eigener Text, gekuerzt. **Bewerte jedes: sinnvoll fuer uns? jetzt oder spaeter? wie gross?**

**1 · Chrome-Erweiterung als Zielplattform.** Im US-B2B-Vertrieb ist Chrome der Standard (~75 %
inkl. Edge/Arc). Eine Erweiterung waere die beste Grundlage fuer ein leichtes Live-Overlay und
regelt Updates ueber den Web Store. **Frage: Wie weit ist unsere heutige Browser-Oberflaeche davon
entfernt? Was ist der schlankste Weg dorthin — und was am heutigen Live-Fenster ist Wegwerf-Arbeit,
wenn wir das machen?**

**2 · Eigener Schluessel des Kunden (BYOK).** Bei Vielnutzern mit 100+ Anrufen/Tag koennen die
Kosten der fremden Dienste explodieren. Idee: Vielnutzer hinterlegen ihren **eigenen** Zugang, wir
nehmen nur eine Grundgebuehr (~$99–149/Monat); bequeme Nutzer bekommen ein Komplettpaket mit Deckel.
**Frage: Wie aufwendig ist ein solches Feld in den Einstellungen im heutigen Code? Was haengt alles
daran (Kosten-Erfassung, Abrechnung, Fehlerbehandlung bei fremdem Schluessel)?**

**3 · Sicherheit der fremden Schluessel.** Wenn Kunden eigene Schluessel nutzen, duerfen die
**niemals** in unserer Datenbank oder auf unserem Server liegen (Leck- und Haftungsrisiko).
**Frage: Geht das rein im Browser des Kunden (`chrome.storage.local`) mit direktem Aufruf oder ueber
einen fluechtigen Durchreicher? Was bricht dabei — Kosten-Erfassung? Schwaerzung? Kaeme unser
Datenschutz-Versprechen ins Wanken?**

**4 · Modell-Weiche (Anbieter/Modell wechselbar).** Wer starr an einem Modell haengt, ist bei
Stoerungen und Latenz-Spitzen ausgeliefert. Eine Zwischenschicht koennte Anbieter wechseln und
schnelle, billige Modelle zum **Vorfiltern** nutzen. **Frage: Wie modular ist unsere heutige
Anbindung? Und ⚠ Vorsicht: Eine Zwischenschicht im Live-Pfad kostet Latenz — wie baut man sie so,
dass sie nichts kostet?**

**5 · Waechter- und Kommentar-Last.** Wir haben viele Waechter und sehr ausfuehrliche Kommentare
eingebaut, um Brueche zu verhindern. **Andres Sorge: Sie stopfen das Kontextfenster voll und machen
den Code unlesbar.** **Frage: Stimmt das, gemessen? Welche Waechter tragen wirklich, welche sind
Rauschen? Und: Welche Kommentare koennten in den modularen Vertraegen aufgehen — also durch Bauart
ersetzt werden statt durch Prosa?** ⚠ Fairness: Mehrere dieser Waechter haben in den letzten Wochen
**echte** Fehler gefangen. Nicht pauschal abraeumen — trennen.

**6 · Lokal testen gegen Server testen.** Wir entwickeln seit Monaten **ausschliesslich** auf dem
Live-Server, weil lokal sich anders verhielt (andere Voreinstellungen, Zertifikate, Datenbank).
Nach dem Start brauchen wir eine saubere Trennung. **Frage: Warum genau verhielt sich lokal anders?
Und wie sieht der pragmatische Weg zu einer Testumgebung aus, die nicht selbst zur Drift-Quelle
wird — das war sie bei uns schon einmal.**

**Zusaetzlich, weil es zum Umbau gehoert:** Wir arbeiten heute direkt auf dem Hauptstrang. Andre
will Zweige (`feature/...`). **Frage: Wie schneidet man das so, dass es die Ausroll-Kette nicht
bremst?**

---

## Form der Antwort

Pro Aufgabe: knapp, auf **Deutsch**, in Klartext ohne englische Fachbegriffe (der Leser ist kein
Entwickler). Jede Aussage ueber den heutigen Zustand **mit Beleg** (Datei:Zeile oder echtes
Suchergebnis). Erschlossenes ausdruecklich als Vermutung kennzeichnen. „Nichts gefunden" gilt nur
mit gepaartem Existenz-Anker.

**Am Ende eine Prioritaeten-Liste:** Was zuerst, was danach, was nach dem Start — mit einem Satz
Begruendung je Zeile.
