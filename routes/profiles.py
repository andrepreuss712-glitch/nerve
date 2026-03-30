import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, g, jsonify, session as flask_session)
from database.db import get_session
from database.models import Profile, User as UserModel
from routes.auth import login_required

profiles_bp = Blueprint('profiles', __name__, url_prefix='/profiles')


def _rolle():
    return flask_session.get('rolle', 'member')


def _active_profile_id():
    return flask_session.get('active_profile_id')


@profiles_bp.route('/')
@login_required
def liste():
    db = get_session()
    try:
        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        active_id = _active_profile_id()
        return render_template('profiles_list.html', profiles=profiles, active_id=active_id)
    finally:
        db.close()


@profiles_bp.route('/new', methods=['GET', 'POST'])
@login_required
def neu():
    if _rolle() not in ('owner', 'admin'):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('profiles.liste'))
    if request.method == 'POST':
        db = get_session()
        try:
            daten_json = request.form.get('daten_json', '{}')
            try:
                json.loads(daten_json)
            except Exception:
                daten_json = '{}'
            p = Profile(
                org_id=g.org.id,
                name=request.form.get('name', '').strip(),
                branche=request.form.get('branche', '').strip(),
                daten=daten_json,
                erstellt_von=g.user.id,
            )
            db.add(p)
            db.commit()
            flash(f'Profil "{p.name}" erstellt.', 'success')
            return redirect(url_for('profiles.liste'))
        finally:
            db.close()
    return render_template('profile_editor.html', profile=None, daten={})


@profiles_bp.route('/wizard', methods=['GET'])
@login_required
def wizard_page():
    """3-step profile wizard for new users."""
    return render_template('profile_wizard.html')


@profiles_bp.route('/wizard', methods=['POST'])
@login_required
def wizard_create():
    """Guided wizard: creates profile from form data, redirects to dashboard."""
    firma = request.form.get('firma', '').strip()
    branche = request.form.get('branche', '').strip()
    rolle = request.form.get('rolle', '').strip()
    produkt = request.form.get('produkt', '').strip()
    zielkunden = request.form.get('zielkunden', '').strip()
    eigener_einwand = request.form.get('eigener_einwand', '').strip()

    # Parse einwaende from JSON list (hidden input built by JS)
    einwaende_raw = request.form.get('einwaende', '[]')
    try:
        einwaende_list = json.loads(einwaende_raw)
    except Exception:
        einwaende_list = []

    # Include free-text objection if provided
    if eigener_einwand and eigener_einwand not in einwaende_list:
        einwaende_list.append(eigener_einwand)

    daten = json.dumps({
        'firma': firma,
        'produkt': produkt,
        'zielkunden': zielkunden,
        'rolle': rolle,
        'einwaende': einwaende_list,
    }, ensure_ascii=False)

    db = get_session()
    try:
        profile = Profile(
            org_id=g.org.id,
            name=firma if firma else 'Mein Profil',
            branche=branche,
            daten=daten,
            erstellt_von=g.user.id,
        )
        db.add(profile)
        db.flush()
        # Set as active profile
        user = db.query(UserModel).get(g.user.id)
        if user:
            user.active_profile_id = profile.id
        db.commit()
        flash('Profil erstellt. Willkommen bei NERVE.', 'success')
        return redirect(url_for('dashboard.index'))
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
def bearbeiten(pid):
    if _rolle() not in ('owner', 'admin'):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('profiles.liste'))
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            flash('Profil nicht gefunden.', 'error')
            return redirect(url_for('profiles.liste'))
        if request.method == 'POST':
            daten_json = request.form.get('daten_json', p.daten or '{}')
            try:
                json.loads(daten_json)
            except Exception:
                daten_json = p.daten or '{}'
            p.name    = request.form.get('name', p.name).strip()
            p.branche = request.form.get('branche', p.branche or '').strip()
            p.daten   = daten_json
            db.commit()
            flash('Profil gespeichert.', 'success')
            return redirect(url_for('profiles.liste'))
        try:
            daten = json.loads(p.daten) if p.daten else {}
        except Exception:
            daten = {}
        return render_template('profile_editor.html', profile=p, daten=daten)
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/activate', methods=['POST'])
@login_required
def aktivieren(pid):
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        flask_session['active_profile_id'] = p.id
        import services.live_session as ls_mod
        try:
            daten = json.loads(p.daten) if p.daten else {}
        except Exception:
            daten = {}
        ls_mod.set_active_profile(p.name, daten)
        u = db.get(UserModel, g.user.id)
        if u:
            u.active_profile_id = p.id
            db.commit()
        flash(f'Profil "{p.name}" aktiviert.', 'success')
    finally:
        db.close()
    return redirect(url_for('profiles.liste'))


@profiles_bp.route('/<int:pid>/delete', methods=['POST'])
@login_required
def loeschen(pid):
    if _rolle() not in ('owner', 'admin'):
        flash('Keine Berechtigung.', 'error')
        return redirect(url_for('profiles.liste'))
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if p:
            if flask_session.get('active_profile_id') == pid:
                flask_session.pop('active_profile_id', None)
            db.delete(p)
            db.commit()
            flash('Profil gelöscht.', 'success')
    finally:
        db.close()
    return redirect(url_for('profiles.liste'))
