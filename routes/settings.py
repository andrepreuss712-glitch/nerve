from flask import Blueprint, render_template, request, jsonify, g, session as flask_session
from routes.auth import login_required
from database.db import get_session
from database.models import User, Organisation

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def _get_usage(user, org):
    from app import PLANS
    minuten_limit = org.minuten_limit or 1000
    minuten_used  = user.minuten_used or 0
    voice_limit   = org.training_voice_limit or 50
    voice_used    = user.trainings_voice_used or 0
    plan_key      = getattr(org, 'plan', None) or getattr(org, 'plan_typ', 'starter') or 'starter'
    plan_def      = PLANS.get(plan_key, PLANS.get('starter', {}))
    return {
        'minuten_used':    minuten_used,
        'minuten_limit':   minuten_limit,
        'minuten_prozent': min(100, round(minuten_used / max(minuten_limit, 1) * 100)),
        'voice_used':      voice_used,
        'voice_limit':     voice_limit,
        'voice_prozent':   min(100, round(voice_used / max(voice_limit, 1) * 100)),
        'plan':            plan_key,
        'plan_name':       plan_def.get('name', 'Solo'),
        'plan_preis':      int(getattr(org, 'plan_preis', None) or plan_def.get('preis', 49)),
        'reset_date':      user.usage_reset_date,
    }


@settings_bp.route('/')
@login_required
def index():
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        usage = _get_usage(user, g.org)
    finally:
        db.close()
    return render_template('settings.html', usage=usage)


@settings_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json(force=True)
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        for field in ['vorname', 'nachname', 'erfahrungslevel',
                      'persoenlich', 'dashboard_stil', 'schmerzpunkt']:
            if field in data:
                setattr(user, field, data[field])
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@settings_bp.route('/billing', methods=['POST'])
@login_required
def update_billing():
    if g.user.rolle not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    data = request.get_json(force=True)
    db = get_session()
    try:
        org = db.query(Organisation).get(g.org.id)
        for field in ['billing_name', 'billing_street', 'billing_zip',
                      'billing_city', 'billing_country', 'billing_vat_id']:
            if field in data:
                setattr(org, field, data[field])
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@settings_bp.route('/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    if g.user.rolle not in ('owner', 'admin'):
        return jsonify({'error': 'Nur Owner oder Admin können kündigen'}), 403
    data = request.get_json(force=True)
    db = get_session()
    try:
        from datetime import datetime
        org = db.query(Organisation).get(g.org.id)
        org.cancelled_at = datetime.now()
        org.cancel_reason = data.get('reason', '')
        org.cancel_feedback = data.get('feedback', '')
        db.commit()
        return jsonify({
            'ok': True,
            'message': 'Dein Abo wurde gekündigt.',
            'aktiv_bis': 'Ende des aktuellen Abrechnungszeitraums',
        })
    finally:
        db.close()


@settings_bp.route('/reactivate', methods=['POST'])
@login_required
def reactivate_subscription():
    if g.user.rolle not in ('owner', 'admin'):
        return jsonify({'error': 'Nur Owner oder Admin'}), 403
    db = get_session()
    try:
        org = db.query(Organisation).get(g.org.id)
        org.cancelled_at = None
        org.cancel_reason = None
        org.cancel_feedback = None
        db.commit()
        return jsonify({'ok': True, 'message': 'Willkommen zurück!'})
    finally:
        db.close()


@settings_bp.route('/privacy', methods=['POST'])
@login_required
def update_privacy():
    if g.user.rolle not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    data = request.get_json(force=True)
    db = get_session()
    try:
        org = db.query(Organisation).get(g.org.id)
        if 'dsgvo_modus' in data:
            org.dsgvo_modus = bool(data['dsgvo_modus'])
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@settings_bp.route('/theme', methods=['POST'])
@login_required
def settings_theme():
    data = request.get_json(silent=True) or {}
    theme = data.get('theme', 'dark')
    if theme not in ('light', 'dark'):
        return jsonify({'error': 'Ungültiger Theme-Wert'}), 400
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        user.preferred_theme = theme
        db.commit()
        return jsonify({'ok': True, 'theme': theme})
    finally:
        db.close()


@settings_bp.route('/language', methods=['POST'])
@login_required
def settings_language():
    data = request.get_json(silent=True) or {}
    lang = data.get('language', 'de')
    allowed = ['de', 'en']
    if lang not in allowed:
        return jsonify({'error': 'Ungültige Sprache'}), 400
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        user.preferred_language = lang
        db.commit()
        return jsonify({'ok': True, 'language': lang})
    finally:
        db.close()


@settings_bp.route('/notifications', methods=['POST'])
@login_required
def update_notifications():
    data = request.get_json(force=True)
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        for field in ['notif_training_reminder', 'notif_streak_warning',
                      'notif_achievements', 'notif_coach', 'notif_nudges']:
            if field in data:
                setattr(user, field, bool(data[field]))
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@settings_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    if g.user.rolle != 'owner':
        return jsonify({'error': 'Nur der Owner kann den Account löschen'}), 403
    data = request.get_json(force=True)
    if data.get('confirmation', '') != 'LÖSCHEN':
        return jsonify({'error': 'Tippe LÖSCHEN zur Bestätigung'}), 400
    db = get_session()
    try:
        # ── Phase 08.23.2.D.UX.1 (DD-02) — DSGVO-Rechenschaftspflicht-Audit VOR jeder ──────
        # Zustandsaenderung. Echte audit_log-Spalten (action/target_type/target_id/details),
        # NICHT die nicht-existierenden Alt-Spalten. Nur Counts + IDs, KEINE Klartext-User-Daten. Traversiert
        # die Cascade-Kette (LANDMINE 6): calls.conversation_log_id -> conversation_logs.id ->
        # transcript_segments. So sind die Counts schon korrekt fuer die spaetere Hard-Purge-Phase.
        from services.audit import log_action
        from database.models import ConversationLog, Call, TranscriptSegment
        _conv_ids = [r[0] for r in db.query(ConversationLog.id).filter(ConversationLog.user_id == g.user.id).all()]
        _n_conv = len(_conv_ids)
        _n_calls = db.query(Call).filter(Call.user_id == g.user.id).count()
        _n_seg = (db.query(TranscriptSegment)
                  .filter(TranscriptSegment.conversation_log_id.in_(_conv_ids)).count()
                  if _conv_ids else 0)
        log_action(db, g.user.id, g.org.id, 'user_deletion_request',
                   target_type='user', target_id=g.user.id,
                   details={'transcript_segments_count': _n_seg, 'calls_count': _n_calls,
                            'conversation_logs_count': _n_conv, 'initiator': 'user_self_request'},
                   request=request)

        # Art.17 Hard-Purge der conversation_logs (-> CASCADE transcript_segments) ist BEWUSST
        # auf eine eigene 🔴-Art.17-Phase verschoben (Andre-Entscheidung 2026-05-30, Option A;
        # START-BLOCKER vor EA-Launch im Backlog). Die ON-DELETE-CASCADE (DD-01) ist live aber
        # schlafend — dieser Audit-Eintrag ist die Grundlage fuer das Restore-Re-Delete-Skript
        # der Folge-Phase (deletion-request-IDs muessen stabil/nicht-recycelt bleiben).
        db.query(User).filter_by(org_id=g.org.id).update({'aktiv': False})
        org = db.query(Organisation).get(g.org.id)
        org.aktiv = False
        db.commit()
        flask_session.clear()
        return jsonify({'ok': True, 'redirect': '/login'})
    finally:
        db.close()


@settings_bp.route('/help')
@login_required
def help_center():
    return render_template('help.html')


@settings_bp.route('/upgrade')
@login_required
def upgrade():
    db = get_session()
    try:
        user = db.query(User).get(g.user.id)
        usage = _get_usage(user, g.org)
    finally:
        db.close()
    return render_template('settings.html', active_tab='billing', usage=usage)
