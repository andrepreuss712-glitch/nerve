import os
import re
from flask import Blueprint, render_template, send_file, abort, g, request, session as flask_session
from routes.auth import login_required
from routes.dashboard import _parse_log_meta
from services.auth_decorators import superadmin_required
from services.audit import log_action
from services.live_session import LOG_DIR
from database.db import get_session
from database.models import User

logs_bp = Blueprint('logs', __name__)

# Phase 08.23.2.AUTH-LOGS-TENANT: Log-Dateiname traegt nur die User-ID (app_routes.py:334
# nerve_log_U{id}_{ts}.txt), KEINE Org -> Firmen-Zuordnung per DB-Lookup der User-IDs von g.org.
_UID_RE = re.compile(r'_U(\d+)_')


def _uid_from_name(fname):
    """User-ID aus dem Log-Dateinamen (Regex _U(\\d+)_, exakt -> kein Substring-Fehlmatch _U12_ vs _U123_)."""
    m = _UID_RE.search(fname)
    return int(m.group(1)) if m else None


def _org_user_ids(db, org_id):
    """Menge der User-IDs einer Firma (inkl. inaktiver — org_id bleibt). FAIL-CLOSED: bei Fehler
    leere Menge, damit der Caller NICHTS zeigt statt fail-open auf 'alle' zurueckzufallen."""
    try:
        return {u.id for u in db.query(User).filter_by(org_id=org_id).all()}
    except Exception:
        return set()


@logs_bp.route('/logs')
@login_required
def liste():
    # Normal-Pfad: owner/admin sehen NUR Logs der eigenen Firma (org-User-ID-Filter). KEIN is_superadmin-Bypass.
    rolle = g.user.rolle
    is_admin = rolle in ('owner', 'admin')
    result = []
    db = get_session()
    try:
        org_ids = _org_user_ids(db, g.org.id) if is_admin else None
        files = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt') and f != '.gitkeep'],
            reverse=True
        )
        for fname in files:
            if is_admin:
                uid = _uid_from_name(fname)
                if uid is None or uid not in org_ids:
                    continue
            else:
                if f'_U{g.user.id}_' not in fname:
                    continue
            fpath = os.path.join(LOG_DIR, fname)
            result.append(_parse_log_meta(fname, fpath))
    except Exception:
        # fail-closed: ein Fehler (z.B. org-Lookup wirft) laesst result leer — NIE 'alle' zeigen.
        result = []
    finally:
        db.close()
    return render_template('logs_page.html', logs=result)


@logs_bp.route('/logs/download/<path:filename>')
@login_required
def download(filename):
    rolle = g.user.rolle
    is_admin = rolle in ('owner', 'admin')
    if not re.match(r'^nerve_log_[A-Za-z0-9_\-]+\.txt$', filename):
        abort(403)
    if is_admin:
        db = get_session()
        try:
            org_ids = _org_user_ids(db, g.org.id)
        except Exception:
            org_ids = set()  # fail-closed -> 403 statt 500/Leak
        finally:
            db.close()
        uid = _uid_from_name(filename)
        if uid is None or uid not in org_ids:  # fail-closed: leere Menge -> 403
            abort(403)
    else:
        if f'_U{g.user.id}_' not in filename:
            abort(403)
    fpath = os.path.join(LOG_DIR, filename)
    if not os.path.isfile(fpath):
        abort(404)
    return send_file(fpath, as_attachment=True, download_name=filename)


# ── Founder-Pfad (superadmin-only, getrennt, audit-pflichtig) ────────────────────────
# Kein is_superadmin-Bypass im Normal-Pfad (das waere T-LOGS-02) — Cross-Org NUR hier,
# und NUR mit fail-closed Metadaten-Audit VOR dem Download. Sicherheits-Muster:
# admin_views.py:224-235 (register_admin_screenshot_route). NICHT learning.py:608 (owner-scoped).

@logs_bp.route('/admin/logs')
@login_required
@superadmin_required
def founder_liste():
    # Firmenuebergreifende Liste ALLER Call-Logs (nur Metadaten via _parse_log_meta). endswith('.txt')
    # -> persoenliche _summary_*.json werden NICHT mitgelistet. Download-Links zeigen auf die Founder-Route.
    result = []
    try:
        files = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt') and f != '.gitkeep'],
            reverse=True
        )
        for fname in files:
            fpath = os.path.join(LOG_DIR, fname)
            result.append(_parse_log_meta(fname, fpath))
    except Exception:
        result = []
    return render_template('logs_page.html', logs=result, download_url='/admin/logs/download/')


@logs_bp.route('/admin/logs/download/<path:filename>')
@login_required
@superadmin_required
def founder_download(filename):
    # Path-Traversal-Guard (Muster admin_views.py:231) + Format-Regex.
    if '..' in filename or filename.startswith('/'):
        abort(400)
    if not re.match(r'^nerve_log_[A-Za-z0-9_\-]+\.txt$', filename):
        abort(400)
    # Grund-Pflicht (DSGVO-Nachvollziehbarkeit).
    grund = (request.args.get('grund') or request.form.get('grund') or '').strip()
    if not grund:
        abort(400)
    fpath = os.path.join(LOG_DIR, filename)
    if not os.path.isfile(fpath):
        abort(404)
    # FAIL-CLOSED Audit VOR Download: schlaegt der Audit-Write fehl -> KEIN File (strict=True re-raist).
    # Metadaten-only (Datei + Grund), NIEMALS Transkript-Inhalt.
    db = get_session()
    try:
        log_action(
            db, g.user.id, g.org.id, 'founder_log_access',
            target_type='call_log', target_id=None,  # target_id ist Integer (models.py:399) — Dateiname gehört in details (Textfeld), nicht hierher
            details={'datei': filename, 'grund': grund}, request=request, strict=True,
        )
    except Exception:
        db.rollback()
        db.close()
        abort(500)
    db.close()
    return send_file(fpath, as_attachment=True, download_name=filename)
