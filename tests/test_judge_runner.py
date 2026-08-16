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

    # ── METRIK-1 Plan 05 Task 1: der gepaarte EXISTENZ-Anker, der diesem Bestandstest fehlte ──
    # Ohne ihn waere der Test auch dann gruen, wenn _build_judge_prompt ein leeres Tupel
    # zurueckgaebe — "nicht gefunden" waere dann von "nichts gelesen" nicht zu unterscheiden.
    # (Bau-Regel-20-Luecke im BESTAND, nicht nur im Neubau.)
    assert '[#1 berater' in user_str          # das Transkript wurde ueberhaupt gerendert
    assert 'headline_observation' in user_str  # die Kopfzeilen-Aufgabe steht im Prompt
    assert len(user_str) > 200


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
# Test 4: Transkript-Tagging (ts_ms ASC, EWB-Knopf-Zeile GEFILTERT)
# ════════════════════════════════════════════════════════════════════════════════════

def test_transcript_tagged_in_order():
    """Jede Transkript-Zeile traegt einen Tag [#i speaker ts_ms ms], in ts_ms ASC Reihenfolge.

    METRIK-1 D-04: die EWB-Knopf-Zeile faellt aus dem Bewerter-Auftrag; die Nummerierung
    laeuft ueber die GEFILTERTE Liste und hinterlaesst deshalb keine Luecke.
    """
    call = _make_call()
    segments = [
        _make_segment(1, 'berater', 500,  'Guten Tag.'),
        _make_segment(2, 'kunde',   1500, 'Kein Interesse. *ewb button*'),
        _make_segment(3, 'berater', 2500, 'Ich verstehe das.'),
    ]
    events = []

    _sys, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)

    # Tag-Format: [#1 berater 500ms]; die gefilterte Kunde-Zeile ruecken die folgenden auf.
    assert '[#1 berater 500ms]' in user_str
    assert '[#2 berater 2500ms]' in user_str
    assert '[#3' not in user_str

    # METRIK-1 D-04: der EWB-Marker ist aus dem Bewerter-Auftrag GEFILTERT (Vertragswechsel 2026-08-13).
    assert '*ewb button*' not in user_str, "D-04: die EWB-Knopf-Zeile darf nicht im Bewerter-Auftrag stehen"

    # Gepaarter Existenz-Anker: "nicht gefunden" darf nicht von "nichts gelesen" kommen.
    assert '[#1 berater' in user_str
    assert user_str.count('[#') >= 2

    # Reihenfolge: Tag 1 vor Tag 2
    pos1 = user_str.index('[#1 berater 500ms]')
    pos2 = user_str.index('[#2 berater 2500ms]')
    assert pos1 < pos2


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
    fake_client.with_options.return_value = fake_client
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
    fake_client.with_options.return_value = fake_client
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
    fake_client.with_options.return_value = fake_client
    monkeypatch.setattr(jr, 'claude_client', fake_client)

    result = jr.run_behavior_judge(call, events, fake_db)

    # Kein LLM-Call
    fake_client.messages.create.assert_not_called()

    # Status zeigt an, warum der Judge nicht lief
    assert result.get('status') == 'transcript_not_resolved'


# ════════════════════════════════════════════════════════════════════════════════════
# METRIK-1 Plan 05 Task 1 — die belegte KOPFZEILE ("bester Moment")
#
# Zwei ZUSAETZLICHE Felder im BESTEHENDEN Tool-Schema. KEIN zweiter LLM-Aufruf, gleiche
# Wartezeit (SPEC Requirement 5, Punkt 25). Die "eine Sache fuers naechste Mal" berechnet
# der CODE (services/fokus_katalog.py, Plan 04) — sie taucht hier bewusst NICHT auf.
# ════════════════════════════════════════════════════════════════════════════════════

def _tool_input_mit_kopfzeile(headline='Der Berater hat den Einwand ruhig gespiegelt.',
                              beleg='Verstehe ich richtig, dass das Budget der Knackpunkt ist?'):
    """tool_input-Form wie sie der Bewerter liefert — mit den beiden Kopfzeilen-Feldern."""
    return {
        'bedarfs_ermittlung': [
            {'beleg_zitat': 'Wie loesen Sie das heute?', 'beobachtung': 'Offene Frage.', 'auspraegung': 'stark'}
        ],
        'gespraechs_eroeffnung': [
            {'beleg_zitat': 'Ich rufe wegen X an.', 'beobachtung': 'Einstieg klar.', 'auspraegung': 'ok'}
        ],
        'einwand_behandlung': [
            {'beleg_zitat': 'Das ist zu teuer.', 'beobachtung': 'Gespiegelt.', 'auspraegung': 'ok'}
        ],
        'gespraechsfuehrung': [
            {'beleg_zitat': 'OK, tschues.', 'beobachtung': 'Gut gefuehrt.', 'auspraegung': 'ok'}
        ],
        'compliance_violation': False,
        'compliance_beleg_zitat': '',
        'headline_observation': headline,
        'headline_beleg_zitat': beleg,
    }


def test_kopfzeile_landet_in_observations():
    """Die beiden Schema-Felder landen als observations_jsonb['_kopfzeile'] — beide Werte."""
    headline = 'Der Berater hat den Preis-Einwand ruhig gespiegelt statt zu rechtfertigen.'
    beleg = 'Verstehe ich richtig, dass das Budget der Knackpunkt ist?'

    observations, _ratings = jr._parse_judge_output(_tool_input_mit_kopfzeile(headline, beleg))

    assert '_kopfzeile' in observations, "'_kopfzeile' fehlt in observations_jsonb"
    kopf = observations['_kopfzeile']
    assert kopf['beobachtung'] == headline
    assert kopf['beleg_zitat'] == beleg
    # 'schema' versioniert NUR diesen Teilblock (DIMENSIONS_VERSION bleibt unveraendert).
    assert kopf['schema'] == 1


def test_kopfzeile_ist_nicht_in_ratings():
    """Die Kopfzeile ist keine Auspraegung und keine Note — sie darf nicht in ratings landen.
    Der bestehende Vertrag fuer '_compliance' bleibt daneben unveraendert."""
    _observations, ratings = jr._parse_judge_output(_tool_input_mit_kopfzeile())

    assert '_kopfzeile' not in ratings, "'_kopfzeile' darf NICHT in ratings_jsonb stehen"
    assert '_compliance' not in ratings, "'_compliance' darf NICHT in ratings_jsonb stehen"
    # Gepaarter Existenz-Anker: ratings ist nicht einfach leer.
    valid_keys = {d['key'] for d in DIMENSIONS}
    assert set(ratings) and set(ratings) <= valid_keys


def test_kopfzeile_fehlend_ergibt_leere_strings():
    """Liefert das Modell die Felder nicht, steht der Schluessel trotzdem da — leer, kein KeyError.

    Ein fehlender Schluessel und ein ehrliches "nichts" waeren im Anzeige-Pfad sonst nicht
    unterscheidbar (dieselbe Form-Garantie-Haltung wie in routes/dashboard.py)."""
    tool_input = _tool_input_mit_kopfzeile()
    del tool_input['headline_observation']
    del tool_input['headline_beleg_zitat']

    observations, _ratings = jr._parse_judge_output(tool_input)

    assert observations['_kopfzeile']['beobachtung'] == ''
    assert observations['_kopfzeile']['beleg_zitat'] == ''
    assert observations['_kopfzeile']['schema'] == 1


def test_schema_verlangt_kopfzeile():
    """JUDGE_TOOL verlangt beide Kopfzeilen-Felder — Runtime-Assertion auf die Datenstruktur.

    Ein Pflichtfeld ist hier vertretbar (anders als bei der "einen Sache"): ein BESTER MOMENT
    existiert in jedem Gespraech, das das Substanz-Tor passiert hat. Der Schutz greift hinten —
    das Beleg-Zitat laeuft durch _pruefe_belege (Plan 05 Task 2)."""
    schema = jr.JUDGE_TOOL['input_schema']
    props = schema['properties']

    assert 'headline_observation' in props, 'headline_observation fehlt als Top-Level-Feld'
    assert 'headline_beleg_zitat' in props, 'headline_beleg_zitat fehlt als Top-Level-Feld'
    assert props['headline_observation']['type'] == 'string'
    assert props['headline_beleg_zitat']['type'] == 'string'

    required = schema['required']
    assert 'headline_observation' in required
    assert 'headline_beleg_zitat' in required
    # Gepaarter Existenz-Anker: die Bestands-Pflichtfelder stehen unveraendert daneben.
    assert 'compliance_violation' in required
    for dim in DIMENSIONS:
        assert dim['key'] in required


def test_prompt_hat_keinen_fokus_schluessel():
    """Der Bewertungs-Auftrag kennt WEDER den Fokus-Katalog NOCH einen seiner Schluessel.

    Strukturell, nicht Sorgfalt: der Fokus entsteht erst NACH dem Modell-Aufruf, im Code
    (SPEC Constraint: "Der Beobachter kennt weder die NERVE-Vorschlaege noch den Fokus")."""
    call = _make_call()
    segments = [
        _make_segment(1, 'berater', 100, 'Guten Tag, darf ich kurz stoeren?'),
        _make_segment(2, 'kunde', 2000, 'Was wollen Sie?'),
    ]
    events = []

    system_str, user_str = jr._build_judge_prompt(call, events, _fake_profile_briefing(), segments)
    full_prompt = system_str + ' ' + user_str

    for verboten in ['focus', 'fokus', 'negative_phrases', 'we_not_i',
                     'problem_language', 'reason_for_call', 'top reps']:
        assert verboten not in full_prompt.lower(), (
            f"Katalog-Begriff '{verboten}' steht im Bewertungs-Auftrag — der Beobachter ist nicht mehr blind."
        )

    # Gepaarte EXISTENZ-Anker: "nicht gefunden" darf nicht von "nichts gebaut" kommen.
    assert '[#1 berater' in user_str
    assert 'headline_observation' in user_str
    assert len(user_str) > 200


def test_genau_ein_llm_aufruf(monkeypatch):
    """run_behavior_judge feuert GENAU EINEN messages.create-Aufruf — die mechanische Zusage
    "kein zusaetzlicher KI-Aufruf" (Punkt 25, Latenz). Die Kosten-Gegenprobe an echten Daten
    (api_cost_log vorher/nachher) kommt im Deploy-Checkpoint von Plan 07 dazu."""
    call = _make_call()
    segments = [_make_segment(1, 'berater', 100, 'Probe-Satz fuer den Zaehl-Test.')]
    events = []
    zaehler = {'n': 0}

    def _zaehl_create(**kwargs):
        zaehler['n'] += 1
        return _make_tool_response()

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=_zaehl_create))
    monkeypatch.setattr(jr, 'claude_client', fake_client)
    monkeypatch.setattr(jr, 'build_profile_context', lambda *a, **k: _fake_profile_briefing())

    fake_db = MagicMock()
    fake_query = MagicMock()
    fake_query.filter.return_value.order_by.return_value.all.return_value = segments
    fake_db.query.return_value = fake_query

    result = jr.run_behavior_judge(call, events, fake_db)

    # Gepaarter Existenz-Anker: der Lauf ist wirklich durchgelaufen (nicht im Fehler-Mantel
    # gelandet, wo 0 Aufrufe ebenfalls "1 nicht ueberschritten" ergaeben).
    assert result.get('status') == 'judged', f"Judge-Lauf endete mit {result.get('status')}"
    assert zaehler['n'] == 1, f"{zaehler['n']} LLM-Aufrufe statt genau 1 — die Latenz-Zusage ist gebrochen."


# ════════════════════════════════════════════════════════════════════════════════════
# METRIK-1 Plan 07 Nachtrag (Andre-Entscheidung 16.08.): die Redeanteil-Norm fliegt
# ERSATZLOS aus dem Bewerter-Auftrag.
#
# WARUM — belegter Schaden am Nutzer, kein Schoenheitsfehler. Aus der Bewertung des
# Anrufs vom 16.08. 20:50:57 woertlich:
#   „Der Kunde kommt im gesamten Transkript nicht zu Wort (0 % Redeanteil vs. 100 %
#    Berater), was weit unter der Kaltakquise-Norm von ~45 % Kunde liegt."
# Im cold_call hoeren wir den Kunden BAUBEDINGT gar nicht: `diarize=is_meeting` und
# `log_sp` hart 0 (services/deepgram_service.py). Der Redeanteil ist dort eine
# KONSTANTE, die wie eine Messung aussieht — das Tabellen-Schild von
# transcript_segments sagt genau diesen Satz. Die KI haelt dem Berater also einen Wert
# vor, den er nicht beeinflussen kann und der nichts misst. Das ist dieselbe Krankheit,
# derentwegen diese ganze Phase existiert — nur im Prompt statt im Dashboard.
#
# ⚠ Die fruehere Vertagung auf 4.0.2 zielte auf die DASHBOARD-Zeile und hat den
# Bewerter-Auftrag nicht mit abgedeckt. Das ist die Luecke, die dieser Test schliesst.
#
# ERSATZ-RECHNUNG: NICHT hier. Sie gehoert nach 4.0.2 und ist von Andre am 16.08.
# definiert: Spanne = letztes Ende minus erster Anfang (ab dem ersten gesprochenen
# Wort, nicht ab Verbindungsaufbau); Redeanteil = Sprechzeit / Spanne. Beide Werte
# liegen seit ZEITSTEMPEL-1 je Abschnitt vor. Solange sie nicht angeschlossen ist,
# sagt der Bewerter zum Redeanteil GAR NICHTS — lieber schweigen als falsch ruegen.
# ════════════════════════════════════════════════════════════════════════════════════
def test_prompt_hat_keine_redeanteil_norm():
    """Im Bewerter-Auftrag steht keine Redeanteil-Norm mehr — ersatzlos, kein Ersatzwert.

    ⚠ ANKER AUF DIE CODE-FORM, nicht auf das nackte Wort „Redeanteil": Plan 06 ist genau
    darueber gestolpert (der Anker traf eine legitime Uebungs-Empfehlung an ganz anderer
    Stelle). Geprueft werden deshalb die drei Zeichenketten, die NUR diese Norm haben kann —
    ihr Name und ihre beiden Zahlenwerte.

    GEPAARTER EXISTENZ-ANKER in derselben Funktion: der Prinzipien-Block und seine Nachbarn
    stehen weiterhin im Auftrag. Ohne ihn waere der Test auch dann gruen, wenn beim naechsten
    Aufraeumen der halbe System-Prompt mitginge — „nicht gefunden" waere von „nichts gebaut"
    nicht zu unterscheiden."""
    call = _make_call()
    segments = [
        _make_segment(1, 'berater', 100, 'Guten Tag, darf ich kurz stoeren?'),
        _make_segment(2, 'kunde', 2000, 'Was wollen Sie?'),
    ]
    system_str, user_str = jr._build_judge_prompt(call, [], _fake_profile_briefing(), segments)
    full_prompt = system_str + ' ' + user_str

    # ── Existenz-Anker ZUERST: der Auftrag wurde ueberhaupt gebaut ────────────────────────
    assert '== BEWERTUNGS-PRINZIPIEN ==' in system_str, (
        'Der Prinzipien-Block fehlt komplett — beim Streichen der Norm ist mehr mitgegangen '
        'als die eine Regel.'
    )
    assert 'Laengen-Neutralitaet' in system_str, 'Das Verbosity-Bias-Prinzip ist mitgegangen.'
    assert 'Hard-Cap Gespraechsfuehrung' in system_str, (
        'Das Belaestigungs-Hard-Cap ist mitgegangen — das ist ein Sicherheits-Prinzip.'
    )
    assert len(system_str) > 500, 'Der System-Prompt ist auffaellig kurz — es fehlt zu viel.'

    # ── Abwesenheits-Anker auf die CODE-FORM der Norm ────────────────────────────────────
    assert 'Kaltakquise-Redeanteil-Norm' not in full_prompt, (
        'Die Redeanteil-Norm steht noch im Bewerter-Auftrag. Im cold_call ist der Redeanteil '
        'baubedingt konstant 100 % — die KI ruegt den Berater fuer etwas, das er nicht '
        'beeinflussen kann und das nichts misst.'
    )
    assert '45% Kunde' not in full_prompt, 'Der Kunden-Zielwert der Norm steht noch im Auftrag.'
    assert '55% Berater' not in full_prompt, 'Der Berater-Zielwert der Norm steht noch im Auftrag.'

    # ── Und kein ERSATZWERT durch die Hintertuer ─────────────────────────────────────────
    # Ersatzlos heisst ersatzlos: solange keine gueltige Rechnung existiert (4.0.2), darf der
    # Bewerter zum Redeanteil GAR NICHTS sagen — auch nicht „ungefaehr" oder „ausgewogen".
    assert '43:57' not in full_prompt, 'Die verworfene Gegen-Norm steht im Auftrag.'
    assert 'Redeanteil-Norm' not in full_prompt, (
        'Es steht wieder eine Redeanteil-Norm im Auftrag — nur anders benannt.'
    )
