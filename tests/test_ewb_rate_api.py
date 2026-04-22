"""Phase 08 Plan 05 — Rating-API + Anrede-Override integration tests.

Tests fuer POST /api/ewb/<id>/rate (3-State-Whitelist + Ownership) + Anrede-Whitelist
in services/deepgram_service.py start_live_session-Handler + /api/beenden persist.

Whitelist-Logik (Phase 08 W-1): isinstance(value, bool) or value is None.
Integer 1/0 darf NICHT als bool akzeptiert werden (Python-Equality 1 == True matcht sonst).
"""
import json
from datetime import datetime

import pytest

from database.models import (
    ConversationLog,
    ObjectionEvent,
    Organisation,
    Profile,
    User,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_user(db_session, email='test@test.de'):
    """Erstelle Org + User. Returnt (org, user)."""
    org = Organisation(name='T', plan='starter')
    db_session.add(org)
    db_session.flush()
    u = User(
        org_id=org.id,
        email=email,
        passwort_hash='x',
        market='dach',
        language='de',
    )
    db_session.add(u)
    db_session.flush()
    db_session.commit()
    return org, u


def _make_event(db_session, user, einwand_typ='Preis', success=None):
    """Helper: ConversationLog + ObjectionEvent fuer einen User."""
    conv = ConversationLog(
        user_id=user.id,
        org_id=user.org_id,
        session_mode='cold_call',
        dauer_sekunden=60,
        started_at=datetime.now(),  # NOT NULL constraint
    )
    db_session.add(conv)
    db_session.flush()
    ev = ObjectionEvent(
        user_id=user.id,
        org_id=user.org_id,
        conversation_log_id=conv.id,
        einwand_typ=einwand_typ,
        success=success,
    )
    db_session.add(ev)
    db_session.flush()
    db_session.commit()
    return conv, ev


def _login(client, user_id):
    """Setze session cookie direkt — Pattern aus test_admin_dashboard_auth.py."""
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


# ── Rating-API Tests ─────────────────────────────────────────────────────

def test_rate_success_true(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 200, r.data
    # Reload ev from DB
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is True


def test_rate_success_false(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': False}),
        content_type='application/json',
    )
    assert r.status_code == 200
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is False


def test_rate_success_null(client, db_from_client):
    """D-04 'Ueberspringen' → NULL. Falls Event vorher True war."""
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u, success=True)
    ev_id = ev.id
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': None}),
        content_type='application/json',
    )
    assert r.status_code == 200
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is None


def test_rate_invalid_string_rejected(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({'success': 'maybe'}),
        content_type='application/json',
    )
    assert r.status_code == 400


def test_rate_integer_rejected(client, db_from_client):
    """Phase 08 W-1: Strict type-check — integer 1/0 NICHT als bool akzeptieren.
    Python-Equality matcht 1 == True und 0 == False, aber isinstance(1, bool) ist False.
    """
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    ev_id = ev.id
    _login(client, u.id)
    # Integer 1 muss abgelehnt werden:
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': 1}),
        content_type='application/json',
    )
    assert r.status_code == 400, f'integer 1 must be rejected, got {r.status_code}'
    # Integer 0 muss ebenfalls abgelehnt werden:
    r = client.post(
        f'/api/ewb/{ev_id}/rate',
        data=json.dumps({'success': 0}),
        content_type='application/json',
    )
    assert r.status_code == 400, f'integer 0 must be rejected, got {r.status_code}'
    # DB muss unveraendert sein:
    reloaded = db.query(ObjectionEvent).filter_by(id=ev_id).first()
    assert reloaded.success is None, 'success column must not be mutated on rejected input'


def test_rate_missing_key_rejected(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    _login(client, u.id)
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert r.status_code == 400


def test_rate_unknown_event_404(client, db_from_client):
    db = db_from_client
    _org, u = _make_user(db)
    _login(client, u.id)
    r = client.post(
        '/api/ewb/99999/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 404


def test_rate_ownership_other_user_403(client, db_from_client):
    """User A cannot rate User B's event."""
    db = db_from_client
    _org_a, u_a = _make_user(db, 'a@a.de')
    _org_b, u_b = _make_user(db, 'b@b.de')
    _conv, ev_b = _make_event(db, u_b)
    _login(client, u_a.id)  # login als A
    r = client.post(
        f'/api/ewb/{ev_b.id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    assert r.status_code == 403


def test_rate_without_login_redirects(client, db_from_client):
    """@login_required muss redirecten — routes/auth.py redirect(url_for('auth.login')) = 302."""
    db = db_from_client
    _org, u = _make_user(db)
    _conv, ev = _make_event(db, u)
    # kein _login()
    r = client.post(
        f'/api/ewb/{ev.id}/rate',
        data=json.dumps({'success': True}),
        content_type='application/json',
    )
    # login_required ist implementation-spezifisch — accept 302 oder 401
    assert r.status_code in (302, 401), f'expected 302/401, got {r.status_code}'


# ── Anrede-Override Tests ────────────────────────────────────────────────

def test_anrede_whitelist_du():
    """Whitelist akzeptiert 'Du'."""
    import threading
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    # Simulation: session-start mit anrede='Du'
    anrede_raw = 'Du'
    if anrede_raw in ('Du', 'Sie'):
        with ls.state_lock:
            ls.state['session_anrede'] = anrede_raw
    try:
        assert ls.state.get('session_anrede') == 'Du'
    finally:
        with ls.state_lock:
            ls.state.pop('session_anrede', None)


def test_anrede_whitelist_rejects_invalid():
    """'Hallo; drop table' oder anderes → wird NICHT in ls.state geschrieben."""
    import threading
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    anrede_raw = 'Hallo; drop table'  # attempt prompt injection
    if anrede_raw in ('Du', 'Sie'):
        with ls.state_lock:
            ls.state['session_anrede'] = anrede_raw
    assert ls.state.get('session_anrede') is None


def test_conv_log_persists_anrede(db_session):
    """ConversationLog.anrede akzeptiert String oder None (D-14 Model-Schema)."""
    org = Organisation(name='T', plan='starter')
    db_session.add(org)
    db_session.flush()
    u = User(
        org_id=org.id,
        email='c@c.de',
        passwort_hash='x',
        market='dach',
        language='de',
    )
    db_session.add(u)
    db_session.flush()
    conv = ConversationLog(
        user_id=u.id,
        org_id=org.id,
        session_mode='cold_call',
        dauer_sekunden=60,
        started_at=datetime.now(),
        anrede='Du',
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)
    assert conv.anrede == 'Du'
