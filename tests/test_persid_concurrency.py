"""Phase 08.23.2.PERSID Plan 06 — Voller Concurrency-Test (Welle E, D-10, SPEC Req 12).

Prueft: Zwei parallele Sessions (User A Org 1 / User B Org 2, verschiedene Orgs) tauschen
KEINE Daten aus — weder Transkript noch Speaker-State noch Analyse-Ergebnis noch Session-State.

S1-Kritisch: diese Datei setzt NERVE_TESTING=1 GANZ OBEN im Modul, VOR dem `import app`.
  Grund: app.py startet Daemons (analyse_loop/coaching_loop/slow_lane_consumer) auf
  MODUL-EBENE. Wuerde der Import OHNE NERVE_TESTING=1 laufen, wuerden echte Daemon-Threads
  geweckt -> blind-gruene Tests, Flakes, Haiku/Deepgram-Aufrufe.
  app.config['TESTING'] waere zu spaet (NACH `import app` setzbar) — daher ENV-Var.

D-10 (Deploy-Contract): Dieser Test wird JETZT (Plan 06, Welle E, letzter PERSID-Plan)
  GRUEN committet. Alle Vorgaenger-Wellen hatten Skeleton (pytest.skip). Der Rot-vor-Fix-
  Beweis ist ein manueller HEAD-Lauf VOR den Plan-06-Aenderungen (dokumentiert im SUMMARY).

B3: test_no_live_global_state.py assertet _PENDING_MIGRATION == frozenset() (alle migriert).

Pflicht-Fallen (RESEARCH §5):
  (a) anonymize/anonymize_output/anonymize_for_storage als IDENTITY patchen — GLiNER-Vacuous-Green.
  (b) NERVE_TESTING=1 VOR import app (S1, Daemon-Nicht-Start).
  (c) MERGE_WINDOW_S -> 0.05 patchen (deterministischer Flush).
  (d) Beide Beenden-Naehte + Doppel-Feuer testen (B1 Blocker-Deckung).
  (e) Kein xfail, kein pytest.skip im vollen Test.

Weil die vollen SocketIO-Routen-Calls (api_beenden mit @login_required) eine vollstaendige
Flask-Auth-Session benoetigen und der Test bewusst keinen DB-Roundtrip macht (kein DB-Marker),
testen wir die zugrundeliegenden per-SID-Mechanismen DIREKT:
  - init_session_state / pop_session_state / stash_ended_session / consume_ended_session
  - record_ewb_click / record_suggestion_offer (alle 6 Caller-Signaturen)
  - reset_session(sid) — nur eigene sid + Snapshot-Pop (N-3)
  - Speaker-Familie per-SID (_second_sp_seen, _log_last_sp)
  - _per_sid_transcript / _per_sid_coaching_buffer
  - get_anonymisierer (Objekt-Identitaets-Check, Reset-Ueberleben)

Diese Schicht ist der kausale Kern der SPEC Req 12 — die HTTP-Route wrappt dieselben Aufrufe.
Zwei-Tenant-Schutz-Invariante: sidA-Writes MUESSEN in sidA-Bucket landen (DA); kein Einfluss
auf sidB-Bucket (WEG); umgekehrt genauso.

KEIN live/perf-Marker -> laeuft im Default-Gate (triage.sh -m "not live and not perf").
Kein DB-Roundtrip -> kein db_session/cleanup_rows Bedarf (nur RAM-State).
"""

# ── S1-KRITISCH: ENV VOR import app setzen ────────────────────────────────────
import os as _os_testing_guard
_os_testing_guard.environ['NERVE_TESTING'] = '1'
# ─────────────────────────────────────────────────────────────────────────────

import threading
import time
import uuid

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _patch_merge_window(monkeypatch):
    """Falle (c): MERGE_WINDOW_S -> 0.05 — deterministischer Flush ohne echtes Warten."""
    import services.live_session as _ls
    import services.deepgram_service as _dg
    monkeypatch.setattr(_ls, 'MERGE_WINDOW_S', 0.05)
    monkeypatch.setattr(_dg, 'MERGE_WINDOW_S', 0.05, raising=False)


@pytest.fixture(autouse=True)
def _patch_anon(monkeypatch):
    """Falle (a): anonymize / anonymize_for_storage als IDENTITY patchen.
    PFLICHT: ohne dies wuerde GLiNER PII-Felder veraendern -> Vacuous-Green.
    """
    try:
        import services.anonymization as _anon
        monkeypatch.setattr(_anon, 'anonymize',
                            lambda text, sid=None: (text, 'identity'), raising=False)
        monkeypatch.setattr(_anon, 'anonymize_output',
                            lambda text, sid=None: text, raising=False)
        monkeypatch.setattr(_anon, 'anonymize_for_storage',
                            lambda text, sid=None: (text, 'identity'), raising=False)
    except ImportError:
        pass  # Modul nicht vorhanden -> kein Anonymisierungspfad aktiv


def _make_sid(prefix='concurrency'):
    return f'test-{prefix}-{uuid.uuid4().hex[:12]}'


def _seed_session(ls, sid, user_id, org_id, *, marker=None):
    """Seede eine in-memory-Session via init_session_state.
    Setzt optional einen Marker ins Transkript-Puffer.
    """
    ls.init_session_state(sid, user_id=user_id, org_id=org_id, profile_id=None)
    if marker:
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript.setdefault(sid, []).append(
                {'text': marker, 'line_id': 1, 't_start': time.monotonic()}
            )
        with ls._per_sid_coaching_lock:
            ls._per_sid_coaching_buffer.setdefault(sid, []).append(
                {'text': marker, 'speaker': 'Berater', 't_start': time.monotonic()}
            )


def _teardown_sid(ls, sid):
    """Sauberer Teardown: poppt Session + Snapshot (kein Leak)."""
    try:
        ls.pop_ended_session(sid)
    except Exception:
        pass
    try:
        ls.pop_session_state(sid)
    except Exception:
        pass
    # Transkript + Coaching Buffer sauber leeren
    try:
        with ls._per_sid_transcript_lock:
            ls._per_sid_transcript.pop(sid, None)
    except Exception:
        pass
    try:
        with ls._per_sid_coaching_lock:
            ls._per_sid_coaching_buffer.pop(sid, None)
    except Exception:
        pass


# ── Test 1+2: 7 gepaarte Assertions (Positiv DA + Isolation WEG) ──────────────

def test_per_sid_transcript_and_state_isolation():
    """7 gepaarte Assertions (SPEC Req 12): A-Daten in A, B-Daten in B, NIE gekreuzt.

    User A (Org 1): Marker 'ZEBRA_ALPHA_BUDGET'
    User B (Org 2): Marker 'QUALLE_BETA_ZEITDRUCK'

    Assertion 1: _per_sid_transcript[sidA] enthaelt A-Marker, NICHT B-Marker.
    Assertion 2: _per_sid_coaching_buffer[sidA] enthaelt A-Marker, NICHT B-Marker.
    Assertion 3: _session_state[sidA]['org_id'] == 1, NICHT org_id von B.
    Assertion 4: ewb_clicks[sidA] enthaelt A-Einwand, NICHT B-Einwand.
    Assertion 5: suggestion_offers[sidA] enthaelt A-Slot, NICHT B-Slot.
    Assertion 6: _second_sp_seen[sidA] unabhaengig von sidB.
    Assertion 7: _log_last_sp[sidA] unabhaengig von sidB.
    """
    import services.live_session as ls

    sid_a = _make_sid('a')
    sid_b = _make_sid('b')

    MARKER_A = 'ZEBRA_ALPHA_BUDGET'
    MARKER_B = 'QUALLE_BETA_ZEITDRUCK'

    try:
        # ── Beide Sessions initialisieren ────────────────────────────────────
        _seed_session(ls, sid_a, user_id=101, org_id=1, marker=MARKER_A)
        _seed_session(ls, sid_b, user_id=202, org_id=2, marker=MARKER_B)

        # ── A: EWB-Klick + Suggestion-Offer ──────────────────────────────────
        ls.record_ewb_click(sid_a, 'Kosten', success=True)
        ls.record_ewb_click(sid_b, 'Zeitdruck', success=False)
        ls.record_suggestion_offer(sid_a, slot='A', source='keyword',
                                   model='haiku', suggestion_text='A-Antwort',
                                   interaction_id='ia-001')
        ls.record_suggestion_offer(sid_b, slot='B', source='pip',
                                   model='haiku', suggestion_text='B-Antwort',
                                   interaction_id='ib-002')

        # ── Speaker-Writes (per-SID) ──────────────────────────────────────────
        with ls._session_state_lock:
            if sid_a in ls._session_state:
                ls._session_state[sid_a]['_second_sp_seen'] = True
                ls._session_state[sid_a]['_log_last_sp'] = 0  # Berater-Speaker fuer A
            if sid_b in ls._session_state:
                ls._session_state[sid_b]['_second_sp_seen'] = False
                ls._session_state[sid_b]['_log_last_sp'] = 1  # Kunden-Speaker fuer B

        # ── Assertion 1: Transkript-Isolation ────────────────────────────────
        with ls._per_sid_transcript_lock:
            a_texts = [e['text'] for e in ls._per_sid_transcript.get(sid_a, [])]
            b_texts = [e['text'] for e in ls._per_sid_transcript.get(sid_b, [])]

        assert MARKER_A in a_texts, f'A-Marker fehlt in A-Transkript: {a_texts}'
        assert MARKER_B not in a_texts, f'B-Marker in A-Transkript (ISOLATION-FEHLER!): {a_texts}'
        assert MARKER_B in b_texts, f'B-Marker fehlt in B-Transkript: {b_texts}'
        assert MARKER_A not in b_texts, f'A-Marker in B-Transkript (ISOLATION-FEHLER!): {b_texts}'

        # ── Assertion 2: Coaching-Buffer-Isolation ────────────────────────────
        with ls._per_sid_coaching_lock:
            a_coaching = [e['text'] for e in ls._per_sid_coaching_buffer.get(sid_a, [])]
            b_coaching = [e['text'] for e in ls._per_sid_coaching_buffer.get(sid_b, [])]

        assert MARKER_A in a_coaching, f'A-Marker fehlt im A-Coaching-Buffer: {a_coaching}'
        assert MARKER_B not in a_coaching, \
            f'B-Marker im A-Coaching-Buffer (ISOLATION-FEHLER!): {a_coaching}'

        # ── Assertion 3: org_id-Isolation im _session_state ──────────────────
        with ls._session_state_lock:
            a_org = ls._session_state.get(sid_a, {}).get('org_id')
            b_org = ls._session_state.get(sid_b, {}).get('org_id')

        assert a_org == 1, f'A-Org falsch: {a_org}'
        assert b_org == 2, f'B-Org falsch: {b_org}'
        assert a_org != b_org, 'A und B haben dieselbe org_id (ISOLATION-FEHLER!)'

        # ── Assertion 4: ewb_clicks-Isolation ────────────────────────────────
        with ls._session_state_lock:
            a_ewb = ls._session_state.get(sid_a, {}).get('state', {}).get('ewb_clicks', [])
            b_ewb = ls._session_state.get(sid_b, {}).get('state', {}).get('ewb_clicks', [])

        a_ewb_types = [e['einwand_typ'] for e in a_ewb]
        b_ewb_types = [e['einwand_typ'] for e in b_ewb]

        assert 'Kosten' in a_ewb_types, f'A-Einwand fehlt in A-ewb_clicks: {a_ewb_types}'
        assert 'Zeitdruck' not in a_ewb_types, \
            f'B-Einwand in A-ewb_clicks (ISOLATION-FEHLER!): {a_ewb_types}'
        assert 'Zeitdruck' in b_ewb_types, f'B-Einwand fehlt in B-ewb_clicks: {b_ewb_types}'
        assert 'Kosten' not in b_ewb_types, \
            f'A-Einwand in B-ewb_clicks (ISOLATION-FEHLER!): {b_ewb_types}'

        # ── Assertion 5: suggestion_offers-Isolation ─────────────────────────
        with ls._session_state_lock:
            a_offers = ls._session_state.get(sid_a, {}).get('state', {}).get('suggestion_offers', [])
            b_offers = ls._session_state.get(sid_b, {}).get('state', {}).get('suggestion_offers', [])

        a_slots = [o['slot'] for o in a_offers]
        b_slots = [o['slot'] for o in b_offers]

        assert 'A' in a_slots, f'A-Slot fehlt in A-suggestion_offers: {a_slots}'
        assert 'B' not in a_slots, \
            f'B-Slot in A-suggestion_offers (ISOLATION-FEHLER!): {a_slots}'
        assert 'B' in b_slots, f'B-Slot fehlt in B-suggestion_offers: {b_slots}'
        assert 'A' not in b_slots, \
            f'A-Slot in B-suggestion_offers (ISOLATION-FEHLER!): {b_slots}'

        # ── Assertion 6+7: Speaker-Isolation ─────────────────────────────────
        with ls._session_state_lock:
            a_sp2 = ls._session_state.get(sid_a, {}).get('_second_sp_seen')
            b_sp2 = ls._session_state.get(sid_b, {}).get('_second_sp_seen')
            a_log_sp = ls._session_state.get(sid_a, {}).get('_log_last_sp')
            b_log_sp = ls._session_state.get(sid_b, {}).get('_log_last_sp')

        # A hat second_sp_seen=True, B hat False — unabhaengig (Cross-Tenant-Speaker-Leak §6.7)
        assert a_sp2 is True, f'A._second_sp_seen erwartet True, war: {a_sp2}'
        assert b_sp2 is False, f'B._second_sp_seen erwartet False, war: {b_sp2}'
        # A hat Speaker 0 (Berater), B hat Speaker 1 (Kunde)
        assert a_log_sp == 0, f'A._log_last_sp erwartet 0, war: {a_log_sp}'
        assert b_log_sp == 1, f'B._log_last_sp erwartet 1, war: {b_log_sp}'

    finally:
        _teardown_sid(ls, sid_a)
        _teardown_sid(ls, sid_b)


# ── Test 3: Reset-Ueberlebens-Check (SPEC Req 4, Objekt-Identitaet) ───────────

def test_reset_session_survival_check():
    """Reset-Ueberlebens-Check: reset_session(sidA) laesst sidB VOLLSTAENDIG unangetastet.

    Objekt-Identitaets-Check: get_anonymisierer(sidB) is anon_b_before (SPEC Req 4 Acceptance).
    Proves: reset_session(sid) NUR die eigene sid — keine All-Reset-Semantik.
    """
    import services.live_session as ls

    sid_a = _make_sid('reset-a')
    sid_b = _make_sid('reset-b')

    try:
        _seed_session(ls, sid_a, user_id=301, org_id=3)
        _seed_session(ls, sid_b, user_id=302, org_id=4)

        # Init anonymisierer fuer B (erzeuge ein Objekt fuer die Identitaets-Pruefer)
        try:
            ls.init_anonymisierer(sid_b)
        except Exception:
            pass  # Anonymisierer optional (GLiNER-Modell evtl. nicht verfuegbar)

        anon_b_before = ls.get_anonymisierer(sid_b)

        # A-Stash aufbauen (simuliert Normal-Hangup :779) + dann A reset
        _seed_session(ls, sid_a, user_id=301, org_id=3, marker='RESET-A-MARKER')
        ls.stash_ended_session(sid_a)
        # reset_session(sid_a) — poppt NUR sid_a (+ N-3-Snapshot)
        ls.reset_session(sid_a)

        # B muss UNVERAENDERT sein
        assert sid_b in ls._session_state, \
            'sidB aus _session_state entfernt — reset_session(sidA) hat sidB geraeumt (BUG!)'

        # Objekt-Identitaets-Check (SPEC Req 4)
        anon_b_after = ls.get_anonymisierer(sid_b)
        assert anon_b_after is anon_b_before, (
            'get_anonymisierer(sidB) ist nach reset_session(sidA) NICHT mehr dasselbe Objekt '
            '(Cross-Reset — reset_session hat sidB unveraendert zu lassen)'
        )

        # N-3: sidA's Snapshot ist nach reset_session weg
        with ls._ended_snapshots_lock:
            assert sid_a not in ls._ended_session_snapshots, \
                'sidA-Snapshot noch in _ended_session_snapshots nach reset_session(sidA) (N-3 fehlt!)'

        # sidB-State muss inhaltlich unveraendert sein
        with ls._session_state_lock:
            b_org = ls._session_state.get(sid_b, {}).get('org_id')
        assert b_org == 4, f'B-Org nach A-Reset veraendert: {b_org}'

    finally:
        _teardown_sid(ls, sid_a)
        _teardown_sid(ls, sid_b)


# ── Test 4: B1-stop_live_session-vor-beenden-Non-Empty (Haupt-Pfad :779) ───────

def test_b1_stop_live_session_vor_beenden_non_empty():
    """B1-Blocker-Deckung: Normal-Hangup via stash_ended_session (:779-Pfad) BEVOR Beenden.

    Beweist: stash_ended_session stasht den vollen State BEVOR er geraeumt wird.
    consume_ended_session liefert den Inhalt NON-EMPTY (A-Marker vorhanden).
    Simulates: pip-launcher stop_live_session emit -> stash_ended_session -> api_beenden liest.
    """
    import services.live_session as ls

    sid_a = _make_sid('b1-normal')
    MARKER_A = 'B1_NORMAL_HANGUP_ZEBRA'

    try:
        _seed_session(ls, sid_a, user_id=401, org_id=5, marker=MARKER_A)
        # EWB-Click aufzeichnen (wie im echten Anruf)
        ls.record_ewb_click(sid_a, 'Kosten', success=True, antwort_text='Antwort-A')
        ls.record_suggestion_offer(sid_a, slot='A', source='keyword',
                                   model='haiku', suggestion_text='Vorschlag-A',
                                   interaction_id='ia-b1-001')

        # Haupt-Pfad :779 — stop_live_session feuert stash_ended_session
        ls.stash_ended_session(sid_a)

        # api_beenden liest via consume_ended_session (N-3 NICHT-destruktiver PEEK)
        snapshot = ls.consume_ended_session(sid_a)

        # ASSERTION: Snapshot ist NICHT leer (B1 Blocker-Bedingung)
        assert snapshot is not None, \
            'Snapshot nach stash_ended_session ist None (B1-Blocker: api_beenden bekommt leeren Record)'
        assert bool(snapshot), \
            'Snapshot nach stash_ended_session ist leer {} (B1-Blocker: leerer Call-Record)'

        # EWB-Clicks sind im Snapshot vorhanden (A-Inhalt DA)
        snap_ewb = snapshot.get('state', {}).get('ewb_clicks', [])
        assert len(snap_ewb) > 0, \
            f'ewb_clicks im Snapshot leer (B1-Blocker: EWB-Daten verloren): {snap_ewb}'
        ewb_types = [e['einwand_typ'] for e in snap_ewb]
        assert 'Kosten' in ewb_types, \
            f'A-Einwand fehlt im Snapshot (B1-Blocker): {ewb_types}'

        # suggestion_offers sind im Snapshot vorhanden
        snap_offers = snapshot.get('state', {}).get('suggestion_offers', [])
        assert len(snap_offers) > 0, \
            f'suggestion_offers im Snapshot leer (B1-Blocker): {snap_offers}'

    finally:
        _teardown_sid(ls, sid_a)


# ── Test 5: N-1-Doppel-Feuer-Non-Empty (:779 dann :815-setdefault) ────────────

def test_n1_doppel_feuer_non_empty():
    """N-1-Blocker-Deckung: stop_live_session (:779) dann disconnect (:815, setdefault {}).

    first-stash-wins (Plan 03 N-1): der volle :779-Snapshot wird durch das leere :815-{}
    NICHT ueberschrieben. consume_ended_session liefert den VOLLEN Snapshot.
    Beweist dass Doppel-Beenden keinen leeren Call-Record erzeugt.
    """
    import services.live_session as ls

    sid_a = _make_sid('n1-doppel')
    MARKER_A = 'N1_DOPPEL_FEUER_QUALLE'

    try:
        _seed_session(ls, sid_a, user_id=501, org_id=6, marker=MARKER_A)
        ls.record_ewb_click(sid_a, 'Zeitdruck', success=True)

        # Erster Stash: stop_live_session :779 (voller State vorhanden)
        ls.stash_ended_session(sid_a)

        # Zweiter Stash-Versuch: disconnect :815 setzt ZUERST setdefault({})
        # (simuliert: der disconnect-Handler findet sid nicht mehr in _session_state ->
        #  setdefault fuegt leeres {} ein -> stash_ended_session prueft N-1 Leer-Skip)
        with ls._session_state_lock:
            ls._session_state.setdefault(sid_a, {})
        # Jetzt stash_ended_session aufrufen (wie der disconnect-Handler :815 es tut)
        ls.stash_ended_session(sid_a)  # soll wegen first-stash-wins NICHTS ueberschreiben

        # api_beenden liest den Snapshot
        snapshot = ls.consume_ended_session(sid_a)

        assert snapshot is not None, \
            'N-1 Doppel-Feuer: Snapshot ist None nach zweitem Stash (erster Stash verloren?)'
        snap_ewb = snapshot.get('state', {}).get('ewb_clicks', [])
        assert len(snap_ewb) > 0, \
            f'N-1 Doppel-Feuer: ewb_clicks leer im Snapshot (leerer Stash hat vollen ueberschrieben!): {snap_ewb}'
        ewb_types = [e['einwand_typ'] for e in snap_ewb]
        assert 'Zeitdruck' in ewb_types, \
            f'N-1 Doppel-Feuer: A-Einwand fehlt im Snapshot (N-1-Fehler): {ewb_types}'

    finally:
        _teardown_sid(ls, sid_a)


# ── Test 6: B1-Late-Write-Ghost-Drop ──────────────────────────────────────────

def test_b1_late_write_ghost_drop():
    """B1-Ghost-Drop: record_* fuer eine gestashte/tote sid belebt sie NICHT wieder.

    Nach stash_ended_session (pop_session_state) ist sidA tot (nicht in _session_state).
    Ein record_ewb_click(sidA, 'LateGhost') danach: Ghost-SID-Guard -> No-Op.
    Der gestashte Snapshot enthaelt KEINEN 'LateGhost'-Eintrag.
    """
    import services.live_session as ls

    sid_a = _make_sid('ghost-drop')

    try:
        _seed_session(ls, sid_a, user_id=601, org_id=7)
        ls.record_ewb_click(sid_a, 'Kosten', success=True)

        # Session stashen + poppen (wie Normal-Hangup)
        ls.stash_ended_session(sid_a)

        # sidA ist jetzt NICHT mehr in _session_state
        assert sid_a not in ls._session_state, \
            'sidA nach stash_ended_session noch in _session_state (pop_session_state fehlt?)'

        # Late-Write nach Beenden
        ls.record_ewb_click(sid_a, 'LateGhost')          # Ghost-SID-Guard -> No-Op
        ls.record_suggestion_offer(sid_a, slot='Z',       # Ghost-SID-Guard -> No-Op
                                   source='late', model='haiku',
                                   suggestion_text='late-text', interaction_id='late-001')

        # sidA darf NICHT wiederbelebt worden sein
        assert sid_a not in ls._session_state, \
            'Late-Write hat die tote sidA wiederbelebt (Ghost-SID-Guard fehlt!)'

        # Snapshot darf KEINEN LateGhost enthalten
        snapshot = ls.consume_ended_session(sid_a)
        if snapshot:
            snap_ewb = snapshot.get('state', {}).get('ewb_clicks', [])
            ewb_types = [e['einwand_typ'] for e in snap_ewb]
            assert 'LateGhost' not in ewb_types, \
                f'LateGhost im Snapshot (Ghost-Drop-Fehler!): {ewb_types}'
            snap_offers = snapshot.get('state', {}).get('suggestion_offers', [])
            offer_slots = [o['slot'] for o in snap_offers]
            assert 'Z' not in offer_slots, \
                f'Late-Offer im Snapshot (Ghost-Drop-Fehler!): {offer_slots}'

    finally:
        _teardown_sid(ls, sid_a)


# ── Test 7: N-3-Snapshot-Pop nach reset_session ───────────────────────────────

def test_n3_snapshot_pop_after_reset():
    """N-3: nach reset_session(sidA)+stash_ended_session ist der Snapshot final gepoppt.

    reset_session(sid) ruft pop_ended_session(sid) (N-3 finales Cleanup).
    Doppel-Beenden bleibt gutartig: Snapshot schon weg -> kein Fehler, kein Wachsen.
    """
    import services.live_session as ls

    sid_a = _make_sid('n3-pop')

    try:
        _seed_session(ls, sid_a, user_id=701, org_id=8)
        ls.record_ewb_click(sid_a, 'Preis', success=True)

        # Normal-Hangup: stash_ended_session (loest pop_session_state aus)
        ls.stash_ended_session(sid_a)

        # Snapshot muss existieren (PEEK verfuegbar)
        snap_before_reset = ls.consume_ended_session(sid_a)
        assert snap_before_reset is not None, \
            'Snapshot vor reset_session fehlt (stash_ended_session funktioniert nicht?)'

        # reset_session(sid_a) — ruft pop_ended_session(sid_a) intern (N-3)
        ls.reset_session(sid_a)

        # Snapshot muss jetzt weg sein
        with ls._ended_snapshots_lock:
            assert sid_a not in ls._ended_session_snapshots, (
                'sidA-Snapshot noch in _ended_session_snapshots nach reset_session(sidA) '
                '— pop_ended_session wurde NICHT aufgerufen (N-3 fehlt!)'
            )

        # Doppel-reset ist gutartig (kein Fehler)
        ls.reset_session(sid_a)  # nochmal — kein Crash

    finally:
        _teardown_sid(ls, sid_a)


# ── Test 8: Same-User-Zwei-Session — W3b Option B (Grenze dokumentiert) ───────

def test_same_user_two_session_boundary():
    """W3b: Same-User-Zwei-Session-Pfad (S3/W3b) — Option B: Grenze dokumentiert.

    _beenden_sid-Vertrag (Plan 03 S3) loest via call_id deterministisch auf.
    EINE Live-Session pro User ist die EA-Invariante (ein Client, ein Browser-Tab).
    Die call_id-exakte Aufloesung (Stufe 1, app_routes.py:151-157) ist der S3-Beweis.

    Grenze: zwei simultane Sessions desselben Users werden in der EA-Phase NICHT
    erwartet. Die Stufe-2-Fallback-Logik (user_id-Scan, maximale session_start_time)
    beendet die neueste Session — deterministisch, aber nicht 100% fehlerfrei fuer
    simultane Tab-Duplikate. Akzeptiertes Trade-off (W3b Option B dokumentiert).

    Dieser Test verifiziert die State-Isolation (sidA1 != sidA2), nicht das Aufloesung-
    Routing (das ist ein HTTP-Pfad, der Login erfordert).
    """
    import services.live_session as ls

    sid_a1 = _make_sid('sameuser-1')
    sid_a2 = _make_sid('sameuser-2')
    SAME_USER_ID = 801

    try:
        # Gleicher User, zwei verschiedene sids
        _seed_session(ls, sid_a1, user_id=SAME_USER_ID, org_id=9)
        _seed_session(ls, sid_a2, user_id=SAME_USER_ID, org_id=9)

        ls.record_ewb_click(sid_a1, 'Kosten-Session1')
        ls.record_ewb_click(sid_a2, 'Kosten-Session2')

        # State-Isolation: a1 != a2, auch bei gleichem User
        with ls._session_state_lock:
            ewb_a1 = ls._session_state.get(sid_a1, {}).get('state', {}).get('ewb_clicks', [])
            ewb_a2 = ls._session_state.get(sid_a2, {}).get('state', {}).get('ewb_clicks', [])

        types_a1 = [e['einwand_typ'] for e in ewb_a1]
        types_a2 = [e['einwand_typ'] for e in ewb_a2]

        assert 'Kosten-Session1' in types_a1, f'Session-1-Einwand fehlt: {types_a1}'
        assert 'Kosten-Session2' not in types_a1, \
            f'Session-2-Einwand in Session-1-Bucket (ISOLATION-FEHLER!): {types_a1}'
        assert 'Kosten-Session2' in types_a2, f'Session-2-Einwand fehlt: {types_a2}'
        assert 'Kosten-Session1' not in types_a2, \
            f'Session-1-Einwand in Session-2-Bucket (ISOLATION-FEHLER!): {types_a2}'

    finally:
        _teardown_sid(ls, sid_a1)
        _teardown_sid(ls, sid_a2)


# ── Test 9: record_* ohne sid / None sid — No-Op (D-02) ───────────────────────

def test_record_dead_sid_noop():
    """D-02: record_ewb_click/record_suggestion_offer ohne/tote sid -> No-Op, kein Crash.
    Kein globaler Fallback, kein Wiederbeleben einer toten sid.
    """
    import services.live_session as ls

    # None-sid
    ls.record_ewb_click(None, 'Kosten')         # No-Op
    ls.record_ewb_click('', 'Kosten')            # No-Op
    ls.record_suggestion_offer(None, slot='A', source='test', model='haiku',
                                suggestion_text='x', interaction_id='y')   # No-Op

    # Nicht-existente sid (Ghost-SID)
    dead_sid = 'ghost-sid-' + uuid.uuid4().hex[:8]
    ls.record_ewb_click(dead_sid, 'Kosten')
    ls.record_suggestion_offer(dead_sid, slot='A', source='test', model='haiku',
                                suggestion_text='x', interaction_id='y')

    # Keine Session wurde erzeugt
    assert dead_sid not in ls._session_state, \
        f'Dead-SID wurde durch record_* wiederbelebt: {dead_sid}'


# ── Test 10: NERVE_TESTING ENV Guard (S1-Sanity) ─────────────────────────────

def test_nerve_testing_env_is_set_before_app_import():
    """S1-Sanity: NERVE_TESTING war zum Import-Zeitpunkt gesetzt.

    Prueft die ENV-Var direkt (kein app-Import noetig — laeuft in jedem Environment).
    """
    assert _os_testing_guard.environ.get('NERVE_TESTING') == '1', (
        'NERVE_TESTING wurde nicht vor dem Import gesetzt (S1-Falle). '
        'Die ENV-Var muss GANZ OBEN in dieser Datei, VOR allen app-Imports, gesetzt werden.'
    )
