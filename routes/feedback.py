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


@feedback_bp.route('/api/feedback/quick', methods=['POST'])
def api_feedback_quick():
    """Quick-Rating nach Training/Live-Session."""
    if not getattr(g, 'user', None):
        return jsonify({'error': 'auth'}), 401
    data = request.get_json(silent=True) or {}
    rating = data.get('rating')
    text = (data.get('text') or '').strip()
    kontext = (data.get('kontext') or 'unknown')[:50]  # 'training' | 'live'
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({'error': 'rating'}), 400
    db = get_session()
    try:
        fb = create_feedback(
            db,
            g.user.id,
            getattr(g.user, 'org_id', None),
            typ='praise' if rating >= 4 else 'idea',
            text=text or f'quick rating {rating}',
            rating=rating,
            kategorie=f'quick:{kontext}',
        )
        return jsonify({'ok': True, 'id': fb.id}), 201
    finally:
        db.close()
