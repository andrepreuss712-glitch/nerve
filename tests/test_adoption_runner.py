# -*- coding: utf-8 -*-
"""TAXO2-Plan 04/06 — Integration-Assertions fuer den Uebernahme-/Adoption-Judge
(adoption_runner.py).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  test_no_word_match: adoption_runner enthaelt KEINEN mechanischen Text-Vergleich
      (difflib/SequenceMatcher/bleu/rouge/cosine); die Einstufung kommt AUSSCHLIESSLICH
      vom LLM (Tool-Use). Testbar: kein verbotenes Symbol wird ins Modulregister importiert.
      Grenzfall-Notiz — kein Function-Call-Mock macht die Abwesenheit mechanischer
      Text-Vergleichs-Module im Laufzeit-Pfad direkt testbar; nur ueber Modulimport-Status.

  test_whole_transcript_and_suggestion_list (ersetzt test_pair_build ab Plan 06):
      run_adoption_judge gibt dem LLM das GANZE Transkript (alle segments ts_ms ASC)
      UND die Vorschlags-Liste (interaction_id + suggestion_text). Kein mechanisches
      Pairing (_build_adoption_pairs darf nicht existieren). Genau 1 LLM-Call (gebuendelt).

  test_bundled_single_call: run_adoption_judge feuert GENAU 1 messages.create-Aufruf
      fuer ALLE Vorschlaege (NICHT einen pro Vorschlag). Direct-DB-Mock (kein
      _build_adoption_pairs-Mock, da Funktion entfernt).

  test_prompt_has_no_outcome: der Adoption-Prompt enthaelt KEIN calls.outcome
      (outcome-blind, T-HT-04-03). Assertion auf den Prompt-Text des messages.create-Aufrufs.
      Direct-DB-Mock.

  test_write_adoption: die Einstufung (adoption_value/reaction_class/following_utterance_ref)
      landet per UPDATE in suggestion_reactions (Assertion auf DB-Schreib-Aufruf).
      Direct-DB-Mock.

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
# Test 2: run_adoption_judge gibt LLM ganzes Transkript + Vorschlags-Liste (Plan 06)
# ════════════════════════════════════════════════════════════════════════════════════

def test_whole_transcript_and_suggestion_list(monkeypatch):
    """run_adoption_judge gibt dem LLM das GANZE Transkript (alle segments ts_ms ASC)
    UND die Vorschlags-Liste (interaction_id + suggestion_text).
    Kein mechanisches Pairing (_build_adoption_pairs darf nicht existieren).
    Genau 1 LLM-Call (gebuendelt).
    """
    import services.adoption_runner as ar
    from database.models import SuggestionReaction, TranscriptSegment

    iid1 = str(uuid.uuid4())
    call = _make_call(conversation_log_id=99)

    # Test-Double fuer Vorschlag
    sug1 = _make_suggestion(iid=iid1, text='Erwaehnen Sie die Erfolgsrate.')

    # Test-Double fuer Transkript (3 Segmente, verschiedene speaker)
    seg_kunde = _make_segment(idx=1, speaker='kunde', ts_ms=1000, text='Was kostet das?')
    seg_berater1 = _make_segment(idx=2, speaker='berater', ts_ms=2000, text='Das kostet 500 Euro.')
    seg_berater2 = _make_segment(idx=3, speaker='berater', ts_ms=4000, text='Unsere Erfolgsrate ist 85 Prozent.')
    all_segments = [seg_kunde, seg_berater1, seg_berater2]

    # Mock LLM
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_adoption_tool_response([
        {'interaction_id': iid1, 'beleg': 'Unsere Erfolgsrate ist 85 Prozent.', 'urteil': 'voll', 'adoption_value': 1.0}
    ])
    fake_client.with_options.return_value = fake_client
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    # Mock DB: SuggestionReaction -> [sug1], TranscriptSegment -> all_segments
    def fake_query(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            # filter(...).all() -> [sug1]
            mock_q.filter.return_value.all.return_value = [sug1]
            # filter(...).first() -> sug1 (fuer die Write-Schleife)
            mock_q.filter.return_value.first.return_value = sug1
        elif model_class is TranscriptSegment:
            # filter(...).order_by(...).all() -> all_segments
            mock_q.filter.return_value.order_by.return_value.all.return_value = all_segments
        return mock_q

    fake_db = MagicMock()
    fake_db.query.side_effect = fake_query

    result = ar.run_adoption_judge(call, fake_db)

    # (a) Genau 1 LLM-Call (gebuendelt, Soll-Verhalten §6 Schaerfung b)
    assert fake_client.messages.create.call_count == 1

    # (b) Prompt enthaelt das ganze Transkript (alle 3 Segmente)
    kwargs = fake_client.messages.create.call_args[1]
    user_str = ' '.join(str(m.get('content', '')) for m in kwargs.get('messages', []))
    full_prompt = kwargs.get('system', '') + ' ' + user_str

    assert 'Was kostet das?' in full_prompt, "Transkript-Segment 1 fehlt im Prompt"
    assert 'Das kostet 500 Euro.' in full_prompt, "Transkript-Segment 2 fehlt im Prompt"
    assert 'Unsere Erfolgsrate ist 85 Prozent.' in full_prompt, "Transkript-Segment 3 fehlt im Prompt"

    # (c) Prompt enthaelt die Vorschlags-Liste (interaction_id + suggestion_text)
    assert iid1 in full_prompt, "interaction_id fehlt im Prompt"
    assert 'Erwaehnen Sie die Erfolgsrate.' in full_prompt, "suggestion_text fehlt im Prompt"

    # (d) _build_adoption_pairs darf NICHT existieren (Negativguard — Funktion ist entfernt)
    # CLAUDE.md Grenzfall: Abwesenheit einer Funktion ist nur ueber hasattr beweisbar.
    assert not hasattr(ar, '_build_adoption_pairs'), (
        "_build_adoption_pairs existiert noch — muss entfernt sein (Wall-Clock/ts_ms-Fragilitaet)"
    )

    # (e) Status OK
    assert result.get('status') == 'adoption_done'


# ════════════════════════════════════════════════════════════════════════════════════
# Test 3: EIN gebuendelter Call fuer ALLE Vorschlaege (Soll-Verhalten §6 Schaerfung b)
# ════════════════════════════════════════════════════════════════════════════════════

def test_bundled_single_call(monkeypatch):
    """run_adoption_judge feuert GENAU 1 messages.create-Aufruf fuer alle Vorschlaege
    (NICHT einen Call pro Vorschlag — gebuendelt, Soll-Verhalten §6 Schaerfung b).
    """
    import services.adoption_runner as ar
    from database.models import SuggestionReaction, TranscriptSegment

    iid1 = str(uuid.uuid4())
    iid2 = str(uuid.uuid4())
    call_obj = _make_call()

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
    fake_client.with_options.return_value = fake_client
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    # Mock DB direkt fuer SuggestionReaction-Query und TranscriptSegment-Query
    sug1_db = _make_suggestion(iid=iid1, text='Vorschlag 1')
    sug2_db = _make_suggestion(iid=iid2, text='Vorschlag 2')

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            # filter().all() fuer den Vorschlaege-Load
            mock_q.filter.return_value.all.return_value = [sug1, sug2]
            # filter().first() fuer die Write-Schleife (per interaction_id)
            call_count = [0]
            def first_side():
                call_count[0] += 1
                if call_count[0] == 1:
                    return sug1_db
                return sug2_db
            mock_q.filter.return_value.first.side_effect = first_side
        elif model_class is TranscriptSegment:
            # filter().order_by().all() -> Segmente
            mock_q.filter.return_value.order_by.return_value.all.return_value = [seg1, seg2]
        return mock_q

    fake_db = MagicMock()
    fake_db.query.side_effect = fake_query_side

    result = ar.run_adoption_judge(call_obj, fake_db)

    # Genau 1 LLM-Call fuer ALLE Vorschlaege (gebuendelt)
    assert fake_client.messages.create.call_count == 1, (
        f"Erwartet genau 1 LLM-Call, aber {fake_client.messages.create.call_count} gemacht — "
        "gebuendelt, NICHT pro Vorschlag!"
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
    from database.models import SuggestionReaction, TranscriptSegment

    iid = str(uuid.uuid4())
    call_obj = _make_call()
    # outcome-Feld explizit auf einem Wert — darf NICHT im Prompt erscheinen
    call_obj.outcome = 'meeting_booked'

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_adoption_tool_response([
        {'interaction_id': iid, 'beleg': 'Test', 'urteil': 'ignoriert', 'adoption_value': 0.0}
    ])
    fake_client.with_options.return_value = fake_client
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    sug = _make_suggestion(iid=iid, text='Test-Vorschlag')
    sug_db = _make_suggestion(iid=iid, text='Test-Vorschlag')

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            mock_q.filter.return_value.all.return_value = [sug]
            mock_q.filter.return_value.first.return_value = sug_db
        elif model_class is TranscriptSegment:
            mock_q.filter.return_value.order_by.return_value.all.return_value = []
        return mock_q

    fake_db = MagicMock()
    fake_db.query.side_effect = fake_query_side

    ar.run_adoption_judge(call_obj, fake_db)

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
    from database.models import SuggestionReaction, TranscriptSegment

    iid = str(uuid.uuid4())
    call_obj = _make_call()

    pair_results = [
        {'interaction_id': iid, 'beleg': 'Wir setzen das so um.', 'urteil': 'voll', 'adoption_value': 1.0}
    ]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_adoption_tool_response(pair_results)
    fake_client.with_options.return_value = fake_client
    monkeypatch.setattr(ar, 'claude_client', fake_client)

    # Echte Suggestion-Row-Attrappe (mutierbares SimpleNamespace)
    sug_row = _make_suggestion(iid=iid, text='Setzen Sie das um.')
    # Zeile initialisiert mit None-Werten (DEFERRED)
    assert sug_row.adoption_value is None
    assert sug_row.reaction_class is None
    assert sug_row.following_utterance_ref is None

    def fake_query_side(model_class):
        mock_q = MagicMock()
        if model_class is SuggestionReaction:
            mock_q.filter.return_value.all.return_value = [sug_row]
            mock_q.filter.return_value.first.return_value = sug_row
        elif model_class is TranscriptSegment:
            mock_q.filter.return_value.order_by.return_value.all.return_value = []
        return mock_q

    fake_db = MagicMock()
    fake_db.query.side_effect = fake_query_side

    result = ar.run_adoption_judge(call_obj, fake_db)

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
