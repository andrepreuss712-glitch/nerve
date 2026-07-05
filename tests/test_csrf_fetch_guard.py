"""Phase 08.23.2.AUTH-1 Plan 02 Task 1 — CSRF-Fetch-Guard (Deploy-Gate-Waechter).

VALIDER Muster-Sweep-Grenzfall (CLAUDE.md „Test-Qualitaets-Regel", KEIN Source-Presence-False-Green):
Der Guard prueft (1) einen Runtime-Constraint (jeder base-erbende Schreib-fetch ist token-abgedeckt,
weil base.html den globalen window.fetch-Wrapper traegt) und (3) ein VERBOTENES Muster (raw XHR-Write /
sendBeacon umgeht den Wrapper). Kein Function-Mock testet das direkt — analog test_no_live_global_state.py.
Entfernt jemand den Wrapper-Marker -> rot; fuegt jemand einen Bypass hinzu -> rot.

DREI CHECKS:
  (1) Wrapper-Praesenz: templates/base.html traegt `window.fetch =` (Plan 01 Marker). Fehlt er, verliert
      JEDES base-erbende Template still seine CSRF-Abdeckung.
  (2) standalone-Eigenabdeckung mit EXAKT-base.html-Target-Match: ein Template gilt NUR dann als vom
      base.html-Wrapper abgedeckt, wenn sein {% extends %}-TARGET EXAKT 'base.html' ist. Kein extends
      ODER anderes Target (z.B. admin/master.html) -> standalone -> muss Meta-Tag + Wrapper SELBST tragen.
      `_`-Prefix-Include-Snippets ausgenommen (base-Wrapper deckt sie zur Laufzeit ab). Die 3
      admin/master.html-erbenden Flask-Admin-Seiten per _STANDALONE_WRAPPER_EXEMPT exempt (Backlog Punkt 17,
      EXAKT-Dateiname-Scope -> eine 4. solche Seite waere RED).
  (3) Forbidden-Bypass: `.open('POST'|'PUT'|'PATCH'|'DELETE'` (XHR-Write) + `navigator.sendBeacon(`
      rekursiv ueber templates/** + static/** (Vendor ausgeschlossen) -> aktiv gefangen.

RESIDUALE, statisch NICHT (voll) fangbare Loecher (bewusst dokumentiert, KEIN „akzeptiert" fuer XHR/Beacon):
  (a) `fetch` ueber eine aliasierte/Options-Variable, die der statische Scan nicht aufloest (Runtime-Wrapper deckt den Pfad).
  (b) ein GEFAELSCHTER `window.fetch =`-Marker INNERHALB eines HTML/JS-KOMMENTARS befriedigt den naiven Grep (marker-fake).
  (c) die `{%-`-Trim-extends-Variante — hier BEREITS toleriert via `_EXTENDS_RE = \\{%-?\\s*extends`, kein Miss.
XMLHttpRequest + navigator.sendBeacon sind AKTIV GEFANGEN (Check 3), NICHT in der „akzeptiert"-Liste.

Verify NUR ueber `bash deploy.sh production` (CLAUDE.md „Kein Local-Dev"); auto-collected, kein live/perf-Marker.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent

# Bewusst exempte state-changing Endpunkte (externe Signatur-Pruefung statt CSRF).
_CSRF_EXEMPT = frozenset({
    '/stripe/webhook',            # Stripe-Webhook: externe Signatur-Pruefung statt CSRF
    'accounts.google.com',        # Google OAuth callback
    'login.microsoftonline.com',  # Microsoft OAuth callback
})

_VENDOR_DIRS = ('vendor', 'lib', 'libs', 'min', 'node_modules', 'dist')

# Grep-verifizierbare Marker (exakt aus Plan 01 Task 2).
_WRAPPER_MARKER = 'window.fetch ='          # Plan 01 Override-Zeile
_META_TOKEN_MARKER = '<meta name="csrf-token"'

# EXAKTER base.html-Target-Match: "vom base.html-Wrapper abgedeckt" NUR wenn extends-Target EXAKT
# 'base.html'. Kein extends ODER anderes Target (z.B. admin/master.html) -> standalone (selbst decken).
# Tolerant gegen {%- Trim, single/double Quotes, umgebende Whitespaces.
_EXTENDS_RE = re.compile(r"""\{%-?\s*extends\s+['\"]([^'\"]+)['\"]""")
_BASE_TEMPLATE = 'base.html'

# Diese 3 erben admin/master.html (Flask-Admin-Parent), NICHT base.html -> ausserhalb der
# window.fetch-Wrapper-Abdeckung. CSRF-Abdeckung = SEPARATES Backlog (Punkt 17, kein AUTH-1-Refactor).
# SCOPE = EXAKT diese 3 Dateinamen: eine ZUKUENFTIGE 4. admin/master.html-Seite mit state-changing
# fetch faellt NICHT unter die Exemption -> RED (Ratschen-Integritaet).
_STANDALONE_WRAPPER_EXEMPT = frozenset({
    'admin/crm_overview.html',   # heute: fetch('/admin/crm/note', POST) auf :155 (unabgedeckt)
    'admin/kpi_dashboard.html',  # heute kein state-changing fetch; admin/master.html-Familie
    'admin/planning_list.html',  # heute kein state-changing fetch; admin/master.html-Familie
})

# state-changing fetch(...) im Options-Block (single-line + multiline, bis zum ersten ';').
_STATE_CHANGING_FETCH = re.compile(
    r"fetch\([^;]*?method:\s*['\"](POST|PUT|PATCH|DELETE)['\"]",
    re.IGNORECASE | re.DOTALL,
)

# Forbidden-Bypass: raw request APIs, die window.fetch umgehen.
_XHR_WRITE = re.compile(r"""\.open\(\s*['\"](POST|PUT|PATCH|DELETE)['\"]""", re.IGNORECASE)
_SENDBEACON = re.compile(r"navigator\.sendBeacon\(")


def _is_vendor(path: Path) -> bool:
    return any(part in _VENDOR_DIRS for part in path.parts) or path.name.endswith('.min.js')


def _is_include_snippet(path: Path) -> bool:
    # Projekt-Konvention: '_'-Prefix-Basename = {% include %}-Fragment, laeuft im Kontext einer
    # base-erbenden Seite -> base.html-Wrapper deckt es zur Laufzeit ab.
    # Beispiele: templates/admin/_tab_ausgaben.html, templates/_tooltip.html.
    return path.name.startswith('_')


def _extends_target(src: str):
    m = _EXTENDS_RE.search(src)
    return m.group(1).strip() if m else None


def _is_standalone(src: str) -> bool:
    # standalone (nicht base-abgedeckt) = kein extends ODER extends-Target != base.html
    return _extends_target(src) != _BASE_TEMPLATE


def _line_no(src: str, pos: int) -> int:
    return src[:pos].count('\n') + 1


def _target_is_exempt(src: str, match: re.Match) -> bool:
    # best-effort: das erste String-Literal nach der Match-Position ist (i.d.R.) die Ziel-URL.
    tail = src[match.start():match.start() + 200]
    m = re.search(r"""['\"]([^'\"]+)['\"]""", tail)
    if not m:
        return False
    url = m.group(1)
    return any(ex in url for ex in _CSRF_EXEMPT)


def test_base_html_carries_fetch_wrapper():
    base = _ROOT / 'templates' / 'base.html'
    src = base.read_text(encoding='utf-8', errors='replace')
    assert _WRAPPER_MARKER in src, \
        "base.html ohne window.fetch-Wrapper (Plan 01 Marker fehlt): templates/base.html"


def test_standalone_templates_self_cover_csrf():
    tmpl_root = _ROOT / 'templates'
    candidates = [
        p for p in tmpl_root.rglob('*.html')
        if not _is_vendor(p)
        and not _is_include_snippet(p)  # _-Prefix = {% include %}-Snippet, base-Wrapper deckt es zur Laufzeit ab (FACT C)
        and p.relative_to(tmpl_root).as_posix() not in _STANDALONE_WRAPPER_EXEMPT  # admin/master.html-Familie, Backlog Punkt 17; EXAKT-Dateiname-Scope, 4. Seite waere RED (FACT D)
    ]
    violations = []
    for p in candidates:
        src = p.read_text(encoding='utf-8', errors='replace')
        # EXAKT-base-Target: crm_overview/kpi_dashboard/planning_list erben admin/master.html -> Target
        # != base.html -> waeren standalone, sind aber oben schon aus der Iteration entfernt.
        if _is_standalone(src) and _STATE_CHANGING_FETCH.search(src):
            if _WRAPPER_MARKER not in src or _META_TOKEN_MARKER not in src:
                fehlt = ('meta-token ' if _META_TOKEN_MARKER not in src else '') + \
                        ('wrapper' if _WRAPPER_MARKER not in src else '')
                violations.append(f"{p.relative_to(_ROOT)} (fehlt: {fehlt.strip()})")
    assert not violations, \
        "standalone-Template mit state-changing fetch ohne Eigenabdeckung (meta-token + window.fetch-Wrapper):\n  " \
        + "\n  ".join(violations)


def test_no_raw_request_bypass():
    scan = [
        p for p in list((_ROOT / 'templates').rglob('*.html')) + list((_ROOT / 'static').rglob('*.js'))
        if not _is_vendor(p)
    ]
    violations = []
    for p in scan:
        src = p.read_text(encoding='utf-8', errors='replace')
        for m in list(_XHR_WRITE.finditer(src)) + list(_SENDBEACON.finditer(src)):
            if not _target_is_exempt(src, m):
                violations.append(f"{p.relative_to(_ROOT)}:{_line_no(src, m.start())}")
    assert not violations, \
        "raw XHR-Write / sendBeacon umgeht den window.fetch-Wrapper:\n  " + "\n  ".join(violations)
