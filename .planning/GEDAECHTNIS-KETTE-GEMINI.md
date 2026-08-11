# BRIEFING — Wissen von Anruf zu Anruf mitnehmen: richtig, und was muss JETZT dafür gebaut werden?

> ⛔ **ARCHIV-BRIEFING — NICHT UNVERÄNDERT WIEDERVERWENDEN (Hinweis 2026-08-11).**
> Der Zuschnitt darin ist überholt: Es führt **(A) Kurzzeit-Gedächtnis, (B) Freie-Antwort-Knopf und (C) Spiegel-Marker als EINEN Jetzt-Bau**. **Seit 11.08. gilt: nur (A) jetzt** (eigene Phase vor dem Engine-Neubau, ~30–50 Zeilen, alle Nahtstellen-Blocker durch PERSID erledigt), **(B) und (C) am Engine-Neubau.** Wer dieses Briefing erneut verschickt, bekommt eine Gegenlese **gegen den geltenden Zuschnitt**.

Du bist Gegenleser. **Nichts lesen, nichts schreiben, nichts ausführen.** Antworte auf Deutsch, direkt, ohne Floskeln. Stimme nicht aus Höflichkeit zu.

## Die Idee des Gründers (wörtlich)

> „Nach einer erfolgreichen Kaltakquise trägt man ja z.B. vor der Auswertung den Termin fürs Meeting ein. Was wäre, wenn man dann vor einem Meeting einmal das Transkript aus der Kaltakquise ins Meeting laden kann und ggf. Dinge hinzufügen kann, worüber man mit dem Kunden sprechen möchte? Dann wüsste die KI direkt, was im Cold Call besprochen wurde und was der User im Meeting ansprechen möchte. Vielleicht kann der User auch weitere Informationen ins Meeting mitnehmen, damit die KI besser helfen kann. Dasselbe dann wieder von Meeting zu Meeting, solange derselbe Kunde involviert ist. Meeting 1, Meeting 2, Meeting 3 usw. bis zum Abschluss.
>
> Wenn nicht, wäre der Eintrag vor der Auswertung, wo der User den genauen Termin eintragen kann, komplett nutzlos. Dann hätte es gereicht, wenn der User einfach nur angibt, wie das Telefonat gelaufen ist — also ‚Termin', ‚E-Mail' oder oder oder."

Er ergänzt: **„Datenschutztechnisch muss man da wahrscheinlich sehr aufpassen."**

## Kontext, den du brauchst

**Das Produkt:** NERVE ist ein Live-Assistent für Verkaufstelefonate. Ein-Mann-Projekt, vor dem Marktstart, keine zahlenden Kunden. **Markt ist US-first** (Gründer ist deutscher Einzelunternehmer, DSGVO gilt für ihn trotzdem).

**Zwei Betriebsarten, rechtlich unterschiedlich:**
- **Kaltakquise:** NERVE hört **NUR den Verkäufer**. Der Kunde wird technisch gar nicht erfasst — Headset-Pflicht ist die tragende Rechtskonstruktion. Das Transkript enthält also **die Worte des Verkäufers**, plus Rückschlüsse der KI auf das, was der Kunde gesagt haben könnte.
- **Meeting:** beide Seiten, nur nach ausdrücklicher Einwilligung mit vorgelesenem Text. Bei Ablehnung fällt es auf Kaltakquise-Modus zurück.

**Unverhandelbare Schranken:** NERVE speichert **nie Audio**. Transkripte werden anonymisiert gespeichert (Namen, Firmen, Telefon, E-Mail werden ersetzt). Gesprächs-Protokolle werden nie gelöscht (Trainingsmaterial für die eigene spätere KI).

**US-Rechtslage, bereits recherchiert:** In etwa einem Dutzend US-Bundesstaaten müssen ALLE Beteiligten der Aufzeichnung zustimmen. Es laufen aktuell Klagen gegen Anbieter, die **Sprecher-Trennung** einsetzen (Biometrie-Vorwurf) und gegen Anbieter, die Kundendaten für **eigene Zwecke** nutzen (Anbieter als „heimlicher Dritter"). 1.000–5.000 $ pro Verstoß, ohne Schadensnachweis.

## Was dazu schon entschieden ist (02.07., drei Sichten deckungsgleich)

Ein kanonisches Dokument hält fest — Zitate:

**JETZT gebaut wird (Kaltakquise-first):**
- Kurzzeit-Gedächtnis der letzten 3–5 Züge **innerhalb eines Gesprächs**, inklusive NERVEs eigener Vorantworten.
- Ein „Freie Antwort"-Knopf: der Verkäufer spiegelt die Kundenantwort laut, NERVE macht daraus weiter.
- **Ein „Gespiegelt"-Marker + gesenkte Konfidenz** — ausdrücklich als *„der eine nicht-nachholbare Türöffner"* bezeichnet: Wenn nicht markiert wird, ob eine Aussage vom Kunden echt kam oder vom Verkäufer nachgesprochen wurde, ist das für alle betroffenen Gespräche **für immer verloren**.

**SPÄTER, ausdrücklich vertagt („nur Tür offen halten"):**
- Manueller Wissens-Eingang **über Betriebsarten hinweg** (`source=manual` als gleichrangige Quelle).
- Abgeleitete Kunden-Übersicht + Zusammenfassung nach dem Anruf, jeweils **frisch aus den Roh-Ereignissen** (ausdrücklich keine Zusammenfassung von Zusammenfassungen — Drift-Gefahr).
- **Zwei Zeiten** je Fakt: wann galt es, wann haben wir es erfahren.
- **„Cold-Call→Meeting- und Meeting→Meeting-Wissens-Zusammenlauf."** ← exakt die Idee des Gründers, bereits beschlossen.

**Der Speicher steht bereits:** Es gibt ein nur-anhängendes Ereignis-Log je Gespräch (mit harter Anruf-Zuordnung, Konfidenz, Betriebsart, Zeitstempel, anonymisiertem Auslöse-Text und einem freien Reserve-Feld für Erweiterungen ohne Umbau). Es gibt bereits eine Vorab-Recherche vor dem Kaltanruf als manuellen Wissens-Eingang.

**Eigene Regel dazu (hart):** *„Ein Türöffner ist nur dann richtig gebaut, wenn er das spätere Feature, das dranhängen soll, auch tragen kann. Vor dem Bau eines Türöffners: das Ziel-Feature grob skizzieren und belegen, dass der Haken es aufnimmt. Besonders kritisch bei nur-anhängender Erfassung — verpasste Felder sind für immer weg, kein Nachtragen möglich."*

## Deine Fragen

1. **Ist die Idee richtig?** Trägt „Wissen wandert Kaltakquise → Meeting 1 → Meeting 2 → … bis zum Abschluss" als Produkt — oder gibt es einen Grund, es NICHT zu bauen?

2. **Der schärfste Punkt des Gründers, prüf ihn:** Er sagt, ohne diese Kette sei das Eintragen des **genauen Termins** nach dem Anruf *„komplett nutzlos"* — dann würde ein simples „Termin / E-Mail / kein Interesse" reichen. **Hat er recht?** Wenn ja: Was heißt das für das Feld, das heute schon existiert und ausgefüllt wird?

3. **Datenschutz + US-Recht — der Kern.** Was ist die Falle?
   - Das Kaltakquise-Transkript enthält im Wesentlichen die Worte des **Verkäufers**, nicht des Kunden. Entschärft das die Sache — oder täuscht das?
   - Im Meeting hat der Kunde in **dieses eine** Gespräch eingewilligt. Deckt diese Einwilligung ab, dass Meeting 1 später in Meeting 3 wieder eingespielt wird? Braucht es dafür eine eigene Einwilligung, einen eigenen Hinweistext?
   - Entsteht durch die Kette faktisch ein **Kundenprofil über Monate**? Ist das unter DSGVO (Zweckbindung, Speicherdauer) und unter US-Recht (Profilbildung, Biometrie-Klagen) noch tragbar?
   - Was muss der Gründer **vor dem ersten echten Kunden** dafür gebaut oder formuliert haben — und was kann warten?

4. **Türöffner-Prüfung, der praktisch wichtigste Teil:** Welche Felder / Marker müssen **JETZT** erfasst werden, damit diese Kette später überhaupt baubar ist — und welche sind später nicht nachholbar? Der bereits benannte „Gespiegelt"-Marker ist einer. **Welche fehlen noch?** Denk konkret an: Kunden-Identität über Gespräche hinweg (bei anonymisierten Transkripten!), Zeitpunkte, Herkunft einer Information, Widerruf.

5. **Die Anonymisierungs-Falle:** Namen und Firmen werden beim Speichern ersetzt. Wie soll man dann über mehrere Gespräche hinweg **denselben Kunden** wiedererkennen und sein Wissen zusammenführen? Ist das ein Widerspruch — und wie löst man ihn, ohne die Anonymisierung aufzuweichen?

6. **Drei Wege nebeneinander**, wie die Kette gebaut werden könnte (von „billigste tragfähige Variante" bis „sauber"). Je Weg: Aufwand, was er nicht löst, wie er scheitert.

7. **Eine Empfehlung** — inklusive: **was davon gehört in die JETZT laufende Arbeit, und was darf warten?** Der Gründer baut als Nächstes die Bewertung nach dem Anruf um. Muss dort etwas mitgebaut werden, damit diese Kette später nicht blockiert ist?

Kurz und dicht. Der Gründer ist **kein Entwickler** — die Empfehlung am Ende muss er ohne Fachbegriffe verstehen können.
