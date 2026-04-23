import json
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, g, jsonify, session as flask_session)
from database.db import get_session
from database.models import Profile, User as UserModel, ProfileSkript, ProfileOpener
from routes.auth import login_required
from services.audit import log_action

profiles_bp = Blueprint('profiles', __name__, url_prefix='/profiles')

# ── Phase 08 D-09: branche Enum-Whitelist ─────────────────────────────────────
# Gilt fuer alle Mutations (wizard_create, neu, bearbeiten) — Freitext-Werte
# werden auf 'sonstiges' gemappt, UI-Select garantiert Whitelist-Konformitaet.
VALID_BRANCHE = {
    'saas_b2b', 'maschinenbau', 'versicherung', 'finanzprodukte',
    'immobilien', 'coaching', 'beratung', 'sonstiges', ''
}


def _normalize_branche(raw: str) -> str:
    """Whitelist-check + Fallback 'sonstiges' statt 400.

    Leerer Input bleibt leer (= nicht gesetzt). Jeder Nicht-Enum-Wert wird
    konservativ auf 'sonstiges' gemappt. Kein Crash, keine Data-Loss.
    """
    v = (raw or '').strip()
    if v and v not in VALID_BRANCHE:
        return 'sonstiges'
    return v


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
                # Phase 08 D-09: gleiche Whitelist-Logik wie in bearbeiten()
                branche=_normalize_branche(request.form.get('branche', '')),
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
    # Phase 08 D-09: Wizard schreibt ebenfalls gegen Enum-Whitelist (Wizard-UI
    # kann immer noch Legacy-Freitext liefern bis Wizard-Plan nachzieht).
    branche = _normalize_branche(request.form.get('branche', ''))
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
            # Phase 08 D-09: branche gegen VALID_BRANCHE whitelisten. Fallback 'sonstiges'.
            p.branche = _normalize_branche(request.form.get('branche', p.branche or ''))
            p.daten   = daten_json
            p.consent_text = request.form.get('consent_text', p.consent_text or '').strip() or None
            db.commit()
            log_action(db, g.user.id, g.org.id, 'profile_update',
                       target_type='profile', target_id=p.id,
                       details={'name': p.name}, request=request)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'ok': True, 'name': p.name})
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
        ls_mod.set_active_profile(p.name, daten, profile_id=p.id)
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


# ══ Phase 08.5: FAQ CRUD + tabu_begriffe ══════════════════════════════════════

_FAQ_KATEGORIEN = {'Technik', 'Preis', 'Referenzen', 'DSGVO', 'Produkt', 'Sonstiges'}
_MAX_FRAGE_LEN = 2000
_MAX_ANTWORT_LEN = 2000
_MAX_TABU_ITEM_LEN = 80
_MAX_TABU_COUNT = 50


def _require_own_profile(profile_id):
    """Return (Profile, db_session) if user owns it, else (None, db_session).
    Org-isolation: profile.org_id must match g.org.id.
    """
    db = get_session()
    p = db.query(Profile).filter_by(id=profile_id).first()
    if not p:
        return None, db
    if not hasattr(g, 'org') or g.org is None or p.org_id != g.org.id:
        return None, db
    return p, db


@profiles_bp.route('/api/profile/<int:profile_id>/faqs', methods=['GET'])
@login_required
def api_faqs_list(profile_id):
    from database.models import ProfileFaq
    p, db = _require_own_profile(profile_id)
    try:
        if p is None:
            return jsonify({'error': 'not_found'}), 404
        rows = db.query(ProfileFaq).filter_by(profile_id=p.id).order_by(ProfileFaq.id.desc()).all()
        return jsonify({
            'faqs': [
                {
                    'id': r.id,
                    'frage_muster': r.frage_muster or '',
                    'antwort': r.antwort or '',
                    'kategorie': r.kategorie or 'Sonstiges',
                    'used_count': r.used_count or 0,
                }
                for r in rows
            ]
        })
    finally:
        db.close()


@profiles_bp.route('/api/profile/<int:profile_id>/faqs', methods=['POST'])
@login_required
def api_faqs_create(profile_id):
    from database.models import ProfileFaq
    data = request.get_json(silent=True) or {}
    frage = (data.get('frage_muster') or '').strip()
    antwort = (data.get('antwort') or '').strip()
    kategorie = (data.get('kategorie') or 'Sonstiges').strip()
    if not frage or not antwort:
        return jsonify({'error': 'frage_muster and antwort required'}), 400
    if len(frage) > _MAX_FRAGE_LEN or len(antwort) > _MAX_ANTWORT_LEN:
        return jsonify({'error': 'field too long'}), 400
    if kategorie not in _FAQ_KATEGORIEN:
        return jsonify({'error': 'invalid kategorie'}), 400
    p, db = _require_own_profile(profile_id)
    try:
        if p is None:
            return jsonify({'error': 'not_found'}), 404
        row = ProfileFaq(
            profile_id=p.id,
            frage_muster=frage,
            antwort=antwort,
            kategorie=kategorie,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({'id': row.id, 'used_count': row.used_count or 0}), 201
    finally:
        db.close()


@profiles_bp.route('/api/profile/faqs/<int:faq_id>', methods=['PUT'])
@login_required
def api_faqs_update(faq_id):
    from database.models import ProfileFaq
    data = request.get_json(silent=True) or {}
    db = get_session()
    try:
        row = db.query(ProfileFaq).filter_by(id=faq_id).first()
        if not row:
            return jsonify({'error': 'not_found'}), 404
        p = db.query(Profile).filter_by(id=row.profile_id).first()
        if not p or not hasattr(g, 'org') or g.org is None or p.org_id != g.org.id:
            return jsonify({'error': 'forbidden'}), 403

        if 'frage_muster' in data:
            f = (data['frage_muster'] or '').strip()
            if not f or len(f) > _MAX_FRAGE_LEN:
                return jsonify({'error': 'invalid frage_muster'}), 400
            row.frage_muster = f
        if 'antwort' in data:
            a = (data['antwort'] or '').strip()
            if not a or len(a) > _MAX_ANTWORT_LEN:
                return jsonify({'error': 'invalid antwort'}), 400
            row.antwort = a
        if 'kategorie' in data:
            k = (data['kategorie'] or '').strip()
            if k not in _FAQ_KATEGORIEN:
                return jsonify({'error': 'invalid kategorie'}), 400
            row.kategorie = k

        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@profiles_bp.route('/api/profile/faqs/<int:faq_id>', methods=['DELETE'])
@login_required
def api_faqs_delete(faq_id):
    from database.models import ProfileFaq
    db = get_session()
    try:
        row = db.query(ProfileFaq).filter_by(id=faq_id).first()
        if not row:
            return jsonify({'error': 'not_found'}), 404
        p = db.query(Profile).filter_by(id=row.profile_id).first()
        if not p or not hasattr(g, 'org') or g.org is None or p.org_id != g.org.id:
            return jsonify({'error': 'forbidden'}), 403
        db.delete(row)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@profiles_bp.route('/api/profile/<int:profile_id>/tabu', methods=['POST'])
@login_required
def api_tabu_update(profile_id):
    import json as _json
    data = request.get_json(silent=True) or {}
    begriffe = data.get('tabu_begriffe', [])
    if not isinstance(begriffe, list):
        return jsonify({'error': 'tabu_begriffe must be list'}), 400
    # Sanitize: strip, dedupe, length/count limits
    clean = []
    seen = set()
    for b in begriffe:
        if not isinstance(b, str):
            continue
        s = b.strip()
        if not s or len(s) > _MAX_TABU_ITEM_LEN:
            continue
        low = s.lower()
        if low in seen:
            continue
        seen.add(low)
        clean.append(s)
        if len(clean) >= _MAX_TABU_COUNT:
            break

    p, db = _require_own_profile(profile_id)
    try:
        if p is None:
            return jsonify({'error': 'not_found'}), 404
        try:
            pdata = _json.loads(p.daten) if p.daten else {}
        except Exception:
            pdata = {}
        if not isinstance(pdata, dict):
            pdata = {}
        basis = pdata.get('basis') if isinstance(pdata.get('basis'), dict) else {}
        basis['tabu_begriffe'] = clean
        pdata['basis'] = basis
        p.daten = _json.dumps(pdata, ensure_ascii=False)
        db.commit()
        return jsonify({'ok': True, 'count': len(clean)})
    finally:
        db.close()
