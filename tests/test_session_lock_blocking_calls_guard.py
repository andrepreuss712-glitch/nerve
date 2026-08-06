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

LOCK-2: ERNEUTE RIEGEL-NAHME UNTER GEHALTENEM RIEGEL
----------------------------------------------------
ANLASS: Anruf vom 31.07. Der LOCKWATCH-Wachhund aus LOCK-1 Teil 3 meldete beim ERSTEN
Einsatz auf Produktion `_session_state_lock >2s belegt | Faden='Thread-3 (coaching_loop)'
… gehalten=133.2s` — und zum ersten Mal stand der HALTER namentlich im Log statt nur seine
Opfer. Wurzel: services/claude_service.py:2062 nimmt den Riegel, :2076 ruft
ls.get_anonymisierer(sid), das denselben Riegel NOCHMAL nimmt. threading.Lock ist NICHT
reentrant (und das ist Absicht, services/live_session.py:308-310: „Ein RLock wuerde diesen
Design-Zwang lautlos aufloesen") -> der Faden blockiert SICH SELBST, dauerhaft. Im py-spy-
Abzug sieht ein Selbstverklemmer aus wie ein Opfer: er steht wartend in acquire(), wie alle
anderen auch.

WARUM DIE LOCK-1-HAELFTE DAS NICHT FAND: ihr Verbots-Set kennt get_session, SessionLocal,
messages.create/stream, sio.emit, requests.*, sleep, join — aber nicht die erneute
Riegel-Nahme. Genau die eine Klasse fehlte. Der Waechter war nicht falsch, er war
unvollstaendig; sein gruenes Ergebnis war wahr und wertlos zugleich.

WARUM DIE NEHMER-LISTE ABGELEITET UND NICHT GEPFLEGT WIRD: eine gepflegte Liste veraltet und
erzeugt genau dieselbe Luecke noch einmal. Der Kommentar bei services/claude_service.py:1441
ist der Beleg — dort stand das Wissen als Kommentar statt als Waechter, und bei
get_anonymisierer hat es niemand gelesen.

RESTLUECKEN — ein Waechter beweist nur, was in seinem Pruefkatalog steht (CLAUDE.md Punkt 31):
1. Dynamischer Dispatch: getattr(...)(...), Callbacks, Monkeypatch, Registry-Hooks sind fuer
   einen statischen Sweep unsichtbar.
2. Die Namens-Heuristik ist zweischneidig: sie faengt matcher.match_with_dedup, kann aber bei
   Namensgleichheit falsch anschlagen — und ein anders benannter Wrapper rutscht durch.
3. Kanten aus Modulen ausserhalb _SCAN_DIRS (app.py, database/, alembic/) werden nicht verfolgt.
4. dict-/str-Methodennamen sind NICHT ausgefiltert. Eine Kollision entstuende nur, wenn eine
   gefaehrliche Funktion wie eine dict-/str-Methode hiesse; unter den 47 abgeleiteten Nehmern
   ist das heute nicht der Fall. Die einzige theoretisch moegliche Kollision ist `index` —
   praktisch ausgeschlossen, formal UNKLAR.
5. Konstruktor-/Property-Durchrutscher: `Klasse()` loest auf den KLASSEN-Namen auf, ein
   riegel-nehmender `__init__` stuende als '__init__' in der Nehmer-Menge -> keine Kante.
   Properties/Deskriptoren erzeugen gar keinen ast.Call, sondern einen Attribut-Zugriff ->
   ebenfalls unsichtbar. Heute unkritisch (einzige riegel-nehmende Methode ist
   match_with_dedup), aber strukturell offen.
6. Lambda/def IN der Region: ast.walk steigt in Lambda-Ruempfe und in der Region definierte
   defs ab. `threading.Timer(2.0, lambda: ls.get_anonymisierer(sid))` unter dem Riegel wird
   deshalb GEMELDET, obwohl der Rumpf erst spaeter OHNE Riegel feuert. Die Richtung ist
   FALSCH-TREFFER (konservativ), nicht Durchrutscher — wer hier je einen Treffer sieht, ordnet
   ihn als Falsch-Treffer ein und nimmt ihn ueber die '# FALSCH-TREFFER:'-Regel heraus, statt
   das Muster aufzuweichen. Heute 0 Vorkommen.
7. Dritte Erwerbsform `try: <riegel>.acquire() ... finally: <riegel>.release()`: der
   eroeffnende Erwerb liegt hier IM try und wuerde als erneute Nahme GEMELDET. Die Richtung
   ist FALSCH-TREFFER (laut), nicht Durchrutscher — bewusst so gewaehlt: eine Ausnahme fuer
   die erste Anweisung haette eine ECHTE Wieder-Nahme an derselben Position STILL verschluckt
   (nachgemessen 2026-07-31). Heute 0 Vorkommen dieser Form (0 von 5 try-Riegel-Regionen in
   services/ + routes/); taucht sie auf, raeumt ein '# FALSCH-TREFFER:'-Eintrag MIT
   Begruendung sie aus — niemals durch Aufweichen des Musters.

GEPRUEFT UND GESCHLOSSEN (Cross-AI Fable 2026-07-31, Punkt 31 verlangt auch diese Aussage):
die DIREKTESTE Form der Fehlerklasse — ein verschachteltes `with <riegel>:` bzw. ein direktes
<riegel>.acquire() INNERHALB einer gehaltenen Region — waere ueber den Call-Pfad unsichtbar
(kein ast.Call bzw. bewusst kein Nehmer-Name). Sie ist NICHT offen gelassen, sondern durch
_direkte_erneute_nahmen gefangen (Meldenamen _MELDE_WITH / _MELDE_ACQUIRE) und durch
test_direkte_erneute_nahme_wird_gefangen paarweise belegt. Heute 0 Vorkommen im Code.
Rest-Kante: in der Doppelform "Erwerb im if-Test UND Erwerb als ERSTE Anweisung im try" bliebe
der zweite Erwerb ungemeldet (die erste Anweisung gilt als der regions-eroeffnende Erwerb) —
heute 0 Vorkommen, und die Alternative waere ein Selbst-Treffer auf jeder try/finally-Form.
ZWEITE SCHICHT DARUNTER: der LOCKWATCH-Wachhund (services/live_session.py:1518-1541) meldet
zur LAUFZEIT, was der statische Sweep nicht sieht. Er hat diesen Fund geliefert.

STOP-REGEL: erwartet sind 0 Verstoesse. Ein echter Fund wird mit Datei:Zeile gemeldet — NICHT
whitelistet, NICHT durch ein RLock aufgeloest, NICHT durch Aufweichen des Musters.
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
#
# ── NACHGEZOGEN 2026-08-06, Phase 08.23.2.SOFORT-2 Welle 1 (Besitzpruefung) ──
# Die Besitz-Fix-Welle hat drei Riegel-Bloecke aus routes/ ENTFERNT und zwei in
# services/live_session.py NEU angelegt. Der Schutz ist NICHT verschwunden, er ist
# GEWANDERT — genau das war der Zweck ("EIN Besitz-Pruefpunkt statt fuenf Bedingungen"):
#   routes/learning.py        2 -> 0   api_postcall_analysis/-outcome loesen _session_state
#                                      nicht mehr selbst auf; sie rufen
#                                      live_session.resolve_own_sid_by_call_id — und DIE
#                                      nimmt den Riegel (services/live_session.py:489).
#   routes/app_routes.py      4 -> 3   api_gatekeeper_phrases scannt _session_state nicht
#                                      mehr selbst; api_beenden/-precall gehen ueber die
#                                      Helfer. Ein Block bleibt.
#   services/live_session.py 26 -> 28  die zwei neuen Helfer sid_belongs_to (:462) und
#                                      resolve_own_sid_by_call_id (:489) nehmen den Riegel
#                                      jeweils in einem eigenen `with`-Block.
# Rechnung, gemessen im Deploy-Gate: 102 - 3 + 2 = 101 = die gemessene SUMME. Die
# Verschiebung geht also restlos auf; es ist kein Block unbewacht verloren gegangen.
#
# ⚠ live_session.py steigt 25 -> 27 (NICHT stehen bleiben): die zwei gewanderten Riegel
#   sind jetzt der EINZIGE Ort, an dem diese Scans synchronisiert sind. Bliebe das Soll
#   bei 25, koennte jemand den Riegel aus einem Helfer nehmen, ohne dass es hier rot wird —
#   der Waechter waere genau fuer die neue Fehlerklasse blind. Das Soll folgt der Wanderung.
# ⚠ routes/learning.py ist ENTFERNT statt auf 0 gesetzt: ein Eintrag mit Soll 0 kann nie
#   fehlschlagen. Eine Nicht-Pruefung in einer Liste von Pruefungen schwaecht die Anker
#   daneben (dieselbe Werkzeug-Falle wie ein `>= 0`-Anker). Die Datei hat heute belegbar
#   NULL Bloecke; kommt dort je wieder einer hinzu, gehoert die Zeile zurueck.
_SOLL_MINDESTENS = {
    'services/claude_service.py': 41,
    'services/deepgram_service.py': 22,
    'services/live_session.py': 27,   # 25 + 2 gewanderte (SOFORT-2)
    'routes/app_routes.py': 3,        # 4 - 1 gewandert (SOFORT-2)
    'services/prompt_pipeline.py': 3,
    'services/cost_tracker.py': 2,
    'services/einwand_keyword_matcher.py': 2,
    # 'routes/learning.py': 2,  -> ENTFERNT (SOFORT-2): heute 0 Bloecke, Begruendung oben
}
# 102 vor SOFORT-2, 101 nach der Wanderung (-3 in routes/, +2 in live_session.py):
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


# ══ Selbst-Test: der Sweep beweist, dass er beisst ═════════════════════════════
# Synthetischer Quelltext statt temporaer verunreinigter Produktiv-Datei — Begruendung
# im Modul-Docstring. Die Schnipsel stehen in tests/, das NICHT im Sweep-Scope liegt
# (_SCAN_DIRS = services/routes) -> kein Selbst-Treffer. Der Alias ist bewusst eine
# nackte Variable ohne import-Zeile: ein dedenteter Import auf Spalte 0 wuerde das
# Modul-Ebenen-Kriterium „der Waechter laedt die App nicht" treffen.

def _analysiere_quelle(quelltext):
    """Faehrt DENSELBEN Sweep gegen einen synthetischen Quelltext. Bewusst dieselben
    Helfer wie der Datei-Sweep — ein nachgebauter Mini-Detektor wuerde nur sich selbst
    beweisen. Deckt BEIDE Formen ab: with-Bloecke und try/finally mit begrenztem Erwerb."""
    baum = ast.parse(textwrap.dedent(quelltext))
    treffer = []
    for block in _sammle_bloecke(baum):
        treffer.extend(_verbotene_aufrufe_in(block))
    for tblock in _sammle_try_bloecke(baum):
        treffer.extend(_verbotene_aufrufe_in(_riegel_region(tblock)))
    return treffer


def _zaehle_bloecke(quelltext):
    """Wie viele UEBERWACHTE Bloecke sieht der Sweep in diesem Quelltext? Beide Formen."""
    baum = ast.parse(textwrap.dedent(quelltext))
    return len(_sammle_bloecke(baum)) + len(_sammle_try_bloecke(baum))


def test_sweep_erkennt_verbotene_aufrufe_in_allen_alias_schreibweisen():
    faelle = [
        ('nackt (live_session.py-Stil)', """
            with _session_state_lock:
                db = get_session()
        """, 'get_session'),
        ('Alias ls.', """
            with ls._session_state_lock:
                sio.emit('x')
        """, 'emit'),
        ('Alias _ls. (prompt_pipeline, einwand_keyword_matcher)', """
            with _ls._session_state_lock:
                time.sleep(1)
        """, 'sleep'),
        ('Alias _ls_av. (claude_service:940)', """
            with _ls_av._session_state_lock:
                db = SessionLocal()
        """, 'SessionLocal'),
        ('Alias ls_module. (deepgram_service:572)', """
            with ls_module._session_state_lock:
                t.join()
        """, 'join'),
        ('Mehr-Item-with', """
            with anderer_lock, ls._session_state_lock:
                requests.post('u')
        """, 'requests.post'),
        ('zwei Ebenen tief im selben Block', """
            with ls._session_state_lock:
                if x:
                    try:
                        client.messages.create()
                    except Exception:
                        pass
        """, 'messages.create'),
    ]
    for beschreibung, quelltext, erwartet in faelle:
        treffer = _analysiere_quelle(quelltext)
        assert len(treffer) == 1, f"{beschreibung}: erwartet 1 Treffer, war {treffer!r}"
        assert treffer[0][1] == erwartet, f"{beschreibung}: {treffer!r}"


def test_sweep_meldet_harmlose_aufrufe_nicht():
    faelle = [
        ('String-Join ist kein Faden-Join', """
            with ls._session_state_lock:
                x = ', '.join(teile)
        """),
        ('dict.get ist kein requests.get', """
            with ls._session_state_lock:
                v = d.get('k', 0)
        """),
        ('get_session AUSSERHALB jedes Riegel-Blocks', """
            def helfer():
                with anderer_lock:
                    pass
                db = get_session()
        """),
        ('anderer Riegel (with)', """
            with anderer_lock:
                sio.emit('x')
        """),
        ('try/finally-Negativfall 1: der Fehl-Zweig eines begrenzten Erwerbs', """
            if ls._session_state_lock.acquire(timeout=2.0):
                try:
                    d.pop('k', None)
                finally:
                    ls._session_state_lock.release()
            else:
                time.sleep(1)
        """),
        ('try/finally-Negativfall 2: fremder Riegel', """
            if _sessions_lock.acquire(timeout=2.0):
                try:
                    db = get_session()
                finally:
                    _sessions_lock.release()
        """),
    ]
    for beschreibung, quelltext in faelle:
        treffer = _analysiere_quelle(quelltext)
        assert treffer == [], f"{beschreibung}: Falsch-Treffer {treffer!r}"


def test_sweep_erkennt_die_begrenzten_erwerbe_aus_plan_03():
    """Die Falsch-Gruen-Sperre. Die try/finally-Form entsteht erst in Welle 2 — ohne
    diesen Selbst-Test waere in Welle 1 ununterscheidbar, ob der Detektor sie erkennt
    oder sie nur noch nicht existiert. Erkennt er sie nicht, deckt er still nichts ab.
    Geprueft wird deshalb BEIDES: der Verbots-Treffer UND die Blockzahl."""
    faelle = [
        ('Form A wie Eingriff C1 (stash_ended_session)', """
            def stash_ended_session(sid):
                if not _session_state_lock.acquire(timeout=2.0):
                    print('[LOCKWATCH] stash_ended_session: Riegel besetzt')
                    return
                try:
                    db = get_session()
                finally:
                    _session_state_lock.release()
        """, 'get_session', 1),
        ('Form B wie Eingriff C4 (handle_disconnect, cross-modul)', """
            def handle_disconnect(sid):
                if ls._session_state_lock.acquire(timeout=2.0):
                    try:
                        sio.emit('x')
                    finally:
                        ls._session_state_lock.release()
                else:
                    print('[LOCKWATCH] handle_disconnect: Riegel besetzt')
        """, 'emit', 1),
        ('Wachhund _lockwatch_tick (Plan 04 Task 2): 0 Treffer, aber 1 gezaehlter Block', """
            def _lockwatch_tick():
                if not _session_state_lock.acquire(timeout=0.05):
                    print('[LOCKWATCH] Riegel besetzt')
                    return
                try:
                    pass
                finally:
                    _session_state_lock.release()
        """, None, 1),
    ]
    for beschreibung, quelltext, erwartet, soll_bloecke in faelle:
        treffer = _analysiere_quelle(quelltext)
        if erwartet is None:
            assert treffer == [], (
                f"{beschreibung}: der Wachhund haelt den Riegel fuer 'pass' — er darf den "
                f"Waechter NICHT rot faerben ({treffer!r}).")
        else:
            assert len(treffer) == 1 and treffer[0][1] == erwartet, (
                f"{beschreibung}: der begrenzte Erwerb aus Plan 03 Task 4 wird NICHT bewacht "
                f"({treffer!r}). Genau die vier Stellen, die wir wegen einer Verklemmung "
                f"anfassen, fielen damit aus dem Waechter.")
        assert _zaehle_bloecke(quelltext) == soll_bloecke, (
            f"{beschreibung}: der Block wird nicht als ueberwachter Block GEZAEHLT — dann ist "
            f"_SOLL_MINDESTENS still falsch und der Verlust wandert in die Zahl.")


# ══ LOCK-2: erneute Riegel-Nahme unter gehaltenem Riegel ══════════════════════
# Mindest-Soll fuer die ABGELEITETE Nehmer-Menge. Faellt die Ableitung still aus (falsches
# AST-Muster, leerer Alias-Satz), findet der Sweep 0 Verstoesse und SIEHT GRUEN AUS. Diese
# Zahl macht ihn dann rot statt blind.
#
# IST-STAND 2026-07-31 (nachgemessen ueber services/ + routes/): 47 abgeleitete Nehmer —
# live_session 21, deepgram_service 10, claude_service 6, app_routes 3, cost_tracker 2,
# learning 2, prompt_pipeline 2, einwand_keyword_matcher 1.
# Fables urspruenglich genannte "48" war eine GERUNDETE Angabe, keine Messung: ihre eigene
# Aufschluesselung ergibt ebenfalls 47.
#
# WARUM 45 UND NICHT 47: der Zweck ist "rot statt blind", nicht exakte Buchfuehrung. Ein
# stiller Total-Ausfall der Ableitung liefert 0 bis eine Handvoll Nehmer — den faengt 45
# genauso zuverlaessig wie 47. Ein Boden von 47 waere dagegen bei JEDER legitimen Entfernung
# eines Nehmers rot; genau das ist real passiert (LOCK-1 hat get_sid_paused bewusst
# riegel-frei gemacht). Der Waechter waere dann ein Blockierer statt ein Netz. Der Puffer
# folgt derselben Logik wie _SOLL_MINDESTENS weiter oben ("Tiefpunkt der Kurve, nicht
# heutiger Ist-Stand").
# Die EXAKTE Ist-Zahl druckt jeder Lauf selbst ([LOCK-2]-Ausgabe unter -s) und sie gehoert
# ins SUMMARY. Sinkt sie: Ursache klaeren und MIT BEGRUENDUNG nachziehen — nie stillschweigend
# senken, nie den Test entfernen.
_SOLL_NEHMER_MINDESTENS = 45

# Falsch-Treffer-Ausnahmen NUR fuer die LOCK-2-Erweiterung. HEUTE LEER — jeder Eintrag
# braucht einen '# FALSCH-TREFFER:'-Kommentar mit Datei:Zeile und Begruendung.
# Ein ECHTER Fund gehoert NICHT hierher, sondern gemeldet (STOP-Regel im Docstring).
_ERNEUTE_NAHME_FALSCH_TREFFER = frozenset()   # {(datei, zeile, name), ...}

# Meldenamen der DIREKTEN Wieder-Nahme. Bewusst von den Call-Treffern
# ('<zieldatei>::<funktion>') unterscheidbar: Plan 02 wertet die Trefferzeilen aus, und ein
# direkter Treffer darf dort nicht als Call-Treffer gelesen werden. Als Konstanten, damit die
# Zeichenkette GENAU EINMAL im Code steht und die Selbst-Tests sie nicht zweitschreiben.
_MELDE_WITH = '<direkte erneute Nahme (with)>'
_MELDE_ACQUIRE = '<direkte erneute Nahme (.acquire)>'


# ── Nehmer-Erkennung (D-3 Punkt 1) ────────────────────────────────────────────
def _ist_riegel_acquire(call):
    """True fuer <riegel>.acquire(...) — Alias-fest ueber DIESELBE Riegel-Erkennung wie der
    with-Zweig (_ist_session_state_lock). Zweite Form der Riegel-Nahme seit LOCK-1 Plan 03."""
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == 'acquire'
            and _ist_session_state_lock(f.value))


def _eigene_knoten(fn_knoten):
    """Alle Knoten im Rumpf von fn_knoten OHNE die Ruempfe verschachtelter def/class.

    WARUM (D-3 Punkt 1): ast.walk wuerde in verschachtelte Funktionen absteigen und
    routes/app_routes.py:api_beenden faelschlich zum Riegel-Nehmer machen, weil das darin
    definierte _load_beenden_state:215 einen Riegel haelt. Die verschachtelte Funktion wird
    separat als EIGENE Funktion erfasst und ist dort zu Recht Nehmer.
    """
    ergebnis = []

    def _lauf(knoten):
        for kind in ast.iter_child_nodes(knoten):
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            ergebnis.append(kind)
            _lauf(kind)

    _lauf(fn_knoten)
    return ergebnis


def _nimmt_riegel_selbst(fn_knoten):
    """Nehmer = im EIGENEN Rumpf liegt ein Riegel-`with` ODER ein <riegel>.acquire().
    Nichts hartkodiert: eine neue riegel-nehmende Funktion ist damit automatisch geschuetzt.
    Eine gepflegte Liste wuerde veralten und dieselbe Luecke neu erzeugen."""
    for k in _eigene_knoten(fn_knoten):
        if isinstance(k, ast.With) and any(
                _ist_session_state_lock(i.context_expr) for i in k.items):
            return True
        if isinstance(k, ast.Call) and _ist_riegel_acquire(k):
            return True
    return False


# ── Modul-/Alias-Aufloesung (D-3 Punkt 2) ─────────────────────────────────────
def _punkt_name(datei):
    """'services/live_session.py' -> 'services.live_session'"""
    return datei[:-3].replace('/', '.')


def _aliase_und_importe(baum, bekannte_module):
    """(modul_aliase, funktions_importe) fuer EINE Datei.

    modul_aliase:    alias-Name        -> ziel-DATEI   (deckt ls / _ls / _ls_av / ls_module)
    funktions_importe: lokaler Name    -> (ziel-DATEI, funktions-Name)

    ast.walk statt baum.body: die riskantesten Aliase sind FUNKTIONSLOKALE lazy-Importe gegen
    Modul-Zyklen (services/claude_service.py:936 `import services.live_session as _ls_av`).
    Ein Sammler nur auf Modul-Ebene faende genau die fuenf Faelle nicht, die schon LOCK-1 zum
    AST gezwungen haben.
    """
    aliase, importe = {}, {}
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for a in knoten.names:
                if a.name in bekannte_module:
                    aliase[a.asname or a.name.split('.')[-1]] = bekannte_module[a.name]
        elif isinstance(knoten, ast.ImportFrom):
            if not knoten.module:
                continue
            for a in knoten.names:
                voll = f'{knoten.module}.{a.name}'
                if voll in bekannte_module:
                    # `from services import live_session as ls` -> Modul, kein Symbol
                    aliase[a.asname or a.name] = bekannte_module[voll]
                elif knoten.module in bekannte_module:
                    importe[a.asname or a.name] = (bekannte_module[knoten.module], a.name)
    return aliase, importe


# ── Funktionen + Kanten einer Datei ───────────────────────────────────────────
def _funktionen_der_datei(baum):
    """[(name, knoten)] fuer JEDE def/async def im Baum — inkl. Methoden und verschachtelter
    defs. Der Name ist der BLOSSE Funktionsname (ohne Klasse): fuer Aufrufer ist eine Methode
    ohnehin nur als `obj.name(...)` sichtbar, und genau darauf setzt der Zweitpass auf."""
    return [(k.name, k) for k in ast.walk(baum)
            if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _aufloesen(func, datei, aliase, importe, lokale_namen):
    """(ziel_datei|None, name|None) fuer den AUFGERUFENEN Ausdruck eines ast.Call.

    ziel_datei is None + name gesetzt  ->  nicht aufloesbar, geht in den namensbasierten
                                           Zweitpass (D-3 Punkt 3).
    """
    if isinstance(func, ast.Name):
        if func.id in lokale_namen:
            return datei, func.id
        if func.id in importe:
            return importe[func.id]
        return None, func.id
    if isinstance(func, ast.Attribute):
        v = func.value
        if isinstance(v, ast.Name) and v.id in aliase:
            return aliase[v.id], func.attr
        return None, func.attr
    return None, None


def _kanten_der_funktion(fn_knoten, datei, aliase, importe, lokale_namen):
    """(aufgeloeste_ziele, namens_ziele) aus dem EIGENEN Rumpf.

    NUR Aufruf-Positionen (knoten.func) — KEINE Argument-Referenzen (D-3 Punkt 4). Sonst
    wuerde threading.Timer(..., ls._flush_segment) (services/deepgram_service.py:254) ein
    Dauer-Falschtreffer: dort wird die Funktion nur als WERT weitergereicht, der Callback
    feuert spaeter auf dem Timer-Faden OHNE Riegel.
    """
    ziele, namen = set(), set()
    for k in _eigene_knoten(fn_knoten):
        if not isinstance(k, ast.Call):
            continue
        zdatei, zname = _aufloesen(k.func, datei, aliase, importe, lokale_namen)
        if zname is None:
            continue
        if zdatei is None:
            namen.add(zname)
        else:
            ziele.add((zdatei, zname))
    return ziele, namen


# ── Fixpunkt (D-3 Punkt 2) ────────────────────────────────────────────────────
def _graph_bauen(baeume):
    """(gefaehrlich, gefaehrliche_namen, nehmer, nehmer_pro_datei) fuer {datei: baum}.

    FIXPUNKT-ITERATION, KEINE REKURSION: die Menge waechst monoton ueber eine endliche
    Grundmenge, terminiert also garantiert — auch bei Zyklen (A ruft B, B ruft A). Eine
    Rekursion ueber den Call-Graph liefe dort ohne Besuchs-Markierung endlos.
    Beliebige Tiefe ist damit gratis: der Kegel aus 99 transitiv gefaehrlichen Funktionen
    (Ist-Stand 2026-07-31 ueber _SCAN_DIRS) entsteht von selbst.
    """
    bekannte_module = {_punkt_name(d): d for d in baeume}
    alle = {}          # (datei, name) -> (ziele, namens_ziele)
    nehmer = set()
    nehmer_pro_datei = {}
    for datei, baum in baeume.items():
        aliase, importe = _aliase_und_importe(baum, bekannte_module)
        funktionen = _funktionen_der_datei(baum)
        lokale_namen = {n for n, _ in funktionen}
        for name, knoten in funktionen:
            schluessel = (datei, name)
            alle[schluessel] = _kanten_der_funktion(
                knoten, datei, aliase, importe, lokale_namen)
            if _nimmt_riegel_selbst(knoten):
                nehmer.add(schluessel)
                nehmer_pro_datei[datei] = nehmer_pro_datei.get(datei, 0) + 1

    gefaehrlich = set(nehmer)
    gefaehrliche_namen = {name for _d, name in gefaehrlich}
    geaendert = True
    while geaendert:
        geaendert = False
        for schluessel, (ziele, namens_ziele) in alle.items():
            if schluessel in gefaehrlich:
                continue
            if (ziele & gefaehrlich) or (namens_ziele & gefaehrliche_namen):
                gefaehrlich.add(schluessel)
                gefaehrliche_namen.add(schluessel[1])
                geaendert = True
    return gefaehrlich, gefaehrliche_namen, nehmer, nehmer_pro_datei


# ── Verstoss-Sweep — ZWEI Pfade ───────────────────────────────────────────────
def _direkte_erneute_nahmen(baum):
    """[(zeile, meldename)] — die DIREKTESTE Form der Fehlerklasse in EINER Datei:
    ein Riegel-`with` ODER ein <riegel>.acquire() INNERHALB einer bereits gehaltenen Region.

    WARUM EIN EIGENER PFAD: _erneute_nahmen_finden wertet nur ast.Call ueber die Nehmer-Menge
    aus. (a) Ein verschachteltes `with ls._session_state_lock:` ist gar kein Call. (b) Ein
    direktes ls._session_state_lock.acquire() loest auf den Namen 'acquire' auf, und der ist
    als _TracedLock-Methode bewusst KEIN Nehmer (der Ausschluss ist fuer die Nehmer-Ableitung
    richtig). Beides ist exakt der Selbstverklemmer vom 31.07., nur ohne Zwischenfunktion —
    und beides waere ueber den Call-Pfad unsichtbar.

    KEIN SELBST-TREFFER DER REGIONS-WURZEL: _sammle_bloecke liefert die Riegel-`with`-Bloecke,
    und genau diese Knoten SIND die Wurzeln. Ein naives ast.walk(wurzel) faende die Wurzel
    wieder und meldete jeden Riegel-Block als Verstoss gegen sich selbst. Gemeldet wird nur,
    was ECHT INNERHALB liegt:
      * with-Regionen: Identitaets-Vergleich `k is wurzel` (die Wurzel selbst faellt raus,
        ein verschachtelter Riegel-`with` nicht).
      * try-Regionen: die Region ist eine ANWEISUNGS-Liste, und _riegel_region liefert
        `body + orelse + except-Ruempfe + finally-VOR-release`. Bei BEIDEN Hausformen des
        begrenzten Erwerbs steht das eroeffnende acquire im `if`-Test bzw. eine Zeile hoeher,
        also AUSSERHALB des `try` — es liegt damit gar nicht erst in der Region und kann sich
        nicht selbst melden. Es braucht deshalb KEINE Positions-Ausnahme.

    WARUM KEINE AUSNAHME DER ERSTEN ANWEISUNG (empirisch entschieden, 2026-07-31):
    Ein frueherer Entwurf schloss die erste Anweisung aus, um zusaetzlich die dritte Form
    (`try: lock.acquire() ... finally: lock.release()`) vor einem Selbst-Treffer zu schuetzen.
    Das riss ein Loch derselben Klasse, die dieser Waechter schliesst: eine ECHTE Wieder-Nahme
    als ERSTE Anweisung einer Form-1/2-Region waere still durchgerutscht. Nachgemessen: die
    dritte Form kommt im Produktiv-Code NICHT vor (0 von 5 try-Riegel-Regionen in
    services/ + routes/ haben ein acquire als erste try-Anweisung), und die beiden echten
    Hausformen brauchen die Ausnahme nicht. Sie faellt deshalb weg.
    Taucht die dritte Form kuenftig auf, meldet der Waechter sie LAUT (ein
    `# FALSCH-TREFFER:`-Eintrag mit Begruendung raeumt sie aus) statt eine echte Wieder-Nahme
    STILL zu verschlucken. Falsch-Treffer-Richtung ist bei einem Waechter die sichere
    Richtung — "rot statt blind" (Punkt 31).
    """
    treffer = []

    def _ist_riegel_with(k):
        return isinstance(k, ast.With) and any(
            _ist_session_state_lock(i.context_expr) for i in k.items)

    for wurzel in _sammle_bloecke(baum):
        for k in ast.walk(wurzel):
            if k is wurzel:
                continue          # die Wurzel ist die gehaltene Region, kein Verstoss
            if _ist_riegel_with(k):
                treffer.append((getattr(k, 'lineno', 0), _MELDE_WITH))
            elif isinstance(k, ast.Call) and _ist_riegel_acquire(k):
                treffer.append((getattr(k, 'lineno', 0), _MELDE_ACQUIRE))

    for tknoten in _sammle_try_bloecke(baum):
        # Keine Positions-Ausnahme: der eroeffnende Erwerb liegt bei beiden Hausformen
        # ausserhalb des try und damit nicht in dieser Region (siehe Docstring).
        for anweisung in _riegel_region(tknoten):
            for k in ast.walk(anweisung):
                if _ist_riegel_with(k):
                    treffer.append((getattr(k, 'lineno', 0), _MELDE_WITH))
                elif isinstance(k, ast.Call) and _ist_riegel_acquire(k):
                    treffer.append((getattr(k, 'lineno', 0), _MELDE_ACQUIRE))
    return treffer


def _erneute_nahmen_finden(baeume):
    """[(datei, zeile, meldename)] — ZWEI Pfade.

    Pfad A (Call-Pfad): Aufrufe unter dem Riegel, die den Riegel selbst ueber eine
    Zwischenfunktion (direkt oder transitiv) wieder nehmen.
    Pfad B (_direkte_erneute_nahmen): die DIREKTE Wieder-Nahme ohne Zwischenfunktion —
    verschachteltes Riegel-`with` (kein ast.Call) und <riegel>.acquire() (bewusst kein
    Nehmer-Name). Ohne Pfad B bliebe die DIREKTESTE Form der Fehlerklasse unsichtbar.

    Beide Pfade nutzen DIESELBEN Regions-Helfer wie LOCK-1
    (_sammle_bloecke / _sammle_try_bloecke / _riegel_region) — eine zweite Regions-Logik
    waere der Anfang der Divergenz.

    Dass die Regionslogik trennt, ist am Produktiv-Code belegt: services/claude_service.py:2076
    liegt IM Block :2062 (Treffer), :2090 und :1355 liegen DAHINTER (kein Treffer) — derselbe
    Quelltext, andere Position.
    """
    gefaehrlich, gefaehrliche_namen, _n, _p = _graph_bauen(baeume)
    bekannte_module = {_punkt_name(d): d for d in baeume}
    treffer = []
    for datei, baum in baeume.items():
        aliase, importe = _aliase_und_importe(baum, bekannte_module)
        lokale_namen = {n for n, _ in _funktionen_der_datei(baum)}
        regionen = [[b] for b in _sammle_bloecke(baum)]
        regionen += [_riegel_region(t) for t in _sammle_try_bloecke(baum)]
        for region in regionen:
            for wurzel in region:
                for k in ast.walk(wurzel):
                    if not isinstance(k, ast.Call):
                        continue
                    zdatei, zname = _aufloesen(
                        k.func, datei, aliase, importe, lokale_namen)
                    if zname is None:
                        continue
                    ist_treffer = ((zdatei, zname) in gefaehrlich if zdatei
                                   else zname in gefaehrliche_namen)
                    if ist_treffer:
                        melde = (f'{zdatei or "?"}::{zname}')
                        treffer.append((datei, getattr(k, 'lineno', 0), melde))
        # Pfad B: direkte Wieder-Nahme in derselben Datei (eigene Regions-Durchlaeufe, weil
        # hier KNOTEN geprueft werden statt Call-Kanten — Schicht 4 Punkt 6).
        for zeile, melde in _direkte_erneute_nahmen(baum):
            treffer.append((datei, zeile, melde))
    return sorted(set(treffer))


def test_keine_erneute_riegel_nahme_unter_dem_riegel():
    baeume = {}
    fehler = []
    for datei, pfad in _python_dateien():
        baum, f = _baum_oder_fehler(pfad)
        if baum is None:
            fehler.append((datei, 0, f'SYNTAX ({f})'))
            continue
        baeume[datei] = baum
    verstoesse = [t for t in _erneute_nahmen_finden(baeume)
                  if t not in _ERNEUTE_NAHME_FALSCH_TREFFER] + fehler
    assert not verstoesse, (
        "Erneute Riegel-Nahme unter gehaltenem _session_state_lock — der Faden blockiert "
        "SICH SELBST (threading.Lock ist NICHT reentrant, und das ist Absicht: "
        "services/live_session.py:308-310):\n" +
        "\n".join(f"  {d}:{z}  ->  {n}" for d, z, n in verstoesse) +
        "\n\nNICHT die Whitelist fuellen und KEIN RLock. Den Wert direkt aus dem SCHON "
        "GEHALTENEN State lesen (Muster: services/live_session.py:859-863 und "
        "services/claude_service.py:1440-1442) oder den Aufruf VOR den Block ziehen "
        "(Muster: services/claude_service.py:2090).")


def test_nehmer_ableitung_faellt_nicht_still_aus():
    baeume = {}
    for datei, pfad in _python_dateien():
        baum, _f = _baum_oder_fehler(pfad)
        if baum is not None:
            baeume[datei] = baum
    _g, _gn, nehmer, pro_datei = _graph_bauen(baeume)
    print('\n[LOCK-2] Abgeleitete Riegel-NEHMER (nichts hartkodiert):')
    for datei in sorted(pro_datei):
        print(f'  {datei}: {pro_datei[datei]}')
    print(f'  SUMME: {len(nehmer)} Nehmer, davon transitiv gefaehrlich: {len(_g)}')
    assert len(nehmer) >= _SOLL_NEHMER_MINDESTENS, (
        f"Die Nehmer-Ableitung liefert nur {len(nehmer)} Funktionen, erwartet mindestens "
        f"{_SOLL_NEHMER_MINDESTENS} (gemessener Ist-Stand 2026-07-31: 47). Entweder greift das "
        f"AST-Muster nicht mehr (dann ist der Waechter BLIND, nicht gruen), oder Nehmer "
        f"wurden legitim zurueckgebaut (dann die Zahl MIT BEGRUENDUNG nachziehen, den Test "
        f"NICHT entfernen).")


# ══ LOCK-2 Selbst-Tests: die Erweiterung beweist, dass sie beisst ══════════════
# Wieder synthetischer Quelltext statt verunreinigter Produktiv-Datei (Begruendung im
# Modul-Docstring). Die Schnipsel liegen in tests/, das NICHT in _SCAN_DIRS steht ->
# kein Selbst-Treffer im Datei-Sweep. Die Datei-Namen sind reine SCHLUESSEL; sie muessen
# auf der Platte nicht existieren, _python_dateien() wird dabei nicht befragt.

def _erneute_nahme_in_quelle(quelltext, datei='services/synthetisch.py'):
    """Faehrt die LOCK-2-Erweiterung gegen einen synthetischen Quelltext — bewusst ueber
    DIESELBE Funktion wie der Datei-Sweep (_erneute_nahmen_finden). Ein nachgebauter
    Mini-Detektor wuerde nur sich selbst beweisen (LOCK-1-Lehre)."""
    return _erneute_nahme_in_quellen({datei: quelltext})


def _erneute_nahme_in_quellen(quellen):
    """Mehr-Datei-Variante. Die Alias-Aufloesung laeuft per Definition ueber Modul-Grenzen
    (ein funktionslokales `import services.live_session as _ls_av` in Datei A zeigt auf Datei
    B) — mit nur EINER synthetischen Datei ist sie gar nicht pruefbar, weil `bekannte_module`
    dann nur diese eine Datei kennt."""
    return _erneute_nahmen_finden(
        {d: ast.parse(textwrap.dedent(q)) for d, q in quellen.items()})


def test_transitivitaet_greift_ueber_zwei_ebenen():
    """Die eigentliche Falsch-Gruen-Sperre: ohne einen synthetischen 2-Ebenen-Fall ist nicht
    unterscheidbar, ob die Fixpunkt-Transitivitaet greift oder ob es zufaellig keinen
    2-Ebenen-Fall im Repo gibt."""
    quelle = """
        def _tief():
            with ls._session_state_lock:
                pass

        def _mittel(sid):
            return _tief()

        def oben(sid):
            with ls._session_state_lock:
                x = _mittel(sid)
    """
    treffer = _erneute_nahme_in_quelle(quelle)
    assert len(treffer) == 1, f"Transitivitaet greift NICHT: {treffer!r}"
    assert treffer[0][2].endswith('::_mittel'), treffer

    # Gegenprobe: ohne den Riegel in `oben` steht der Aufruf unter KEINEM Riegel.
    ohne_riegel = """
        def _tief():
            with ls._session_state_lock:
                pass

        def _mittel(sid):
            return _tief()

        def oben(sid):
            x = _mittel(sid)
    """
    assert _erneute_nahme_in_quelle(ohne_riegel) == [], (
        "Ohne gehaltenen Riegel ist derselbe Aufruf harmlos — meldet der Sweep ihn "
        "trotzdem, kommt der Treffer nicht aus der Region.")


def test_verschachtelte_defs_haften_nicht_fuer_den_aeusseren():
    """Nachbau von routes/app_routes.py:api_beenden mit dem verschachtelten
    _load_beenden_state:215. Der aeussere Rahmen haftet NICHT fuer den Riegel im
    verschachtelten Rumpf — er haftet nur fuer das, was er selbst ruft."""
    quelle = """
        def api_beenden():
            def _load_beenden_state(sid):
                with ls._session_state_lock:
                    return 1
            return _load_beenden_state('x')

        def ruft_nur_den_aeusseren():
            with ls._session_state_lock:
                api_beenden()
    """
    treffer = _erneute_nahme_in_quelle(quelle)
    assert len(treffer) == 1, (
        f"api_beenden ist TRANSITIV gefaehrlich (es RUFT _load_beenden_state) — der Aufruf "
        f"unter dem Riegel muss gemeldet werden: {treffer!r}")
    assert treffer[0][2].endswith('::api_beenden'), treffer

    # Der NEHMER-Status haengt am EIGENEN Rumpf: ohne den Aufruf ist api_beenden weder
    # Nehmer noch gefaehrlich, obwohl der Riegel im verschachtelten def steht.
    quelle_ohne_aufruf = """
        def api_beenden():
            def _load_beenden_state(sid):
                with ls._session_state_lock:
                    return 1
            return 0
    """
    baeume = {'services/synthetisch.py': ast.parse(textwrap.dedent(quelle_ohne_aufruf))}
    gefaehrlich, _gn, nehmer, _p = _graph_bauen(baeume)
    assert ('services/synthetisch.py', 'api_beenden') not in nehmer, (
        "api_beenden gilt faelschlich als Riegel-NEHMER, nur weil _load_beenden_state in "
        "ihm definiert ist — _eigene_knoten steigt nicht in verschachtelte defs ab.")
    assert ('services/synthetisch.py', 'api_beenden') not in gefaehrlich
    assert ('services/synthetisch.py', '_load_beenden_state') in nehmer


def test_argument_referenz_ist_kein_treffer():
    """Nachbau von services/deepgram_service.py:254 — threading.Timer(..., ls._flush_segment)
    reicht die Funktion nur als WERT weiter; der Callback feuert spaeter auf dem Timer-Faden
    OHNE Riegel. Waere das ein Treffer, waere es ein Dauer-Falschtreffer."""
    quelle = """
        def _flush_segment(sid):
            with ls._session_state_lock:
                pass

        def plant_timer(sid):
            with ls._session_state_lock:
                threading.Timer(2.0, _flush_segment).start()
    """
    assert _erneute_nahme_in_quelle(quelle) == [], (
        "Eine reine Argument-Referenz wurde als Aufruf gemeldet — "
        "services/deepgram_service.py:254 waere ein Dauer-Falschtreffer.")

    # Gepaart: derselbe Name als AUFRUF ist sehr wohl ein Treffer. Ohne diese Paarung
    # waere nicht unterscheidbar, ob der Detektor korrekt trennt oder nur nichts findet.
    als_aufruf = """
        def _flush_segment(sid):
            with ls._session_state_lock:
                pass

        def plant_timer(sid):
            with ls._session_state_lock:
                _flush_segment(sid)
    """
    treffer = _erneute_nahme_in_quelle(als_aufruf)
    assert len(treffer) == 1 and treffer[0][2].endswith('::_flush_segment'), (
        f"Der echte Aufruf desselben Nehmers wird NICHT gemeldet: {treffer!r}")


def test_zyklus_im_aufrufgraph_terminiert():
    """Terminierungs-Beweis. Eine Rekursion ueber den Call-Graph liefe hier ohne
    Besuchs-Markierung endlos (bzw. RecursionError); die Fixpunkt-Iteration terminiert
    garantiert. Der Test ist gruen, wenn er ueberhaupt zurueckkehrt."""
    quelle = """
        def a():
            return b()

        def b():
            return a()

        def nimmt():
            with ls._session_state_lock:
                return a()
    """
    assert _erneute_nahme_in_quelle(quelle) == [], (
        "Weder a noch b nimmt je einen Riegel — kein Treffer erwartet.")

    # Derselbe Zyklus, aber b nimmt den Riegel: die Gefahr muss ueber den Zyklus zu a
    # weiterwandern, und der Sweep muss trotzdem terminieren.
    mit_riegel_im_zyklus = """
        def a():
            return b()

        def b():
            with ls._session_state_lock:
                pass
            return a()

        def nimmt():
            with ls._session_state_lock:
                return a()
    """
    treffer = _erneute_nahme_in_quelle(mit_riegel_im_zyklus)
    assert len(treffer) == 1 and treffer[0][2].endswith('::a'), (
        f"Der Zyklus traegt die Gefahr nicht weiter: {treffer!r}")


def test_erneute_nahme_meldet_harmlose_aufrufe_nicht():
    faelle = [
        ('dict-/list-Methoden unter dem Riegel', """
            def oben(sid):
                with ls._session_state_lock:
                    v = d.get('k', 0)
                    liste.append(v)
        """),
        ('riegel-freie Funktion unter dem Riegel (live_session.py:1106)', """
            def ist_painpoint_duplikat(text, liste):
                return text in liste

            def oben(sid):
                with ls._session_state_lock:
                    ist_painpoint_duplikat('x', [])
        """),
        ('Nehmer-Aufruf AUSSERHALB jedes Riegel-Blocks (claude_service.py:2090)', """
            def get_anonymisierer(sid):
                with ls._session_state_lock:
                    return 1

            def oben(sid):
                a = get_anonymisierer(sid)
        """),
        ('Nehmer-Aufruf NACH dem release im finally (stash_ended_session:742)', """
            def get_anonymisierer(sid):
                with ls._session_state_lock:
                    return 1

            def stash_ended_session(sid):
                if not ls._session_state_lock.acquire(timeout=2.0):
                    return
                try:
                    d.pop('k', None)
                finally:
                    ls._session_state_lock.release()
                    get_anonymisierer(sid)
        """),
    ]
    for beschreibung, quelltext in faelle:
        treffer = _erneute_nahme_in_quelle(quelltext)
        assert treffer == [], f"{beschreibung}: Falsch-Treffer {treffer!r}"


def test_namensbasierter_zweitpass_faengt_methoden_aufrufe():
    """Der Anker fuer D-3 Punkt 3. services/einwand_keyword_matcher.py:match_with_dedup ist
    fuer jeden Aufrufer nur als `matcher.match_with_dedup(...)` sichtbar — der Empfaenger ist
    NICHT aufloesbar. Ohne den namensbasierten Zweitpass bliebe die Klasse unsichtbar, und
    NICHTS wuerde rot: der eine reale Treffer laeuft ueber die Alias-Aufloesung."""
    quelle = """
        class EinwandMatcher:
            def match_with_dedup(self, text):
                with _ls._session_state_lock:
                    return 1

        def oben(matcher, text):
            with ls._session_state_lock:
                return matcher.match_with_dedup(text)
    """
    treffer = _erneute_nahme_in_quelle(quelle)
    assert len(treffer) == 1, f"Der namensbasierte Zweitpass greift NICHT: {treffer!r}"
    assert treffer[0][2] == '?::match_with_dedup', (
        f"Erwartet ein Treffer OHNE aufgeloeste Datei ('?') — genau das belegt, dass der "
        f"NAMENS-pass gefeuert hat und nicht die Alias-Aufloesung: {treffer!r}")

    # Gepaarte Gegenprobe: unbekannter Methodenname -> 0 Treffer. Ohne sie waere nicht
    # unterscheidbar, ob der Zweitpass gezielt trifft oder pauschal jeden Attribut-Aufruf.
    unbekannt = """
        class EinwandMatcher:
            def match_with_dedup(self, text):
                with _ls._session_state_lock:
                    return 1

        def oben(matcher, text):
            with ls._session_state_lock:
                return matcher.unbekannte_methode(text)
    """
    assert _erneute_nahme_in_quelle(unbekannt) == [], (
        "Der Zweitpass meldet pauschal jeden Attribut-Aufruf statt nur die gefaehrlichen "
        "Namen — das waere ein Dauer-Falschtreffer.")


def test_alias_aufloesung_zielt_auf_die_datei_nicht_nur_den_namen():
    """Die Alias-Aufloesung ist heute NUR durch den einen realen Treffer belegt — und der
    verschwindet mit Plan 03. Danach bewacht nichts mehr, ob _ls_av.get_anonymisierer()
    unter einem Riegel ueberhaupt noch erkannt wird. Nachbau des funktionslokalen
    Lazy-Imports aus services/claude_service.py:936."""
    ziel = """
        def get_anonymisierer(sid):
            with _session_state_lock:
                return 1
    """
    rufer = """
        def coaching_loop(sid):
            import services.live_session as _ls_av
            with _ls_av._session_state_lock:
                return _ls_av.get_anonymisierer(sid)
    """
    treffer = _erneute_nahme_in_quellen({
        'services/live_session.py': ziel,
        'services/claude_service.py': rufer,
    })
    assert len(treffer) == 1, f"Die Alias-Aufloesung greift NICHT: {treffer!r}"
    assert treffer[0][2] == 'services/live_session.py::get_anonymisierer', treffer

    # Gepaarte Gegenprobe: derselbe Alias zeigt auf eine RIEGEL-FREIE Funktion GLEICHEN
    # Namens — waehrend der gefaehrliche Namensvetter weiterhin im Baum-Satz liegt.
    # 0 Treffer beweist: die Aufloesung zielt auf die DATEI, nicht bloss auf den Namen.
    harmlos = """
        def get_anonymisierer(sid):
            return 1
    """
    rufer_harmlos = """
        def coaching_loop(sid):
            import services.harmlos as _ls_av
            with _ls_av._session_state_lock:
                return _ls_av.get_anonymisierer(sid)
    """
    assert _erneute_nahme_in_quellen({
        'services/live_session.py': ziel,
        'services/harmlos.py': harmlos,
        'services/claude_service.py': rufer_harmlos,
    }) == [], (
        "Die Aufloesung zielt nur auf den NAMEN statt auf die Datei, auf die der Alias "
        "zeigt — ein gleichnamiger riegel-freier Helfer waere ein Dauer-Falschtreffer.")


def test_direkte_erneute_nahme_wird_gefangen():
    """Pfad B: verschachteltes Riegel-`with` und direktes <riegel>.acquire() unter dem Riegel.
    Beides ist der Selbstverklemmer vom 31.07. OHNE Zwischenfunktion — und beides ist ueber den
    Call-Pfad unsichtbar (kein ast.Call bzw. bewusst kein Nehmer-Name). Die beiden
    Gegenproben beweisen, dass die Regions-WURZEL sich nicht selbst meldet."""
    verschachtelt = """
        def oben(sid):
            with ls._session_state_lock:
                with ls._session_state_lock:
                    pass
    """
    treffer = _erneute_nahme_in_quelle(verschachtelt)
    assert len(treffer) == 1 and treffer[0][2] == _MELDE_WITH, (
        f"Verschachtelter Riegel-with unter gehaltenem Riegel NICHT gefangen: {treffer!r}")

    nebeneinander = """
        def a(sid):
            with ls._session_state_lock:
                pass

        def b(sid):
            with ls._session_state_lock:
                pass
    """
    assert _erneute_nahme_in_quelle(nebeneinander) == [], (
        "Die Regions-WURZEL meldet sich selbst — dann waere JEDER Riegel-Block ein "
        "'Verstoss' (heute 42 with-Bloecke), der Waechter unbrauchbar, und der bequeme "
        "Ausweg waere ein Aufweichen des Musters.")

    direkter_erwerb = """
        def oben(sid):
            with ls._session_state_lock:
                ls._session_state_lock.acquire(timeout=2.0)
    """
    treffer = _erneute_nahme_in_quelle(direkter_erwerb)
    assert len(treffer) == 1 and treffer[0][2] == _MELDE_ACQUIRE, (
        f"Direkter <riegel>.acquire() unter gehaltenem Riegel NICHT gefangen: {treffer!r}")

    eroeffnender_erwerb = """
        def stash_ended_session(sid):
            if not ls._session_state_lock.acquire(timeout=2.0):
                return
            try:
                d.pop('k', None)
            finally:
                ls._session_state_lock.release()
    """
    assert _erneute_nahme_in_quelle(eroeffnender_erwerb) == [], (
        "Der regions-EROEFFNENDE Erwerb meldet sich selbst — dann waere jede begrenzte "
        "Erwerbsform aus LOCK-1 Plan 03 Task 4 ein 'Verstoss'.")

    # Die beiden Faelle, die eine Positions-Ausnahme (`pos == 0`) still verschluckt haette.
    # Ohne sie waere der Waechter an genau der Stelle blind, die er bewachen soll.
    wieder_nahme_als_erste_anweisung = """
        def oben(sid):
            if not ls._session_state_lock.acquire(timeout=2.0):
                return
            try:
                ls._session_state_lock.acquire()
            finally:
                ls._session_state_lock.release()
    """
    treffer = _erneute_nahme_in_quelle(wieder_nahme_als_erste_anweisung)
    assert len(treffer) == 1 and treffer[0][2] == _MELDE_ACQUIRE, (
        f"Echte Wieder-Nahme als ERSTE Anweisung einer try-Region NICHT gefangen: "
        f"{treffer!r} — eine Positions-Ausnahme fuer pos==0 waere genau hier blind.")

    verschachtelt_in_try_region = """
        def oben(sid):
            if not ls._session_state_lock.acquire(timeout=2.0):
                return
            try:
                with ls._session_state_lock:
                    pass
            finally:
                ls._session_state_lock.release()
    """
    treffer = _erneute_nahme_in_quelle(verschachtelt_in_try_region)
    assert len(treffer) == 1 and treffer[0][2] == _MELDE_WITH, (
        f"Riegel-`with` innerhalb einer begrenzt erworbenen Region NICHT gefangen: {treffer!r}")
