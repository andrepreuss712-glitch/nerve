"""Phase 08 Plan 06 — A/B-Stats-Query + EwbRating + Scenario-Seed Tests.

9 Tests covering:
  - EwbRating Model (quality_score formula D-27, UniqueConstraint, schema)
  - _seed_ewb_scenarios (3 system scenarios, idempotent, erstellt_von=NULL)
  - A/B-Auswertungs-Query (3-stufiger JOIN, WHERE success IS NOT NULL filter)
  - Quality-Score-Gate threshold (D-27: >=80% >=80)
"""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import text

from database.models import (
    ConversationLog,
    EwbRating,
    ObjectionEvent,
    Organisation,
    TrainingScenario,
    User,
)


@pytest.fixture(autouse=True)
def _ab_stats_cleanup():
    """Phase 08.23.2.PGTEST Task 9: diese Tests COMMITTEN Org/User/ConvLog/EwbRating (public, kein crm).
    Auf der persistenten nerve_test wuerden sie leaken -> Baseline-Cleanup-Waechter rot. id-Wasserzeichen-
    Teardown ueber eine eigene kurzlebige Engine. (Die [P08-] System-Scenarios sind bereits Teil der
    app-import-Baseline -> _seed_ewb_scenarios ist idempotent, kein training_scenarios-Drift.)"""
    import os as _os
    from sqlalchemy import create_engine as _ce, text as _sql
    dsn = _os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        yield
        return
    eng = _ce(dsn)
    tables = ("ewb_ratings", "conversation_logs", "users", "tenant_orgs", "organisations")
    def _maxid(conn, tbl):
        try:
            return conn.execute(_sql(f"SELECT COALESCE(MAX(id),0) FROM public.{tbl}")).scalar()
        except Exception:
            return 0
    with eng.connect() as conn:
        base = {t: _maxid(conn, t) for t in tables}
    try:
        yield
    finally:
        try:
            with eng.begin() as conn:
                conn.execute(_sql("DELETE FROM public.ewb_ratings WHERE id > :b"),
                             {"b": base["ewb_ratings"]})
                conn.execute(_sql("DELETE FROM public.conversation_logs WHERE id > :b"),
                             {"b": base["conversation_logs"]})
                conn.execute(
                    _sql("DELETE FROM public.tenant_orgs WHERE legacy_org_id IN "
                         "(SELECT id FROM public.organisations WHERE id > :b)"),
                    {"b": base["organisations"]},
                )
                conn.execute(_sql("DELETE FROM public.users WHERE id > :b"), {"b": base["users"]})
                conn.execute(_sql("DELETE FROM public.organisations WHERE id > :b"),
                             {"b": base["organisations"]})
        except Exception as _te:
            print(f"[PGTEST-CLEANUP] ab_stats teardown failed (non-fatal): {_te!r}")
        finally:
            eng.dispose()


def _mk_user(db, email=None):
    # email UNIQUE pro Run (uuid-suffixed) -- persistente nerve_test (Task 9). TrainingScenario.
    # erstellt_von ist nullable -> _seed_ewb_scenarios braucht keinen extra User-Parent.
    if email is None:
        email = f"ab-stats-{uuid.uuid4().hex[:8]}@nerve.local"
    org = Organisation(name='T', plan='starter')
    db.add(org)
    db.flush()
    u = User(org_id=org.id, email=email, passwort_hash='x',
             market='dach', language='de')
    db.add(u)
    db.flush()
    db.commit()
    return org, u


def _mk_conv(db, user, **kw):
    conv = ConversationLog(
        user_id=user.id,
        org_id=user.org_id,
        session_mode='cold_call',
        dauer_sekunden=60,
        started_at=datetime.now(),
        **kw,
    )
    db.add(conv)
    db.flush()
    return conv


# ── EwbRating Model ──────────────────────────────────────────────────

def test_ewb_rating_quality_score_formula(db_session):
    """D-27: (klingt + 2*halluzi + trifft) / 4 * 100 → alle 3 True = 100."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    r = EwbRating(
        conversation_log_id=conv.id,
        einwand_typ_key='Zu teuer',
        klingt_wie_mensch=True,
        keine_halluzination=True,
        trifft_einwand=True,
        rater_id=u.id,
    )
    db_session.add(r)
    db_session.commit()
    # (1 + 2*1 + 1) / 4 * 100 = 100
    assert r.quality_score == 100.0


def test_ewb_rating_quality_score_partial(db_session):
    """Nur halluzi-OK: (0 + 2*1 + 0)/4*100 = 50."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    r = EwbRating(
        conversation_log_id=conv.id,
        einwand_typ_key='t',
        klingt_wie_mensch=False,
        keine_halluzination=True,
        trifft_einwand=False,
        rater_id=u.id,
    )
    db_session.add(r)
    db_session.commit()
    assert r.quality_score == 50.0


def test_ewb_rating_unique_conv_ewb(db_session):
    """Unique-Constraint (conversation_log_id, einwand_typ_key)."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    r1 = EwbRating(
        conversation_log_id=conv.id, einwand_typ_key='t',
        klingt_wie_mensch=True, keine_halluzination=True,
        trifft_einwand=True, rater_id=u.id,
    )
    db_session.add(r1)
    db_session.commit()
    r2 = EwbRating(
        conversation_log_id=conv.id, einwand_typ_key='t',
        klingt_wie_mensch=False, keine_halluzination=False,
        trifft_einwand=False, rater_id=u.id,
    )
    db_session.add(r2)
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


# ── _seed_ewb_scenarios ──────────────────────────────────────────────

def test_seed_ewb_scenarios_creates_3(db_session):
    """Seed erzeugt genau 3 [P08-*] Scenarios."""
    _, _u = _mk_user(db_session)
    from app import _seed_ewb_scenarios
    _seed_ewb_scenarios(db=db_session)
    count = db_session.query(TrainingScenario).filter(
        TrainingScenario.name.like('[P08-%')
    ).count()
    assert count == 3, f'Expected 3 scenarios, got {count}'


def test_seed_ewb_scenarios_idempotent(db_session):
    """Seed zweifach → immer noch genau 3 Scenarios (keine Dubletten)."""
    _, _u = _mk_user(db_session)
    from app import _seed_ewb_scenarios
    _seed_ewb_scenarios(db=db_session)
    _seed_ewb_scenarios(db=db_session)
    count = db_session.query(TrainingScenario).filter(
        TrainingScenario.name.like('[P08-%')
    ).count()
    assert count == 3


def test_seed_ewb_scenarios_system_marker(db_session):
    """erstellt_von IS NULL (System-Scenarios per Phase 04.9-Pattern)."""
    _, _u = _mk_user(db_session)
    from app import _seed_ewb_scenarios
    _seed_ewb_scenarios(db=db_session)
    rows = db_session.query(TrainingScenario).filter(
        TrainingScenario.name.like('[P08-%')
    ).all()
    assert len(rows) == 3
    for r in rows:
        assert r.erstellt_von is None, (
            f'Scenario {r.name} missing system marker (erstellt_von should be NULL)'
        )


# ── A/B-Auswertungs-SQL-Join (Phase 08.19.5 REQ-05: ft_objection_events removed) ──
# Tests test_ab_stats_join_success_rate + test_ab_stats_filters_null_success removed:
# ft_objection_events table dropped, FtObjectionEvent model deleted — no writer ever existed.

# ── Quality-Score-Gate (D-27) ────────────────────────────────────────

def test_quality_gate_80_percent_threshold(db_session):
    """80% der EWBs muessen Score >= 80. 10 Ratings: 8×100, 2×50."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    # 8 ratings (alle 3 Kriterien True → Score 100)
    for i in range(8):
        db_session.add(EwbRating(
            conversation_log_id=conv.id,
            einwand_typ_key=f'High_{i}',
            klingt_wie_mensch=True, keine_halluzination=True,
            trifft_einwand=True, rater_id=u.id,
        ))
    # 2 ratings (nur halluzi ok → Score 50)
    for i in range(2):
        db_session.add(EwbRating(
            conversation_log_id=conv.id,
            einwand_typ_key=f'Low_{i}',
            klingt_wie_mensch=False, keine_halluzination=True,
            trifft_einwand=False, rater_id=u.id,
        ))
    db_session.commit()
    # scoped (Delta-Review-2): nur die test-eigenen Ratings dieses conv -> persistente nerve_test /
    # geleakte Fremd-Ratings poisonen die rate nicht.
    all_ratings = db_session.query(EwbRating).filter_by(conversation_log_id=conv.id).all()
    scores = [r.quality_score for r in all_ratings]
    high_count = sum(1 for s in scores if s >= 80)
    rate = high_count / len(scores)
    assert rate == 0.8  # genau 80%
    # Gate: >= 80% → PASS
    assert rate >= 0.8
