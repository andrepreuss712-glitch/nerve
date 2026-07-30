"""Waechter 3 (Ein-Schreiber-Sperre) — Phase 08.23.2.COUNTERPART.

'counterpart' darf nur an ZWEI Stellen entstehen:
  1. Init-Default in live_session.init_session_state (Dict-Literal beim Anlegen des States)
  2. handle_toggle_counterpart in deepgram_service (der einzige Umschalter)

Alles andere waere ein dritter Schreiber — genau die Konstellation, aus der der
urspruengliche Bug entstanden ist (Zustand an sieben Orten).

Grenze dieses Waechters (bewusst benannt, nicht ueberversprochen): ein statischer Sweep
sieht kein setattr() und keinen dynamisch gebauten Schluessel. Er faengt das reale
Muster (st['counterpart'] = ...), nicht jede denkbare Umgehung.

KEIN Source-Presence-False-Green: Test 1 prueft ein VERBOTENES Muster (Schreiber ausserhalb
der Whitelist), Test 2 ruft die echte Funktion auf und assertiert die State-Mutation.
"""
import ast
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SCAN_DIRS = ('services', 'routes')
_KEY = 'counter' + 'part'

# (relativer Pfad, umschliessende Funktion) — die EINZIGEN erlaubten Subscript-Schreiber.
_ALLOWED_WRITERS = frozenset({
    ('services/deepgram_service.py', 'handle_toggle_counterpart'),
})


def _enclosing_function(func_nodes, lineno):
    best = None
    for fn in func_nodes:
        if fn.lineno <= lineno <= (fn.end_lineno or fn.lineno):
            if best is None or fn.lineno > best.lineno:
                best = fn
    return best.name if best is not None else '<modul-ebene>'


def _iter_py_files():
    for d in _SCAN_DIRS:
        base = _ROOT / d
        if not base.is_dir():
            continue
        for path in base.rglob('*.py'):
            # Kompilierte Artefakte liegen in __pycache__ und tragen den alten Stand —
            # sie werden NIE geparst (ast.parse wuerde ohnehin scheitern).
            if '__pycache__' in path.parts:
                continue
            yield path


def _collect_writers():
    found = set()
    details = []
    for path in _iter_py_files():
        rel = path.relative_to(_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
        except SyntaxError:
            continue
        funcs = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for tgt in targets:
                if (isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.slice, ast.Constant)
                        and tgt.slice.value == _KEY):
                    fname = _enclosing_function(funcs, node.lineno)
                    found.add((rel, fname))
                    details.append(f'{rel}:{node.lineno}  in {fname}()')
    return found, details


def test_counterpart_has_exactly_one_assigning_writer():
    found, details = _collect_writers()
    extra = found - _ALLOWED_WRITERS
    missing = _ALLOWED_WRITERS - found
    assert not extra, (
        'Neuer counterpart-Schreiber ausserhalb der Whitelist:\n  '
        + '\n  '.join(f'{rel}  in {fn}()' for rel, fn in sorted(extra))
        + '\n\nAlle gefundenen Schreiber:\n  ' + '\n  '.join(details)
        + '\n\nEin-Schreiber-Sperre (Phase 08.23.2.COUNTERPART): counterpart entsteht nur '
          'im Init-Default (live_session.init_session_state) und im Toggle-Handler.'
    )
    assert not missing, (
        f'Erwarteter counterpart-Schreiber fehlt: {sorted(missing)}. '
        'Gefunden wurde:\n  ' + '\n  '.join(details)
    )


def test_init_session_state_seeds_counterpart():
    """Laufzeit-Beleg fuer den zweiten erlaubten Schreiber (Dict-Literal, AST-unsichtbar)."""
    import services.live_session as ls
    sid = 'test-counterpart-single-writer-001'
    try:
        ls.init_session_state(sid, 1, 1)
        with ls._session_state_lock:
            st = ls._session_state[sid]['state']
        assert st['counterpart'] == 'gatekeeper', (
            f"Init-Default (cold_call) muss 'gatekeeper' sein, war: {st['counterpart']!r}")
    finally:
        with ls._session_state_lock:
            ls._session_state.pop(sid, None)


def test_init_session_state_meeting_seeds_decision_maker():
    """Meeting-Regressions-Waechter: zu einem Termin sitzt man beim Entscheider.

    Ohne diese Kopplung liefe JEDER Meeting-Anruf bis zum ersten manuellen Toggle still
    im 4-Phasen-Sekretaersmodell (Cross-AI-Fund 2026-07-28).
    """
    import services.live_session as ls
    sid = 'test-counterpart-single-writer-002'
    try:
        ls.init_session_state(sid, 1, 1, mode='meeting')
        with ls._session_state_lock:
            st = ls._session_state[sid]['state']
        assert st['counterpart'] == 'decision_maker', (
            f"Meeting muss beim Entscheider starten, war: {st['counterpart']!r}")
    finally:
        with ls._session_state_lock:
            ls._session_state.pop(sid, None)


def test_guard_actually_scans_something():
    files = list(_iter_py_files())
    assert len(files) >= 15, f'Sweep sieht nur {len(files)} Dateien — Pfad-Logik kaputt?'
