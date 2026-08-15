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
    User, ConversationLog, Call, RubricScore, ObjectionEvent,
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
    ids = {'calls': [], 'logs': [], 'users': [], 'events': []}
    yield ids
    if ids['calls']:
        cleanup_rows(db_from_client, {Call: ids['calls']})
    rest = {}
    if ids['events']:
        rest[ObjectionEvent] = ids['events']
    if ids['logs']:
        rest[ConversationLog] = ids['logs']
    if ids['users']:
        rest[User] = ids['users']
    if rest:
        cleanup_rows(db_from_client, rest)


def _seed_session(db, tracker, observations, outcome='meeting_booked',
                  status='scored', payload=None, typ='live', kb_end=None,
                  redeanteil_avg=None, skript_abdeckung=None):
    """Legt Nutzer + ConversationLog + Call + live-rubric_score an und gibt (user, sid) zurueck.

    `outcome` ist seit METRIK-1 D-20 ein **Test-Parameter**: `None` bildet einen Anruf ohne
    bestaetigtes Gespraechsergebnis ab. Frueher war der Wert fest verdrahtet, weil eine
    Anzeige-Sperre sonst jeden Zweig verstellt haette — die Sperre ist ersatzlos entfallen.

    `typ` ist seit METRIK-1 D-17 ein **Test-Parameter**: die Auswertungsseite entscheidet ab
    Plan 06 anhand von `conversation_logs.typ`, ob eine Gesamtnote ueberhaupt angebracht ist.
    Ohne einen echten `typ='training'`-Seed waere „die Trainings-Note lebt noch" eine
    Behauptung statt eines Belegs (Gap C).

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

    conv = ConversationLog(user_id=u.id, org_id=org_id, typ=typ, started_at=_now(),
                           kb_end=kb_end, redeanteil_avg=redeanteil_avg,
                           skript_abdeckung=skript_abdeckung)
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
        # Vorgabe 'scored': weder judge_failed noch not_gradable -> Zweig (e).
        # METRIK-1 Plan 03 Task 2: 'not_gradable' + payload erreichen die _reason-Weiche (b).
        status=status,
        tenant_id=tenant_id,
        observations_jsonb=observations,
        payload_jsonb=(payload if payload is not None else {}),
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


# ── METRIK-1 Plan 03 Task 2: dritter Ablehnungs-Zweig, der alte Zweig bleibt ──────────────
SATZ_ZU_WENIG_GESPROCHEN = 'In diesem Gespräch wurde zu wenig gesprochen'
SATZ_ALT_GRUND = 'Zu wenig auswertbare Momente'
SATZ_AUDIO = 'Audio zu schlecht'


def test_ablehnungsgrund_zu_wenig_gesprochen_zeigt_eigenen_text(client, db_from_client, tracker):
    """Der neue Grund des Sprech-Substanz-Tors bekommt seine eigene, wahre Erklaerung.

    ROT-vor-GRUEN: ohne den dritten Zweig faellt `too_little_speech` in den Sonst-Zweig und
    der Anruf bekommt „Audio zu schlecht" — eine Aussage ueber die Tonqualitaet, die hier
    nachweislich falsch ist.

    Die DREI Redeabschnitte im Seed sind Absicht: die Abschnitts-Bedingung ist seit dem 14.08.
    gestrichen, abgewiesen wurde allein wegen der 12 Woerter. Der Anzeige-Zweig liest
    ausschliesslich `reason` und ist von den Messwerten unabhaengig."""
    u, sid, tenant_id = _seed_session(
        db_from_client, tracker, {},
        status='not_gradable',
        payload={'reason': 'too_little_speech', 'berater_woerter': 12, 'redeabschnitte': 3,
                 'sprechzeit_ms': 4100, 'high_conf_events': 0, 'tor_zweig': 'zu_wenig_woerter'},
    )
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert SATZ_ZU_WENIG_GESPROCHEN in html, (
        'Der neue Ablehnungs-Grund hat keinen eigenen Text — der Anruf bekommt eine fremde '
        'Erklaerung.'
    )
    assert SATZ_AUDIO not in html, (
        'Der Anruf bekommt „Audio zu schlecht" — eine Aussage ueber die Tonqualitaet, die hier '
        'falsch ist.'
    )


def test_alter_ablehnungsgrund_bleibt_erhalten(client, db_from_client, tracker):
    """REGRESSIONS-Test gegen das versehentliche Aufraeumen des Alt-Zweigs.

    `too_few_high_confidence_events` wird seit METRIK-1 nicht mehr geschrieben — Alt-Zeilen mit
    diesem Grund stehen aber in der Datenbank. Wer den Zweig entfernt, gibt genau diesen Anrufen
    die falsche Erklaerung."""
    u, sid, tenant_id = _seed_session(
        db_from_client, tracker, {},
        status='not_gradable',
        payload={'reason': 'too_few_high_confidence_events'},
    )
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert SATZ_ALT_GRUND in html, (
        'Der Alt-Zweig ist weg — Anrufe mit dem alten Grund bekommen jetzt eine falsche '
        'Erklaerung.'
    )


def test_unbekannter_ablehnungsgrund_faellt_auf_audio_zurueck(client, db_from_client, tracker):
    """Der Sonst-Zweig bleibt unveraendert der Auffang fuer alles Uebrige."""
    u, sid, tenant_id = _seed_session(
        db_from_client, tracker, {},
        status='not_gradable',
        payload={'reason': 'poor_audio_health'},
    )
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert SATZ_AUDIO in html, 'Der Sonst-Zweig faengt den Audio-Grund nicht mehr.'


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


# ── METRIK-1 Plan 06 (D-14/D-15/D-16/D-17/D-19): die alte Note verlaesst die Live-Seite ───
#
# WARUM: Die Gesamtnote mass im echten Anruf zu 40 % die Kaufbereitschaft des KUNDEN — etwas,
# das der Verkaeufer nicht steuert — und zu 20 % einen Redeanteil, der im Kaltakquise-Modus
# baubedingt 100 % ist (der Term war dort IMMER 0). Im Training gibt es keinen Kunden mit Laune,
# sondern ein festes Szenario mit einer richtigen Antwort: dort misst eine Note tatsaechlich
# den Verkaeufer — und bleibt deshalb.
HERO_LABEL = 'Gesamt-Score'
HERO_KLASSE = 'n-session-detail-hero'
KOPF_ZEILE = 'Result:'
TREND_ABZEICHEN = 'vs Schnitt letzte 5'
VIERER_AUFRISS = 'n-session-detail-breakdown'
# ⚠ FEHLMESSUNG VERMIEDEN: Der Plan nennt als Anker das nackte Wort „Redeanteil" — und ein
# Lauf am 2026-08-15 hat belegt, dass es AUCH ausserhalb des Aufrisses auf derselben Seite
# steht: `_derive_practice_recommendations` (Regel 3) erzeugt bei Sessions MIT
# Speaker-Trennung eine Uebungs-Empfehlung zum Redeanteil. Die ist kein Ueberbleibsel des
# Aufrisses, sondern ein eigener, gewollter Coaching-Hinweis. Der Anker zeigt deshalb auf die
# CODE-FORM der Aufriss-Zeile (ihr title-Tooltip), nicht auf ein Wort der Prosa.
REDEANTEIL_ZEILE = 'Gewichtung 20% im Gesamt-Score'


def _seed_weitere_logs(db, tracker, user_id, org_id, typ, kb_end, anzahl):
    """Legt `anzahl` weitere ConversationLogs desselben Nutzers an (fuer den Trend-Schnitt).

    Der Trend-Block in routes/dashboard.py zog den Schnitt ueber die letzten fuenf Sitzungen
    desselben `typ`. Ohne echte Nachbar-Zeilen bliebe `trend_avg` None und der Test waere
    gruen, ohne das Abzeichen je gesehen zu haben — ein stiller Fehlbeleg."""
    for _ in range(anzahl):
        c = ConversationLog(user_id=user_id, org_id=org_id, typ=typ,
                            started_at=_now(), kb_end=kb_end)
        db.add(c)
        db.flush()
        tracker['logs'].append(c.id)
    db.commit()


def test_live_zeigt_keine_gesamtnote(client, db_from_client, tracker):
    """D-15/D-19: Ein LIVE-Anruf zeigt auf der Auswertungsseite keine Zahl mehr, die wie eine
    Note aussieht — nicht im Hero, nicht als Trend-Abzeichen, nicht im Kopfbereich.

    ROT-vor-GRUEN: gegen den Stand vor Plan 06 rendert der Hero fuer BEIDE Typen und der
    Kopfbereich traegt `Result: <kb_end>/100`.

    Gepaarte Existenz-Anker in derselben Funktion (HTTP 200 + die KI-Karte): sonst waere
    „nichts gefunden" nicht von „Seite gar nicht gerendert" zu unterscheiden."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    }, typ='live', kb_end=64)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    # Existenz-Anker zuerst — er beweist, dass ueberhaupt gelesen wurde.
    assert 'KI-Einschätzung' in html, 'Die Seite wurde gar nicht bis zur Einschaetzung gerendert.'

    assert HERO_LABEL not in html, (
        'Der Live-Anruf zeigt weiterhin einen Gesamt-Score — genau die Zahl, die zu 40 % die '
        'Kaufbereitschaft des Kunden mass.'
    )
    assert HERO_KLASSE not in html, 'Der Score-Hero wird fuer einen Live-Anruf noch gerendert.'
    assert KOPF_ZEILE not in html, (
        'Der Kopfbereich zeigt weiterhin "Result: X/100" — bei LIVE ist das die Kaufbereitschaft '
        'des Kunden, beschriftet wie eine Note des Verkaeufers.'
    )
    assert TREND_ABZEICHEN not in html, 'Das Trend-Abzeichen ist nicht ersatzlos entfallen.'


def test_training_behaelt_seine_note(client, db_from_client, tracker):
    """⚠ DER GAP-C-TEST (D-17). Eine TRAINING-Sitzung zeigt ihre Note unveraendert.

    Der Score-Hero hatte bis Plan 06 KEINE typ-Weiche — wer ihn blind entfernt, laesst die
    Trainings-Note still sterben. Dieser Test ist absichtlich schon VOR dem Umbau gruen: sein
    Zweck ist nicht der Neubau, sondern die Regel gegen ein Zuviel. Er muss rot werden, sobald
    jemand die Note auch dem Training wegnimmt."""
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {},
                                      typ='training', kb_end=78)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert HERO_LABEL in html, (
        'Die Trainings-Note ist still gestorben — im Training gibt es keinen Kunden mit Laune, '
        'sondern ein festes Szenario mit einer richtigen Antwort. Dort misst die Note wirklich '
        'den Verkaeufer.'
    )
    assert HERO_KLASSE in html, 'Der Score-Hero fehlt der Trainings-Sitzung komplett.'
    assert '>78</div>' in html, (
        'Der Zahlenwert der Trainings-Note steht nicht im HTML — der Hero rendert leer.'
    )


def test_kein_vierer_aufriss_mehr(client, db_from_client, tracker):
    """D-16: Der Vierer-Aufriss faellt GANZ — auch der Live-Zweig.

    „Gewichtungen raus, Zahlen bleiben" ist ausdruecklich verworfen: das haette die
    Redeanteil-Zeile stehengelassen, die im Kaltakquise-Modus baubedingt immer 100 % zeigt.

    Gepaarter Existenz-Anker: die Kopfbereichs-Zeile `Dauer:` steht weiter im HTML."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    }, typ='live', kb_end=64, redeanteil_avg=100, skript_abdeckung=42)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert 'Dauer:' in html, 'Der Kopfbereich fehlt — die Seite wurde gar nicht gerendert.'
    assert VIERER_AUFRISS not in html, 'Der Vierer-Aufriss steht noch auf der Seite.'
    assert REDEANTEIL_ZEILE not in html, (
        'Die Redeanteil-Zeile des Aufrisses lebt weiter — im Kaltakquise-Modus zeigt sie '
        'baubedingt immer 100 %, ihr Beitrag zur alten Note war dort immer 0.'
    )
    # Gegenprobe zur Praezisierung oben: die Gewichtungs-Tooltips der vier Aufriss-Zeilen sind
    # ALLE weg — nicht nur der eine, auf den der Anker zeigt.
    for _gewicht in ('Gewichtung 40%', 'Gewichtung 30%', 'Gewichtung 10%'):
        assert _gewicht not in html, f'Aufriss-Zeile mit {_gewicht} steht noch auf der Seite.'


def test_kein_trend_abzeichen_bei_training(client, db_from_client, tracker):
    """D-14 gilt AUCH fuer Training: der Trend-Streifen ist ersatzlos entfallen.

    ROT-vor-GRUEN: mit fuenf aelteren Trainings-Sitzungen (kb_end=50) und einer aktuellen mit
    78 rechnete der Trend-Block einen Schnitt und rendert „+28 vs Schnitt letzte 5".

    Gepaarter Existenz-Anker: `Gesamt-Score` steht weiterhin da — sonst waere „Abzeichen weg"
    von „Hero mitsamt Note weg" nicht zu unterscheiden."""
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {},
                                      typ='training', kb_end=78)
    _seed_weitere_logs(db_from_client, tracker, u.id, u.org_id, 'training', 50, 5)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert HERO_LABEL in html, 'Die Trainings-Note fehlt — der Existenz-Anker greift nicht.'
    assert TREND_ABZEICHEN not in html, (
        'Das Trend-Abzeichen erscheint im Training weiter. Eine neutrale Ersatz-Zahl ist '
        'verworfen; der Streifen kommt erst mit der Fokus-Serie zurueck.'
    )


# ── METRIK-1 Plan 06 Task 3 (D-12, Lesestelle 7): kein Trainings-Notenschnitt bei LIVE ────
TRAININGS_DURCHSCHNITT = 'Zuletzt im Training: Ø'
TRAININGS_ZAEHLUNG = 'Im Training:'


def test_kein_trainings_durchschnitt_auf_der_live_seite(client, db_from_client, tracker):
    """D-12/Lesestelle 7: „Zuletzt im Training: Ø 80/100 aus 3 Sessions" faellt.

    Der Wert war ein Mittelwert ueber `kb_end` von Trainings-Sitzungen — also wieder eine
    Gesamtnote, diesmal auf der Auswertungsseite eines LIVE-Anrufs.

    Der Seed ist absichtlich der Fall, der den alten Zweig AUSGELOEST haette: ein nicht
    behandelter Einwand im Live-Anruf plus drei Trainings-Sitzungen mit demselben Einwand-Typ
    und kb_end=80 (Bedingung war avg >= 70 UND sessions >= 3).

    Gepaarter Existenz-Anker: der Sonst-Zweig „Im Training: N Sessions" steht im HTML — sonst
    waere „Durchschnitt weg" von „Empfehlungs-Block gar nicht gerendert" nicht zu
    unterscheiden. Er war schon vorher gebaut; es musste nichts Neues entstehen."""
    einwand = 'zu_teuer'
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
    }, typ='live', kb_end=64)

    # Der nicht behandelte Einwand im Live-Anruf -> Empfehlung MIT cross_context.
    ev = ObjectionEvent(user_id=u.id, org_id=u.org_id, conversation_log_id=sid,
                        einwand_typ=einwand, success=False)
    db_from_client.add(ev)
    db_from_client.flush()
    tracker['events'].append(ev.id)

    # Drei Trainings-Sitzungen mit demselben Einwand-Typ und einer guten Note.
    for _ in range(3):
        t = ConversationLog(user_id=u.id, org_id=u.org_id, typ='training',
                            started_at=_now(), kb_end=80)
        db_from_client.add(t)
        db_from_client.flush()
        tracker['logs'].append(t.id)
        tev = ObjectionEvent(user_id=u.id, org_id=u.org_id, conversation_log_id=t.id,
                             einwand_typ=einwand, success=True)
        db_from_client.add(tev)
        db_from_client.flush()
        tracker['events'].append(tev.id)
    db_from_client.commit()

    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    # Reihenfolge mit Absicht: die ABWESENHEIT zuerst. Im ROT-Lauf ist dann die Fehlermeldung
    # eindeutig ("der Durchschnitt steht da") statt mehrdeutig ("der Sonst-Zweig fehlt" — was
    # vor dem Umbau auch heissen kann, dass korrekterweise der Durchschnitts-Zweig griff).
    assert TRAININGS_DURCHSCHNITT not in html, (
        'Die Live-Auswertungsseite zeigt weiterhin einen Trainings-Notendurchschnitt.'
    )
    assert TRAININGS_ZAEHLUNG in html, (
        'Der Empfehlungs-Block mit Trainings-Bezug wurde gar nicht gerendert — der Test kann '
        'ueber die Abwesenheit des Durchschnitts nichts aussagen.'
    )


# ── METRIK-1 Plan 07 (Requirement 5): Form 2 wird sichtbar ────────────────────────────────
#
# EINE belegte Kopfzeile ganz oben, GENAU EINE Sache fuers naechste Mal — und wenn kein
# Katalog-Kriterium verletzt ist, ein ehrliches „nichts". Die vollstaendigen Beobachtungen
# wandern hinter einen Aufklapper.
#
# D-10: Der „diesmal nichts"-Zweig ist der NORMALFALL, nicht die Ausnahme. Der Fokus-Katalog
# ist englisch, der gesamte gespeicherte Bestand deutsch — auf einem deutschen Anruf kann kein
# Kriterium ausloesen. Deshalb wird hier BEIDES festgenagelt: der Zweig mit einer Sache UND der
# ehrliche Leer-Zweig. Eine erfundene Sache oder eine leere Stelle waere der Fehler.
#
# ⚠ Die Konstanten unten tragen bewusst KEINE Anfuehrungszeichen, Apostrophe, `&`, `<` oder `>`:
# Jinja escapt per Voreinstellung (T-METRIK1-07-03 — genau so soll es sein), ein `"` im
# Erwartungswert wuerde im HTML als `&#34;` stehen und `html.count(...)` waere 0. Der Test
# haette dann eine Fehlmessung statt eines Befundes gemeldet.
KOPFZEILE_BEOBACHTUNG = 'Der beste Moment war die ruhige Rueckfrage nach dem ersten Nein.'
KOPFZEILE_ZITAT = 'Darf ich trotzdem eine einzige Frage stellen?'
FOKUS_SATZ = 'You said we provide four times - name the customer benefit instead.'
FOKUS_BELEG = 'we provide a full onboarding package'
NICHTS_SATZ = 'Nothing flagged this time.'
EINE_SACHE_TITEL = 'One thing for next time'
AUFKLAPPER_TITEL = 'Alle Beobachtungen'
AUFKLAPPER_FORM = '<details class="n-observation-dim">'
DAUER_MELDUNG = 'Einschätzung wird im Hintergrund ausgewertet'


def _kopfzeile(beobachtung=KOPFZEILE_BEOBACHTUNG, zitat=KOPFZEILE_ZITAT):
    """Der `_kopfzeile`-Unterstrich-Schluessel, wie ihn services/judge_runner.py schreibt."""
    return {'schema': 1, 'beobachtung': beobachtung, 'beleg_zitat': zitat}


def _fokus(focus_key='we_not_i', satz=FOKUS_SATZ, beleg=FOKUS_BELEG, count=4):
    """Der `_fokus`-Unterstrich-Schluessel, wie ihn services/slow_lane.py schreibt.

    `focus_key=None` + leerer Satz ist der EHRLICHE Leer-Fall (D-10) — er wird IMMER
    geschrieben, damit „kein Kriterium verletzt" von „nie befuellt" unterscheidbar bleibt."""
    return {'schema': 1, 'katalog_version': 1, 'focus_key': focus_key,
            'count': count, 'satz': satz, 'beleg': beleg}


def test_kopfzeile_wird_gezeigt(client, db_from_client, tracker):
    """Die belegte Kopfzeile steht mit ihrem woertlichen Zitat auf der Seite.

    ROT-vor-GRUEN: das Template liest `kopfzeile_display` vor Plan 07 nicht — der Kontext-Wert
    kommt seit Plan 05 an und wird schlicht verworfen.

    Gepaarter Existenz-Anker: die KI-Karte selbst steht im HTML, sonst waere „Kopfzeile fehlt"
    von „Seite gar nicht gerendert" nicht zu unterscheiden."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(),
    }, typ='live')
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert 'KI-Einschätzung' in html, 'Die Seite wurde gar nicht bis zur Einschaetzung gerendert.'
    assert KOPFZEILE_BEOBACHTUNG in html, (
        'Die Kopfzeile des Bewerters steht nicht auf der Seite — der Satz, der haengen bleiben '
        'soll, wird verworfen.'
    )
    assert KOPFZEILE_ZITAT in html, (
        'Das Beleg-Zitat der Kopfzeile fehlt — Lob ohne Beleg ist genau das, was das Produkt '
        'nicht geben darf.'
    )


def test_genau_eine_sache(client, db_from_client, tracker):
    """⚠ DER „GENAU EINE"-ANKER (T-METRIK1-07-04).

    Gezaehlt statt nur auf Vorhandensein geprueft: der Satz steht GENAU EINMAL im HTML. Ein
    Test auf `in html` waere auch dann gruen, wenn die eine Sache versehentlich zweimal
    gerendert wird — „genau EINE Sache" wuerde dann zu zweien, ohne dass es auffaellt.

    Und der Leer-Zweig darf NICHT zusaetzlich erscheinen: eine Sache UND „nichts diesmal"
    nebeneinander waere ein Widerspruch auf dem Bildschirm."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(),
    }, typ='live')
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert EINE_SACHE_TITEL in html, (
        'Die Ueberschrift der einen Sache fehlt — die Stelle existiert gar nicht.'
    )
    assert html.count(FOKUS_SATZ) == 1, (
        f'Die eine Sache steht {html.count(FOKUS_SATZ)}x im HTML statt genau einmal — aus '
        f'"genau EINE Sache" sind mehrere geworden.'
    )
    assert FOKUS_BELEG in html, 'Das woertliche Beleg-Zitat der einen Sache fehlt.'
    assert NICHTS_SATZ not in html, (
        'Der Leer-Zweig erscheint, obwohl eine Sache berechnet wurde — beides nebeneinander '
        'ist ein Widerspruch auf dem Bildschirm.'
    )


def test_diesmal_nichts_zweig(client, db_from_client, tracker):
    """D-10: kein Kriterium verletzt -> ein ehrliches „nichts", und die Kopfzeile bleibt.

    ⚠ BEIDE Assertions gehoeren in DIESELBE Funktion: der Nichts-Zweig darf die Kopfzeile nicht
    mitreissen. Die Kopfzeile kommt vom Modell, die eine Sache vom Code — sie haengen nicht
    aneinander, und genau das muss belegt sein.

    Auf deutschem Bestand ist das der NORMALFALL, nicht die Ausnahme: der Katalog ist englisch.
    Eine erfundene Sache oder eine leere Stelle waere hier der Fehler."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(focus_key=None, satz='', beleg='', count=0),
    }, typ='live')
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert NICHTS_SATZ in html, (
        'Der ehrliche Leer-Zweig fehlt — ohne ihn steht bei jedem deutschen Anruf eine leere '
        'Stelle, wo eine Aussage stehen muesste.'
    )
    assert KOPFZEILE_BEOBACHTUNG in html, (
        'Der Nichts-Zweig hat die Kopfzeile mitgerissen — sie haengt nicht am Katalog (D-10).'
    )
    assert EINE_SACHE_TITEL in html, (
        'Die Ueberschrift der einen Sache ist im Leer-Fall verschwunden — dann ist "nichts '
        'gefunden" von "gar nicht ausgewertet" nicht zu unterscheiden.'
    )


def test_beobachtungen_liegen_hinter_dem_aufklapper(client, db_from_client, tracker):
    """Die VOLLSTAENDIGEN Beobachtungen liegen hinter `<details>`, Kopfzeile und eine Sache davor.

    Der Positions-Vergleich ist bewusst auf die CODE-FORM des NEUEN Elements gerichtet
    (`<details class="n-observation-dim">`) und nicht auf den nackten Tag-Namen: die Datei
    traegt seit dem Vorgespraechs-Block bereits ein zweites `<details`. Ein Anker auf `<details`
    allein wuerde nicht sagen, WELCHES Element gemeint ist.

    Gepaarter Existenz-Anker: der Dimensions-Titel steht ueberhaupt im HTML — sonst wuerde
    `html.index` mit ValueError scheitern statt eine falsche Reihenfolge zu melden."""
    dim_name = DIMENSIONS[0]['name']
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(),
    }, typ='live')
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert AUFKLAPPER_FORM in html, 'Der Aufklapper um die vollstaendigen Beobachtungen fehlt.'
    assert AUFKLAPPER_TITEL in html, 'Der Aufklapper hat keine Beschriftung.'
    assert dim_name in html, 'Der Dimensions-Titel steht gar nicht im HTML.'
    assert html.index(AUFKLAPPER_FORM) < html.index(dim_name), (
        'Die Dimensionen stehen VOR dem Aufklapper — die vollstaendigen Beobachtungen liegen '
        'nicht einen Klick tiefer.'
    )
    assert html.index(KOPFZEILE_BEOBACHTUNG) < html.index(AUFKLAPPER_FORM), (
        'Die Kopfzeile steht hinter dem Aufklapper statt davor.'
    )
    assert html.index(FOKUS_SATZ) < html.index(AUFKLAPPER_FORM), (
        'Die eine Sache steht hinter dem Aufklapper statt davor.'
    )


def test_alle_beobachtungen_verworfen_zeigt_nicht_genug(client, db_from_client, tracker):
    """SPEC Req 3: sind ALLE Beobachtungen von der Zitat-Pruefung verworfen worden, steht dort
    „Nicht genug zum Bewerten." — NICHT eine leere Seite und NICHT die Dauer-Meldung.

    ⚠ Ehrlich benannt: dieser Test ist schon VOR dem Bau gruen. Sein Zweck ist nicht der
    Neubau, sondern die Regel gegen ein Zuviel — der Faenger sitzt ab Plan 07 INNERHALB des
    Aufklappers und muss diesen Umzug ueberleben. Er muss rot werden, sobald jemand ihn beim
    Einhuellen verliert."""
    leer = {d['key']: [] for d in DIMENSIONS}
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        **leer,
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(focus_key=None, satz='', beleg='', count=0),
    }, typ='live')
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert LEER_SATZ in html, (
        'Der Faenger „Nicht genug zum Bewerten." ist beim Einhuellen in den Aufklapper '
        'verlorengegangen — der Anruf zeigt eine leere Stelle.'
    )
    assert DAUER_MELDUNG not in html, (
        'Die Seite zeigt die Dauer-Meldung „wird im Hintergrund ausgewertet" — die Zeile ist '
        'da, sie hat nur nichts Verwertbares. Das ist die falsche Erklaerung.'
    )


def test_ki_karte_steht_vor_dem_kb_verlauf(client, db_from_client, tracker):
    """D-15: Die KI-Einschaetzung ist das Erste auf der Seite.

    ⚠ ANKER-WAHL, begruendet statt geraten: Der urspruengliche Plan-Anker („KI-Karte vor dem
    Training-Hero", Zeichenkette `Gesamt-Score`) ist per Bauart unerfuellbar — bei
    `typ='training'` ist die KI-Karte gar nicht sichtbar (sie steht hart in einer
    `conv.typ == 'live'`-Weiche), und bei `typ='live'` gibt es nach Plan 06 keinen
    `Gesamt-Score` mehr. Es gibt also keinen Seitenzustand, in dem beide Zeichenketten
    gleichzeitig vorkaemen.

    `Kaufbereitschafts-Verlauf` ist der `else`-Zweig der Diagramm-Ueberschrift — also genau der
    LIVE-Zweig — und liegt deutlich unterhalb der KI-Karte.

    Gepaarter Existenz-Anker: beide Zeichenketten stehen ueberhaupt im HTML. Ohne ihn wuerde
    `html.index` bei einem leeren Rendering mit ValueError scheitern und wie ein Testfehler
    aussehen statt wie ein Fund."""
    dim_key = DIMENSIONS[0]['key']
    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        dim_key: [{'beobachtung': BEOBACHTUNG, 'beleg_zitat': BELEG_ZITAT}],
        '_kopfzeile': _kopfzeile(),
        '_fokus': _fokus(),
    }, typ='live', kb_end=64)
    _login(client, u, tenant_id)

    r = client.get(f'/session/{sid}')
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    html = r.get_data(as_text=True)

    assert 'KI-Einschätzung' in html, 'Die KI-Karte steht gar nicht im HTML.'
    assert 'Kaufbereitschafts-Verlauf' in html, 'Die Diagramm-Ueberschrift steht gar nicht im HTML.'
    assert html.index('KI-Einschätzung') < html.index('Kaufbereitschafts-Verlauf'), (
        'Die KI-Einschaetzung steht nicht als Erstes auf der Seite — sie ist ab METRIK-1 die '
        'Antwort auf „wie lief das Gespraech", nicht eine Beigabe unter dem Diagramm.'
    )
