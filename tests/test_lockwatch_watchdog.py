"""Wachhund + Aufsatz-Riegel (Welle 3) — Phase 08.23.2.LOCK-1 Teil 3.

Am 30.07. starb eine Sitzung um 09:27:56 und NIEMAND hat es gemerkt: kein Fehler,
kein 504, keine Log-Zeile. Der py-spy-Abzug (PID 2335884) zeigte 1416 wartende
Faeden und KEINEN Halter mit sichtbarem Python-Rahmen. Diese Tests decken die zwei
Bauteile ab, die das aendern: den Aufsatz-Riegel _TracedLock (er zeichnet BEIM
ERWERB auf, wer den Riegel nimmt und seit wann) und den periodischen
[LOCKWATCH]-Tick (er meldet einen klemmenden Riegel spaetestens ~30s spaeter).

ERWARTUNGS-DAEMPFER: faulthandler zeigt exakt dieselbe Sicht wie py-spy — Python-
Stapel aller Faeden. Genau dort war der Halter am 30.07. UNSICHTBAR. faulthandler
ersetzt nur das WERKZEUG (py-spy liegt im Prod-venv, aber nicht in requirements.txt),
nicht die Antwort auf 'wer haelt den Riegel'. Die liefert allein der Aufsatz-Riegel.

Die faulthandler-Registrierung selbst wird hier NICHT geprueft: sie steht in app.py
hinter dem NERVE_TESTING-Guard und ist ein Ein-Zeilen-stdlib-Aufruf. Ihre Abnahme ist
die Beleg-Zeile im Journal nach dem Deploy ('[LOCKWATCH] faulthandler auf SIGUSR1
registriert ...').

Diese Tests sind Verhaltens-Tests, KEIN Quelltext-Check. Ein Test, der stattdessen den
QUELLTEXT von _lockwatch_tick nach der Log-Zeile durchsucht, waere ein
Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel, Z.312-335) und ist hier
ausdruecklich NICHT gebaut — gemessen wird, was der Tick TUT (capsys-Ausgabe, Zaehler,
Riegel-Zustand).

Kein pytest-Marker: deploy.sh fahrt `-m "not live and not perf"` — ein Marker wuerde
diese Tests aus dem Abnahme-Gate ausschliessen.
"""
import threading
import time

import pytest

import services.live_session as ls


_HOLDER_NOTBREMSE_S = 30.0   # selbst bei kaputtem Teardown ist der Riegel nach 30s frei
                             # (deploy.sh hat KEINEN pytest-Timeout -> ein Haenger haengt
                             # den Deploy).
_HELD_READY_S = 5.0
_HALTER_NAME = 'LOCKWATCH-testhalter'


@pytest.fixture
def held_session_state_lock():
    """Haelt _session_state_lock in einem Daemon-Faden, solange der Test laeuft.

    Handshake ueber ein Event: der Test laeuft erst weiter, wenn der Halter den Riegel
    WIRKLICH hat — sonst prueft der Wachhund einen freien Riegel und der Test waere
    zufaellig gruen.
    """
    held = threading.Event()
    release = threading.Event()

    def _halte():
        with ls._session_state_lock:
            held.set()
            release.wait(timeout=_HOLDER_NOTBREMSE_S)

    h = threading.Thread(target=_halte, daemon=True, name=_HALTER_NAME)
    h.start()
    assert held.wait(timeout=_HELD_READY_S), 'Halter-Faden hat den Riegel nicht genommen'
    try:
        yield h
    finally:
        release.set()
        h.join(timeout=5.0)


@pytest.fixture
def zaehler_zurueckgesetzt():
    """Setzt die drei Wachhund-Zaehler vor UND nach jedem Test zurueck.

    Ohne das haengt das Ergebnis an der Test-Reihenfolge: _LOCKWATCH_EVERY_N_TICKS
    drosselt ueber `_lockwatch_tick_count % N`, ein Rest aus einem Vor-Test wuerde die
    Drosselung verschieben.
    """
    ls._lockwatch_tick_count = 0
    ls._lockwatch_runs = 0
    ls._lockwatch_fails = 0
    yield
    ls._lockwatch_tick_count = 0
    ls._lockwatch_runs = 0
    ls._lockwatch_fails = 0


def test_tracedlock_zeichnet_halter_auf():
    """Der Aufsatz-Riegel merkt sich BEIM ERWERB, wer ihn genommen hat."""
    with ls._session_state_lock:
        assert ls._session_state_lock.holder_thread == threading.current_thread().name
        assert ls._session_state_lock.holder_ident == threading.current_thread().ident
        assert ls._session_state_lock.holder_since is not None


def test_tracedlock_loescht_halter_bei_freigabe():
    """Nach der Freigabe steht kein alter Halter mehr da (sonst meldete der Wachhund
    einen Faden, der laengst weg ist)."""
    with ls._session_state_lock:
        pass
    assert ls._session_state_lock.holder_thread is None
    assert ls._session_state_lock.holder_ident is None
    assert ls._session_state_lock.holder_since is None


def test_tracedlock_acquire_timeout_kehrt_mit_false_zurueck(held_session_state_lock):
    """acquire(timeout=...) funktioniert durch den Aufsatz weiterhin.

    Das ist der key_link zu wait_session_state_lock_free (Teil 1) und zu den begrenzten
    Erwerben aus Teil 2c — sie sind die einzigen Nicht-`with`-Nutzer des Riegels.
    """
    t0 = time.monotonic()
    got = ls._session_state_lock.acquire(timeout=0.2)
    dauer = time.monotonic() - t0
    assert got is False
    assert 0.15 < dauer < 2.0, f"acquire(timeout=0.2) dauerte {dauer:.2f}s"


def test_lockwatch_tick_meldet_klemmenden_riegel(
        zaehler_zurueckgesetzt, held_session_state_lock, capsys, monkeypatch):
    """Klemmt der Riegel, nennt die Meldung Faden-Name UND Uebernahme-Zeit."""
    # Nur die WARTEZEIT im Test wird verkuerzt; der Produktiv-Wert bleibt 2.0.
    monkeypatch.setattr(ls, '_LOCKWATCH_ACQUIRE_TIMEOUT_S', 0.2)

    for _ in range(ls._LOCKWATCH_EVERY_N_TICKS):
        ls._lockwatch_tick()

    out = capsys.readouterr().out
    assert '[LOCKWATCH] _session_state_lock >2s belegt' in out
    # Literal statt Konstante: die Meldung muss GENAU den Namen tragen, den die Fixture
    # gesetzt hat — eine Konstante auf beiden Seiten waere gegen sich selbst gruen.
    assert 'LOCKWATCH-testhalter' in out, (
        f"Die Meldung nennt den Halter-Faden nicht: {out!r}. Genau dafuer gibt es den "
        f"Aufsatz-Riegel — CONTEXT verlangt Faden-Name UND Uebernahme-Zeit.")
    assert 'Uebernahme=' in out and 'unbekannt' not in out.split('Uebernahme=')[1][:12]
    assert 'sudo systemctl kill -s SIGUSR1 nerve' in out
    assert ls._lockwatch_fails == 1


def test_lockwatch_tick_haelt_den_riegel_nicht_fest(zaehler_zurueckgesetzt):
    """P-3, die gefaehrlichste Falle: der Waechter darf nicht selbst zur Ursache werden.

    Bewusst OHNE Halter-Fixture — geprueft wird der ERFOLGSFALL: der Wachhund nimmt den
    Riegel, tut nichts, gibt ihn im finally wieder frei.
    """
    for _ in range(ls._LOCKWATCH_EVERY_N_TICKS):
        ls._lockwatch_tick()
    assert ls._lockwatch_runs == 1
    assert ls._lockwatch_fails == 0
    assert ls._session_state_lock.acquire(timeout=1.0) is True, (
        "Der Wachhund hat den Riegel nach einer ERFOLGREICHEN Pruefung nicht freigegeben "
        "— dann ist der Waechter selbst die Ursache (P-3).")
    ls._session_state_lock.release()


def test_lockwatch_tick_drosselt(zaehler_zurueckgesetzt):
    """Erst der _LOCKWATCH_EVERY_N_TICKS-te Aufruf prueft wirklich (~30s bei 5s-Takt)."""
    for _ in range(ls._LOCKWATCH_EVERY_N_TICKS - 1):
        ls._lockwatch_tick()
    assert ls._lockwatch_runs == 0, "Der Tick prueft zu frueh — die Drosselung greift nicht."
    ls._lockwatch_tick()
    assert ls._lockwatch_runs == 1
