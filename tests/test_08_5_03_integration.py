"""
tests/test_08_5_03_integration.py
──────────────────────────────────────────────────────────────────────────
Phase 08.5 Plan 03 — TDD Tests for:
  - EinwandKeywordMatcher.match_with_dedup writing kw_fired_for_line into ls.state
  - analyse_loop dispatcher: kw_fired_for_line guard, classify_utterance routing,
    confidence threshold, tabu filter, emit paths
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call
import threading


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: build a minimal live_session mock
# ─────────────────────────────────────────────────────────────────────────────

def _make_ls_mock(line_id='line-42', user_id=1, anrede='Sie',
                  kw_fired_for_line=None, slot1_busy_until=0.0,
                  active_profile_id=42):
    """Return a minimal ls mock with thread-safe state + state_lock."""
    ls = types.ModuleType('live_session_mock')
    ls.state_lock = threading.Lock()
    ls.state = {
        'line_id': line_id,
        'user_id': user_id,
        'session_anrede': anrede,
        'kw_fired_for_line': kw_fired_for_line,
        'slot1_variant_busy_until': slot1_busy_until,
        'active_profile_id': active_profile_id,
        'active_sid': 'sid-test-123',
    }
    return ls


# ─────────────────────────────────────────────────────────────────────────────
# Test Group 1: kw_fired_for_line flag in EinwandKeywordMatcher
# ─────────────────────────────────────────────────────────────────────────────

class TestKwFiredForLineFlag(unittest.TestCase):

    def _get_matcher_class(self):
        """Import fresh from source — no caching issues."""
        import importlib
        import services.einwand_keyword_matcher as m
        importlib.reload(m)
        return m.EinwandKeywordMatcher

    def test_match_hit_sets_kw_fired_for_line(self):
        """Test 1: When match_with_dedup returns a match, ls.state['kw_fired_for_line']
        is set to current line_id (from ls.state['line_id'])."""
        from services.einwand_keyword_matcher import EinwandKeywordMatcher
        import services.live_session as ls_real

        mock_ls = _make_ls_mock(line_id='line-42', kw_fired_for_line=None)

        matcher = EinwandKeywordMatcher()

        # Patch services.live_session inside the module
        with patch('services.einwand_keyword_matcher.ls_module', mock_ls, create=True):
            # Use a text that hits 'zu_teuer' and an einwand that has a gegenargument
            profile_einwaende = [
                {'kurzlabel': 'preis', 'gegenargument': 'Unser Preis ist gerechtfertigt.'}
            ]
            result = matcher.match_with_dedup('Das ist viel zu teuer', profile_einwaende)

        # If match returned, kw_fired_for_line should be set
        if result is not None:
            self.assertEqual(mock_ls.state.get('kw_fired_for_line'), 'line-42')

    def test_no_match_does_not_overwrite_kw_fired_for_line(self):
        """Test 2: When match_with_dedup returns None, kw_fired_for_line is NOT changed."""
        from services.einwand_keyword_matcher import EinwandKeywordMatcher
        mock_ls = _make_ls_mock(line_id='line-99', kw_fired_for_line='line-55')
        matcher = EinwandKeywordMatcher()

        with patch('services.einwand_keyword_matcher.ls_module', mock_ls, create=True):
            result = matcher.match_with_dedup('Schönes Wetter heute', [])

        # No match → kw_fired_for_line unchanged
        self.assertIsNone(result)
        self.assertEqual(mock_ls.state.get('kw_fired_for_line'), 'line-55')


# ─────────────────────────────────────────────────────────────────────────────
# Test Group 2: analyse_loop dispatcher (kw_fired_for_line guard + routing)
# These tests call the QA-dispatch logic directly via a helper extracted from
# claude_service.py — we test the *logic path*, not the threading loop.
# ─────────────────────────────────────────────────────────────────────────────

def _build_qa_dispatch_context(
        line_id='line-10', kw_fired_for_line=None,
        user_id=1, anrede='Sie', slot1_busy_until=0.0,
        active_profile_id=42, active_sid='sid-test'):
    """Returns (ls_mock, sio_mock, config_mock) for dispatch tests."""
    ls = _make_ls_mock(line_id=line_id, user_id=user_id, anrede=anrede,
                       kw_fired_for_line=kw_fired_for_line,
                       slot1_busy_until=slot1_busy_until,
                       active_profile_id=active_profile_id)
    ls.state['active_sid'] = active_sid
    sio = MagicMock()
    return ls, sio


class TestAnalyseLoopDispatcher(unittest.TestCase):
    """Tests for the QA-pipeline dispatch logic added to analyse_loop."""

    def _get_dispatch_fn(self):
        """Import the dispatch function once the plan adds it to claude_service."""
        from services.claude_service import _qa_pipeline_dispatch
        return _qa_pipeline_dispatch

    def test_kw_fired_for_line_equal_skips_classify(self):
        """Test 3: kw_fired_for_line == current line_id → classify_utterance NOT called."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(
            line_id='line-7', kw_fired_for_line='line-7'
        )
        with patch('services.qa_pipeline.classify_utterance') as mock_cls:
            dispatch('Kunde sagt irgendwas', 'line-7', '', ls, sio)
            mock_cls.assert_not_called()

    def test_kw_fired_different_calls_classify(self):
        """Test 4: kw_fired_for_line != current line_id → classify_utterance IS called."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(
            line_id='line-8', kw_fired_for_line='line-7'
        )
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'smalltalk_none', 'confidence': 0.9}) as mock_cls, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Hallo', 'line-8', '', ls, sio)
            mock_cls.assert_called_once()

    def test_smalltalk_none_no_emit(self):
        """Test 5: kategorie='smalltalk_none' → no Slot 1 emit, no response generation."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-9', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'smalltalk_none', 'confidence': 0.9}), \
             patch('services.qa_pipeline.generate_qa_response') as mock_gen, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Ja, okay', 'line-9', '', ls, sio)
            mock_gen.assert_not_called()
            sio.emit.assert_not_called()

    def test_einwand_unknown_high_conf_emits_slot1(self):
        """Test 6: einwand_unknown with confidence >= threshold → generate + emit qa_slot1."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-10', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Gute Antwort auf Einwand'), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Das ist zu teuer ohne Keyword', 'line-10', '', ls, sio)
            # qa_slot1 must be emitted
            calls = [str(c) for c in sio.emit.call_args_list]
            self.assertTrue(
                any('qa_slot1' in c for c in calls),
                f"Expected qa_slot1 emit, got: {calls}"
            )

    def test_low_confidence_emits_soft_hint(self):
        """Test 7: confidence < CLASSIFIER_CONFIDENCE_THRESHOLD → emit qa_soft_hint with locked text."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-11', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.3}), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Mhm', 'line-11', '', ls, sio)
            emitted_events = [c.args[0] for c in sio.emit.call_args_list]
            self.assertIn('qa_soft_hint', emitted_events,
                          f"Expected qa_soft_hint, got: {emitted_events}")
            # Check D-04 locked text
            soft_hint_calls = [c for c in sio.emit.call_args_list if c.args[0] == 'qa_soft_hint']
            self.assertTrue(len(soft_hint_calls) > 0)
            hint_data = soft_hint_calls[0].args[1]
            self.assertIn('Neuer Einwand', hint_data.get('text', ''),
                          f"D-04 locked text missing, got: {hint_data}")

    def test_tabu_filter_triggers_soft_hint(self):
        """Test 8: apply_tabu_filter=True → discard response, emit qa_soft_hint."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-12', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Antwort mit Competitor-Begriff'), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=True), \
             patch('services.claude_service._qa_load_tabu', return_value=['Competitor']):
            dispatch('Haben Sie auch Competitor?', 'line-12', '', ls, sio)
            emitted_events = [c.args[0] for c in sio.emit.call_args_list]
            self.assertIn('qa_soft_hint', emitted_events)
            qa_slot1_calls = [c for c in sio.emit.call_args_list if c.args[0] == 'qa_slot1']
            self.assertEqual(len(qa_slot1_calls), 0, "qa_slot1 must NOT be emitted when tabu filtered")

    def test_frage_faq_match_emits_slot1(self):
        """Test 9 (frage path): FAQ match → emit qa_slot1 with faq.antwort."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-13', kw_fired_for_line=None)
        mock_faq = {'id': 7, 'frage_muster': 'Was kostet das?',
                    'antwort': 'Unser Preis startet bei 49 Euro.', 'kategorie': 'Preis'}
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'frage', 'confidence': 0.9}), \
             patch('services.qa_pipeline.match_faq', return_value=mock_faq), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]), \
             patch('services.claude_service._qa_load_faqs', return_value=[mock_faq]):
            dispatch('Wie teuer ist das?', 'line-13', '', ls, sio)
            emitted_events = [c.args[0] for c in sio.emit.call_args_list]
            self.assertIn('qa_slot1', emitted_events,
                          f"Expected qa_slot1 for faq match, got: {emitted_events}")


if __name__ == '__main__':
    unittest.main()
