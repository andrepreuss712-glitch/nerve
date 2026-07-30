"""Behavioral Tests fuer den counterpart_switch-DB-Write + Skip-Guard via handle_toggle_counterpart.

Phase 08.23.2.COUNTERPART: der Toggle ist server-autoritativ. Der Browser sendet
'toggle_counterpart' OHNE Wert, der Server rechnet das Gegenteil aus SEINEM Zustand.
Migration 0035: der DB-Event heisst 'counterpart_switch' — nicht mehr nach der Anruf-Art.
Die Payload traegt getrennte Achsen (call_type + old_counterpart/new_counterpart). Der
DATEINAME bleibt bewusst wie er ist (Diff-Rauschen ohne Nutzen, CLAUDE.md Punkt 17).

Phase 08.23.2.C.R.F (bleibt gueltig): Tests muessen den echten Handler aufrufen — nicht
manuell CallEvent-Objekte bauen und in Mock-DB schieben (das war der False-Green-Klassen-
Fehler aus Phase C.R der zu C.R.F gefuehrt hat).

Technik: register_audio_handlers(mock_sio) mit mock_sio.on-Capture, dann handler() direkt aufrufen.
flask.request und database.db.SessionLocal werden gepacht damit der Handler isoliert laeuft.

REQ-6: counterpart_switch CallEvents muessen in DB geschrieben werden wenn call_id gesetzt.
Skip-Guard: wenn call_id=None → kein INSERT (kein aktiver Anruf).
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


def test_counterpart_switch_payload_persisted_to_db():
    """handle_toggle_counterpart schreibt CallEvent mit korrekten Feldern in DB.

    Szenario: call_id ist im State gesetzt (create_call_for_sid() wurde aufgerufen,
    wie nach Plan 01 auf jedem Produktions-Pfad). Toggle von gatekeeper zu decision_maker.
    Erwartet: handler ruft db_session.add() mit CallEvent(event_type='counterpart_switch')
    auf, Payload enthaelt call_type, old_counterpart, new_counterpart.
    """
    test_sid = 'test-mode-switch-rf-001'
    test_call_id = 'test-uuid-rf-switch-001'

    handler, mock_sio = _extract_handler('toggle_counterpart')

    # State wie nach create_call_for_sid() (Plan 01): call_id ist gesetzt
    with ls._session_state_lock:
        ls._session_state[test_sid] = {
            'mode': 'cold_call',            # ACHSE A (call_type), top-level
            'state': {
                'counterpart': 'gatekeeper',   # ACHSE B (Gespraechspartner)
                'call_id': test_call_id,
                'current_phase': 1,
                'phase_hint_count': 0,
                'pending_phase': None,
                'phase_entered_at': 0.0,
            }
        }

    mock_db = MagicMock()
    added_objects = []
    mock_db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
    mock_db.commit = MagicMock()
    mock_db.close = MagicMock()

    try:
        with patch('flask.request', new=MagicMock(sid=test_sid)), \
             patch('database.db.SessionLocal', return_value=mock_db):
            handler(None)

        # Handler muss genau 1 Objekt in DB geschrieben haben
        assert len(added_objects) == 1, (
            f'Erwartet 1 DB-Add-Aufruf, war: {len(added_objects)}. '
            f'Skip-Guard darf bei gesetzter call_id nicht feuern.'
        )
        evt = added_objects[0]

        # event_type und call_id korrekt — der Event heisst 'counterpart_switch'
        assert evt.event_type == 'counterpart_switch', f'event_type falsch: {evt.event_type!r}'
        assert evt.call_id == test_call_id, f'call_id falsch: {evt.call_id!r}'

        # 3 Pflicht-Payload-Keys (getrennte Achsen)
        assert 'call_type' in evt.payload, 'call_type fehlt im Payload'
        assert 'old_counterpart' in evt.payload, 'old_counterpart fehlt im Payload'
        assert 'new_counterpart' in evt.payload, 'new_counterpart fehlt im Payload'

        # Werte korrekt: vorher gatekeeper, nachher decision_maker; Anruf-Art unveraendert
        assert evt.payload['old_counterpart'] == 'gatekeeper'
        assert evt.payload['new_counterpart'] == 'decision_maker'
        assert evt.payload['call_type'] == 'cold_call'

    finally:
        with ls._session_state_lock:
            ls._session_state.pop(test_sid, None)


def test_call_id_none_means_skip_guard_fires():
    """handle_toggle_counterpart schreibt KEIN CallEvent wenn call_id=None im State.

    Szenario: call_id ist None (wie VOR Plan 01 auf Produktions-Pfad, oder nach
    einem DB-Fehler in create_call_for_sid). Skip-Guard in handler: if _call_id is None
    → kein DB-Write.
    Erwartet: db_session.add() wird nie aufgerufen.
    """
    test_sid = 'test-skip-guard-rf-001'

    handler, mock_sio = _extract_handler('toggle_counterpart')

    # State mit call_id=None — Skip-Guard-Bedingung
    with ls._session_state_lock:
        ls._session_state[test_sid] = {
            'mode': 'cold_call',
            'state': {
                'counterpart': 'gatekeeper',
                'call_id': None,
                'current_phase': 1,
                'phase_hint_count': 0,
                'pending_phase': None,
                'phase_entered_at': 0.0,
            }
        }

    mock_db = MagicMock()
    mock_db.close = MagicMock()

    try:
        with patch('flask.request', new=MagicMock(sid=test_sid)), \
             patch('database.db.SessionLocal', return_value=mock_db):
            handler(None)

        # Skip-Guard muss gefeuert haben — kein DB-Write erwartet
        mock_db.add.assert_not_called()

    finally:
        with ls._session_state_lock:
            ls._session_state.pop(test_sid, None)
