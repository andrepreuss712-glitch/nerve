"""Slow Lane — die dritte Geschwindigkeits-Bahn (Phase 08.23.2.TAXO1 Geruest, TAXO2-Plan 03).

Async, OFF dem kritischen Pfad: eine adapter-gekapselte Warteschlange + EIN Daemon-Consumer
+ Graceful-Shutdown-Flush. TAXO2 (Plan 03) macht die Bahn ECHT + benotend: der Consumer liest
offene intent_event-Zeilen (`WHERE handling_status='pending'`), wendet regel-/marker-basierte
Anker-Regeln (services/handling_markers.py) auf die naechste Berater-Aussage an und schreibt
`handling_score_numeric` 1-3 IN-PLACE — mit grosszuegiger Abstention. LLM-Verhaltens-Urteil
laeuft NUR hier (async, post-call), NIE auf Fast/Medium Lane (Bau-Regel 1, Zirkelschluss-Schutz).

Drei harte Bau-Regeln (NERVE TAXO-Geruest, verriegelt §5):
  Bau-Regel 1: intent_event ist nach Erzeugung read-only fuer die Live-Bahnen (Fast/Medium).
    Die einzige Schreibstelle der Live-Bahnen bleibt `emit_intent_event` (INSERT-only). Die
    Slow Lane ist der EINZIGE In-Place-Schreiber von handling_score_numeric/handling_status
    (race-frei: kein Live-Leser von intent_event, ORM-aware grep-Gate Task 0 / F-04; 1 Consumer-
    Thread). §8.7-ENGE-Abweichung: pro-EVENT-Note in-place (statt separatem Objekt) — die
    pro-CALL-Note (rubric_score) ist das von §8.7 verlangte separate Objekt.
  Bau-Regel 2: Graceful-Shutdown drained die Queue beim sauberen Stop (atexit + SIGTERM). Die
    Sicherung ist die durable intent_event-Zeile: die Queue traegt nur event_id-Verweise, die
    Arbeits-Liste ist aus der DB re-derivierbar (`WHERE handling_status='pending'`).

Statemachine handling_status (TAXO2-Wurzel-Fix gegen die dreifach-ueberladene NULL, F-01/F-05/F-06):
  'pending'   = noch nicht verarbeitet (= Arbeitsliste; ersetzt "handling_score_numeric IS NULL")
  'scored'    = handling_score_numeric (1-3) gesetzt
  'abstained' = bewusst abgewinkt (D-07; score bleibt NULL, abstain_log geschrieben) — ABGESCHLOSSEN
  'failed'    = dauerhaft nicht bewertbar (Tor-1-Garbage ODER Poison-Pill F-05; score NULL) — ABGESCHLOSSEN
Der Call-Ende-Merge (Plan 04) zaehlt NUR 'pending' als offen.

Multi-Worker-Vorsorge (F-06, NICHT gebaut — Foundation-Register, Anti-Abrieb): die Arbeitsliste
ist `WHERE handling_status='pending'`. Aktivierung Block M via
`SELECT ... WHERE handling_status='pending' FOR UPDATE SKIP LOCKED`. JETZT 1 Consumer-Thread,
KEIN SKIP LOCKED gebaut.

Hook-/Registrierungs-Schicht (FOLD 23.06., Plan 03 Task 5): zwei Modul-Listen
(_PERIODIC_TICK_HOOKS / _CALL_END_MERGE_STEPS) + register-/run-Funktionen. Plan 04/06/07
HAENGEN sich nur ein (append), statt _periodic_tick / den Merge je neu zu schreiben. H-3
(Re-Queue-Bootstrap) ist der erste Tick-Hook. Die Call-End-Step-Liste ist hier LEER (Plan 04
baut den Merge-Gate + GUC-Klammer drumherum und ruft run_call_end_steps darin).
"""

import queue

from database.db import get_session, set_current_tenant, clear_current_tenant
from database.models import IntentEvent, AbstainLog, Call, TranscriptSegment, ModeWeightConfig
from services.handling_markers import grade_handling


# ── Stop-Signal ──────────────────────────────────────────────────────────────────
# Modul-Singleton-Sentinel: ein eindeutiges Objekt, das den Consumer sauber stoppt.
SENTINEL = object()

# ── Periodischer Tick-Takt (§0.1) ─────────────────────────────────────────────────
# Sekunden zwischen zwei Ticks bei leerer Queue. get(timeout=...) schlaeft dazwischen —
# kein Busy-Loop, kein CPU-Fresser.
SLOW_LANE_TICK = 5.0

# ── Tor-1-Konfidenz-Default (D-03) ─────────────────────────────────────────────────
# Fallback, wenn mode_weight_config.confidence_gate fuer (mode, vorwand_behandlung) NULL ist.
DEFAULT_CONFIDENCE_GATE = 0.70
HANDLING_DIMENSION = 'vorwand_behandlung'

# ── H-3 Re-Queue-Drossel ────────────────────────────────────────────────────────────
# Der Bootstrap-Aufruf (Consumer-Start) ist immer voll. Der periodische Safety-Net ist
# gedrosselt (Queue-Bloat-Schutz): nur alle N Ticks UND nur wenn die Queue leer ist.
_REQUEUE_LIMIT = 500
_REQUEUE_EVERY_N_TICKS = 6        # ~30s bei SLOW_LANE_TICK=5.0
_tick_count = 0


# ── Hook-/Registrierungs-Schicht (FOLD 23.06., Task 5 — minimal: 2 Listen + 3 Funktionen) ──
# Spaetere Plaene (04/06/07) HAENGEN sich nur ein (append), statt _periodic_tick / den Merge
# neu zu schreiben. KEINE Prioritaeten/Klassen/Dependency-Graphen (kein Over-Engineering).
_PERIODIC_TICK_HOOKS: list = []
_CALL_END_MERGE_STEPS: list = []


def register_periodic_tick_hook(fn) -> None:
    """Registriert eine periodische Wartungs-Funktion (wird bei jedem Tick gerufen)."""
    _PERIODIC_TICK_HOOKS.append(fn)


def register_call_end_step(fn) -> None:
    """Registriert einen Call-Ende-Schritt (Plan 04/06/07 haengen hier compute_rubric /
    Schatten-Vergleich / Aggregat-Write ein). Schritte laufen in Registrierungs-Reihenfolge."""
    _CALL_END_MERGE_STEPS.append(fn)


def run_call_end_steps(ctx) -> None:
    """Fuehrt alle registrierten Call-Ende-Schritte der Reihe nach mit gemeinsamem ctx aus.

    ANDERE Fehler-Semantik als _periodic_tick (FOLD 23.06., Gemini — KRITISCH): KEIN per-Schritt
    try/except. Ein Schritt-Fehler PROPAGIERT — innerhalb EINES Calls ist all-or-nothing korrekt
    (die rubric_score-/Aggregat-UPSERTs sind idempotent, ein Re-Run laeuft sauber neu; ein
    Teil-Erfolg = halb-geschriebene Note ist schlimmer als ein sauberer Re-Run). Die PRO-CALL-
    Isolierung (ein fehlerhafter Call darf die Schleife fuer ANDERE Calls nicht abreissen) liegt
    im Consumer/Merge-Gate (Plan 04), NICHT hier.

    ctx: leichtes dict/Objekt (call, events, speech_stats, db, results) — Plan 04 fuellt es.
    In dieser Welle ist _CALL_END_MERGE_STEPS LEER -> No-Op.
    """
    for step in _CALL_END_MERGE_STEPS:
        step(ctx)


class SlowLaneQueue:
    """Adapter-gekapselte Slow-Lane-Queue (Bau-Regel 2, Geruest §5). Default queue.Queue;
    Redis-Impl spaeter ohne Interface-Umbau."""

    def __init__(self):
        self._q = queue.Queue()

    def put(self, event_ref) -> None:
        """Legt einen leichten Verweis ab (event_ref = {'event_id': eid}). KEINE
        intent_event-Mutation — nur ein Arbeits-Signal auf eine schon-durable DB-Zeile."""
        self._q.put(event_ref)

    def drain(self) -> list:
        """Zieht alle aktuell vorhandenen Items non-blocking heraus (fuer den Flush).
        Sentinel-Items werden ausgefiltert (Stop-Signale, keine Arbeit)."""
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

    def qsize(self) -> int:
        """Best-effort Groesse (Queue-Bloat-Drossel des H-3-Safety-Net). queue.Queue.qsize()
        ist auf manchen Plattformen approximativ — fuer eine Drossel ausreichend."""
        return self._q.qsize()


# ── Modul-Singleton ────────────────────────────────────────────────────────────────
slow_lane = SlowLaneQueue()


# ── Tor-1-Konfidenz-Schwelle (D-03, garbage-in-Schutz) ──────────────────────────────
def _confidence_gate_for(ev, db) -> float:
    """Liest die Tor-1-Konfidenzschwelle aus mode_weight_config (mode, vorwand_behandlung).
    NULL/fehlt -> DEFAULT_CONFIDENCE_GATE (0.70). Best-effort (kein Crash bei DB-Fehler)."""
    try:
        cfg = (db.query(ModeWeightConfig)
                 .filter(ModeWeightConfig.session_mode == ev.mode,
                         ModeWeightConfig.dimension == HANDLING_DIMENSION)
                 .first())
        if cfg is not None and cfg.confidence_gate is not None:
            return float(cfg.confidence_gate)
    except Exception:
        pass
    return DEFAULT_CONFIDENCE_GATE


def _tenant_id_for(ev, db):
    """Best-effort Mandanten-ID des Events (aus dem Call). None, wenn nicht ermittelbar."""
    try:
        if not ev.call_id:
            return None
        c = db.query(Call).filter(Call.id == ev.call_id).first()
        return getattr(c, 'tenant_id', None) if c is not None else None
    except Exception:
        return None


def _tenant_id_for_item(item, db):
    """TENANT-FOUND Plan 03 (A1): Tenant eines Queue-Items (dict {'event_id': eid}) ueber den
    Call ermitteln — read-only, GUC-frei (calls/intent_event haben KEINE RLS). Laedt das Event
    zum event_id und delegiert an _tenant_id_for. None, wenn nicht ermittelbar."""
    try:
        eid = item.get('event_id') if isinstance(item, dict) else None
        if eid is None:
            return None
        ev = db.query(IntentEvent).filter(IntentEvent.event_id == eid).first()
        return _tenant_id_for(ev, db) if ev is not None else None
    except Exception:
        return None


def _find_next_advisor_utterance(ev, db):
    """Best-effort: die naechste Berater-Aussage NACH diesem Einwand.

    Quelle: transcript_segments (anonymisiert, Pipeline B) des zugehoerigen conversation_log.
    Naht: intent_event.call_id -> calls.id -> calls.conversation_log_id -> transcript_segments.
    Anker = ev.timestamp (wall-clock) gegen transcript_segments.created_at; intra-Call-Reihenfolge
    via ts_ms. GROSSZUEGIGE ABSTENTION (D-07): findet sich keine verlaessliche Folge-Aussage
    (kein call_id, kein conversation_log, kein Berater-Segment) -> None. grade_handling abstainiert
    dann (lieber keine Note als eine falsche).
    """
    try:
        if not ev.call_id:
            return None
        call = db.query(Call).filter(Call.id == ev.call_id).first()
        if call is None or not call.conversation_log_id:
            return None
        seg = (db.query(TranscriptSegment)
                 .filter(TranscriptSegment.conversation_log_id == call.conversation_log_id,
                         TranscriptSegment.speaker == 'berater',
                         TranscriptSegment.created_at >= ev.timestamp)
                 .order_by(TranscriptSegment.created_at.asc())
                 .first())
        return seg.text if seg is not None else None
    except Exception:
        return None


def _persist_event_ref(event_ref, db) -> None:
    """TAXO2: echt + benotend. Ersetzt den TAXO1-No-Op. Statemachine pending->scored/abstained/
    failed mit In-Place-UPDATE. KEIN commit hier (Consumer/flush committen, TAXO1-Vertrag).

    Idempotenz (F-01): nur Zeilen mit handling_status='pending' werden verarbeitet — scored/
    abstained/failed werden NICHT neu verarbeitet (kein doppelter abstain_log bei Consumer-Restart).
    """
    eid = event_ref.get('event_id') if isinstance(event_ref, dict) else None
    if eid is None:
        return
    ev = db.query(IntentEvent).filter(IntentEvent.event_id == eid).first()
    if ev is None:
        return
    # ── Idempotenz-Skip (F-01): nur 'pending' verarbeiten ───────────────────────────
    if ev.handling_status != 'pending':
        return

    # ── Tor-1-Konfidenz (D-03): garbage-in-Schutz, GETRENNT von Abstention ──────────
    # Niedrig-Konfidenz = Ereignis fragwuerdig -> 'failed' (NICHT 'abstained', KEIN abstain_log;
    # das ist Tor 1, nicht Tor 2). confidence None -> kein Signal -> NICHT failen (D-07
    # grosszuegig; grade_handling abstainiert spaeter, falls die Behandlung unklar ist).
    gate = _confidence_gate_for(ev, db)
    if ev.confidence is not None and ev.confidence < gate:
        ev.handling_status = 'failed'
        return

    # ── Benotung in der Poison-Pill-Klammer (F-05) ──────────────────────────────────
    try:
        next_utt = _find_next_advisor_utterance(ev, db)
        triggering_text = (ev.payload_jsonb or {}).get('triggering_text')
        score = grade_handling(ev, next_utt, triggering_text=triggering_text)
    except Exception as e:
        # Dauerhaft nicht bewertbar -> 'failed' (blockiert den Call-Ende-Merge NICHT;
        # Plan 04 zaehlt 'failed' nicht als offen). Call mit "N Events nicht bewertbar"-Marker
        # trotzdem benotbar (D-09-not_gradable-Philosophie konsistent).
        ev.handling_status = 'failed'
        print(f"[SLOW] grade failed event_id={eid}: {type(e).__name__}: {e}")
        return

    if score in (1, 2, 3):
        # Erfolg: In-Place-UPDATE (race-frei per Task 0).
        ev.handling_score_numeric = score
        ev.handling_status = 'scored'
    else:
        # Abstention (Tor 2, D-07): score None -> handling_score_numeric bleibt NULL;
        # handling_status='abstained' (F-01: NICHT nur NULL!) + Goodhart-Log (D-07 Rider 3).
        # ── CALLID-Backstop (CI-4, primaeres Netz): Tenant/call_id MUSS aufloesbar sein, sonst
        #    scheitert der abstain_log-INSERT gegen FORCE RLS fail-closed (RESEARCH §4) -> rollback
        #    -> 'pending' bleibt -> H-3 re-queued ENDLOS. Nach Plan 01/02 darf das praktisch nie
        #    feuern; tut es das, ist es Race/Regression -> TERMINAL 'failed' (aus der pending-
        #    Arbeitsliste raus, F-01: H-3 re-queued nur 'pending') + LAUTER Alarm, KEIN abstain_log
        #    (kein fail-closed-Crash), KEIN 'pending' (kein stiller Verlust, kein Endlos-Loop).
        _bk_tenant = _tenant_id_for(ev, db)
        if _bk_tenant is None:
            ev.handling_status = 'failed'
            print(
                f"[CALLID-ALARM] slow-lane: tenant/call_id nicht ermittelbar fuer "
                f"event_id={ev.event_id} (call_id={ev.call_id!r}) -> 'failed' "
                f"(Race/Regression NACH dem Fix — untersuchen). Kein abstain_log, kein Re-Queue."
            )
            return
        ev.handling_status = 'abstained'
        db.add(AbstainLog(
            event_id=ev.event_id,
            interaction_id=ev.interaction_id,
            next_advisor_sentence=next_utt,
            intent_type=ev.intent_type,
            tenant_id=_bk_tenant,
        ))


def _requeue_pending(limit=_REQUEUE_LIMIT) -> int:
    """H-3 Bootstrap-Re-Queue: re-derived die Arbeitsliste aus der DB
    (`WHERE handling_status='pending'`) und legt event_id-Verweise in die Queue.

    Noetig, weil nach Crash/Deploy/`systemctl restart` der Consumer mit LEERER Queue startet:
    der Producer (emit_intent_event) feuert slow_lane.put() nur fuer NEUE Erkennungen — er fuellt
    die vor dem Restart geschriebenen pending-Events NICHT nach. Ohne Re-Queue bleiben sie fuer
    immer 'pending' liegen -> ihr Call haengt ewig "wird ausgewertet…" (Plan-04-Merge feuert nie).

    Idempotent (KRITISCH gegen Queue-Bloat): weil _persist_event_ref Zeilen mit
    handling_status != 'pending' skippt, ist ein doppelt einge-queuetes Event harmlos.
    """
    db = get_session()
    n = 0
    try:
        rows = (db.query(IntentEvent.event_id)
                  .filter(IntentEvent.handling_status == 'pending')
                  .order_by(IntentEvent.timestamp.asc())
                  .limit(limit)
                  .all())
        for row in rows:
            eid = row[0]
            slow_lane.put({'event_id': eid})
            n += 1
    finally:
        db.close()
    print(f"[SLOW] requeue_pending: {n} re-enqueued")
    return n


def _requeue_pending_safety_net() -> None:
    """Periodischer Safety-Net-Hook (H-3): faengt Events, die NACH dem Bootstrap pending wurden
    aber deren put() verloren ging (Producer-Crash zwischen DB-Write und put). Gedrosselt gegen
    Queue-Bloat: nur alle N Ticks UND nur wenn die Queue (nahezu) leer ist. Registriert via
    register_periodic_tick_hook (NICHT hart im Tick-Body — Task 5)."""
    global _tick_count
    _tick_count += 1
    if _tick_count % _REQUEUE_EVERY_N_TICKS != 0:
        return
    try:
        if slow_lane.qsize() > 0:
            return  # noch Arbeit in der Queue -> kein Nachfuellen noetig
    except Exception:
        pass
    _requeue_pending()


def _periodic_tick() -> None:
    """PERIODISCHE TIMER-KOMPONENTE (§0.1): iteriert die registrierten Tick-Hooks. Ein Hook-Fehler
    darf den Tick + die ANDEREN Hooks NICHT killen (Verfuegbarkeits-Schutz) -> per-Hook try/except.
    H-3 (_requeue_pending_safety_net) ist registriert; Plan 04 haengt H-2-Sweep + M-4-GUC genauso
    ein (register_periodic_tick_hook), ohne diesen Body neu zu schreiben."""
    for hook in _PERIODIC_TICK_HOOKS:
        try:
            hook()
        except Exception as e:
            print(f"[SLOW] periodic hook {getattr(hook, '__name__', '?')} failed: {type(e).__name__}: {e}")


def flush_to_db() -> int:
    """Shutdown-Hook (atexit + SIGTERM): drained offene Queue-Items und benotet sie durch den
    Persist-Pfad. Gibt die Anzahl gedrainter Items zurueck.

    Selbst wenn flush_to_db NICHT laeuft (SIGKILL/OOM), geht nichts verloren — die event_ids
    verweisen auf schon-durable intent_event-Zeilen und sind aus der DB re-derivierbar
    (`WHERE handling_status='pending'`, H-3-Bootstrap beim naechsten Start).
    """
    items = slow_lane.drain()
    flushed = 0
    for it in items:
        # ── A1-Klammer PRO ITEM (CI-5, symmetrisch zum Consumer-Loop slow_lane_consumer):
        #    Tenant in SEPARATER read-only Session ermitteln (calls/intent_event haben KEINE RLS
        #    -> GUC-frei), Session SCHLIESSEN, GUC setzen, DANN die committende Schreib-Session
        #    oeffnen -> after_begin (db.py) liest den contextvar bei TX-Begin. OHNE diese Klammer
        #    wuerde der abstain_log-INSERT beim SIGTERM/atexit-Flush gegen FORCE RLS fail-closed
        #    abgewiesen (RESEARCH §5: bisherige Asymmetrie zum Consumer-Loop) — auch bei gueltiger
        #    call_id. Per-Item-TX (KEIN Sammel-Commit ueber Tenant-Grenzen).
        _tid = None
        _read_db = get_session()
        try:
            _tid = _tenant_id_for_item(it, _read_db)
        finally:
            _read_db.close()

        if _tid is not None:
            set_current_tenant(str(_tid))

        db = get_session()
        try:
            _persist_event_ref(it, db)
            db.commit()
            flushed += 1
        except Exception as e:
            db.rollback()
            # Per-Item-Fehler-Isolierung + EXPLIZITES Log (Gemini-Review-Fund 3): ein Item killt
            # den Flush der ANDEREN NICHT, aber der Fehlschlag darf im Shutdown-Log nicht still
            # verschwinden (kein `except: pass`) — sonst verdeckt er den erfolgreichen Flush der uebrigen.
            _eid = it.get('event_id') if isinstance(it, dict) else getattr(it, 'event_id', None)
            print(f"[SLOW] flush_to_db item-Fehler event_id={_eid}: {e!r} — uebersprungen, Flush laeuft weiter")
        finally:
            clear_current_tenant()  # Thread-Reuse-Hygiene (analog Consumer-Loop), IMMER
            db.close()
    print(f"[SLOW] flush_to_db: {len(items)} items drained, {flushed} persisted")
    return len(items)


def slow_lane_consumer() -> None:
    """Daemon-Consumer-Loop, timeout-getaktet (§0.1). Bei leerer Queue: _periodic_tick (Hooks).
    Bei einem Item: _persist_event_ref + commit (TAXO2 In-Place-Benotung). Sentinel stoppt sauber.
    Einzelfehler ueberleben den Loop (pro-Item-Isolierung: ein fehlerhaftes Event reisst die
    Schleife fuer ANDERE Events nicht ab)."""
    # ── Hook-Import-Block (Task 5, IMPORT-FALLE schliessen) ──────────────────────────
    # Die register_*-Aufrufe von Plan 04/06/07 laufen NUR, wenn deren Module beim Daemon-Start
    # importiert werden — sonst bleibt die Registry LAUTLOS leer (kein Schritt laeuft). Plan
    # 04/06/07 ergaenzen hier ihren Import. In Plan 03 ist der Block leer/vorbereitet (H-3 ist
    # modul-intern bereits registriert, s.u.).
    # (Plan 04: import services.rubric_engine  # registriert compute_rubric -> rubric_score)
    # (Plan 06: import services.shadow_aggregate  # registriert Schatten-Vergleich)
    # (Plan 07: import services.aggregate_writer  # registriert Aggregat-Write)

    # ── Start-Beleg-Log (Pflicht): eine leere Registry ist sofort in inspect.sh logs sichtbar
    #    (statt still). Erwartet 0 in Plan 03; >0 sobald Plan 04+ deployed (sonst Import-Falle).
    print(f"[SLOW] call-end-steps registriert: {len(_CALL_END_MERGE_STEPS)} | "
          f"periodic-hooks: {len(_PERIODIC_TICK_HOOKS)}")

    # ── H-3 Bootstrap-Re-Queue (vor dem Loop): pending-Events nach Restart nachfuellen ──
    try:
        _requeue_pending()
    except Exception as e:
        print(f"[SLOW] bootstrap requeue failed: {type(e).__name__}: {e}")

    while True:
        try:
            item = slow_lane.get(timeout=SLOW_LANE_TICK)
        except queue.Empty:
            _periodic_tick()      # Hook-Liste (H-3 Safety-Net; Plan 04 H-2/M-4)
            continue
        if item is SENTINEL:
            flush_to_db()
            break
        # ── A1 (TENANT-FOUND Plan 03, GELOCKT): Tenant in SEPARATER read-only Session ermitteln ──
        # (calls/intent_event haben KEINE RLS -> GUC-frei lesbar), Session SCHLIESSEN, GUC setzen,
        # DANN die committende Schreib-Session oeffnen -> after_begin (db.py:73-89) liest den
        # contextvar bei TX-Begin der Schreib-Session. KEIN db.rollback() zur TX-Steuerung (das
        # waere A2, verworfen — Cross-AI MEDIUM #2). abstain_log (FORCE RLS, Plan 02) braucht den
        # GUC; sonst weist WITH CHECK den INSERT fail-closed ab (M-4). Latenz: Slow Lane, Punkt 25.
        _tid = None
        _read_db = get_session()
        try:
            _tid = _tenant_id_for_item(item, _read_db)   # GUC-freier Lookup ueber calls.tenant_id
        finally:
            _read_db.close()                             # Read-Session zu, BEVOR set_current_tenant

        if _tid is not None:
            set_current_tenant(str(_tid))                # contextvar VOR der Schreib-TX

        db = get_session()        # committende Schreib-Session — after_begin liest den GUC bei TX-Begin
        try:
            _persist_event_ref(item, db)
            db.commit()           # TAXO2: die In-Place-Benotung persistieren (TAXO1 war No-Op)
        except Exception as e:
            db.rollback()         # Zeile bleibt 'pending' -> H-3 re-queued sie spaeter
            print(f"[SLOW] consumer error: {e}")
        finally:
            clear_current_tenant()  # Thread-Reuse-Hygiene (analog app.py:2134-2138), IMMER
            db.close()


def request_shutdown() -> None:
    """Legt das Sentinel in die Queue → der Consumer flusht offene Items und stoppt sauber.
    Vom atexit-/SIGTERM-Hook genutzt (Bau-Regel 2)."""
    slow_lane.put(SENTINEL)


# ── H-3 als erster periodischer Tick-Hook registrieren (Task 4 via Task-5-Registry) ──
# Plan 04 registriert H-2-Sweep + M-4-GUC genauso (register_periodic_tick_hook), ohne
# _periodic_tick neu zu schreiben.
register_periodic_tick_hook(_requeue_pending_safety_net)
