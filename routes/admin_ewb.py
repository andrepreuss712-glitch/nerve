"""Phase 08 Plan 06 — EWB-Quality Admin Blueprint.

Zwei Pages:
  - GET  /admin/ewb/quality          : A/B-Stats + Quality-Score-Gate + Varianz-Range
  - GET  /admin/ewb/rating-template  : Bulk-Rating-UI fuer Andre (100 EWBs x 3 Kriterien)
  - POST /admin/ewb/rating-template/<conv_id>/<einwand_key>/rate : Inline-AJAX-Save

Alle Routes gated durch @login_required + @superadmin_required
(Pattern aus routes/admin_dashboard.py Phase 04.7.2).
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, render_template, request
from sqlalchemy import text

from database.db import get_session
from database.models import EwbRating
from routes.auth import login_required
from services.auth_decorators import superadmin_required


admin_ewb_bp = Blueprint(
    'admin_ewb', __name__,
    url_prefix='/admin/ewb',
    template_folder='../templates/admin',
)


@admin_ewb_bp.route('/quality')
@login_required
@superadmin_required
def ewb_quality():
    """A/B-Stats-Card: success_rate pro prompt_version + Quality-Gate + Varianz-Range."""
    db = get_session()
    try:
        # A/B-Auswertung (D-22, RESEARCH Focus Area 3): 3-stufiger JOIN
        ab_rows = db.execute(text("""
            SELECT ftoe.prompt_version AS version,
                   COUNT(*) AS n,
                   AVG(CASE WHEN oe.success = 1 THEN 1.0 ELSE 0.0 END) AS success_rate
            FROM ft_objection_events ftoe
            JOIN ft_call_sessions fcs ON fcs.id = ftoe.ft_session_id
            JOIN objection_events oe
              ON oe.conversation_log_id = fcs.conversation_log_id
             AND oe.einwand_typ = ftoe.objection_type
            WHERE oe.success IS NOT NULL
            GROUP BY ftoe.prompt_version
            ORDER BY ftoe.prompt_version
        """)).fetchall()
        # Rows zu dicts umwandeln fuer robusten Template-Zugriff (row.version, row.n, ...).
        ab_rows = [
            {'version': r[0], 'n': r[1], 'success_rate': float(r[2] or 0.0)}
            for r in ab_rows
        ]

        # Quality-Score-Gate (D-27): >= 80% der Ratings haben Score >= 80
        rating_rows = db.query(EwbRating).all()
        scores = [r.quality_score for r in rating_rows]
        total = len(scores)
        high = sum(1 for s in scores if s >= 80)
        pct_high = (high / total * 100) if total else 0.0

        # Varianz-Range (D-28): max-min ueber kb_end der rated Sessions.
        # kb_end IST die persistierte Form von scoring.gesamt_score
        # (routes/training.py:726 + services/integration_engine.py:217).
        # CONTEXT D-28 spricht konzeptionell von 'gesamt_score' — keine neue
        # Column noetig. RESEARCH Open Question 5 = RESOLVED.
        rated_conv_ids = {r.conversation_log_id for r in rating_rows}
        if rated_conv_ids:
            # expanding bindparams Pattern fuer IN-Queries
            ids_list = list(rated_conv_ids)
            placeholders = ','.join(f':id{i}' for i in range(len(ids_list)))
            params = {f'id{i}': _id for i, _id in enumerate(ids_list)}
            score_rows = db.execute(
                text(f"""
                    SELECT COALESCE(kb_end, 0) AS s FROM conversation_logs
                    WHERE id IN ({placeholders})
                """),
                params,
            ).fetchall()
            session_scores = [r[0] for r in score_rows if r[0] is not None]
            varianz_range = (max(session_scores) - min(session_scores)) if session_scores else 0
        else:
            varianz_range = 0

        return render_template(
            'admin/ewb_quality.html',
            ab_rows=ab_rows,
            total_ratings=total,
            high_score_count=high,
            pct_high=pct_high,
            varianz_range=varianz_range,
        )
    finally:
        db.close()


@admin_ewb_bp.route('/rating-template')
@login_required
@superadmin_required
def ewb_rating_template():
    """Bulk-Rating-UI: Alle bisherigen ObjectionEvents mit Rating-Status (LEFT JOIN)."""
    db = get_session()
    try:
        # LEFT JOIN: zeigt auch ungerateted events; pre-populated wenn bereits gerated.
        q = db.execute(text("""
            SELECT oe.id                  AS oe_id,
                   oe.einwand_typ         AS einwand_typ,
                   oe.success             AS success,
                   oe.conversation_log_id AS conv_id,
                   cl.session_mode        AS session_mode,
                   cl.created_at          AS created_at,
                   r.klingt_wie_mensch    AS klingt_wie_mensch,
                   r.keine_halluzination  AS keine_halluzination,
                   r.trifft_einwand       AS trifft_einwand
            FROM objection_events oe
            JOIN conversation_logs cl ON cl.id = oe.conversation_log_id
            LEFT JOIN ewb_ratings r
              ON r.conversation_log_id = oe.conversation_log_id
             AND r.einwand_typ_key = oe.einwand_typ
            ORDER BY cl.created_at DESC, oe.id ASC
            LIMIT 200
        """)).fetchall()
        events = [
            {
                'oe_id': row[0],
                'einwand_typ': row[1],
                'success': row[2],
                'conv_id': row[3],
                'session_mode': row[4],
                'created_at': row[5],
                'klingt_wie_mensch': row[6],
                'keine_halluzination': row[7],
                'trifft_einwand': row[8],
            }
            for row in q
        ]
        return render_template('admin/ewb_rating_template.html', events=events)
    finally:
        db.close()


@admin_ewb_bp.post('/rating-template/<int:conv_id>/<path:einwand_key>/rate')
@login_required
@superadmin_required
def ewb_rating_save(conv_id, einwand_key):
    """AJAX-Save fuer ein einzelnes EWB-Rating.

    Idempotent via UniqueConstraint uq_ewb_rating_per_conv_ewb:
      - existing row → UPDATE
      - no row       → INSERT

    Payload: {klingt_wie_mensch: bool, keine_halluzination: bool, trifft_einwand: bool}
    Strict Boolean-Check (T-08-06-02): alle 3 Felder muessen in (True, False).
    """
    data = request.get_json(silent=True) or {}
    klingt = data.get('klingt_wie_mensch')
    halluzi = data.get('keine_halluzination')
    trifft = data.get('trifft_einwand')
    if any(x not in (True, False) for x in (klingt, halluzi, trifft)):
        return jsonify({
            'error': 'invalid_criteria',
            'expected': 'all 3 fields (klingt_wie_mensch, keine_halluzination, trifft_einwand) must be bool',
        }), 400

    db = get_session()
    try:
        existing = (
            db.query(EwbRating)
              .filter_by(conversation_log_id=conv_id, einwand_typ_key=einwand_key)
              .first()
        )
        if existing:
            existing.klingt_wie_mensch = klingt
            existing.keine_halluzination = halluzi
            existing.trifft_einwand = trifft
            existing.rater_id = g.user.id
            existing.rated_at = datetime.utcnow()
        else:
            db.add(EwbRating(
                conversation_log_id=conv_id,
                einwand_typ_key=einwand_key,
                klingt_wie_mensch=klingt,
                keine_halluzination=halluzi,
                trifft_einwand=trifft,
                rater_id=g.user.id,
            ))
        db.commit()
        print(
            f"[EWB-Rating] conv={conv_id} ewb='{einwand_key[:30]}' "
            f"klingt={klingt} halluzi={halluzi} trifft={trifft}"
        )
        return jsonify({'ok': True})
    finally:
        db.close()
