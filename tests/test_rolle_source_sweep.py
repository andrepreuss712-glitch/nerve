"""Phase 08.23.2.AUTH-1 Plan 04 Task 1 — Rollen-Quellen-Sweep-Waechter (ERST-ROT gegen HEAD).

Erzwingt: die Rolle wird IMMER frisch aus der DB gelesen (`g.user.rolle`), NIE aus der Session-
Merk-Notiz (`session.get('rolle')` / `session['rolle']`). Ein session-Rolle-Reader ist die
Stale-Role-Klasse (Elevation of Privilege: eine Rollen-Aenderung wirkt erst nach Neu-Anmeldung).

VALIDER Muster-Sweep (CLAUDE.md „Test-Qualitaets-Regel"): prueft einen Runtime-Constraint (Rolle-
Quelle = DB, nicht Session) ueber routes/** UND templates/** — kein Function-Mock testet den ganzen
Sweep. Kein Source-Presence-False-Green: taucht irgendwo ein session-Rolle-Reader auf -> rot.

Fable-Erweiterung (Pruefpunkt 4, Ratsche): der Sweep scannt AUCH templates/** — sonst schluepft ein
zukuenftiger `session.get('rolle')`/`session['rolle']`-Reader in einem Jinja-Template durch.

Whitelist: NUR die Setzstelle routes/auth.py (auth.py:130 `session['rolle'] = user_rolle`, D-12) —
sie SCHREIBT die Session-Rolle (harmlos), liest sie nicht. Der Python-Reader-Regex matcht ohnehin
nur `.get('rolle'`, nicht die `[...]=`-Zuweisung; die Whitelist ist Belt-and-Suspenders.

Verify NUR ueber `bash deploy.sh production` (CLAUDE.md „Kein Local-Dev"); auto-collected.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent

# NUR der Setter (D-12) — schreibt session['rolle'], liest nicht.
_ROLLE_READER_WHITELIST = frozenset({'routes/auth.py'})

# Python (routes/*.py): `.get('rolle'` — matcht bewusst NICHT die Setter-Zuweisung session['rolle'] = ...
_PY_READER = re.compile(r"(?:flask_session|session)\.get\(\s*['\"]rolle['\"]")
# Jinja (templates/**): `session.get('rolle')` UND `session['rolle']` als Lese-Ausdruck.
_TPL_READER = re.compile(r"session(?:\.get\(\s*['\"]rolle['\"]|\[\s*['\"]rolle['\"]\s*\])")


def _line_no(src: str, pos: int) -> int:
    return src[:pos].count('\n') + 1


def test_no_session_rolle_readers():
    violations = []

    for p in sorted((_ROOT / 'routes').glob('*.py')):
        rel = p.relative_to(_ROOT).as_posix()
        if rel in _ROLLE_READER_WHITELIST:
            continue
        src = p.read_text(encoding='utf-8', errors='replace')
        for m in _PY_READER.finditer(src):
            violations.append(f"{rel}:{_line_no(src, m.start())}")

    for p in sorted((_ROOT / 'templates').rglob('*.html')):
        rel = p.relative_to(_ROOT).as_posix()
        if rel in _ROLLE_READER_WHITELIST:
            continue
        src = p.read_text(encoding='utf-8', errors='replace')
        for m in _TPL_READER.finditer(src):
            violations.append(f"{rel}:{_line_no(src, m.start())}")

    assert not violations, \
        "session-Rolle-Leser (nutze g.user.rolle):\n  " + "\n  ".join(violations)
