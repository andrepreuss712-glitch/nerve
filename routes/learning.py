"""Learning Card + Coach Report API routes."""
from flask import Blueprint, request, jsonify, g
from routes.auth import login_required

learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/api/postcall_analysis', methods=['POST'])
@login_required
def api_postcall_analysis():
    """D-01: Async endpoint called from postcall overlay to generate Lernkarten suggestions."""
    data = request.get_json(force=True)
    conv_id = data.get('conv_id')
    if not conv_id:
        return jsonify({'error': 'conv_id required'}), 400

    # T-04.11-02: Verify conv_id belongs to requesting user
    from database.db import get_session
    from database.models import ConversationLog
    db_check = get_session()
    try:
        conv = db_check.query(ConversationLog).filter_by(
            id=conv_id, user_id=g.user.id
        ).first()
        if not conv:
            return jsonify({'error': 'not found'}), 404
    finally:
        db_check.close()

    from services.coaching_service import generate_postcall_analysis
    suggestions = generate_postcall_analysis(
        conv_id=conv_id,
        user_id=g.user.id,
        einwaende=data.get('einwaende', []),
        painpoints=data.get('painpoints', []),
        kb_start=data.get('kb_start', 30),
        kb_end=data.get('kb_end', 30),
        redeanteil_berater=data.get('redeanteil_berater', 50),
        redeanteil_kunde=data.get('redeanteil_kunde', 50),
        dauer_sek=data.get('dauer_sek', 0),
        skript_abdeckung=data.get('skript_abdeckung', 0),
        ga_details=data.get('ga_details', []),
        kaufsignale=data.get('kaufsignale', []),
    )
    return jsonify({'vorschlaege': suggestions})


@learning_bp.route('/api/learning_cards', methods=['GET'])
@login_required
def api_get_cards():
    """Get user's learning cards, optionally filtered by status."""
    status = request.args.get('status', 'aktiv')
    from database.db import get_session
    from database.models import LearningCard
    db = get_session()
    try:
        q = db.query(LearningCard).filter_by(user_id=g.user.id)
        if status != 'all':
            q = q.filter_by(status=status)
        cards = q.order_by(LearningCard.created_at.desc()).all()
        return jsonify({'cards': [
            {'id': c.id, 'category': c.category,
             'original_suggestion': c.original_suggestion,
             'final_text': c.final_text, 'lernziel': c.lernziel,
             'source': c.source, 'status': c.status,
             'applied_count': c.applied_count,
             'created_at': c.created_at.isoformat() if c.created_at else None,
             'learned_at': c.learned_at.isoformat() if c.learned_at else None}
            for c in cards
        ]})
    finally:
        db.close()


@learning_bp.route('/api/learning_cards/<int:card_id>/save', methods=['POST'])
@login_required
def api_save_card(card_id):
    """D-06: Accept a suggestion as active card. Enforces max 5 active (D-07)."""
    from database.db import get_session
    from database.models import LearningCard
    db = get_session()
    try:
        card = db.query(LearningCard).filter_by(id=card_id, user_id=g.user.id).first()
        if not card:
            return jsonify({'error': 'not found'}), 404
        # D-07: max 5 active
        active_count = db.query(LearningCard).filter_by(
            user_id=g.user.id, status='aktiv').count()
        if active_count >= 5:
            return jsonify({'error': 'max_reached', 'message': 'Max 5 aktive Lernkarten. Markiere eine als gelernt oder archiviert.'}), 409
        data = request.get_json(silent=True) or {}
        if data.get('final_text'):
            card.final_text = data['final_text']
        card.status = 'aktiv'
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@learning_bp.route('/api/learning_cards/<int:card_id>/regenerate', methods=['POST'])
@login_required
def api_regenerate_card(card_id):
    """D-06: Return pre-generated alternative (max 3x). Alternatives stored in coaching_service."""
    from database.db import get_session
    from database.models import LearningCard
    db = get_session()
    try:
        card = db.query(LearningCard).filter_by(id=card_id, user_id=g.user.id).first()
        if not card:
            return jsonify({'error': 'not found'}), 404
        if card.regenerate_count >= 3:
            return jsonify({'error': 'max_regenerations', 'message': 'Max 3x neuer Vorschlag erreicht.'}), 409
        card.regenerate_count += 1
        db.commit()
        return jsonify({'ok': True, 'regenerate_count': card.regenerate_count})
    finally:
        db.close()


@learning_bp.route('/api/learning_cards/<int:card_id>/status', methods=['POST'])
@login_required
def api_update_status(card_id):
    """D-07: Update card status (aktiv/gelernt/archiviert)."""
    from database.db import get_session
    from database.models import LearningCard
    data = request.get_json(force=True)
    new_status = data.get('status')
    if new_status not in ('aktiv', 'gelernt', 'archiviert'):
        return jsonify({'error': 'invalid status'}), 400
    db = get_session()
    try:
        card = db.query(LearningCard).filter_by(id=card_id, user_id=g.user.id).first()
        if not card:
            return jsonify({'error': 'not found'}), 404
        if new_status == 'aktiv':
            active_count = db.query(LearningCard).filter_by(
                user_id=g.user.id, status='aktiv').count()
            if active_count >= 5:
                return jsonify({'error': 'max_reached'}), 409
        card.status = new_status
        if new_status == 'gelernt':
            from datetime import datetime, timezone
            card.learned_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@learning_bp.route('/api/learning_cards/<int:card_id>/applied', methods=['POST'])
@login_required
def api_mark_applied(card_id):
    """D-11: Post-Call 'Hast du deine Lernkarte angewendet?' -- increment applied_count."""
    from database.db import get_session
    from database.models import LearningCard
    data = request.get_json(silent=True) or {}
    applied = data.get('applied')  # 'ja' | 'nein' | 'anders'
    db = get_session()
    try:
        card = db.query(LearningCard).filter_by(id=card_id, user_id=g.user.id).first()
        if not card:
            return jsonify({'error': 'not found'}), 404
        if applied == 'ja':
            card.applied_count += 1
        elif applied == 'anders':
            card.applied_count += 1
            if data.get('new_text'):
                card.final_text = data['new_text']
        db.commit()
        return jsonify({'ok': True, 'applied_count': card.applied_count})
    finally:
        db.close()


@learning_bp.route('/api/learning_cards/<int:card_id>/user_text', methods=['POST'])
@login_required
def api_user_text(card_id):
    """D-06: 'Selbst eingeben' -- validate user text covers lernziel."""
    from database.db import get_session
    from database.models import LearningCard
    data = request.get_json(force=True)
    user_text = data.get('text', '').strip()
    if not user_text:
        return jsonify({'error': 'text required'}), 400
    db = get_session()
    try:
        card = db.query(LearningCard).filter_by(id=card_id, user_id=g.user.id).first()
        if not card:
            return jsonify({'error': 'not found'}), 404
        from services.coaching_service import validate_user_text
        validation = validate_user_text(user_text, card.lernziel or card.category)
        if validation.get('covers_goal', True):
            card.final_text = user_text
            card.source = 'user'
            db.commit()
        return jsonify({'ok': True, 'validation': validation})
    finally:
        db.close()
