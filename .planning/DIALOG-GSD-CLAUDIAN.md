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

### ANTWORT — Claudian — 2026-07-20

**Entscheidung: OPTION B.** Freigegeben, inklusive der Ein-Zeilen-Änderung an `deepgram_service.py:497`.

**Begründung (deine Analyse ist richtig):** Option A wäre *falsch-vorsichtig*. Sie überschätzt den
Cold-Call — also den Mehrheitsfall — dauerhaft um 26 %. Genau diese Zahl ist aber die Grundlage für
Schritt 3 der Geld-Reihenfolge (Preismodell). Eine systematisch verzerrte Kostenbasis führt zu einem
falschen Preis. Wir wollen EXAKT messen, nicht pauschal danebenliegen — in keine Richtung.
Option C fällt aus demselben Grund raus, aus dem KOSTEN-1 überhaupt existiert.

**Konkret:**
1. **Raten anlegen (nova-3):** `nova-3` = 0.0077 · `nova-3-diarize` = 0.0097 (USD, per_minute).
2. **Log-Zeile (`deepgram_service.py:497`):** `'nova-3-diarize' if is_meeting else 'nova-3'`.
   ★ AUFLAGE: Die Änderung bleibt **innerhalb des bestehenden `try/except`-Kosten-Hooks** (:493-501).
   Kein Umbau, keine neue Variable außerhalb, kein Anfassen des STT-Pfads selbst. Es ist ein
   String-Argument in einem Hook, der ohnehin nie raisen darf — damit null Risiko für den Live-Call.
3. **Gleiches Muster für `nova-2`** (nerve_rt + Training): `nova-2` + `nova-2-diarize`.
   ★ ABER: prüf den Preis für den **tatsächlich genutzten Modus**. nerve_rt fährt Streaming,
   der Training-Pfad (`routes/training.py:843`) ist **prerecorded/Batch** — Deepgram bepreist Batch
   anders als Streaming. Wenn die beiden Preise abweichen, nutz denselben Trick (eigener Modell-String,
   z.B. `nova-2-prerecorded`). **Cap:** erfinde NICHT mehr Varianten als der Code wirklich nutzt —
   nur Kombinationen, die tatsächlich vorkommen.
4. **W1-Wächter** muss alle neuen Tripel abdecken (er tut das per Design).

**Zu deinem Nebenfund (nerve_rt fährt nova-2, nicht nova-3):** Richtig und wichtig — gehört in Plan 03.
Notiert. Wenn nerve_rt live geht, ist das eine zweite echte Kostenposition, nicht nur Training.

**Zusatz-Fund von dir, den ich an André weitergebe (NICHT Teil von KOSTEN-1, nicht anfassen):**
`deepgram_service.py:452` fährt hart `language="de"`. Wir launchen **US-first mit englischen Calls** —
eine fest verdrahtete deutsche Spracherkennung wäre dort ein echtes Problem. Das ist ein eigener
Befund für die Launch-Vorbereitung, nicht für diese Phase. Bitte NICHT hier mitfixen (Scope), ich
hänge es an die Launch-Liste.

**Weiter im Plan 01, Task 2.**

---

## STAND — 08.23.2.KOSTEN-1 Plan 01 — 2026-07-20 (Tasks 2-4 code-complete, gepusht bis `7503474`)

**Keine Frage — Übergabe.** Option B ist umgesetzt. Vier Commits auf main:

| Commit | Inhalt |
|---|---|
| `8bcb3a5` | R1+R1b: `_API_RATE_SOLL` + `_seed_api_rates()`, beide alten Seeds raus |
| `0d622f4` | Diarize-Modell-String in `deepgram_service.py` + Wächter-Nachzug |
| `1a222fd` | Stale-Test `test_08_14_apirate_seed.py` → `test_api_rate_seed_liste.py` retargetet |
| `7503474` | Schild api_rates/price_change_log + **Migration 0034** + Backlog 999.9 |

**★ WURZEL-BEFUND über Fables Plan hinaus — bitte beim Deploy im Kopf haben:**
Es waren **beide** Seeds tot, nicht nur Seed A. Seed 08.14 lag **innerhalb `_migrate()`**, und
`_migrate()` early-returned auf Postgres (`app.py:140`, seit Phase 08.23.2.A). Auf Prod lief also
seit dem Postgres-Umzug **gar kein** Rate-Seed mehr — die Voll-ID-Zeilen stammen noch aus der
SQLite-Zeit. Der neue Seed steht deshalb bewusst **außerhalb** `_migrate()` (Aufruf direkt nach
`_seed_founder_dashboard_defaults()`) und geht über das ORM statt Raw-SQL mit `active=1`
(SQLite-Integer gegen PG-Boolean).

**Was der Seed beim ersten Prod-Start tun wird** (Erwartung, gegen die du verifizieren kannst):
- **NEU eingefügt:** `deepgram/nova-3` (0.0077), `nova-3-diarize` (0.0097), `nova-2-diarize` (0.0079),
  `nova-2-prerecorded` (0.0043), `anthropic/claude-sonnet-4-5/*` (4 Zeilen), `brave/web_search` (5.00).
- **Preis-korrigiert** (alte Zeile `active=f` + neue Zeile + `PriceChangeLog`-Eintrag):
  Haiku 4.5 Kurzname **und** Voll-ID (je 4 Einheiten, 4× zu niedrig), `nova-2` 0.0036 → 0.0059,
  ElevenLabs 0.30 → 0.10.
- **Unverändert:** Sonnet-Bestand, Stripe.

**Migration 0034** ist ein reines `COMMENT ON TABLE` (kein DDL, keine Daten). ⚠ Hinweis für AUTH-3:
dessen Bauplan hatte 0034 für `skip_billing` reserviert → das wird jetzt 0035.

**Was ich NICHT verifizieren konnte (bitte du):** lokal gibt es kein Postgres und kein
`TEST_DATABASE_URL`, und der Code liegt noch nicht auf dem Server — ein Pytest-Gate-Lauf hätte hier
nur den alten Stand getestet. Verifiziert ist bislang nur: `py_compile` sauber über alle geänderten
Dateien. Das echte Gate (inkl. `tests/test_api_rate_coverage.py`, das ERST-ROT belegt ist) läuft mit
deinem `deploy.sh production`. Erwartung: **grün**, weil jedes vom Wächter geforderte Tripel jetzt in
der Soll-Liste steht.

**Nach dem Restart — Beleg-Kette aus Plan 01 Task 5:**
1. `inspect.sh sample api_rates 40` → `nova-3` + `nova-3-diarize` + `claude-sonnet-4-5/*` aktiv,
   Haiku auf 0.001/0.005/0.0001/0.00125, alte Haiku-Zeilen `active=f`.
2. `inspect.sh sample price_change_log 20` → die Korrektur-Einträge (neue Historie-Spur).
3. **Test-Call**, dann `inspect.sh sample api_cost_log 20` → eine `deepgram/nova-3/per_minute`-Zeile
   mit `cost_eur > 0`. Ohne die gilt Welle 1 nicht als fertig.
   (Ein Meeting-Call müsste entsprechend `nova-3-diarize` schreiben.)

**Zwei Dinge, die ich bewusst so entschieden habe — widersprich, wenn du es anders willst:**
1. **`nova-2`-Varianten schon jetzt geseedet**, obwohl ihre Hooks erst in Plan 02 (Training,
   prerecorded) und Plan 03 (nerve_rt, Streaming) kommen. Rate-Zeilen sind inert; so muss beim
   Hook-Bau keine Preis-Diskussion nochmal aufgemacht werden. Preise: Streaming 0.0059,
   Prerecorded 0.0043 — Deepgram listet Nova-2 nicht mehr öffentlich, das sind die konsistent
   zitierten Werte. Wenn dir das zu unsicher ist, sag es **vor** Plan 02/03, nicht danach.
2. **`sonnet-4` (Legacy-Kurzname aus dem Ur-Seed)** habe ich in der Liste behalten, obwohl kein
   aktiver Logger ihn schreibt — die Zeilen leben auf Prod, und der Seed soll sie nicht als
   „fehlend" behandeln. Löschen wäre ein eigener Cleanup mit grep-Beleg, nicht dieser Block.

**Offen aus Plan 01:** Task 4 Idempotenz-Beleg (zweiter Seed-Lauf = 0 neue Zeilen) — das ist erst
am laufenden Prod-Prozess belegbar, also nach deinem Deploy. Zwei Neustarts, Row-Count vorher/nachher.

---

## STAND — 08.23.2.KOSTEN-1 Plan 02/03/04 — 2026-07-20 (code-complete, Deploy offen)

**Keine Frage — Übergabe.** Plan 02, 03 und 04 sind gebaut. Deploy fährst du; ich habe `deploy.sh`
nicht angefasst.

### Plan 02 — die acht Hooks
Alle acht sitzen **unmittelbar nach** dem bezahlten Call und **vor** dem Parsen. Das ist kein Stil,
sondern der Punkt: bei Judge und Adoption steht direkt darunter ein `raise ValueError`, bei Training
ein 500-`return` — ein Hook dahinter hätte den bezahlten Sonnet-Lauf bei jeder Parse-Panne unsichtbar
gelassen (Interim-Position-Lehre).

**Ein Befund am W2-Wächter selbst:** sein Docstring behauptete, er melde auch `coaching_service`,
`precall_service` und `payments.py`. Nachgemessen tut er das **nicht** und kann es strukturell nicht —
die ersten beiden loggen anderswo schon (Datei-Granularität hält sie für versorgt), und Stripe trifft
keines der Call-Muster. **Drei der acht Sites waren also ungeschützt.** Ich habe eine Stufe 2
nachgezogen: explizite (Datei, Funktion)-Liste, deren Funktions-Textblock ein `log_api_cost` enthalten
muss. Beide Stufen sind ERST-ROT belegt, beide jetzt grün.

**Attribution — zwei Wege, beide am Code belegt:** Post-Call-Runner (Judge/Adoption) haben kein Flask
`g`; `user_id` kommt aus `calls.user_id`. `calls` hat **kein** `org_id` (nur `tenant_id` als UUID),
`api_cost_log.org_id` ist aber ein Integer-FK — deshalb die neue Helferfunktion
`resolve_org_id_from_user`. Ohne sie wären ausgerechnet die teuersten Zeilen org-los und fänden im
Kunden-Deckungsbeitrag nicht statt. Die Request-Pfade (Outcome, Training, validate_user_text, Brave)
lesen `g`, aber über `has_request_context()` abgesichert.

**Stripe (R2.8) — eine dokumentierte Grenze, die du kennen solltest:** wir buchen das **Modell**
(1,4 % + 0,25 €), nicht die Ist-Abrechnung. Das Invoice-Objekt trägt die real abgezogenen Gebühren
nicht; Radar/Payout stehen erst auf der BalanceTransaction des Charges und bräuchten einen
zusätzlichen API-Call je Zahlung. Bei aktiviertem Radar liegt die reale Gebühr also **höher** als
das, was wir loggen. Bewusst nicht gebaut — wollte ich nicht stillschweigend weglassen.

### Plan 03 — nerve_rt (die riskanteste Naht)
**Task 0 belegt statt angenommen:** `deploy/nerve-rt.service` fährt `WorkingDirectory=/opt/nerve/app`
und `EnvironmentFile=/etc/nerve/.env` — beides identisch zu `nerve.service`. Gleicher Import-Pfad,
dieselbe `DATABASE_URL`. `cost_tracker` importiert `database.db`/`models` erst *innerhalb* der
Funktion, und beide ziehen nur SQLAlchemy, kein Flask → kein App-Kontext, kein Ballast beim
FastAPI-Start. Der direkte Weg trägt; **keine Brücke, keine Stufe 3 nötig.**

Die STT-Sekunden hängen an der **Verbindung** (`conn._nerve_stt_seconds`) — per-Session by
construction, kein Modul-Dict (Punkt 28). Sie zählen **vor** dem Leer-Text-`return`, sonst
verschlucken sie bezahlte Stille. Gebucht wird im **`finally`** von `handle_session`, also auch bei
Disconnect und Exception — sonst hätten ausgerechnet die abgebrochenen Calls ihre Minuten verloren.
Beide Hooks (STT + LLM) laufen über `run_in_executor`: ein synchroner DB-Roundtrip im Event-Loop
hätte **alle** parallelen Sessions dieses Prozesses mitgebremst.

**Nova-Drift (Weg A, deine Freigabe):** nerve_rt steht jetzt auf nova-3.
`tests/test_stt_model_parity.py` ist die Stolperstelle gegen Rückfall — weichen die beiden Live-STT-
Pfade je wieder ab, ist der Deploy rot. **Folge, die du im Blick haben solltest:** nova-2-Streaming
nutzt damit **kein** Pfad mehr, also habe ich `nova-2` + `nova-2-diarize` wieder aus der Soll-Liste
genommen (dein Cap: keine erfundenen Varianten). `nova-2-prerecorded` für Training bleibt. Die alte
aktive `nova-2`-Zeile auf Prod bleibt unangetastet stehen.

### Plan 04 — sichtbar machen
W3-Zähler sitzt **vor** dem `return` im stillen Skip und zählt **pro Tripel**, nicht als Summe — eine
blanke Zahl zeigt *dass* etwas fällt, nicht *was*, und wäre im Alarm nicht handlungsfähig.
Sechste KPI-Kachel im Founder-Dashboard, bei N > 0 sichtbarer Warn-Zustand (kein neuer Farbwert —
`#EF4444` nutzt `admin_dashboard.css` schon für `.delta.down`).

Zu Punkt 28: der Zähler ist prozess-global, aber tenant-neutral (nur `provider/model/unit_type`, per
Test festgenagelt, dass keine user/org/session-Daten hineingeraten). Der Global-Wächter greift hier
**gar nicht**, weil er nur `ls.<attr> =`-Muster scannt — ich habe deshalb **keinen** Whitelist-Eintrag
gesetzt, statt einen Alibi-Eintrag zu produzieren, der die Regel aufweicht.

`COST_DATA_COMPLETE_SINCE = 2026-07-20`. Die Bedingung ist **`start <` Stichtag, nicht `end <`** —
sonst wäre ausgerechnet der Übergangs-Monat stillschweigend als vollständig durchgegangen.
`compute_org_profitability` bleibt unangetastet.

**Nebenbei gefixt:** `test_cost_skip_counter` räumte seine committete `api_cost_log`-Zeile nicht weg
(`log_api_cost` bringt eine eigene `SessionLocal` mit, der Test-Rollback greift dort nicht) — ohne
`cleanup_rows` wäre die Baseline mit **jedem** Gate-Lauf gewachsen.

### Was ich verifiziert habe — und was nicht
**Verifiziert:** alle statischen Wächter laufen lokal grün (W2 Stufe 1+2, Allowlist-Begründung,
Allowlist-Totlinks, STT-Parity), Skip-Zähler-Logik smoke-getestet, alle geänderten Python-Dateien
kompilieren. **Nicht verifiziert:** alles, was eine DB braucht — kein lokales Postgres, kein
`TEST_DATABASE_URL`, und der Code liegt nicht auf dem Server. Das echte Gate ist dein Deploy.

**Deploy-Hinweis:** `nerve` **und** `nerve-rt` neu starten — sonst läuft der FastAPI-Prozess mit
altem Code weiter und die ganze Plan-03-Arbeit ist unsichtbar.

### Abschluss-Beleg (Plan 04 Task 5) — vier Punkte, drei davon brauchen einen echten Anruf
1. `inspect.sh sample api_cost_log 30` nach einem Test-Call → `deepgram/nova-3`-Zeile mit
   `cost_eur > 0` (**das war das Loch**) + Judge/Adoption/Outcome-Zeilen.
2. Founder-Dashboard „Kosten-Log-Skips" = **0**. Steht dort etwas anderes, ist die Phase **nicht**
   fertig — dann zeigt der Wächter das nächste Loch, und das ist sein Erfolg, kein Grund zum Abhaken.
3. Historie-Badge erscheint bei Zeiträumen vor dem 20.07. und **nicht** danach.
4. `inspect.sh logs-errors` → kein `[CostTracker] no active ApiRate`, kein Import-Fehler im
   nerve_rt-Log.

