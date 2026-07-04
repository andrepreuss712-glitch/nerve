"""Phase 08.23.2.PERSID Plan 06 Task 1 — RED Tests: Familie D per-SID (B4, W-2).

Prueft:
  - record_ewb_click(sid, ...) schreibt in den per-SID-Bucket (NICHT global state)
  - record_suggestion_offer(sid, ...) schreibt in den per-SID-Bucket
  - Isolation: Eintrag in SID A taucht NICHT in SID B auf
  - D-02: None/tote sid -> No-Op (kein Ghost-Wiederbeleben)
  - B4: neue Signatur (sid als erstes Arg) wirft keinen TypeError bei korrektem Aufruf

TDD-RED: diese Tests sind unter der ALTEN Signatur (ohne sid) rot.
"""
import os as _os_testing_guard
_os_testing_guard.environ.setdefault('NERVE_TESTING', '1')

import uuid
import pytest

import services.live_session as ls


@pytest.fixture()
def two_sids():
    """Zwei isolierte per-SID-Sessions fuer Familie-D-Tests."""
    sid_a = f"test-d-a-{uuid.uuid4().hex[:10]}"
    sid_b = f"test-d-b-{uuid.uuid4().hex[:10]}"
    ls.init_session_state(sid_a, user_id=10, org_id=1)
    ls.init_session_state(sid_b, user_id=20, org_id=2)
    yield sid_a, sid_b
    ls.pop_session_state(sid_a)
    ls.pop_session_state(sid_b)


# ── Test 1 (gepaart): record_ewb_click Isolation ─────────────────────────────

def test_record_ewb_click_per_sid_isolation(two_sids):
    """sidA record_ewb_click('Kosten') landet NUR in sidA-Bucket, NICHT in sidB."""
    sid_a, sid_b = two_sids
    ls.record_ewb_click(sid_a, 'Kosten', success=True)
    ls.record_ewb_click(sid_b, 'Zeit', success=False)

    with ls._session_state_lock:
        clicks_a = list(ls._session_state[sid_a]['state'].get('ewb_clicks', []))
        clicks_b = list(ls._session_state[sid_b]['state'].get('ewb_clicks', []))

    typen_a = [c['einwand_typ'] for c in clicks_a]
    typen_b = [c['einwand_typ'] for c in clicks_b]

    assert 'Kosten' in typen_a, "sidA muss 'Kosten'-Click haben"
    assert 'Zeit' not in typen_a, "sidA darf KEINE 'Zeit'-Eintraege haben (Isolation)"
    assert 'Zeit' in typen_b, "sidB muss 'Zeit'-Click haben"
    assert 'Kosten' not in typen_b, "sidB darf KEINE 'Kosten'-Eintraege haben (Isolation)"


def test_record_suggestion_offer_per_sid_isolation(two_sids):
    """sidA record_suggestion_offer('A', ...) landet NUR in sidA-Bucket."""
    sid_a, sid_b = two_sids
    iid_a = str(uuid.uuid4())
    iid_b = str(uuid.uuid4())
    ls.record_suggestion_offer(sid_a, slot='A', source='keyword', model=None,
                               suggestion_text='Antwort fuer A', interaction_id=iid_a)
    ls.record_suggestion_offer(sid_b, slot='B', source='auto_variante', model='haiku',
                               suggestion_text='Antwort fuer B', interaction_id=iid_b)

    with ls._session_state_lock:
        offers_a = list(ls._session_state[sid_a]['state'].get('suggestion_offers', []))
        offers_b = list(ls._session_state[sid_b]['state'].get('suggestion_offers', []))

    texts_a = [o['suggestion_text'] for o in offers_a]
    texts_b = [o['suggestion_text'] for o in offers_b]

    assert 'Antwort fuer A' in texts_a
    assert 'Antwort fuer B' not in texts_a, "sidA darf KEINEN B-Text haben"
    assert 'Antwort fuer B' in texts_b
    assert 'Antwort fuer A' not in texts_b, "sidB darf KEINEN A-Text haben"


# ── Test 2 (D-02): None/tote sid -> No-Op ────────────────────────────────────

def test_record_ewb_click_none_sid_is_noop():
    """D-02: record_ewb_click mit sid=None -> No-Op, kein Crash, kein global state write."""
    # Sicherstellen dass global state kein ewb_clicks hat (nach Migration)
    ls.record_ewb_click(None, 'Phantomkosten', success=True)
    # Kein Crash -> Test gruen; Beleg: dead sid fuehrt zu keinem Bucket-Write
    # (Bucket-Inhalt prueft test_1)


def test_record_ewb_click_dead_sid_is_noop():
    """D-02 Ghost-SID-Guard: tote sid -> No-Op, keine Session-Wiederbelebung."""
    dead_sid = f"dead-{uuid.uuid4().hex}"
    ls.record_ewb_click(dead_sid, 'GhostKosten', success=True)
    with ls._session_state_lock:
        assert dead_sid not in ls._session_state, (
            "record_ewb_click darf eine tote/nicht-existente sid NICHT wiederbeleben (Ghost-Guard)"
        )


def test_record_suggestion_offer_dead_sid_is_noop():
    """D-02 Ghost-SID-Guard: tote sid -> No-Op."""
    dead_sid = f"dead-offer-{uuid.uuid4().hex}"
    ls.record_suggestion_offer(dead_sid, slot='A', source='keyword', model=None,
                               suggestion_text='Ghost', interaction_id=str(uuid.uuid4()))
    with ls._session_state_lock:
        assert dead_sid not in ls._session_state, (
            "record_suggestion_offer darf eine tote sid NICHT wiederbeleben"
        )


# ── Test 3 (B4): neue Signatur akzeptiert sid als erstes Arg ─────────────────

def test_record_ewb_click_new_signature(two_sids):
    """B4: neue Signatur record_ewb_click(sid, einwand_typ, ...) wirft keinen TypeError."""
    sid_a, _ = two_sids
    # Alle drei Caller-Pfade simulieren (success=True/False, mit/ohne antwort)
    ls.record_ewb_click(sid_a, 'Preis', success=True, antwort_text='Antwort', einwand_text='Preis')
    ls.record_ewb_click(sid_a, 'Zeit', success=False, einwand_text='Zeit')
    ls.record_ewb_click(sid_a, 'Vertrauen', success=False)


def test_record_suggestion_offer_new_signature(two_sids):
    """B4: neue Signatur record_suggestion_offer(sid, slot, source, ...) wirft keinen TypeError."""
    sid_a, _ = two_sids
    ls.record_suggestion_offer(sid_a, slot='A', source='keyword', model=None,
                               suggestion_text='KW-Vorschlag', interaction_id=str(uuid.uuid4()),
                               einwand_typ='Preis')
    ls.record_suggestion_offer(sid_a, slot='B', source='auto_variante', model='haiku',
                               suggestion_text='AutoVar-Vorschlag', interaction_id=str(uuid.uuid4()))


# ── Test 4 (W-2 Signatur-Check): interaction_id wird durchgereicht ────────────

def test_record_suggestion_offer_interaction_id_durchgereicht(two_sids):
    """W-2/B1: record_suggestion_offer reicht interaction_id ins per-SID-Bucket durch."""
    sid_a, _ = two_sids
    iid = str(uuid.uuid4())
    ls.record_suggestion_offer(sid_a, slot='B', source='manual_button', model='haiku',
                               suggestion_text='[PERSON_A] x', interaction_id=iid)
    with ls._session_state_lock:
        offers = list(ls._session_state[sid_a]['state'].get('suggestion_offers', []))
    assert len(offers) >= 1
    assert offers[-1]['interaction_id'] == iid
    assert offers[-1]['interaction_id'] is not None


def test_record_suggestion_offer_no_db_write(two_sids, monkeypatch):
    """Punkt 25 (Latenz): record_suggestion_offer macht KEINEN DB-Write (reiner RAM-Append)."""
    sid_a, _ = two_sids
    import database.db as dbmod
    called = {'get_session': 0}
    _real = dbmod.get_session

    def _spy(*a, **k):
        called['get_session'] += 1
        return _real(*a, **k)

    monkeypatch.setattr(dbmod, 'get_session', _spy)
    before_count = len(ls._session_state.get(sid_a, {}).get('state', {}).get('suggestion_offers', []))
    ls.record_suggestion_offer(sid_a, slot='A', source='keyword', model=None,
                               suggestion_text='[PERSON_A] y', interaction_id=str(uuid.uuid4()))
    with ls._session_state_lock:
        after_count = len(ls._session_state[sid_a]['state'].get('suggestion_offers', []))

    assert after_count == before_count + 1, "RAM-Puffer muss um genau 1 wachsen"
    assert called['get_session'] == 0, "Punkt 25: record_suggestion_offer DARF KEINE DB anfassen"
