# -*- coding: utf-8 -*-
"""TAXO2-Plan 03 — Integration-Assertions fuer den LLM-Verhaltens-Judge (judge_runner.py).

Beweist Runtime-Verhalten (CLAUDE.md Test-Qualitaets-Regel — KEIN Source-Presence):

  Outcome-Trennung: der gebaute Prompt enthaelt PHYSISCH KEIN calls.outcome /
      'meeting_booked' / 'no_interest' / 'contract_signed' / 'callback' / 'wrong_person'.

  Vorschlags-Trennung: der Prompt enthaelt KEINE suggestion_reactions-Inhalte (Bias-Schutz;
      Adoption ist Plan 04). Runtime-Assertion auf den Prompt-Text.

  Rubrik Anfang+Ende: dimensions_for_prompt()-Block kommt MINDESTENS zweimal vor
      (Lost-in-the-Middle: Anfang UND Ende des Prompts).

  Tool-Use erzwungen: der messages.create-Call wird mit tools + tool_choice aufgerufen;
      Schema verlangt pro Dimension beleg_zitat -> beobachtung -> auspraegung (Beleg-VOR-Note).

  Compliance als eigenes Feld (Cross-AI-Finding 2): JUDGE_TOOL input_schema hat ein
      SEPARATES Top-Level-Feld compliance_violation (boolean) + compliance_beleg_zitat (string)
      — NICHT innerhalb einer Dimension.

  Parse->UPSERT-Form: gemockte Tool-Antwort -> observations_jsonb
      {dim_key:[{beobachtung,beleg_zitat}]} + ratings_jsonb {dim_key:'schwach'|'ok'|'stark'}
      + Compliance-Eintrag in observations_jsonb['_compliance'] ({verletzt, beleg_zitat}).

  Compliance-Hard-Gate-Separatheit: '_compliance' NICHT in ratings_jsonb —
      kein Mittelwert-Beitrag (Hard-Gate-Semantik, Finding 2).

  Transcript-resolved-Gate: run_behavior_judge kehrt fruehzeitig zurueck, wenn
      transcript_resolved==False.

Kein echter LLM-/DB-Zugriff: anthropic.client + DB-Session werden monkeypatcht.
"""

import types
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import services.judge_runner as jr
from services.judge_dimensions import DIMENSIONS, dimensions_for_prompt


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
        audio_health_score=0.9,
        transcript_resolved=True,
        user_id=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_segment(idx=1, speaker='berater', ts_ms=1000, text='Hallo, wie kann ich helfen?'):
    return SimpleNamespace(id=idx, ts_ms=ts_ms, speaker=speaker, text=text)


def _fake_profile_briefing():
    return "## Branche\nVertrieb\n## Basis\nKaltakquise\n## PreCall-Briefing\n(noch nicht erstellt)"


def _make_tool_response(dim_results=None, compliance_violation=False, compliance_beleg=''):
    """Baut eine gemockte anthropic-Tool-Use-Antwort."""
    if dim_results is None:
        dim_results = {
            'bedarfs_ermittlung': [{'beleg_zitat': 'Wie loesung Sie das?', 'beobachtung': 'Berater fragte offen.', 'auspraegung': 'stark'}],
            'gespraechs_eroeffnung': [{'beleg_zitat': 'Ich rufe wegen X an.', 'beobachtung': 'Einstieg klar.', 'auspraegung': 'ok'}],
            'einwand_behandlung': [{'beleg_zitat': 'Das ist zu teuer.', 'beobachtung': 'Einwand uebergangen.', 'auspraegung': 'schwach'}],
            'gespraechsfuehrung': [{'beleg_zitat': 'Berater redet.', 'beobachtung': 'Redeanteil ok.', 'auspraegung': 'ok'}],
        }
    tool_input = dict(dim_results)
    tool_input['compliance_violation'] = compliance_violation
    tool_input['compliance_beleg_zitat'] = compliance_beleg

    tool_use_block = SimpleNamespace(
        type='tool_use',
        name='record_observations',
        input=tool_input,
    )
    response = SimpleNamespace(
        stop_reason='tool_use',
        content=[tool_use_block],
    )
    return response


# ════════════════════════════════════════════════════════════════════════════════════
# Test 1: Outcome physisch NICHT im Prompt
# ════════════════════════════════════════════════════════════════════════════════════

def test_prompt_has_no_outcome():
    """Der Prompt-Text enthaelt KEINE Outcome-Werte — physische Trennung, nicht nur Weglassen."""
    call = _make_call()
    segments = [
        _make_segment(1, 'berater', 100, 'Guten Tag, darf ich kurz stoeren?'),
        _make_segment(2, 'kunde', 2000, 'Was wollen Sie?'),
    ]
    events = []

    system_str, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)
    full_prompt = system_str + ' ' + user_str

    # Keine Outcome-Werte im Prompt (physische Trennung)
    for outcome_val in ['meeting_booked', 'no_interest', 'contract_signed', 'callback', 'wrong_person']:
        assert outcome_val not in full_prompt, f"Outcome-Wert '{outcome_val}' im Prompt gefunden!"

    # Auch das Feld-Wort 'outcome' selbst darf nicht vorkommen (wuerde den Wert implizieren)
    assert 'outcome' not in full_prompt.lower(), "Das Wort 'outcome' ist im Prompt!"


# ════════════════════════════════════════════════════════════════════════════════════
# Test 2: NERVE-Vorschlaege NICHT im Prompt (Bias-Schutz)
# ════════════════════════════════════════════════════════════════════════════════════

def test_prompt_has_no_suggestions():
    """Der Prompt enthaelt KEINE suggestion_reactions-Inhalte — Bias-Schutz gegen Self-Enhancement."""
    call = _make_call()
    segments = [_make_segment(1, 'berater', 100, 'Probe-Satz')]
    events = []

    system_str, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)
    full_prompt = system_str + ' ' + user_str

    # Kein Vorschlags-Inhalt (Adoption ist Plan 04)
    assert 'suggestion_reaction' not in full_prompt
    assert 'NERVE schlug vor' not in full_prompt
    assert 'Vorschlag' not in full_prompt


# ════════════════════════════════════════════════════════════════════════════════════
# Test 3: Rubrik an Anfang UND Ende (Lost-in-the-Middle)
# ════════════════════════════════════════════════════════════════════════════════════

def test_rubric_at_start_and_end():
    """dimensions_for_prompt()-Block erscheint MINDESTENS zweimal im Prompt (Anfang+Ende)."""
    call = _make_call()
    segments = [_make_segment(1, 'berater', 100, 'Test')]
    events = []

    system_str, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)
    full_prompt = system_str + '\n' + user_str

    # Eine Phrase aus dem dimensions_for_prompt()-Output als Anker
    rubrik_sample = 'Bedarfsermittlung'  # fester Dim-Name aus judge_dimensions.DIMENSIONS
    count = full_prompt.count(rubrik_sample)
    assert count >= 2, (
        f"Rubrik-Block ('{rubrik_sample}') kommt nur {count}x vor — muss mindestens 2x (Anfang+Ende) vorkommen"
    )


# ════════════════════════════════════════════════════════════════════════════════════
# Test 4: Transkript-Tagging (ts_ms ASC, ewb button erhalten)
# ════════════════════════════════════════════════════════════════════════════════════

def test_transcript_tagged_in_order():
    """Jede Transkript-Zeile traegt einen Tag [#i speaker ts_ms ms], in ts_ms ASC Reihenfolge."""
    call = _make_call()
    segments = [
        _make_segment(1, 'berater', 500,  'Guten Tag.'),
        _make_segment(2, 'kunde',   1500, 'Kein Interesse. *ewb button*'),
        _make_segment(3, 'berater', 2500, 'Ich verstehe das.'),
    ]
    events = []

    _sys, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)

    # Tag-Format: [#1 berater 500ms]
    assert '[#1 berater 500ms]' in user_str
    assert '[#2 kunde 1500ms]' in user_str
    assert '[#3 berater 2500ms]' in user_str

    # ewb-button-Marker bleibt im Text
    assert '*ewb button*' in user_str

    # Reihenfolge: Tag 1 vor Tag 2 vor Tag 3
    pos1 = user_str.index('[#1 berater 500ms]')
    pos2 = user_str.index('[#2 kunde 1500ms]')
    pos3 = user_str.index('[#3 berater 2500ms]')
    assert pos1 < pos2 < pos3


# ════════════════════════════════════════════════════════════════════════════════════
# Test 5: Tool-Use erzwungen — Schema + tool_choice
# ════════════════════════════════════════════════════════════════════════════════════

def test_forced_tool_use(monkeypatch):
    """messages.create wird mit tools + tool_choice={'type':'tool'} aufgerufen.
    Schema verlangt pro Dimension beleg_zitat -> beobachtung -> auspraegung (Beleg-VOR-Note).
    """
    call = _make_call()
    segments = [_make_segment(1, 'berater', 100, 'Probe')]
    events = []
    captured = {}

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_tool_response()
    monkeypatch.setattr(jr, 'claude_client', fake_client)
    monkeypatch.setattr(jr, 'build_profile_context', lambda *a, **k: _fake_profile_briefing())

    # Fake DB-Session die segments zurueckgibt
    fake_db = MagicMock()
    fake_query = MagicMock()
    fake_query.filter.return_value.order_by.return_value.all.return_value = segments
    fake_db.query.return_value = fake_query

    jr.run_behavior_judge(call, events, fake_db)

    # Assertion auf den create-Aufruf
    assert fake_client.messages.create.called
    kwargs = fake_client.messages.create.call_args[1]

    # tools UND tool_choice muss vorhanden sein
    assert 'tools' in kwargs, "Parameter 'tools' fehlt im messages.create-Aufruf"
    assert 'tool_choice' in kwargs, "Parameter 'tool_choice' fehlt im messages.create-Aufruf"
    assert kwargs['tool_choice']['type'] == 'tool', "tool_choice type muss 'tool' sein (forced)"
    assert kwargs['tool_choice']['name'] == 'record_observations'

    # Schema jeder Dimension: beleg_zitat, beobachtung, auspraegung (Beleg-VOR-Note)
    tool_def = kwargs['tools'][0]
    schema = tool_def['input_schema']
    props = schema.get('properties', {})

    for dim in DIMENSIONS:
        key = dim['key']
        assert key in props, f"Dimension '{key}' fehlt im Tool-Schema"
        dim_schema = props[key]
        # Array of observation objects
        items = dim_schema.get('items', {})
        item_props = items.get('properties', {})
        assert 'beleg_zitat' in item_props, f"'beleg_zitat' fehlt in Dimension '{key}'"
        assert 'beobachtung' in item_props, f"'beobachtung' fehlt in Dimension '{key}'"
        assert 'auspraegung' in item_props, f"'auspraegung' fehlt in Dimension '{key}'"


# ════════════════════════════════════════════════════════════════════════════════════
# Test 6: Compliance als EIGENES Feld (Cross-AI-Finding 2)
# ════════════════════════════════════════════════════════════════════════════════════

def test_compliance_is_separate_field(monkeypatch):
    """JUDGE_TOOL input_schema hat compliance_violation (bool) + compliance_beleg_zitat (string)
    als SEPARATE Top-Level-Felder — NICHT innerhalb einer Dimension."""
    call = _make_call()
    segments = [_make_segment(1, 'berater', 100, 'Probe')]
    events = []

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_tool_response()
    monkeypatch.setattr(jr, 'claude_client', fake_client)
    monkeypatch.setattr(jr, 'build_profile_context', lambda *a, **k: _fake_profile_briefing())

    fake_db = MagicMock()
    fake_query = MagicMock()
    fake_query.filter.return_value.order_by.return_value.all.return_value = segments
    fake_db.query.return_value = fake_query

    jr.run_behavior_judge(call, events, fake_db)

    kwargs = fake_client.messages.create.call_args[1]
    tool_def = kwargs['tools'][0]
    schema = tool_def['input_schema']
    props = schema.get('properties', {})

    # compliance_violation und compliance_beleg_zitat muessen Top-Level-Felder sein
    assert 'compliance_violation' in props, "compliance_violation fehlt als Top-Level-Feld im Schema"
    assert 'compliance_beleg_zitat' in props, "compliance_beleg_zitat fehlt als Top-Level-Feld im Schema"

    # compliance_violation muss ein boolean sein
    assert props['compliance_violation'].get('type') == 'boolean', "compliance_violation muss boolean-Typ haben"

    # Die Dim-Keys duerfen KEIN 'compliance_violation' enthalten
    for dim in DIMENSIONS:
        key = dim['key']
        dim_schema = props.get(key, {})
        items = dim_schema.get('items', {})
        item_props = items.get('properties', {})
        assert 'compliance_violation' not in item_props, (
            f"compliance_violation darf NICHT innerhalb Dimension '{key}' liegen"
        )


# ════════════════════════════════════════════════════════════════════════════════════
# Test 7: Parse -> UPSERT-Form (observations_jsonb + ratings_jsonb + _compliance)
# ════════════════════════════════════════════════════════════════════════════════════

def test_parse_separates_ratings():
    """_parse_judge_output baut observations_jsonb {dim:[{beobachtung,beleg_zitat}]} +
    ratings_jsonb {dim: auspraegung} (auspraegung NICHT in observations) +
    observations_jsonb['_compliance'] = {verletzt:bool, beleg_zitat:str}."""
    tool_input = {
        'bedarfs_ermittlung': [
            {'beleg_zitat': 'Wie loesung Sie das heute?', 'beobachtung': 'Offene Frage gestellt.', 'auspraegung': 'stark'}
        ],
        'gespraechs_eroeffnung': [
            {'beleg_zitat': 'Ich rufe wegen X an.', 'beobachtung': 'Einstieg klar.', 'auspraegung': 'ok'}
        ],
        'einwand_behandlung': [
            {'beleg_zitat': 'Das ist zu teuer.', 'beobachtung': 'Uebergangen.', 'auspraegung': 'schwach'}
        ],
        'gespraechsfuehrung': [
            {'beleg_zitat': 'OK, tschues.', 'beobachtung': 'Gut gefuehrt.', 'auspraegung': 'ok'}
        ],
        'compliance_violation': False,
        'compliance_beleg_zitat': '',
    }

    observations, ratings = jr._parse_judge_output(tool_input)

    # Observations: nur {beobachtung, beleg_zitat} — KEINE auspraegung
    for dim in ['bedarfs_ermittlung', 'gespraechs_eroeffnung', 'einwand_behandlung', 'gespraechsfuehrung']:
        assert dim in observations, f"Dim '{dim}' fehlt in observations_jsonb"
        for obs in observations[dim]:
            assert 'beobachtung' in obs
            assert 'beleg_zitat' in obs
            assert 'auspraegung' not in obs, (
                f"'auspraegung' darf NICHT in observations stehen (nur intern in ratings)"
            )

    # Ratings: nur auspraegung
    assert ratings['bedarfs_ermittlung'] == 'stark'
    assert ratings['gespraechs_eroeffnung'] == 'ok'
    assert ratings['einwand_behandlung'] == 'schwach'
    assert ratings['gespraechsfuehrung'] == 'ok'

    # Compliance in observations['_compliance']
    assert '_compliance' in observations, "'_compliance' fehlt in observations_jsonb"
    comp = observations['_compliance']
    assert 'verletzt' in comp
    assert comp['verletzt'] is False
    assert 'beleg_zitat' in comp


# ════════════════════════════════════════════════════════════════════════════════════
# Test 8: Compliance NICHT in ratings_jsonb (Hard-Gate, nicht aufmittelbar)
# ════════════════════════════════════════════════════════════════════════════════════

def test_compliance_not_in_ratings():
    """'_compliance' liegt SEPARAT in observations_jsonb — NICHT in ratings_jsonb.
    Das Hard-Gate darf nicht von einer Dimension rausgemittelt werden."""
    tool_input = {
        'bedarfs_ermittlung': [
            {'beleg_zitat': 'Wie sieht das bei Ihnen aus?', 'beobachtung': 'Gut.', 'auspraegung': 'stark'}
        ],
        'gespraechs_eroeffnung': [
            {'beleg_zitat': 'Guten Tag.', 'beobachtung': 'OK.', 'auspraegung': 'ok'}
        ],
        'einwand_behandlung': [
            {'beleg_zitat': 'Kein Interesse!', 'beobachtung': 'Nach dreimaligem Nein weitergemacht.', 'auspraegung': 'schwach'}
        ],
        'gespraechsfuehrung': [
            {'beleg_zitat': 'Dreimal abgelehnt, weiter gepitcht.', 'beobachtung': 'Grenze ueberschritten.', 'auspraegung': 'schwach'}
        ],
        'compliance_violation': True,
        'compliance_beleg_zitat': 'Nein danke! Ich will das nicht! Bitte nicht mehr anrufen!',
    }

    observations, ratings = jr._parse_judge_output(tool_input)

    # _compliance MUSS in observations
    assert '_compliance' in observations
    assert observations['_compliance']['verletzt'] is True
    assert 'Nein danke' in observations['_compliance']['beleg_zitat']

    # _compliance darf NICHT in ratings (kein Mittelwert-Beitrag)
    assert '_compliance' not in ratings, "'_compliance' darf NICHT in ratings_jsonb stehen (Hard-Gate)"
    # Alle ratings-Keys sind echte Dim-Keys
    valid_keys = {d['key'] for d in DIMENSIONS}
    for key in ratings:
        assert key in valid_keys, f"Unerwarteter Key '{key}' in ratings_jsonb"


# ════════════════════════════════════════════════════════════════════════════════════
# Test 9: Anstoss gated auf transcript_resolved (Plan-01-Fan-In)
# ════════════════════════════════════════════════════════════════════════════════════

def test_judge_gated_on_transcript_resolved(monkeypatch):
    """run_behavior_judge kehrt fruehzeitig zurueck (status='transcript_not_resolved')
    wenn transcript_resolved==False — der Judge laeuft dem Transkript-Write nie voraus."""
    call = _make_call(transcript_resolved=False)
    events = []
    fake_db = MagicMock()

    fake_client = MagicMock()
    monkeypatch.setattr(jr, 'claude_client', fake_client)

    result = jr.run_behavior_judge(call, events, fake_db)

    # Kein LLM-Call
    fake_client.messages.create.assert_not_called()

    # Status zeigt an, warum der Judge nicht lief
    assert result.get('status') == 'transcript_not_resolved'
