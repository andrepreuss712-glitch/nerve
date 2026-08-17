"""METRIK-1 Plan 08 (D-13/D-14): Das Anruf-Fenster benotet nicht mehr.

Serverseitig pruefbar, KEIN Browser noetig — das Test-Tor hat keinen.
Beide Tests belegen Laufzeit-Verhalten (Request gegen die echte PG nerve_test bzw. die
Laufzeit-Schnittstelle des Routen-Moduls), kein Quelltext-Vorhandensein.

★ ERST-ROT: Beide Tests MUESSEN gegen den Stand vor Task 2 ROT sein — die Trend-Route
antwortet dort noch, und die Vierer-Formel haengt noch am Modul.

Jeder Test traegt einen gepaarten Existenz-Anker in DERSELBEN Funktion. Ohne ihn waere
"404" nicht von "Test-Client kaputt / nicht eingeloggt" und "Attribut fehlt" nicht von
"Modul gar nicht geladen" zu unterscheiden (Bau-Regel 20).

Alle committeten Rows werden im POST-yield-Teardown via cleanup_rows weggeraeumt
(Test-Cleanup-Regel, public.* ohne Tenant-GUC). Emails sind uuid-suffixed gegen die
UNIQUE-Constraint auf users.email.
"""

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
