"""Phase 08.23.2.SOFORT-2 Plan 05 — Waechter: Zeitlimit auf JEDEM Live-LLM-Aufruf (ERST-ROT).

WOFUER: ohne `timeout=` greifen die SDK-Vorgaben (`read=600 s`). Weil `analyse_loop` und
`coaching_loop` sequentiell ueber alle SIDs iterieren, stehen in dieser Zeit ALLE Gespraeche
still — ein einziger haengender Aufruf legt den Live-Betrieb aller Mandanten lahm. Dieser
Waechter nagelt fest, dass kein Live-Pfad ohne Zeitlimit laeuft, dass die Stream-Pfade die
ZWEITE Zahl benutzen, und dass der Modul-Client `max_retries=0` traegt.

WAS ER TUT: reiner statischer AST-Sweep ueber die vier Dateien mit produktiven Live-LLM-Pfaden.
Er leitet die Pfad-Liste SELBST aus dem Code ab (D-05) — eine handgepflegte Liste reisst
dieselbe Luecke spaeter leiser wieder auf. Keine Datenbank, kein Netz, kein Laden der
Anwendung: die Datei laesst sich gegen jeden ausgecheckten oder ausgerollten Stand fahren.

Geruest uebernommen aus tests/test_live_latency_coverage.py (MESSGERAETE-1 Plan 01) —
dieselbe Ableitung, andere Frage.

RESTLUECKEN
-----------
1. ABGEDECKT: dass jeder messages.create/messages.stream-Aufruf in services/claude_service.py
   und services/qa_pipeline.py ein timeout-Schluesselwort traegt, dass die Stream-Aufrufe die
   ZWEITE Zahl benutzen (LIVE_LLM_STREAM_TIMEOUT_S statt LIVE_LLM_TIMEOUT_S), und dass der
   Modul-Client mit max_retries=0 erzeugt wird.

2. ⚠ ER SIEHT EIN SCHLUESSELWORT, NICHT DEN WERT. `timeout=0.0001` oder `timeout=None` waere
   gruen. Fuer die Stream-Pfade prueft er immerhin den NAMEN der Konstante — nicht deren Zahl.
   Die Zahlen selbst sind benannte Festlegungen in config.py (F-1/F-2) und werden von der
   Abnahme an echten Daten getragen (D-06, Plan 08), nicht von diesem Test.

3. ⚠ ER SAGT NICHTS DARUEBER, OB DER except-ZWEIG ERREICHBAR IST. anthropic.APITimeoutError ist
   eine UNTERKLASSE von anthropic.APIConnectionError — steht das breitere except zuerst, ist
   der Timeout-Zweig unerreichbar und Stufe 1/2 aus D-04 feuern nie, waehrend dieser Waechter
   gruen bleibt. Dagegen steht allein der Runtime-Test aus Plan 06 Task 3.

4. STRUKTURELL UNSICHTBAR: geparst werden NUR die VIER Sweep-Dateien
   (SWEEP_DATEIEN = services/claude_service.py, services/qa_pipeline.py,
   services/adoption_runner.py, services/judge_runner.py). Ein Live-LLM-Pfad in einer FUENFTEN
   Datei taucht hier nie auf - dieselbe groesste Luecke wie beim Vorbild
   tests/test_live_latency_coverage.py. Ebenso unsichtbar: dynamischer Dispatch via getattr,
   Monkeypatch, ein Wrapper, der messages.create weiterreicht, und jeder Aufruf, der zur
   Laufzeit entsteht.

   HISTORIE, weil sie die Regel belegt (Fund C-1, Andre-Entscheidung 2026-08-05):
   Bis zum Replan umfasste SWEEP_DATEIEN nur die ersten ZWEI Dateien. Ausserhalb lagen
   nachweislich zwei Aufrufe OHNE Zeitlimit:
     services/adoption_runner.py:281   claude_client.messages.create(...)
     services/judge_runner.py:382      claude_client.messages.create(...)
   Beide importieren claude_client aus services/claude_service.py (adoption_runner.py:35,
   judge_runner.py:32) und laufen aus services/slow_lane.py (:504 run_behavior_judge,
   :897 run_adoption_judge) im EINZIGEN Consumer-Faden (services/slow_lane.py:30 -
   "JETZT 1 Consumer-Thread"). Ein Haenger dort blockiert bis zu ZEHN MINUTEN die
   Nachbearbeitung ALLER Mandanten.
   ENTSCHEIDEND WAR NICHT DIE GROESSE, SONDERN: DIESER WAECHTER WAERE DABEI GRUEN GEBLIEBEN
   und haette "kein Live-Aufruf ohne Zeitlimit" gemeldet, waehrend das Loch offen war.
   Ein gruener Waechter bei offenem Loch ist gefaehrlicher als gar keiner (Punkt 31).
   Deshalb wurden die zwei Dateien in SWEEP_DATEIEN aufgenommen und beide Aufrufe in Plan 06
   Task 2 mit timeout= versehen - GEFIXT, nicht gemeldet. R-10 ist damit erledigt und steht
   NICHT mehr in FUNDE.md Abschnitt 2.
   ⚠ KORREKTUR 2026-08-06 (Andre-Entscheidung, Fund E-10): diese ZWEI Aufrufe tragen
   BATCH_LLM_TIMEOUT_S (45 s), NICHT LIVE_LLM_TIMEOUT_S (12 s). Hier stand vorher
   "derselbe Mechanismus wie live" - das war falsch. Sie laufen NICHT im Live-Gespraech;
   die Post-Call-Auswertung dauert insgesamt 15,2 s (MESSGERAETE-1), 12 s haetten sie
   gekappt und dem Berater die Coaching-Note genommen. Begruendung: config.py, F-7.
   ⚠ DIESER WAECHTER MERKT DEN UNTERSCHIED NICHT: test_jeder_live_aufruf_traegt_ein_zeitlimit
   prueft nur die ANWESENHEIT eines timeout-Schluesselworts (`hat_timeout = 'timeout' in kw`),
   nicht WELCHE Konstante. Nur der Stream-Test bindet an einen Namen. Wer eine dritte Klasse
   von Pfaden anlegt, bekommt von hier KEINE Warnung, wenn er die falsche Zahl nimmt -
   das ist eine bewusste Restluecke, keine Nachlaessigkeit (Punkt 31).
   WAS HIER NICHT STEHEN DARF: eine generische Luecken-Formulierung, unter der konkrete,
   heute existierende Faelle verschwinden. Wer den Sweep je erweitert, haengt an jeden neuen
   LIVE-Aufruf timeout=httpx.Timeout(config.LIVE_LLM_TIMEOUT_S, connect=config.LLM_CONNECT_TIMEOUT_S)
   - an einen BATCH-Aufruf dagegen config.BATCH_LLM_TIMEOUT_S.

5. HEURISTIK, zweischneidig: der Stream-Test vergleicht den QUELLTEXT des timeout-Arguments
   gegen den Konstantennamen. Ein Alias (`from config import LIVE_LLM_STREAM_TIMEOUT_S as T`)
   wuerde faelschlich rot melden (Falschtreffer). Umgekehrt wuerde ein `timeout=_LIMIT`, wo
   `_LIMIT` irgendwo anders gesetzt wird, beim Grundtest gruen durchrutschen (Durchrutscher).

6. GEPRUEFT UND GESCHLOSSEN:
   - Die direkteste Form der Fehlerklasse — ein Live-Aufruf ganz ohne Zeitlimit — ist abgedeckt
     durch test_jeder_live_aufruf_traegt_ein_zeitlimit. Rest-Kante: der Wert (Punkt 2).
   - Die Verdreifachung des Worst Case durch max_retries: geschlossen durch
     test_modul_client_hat_max_retries_null. DAS IST DIE LUECKE, DIE DIESER WAECHTER GEGENUEBER
     EINER REINEN timeout-PRUEFUNG ZUSAETZLICH SCHLIESST — ohne sie waere sein Gruen wahr und
     wertlos zugleich.
   - Ein Stream, der faelschlich an der Gesamtdauer gekappt wird (D-03): geschlossen durch
     test_streaming_pfade_tragen_das_stream_zeitlimit.
   - Stiller Ausfall der Ableitung: geschlossen durch MINDEST_LIVE_PFADE = 10 und
     MINDEST_STREAMING_PFADE = 2 sowie durch die getrennte "Konstruktor nicht gefunden"-Meldung.
   - NICHT geschlossen: die Erreichbarkeit des except-Zweigs (Punkt 3).

ZWEITE SCHICHT DARUNTER
-----------------------
(a) der umgeschriebene Runtime-Test tests/test_stabil1_http_llm_timeout.py::
    test_daemon_pfad_mit_zeitlimit (Plan 06 Task 3) — er ruft den Pfad wirklich auf und liest
    das uebergebene timeout aus dem Fake;
(b) der echte Test-Anruf aus D-06 (Plan 08) mit dem Vergleich der api_cost_log-Messwerte gegen
    die MESSGERAETE-1-Tabelle — der einzige Beweis, dass kein legitimer Aufruf neu gekappt wird.
Ein gruener Waechter ist ausdruecklich KEIN Ersatz fuer beides.

WAS NICHT ERLAUBT IST, wenn dieser Waechter anschlaegt: die Allowlist fuellen, das Muster
aufweichen oder ein Mindest-Soll senken. Einzige zulaessige Ausnahme ist der nachweisliche
Falsch-Treffer, mit `# FALSCH-TREFFER:`-Kommentar, Datei:Zeile und Begruendung.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Die VIER Dateien mit produktiven Live-LLM-Pfaden. Die zwei letzten sind neu gegenueber dem
# Latenz-Waechter (Andre-Entscheidung 2026-08-05 zu R-10 / Cross-AI-Fund C-1): der
# Welle-2-Waechter meldet sonst GRUEN, waehrend das Loch offen ist — ein gruener Waechter bei
# offenem Loch ist gefaehrlicher als gar keiner. Und weil ein Haenger dort ALLE Mandanten
# gleichzeitig trifft, ist es ein Mehrnutzer-Thema, also scope-konform.
SWEEP_DATEIEN: tuple[str, ...] = (
    'services/claude_service.py',
    'services/qa_pipeline.py',
    'services/adoption_runner.py',
    'services/judge_runner.py',
)

# Die Datei, in der der Modul-Client erzeugt wird (max_retries-Pruefung).
CLIENT_QUELLE = 'services/claude_service.py'

# Sperre gegen den stillen Ausfall (CLAUDE.md Punkt 31), Zahlen-Tafel ZT-15:
# sieben Live-Pfade in claude_service.py + classify_utterance in qa_pipeline.py
# + run_adoption_judge + run_behavior_judge, nach Allowlist-Abzug.
MINDEST_LIVE_PFADE = 10

# Zahlen-Tafel ZT-16: streame_auto_variante + streame_manual_ewb_variante.
MINDEST_STREAMING_PFADE = 2

# Die zweite Zahl (F-2): Stream-Pfade duerfen NICHT am Gesamt-Limit haengen (D-03).
STREAM_KONSTANTE = 'LIVE_LLM_STREAM_TIMEOUT_S'
BLOCK_KONSTANTE = 'LIVE_LLM_TIMEOUT_S'

# ── Allowlist — Datei::Funktion -> GRUND. Ohne Grund kein Eintrag. ──────────────────────────
ALLOWLIST: dict[str, str] = {
    'services/qa_pipeline.py::generate_qa_response':
        'TOTER CODE, kein fehlender Messpfad (Cross-AI 2026-08-03, beide Reviewer einig): '
        'repo-weite Aufrufer-Suche zeigt NULL Produktiv-Call-Sites — nur Definition, '
        'Kommentare und Tests. tests/test_h1_qakill.py nagelt das als Runtime-Waechter fest. '
        'Gilt auch fuer das Zeitlimit: ein Pfad ohne Produktiv-Aufrufer braucht keines. '
        'Wird der Pfad je reaktiviert, faellt dieser Eintrag raus und der Waechter fordert '
        'das Zeitlimit.',
}


# ── AST-Hilfen (uebernommen aus tests/test_live_latency_coverage.py) ────────────────────────

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


class ModellAufruf(NamedTuple):
    zeile: int
    streaming: bool
    hat_timeout: bool
    timeout_quelltext: str | None


class LivePfad(NamedTuple):
    datei: str
    funktion: str
    zeile: int
    streaming: bool
    aufrufe: tuple


def _modell_aufruf(call: ast.Call) -> ModellAufruf:
    kw = {k.arg: k.value for k in call.keywords if k.arg}
    wert = kw.get('timeout')
    try:
        quelltext = ast.unparse(wert) if wert is not None else None
    except Exception:  # pragma: no cover - defensiv
        quelltext = '<nicht darstellbar>'
    return ModellAufruf(
        zeile=call.lineno,
        streaming=call.func.attr == 'stream',
        hat_timeout='timeout' in kw,
        timeout_quelltext=quelltext,
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
            modell_aufrufe = [n for n in eigene
                              if isinstance(n, ast.Call) and _is_messages_call(n)]
            if not modell_aufrufe:
                continue
            if f'{rel}::{knoten.name}' in ALLOWLIST:
                continue
            aufrufe = tuple(_modell_aufruf(c) for c in modell_aufrufe)
            gefunden.append(LivePfad(
                datei=rel,
                funktion=knoten.name,
                zeile=knoten.lineno,
                streaming=any(a.streaming for a in aufrufe),
                aufrufe=aufrufe,
            ))
    return gefunden


def _finde_client_konstruktor():
    """Die Zuweisung, deren Wert ein Aufruf auf `anthropic.Anthropic(...)` ist.

    Rueckgabe: der ast.Call-Knoten oder None. None heisst NICHT "in Ordnung", sondern
    "Ableitung ausgefallen" — der aufrufende Test macht daraus einen eigenen Fehlschlag.
    """
    pfad = REPO_ROOT / CLIENT_QUELLE
    if not pfad.exists():
        return None
    try:
        baum = ast.parse(pfad.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):  # pragma: no cover - defensiv
        return None
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Assign):
            continue
        wert = knoten.value
        if not isinstance(wert, ast.Call):
            continue
        f = wert.func
        if isinstance(f, ast.Attribute) and f.attr == 'Anthropic':
            return wert
        if isinstance(f, ast.Name) and f.id == 'Anthropic':
            return wert
    return None


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


# ── Die fuenf Pruefungen ────────────────────────────────────────────────────────────────────

def test_mindestens_erwartete_live_pfade_gefunden():
    """Sperre gegen den stillen Ausfall: faellt die Ableitung aus, waere alles andere blind-gruen."""
    pfade = _sammle_live_pfade()
    assert len(pfade) >= MINDEST_LIVE_PFADE, (
        f'Der AST-Sweep hat nur {len(pfade)} Live-LLM-Pfade gefunden, erwartet sind mindestens '
        f'{MINDEST_LIVE_PFADE} (sieben in services/claude_service.py + classify_utterance in '
        'services/qa_pipeline.py + run_adoption_judge + run_behavior_judge, nach '
        'Allowlist-Abzug). Das ist KEIN Erfolg: ohne Ableitung ist dieser Waechter blind statt '
        'rot und sieht dabei gruen aus. '
        'Die Zahl NIE stillschweigend senken — Ursache klaeren und mit Begruendung nachziehen.\n'
        'Gefunden: ' + (', '.join(_etikett(p) for p in pfade) or '(nichts)')
    )


def test_jeder_live_aufruf_traegt_ein_zeitlimit():
    """Kein Live-LLM-Aufruf ohne timeout= — sonst greifen die SDK-Vorgaben (read=600 s)."""
    offen: list[str] = []
    for p in _sammle_live_pfade():
        for a in p.aufrufe:
            if not a.hat_timeout:
                offen.append(f'{p.datei}::{p.funktion} (Aufruf Zeile {a.zeile})')
    assert not offen, (
        'Diese Live-LLM-Aufrufe laufen OHNE Zeitlimit:\n  ' + '\n  '.join(offen)
        + '\n\nOhne Zeitlimit greifen die SDK-Vorgaben (read=600 s). Weil analyse_loop und '
          'coaching_loop sequentiell ueber alle SIDs iterieren, stehen in dieser Zeit ALLE '
          'Gespraeche still.\n'
          'Fix: timeout=httpx.Timeout(config.LIVE_LLM_TIMEOUT_S, '
          'connect=config.LLM_CONNECT_TIMEOUT_S) an den Aufruf (Plan 06).'
    )


def test_streaming_pfade_tragen_das_stream_zeitlimit():
    """Streaming braucht die ZWEITE Zahl (D-03): das Gesamt-Limit wuerde lange Antworten kappen."""
    pfade = _sammle_live_pfade()
    streams = [p for p in pfade if p.streaming]
    assert len(streams) >= MINDEST_STREAMING_PFADE, (
        f'Nur {len(streams)} Streaming-Pfade gefunden, erwartet mindestens '
        f'{MINDEST_STREAMING_PFADE} (streame_auto_variante + streame_manual_ewb_variante). '
        'Ableitung pruefen, Zahl nicht senken.'
    )
    falsch: list[str] = []
    for p in streams:
        for a in p.aufrufe:
            if not a.streaming:
                continue
            quelle = a.timeout_quelltext or ''
            if STREAM_KONSTANTE not in quelle:
                falsch.append(
                    f'{p.datei}::{p.funktion} (Aufruf Zeile {a.zeile}) -> '
                    f'timeout={quelle or "(fehlt)"}'
                )
    assert not falsch, (
        f'Diese Stream-Aufrufe haengen nicht an {STREAM_KONSTANTE}:\n  ' + '\n  '.join(falsch)
        + f'\n\nEin Stream darf NICHT am blockierenden Limit ({BLOCK_KONSTANTE}) haengen — '
          '`read` gilt bei httpx PRO DATENBLOCK, die Gesamtdauer wird bewusst NICHT gekappt '
          '(D-03). Lange, legitime Antworten wuerden sonst mitten im Satz abbrechen.'
    )


def test_modul_client_hat_max_retries_null():
    """Die Achillesferse: `max_retries` gibt es nur am Client und es gilt PRO VERSUCH.

    Ohne diese Pruefung haelt ein 12-s-Limit im Worst Case 3 x 12 s + Backoff ~ 38 s — und ein
    Waechter, der nur `timeout=` prueft, bleibt dabei gruen.
    """
    konstruktor = _finde_client_konstruktor()
    assert konstruktor is not None, (
        f'Konstruktor nicht gefunden: in {CLIENT_QUELLE} gibt es keine Zuweisung, deren Wert '
        'ein Aufruf auf anthropic.Anthropic(...) ist. Ableitung ausgefallen — das ist KEIN '
        'Erfolg: der Waechter waere hier blind statt rot. Erkennungs-Ausdruck reparieren, '
        'diesen Test NICHT entfernen.'
    )
    kw = {k.arg: k.value for k in konstruktor.keywords if k.arg}
    wert = kw.get('max_retries')
    ist_null = isinstance(wert, ast.Constant) and wert.value == 0
    if not ist_null:
        try:
            gefunden = ast.unparse(wert) if wert is not None else 'SDK-Vorgabe 2'
        except Exception:  # pragma: no cover - defensiv
            gefunden = '<nicht darstellbar>'
        versuche = '2+1' if wert is None else f'{gefunden}+1'
        raise AssertionError(
            f'{CLIENT_QUELLE}:{konstruktor.lineno} — der Modul-Client traegt kein '
            f'max_retries=0 (gefunden: {gefunden}).\n'
            f'Worst Case: {versuche} Versuche x timeout (plus Backoff dazwischen). Bei '
            'LIVE_LLM_TIMEOUT_S = 12 s sind das ~38 s statt 12 s — und ein Waechter, der nur '
            'timeout= prueft, bleibt dabei gruen. max_retries ist als Aufruf-Argument NICHT '
            'setzbar, es gehoert an den Client.'
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
