# -*- coding: utf-8 -*-
"""METRIK-1 Plan 05 — Form 2 im Hintergrund: belegte Kopfzeile + genau EINE Sache.

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  Der Fokus ("die eine Sache") wird vom CODE aus den BERATER-Zeilen berechnet und landet als
  observations_jsonb['_fokus'] in derselben rubric_score-Zeile wie die Kopfzeile.

  Der Schluessel wird IMMER geschrieben — auch mit focus_key=None (D-10: "kein Kriterium
  verletzt" ist der NORMALFALL und muss von "Feld nie befuellt" unterscheidbar bleiben).

  Kunden-Zeilen und EWB-Knopf-Zeilen zaehlen NICHT: der Katalog bewertet den Verkaeufer, und
  ein Knopfdruck ist kein Satz.

Kein echter LLM-Aufruf, kein echter DB-Write in den Funktions-Tests: run_behavior_judge,
_segments_for_call und _upsert_rubric_score werden monkeypatcht; der UPSERT wird abgefangen.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import template_rendered
from sqlalchemy import text
from werkzeug.security import generate_password_hash

import services.judge_runner as jr
import services.slow_lane as sl
from database.models import Call, ConversationLog, RubricScore, User
from services.judge_dimensions import DIMENSIONS
from tests.conftest import cleanup_rows

DIM = DIMENSIONS[0]['key']


def _seg(idx=1, speaker='berater', ts_ms=1000, text=''):
    """transcript_segments-Row-Attrappe (kein ORM, kein DB)."""
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text,
                           word_count=len(text.split()), start_ms=ts_ms, end_ms=ts_ms + 1000)


def _texte_als_segmente(texte, speaker='berater'):
    return [_seg(i + 1, speaker, (i + 1) * 1000, t) for i, t in enumerate(texte)]


def _observations(kopf_zitat='', kopf_beobachtung='', dim_zitat=''):
    """observations_jsonb-Form aus judge_runner._parse_judge_output."""
    obs = {d['key']: [] for d in DIMENSIONS}
    if dim_zitat:
        obs[DIM] = [{'beobachtung': 'Der Berater fragte offen nach.', 'beleg_zitat': dim_zitat}]
    obs['_compliance'] = {'verletzt': False, 'beleg_zitat': ''}
    obs['_kopfzeile'] = {'schema': 1, 'beobachtung': kopf_beobachtung, 'beleg_zitat': kopf_zitat}
    return obs


def _lauf(monkeypatch, segments, observations=None):
    """Fuehrt _judge_step mit gemocktem Bewerter aus und liefert die an den UPSERT
    uebergebenen observations zurueck."""
    call = SimpleNamespace(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        call_mode='cold_call',
        conversation_log_id=4242,
        user_id=1,
        transcript_resolved=True,
    )
    gefangen = {}

    def _fake_judge(_call, _events, _db):
        return {
            'observations_jsonb': observations if observations is not None else _observations(),
            'ratings_jsonb': {},
            'dimensions_version': 2,
            'status': 'judged',
        }

    def _fake_upsert(_db, **kwargs):
        gefangen.update(kwargs)

    monkeypatch.setattr(jr, 'run_behavior_judge', _fake_judge)
    monkeypatch.setattr(sl, '_segments_for_call', lambda _sid, _db: segments)
    monkeypatch.setattr(sl, '_upsert_rubric_score', _fake_upsert)

    sl._judge_step({'call': call, 'events': [], 'db': MagicMock()})

    assert 'observations' in gefangen, 'Der UPSERT wurde ohne observations aufgerufen.'
    return gefangen['observations']


# ── Die vier englischen Berater-Zeilen mit 4x "we provide" (Katalog-Schwelle 4) ────────────
ENGLISCH_NEGATIV = [
    'Hi there, we provide sales coaching for teams like yours.',
    'And we provide onboarding for every new rep.',
    'On top of that we provide weekly reviews.',
    'Finally we provide a dashboard for your managers.',
]

DEUTSCH_NEUTRAL = [
    'Guten Tag Herr Meier, mein Name ist Anna Schmidt von der Vertriebsberatung.',
    'Der Grund meines Anrufs: wir haben mit Betrieben Ihrer Groesse gearbeitet.',
    'Wo klemmt es bei Ihnen im Moment am meisten?',
    'Verstehe, das hoere ich oft. Darf ich dazu zwei Fragen stellen?',
]


def test_fokus_wird_aus_berater_texten_berechnet(monkeypatch):
    """Vier Berater-Zeilen mit 'we provide' -> observations['_fokus'] traegt negative_phrases."""
    obs = _lauf(monkeypatch, _texte_als_segmente(ENGLISCH_NEGATIV))

    assert '_fokus' in obs, "'_fokus' fehlt in den gespeicherten observations"
    fokus = obs['_fokus']
    assert fokus['focus_key'] == 'negative_phrases', f"focus_key ist {fokus['focus_key']!r}"
    assert fokus['count'] >= 4
    assert fokus['satz'], 'Der Fokus-Satz ist leer.'
    # Der Beleg ist per Bauart woertlich eine der uebergebenen Zeilen (D-07).
    assert fokus['beleg'] in ENGLISCH_NEGATIV
    assert fokus['katalog_version'] == 1


def test_fokus_none_wird_trotzdem_geschrieben(monkeypatch):
    """D-10: nie eine leere Stelle, nie ein fehlender Schluessel.

    Auf deutschem Bestand loest per Bauart kein Kriterium aus — der Schluessel steht trotzdem
    da, mit focus_key=None. Sonst waere "kein Fokus" von "Feld nie befuellt" nicht zu
    unterscheiden."""
    obs = _lauf(monkeypatch, _texte_als_segmente(DEUTSCH_NEUTRAL))

    assert '_fokus' in obs, "'_fokus' fehlt — 'kein Fokus' waere von 'nie befuellt' ununterscheidbar"
    assert obs['_fokus']['focus_key'] is None
    assert obs['_fokus']['satz'] is None
    assert obs['_fokus']['schema'] == 1


def test_kundenzeilen_zaehlen_nicht_fuer_den_fokus(monkeypatch):
    """Der Katalog bewertet den VERKAEUFER: dieselben Saetze als Kunden-Zeilen ergeben nichts."""
    obs = _lauf(monkeypatch, _texte_als_segmente(ENGLISCH_NEGATIV, speaker='kunde'))

    assert obs['_fokus']['focus_key'] is None, (
        'Eine Kunden-Zeile hat den Fokus ausgeloest — dem Berater wuerde vorgehalten, was der '
        'Kunde gesagt hat.'
    )


def test_ewb_zeile_zaehlt_nicht_fuer_den_fokus(monkeypatch):
    """Ein Knopfdruck ist kein Satz — die EWB-Pseudo-Zeile darf keinen Fokus erzeugen.

    Gepaarter Positiv-Fall in derselben Funktion: dieselben Texte OHNE Suffix loesen aus.
    Ohne ihn waere 'kein Fokus' nicht vom kaputten Testaufbau zu unterscheiden."""
    mit_marker = [t + ' *ewb button*' for t in ENGLISCH_NEGATIV]

    obs_gefiltert = _lauf(monkeypatch, _texte_als_segmente(mit_marker))
    assert obs_gefiltert['_fokus']['focus_key'] is None, (
        'Die EWB-Knopf-Zeilen haben einen Fokus erzeugt — der Filter greift nicht.'
    )

    obs_positiv = _lauf(monkeypatch, _texte_als_segmente(ENGLISCH_NEGATIV))
    assert obs_positiv['_fokus']['focus_key'] == 'negative_phrases', (
        'Der Positiv-Fall loest nicht aus — der Negativ-Fall oben beweist dann nichts.'
    )


def test_kopfzeile_und_fokus_stehen_nebeneinander(monkeypatch):
    """Beide Unterstrich-Schluessel liegen in DERSELBEN rubric_score-Zeile.

    Das Kopfzeilen-Zitat ist woertlich eine der Transkript-Zeilen und ueberlebt deshalb die
    Zitat-Pruefung — genau die Pruefung, die ein erfundenes Zitat verwerfen wuerde."""
    segments = _texte_als_segmente(ENGLISCH_NEGATIV)
    obs = _lauf(monkeypatch, segments, observations=_observations(
        kopf_zitat=ENGLISCH_NEGATIV[0],
        kopf_beobachtung='Klarer Einstieg mit dem Nutzen.',
    ))

    assert '_kopfzeile' in obs and '_fokus' in obs
    assert obs['_kopfzeile']['beobachtung'] == 'Klarer Einstieg mit dem Nutzen.'
    assert obs['_kopfzeile']['beleg_zitat'] == ENGLISCH_NEGATIV[0]
    assert obs['_fokus']['focus_key'] == 'negative_phrases'


# ══════════════════════════════════════════════════════════════════════════════════════════
# Task 3: Kopfzeile und eine Sache im ANZEIGE-Kontext
#
# Das Template rendert sie erst in Plan 07 — geprueft wird deshalb der Template-KONTEXT
# (flask.template_rendered-Signal), nicht das HTML. HTTP 200 als gepaarter Existenz-Anker.
# ══════════════════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tracker(db_from_client):
    """Reverse-FK-Teardown. ZWEI cleanup_rows-Aufrufe, weil `calls` KIND von `conversation_logs`
    ist, die globale _CLEANUP_FK_ORDER aber conversation_logs VOR calls listet (dieselbe
    Reihenfolge-Falle wie in test_session_detail_render.py)."""
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


def _seed_session(db, tracker, observations):
    """Nutzer + ConversationLog + Call + live-rubric_score in der Seed-Org der client-Fixture.

    Die eigene Org waere ein anderer tenant_id — `rubric_score` hat FORCE RLS und die Zeile
    waere fuer den Request unsichtbar (der Test waere aus dem falschen Grund gruen/rot)."""
    from tests import conftest as _cf
    tenant_id = _cf.TEST_TENANT_UUID
    org_id = db.execute(
        text("SELECT legacy_org_id FROM tenant_orgs WHERE id = :t"), {"t": tenant_id}
    ).scalar()
    assert org_id is not None, 'Seed-Tenant der client-Fixture nicht aufloesbar'

    u = User(email=f'form2_{uuid.uuid4().hex[:8]}@nerve.local',
             passwort_hash=generate_password_hash('pw'),
             rolle='owner', org_id=org_id, aktiv=True, onboarding_done=True)
    db.add(u)
    db.flush()
    tracker['users'].append(u.id)

    conv = ConversationLog(user_id=u.id, org_id=org_id, typ='live',
                           started_at=datetime.now(timezone.utc))
    db.add(conv)
    db.flush()
    tracker['logs'].append(conv.id)

    call_id = str(uuid.uuid4())
    db.add(Call(id=call_id, user_id=u.id, tenant_id=tenant_id, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc),
                transcript_storage='none', outcome='meeting_booked',
                conversation_log_id=conv.id))
    tracker['calls'].append(call_id)

    db.add(RubricScore(id=uuid.uuid4(), call_id=call_id, conversation_log_id=conv.id,
                       session_mode='cold_call', origin='live', status='scored',
                       tenant_id=tenant_id, observations_jsonb=observations, payload_jsonb={}))
    db.commit()
    return u, conv.id, tenant_id


def _login(client, u, tenant_id):
    """Login MIT `tenant_id` — ohne den Eintrag ist die GUC leer und `rubric_score`
    (FORCE RLS) liefert still 0 Zeilen (FORCE-RLS-Falle)."""
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
        s['tenant_id'] = str(tenant_id)


def test_kontext_traegt_kopfzeile_und_fokus(client, db_from_client, tracker):
    """`/session/<sid>` gibt kopfzeile_display und fokus_display in geformter Form weiter."""
    from app import app as flask_app

    u, sid, tenant_id = _seed_session(db_from_client, tracker, {
        DIM: [{'beobachtung': 'Bedarf sauber ausgelesen.',
               'beleg_zitat': 'Was bremst Sie im Moment am meisten?'}],
        '_kopfzeile': {'schema': 1, 'beobachtung': 'Der beste Moment: ruhig gespiegelt.',
                       'beleg_zitat': 'Verstehe ich richtig, dass das Budget klemmt?'},
        '_fokus': {'schema': 1, 'katalog_version': 1, 'focus_key': 'negative_phrases',
                   'count': 5, 'satz': 'You said "we provide" 5 times — top reps cap it at 3.',
                   'beleg': 'And we provide onboarding for every new rep.'},
    })
    _login(client, u, tenant_id)

    kontexte = []

    def _mitschreiben(_sender, template, context, **_extra):
        kontexte.append(context)

    template_rendered.connect(_mitschreiben, flask_app)
    try:
        r = client.get(f'/session/{sid}')
    finally:
        template_rendered.disconnect(_mitschreiben, flask_app)

    # Gepaarter Existenz-Anker: "Schluessel nicht gefunden" darf nicht von "Seite nicht
    # gerendert" kommen.
    assert r.status_code == 200, f'Auswertungs-Seite antwortet {r.status_code} statt 200.'
    assert kontexte, 'Es wurde kein Template gerendert — das Signal hat nichts mitgeschrieben.'
    ctx = kontexte[0]

    assert 'kopfzeile_display' in ctx, 'kopfzeile_display fehlt im Template-Kontext'
    assert 'fokus_display' in ctx, 'fokus_display fehlt im Template-Kontext'
    assert ctx['kopfzeile_display']['beobachtung'] == 'Der beste Moment: ruhig gespiegelt.'
    assert ctx['kopfzeile_display']['beleg_zitat'] == 'Verstehe ich richtig, dass das Budget klemmt?'
    assert ctx['fokus_display']['focus_key'] == 'negative_phrases'
    assert ctx['fokus_display']['satz'].startswith('You said')
    assert ctx['fokus_display']['beleg'] == 'And we provide onboarding for every new rep.'
