"""
Phase 08.19.4: DSGVO-Pflicht-Tests — SID-Isolation
Prueft dass kein Cross-User-State-Contamination moeglich ist.
Alle Tests sind Runtime-Behavior-Tests (keine Source-Presence-Checks).
"""
import threading
import pytest
import services.live_session as ls


def _clean_sids(*sids):
    """Tear down test SIDs to avoid cross-test contamination."""
    for sid in sids:
        ls.pop_session_state(sid)


class TestPerSidProfileIsolation:

    def test_two_sids_independent_profiles(self):
        """User A und User B haben ihr eigenes Profil — keine Cross-Contamination."""
        sid_a = 'test-sid-user-a'
        sid_b = 'test-sid-user-b'
        try:
            ls.set_profile_for_sid(sid_a, 'Profil A', {'unternehmen': 'Firma A'})
            ls.set_profile_for_sid(sid_b, 'Profil B', {'unternehmen': 'Firma B'})

            name_a, daten_a = ls.get_profile_for_sid(sid_a)
            name_b, daten_b = ls.get_profile_for_sid(sid_b)

            assert name_a == 'Profil A', f"SID-A should have Profil A, got {name_a!r}"
            assert name_b == 'Profil B', f"SID-B should have Profil B, got {name_b!r}"
            assert daten_a.get('unternehmen') == 'Firma A'
            assert daten_b.get('unternehmen') == 'Firma B'
            # Cross-check: A does not leak into B and vice versa
            assert daten_a.get('unternehmen') != daten_b.get('unternehmen')
        finally:
            _clean_sids(sid_a, sid_b)

    def test_disconnect_cleanup(self):
        """pop_session_state entfernt SID aus _per_sid_profile, _session_state und _per_sid_transcript."""
        sid = 'test-sid-cleanup'
        ls.set_profile_for_sid(sid, 'Test', {'x': 1})
        ls.init_session_state(sid, user_id=99, org_id=1)
        # Transkript-Buffer-Eintrag anlegen
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript[sid] = [{'text': 'hello', 'line_id': 1}]

        ls.pop_session_state(sid)

        name, daten = ls.get_profile_for_sid(sid)
        assert name == '', f"After pop, profile name should be empty, got {name!r}"
        assert daten == {}, f"After pop, profile daten should be empty dict, got {daten!r}"
        with ls._session_state_lock:
            assert sid not in ls._session_state, "SID should be removed from _session_state after disconnect"
        with ls._per_sid_transcript_lock:
            assert sid not in ls._per_sid_transcript, "SID should be removed from _per_sid_transcript after disconnect"

    def test_tier1_isolation(self):
        """Tier-1 DSGVO-Keys: user_id und org_id sind pro SID isoliert."""
        sid_1 = 'test-tier1-sid-1'
        sid_2 = 'test-tier1-sid-2'
        try:
            ls.init_session_state(sid_1, user_id=101, org_id=5)
            ls.init_session_state(sid_2, user_id=202, org_id=7)

            with ls._session_state_lock:
                state_1 = dict(ls._session_state.get(sid_1, {}))
                state_2 = dict(ls._session_state.get(sid_2, {}))

            assert state_1['user_id'] == 101
            assert state_2['user_id'] == 202
            assert state_1['org_id'] == 5
            assert state_2['org_id'] == 7
            # Tier-1 cross-check: user_id nicht kontaminiert
            assert state_1['user_id'] != state_2['user_id']
        finally:
            _clean_sids(sid_1, sid_2)

    def test_unknown_sid_fallback(self):
        """get_profile_for_sid fuer unbekannte SID gibt ('', {}) zurueck ohne Exception."""
        result = ls.get_profile_for_sid('definitely-nonexistent-sid-xyz-123')
        assert result == ('', {}), f"Unknown SID should return ('', {{}}), got {result!r}"

    def test_init_session_state_required_keys(self):
        """init_session_state erstellt Eintrag mit allen DSGVO-Pflicht-Keys."""
        sid = 'test-init-keys'
        try:
            ls.init_session_state(sid, user_id=42, org_id=3, profile_id=7,
                                  market='dach', language='de', mode='meeting')
            with ls._session_state_lock:
                state = ls._session_state.get(sid)
            assert state is not None, "SID should be in _session_state after init"
            required_keys = ['user_id', 'org_id', 'active_profile_id', 'kaufbereitschaft',
                              'conversation_log', 'berater_words', 'kunde_words',
                              'roles_swapped', 'covered_phases']
            for key in required_keys:
                assert key in state, f"Required key {key!r} missing from _session_state[sid]"
            assert state['user_id'] == 42
            assert state['org_id'] == 3
            assert state['active_profile_id'] == 7
            assert state['kaufbereitschaft'] == 30
            assert isinstance(state['conversation_log'], list)
            assert isinstance(state['covered_phases'], set)
        finally:
            _clean_sids(sid)

    def test_concurrent_sid_writes_no_cross_contamination(self):
        """Thread-Safety: zwei Threads schreiben gleichzeitig verschiedene SIDs ohne Interferenz."""
        sid_x = 'test-thread-x'
        sid_y = 'test-thread-y'
        errors = []

        def write_x():
            for _ in range(50):
                ls.set_profile_for_sid(sid_x, 'PX', {'key': 'X'})
                name, _ = ls.get_profile_for_sid(sid_x)
                if name != 'PX':
                    errors.append(f"SID-X contaminated: got {name!r}")

        def write_y():
            for _ in range(50):
                ls.set_profile_for_sid(sid_y, 'PY', {'key': 'Y'})
                name, _ = ls.get_profile_for_sid(sid_y)
                if name != 'PY':
                    errors.append(f"SID-Y contaminated: got {name!r}")

        try:
            t1 = threading.Thread(target=write_x)
            t2 = threading.Thread(target=write_y)
            t1.start(); t2.start()
            t1.join(); t2.join()
            assert not errors, f"Thread-safety violations: {errors}"
        finally:
            _clean_sids(sid_x, sid_y)

    def test_no_module_global_profile_on_import(self):
        """
        Import von live_session befuellt kein Profil vor.
        Nach Import ist _per_sid_profile leer fuer neue SIDs.
        Runtime-Check: wenn _load_initial_profile noch existieren wuerde,
        wuerde es active_profile_data global setzen — dieses Global existiert nicht mehr.
        """
        import services.live_session as ls_fresh
        # Neue SID-Abfrage muss ('', {}) liefern — kein vorab gesetztes Global
        test_sid = '__no_global_test_sid__'
        result = ls_fresh.get_profile_for_sid(test_sid)
        assert result == ('', {}), \
            f"Neue SID-Abfrage sollte ('', {{}}) liefern — kein pre-populiertes Global. Got {result!r}"
        # Veraltete Module-Globals duerfen nicht mehr existieren
        assert not hasattr(ls_fresh, 'active_profile_data'), \
            "active_profile_data Module-Global darf nach Phase 08.19.4 nicht existieren"
        assert not hasattr(ls_fresh, 'active_profile_name'), \
            "active_profile_name Module-Global darf nach Phase 08.19.4 nicht existieren"


# ── Latency Measurement Scaffold (D-03) ──────────────────────────────────────
# Phase 08.19.4 erfordert Latenz-Dokumentation fuer N=1/5/10/20/50 parallele Sessions.
# Dieser Scaffold ist KEIN blockierender Test — manuell ausfuehren zur Messung.
#
# Usage: pytest tests/test_session_scoping.py::test_latency_scaffold_n_sessions -s --no-header
#
# Threshold-Tabelle (Schaetzwerte aus RESEARCH.md — nach Launch mit Messwerten fuellen):
#   N=1:   ~1-3ms/cycle    (set+get in-memory, geschaetzt — nach Launch messen)
#   N=5:   ~5-15ms/cycle   (geschaetzt — nach Launch messen)
#   N=10:  ~10-30ms/cycle  (geschaetzt — nach Launch messen)
#   N=20:  ~20-60ms/cycle  (geschaetzt — nach Launch messen)
#   N=50:  ~50-150ms/cycle (geschaetzt — nach Launch messen)
#
# HINWEIS: Claude-Call-Latenz (1-3s) dominiert im analyse_loop — der in-memory
# set/get Overhead ist vernachlaessigbar. Kritische Schwelle:
# N*claude_call_latency > loop_interval -> Sessions fallen zurueck.
# Bei N=5 und claude_latency=3s: 15s Cycle. KRITISCH — siehe SKALIERUNG-Kommentar
# in analyse_loop.
#
# SKALIERUNG: wenn Loop-Cycle bei N Sessions > 3 Sek,
# switch zu ThreadPoolExecutor — siehe Phase Block M (08.19.5 oder spaeter).

@pytest.mark.skip(reason="Manual latency scaffold — run explicitly to measure")
def test_latency_scaffold_n_sessions():
    """Misst Zeit fuer N concurrent set_profile_for_sid + get_profile_for_sid Ops."""
    import time
    N_VALUES = [1, 5, 10, 20, 50]
    for n in N_VALUES:
        sids = [f'perf-sid-{i}' for i in range(n)]
        try:
            for sid in sids:
                ls.set_profile_for_sid(sid, f'Profile-{sid}', {'n': n})
            start = time.monotonic()
            for _ in range(10):  # 10 read cycles
                for sid in sids:
                    ls.get_profile_for_sid(sid)
            elapsed = (time.monotonic() - start) / 10 * 1000
            print(f"N={n:3d}: {elapsed:.1f}ms per cycle (10-iteration average)")
        finally:
            for sid in sids:
                ls.pop_session_state(sid)
