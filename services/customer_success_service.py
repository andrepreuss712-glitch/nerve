from datetime import datetime, timedelta
from sqlalchemy import func
from database.models import User, ConversationLog, CrmNote


# -- Status Badge Berechnung ------------------------------------------------

STATUS_LABELS = {
    'top':   'Top',
    'aktiv': 'Aktiv',
    'ruhig': 'Ruhig',
    'churn': 'Churn-Risiko',
}


def get_all_user_crm_data(db):
    """
    Returns list of dicts for all non-superadmin users with computed status badge.
    Caller passes db session. Per D-03: uses ConversationLog + User.letzte_aktivitaet.
    Only aggregated numeric metrics returned — no raw transcript data (DSGVO).
    """
    now = datetime.utcnow()
    cutoff_7d  = now - timedelta(days=7)
    cutoff_14d = now - timedelta(days=14)
    cutoff_30d = now - timedelta(days=30)

    # Single aggregation query for call stats per user (last 30 days)
    call_stats = (
        db.query(
            ConversationLog.user_id,
            func.count(ConversationLog.id).label('total_calls'),
            func.max(ConversationLog.started_at).label('last_call'),
            func.avg(ConversationLog.kb_end).label('avg_kb'),
            func.avg(ConversationLog.dauer_sekunden).label('avg_dauer'),
            func.sum(ConversationLog.einwaende_behandelt).label('einwaende_ok'),
            func.sum(ConversationLog.einwaende_gesamt).label('einwaende_total'),
        )
        .filter(ConversationLog.started_at >= cutoff_30d)
        .group_by(ConversationLog.user_id)
        .all()
    )
    call_map = {r.user_id: r for r in call_stats}

    # All non-superadmin users
    users = db.query(User).filter(User.is_superadmin == False).all()  # noqa: E712

    # All CRM notes (small table, fine to load all)
    notes = {n.user_id: n for n in db.query(CrmNote).all()}

    # Average calls for "Top" threshold — only among users who have calls
    avg_calls = (sum(r.total_calls for r in call_stats) / len(call_stats)
                 if call_stats else 0)

    result = []
    for u in users:
        c = call_map.get(u.id)
        note = notes.get(u.id)
        status = _compute_status(u, c, cutoff_7d, cutoff_14d, avg_calls)
        einwand_rate = 0
        if c and c.einwaende_total and c.einwaende_total > 0:
            einwand_rate = round((c.einwaende_ok or 0) / c.einwaende_total * 100)

        result.append({
            'user': u,
            'user_id': u.id,
            'email': u.email,
            'status': status,
            'status_label': STATUS_LABELS.get(status, status),
            'last_call': c.last_call if c else None,
            'total_calls_30d': c.total_calls if c else 0,
            'avg_kb': round(c.avg_kb or 0) if c else 0,
            'avg_dauer_min': round((c.avg_dauer or 0) / 60, 1) if c else 0,
            'einwand_rate': einwand_rate,
            'notiz': note.notiz if note else '',
            'notiz_updated': note.updated_at if note else None,
            'letzte_aktivitaet': u.letzte_aktivitaet,
        })

    # Sort: churn first, then ruhig, then aktiv, then top
    status_order = {'churn': 0, 'ruhig': 1, 'aktiv': 2, 'top': 3}
    result.sort(key=lambda x: status_order.get(x['status'], 99))
    return result


def _compute_status(user, call_agg, cutoff_7d, cutoff_14d, avg_calls):
    """
    Per D-01/D-02:
    - Top = above-average call frequency + KB trend positive (avg_kb > 60)
    - Aktiv = calls in last 7 days
    - Ruhig = 7 days no call
    - Churn-Risiko = 14 days no activity (no call AND no login)
    """
    last_call  = call_agg.last_call if call_agg else None
    last_login = user.letzte_aktivitaet

    # Top: above-average calls AND strong KB score
    if (call_agg
            and call_agg.total_calls > avg_calls
            and (call_agg.avg_kb or 0) > 60):
        return 'top'

    # Churn: 14 days no call AND no login
    login_stale = (not last_login) or (last_login < cutoff_14d)
    call_stale  = (not last_call)  or (last_call  < cutoff_14d)
    if login_stale and call_stale:
        return 'churn'

    # Ruhig: 7 days no call
    if (not last_call) or (last_call < cutoff_7d):
        return 'ruhig'

    return 'aktiv'


# -- Follow-Up Hinweise -----------------------------------------------------

def get_followup_hints(users_crm):
    """
    Per D-09/D-10: Returns list of actionable follow-up hints sorted by urgency.
    Includes performance-based hints (D-10), not just calendar-based (D-09).
    """
    hints = []
    for u in users_crm:
        if u['status'] == 'churn':
            days = _days_inactive(u)
            hints.append({
                'user_email': u['email'],
                'user_id': u['user_id'],
                'urgency': 'high',
                'typ': 'churn',
                'reason': f"Kein Call und kein Login seit {days}+ Tagen",
            })
        elif u['status'] == 'ruhig':
            days = _days_since_call(u)
            hints.append({
                'user_email': u['email'],
                'user_id': u['user_id'],
                'urgency': 'medium',
                'typ': 'inaktiv',
                'reason': f"Kein Call seit {days}+ Tagen",
            })

        # D-10: Performance-based hints
        if u['avg_kb'] > 0 and u['avg_kb'] < 40 and u['total_calls_30d'] >= 3:
            hints.append({
                'user_email': u['email'],
                'user_id': u['user_id'],
                'urgency': 'medium',
                'typ': 'performance',
                'reason': f"Niedriger KB-Score ({u['avg_kb']}%) bei {u['total_calls_30d']} Calls",
            })
        if u['einwand_rate'] < 30 and u['total_calls_30d'] >= 3:
            hints.append({
                'user_email': u['email'],
                'user_id': u['user_id'],
                'urgency': 'medium',
                'typ': 'performance',
                'reason': f"Einwand-Erfolgsrate nur {u['einwand_rate']}% — Training empfehlen",
            })

    # Sort: high urgency first
    hints.sort(key=lambda h: 0 if h['urgency'] == 'high' else 1)
    return hints


def _days_inactive(u):
    now = datetime.utcnow()
    dates = [d for d in [u.get('last_call'), u.get('letzte_aktivitaet')] if d]
    if not dates:
        return 30  # no data = assume long inactive
    latest = max(dates)
    return (now - latest).days


def _days_since_call(u):
    if not u.get('last_call'):
        return 30
    return (datetime.utcnow() - u['last_call']).days
