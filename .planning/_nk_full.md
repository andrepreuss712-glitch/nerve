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

## DER ZU PRUEFENDE CODE — VOLLSTAENDIG (services/coaching_service.py, 519 Zeilen gesamt)

```python

### TEIL A - Modul-Kopf + Verwendungsstelle (Zeilen 3-75)
   3  import threading
   4  from datetime import datetime, timezone
   5  from contextlib import contextmanager
   6  import config
   7  from services.claude_service import claude_client, http_llm_client
   8  
   9  _conv_locks = {}                       # conv_id(str) -> [threading.Lock, Nehmer-Zaehler]
  10  _conv_locks_guard = threading.Lock()   # schuetzt NUR die Ablage; NIE ueber einem Netz-Aufruf
  11  
  12  POSTCALL_PROMPT = """Du bist ein erfahrener Sales-Coach. Analysiere dieses Verkaufsgespraech und schlage exakt 3 Lernkarten vor.
  13  
  14  Gespraechsdaten:
  15  - Einwaende: {einwaende}
  16  - Kaufsignale: {kaufsignale}
  17  - Painpoints: {painpoints}
  18  - Kaufbereitschaft: Start {kb_start}% -> Ende {kb_end}%
  19  - Redeanteil Berater: {redeanteil_berater}% / Kunde: {redeanteil_kunde}%
  20  - Dauer: {dauer_sek} Sekunden
  21  - Skript-Abdeckung: {skript_abdeckung}%
  22  - Gegenargument-Details: {ga_details}
  23  
  24  Priorisierung (per D-03):
  25  1. Fehler der den Abschluss direkt verhindert hat
  26  2. Haeufigster Fehler im Call
  27  3. Kleinste Verbesserung mit groesster Wirkung
  28  
  29  WICHTIG: Jeder Vorschlag MUSS ein konkreter Satz sein, den der Vertriebler beim naechsten Call woertlich sagen kann. KEINE generischen Tipps wie "Vertiefen Sie Einwaende".
  30  
  31  Beispiel guter Vorschlag:
  32  "Wenn der Kunde sagt 'Das ist zu teuer' - antworte mit: 'Im Vergleich wozu meinen Sie das?' und schweig dann."
  33  
  34  Antworte als JSON mit exakt diesem Format:
  35  {{
  36    "vorschlaege": [
  37      {{
  38        "category": "einwand_preis",
  39        "original_suggestion": "Wenn der Kunde sagt...",
  40        "alternative_1": "Alternative Formulierung 1...",
  41        "alternative_2": "Alternative Formulierung 2...",
  42        "lernziel": "Einwaende vertiefen statt direkt kontern"
  43      }},
  44      ...
  45    ]
  46  }}
  47  
  48  Genau 3 Vorschlaege. Jeder mit 2 Alternativen (fuer "Neuer Vorschlag" per D-06, pre-generated to avoid extra Sonnet calls). Categories aus: einwand_preis, einwand_zeit, einwand_wettbewerb, einwand_bedarf, einwand_entscheider, zu_frueh_pitch, redeanteil, kaufsignal_verpasst, abschluss_timing, phasen_sprung."""
  49  
  50  
  51  def generate_postcall_analysis(conv_id, user_id, einwaende, painpoints,
  52                                  kb_start, kb_end, redeanteil_berater,
  53                                  redeanteil_kunde, dauer_sek,
  54                                  skript_abdeckung, ga_details,
  55                                  kaufsignale=None, profile_data=None):
  56      """Generate max 3 learning card suggestions via Sonnet (D-01, D-02).
  57  
  58      T-04.11-05: Guard against duplicate analysis — check if suggestions
  59      already exist for this conv_id before calling Sonnet.
  60      """
  61      with _analysis_lock_for(conv_id):
  62          # T-04.11-05: Duplicate guard — one analysis per conversation
  63          from database.db import get_session
  64          from database.models import LearningCard
  65          db_check = get_session()
  66          try:
  67              existing = db_check.query(LearningCard).filter_by(call_id=conv_id).count()
  68              if existing > 0:
  69                  print(f"[Coach] Suggestions already exist for conv_id={conv_id}, skipping Sonnet call")
  70                  return []
  71          finally:
  72              db_check.close()
  73  
  74          prompt_text = POSTCALL_PROMPT.format(
  75              einwaende=json.dumps(einwaende, ensure_ascii=False)[:2000],

### TEIL B - die Riegel-Fabrik selbst (Zeilen 485-520)
 485  # _conv_locks_guard wird AUSSCHLIESSLICH fuer Dict-Operationen gehalten: kein
 486  # get_session, kein messages.create, kein sleep, kein emit. (Dieselbe Bau-Vorschrift,
 487  # die tests/test_session_lock_blocking_calls_guard.py:158-166 fuer _session_state_lock
 488  # durchsetzt.)
 489  @contextmanager
 490  def _analysis_lock_for(conv_id):
 491      """Riegel pro conv_id. Duplikatschutz identisch stark, verschiedene Anrufe
 492      blockieren sich nicht mehr.
 493  
 494      key = str(conv_id): routes/learning.py:23, :211 und :383 lesen conv_id OHNE Cast aus
 495      dem JSON — 5 und "5" bekaemen sonst VERSCHIEDENE Riegel, obwohl
 496      filter_by(call_id=...) in Postgres denselben Datensatz meint. Kein Sonderfall fuer
 497      None/falsy: None wird zu 'None' und teilt sich einen Riegel. Fail-safe Richtung —
 498      mehr Serialisierung, nie weniger Schutz.
 499      """
 500      key = str(conv_id)
 501      with _conv_locks_guard:                   # (1) holen/anlegen + Zaehler HOCH
 502          eintrag = _conv_locks.get(key)        #     HOCH vor acquire(): sonst koennte
 503          if eintrag is None:                   #     ein Wartender wegge-raeumt werden
 504              eintrag = [threading.Lock(), 0]   #     und ein Dritter legte einen ZWEITEN
 505              _conv_locks[key] = eintrag        #     Riegel unter demselben Key an
 506          eintrag[1] += 1
 507      riegel = eintrag[0]
 508      erworben = False
 509      try:
 510          riegel.acquire()                      # (2) warten AUSSERHALB des Ablage-Riegels
 511          erworben = True                       #     acquire() liegt IM try: wirft es
 512          yield                                 #     (Signal/Abbruch), raeumt das finally
 513      finally:                                  #     den Zaehler trotzdem wieder ab
 514          if erworben:
 515              riegel.release()                  # (3) erst freigeben ...
 516          with _conv_locks_guard:               # (4) ... dann Zaehler RUNTER, unter der
 517              eintrag[1] -= 1                   #     Ablage: '-= 1' und '== 0' sind sonst
 518              if eintrag[1] == 0 and _conv_locks.get(key) is eintrag:
 519                  del _conv_locks[key]          #     nicht atomar zueinander
 520  
```
