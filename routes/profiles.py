import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, g, jsonify, session as flask_session)
from database.db import get_session
from database.models import Profile, User as UserModel, ProfileSkript, ProfileOpener
from routes.auth import login_required
from services.audit import log_action

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
            p.consent_text = request.form.get('consent_text', p.consent_text or '').strip() or None
            db.commit()
            log_action(db, g.user.id, g.org.id, 'profile_update',
                       target_type='profile', target_id=p.id,
                       details={'name': p.name}, request=request)
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


# ── Skripte CRUD ──────────────────────────────────────────────────────────────

@profiles_bp.route('/<int:pid>/skripte')
@login_required
def skripte_liste(pid):
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        items = db.query(ProfileSkript).filter_by(profile_id=pid).order_by(ProfileSkript.sortierung, ProfileSkript.id).all()
        return jsonify([{'id': s.id, 'name': s.name, 'inhalt': s.inhalt or '', 'sortierung': s.sortierung} for s in items])
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/skripte', methods=['POST'])
@login_required
def skript_erstellen(pid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        data = request.get_json(force=True)
        max_sort = db.query(ProfileSkript).filter_by(profile_id=pid).count()
        s = ProfileSkript(profile_id=pid, name=data.get('name', '').strip() or 'Neues Skript',
                          inhalt=data.get('inhalt', ''), sortierung=max_sort)
        db.add(s)
        db.commit()
        return jsonify({'id': s.id, 'name': s.name, 'inhalt': s.inhalt or '', 'sortierung': s.sortierung}), 201
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/skripte/<int:sid>', methods=['PUT'])
@login_required
def skript_bearbeiten(pid, sid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        s = db.query(ProfileSkript).filter_by(id=sid, profile_id=pid).first()
        if not s:
            return jsonify({'error': 'not found'}), 404
        data = request.get_json(force=True)
        if 'name' in data:
            s.name = data['name'].strip()
        if 'inhalt' in data:
            s.inhalt = data['inhalt']
        if 'sortierung' in data:
            s.sortierung = data['sortierung']
        db.commit()
        return jsonify({'id': s.id, 'name': s.name, 'inhalt': s.inhalt or '', 'sortierung': s.sortierung})
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/skripte/<int:sid>', methods=['DELETE'])
@login_required
def skript_loeschen(pid, sid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        s = db.query(ProfileSkript).filter_by(id=sid, profile_id=pid).first()
        if s:
            db.delete(s)
            db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


# ── Opener CRUD ───────────────────────────────────────────────────────────────

@profiles_bp.route('/<int:pid>/opener')
@login_required
def opener_liste(pid):
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        items = db.query(ProfileOpener).filter_by(profile_id=pid).order_by(ProfileOpener.sortierung, ProfileOpener.id).all()
        return jsonify([{'id': o.id, 'name': o.name, 'inhalt': o.inhalt or '', 'sortierung': o.sortierung} for o in items])
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/opener', methods=['POST'])
@login_required
def opener_erstellen(pid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        data = request.get_json(force=True)
        max_sort = db.query(ProfileOpener).filter_by(profile_id=pid).count()
        o = ProfileOpener(profile_id=pid, name=data.get('name', '').strip() or 'Neuer Opener',
                          inhalt=data.get('inhalt', ''), sortierung=max_sort)
        db.add(o)
        db.commit()
        return jsonify({'id': o.id, 'name': o.name, 'inhalt': o.inhalt or '', 'sortierung': o.sortierung}), 201
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/opener/<int:oid>', methods=['PUT'])
@login_required
def opener_bearbeiten(pid, oid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        o = db.query(ProfileOpener).filter_by(id=oid, profile_id=pid).first()
        if not o:
            return jsonify({'error': 'not found'}), 404
        data = request.get_json(force=True)
        if 'name' in data:
            o.name = data['name'].strip()
        if 'inhalt' in data:
            o.inhalt = data['inhalt']
        if 'sortierung' in data:
            o.sortierung = data['sortierung']
        db.commit()
        return jsonify({'id': o.id, 'name': o.name, 'inhalt': o.inhalt or '', 'sortierung': o.sortierung})
    finally:
        db.close()


@profiles_bp.route('/<int:pid>/opener/<int:oid>', methods=['DELETE'])
@login_required
def opener_loeschen(pid, oid):
    if _rolle() not in ('owner', 'admin'):
        return jsonify({'error': 'Keine Berechtigung'}), 403
    db = get_session()
    try:
        p = db.query(Profile).filter_by(id=pid, org_id=g.org.id).first()
        if not p:
            return jsonify({'error': 'not found'}), 404
        o = db.query(ProfileOpener).filter_by(id=oid, profile_id=pid).first()
        if o:
            db.delete(o)
            db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()
