"""
tests/test_medium_lane_intent_event_live.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.TAXO1.MEDFIX — Netz-Ratsche (Punkt 20, MEDFIX-3).

Integration-Assertion (CLAUDE.md Test-Qualitaets-Regel): beweist, dass aus dem
LIVE-DISPATCH (analyse_loop Medium-Lane-Block) heraus — mit einem gemockten
Haiku-Einwand-JSON — eine echte intent_event-Zeile in nerve_test landet. KEIN
isolierter emit_intent_event-Unit-Test (den deckt test_intent_event_writer.py ab);
KEIN Source-Presence. Diese Luecke (Tests gruen != live geschrieben) liess den
Welle-4-Cutover-Defekt (intent_event leer) durch.

Plus eine reine Function-Call-Assertion (MEDFIX-1): analysiere_mit_claude nutzt
nach dem Wurzel-Fix SYSTEM_PROMPT_BASE (JSON-Einwand-Schema) als System-Prompt
und liefert wieder ein strukturiertes dict statt {} — der Haiku-Call ist hier
gemockt (kein Netz, kein Local-Dev-Verstoss).

Server-seitig via pytest gegen REAL-PG nerve_test. Sauberer Skip wenn DSN fehlt
(db_session-Fixture skippt -> kein False-Green). KEIN live/perf-Marker: laeuft im
Default-Gate (`triage.sh tests/ -m "not live and not perf"`) mit.
Committende Tests raeumen ihre Rows via cleanup_rows weg (Baseline-Sauberkeit,
Phase 08.23.2.PGTEST).
"""

import time
import uuid

import pytest

from database.models import IntentEvent


class _StopLoop(Exception):
    """Sentinel, um den `while True`-Daemon analyse_loop nach genau EINEM Tick zu
    verlassen. Wird aus dem one-shot analyse_trigger.wait() geworfen — analyse_loop
    umschliesst wait() mit KEINEM try, also propagiert die Exception sauber heraus."""


class _OneShotTrigger:
    """Ersetzt ls.analyse_trigger: erster wait() -> True (ein Tick laeuft durch),
    zweiter wait() -> _StopLoop (Schleife endet). clear() ist no-op."""

    def __init__(self):
        self._calls = 0

    def wait(self, timeout=None):
        self._calls += 1
        if self._calls > 1:
            raise _StopLoop()
        return True

    def clear(self):
        pass


def _sid():
    return f"test-medlane-{uuid.uuid4().hex[:12]}"


def _seed_call(db):
    """calls-Row = FK-Ziel fuer intent_event.call_id (NOT NULL ab CALLID Deploy 2 / Migration 0025).
    Der Medium-Lane-Dispatch liest call_id aus dem gehaltenen state -> die Naht braucht eine echte
    calls.id + call_id im State (wie nach create_call_for_sid auf dem Produktiv-Pfad)."""
    from datetime import datetime, timezone
    from database.models import Call
    cid = str(uuid.uuid4())
    db.add(Call(id=cid, user_id=1, call_mode='cold_call',
                started_at=datetime.now(timezone.utc), transcript_storage='none'))
    db.commit()
    return cid


def test_analysiere_uses_classification_schema_returns_structured_dict(monkeypatch):
    """MEDFIX-1 (Wurzel-Fix, reine Function-Call-Assertion, kein DB/Netz):
    analysiere_mit_claude reicht SYSTEM_PROMPT_BASE (JSON-Einwand-Schema) als
    System-Prompt an die Claude-API durch — NICHT den EWB-ANTWORT-Prompt — und
    liefert ein strukturiertes dict mit 'einwand'. Der API-Call ist gemockt."""
    import services.claude_service as cs

    captured = {}

    class _Block:
        text = ('{"einwand": true, "typ": "Kosten/Preis", '
                '"intent_type": "echter_einwand", "confidence": 0.8, '
                '"intensitaet": "mittel", "einwand_zitat": "zu teuer"}')

    class _FakeMsg:
        content = [_Block()]
        usage = None

    class _FakeMessages:
        def create(self, *, model, max_tokens, system, messages, **kwargs):
            # SOFORT-2: **kwargs, weil die Live-Aufrufe seit D-03 zusaetzlich ein
            # timeout=httpx.Timeout(...) uebergeben. Ohne diese Ergaenzung stirbt der Fake an
            # TypeError: create() got an unexpected keyword argument 'timeout'.
            captured['system'] = system
            return _FakeMsg()

    class _FakeClient:
        messages = _FakeMessages()

        def with_options(self, *args, **kwargs):
            return self

    # Den ganzen Client ersetzen -> robust, egal ob der echte Client (API-Key) init ist.
    monkeypatch.setattr(cs, 'claude_client', _FakeClient())

    out = cs.analysiere_mit_claude("Das ist mir ehrlich zu teuer", "", sid=None)

    assert isinstance(out, dict)
    assert out.get('einwand') is True
    assert out.get('intent_type') == 'echter_einwand'

    # Wurzel-Fix-Beweis: der Klassifikations-System-Prompt IST SYSTEM_PROMPT_BASE
    # (System kann String sein ODER cached-list mit cache_control).
    sys_arg = captured['system']
    sys_text = sys_arg if isinstance(sys_arg, str) else sys_arg[0]['text']
    assert sys_text == cs.SYSTEM_PROMPT_BASE
    assert 'Antworte IMMER als valides JSON' in sys_text


def test_medium_lane_live_dispatch_writes_intent_event(db_session, monkeypatch):
    """MEDFIX-3 (Netz-Ratsche): ein analyse_loop-Tick mit gemocktem Haiku-Einwand
    schreibt aus dem Medium-Lane-Block heraus eine intent_event-Zeile in nerve_test.
    Beweist den Emit AUS dem Dispatch (nicht emit_intent_event isoliert)."""
    import services.claude_service as cs
    import services.live_session as ls

    sid = _sid()
    # intent_event.call_id ist NOT NULL ab Deploy 2 (0025): echte calls-Row + call_id im State,
    # damit der Dispatch (_durable_call_id(state['call_id'])) eine gueltige call_id durchreicht.
    cid = _seed_call(db_session)

    # 1. Haiku-Klassifikation mocken: das strukturierte Einwand-JSON, das
    #    SYSTEM_PROMPT_BASE nach dem Wurzel-Fix liefert (Plan-sanktioniert).
    def _fake_analyse(neuer_text, kontext, sid=None):
        return {
            'einwand': True,
            'typ': 'Kosten/Preis',
            'intent_type': 'echter_einwand',
            'confidence': 0.8,
            'intensitaet': 'mittel',
            'einwand_zitat': 'zu teuer',
            'gegenargument_1': 'Antwort-Ansatz A.',
            'gegenargument_2': 'Antwort-Ansatz B.',
        }

    monkeypatch.setattr(cs, 'analysiere_mit_claude', _fake_analyse)
    # H1 (2026-07-22): der Default-Merge-Pfad (MERGE_ANALYSE_QA='1') ruft
    # analysiere_und_klassifiziere, NICHT mehr analysiere_mit_claude. Ohne diesen
    # zweiten Mock liefe hier ein realer (leerer) Haiku-Call -> kein Einwand -> kein
    # intent_event (0>=1). Stale-Contract-Retarget: beide Pfade auf dasselbe Fake
    # (die Einwand-Sektion ist top-level identisch; der Merge nutzt zusaetzlich .get('qa')).
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere', _fake_analyse)
    # Downstream-Helfer (NACH dem Emit) hermetisch stubben — kein Netz/QA-Pipeline.
    monkeypatch.setattr(cs, '_qa_pipeline_dispatch', lambda *a, **k: None)

    # 2. Per-SID-State + Transcript-Puffer + echter cold_call-Modus aufsetzen.
    monkeypatch.setitem(ls._session_state, sid, {
        'user_id': 1,
        'org_id': 1,
        'mode': 'cold_call',
        'state': {
            'is_paused': False,
            'analysiert_bisher': [],
            'current_phase': 2,
            'active_learning_cards': [],
            'call_id': cid,   # durable call_id (wie nach create_call_for_sid) -> Dispatch reicht sie durch
        },
    })
    monkeypatch.setitem(ls._per_sid_transcript, sid, [
        {'text': 'Das ist mir zu teuer', 'line_id': 1, 't_start': time.monotonic()},
    ])
    # TAXO1-07: globales _session_modes geloescht — der cold_call/meeting-Modus lebt
    # jetzt per-SID (oben in _session_state[sid]['mode']='cold_call'). Kein Mock noetig.

    # 3. Daemon-Schleife auf genau EINEN Tick begrenzen.
    monkeypatch.setattr(ls, 'analyse_trigger', _OneShotTrigger())

    # 4. Live-Dispatch fahren (ein Tick), dann sauber raus.
    with pytest.raises(_StopLoop):
        cs.analyse_loop()

    # 5. Assertion: eine intent_event-Zeile fuer diesen sid AUS dem Dispatch.
    db_session.rollback()  # frischer READ-COMMITTED-Snapshot fuer den emit-Commit
    rows = db_session.query(IntentEvent).filter(
        IntentEvent.session_id == sid).all()
    eids = [r.event_id for r in rows]
    try:
        assert len(rows) >= 1, "kein intent_event aus dem Medium-Lane-Dispatch geschrieben"
        row = rows[0]
        assert row.intent_type == 'echter_einwand'
        assert row.mode == 'cold_call'
        assert row.phase == 2
        assert str(row.call_id) == cid  # Dispatch reicht die durable call_id durch (NOT NULL, CI-1)
        assert (row.payload_jsonb or {}).get('source') == 'llm_inferred'
        assert row.interaction_id is not None  # Moment-Fenster vom Dispatch geoeffnet
    finally:
        from tests.conftest import cleanup_rows
        cleanup_rows(db_session, {"public.intent_event": eids, "public.calls": [cid]})
