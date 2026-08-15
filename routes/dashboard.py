import os
import re
import json
import hashlib
import traceback
from datetime import datetime, timedelta, date
from difflib import SequenceMatcher
from flask import Blueprint, render_template, redirect, url_for, g, session as flask_session, jsonify, request, abort
from routes.auth import login_required
from database.db import get_session
from database.models import Profile, User as UserModel, ConversationLog, Organisation
from services.live_session import LOG_DIR
import config
from services.claude_service import claude_client, http_llm_client

dashboard_bp = Blueprint('dashboard', __name__)


def _parse_kunden_meta(pt_name):
    """Extract kunden_name + kunden_alter from PersonalityType.name (Phase 07.2 Wave 1).

    Pattern: 'Markus Wendland, 48' -> ('Markus Wendland', '48')
    Archetype: 'Beschaeftigter Chef' -> (None, None)
    Empty / None input -> (None, None)

    Returns: (name:str|None, alter:str|None)
    """
    if not pt_name:
        return (None, None)
    m = re.match(r'^(.+?),\s*(\d+)$', pt_name.strip())
    if not m:
        return (None, None)
    return (m.group(1).strip(), m.group(2).strip())


def _dedupe_painpoints(painpoints):
    """UAT-R2 I / UAT-R3 I-bis: Dedupe near-duplicate painpoints (SequenceMatcher > 0.60, keep first).

    Backend-Dedupe vermeidet dass zwei fast-identische Painpoints (vom Analyse-Loop
    doppelt erzeugt) in Section 7 des Session-Details nebeneinander stehen.

    Threshold-History:
      UAT-R2 (0.75): zu strikt — User sah weiterhin Near-Duplikate wie
        "Vertriebler wissen im Moment eines Einwands nicht, was sie sagen sollen"
        vs "Vertriebler haben im Moment des Einwands keine Antwort parat"
        (gemessener Ratio: 0.656 — rutschte durch den 0.75-Filter).
      UAT-R3 (0.60): faengt obiges Beispielpaar ab, bleibt aber deutlich ueber
        0.50, um False-Positives bei inhaltlich verschiedenen Painpoints zum
        selben Thema zu vermeiden.

    Painpoint-Shape (aus ConversationLog.painpoints_details JSON):
      [{text: str, ts: str|None}, ...]
    """
    if not painpoints:
        return painpoints
    result = []
    for p in painpoints:
        if not isinstance(p, dict):
            continue
        text = (p.get('text') or p.get('beschreibung') or '').strip().lower()
        if not text:
            continue
        is_dup = any(
            SequenceMatcher(None, text, (r.get('text') or r.get('beschreibung') or '').strip().lower()).ratio() > 0.60
            for r in result
        )
        if not is_dup:
            result.append(p)
    return result


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
            'profil': c.profile_name or '-',
            'relative': _relative_date(c.created_at) if c.created_at else '-',
        })
    return result


def get_recent_logs(user_id, org_id, rolle, limit=5):
    # Phase 08.23.2.AUTH-LOGS-TENANT: Widget respektiert jetzt die Firmen-Grenze — owner/admin sehen
    # NUR Logs der eigenen Firma (org_id JETZT genutzt). Kein is_superadmin-Bypass. fail-closed.
    is_admin = rolle in ('owner', 'admin')
    org_ids = None
    if is_admin:
        db = get_session()
        try:
            org_ids = {u.id for u in db.query(UserModel).filter_by(org_id=org_id).all()}
        except Exception:
            org_ids = set()  # fail-closed: nichts zeigen statt 'alle'
        finally:
            db.close()
    result = []
    try:
        files = sorted(
            [f for f in os.listdir(LOG_DIR) if f.endswith('.txt') and f != '.gitkeep'],
            reverse=True
        )
        for fname in files:
            if is_admin:
                m = re.search(r'_U(\d+)_', fname)
                uid = int(m.group(1)) if m else None
                if uid is None or uid not in org_ids:
                    continue
            else:
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
        msg = http_llm_client(long_running=True).messages.create(
            model=config.MODEL_WEEKLY_SUMMARY,
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        try:
            from services.cost_tracker import log_api_cost
            _u = getattr(msg, 'usage', None)
            if _u:
                _in = getattr(_u, 'input_tokens', 0) or 0
                _out = getattr(_u, 'output_tokens', 0) or 0
                log_api_cost('anthropic', 'sonnet-4-5', user_id=getattr(user, 'id', None),
                             units=_in/1000.0, unit_type='per_1k_input_tokens',
                             context_tag='weekly_dashboard', call_site='weekly')
                log_api_cost('anthropic', 'sonnet-4-5', user_id=getattr(user, 'id', None),
                             units=_out/1000.0, unit_type='per_1k_output_tokens',
                             context_tag='weekly_dashboard', call_site='weekly')
        except Exception as _e:
            print(f"[CostHook] weekly_summary skipped: {_e}")
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
    avg_deal = 4000  # TODO: derive from org.branche or user profile
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
        'branche':                 'Sonstiges',
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
        return render_template('marketing/landing.html', open_modal=modal)
    db = get_session()
    try:
        u = db.get(UserModel, flask_session['user_id'])
        if not u or not u.aktiv:
            flask_session.clear()
            return render_template('marketing/landing.html', open_modal='')
    finally:
        db.close()
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/dashboard')
@login_required
def index():
    db = get_session()
    try:
        user = db.query(UserModel).get(g.user.id)

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
        recent_logs = get_recent_logs(g.user.id, g.org.id, g.user.rolle)
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

        # ── D-12: Persistente Trainings-Empfehlung ────────────────────────
        training_recommendation = None
        try:
            if hasattr(g.user, 'pending_training_recommendation') and g.user.pending_training_recommendation:
                import json as _jtr
                training_recommendation = _jtr.loads(g.user.pending_training_recommendation)
        except Exception:
            pass

        # ── Coach-Modul data (Phase 04.11) ─────────────────────────────────
        try:
            from services.coaching_service import get_active_cards, get_or_generate_weekly_report, get_longterm_data
            import json as _json
            learning_cards = get_active_cards(g.user.id)
            weekly_report = get_or_generate_weekly_report(g.user.id)
            longterm_data = get_longterm_data(g.user.id, weeks=12)
        except Exception as _ce:
            print(f"[Coach] Dashboard data error: {_ce}")
            learning_cards = []
            weekly_report = None
            longterm_data = None

        # D-12 (AUTH-2 Plan 05): persistentes Skip-Banner — sichtbar wenn onboarding_state='skipped'
        # UND kein aktives Profil. Pflicht-Banner bis Profil existiert (Training ist sonst 404).
        _user_state = getattr(user, 'onboarding_state', None)
        _has_profile = bool(getattr(user, 'active_profile_id', None))
        show_no_profile_banner = (_user_state == 'skipped' and not _has_profile)

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
                               dashboard_style=dashboard_style,
                               learning_cards=learning_cards,
                               weekly_report=weekly_report,
                               longterm_data_json=_json.dumps(longterm_data, ensure_ascii=False) if longterm_data else 'null',
                               training_recommendation=training_recommendation,
                               show_no_profile_banner=show_no_profile_banner)
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


@dashboard_bp.route('/analytics')
@login_required
def analytics_page():
    from database.models import ConversationLog as CL
    db = get_session()
    try:
        mode = (request.args.get('mode') or '').strip()
        q = db.query(CL).filter(CL.user_id == g.user.id)
        if mode in ('cold_call', 'meeting', 'training'):
            q = q.filter(CL.session_mode == mode)
        q = q.order_by(CL.id.desc()).limit(200)
        rows = q.all()
        return render_template('analytics.html',
                               sessions=rows,
                               active_mode=mode)
    finally:
        db.close()


@dashboard_bp.route('/session/<int:sid>')
@login_required
def session_detail(sid):
    from database.models import ConversationLog as CL, ObjectionEvent, PersonalityType
    from routes.app_routes import _calc_call_score, _derive_practice_recommendations
    import json as _json

    db = get_session()
    try:
        conv = db.query(CL).filter(
            CL.id == sid,
            CL.user_id == g.user.id,
        ).first()
        if not conv:
            abort(404)

        events = db.query(ObjectionEvent).filter(
            ObjectionEvent.conversation_log_id == sid,
        ).order_by(ObjectionEvent.id.asc()).all()

        # Phase 07.1: personality pre-resolve (kein relationship() am Model, PATTERNS 4.9)
        pt = None
        if conv.personality_type_id:
            pt = db.query(PersonalityType).filter_by(id=conv.personality_type_id).first()

        # Phase 07.1 (W-06): score_total typ-aware
        #  - Live: _calc_call_score (Gesamt-Score, 4 Komponenten)
        #  - Training: kb_end Fallback (kein _calc_call_score fuer Training)
        conv_typ = (conv.typ or 'live')

        # Fix B (07.1 UAT-R1): kb_end konsistent aus kb_verlauf-Endpunkt ableiten,
        # falls Verlauf vorhanden — sonst weicht Score-Hero vom Chart-Ende ab.
        # kb_verlauf-Shape: [{ts: "HH:MM:SS", wert: 0-100}]
        kb_end_effective = conv.kb_end
        try:
            if conv.kb_verlauf:
                _verl = _json.loads(conv.kb_verlauf)
                if isinstance(_verl, list) and _verl:
                    _last = _verl[-1]
                    if isinstance(_last, dict) and 'wert' in _last:
                        kb_end_effective = _last.get('wert')
        except Exception:
            # Fallback auf conv.kb_end bei kaputtem JSON — nicht blocken
            kb_end_effective = conv.kb_end
        if kb_end_effective is None:
            kb_end_effective = 0

        if conv_typ == 'live':
            # Score mit dem effektiven kb_end berechnen (mini-Shim um _calc_call_score
            # ohne zweite Helper-Variante): temporaer conv.kb_end setzen, Score holen,
            # urspruenglichen Wert zurueckschreiben — Session-Lifecycle bleibt read-only.
            _orig_kb = conv.kb_end
            try:
                conv.kb_end = kb_end_effective
                score_total = _calc_call_score(conv)
            finally:
                conv.kb_end = _orig_kb
        else:
            score_total = kb_end_effective

        # Phase 07.1 (W-06): Trend-Avg typ-diskriminierend.
        # Live    -> _calc_call_score ueber letzte 5 typ='live'.
        # Training-> kb_end ueber letzte 5 typ='training' (kein _calc_call_score
        #            fuer Training definiert; Score-Hero nutzt ebenfalls kb_end).
        # Wave 4 / POLISH-33: Training-Trend-Badge wieder aktiv — Template-Gate
        # 'conv.typ != training' entfaellt parallel.
        trend_avg = None
        recent = (db.query(CL)
                    .filter(CL.user_id == g.user.id)
                    .filter(CL.typ == conv_typ)
                    .filter(CL.id != conv.id)
                    .order_by(CL.created_at.desc())
                    .limit(5).all())
        if recent:
            if conv_typ == 'live':
                trend_avg = round(sum(_calc_call_score(c) for c in recent) / len(recent))
            else:
                # Training-Schnitt ueber kb_end (None-tolerant, None->0 behandeln
                # damit eine einzelne leere kb_end keine Division-Error-Kette ausloest)
                _vals = [(c.kb_end if c.kb_end is not None else 0) for c in recent]
                trend_avg = round(sum(_vals) / len(_vals)) if _vals else None

        # Phase 07.1: chart_data_json typ-diskriminierend
        if conv_typ == 'training':
            chart_data_json = conv.stimmung_history or '[]'
        else:
            chart_data_json = conv.kb_verlauf or '[]'

        # Phase 07.1: schwierigkeit_label aus phasen_details parsen (RESEARCH Q2 Option A)
        # Wave 4 / POLISH-32: Default-Wert None statt '—' — Template blendet Badge
        # komplett aus wenn None (kein em-dash-Placeholder mehr im Header).
        schwierigkeit_label = None
        if conv_typ == 'training' and conv.phasen_details:
            try:
                pd = _json.loads(conv.phasen_details)
                raw = (pd.get('schwierigkeit') if isinstance(pd, dict) else None) or ''
                mapping = {
                    'leicht':   'Einsteiger',
                    'mittel':   'Fortgeschritten',
                    'schwer':   'Experte',
                    'einsteiger': 'Einsteiger',
                    'fortgeschritten': 'Fortgeschritten',
                    'experte':  'Experte',
                }
                schwierigkeit_label = mapping.get(str(raw).lower()) or None
            except Exception:
                schwierigkeit_label = None

        # Phase 07.2 Wave 1: schwierigkeit_raw als raw-Key fuer "Nochmal trainieren"-URL (Plan 03).
        # schwierigkeit_label ist User-facing Mapping ("Einsteiger"), schwierigkeit_raw der
        # raw-Key ("leicht"). Nur setzen wenn schwierigkeit_label erfolgreich geparst wurde —
        # dann ist Konsistenz garantiert. Whitelist auf 3 Werte (T-07.2-04b Tampering-Mitigation).
        schwierigkeit_raw = None
        if schwierigkeit_label is not None and conv.phasen_details:
            try:
                pd2 = _json.loads(conv.phasen_details)
                raw2 = (pd2.get('schwierigkeit') if isinstance(pd2, dict) else None) or ''
                raw2_lower = str(raw2).lower()
                if raw2_lower in ('leicht', 'mittel', 'schwer'):
                    schwierigkeit_raw = raw2_lower
            except Exception:
                schwierigkeit_raw = None

        # Phase 07.2 Wave 1: Scoring-Listen aus phasen_details extrahieren (Training only).
        # Template rendert Sektionen 12 (Wendepunkt), 13 (6 Einzel-Scores), 14 (Verbesserungen)
        # aus diesen Listen. isinstance-Guards + silent-except gegen manipulierte JSON-Payloads
        # (T-07.2-02 Tampering-Mitigation).
        scoring_kategorien = []
        scoring_wendepunkte_detail = []
        scoring_verbesserungen = []
        if conv_typ == 'training' and conv.phasen_details:
            try:
                pd = _json.loads(conv.phasen_details)
                if isinstance(pd, dict):
                    _cat = pd.get('kategorien')
                    if isinstance(_cat, list):
                        scoring_kategorien = _cat
                    _wp = pd.get('wendepunkte_detail')
                    if isinstance(_wp, list):
                        scoring_wendepunkte_detail = _wp
                    _vb = pd.get('verbesserungen')
                    if isinstance(_vb, list):
                        scoring_verbesserungen = _vb
            except Exception:
                # Silent fallback auf leere Listen (Template rendert Empty-State)
                pass

        # Phase 07.2 Wave 1: Kunden-Metadaten aus PersonalityType.name parsen (Training only).
        # Pattern "Vorname Nachname, Alter" -> (name, alter); Archetype-Name -> (None, None).
        # Phase 07.2 UAT-R1 Fix 1: Fallback auf phasen_details.custom_persona_name, wenn
        # die Training-Session mit einer UNSAVED Custom-Persona (generated_personality) lief.
        # In dem Fall ist personality_type_id=NULL (kein pt-Datensatz), aber training_end()
        # persistiert den Custom-Namen in phasen_details. Wir bauen zusaetzlich einen
        # Display-Badge (kunden_display_name / kunden_display_icon), damit das Template
        # bei Custom-Kunden mindestens den Namen prominent zeigen kann.
        kunden_name = None
        kunden_alter = None
        kunden_display_name = None
        kunden_display_icon = None
        if conv_typ == 'training':
            if pt:
                kunden_name, kunden_alter = _parse_kunden_meta(pt.name)
                kunden_display_name = pt.name
                kunden_display_icon = pt.icon or None
            elif conv.phasen_details:
                try:
                    _pd_cp = _json.loads(conv.phasen_details)
                    if isinstance(_pd_cp, dict):
                        _cp_name_raw = _pd_cp.get('custom_persona_name')
                        if isinstance(_cp_name_raw, str) and _cp_name_raw.strip():
                            kunden_name, kunden_alter = _parse_kunden_meta(_cp_name_raw)
                            kunden_display_name = _cp_name_raw.strip()
                            _cp_icon_raw = _pd_cp.get('custom_persona_icon')
                            if isinstance(_cp_icon_raw, str) and _cp_icon_raw.strip():
                                kunden_display_icon = _cp_icon_raw.strip()
                except Exception:
                    # Silent fallback — None/None belassen
                    pass

        # Phase 07.1: Recommendations
        recommendations = _derive_practice_recommendations(db, conv, events)

        # UAT-R2 I / UAT-R3 I-bis: Painpoints im Backend dedupen, damit Template
        # clean bleibt. Backend erzeugt gelegentlich fast-identische Painpoints
        # (z.B. leichte Umformulierung desselben Schmerzpunkts) — SequenceMatcher
        # > 0.60 => Dup. (UAT-R2 startete mit 0.75, war zu strikt — siehe Helper.)
        _pp_raw = []
        try:
            if conv.painpoints_details:
                _pp_parsed = _json.loads(conv.painpoints_details)
                if isinstance(_pp_parsed, list):
                    _pp_raw = _pp_parsed
        except Exception:
            _pp_raw = []
        painpoints = _dedupe_painpoints(_pp_raw)

        # ── TAXO2-Plan 04/05 (FOLD 26.06.) — "Neu — Vorschau"-Panel (ADDITIV, read-only) ──────────
        # Die zum Call gehoerende live-rubric_score-Zeile lesen (Beobachtungen statt Zahl,
        # TAXO2-Plan 05) + outcome_confirmed (METRIK-1 D-20/D-21: MARKIERUNG, keine Sperre mehr —
        # die frueher hier stehende Etikettierung als Schutz vor durchsickernden Ergebnissen war
        # ein Irrtum; der Bewerter ist ergebnis-blind und laeuft vor jeder Anzeige).
        # Plan 05: observations_jsonb + _compliance werden SEPARAT extrahiert und als
        # observations_display (geordnet nach DIMENSIONS) + compliance_verletzt/compliance_beleg
        # ans Template gegeben — Template bleibt dumm (Punkt 27: einfachster tragfaehiger Weg).
        # rubric_score hat FORCE RLS; Request-Pfad-GUC (g.tenant_id) erlaubt das Lesen der Zeile.
        rubric_preview = None
        outcome_confirmed = False
        observations_display = []   # [{name, eintraege:[{beobachtung, beleg_zitat}]}] je Dimension
        compliance_verletzt = False
        compliance_beleg = ''
        try:
            from database.models import Call as _Call, RubricScore as _RubricScore
            from services.judge_dimensions import DIMENSIONS as _DIMENSIONS
            _call_row = (db.query(_Call)
                           .filter(_Call.conversation_log_id == sid,
                                   _Call.user_id == g.user.id)
                           .order_by(_Call.started_at.desc())
                           .first())
            if _call_row is not None:
                outcome_confirmed = (_call_row.outcome is not None)
                rubric_preview = (db.query(_RubricScore)
                                    .filter(_RubricScore.call_id == _call_row.id,
                                            _RubricScore.origin == 'live')
                                    .first())
            if rubric_preview is not None:
                # FORM-GARANTIE (Fehler-500, 2026-08-01): observations_jsonb ist JSONB — die Form
                # ist in der DB NIRGENDS erzwungen. Steht dort etwas anderes als erwartet (String,
                # Zahl, dict statt Liste), bricht sonst erst das Template, also NACH dem try/except
                # unten — dort, wo kein Netz mehr haengt. Deshalb die Form HIER erzwingen, wo sie
                # entsteht: der Anzeige-Pfad bekommt garantiert [{name, eintraege: list[dict]}].
                _obs = rubric_preview.observations_jsonb
                if not isinstance(_obs, dict):
                    _obs = {}
                # _compliance separat extrahieren — NICHT in die Dimensions-Schleife mischen
                _compliance = _obs.get('_compliance')
                if not isinstance(_compliance, dict):
                    _compliance = {}
                compliance_verletzt = bool(_compliance.get('verletzt'))
                compliance_beleg = _compliance.get('beleg_zitat') or ''
                # observations_display: geordnet nach fester DIMENSIONS-Reihenfolge
                for _dim in _DIMENSIONS:
                    _key = _dim['key']
                    _roh = _obs.get(_key)
                    # Nur echte Listen; Nicht-dict-Eintraege darin verwerfen (das Template ruft
                    # obs.get(...) — ein String an dieser Stelle waere der naechste 500).
                    _items = [_e for _e in _roh if isinstance(_e, dict)] if isinstance(_roh, list) else []
                    observations_display.append({
                        'name': _dim['name'],
                        # Schluessel heisst 'eintraege', NICHT 'items': in Jinja2 loest der
                        # Punkt-Zugriff `dim.items` ueber getattr auf und trifft die Dict-METHODE
                        # dict.items statt den Schluessel -> `{% for obs in dim.items %}` warf
                        # "TypeError: 'builtin_function_or_method' object is not iterable" (HTTP 500
                        # auf der Auswertungs-Seite, 2026-08-01). Der Name war die Falle, nicht der
                        # Zugriff — deshalb umbenannt statt am Template geflickt.
                        'eintraege': _items,
                    })
        except Exception as _e_preview:
            # Vorschau-Panel ist nice-to-have — ein Fehler darf session_detail NIE brechen.
            print(f'[TAXO2-05] rubric_preview Lese-Fehler (non-fatal) sid={sid}: {_e_preview}')
            rubric_preview = None
            observations_display = []
            compliance_verletzt = False
            compliance_beleg = ''

        # ── SICHERHEITSNETZ um das Rendern (Fehler-500, 2026-08-01) ──────────────────────────
        # Der except oben endet VOR dieser Zeile. Ein Fehler im Vorschau-Panel entsteht aber erst
        # BEIM Rendern (Jinja) — das Netz hing also nie dort, wo gerissen wird, und die Zusage im
        # Kommentar oben ("darf session_detail NIE brechen") war faktisch falsch. Sie wird hier
        # wahr gemacht: bricht der Render, wird EINMAL ohne Vorschau-Daten neu gerendert.
        # Der Fehler wird NICHT stumm geschluckt — Typ, Meldung und voller Traceback gehen ins Log.
        def _render(_preview_on=True):
            return render_template(
                'session_detail.html',
                conv=conv,
                events=events,
                # Bei _preview_on=False faellt NUR das Vorschau-Panel weg; der Rest der Seite
                # (Transkript, Chart, Empfehlungen) bleibt vollstaendig.
                rubric_preview=(rubric_preview if _preview_on else None),        # TAXO2-05: live-rubric_score-Zeile (status + guard)
                # METRIK-1 D-20: Markierung "Ergebnis nicht bestaetigt" (calls.outcome IS NOT NULL).
                # Der Fallback-Wert False bleibt bewusst: im Fallback-Render wird die Karte ohnehin
                # ohne Vorschau-Daten gezeichnet, und False erzeugt dort dieselbe Markierung wie ein
                # unbestaetigter Anruf. Das ist die konservative Richtung — lieber einmal zu viel
                # markiert als eine Bewertung faelschlich als "zaehlt" ausgewiesen.
                outcome_confirmed=(outcome_confirmed if _preview_on else False),
                observations_display=(observations_display if _preview_on else []),   # TAXO2-05: [{name, eintraege}] je Dimension
                compliance_verletzt=(compliance_verletzt if _preview_on else False),  # TAXO2-05: _compliance.verletzt bool
                compliance_beleg=(compliance_beleg if _preview_on else ''),           # TAXO2-05: _compliance.beleg_zitat str
                pt=pt,
                trend_avg=trend_avg,
                chart_data_json=chart_data_json,
                schwierigkeit_label=schwierigkeit_label,
                recommendations=recommendations,
                score_total=score_total,            # W-06: Gesamt-Score fuer Score-Hero
                kb_end_effective=kb_end_effective,  # Fix B (UAT-R1): = letzter kb_verlauf-Punkt falls vorhanden
                painpoints=painpoints,              # UAT-R2 I / UAT-R3 I-bis: dedupliziert (SequenceMatcher > 0.60)
                # Phase 07.2 Wave 1: Scoring-Konsolidierung Context-Keys
                scoring_kategorien=scoring_kategorien,                  # Sektion 13: 6 Einzel-Scores (Training only)
                scoring_wendepunkte_detail=scoring_wendepunkte_detail,  # Sektion 12: Wendepunkt-Analyse (Training only)
                scoring_verbesserungen=scoring_verbesserungen,          # Sektion 14: Verbesserungspotenzial (Training only)
                kunden_name=kunden_name,                                # Header-Subtext: "Vorname Nachname"
                kunden_alter=kunden_alter,                              # Header-Subtext: Alter-String
                kunden_display_name=kunden_display_name,                # UAT-R1 Fix 1: Custom-Kunden-Badge-Text (pt.name ODER custom_persona_name)
                kunden_display_icon=kunden_display_icon,                # UAT-R1 Fix 1: Custom-Kunden-Badge-Icon
                schwierigkeit_raw=schwierigkeit_raw,                    # Plan 03 "Nochmal trainieren"-URL raw-Key
            )

        try:
            return _render()
        except Exception as _e_render:
            # KEIN stilles Schlucken: Typ, Meldung und VOLLER Traceback ins Log
            # (auffindbar via `inspect.sh logs-errors`, Praefix [TAXO2-05] + sid).
            _tb_erst = traceback.format_exc()
            print(f'[TAXO2-05] session_detail Render-Fehler sid={sid}: '
                  f'{type(_e_render).__name__}: {_e_render}')
            print(f'[TAXO2-05] Traceback (Erst-Render) sid={sid}:\n{_tb_erst}')
            try:
                # Zweiter Versuch OHNE Vorschau-Daten — die Seite kommt degradiert statt als 500.
                return _render(_preview_on=False)
            except Exception as _e_fallback:
                # Der Fallback ist selbst gerissen -> der Fehler lag NICHT am Vorschau-Panel.
                # Der ERSTE Traceback wird hier noch einmal mitgegeben, damit ihn der zweite
                # nicht verdeckt (Vorgabe: nicht ueberschreiben), dann sauber weiterreichen:
                # ein 500 mit Log ist ehrlicher als eine stumme Falsch-Seite.
                print(f'[TAXO2-05] session_detail Fallback-Render ebenfalls gescheitert sid={sid}: '
                      f'{type(_e_fallback).__name__}: {_e_fallback}')
                print(f'[TAXO2-05] Traceback (Fallback) sid={sid}:\n{traceback.format_exc()}')
                print(f'[TAXO2-05] Traceback (Erst-Render, erneut) sid={sid}:\n{_tb_erst}')
                raise
    finally:
        db.close()


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
