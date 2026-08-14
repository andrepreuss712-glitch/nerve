# -*- coding: utf-8 -*-
"""METRIK-1 Plan 01 Task 6 — Verhaltens-Tests der Gruender-Sicht auf die Zitat-Pruefung.

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  Alle FUENF Werte je Anruf kommen aus dem PERSISTIERTEN rubric_score.payload_jsonb['beleg_check']
      — nicht aus dem Prozess-Zaehler (der misst eine andere Groesse: summiert, pro Prozess).

  FORCE-RLS-Falle umgangen: die Mandanten-Schleife findet die Zeile auch dann, wenn der
      aufrufende Kontext KEINE passende Mandanten-GUC gesetzt hat. Ohne die Schleife liefert
      rubric_score als nerve_app STILL 0 Zeilen — eine leere Liste waere von "keine Verwuerfe"
      nicht zu unterscheiden. Dieser Test ist der EINZIGE Beleg, dass die Falle wirklich
      umgangen und nicht bloss im Docstring behauptet ist.

  Die Schwelle warnt von selbst — nach MENGE oder nach ANTEIL, letzteres erst ab einer
      tragfaehigen Stichprobe.

  Der Einzelfall ist AUFRUFBAR (Einloesung des Versprechens aus Task 4) und nur fuer superadmin.

Cleanup (CLAUDE.md Test-Cleanup-Regel): committende Rows werden reverse-FK weggeraeumt;
rubric_score haengt per FK ON DELETE CASCADE an calls und faellt mit dem Call.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

import routes.admin_dashboard as ad
from tests.conftest import cleanup_rows
from database.models import Call, ConversationLog, RubricScore, TranscriptSegment, User

BELEG_WERTE = {'schema': 1, 'geprueft': 9, 'treffer': 5, 'near_miss': 2,
               'verworfen': 2, 'compliance_beleg_verworfen': 1}
TRANSKRIPT_SATZ = 'Ich habe im Moment ehrlich gesagt kein Interesse.'


def _now():
    return datetime.now(timezone.utc)


def _tagesbeginn():
    return datetime.combine(date.today(), datetime.min.time())


@pytest.fixture
def tracker(db_from_client):
    """Reverse-FK-Teardown: calls zuerst (Kind von conversation_logs), dann logs + users."""
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


def _seed_fall(db, tracker, werte=None, is_superadmin=True, compliance=None):
    """Nutzer + ConversationLog + Call + Transkript + live-rubric_score mit beleg_check-Payload.

    Der Nutzer liegt in der Seed-Org der client-Fixture: rubric_score hat FORCE RLS, und der
    Request-Pfad setzt die Tenant-GUC aus der Org des eingeloggten Nutzers.
    """
    from tests import conftest as _cf
    tenant_id = _cf.TEST_TENANT_UUID
    org_id = db.execute(
        text("SELECT legacy_org_id FROM tenant_orgs WHERE id = :t"), {"t": tenant_id}
    ).scalar()
    assert org_id is not None, 'Seed-Tenant der client-Fixture nicht aufloesbar'

    u = User(email=f'beleg_founder_{uuid.uuid4().hex[:8]}@nerve.local',
             passwort_hash=generate_password_hash('pw'),
             rolle='owner', org_id=org_id, aktiv=True, onboarding_done=True,
             is_superadmin=is_superadmin)
    db.add(u)
    db.flush()
    tracker['users'].append(u.id)

    conv = ConversationLog(user_id=u.id, org_id=org_id, typ='live', started_at=_now())
    db.add(conv)
    db.flush()
    tracker['logs'].append(conv.id)

    db.add(TranscriptSegment(conversation_log_id=conv.id, ts_ms=1000,
                             speaker='kunde', text=TRANSKRIPT_SATZ))

    call_id = str(uuid.uuid4())
    db.add(Call(
        id=call_id, user_id=u.id, tenant_id=tenant_id, call_mode='cold_call',
        started_at=_now(), ended_at=_now(), transcript_storage='none',
        outcome='no_interest', conversation_log_id=conv.id,
    ))
    tracker['calls'].append(call_id)

    observations = {'_compliance': compliance or {'verletzt': True, 'beleg_zitat': ''}}
    db.add(RubricScore(
        id=uuid.uuid4(), call_id=call_id, conversation_log_id=conv.id,
        session_mode='cold_call', origin='live', status='judged', tenant_id=tenant_id,
        payload_jsonb={'beleg_check': dict(werte or BELEG_WERTE)},
        observations_jsonb=observations,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return u, call_id, tenant_id


def _login(client, u, tenant_id):
    with client.session_transaction() as s:
        s['user_id'] = u.id
        s['rolle'] = 'owner'
        s['tenant_id'] = str(tenant_id)


def test_faelle_enthalten_alle_fuenf_werte(client, db_from_client, tracker):
    """Alle fuenf Werte kommen mit den geseedeten Zahlen aus dem persistierten payload_jsonb."""
    _u, call_id, _tenant = _seed_fall(db_from_client, tracker)

    faelle = ad._beleg_check_faelle(db_from_client, _tagesbeginn())

    meiner = [f for f in faelle if f['call_id'] == call_id]
    assert len(meiner) == 1, f'Der geseedete Fall wurde nicht genau einmal gefunden ({len(meiner)}).'
    fall = meiner[0]
    assert fall['geprueft'] == BELEG_WERTE['geprueft']
    assert fall['treffer'] == BELEG_WERTE['treffer']
    assert fall['near_miss'] == BELEG_WERTE['near_miss']
    assert fall['verworfen'] == BELEG_WERTE['verworfen']
    assert fall['compliance_beleg_verworfen'] == BELEG_WERTE['compliance_beleg_verworfen']


def test_faelle_findet_die_zeile_trotz_force_rls(client, db_from_client, tracker):
    """OHNE passende Mandanten-GUC im aufrufenden Kontext wird der Fall TROTZDEM gefunden.

    Gegen eine naive Einzel-Abfrage ohne Mandanten-Schleife ist das rot — und zwar STILL
    (0 Zeilen statt eines Fehlers). Genau diese Stille ist die Falle."""
    from database.db import clear_current_tenant, set_current_tenant
    from tests import conftest as _cf

    _u, call_id, _tenant = _seed_fall(db_from_client, tracker)

    clear_current_tenant()   # der Founder-Request traegt NICHT die Mandanten-GUC dieses Anrufs
    try:
        faelle = ad._beleg_check_faelle(db_from_client, _tagesbeginn())
    finally:
        set_current_tenant(_cf.TEST_TENANT_UUID)   # Teardown braucht die GUC wieder

    gefunden = [f for f in faelle if f['call_id'] == call_id]
    assert len(gefunden) == 1, (
        'Die Zeile wurde OHNE Mandanten-GUC nicht gefunden — FORCE RLS liefert still 0 Zeilen, '
        'und eine leere Liste ist von "keine Verwuerfe" nicht zu unterscheiden.'
    )
    assert gefunden[0]['verworfen'] == BELEG_WERTE['verworfen']


def test_summe_ueber_schwelle_setzt_alarm(client, db_from_client, monkeypatch):
    """Die Schwelle warnt von selbst — nach Menge ODER Anteil, letzterer erst ab Stichprobe."""
    def _faelle(werte):
        def _fake(_db, _seit, grenze=20):
            return [dict(werte, call_id='x', tenant_id='t', created_at=None)]
        return _fake

    # (a) knapp UNTER der Mengen-Schwelle, Anteil unauffaellig -> kein Alarm
    monkeypatch.setattr(ad, '_beleg_check_faelle', _faelle({
        'geprueft': 100, 'treffer': 91, 'near_miss': 0,
        'verworfen': ad.BELEG_ALARM_VERWORFEN_HEUTE - 1, 'compliance_beleg_verworfen': 0}))
    assert ad._beleg_check_faelle_payload(db_from_client)['alarm'] is False

    # (b) knapp DARUEBER -> Alarm
    monkeypatch.setattr(ad, '_beleg_check_faelle', _faelle({
        'geprueft': 100, 'treffer': 89, 'near_miss': 0,
        'verworfen': ad.BELEG_ALARM_VERWORFEN_HEUTE + 1, 'compliance_beleg_verworfen': 0}))
    payload = ad._beleg_check_faelle_payload(db_from_client)
    assert payload['alarm'] is True
    assert payload['schwelle'] == ad.BELEG_ALARM_VERWORFEN_HEUTE

    # (c) hoher ANTEIL, aber Stichprobe zu klein -> KEIN Alarm (sonst alarmieren 2 von 3)
    monkeypatch.setattr(ad, '_beleg_check_faelle', _faelle({
        'geprueft': ad.BELEG_ALARM_MIN_GEPRUEFT - 1, 'treffer': 0,
        'near_miss': 1, 'verworfen': 1, 'compliance_beleg_verworfen': 0}))
    assert ad._beleg_check_faelle_payload(db_from_client)['alarm'] is False

    # (d) hoher ANTEIL mit tragfaehiger Stichprobe -> Alarm, obwohl die MENGE unter der Schwelle liegt
    monkeypatch.setattr(ad, '_beleg_check_faelle', _faelle({
        'geprueft': ad.BELEG_ALARM_MIN_GEPRUEFT + 5, 'treffer': 10,
        'near_miss': 10, 'verworfen': 1, 'compliance_beleg_verworfen': 0}))
    assert ad._beleg_check_faelle_payload(db_from_client)['alarm'] is True


def test_einzelfall_seite_zeigt_alle_fuenf_werte(client, db_from_client, tracker):
    """Die Einzelfall-Seite antwortet 200 und zeigt die fuenf Zahlen samt call_id."""
    u, call_id, tenant_id = _seed_fall(db_from_client, tracker)
    _login(client, u, tenant_id)

    r = client.get(f'/admin/dashboard/beleg-check/{call_id}')
    html = r.get_data(as_text=True)

    assert r.status_code == 200, f'Einzelfall-Seite antwortet {r.status_code} statt 200.'
    # Gepaarter Existenz-Anker: "Zahl nicht gefunden" darf nicht von "Seite nicht gerendert" kommen.
    assert 'ZITAT-PRÜFUNG' in html, 'Die Seite wurde gar nicht gerendert.'
    assert call_id in html, 'Die call_id fehlt auf der Einzelfall-Seite.'
    for feld in ('geprueft', 'treffer', 'near_miss', 'verworfen', 'compliance_beleg_verworfen'):
        assert f'>{BELEG_WERTE[feld]}<' in html, f'Der Wert fuer {feld} fehlt auf der Seite.'
    # Das Transkript steht zum Gegenlesen daneben — sonst ist das Zitat nicht pruefbar.
    assert TRANSKRIPT_SATZ in html, 'Das Transkript fehlt — der Beleg waere nicht gegenlesbar.'


def test_einzelfall_seite_ist_nicht_fuer_jeden(client, db_from_client, tracker):
    """Derselbe Aufruf als normaler Nutzer liefert NICHT 200."""
    u, call_id, tenant_id = _seed_fall(db_from_client, tracker, is_superadmin=False)
    _login(client, u, tenant_id)

    r = client.get(f'/admin/dashboard/beleg-check/{call_id}')

    assert r.status_code != 200, 'Ein normaler Nutzer darf den Einzelfall nicht sehen.'
    assert r.status_code in (302, 401, 403), f'Unerwarteter Status {r.status_code}.'
