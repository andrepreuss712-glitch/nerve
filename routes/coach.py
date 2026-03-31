import json
import secrets
from datetime import datetime
from functools import wraps
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, g, jsonify)
from routes.auth import login_required
from database.db import get_session
from database.models import (User, Organisation, Profile, CoachAssignment,
                              Invitation, TrainingScenario)

coach_bp = Blueprint('coach', __name__, url_prefix='/coach')


def coach_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_coach'):
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated


def _get_coach_orgs(db, coach_id):
    """Return list of orgs this coach is assigned to."""
    assignments = (db.query(CoachAssignment)
                   .filter_by(coach_id=coach_id, aktiv=True)
                   .all())
    org_ids = [a.org_id for a in assignments]
    if not org_ids:
        return []
    return db.query(Organisation).filter(Organisation.id.in_(org_ids)).all()


# ── Dashboard ──────────────────────────────────────────────────────────────────

@coach_bp.route('/')
@login_required
@coach_required
def dashboard():
    db = get_session()
    try:
        orgs = _get_coach_orgs(db, g.user.id)
        firmen = []
        for org in orgs:
            user_count    = db.query(User).filter_by(org_id=org.id, aktiv=True).count()
            profile_count = db.query(Profile).filter_by(org_id=org.id).count()
            firmen.append({
                'org':           org,
                'user_count':    user_count,
                'profile_count': profile_count,
            })
        return render_template('coach_dashboard.html', firmen=firmen)
    finally:
        db.close()


# ── Firma-Detail ───────────────────────────────────────────────────────────────

@coach_bp.route('/firma/<int:org_id>')
@login_required
@coach_required
def firma_detail(org_id):
    db = get_session()
    try:
        # Verify coach is assigned to this org
        assignment = db.query(CoachAssignment).filter_by(
            coach_id=g.user.id, org_id=org_id, aktiv=True).first()
        if not assignment:
            return redirect(url_for('coach.dashboard'))
        org      = db.get(Organisation, org_id)
        users    = db.query(User).filter_by(org_id=org_id, aktiv=True).all()
        profiles = db.query(Profile).filter_by(org_id=org_id).order_by(Profile.name).all()
        scenarios = (db.query(TrainingScenario)
                     .filter_by(org_id=org_id)
                     .order_by(TrainingScenario.erstellt_am.desc())
                     .all())
        return render_template('coach_firma.html',
                               org=org, users=users,
                               profiles=profiles, scenarios=scenarios)
    finally:
        db.close()


# ── Firma einladen ─────────────────────────────────────────────────────────────

@coach_bp.route('/firma/einladen', methods=['POST'])
@login_required
@coach_required
def firma_einladen():
    """Create org + owner invite for a new client company."""
    data      = request.get_json(force=True)
    firmname  = (data.get('firmenname') or '').strip()
    email     = (data.get('email') or '').strip().lower()
    plan      = data.get('plan', 'starter')
    if not firmname or not email:
        return jsonify({'error': 'Firmenname und E-Mail erforderlich'}), 400

    from config import PLANS
    max_users = PLANS.get(plan, {}).get('max_users', 5)

    db = get_session()
    try:
        org = Organisation(
            name=firmname, plan=plan, max_users=max_users,
            billing_email=email, coach_id=g.user.id,
        )
        db.add(org)
        db.flush()

        token = secrets.token_urlsafe(32)
        inv   = Invitation(org_id=org.id, email=email, token=token)
        db.add(inv)

        assignment = CoachAssignment(coach_id=g.user.id, org_id=org.id)
        db.add(assignment)

        db.commit()

        invite_url = url_for('auth.register', token=token, _external=True)
        return jsonify({'ok': True, 'org_id': org.id, 'invite_url': invite_url})
    finally:
        db.close()


# ── Profil für Firma erstellen ─────────────────────────────────────────────────

@coach_bp.route('/firma/<int:org_id>/profile/neu', methods=['POST'])
@login_required
@coach_required
def firma_profile_neu(org_id):
    db = get_session()
    try:
        assignment = db.query(CoachAssignment).filter_by(
            coach_id=g.user.id, org_id=org_id, aktiv=True).first()
        if not assignment:
            return jsonify({'error': 'Kein Zugriff'}), 403
        data    = request.get_json(force=True)
        name    = (data.get('name') or '').strip()
        branche = (data.get('branche') or '').strip()
        if not name:
            return jsonify({'error': 'Name fehlt'}), 400
        profile = Profile(
            org_id=org_id,
            name=name,
            branche=branche,
            daten=json.dumps(data.get('daten', {}), ensure_ascii=False),
            erstellt_von=g.user.id,
        )
        db.add(profile)
        db.commit()
        return jsonify({'ok': True, 'id': profile.id})
    finally:
        db.close()


# ── Methodik übertragen ────────────────────────────────────────────────────────

@coach_bp.route('/methodik/uebertragen', methods=['POST'])
@login_required
@coach_required
def methodik_uebertragen():
    """Copy one of coach's profiles to a client org."""
    data       = request.get_json(force=True)
    profile_id = data.get('profile_id')
    ziel_org   = data.get('ziel_org_id')
    if not profile_id or not ziel_org:
        return jsonify({'error': 'profile_id und ziel_org_id erforderlich'}), 400

    db = get_session()
    try:
        # Coach must own source profile's org
        src = db.get(Profile, profile_id)
        if not src:
            return jsonify({'error': 'Profil nicht gefunden'}), 404

        # Coach must be assigned to target org
        assignment = db.query(CoachAssignment).filter_by(
            coach_id=g.user.id, org_id=ziel_org, aktiv=True).first()
        if not assignment:
            return jsonify({'error': 'Kein Zugriff auf Ziel-Organisation'}), 403

        new_profile = Profile(
            org_id=ziel_org,
            name=src.name,
            branche=src.branche,
            daten=src.daten,
            erstellt_von=g.user.id,
        )
        db.add(new_profile)
        db.commit()
        return jsonify({'ok': True, 'id': new_profile.id})
    finally:
        db.close()


# ── Live-Tipp senden ──────────────────────────────────────────────────────────

@coach_bp.route('/live_tipp', methods=['POST'])
@login_required
@coach_required
def live_tipp():
    """Push a live coaching tip visible to a salesperson during their call."""
    data    = request.get_json(force=True)
    org_id  = data.get('org_id')
    user_id = data.get('user_id')
    tipp    = (data.get('tipp') or '').strip()
    if not tipp:
        return jsonify({'error': 'Tipp fehlt'}), 400

    assignment = None
    if org_id:
        db = get_session()
        try:
            assignment = db.query(CoachAssignment).filter_by(
                coach_id=g.user.id, org_id=org_id, aktiv=True).first()
        finally:
            db.close()
    if org_id and not assignment:
        return jsonify({'error': 'Kein Zugriff'}), 403

    import services.live_session as ls
    with ls.coach_tipps_lock:
        ls.coach_tipps.append({
            'text':       tipp,
            'ts':         datetime.now().strftime('%H:%M:%S'),
            'coach_name': g.user.email,
            'org_id':     org_id,
            'user_id':    user_id,
        })

    return jsonify({'ok': True})


# ── API: Coach-Tipps abrufen (für Berater im Live-Call) ──────────────────────

@coach_bp.route('/api/tipps')
@login_required
def api_tipps():
    """Return and clear pending coach tips for the current user's org."""
    import services.live_session as ls
    with ls.coach_tipps_lock:
        tipps = [t for t in ls.coach_tipps
                 if t.get('org_id') == g.org.id or t.get('user_id') == g.user.id]
        ls.coach_tipps = [t for t in ls.coach_tipps
                          if t not in tipps]
    return jsonify({'ok': True, 'tipps': tipps})


# ── API: Coach-eigene Profile auflisten ───────────────────────────────────────

@coach_bp.route('/api/my_profiles')
@login_required
@coach_required
def api_my_profiles():
    db = get_session()
    try:
        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        return jsonify({'ok': True, 'profiles': [
            {'id': p.id, 'name': p.name, 'branche': p.branche or ''}
            for p in profiles
        ]})
    finally:
        db.close()


# ── Methodik-Seite ─────────────────────────────────────────────────────────────

@coach_bp.route('/methodik')
@login_required
@coach_required
def methodik():
    db = get_session()
    try:
        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        orgs     = _get_coach_orgs(db, g.user.id)
        return render_template('coach_methodik.html', profiles=profiles, orgs=orgs)
    finally:
        db.close()
