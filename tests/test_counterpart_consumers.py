"""Verhaltens-Tests fuer die counterpart-Konsumenten (Phase 08.23.2.COUNTERPART).

Der folgenreichste Leser ist derive_answer_params: er bestimmt die Rollen-Bezeichnung
im LIVE-Prompt und faellt bei fehlendem Schluessel STILL auf 'gatekeeper' zurueck
(or 'gatekeeper' — kein Crash). Ein Umbau ohne diese Tests waere unsichtbar falsch.

Kein Source-Presence-False-Green: jeder Test ruft die echte Funktion auf und
assertiert den Rueckgabewert.
"""
import services.live_session as ls
from services.prompt_pipeline import derive_answer_params


def _seed(sid, *, mode='cold_call', state=None):
    """Per-SID-State wie nach init_session_state (Achse A top-level, Achse B im Sub-Dict)."""
    with ls._session_state_lock:
        ls._session_state[sid] = {
            'mode': mode,
            'user_id': 1,
            'org_id': 1,
            'state': dict(state or {}),
        }


def _drop(sid):
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)


# ── Teil 1: die Prompt-Rolle (Task 1) ────────────────────────────────────────

def test_role_gatekeeper_when_counterpart_gatekeeper():
    sid = 'cp-consumers-role-gk'
    _seed(sid, mode='cold_call', state={'counterpart': 'gatekeeper'})
    try:
        p = derive_answer_params(sid)
    finally:
        _drop(sid)
    assert p['role'] == 'gatekeeper', p
    assert p['mode'] == 'cold_call', p


def test_role_interessent_when_counterpart_decision_maker():
    sid = 'cp-consumers-role-dm'
    _seed(sid, mode='cold_call', state={'counterpart': 'decision_maker'})
    try:
        p = derive_answer_params(sid)
    finally:
        _drop(sid)
    assert p['role'] == 'interessent', (
        "decision_maker muss die Prompt-Rolle 'interessent' ergeben "
        f"(Prompt-Rollen-Bezeichnung, kein Zustands-Wort) — bekommen: {p['role']!r}")


def test_role_meeting_wins_over_counterpart():
    """Die heutige Vorrangordnung ist bewusst UNVERAENDERT: mode=='meeting' schlaegt
    den Gespraechspartner. Dieser Test sichert sie gegen spaeteres Umdrehen."""
    sid = 'cp-consumers-role-meeting'
    _seed(sid, mode='meeting', state={'counterpart': 'gatekeeper'})
    try:
        p = derive_answer_params(sid)
    finally:
        _drop(sid)
    assert p['role'] == 'meeting', p
    assert p['mode'] == 'meeting', p


def test_role_fail_open_for_unknown_sid():
    p = derive_answer_params('gibt-es-nicht')
    assert p['role'] == 'gatekeeper', (
        "Unbekannte SID muss ueber den or-'gatekeeper'-Zweig laufen — "
        "'interessent' gilt nur im Exception-Pfad")
    assert p['mode'] == 'cold_call', p


def test_warns_when_session_exists_but_counterpart_key_missing(capsys):
    """Der Zaun um den stillen Fallback: Session da, Schluessel fehlt -> WARN im Log.

    Ohne diese Warnung waere die Fehlerklasse 'fehlender Schluessel ⇒ still falsche
    Rolle' nur umbenannt, nicht beseitigt.
    """
    sid = 'cp-consumers-key-missing'
    _seed(sid, mode='cold_call', state={})
    try:
        p = derive_answer_params(sid)
    finally:
        _drop(sid)
    out = capsys.readouterr().out
    assert p['role'] == 'gatekeeper', p
    assert 'counterpart' in out, out
    assert 'WARN' in out, out

    # Gegenprobe: die unbekannte SID ist der legitime Normalfall (Ghost-SID /
    # Aufruf vor Anruf-Start) — dort darf KEINE WARN-Zeile das Log zumuellen.
    derive_answer_params('gibt-es-nicht')
    out2 = capsys.readouterr().out
    assert 'WARN' not in out2, out2
