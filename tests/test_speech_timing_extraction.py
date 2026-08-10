"""Phase 08.23.2.ZEITSTEMPEL-1 — ROT-Netz fuer die Wortzeiten-Naht.

Function-Call-Return-Tests gegen die reine Extraktions-Funktion. KEIN Source-Presence-Check
(CLAUDE.md Test-Qualitaets-Regel): die Tests rufen die Funktion auf und assertieren auf den
Rueckgabewert. Kein DB-Zugriff, kein commit -> kein Zeilen-Aufraeumen noetig (tests/conftest.py-Konvention).

ROT gegen den Stand vor dieser Phase: services/deepgram_service._extract_word_times
existiert nicht -> ImportError beim Sammeln.

KEIN Versatz-Parameter: der Reconnect-Versatz (D-05) ist nach dem Cross-AI-Review vom
2026-08-10 gestrichen. Ohne ihn wird die Pause ueber eine Naht negativ — physikalisch
unmoeglich und damit ein selbsterklaerendes "unbekannt".
"""
from services.deepgram_service import _extract_word_times


class _FakeWord:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class _FakeResult:
    """Minimaler Nachbau von result.channel.alternatives[0].words (deepgram-sdk 3.10.0)."""
    def __init__(self, words):
        alt = type('Alt', (), {'words': words})()
        self.channel = type('Ch', (), {'alternatives': [alt]})()


def test_extrahiert_start_ende_und_wortanzahl():
    r = _FakeResult([_FakeWord(1.2, 1.9), _FakeWord(2.0, 2.6), _FakeWord(3.9, 4.3)])
    assert _extract_word_times(r) == (1200, 4300, 3)


def test_rundet_auf_ganze_millisekunden():
    r = _FakeResult([_FakeWord(0.0004, 0.5), _FakeWord(4.0, 4.2996)])
    assert _extract_word_times(r) == (0, 4300, 2)


def test_leere_wortliste_gibt_none_statt_indexerror():
    # is_final=True kann laut Deepgram-Verhalten mit leerer words-Liste kommen.
    assert _extract_word_times(_FakeResult([])) == (None, None, None)


def test_kaputtes_result_gibt_none_statt_crash():
    # Der Live-Loop-Thread darf an dieser Stelle NIE sterben (Muster _get_speaker).
    assert _extract_word_times(object()) == (None, None, None)
    assert _extract_word_times(None) == (None, None, None)


def test_wortanzahl_ist_die_zahl_der_wortobjekte():
    # D-07: gezaehlt werden die ROHEN Wortobjekte, nicht die Woerter des spaeter
    # anonymisierten Textes ([PERSON_A] ersetzt zwei gesprochene Woerter durch eines).
    r = _FakeResult([_FakeWord(0.5, 0.8), _FakeWord(0.9, 1.4), _FakeWord(1.5, 2.5)])
    assert _extract_word_times(r)[2] == 3


def test_zweiter_aufruf_liefert_dasselbe():
    # Die Funktion haelt keinen Zustand — kein akkumulierender Versatz, kein Zaehler.
    r = _FakeResult([_FakeWord(0.5, 2.5)])
    assert _extract_word_times(r) == _extract_word_times(r) == (500, 2500, 1)
