"""Phase 08.23.2.TAXO1 Plan 02 — Integration-Assertions fuer die Slow Lane.

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):
  - Graceful-Shutdown drained ein offenes Queue-Item ueber den Flush-Pfad (Rueckgabewert +
    Queue-leer-State).
  - Sentinel stoppt den Consumer sauber (das vom Consumer gelesene Item IST das Sentinel).
  - Graceful-Shutdown + Sentinel-Stop bleiben unveraendert (Queue-/Flush-Mechanik).

TAXO2-Plan 03 (2026-06-25): _persist_event_ref ist NICHT mehr No-Op — die Slow Lane benotet
jetzt in-place (handling_status-Statemachine + abstain_log). Der frueher hier lebende
`test_persist_event_ref_is_noop_on_intent_event` testete den TAXO1-No-Op-Vertrag und ist mit
dem Wave-Wechsel obsolet (Contract-Change). Die neue Statemachine-Verhaltens-Abdeckung liegt
in tests/test_handling_score_marker.py (scored/abstained/failed/Idempotenz/Poison-Pill).

Kein echter Prod-/PG-Write: flush_to_db's get_session() wird durch eine Mock-Session ersetzt,
sodass der Test DSN-frei laeuft (server-seitig wie lokal-skip-frei).
"""

from unittest.mock import MagicMock


def _fresh_slow_lane(monkeypatch):
    """Liefert das slow_lane-Modul mit einer FRISCHEN, leeren Queue (Test-Isolation gegen den
    Modul-Singleton). Gibt das Modul zurueck."""
    import services.slow_lane as sl
    # Singleton-Queue gegen eine frische ersetzen, damit Tests sich nicht gegenseitig vergiften.
    fresh = sl.SlowLaneQueue()
    monkeypatch.setattr(sl, 'slow_lane', fresh)
    return sl


def test_graceful_shutdown_flushes_queue_to_db(monkeypatch):
    sl = _fresh_slow_lane(monkeypatch)

    # get_session() durch eine Mock-Session ersetzen -> kein echter DB-Zugriff.
    mock_session = MagicMock()
    monkeypatch.setattr(sl, 'get_session', lambda: mock_session)

    # Ein offenes Arbeits-Item (leichter event_id-Verweis) in die Queue legen.
    sl.slow_lane.put({'event_id': 4711})

    # Simulierter Shutdown-Flush.
    n = sl.flush_to_db()

    # Integration-Assertion: genau 1 Item wurde gedrained ...
    assert n == 1
    # ... und die Queue ist danach leer (kein Rest-Item).
    assert sl.slow_lane.drain() == []
    # Session wurde sauber geschlossen (try-finally close, CLAUDE.md Database Patterns).
    mock_session.close.assert_called_once()


def test_sentinel_stops_consumer(monkeypatch):
    sl = _fresh_slow_lane(monkeypatch)

    # request_shutdown legt das Sentinel ab.
    sl.request_shutdown()

    # Der Consumer liest als naechstes Item das Sentinel -> sauberer Stop.
    item = sl.slow_lane.get(timeout=1.0)
    assert item is sl.SENTINEL


def test_drain_filters_out_sentinel(monkeypatch):
    sl = _fresh_slow_lane(monkeypatch)

    # Mix aus echtem Arbeits-Item und Sentinel.
    sl.slow_lane.put({'event_id': 1})
    sl.request_shutdown()           # legt SENTINEL
    sl.slow_lane.put({'event_id': 2})

    items = sl.slow_lane.drain()

    # drain() liefert NUR Arbeits-Items, das Sentinel ist herausgefiltert.
    assert {'event_id': 1} in items
    assert {'event_id': 2} in items
    assert sl.SENTINEL not in items
    assert len(items) == 2
