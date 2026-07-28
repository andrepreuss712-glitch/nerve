"""Waechter: eine Sendung in eine TOTE Deepgram-Verbindung verschwindet nicht mehr lautlos.

SOFORT-PAKET 27.07. FIX 4. Das Deepgram-SDK wirft bei toter Verbindung KEINEN Fehler:
es gibt still False zurueck und schluckt die Ausnahme intern
(deepgram/clients/common/v1/abstract_sync_websocket.py:387-447). Unser alter Code fing nur
*geworfene* Fehler -> die Ton-Brocken #600-#800 des Test-Anrufs verschwanden lautlos.

Bewusst NUR Logging, KEIN Wiederaufbau (spaetere Phase).

Function-Call-Return- + State-Mutation-Test mit Schein-Verbindung: kein Netz, keine DB.
"""

import pytest

import services.deepgram_service as deepgram_service

_SID_TOT = 'sid-tot'
_SID_OK = 'sid-ok'
_SID_NONE = 'sid-none'
_SID_RAISE = 'sid-raise'


class _ToteVerbindung:
    def send(self, data):
        return False


class _GesundeVerbindung:
    def send(self, data):
        return True


class _NoneVerbindung:
    """Aeltere/andere Implementierung gibt None zurueck — darf KEINEN Fehlalarm ausloesen."""

    def send(self, data):
        return None


class _WerfendeVerbindung:
    def send(self, data):
        raise RuntimeError('websocket kaputt')


@pytest.fixture(autouse=True)
def _kein_zustand_uebrig():
    yield
    for sid in (_SID_TOT, _SID_OK, _SID_NONE, _SID_RAISE):
        deepgram_service._send_fail_counts.pop(sid, None)


def test_tote_verbindung_loggt_erste_fehlsendung(capsys):
    ok = deepgram_service._send_audio_chunk(_SID_TOT, _ToteVerbindung(), b'\x00' * 32, chunk_no=600)
    assert ok is False
    out = capsys.readouterr().out
    assert 'Send fehlgeschlagen' in out
    assert f'sid={_SID_TOT}' in out
    assert 'chunk=#600' in out
    assert deepgram_service._send_fail_counts[_SID_TOT] == 1


def test_log_flut_wird_gedrosselt(capsys):
    deepgram_service._send_audio_chunk(_SID_TOT, _ToteVerbindung(), b'\x00' * 4, chunk_no=1)
    capsys.readouterr()  # erste Zeile abraeumen

    verbindung = _ToteVerbindung()
    for i in range(2, 102):  # Fehlschlaege 2..101 -> nur der 100. loggt
        deepgram_service._send_audio_chunk(_SID_TOT, verbindung, b'\x00' * 4, chunk_no=i)

    zeilen = [z for z in capsys.readouterr().out.splitlines() if 'Send fehlgeschlagen' in z]
    assert len(zeilen) == 1, f'Erwartet genau 1 zusaetzliche Zeile (der 100.), bekam {len(zeilen)}'
    assert 'fehl_sendungen=100' in zeilen[0]
    assert deepgram_service._send_fail_counts[_SID_TOT] == 101


def test_gesunde_verbindung_loggt_nichts(capsys):
    ok = deepgram_service._send_audio_chunk(_SID_OK, _GesundeVerbindung(), b'\x00' * 4, chunk_no=5)
    assert ok is True
    assert 'Send fehlgeschlagen' not in capsys.readouterr().out
    assert _SID_OK not in deepgram_service._send_fail_counts


def test_none_rueckgabe_ist_kein_fehlalarm(capsys):
    ok = deepgram_service._send_audio_chunk(_SID_NONE, _NoneVerbindung(), b'\x00' * 4, chunk_no=7)
    assert ok is True
    assert 'Send fehlgeschlagen' not in capsys.readouterr().out
    assert _SID_NONE not in deepgram_service._send_fail_counts


def test_geworfene_ausnahme_behaelt_bestehenden_pfad(capsys):
    """Beweis, dass beim Umbau kein Verhalten verloren ging: die alte 'Send error'-Zeile bleibt."""
    ok = deepgram_service._send_audio_chunk(_SID_RAISE, _WerfendeVerbindung(), b'\x00' * 4, chunk_no=9)
    assert ok is False
    out = capsys.readouterr().out
    assert 'Send error' in out
    assert f'sid={_SID_RAISE}' in out


def test_close_raeumt_den_zaehler_weg():
    """Kein Zaehler-Leck ueber Anrufe hinaus: _close_deepgram_connection raeumt per sid auf."""
    deepgram_service._send_fail_counts[_SID_TOT] = 42
    deepgram_service._close_deepgram_connection(_SID_TOT)
    assert _SID_TOT not in deepgram_service._send_fail_counts
