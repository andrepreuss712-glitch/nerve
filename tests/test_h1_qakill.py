"""
tests/test_h1_qakill.py
──────────────────────────────────────────────────────────────────────────
Phase 08.23.2.H1 Plan 01 (WEG 1, Welle 1 — QAKILL)

Runtime-Waechter fuer den Kill des verworfenen `generate_qa_response`-Antwort-
Calls im Live-Dispatch `_qa_pipeline_dispatch` (services/claude_service.py).

Warum ueberhaupt gekappt wird — Beweis-Ergebnis des Pflicht-Vorabchecks (Punkt 20):
grep + Code-Lesung belegen, dass das Ergebnis `_antwort` beider Aufrufe
KONSUMENTEN-FREI ist (kein Emit, kein State-Write, kein DB-Write, kein Return,
kein Log-Konsum haengt an `_antwort`).

──────────────────────────────────────────────────────────────────────────
GREP-BELEG (verbatim, `grep -n "generate_qa_response" services/ -r`, HEAD 1aa2445):

  services\\claude_service.py:1528:            classify_utterance, generate_qa_response,   # Import
  services\\claude_service.py:1630:            # Pfad (generate_qa_response / FAQ) bleibt ...   # Kommentar
  services\\claude_service.py:1641:                _antwort = generate_qa_response(            # AUFRUF 1 (einwand_unknown else)
  services\\claude_service.py:1686:                    _antwort = generate_qa_response(        # AUFRUF 2 (frage/kein-FAQ else)
  services\\qa_pipeline.py:12:  - generate_qa_response(utterance, category, ...              # Docstring
  services\\qa_pipeline.py:82:# ... bleibt strukturell erhalten (siehe generate_qa_response). # Kommentar
  services\\qa_pipeline.py:377:# -- Public: generate_qa_response ---                          # Section-Kommentar
  services\\qa_pipeline.py:378:def generate_qa_response(utterance: str, category: str, ...   # DEFINITION
  services\\qa_pipeline.py:500:        print(f"[QA] generate_qa_response failed: {e}")         # Log-String

=> Genau ZWEI Produktiv-Aufrufe (claude_service.py:1641 + :1686), beide in
   `_qa_pipeline_dispatch`. Alles Uebrige: Import/Kommentar/Docstring/def/Log.

KONSUMENTEN-FREIHEIT von `_antwort` (Code-Lesung beider else-Zweige):

  Zweig 1 (einwand_unknown, :1641-1651):
    _antwort = generate_qa_response(...)
    if not _antwort:            _emit_soft_hint(reason='empty_response')   # No-Op (nur print)
    elif apply_tabu_filter(_antwort, _tabu_begriffe):                      # reine Funktion
        _emit_soft_hint(reason='tabu_filtered')                           # No-Op
        print(f"[QA-INT] response tabu-filtered len={len(_antwort)}")     # len() im print
    else: _emit_qa_slot1(_antwort)                                        # No-Op (nur print)

  Zweig 2 (frage/kein-FAQ, :1686-1695): identisches Muster, gleiche No-Op-Emitter.

  `_antwort` fliesst NUR in: `if not _antwort`, `apply_tabu_filter(_antwort,...)`
  (reine Funktion, entscheidet nur WELCHER No-Op), `len(_antwort)` in einem print,
  und die No-Op-Emitter `_emit_soft_hint`/`_emit_qa_slot1` (seit PIP-01 emittieren
  sie NICHTS, nur print — services/claude_service.py:1548 + :1618). KEIN return,
  KEIN ls._session_state[...]=, KEIN .commit(), KEIN sio.emit, KEIN intent_event
  haengt an `_antwort`. => Aufruf ist ein verworfener Bezahl-Call. Sicher kappbar.

MODEL_QA=SONNET-FUND (Zusatzschaerfe): `generate_qa_response` laeuft auf
  `config.MODEL_QA` (qa_pipeline.py:444), Default `claude-sonnet-4-5`
  (config.py:75); Cost-Model-Ableitung `'sonnet-4-5' if 'sonnet' in config.MODEL_QA`
  (qa_pipeline.py:473). Der verworfene Aufruf ist also ein verworfener SONNET-Call
  im Live-Loop — verletzt zusaetzlich die CLAUDE.md-Constraint "Sonnet MUSS raus
  aus dem Live-Loop". Der Kill schliesst dieses Constraint-Leck.

LEBENDE Konsumenten (bleiben unangetastet — classify_utterance BLEIBT):
  - low-conf Abstain-intent_events (_emit_abstain_event -> emit_intent_event),
  - FAQ-Treffer used_count-Inkrement (ProfileFaq.used_count += 1).
  Diese Datei asserted BEIDE weiter aktiv (Positiv-Waechter).
──────────────────────────────────────────────────────────────────────────
"""

import types
import threading
import unittest
from unittest.mock import MagicMock, patch


def _make_ls_mock(user_id=1, org_id=1, anrede='Sie', active_profile_id=42,
                  active_sid='sid-test', kw_fired_for_line=None,
                  slot1_busy_until=0.0):
    """Minimaler ls-Mock mit per-SID single-source state + Abstain-Closure-Methoden."""
    ls = types.ModuleType('live_session_mock')
    ls._session_state_lock = threading.Lock()
    ls._session_state = {
        active_sid: {
            'user_id': user_id,
            'org_id': org_id,
            'active_profile_id': active_profile_id,
            'active_sid': active_sid,
            'mode': 'cold_call',
            'session_anrede': anrede,
            'state': {
                'kw_fired_for_line': kw_fired_for_line,
                'slot1_variant_busy_until': slot1_busy_until,
                'current_phase': None,
                'call_id': 'call-xyz',
            },
        }
    }
    # Methoden, die _emit_abstain_event auf ls aufruft (sonst AttributeError -> emit skipped)
    ls.get_or_open_moment = MagicMock(return_value=None)
    ls._durable_call_id = MagicMock(return_value='call-xyz')
    ls.get_anonymisierer = MagicMock(return_value=None)
    return ls


def _dispatch():
    from services.claude_service import _qa_pipeline_dispatch
    return _qa_pipeline_dispatch


class TestQaKill(unittest.TestCase):
    """Runtime-Waechter: der verworfene generate_qa_response-Call feuert NICHT mehr."""

    def test_einwand_unknown_high_conf_does_not_call_generate_qa_response(self):
        """RED gegen Ist-Code, GRUEN nach Kill: high-conf einwand_unknown ruft
        generate_qa_response NICHT mehr auf (verworfener Sonnet-Call entfernt)."""
        dispatch = _dispatch()
        ls = _make_ls_mock()
        sio = MagicMock()
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Antwort die verworfen wird') as mock_gen, \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]):
            dispatch('Das ist zu teuer ohne Keyword', 'line-h1-1', '', ls, sio, sid='sid-test')
        self.assertFalse(
            mock_gen.called,
            "generate_qa_response darf im high-conf einwand_unknown-Zweig NICHT mehr "
            "aufgerufen werden (verworfener Sonnet-Call, QAKILL).")

    def test_frage_no_faq_high_conf_does_not_call_generate_qa_response(self):
        """RED gegen Ist-Code, GRUEN nach Kill: high-conf frage ohne FAQ-Match ruft
        generate_qa_response NICHT mehr auf."""
        dispatch = _dispatch()
        ls = _make_ls_mock()
        sio = MagicMock()
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'frage', 'confidence': 0.95}), \
             patch('services.qa_pipeline.generate_qa_response',
                   return_value='Antwort die verworfen wird') as mock_gen, \
             patch('services.qa_pipeline.match_faq', return_value=None), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]), \
             patch('services.claude_service._qa_load_faqs', return_value=[]):
            dispatch('Wie funktioniert das genau?', 'line-h1-2', '', ls, sio, sid='sid-test')
        self.assertFalse(
            mock_gen.called,
            "generate_qa_response darf im high-conf frage/kein-FAQ-Zweig NICHT mehr "
            "aufgerufen werden (verworfener Sonnet-Call, QAKILL).")

    # ── Positiv-Waechter: lebende Konsumenten bleiben aktiv ──────────────────

    def test_low_conf_einwand_unknown_still_fires_abstain_intent_event(self):
        """LEBENDER Konsument: low-conf einwand_unknown feuert weiter ein
        intent_event mit abstained=True (H-4 Abstain-Funnel, DSGVO/TAXO)."""
        dispatch = _dispatch()
        ls = _make_ls_mock()
        sio = MagicMock()
        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'einwand_unknown', 'confidence': 0.2}), \
             patch('services.claude_service._qa_load_tabu', return_value=[]), \
             patch('services.intent_event_writer.emit_intent_event') as mock_emit:
            dispatch('Mhm, weiss nicht', 'line-h1-3', '', ls, sio, sid='sid-test')
        self.assertTrue(mock_emit.called,
                        "low-conf einwand_unknown MUSS weiter emit_intent_event feuern.")
        kwargs = mock_emit.call_args.kwargs
        self.assertTrue(kwargs.get('abstained'),
                        "Abstain-Event MUSS abstained=True tragen (low-conf Drop).")
        self.assertEqual(kwargs.get('intent_type'), 'echter_einwand')

    def test_faq_match_increments_used_count(self):
        """LEBENDER Konsument: FAQ-Treffer (nicht-tabu) inkrementiert used_count."""
        dispatch = _dispatch()
        ls = _make_ls_mock()
        sio = MagicMock()
        mock_faq = {'id': 7, 'frage_muster': 'Was kostet das?',
                    'antwort': 'Ab 49 Euro.', 'mode': 'literal'}

        class _Row:
            used_count = 3

        row = _Row()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = row

        with patch('services.qa_pipeline.classify_utterance',
                   return_value={'kategorie': 'frage', 'confidence': 0.9}), \
             patch('services.qa_pipeline.match_faq', return_value=mock_faq), \
             patch('services.qa_pipeline.apply_tabu_filter', return_value=False), \
             patch('services.claude_service._qa_load_tabu', return_value=[]), \
             patch('services.claude_service._qa_load_faqs', return_value=[mock_faq]), \
             patch('database.db.SessionLocal', return_value=db):
            dispatch('Wie teuer ist das?', 'line-h1-4', '', ls, sio, sid='sid-test')

        self.assertEqual(row.used_count, 4,
                         "FAQ-used_count MUSS bei nicht-tabu-Treffer inkrementiert werden.")
        self.assertTrue(db.commit.called, "used_count-Inkrement MUSS committed werden.")

    def test_model_qa_default_is_sonnet(self):
        """Dokumentiert den Zusatzfund: MODEL_QA ist zur Laufzeit Sonnet-Default —
        der (jetzt gekappte) Call war ein verworfener Sonnet-Call im Live-Loop."""
        import config
        self.assertIn('sonnet', config.MODEL_QA.lower(),
                      f"MODEL_QA sollte Sonnet sein (verworfener Sonnet-Call-Fund), "
                      f"ist: {config.MODEL_QA}")


if __name__ == '__main__':
    unittest.main()
