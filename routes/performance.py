import json
from datetime import datetime, timedelta, date
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

        # ── Ø Score (aus kb_end der Live-Sessions) ────────────────────────
        scores = [l.kb_end for l in logs_90 if getattr(l, 'kb_end', None) is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None

        # ── Deals diese Woche / gesamt ────────────────────────────────────
        cutoff_7 = datetime.now() - timedelta(days=7)
        deals_diese_woche = sum(
            1 for l in logs_90
            if getattr(l, 'result', None) == 'gewonnen'
            and l.created_at and l.created_at >= cutoff_7
        )
        deals_gesamt = sum(1 for l in logs_90 if getattr(l, 'result', None) == 'gewonnen')

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
            'avg_score':            avg_score,
            'deals_diese_woche':    deals_diese_woche,
            'deals_gesamt':         deals_gesamt,
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


# ── GET /api/dashboard ────────────────────────────────────────────────────────

@performance_bp.route('/api/dashboard')
@login_required
def api_dashboard():
    db = get_session()
    try:
        user = db.get(UserModel, g.user.id)
        now = datetime.now()

        # ── Zeitgrenzen ───────────────────────────────────────────────────────
        cutoff_7  = now - timedelta(days=7)
        cutoff_14 = now - timedelta(days=14)
        cutoff_28 = now - timedelta(days=28)
        cutoff_90 = now - timedelta(days=90)

        logs_90 = (db.query(ConversationLog)
                   .filter(ConversationLog.user_id == g.user.id,
                           ConversationLog.created_at >= cutoff_90)
                   .order_by(ConversationLog.created_at.asc())
                   .all())

        logs_live_90  = [l for l in logs_90 if getattr(l, 'typ', None) == 'live']
        logs_this_week = [l for l in logs_live_90 if l.created_at and l.created_at >= cutoff_7]
        logs_last_week = [l for l in logs_live_90 if l.created_at and cutoff_14 <= l.created_at < cutoff_7]

        # ── Begrüßung ─────────────────────────────────────────────────────────
        hour = now.hour
        if hour < 12:
            greeting = 'Guten Morgen'
        elif hour < 18:
            greeting = 'Hallo'
        else:
            greeting = 'Guten Abend'

        vorname = getattr(user, 'vorname', '') or ''

        streak = user.streak_count or 0

        # Score-Trend diese Woche vs. letzte Woche
        scores_this = [l.kb_end for l in logs_this_week if l.kb_end]
        scores_last = [l.kb_end for l in logs_last_week if l.kb_end]
        avg_score = round(sum(scores_this) / len(scores_this), 1) if scores_this else None
        avg_score_last = round(sum(scores_last) / len(scores_last), 1) if scores_last else None
        score_trend_pct = None
        if avg_score and avg_score_last and avg_score_last > 0:
            score_trend_pct = round((avg_score - avg_score_last) / avg_score_last * 100)

        if score_trend_pct and score_trend_pct > 0:
            greeting_subtitle = f'Dein Score ist diese Woche um {score_trend_pct}% gestiegen 📈'
        elif streak >= 7:
            greeting_subtitle = f'🔥 {streak} Tage Streak — stark!'
        elif streak >= 3:
            greeting_subtitle = f'🔥 {streak} Tage Streak — weiter so!'
        else:
            last_live = logs_live_90[-1] if logs_live_90 else None
            days_inactive = (now - last_live.created_at).days if last_live else 999
            if days_inactive >= 3:
                greeting_subtitle = 'Zeit für eine neue Session — deine Skills warten!'
            else:
                greeting_subtitle = 'Bereit für den nächsten Deal?'

        # ── KPIs ──────────────────────────────────────────────────────────────
        sessions_this_week = len(logs_this_week)
        sessions_last_week = len(logs_last_week)
        sessions_delta = sessions_this_week - sessions_last_week

        deals_total = sum(1 for l in logs_live_90 if getattr(l, 'result', None) == 'gewonnen')

        logs_4w = [l for l in logs_live_90 if l.created_at and l.created_at >= cutoff_28]
        calls_pro_woche = round(len(logs_4w) / 4.0, 1) if logs_4w else 0
        calls_pro_monat = round(calls_pro_woche * 4.3)

        getaggt  = [l for l in logs_live_90 if getattr(l, 'result', None) in ('gewonnen', 'verloren')]
        gewonnen = [l for l in getaggt if getattr(l, 'result', None) == 'gewonnen']
        closing_rate = round(len(gewonnen) / len(getaggt) * 100, 1) if getaggt else None
        cr_fuer_formel = closing_rate or 20.0

        avg_deal_wert  = user.avg_deal_wert if user else None
        dw_fuer_formel = avg_deal_wert or 0
        umsatz_pro_monat = round(calls_pro_monat * (cr_fuer_formel / 100.0) * dw_fuer_formel) if dw_fuer_formel else 0

        # ── Aktivitäts-Chart (letzte 4 Wochen) ───────────────────────────────
        wochen_data = {}
        for l in logs_live_90:
            if l.created_at and l.created_at >= cutoff_28:
                kw = l.created_at.strftime('%G-W%V')
                wochen_data[kw] = wochen_data.get(kw, 0) + 1
        alle_wochen = []
        for i in range(3, -1, -1):
            kw = (now - timedelta(weeks=i)).strftime('%G-W%V')
            if kw not in alle_wochen:
                alle_wochen.append(kw)
        activity_labels = ['KW' + w.split('-W')[1] for w in alle_wochen]
        activity_data   = [wochen_data.get(w, 0) for w in alle_wochen]

        # ── Einwand-Performance (aus gegenargument_details) ───────────────────
        einwand_stats = {}
        for log in logs_90:
            if not log.gegenargument_details:
                continue
            try:
                for ga in json.loads(log.gegenargument_details):
                    et = ga.get('einwand_typ', '')
                    if not et:
                        continue
                    if et not in einwand_stats:
                        einwand_stats[et] = {'gesamt': 0, 'behandelt': 0}
                    einwand_stats[et]['gesamt'] += 1
                    if ga.get('behandelt'):
                        einwand_stats[et]['behandelt'] += 1
            except Exception:
                pass

        objection_list = []
        for et, st in sorted(einwand_stats.items(), key=lambda x: -x[1]['gesamt'])[:4]:
            rate = round(st['behandelt'] / max(st['gesamt'], 1) * 100)
            objection_list.append({'name': et, 'success_rate': rate})
        objection_list.sort(key=lambda x: -x['success_rate'])

        # ── Sales Performance ─────────────────────────────────────────────────
        forecast = _berechne_forecast(calls_pro_monat, cr_fuer_formel, dw_fuer_formel)

        roi_mehrwert = None
        if dw_fuer_formel and closing_rate is not None:
            cr_delta = closing_rate * 0.15 / 100.0
            roi_mehrwert = round(calls_pro_monat * cr_delta * dw_fuer_formel) - 99

        hint_ewb = None
        if dw_fuer_formel and cr_fuer_formel:
            cr_mit_ewb  = min(cr_fuer_formel * 1.10, 100)
            hint_ewb    = round(calls_pro_monat * (cr_mit_ewb - cr_fuer_formel) / 100.0 * dw_fuer_formel)

        # S-Kurve (12 Monatspunkte, kumulativ)
        s_curve_data = []
        if dw_fuer_formel:
            umsatz_basis = calls_pro_monat * (cr_fuer_formel / 100.0) * dw_fuer_formel
            cumulative = 0
            for i in range(1, 13):
                cumulative += round(umsatz_basis * (1.05 ** i))
                s_curve_data.append(cumulative)
        else:
            s_curve_data = [0] * 12

        # ── Letzte Sessions ───────────────────────────────────────────────────
        recent_logs = (db.query(ConversationLog)
                       .filter(ConversationLog.user_id == g.user.id)
                       .order_by(ConversationLog.created_at.desc())
                       .limit(5).all())

        recent_sessions = []
        for l in recent_logs:
            if l.created_at:
                delta = now - l.created_at
                if delta.days == 0:
                    date_str = 'Heute ' + l.created_at.strftime('%H:%M')
                elif delta.days == 1:
                    date_str = 'Gestern ' + l.created_at.strftime('%H:%M')
                else:
                    date_str = l.created_at.strftime('%d.%m.')
            else:
                date_str = '-'
            if getattr(l, 'typ', None) == 'training':
                stype = 'training'
            elif getattr(l, 'session_mode', None) == 'cold_call':
                stype = 'cold_call'
            else:
                stype = 'meeting'
            recent_sessions.append({
                'id':           l.id,
                'date_str':     date_str,
                'session_type': stype,
                'score':        l.kb_end or 0,
            })

        # ── Empfehlungen ──────────────────────────────────────────────────────
        recommendations = []
        if objection_list:
            weakest = min(objection_list, key=lambda x: x['success_rate'])
            if weakest['success_rate'] < 65:
                recommendations.append({
                    'icon':     '🎯',
                    'title':    f'Trainiere "{weakest["name"]}"',
                    'subtitle': f'Schwächster Einwand ({weakest["success_rate"]}% Erfolg)',
                    'url':      f'/training?quick=1&einwand_typ={weakest["name"]}',
                })
        if streak >= 3:
            recommendations.append({
                'icon':     '🔥',
                'title':    f'{streak} Tage Streak!',
                'subtitle': 'Stark — mach weiter so!',
                'url':      None,
            })
        elif sessions_this_week == 0:
            recommendations.append({
                'icon':     '📈',
                'title':    'Noch kein Call diese Woche',
                'subtitle': 'Starte jetzt um den Streak zu beginnen!',
                'url':      '/live',
            })
        if 0 < sessions_this_week <= 7:
            goal = sessions_this_week + max(1, 3 - sessions_this_week % 3)
            remaining = goal - sessions_this_week
            if 1 <= remaining <= 5:
                recommendations.append({
                    'icon':     '🏆',
                    'title':    f'Noch {remaining} Calls für Wochen-Ziel!',
                    'subtitle': f'{sessions_this_week} von {goal} diese Woche',
                    'url':      None,
                })
        recommendations = recommendations[:3]
        if not recommendations:
            recommendations.append({
                'icon':     '🚀',
                'title':    'Bereit für den ersten Call?',
                'subtitle': 'Starte NERVE im Live-Modus',
                'url':      '/live',
            })

        return jsonify({
            'greeting':          greeting,
            'greeting_subtitle': greeting_subtitle,
            'vorname':           vorname,
            'kpis': {
                'avg_score':           avg_score,
                'sessions_this_week':  sessions_this_week,
                'deals_total':         deals_total,
                'revenue_month':       umsatz_pro_monat,
                'streak_days':         streak,
            },
            'kpi_trends': {
                'avg_score_pct':   score_trend_pct,
                'sessions_delta':  sessions_delta,
            },
            'activity_chart': {
                'labels': activity_labels,
                'data':   activity_data,
            },
            'objection_performance': objection_list,
            'performance': {
                'hat_daten':       len(logs_live_90) >= 3,
                'umsatz_pro_monat': umsatz_pro_monat,
                'forecast_12m':    forecast['forecast_12m'],
                'roi_mehrwert':    roi_mehrwert,
                'avg_deal_wert':   avg_deal_wert,
                'calls_pro_monat': calls_pro_monat,
                'closing_rate':    closing_rate,
                'hint_ewb':        hint_ewb,
                's_curve':         s_curve_data,
            },
            'recent_sessions':   recent_sessions,
            'recommendations':   recommendations,
        })
    finally:
        db.close()
