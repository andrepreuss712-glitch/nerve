"""
tests/test_callid_race_close.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.CALLID Plan 02 — Call-Start-Race-Close (CI-2, Mechanik=REORDER).

Beweist das Ordering-Gate als RUNTIME-Verhalten (kein Source-Presence): der echte
handle_start_live_session-Handler wird via register_audio_handlers(mock_sio)-Capture
extrahiert (Muster aus test_mode_switch_event.py) und aufgerufen. create_call_for_sid
und _open_deepgram_connection werden so gepatcht, dass sie ihre Aufruf-REIHENFOLGE und
den per-SID call_id-Zustand IM MOMENT des Connection-Open aufzeichnen.

Invariante (V-CI-3): _open_deepgram_connection (= Detection-Freischaltung) laeuft ERST
NACHDEM create_call_for_sid die durable call_id im per-SID-state gesetzt hat. Damit kann
KEIN intent_event mit call_id=NULL im Start-Fenster emittiert werden — die Reorder erzwingt
die Sequenz. Bricht jemand die Reorder (Connection-Open wieder vor create_call), faellt
dieser Test (echtes Verhalten, kein Mock-Schein).

Kein DSN noetig (reiner RAM-State + Mocks) — laeuft auch ohne TEST_DATABASE_URL.
"""
import uuid
from unittest.mock import patch, MagicMock

import services.live_session as ls
import services.deepgram_service as dg


def _extract_handler(event_name):
    """Extrahiert einen registrierten SocketIO-Handler (Closure) aus register_audio_handlers.
    mock_sio.on(event) zeichnet die Registrierung auf und gibt fn unveraendert zurueck."""
    registered = {}
    mock_sio = MagicMock()
    mock_sio.on = lambda event: (lambda fn: registered.__setitem__(event, fn) or fn)
    from services.deepgram_service import register_audio_handlers
    register_audio_handlers(mock_sio)
    return registered[event_name], mock_sio


def _mock_db_returning_none():
    """SessionLocal-Mock, dessen User/Profile-Queries None liefern (kein _load_profile_cache,
    kein DB-Zugriff) — der Handler laeuft mit org_id=0/profile=None durch."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.close = MagicMock()
    return mock_db


def test_connection_opens_only_after_call_id_durable():
    """V-CI-3: Bei jedem moeglichen Emit (= ab Connection-Open) ist die call_id bereits durable.
    REORDER erzwingt: create_call_for_sid VOR _open_deepgram_connection."""
    test_sid = f"test-race-{uuid.uuid4().hex[:10]}"
    durable_cid = str(uuid.uuid4())
    order = []
    snapshot = {}

    def fake_create(sid, user_id=None, call_mode='cold_call'):
        # mimt den echten create_call_for_sid: setzt die durable call_id im per-SID-state.
        order.append('create_call')
        with ls._session_state_lock:
            ls._session_state.setdefault(sid, {}).setdefault('state', {})['call_id'] = durable_cid
        return durable_cid

    def fake_open(sid, mode='cold_call', keyterms=None):
        order.append('open')
        # Zustand der call_id GENAU im Moment der Detection-Freischaltung:
        snapshot['call_id_at_open'] = ls.resolve_call_id_for_sid(sid)

    handler, _sio = _extract_handler('start_live_session')

    mock_session = MagicMock()
    mock_session.get.side_effect = lambda k, *a: 1 if k == 'user_id' else (a[0] if a else None)

    try:
        with patch('flask.request', new=MagicMock(sid=test_sid)), \
             patch('flask.session', new=mock_session), \
             patch('database.db.SessionLocal', return_value=_mock_db_returning_none()), \
             patch.object(ls, 'create_call_for_sid', new=fake_create), \
             patch.object(dg, '_open_deepgram_connection', new=fake_open):
            handler({'mode': 'cold_call'})

        # 1) Beide Schritte liefen, in der erzwungenen Reihenfolge.
        assert 'create_call' in order, "create_call_for_sid muss im Start-Pfad laufen (Single-Owner)"
        assert 'open' in order, "_open_deepgram_connection muss im Start-Pfad laufen"
        assert order.index('create_call') < order.index('open'), (
            f"REORDER verletzt: call_id-Anlage muss VOR Connection-Open liegen, war {order}"
        )

        # 2) Kernbeweis (V-CI-3): bei Detection-Freischaltung ist die call_id durable (NICHT None,
        #    NICHT Sentinel) -> kein NULL-call_id-Emit im Start-Fenster moeglich.
        assert snapshot.get('call_id_at_open') == durable_cid, (
            f"call_id bei Connection-Open war {snapshot.get('call_id_at_open')!r}, "
            f"erwartet durable {durable_cid!r} (NULL-Emit-Fenster nicht geschlossen)"
        )
    finally:
        with ls._session_state_lock:
            ls._session_state.pop(test_sid, None)


def test_create_call_is_single_owner_in_start_handler():
    """Single-Owner: create_call_for_sid wird aus dem Start-Handler gerufen (genau 1x),
    NICHT aus einem Detection-/emit-Pfad. Verhalten, kein grep."""
    test_sid = f"test-race-{uuid.uuid4().hex[:10]}"
    calls = []

    def fake_create(sid, user_id=None, call_mode='cold_call'):
        calls.append(sid)
        with ls._session_state_lock:
            ls._session_state.setdefault(sid, {}).setdefault('state', {})['call_id'] = str(uuid.uuid4())
        return ls._session_state[sid]['state']['call_id']

    handler, _sio = _extract_handler('start_live_session')
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda k, *a: 1 if k == 'user_id' else (a[0] if a else None)

    try:
        with patch('flask.request', new=MagicMock(sid=test_sid)), \
             patch('flask.session', new=mock_session), \
             patch('database.db.SessionLocal', return_value=_mock_db_returning_none()), \
             patch.object(ls, 'create_call_for_sid', new=fake_create), \
             patch.object(dg, '_open_deepgram_connection', new=lambda *a, **k: None):
            handler({'mode': 'cold_call'})
        assert calls == [test_sid], f"create_call_for_sid genau 1x aus dem Start-Handler, war {calls}"
    finally:
        with ls._session_state_lock:
            ls._session_state.pop(test_sid, None)
