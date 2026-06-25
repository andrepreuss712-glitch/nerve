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

    # CI-5 (08.23.2.CALLID Plan 03): flush_to_db ist jetzt A1-geklammert — PRO ITEM eine separate
    # Read-Session (GUC-freier Tenant-Lookup) + eine Schreib-Session unter gesetztem Tenant-GUC
    # (symmetrisch zum Consumer-Loop). get_session() liefert daher pro Aufruf eine FRISCHE
    # Mock-Session; wir sammeln sie, um den Per-Item-Read+Write-Pfad zu pruefen. Kein echter DB-Zugriff.
    sessions = []

    def _fresh_session():
        s = MagicMock()
        sessions.append(s)
        return s
    monkeypatch.setattr(sl, 'get_session', _fresh_session)

    # Tenant aufloesbar machen -> der Flush nimmt den echten A1-Pfad (set_current_tenant gesetzt),
    # statt den GUC zu ueberspringen. _persist_event_ref ueberspringt die Benotung (Event-Stub
    # handling_status != 'pending') -> dieser Test prueft die Flush-/Drain-Mechanik, nicht das Scoring.
    monkeypatch.setattr(sl, '_tenant_id_for_item', lambda item, db: 'tenant-uuid-stub')

    # Ein offenes Arbeits-Item (leichter event_id-Verweis) in die Queue legen.
    sl.slow_lane.put({'event_id': 4711})

    # Simulierter Shutdown-Flush.
    n = sl.flush_to_db()

    # Integration-Assertion (unveraendert): genau 1 Item wurde gedrained ...
    assert n == 1
    # ... und die Queue ist danach leer (kein Rest-Item).
    assert sl.slow_lane.drain() == []
    # A1-Klammer: pro Item eine Read- + eine Schreib-Session (2 get_session-Aufrufe), beide sauber
    # geschlossen (try-finally close, CLAUDE.md Database Patterns).
    assert len(sessions) == 2
    for s in sessions:
        s.close.assert_called_once()
    # Die Schreib-Session (zweite) committet den per-Item-Flush.
    sessions[1].commit.assert_called_once()


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
