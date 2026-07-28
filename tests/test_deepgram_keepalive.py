"""Waechter: der Deepgram-Client wird MIT Keepalive-Option gebaut (SOFORT-PAKET 27.07. FIX 3).

Ohne Keepalive schliesst Deepgram nach ~10s ohne eintreffende Audio-Daten mit Code 1011
("did not receive audio data") — der Ton muss dafuer nicht aufhoeren, er muss nur einmal
kurz stauen (Test-Anruf 27.07., 17:03:42).

Runtime-Test ohne Netz/DB: DeepgramClient wird gemockt, das uebergebene echte
DeepgramClientOptions-Objekt wird abgefangen und ueber seine Runtime-API bewertet
(is_keep_alive_enabled / url) — kein String-Vergleich am Quelltext.
"""

import pytest

import services.deepgram_service as deepgram_service
from config import DEEPGRAM_HOST

_TEST_SID = 'sid-keepalive-test'


class _FakeConnection:
    """Minimal-Ersatz fuer die Live-Websocket-Verbindung (kein Netz)."""

    def on(self, *args, **kwargs):
        return None

    def start(self, options):
        return True


class _FakeListen:
    def __init__(self, connection):
        self.websocket = self
        self._connection = connection

    def v(self, _version):
        return self._connection


def _make_fake_client(captured):
    class _FakeClient:
        def __init__(self, api_key, config=None):
            captured.append(config)
            self.listen = _FakeListen(_FakeConnection())

    return _FakeClient


@pytest.fixture
def captured_config(monkeypatch):
    captured = []
    monkeypatch.setattr(deepgram_service, 'DeepgramClient', _make_fake_client(captured))
    try:
        deepgram_service._open_deepgram_connection(_TEST_SID, mode='cold_call')
        assert captured and captured[0] is not None, 'Kein DeepgramClientOptions-Objekt abgefangen'
        yield captured[0]
    finally:
        # Kein Zustand ueber den Test hinaus (die Funktion traegt sich in beide Dicts ein).
        with deepgram_service._sessions_lock:
            deepgram_service._deepgram_sessions.pop(_TEST_SID, None)
            deepgram_service._cost_opened_at.pop(_TEST_SID, None)


def test_client_wird_mit_keepalive_gebaut(captured_config):
    # SDK 3.10.0 gibt den ROHEN Options-Wert zurueck ('true'), nicht bool True —
    # deshalb Truthiness statt Identitaets-Vergleich (verifiziert am installierten SDK).
    assert captured_config.is_keep_alive_enabled(), (
        'DeepgramClientOptions ohne Keepalive — Deepgram bricht bei kurzem Ton-Stau '
        'mit 1011 "did not receive audio data" ab.'
    )


def test_eu_host_override_bleibt_erhalten(captured_config):
    """Regressions-Schutz (POLISH-49 / DSGVO): der url=-Parameter darf beim Ergaenzen der
    Keepalive-Option nicht verloren gehen."""
    assert DEEPGRAM_HOST in (captured_config.url or ''), (
        f'DEEPGRAM_HOST ({DEEPGRAM_HOST}) fehlt in der Client-URL ({captured_config.url!r}) — '
        'der EU-Host-Override waere damit kaputt.'
    )
