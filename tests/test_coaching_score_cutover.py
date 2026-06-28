"""TAXO2-Plan 04 + Plan 03 — Integration-Assertions fuer den Call-Ende-Merge (Slow Lane, async).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  F-02  Merge feuert NUR wenn Call ended (ended_at IS NOT NULL) UND pending_events==0
        UND audio_health_resolved==True UND transcript_resolved==True (4 Fan-In-Gates).
        - laeuft noch (ended_at None)              -> KEIN rubric_score-Write
        - noch offene 'pending'-Events             -> KEIN rubric_score-Write
        - transcript_resolved=False                -> Merge wartet (Plan-03-Fan-In, Punkt 26)
        - ended + 0 pending + beide resolved       -> Judge-Schritt laeuft (UPSERT)
        - scored/abstained/failed terminal         -> zaehlen NICHT als pending (Merge feuert)

  F-09 GESTRICHEN  Merge braucht KEINE outcome-Vorbedingung (Engine ergebnis-blind).

  F-07/D-09  Audio-Gate VOR dem Judge-Call; high-conf-Events SELBST aus der events-Liste gezaehlt
             (confidence >= Tor-1), NICHT aus dem Engine-Dict.
        - audio_health_score < Schwelle ODER NULL  -> status='not_gradable', KEIN Judge-Call
        - < MIN_HIGH_CONFIDENCE_EVENTS hoch-konf.  -> status='not_gradable', KEIN Judge-Call

  M-4  set_current_tenant(call.tenant_id) VOR dem Write; clear_current_tenant() im finally
       (auch bei Exception — Cross-Tenant-Leak-Schutz). tenant_id NULL -> skip + lautes Log.

  Robustheit  Merge-Fehler -> gedeckelter Re-Queue (attempts+1) bis SCORE_MAX_RETRIES, dann
              Dead-Letter (laut). Call NICHT als erledigt markiert. Daemon stirbt NIE.

  TAXO2-04 Gap-Fix (Audio-Race / Fan-In-Join)  der Merge wartet auf audio_health_resolved==True.
        - resolved=False -> Merge wartet (kein false-poor durch async-Ordering).
        - kein-Buffer (resolved=True + score=None) -> korrekt poor_audio_health (KEIN false-negative).
        - gutes Audio (resolved=True + score>=Schwelle) -> NICHT poor_audio_health (der Live-Bug).

  TAXO2-Plan 03 Cutover  der registrierte Schritt ist jetzt _judge_step (LLM-Bewerter).
        - compute_rubric (Marker-Engine) als Noten-Quelle abgeloest (Punkt 20).
        - _judge_step UPSERTet observations/ratings (NICHT coaching_score/dimensions der Alt-Engine).
        - Compliance-Hard-Gate persists in observations_jsonb['_compliance'] (Finding 2).

Kein echter Prod-/PG-Write: db-Zugriffe laufen ueber Fake-/Mock-Sessions, Test laeuft DSN-frei.
Der scharfe Postgres-Lauf (RLS-fail-closed, echter UPSERT) faellt im deploy.sh-Pytest-Gate an.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import services.slow_lane as sl


# ════════════════════════════════════════════════════════════════════════════════════
# Test-Doubles
# ════════════════════════════════════════════════════════════════════════════════════

def _make_call(**overrides):
    """Leichtgewichtige calls-Row-Attrappe."""
    base = dict(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        call_mode='cold_call',
        ended_at=object(),              # != None -> ended
        conversation_log_id=42,
        audio_health_score=0.9,         # > Schwelle (gutes Audio)
        audio_health_resolved=True,     # TAXO2-04 Fan-In-Join: Audio-Zustand festgeschrieben (Default)
        transcript_resolved=True,       # TAXO2-Plan-03 Fan-In: Transkript festgeschrieben (Punkt 26)
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_event(**overrides):
    base = dict(
        event_id=1, call_id=None, session_id='sid-1',
        intent_type='vorwand', confidence=0.95,
        handling_status='scored', handling_score_numeric=3,
        timestamp=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _MergeFakeSession:
    """Fake-Session fuer _call_end_merge: query(Call).filter().first() -> call;
    _events_for_call/_pending_events werden separat monkeypatcht. execute/commit getrackt."""

    def __init__(self, call):
        self._call = call
        self.committed = False
        self.rolled_back = False
        self.executed = []

    def query(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._call

    def execute(self, stmt):
        self.executed.append(stmt)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def _install_merge_doubles(monkeypatch, call, *, pending=0, events=None,
                           high_conf=5, sessions=None):
    """Verkabelt die DB-Helfer von _call_end_merge mit Fakes. `sessions` ist eine Liste,
    in die jede get_session()-Instanz gepusht wird (Reihenfolge: read_db, write_db)."""
    events = events if events is not None else [_make_event(call_id=call.id)]
    sess_list = sessions if sessions is not None else []

    def _fake_get_session():
        s = _MergeFakeSession(call)
        sess_list.append(s)
        return s

    monkeypatch.setattr(sl, 'get_session', _fake_get_session)
    monkeypatch.setattr(sl, '_pending_events', lambda cid, db: pending)
    monkeypatch.setattr(sl, '_events_for_call', lambda cid, db: events)
    monkeypatch.setattr(sl, '_count_high_confidence', lambda evs, db: high_conf)
    return sess_list


@pytest.fixture
def guc_spy(monkeypatch):
    """Spy auf set/clear_current_tenant in slow_lane — beweist M-4-Reihenfolge + finally-Cleanup."""
    calls = {'set': [], 'clear': 0}
    monkeypatch.setattr(sl, 'set_current_tenant', lambda tid: calls['set'].append(tid))
    monkeypatch.setattr(sl, 'clear_current_tenant', lambda: calls.__setitem__('clear', calls['clear'] + 1))
    return calls


# ════════════════════════════════════════════════════════════════════════════════════
# F-02 — harte Merge-Vorbedingung
# ════════════════════════════════════════════════════════════════════════════════════

def test_merge_does_not_fire_while_call_running(monkeypatch, guc_spy):
    # Call laeuft noch (ended_at None) -> KEIN rubric_score-Write, KEIN GUC gesetzt.
    call = _make_call(ended_at=None)
    sessions = _install_merge_doubles(monkeypatch, call)
    step = MagicMock()
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [step])

    sl._call_end_merge({'call_id': call.id})

    step.assert_not_called()
    assert guc_spy['set'] == []                 # kein Write -> keine GUC


def test_merge_does_not_fire_with_pending_events(monkeypatch, guc_spy):
    # Call ended, aber noch 2 'pending'-Events -> KEIN Merge (transient-WAHR-Schutz).
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=2)
    step = MagicMock()
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [step])

    sl._call_end_merge({'call_id': call.id})

    step.assert_not_called()
    assert guc_spy['set'] == []


def test_merge_fires_when_ended_and_zero_pending(monkeypatch, guc_spy):
    # ended + 0 pending -> der registrierte Call-Ende-Schritt laeuft (ctx korrekt befuellt).
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=0)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS',
                        [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('call') is call
    assert seen.get('not_gradable_reason') is None   # gutes Audio + genug high-conf
    assert guc_spy['set'] == [str(call.tenant_id)]   # M-4: GUC mit call.tenant_id gesetzt
    assert guc_spy['clear'] == 1                      # finally lief


def test_merge_fires_with_terminal_events_only(monkeypatch, guc_spy):
    # 1 abstained + 1 failed + Rest scored -> pending==0 -> Merge feuert (F-01/F-05 terminal).
    call = _make_call()
    events = [
        _make_event(event_id=1, handling_status='scored'),
        _make_event(event_id=2, handling_status='abstained'),
        _make_event(event_id=3, handling_status='failed'),
    ]
    _install_merge_doubles(monkeypatch, call, pending=0, events=events)
    ran = {'n': 0}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: ran.__setitem__('n', ran['n'] + 1)])

    sl._call_end_merge({'call_id': call.id})

    assert ran['n'] == 1


# ════════════════════════════════════════════════════════════════════════════════════
# F-07 / D-09 — Audio-Gate VOR dem Scoring (high-conf aus events-Liste)
# ════════════════════════════════════════════════════════════════════════════════════

def test_audio_gate_null_health_marks_not_gradable(monkeypatch):
    call = _make_call(audio_health_score=None)
    _install_merge_doubles(monkeypatch, call, pending=0)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('not_gradable_reason') == 'poor_audio_health'


def test_audio_gate_low_health_marks_not_gradable(monkeypatch):
    call = _make_call(audio_health_score=0.2)   # < 0.5 Default
    _install_merge_doubles(monkeypatch, call, pending=0)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('not_gradable_reason') == 'poor_audio_health'


def test_too_few_high_confidence_events_marks_not_gradable(monkeypatch):
    # Gutes Audio, aber nur 1 hoch-konfidentes Event (< MIN_HIGH_CONFIDENCE_EVENTS=3).
    call = _make_call(audio_health_score=0.9)
    _install_merge_doubles(monkeypatch, call, pending=0, high_conf=1)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('not_gradable_reason') == 'too_few_high_confidence_events'


def test_count_high_confidence_uses_events_list(monkeypatch):
    # high-conf wird SELBST aus der events-Liste gezaehlt (confidence >= gate), NICHT aus
    # einem Engine-Feld. conf=None zaehlt NICHT.
    monkeypatch.setattr(sl, '_confidence_gate_for', lambda ev, db: 0.70)
    events = [
        _make_event(confidence=0.95),   # zaehlt
        _make_event(confidence=0.80),   # zaehlt
        _make_event(confidence=0.40),   # zu niedrig
        _make_event(confidence=None),   # None -> nicht sicher
    ]
    assert sl._count_high_confidence(events, db=None) == 2


# ════════════════════════════════════════════════════════════════════════════════════
# M-4 — Tenant-GUC + Leak-Schutz
# ════════════════════════════════════════════════════════════════════════════════════

def test_daemon_write_sets_tenant_guc(monkeypatch, guc_spy):
    # set_current_tenant(call.tenant_id) wird VOR dem Schritt gerufen (Spy beweist Reihenfolge).
    call = _make_call()
    order = []
    _install_merge_doubles(monkeypatch, call, pending=0)
    monkeypatch.setattr(sl, 'set_current_tenant', lambda tid: order.append(('set', tid)))
    monkeypatch.setattr(sl, 'clear_current_tenant', lambda: order.append(('clear', None)))
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: order.append(('step', None))])

    sl._call_end_merge({'call_id': call.id})

    assert order[0] == ('set', str(call.tenant_id))   # GUC ZUERST
    assert ('step', None) in order
    assert order[-1] == ('clear', None)               # clear im finally (zuletzt)


def test_daemon_clears_tenant_on_exception(monkeypatch, guc_spy):
    # Wirft der Schritt -> clear_current_tenant() laeuft TROTZDEM (finally), kein Leak.
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=0)

    def _boom(ctx):
        raise RuntimeError("RLS rejected")
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [_boom])
    # Re-Queue-Pfad neutralisieren (sonst put() auf der echten Queue)
    monkeypatch.setattr(sl.slow_lane, 'put', lambda *a, **k: None)

    sl._call_end_merge({'call_id': call.id, 'attempts': 0})

    assert guc_spy['set'] == [str(call.tenant_id)]
    assert guc_spy['clear'] == 1                       # finally lief trotz Exception


def test_merge_skips_when_tenant_id_null(monkeypatch, guc_spy):
    # Alt-Call ohne tenant_id -> KEIN Write, KEINE GUC, kein Crash (lautes Log).
    call = _make_call(tenant_id=None)
    _install_merge_doubles(monkeypatch, call, pending=0)
    step = MagicMock()
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [step])

    sl._call_end_merge({'call_id': call.id})

    step.assert_not_called()
    assert guc_spy['set'] == []


# ════════════════════════════════════════════════════════════════════════════════════
# Robustheit — Retry / Dead-Letter / Daemon-Survival
# ════════════════════════════════════════════════════════════════════════════════════

def test_daemon_write_failure_requeues_with_cap(monkeypatch, guc_spy):
    # Schritt scheitert, attempts < Cap -> Re-Queue mit attempts+1 (KEIN Dead-Letter).
    monkeypatch.setattr('config.SCORE_MAX_RETRIES', 3, raising=False)
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=0)
    requeued = []
    monkeypatch.setattr(sl.slow_lane, 'put', lambda item: requeued.append(item))
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))])

    sl._call_end_merge({'call_id': call.id, 'attempts': 0})

    assert len(requeued) == 1
    assert requeued[0]['attempts'] == 1
    assert requeued[0]['call_id'] == call.id


def test_daemon_write_failure_dead_letters_after_cap(monkeypatch, guc_spy):
    # attempts+1 >= Cap -> KEIN Re-Queue, Dead-Letter (best-effort status='failed').
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=0)
    requeued = []
    monkeypatch.setattr(sl.slow_lane, 'put', lambda item: requeued.append(item))
    marked = {'n': 0}
    monkeypatch.setattr(sl, '_mark_merge_failed', lambda cid, tid: marked.__setitem__('n', marked['n'] + 1))
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))])

    sl._call_end_merge({'call_id': call.id, 'attempts': 2})   # 2+1 == 3 == Cap

    assert requeued == []          # kein Endlos-Re-Queue
    assert marked['n'] == 1        # Dead-Letter-Markierung versucht


def test_daemon_write_failure_not_marked_done(monkeypatch, guc_spy):
    # KEIN Silent-Drop: bei Fehler wird rollback gerufen und der Call NICHT erfolgreich committet.
    call = _make_call()
    sessions = _install_merge_doubles(monkeypatch, call, pending=0)
    monkeypatch.setattr(sl.slow_lane, 'put', lambda *a, **k: None)
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))])

    sl._call_end_merge({'call_id': call.id, 'attempts': 0})

    # write_db (zweite Session: read_db, write_db) wurde zurueckgerollt, nie committet.
    write_db = sessions[-1]
    assert write_db.rolled_back is True
    assert write_db.committed is False


def test_daemon_survives_step_exception(monkeypatch, guc_spy):
    # Eine Exception failt NUR diesen Call — _call_end_merge propagiert sie NICHT
    # (der Consumer-Loop laeuft weiter, Daemon stirbt nie).
    call = _make_call()
    _install_merge_doubles(monkeypatch, call, pending=0)
    monkeypatch.setattr(sl.slow_lane, 'put', lambda *a, **k: None)
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: (_ for _ in ()).throw(RuntimeError("boom"))])

    # Kein Raise nach aussen:
    sl._call_end_merge({'call_id': call.id, 'attempts': 0})


# ════════════════════════════════════════════════════════════════════════════════════
# Registry — _judge_step (LLM-Bewerter) ist eingehaengt (Cutover von _compute_rubric_step)
# TAXO2-Plan 03 Cutover (Punkt 20): _judge_step ersetzt _compute_rubric_step.
# ════════════════════════════════════════════════════════════════════════════════════

def test_compute_rubric_step_registered():
    # TAXO2-Plan 03 CUTOVER: _judge_step ist registriert, NICHT _compute_rubric_step.
    # Der LLM-Bewerter hat die Marker-Engine als Noten-Quelle abgeloest (Punkt 20).
    assert sl._judge_step in sl._CALL_END_MERGE_STEPS
    assert sl._compute_rubric_step not in sl._CALL_END_MERGE_STEPS


def test_compute_rubric_step_not_a_periodic_hook():
    # FOLD 26.06. + Cutover Plan 03: KEIN _periodic_tick-Hook (H-2-Sweep gestrichen, Punkt 20).
    assert sl._judge_step not in sl._PERIODIC_TICK_HOOKS
    assert sl._compute_rubric_step not in sl._PERIODIC_TICK_HOOKS


# ════════════════════════════════════════════════════════════════════════════════════
# _judge_step — UPSERT-Aufruf (TAXO2-Plan 03 Cutover: LLM-Bewerter statt compute_rubric)
# ════════════════════════════════════════════════════════════════════════════════════

def test_compute_step_not_gradable_writes_status_only(monkeypatch):
    # not_gradable_reason gesetzt -> rubric_score-Zeile mit status='not_gradable', KEIN Judge-Call.
    # (Kein LLM auf Muell-Audio — Audio-Gate D-09 bleibt unveraendert.)
    call = _make_call()
    captured = {}
    monkeypatch.setattr(sl, '_upsert_rubric_score',
                        lambda db, **kw: captured.update(kw))
    db = MagicMock()
    ctx = {'call': call, 'events': [], 'db': db, 'not_gradable_reason': 'poor_audio_health'}

    sl._judge_step(ctx)

    assert captured['status'] == 'not_gradable'
    # Kein coaching_score (write-stop, ALT-Spalte) — judge_step setzt ihn nicht mehr
    assert captured.get('coaching_score') is None
    db.commit.assert_called_once()


def test_compute_step_scored_upserts_engine_result(monkeypatch):
    # Normaler Pfad: run_behavior_judge-Ergebnis landet im UPSERT mit observations/ratings.
    # TAXO2-Plan 03 Cutover: compute_rubric NICHT mehr aufgerufen — nur run_behavior_judge.
    import unittest.mock as _mock
    call = _make_call()
    fake_judge_result = {
        'observations_jsonb': {
            'bedarfs_ermittlung': [{'beobachtung': 'Gut.', 'beleg_zitat': 'Wie geht das?'}],
            '_compliance': {'verletzt': False, 'beleg_zitat': ''},
        },
        'ratings_jsonb': {'bedarfs_ermittlung': 'stark'},
        'dimensions_version': 2,
        'status': 'judged',
    }
    captured = {}
    monkeypatch.setattr(sl, '_upsert_rubric_score', lambda db, **kw: captured.update(kw))
    db = MagicMock()
    events = [_make_event(session_id='sid-9', handling_status='scored')]
    ctx = {'call': call, 'events': events, 'db': db, 'not_gradable_reason': None}

    # Patch den lazy-import in _judge_step via services.judge_runner-Modul-Attribut
    with _mock.patch('services.judge_runner.run_behavior_judge', return_value=fake_judge_result):
        sl._judge_step(ctx)

    assert captured['status'] == 'judged'
    assert captured['observations'] == fake_judge_result['observations_jsonb']
    assert captured['ratings'] == fake_judge_result['ratings_jsonb']
    assert captured['dimensions_version'] == 2
    assert captured['session_mode'] == 'cold_call'
    db.commit.assert_called_once()


def test_compute_step_marks_failed_events(monkeypatch):
    # judge_failed: run_behavior_judge gibt status=judge_failed zurueck ->
    # rubric_score.status=judge_failed (kein Crash, idempotenter Re-Run).
    import unittest.mock as _mock
    call = _make_call()
    fake_fail_result = {'status': 'judge_failed', 'error': 'LLM-Timeout'}
    captured = {}
    monkeypatch.setattr(sl, '_upsert_rubric_score', lambda db, **kw: captured.update(kw))
    db = MagicMock()
    events = [_make_event(event_id=1, handling_status='scored')]
    ctx = {'call': call, 'events': events, 'db': db, 'not_gradable_reason': None}

    with _mock.patch('services.judge_runner.run_behavior_judge', return_value=fake_fail_result):
        sl._judge_step(ctx)

    # status=judge_failed geschrieben (Fehler-Mantel)
    assert captured['status'] == 'judge_failed'
    db.commit.assert_called_once()


# ════════════════════════════════════════════════════════════════════════════════════
# TAXO2-04 Gap-Fix — Audio-Race / Fan-In-Join (audio_health_resolved)
#
# Wurzel: der Merge las calls.audio_health_score, BEVOR der async _audio_health_bg-Thread ihn
# schrieb -> NULL -> faelschlich poor_audio_health (live verifiziert: Call mit score=0.93 trug
# trotzdem reason='poor_audio_health'). Fix: ein explizites Fan-In-Join-Flag
# calls.audio_health_resolved; der Merge wartet darauf, bevor er ein NULL-Audio als 'kein Audio' wertet.
# ════════════════════════════════════════════════════════════════════════════════════

def test_merge_waits_for_audio_resolved(monkeypatch, guc_spy):
    # ended + 0 pending, ABER audio_health_resolved=False -> der Merge feuert NICHT (er wartet auf
    # den Audio-Pfad, der resolved=True setzt + re-putet). KEIN GUC, KEIN Schritt — die Race-Wurzel.
    call = _make_call(audio_health_resolved=False)
    _install_merge_doubles(monkeypatch, call, pending=0)
    step = MagicMock()
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [step])

    sl._call_end_merge({'call_id': call.id})

    step.assert_not_called()              # Merge wartet -> kein compute-Schritt
    assert guc_spy['set'] == []           # kein Write -> keine GUC


def test_no_buffer_sets_resolved_true(monkeypatch):
    # Kein-Buffer-Pfad: resolved=True (api_beenden-als-absent) UND audio_health_score=None.
    # Erwartung: das ist KEIN false-negative — ein NULL-Score NACH resolved==True ist korrekt
    # 'wirklich kein Audio' -> poor_audio_health (richtig, nicht faelschlich). Der Merge feuert
    # (resolved erfuellt), das Audio-Gate setzt den korrekten not_gradable_reason.
    call = _make_call(audio_health_resolved=True, audio_health_score=None)
    _install_merge_doubles(monkeypatch, call, pending=0)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('call') is call                              # Merge ist gefeuert (resolved erfuellt)
    assert seen.get('not_gradable_reason') == 'poor_audio_health'  # korrekt, KEIN false-negative


def test_good_audio_not_marked_poor(monkeypatch):
    # Der eigentliche Live-Bug: gutes Audio (>= Schwelle) + resolved==True + genug high-conf
    # -> NICHT poor_audio_health. Vorher las der Merge ein noch-NULL-Audio (Race) und flaggte
    # faelschlich poor_audio_health trotz spaeterem score=0.93.
    call = _make_call(audio_health_resolved=True, audio_health_score=0.93)
    _install_merge_doubles(monkeypatch, call, pending=0, high_conf=5)
    seen = {}
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [lambda ctx: seen.update(ctx)])

    sl._call_end_merge({'call_id': call.id})

    assert seen.get('call') is call                  # Merge gefeuert
    assert seen.get('not_gradable_reason') is None   # gutes Audio -> NICHT poor_audio_health


# ════════════════════════════════════════════════════════════════════════════════════
# TAXO2-Plan 03 — transcript_resolved-Gate (Punkt 26 / Plan-01-Fan-In)
# ════════════════════════════════════════════════════════════════════════════════════

def test_merge_waits_for_transcript_resolved(monkeypatch, guc_spy):
    # ended + 0 pending + audio_resolved=True, ABER transcript_resolved=False ->
    # Merge feuert NICHT (wuerde gegen leeres Transkript bewerten, Punkt 26).
    call = _make_call(transcript_resolved=False)
    _install_merge_doubles(monkeypatch, call, pending=0)
    step = MagicMock()
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [step])

    sl._call_end_merge({'call_id': call.id})

    step.assert_not_called()                 # Merge wartet -> kein Judge-Schritt
    assert guc_spy['set'] == []              # kein Write -> keine GUC


def test_judge_step_skips_on_not_gradable(monkeypatch):
    # not_gradable_reason gesetzt -> status=not_gradable, run_behavior_judge NICHT aufgerufen
    # (kein LLM auf Muell-Audio — Audio-Gate D-09 bleibt unveraendert).
    import unittest.mock as _mock
    call = _make_call()
    captured = {}
    monkeypatch.setattr(sl, '_upsert_rubric_score', lambda db, **kw: captured.update(kw))
    db = MagicMock()
    ctx = {'call': call, 'events': [], 'db': db, 'not_gradable_reason': 'poor_audio_health'}

    with _mock.patch('services.judge_runner.run_behavior_judge') as mock_judge:
        sl._judge_step(ctx)
        mock_judge.assert_not_called()  # kein LLM-Call bei not_gradable

    assert captured['status'] == 'not_gradable'


def test_compliance_persisted_in_observations(monkeypatch):
    # run_behavior_judge gibt observations_jsonb['_compliance']={'verletzt':True,...} zurueck ->
    # _upsert_rubric_score schreibt observations inkl. '_compliance' (Hard-Gate persistiert, Finding 2).
    # ratings_jsonb enthaelt KEIN '_compliance' (kein Mittelwert-Beitrag).
    import unittest.mock as _mock
    call = _make_call()
    fake_judge_result = {
        'observations_jsonb': {
            'bedarfs_ermittlung': [{'beobachtung': 'Schwach.', 'beleg_zitat': 'Gar keine Fragen.'}],
            'gespraechs_eroeffnung': [{'beobachtung': 'OK.', 'beleg_zitat': 'Guten Tag.'}],
            'einwand_behandlung': [{'beobachtung': 'Uebergangen.', 'beleg_zitat': 'Nein danke!'}],
            'gespraechsfuehrung': [{'beobachtung': 'Grenze ueberschritten.', 'beleg_zitat': 'Dreimal Nein.'}],
            '_compliance': {'verletzt': True, 'beleg_zitat': 'Nein danke! Dreimal!'},
        },
        'ratings_jsonb': {
            'bedarfs_ermittlung': 'schwach',
            'gespraechs_eroeffnung': 'ok',
            'einwand_behandlung': 'schwach',
            'gespraechsfuehrung': 'schwach',
        },
        'dimensions_version': 2,
        'status': 'judged',
    }
    captured = {}
    monkeypatch.setattr(sl, '_upsert_rubric_score', lambda db, **kw: captured.update(kw))
    db = MagicMock()
    ctx = {'call': call, 'events': [], 'db': db, 'not_gradable_reason': None}

    with _mock.patch('services.judge_runner.run_behavior_judge', return_value=fake_judge_result):
        sl._judge_step(ctx)

    # Compliance in observations (Hard-Gate persistiert, Finding 2)
    assert '_compliance' in captured['observations'], "'_compliance' fehlt in observations_jsonb"
    assert captured['observations']['_compliance']['verletzt'] is True

    # Compliance NICHT in ratings (Hard-Gate, nicht aufmittelbar)
    assert '_compliance' not in captured['ratings'], "'_compliance' darf NICHT in ratings_jsonb stehen"

    db.commit.assert_called_once()
