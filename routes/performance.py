import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, g
from routes.auth import login_required
from database.db import get_session
from database.models import ConversationLog, User as UserModel

performance_bp = Blueprint('performance', __name__)

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _get_calendar_week(dt):
    """Gibt ISO-Kalenderwoche als String zurueck: '2026-W14'"""
    return dt.strftime('%G-W%V')

def _berechne_forecast(calls_pro_monat, closing_rate, avg_deal_wert):
    """
    Berechnet Umsatz-Forecast fuer 3/6/12 Monate.
    S-Kurven-Effekt: leicht exponentiell (Faktor 1.05 pro Monat durch NERVE-Verbesserung).
    """
    if not avg_deal_wert or calls_pro_monat == 0:
        return {'forecast_3m': 0, 'forecast_6m': 0, 'forecast_12m': 0}

    umsatz_monat = calls_pro_monat * (closing_rate / 100.0) * avg_deal_wert
    wachstum = 1.05   # 5% monatliche Verbesserung durch NERVE (Marketing-Annahme)

    f3, f6, f12 = 0, 0, 0
    for i in range(1, 13):
        monat_umsatz = round(umsatz_monat * (wachstum ** i))
        if i <= 3:
            f3 += monat_umsatz
        if i <= 6:
            f6 += monat_umsatz
        f12 += monat_umsatz

    return {
        'forecast_3m':  f3,
        'forecast_6m':  f6,
        'forecast_12m': f12,
    }

# ── GET /api/performance ──────────────────────────────────────────────────────

@performance_bp.route('/api/performance')
@login_required
def api_performance():
    db = get_session()
    try:
        # Lade User fuer avg_deal_wert
        user = db.get(UserModel, g.user.id)
        avg_deal_wert = user.avg_deal_wert if user else None

        # Alle Live-Sessions des Users (letzte 90 Tage fuer Charts)
        cutoff_90 = datetime.now() - timedelta(days=90)
        logs_90 = (db.query(ConversationLog)
                   .filter(
                       ConversationLog.user_id == g.user.id,
                       ConversationLog.typ == 'live',
                       ConversationLog.created_at >= cutoff_90,
                   )
                   .order_by(ConversationLog.created_at.asc())
                   .all())

        hat_daten = len(logs_90) >= 3

        # ── Calls pro Woche (letzte 8 Wochen) ────────────────────────────
        cutoff_56 = datetime.now() - timedelta(days=56)
        logs_8w = [l for l in logs_90 if l.created_at and l.created_at >= cutoff_56]

        wochen_calls = {}   # '2026-W14' -> count
        wochen_abschluesse = {}
        for l in logs_8w:
            if not l.created_at:
                continue
            kw = _get_calendar_week(l.created_at)
            wochen_calls[kw] = wochen_calls.get(kw, 0) + 1
            if getattr(l, 'result', None) == 'gewonnen':
                wochen_abschluesse[kw] = wochen_abschluesse.get(kw, 0) + 1

        # Letzten 8 Wochen aufsteigend
        alle_wochen = sorted(set(list(wochen_calls.keys())))[-8:]
        chart_data = {
            'labels': alle_wochen,
            'calls':  [wochen_calls.get(w, 0) for w in alle_wochen],
            'abschluesse': [wochen_abschluesse.get(w, 0) for w in alle_wochen],
        }

        # ── Calls pro Woche (Durchschnitt letzte 4 Wochen) ───────────────
        cutoff_28 = datetime.now() - timedelta(days=28)
        logs_4w = [l for l in logs_90 if l.created_at and l.created_at >= cutoff_28]
        calls_pro_woche = round(len(logs_4w) / 4.0, 1) if logs_4w else 0
        calls_pro_monat = round(calls_pro_woche * 4.3)

        # ── Closing Rate ──────────────────────────────────────────────────
        getaggt = [l for l in logs_90 if getattr(l, 'result', None) in ('gewonnen', 'verloren')]
        gewonnen = [l for l in getaggt if getattr(l, 'result', None) == 'gewonnen']
        closing_rate = round(len(gewonnen) / len(getaggt) * 100, 1) if getaggt else None

        # ── Einwand-Erfolgsquote ──────────────────────────────────────────
        total_einwaende = sum(l.einwaende_gesamt or 0 for l in logs_90)
        total_behandelt = sum(l.einwaende_behandelt or 0 for l in logs_90)
        einwand_erfolgsquote = round(total_behandelt / total_einwaende * 100, 1) if total_einwaende > 0 else None

        # ── Umsatz-Berechnung ─────────────────────────────────────────────
        cr_fuer_formel = closing_rate or 20.0   # Fallback fuer Simulation
        dw_fuer_formel = avg_deal_wert or 0
        umsatz_pro_monat = round(calls_pro_monat * (cr_fuer_formel / 100.0) * dw_fuer_formel) if dw_fuer_formel else 0

        forecast = _berechne_forecast(calls_pro_monat, cr_fuer_formel, dw_fuer_formel)

        # ── Trend vs. Vormonat ────────────────────────────────────────────
        cutoff_30 = datetime.now() - timedelta(days=30)
        cutoff_60 = datetime.now() - timedelta(days=60)
        logs_letzter_monat = [l for l in logs_90 if l.created_at and l.created_at >= cutoff_30]
        logs_vormonat = [l for l in logs_90 if l.created_at and cutoff_60 <= l.created_at < cutoff_30]
        trend_prozent = None
        if logs_vormonat:
            trend_prozent = round((len(logs_letzter_monat) - len(logs_vormonat)) / max(len(logs_vormonat), 1) * 100)

        # ── ROI ──────────────────────────────────────────────────────────
        # ROI = (15% Einwand-Verbesserung) * Closing-Rate-Delta * Calls/Monat * avg_deal_wert - 99
        # Annahme: NERVE verbessert Einwand-Erfolgsquote um 15% (Marketing-Annahme, klar gelabelt)
        roi_mehrwert = None
        if dw_fuer_formel and closing_rate is not None:
            nerve_verbesserung = 0.15   # 15% Einwand-Erfolgsquote-Verbesserung (Annahme)
            cr_delta = closing_rate * nerve_verbesserung / 100.0
            roi_mehrwert = round(calls_pro_monat * cr_delta * dw_fuer_formel) - 99

        return jsonify({
            'hat_daten':            hat_daten,
            'calls_pro_woche':      calls_pro_woche,
            'calls_pro_monat':      calls_pro_monat,
            'closing_rate':         closing_rate,
            'einwand_erfolgsquote': einwand_erfolgsquote,
            'avg_deal_wert':        avg_deal_wert,
            'umsatz_pro_monat':     umsatz_pro_monat,
            'forecast_3m':          forecast['forecast_3m'],
            'forecast_6m':          forecast['forecast_6m'],
            'forecast_12m':         forecast['forecast_12m'],
            'trend_prozent':        trend_prozent,
            'chart_data':           chart_data,
            'roi_mehrwert':         roi_mehrwert,
            'total_live_calls':     len(logs_90),
        })
    finally:
        db.close()

# ── PATCH /api/session/<id>/result ───────────────────────────────────────────

@performance_bp.route('/api/session/<int:session_id>/result', methods=['PATCH'])
@login_required
def api_session_result(session_id):
    data = request.get_json(force=True) or {}
    result = data.get('result')
    # Nur erlaubte Werte akzeptieren
    if result not in ('gewonnen', 'verloren', None):
        return jsonify({'error': 'Ungültiger Wert — erlaubt: gewonnen | verloren | null'}), 400

    db = get_session()
    try:
        log = (db.query(ConversationLog)
               .filter(
                   ConversationLog.id == session_id,
                   ConversationLog.user_id == g.user.id,   # Nur eigene Sessions
                   ConversationLog.typ == 'live',
               )
               .first())
        if not log:
            return jsonify({'error': 'Session nicht gefunden'}), 404
        log.result = result
        db.commit()
        return jsonify({'ok': True, 'result': result})
    finally:
        db.close()

# ── PATCH /api/user/deal-wert ─────────────────────────────────────────────────

@performance_bp.route('/api/user/deal-wert', methods=['PATCH'])
@login_required
def api_user_deal_wert():
    data = request.get_json(force=True) or {}
    wert = data.get('avg_deal_wert')
    try:
        wert = int(wert)
        if wert < 0 or wert > 10_000_000:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'Ungültiger Wert — muss positive Ganzzahl in Euro sein'}), 400

    db = get_session()
    try:
        user = db.get(UserModel, g.user.id)
        if not user:
            return jsonify({'error': 'User nicht gefunden'}), 404
        user.avg_deal_wert = wert
        db.commit()
        return jsonify({'ok': True, 'avg_deal_wert': wert})
    finally:
        db.close()
