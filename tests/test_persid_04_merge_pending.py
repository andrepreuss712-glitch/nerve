"""Phase 08.23.2.PERSID Plan 04 — Tests fuer per-SID _merge_pending (Familie B).

TDD-RED: diese Tests ROETEN vor der Implementierung, da _merge_pending noch modul-global ist.

Drei Kern-Verhaltenspruefungen:
  Test 1 (Isolation): zwei SIDs A/B, gleicher Sprecher-Key "0"; nach Flush enthaelt
    _per_sid_transcript[A] KEINE Beta-Woerter und umgekehrt (Cross-Tenant-PII-Beweis).
  Test 2 (Cross-Pop): Timer-Callback poppt aus dem RICHTIGEN per-SID-Bucket (kein Cross-Pop).
  Test 3 (S4 Lock): _flush_segment hat Signatur (sid, key); kein _merge_lock in live_session.

KEIN Source-Presence-False-Green (CLAUDE.md Test-Qualitaets-Regel):
  Alle drei Tests pruefen Runtime-State-Mutation, nicht Code-Existenz.
"""

import inspect
import threading
import time
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

import services.live_session as ls


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_session_state():
    """Jeden Test mit sauberem per-SID-State starten und nachher aufraemen."""
    sid_a = 'test-sid-alpha-04'
    sid_b = 'test-sid-beta-04'
    # Sicherstellen dass kein Altbestand existiert
    ls.pop_session_state(sid_a)
    ls.pop_session_state(sid_b)
    with ls._per_sid_transcript_lock:
        ls._per_sid_transcript.pop(sid_a, None)
        ls._per_sid_transcript.pop(sid_b, None)
    with ls._per_sid_coaching_lock:
        ls._per_sid_coaching_buffer.pop(sid_a, None)
        ls._per_sid_coaching_buffer.pop(sid_b, None)

    ls.init_session_state(sid_a, user_id=901, org_id=1)
    ls.init_session_state(sid_b, user_id=902, org_id=2)

    yield sid_a, sid_b

    # Teardown
    ls.pop_session_state(sid_a)
    ls.pop_session_state(sid_b)
    with ls._per_sid_transcript_lock:
        ls._per_sid_transcript.pop(sid_a, None)
        ls._per_sid_transcript.pop(sid_b, None)
    with ls._per_sid_coaching_lock:
        ls._per_sid_coaching_buffer.pop(sid_a, None)
        ls._per_sid_coaching_buffer.pop(sid_b, None)


# ---------------------------------------------------------------------------
# Test 1: Isolation — zwei SIDs, gleicher Sprecher-Key, KEINE Vermischung
# ---------------------------------------------------------------------------

def test_merge_pending_cross_tenant_isolation(fresh_session_state):
    """Nach Flush enthaelt _per_sid_transcript[A] KEINE Beta-Woerter und umgekehrt.

    Prueft Runtime-State-Mutation nach _flush_segment-Aufruf.
    Kein Source-Presence-False-Green: wenn _flush_segment falsch poppt, landet
    der Text beim falschen SID und der Test roetet.
    """
    sid_a, sid_b = fresh_session_state
    alpha_text = 'Zebra Alpha Hallo'
    beta_text  = 'Qualle Beta Welt'
    speaker_key = '0'

    # _merge_pending pro SID vorbelegen (als ob deepgram_service geschrieben haette)
    with ls._session_state_lock:
        ls._session_state[sid_a]['_merge_pending'] = {
            speaker_key: {
                'texts':           [alpha_text],
                'line_id':         '1',
                'speaker':         0,
                'roles_confirmed': True,
                'sp_name':         'Berater',
                't_start':         time.monotonic(),
                'sid':             sid_a,
                'timer':           MagicMock(),
            }
        }
        ls._session_state[sid_b]['_merge_pending'] = {
            speaker_key: {
                'texts':           [beta_text],
                'line_id':         '2',
                'speaker':         0,
                'roles_confirmed': True,
                'sp_name':         'Berater',
                't_start':         time.monotonic(),
                'sid':             sid_b,
                'timer':           MagicMock(),
            }
        }

    # Flush ausfuehren — neue Signatur (sid, key)
    ls._flush_segment(sid_a, speaker_key)
    ls._flush_segment(sid_b, speaker_key)

    # Jetzt pruefen: A-Transcript darf KEINE Beta-Woerter enthalten und umgekehrt
    with ls._per_sid_coaching_lock:
        coaching_a = [e['text'] for e in ls._per_sid_coaching_buffer.get(sid_a, [])]
        coaching_b = [e['text'] for e in ls._per_sid_coaching_buffer.get(sid_b, [])]

    alpha_words = set(alpha_text.lower().split())
    beta_words  = set(beta_text.lower().split())

    # A darf kein reines Beta-Wort enthalten
    leaked_to_a = beta_words - alpha_words
    for word in leaked_to_a:
        for entry_text in coaching_a:
            assert word not in entry_text.lower(), (
                f"Cross-Tenant-PII-Leak! Beta-Wort '{word}' in SID-A-Coaching-Buffer: {coaching_a!r}"
            )

    # B darf kein reines Alpha-Wort enthalten
    leaked_to_b = alpha_words - beta_words
    for word in leaked_to_b:
        for entry_text in coaching_b:
            assert word not in entry_text.lower(), (
                f"Cross-Tenant-PII-Leak! Alpha-Wort '{word}' in SID-B-Coaching-Buffer: {coaching_b!r}"
            )

    # Sanity: Alpha-Text muss in A vorhanden sein
    assert any('zebra' in e.lower() for e in coaching_a), (
        f"Alpha-Text nicht in SID-A-Buffer: {coaching_a!r}"
    )
    # Sanity: Beta-Text muss in B vorhanden sein
    assert any('qualle' in e.lower() for e in coaching_b), (
        f"Beta-Text nicht in SID-B-Buffer: {coaching_b!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: Cross-Pop — Timer poppt aus dem RICHTIGEN per-SID-Bucket
# ---------------------------------------------------------------------------

def test_flush_segment_pops_correct_per_sid_bucket(fresh_session_state):
    """Timer-Callback _flush_segment(sid, key) poppt aus _session_state[sid]['_merge_pending'].

    Nach dem Flush ist der Eintrag aus dem Bucket der betroffenen SID entfernt,
    der Bucket der anderen SID bleibt unveraendert.
    """
    sid_a, sid_b = fresh_session_state
    speaker_key = '1'

    text_a = 'nur fuer SID A'
    text_b = 'nur fuer SID B'

    with ls._session_state_lock:
        ls._session_state[sid_a]['_merge_pending'] = {
            speaker_key: {
                'texts':           [text_a],
                'line_id':         '10',
                'speaker':         1,
                'roles_confirmed': True,
                'sp_name':         'Kunde',
                't_start':         time.monotonic(),
                'sid':             sid_a,
                'timer':           MagicMock(),
            }
        }
        ls._session_state[sid_b]['_merge_pending'] = {
            speaker_key: {
                'texts':           [text_b],
                'line_id':         '11',
                'speaker':         1,
                'roles_confirmed': True,
                'sp_name':         'Kunde',
                't_start':         time.monotonic(),
                'sid':             sid_b,
                'timer':           MagicMock(),
            }
        }

    # Nur SID-A-Bucket flushen
    ls._flush_segment(sid_a, speaker_key)

    # SID-A-Bucket muss leer/entfernt sein
    with ls._session_state_lock:
        bucket_a = ls._session_state.get(sid_a, {}).get('_merge_pending', {})
        bucket_b = ls._session_state.get(sid_b, {}).get('_merge_pending', {})

    assert speaker_key not in bucket_a, (
        f"_flush_segment hat Eintrag in SID-A-Bucket NICHT entfernt: {bucket_a!r}"
    )

    # SID-B-Bucket muss unveraendert geblieben sein (kein Cross-Pop)
    assert speaker_key in bucket_b, (
        f"_flush_segment hat faelschlicherweise den SID-B-Bucket geleert (Cross-Pop)! bucket_b={bucket_b!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: S4 Lock — keine Referenz auf _merge_lock; _flush_segment(sid, key)
# ---------------------------------------------------------------------------

def test_flush_segment_signature_takes_sid_and_key():
    """_flush_segment hat Runtime-Signatur (sid, key) — zwei Parameter.

    Prueft inspect.signature() -> Runtime-API-Schnittstelle (CLAUDE.md: inspect.signature OK).
    Kein Source-Presence-False-Green: wenn Signatur falsch, schlaegt inspect fehl.
    """
    sig = inspect.signature(ls._flush_segment)
    params = list(sig.parameters.keys())
    assert len(params) == 2, (
        f"_flush_segment muss genau 2 Parameter haben (sid, key), hat: {params}"
    )
    assert params[0] == 'sid', (
        f"Erster Parameter muss 'sid' sein, ist: {params[0]!r}"
    )
    assert params[1] == 'key', (
        f"Zweiter Parameter muss 'key' sein, ist: {params[1]!r}"
    )


def test_merge_lock_deleted_from_live_session():
    """_merge_lock darf nicht mehr als Modul-Attribut in live_session existieren.

    S4: GENAU EIN Lock (_session_state_lock). _merge_lock geloescht.
    Prueft hasattr() -> Runtime-State (CLAUDE.md: hasattr als Absenz-Pruefung OK
    wenn als Pflicht-Deletion-Gate verwendet, nicht als Presence-Schutz).
    """
    assert not hasattr(ls, '_merge_lock'), (
        "_merge_lock ist noch in live_session definiert — S4: muss geloescht werden. "
        "GENAU EIN Lock = _session_state_lock."
    )


def test_merge_pending_global_deleted_from_live_session():
    """Die modul-globale _merge_pending = {} darf nicht mehr existieren.

    Nach per-SID-Migration liegt _merge_pending UNTER _session_state[sid].
    Die Modul-Globale ist Dead-Code und wird in Plan 04 entfernt.
    """
    assert not hasattr(ls, '_merge_pending'), (
        "_merge_pending ist noch als Modul-Global in live_session definiert — "
        "muss nach per-SID-Migration entfernt werden."
    )
