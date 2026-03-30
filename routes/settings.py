from flask import Blueprint, render_template, request, jsonify, g, session as flask_session, redirect, url_for
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
    if flask_session.get('rolle') not in ('owner', 'admin'):
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
    if flask_session.get('rolle') not in ('owner', 'admin'):
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
    if flask_session.get('rolle') not in ('owner', 'admin'):
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
    if flask_session.get('rolle') not in ('owner', 'admin'):
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
    if flask_session.get('rolle') != 'owner':
        return jsonify({'error': 'Nur der Owner kann den Account löschen'}), 403
    data = request.get_json(force=True)
    if data.get('confirmation', '') != 'LÖSCHEN':
        return jsonify({'error': 'Tippe LÖSCHEN zur Bestätigung'}), 400
    db = get_session()
    try:
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
