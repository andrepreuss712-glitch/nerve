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


---

## ★ ANDRÉ-VORGABE — 2026-07-20 (für die Stripe-Arbeit in AUTH-3, NICHT jetzt)

**„Die Stripe-Kosten sollten wir auch so genau wie möglich tracken."**

Ist-Stand nach KOSTEN-1 R2.8: wir buchen das **Modell** (1,4 % + 0,25 €), nicht die real abgezogene
Gebühr. Bei aktivem Radar/abweichenden Kartentypen liegt die echte Gebühr **höher** → wir unter-
berichten dort leicht. Das ist dieselbe Klasse, die KOSTEN-1 gerade behoben hat, deshalb Vorgabe:

**Wenn Stripe in AUTH-3 live geht, wird die ECHTE Gebühr geloggt, nicht das Modell.** Weg: pro Zahlung
die `BalanceTransaction` des Charges holen (`fee`/`fee_details` = tatsächlich abgezogen, inkl. Radar
und Payout-Anteilen) und diesen Betrag buchen statt der Formel. Kostet einen zusätzlichen API-Call je
Zahlung — bei EA-Volumen vernachlässigbar, und es ist die einzige Zahl, die stimmt.

Bis dahin bleibt die Modell-Rechnung als Näherung stehen (bewusst, dokumentiert, nicht still).

---

## ★ TEMPO-1 — Pflicht-Pre-Checks vor der Planung (Punkt 20), 2026-07-21

Der ROADMAP-Eintrag TEMPO-1 verlangt zwei Verifikationen VOR der Planung. Beide sind gefahren,
beide Ergebnisse hier belegt — damit später nachvollziehbar ist, worauf die Plaene aufsetzen.

### 1. Haengt der cache_read-Logging-Hook auch am EWB/QA-Pfad? → JA, an allen dreien.

Der Roadmap-Eintrag nennt `claude_service.py:556ff` als Muster und fragt, ob der Hook auch am
Antwort-Pfad haengt. Er haengt — und zwar an jedem der drei Konsumenten von `answer_system_content()`:

| Antwort-Pfad | Aufruf `answer_system_content` | Cache-Hook | `context_tag` / `call_site` |
|---|---|---|---|
| Auto/EWB (`streame_auto_variante`) | `claude_service.py:620` | `:700-709` | `ewb` / `ewb` |
| Manuell (Knopf) | `claude_service.py:778` | `:853-862` | `ewb` / `ewb` |
| QA | `qa_pipeline.py:418` | `qa_pipeline.py:488-497` | `qa` / `qa` |

**Konsequenz: es ist NICHTS neu anzulegen.** Der Beleg nach dem Deploy ist fuehrbar, sobald der
Marker sitzt. Die Hooks lesen `cache_read_input_tokens` / `cache_creation_input_tokens` und
schreiben nur bei `> 0` — ein fehlender Marker sieht also aus wie „keine Zeile", nicht wie ein Fehler.

**Korrektur am Beleg-Query im Roadmap-Text:** dort steht `pip_stream`. Ein `context_tag='pip_stream'`
existiert im Code **nicht** — die Enumeration aller `context_tag=`/`call_site=`-Literale in
`services/`, `routes/`, `nerve_rt/` kennt ihn nicht. `pip_stream` ist ein Mess-Label, kein DB-Wert.
Der Beleg lautet daher:

    unit_type='per_1k_cache_read_tokens' AND units > 0 AND context_tag IN ('ewb','qa')

Wer nach `pip_stream` sucht, findet garantiert nichts und haelt eine funktionierende Aktivierung
faelschlich fuer gescheitert.

### 2. Ist die per-SID-Anrede weiterhin AUSSERHALB des STABIL-Blocks? → JA, Anti-Cache-Poison haelt.

`prompt_pipeline.py:474-481` filtert im `return_blocks=True`-Pfad die Sek.-7-Zeile
(`Anrede: … WICHTIG: Nutze konsequent …`) aktiv aus dem Stabil-Block heraus; die Anrede steht
ausschliesslich volatil in Sektion 9 (`:452`, liest `session_anrede` per-SID). Der Alt-String-Pfad
(`return_blocks=False`) behaelt sie — der ist fuer den Cache irrelevant.

Zusatz-Scan der Sektionen 1–7 (`:145-433`) auf weitere per-Anruf-Inhalte: **ein** Zugriff auf
`_session_state[sid]['_profile_cache']` — das ist der pro-User-Profil-Cache, ueber einen Anruf hinweg
stabil. Kein Zeitstempel, kein Transkript, keine Session-ID im Stabil-Teil.

**Der Prefix ist stabil → der Cache kann greifen.**

### 3. Fund waehrend der Pre-Checks (geht in die Planung ein)

`answer_system_content()` (`prompt_pipeline.py:686`) baut die Content-Bloecke so:

    content = [{'type': 'text', 'text': b['text']} for b in blocks if b.get('text')]

Dabei faellt der `_layer`-Marker (`'stable'` / `'volatile'`) weg, den `build_answer_context` (`:618-621`)
gerade erst gesetzt hat. Der Marker muss **an dieser Stelle** ausgewertet werden, bevor er verloren
geht — nicht weiter unten in `claude_service`/`qa_pipeline`, wo nur noch eine Liste ohne Layer-Info
ankommt. Genau ein `cache_control` auf den `stable`-Block, keins auf `volatile`.

**Bekannte, akzeptierte Cache-Segmentierung (kein Bug, aber zu wissen):** der Stabil-Block enthaelt
`Rolle: {role_goal}` (`:596-598`). Kippt `contact_category` mitten im Anruf von `gatekeeper` auf
`target`, aendert sich der Prefix → ein Cache-Miss und ein neuer Write. Inhaltlich korrekt, kostet
nur den einen Aufschlag. Nicht „reparieren".

### Randbedingungen fuer diese Phase (André, 2026-07-21)

Scope eng: **nur** `cache_control` auf den bestehenden `_layer:"stable"`-Block + `CACHE_ANALYSE`-
Aufraeumen. **Nichts** aus dem TAXO3-Alt-Plan-04 dazunehmen. `autonomous: false`, kein Auto-Advance,
**Cross-AI vor Execute ist Pflicht.**

---

## FRAGE — 08.23.2.TEMPO-1 Welle 0 (Plan 00, Task 1) — 2026-07-21

**Wo stehe ich:** Task 1 ist gebaut und committet (`2a1b574`). `tests/test_cache_prefix_stabilitaet.py`
mit vier Runtime-Waechtern angelegt, **kein Produktivcode angefasst**
(`git diff --name-only HEAD -- services/ config.py` → 0 Zeilen). Task 2 (die drei Zeilen) habe ich
bewusst **nicht** angefangen.

Die vier Tests:
1. `test_ohne_opener_mit_faqs_prefix_byte_gleich_und_kein_db_im_hotpath` (real-PG)
2. `test_opener_zeile_mit_null_inhalt_liefert_leerstring_sentinel` (real-PG, inkl. dem
   nachgezogenen 0-DB-Verhaltens-Check aus `272fc0d` — Zaehler-Reset, zweimal
   `build_answer_context`, `_opened['n'] == 0`, plus Byte-Gleichheit des Stabil-Blocks;
   Aufbau identisch zu Test 1 **inkl. `set_profile_for_sid`**, damit kein falsches Rot aus dem
   `pdata`-Fallback kommt)
3. `test_faq_liste_im_session_cache_waechst_nicht` (In-Memory)
4. `test_faq_reihenfolge_ueber_zwei_aufrufe_stabil` (In-Memory)

**Lokales Vorab-Signal — `pytest tests/test_cache_prefix_stabilitaet.py -q` (verbatim):**

```
ssFF                                                                     [100%]
================================== FAILURES ===================================
________________ test_faq_liste_im_session_cache_waechst_nicht ________________
>       assert len(_cache_dict['faqs']) == 1, (
            f"Session-Cache mutiert: {len(_cache_dict['faqs'])} statt 1 FAQ -> _faqs ist eine Referenz "
            'auf den Cache, der Fallback appendet hinein (prompt_pipeline.py:186/:218).')
E       AssertionError: Session-Cache mutiert: 5 statt 1 FAQ -> _faqs ist eine Referenz auf den Cache, der Fallback appendet hinein (prompt_pipeline.py:186/:218).
E       assert 5 == 1
E        +  where 5 = len([{'a': '1', 'q': 'A'}, {'a': 'A1', 'q': 'F1'}, {'a': 'A2', 'q': 'F2'}, {'a': 'A2', 'q': 'F2'}, {'a': 'A1', 'q': 'F1'}])

tests\test_cache_prefix_stabilitaet.py:301: AssertionError
_______________ test_faq_reihenfolge_ueber_zwei_aufrufe_stabil ________________
>       assert stabil_1 == stabil_2, (
            'FAQ-Reihenfolge wechselt zwischen zwei Aufrufen -> die FAQ-Fallback-Query braucht ein '
            'order_by VOR dem limit (prompt_pipeline.py:211-213); ohne ORDER BY garantiert Postgres '
            'keine Reihenfolge und der Cache-Prefix aendert sich STILL.')
E       AssertionError: FAQ-Reihenfolge wechselt zwischen zwei Aufrufen -> die FAQ-Fallback-Query braucht ein order_by VOR dem limit (prompt_pipeline.py:211-213); ohne ORDER BY garantiert Postgres keine Reihenfolge und der Cache-Prefix aendert sich STILL.
E       assert 'Ziel ist ver...nF: F2\nA: A2' == 'Ziel ist ver...nF: F1\nA: A1'
E
E         Skipping 2192 identical leading characters in diff, use -v to show
E           # FAQ
E         + F: F1
E         + A: A1
E           F: F2
E         - A: A2...

tests\test_cache_prefix_stabilitaet.py:336: AssertionError
=========================== short test summary info ===========================
SKIPPED [1] tests\test_cache_prefix_stabilitaet.py:136: TEST_DATABASE_URL not set -- generic fixtures require real-PG nerve_test (no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.
SKIPPED [1] tests\test_cache_prefix_stabilitaet.py:212: TEST_DATABASE_URL not set -- generic fixtures require real-PG nerve_test (no SQLite fallback by design, Req-2/D-07). Run server-side via deploy.sh-Gate.
2 failed, 2 skipped in 0.07s
```

**Einordnung — welcher Defekt macht welche Assertion rot:**

| Test | Rote Assertion | Ist / Soll | Defekt |
|---|---|---|---|
| `test_faq_liste_im_session_cache_waechst_nicht` | `len(_cache_dict['faqs']) == 1` | **5** statt **1** | Defekt 2 — `prompt_pipeline.py:186` holt `_faqs` als **Referenz** auf den Session-Cache, `:218` appendet hinein. Zwei Antwort-Calls → 1 + 2 + 2 = 5 Eintraege. Genau der Prompt-Bloat pro Call. |
| `test_faq_reihenfolge_ueber_zwei_aufrufe_stabil` | `stabil_1 == stabil_2` | Stabil-Block Call 1 endet auf `F: F1 / A: A1 / F: F2 / A: A2`, Call 2 auf `F: F2 / A: A2 / F: F1 / A: A1` | Defekt 3 — die FAQ-Fallback-Query `prompt_pipeline.py:211-213` hat **kein `order_by`** vor dem `limit`. Der Prefix wechselt **still** die Bytes; ohne Fix laeuft `cache_control` aus Welle 2 in Cache-**Writes** statt Cache-Reads. |

Beide sind **aus dem richtigen Grund** rot: es ist in beiden Faellen die im Plan vorgesehene
Verhaltens-Assertion, kein Import-, Fixture- oder Sammel-Fehler (der Lauf sammelt sauber, 4 Tests,
0 errors).

⚠ **Tests 1 und 2 laufen lokal NICHT** — die `db_session`-Fixture skippt ohne `TEST_DATABASE_URL`
(`conftest.py`, kein SQLite-Fallback by design). Damit sind genau die beiden Waechter, die den
**Sentinel-Defekt (Defekt 1: `live_session.py:821` schreibt `None` statt `''`)** und die
**0-DB-Zusage im Hot-Path** (`prompt_pipeline.py:126`) belegen, **ausschliesslich am echten Tor
belegbar**. Lokal ist dazu keine Aussage moeglich — weder gruen noch rot.

**Meldung: bereit fuer den Erst-Rot-Lauf am echten Tor.**

`bash deploy.sh production` fahre ich auftragsgemaess **nicht** — das ist Claudians Lauf. Erwartung
dort: das Pytest-Gate auf dem Server wird rot mit
`FAILED tests/test_cache_prefix_stabilitaet.py::test_ohne_opener_mit_faqs_prefix_byte_gleich_und_kein_db_im_hotpath`
(Sentinel-Assertion: `_cache['opener_content']` ist `None` statt `''`) und
`FAILED ...::test_opener_zeile_mit_null_inhalt_liefert_leerstring_sentinel` (gleiche Ursache, zweiter
Pfad zum `None`), plus den beiden oben schon lokal roten. Der Deploy bricht dabei bestimmungsgemaess
**vor dem Restart** ab — der Task hat **keinen** Produktivcode geaendert, es geht also ohnehin nichts
live.

**Ich halte hier an.** Task 2 (die drei Zeilen) starte ich erst, wenn das Rot vom echten Tor
verbatim zurueckgemeldet ist. Wenn das Gate dort **gruen** ist, ist das ein Befund (der Waechter
trifft den Defekt nicht) und kein Anlass, die Tests nachzubiegen.

### ANTWORT — Claudian — 2026-07-21

**ERST-ROT AM ECHTEN TOR BELEGT. Alle vier Waechter rot, jeder aus seinem vorgesehenen Grund.
Weiter mit Task 2.**

Zwischenfall vorweg (loest deinen ersten roten Lauf, falls du ihn siehst): der erste
`deploy.sh production` brach in der COLLECTION ab — `RuntimeError: SECRET_KEY is insecure`
(app.py:44), `1 error during collection`, KEIN Test lief. Ursache war NICHT dein Waechter,
sondern mein Security-Fix von heute Mittag: die verwaiste `/opt/nerve/app/.env` war die einzige
SECRET_KEY-Quelle fuer den als nerve_app laufenden Testlauf (er kann /etc/nerve/.env nicht lesen).
Fable-Bestandspruefung: SECRET_KEY ist der EINZIGE Modul-Level-Hard-Fail, kein weiterer Env-Wert
fehlt. Fix committet als `2c457e8` (Wegwerf-SECRET_KEY pro Lauf im Gate). Danach lief das Tor sauber.

**Verbatim vom zweiten, gueltigen Lauf (real-PG auf dem Server, `4 failed, 963 passed, 6 skipped,
5 deselected in 56.31s`, `[deploy] FEHLER: pytest ROT — kein Restart, kein Deploy` → Prod unberuehrt):**

```
FAILED tests/test_cache_prefix_stabilitaet.py::test_ohne_opener_mit_faqs_prefix_byte_gleich_und_kein_db_im_hotpath
  assert _cache['opener_content'] == ''
  AssertionError: Sentinel-Bruch: _load_profile_cache schreibt bei fehlendem Opener nicht '' sondern None
  assert None == ''

FAILED tests/test_cache_prefix_stabilitaet.py::test_opener_zeile_mit_null_inhalt_liefert_leerstring_sentinel
  assert _cache['opener_content'] == ''
  AssertionError: NULL-inhalt-Pfad: Opener-Zeile vorhanden, inhalt NULL -> muss '' ergeben, ist aber None
  assert None == ''

FAILED tests/test_cache_prefix_stabilitaet.py::test_faq_liste_im_session_cache_waechst_nicht
  assert len(_cache_dict['faqs']) == 1
  AssertionError: Session-Cache mutiert: 5 statt 1 FAQ -> Referenz statt Kopie (:186/:218)
  assert 5 == 1

FAILED tests/test_cache_prefix_stabilitaet.py::test_faq_reihenfolge_ueber_zwei_aufrufe_stabil
  assert stabil_1 == stabil_2
  AssertionError: FAQ-Reihenfolge wechselt zwischen zwei Aufrufen -> order_by VOR limit fehlt (:211-213)
```

Test 1 + 2 treffen Defekt 1 (Sentinel None statt '') — der lokal ueberhaupt nicht belegbar war.
Test 2 zeigt zusaetzlich, dass der Zusatz greift (der Lauf kommt gar nicht bis zur 0-DB-Assertion,
weil schon der Sentinel-Wert rot ist — nach dem Fix wird beides gruen). Test 3 = Defekt 2, Test 4 =
Defekt 3. Kein Collection-/Fixture-Fehler, sauberes Sammeln, 963 Bestands-Tests gruen.

**Freigabe: Task 2 (die drei Zeilen aus Plan 00) bauen.** Danach Task 3 (Waechter gruen belegen +
Stale-Test-Sichtung), committen, pushen — und wieder anhalten. Den Danach-Gruen-Lauf am echten Tor
fahre ich, wie den Erst-Rot-Lauf. NICHT auf Plan 01/02/03 auto-advancen.

### FRAGE — 08.23.2.TEMPO-1 Welle 0 (Plan 00, Task 2+3) — 2026-07-21

**Task 2 + Task 3 gebaut, committet, gepusht (`e1ed70f`, `5f63c58`). Bereit fuer den Gruen-Lauf am echten Tor.**

Die drei Zeilen (Commit `e1ed70f`):
- `live_session.py:825` Sentinel `''` statt `None` — **beide Pfade**:
  `'opener_content': (getattr(_opener, 'inhalt', '') or '') if _opener else '',`
- `prompt_pipeline.py:186` Kopie statt Referenz: `_faqs = list(_profile_cache.get('faqs', []))`
- `prompt_pipeline.py:213` `.order_by(_FAQ_op.id).limit(20).all()` (order_by VOR limit)
- Kommentar-Wahrheit `prompt_pipeline.py:185`: `# None = Cache nicht geladen; '' = geladen, kein Opener`

Zeilen-Neutralitaet gehalten: `wc -l services/prompt_pipeline.py` == **686** (Plan-02-Anker bleiben gueltig).
Randfunde NICHT angefasst (kein order_by in `live_session.py:795-802`, kein Profil-Stempel).

**Lokales Vorab-Signal (KEINE Abnahme):**
```
test_faq_liste_im_session_cache_waechst_nicht PASSED
test_faq_reihenfolge_ueber_zwei_aufrufe_stabil PASSED
test_ohne_opener_mit_faqs_..._kein_db_im_hotpath SKIPPED (real-PG)
test_opener_zeile_mit_null_inhalt_liefert_leerstring_sentinel SKIPPED (real-PG)
2 passed, 2 skipped
```
Tests 3+4 rot→gruen ggue. Task-1-Erst-Rot. Tests 1+2 (Sentinel + 0-DB) skippen lokal → das
rot→gruen-**Paar** fuer Defekt 1 ist nur am Tor belegbar.

**Stale-Test-Sichtung (Punkt 18): kein Retarget noetig.**
`test_per_sid_migration.py:82-88` (nur Key-Existenz), `test_prompt_pipeline.py:450` (eigene
None-Fixture, legitim „nicht geladen"), `test_build_answer_context.py:138` (`opener_content=''`
jetzt prod-treu) — alle gruen, keiner prueft den geaenderten Vertrag und bleibt faelschlich gruen.
29 passed / 5 skipped / 0 failed.

**Bitte den Gruen-Lauf am echten Tor fahren** (`bash deploy.sh production`): erwartet ist, dass die
vier Waechter jetzt GRUEN sind (das rot→gruen-Paar ggue. dem Erst-Rot-Lauf `4 failed, 963 passed`).
Sobald das Gate gruen ist und der Restart durchlaeuft, ist Welle 0 live. Danach entscheidet Andre
ueber Welle 1 (Plan 01) — **kein Auto-Advance** von meiner Seite.

### ANTWORT — Claudian — 2026-07-22

**WELLE 0 IST LIVE. Tor grün, Neustart durch, beide Dienste laufen.**

`deploy.sh production` grün: `967 passed, 6 skipped, 5 deselected in 53.57s` (Gegenstück zum
Erst-Rot `4 failed, 963 passed` — dieselben vier cache_prefix-Tests jetzt grün), POST-SUITE
Baseline-Check OK, Restart durch (`active (running) since 2026-07-22 06:08:51 UTC`), Waisen-Prune
Dry-Run 1 Kandidat (nichts bewegt). Verifiziert: `nerve` + `nerve-rt` beide `active`,
`app.getnerve.app/api/health` = 200. Service-Diff seit 2606c3b = nur die zwei geplanten Dateien,
die drei Randfunde unberührt, prompt_pipeline.py weiter 686 Zeilen.

Das rot→grün-Paar für den Sentinel (Defekt 1) liegt damit vor — Erst-Rot `2606c3b`, Grün jetzt.

**Über Welle 1 entscheidet André.** Kein Auto-Advance. Halt bestätigt.

### FRAGE — 08.23.2.TEMPO-1 Welle 1 (Plan 01) — 2026-07-22

**Plan 01 komplett gebaut, committet, gepusht (`9a9e509`, `c463629`, `a44ad23`). Bereit fuer den Tor-Lauf.**

Toter Cache-Apparat entfernt, EIN ehrlicher Schalter rein:
- **Task 1** (`9a9e509`): `CACHE_ANALYSE`-Zweig + `print("[Cache-Check]…")` in `claude_service.py:526-535`
  raus → `_system = SYSTEM_PROMPT_BASE` (Analyse bleibt bewusst UNCACHED, Erklaer-Kommentar steht).
  `_CACHE_MIN_CHARS` an BEIDEN Stellen weg (`claude_service.py:10-11` + Waise `qa_pipeline.py:48-49`).
- **Task 2** (`c463629`): `config.py` — `CACHE_ANALYSE`/`CACHE_EWB`/`CACHE_QA` raus,
  `CACHE_ANTWORT = os.getenv("CACHE_ANTWORT","true").lower()=="true"` als EINZIGER Schalter (default true).
  Projekt-Doku (ARCHITECTURE/INTEGRATIONS/STACK) nachgezogen.
- **Task 3** (`a44ad23`): Test-Contract in `test_08_13_01_config_constants.py` **ersetzt** (Punkt 18,
  nicht geloescht): CACHE_ANTWORT default/typ/env-override + `test_abgeloeste_schalter_sind_weg`
  (Runtime-`hasattr`, kein Source-Presence).

Scope gehalten (selbst gegengeprueft): `prompt_pipeline.py` **0 Zeilen** Diff (Plan-02-Territorium
unberuehrt, kein `cache_control`, `answer_system_content` unangetastet), MODEL-Block unberuehrt,
Randfunde nicht angefasst. Produktivcode-grep auf die drei toten Namen + `_CACHE_MIN_CHARS`: **0 Treffer**.
`CACHE_ANTWORT`-Def genau 1x. `ast.parse` gruen fuer alle vier `.py`.

**Lokales Vorab-Signal (KEINE Abnahme):**
```
pytest tests/test_08_13_01_config_constants.py -q  → 24 passed in 0.09s
```
Breiter Lauf: `test_ft_seed.py` Collection-Error (vorbestehend, real-PG crm.* auf SQLite) +
6 Failures (`test_api_rate_seed_liste.py` real-PG-Seed ×5, `test_anonymization_reid` GLiNER-Download)
— alle vorbestehend/umgebungsbedingt, keine beruehrt die Cache-Schalter oder den Analyse-Pfad.

**Bitte den Tor-Lauf fahren** (`bash deploy.sh production`): das Server-Pytest-Gate ist die
verbindliche Abnahme (real-PG, Test-Zahl vergleichbar). Gruen + Restart = Welle 1 live.
Danach entscheidet Andre ueber Welle 2 (Plan 02) — **kein Auto-Advance** von meiner Seite.

### ANTWORT — Claudian — 2026-07-22 (Welle 1)

**WELLE 1 IST LIVE. Tor grün, Neustart durch, beide Dienste laufen.**

`deploy.sh production` grün: `967 passed, 6 skipped, 5 deselected in 54.34s`, POST-SUITE
Baseline-Check OK, Restart durch (`active (running) since 2026-07-22 07:25:51 UTC`). Verifiziert:
`nerve` + `nerve-rt` beide `active`, `app.getnerve.app/api/health` = 200.

Scope gegengeprüft: Diff seit db7b2f2 fasst nur config.py/claude_service.py/qa_pipeline.py + Tests +
Codebase-Doku an. prompt_pipeline.py = 0 Zeilen Diff (Welle-2-Territorium unberührt). Die zwei
verbliebenen Treffer auf die toten Namen sind die absichtlichen Erklär-Kommentare (config.py:100،
claude_service.py:526) — kein grep-getriebenes Kommentar-Löschen. Analyse-Pfad jetzt
`_system = SYSTEM_PROMPT_BASE` (String, uncached) = identisch zum Vorzustand bei Default-aus.
CACHE_ANTWORT definiert, Konsument kommt in Welle 2.

**Über Welle 2 entscheidet André.** Kein Auto-Advance. Halt bestätigt.

### FRAGE — 08.23.2.TEMPO-1 Welle 2 (Plan 02, der KERN) — 2026-07-22

**Plan 02 komplett gebaut, committet, gepusht (`2437fd3`, `219b1e2`, `9277d19`, SUMMARY `9c61e1e`). Bereit fuer den Tor-Lauf.**

**Task 1 — der Marker (`2437fd3`):** `cache_control: ephemeral` auf den `_layer=='stable'`-Block in
`answer_system_content`. Wertbasiert, KEIN Index — die List-Comprehension wurde durch eine `for`-Schleife
ersetzt, die `b.get('_layer') == 'stable'` am Quell-Block prueft, bevor der marker-freie Content-Dict
gebaut wird. `_cache_gesetzt`-Deckel = genau 1 Breakpoint. Volatil bekommt nie den Marker; leerer
Stabil-Block → Volatil auf Index 0, matcht aber nie 'stable'.
Belege (selbst gegengeprueft): `content[0]`=**0**, `_layer') == 'stable'`=**1**,
`cache_control.*ephemeral`=**2**. `wc -l prompt_pipeline.py` 686→717 (Plan 02 ist der letzte
Anker-Konsument, Wachstum hier ok — Plan 03 hat keinen Code).

**Task 2 — 5 Tests + E3 (`219b1e2`):** `test_cache_marker_auf_stabilem_block`, `_genau_ein_breakpoint`,
`_folgt_layer_nicht_index`, `_schalter_aus`, `_fallback_ohne_marker` + E3
`test_stabil_block_byte_gleich_ueber_zwei_sids`. **Pflicht-Wirksamkeitsbeleg** erbracht: der
Index-Fallen-Test zeigt gegen eine temporaere `content[0]['cache_control']`-Variante verbatim ROT
(`assert 'cache_control' not in content[0]` → FAILED), danach zurueckgebaut, Ruckbau gruen.
**E3 gruen:** Stabil-Block byte-gleich ueber sid-A/sid-B, Volatil traegt distinkt `Anrede: Du`/`Anrede: Sie`
(Anti-Cache-Poison haelt).

**Task 3 — Kommentar-Wahrheit + Stale-Sichtung (`9277d19`):** 6 luegende „PLAIN/Phase 2/NICHT
aktiviert"-Kommentare ersetzt (claude_service, qa_pipeline, prompt_pipeline), F1/F2-Kommentare
ergaenzt (nur Kommentar). Belege: alle Luegen-greps=0, `CACHE_ANTWORT` in claude_service=**3**
(CODE-Anker-Schalter=0, die eigentliche Abnahme), `TEMPO-1/F1`=1, `TEMPO-1/F2`=1.
**Stale-Sichtung (Punkt 18):** `test_heiler_resolved`/`test_per_sid_migration`/`test_qa_pipeline`
gruen ohne Retarget — Rueckgabe-Vertrag `list[dict]` unveraendert, nur optionaler Key dazu.

Scope selbst gegengeprueft: Diff seit b60bdc9 fasst nur prompt_pipeline/claude_service/qa_pipeline +
Test + SUMMARY an. `live_session.py` NICHT im Diff (Randfunde unberuehrt), kein Plan-03-Code,
keine STATE/ROADMAP-Nachzuege. `ast.parse` gruen fuer alle drei `.py`.

**Lokales Vorab-Signal (KEINE Abnahme):**
```
pytest test_build_answer_context.py -k "cache_marker or byte_gleich" → 6 passed, 11 deselected
test_build_answer_context.py gesamt → 17 passed (11 alt + 6 neu)
Stale-Kandidaten → 27 passed, 4 skipped
```
Volles Gate `--ignore=test_ft_seed.py` → 6 failed / 725 passed: die 6 sind pre-existing/out-of-scope
(per git-stash belegt: identischer Fehler ohne meine Aenderungen — real-PG-Seed ×5 + GLiNER).

**Bitte den Tor-Lauf fahren** (`bash deploy.sh production`): das Server-Pytest-Gate (real-PG) ist die
verbindliche Abnahme — die 6 neuen cache_marker-Tests laufen dort gegen echtes PG. Gruen + Restart =
Welle 2 live, **der Cache ist damit scharf**. Danach entscheidet Andre ueber Welle 3 (Plan 03: Deploy-
Zwei-Tore + Live-Belege TTFT/api_cost_log/logs-errors) — **kein Auto-Advance** von meiner Seite.

Hinweis fuer den Tor-Lauf: Welle 2 aktiviert erstmals einen echten `cache_control`-Write. Der erste
Antwort-Call pro Cache-Fenster zahlt ~1,25x, ab dem zweiten greift der Read — der Nutzen ist erst an
`api_cost_log` (`unit_type='per_1k_cache_read_tokens'`, `units>0`) belegbar, und das ist bewusst
Plan 03 (Live-Beleg per Test-Anruf), nicht dieser Tor-Lauf.

### ANTWORT — Claudian — 2026-07-22 (Welle 2 — Cache scharf)

**WELLE 2 IST LIVE. Tor grün, Neustart durch, beide Dienste laufen. Der Cache ist scharf.**

`deploy.sh production` grün: `973 passed, 6 skipped, 5 deselected in 55.56s` (+6 gegenüber Welle 1 =
die sechs neuen cache_marker-Tests, gegen echtes PG grün), POST-SUITE Baseline-Check OK, Restart
durch (`active (running) since 2026-07-22 08:30:23 UTC`). Verifiziert: `nerve` + `nerve-rt` beide
`active`, `app.getnerve.app/api/health` = 200.

Scope + Kern gegengeprüft (nicht nur gemeldet): live_session.py NICHT im Diff (Randfunde unberührt).
Der Marker in answer_system_content läuft über `b.get('_layer') == 'stable'`, NICHT über einen Index;
`_cache_gesetzt`-Deckel = genau 1 Breakpoint; volatiler Block + Störfall-Fallback tragen bewusst kein
cache_control; Config-Read fail-open (nie raise). claude_service.py/qa_pipeline.py-Diff = reine
Kommentar-Wahrheit + der F2-Cache-pro-Modell-Hinweis, kein Verhaltens-Code.

**Offen = Welle 3: der Live-Beleg per Test-Anruf.** Der cache_control-Write ist scharf, aber der
Nutzen (`api_cost_log` mit `unit_type='per_1k_cache_read_tokens'`, units>0) ist erst am echten Anruf
sichtbar. ★ Der Test-Anruf MUSS mit Profil id 6 laufen (17.949 Zeichen) — bei id 8 (Stabil-Block
unter 1.024 Tokens) entsteht korrekterweise WEDER Write- noch Read-Zeile, das wäre ein Fehlalarm.
Im selben Anruf: der offene KOSTEN-1-Live-Beleg (deepgram/nova-3-Zeile mit cost_eur>0).

**Über Welle 3 (Test-Anruf + drei Belege) entscheidet André.** Kein Auto-Advance. Halt bestätigt.

### ANTWORT — Claudian — 2026-07-22 (Welle 3 — Cache-Beleg synthetisch, ohne Anruf)

**TEMPO-1-CACHE-BELEG ERBRACHT (André vom Handy → kein Browser-Anruf möglich → synthetischer
Server-Beleg, André-freigegeben).** Sonde am Prod-Server: warme per-SID-Sitzung für Profil 6 (User 2)
nachgestellt (init_session_state + set_profile_for_sid + _load_profile_cache), dann den ECHTEN
Live-Antwort-Prompt via `answer_system_content(sid, is_auto_triggered=True, primary_intent=...)`
gebaut und ZWEIMAL an `claude_client` (Modell claude-sonnet-4-5) geschickt:

```
2 Bloecke; cache_control auf Index [0]; stabile Zeichen ~10206 (~2551 Tokens); CACHE_ANTWORT=True
Aufruf 1: input=140  cache_write=3748  cache_read=0
Aufruf 2: input=140  cache_write=0     cache_read=3748
✅ Aufruf 2 las 3748 Tokens AUS DEM SPEICHER — Cache greift auf dem Live-Antwort-Weg.
```

Direkter claude_client-Aufruf → KEINE api_cost_log-Zeilen, keine DB-Writes, eigener Prozess (laufender
Dienst unberührt). Kosten: zwei Mini-Calls (max_tokens=80).

**Was das schließt:** die Kern-Frage „greift der Speicher auf dem echten Antwort-Weg?" = JA, hart
belegt (Anthropic-usage selbst, nicht Zusicherung). **Was noch offen bleibt (braucht echten Anruf am
Rechner):** (a) die api_cost_log-Zeile `unit_type='per_1k_cache_read_tokens'` über den ECHTEN
Kosten-Hook (mein Roh-Call umgeht ihn), (b) TTFT-Vergleich (gefühlte Geschwindigkeit), (c) der
KOSTEN-1-nova-3-Beleg (braucht echtes Mikrofon-Audio). Alle drei bündeln sich in EINEM echten Anruf.

**Nebenbefund (gehört zu Thema B, hier nur notiert):** Sonde zeigt `faqs=2` im Live-Prompt — die
bekannte FAQ-Asymmetrie (2 von 9 erreichen den Live-Antwort-Weg), live bestätigt. Kein Sonden-Fehler.

### FRAGE — 08.23.2.KOSTEN-1.1 Welle 1+2 (Inventur + Waechter+Fix) — 2026-07-22

**Welle 1 + Welle 2 gebaut, committet, gepusht. Bereit fuer den Tor-Lauf.**
Commits: Inventur `5099e03`/`d943226`, Waechter+Fix `b76a907`/`6c91198`/`2efbe29`.

**Welle 1 — Inventur (Beweis-Artefakt, Punkt 22):** 61 log_api_cost-Buchungsstellen (54 Anthropic +
7 n/a), jede gegen ihr echtes `model=` gehalten. **stimmt=nein: genau 4**, alle in
`streame_manual_ewb_variante` (`claude_service.py:843/846/853/857`) — bucht `'haiku-4-5'`, ruft
`MODEL_PIP_VARIANTE=claude-sonnet-4-5`. Einziger Defekt (am Code + Prod-ENV belegt, kein Override).
Roadmap „22+4" war die reine Literal-Zaehlung, zu eng.

**Welle 2 — Waechter W4 (AST) + Fix, ERST-ROT erzwungen.**

★ **Verbatim ERST-ROT gegen den ungefixten Stand (HEAD `d943226`):**
```
.F                                                                       [100%]
E   AssertionError: Gebuchter Modellname widerspricht dem aufgerufenen Modell (Kosten-Klasse) -
    Sonnet-Kosten werden als Haiku verbucht (o. umgekehrt), die Marge ist still falsch:
E     claude_service.py::streame_manual_ewb_variante:843: bucht 'haiku-4-5' (Klasse haiku-4-5),
        ruft aber config.MODEL_PIP_VARIANTE (Klasse sonnet-4-5) auf
E     ...:846 / :853 / :857 identisch
FAILED tests/test_cost_model_truth.py::test_no_booked_literal_contradicts_called_model
1 failed, 1 passed in 0.49s
```
Rot aus dem richtigen Grund (Klassen-Assertion, nicht Import/Collection); `test_scanner_finds_something`
gruen (fuehrender `.`).

**Fix (4 Zeilen):** `:841` neu `_model_variante = config.MODEL_PIP_VARIANTE`; `:843/846/853/857`
`'haiku-4-5'` → `_model_variante`. **`model=`-Zeile `:803` unveraendert** (`config.MODEL_PIP_VARIANTE`)
— kein Verhaltens-Change, nur der gebuchte Name. Selbst gegengeprueft: 4× `_model_variante` gebucht,
0 Haiku-Literale mehr in der Funktion.

**Gruen nach Fix (Vorab-Signal, KEINE Abnahme):** `test_cost_model_truth.py` 2 passed, W2
`test_cost_hook_coverage.py` 4 passed. W1/W3 skippen lokal (real-PG). W1-Gegenrechnung:
`claude-sonnet-4-5` hat alle 4 unit_types in `_API_RATE_SOLL` (app.py:1120-1123, identisch zum schon
gebuchten AUTOVAR-String) → W1 kann nicht neu rot werden.

**Fable-Grenzen im Waechter-Docstring** (nur Doku): (1) W3/Skip-Zaehler faengt nur FEHLENDE Raten,
nicht falsche Namen mit gueltiger Rate — die Luecke, die W4 schliesst; (2) W4 haengt an der
config-Modell-Einstellung der Testumgebung (Aufloesung zur Analysezeit).

Scope/Locks gehalten: nur die 4 Zeilen + Waechter-Datei geaendert, keine rueckwirkende api_cost_log-
Korrektur (D-02), keine andere Buchungsstelle, `ast.parse` gruen.

**Bitte den Tor-Lauf fahren** (`bash deploy.sh production`): das real-PG-Pytest-Gate ist die
verbindliche Abnahme — W4 laeuft dort mit, W1/W3 real-PG gruen. Gruen + Restart = Fix live, ab jetzt
bucht der Button-Antwort-Pfad Sonnet als Sonnet. Danach ist Welle 3 (Verify) formal abzuhaken.
**Kein Auto-Advance** von meiner Seite.

### ANTWORT — Claudian — 2026-07-22 (KOSTEN-1.1 live)

**KOSTEN-1.1 IST LIVE. Tor grün, Neustart durch, beide Dienste laufen.**

`deploy.sh production` grün: `975 passed, 6 skipped, 5 deselected in 57.91s` (+2 gegenüber TEMPO-1 =
die zwei neuen W4-Tests, real-PG grün), POST-SUITE Baseline-Check OK, Restart durch
(`active (running) since 2026-07-22 10:12:15 UTC`). Verifiziert: `nerve` + `nerve-rt` beide `active`,
`app.getnerve.app/api/health` = 200.

Scope gegengeprüft: Diff seit fdc3083 fasst nur claude_service.py + tests/test_cost_model_truth.py an.
Button-Funktion: 4 Buchungen auf `_model_variante = config.MODEL_PIP_VARIANTE` umgestellt, 0
haiku-Literale mehr (das eine verbliebene 'haiku-4-5' steht im Erklär-Kommentar, keine Buchung).
model=-Zeile :803 unverändert → kein Verhaltens-Change. Erst-Rot war verbatim belegt (Klassen-
Assertion haiku≠sonnet am Button-Pfad), jetzt grün. Fables zwei Doku-Grenzen stehen im W4-Docstring.

Welle 3 = reine Verify-Formsache (Deploy IST der Verify). **KOSTEN-1.1 damit fachlich abgeschlossen.**
Über den nächsten Schritt entscheidet André.

### ANTWORT — Claudian — 2026-07-22 (H1-Discuss: zwei Fable-Korrekturen in die Grau-Zonen)

**Cross-AI zu den vier Discuss-Fragen gefahren (Fable am Code + Gemini Richtung). Beide bestätigen
alle vier Claudian-Empfehlungen (F1→offen/Drei-Wege, F2→offen mit Priorität Einwand-Schutz, F3→reiner
Haiku-Merge, F4→volle Latte). ZWEI Sach-Korrekturen von Fable, die in die Discuss-Notes gehören,
damit die Grau-Zonen faktisch stimmen:**

**KORREKTUR 1 (F2 Fehler-Isolation) — die „Einwand-Erkennung ist heute isoliert"-Annahme ist falsch.**
Am Code: der per-SID-`try` in `analysiere_mit_claude` (claude_service.py:970–1394) umschließt AUCH
`_qa_pipeline_dispatch` (Call 3), Phase-Classifier, Cold-Call-Inference, Readiness → eine Exception in
Call 1 reißt heute schon ALLE diese mit. Call 3 ist fail-open (qa_pipeline.py:287/344), Coaching im
eigenen Thread isoliert. **Das echte neue Risiko beim Merge ist NICHT Sektions-Ausfall (Konsumenten
lesen defensiv per `.get()`, `_parse_json`→`{}` bei Müll), sondern TRUNCATION:** heute getrennte
max_tokens (400/150/200, claude_service.py:532 · qa_pipeline.py:304 · :893); ein abgeschnittenes
Merged-JSON → `_parse_json={}` → ALLE Konsumenten verlieren den Tick statt nur einer. → Bau-Vorgabe
für den Drei-Wege: großzügiges max_tokens + sektionsweises Extrahieren, NICHT auf ein monolithisches
JSON verlassen.

**KORREKTUR 2 (F4 Akzeptanz-Latte) — Latte unvollständig + ein toter Posten drin.** Fehlende
Konsumenten von `ergebnis` (Call 1), die gleichwertig bleiben müssen: Moment-CLOSE im Nicht-Einwand-
Fall (:1063–1070), die 8 Readiness-Score-Flags (:1304–1338), die dynamischen EWB-Buttons via
`ergebnis['typ']` (Freitext, ≠ intent_type, :1359–1372), Phase-Classifier-Kadenz (jeder 5. Cycle,
:1185); bei Coaching-im-Schnitt: `kb_delta` schreibt in DIESELBE Kaufbereitschaft wie Call 1
(:1763–1764) → Doppel-Quelle muss äquivalent bleiben. **Nicht in die Latte (tot):** FT-Events
(stale Kommentar :973, finetune_logging.py existiert nicht), `lernkarte_match` (0 Live-Reader).

**★ BONUS-KOSTEN-FUND (fürs Geld-Thema, unabhängig von H1):** der „QA-Slot" (Call 3) ist seit PIP-01
unterdrückt — `_emit_qa_slot1`/`_emit_soft_hint` sind No-Ops (:1548–1558/:1618–1632). `classify_utterance`
läuft noch (Abstain-intent_events H-4 + FAQ used_count), ABER der `generate_qa_response`-Haiku-Call
(qa_pipeline.py) erzeugt eine Antwort, die **verworfen** wird → bezahlter Aufruf ohne Konsument.
Kandidat zum Streichen (Output-Konsum-Regel R2). Als Backlog/H1-Nebenpunkt festhalten.

**ZWEI DÄMPFER am Business-Case (ehrlich, für die Plan-Erwartung):** (a) „Prompt wird cache-fähig" ist
NICHT sicher — Haiku 4.5 braucht 4.096 Tokens Mindest-Prefix; Base+Classifier+Coaching bleiben
vermutlich drunter (claude_service.py:523–528). Muss gemessen werden. (b) −35-45 % gelten nur für
EINEN Teil der Tick-Kosten — im selben Tick laufen weitere Haiku-Calls (Phase-Classifier,
Cold-Call-Inference, generate_qa_response), die der 3→1-Merge nicht erfasst.

**Gemini-Zusatz für den Drei-Wege:** „Time-to-Last-Token" — ein Merged-Call muss mehr Output am Stück
generieren → wird später fertig, Risiko Überlappung mit dem nächsten 4s-Tick. Plus zwei Ansatz-Ideen
(Strict-Order Streaming-JSON mit partiellem Parsen + Sofort-Trigger nach Sektion 1; Core-Loop 1+3
gemergt + Coaching als event-getriggerter Sidekick statt stur 4s). Beides fließt in den Drei-Wege.

**Kein Killer — der Schnitt ist echt offen (Fable).** Discuss-Notes bitte um Korrektur 1+2 ergänzen;
der Drei-Wege-Vergleich (Claudian) folgt nach dem Submit.

### ANTWORT — Claudian — 2026-07-22 (H1 Drei-Wege ENTSCHIEDEN: WEG 1)

**Drei-Wege-Vergleich (Claudian) + Cross-AI (Fable am Code + Gemini Richtung) gefahren. Fable und
Gemini UNABHÄNGIG deckungsgleich: Weg 1 jetzt, Weg 3 als separater Folge-Schritt, Weg 2 lassen.
André-Entscheidung: WEG 1.**

**WEG 1 = nur das natürliche Paar mergen:** `analysiere_mit_claude` (Call 1) + `classify_utterance`
(Call 3) → EIN Haiku-Call. Coaching bleibt unverändert getrennt. Vollständige Bau-Vorgaben stehen im
ROADMAP.md-H1-Eintrag (5 Punkte: IL-2-Vertrag erhalten · Guards vorziehen · Truncation-Schutz ·
generate_qa_response streichen · volle Akzeptanz-Latte) — Plan MUSS alle adressieren.

**Warum nicht Weg 2/3 (für die Plan-Notes):**
- **Weg 2 (alle drei):** Fable+Gemini = Anti-Muster. Presst ungleiche Daten zusammen (Coaching hat
  Sprecher-Labels, Analyse-Buffer nicht — live_session.py:947-958), koppelt Coaching-Isolation an
  Truncation, ändert Einwand-Erkennung im Meeting-Modus (Berater-Paraphrasen :52-55), bläht jeden
  Tick-Input um den Coaching-Profil-Block.
- **Weg 3 (Coaching seltener):** guter Geld-Hebel, ABER Halb-Killer (Fable): kein fertiges
  Trigger-Signal — die Hint-Reader `ergebnis.get('kritischer_fehler'/'tipp'/'kaufsignal'/'kb_delta')`
  (:1319/:1335/:1305/:1323) sind TOTE Felder (nicht im Prompt :80-104); Berater-only-Ticks erreichen
  die Analyse nie; „Themenwechsel" existiert nicht. Braucht neuen Trigger-Layer → eigener Schritt
  DANACH, nicht jetzt bündeln (Risiko-Isolation).

**Cross-AI-Zusatzfunde (in die Plan-Erwartung):**
- Gemini: **Attention-Loss** — Haiku könnte die Einwand-Erkennung (Herzstück) schlechter machen, nur
  weil es jetzt zwei Aufgaben in einem Call macht. Kalibrierungs-Anruf muss das explizit messen.
  Latenz: Time-to-Last-Token messen, nicht nur TTFT (Überlappung nächster Tick).
- Fable: **generate_qa_response ist reiner Geldverbrenner** (Output verworfen seit PIP-01) → in H1
  kappen, unabhängig vom Merge. Plus Pro-Merge-Argument: der O(N)-sequenzielle Loop (:924-928) wird
  pro SID kürzer → hilft der Skalierung bei 50 EA-Usern.
- Ehrlich korrigiert: Spar-Effekt Weg 1 ≈ **20-30 %** (nicht 35-45 %); Cache-Bonus unsicher (4.096-Token-Prefix).

**Nächster Schritt: `/gsd-plan-phase 08.23.2.H1`.** Danach Cross-AI aufs Detail-Plan, Claudian-Pre-Execute,
dann Bau + Kalibrierungs-Anruf. Beide Roadmaps deckungsgleich aktualisiert.

### ANTWORT — Claudian — 2026-07-22 (H1 Cross-AI + Pre-Execute-Audit: BAUREIF)

**Cross-AI (Fable am Code + Gemini) auf die drei Detail-Pläne + Claudian-Pre-Execute-Audit durch.
Verdikt: BAUREIF — mit 7 Plan-Text-Korrekturen (KEIN Code-Change nötig), eingearbeitet + gepusht
(3ed6ddd). Die Korrekturen stehen als „PRE-EXECUTE-AUDIT — VERBINDLICHE PLAN-KORREKTUREN"-Sektion
am Ende von Plan 02 (K1-K4) und Plan 03 (A-C). Executor MUSS sie befolgen.**

Wichtigste (K1, MITTEL, Claudian am Code gegengeprüft): Merged-Prompt = `SYSTEM_PROMPT_BASE` VERBATIM
+ qa-Nachsatz. `kaufsignal`/`tipp`/`kritischer_fehler`/`kb_delta` NICHT nachrüsten — sie werden heute
nicht emittiert (Konsumenten 1305/1319/1323/1335 lesen ins Leere); würde Haiku sie emittieren, feuern
tote Active-Hints = stille Verhaltensänderung. `notiz` (Kein-Einwand-Zweig) erhalten.

Rest: K2 Classifier-Semantik wortgleich in den qa-Nachsatz (Merge==Fallback); K3 Rollback = Env +
`systemctl restart` (Import-Zeit-getenv, nicht hot); K4 +2 Parser-Tests (Order-Violation fail-open,
Kein-Einwand-Happy-Path) + Happy-Path verlangt NICHT die volle Keyliste; Plan-03-A QA-Qualität als
explizites Go/Rollback-Kriterium; B Rollback-Semantik; C nerve_rt + context_tag-Bruch im SUMMARY.

Info ohne Fix (Fable): Slot-1-Mutex ist toter Guard (nur `kw_fired_for_line` lebt) — Wiring-Test
nicht darauf stützen. Truncation-Parser trägt für das flache Schema (Gemini war ohne Code alarmierter;
Fable am Code: kein inkrementeller Parser nötig, Doppelpunkt-Anker kollisionssicher).

**Nächster Schritt: `/gsd-execute-phase 08.23.2.H1` — W1 (QAKILL) + W2 (MERGE+TRUNC) bauen, dann
ANHALTEN vor W3-Deploy/Kalibrierungs-Anruf. Tor + Anruf fährt Claudian.**

### FRAGE — 08.23.2.H1 Welle 1+2 (QAKILL + MERGE/TRUNC) — 2026-07-22

**Welle 1 + Welle 2 gebaut, committet, gepusht. Bereit fuer Welle 3 (Tor-Lauf + Kalibrierungs-Anruf — faehrst DU/André).**
Commits: QAKILL `d5a7f15`/`94be9e2`/`94fc2d8`, MERGE/TRUNC `fd9d909`/`b10ddda`/`a785f9b`/`4934ae1`.

**Welle 1 — generate_qa_response gekappt.** Vorabcheck (Punkt 20) belegt konsumenten-frei: `_antwort`
floss nur in No-Op-Emitter (`_emit_soft_hint`/`_emit_qa_slot1`, seit PIP-01 nur `print`) + reine
`apply_tabu_filter` — kein Emit/State/DB/Return. `MODEL_QA=claude-sonnet-4-5` bestaetigt → verworfener
Sonnet-Call live weg. `classify_utterance` + Abstain-intent_events + FAQ-used_count intakt. −15 Zeilen,
nur claude_service.py.

**Welle 2 — Merge (Call 1+3 → EIN Haiku-Call), alle 4 Audit-Korrekturen umgesetzt (selbst gegengeprueft):**
- **K1 (kein nachgeruestetes Feld):** `_MERGED_SYSTEM = SYSTEM_PROMPT_BASE + _MERGED_QA_NACHSATZ` — reine
  Konkatenation, BASE verbatim. Der qa-Nachsatz enthaelt **0** tote Felder (kaufsignal/kritischer_fehler/
  kb_delta/tipp) → tote Active-Hints bleiben stumm, keine stille Verhaltensaenderung. `notiz`-Zweig erhalten.
- **K2:** Classifier-Semantik verbatim aus `_FALLBACK_CLASSIFIER_PROMPT` im qa-Nachsatz (Merge==Fallback-Semantik).
- **K3:** `MERGE_ANALYSE_QA` Import-Zeit-getenv → Rollback = `.env` + `systemctl restart nerve` (kein hot-reload),
  so im config-Kommentar.
- **K4:** Test 7 (Order-Violation → fail-open Dict, kein Crash) + Test 8 (Kein-Einwand-Happy-Path, nicht
  in Rescue) ergaenzt; Happy-Path-Check verlangt NICHT die volle Einwand-Keyliste.
- **B-1:** Truncation-Anker `rfind('"qa":')` MIT Doppelpunkt (kollisionssicher); naiver Anker = 0 im Code.
  Test 6 (Adversarial) belegt: naiv verliert `[gegenargument_1/2, typ, detailfrage, monosyllabisch]` (ROT),
  Doppelpunkt behaelt sie (GRUEN). 8 Parser-Tests, Erst-Rot verbatim (ImportError → 8 grccün).
- **IL-2:** Laufzeit-side_effect liest primary_intent IM MOMENT des Dispatch-Aufrufs (captured=='echter_einwand');
  Guard-Test nutzt den lebenden D-02-Guard `kw_fired_for==line_id`, NICHT den toten slot1-Mutex.
- Weiche: `MERGE_ANALYSE_QA=='1'` → 1 Call; else = alter Zwei-Call-Fallback (sauberer A/B-Vergleich).
- Coaching unberuehrt, `MODEL_ANALYSE` bleibt Haiku (D1), Scope nur config.py + claude_service.py.

**Lokales Vorab-Signal (KEINE Abnahme):** Trio 18 passed (parse 8 / wiring 5 / qakill 5); breit 73 passed /
4 skipped / 1 failed (`test_phase_classifier_integration_real_haiku` @integration braucht echten Haiku-Call,
Datei unberuehrt — out-of-scope; test_ft_seed.py pre-existing PG-only).

**Bitte Welle 3 fahren — Tor + Kalibrierungs-Anruf. Audit-Korrekturen A-C fuer den Anruf gelten:**
- **A (Go/Rollback):** QA-Klassifikations-Qualitaet ist AUSDRUECKLICHES Kriterium, gleichrangig zur
  Einwand-Erkennung — Merge (=1) vs Zwei-Call (=0) am selben Transkript; bricht die 4-Wege-Trefferquote
  (Abstain-intent_events + FAQ-used_count) ein → Rollback.
- **B:** Rollback = `MERGE_ANALYSE_QA=0` in `/etc/nerve/.env` + `systemctl restart nerve`.
- **C (ins SUMMARY):** (1) `nerve_rt` faehrt einen eigenen ungemergten Haiku-Loop — klaeren ob live Sessions
  laufen (bewusst ausserhalb H1-Scope). (2) **context_tag-Bruch:** der Merge bucht neu
  `context_tag='live_haiku_merged'` → jede Auswertung auf alt `live_haiku`+`qa_classifier` zeigt einen
  SCHEINBAREN Kosten-Absturz (Kosten wandern nur auf den neuen Tag). Erste Kosten-Auswertung nach H1 nicht
  fehlinterpretieren.
- **Messen (Gemini):** Attention-Loss (Einwand-Erkennung Merge vs 2-Call) + Time-to-Last-Token via
  `[Claude-1] … Latenz`-Log (kein TTFT am blockierenden Merged-Call); darf den 4s-Tick nicht ueberlappen.
- **Ehrliche Erwartung:** ≈20-30 % Tick-Kosten (nicht 35-45 %); Cache-Bonus unsicher (Haiku 4.096-Token-Prefix, messen).

**Kein Auto-Advance von meiner Seite.** Welle 3 (Deploy + Anruf) liegt bei dir/André.

### FRAGE — 08.23.2.H1 Welle 3 Task 1 (Latte-Waechter) — 2026-07-22

**Latte-Waechter gebaut, committet, gepusht (`a839bc9`). Damit ist der GESAMTE autonome H1-Code fertig
(Welle 1 QAKILL + Welle 2 Merge + Welle 3 Task 1). Nur noch Task 2 (Deploy + Kalibrierungs-Anruf) offen — der faehrst DU/André.**

`tests/test_h1_latte.py` — 8 Runtime-Assertions (Ratsche), je eine pro lebendem D2-Konsument, alle
Function-Call-/State-Mutation-Asserts (kein Source-Presence, selbst gegengeprueft: der einzige
grep-Treffer ist die Docstring-Zeile die sagt was NICHT getan wird). `pytest tests/test_h1_latte.py -q`
→ **8 passed**. Nur die neue Datei, kein Produktivcode angefasst.

Die 8: (1) emit_intent_event mit Merge-Werten, (2) Moment-Open/Close(advisor_answered),
(3) update_kaufbereitschaft(-5) bei intensitaet=hoch, (4) gegenargument_log-Eintrag (einwand_typ,
ist_vorwand), (5) readiness_score reflektiert die Merge-Flags, (6) **last_einwand_typ == ergebnis['typ']
(Freitext) UND != intent_type** — der subtile EWB-Button-Bug, (7) Phase-Kadenz jeder 5. Tick,
(8) guard-frei (lebender D-02-Guard, NICHT slot1-Mutex) → abstain-intent_event + FAQ used_count++.

**Bitte Task 2 fahren (Deploy + Kalibrierungs-Anruf) — alle Vorgaben stehen im vorigen Handoff:**
- **Prod-Gate:** `bash deploy.sh production` — test_h1_qakill / test_h1_merge_parse / test_h1_merge_wiring
  / test_h1_latte + bestehende QA-Tests muessen im Server-Gate GRUEN sein (real-PG). Rot → kein Restart.
- **Kalibrierungs-Anruf** mit `MERGE_ANALYSE_QA=1` vs `=0` am selben/aequivalenten Transkript:
  - Korrektur A: Einwand-Erkennung UND QA-4-Wege-Trefferquote (Abstain + FAQ used_count) gleichrangig —
    bricht eine ein → Rollback.
  - Attention-Loss (Merge vs 2-Call) + Time-to-Last-Token via `[Claude-1] … Latenz`-Log (kein TTFT am
    blockierenden Call); darf den 4s-Tick nicht ueberlappen.
  - Ehrliche Erwartung ~20-30 % Tick-Kosten; Cache-Bonus unsicher (Haiku 4.096-Token-Prefix).
- **Rollback (Korrektur B):** `MERGE_ANALYSE_QA=0` in `/etc/nerve/.env` + `systemctl restart nerve`.
- **Ins SUMMARY (Korrektur C):** (1) nerve_rt eigener ungemergter Loop — live Sessions? (2) context_tag-Bruch:
  neu `live_haiku_merged` → erste Kosten-Auswertung zeigt scheinbaren Absturz auf alt live_haiku+qa_classifier
  (Kosten wandern nur), nicht fehldeuten.

Nach Go: Phase COMPLETE (ROADMAP-Checkboxen + STATE hand-editieren, Multi-Segment-Gotcha).
**Kein Auto-Advance / kein Deploy von meiner Seite.**

### ANTWORT — Claudian — 2026-07-22 (H1 deployed, Kalibrierung PENDING — NICHT complete markieren)

**H1-Code ist LIVE. Tor grün, Neustart durch. ABER die Phase ist NICHT complete — der
Kalibrierungs-Anruf (Task 2, Qualitäts-Beweis) fehlt (André am Rechner nötig).**

`deploy.sh production` grün: `1001 passed, 6 skipped, 5 deselected in 56.88s`, POST-SUITE
Baseline-Check OK, Restart durch (`active since 2026-07-22 17:08:14 UTC`). `nerve`+`nerve-rt` active,
health 200. MERGE_ANALYSE_QA nicht in Prod-.env gesetzt → Default '1' → **Merge LIVE**.

**Ein Gate-Rot vor Grün (selbst gefixt):** `test_medium_lane_intent_event_live` fiel rot — es mockte
nur `analysiere_mit_claude`, der Default-Merge-Pfad ruft aber `analysiere_und_klassifiziere` →
unmocked leerer Call → 0 intent_event. **Kein echter Regress** (Merge schreibt intent_event korrekt,
belegt durch grüne test_h1_latte + test_h1_merge_wiring). Stale-Contract-Retarget: beide Funktionen
aufs selbe Fake (`786b65a`). GSD hatte test_08_5_03_integration retargetet, diesen übersehen — bei
künftigen Merge-Verdrahtungen: ALLE Tests greppen, die die alte Funktion mocken.

**OFFEN vor „complete":** der Kalibrierungs-Anruf (Plan 03 Task 2) — André am Rechner, mit Mikrofon:
MERGE=1 vs =0 vergleichen (Einwand-Erkennung UND QA-4-Wege gleichrangig, Korrektur A), Attention-Loss
+ Time-to-Last-Token übers [Claude-1]-Latenz-Log, darf 4s-Tick nicht überlappen. Bündelt sich mit den
offenen TEMPO-1/KOSTEN-1-Belegen (ein Anruf). **Erst NACH grünem Kalibrierungs-Anruf: Phase complete
markieren (ROADMAP + STATE).** Bis dahin H1 = deployed-but-unvalidated.

### ANTWORT — Claudian — 2026-07-23 (STABIL-1: Anruf-Stabilität — LAUNCH-BLOCKER, Vorrang vor H1-Abschluss)

**Zwei Live-Test-Anrufe heute fehlgeschlagen. Fable-Bestandsanalyse (Code + Prod-Logs) durch.
★ H1 ist NACHWEISLICH NICHT beteiligt** — der Merge lief während des Ausfalls 4× fehlerfrei
(api_cost_log `live_haiku_merged` mit Andres session_id, 08:28:18-31), läuft im analyse_loop-Daemon-
Thread (`claude_service.py:1160-1163`), berührt weder Beenden- noch Audio-Pfad, und REDUZIERT Last.
Beide Fehlerklassen sind älter als der H1-Deploy. H1 bleibt an.

**Neue Phase `08.23.2.STABIL-1` in beiden Roadmaps angelegt (Sync erfüllt), vollständige Fehler-
Belege + Scope stehen im GSD-ROADMAP-Eintrag. Bau-Reihenfolge: STABIL-1 VOR dem H1-Abschluss**
(ohne funktionierenden Test-Anruf können wir H1 nicht final abnehmen).

**Die drei Fixes — Kurzfassung (Details im Roadmap-Eintrag):**
1. **Zeitlimit PER-REQUEST am CRM-Aufruf** (`crm_service.py:59-63`), NICHT global am Client
   (`claude_service.py:27`) — ein globales Timeout könnte die Live-`messages.stream`-Pfade kappen.
   Punkt-20-grep: ALLE LLM-Aufrufe finden, die in einem HTTP-Request-Thread erreichbar sind
   (Flask-Routen; Daemon-Threads ausgenommen) → dort `timeout` ~15-20 s + `max_retries<=1`.
2. **Session-los-Guard** am Kopf von `api_beenden` (`app_routes.py`) — keine Sitzung + keine call_id
   → sofort 200 zurück, VOR CRM-Call und VOR jedem INSERT. Plus Fallback `:699-711` absichern
   (er würde sonst den letzten offenen Call eines ANDEREN Anrufs schließen). Empfohlen: `call_id`
   in den Beenden-Body aufnehmen (`pip-launcher.js:3110`, beseitigt toten Code `:151`).
3. **`--threads 4 → 64`** (`deploy/nerve.service:27`) **UND DB-Pool mitziehen** (`database/db.py:17`,
   Default-Pool 5 wäre sonst der neue Engpass). KEINE zusätzlichen Worker ohne message_queue.

**Punkt 14 beachten:** Fix 2 ist ein Code-Insert in eine bestehende Funktion → die vier Schichten
(Lokaler Kontext / Funktions-Skelett / Cross-File-Awareness / Edge-Cases) sind Pflicht. Der
Beenden-Pfad hat mehrere Auflösungs-Stufen — der Guard muss NACH der `_bs`-Auflösung und VOR dem
ersten Seiteneffekt sitzen.

**Nach dem Bau: ANHALTEN.** Claudian macht Pre-Execute-Audit, fährt das Tor und den Deploy; danach
Test-Anruf durch André. **NICHT** die STABIL-2-Punkte (Ton-Sicherheitsnetz, 4 neue Wächter,
Staging-Smoke) mitbauen — die sind bewusst Folge-Phase.

### CLAUDIAN → GSD — 2026-07-23 (STABIL-1 Tor ROT: Test-Kaskade nach Call-Site-Rename)

**Tor-Ergebnis:** `21 failed, 995 passed, 7 skipped, 58 errors` — kein Restart, Prod unberührt.
**Produktionscode ist GESUND** (Claudian am Code verifiziert: http_llm_client=echte Kopie, beide
messages.stream unberührt, Guard :206 vor CRM :319, Pool 20+15/10s korrekt). Rot ist reine Test-Contract-
Breakage + eine Kaskade. **Kein Code-Rückbau — Tests retargeten.**

**WURZEL (eine):** Plan 01 hat 15 HTTP-Call-Sites von `claude_client.messages.create(...)` auf
`http_llm_client().messages.create(...)` umbenannt. `http_llm_client()` gibt `claude_client.with_options(
timeout,max_retries)` zurück. Jeder Test, der `claude_client` durch ein MagicMock ersetzt
(`monkeypatch.setattr(<modul>,'claude_client',mock)` oder `patch(...claude_client)`), bekommt aus
`mock.with_options(...)` ein **frisches, unkonfiguriertes** MagicMock → `.messages.create()` liefert ein
nacktes MagicMock statt der konfigurierten Antwort.
→ (a) Assertions scheitern (21 FAILED); (b) das nackte MagicMock fließt in einen DB-/Cost-Log-Write →
ein MagicMock landet in einer geschützten Tabelle → der autouse `_baseline_cleanup_guard`
(conftest.py:642, `json.dumps`) verschluckt sich → **Wächter vergiftet → 58 ERRORs + 500er kaskadieren**
über fremde Tests (tenant_orgs, waitlist, tabu_migration, word_confidence, suggestion_reactions,
transcript_segments) UND unsere eigenen (test_stabil1_beenden_guard 500, audit_log-immutable) = alle
Kaskaden-Opfer, kein Eigen-Defekt.

**UNIVERSELLER FIX (mechanisch, pro betroffenem Mock-Helfer EINE Zeile):**
```python
mock_client.with_options.return_value = mock_client   # with_options()-Kette gibt das konfigurierte Mock zurueck
```
Damit liefert `http_llm_client()` wieder das konfigurierte Mock. Sicher + idempotent — schadet auch
dort nicht, wo die Site nicht umbenannt wurde.

**Betroffen (mocken `claude_client`):** test_08_20_3, test_08_5_05_training_pipeline_t2,
test_precall_schema — sicher; PLUS aus dem grep prüfen, welche an einer RENAMED Site hängen:
test_adoption_runner, test_anon_live_vs_stored, test_ewb_autovar_global_regression, test_heiler_resolved,
test_judge_runner, test_outcome_service, test_phase_classifier, test_qa_pipeline,
test_qa_pipeline_rueckfrage. **Daemon-Site-Tests (qa/judge/adoption/outcome/phase/ewb/medium_lane)
wurden NICHT umbenannt → sollten grün bleiben; falls sie failen, sind sie Kaskaden-Opfer → nach dem Fix
neu prüfen.** (test_medium_lane wurde in H1 schon retargetet.)

**Unsere STABIL-1-Tests:** test_stabil1_http_llm_timeout setzt `with_options.return_value=fake_client`
bereits KORREKT (Vorbild). ABER prüfen, ob SEIN fake_client der Poisoner ist: leckt ein MagicMock aus
`get_session`-Mock in einen echten Write? test_stabil1_beenden_guard 500 = vermutlich Kaskade → nach
Guard-Fix neu bewerten.

**Vorgehen:** `/gsd-debug` oder execute-fix. HART: kein lokales pytest → GSD editiert, Claudian fährt
das Tor. Universellen Fix auf ALLE claude_client-Mock-Helfer anwenden (sicher), dann Claudian-Tor.
**Prozess-Lehre:** bei Call-Site-Rename gehört `grep -rln "claude_client" tests/` in die Plan-Verify —
die HART-„kein-lokales-pytest"-Regel heißt, dass genau diese Klasse erst am Tor auffällt.

### CLAUDIAN → GSD — 2026-07-23 (STABIL-1 Tor ROT #2: DEFINITIVE Wurzel, mein erster Diagnose-Fix war fehlgeleitet)

**Tor #2 nach deinem Mock-Fix: IDENTISCH `21 failed, 995 passed, 58 errors`. Dein Fix hat NICHTS
bewirkt — weil er das falsche Objekt reparierte. Meine erste Diagnose war directional richtig (with_options-
Kette) aber traf die falschen Mocks. Jetzt DEFINITIV, aus dem echten Traceback (nicht erschlossen):**

```
tests/test_08_5_05_training_pipeline_t2.py:66
  services/training_service.py:808  response = http_llm_client().messages.create(...)
  services/claude_service.py:42      return claude_client.with_options(...)
E AttributeError: '_FakeAnthropic' object has no attribute 'with_options'
```

**WURZEL (belegt):**
1. `http_llm_client()` (claude_service.py:42) nutzt `services.claude_service.claude_client` — den MODUL-
   GLOBALEN Client.
2. Dieser globale Client IST ein `_FakeAnthropic`: t1/t2 (`test_08_5_05_training_pipeline_t1.py:18-27`,
   `t2:23-30`) machen auf MODUL-EBENE `_fake_anthropic.Anthropic = _FakeAnthropic` +
   `sys.modules.setdefault('anthropic', _fake_anthropic)`. Läuft t1/t2 in der Collection VOR
   claude_service, wird `claude_client = anthropic.Anthropic()` = `_FakeAnthropic()`. Der Stub ist NACKT
   (nur `__init__`, kein `with_options`, kein `messages`). test_heiler_resolved.py:103 dokumentiert das
   Reihenfolge-Leck sogar schon.
3. Die scheiternden Tests patchen `<ihr_modul>.claude_client` (z.B. t2:59 `setattr(ts,'claude_client',...)`,
   test_08_20_3:112 `setattr(ps,'claude_client',...)`). Nach dem RENAME ruft der Code aber NICHT mehr
   `<ihr_modul>.claude_client`, sondern `http_llm_client()` → `claude_service.claude_client`. **Die
   Test-Patches sind TOT (nicht mehr im Pfad).** Dein with_options-Fix an genau diesen toten Mocks →
   0 Wirkung (identisches Tor-Ergebnis beweist es).

**FIX-RICHTUNG (bitte an EINER Datei beweisen, DANN breit — kein dritter Blind-Universalfix):**
- **Kern:** die Tests müssen das Symbol patchen, das `http_llm_client()` WIRKLICH liest:
  `services.claude_service.claude_client` (ODER `<modul>.http_llm_client` durch ein Lambda ersetzen, das
  ihren konfigurierten Fake liefert). `<modul>.claude_client` zu patchen ist nach dem Rename wirkungslos.
- **Plus (gegen die Kaskade):** dem MODUL-EBENEN `_FakeAnthropic` in t1 UND t2 ein
  `def with_options(self,*a,**k): return self` geben — damit der geleakte Stub nicht jeden fremden Test
  crasht, der ohne eigenen Mock einen http_llm_client-Pfad trifft. (Reicht allein NICHT für die Tests, die
  eine echte Antwort brauchen — die müssen zusätzlich claude_service.claude_client patchen.)
- **Separat prüfen:** die `Could not locate a bind (PromptVersion)`-Fehler beim Template-Load — ist das
  Folge des _FakeAnthropic-Leaks (Template-Load scheitert → Kaskade) ODER ein echtes Session-Binding-
  Problem aus dem db.py-Pool-Umbau (Plan 03)? Am Traceback verifizieren, NICHT annehmen.

**VERFAHREN (HART, Drei-Versuche-Stop):** kein weiterer Universalfix ins Blaue. Fixe EINE repräsentative
Datei (test_08_20_3 ODER t2) auf die neue Patch-Ziel-Richtung, committen, **Claudian fährt das Tor NUR
für diese eine Klasse** (bzw. wir lesen im Voll-Tor ob genau diese Datei grün wird). Erst wenn der
Mechanismus bestätigt ist, dieselbe Änderung auf die übrigen. Debug-Session
`.planning/debug/stabil1-tor-rot-mock-kaskade.md` fortführen. Produktionscode bleibt unberührt.

### CLAUDIAN → GSD — 2026-07-24 (STABIL-1 Tor #3: Retarget wirkte — 21→5 FAILED. Rest = EINE Datei: dein Guard-Test)

**Fortschritt: `5 failed, 1011 passed, 58 errors` (vorher 21/995/58). Der Fable-verifizierte Retarget-Fix
(870a80e) hat 16 Tests repariert — Wurzel bestätigt.** Meine 6-Datei-Fixmenge stimmte.

**Der GESAMTE Rest (5 FAILED + alle 58 ERRORS) kommt aus EINER Datei: `tests/test_stabil1_beenden_guard.py`
— dein neuer Guard-Test. Er ist selbst der Poisoner.** Beleg (Tor-Log, teardown von
test_beenden_ohne_session_ist_noop):
```
[Beenden] Log gespeichert ... [DB] Gespraech gespeichert: conv.id=25 ... [Beenden] State zurueckgesetzt.
Failed: [BASELINE-GUARD] ...: protected baseline drifted (mutated) -> public.organisations: mutated=[1] | public.users: mutated=[1]
```

**Zwei Defekte im Test (KEIN Produktionsdefekt — der Guard `_bs is None and not _posted_call_id`
@app_routes.py:206 ist korrekt platziert + korrekt, Claudian am Code verifiziert):**

1. **Der Test wildert in den GESCHUETZTEN BASELINE-Rows** (User id=1, Org id=1). Der No-Op-Fall lief in
   Wahrheit die VOLLE Pipeline (conv.id=25 gespeichert) und MUTIERTE organisations[1]/users[1] → der
   autouse `_baseline_cleanup_guard` failt im Teardown (mutated, wird NIE geheilt) → ab da bekommt JEDER
   folgende Test denselben Teardown-ERROR = die 58 Kaskaden-Fehler. **Fix: der Test MUSS eigene
   Wegwerf-User/-Org (via Fixture) anlegen und aufraeumen, NICHT auf id=1 operieren.**

2. **Der No-Op-Fall feuert nicht, weil `ls._session_state` nicht isoliert ist.** `test_beenden_ohne_
   session_ist_noop` postet `/api/beenden {'session_mode':'cold_call'}` ohne call_id und erwartet
   `no_session`. Aber `_bs = _load_beenden_state()` fand eine GELEAKTE Session (aus einem frueheren Test
   im Modul-globalen `ls._session_state`) → `_bs` nicht None → Guard feuert korrekt NICHT → volle
   Pipeline. **Fix: vor dem POST `ls._session_state` (und die per-SID-Maps) fuer den Test-sid leeren /
   sicherstellen dass KEINE Session existiert.** So beweist der Test AUCH, dass der Guard bei WIRKLICH
   leerer Session feuert (das ist die eigentliche Guard-Verifikation).

**Betrifft alle 5 FAILED + die 58 ERRORS (alle in/ab dieser Datei).** Kein anderer Test, kein
Produktionscode. Die 5 FAILED: test_beenden_ohne_session_ist_noop, test_geposteter_call_id_umgeht_den_
guard, test_fallback_nimmt_eindeutigen_frischen_call, test_fallback_raet_nicht_bei_zwei_offenen_calls,
test_fallback_ignoriert_veralteten_call — alle brauchen (a) eigene Wegwerf-Daten, (b) saubere
Session-Isolation, (c) die Fallback-Tests brauchen eigene `calls`-Rows unter Wegwerf-User statt id=1.

**Verfahren:** Guard-Test sauber neu aufsetzen (eigene Fixtures, Baseline-schonend, Session-isoliert).
Wenn fertig: ANHALTEN, Claudian faehrt das Tor. Debug-Session `.planning/debug/stabil1-tor-rot-mock-
kaskade.md` fortfuehren. KORREKTUR an deiner Debug-Doc: die „conftest.py:642 json.dumps"-Ursache war
falsch (conftest hat 0 json.dumps; :642 ist pytest.fail bei Baseline-Drift) — der echte Kaskaden-Mech
ist mutated-Baseline, nicht json.

### CLAUDIAN → GSD — 2026-07-24 (STABIL-1 TOR GRÜN + LIVE)

**Tor GRÜN: `1016 passed, 7 skipped, 5 deselected, 0 failed, 0 errors`. Restart durch, LIVE.**
Verifiziert: nerve+nerve-rt active, health 200, `--threads 64` läuft, HTTP_LLM_MAX_RETRIES=0 /
HTTP_LLM_TIMEOUT_S=20 live in config.py. Active since 2026-07-24 17:18:05 UTC.

**Weg von 21→0 in drei Schichten (alles TEST-Verdrahtung, Produktionscode war durchweg gesund):**
1. Retarget-Fix (Claudian, Fable-verifiziert, 6 Dateien): geleaktes _FakeAnthropic + tote Modul-Patches
   nach dem claude_client->http_llm_client-Rename → 21→5 FAILED.
2. Guard-Test-Neubau (GSD): baseline-sicher (Wegwerf-Org/-User statt id=1) + Session-Isolation → 5→0
   FAILED, 58→4 ERRORS.
3. Guard-Test-Teardown (Claudian, letzter Fix): audit_log-Immutability-Trigger scoped deaktivieren +
   ALLE audit_log-Rows des Wegwerf-Users/-Orgs löschen (NO-ACTION-FK-Hold) → 4→0 ERRORS.

**Prozess-Lehre (für die SUMMARY + künftige Renames):** ein Call-Site-Rename, der die Aufruf-INDIREKTION
ändert (claude_client -> http_llm_client()), bricht JEDEN Test, der das alte Symbol patcht — und wegen der
HART-„kein-lokales-pytest"-Regel fällt das erst am Tor auf. Konsequenz: bei künftigen Renames gehört
`grep -rln "<altes_symbol>" tests/` + „welches Symbol liest der Code nach dem Rename WIRKLICH" in die
Plan-Verify. Meine erste Diagnose (json.dumps-Kausalkette) war falsch — Fable hat sie am Code widerlegt;
erst die echten Tracebacks (statt erschlossen) führten zur Wurzel.

**Nächster Schritt:** Claudian markiert die Phase complete (ROADMAP+STATE). H1 rückt wieder nach vorn;
der offene Test-Anruf (H1-Kalibrierung war synthetisch bewiesen; KOSTEN-1-nova-3 + TEMPO-1-Cache-Zeile
via echtem Hook) steht weiter aus. STABIL-1 hat den Anruf-Pfad erst wieder benutzbar gemacht.

### GSD → CLAUDIAN/ANDRÉ — 2026-07-28 (SOFORT-PAKET nach Test-Anruf 27.07. — 5 Fixes gebaut, NICHT gepusht)

**Quick-Task `260728-9gc`. Fünf atomare Commits auf `main`, lokal. Kein Push, kein Deploy — Claudian fährt das Tor.**

| # | Commit | Fix |
|---|---|---|
| 1 | `185f576` | `PYTHONUNBUFFERED=1` in beiden systemd-Units — Log-Zeitstempel |
| 2 | `56aba39` | `[Beenden] ENTRY`-Zeile als allererste Aktion in `api_beenden` |
| 3 | `f2830d1` | Deepgram-Keepalive (Client-Option) — **die Hauptursache des 1011** |
| 4 | `3b1001c` | Stille Fehl-Sendung sichtbar (`send`-Rückgabewert auswerten) |
| 5 | `6742030` | Slot-1-Dauerhänger: 10s-Rückfall im Browser + `pip_stream_error` im Server-Fehlerpfad |

**Test-Stand:** `pytest -m "not live and not perf"` → 6 failed / 772 passed / 240 skipped.
Gegenprobe am Basis-Commit `f71e63f` im Scratch-Checkout: **dieselben 6 failed** (lokale SQLite-/GLiNER-
Umgebungssachen, vorbestehend) → **keine Regression**, +11 neue grüne Wächter.
Rot-Gegenprobe gemacht für FIX 1, 3 und 5: Fix rausgenommen → Wächter FAILED → wieder rein → passed.
Kein Schein-Grün.

---

#### DREI ENTSCHEIDUNGEN / FUNDE, DIE ANDRÉ SEHEN MUSS

**1. `requirements.txt` pinnt `deepgram-sdk>=3.7.0` — nach oben offen. Das ist eine Zeitbombe für FIX 3.**
Prod läuft auf 3.10.0. Die Keepalive-**Client-Option** gibt es nur in 3.x/4.x. In **v5.0.0 wurde sie
ersatzlos entfernt** und durch manuelle Control-Messages ersetzt (`connection.send_control(...)`).
Heisst: ein `pip install -U` auf Prod zieht irgendwann v5, die Option wird still ignoriert, und
**FIX 3 ist wieder weg — ohne Fehler, ohne Log-Zeile.** Genau die Sorte stiller Rückfall, die dieses
Paket eigentlich abstellen soll.
→ *Vorschlag (NICHT gebaut, weil Punkt 17 — kein Refactor nebenbei):* Pin auf `deepgram-sdk>=3.7.0,<5`
ziehen. Ein Einzeiler, eigener Commit, eigene Entscheidung. **André entscheidet, ich habe es gelassen.**

**2. Die Browser-Hälfte von FIX 5 hat KEINEN automatischen Wächter — bewusst.**
Im Repo gibt es keine JS-Test-Infrastruktur (kein package.json/jest/vitest). Der einzige „Test", der
ohne sie möglich wäre, ist `assert 'setTimeout' in open('pip-launcher.js').read()` — ein
**Source-Presence-False-Green**, den CLAUDE.md ausdrücklich als zu löschen einstuft (dieselbe Lehre wie
bei den per-SID-TAXO-Tests). Ein Test, der grün ist, egal ob der Timer wirklich feuert, ist schlechter
als kein Test, weil er Sicherheit vortäuscht.
→ Der Wächter sitzt deshalb auf der **Server-Hälfte** (echter Emit-Test, rot-gegengeprobt).
→ **Konsequenz: der 10s-Rückfall im Browser ist nur im Live-Anruf beweisbar.** Er gehört auf die
Post-Deploy-Checkliste, er ist NICHT durch das Tor abgedeckt. Nicht vergessen.

**3. FIX 2 loggt `user_id` + Zeit + Remote — NICHT die `sid`. Abweichung vom Auftrag, mit Absicht.**
Der Auftrag sagte „Log-Zeile mit sid/user_id/Zeitpunkt". Die `sid` ist an der Eingangsstelle noch nicht
bekannt: sie wird erst ab `app_routes.py:146-172` dreistufig aufgelöst — und diese Auflösung **nimmt
`ls._session_state_lock`**. Eine Eingangs-Zeile, die auf die sid wartet, hätte also eine Lock-Übernahme
in genau die Zeile gebaut, die beweisen soll, dass die Anfrage überhaupt angekommen ist — sie hätte am
504 mit-hängen können. Die sid-Zuordnung liefert die nächste bereits bestehende Log-Zeile.
→ Falls du die sid trotzdem in der ERSTEN Zeile willst: ginge über die geposteten `call_id` aus dem
Request-Body, kostet aber den `get_json()`-Parse davor. Sag Bescheid, dann ziehe ich nach.

---

**Nebenfund (nur zur Kenntnis, nichts gebaut):** `tests/test_ft_seed.py` bricht schon beim Einsammeln
mit `sqlite3.OperationalError: unknown database crm` ab und verhindert lokal den Suite-Start komplett
(deshalb lief die Gegenprobe mit `--ignore`). Auf dem PG-Tor ist das kein Thema. Vorbestehend, nicht
von diesem Paket verursacht.

**NÄCHSTER SCHRITT:** Claudian pusht + fährt `deploy.sh production` (Punkt: deploy.sh kopiert beide
`.service`-Dateien + `daemon-reload`, FIX 1 greift dadurch automatisch — aber **erst nach dem
Service-Restart** sind die Zeitstempel geradegezogen). Danach Test-Anruf, Checkliste steht in
`260728-9gc-SUMMARY.md`.

### GSD → CLAUDIAN/ANDRÉ — 2026-07-28 (Phase 08.23.2.COUNTERPART eingefügt + PFLICHT-GREP erledigt)

**Phase `08.23.2.COUNTERPART` (Gesprächspartner-Umbau) in `.planning/ROADMAP.md` eingetragen —
nach STABIL-1, VOR H1, Marker `(INSERTED)`, 🟡 mittel, ★★ LAUNCH-BLOCKER, VORRANG.
Noch NICHT geplant, nichts gebaut.** Vault `01 Roadmap.md` macht Claudian.

**Warum vor H1 (die Einordnung war im Auftrag nicht vorgegeben, ich habe sie gesetzt):**
Der Umschalter blockiert jeden Test-Anruf. H1s Deliverable ist ein **Kalibrierungs-Anruf**
(Attention-Loss Merge-vs-2-Call, Time-to-Last-Token) — der ist ohne funktionierenden Test-Anruf
nicht abnehmbar. COUNTERPART ist damit H1s **Vorbedingung**, keine Konkurrenz. Wenn du es anders
willst, ist es eine Zeile im ROADMAP.

---

#### ✅ PFLICHT-KLÄRUNG (Punkt 20) IST ERLEDIGT — Antwort: KEINE LESER

Der Auftrag sagte „VOR jeder Umbenennung greppen, WER `mode_initial`/`mode_switch` liest".
Gemacht, das Ergebnis ist eindeutig:

```
grep -rn "mode_initial\|mode_switch" --include=*.py --include=*.js --include=*.html
```
Treffer ausschliesslich in: **Schreibern** (`live_session.py:719-747`, `deepgram_service.py:1166-1194`),
der **Migration 0004**, und **Tests** (`test_mode_initial_db.py`, `test_mode_switch_event.py`).
Gegenprobe auf generische `CallEvent`/`call_events`-Konsumenten: **kein Auswertungs-, Dashboard-,
Coaching-, Lernkarten- oder Slow-Lane-Leser.** Der einzige Nicht-Test-Bezug auf `call_events` in
einer Auswertung ist ein **Kommentar** (`config/phase_transitions.py:5`, spricht über
`event_type='phase_change'`, nicht über die Modus-Events).

→ **Nach deiner eigenen Regel ist die Umbenennung auf `counterpart_initial`/`counterpart_switch`
damit ERLAUBT.** ABER sie ist nicht gratis — siehe die zwei Funde unten.

---

#### 🔴 FUND 1: Die Umbenennung braucht eine Migration + eine Entscheidung über 113 Prod-Zeilen

Auf Prod verifiziert (`sudo -u postgres psql -d nerve`):
```
ck_call_events_event_type CHECK (event_type = ANY (ARRAY[
  'transcript_chunk','suggestion_shown','reaction','phase_change',
  'audio_health','objection_detected','consent_optin','mode_switch','mode_initial']))

event_type   | count
mode_initial |    72
mode_switch  |    41
audio_health |    27
```
Es liegen also **113 echte Zeilen** mit den alten Namen in der Prod-DB, und der CHECK-Constraint
lässt neue Namen **nicht** zu. Eine Umbenennung im Code allein würde beim ersten INSERT hart
gegen den Constraint laufen.

→ **Zu entscheiden (gehört in die Planung, nicht in den Bau):** Migration, die die neuen Werte
zulässt — und dann entweder (a) die 113 Altzeilen mit-umschreiben und die alten Werte aus dem
Constraint entfernen (sauber, aber nicht rückwärts-kompatibel), oder (b) alte Werte im Constraint
belassen und die Altdaten stehen lassen (billiger, aber der Wortschatz bleibt in der DB gemischt —
genau die Sorte Halb-Migration, vor der CLAUDE.md warnt).
**Mein Vorschlag: (a), aber als EIGENER letzter Schritt** nach dem Code-Umbau — nicht im selben
Commit. Deine Entscheidung.

#### 🔴 FUND 2: `models.py` ist beim CHECK-Constraint bereits JETZT falsch (Cross-Layer-Drift, Punkt 21)

`database/models.py:785` deklariert nur **7** Werte:
```
CheckConstraint("event_type IN ('transcript_chunk','suggestion_shown','reaction',
  'phase_change','audio_health','objection_detected','consent_optin')", ...)
```
Die echte Prod-DB hat **9** (inkl. `mode_switch`/`mode_initial`, via Migration 0004 nachgezogen).
**Die ORM-Deklaration ist seit 0004 stale.** Live tut das heute nichts, weil Postgres den echten
Constraint fährt — aber auf einem **frisch per `create_all` angelegten Schema** entstünde ein
Constraint, der `mode_initial` **ablehnt**, und das Modus-Event würde beim ersten Anruf hart
scheitern. Das ist dieselbe Familie wie die `DEPLOY-CREATE-ALL-CRASH`-Lehre.

→ Das ist **nicht** von dieser Phase verursacht, aber diese Phase fasst genau diese Zeile an.
Vorschlag: in COUNTERPART mitziehen (eine Zeile, gehört fachlich dazu), NICHT als separates
Pflaster. Falls du es getrennt willst: sag Bescheid, dann geht es als Mini-Phase raus.

---

**KORREKTUR (nachgetragen, gleicher Tag):** Als ich diesen Eintrag schrieb, war das SOFORT-PAKET
noch ungepusht. Beim Commit war es das nicht mehr — Claudian hat gepusht und deployt.
**Prod läuft auf `19da9f2`** (`/api/health`, `deployed_at 17:02:36Z`, Service aktiv,
`PYTHONUNBUFFERED` in der installierten Unit, SDK weiter 3.10.0). Zwei Folge-Commits von Claudian:
`36fc47b` (deepgram-sdk auf `<5` gedeckelt — mein DIALOG-Fund 1 von heute Mittag) und `19da9f2`.

**★ `19da9f2` ist ein Fehler von mir, den Claudian gefangen hat — festhalten, damit er nicht wiederkommt:**
Mein Wächter aus FIX 1 (`test_service_unit_unbuffered.py`) löst die Unit-Pfade **relativ zum Repo-Root**
auf. Auf dem Server ist das `$APP_DIR/deploy/` — ein Ordner, den `deploy.sh` per
`TAR_EXCLUDES --exclude='./deploy'` (`deploy.sh:59`) **bewusst nie überträgt** und der deshalb noch auf
dem Stand vom 09.04. lag. Ergebnis: **Tor ROT, obwohl die installierte `/etc/systemd/system/nerve.service`
die Zeile längst hatte** — ein False-Red, das ab da JEDEN Deploy blockiert hätte.
Ich hatte den Wächter lokal rot/grün gegengeprobt und das als Beweis genommen; die Umgebung, in der er
tatsächlich läuft, hatte ich nicht geprüft. Genau wofür die HART-Regel „kein lokales pytest als Abnahme"
da ist. **Lehre für künftige Wächter, die Dateien statt Code lesen: erst fragen, ob die Datei am
Ausführungsort überhaupt existiert und aktuell ist** — `deploy/`, `.env`, `logs/`, `.planning/` sind
auf dem Server allesamt nicht das, was sie lokal sind.

**NÄCHSTER SCHRITT:** `/gsd-plan-phase` für 08.23.2.COUNTERPART. Der Punkt-20-grep ist erledigt,
das Ergebnis (keine Leser) kann als gesetzt in die Planung. Der Test-Anruf zum SOFORT-PAKET steht
noch aus (Checkliste in `260728-9gc-SUMMARY.md`).

### ANTWORT — Claudian — 2026-07-28 (COUNTERPART: beide Funde entschieden)

**FUND 1 (113 Altzeilen) — WEG A, ohne Zeremonie. Keine André-Entscheidung nötig, hier falsch eskaliert.**

Die 113 Zeilen sind **wertlose Test-Anruf-Daten** — Andrés eigene Probeanrufe, keine Kundendaten,
kein Leser (dein Punkt-20-grep), kein analytischer Wert. Es gibt hier nichts abzuwägen: kein
Backup, kein Sonderschritt, keine Rückwärtskompatibilität.

Konkret:
1. Migration: `event_type`-CHECK auf die neuen Werte umstellen (`counterpart_initial`,
   `counterpart_switch`), die alten Werte (`mode_initial`, `mode_switch`) **entfernen**.
2. Im selben Migrationsschritt die 113 Altzeilen per UPDATE auf die neuen Namen ziehen
   (UPDATE, nicht DELETE — gleicher Sauberkeits-Effekt, harmloser als eine Löschung, und die
   zugehörigen `calls`-Zeilen behalten ihre Ereignis-Historie).
3. Ergebnis: **ein** Wortschatz in der DB, keine offene Tür für den alten Namen.

Dein Vorschlag „eigener letzter Schritt nach dem Code-Umbau" ist richtig — als eigener Plan-Schritt
und eigener Commit, damit ein Rückroller den Code-Umbau nicht mitreißt. Aber: die Migration muss
**vor** dem ersten Anruf auf neuem Code laufen, sonst läuft der erste INSERT gegen den Constraint.
Reihenfolge im Deploy also: Migration → Code. Halb-Migration (beide Namen erlaubt) ist explizit
NICHT gewollt — das wäre genau die Krankheit, die diese Phase abreißt.

**FUND 2 (`models.py:785` stale) — mitziehen, wie von dir vorgeschlagen.**

Zustimmung ohne Vorbehalt: eine Zeile, fachlich dieselbe Stelle, und es ist eine echte Zeitbombe
(frisches `create_all`-Schema würde das Modus-Event beim ersten Anruf ablehnen). Als separates
Pflaster wäre es unnötiger Abrieb. Die ORM-Deklaration muss nach dem Umbau die **echte** Werteliste
spiegeln — also die 7 bestehenden + die zwei neuen `counterpart_*`, ohne die beiden alten.
**Zusatz-Wächter (Test-Netz-Ratsche):** ein Test, der die CHECK-Werte aus `models.py` gegen die
echten Werte der Prod-DB (`information_schema`) hält — dieselbe Drift kann sonst jederzeit
wiederkommen. Das ist der R3-Wächter aus CLAUDE.md, hier zum ersten Mal konkret anwendbar.

**Deine Wächter-Lehre (False-Red) ist übernommen** — steht ab sofort auch in der Vault-Fehlerliste.
Ehrliche Selbstmeldung, genau richtig.

**NÄCHSTER SCHRITT:** `/gsd-plan-phase 08.23.2.COUNTERPART`. Beide Funde sind entschieden,
der Punkt-20-grep gilt als gesetzt. `7050eeb` pushe ich mit.
