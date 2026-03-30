import os
import re
from flask import Blueprint, render_template, send_file, abort, g, session as flask_session
from routes.auth import login_required
from routes.dashboard import get_recent_logs, _parse_log_meta
from services.live_session import LOG_DIR

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/logs')
@login_required
def liste():
    rolle = flask_session.get('rolle', 'member')
    is_admin = rolle in ('owner', 'admin')
    result = []
    try:
        files = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt') and f != '.gitkeep'],
            reverse=True
        )
        for fname in files:
            if not is_admin:
                if f'_U{g.user.id}_' not in fname:
                    continue
            fpath = os.path.join(LOG_DIR, fname)
            result.append(_parse_log_meta(fname, fpath))
    except Exception:
        pass
    return render_template('logs_page.html', logs=result)


@logs_bp.route('/logs/download/<path:filename>')
@login_required
def download(filename):
    rolle = flask_session.get('rolle', 'member')
    is_admin = rolle in ('owner', 'admin')
    if not re.match(r'^nerve_log_[A-Za-z0-9_\-]+\.txt$', filename):
        abort(403)
    if not is_admin:
        if f'_U{g.user.id}_' not in filename:
            abort(403)
    fpath = os.path.join(LOG_DIR, filename)
    if not os.path.isfile(fpath):
        abort(404)
    return send_file(fpath, as_attachment=True, download_name=filename)
