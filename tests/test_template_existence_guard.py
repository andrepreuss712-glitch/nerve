"""Phase 08.23.2.AUTH-1 Plan 02 Task 2 — Template-Existenz-Guard (Deploy-Gate-Waechter).

Faengt jeden `render_template('...')`-String in routes/*.py + app.py, dessen Template-Datei fehlt —
SINGLE-LINE UND MULTILINE (Template-String auf der Folgezeile nach `render_template(`). Ein fehlendes
Template ist ein 500/Broken-Page zur Laufzeit; der Guard blockt den Deploy VORHER.

VALIDER Muster-Sweep (CLAUDE.md „Test-Qualitaets-Regel"): prueft ein Runtime-Constraint (jedes gerenderte
Template existiert), kein Function-Mock testet das direkt. Kein Source-Presence-False-Green: verschwindet
eine Template-Datei ODER kommt ein render_template auf ein fehlendes Template dazu -> rot.

FIX 1 (whitespace-tolerante Regex, `\\s*` zwischen `(` und Quote, `\\s` matcht `\\n`): faengt die 4 realen
MULTILINE-Calls (admin_dashboard.py:70 'admin/dashboard.html', admin_ewb.py:94 'admin/ewb_quality.html',
dashboard.py:965 'session_detail.html', payments.py:140 'pricing.html'). Die alte Single-Line-Regex verpasste
sie -> u.a. waere die pricing.html-Exemption NIE gefeuert (falsch-gruen auf einem realen Miss).

`_TEMPLATE_EXEMPT` = pricing.html: existiert HEUTE bewusst NICHT (AUTH-3 Welle 3 liefert sie); der
payments.py:140-141-Multiline-Call wird vom Guard ENTDECKT, aber via Exemption uebersprungen -> kein
falsches ROT auf HEAD. Selbst-loeschender Marker.

Verify NUR ueber `bash deploy.sh production` (CLAUDE.md „Kein Local-Dev"); auto-collected, kein live/perf-Marker.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent

_TEMPLATE_EXEMPT = frozenset({
    'pricing.html',  # 'pricing.html': AUTH-3 Welle 3 liefert die Datei und LOESCHT diesen Eintrag
})

# \s* faengt die 4 MULTILINE-Calls (payments.py:140-141 pricing.html, admin_dashboard.py:70-71,
# admin_ewb.py:94-95, dashboard.py:965-966); Suche ueber den ganzen Datei-Text, \s matcht \n.
_RENDER_RE = re.compile(r"render_template\(\s*['\"]([^'\"]+)['\"]")


def test_render_template_files_exist():
    src_files = list((_ROOT / 'routes').glob('*.py')) + [_ROOT / 'app.py']
    violations = []
    for src_file in src_files:
        src = src_file.read_text(encoding='utf-8', errors='replace')
        for m in _RENDER_RE.finditer(src):
            tmpl = m.group(1)
            if Path(tmpl).name in _TEMPLATE_EXEMPT:
                continue  # bewusst-noch-nicht-existierend (pricing.html: AUTH-3)
            if not (_ROOT / 'templates' / tmpl).exists():
                violations.append(f"{src_file.relative_to(_ROOT)} -> '{tmpl}' fehlt")
    assert not violations, "render_template auf fehlende Datei:\n  " + "\n  ".join(violations)
