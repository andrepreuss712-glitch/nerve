"""Phase 08 Plan 06 — A/B-Stats-Query + EwbRating + Scenario-Seed Tests.

9 Tests covering:
  - EwbRating Model (quality_score formula D-27, UniqueConstraint, schema)
  - _seed_ewb_scenarios (3 system scenarios, idempotent, erstellt_von=NULL)
  - A/B-Auswertungs-Query (3-stufiger JOIN, WHERE success IS NOT NULL filter)
  - Quality-Score-Gate threshold (D-27: >=80% >=80)
"""
from datetime import datetime

import pytest
from sqlalchemy import text

from database.models import (
    ConversationLog,
    EwbRating,
    FtCallSession,
    FtObjectionEvent,
    ObjectionEvent,
    Organisation,
    TrainingScenario,
    User,
)


def _mk_user(db, email='a@a.de'):
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


# ── A/B-Auswertungs-SQL-Join (Focus Area 3, D-22) ────────────────────

def test_ab_stats_join_success_rate(db_session):
    """3-stufiger Join liefert korrekte (prompt_version, n, success_rate)."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    fcs = FtCallSession(
        user_id=u.id, conversation_log_id=conv.id,
        mode='cold_call', market='dach', language='de',
    )
    db_session.add(fcs)
    db_session.flush()

    # 2 ObjectionEvents: 1 success=True, 1 success=False
    oe1 = ObjectionEvent(
        user_id=u.id, org_id=u.org_id,
        conversation_log_id=conv.id,
        einwand_typ='Zu teuer', success=True,
    )
    oe2 = ObjectionEvent(
        user_id=u.id, org_id=u.org_id,
        conversation_log_id=conv.id,
        einwand_typ='Bedarf unklar', success=False,
    )
    db_session.add_all([oe1, oe2])

    # 2 FtObjectionEvents mit unterschiedlichen prompt_version
    ftoe1 = FtObjectionEvent(
        ft_session_id=fcs.id, user_id=u.id,
        market='dach', language='de',
        timestamp_ms=1000, objection_type='Zu teuer',
        model_used='haiku-4-5', prompt_version='v1-legacy',
    )
    ftoe2 = FtObjectionEvent(
        ft_session_id=fcs.id, user_id=u.id,
        market='dach', language='de',
        timestamp_ms=2000, objection_type='Bedarf unklar',
        model_used='haiku-4-5', prompt_version='v2-modular',
    )
    db_session.add_all([ftoe1, ftoe2])
    db_session.commit()

    # A/B-Query ausfuehren
    rows = db_session.execute(text("""
        SELECT ftoe.prompt_version AS v, COUNT(*) AS n,
               AVG(CASE WHEN oe.success = 1 THEN 1.0 ELSE 0.0 END) AS rate
        FROM ft_objection_events ftoe
        JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
        JOIN objection_events oe
          ON oe.conversation_log_id = fcs.conversation_log_id
         AND oe.einwand_typ = ftoe.objection_type
        WHERE oe.success IS NOT NULL
        GROUP BY ftoe.prompt_version
        ORDER BY v
    """)).fetchall()
    results = {r[0]: (r[1], float(r[2])) for r in rows}
    assert 'v1-legacy' in results
    assert 'v2-modular' in results
    assert results['v1-legacy'] == (1, 1.0), f'v1: {results["v1-legacy"]}'
    assert results['v2-modular'] == (1, 0.0), f'v2: {results["v2-modular"]}'


def test_ab_stats_filters_null_success(db_session):
    """D-05: WHERE success IS NOT NULL — NULL-Events werden ausgeschlossen."""
    _, u = _mk_user(db_session)
    conv = _mk_conv(db_session, u)
    fcs = FtCallSession(
        user_id=u.id, conversation_log_id=conv.id,
        mode='cold_call', market='dach', language='de',
    )
    db_session.add(fcs)
    db_session.flush()
    oe_null = ObjectionEvent(
        user_id=u.id, org_id=u.org_id,
        conversation_log_id=conv.id,
        einwand_typ='Zu teuer', success=None,
    )
    ftoe = FtObjectionEvent(
        ft_session_id=fcs.id, user_id=u.id,
        market='dach', language='de',
        timestamp_ms=1000, objection_type='Zu teuer',
        model_used='haiku-4-5', prompt_version='v1-legacy',
    )
    db_session.add_all([oe_null, ftoe])
    db_session.commit()
    rows = db_session.execute(text("""
        SELECT COUNT(*) FROM ft_objection_events ftoe
        JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
        JOIN objection_events oe
          ON oe.conversation_log_id = fcs.conversation_log_id
         AND oe.einwand_typ = ftoe.objection_type
        WHERE oe.success IS NOT NULL
    """)).scalar()
    assert rows == 0  # alle success=NULL → wegfiltriert


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
    all_ratings = db_session.query(EwbRating).all()
    scores = [r.quality_score for r in all_ratings]
    high_count = sum(1 for s in scores if s >= 80)
    rate = high_count / len(scores)
    assert rate == 0.8  # genau 80%
    # Gate: >= 80% → PASS
    assert rate >= 0.8
