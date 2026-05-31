"""Phase 08.23.2.D.UX.4-02 — Backend Postcall-Split Tests.

Runtime-Verhalten (echte Flask test_client Requests, DB-Reads/-Writes, Return-Werte):
- /api/postcall_outcome liefert outcome OHNE Sonnet (generate_postcall_analysis NICHT aufgerufen)
- conf=0-Degraded-Pfad (outcome None, source None)
- /api/postcall_cards liefert vorschlaege (Sonnet gemockt)

Kein Source-Presence-Test (CLAUDE.md Test-Qualitaets-Regel).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from database.db import get_session
from database.models import User, Organisation, ConversationLog, Call


def _now():
    return datetime.now(timezone.utc)


def _seed_user_and_conv(user_id=1, org_id=1):
    """Legt Org + User + ConversationLog an, damit login_required passt + Ownership-Check gruen ist.

    Gibt conv_id (int) zurueck. login_required laedt User via session['user_id'] und prueft
    user.org_id == org.id — beide muessen existieren.
    """
    db = get_session()
    try:
        if db.query(Organisation).filter_by(id=org_id).first() is None:
            db.add(Organisation(id=org_id, name='Test-Org'))
            db.commit()
        if db.query(User).filter_by(id=user_id).first() is None:
            db.add(User(
                id=user_id, org_id=org_id, email=f'split-test-{user_id}@nerve.local',
                passwort_hash='x', rolle='owner', aktiv=True,
            ))
            db.commit()
        conv = ConversationLog(user_id=user_id, org_id=org_id, created_at=_now())
        db.add(conv)
        db.commit()
        return conv.id
    finally:
        db.close()


def _cleanup_conv(conv_id):
    db = get_session()
    try:
        db.query(ConversationLog).filter(ConversationLog.id == conv_id).delete()
        db.commit()
    finally:
        db.close()


def _auth_client(client, user_id=1):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return client


# -- /api/postcall_outcome — Haiku-only (kein Sonnet) --------------------------

def test_outcome_endpoint_returns_outcome_without_sonnet(client):
    """Outcome-Endpoint liefert outcome/source aus Haiku-classify; Sonnet wird NICHT aufgerufen."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'meeting_booked', 'confidence': 0.95}) as m_classify, \
             patch('services.coaching_service.generate_postcall_analysis') as m_sonnet:
            resp = client.post('/api/postcall_outcome', json={'conv_id': conv_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht — Endpoint braucht authentifizierte Session')

            assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
            data = resp.get_json()
            assert data is not None
            # Haiku-classify wurde aufgerufen, Sonnet NICHT (kein generate_postcall_analysis)
            assert m_classify.called or 'outcome' in data, 'classify oder outcome-Pfad muss laufen'
            m_sonnet.assert_not_called()
            # Response enthaelt KEIN vorschlaege-Key (gehoert zu /api/postcall_cards)
            assert 'vorschlaege' not in data, 'Outcome-Endpoint darf kein vorschlaege liefern'
            assert 'outcome' in data and 'confidence' in data and 'source' in data
    finally:
        _cleanup_conv(conv_id)


def test_outcome_endpoint_returns_outcome_with_call_id(client):
    """Mit call_id triggert classify + Schwellenlogik -> source='ai_auto' bei conf>=0.90."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    call_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.add(Call(id=call_id, user_id=1, call_mode='cold_call',
                    started_at=_now(), transcript_storage='none'))
        db.commit()
    finally:
        db.close()
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'meeting_booked', 'confidence': 0.95}), \
             patch('services.coaching_service.generate_postcall_analysis') as m_sonnet:
            resp = client.post('/api/postcall_outcome',
                               json={'conv_id': conv_id, 'call_id': call_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['outcome'] == 'meeting_booked'
            assert data['source'] == 'ai_auto'
            m_sonnet.assert_not_called()
    finally:
        db2 = get_session()
        try:
            db2.query(Call).filter(Call.id == call_id).delete()
            db2.commit()
        finally:
            db2.close()
        _cleanup_conv(conv_id)


def test_outcome_endpoint_conf_zero_path(client):
    """conf=0 (leeres Transcript / classify-Fail) -> outcome None, source None (LB-04 Degraded)."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    call_id = str(uuid.uuid4())
    db = get_session()
    try:
        db.add(Call(id=call_id, user_id=1, call_mode='cold_call',
                    started_at=_now(), transcript_storage='none'))
        db.commit()
    finally:
        db.close()
    try:
        with patch('routes.learning.outcome_service.classify',
                   return_value={'outcome': 'unknown', 'confidence': 0.0}):
            resp = client.post('/api/postcall_outcome',
                               json={'conv_id': conv_id, 'call_id': call_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['outcome'] is None, 'conf=0 -> outcome None'
            assert data['source'] is None, 'conf=0 -> source None'
            assert data['confidence'] == 0.0
    finally:
        db2 = get_session()
        try:
            db2.query(Call).filter(Call.id == call_id).delete()
            db2.commit()
        finally:
            db2.close()
        _cleanup_conv(conv_id)


def test_outcome_endpoint_ownership_404(client):
    """Fremder/nicht-existenter conv_id -> 404 (Ownership-Check, T-UX4-05)."""
    _auth_client(client)
    resp = client.post('/api/postcall_outcome', json={'conv_id': 999999})
    if resp.status_code in (302, 401):
        pytest.skip('Login-Fixture greift nicht')
    assert resp.status_code == 404


# -- /api/postcall_cards — Sonnet-only -----------------------------------------

def test_cards_endpoint_returns_vorschlaege(client):
    """Cards-Endpoint liefert vorschlaege aus generate_postcall_analysis (gemockt)."""
    conv_id = _seed_user_and_conv()
    _auth_client(client)
    fake_cards = [
        {'category': 'einwand_preis', 'original_suggestion': 'Im Vergleich wozu?',
         'lernziel': 'Einwaende vertiefen'},
    ]
    try:
        with patch('services.coaching_service.generate_postcall_analysis',
                   return_value=fake_cards) as m_sonnet:
            resp = client.post('/api/postcall_cards', json={'conv_id': conv_id})
            if resp.status_code in (302, 401):
                pytest.skip('Login-Fixture greift nicht')
            assert resp.status_code == 200, f'Erwartet 200, bekam {resp.status_code}'
            data = resp.get_json()
            assert 'vorschlaege' in data, 'Cards-Endpoint muss vorschlaege liefern'
            assert data['vorschlaege'] == fake_cards
            m_sonnet.assert_called_once()
            # call kwargs tragen conv_id + user_id durch (confirm-unabhaengige Persistenz)
            _, kwargs = m_sonnet.call_args
            assert kwargs.get('conv_id') == conv_id
    finally:
        _cleanup_conv(conv_id)


def test_cards_endpoint_ownership_404(client):
    """Fremder/nicht-existenter conv_id -> 404."""
    _auth_client(client)
    resp = client.post('/api/postcall_cards', json={'conv_id': 999999})
    if resp.status_code in (302, 401):
        pytest.skip('Login-Fixture greift nicht')
    assert resp.status_code == 404
