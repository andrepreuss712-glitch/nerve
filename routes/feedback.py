from flask import Blueprint, request, jsonify, g
from database.db import get_session
from services.feedback_service import create_feedback, save_screenshot

feedback_bp = Blueprint('feedback', __name__)

ALLOWED_TYPES = {'bug', 'idea', 'praise', 'question'}


@feedback_bp.route('/api/feedback', methods=['POST'])
def api_feedback():
    """Feedback-Ticket mit optionalem Screenshot."""
    if not getattr(g, 'user', None):
        return jsonify({'error': 'auth'}), 401
    typ = (request.form.get('typ') or '').strip().lower()
    text = (request.form.get('text') or '').strip()
    context_url = (request.form.get('context_url') or '')[:500]
    if typ not in ALLOWED_TYPES or len(text) < 3:
        return jsonify({'error': 'invalid'}), 400
    db = get_session()
    try:
        screenshot_rel = None
        file = request.files.get('screenshot')
        if file:
            try:
                screenshot_rel = save_screenshot(file)
            except ValueError as e:
                return jsonify({'error': f'screenshot: {e}'}), 400
        fb = create_feedback(
            db,
            g.user.id,
            getattr(g.user, 'org_id', None),
            typ,
            text,
            screenshot_rel,
            context_url,
        )
        return jsonify({'ok': True, 'id': fb.id}), 201
    finally:
        db.close()


