"""METRIK-1 Plan 08 (D-13/D-14): Das Anruf-Fenster benotet nicht mehr.

Serverseitig pruefbar, KEIN Browser noetig — das Test-Tor hat keinen.
Die ersten beiden Tests belegen Laufzeit-Verhalten (Request gegen die echte PG nerve_test
bzw. die Laufzeit-Schnittstelle des Routen-Moduls), kein Quelltext-Vorhandensein.
Der dritte Test (Pflicht-Nachtrag 17.08., Task 2b) prueft den Kontrollfluss-Vertrag des
Browser-Aufraeumers — seine ausdrueckliche Begruendung steht direkt ueber ihm.

★ ERST-ROT: Beide Tests MUESSEN gegen den Stand vor Task 2 ROT sein — die Trend-Route
antwortet dort noch, und die Vierer-Formel haengt noch am Modul.

Jeder Test traegt einen gepaarten Existenz-Anker in DERSELBEN Funktion. Ohne ihn waere
"404" nicht von "Test-Client kaputt / nicht eingeloggt" und "Attribut fehlt" nicht von
"Modul gar nicht geladen" zu unterscheiden (Bau-Regel 20).

Alle committeten Rows werden im POST-yield-Teardown via cleanup_rows weggeraeumt
(Test-Cleanup-Regel, public.* ohne Tenant-GUC). Emails sind uuid-suffixed gegen die
UNIQUE-Constraint auf users.email.
"""

import os
import re
import uuid

import pytest
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import User, Organisation


@pytest.fixture
def cleanup_tracker(client):
    """yield ein {Model: [ids]}-Dict; POST-yield reverse-FK-clean via cleanup_rows (public.*)."""
    ids = {User: [], Organisation: []}
    yield ids
    cleanup_rows(client._test_session, ids)


def _make_user(client, tracker):
    """Legt Org + bestaetigten User auf der MODUL-SessionLocal an und committet.

    email_confirmed=True ist Pflicht: das login_required-Gate ist fail-closed
    (AUTH-EMAIL-VERIFY D-01b) und wuerde jeden anderen Wert auf die Warteseite lenken —
    dann waere jede Antwort ein 302 und der Existenz-Anker unten wertlos.
    """
    db = client._test_session
    org = Organisation(name='TestOrg', plan='starter')
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=f'pipnote-{uuid.uuid4().hex[:8]}@nerve.local',
        passwort_hash=generate_password_hash('secret12345'),
        rolle='owner',
        aktiv=True,
        email_confirmed=True,
    )
    db.add(user)
    db.commit()
    tracker[Organisation].append(org.id)
    tracker[User].append(user.id)
    return org.id, user.id


def _login(client, org_id, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['org_id'] = org_id


def test_postcall_trend_route_existiert_nicht_mehr(client, cleanup_tracker):
    """Der Vergleichs-Streifen des Anruf-Fensters hat keine Route mehr (D-14).

    Ein authentifizierter GET auf '/api/postcall/trend?n=5' liefert 404.

    Gepaarter Existenz-Anker in derselben Funktion: die Nachbar-Route '/api/keepalive'
    antwortet weiterhin mit 200. Sie ist POST-only (routes/app_routes.py) — der Plan
    nennt hier einen GET, das waere gegen diese Route ein 405 und damit ein falscher
    Sollwert; belegt wird dieselbe Sache mit der Methode, die die Route wirklich fuehrt.
    """
    org_id, user_id = _make_user(client, cleanup_tracker)
    _login(client, org_id, user_id)

    lebt = client.post('/api/keepalive')
    assert lebt.status_code == 200, (
        'Existenz-Anker gerissen: die Nachbar-Route antwortet nicht mit 200 — '
        f'Status {lebt.status_code}. Ein 404 unten waere dann kein Loesch-Beweis, '
        'sondern nur ein kaputter oder nicht eingeloggter Test-Client.'
    )

    weg = client.get('/api/postcall/trend?n=5', follow_redirects=False)
    assert weg.status_code == 404, (
        'Die Trend-Route des Anruf-Fensters antwortet noch — Status '
        f'{weg.status_code}. Sie speiste den Vergleichs-Streifen nach dem Auflegen und '
        'ist mit METRIK-1 ersatzlos entfallen.'
    )


def test_calc_call_score_ist_weg(client, cleanup_tracker):
    """Die Vierer-Formel haengt nicht mehr am Routen-Modul (D-13).

    ⚠ Begruendung fuer hasattr (einziger zulaessiger Einsatz in dieser Datei): geprueft
    wird die LAUFZEIT-Schnittstelle des importierten Moduls — welche Namen nach dem
    Import wirklich aufrufbar sind — NICHT das Vorhandensein von Quelltext. Ein
    getilgter Name kann nicht mehr versehentlich verdrahtet werden.

    Gepaarter Existenz-Anker in derselben Funktion: '_calc_process_score' lebt. Er ist
    der ERZEUGER von calls.coaching_score/score_breakdown und bleibt bewusst stehen —
    und er belegt zugleich, dass ueberhaupt ein Modul geladen wurde.
    """
    from routes import app_routes

    assert hasattr(app_routes, '_calc_process_score'), (
        'Existenz-Anker gerissen: der ERZEUGER fehlt im geladenen Modul. Dann sagt die '
        'Abwesenheit unten nichts — womoeglich wurde gar nichts geladen.'
    )
    assert not hasattr(app_routes, '_calc_call_score'), (
        'Die Vierer-Formel _calc_call_score haengt noch am Modul. Sie gewichtete den '
        'Redeanteil, der im Kaltakquise-Modus baubedingt konstant ist — sie misst nichts '
        'und ist mit METRIK-1 geloescht.'
    )


# ── Pflicht-Nachtrag 17.08. (Plan 08, Task 2b) ────────────────────────────────────────────
#
# ⚠ WARUM DIESER TEST DIE AUSGELIEFERTE DATEI LIEST UND NICHT DEN BROWSER FAEHRT —
#   ausdrueckliche Begruendung fuer den Grenzfall der Test-Qualitaets-Regel (CLAUDE.md):
#
#   Der Fehler sitzt in static/pip-launcher.js: reines Browser-JS in einer IIFE, die nach
#   aussen nur { open, close, isActive } gibt. Weder der Aufraeumer noch der Weg "Naechster
#   Call" sind aufrufbar, ohne eine JS-Laufzeit zu starten. Auf dem Ausroll-Server gibt es
#   keine:
#       $ ssh ... 'which node; node --version'
#       bash: line 1: node: command not found
#   und lokal etwas auszufuehren ist HART verboten ("Kein Local-Dev"). Ein Funktions-Aufruf
#   ist hier also nicht bloss unbequem, sondern im Test-Tor nicht herstellbar.
#
#   Deshalb prueft der Test NICHT, ob irgendwo eine Zeichenkette vorkommt, sondern den
#   KONTROLLFLUSS-VERTRAG an den per Klammer-Zaehlung ausgeschnittenen Funktionsrumpfen:
#   ruft der Weg "Naechster Call" den EINEN Aufraeumer, raeumt dieser Aufraeumer den
#   gemerkten Ausgang mit weg, und hat der gemerkte Ausgang danach ueberhaupt noch einen
#   Leser. Genau daran ist der Bestandsfehler entstanden: der Aufraeumer existierte, wurde
#   aber nur auf zwei von drei Wegen gerufen.
#
#   ⛔ Die Kommentare in pip-launcher.js duerfen die geprueften Code-Formen NICHT im
#   Wortlaut zitieren (Selbstbezug-Falle, Bau-Regel 20) — der Leser-Anker unten wuerde sonst
#   an der eigenen Erklaerung haengenbleiben. Der Test ignoriert `//`-Zeilen zusaetzlich.

_PIP_JS_PFAD = os.path.join(os.path.dirname(__file__), '..', 'static', 'pip-launcher.js')


def _js_quelle():
    with open(_PIP_JS_PFAD, encoding='utf-8') as f:
        return f.read()


def _funktionsrumpf(src, kopf):
    """Schneidet den Rumpf der JS-Funktion `kopf` per Klammer-Zaehlung heraus.

    Ein Zeilen-grep kann nicht sagen, IN WELCHER Funktion eine Zeile steht — genau das ist
    hier die Frage. Deshalb Klammer-Zaehlung statt Zeilen-Suche.
    """
    start = src.find(kopf)
    assert start >= 0, (
        f'Anker-Fehlmessung: {kopf!r} steht nicht mehr in pip-launcher.js. Dann sagt jede '
        'weitere Zusicherung unten nichts — erst die Funktion wiederfinden.'
    )
    auf = src.find('{', start)
    assert auf >= 0, f'{kopf!r} gefunden, aber keine oeffnende Klammer dahinter.'
    tiefe = 0
    for i in range(auf, len(src)):
        z = src[i]
        if z == '{':
            tiefe += 1
        elif z == '}':
            tiefe -= 1
            if tiefe == 0:
                return src[start:i + 1]
    raise AssertionError(f'Rumpf von {kopf!r} nicht geschlossen — Datei unvollstaendig?')


def test_naechster_call_raeumt_den_vorigen_anruf_weg():
    """Nach "Naechster Call" darf kein Wert des vorigen Anrufs stehenbleiben (Nachtrag 17.08.).

    Belegt am 17.08. an vier echten Anrufen: vier Dauern, eine Anzeige — und beim vierten
    Anruf stand ein Ausgang auf dem Schirm, den die Datenbank gar nicht hatte.
    """
    src = _js_quelle()
    rumpf_reset = _funktionsrumpf(src, 'function _resetLiveState(')
    rumpf_next = _funktionsrumpf(src, 'function nextCall(')

    # ── Gepaarte Existenz-Anker: ohne sie waere jedes Fehlen unten nicht von "falsch
    #    ausgeschnitten" oder "Datei umgebaut" zu unterscheiden.
    assert src.count('state.pendingPostcall = null') == 1, (
        'Existenz-Anker gerissen: der Nach-Anruf-Zustand wird an '
        f'{src.count("state.pendingPostcall = null")} Stellen genullt statt an genau einer. '
        'Es gibt dann mehr als einen Aufraeum-Pfad — und die laufen erfahrungsgemaess '
        'auseinander.'
    )
    assert 'state.pendingPostcall = null' in rumpf_reset, (
        'Existenz-Anker gerissen: die eine Nullung sitzt nicht im ausgeschnittenen '
        'Aufraeumer — der Schnitt oben trifft die falsche Funktion.'
    )
    assert 'json.outcome' in src, (
        'Existenz-Anker gerissen: der vom Server gelieferte Ausgang wird nirgends mehr '
        'gelesen. Dann ist nicht der Rueckfall weg, sondern die Anzeige.'
    )

    # ── ① Der Weg "Naechster Call" ruft den bestehenden Aufraeumer.
    assert '_resetLiveState()' in rumpf_next, (
        'Der Weg "Naechster Call" raeumt den Nach-Anruf-Zustand nicht weg: er ruft den '
        'Aufraeumer nicht. Mikrofon, Verbindung und Timer werden geraeumt, der Zustand des '
        'vorigen Anrufs bleibt stehen und erscheint im naechsten Anruf-Fenster.'
    )

    # ── ② Kein zweiter Aufraeum-Pfad: der Weg nullt nicht selbst, er fragt den Besitzer.
    for feld in ('pendingPostcall', 'lastCallId', 'lastOutcome'):
        assert feld not in rumpf_next, (
            f'"Naechster Call" nullt {feld} selbst. Damit gibt es einen zweiten '
            'Aufraeum-Pfad neben dem Aufraeumer — genau die Bauform, die diesen Fehler '
            'erzeugt hat. Der Aufruf reicht.'
        )

    # ── ③ Der gemerkte Ausgang wird im selben Aufraeumer mitgenullt.
    assert 'state.lastOutcome = null' in rumpf_reset, (
        'Der gemerkte Ausgang des vorigen Anrufs wird im Aufraeumer nicht genullt. Er lebt '
        'dann ueber den Anruf hinaus weiter.'
    )

    # ── ④ Und er hat danach keinen Leser mehr: kein Rueckfall auf den vorigen Ausgang.
    leser = [
        zeile.strip()
        for zeile in src.splitlines()
        if 'state.lastOutcome' in zeile
        and not zeile.strip().startswith('//')
        and not re.search(r'state\.lastOutcome\s*=', zeile)
    ]
    assert leser == [], (
        'Der gemerkte Ausgang des VORIGEN Anrufs wird noch gelesen: '
        f'{leser}. Fehlt der Ausgang des aktuellen Anrufs, erscheint damit der alte — '
        'ein falscher Ausgang ist schlimmer als keiner.'
    )
