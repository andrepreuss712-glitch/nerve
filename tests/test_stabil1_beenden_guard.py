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

Tests, die den vollen Pfad durchlaufen lassen (Bypass/Fallback-Haelfte),
mutieren den geteilten Base-Seed-User (id=1) via Punkte/Fair-Use-Update —
_UserCounterSnapshot friert diese Felder ein und stellt sie im Teardown
wieder her (Baseline-Sauberkeit, CLAUDE.md Test-Cleanup-Regel). Erzeugte
Call/ConversationLog/AuditLog-Rows werden von jedem Test explizit weggeraeumt.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import config as _cfg
import services.live_session as ls
from database.db import get_session
from database.models import AuditLog, Call, ConversationLog, Organisation, User

_CRM_MOCK_RETURN = {'crm_notiz': '', 'followup_email': '', 'naechste_schritte': []}


def _auth_client(client, user_id=1):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return client


def _make_call(user_id=1, started_at=None, call_mode='cold_call'):
    """Erzeugt einen offenen Call-Record (analog create_call_for_sid). Gibt call_id (str) zurueck."""
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


def _cleanup_calls(call_ids):
    call_ids = [c for c in (call_ids or []) if c]
    if not call_ids:
        return
    db = get_session()
    try:
        db.query(Call).filter(Call.id.in_(call_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _cleanup_conv(conv_ids):
    """Raeumt ConversationLog + zugehoerige AuditLog-Zeilen weg. MUSS NACH _cleanup_calls
    laufen (Call.conversation_log_id ist FK auf conversation_logs.id — Kind zuerst)."""
    conv_ids = [c for c in (conv_ids or []) if c]
    if not conv_ids:
        return
    db = get_session()
    try:
        db.query(AuditLog).filter(
            AuditLog.target_type == 'conversation_log',
            AuditLog.target_id.in_(conv_ids),
        ).delete(synchronize_session=False)
        db.query(ConversationLog).filter(ConversationLog.id.in_(conv_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _seed_live_session(user_id=1, call_id=None):
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


class _UserCounterSnapshot:
    """Friert users.total_points/live_calls_used/minuten_used/level + organisations.
    live_minutes_used/fair_use_reset_month fuer die Dauer eines Tests ein und stellt sie
    danach wieder her. Noetig fuer Tests, die den vollen Punkte-Update-Block (:628-663)
    gegen den geteilten Base-Seed-User (id=1) durchlaufen lassen — sonst Baseline-Pollution."""

    def __init__(self, user_id=1, org_id=1):
        self.user_id = user_id
        self.org_id = org_id
        self._snap = {}

    def __enter__(self):
        db = get_session()
        try:
            u = db.get(User, self.user_id)
            org = db.get(Organisation, self.org_id)
            self._snap = {
                'total_points': u.total_points,
                'live_calls_used': u.live_calls_used,
                'minuten_used': u.minuten_used,
                'level': u.level,
                'live_minutes_used': org.live_minutes_used if org else None,
                'fair_use_reset_month': org.fair_use_reset_month if org else None,
            }
        finally:
            db.close()
        return self

    def __exit__(self, *exc):
        db = get_session()
        try:
            u = db.get(User, self.user_id)
            org = db.get(Organisation, self.org_id)
            if u is not None:
                u.total_points = self._snap.get('total_points')
                u.live_calls_used = self._snap.get('live_calls_used')
                u.minuten_used = self._snap.get('minuten_used')
                u.level = self._snap.get('level')
            if org is not None:
                org.live_minutes_used = self._snap.get('live_minutes_used')
                org.fair_use_reset_month = self._snap.get('fair_use_reset_month')
            db.commit()
        finally:
            db.close()
        return False


# ── Guard-Halbseite ───────────────────────────────────────────────────────────

def test_beenden_ohne_session_ist_noop(client):
    """Kein Session-State, kein geposteter call_id -> 200 {ok:False, reason:'no_session'}."""
    _auth_client(client)
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


def test_guard_schreibt_nichts(client):
    """Guard-Pfad: 0 ConversationLog-INSERTs, 0 Aenderungen an total_points/live_calls_used/
    minuten_used, generate_crm_export wird NICHT aufgerufen."""
    _auth_client(client)
    db = get_session()
    try:
        u_before = db.get(User, 1)
        convs_before = db.query(ConversationLog).filter(ConversationLog.user_id == 1).count()
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
        u_after = db.get(User, 1)
        convs_after = db.query(ConversationLog).filter(ConversationLog.user_id == 1).count()
        assert convs_after == convs_before, 'Guard-Pfad darf kein ConversationLog anlegen'
        assert u_after.total_points == pts_before, 'Guard-Pfad darf keine Punkte vergeben'
        assert u_after.live_calls_used == calls_used_before, 'Guard-Pfad darf live_calls_used nicht erhoehen'
        assert u_after.minuten_used == min_before, 'Guard-Pfad darf minuten_used nicht erhoehen'
    finally:
        db.close()


def test_guard_schliesst_keinen_offenen_call(client):
    """Kern-Regressionstest fuer Live-Anruf 1: ein bereits offener Call eines ANDEREN
    Requests bleibt nach einem sitzungslosen /api/beenden unangetastet (ended_at is None)."""
    _auth_client(client)
    call_id = _make_call(user_id=1, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    try:
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
    finally:
        _cleanup_calls([call_id])


def test_geposteter_call_id_umgeht_den_guard(client):
    """Ein geposteter call_id OHNE lebende Session ist KEIN Guard-Fall (dokumentiert das
    Soll-Verhalten fuer den spaeteren Plan-04-Fall — Bypass ist bis STABIL-2 nicht erreichbar,
    da das Frontend heute keine call_id postet). Antwort ist NICHT reason=='no_session'."""
    _auth_client(client)
    call_id = _make_call(user_id=1, started_at=datetime.now(timezone.utc) - timedelta(minutes=2))
    conv_ids = []
    with _UserCounterSnapshot(user_id=1, org_id=1):
        try:
            with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
                resp = client.post('/api/beenden', json={'session_mode': 'cold_call', 'call_id': call_id})
                if resp.status_code in (302, 401):
                    pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data.get('reason') != 'no_session', \
                    'Geposteter call_id ohne Session muss den Guard umgehen (normaler Pfad laeuft)'
                if data.get('conv_id'):
                    conv_ids.append(data['conv_id'])
        finally:
            _cleanup_calls([call_id])
            _cleanup_conv(conv_ids)


# ── Fallback-Halbseite ─────────────────────────────────────────────────────────

def test_fallback_nimmt_eindeutigen_frischen_call(client):
    """Positiv-Fall: genau EIN offener, frischer Call + lebender Session-State (ohne call_id
    im State) -> der Fallback greift, die Row hat danach ended_at is not None. Verhindert
    dass die Haertung (K1/Eindeutigkeit) zu scharf wird."""
    _auth_client(client)
    call_id = _make_call(user_id=1, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    sid = _seed_live_session(user_id=1)
    conv_ids = []
    with _UserCounterSnapshot(user_id=1, org_id=1):
        try:
            with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
                resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
                if resp.status_code in (302, 401):
                    pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
                assert resp.status_code == 200
                data = resp.get_json()
                assert data.get('ok') is True
                if data.get('conv_id'):
                    conv_ids.append(data['conv_id'])

            db = get_session()
            try:
                row = db.get(Call, call_id)
                assert row.ended_at is not None, 'Eindeutiger frischer Call MUSS geschlossen werden'
            finally:
                db.close()
        finally:
            _cleanup_sid(sid)
            _cleanup_calls([call_id])
            _cleanup_conv(conv_ids)


def test_fallback_raet_nicht_bei_zwei_offenen_calls(client):
    """Zwei offene Calls des Users -> der Fallback raet NICHT (D-02): beide Rows haben
    danach weiterhin ended_at is None."""
    _auth_client(client)
    call_id_a = _make_call(user_id=1, started_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    call_id_b = _make_call(user_id=1, started_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    sid = _seed_live_session(user_id=1)
    conv_ids = []
    with _UserCounterSnapshot(user_id=1, org_id=1):
        try:
            with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
                resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
                if resp.status_code in (302, 401):
                    pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
                assert resp.status_code == 200
                data = resp.get_json()
                if data.get('conv_id'):
                    conv_ids.append(data['conv_id'])

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
            _cleanup_calls([call_id_a, call_id_b])
            _cleanup_conv(conv_ids)


def test_fallback_ignoriert_veralteten_call(client):
    """PRE-EXECUTE-AUDIT K1: Frische-Fenster ist STABIL1_FALLBACK_FRESH_HOURS (2h Default),
    NICHT mehr MAX_SESSION_HOURS (8h). Ein Call aelter als das Frische-Fenster wird vom
    Fallback ignoriert -> ended_at bleibt None."""
    _auth_client(client)
    stale_started = datetime.now(timezone.utc) - timedelta(hours=_cfg.STABIL1_FALLBACK_FRESH_HOURS + 1)
    call_id = _make_call(user_id=1, started_at=stale_started)
    sid = _seed_live_session(user_id=1)
    conv_ids = []
    with _UserCounterSnapshot(user_id=1, org_id=1):
        try:
            with patch('services.crm_service.generate_crm_export', return_value=dict(_CRM_MOCK_RETURN)):
                resp = client.post('/api/beenden', json={'session_mode': 'cold_call'})
                if resp.status_code in (302, 401):
                    pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')
                assert resp.status_code == 200
                data = resp.get_json()
                if data.get('conv_id'):
                    conv_ids.append(data['conv_id'])

            db = get_session()
            try:
                row = db.get(Call, call_id)
                assert row.ended_at is None, 'Veralteter Call (ausserhalb Frische-Fenster) darf nicht geschlossen werden'
            finally:
                db.close()
        finally:
            _cleanup_sid(sid)
            _cleanup_calls([call_id])
            _cleanup_conv(conv_ids)
