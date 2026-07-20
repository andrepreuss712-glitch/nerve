# DIALOG GSD ↔ Claudian

Fragen von GSD (Claude Code, Terminal) an Claudian/André. Format: `## FRAGE — <Phase> — <Datum/Uhrzeit>`,
Antwort direkt darunter als `### ANTWORT — <Datum/Uhrzeit>`. André arbeitet vom Handy und kann das
Terminal nicht kopieren; Claudian sieht das Terminal nicht — deshalb läuft alles über diese Datei.

---

## FRAGE — 08.23.2.KOSTEN-1 — 2026-07-20

**Wo stehe ich:** Plan 01, Task 0 (Entscheidungs-Checkpoint) abgeschlossen bis auf einen Punkt.
Task 1 (W1-Wächter) ist gebaut + ERST-ROT belegt (`4e55b06`). Nächster Schritt wäre Task 2
(Raten-Liste in `app.py` schreiben) — dafür brauche ich eine Zahl.

**Was Task 0 ergeben hat (erledigt, keine Frage):**
- **Multilingual? NEIN.** `services/deepgram_service.py:452` fährt hart `language="de"`; im ganzen
  Repo kein `"multi"`-Sprachcode. → **Monolingual-Rate $0.0077/min gilt.** Bestätigt gegen
  deepgram.com/pricing + Sekundärquellen (2026: Nova-3 Streaming PAYG $0.0077/min).
- **Nebenfund (betrifft Plan 03, nicht diese Frage):** `nerve_rt/services/stt/deepgram_adapter.py:99`
  fährt **`nova-2`**, nicht `nova-3`. Die Haupt-App fährt nova-3. Wenn nerve_rt live geht, wird
  deshalb die `nova-2`-Rate zur zweiten echten Kostenposition — nicht nur der Training-Prerecorded-Pfad.

**Frage: Deepgram-Diarization ist NICHT im Minutenpreis enthalten — wie preisen wir sie ein?**

Belegt: Diarization ist ein Add-on von **+$0.0020/min** auf den Basis-Streaming-Preis
(deepgram.com/pricing sowie mehrere unabhängige Preis-Übersichten 2026).
Unser Code schaltet sie **konditional**: `diarize=is_meeting` (`deepgram_service.py:457`,
identisch in `nerve_rt` :106). Also:
- Cold-Call → 0.0077 $/min
- Meeting → 0.0077 + 0.0020 = **0.0097 $/min** (+26 %)

`api_rates` kennt aber nur **einen** Preis pro `(provider, model, unit_type)`. Optionen:

- **A — Eine Rate, worst case:** `deepgram/nova-3/per_minute = 0.0097`. Kein Code-Eingriff.
  Überschätzt Cold-Calls (die Mehrheit) dauerhaft um 26 %. Marge sieht schlechter aus als sie ist —
  fürs Preismodell die falsche Richtung von „vorsichtig".
- **B — Zwei Modell-Strings (meine Empfehlung):** `nova-3` = 0.0077 und `nova-3-diarize` = 0.0097.
  `deepgram_service.py:497` loggt statt fix `'nova-3'` dann `'nova-3-diarize' if is_meeting else 'nova-3'`
  — **eine Zeile**, kein neues System, `is_meeting` liegt an der Stelle bereits vor. Der W1-Wächter
  deckt beide Tripel ab. Ergebnis: exakte Kosten pro Call-Typ, was für das Preismodell (Schritt 3
  der Geld-Reihenfolge) genau die Zahl ist, die wir brauchen.
- **C — Nur 0.0077, Diarization ignorieren:** unterschätzt Meetings. Fällt raus (KOSTEN-1 existiert,
  weil wir zu wenig messen).

Dieselbe Entscheidung gilt sinngemäß für **`nova-2`** (nerve_rt + Training), das denselben
`diarize=is_meeting`-Schalter hat.

**Blockiert:** Task 2 (Raten-Liste) und damit der ganze Rest von Plan 01. Ohne die Zahl schreibe ich
keine Preis-Zeile. Bei Option B kommt zusätzlich die Ein-Zeilen-Änderung an `deepgram_service.py:497`
dazu — die möchte ich freigegeben haben, weil sie den Live-Pfad berührt (auch wenn es nur ein
String-Argument im bereits bestehenden Kosten-Hook ist).

### ANTWORT — <offen>
