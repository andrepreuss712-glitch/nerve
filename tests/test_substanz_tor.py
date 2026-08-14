"""METRIK-1 Requirement 1 + 2 — Verhaltens-Tests fuer das Sprech-Substanz-Tor.

Das alte Tor fragte "gab es mindestens drei hoch-konfidente Einwand-Momente?" und sperrte
damit 83 % aller Anrufe aus: im Kaltakquise-Modus hoert NERVE nur den Berater und die
automatische Einwand-Erkennung ist kanonisch abgeschaltet, Momente entstehen fast nur per
Knopfdruck. Das neue Tor fragt "wurde ueberhaupt genug gesprochen?" und hat GENAU EINE
Bedingung: die Zahl der gesprochenen Berater-Woerter.

Alle Tests hier pruefen RUNTIME-VERHALTEN (CLAUDE.md Test-Qualitaets-Regel):
Rueckgabewerte reiner Funktionen bzw. der befuellte ctx nach einem echten _call_end_merge.
Keine Quelltext-Pruefung, kein Nachsehen ob ein Symbol existiert — solche Tests bleiben gruen,
solange der Code nur DASTEHT, auch wenn er nie laeuft.

Jeder Tor-Test prueft das PAAR (grund, zweig) — nicht nur den Grund. Der Zweig ist der Beleg
dafuer, dass "unbekannte Wortzahl" ein EIGENER Programm-Weg ist und nicht dieselbe Ablehnung
unter anderem Namen (Auflage aus dem Cross-AI-Durchgang, Gemini B-3 = GSD-Plan-Checker W-5).
"""

import uuid
from types import SimpleNamespace

import pytest

import services.slow_lane as sl


# ════════════════════════════════════════════════════════════════════════════════════
# Test-Doubles — Muster tests/test_judge_runner.py::_make_segment, erweitert um die
# ZEITSTEMPEL-1-Spalten (word_count/start_ms/end_ms).
# ════════════════════════════════════════════════════════════════════════════════════

def _make_segment(idx=1, speaker='berater', ts_ms=1000, text='Guten Tag, darf ich kurz stoeren?',
                  word_count=None, start_ms=None, end_ms=None):
    """transcript_segments-Zeilen-Attrappe. speaker traegt die DB-FORM (String), nicht die
    RAM-Ganzzahl aus services/deepgram_service.py — der CheckConstraint
    ck_transcript_segments_speaker laesst nur 'berater'|'kunde'|'system' zu."""
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text,
                           word_count=word_count, start_ms=start_ms, end_ms=end_ms)


def _berater(word_count, idx=1, **kw):
    return _make_segment(idx=idx, speaker='berater', word_count=word_count, **kw)


def _kunde(word_count, idx=1, **kw):
    return _make_segment(idx=idx, speaker='kunde', word_count=word_count, **kw)


# ════════════════════════════════════════════════════════════════════════════════════
# 1 — Das Abnahme-Kriterium von SPEC Requirement 1
# ════════════════════════════════════════════════════════════════════════════════════

def test_zwanzig_woerter_ohne_moment_wird_bewertet():
    """Zwanzig Berater-Woerter, NULL hoch-konfidente Momente -> der Anruf wird bewertet.

    Das ist das woertliche Abnahme-Kriterium von SPEC Requirement 1. Unter dem alten Tor
    waere derselbe Anruf abgewiesen worden, weil die Zahl der Momente 0 ist.
    """
    segments = [_berater(10, idx=1), _berater(10, idx=2)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] == 20
    assert mess['berater_wortzahl_unbekannt'] is False
    assert sl._tor_sprech_substanz(mess) == (None, 'genug_woerter')


# ════════════════════════════════════════════════════════════════════════════════════
# 2 — Der Cross-AI-Fund vom 14.08. als Verhaltens-Test
# ════════════════════════════════════════════════════════════════════════════════════

def test_hundert_woerter_in_einem_einzigen_abschnitt_wird_durchgelassen():
    """EIN Redeabschnitt mit hundert Woertern kommt durch.

    Bei endpointing=900 (services/deepgram_service.py) ist ein am Stueck gesprochener
    Einstieg ohne Atempause EIN einziges Segment. Eine Mindestzahl an Redeabschnitten haette
    genau diesen Anruf abgewiesen — den Anruf, fuer den diese Phase existiert. Die
    Abschnitts-Bedingung ist deshalb am 14.08. ersatzlos gestrichen worden.

    Dieser Test ist die Gegenprobe zur gestrichenen Bedingung: waere sie noch da, waere er rot.
    """
    segments = [_berater(100, idx=1)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['redeabschnitte'] == 1
    assert mess['berater_woerter'] == 100
    assert sl._tor_sprech_substanz(mess) == (None, 'genug_woerter')


# ════════════════════════════════════════════════════════════════════════════════════
# 3 — Die untere Kante
# ════════════════════════════════════════════════════════════════════════════════════

def test_vier_woerter_wird_abgelehnt():
    """Vier Berater-Woerter werden abgewiesen (SPEC-Abnahme). Aus vier Woertern ist kein
    zitierfaehiger Satz ziehbar, und ein woertliches Zitat ist die ganze Herleitung der 20."""
    segments = [_berater(4, idx=1)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] == 4
    assert sl._tor_sprech_substanz(mess) == ('too_little_speech', 'zu_wenig_woerter')


# ════════════════════════════════════════════════════════════════════════════════════
# 4 + 5 — Der EIGENE Unbekannt-Zweig (fail-open), im Rueckgabewert belegt
# ════════════════════════════════════════════════════════════════════════════════════

def test_nur_null_wortzahlen_laeuft_ueber_den_eigenen_unbekannt_zweig():
    """Ausschliesslich unbekannte Wortzahlen -> DURCHGELASSEN, ueber einen EIGENEN Zweig.

    SPEC :517 verlangt woertlich: "ein Anruf mit ausschliesslich word_count IS NULL wird nicht
    wegen Wortmangel abgelehnt." Bis zum 13.08. wurde er es faktisch doch — nur mit anderer
    Begruendung unter DEMSELBEN reason-String. Zwei unabhaengige Gegenleser (Gemini B-3 und der
    GSD-Plan-Checker W-5) haben das gefunden.

    Der Beleg ist deshalb der RUECKGABEWERT und nicht ein Docstring: 'wortzahl_unbekannt_
    durchgelassen' ist vom Genug-Zweig unterscheidbar UND liefert kein reason.
    """
    segments = [_berater(None, idx=1), _berater(None, idx=2)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] is None
    assert mess['berater_wortzahl_unbekannt'] is True
    assert sl._tor_sprech_substanz(mess) == (None, 'wortzahl_unbekannt_durchgelassen')


def test_gemischte_null_unter_zwanzig_laeuft_ueber_den_eigenen_unbekannt_zweig():
    """Bekannte Summe 14 (< 20), aber eine Berater-Zeile ohne Wortzahl -> DURCHGELASSEN.

    Die fail-open-Kante: die Wortbedingung ist nicht entschieden, also wird im Zweifel
    durchgelassen — und zwar sichtbar ueber den Unbekannt-Zweig, nicht getarnt als "genug".
    """
    segments = [_berater(8, idx=1), _berater(6, idx=2), _berater(None, idx=3)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] == 14
    assert mess['berater_wortzahl_unbekannt'] is True
    assert sl._tor_sprech_substanz(mess) == (None, 'wortzahl_unbekannt_durchgelassen')


# ════════════════════════════════════════════════════════════════════════════════════
# 6 — Die Abgrenzung: "gar nichts gesagt" ist nicht "unbekannt"
# ════════════════════════════════════════════════════════════════════════════════════

def test_ohne_jede_berater_zeile_wird_abgelehnt():
    """Keine einzige Berater-Zeile -> ABGELEHNT, ueber den Zweig keine_berater_zeile.

    Ohne diesen Test waere der fail-open-Zweig nicht von einem Durchwinken aller Anrufe zu
    unterscheiden: "unbekannt" darf kein Sammel-Ausgang sein.
    """
    segments = [_kunde(30, idx=1), _kunde(25, idx=2)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] is None
    assert mess['berater_wortzahl_unbekannt'] is False
    grund, zweig = sl._tor_sprech_substanz(mess)
    assert (grund, zweig) == ('too_little_speech', 'keine_berater_zeile')
    # Die eigentliche Abgrenzung: dieser Fall darf NICHT im fail-open-Zweig landen.
    assert zweig != 'wortzahl_unbekannt_durchgelassen'


# ════════════════════════════════════════════════════════════════════════════════════
# 7 — Die EINZIGE verbliebene EWB-Kante des Tors (Ableitung c2)
# ════════════════════════════════════════════════════════════════════════════════════

def test_ewb_zeile_kippt_nicht_in_den_unbekannt_zweig():
    """Die EWB-Knopf-Zeile (speaker kunde, word_count NULL) kippt das Tor NICHT auf fail-open.

    Die Unbekannt-Erkennung schaut NUR auf Berater-Zeilen. Sonst waere das Tor per Knopfdruck
    aushebelbar: ein Knopfdruck haengt eine Kunde-Zeile ohne Wortzahl an, und jeder zu kurze
    Anruf liefe damit in den fail-open-Zweig. Seit der Streichung der Abschnitts-Bedingung ist
    das die einzige verbliebene EWB-Kante des Tors — sie traegt hier allein.
    """
    segments = [
        _berater(5, idx=1),
        _berater(5, idx=2),
        _berater(5, idx=3),
        _kunde(None, idx=4, text='Kein Interesse. *ewb button*'),
    ]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] == 15
    assert mess['berater_wortzahl_unbekannt'] is False
    assert sl._tor_sprech_substanz(mess) == ('too_little_speech', 'zu_wenig_woerter')


# ════════════════════════════════════════════════════════════════════════════════════
# 8 — Regel (c): nur BERATER-Woerter zaehlen (Meeting-Modus)
# ════════════════════════════════════════════════════════════════════════════════════

def test_nur_kundenwoerter_werden_nicht_gezaehlt():
    """Im Meeting-Modus tragen auch Kunden-Zeilen word_count. Wer stumpf summiert, laesst ein
    Meeting durch, in dem fast nur der Kunde sprach — bewertet wird aber der Berater."""
    segments = [_kunde(40, idx=1), _kunde(40, idx=2), _kunde(40, idx=3), _berater(3, idx=4)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['berater_woerter'] == 3
    assert sl._tor_sprech_substanz(mess) == ('too_little_speech', 'zu_wenig_woerter')


# ════════════════════════════════════════════════════════════════════════════════════
# 9 — redeabschnitte: gemessen, aber ohne Entscheidungsgewalt
# ════════════════════════════════════════════════════════════════════════════════════

def test_redeabschnitte_sind_diagnose_und_keine_bedingung():
    """Die Zahl der Redeabschnitte wird korrekt GEMESSEN (Zeilen mit word_count IS NOT NULL,
    alle Sprecher) — und sie entscheidet NICHTS. Diese Haelfte belegt die Messung; dass die
    Zahl nichts entscheidet, belegt daneben Test 2 (hundert Woerter in EINEM Abschnitt kommen
    durch). Der Wert traegt die Nachjustierung nach rund hundert echten Anrufen."""
    segments = [_berater(100, idx=1), _berater(None, idx=2), _kunde(None, idx=3)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['redeabschnitte'] == 1
    assert mess['berater_woerter'] == 100


# ════════════════════════════════════════════════════════════════════════════════════
# 10 + 11 — Sprechzeit als reiner Messwert
# ════════════════════════════════════════════════════════════════════════════════════

def test_sprechzeit_summiert_nur_berater_und_klemmt_negativ():
    """Eine negative Differenz traegt 0 bei, nicht -500.

    Das Schild _SCHILD_START_MS nennt ueberlappende Deepgram-Endergebnisse ausdruecklich als
    UNVERIFIED und verlangt vom Leser, negative Differenzen abzufangen.
    """
    segments = [
        _berater(10, idx=1, start_ms=0, end_ms=1000),
        _berater(10, idx=2, start_ms=2000, end_ms=1500),
        _kunde(50, idx=3, start_ms=0, end_ms=9000),
    ]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['sprechzeit_ms'] == 1000


def test_sprechzeit_unbekannt_ist_none_nicht_null():
    """Alt-Anrufe vor ZEITSTEMPEL-1 tragen keine Wortzeiten -> sprechzeit_ms is None.
    NULL heisst unbekannt, nie "hat null Millisekunden gesprochen"."""
    segments = [_berater(10, idx=1), _berater(15, idx=2)]
    mess = sl._mess_sprech_substanz(segments)

    assert mess['sprechzeit_ms'] is None
    assert mess['berater_woerter'] == 25


# ════════════════════════════════════════════════════════════════════════════════════
# 12 — Reihenfolge der Tore: Audio zuerst (SPEC Req 1, unveraendert)
# ════════════════════════════════════════════════════════════════════════════════════

def _make_call(**overrides):
    base = dict(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        call_mode='cold_call',
        ended_at=object(),
        conversation_log_id=42,
        audio_health_score=0.9,
        audio_health_resolved=True,
        transcript_resolved=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeSession:
    def __init__(self, call):
        self._call = call

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._call

    def execute(self, stmt):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def merge_doubles(monkeypatch):
    """Verkabelt die DB-Helfer von _call_end_merge mit Fakes und liefert einen Aufrufer, der
    den befuellten ctx zurueckgibt."""
    def _lauf(call, segments, high_conf=0):
        monkeypatch.setattr(sl, 'get_session', lambda: _FakeSession(call))
        monkeypatch.setattr(sl, '_pending_events', lambda cid, db: 0)
        monkeypatch.setattr(sl, '_events_for_call', lambda cid, db: [])
        monkeypatch.setattr(sl, '_count_high_confidence', lambda evs, db: high_conf)
        monkeypatch.setattr(sl, '_segments_for_call', lambda clid, db: segments)
        monkeypatch.setattr(sl, 'set_current_tenant', lambda tid: None)
        monkeypatch.setattr(sl, 'clear_current_tenant', lambda: None)
        seen = {}
        monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])
        sl._call_end_merge({'call_id': call.id})
        return seen
    return _lauf


def test_audio_tor_hat_vorrang(merge_doubles):
    """Schlechtes Audio UND zu wenig Sprech-Substanz -> der Grund lautet poor_audio_health.

    Das Audio-Gueten-Tor steht unveraendert VORNE (SPEC Req 1: "Das Audio-Gueten-Tor bleibt
    unveraendert"). Geprueft wird der echte Kaskaden-Ablauf in _call_end_merge, NICHT eine im
    Test nachgebaute Kopie der Kaskade — eine Kopie bewiese nur, dass der Test rechnen kann.
    """
    call = _make_call(audio_health_score=0.1)
    seen = merge_doubles(call, segments=[_berater(2, idx=1)])

    assert seen.get('not_gradable_reason') == 'poor_audio_health'
    # Gepaarter Existenz-Anker: der Tor-Block lief ueberhaupt, und die Messwerte stehen daneben
    # — sonst waere "richtiger Grund" nicht von "Merge gar nicht gefeuert" zu unterscheiden.
    assert seen.get('mess_substanz', {}).get('berater_woerter') == 2
