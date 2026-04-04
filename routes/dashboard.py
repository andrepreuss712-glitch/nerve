import os
import re
import json
import hashlib
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, redirect, url_for, g, session as flask_session, jsonify, request
from routes.auth import login_required
from database.db import get_session
from database.models import Profile, User as UserModel, ConversationLog, Organisation
from services.live_session import LOG_DIR

dashboard_bp = Blueprint('dashboard', __name__)


def _parse_log_meta(fname, fpath):
    m = re.match(r'nerve_log_(?:U(\d+)_)?(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.txt', fname)
    uid = int(m.group(1)) if m and m.group(1) else None
    ts_str = m.group(2) if m else None
    dt = None
    if ts_str:
        try:
            dt = datetime.strptime(ts_str, '%Y-%m-%dT%H-%M-%S')
        except Exception:
            pass
    meta = {
        'filename': fname,
        'user_id': uid,
        'datetime': dt,
        'datum': dt.strftime('%d.%m.%Y') if dt else '–',
        'uhrzeit': dt.strftime('%H:%M') if dt else '–',
        'profil': '–',
        'dauer': '–',
        'einwaende': 0,
        'painpoints': 0,
        'segmente': 0,
    }
    try:
        content = open(fpath, encoding='utf-8').read()
        pm = re.search(r'Profil: (.+)', content)
        if pm:
            meta['profil'] = pm.group(1).strip()
        sm = re.search(r'Gesprächssegmente gesamt:\s+(\d+)', content)
        if sm:
            meta['segmente'] = int(sm.group(1))
        em = re.search(r'Erkannte Einwände:\s+(\d+)', content)
        if em:
            meta['einwaende'] = int(em.group(1))
        pm2 = re.search(r'Gesammelte Painpoints:\s+(\d+)', content)
        if pm2:
            meta['painpoints'] = int(pm2.group(1))
        timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2})\]', content)
        if len(timestamps) >= 2:
            t1 = datetime.strptime(timestamps[0], '%H:%M:%S')
            t2 = datetime.strptime(timestamps[-1], '%H:%M:%S')
            diff = int((t2 - t1).total_seconds())
            meta['dauer'] = f"{diff // 60}:{diff % 60:02d}"
    except Exception:
        pass
    return meta


def _relative_date(dt):
    """Return human-readable relative date label in German."""
    if not dt:
        return '-'
    today = date.today()
    d = dt.date() if hasattr(dt, 'date') else dt
    diff = (today - d).days
    if diff == 0:
        return 'heute'
    if diff == 1:
        return 'gestern'
    if diff < 7:
        return f'vor {diff} Tagen'
    return dt.strftime('%d.%m.')


def get_recent_calls_db(user_id, db, limit=5):
    """DB-based recent calls for dashboard -- includes session_mode and score."""
    from database.models import ConversationLog as CL
    calls = (db.query(CL)
             .filter(CL.user_id == user_id)
             .order_by(CL.created_at.desc())
             .limit(limit)
             .all())
    result = []
    for c in calls:
        dauer_sec = c.dauer_sekunden or 0
        result.append({
            'datum': c.created_at.strftime('%d.%m.%Y') if c.created_at else '-',
            'uhrzeit': c.created_at.strftime('%H:%M') if c.created_at else '-',
            'session_mode': getattr(c, 'session_mode', None) or 'meeting',
            'score': c.kb_end or 0,
            'dauer': f"{dauer_sec // 60}:{dauer_sec % 60:02d}" if dauer_sec else '-',
            'profil': c.profil_name or '-',
            'relative': _relative_date(c.created_at) if c.created_at else '-',
        })
    return result


def get_recent_logs(user_id, org_id, rolle, limit=5):
    is_admin = rolle in ('owner', 'admin')
    result = []
    try:
        files = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt') and f != '.gitkeep'],
            reverse=True
        )
        for fname in files:
            if not is_admin:
                if f'_U{user_id}_' not in fname:
                    continue
            fpath = os.path.join(LOG_DIR, fname)
            result.append(_parse_log_meta(fname, fpath))
            if len(result) >= limit:
                break
    except Exception:
        pass
    return result


def _check_achievements(user, logs):
    total_behandelt = sum(l.einwaende_behandelt or 0 for l in logs)
    achievements = [
        {'id': 'first_call', 'name': 'Erster Call', 'icon': '🎯',
         'desc': 'Dein erstes Gespräch mit NERVE', 'earned': len(logs) >= 1},
        {'id': 'ten_calls', 'name': '10 Gespräche', 'icon': '🔥',
         'desc': '10 Gespräche geführt', 'earned': len(logs) >= 10},
        {'id': 'fifty_calls', 'name': '50 Gespräche', 'icon': '💪',
         'desc': '50 Gespräche geführt', 'earned': len(logs) >= 50},
        {'id': 'einwand_meister', 'name': 'Einwand-Meister', 'icon': '🛡️',
         'desc': '10 Einwände erfolgreich behandelt', 'earned': total_behandelt >= 10,
         'progress': min(total_behandelt, 10), 'goal': 10},
        {'id': 'score_80', 'name': 'Top Performer', 'icon': '⭐',
         'desc': 'Score über 80 erreicht',
         'earned': any((l.kb_end or 0) >= 80 for l in logs)},
        {'id': 'streak_3', 'name': '3-Tage-Streak', 'icon': '🔥',
         'desc': '3 Tage in Folge trainiert', 'earned': (user.streak_count or 0) >= 3},
        {'id': 'streak_7', 'name': 'Woche am Stück', 'icon': '💎',
         'desc': '7 Tage in Folge trainiert', 'earned': (user.streak_count or 0) >= 7},
        {'id': 'streak_30', 'name': 'Unaufhaltbar', 'icon': '👑',
         'desc': '30 Tage in Folge trainiert', 'earned': (user.streak_count or 0) >= 30},
    ]
    return achievements


def _get_level(points):
    levels = [
        {'name': 'Sales Rookie',       'min': 0,     'icon': '🌱'},
        {'name': 'Sales Starter',      'min': 200,   'icon': '⚡'},
        {'name': 'Sales Professional', 'min': 1000,  'icon': '🎯'},
        {'name': 'Sales Expert',       'min': 3000,  'icon': '💎'},
        {'name': 'Sales Master',       'min': 7000,  'icon': '👑'},
        {'name': 'Sales Legend',       'min': 15000, 'icon': '🏆'},
    ]
    current = levels[0]
    next_level = levels[1]
    for i, lvl in enumerate(levels):
        if points >= lvl['min']:
            current = lvl
            next_level = levels[i + 1] if i + 1 < len(levels) else None
    progress = 0
    if next_level:
        range_total = next_level['min'] - current['min']
        range_done = points - current['min']
        progress = min(round(range_done / range_total * 100), 100)
    return {'current': current, 'next': next_level, 'points': points, 'progress': progress}


def _get_quote_of_day():
    quotes = [
        {"text": "Verkaufen heißt nicht reden. Verkaufen heißt die richtige Frage stellen.", "author": ""},
        {"text": "Der Kunde kauft nicht das Produkt. Er kauft die Lösung seines Problems.", "author": ""},
        {"text": "Einwände sind keine Ablehnung. Sie sind Interesse, das noch Antworten braucht.", "author": ""},
        {"text": "Wer fragt, führt. Wer redet, verliert.", "author": ""},
        {"text": "Ein guter Vertriebler hört 70% der Zeit zu und redet 30%.", "author": ""},
        {"text": "Jedes Nein bringt dich näher an dein nächstes Ja.", "author": ""},
        {"text": "Vertrauen entsteht nicht durch Argumente. Vertrauen entsteht durch Zuhören.", "author": ""},
        {"text": "Fang einfach mal an. Den Rest lernst du unterwegs.", "author": "André Preuß"},
        {"text": "Der beste Zeitpunkt für einen Follow-up war gestern. Der zweitbeste ist jetzt.", "author": ""},
        {"text": "Dein Kunde hat ein Problem. Dein Job ist nicht zu verkaufen sondern zu verstehen.", "author": ""},
        {"text": "Motivation bringt dich zum Hörer. Disziplin lässt dich drücken.", "author": ""},
        {"text": "Ein Einwand ist ein Geschenk. Er zeigt dir wo der Kunde wirklich steht.", "author": ""},
        {"text": "Perfektion ist der Feind des Fortschritts. Mach den Call.", "author": ""},
        {"text": "Menschen kaufen von Menschen denen sie vertrauen. Sei echt.", "author": ""},
        {"text": "Der Unterschied zwischen gut und großartig liegt in den letzten 10 Minuten Vorbereitung.", "author": ""},
        {"text": "Wissen schützt. Unwissenheit kostet.", "author": "André Preuß"},
        {"text": "Die beste Technik ist die die du vergisst weil sie dir in Fleisch und Blut übergegangen ist.", "author": ""},
        {"text": "Kein Deal stirbt am Einwand. Er stirbt am fehlenden Follow-up.", "author": ""},
        {"text": "Frag nicht ob der Kunde kaufen will. Frag was ihn davon abhält.", "author": ""},
        {"text": "Jeder Anruf ist eine Chance. Auch wenn sich der letzte wie eine Niederlage angefühlt hat.", "author": ""},
    ]
    day_hash = int(hashlib.md5(str(date.today()).encode()).hexdigest(), 16)
    return quotes[day_hash % len(quotes)]


def _generate_improvement_tip(logs, user):
    if not logs:
        name = user.vorname or 'du'
        return {
            'text': f"Hey {name} — starte dein erstes Training oder Live-Gespräch um personalisierte Tipps zu bekommen.",
            'type': 'start'
        }
    avg_redeanteil = sum(l.redeanteil_avg or 0 for l in logs) / len(logs)
    total_einwaende = sum(l.einwaende_gesamt or 0 for l in logs)
    total_behandelt = sum(l.einwaende_behandelt or 0 for l in logs)
    erfolgsquote = (total_behandelt / total_einwaende * 100) if total_einwaende > 0 else 0
    avg_kb = sum(l.kb_end or 30 for l in logs) / len(logs)
    name = user.vorname or 'du'
    if avg_redeanteil > 60:
        return {
            'text': f"{name}, dein Redeanteil liegt bei {round(avg_redeanteil)}%. Versuche mehr zuzuhören und offene Fragen zu stellen. Ziel: unter 40%.",
            'type': 'redeanteil'
        }
    elif erfolgsquote < 40 and total_einwaende > 3:
        return {
            'text': f"{name}, deine Einwand-Erfolgsquote liegt bei {round(erfolgsquote)}%. Trainiere gezielt mit dem KI-Kunden — besonders Preiseinwände.",
            'type': 'einwaende'
        }
    elif avg_kb < 40:
        return {
            'text': f"{name}, die Kaufbereitschaft deiner Kunden endet im Schnitt bei {round(avg_kb)}%. Versuche mehr Painpoints aufzudecken bevor du dein Produkt vorstellst.",
            'type': 'kb'
        }
    else:
        return {
            'text': f"Starke Woche, {name}! Dein Redeanteil ist bei {round(avg_redeanteil)}% und die Einwand-Quote bei {round(erfolgsquote)}%. Weiter so.",
            'type': 'positiv'
        }


def _generate_weekly_summary(user, stats, logs):
    """Generiert personalisierte Wochen-Zusammenfassung via Claude."""
    try:
        import os as _os
        cache_file = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'logs', f'_summary_{user.id}.json')
        if _os.path.exists(cache_file):
            with open(cache_file, encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('date') == str(date.today()):
                return cached['text']
    except Exception:
        pass

    try:
        from config import ANTHROPIC_API_KEY
        import anthropic
        stil = user.dashboard_stil or ''
        name = user.vorname or 'du'
        persoenlich = user.persoenlich or ''
        stil_anweisung = ''
        if stil:
            stil_anweisung = f"""
WICHTIG — PERSÖNLICHER STIL:
Der User hat folgendes über sich geschrieben: "{stil}"
Formuliere die GESAMTE Zusammenfassung in diesem Stil!
Nutze Metaphern, Vergleiche und Sprache aus dieser Welt.
Sei kreativ, witzig, aber nie herablassend.
Die Zahlen müssen trotzdem korrekt sein — aber die Formulierung soll sich anfühlen
als käme sie aus der Welt des Users.
"""
        prompt = f"""Schreibe eine kurze, motivierende Wochen-Zusammenfassung
für das Sales-Dashboard eines Vertrieblers.

Name: {name}
Persönliches: {persoenlich}
{stil_anweisung}

DATEN DIESER WOCHE:
- Gespräche geführt: {stats.get('gespraeche', 0)}
- Einwand-Erfolgsquote: {stats.get('einwand_erfolg', 0)}%
- Durchschnittlicher Redeanteil: {stats.get('avg_redeanteil', 0)}%
- Trend gegenüber Vorwoche: {stats.get('trend_score', 'neutral')}
- Streak: {stats.get('streak', 0)} Tage

REGELN:
- Maximal 4 Sätze
- Nenne konkrete Zahlen
- Wenn es gut läuft: motivierend, stolz
- Wenn es schlecht läuft: aufmunternd, konstruktiv
- Wenn kein Stil angegeben: professionell aber warm
- Kein Markdown, keine Sternchen — reiner Text
- Sprich den User mit seinem Vornamen an
"""
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = msg.content[0].text.strip()
        try:
            import os as _os
            cache_file = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'logs', f'_summary_{user.id}.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'date': str(date.today()), 'text': text}, f, ensure_ascii=False)
        except Exception:
            pass
        return text
    except Exception:
        return None


def _calculate_roi(user, logs, org):
    """Schätzt ROI basierend auf echten Gesprächsdaten."""
    if not logs or len(logs) < 5:
        return None
    DEAL_VALUES = {
        'SaaS': 5000, 'Versicherung': 2000, 'Consulting': 8000,
        'Recruiting': 6000, 'Immobilien': 10000, 'Agentur': 4000,
        'Industrie': 7000, 'IT-Dienstleistung': 4000, 'Sonstiges': 4000,
    }
    branche  = 'Sonstiges'
    avg_deal = DEAL_VALUES.get(branche, 4000)
    total_einwaende = sum(l.einwaende_gesamt or 0 for l in logs)
    behandelt       = sum(l.einwaende_behandelt or 0 for l in logs)
    if total_einwaende == 0:
        return None
    erfolgsquote   = behandelt / total_einwaende
    zusatz_deals   = round(behandelt * 0.10, 1)
    geschaetzter_mehrwert = round(zusatz_deals * avg_deal)
    plan_kosten    = int(getattr(org, 'plan_preis', None) or 49)
    roi_faktor     = round(geschaetzter_mehrwert / max(plan_kosten, 1), 1)
    return {
        'einwaende_behandelt':     behandelt,
        'einwaende_gesamt':        total_einwaende,
        'erfolgsquote':            round(erfolgsquote * 100),
        'geschaetzte_deals':       zusatz_deals,
        'avg_deal_value':          avg_deal,
        'geschaetzter_mehrwert':   geschaetzter_mehrwert,
        'plan_kosten':             plan_kosten,
        'roi_faktor':              roi_faktor,
        'branche':                 branche,
        'stark':                   roi_faktor >= 10,
    }


def _update_level(user):
    levels = [
        ('rookie', 0), ('starter', 200), ('professional', 1000),
        ('expert', 3000), ('master', 7000), ('legend', 15000),
    ]
    for name, threshold in reversed(levels):
        if (user.total_points or 0) >= threshold:
            user.level = name
            break


@dashboard_bp.route('/')
def root():
    if 'user_id' not in flask_session:
        modal = flask_session.get('open_modal', '')
        return render_template('landing.html', open_modal=modal)
    db = get_session()
    try:
        u = db.get(UserModel, flask_session['user_id'])
        if not u or not u.aktiv:
            flask_session.clear()
            return render_template('landing.html', open_modal='')
    finally:
        db.close()
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/dashboard')
@login_required
def index():
    db = get_session()
    try:
        user = db.query(UserModel).get(g.user.id)

        # ── Wizard redirect: profileless users who finished onboarding ─────
        if user and user.onboarding_done:
            profile_count = db.query(Profile).filter_by(org_id=g.org.id).count()
            if profile_count == 0:
                return redirect(url_for('profiles.wizard_page'))

        # ── Streak aktualisieren ───────────────────────────────────────────
        today = date.today()
        if user.streak_last_date:
            diff = (today - user.streak_last_date).days
            if diff == 0:
                pass
            elif diff == 1:
                user.streak_count = (user.streak_count or 0) + 1
                user.streak_last_date = today
            else:
                user.streak_count = 1
                user.streak_last_date = today
        else:
            # First login — initialize streak
            user.streak_count = 1
            user.streak_last_date = today

        # ── Letzte 30 Tage ─────────────────────────────────────────────────
        cutoff = datetime.now() - timedelta(days=30)
        logs = (db.query(ConversationLog)
                .filter(ConversationLog.user_id == g.user.id,
                        ConversationLog.created_at >= cutoff)
                .order_by(ConversationLog.created_at.desc())
                .all())

        # ── Stats ──────────────────────────────────────────────────────────
        stats = {
            'gespraeche': len(logs),
            'avg_score': 0,
            'einwand_erfolg': 0,
            'avg_redeanteil': 0,
            'avg_kb': 0,
            'trend_score': 'neutral',
            'streak': user.streak_count or 0,
        }
        if logs:
            stats['avg_kb'] = round(sum(l.kb_end or 30 for l in logs) / len(logs))
            total_e = sum(l.einwaende_gesamt or 0 for l in logs)
            total_b = sum(l.einwaende_behandelt or 0 for l in logs)
            stats['einwand_erfolg'] = round(total_b / total_e * 100) if total_e > 0 else 0
            stats['avg_redeanteil'] = round(sum(l.redeanteil_avg or 0 for l in logs) / len(logs))
            # Trend: letzte 7 vs. vorherige 7 Tage
            cutoff_7 = datetime.now() - timedelta(days=7)
            cutoff_14 = datetime.now() - timedelta(days=14)
            recent7 = [l for l in logs if l.created_at and l.created_at >= cutoff_7]
            prev7 = [l for l in logs if l.created_at and cutoff_14 <= l.created_at < cutoff_7]
            if recent7 and prev7:
                avg_r = sum(l.kb_end or 30 for l in recent7) / len(recent7)
                avg_p = sum(l.kb_end or 30 for l in prev7) / len(prev7)
                stats['trend_score'] = 'up' if avg_r > avg_p else ('down' if avg_r < avg_p else 'neutral')

        # ── Aktivitäts-Heatmap (90 Tage) ──────────────────────────────────
        cutoff_90 = datetime.now() - timedelta(days=90)
        all_logs = (db.query(ConversationLog)
                    .filter(ConversationLog.user_id == g.user.id,
                            ConversationLog.created_at >= cutoff_90)
                    .all())
        activity_map = {}
        for l in all_logs:
            if l.created_at:
                day_str = l.created_at.strftime('%Y-%m-%d')
                activity_map[day_str] = activity_map.get(day_str, 0) + 1

        # ── Achievements ───────────────────────────────────────────────────
        achievements = _check_achievements(user, logs)

        # ── Level ──────────────────────────────────────────────────────────
        level_info = _get_level(user.total_points or 0)

        # ── Quote ──────────────────────────────────────────────────────────
        qotd = _get_quote_of_day()

        # ── Personalisierter Text ──────────────────────────────────────────
        weekly_summary = None
        if (user.dashboard_stil or user.persoenlich) and len(logs) >= 3:
            weekly_summary = _generate_weekly_summary(user, stats, logs)
        improvement_tip = _generate_improvement_tip(logs, user)

        # ── Active profile ─────────────────────────────────────────────────
        active_profile = None
        apid = flask_session.get('active_profile_id') or (user.active_profile_id if user else None)
        if apid:
            active_profile = db.query(Profile).filter_by(id=apid, org_id=g.org.id).first()
            if apid:
                flask_session['active_profile_id'] = apid

        profiles = db.query(Profile).filter_by(org_id=g.org.id).order_by(Profile.name).all()
        recent_logs = get_recent_logs(g.user.id, g.org.id, flask_session.get('rolle', 'member'))
        recent_calls = get_recent_calls_db(g.user.id, db, limit=5)
        welcome_trial = flask_session.pop('welcome_trial', False)

        # ── Usage + Fair-Use ───────────────────────────────────────────────────
        minuten_limit   = g.org.minuten_limit or 1000
        minuten_used    = user.minuten_used or 0
        voice_limit     = g.org.training_voice_limit or 50
        voice_used      = user.trainings_voice_used or 0
        plan_key        = getattr(g.org, 'plan', None) or getattr(g.org, 'plan_typ', 'starter') or 'starter'
        from app import PLANS
        plan_def        = PLANS.get(plan_key, PLANS.get('starter', {}))
        usage = {
            'minuten_used':    minuten_used,
            'minuten_limit':   minuten_limit,
            'minuten_prozent': min(100, round(minuten_used / max(minuten_limit, 1) * 100)),
            'voice_used':      voice_used,
            'voice_limit':     voice_limit,
            'voice_prozent':   min(100, round(voice_used / max(voice_limit, 1) * 100)),
            'plan':            plan_key,
            'plan_name':       plan_def.get('name', 'Starter'),
            'plan_preis':      int(getattr(g.org, 'plan_preis', None) or plan_def.get('preis', 49)),
            'reset_date':      user.usage_reset_date,
        }

        # ── ROI ────────────────────────────────────────────────────────────────
        roi = _calculate_roi(user, logs, g.org)

        db.commit()

        dashboard_style = getattr(user, 'dashboard_style', 'vollstaendig') or 'vollstaendig'

        return render_template('dashboard.html',
                               stats=stats,
                               activity_map=json.dumps(activity_map),
                               achievements=achievements,
                               level_info=level_info,
                               improvement_tip=improvement_tip,
                               weekly_summary=weekly_summary,
                               qotd=qotd,
                               user=user,
                               streak=user.streak_count or 0,
                               recent_logs=recent_logs,
                               recent_calls=recent_calls,
                               active_profile=active_profile,
                               profiles=profiles,
                               welcome_trial=welcome_trial,
                               usage=usage,
                               roi=roi,
                               dashboard_style=dashboard_style)
    finally:
        db.close()


@dashboard_bp.route('/api/nudge')
@login_required
def get_nudge():
    user = g.user
    org = g.org
    dismissed = json.loads(user.nudge_dismissed or '[]')
    nudge = None
    if not user.notif_nudges:
        return jsonify({'nudge': None})

    if getattr(org, 'plan_typ', 'bundle') == 'training' and 'cross_sell_live' not in dismissed:
        if (user.trainings_used or 0) >= 5:
            remaining = max(0, (org.training_free_calls or 5) - (user.live_calls_used or 0))
            nudge = {
                'id': 'cross_sell_live',
                'title': 'Bereit für den echten Einsatz?',
                'text': f'Deine Trainings laufen super! Teste die Live-Unterstützung im echten Gespräch — du hast noch {remaining} kostenlose Live-Calls.',
                'cta': 'Live-Modus testen',
                'cta_url': '/live',
                'type': 'positive',
            }
    elif getattr(org, 'plan_typ', 'bundle') == 'live' and 'cross_sell_training' not in dismissed:
        db = get_session()
        try:
            recent = (db.query(ConversationLog)
                      .filter(ConversationLog.user_id == user.id)
                      .order_by(ConversationLog.created_at.desc())
                      .limit(5).all())
            if len(recent) >= 3:
                avg_kb = sum(l.kb_end or 30 for l in recent) / len(recent)
                if avg_kb < 50:
                    remaining = max(0, (org.live_free_trainings or 3) - (user.trainings_used or 0))
                    nudge = {
                        'id': 'cross_sell_training',
                        'title': 'Training macht den Unterschied',
                        'text': f'Deine letzten Gespräche zeigen Potential bei der Einwandbehandlung. Übe gezielt mit unserem KI-Kunden — {remaining} Trainings gratis.',
                        'cta': 'Training starten',
                        'cta_url': '/training',
                        'type': 'helpful',
                    }
        finally:
            db.close()

    return jsonify({'nudge': nudge})


@dashboard_bp.route('/api/nudge/dismiss', methods=['POST'])
@login_required
def dismiss_nudge():
    data = request.get_json(force=True)
    nudge_id = data.get('nudge_id', '')
    db = get_session()
    try:
        user = db.query(UserModel).get(g.user.id)
        dismissed = json.loads(user.nudge_dismissed or '[]')
        if nudge_id not in dismissed:
            dismissed.append(nudge_id)
            user.nudge_dismissed = json.dumps(dismissed)
            db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@dashboard_bp.route('/api/notifications')
@login_required
def get_notifications():
    user = g.user
    notifs = []
    today = date.today()

    # Streak warning
    if user.notif_streak_warning and (user.streak_count or 0) >= 3 and user.streak_last_date:
        diff = (today - user.streak_last_date).days if user.streak_last_date else 999
        if diff >= 1:
            notifs.append({
                'id': 'streak_warning',
                'icon': '🔥',
                'text': f'Dein Streak ist in Gefahr! Noch 1 Training heute um ihn zu halten.',
                'url': '/training',
            })

    # Training reminder (Monday or long gap)
    if user.notif_training_reminder:
        if not user.streak_last_date or (today - user.streak_last_date).days > 3:
            notifs.append({
                'id': 'training_reminder',
                'icon': '⚡',
                'text': 'Du hast diese Woche noch nicht trainiert. 10 Minuten reichen.',
                'url': '/training',
            })

    return jsonify({'notifications': notifs[:2]})


@dashboard_bp.route('/api/analytics')
@login_required
def analytics():
    db = get_session()
    try:
        cutoff = datetime.now() - timedelta(days=30)
        logs = (db.query(ConversationLog)
                .filter(ConversationLog.org_id == g.org.id,
                        ConversationLog.created_at >= cutoff)
                .all())
        if not logs:
            return jsonify({'has_data': False})

        total = len(logs)
        avg_kb_end = round(sum(l.kb_end or 30 for l in logs) / total)
        total_einwaende = sum(l.einwaende_gesamt or 0 for l in logs)
        total_behandelt = sum(l.einwaende_behandelt or 0 for l in logs)
        erfolgsquote = round(total_behandelt / total_einwaende * 100) if total_einwaende > 0 else 0
        avg_redeanteil = round(sum(l.redeanteil_avg or 0 for l in logs) / total)

        typ_cnt = {}
        for log in logs:
            if not log.gegenargument_details:
                continue
            try:
                details = json.loads(log.gegenargument_details)
                for ga in details:
                    t = ga.get('einwand_typ', '')
                    if t:
                        typ_cnt[t] = typ_cnt.get(t, 0) + 1
            except Exception:
                pass
        top_einwaende = sorted(typ_cnt.items(), key=lambda x: -x[1])[:3]

        kb_vals = [l.kb_end or 30 for l in sorted(logs, key=lambda x: x.created_at or datetime.min)]
        trend = 'up'
        if len(kb_vals) >= 4:
            half = len(kb_vals) // 2
            avg_first = sum(kb_vals[:half]) / half
            avg_last = sum(kb_vals[half:]) / len(kb_vals[half:])
            trend = 'up' if avg_last >= avg_first else 'down'

        return jsonify({
            'has_data': True,
            'gespraeche': total,
            'avg_kb': avg_kb_end,
            'erfolgsquote': erfolgsquote,
            'avg_redeanteil': avg_redeanteil,
            'trend': trend,
            'top_einwaende': [{'typ': t, 'count': c} for t, c in top_einwaende],
            'total_einwaende': total_einwaende,
        })
    finally:
        db.close()
