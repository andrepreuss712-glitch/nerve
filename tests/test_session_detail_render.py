"""Fehler-500 Auswertungs-Seite (session_detail) — ERST-ROT gegen HEAD 7d90ca4.

Nagelt fest, dass `/session/<sid>` mit einer live-`rubric_score`-Zeile **rendert** (HTTP 200) und
die Beobachtungen sichtbar sind — und dass der Leer-Fall den Satz „Nicht genug zum Bewerten."
zeigt statt zu brechen.

WARUM DAS GEGEN HEAD ROT IST (die Falle):
`routes/dashboard.py` baut `observations_display = [{'name':…, 'items':[…]}]`. In Jinja2 loest
`dim.items` NICHT auf den Dict-Key auf, sondern auf die **Methode** `dict.items` — Jinja probiert
bei Punkt-Zugriff zuerst das Attribut. Folge in `templates/session_detail.html`:
  * `selectattr('items')`  -> die Methode ist immer truthy -> der Leer-Zweig ist TOT
  * `{% if dim.items %}`   -> immer truthy -> der „keine Beobachtung"-Zweig ist TOT
  * `{% for obs in dim.items %}` -> TypeError: 'builtin_function_or_method' object is not iterable
    -> HTTP 500
Latent seit 4354957 (2026-06-28); scharf geworden, seit nach dem Lock-Fix wieder rubric_score-Zeilen
entstehen. **Beide Tests unten laufen gegen HEAD in denselben 500** (auch der Leer-Fall, weil der
tote selectattr-Zweig in die Schleife faellt).

CLAUDE.md-konform: reine Runtime-Assertions (HTTP-Status + gerendertes HTML). KEIN
`inspect.getsource`, kein String-in-Source, kein `open(datei).read()` — der Test wuerde sonst gruen
bleiben, waehrend die Seite bricht (das ist genau der Fehler, den er fangen soll).

Cleanup (CLAUDE.md Test-Cleanup-Regel): committende Rows werden reverse-FK weggeraeumt.
`rubric_score` haengt per FK ON DELETE CASCADE an `calls` und faellt mit dem Call.
Verify NUR via deploy.sh-Gate / Server-Lauf — kein Local-Dev.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from tests.conftest import cleanup_rows
from database.models import (
    User, ConversationLog, Call, RubricScore,
)
from services.judge_dimensions import DIMENSIONS


BEOBACHTUNG = 'Der Bedarf wurde sauber ausgelesen, bevor das Angebot kam.'
BELEG_ZITAT = 'Was genau bremst Sie im Moment am meisten?'
LEER_SATZ = 'Nicht genug zum Bewerten.'


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def tracker(db_from_client):
    """Reverse-FK-Teardown. ZWEI cleanup_rows-Aufrufe, weil `calls` KIND von `conversation_logs`
    ist (conversation_log_id-FK), die globale _CLEANUP_FK_ORDER aber conversation_logs VOR calls
    listet — dieselbe Reihenfolge-Falle wie in test_dashboard_outcome_reminder.py."""
    ids = {'calls': [], 'logs': [], 'users': []}
    yield ids
    if ids['calls']:
        cleanup_rows(db_from_client, {Call: ids['calls']})
    rest = {}
    if ids['logs']:
        rest[ConversationLog] = ids['logs']
    if ids['users']:
        rest[User] = ids['users']
    if rest:
        cleanup_rows(db_from_client, rest)


def _seed_session(db, tracker, observations, outcome='meeting_booked'):
    """Legt Nutzer + ConversationLog + Call + live-rubric_score an und gibt (user, sid) zurueck.

    `outcome` ist seit METRIK-1 D-20 ein **Test-Parameter**: `None` bildet einen Anruf ohne
    bestaetigtes Gespraechsergebnis ab. Frueher war der Wert fest verdrahtet, weil eine
    Anzeige-Sperre sonst jeden Zweig verstellt haette — die Sperre ist ersatzlos entfallen.

    Der Nutzer wird in die **Seed-Org der client-Fixture** gelegt: `rubric_score` hat FORCE RLS,
    und der Request-Pfad setzt die Tenant-GUC aus der Org des eingeloggten Nutzers. Eine eigene Org
    haette einen anderen tenant_id -> die Zeile waere fuer den Request unsichtbar und der Test
    waere aus dem falschen Grund gruen/rot.
    """
    from tests import conftest as _cf
    tenant_id = _cf.TEST_TENANT_UUID
    org_id = db.execute(
        text("SELECT legacy_org_id FROM tenant_orgs WHERE id = :t"), {"t": tenant_id}
    ).scalar()
    assert org_id is not None, 'Seed-Tenant der client-Fixture nicht aufloesbar'

    u = User(email=f'sd_render_{uuid.uuid4().hex[:8]}@nerve.local',
             passwort_hash=generate_password_hash('pw'),
             rolle='owner', org_id=org_id, aktiv=True, onboarding_done=True)
    db.add(u)
    db.flush()
    tracker['users'].append(u.id)

    conv = ConversationLog(user_id=u.id, org_id=org_id, typ='live', started_at=_now())
    db.add(conv)
    db.flush()
    tracker['logs'].append(conv.id)

    call_id = str(uuid.uuid4())
    db.add(Call(
        id=call_id,
        user_id=u.id,
        tenant_id=tenant_id,
        call_mode='cold_call',
        started_at=_now(),
        ended_at=_now(),
        transcript_storage='none',
        # METRIK-1 D-20: Der Vorgabewert bildet den BESTAETIGTEN Fall ab — NICHT mehr, weil eine
        # Anzeige-Sperre sonst den Zweig verstellen wuerde. Die Sperre ist ersatzlos entfallen;
        # der unbestaetigte Fall (outcome=None) hat einen eigenen Test.
        outcome=outcome,
        conversation_log_id=conv.id,
    ))
    tracker['calls'].append(call_id)

    db.add(RubricScore(
        id=uuid.uuid4(),
        call_id=call_id,
        conversation_log_id=conv.id,
        session_mode='cold_call',
        origin='live',          # das Preview liest NUR origin='live'
        status='scored',        # weder judge_failed noch not_gradable -> Zweig (e)
        tenant_id=tenant_id,
        observations_jsonb=observations,
    ))
    db.commit()
    return u, conv.id, tenant_id


def _login(client, u, tenant_id):
    """Login MIT `tenant_id` in der Flask-Session.

    PFLICHT, nicht Kosmetik: `app.py:2292` liest die Mandanten-UUID aus der Flask-Session
    (`_g2.tenant_id = _sess.get('tenant_id')`) und schiebt sie ueber den after_begin-Hook als
    GUC `app.tenant_id` in jede Transaktion. Ohne diesen Eintrag ist die GUC leer, und
    `rubric_score` (FORCE RLS) liefert **0 Zeilen** — der Route-Pfad landet dann im Zweig
    „(d) row-absent" und erreicht die Beobachtungs-Schleife nie. Der Test waere rot, aber aus
    dem FALSCHEN Grund (gemessen 2026-08-01: genau diese Falle, siehe Memory
    „RLS inspect false-negative")."""
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
        s['tenant_id'] = str(tenant_id)


def test_session_detail_rendert_mit_beobachtungen(client, db_from_client, tracker):
    """Mit echten Beobachtungen: HTTP 200 und der Beobachtungstext steht im HTML.

    Gegen HEAD: 500 (TypeError in `{% for obs in dim.items %}`)."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    })
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, (
        f'Auswertungs-Seite antwortet {r.status_code} statt 200 — die Beobachtungs-Schleife '
        f'bricht (dim.items loest auf die Dict-METHODE auf, nicht auf den Key).'
    )
    html = r.get_data(as_text=True)
    assert BEOBACHTUNG in html, 'Die Beobachtung wird nicht angezeigt.'
    assert BELEG_ZITAT in html, 'Das Beleg-Zitat wird nicht angezeigt.'


def test_session_detail_leere_beobachtungen_zeigt_hinweis(client, db_from_client, tracker):
    """Ohne Beobachtungen: HTTP 200 und der Satz „Nicht genug zum Bewerten." steht im HTML.

    Gegen HEAD ebenfalls rot: `selectattr('items')` filtert nichts weg (die Methode ist immer
    truthy), also faellt der Leer-Fall in die Schleife statt in den Hinweis-Zweig."""
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {})
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, (
        f'Auswertungs-Seite antwortet {r.status_code} statt 200 — der Leer-Fall laeuft in die '
        f'Beobachtungs-Schleife, weil selectattr auf die Dict-Methode trifft.'
    )
    html = r.get_data(as_text=True)
    assert LEER_SATZ in html, (
        f'Der Hinweis {LEER_SATZ!r} fehlt — der Leer-Zweig ist tot, solange selectattr auf die '
        f'immer-truthy Dict-Methode trifft.'
    )


# ── METRIK-1 Plan 03 Task 1 (D-20): die Einschaetzung haengt NICHT mehr am Outcome-Klick ──
MARKIERUNG_UNBESTAETIGT = 'Gesprächsergebnis noch nicht bestätigt'
SPERR_SATZ_ALT = 'Gesprächsergebnis bestätigen, dann erscheint die Einschätzung.'


def test_einschaetzung_erscheint_ohne_bestaetigtes_ergebnis(client, db_from_client, tracker):
    """METRIK-1 Requirement 4 / D-20: die KI-Einschaetzung haengt NICHT mehr am Outcome-Klick.

    ROT-vor-GRUEN: Gegen den Stand VOR dieser Phase ist der Test rot — die Sperre (0) fing den
    Request ab und die Seite zeigte 'Gespraechsergebnis bestaetigen, dann erscheint die
    Einschaetzung.'. Ein sauberer Beleg ohne neue Mechanik: derselbe Seed, nur outcome=None.

    Der unbestaetigte Anruf wird dabei ehrlich MARKIERT statt versteckt — beides wird geprueft,
    sonst waere 'Sperre weg' von 'Markierung vergessen' nicht zu unterscheiden.
    """
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    }, outcome=None)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, (
        f'Auswertungs-Seite antwortet {r.status_code} statt 200 — der unbestaetigte Anruf '
        f'bricht die Seite.'
    )
    html = r.get_data(as_text=True)

    # Gepaarter Existenz-Anker: "Sperr-Satz nicht gefunden" darf nicht von "Seite gar nicht
    # gerendert" kommen.
    assert MARKIERUNG_UNBESTAETIGT in html, (
        'Die ehrliche Markierung fehlt — ohne sie ist ein unbestaetigter Anruf von einem '
        'bestaetigten nicht zu unterscheiden.'
    )
    assert BELEG_ZITAT in html, (
        'Das Beleg-Zitat fehlt — die Einschaetzung haengt weiterhin am Bestaetigungs-Klick.'
    )
    assert SPERR_SATZ_ALT not in html, (
        'Der Sperr-Satz steht noch auf der Seite — die Anzeige-Sperre ist nicht entfallen.'
    )


def test_bestaetigter_anruf_traegt_die_markierung_nicht(client, db_from_client, tracker):
    """Gegenprobe zur Markierung: mit bestaetigtem Ergebnis erscheint sie NICHT.

    Ohne diesen Partner koennte die Markierung fest verdrahtet sein und der Test darueber
    waere trotzdem gruen — sie waere dann keine Aussage mehr, sondern Dekoration."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    })
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert BELEG_ZITAT in html, 'Die Seite wurde gar nicht bis zur Einschaetzung gerendert.'
    assert MARKIERUNG_UNBESTAETIGT not in html, (
        'Ein bestaetigter Anruf traegt die Unbestaetigt-Markierung — sie haengt nicht am '
        'Wahrheitswert calls.outcome.'
    )


# ── METRIK-1 Plan 01 Task 4: Compliance-Vorwurf nur MIT pruefbarem Beleg ──────────────────
# Andre-Entscheidung 14.08.: Ohne pruefbaren Beleg erscheint AUSSCHLIESSLICH der neutrale Satz —
# kein Verdikt, auch nicht abgeschwaecht. Das `verletzt`-Flag bleibt gesetzt (Sicherheits-Hard-Gate),
# es wird nur nicht mehr als Anschuldigung angezeigt.

NEUTRALER_SATZ = 'Dieses Gespräch wurde gemeldet und wird von einem NERVE-Mitarbeiter geprüft.'
VERDIKT_WORT = 'Belästigung'


def test_compliance_ohne_beleg_rendert_nur_den_neutralen_satz(client, db_from_client, tracker):
    """`verletzt=True` ohne Beleg-Zitat: nur der neutrale Satz, KEIN Vorwurf.

    Gegen den Stand vor Task 4 rot: dort haengt nur das Blockquote am Beleg, der Verdikt-Text
    erscheint auch ohne Zitat."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_compliance': {'verletzt': True, 'beleg_zitat': ''},
    })
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    html = r.get_data(as_text=True)

    # Gepaarter Existenz-Anker: "Vorwurf nicht gefunden" darf nicht von "Seite nicht gerendert" kommen.
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    assert 'KI-Einschätzung' in html, 'Die Seite wurde gar nicht bis zum Panel gerendert.'

    assert NEUTRALER_SATZ in html, 'Der neutrale Satz fehlt — das Versprechen wird nicht angezeigt.'
    assert VERDIKT_WORT not in html, (
        'Der harte Verdikt-Text erscheint ohne pruefbaren Beleg — genau das ist der Vorwurf, '
        'den die Entscheidung vom 14.08. entfernt.'
    )


def test_compliance_mit_beleg_zeigt_den_alarm_unveraendert(client, db_from_client, tracker):
    """Mit pruefbarem Beleg bleibt der Alarm-Kasten unveraendert — die Regel gegen ein Zuviel."""
    dim_key = DIMENSIONS[0]['key']
    comp_zitat = 'Nein danke, bitte rufen Sie hier nicht mehr an.'
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_compliance': {'verletzt': True, 'beleg_zitat': comp_zitat},
    })
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    html = r.get_data(as_text=True)

    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    assert VERDIKT_WORT in html, 'Der Verdikt-Text fehlt, obwohl ein pruefbarer Beleg vorliegt.'
    assert comp_zitat in html, 'Das geprüfte Compliance-Zitat wird nicht angezeigt.'
    assert NEUTRALER_SATZ not in html, (
        'Der neutrale Ersatz-Satz erscheint, obwohl ein Beleg vorliegt — der Zweig greift zu breit.'
    )


# ── Option 3, Haelfte 1: Form-Garantie an der Quelle ──────────────────────────────────────
def test_session_detail_haelt_kaputte_jsonb_form_aus(client, db_from_client, tracker):
    """`observations_jsonb` ist JSONB — die Form ist in der DB NIRGENDS erzwungen.

    Steht unter einem Dimensions-Schluessel etwas anderes als eine Liste von Dicts (hier: ein
    String, eine Zahl, ein dict, ein None-Eintrag), darf die Seite nicht brechen. Ohne die
    Form-Garantie in routes/dashboard.py liefe `{% for obs in dim.eintraege %}` ueber die
    Zeichen eines Strings und `obs.get(...)` waere der naechste 500."""
    keys = [d['key'] for d in DIMENSIONS]
    kaputt = {
        keys[0]: 'kein-list-sondern-string',
        keys[1]: 42,
        keys[2]: {'kein': 'list'},
        keys[3]: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}, None, 'muell'],
    }
    u, sid, tenant_id = _seed_session(db_from_client, tracker, kaputt)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, (
        f'Kaputte JSONB-Form bricht die Seite ({r.status_code}) — die Form-Garantie greift nicht.'
    )
    html = r.get_data(as_text=True)
    # Der EINE gueltige Eintrag ueberlebt, der Muell drumherum wird verworfen.
    assert BEOBACHTUNG in html, 'Der gueltige Eintrag wurde mit dem Muell zusammen verworfen.'
    assert 'kein-list-sondern-string' not in html, 'Ein String wurde als Eintragsliste durchgereicht.'


# ── Option 3, Haelfte 2: das Netz um den Render ───────────────────────────────────────────
def test_session_detail_netz_faengt_render_fehler(client, db_from_client, tracker, monkeypatch):
    """Bricht das Rendern WEGEN der Vorschau-Daten, kommt die Seite degradiert statt als 500.

    Beweist das Netz selbst, nicht nur seine Existenz: `render_template` wird so ersetzt, dass
    es beim ERSTEN Aufruf (mit Vorschau-Daten) wirft und beim zweiten (ohne) durchlaeuft — genau
    der Fall, fuer den das Netz gebaut ist. Ohne Netz waere das ein HTTP 500."""
    import routes.dashboard as _dash

    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    })
    _login(client, u, tenant_id)

    _echt = _dash.render_template
    aufrufe = {'n': 0}

    def _wackelig(template_name, **kw):
        # Nur der Render MIT Vorschau-Daten faellt — der Fallback (leere Liste) laeuft durch.
        if template_name == 'session_detail.html' and kw.get('observations_display'):
            aufrufe['n'] += 1
            raise RuntimeError('simulierter Render-Fehler im Vorschau-Panel')
        return _echt(template_name, **kw)

    monkeypatch.setattr(_dash, 'render_template', _wackelig)

    r = client.get(f'/session/{sid}')
    assert aufrufe['n'] == 1, 'Der Erst-Render wurde nicht wie erwartet zum Scheitern gebracht.'
    assert r.status_code == 200, (
        f'Das Netz faengt den Render-Fehler nicht ({r.status_code}) — die Zusage '
        f'"darf session_detail NIE brechen" waere weiter unwahr.'
    )
    html = r.get_data(as_text=True)
    # Die Seite kommt — ohne das Vorschau-Panel, aber vollstaendig im Rest.
    assert BEOBACHTUNG not in html, 'Der Fallback zeigt die Vorschau-Daten, die gerade gerissen sind.'
    assert 'session-detail' in html or '</html>' in html, 'Der Fallback lieferte keine vollstaendige Seite.'
