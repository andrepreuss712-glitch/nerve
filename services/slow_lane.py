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

from sqlalchemy import text as _sa_text
from sqlalchemy.dialects.postgresql import insert as _pg_insert

from database.db import get_session, set_current_tenant, clear_current_tenant
from database.models import IntentEvent, AbstainLog, Call, TranscriptSegment, ModeWeightConfig, RubricScore
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

    # ── F2-Stilllegung (PERSID Req 8) ───────────────────────────────────────────────
    # Der per-Ereignis-Benoter schreibt keine Leerlauf-Noten mehr (100% abstained/NULL
    # am Prod belegt F2 tot; der LLM-Gesamtbewerter deckt das Urteil ab via Judge).
    # not_gradable = existierender Terminal-Status (:364) -> _pending_events zaehlt es
    # NICHT (nur 'pending' wird gezaehlt) -> drainet auf 0 -> Call-Ende-Merge/rubric_score
    # feuert normal (deadlock-frei). NULL Schema-Change; umgeht auch den RLS-fail-closed-
    # Loop (:262-276); DB-Felder handling_score_numeric/handling_status/abstain_log bleiben.
    ev.handling_status = _STATUS_NOT_GRADABLE
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


# ════════════════════════════════════════════════════════════════════════════════════
# TAXO2-Plan 04 — Call-Ende-Merge (Option B + FOLD 26.06.)
#
# Die Engine rechnet am Call-Ende die rubric_score-Aufschluesselung + Kopf-Zahl und schreibt
# sie ASYNC (Slow Lane, D-10) in die EINZIGE Engine-Schreib-Tabelle: rubric_score (Option B —
# KEIN calls.coaching_score-Write, KEIN outcome in rubric_score). Anstoss = api_beenden
# (slow_lane.put({'call_id': ...})). Harte Vorbedingung F-02: Call ended (ended_at IS NOT NULL)
# UND pending_events(call_id)==0 UND audio_health_resolved==True (TAXO2-04 Fan-In-Join gegen die
# Audio-Race: der Merge wartet, bis der async Audio-Zustand festgeschrieben ist, sonst liest er ein
# noch-nicht-geschriebenes NULL-audio_health_score und flaggt faelschlich poor_audio_health).
# KEINE outcome-Vorbedingung (F-09 gestrichen — Engine
# ergebnis-blind). KEIN H-2-Sweep. M-4-GUC-Klammer (set/clear_current_tenant, finally) um JEDEN
# rubric_score-Write. Audio-Gate D-09 VOR dem Scoring. Retry/Dead-Letter (SCORE_MAX_RETRIES).
# ════════════════════════════════════════════════════════════════════════════════════

# Status-/origin-/Reason-Konstanten (ASCII-Identifier, CLAUDE.md Umlaut-Regel).
_ORIGIN_LIVE = 'live'
_STATUS_SCORED = 'scored'
_STATUS_NOT_GRADABLE = 'not_gradable'
_STATUS_FAILED = 'failed'
_STATUS_JUDGED = 'judged'  # TAXO2-Plan 03: LLM-Bewerter-Ergebnis


def _pending_events(call_id, db) -> int:
    """F-02: Anzahl noch OFFENER Momente eines Calls. Zaehlt NUR handling_status='pending' —
    scored/abstained/failed sind TERMINAL (F-01/F-05, 'failed'-Setzpunkte :236/:248/:267) und
    blockieren den Merge NICHT (sonst drainte pending nie auf 0 bei einem Poison-Pill-Event)."""
    return (db.query(IntentEvent)
              .filter(IntentEvent.call_id == call_id,
                      IntentEvent.handling_status == 'pending')
              .count())


def _events_for_call(call_id, db) -> list:
    """Laedt alle intent_event-Rows eines Calls (Aggregations-Eingang fuer compute_rubric +
    D-09-high-conf-Zaehlung). Read-only; calls/intent_event haben KEINE RLS -> GUC-frei."""
    return (db.query(IntentEvent)
              .filter(IntentEvent.call_id == call_id)
              .order_by(IntentEvent.timestamp.asc())
              .all())


def _count_high_confidence(events, db) -> int:
    """D-09 (F-07, FOLD 26.06.): zaehlt die hoch-konfidenten Events SELBST aus der events-Liste
    (confidence >= Tor-1-Schwelle) — NICHT aus einem compute_rubric-Rueckgabefeld (das Engine-Dict
    fuehrt keine solche Zaehlung). Pro Event wird die Tor-1-Schwelle aus mode_weight_config
    (mode, vorwand_behandlung) gelesen (DEFAULT_CONFIDENCE_GATE-Fallback). confidence=None zaehlt
    NICHT als sicher (Gemini-Skepsis, konsistent zu rubric_engine._sample_size_for)."""
    n = 0
    for ev in (events or []):
        conf = getattr(ev, 'confidence', None)
        if conf is None:
            continue
        gate = _confidence_gate_for(ev, db)
        if conf >= gate:
            n += 1
    return n


def _mode_config_for(mode_key, db) -> dict:
    """Laedt den modus-spezifischen Gewichtssatz aus mode_weight_config als
    {dimension: {weight, enabled, partial_marker, indirekt_erkannt, confidence_gate}} — die
    Form, die compute_rubric (Plan 02) erwartet. Leerer Lookup -> {} (Engine setzt dann
    status='no_weight_set' mit Trace, NICHT still NULL)."""
    out = {}
    if not mode_key:
        return out
    rows = (db.query(ModeWeightConfig)
              .filter(ModeWeightConfig.session_mode == mode_key)
              .all())
    for r in rows:
        out[r.dimension] = {
            'weight': r.weight,
            'enabled': r.enabled,
            'partial_marker': r.partial_marker,
            'indirekt_erkannt': r.indirekt_erkannt,
            'confidence_gate': r.confidence_gate,
        }
    return out


def _upsert_rubric_score(db, *, call_id, conversation_log_id, session_mode, tenant_id,
                         coaching_score=None, is_provisional=False, measured_weight_pct=None,
                         unmeasured_dimensions=None, dimensions=None, status, payload=None,
                         observations=None, ratings=None, dimensions_version=None) -> None:
    """F-03 idempotenter UPSERT in rubric_score (DER EINZIGE Engine-Write, Option B).
    ON CONFLICT (call_id) WHERE origin='live' DO UPDATE — referenziert den partiellen Unique-Index
    ux_rubric_score_live_call_id (Plan 01). KEIN calls.coaching_score-Write, KEIN outcome-Feld
    (FOLD 26.06. — outcome bleibt in calls, die Anzeige-Sperre liest es per Join).

    TAXO2-Plan 03 Erweiterung: observations/ratings/dimensions_version fuer den LLM-Bewerter.
    ALT-Spalten (coaching_score/is_provisional/measured_weight_pct/unmeasured_dimensions/dimensions)
    bleiben als kwargs (write-stop: Werte sind None/falsy, werden nicht mehr befuellt — Punkt 20).
    """
    values = {
        'call_id': call_id,
        'conversation_log_id': conversation_log_id,
        'session_mode': session_mode,
        'origin': _ORIGIN_LIVE,
        # ALT-Spalten (write-stop ab LLM-Bewerter TAXO2 — Punkt 20, Foundation-Register):
        # werden nicht mehr befuellt; bleiben als kwargs fuer Rueckwaerts-Kompatibilitaet.
        'coaching_score': coaching_score,
        'is_provisional': is_provisional,
        'measured_weight_pct': measured_weight_pct,
        'unmeasured_dimensions': unmeasured_dimensions,
        'dimensions': dimensions,
        'status': status,
        'tenant_id': tenant_id,
        'payload_jsonb': payload or {},
        # LLM-Bewerter-Spalten (TAXO2-Plan 03, Migration 0029):
        'observations_jsonb': observations or {},
        'ratings_jsonb': ratings or {},
    }
    if dimensions_version is not None:
        values['score_schema_version'] = dimensions_version

    stmt = _pg_insert(RubricScore.__table__).values(**values)
    update_cols = {k: stmt.excluded[k] for k in (
        'conversation_log_id', 'session_mode', 'coaching_score', 'is_provisional',
        'measured_weight_pct', 'unmeasured_dimensions', 'dimensions', 'status',
        'tenant_id', 'payload_jsonb', 'observations_jsonb', 'ratings_jsonb',
    )}
    if dimensions_version is not None:
        update_cols['score_schema_version'] = stmt.excluded['score_schema_version']
    stmt = stmt.on_conflict_do_update(
        index_elements=['call_id'],
        index_where=_sa_text("origin = 'live'"),
        set_=update_cols,
    )
    db.execute(stmt)


def _bester_befund(zitat, fenster_liste):
    """Bester Befund ueber alle Pruef-Fenster. Rangfolge treffer > near_miss > no_match."""
    from services.beleg_check import beleg_im_transkript

    bester_score, bester_befund = 0.0, 'no_match'
    for fenster in (fenster_liste or []):
        _ok, _score, _befund = beleg_im_transkript(zitat, fenster)
        if _score > bester_score:
            bester_score, bester_befund = _score, _befund
    return bester_befund, bester_score


def _pruefe_belege(observations: dict, pruef_fenster: list) -> tuple:
    """METRIK-1 Req 3: prueft JEDES Beleg-Zitat gegen die Pruef-Fenster, BEVOR es gespeichert wird.

    Drei Wege (SPEC Req 3, services/beleg_check.py liefert genau diese drei Befunde):
      'treffer'   -> Beobachtung uebernehmen.
      'near_miss' -> Beobachtung uebernehmen UND zaehlen (kleine Abweichungen entstehen schon
                     durch die Schwaerzung — [PERSON_A] steht fuer zwei gesprochene Woerter).
      'no_match'  -> die GANZE Beobachtung faellt weg, nicht nur das Zitat.

    Sonderfall '_compliance' (reservierter Schluessel, judge_runner.py:317-323): Bei 'no_match'
    wird NUR das Zitat geleert, das Flag `verletzt` BLEIBT stehen und wird getrennt gezaehlt.
    Begruendung: `_compliance` ist ein Sicherheits-Hard-Gate (L3-Safety). Ein Zitat-Fehler darf
    einen Belaestigungs-Befund nicht verschwinden lassen — das waere die teure Fehlerrichtung.
    Das Sicherheits-Hard-Gate ueberlebt einen Zitat-Fehler.

    Baut das Ergebnis NEU auf (Muster judge_runner._parse_judge_output:293-326), statt am
    LLM-Dict herumzuflicken. Iteriert ueber DIMENSIONS statt ueber observations.keys(), damit
    Unterstrich-Schluessel und unbekannte Keys nicht versehentlich als Dimension durchlaufen.

    Geprueft wird gegen Segment- und Nachbarpaar-Fenster, NICHT gegen den Gesamt-Korpus: ein
    Trennzeichen ueberlebt die Normalisierung in beleg_check nicht (:18-19), und Score B ist
    reihenfolge-blind (:80-86). Gegen den Gesamt-Korpus wuerde deshalb ein Zitat, das Minute 2
    und Minute 10 mischt, als Treffer durchgehen. Die Fenster baut
    transkript_renderer.pruef_fenster (Begruendung und benannte Grenze stehen dort).

    Args:
        observations: observations_jsonb aus run_behavior_judge.
        pruef_fenster: transkript_renderer.pruef_fenster(segments) — Liste von Fenster-Texten.

    Returns:
        (observations_geprueft: dict, zaehler: dict)
        zaehler = {'schema': 1, 'geprueft': int, 'treffer': int, 'near_miss': int,
                   'verworfen': int, 'compliance_beleg_verworfen': int}
    """
    from services.judge_dimensions import DIMENSIONS

    zaehler = {'schema': 1, 'geprueft': 0, 'treffer': 0, 'near_miss': 0,
               'verworfen': 0, 'compliance_beleg_verworfen': 0}
    quelle = observations if isinstance(observations, dict) else {}
    geprueft = {}

    dim_keys = set()
    for dim in DIMENSIONS:
        key = dim['key']
        dim_keys.add(key)
        roh = quelle.get(key)
        neue_liste = []
        if not isinstance(roh, list):
            # Form-Garantie an der Entstehungsstelle (Haltung wie routes/dashboard.py:961-992):
            # eine Nicht-Liste ist kein Container fuer Beobachtungen -> verworfen.
            if roh is not None:
                zaehler['verworfen'] += 1
            geprueft[key] = neue_liste
            continue
        for eintrag in roh:
            if not isinstance(eintrag, dict):
                zaehler['verworfen'] += 1
                continue
            zitat = eintrag.get('beleg_zitat') or ''
            zaehler['geprueft'] += 1
            if not zitat:
                # Leeres Zitat: beleg_check.py:52-53 liefert dafuer ohnehin 'no_match'.
                zaehler['verworfen'] += 1
                continue
            befund, _score = _bester_befund(zitat, pruef_fenster)
            if befund == 'no_match':
                zaehler['verworfen'] += 1
                continue
            if befund == 'near_miss':
                zaehler['near_miss'] += 1
            else:
                zaehler['treffer'] += 1
            neue_liste.append({
                'beobachtung': eintrag.get('beobachtung', ''),
                'beleg_zitat': zitat,
            })
        geprueft[key] = neue_liste

    # ── '_compliance': Flag bleibt, nur das Zitat faellt (Sicherheits-Hard-Gate) ─────────────
    comp = quelle.get('_compliance')
    if isinstance(comp, dict):
        verletzt = bool(comp.get('verletzt', False))
        comp_zitat = comp.get('beleg_zitat') or ''
        neues_zitat = comp_zitat
        if verletzt and comp_zitat:
            zaehler['geprueft'] += 1
            befund, _score = _bester_befund(comp_zitat, pruef_fenster)
            if befund == 'no_match':
                neues_zitat = ''
                zaehler['compliance_beleg_verworfen'] += 1
            elif befund == 'near_miss':
                zaehler['near_miss'] += 1
            else:
                zaehler['treffer'] += 1
        geprueft['_compliance'] = {'verletzt': verletzt, 'beleg_zitat': neues_zitat}
    elif comp is not None:
        geprueft['_compliance'] = comp

    # ── Vorwaerts-Vertraeglichkeit: unbekannte (Unterstrich-)Schluessel unveraendert durch ───
    for key, wert in quelle.items():
        if key in dim_keys or key == '_compliance':
            continue
        geprueft[key] = wert

    return geprueft, zaehler


def _judge_step(ctx) -> None:
    """Registrierter Call-Ende-Schritt (run_call_end_steps): stoesst den LLM-Verhaltens-Judge an
    + UPSERTet observations_jsonb / ratings_jsonb in rubric_score. Laeuft INNERHALB der
    M-4-GUC-Klammer des Merge-Gates (set_current_tenant ist bereits gesetzt -> after_begin
    publiziert app.tenant_id fuer den FORCE-RLS-Write, M-4).

    TAXO2-Plan 03 CUTOVER (Punkt 20): compute_rubric (Marker-Engine) als Noten-Quelle
    abgeloest durch run_behavior_judge (LLM-Bewerter, Soll-Verhalten §6).
    rubric_engine.py bleibt im Baum als Foundation (nicht geloescht — Punkt 20,
    Foundation-Code-Register); kein lebender Noten-Aufruf mehr in slow_lane.py.

    Bau-Regel 1: der Judge laeuft NUR hier (Slow-Lane-Consumer, async) — KEIN LLM in der
    Fast/Live-Lane. Latenz egal (Punkt 25, Slow Lane).

    ctx (vom Merge-Gate gefuellt): {call, events, db, high_conf, not_gradable_reason}.
    """
    from services.judge_runner import run_behavior_judge

    call = ctx['call']
    events = ctx['events']
    db = ctx['db']
    mode_key = call.call_mode  # N-4: QUELLE DER WAHRHEIT = calls.call_mode (NIE session_mode)
    tenant_id = call.tenant_id

    # ── Audio-Gate D-09 (VOR dem Judge-Call): not_gradable speichern+flaggen (Option B: in
    #    rubric_score, NICHT calls). Kein LLM auf Muell-Audio.
    #    Auch dieser Write geht unter Tenant-GUC (M-4 gilt fuer JEDEN rubric_score-Write). ──────
    reason = ctx.get('not_gradable_reason')
    if reason is not None:
        _upsert_rubric_score(
            db,
            call_id=call.id,
            conversation_log_id=call.conversation_log_id,
            session_mode=mode_key,
            tenant_id=tenant_id,
            status=_STATUS_NOT_GRADABLE,
            payload={'reason': reason},
        )
        db.commit()
        return

    # ── LLM-Verhaltens-Judge (run_behavior_judge, Plan 03) ──────────────────────────────────
    # compute_rubric (Marker-Engine) als Noten-Quelle abgeloest (Punkt 20 Cutover).
    # rubric_engine.py + compute_rubric bleiben im Baum als Foundation — kein lebender Aufruf.
    result = run_behavior_judge(call, events, db)

    # ── METRIK-1 Req 3 (D-05): Zitat-Pruefung VOR dem Speichern ──────────────────────────────
    # Der Pruef-Korpus entsteht aus DERSELBEN Segment-Liste und DEMSELBEN EWB-Filter wie der
    # Bewerter-Auftrag (transkript_renderer). Zwei getrennte Renderings wuerden hausgemachte
    # Beinahe-Treffer erzeugen (SPEC NACHTRAG 2 Punkt 8). Die Sortierung ist zeichengleich zu
    # judge_runner.py:370-375 — bewusst, damit derselbe Korpus entsteht.
    from services.transkript_renderer import pruef_fenster
    from services.beleg_check_counter import record_beleg_check

    _segments = (db.query(TranscriptSegment)
                   .filter(TranscriptSegment.conversation_log_id == call.conversation_log_id)
                   .order_by(TranscriptSegment.ts_ms.asc(), TranscriptSegment.id.asc())
                   .all())
    # Geprueft wird gegen Segment- und Nachbarpaar-Fenster, nicht gegen den Gesamt-Korpus
    # (Task 5): ein zusammengesetztes Zitat aus Minute 2 und Minute 10 wuerde sonst durchgehen.
    _fenster = pruef_fenster(_segments)
    _observations, _beleg_zaehler = _pruefe_belege(result.get('observations_jsonb') or {}, _fenster)
    record_beleg_check(_beleg_zaehler)

    # ── UPSERT: Beobachtungen + interne Auspraegung (KEINE Zahl) unter M-4-GUC ──────────────
    # observations_jsonb enthaelt auch den '_compliance'-Hard-Gate-Schluessel (Finding 2).
    # Laeuft unter der bestehenden GUC-Klammer des Merge-Gates (M-4, gesetzt von _call_end_merge).
    #
    # D-23 UPSERT-Semantik: _upsert_rubric_score fuehrt 'payload_jsonb' in update_cols
    # (:473-477) -> der excluded-Wert der Spalte ERSETZT die Zeile vollstaendig. Der Zaehler
    # wird deshalb als ABSOLUTWERT DES LAUFS geschrieben. Ein jsonb-Inkrement waere hier falsch:
    # damit zaehlte ein Wiederholungslauf desselben Anrufs doppelt. "Nicht doppelt zaehlen" ist
    # so per Bauart erfuellt, nicht per Sorgfalt.
    _upsert_rubric_score(
        db,
        call_id=call.id,
        conversation_log_id=call.conversation_log_id,
        session_mode=mode_key,
        tenant_id=tenant_id,
        observations=_observations,
        ratings=result.get('ratings_jsonb') or {},
        dimensions_version=result.get('dimensions_version'),
        status=result.get('status') or _STATUS_JUDGED,
        payload={'beleg_check': _beleg_zaehler},
    )
    db.commit()


# ── Foundation-Code-Register (Punkt 20, Pruning-Notiz 3a/3b) ────────────────────────────
# compute_rubric / rubric_engine.py: Marker-Engine als Noten-Quelle abgeloest durch
# run_behavior_judge (LLM-Bewerter, TAXO2-Plan 03, Soll-Verhalten §6 Cutover Punkt 20).
# rubric_engine.py + die Funktion compute_rubric bleiben UNBERUEHRT im Baum — Foundation-Code
# fuer spaetere Verwendung (z.B. Hybrid-Ansatz, Audit-Vergleich). Kein lebender Noten-Aufruf
# mehr in slow_lane.py (register_call_end_step zeigt auf _judge_step, nicht mehr auf
# _compute_rubric_step). Das models.py ALT-Spalten-Schild (coaching_score etc.) bleibt
# (write-stop, Plan 02) — wird nicht geloescht.
# _compute_rubric_step bleibt als toter Code (NICHT registriert) fuer Cross-Referenz-Suchen.

def _compute_rubric_step(ctx) -> None:
    """TAXO2-Plan 03 CUTOVER: NICHT mehr registriert — abgeloest durch _judge_step.
    Verbleib: toter Code fuer Cross-Referenz (grep-Schutz gegen Verweis-Breakage).
    compute_rubric (Marker-Engine) als Noten-Quelle durch LLM-Bewerter ersetzt (Punkt 20).
    rubric_engine.py bleibt als Foundation im Baum (nicht geloescht, Pruning-Notiz 3a/3b).

    ctx (NICHT mehr aufgerufen): {call, events, db, high_conf, not_gradable_reason}.
    """
    # Toter Code — kein lebender Aufruf mehr (register_call_end_step zeigt auf _judge_step).
    # compute_rubric bleibt als Foundation: from services.rubric_engine import compute_rubric
    raise RuntimeError(
        '_compute_rubric_step ist nicht mehr registriert (TAXO2-Plan 03 Cutover). '
        'Registrierter Schritt: _judge_step.'
    )


def _call_end_merge(item) -> None:
    """Konsumiert ein api_beenden-Anstoss-Item ({'call_id': ..., 'attempts': N}) und fuehrt den
    Call-Ende-Merge aus — MIT harter Vorbedingung (F-02), Audio-Gate (D-09), M-4-GUC-Klammer und
    Retry/Dead-Letter (SCORE_MAX_RETRIES). Ein Fehler failt NUR diesen Call (der Consumer-Loop
    faengt die Exception und der Daemon stirbt nie); der Re-Queue-mit-Cap haengt hier drin.

    Datenfluss: api_beenden -> slow_lane.put({'call_id': ...}) -> Consumer -> _call_end_merge.
    """
    from config import (AUDIO_HEALTH_GATE_THRESHOLD, MIN_HIGH_CONFIDENCE_EVENTS,
                        SCORE_MAX_RETRIES)

    call_id = item.get('call_id') if isinstance(item, dict) else None
    if call_id is None:
        return
    attempts = item.get('attempts', 0) if isinstance(item, dict) else 0

    # ── F-02 Vorbedingung lesen (GUC-frei: calls/intent_event haben KEINE RLS) ──────────────
    read_db = get_session()
    try:
        call = read_db.query(Call).filter(Call.id == call_id).first()
        if call is None:
            return
        # call_status=='ended' == ended_at IS NOT NULL (das Feld, das api_beenden setzt, :696).
        if call.ended_at is None:
            return  # Call laeuft noch -> KEIN vorzeitiger Merge (transient-WAHR-Schutz)
        if _pending_events(call_id, read_db) != 0:
            return  # noch offene Momente -> warten (drainen scored/abstained/failed terminal)
        # ── TAXO2-04 Fan-In-Join (Audio-Race-Fix): der Merge wartet ZUSAETZLICH darauf, dass der
        #    async Audio-Zustand endgueltig festgeschrieben ist (audio_health_resolved==True). VOR
        #    diesem Gate konnte der Merge calls.audio_health_score lesen, BEVOR der _audio_health_bg-
        #    Thread ihn schrieb -> NULL -> faelschlich poor_audio_health. JETZT bedeutet ein NULL-
        #    Score NACH resolved==True korrekt 'wirklich kein Audio'. Den Flag setzt api_beenden
        #    (kein Buffer) ODER der Thread-finally (Buffer da) — beide re-putten danach. ───────────
        if not getattr(call, 'audio_health_resolved', False):
            return  # Audio-Zustand noch nicht festgeschrieben -> warten (Re-Put folgt vom Audio-Pfad)

        # ── TAXO2-Plan 03 Fan-In (Punkt 26 / transcript_resolved): der Judge laeuft ERST,
        #    nachdem api_beenden das Transkript committed hat (transcript_resolved=True).
        #    Ohne dieses Gate koennte der Judge gegen ein noch-leeres transcript_segments lesen.
        #    api_beenden setzt transcript_resolved IMMER True (resolved-als-absent) -> kein Hang.
        #    Jetzt VIER Vorbedingungen: ended + 0 pending + audio_resolved + transcript_resolved.
        if not getattr(call, 'transcript_resolved', False):
            return  # Transkript noch nicht festgeschrieben -> Judge wuerde leer lesen (Punkt 26)

        # ── M-4: tenant_id ZUERST lesen (calls nicht FORCE-RLS), bevor die GUC gesetzt wird ──
        tenant_id = call.tenant_id
        # ── Audio-Gate D-09 (VOR dem Scoring): events laden + high-conf SELBST zaehlen ──────
        events = _events_for_call(call_id, read_db)
        n_high_conf = _count_high_confidence(events, read_db)
        not_gradable_reason = None
        if call.audio_health_score is None or call.audio_health_score < AUDIO_HEALTH_GATE_THRESHOLD:
            not_gradable_reason = 'poor_audio_health'
        elif n_high_conf < MIN_HIGH_CONFIDENCE_EVENTS:
            not_gradable_reason = 'too_few_high_confidence_events'
    finally:
        read_db.close()

    if tenant_id is None:
        # Alt-Call ohne Tenant -> der FORCE-RLS-Write wuerde fail-closed abgelehnt. LAUT loggen,
        # kein stiller Abbruch, kein Re-Queue (Re-Queue wuerde ewig scheitern -> Dead-Letter-Spam).
        print(f"[SLOW] merge skip call={call_id}: tenant_id NULL (Alt-Call ohne Tenant) — kein rubric_score-Write")
        return

    # ── M-4 GUC-Klammer (KRITISCH gegen FORCE-RLS-fail-closed + Cross-Tenant-Leak) ──────────
    # set_current_tenant VOR dem Txn-Begin der Schreib-Session (after_begin liest den contextvar).
    # clear_current_tenant() ZWINGEND im finally: der Endlos-Daemon-Thread leakt sonst nach einer
    # Exception die tenant_id in die naechste Iteration -> Cross-Tenant-Write.
    set_current_tenant(str(tenant_id))
    write_db = get_session()
    try:
        # frische, GUC-gebundene Schreib-Session (after_begin set_config app.tenant_id bei TX-Begin)
        call_w = write_db.query(Call).filter(Call.id == call_id).first()
        events_w = _events_for_call(call_id, write_db)
        ctx = {
            'call': call_w,
            'events': events_w,
            'db': write_db,
            'high_conf': n_high_conf,
            'not_gradable_reason': not_gradable_reason,
            'results': {},
        }
        # Eigener Schritt via Registry (Plan 06/07 registrieren spaeter EBENSO).
        run_call_end_steps(ctx)
        # optional SocketIO 'score_ready' (Display-Mechanik = 999.2; hier nur der Punkt) — NACH commit
    except Exception as e:
        write_db.rollback()
        # M-4-VERSCHAERFUNG: RLS/permission-denied/IntegrityError/compute_rubric-Fehler -> der Call
        # wird NICHT als erledigt markiert. Gedeckelter Re-Queue (attempts+1) bis SCORE_MAX_RETRIES,
        # danach Dead-Letter (laut, Job aus der Queue). KEIN Silent-Drop, KEIN Endlos-Block.
        next_attempt = attempts + 1
        if next_attempt >= SCORE_MAX_RETRIES:
            print(f"[SLOW] DEAD-LETTER call={call_id} after {next_attempt} attempts: {type(e).__name__}: {e}")
            # Best-effort: rubric_score.status='failed' markieren (eigene GUC-Klammer-Session).
            _mark_merge_failed(call_id, tenant_id)
        else:
            print(f"[SLOW] merge failed call={call_id} attempt={next_attempt}/{SCORE_MAX_RETRIES}: {type(e).__name__}: {e}")
            slow_lane.put({'call_id': call_id, 'attempts': next_attempt})
        # Propagiert NICHT weiter — _call_end_merge hat den Fehler isoliert behandelt; der
        # Consumer-Loop laeuft sauber weiter (Daemon ueberlebt).
    finally:
        clear_current_tenant()  # LAEUFT IMMER — auch bei Exception (Cross-Tenant-Leak-Schutz)
        write_db.close()


def _mark_merge_failed(call_id, tenant_id) -> None:
    """Dead-Letter best-effort: rubric_score-Zeile mit status='failed' schreiben (das Vorschau-Panel
    zeigt dann 'Berechnung fehlgeschlagen'). Eigene M-4-GUC-Klammer; Fehler hier wird nur geloggt
    (kein Re-Throw — der Call ist bereits Dead-Letter)."""
    if tenant_id is None:
        return
    set_current_tenant(str(tenant_id))
    db = get_session()
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        if call is None:
            return
        _upsert_rubric_score(
            db,
            call_id=call.id,
            conversation_log_id=call.conversation_log_id,
            session_mode=call.call_mode,
            tenant_id=tenant_id,
            coaching_score=None,
            is_provisional=False,
            measured_weight_pct=None,
            unmeasured_dimensions=None,
            dimensions=None,
            status=_STATUS_FAILED,
            payload={'reason': 'dead_letter'},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[SLOW] dead-letter status-write failed call={call_id}: {type(e).__name__}: {e}")
    finally:
        clear_current_tenant()
        db.close()


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
    # (Plan 04: compute_rubric->rubric_score ist MODUL-INTERN registriert, s.u. am Datei-Ende
    #  register_call_end_step(_compute_rubric_step) — laeuft beim Import von slow_lane selbst,
    #  also keine Import-Falle. compute_rubric/get_speech_stats werden lazy im Schritt importiert.)
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
        # ── TAXO2-Plan 04: Call-Ende-Anstoss ({'call_id': ...}) -> Merge-Gate (F-02/M-4/D-09) ──
        # api_beenden legt {'call_id': ...} ab (Scoring-Anstoss, FOLD 26.06.). _call_end_merge
        # isoliert seine Fehler selbst (Retry/Dead-Letter), darum hier nur ein Schutz-Klammer
        # gegen unerwartete Exceptions (Daemon ueberlebt IMMER — pro-Item-Isolierung).
        if isinstance(item, dict) and 'call_id' in item:
            try:
                _call_end_merge(item)
            except Exception as e:
                print(f"[SLOW] call-end merge unexpected error call={item.get('call_id')}: {type(e).__name__}: {e}")
            continue
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
        _persisted_call_id = None
        try:
            _persist_event_ref(item, db)
            db.commit()           # TAXO2: die In-Place-Benotung persistieren (TAXO1 war No-Op)
            # TAXO2-Plan 04 (F-02-Trigger): merke die call_id des gerade benoteten Events, um
            # NACH dem commit zu pruefen, ob dieses Event das LETZTE offene war (pending->0) und
            # der Call bereits ended ist -> dann den Merge anstossen. Schliesst die Ordering-Race:
            # api_beenden kann VOR dem letzten Event ankommen (sah dann pending!=0, kein Merge) ->
            # ohne dieses Re-Enqueue feuerte der Merge nie (KEIN H-2-Sweep deckt das ab).
            _ev_row = (db.query(IntentEvent.call_id)
                         .filter(IntentEvent.event_id == (item.get('event_id') if isinstance(item, dict) else None))
                         .first())
            _persisted_call_id = _ev_row[0] if _ev_row else None
        except Exception as e:
            db.rollback()         # Zeile bleibt 'pending' -> H-3 re-queued sie spaeter
            print(f"[SLOW] consumer error: {e}")
        finally:
            clear_current_tenant()  # Thread-Reuse-Hygiene (analog app.py:2134-2138), IMMER
            db.close()

        # ── F-02 Trigger-nach-Event: war das das letzte offene Event eines ended Calls? ──────
        if _persisted_call_id is not None:
            _check_db = get_session()
            try:
                _c = _check_db.query(Call).filter(Call.id == _persisted_call_id).first()
                if (_c is not None and _c.ended_at is not None
                        and _pending_events(_persisted_call_id, _check_db) == 0):
                    slow_lane.put({'call_id': _persisted_call_id})
            except Exception as e:
                print(f"[SLOW] post-persist merge-check error call={_persisted_call_id}: {type(e).__name__}: {e}")
            finally:
                _check_db.close()


def request_shutdown() -> None:
    """Legt das Sentinel in die Queue → der Consumer flusht offene Items und stoppt sauber.
    Vom atexit-/SIGTERM-Hook genutzt (Bau-Regel 2)."""
    slow_lane.put(SENTINEL)


# ── H-3 als erster periodischer Tick-Hook registrieren (Task 4 via Task-5-Registry) ──
register_periodic_tick_hook(_requeue_pending_safety_net)

# ── TAXO2-Plan 03 CUTOVER: run_behavior_judge->rubric_score als Call-Ende-Schritt registrieren ──
# Cutover von compute_rubric (Marker-Engine, Punkt 20) auf _judge_step (LLM-Bewerter, Plan 03).
# _compute_rubric_step ist NOT MORE registriert — sie bleibt als toter Code fuer grep-Schutz.
# Der Merge-Gate + M-4-GUC-Klammer + Retry/Dead-Letter sitzen in _call_end_merge (Consumer-Pfad),
# das run_call_end_steps INNERHALB der GUC-Klammer ruft. Bau-Regel 1: der Judge laeuft nur hier.
register_call_end_step(_judge_step)


# ── TAXO2-Plan 04: Uebernahme-/Adoption-Call als zweiter Call-Ende-Schritt registrieren ─────────
# SEPARATER Schritt NACH dem Verhaltens-Judge (_judge_step): der Adoption-Judge kennt die
# NERVE-Vorschlaege (suggestion_reactions.suggestion_text), der Verhaltens-Judge NICHT
# (Bias-Schutz, Soll-Verhalten §6). Beide laufen in DERSELBEN M-4-GUC-Klammer (ctx).
# Reihenfolge: _judge_step zuerst (Verhalten), _adoption_step danach (Uebernahme) —
# unabhaengig voneinander, stabile Reihenfolge erleichtert Debugging.
# Bau-Regel 1: kein LLM in der Fast/Live-Lane. Dieser Schritt laeuft NUR hier (async,
# Slow-Lane-Consumer, post-call).

def _adoption_step(ctx) -> None:
    """Registrierter Call-Ende-Schritt (run_call_end_steps): stoesst den Uebernahme-/Adoption-
    Judge an + schreibt adoption_value / reaction_class / following_utterance_ref in
    suggestion_reactions (DEFERRED-Spalten, jetzt befuellt). Laeuft INNERHALB der M-4-GUC-Klammer
    des Merge-Gates (set_current_tenant ist bereits gesetzt -> FORCE-RLS-Write valide, M-4).

    Audio-Gate D-09 konsistent: kein Adoption-Call auf not_gradable Audio (Muell-Audio = keine
    Vorschlaege sinnvoll bewertbar — konsistent mit _judge_step).

    ctx (vom Merge-Gate gefuellt): {call, events, db, high_conf, not_gradable_reason}.
    """
    from services.adoption_runner import run_adoption_judge

    call = ctx['call']
    db = ctx['db']

    # ── Audio-Gate D-09 (VOR dem Adoption-Call): kein LLM auf Muell-Audio ───────────────────
    reason = ctx.get('not_gradable_reason')
    if reason is not None:
        call_id = getattr(call, 'id', '?')
        print(f'[ADOPTION] skip call={call_id}: not_gradable ({reason}) — kein Adoption-Call auf Muell-Audio')
        return

    # ── Uebernahme-Judge (run_adoption_judge, Plan 04) ────────────────────────────────────────
    run_adoption_judge(call, db)
    db.commit()


register_call_end_step(_adoption_step)
