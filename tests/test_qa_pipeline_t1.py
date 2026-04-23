"""
Temporary RED-phase tests for Task 1: services/qa_pipeline.py
(These tests MUST fail before the file is created.)
"""
import unittest
from unittest.mock import patch, MagicMock


class TestTask1RedPhase(unittest.TestCase):
    def test_import_classify_utterance(self):
        from services.qa_pipeline import classify_utterance
        result = classify_utterance("Das ist mir zu teuer", "", 0)
        self.assertIn('kategorie', result)
        self.assertIn('confidence', result)
        self.assertIn('einwand_zitat', result)

    def test_apply_tabu_filter_basic(self):
        from services.qa_pipeline import apply_tabu_filter
        self.assertTrue(apply_tabu_filter('Wir sind besser als Competitor', ['Competitor']))
        self.assertTrue(apply_tabu_filter('Wir sind besser als Competitor', ['competitor']))
        self.assertFalse(apply_tabu_filter('harmloser Text', ['Preis']))
        self.assertFalse(apply_tabu_filter('', ['x']))
        self.assertFalse(apply_tabu_filter('x', []))
        self.assertFalse(apply_tabu_filter('x', None))

    def test_match_faq_stub(self):
        from services.qa_pipeline import match_faq
        result = match_faq('x', [{'frage_muster': 'y', 'antwort': 'z'}])
        self.assertIsNone(result)

    def test_haiku_model_id_in_file(self):
        import subprocess
        result = subprocess.run(
            ['grep', '-c', 'claude-haiku-4-5-20251001', 'services/qa_pipeline.py'],
            capture_output=True, text=True,
            cwd='/c/Users/andre/dev/salesnerve'
        )
        count = int(result.stdout.strip())
        self.assertGreaterEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
