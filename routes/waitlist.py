import secrets
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session as flask_session, g
from database.db import get_session
from database.models import Waitlist, Organisation, Invitation

waitlist_bp = Blueprint('waitlist', __name__, url_prefix='/waitlist')


@waitlist_bp.route('/join', methods=['POST'])
def join_waitlist():
    data = request.get_json(force=True)
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()
    firma = data.get('firma', '').strip()
    branche = data.get('branche', '').strip()
    referred_by = data.get('ref', '').strip()
    if not email:
        return jsonify({'error': 'Email ist Pflicht'}), 400
    db = get_session()
    try:
        existing = db.query(Waitlist).filter_by(email=email).first()
        if existing:
            return jsonify({
                'ok': True,
                'already': True,
                'position': existing.position,
                'referral_code': existing.referral_code,
            })
        count = db.query(Waitlist).count()
        position = count + 1
        referral_code = secrets.token_urlsafe(6)
        entry = Waitlist(
            email=email,
            name=name,
            firma=firma,
            branche=branche,
            position=position,
            referral_code=referral_code,
            referred_by=referred_by if referred_by else None,
        )
        db.add(entry)
        if referred_by:
            referrer = db.query(Waitlist).filter_by(referral_code=referred_by).first()
            if referrer and (referrer.position or 1) > 3:
                referrer.position = max(1, (referrer.position or 1) - 3)
        db.commit()
        return jsonify({
            'ok': True,
            'position': position,
            'referral_code': referral_code,
            'total_waiting': count + 1,
        })
    finally:
        db.close()


@waitlist_bp.route('/status/<code>')
def check_status(code):
    db = get_session()
    try:
        entry = db.query(Waitlist).filter_by(referral_code=code).first()
        if not entry:
            return jsonify({'error': 'Nicht gefunden'}), 404
        ahead = db.query(Waitlist).filter(
            Waitlist.position < entry.position,
            Waitlist.status == 'waiting'
        ).count()
        referral_count = db.query(Waitlist).filter_by(referred_by=entry.referral_code).count()
        return jsonify({
            'position': entry.position,
            'ahead': ahead,
            'status': entry.status,
            'referrals': referral_count,
        })
    finally:
        db.close()


@waitlist_bp.route('/stats')
def waitlist_stats():
    db = get_session()
    try:
        total = db.query(Waitlist).count()
        registered = db.query(Waitlist).filter_by(status='registered').count()
        remaining = max(0, 50 - registered)
        return jsonify({
            'total_signups': total,
            'spots_taken': registered,
            'spots_remaining': remaining,
        })
    finally:
        db.close()


@waitlist_bp.route('/invite/<int:wid>', methods=['POST'])
def invite_from_waitlist(wid):
    if flask_session.get('rolle') != 'owner':
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        entry = db.query(Waitlist).get(wid)
        if not entry:
            return jsonify({'error': 'Nicht gefunden'}), 404
        if entry.status != 'waiting':
            return jsonify({'error': f'Status ist bereits {entry.status}'}), 400
        org = Organisation(
            name=entry.firma or f"{entry.name}'s Team",
            plan='starter',
            max_users=1,
            billing_email=entry.email,
            is_early_access=True,
            early_access_discount=50,
            plan_preis=49,
        )
        db.add(org)
        db.flush()
        token = secrets.token_urlsafe(32)
        inv = Invitation(
            org_id=org.id,
            email=entry.email,
            token=token,
        )
        db.add(inv)
        entry.status = 'invited'
        entry.invited_at = datetime.now()
        db.commit()
        register_link = f"/register?token={token}"
        return jsonify({
            'ok': True,
            'email': entry.email,
            'register_link': register_link,
        })
    finally:
        db.close()


@waitlist_bp.route('/admin')
def admin_waitlist():
    if flask_session.get('rolle') != 'owner':
        return redirect(url_for('dashboard.index'))
    db = get_session()
    try:
        entries = db.query(Waitlist).order_by(Waitlist.position).all()
        stats = {
            'total': len(entries),
            'waiting': len([e for e in entries if e.status == 'waiting']),
            'invited': len([e for e in entries if e.status == 'invited']),
            'registered': len([e for e in entries if e.status == 'registered']),
        }
        return render_template('waitlist_admin.html', entries=entries, stats=stats)
    finally:
        db.close()
