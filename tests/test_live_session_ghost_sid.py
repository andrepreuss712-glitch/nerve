"""
tests/test_live_session_ghost_sid.py
─────────────────────────────────────────────────────────────────────
Phase 08.20 D-09: Ghost-SID Guard + Deadlock-Stress Tests

HIGH-1: set_briefing_for_sid silently drops writes for non-existent SIDs.
HIGH-2: 10 parallel threads doing Connect->write briefing->Disconnect
        must complete without deadlock within 10 seconds.
"""
import threading
import time

import services.live_session as ls


def test_ghost_sid_briefing_silently_dropped():
    """HIGH-1: Async PreCall completing after disconnect must not leak ghost SID entry."""
    sid = 'ghost-test-sid-001'
    # SID is NOT in _session_state (simulates post-disconnect state)
    with ls._session_state_lock:
        ls._session_state.pop(sid, None)
    # Call set_briefing_for_sid — simulates async recherche_firma() completing late
    ls.set_briefing_for_sid(sid, 'This should be silently dropped')
    # Assert: no entry in _session_state for this SID
    with ls._session_state_lock:
        assert sid not in ls._session_state, (
            f"Ghost SID {sid} created in _session_state after post-disconnect set_briefing_for_sid()"
        )
    print('test_ghost_sid_briefing_silently_dropped: PASS')


def test_deadlock_stress_no_deadlock():
    """HIGH-2: 10 parallel threads doing Connect->write briefing->Disconnect must complete
    without deadlock within 10 seconds."""
    NUM_THREADS = 10
    TIMEOUT_S = 10
    results = []
    barrier = threading.Barrier(NUM_THREADS)

    def session_lifecycle(thread_id):
        sid = f'stress-test-sid-{thread_id:03d}'
        barrier.wait()  # Sync all threads to start simultaneously
        try:
            # Simulate Connect: init session state
            with ls._session_state_lock:
                ls._session_state[sid] = {'user_id': thread_id, 'org_id': 1}
            # Simulate PreCall briefing write
            ls.set_briefing_for_sid(sid, f'Briefing for thread {thread_id}')
            # Verify briefing is readable
            result = ls.get_briefing_for_sid(sid)
            assert result == f'Briefing for thread {thread_id}', f'Briefing mismatch: {result}'
            # Simulate Disconnect
            ls.pop_session_state(sid)
            # Verify cleanup
            with ls._session_state_lock:
                assert sid not in ls._session_state, f'SID {sid} not cleaned after pop'
            results.append(('ok', thread_id))
        except Exception as e:
            results.append(('error', thread_id, str(e)))

    threads = [threading.Thread(target=session_lifecycle, args=(i,)) for i in range(NUM_THREADS)]
    for t in threads:
        t.start()

    deadline = time.monotonic() + TIMEOUT_S
    for t in threads:
        remaining = deadline - time.monotonic()
        t.join(timeout=max(0, remaining))

    errors = [r for r in results if r[0] == 'error']
    not_done = NUM_THREADS - len(results)
    assert not_done == 0, f'{not_done} threads did not complete within {TIMEOUT_S}s (deadlock?)'
    assert errors == [], f'Thread errors: {errors}'
    print(f'test_deadlock_stress_no_deadlock: PASS ({NUM_THREADS} threads, no deadlock)')
