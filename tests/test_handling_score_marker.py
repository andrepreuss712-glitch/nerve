"""TAXO2-Plan 03 — Integration-Assertions fuer die Einwand-Behandlungs-Benotung (Slow Lane).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):
  Task 1: grade_handling (reine Marker-Regeln) liefert 1-3 oder Abstention (None).
  Task 3: _persist_event_ref Statemachine pending->scored/abstained/failed (Mock-Session):
          - score      -> handling_score_numeric gesetzt + handling_status='scored'
          - None        -> handling_score_numeric NULL + handling_status='abstained' + abstain_log-add (F-01)
          - Exception   -> handling_status='failed', KEIN abstain_log, kein Crash (F-05)
          - Tor-1 low   -> handling_status='failed', KEIN abstain_log (D-03, getrennt von Abstention)
          - Idempotenz  -> handling_status != 'pending' wird uebersprungen (F-01)
  Task 4: _requeue_pending legt NUR 'pending'-Events in die Queue; Consumer-Bootstrap ruft es auf.
  Task 5: Hook-/Registrierungs-Schicht (per-Hook-Isolierung im Tick; all-or-nothing im Call-End).

Kein echter Prod-/PG-Write: db-Zugriffe laufen ueber Mock-/Fake-Sessions, Test laeuft DSN-frei.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import services.slow_lane as sl
from services.handling_markers import grade_handling


# ════════════════════════════════════════════════════════════════════════════════════
# Task 1 — grade_handling (reine Funktion, Marker-Regeln)
# ════════════════════════════════════════════════════════════════════════════════════

def test_grade_handling_label_marker_is_three():
    # Label/Spiegeln zuerst, kein sofortiges Gegenargument -> GUT (3).
    utt = "Wenn ich Sie richtig verstehe, ist Ihnen der Preis wichtig?"
    assert grade_handling(None, utt) == 3


def test_grade_handling_immediate_counter_is_one():
    # Sofortiges Wegargumentieren als Eroeffnung, keine Anerkennung -> SCHLECHT (1).
    utt = "Aber unser Produkt ist doch viel guenstiger als die Konkurrenz, glauben Sie mir."
    assert grade_handling(None, utt) == 1


def test_grade_handling_mixed_label_and_counter_is_two():
    # Teils Anerkennung (Label) + sofortiges Gegenargument (Eroeffnung) -> MITTEL (2).
    utt = "Aber verstehe ich richtig dass Sie den Preis meinen, das ist trotzdem fair."
    assert grade_handling(None, utt) == 2


def test_grade_handling_too_short_abstains():
    # Zu kurz/generisch -> grosszuegige Abstention (None), D-07.
    assert grade_handling(None, "Ja gut.") is None


def test_grade_handling_empty_or_none_abstains():
    assert grade_handling(None, None) is None
    assert grade_handling(None, "") is None
    assert grade_handling(None, "   ") is None


def test_grade_handling_unclear_abstains():
    # Weder Anker noch Gegenargument erkennbar -> Abstention (None).
    utt = "Das Wetter heute ist wirklich sehr angenehm und sonnig draussen."
    assert grade_handling(None, utt) is None


def test_grade_handling_triggering_text_mirror_is_three():
    # FOLD B P1: Berater greift den bekannten Ausloeser-Wortlaut auf (Spiegeln) -> GUT (3),
    # auch ohne expliziten Label-Marker.
    utt = "Das Budget ist also aktuell knapp bei Ihnen, das hoere ich."
    trig = "wir haben dafuer aktuell kein Budget eingeplant"
    assert grade_handling(None, utt, triggering_text=trig) == 3


# ════════════════════════════════════════════════════════════════════════════════════
# Task 3 — _persist_event_ref Statemachine (Mock-Session)
# ════════════════════════════════════════════════════════════════════════════════════

def _make_event(**overrides):
    """Leichtgewichtige intent_event-Attrappe (SimpleNamespace) im 'pending'-Zustand."""
    base = dict(
        event_id=4711,
        handling_status='pending',
        handling_score_numeric=None,
        confidence=0.9,
        mode='cold_call',
        intent_type='preis_zu_hoch',
        interaction_id=str(uuid.uuid4()),
        call_id=None,
        timestamp=None,
        payload_jsonb={'triggering_text': None},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _db_returning(ev):
    """Mock-Session, deren query(...).filter(...).first() das Event liefert. add() wird getrackt."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = ev
    return db


def _patch_helpers(monkeypatch, next_utt="Wenn ich Sie richtig verstehe ...", gate=0.70):
    """Neutralisiert die DB-abhaengigen Helfer von _persist_event_ref fuer den Statemachine-Test."""
    monkeypatch.setattr(sl, '_find_next_advisor_utterance', lambda ev, db: next_utt)
    monkeypatch.setattr(sl, '_confidence_gate_for', lambda ev, db: gate)
    monkeypatch.setattr(sl, '_tenant_id_for', lambda ev, db: None)


def test_persist_scored_sets_score_and_status(monkeypatch):
    _patch_helpers(monkeypatch)
    monkeypatch.setattr(sl, 'grade_handling', lambda ev, utt, triggering_text=None: 3)
    ev = _make_event()
    db = _db_returning(ev)

    sl._persist_event_ref({'event_id': 4711}, db)

    assert ev.handling_score_numeric == 3
    assert ev.handling_status == 'scored'
    db.add.assert_not_called()          # kein abstain_log bei score


def test_persist_abstain_writes_abstain_log(monkeypatch):
    _patch_helpers(monkeypatch, next_utt="Das Wetter ist heute schoen.")
    monkeypatch.setattr(sl, 'grade_handling', lambda ev, utt, triggering_text=None: None)
    ev = _make_event()
    db = _db_returning(ev)

    sl._persist_event_ref({'event_id': 4711}, db)

    # F-01: NICHT nur NULL — handling_status='abstained'; handling_score_numeric bleibt NULL.
    assert ev.handling_score_numeric is None
    assert ev.handling_status == 'abstained'
    # Goodhart-Log (D-07 Rider 3): genau eine abstain_log-Zeile mit dem Satz + interaction_id.
    db.add.assert_called_once()
    logged = db.add.call_args[0][0]
    assert isinstance(logged, sl.AbstainLog)
    assert logged.event_id == ev.event_id
    assert logged.interaction_id == ev.interaction_id
    assert logged.next_advisor_sentence == "Das Wetter ist heute schoen."
    assert logged.intent_type == ev.intent_type


def test_persist_poison_pill_sets_failed_no_log(monkeypatch):
    _patch_helpers(monkeypatch)

    def _boom(ev, utt, triggering_text=None):
        raise RuntimeError("Marker-Engine kaputt")
    monkeypatch.setattr(sl, 'grade_handling', _boom)
    ev = _make_event()
    db = _db_returning(ev)

    # Kein Crash (F-05): Exception wird in 'failed' uebersetzt.
    sl._persist_event_ref({'event_id': 4711}, db)

    assert ev.handling_status == 'failed'
    assert ev.handling_score_numeric is None
    db.add.assert_not_called()          # KEIN abstain_log bei Poison-Pill


def test_persist_tor1_low_confidence_sets_failed_no_log(monkeypatch):
    # D-03: confidence < gate -> 'failed' (Ereignis garbage), KEIN abstain_log (Tor 1, nicht Tor 2).
    _patch_helpers(monkeypatch, gate=0.70)
    called = {'graded': False}

    def _grade(ev, utt, triggering_text=None):
        called['graded'] = True
        return 3
    monkeypatch.setattr(sl, 'grade_handling', _grade)
    ev = _make_event(confidence=0.4)
    db = _db_returning(ev)

    sl._persist_event_ref({'event_id': 4711}, db)

    assert ev.handling_status == 'failed'
    assert ev.handling_score_numeric is None
    assert called['graded'] is False    # gar nicht erst benotet
    db.add.assert_not_called()


def test_persist_idempotent_skip_non_pending(monkeypatch):
    # F-01: eine bereits 'abstained' Zeile wird bei Re-Run uebersprungen -> KEIN zweiter abstain_log.
    _patch_helpers(monkeypatch)
    monkeypatch.setattr(sl, 'grade_handling', lambda ev, utt, triggering_text=None: None)
    ev = _make_event(handling_status='abstained')
    db = _db_returning(ev)

    sl._persist_event_ref({'event_id': 4711}, db)

    assert ev.handling_status == 'abstained'   # unveraendert
    db.add.assert_not_called()                 # kein Doppel-Log


def test_persist_missing_row_is_noop(monkeypatch):
    # Zeile nicht (mehr) da -> Loop ueberlebt, kein Crash.
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    sl._persist_event_ref({'event_id': 999}, db)
    db.add.assert_not_called()


# ════════════════════════════════════════════════════════════════════════════════════
# Task 4 — _requeue_pending (H-3 Bootstrap-Re-Queue)
# ════════════════════════════════════════════════════════════════════════════════════

class _FakeQuery:
    """Minimaler Query-Stub: _requeue_pending's EINZIGE filter() ist WHERE handling_status='pending'.
    all() liefert nur die pending-Zeilen als (event_id,)-Tupel — beweist, dass scored/abstained
    NICHT re-enqueued werden."""
    def __init__(self, rows):
        self._rows = list(rows)          # rows: list of (event_id, status)
        self._only_pending = False

    def filter(self, *a, **k):
        self._only_pending = True
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def all(self):
        rows = self._rows
        if self._only_pending:
            rows = [r for r in rows if r[1] == 'pending']
        return [(r[0],) for r in rows]


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def query(self, *a, **k):
        return _FakeQuery(self._rows)

    def close(self):
        self.closed = True


def _fresh_queue(monkeypatch):
    fresh = sl.SlowLaneQueue()
    monkeypatch.setattr(sl, 'slow_lane', fresh)
    return fresh


def test_requeue_pending_enqueues_only_pending(monkeypatch):
    q = _fresh_queue(monkeypatch)
    rows = [(1, 'pending'), (2, 'scored'), (3, 'pending'), (4, 'abstained')]
    session = _FakeSession(rows)
    monkeypatch.setattr(sl, 'get_session', lambda: session)

    n = sl._requeue_pending()

    assert n == 2                                  # nur die 2 pending
    enqueued = q.drain()
    assert {'event_id': 1} in enqueued
    assert {'event_id': 3} in enqueued
    assert {'event_id': 2} not in enqueued         # scored NICHT
    assert {'event_id': 4} not in enqueued         # abstained NICHT
    assert session.closed is True                  # try-finally close


def test_consumer_bootstrap_requeues(monkeypatch):
    # Beweist: slow_lane_consumer ruft _requeue_pending VOR dem Loop (H-3-Bootstrap-Pfad).
    _fresh_queue(monkeypatch)
    calls = {'requeue': 0}
    monkeypatch.setattr(sl, '_requeue_pending', lambda *a, **k: calls.__setitem__('requeue', calls['requeue'] + 1) or 0)
    monkeypatch.setattr(sl, 'get_session', lambda: MagicMock())

    # Sentinel sofort in die Queue -> Loop bricht nach dem Bootstrap sauber ab.
    sl.request_shutdown()
    sl.slow_lane_consumer()

    assert calls['requeue'] == 1


# ════════════════════════════════════════════════════════════════════════════════════
# Task 5 — Hook-/Registrierungs-Schicht
# ════════════════════════════════════════════════════════════════════════════════════

def test_periodic_tick_runs_registered_hooks(monkeypatch):
    # Frische Hook-Liste (Isolation gegen die modul-globale Registry).
    monkeypatch.setattr(sl, '_PERIODIC_TICK_HOOKS', [])
    ran = {'a': False, 'b': False}

    def hook_a():
        ran['a'] = True

    def hook_boom():
        raise RuntimeError("Wartungsjob A kaputt")

    def hook_b():
        ran['b'] = True

    # Reihenfolge: a, dann ein werfender Hook, dann b — b MUSS trotzdem laufen.
    sl.register_periodic_tick_hook(hook_a)
    sl.register_periodic_tick_hook(hook_boom)
    sl.register_periodic_tick_hook(hook_b)

    sl._periodic_tick()                 # darf NICHT crashen (per-Hook try/except)

    assert ran['a'] is True
    assert ran['b'] is True             # ein Hook-Fehler killt die anderen NICHT


def test_call_end_steps_registry_empty_and_callable(monkeypatch):
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [])
    # Leere Liste -> No-Op (Plan 03 registriert hier KEINEN Schritt).
    sl.run_call_end_steps({'call': 'x'})

    seen = {}

    def step(ctx):
        seen['ctx'] = ctx

    sl.register_call_end_step(step)
    sl.run_call_end_steps({'call': 'y'})
    assert seen['ctx'] == {'call': 'y'}


def test_call_end_step_exception_propagates(monkeypatch):
    # ANDERE Semantik als der Tick: ein Schritt-Fehler PROPAGIERT (all-or-nothing pro Call),
    # KEIN per-Schritt swallow. Idempotente UPSERTs -> sauberer Re-Run statt Teil-Schreibung.
    monkeypatch.setattr(sl, '_CALL_END_MERGE_STEPS', [])

    def boom(ctx):
        raise ValueError("Merge-Schritt kaputt")

    sl.register_call_end_step(boom)
    with pytest.raises(ValueError):
        sl.run_call_end_steps({})
