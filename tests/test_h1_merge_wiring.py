"""
tests/test_h1_merge_wiring.py
──────────────────────────────────────────────────────────────────────────
Phase 08.23.2.H1 Plan 02 (WEG 1, Welle 2 — MERGE-Verdrahtung)

Runtime-Wiring-Tests (CLAUDE.md Test-Qualitaets-Regel: Function-Call- +
State-Mutation-Assertions, KEIN Source-Presence). Fahren den echten
analyse_loop ueber genau EINEN Tick (_OneShotTrigger-Muster wie
test_medium_lane_intent_event_live) mit gemocktem Haiku und gemockten
DB/intent_event-Naehten — kein Netz, kein Local-Server, keine DB.

Beweist die MERGE-Verdrahtung (Bau-Vorgaben 1/2/5):
  (a) MERGE=1: pro Tick GENAU EIN Merged-Call (analysiere_und_klassifiziere);
      analysiere_mit_claude UND classify_utterance werden NICHT gerufen.
  (b) Guard-Fall (kw_fired_for_line == line_id): keine QA-Konsumtion (kein
      Abstain), ABER die Einwand-Sektion wird trotzdem verarbeitet (intent_event
      feuert) — Einwand-Pfad-Invariante.
  (c) Truncation-Fall (qa_section == {}): Dispatch faellt fail-open
      (smalltalk_none/0.0), kein Crash; Einwand-Sektion voll verarbeitet.
  (d) IL-2-Reihenfolge (W-2, echte Laufzeit-Mechanik): der Dispatch-side_effect
      liest primary_intent IM MOMENT DES AUFRUFS -> beweist, dass der IL-2-Write
      VOR dem Dispatch passierte (kein "am Ende sind beide gesetzt").
  (e) Rollback (MERGE=0): analysiere_mit_claude + classify_utterance werden
      gerufen, analysiere_und_klassifiziere NICHT.
──────────────────────────────────────────────────────────────────────────
"""

import time
import uuid
import unittest
from unittest.mock import MagicMock, patch

import config
import services.claude_service as cs


class _StopLoop(Exception):
    """Sentinel: verlaesst den `while True`-Daemon analyse_loop nach EINEM Tick."""


class _OneShotTrigger:
    """Erster wait() -> True (ein Tick laeuft), zweiter -> _StopLoop. clear() no-op."""

    def __init__(self):
        self._calls = 0

    def wait(self, timeout=None):
        self._calls += 1
        if self._calls > 1:
            raise _StopLoop()
        return True

    def clear(self):
        pass


def _einwand_dict(with_qa=None):
    """Das strukturierte Einwand-JSON (top-level = analysiere_mit_claude-Schema).
    with_qa: None (kein qa-Key), {} (Truncation) oder ein qa-Dict."""
    d = {
        'einwand': True,
        'typ': 'Kosten/Preis',
        'intent_type': 'echter_einwand',
        'confidence': 0.8,
        'intensitaet': 'mittel',
        'einwand_zitat': 'zu teuer',
        'gegenargument_1': 'Ansatz A?',
        'gegenargument_2': 'Ansatz B?',
    }
    if with_qa is not None:
        d['qa'] = with_qa
    return d


def _seed_ls(monkeypatch, sid, line_id=1, kw_fired_for_line=None):
    """Seedet den echten live_session-Modul-State fuer EINEN analyse_loop-Tick und
    stubbt die DB/moment/anon-Naehte hermetisch (kein Netz, keine DB)."""
    import services.live_session as ls

    monkeypatch.setitem(ls._session_state, sid, {
        'user_id': 1,
        'org_id': 1,
        'mode': 'cold_call',
        'kaufbereitschaft': 30,
        'conversation_log': [],
        'gegenargument_log': [],
        'phasen_log': [],
        'covered_phases': set(),
        'state': {
            'is_paused': False,
            'analysiert_bisher': [],
            'current_phase': 2,
            'active_learning_cards': [],
            'call_id': 'call-xyz',
            'kw_fired_for_line': kw_fired_for_line,
            'slot1_variant_busy_until': 0.0,
        },
    })
    monkeypatch.setitem(ls._per_sid_transcript, sid, [
        {'text': 'Das ist mir zu teuer', 'line_id': line_id, 't_start': time.monotonic()},
    ])
    monkeypatch.setattr(ls, 'analyse_trigger', _OneShotTrigger())

    # DB/moment/anon-Naehte stubben (kein Netz, keine DB).
    monkeypatch.setattr(ls, 'get_or_open_moment', MagicMock(return_value='iid-1'), raising=False)
    monkeypatch.setattr(ls, 'close_moment', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, '_durable_call_id', MagicMock(return_value='call-xyz'), raising=False)
    monkeypatch.setattr(ls, 'get_anonymisierer', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, 'update_kaufbereitschaft', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, 'get_profile_for_sid', MagicMock(return_value=('', {})), raising=False)
    return ls


def _run_one_tick():
    with unittest.TestCase().assertRaises(_StopLoop):
        cs.analyse_loop()


class TestMergeWiring(unittest.TestCase):

    def setUp(self):
        # eigenes monkeypatch-Aequivalent via patch.stopall im tearDown
        import _pytest.monkeypatch as _mp
        self._mp = _mp.MonkeyPatch()

    def tearDown(self):
        self._mp.undo()

    # ── (a) EIN Merged-Call pro Tick ─────────────────────────────────────────
    def test_a_merge_one_call_per_tick(self):
        mp = self._mp
        sid = f"wire-{uuid.uuid4().hex[:8]}"
        _seed_ls(mp, sid)
        mp.setattr(config, 'MERGE_ANALYSE_QA', '1')

        mock_merged = MagicMock(return_value=_einwand_dict(with_qa={
            'kategorie': 'smalltalk_none', 'confidence': 0.0, 'einwand_zitat': None}))
        mock_call1 = MagicMock(return_value=_einwand_dict())
        mp.setattr(cs, 'analysiere_und_klassifiziere', mock_merged)
        mp.setattr(cs, 'analysiere_mit_claude', mock_call1)

        with patch('services.qa_pipeline.classify_utterance') as mock_classify, \
             patch('services.intent_event_writer.emit_intent_event') as mock_emit, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            _run_one_tick()

        self.assertEqual(mock_merged.call_count, 1,
                         "Merge-Pfad: analysiere_und_klassifiziere MUSS genau EINMAL pro Tick laufen.")
        self.assertFalse(mock_call1.called,
                         "Merge-Pfad: analysiere_mit_claude (Call 1) darf NICHT laufen.")
        self.assertFalse(mock_classify.called,
                         "Merge-Pfad: classify_utterance (Call 3) darf NICHT laufen — QA kommt aus qa_section.")
        # Einwand-Sektion trotzdem verarbeitet -> intent_event gefeuert
        self.assertTrue(mock_emit.called, "Einwand-Sektion MUSS ein intent_event feuern.")

    # ── (b) Guard gatet nur die QA-Konsumtion, nicht die Einwand-Sektion ─────
    def test_b_guard_gates_qa_but_not_einwand(self):
        mp = self._mp
        sid = f"wire-{uuid.uuid4().hex[:8]}"
        line_id = 7
        # Guard aktiv: kw_fired_for_line == line_id
        _seed_ls(mp, sid, line_id=line_id, kw_fired_for_line=line_id)
        mp.setattr(config, 'MERGE_ANALYSE_QA', '1')

        # qa_section waere sonst ein low-conf 'frage' -> wuerde normalerweise ein
        # Abstain-Event feuern. Der Guard MUSS das unterdruecken.
        mp.setattr(cs, 'analysiere_und_klassifiziere',
                   MagicMock(return_value=_einwand_dict(with_qa={
                       'kategorie': 'frage', 'confidence': 0.1, 'einwand_zitat': 'wie teuer'})))

        with patch('services.qa_pipeline.classify_utterance') as mock_classify, \
             patch('services.intent_event_writer.emit_intent_event') as mock_emit, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            _run_one_tick()

        # QA-Konsum gegated: classify NICHT gerufen, KEIN Abstain-Event
        self.assertFalse(mock_classify.called,
                         "Guard-Fall: classify_utterance darf nicht laufen (Merge-Pfad).")
        abstain_calls = [c for c in mock_emit.call_args_list
                         if c.kwargs.get('abstained')]
        self.assertEqual(abstain_calls, [],
                         "Guard-Fall: KEIN Abstain-Event (QA-Konsum ist gegated).")
        # ABER: Einwand-Sektion trotzdem verarbeitet -> genau EIN Medium-Lane-Emit
        self.assertTrue(mock_emit.called,
                        "Guard gatet nur die QA-Konsumtion — die Einwand-Sektion MUSS feuern.")
        med_calls = [c for c in mock_emit.call_args_list
                     if c.kwargs.get('source') == 'llm_inferred'
                     and not c.kwargs.get('abstained')]
        self.assertEqual(len(med_calls), 1,
                         "Genau EIN Medium-Lane intent_event (Einwand-Pfad-Invariante).")

    # ── (c) Truncation: qa_section == {} -> fail-open, kein Crash ────────────
    def test_c_truncation_qa_empty_fail_open(self):
        mp = self._mp
        sid = f"wire-{uuid.uuid4().hex[:8]}"
        _seed_ls(mp, sid)
        mp.setattr(config, 'MERGE_ANALYSE_QA', '1')

        # Truncation: Merged-Call liefert die Einwand-Sektion, aber qa == {}
        mp.setattr(cs, 'analysiere_und_klassifiziere',
                   MagicMock(return_value=_einwand_dict(with_qa={})))

        with patch('services.qa_pipeline.classify_utterance') as mock_classify, \
             patch('services.intent_event_writer.emit_intent_event') as mock_emit, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            _run_one_tick()   # darf NICHT crashen

        self.assertFalse(mock_classify.called,
                         "Truncation-Fall: kein Fallback-classify_utterance (Merge-Pfad, qa_section ist {}).")
        # Einwand-Sektion voll verarbeitet trotz fehlender QA-Sektion
        self.assertTrue(mock_emit.called,
                        "Truncation der QA-Sektion darf die Einwand-Sektion NICHT killen.")

    # ── (d) IL-2-Reihenfolge: primary_intent steht VOR dem Dispatch ──────────
    def test_d_il2_write_before_dispatch(self):
        mp = self._mp
        sid = f"wire-{uuid.uuid4().hex[:8]}"
        ls = _seed_ls(mp, sid)
        mp.setattr(config, 'MERGE_ANALYSE_QA', '1')

        mp.setattr(cs, 'analysiere_und_klassifiziere',
                   MagicMock(return_value=_einwand_dict(with_qa={
                       'kategorie': 'smalltalk_none', 'confidence': 0.0, 'einwand_zitat': None})))

        captured = {}

        def _dispatch_side_effect(*args, **kwargs):
            # IM MOMENT des Dispatch-Aufrufs den per-SID primary_intent lesen.
            st = (ls._session_state.get(sid) or {}).get('state') or {}
            captured['primary_intent_at_dispatch'] = st.get('primary_intent')
            captured['confidence_at_dispatch'] = st.get('confidence')

        mock_dispatch = MagicMock(side_effect=_dispatch_side_effect)
        mp.setattr(cs, '_qa_pipeline_dispatch', mock_dispatch)

        with patch('services.intent_event_writer.emit_intent_event'):
            _run_one_tick()

        self.assertTrue(mock_dispatch.called, "Dispatch MUSS aufgerufen werden.")
        # Beweis IL-2: primary_intent war beim Dispatch-Aufruf BEREITS gesetzt
        self.assertEqual(captured.get('primary_intent_at_dispatch'), 'echter_einwand',
                         "IL-2-Write (primary_intent) MUSS VOR dem Dispatch-Aufruf passieren.")
        self.assertAlmostEqual(captured.get('confidence_at_dispatch'), 0.8,
                               msg="IL-2-Write (confidence) MUSS VOR dem Dispatch-Aufruf passieren.")
        # Dispatch bekam die qa_section aus dem Merged-Call durchgereicht (nicht None)
        self.assertIsNotNone(mock_dispatch.call_args.kwargs.get('qa_section'),
                             "Merge-Pfad: Dispatch MUSS die qa_section aus dem Merged-Call bekommen.")

    # ── (e) Rollback: MERGE=0 -> Zwei-Call-Pfad ──────────────────────────────
    def test_e_rollback_two_call_path(self):
        mp = self._mp
        sid = f"wire-{uuid.uuid4().hex[:8]}"
        _seed_ls(mp, sid)
        mp.setattr(config, 'MERGE_ANALYSE_QA', '0')

        mock_merged = MagicMock(return_value=_einwand_dict(with_qa={}))
        mock_call1 = MagicMock(return_value=_einwand_dict())
        mp.setattr(cs, 'analysiere_und_klassifiziere', mock_merged)
        mp.setattr(cs, 'analysiere_mit_claude', mock_call1)

        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'smalltalk_none', 'confidence': 0.0,
                                 'einwand_zitat': None}) as mock_classify, \
             patch('services.intent_event_writer.emit_intent_event'), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            _run_one_tick()

        self.assertTrue(mock_call1.called,
                        "Rollback (MERGE=0): analysiere_mit_claude MUSS laufen.")
        self.assertTrue(mock_classify.called,
                        "Rollback (MERGE=0): classify_utterance MUSS laufen (Dispatch-Fallback, qa_section is None).")
        self.assertFalse(mock_merged.called,
                         "Rollback (MERGE=0): analysiere_und_klassifiziere darf NICHT laufen.")


if __name__ == '__main__':
    unittest.main()
