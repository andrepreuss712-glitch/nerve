"""Phase 08.23.2.ZEITSTEMPEL-1 — Weg C: Art-9-Abschnitte verlieren ihre Sprech-Zeit nicht.

Verhaltens-Test gegen den ECHTEN on_message-Handler mit gemockter Anonymisierungs-Naht.
Kein Source-Presence-Check, kein DB-Zugriff, kein commit -> kein Zeilen-Aufraeumen noetig.

ROT gegen den Stand vor dieser Phase: bei einem Art-9-Treffer entsteht heute GAR KEINE
Zeile im conversation_log (services/deepgram_service.py:154-157 setzen nur
_text_for_analysis = None und ueberspringen den Append) -> len(log) == 0 statt 1.

WARUM WEG C (Andre-Entscheidung 2026-08-10, DIALOG-GSD-CLAUDIAN.md):
Ein verworfener Abschnitt fehlt in Zaehler UND Nenner des Redeanteils, und seine Luecke
wird spaeter als Pause fehlgelesen. Eine still verzerrte Kennzahl ist genau die
Fehlerklasse, die diese Phase beseitigen soll. Gespeichert wird trotzdem GENAUSO WENIG
INHALT WIE HEUTE: nur Zeiten, eine Zahl und ein neutraler Platzhalter OHNE Kategorie
(der Marker soll nicht verraten, worum es ging).

Die Anonymisierungs-Pipeline wird dabei nur ERGAENZT, nicht umgebaut: anonymize() bleibt
fail-closed, es wird KEIN roher und KEIN geschwaerzter Text zusaetzlich gespeichert.
"""
import pytest

import services.deepgram_service as dg
import services.live_session as ls


_SID = 'zs1-art9-001'
_PLATZHALTER = '[nicht gespeichert]'
_ROHTEXT = 'Mein Kollege ist seit Montag krankgeschrieben'


class _FakeWord:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.confidence = 0.99


class _FakeResult:
    """Minimaler Nachbau eines finalisierten Deepgram-Ergebnisses."""
    def __init__(self, transcript, words):
        self.is_final = True
        alt = type('Alt', (), {'transcript': transcript, 'words': words})()
        self.channel = type('Ch', (), {'alternatives': [alt]})()
        self.metadata = type('Meta', (), {'duration': 0.0})()


class _StummesSio:
    def emit(self, *a, **k):
        return None


@pytest.fixture
def geseedete_sid(monkeypatch):
    """Seedet den per-SID-Zustand direkt (Muster tests/test_audio_path_lock_free_guard.py)
    und ersetzt extensions.socketio durch eine stumme Attrappe — on_message holt sie
    erst zur Aufrufzeit (`from extensions import socketio as sio`)."""
    import extensions
    monkeypatch.setattr(extensions, 'socketio', _StummesSio(), raising=False)
    with ls._session_state_lock:
        ls._session_state[_SID] = {
            'state': {'is_paused': False},
            'conversation_log': [],
            'word_confidences': [],
            '_line_id_counter': 0,
            'anonymisierer': None,
        }
    yield
    with ls._session_state_lock:
        ls._session_state.pop(_SID, None)


def _lauf(monkeypatch, anon_rueckgabe, words=None):
    """Ruft den echten on_message-Handler einmal auf und gibt den RAM-Log zurueck."""
    import services.anonymization as anon
    monkeypatch.setattr(anon, 'anonymize', lambda text, cache: anon_rueckgabe)
    handler = dg._make_on_message(_SID, mode='cold_call')
    handler(None, _FakeResult(_ROHTEXT, words if words is not None else [
        _FakeWord(2.0, 2.4), _FakeWord(2.5, 3.0), _FakeWord(3.1, 3.6),
        _FakeWord(3.7, 4.0), _FakeWord(4.1, 5.0),
    ]))
    with ls._session_state_lock:
        return list(ls._session_state[_SID]['conversation_log'])


def test_art9_treffer_erzeugt_zeile_mit_zeiten_ohne_inhalt(geseedete_sid, monkeypatch):
    log = _lauf(monkeypatch, ('[ART9_REDACTED]', 'art9'))
    assert len(log) == 1
    assert log[0]['text'] == _PLATZHALTER
    assert log[0]['start_ms'] == 2000
    assert log[0]['end_ms'] == 5000
    assert log[0]['word_count'] == 5


def test_art9_zeile_traegt_kein_fragment_des_originaltexts(geseedete_sid, monkeypatch):
    log = _lauf(monkeypatch, ('[ART9_REDACTED]', 'art9'))
    _ganze_zeile = repr(log[0])
    assert 'krankgeschrieben' not in _ganze_zeile
    assert 'Kollege' not in _ganze_zeile
    assert 'ART9' not in _ganze_zeile


def test_anonymisierungs_fehler_erzeugt_dieselbe_platzhalter_zeile(geseedete_sid, monkeypatch):
    log = _lauf(monkeypatch, ('[ANON_FEHLER]', 'fehler'))
    assert len(log) == 1
    assert log[0]['text'] == _PLATZHALTER
    assert log[0]['word_count'] == 5


def test_pipeline_ausfall_erzeugt_platzhalter_zeile_statt_gar_keiner(geseedete_sid, monkeypatch):
    import services.anonymization as anon

    def _wirft(text, cache):
        raise anon.AnonymizationPipelineUnavailable('Test')

    monkeypatch.setattr(anon, 'anonymize', _wirft)
    handler = dg._make_on_message(_SID, mode='cold_call')
    handler(None, _FakeResult(_ROHTEXT, [_FakeWord(0.0, 1.0), _FakeWord(1.2, 2.0)]))
    with ls._session_state_lock:
        log = list(ls._session_state[_SID]['conversation_log'])
    assert len(log) == 1
    assert log[0]['text'] == _PLATZHALTER
    assert log[0]['start_ms'] == 0
    assert log[0]['end_ms'] == 2000


def test_unerwarteter_fehler_erzeugt_platzhalter_zeile(geseedete_sid, monkeypatch):
    import services.anonymization as anon

    def _wirft(text, cache):
        raise ValueError('unerwartet')

    monkeypatch.setattr(anon, 'anonymize', _wirft)
    handler = dg._make_on_message(_SID, mode='cold_call')
    handler(None, _FakeResult(_ROHTEXT, [_FakeWord(0.0, 1.0), _FakeWord(1.2, 2.0)]))
    with ls._session_state_lock:
        log = list(ls._session_state[_SID]['conversation_log'])
    assert len(log) == 1
    assert log[0]['text'] == _PLATZHALTER


def test_normaler_abschnitt_traegt_weiterhin_den_anonymisierten_text(geseedete_sid, monkeypatch):
    log = _lauf(monkeypatch, ('Mein Kollege ist seit [DATUM] krank', 'tier_1'))
    assert len(log) == 1
    assert log[0]['text'] == 'Mein Kollege ist seit [DATUM] krank'
    assert log[0]['start_ms'] == 2000
    assert log[0]['end_ms'] == 5000
    assert log[0]['word_count'] == 5


def test_abschnitt_ohne_wortobjekte_bekommt_none_statt_null_werte(geseedete_sid, monkeypatch):
    # Bekannte Daten-Kante (Gemini LOW): ein Endergebnis mit Text, aber ohne
    # Wortobjekte. NULL heisst "unbekannt"; eine 0 wuerde "hat nichts gesagt"
    # behaupten und jeden Mittelwert verfaelschen (D-04).
    log = _lauf(monkeypatch, ('[ART9_REDACTED]', 'art9'), words=[])
    assert len(log) == 1
    assert log[0]['start_ms'] is None
    assert log[0]['end_ms'] is None
    assert log[0]['word_count'] is None
