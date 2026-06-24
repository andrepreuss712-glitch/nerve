"""TAXO2-Plan 08 (FOLD A) — suggestion_reactions: Schema-/Insert-Roundtrip + F-08-Cascade +
Anon-Vertrag-verbatim (FOLD A-2) + DELETE-Scope (B3) + B1-interaction_id + Latenz-Beleg (Punkt 25)
+ Idempotenz.

CLAUDE.md-konform: ausschliesslich Runtime-Behavior-Tests gegen REAL-PG nerve_test
(db_session-Fixture seedet einen Test-Mandanten + setzt den app.tenant_id-GUC -> FORCE-RLS
laesst die Inserts unter `tenant_id == TEST_TENANT_UUID` durch). KEINE Source-Presence-Assertions.

SKIP nur ohne TEST_DATABASE_URL (kein sqlite-Fallback by design) — im Gate laeuft scharf.
Jeder committende Test raeumt seine Rows via cleanup_rows wieder weg (Baseline-Sauberkeit).
"""
import uuid
from datetime import datetime, timezone

import tests.conftest as conftest
from tests.conftest import cleanup_rows


def _make_call(db, tenant):
    """Erzeugt eine calls-Row unter dem Test-Tenant (tenant_id == GUC, sonst RLS WITH CHECK
    auf abhaengigen Tabellen). Gibt call_id (str) zurueck."""
    from database.models import Call
    call_id = str(uuid.uuid4())
    db.add(Call(
        id=call_id,
        user_id=1,
        tenant_id=tenant,
        call_mode='cold_call',
        started_at=datetime.now(timezone.utc),
        transcript_storage='none',
    ))
    db.commit()
    return call_id


# ── Schema-/Insert-Roundtrip + DEFERRED-Felder NULL ──────────────────────────

def test_suggestion_reactions_insert_roundtrip(db_session):
    """Minimaler Insert (slot/source/suggestion_text/payload_jsonb + tenant) -> commit ->
    query -> assert Feldwerte; DEFERRED-Felder (adoption_value/...) sind NULL."""
    from database.models import SuggestionReaction
    tenant = conftest.TEST_TENANT_UUID
    assert tenant, "Fixture muss TEST_TENANT_UUID geseedet haben"
    row_id = str(uuid.uuid4())
    try:
        db_session.add(SuggestionReaction(
            id=row_id,
            org_id=1, user_id=1, tenant_id=tenant,
            slot='B', source='auto_variante', model='haiku',
            suggestion_text='[PERSON_A] ist ein guter Ansprechpartner.',
            payload_jsonb={},
            ts_offered=datetime.now(timezone.utc),
        ))
        db_session.commit()

        got = db_session.query(SuggestionReaction).filter(
            SuggestionReaction.id == row_id).first()
        assert got is not None
        assert got.slot == 'B'
        assert got.source == 'auto_variante'
        assert got.model == 'haiku'
        assert got.suggestion_text == '[PERSON_A] ist ein guter Ansprechpartner.'
        # DEFERRED (post-Launch, NICHT in TAXO2 befuellt) -> NULL
        assert got.adoption_value is None
        assert got.following_utterance_ref is None
        assert got.reaction_class is None
    finally:
        cleanup_rows(db_session, {"public.suggestion_reactions": [row_id]}, tenant=tenant)


# ── F-08: Cascade on Call-Delete (0 Waisen) ──────────────────────────────────

def test_suggestion_reactions_cascade_on_call_delete(db_session):
    """F-08/DD-01: suggestion_reactions.call_id ist HARTER FK ON DELETE CASCADE.
    Test-Call + suggestion_reactions-Zeile -> DELETE Call -> assert 0 Waisen (DSGVO Art.17)."""
    from database.models import Call, SuggestionReaction
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    row_id = str(uuid.uuid4())
    try:
        db_session.add(SuggestionReaction(
            id=row_id, call_id=call_id, org_id=1, user_id=1, tenant_id=tenant,
            slot='B', source='manual_button', suggestion_text='[PERSON_A] Antwort.',
            payload_jsonb={},
        ))
        db_session.commit()
        assert db_session.query(SuggestionReaction).filter(
            SuggestionReaction.id == row_id).first() is not None

        # Call loeschen -> CASCADE raeumt suggestion_reactions mit.
        db_session.query(Call).filter(Call.id == call_id).delete(synchronize_session=False)
        db_session.commit()

        orphans = db_session.query(SuggestionReaction).filter(
            SuggestionReaction.call_id == call_id).count()
        assert orphans == 0, f"F-08: {orphans} Waisen nach Call-Delete (erwartet 0 — CASCADE)"
    finally:
        # Call ist (im Erfolgsfall) weg + Cascade raeumte die Row; defensiv beide IDs anbieten.
        cleanup_rows(db_session,
                     {"public.suggestion_reactions": [row_id], "public.calls": [call_id]},
                     tenant=tenant)


# ── FOLD A-2: Flush schreibt die schon-anonymisierte Storage-Version VERBATIM ──

def test_flush_writes_storage_text_verbatim(db_session):
    """FOLD A-2: ein offer mit BEREITS anonymisiertem suggestion_text ('[PERSON_A] ...') ->
    flush_suggestion_offers -> die DB-Zeile traegt EXAKT diesen Text (KEINE zweite Anon im
    Flush, kein Doppel-Token, kein cache=None-No-Op)."""
    from database.models import Call, SuggestionReaction
    from services.suggestion_capture import flush_suggestion_offers
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    storage_text = '[PERSON_A] ist der Entscheider bei [ORG_B].'
    iid = str(uuid.uuid4())
    written_ids = []
    try:
        n = flush_suggestion_offers(
            conversation_log_id=None, call_id=call_id, user_id=1, org_id=1, tenant_id=tenant,
            suggestion_offers=[{
                'slot': 'B', 'source': 'auto_variante', 'model': 'haiku',
                'suggestion_text': storage_text, 'interaction_id': iid,
                'einwand_typ': 'zu_teuer', 'ts': datetime.now(timezone.utc).isoformat(),
            }],
            db=db_session,
        )
        db_session.commit()
        assert n == 1

        got = db_session.query(SuggestionReaction).filter(
            SuggestionReaction.call_id == call_id).first()
        assert got is not None
        written_ids.append(got.id)
        # VERBATIM: exakt der schon-anonymisierte Text, unveraendert.
        assert got.suggestion_text == storage_text
        assert str(got.interaction_id) == iid     # B1: gesetzt (UUID-Spalte -> UUID-Objekt; String-Vergleich)
        assert got.adoption_value is None         # DEFERRED
    finally:
        cleanup_rows(db_session,
                     {"public.suggestion_reactions": written_ids, "public.calls": [call_id]},
                     tenant=tenant)


# ── FOLD A-2/B3: DELETE strikt auf org+call_id gescoped (NIE Fremd-Call-Zeilen) ──

def test_flush_delete_scoped_to_call(db_session):
    """FOLD A-2/B3: zwei Calls (A, B) desselben org -> flush fuer callA loescht/ersetzt NUR
    callA-Zeilen, callB-Zeilen bleiben unberuehrt. Beweist org+call_id-Scope."""
    from database.models import Call, SuggestionReaction
    from services.suggestion_capture import flush_suggestion_offers
    tenant = conftest.TEST_TENANT_UUID
    call_a = _make_call(db_session, tenant)
    call_b = _make_call(db_session, tenant)
    written = []
    try:
        # callB hat eine Zeile (darf NIE angefasst werden).
        flush_suggestion_offers(
            conversation_log_id=None, call_id=call_b, user_id=1, org_id=1, tenant_id=tenant,
            suggestion_offers=[{'slot': 'A', 'source': 'keyword', 'model': None,
                                'suggestion_text': '[PERSON_B] callB', 'interaction_id': str(uuid.uuid4())}],
            db=db_session)
        db_session.commit()

        # callA flush (1 Zeile) — darf callB NICHT beruehren.
        flush_suggestion_offers(
            conversation_log_id=None, call_id=call_a, user_id=1, org_id=1, tenant_id=tenant,
            suggestion_offers=[{'slot': 'B', 'source': 'auto_variante', 'model': 'haiku',
                                'suggestion_text': '[PERSON_A] callA', 'interaction_id': str(uuid.uuid4())}],
            db=db_session)
        db_session.commit()

        a_count = db_session.query(SuggestionReaction).filter(SuggestionReaction.call_id == call_a).count()
        b_count = db_session.query(SuggestionReaction).filter(SuggestionReaction.call_id == call_b).count()
        assert a_count == 1
        assert b_count == 1, "B3: callB-Zeile wurde vom callA-Flush angefasst (DELETE zu breit)"

        # Re-Flush callA (Doppel-/api/beenden) -> callA bleibt 1, callB unberuehrt.
        flush_suggestion_offers(
            conversation_log_id=None, call_id=call_a, user_id=1, org_id=1, tenant_id=tenant,
            suggestion_offers=[{'slot': 'B', 'source': 'auto_variante', 'model': 'haiku',
                                'suggestion_text': '[PERSON_A] callA v2', 'interaction_id': str(uuid.uuid4())}],
            db=db_session)
        db_session.commit()
        assert db_session.query(SuggestionReaction).filter(SuggestionReaction.call_id == call_a).count() == 1
        assert db_session.query(SuggestionReaction).filter(SuggestionReaction.call_id == call_b).count() == 1

        written = [r.id for r in db_session.query(SuggestionReaction).filter(
            SuggestionReaction.call_id.in_([call_a, call_b])).all()]
    finally:
        cleanup_rows(db_session,
                     {"public.suggestion_reactions": written,
                      "public.calls": [call_a, call_b]},
                     tenant=tenant)


# ── FOLD A-2/B1: record_suggestion_offer reicht interaction_id durch (nie None) ──

def test_record_suggestion_offer_always_sets_interaction_id():
    """B1: record_suggestion_offer mit gesetztem interaction_id -> der RAM-entry traegt es.
    (Der Capture-Hook setzt es via get_or_open_moment immer; hier der Durchreich-Beleg.)"""
    import services.live_session as ls
    with ls.state_lock:
        ls.state['suggestion_offers'] = []
    iid = str(uuid.uuid4())
    ls.record_suggestion_offer(slot='B', source='auto_variante', model='haiku',
                               suggestion_text='[PERSON_A] x', interaction_id=iid)
    with ls.state_lock:
        offers = list(ls.state.get('suggestion_offers', []))
    assert len(offers) == 1
    assert offers[0]['interaction_id'] == iid
    assert offers[0]['interaction_id'] is not None


# ── Punkt 25 (Latenz): record_suggestion_offer macht KEINEN DB-Write ─────────

def test_record_suggestion_offer_does_no_db_write(monkeypatch):
    """Punkt 25: monkeypatch/Spy auf get_session -> record_suggestion_offer ruft KEINE DB;
    der RAM-Puffer waechst um 1, get_session wird NICHT aufgerufen (Latenz-Beleg)."""
    import services.live_session as ls
    import database.db as dbmod

    called = {'get_session': 0}
    _real = dbmod.get_session

    def _spy(*a, **k):
        called['get_session'] += 1
        return _real(*a, **k)

    monkeypatch.setattr(dbmod, 'get_session', _spy)

    with ls.state_lock:
        ls.state['suggestion_offers'] = []
        before = len(ls.state['suggestion_offers'])
    ls.record_suggestion_offer(slot='A', source='keyword', model=None,
                               suggestion_text='[PERSON_A] y', interaction_id=str(uuid.uuid4()))
    with ls.state_lock:
        after = len(ls.state.get('suggestion_offers', []))

    assert after == before + 1, "RAM-Puffer muss um genau 1 wachsen"
    assert called['get_session'] == 0, "Punkt 25: record_suggestion_offer DARF KEINE DB anfassen"


# ── Idempotenz: doppelter Flush derselben Offers -> genau N Zeilen ────────────

def test_flush_idempotent_on_double_call(db_session):
    """Zweimaliger flush DESSELBEN call_id -> genau N Zeilen (kein Duplikat, B3-Scope)."""
    from database.models import Call, SuggestionReaction
    from services.suggestion_capture import flush_suggestion_offers
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    offers = [
        {'slot': 'B', 'source': 'auto_variante', 'model': 'haiku',
         'suggestion_text': '[PERSON_A] eins', 'interaction_id': str(uuid.uuid4())},
        {'slot': 'A', 'source': 'keyword', 'model': None,
         'suggestion_text': '[PERSON_A] zwei', 'interaction_id': str(uuid.uuid4())},
    ]
    written = []
    try:
        flush_suggestion_offers(conversation_log_id=None, call_id=call_id, user_id=1,
                                org_id=1, tenant_id=tenant, suggestion_offers=offers, db=db_session)
        db_session.commit()
        flush_suggestion_offers(conversation_log_id=None, call_id=call_id, user_id=1,
                                org_id=1, tenant_id=tenant, suggestion_offers=offers, db=db_session)
        db_session.commit()

        count = db_session.query(SuggestionReaction).filter(
            SuggestionReaction.call_id == call_id).count()
        assert count == 2, f"Idempotenz: {count} Zeilen nach Doppel-Flush (erwartet 2)"
        written = [r.id for r in db_session.query(SuggestionReaction).filter(
            SuggestionReaction.call_id == call_id).all()]
    finally:
        cleanup_rows(db_session,
                     {"public.suggestion_reactions": written, "public.calls": [call_id]},
                     tenant=tenant)


# ── Leerer Puffer -> No-Op (return 0, KEIN DELETE) ───────────────────────────

def test_flush_empty_buffer_is_noop(db_session):
    """Leerer Puffer -> return 0, KEIN DELETE: bestehende Zeilen bleiben unberuehrt."""
    from database.models import Call, SuggestionReaction
    from services.suggestion_capture import flush_suggestion_offers
    tenant = conftest.TEST_TENANT_UUID
    call_id = _make_call(db_session, tenant)
    row_id = str(uuid.uuid4())
    try:
        db_session.add(SuggestionReaction(
            id=row_id, call_id=call_id, org_id=1, user_id=1, tenant_id=tenant,
            slot='B', source='auto_variante', suggestion_text='[PERSON_A] bleibt', payload_jsonb={}))
        db_session.commit()

        n = flush_suggestion_offers(conversation_log_id=None, call_id=call_id, user_id=1,
                                    org_id=1, tenant_id=tenant, suggestion_offers=[], db=db_session)
        db_session.commit()
        assert n == 0
        # Die bestehende Zeile wurde NICHT geloescht (kein DELETE bei leerem Puffer).
        assert db_session.query(SuggestionReaction).filter(
            SuggestionReaction.id == row_id).first() is not None
    finally:
        cleanup_rows(db_session,
                     {"public.suggestion_reactions": [row_id], "public.calls": [call_id]},
                     tenant=tenant)
