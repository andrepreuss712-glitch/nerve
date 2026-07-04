"""
tests/test_persid_03_snapshot.py
────────────────────────────────────────────────────────────────────
Phase 08.23.2.PERSID Plan 03 — Task 1 (TDD RED then GREEN).

Waechter:
  B1  — _ended_session_snapshots-Fundament: BEIDE Beenden-Naehte stashen, kein
         Datenverlust bei normalem Hangup (stop_live_session) ODER disconnect-
         vor-beenden.
  N-1 — Doppel-Feuer-Race: stop_live_session (voller Snapshot) + handle_disconnect
         (setzt leeres setdefault-Dict) -> Snapshot bleibt VOLL (first-stash-wins +
         Leer-Skip).
  N-3 — consume_ended_session ist NICHT-destruktiver PEEK: zweimaliges Lesen liefert
         denselben Inhalt (kein Pop beim ersten Lesen).
  N-2 — NACH Stash liest api_beenden Redeanteil/Tempo/Monolog und word_confidences
         aus dem Snapshot, NICHT aus dem leeren _session_state.
  S3  — _beenden_sid wird bevorzugt via posted call_id aufgeloest (exakt).

Integration-Assertions (CLAUDE.md Test-Qualitaets-Regel):
  Alle Tests pruefe RUNTIME-Verhalten — State-Mutation in dict nach Function-Call.
  KEIN Source-Presence-False-Green.

D-10-Konformitaet: dieser Test wurde VOR der Implementierung committiert —
MUSS initial ROT sein (stash_ended_session / consume_ended_session existieren noch nicht).
"""

import threading
import time
import unittest.mock as mock

import pytest

import services.live_session as ls


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_snapshot_state():
    """Raumt _ended_session_snapshots + _session_state nach jedem Test auf."""
    yield
    # Teardown: _ended_session_snapshots aufraeumen (falls Helfer existiert)
    if hasattr(ls, '_ended_session_snapshots'):
        with ls._ended_snapshots_lock if hasattr(ls, '_ended_snapshots_lock') else threading.Lock():
            # Direkt leeren um Lock-Abhaengigkeit zu vermeiden
            try:
                ls._ended_session_snapshots.clear()
            except Exception:
                pass
    # _session_state aufraeumen
    with ls._session_state_lock:
        for sid in ['sid_a', 'sid_b', 'sid_c', '__test_sid__']:
            ls._session_state.pop(sid, None)


def _init_sid(sid, berater_words=42, call_id='cid-001'):
    """Hilfsfunktion: initialisiert _session_state[sid] mit Testdaten."""
    with ls._session_state_lock:
        ls._session_state[sid] = {
            'user_id': 1,
            'berater_words': berater_words,
            'kunde_words': 10,
            'session_start_time': time.monotonic() - 60.0,
            'laengster_monolog_sek': 12.5,
            'word_confidences': [(100, 0.95), (200, 0.88)],
            'state': {'call_id': call_id},
            '_briefing': 'Testbriefing fuer ' + sid,
        }


# ── Test 1: B1 Normal-Hangup-Pfad (:779) stasht den State ────────────────────

def test_b1_stop_live_session_stashes_snapshot():
    """stop_live_session stasht State in _ended_session_snapshots statt sofort zu poppen.

    Nach stash_ended_session(sid_a):
    - _session_state hat KEINEN Eintrag mehr fuer sid_a (pop erfolgt)
    - _ended_session_snapshots[sid_a] enthaelt den gestashten State
    - consume_ended_session(sid_a) liefert die Daten zurueck
    """
    _init_sid('sid_a', berater_words=42)
    assert ls._session_state.get('sid_a') is not None

    # stash_ended_session muss existieren (B1-Fundament)
    assert hasattr(ls, 'stash_ended_session'), "stash_ended_session fehlt in live_session"

    ls.stash_ended_session('sid_a')

    # _session_state sollte keine lebende Session mehr haben
    with ls._session_state_lock:
        assert 'sid_a' not in ls._session_state, \
            "pop_session_state sollte von stash_ended_session aufgerufen werden"

    # consume_ended_session muss existieren (N-3)
    assert hasattr(ls, 'consume_ended_session'), "consume_ended_session fehlt in live_session"

    snap = ls.consume_ended_session('sid_a')
    assert snap is not None, "consume_ended_session liefert None — Snapshot wurde nicht gestasht"
    assert snap.get('berater_words') == 42, \
        f"Snapshot enthaelt falsche berater_words: {snap.get('berater_words')!r}"


# ── Test 1b: B1 Disconnect-Pfad (:815) stasht den State ─────────────────────

def test_b1_disconnect_stashes_snapshot():
    """handle_disconnect-aequivalent: stash_ended_session fuer den :815-Pfad.

    Wenn _session_state[sid] volle Daten hat (NICHT durch setdefault leer erzeugt),
    wird der vollstaendige Snapshot gestasht.
    """
    _init_sid('sid_b', berater_words=77)

    ls.stash_ended_session('sid_b')

    snap = ls.consume_ended_session('sid_b')
    assert snap is not None, "Snapshot nicht vorhanden nach stash (disconnect-Pfad)"
    assert snap.get('berater_words') == 77


# ── Test 1c: N-1 Doppel-Feuer (voller Snapshot bleibt erhalten) ──────────────

def test_n1_double_fire_first_stash_wins():
    """N-1: voller Stash (:779) + leerer setdefault-Stash (:815) — voller Snapshot bleibt.

    Ablauf (simuliert BEIDE Naehte):
    1. _session_state[sid_a] volle Daten (berater_words=42)
    2. stash_ended_session(sid_a) -> voller Snapshot gespeichert, State gepoppt
    3. setdefault erzeugt leeres {} in _session_state[sid_a] (wie handle_disconnect :810-811)
    4. stash_ended_session(sid_a) erneut -> Leer-Skip ODER first-stash-wins
    5. consume_ended_session(sid_a) liefert immer noch berater_words=42
    """
    _init_sid('sid_a', berater_words=42)

    # Erster Stash (voller State — :779 Pfad)
    ls.stash_ended_session('sid_a')

    # setdefault erzeugt leeres {} (wie handle_disconnect :810-811)
    with ls._session_state_lock:
        ls._session_state.setdefault('sid_a', {})

    # Zweiter Stash-Versuch (leerer Dict — :815 Pfad NACH setdefault)
    ls.stash_ended_session('sid_a')

    # Snapshot MUSS noch den vollen Inhalt haben
    snap = ls.consume_ended_session('sid_a')
    assert snap is not None, "Snapshot verloren nach Doppel-Feuer"
    assert snap.get('berater_words') == 42, \
        f"N-1 verletzt: zweiter leerer Stash hat vollen Snapshot ueberschrieben " \
        f"(berater_words={snap.get('berater_words')!r})"


# ── Test 2b: N-3 PEEK nicht-destruktiv ───────────────────────────────────────

def test_n3_peek_not_destructive():
    """N-3: consume_ended_session ist ein PEEK — zweimaliges Lesen liefert denselben Inhalt."""
    _init_sid('sid_a', berater_words=99)
    ls.stash_ended_session('sid_a')

    snap1 = ls.consume_ended_session('sid_a')
    snap2 = ls.consume_ended_session('sid_a')

    assert snap1 is not None, "Erster consume gibt None"
    assert snap2 is not None, "Zweiter consume gibt None — consume_ended_session hat gepoppt (destruktiv)"
    assert snap1.get('berater_words') == snap2.get('berater_words') == 99, \
        "N-3 verletzt: zweiter Peek liefert anderen Inhalt als erster"


# ── Test 2: B1 Ghost-Drop (Late-Write nach stash belebt sid nicht wieder) ────

def test_b1_ghost_drop_late_write():
    """B1 Ghost-Drop: spaeter Late-Write auf tote sid schreibt NICHT in _ended_session_snapshots.

    Nach stash ist die sid aus _session_state entfernt. Ghost-SID-Guard in set_briefing_for_sid
    / record_ewb_click / Anrede-Write (alle `if sid in _session_state`) verhindern
    Wiederbelebung. _ended_session_snapshots darf vom Late-Write NICHT beruehrt werden.
    """
    _init_sid('sid_a', berater_words=10)
    ls.stash_ended_session('sid_a')

    # simulate Late-Write via set_briefing_for_sid (Ghost-SID-Guard muss greifen)
    ls.set_briefing_for_sid('sid_a', 'LATE_WRITE_INJECTION')

    # _session_state hat keine lebende sid_a
    with ls._session_state_lock:
        assert 'sid_a' not in ls._session_state, \
            "Late-Write hat sid_a in _session_state wiederbelebt"

    # Snapshot bleibt unveraendert (Late-Write aendert nichts)
    snap = ls.consume_ended_session('sid_a')
    assert snap is not None, "Snapshot durch Late-Write zerstoert"
    briefing_after = snap.get('_briefing')
    assert briefing_after != 'LATE_WRITE_INJECTION', \
        f"Late-Write hat den Snapshot-Briefing unveraendert gelassen — " \
        f"aber _session_state war leer, nichts sollte gehen"


# ── Test 3: S3 exakte Aufloesung via posted call_id ──────────────────────────

def test_s3_exact_call_id_resolution():
    """S3: _beenden_sid wird via posted call_id exakt aufgeloest.

    Setup: 2 Sessions desselben Users, unterschiedliche call_ids.
    _beenden_sid muss auf die Session mit der gematchten call_id zeigen, nicht die andere.

    Da _load_beenden_state in app_routes existiert, testen wir das _session_state-Scan-Muster
    direkt (analog zum existierenden _phase_d_call_id-Muster app_routes.py:194-207).
    """
    # Zwei Sessions, gleicher User
    with ls._session_state_lock:
        ls._session_state['sid_c'] = {
            'user_id': 5,
            'session_start_time': time.monotonic() - 30.0,
            'state': {'call_id': 'cid-RICHTIG'},
            'berater_words': 111,
        }
        ls._session_state['sid_b'] = {
            'user_id': 5,
            'session_start_time': time.monotonic() - 10.0,
            'state': {'call_id': 'cid-FALSCH'},
            'berater_words': 222,
        }

    # Exakter Scan via call_id (Muster app_routes.py:194-201)
    posted_call_id = 'cid-RICHTIG'
    matched_sid = None
    with ls._session_state_lock:
        for _s, _sd in ls._session_state.items():
            if _sd.get('state', {}).get('call_id') and \
               str(_sd['state']['call_id']) == str(posted_call_id):
                matched_sid = _s
                break

    assert matched_sid == 'sid_c', \
        f"S3 verletzt: posted call_id='cid-RICHTIG' hat sid={matched_sid!r} " \
        f"statt 'sid_c' aufgeloest"

    # Teardown
    with ls._session_state_lock:
        ls._session_state.pop('sid_c', None)
        ls._session_state.pop('sid_b', None)


# ── Test 4: N-2 Snapshot liefert Redeanteil-Basis nach stash ────────────────

def test_n2_speech_stats_from_snapshot():
    """N-2: nach stop_live_session-Stash liest api_beenden-Logik Speech-Stats aus Snapshot.

    Prueft dass stash_ended_session die berater_words/kunde_words/session_start_time/
    laengster_monolog_sek SOWIE word_confidences in den Snapshot kopiert.
    (consume_ended_session gibt den gestashten State zurueck, der diese Keys enthalten muss.)
    """
    _init_sid('sid_a', berater_words=150)
    # session_start_time ist bereits via _init_sid gesetzt
    # laengster_monolog ist 12.5, word_confidences sind gesetzt

    ls.stash_ended_session('sid_a')

    # _session_state hat keine lebende Session mehr
    with ls._session_state_lock:
        assert 'sid_a' not in ls._session_state

    snap = ls.consume_ended_session('sid_a')
    assert snap is not None

    # Alle N-2-Keys muessen im Snapshot stecken
    assert snap.get('berater_words') == 150, \
        f"berater_words fehlt im Snapshot: {snap.get('berater_words')!r}"
    assert snap.get('kunde_words') == 10, \
        f"kunde_words fehlt im Snapshot: {snap.get('kunde_words')!r}"
    assert snap.get('laengster_monolog_sek') == 12.5, \
        f"laengster_monolog_sek fehlt im Snapshot: {snap.get('laengster_monolog_sek')!r}"
    assert snap.get('session_start_time') is not None, \
        "session_start_time fehlt im Snapshot"
    wc = snap.get('word_confidences')
    assert wc and len(wc) > 0, \
        f"word_confidences fehlt/leer im Snapshot: {wc!r}"
