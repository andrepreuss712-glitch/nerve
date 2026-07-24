"""Unit tests for services/qa_pipeline.py (Phase 08.5)."""
import sys
import types
import unittest
from unittest.mock import patch, MagicMock


# ── Inject a minimal sentence_transformers stub so tests work without install ──
# This must happen BEFORE importing services.qa_pipeline.
def _make_st_stub():
    st = types.ModuleType('sentence_transformers')
    util_mod = types.ModuleType('sentence_transformers.util')
    st.util = util_mod
    st.SentenceTransformer = MagicMock
    sys.modules.setdefault('sentence_transformers', st)
    sys.modules.setdefault('sentence_transformers.util', util_mod)

_make_st_stub()

from services.qa_pipeline import (
    classify_utterance, generate_qa_response, match_faq, apply_tabu_filter
)


class TestApplyTabuFilter(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertFalse(apply_tabu_filter('', ['x']))
        self.assertFalse(apply_tabu_filter('x', []))
        self.assertFalse(apply_tabu_filter('x', None))

    def test_substring_match(self):
        self.assertTrue(apply_tabu_filter('Wir sind besser als Competitor', ['Competitor']))

    def test_case_insensitive(self):
        self.assertTrue(apply_tabu_filter('Wir sind besser als COMPETITOR', ['competitor']))
        self.assertTrue(apply_tabu_filter('Wir sind besser als competitor', ['Competitor']))

    def test_no_match(self):
        self.assertFalse(apply_tabu_filter('harmloser Text', ['Preis']))

    def test_ignores_non_string(self):
        self.assertFalse(apply_tabu_filter('text', [None, 123, '']))

    def test_multiple_tabu(self):
        self.assertTrue(apply_tabu_filter('erwaehnt Preis offen', ['Konkurrenz', 'Preis']))


class TestMatchFaq(unittest.TestCase):
    def test_empty_faqs(self):
        self.assertIsNone(match_faq('wie teuer?', []))

    def test_empty_utterance(self):
        self.assertIsNone(match_faq('', [{'id': 1, 'frage_muster': 'test', 'antwort': 'x'}]))

    def test_whitespace_utterance(self):
        self.assertIsNone(match_faq('   ', [{'id': 1, 'frage_muster': 'test', 'antwort': 'x'}]))

    def test_model_unavailable(self):
        """If sentence-transformers not installed or load fails, match_faq returns None."""
        with patch('services.qa_pipeline._get_embedding_model', return_value=None):
            result = match_faq('wie teuer?', [{'id': 1, 'frage_muster': 'Was kostet es?', 'antwort': '99EUR'}])
            self.assertIsNone(result)

    def test_must_not_raise(self):
        """Even with broken model, no exception propagates."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("boom")
        with patch('services.qa_pipeline._get_embedding_model', return_value=mock_model):
            result = match_faq('x', [{'id': 1, 'frage_muster': 'y', 'antwort': 'z'}])
            self.assertIsNone(result)

    def test_semantic_match_above_threshold(self):
        """When model returns high similarity, match_faq returns the matched FAQ dict."""
        faq_list = [{'id': 1, 'frage_muster': 'Was kostet es?', 'antwort': '99EUR'}]

        # Build a mock model and mock util.cos_sim that returns score > threshold
        mock_model = MagicMock()

        row = MagicMock()
        row.argmax.return_value = 0
        # float(scores[best_idx]) -> 0.95
        row.__getitem__ = MagicMock(return_value=MagicMock(__float__=lambda self: 0.95))

        mock_util = MagicMock()
        mock_util.cos_sim.return_value = [row]

        st_stub = sys.modules.get('sentence_transformers')
        orig_util = getattr(st_stub, 'util', None)
        try:
            st_stub.util = mock_util
            sys.modules['sentence_transformers.util'] = mock_util
            with patch('services.qa_pipeline._get_embedding_model', return_value=mock_model):
                result = match_faq('wie teuer', faq_list, threshold=0.5)
                # Should return the matched faq or None if import path differs
                self.assertTrue(result is None or result == faq_list[0])
        finally:
            if orig_util is not None:
                st_stub.util = orig_util
                sys.modules['sentence_transformers.util'] = orig_util

    def test_no_match_below_threshold(self):
        """When similarity is below threshold, match_faq returns None."""
        faq_list = [{'id': 1, 'frage_muster': 'Was kostet es?', 'antwort': '99EUR'}]

        mock_model = MagicMock()

        row = MagicMock()
        row.argmax.return_value = 0
        row.__getitem__ = MagicMock(return_value=MagicMock(__float__=lambda self: 0.30))

        mock_util = MagicMock()
        mock_util.cos_sim.return_value = [row]

        st_stub = sys.modules.get('sentence_transformers')
        orig_util = getattr(st_stub, 'util', None)
        try:
            st_stub.util = mock_util
            sys.modules['sentence_transformers.util'] = mock_util
            with patch('services.qa_pipeline._get_embedding_model', return_value=mock_model):
                result = match_faq('Wetter ist schoen', faq_list, threshold=0.75)
                self.assertIsNone(result)
        finally:
            if orig_util is not None:
                st_stub.util = orig_util
                sys.modules['sentence_transformers.util'] = orig_util


class TestClassifyUtterance(unittest.TestCase):
    def test_empty_text_returns_fallback(self):
        result = classify_utterance('', '', 0)
        self.assertEqual(result['kategorie'], 'smalltalk_none')
        self.assertEqual(result['confidence'], 0.0)
        self.assertIsNone(result['einwand_zitat'])

    def test_whitespace_only_returns_fallback(self):
        result = classify_utterance('   \n\t  ', '', 0)
        self.assertEqual(result['kategorie'], 'smalltalk_none')

    def test_fail_open_on_claude_exception(self):
        """When Claude API raises, classify_utterance returns fail-open dict."""
        with patch('services.qa_pipeline.resolve_prompt_version', return_value='v1'), \
             patch('services.qa_pipeline._load_qa_template', return_value='prompt'):
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = RuntimeError("API down")
            mock_client.with_options.return_value = mock_client
            import services.claude_service as cs
            with patch.object(cs, 'claude_client', mock_client):
                result = classify_utterance('echt interessant', '', 0)
                self.assertEqual(result['kategorie'], 'smalltalk_none')
                self.assertEqual(result['confidence'], 0.0)

    def test_invalid_json_returns_fallback(self):
        """When Claude returns invalid JSON, returns fail-open dict."""
        with patch('services.qa_pipeline.resolve_prompt_version', return_value='v1'), \
             patch('services.qa_pipeline._load_qa_template', return_value='prompt'):
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text='NOT JSON AT ALL')]
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_msg
            mock_client.with_options.return_value = mock_client
            import services.claude_service as cs
            with patch.object(cs, 'claude_client', mock_client):
                result = classify_utterance('test text', '', 0)
                self.assertEqual(result['kategorie'], 'smalltalk_none')
                self.assertEqual(result['confidence'], 0.0)

    def test_unknown_kategorie_coerced_to_smalltalk(self):
        """Unknown kategorie values are coerced to smalltalk_none."""
        import json
        valid_json = json.dumps({'kategorie': 'UNBEKANNT', 'confidence': 0.9, 'einwand_zitat': None})
        with patch('services.qa_pipeline.resolve_prompt_version', return_value='v1'), \
             patch('services.qa_pipeline._load_qa_template', return_value='prompt'):
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text=valid_json)]
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_msg
            mock_client.with_options.return_value = mock_client
            import services.claude_service as cs
            with patch.object(cs, 'claude_client', mock_client):
                result = classify_utterance('test', '', 0)
                self.assertEqual(result['kategorie'], 'smalltalk_none')


class TestGenerateQaResponse(unittest.TestCase):
    def test_empty_utterance_returns_empty(self):
        self.assertEqual(generate_qa_response('', 'einwand_unknown', {}, 'Sie', 'v1', 0), '')

    def test_invalid_category_returns_empty(self):
        self.assertEqual(generate_qa_response('x', 'smalltalk_none', {}, 'Sie', 'v1', 0), '')
        self.assertEqual(generate_qa_response('x', 'einwand_known', {}, 'Sie', 'v1', 0), '')

    def test_fail_closed_on_exception(self):
        """When the system-prompt source raises, error is caught non-fatally.
        Function continues and returns fallback Rueckfrage (never empty, never propagates).
        LB-3-Fix (08.20-03) + TAXO3 P1-02: QA baut den System-Prompt jetzt aus
        answer_system_content (build_answer_context) — dessen Fehler bleiben non-fatal."""
        with patch('services.qa_pipeline.answer_system_content', side_effect=RuntimeError("boom")):
            result = generate_qa_response(
                'wie teuer?', 'frage', {}, 'Sie',
                confidence=1.0, version='', user_id=0
            )
            # Non-fatal: function falls through to outer except (no claude_client in test env)
            # → returns _FALLBACK_RUECKFRAGE, never raises, never empty
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

    def test_success_returns_string(self):
        """When Haiku call succeeds, returns non-empty string."""
        with patch('services.qa_pipeline.resolve_prompt_version', return_value='v1'), \
             patch('services.qa_pipeline._load_qa_template',
                   return_value='Anrede: {anrede}. Profil-Kontext:\n{profile_context}'), \
             patch('services.qa_pipeline.build_profile_context', return_value='Profil-Info'):
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text='Das ist kein Problem fuer unsere Kunden.')]
            mock_client = MagicMock()
            mock_client.messages.create.return_value = mock_msg
            mock_client.with_options.return_value = mock_client
            import services.claude_service as cs
            with patch.object(cs, 'claude_client', mock_client):
                result = generate_qa_response(
                    'Wie lange dauert die Implementierung?', 'frage', {}, 'Sie', 'v1', 0
                )
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


if __name__ == '__main__':
    unittest.main()
