"""Waechter 2 (Wortschatz-Sperre) — Phase 08.23.2.COUNTERPART.

Der Gespraechspartner hatte drei Namen an sieben Orten. Nach dem Abriss heisst er
ueberall 'counterpart'. Dieser Sweep macht jede Rueckkehr der alten Zustands- und
Event-BEZEICHNER in services/, routes/, static/ und templates/ rot.

Abgrenzung (wichtig): verboten sind BEZEICHNER, nicht Vokabular. 'gatekeeper' bleibt ein
gueltiger counterpart-WERT und ist ausserdem ein voellig unbeteiligter Outcome-Wert im
Bestand (gatekeeper_blocked in templates/dashboard.html). Wer 'gatekeeper' ins Muster
aufnimmt, faerbt die halbe Codebasis rot — genau das ist hier NICHT gemeint.

Scope-Entscheidung: tests/ ist NICHT im Sweep. Die Absenz-Assertion in
test_live_session_gatekeeper.py muss die alten Schluesselnamen nennen duerfen.

Kompilat-Ausschluss (explizit, nicht beilaeufig): __pycache__-Verzeichnisse und .pyc-Dateien
werden IMMER uebersprungen. Stale Bytecode aus der Zeit VOR dem Umbau traegt die alten
Bezeichner als Bytes weiter (belegt 2026-07-30: routes/__pycache__/app_routes.cpython-311.pyc)
— ein Sweep, der darauf rot wird, meldet Vergangenheit statt Quelltext. Zwei unabhaengige
Filter: (1) Verzeichnisname __pycache__, (2) Endungs-Whitelist .py/.js/.html.

KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel): geprueft wird ein
VERBOTENES Muster, nicht die Existenz erwuenschten Codes. Ein False-Green kann nicht
entstehen — kehrt das Muster zurueck, roetet es den Test. Dokumentierter Regex-Grenzfall;
eine Mock-bare Funktion, die 'kein Code nutzt dieses Wort mehr' beweisen koennte,
existiert nicht.
"""
from pathlib import Path

_ROOT = Path(__file__).parent.parent
# templates/ ist mit im Scope, weil das Knopf-Markup dort liegt (base.html:586) und in
# Welle 1 umgebaut wurde. HEUTE steht dort keiner der verbotenen Bezeichner (verifiziert
# 2026-07-30: 0 Treffer) — der Scan ist VORBEUGEND (haelt die Sperre gueltig, wenn das
# Markup spaeter wieder angefasst wird), nicht Loch-schliessend.
_SCAN_DIRS = ('services', 'routes', 'static', 'templates')
_SCAN_SUFFIXES = ('.py', '.js', '.html')

# Verzeichnisse, die NIE gescannt werden. __pycache__ enthaelt kompilierten Bytecode aus
# der Zeit vor dem Umbau — dort stehen die alten Bezeichner als Byte-Literale drin.
_SKIP_DIR_NAMES = frozenset({'__pycache__'})

# VERBOTEN sind die alten ZUSTANDS-/EVENT-BEZEICHNER — NICHT das Vokabular.
# NIEMALS das blosse Wort 'gatekeeper' aufnehmen: gueltiger counterpart-Wert +
# unbeteiligter Outcome-Wert 'gatekeeper_blocked' (templates/dashboard.html:792,877,
# 881,956,960). Eine solche "Verschaerfung" faerbt die halbe Codebasis rot.
# Fragmentiert zusammengesetzt, damit diese Datei sich nicht selbst findet,
# falls der Scope je erweitert wird.
_FORBIDDEN = (
    'current' + '_mode',
    'contact' + '_category',
    'contact' + 'Category',
    'current' + 'Mode',         # Browser-Kopie (pip-launcher.js:2637) — Camel-Case ohne
                                # Unterstrich, vom alten Muster NICHT gefangen
    'manual' + '_mode_toggle',  # geloeschtes Socket-Event (deckt auch _ack ab)
)

# Fremd-Assets, die zufaellig treffen wuerden. Leer lassen, solange nichts noetig ist —
# JEDER Eintrag braucht eine Begruendung im Kommentar.
_IGNORED_FILES: frozenset = frozenset()


def _iter_source_files():
    for d in _SCAN_DIRS:
        base = _ROOT / d
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            # Filter 1: kompilierte Artefakte per Verzeichnisname.
            if _SKIP_DIR_NAMES & set(path.parts):
                continue
            # Filter 2: Endungs-Whitelist (schliesst .pyc/.pyo zusaetzlich aus).
            if path.suffix not in _SCAN_SUFFIXES or not path.is_file():
                continue
            if path.relative_to(_ROOT).as_posix() in _IGNORED_FILES:
                continue
            yield path


def test_forbidden_counterpart_vocabulary_absent():
    violations = []
    for path in _iter_source_files():
        rel = path.relative_to(_ROOT).as_posix()
        text = path.read_text(encoding='utf-8', errors='ignore')
        for line_no, line in enumerate(text.splitlines(), start=1):
            for word in _FORBIDDEN:
                if word in line:
                    violations.append(f'{rel}:{line_no}  [{word}]  {line.strip()[:100]}')
    assert not violations, (
        'Alter Gespraechspartner-Wortschatz zurueck in services/routes/static '
        f'({len(violations)} Treffer):\n  ' + '\n  '.join(violations)
        + '\n\nPhase 08.23.2.COUNTERPART: der Gespraechspartner heisst counterpart '
          "('gatekeeper' | 'decision_maker'), die Anruf-Art heisst call_type "
          "('cold_call' | 'meeting'). Keine Wort-Ueberlappung."
    )


def test_guard_actually_scans_something():
    """Falsifizierbarkeit: der Sweep muss echte Dateien sehen.

    Ohne diesen Test waere ein kaputter Pfad ein stiller Gruen-Macher (0 Dateien
    gescannt = 0 Verstoesse = gruen).
    """
    files = list(_iter_source_files())
    assert len(files) >= 20, f'Sweep sieht nur {len(files)} Dateien — Pfad-Logik kaputt?'
    names = {p.name for p in files}
    for expected in ('live_session.py', 'deepgram_service.py', 'pip-launcher.js',
                     'base.html'):
        assert expected in names, f'{expected} nicht im Sweep-Scope'


def test_guard_skips_compiled_bytecode():
    """Stale .pyc darf den Waechter NICHT roeten (Orchestrator-Befund 2026-07-30).

    Kompilierter Bytecode aus der Zeit vor dem Umbau traegt die alten Bezeichner als
    Bytes weiter. Der Sweep meldet Quelltext, nicht Vergangenheit.
    """
    scanned = [p.relative_to(_ROOT).as_posix() for p in _iter_source_files()]
    assert not [p for p in scanned if '__pycache__' in p], (
        '__pycache__-Dateien im Sweep-Scope: ' + str(scanned[:5]))
    assert not [p for p in scanned if p.endswith(('.pyc', '.pyo'))], (
        'Kompilierte Artefakte im Sweep-Scope: ' + str(scanned[:5]))
