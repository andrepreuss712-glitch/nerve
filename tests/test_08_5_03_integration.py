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
                  active_profile_id=42, active_sid='sid-test-123'):
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
        'active_sid': active_sid,
    }
    # Phase 08.19.4: per-SID state dict (mirrors live_session._session_state)
    # Phase 08.23.2.TAXO1-03: the live dispatch + matcher read/write line_id,
    # kw_fired_for_line, slot1_variant_busy_until and session_anrede from the
    # per-SID single source _session_state[sid]['state'] — NOT from the old global
    # ls.state. The mock therefore seeds that 'state' sub-dict like the live path.
    ls._session_state_lock = threading.Lock()
    ls._session_state = {
        active_sid: {
            'user_id': user_id,
            'org_id': 1,
            'active_profile_id': active_profile_id,
            'active_sid': active_sid,
            'state': {
                'line_id': line_id,
                'kw_fired_for_line': kw_fired_for_line,
                'slot1_variant_busy_until': slot1_busy_until,
                'session_anrede': anrede,
            },
        }
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

        mock_ls = _make_ls_mock(line_id='line-42', kw_fired_for_line=None,
                                active_sid='sid-test-123')

        matcher = EinwandKeywordMatcher()

        # Patch services.live_session inside the module
        with patch('services.einwand_keyword_matcher.ls_module', mock_ls, create=True):
            # Use a text that hits 'zu_teuer' and an einwand that has a gegenargument
            profile_einwaende = [
                {'kurzlabel': 'preis', 'gegenargument': 'Unser Preis ist gerechtfertigt.'}
            ]
            # Phase 08.23.2.TAXO1-03 (§0.1 P4 REVERSE): matcher writes kw_fired_for_line
            # into the per-SID single source, so it needs the sid.
            result = matcher.match_with_dedup('Das ist viel zu teuer', profile_einwaende,
                                              sid='sid-test-123')

        # If match returned, kw_fired_for_line must be set in the per-SID single source
        # (NOT the old global ls.state — that path was deleted in Wave 3).
        if result is not None:
            self.assertEqual(
                mock_ls._session_state['sid-test-123']['state'].get('kw_fired_for_line'),
                'line-42',
            )

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
                       active_profile_id=active_profile_id,
                       active_sid=active_sid)
    ls.state['active_sid'] = active_sid
    sio = MagicMock()
    return ls, sio


# Phase 08.23.2.PIP-01: die vier Roh-Enum-Kategorien duerfen NIE als ewb_signal-typ
# rausgehen (Cross-AI LOW Geister-Button). _kat-Enum-Quelle: qa_pipeline.py:324.
_RAW_ENUM_TYPS = {'smalltalk_none', 'frage', 'einwand_known', 'einwand_unknown'}


def _emitted_events(sio):
    """Liste der Event-Namen, die auf dem sio-Mock emittiert wurden."""
    return [c.args[0] for c in sio.emit.call_args_list if c.args]


def _ewb_signal_payloads(sio):
    """Liste der ewb_signal-Payload-Dicts (zweites Positional-Arg) auf dem sio-Mock."""
    out = []
    for c in sio.emit.call_args_list:
        if c.args and c.args[0] == 'ewb_signal':
            out.append(c.args[1] if len(c.args) > 1 else {})
    return out


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
            dispatch('Kunde sagt irgendwas', 'line-7', '', ls, sio, sid='sid-test')
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
            dispatch('Hallo', 'line-8', '', ls, sio, sid='sid-test')
            mock_cls.assert_called_once()

    def test_smalltalk_none_no_emit(self):
        """Test 5: kategorie='smalltalk_none' → no Slot 1 emit, no response generation."""
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-9', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'smalltalk_none', 'confidence': 0.9}), \
             patch('services.qa_pipeline.generate_qa_response') as mock_gen, \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Ja, okay', 'line-9', '', ls, sio, sid='sid-test')
            mock_gen.assert_not_called()
            sio.emit.assert_not_called()

    def test_einwand_unknown_high_conf_no_readzone_emit(self):
        """PIP-01 (Item a) — frueher test_einwand_unknown_high_conf_emits_slot1.

        Neuer ewb_signal-Vertrag: einwand_unknown high-conf laeuft weiter durch die
        Antwort-Generierung (generate_qa_response wird aufgerufen), aber der Auto-Pfad
        schreibt NICHT mehr die Lese-Zone (slot 1) -> KEIN qa_slot1-Emit. Es entsteht
        auch KEIN ewb_signal: der Roh-Enum 'einwand_unknown' ist ein Platzhalter, kein
        anzeigbares Kurz-Label -> Blocklist -> kein (Geister-)Button (Cross-AI HIGH #1
        + LOW). lieber kein Button als ein Geister-Button.
        """
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-10', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Gute Antwort auf Einwand') as mock_gen, \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Das ist zu teuer ohne Keyword', 'line-10', '', ls, sio, sid='sid-test')
        emitted = _emitted_events(sio)
        # Upstream-Logik bleibt erhalten (nur der Lese-Zonen-Schreib-Seiteneffekt entfaellt)
        mock_gen.assert_called_once()
        self.assertNotIn('qa_slot1', emitted,
                         f"qa_slot1 darf nach PIP-01 nicht mehr feuern (Lese-Zonen-Cut), got: {emitted}")
        self.assertNotIn('ewb_signal', emitted,
                         f"einwand_unknown ohne konkretes Kurz-Label -> kein ewb_signal, got: {emitted}")
        # Defensiv: falls je ein ewb_signal kaeme, niemals mit Roh-Enum als typ
        for payload in _ewb_signal_payloads(sio):
            self.assertNotIn(payload.get('typ'), _RAW_ENUM_TYPS)

    def test_einwand_unknown_passes_profile_data_not_empty(self):
        """WR-01 Regression: generate_qa_response muss _profile_daten erhalten, nicht {}.
        Phase 08.19.4: migriert von get_active_profile() auf get_profile_for_sid(sid).
        """
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-20', kw_fired_for_line=None)
        captured_calls = []
        def _capture_gen(*args, **kwargs):
            captured_calls.append({'args': args, 'kwargs': kwargs})
            return 'Testantwort'

        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   side_effect=_capture_gen), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]), \
             patch('services.live_session.get_profile_for_sid',
                   return_value=('TestProfil', {'basis': {'produktbeschreibung': 'CRM'}})):
            dispatch('Das ist zu teuer', 'line-20', '', ls, sio, sid='sid-test')

        self.assertTrue(len(captured_calls) > 0, "generate_qa_response wurde nicht aufgerufen")
        call_args = captured_calls[0]['args']
        # 3. Argument muss ein nicht-leeres Dict sein (nicht {})
        profile_data_arg = call_args[2]
        self.assertIsInstance(profile_data_arg, dict, "profile_data muss dict sein")
        self.assertNotEqual(profile_data_arg, {}, "profile_data darf nicht leer sein (WR-01)")

    def test_low_confidence_no_readzone_emit(self):
        """PIP-01 (Item a + Cross-AI HIGH #2) — frueher test_low_confidence_emits_soft_hint.

        Neuer ewb_signal-Vertrag: low-confidence (einwand_unknown, conf < threshold)
        emittiert KEINEN qa_soft_hint mehr. Der frueher gesendete Literal-Hint
        'Neuer Einwand — noch kein Vorschlag' war ein Lese-Zonen-Text und waere als
        ewb_signal-typ ein Langstring-/Geister-Button -> verboten. Ohne echtes Kurz-Label
        wird gar kein Signal emittiert. Die abstain-/intent_event-Logik (DSGVO/TAXO) im
        Caller bleibt unberuehrt (sie laeuft NICHT ueber sio.emit, sondern den
        intent_event_writer) -> kein sio-Emit erwartet.
        """
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-11', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.3}), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Mhm', 'line-11', '', ls, sio, sid='sid-test')
        emitted = _emitted_events(sio)
        self.assertNotIn('qa_soft_hint', emitted,
                         f"qa_soft_hint darf nach PIP-01 nicht mehr feuern (Lese-Zonen-Cut), got: {emitted}")
        self.assertNotIn('ewb_signal', emitted,
                         f"kein echtes Kurz-Label -> kein ewb_signal, got: {emitted}")
        # Defensiv: kein Roh-Enum und kein Langstring-Hint als ewb_signal-typ
        for payload in _ewb_signal_payloads(sio):
            self.assertNotIn(payload.get('typ'), _RAW_ENUM_TYPS)
            self.assertLessEqual(len(str(payload.get('typ', ''))), 40,
                                 "ewb_signal-typ darf kein Langstring/Hint-Absatz sein")

    def test_tabu_filter_no_readzone_emit(self):
        """PIP-01 (Item a) — frueher test_tabu_filter_triggers_soft_hint.

        Neuer ewb_signal-Vertrag: tabu-gefilterte Antwort -> KEIN qa_slot1 (war schon so)
        UND KEIN qa_soft_hint mehr (Lese-Zonen-Cut) UND KEIN ewb_signal (kein echtes
        Kurz-Label im analyse_loop/QA-Pfad). Die Antwort wird verworfen, ohne dass etwas
        in die Lese-Zone oder die Button-Zone geschrieben wird.
        """
        dispatch = self._get_dispatch_fn()
        ls, sio = _build_qa_dispatch_context(line_id='line-12', kw_fired_for_line=None)
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Antwort mit Competitor-Begriff'), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=True), \
             patch('services.claude_service._qa_load_tabu', return_value=['Competitor']):
            dispatch('Haben Sie auch Competitor?', 'line-12', '', ls, sio, sid='sid-test')
        emitted = _emitted_events(sio)
        self.assertNotIn('qa_soft_hint', emitted,
                         f"qa_soft_hint darf nach PIP-01 nicht mehr feuern, got: {emitted}")
        self.assertNotIn('qa_slot1', emitted,
                         f"qa_slot1 darf bei tabu nie feuern, got: {emitted}")
        self.assertNotIn('ewb_signal', emitted,
                         f"kein echtes Kurz-Label -> kein ewb_signal, got: {emitted}")

    def test_frage_faq_match_no_readzone_emit(self):
        """PIP-01 (Item a) — frueher test_frage_faq_match_emits_slot1.

        Neuer ewb_signal-Vertrag: 'frage' ist eine NON-Action-Kategorie fuer die
        EWB-Button-Zone. Der FAQ-Match-Pfad laeuft weiter (FAQ-Logik/used_count), aber er
        schreibt NICHT mehr qa_slot1 in die Lese-Zone und erzeugt KEIN ewb_signal
        (kein Einwand-Button fuer eine Frage).
        """
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
            dispatch('Wie teuer ist das?', 'line-13', '', ls, sio, sid='sid-test')
        emitted = _emitted_events(sio)
        self.assertNotIn('qa_slot1', emitted,
                         f"qa_slot1 darf nach PIP-01 nicht mehr feuern, got: {emitted}")
        self.assertNotIn('ewb_signal', emitted,
                         f"'frage' ist NON-Action -> kein ewb_signal, got: {emitted}")


if __name__ == '__main__':
    unittest.main()
