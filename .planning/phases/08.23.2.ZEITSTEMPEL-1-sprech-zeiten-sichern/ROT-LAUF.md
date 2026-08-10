# ROT-LAUF — Phase 08.23.2.ZEITSTEMPEL-1 (Plan 02)

**Gezogen:** 2026-08-10, `bash deploy.sh production` (Andre, deploy.sh ist agenten-gesperrt)
**Stand:** HEAD `9b3a190` — ROT-Netz aus Plan 01, **kein** Produktionscode, **kein** Schema
**Ergebnis:** Tor ROT -> **kein Restart, kein Deploy**, Production laeuft unveraendert weiter

Dieser Lauf ist ein **Abnahme-Artefakt** (Bau-Regel 1, Punkt 31), kein Nebenprodukt.
Ohne ihn waere das spaetere GRUEN wertlos.

---

## Zwei Laeufe — der erste war blind

| Lauf | Ergebnis | Aussagekraft |
|---|---|---|
| 14:15 | `5 deselected, 13 warnings, 1 error in 12.50s` — `Interrupted: 1 error during collection` | **blind.** Der Modul-Import von `_extract_word_times` war ein Collection-Error; pytest brach den GESAMTEN Lauf ab. Zwei der drei ROT-Netze und die ~1140 Bestandstests liefen **nie**. |
| 14:24 | **16 FAILED, 0 ERROR**, Suite bis 100 % durchgelaufen | **gueltig.** Alle drei Netze rot, jedes aus seinem eigenen Grund. |

Der Fix dazwischen: Import in den Testkoerper (Commit `9b3a190`). Punkt 31 in Reinform —
**ein Abbruch VOR dem Pruefkatalog beweist nichts ueber das, was im Katalog steht.**

Ein Lauf mit `ERROR ... during collection` ist ab jetzt **kein gueltiger ROT-Beleg** mehr.

---

## Soll/Ist — jedes Netz aus dem RICHTIGEN Grund rot

| Datei | erwartet | gemessen | Fehlergrund im Lauf |
|---|---|---|---|
| `tests/test_art9_zeitzeile.py` | 7 FAILED | **7 FAILED** | `assert 0 == 1` / `IndexError: list index out of range` — heute entsteht bei Art-9-Treffer **gar keine Zeile** (`len(log) == 0`). Genau der Grund, den D-07 verlangt. |
| `tests/test_speech_timing_extraction.py` | 6 FAILED | **6 FAILED** | `ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service'` |
| `tests/test_transcript_segments_write.py` | 3 FAILED + 1 gruen | **3 FAILED** | `KeyError: 'start_ms'` / `KeyError: 'end_ms'` — die reine Transform reicht die drei Schluessel nicht durch |
| **Summe** | **16 FAILED, 0 ERROR** | **16 FAILED, 0 ERROR** | |

Der vierte Test in `test_transcript_segments_write.py`
(`test_ts_ms_bleibt_unberuehrt_von_den_neuen_spalten`) ist ein **Gegenpol** zu D-02 und heute
schon gruen — das ist so gewollt und nicht herstellbar-rot. Er beweist, dass `ts_ms` von der
Aenderung unberuehrt bleibt.

---

## Tor-Ausgabe (verbatim, gueltiger Lauf 14:24)

```
[deploy] Postgres-Test-Gate: provisioniere Wegwerf-nerve_test (pg_dump-Restore vom Prod-nerve)...
[deploy] Dump-Treue-Katalog-Gate OK: crm-Policies=7, FORCE=5, anon-SELECT-GRANTs=5
[deploy] pytest gegen DATABASE_URL=postgresql://nerve_app@/nerve_test (+ 4 Test-DSNs)
........................................................................ [  6%]
........................................................................ [ 12%]
.........................................................s.............. [ 18%]
.......................FFFFFFF.......................................... [ 24%]
........................................................................ [ 30%]
.........................................................s.............. [ 37%]
........................................................................ [ 43%]
........................................................................ [ 49%]
........................................................................ [ 55%]
........................................................................ [ 61%]
........................................................................ [ 67%]
.....................[Claude-1] SID=test-sid-alpha-04 Analysiere (line 10): nur fuer SID A…
................................................... [ 74%]
..............s............................................ss........... [ 80%]
........................................................................ [ 86%]
........................................................................ [ 92%]
s...............FFFFFF...........s...................................FFF [ 98%]
..............                                                           [100%]
=================================== FAILURES ===================================
____________ test_art9_treffer_erzeugt_zeile_mit_zeiten_ohne_inhalt ____________
tests/test_art9_zeitzeile.py:87: in test_art9_treffer_erzeugt_zeile_mit_zeiten_ohne_inhalt
    assert len(log) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Art-9 erkannt, Transcript-Snippet verworfen (sid='zs1-art9-001', len=45)
____________ test_art9_zeile_traegt_kein_fragment_des_originaltexts ____________
tests/test_art9_zeitzeile.py:96: in test_art9_zeile_traegt_kein_fragment_des_originaltexts
    _ganze_zeile = repr(log[0])
                        ^^^^^^
E   IndexError: list index out of range
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Art-9 erkannt, Transcript-Snippet verworfen (sid='zs1-art9-001', len=45)
________ test_anonymisierungs_fehler_erzeugt_dieselbe_platzhalter_zeile ________
tests/test_art9_zeitzeile.py:104: in test_anonymisierungs_fehler_erzeugt_dieselbe_platzhalter_zeile
    assert len(log) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Pipeline-Fehler, Transcript-Snippet verworfen (sid='zs1-art9-001', len=45)
_______ test_pipeline_ausfall_erzeugt_platzhalter_zeile_statt_gar_keiner _______
tests/test_art9_zeitzeile.py:120: in test_pipeline_ausfall_erzeugt_platzhalter_zeile_statt_gar_keiner
    assert len(log) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Pipeline unavailable, Transcript-Snippet verworfen (sid='zs1-art9-001')
______________ test_unerwarteter_fehler_erzeugt_platzhalter_zeile ______________
tests/test_art9_zeitzeile.py:137: in test_unerwarteter_fehler_erzeugt_platzhalter_zeile
    assert len(log) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Unerwarteter Fehler im INPUT-PFAD (sid='zs1-art9-001'): ValueError
_______ test_normaler_abschnitt_traegt_weiterhin_den_anonymisierten_text _______
tests/test_art9_zeitzeile.py:145: in test_normaler_abschnitt_traegt_weiterhin_den_anonymisierten_text
    assert log[0]['start_ms'] == 2000
           ^^^^^^^^^^^^^^^^^^
E   KeyError: 'start_ms'
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
________ test_abschnitt_ohne_wortobjekte_bekommt_none_statt_null_werte _________
tests/test_art9_zeitzeile.py:155: in test_abschnitt_ohne_wortobjekte_bekommt_none_statt_null_werte
    assert len(log) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[DG] [Berater] Mein Kollege ist seit Montag krankgeschrieben
[ANON] Art-9 erkannt, Transcript-Snippet verworfen (sid='zs1-art9-001', len=45)
__________________ test_extrahiert_start_ende_und_wortanzahl ___________________
tests/test_speech_timing_extraction.py:50: in test_extrahiert_start_ende_und_wortanzahl
    assert _extract_word_times(r) == (1200, 4300, 3)
           ^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
_____________________ test_rundet_auf_ganze_millisekunden ______________________
tests/test_speech_timing_extraction.py:55: in test_rundet_auf_ganze_millisekunden
    assert _extract_word_times(r) == (0, 4300, 2)
           ^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
_______________ test_leere_wortliste_gibt_none_statt_indexerror ________________
tests/test_speech_timing_extraction.py:60: in test_leere_wortliste_gibt_none_statt_indexerror
    assert _extract_word_times(_FakeResult([])) == (None, None, None)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
__________________ test_kaputtes_result_gibt_none_statt_crash __________________
tests/test_speech_timing_extraction.py:65: in test_kaputtes_result_gibt_none_statt_crash
    assert _extract_word_times(object()) == (None, None, None)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
_________________ test_wortanzahl_ist_die_zahl_der_wortobjekte _________________
tests/test_speech_timing_extraction.py:73: in test_wortanzahl_ist_die_zahl_der_wortobjekte
    assert _extract_word_times(r)[2] == 3
           ^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
_____________________ test_zweiter_aufruf_liefert_dasselbe _____________________
tests/test_speech_timing_extraction.py:79: in test_zweiter_aufruf_liefert_dasselbe
    assert _extract_word_times(r) == _extract_word_times(r) == (500, 2500, 1)
           ^^^^^^^^^^^^^^^^^^^^^^
tests/test_speech_timing_extraction.py:31: in _extract_word_times
    from services.deepgram_service import _extract_word_times as _impl
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service' (/opt/nerve/app/services/deepgram_service.py)
___________________ test_transform_reicht_sprechzeiten_durch ___________________
tests/test_transcript_segments_write.py:66: in test_transform_reicht_sprechzeiten_durch
    assert segs[0]['start_ms'] == 1200
           ^^^^^^^^^^^^^^^^^^^
E   KeyError: 'start_ms'
__________________ test_knopfzeile_ohne_wortzeiten_wird_null ___________________
tests/test_transcript_segments_write.py:80: in test_knopfzeile_ohne_wortzeiten_wird_null
    assert segs[0]['start_ms'] is None
           ^^^^^^^^^^^^^^^^^^^
E   KeyError: 'start_ms'
_______________ test_platzhalterzeile_behaelt_ihre_sprechzeiten ________________
tests/test_transcript_segments_write.py:97: in test_platzhalterzeile_behaelt_ihre_sprechzeiten
    assert segs[0]['end_ms'] - segs[0]['start_ms'] == 30000
           ^^^^^^^^^^^^^^^^^
E   KeyError: 'end_ms'
```

Die `[BASELINE-AUTO-FIX]`-Teardown-Warnungen sind aus Platzgruenden nur einmal exemplarisch
zitiert (siehe Folgefund unten) — sie stehen im Original hinter jedem der 16 Fehlschlaege.

**Erster (blinder) Lauf 14:15, zum Vergleich:**

```
==================================== ERRORS ====================================
___________ ERROR collecting tests/test_speech_timing_extraction.py ____________
ImportError while importing test module '/opt/nerve/app/tests/test_speech_timing_extraction.py'.
tests/test_speech_timing_extraction.py:14: in <module>
    from services.deepgram_service import _extract_word_times
E   ImportError: cannot import name '_extract_word_times' from 'services.deepgram_service'
=========================== short test summary info ============================
ERROR tests/test_speech_timing_extraction.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
5 deselected, 13 warnings, 1 error in 12.50s
[deploy] FEHLER: pytest gegen nerve_test ROT — kein Restart, kein Deploy
```

---

## Folgefund (NICHT von dieser Phase verursacht, nicht hier gefixt)

Hinter jedem der 16 Fehlschlaege steht im Teardown:

```
WARNING  tests.conftest:conftest.py:662 [BASELINE-AUTO-FIX] <test> leaked rows in public.profiles: [4, 17, 18, 19, 20]
WARNING  tests.conftest:conftest.py:662 [BASELINE-AUTO-FIX] <test> leaked rows in public.organisations: [212, 221, ...]
WARNING  tests.conftest:conftest.py:662 [BASELINE-AUTO-FIX] <test> leaked rows in public.users: [65, 69, ...]
WARNING  tests.conftest:conftest.py:719 [BASELINE-AUTO-FIX] <test>: ['public.profiles', 'public.organisations', 'public.users']
         nach Retry-Loop nicht loeschbar (Mutual-FK-Hard-Stall?) -> Folge-Tests koennen beeintraechtigt sein
```

**Warum das nicht diese Phase ist:** die drei neuen Test-Dateien fassen **keine DB an** —
`test_speech_timing_extraction.py` ruft eine reine Funktion mit Fake-Objekten auf und macht
weder `get_session()` noch `commit()`. Trotzdem werden ihm dieselben Zeilen-IDs zugeschrieben
wie allen anderen. Der Waechter meldet also Zeilen, die **vor** dem Test schon da waren, und
haengt sie an den zufaellig gerade laufenden Test.

Das ist genau die Fehlerklasse aus dem Merksatz „**Zaehl-Seite ist nicht Melde-Seite**"
(MEHRNUTZER-REST-1). Die Baseline aus Phase TEST-AUFRAEUM war `[BASELINE-AUTO-FIX] = 0` —
jetzt ist sie es nicht mehr. Ob die Ursache im Dump-Restore, in der Baseline-Erhebung oder in
einem anderen Test liegt, ist **hier bewusst nicht untersucht**: Reparatur-Modus, nur der
Fehler dieser Phase wird angefasst (Bau-Regel 5). Gehoert als eigene Mini-Phase nachgezogen.

**Fuer das GRUEN-Tor dieser Phase heisst das:** die 16 muessen auf 0 gehen; die
`[BASELINE-AUTO-FIX]`-Warnungen duerfen sich dabei **nicht vermehren**, aber ihr blosses
Vorhandensein ist kein Ausschlussgrund — sie standen vorher schon da.

---

## Was dieser Lauf beweist — und was nicht

**Beweist:** Alle drei Luecken existieren heute wirklich, jede aus ihrem eigenen, benannten
Grund. Das Tor blockt den Restart. Die ~1140 Bestandstests laufen und sind gruen.

**Beweist NICHT:**
- dass der spaetere Fix richtig ist — dafuer ist der GRUEN-Lauf in Plan 06 da
- irgendetwas ueber die Cold-Call-Grenze (D-16) — die ist eine benannte Grenze, kein Test
- irgendetwas ueber echte Deepgram-Wortzeiten — die Fake-Objekte bilden die SDK-Form nach,
  nicht die SDK selbst. Der Wirkungs-Beleg kommt aus dem echten Test-Anruf (D-12).
