import os
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_session
from database.models import User, Organisation, Session as DbSession, Invitation
from config import MAX_SESSION_HOURS, PLANS
from services.audit import log_action

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        # Attach user to g — read all needed attributes BEFORE db.close()
        db = get_session()
        try:
            user = db.get(User, session['user_id'])
            if not user or not user.aktiv:
                session.clear()
                return redirect(url_for('auth.login'))
            g.user = user
            g.org  = db.get(Organisation, user.org_id)
            # Read onboarding flag inside session so it's available after close
            onboarding_done = bool(getattr(user, 'onboarding_done', True))
        finally:
            db.close()
        # Redirect to onboarding if not done yet (skip for onboarding routes themselves)
        if not onboarding_done and not request.path.startswith('/onboarding'):
            return redirect(url_for('onboarding.wizard'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    # Redirect GET to landing page (login is now a modal)
    return redirect('/?modal=login')


def _login_user(db, user):
    """Setzt Flask-session + DbSession für ein bereits validiertes User-Objekt.
    Liest ALLE benoetigten User-Attribute VOR db.close() (CLAUDE.md Konvention).
    Caller ist verantwortlich für db.close(). Returns user_info dict.
    """
    # Read ALL needed attributes now, before session closes
    user_id              = user.id
    user_org_id          = user.org_id
    user_rolle           = user.rolle
    user_is_coach        = bool(user.is_coach) if hasattr(user, 'is_coach') else False
    user_onboarding_done = bool(user.onboarding_done) if hasattr(user, 'onboarding_done') else True

    session.permanent    = True
    session['user_id']   = user_id
    session['org_id']    = user_org_id
    session['rolle']     = user_rolle
    session['is_coach']  = user_is_coach
    tok    = secrets.token_urlsafe(32)
    ablauf = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=MAX_SESSION_HOURS)
    db_sess = DbSession(user_id=user_id, token=tok, ablauf_am=ablauf)
    db.add(db_sess)
    # ── Superadmin ENV-Seed (idempotent) ──────────────────────────────
    _sa_email = os.environ.get('SUPERADMIN_EMAIL', '').strip().lower()
    if _sa_email and user.email and user.email.lower() == _sa_email and not getattr(user, 'is_superadmin', False):
        user.is_superadmin = True
        print(f"[AUTH] Seeded superadmin: {user.email}")
    db.commit()
    return {
        'id':              user_id,
        'org_id':          user_org_id,
        'rolle':           user_rolle,
        'is_coach':        user_is_coach,
        'onboarding_done': user_onboarding_done,
    }


def _do_login(email, passwort):
    """Email/Passwort-Pfad. Returns (user_info_dict, error_msg)."""
    db = get_session()
    try:
        user = db.query(User).filter_by(email=email, aktiv=True).first()
        # Phase 04.6.1: leerer passwort_hash = OAuth-Only-User → Email-Login verboten
        # Identischer Errortext verhindert User-Enumeration (T-04.6.1-03)
        if not user or not user.passwort_hash:
            return None, 'E-Mail oder Passwort falsch.'
        if not check_password_hash(user.passwort_hash, passwort):
            return None, 'E-Mail oder Passwort falsch.'
        user_info = _login_user(db, user)
        log_action(db, user.id, getattr(user, 'org_id', None), 'login',
                   target_type='user', target_id=user.id,
                   details={'method': 'password'}, request=request)
        return user_info, None
    finally:
        db.close()


def _create_org_and_user(db, *, email, vorname, nachname, firmenname,
                         teamgroesse='1-5', passwort_hash=None,
                         oauth_provider=None, oauth_id=None, avatar_url=None):
    """Legt Organisation + User in derselben DB-Session an. Caller macht db.commit().
    Wird von api_register (Email-Pfad) und routes/oauth.py (OAuth-Pfad, Plan 02) genutzt.
    """
    from database.models import Organisation as OrgModel
    size_to_plan = {'1-5': 'starter', '6-15': 'starter', '16-30': 'business', '30+': 'business'}
    plan      = size_to_plan.get(teamgroesse, 'starter')
    max_users = PLANS[plan]['max_users']
    now       = datetime.now(timezone.utc).replace(tzinfo=None)
    trial_end = now + timedelta(days=14)
    org = OrgModel(
        name=firmenname, plan=plan, max_users=max_users,
        billing_email=email, trial_starts_at=now,
    )
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id, email=email,
        passwort_hash=passwort_hash if passwort_hash is not None else '',
        rolle='owner', is_trial=True, trial_ends_at=trial_end,
        vorname=vorname, nachname=nachname,
        oauth_provider=oauth_provider,
        oauth_id=oauth_id,
        avatar_url=avatar_url,
        onboarding_done=False,  # OAuth-User durchlaufen Wizard wie Email-User
    )
    db.add(user)
    db.flush()
    return user


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json(force=True)
    email    = data.get('email', '').strip().lower()
    passwort = data.get('passwort', '')
    if not email or not passwort:
        return jsonify({'ok': False, 'error': 'E-Mail und Passwort erforderlich.'}), 400
    user_info, err = _do_login(email, passwort)
    if err:
        return jsonify({'ok': False, 'error': err}), 401
    return jsonify({'ok': True, 'coach': user_info['is_coach']})


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """Direkt-Registrierung von der Landingpage (ohne Einladungslink)."""
    data       = request.get_json(force=True)
    vorname    = data.get('vorname', '').strip()
    nachname   = data.get('nachname', '').strip()
    email      = data.get('email', '').strip().lower()
    passwort   = data.get('passwort', '')
    firmenname = data.get('firmenname', '').strip()
    branche    = data.get('branche', '')
    teamgroesse = data.get('teamgroesse', '1-5')

    if not all([vorname, email, passwort, firmenname]):
        return jsonify({'ok': False, 'error': 'Pflichtfelder fehlen.'}), 400
    if len(passwort) < 8:
        return jsonify({'ok': False, 'error': 'Passwort muss mindestens 8 Zeichen haben.'}), 400

    db = get_session()
    try:
        if db.query(User).filter_by(email=email).first():
            return jsonify({'ok': False, 'error': 'E-Mail bereits registriert.'}), 400
        user = _create_org_and_user(
            db,
            email=email, vorname=vorname, nachname=nachname,
            firmenname=firmenname, teamgroesse=teamgroesse,
            passwort_hash=generate_password_hash(passwort),
        )
        db.commit()
        _login_user(db, user)
        session['welcome_trial'] = True
        return jsonify({'ok': True})
    finally:
        db.close()


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Nur über Einladungslink erreichbar (token pflichtmäßig)."""
    token = request.args.get('token') or request.form.get('token')
    if not token:
        flash('Registrierung nur über Einladungslink.', 'error')
        return redirect(url_for('auth.login'))
    db = get_session()
    try:
        inv = db.query(Invitation).filter_by(token=token, verwendet=False).first()
        if not inv:
            flash('Einladungslink ungültig oder bereits verwendet.', 'error')
            return redirect(url_for('auth.login'))
        org = db.get(Organisation, inv.org_id)
        if request.method == 'POST':
            email    = request.form.get('email', '').strip().lower()
            passwort = request.form.get('passwort', '')
            if email != inv.email:
                flash('E-Mail stimmt nicht mit der Einladung überein.', 'error')
                return render_template('register.html', token=token, org=org, inv=inv)
            if len(passwort) < 8:
                flash('Passwort muss mindestens 8 Zeichen haben.', 'error')
                return render_template('register.html', token=token, org=org, inv=inv)
            if db.query(User).filter_by(email=email).first():
                flash('E-Mail bereits registriert.', 'error')
                return render_template('register.html', token=token, org=org, inv=inv)
            user = User(
                org_id=inv.org_id,
                email=email,
                passwort_hash=generate_password_hash(passwort),
                rolle='member',
            )
            db.add(user)
            inv.verwendet = True
            db.commit()
            flash('Account erstellt – bitte einloggen.', 'success')
            return redirect(url_for('auth.login'))
        return render_template('register.html', token=token, org=org, inv=inv)
    finally:
        db.close()


@auth_bp.route('/logout')
def logout():
    auto = request.args.get('auto')
    # Audit vor session.clear() — danach ist g.user nicht mehr verfügbar
    if 'user_id' in session:
        try:
            _uid = session.get('user_id')
            _oid = session.get('org_id')
            _db = get_session()
            try:
                log_action(_db, _uid, _oid, 'logout',
                           target_type='user', target_id=_uid, request=request)
            finally:
                _db.close()
        except Exception:
            pass
    session.clear()
    if auto:
        flash('Du wurdest automatisch ausgeloggt.', 'info')
    return redirect(url_for('auth.login'))
