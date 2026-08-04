"""Phase 08.23.2.MESSGERAETE-1 Plan 01 — Waechter: Antwort-Dauer je Live-KI-Aufruf (ERST-ROT).

WOFUER: `api_cost_log.latency_ms` existiert seit Phase 08.13 — und wurde von KEINEM Live-Call
gesetzt (Prod-Beleg: COUNT(latency_ms) = 0 ueber 21 Tage bei allen Live-Sorten). Eine Spalte
ohne Schreiber und ohne Leser stirbt still. Dieser Waechter nagelt die Messung fest, damit sie
nicht wieder lautlos verschwindet.

WAS ER TUT: reiner statischer AST-Sweep ueber die zwei Dateien mit produktiven Live-LLM-Pfaden.
Er leitet die Pfad-Liste SELBST aus dem Code ab (D-05) — eine handgepflegte Liste reisst
dieselbe Luecke spaeter leiser wieder auf; genau das ist hier belegt passiert (die ROADMAP-Liste
kannte fuenf von acht Pfaden). Keine Datenbank, kein Netz, kein Laden der Anwendung: die Datei
laesst sich gegen jeden ausgecheckten oder ausgerollten Stand fahren.

RESTLUECKEN
-----------
1. ABGEDECKT: dass in jeder Funktion von services/claude_service.py UND services/qa_pipeline.py,
   die messages.create oder
   messages.stream ruft, die input-Token-Buchung ein latency_ms-Keyword traegt (Streaming
   zusaetzlich ttft_ms) — und dass Output-/Cache-Buchungen es NICHT tragen.

2. ⚠ DIE ZENTRALE LUECKE, ausdruecklich benannt: der Waechter prueft, DASS gemessen wird —
   NICHT, DASS DIE ZAHL STIMMT. Er sieht ein Keyword im Syntaxbaum. Ob `_t_api_start`
   unmittelbar vor dem API-Aufruf steht oder 40 Zeilen frueher (dann misst man Prompt-Bau mit),
   kann er strukturell nicht beurteilen — AST-Nachbarschaft ist kein Beweis fuer
   Ausfuehrungs-Nachbarschaft (try/except, with, Retry-Schleifen verschieben die Reihenfolge).
   Er wuerde `latency_ms=0` genauso gruen abnicken wie den richtigen Wert.

   ⚠ ZWEITE HAELFTE DERSELBEN LUECKE (Cross-AI 2026-08-03): drei der acht Pfade sind
   dormant und koennen die Zahl deshalb auch an echten Daten nicht belegen —
   pip_autovar (null Produktiv-Aufrufer), live_haiku und qa_classifier (beide rollback-only,
   MERGE_ANALYSE_QA=0 + Neustart noetig). Fuer sie bleibt es bei "traegt das Keyword".
   Konkret fuer TTFT: der Zwei-Spalten-Nachweis an echten Daten haengt an EINEM Pfad
   (pip_variante). Das beweist Schema, Schreiber, Leser und die Zwei-Spalten-Trennung
   Ende-zu-Ende — es beweist NICHT, dass der pip_autovar-Einbau korrekt MISST.
   ⚠ DRITTE HAELFTE, ganz ohne Waechter: ob der Mess-Anker unmittelbar am API-Aufruf steht,
   sieht dieser Test nicht — und ein Argument im Aufruf (z.B. system=_build_prompt(...)) wird
   von Python NACH dem Anker ausgewertet und damit MITGEMESSEN. Genau das war der Cross-AI-
   Blocker bei analysiere_coaching. Verteidigung ist allein die Hoist-Vorgabe in Plan 02.

3. STRUKTURELL UNSICHTBAR: geparst werden NUR services/claude_service.py und
   services/qa_pipeline.py. Ein neuer Live-LLM-Pfad in einer ANDEREN Datei taucht hier nie auf —
   und er faellt auch im Founder-Dashboard nicht auf: sein context_tag steht nicht in
   LIVE_LLM_CONTEXT_TAGS, also landet er sichtbar in Tabelle 2 "Uebrige Kosten", aber OHNE
   Dauer-Spalten und OHNE Alarm. Das ist die groesste bekannte Luecke dieses Waechters.
   Ebenso unsichtbar: dynamischer Dispatch (getattr), Monkeypatch, ein Wrapper, der
   log_api_cost weiterreicht.

4. HEURISTIK, zweischneidig: unit_type wird nur als ast.Constant-String gelesen. Eine Buchung
   mit unit_type=_VARIABLE rutscht LAUTLOS DURCH (Durchrutscher). Umgekehrt wuerde eine
   Hilfsfunktion, die messages.create nur erwaehnt ohne sie zu rufen, faelschlich als Live-Pfad
   gefordert (Falschtreffer).

5. GEPRUEFT UND GESCHLOSSEN:
   - Doppelzaehlung ueber Cache-/Output-Buchungen (D-07): geschlossen durch
     test_nur_die_input_buchung_traegt_die_dauer.
   - Stiller Ausfall der Ableitung: geschlossen durch das Mindest-Soll MINDEST_LIVE_PFADE
     (Wert 8, nach Allowlist-Abzug).
   - Drift zwischen Code-Funden und der Anzeige-Liste (D-11): geschlossen durch
     test_live_tag_liste_ist_synchron.
   - Der Rollback-Zwilling qa_classifier (D-10): geschlossen durch den Sweep ueber
     services/qa_pipeline.py. Rest-Kante: generate_qa_response steht begruendet auf
     der Allowlist (toter Code) — wird er reaktiviert, muss der Eintrag fallen.
   - Streaming mit nur EINER Zahl (D-03): geschlossen durch
     test_streaming_pfade_tragen_zusaetzlich_ttft_ms.
   - Rest-Kante: ein Live-Pfad, der GAR KEINEN Cost-Hook hat, faellt hier ueber die fehlende
     input-Buchung rot — die vollstaendige Hook-Abdeckung bleibt aber Aufgabe von
     tests/test_cost_hook_coverage.py (W2 aus KOSTEN-1).

6. ZWEITE SCHICHT DARUNTER: die Abnahme an ECHTEN Prod-Daten (D-06, Plan 04) —
   SELECT context_tag, COUNT(*), COUNT(latency_ms) ... mit der Forderung
   COUNT(latency_ms) = COUNT(*) je Live-Sorte. Plus der Leser im Founder-Dashboard (Plan 03):
   eine Frage-Sorte mit "0 Antworten" oder einer offensichtlich unsinnigen Ø-Dauer faellt dort
   ins Auge. Ein gruener Waechter ist ausdruecklich KEIN Ersatz fuer beides.

WAS NICHT ERLAUBT IST, wenn dieser Waechter anschlaegt: die Allowlist fuellen, das Muster
aufweichen oder das Mindest-Soll senken. Einzige zulaessige Ausnahme ist der nachweisliche
Falsch-Treffer, mit `# FALSCH-TREFFER:`-Kommentar, Datei:Zeile und Begruendung.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Die zwei Dateien mit produktiven Live-LLM-Pfaden. qa_pipeline.py ist seit D-10 dabei:
# qa_classifier ist der Rollback-Zwilling von live_haiku — handverlesene Datei-Grenzen zu
# ziehen war genau der Fehler, den diese Phase abschafft.
SWEEP_DATEIEN: tuple[str, ...] = (
    'services/claude_service.py',
    'services/qa_pipeline.py',
)

# Quelle der EINEN Tag-Liste (D-11). Wird per Datei-Pfad gelesen, NICHT geladen — der Sweep
# bleibt dadurch frei von Anwendungs-Abhaengigkeiten und laeuft auch ohne Umgebung.
TAG_QUELLE = 'services/cost_tracker.py'

# Sperre gegen den stillen Ausfall (CLAUDE.md Punkt 31): sieben Live-Pfade in
# claude_service.py + classify_utterance in qa_pipeline.py, nach Allowlist-Abzug.
MINDEST_LIVE_PFADE = 8

# Mindestens zwei Streaming-Pfade: streame_auto_variante + streame_manual_ewb_variante.
# Die ROADMAP-Liste kannte nur einen davon (CONTEXT Punkt 7).
MINDEST_STREAMING_PFADE = 2

INPUT_UNIT = 'per_1k_input_tokens'

# Buchungen dieser Sorten duerfen die Dauer NICHT tragen (D-07): eine API-Antwort erzeugt
# mehrere Buchungen; traegt jede dieselbe Dauer, zaehlt sie 2-4x in Ø/p50/p95.
NICHT_DAUER_UNITS = frozenset({
    'per_1k_output_tokens',
    'per_1k_cache_read_tokens',
    'per_1k_cache_write_tokens',
})

DAUER_KEYWORDS = ('latency_ms', 'ttft_ms')

# ── Allowlist — Datei::Funktion -> GRUND. Ohne Grund kein Eintrag. ──────────────────────────
ALLOWLIST: dict[str, str] = {
    'services/qa_pipeline.py::generate_qa_response':
        'TOTER CODE, kein fehlender Messpfad (Cross-AI 2026-08-03, beide Reviewer einig): '
        'repo-weite Aufrufer-Suche zeigt NULL Produktiv-Call-Sites — nur Definition, '
        'Kommentare und Tests. tests/test_h1_qakill.py nagelt das als Runtime-Waechter fest. '
        'Eine Messung einzubauen waere Wegwerf-Arbeit (CONTEXT D-10). Wird der Pfad je '
        'reaktiviert, faellt dieser Eintrag raus und der Waechter fordert die Messung.',
}


# ── AST-Hilfen (Muster: tests/test_cost_model_truth.py) ─────────────────────────────────────

def _own_nodes(func: ast.AST):
    """Alle Nachfahren-Knoten von `func`, OHNE in verschachtelte Funktionen abzusteigen."""
    for child in ast.iter_child_nodes(func):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        yield child
        yield from _own_nodes(child)


def _is_messages_call(call: ast.Call) -> bool:
    """`X.messages.create(...)` / `X.messages.stream(...)` — ein bezahlter Modell-Aufruf."""
    f = call.func
    if not (isinstance(f, ast.Attribute) and f.attr in ('create', 'stream')):
        return False
    inner = f.value
    return isinstance(inner, ast.Attribute) and inner.attr == 'messages'


def _is_log_api_cost(call: ast.Call) -> bool:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id == 'log_api_cost'
    if isinstance(f, ast.Attribute):
        return f.attr == 'log_api_cost'
    return False


def _string_const(node: ast.AST | None):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class Buchung(NamedTuple):
    zeile: int
    unit_type: str | None
    context_tag: str | None
    keywords: frozenset


class LivePfad(NamedTuple):
    datei: str
    funktion: str
    zeile: int
    streaming: bool
    buchungen: tuple


def _buchung(call: ast.Call) -> Buchung:
    kw = {k.arg: k.value for k in call.keywords if k.arg}
    return Buchung(
        zeile=call.lineno,
        unit_type=_string_const(kw.get('unit_type')),
        context_tag=_string_const(kw.get('context_tag')),
        keywords=frozenset(kw),
    )


def _sammle_live_pfade() -> list[LivePfad]:
    """Leitet die produktiven Live-LLM-Pfade per ast.parse aus den Sweep-Dateien ab (D-05)."""
    gefunden: list[LivePfad] = []
    for rel in SWEEP_DATEIEN:
        pfad = REPO_ROOT / rel
        if not pfad.exists():
            continue
        try:
            baum = ast.parse(pfad.read_text(encoding='utf-8'))
        except (OSError, SyntaxError):  # pragma: no cover - defensiv
            continue
        for knoten in ast.walk(baum):
            if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            eigene = list(_own_nodes(knoten))
            aufrufe = [n for n in eigene if isinstance(n, ast.Call)]
            modell_aufrufe = [c for c in aufrufe if _is_messages_call(c)]
            if not modell_aufrufe:
                continue
            if f'{rel}::{knoten.name}' in ALLOWLIST:
                continue
            gefunden.append(LivePfad(
                datei=rel,
                funktion=knoten.name,
                zeile=knoten.lineno,
                streaming=any(c.func.attr == 'stream' for c in modell_aufrufe),
                buchungen=tuple(_buchung(c) for c in aufrufe if _is_log_api_cost(c)),
            ))
    return gefunden


def _lies_tag_listen() -> dict:
    """Liest LIVE_LLM_CONTEXT_TAGS / CACHE_CONTEXT_TAGS per ast.literal_eval aus der Quelle.

    Bewusst KEIN Laden des Moduls: der Sweep bleibt eine reine Datei-Analyse. Fehlt eine
    Konstante, gibt diese Funktion sie schlicht nicht zurueck — der Test daraus macht einen
    FEHLSCHLAG, keinen Skip (ein Skip waere genau der stille Ausfall aus Punkt 31).
    """
    pfad = REPO_ROOT / TAG_QUELLE
    treffer: dict = {}
    if not pfad.exists():
        return treffer
    try:
        baum = ast.parse(pfad.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):  # pragma: no cover - defensiv
        return treffer
    for knoten in baum.body:
        ziel = None
        if isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Name):
            ziel = knoten.target.id
        elif (isinstance(knoten, ast.Assign) and len(knoten.targets) == 1
                and isinstance(knoten.targets[0], ast.Name)):
            ziel = knoten.targets[0].id
        if ziel not in ('LIVE_LLM_CONTEXT_TAGS', 'CACHE_CONTEXT_TAGS'):
            continue
        if getattr(knoten, 'value', None) is None:
            continue
        try:
            treffer[ziel] = ast.literal_eval(knoten.value)
        except (ValueError, SyntaxError):
            continue
    return treffer


def _funktion_existiert(rel: str, name: str) -> bool:
    pfad = REPO_ROOT / rel
    if not pfad.exists():
        return False
    try:
        baum = ast.parse(pfad.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):  # pragma: no cover - defensiv
        return False
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
               for n in ast.walk(baum))


def _etikett(p: LivePfad) -> str:
    return f'{p.datei}::{p.funktion} (Zeile {p.zeile})'


# ── Die sechs Pruefungen ────────────────────────────────────────────────────────────────────

def test_mindestens_acht_live_pfade_gefunden():
    """Sperre gegen den stillen Ausfall: faellt die Ableitung aus, waere alles andere blind-gruen."""
    pfade = _sammle_live_pfade()
    assert len(pfade) >= MINDEST_LIVE_PFADE, (
        f'Der AST-Sweep hat nur {len(pfade)} Live-LLM-Pfade gefunden, erwartet sind mindestens '
        f'{MINDEST_LIVE_PFADE} (sieben in services/claude_service.py + classify_utterance in '
        'services/qa_pipeline.py, nach Allowlist-Abzug). Das ist KEIN Erfolg: ohne Ableitung '
        'ist dieser Waechter blind statt rot und sieht dabei gruen aus. '
        'Die Zahl NIE stillschweigend senken — Ursache klaeren und mit Begruendung nachziehen.\n'
        'Gefunden: ' + (', '.join(_etikett(p) for p in pfade) or '(nichts)')
    )


def test_input_buchung_traegt_latency_ms():
    """Jede Live-Funktion bucht ihre input-Token MIT Dauer — sonst bleibt latency_ms tot."""
    fehlend: list[str] = []
    ohne_input_buchung: list[str] = []
    for p in _sammle_live_pfade():
        input_buchungen = [b for b in p.buchungen if b.unit_type == INPUT_UNIT]
        if not input_buchungen:
            ohne_input_buchung.append(_etikett(p))
            continue
        for b in input_buchungen:
            if 'latency_ms' not in b.keywords:
                fehlend.append(f'{p.datei}::{p.funktion} (Buchung Zeile {b.zeile})')

    assert not ohne_input_buchung, (
        'Diese Live-LLM-Funktionen haben GAR KEINE input-Token-Buchung mit literalem '
        f"unit_type='{INPUT_UNIT}' — das ist selbst ein Defekt (ohne sie gibt es keinen Ort "
        'fuer die Dauer):\n  ' + '\n  '.join(ohne_input_buchung)
    )
    assert not fehlend, (
        'Diese Live-LLM-Aufrufe messen ihre Antwort-Dauer nicht (input-Token-Buchung ohne '
        'latency_ms=):\n  ' + '\n  '.join(fehlend)
        + '\n\nFix: monotonic()-Anker unmittelbar um den messages.create/stream-Aufruf und '
          'latency_ms= an die input-Token-Buchung (D-01/D-07, Plan 02).'
    )


def test_streaming_pfade_tragen_zusaetzlich_ttft_ms():
    """Streaming braucht ZWEI Zahlen (D-03): bis zum letzten UND bis zum ersten Token."""
    pfade = _sammle_live_pfade()
    streams = [p for p in pfade if p.streaming]
    assert len(streams) >= MINDEST_STREAMING_PFADE, (
        f'Nur {len(streams)} Streaming-Pfade gefunden, erwartet mindestens '
        f'{MINDEST_STREAMING_PFADE} (streame_auto_variante + streame_manual_ewb_variante). '
        'Ableitung pruefen, Zahl nicht senken.'
    )
    fehlend: list[str] = []
    for p in streams:
        for b in p.buchungen:
            if b.unit_type == INPUT_UNIT and 'ttft_ms' not in b.keywords:
                fehlend.append(f'{p.datei}::{p.funktion} (Buchung Zeile {b.zeile})')
    assert not fehlend, (
        'Streaming-Pfade ohne ttft_ms= an der input-Token-Buchung — damit faellt die Zeit bis '
        'zum ERSTEN Token unter den Tisch, und latency_ms allein taeuscht eine langsamere '
        'Antwort vor, als der Nutzer erlebt:\n  ' + '\n  '.join(fehlend)
    )


def test_nur_die_input_buchung_traegt_die_dauer():
    """D-07-Doppelzaehlungs-Sperre: Output-/Cache-Buchungen bleiben ohne Dauer."""
    verstoesse: list[str] = []
    for p in _sammle_live_pfade():
        for b in p.buchungen:
            if b.unit_type not in NICHT_DAUER_UNITS:
                continue
            getragen = [k for k in DAUER_KEYWORDS if k in b.keywords]
            if getragen:
                verstoesse.append(
                    f'{p.datei}::{p.funktion} (Buchung Zeile {b.zeile}, '
                    f'unit_type={b.unit_type}) traegt {", ".join(getragen)}'
                )
    assert not verstoesse, (
        'Diese Buchungen tragen die Dauer, obwohl sie NICHT die input-Token-Buchung sind. Eine '
        'API-Antwort erzeugt mehrere Buchungen — traegt jede dieselbe Dauer, geht sie 2-4x in '
        'Ø/p50/p95 ein und jeder Mittelwert luegt (D-07):\n  ' + '\n  '.join(verstoesse)
    )


def test_live_tag_liste_ist_synchron():
    """D-11: die EINE Anzeige-Liste muss exakt den aus dem Code abgeleiteten Tags entsprechen."""
    listen = _lies_tag_listen()
    fehlende_konstanten = [
        name for name in ('LIVE_LLM_CONTEXT_TAGS', 'CACHE_CONTEXT_TAGS') if name not in listen
    ]
    assert not fehlende_konstanten, (
        f'In {TAG_QUELLE} fehlen als reine Literale: ' + ', '.join(fehlende_konstanten)
        + '. Das ist ein FEHLSCHLAG, kein Skip: ohne die Liste kann der Drift-Schutz zwischen '
          'Code-Ableitung und Founder-Dashboard nichts pruefen, saehe aber gruen aus (Punkt 31). '
          'Beide Konstanten muessen Literale bleiben (kein Funktionsaufruf, keine Referenz, '
          'kein f-String), damit sie ohne Laden des Moduls lesbar sind.'
    )

    live_liste = set(listen['LIVE_LLM_CONTEXT_TAGS'])
    cache_liste = set(listen['CACHE_CONTEXT_TAGS'])
    erwartet = live_liste - cache_liste

    aus_code = {
        b.context_tag
        for p in _sammle_live_pfade()
        for b in p.buchungen
        if b.unit_type == INPUT_UNIT and b.context_tag
    }

    nur_im_code = sorted(aus_code - erwartet)
    nur_in_liste = sorted(erwartet - aus_code)
    assert not nur_im_code and not nur_in_liste, (
        'Die Live-KI-Tag-Liste ist aus dem Tritt geraten (D-11):\n'
        f'  im Code, aber nicht in der Liste: {nur_im_code or "-"}\n'
        '    -> diese Frage-Sorte faellt im Founder-Dashboard still in Tabelle 2 "Uebrige '
        'Kosten", ohne Dauer-Spalten und ohne Alarm.\n'
        f'  in der Liste, aber nicht im Code: {nur_in_liste or "-"}\n'
        '    -> Karteileiche: sie taeuscht eine Messung vor, die es nicht gibt.\n'
        f'  Pflegeort: {TAG_QUELLE}'
    )


def test_allowlist_ist_begruendet_und_lebt():
    """Hygiene der Ausnahmen: jede braucht einen Grund und ein reales Ziel."""
    unbegruendet = [k for k, grund in ALLOWLIST.items() if len((grund or '').strip()) < 20]
    assert not unbegruendet, (
        'Allowlist-Eintraege ohne belastbare Begruendung — genau so wird die Allowlist die '
        'Hintertuer, die den Waechter aushoehlt: ' + ', '.join(unbegruendet)
    )

    tot = []
    for schluessel in ALLOWLIST:
        datei, _, funktion = schluessel.partition('::')
        if not _funktion_existiert(datei, funktion):
            tot.append(schluessel)
    assert not tot, (
        'Diese Allowlist-Eintraege zeigen ins Leere (Funktion umbenannt oder geloescht). Das ist '
        'KEIN Erfolg: der Eintrag weitet den Sweep still auf und sieht dabei gruen aus. '
        'Nachziehen oder streichen:\n  ' + '\n  '.join(tot)
    )
