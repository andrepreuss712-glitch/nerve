"""Learning Card + Coach Report API routes."""
from flask import Blueprint, request, jsonify, g
from routes.auth import login_required
from services import outcome_service
from database.db import get_session
from database.models import ConversationLog, Call, TranscriptSegment
import services.live_session as ls

learning_bp = Blueprint('learning', __name__)

# Phase 08.23.2.D: socketio fuer outcome_ready-Emit
try:
    from extensions import socketio as _sio_phase_d
except ImportError:
    _sio_phase_d = None


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

    try:
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

        # -- Phase 08.23.2.D REQ-D-3 - Haiku-Outcome-Classifier + calls-UPDATE + outcome_ready-Emit --
        _posted_call_id = data.get('call_id') if isinstance(data, dict) else None
        _outcome_val = None
        _outcome_conf = 0.0
        _outcome_source_val = None
        if _posted_call_id:
            # Conv-Data fuer Classifier zusammenbauen
            _db_cls = get_session()
            try:
                _conv = _db_cls.query(ConversationLog).filter(
                    ConversationLog.id == conv_id,
                    ConversationLog.user_id == g.user.id,
                ).first()
                if _conv is not None:
                    _conv_data = {
                        'dauer_sekunden': data.get('dauer_sek', 0) or 0,
                        'erreichte_phase': getattr(_conv, 'erreichte_phase', None),
                        'einwaende_liste': data.get('einwaende', []),
                        'ewb_clicks': [],
                        'kb_endwert': data.get('kb_end', 0) or 0,
                        'log_entries': [],
                    }
                    # D.UX.1 (Bug A Fix, DA-05): log_entries kommen jetzt aus der DB-Tabelle
                    # transcript_segments — NICHT mehr aus dem alten getattr-Lesepfad auf eine
                    # nie existierende Spalte (Bug-A-Wurzel: conversation_logs hat diese Spalte nicht).
                    # F2 (Cross-AI Gemini): stabile Zwei-Spalten-Ordnung (ts_ms, id). id=BIGSERIAL=
                    # Insert-Reihenfolge = temporale Ordnung — korrekter Sekundaerschluessel bei
                    # ts_ms-Ties (Postgres-Sort ist auf Ties nicht stabil; HH:MM:SS hat 1s-Granularitaet).
                    segments = (_db_cls.query(TranscriptSegment)
                                .filter(TranscriptSegment.conversation_log_id == _conv.id)
                                .order_by(TranscriptSegment.ts_ms, TranscriptSegment.id)
                                .all())
                    _conv_data['log_entries'] = [
                        {'ts_ms': s.ts_ms, 'speaker': s.speaker, 'text': s.text}
                        for s in segments
                    ]
                    if not segments:
                        print(f'[D.UX.1] no transcript_segments for conv={_conv.id} (empty transcript or pre-0010 call)')

                    _result = outcome_service.classify(_conv_data)
                    _outcome_val = _result.get('outcome')
                    _outcome_conf = float(_result.get('confidence', 0.0))

                    # Schwellenlogik (D.UX.1 Bug B Fix — DB-01/02/03). Thresholds unveraendert (DB-03).
                    # ck_calls_outcome_source erlaubt bereits ai_auto / ai_auto_unsicher / user_corrected
                    # -> keine Constraint-Aenderung. Reihenfolge: == 0 ZUERST testen.
                    if _outcome_conf == 0:
                        # Kein Klassifizierungs-Versuch: leeres Transcript / API-Timeout / Parse-Fehler / Exception.
                        _outcome_val = None
                        _outcome_source_val = None
                        # DB-04 Telemetrie: lokal ableitbarer Fehler-Typ. empty_transcript wenn log_entries leer,
                        # sonst classify_zero (outcome_service liefert hier nur confidence — feinere Typen
                        # empty/timeout/parse/exception sind D.UX.4-Telemetrie, deferred per CONTEXT).
                        _fail_type = 'empty_transcript' if not _conv_data.get('log_entries') else 'classify_zero'
                        print(f'[D.UX.1] classify() confidence=0 fail_type={_fail_type} conv={_conv.id}')
                    elif _outcome_conf < 0.70:
                        # Haiku unsicher: Best-Guess BEHALTEN (DB-02, fuer DPO-Training Phase E), NICHT auf None setzen.
                        _outcome_source_val = 'ai_auto_unsicher'
                    elif _outcome_conf < 0.90:
                        _outcome_source_val = 'ai_auto_unsicher'  # bestehende D.UX-Logik (0.70..0.90)
                    else:
                        _outcome_source_val = 'ai_auto'           # bestehende D.UX-Logik (>= 0.90)
            finally:
                _db_cls.close()

            # UPDATE calls (separate Session)
            if _outcome_val is not None or _outcome_conf > 0.0:
                _db_upd = get_session()
                try:
                    _call_row = _db_upd.query(Call).filter(
                        Call.id == _posted_call_id,
                        Call.user_id == g.user.id,
                    ).first()
                    if _call_row is not None:
                        if _outcome_val is not None:
                            _call_row.outcome = _outcome_val
                            _call_row.outcome_confidence = _outcome_conf
                            _call_row.outcome_source = _outcome_source_val
                        else:
                            # Niedrige Confidence: confidence trotzdem speichern fuer Statistik
                            _call_row.outcome_confidence = _outcome_conf
                        _db_upd.commit()
                except Exception as _e_cu:
                    print(f'[Phase08.23.2.D] postcall calls-UPDATE Fehler: {_e_cu}')
                    _db_upd.rollback()
                finally:
                    _db_upd.close()

            # SocketIO emit 'outcome_ready' - NUR room-targeted, KEIN broadcast (Multi-User-Privacy)
            if _sio_phase_d is not None:
                try:
                    _sid_for_emit = None
                    with ls._session_state_lock:
                        for _sid, _sd in ls._session_state.items():
                            if str(_sd.get('state', {}).get('call_id')) == str(_posted_call_id):
                                _sid_for_emit = _sid
                                break
                    if _sid_for_emit:
                        # BLOCKER-1: emit fires even for confidence=0 (outcome/source null) so FE _decideModalState
                        # can render Zustand 1 ('Automatische Erkennung nicht verfügbar'). Dieser Emit ist ein
                        # SIBLING des calls-UPDATE-Write-Guards (oben) — er haengt NICHT von (_outcome_val or
                        # _outcome_conf) ab, nur von SocketIO + aktiver SID. NICHT in den Write-Guard verschieben.
                        _payload = {
                            'outcome': _outcome_val,
                            'confidence': round(_outcome_conf, 3),
                            'source': _outcome_source_val,
                            'call_id': str(_posted_call_id),
                        }
                        _sio_phase_d.emit('outcome_ready', _payload, room=_sid_for_emit)
                    # else: KEINE aktive SID - SKIP emit. Frontend nutzt /api/calls/latest_outcome
                    # fuer den Reconnect-Case (D-04e Fallback-Pull). Broadcast ist verboten weil
                    # multi-user-leaky (alle verbundenen User wuerden den Event empfangen).
                except Exception as _e_em:
                    print(f'[Phase08.23.2.D] outcome_ready emit Fehler: {_e_em}')

        # BLOCKER-1 (belt-and-suspenders): unconditional response — traegt den confidence=0-Fall
        # ({outcome:null, source:null, call_id}) fuer den no-active-SID Fallback (Plan 04 Call-site B).
        # KEIN (_outcome_val||_outcome_conf)-Guard hier.
        return jsonify({
            'vorschlaege': suggestions,
            'outcome': _outcome_val,
            'confidence': round(_outcome_conf, 3) if _outcome_conf else 0.0,
            'source': _outcome_source_val,
            'call_id': str(_posted_call_id) if _posted_call_id else None,
        })
    except Exception as _e:
        import traceback
        traceback.print_exc()
        print(f"[Learning] api_postcall_analysis Fehler: {_e}")
        return jsonify({'ok': False, 'error': 'internal error'}), 500


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


