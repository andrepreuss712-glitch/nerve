"""Phase 08 Plan 05 — Rating-API + Anrede-Override integration tests.

Tests fuer POST /api/ewb/<id>/rate (3-State-Whitelist + Ownership) + Anrede-Whitelist
in services/deepgram_service.py start_live_session-Handler + /api/beenden persist.

Whitelist-Logik (Phase 08 W-1): isinstance(value, bool) or value is None.
Integer 1/0 darf NICHT als bool akzeptiert werden (Python-Equality 1 == True matcht sonst).
"""
import json
import uuid
from datetime import datetime

import pytest

from database.models import (
    ConversationLog,
    ObjectionEvent,
    Organisation,
    Profile,
    User,
)


# ── Cleanup ────────────────────────────────────────────────────────────────
# Diese Tests COMMITTEN ihre Org/User/ConvLog/ObjectionEvent-Kette (via _make_user/_make_event,
# beide rufen db_session.commit()). Auf der persistenten nerve_test wuerden diese Rows leaken ->
# der Baseline-Cleanup-Waechter (conftest._baseline_cleanup_guard) wuerde rot. Daher loescht der
# id-Wasserzeichen-Teardown (#8/MED-1) alle nach Fixture-Start angelegten Rows reverse-FK wieder weg.
# Public-only, kein crm -> kein Tenant-GUC noetig. Laeuft in der Fixture-POST-yield-Sektion (auch bei
# Assertion-Fehler) -> kein State-Leak.
@pytest.fixture(autouse=True)
def _ewb_rate_cleanup():
    import os as _os
    from sqlalchemy import create_engine as _ce, text as _sql
    dsn = _os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        yield
        return
    # Eigene kurzlebige Engine (entkoppelt davon, ob der Test db_session ODER client/db_from_client
    # nutzt — beide binden die MODUL-SessionLocal pro Test um/disposen sie). Snapshot der id-Watermark
    # VOR dem Test, reverse-FK-DELETE aller danach angelegten Rows NACH dem Test.
    eng = _ce(dsn)
    def _maxid(conn, tbl):
        try:
            return conn.execute(_sql(f"SELECT COALESCE(MAX(id),0) FROM public.{tbl}")).scalar()
        except Exception:
            return 0
    tables = ("objection_event", "conversation_logs", "users", "tenant_orgs", "organisations")
    with eng.connect() as conn:
        base = {t: _maxid(conn, t) for t in tables}
    try:
        yield
    finally:
        try:
            with eng.begin() as conn:
                # reverse-FK: objection_event -> conversation_logs -> users -> tenant_orgs -> orgs.
                conn.execute(_sql("DELETE FROM public.objection_event WHERE id > :b"),
                             {"b": base["objection_event"]})
                conn.execute(_sql("DELETE FROM public.conversation_logs WHERE id > :b"),
                             {"b": base["conversation_logs"]})
                # tenant_orgs keyed by legacy_org_id (trigger row per new org) -> delete those first.
                conn.execute(
                    _sql("DELETE FROM public.tenant_orgs WHERE legacy_org_id IN "
                         "(SELECT id FROM public.organisations WHERE id > :b)"),
                    {"b": base["organisations"]},
                )
                conn.execute(_sql("DELETE FROM public.users WHERE id > :b"), {"b": base["users"]})
                conn.execute(_sql("DELETE FROM public.organisations WHERE id > :b"),
                             {"b": base["organisations"]})
        except Exception as _te:
            print(f"[PGTEST-CLEANUP] ewb_rate teardown failed (non-fatal): {_te!r}")
        finally:
            eng.dispose()


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_user(db_session, email=None):
    """Erstelle Org + User. Returnt (org, user).

    Phase 08.23.2.PGTEST Task 6: email ist UNIQUE pro Run (uuid-suffixed) — sonst wirft
    users.email UNIQUE NOT NULL eine IntegrityError auf der persistenten nerve_test, wenn der Test
    neben anderen email-seedenden Tests laeuft. Org-Insert feuert trg_mk_tenant_org -> tenant_orgs
    entsteht automatisch (KEIN manueller tenant_orgs-Insert -> kein UNIQUE(legacy_org_id)-Bruch)."""
    if email is None:
        email = f"ewb-rate-{uuid.uuid4().hex[:8]}@nerve.local"
    else:
        # Auch explizit uebergebene Emails pro Run eindeutig machen (persistente nerve_test).
        local, _, domain = email.partition('@')
        email = f"{local}-{uuid.uuid4().hex[:8]}@{domain or 'nerve.local'}"
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
    # expire_all() forces a refresh from DB — route wrote via a separate Session
    # on the same shared engine, so test-session's cached ev is stale.
    db.expire_all()
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
    db.expire_all()
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
    db.expire_all()
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
    db.expire_all()
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

@pytest.fixture(autouse=True)
def _cleanup_session_anrede():
    """Autouse fixture: ensure ls.state['session_anrede'] is always clean
    before AND after each test in this module. Prevents cross-test leakage
    into test_ewb_pipeline.py which reads session_anrede via build_profile_context.
    """
    import threading
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    yield
    with ls.state_lock:
        ls.state.pop('session_anrede', None)


def _apply_anrede_whitelist(anrede_raw):
    """Mirror production logic from services/deepgram_service.py (CR-02)."""
    import services.live_session as ls
    anrede_norm = anrede_raw.strip().title() if isinstance(anrede_raw, str) else None
    if anrede_norm in ('Du', 'Sie'):
        with ls.state_lock:
            ls.state['session_anrede'] = anrede_norm
        return anrede_norm
    return None


def test_anrede_whitelist_du():
    """Whitelist akzeptiert 'Du' exakt."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Du')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_lowercase():
    """CR-02: 'du' wird als 'Du' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('du')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_whitespace():
    """CR-02: ' Du' (mit Whitespace) wird normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist(' Du ')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_uppercase():
    """CR-02: 'DU' wird als 'Du' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('DU')
    assert ls.state.get('session_anrede') == 'Du'


def test_anrede_whitelist_accepts_sie_lowercase():
    """CR-02: 'sie' wird als 'Sie' normalisiert und akzeptiert."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('sie')
    assert ls.state.get('session_anrede') == 'Sie'


def test_anrede_whitelist_rejects_invalid():
    """'Hallo; drop table' oder anderes → wird NICHT in ls.state geschrieben."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Hallo; drop table')  # attempt prompt injection
    assert ls.state.get('session_anrede') is None


def test_anrede_whitelist_rejects_partial_match():
    """CR-02: 'Duo' oder 'Sieb' fallen trotz Normalisierung raus."""
    import services.live_session as ls
    with ls.state_lock:
        ls.state.pop('session_anrede', None)
    _apply_anrede_whitelist('Duo')
    assert ls.state.get('session_anrede') is None
    _apply_anrede_whitelist('sieb')
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
