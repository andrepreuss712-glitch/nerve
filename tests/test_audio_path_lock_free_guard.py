"""Waechter 3 (Ton-Weg riegel-frei) — Phase 08.23.2.LOCK-1.

get_sid_paused lief bei JEDEM Ton-Brocken, also 10x/Sekunde pro Anruf
(deepgram_service.py:864, 100ms-Frames) — und nahm dabei denselben GLOBALEN
_session_state_lock wie Analyse, Coaching, Umschalter, Knopfdruck und Auflegen.
py-spy-Abzug 30.07. (sid 5Y-0MFlm_ITb1cupAAAB, PID 2335884): 1415 von 1416
blockierten Rahmen standen genau dort. Klemmte der Riegel einmal, starb die
ganze Sitzung — stumm.

DIESER TEST IST EIN VERHALTENS-TEST, KEIN QUELLTEXT-CHECK.
Ein Test, der stattdessen den QUELLTEXT von get_sid_paused nach dem Riegel-Wort
durchsucht, waere ein Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel,
Z.312-335) und ist hier ausdruecklich NICHT gebaut. Stattdessen: ein Halter-Faden HAELT den Riegel,
und die Funktion muss trotzdem zurueckkehren UND den korrekten Wert liefern.
Die gepaarte Wert-Assertion ist Pflicht — ohne sie waere ein `return False`-Stub gruen.

ABGRENZUNG (wichtig, RESEARCH §2): geprueft wird der 10-Hz-EINGANGS-Weg
(handle_audio_chunk -> get_sid_paused). Der on_message-Weg (deepgram_service.py:85)
wird NICHT riegel-frei — dort liegen 13 weitere _session_state_lock-Nahmen, u.a.
deepgram_service.py:94 bei JEDER finalisierten Zeile. Dieser Waechter behauptet
NICHT "on_message ist riegel-frei". Genau deshalb gibt es Teil 2 (finish()-Zeitlimit).

ERST ROT: am Stand vor Plan 03 muessen BEIDE Tests fehlschlagen (get_sid_paused
blockiert bei live_session.py:107). Ein Test, der von Anfang an gruen ist, beweist nichts.

_extract_handler ist bewusst aus tests/test_mode_switch_event.py:23-39 KOPIERT und
nicht in conftest.py gezogen: conftest.py ist 966 Zeilen gemeinsame Infrastruktur;
eine Aenderung dort riskiert die ganze Suite und wuerde einen Datei-Konflikt mit den
anderen Plaenen dieser Phase erzeugen. Zwoelf duplizierte Zeilen sind der billigere Preis.

Kein pytest-Marker: deploy.sh:221 fahrt `-m "not live and not perf"` — ein Marker
wuerde diesen Waechter aus dem Abnahme-Gate ausschliessen.
"""
import threading

import pytest
from unittest.mock import MagicMock

import services.live_session as ls


_HOLDER_NOTBREMSE_S = 30.0   # Schicht 4 Punkt 2: selbst bei kaputtem Teardown ist der
                             # Riegel nach 30s frei statt fuer immer (deploy.sh:221 hat
                             # KEINEN pytest-Timeout -> ein Haenger haengt den Deploy).
_HELD_READY_S = 5.0
_PRUEFLING_TIMEOUT_S = 2.0   # get_sid_paused ist ein dict-Read; 2s sind grosszuegig.
_SID_PAUSED = 'lock1-w3-paused-001'
_SID_UNBEKANNT = 'lock1-w3-unbekannt-002'


def _extract_handler(event_name):
    """Extrahiert einen registrierten SocketIO-Handler aus register_audio_handlers.

    register_audio_handlers(sio) registriert Handler als verschachtelte Closures via
    @sio.on(event). Wir uebergeben ein Mock-sio dessen .on-Methode die Registrierungen
    in einem Dict aufzeichnet — so koennen wir den echten Handler-Code direkt aufrufen.

    Bewusste Kopie aus tests/test_mode_switch_event.py:23-39 (siehe Modul-Docstring):
    kein Cross-Test-Import, keine conftest.py-Aenderung.
    """
    registered = {}

    mock_sio = MagicMock()
    # sio.on(event) gibt einen Decorator zurueck der fn registriert und unveraendert zurueckgibt
    mock_sio.on = lambda event: (lambda fn: registered.__setitem__(event, fn) or fn)

    from services.deepgram_service import register_audio_handlers
    register_audio_handlers(mock_sio)

    return registered[event_name], mock_sio


@pytest.fixture
def geseedeter_state():
    """Seedet is_paused=True fuer _SID_PAUSED. MUSS vor der Halter-Fixture laufen
    (Parameter-Reihenfolge!), sonst blockiert das Seeding selbst am gehaltenen Riegel."""
    with ls._session_state_lock:
        ls._session_state[_SID_PAUSED] = {'state': {'is_paused': True}}
        ls._session_state.pop(_SID_UNBEKANNT, None)
    yield
    with ls._session_state_lock:
        ls._session_state.pop(_SID_PAUSED, None)


@pytest.fixture
def held_session_state_lock():
    """Haelt _session_state_lock in einem Daemon-Faden, solange der Test laeuft.

    Liefert eine Anmelde-Funktion: jeder Pruefling-Faden meldet sich direkt nach
    start() an und wird NACH der Riegel-Freigabe eingesammelt (Schicht 4 Punkt 3).
    Ohne diesen zweiten Join laeuft ein im ROT-Lauf noch am Riegel stehender Faden
    in den naechsten Teardown hinein.
    """
    _nachzuegler = []
    held = threading.Event()
    release = threading.Event()

    def _halte():
        with ls._session_state_lock:
            held.set()
            # Notbremse: selbst bei kaputtem Teardown ist der Riegel nach 30s frei.
            release.wait(timeout=_HOLDER_NOTBREMSE_S)

    h = threading.Thread(target=_halte, daemon=True, name='LOCK1-holder')
    h.start()
    assert held.wait(timeout=_HELD_READY_S), 'Halter-Faden hat den Riegel nicht genommen'

    def registriere_pruefling(t):
        _nachzuegler.append(t)

    try:
        yield registriere_pruefling
    finally:
        release.set()
        h.join(timeout=5.0)
        for _t in _nachzuegler:
            _t.join(timeout=5.0)


def test_get_sid_paused_kehrt_mit_gehaltenem_riegel_zurueck(geseedeter_state, held_session_state_lock):
    """get_sid_paused muss auch bei gehaltenem Riegel zurueckkehren — und richtig liegen.

    Die Parameter-Reihenfolge ist LOAD-BEARING: pytest baut in Parameter-Reihenfolge auf
    und in umgekehrter Reihenfolge ab. `geseedeter_state` muss VOR `held_session_state_lock`
    stehen, sonst blockiert das Seeding selbst am gehaltenen Riegel (Schicht 4 Punkt 1).
    """
    ergebnis = []

    def _lies():
        ergebnis.append(ls.get_sid_paused(_SID_PAUSED))
        ergebnis.append(ls.get_sid_paused(_SID_UNBEKANNT))

    c = threading.Thread(target=_lies, daemon=True, name='LOCK1-pruefling-get-sid-paused')
    c.start()
    held_session_state_lock(c)   # Nachzuegler-Anmeldung, Schicht 4 Punkt 3
    c.join(timeout=_PRUEFLING_TIMEOUT_S)
    assert not c.is_alive(), (
        f"get_sid_paused kehrte mit gehaltenem _session_state_lock nicht innerhalb "
        f"{_PRUEFLING_TIMEOUT_S}s zurueck — die Funktion nimmt den globalen Riegel "
        f"(live_session.py:105-108). Das ist Wurzel 1 aus Phase 08.23.2.LOCK-1.")
    assert ergebnis == [True, False], (
        f"Riegel-freies Lesen liefert den falschen Wert: {ergebnis!r} "
        f"— erwartet [True, False] (geseedet is_paused=True bzw. unbekannte sid).")


def test_handle_audio_chunk_kehrt_mit_gehaltenem_riegel_zurueck(geseedeter_state, held_session_state_lock):
    """Der 10-Hz-Eingang muss auch bei gehaltenem Riegel zurueckkehren.

    Parameter-Reihenfolge wie oben LOAD-BEARING (Schicht 4 Punkt 1).

    Keine Deepgram-Attrappe noetig: _deepgram_sessions kennt _SID_UNBEKANNT nicht ->
    connection is None -> _send_audio_chunk wird nicht gerufen (deepgram_service.py:866-869).
    Der Test durchlaeuft trotzdem den kompletten Weg bis hinter :864.
    """
    handler, _mock_sio = _extract_handler('audio_chunk')
    fertig = threading.Event()

    def _sende():
        handler(b'\x00' * 100, sid=_SID_UNBEKANNT)
        fertig.set()

    c = threading.Thread(target=_sende, daemon=True, name='LOCK1-pruefling-audio-chunk')
    c.start()
    held_session_state_lock(c)   # Nachzuegler-Anmeldung, Schicht 4 Punkt 3
    c.join(timeout=_PRUEFLING_TIMEOUT_S)
    assert not c.is_alive(), (
        f"handle_audio_chunk kehrte mit gehaltenem _session_state_lock nicht innerhalb "
        f"{_PRUEFLING_TIMEOUT_S}s zurueck — der 10-Hz-Ton-Weg haengt an "
        f"deepgram_service.py:864 (ls.get_sid_paused). 1415 von 1416 blockierten Rahmen "
        f"im py-spy-Abzug vom 30.07. standen genau dort.")
    assert fertig.is_set(), (
        "handle_audio_chunk ist zurueckgekehrt, hat aber das Fertig-Signal nicht gesetzt — "
        "der Faden ist also anders geendet als durch regulaere Rueckkehr.")
