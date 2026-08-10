# BRIEFING — Auswertungs-Bereich abreißen und neu bauen, oder nicht?

Du bist Gegenleser. **Nichts lesen, nichts schreiben, nichts ausführen** — alle Fakten stehen unten. Antworte auf Deutsch, direkt, ohne Höflichkeitsfloskeln. Wenn wir falsch liegen, sag es hart. Deine Aufgabe ist NICHT, dem Gründer zuzustimmen.

## Die Frage in einem Satz

Der Gründer sagt: *„Vielleicht sollten wir den Auswertungsbereich komplett löschen und neu aufsetzen. Wenn da an einem Aufruf so viel dranhängt, ist es nicht clever, da dran rumzumachen. Ich plädiere zu abreißen, Recherche wie es für den US-Markt aussehen sollte, dann neu bauen."*

## Kontext

NERVE ist ein Live-Assistent für Verkaufs-Telefonate (Ein-Mann-Projekt, vor dem Marktstart, keine zahlenden Kunden). Nach jedem Anruf gibt es eine **Auswertung**: Note, Kacheln, Verläufe, Einwand-Zeitleiste, Empfehlungen.

**Der Auslöser der Frage:** Beim Prüfen einer geplanten Kosten-Optimierung stellte sich heraus, dass ein einziger KI-Aufruf (der „Coaching-Aufruf", feuert nach jedem Satz) **vier** Dinge liefert, von denen wir bisher nur eines auf dem Schirm hatten:
- ein Coaching-Tipp — **wird seit Monaten bewusst gar nicht angezeigt**
- eine Kategorie — nur intern
- **Schmerzpunkte** — werden an zwei Stellen angezeigt, er ist ihr **einziger** Erzeuger
- eine Kaufbereitschafts-Änderung — speist die Note

Und die Kaufbereitschaft selbst hat **sieben** Verbraucher, darunter einen, bei dem **derselbe Feldname etwas völlig anderes bedeutet**: In Trainings-Sitzungen enthält die Spalte `kb_end` gar keine Kaufbereitschaft, sondern die **Trainings-Gesamtnote** (steht wörtlich als Kommentar im Code). Wer die Spalte naiv leert, killt still die Trainings-Bewertung.

Der Gründer schließt daraus: zu verworren zum Reparieren.

## Was es faktisch gibt (gemessen, nicht geschätzt)

| Datei | Zeilen | Rolle |
|---|---|---|
| `templates/session_detail.html` | 878 | die große Auswertungs-Seite nach dem Anruf |
| `templates/dashboard.html` | 1217 | Übersicht mit Kennzahlen-Kacheln + Verlaufs-Diagramm |
| `routes/dashboard.py` | 1117 | liefert die Daten dafür |
| `static/pip-launcher.js` | 4813 (davon 94 Fundstellen „postcall") | das schwebende Fenster; enthält auch den Abschluss-Bildschirm |
| `services/coaching_service.py` | 519 | Coaching-Bericht + Lernkarten nach dem Anruf |
| `services/judge_runner.py` | 453 | **der NEUE Bewerter (Beleg-vor-Note) — existiert bereits** |
| `services/rubric_engine.py` | 237 | **der neue Punkte-Rechner — existiert bereits** |
| `services/beleg_check.py` | 99 | **Schutz gegen erfundene Zitate — existiert bereits, aber nicht angeschlossen** |
| die alten Noten-Rechner in `routes/app_routes.py` | ~160 | `_calc_call_score`, `_calc_process_score`, `_apply_outcome_modifier` |

## ⚠ DER ENTSCHEIDENDE PUNKT — es sind schon ZWEI Abrisse geplant

Bevor du antwortest: Genau dieser Bereich ist bereits **zweimal** als Neubau eingeplant. Der Gründer weiß das in diesem Moment nicht mehr im Detail — deshalb ist die Kernfrage vielleicht gar nicht „abreißen ja/nein", sondern „planen wir gerade denselben Abriss zum dritten Mal?".

1. **Phase METRIK-1** (der nächste Schritt) ist bereits als **Ablöse-Phase, ausdrücklich keine Reparatur** definiert. Ihre Streich-Liste steht fest und ist lang: die komplette Kaufbereitschafts-Familie samt Schreibpfaden, alle drei alten Noten-Rechner, die Note-Spalten, die Skript-Abdeckung, den Redeanteil im Kaltakquise-Modus, mehrere tote Zähler. Der Nachfolger (Beleg-vor-Note-Bewerter) **existiert bereits im Code**; der Auftrag lautet „stilllegen + hochziehen", nicht „Formel feilen". Von ~30 heutigen Werten sollen ~9 überleben.

2. **Phase 4c (Engine-Neubau)** ist ein bereits beschlossener 🔴-Neubau der Live-Verarbeitung — **ausdrücklich erweitert auf die Auswertung nach dem Anruf**, weil die heute eine Warteschlange mit **einem** Bearbeiter für alle Firmen ist (bei zwei gleichzeitig endenden Anrufen verdoppelt sich die Wartezeit). Das betrifft die **Maschinerie** der Auswertung.

**Was in KEINER der beiden Phasen sauber zugeordnet ist: die ANZEIGE.** Also die 878 + 1217 Zeilen Vorlagen und der Abschluss-Bildschirm im schwebenden Fenster. Dafür gibt es einen Design-Brief von Ende Juni, der die Anzeige als „eigene Phase nach dem Fundament" vorsieht — aber diese Phase steht in keiner Reihenfolge.

## Der US-Markt-Punkt (spricht FÜR den Neubau)

Der Markt wurde von Deutschland auf **USA** umgestellt. Eine Recherche von gestern hat belegt, dass mehrere unserer Bewertungs-Annahmen **für den US-Markt falsch sind**: längere Redeblöcke sind bei Kaltakquise besser (nicht schlechter), die Fragenanzahl wirkt nachweislich nicht, der Redeanteil läuft gegenläufig zum Bedarfsgespräch, und der Small Talk, den deutsche Trainer verbieten, ist im US-Datensatz der zweitstärkste Hebel. Drei geplante Anzeige-Symbole wurden daraufhin gestrichen. **Zusätzlich:** Der Coaching-Text ist im deutschen Ton geschrieben (Lob vor Kritik) und liest sich für US-Verkäufer wie ein Verfahren gegen sie — der Schaden zeigt sich in Abwanderung, nicht in schlechteren Anrufen.

Es steht ohnehin ein Blocker „Coaching-Inhalte auf US-Markt umstellen" auf der Liste.

## Unsere eigene Regel dazu (an die du dich halten sollst)

> **Fix oder Neubau? — pro angefasstem Modul bewusst entscheiden, nicht schleichen.** Neubau-Signale: drei oder mehr Pflaster drin · gemischte Konventionen in einer Datei · über 500 Zeilen mit vermischten Zuständigkeiten · unklarer Daten-Fluss · „der Fix wäre das nächste Pflaster". Bei Neubau alten Code als **Funktions-Referenz** lesen (welche Randfälle löst er?), **nicht als Vorlage**. Gilt für **einzelne Module**, nie für die ganze App — der komplette Neuschrieb würde Jahre gelöster Randfälle wegwerfen. Vor dem Start und ohne echte Nutzer ist Modul-Neubau billig; später nicht.

Zweite Regel: **Einfachster tragfähiger Weg zuerst.** Über-Engineering ist eine Form von Abrieb.
Dritte Regel: **Jede Neuplanung erzeugt Abrieb** — verlorene Zeit, neue Fehler, verlorener Kontext.

## Deine Aufgabe

1. **Ist „abreißen" hier richtig — oder planen wir denselben Abriss zum dritten Mal?** Sag klar, was von der Forderung des Gründers bereits durch METRIK-1 und 4c abgedeckt ist und was wirklich ungedeckt bleibt.
2. **Wo genau verläuft die Grenze des „Auswertungsbereichs"?** Ein Abriss ohne saubere Grenze ist der Anfang eines Total-Neuschriebs, den unsere eigene Regel verbietet. Zieh die Linie.
3. **Drei konkurrierende Wege nebeneinander**, nicht einer verteidigt. Je Weg: Aufwand, was er NICHT löst, wie er scheitert. Denk auch an Wege außerhalb unseres Rahmens.
4. **Genau eine Empfehlung** mit Begründung — und ausdrücklich: was spricht dagegen?
5. **Reihenfolge:** Wenn neu gebaut wird — vor oder nach 4c? Der Gründer will „erst Recherche, wie es für den US-Markt aussehen soll, dann bauen". Ist das die richtige Reihenfolge, oder gehört die Maschinerie zuerst?
6. **Was geht beim Abriss verloren?** Benenne konkret, welche gelösten Randfälle in so einer gewachsenen Auswertung stecken und wie man sie rettet, ohne den alten Code als Vorlage zu nehmen.
7. **Die unbequeme Frage:** Der Gründer begründet den Abriss mit *„da hängt so viel an einem Aufruf"*. Ist Verflechtung überhaupt ein gültiges Neubau-Argument — oder verlagert ein Neubau die Verflechtung nur an eine neue Stelle, wo wir sie noch nicht sehen?

Fließtext mit Zwischenüberschriften. Kein Code nötig, es geht ums Konzept.
