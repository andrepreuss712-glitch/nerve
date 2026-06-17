"""Slow Lane — die dritte Geschwindigkeits-Bahn (Phase 08.23.2.TAXO1, REQ 3, Geruest §5).

Async, OFF dem kritischen Pfad: eine adapter-gekapselte Warteschlange + EIN Daemon-Consumer
+ Graceful-Shutdown-Flush. In TAXO1 laeuft die Bahn LEER (kein Producer angebunden) und
benotet NICHTS — Scoring/Anreicherung sind TAXO2.

Drei harte Bau-Regeln (NERVE TAXO-Geruest, verriegelt §5):
  Bau-Regel 1: intent_event ist nach Erzeugung read-only fuer die Live-Bahnen. Die Slow Lane
    schreibt KEINE neue intent_event-Zeile und mutiert KEINE bestehende. In TAXO1 ist
    `_persist_event_ref` ein echter No-Op — die einzige Schreibstelle bleibt `emit_intent_event`
    (Plan 04). Das Scoring arbeitet in TAXO2 auf einem separaten Score-Objekt.
  Bau-Regel 2: Graceful-Shutdown drained die Queue beim sauberen Stop (atexit + SIGTERM). Das
    ist eine Optimierung fuer den haeufigen deploy.sh-Restart, KEINE Daten-Sicherung. Die
    Sicherung ist die durable intent_event-Zeile (Design-Block §0): die Queue traegt nur
    event_id-Verweise, die Arbeits-Liste ist aus der DB re-derivierbar
    (`SELECT id FROM intent_event WHERE handling_status='pending'`, INTERLOCK I-3).

Struktur-Einsicht §0.1: der Consumer-Loop ist timeout-getaktet (`get(timeout=SLOW_LANE_TICK)`)
mit einem `_periodic_tick()`-No-Op-Haken — die periodische Timer-Komponente, an die TAXO2 den
Sweep (H-2), das Re-Queue-Bootstrap (H-3) und das tenant_id-GUC (M-4) ohne Re-Architektur
haengt. In TAXO1 nur Struktur, Verhalten leer.
"""

import queue

from database.db import get_session


# ── Stop-Signal ──────────────────────────────────────────────────────────────────
# Modul-Singleton-Sentinel: ein eindeutiges Objekt, das den Consumer sauber stoppt.
SENTINEL = object()

# ── Periodischer Tick-Takt (§0.1) ─────────────────────────────────────────────────
# Sekunden zwischen zwei No-Op-Ticks bei leerer Queue. get(timeout=...) schlaeft
# dazwischen — kein Busy-Loop, kein CPU-Fresser.
SLOW_LANE_TICK = 5.0


class SlowLaneQueue:
    """Adapter-gekapselte Slow-Lane-Queue (Bau-Regel 2, Geruest §5). Default queue.Queue;
    Redis-Impl spaeter ohne Interface-Umbau. In TAXO1: konsumiert + persistiert, KEIN Scoring
    (TAXO2)."""

    def __init__(self):
        self._q = queue.Queue()

    def put(self, event_ref) -> None:
        """Legt einen leichten Verweis ab (event_ref = z.B. {'event_id': eid}). KEINE
        intent_event-Mutation — nur ein Arbeits-Signal auf eine schon-durable DB-Zeile."""
        self._q.put(event_ref)

    def drain(self) -> list:
        """Zieht alle aktuell vorhandenen Items non-blocking heraus (fuer den Flush).
        Sentinel-Items werden ausgefiltert (sie sind Stop-Signale, keine Arbeit)."""
        items = []
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            if item is SENTINEL:
                continue
            items.append(item)
        return items

    def get(self, timeout=None):
        """Pass-through fuer den Consumer-Loop: blocking get mit optionalem timeout.
        Wirft queue.Empty bei Timeout (vom Consumer als periodischer Tick gefangen)."""
        return self._q.get(timeout=timeout)


# ── Modul-Singleton ────────────────────────────────────────────────────────────────
slow_lane = SlowLaneQueue()


def _periodic_tick() -> None:
    # PERIODISCHE TIMER-KOMPONENTE: No-Op in TAXO1 — TAXO2 haengt hier Sweep (H-2) /
    # Re-Queue-Bootstrap (H-3) / tenant_id-GUC (M-4) an. KEINE Sweep-/DB-Logik hier.
    pass


def _persist_event_ref(event_ref, db) -> None:
    # SLOW LANE: No-Op in TAXO1 — intent_event ist durabel von emit_intent_event geschrieben;
    # Anreicherung/Scoring erst TAXO2 (separates Score-Objekt). KEIN INSERT/UPDATE auf
    # intent_event hier. event_ref ist nur ein Verweis (z.B. {'event_id': eid}); die Struktur
    # existiert, damit Welle 4 / TAXO2 ohne Interface-Umbau andocken.
    pass


def flush_to_db() -> int:
    """Shutdown-Hook (atexit + SIGTERM): drained offene Queue-Items und reicht sie durch den
    Persist-Pfad (in TAXO1 No-Op). Gibt die Anzahl gedrainter Items zurueck.

    Wichtig (Design §0): Selbst wenn flush_to_db NICHT laeuft (SIGKILL/OOM), geht nichts
    Wertvolles verloren — die event_ids verweisen auf schon-durable intent_event-Zeilen und
    sind aus der DB re-derivierbar (`WHERE handling_status='pending'`). Der Flush ist
    Optimierung, keine Daten-Garantie.
    """
    items = slow_lane.drain()
    db = get_session()
    try:
        for it in items:
            _persist_event_ref(it, db)  # No-Op in TAXO1
        db.commit()  # in TAXO1 effektiv no-op (kein DB-Write); Struktur fuer Welle 4
    finally:
        db.close()
    print(f"[SLOW] flush_to_db: {len(items)} items drained")
    return len(items)


def slow_lane_consumer() -> None:
    """Daemon-Consumer-Loop, timeout-getaktet (§0.1 — die periodische Timer-Komponente).

    Bei leerer Queue wacht der Loop alle SLOW_LANE_TICK Sekunden und ruft `_periodic_tick()`
    (No-Op in TAXO1; in TAXO2 das Herzstueck fuer H-2/H-3/M-4). Bei einem Item: normaler
    `_persist_event_ref` (No-Op in TAXO1). Sentinel stoppt den Loop sauber.
    Kein Busy-Loop (get schlaeft bis Item ODER Timeout); Einzelfehler ueberleben den Loop.
    """
    while True:
        try:
            item = slow_lane.get(timeout=SLOW_LANE_TICK)
        except queue.Empty:
            _periodic_tick()      # No-Op in TAXO1; TAXO2 haengt Sweep/Re-Queue/GUC an
            continue
        if item is SENTINEL:
            flush_to_db()
            break
        db = get_session()
        try:
            _persist_event_ref(item, db)   # No-Op in TAXO1
        except Exception as e:
            print(f"[SLOW] consumer error: {e}")   # Loop ueberlebt Einzelfehler
        finally:
            db.close()


def request_shutdown() -> None:
    """Legt das Sentinel in die Queue → der Consumer flusht offene Items und stoppt sauber.
    Vom atexit-/SIGTERM-Hook genutzt (Bau-Regel 2)."""
    slow_lane.put(SENTINEL)
