from flask import g, redirect, url_for, abort, request, send_from_directory, flash
from flask_admin import BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from sqlalchemy import func
from database.db import db_session, get_session
from database.models import (
    User, Organisation, Feedback, AuditLog, ConversationLog,
    ObjectionEvent, PlanningFeedbackLink,
)
from services.email_service import send_feedback_in_planning
from services.feedback_service import UPLOAD_DIR
from services.audit import log_action
import os


def _is_superadmin():
    return getattr(g, 'user', None) is not None and getattr(g.user, 'is_superadmin', False)


class SecureModelView(ModelView):
    page_size = 50

    def is_accessible(self):
        return _is_superadmin()

    def inaccessible_callback(self, name, **kwargs):
        if getattr(g, 'user', None) is None:
            return redirect(url_for('auth.login'))
        abort(403)


class UserAdmin(SecureModelView):
    column_list = ('id', 'email', 'rolle', 'is_superadmin', 'org_id', 'erstellt_am')
    column_searchable_list = ('email',)
    column_filters = ('rolle', 'is_superadmin', 'org_id')


class OrgAdmin(SecureModelView):
    column_list = ('id', 'name', 'plan', 'subscription_status')
    column_searchable_list = ('name',)
    column_filters = ('plan', 'subscription_status')


class FeedbackAdmin(SecureModelView):
    column_list = ('id', 'user_id', 'typ', 'status', 'rating', 'kategorie', 'created_at', 'notification_sent')
    column_filters = ('typ', 'status', 'kategorie', 'notification_sent')
    column_searchable_list = ('text', 'kategorie')
    form_columns = ('typ', 'status', 'kategorie', 'text')

    @action('mark_in_planning', 'In Planung übernehmen',
            'Wirklich diese Feedbacks in Planung übernehmen und User benachrichtigen?')
    def action_mark_in_planning(self, ids):
        db = get_session()
        try:
            sent = 0
            for fid in ids:
                fb = db.query(Feedback).get(int(fid))
                if not fb:
                    continue
                fb.status = 'in_planning'
                db.add(PlanningFeedbackLink(
                    feedback_id=fb.id,
                    planning_title=(fb.text or '')[:200],
                ))
                if not fb.notification_sent:
                    u = db.query(User).get(fb.user_id)
                    if u and u.email:
                        ok = send_feedback_in_planning(
                            u.email, fb.text or '', getattr(u, 'vorname', '') or ''
                        )
                        if ok:
                            fb.notification_sent = True
                            sent += 1
                log_action(db, getattr(g.user, 'id', None), getattr(g.user, 'org_id', None),
                           'feedback_in_planning', target_type='feedback', target_id=fb.id,
                           request=request)
            db.commit()
            flash(f'{len(ids)} Feedback(s) in Planung. {sent} Email(s) gesendet.', 'success')
        finally:
            db.close()


class AuditLogAdmin(SecureModelView):
    can_create = False
    can_edit   = False
    can_delete = False
    column_list = ('id', 'created_at', 'action', 'user_id', 'target_type', 'target_id', 'ip_address')
    column_filters = ('action', 'user_id', 'target_type')
    column_default_sort = ('id', True)


class ConvLogAdmin(SecureModelView):
    can_edit   = False
    can_delete = False
    column_list = ('id', 'user_id', 'session_mode', 'dauer_sekunden', 'einwaende_total',
                   'einwaende_ok', 'started_at', 'ended_at')
    column_filters = ('session_mode', 'user_id')
    column_default_sort = ('id', True)


class KpiDashboardView(BaseView):
    def is_accessible(self):
        return _is_superadmin()

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

    @expose('/')
    def index(self):
        db = get_session()
        try:
            from datetime import datetime, timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            stats = {
                'users_total':       db.query(func.count(User.id)).scalar() or 0,
                'orgs_total':        db.query(func.count(Organisation.id)).scalar() or 0,
                'sessions_week':     db.query(func.count(ConversationLog.id)).filter(
                                         ConversationLog.started_at >= week_ago).scalar() or 0,
                'feedback_new':      db.query(func.count(Feedback.id)).filter(
                                         Feedback.status == 'new').scalar() or 0,
                'feedback_planning': db.query(func.count(Feedback.id)).filter(
                                         Feedback.status == 'in_planning').scalar() or 0,
                'audit_week':        db.query(func.count(AuditLog.id)).filter(
                                         AuditLog.created_at >= week_ago).scalar() or 0,
            }
            return self.render('admin/kpi_dashboard.html', stats=stats)
        finally:
            db.close()


class PlanningListView(BaseView):
    def is_accessible(self):
        return _is_superadmin()

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login'))

    @expose('/', methods=['GET', 'POST'])
    def index(self):
        db = get_session()
        try:
            if request.method == 'POST':
                link_id    = int(request.form.get('id') or 0)
                new_status = (request.form.get('status') or '').strip()
                if link_id and new_status in ('backlog', 'active', 'done'):
                    link = db.query(PlanningFeedbackLink).get(link_id)
                    if link:
                        link.planning_status = new_status
                        db.commit()
            links = (db.query(PlanningFeedbackLink)
                       .order_by(PlanningFeedbackLink.id.desc())
                       .limit(200).all())
            return self.render('admin/planning_list.html', links=links)
        finally:
            db.close()


def register_admin_screenshot_route(app):
    from services.auth_decorators import superadmin_required

    @app.route('/admin/feedback/screenshot/<path:rel>')
    @superadmin_required
    def admin_feedback_screenshot(rel):
        # rel kommt als 'feedback/<uuid>.<ext>' aus DB
        if '..' in rel or rel.startswith('/'):
            abort(400)
        # UPLOAD_DIR endet auf 'feedback' — strip prefix
        name = rel.split('feedback/', 1)[-1]
        return send_from_directory(UPLOAD_DIR, name)
