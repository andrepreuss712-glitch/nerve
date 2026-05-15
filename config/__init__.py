# config-Package -- Hysterese-Konfig, Phase-Transition-Matrix.
# Neu in Phase 08.23.2.C (per RESEARCH.md: config/ existierte noch nicht).
#
# Deviation Rule 3 (Plan 06, Task 2): config/-Package shadowed config.py-Modul.
# Alle Services importieren 'from config import ...' und erwarten die Konstanten
# aus config.py (ANALYSE_INTERVALL, MERGE_WINDOW_S, etc.).
# Loesung: config.py-Inhalte via importlib laden und in diesem __init__ re-exportieren.
# So bleibt 'from config import ANALYSE_INTERVALL' funktionsfaehig.
import importlib.util as _ilu
import os as _os
import sys as _sys

_config_py = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'config.py')
if _os.path.exists(_config_py):
    _spec = _ilu.spec_from_file_location('_config_legacy', _config_py)
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    # Re-export alle public-Namen aus config.py in dieses Package-Namespace
    for _k, _v in vars(_mod).items():
        if not _k.startswith('_'):
            globals()[_k] = _v
    del _spec, _mod
del _ilu, _os, _sys, _config_py, _k, _v
