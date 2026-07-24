"""Phase 08.23.2.STABIL-1 Plan 02 (b) — Session-los-Guard + gehaerteter DB-Fallback.

Runtime-Verhalten gegen echte Flask test_client Requests + real-PG (CLAUDE.md
Test-Qualitaets-Regel: KEINE Source-Presence-Assertions).

Guard-Halbseite (api_beenden :192-206):
    _bs is None UND kein geposteter call_id -> sofortiger 200 {ok:False,
    reason:'no_session'} no-op — kein CRM-Call, kein ConversationLog-INSERT,
    kein audit_log, keine Punkte, kein calls-UPDATE.

Fallback-Halbseite (api_beenden Fallback-Query, PRE-EXECUTE-AUDIT K1):
    Nur EIN offener Call innerhalb STABIL1_FALLBACK_FRESH_HOURS (2h, eigene
    Konstante, NICHT MAX_SESSION_HOURS) wird geschlossen; bei Mehrdeutigkeit
    oder Alter wird NICHT geraten (D-02).

Baseline-Sicherheit (Rewrite, siehe .planning-Auftrag): jeder Test laeuft gegen
eine EIGENE throwaway Organisation + einen EIGENEN throwaway User (fixture
`throwaway` unten) — NIE gegen die geschuetzte Baseline User id=1 / Org id=1.
Die volle /api/beenden-Pipeline (Fair-Use/Punkte-Block ~app_routes.py:614-647)
mutiert dadurch NUR die throwaway-Rows; der autouse `_baseline_cleanup_guard`
bleibt unberuehrt. Jeder Test traegt seine erzeugten Call-/ConversationLog-Ids
in den vom Fixture bereitgestellten Tracker ein — das Fixture-Teardown raeumt
ALLES (audit_log ueber conv-target, calls, conversation_logs, den User, seinen
tenant_orgs-Eintrag, die Org) reverse-FK via dem kanonischen `cleanup_rows`-
Helfer (best-effort, FK-zyklus-robust) weg.

Session-Isolation (Defekt 2): vor jedem no-op/guard-POST wird
`_clear_leaked_sessions_for_user()` aufgerufen — entfernt alle
`services.live_session._session_state`-Eintraege des throwaway-Users, damit
der Stufe-2 user_id-Scan (app_routes.py:164-171) NICHTS findet und `_bs`
None bleibt (der Guard bei :206 feuert dann tatsaechlich). Seit der PERSID-
Migration (CLAUDE.md Punkt 28) ist `_session_state` der EINZIGE modul-globale
Live-Zustand-Dict in live_session.py — keine weiteren Sibling-Maps zu leeren.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

import config as _cfg
import services.live_session as ls
from database.db import get_session
from database.models import AuditLog, Call, ConversationLog, Organisation, User
from tests.conftest import cleanup_rows

_CRM_MOCK_RETURN = {'crm_notiz': '', 'followup_email': '', 'naechste_schritte': []}


def _make_call(user_id, started_at=None, call_mode='cold_call'):
    """Erzeugt einen offenen Call-Record (analog create_call_for_sid) unter der throwaway user_id.
    Gibt call_id (str) zurueck. Caller MUSS die id in throwaway['call_ids'] eintragen."""
    db = get_session()
    try:
        call_id = str(uuid.uuid4())
        row = Call(
            id=call_id,
            user_id=user_id,
            call_mode=call_mode,
            started_at=started_at or datetime.now(timezone.utc),
            transcript_storage='none',
        )
        db.add(row)
        db.commit()
        return call_id
    finally:
        db.close()


def _seed_live_session(user_id, call_id=None):
    """Minimaler lebender Session-State (services.live_session._session_state[sid]).

    Alle downstream-Reads in api_beenden gehen ueber `_bs.get(key, default)` — die hier
    NICHT gesetzten Keys fallen auf ihre Defaults zurueck, kein Crash. Kein call_id im
    `state`-Sub-Dict -> Stufe 1 (posted call_id) greift nicht, Stufe 2 (user_id-Scan)
    loest die sid auf, _phase_d_call_id bleibt None -> der DB-Fallback (Task 2) wird
    erzwungen (statt frueh aus _bs befuellt zu werden).
    """
    sid = f"test-stabil1-{uuid.uuid4().hex[:12]}"
    state = {
        'user_id': user_id,
        'session_start_time': time.monotonic(),
        'state': {'call_id': call_id} if call_id else {},
        'berater_words': 0, 'kunde_words': 0,
        'laengster_monolog_sek': 0.0,
        'word_confidences': [],
        'conversation_log': [], 'painpoints': [],
        'kaufbereitschaft_verlauf': [], 'kaufbereitschaft': 30,
        'covered_phases': set(), 'aktive_phase_idx': 0,
        'gegenargument_log': [], 'phasen_log': [],
        'session_anrede': None,
    }
    with ls._session_state_lock:
        ls._session_state[sid] = state
    return sid


def _cleanup_sid(sid):
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


def _clear_leaked_sessions_for_user(user_id):
    """Session-Isolation (Defekt 2): entfernt VOR einem no-op/guard-POST alle _session_state-
    Eintraege des throwaway-Users, damit der Stufe-2 user_id-Scan (app_routes.py:164-171)
    NICHTS findet -> _bs bleibt None -> der Guard (:206) feuert tatsaechlich. Ein frischer
    throwaway-User hat in der Praxis noch keine Session, aber das explizite Clear macht die
    Guard-Tests unabhaengig von Test-Reihenfolge / Wiederholungslaeufen / Leaks anderer Tests."""
    with ls._session_state_lock:
        stale_sids = [s for s, st in ls._session_state.items() if st.get('user_id') == user_id]
        for s in stale_sids:
            ls._session_state.pop(s, None)


@pytest.fixture
def throwaway(client):
    """Throwaway Organisation + User (ORM) — NIE die geschuetzte Baseline id=1 anfassen.

    org via flush() (feuert trg_mk_tenant_org automatisch -> tenant_orgs-Row, KEIN manueller
    Insert, CLAUDE.md Punkt 22 F1-Lektion), User darunter, Client wird per session_transaction
    als dieser User authentifiziert. Gibt einen Tracker-Dict zurueck; jeder Test traegt seine
    erzeugten Call-/ConversationLog-Ids in tracker['call_ids']/['conv_ids'] ein.

    Teardown (reverse-FK, best-effort via cleanup_rows):
      1. Alle _session_state-Eintraege des Users leeren (kein Leak in Folgetests).
      2. audit_log-Zeilen mit target_type='conversation_log' + target_id in conv_ids (eigene
         Query, cleanup_rows kennt keine target_type-Filterung).
      3. Call + ConversationLog + User + tenant_orgs + Organisation in EINEM cleanup_rows-Aufruf
         (FK-zyklus-robuster Savepoint-Retry-Loop im Helfer selbst — keine manuelle Order noetig).
    """
    db = client._test_session
    org = Organisation(name=f"[STABIL1-TEST] org {uuid.uuid4().hex[:8]}", plan='starter')
    db.add(org)
    db.flush()  # feuert trg_mk_tenant_org -> tenant_orgs-Row automatisch
    user = User(
        email=f"stabil1-{uuid.uuid4().hex[:8]}@nerve.local",
        passwort_hash=generate_password_hash('pw'),
        rolle='owner', org_id=org.id, aktiv=True, onboarding_done=True,
    )
    db.add(user)
    db.commit()
    org_id, user_id = org.id, user.id

    tenant_org_row = db.execute(
        text("SELECT id FROM tenant_orgs WHERE legacy_org_id = :o"), {"o": org_id}
    ).first()
    tenant_org_id = tenant_org_row[0] if tenant_org_row else None

    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    tracker = {'user_id': user_id, 'org_id': org_id, 'call_ids': [], 'conv_ids': []}
    yield tracker

    _clear_leaked_sessions_for_user(user_id)

    call_ids = [c for c in tracker['call_ids'] if c]
    conv_ids = [c for c in tracker['conv_ids'] if c]

    cleanup_db = get_session()
    try:
        # audit_log traegt trg_audit_log_immutable (Migration 0026, BEFORE DELETE -> RAISE),
        # der AUCH fuer den Owner feuert. nerve_app OWNT audit_log (conftest.py:701) -> Trigger
        # SCOPED deaktivieren, ALLE audit_log-Rows dieses Wegwerf-Users/-Orgs loeschen (nicht nur
        # target_type: die NO-ACTION-FKs audit_log.user_id/org_id -> users/organisations halten
        # sonst User+Org fest -> cleanup_rows unten stallt), Trigger im finally IMMER reaktivieren.
        # Drei getrennte committete TX (Muster aus _baseline_cleanup_guard, conftest.py:703).
        cleanup_db.execute(text(
            "ALTER TABLE public.audit_log DISABLE TRIGGER trg_audit_log_immutable"))
        cleanup_db.commit()
        try:
            cleanup_db.query(AuditLog).filter(
                (AuditLog.user_id == user_id) | (AuditLog.org_id == org_id)
            ).delete(synchronize_session=False)
            cleanup_db.commit()
        finally:
            cleanup_db.execute(text(
                "ALTER TABLE public.audit_log ENABLE TRIGGER trg_audit_log_immutable"))
            cleanup_db.commit()

        spec = {}
        if call_ids:
            spec[Call] = call_ids
        if conv_ids:
            spec[ConversationLog] = conv_ids
        spec[User] = [user_id]
        if tenant_org_id:
            spec['public.tenant_orgs'] = [tenant_org_id]
        spec[Organisation] = [org_id]
        cleanup_rows(cleanup_db, spec)
    finally:
        cleanup_db.close()


# ── Guard-Halbseite ───────────────────────────────────────────────────────────

def test_beenden_ohne_session_ist_noop(client, throwaway):
    """Kein Session-State, kein geposteter call_id -> 200 {ok:False, reason:'no_session'}."""
    _clear_leaked_sessions_for_user(throwaway['user_id'])
    with patch('services.crm_service.generate_crm_export') as m_crm:
        resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
        if resp.status_code in (302, 401):
            pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
        assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
        data = resp.get_json()
        assert data is not None
        assert data['ok'] is False
        assert data['reason'] == 'no_session'
        m_crm.assert_not_called()


def test_guard_schreibt_nichts(client, throwaway):
    """Guard-Pfad: 0 ConversationLog-INSERTs, 0 Aenderungen an total_points/live_calls_used/
    minuten_used, generate_crm_export wird NICHT aufgerufen."""
    uid = throwaway['user_id']
    _clear_leaked_sessions_for_user(uid)

    db = get_session()
    try:
        u_before = db.get(User, uid)
        convs_before = db.query(ConversationLog).filter(ConversationLog.user_id == uid).count()
        pts_before = u_before.total_points
        calls_used_before = u_before.live_calls_used
        min_before = u_before.minuten_used
    finally:
        db.close()

    with patch('services.crm_service.generate_crm_export') as m_crm:
        resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
        if resp.status_code in (302, 401):
            pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is False and data['reason'] == 'no_session'
        m_crm.assert_not_called()

    db = get_session()
    try:
        u_after = db.get(User, uid)
        convs_after = db.query(ConversationLog).filter(ConversationLog.user_id == uid).count()
        assert convs_after == convs_before, 'Guard-Pfad darf kein ConversationLog anlegen'
        assert u_after.total_points == pts_before, 'Guard-Pfad darf keine Punkte vergeben'
        assert u_after.live_calls_used == calls_used_before, 'Guard-Pfad darf live_calls_used nicht erhoehen'
        assert u_after.minuten_used == min_before, 'Guard-Pfad darf minuten_used nicht erhoehen'
    finally:
        db.close()


def test_guard_schliesst_keinen_offenen_call(client, throwaway):
    """Kern-Regressionstest fuer Live-Anruf 1: ein bereits offener Call eines ANDEREN
    Requests bleibt nach einem sitzungslosen /api/beenden unangetastet (ended_at is None)."""
    uid = throwaway['user_id']
    _clear_leaked_sessions_for_user(uid)
    call_id = _make_call(user_id=uid, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    throwaway['call_ids'].append(call_id)

    with patch('services.crm_service.generate_crm_export') as m_crm:
        resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
        if resp.status_code in (302, 401):
            pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['reason'] == 'no_session'
        m_crm.assert_not_called()

    db = get_session()
    try:
        row = db.get(Call, call_id)
        assert row.ended_at is None, 'Guard darf den fremden offenen Call NICHT schliessen'
        assert row.conversation_log_id is None
    finally:
        db.close()


def test_geposteter_call_id_umgeht_den_guard(client, throwaway):
    """Ein geposteter call_id OHNE lebende Session ist KEIN Guard-Fall (dokumentiert das
    Soll-Verhalten fuer den spaeteren Plan-04-Fall — Bypass ist bis STABIL-2 nicht erreichbar,
    da das Frontend heute keine call_id postet). Antwort ist NICHT reason=='no_session'."""
    uid = throwaway['user_id']
    call_id = _make_call(user_id=uid, started_at=datetime.now(timezone.utc) - timedelta(minutes=2))
    throwaway['call_ids'].append(call_id)

    with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
        resp = client.post('/api/beenden', json={'session_mode': 'cold_call', 'call_id': call_id})
        if resp.status_code in (302, 401):
            pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('reason') != 'no_session', \
            'Geposteter call_id ohne Session muss den Guard umgehen (normaler Pfad laeuft)'
        if data.get('conv_id'):
            throwaway['conv_ids'].append(data['conv_id'])


# ── Fallback-Halbseite ─────────────────────────────────────────────────────────

def test_fallback_nimmt_eindeutigen_frischen_call(client, throwaway):
    """Positiv-Fall: genau EIN offener, frischer Call + lebender Session-State (ohne call_id
    im State) -> der Fallback greift, die Row hat danach ended_at is not None. Verhindert
    dass die Haertung (K1/Eindeutigkeit) zu scharf wird. Throwaway-User traegt NUR diesen
    einen Call -> keine Fremd-Calls anderer Tests koennen die Eindeutigkeit stoeren (Defekt 3)."""
    uid = throwaway['user_id']
    call_id = _make_call(user_id=uid, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    throwaway['call_ids'].append(call_id)
    sid = _seed_live_session(user_id=uid)
    try:
        with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
            resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get('ok') is True
            if data.get('conv_id'):
                throwaway['conv_ids'].append(data['conv_id'])

        db = get_session()
        try:
            row = db.get(Call, call_id)
            assert row.ended_at is not None, 'Eindeutiger frischer Call MUSS geschlossen werden'
        finally:
            db.close()
    finally:
        _cleanup_sid(sid)


def test_fallback_raet_nicht_bei_zwei_offenen_calls(client, throwaway):
    """Zwei offene Calls des Users -> der Fallback raet NICHT (D-02): beide Rows haben
    danach weiterhin ended_at is None."""
    uid = throwaway['user_id']
    call_id_a = _make_call(user_id=uid, started_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    call_id_b = _make_call(user_id=uid, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    throwaway['call_ids'].extend([call_id_a, call_id_b])
    sid = _seed_live_session(user_id=uid)
    try:
        with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
            resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
            assert resp.status_code == 200
            data = resp.get_json()
            if data.get('conv_id'):
                throwaway['conv_ids'].append(data['conv_id'])

        db = get_session()
        try:
            row_a = db.get(Call, call_id_a)
            row_b = db.get(Call, call_id_b)
            assert row_a.ended_at is None, 'Mehrdeutigkeit -> Fallback darf keinen der Calls schliessen'
            assert row_b.ended_at is None, 'Mehrdeutigkeit -> Fallback darf keinen der Calls schliessen'
        finally:
            db.close()
    finally:
        _cleanup_sid(sid)


def test_fallback_ignoriert_veralteten_call(client, throwaway):
    """PRE-EXECUTE-AUDIT K1: Frische-Fenster ist STABIL1_FALLBACK_FRESH_HOURS (2h Default),
    NICHT mehr MAX_SESSION_HOURS (8h). Ein Call aelter als das Frische-Fenster wird vom
    Fallback ignoriert -> ended_at bleibt None."""
    uid = throwaway['user_id']
    stale_started = datetime.now(timezone.utc) - timedelta(hours=_cfg.STABIL1_FALLBACK_FRESH_HOURS + 1)
    call_id = _make_call(user_id=uid, started_at=stale_started)
    throwaway['call_ids'].append(call_id)
    sid = _seed_live_session(user_id=uid)
    try:
        with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
            resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
            assert resp.status_code == 200
            data = resp.get_json()
            if data.get('conv_id'):
                throwaway['conv_ids'].append(data['conv_id'])

        db = get_session()
        try:
            row = db.get(Call, call_id)
            assert row.ended_at is None, 'Veralteter Call (ausserhalb Frische-Fenster) darf nicht geschlossen werden'
        finally:
            db.close()
    finally:
        _cleanup_sid(sid)
