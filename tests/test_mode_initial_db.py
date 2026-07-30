"""Behavioral-Test fuer mode_initial DB-INSERT in create_call_for_sid().

Phase 08.23.2.C.R: Verifiziert dass create_call_for_sid() tatsaechlich
einen mode_initial-Eintrag in call_events schreibt (REQ-6 DB-INSERT-Nachweis).
Nutzt Mock-SessionLocal (via database.db.SessionLocal) damit kein produktives
Schema benoetigt wird.

Patch-Strategie: create_call_for_sid importiert SessionLocal lokal via
`from database.db import SessionLocal` — daher muss database.db.SessionLocal
gepatcht werden (nicht services.live_session.SessionLocal, das nicht existiert).
"""
from unittest.mock import patch, MagicMock


def _make_mock_session():
    """Mock-Session die .add()-Aufrufe aufzeichnet."""
    session = MagicMock()
    session.added_objects = []

    def _add(obj):
        session.added_objects.append(obj)

    session.add = MagicMock(side_effect=_add)
    session.commit = MagicMock()
    session.close = MagicMock()
    session.rollback = MagicMock()
    return session


def test_create_call_for_sid_writes_mode_initial():
    """create_call_for_sid() muss mode_initial-Event in call_events schreiben."""
    import services.live_session as ls

    test_sid = 'test-behavioral-sid-001'

    # Session-State mit gatekeeper-Default vorbereiten
    with ls._session_state_lock:
        ls._session_state[test_sid] = {
            'mode': 'cold_call',          # ACHSE A (call_type), top-level
            'state': {
                'counterpart': 'gatekeeper',   # ACHSE B (Gespraechspartner)
                'call_id': None,
            }
        }

    try:
        # Beide DB-Sitzungen (Call-Insert + mode_initial-Insert) tracken
        main_session = _make_mock_session()
        mi_session = _make_mock_session()

        # Call-Objekt mit .id nach refresh() simulieren
        real_call_obj = MagicMock()

        def _mock_refresh(obj):
            obj.id = 'test-uuid-0001-0001'

        main_session.refresh = MagicMock(side_effect=_mock_refresh)

        session_call_count = [0]

        def _session_factory():
            session_call_count[0] += 1
            if session_call_count[0] == 1:
                return main_session
            return mi_session

        # database.db.SessionLocal patchen — create_call_for_sid importiert lokal
        # `from database.db import SessionLocal as _SL` und `_SL_mi`.
        with patch('database.db.SessionLocal', side_effect=_session_factory), \
             patch('database.models.Call', return_value=real_call_obj):

            result = ls.create_call_for_sid(test_sid, user_id=1)

        # Rueckgabe muss eine call_id (string) sein
        assert result is not None, 'create_call_for_sid() hat None zurueckgegeben'

        # mode_initial-CallEvent muss via mi_session.add() geschrieben worden sein
        mi_added = mi_session.added_objects
        assert len(mi_added) >= 1, (
            'create_call_for_sid() hat keinen mode_initial-Event in call_events geschrieben. '
            'Plan 04 Task 2 (Wave 2) muss den INSERT implementiert haben.'
        )

        # Hinzugefuegtes Objekt muss mode_initial-Payload haben
        evt = mi_added[-1]
        assert evt.event_type == 'mode_initial', (
            f'Erwartetes event_type="mode_initial", aber got {evt.event_type!r}'
        )
        # Phase 08.23.2.COUNTERPART: getrennte Achsen, getrennte Felder
        assert evt.payload['counterpart'] == 'gatekeeper'
        assert evt.payload['call_type'] == 'cold_call'
        assert evt.payload['sid'] == test_sid
        assert 'timestamp' in evt.payload

    finally:
        # Cleanup: State nach Test entfernen
        with ls._session_state_lock:
            ls._session_state.pop(test_sid, None)
