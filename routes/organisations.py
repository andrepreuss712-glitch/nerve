import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.security import generate_password_hash
from database.db import get_session
from database.models import Organisation, User, Invitation, BillingEvent
from routes.auth import login_required
from config import PLANS

orgs_bp = Blueprint('orgs', __name__, url_prefix='/org')


def _require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('rolle') not in ('owner', 'admin'):
            return jsonify({'error': 'Keine Berechtigung'}), 403
        return f(*args, **kwargs)
    return decorated


@orgs_bp.route('/team')
@login_required
@_require_admin
def team():
    db = get_session()
    try:
        users = db.query(User).filter_by(org_id=g.org.id).all()
        invitations = db.query(Invitation).filter_by(org_id=g.org.id, verwendet=False).all()
        plan_info = PLANS.get(g.org.plan, {})
        return render_template('team.html', users=users, invitations=invitations,
                               org=g.org, plan_info=plan_info)
    finally:
        db.close()


@orgs_bp.route('/invite', methods=['POST'])
@login_required
@_require_admin
def invite():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash('E-Mail fehlt.', 'error')
        return redirect(url_for('orgs.team'))
    db = get_session()
    try:
        plan_info = PLANS.get(g.org.plan, {})
        max_users = plan_info.get('max_users')
        aktive_user = db.query(User).filter_by(org_id=g.org.id, aktiv=True).count()
        if max_users is not None and aktive_user >= max_users:
            flash(f'Plan-Limit erreicht ({aktive_user}/{max_users} User). Upgrade nötig.', 'error')
            return redirect(url_for('orgs.team'))
        if db.query(User).filter_by(email=email).first():
            flash('Diese E-Mail ist bereits registriert.', 'error')
            return redirect(url_for('orgs.team'))
        # Bestehende offene Einladung löschen
        old = db.query(Invitation).filter_by(org_id=g.org.id, email=email, verwendet=False).first()
        if old:
            db.delete(old)
        tok = secrets.token_urlsafe(32)
        inv = Invitation(org_id=g.org.id, email=email, token=tok)
        db.add(inv)
        db.commit()
        link = url_for('auth.register', token=tok, _external=True)
        flash(f'Einladungslink für {email}: {link}', 'success')
    finally:
        db.close()
    return redirect(url_for('orgs.team'))


@orgs_bp.route('/invite/<int:inv_id>/revoke', methods=['POST'])
@login_required
@_require_admin
def revoke_invite(inv_id):
    db = get_session()
    try:
        inv = db.query(Invitation).filter_by(id=inv_id, org_id=g.org.id).first()
        if inv:
            db.delete(inv)
            db.commit()
    finally:
        db.close()
    return redirect(url_for('orgs.team'))


@orgs_bp.route('/user/<int:user_id>/deactivate', methods=['POST'])
@login_required
@_require_admin
def deactivate_user(user_id):
    if user_id == session['user_id']:
        flash('Du kannst deinen eigenen Account nicht deaktivieren.', 'error')
        return redirect(url_for('orgs.team'))
    db = get_session()
    try:
        user = db.query(User).filter_by(id=user_id, org_id=g.org.id).first()
        if user and user.rolle != 'owner':
            user.aktiv = False
            db.commit()
    finally:
        db.close()
    return redirect(url_for('orgs.team'))


@orgs_bp.route('/user/<int:user_id>/reactivate', methods=['POST'])
@login_required
@_require_admin
def reactivate_user(user_id):
    db = get_session()
    try:
        user = db.query(User).filter_by(id=user_id, org_id=g.org.id).first()
        if user:
            user.aktiv = True
            db.commit()
    finally:
        db.close()
    return redirect(url_for('orgs.team'))


@orgs_bp.route('/settings/dsgvo', methods=['POST'])
@login_required
@_require_admin
def settings_dsgvo():
    db = get_session()
    try:
        org = db.query(Organisation).filter_by(id=g.org.id).first()
        if org:
            data = request.get_json(force=True)
            org.dsgvo_modus = bool(data.get('dsgvo_modus', True))
            db.commit()
            return jsonify({'ok': True, 'dsgvo_modus': org.dsgvo_modus})
        return jsonify({'error': 'not found'}), 404
    finally:
        db.close()
