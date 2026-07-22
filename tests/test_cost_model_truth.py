"""Phase 08.23.2.KOSTEN-1.1 Welle 2 — W4 Modellnamen-Wahrheits-Waechter (statischer AST-Abgleich).

WOFUER (Fehlerklasse): eine Funktion RUFT ein Modell auf (`*.messages.create/stream(model=...)`)
und BUCHT dabei die Kosten unter einem hart codierten Modellnamen (`log_api_cost('anthropic',
'<literal>', ...)`), dessen Kosten-KLASSE (Haiku vs. Sonnet, via `normalize_model_name`) NICHT zu
dem tatsaechlich aufgerufenen `config.MODEL_*`-Modell passt. Belegter Fall: `streame_manual_ewb_variante`
ruft Sonnet (`config.MODEL_PIP_VARIANTE = claude-sonnet-4-5`), buchte aber seit jeher `'haiku-4-5'`
-> Sonnet-Kosten (~3x) wurden als Haiku verbucht, die Marge war still zu schoen.

WARUM AST STATT LAUFZEIT (Punkt 27 + CLAUDE.md-Grenzfall): der Defekt-Pfad haengt an
`messages.stream` + SocketIO + prompt_pipeline. Ein Laufzeit-Mock waere ein schweres Harness fuer
eine rein STATISCHE Wahrheit ("passt der gebuchte Literal-Name zur Kosten-Klasse des an derselben
Stelle gerufenen config.MODEL_*-Modells?"). Das ist genau der in CLAUDE.md dokumentierte Grenzfall
"inspect/AST fuer Runtime-Constraints OK, wenn kein Function-Mock die Constraint direkt testbar macht".

WARUM KEIN SOURCE-PRESENCE-FALSE-GREEN (Test-Qualitaets-Regel): dieser Waechter prueft nicht, ob ein
String im Quelltext STEHT. Er parst die STRUKTUR (das `model=`-Argument des Modell-Aufrufs gegen das
zweite Argument der `log_api_cost`-Buchung), loest beide ueber `config` + `normalize_model_name` auf
und wird ROT, wenn die WERTE (Kosten-Klassen) auseinanderlaufen — nicht, wenn ein String fehlt. Ein
reiner Umbau ohne Klassen-Drift bleibt gruen; ein Klassen-Widerspruch wird rot, egal wie der Code
formuliert ist.

BEWUSSTE GRENZEN (verbindlich — NICHT "verbessern"):
- **W4 sieht nur LITERAL-Buchungen.** Buchungen ueber eine Variable (`_model_autovar`, `_cost_model`,
  `_m`, oder `config.MODEL_X` direkt als Arg 2) UEBERSPRINGT der Waechter — die decken sich per
  Konstruktion mit dem Aufruf (selbe Variable) bzw. werden zur LAUFZEIT von W3 (Skip-Zaehler,
  `tests/test_cost_skip_counter.py`) gedeckt.
- **W4 faengt ueber die Kosten-KLASSE (Haiku vs. Sonnet), nicht ueber die exakte Modell-VERSION.**
  Ein Literal, das per config auf die falsche Variable derselben Klasse zeigt, sieht W4 nicht.
- **W3/Skip-Zaehler fuellt eine ANDERE Luecke:** er fuellt nur FEHLENDE Raten, nicht FALSCHE Namen mit
  gueltiger Rate. Genau diese Luecke schliesst W4 — der belegte Defekt hatte eine GUELTIGE Haiku-Rate
  und floss deshalb NIE in den Skip-Zaehler; W1/W2/W3 konnten ihn strukturell nicht fangen.
- **W4 haengt an der Modell-Einstellung der Testumgebung:** er loest `config.MODEL_*` zur Analysezeit
  auf. Aendert sich der config-Default oder wird per ENV ueberschrieben, aendert sich die Soll-Klasse
  mit. Bewusste Grenze — der Waechter prueft die Wahrheit RELATIV zur aktiven config.

real-PG NICHT noetig: reiner Struktur-Check, kein db_session, kein Cleanup.
"""
from __future__ import annotations

import ast
from pathlib import Path

import config
from services.cost_tracker import normalize_model_name

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ('services', 'routes', 'nerve_rt')


def _own_nodes(func: ast.AST):
    """Alle Nachfahren-Knoten von `func`, OHNE in verschachtelte Funktionen abzusteigen.

    So bleibt die Analyse pro Funktion sauber gekapselt: eine Buchung/ein Aufruf in einer
    inneren Funktion zaehlt nur zu DIESER inneren Funktion (die separat besucht wird).
    """
    for child in ast.iter_child_nodes(func):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield child
        yield from _own_nodes(child)


def _is_log_api_cost(call: ast.Call) -> bool:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id == 'log_api_cost'
    if isinstance(f, ast.Attribute):
        return f.attr == 'log_api_cost'
    return False


def _is_messages_call(call: ast.Call) -> bool:
    """`X.messages.create(...)` / `X.messages.stream(...)` — Anthropic-Modell-Aufruf."""
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr in ('create', 'stream')):
        return False
    inner = f.value
    return isinstance(inner, ast.Attribute) and inner.attr == 'messages'


def _string_const(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _config_attr(node: ast.AST):
    """Gibt den Attributnamen zurueck, wenn `node` == `config.MODEL_*` ist, sonst None."""
    if (isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == 'config'
            and node.attr.startswith('MODEL')):
        return node.attr
    return None


def _collect_assignments(own_nodes) -> dict[str, list[ast.AST]]:
    """name -> Liste der RHS-Ausdruecke (nur einfache `Name = value`-Zuweisungen)."""
    assigns: dict[str, list[ast.AST]] = {}
    for n in own_nodes:
        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                if isinstance(tgt, ast.Name):
                    assigns.setdefault(tgt.id, []).append(n.value)
    return assigns


def _resolve_model_config_attr(expr: ast.AST, assigns: dict[str, list[ast.AST]]):
    """Loest den model=-Ausdruck EIN-SCHRITT auf einen config.MODEL_*-Attributnamen auf.

    - `config.MODEL_X` direkt -> 'MODEL_X'
    - `<name>`, in derselben Funktion GENAU EINMAL via `<name> = config.MODEL_X` gesetzt -> 'MODEL_X'
    - mehrfache/andere Zuweisung (z.B. Fallback auf ein Literal) -> None (konservativ: mehrdeutig).
    """
    attr = _config_attr(expr)
    if attr:
        return attr
    if isinstance(expr, ast.Name):
        rhss = assigns.get(expr.id)
        if rhss and len(rhss) == 1:
            return _config_attr(rhss[0])
    return None


def _find_violations() -> list[tuple[str, int, str, str, str, str, str]]:
    """Sweep ueber SCAN_DIRS. Rueckgabe pro Verstoss:
    (relpath, lineno, funcname, booked_literal, booked_class, called_config_attr, called_class).
    """
    violations = []
    for rel in SCAN_DIRS:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in base.rglob('*.py'):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (OSError, SyntaxError):  # pragma: no cover - defensiv
                continue
            relpath = path.relative_to(REPO_ROOT).as_posix()
            for func in ast.walk(tree):
                if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                own = list(_own_nodes(func))
                assigns = _collect_assignments(own)

                # (a) Literal-Buchungen: log_api_cost('anthropic', '<literal>', ...)
                literal_bookings = []  # (lineno, literal)
                # (b) aufgeloeste Anthropic-Modell-Klassen aus messages.create/stream(model=...)
                called = {}  # config_attr -> class
                for n in own:
                    if not isinstance(n, ast.Call):
                        continue
                    if _is_log_api_cost(n) and len(n.args) >= 2:
                        if _string_const(n.args[0]) == 'anthropic':
                            lit = _string_const(n.args[1])
                            if lit is not None:
                                literal_bookings.append((n.lineno, lit))
                    elif _is_messages_call(n):
                        model_kw = next((kw.value for kw in n.keywords
                                         if kw.arg == 'model'), None)
                        if model_kw is None:
                            continue
                        attr = _resolve_model_config_attr(model_kw, assigns)
                        if attr is not None:
                            val = getattr(config, attr, None)
                            called[attr] = normalize_model_name(val)

                if not literal_bookings:
                    continue
                distinct_classes = set(called.values())
                if len(distinct_classes) != 1:
                    # 0 = unaufloesbar, >1 = mehrdeutig -> konservativ NICHT werten (Doku: Grenze).
                    continue
                called_attr = next(iter(called))
                called_class = next(iter(distinct_classes))
                for lineno, lit in literal_bookings:
                    if normalize_model_name(lit) != called_class:
                        violations.append((
                            relpath, lineno, func.name,
                            lit, normalize_model_name(lit),
                            called_attr, called_class,
                        ))
    return violations


def test_scanner_finds_something():
    """Blind-Gruen-Schutz (W1-Lehre): der Sweep MUSS ueberhaupt Literal-Buchungen finden.

    Findet er keine, ist der Scanner kaputt (falsche Pfade, geaenderte Aufruf-Form) und
    `test_no_booked_literal_contradicts_called_model` waere still blind-gruen.
    """
    count = 0
    for rel in SCAN_DIRS:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in base.rglob('*.py'):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (OSError, SyntaxError):  # pragma: no cover
                continue
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and _is_log_api_cost(n) and len(n.args) >= 2
                        and _string_const(n.args[0]) == 'anthropic'
                        and _string_const(n.args[1]) is not None):
                    count += 1
    assert count > 0, (
        "W4-Scanner hat KEINE log_api_cost-Literal-Buchung gefunden — der Sweep ist kaputt "
        "(Pfade verschoben oder Aufruf-Form geaendert), kein Erfolg."
    )


def test_no_booked_literal_contradicts_called_model():
    """Kein hart gebuchter Modellname darf der Kosten-Klasse des an derselben Stelle
    aufgerufenen config.MODEL_*-Modells widersprechen (Haiku vs. Sonnet)."""
    violations = _find_violations()
    assert not violations, (
        "Gebuchter Modellname widerspricht dem aufgerufenen Modell (Kosten-Klasse) — "
        "Sonnet-Kosten werden als Haiku verbucht (o. umgekehrt), die Marge ist still falsch:\n  "
        + "\n  ".join(
            f"{rel}::{fn}:{ln}: bucht '{lit}' (Klasse {bcls}), "
            f"ruft aber config.{attr} (Klasse {ccls}) auf"
            for rel, ln, fn, lit, bcls, attr, ccls in violations
        )
        + "\n\nFix: das Literal durch die echte config.MODEL_*-Variable des model=-Aufrufs "
          "ersetzen (Muster _model_autovar, claude_service.py:620)."
    )
