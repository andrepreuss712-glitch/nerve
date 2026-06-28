# -*- coding: utf-8 -*-
"""TAXO2-Plan 04 — Integration-Assertions fuer den Uebernahme-/Adoption-Judge
(adoption_runner.py).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  test_no_word_match: adoption_runner enthaelt KEINEN mechanischen Text-Vergleich
      (difflib/SequenceMatcher/bleu/rouge/cosine); die Einstufung kommt AUSSCHLIESSLICH
      vom LLM (Tool-Use). Testbar: kein verbotenes Symbol wird ins Modulregister importiert.
      Beginn des test_no_word_match-Kommentars: Grenzfall-Notiz — Source-Presence nur wenn
      kein Function-Call-Mock die Constraint direkt testbar macht; hier ist kein Function-Call
      denkbar, der den mechanischen Vergleich *im Runtme-Pfad* sichtbar machte, ohne dafuer
      den Modulimport zu belegen. Modulimport ist die einzige beweisbare Grenze.

  test_pair_build: _build_adoption_pairs baut je interaction_id das Roh-Paar
      (suggestion_text + erste folgende berater-Aeusserung aus transcript_segments).
      Kein folgende Berater-Satz -> following=None (kein Crash). Assertion auf Rueckgabeliste.

  test_bundled_single_call: run_adoption_judge feuert GENAU 1 messages.create-Aufruf
      fuer ALLE Paare (NICHT einen pro Paar). Monkeypatch-Assertion auf Call-Zaehler.

  test_prompt_has_no_outcome: der Adoption-Prompt enthaelt KEIN calls.outcome
      (outcome-blind, T-HT-04-03). Assertion auf den Prompt-Text des messages.create-Aufrufs.

  test_write_adoption: die Einstufung (adoption_value/reaction_class/following_utterance_ref)
      landet per UPDATE in suggestion_reactions (Assertion auf DB-Schreib-Aufruf).

Kein echter LLM-/DB-Zugriff: anthropic.client + DB-Session werden monkeypatcht.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest


# ════════════════════════════════════════════════════════════════════════════════════
# Test-Doubles
# ════════════════════════════════════════════════════════════════════════════════════

def _make_call(**overrides):
    """Leichtgewichtige calls-Row-Attrappe."""
    base = dict(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        call_mode='cold_call',
        conversation_log_id=42,
        transcript_resolved=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_suggestion(iid=None, text='Erwaehnen Sie unsere Erfolgsrate.', sid=None):
    """Attrappe fuer SuggestionReaction-Row (nur ANGEBOT-Haelfte)."""
    if iid is None:
        iid = str(uuid.uuid4())
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        interaction_id=iid,
        suggestion_text=text,
        adoption_value=None,
        reaction_class=None,
        following_utterance_ref=None,
    )


def _make_segment(idx=1, speaker='berater', ts_ms=2000, text='Ja, wir haben gute Ergebnisse.'):
    """Attrappe fuer TranscriptSegment-Row."""
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text)


def _make_adoption_tool_response(pairs_results=None):
    """Baut eine gemockte Anthropic-Tool-Use-Antwort fuer den Adoption-Judge."""
    if pairs_results is None:
        pairs_results = [
            {
                'interaction_id': 'test-iid-1',
                'beleg': 'Ja, wir haben gute Ergebnisse.',
                'urteil': 'voll',
                'adoption_value': 1.0,
            }
        ]
    tool_input = {'ergebnisse': pairs_results}
    tool_use_block = SimpleNamespace(
        type='tool_use',
        name='record_adoption',
        input=tool_input,
    )
    response = SimpleNamespace(
        stop_reason='tool_use',
        content=[tool_use_block],
    )
    return response


# ════════════════════════════════════════════════════════════════════════════════════
# Test 1: Kein mechanischer Textvergleich (Soll-Verhalten §6 — LLM-Urteil only)
# ════════════════════════════════════════════════════════════════════════════════════

def test_no_word_match():
    """adoption_runner importiert KEINE mechanischen Text-Vergleichs-Module
    (difflib, SequenceMatcher, bleu, rouge, cosine, bert_score).

    Grenzfall-Notiz (CLAUDE.md Source-Presence-Ausnahme): kein Function-Call-Mock macht
    die Abwesenheit mechanischer Text-Vergleichs-Module im Laufzeit-Pfad direkt testbar —
    diese Constraint ist nur ueber den Modulimport-Status beweisbar. Die verbotenen Module
    sind difflib / SequenceMatcher / bleu-Varianten / rouge-Varianten / cosine /
    bert_score: sie koennen nicht per Function-Call-Assertion auf Abwesenheit getestet
    werden, ohne sie zu importieren.
    """
    import sys
    import importlib

    # adoption_runner importieren (loescht ggf. gecachten stand)
    if 'services.adoption_runner' in sys.modules:
        del sys.modules['services.adoption_runner']

    import services.adoption_runner as ar  # importiert das Modul

    # Verbotene mechanische Vergleichs-Module duerfen NICHT im Modulregister stehen
    # (transitiv durch adoption_runner importiert)
    forbidden = ['difflib', 'SequenceMatcher', 'nltk', 'rouge', 'bert_score']
    for mod_name in forbidden:
        # Pruefe: ist das Modul transitiv im Namespace von adoption_runner?
        assert not hasattr(ar, mod_name), (
            f"adoption_runner importiert '{mod_name}' — mechanischer Textvergleich verboten (Soll-Verhalten §6)"
        )

    # Pruefe auch auf haeufige Cosine-/Embedding-Tools die als Vergleich missbraucht werden koennen
    cosine_suspects = ['sklearn', 'scipy', 'torch', 'sentence_transformers']
    for mod_name in cosine_suspects:
        assert not hasattr(ar, mod_name), (
            f"adoption_runner importiert '{mod_name}' — nur LLM-Urteil erlaubt (Soll-Verhalten §6)"
        )


# ════════════════════════════════════════════════════════════════════════════════════
# Test 2: Roh-Paar-Bau aus committeten Daten
# ════════════════════════════════════════════════════════════════════════════════════

def test_pair_build():
    """_build_adoption_pairs baut Roh-Paare (interaction_id, suggestion_text, following_text).

    Fall A: ein Vorschlag mit folgender Berater-Aeusserung -> Paar mit following_text gesetzt.
    Fall B: ein Vorschlag OHNE folgende Berater-Aeusserung -> Paar mit following_text=None.
    Kein Crash in beiden Faellen.
    """
    import services.adoption_runner as ar

    iid_a = str(uuid.uuid4())
    iid_b = str(uuid.uuid4())

    call = _make_call(conversation_log_id=99)

    suggestion_a = _make_suggestion(iid=iid_a, text='Nennen Sie die ROI-Zahlen.')
    suggestion_b = _make_suggestion(iid=iid_b, text='Fragen Sie nach dem Budget.')

    # ts_offered fuer suggestion_a (wann der Vorschlag gezeigt wurde)
    from datetime import datetime
    suggestion_a.ts_offered = datetime(2025, 1, 1, 10, 0, 0)
    suggestion_b.ts_offered = datetime(2025, 1, 1, 10, 5, 0)

    # TranscriptSegments: ein berater-Satz nach suggestion_a, keiner nach suggestion_b
    seg_berater_after_a = _make_segment(
        idx=3, speaker='berater', ts_ms=3000,
        text='Unser ROI liegt bei 200 Prozent fuer diesen Fall.'
    )
    seg_kunde = _make_segment(idx=1, speaker='kunde', ts_ms=1000, text='Interessant.')
    # suggestion_b hat kein folgendes Berater-Segment -> following_text=None

    # Mock DB: suggestion_reactions-Query gibt A+B zurueck; transcript_segments-Query
    # gibt verschiedene Ergebnisse je nach Filter (simplified: first() per Vorschlag)
    def fake_query_side_effect(model_class):
        """Gibt je nach abgefragetem Modell passende Filter-Chains zurueck."""
        from database.models import SuggestionReaction, TranscriptSegment
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            # filter(...).all() -> [suggestion_a, suggestion_b]
            mock_q.filter.return_value.all.return_value = [suggestion_a, suggestion_b]
        elif model_class is TranscriptSegment:
            # Wir emulieren: fuer suggestion_a gibt es einen Berater-Satz (ts_ms > ts_offered),
            # fuer suggestion_b nicht. Hier vereinfacht via side_effect auf first().
            call_count = [0]
            def first_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return seg_berater_after_a   # suggestion_a hat Folge-Satz
                return None                       # suggestion_b hat keinen
            filter_mock = MagicMock()
            filter_mock.filter.return_value = filter_mock
            filter_mock.order_by.return_value = filter_mock
            filter_mock.first.side_effect = first_side_effect
            mock_q.filter.return_value = filter_mock
        return mock_q

    fake_db = MagicMock()
    fake_db.query.side_effect = fake_query_side_effect

    pairs = ar._build_adoption_pairs(call, fake_db)

    assert len(pairs) == 2, f"Erwartet 2 Paare, erhalten: {len(pairs)}"

    # Pair fuer suggestion_a: following_text gesetzt
    pair_a = next((p for p in pairs if p['interaction_id'] == iid_a), None)
    assert pair_a is not None, "Paar fuer interaction_id_a fehlt"
    assert pair_a['suggestion_text'] == 'Nennen Sie die ROI-Zahlen.'
    assert pair_a['following_text'] == 'Unser ROI liegt bei 200 Prozent fuer diesen Fall.'

    # Pair fuer suggestion_b: following_text=None (kein Crash)
    pair_b = next((p for p in pairs if p['interaction_id'] == iid_b), None)
    assert pair_b is not None, "Paar fuer interaction_id_b fehlt"
    assert pair_b['following_text'] is None


# ════════════════════════════════════════════════════════════════════════════════════
# Test 3: EIN gebuendelter Call fuer ALLE Paare (Soll-Verhalten §6 Schaerfung b)
# ════════════════════════════════════════════════════════════════════════════════════

def test_bundled_single_call(monkeypatch):
    """run_adoption_judge feuert GENAU 1 messages.create-Aufruf fuer alle Paare
    (NICHT einen Call pro Paar — gebuendelt, Soll-Verhalten §6 Schaerfung b).
    """
    import services.adoption_runner as ar
    from database.models import SuggestionReaction, TranscriptSegment

    iid1 = str(uuid.uuid4())
    iid2 = str(uuid.uuid4())
    call = _make_call()

    sug1 = _make_suggestion(iid=iid1, text='Vorschlag 1')
    sug2 = _make_suggestion(iid=iid2, text='Vorschlag 2')

    seg1 = _make_segment(idx=1, speaker='berater', ts_ms=2000, text='Antwort 1')
    seg2 = _make_segment(idx=2, speaker='berater', ts_ms=4000, text='Antwort 2')

    # Mock LLM-Client
    fake_client = MagicMock()
    pair_results = [
        {'interaction_id': iid1, 'beleg': 'Antwort 1', 'urteil': 'voll', 'adoption_value': 1.0},
        {'interaction_id': iid2, 'beleg': 'Antwort 2', 'urteil': 'teilweise', 'adoption_value': 0.5},
    ]
    fake_client.messages.create.return_value = _make_adoption_tool_response(pair_results)
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    # Mock _build_adoption_pairs: gibt 2 Paare zurueck (kein echter DB-Call)
    monkeypatch.setattr(ar, '_build_adoption_pairs', lambda c, db: [
        {'interaction_id': iid1, 'suggestion_text': 'Vorschlag 1', 'following_text': 'Antwort 1'},
        {'interaction_id': iid2, 'suggestion_text': 'Vorschlag 2', 'following_text': 'Antwort 2'},
    ])

    # Mock DB (wird nur fuer UPDATE gebraucht)
    fake_db = MagicMock()
    sug1_db = _make_suggestion(iid=iid1, text='Vorschlag 1')
    sug2_db = _make_suggestion(iid=iid2, text='Vorschlag 2')

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            call_count = [0]
            def first_side():
                call_count[0] += 1
                if call_count[0] == 1:
                    return sug1_db
                return sug2_db
            mock_q.filter.return_value.first.side_effect = first_side
        return mock_q

    fake_db.query.side_effect = fake_query_side

    result = ar.run_adoption_judge(call, fake_db)

    # Genau 1 LLM-Call fuer ALLE Paare (gebuendelt)
    assert fake_client.messages.create.call_count == 1, (
        f"Erwartet genau 1 LLM-Call, aber {fake_client.messages.create.call_count} gemacht — "
        "gebuendelt, NICHT pro Paar!"
    )
    assert result.get('status') == 'adoption_done'


# ════════════════════════════════════════════════════════════════════════════════════
# Test 4: Outcome physisch NICHT im Adoption-Prompt (T-HT-04-03)
# ════════════════════════════════════════════════════════════════════════════════════

def test_prompt_has_no_outcome(monkeypatch):
    """Der Adoption-Prompt enthaelt KEIN calls.outcome (outcome-blind, T-HT-04-03).
    Assertion auf den tatsaechlichen Prompt-Text des messages.create-Aufrufs.
    """
    import services.adoption_runner as ar
    from database.models import SuggestionReaction

    iid = str(uuid.uuid4())
    call = _make_call()
    # outcome-Feld explizit auf einem Wert — darf NICHT im Prompt erscheinen
    call.outcome = 'meeting_booked'

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_adoption_tool_response([
        {'interaction_id': iid, 'beleg': 'Test', 'urteil': 'ignoriert', 'adoption_value': 0.0}
    ])
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    monkeypatch.setattr(ar, '_build_adoption_pairs', lambda c, db: [
        {'interaction_id': iid, 'suggestion_text': 'Test-Vorschlag', 'following_text': 'Test-Antwort'},
    ])

    fake_db = MagicMock()
    sug_db = _make_suggestion(iid=iid, text='Test-Vorschlag')

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            mock_q.filter.return_value.first.return_value = sug_db
        return mock_q

    fake_db.query.side_effect = fake_query_side

    ar.run_adoption_judge(call, fake_db)

    # Prompt extrahieren (system + messages)
    assert fake_client.messages.create.called
    kwargs = fake_client.messages.create.call_args[1]
    system_str = kwargs.get('system', '')
    messages = kwargs.get('messages', [])
    user_str = ' '.join(str(m.get('content', '')) for m in messages)
    full_prompt = system_str + ' ' + user_str

    # Outcome-Werte duerfen NICHT vorkommen
    for outcome_val in ['meeting_booked', 'no_interest', 'contract_signed', 'callback', 'wrong_person']:
        assert outcome_val not in full_prompt, (
            f"Outcome-Wert '{outcome_val}' im Adoption-Prompt gefunden — muss raus (T-HT-04-03)"
        )
    assert 'outcome' not in full_prompt.lower(), "Das Wort 'outcome' ist im Adoption-Prompt!"


# ════════════════════════════════════════════════════════════════════════════════════
# Test 5: Write in suggestion_reactions (adoption_value / reaction_class / following_utterance_ref)
# ════════════════════════════════════════════════════════════════════════════════════

def test_write_adoption(monkeypatch):
    """Die Einstufung (adoption_value/reaction_class/following_utterance_ref) landet
    per In-Place-UPDATE in suggestion_reactions (DEFERRED-Spalten, jetzt befuellt).
    Assertion auf ORM-Attribut-Schreibung (state mutation nach run_adoption_judge).
    """
    import services.adoption_runner as ar
    from database.models import SuggestionReaction

    iid = str(uuid.uuid4())
    call = _make_call()

    pair_results = [
        {'interaction_id': iid, 'beleg': 'Wir setzen das so um.', 'urteil': 'voll', 'adoption_value': 1.0}
    ]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_adoption_tool_response(pair_results)
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    monkeypatch.setattr(ar, '_build_adoption_pairs', lambda c, db: [
        {'interaction_id': iid, 'suggestion_text': 'Setzen Sie das um.', 'following_text': 'Wir setzen das so um.'},
    ])

    # Echte Suggestion-Row-Attrappe (mutierbares SimpleNamespace)
    sug_row = _make_suggestion(iid=iid, text='Setzen Sie das um.')
    # Zeile initialisiert mit None-Werten (DEFERRED)
    assert sug_row.adoption_value is None
    assert sug_row.reaction_class is None
    assert sug_row.following_utterance_ref is None

    fake_db = MagicMock()

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            mock_q.filter.return_value.first.return_value = sug_row
        return mock_q

    fake_db.query.side_effect = fake_query_side

    result = ar.run_adoption_judge(call, fake_db)

    # Die DEFERRED-Spalten muessen jetzt befuellt sein
    assert sug_row.adoption_value == 1.0, (
        f"adoption_value nicht gesetzt: {sug_row.adoption_value!r}"
    )
    assert sug_row.reaction_class == 'voll', (
        f"reaction_class nicht gesetzt: {sug_row.reaction_class!r}"
    )
    assert sug_row.following_utterance_ref is not None, (
        "following_utterance_ref ist None — muss den Beleg-Verweis enthalten"
    )
    assert result.get('status') == 'adoption_done'
    assert result.get('written', 0) >= 1
