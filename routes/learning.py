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
        # D-01: Log learning_card_accepted event before commit
        try:
            from services.integration_engine import log_learning_event
            log_learning_event(db, g.user.id, 'learning_card_accepted', 'coach', card.call_id, {
                'card_id': card.id, 'category': card.category,
            })
        except Exception as _le:
            print(f"[Engine] LearningCard Event Fehler: {_le}")
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
        # D-01: Log learning_card_rejected when archiving (before commit)
        if new_status == 'archiviert':
            try:
                from services.integration_engine import log_learning_event
                log_learning_event(db, g.user.id, 'learning_card_rejected', 'coach', card.call_id, {
                    'card_id': card.id, 'category': card.category,
                })
            except Exception as _le:
                print(f"[Engine] LearningCard Event Fehler: {_le}")
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
        # D-01: Log learning_card_applied event (before commit)
        try:
            from services.integration_engine import log_learning_event
            log_learning_event(db, g.user.id, 'learning_card_applied', 'coach', card.call_id, {
                'card_id': card.id, 'category': card.category,
            })
        except Exception as _le:
            print(f"[Engine] LearningCard Event Fehler: {_le}")
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
            # D-01: Log learning_card_custom event (before commit)
            try:
                from services.integration_engine import log_learning_event
                log_learning_event(db, g.user.id, 'learning_card_custom', 'coach', card.call_id, {
                    'card_id': card.id, 'category': card.category,
                })
            except Exception as _le:
                print(f"[Engine] LearningCard Event Fehler: {_le}")
            db.commit()
        return jsonify({'ok': True, 'validation': validation})
    finally:
        db.close()


@learning_bp.route('/api/training/postcall-analysis', methods=['POST'])
@login_required
def api_training_postcall_analysis():
    """D-09: Lernkarten-Vorschlaege nach Training generieren.
    Gleicher Mechanismus wie Post-Call Analyse, aber mit Training-ConversationLog."""
    req_data = request.get_json(silent=True) or {}
    conv_id = req_data.get('conv_id')
    if not conv_id:
        return jsonify({'ok': False, 'error': 'conv_id fehlt'}), 400

    from database.db import get_session
    db = get_session()
    try:
        from database.models import ConversationLog
        conv = db.query(ConversationLog).filter_by(id=conv_id, user_id=g.user.id).first()
        if not conv or conv.typ != 'training':
            return jsonify({'ok': False, 'error': 'Training-Session nicht gefunden'}), 404

        # Wendepunkt-Saetze aus phasen_details (scoring) extrahieren
        import json
        scoring = json.loads(conv.phasen_details or '{}')
        wendepunkt_saetze = scoring.get('wendepunkt_saetze', [])
        einwaende = [{'typ': ws.get('einwand_typ', '?'), 'zitat': ws.get('text', '')} for ws in wendepunkt_saetze]
        ga_details = json.loads(conv.gegenargument_details or '[]')

        from services.coaching_service import generate_postcall_analysis
        suggestions = generate_postcall_analysis(
            conv_id=conv.id,
            user_id=g.user.id,
            einwaende=einwaende,
            painpoints=[],
            kb_start=0,
            kb_end=conv.kb_end or scoring.get('gesamt_score', 0),
            redeanteil_berater=60,
            redeanteil_kunde=40,
            dauer_sek=conv.dauer_sekunden or 0,
            skript_abdeckung=scoring.get('gesamt_score', 0),
            ga_details=ga_details,
        )
        return jsonify({'ok': True, 'suggestions': suggestions})
    except Exception as e:
        print(f"[Learning] Training PostCall Analysis Fehler: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        db.close()
