"""Phase 08.23.2.PERSID Plan 05 — Tests fuer Familie C (Welle 4).

Familie C: conversation_log, painpoints, gegenargument_log, phasen_log,
covered_phases, kaufbereitschaft(_verlauf), aktive_phase_idx — alle per-SID.

TDD-Verhalten (D-10): Tests werden zusammen mit der Implementierung committet (GREEN).
D-10: kein committeter roter Test (deploy.sh-Gate). Rot-Beweis: manuell vor Implementierung.

Tests pruefen Runtime-State-Mutation, nicht Code-Existenz (CLAUDE.md Test-Qualitaets-Regel).
Kein Source-Presence-False-Green: kein inspect.getsource / grep auf Quelldateien.
"""

import inspect
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import services.live_session as ls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def two_sessions():
    """Starte zwei isolierte Sessions und raeume hinterher auf."""
    sid_a = 'test-sid-famC-alpha-05'
    sid_b = 'test-sid-famC-beta-05'
    for s in (sid_a, sid_b):
        ls.pop_session_state(s)
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript.pop(s, None)
        with ls._per_sid_coaching_lock:
            ls._per_sid_coaching_buffer.pop(s, None)

    ls.init_session_state(sid_a, user_id=501, org_id=10)
    ls.init_session_state(sid_b, user_id=502, org_id=20)

    yield sid_a, sid_b

    for s in (sid_a, sid_b):
        ls.pop_session_state(s)
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript.pop(s, None)
        with ls._per_sid_coaching_lock:
            ls._per_sid_coaching_buffer.pop(s, None)


# ---------------------------------------------------------------------------
# Test 1: Gepaarte Isolation — conversation_log, painpoints, gegenargument_log,
#          phasen_log, covered_phases trennen A von B
# ---------------------------------------------------------------------------

def test_conversation_log_isolation(two_sessions):
    """Zwei SIDs: Append auf A landet NUR in A, nicht in B.

    Prueft Runtime-State-Mutation (dict write + read) — kein Source-Presence-False-Green.
    """
    sid_a, sid_b = two_sessions
    ts = datetime.now().strftime('%H:%M:%S')

    # Direkt in per-SID state schreiben (wie claude_service.py nach Migration)
    with ls._session_state_lock:
        if sid_a in ls._session_state:
            ls._session_state[sid_a]['conversation_log'].append(
                {'ts': ts, 'type': 'transcript', 'speaker': 0, 'text': 'AlphaSatz', 'data': None}
            )
    with ls._session_state_lock:
        if sid_b in ls._session_state:
            ls._session_state[sid_b]['conversation_log'].append(
                {'ts': ts, 'type': 'transcript', 'speaker': 0, 'text': 'BetaSatz', 'data': None}
            )

    with ls._session_state_lock:
        log_a = list(ls._session_state[sid_a]['conversation_log'])
        log_b = list(ls._session_state[sid_b]['conversation_log'])

    texts_a = [e['text'] for e in log_a]
    texts_b = [e['text'] for e in log_b]

    assert 'AlphaSatz' in texts_a, f"AlphaSatz fehlt in SID-A log: {texts_a!r}"
    assert 'BetaSatz' not in texts_a, f"BetaSatz leck in SID-A log: {texts_a!r}"
    assert 'BetaSatz' in texts_b, f"BetaSatz fehlt in SID-B log: {texts_b!r}"
    assert 'AlphaSatz' not in texts_b, f"AlphaSatz leck in SID-B log: {texts_b!r}"


def test_painpoints_isolation(two_sessions):
    """painpoints pro SID — keine Vermischung."""
    sid_a, sid_b = two_sessions
    ts = datetime.now().strftime('%H:%M:%S')

    with ls._session_state_lock:
        if sid_a in ls._session_state:
            ls._session_state[sid_a]['painpoints'].append({'ts': ts, 'text': 'Alpha-Pain'})
        if sid_b in ls._session_state:
            ls._session_state[sid_b]['painpoints'].append({'ts': ts, 'text': 'Beta-Pain'})

    with ls._session_state_lock:
        pp_a = [p['text'] for p in ls._session_state[sid_a]['painpoints']]
        pp_b = [p['text'] for p in ls._session_state[sid_b]['painpoints']]

    assert 'Alpha-Pain' in pp_a
    assert 'Beta-Pain' not in pp_a
    assert 'Beta-Pain' in pp_b
    assert 'Alpha-Pain' not in pp_b


def test_gegenargument_log_isolation(two_sessions):
    """gegenargument_log pro SID — keine Vermischung."""
    sid_a, sid_b = two_sessions
    ts = datetime.now().strftime('%H:%M:%S')
    entry = lambda name: {
        'ts': ts, 'einwand_typ': name, 'einwand_zitat': '', 'ist_vorwand': False,
        'gegenargument_1': '', 'gegenargument_2': '', 'gewaehlte_option': None,
        'kb_vorher': 30, 'kb_nachher': None, 'kb_delta': None, 'erfolgreich': None,
    }

    with ls._session_state_lock:
        if sid_a in ls._session_state:
            ls._session_state[sid_a]['gegenargument_log'].append(entry('alpha_einwand'))
        if sid_b in ls._session_state:
            ls._session_state[sid_b]['gegenargument_log'].append(entry('beta_einwand'))

    with ls._session_state_lock:
        ga_a = [g['einwand_typ'] for g in ls._session_state[sid_a]['gegenargument_log']]
        ga_b = [g['einwand_typ'] for g in ls._session_state[sid_b]['gegenargument_log']]

    assert 'alpha_einwand' in ga_a
    assert 'beta_einwand' not in ga_a
    assert 'beta_einwand' in ga_b
    assert 'alpha_einwand' not in ga_b


def test_phasen_log_isolation(two_sessions):
    """phasen_log pro SID."""
    sid_a, sid_b = two_sessions
    ts = datetime.now().strftime('%H:%M:%S')

    with ls._session_state_lock:
        if sid_a in ls._session_state:
            ls._session_state[sid_a]['phasen_log'].append({'ts': ts, 'nach_phase': 'Opener'})
        if sid_b in ls._session_state:
            ls._session_state[sid_b]['phasen_log'].append({'ts': ts, 'nach_phase': 'Pitch'})

    with ls._session_state_lock:
        ph_a = [p['nach_phase'] for p in ls._session_state[sid_a]['phasen_log']]
        ph_b = [p['nach_phase'] for p in ls._session_state[sid_b]['phasen_log']]

    assert 'Opener' in ph_a
    assert 'Pitch' not in ph_a
    assert 'Pitch' in ph_b
    assert 'Opener' not in ph_b


def test_covered_phases_isolation(two_sessions):
    """covered_phases pro SID."""
    sid_a, sid_b = two_sessions

    with ls._session_state_lock:
        if sid_a in ls._session_state:
            ls._session_state[sid_a]['covered_phases'].add(0)
        if sid_b in ls._session_state:
            ls._session_state[sid_b]['covered_phases'].add(2)

    with ls._session_state_lock:
        cp_a = set(ls._session_state[sid_a]['covered_phases'])
        cp_b = set(ls._session_state[sid_b]['covered_phases'])

    assert 0 in cp_a
    assert 2 not in cp_a
    assert 2 in cp_b
    assert 0 not in cp_b


# ---------------------------------------------------------------------------
# Test 2: S4 RMW — update_kaufbereitschaft(sid, delta) atomar
# ---------------------------------------------------------------------------

def test_update_kaufbereitschaft_per_sid_signature():
    """update_kaufbereitschaft nimmt sid als ersten Parameter.

    inspect.signature() prueft Runtime-API (CLAUDE.md: OK fuer Parameter-Verifikation).
    """
    sig = inspect.signature(ls.update_kaufbereitschaft)
    params = list(sig.parameters.keys())
    assert 'sid' in params, (
        f"update_kaufbereitschaft muss 'sid' als Parameter haben. Aktuell: {params}"
    )
    assert params[0] == 'sid', (
        f"'sid' muss erster Parameter sein, ist: {params[0]!r}"
    )


def test_update_kaufbereitschaft_isolates_per_sid(two_sessions):
    """Zwei parallele update_kaufbereitschaft-Calls sind unabhaengig konsistent.

    State-Mutation: kaufbereitschaft und kaufbereitschaft_verlauf pro SID.
    Kein Lost-Update: clamp+append atomar (S4).
    """
    sid_a, sid_b = two_sessions

    # Startwert setzen
    with ls._session_state_lock:
        ls._session_state[sid_a]['kaufbereitschaft'] = 50
        ls._session_state[sid_b]['kaufbereitschaft'] = 40
        ls._session_state[sid_a]['kaufbereitschaft_verlauf'] = []
        ls._session_state[sid_b]['kaufbereitschaft_verlauf'] = []

    results = {}
    errors = []

    def update_a():
        try:
            ls.update_kaufbereitschaft(sid_a, +5)
            results['a'] = None
        except Exception as e:
            errors.append(f'sid_a: {e}')

    def update_b():
        try:
            ls.update_kaufbereitschaft(sid_b, +3)
            results['b'] = None
        except Exception as e:
            errors.append(f'sid_b: {e}')

    t1 = threading.Thread(target=update_a)
    t2 = threading.Thread(target=update_b)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert not errors, f"Fehler in update_kaufbereitschaft: {errors}"

    with ls._session_state_lock:
        kb_a = ls._session_state[sid_a]['kaufbereitschaft']
        kb_b = ls._session_state[sid_b]['kaufbereitschaft']
        verlauf_a = list(ls._session_state[sid_a]['kaufbereitschaft_verlauf'])
        verlauf_b = list(ls._session_state[sid_b]['kaufbereitschaft_verlauf'])

    assert kb_a == 55, f"SID-A kaufbereitschaft erwartet 55, got {kb_a}"
    assert kb_b == 43, f"SID-B kaufbereitschaft erwartet 43, got {kb_b}"
    assert len(verlauf_a) == 1, f"SID-A verlauf sollte 1 Eintrag haben: {verlauf_a!r}"
    assert len(verlauf_b) == 1, f"SID-B verlauf sollte 1 Eintrag haben: {verlauf_b!r}"
    assert verlauf_a[0]['wert'] == 55
    assert verlauf_b[0]['wert'] == 43


def test_update_kaufbereitschaft_no_op_without_sid():
    """update_kaufbereitschaft ohne sid → No-Op, kein Fehler (D-02)."""
    # Soll nicht crashen
    try:
        ls.update_kaufbereitschaft(None, +5)
        ls.update_kaufbereitschaft('', +5)
    except Exception as e:
        pytest.fail(f"update_kaufbereitschaft ohne sid soll No-Op sein, crashte aber: {e}")


# ---------------------------------------------------------------------------
# Test 3: B5 — aktive_phase_idx beide Reader per-SID, kein AttributeError
# ---------------------------------------------------------------------------

def test_aktive_phase_idx_readable_per_sid(two_sessions):
    """_session_state[sid]['aktive_phase_idx'] ist pro SID lesbar ohne phase_lock.

    Prueft: per-SID-Read gibt korrekten Wert zurueck (State-Mutation-Test).
    """
    sid_a, sid_b = two_sessions

    with ls._session_state_lock:
        ls._session_state[sid_a]['aktive_phase_idx'] = 2
        ls._session_state[sid_b]['aktive_phase_idx'] = 0

    with ls._session_state_lock:
        idx_a = ls._session_state[sid_a].get('aktive_phase_idx', 0)
        idx_b = ls._session_state[sid_b].get('aktive_phase_idx', 0)

    assert idx_a == 2, f"SID-A aktive_phase_idx erwartet 2, got {idx_a}"
    assert idx_b == 0, f"SID-B aktive_phase_idx erwartet 0, got {idx_b}"


def test_phase_lock_deleted_from_live_session():
    """phase_lock darf nach Migration nicht mehr in live_session existieren (B5).

    hasattr-Pruefung: als Pflicht-Deletion-Gate (nicht als Presence-Schutz).
    """
    assert not hasattr(ls, 'phase_lock'), (
        "phase_lock ist noch in live_session definiert. B5: BEIDE aktive_phase_idx-Reader "
        "sind per-SID → phase_lock ist ueberfluessig und wurde geloescht."
    )


def test_aktive_phase_idx_global_deleted_from_live_session():
    """aktive_phase_idx Modul-Global darf nach Migration nicht mehr in live_session existieren."""
    assert not hasattr(ls, 'aktive_phase_idx'), (
        "aktive_phase_idx ist noch als Modul-Global in live_session definiert. "
        "Nach per-SID-Migration (Plan 05 Task 3) muss es entfernt sein."
    )


# ---------------------------------------------------------------------------
# Test 4: N-3 — _build_log_content nimmt bs als Parameter
# ---------------------------------------------------------------------------

def test_build_log_content_signature_takes_bs():
    """_build_log_content(bs, ...) nimmt bs als ersten Parameter.

    inspect.signature() prueft Runtime-API (CLAUDE.md: OK fuer Parameter-Verifikation).
    N-3: KEIN eigener _load_beenden_state-Aufruf im Helfer — Caller reicht _bs durch.
    """
    sig = inspect.signature(ls._build_log_content)
    params = list(sig.parameters.keys())
    assert len(params) >= 1, "_build_log_content muss mindestens 1 Parameter haben"
    assert params[0] == 'bs', (
        f"Erster Parameter muss 'bs' sein (per-SID State), ist: {params[0]!r}"
    )


def test_build_log_content_reads_from_bs(two_sessions):
    """_build_log_content(bs) liest conversation_log aus dem uebergebenen State.

    Wenn bs['conversation_log'] einen Transcript-Eintrag hat, erscheint er im Output.
    Das ist ein Function-Call-Return-Test — kein Source-Presence-False-Green.
    """
    sid_a, _ = two_sessions
    ts_str = '10:00:00'
    fake_bs = {
        'conversation_log': [
            {'ts': ts_str, 'type': 'transcript', 'speaker': 0, 'text': 'TestTranscriptAlpha', 'data': None}
        ],
        'painpoints': [],
        'gegenargument_log': [],
        'phasen_log': [],
    }

    content = ls._build_log_content(fake_bs)
    assert 'TestTranscriptAlpha' in content, (
        f"_build_log_content liest NICHT aus dem uebergebenen bs. "
        f"Erwartet 'TestTranscriptAlpha' im Output."
    )


# ---------------------------------------------------------------------------
# Test 5: Module-Globale Familie C — Abwesenheits-Gates
# ---------------------------------------------------------------------------

def test_conversation_log_global_deleted():
    """conversation_log Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'conversation_log'), (
        "conversation_log ist noch als Modul-Global in live_session — "
        "nach per-SID-Migration (Plan 05 Task 3) entfernen."
    )


def test_painpoints_global_deleted():
    """painpoints Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'painpoints'), (
        "painpoints ist noch als Modul-Global in live_session — "
        "nach per-SID-Migration entfernen."
    )


def test_gegenargument_log_global_deleted():
    """gegenargument_log Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'gegenargument_log'), (
        "gegenargument_log ist noch als Modul-Global in live_session — entfernen."
    )


def test_phasen_log_global_deleted():
    """phasen_log Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'phasen_log'), (
        "phasen_log ist noch als Modul-Global in live_session — entfernen."
    )


def test_kaufbereitschaft_global_deleted():
    """kaufbereitschaft Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'kaufbereitschaft'), (
        "kaufbereitschaft ist noch als Modul-Global in live_session — entfernen."
    )


def test_covered_phases_global_deleted():
    """covered_phases Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'covered_phases'), (
        "covered_phases ist noch als Modul-Global in live_session — entfernen."
    )


def test_log_lock_global_deleted():
    """log_lock Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'log_lock'), (
        "log_lock ist noch als Modul-Global in live_session — entfernen."
    )


def test_kb_lock_global_deleted():
    """kb_lock Modul-Global darf nach Task 3 nicht mehr existieren."""
    assert not hasattr(ls, 'kb_lock'), (
        "kb_lock ist noch als Modul-Global in live_session — entfernen."
    )
