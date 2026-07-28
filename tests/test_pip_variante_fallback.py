"""Waechter: der frueh-abbrechende Fehlerpfad von streame_manual_ewb_variante meldet sich.

SOFORT-PAKET 27.07. FIX 5 (Server-Haelfte). Scheitert der Aufbau des Auftragstexts
(answer_system_content), gab die Funktion frueher nur ein Fehler-Objekt zurueck — OHNE
pip_stream_error zu senden. Ergebnis im PiP: kein KI-Aufruf UND keine Fehlermeldung,
der Slot-1-Platzhalter "Variante wird gebaut…" blieb ewig stehen (Test-Anruf 27.07.).

Offline: kein Anthropic-Call, keine DB, kein Netz — answer_system_content wirft, socketio.emit
ist ein Sammler. Function-Call-Return- + State-Mutation-Test.

Browser-Haelfte (10s-Sicherungs-Timer in pip-launcher.js): kein automatisierter Waechter
moeglich — im Repo existiert keine JS-Test-Infrastruktur. Ein
`open('pip-launcher.js').read() + assert 'setTimeout' in src` waere ein Source-Presence-
False-Green (CLAUDE.md) und ist bewusst NICHT geschrieben. Verifikation im Live-Test.
"""

import pytest

import extensions
import services.prompt_pipeline as prompt_pipeline
from services.claude_service import streame_manual_ewb_variante

_SID = 'sid-fallback-test'


def _raiser(*args, **kwargs):
    raise RuntimeError('kaputt')


class _SammelSocketIO:
    """Ersatz fuer extensions.socketio: ausserhalb der App ist es None (extensions.py:4),
    deshalb wird das GANZE Objekt gesetzt, nicht nur dessen emit-Attribut."""

    def __init__(self):
        self.emits = []

    def emit(self, event, payload=None, **kwargs):
        self.emits.append((event, payload, kwargs.get('room')))


@pytest.fixture
def emits(monkeypatch):
    sammler = _SammelSocketIO()
    monkeypatch.setattr(prompt_pipeline, 'answer_system_content', _raiser)
    monkeypatch.setattr(extensions, 'socketio', sammler)
    return sammler.emits


def test_fehlerpfad_sendet_pip_stream_error(emits):
    result = streame_manual_ewb_variante('zu_teuer', {}, '', _SID, slot=1)

    fehler_emits = [e for e in emits if e[0] == 'pip_stream_error']
    assert len(fehler_emits) == 1, f'Erwartet genau 1 pip_stream_error, bekam: {emits}'
    _event, payload, room = fehler_emits[0]
    assert payload.get('slot') == 1
    assert room == _SID
    assert payload.get('error')

    # Beweis, dass wirklich der frueh-abbrechende Pfad getestet wurde:
    assert not [e for e in emits if e[0] == 'pip_stream_start'], \
        f'pip_stream_start darf im Fehlerpfad NICHT kommen: {emits}'

    # Rueckgabe-Vertrag unveraendert — deepgram_service._run liest genau diese Felder.
    assert result['error']
    assert result['gegenargument_1'] is None
