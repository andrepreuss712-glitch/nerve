"""Hin-und-Zurueck-Waechter fuer den server-autoritativen Gespraechspartner-Toggle.

Phase 08.23.2.COUNTERPART Waechter 1. Dieser Test existierte vor dieser Phase NIRGENDS:
tests/test_mode_switch_event.py ruft den Toggle-Handler in zwei getrennten Tests je genau
EINMAL auf, nie zweimal im selben Testkoerper — genau deshalb ist der Verklemm-Bug
(ab Klick 2 immer derselbe Zielwert) durch alle Netze gerutscht.

Vertrag: Browser sendet 'toggle_counterpart' OHNE Wert. Der Server berechnet das Gegenteil
aus SEINEM Zustand. Zweimal getoggelt == Ausgangszustand.

KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel): jeder Test ruft den
ECHTEN Handler auf und assertiert die State-Mutation im per-SID-Dict — Runtime-Verhalten,
kein 'Code existiert'-Check.
"""
from unittest.mock import patch, MagicMock
import services.live_session as ls


def _extract_handler(event_name):
    """Extrahiert einen registrierten SocketIO-Handler aus register_audio_handlers.

    register_audio_handlers(sio) registriert Handler als verschachtelte Closures via
    @sio.on(event). Wir uebergeben ein Mock-sio dessen .on-Methode die Registrierungen
    in einem Dict aufzeichnet — so koennen wir den echten Handler-Code direkt aufrufen.
    """
    registered = {}

    mock_sio = MagicMock()
    # sio.on(event) gibt einen Decorator zurueck der fn registriert und unveraendert zurueckgibt
    mock_sio.on = lambda event: (lambda fn: registered.__setitem__(event, fn) or fn)

    from services.deepgram_service import register_audio_handlers
    register_audio_handlers(mock_sio)

    return registered[event_name], mock_sio


def _cp(sid):
    """Liest den Gespraechspartner aus dem per-SID-State (oder None)."""
    with ls._session_state_lock:
        return ((ls._session_state.get(sid) or {}).get('state') or {}).get('counterpart')


def _seed_state(sid, counterpart='gatekeeper', call_id=None, mode='cold_call'):
    """Per-SID-State wie nach init_session_state (Achse A top-level, Achse B im Sub-Dict)."""
    with ls._session_state_lock:
        ls._session_state[sid] = {
            'mode': mode,          # ACHSE A: Anruf-Art (call_type) — NICHT der Gespraechspartner
            'user_id': 1,
            'org_id': 1,
            'state': {
                'counterpart': counterpart,   # ACHSE B: Gespraechspartner
                'call_id': call_id,
                'current_phase': 1,
                'phase_hint_count': 0,
                'pending_phase': None,
                'phase_entered_at': 0.0,
            },
        }


def _drop_state(sid):
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


def test_toggle_counterpart_roundtrip_returns_to_gatekeeper():
    """DER Waechter: zweimal toggeln muss wieder beim Ausgangswert landen.

    Die Assertion NACH dem ersten Aufruf ist die eigentliche Falsifizierbarkeit —
    ohne sie waere der Test auch gruen, wenn der Handler gar nichts taete.
    """
    sid = 'test-cp-roundtrip-001'
    handler, mock_sio = _extract_handler('toggle_counterpart')
    _drop_state(sid)
    _seed_state(sid)
    try:
        with patch('flask.request', new=MagicMock(sid=sid)), \
             patch('database.db.SessionLocal', return_value=MagicMock()):
            handler(None)
            assert _cp(sid) == 'decision_maker', (
                f"Erster Toggle muss auf decision_maker kippen, war: {_cp(sid)!r}")
            handler(None)
            assert _cp(sid) == 'gatekeeper', (
                f"Hin-und-Zurueck gebrochen: zweiter Toggle muss wieder gatekeeper "
                f"ergeben, war: {_cp(sid)!r}")
    finally:
        _drop_state(sid)


def test_toggle_counterpart_ignores_payload():
    """Server-Autoritaet: ein mitgeschickter Alt-Payload ist wirkungslos."""
    sid = 'test-cp-ignores-payload-001'
    handler, mock_sio = _extract_handler('toggle_counterpart')
    _drop_state(sid)
    _seed_state(sid)
    try:
        with patch('flask.request', new=MagicMock(sid=sid)), \
             patch('database.db.SessionLocal', return_value=MagicMock()):
            handler({'category': 'gatekeeper'})   # boesartiger Alt-Payload
        assert _cp(sid) == 'decision_maker', (
            f"Der Server rechnet aus SEINEM Zustand; der Payload darf nichts bestimmen. "
            f"War: {_cp(sid)!r}")
    finally:
        _drop_state(sid)


def test_toggle_without_session_state_is_refused():
    """Race-Waechter A: SID gar nicht bekannt -> kein Write, kein Erfolg, kein Geister-Eintrag."""
    sid = 'test-cp-no-session-001'
    handler, mock_sio = _extract_handler('toggle_counterpart')
    _drop_state(sid)
    try:
        with patch('flask.request', new=MagicMock(sid=sid)), \
             patch('database.db.SessionLocal', return_value=MagicMock()):
            handler(None)

        assert sid not in ls._session_state, (
            'Toggle ohne Session-State hat einen Geister-Eintrag angelegt.')

        _emits = [c.args for c in mock_sio.emit.call_args_list]
        _changed = [a for a in _emits if a and a[0] == 'counterpart_changed']
        assert not _changed, (
            f'Kein counterpart_changed erwartet ohne aktiven Session-State, waren: {len(_changed)}')

        _acks = [a for a in _emits if a and a[0] == 'counterpart_toggle_ack']
        assert len(_acks) == 1, f'Genau EIN Ack erwartet, waren: {len(_acks)}'
        assert _acks[0][1]['ok'] is False, (
            f"Ablehnung muss ok:False melden, war: {_acks[0][1]!r}")
    finally:
        _drop_state(sid)


def test_toggle_before_init_does_not_create_state():
    """Race-Waechter B (das echte Fenster): SID da wie nach 'connect', aber ohne 'state'-Sub-Dict.

    Ein setdefault('state', {}) wuerde hier ein Dict anlegen, das init_session_state
    Sekundenbruchteile spaeter wholesale wegwirft — genau der Bug.
    """
    sid = 'test-cp-before-init-001'
    handler, mock_sio = _extract_handler('toggle_counterpart')
    _drop_state(sid)
    with ls._session_state_lock:
        ls._session_state[sid] = {'_user_id': 1}
    try:
        with patch('flask.request', new=MagicMock(sid=sid)), \
             patch('database.db.SessionLocal', return_value=MagicMock()):
            handler(None)

        assert 'state' not in ls._session_state[sid], (
            "setdefault-Geist: der Handler hat ein 'state'-Sub-Dict angelegt, das "
            "init_session_state gleich darauf wegwirft.")

        _emits = [c.args for c in mock_sio.emit.call_args_list]
        _changed = [a for a in _emits if a and a[0] == 'counterpart_changed']
        assert not _changed, (
            f'Kein counterpart_changed erwartet vor init_session_state, waren: {len(_changed)}')

        _acks = [a for a in _emits if a and a[0] == 'counterpart_toggle_ack']
        assert len(_acks) == 1, f'Genau EIN Ack erwartet, waren: {len(_acks)}'
        assert _acks[0][1]['ok'] is False, (
            f"Ablehnung muss ok:False melden, war: {_acks[0][1]!r}")
    finally:
        _drop_state(sid)


def test_successful_toggle_emits_exactly_one_counterpart_changed():
    """Erfolgs-Emit-Waechter: Server-Zustand und Anzeige duerfen nicht unbewacht auseinanderlaufen."""
    sid = 'test-cp-emit-once-001'
    handler, mock_sio = _extract_handler('toggle_counterpart')
    _drop_state(sid)
    _seed_state(sid)
    try:
        with patch('flask.request', new=MagicMock(sid=sid)), \
             patch('database.db.SessionLocal', return_value=MagicMock()):
            handler(None)

        _changed = [c for c in mock_sio.emit.call_args_list
                    if c.args and c.args[0] == 'counterpart_changed']
        assert len(_changed) == 1, f"Genau EIN counterpart_changed erwartet, waren: {len(_changed)}"
        assert _changed[0].args[1]['counterpart'] == 'decision_maker'
        assert _changed[0].args[1]['source'] == 'manual'
        assert _changed[0].kwargs.get('room') == sid      # room=sid, kein Broadcast
        _acks = [c for c in mock_sio.emit.call_args_list
                 if c.args and c.args[0] == 'counterpart_toggle_ack']
        assert len(_acks) == 1 and _acks[0].args[1] == {'ok': True}
    finally:
        _drop_state(sid)
