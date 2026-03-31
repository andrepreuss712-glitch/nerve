import json
from flask import Blueprint, render_template, request, jsonify, session as flask_session, g
from database.db import get_session
from database.models import Changelog, User

changelog_bp = Blueprint('changelog', __name__, url_prefix='/changelog')


@changelog_bp.route('/')
def public_changelog():
    db = get_session()
    try:
        entries = (db.query(Changelog)
                   .filter_by(veroeffentlicht=True)
                   .order_by(Changelog.created_at.desc())
                   .limit(20).all())
        for e in entries:
            try:
                e.bugs_parsed = json.loads(e.bekannte_bugs) if e.bekannte_bugs else []
            except Exception:
                e.bugs_parsed = []
        return render_template('changelog.html', entries=entries)
    finally:
        db.close()


@changelog_bp.route('/latest')
def latest_for_popup():
    if 'user_id' not in flask_session:
        return jsonify({'has_new': False, 'entries': []})
    db = get_session()
    try:
        user = db.query(User).get(flask_session['user_id'])
        if not user:
            return jsonify({'has_new': False, 'entries': []})
        last_seen = user.last_seen_changelog or '0.0.0'
        entries = (db.query(Changelog)
                   .filter(Changelog.veroeffentlicht == True,
                           Changelog.version > last_seen)
                   .order_by(Changelog.created_at.desc())
                   .limit(3).all())
        result = []
        for e in entries:
            try:
                bugs = json.loads(e.bekannte_bugs) if e.bekannte_bugs else []
            except Exception:
                bugs = []
            result.append({
                'version': e.version,
                'titel': e.titel,
                'inhalt': e.inhalt,
                'typ': e.typ,
                'bugs': bugs,
                'datum': e.created_at.strftime('%d.%m.%Y') if e.created_at else '',
            })
        return jsonify({
            'has_new': len(result) > 0,
            'entries': result,
            'latest_version': result[0]['version'] if result else last_seen,
        })
    finally:
        db.close()


@changelog_bp.route('/seen', methods=['POST'])
def mark_seen():
    if 'user_id' not in flask_session:
        return jsonify({'ok': True})
    data = request.get_json(force=True)
    version = data.get('version', '')
    db = get_session()
    try:
        user = db.query(User).get(flask_session['user_id'])
        if user:
            user.last_seen_changelog = version
            db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@changelog_bp.route('/admin', methods=['POST'])
def add_entry():
    if flask_session.get('rolle') != 'owner':
        return jsonify({'error': 'Keine Berechtigung'}), 403
    data = request.get_json(force=True)
    db = get_session()
    try:
        entry = Changelog(
            version=data.get('version', '').strip(),
            titel=data.get('titel', '').strip(),
            inhalt=data.get('inhalt', '').strip(),
            typ=data.get('typ', 'update'),
            bekannte_bugs=json.dumps(data.get('bugs', []), ensure_ascii=False) if data.get('bugs') else None,
        )
        db.add(entry)
        db.commit()
        return jsonify({'ok': True, 'id': entry.id})
    finally:
        db.close()
