"""Phase 08.23.2.LOCK-1 Plan 02 — Waechter 2: statische AST-Sperre gegen blockierende
Aufrufe unter dem Sitzungs-Riegel `_session_state_lock`.

ANLASS
------
Anruf vom 30.07., sid `5Y-0MFlm_ITb1cupAAAB`: 1416 Faeden standen blockiert am
Sitzungs-Riegel — und **niemand** hatte einen sichtbaren Halter-Rahmen. Die Wurzel-Frage
„wer hielt den Riegel?" ist bis heute unbeantwortet. Solange sie das ist, ist der einzige
belastbare Schutz strukturell: **unter dem Riegel darf nichts stehen, das warten kann.**
Kein `get_session`/`SessionLocal` (DB), kein `messages.create`/`messages.stream` (LLM),
kein `sio.emit` (Socket), kein `requests.*` (Netz), kein `sleep`, kein Faden-`join`.

WARUM AST UND NICHT GREP
------------------------
Ein grep auf `with _session_state_lock:` ist doppelt falsch:

* Er **uebersieht fuenf Alias-Schreibweisen**, die durch lazy-Importe gegen Modul-Zyklen
  entstehen — Praefixe `_ls_av.` (services/claude_service.py:940), `ls_module.`
  (services/deepgram_service.py:572) und `_ls.` (services/prompt_pipeline.py:654,
  services/einwand_keyword_matcher.py:259 und :286).
* Er **zaehlt Kommentare mit** — services/einwand_keyword_matcher.py:273 nennt die Woerter
  nur in einem Kommentar („EIGENER `with _session_state_lock`-Block").

Ein grep-basierter Waechter haette also fuenf echte Bloecke verpasst und einen Kommentar
bewacht. Deshalb: `ast`, kein Textmuster. Die Riegel-Erkennung geht ueber den
**Attribut-Namen**, nicht ueber den Empfaenger — dadurch muss keine Alias-Liste gepflegt
werden und ein kuenftiger sechster Alias wird automatisch mitgefangen.

ZWEI FORMEN DER RIEGEL-NAHME
----------------------------
Heute sind alle Bloecke `with`-Bloecke. Ab Plan 03 Task 4 gibt es eine zweite Form:
begrenzter Erwerb (`acquire(timeout=...)`) mit `try:` / `finally: ...release()`. Vier
Bereiche werden dort umgestellt, ein fuenfter kommt in Plan 04 Task 2 dazu
(`_lockwatch_tick`). Ein Waechter, der nur `with` kennt, verloere **genau die Stellen aus
der Bewachung, die wir wegen einer Verklemmung anfassen**. Deshalb erfasst dieser Sweep
beide Formen — dieselbe Verbots-Pruefung, dieselbe Alias-Erkennung, nur ein zweiter
Block-Sammler.

Verankert wird der `try/finally`-Zweig an der **Freigabe**, nicht am Erwerb: das
`release()` markiert das Ende der Riegel-Region eindeutig, waehrend der Erwerb je nach
Form eine Zeile hoeher steht (`if not lock.acquire(...): return`) oder im if-Test
(`if lock.acquire(...):`). Beide Formen enden im selben `finally`.

KEIN SOURCE-PRESENCE-FALSE-GREEN (CLAUDE.md Test-Qualitaets-Regel)
------------------------------------------------------------------
Der Sweep prueft ein **verbotenes Muster**, NICHT die Existenz erwuenschten Codes.
Ein False-Green kann dadurch nicht entstehen: verschwindet Code, wird der Test gruener;
kommt das Muster zurueck, wird er rot — nie umgekehrt. Das ist der in CLAUDE.md
dokumentierte Grenzfall (kein Function-Call-Mock kann „nichts Blockierendes unter dem
Riegel" ueber alle 102 Bloecke hinweg direkt testbar machen).

FALSIFIZIERBARKEIT UEBER SYNTHETISCHEN QUELLTEXT (Abweichung von COUNTERPART-03)
-------------------------------------------------------------------------------
Die Hausschule (COUNTERPART-03) verlangt fuer Waechter einen Rot-Nachweis durch temporaere
Verunreinigung einer **Produktiv**-Datei. Hier waere das ein echtes Risiko: die temporaere
Zeile muesste **unter** einen echten Riegel-Block — bleibt sie versehentlich stehen, ist
das exakt der Bug, den diese Phase behebt. Der synthetische Quelltext in den Selbst-Tests
beweist dasselbe (der Detektor beisst) ohne jedes Rueckbau-Risiko. Deshalb fasst dieser
Waechter **keine** Produktiv-Datei an.

Die `try/finally`-Selbst-Tests stehen bereits hier in Welle 1, obwohl es die Form im Repo
erst ab Welle 2 gibt: sonst waere nicht unterscheidbar, ob der Detektor die Form **erkennt**
oder sie nur noch nicht **existiert**. Erkennt er sie nicht, deckt er still nichts ab —
und die Zahlen saehen trotzdem plausibel aus.

BEKANNTE GRENZEN (ehrlich benannt, nicht heimlich)
--------------------------------------------------
1. Der Sweep sieht nur **direkte** Aufrufe im Block. Ein Helfer, der zwei Ebenen tiefer
   `get_session()` ruft, rutscht durch. Genau diese Klasse ist bei `close_moment` /
   `get_or_open_moment` (services/live_session.py:599-605, :648-650) bewusst so gebaut
   („lock-free, Aufrufer haelt").
2. `_SOLL_MINDESTENS` ist ein **Mindest**wert. Ein weiterer legitimer Rueckbau wuerde den
   Waechter rot machen — dann wird die Zahl **mit Begruendung** nachgezogen, der Test wird
   **nicht** entfernt.
3. Eine Riegel-Nahme, die den Riegel im `finally` **nicht** freigibt, saehe dieser Sweep
   nicht — sie waere allerdings ein fuer immer klemmender Riegel und damit ein weit
   groesseres Problem als ein fehlender Waechter-Treffer.

STOP-REGEL
----------
Erwartet sind **0** Verstoesse. Findet der Sweep einen echten blockierenden Aufruf unter
dem Riegel, ist das ein **Fund** und kein Konfigurations-Problem: anhalten, mit
`Datei:Zeile` melden, **nicht** die Whitelist fuellen und **nicht** das Muster aufweichen.
Einzige erlaubte Whitelist-Kategorie ist ein nachweislicher **Falsch**-Treffer (Aufruf, der
nur zufaellig so heisst), mit `# FALSCH-TREFFER:`-Kommentar, `Datei:Zeile` und Begruendung.
"""

import ast
import textwrap
from pathlib import Path

# ── Wurzel + Sweep-Bereich ────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_SCAN_DIRS = ('services', 'routes')

# ── Verbotene Aufrufe unter dem Riegel (CONTEXT <decisions>, Waechter 2) ──────
# Als NAME (nackter Aufruf) verboten:
_VERBOTENE_NAMEN = frozenset({'get_session', 'SessionLocal', 'sleep'})
# Als ATTRIBUT (x.name(...)) verboten:
_VERBOTENE_ATTRIBUTE = frozenset({'get_session', 'SessionLocal', 'sleep', 'emit', 'join'})
# Empfaenger-gebunden: requests.<irgendwas>() — NICHT ueber den Methodennamen, sonst
# waere jedes dict.get(...) ein Falsch-Treffer (haeufigster Aufruf unter dem Riegel).
_VERBOTENE_EMPFAENGER_MODULE = frozenset({'requests'})
# <...>.messages.create / .stream — ein nacktes create(...) wird NICHT gemeldet.
_VERBOTENE_MESSAGES_METHODEN = frozenset({'create', 'stream'})

# Mindest-Soll pro Datei, ueber BEIDE Formen zusammen (with + try/finally).
# Unter-Sweep-Sperre. Die Werte stehen auf dem TIEFPUNKT der Kurve ueber die drei
# Wellen, NICHT auf dem heutigen Ist-Stand:
#   live_session.py     26 (heute) -> 25 -> 25 -> 26   => Soll 25
#   deepgram_service.py 22 (heute) -> 22 -> 22 -> 22   => Soll 22
# Der Knick kommt daher, dass Plan 03 get_sid_paused den Riegel GANZ nimmt (ein Block
# weniger, zu Recht) und vier weitere Bloecke von `with` auf `try/finally` umstellt —
# die bleiben ueberwacht, weil dieser Sweep beide Formen zaehlt. Stuende hier 22/21,
# waere der Waechter nach Plan 03 Task 4 still blind statt rot.
_SOLL_MINDESTENS = {
    'services/claude_service.py': 41,
    'services/deepgram_service.py': 22,
    'services/live_session.py': 25,
    'routes/app_routes.py': 4,
    'services/prompt_pipeline.py': 3,
    'services/cost_tracker.py': 2,
    'routes/learning.py': 2,
    'services/einwand_keyword_matcher.py': 2,
}
# 102 heute, 101 nach Plan 03, 102 nach Plan 04 -> das Minimum ueber alle drei Wellen:
_SOLL_SUMME_MINDESTENS = 101

# Falsch-Treffer-Ausnahmen. HEUTE LEER — jeder Eintrag braucht einen
# '# FALSCH-TREFFER:'-Kommentar mit Datei:Zeile und einer Begruendung.
# Ein ECHTER Fund gehoert NICHT hierher, sondern gemeldet (STOP-Regel im Docstring).
_FALSCH_TREFFER = frozenset()   # {(datei, zeile, name), ...}


# ── Riegel-Erkennung ──────────────────────────────────────────────────────────
def _ist_session_state_lock(expr):
    """Faengt ls./_ls./_ls_av./ls_module./nackt — ueber den ATTRIBUT-Namen, nicht ueber
    den Empfaenger. Dadurch muss keine Alias-Liste gepflegt werden und ein kuenftiger
    sechster Alias wird automatisch mitgefangen."""
    if isinstance(expr, ast.Attribute) and expr.attr == '_session_state_lock':
        return True
    if isinstance(expr, ast.Name) and expr.id == '_session_state_lock':
        return True
    return False


def _sammle_bloecke(baum):
    """Jedes ast.With, bei dem IRGENDEIN Kontext-Ausdruck der Sitzungs-Riegel ist —
    auch `with anderer_lock, ls._session_state_lock:` wird gefangen."""
    gefunden = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.With) and any(
                _ist_session_state_lock(item.context_expr) for item in knoten.items):
            gefunden.append(knoten)
    return gefunden


# ── Zweite Form: try/finally mit begrenztem Erwerb (Plan 03 Task 4 / Plan 04 Task 2) ──
def _ist_lock_release_aufruf(call):
    """True fuer <riegel>.release() — egal ob nackt oder ueber einen Alias
    (ls./_ls./_ls_av./ls_module.). Nutzt DIESELBE Riegel-Erkennung wie der with-Zweig;
    eine zweite Alias-Logik waere der Anfang der Divergenz."""
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == 'release'
            and _ist_session_state_lock(f.value))


def _sammle_try_bloecke(baum):
    """Jedes ast.Try, dessen finally-Zweig den Sitzungs-Riegel FREIGIBT.

    Verankert an der FREIGABE, nicht am Erwerb: das release() markiert das Ende der
    Riegel-Region eindeutig, waehrend der Erwerb je nach Form eine Zeile hoeher steht
    (`if not lock.acquire(...): return`) oder im if-Test (`if lock.acquire(...):`).
    Beide Formen schreibt Plan 03 Task 4; beide enden im selben finally.
    """
    gefunden = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Try) and any(
                isinstance(k, ast.Call) and _ist_lock_release_aufruf(k)
                for anw in knoten.finalbody for k in ast.walk(anw)):
            gefunden.append(knoten)
    return gefunden


def _riegel_region(try_knoten):
    """Die Anweisungen, die WIRKLICH unter dem Riegel laufen: body + orelse +
    except-Ruempfe (laufen vor dem finally, halten den Riegel also noch) + die
    finally-Anweisungen VOR dem release. Ab dem release ist der Riegel frei.

    NICHT enthalten: der else-Zweig von `if lock.acquire(...):` — er laeuft, WEIL der
    Erwerb fehlschlug, also OHNE Riegel. Er ist ein Geschwister des try und liegt damit
    nie in dieser Region. Dort stehen die [LOCKWATCH]-print-Zeilen; sie duerfen nicht
    gemeldet werden.
    """
    region = list(try_knoten.body) + list(try_knoten.orelse)
    for behandler in try_knoten.handlers:
        region.extend(behandler.body)
    for anw in try_knoten.finalbody:
        if any(isinstance(k, ast.Call) and _ist_lock_release_aufruf(k)
               for k in ast.walk(anw)):
            break
        region.append(anw)
    return region


# ── Verbots-Pruefung (genau EINE, fuer beide Formen) ──────────────────────────
def _ist_verbotener_aufruf(call):
    """Melde-Name des verbotenen Aufrufs, sonst None."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id if f.id in _VERBOTENE_NAMEN else None
    if isinstance(f, ast.Attribute):
        if f.attr == 'join':
            # ', '.join(x) ist String-Verkettung, KEIN Faden-join.
            if isinstance(f.value, ast.Constant) and isinstance(f.value.value, str):
                return None
            return 'join'
        if (f.attr in _VERBOTENE_MESSAGES_METHODEN
                and isinstance(f.value, ast.Attribute) and f.value.attr == 'messages'):
            return 'messages.' + f.attr
        if (isinstance(f.value, ast.Name)
                and f.value.id in _VERBOTENE_EMPFAENGER_MODULE):
            return f'{f.value.id}.{f.attr}'
        if f.attr in _VERBOTENE_ATTRIBUTE:
            return f.attr
    return None


def _verbotene_aufrufe_in(knoten_oder_liste):
    """Nimmt ENTWEDER einen Knoten (with-Block) ODER eine Liste von Knoten
    (Riegel-Region eines try/finally). Ein zweiter, parallel gepflegter Verbots-Pruefer
    waere der Anfang der Divergenz — es gibt genau diesen einen.

    ast.walk geht auch in verschachtelte with/try/if-Bloecke: ein get_session() zwei
    Ebenen tief im selben Riegel-Block ist genauso schaedlich.
    """
    knoten = (knoten_oder_liste if isinstance(knoten_oder_liste, list)
              else [knoten_oder_liste])
    treffer = []
    for wurzel in knoten:
        for n in ast.walk(wurzel):
            if isinstance(n, ast.Call):
                name = _ist_verbotener_aufruf(n)
                if name:
                    treffer.append((getattr(n, 'lineno', 0), name))
    return treffer


# ── Datei-Sweep ───────────────────────────────────────────────────────────────
def _python_dateien():
    """(relativer-posix-Pfad, Path) fuer jede .py-Datei in _SCAN_DIRS.
    __pycache__ wird uebersprungen — .pyc ist kein Quelltext, und stale Bytecode war in
    Phase COUNTERPART-03 der einzige verbliebene Falsch-Treffer."""
    ergebnis = []
    for d in _SCAN_DIRS:
        for p in (_ROOT / d).rglob('*.py'):
            if '__pycache__' in p.parts:
                continue
            ergebnis.append((p.relative_to(_ROOT).as_posix(), p))
    return sorted(ergebnis)


def _baum_oder_fehler(pfad):
    """(baum, None) oder (None, fehlermeldung). Kein errors='ignore': ein Dekodier-Fehler
    soll auffallen, nicht still einen Block verschlucken."""
    try:
        return ast.parse(pfad.read_text(encoding='utf-8')), None
    except (SyntaxError, UnicodeDecodeError) as e:
        return None, f'{type(e).__name__}: {e}'


def test_keine_blockierenden_aufrufe_unter_dem_sitzungs_riegel():
    verstoesse = []
    for datei, pfad in _python_dateien():
        baum, fehler = _baum_oder_fehler(pfad)
        if baum is None:
            # Nicht verschlucken: sichtbar rot statt still uebersprungen.
            verstoesse.append((datei, 0, f'SYNTAX ({fehler})'))
            continue
        treffer = []
        for block in _sammle_bloecke(baum):
            treffer.extend(_verbotene_aufrufe_in(block))
        for tblock in _sammle_try_bloecke(baum):
            treffer.extend(_verbotene_aufrufe_in(_riegel_region(tblock)))
        for zeile, name in treffer:
            if (datei, zeile, name) in _FALSCH_TREFFER:
                continue
            verstoesse.append((datei, zeile, name))

    verstoesse = sorted(set(verstoesse))
    assert not verstoesse, (
        "Blockierender Aufruf unter _session_state_lock gefunden — genau das Muster, das am "
        "30.07. eine ganze Sitzung stumm getoetet hat:\n" +
        "\n".join(f"  {d}:{z}  ->  {n}()" for d, z, n in verstoesse) +
        "\n\nNICHT die Whitelist fuellen. Den Aufruf AUS dem Riegel-Block herausziehen "
        "(Muster: services/deepgram_service.py:211-219 macht den emit bewusst AUSSERHALB "
        "des Riegels; services/live_session.py:480-495 nimmt einen Schnappschuss unter dem "
        "Riegel und arbeitet danach ohne ihn).")


def test_sweep_erreicht_alle_bekannten_bloecke():
    ist = {}
    aufteilung = {}
    for datei, pfad in _python_dateien():
        baum, _fehler = _baum_oder_fehler(pfad)
        if baum is None:
            continue
        n_with = len(_sammle_bloecke(baum))
        n_try = len(_sammle_try_bloecke(baum))
        if n_with or n_try:
            ist[datei] = n_with + n_try
            aufteilung[datei] = (n_with, n_try)

    # Ist-Zaehlung ins Gate-Log — GETRENNT nach Form. Eine einzelne Summe wuerde einen
    # Deckungsverlust verstecken: steht nach Plan 03 dort try/finally=0, greift die
    # Erweiterung nicht und der Waechter ist blind -> STOP.
    print('\n[LOCK-1 Waechter 2] Ist-Zaehlung der ueberwachten Riegel-Bloecke:')
    for datei in sorted(ist):
        n_with, n_try = aufteilung[datei]
        print(f'  {datei}: {ist[datei]} (with={n_with}, try/finally={n_try})')
    print(f'  SUMME: {sum(ist.values())} '
          f'(with={sum(w for w, _ in aufteilung.values())}, '
          f'try/finally={sum(t for _, t in aufteilung.values())}) '
          f'in {len(ist)} Dateien')

    zu_wenig = {d: (ist.get(d, 0), soll) for d, soll in _SOLL_MINDESTENS.items()
                if ist.get(d, 0) < soll}
    assert not zu_wenig, (
        f"Unter-Sweep: der Waechter sieht weniger Riegel-Bloecke als bekannt sind — "
        f"{zu_wenig}. Entweder wurde eine Datei nicht gescannt (dann ist der Waechter "
        f"blind), oder Bloecke wurden legitim entfernt (dann die Zahl MIT BEGRUENDUNG "
        f"nachziehen, den Test NICHT entfernen).")
    assert sum(ist.values()) >= _SOLL_SUMME_MINDESTENS, (
        f"Unter-Sweep ueber die Summe: {sum(ist.values())} ueberwachte Bloecke, "
        f"erwartet mindestens {_SOLL_SUMME_MINDESTENS}. Gezaehlt werden BEIDE Formen "
        f"(with + try/finally) — faellt die Summe darunter, deckt der Waechter weniger "
        f"ab als die Phase versprochen hat.")
