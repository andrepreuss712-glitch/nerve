"""
Phase 04.7.1 Plan 04 — Unit tests for _write_ft_assistant_event().

Focus: Cold-Call DSGVO NULL-enforcement (D-03/D-04/D-05) — even when the
caller passes a transcript_segment, Cold-Call mode MUST drop it to NULL.
"""
import threading


def _setup_ls_state(**overrides):
    """Patch services.live_session.state with test values (thread-safe)."""
    import services.live_session as ls
    if not hasattr(ls, 'state_lock'):
        ls.state_lock = threading.Lock()
    with ls.state_lock:
        ls.state.update({
            'ft_session_id': overrides.get('ft_session_id'),
            'user_id':       overrides.get('user_id'),
            'mode':          overrides.get('mode', 'cold_call'),
            'market':        overrides.get('market', 'dach'),
            'language':      overrides.get('language', 'de'),
            'kaufbereitschaft': overrides.get('kaufbereitschaft', 50),
        })
    return ls


def _restore_ls_state(ls, keys):
    with ls.state_lock:
        for k in keys:
            ls.state.pop(k, None)


class _FakeSession:
    """Adapter so SessionLocal() returns the pytest db_session without closing it."""
    def __init__(self, real):
        self._real = real
    def add(self, *a, **k):
        return self._real.add(*a, **k)
    def commit(self):
        return self._real.commit()
    def close(self):
        pass
    def query(self, *a, **k):
        return self._real.query(*a, **k)


def _seed_fixtures(db_session, mode='cold_call'):
    from database.models import Organisation, User, FtCallSession, PromptVersion
    org = Organisation(name='T', plan='starter')
    db_session.add(org); db_session.flush()
    u = User(org_id=org.id, email='t@t.de', passwort_hash='x', market='dach', language='de')
    db_session.add(u); db_session.flush()
    sess = FtCallSession(user_id=u.id, mode=mode, market='dach', language='de')
    db_session.add(sess); db_session.flush()
    db_session.add(PromptVersion(
        module='assistant_live', version='v1.0.0',
        prompt_text='x' * 40, is_active=True,
    ))
    db_session.commit()
    return org, u, sess


def test_cold_call_forces_transcript_null(db_session, monkeypatch):
    """D-04/D-05: Cold-Call mode MUST hard-NULL transcript_segment and speaker."""
    from database.models import FtAssistantEvent

    _org, u, sess = _seed_fixtures(db_session, mode='cold_call')

    ls = _setup_ls_state(ft_session_id=sess.id, user_id=u.id, mode='cold_call')
    try:
        # Route SessionLocal() to our in-memory test session
        import database.db as dbmod
        import services.claude_service as cs
        monkeypatch.setattr(cs, '_ACTIVE_PROMPT_CACHE', {})
        # Patch both the module-level SessionLocal and the one imported inside the helper
        fake_factory = lambda: _FakeSession(db_session)
        monkeypatch.setattr(dbmod, 'SessionLocal', fake_factory)

        # Also patch get_active_prompt_version to read from our test session
        def _fake_gapv(module):
            from database.models import PromptVersion
            pv = db_session.query(PromptVersion).filter_by(module=module, is_active=True).first()
            return pv.version if pv else 'unknown'
        monkeypatch.setattr(cs, 'get_active_prompt_version', _fake_gapv)

        cs._write_ft_assistant_event(
            module='assistant_live',
            hint_type='objection',
            hint_text='Test hint',
            model_used='claude-haiku-test',
            context={
                'transcript_segment': 'SHOULD BE DROPPED BY DSGVO',
                'speaker': 'customer',
                'conversation_phase': 'discovery',
                'hint_category': 'kosten',
            },
        )

        rows = db_session.query(FtAssistantEvent).all()
        assert len(rows) == 1, "exactly one row should be written"
        row = rows[0]
        assert row.transcript_segment is None, "D-04: Cold-Call must NULL transcript_segment"
        assert row.speaker is None, "D-05: Cold-Call must NULL speaker"
        assert row.hint_text == 'Test hint'
        assert row.hint_type == 'objection'
        assert row.hint_category == 'kosten'
        assert row.model_used == 'claude-haiku-test'
        assert row.prompt_version == 'v1.0.0'
        assert row.market == 'dach'
        assert row.language == 'de'
        assert row.readiness_score == 50
        assert row.conversation_phase == 'discovery'
    finally:
        _restore_ls_state(ls, ['ft_session_id', 'user_id', 'mode', 'market', 'language'])


def test_meeting_mode_preserves_transcript(db_session, monkeypatch):
    """Meeting mode must preserve transcript_segment and speaker from context."""
    from database.models import FtAssistantEvent

    _org, u, sess = _seed_fixtures(db_session, mode='meeting')

    ls = _setup_ls_state(ft_session_id=sess.id, user_id=u.id, mode='meeting')
    try:
        import database.db as dbmod
        import services.claude_service as cs
        monkeypatch.setattr(cs, '_ACTIVE_PROMPT_CACHE', {})
        monkeypatch.setattr(dbmod, 'SessionLocal', lambda: _FakeSession(db_session))

        def _fake_gapv(module):
            from database.models import PromptVersion
            pv = db_session.query(PromptVersion).filter_by(module=module, is_active=True).first()
            return pv.version if pv else 'unknown'
        monkeypatch.setattr(cs, 'get_active_prompt_version', _fake_gapv)

        cs._write_ft_assistant_event(
            module='assistant_live',
            hint_type='hint',
            hint_text='Meeting hint',
            model_used='claude-haiku-test',
            context={'transcript_segment': 'kept', 'speaker': 'rep'},
        )

        rows = db_session.query(FtAssistantEvent).all()
        assert len(rows) == 1
        assert rows[0].transcript_segment == 'kept'
        assert rows[0].speaker == 'rep'
    finally:
        _restore_ls_state(ls, ['ft_session_id', 'user_id', 'mode', 'market', 'language'])


def test_skips_when_ft_session_id_missing(db_session, monkeypatch):
    """No ft_session_id (Phase 04.7.1 not yet active) → skip write silently."""
    from database.models import FtAssistantEvent

    _seed_fixtures(db_session, mode='cold_call')

    ls = _setup_ls_state(ft_session_id=None, user_id=None, mode='cold_call')
    try:
        import database.db as dbmod
        import services.claude_service as cs
        monkeypatch.setattr(dbmod, 'SessionLocal', lambda: _FakeSession(db_session))

        cs._write_ft_assistant_event(
            module='assistant_live',
            hint_type='hint',
            hint_text='should not be written',
            model_used='claude-haiku-test',
            context={},
        )

        rows = db_session.query(FtAssistantEvent).all()
        assert len(rows) == 0, "no row should be written when ft_session_id is None"
    finally:
        _restore_ls_state(ls, ['ft_session_id', 'user_id', 'mode', 'market', 'language'])


def test_write_hook_swallows_exceptions(db_session, monkeypatch):
    """Any DB exception must NOT propagate — analyse_loop must never crash."""
    import services.claude_service as cs
    import database.db as dbmod

    ls = _setup_ls_state(ft_session_id=1, user_id=1, mode='cold_call')
    try:
        class _Boom:
            def __call__(self):
                raise RuntimeError("DB explosion")
        monkeypatch.setattr(dbmod, 'SessionLocal', _Boom())

        # Must not raise
        cs._write_ft_assistant_event(
            module='assistant_live',
            hint_type='hint',
            hint_text='x',
            model_used='claude-haiku-test',
            context={},
        )
    finally:
        _restore_ls_state(ls, ['ft_session_id', 'user_id', 'mode', 'market', 'language'])
