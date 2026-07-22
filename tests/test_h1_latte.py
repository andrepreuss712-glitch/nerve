"""
tests/test_h1_latte.py
──────────────────────────────────────────────────────────────────────────
Phase 08.23.2.H1 Plan 03 (WEG 1, Welle 3 — D2-LATTE-WAECHTER)

Runtime-Ratsche fuer die Akzeptanz-Latte (Bau-Vorgabe 5 / D2): beweist, dass
der GEMERGTE Call (analysiere_und_klassifiziere, MERGE_ANALYSE_QA='1') JEDEN
lebenden Call-1-Konsumenten weiterhin mit gleichwertigen Werten speist. Wird
ROT, sobald eine kuenftige Merge-Aenderung einem Konsumenten den Wert entzieht.

CLAUDE.md Test-Qualitaets-Regel: ausschliesslich Runtime-Verhalten —
Function-Call- (Mock-Assert) + State-Mutation-Asserts (per-SID-State nach dem
Tick). KEIN inspect.getsource, KEIN 'string' in src, KEIN hasattr-als-Schutz,
KEIN grep auf Quellcode. Kein echter LLM-/Netz-/DB-Call (alle Naehte gemockt),
laeuft im Standard-Gate `not live and not perf` (kein -m live).

Fahrmuster: EIN echter analyse_loop-Tick pro Fall (_OneShotTrigger wie
test_h1_merge_wiring / test_medium_lane_intent_event_live), Haiku +
DB/emit/moment/anon-Naehte hermetisch gemockt.

Die 8 Latte-Punkte (aus <latte_liste> im PLAN):
  1 Medium-Lane intent_event (Typ/confidence/Zitat) bei einwand
  2 Moment open (einwand) + close('advisor_answered') (cold_call, subst. Turn)
  3 Kaufbereitschaft-Update -5 bei intensitaet=='hoch'
  4 gegenargument_log: einwand_typ==intent_type, ist_vorwand==(intent_type=='vorwand')
  5 Readiness-Flags -> readiness_score/bucket per-SID (> Baseline ohne Flags)
  6 Dynamische EWB-Buttons: last_einwand_typ == ergebnis['typ'] (Freitext, != intent_type)
  7 Phase-Kadenz: jeder 5. Cycle -> classify_phase genau EINMAL (Zaehler per-SID)
  8 Abstain-intent_event (low-conf, QA-Sektion) + FAQ used_count-Inkrement
──────────────────────────────────────────────────────────────────────────
"""

import time
import uuid
import types
from unittest.mock import MagicMock

import pytest

import config
import services.claude_service as cs


# ── Fahrwerk ─────────────────────────────────────────────────────────────────

class _StopLoop(Exception):
    """Sentinel: verlaesst den `while True`-Daemon analyse_loop nach den Ticks."""


class _OneShotTrigger:
    """Erster wait() -> True (ein Tick), zweiter -> _StopLoop. clear() no-op."""

    def __init__(self):
        self._calls = 0

    def wait(self, timeout=None):
        self._calls += 1
        if self._calls > 1:
            raise _StopLoop()
        return True

    def clear(self):
        pass


class _MultiTickTrigger:
    """Fuellt vor JEDEM der n Ticks den per-SID-Transcript-Buffer neu (der Loop
    leert ihn nach Konsum) und stoppt nach n Ticks. Fuer die Phase-Kadenz-Probe."""

    def __init__(self, ls, sid, n):
        self._ls = ls
        self._sid = sid
        self._n = n
        self._i = 0

    def wait(self, timeout=None):
        self._i += 1
        if self._i > self._n:
            raise _StopLoop()
        self._ls._per_sid_transcript[self._sid] = [
            {'text': 'der kunde sagt hier etwas neues dazu',
             'line_id': self._i, 't_start': time.monotonic()},
        ]
        return True

    def clear(self):
        pass


def _merged(*, einwand=True, intent_type='echter_einwand', typ='Preis-Einwand',
            confidence=0.8, intensitaet='hoch', einwand_zitat='zu teuer',
            qa=None, **flags):
    """Realistisches Merged-Ergebnis (Einwand-Sektion top-level + optional qa)."""
    d = {
        'einwand': einwand,
        'intent_type': intent_type,
        'typ': typ,                       # Freitext-EWB-Label (Punkt 6: != intent_type)
        'confidence': confidence,
        'intensitaet': intensitaet,
        'einwand_zitat': einwand_zitat,
        'gegenargument_1': 'Ansatz A?',
        'gegenargument_2': 'Ansatz B?',
    }
    d.update(flags)                       # Readiness-Flags (kaufsignal=... etc.)
    if qa is not None:
        d['qa'] = qa
    return d


def _seed(monkeypatch, sid, *, mode='cold_call', line_id=1, kw_fired_for_line=None,
          text='das ist mir viel zu teuer', active_profile_id=None):
    """Seedet den echten live_session-State fuer EINEN Tick und stubbt alle
    DB/moment/anon/kb-Naehte hermetisch (kein Netz, keine DB). Gibt das
    live_session-Modul zurueck (fuer per-SID-State-Asserts)."""
    import services.live_session as ls

    monkeypatch.setitem(ls._session_state, sid, {
        'user_id': 1,
        'org_id': 1,
        'mode': mode,
        'active_profile_id': active_profile_id,
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
            'slot1_variant_busy_until': 0.0,   # TOTER Guard (nirgends gesetzt) — nicht als
                                               # guard-frei-Beweis genutzt; s. Punkt 8-Kommentar.
        },
    })
    monkeypatch.setitem(ls._per_sid_transcript, sid, [
        {'text': text, 'line_id': line_id, 't_start': time.monotonic()},
    ])
    monkeypatch.setattr(ls, 'analyse_trigger', _OneShotTrigger())

    monkeypatch.setattr(ls, 'get_or_open_moment', MagicMock(return_value='iid-1'), raising=False)
    monkeypatch.setattr(ls, 'close_moment', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, '_durable_call_id', MagicMock(return_value='call-xyz'), raising=False)
    monkeypatch.setattr(ls, 'get_anonymisierer', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, 'update_kaufbereitschaft', MagicMock(return_value=None), raising=False)
    monkeypatch.setattr(ls, 'get_profile_for_sid', MagicMock(return_value=('', {})), raising=False)
    # Anonymisierung als deterministischer Passthrough -> Freitext-Werte bleiben
    # nachpruefbar (triggering_text / einwand_zitat).
    monkeypatch.setattr('services.anonymization.anonymize_output', lambda text, cache: text)
    return ls


def _run_tick():
    with pytest.raises(_StopLoop):
        cs.analyse_loop()


def _patch_emit(monkeypatch):
    mock_emit = MagicMock()
    monkeypatch.setattr('services.intent_event_writer.emit_intent_event', mock_emit)
    return mock_emit


# ── Punkt 1: Medium-Lane intent_event (Typ/confidence/Zitat) ─────────────────

def test_01_medium_lane_intent_event_gets_merged_values(monkeypatch):
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    text = 'das ist mir viel zu teuer'
    _seed(monkeypatch, sid, text=text)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True, intent_type='echter_einwand',
                            confidence=0.8,
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    mock_emit = _patch_emit(monkeypatch)

    _run_tick()

    # Runtime-Assert: emit_intent_event (Function-Call) mit den Merged-Werten.
    med = [c for c in mock_emit.call_args_list
           if c.kwargs.get('source') == 'llm_inferred' and not c.kwargs.get('abstained')]
    assert len(med) == 1, "Genau EIN Medium-Lane intent_event pro Einwand-Tick."
    k = med[0].kwargs
    assert k['intent_type'] == 'echter_einwand'         # Typ aus dem Merged-Ergebnis
    assert k['confidence'] == pytest.approx(0.8)         # confidence durchgereicht (< cold-call-cap 0.85)
    assert k['triggering_text'] == text                  # Zitat/Ausloeser (anon-Passthrough)


# ── Punkt 2: Moment open (einwand) + close (Nicht-Einwand, subst. Turn) ──────

def test_02_moment_open_on_einwand_and_close_on_advisor_answer(monkeypatch):
    # 2a) einwand=true -> get_or_open_moment aufgerufen
    sid_o = f"latte-{uuid.uuid4().hex[:8]}"
    ls = _seed(monkeypatch, sid_o)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True,
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)
    _run_tick()
    ls.get_or_open_moment.assert_called_once()           # Function-Call-Assert: Fenster geoeffnet

    # 2b) einwand=false + cold_call + substanzieller Turn (>=6 Woerter)
    #     -> close_moment('advisor_answered')
    sid_c = f"latte-{uuid.uuid4().hex[:8]}"
    ls2 = _seed(monkeypatch, sid_c, mode='cold_call',
                text='ich verstehe das gut und schlage folgendes vor')  # 8 Woerter
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=False,
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _run_tick()
    ls2.close_moment.assert_called_once_with(sid_c, reason='advisor_answered')


# ── Punkt 3: Kaufbereitschaft -5 bei intensitaet=='hoch' ─────────────────────

def test_03_kaufbereitschaft_minus5_on_hoch(monkeypatch):
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    ls = _seed(monkeypatch, sid)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True, intensitaet='hoch',
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)

    _run_tick()

    # Function-Call-Assert: Delta -5 (hoch); der Merge speist intensitaet weiter.
    ls.update_kaufbereitschaft.assert_called_once_with(sid, -5)


# ── Punkt 4: gegenargument_log (einwand_typ, ist_vorwand abgeleitet) ─────────

def test_04_gegenargument_log_entry_from_merged(monkeypatch):
    # 4a) echter_einwand -> einwand_typ==intent_type, ist_vorwand False
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    ls = _seed(monkeypatch, sid)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True, intent_type='echter_einwand',
                            einwand_zitat='zu teuer',
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)
    _run_tick()

    # State-Mutation-Assert: neuer per-SID gegenargument_log-Eintrag.
    log = ls._session_state[sid]['gegenargument_log']
    assert len(log) == 1
    entry = log[-1]
    assert entry['einwand_typ'] == 'echter_einwand'      # == intent_type (§1, migriert)
    assert entry['ist_vorwand'] is False                 # abgeleitet: 'echter_einwand' != 'vorwand'
    assert entry['einwand_zitat'] == 'zu teuer'          # Freitext (anon-Passthrough)
    assert entry['gegenargument_1'] == 'Ansatz A?'
    assert entry['gegenargument_2'] == 'Ansatz B?'

    # 4b) vorwand -> ist_vorwand True (Beweis der Ableitung intent_type=='vorwand')
    sid2 = f"latte-{uuid.uuid4().hex[:8]}"
    ls2 = _seed(monkeypatch, sid2)
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True, intent_type='vorwand',
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _run_tick()
    entry2 = ls2._session_state[sid2]['gegenargument_log'][-1]
    assert entry2['einwand_typ'] == 'vorwand'
    assert entry2['ist_vorwand'] is True


# ── Punkt 5: Readiness-Flags -> readiness_score/bucket per-SID ───────────────

def test_05_readiness_score_reflects_flags(monkeypatch):
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    # einwand=False -> kein einwand_offen-Malus; nur die positiven Flags zaehlen.
    ls = _seed(monkeypatch, sid)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=False,
                            kaufsignal=True, budget_erwaehnt=True, naechster_schritt=True,
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)

    _run_tick()

    # State-Mutation-Assert: die Merged-Flags flossen in den Score (Baseline=30).
    st = ls._session_state[sid]['state']
    assert st['readiness_score'] > 30, "Gesetzte Readiness-Flags muessen den Score ueber die Baseline heben."
    assert st['readiness_bucket'] and st['readiness_bucket'] != 'cold'


# ── Punkt 6: Dynamische EWB-Buttons: last_einwand_typ == ergebnis['typ'] ─────

def test_06_last_einwand_typ_is_freetext_not_intent_type(monkeypatch):
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    ls = _seed(monkeypatch, sid)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    # Freitext-typ ('Preis-Einwand') bewusst != intent_type ('echter_einwand').
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True, intent_type='echter_einwand', typ='Preis-Einwand',
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)

    _run_tick()

    # State-Mutation-Assert: die EWB-Buttons haengen am Freitext-typ, NICHT am
    # intent_type. Verwechslung (intent_type statt typ) macht diesen Test ROT.
    last = ls._session_state[sid]['state']['last_einwand_typ']
    assert last == 'Preis-Einwand'                       # == ergebnis['typ'] (Freitext)
    assert last != 'echter_einwand'                      # != intent_type (der subtile Bug)


# ── Punkt 7: Phase-Kadenz — jeder 5. Cycle triggert classify_phase einmal ────

def test_07_phase_classifier_cadence_every_5th_tick(monkeypatch):
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    ls = _seed(monkeypatch, sid, mode='cold_call')
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=True,
                            qa={'kategorie': 'smalltalk_none', 'confidence': 0.0})))
    _patch_emit(monkeypatch)
    # Phase-/Cold-Call-Naehte stubben (keine Haiku-Calls im Kadenz-Zweig).
    mock_classify_phase = MagicMock(return_value=None)   # None -> detect_phase-Zweig uebersprungen
    monkeypatch.setattr(cs, 'classify_phase', mock_classify_phase)
    monkeypatch.setattr('services.ki_logik.infer_cold_call_context', MagicMock(return_value={}))
    # 5 Ticks fahren (Trigger fuellt den Buffer je Tick neu).
    monkeypatch.setattr(ls, 'analyse_trigger', _MultiTickTrigger(ls, sid, 5))

    _run_tick()

    # Function-Call-Assert + State-Mutation-Assert: Zaehler per-SID auf 5, und die
    # Kadenz (jeder 5.) triggert classify_phase genau EINMAL.
    assert ls._session_state[sid]['state']['phase_cycle_counter'] == 5
    assert mock_classify_phase.call_count == 1


# ── Punkt 8: Abstain-intent_event (low-conf QA) + FAQ used_count-Inkrement ───

def test_08_abstain_event_and_faq_used_count(monkeypatch):
    # 8a) Guard-frei (kw_fired_for != line_id — der LEBENDE D-02-Guard, NICHT der
    #     tote slot1_variant_busy_until-Mutex) + QA low-conf 'frage' ohne FAQ-Match
    #     -> emit_intent_event(abstained=True, intent_type='info_frage').
    sid = f"latte-{uuid.uuid4().hex[:8]}"
    _seed(monkeypatch, sid, line_id=3, kw_fired_for_line=None, text='wie teuer',
          active_profile_id=42)
    monkeypatch.setattr(config, 'MERGE_ANALYSE_QA', '1')
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=False,   # isoliert die QA-Sektion (kein Medium-Lane-Emit)
                            qa={'kategorie': 'frage', 'confidence': 0.1})))  # 0.1 < 0.55
    monkeypatch.setattr(cs, '_qa_load_faqs', MagicMock(return_value=[]))     # kein FAQ-Match-Pfad
    monkeypatch.setattr(cs, '_qa_load_tabu', MagicMock(return_value=[]))
    mock_emit = _patch_emit(monkeypatch)

    _run_tick()

    abstain = [c for c in mock_emit.call_args_list if c.kwargs.get('abstained')]
    assert len(abstain) == 1, "Low-conf QA-Frage ohne FAQ -> genau EIN Abstain-intent_event."
    assert abstain[0].kwargs['intent_type'] == 'info_frage'

    # 8b) FAQ-Match-Pfad -> used_count-Inkrement erreicht (DB-Write-Naht).
    sid2 = f"latte-{uuid.uuid4().hex[:8]}"
    _seed(monkeypatch, sid2, line_id=4, kw_fired_for_line=None, text='wie teuer',
          active_profile_id=42)
    faq = {'id': 77, 'frage_muster': 'wie teuer', 'antwort': 'Antwort X',
           'kategorie': 'preis', 'mode': 'literal'}
    monkeypatch.setattr(cs, 'analysiere_und_klassifiziere',
                        MagicMock(return_value=_merged(
                            einwand=False,
                            qa={'kategorie': 'frage', 'confidence': 0.9})))
    monkeypatch.setattr(cs, '_qa_load_faqs', MagicMock(return_value=[faq]))
    monkeypatch.setattr(cs, '_qa_load_tabu', MagicMock(return_value=[]))
    monkeypatch.setattr('services.qa_pipeline.match_faq', MagicMock(return_value=faq))
    monkeypatch.setattr('services.qa_pipeline.apply_tabu_filter', MagicMock(return_value=False))
    # DB-Naht fuer den used_count-UPDATE stubben (kein echter DB-Call).
    fake_row = types.SimpleNamespace(used_count=0)
    fake_session = MagicMock()
    fake_session.query.return_value.filter_by.return_value.first.return_value = fake_row
    monkeypatch.setattr('database.db.SessionLocal', lambda: fake_session)

    _run_tick()

    # State-Mutation-Assert: der FAQ-used_count-Konsument wird vom Merge-Pfad erreicht.
    assert fake_row.used_count == 1, "FAQ-Match muss used_count inkrementieren (aus der Merged-QA-Sektion)."
    assert fake_session.commit.called


if __name__ == '__main__':
    import sys
    sys.exit(pytest.main([__file__, '-q']))
