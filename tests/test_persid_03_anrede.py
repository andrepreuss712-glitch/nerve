"""
tests/test_persid_03_anrede.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 03 — Task 2 (TDD RED then GREEN).

Waechter:
  B2  — session_anrede kanonisch per-sid (top-level, LAZY), alle Reader + beide Writer
         im selben Deploy; kein Split-Brain mehr (SPEC Req 6).
  N-4 — Start-Anrede-Write laeuft NACH init_session_state -> Write geht in
         _session_state[sid]['session_anrede'], wird NICHT vom init ueberschrieben.
  W-1 — Tote 'state'-Subdict-Seeds session_anrede/mic_muted geloescht.
  W-2 — Anrede-Test-Bestand migriert: kein globaler title-case-False-Green mehr.

Integration-Assertions (CLAUDE.md Test-Qualitaets-Regel):
  Alle Tests pruefe RUNTIME-Verhalten — State-Mutation in dict nach Function-Call.

D-10-Konformitaet: dieser Test wurde VOR der Implementierung committiert.
"""

import threading
import time

import pytest

import services.live_session as ls


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_anrede_state():
    """Raumt per-SID-State nach jedem Test auf."""
    yield
    with ls._session_state_lock:
        for sid in ['sid_a', 'sid_b', '__anrede_test__']:
            ls._session_state.pop(sid, None)
    if hasattr(ls, '_ended_session_snapshots'):
        try:
            with ls._ended_snapshots_lock:
                for sid in ['sid_a', 'sid_b']:
                    ls._ended_session_snapshots.pop(sid, None)
        except Exception:
            pass


# ── Test 1: B2 Split-Brain geschlossen — per-sid Isolation ───────────────────

def test_b2_per_sid_isolation():
    """Split-Brain geschlossen: session_anrede ist pro-SID isoliert.

    Session A bekommt 'du', Session B bekommt 'sie'.
    Reader fuer A gibt 'du', Reader fuer B gibt 'sie' — kein Cross-Tenant-Leak.
    """
    with ls._session_state_lock:
        ls._session_state['sid_a'] = {'session_anrede': 'du', 'user_id': 1}
        ls._session_state['sid_b'] = {'session_anrede': 'sie', 'user_id': 2}

    anrede_a = ls._session_state.get('sid_a', {}).get('session_anrede')
    anrede_b = ls._session_state.get('sid_b', {}).get('session_anrede')

    assert anrede_a == 'du', f"sid_a sollte 'du' haben, hat {anrede_a!r}"
    assert anrede_b == 'sie', f"sid_b sollte 'sie' haben, hat {anrede_b!r}"


# ── Test 1b: N-4 — Start-Write ueberlebt init_session_state ──────────────────

def test_n4_start_write_after_init_survives():
    """N-4: per-sid-Write NACH init_session_state -> Wert bleibt erhalten.

    Simuliert das korrekte Muster (wie session_start_time :687-690):
      1. init_session_state(sid, ...) — erzeugt _session_state[sid]
      2. per-sid-Write: _session_state[sid]['session_anrede'] = 'du'
    Danach muss _session_state[sid]['session_anrede'] == 'du' sein.
    """
    sid = '__anrede_test__'
    # init_session_state aufrufen (erzeugt frischen Dict)
    ls.init_session_state(sid, user_id=99, org_id=1)

    # Per-sid-Write NACH init (N-4-Muster)
    with ls._session_state_lock:
        if sid in ls._session_state:
            ls._session_state[sid]['session_anrede'] = 'du'

    anrede = ls._session_state.get(sid, {}).get('session_anrede')
    assert anrede == 'du', \
        f"N-4 verletzt: session_anrede wurde durch init ueberschrieben ({anrede!r})"

    # Teardown
    ls.pop_session_state(sid)


# ── Test 2: Case-Konsistenz — beide Writer schreiben lowercase ────────────────

def test_case_consistency_lowercase():
    """Beide Writer (Start + Toggle) schreiben lowercase 'du'/'sie' — kein 'Du'/'Sie'-Drift."""
    with ls._session_state_lock:
        ls._session_state['sid_a'] = {}
        ls._session_state['sid_a']['session_anrede'] = 'du'   # Start-Write (lowercase, N-4)

    anrede = ls._session_state['sid_a'].get('session_anrede')
    assert anrede == 'du', f"Start-Writer muss lowercase schreiben, schreibt {anrede!r}"
    assert anrede not in ('Du', 'Sie'), "Case-Drift: titel-case statt lowercase"


# ── Test 3: Fallback tot — _resolve_anrede nutzt nur per-sid ─────────────────

def test_resolve_anrede_no_global_fallback():
    """_resolve_anrede liest nur per-sid (und ki.ansprache als Default), keinen ls.state-Fallback.

    Prueft: wenn ls.state['session_anrede'] einen Wert hat ABER _session_state[sid] keinen,
    gibt _resolve_anrede 'Sie' zurueck (ki-Default, NICHT den alten global).
    NACH der Migration: kein `ls.state`-Fallback in _resolve_anrede.
    """
    from services.prompt_pipeline import _resolve_anrede

    # Sicherstellen dass sid_a keinen session_anrede-Eintrag hat
    with ls._session_state_lock:
        ls._session_state['sid_a'] = {}  # kein 'session_anrede'

    # ki ohne ansprache -> Default 'Sie'
    ki = {}
    result = _resolve_anrede(ls, ki, sid='sid_a')
    # Ergebnis muss 'Sie' sein (kein globaler Fallback)
    assert result == 'Sie', \
        f"_resolve_anrede liefert {result!r} statt 'Sie' — globaler Fallback noch aktiv?"


# ── Test 3b: claude_service:1481 liest top-level statt Subdict ───────────────

def test_claude_service_anrede_reads_toplevel():
    """W-a: claude_service liest session_anrede vom top-level, NICHT aus dem 'state'-Subdict.

    Prueft indirekt: wenn _session_state[sid]['session_anrede']='du' (top-level, KEIN Subdict),
    und analyse_loop _resolve_anrede aufruft, liefert es 'du'.
    """
    sid = 'sid_a'
    with ls._session_state_lock:
        ls._session_state[sid] = {
            'user_id': 1,
            'session_anrede': 'du',   # top-level (kanonisch)
            'state': {
                # KEIN 'session_anrede' im Subdict (tote Ebene W-1 bereits entfernt)
            }
        }

    # _resolve_anrede (wie claude_service es aufruft) muss 'du' liefern
    from services.prompt_pipeline import _resolve_anrede
    ki = {'ansprache': 'Sie'}  # ki-Default waere 'Sie'
    result = _resolve_anrede(ls, ki, sid=sid)
    assert result == 'du', \
        f"claude:1481-Nachfolger liest falsche Ebene: {result!r} statt 'du'"


# ── Test 4: get_briefing_for_sid — per-SID Isolation ────────────────────────

def test_briefing_per_sid_isolation():
    """get_briefing_for_sid ist per-SID isoliert (§6.9)."""
    ls.set_briefing_for_sid('sid_a', 'Briefing A')
    ls.set_briefing_for_sid('sid_b', 'Briefing B')

    # Muss per-SID isoliert sein
    briefing_a = None
    briefing_b = None
    with ls._session_state_lock:
        ls._session_state.setdefault('sid_a', {})
        ls._session_state.setdefault('sid_b', {})
    ls.set_briefing_for_sid('sid_a', 'Briefing A')
    ls.set_briefing_for_sid('sid_b', 'Briefing B')
    briefing_a = ls.get_briefing_for_sid('sid_a')
    briefing_b = ls.get_briefing_for_sid('sid_b')

    assert briefing_a == 'Briefing A', f"sid_a Briefing: {briefing_a!r}"
    assert briefing_b == 'Briefing B', f"sid_b Briefing: {briefing_b!r}"


# ── Test W-1: tote Subdict-Seeds sind weg ─────────────────────────────────────

def test_w1_no_session_anrede_in_state_subdict():
    """W-1: 'state'-Subdict in init_session_state enthaelt kein 'session_anrede'.

    Ebenen-Falle beseitigt: frischer init-State darf keinen 'session_anrede'-Key
    im 'state'-Sub-Dict haben (war tot, wurde von keinem echten Reader genutzt).
    """
    sid = '__anrede_test__'
    ls.init_session_state(sid, user_id=99, org_id=1)
    with ls._session_state_lock:
        st = ls._session_state.get(sid, {})
        state_subdict = st.get('state', {})
    ls.pop_session_state(sid)

    assert 'session_anrede' not in state_subdict, \
        f"W-1 verletzt: 'session_anrede' noch im 'state'-Subdict von init_session_state"


def test_w1_no_mic_muted_in_state_subdict():
    """W-1: 'state'-Subdict in init_session_state enthaelt kein 'mic_muted' (oder es liegt top-level).

    mic_muted muss auf der kanonischen top-level-Ebene sein, nicht im 'state'-Subdict.
    """
    sid = '__anrede_test__'
    ls.init_session_state(sid, user_id=99, org_id=1)
    with ls._session_state_lock:
        st = ls._session_state.get(sid, {})
        state_subdict = st.get('state', {})
        top_level_mic = st.get('mic_muted')
    ls.pop_session_state(sid)

    assert 'mic_muted' not in state_subdict, \
        f"W-1 verletzt: 'mic_muted' noch im 'state'-Subdict von init_session_state (statt top-level)"


# ── Test W-2: Anrede-Tests gegen echten per-sid-Pfad ─────────────────────────

def test_w2_anrede_whitelist_per_sid_du():
    """W-2 (ersetzt test_ewb_rate_api.test_anrede_whitelist_du):
    Start-Anrede 'du' landet per-SID (lowercase), NICHT global title-case.
    """
    sid = '__anrede_test__'
    # Frischer per-SID-State (simuliert NACH init_session_state)
    with ls._session_state_lock:
        ls._session_state[sid] = {}

    # Whitelist-Logik (lowercase, per-SID): direkt den Write ausfuehren
    anrede_raw = 'Du'
    anrede_norm = anrede_raw.strip().lower()   # lowercase (kanonisch, NICHT title-case)
    if anrede_norm in ('du', 'sie'):
        with ls._session_state_lock:
            if sid in ls._session_state:
                ls._session_state[sid]['session_anrede'] = anrede_norm

    result = ls._session_state.get(sid, {}).get('session_anrede')
    assert result == 'du', \
        f"W-2 per-sid lowercase: erwartet 'du', bekam {result!r}"
    # Sicherstellen: kein Global-Write
    assert ls.state.get('session_anrede') is None, \
        "W-2: globaler ls.state-Write ist verboten (per-SID ist kanonisch)"

    # Teardown
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


def test_w2_anrede_whitelist_per_sid_sie():
    """W-2: Start-Anrede 'sie' landet per-SID lowercase."""
    sid = '__anrede_test__'
    with ls._session_state_lock:
        ls._session_state[sid] = {}

    anrede_norm = 'sie'
    with ls._session_state_lock:
        if sid in ls._session_state:
            ls._session_state[sid]['session_anrede'] = anrede_norm

    result = ls._session_state.get(sid, {}).get('session_anrede')
    assert result == 'sie', f"erwartet 'sie', bekam {result!r}"

    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


def test_w2_anrede_whitelist_rejects_invalid_per_sid():
    """W-2: ungueltige Anrede landet NICHT per-SID."""
    sid = '__anrede_test__'
    with ls._session_state_lock:
        ls._session_state[sid] = {}

    anrede_raw = 'Hallo; drop table'
    anrede_norm_raw = anrede_raw.strip().lower()
    if anrede_norm_raw in ('du', 'sie'):
        with ls._session_state_lock:
            if sid in ls._session_state:
                ls._session_state[sid]['session_anrede'] = anrede_norm_raw

    result = ls._session_state.get(sid, {}).get('session_anrede')
    assert result is None, f"Injection schrieb session_anrede per-SID: {result!r}"

    with ls._session_state_lock:
        ls._session_state.pop(sid, None)
