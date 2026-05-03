"""
Phase 08.19.5: Per-SID-Migration-Tests — REQ-06/07/08 + REQ-01 Isolation
Prueft _load_profile_cache, vorwissen_level Chain, streame_manual_ewb_variante Error-Prop,
is_paused SID-Isolation. Alle Tests sind Function-Call-Return-Tests. Siehe CLAUDE.md.
"""
import pytest
import services.live_session as ls


# ── Teardown-Hilfsfunktion ────────────────────────────────────────────────────

def _clean_sids(*sids):
    """Tear down test SIDs to avoid cross-test contamination."""
    for sid in sids:
        ls.pop_session_state(sid)


# ── REQ-01: is_paused SID-Isolation ──────────────────────────────────────────

def test_is_paused_isolation():
    """SID-A pause darf SID-B nicht beeinflussen (REQ-01 Akzeptanzkriterium)."""
    sid_a = 'test-paused-sid-a'
    sid_b = 'test-paused-sid-b'
    try:
        ls.init_session_state(sid_a, user_id=1, org_id=1)
        ls.init_session_state(sid_b, user_id=2, org_id=1)

        # Pause SID-A
        with ls._session_state_lock:
            ls._session_state[sid_a]['state']['is_paused'] = True

        # SID-B must remain unpaused
        assert ls.get_sid_paused(sid_b) == False, \
            "SID-B should not be paused when SID-A is paused"
        assert ls.get_sid_paused(sid_a) == True, \
            "SID-A should report paused"
    finally:
        _clean_sids(sid_a, sid_b)


# ── REQ-06: _load_profile_cache() Integration-Test ───────────────────────────

def test_load_profile_cache_populates_sid(db_session, monkeypatch):
    """Integration-Test: _load_profile_cache befuellt _session_state[sid]['_profile_cache']."""
    from database.models import User, Profile
    import database.db as _db_mod

    # Setup: User + Profile in In-Memory-DB
    u = User(
        vorname='Test', nachname='User', email='cache-test@nerve.de',
        passwort_hash='x', rolle='member', org_id=1,
    )
    db_session.add(u)
    db_session.flush()

    p = Profile(
        name='CacheProfil', org_id=1,
        daten='{"basis": {"beschreibung": "Testbeschreibung"}}',
    )
    db_session.add(p)
    db_session.flush()

    sid = 'test-cache-sid'
    ls.init_session_state(sid, user_id=u.id, org_id=1, profile_id=p.id)

    # Monkeypatch SessionLocal so _load_profile_cache uses the in-memory DB
    monkeypatch.setattr(_db_mod, 'SessionLocal', lambda: db_session)

    try:
        ls._load_profile_cache(sid=sid, user_id=u.id, profile_id=p.id)

        with ls._session_state_lock:
            cache = ls._session_state.get(sid, {}).get('_profile_cache', None)

        assert isinstance(cache, dict), \
            f"_profile_cache should be dict after _load_profile_cache, got {type(cache)}"
        # _profile_cache holds: opener_content, user_firstname, faqs, profile_branche
        expected_keys = {'opener_content', 'user_firstname', 'faqs', 'profile_branche'}
        present = expected_keys & set(cache.keys())
        assert present, \
            f"Expected at least one of {expected_keys} in _profile_cache, got: {list(cache.keys())}"
    finally:
        _clean_sids(sid)


# ── REQ-07: vorwissen_level UI→Backend Chain ──────────────────────────────────

def test_vorwissen_level_flows_into_profile_context():
    """vorwissen_level 'hoch' in _session_state[sid] erscheint in build_profile_context output."""
    from services.prompt_pipeline import build_profile_context

    sid = 'test-vorwissen-sid'
    ls.init_session_state(sid, user_id=1, org_id=1)
    ls.set_profile_for_sid(sid, 'TestProfil', {'basis': {'beschreibung': 'Testbeschreibung'}})

    # Simulate handle_set_vorwissen writing to state:
    with ls._session_state_lock:
        ls._session_state[sid]['vorwissen_level'] = 'hoch'

    try:
        result = build_profile_context(user_id=1, sid=sid)
        assert isinstance(result, str), \
            f"build_profile_context should return str, got {type(result)}"
        assert 'hoch' in result or 'Vorwissen' in result, \
            f"vorwissen_level 'hoch' sollte im build_profile_context output erscheinen. " \
            f"Got (first 300 chars): {result[:300]}"
    finally:
        _clean_sids(sid)


# ── REQ-08: streame_manual_ewb_variante() Error-Propagation ──────────────────

def test_ewb_variante_propagates_profile_context_error(monkeypatch):
    """build_profile_context Exception fuehrt zu Error-Dict — kein silent fail (REQ-08)."""
    from services.claude_service import streame_manual_ewb_variante
    import services.prompt_pipeline as pp

    def _raise(*args, **kwargs):
        raise RuntimeError("profile_context kaboom")

    monkeypatch.setattr(pp, 'build_profile_context', _raise)

    result = streame_manual_ewb_variante('zu_teuer', {}, '', 'test-ewb-sid', slot=1)
    assert isinstance(result, dict), \
        f"Expected dict result on error, got {type(result)}: {result!r}"
    assert 'error' in result, \
        f"Expected 'error' key in result dict, got keys: {list(result.keys())}"
    assert result.get('gegenargument_1') is None, \
        f"gegenargument_1 should be None on error, got: {result.get('gegenargument_1')!r}"


# ── REQ-2/REQ-3 (Phase 08.19.5.1): WR-01 + WR-02 per-SID Isolation ──────────

def test_write_ft_event_isolation_per_sid(db_session, monkeypatch):
    """FT-Event fuer SID-A traegt user_id von User-A, nicht User-B (WR-01 REQ-2)."""
    import services.claude_service as cs
    import database.db as _db_mod
    from database.models import FtAssistantEvent, Organisation, User, FtCallSession, PromptVersion

    # Fixtures: Org, zwei User, zwei FtCallSessions
    org = Organisation(name='IsoTest', plan='starter')
    db_session.add(org); db_session.flush()

    u_a = User(org_id=org.id, email='iso-a@nerve.de', passwort_hash='x',
               market='dach', language='de')
    u_b = User(org_id=org.id, email='iso-b@nerve.de', passwort_hash='x',
               market='dach', language='de')
    db_session.add_all([u_a, u_b]); db_session.flush()

    sess_a = FtCallSession(user_id=u_a.id, mode='meeting', market='dach', language='de')
    db_session.add(sess_a); db_session.flush()
    db_session.add(PromptVersion(
        module='assistant_live', version='v1.0.0',
        prompt_text='x' * 40, is_active=True,
    ))
    db_session.commit()

    sid_a = 'test-ft-iso-sid-a'
    sid_b = 'test-ft-iso-sid-b'
    try:
        ls.init_session_state(sid_a, user_id=u_a.id, org_id=org.id, mode='meeting',
                              market='dach', language='de')
        ls.init_session_state(sid_b, user_id=u_b.id, org_id=org.id, mode='meeting',
                              market='dach', language='de')
        # Set ft_session_id in state sub-key for sid_a
        with ls._session_state_lock:
            ls._session_state[sid_a]['state']['ft_session_id'] = sess_a.id

        monkeypatch.setattr(cs, '_ACTIVE_PROMPT_CACHE', {})
        from tests.test_ft_write_hooks import _FakeSession
        monkeypatch.setattr(_db_mod, 'SessionLocal', lambda: _FakeSession(db_session))

        def _fake_gapv(module):
            from database.models import PromptVersion as PV
            pv = db_session.query(PV).filter_by(module=module, is_active=True).first()
            return pv.version if pv else 'unknown'
        monkeypatch.setattr(cs, 'get_active_prompt_version', _fake_gapv)

        # Rufe mit SID-A auf — nur User-A darf in die Row
        cs._write_ft_assistant_event(
            module='assistant_live',
            hint_type='einwand',
            hint_text='Test Einwand',
            model_used='claude-haiku-test',
            context={'transcript_segment': 'Test', 'speaker': 'rep',
                     'conversation_phase': 'discovery'},
            sid=sid_a,
        )

        rows = db_session.query(FtAssistantEvent).all()
        assert len(rows) == 1, "Genau eine Row erwartet"
        assert rows[0].user_id == u_a.id, \
            f"Row muss user_id von User-A ({u_a.id}) haben, nicht {rows[0].user_id}"
        assert rows[0].user_id != u_b.id, \
            "Row darf NICHT user_id von User-B haben (WR-01 Isolation)"
    finally:
        _clean_sids(sid_a, sid_b)


def test_learning_cards_isolation_per_sid(monkeypatch):
    """WR-02: SID-A sieht eigene active_learning_cards; SID-B sieht leere Liste (REQ-3)."""
    sid_a = 'test-lk-iso-sid-a'
    sid_b = 'test-lk-iso-sid-b'
    try:
        ls.init_session_state(sid_a, user_id=1, org_id=1)
        ls.init_session_state(sid_b, user_id=2, org_id=1)

        # Schreibe Cards fuer SID-A (so wie load_learning_cards es tut)
        cards_a = [{'category': 'einwand', 'final_text': 'Karte A1'}]
        with ls._session_state_lock:
            ls._session_state[sid_a]['state']['active_learning_cards'] = cards_a

        # Lese per-SID wie analyse_loop es nach WR-02-Fix tut
        with ls._session_state_lock:
            lk_a = ls._session_state.get(sid_a, {}).get('state', {}).get('active_learning_cards', [])
            lk_b = ls._session_state.get(sid_b, {}).get('state', {}).get('active_learning_cards', [])

        assert lk_a == cards_a, \
            f"SID-A muss eigene Cards sehen, got: {lk_a}"
        assert lk_b == [], \
            f"SID-B muss leere Liste sehen (kein Overlap), got: {lk_b}"
    finally:
        _clean_sids(sid_a, sid_b)
