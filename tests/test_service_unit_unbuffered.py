"""Waechter: beide systemd-Units setzen PYTHONUNBUFFERED=1 im [Service]-Block.

Abgrenzung zur Test-Qualitaets-Regel (CLAUDE.md): das ist KEIN Source-Presence-Test
auf Python-Code, sondern die Pruefung eines Deployment-Konfigurations-Artefakts,
dessen Inhalt die einzige pruefbare Wahrheit ist (gleiches Muster wie das akzeptierte
tests/test_stt_model_parity.py). Ohne die Zeile puffert Python unter systemd blockweise
(~8KB) und die journal-Zeitstempel eines ganzen Anrufs klumpen Minuten spaeter zusammen
(Test-Anruf 27.07. — Ferndiagnose dadurch komplett falsch).
"""

import os
import re

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_UNITS = [
    os.path.join(_REPO_ROOT, 'deploy', 'nerve.service'),
    os.path.join(_REPO_ROOT, 'deploy', 'nerve-staging.service'),
]

_ENV_RE = re.compile(r'^\s*Environment=PYTHONUNBUFFERED=1\s*$')
_SECTION_RE = re.compile(r'^\s*\[(?P<name>[^\]]+)\]\s*$')


@pytest.mark.parametrize('unit_path', _UNITS, ids=[os.path.basename(p) for p in _UNITS])
def test_unit_setzt_pythonunbuffered_im_service_block(unit_path):
    assert os.path.isfile(unit_path), f'Unit-Datei fehlt: {unit_path}'

    with open(unit_path, 'r', encoding='utf-8') as fh:
        lines = fh.read().splitlines()

    treffer = [i for i, line in enumerate(lines) if _ENV_RE.match(line)]
    assert treffer, (
        f'{os.path.basename(unit_path)}: Zeile "Environment=PYTHONUNBUFFERED=1" fehlt — '
        'ohne sie klumpen die Log-Zeitstempel unter systemd.'
    )

    # Wirksamkeits-Bedingung: die Zeile muss INNERHALB von [Service] stehen.
    for idx in treffer:
        aktueller_block = None
        for i in range(idx):
            m = _SECTION_RE.match(lines[i])
            if m:
                aktueller_block = m.group('name')
        assert aktueller_block == 'Service', (
            f'{os.path.basename(unit_path)}: PYTHONUNBUFFERED steht in Block '
            f'[{aktueller_block}] statt in [Service] — dort waere sie wirkungslos.'
        )
